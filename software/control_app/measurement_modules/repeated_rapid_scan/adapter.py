"""Experiment-owned scientific adapter for the frozen guided host interface."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import csv
import json
from pathlib import Path
from threading import Event

import numpy as np

from control_app.measurement_host.context import thaw_data
from control_app.measurement_host.interchange import load_sample_selection
from control_app.measurement_host.presentation import ScientificSelections
from .session import ReviewSession, scientific_contract, compatibility_conflicts
from .settings import RepeatedRapidScanSettings
from .planner import build_plan


class _WorkerBridge:
    def __init__(self, worker, adapter, simulated):
        self.worker, self.adapter, self.simulated = worker, adapter, simulated

    def __getattr__(self, name):
        return getattr(self.worker, name)

    def check_cancelled(self):
        self.worker.check_cancelled()

    def confirm_physical_action(self, description, *, cleanup=False):
        if not cleanup:
            self.check_cancelled()
        if self.simulated:
            self.worker.message.emit("SIMULATION physical condition: " + description)
            return True
        if self.adapter.manual_action_handler is None:
            raise ValueError("A manual physical action is required: " + description)
        return self.adapter.manual_action_handler(description, self.worker, cleanup=cleanup)


class RepeatedRapidScanAdapter:
    def __init__(self, context, settings_widget):
        self.context, self.settings_widget = context, settings_widget
        self.session = ReviewSession(context.mode)
        self.capabilities = None
        self.calibration = None
        self.runner = None
        self.manual_action_handler = None
        self._pending_selection = None
        self._pending_bundle = None
        self.fit_model = None
        saved = context.preferences.value("settings", None)
        if saved:
            try:
                settings_widget.apply(json.loads(saved) if isinstance(saved, str) else saved)
            except (ValueError, TypeError, KeyError):
                # An incompatible preference cannot disable construction; loaded
                # native plans still surface their explicit validation error.
                pass

    def read_settings(self):
        return self.settings_widget.read()

    def apply_settings(self, settings):
        self.settings_widget.apply(settings)
        self.context.preferences.setValue("settings", json.dumps(settings))
        self.context.preferences.sync()

    def make_plan(self, settings):
        return build_plan(settings, capabilities=self.capabilities, calibration=self.calibration)

    def validate_plan(self, plan):
        return ()  # build_plan validates structure; readiness is separate and visible.

    def summarize_plan(self, plan):
        s, e = plan.settings, plan.estimates
        items = "\n".join(f"• {item.message}" for item in plan.readiness_items)
        actual = plan.actual
        return (f"{plan.movie_count} finite movies · {plan.pump_count} authorized electrical pump events\n"
                f"{e['scans_per_movie']} scans/movie: {s.pre_scans} before, one crossing, {s.post_scans} after\n"
                f"{e['movie_duration_s']:.6g} s/movie · {s.mode} detector mode · {s.execution}\n"
                f"Requested period {s.measured_scan_period_s:.9g} s; selected {plan.selected['scan_period_s']:.9g} s; "
                f"measured readback {actual.get('scan_period_s')!r} s\n"
                f"Full-movie memory {e['movie_memory_bytes']/1024**2:.1f} MiB; retained storage {e['storage_bytes']/1024**2:.1f} MiB\n"
                f"Retained-run memory estimate {e.get('retained_run_memory_bytes', e['movie_memory_bytes'])/1024**2:.1f} MiB\n"
                f"Timing upload estimate {e['upload_s']:.1f} s; full workflow estimate {e['wall_time_s']:.1f} s\n"
                f"Reset: every population band ≤ {s.recovery.band_relative_tolerance:g} relative change; "
                f"off-band ≤ {s.recovery.offband_absolute_tolerance:g}; {s.recovery.consecutive_scans} consecutive scans. "
                f"Wait allowance {s.recovery.max_reset_wait_s:g} s. An incomplete recovery stops further equivalent pumps.\n"
                f"{s.value_source}\nReadiness: {'applicable evidence resolved' if not items else chr(10)+items}")

    def wall_estimate(self, plan):
        return float(plan.estimates.get("wall_time_s", 0)) if plan else 0.

    def selected_records(self):
        return ScientificSelections(tuple(deepcopy(self.session.calibration_records)), tuple(deepcopy(self.session.sample_records)))

    def hardware_required(self, kind, settings):
        return settings.get("execution") == "hardware"

    def _contract(self, settings, configuration=None, calibration=None, samples=None):
        configuration = self.context.configuration() if configuration is None else thaw_data(configuration)
        contract = scientific_contract(thaw_data(settings), self.session.configuration_contract(configuration),
            self.session.calibration_records if calibration is None else thaw_data(calibration),
            self.session.sample_records if samples is None else thaw_data(samples))
        contract["background_record_id"] = getattr(self.session.background, "record_id", None)
        return contract

    def validate_blank(self, plan):
        if self.context.mode == "dual":
            return ()
        if self.session.blank is None:
            return ("no sequential blank is selected",)
        record = self.session.blank
        errors = list(self.session.check(record, self._contract(plan.settings.to_dict())))
        if record.get("kind") != "blank":
            errors.append("selected record is not a sequential blank")
        if record.get("status") not in ("complete", "completed"):
            errors.append("sequential blank is partial, rejected or interrupted")
        return tuple(errors)

    def validate_review(self, preliminary, plan):
        errors = list(self.session.check(preliminary, self._contract(plan.settings.to_dict())))
        if preliminary.get("kind") != "preliminary":
            errors.append("record is not an unpumped sample preliminary")
        if preliminary.get("status") not in ("complete", "completed"):
            errors.append("preliminary is partial, rejected or interrupted")
        if self.context.mode == "single":
            errors.extend(self.validate_blank(plan))
            selected_id = (self.session.blank or {}).get("run_id")
            recorded_id = preliminary.get("blank_run_id")
            if selected_id != recorded_id:
                errors.append(f"blank selection changed: preliminary used {recorded_id!r}; selected {selected_id!r}")
        self.session.errors = errors
        return tuple(errors)

    def summarize_preliminary(self, result):
        count = sum(len(movie.scans) for movie in result.get("native_movies", ()))
        label = "simultaneous Q₀ = sample/reference" if self.context.mode == "dual" else "sample with compatible sequential blank"
        return (f"{count} unpumped scans retained; {label}. Inspect native signals, support and spectrum before approving. "
                "Review is specific to these settings, condition, calibrations and instrument state.")

    def _run(self, snapshot, worker, kind):
        from .runner import RepeatedRapidScanRunner
        self.runner = RepeatedRapidScanRunner(self.context)
        contract = self._contract(snapshot.operation.settings, snapshot.operation.configuration,
                                  snapshot.operation.calibration_records, snapshot.operation.sample_records)
        bridge = _WorkerBridge(worker, self, not snapshot.operation.hardware)
        result = self.runner.run(snapshot, bridge, kind=kind, review_contract=contract,
                                 blank=deepcopy(self.session.blank), background=deepcopy(self.session.background))
        result.setdefault("review_contract", contract)
        result.setdefault("kind", kind)
        result.setdefault("run_id", snapshot.operation.run_id)
        if kind == "preliminary" and self.context.mode == "single":
            result.setdefault("blank_run_id", (self.session.blank or {}).get("run_id"))
        return result

    def run_preliminary(self, snapshot, worker):
        return self._run(snapshot, worker, "preliminary")

    def run_measurement(self, snapshot, worker):
        return self._run(snapshot, worker, "measurement")

    def run_auxiliary(self, snapshot, worker, kind):
        return self._run(snapshot, worker, kind)

    def request_abort(self, reason):
        if self.runner is not None:
            self.runner.request_abort(reason)

    def save_plan(self, path, settings, plan):
        path = Path(path)
        with path.open("x", encoding="utf-8") as stream:
            json.dump({"record_kind": "repeated_rapid_scan_plan", "schema_version": 1,
                       "experiment_id": "repeated_rapid_scan", "mode": self.context.mode,
                       "settings": settings, "plan": plan.to_dict(),
                       "calibration_records": self.session.calibration_records,
                       "sample_records": self.session.sample_records}, stream, indent=2, allow_nan=False)
        self.context.preferences.setValue("settings", json.dumps(settings))

    def load_plan(self, path):
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if (value.get("record_kind") != "repeated_rapid_scan_plan" or value.get("schema_version") != 1
                or value.get("experiment_id") != "repeated_rapid_scan" or value.get("mode") != self.context.mode):
            raise ValueError("Incompatible experiment, detector mode or plan schema")
        settings = RepeatedRapidScanSettings.from_dict(value["settings"])
        if settings.mode != self.context.mode:
            raise ValueError("Plan settings belong to another detector mode")
        # Saved evidence is provenance; promotion and installed readbacks must be
        # resolved again through their authoritative providers before real use.
        return settings.to_dict()

    def load_run(self, path):
        from .persistence import load_run
        settings = RepeatedRapidScanSettings.from_dict(self.read_settings())
        saved = load_run(path, expected_mode=self.context.mode, expected_condition_id=settings.condition_id)
        record = dict(saved.record)
        metadata = dict(record.get("metadata", {}))
        return {**metadata, **record, "native_movies": record.get("movies", record.get("native_movies", ())),
                "processed": record.get("results", record.get("processed", ())),
                "output_path": str(path), "run_id": saved.run_id}

    def load_record(self, path, kind):
        result = self.load_run(path)
        if result.get("kind") != kind:
            raise ValueError(f"Expected a {kind} record; saved record is {result.get('kind')!r}")
        errors = compatibility_conflicts(result.get("review_contract", {}), self._contract(self.read_settings()))
        if errors:
            raise ValueError("Incompatible record: " + "; ".join(errors))
        if result.get("status") not in ("complete", "completed"):
            raise ValueError("A partial, interrupted or rejected record cannot supply a blank/review baseline")
        return result

    def export_run(self, path, result):
        with Path(path).open("x", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["movie_id", "scan_index", "direction", "native_point", "time_s", "wavenumber_cm1",
                             "normalized_signal", "delta_absorbance", "absolute_absorbance", "variance_delta_absorbance", "valid", "exclusions"])
            for movie in result.get("processed", ()):
                for point in movie.points:
                    for i in range(len(point.time_s)):
                        reasons = [name for name, flags in point.flags.items() if np.asarray(flags)[i]]
                        writer.writerow([movie.movie_id, point.scan_index, point.direction, i, point.time_s[i],
                            point.wavenumbers_cm1[i], point.normalized_signal[i], point.delta_absorbance[i],
                            point.absolute_absorbance[i], point.variance_delta_absorbance[i], point.valid[i], ";".join(reasons)])

    def read_selection(self, path):
        return load_sample_selection(path).to_dict()

    def apply_selection(self, selection):
        settings = self.read_settings()
        if selection["condition_id"] != settings["condition"]["condition_id"]:
            raise ValueError("Sample selection condition does not match the selected condition")
        if selection["sample_id"] != settings["condition"]["sample_id"]:
            raise ValueError("Sample selection sample_id does not match the selected sample")
        settings["condition"]["sample_selection_id"] = selection["selection_id"]
        settings["band_windows_cm1"] = [[w["lower_cm1"], w["upper_cm1"]] for w in selection["windows"]]
        lower = min(w[0] for w in settings["band_windows_cm1"] + list(settings["offband_windows_cm1"]))
        upper = max(w[1] for w in settings["band_windows_cm1"] + list(settings["offband_windows_cm1"]))
        settings["scan_start_cm1"], settings["scan_stop_cm1"] = lower, upper
        self.session.sample_records = [deepcopy(selection)]
        self.apply_settings(settings)

    def read_bundle(self, bundle_id):
        bundle = self.context.promoted_bundle(bundle_id)
        record = {"bundle_id": bundle.bundle_id, "manifest": deepcopy(bundle.manifest), "path": str(bundle.path)}
        background_file = bundle.manifest.get("repeated_rapid_scan", {}).get("background_file")
        if background_file and self.context.mode == "dual":
            from .persistence import load_baseline
            root = Path(bundle.path).resolve()
            path = (root / background_file).resolve()
            if not path.is_relative_to(root):
                raise ValueError("Promoted background path must remain within its bundle")
            background = load_baseline(path, expected_mode="dual")
            if background.kind != "background" or not background.complete or not background.accepted:
                raise ValueError("Promoted path balance must be an accepted complete measured background B")
            record["background"] = background
        return record

    def apply_bundle(self, record):
        from .planner import resolve_calibration_from_bundle, resolve_operating_settings
        evidence = resolve_calibration_from_bundle(record["manifest"])
        settings = RepeatedRapidScanSettings.from_dict(self.read_settings())
        background = record.get("background")
        if background is not None and background.condition_id != settings.condition_id:
            raise ValueError("Promoted path-balance background condition does not match the selected condition")
        selected = resolve_operating_settings(settings, promoted_bundle=asdict(evidence),
                                               installed_readbacks=asdict(self.capabilities) if self.capabilities else {})
        self.calibration = evidence
        self.session.background = background
        section = record["manifest"]["repeated_rapid_scan"]
        selected_record = {key: value for key, value in record.items() if key != "background"}
        if background is not None:
            selected_record["background_record_id"] = background.record_id
        self.session.calibration_records = [{**selected_record, "device_configuration": deepcopy(section.get("device_configuration", {}))}]
        self.apply_settings(selected.settings.to_dict())

    def apply_capabilities(self, result):
        from .planner import HardwareCapabilities
        value = result.get("capabilities")
        if value is not None:
            self.capabilities = value if isinstance(value, HardwareCapabilities) else HardwareCapabilities(**value)

    def new_run(self):
        retained = getattr(self.runner, "last_result", None)
        if retained and retained.get("status") == "preservation_failed" and not retained.get("recovered_to"):
            raise ValueError("Native data exist only in memory after storage failure. Save retained records before New run.")
        self.session.clear()
        self.runner = None

    def preserve_retained(self, snapshot, worker):
        from .persistence import save_run
        retained = getattr(self.runner, "last_result", None)
        if not retained:
            raise ValueError("No retained native record is awaiting preservation")
        record = deepcopy(retained)
        worker.check_cancelled()
        record.update(run_id=snapshot.run_id, source_run_id=retained["run_id"],
                      source_output_path=retained["output_path"], output_path=str(snapshot.output_path),
                      preservation_operation=snapshot.to_dict(), status="preserved_after_storage_failure")
        save_run(snapshot.output_path, record=record)
        retained["recovered_to"] = str(snapshot.output_path)
        return record

    def fit_record(self, snapshot, worker, result, movie_index, model):
        from .processing import fit_recovery_model
        from .persistence import save_run
        movie = result["processed"][movie_index]
        native = next(m for m in result["native_movies"] if m.movie_id == movie.movie_id)
        record = {"experiment_id": "repeated_rapid_scan", "schema_version": 1,
                  "kind": "analysis", "mode": self.context.mode, "run_id": snapshot.run_id,
                  "condition_id": movie.condition_id, "operation": snapshot.to_dict(),
                  "source_run_id": result.get("run_id"), "source_path": result.get("output_path"),
                  "native_movies": [native], "processed": [movie], "analysis_inputs": model,
                  "output_path": str(snapshot.output_path), "status": "partial"}
        error = None
        try:
            worker.check_cancelled()
            worker.message.emit("Analysis: apparent recovery on actual native time/wavelength with identified scan/filter kernel")
            record["fit_analysis"] = fit_recovery_model(native, movie, model, cancelled=worker.cancel_event.is_set)
            record["status"] = "complete"
        except BaseException as exc:
            record["status"] = "cancelled" if isinstance(exc, InterruptedError) else "failed"
            record["error"] = str(exc)
            error = exc
        finally:
            save_run(snapshot.output_path, record=record)
        if error:
            raise error
        return record
