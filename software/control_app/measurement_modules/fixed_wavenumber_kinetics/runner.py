"""Finite fixed-point workflow with durable chunks and verified owned cleanup."""
from __future__ import annotations

from contextlib import nullcontext
from collections import deque
from pathlib import Path
import time

import numpy as np

from .adapters import AcquisitionStopped, InstalledDevices, check_cancel, mapping


class Moments:
    """Streaming sufficient statistics; neither long traces nor clocks are rebased."""
    def __init__(self):
        self.n = 0
        self.origin = None
        self.st = self.stt = self.sy = self.syy = self.sty = 0.
        self.first = self.last = None

    def add(self, t, values, clock):
        t, values = np.asarray(t), np.asarray(values, dtype=float)
        valid = np.isfinite(values)
        t, values = t[valid], values[valid]
        if not len(t):
            return
        if self.origin is None:
            self.origin = int(t[0])
            self.first = self.origin
        self.last = int(t[-1])
        dt = (t.astype(np.int64)-self.origin).astype(float) / clock
        self.n += len(values)
        self.st += float(dt.sum()); self.stt += float(dt @ dt)
        self.sy += float(values.sum()); self.syy += float(values @ values)
        self.sty += float(dt @ values)

    def summary(self, clock, drift_limit=.01, cv_limit=.05):
        if self.n < 3:
            return {"count": self.n, "stationary": False, "reason": "fewer than three valid observations"}
        mean = self.sy/self.n
        var = max(0., (self.syy-self.sy*self.sy/self.n)/(self.n-1))
        denom = self.stt-self.st*self.st/self.n
        slope = (self.sty-self.st*self.sy/self.n)/denom if denom > 0 else float("inf")
        duration = (self.last-self.first)/clock
        drift = abs(slope*duration)/max(abs(mean), 1e-30)
        cv = np.sqrt(var)/max(abs(mean), 1e-30)
        return {"count": self.n, "mean": mean, "std": float(np.sqrt(var)), "slope_per_s": slope,
                "drift_fraction": drift, "cv": float(cv), "duration_s": duration,
                "stationary": bool(mean > 0 and drift <= drift_limit and cv <= cv_limit)}


def normalized_observations(chunk, mode):
    sample = chunk.get("sample", {})
    ts = np.asarray(sample.get("timestamp", []))
    x = np.asarray(sample.get("x", []), dtype=float)
    y = np.asarray(sample.get("y", np.zeros(len(x))), dtype=float)
    if len(ts) != len(x) or len(x) != len(y):
        raise RuntimeError("Native sample timestamps/x/y lengths differ")
    amplitude = np.hypot(x, y)
    valid = np.isfinite(amplitude) & (amplitude > 0)
    for key in ("clipped", "unlocked"):
        if key in sample:
            valid &= ~np.asarray(sample[key], dtype=bool)
    if mode == "dual":
        ref = chunk.get("reference", {})
        rt = np.asarray(ref.get("timestamp", []))
        rx = np.asarray(ref.get("x", []), dtype=float)
        ry = np.asarray(ref.get("y", np.zeros(len(rx))), dtype=float)
        if len(rt) != len(rx) or len(rx) != len(ry):
            raise RuntimeError("Native reference timestamps/x/y lengths differ")
        _, si, ri = np.intersect1d(ts, rt, return_indices=True)
        rr = np.hypot(rx, ry)
        supported = valid[si] & np.isfinite(rr[ri]) & (rr[ri] > 0)
        for key in ("clipped", "unlocked"):
            if key in ref:
                supported &= ~np.asarray(ref[key], dtype=bool)[ri]
        return ts[si][supported], (amplitude[si]/np.where(rr[ri] > 0, rr[ri], np.nan))[supported]
    return ts[valid], amplitude[valid]


