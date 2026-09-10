"""Scientific adapter for the host's guided presentation, with tab-local state."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
from threading import Event

from control_app.measurement_host.presentation import ScientificSelections
from control_app.measurement_host.interchange import sample_selection_from_dict

from .settings import Settings
from .planner import build_plan


class FixedPointAdapter:
    def __init__(self, context, editor):
        self.context, self.editor = context, editor
        self.blank = None
        self.evidence = {}
        self.bundle_record = None
        self.instrument_changes = []
        self.last_record = None
        self.active_cancel = None
        self.preview_callback = lambda payload: None
        self._profile_error = ""
        self.local_selection = None
        self.previous_pumped_record = context.preferences.value("previous_pumped_state")

    def read_settings(self):
        return self.editor.values()

    def apply_settings(self, settings):
        self._validate_envelope(settings)
        self.editor.apply(settings)

    def _validate_envelope(self, data):
        if (data.get("experiment_id") != "fixed_wavenumber_kinetics" or data.get("schema_version") != 1
                or data.get("record_kind") != "fixed_point_plan"):
            raise ValueError("Not a fixed-wavenumber kinetics v1 plan")
        if data["settings"].get("mode") != self.context.mode:
            raise ValueError("Detector mode differs from this tab")
        Settings.from_dict(data["settings"])
        if data.get("sample_selection"):
            sample_selection_from_dict(data["sample_selection"])

    def load_profile(self, bundle_id):
        """Only the host promotion-validating loader establishes instrument authority."""
        bundle = self.context.promoted_bundle(bundle_id)
        manifest = deepcopy(bundle.manifest)
        profile = manifest.get("fixed_wavenumber_kinetics")
        if profile is None:
            relative = manifest.get("fixed_wavenumber_kinetics_profile")
            if not relative:
                raise ValueError("Bundle must supply fixed_wavenumber_kinetics profile data or its relative JSON path")
            path = (Path(bundle.path) / relative).resolve()
            if not path.is_relative_to(Path(bundle.path).resolve()):
                raise ValueError("Operating-profile path must stay inside the promoted bundle")
            profile = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(profile, dict):
            raise ValueError("Operating profile must be a mapping")
        return {"bundle_id": bundle.bundle_id, "manifest": manifest, "profile": profile,
                "path": str(bundle.path)}

    def accept_profile(self, record):
        self.bundle_record = deepcopy(record)
        profile = deepcopy(record["profile"])
        self.evidence = profile if "operating_profile" in profile else {"operating_profile": profile}
        self.evidence.setdefault("bundle_id", record["bundle_id"])
        self._profile_error = ""

    def make_plan(self, envelope, *, purpose="measurement"):
        settings = Settings.from_dict(envelope["settings"])
        configuration = self.context.configuration()
        evidence = deepcopy(self.evidence)
        if envelope.get("execution") == "simulation":
            from .simulation import simulation_profile
            simulation = simulation_profile(self.context.mode, condition_id=settings.condition_id,
                                            condition_profile=settings.condition_profile)
            configuration = simulation["configuration"]
            evidence = simulation["evidence"]
        elif envelope.get("bundle_id") != (self.bundle_record or {}).get("bundle_id"):
            evidence = {}
        selection = envelope.get("sample_selection")
        if selection:
            record = sample_selection_from_dict(selection)
            if purpose == "measurement" or (record.sample_id == settings.sample_id and record.condition_id == settings.condition_id):
                evidence["sample_selection"] = record.to_dict()
        elif self.local_selection:
            evidence["sample_selection"] = deepcopy(self.local_selection)
        if envelope.get("fresh_state_record"):
            evidence.setdefault("operating_profile", {})["fresh_state_record"] = deepcopy(envelope["fresh_state_record"])
        return build_plan(settings, configuration, evidence, purpose=purpose)

    def validate_plan(self, plan):
        return tuple(getattr(plan, "validation_errors", ()))

    def summarize_plan(self, plan):
        data = plan.to_dict()
        s = plan.settings
        lines = [f"{s.condition_profile} · {self.context.mode} detector mode",
                 f"{len(s.positions)} ordered measured positions · {s.technical_repetitions} technical repetition(s)",
                 f"Observation: {s.pre_observation_s:g} s before / {s.post_observation_s:g} s after each event",
                 f"Finite authorized pump budget: {s.event_budget}. Sequential positions are separate observations."]
        lines.append(f"Programmed pump events: {plan.total_pump_events}")
        for key in ("wall_clock_s", "storage_bytes", "peak_memory_bytes"):
            value = plan.estimates.get(key)
            lines.append(f"{key.replace('_', ' ')}: {value if value is not None else 'unresolved'}")
        lines.append(plan.estimates.get("basis", ""))
        resolved = data.get("resolved", {})
        if resolved:
            for role in ("sample", "reference") if s.mode == "dual" else ("sample",):
                detector = resolved.get(role, {})
                lines.append(f"{role.title()}: demod {detector.get('demodulator_index', '?')}, "
                    f"{detector.get('rate_sps', '?')} Sa/s, filter {detector.get('order', '?')}, "
                    f"τ={detector.get('timeconstant_s', '?')} s")
            lines.append(f"Characterized settling {resolved.get('settling_s', '?')} s; accepted event interval "
                         f"{resolved.get('minimum_event_interval_s', '?')} s. Probe carrier is independent.")
        if plan.readiness_items:
            lines.append("Readiness items:\n" + "\n".join(str(item) for item in plan.readiness_items))
        lines.append("Direct HF2LI response limits temporal claims; a fixed point does not measure full band area or identify a microscopic pathway.")
        return "\n".join(lines)

    def selected_records(self):
        selected = self.read_settings().get("sample_selection") or self.evidence.get("sample_selection")
        samples = [deepcopy(record) for record in (selected or self.local_selection, self.read_settings().get("fresh_state_record")) if record]
        return ScientificSelections(
            calibration_records=(deepcopy(self.bundle_record),) if self.bundle_record else (),
            sample_records=tuple(samples),
        )

    def hardware_required(self, kind, settings):
        return settings.get("execution", "connected") == "connected"

    def _run(self, snapshot, worker, kind):
        from .runner import Runner
        import time
        self.active_cancel = worker.cancel_event
        last_preview = [0.]
        estimate = snapshot.plan.estimates.get("wall_clock_s")
        def progress(payload):
            if isinstance(payload, str):
                worker.notify(worker.message.emit, payload)
                return
            message = payload.get("message", payload.get("stage", ""))
            if "elapsed_s" in payload:
                message += f" · elapsed {payload['elapsed_s']:.1f} s"
                if payload.get("remaining_s") is None and estimate is not None:
                    payload = {**payload, "remaining_s": max(0., estimate-payload["elapsed_s"]),
                               "basis": "whole guided-plan stage allowances; manual handling excluded"}
            if payload.get("remaining_s") is not None:
                message += f" · remaining ~{payload['remaining_s']:.1f} s ({payload.get('basis', 'planned stages')})"
            worker.notify(worker.message.emit, message)
            if "total" in payload:
                completed, total = float(payload.get("completed", 0)), float(payload["total"])
                if total > 0 and (total < 1 or not total.is_integer()):
                    worker.notify(worker.progress.emit, min(1000, int(1000*completed/total)), 1000)
                else:
                    worker.notify(worker.progress.emit, int(completed), int(total))
            if payload.get("preview") is not None and time.monotonic()-last_preview[0] >= .25:
                worker.notify(self.preview_callback, payload["preview"])
                last_preview[0] = time.monotonic()
        try:
            result = Runner(self.context).run(snapshot.operation, snapshot.plan, kind=kind,
                        cancel=worker.cancel_event, progress=progress,
                        blank=deepcopy(self.blank), preliminary=snapshot.preliminary)
            self.last_record = result
            if any(event.get("commanded_event_number") for event in result.get("events", [])):
                self.previous_pumped_record = {"settings": deepcopy(result["settings"]),
                    "resolved": deepcopy(result["plan"]["resolved"]),
                    "events": [{key: deepcopy(event.get(key)) for key in ("position_cm1", "baseline", "reset", "commanded_event_number")}
                               for event in result["events"]], "run_id": result["run_id"]}
                self.context.preferences.setValue("previous_pumped_state", self.previous_pumped_record)
            if result.get("status") == "stopped":
                raise InterruptedError("Acquisition stopped")
            if result.get("status") not in ("complete", "completed"):
                raise RuntimeError(result.get("cleanup_error") or result.get("storage_error") or
                                   result.get("analysis_error") or result.get("error") or str(result.get("status")))
            return result
        finally:
            self.active_cancel = None

    def run_preliminary(self, snapshot, worker):
        return self._run(snapshot, worker, "preliminary")

    def run_measurement(self, snapshot, worker):
        return self._run(snapshot, worker, "measurement")

    def run_blank(self, snapshot, worker):
        return self._run(snapshot, worker, "blank")

    def summarize_preliminary(self, result):
        analysis = result.get("analysis", {})
        lines = ["Review the retained unpumped fixed-point signal, baseline statistics and quality flags before Start."]
        for event in analysis.get("events", []):
            baseline = event.get("baseline", {})
            mean, cv, drift = (baseline.get(k) for k in ("mean", "cv", "drift_fraction"))
            lines.append(f"{event.get('wavenumber_cm1', '')} cm⁻¹ · mean {mean:.6g} · CV {cv:.3g} · fractional drift {drift:.3g} · "
                         f"{'stationary' if baseline.get('stationary') else 'not stationary'}"
                         if all(isinstance(v, (float, int)) for v in (mean, cv, drift)) else str(baseline))
            if len(lines) >= 4:
                lines.append("Additional positions and full statistics are available in the retained event views.")
                break
        lines.extend(str(x) for x in analysis.get("quality_flags", []))
        return "\n".join(lines)

    def validate_review(self, preliminary, plan):
        from .processing import compatible_record
        errors = list(compatible_record(preliminary, plan)[1])
        if self.instrument_changes:
            errors.extend(self.instrument_changes)
        if preliminary.get("status") not in ("completed", "complete"):
            errors.append("The preliminary record did not complete successfully")
        if preliminary.get("kind") not in ("preliminary", None):
            errors.append("An unpumped sample preliminary record is required")
        if self.context.mode == "single":
            if self.blank is None:
                errors.append("Acquire or load the complete compatible buffer blank first")
            else:
                errors.extend(compatible_record(self.blank, plan)[1])
        for event in preliminary.get("analysis", {}).get("events", []):
            baseline = event.get("baseline", {})
            if baseline.get("stationary") is False:
                errors.append("Preliminary baseline is not stationary")
        previous = self.previous_pumped_record
        current = plan.settings.to_dict()
        identity = ("sample_id", "preparation_id", "cell_id", "condition_id", "position_id")
        fresh = plan.resolved.get("fresh_state_record", {})
        fresh_applies = fresh.get("accepted") is True and all(fresh.get(k) == current.get(k) for k in identity)
        if previous and not fresh_applies and not current["condition_profile"].startswith("cryo") and all(
                previous["settings"].get(k) == current.get(k) for k in identity):
            if not plan.resolved.get("reset_record_id"):
                errors.append("Another event on this sample state requires applicable measured reset-equivalence evidence")
            old_by_position = {event["position_cm1"]: event for event in previous["events"] if event.get("commanded_event_number")}
            for event in preliminary.get("analysis", {}).get("events", []):
                old = old_by_position.get(event.get("wavenumber_cm1"))
                if old and not (old.get("reset") or {}).get("accepted"):
                    mean = event.get("baseline", {}).get("mean")
                    initial = (old.get("baseline") or {}).get("mean")
                    if mean is None or not initial or abs(mean/initial-1) > current["reset_tolerance_fraction"]:
                        errors.append("This sample has not returned to its retained pre-pump baseline; continue recovery or establish an equivalent fresh state")
        if preliminary.get("analysis", {}).get("quality_flags"):
            errors.extend(str(flag) for flag in preliminary["analysis"]["quality_flags"])
        return tuple(dict.fromkeys(errors))

    def request_abort(self, reason):
        if self.active_cancel is not None:
            self.active_cancel.set()

    def save_plan(self, path, settings, plan):
        from .persistence import write_json
        self._validate_envelope(settings)
        write_json(Path(path), {**settings, "preview": plan.to_dict() if plan else None})

    def load_plan(self, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self._validate_envelope(data)
        data.pop("preview", None)
        return data

    def load_run(self, path, *, condition_id=None, cancel=None):
        from .persistence import load_run, load_analysis_inputs
        from .processing import analyze_run, AnalysisCancelled
        path = Path(path)
        if path.is_dir() and not (path/"run.json").exists() and (path/"native_run.json").exists():
            path = path/"native_run.json"
        record = load_run(path, mode=self.context.mode, condition_id=condition_id)
        if not record.get("analysis") and record.get("native_chunks"):
            try:
                record["analysis"] = analyze_run(record, **load_analysis_inputs(record), cancel=cancel)
                record["offline_reanalysis"] = "Derived from retained native data; original acquisition disposition unchanged"
            except AnalysisCancelled as exc:
                raise InterruptedError(str(exc)) from exc
        return record

    def export_run(self, path, result):
        from .persistence import export_analysis_csv
        export_analysis_csv(result, path)

    def new_run(self):
        self.blank = self.last_record = None
        self.local_selection = None
        self.instrument_changes.clear()
