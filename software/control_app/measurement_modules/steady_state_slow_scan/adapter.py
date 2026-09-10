"""Module scientific adapter; the host owns dispatch, device scope and widgets."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import math
from pathlib import Path
from uuid import uuid4

from control_app.measurement_host.presentation import ScientificSelections, StartSnapshot

from .settings import SlowScanSettings, PlannerInputs
from .planner import build_plan, inputs_from_context, simulation_inputs


class SlowScanScientificAdapter:
    def __init__(self, context, settings_widget):
        self.context = context
        self.settings_widget = settings_widget
        self.controls = {"dark": None, "blank": None}
        self.physical_controls_confirmed = False
        self.inputs = None
        self.readbacks = {}
        self.runner = None
        self.next_output_root = None
        self._instrument_generation = 0
        self._control_generations = {}
        self._instrument_reason = ""
        self._calibration_records = ()
        self._last_settings = settings_widget.read_settings()
        saved = context.preferences.value("settings", "")
        if saved:
            try:
                data = json.loads(saved) if isinstance(saved, str) else saved
                settings_widget.apply_settings(data)
            except (ValueError, TypeError, KeyError):
                # A malformed prior preference is not a scientific default.
                pass

    def read_settings(self):
        data = self.settings_widget.read_settings()
        data["physical_controls_confirmed"] = self.physical_controls_confirmed
        self._last_settings = deepcopy(data)
        return data

    def apply_settings(self, settings):
        self.settings_widget.apply_settings(settings)
        self.physical_controls_confirmed = False

    def persist_preferences(self):
        try:
            data = self.read_settings()
            data["physical_controls_confirmed"] = False
            self.context.preferences.setValue("settings", json.dumps(data))
        except (ValueError, TypeError):
            # Intermediate form edits remain editable, never become a bad saved plan.
            return

    def make_plan(self, settings):
        typed = SlowScanSettings.from_dict(settings)
        inputs = self.inputs if typed.hardware else simulation_inputs(typed)
        return build_plan(typed, inputs)

    def validate_plan(self, plan):
        return plan.errors

    def summarize_plan(self, plan):
        selected = plan.selected
        lines = [f"{'Connected' if plan.settings.hardware else 'SIMULATION ONLY'} • {plan.settings.mode} detector • "
                 f"{len(plan.blocks)} declared forward/reverse acquisition blocks",
                 "Pump FIRE and Q-switch: inhibited for every frame.",
                 f"Requested resolution: {plan.settings.requested_resolution_cm1:g} cm⁻¹."]
        for label, key, unit in (("Native rate", "sample_rate_hz", "Hz/channel"),
                                 ("HF2LI time constant", "time_constant_s", "s"),
                                 ("Effective resolution", "effective_resolution_cm1", "cm⁻¹"),
                                 ("Aggregate recorder rate", "aggregate_rate_hz", "samples/s")):
            value = selected.get(key)
            if value is not None:
                lines.append(f"{label}: {value:g} {unit}" if isinstance(value, (int, float)) else f"{label}: {value} {unit}")
        if plan.blocks:
            speeds = sorted(set(block.scan_speed_cm1_s for block in plan.blocks))
            lines.append("Selected trajectory speeds: " + ", ".join(f"{value:g}" for value in speeds) + " cm⁻¹/s")
            intrinsic, response, rate = (selected.get(name) for name in
                                         ("intrinsic_resolution_cm1", "measured_response_s", "sample_rate_hz"))
            if all(value is not None and value > 0 for value in (intrinsic, response, rate)):
                limiting_rate = min(rate, selected.get("reference_sample_rate_hz") or rate)
                resolution = max(math.hypot(intrinsic, speed / limiting_rate, speed * response) for speed in speeds)
                lines.append(f"Selected resolution estimate: ≤{resolution:.4g} cm⁻¹ (characterized response model).")
        estimate = plan.estimates
        if estimate:
            basis = "lower bound" if estimate.get("wall_clock_is_lower_bound") else "planned"
            storage = f"{estimate['native_storage_bytes'] / 1e6:.2f} MB" if estimate.get("native_storage_bytes") is not None else "unresolved"
            memory = f"{estimate['peak_memory_bytes'] / 1e6:.2f} MB" if estimate.get("peak_memory_bytes") is not None else "unresolved"
            lines.append(f"Wall time: {estimate.get('wall_clock_s', 0):.1f} s ({basis}); "
                         f"native storage: {storage}; memory: {memory}.")
        if plan.readiness:
            lines.append(f"{len(plan.readiness)} readiness items: " + "; ".join(plan.readiness[:2]) +
                         (". Inspect plan for the complete list." if len(plan.readiness) > 2 else ""))
        if plan.warnings:
            lines.append(" ".join(plan.warnings[:1]))
        return "\n".join(lines)

    def estimated_seconds(self, plan):
        if plan is None:
            return None
        for key in ("wall_clock_s", "wall_clock_estimate_s", "total_wall_time_s", "total_s"):
            if plan.estimates.get(key) is not None:
                return float(plan.estimates[key])
        return None

    def load_operating_profile(self):
        settings = SlowScanSettings.from_dict(self.read_settings())
        self.inputs = inputs_from_context(self.context, settings, readbacks=self.readbacks)
        self._calibration_records = tuple(
            {"record_kind": "promoted_instrument_calibration", "bundle_id": bundle_id}
            for bundle_id in self.inputs.promoted_bundle_ids
        )

    def selected_records(self):
        records = []
        for role, result in self.controls.items():
            if result is not None:
                records.append({"record_kind": f"slow_scan_{role}", "run_id": result.get("run_id", ""),
                                "native_path": str(result.get("path", "")),
                                "condition_id": result.get("condition_id", ""), "mode": self.context.mode})
        return ScientificSelections(calibration_records=self._calibration_records,
                                    sample_records=tuple(records))

    def hardware_required(self, kind, settings):
        if kind == "capability":
            if not settings.get("hardware", False):
                raise ValueError("Select connected instruments before reading installed capabilities")
            return True
        return bool(settings.get("hardware", False))

    def _get_runner(self):
        if self.runner is None:
            from .runner import SlowScanRunner
            self.runner = SlowScanRunner(self.context)
        return self.runner

    def _runner_snapshot(self, snapshot):
        controls = deepcopy(self.controls)
        controls["q0"] = deepcopy(snapshot.preliminary) if snapshot.kind == "measurement" else None
        controls["reviewed"] = snapshot.kind == "measurement"
        return StartSnapshot(snapshot.operation, snapshot.kind, snapshot.plan, controls)

    def run_control(self, snapshot, worker):
        return self._get_runner().run(self._runner_snapshot(snapshot), worker)

    def run_preliminary(self, snapshot, worker):
        return self._get_runner().run(self._runner_snapshot(snapshot), worker)

    def run_measurement(self, snapshot, worker):
        return self._get_runner().run(self._runner_snapshot(snapshot), worker)

    def request_abort(self, reason):
        if self.runner is not None:
            self.runner.request_abort(reason)

    def accept_control(self, role, result):
        if role == "capability":
            self.readbacks = deepcopy(result.get("readbacks", {}))
            if result.get("inputs") is not None:
                value = result["inputs"]
                self.inputs = value if isinstance(value, PlannerInputs) else PlannerInputs.from_dict(value)
            else:
                self.load_operating_profile()
            return
        if role not in self.controls:
            raise ValueError(f"Unknown control role {role}")
        if role == "blank" and self.context.mode != "single":
            raise ValueError("Dual-detector slow scan uses a simultaneous matched-buffer reference")
        if result.get("kind") != role:
            raise ValueError(f"Selected native record is not a {role} record")
        if result.get("status") not in ("complete", "completed"):
            raise ValueError("Interrupted or rejected controls cannot satisfy readiness")
        errors = self.compatibility_errors(result, self.make_plan(self.read_settings()))
        if errors:
            raise ValueError("Incompatible control: " + "; ".join(errors))
        self.controls[role] = deepcopy(result)
        self._control_generations[role] = self._instrument_generation

    def compatibility_errors(self, result, plan, *, comparison=False):
        if result is None:
            return ["No selected record"]
        if plan is None:
            return ["Resolve the current plan to assess compatibility"]
        expected = plan.settings.to_dict()
        stored = result.get("settings", {})
        if hasattr(stored, "to_dict"):
            stored = stored.to_dict()
        errors = []
        if stored.get("experiment_id", result.get("experiment_id", "steady_state_slow_scan")) != "steady_state_slow_scan":
            errors.append("experiment identity differs")
        if stored.get("mode", result.get("mode")) != expected["mode"]:
            errors.append("detector mode differs")
        recorded = stored.get("condition", {})
        for name, value in expected["condition"].items():
            if comparison and name in ("state_id", "exposure_history_id", "state_verification_id"):
                continue
            if recorded.get(name) != value:
                errors.append(f"condition.{name} differs")
        for name in ("segments", "calibration_bundle_ids", "sample_rate_hz", "time_constant_s", "filter_order",
                     "probe_rate_hz", "probe_width_s", "requested_scan_speed_cm1_s", "marker_interval_cm1", "hardware"):
            a, b = stored.get(name), expected.get(name)
            # Host freezing changes list containers to tuples; the values are identical.
            if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
                errors.append(f"{name} differs")
        previous_plan = result.get("plan", {})
        if hasattr(previous_plan, "to_dict"):
            previous_plan = previous_plan.to_dict()
        previous_selected = previous_plan.get("selected", {})
        for name in ("sample_rate_hz", "time_constant_s", "filter_order", "probe_rate_hz", "probe_width_s", "hf2li", "demodulator_roles"):
            if name in previous_selected and json.dumps(previous_selected[name], sort_keys=True) != json.dumps(plan.selected.get(name), sort_keys=True):
                errors.append(f"resolved {name} differs")
        if not comparison and result.get("compatibility") is not None:
            from .runner import compatibility_errors
            errors.extend(compatibility_errors(result, plan))
        return list(dict.fromkeys(errors))

    def control_errors(self, plan):
        errors = []
        for role in ("dark", "blank") if self.context.mode == "single" else ("dark",):
            result = self.controls.get(role)
            if result is None:
                errors.append(f"Acquire or load a complete compatible {role}")
            else:
                errors.extend(f"{role}: {error}" for error in self.compatibility_errors(result, plan))
                if self._control_generations.get(role) != self._instrument_generation:
                    errors.append(f"{role}: {self._instrument_reason}")
        return errors

    def summarize_preliminary(self, result):
        spectra = result.get("spectra", ())
        quantities = sorted({str(getattr(spectrum, "quantity", "unknown")) for spectrum in spectra})
        return (f"Review {len(spectra)} individual preliminary spectra, directions, detector support, fit residuals and controls. "
                f"Reported quantities: {', '.join(quantities) or 'no valid spectrum'}. "
                "Checking review enables the unpumped scan; sample-state acceptance remains a separate named decision.")

    def validate_review(self, preliminary, plan):
        errors = self.control_errors(plan) + self.compatibility_errors(preliminary, plan)
        if preliminary.get("status") not in ("complete", "completed"):
            errors.append("Preliminary measurement did not complete")
        if not preliminary.get("spectra"):
            errors.append("Preliminary measurement has no reviewable spectral data")
        for spectrum in preliminary.get("spectra", ()):
            valid = getattr(spectrum, "valid", ())
            if not any(valid):
                errors.append("Preliminary spectrum lacks valid matched detector support")
        return errors

    def invalidate_instrument_state(self, reason):
        self._instrument_generation += 1
        self._instrument_reason = reason
        self.readbacks = {}

    def save_plan(self, path, settings, plan):
        from .persistence import save_plan
        save_plan(path, settings, mode=self.context.mode, plan=self.plan_details(plan))

    def plan_details(self, plan):
        from .timing import compile_timing
        details = plan.to_dict()
        try:
            details["compiled_timing"] = compile_timing(plan).to_dict()
        except ValueError as exc:
            details["timing_readiness"] = str(exc)
        return details

    def load_plan(self, path):
        from .persistence import load_plan
        return load_plan(path, expected_mode=self.context.mode)

    def load_run(self, path):
        from .persistence import load_run
        current = deepcopy(self._last_settings)
        return load_run(path, expected_mode=self.context.mode,
                        expected_condition_id=current["condition"]["condition_id"])

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
        plan = build_plan(current["settings"], current.get("plan", {}).get("inputs", {}))
        errors = self.compatibility_errors(result, plan, comparison=True)
        if errors:
            raise ValueError("Pre/post comparison incompatible: " + "; ".join(errors))
        worker.check_cancelled()
        return result

    def export_run(self, path, result):
        from .persistence import export_run
        export_run(path, result)

    def refit(self, result, settings, worker):
        from .processing import FitSettings, fit_model_alternatives
        from .persistence import export_run
        worker.message.emit("Analysis: fitting individual spectra and prospective model alternatives")
        chosen = FitSettings(peak_count=settings["fit_peak_count"], line_shape=settings["fit_line_shape"],
                             baseline_degree=settings["fit_baseline_degree"],
                             fringe_periods_cm1=tuple(settings["fit_fringe_periods_cm1"]))
        alternative_shape = "lorentzian" if chosen.line_shape == "gaussian" else "gaussian"
        alternatives = (chosen, replace(chosen, line_shape=alternative_shape),
                        replace(chosen, baseline_degree=0 if chosen.baseline_degree else 1))
        result["fits"], result["fit_alternatives"] = [], []
        for index, spectrum in enumerate(result.get("spectra", ())):
            worker.check_cancelled()
            fits = fit_model_alternatives(spectrum, alternatives, cancel_check=worker.check_cancelled)
            result["fits"].append(fits[0])
            result["fit_alternatives"].append(fits)
            worker.progress.emit(index + 1, len(result["spectra"]))
        worker.check_cancelled()
        if result.get("path"):
            path = Path(result["path"]) / f"analysis_{uuid4()}.json"
            export_run(path, result)
            result["analysis_path"] = str(path)
        return result

    def export_selection(self, path, result, windows, reviewer, rationale, worker):
        from .persistence import export_selection
        worker.check_cancelled()
        condition = result["settings"]["condition"]
        acceptance = {"sample_state_accepted": True, "review_complete": True,
                      "configuration_id": condition["configuration_id"], "rationale": rationale}
        return export_selection(result, path, windows=windows, accepted_by=reviewer, acceptance=acceptance)

    def new_run(self):
        self.controls = {"dark": None, "blank": None}
        self._control_generations.clear()
        self._instrument_reason = ""
        self.physical_controls_confirmed = False
        self.runner = None