class Runner:
    def __init__(self, context, *, device_factory=None, history_path=None):
        self.context = context
        self.device_factory = device_factory
        self.history_path = history_path

    def run(self, operation, plan, *, kind="measurement", cancel=None,
            progress=None, blank=None, preliminary=None):
        from .persistence import NativeChunkWriter, save_run
        from .processing import analyze_run, time_from_ticks
        progress = progress or (lambda event: None)
        check = lambda: check_cancel(cancel)
        started = time.monotonic()
        plan = mapping(plan)
        settings = mapping(plan["settings"])
        resolved = dict(plan["resolved"])
        directory = Path(operation.output_path)
        record = {"experiment_id": "fixed_wavenumber_kinetics", "schema_version": 1,
            "mode": self.context.mode, "kind": kind, "run_id": operation.run_id,
            "plan_id": operation.plan_id, "started_utc": operation.started_utc,
            "condition_id": settings["condition_id"], "sample_id": settings["sample_id"],
            "condition_profile": settings["condition_profile"], "settings": settings,
            "plan": plan, "run_directory": str(directory), "native_chunks": [], "events": [],
            "status": "running", "quality_flags": [], "simulation": not operation.hardware,
            "acquisition_response": resolved.get("acquisition_response", {}),
            "background_balance": resolved.get("background_balance") or {},
            "clock_epoch_policy": "Native uint timestamps retained exactly; pump epoch is first measured electrical sync; no optical equivalence implied"}
        record["analysis_inputs"] = {}
        for name, parent in (("blank", blank), ("preliminary", preliminary)):
            if parent is None:
                continue
            reference = {key: parent.get(key) for key in ("run_id", "experiment_id", "mode", "condition_id", "schema_version")}
            if parent.get("run_directory"):
                parent_directory = Path(parent["run_directory"])
                parent_file = parent_directory / "run.json"
                if not parent_file.exists() and (parent_directory / "native_run.json").exists():
                    parent_file = parent_directory / "native_run.json"
                reference["native_path"] = str(parent_file.resolve())
            record["analysis_inputs"][name] = reference
        device = None
        writer = None
        preservation = False
        cleanup = {"safe_verified": True, "errors": [], "actions": []}
        history = None
        def emit(event):
            event.setdefault("elapsed_s", time.monotonic()-started)
            event.setdefault("basis", "Planned acquisition plus measured settling, device upload, restoration and processing")
            try:
                progress(event)
            except Exception as exc:
                # A GUI callback must never bypass physical cleanup/preservation.
                record.setdefault("presentation_errors", []).append(str(exc))
        scope = self.context.hardware_scope(operation) if operation.hardware else nullcontext()
        with scope:
            try:
                # Create retention before any device or pump work, and never overwrite a run.
                writer = NativeChunkWriter(directory)
                check()
                if kind not in {"blank", "preliminary", "measurement"}:
                    raise ValueError("Unknown acquisition kind")
                if not plan.get("ready", False):
                    raise RuntimeError("Plan readiness unresolved: " + "; ".join(map(str, plan.get("readiness_items", []))))
                if settings["mode"] != self.context.mode:
                    raise ValueError("Plan detector mode mismatch")
                if operation.hardware and resolved.get("qualification_kind") == "simulation":
                    raise RuntimeError("Synthetic operating profile cannot authorize connected devices")
                if kind == "measurement" and settings.get("pump_enabled", True) and (operation.hardware or settings["condition_profile"].startswith("cryo")):
                    from .state_history import StateHistory
                    if operation.hardware:
                        self.context.ownership.assert_owner(operation.ownership)
                    history_path = self.history_path
                    if not operation.hardware and history_path is None:
                        history_path = Path(operation.save_root) / "measurements" / "fixed_wavenumber_kinetics" / "simulation_state_history.jsonl"
                    history = StateHistory(history_path)
                    record["state_history_check"] = history.check(settings, resolved)
                if self.device_factory:
                    device = self.device_factory(self.context, operation)
                elif operation.hardware:
                    device = InstalledDevices(self.context, operation)
                else:
                    from .simulation import SimulatedDevices
                    device = SimulatedDevices(self.context, operation)
                emit({"stage": "configuration", "message": "Connecting operation-owned devices"})
                device.connect(check)
                device.configure(resolved, check)
                record["readbacks"] = device.readbacks
                record["initial_states"] = device.before
                blocks = list(plan["blocks"])
                delivered = 0
                last_pump = None
                previous_block_last_tick = None
                retained_bytes = 0
                for block_index, raw_block in enumerate(blocks):
                    block = mapping(raw_block)
                    check()
                    pumped = kind == "measurement" and settings.get("pump_enabled", True) and int(block.get("event_count", 1)) > 0
                    if pumped and delivered >= int(settings["event_budget"]):
                        raise RuntimeError("Finite pump budget exhausted; no automatic retry")
                    if pumped and delivered and settings["condition_profile"].startswith("cryo"):
                        raise RuntimeError("Cryogenic state requires a new explicitly established equivalent-state operation")
                    if pumped and operation.hardware:
                        health = device.read_health()
                        record.setdefault("health_readbacks", []).append(health)
                        if health.get("read_errors") or health.get("reference_locked") is not True or health.get("clock_locked") is not True or health.get("external_clock_selected") is not True or health.get("overload") is not False or health.get("data_loss"):
                            raise RuntimeError("HF2LI live lock/overload readiness did not pass")
                    event = {"position_index": block["position_index"], "event_index": block_index,
                        "repetition_index": block.get("repetition_index", 0),
                        "position_cm1": block.get("position_cm1", block.get("wavenumber_cm1")),
                        "expected_pump_count": int(pumped), "pump_timestamps": [],
                        "original_pump_timestamp": None, "clockbase_hz": device.clockbase_hz,
                        "optical_time_zero": "unresolved unless independently qualified timing data supplied",
                        "position_label": settings["positions"][block["position_index"]].get("label", "band"),
                        "dose": resolved.get("pump_dose"), "dose_units": resolved.get("pump_dose_units"),
                        "equivalent_state": not pumped or delivered == 0 or bool(record["events"][-1].get("reset", {}).get("accepted")),
                        "reset_evidence": record["events"][-1].get("reset") if record["events"] else None}
                    record["events"].append(event)
                    program = mapping(block["timing"]) if block.get("timing") else None
                    if pumped:
                        if not program or program.get("expected_pump_count") != 1:
                            raise RuntimeError("Each reset-gated block must compile exactly one finite event")
                        event["timing_upload"] = device.upload(program, check, emit)
                    emit({"stage": "tuning/settling", "message": f"Tuning {event['position_cm1']:g} cm^-1", "completed": block_index, "total": len(blocks)})
                    event["tuning"] = device.tune(event["position_cm1"], settings, check, emit)
                    device.start_stream()
                    baseline = Moments()
                    native_baselines = {role: Moments() for role in (("sample", "reference") if self.context.mode == "dual" else ("sample",))}
                    reset_window_s = float(settings.get("reset_observation_s") or settings["pre_observation_s"])
                    tail_chunks = deque()
                    last_ticks, previous_dio = {}, 0
                    chunk_s = min(float(settings["chunk_duration_s"]), 1.)
                    def acquire(duration, phase, stats=None):
                        nonlocal previous_dio, retained_bytes
                        elapsed = 0.
                        empty = 0
                        phase_starts = dict(last_ticks)
                        polls = 0
                        final_summary = None
                        while elapsed < duration-1e-12:
                            check()
                            span = min(chunk_s, duration-elapsed)
                            emit({"stage": "retrieval", "message": "Retrieving native device-clock observations",
                                "completed": elapsed, "total": duration})
                            chunk = device.read(span)
                            chunk["position_index"] = event["position_index"]
                            chunk["event_index"] = event["event_index"]
                            chunk["kind"] = phase
                            native_size = sum(v.nbytes for stream in chunk.values() if isinstance(stream, dict)
                                for v in stream.values() if isinstance(v, np.ndarray))
                            # Write before validation: malformed/rejected records are evidence too.
                            try:
                                ref = writer.append(chunk, position_index=event["position_index"],
                                    event_index=event["event_index"], kind=phase)
                            except Exception as exc:
                                record["native_preservation_error"] = str(exc)
                                raise
                            record["native_chunks"].append(ref)
                            retained_bytes += native_size
                            if native_size > settings["memory_limit_mb"]*1024**2:
                                raise RuntimeError("Native poll exceeds planned memory budget; obtained values preserved")
                            polls += 1
                            if retained_bytes > settings["storage_limit_mb"]*1024**2:
                                raise RuntimeError("Native retained bytes exceed authorized storage budget")
                            for role in ("sample", "reference"):
                                for flag in ("clipped", "unlocked"):
                                    if np.any(chunk.get(role, {}).get(flag, False)):
                                        raise RuntimeError(f"{phase}: {role} {flag} observations; native chunk preserved")
                            for role in ("sample", "reference", "timing"):
                                stream = chunk.get(role, {})
                                ticks = np.asarray(stream.get("timestamp", []))
                                if len(ticks):
                                    if role == "sample":
                                        if "first_native_timestamp" not in event:
                                            event["first_native_timestamp"] = int(ticks[0])
                                            event["native_timestamp_channel"] = "sample"
                                            if previous_block_last_tick is not None:
                                                gap_s = (int(ticks[0])-previous_block_last_tick)/device.clockbase_hz
                                                event["inter_block_dead_time_s"] = max(0., gap_s-1./resolved["sample"]["rate_sps"])
                                                event["inter_block_dead_time_basis"] = "Observed sample-clock gap beyond one selected sample interval; native missing support is not imputed"
                                            else:
                                                event["inter_block_dead_time_s"] = None
                                        event["last_native_timestamp"] = int(ticks[-1])
                                    if np.any(ticks[1:] <= ticks[:-1]) or (role in last_ticks and int(ticks[0]) <= last_ticks[role]):
                                        raise RuntimeError(f"{role} timestamp overlap/reversal; native chunk preserved")
                                    rate = resolved.get(role, {}).get("rate_sps", resolved["timing_rate_sps"])
                                    gaps = np.flatnonzero(np.diff(ticks.astype(np.int64)) > 1.6*device.clockbase_hz/rate)
                                    if len(gaps):
                                        record["quality_flags"].append(f"{role} {len(gaps)} internal gaps in chunk {len(record['native_chunks'])}")
                                    if role in last_ticks and (int(ticks[0])-last_ticks[role]) > 1.6*device.clockbase_hz/rate:
                                        record["quality_flags"].append(f"{role} data gap before chunk {len(record['native_chunks'])}")
                                    last_ticks[role] = int(ticks[-1])
                                    if role not in phase_starts:
                                        phase_starts[role] = int(ticks[0])-int(round(device.clockbase_hz/rate))
                            timing = chunk.get("timing", {})
                            t = np.asarray(timing.get("timestamp", []))
                            dio = np.asarray(timing.get("dio", []), dtype=np.uint64)
                            if len(t) != len(dio):
                                raise RuntimeError("Missing or malformed native electrical timing stream")
                            bit = np.uint64(1 << int(resolved["pump_marker_bit"]))
                            for tick, word in zip(t, dio):
                                current = int(bool(word & bit))
                                if current and not previous_dio:
                                    event["pump_timestamps"].append(int(tick))
                                    if event["original_pump_timestamp"] is None:
                                        event["original_pump_timestamp"] = int(tick)
                                previous_dio = current
                            if phase == "baseline" and event["pump_timestamps"]:
                                raise RuntimeError("Unexpected measured pump sync during unpumped baseline")
                            if len(event["pump_timestamps"]) > event["expected_pump_count"]:
                                raise RuntimeError("Observed electrical pump count exceeds authorized finite count; no retry")
                            health = chunk.get("health")
                            if health and (not health.get("reference_locked") or not health.get("clock_locked") or health.get("overload") or health.get("data_loss")):
                                raise RuntimeError("HF2LI live lock, overload or loss fault; native chunk preserved")
                            ts, values = normalized_observations(chunk, self.context.mode)
                            if stats is not None:
                                for role, moments in native_baselines.items():
                                    stream = chunk.get(role, {})
                                    rt = np.asarray(stream.get("timestamp", []))
                                    rx = np.asarray(stream.get("x", []), dtype=float)
                                    ry = np.asarray(stream.get("y", np.zeros(len(rx))), dtype=float)
                                    if len(rt) == len(rx) == len(ry):
                                        moments.add(rt, np.hypot(rx, ry), device.clockbase_hz)
                            if len(values):
                                empty = 0
                                if stats is not None:
                                    stats.add(ts, values, device.clockbase_hz)
                                tail_chunks.append((ts.copy(), values.copy()))
                                cutoff = int(ts[-1])-int(round(reset_window_s*device.clockbase_hz))
                                while tail_chunks and int(tail_chunks[0][0][-1]) < cutoff:
                                    tail_chunks.popleft()
                                if tail_chunks:
                                    first_t, first_v = tail_chunks[0]
                                    mask = first_t >= cutoff
                                    tail_chunks[0] = (first_t[mask], first_v[mask])
                                if sum(t.nbytes+v.nbytes for t,v in tail_chunks) > settings["memory_limit_mb"]*1024**2/4:
                                    raise RuntimeError("Requested reset observation window exceeds bounded analysis memory; native values preserved")
                                tail = Moments()
                                for tail_t, tail_v in tail_chunks:
                                    tail.add(tail_t, tail_v, device.clockbase_hz)
                                final_summary = tail.summary(device.clockbase_hz, settings["baseline_drift_fraction"], settings["baseline_cv_limit"])
                            else:
                                empty += 1
                                if empty >= 3:
                                    raise RuntimeError("No valid matched detector/reference support in three native polls")
                            required_roles = ("sample", "reference", "timing") if self.context.mode == "dual" else ("sample", "timing")
                            elapsed = min(((last_ticks[r]-phase_starts[r])/device.clockbase_hz
                                if r in last_ticks and r in phase_starts else 0.) for r in required_roles)
                            if polls > max(20, int(duration/chunk_s)*5+20):
                                raise RuntimeError("Device-clock capture boundary not reached within bounded retrieval polls")
                            stride = max(1, len(values)//1000)
                            preview_ticks = ts[::stride]
                            def native_preview(role):
                                stream = chunk.get(role, {})
                                stamps = np.asarray(stream.get("timestamp", []))
                                if not len(stamps) or not len(preview_ticks):
                                    return []
                                indices = np.searchsorted(stamps, preview_ticks)
                                amplitudes = np.hypot(np.asarray(stream.get("x", [])),
                                    np.asarray(stream.get("y", np.zeros(len(stamps)))))
                                return amplitudes[indices].tolist()
                            emit({"stage": "acquisition" if phase != "reset_wait" else "recovery waits",
                                "message": f"{phase}: {elapsed:.3g}/{duration:.3g} s",
                                "completed": elapsed, "total": duration,
                                "preview": {"analysis": {"events": [{"time_s": time_from_ticks(ts[::stride], event['original_pump_timestamp'] or baseline.origin or 0, device.clockbase_hz).tolist(),
                                    "sample": native_preview("sample"),
                                    "reference": native_preview("reference") if self.context.mode == "dual" else None,
                                    "ratio": values[::stride].tolist() if self.context.mode == "dual" else None,
                                    "original_pump_timestamp": event["original_pump_timestamp"],
                                    "measured_pump_time_s": [0.0] if event["original_pump_timestamp"] is not None else [],
                                    "pump_marker_qualification": "measured electrical sync; optical arrival unresolved"}]},
                                    "mode": self.context.mode, "kind": kind}})
                        return final_summary
                    acquire(float(settings["pre_observation_s"]), "baseline", baseline)
                    event["baseline"] = baseline.summary(device.clockbase_hz, settings["baseline_drift_fraction"], settings["baseline_cv_limit"])
                    event["native_baselines"] = {role: value.summary(device.clockbase_hz, settings["baseline_drift_fraction"], settings["baseline_cv_limit"]) for role, value in native_baselines.items()}
                    if record["quality_flags"]:
                        raise RuntimeError("Missing native support in baseline; later pump events inhibited")
                    if not event["baseline"]["stationary"] or not all(value["stationary"] for value in event["native_baselines"].values()):
                        raise RuntimeError("Stationary pre-pump baseline failed; pump remains inhibited")
                    if pumped:
                        check()
                        # Budget is consumed at dispatch even if observed sync later goes missing.
                        if history is not None:
                            if operation.hardware:
                                self.context.ownership.assert_owner(operation.ownership)
                            event["state_dispatch_intent"] = history.consume(settings, resolved, operation, event)
                        delivered += 1
                        event["commanded_event_number"] = delivered
                        device.start_event(program)
                        tail = acquire(float(program["duration_s"]), "observation")
                        event["timing_completion"] = device.finish_event()
                        if event["timing_completion"]["frames_status"] != "DONE":
                            raise RuntimeError("Finite timing table did not complete")
                        if event["timing_completion"]["frame_shot_count"] != len(program["frames"]):
                            raise RuntimeError("Finite frame shot-count readback differs from acknowledged complete table")
                        count = len(event["pump_timestamps"])
                        if count != 1:
                            raise RuntimeError(f"Observed electrical pump count {count} != authorized 1; no retry")
                        event["original_pump_timestamp"] = event["pump_timestamps"][0]
                        if last_pump is not None:
                            event["actual_event_interval_s"] = (event["original_pump_timestamp"]-last_pump)/device.clockbase_hz
                        last_pump = event["original_pump_timestamp"]
                        wait = max(0., float(resolved.get("minimum_event_interval_s") or 0.) - (last_ticks["sample"]-last_pump)/device.clockbase_hz)
                        if block_index < len(blocks)-1 and wait > 0:
                            tail = acquire(wait, "reset_wait")
                    else:
                        tail = acquire(float(settings["post_observation_s"]), "observation")
                        if event["pump_timestamps"]:
                            raise RuntimeError("Unexpected pump sync in unpumped control")
                    event["tail_statistics"] = tail
                    delta = abs(tail["mean"]/event["baseline"]["mean"]-1) if tail and "mean" in tail else float("inf")
                    event["reset"] = {"observed_fraction_from_baseline": delta,
                        "record_id": resolved.get("reset_record_id"),
                        "requested_observation_s": reset_window_s,
                        "tolerance_fraction": settings["reset_tolerance_fraction"],
                        "accepted": bool(tail and tail["stationary"] and delta <= settings["reset_tolerance_fraction"] and not record["quality_flags"]),
                        "support": "Retained requested final recovery window, at the same wavenumber and unchanged detector response"}
                    device.stop_stream()
                    previous_block_last_tick = event.get("last_native_timestamp")
                    if pumped and block_index < len(blocks)-1 and not event["reset"]["accepted"]:
                        raise RuntimeError("Measured recovery/reset criterion failed; later pump events inhibited")
                record["status"] = "complete"
            except AcquisitionStopped:
                record["status"] = "stopped"
                record["message"] = "Acquisition stopped"
            except Exception as exc:
                record["status"] = "failed"
                record["error"] = str(exc)
            finally:
                emit({"stage": "restoration", "message": "Disabling emission and timing; verifying restoration"})
                if device is not None:
                    try:
                        def retain_tail(chunk):
                            if writer is None:
                                raise RuntimeError("No native writer available for final device tail")
                            event = record["events"][-1] if record["events"] else {}
                            emit({"stage": "retrieval", "message": "Retaining final available native tail after safe inhibition"})
                            ref = writer.append(chunk, position_index=event.get("position_index", 0),
                                event_index=event.get("event_index", 0), kind="cleanup_tail")
                            record["native_chunks"].append(ref)
                            record["cleanup_tail"] = {"reference": ref, "retention": "one final bounded native poll after inhibition"}
                            sample_ticks = chunk.get("sample", {}).get("timestamp", [])
                            if len(sample_ticks):
                                event.setdefault("first_native_timestamp", int(sample_ticks[0]))
                                event["last_native_timestamp"] = int(sample_ticks[-1])
                            timing = chunk.get("timing", {})
                            for tick, word in zip(timing.get("timestamp", []), timing.get("dio", [])):
                                if int(word) & (1 << int(resolved["pump_marker_bit"])) and event.get("original_pump_timestamp") is None:
                                    event.setdefault("unqualified_pump_marker_candidates", []).append({
                                        "timestamp": int(tick), "source": "cleanup_tail",
                                        "reason": "High level without a qualified observed rising edge"})
                                    event["epoch_quality"] = "missing observed onset; cleanup-tail high level is an unqualified candidate only"
                                    if "missing_observed_pump_epoch" not in record["quality_flags"]:
                                        record["quality_flags"].append("missing_observed_pump_epoch")
                                    break
                        cleanup = device.cleanup(retain_tail=retain_tail)
                        if cleanup.get("preservation_errors"):
                            record["native_preservation_error"] = "; ".join(cleanup["preservation_errors"])
                            record["native_loss_boundary"] = "Final available device tail could not be certified retained"
                    except Exception as exc:
                        cleanup = {"safe_verified": False, "errors": [str(exc)], "actions": []}
                record["restoration"] = cleanup
                if not cleanup["safe_verified"]:
                    record["acquisition_status"] = record["status"]
                    record["status"] = "cleanup_failed"
                    record["cleanup_error"] = "; ".join(cleanup["errors"])
                elif record.get("native_preservation_error") or writer is None:
                    record["status"] = "preservation_failed"
                if history is not None and any(event.get("state_dispatch_intent") for event in record["events"]):
                    try:
                        if operation.hardware:
                            self.context.ownership.assert_owner(operation.ownership)
                        history.outcome(operation, record)
                    except Exception as exc:
                        record["state_history_error"] = str(exc)
                        record["native_preservation_error"] = "Required consumed-state outcome preservation failed: " + str(exc)
                        if cleanup["safe_verified"]:
                            record["status"] = "preservation_failed"
                try:
                    if writer is not None:
                        writer.close()
                    emit({"stage": "saving", "message": "Saving native manifest and restoration record"})
                    save_run(record, directory / "native_run.json")
                    preservation = not bool(record.get("native_preservation_error")) and writer is not None
                    emit({"stage": "analysis", "message": "Analyzing retained native observations"})
                    try:
                        if record["status"] != "stopped":
                            record["analysis"] = analyze_run(record, preliminary=preliminary, blank=blank, cancel=cancel)
                    except Exception as exc:
                        if cancel is not None and hasattr(cancel, "is_set") and cancel.is_set():
                            record["analysis_status"] = "stopped"
                            if record["status"] == "complete":
                                record["status"] = "stopped"
                                record["message"] = "Acquisition stopped"
                        else:
                            record["analysis_error"] = str(exc)
                            if record["status"] == "complete":
                                record["status"] = "analysis_failed"
                    record["preservation_verified"] = preservation
                    record["elapsed_s"] = time.monotonic()-started
                    save_run(record, directory / "run.json")
                except Exception as exc:
                    preservation = False
                    record["storage_error"] = str(exc)
                    if cleanup["safe_verified"]:
                        record["status"] = "preservation_failed"
                finally:
                    if operation.hardware:
                        self.context.ownership.release(operation.ownership,
                            safe_verified=bool(cleanup["safe_verified"]), preservation_verified=preservation,
                            detail=record.get("cleanup_error", record.get("storage_error", record.get("error", record["status"]))))
        record["preservation_verified"] = preservation
        record["elapsed_s"] = time.monotonic()-started
        return record
