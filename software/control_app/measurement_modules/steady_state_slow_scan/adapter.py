"""Scientific operations for the shared compact measurement presentation."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from control_app.measurement_host.presentation import ScientificSelections, StartSnapshot
from control_app.measurement_host.context import thaw_data
from .settings import SlowScanSettings, PlannerInputs
from .planner import build_plan, inputs_from_context


class SlowScanScientificAdapter:
    def __init__(self, context, settings_widget):
        self.context, self.settings_widget = context, settings_widget
        self.controls = {"dark": None, "blank": None, "q0": None}
        self.inputs = None
        self.readbacks = {}
        self.runner = None
        self._last_settings = settings_widget.read_settings()
        self._calibration_records = ()
        saved = context.preferences.value("settings", "")
        if saved:
            try:
                settings_widget.apply_settings(json.loads(saved) if isinstance(saved, str) else saved)
            except (ValueError, TypeError, KeyError):
                pass

    def read_settings(self):
        data = self.settings_widget.read_settings()
        self._last_settings = deepcopy(data)
        return data

    def apply_settings(self, settings):
        self.settings_widget.apply_settings(settings)

    def read_operation_settings(self, kind):
        """Read-only file/device inspection also works with an unfinished number."""
        try:
            return self.read_settings()
        except (ValueError, TypeError):
            return deepcopy(self._last_settings)

    def persist_preferences(self):
        try:
            self.context.preferences.setValue("settings", json.dumps(self.read_settings()))
        except (ValueError, TypeError):
            pass  # An unfinished number remains editable but is not a saved plan.

    def make_plan(self, settings):
        typed = SlowScanSettings.from_dict(settings)
        inputs = self.inputs or inputs_from_context(self.context, typed, readbacks=self.readbacks)
        return build_plan(typed, inputs)

    def validate_plan(self, plan):
        return plan.errors

    def validate_preliminary(self, preliminary, plan):
        return ()  # Previous sample data is optional; no approval state exists.

    def validate_operation(self, kind, plan, preliminary):
        return tuple(plan.errors) if plan is not None and kind in ("measurement", "preliminary", "blank") else ()

    def summarize_plan(self, plan):
        selected, settings = plan.selected, plan.settings
        duration = plan.estimates.get("wall_clock_s")
        current = selected.get("current_ma", settings.current_ma)
        rate = selected.get("repetition_rate_hz", settings.repetition_rate_hz)
        width = selected.get("pulse_width_s", settings.pulse_width_s)
        duty = f"{100*rate*width:.3g}%" if rate and width else "Auto"
        filters = []
        for label, tau_key, order_key in (("Sample", "time_constant_s", "filter_order"),
                                           ("Reference", "reference_time_constant_s", "reference_filter_order")):
            tau, order = selected.get(tau_key), selected.get(order_key)
            if tau and order and (label == "Sample" or self.context.mode == "dual"):
                filters.append(f"{label} {tau*1000:g} ms, order {order}")
        return (("Range", f"{settings.upper_cm1:g} → {settings.lower_cm1:g} cm⁻¹"),
                ("Speed / scans", f"{settings.requested_scan_speed_cm1_s:g} cm⁻¹/s / {settings.replicates} scans"),
                ("Laser current", f"{current:g} mA" if current is not None else "Auto"),
                ("Pulse duty", duty), ("HF2LI filters", "; ".join(filters) or "Auto"),
                ("Estimated time", f"{duration:.3g} s" if duration and plan.blocks else "Available after device readback"))

    def estimated_seconds(self, plan):
        return plan.estimates.get("wall_clock_s") if plan is not None else None

    def selected_records(self):
        records = tuple({"record_kind": f"slow_scan_{role}", "run_id": record.get("run_id", ""),
                         "native_path": str(record.get("path", ""))}
                        for role, record in self.controls.items() if record is not None)
        return ScientificSelections(calibration_records=self._calibration_records, sample_records=records)

    def hardware_required(self, kind, settings):
        return kind in ("dark", "blank", "preliminary", "measurement", "capability")

    def _get_runner(self):
        if self.runner is None:
            from .runner import SlowScanRunner
            self.runner = SlowScanRunner(self.context)
        return self.runner

    def _runner_snapshot(self, snapshot):
        controls = deepcopy(self.controls)
        if snapshot.preliminary is not None and snapshot.preliminary.get("spectra"):
            controls["q0"] = deepcopy(snapshot.preliminary)
        plan = snapshot.plan
        if plan is None and snapshot.kind == "capability":
            plan = build_plan(SlowScanSettings.from_dict(thaw_data(snapshot.settings)))
        return StartSnapshot(snapshot.operation, snapshot.kind, plan, controls)

    def run_control(self, snapshot, worker):
        return self._get_runner().run(self._runner_snapshot(snapshot), worker)

    def run_preliminary(self, snapshot, worker):
        return self.run_control(snapshot, worker)

    def run_measurement(self, snapshot, worker):
        return self.run_control(snapshot, worker)

    def request_abort(self, reason):
        if self.runner is not None:
            self.runner.request_abort(reason)

    def accept_result(self, result):
        role = result.get("kind")
        belongs = (result.get("mode") == self.context.mode and result.get("instance_id") == self.context.instance_id
                   and result.get("experiment_id") == "steady_state_slow_scan")
        if role in ("dark", "blank") and result.get("status") in ("complete", "completed") and belongs:
            self.controls[role] = deepcopy(result)
        if belongs and result.get("automatic_dark", {}).get("status") in ("complete", "completed"):
            self.controls["dark"] = deepcopy(result["automatic_dark"])
        if belongs and role in ("preliminary", "measurement") and result.get("status") in ("complete", "completed"):
            self.controls["q0"] = deepcopy(result)
        if result.get("readbacks") and not result.get("simulation"):
            self.readbacks = deepcopy(result["readbacks"])
        if result.get("plan", {}).get("inputs"):
            inputs = PlannerInputs.from_dict(result["plan"]["inputs"])
            if not inputs.simulation:
                self.inputs = inputs

    def accept_control(self, role, result):
        if role == "capability":
            self.readbacks = deepcopy(result.get("readbacks", {}))
            value = result.get("inputs")
            self.inputs = (value if isinstance(value, PlannerInputs) else PlannerInputs.from_dict(value)) if value is not None else None
            return
        if role not in ("dark", "blank") or (role == "blank" and self.context.mode == "dual"):
            raise ValueError("Select the matching detector control type")
        if result.get("kind") != role or result.get("mode") != self.context.mode:
            raise ValueError(f"The selected native record is not a {self.context.mode} {role}")
        if result.get("status") not in ("complete", "completed"):
            raise ValueError(f"Select a completed {role} record")
        if result.get("experiment_id") != "steady_state_slow_scan" or result.get("instance_id") != self.context.instance_id:
            raise ValueError("The selected control belongs to another measurement instance")
        self.controls[role] = deepcopy(result)
        self.accept_result(result)

    def compatibility_errors(self, result, plan, *, comparison=False):
        if result is None:
            return ()
        if result.get("mode") != self.context.mode:
            return ("Detector mode differs",)
        if comparison:
            return ()  # Different state metadata is the purpose of comparison.
        from .runner import compatibility_errors
        return compatibility_errors(result, plan) if plan is not None else ()

    def invalidate_instrument_state(self, reason):
        self.readbacks, self.inputs = {}, None
        # Runner rechecks native control compatibility against the fresh device
        # settings at Start. A changed control never blocks recording raw data.

    def save_plan(self, path, settings, plan):
        from .persistence import save_plan
        from .timing import compile_timing
        details = plan.to_dict()
        try:
            details["compiled_timing"] = compile_timing(plan).to_dict()
        except ValueError:
            pass
        save_plan(path, settings, mode=self.context.mode, plan=details)

    def load_plan(self, path):
        from .persistence import load_plan
        return load_plan(path, expected_mode=self.context.mode)

    def load_run(self, path):
        from .persistence import load_run
        return load_run(path, expected_mode=self.context.mode)

    def load_control(self, path, role, worker):
        worker.check_cancelled()
        result = self.load_run(path)
        if result.get("kind") != role:
            raise ValueError(f"The selected native run is not a {role}")
        worker.check_cancelled()
        return result

    def load_comparison(self, path, current, worker):
        worker.check_cancelled()
        result = self.load_run(path)
        worker.check_cancelled()
        return result

    def export_run(self, path, result):
        from .persistence import export_run
        return export_run(path, result)

    def export_selection(self, path, result, windows, worker):
        from .persistence import export_selection
        worker.check_cancelled()
        return export_selection(result, path, windows=windows)

    def new_run(self):
        self.controls = {"dark": None, "blank": None, "q0": None}
        self.runner = None
