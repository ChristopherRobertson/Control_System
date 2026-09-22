"""Experiment-owned acquisition/data adapter for the compact host panel."""
from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
from dataclasses import asdict, fields, is_dataclass, replace
import csv
import json
from pathlib import Path

import numpy as np

from control_app.measurement_host.context import thaw_data
from control_app.measurement_host.presentation import ScientificSelections
from .session import MeasurementSession, normalize_ui_settings, operational_contract
from .settings import AcquisitionIntent, ConditionProfile, RepeatedRapidScanSettings
from .planner import HardwareCapabilities, build_plan


def retained_native_bytes(records):
    """Count actual retained ndarray storage once per object, without digests."""
    seen = set()
    def visit(value):
        identity = id(value)
        if identity in seen:
            return 0
        seen.add(identity)
        if isinstance(value,np.ndarray):
            return int(value.nbytes) + (sum(visit(item) for item in value.flat) if value.dtype.hasobject else 0)
        if is_dataclass(value) and not isinstance(value,type):
            return sum(visit(getattr(value,field.name)) for field in fields(value))
        if isinstance(value,Mapping):
            return sum(visit(item) for item in value.values())
        if isinstance(value,(list,tuple,set,frozenset)):
            return sum(visit(item) for item in value)
        return 0
    return visit(records)


