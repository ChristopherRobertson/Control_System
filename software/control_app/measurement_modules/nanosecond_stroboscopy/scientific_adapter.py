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

    def __init__(self, context, settings_widget, *, runner_factory=None):
        self.context, self.settings_widget = context, settings_widget
        self.blank = None
        self.last_result = None
        self.sample_records = []
        self.calibration_records = []
        self.instrument_state = {}
        self.instrument_initial = {}
        self.active_runner = None
        self.frozen_inputs = None
        self.runner_factory = runner_factory
        self.capabilities = {}

    def read_settings(self):
        return self.settings_widget.read_settings()

    def apply_settings(self, settings):
        if settings.get("mode", self.context.mode) != self.context.mode:
            raise ValueError("The plan belongs to the other detector mode")
        self.settings_widget.apply_settings(settings)

    def make_plan(self, settings):
        return build_plan(Settings.from_dict(settings), capabilities=self.capabilities)

    def validate_plan(self, plan):
        return tuple(plan.errors)

    def summarize_plan(self, plan):
        settings = _settings(getattr(plan, "resolved_settings", None) or plan.settings)
        budget = plan.budget
        duration = budget.get("total_s")
        duration_text = f"{duration / 60:.1f} min" if isinstance(duration, (int, float)) else "pending device check"
        if isinstance(duration, (int, float)) and budget.get("capture_estimate_complete") is False:
            duration_text = f"≥ {duration_text} · device check pending"
        storage = budget.get("storage_bytes")
        storage_text = f"{storage / 1e6:.1f} MB" if isinstance(storage, (int, float)) else "storage pending"
        rate, tau = settings.get("hf2li_rate_hz"), settings.get("filter_time_constant_s")
        detector = (f"{rate:g} Sa/s · {tau:g} s filter" if isinstance(rate, (int, float)) and isinstance(tau, (int, float))
                    else "automatic after device check")
        delays = settings["delays_ns"]
        step = settings.get("timing_step_ns")
        grid = f"{step:g} ns command grid" if isinstance(step, (int, float)) else "grid pending"
        period = settings.get("probe_period_s")
        cycle = f"{settings['cycle_interval_s']:g} s cycle"
        if isinstance(period, (int, float)):
            cycle += f" · {period:g} s probe period"
        return (
            ("Schedule", f"{len(settings['wavenumbers_cm1'])} wavelengths × {len(settings['delays_ns'])} delays × {settings['repetitions']} repeats"),
            ("Delay", f"{min(delays):g}…{max(delays):g} ns · {grid}" if delays else "No delays selected"),
            ("Cadence", cycle),
            ("Sequence", f"{budget.get('event_count', 0):,} events · {storage_text}"),
            ("Estimated duration", duration_text),
            ("HF2LI impulse area", detector),
        )

    def selected_records(self):
        return ScientificSelections(
            calibration_records=tuple(deepcopy(self.calibration_records)),
            sample_records=tuple(deepcopy(self.sample_records)),
        )

    def hardware_required(self, kind, settings):
        if kind.startswith("load") or kind in ("save_plan", "export", "simulation_preview"):
            return False
        return settings.get("execution_mode", "connected") == "connected"

    def compatibility(self, record, plan, *, kind=None):
        from .processing import validate_native_baseline
        if not record:
            return ["Acquire or load a blank." if kind == "blank" else "Acquire or load an unpumped sample."]
        errors = validate_native_baseline(record, _settings(plan.settings), kind=kind or "preliminary")
        recorded = record.get("ui_instrument_state", {})
        for key, value in self.instrument_state.items():
            if recorded.get(key, self.instrument_initial.get(key)) != value:
                errors.append(f"Instrument configuration differs: {key}.")
        return errors

    def validate_preliminary(self, preliminary, plan):
        errors = self.compatibility(preliminary, plan, kind="preliminary")
        if self.context.mode == "single":
            errors += self.compatibility(self.blank, plan, kind="blank")
        return errors

    def validate_operation(self, kind, plan, preliminary):
        if kind == "preliminary" and self.context.mode == "single":
            return self.compatibility(self.blank, plan, kind="blank")
        if kind == "measurement":
            return self.validate_preliminary(preliminary, plan)
        return ()

    def _run(self, snapshot, worker, kind):
        from .runner import Runner
        self.active_runner = (self.runner_factory or Runner)(self.context)
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
        return f"Unpumped sample {'Q0 ' if self.context.mode == 'dual' else ''}ready · {len(result.get('events', []))} events"

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
