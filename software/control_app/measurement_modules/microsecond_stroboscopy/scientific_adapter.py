"""Module-owned acquisition callbacks for the compact host presentation API.

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
    def __init__(self, context, settings_widget, *, runner=None, hardware=True):
        self.context, self.settings_widget = context, settings_widget
        self.runner = runner
        self._hardware = bool(hardware)
        self.blank = None
        self.retained_preliminary = None
        self.last_record = None
        self.capabilities = None
        self.qualification = None
        self.calibration_records = ()
        self.sample_records = ()
        self.instrument_changes = []
        self._instrument_original = {}
        self._instrument_actual = {}
        self._active_worker = None

    def read_settings(self):
        return self.settings_widget.read_settings()

    def read_operation_settings(self, kind):
        # Capability checks and storage rescue remain available while an
        # acquisition text field is temporarily incomplete or invalid.
        return {"experiment_id": "microsecond_stroboscopy", "mode": self.context.mode,
                "operation_kind": str(kind)}

    def apply_settings(self, settings):
        self.settings_widget.apply_settings(plain(settings))

    def make_plan(self, settings):
        from .settings import StroboscopySettings
        from .planner import build_plan
        requested = StroboscopySettings.from_dict(setting_values(settings))
        if requested.mode != self.context.mode:
            raise ValueError("Plan detector mode differs from this tab")
        return build_plan(requested, capabilities=self.capabilities, qualification=self.qualification)

    def validate_plan(self, plan):
        readiness = plain(getattr(plan, "readiness", {}))
        # Capacity applies to each action's own acquisition. A large Sample
        # request must not disable a small unpumped preliminary measurement.
        issues = readiness.get("issues", ()) if isinstance(readiness, dict) else ()
        errors = [issue["message"] for issue in issues if issue.get("severity") == "error"
                  and issue.get("code") not in ("memory_budget", "storage_budget")]
        return tuple(errors)

    def summarize_plan(self, plan):
        data = plain(plan)
        budget = plain(getattr(plan, "budget", data.get("budget", {})))
        settings = plain(plan.settings)
        count = len(settings.get("spectral_points", ()))
        delays = settings.get("delays_us", ())
        averages = settings.get("averages", 1)
        response = settings["response"]
        return (
            ("Acquisition", f"{count} wavenumbers × {len(delays)} delays × {averages}"),
            ("Delay range", f"{min(delays):g} – {max(delays):g} µs" if delays else "—"),
            ("HF2 response", f"Order {response['hf2_order']} · {response['hf2_time_constant_s'] * 1e6:g} µs"),
            ("Sample rate", f"{response['sample_rate_sps'] / 1000:g} kSa/s"),
            ("Estimated time", f"{budget.get('wall_clock_s', 0):,.1f} s"),
            ("Estimated memory", f"{budget.get('memory_bytes', 0)/1024**3:,.2f} / {settings['budget']['maximum_memory_bytes']/1024**3:g} GiB limit"),
            ("Native storage", f"{budget.get('storage_bytes', 0)/1024**2:,.1f} MiB"),
            ("Delay reference", "Electrical Variable Sync"),
        )

    def selected_records(self):
        return ScientificSelections(calibration_records=deepcopy(self.calibration_records),
                                    sample_records=deepcopy(self.sample_records))

    def hardware_required(self, kind, settings):
        # Loading an old simulation plan must never silently select a simulator.
        # Offline acquisition requires explicit developer construction/injection.
        return self._hardware and kind not in ("retry_native_save", "retry_preservation")

    def compatibility(self, plan, *, kind=None):
        from .planner import acquisition_signature
        return {
            "experiment_id": "microsecond_stroboscopy",
            "mode": self.context.mode,
            "settings": acquisition_signature(plan.settings, kind=kind),
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
        if record.get("errors"):
            errors.append("Selected record retains unresolved acquisition errors: " + "; ".join(map(str, record["errors"])))
        if kind in ("blank", "preliminary") and plan is not None:
            points = record.get("processing", {}).get("points", [])
            valid_waves = {point.get("wavenumber_cm1") for point in points if point.get("valid")}
            needed_waves = {point.wavenumber_cm1 for point in plan.settings.spectral_points}
            if not needed_waves.issubset(valid_waves):
                errors.append("Selected record lacks valid native support at the requested wavenumbers.")
        expected = self.compatibility(plan, kind=kind)
        actual = record.get("compatibility")
        if actual is None:
            # Native v1 records retain full settings even when they predate the
            # compact panel's explicit compatibility entry.
            from .planner import acquisition_signature
            try:
                actual = {"experiment_id": record["experiment_id"], "mode": record["mode"],
                          "settings": acquisition_signature(record["settings"], kind=kind), "instrument_state": {}}
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f"Selected record lacks acquisition settings: {exc}")
        if actual is not None:
            from .planner import acquisition_signature
            actual = {key: deepcopy(value) for key, value in actual.items()
                      if key in ("experiment_id", "mode", "settings", "instrument_state")}
            if "settings" in actual:
                actual["settings"] = acquisition_signature(actual["settings"], kind=kind)
            actual.setdefault("instrument_state", {})
            # The event's explicit previous value supplies the previously
            # unobserved state of records retained before that first event.
            for key, value in self._instrument_original.items():
                actual["instrument_state"].setdefault(key, value)
            if kind in ("blank","preliminary"):
                # Keep a candidate until acquisition can compare the actual SDK
                # optical width at each wavelength. This plan is only a request.
                for entry in (expected,actual):
                    entry.get("settings",{}).get("timing",{}).pop("mircat_pulse_width_ns",None)
            errors.extend(compatibility_mismatches(expected, actual))
        return errors

    def validate_preliminary(self, preliminary, plan):
        # Each run measures its own unpumped baseline. Compatible earlier data
        # are optional; absent or stale data never become an approval gate.
        return ()

    def validate_operation(self, kind, plan, preliminary):
        if kind in ("save_plan", "load_plan", "load_run", "export", "retry_preservation", "retry_native_save", "check_capabilities"):
            if kind != "check_capabilities":
                return ()
        if self._hardware:
            required = {"hf2li"} if kind == "check_capabilities" else {"hf2li", "mircat", "t660_1", "t660_2"}
            if kind in ("save_plan", "load_plan", "load_run", "export", "retry_preservation", "retry_native_save"):
                return ()
            missing = required - set(self.context.devices.available(hardware=True))
            if missing:
                return ("Device service unavailable: " + ", ".join(sorted(missing)),)
        if kind in ("blank", "preliminary", "measurement", "run") and plan is not None:
            from .planner import build_plan
            scoped = build_plan(plan.settings, capabilities=self.capabilities, qualification=self.qualification,
                                kind="run" if kind == "measurement" else kind)
            return scoped.readiness.errors
        return ()

    def reusable(self, record, plan, *, kind):
        try:
            return record if isinstance(record, dict) and not self.validate_record(record, plan, kind=kind) else None
        except (ValueError, TypeError, KeyError, AttributeError):
            # A malformed optional old reference cannot strand a newly owned
            # acquisition before the runner establishes cleanup/preservation.
            return None

    def reuse_records(self, record, plan=None):
        """Retain acquired or loaded candidates; compatibility is checked at use."""
        if not isinstance(record, dict):
            return
        if record.get("kind") == "blank":
            self.blank = record
        elif record.get("kind") == "preliminary":
            self.retained_preliminary = record
        if isinstance(record.get("blank"), dict):
            self.blank = record["blank"]
        elif isinstance(record.get("blank_record"), dict):
            self.blank = record["blank_record"]
        if isinstance(record.get("preliminary"), dict):
            self.retained_preliminary = record["preliminary"]

    def _execute(self, snapshot, worker, kind):
        self._active_worker = worker
        self.last_record = None
        try:
            from .runner import run_acquisition
            from .persistence import save_run
            from .processing import process_run
            compatibility = self.compatibility(snapshot.plan, kind=kind)
            blank = self.reusable(self.blank, snapshot.plan, kind="blank")
            preliminary = self.reusable(snapshot.preliminary, snapshot.plan, kind="preliminary")
            if preliminary is None:
                preliminary = self.reusable(self.retained_preliminary, snapshot.plan, kind="preliminary")
        except Exception:
            # No device or new native data exists before runner dispatch.
            self._active_worker = None
            if snapshot.operation.hardware:
                self.context.ownership.release(snapshot.operation.ownership, safe_verified=True,
                    preservation_verified=True, detail="Adapter setup failed before device access")
            raise

        def progress(message):
            worker.message.emit(message)
            upload = re.search(r"Timing-table upload: (\d+)/(\d+) acknowledged", message)
            if upload:
                worker.progress.emit(int(upload.group(1)), int(upload.group(2)))
            else:
                worker.progress.emit(0, 0)

        def preserve(record):
            from .planner import acquisition_signature
            record["compatibility"] = deepcopy(compatibility)
            if record.get("settings"):
                record["compatibility"]["settings"] = acquisition_signature(record["settings"], kind=kind)
            self.last_record = record
            if record.get("disposition", record.get("status")) in ("complete", "completed") and not worker.cancel_event.is_set():
                worker.message.emit("Reconstructing measurements…")
                try:
                    record["processing"] = process_run(record, check_cancelled=worker.check_cancelled)
                except InterruptedError:
                    record["analysis_status"] = "interrupted"
                except Exception as exc:
                    record["analysis_error"] = f"{type(exc).__name__}: {exc}"
            worker.message.emit("Saving native data…")
            path = save_run(snapshot.operation.output_path, record)
            record["native_path"] = str(path)
            return path

        try:
            record = (self.runner or run_acquisition)(
                self.context, snapshot.operation, snapshot.plan, kind=kind,
                cancel=worker.cancel_event.is_set, progress=progress,
                preserve=preserve, preliminary=preliminary, blank=blank,
            )
            self.last_record = record
            self.reuse_records(record)
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
        record = load_run(path, mode=self.context.mode)
        if "processing" not in record:
            from .processing import process_run
            try:
                record["processing"] = process_run(record, fit_models=False)
            except Exception as exc:
                record["analysis_error"] = f"{type(exc).__name__}: {exc}"
        self.reuse_records(record)
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
        # Preserve compatible acquired/loaded reference candidates across runs.
        self.last_record = None

    def instrument_state_changed(self, change):
        for item in change.changes:
            key = f"{item.device_id}.{item.configuration_key}"
            self._instrument_original.setdefault(key, item.previous_value)
            self._instrument_actual[key] = item.new_value
        self.instrument_changes = [
            f"Instrument {key}: record {previous!r}; current {self._instrument_actual[key]!r}; "
            "retained reference data will be rechecked."
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
