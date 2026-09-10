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

    def run(self, snapshot, worker, kind=None, *, review_contract=None, blank=None, background=None):
        operation, plan = snapshot.operation, snapshot.plan
        settings = get(plan, "settings")
        kind = kind or snapshot.kind
        started = monotonic()
        record = {"experiment_id": "repeated_rapid_scan", "schema_version": 1,
                  "run_id": operation.run_id, "mode": get(settings, "mode"), "kind": kind,
                  "condition_id": get(settings, "condition_id", get(get(settings, "condition", {}), "condition_id")),
                  "operation": operation.to_dict(), "plan": plain(plan), "review_contract": plain(review_contract or {}),
                  "preliminary_selection": snapshot.preliminary, "native_movies": [], "qualification_movies": [],
                  "processed": [], "assessments": [], "status": "partial", "errors": [],
                  "output_path": str(operation.output_path), "baseline": None}
        record["background"] = background
        self.last_result = record
        self.active = True
        self._cancel_event = worker.cancel_event
        self._physical_state = None
        self._physical_pending_state = None
        self._physical_records = record.setdefault("physical_actions", [])
        acquirer, failure, restoration = None, None, {"safe_verified": True, "errors": [], "device_access_started": False}
        preservation_verified = False
        try:
            worker.check_cancelled()
            if settings is None:
                raise ValueError("Scientific plan settings are missing")
            if operation.instance_id != f"repeated_rapid_scan:{get(settings, 'mode')}":
                raise ValueError("Operation mode differs from the frozen scientific plan")
            if operation.hardware and kind != "capabilities" and not get(plan, "ready_for_hardware", False):
                missing = [get(item, "message", str(item)) for item in get(plan, "readiness_items", ()) if get(item, "blocks_hardware", True)]
                raise ValueError("Installed acquisition readiness: " + "; ".join(missing))
            factory = self.acquirer_factory
            if factory is None:
                if operation.hardware:
                    factory = InstalledDevicesAcquirer
                else:
                    from .simulation import SimulationAcquirer
                    factory = SimulationAcquirer
            acquirer = factory(self.context, operation, plan)
            acquirer.role = kind
            acquirer.prepare(worker)
            record["readbacks"] = acquirer.readbacks
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
            physical_uncertain = self._physical_state in ("pump_blocked", "dark") or self._physical_pending_state in ("pump_blocked", "dark")
            if operation.hardware and physical_uncertain:
                try:
                    if not restoration.get("safe_verified", False):
                        raise RuntimeError("Physical restoration cannot be requested until safe optical output inhibition is verified")
                    worker.confirm_physical_action("Instrument outputs are inhibited. Restore the sample, probe and pump path to the recorded pre-run physical configuration.", cleanup=True)
                    self._physical_records.append({"action": "restore physical configuration", "accepted": True})
                except BaseException as exc:
                    restoration["safe_verified"] = False
                    restoration.setdefault("errors", []).append(f"Physical restoration not confirmed: {exc}")
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
        if kind == "preliminary" and get(settings, "mode") == "single":
            if not blank or not get(blank, "baseline") or not get(get(blank, "baseline"), "complete", False):
                raise ValueError("Acquire or load a complete compatible sequential blank before the sample preliminary")
            record["blank"] = blank
            record["blank_run_id"] = get(blank, "run_id")
        if record["operation"]["hardware"]:
            self._confirm_physical(worker, "blank" if kind == "blank" else "sample",
                "Load the complete matched blank/control cell and confirm condition and temperature identifiers." if kind == "blank" else
                "Load the sample and, for dual mode, the matched-buffer reference. Confirm preparation, cell, position and temperature records; pump commands remain inhibited.", acquirer)
        selected = list(get(plan, "movies"))
        if kind == "preliminary":
            # One complete unpumped movie per direction supplies sample Q0.
            selected = list({get(movie, "direction"): movie for movie in reversed(selected)}.values())
        for index, movie_plan in enumerate(selected):
            worker.check_cancelled()
            movie = acquirer.capture(_unpumped(movie_plan, ":"+kind), worker)
            record["native_movies"].append(movie)
            state = self._stationarity(movie.scans, settings)
            record["assessments"].append(state)
            if not state.accepted:
                raise ValueError("Unpumped train rejected: " + "; ".join(state.reasons))
            record["processed"].append(reconstruct_movie(movie, background=background or (get(blank, "baseline") if blank else None),
                spectral_match_tolerance_cm1=(settings.scan_stop_cm1-settings.scan_start_cm1)/(max(64, int(settings.sample_rate_hz*settings.measured_scan_period_s))-1)*.6,
                cancelled=worker.cancel_event.is_set,
                band_windows_cm1=settings.band_windows_cm1, offband_windows_cm1=settings.offband_windows_cm1))
        baseline_kind = "background" if kind == "blank" else "q0" if settings.mode == "dual" else "single_baseline"
        # Acquisition acceptance is distinct from the host's named explicit
        # preliminary review required before Start; snapshot contains that review.
        record["baseline"] = _combined_baseline(record["native_movies"], baseline_kind, record["run_id"]+":baseline", accepted=True)
        if not record["baseline"].complete:
            raise ValueError("Preliminary/blank lacks complete valid detector and wavelength support")
        record["status"] = "complete"

    @staticmethod
    def _stationarity(scans, settings):
        return assess_stationarity(scans, settings.band_windows_cm1, settings.offband_windows_cm1,
            relative_tolerance=settings.recovery.stationarity_relative_tolerance,
            minimum_scans=settings.recovery.consecutive_scans)

    def _measurement(self, acquirer, plan, preliminary, worker, record, blank, background=None):
        settings = get(plan, "settings")
        baseline = get(preliminary, "baseline")
        if baseline is None or not baseline.complete or not baseline.accepted:
            raise ValueError("A compatible accepted unpumped preliminary baseline is required")
        blank = blank or get(preliminary, "blank")
        background = background or (get(blank, "baseline") if blank else None) or get(preliminary, "background")
        record["background"] = background
        if settings.mode == "single" and background is None:
            raise ValueError("Single-detector measurement requires its compatible complete sequential blank")
        record["baseline"], record["blank"] = baseline, blank
        record["blank_run_id"] = get(blank, "run_id") if blank else None
        movies = get(plan, "movies")
        for index, movie_plan in enumerate(movies):
            worker.check_cancelled()
            if record["operation"]["hardware"]:
                control = get(movie_plan, "control")
                physical_state = control if control in ("pump_blocked", "dark") else "sample"
                self._confirm_physical(worker, physical_state, get(movie_plan, "required_action"), acquirer)
            if get(movie_plan, "control") == "sample":
                notify(worker, f"Pre-pump stationarity: qualification train for movie {index+1}/{len(movies)}")
                qualification = acquirer.capture(movie_plan, worker, qualification=True)
                record["qualification_movies"].append(qualification)
                state = self._stationarity(qualification.scans, settings)
                record["assessments"].append(state)
                if not state.accepted:
                    raise ValueError("Pre-pump stationarity rejected; pump remains inhibited: " + "; ".join(state.reasons))
            movie = acquirer.capture(movie_plan, worker)
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
            permitted_exclusions = {"missing_calibrated_trajectory", "missing_baseline_support"}
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
                    raise ValueError("Declared movie pre-pump region failed retrospective stationarity; no next pump")
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

    def _confirm_physical(self, worker, state, description, acquirer):
        if self._physical_state == state:
            return
        callback = getattr(worker, "confirm_physical_action", None)
        if callback is None:
            raise ValueError("Connected operation requires the host operator physical-action confirmation")
        pause = getattr(acquirer, "safe_pause", None)
        if pause is None:
            raise ValueError("Connected adapter cannot verify safe pause before manual physical action")
        pause()
        self._physical_pending_state = state
        callback(description)
        self._physical_state = state
        self._physical_pending_state = None
        self._physical_records.append({"state": state, "description": description, "accepted": True,
                                       "observed_utc": datetime.now(timezone.utc).isoformat()})
