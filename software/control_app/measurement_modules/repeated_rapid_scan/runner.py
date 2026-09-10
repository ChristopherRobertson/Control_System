"""Independent repeated-movie workflow and host-owned preservation lifecycle."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

import numpy as np

from .acquisition import InstalledDevicesAcquirer, get, notify, plain
from .data import StateAssessment
from .processing import assess_recovery, assess_stationarity, build_baseline, combine_baselines, reconstruct_movie


def _unpumped(movie, suffix):
    compiled = get(movie, "compiled")
    frames = plain(get(compiled, "frames"))
    for frame in frames:
        for channel in "AB":
            frame["channels"][channel]["enabled"] = False
    if hasattr(compiled, "__dataclass_fields__"):
        compiled = replace(compiled, frames=tuple(frames), electrical_pump_count=0,
                           pump_command_s=None, fire_command_s=None)
        return replace(movie, movie_id=get(movie, "movie_id")+suffix, control="probe_only", pump_count=0, compiled=compiled)
    return {**plain(movie), "movie_id": get(movie, "movie_id")+suffix, "control": "probe_only", "pump_count": 0,
            "compiled": {**plain(compiled), "frames": frames, "electrical_pump_count": 0,
                         "pump_command_s": None, "fire_command_s": None}}


def _combined_baseline(movies, kind, record_id, *, accepted):
    if not movies:
        return None
    return combine_baselines([build_baseline(movie, kind=kind, pre_pump_only=False, accepted=accepted)
                              for movie in movies], record_id=record_id, accepted=accepted)


class RepeatedRapidScanRunner:
    """One mutable runner per tab; ownership release is always the final action.

    ``run`` returns a persisted record with ``baseline``, ``native_movies``,
    ``processed``, ``status`` and ``output_path``.  Error/cancellation outcomes
    are saved and exposed as ``last_result`` before the original error is raised.
    Cleanup/save failures take precedence over normal acquisition cancellation.
    """
    def __init__(self, context, acquirer_factory=None, *, saver=None):
        self.context, self.acquirer_factory = context, acquirer_factory
        self.saver = saver
        self.last_result = None
        self.active = False
        self._cancel_event = None

    def request_abort(self, reason="Operator stop"):
        if self._cancel_event is not None:
            self._cancel_event.set()

    def run(self, snapshot, worker, kind=None, *, compatibility_contract=None, review_contract=None, blank=None, background=None):
        operation, plan = snapshot.operation, snapshot.plan
        settings = get(plan, "settings")
        kind = kind or snapshot.kind
        started = monotonic()
        record = {"experiment_id": "repeated_rapid_scan", "schema_version": 1,
                  "run_id": operation.run_id, "mode": get(settings, "mode"), "kind": kind,
                  "condition_id": get(settings, "condition_id", get(get(settings, "condition", {}), "condition_id")),
                  "operation": operation.to_dict(), "plan": plain(plan), "compatibility_contract": plain(compatibility_contract or review_contract or {}),
                  "preliminary_selection": snapshot.preliminary, "native_movies": [], "qualification_movies": [], "omitted_controls": [],
                  "processed": [], "assessments": [], "status": "partial", "errors": [],
                  "output_path": str(operation.output_path), "baseline": None}
        record["background"] = background
        self.last_result = record
        self.active = True
        self._cancel_event = worker.cancel_event
        acquirer, failure, restoration = None, None, {"safe_verified": True, "errors": [], "device_access_started": False}
        preservation_verified = False
        try:
            worker.check_cancelled()
            if settings is None:
                raise ValueError("Scientific plan settings are missing")
            if operation.instance_id != f"repeated_rapid_scan:{get(settings, 'mode')}":
                raise ValueError("Operation mode differs from the frozen scientific plan")
            factory = self.acquirer_factory
            if factory is None:
                if operation.hardware:
                    factory = InstalledDevicesAcquirer
                else:
                    from .simulation import SimulationAcquirer
                    factory = SimulationAcquirer
            acquirer = factory(self.context, operation, plan)
            acquirer.role = kind
            discover = getattr(acquirer, "discover", None)
            if operation.hardware and callable(discover):
                discover(worker)
                if kind != "capabilities":
                    from .planner import resolve_intent_settings, build_plan
                    from .settings import AcquisitionIntent
                    record["requested_plan"] = record["plan"]
                    settings = resolve_intent_settings(AcquisitionIntent.from_settings(settings),
                        mode=settings.mode, base_settings=settings, capabilities=acquirer.readbacks["capabilities"],
                        overrides=settings.manual_overrides)
                    plan = build_plan(settings, capabilities=acquirer.readbacks["capabilities"])
                    acquirer.plan, acquirer.settings = plan, settings
            if kind != "capabilities" or not callable(discover):
                acquirer.prepare(worker)
            if kind != "capabilities":
                # Preserve the selected native rate/filter/range after ordinary
                # hardware quantization; do not treat quantization as a refusal.
                actual_values = get(get(acquirer.readbacks, "capabilities", {}), "live_settings", {})
                fields = ("sample_rate_hz", "reference_rate_hz", "sample_filter_order", "reference_filter_order",
                          "sample_filter_timeconstant_s", "reference_filter_timeconstant_s",
                          "sample_input_range_v", "reference_input_range_v",
                          "mircat_pulse_rate_hz", "mircat_pulse_width_ns", "mircat_current_ma")
                updates = {name: actual_values[name] for name in fields if name in actual_values}
                if updates:
                    settings = replace(settings, **updates)
                    from .planner import build_plan
                    plan = build_plan(settings, capabilities=acquirer.readbacks.get("capabilities", {}))
                    acquirer.plan, acquirer.settings = plan, settings
                from .session import operational_contract
                requested_contract = record["compatibility_contract"]
                record["requested_compatibility_contract"] = requested_contract
                record["compatibility_contract"] = operational_contract(settings.to_dict(),
                    {"observed_changes": requested_contract.get("instrument_changes", {})})
                record["plan"] = plain(plan)
                if kind == "blank":
                    retained = get(get(plan, "capabilities", {}), "selected_baseline_bytes", 0)
                    if get(plan, "estimates").get("blank_action_memory_bytes", 0) + retained > settings.memory_limit_bytes:
                        raise MemoryError("Full blank schedule exceeds available memory allocation")
                    if get(plan, "estimates").get("blank_action_storage_bytes", 0) + retained > settings.storage_limit_bytes:
                        raise OSError("Full blank schedule exceeds native storage allocation")
            record["readbacks"] = acquirer.readbacks
            record["capabilities"] = acquirer.readbacks.get("capabilities", {})
            if kind == "capabilities":
                record["capabilities"] = acquirer.readbacks.get("capabilities", {})
                record["status"] = "complete"
            elif kind in ("blank", "preliminary"):
                self._preliminary(acquirer, plan, kind, worker, record, blank or get(snapshot.preliminary, "blank"), background)
            elif kind == "measurement":
                self._measurement(acquirer, plan, snapshot.preliminary, worker, record, blank, background)
            else:
                raise ValueError(f"Unsupported repeated rapid-scan operation {kind!r}")
        except BaseException as exc:
            failure = exc
            record["status"] = "cancelled" if isinstance(exc, InterruptedError) else "failed"
            record["errors"].append(f"{type(exc).__name__}: {exc}")
        finally:
            if acquirer is not None:
                try:
                    restoration = acquirer.restore(worker)
                except BaseException as exc:
                    restoration = {"safe_verified": False, "errors": [f"{type(exc).__name__}: {exc}"]}
                record["raw_movies"] = acquirer.raw_movies
                record["readbacks"] = acquirer.readbacks
            record["restoration"] = restoration
            if restoration.get("errors") or not restoration.get("safe_verified", False):
                record["errors"].extend(restoration.get("errors", ["Safe restoration not verified"]))
                record["status"] = "cleanup_failed"
            record["elapsed_s"] = monotonic()-started
            record["completed_utc"] = datetime.now(timezone.utc).isoformat()
            notify(worker, "Saving: preserving native, partial, excluded and restoration records")
            try:
                if self.saver is None:
                    from .persistence import save_run
                    saver = save_run
                else:
                    saver = self.saver
                saver(Path(operation.output_path), record=record)
                preservation_verified = True
            except BaseException as exc:
                record["status"] = "preservation_failed"
                record["errors"].append(f"Native preservation failed: {type(exc).__name__}: {exc}")
                failure = RuntimeError("; ".join(record["errors"]))
            finally:
                if operation.ownership is not None:
                    try:
                        self.context.ownership.release(operation.ownership,
                            safe_verified=bool(restoration.get("safe_verified", False)),
                            preservation_verified=preservation_verified,
                            detail=f"repeated_rapid_scan {kind}: {record['status']}")
                    except BaseException as exc:
                        record["errors"].append(f"Ownership release failed: {exc}")
                        failure = RuntimeError("; ".join(record["errors"]))
                self.active = False
                self._cancel_event = None
        if record["status"] == "cleanup_failed":
            raise RuntimeError("Restoration failed: " + "; ".join(record["errors"])) from failure
        if failure is not None:
            if isinstance(failure, InterruptedError):
                raise InterruptedError("Acquisition stopped; partial records preserved") from failure
            raise failure
        notify(worker, f"Analysis complete: {record['status']}; {record['elapsed_s']:.2f} s elapsed")
        return record

    def _preliminary(self, acquirer, plan, kind, worker, record, blank, background=None):
        settings = get(plan, "settings")
        if kind == "blank" and get(settings, "mode") == "dual":
            raise ValueError("Dual mode records matched reference simultaneously; no routine sequential blank")
        blank = self._reusable(blank, record, "blank")
        record["blank"] = blank
        record["background"] = background
        record["blank_run_id"] = get(blank, "run_id") if blank else None
        selected = list(get(plan, "movies"))
        if kind == "preliminary":
            # One complete unpumped movie per direction supplies sample Q0.
            selected = list({get(movie, "direction"): movie for movie in reversed(selected)}.values())
        display_background = self._normalization(background or (get(blank, "baseline") if blank else None), record, background=True)
        for index, movie_plan in enumerate(selected):
            worker.check_cancelled()
            movie = self._capture(acquirer, _unpumped(movie_plan, ":"+kind), worker, record)
            record["native_movies"].append(movie)
            state = self._stationarity(movie.scans, settings)
            record["assessments"].append(state)
            record["processed"].append(reconstruct_movie(movie, background=display_background,
                spectral_match_tolerance_cm1=(settings.scan_stop_cm1-settings.scan_start_cm1)/(max(64, int(settings.sample_rate_hz*settings.measured_scan_period_s))-1)*.6,
                cancelled=worker.cancel_event.is_set,
                band_windows_cm1=settings.band_windows_cm1, offband_windows_cm1=settings.offband_windows_cm1))
        baseline_kind = "background" if kind == "blank" else "q0" if settings.mode == "dual" else "single_baseline"
        # Baseline validity and stationarity are measured diagnostics. No named
        # reviewer or approval flag is required to retain/use raw observations.
        record["baseline"] = _combined_baseline(record["native_movies"], baseline_kind, record["run_id"]+":baseline", accepted=True)
        if not record["baseline"].complete:
            record.setdefault("warnings", []).append("Baseline has incomplete support; raw data retained and unsupported normalized points remain missing")
        record["status"] = "complete"

    @staticmethod
    def _capture(acquirer, movie_plan, worker, record):
        movie = acquirer.capture(movie_plan, worker)
        return replace(movie, metadata={**movie.metadata, "compatibility_contract": record["compatibility_contract"]})

    @staticmethod
    def _stationarity(scans, settings):
        return assess_stationarity(scans, settings.band_windows_cm1, settings.offband_windows_cm1,
            relative_tolerance=settings.recovery.stationarity_relative_tolerance,
            minimum_scans=settings.recovery.consecutive_scans)

    def _measurement(self, acquirer, plan, preliminary, worker, record, blank, background=None):
        settings = get(plan, "settings")
        preliminary = self._reusable(preliminary, record, "sample baseline")
        blank = self._reusable(blank or get(preliminary, "blank"), record, "blank")
        background = background or (get(blank, "baseline") if blank else None) or get(preliminary, "background")
        if preliminary is None or get(preliminary, "baseline") is None:
            notify(worker, "Acquisition: recording unpumped sample baseline automatically")
            preliminary = {"experiment_id": "repeated_rapid_scan", "schema_version": 1,
                "kind": "preliminary", "mode": settings.mode, "condition_id": settings.condition_id,
                "run_id": record["run_id"], "compatibility_contract": record["compatibility_contract"],
                "operation": record["operation"], "plan": record["plan"], "native_movies": [],
                "processed": [], "assessments": [], "status": "partial"}
            record["auto_preliminary"] = preliminary
            old_role = acquirer.role
            acquirer.role = "preliminary"
            try:
                self._preliminary(acquirer, plan, "preliminary", worker, preliminary, blank, background)
            finally:
                acquirer.role = old_role
        baseline = get(preliminary, "baseline")
        record["baseline"], record["blank"], record["background"] = baseline, blank, background
        record["blank_run_id"] = get(blank, "run_id") if blank else None
        baseline = self._normalization(baseline, record)
        background = self._normalization(background, record, background=True)
        if settings.mode == "single" and background is None:
            record.setdefault("warnings", []).append("No compatible blank: native signal and changes relative to the unpumped sample are available; absolute absorbance is unavailable")
        movies = get(plan, "movies")
        for index, movie_plan in enumerate(movies):
            worker.check_cancelled()
            if record["operation"]["hardware"] and get(movie_plan, "control") in ("pump_blocked", "dark"):
                record["omitted_controls"].append({"movie_id": get(movie_plan, "movie_id"),
                    "requested_control": get(movie_plan, "control"), "status": "not_acquired",
                    "reason": "No installed actuator changes the optical blocking state; no blocking state or control data is fabricated"})
                continue
            movie = self._capture(acquirer, movie_plan, worker, record)
            record["native_movies"].append(movie)
            expected = get(movie_plan, "pump_count", 0)
            if len(movie.pump_observations) != expected or any(not p.independently_observed for p in movie.pump_observations):
                raise ValueError("Independent observed pump count differs from authorization; no biological retry")
            notify(worker, "Analysis: align native timestamps and measured scan trajectories")
            reconstruction = reconstruct_movie(movie, baseline=baseline, background=background,
                band_windows_cm1=settings.band_windows_cm1, offband_windows_cm1=settings.offband_windows_cm1,
                alignment_tolerance_s=0.25/max(settings.sample_rate_hz, settings.reference_rate_hz),
                spectral_match_tolerance_cm1=(settings.scan_stop_cm1-settings.scan_start_cm1)/(max(64, int(settings.sample_rate_hz*settings.measured_scan_period_s))-1)*.6,
                cancelled=worker.cancel_event.is_set)
            record["processed"].append(reconstruction)
            diagnostic_dark = get(movie_plan, "control") == "dark"
            permitted_exclusions = {"missing_calibrated_trajectory", "missing_baseline_support", "missing_background_support"}
            if diagnostic_dark:
                # A measured detector-dark control has no physical logarithmic
                # normalization support. Keep zero/native samples and flags;
                # never manufacture positive intensities to obtain absorbance.
                permitted_exclusions.update(("nonpositive_sample", "bad_reference", "nonpositive_reference"))
            bad = [name for point in reconstruction.points for name, flags in point.flags.items()
                   if name not in permitted_exclusions and np.any(flags)]
            if bad or reconstruction.status == "rejected":
                raise ValueError("Movie has rejected detector support: " + ", ".join(sorted(set(bad))))
            if get(movie_plan, "control") == "sample":
                pre, post = [], []
                point_map = {point.scan_index: point for point in reconstruction.points}
                for scan in movie.scans:
                    times = point_map[scan.scan_index].time_s
                    if len(times) and max(times) < 0:
                        pre.append(scan)
                    elif len(times) and min(times) > 0:
                        post.append(scan)
                pre_state = self._stationarity(pre, settings)
                record["assessments"].append(pre_state)
                if not pre_state.accepted:
                    record.setdefault("warnings", []).append("Measured pre-pump sample is nonstationary; recovery inference is limited")
                notify(worker, "Recovery verification: measured band populations and off-band baseline")
                reset = assess_recovery(pre, post, settings.band_windows_cm1, settings.offband_windows_cm1,
                    band_relative_tolerance=settings.recovery.band_relative_tolerance,
                    offband_absolute_tolerance=settings.recovery.offband_absolute_tolerance,
                    consecutive_scans=settings.recovery.consecutive_scans)
                last_delay = max((float(np.max(point.time_s)) for point in reconstruction.points if len(point.time_s)), default=0.)
                if last_delay < settings.recovery.min_recovery_s:
                    reset = StateAssessment(False, (*reset.reasons, "Measured movie does not reach minimum recovery duration"), reset.metrics)
                record["assessments"].append(reset)
                if not reset.accepted:
                    record["status"] = "incomplete_recovery"
                    record["next_pump_inhibited"] = True
                    record["outcome"] = "Duration-limited incomplete recovery; native finite movie retained and no equivalent pump retried"
                    break
            notify(worker, f"Movie schedule: {index+1}/{len(movies)} complete", index+1, len(movies))
        else:
            record["status"] = "complete"

    @staticmethod
    def _normalization(value, record, *, background=False):
        if value is None:
            return None
        from .session import compatibility_conflicts
        reasons = []
        if value.mode != record["mode"]:
            reasons.append("Detector mode differs")
        expected = "background" if background else "q0" if record["mode"] == "dual" else "single_baseline"
        if value.kind != expected:
            reasons.append("Reference kind differs")
        if not value.complete:
            reasons.append("Reference record has incomplete native support")
        if "acquisition" in value.compatibility:
            reasons.extend(compatibility_conflicts(value.compatibility, record["compatibility_contract"]))
        if reasons:
            record.setdefault("unused_normalizations", []).append({"source": value, "reasons": reasons})
            record.setdefault("warnings", []).append("Reference retained without normalization: " + "; ".join(reasons))
            return None
        return value

    @staticmethod
    def _reusable(candidate, record, label):
        if not candidate:
            return None
        from .session import compatibility_conflicts, record_contract
        observed = record_contract(candidate)
        conflicts = compatibility_conflicts(observed, record["compatibility_contract"]) if observed is not None else ["No acquisition compatibility information"]
        if get(candidate, "mode") != record["mode"]:
            conflicts.append("Detector mode differs")
        if conflicts:
            record.setdefault("unused_baselines", []).append({"kind": label, "source": candidate, "differences": conflicts})
            return None
        return candidate
