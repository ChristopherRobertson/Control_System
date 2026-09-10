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


def _runtime_configuration(operation, settings):
    """Optional run configuration and calibration, independent of promotion.

    Device addresses and wiring come from the frozen host configuration. Any
    selected scientific calibration stays explicit data and may improve claims;
    absent calibration never prevents native/electrical-relative acquisition.
    """
    configuration=data(operation.configuration)
    runtime=deepcopy(configuration.get("microsecond_stroboscopy",{}))
    for record in operation.calibration_records:
        record=data(record)
        if not isinstance(record,dict):
            continue
        candidate=record.get("microsecond_stroboscopy")
        if isinstance(candidate,dict):
            modes=candidate.get("modes",[candidate.get("mode",settings.mode)])
            if settings.mode in modes:
                for field in ("timing","normalization","response_calibration_id"):
                    if field in candidate:
                        runtime[field]=deepcopy(candidate[field])
                if record.get("record_kind")=="measured_response_calibration" and record.get("calibration_id") and record.get("source",{}).get("native_path"):
                    runtime["response_calibration_record"]=deepcopy(record)
    runtime.setdefault("hf2li",{})
    runtime.setdefault("settle_s",settings.budget.detector_settling_s_per_wavenumber)
    runtime.setdefault("tune_timeout_s",45.)
    runtime.setdefault("tune_tolerance_cm1",.1)
    runtime["configuration_basis"]="frozen installed configuration and connected device readbacks"
    return runtime


def _compatible(record, settings, label):
    if not isinstance(record,dict):
        raise ValueError(f"A complete compatible {label} record is required")
    if record.get("experiment_id") != settings.experiment_id or record.get("mode") != settings.mode:
        raise ValueError(f"{label} experiment/detector mode differs")
    kind="blank" if record.get("kind")=="blank" else "preliminary"
    if _pre_tune_signature(record.get("requested_settings",record.get("settings",{})),kind) != _pre_tune_signature(settings,kind):
        raise ValueError(f"{label} acquisition settings differ")
    if record.get("disposition",record.get("status")) != "complete":
        raise ValueError(f"{label} is interrupted or rejected")
    observed = {b["wavenumber_cm1"] for b in record.get("native_blocks",[]) if b.get("sample")}
    if observed != {p.wavenumber_cm1 for p in settings.spectral_points}:
        raise ValueError(f"{label} does not cover every selected wavenumber")
    if record.get("restoration",{}).get("safe_verified") is not True:
        raise ValueError(f"{label} restoration has not been verified")


def _pre_tune_signature(settings,kind):
    from .planner import acquisition_signature
    signature=acquisition_signature(settings,kind=kind)
    # SDK optical width is only known after the current wavelength is tuned.
    signature.get("timing",{}).pop("mircat_pulse_width_ns",None)
    return signature


def _reference_optical_widths(record,wavenumber):
    """Prefer wavelength-local device observations over the last tune summary."""
    blocks=[block for block in record.get("native_blocks",[]) if block.get("wavenumber_cm1")==wavenumber]
    fallback=record.get("actual_settings",record.get("settings",{})).get("timing",{}).get("mircat_pulse_width_ns")
    widths=[]
    for block in blocks:
        readbacks=block.get("readbacks",{})
        width=readbacks.get("mircat_pulse_parameters",{}).get("pulse_width_ns")
        if width is None:
            width=readbacks.get("actual_settings",{}).get("timing",{}).get("mircat_pulse_width_ns",fallback)
        widths.append(width)
    return widths or [fallback]


def _local_level(block, settings):
    sample = block.get("sample",{})
    x=np.asarray(sample.get("x",[]),dtype=float)
    y=np.asarray(sample.get("y",np.zeros_like(x)),dtype=float)
    if len(x)<2 or len(y)!=len(x) or not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise AcquisitionIntegrityError("Missing/nonfinite detector observations during baseline measurement")
    # Magnitude is only the live stability diagnostic. Native X/Y are retained
    # unchanged for independently chosen scientific normalization.
    return float(np.mean(np.hypot(x,y)))


