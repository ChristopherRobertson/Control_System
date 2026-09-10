"""Experiment-owned adapter for the frozen host presentation contract."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from control_app.measurement_host.presentation import ScientificSelections

from .planner import build_plan
from .settings import Settings


def _settings(value):
    return value.to_dict() if hasattr(value, "to_dict") else dict(value)


class NanosecondScientificAdapter:
    """One mutable scientific session per detector tab; no shared device state."""

    def __init__(self, context, settings_widget):
        self.context, self.settings_widget = context, settings_widget
        self.blank = None
        self.last_result = None
        self.sample_records = []
        self.calibration_records = []
        self.instrument_state = {}
        self.instrument_initial = {}
        self.active_runner = None
        self.frozen_inputs = None

    def read_settings(self):
        return self.settings_widget.read_settings()

    def apply_settings(self, settings):
        if settings.get("mode", self.context.mode) != self.context.mode:
            raise ValueError("The plan belongs to the other detector mode")
        self.settings_widget.apply_settings(settings)

    def make_plan(self, settings):
        return build_plan(Settings.from_dict(settings))

    def validate_plan(self, plan):
        return tuple(plan.errors)

    def summarize_plan(self, plan):
        settings = _settings(plan.settings)
        budget = plan.budget
        lines = [
            "EXAMPLE ONLY — simulator settings; connected readiness is checked separately."
            if settings.get("illustrative_only", False) else "Scientific plan; operating readiness must be established from retained evidence.",
            f"{settings.get('profile_id', '')} · {self.context.mode} detector mode",
            f"{len(settings['wavenumbers_cm1'])} selected wavenumbers × "
            f"{len(settings['delays_ns'])} delays × {settings['repetitions']} technical repetitions",
            "Delay schedule (requested ns): " + ", ".join(f"{v:g}" for v in settings["delays_ns"]),
            "Selected command grid (ns): " + ", ".join(f"{v:g}" for v in plan.timing.get("quantized_delays_ns", [])),
            "Programmed electrical intervals (ns): " + ", ".join(f"{v:g}" for v in plan.timing.get("electrical_delays_ns", [])),
            plan.timing.get("resolution_statement", "No optical time resolution is established by command quantization."),
            "Each wavenumber completes its entire delay/control series before retuning.",
            "Kernel: phase-selected probe pulse → HF2LI integrated spectral value; "
            "electrical commands, optical arrival, aperture and filter history remain distinct.",
        ]
        for key, value in budget.items():
            if isinstance(value, (str, int, float)):
                lines.append(f"{key.replace('_', ' ')}: {value:g}" if isinstance(value, (int, float)) else f"{key.replace('_', ' ')}: {value}")
        lines += ["Readiness: " + str(item) for item in plan.readiness]
        lines += ["Planning note: " + str(item) for item in plan.warnings]
        return "\n".join(lines)

    def evaluate_schedule(self, operation, plan, worker):
        """Retained prospective simulation with cooperative cancellation."""
        from .simulation import evaluate_schedule
        from .persistence import NativeStore
        settings = plan.settings
        store = NativeStore(operation.output_path, mode=self.context.mode,
                            settings=settings.to_dict(), kind="simulation_preview", operation=operation)
        try:
            worker.message.emit("Forward simulation: testing lifetime identifiability under entered IRF, aperture, jitter, noise and reset model.")
            result = evaluate_schedule(
                settings.delays_ns, settings.candidate_lifetime_ns, settings.expected_amplitude,
                settings.kernel(), noise_sd=settings.noise_sd, repetitions=settings.repetitions,
                trials=12, seed=settings.random_seed, cancel_check=worker.check_cancelled,
            )
            store.save_record("prospective_simulation", result)
            store.finish("completed", result=result, restoration={"hardware_access": False})
            result["output_path"] = str(operation.output_path)
            return result
        except InterruptedError as exc:
            store.finish("cancelled", error=str(exc), restoration={"hardware_access": False})
            raise InterruptedError("Acquisition stopped; prospective simulation cancellation retained.") from exc
        except Exception as exc:
            if not store.finished:
                store.finish("failed", error=str(exc), restoration={"hardware_access": False})
            raise

    def selected_records(self):
        return ScientificSelections(
            calibration_records=tuple(deepcopy(self.calibration_records)),
            sample_records=tuple(deepcopy(self.sample_records)),
        )

    def hardware_required(self, kind, settings):
        return settings.get("execution_mode", "simulation") == "connected"

    def compatibility(self, record, plan, *, kind=None):
        from .processing import validate_native_baseline
        if not record:
            return ["A complete compatible " + (kind or "preliminary") + " record is required."]
        errors = validate_native_baseline(record, _settings(plan.settings), kind=kind or "preliminary")
        recorded = record.get("ui_instrument_state", {})
        for key, value in self.instrument_state.items():
            if recorded.get(key, self.instrument_initial.get(key)) != value:
                errors.append(f"Instrument configuration differs: {key}.")
        return errors

    def validate_review(self, preliminary, plan):
        errors = self.compatibility(preliminary, plan, kind="preliminary")
        if self.context.mode == "single":
            errors += self.compatibility(self.blank, plan, kind="blank")
        errors += self.selection_conflicts(_settings(plan.settings))
        return errors

    def selection_conflicts(self, settings):
        """Sample-derived selections remain condition data, never calibration."""
        errors = []
        for record in self.sample_records:
            for name in ("sample_id", "condition_id"):
                if record.get(name) != settings.get(name):
                    errors.append(f"Accepted sample selection {name} differs from current settings.")
            if record.get("selection_id") != settings.get("sample_selection_id"):
                errors.append("Accepted sample selection ID differs from current settings.")
            for name, value in record.get("condition", {}).items():
                if name in settings and settings[name] is not None and settings[name] != value:
                    errors.append(f"Accepted sample selection condition.{name} differs from current settings.")
            windows = record.get("windows", [])
            for wave in settings["wavenumbers_cm1"]:
                if not any(window["lower_cm1"] <= wave <= window["upper_cm1"] for window in windows):
                    errors.append(f"Selected wavenumber {wave:g} cm^-1 is outside accepted sample windows.")
        return errors

    def _run(self, snapshot, worker, kind):
        from .runner import Runner
        self.active_runner = Runner(self.context)
        frozen = self.frozen_inputs or {"blank": deepcopy(self.blank), "ui_instrument_state": deepcopy(self.instrument_state)}
        try:
            result = self.active_runner.run(
                snapshot.operation, snapshot.plan, kind=kind,
                baseline=snapshot.preliminary,
                blank=frozen["blank"], worker=worker,
                scientific_context={"ui_instrument_state": frozen["ui_instrument_state"]},
            )
            result.setdefault("ui_instrument_state", deepcopy(frozen["ui_instrument_state"]))
            self.last_result = result
            status = result.get("status", "failed")
            if status == "cancelled":
                raise InterruptedError("Acquisition stopped; available native records were retained.")
            if status != "completed":
                raise RuntimeError(result.get("error") or result.get("failure") or status)
            return result
        finally:
            self.active_runner = None

    def run_blank(self, snapshot, worker):
        if self.context.mode != "single":
            raise ValueError("Dual mode uses simultaneous reference and Q0, not a routine separate blank")
        return self._run(snapshot, worker, "blank")

    def run_preliminary(self, snapshot, worker):
        return self._run(snapshot, worker, "preliminary")

    def run_measurement(self, snapshot, worker):
        return self._run(snapshot, worker, "measurement")

    def summarize_preliminary(self, result):
        quantity = "unpumped sample / sequential blank" if self.context.mode == "single" else "Q0 = unpumped sample / matched-buffer reference"
        return (
            f"Review {quantity}: {len(result.get('events', []))} retained events. "
            "Inspect native support and quality flags before approving. "
            "Approval permits the explicit Start action; it does not establish optical timing or reset qualification."
        )

    def request_abort(self, reason):
        # Host worker's event is the canonical cancellation token. This optional
        # runner method only requests stop; it never releases hardware ownership.
        if self.active_runner and hasattr(self.active_runner, "request_abort"):
            self.active_runner.request_abort(reason)

    def save_plan(self, path, settings, plan):
        from .persistence import save_plan
        save_plan(path, settings, plan, mode=self.context.mode)

    def load_plan(self, path):
        from .persistence import load_plan
        return load_plan(path, expected_mode=self.context.mode)

    def load_run(self, path):
        from .persistence import load_run
        return load_run(path, expected_mode=self.context.mode)

    def export_run(self, path, result):
        from .persistence import export_csv
        export_csv(path, result.get("result") or result)

    def new_run(self):
        self.blank = self.last_result = None
        self.frozen_inputs = None

    def freeze_inputs(self):
        """Called on the UI thread before dispatch; workers never consult widgets."""
        self.frozen_inputs = {"blank": deepcopy(self.blank),
                              "ui_instrument_state": deepcopy(self.instrument_state)}

    def note_instrument_change(self, change):
        details = []
        for item in change.changes:
            key = f"{item.device_id}.{item.configuration_key}"
            self.instrument_initial.setdefault(key, deepcopy(item.previous_value))
            self.instrument_state[key] = deepcopy(item.new_value)
            details.append(key)
        return ", ".join(details)
