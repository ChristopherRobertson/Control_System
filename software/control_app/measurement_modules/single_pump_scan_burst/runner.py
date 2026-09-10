"""Durable one-pump lifecycle shared as pure implementation by isolated tabs."""
from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
from dataclasses import dataclass, field as dataclass_field, replace
from pathlib import Path
from threading import Event
from time import monotonic

import numpy as np

from .acquisition import AcquisitionStopped, ConnectedBurstAdapter, ReadinessError, data, field
from .persistence import RunStore, json_value


@dataclass
class RunOutcome:
    status: str
    output_path: str
    native_paths: list[str] = dataclass_field(default_factory=list)
    epoch: dict | None = None
    cleanup_errors: list[str] = dataclass_field(default_factory=list)
    error: str | None = None
    summary: dict = dataclass_field(default_factory=dict)
    data: dict = dataclass_field(default_factory=dict)

    def to_dict(self):
        return json_value(self.__dict__)


class BurstRunner:
    def __init__(self, context, plan, operation, *, store=None, adapter=None, progress=None, cancel=None):
        self.context, self.plan, self.operation = context, plan, operation
        self.settings = plan.settings
        self.cancel_event = cancel if cancel is not None else Event()
        self.callback = progress or (lambda value: None)
        self.store = store
        self.adapter = adapter
        self.started = monotonic()
        self.epoch, self.completed, self.paths = None, [], []
        self.exposure_s = 0.0
        self.pump_intent = False
        self._last_progress = {}
        self._started_once = False

    def cancel(self, reason="User requested stop"):
        self.cancel_event.set()

    def _check(self):
        if self.cancel_event.is_set():
            raise AcquisitionStopped("Acquisition stopped")

    def _progress(self, **values):
        self._check()
        temperature = values.pop("temperature", None)
        if temperature is not None:
            self._validate_temperature(temperature)
            values["temperature_k"] = temperature["temperature_k"]
        values.setdefault("elapsed_s", monotonic() - self.started)
        values.setdefault("remaining_basis", "finite planned observation plus configured preparation/restoration estimates; actual native timing retained")
        values.setdefault("probe_exposure_s", self.exposure_s)
        self._last_progress = values
        self.callback(values)

    def _progress_cleanup(self, stage, message):
        # Abort does not interrupt physical restoration or durable preservation.
        try:
            self.callback({"stage": stage, "message": message, "elapsed_s": monotonic() - self.started})
        except Exception:
            pass

    def _checkpoint(self, status):
        self.store.checkpoint({"status": status, "epoch": self.epoch,
            "pump_intent": self.pump_intent, "completed_blocks": list(self.completed),
            "probe_exposure_s": self.exposure_s, "native_paths": list(self.paths),
            "settings": self.settings.to_dict()})

    def _validate_temperature(self, record):
        value, uncertainty = float(record["temperature_k"]), float(record["uncertainty_k"])
        if record.get("temperature_identity") != self.settings.temperature_identity:
            raise ReadinessError("Temperature identity differs from the accepted cryogenic sample state")
        lo, hi = self.settings.min_temperature_k, self.settings.max_temperature_k
        if (lo is None or hi is None or value - uncertainty < lo or value + uncertainty > hi):
            raise ReadinessError(f"Thermal excursion or insufficient margin: {value:g} ± {uncertainty:g} K outside [{lo}, {hi}] K")

    def _temperature(self):
        record = self.adapter.temperature()
        self._validate_temperature(record)
        return record

    def _metadata(self, kind):
        return {"experiment_id": "single_pump_scan_burst", "mode": self.settings.mode,
            "condition_id": self.settings.condition_id, "operation": self.operation.to_dict(),
            "settings": self.settings.to_dict(), "plan": data(self.plan), "kind": kind}

    def _make_adapter(self):
        if self.adapter is not None:
            return
        if self.operation.hardware:
            cls = ConnectedBurstAdapter
        else:
            from .simulation import SimulatedBurstAdapter
            cls = SimulatedBurstAdapter
        self.adapter = cls(self.context, self.operation, self.plan, cancel=self.cancel_event,
                           progress=self._progress, store=self.store)

    def _validate_review(self, review, baseline):
        if not review or not review.get("accepted"):
            raise ReadinessError("Explicit accepted preliminary review and Start action are required")
        if json_value(review.get("settings")) != json_value(self.settings.to_dict()):
            raise ReadinessError("Review settings changed; reacquire or load compatible preliminary data and review again")
        if not baseline:
            raise ReadinessError("Accepted stationary pre-pump spectra are required")
        preliminary = baseline.get("preliminary", baseline)
        self._compatible_record(preliminary, "preliminary")
        if self.settings.mode == "single":
            self._compatible_record(baseline.get("blank"), "baseline")

    def _compatible_record(self, record, kind):
        if not record or not record.get("complete"):
            raise ReadinessError(f"Complete compatible {kind} record is required")
        metadata = record.get("metadata", {})
        if metadata.get("mode") != self.settings.mode or metadata.get("condition_id") != self.settings.condition_id:
            raise ReadinessError(f"{kind} experiment/mode/condition mismatch")
        if metadata.get("experiment_id") != "single_pump_scan_burst":
            raise ReadinessError(f"{kind} belongs to another experiment")
        if json_value(metadata.get("settings")) != json_value(self.settings.to_dict()):
            raise ReadinessError(f"{kind} settings, sample identity or calibration changed")
        if metadata.get("kind") != kind:
            raise ReadinessError(f"Expected {kind} record, found {metadata.get('kind')}")

    def prepare(self, kind="preliminary"):
        if kind not in ("baseline", "preliminary", "capabilities"):
            raise ValueError("Preparation kind must be baseline, preliminary or capabilities")
        return self._execute(kind)

    def run(self, review, baseline=None, continuation=None):
        return self._execute("measurement", review=review, baseline=baseline, continuation=continuation)

    def _execute(self, kind, *, review=None, baseline=None, continuation=None):
        if self._started_once:
            raise RuntimeError("An operation cannot be repeated; create an explicitly new run")
        self._started_once = True
        result = RunOutcome("failed", str(self.operation.output_path))
        preservation = False
        preservation_failure = None
        restored = {"safe_verified": True, "errors": [], "records": {}}
        scope = self.context.hardware_scope(self.operation) if self.operation.hardware else nullcontext()
        with scope:
            try:
                if self.store is None:
                    self.store = RunStore(self.operation.output_path, self._metadata(kind))
                self._check()
                self._make_adapter()
                if kind != "capabilities":
                    self.plan.require_valid()
                if kind == "measurement":
                    self._validate_review(review, baseline)
                    if self.operation.hardware and not self.plan.ready:
                        raise ReadinessError("; ".join(self.plan.readiness))
                    if self.operation.hardware and continuation is None:
                        from .persistence import assert_unused_sample_state
                        assert_unused_sample_state(self.operation.output_path, self.settings)
                    self.store.save_record("accepted-preliminary-review", review)
                    references = {}
                    for name in ("blank", "preliminary"):
                        record = baseline.get(name)
                        if record:
                            references[name] = {key: record[key] for key in ("output_path", "complete", "metadata", "native_paths") if key in record}
                    self.store.save_record("selected-baselines", references)
                self._progress(stage="configuration", message="Configuring owned instrument services", fraction=0)
                if kind == "capabilities":
                    result.data = self.adapter.inspect_capabilities()
                else:
                    readback = self.adapter.configure(pumped=kind == "measurement" and continuation is None)
                    self.store.save_record("configured-readbacks", readback)
                    self._temperature()
                    if kind == "measurement":
                        self._measurement(continuation, result, baseline)
                        from .processing import analyze_run
                        analysis = analyze_run(self.operation.output_path, baseline_bundle=baseline,
                            cancel_check=self._check, progress=self.callback, store=self.store)
                        result.summary.update(analysis.get("summary", {}))
                        result.data["analysis"] = analysis
                    else:
                        self._preparation(kind, result)
                self._check()
                result.status = "complete"
            except AcquisitionStopped:
                result.status, result.error = "stopped", "Acquisition stopped"
            except Exception as exc:
                result.status, result.error = "incomplete" if self.pump_intent else "failed", str(exc)
                if isinstance(exc, OSError):
                    preservation_failure = str(exc)
            finally:
                self._progress_cleanup("restoration", "Restoring instruments and verifying safe idle")
                if self.adapter is not None:
                    try:
                        restored = self.adapter.restore()
                    except Exception as exc:
                        restored = {"safe_verified": False, "errors": [str(exc)], "records": {}}
                result.cleanup_errors = list(restored.get("errors", []))
                if not restored.get("safe_verified"):
                    result.status = "cleanup_failed"
                result.epoch, result.native_paths = self.epoch, list(self.paths)
                result.summary.update(completed_blocks=list(self.completed), probe_exposure_s=self.exposure_s,
                                      pump_intent=self.pump_intent, right_censored=True,
                                      acquisition_message=result.error or "Observation complete")
                self._progress_cleanup("saving", "Preserving native data, epoch and restoration records")
                if self.store is not None:
                    try:
                        self.store.save_record("restoration", restored)
                        self._checkpoint(result.status)
                        self.store.finalize(result.status, epoch=self.epoch, error=result.error,
                            cleanup_errors=result.cleanup_errors, summary=result.summary, native_paths=self.paths)
                        preservation = preservation_failure is None
                        if preservation_failure:
                            result.cleanup_errors.append("Required native preservation incomplete: " + preservation_failure)
                    except Exception as exc:
                        result.cleanup_errors.append("Preservation failed: " + str(exc))
                        result.status = "preservation_failed" if restored.get("safe_verified") else "cleanup_failed"
                if self.operation.hardware:
                    self.context.ownership.release(self.operation.ownership,
                        safe_verified=bool(restored.get("safe_verified")), preservation_verified=preservation,
                        detail=f"{result.status}: {result.error or ''}; {'; '.join(result.cleanup_errors)}")
        if kind != "measurement":
            return {**result.to_dict(), **json_value(result.data), "metadata": self._metadata(kind),
                    "complete": result.status == "complete"}
        return result

    def _unpumped_block(self):
        from .planner import compile_preliminary
        return compile_preliminary(self.plan)

    def _preparation(self, kind, result):
        from .planner import compile_blank_blocks
        blocks = compile_blank_blocks(self.plan) if kind == "baseline" else (self._unpumped_block(),)
        start = self.adapter.native_now()
        total_scans = 0
        for block in blocks:
            self._check()
            # A complete sequential blank retains the whole declared schedule,
            # including dark/probe-duty history, while every pump channel is OFF.
            if kind == "baseline":
                previous_epoch = self.epoch
                self.epoch = {"pump_time_s": start, "blank_schedule_origin_only": True}
                self._wait_until(block.planned_elapsed_s, len(self.completed))
                self.epoch = previous_epoch
            self.adapter.program_block(block, pump_allowed=False)
            exposure = self._block_exposure(block)
            if self.exposure_s + exposure > self.settings.max_probe_exposure_s:
                raise ReadinessError("Preparation probe exposure budget exhausted")
            captured = self.adapter.capture_block(block, pump_allowed=False)
            self.exposure_s += exposure
            if captured.get("observed_pump_count") != 0:
                raise ReadinessError("Unexpected pump during unpumped preparation")
            native = captured["native"]
            # Each reconstructed chunk carries globally unique scan identities.
            scans = np.asarray(native["scan_index"])
            valid = scans >= 0
            if valid.any():
                scans = scans.copy()
                scans[valid] = scans[valid] - scans[valid].min() + total_scans
                native["scan_index"] = scans
            total_scans += block.scan_count
            self.paths.append(self.store.save_chunk("unpumped-" + block.block_id, native))
            self._validate_spectral_support(native, block.scan_count)
            self._temperature()
            self.completed.append(block.block_id)
            self._checkpoint("unpumped_preparation")
        result.data = {"stationarity_review_required": True, "total_scans": total_scans,
                       "coverage": "Complete sequential unpumped plan with matched spectral, filter and dark/probe-duty schedule" if kind == "baseline" else "Stationary repeated preliminary spectra",
                       "controls_record_ids": list(self.settings.controls_record_ids)}
        if kind == "preliminary":
            result.data["native"] = native

    def _measurement(self, continuation, result, baseline):
        from .processing import PlateauTracker, load_spectral_record, process_block
        tracker = PlateauTracker(self.settings.plateau_band_windows_cm1,
            relative_tolerance=self.settings.plateau_relative_tolerance if self.settings.plateau_enabled else None,
            required_bursts=self.settings.plateau_required_bursts)
        preliminary = baseline.get("preliminary", baseline)
        preliminary_native = preliminary.get("native")
        if preliminary_native is None:
            preliminary_native = load_spectral_record(preliminary["output_path"])
        # The sample preliminary has already spent some of this same state's
        # probe budget. The separate matched-buffer blank is another specimen.
        if preliminary.get("output_path"):
            from .persistence import load_run
            prior = load_run(preliminary["output_path"])
            self.exposure_s = float(prior.get("checkpoint", {}).get("state", {}).get("probe_exposure_s", 0.))
        self.exposure_s += float(self.settings.hardware_evidence.get("sample_prior_probe_pulse_on_s", 0.))
        plateau_reached = False
        matching = self.settings.hardware_evidence.get("operating_configuration", {}).get("detector_matching", {})
        self.store.append_event("detector_matching_rule", {"time_tolerance_s": float(matching.get("time_tolerance_s", 0.)),
            "wavenumber_tolerance_cm1": float(matching.get("wavenumber_tolerance_cm1", 0.)),
            "record_id": matching.get("record_id"), "rule": "nearest supported sample; no interpolation across scan gaps"})
        if continuation:
            if "state" in continuation:
                continuation = continuation["state"]
            if "settings" in continuation and json_value(continuation["settings"]) != json_value(self.settings.to_dict()):
                raise ReadinessError("Continuation plan or sample/calibration settings changed; preserve the incomplete observation")
            if continuation.get("pump_intent") and not continuation.get("epoch"):
                raise ReadinessError("Ambiguous retained pump intent without independently observed epoch; never fire a replacement pump")
            if not continuation.get("epoch") or not continuation["epoch"].get("independently_observed"):
                raise ReadinessError("Continuation needs a retained independently observed pump epoch")
            self.adapter.verify_continuation(continuation)
            self.epoch = deepcopy(continuation["epoch"])
            self.pump_intent = True
            self.completed = list(continuation.get("completed_blocks", ()))
            self.exposure_s = float(continuation.get("probe_exposure_s", 0))
            if self.plan.blocks[0].block_id not in self.completed:
                raise ReadinessError("Interrupted pumped early block cannot be replayed; retain incomplete observation")
            self.store.append_event("explicit_continuation", continuation)
            if continuation.get("source_output_path"):
                self.store.save_record("continuation-source", {"source_output_path": continuation["source_output_path"],
                    "epoch": self.epoch, "completed_blocks": self.completed, "state_evidence": continuation.get("state_evidence")})
                from .processing import prime_tracker
                prime_tracker(tracker, continuation["source_output_path"], cancel=self._check)
        for index, block in enumerate(self.plan.blocks):
            if block.block_id in self.completed:
                continue
            if plateau_reached and block.kind != "final":
                self.store.append_event("prospective_plateau_skipped_burst", {"block_id": block.block_id})
                continue
            self._check()
            pumped = bool(block.pump_enabled)
            if pumped and (self.pump_intent or self.epoch is not None):
                raise ReadinessError("A second or replacement pump is prohibited")
            self.adapter.idle()
            self._temperature()
            if self.epoch is not None and not plateau_reached:
                now = self._wait_until(block.planned_elapsed_s, index)
                if now - float(self.epoch["pump_time_s"]) > self.settings.observation_limit_s and block.kind != "final":
                    self.store.append_event("missed_burst", {"block_id": block.block_id,
                        "reason": "declared observation limit already passed", "observed_native_time_s": now})
                    continue
            duration = self._block_exposure(block)
            # Conservative exposure bound includes all armed block time.
            if self.exposure_s + duration > self.settings.max_probe_exposure_s:
                raise ReadinessError("Prospective probe exposure budget exhausted before next block")
            self._progress(stage="tuning", message=f"Preparing {block.block_id}", burst_index=index,
                           scan_count=sum(b.scan_count for b in self.plan.blocks if b.block_id in self.completed), fraction=index / len(self.plan.blocks))
            self.adapter.program_block(block, pump_allowed=pumped)
            self._check()
            def intent():
                if self.pump_intent:
                    raise ReadinessError("Pump intent is already durable; a replacement pump is prohibited")
                if self.operation.hardware:
                    from .persistence import assert_unused_sample_state
                    assert_unused_sample_state(self.operation.output_path, self.settings)
                self.store.append_event("pump_intent", {"block_id": block.block_id, "automatic_retry_allowed": False})
                self.pump_intent = True
                self._checkpoint("pump_intent_committed")
            captured = self.adapter.capture_block(block, pump_allowed=pumped, before_fire=intent if pumped else None)
            native = captured["native"]
            if pumped:
                epoch = captured.get("epoch")
                if not epoch or not epoch.get("independently_observed") or epoch.get("optical_event_count") != 1:
                    self.paths.append(self.store.save_chunk("spectral-" + block.block_id, native))
                    raise ReadinessError("Optical pump epoch unresolved; retain incomplete record and never repeat")
                self.epoch = epoch
                self.store.append_event("pump_epoch_observed", epoch)
                self._checkpoint("pump_epoch_committed")
            elif captured.get("observed_pump_count"):
                self.paths.append(self.store.save_chunk("spectral-" + block.block_id, native))
                raise ReadinessError("Unexpected additional pump observed in later block")
            if self.epoch.get("pump_timestamp_ticks") is not None:
                native["pump_timestamp_ticks"] = np.asarray(self.epoch["pump_timestamp_ticks"], dtype=np.uint64)
                native["pump_optical_offset_s"] = np.asarray(self.epoch.get("optical_offset_s", 0.))
            # Planned scan identity survives omitted bursts after a plateau;
            # the final spectrum still matches the complete sequential blank.
            scan_offset = sum(b.scan_count for b in self.plan.blocks[:index])
            scans = np.asarray(native["scan_index"])
            valid = scans >= 0
            if valid.any():
                scans = scans.copy()
                scans[valid] = scans[valid] - scans[valid].min() + scan_offset
                native["scan_index"] = scans
            self.paths.append(self.store.save_chunk("spectral-" + block.block_id, native))
            self.exposure_s += duration
            self.store.append_event("probe_exposure", {"block_id": block.block_id,
                "probe_pulse_on_s": self.exposure_s, "block_probe_pulse_on_s": duration,
                "native_time_s": captured.get("end_native_time_s"), "basis": "conservative block enabled duration times selected pulse duty"})
            self.completed.append(block.block_id)
            self.store.append_event("block_completed", {"block_id": block.block_id,
                "planned_elapsed_s": block.planned_elapsed_s, "observed_scan_count": captured["observed_scan_count"],
                "end_native_time_s": captured.get("end_native_time_s")})
            self._temperature()
            self._checkpoint("observing")
            self._progress(stage="analysis", message=f"Analyzing retained {block.block_id}")
            blank_native = None
            if self.settings.mode == "single":
                blank_native = load_spectral_record(baseline["blank"]["output_path"], block_id="blank-" + block.block_id)
            processed = process_block(native, preliminary_native, mode=self.settings.mode,
                pump_time_s=self.epoch["pump_time_s"], blank=blank_native, cancel=self._check,
                baseline_blank=load_spectral_record(baseline["blank"]["output_path"], block_id="blank-" + self.plan.blocks[0].block_id) if self.settings.mode == "single" else None,
                time_tolerance_s=float(matching.get("time_tolerance_s", 0.)),
                wavenumber_tolerance_cm1=float(matching.get("wavenumber_tolerance_cm1", 0.)))
            processed_path = self.store.save_chunk("processed-" + block.block_id,
                {key: value for key, value in processed.items() if isinstance(value, np.ndarray) or np.isscalar(value)})
            self._validate_spectral_support(native, block.scan_count)
            if not np.asarray(processed["valid"]).any():
                raise ReadinessError("No valid matched baseline/reference spectral support; native and rejected derived records retained")
            assessment = tracker.update(processed, block.block_id)
            self.store.append_event("band_plateau_assessment", assessment)
            if self.settings.plateau_enabled and assessment["reached"]:
                plateau_reached = True
                self.store.append_event("prospective_plateau_reached", {"block_id": block.block_id,
                    "final_state_spectrum_required": True, "criterion": assessment})
            result.summary.update(plateau=assessment, processed_path=processed_path)
            # Only a small latest preview is retained in the UI; full native blocks
            # have already been flushed independently to disk.
            result.data = {"latest_native": native, "latest_processed": processed,
                           "processed_path": processed_path, "native_path": self.paths[-1]}
        result.summary["termination"] = "prospective_plateau_with_final_spectrum" if plateau_reached else "declared_observation_limit"

    def _validate_spectral_support(self, native, expected_scans):
        from .processing import detector_ratio, Quality
        matching = self.settings.hardware_evidence.get("operating_configuration", {}).get("detector_matching", {})
        checked = detector_ratio(native, mode=self.settings.mode,
            time_tolerance_s=float(matching.get("time_tolerance_s", 0.)),
            wavenumber_tolerance_cm1=float(matching.get("wavenumber_tolerance_cm1", 0.)))
        flags = checked["quality_flags"]
        if np.any(flags & (Quality.CLIPPED | Quality.UNLOCKED)):
            raise ReadinessError("Detector clipping or reference unlock; native records retained")
        scans = np.asarray(native["scan_index"])
        observed = np.unique(scans[scans >= 0])
        if len(observed) != expected_scans or any(np.count_nonzero((scans == scan) & (flags == 0)) < 2 for scan in observed):
            raise ReadinessError("Missing sample/reference spectral support for a declared scan; partial native records retained")

    def _block_exposure(self, block):
        selected = {key: row["selected"] for key, row in self.plan.selected_values.items()}
        duty = selected.get("probe_rate_hz", self.settings.probe_rate_hz) * selected.get("probe_pulse_width_s", self.settings.probe_pulse_width_s)
        return float(block.duration_s) * duty

    def _wait_until(self, target, index):
        self._checkpoint("dark_wait")
        if getattr(self.adapter, "virtual_time", False):
            self.adapter.wait_target = float(self.epoch["pump_time_s"]) + float(target)
        last_record = -float("inf")
        while True:
            self._check()
            observed = self.adapter.native_now()
            remaining = float(target) - (observed - float(self.epoch["pump_time_s"]))
            if remaining <= 1e-12:
                self.store.append_event("burst_ready", {"burst_index": index, "native_now_s": observed,
                    "planned_elapsed_s": target, "late_by_s": max(0., -remaining),
                    "time_basis": "native HF2LI observations; host scheduling only prepares future block"})
                return observed
            if observed - last_record >= self.settings.temperature_check_interval_s:
                record = self._temperature()
                self._progress(stage="recovery_wait", message=f"Dark wait; next planned burst in {remaining:.6g} s",
                    next_burst_s=remaining, remaining_s=remaining, burst_index=index, temperature=record)
                self.store.append_event("dark_wait_progress", {"native_time_s": observed, "next_burst_s": remaining})
                last_record = observed
            # Abort-responsive host pacing never determines a precise edge.
            if not getattr(self.adapter, "virtual_time", False):
                self.cancel_event.wait(min(.1, remaining))
