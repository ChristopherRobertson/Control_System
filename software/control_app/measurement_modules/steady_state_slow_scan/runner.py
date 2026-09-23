"""Slow-scan lifecycle, independent controls, processing and required retention."""
from __future__ import annotations

from control_app.paths import research_output_path

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic
import shutil
import numpy as np

from .settings import SlowScanSettings
from .native import combine_poll_streams


_CONTROL_SETTINGS = ("mode", "laser_mode", "segments", "replicates")
_CONTROL_SELECTED = ("detector_recording", "mircat_pulse_trigger_mode", "sample_rate_hz", "reference_sample_rate_hz", "time_constant_s", "filter_order",
    "repetition_rate_hz", "pulse_width_s", "current_ma",
    "probe_rate_hz", "probe_width_s", "marker_interval_cm1", "marker_width_s",
    "process_pulse_width_s", "demodulator_roles", "hf2li")


def _acquisition_compatibility(settings, selected, blocks=(), profile=None):
    """Compare acquired settings, not labels, optional metadata or Auto spelling."""
    def plain(value):
        if hasattr(value, "to_dict"):
            value = value.to_dict()
        if isinstance(value, dict):
            return {key: plain(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [plain(item) for item in value]
        return value
    return {"version": 2,
        "settings": {key: plain(settings.get(key)) for key in _CONTROL_SETTINGS},
        "selected": {key: plain(selected.get(key)) for key in _CONTROL_SELECTED},
        "qcl_pulse_params": plain((profile or {}).get("qcl_pulse_params", {})),
        "trajectories": [{key: plain(block).get(key) for key in
            ("segment_id", "qcl", "direction", "start_cm1", "stop_cm1", "scan_speed_cm1_s")}
            for block in blocks]}


def compatibility(plan):
    return _acquisition_compatibility(plan.settings.to_dict(), plan.selected,
        [block.to_dict() for block in plan.blocks], plan.inputs.scientific_profile)


def compatibility_errors(result, plan, *, kind=None):
    if not isinstance(result, dict):
        return ("No compatible record selected",)
    errors = []
    if result.get("experiment_id") != "steady_state_slow_scan":
        errors.append("Experiment identity mismatch")
    if result.get("instance_id") != plan.settings.instance_id:
        errors.append("Detector instance identity mismatch")
    if plan.settings.hardware and (result.get("simulation") is not False or result.get("readbacks", {}).get("simulation")):
        errors.append("Connected acquisition requires an observed control, not a simulated record")
    if result.get("mode") != plan.settings.mode:
        errors.append("Detector mode mismatch")
    if result.get("status") != "completed":
        errors.append("Control did not complete")
    if kind is not None and result.get("kind") != kind:
        errors.append(f"Expected {kind} record, received {result.get('kind')}")
    expected = compatibility(plan)
    actual = result.get("compatibility", {})
    if actual.get("version") != 2:
        stored_plan = result.get("plan", {})
        actual = _acquisition_compatibility(result.get("settings", actual.get("settings", {})),
            stored_plan.get("selected", actual.get("selected", {})), stored_plan.get("blocks", ()),
            stored_plan.get("inputs", {}).get("scientific_profile", {}))
    for key, value in expected.items():
        if actual.get(key) != value:
            if key == "settings":
                names = [name for name, field in value.items() if actual.get(key, {}).get(name) != field]
                errors.append("Control settings mismatch: " + ", ".join(names))
            else:
                errors.append(f"Control mismatch: {key}")
    return tuple(errors)


class SyntheticSlowScanBackend:
    """Explicit offline demonstration/injected-test backend. Never opens devices."""
    def __init__(self, context, operation):
        self.context, self.operation = context, operation
        self.readbacks = {"simulation": True}
        self.raw_records = []

    def prepare(self, plan, compiled, check, report):
        check()
        self.plan = plan
        self.readbacks["compiled_timing"] = compiled.to_dict()
        report("configuration", "SIMULATION: injected synthetic spectrometer")

    def discover(self, check):
        check()
        return {"simulation": True, "note": "No connected device discovery performed"}

    def acquire_dark(self, plan, check, report):
        check()
        report("acquisition", "SIMULATION detector dark; pump OFF")
        data = {}
        for role in ("sample", "reference", "timing"):
            index = plan.inputs.demodulator_roles[role]
            data[f"/sim/demods/{index}/sample"] = {"timestamp": np.arange(64, dtype=np.uint64),
                "x": np.full(64, .001), "y": np.zeros(64), "dio": np.zeros(64, dtype=np.uint32)}
        return [{"data": data, "simulation": True}]

    def acquire_block(self, block, plan, check, report):
        check()
        scan = block.block
        report("timing-table upload", f"SIMULATION: acknowledged {block.physical_frame_count} frames; A/B OFF")
        values = []
        preceding = 0.
        for earlier in plan.blocks:
            if earlier.block_id == scan.block_id:
                break
            preceding += (earlier.replicates+1)*earlier.frame_period_s
        for repeat in range(scan.replicates):
            check()
            report("acquisition", f"SIMULATION {scan.block_id} sweep {repeat+1}/{scan.replicates}")
            n = min(4000, max(120, int(scan.scan_duration_s*plan.selected["sample_rate_hz"])))
            axis = np.linspace(scan.start_cm1, scan.stop_cm1, n)
            center = (scan.start_cm1+scan.stop_cm1)/2
            span = abs(scan.stop_cm1-scan.start_cm1)
            absorbance = .1*np.exp(-.5*((axis-center)/(span/12))**2)
            reference = 1+.02*(axis-center)/span
            sample = reference*10**(-absorbance)
            if getattr(self, "kind", "") == "blank":
                sample = reference.copy()
            # Deterministic nonzero noise allows uncertainty demonstrations; its
            # provenance remains simulation-only and does not authorize export.
            rng = np.random.default_rng(310+repeat)
            sample += rng.normal(0., 1e-5, n)
            values.append({"axis_cm1": axis, "sample": sample+.001,
                "reference": reference+.001 if plan.settings.mode == "dual" else None,
                "timestamps_s": preceding+repeat*scan.frame_period_s+np.linspace(0., scan.scan_duration_s, n),
                "sample_variance": np.full(n, 1e-10),
                "reference_variance": np.full(n, 1e-10) if plan.settings.mode == "dual" else None,
                "detector_covariance": np.zeros(n) if plan.settings.mode == "dual" else None,
                "valid": np.ones(n, bool), "flags": (), "simulation": True})
        return values

    def restore(self):
        return {"safe_verified": True, "errors": [], "simulation": True,
                "pump_outputs": {"FIRE": False, "Q-switch": False}}


class SlowScanRunner:
    def __init__(self, context, *, backend_factory=None):
        self.context = context
        self.backend_factory = backend_factory
        self.cancel = Event()
        self.cancel_reason = "Acquisition stopped"
        self.last_result = None
        self._prepared = None

    def _close_prepared(self):
        prepared, self._prepared = self._prepared, None
        return self._restore_backend(prepared["backend"]) if prepared else {"safe_verified": True, "errors": []}

    @staticmethod
    def _restore_backend(backend):
        try:
            restored = backend.restore()
        except BaseException as exc:
            restored = {"safe_verified": False, "errors": [str(exc)]}
        blank_path = getattr(backend, "_prepared_blank_path", None)
        if blank_path is not None:
            from .persistence import _write_json_exclusive
            try:
                _write_json_exclusive(Path(blank_path) / "prepared_session_cleanup.json", restored)
                backend._prepared_blank_path = None
            except Exception as exc:
                restored = {**restored, "safe_verified": False,
                            "errors": [*restored.get("errors", []), f"Cleanup record could not be saved: {exc}"]}
        return restored

    @staticmethod
    def _session_settings(settings):
        values = settings.to_dict()
        for key in ("plan_label", "run_label", "condition"):
            values.pop(key, None)
        return values

    def request_abort(self, reason="Acquisition stopped"):
        self.cancel_reason = str(reason)
        self.cancel.set()

    def run(self, snapshot, worker, *, role=None, backend=None):
        if snapshot.operation.hardware:
            with self.context.hardware_scope(snapshot.operation):
                return self._run(snapshot, worker, role=role, backend=backend)
        return self._run(snapshot, worker, role=role, backend=backend)

    def _run(self, snapshot, worker, *, role=None, backend=None):
        from .acquisition import InstalledSlowScanBackend
        from .timing import compile_timing
        from .processing import NativeSweep, assess_sweeps
        from .persistence import save_run
        self.cancel.clear()
        operation, plan = snapshot.operation, snapshot.plan
        kind = role or snapshot.kind
        kind = "measurement" if kind == "sample" else kind
        if kind not in ("dark", "blank", "preliminary", "measurement", "capability"):
            raise ValueError(f"Unsupported slow-scan operation: {kind}")
        started = monotonic()
        result = {"run_id": operation.run_id, "mode": self.context.mode,
            "condition_id": plan.settings.condition.condition_id, "kind": kind,
            "experiment_id": "steady_state_slow_scan", "instance_id": self.context.instance_id,
            "status": "preparing", "path": str(operation.output_path),
            "settings": plan.settings.to_dict(), "plan": plan.to_dict(), "operation": operation.to_dict(),
            "compatibility": compatibility(plan), "sweeps": [], "spectra": [], "fits": [],
            "fit_alternatives": [], "quality": {}, "readbacks": {}, "controls": {}, "restoration": {},
            "analysis_policy": {"peak_model": None, "automatic_peak_fitting": False},
            "events": [], "simulation": not operation.hardware,
            "claims": {"pump_command_count": 0, "optical_pump_count": None,
                "optical_time_zero": "unresolved/not measured by static spectroscopy",
                "phase_accepted": False, "instrument_bundle_promoted": False}}
        self.last_result = result
        primary_error = None
        saved = False
        restored = {"safe_verified": True, "errors": []}
        active_backend = self._prepared["backend"] if self._prepared is not None else None
        retained = False
        resumed = False
        retained_dark = None

        def check():
            if self.cancel.is_set():
                raise InterruptedError("Acquisition stopped: " + self.cancel_reason)
            try:
                worker.check_cancelled()
            except InterruptedError as exc:
                raise InterruptedError("Acquisition stopped: " + str(exc)) from exc

        def report(stage, message):
            elapsed = monotonic()-started
            estimate = plan.estimates.get("wall_clock_s", 0.)
            basis = "lower-bound estimate" if plan.estimates.get("wall_clock_is_lower_bound") else "planned estimate"
            text = f"{stage}: {message} · elapsed {elapsed:.1f} s · remaining ~{max(0., estimate-elapsed):.1f} s ({basis})"
            result["events"].append({"stage": stage, "elapsed_s": elapsed, "message": message})
            # Notification failures never bypass restoration or required saving.
            try:
                worker.message.emit(text)
            except Exception as exc:
                result.setdefault("notification_errors", []).append(str(exc))

        try:
            if operation.instance_id != self.context.instance_id or plan.settings.instance_id != self.context.instance_id:
                raise ValueError("Operation/plan detector instance mismatch")
            if operation.hardware:
                self.context.ownership.assert_owner(operation.ownership)
            check()
            research_output_path(operation.output_path).mkdir(parents=True, exist_ok=False)
            if kind != "capability" and plan.errors:
                raise ValueError("; ".join(plan.errors))
            # Construction never opens a device. Discovery, configuration and
            # retention all remain inside this operation's ownership scope.
            factory = self.backend_factory or (InstalledSlowScanBackend if operation.hardware else SyntheticSlowScanBackend)
            if self._prepared is not None:
                prepared = self._prepared
                active_backend = prepared["backend"]
                if (operation.hardware and operation.ownership == prepared["token"]
                        and kind == "measurement"
                        and operation.configuration == active_backend.operation.configuration
                        and self._session_settings(plan.settings) == prepared["settings"]):
                    self._prepared = None
                    plan = replace(prepared["plan"], settings=plan.settings)
                    active_backend.resume(operation)
                    resumed = True
                    retained_dark = prepared.get("dark")
                    result["prepared_session_reused"] = True
                    result["plan"] = plan.to_dict()
                    result["compatibility"] = compatibility(plan)
                else:
                    cleanup = self._close_prepared()
                    if not cleanup.get("safe_verified"):
                        raise RuntimeError("Prepared session cleanup failed: " + str(cleanup.get("errors")))
                    active_backend = None
            active_backend = active_backend or backend or factory(self.context, operation)
            active_backend.kind = kind
            if kind != "capability":
                if operation.hardware and not resumed and hasattr(active_backend, "resolve_plan"):
                    report("configuration", "Reading device settings")
                    plan = active_backend.resolve_plan(plan.settings, check)
                    result["plan"] = plan.to_dict()
                    result["compatibility"] = compatibility(plan)
                plan.require_ready(hardware=operation.hardware)
                needed = int(plan.estimates.get("native_storage_bytes") or 0)
                if shutil.disk_usage(operation.output_path).free < needed:
                    raise OSError(f"Insufficient storage for {needed} estimated native bytes")
                if available_memory_bytes() < int(plan.estimates.get("peak_memory_bytes") or 0):
                    raise MemoryError("Declared complete acquisition exceeds available memory; revise the explicit plan")
                controls = dict(snapshot.preliminary or {})
                if resumed and not controls.get("dark") and retained_dark:
                    controls["dark"] = retained_dark
                self._validate_controls(controls, plan, kind)
            if kind == "capability":
                report("configuration", "Checking connected capabilities under exclusive ownership")
                result["readbacks"] = active_backend.discover(check)
                result["status"] = "completed"
            else:
                compiled = compile_timing(plan)
                result["compiled_timing"] = compiled.to_dict()
                prepared_plan = None if resumed else active_backend.prepare(plan, compiled, check, report)
                if prepared_plan is not None:
                    # Observed input ranging is part of preparation. Compatibility
                    # uses the final selected ranges, never the prior idle ranges.
                    plan = prepared_plan
                    result["plan"] = plan.to_dict()
                    result["compatibility"] = compatibility(plan)
                result["readbacks"] = active_backend.readbacks
                for name in ("dark", "blank", "q0"):
                    if controls.get(name) is None:
                        continue
                    reasons = compatibility_errors(controls[name], plan,
                        kind=name if name != "q0" else None)
                    if reasons:
                        result.setdefault("unused_controls", {})[name] = list(reasons)
                        controls.pop(name)
                        report("configuration", f"{name.capitalize()} differs; acquiring without this record")
                        continue
                    try:
                        self._validate_instrument_controls({name: controls.get(name)}, active_backend.readbacks)
                    except ValueError as exc:
                        controls.pop(name, None)
                        result.setdefault("unused_controls", {})[name] = [str(exc)]
                        report("configuration", f"{name.capitalize()} device settings differ; record omitted")
                if kind == "dark":
                    records = active_backend.acquire_dark(plan, check, report)
                    result["dark_native_records"] = records
                    result["dark"] = self._dark_statistics(records, plan)
                else:
                    if not controls.get("dark"):
                        report("dark", "Reading emission-OFF baseline")
                        records = active_backend.acquire_dark(plan, check, report)
                        result["dark_native_records"] = records
                        result["dark"] = self._dark_statistics(records, plan)
                        controls["dark"] = {"run_id": operation.run_id + ":dark", "kind": "dark",
                            "source_run_id": operation.run_id, "native_record_field": "dark_native_records",
                            "experiment_id": "steady_state_slow_scan", "instance_id": self.context.instance_id,
                            "mode": self.context.mode, "condition_id": plan.settings.condition.condition_id,
                            "status": "completed", "path": str(operation.output_path),
                            "settings": plan.settings.to_dict(), "compatibility": compatibility(plan),
                            "simulation": not operation.hardware, "dark": deepcopy(result["dark"]),
                            "readbacks": deepcopy(active_backend.readbacks)}
                        result["automatic_dark"] = controls["dark"]
                    result["controls"] = {key: {"run_id": value["run_id"], "path": value["path"]}
                        for key, value in controls.items() if key in ("dark", "blank", "q0") and isinstance(value, dict)}
                    for block_index, block in enumerate(compiled.blocks):
                        check()
                        observed = active_backend.acquire_block(block, plan, check, report)
                        for repeat, values in enumerate(observed):
                            names = {name: values[name] for name in ("axis_cm1", "sample", "reference", "timestamps_s", "sample_variance", "reference_variance", "detector_covariance", "valid", "flags") if name in values}
                            sweep = NativeSweep(f"{operation.run_id}:{block.block.block_id}:{repeat}", self.context.mode,
                                plan.settings.condition.condition_id, block.block.segment_id, block.block.direction, repeat,
                                **names, metadata={"compatibility": compatibility(plan),
                                    "configuration_id": plan.inputs.configuration_id,
                                    "condition": plan.settings.condition.to_dict(), "qcl": block.block.qcl,
                                    "laser_mode": plan.settings.laser_mode,
                                    "detector_recording": plan.selected["detector_recording"],
                                    "detector_units": "HF2LI demodulator magnitude; raw signed X/Y retained in native chunks",
                                    "detector_dc_response_qualified": False,
                                    "native_assignment": {key: deepcopy(value) for key, value in values.items() if key not in names},
                                    "effective_resolution_cm1": self._resolution_estimate(plan, block.block),
                                    "native_axis_basis": "simulated" if not operation.hardware else "observed controller marker intervals",
                                    "native_chunk_path": str(operation.output_path / "native_chunks"),
                                    "simulation": not operation.hardware})
                            result["sweeps"].append(sweep)
                        if len(observed) != block.block.replicates:
                            raise RuntimeError("Observed sweep count differs from the declared block; native partial data retained")
                        try:
                            worker.progress.emit(block_index+1, len(compiled.blocks))
                        except Exception:
                            pass
                    report("analysis", "Processing spectra")
                    for sweep in result["sweeps"]:
                        check()
                        processed = self._process(sweep, controls, plan, kind, check)
                        result["spectra"].append(processed)
                    result["quality"] = assess_sweeps(result["spectra"],
                        max_gap_cm1=plan.inputs.scientific_profile.get("control_match_max_gap_cm1"),
                        maximum_rms_difference=plan.inputs.scientific_profile.get("maximum_repeatability_rms"))
                    severe = {"unexpected_electrical_pump_sync", "sweep_trigger_count_mismatch", "wavelength_marker_count_mismatch",
                              "direction_changed_inside_sweep", "observed_direction_mismatch", "saturation", "clipping", "unlock", "missing_reference_support", "invalid_reference_signal"}
                    flags = {flag for item in result["spectra"] for flag in item.flags}
                    if severe & flags:
                        raise RuntimeError("Slow-scan quality failure: " + ", ".join(sorted(severe & flags)))
                result["status"] = "completed"
        except BaseException as exc:
            primary_error = exc
            result["status"] = "cancelled" if isinstance(exc, InterruptedError) else "failed"
            result["error"] = str(exc)
        finally:
            if self._prepared is not None and self._prepared["backend"] is active_backend:
                self._prepared = None
            report("restoration", "Restoring settings and verifying outputs OFF")
            if active_backend is not None:
                try:
                    if (kind == "blank" and operation.hardware and primary_error is None
                            and hasattr(active_backend, "park")):
                        restored = active_backend.park(check, report)
                        retained = True
                    else:
                        restored = self._restore_backend(active_backend)
                except BaseException as exc:
                    try:
                        restored = self._restore_backend(active_backend)
                    except BaseException as cleanup_exc:
                        restored = {"safe_verified": False, "errors": [str(cleanup_exc)]}
                    if (kind == "blank" and primary_error is None and isinstance(exc, Exception)
                            and not isinstance(exc, InterruptedError) and restored.get("safe_verified")):
                        result["prepared_session"] = {"retained": False, "warning": str(exc),
                            "fallback_restoration_verified": True}
                        report("prepared session", "Blank saved as usable data; prepared session unavailable: " + str(exc))
                    else:
                        primary_error = primary_error or exc
                        result["status"] = "cancelled" if isinstance(primary_error, InterruptedError) else "failed"
                        result["error"] = str(exc)
                result["readbacks"] = deepcopy(active_backend.readbacks)
                # Raw records remain available in memory even if storage failed.
                result["partial_native_records"] = active_backend.raw_records
            result["restoration"] = restored
            if not retained and not restored.get("safe_verified", False):
                result["status"] = "failed"
                result["cleanup_error"] = "; ".join(restored.get("errors", ["Restoration unverified"]))
            report("saving", "Saving data")
            result["elapsed_s"] = monotonic()-started
            try:
                save_run(operation.output_path, result, result["sweeps"])
                saved = True
            except BaseException as exc:
                result["status"] = "failed"
                result["storage_error"] = str(exc)
            if retained and saved:
                active_backend._prepared_blank_path = operation.output_path
                self._prepared = {"backend": active_backend, "plan": plan, "token": operation.ownership,
                                  "settings": self._session_settings(plan.settings),
                                  "dark": deepcopy(controls.get("dark"))}
                try:
                    self.context.ownership.park(operation.ownership, cleanup=self._close_prepared)
                except BaseException:
                    cleanup = self._close_prepared()
                    self.context.ownership.release(operation.ownership,
                        safe_verified=bool(cleanup.get("safe_verified")), preservation_verified=saved,
                        detail="Prepared session registration failed; cleanup attempted")
                    raise
            elif retained:
                restored = self._restore_backend(active_backend)
                result["restoration"] = restored
            if operation.hardware and not (retained and saved):
                self.context.ownership.release(operation.ownership,
                    safe_verified=bool(restored.get("safe_verified")), preservation_verified=saved,
                    detail=result.get("cleanup_error") or result.get("storage_error") or result.get("error") or "Slow scan restored and preserved")
        # Cleanup/preservation failures outrank intentional cancellation.
        if result.get("cleanup_error") or result.get("storage_error"):
            raise RuntimeError("; ".join(x for x in (result.get("cleanup_error"), result.get("storage_error"),
                f"Original outcome: {primary_error}" if primary_error else None) if x)) from primary_error
        if primary_error:
            raise primary_error
        report("complete", "Saved")
        return result

    @staticmethod
    def _validate_controls(controls, plan, kind):
        if kind == "blank" and plan.settings.mode == "dual":
            raise ValueError("Dual slow scan uses simultaneous matched reference; no routine sequential blank")
        # Controls are reusable observed data, never procedural approvals.
        # Missing blank/Q0 leaves raw/relative output; dark is acquired here.

    @staticmethod
    def _resolution_estimate(plan, block):
        intrinsic = plan.selected.get("intrinsic_resolution_cm1")
        response = plan.selected.get("measured_response_s")
        rate = plan.selected.get("sample_rate_hz")
        if any(value is None for value in (intrinsic, response, rate)):
            return None
        return (intrinsic**2 + (block.scan_speed_cm1_s/rate)**2 +
                (block.scan_speed_cm1_s*response)**2)**.5

    @staticmethod
    def _validate_instrument_controls(controls, current):
        actual = current.get("hf2li", {}).get("nodes")
        if actual is None:
            return
        # External-reference oscillator and PLL center frequencies drift while
        # stopped. Retain those observations without treating them as settings.
        def settings_only(nodes):
            return {path: value for path, value in nodes.items()
                    if "/oscs/" not in path and not path.endswith("/plls/0/freqcenter")}
        actual = settings_only(actual)
        for role in ("dark", "blank", "q0"):
            control = controls.get(role)
            if not isinstance(control, dict):
                continue
            previous = control.get("readbacks", {}).get("hf2li", {}).get("nodes")
            if previous is not None:
                previous = settings_only(previous)
            if previous != actual:
                raise ValueError(f"{role} HF2LI settings changed")

    @staticmethod
    def _dark_statistics(records, plan):
        values = {"source": "measured mean detector magnitude during emission-OFF interval", "estimator": "mean; variance of mean, correlated HF samples may lower effective N"}
        for role in ("sample", "reference"):
            if role == "reference" and plan.settings.mode == "single":
                continue
            stream = combine_poll_streams(records, plan.inputs.demodulator_roles[role])
            magnitude = np.hypot(stream.get("x", []), stream.get("y", []))
            if len(magnitude) < 2 or not np.all(np.isfinite(magnitude)):
                raise ValueError(f"Dark {role} record is missing/invalid")
            values[role] = float(np.mean(magnitude))
            values[role+"_variance"] = float(np.var(magnitude, ddof=1)/len(magnitude))
        return values

    @staticmethod
    def _process(sweep, controls, plan, kind, check):
        from .processing import process_sweep, SpectralControl, AxisCorrection
        def control(name, requested_kind):
            result = controls.get(name)
            if not isinstance(result, dict):
                return None
            choices = [s for s in result.get("spectra", []) if s.native.segment_id == sweep.segment_id and s.native.direction == sweep.direction]
            match = next((s for s in choices if s.native.replicate == sweep.replicate), None)
            if match is None:
                raise ValueError(f"No matched {name} segment/direction/replicate")
            if requested_kind == "unpumped_q0" and match.ratio is None:
                return None  # A prior raw spectrum is not a normalized baseline.
            values = match.ratio if requested_kind == "unpumped_q0" and match.ratio is not None else match.signal
            variance = match.provenance.get("ratio_variance", match.variance) if requested_kind == "unpumped_q0" else match.variance
            return SpectralControl(result["run_id"]+":"+match.native.sweep_id, requested_kind, sweep.mode,
                sweep.condition_id, match.native.axis_cm1, values, variance,
                match.provenance.get("ratio_valid", match.valid) if requested_kind == "unpumped_q0" else match.valid,
                {"complete": True, "compatibility": compatibility(plan)})
        profile = plan.inputs.scientific_profile
        omitted = {}
        def optional_calibration(name, constructor):
            if not profile.get(name):
                return None
            try:
                return constructor(**profile[name])
            except (TypeError, ValueError) as exc:
                omitted[name] = str(exc)
                return None
        axis = optional_calibration("axis_correction", AxisCorrection)
        balance = optional_calibration("path_balance", SpectralControl)
        processed = process_sweep(sweep, dark=controls.get("dark", {}).get("dark") if controls.get("dark") else None,
            blank=control("blank", "blank") if sweep.mode == "single" and kind != "blank" else None,
            q0=control("q0", "unpumped_q0") if kind == "measurement" and (sweep.mode == "dual" or controls.get("blank")) else None,
            path_balance=balance, axis_correction=axis, max_gap_cm1=profile.get("control_match_max_gap_cm1"), cancel_check=check)
        if omitted:
            processed = replace(processed, provenance={**processed.provenance, "calibration_omitted": omitted},
                flags=tuple(dict.fromkeys((*processed.flags, *(name+"_not_applied" for name in omitted)))))
        return processed


def run(context, snapshot, worker, *, role=None, backend=None):
    return SlowScanRunner(context).run(snapshot, worker, role=role, backend=backend)


def discover(context, snapshot, worker):
    return SlowScanRunner(context).run(replace(snapshot, kind="capability"), worker)


def available_memory_bytes():
    """Current physical memory for the entire declared block, no auto splitting."""
    import os
    if os.name == "nt":
        import ctypes
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
        state = MemoryStatus()
        state.length = ctypes.sizeof(state)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
            raise RuntimeError("Cannot establish available acquisition memory")
        return state.available
    return os.sysconf("SC_AVPHYS_PAGES")*os.sysconf("SC_PAGE_SIZE")
