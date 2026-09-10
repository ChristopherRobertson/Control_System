"""Independent equivalent-event workflow with verified cleanup and retention."""
from __future__ import annotations

from copy import deepcopy
from contextlib import nullcontext
from datetime import datetime, timezone
import math
import time
from uuid import uuid4

import numpy as np

from .acquisition import (AcquisitionIntegrityError, AcquisitionStopped, InstalledAcquirer,
                          SimulatedAcquirer, data)
from .settings import StroboscopySettings
from .timing import compile_timing


class AcquisitionFailure(RuntimeError):
    def __init__(self, message, record):
        super().__init__(message)
        self.record = record


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _validate_sample_selection(operation, settings):
    """Validate retained sample evidence independently of its producing module."""
    from control_app.measurement_host.interchange import sample_selection_from_dict
    selected_id=settings.identity.sample_selection_id
    candidates=[record for record in operation.sample_records
                if hasattr(record,"get") and record.get("selection_id")==selected_id]
    if not selected_id or len(candidates)!=1:
        raise ValueError("Real acquisition requires exactly one retained accepted sample selection matching sample_selection_id")
    selection=sample_selection_from_dict(data(candidates[0]))
    if selection.sample_id!=settings.identity.sample_id:
        raise ValueError("Accepted sample selection sample_id differs from selected sample identity")
    if selection.condition_id!=settings.identity.condition_id:
        raise ValueError("Accepted sample selection condition_id differs from selected condition identity")
    outside=[point.wavenumber_cm1 for point in settings.spectral_points if point.role=="band"
             and not any(window.lower_cm1<=point.wavenumber_cm1<=window.upper_cm1 for window in selection.windows)]
    if outside:
        raise ValueError(f"Selected band coordinates lie outside accepted sample spectral windows: {outside} cm⁻¹")


def _profile(context, operation, settings):
    identifiers = list(settings.promoted_bundle_ids)
    identifiers += [r.get("bundle_id") for r in operation.calibration_records if hasattr(r,"get") and r.get("bundle_id")]
    if operation.settings.get("_qualified_bundle_id"):
        identifiers.append(operation.settings["_qualified_bundle_id"])
    profiles = []
    for identifier in dict.fromkeys(identifiers):
        bundle = context.promoted_bundle(identifier)
        manifest = bundle.manifest if hasattr(bundle,"manifest") else bundle.get("manifest",bundle)
        if manifest.get("status") != "PROMOTED":
            raise ValueError("Calibration bundle is not explicitly PROMOTED")
        profile = manifest.get("microsecond_stroboscopy")
        if profile:
            modes = profile.get("modes",[profile.get("mode")])
            conditions = profile.get("condition_profile_ids",[profile.get("condition_profile_id")])
            if profile.get("experiment_id") == "microsecond_stroboscopy" and settings.mode in modes and settings.condition_profile_id in conditions:
                profiles.append(profile)
    if len(profiles) != 1:
        raise ValueError("Select exactly one applicable promoted microsecond acquisition profile")
    profile = profiles[0]
    for field in ("wiring_id","reset_equivalence_id","hf2li","tune_tolerance_cm1","settle_s"):
        if field not in profile or profile[field] is None:
            raise ValueError(f"Promoted microsecond profile is missing {field}")
    hf = profile["hf2li"]
    if not hf.get("signal_inputs") or not hf.get("pll") or not hf.get("integrity_nodes"):
        raise ValueError("Promoted HF2LI profile needs receiver settings, PLL and monitored integrity nodes")
    if not hf.get("phase_shift_deg") or not hf.get("signed_x_calibration_id"):
        raise ValueError("Promoted HF2LI profile needs calibrated signed-X phases and projection identity")
    clocks=profile.get("timing_clock_readbacks",{})
    if not clocks.get("t660_1") or not clocks.get("t660_2"):
        raise ValueError("Promoted profile must specify verified receiving-clock locks and master clock mode readbacks")
    if settings.controls.require_dark:
        dark=profile.get("normalization",{}).get("dark_offsets",{})
        for role in ("sample","reference") if settings.mode=="dual" else ("sample",):
            entry=dark.get(role,{})
            if not entry.get("record_id") or entry.get("record_id")!=settings.controls.dark_record_id:
                raise ValueError(f"Applicable measured {role} dark offset record must match selected dark control")
            if not isinstance(entry.get("offset"),(int,float)) or not math.isfinite(entry["offset"]):
                raise ValueError(f"Measured {role} dark offset is missing/nonfinite")
            if not isinstance(entry.get("standard_error"),(int,float)) or not math.isfinite(entry["standard_error"]) or entry["standard_error"]<0:
                raise ValueError(f"Measured {role} dark uncertainty is missing/invalid")
    if settings.reset.method != "passive_recovery":
        raise ValueError("Installed adapters cannot automate thermal, position, flow or replacement reset; use an explicitly completed physical reset")
    if not settings.reset.equivalent_state_verified or not settings.reset.equivalence_record_id:
        raise ValueError("Equivalent sample-state reset requires an accepted multi-observable record")
    if profile["reset_equivalence_id"] != settings.reset.equivalence_record_id:
        raise ValueError("Selected reset record is outside the promoted acquisition profile")
    return deepcopy(profile)


