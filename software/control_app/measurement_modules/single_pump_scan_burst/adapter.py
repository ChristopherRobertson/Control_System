"""Experiment-specific data adapter for the shared compact measurement panel."""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import fields
import json
from pathlib import Path
from threading import Lock

from control_app.measurement_host.presentation import ScientificSelections
from .persistence import RunStore, compatibility_conflicts, json_value, load_run, write_json


class BurstScientificAdapter:
    def __init__(self, context, settings_widget, *, runner_factory=None, hardware=True):
        self.context, self.settings_widget = context, settings_widget
        self.runner_factory, self.hardware = runner_factory, bool(hardware)
        self.blank = self.capabilities = None
        self.calibration_records = ()
        self.sample_selection = None
        self._preliminary_records = deque(maxlen=8)
        self._runner = None
        self._runner_lock = Lock()
        self._settings_cache = {}

    def read_settings(self):
        result = self.settings_widget.read_settings()
        self._settings_cache = deepcopy(result)
        return result

    def read_operation_settings(self, kind):
        if kind == "capabilities":
            from .settings import Settings
            return Settings(mode=self.context.mode).to_dict()
        return self.read_settings()

    def apply_settings(self, settings):
        if settings.get("mode", self.context.mode) != self.context.mode:
            raise ValueError("Choose a plan saved from this detector mode.")
        self.settings_widget.apply_settings(settings)

    def make_plan(self, settings):
        from .planner import compile_plan
        from .settings import Settings
        names = {field.name for field in fields(Settings)}
        requested = Settings.from_dict({key: value for key, value in settings.items() if key in names})
        return compile_plan(requested, self.capabilities)

    def validate_plan(self, plan):
        messages = []
        limit = min(.30, plan.capabilities.probe_duty_max)
        for error in plan.errors:
            if "internal rate" in error and "duty limit" in error:
                error = f"Shorten Pulse width: the laser's internal pulse duty would exceed {limit:.0%}."
            elif "repetition rate" in error and "duty limit" in error:
                error = f"Reduce Repetition rate or Pulse width: emitted pulse duty would exceed {limit:.0%}."
            if error not in messages:
                messages.append(error)
        return tuple(messages)

    def summarize_plan(self, plan):
        if not plan.valid:
            return (("Plan", "Check the highlighted settings"),)
        settings, estimates = plan.settings, plan.estimates
        def duration(value):
            if value is None:
                return "Automatic"
            if value < 1:
                scale, unit = (1e9, "ns") if value < 1e-6 else (1e6, "µs") if value < 1e-3 else (1e3, "ms")
                return f"{value * scale:.4g} {unit}"
            if value < 60:
                return f"{value:.4g} s"
            seconds = round(value)
            minutes, seconds = divmod(seconds, 60)
            if minutes < 60:
                return f"{minutes} min" + (f" {seconds} s" if seconds else "")
            hours, minutes = divmod(minutes, 60)
            return f"{hours} h" + (f" {minutes} min" if minutes else "")
        rates = f"{settings.sample_rate_hz / 1000:.4g}"
        if self.context.mode == "dual":
            rates += f" / {settings.reference_rate_hz / 1000:.4g}"
        rates += " kSa/s"
        size = estimates.get("native_bytes", 0)
        data = f"{size / 1e9:.3g} GB" if size >= 1e9 else f"{size / 1e6:.3g} MB"
        return (("Scan time", duration(estimates.get("scan_duration_s"))),
                ("Early scans", str(settings.early_scan_count)),
                ("Later bursts", f"{settings.later_burst_count} × {settings.scans_per_burst} scans"),
                ("Observation", duration(settings.observation_limit_s)),
                ("HF2LI rate", rates),
                ("Pulse duty", f"{settings.probe_rate_hz * settings.probe_pulse_width_s * 100:.3g}% emitted / "
                    f"{settings.mircat_internal_pulse_rate_hz * settings.probe_pulse_width_s * 100:.3g}% internal (max {min(.30, plan.capabilities.probe_duty_max) * 100:g}%)"),
                ("Estimated data", data),
                ("Total time", "≈" + duration(estimates.get("wall_time_min_s"))))

    def selected_records(self):
        samples = (deepcopy(self.sample_selection),) if self.sample_selection else ()
        return ScientificSelections(tuple(self.calibration_records), samples)

    def hardware_required(self, kind, settings):
        # Simulation is an injected development/test dependency, never a normal
        # operator mode and never selected by loading a saved settings file.
        return self.hardware and kind in {"baseline", "preliminary", "measurement", "capabilities"}

    def _identity(self, plan):
        from .acquisition import acquisition_identity
        return acquisition_identity(plan.settings)

    def _record_identity(self, record):
        from .acquisition import acquisition_identity
        metadata = record.get("metadata", {})
        settings = record.get("actual_settings", metadata.get("actual_settings", metadata.get("settings", {})))
        if not settings and record.get("compatibility"):
            compatibility = record["compatibility"]
            settings = compatibility.get("settings", compatibility)
        return acquisition_identity(settings)

    def _record_conflicts(self, record, plan, label):
        if not record or not record.get("complete"):
            return ["Acquire or load an unpumped sample." if label == "sample" else f"Acquire or load a completed {label}."]
        saved, requested = self._record_identity(record), self._identity(plan)
        conflicts = [name for name in requested if saved.get(name) is not None and requested[name] is not None and saved[name] != requested[name]]
        if conflicts:
            field = conflicts[0].replace("_", " ")
            return [f"{label.capitalize()} differs: {field}. Reacquire it or restore the matching setting."]
        return []

    def blank_conflicts(self, plan):
        return [] if self.context.mode == "dual" else self._record_conflicts(self.blank, plan, "blank")

    def validate_preliminary(self, preliminary, plan):
        return tuple(self._record_conflicts(preliminary, plan, "sample"))

    def validate_operation(self, kind, plan, preliminary):
        if kind == "preliminary":
            return ()
        if kind == "measurement":
            return self.validate_preliminary(preliminary, plan)
        return ()

    def retain_preliminary(self, result):
        self._preliminary_records.append(result)

    def compatible_preliminary(self, plan):
        return next((record for record in reversed(self._preliminary_records)
                     if not self.validate_preliminary(record, plan)), None)

    def summarize_preliminary(self, result):
        return "Sample/reference baseline ready." if self.context.mode == "dual" else "Sample baseline ready."

    @staticmethod
    def _record_reference(record):
        if record is None:
            return None
        return {key: deepcopy(record[key]) for key in ("complete", "metadata", "actual_settings", "output_path", "native_paths", "compatibility") if key in record}

    @staticmethod
    def _raise_failed_outcome(result, path):
        if result.get("cleanup_errors") or result.get("status") in ("cleanup_failed", "preservation_failed"):
            raise RuntimeError("Restoration or saving failed: " + "; ".join(result.get("cleanup_errors", ())))
        if result.get("status") in ("stopped", "cancelled", "aborted"):
            raise InterruptedError("Acquisition stopped. Partial data saved.")
        if result.get("status") in ("failed", "incomplete"):
            raise RuntimeError(str(result.get("error", "Acquisition incomplete")))

    @staticmethod
    def _with_display(result):
        # Native reads and bounded display preparation happen in a host worker.
        from .widgets import _display_points
        path = result.get("output_path", result.get("path"))
        if path and "events" not in result:
            retained = load_run(path)
            result["events"], result["chunks"] = retained["events"], retained["chunks"]
            result.setdefault("metadata", retained["metadata"])
            result.setdefault("manifest", retained["manifest"])
        if path:
            actual_path = Path(path) / "records" / "actual-settings.json"
            if actual_path.is_file():
                actual = json.loads(actual_path.read_text(encoding="utf-8"))
                result["actual_settings"] = actual["settings"]
                result["metadata"] = {**result.get("metadata", {}), "actual_settings": actual["settings"]}
                result.setdefault("capabilities", actual.get("capabilities"))
        result["display_points"] = _display_points(result)
        if path:
            result["native_display_points"] = _display_points({**result, "data": {}, "native": None}, native_only=True)
        return result

    def _execute(self, snapshot, worker, *, preparation=None):
        from .runner import BurstRunner
        store = runner = None
        def progress(update):
            text = str(update.get("message", update.get("stage", "Acquiring")))
            if update.get("next_burst_s") is not None:
                text = f"Next burst in {update['next_burst_s']:.3g} s"
            if update.get("scan_count") is not None:
                text += f" · {update['scan_count']} scans"
            if update.get("elapsed_s") is not None:
                text += f" · {update['elapsed_s']:.1f} s elapsed"
            if update.get("remaining_s") is not None:
                text += f" · ≈{update['remaining_s']:.1f} s left"
            worker.message.emit(text)
            if update.get("fraction") is not None:
                worker.progress.emit(round(max(0., min(1., update["fraction"])) * 1000), 1000)
        try:
            plan = snapshot.plan if snapshot.plan is not None else self.make_plan(snapshot.settings)
            metadata = {"mode": self.context.mode, "condition_id": plan.settings.condition_id,
                "operation": snapshot.operation.to_dict(), "settings": plan.settings.to_dict(),
                "plan": json_value(plan), "kind": preparation or "measurement", "compatibility": self._identity(plan)}
            store = RunStore(snapshot.operation.output_path, metadata)
            factory = self.runner_factory or BurstRunner
            runner = factory(self.context, plan, snapshot.operation, store=store, progress=progress)
            with self._runner_lock:
                self._runner = runner
            if worker.cancel_event.is_set():
                runner.cancel("Stopped before preparation")
            if preparation:
                result = json_value(runner.prepare(kind=preparation))
            else:
                preliminary = snapshot.preliminary or {}
                baseline = {"preliminary": self._record_reference(preliminary),
                            "blank": self._record_reference(preliminary.get("_dispatch_blank"))}
                result = json_value(runner.run(baseline=baseline))
            self._raise_failed_outcome(result, snapshot.operation.output_path)
            result.setdefault("output_path", str(snapshot.operation.output_path))
            result.setdefault("metadata", metadata)
            result["preparation_kind"] = preparation
            return result if preparation == "capabilities" else self._with_display(result)
        except BaseException:
            if runner is None and snapshot.operation.hardware:
                self.context.ownership.release(snapshot.operation.ownership, safe_verified=True,
                    preservation_verified=store is not None, detail="Operation failed before device construction")
            raise
        finally:
            with self._runner_lock:
                if self._runner is runner:
                    self._runner = None

    def run_preliminary(self, snapshot, worker):
        return self._execute(snapshot, worker, preparation="preliminary")

    def run_measurement(self, snapshot, worker):
        return self._execute(snapshot, worker)

    def run_blank(self, snapshot, worker):
        return self._execute(snapshot, worker, preparation="baseline")

    def run_capabilities(self, snapshot, worker):
        return self._execute(snapshot, worker, preparation="capabilities")

    def request_abort(self, reason):
        with self._runner_lock:
            runner = self._runner
        if runner is not None:
            runner.cancel(reason)

    def save_plan(self, path, settings, plan):
        write_json(Path(path), {"schema_version": "single-pump-scan-burst-plan/1", "experiment_id": self.context.experiment_id,
            "mode": self.context.mode, "settings": self.settings_widget.normalize_settings(settings), "compiled_preview": json_value(plan)})

    def load_plan(self, path):
        record = json.loads(Path(path).read_text(encoding="utf-8"))
        if record.get("schema_version") != "single-pump-scan-burst-plan/1" or record.get("experiment_id") != self.context.experiment_id:
            raise ValueError("Choose a single-pump scan-burst plan.")
        if record.get("mode") != self.context.mode:
            raise ValueError("Choose a plan saved from this detector mode.")
        settings = self.settings_widget.normalize_settings(record["settings"])
        self.make_plan(settings)
        return settings

    def load_run(self, path):
        return self._with_display(load_run(path, expected_mode=self.context.mode))

    def load_blank(self, path, plan):
        if self.context.mode != "single":
            raise ValueError("The reference detector records the blank simultaneously.")
        run = load_run(path, expected_mode=self.context.mode)
        if run["metadata"].get("kind") != "baseline" or run["status"] not in ("complete", "completed"):
            raise ValueError("Choose a completed blank run.")
        record = {"complete": True, "output_path": str(path), "metadata": run["metadata"], "native_paths": run["chunks"]}
        actual_path = Path(path) / "records" / "actual-settings.json"
        if actual_path.is_file():
            actual = json.loads(actual_path.read_text(encoding="utf-8"))
            record["actual_settings"] = actual["settings"]
            record["metadata"] = {**record["metadata"], "actual_settings": actual["settings"]}
        errors = self._record_conflicts(record, plan, "blank")
        if errors:
            raise ValueError(errors[0])
        return self._with_display(record)

    def export_run(self, path, result):
        """Stream all retained quantitative points, excluding display sampling."""
        import csv
        import os
        import numpy as np
        from .persistence import iter_chunks
        root = result.get("output_path", result.get("path"))
        if not root:
            raise ValueError("A retained native run is required for quantitative export")
        retained = load_run(root, expected_mode=self.context.mode)
        processed = any(Path(name).name.startswith("processed-") for name in retained["chunks"])
        with Path(path).open("x", encoding="utf-8", newline="") as stream:
            output = csv.writer(stream)
            output.writerow(("time_s", "wavenumber_cm1", "sample", "reference", "Q_or_transmission", "delta_absorbance",
                             "absolute_absorbance_if_applicable", "variance", "valid", "quality_flags", "scan_index", "direction"))
            for block in iter_chunks(root):
                if processed and "delta_absorbance" not in block:
                    continue
                if "wavenumber_cm1" not in block:
                    continue
                n = len(np.asarray(block["wavenumber_cm1"]).reshape(-1))
                arrays = []
                for key in ("time_s", "wavenumber_cm1", "sample", "reference", "ratio", "delta_absorbance", "absorbance", "variance", "valid", "quality_flags", "scan_index", "direction"):
                    value = block.get(key, block.get("sample_time_s") if key == "time_s" else None)
                    array = np.asarray(value) if value is not None else np.full(n, "")
                    arrays.append(np.full(n, array.item()) if array.ndim == 0 else array.reshape(-1))
                for index in range(n):
                    output.writerow(array[index] if index < len(array) else "" for array in arrays)
            stream.flush()
            os.fsync(stream.fileno())

    def new_run(self):
        self.blank = None
        self._preliminary_records.clear()


ScientificAdapter = BurstScientificAdapter
