"""Durable one-pump lifecycle shared as pure implementation by isolated tabs."""
from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
from dataclasses import dataclass, field as dataclass_field, replace
from pathlib import Path
from threading import Event
from time import monotonic

import numpy as np

from .acquisition import AcquisitionStopped, ConnectedBurstAdapter, ReadinessError, acquisition_identity, data, field
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
        result = json_value(self.__dict__)
        result["actual_settings"] = result["summary"].get("actual_settings")
        result["capabilities"] = result["data"].get("capabilities")
        return result


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
        self._prior_exposure_s = 0.0
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
        if temperature and temperature.get("temperature_k") is not None:
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

    def _temperature(self):
        return self.adapter.temperature()

    def _metadata(self, kind):
        return {"experiment_id": "single_pump_scan_burst", "mode": self.settings.mode,
            "condition_id": self.settings.condition_id, "operation": self.operation.to_dict(),
            "settings": self.settings.to_dict(), "actual_settings": self.settings.to_dict(), "plan": data(self.plan), "kind": kind}

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

    def _compatible_record(self, record, kind):
        if not record:
            return
        metadata = record.get("metadata", {})
        if metadata.get("mode", self.settings.mode) != self.settings.mode:
            raise ReadinessError(f"{kind} detector mode does not match")
        if metadata.get("experiment_id", "single_pump_scan_burst") != "single_pump_scan_burst":
            raise ReadinessError(f"{kind} belongs to another experiment")
        selected = metadata.get("actual_settings", metadata.get("settings"))
        if selected:
            previous, current = acquisition_identity(selected), acquisition_identity(self.settings)
            mismatches = [name for name in current if previous.get(name) is not None and current[name] is not None and previous[name] != current[name]]
            if mismatches:
                raise ReadinessError(f"{kind} measured settings differ: {', '.join(mismatches)}")

    def prepare(self, kind="preliminary"):
        if kind not in ("baseline", "preliminary", "capabilities"):
            raise ValueError("Preparation kind must be baseline, preliminary or capabilities")
        return self._execute(kind)

    def run(self, baseline=None, continuation=None):
        return self._execute("measurement", baseline=baseline, continuation=continuation)

    def _execute(self, kind, *, baseline=None, continuation=None):
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
                if kind == "measurement":
                    baseline = baseline or {}
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
                    self.plan = self.adapter.plan
                    self.settings = self.plan.settings
                    self.plan.require_valid()
                    self.store.save_record("configured-readbacks", readback)
                    self.store.save_record("selected-acquisition-plan", {"settings": self.settings.to_dict(), "plan": data(self.plan)})
                    self.store.save_record("actual-settings", {"settings": self.settings.to_dict(), "capabilities": data(self.plan.capabilities)})
                    result.summary["actual_settings"] = self.settings.to_dict()
                    result.data["capabilities"] = readback.get("capabilities", data(self.plan.capabilities))
                    self._temperature()
                    if kind == "measurement":
                        self._compatible_record(baseline.get("preliminary", baseline if baseline.get("native") else None), "preliminary")
                        try:
                            self._compatible_record(baseline.get("blank"), "baseline")
                        except ReadinessError as exc:
                            self.store.append_event("blank_comparison_unavailable", {"reason": str(exc), "relative_signals_available": True})
                            baseline = {key: value for key, value in baseline.items() if key != "blank"}
                        self._measurement(continuation, result, baseline)
                        from .processing import analyze_run
                        try:
                            analysis = analyze_run(self.operation.output_path, baseline_bundle=baseline,
                                cancel_check=self._check, progress=self.callback, store=self.store)
                            result.summary.update(analysis.get("summary", {}))
                            result.data["analysis"] = analysis
                        except ValueError as exc:
                            self.store.append_event("analysis_unavailable", {"reason": str(exc), "native_data_retained": True})
                            result.summary["analysis_unavailable"] = str(exc)
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
                if self.adapter is not None and hasattr(self.adapter, "observed_probe_pulse_on_s"):
                    self.exposure_s = self._prior_exposure_s + self.adapter.observed_probe_pulse_on_s
                result.summary.update(completed_blocks=list(self.completed), probe_exposure_s=self.exposure_s,
                                      pump_intent=self.pump_intent, right_censored=True,
                                      acquisition_message=result.error or "Observation complete")
                result.data.setdefault("capabilities", data(self.plan.capabilities))
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
        from .planner import compile_preliminary
        blocks = (compile_preliminary(self.plan, kind=kind),)
        total_scans = 0
        for block in blocks:
            self._check()
            self.adapter.program_block(block, pump_allowed=False)
            exposure = self._block_exposure(block)
            captured = self.adapter.capture_block(block, pump_allowed=False)
            exposure = float(captured.get("probe_pulse_on_upper_bound_s", exposure))
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
        result.data.update(total_scans=total_scans, coverage="Repeated unpumped spectral trajectory", native=native)

    def _measurement(self, continuation, result, baseline):
        from .processing import PlateauTracker, load_spectral_record, process_block
        tracker = PlateauTracker(self.settings.plateau_band_windows_cm1 if self.settings.plateau_enabled else (),
            relative_tolerance=self.settings.plateau_relative_tolerance if self.settings.plateau_enabled else None,
            required_bursts=self.settings.plateau_required_bursts if self.settings.plateau_enabled else 3)
        preliminary = baseline.get("preliminary", baseline if baseline.get("native") else {}) or {}
        preliminary_native = preliminary.get("native")
        if preliminary_native is None and preliminary.get("output_path"):
            preliminary_native = load_spectral_record(preliminary["output_path"])
        # The sample preliminary has already spent some of this same state's
        # probe budget. The separate matched-buffer blank is another specimen.
        if preliminary.get("output_path"):
            from .persistence import load_run
            prior = load_run(preliminary["output_path"])
            self.exposure_s = float(prior.get("checkpoint", {}).get("state", {}).get("probe_exposure_s", 0.))
            self._prior_exposure_s = self.exposure_s
        plateau_reached = False
        matching = {"time_tolerance_s": field(self.settings, "detector_matching_time_tolerance_s", 0.) or 0.,
                    "wavenumber_tolerance_cm1": field(self.settings, "wavenumber_matching_tolerance_cm1", 0.) or 0.}
        self.store.append_event("detector_matching_rule", {"time_tolerance_s": float(matching.get("time_tolerance_s", 0.)),
            "wavenumber_tolerance_cm1": float(matching.get("wavenumber_tolerance_cm1", 0.)),
            "record_id": matching.get("record_id"), "rule": "nearest supported sample; no interpolation across scan gaps"})
        if continuation:
            if "state" in continuation:
                continuation = continuation["state"]
            if "settings" in continuation and acquisition_identity(continuation["settings"]) != acquisition_identity(self.settings):
                raise ReadinessError("Continuation recorder or spectral settings changed; preserve the incomplete observation")
            if continuation.get("pump_intent") and not continuation.get("epoch"):
                raise ReadinessError("Ambiguous retained pump intent without an observed epoch; never fire a replacement pump")
            if not continuation.get("epoch") or not (continuation["epoch"].get("independently_observed") or continuation["epoch"].get("electrically_observed")):
                raise ReadinessError("Continuation needs a retained observed pump clock")
            self.adapter.verify_continuation(continuation)
            self.epoch = deepcopy(continuation["epoch"])
            self.pump_intent = True
            self.completed = list(continuation.get("completed_blocks", ()))
            self.exposure_s = float(continuation.get("probe_exposure_s", 0))
            self._prior_exposure_s = self.exposure_s
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
            self._progress(stage="tuning", message=f"Preparing {block.block_id}", burst_index=index,
                           scan_count=sum(b.scan_count for b in self.plan.blocks if b.block_id in self.completed), fraction=index / len(self.plan.blocks))
            self.adapter.program_block(block, pump_allowed=pumped)
            self._check()
            def intent():
                if self.pump_intent:
                    raise ReadinessError("Pump intent is already durable; a replacement pump is prohibited")
                self.store.append_event("pump_intent", {"block_id": block.block_id, "automatic_retry_allowed": False})
                self.pump_intent = True
                self._checkpoint("pump_intent_committed")
            captured = self.adapter.capture_block(block, pump_allowed=pumped, before_fire=intent if pumped else None)
            duration = float(captured.get("probe_pulse_on_upper_bound_s", duration))
            native = captured["native"]
            if pumped:
                epoch = captured.get("epoch")
                if not epoch or not (epoch.get("electrically_observed") or epoch.get("independently_observed")):
                    self.paths.append(self.store.save_chunk("spectral-" + block.block_id, native))
                    raise ReadinessError("No observed pump clock; retain native data and never repeat the pump automatically")
                self.epoch = epoch
                self.store.append_event("pump_epoch_observed", epoch)
                self._checkpoint("pump_epoch_committed")
            elif captured.get("observed_pump_count"):
                self.paths.append(self.store.save_chunk("spectral-" + block.block_id, native))
                raise ReadinessError("Unexpected additional pump observed in later block")
            if self.epoch.get("pump_timestamp_ticks") is not None:
                native["pump_timestamp_ticks"] = np.asarray(self.epoch["pump_timestamp_ticks"], dtype=np.uint64)
                native["pump_optical_offset_s"] = np.asarray(self.epoch.get("optical_offset_s", 0.))
                native["time_reference"] = np.asarray(self.epoch.get("time_reference", "electrical_trigger"))
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
            self._validate_spectral_support(native, block.scan_count)
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
            result.data.update(latest_native=native, native_path=self.paths[-1])
            if preliminary_native is None:
                self.store.append_event("relative_analysis_unavailable", {"block_id": block.block_id,
                    "reason": "No sample baseline supplied", "native_data_retained": True})
                continue
            self._progress(stage="analysis", message=f"Analyzing retained {block.block_id}")
            blank_native = None
            if self.settings.mode == "single" and baseline.get("blank"):
                blank_native = baseline["blank"].get("native")
                if blank_native is None and baseline["blank"].get("output_path"):
                    blank_native = load_spectral_record(baseline["blank"]["output_path"])
            processed = process_block(native, preliminary_native, mode=self.settings.mode,
                pump_time_s=self.epoch["pump_time_s"], blank=blank_native, cancel=self._check,
                baseline_blank=blank_native,
                time_tolerance_s=float(matching.get("time_tolerance_s", 0.)),
                wavenumber_tolerance_cm1=float(matching.get("wavenumber_tolerance_cm1", 0.)))
            processed_path = self.store.save_chunk("processed-" + block.block_id,
                {key: value for key, value in processed.items() if isinstance(value, np.ndarray) or np.isscalar(value)})
            if not np.asarray(processed["valid"]).any():
                self.store.append_event("relative_analysis_unavailable", {"block_id": block.block_id,
                    "reason": "No valid matched comparison support", "native_data_retained": True})
            assessment = tracker.update(processed, block.block_id)
            self.store.append_event("band_plateau_assessment", assessment)
            if self.settings.plateau_enabled and assessment["reached"]:
                plateau_reached = True
                self.store.append_event("prospective_plateau_reached", {"block_id": block.block_id,
                    "final_state_spectrum_required": True, "criterion": assessment})
            result.summary.update(plateau=assessment, processed_path=processed_path)
            # Only a small latest preview is retained in the UI; full native blocks
            # have already been flushed independently to disk.
            result.data.update(latest_native=native, latest_processed=processed,
                               processed_path=processed_path, native_path=self.paths[-1])
        result.summary["termination"] = "prospective_plateau_with_final_spectrum" if plateau_reached else "declared_observation_limit"

    def _validate_spectral_support(self, native, expected_scans):
        from .processing import detector_ratio, Quality
        matching = {"time_tolerance_s": field(self.settings, "detector_matching_time_tolerance_s", 0.) or 0.,
                    "wavenumber_tolerance_cm1": field(self.settings, "wavenumber_matching_tolerance_cm1", 0.) or 0.}
        checked = detector_ratio(native, mode=self.settings.mode,
            time_tolerance_s=float(matching.get("time_tolerance_s", 0.)),
            wavenumber_tolerance_cm1=float(matching.get("wavenumber_tolerance_cm1", 0.)))
        flags = checked["quality_flags"]
        if np.any(flags & (Quality.CLIPPED | Quality.UNLOCKED)):
            raise ReadinessError("Detector clipping or reference unlock; native records retained")
        scans = np.asarray(native["scan_index"])
        observed = np.unique(scans[scans >= 0])
        if len(observed) != expected_scans or any(np.count_nonzero((scans == scan) & (flags == 0)) < 2 for scan in observed):
            self.store.append_event("missing_spectral_support", {"observed_scans": len(observed), "expected_scans": expected_scans,
                "message": "Raw acquisition retained; some spectral or reference support is unavailable"})

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
            if observed - last_record >= 1.:
                record = self._temperature()
                self._progress(stage="recovery_wait", message=f"Dark wait; next planned burst in {remaining:.6g} s",
                    next_burst_s=remaining, remaining_s=remaining, burst_index=index, temperature=record)
                self.store.append_event("dark_wait_progress", {"native_time_s": observed, "next_burst_s": remaining})
                last_record = observed
            # Abort-responsive host pacing never determines a precise edge.
            if not getattr(self.adapter, "virtual_time", False):
                self.cancel_event.wait(min(.1, remaining))