def _compatible(record, settings, label):
    if not isinstance(record,dict):
        raise ValueError(f"A complete compatible {label} record is required")
    if record.get("experiment_id") != settings.experiment_id or record.get("mode") != settings.mode:
        raise ValueError(f"{label} experiment/detector mode differs")
    if record.get("settings") != settings.to_dict():
        raise ValueError(f"{label} settings, calibration, sample or condition differs")
    if record.get("disposition",record.get("status")) != "complete":
        raise ValueError(f"{label} is interrupted or rejected")
    observed = {b["wavenumber_cm1"] for b in record.get("native_blocks",[]) if b.get("sample")}
    if observed != {p.wavenumber_cm1 for p in settings.spectral_points}:
        raise ValueError(f"{label} does not cover every selected wavenumber")
    if record.get("restoration",{}).get("safe_verified") is not True:
        raise ValueError(f"{label} restoration has not been verified")
    if record.get("kind")=="blank":
        expected={(p.wavenumber_cm1,float(delay)*1e-6,average) for p in settings.spectral_points
                  for delay in settings.delays_us for average in range(settings.averages)}
        blocks=[b for b in record.get("native_blocks",[]) if b.get("kind")=="blank_control"]
        actual={(b.get("wavenumber_cm1"),b.get("delay_s"),b.get("average_index")) for b in blocks}
        if actual!=expected or len(blocks)!=len(expected) or any(b.get("flags") for b in blocks):
            raise ValueError("Sequential blank is missing compatible declared delay/average control blocks")


def _local_level(block, settings):
    sample = block.get("sample",{})
    x = np.asarray(sample.get("x",[]),dtype=float)
    if len(x)<2 or not np.all(np.isfinite(x)) or np.any(x<=0):
        raise AcquisitionIntegrityError("Missing/nonpositive/invalid sample support during reset verification")
    if settings.mode == "dual":
        from .processing import normalized_observable
        response = settings.response
        tolerance=min(.49/response.sample_rate_sps,.49/response.reference_rate_sps)+response.reference_alignment_uncertainty_s
        result = normalized_observable(sample,block.get("reference"),tolerance_s=tolerance,
            sample_latency_s=response.detector_latency_s,reference_latency_s=response.reference_latency_s)
        if not np.isfinite(result["value"]) or result["flags"]:
            raise AcquisitionIntegrityError("Invalid matched reference support during reset verification")
        return float(result["value"])
    return float(np.mean(x))


