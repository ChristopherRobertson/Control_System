"""Scientific adapter for the host's guided presentation, with tab-local state."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
from threading import Event

from control_app.measurement_host.presentation import ScientificSelections

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
        self.live_readbacks = {}

    def read_settings(self):
        return self.editor.values()

    def read_operation_settings(self, kind):
        if kind in ("capabilities", "load_blank", "export_handoff"):
            return {"experiment_id": "fixed_wavenumber_kinetics", "schema_version": 1,
                    "record_kind": "fixed_point_plan", "settings": Settings(mode=self.context.mode).to_dict(),
                    "execution": self.editor._execution}
        return self.read_settings()

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
        if envelope.get("historical_ui_settings"):
            evidence["historical_ui_settings"] = deepcopy(envelope["historical_ui_settings"])
        live = deepcopy(self.live_readbacks)
        if envelope.get("execution") == "simulation":
            from .simulation import simulation_profile
            simulation = simulation_profile(self.context.mode, condition_id=settings.condition_id,
                                            condition_profile=settings.condition_profile)
            configuration, evidence = simulation["configuration"], simulation["evidence"]
            live = {}
        return build_plan(settings, configuration, evidence, purpose=purpose, live_readbacks=live)

    def validate_plan(self, plan):
        return tuple(getattr(plan, "validation_errors", ()))

    def summarize_plan(self, plan):
        s, resolved = plan.settings, plan.resolved
        def format_value(value, unit):
            return f"{value:g} {unit}" if isinstance(value, (float, int)) else "Check device"
        detector = resolved.get("sample", {})
        detector_text = format_value(detector.get("rate_sps"), "Sa/s")
        if s.mode == "dual":
            detector_text += " / " + format_value(resolved.get("reference", {}).get("rate_sps"), "Sa/s")
        rows = [("Observation", f"{s.pre_observation_s:g} s before + {s.post_observation_s:g} s recovery"),
                ("Sequence", f"{len(s.positions)} position(s) · {plan.total_pump_events} pump event(s)"),
                ("Duration", format_value(plan.estimates.get("wall_clock_s"), "s")),
                ("Detector rate", detector_text),
                ("Filter", format_value(detector.get("timeconstant_s"), "s") +
                    (f" · order {detector['order']}" if detector.get("order") is not None else ""))]
        size = plan.estimates.get("storage_bytes")
        rows.append(("Storage", f"{size/1024**2:.1f} MiB" if isinstance(size, (float, int)) else "Check device"))
        return rows

    def selected_records(self):
        selected = self.editor.sample_selection
        return ScientificSelections(
            calibration_records=(deepcopy(self.bundle_record),) if self.bundle_record else (),
            sample_records=(deepcopy(selected),) if selected else (),
        )

    def hardware_required(self, kind, settings):
        return kind in ("capabilities", "blank", "preliminary", "measurement") and settings.get("execution", "connected") == "connected"

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
                message += f" · ~{payload['remaining_s']:.1f} s remaining"
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
                        blank=self._compatible_parent(self.blank, snapshot.plan),
                        preliminary=self._compatible_parent(snapshot.preliminary, snapshot.plan))
            self.last_record = result
            if result.get("status") == "stopped":
                raise InterruptedError("Acquisition stopped")
            if result.get("status") not in ("complete", "completed"):
                raise RuntimeError(result.get("cleanup_error") or result.get("storage_error") or
                                   result.get("analysis_error") or result.get("error") or str(result.get("status")))
            return result
        finally:
            self.active_cancel = None

    def _compatible_parent(self, record, plan):
        from .processing import compatible_record
        if record and record.get("status") in ("complete", "completed") and compatible_record(record, plan)[0]:
            return deepcopy(record)
        return None

    def run_preliminary(self, snapshot, worker):
        return self._run(snapshot, worker, "preliminary")

    def run_measurement(self, snapshot, worker):
        return self._run(snapshot, worker, "measurement")

    def run_blank(self, snapshot, worker):
        return self._run(snapshot, worker, "blank")

    def summarize_preliminary(self, result):
        events = result.get("analysis", {}).get("events", [])
        if not events:
            return "Sample retained"
        baseline = events[0].get("baseline", {})
        mean = baseline.get("mean")
        return f"Sample mean {mean:.5g}" if isinstance(mean, (float, int)) else "Sample retained"

    def validate_preliminary(self, preliminary, plan):
        # Every measurement contains its own observed pre-pump baseline. Optional
        # parent data are reused only when they match the physical acquisition.
        return ()

    def validate_operation(self, kind, plan, preliminary):
        if kind in ("capabilities", "load_blank", "export_handoff"):
            return ()
        return self.validate_plan(plan)

    def run_capabilities(self, snapshot, worker):
        from .runner import Runner
        return Runner(self.context).discover(snapshot.operation, Settings.from_dict(snapshot.settings["settings"]),
            cancel=worker.cancel_event, progress=lambda payload: worker.notify(worker.message.emit,
                payload if isinstance(payload, str) else payload.get("message", payload.get("stage", "Checking device"))))

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
