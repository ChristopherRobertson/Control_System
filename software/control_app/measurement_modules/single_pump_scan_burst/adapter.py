"""Scientific adapter for the frozen host's independent guided experiment tabs."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
import json
from pathlib import Path
from threading import Lock

from control_app.measurement_host.presentation import ScientificSelections
from .persistence import RunStore, compatibility_conflicts, json_value, load_run, write_json


class BurstScientificAdapter:
    def __init__(self, context, settings_widget, *, runner_factory=None):
        self.context, self.settings_widget = context, settings_widget
        self.blank = self.sample_selection = self.capabilities = None
        self.calibration_records = ()
        self.instrument_revision = 0
        self.instrument_changes = []
        self.preparation_kind = "preliminary"
        self.runner_factory = runner_factory
        self._runner = None
        self._runner_lock = Lock()
        self._settings_cache = {}
        self.continuation = None
        self.used_accepted_states = set(context.preferences.value("used_accepted_state_ids", ()))
        self.last_measurement_outcome = None

    def read_settings(self):
        settings = self.settings_widget.read_settings()
        self._settings_cache = deepcopy(settings)
        return settings

    def apply_settings(self, settings):
        if settings.get("mode", self.context.mode) != self.context.mode:
            raise ValueError("Plan detector mode does not match this tab")
        self.settings_widget.apply_settings(settings)

    def make_plan(self, settings):
        from .planner import compile_plan
        from .settings import Settings
        names = {item.name for item in fields(Settings)}
        return compile_plan(Settings.from_dict({k: v for k, v in settings.items() if k in names}), self.capabilities)

    def validate_plan(self, plan):
        return tuple(plan.errors)

    def summarize_plan(self, plan):
        if not plan.valid:
            return "Plan incomplete: enter explicit operating values and accepted cryogenic sample-state evidence."
        e, settings = plan.estimates, plan.settings
        def number(key, scale=1.):
            value = e.get(key)
            return "unresolved" if value is None else f"{value / scale:.6g}"
        return "\n".join((
            f"{settings.architecture_id} / {self.context.mode}: exactly one pump",
            f"{plan.total_scans} scans, {len(plan.blocks)} explicit blocks, {settings.observation_limit_s:g} s observation",
            f"Individual scan {number('scan_duration_s')} s; spacing {number('scan_interval_s')} s",
            f"Native estimate {number('native_bytes', 1e6)} MB; peak memory {number('peak_memory_bytes', 1e6)} MB",
            f"Wall time ≥{number('wall_time_min_s')} s including controls, preparation and processing",
            f"Probe pulse-on exposure {number('probe_pulse_on_s')} s; observed gaps remain gaps",
            f"{len(plan.readiness)} readiness items; inspect Plan details before connected acquisition",
        ))

    def selected_records(self):
        samples = (deepcopy(self.sample_selection),) if self.sample_selection else ()
        return ScientificSelections(tuple(self.calibration_records), samples)

    def hardware_required(self, kind, settings):
        return settings.get("_execution", "connected") == "connected"

    def _identity(self, plan):
        return {"experiment_id": self.context.experiment_id, "mode": self.context.mode,
                "settings": plan.settings.to_dict(), "instrument_revision": self.instrument_revision,
                "capabilities": json_value(self.capabilities), "sample_selection": json_value(self.sample_selection),
                "calibration_records": json_value(self.calibration_records)}

    def blank_conflicts(self, plan):
        if self.context.mode == "dual":
            return []
        if self.blank is None:
            return ["Acquire or load a complete compatible sequential blank/control record first."]
        if not self.blank.get("complete", False):
            return ["The selected blank is incomplete; rejected/interrupted records remain retained."]
        return compatibility_conflicts(self.blank.get("compatibility", {}), self._identity(plan), "Blank")

    def validate_review(self, preliminary, plan):
        errors = list(self.blank_conflicts(plan))
        if self.continuation is None and plan.settings.accepted_state_id in self.used_accepted_states:
            errors.append("This accepted sample state already has a pump record. Select an independently accepted new/equivalent state ID for a separately identified observation, or use explicit continuation.")
        if not preliminary or not preliminary.get("complete", False):
            errors.append("A completed unpumped sample preliminary is required.")
        if preliminary:
            errors.extend(compatibility_conflicts(preliminary.get("compatibility", {}), self._identity(plan), "Preliminary"))
        return errors

    def summarize_preliminary(self, result):
        quantity = "Sample/reference Q₀" if self.context.mode == "dual" else "Sample and sequential blank"
        return (f"{quantity}: inspect measured spectral support, clipping/lock flags, stationary spectra and temperature. "
                "Review approval is required before Start. No pump was requested in this preliminary acquisition.")

    @staticmethod
    def _record_reference(record):
        if record is None:
            return None
        return {key: deepcopy(record[key]) for key in ("complete", "metadata", "output_path", "native_paths", "compatibility") if key in record}

    @staticmethod
    def _raise_failed_outcome(result, path):
        if result.get("cleanup_errors") or result.get("status") in ("cleanup_failed", "preservation_failed"):
            raise RuntimeError("Restoration or preservation failed: " + "; ".join(result.get("cleanup_errors", ())) + "; retained at " + str(path))
        if result.get("status") in ("stopped", "cancelled", "aborted"):
            raise InterruptedError("Acquisition stopped; available native records were retained at " + str(path))
        if result.get("status") in ("failed", "incomplete"):
            raise RuntimeError(str(result.get("error", "Incomplete observation")) + "; retained at " + str(path))

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
        result["display_points"] = _display_points(result)
        if path:
            result["native_display_points"] = _display_points({**result, "data": {}, "native": None}, native_only=True)
        return result

    def _execute(self, snapshot, worker, *, preparation=None):
        from .runner import BurstRunner
        factory = self.runner_factory or BurstRunner
        store = runner = None
        if preparation is None:
            self.last_measurement_outcome = None
        metadata = {"mode": self.context.mode, "condition_id": snapshot.settings.get("condition_id"),
                    "operation": snapshot.operation.to_dict(), "settings": snapshot.plan.settings.to_dict(),
                    "plan": json_value(snapshot.plan), "kind": preparation or "measurement",
                    "compatibility": self._identity(snapshot.plan)}
        def progress(update):
            text = str(update.get("message", ""))
            if update.get("elapsed_s") is not None:
                text += f" | elapsed {update['elapsed_s']:.3f} s"
            if update.get("remaining_s") is not None:
                text += f" | remaining ≈{update['remaining_s']:.3f} s ({update.get('remaining_basis', 'declared finite schedule')})"
            for key, label in (("burst_index", "burst"), ("scan_count", "scans"), ("next_burst_s", "next burst in s"),
                               ("temperature_k", "sample K"), ("probe_exposure_s", "probe exposure s")):
                if update.get(key) is not None:
                    text += f" | {label}: {update[key]}"
            worker.message.emit(str(update.get("stage", "Acquisition")) + ": " + text)
            if update.get("fraction") is not None:
                worker.progress.emit(round(max(0., min(1., update["fraction"])) * 1000), 1000)
        try:
            store = RunStore(snapshot.operation.output_path, metadata)
            runner = factory(self.context, snapshot.plan, snapshot.operation, store=store, progress=progress)
            with self._runner_lock:
                self._runner = runner
            if worker.cancel_event.is_set():
                runner.cancel("Stopped before preparation")
            if preparation:
                result = json_value(runner.prepare(kind=preparation))
                self._raise_failed_outcome(result, snapshot.operation.output_path)
                result["preparation_kind"] = preparation
                result["compatibility"] = metadata["compatibility"]
                result.setdefault("output_path", str(snapshot.operation.output_path))
                return self._with_display(result) if preparation != "capabilities" else result
            review = {"accepted": True, "settings": snapshot.plan.settings.to_dict(), "compatibility": metadata["compatibility"]}
            dispatched = snapshot.preliminary or {}
            baseline = {"preliminary": self._record_reference(snapshot.preliminary),
                        "blank": self._record_reference(dispatched.get("_dispatch_blank"))}
            continuation = None
            selected_continuation = dispatched.get("_dispatch_continuation")
            if selected_continuation is not None:
                continuation = deepcopy(selected_continuation["continuation"])
                baseline = deepcopy(selected_continuation["baseline"])
                review.update(retained_review=selected_continuation["review"],
                    continuity_evidence=continuation["state_evidence"], source_output_path=continuation["source_output_path"])
            result = json_value(runner.run(review=review, baseline=baseline, continuation=continuation))
            self.last_measurement_outcome = result
            self._raise_failed_outcome(result, snapshot.operation.output_path)
            return self._with_display(result)
        except BaseException:
            if runner is None and snapshot.operation.hardware:
                self.context.ownership.release(snapshot.operation.ownership, safe_verified=True,
                    preservation_verified=store is not None,
                    detail="Preparation failed before device construction; no pump requested")
            raise
        finally:
            with self._runner_lock:
                if self._runner is runner:
                    self._runner = None

    def run_preliminary(self, snapshot, worker):
        kind = self.preparation_kind
        self.preparation_kind = "preliminary"
        return self._execute(snapshot, worker, preparation=kind)

    def run_measurement(self, snapshot, worker):
        return self._execute(snapshot, worker)

    def request_abort(self, reason):
        with self._runner_lock:
            runner = self._runner
        if runner is not None:
            runner.cancel(reason)

    def save_plan(self, path, settings, plan):
        write_json(Path(path), {"schema_version": "single-pump-scan-burst-plan/1",
            "experiment_id": self.context.experiment_id, "mode": self.context.mode,
            "settings": settings, "compiled_preview": json_value(plan)})

    def load_plan(self, path):
        record = json.loads(Path(path).read_text(encoding="utf-8"))
        if record.get("schema_version") != "single-pump-scan-burst-plan/1" or record.get("experiment_id") != self.context.experiment_id:
            raise ValueError("Incompatible experiment or plan schema")
        if record.get("mode") != self.context.mode:
            raise ValueError("Incompatible detector mode in saved plan")
        self.make_plan(record["settings"])
        return record["settings"]

    def load_run(self, path):
        return self._with_display(load_run(path, expected_mode=self.context.mode,
                        expected_condition_id=self._settings_cache.get("condition_id")))

    def load_blank(self, path, plan):
        if self.context.mode != "single":
            raise ValueError("Dual detection uses concurrent reference and Q₀, without a routine blank sequence")
        run = load_run(path, expected_mode=self.context.mode, expected_condition_id=plan.settings.condition_id)
        if run["metadata"].get("kind") != "baseline" or run["status"] not in ("complete", "completed"):
            raise ValueError("A completed sequential blank/control record is required")
        result = {"complete": True, "output_path": str(path), "metadata": run["metadata"],
                  "compatibility": run["metadata"].get("compatibility", {}), "native_paths": run["chunks"]}
        errors = compatibility_conflicts(result["compatibility"], self._identity(plan), "Blank")
        if errors:
            raise ValueError("\n".join(errors))
        return self._with_display(result)

    def prepare_continuation(self, path, evidence_path):
        """Validate retained history and a separate proof before any device access."""
        from .settings import Settings
        from .planner import compile_plan
        retained = load_run(path, expected_mode=self.context.mode,
                            expected_condition_id=self._settings_cache.get("condition_id"))
        if retained["status"] not in ("stopped", "incomplete", "failed") or retained["journal_errors"]:
            raise ValueError("Continuation requires a retained incomplete/stopped record with a readable committed journal")
        state = deepcopy(retained.get("checkpoint", {}).get("state", {}))
        epoch = state.get("epoch")
        if not state.get("pump_intent") or not epoch or not epoch.get("independently_observed") or epoch.get("optical_event_count") != 1:
            raise ValueError("Retained independent pump epoch is ambiguous; continuation cannot request a replacement pump")
        settings = retained["metadata"].get("settings", {})
        scientific = Settings.from_dict(settings)
        plan = compile_plan(scientific, self.capabilities)
        plan.require_valid()
        if plan.blocks[0].block_id not in state.get("completed_blocks", ()):
            raise ValueError("Interrupted early pumped block cannot be replayed; retain this incomplete observation")
        proof = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
        for key in ("accepted_by", "uninterrupted_native_clock", "unchanged_sample_state"):
            if not proof.get(key):
                raise ValueError(f"Continuity evidence requires {key}")
        if not isinstance(proof["accepted_by"], str) or not proof["accepted_by"].strip():
            raise ValueError("Continuity evidence requires a named reviewer")
        if proof.get("sample_state") is not None:
            conflicts = compatibility_conflicts(proof["sample_state"], epoch.get("sample_state"), "Continuity sample state")
            if conflicts:
                raise ValueError("\n".join(conflicts))
        source_hardware = bool(retained["metadata"].get("operation", {}).get("hardware"))
        selected_hardware = self._settings_cache.get("_execution", "connected") == "connected"
        if source_hardware != selected_hardware:
            raise ValueError("Continuation cannot switch between retained real hardware and simulation")
        if not source_hardware and (not isinstance(proof.get("native_now_s"), (int, float)) or proof["native_now_s"] <= epoch["pump_time_s"]):
            raise ValueError("Synthetic continuation requires native_now_s after the retained pump")
        root = Path(path)
        baseline = json.loads((root / "records" / "selected-baselines.json").read_text(encoding="utf-8"))
        review = json.loads((root / "records" / "accepted-preliminary-review.json").read_text(encoding="utf-8"))
        if not review.get("accepted") or compatibility_conflicts(review.get("settings"), settings):
            raise ValueError("Retained accepted preliminary review does not match the original scientific plan")
        if compatibility_conflicts(state.get("settings"), settings):
            raise ValueError("Retained checkpoint settings do not match original scientific settings")
        state.update(source_output_path=str(root.resolve()), state_evidence=proof,
                     continuity_evidence_path=str(Path(evidence_path).resolve()))
        return {"settings": {**settings, "_execution": "connected" if source_hardware else "simulated"},
                "continuation": state, "baseline": baseline, "review": review,
                "operation_records": retained["metadata"].get("operation", {})}

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
        self.continuation = None
        self.preparation_kind = "preliminary"


ScientificAdapter = BurstScientificAdapter