def run_acquisition(context, operation, plan, *, kind="run", cancel=lambda:False,
                    progress=lambda message:None, preserve=None, preliminary=None, blank=None):
    """Run a frozen operation and preserve outcomes before releasing ownership.

    ``preserve(record)`` must durably save complete native arrays and return its
    path. It is called before devices, after each retained block, and following
    restoration. Analysis may be performed there after native saving. Failure
    records remain on ``AcquisitionFailure.record`` if persistence itself fails.
    """
    settings = getattr(plan,"settings",plan)
    if not isinstance(settings,StroboscopySettings):
        settings = StroboscopySettings.from_dict(data(settings))
    if kind not in ("run","blank","preliminary"):
        raise ValueError("Unsupported microsecond acquisition kind")
    if operation.instance_id != settings.instance_id or context.instance_id != settings.instance_id:
        raise ValueError("Frozen operation belongs to another detector mode")
    if preserve is None:
        from .persistence import save_run
        preserve = lambda record: save_run(operation.output_path,record)
    record = {"schema_version":1,"experiment_id":settings.experiment_id,"mode":settings.mode,
        "instance_id":settings.instance_id,"run_id":operation.run_id,"plan_id":operation.plan_id,
        "started_utc":operation.started_utc,"kind":kind,"settings":settings.to_dict(),
        "operation":operation.to_dict(),"native_blocks":[],"readbacks":{},"restoration":{},
        "disposition":"preparing","status":"preparing","errors":[],"simulation":not operation.hardware}
    if preliminary is not None:
        record["preliminary"] = deepcopy(preliminary)
    if blank is not None:
        record["blank_record"] = deepcopy(blank)
    acquirer, safe, saved, primary = None, True, False, None
    started = time.monotonic()
    def save():
        nonlocal saved
        progress("Saving: retaining complete native and restoration records")
        record["elapsed_s"] = time.monotonic()-started
        record["native_path"] = str(preserve(record))
        saved = True
    def new_block(wave,block_kind,delay=0.,average=0):
        block = {"block_id":str(uuid4()),"event_id":str(uuid4()),"wavenumber_cm1":float(wave),
                 "kind":block_kind,"delay_s":float(delay),"average_index":average,
                 "acquisition_order":len(record["native_blocks"]),"started_utc":_utc(),"flags":[]}
        record["native_blocks"].append(block)
        return block
    def observe(wave,block_kind,duration):
        block = new_block(wave,block_kind)
        acquirer.observe(duration,block)
        block["completed_utc"] = _utc()
        save()
        return block
    with context.hardware_scope(operation) if operation.hardware else nullcontext():
        context.lifecycle.notify_state(True,"microsecond stroboscopy "+kind)
        try:
            from .planner import build_plan
            validation = build_plan(settings)
            if validation.readiness.errors:
                raise ValueError("; ".join(validation.readiness.errors))
            if (settings.response.sample_demodulator,settings.response.reference_demodulator,settings.response.timing_demodulator)!=(0,3,2):
                raise ValueError("Installed wiring assigns sample/reference/timing demodulators 0/3/2")
            if operation.hardware:
                _validate_sample_selection(operation,settings)
            if settings.mode == "single" and kind in ("preliminary","run"):
                _compatible(blank,settings,"sequential blank")
            if kind == "run":
                _compatible(preliminary,settings,"reviewed preliminary")
            if settings.mode == "dual" and kind == "blank":
                raise ValueError("Dual mode uses simultaneous reference; no routine sequential blank")
            profile = _profile(context,operation,settings) if operation.hardware else {}
            record["qualification"]=deepcopy(profile)
            if operation.hardware:
                applicable = build_plan(settings,qualification=profile)
                preflight_issues=[i.message for i in applicable.readiness.issues if i.severity in ("error","blocker") and i.code!="installed_readbacks"]
                if preflight_issues:
                    raise ValueError("; ".join(preflight_issues))
            # Destination writability is established before a factory can touch
            # an instrument. The final callback also runs for rejected setup.
            save()
            if cancel():
                raise AcquisitionStopped("Acquisition stopped")
            injected = {"hf2li","mircat","t660_1","t660_2"}.issubset(context.devices.available(hardware=operation.hardware))
            cls = InstalledAcquirer if operation.hardware or injected else SimulatedAcquirer
            if cls is InstalledAcquirer and not operation.hardware:
                profile = data(operation.configuration).get("microsecond_stroboscopy",{})
                record["qualification"]=deepcopy(profile)
            acquirer = cls(context,operation,settings,profile,cancel=cancel,progress=progress)
            safe = False
            program = compile_timing(settings,delays_us=[settings.delays_us[0]],pumped=False)
            record["readbacks"] = acquirer.prepare(program)
            if operation.hardware:
                from .planner import capabilities_from_readbacks
                capabilities=capabilities_from_readbacks(settings,record["readbacks"])
                record["capabilities"]=data(capabilities)
                connected=build_plan(settings,qualification=profile,capabilities=capabilities)
                if not connected.hardware_ready:
                    raise ValueError("; ".join(connected.readiness.errors+connected.readiness.blockers))
            record["status"] = record["disposition"] = "acquiring"
            delays = sorted(settings.delays_us,reverse=settings.delay_order=="descending")
            for point in settings.spectral_points:
                acquirer.check()
                wave = point.wavenumber_cm1
                record["readbacks"]["tune"] = acquirer.tune(wave)
                baseline_kind = kind if kind in ("blank","preliminary") else "baseline"
                duration = settings.controls.preliminary_duration_s if kind=="preliminary" else settings.controls.baseline_duration_s
                baseline = observe(wave,baseline_kind,duration)
                baseline_level = _local_level(baseline,settings)
                if kind == "blank":
                    for average in range(settings.averages):
                        for delay in settings.delays_us:
                            event = compile_timing(settings,delays_us=[delay],pumped=False)
                            block = new_block(wave,"blank_control",delay*1e-6,average)
                            acquirer.capture(event,block)
                            block["completed_utc"] = _utc()
                            save()
                    continue
                if kind != "run":
                    continue
                reviewed_blocks=[b for b in preliminary.get("native_blocks",[]) if b.get("wavenumber_cm1")==wave and b.get("kind")=="preliminary"]
                if not reviewed_blocks:
                    raise AcquisitionIntegrityError("Reviewed preliminary has no matching native baseline")
                reviewed_level=float(np.mean([_local_level(b,settings) for b in reviewed_blocks]))
                baseline_change=abs(baseline_level/reviewed_level-1)
                baseline["reviewed_state_verification"]={"relative_change":baseline_change,
                    "tolerance_fraction":settings.reset.tolerance_fraction,"passed":baseline_change<=settings.reset.tolerance_fraction}
                if baseline_change>settings.reset.tolerance_fraction:
                    baseline["flags"].append("initial_state_mismatch")
                    raise AcquisitionIntegrityError("Initial sample baseline differs from reviewed preliminary; pumping inhibited")
                for average in range(max(settings.averages,settings.controls.pump_blocked_averages)):
                    current_delays = list(reversed(delays)) if settings.delay_order=="alternating" and average%2 and average<settings.averages else delays
                    for delay in current_delays:
                        if average<settings.controls.pump_blocked_averages:
                            control_program=compile_timing(settings,delays_us=[delay],pumped=False)
                            control=new_block(wave,"pump_off",delay*1e-6,average)
                            acquirer.capture(control_program,control)
                            control["completed_utc"]=_utc()
                            save()
                        if average>=settings.averages:
                            continue
                        acquirer.wait(settings.reset.recovery_wait_s,"Recovery: qualified passive-equivalence interval")
                        reset = observe(wave,"reset",settings.reset.verification_duration_s)
                        relative = abs(_local_level(reset,settings)/baseline_level-1)
                        reset["reset_verification"] = {"relative_change":relative,"tolerance_fraction":settings.reset.tolerance_fraction,
                            "passed":relative<=settings.reset.tolerance_fraction,"scope":"online local baseline; full spectral/temperature equivalence belongs to selected qualification",
                            "equivalence_record_id":settings.reset.equivalence_record_id}
                        if relative>settings.reset.tolerance_fraction:
                            reset["flags"].append("unrecovered")
                            raise AcquisitionIntegrityError("Sample has not recovered to equivalent local baseline; no further pump and no retry")
                        event = compile_timing(settings,delays_us=[delay],pumped=True)
                        block = new_block(wave,"pumped",event.events[0].selected_delay_us*1e-6,average)
                        acquirer.capture(event,block)
                        block["completed_utc"] = _utc()
                        save()
                acquirer.wait(settings.reset.recovery_wait_s,"Recovery: final state verification")
                final = observe(wave,"post_run",settings.reset.verification_duration_s)
                if abs(_local_level(final,settings)/baseline_level-1)>settings.reset.tolerance_fraction:
                    final["flags"].append("unrecovered")
                    raise AcquisitionIntegrityError("Final sample state is unrecovered")
            record["status"] = record["disposition"] = "complete"
        except AcquisitionStopped as exc:
            primary = exc
            record["status"] = record["disposition"] = "interrupted"
            record["message"] = "Acquisition stopped"
        except Exception as exc:
            primary = exc
            record["status"] = record["disposition"] = "failed"
            record["errors"].append(str(exc))
        finally:
            if acquirer:
                if acquirer.current_block and not acquirer.current_block.get("completed_utc"):
                    acquirer.current_block.setdefault("flags",[]).append("incomplete")
                try:
                    record["restoration"] = acquirer.close()
                    safe = record["restoration"].get("safe_verified") is True
                except Exception as exc:
                    safe = False
                    record["restoration"] = {"safe_verified":False,"errors":[str(exc)]}
            else:
                record["restoration"] = {"safe_verified":True,"devices_created":False,"errors":[]}
            if not safe:
                record["status"] = record["disposition"] = "cleanup_failed"
                record["errors"] += record["restoration"].get("errors",[])
            record["finished_utc"] = _utc()
            saved = False
            try:
                save()
            except Exception as exc:
                record["preservation_error"] = str(exc)
                record["errors"].append("Required native preservation failed: "+str(exc))
                if safe:
                    record["status"] = record["disposition"] = "preservation_failed"
            if operation.hardware:
                context.ownership.release(operation.ownership,safe_verified=safe,preservation_verified=saved,
                    detail="; ".join(record["errors"]) or record["disposition"])
            context.lifecycle.notify_state(False,record["disposition"])
    if not safe or not saved or (primary is not None and not isinstance(primary,AcquisitionStopped)):
        raise AcquisitionFailure("; ".join(record["errors"]) or "Acquisition failed",record) from primary
    return record