def _detector_readback_signature(readbacks,mode):
    """Actual receiver and projection settings determine blank transfer."""
    device=readbacks.get("hf2li_device")
    nodes=readbacks.get("hf2li",{}).get("nodes",{})
    if not device or not nodes:
        return None
    values={"device_id":device}
    for index in (0,3) if mode=="dual" else (0,):
        for field in ("phaseshift","adcselect","oscselect","harmonic","sinc"):
            suffix=f"demods/{index}/{field}"
            values[suffix]=nodes.get(f"/{device}/{suffix}",{}).get("value")
    for index in (0,1) if mode=="dual" else (0,):
        for field in ("range","ac","diff","imp50"):
            suffix=f"sigins/{index}/{field}"
            values[suffix]=nodes.get(f"/{device}/{suffix}",{}).get("value")
    return values


def run_acquisition(context, operation, plan, *, kind="run", cancel=lambda:False,
                    progress=lambda message:None, preserve=None, preliminary=None, blank=None, acquirer_factory=None):
    """Run a frozen operation and preserve outcomes before releasing ownership.

    ``preserve(record)`` must durably save complete native arrays and return its
    path. It is called before devices, after each retained block, and following
    restoration. Analysis may be performed there after native saving. Failure
    records remain on ``AcquisitionFailure.record`` if persistence itself fails.
    """
    try:
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
            "requested_settings":settings.to_dict(),
            "operation":operation.to_dict(),"native_blocks":[],"readbacks":{},"restoration":{},
            "disposition":"preparing","status":"preparing","errors":[],"simulation":not operation.hardware}
        if preliminary is not None:
            record["preliminary"] = deepcopy(preliminary)
        if blank is not None:
            record["blank_record"] = deepcopy(blank)
    except Exception:
        # Setup can fail while allocating retained references. No device has
        # been accessed and no new native data exists at this point.
        if operation.hardware:
            context.ownership.release(operation.ownership,safe_verified=True,preservation_verified=True,
                detail="Operation record preparation failed before device access")
        raise
    progress_callback=progress
    def progress(message):
        try:
            progress_callback(message)
        except Exception as exc:
            record.setdefault("notification_errors",[]).append(str(exc))
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
        try:
            context.lifecycle.notify_state(True,"microsecond stroboscopy "+kind)
            from .planner import build_plan
            validation = build_plan(settings,kind=kind)
            if validation.readiness.errors:
                raise ValueError("; ".join(validation.readiness.errors))
            if (settings.response.sample_demodulator,settings.response.reference_demodulator,settings.response.timing_demodulator)!=(0,3,2):
                raise ValueError("Installed wiring assigns sample/reference/timing demodulators 0/3/2")
            for label,candidate in (("sequential blank",blank),("preliminary",preliminary)):
                if candidate is None:
                    continue
                try:
                    _compatible(candidate,settings,label)
                except (ValueError,TypeError,KeyError) as exc:
                    record.setdefault("unused_optional_records",[]).append({"kind":label,"reason":str(exc),"run_id":candidate.get("run_id") if isinstance(candidate,dict) else None})
                    if label=="sequential blank":
                        blank=None
                        record.pop("blank_record",None)
                    else:
                        preliminary=None
                        record.pop("preliminary",None)
            if settings.mode == "dual" and kind == "blank":
                raise ValueError("Dual mode uses simultaneous reference; no routine sequential blank")
            profile=_runtime_configuration(operation,settings)
            record["qualification"]=deepcopy(profile)
            # Destination writability is established before a factory can touch
            # an instrument. The final callback also runs for rejected setup.
            save()
            if cancel():
                raise AcquisitionStopped("Acquisition stopped")
            injected={"hf2li","mircat","t660_1","t660_2"}.issubset(context.devices.available(hardware=operation.hardware))
            if acquirer_factory is None:
                if not operation.hardware and not injected:
                    raise ValueError("Installed acquisition requires a hardware operation; developer simulation must be explicitly injected")
                acquirer_factory=InstalledAcquirer
            acquirer=acquirer_factory(context,operation,settings,profile,cancel=cancel,progress=progress)
            record["simulation"]=isinstance(acquirer,SimulatedAcquirer) or not operation.hardware
            safe = False
            program = compile_timing(settings,delays_us=[settings.delays_us[0]],pumped=False)
            record["readbacks"] = acquirer.prepare(program)
            settings=StroboscopySettings.from_dict(data(acquirer.settings))
            record["actual_settings"]=settings.to_dict()
            record["settings"]=settings.to_dict()
            actual_detector=_detector_readback_signature(record["readbacks"],settings.mode)
            for label,candidate in (("sequential blank",blank),("preliminary",preliminary)):
                if not isinstance(candidate,dict):
                    continue
                previous=candidate.get("actual_settings",candidate.get("settings",{}))
                comparison_kind="blank" if label=="sequential blank" else "preliminary"
                prior_detector=_detector_readback_signature(candidate.get("readbacks",{}),settings.mode)
                difference=[]
                if actual_detector is not None:
                    prior_detector=prior_detector or {}
                    difference=[key for key,value in actual_detector.items() if value is None or prior_detector.get(key)!=value]
                changed_settings=_pre_tune_signature(previous,comparison_kind)!=_pre_tune_signature(settings,comparison_kind)
                if changed_settings or difference:
                    reason="actual connected acquisition settings differ" if changed_settings else "actual detector receiver/projection settings differ: "+", ".join(difference)
                    record.setdefault("unused_optional_records",[]).append({"kind":label,"reason":reason,"run_id":candidate.get("run_id")})
                    if label=="sequential blank":
                        blank=None
                        record.pop("blank_record",None)
                    else:
                        preliminary=None
                        record.pop("preliminary",None)
            if operation.hardware:
                from .planner import capabilities_from_readbacks
                capabilities=capabilities_from_readbacks(settings,record["readbacks"])
                record["capabilities"]=data(capabilities)
                connected=build_plan(settings,qualification=profile,capabilities=capabilities,kind=kind)
                if connected.readiness.errors:
                    raise ValueError("; ".join(connected.readiness.errors))
                settings=connected.settings
                acquirer.settings=settings.to_dict()
                record["settings"]=settings.to_dict()
                record["actual_settings"]=settings.to_dict()
            measured=profile.get("response_calibration_record",{})
            parameters=measured.get("microsecond_stroboscopy",{}).get("response_parameters",{})
            required=("hf2_order","hf2_time_constant_s","sample_rate_sps","integration_aperture_s","detector_latency_s","jitter_s")
            if settings.mode=="dual":
                required+=("reference_order","reference_time_constant_s","reference_rate_sps","reference_latency_s")
            matches=bool(measured) and all(isinstance(parameters.get(key),(int,float)) and math.isfinite(parameters[key])
                and math.isclose(parameters[key],getattr(settings.response,key),rel_tol=1e-9,abs_tol=1e-15) for key in required)
            actual_settings=settings.to_dict()
            actual_settings["response"]["qualified"]=bool(matches)
            actual_settings["response"]["qualification_id"]=measured.get("calibration_id","") if matches else ""
            settings=StroboscopySettings.from_dict(actual_settings)
            acquirer.settings=actual_settings
            record["settings"]=deepcopy(actual_settings)
            record["actual_settings"]=deepcopy(actual_settings)
            record["status"] = record["disposition"] = "acquiring"
            delays = sorted(settings.delays_us,reverse=settings.delay_order=="descending")
            for point in settings.spectral_points:
                acquirer.check()
                wave = point.wavenumber_cm1
                record["readbacks"]["tune"] = acquirer.tune(wave)
                # MIRcat optical width is read back during each tune, separately
                # from the external trigger pulse. Preserve accepted values in
                # the run as well as the per-block device readbacks.
                record["actual_settings"] = data(acquirer.settings)
                record["settings"] = deepcopy(record["actual_settings"])
                optical_width=record["actual_settings"]["timing"]["mircat_pulse_width_ns"]
                for label,candidate in (("sequential blank",blank),("preliminary",preliminary)):
                    if not isinstance(candidate,dict):
                        continue
                    prior_widths=_reference_optical_widths(candidate,wave)
                    if any(not isinstance(value,(float,int)) or isinstance(value,bool) or not math.isfinite(value)
                           or value!=optical_width for value in prior_widths):
                        record.setdefault("unused_optional_records",[]).append({"kind":label,"run_id":candidate.get("run_id"),
                            "source_native_path":candidate.get("native_path"),"wavenumber_cm1":wave,
                            "reason":"Actual MIRcat optical pulse width differs or is unavailable at this wavenumber",
                            "actual_optical_width_ns":optical_width,"reference_optical_widths_ns":prior_widths})
                        if label=="sequential blank":
                            blank=None
                            record.pop("blank_record",None)
                        else:
                            preliminary=None
                            record.pop("preliminary",None)
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
                prior_blocks=[b for b in (preliminary or {}).get("native_blocks",[]) if b.get("wavenumber_cm1")==wave and b.get("kind")=="preliminary"]
                if prior_blocks:
                    prior_level=float(np.mean([_local_level(b,settings) for b in prior_blocks]))
                    baseline_change=abs(baseline_level/prior_level-1) if prior_level>0 else math.nan
                    baseline["preliminary_baseline_comparison"]={"relative_change":baseline_change,
                        "tolerance_fraction":settings.reset.tolerance_fraction,"passed":bool(math.isfinite(baseline_change) and baseline_change<=settings.reset.tolerance_fraction),"acquisition_gate":False}
                    if not math.isfinite(baseline_change) or baseline_change>settings.reset.tolerance_fraction:
                        baseline["flags"].append("initial_state_mismatch")
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
                        acquirer.wait(settings.reset.recovery_wait_s,"Waiting: requested interval before the next event")
                        reset = observe(wave,"reset",settings.reset.verification_duration_s)
                        relative = abs(_local_level(reset,settings)/baseline_level-1) if baseline_level>0 else math.nan
                        reset["reset_verification"] = {"relative_change":relative,"tolerance_fraction":settings.reset.tolerance_fraction,
                            "passed":bool(math.isfinite(relative) and relative<=settings.reset.tolerance_fraction),"scope":"observed local detector baseline; advisory for equivalent-state claims","acquisition_gate":False,
                            "equivalence_record_id":settings.reset.equivalence_record_id}
                        nonrecovery=not math.isfinite(relative) or relative>settings.reset.tolerance_fraction
                        if nonrecovery:
                            reset["flags"].append("reset_nonrecovery")
                        event = compile_timing(settings,delays_us=[delay],pumped=True)
                        block = new_block(wave,"pumped",event.events[0].selected_delay_us*1e-6,average)
                        acquirer.capture(event,block)
                        if nonrecovery:
                            block["flags"].append("reset_nonrecovery")
                        block["completed_utc"] = _utc()
                        save()
                acquirer.wait(settings.reset.recovery_wait_s,"Recovery: final state verification")
                final = observe(wave,"post_run",settings.reset.verification_duration_s)
                final_change=abs(_local_level(final,settings)/baseline_level-1) if baseline_level>0 else math.nan
                if not math.isfinite(final_change) or final_change>settings.reset.tolerance_fraction:
                    final["flags"].append("reset_nonrecovery")
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
            try:
                context.lifecycle.notify_state(False,record["disposition"])
            except Exception as exc:
                record.setdefault("notification_errors",[]).append(str(exc))
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
