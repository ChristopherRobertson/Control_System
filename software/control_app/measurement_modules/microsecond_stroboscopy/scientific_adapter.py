"""Module-owned science/review callbacks for the frozen host presentation API.

Only explicit worker operations construct devices. Compatibility compares named
scientific values, never digests, run UUIDs, or discovery timestamps.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
import json
import re
from pathlib import Path
from typing import Mapping

from control_app.measurement_host.presentation import ScientificSelections


def plain(value):
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


def setting_values(value):
    return {key: item for key, item in plain(value).items() if not key.startswith("_")}


def compatibility_mismatches(expected, actual, prefix=""):
    """Describe each changed explicit value; stable IDs are useful provenance."""
    expected, actual = plain(expected), plain(actual)
    if isinstance(expected, dict) and isinstance(actual, dict):
        result = []
        for key in sorted(set(expected) | set(actual)):
            name = f"{prefix}.{key}" if prefix else key
            if key not in actual:
                result.append(f"{name}: missing from selected record")
            elif key not in expected:
                result.append(f"{name}: absent from current settings")
            else:
                result.extend(compatibility_mismatches(expected[key], actual[key], name))
        return result
    if expected != actual:
        return [f"{prefix}: current {expected!r}; record {actual!r}"]
    return []


class MicrosecondScientificAdapter:
    def __init__(self, context, settings_widget, *, runner=None):
        self.context, self.settings_widget = context, settings_widget
        self.runner = runner
        self.blank = None
        self.last_record = None
        self.capabilities = None
        self.qualification = None
        self.calibration_records = ()
        self.sample_records = ()
        self.instrument_changes = []
        self._instrument_original = {}
        self._instrument_actual = {}
        self._condition_profile_id = settings_widget._base["condition_profile_id"]
        self._active_worker = None

    def read_settings(self):
        return self.settings_widget.read_settings()

    def apply_settings(self, settings):
        self.settings_widget.apply_settings(plain(settings))

    def make_plan(self, settings):
        from .settings import StroboscopySettings
        from .planner import build_plan
        requested = StroboscopySettings.from_dict(setting_values(settings))
        if requested.mode != self.context.mode:
            raise ValueError("Plan detector mode differs from this tab")
        self._condition_profile_id = requested.condition_profile_id
        return build_plan(requested, capabilities=self.capabilities, qualification=self.qualification)

    def validate_plan(self, plan):
        from control_app.measurement_host.interchange import sample_selection_from_dict
        readiness = plain(getattr(plan, "readiness", {}))
        errors = list(readiness.get("errors", ())) if isinstance(readiness, dict) else []
        settings = plan.settings
        if self.sample_records:
            matching = [plain(record) for record in self.sample_records
                        if isinstance(plain(record), Mapping)
                        and plain(record).get("selection_id") == settings.identity.sample_selection_id]
            if len(matching) != 1:
                errors.append("The named sample_selection_id must select exactly one retained accepted sample spectral selection.")
            else:
                try:
                    selection = sample_selection_from_dict(matching[0])
                except (ValueError, TypeError) as exc:
                    errors.append(f"Selected sample spectral record is invalid: {exc}")
                else:
                    if selection.sample_id != settings.identity.sample_id:
                        errors.append("Selected sample spectral record sample_id differs from the entered sample.")
                    if selection.condition_id != settings.identity.condition_id:
                        errors.append("Selected sample spectral record condition_id differs from the entered condition.")
                    outside = [point.wavenumber_cm1 for point in settings.spectral_points
                               if point.role == "band" and not any(window.lower_cm1 <= point.wavenumber_cm1 <= window.upper_cm1
                                                                   for window in selection.windows)]
                    if outside:
                        errors.append("Band coordinates outside accepted sample windows (cm⁻¹): " + ", ".join(f"{value:g}" for value in outside))
        elif settings.execution_mode == "hardware":
            errors.append("Load the retained accepted sample spectral selection; a sample_selection_id alone is not a record.")
        return tuple(errors)

    def summarize_plan(self, plan):
        data = plain(plan)
        budget = plain(getattr(plan, "budget", data.get("budget", {})))
        settings = plain(plan.settings)
        count = len(settings.get("spectral_points", ()))
        delays = settings.get("delays_us", ())
        averages = settings.get("averages", 1)
        rows = [f"{count} wavenumbers × {len(delays)} delays × {averages} averages",
                "Complete delay/reset series at each wavenumber before tuning onward."]
        if delays:
            rows.append(f"Requested coverage {min(delays):g} to {max(delays):g} µs; grid spacing is not the response resolution.")
        rows.append(f"Budget: {budget.get('event_count', 0):,} pump events; "
                    f"{budget.get('total_block_count', 0):,} blocks; {budget.get('total_frame_count', 0):,} timing frames.")
        rows.append(f"Wall clock {budget.get('wall_clock_s', 0):,.1f} s; "
                    f"upload {budget.get('upload_s', 0):,.1f} s; recovery {budget.get('recovery_s', 0):,.1f} s.")
        rows.append(f"Memory {budget.get('memory_bytes', 0)/1024**2:,.1f} MiB; "
                    f"native storage {budget.get('storage_bytes', 0)/1024**2:,.1f} MiB.")
        rows.append(str(budget.get("estimate_basis", "")))
        readiness = plain(getattr(plan, "readiness", {}))
        if isinstance(readiness, dict):
            for name in ("warnings", "blockers", "missing", "commissioning_items"):
                items = readiness.get(name, ())
                if items:
                    rows.append(name.replace("_", " ").capitalize() + ": " + "; ".join(map(str, items)))
        elif isinstance(readiness, (list, tuple)):
            rows.extend(map(str, readiness))
        return "\n".join(rows)

    def selected_records(self):
        return ScientificSelections(calibration_records=deepcopy(self.calibration_records),
                                    sample_records=deepcopy(self.sample_records))

    def hardware_required(self, kind, settings):
        return settings.get("execution_mode", "simulation") == "hardware"

    def compatibility(self, plan):
        return {
            "experiment_id": "microsecond_stroboscopy",
            "mode": self.context.mode,
            "settings": setting_values(plan.settings),
            "calibrations": [plain(record) for record in self.calibration_records],
            "sample_selections": [plain(record) for record in self.sample_records],
            "instrument_state": deepcopy(self._instrument_actual),
        }

    def validate_record(self, record, plan, *, kind=None):
        errors = []
        if not isinstance(record, dict):
            return ["No compatible completed native record is selected."]
        if record.get("experiment_id") != "microsecond_stroboscopy":
            errors.append("Selected record belongs to a different experiment.")
        if record.get("mode") != self.context.mode:
            errors.append("Selected record belongs to the other detector mode.")
        if kind is not None and record.get("kind") != kind:
            errors.append(f"Select a {kind} record, not {record.get('kind', 'an unspecified record')}.")
        status = record.get("status", record.get("disposition"))
        if status not in ("completed", "complete", "accepted"):
            errors.append(f"Selected record is {status!r}; completed acquisition is required.")
        if record.get("analysis_error") or record.get("analysis_status") == "interrupted":
            errors.append("Selected record has incomplete analysis; complete scientific review is unavailable.")
        if record.get("restoration", {}).get("safe_verified") is not True:
            errors.append("Selected record does not verify instrument restoration.")
        if record.get("errors"):
            errors.append("Selected record retains unresolved acquisition errors: " + "; ".join(map(str, record["errors"])))
        if kind in ("blank", "preliminary") and plan is not None:
            points = record.get("processing", {}).get("points", [])
            valid_waves = {point.get("wavenumber_cm1") for point in points if point.get("valid")}
            needed_waves = {point.wavenumber_cm1 for point in plan.settings.spectral_points}
            if not needed_waves.issubset(valid_waves):
                errors.append("Selected record lacks valid native review support at every declared wavenumber.")
            if kind == "blank":
                schedule = {(float(block["wavenumber_cm1"]), round(float(block.get("delay_s", 0)) * 1e6, 9), block.get("average_index"))
                            for block in record.get("native_blocks", ()) if block.get("kind") == "blank_control" and block.get("completed_utc")
                            and block.get("sample") and not block.get("flags")}
                expected_schedule = {(wave, round(delay, 9), average) for wave in needed_waves
                                     for delay in plan.settings.delays_us for average in range(plan.settings.averages)}
                if not expected_schedule.issubset(schedule):
                    errors.append("Sequential blank is missing declared delay/average control blocks.")
        expected = self.compatibility(plan)
        actual = record.get("compatibility")
        if actual is None:
            errors.append("Selected record lacks explicit baseline/review compatibility provenance.")
        else:
            actual = deepcopy(actual)
            actual.setdefault("instrument_state", {})
            # The event's explicit previous value supplies the previously
            # unobserved state of records retained before that first event.
            for key, value in self._instrument_original.items():
                actual["instrument_state"].setdefault(key, value)
            errors.extend(compatibility_mismatches(expected, actual))
        return errors

    def validate_review(self, preliminary, plan):
        errors = self.validate_record(preliminary, plan, kind="preliminary")
        if self.context.mode == "single":
            errors.extend("Blank: " + text for text in self.validate_record(self.blank, plan, kind="blank"))
        return errors

    def summarize_preliminary(self, result):
        label = "simultaneous sample/reference Q₀" if self.context.mode == "dual" else "sample with sequential blank"
        return (f"Review unpumped {label}; record {result.get('run_id', 'retained')}. "
                "Check measured support, detector flags, sample identity, and spectrum before explicit Start. "
                "Physical sample/reference loading is an operator action.")

    def _execute(self, snapshot, worker, kind):
        from .runner import run_acquisition
        from .persistence import save_run
        from .processing import process_run
        self._active_worker = worker
        self.last_record = None
        compatibility = self.compatibility(snapshot.plan)
        blank = deepcopy(self.blank)

        def progress(message):
            worker.message.emit(message)
            upload = re.search(r"Timing-table upload: (\d+)/(\d+) acknowledged", message)
            if upload:
                worker.progress.emit(int(upload.group(1)), int(upload.group(2)))
            else:
                worker.progress.emit(0, 0)

        def preserve(record):
            record["compatibility"] = deepcopy(compatibility)
            self.last_record = record
            if record.get("disposition", record.get("status")) in ("complete", "completed") and not worker.cancel_event.is_set():
                worker.message.emit("Analysis: response-aware reconstruction and coverage; preserving native data.")
                try:
                    record["processing"] = process_run(record, check_cancelled=worker.check_cancelled)
                except InterruptedError:
                    record["analysis_status"] = "interrupted"
                except Exception as exc:
                    record["analysis_error"] = f"{type(exc).__name__}: {exc}"
            worker.message.emit("Saving native, rejected, interrupted and restoration records.")
            path = save_run(snapshot.operation.output_path, record)
            record["native_path"] = str(path)
            return path

        try:
            record = (self.runner or run_acquisition)(
                self.context, snapshot.operation, snapshot.plan, kind=kind,
                cancel=worker.cancel_event.is_set, progress=progress,
                preserve=preserve, preliminary=deepcopy(snapshot.preliminary), blank=blank,
            )
            self.last_record = record
            if record.get("analysis_error"):
                raise RuntimeError("Native data saved; analysis failed: " + record["analysis_error"])
            if worker.cancel_event.is_set() or record.get("status", record.get("disposition")) in ("interrupted", "cancelled", "stopped"):
                raise InterruptedError("Acquisition stopped. Native partial data and restoration records retained.")
            return record
        finally:
            self._active_worker = None

    def run_preliminary(self, snapshot, worker):
        return self._execute(snapshot, worker, "preliminary")

    def run_measurement(self, snapshot, worker):
        return self._execute(snapshot, worker, "run")

    def run_blank(self, snapshot, worker):
        if self.context.mode != "single":
            raise ValueError("Dual mode acquires sample and buffer reference simultaneously.")
        return self._execute(snapshot, worker, "blank")

    def request_abort(self, reason):
        if self._active_worker is not None:
            self._active_worker.request_abort(reason)

    def save_plan(self, path, settings, plan):
        from .persistence import save_plan
        return save_plan(path, settings)

    def load_plan(self, path):
        from .persistence import load_plan
        return plain(load_plan(path, mode=self.context.mode))

    def load_run(self, path):
        from .persistence import load_run
        record = load_run(path, mode=self.context.mode, condition_id=self._condition_profile_id)
        if "processing" not in record:
            from .processing import process_run
            try:
                record["processing"] = process_run(record, fit_models=False)
            except Exception as exc:
                record["analysis_error"] = f"{type(exc).__name__}: {exc}"
        return record

    def export_run(self, path, result):
        """Export explicit processed/native values; never overwrite a saved file."""
        import csv
        points = result.get("processing", {}).get("points", [])
        if not points:
            raise ValueError("No processed native points are available for export")
        keys = sorted({key for point in points for key in point})
        with Path(path).open("x", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=keys)
            writer.writeheader()
            for point in points:
                writer.writerow({key: json.dumps(plain(value)) if isinstance(value, (dict, list, tuple)) else value
                                 for key, value in point.items()})

    def new_run(self):
        self.blank = self.last_record = None

    def instrument_state_changed(self, change):
        for item in change.changes:
            key = f"{item.device_id}.{item.configuration_key}"
            self._instrument_original.setdefault(key, item.previous_value)
            self._instrument_actual[key] = item.new_value
        self.instrument_changes = [
            f"Instrument {key}: record {previous!r}; current {self._instrument_actual[key]!r}; "
            "recheck instruments and reacquire preliminary."
            for key, previous in self._instrument_original.items() if self._instrument_actual[key] != previous
        ]

    def acknowledge_instrument_check(self):
        # A capability menu/readback check is not a new sample baseline and
        # cannot erase a named instrument-state mismatch in a retained record.
        return None

    def load_qualified_bundle(self, bundle_id):
        """The host alone verifies promotion; an entered ID is never qualification."""
        from .planner import Qualification
        bundle = self.context.promoted_bundle(bundle_id)
        manifest = plain(bundle.manifest)
        profile = manifest.get("microsecond_stroboscopy", manifest.get("qualification", {}))
        self.qualification = Qualification.from_dict(profile)
        self.calibration_records = ({"bundle_id": bundle.bundle_id, "path": str(bundle.path),
                                     "qualification": plain(self.qualification)},)
        return self.qualification