def discover_capabilities(context, operation, *, cancel=lambda:False, progress=lambda message:None, preserve=None):
    """Guarded connected readback discovery with the same preservation ownership."""
    from .persistence import save_run
    preserve = preserve or (lambda record:save_run(operation.output_path,record))
    record = {"schema_version":1,"experiment_id":"microsecond_stroboscopy","mode":context.mode,
        "run_id":operation.run_id,"kind":"capabilities","settings":data(operation.settings),
        "native_blocks":[],"status":"preparing","disposition":"preparing","errors":[]}
    hf, safe, saved = None,True,False
    with context.hardware_scope(operation) if operation.hardware else nullcontext():
        try:
            preserve(record)
            if cancel(): raise AcquisitionStopped("Acquisition stopped")
            progress("Configuration: discovering connected HF2LI supported settings")
            hf = context.devices.create("hf2li",operation)
            hf.connect()
            safe = False
            method = hf.discover_dual_phase_scan_capabilities if context.mode=="dual" else hf.discover_phase_scan_capabilities
            record["capabilities"] = method()  # Device API, not another experiment.
            safe = True
            record["status"] = record["disposition"] = "complete"
        except Exception as exc:
            record["errors"].append(str(exc))
            record["status"] = record["disposition"] = "failed"
        finally:
            if hf:
                try: hf.close()
                except Exception as exc:
                    safe=False
                    record["errors"].append(str(exc))
            record["restoration"]={"safe_verified":safe,"errors":record["errors"]}
            try:
                record["native_path"]=str(preserve(record)); saved=True
            except Exception as exc: record["errors"].append(str(exc))
            if operation.hardware:
                context.ownership.release(operation.ownership,safe_verified=safe,preservation_verified=saved,detail="; ".join(record["errors"]))
    if record["errors"]:
        raise AcquisitionFailure("; ".join(record["errors"]),record)
    return record