class RepeatedRapidScanAdapter:
    def __init__(self, context, settings_widget, *, acquirer_factory=None, runner_factory=None):
        self.context, self.settings_widget = context, settings_widget
        self.session = MeasurementSession(context.mode)
        self.capabilities = None
        self.calibration = None
        self.runner = None
        self.acquirer_factory, self.runner_factory = acquirer_factory, runner_factory
        self._pending_selection = None
        self._pending_bundle = None
        self.fit_model = None
        saved = context.preferences.value("settings", None)
        if saved:
            try:
                value = json.loads(saved) if isinstance(saved, str) else saved
                settings_widget.apply(self._preference_settings(value))
            except (ValueError, TypeError, KeyError):
                # An incompatible preference cannot disable construction; loaded
                # native plans still surface their explicit validation error.
                pass

    def _preference_settings(self, value):
        legacy_example = value.get("execution") == "simulation" or "EXAMPLE ONLY" in value.get("value_source","").upper()
        settings = RepeatedRapidScanSettings.from_dict(normalize_ui_settings(value,self.context.mode))
        if not legacy_example:
            return settings.to_dict()
        intent = AcquisitionIntent.from_settings(settings)
        sample = intent.sample_name if intent.sample_name not in ("", "unassigned", "unknown") else "Sample"
        condition = ConditionProfile(sample_id=sample)
        return replace(settings,execution="hardware",condition=condition,controls=("probe_only",),
                       acquisition_intent=replace(intent,sample_name=sample).to_dict(),manual_overrides={},
                       calibration_ids=(),instrument_state_id="unverified",
                       value_source="Stored acquisition intent; installed readbacks will resolve operating settings").to_dict()

    def read_settings(self):
        return self.settings_widget.read()

    def read_operation_settings(self, kind):
        if kind == "capabilities":
            reader = getattr(self.settings_widget,"raw_intent",None)
            raw = reader() if reader is not None else {}
            return {"mode":self.context.mode,"experiment_id":"repeated_rapid_scan",
                    "acquisition_intent":deepcopy(raw)}
        return self.read_settings()

    def apply_settings(self, settings):
        checked = RepeatedRapidScanSettings.from_dict(normalize_ui_settings(settings,self.context.mode))
        if checked.mode != self.context.mode:
            raise ValueError("Settings belong to another detector mode")
        settings = checked.to_dict()
        self.settings_widget.apply(settings)
        self.context.preferences.setValue("settings", json.dumps(settings))
        self.context.preferences.sync()

    def make_plan(self, settings):
        retained = retained_native_bytes((self.session.blank,self.session.preliminary,
                                          self.session.background,self.session.result))
        caps = self.capabilities or HardwareCapabilities()
        if isinstance(caps,Mapping):
            caps = HardwareCapabilities(**caps)
        caps = replace(caps,selected_baseline_bytes=retained)
        return build_plan(settings, capabilities=caps, calibration=self.calibration)

    def validate_plan(self, plan):
        return ()  # build_plan validates structure; readiness is separate and visible.

    def summarize_plan(self, plan):
        from control_app.measurement_host.experiment_summary import summary_rows
        return summary_rows(plan, self._procedure_summary(plan), slow_scan=False)

    def _procedure_summary(self, plan):
        s, e = plan.settings, plan.estimates
        actual = plan.actual
        sample_source = ("readback" if actual.get("sample_rate_hz") == s.sample_rate_hz and
                         (s.mode == "single" or actual.get("reference_rate_hz") == s.reference_rate_hz) else "requested")
        hf = f"S {s.sample_rate_hz:g} Sa/s · τ {s.sample_filter_timeconstant_s:g}s/{s.sample_filter_order}"
        if s.mode == "dual":
            hf += f"; R {s.reference_rate_hz:g} Sa/s · τ {s.reference_filter_timeconstant_s:g}s/{s.reference_filter_order}"
        return (("Sequence", f"{plan.movie_count} movies · {plan.pump_count} pump events"),
                ("Movie", f"{e['scans_per_movie']} scans @ {plan.selected['scan_period_s']*1000:.6g} ms · {e['movie_duration_s']:.6g} s"),
                ("HF2LI", f"{hf} ({sample_source} rates)"),
                ("Memory / storage", f"{e.get('retained_run_memory_bytes',e['movie_memory_bytes'])/1024**2:.1f} / {e['storage_bytes']/1024**2:.1f} MiB"),
                ("Duration", f"{e['wall_time_s']:.1f} s estimated total"))

    def wall_estimate(self, plan):
        return float(plan.estimates.get("wall_time_s", 0)) if plan else 0.

    def selected_records(self):
        return ScientificSelections(tuple(deepcopy(self.session.calibration_records)), tuple(deepcopy(self.session.sample_records)))

    def hardware_required(self, kind, settings):
        return kind in ("measurement", "preliminary", "blank", "capabilities")

    def _contract(self, settings, configuration=None, calibration=None, samples=None):
        configuration = self.context.configuration() if configuration is None else thaw_data(configuration)
        contract = operational_contract(thaw_data(settings), self.session.configuration_contract(configuration),
            self.session.calibration_records if calibration is None else thaw_data(calibration),
            self.session.sample_records if samples is None else thaw_data(samples))
        return contract

    def validate_blank(self, plan):
        if self.context.mode == "dual":
            return ()
        if self.session.blank is None:
            return ()
        record = self.session.blank
        errors = list(self.session.check(record, self._contract(plan.settings.to_dict())))
        if record.get("kind") != "blank":
            errors.append("selected record is not a sequential blank")
        if record.get("status") not in ("complete", "completed"):
            errors.append("sequential blank is partial, rejected or interrupted")
        baseline = record.get("baseline")
        if baseline is None or not baseline.complete or baseline.mode != self.context.mode or baseline.kind != "background":
            errors.append("sequential blank lacks complete compatible background support")
        return tuple(errors)

    def validate_preliminary(self, preliminary, plan):
        if preliminary is None:
            self.session.errors.clear()
            return ()
        errors = list(self.session.check(preliminary, self._contract(plan.settings.to_dict())))
        if preliminary.get("kind") != "preliminary":
            errors.append("record is not an unpumped sample preliminary")
        if preliminary.get("status") not in ("complete", "completed"):
            errors.append("preliminary is partial, rejected or interrupted")
        baseline = preliminary.get("baseline")
        if baseline is None or not baseline.complete:
            errors.append("record lacks complete native baseline support")
        elif baseline.mode != self.context.mode:
            errors.append("native baseline belongs to another detector mode")
        self.session.errors = errors
        return tuple(errors)

    def validate_operation(self, kind, plan, preliminary=None):
        if kind in ("load_blank","load_preliminary","load_selection","load_fit_model","fit_movie","preserve_retained"):
            return ()
        if kind == "capabilities":
            return ()
        if kind not in ("measurement", "preliminary", "blank"):
            return (f"Unknown acquisition operation {kind!r}",)
        if plan is None:
            return ("An acquisition plan is required",)
        if plan.settings.mode != self.context.mode:
            return ("Plan belongs to another detector mode",)
        if kind == "blank" and self.context.mode == "dual":
            return ("The dual mode records sample/reference simultaneously",)
        return ()

    def compatible_preliminary(self, plan, candidate=None):
        candidate = candidate if candidate is not None else self.session.preliminary
        return candidate if candidate is not None and not self.validate_preliminary(candidate,plan) else None

    def compatible_blank(self, plan):
        return self.session.blank if self.session.blank is not None and not self.validate_blank(plan) else None

    def summarize_preliminary(self, result):
        count = sum(len(movie.scans) for movie in result.get("native_movies", ()))
        label = "simultaneous sample/reference baseline" if self.context.mode == "dual" else "unpumped sample baseline"
        return f"{count} unpumped scans retained; {label}. Compatible native support is reused automatically."

    def _run(self, snapshot, worker, kind):
        from .runner import RepeatedRapidScanRunner
        if snapshot.plan is None and kind == "capabilities":
            snapshot = replace(snapshot,plan=build_plan(RepeatedRapidScanSettings(mode=self.context.mode)))
        factory = self.runner_factory or RepeatedRapidScanRunner
        self.runner = factory(self.context, acquirer_factory=self.acquirer_factory)
        contract = ({} if kind == "capabilities" else
                    self._contract(snapshot.operation.settings, snapshot.operation.configuration,
                                   snapshot.operation.calibration_records, snapshot.operation.sample_records))
        preliminary = self.compatible_preliminary(snapshot.plan,snapshot.preliminary) if kind == "measurement" else snapshot.preliminary
        snapshot = replace(snapshot,preliminary=deepcopy(preliminary))
        blank = None if kind == "capabilities" else self.compatible_blank(snapshot.plan)
        result = self.runner.run(snapshot, worker, kind=kind, compatibility_contract=contract,
                                 blank=deepcopy(blank), background=None if kind == "capabilities" else deepcopy(self.session.background))
        result.setdefault("compatibility_contract", contract)
        result.setdefault("kind", kind)
        result.setdefault("run_id", snapshot.operation.run_id)
        if kind == "preliminary":
            self.session.preliminary = result
        elif kind == "blank":
            self.session.blank = result
        elif kind == "measurement":
            self.session.result = result
            generated = result.get("auto_preliminary",result.get("preliminary"))
            if generated is not None:
                self.session.preliminary = generated
        return result

    def run_preliminary(self, snapshot, worker):
        return self._run(snapshot, worker, "preliminary")

    def run_measurement(self, snapshot, worker):
        return self._run(snapshot, worker, "measurement")

    def run_auxiliary(self, snapshot, worker, kind):
        return self._run(snapshot, worker, kind)

    def request_abort(self, reason):
        if self.runner is not None:
            self.runner.request_abort(reason)

    def save_plan(self, path, settings, plan):
        checked = RepeatedRapidScanSettings.from_dict(normalize_ui_settings(settings,self.context.mode))
        if checked.mode != self.context.mode or plan.settings.mode != self.context.mode:
            raise ValueError("Plan settings belong to another detector mode")
        settings = checked.to_dict()
        plan = self.make_plan(settings)
        path = Path(path)
        with path.open("x", encoding="utf-8") as stream:
            json.dump({"record_kind": "repeated_rapid_scan_plan", "schema_version": 1,
                       "experiment_id": "repeated_rapid_scan", "mode": self.context.mode,
                       "settings": settings, "plan": plan.to_dict(),
                       "calibration_records": self.session.calibration_records,
                       "sample_records": self.session.sample_records}, stream, indent=2, allow_nan=False)
        self.context.preferences.setValue("settings", json.dumps(settings))

    def load_plan(self, path):
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if (value.get("record_kind") != "repeated_rapid_scan_plan" or value.get("schema_version") != 1
                or value.get("experiment_id") != "repeated_rapid_scan" or value.get("mode") != self.context.mode):
            raise ValueError("Incompatible experiment, detector mode or plan schema")
        return normalize_ui_settings(value["settings"],self.context.mode)

    def load_run(self, path):
        from .persistence import load_run
        saved = load_run(path, expected_mode=self.context.mode)
        record = dict(saved.record)
        metadata = dict(record.get("metadata", {}))
        return {**metadata, **record, "native_movies": record.get("movies", record.get("native_movies", ())),
                "processed": record.get("results", record.get("processed", ())),
                "output_path": str(path), "run_id": saved.run_id}

    def load_record(self, path, kind):
        result = self.load_run(path)
        if result.get("kind") != kind:
            raise ValueError(f"Expected a {kind} record; saved record is {result.get('kind')!r}")
        errors = self.session.check(result, self._contract(self.read_settings()))
        if errors:
            raise ValueError("Incompatible record: " + "; ".join(errors))
        if result.get("status") not in ("complete", "completed"):
            raise ValueError("A partial, interrupted or rejected record cannot supply complete normalization support")
        baseline = result.get("baseline")
        if baseline is None or not baseline.complete or baseline.mode != self.context.mode:
            raise ValueError("Record lacks complete compatible native normalization support")
        return result

    def export_run(self, path, result):
        with Path(path).open("x", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["movie_id", "scan_index", "direction", "native_point", "time_s", "wavenumber_cm1",
                             "normalized_signal", "delta_absorbance", "absolute_absorbance", "variance_delta_absorbance", "valid", "exclusions"])
            for movie in result.get("processed", ()):
                for point in movie.points:
                    for i in range(len(point.time_s)):
                        reasons = [name for name, flags in point.flags.items() if np.asarray(flags)[i]]
                        writer.writerow([movie.movie_id, point.scan_index, point.direction, i, point.time_s[i],
                            point.wavenumbers_cm1[i], point.normalized_signal[i], point.delta_absorbance[i],
                            point.absolute_absorbance[i], point.variance_delta_absorbance[i], point.valid[i], ";".join(reasons)])

    def read_selection(self, path):
        record = json.loads(Path(path).read_text(encoding="utf-8"))
        windows = record.get("windows")
        if not isinstance(windows,list) or not windows:
            raise ValueError("Spectral selection requires measured or chosen windows")
        for window in windows:
            lower,upper = float(window["lower_cm1"]),float(window["upper_cm1"])
            if not np.isfinite(lower) or not np.isfinite(upper) or lower>=upper:
                raise ValueError("Spectral windows must have finite increasing endpoints")
        record.setdefault("selection_id",Path(path).stem)
        record["source_path"] = str(Path(path).resolve())
        return record

    def apply_selection(self, selection):
        settings = self.read_settings()
        settings["condition"]["sample_selection_id"] = selection["selection_id"]
        settings["band_windows_cm1"] = [[w["lower_cm1"], w["upper_cm1"]] for w in selection["windows"]]
        lower = min(w[0] for w in settings["band_windows_cm1"] + list(settings["offband_windows_cm1"]))
        upper = max(w[1] for w in settings["band_windows_cm1"] + list(settings["offband_windows_cm1"]))
        settings["scan_start_cm1"], settings["scan_stop_cm1"] = lower, upper
        intent = AcquisitionIntent.from_settings(settings)
        settings["acquisition_intent"] = replace(intent,spectral_min_cm1=lower,spectral_max_cm1=upper).to_dict()
        overrides = dict(settings.get("manual_overrides",{}))
        overrides.update(band_windows_cm1=deepcopy(settings["band_windows_cm1"]),
                         offband_windows_cm1=deepcopy(settings["offband_windows_cm1"]))
        settings["manual_overrides"] = overrides
        self.session.sample_records = [deepcopy(selection)]
        self.apply_settings(settings)

    def read_bundle(self, bundle_id):
        bundle = self.context.promoted_bundle(bundle_id)
        record = {"bundle_id": bundle.bundle_id, "manifest": deepcopy(bundle.manifest), "path": str(bundle.path)}
        background_file = bundle.manifest.get("repeated_rapid_scan", {}).get("background_file")
        if background_file and self.context.mode == "dual":
            from .persistence import load_baseline
            root = Path(bundle.path).resolve()
            path = (root / background_file).resolve()
            if not path.is_relative_to(root):
                raise ValueError("Promoted background path must remain within its bundle")
            background = load_baseline(path, expected_mode="dual")
            if background.kind != "background" or not background.complete:
                raise ValueError("Path balance requires a complete measured background B record")
            record["background"] = background
        return record

    def apply_bundle(self, record):
        from .planner import resolve_calibration_from_bundle, resolve_operating_settings
        evidence = resolve_calibration_from_bundle(record["manifest"])
        settings = RepeatedRapidScanSettings.from_dict(self.read_settings())
        background = record.get("background")
        selected = resolve_operating_settings(settings, promoted_bundle=asdict(evidence),
                                               installed_readbacks=asdict(self.capabilities) if self.capabilities else {})
        self.calibration = evidence
        self.session.background = background
        section = record["manifest"]["repeated_rapid_scan"]
        selected_record = {key: value for key, value in record.items() if key != "background"}
        if background is not None:
            selected_record["background_record_id"] = background.record_id
        self.session.calibration_records = [{**selected_record, "device_configuration": deepcopy(section.get("device_configuration", {}))}]
        self.apply_settings(selected.settings.to_dict())

    def apply_capabilities(self, result):
        from .planner import HardwareCapabilities
        value = result.get("capabilities")
        if value is not None:
            self.capabilities = value if isinstance(value, HardwareCapabilities) else HardwareCapabilities(**value)
            setter = getattr(self.settings_widget,"set_capabilities",None)
            if setter is not None:
                setter(self.capabilities)

    def new_run(self):
        retained = getattr(self.runner, "last_result", None)
        if retained and retained.get("status") == "preservation_failed" and not retained.get("recovered_to"):
            raise ValueError("Native data exist only in memory after storage failure. Save retained records before New run.")
        self.session.clear()
        self.runner = None

    def preserve_retained(self, snapshot, worker):
        from .persistence import save_run
        retained = getattr(self.runner, "last_result", None)
        if not retained:
            raise ValueError("No retained native record is awaiting preservation")
        record = deepcopy(retained)
        worker.check_cancelled()
        record.update(run_id=snapshot.run_id, source_run_id=retained["run_id"],
                      source_output_path=retained["output_path"], output_path=str(snapshot.output_path),
                      preservation_operation=snapshot.to_dict(), status="preserved_after_storage_failure")
        save_run(snapshot.output_path, record=record)
        retained["recovered_to"] = str(snapshot.output_path)
        return record

    def fit_record(self, snapshot, worker, result, movie_index, model):
        from .processing import fit_recovery_model
        from .persistence import save_run
        movie = result["processed"][movie_index]
        native = next(m for m in result["native_movies"] if m.movie_id == movie.movie_id)
        record = {"experiment_id": "repeated_rapid_scan", "schema_version": 1,
                  "kind": "analysis", "mode": self.context.mode, "run_id": snapshot.run_id,
                  "condition_id": movie.condition_id, "operation": snapshot.to_dict(),
                  "source_run_id": result.get("run_id"), "source_path": result.get("output_path"),
                  "native_movies": [native], "processed": [movie], "analysis_inputs": model,
                  "output_path": str(snapshot.output_path), "status": "partial"}
        error = None
        try:
            worker.check_cancelled()
            worker.message.emit("Analysis: apparent recovery on actual native time/wavelength with identified scan/filter kernel")
            record["fit_analysis"] = fit_recovery_model(native, movie, model, cancelled=worker.cancel_event.is_set)
            record["status"] = "complete"
        except BaseException as exc:
            record["status"] = "cancelled" if isinstance(exc, InterruptedError) else "failed"
            record["error"] = str(exc)
            error = exc
        finally:
            save_run(snapshot.output_path, record=record)
        if error:
            raise error
        return record
