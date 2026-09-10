"""Slow-scan lifecycle, independent controls, processing and required retention."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic
import shutil
import numpy as np

from .settings import SlowScanSettings
from .native import combine_poll_streams


def compatibility(plan):
    """Explicit fields, never a digest; only scientifically relevant settings."""
    values = plan.settings.to_dict()
    for key in ("acceptance_reviewer", "acceptance_rationale", "plan_label", "hardware",
                "physical_controls_confirmed", "condition_equilibrated"):
        values.pop(key, None)
    return {"settings": values, "selected": deepcopy(plan.selected),
            "configuration_id": plan.settings.condition.configuration_id,
            "calibration_bundle_ids": list(plan.inputs.promoted_bundle_ids)}


def compatibility_errors(result, plan, *, kind=None):
    if not isinstance(result, dict):
        return ("A complete compatible control/preliminary record is required",)
    errors = []
    if result.get("experiment_id") != "steady_state_slow_scan":
        errors.append("Experiment identity mismatch")
    if result.get("instance_id") != plan.settings.instance_id:
        errors.append("Detector instance identity mismatch")
    if plan.settings.hardware and (result.get("simulation") is not False or result.get("readbacks", {}).get("simulation")):
        errors.append("Connected acquisition requires an observed control, not a simulated record")
    if result.get("mode") != plan.settings.mode:
        errors.append("Detector mode mismatch")
    if result.get("condition_id") != plan.settings.condition.condition_id:
        errors.append("Independent sample/temperature condition mismatch")
    if result.get("status") != "completed":
        errors.append("Interrupted, rejected or failed records cannot supply a control or review")
    if kind is not None and result.get("kind") != kind:
        errors.append(f"Expected {kind} record, received {result.get('kind')}")
    expected = compatibility(plan)
    actual = result.get("compatibility", {})
    for key, value in expected.items():
        if actual.get(key) != value:
            if key == "settings":
                names = [name for name, field in value.items() if actual.get(key, {}).get(name) != field]
                errors.append("Control/review settings mismatch: " + ", ".join(names))
            else:
                errors.append(f"Control/review mismatch: {key}")
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
        from .processing import NativeSweep, FitSettings, fit_spectrum, fit_model_alternatives, assess_sweeps
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
            "events": [], "simulation": not operation.hardware,
            "claims": {"pump_command_count": 0, "optical_pump_count": None,
                "optical_time_zero": "unresolved/not measured by static spectroscopy",
                "phase_accepted": False, "instrument_bundle_promoted": False}}
        self.last_result = result
        primary_error = None
        saved = False
        restored = {"safe_verified": True, "errors": []}
        active_backend = None

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
            operation.output_path.mkdir(parents=True, exist_ok=False)
            if kind != "capability":
                plan.require_ready(hardware=operation.hardware)
                if operation.hardware:
                    from .planner import inputs_from_context
                    resolved = inputs_from_context(self.context, plan.settings)
                    for field in ("scientific_profile", "configuration_id", "condition_ids", "modes",
                                  "promoted_bundle_ids", "tee_receiver_topology_verified", "process_trigger_qualified",
                                  "wavelength_markers_qualified", "t660_tick_s", "t660_maximum_delay_s"):
                        if getattr(resolved, field) != getattr(plan.inputs, field):
                            raise ValueError(f"Promoted operating profile changed or is incompatible: {field}; replan and review")
                    qualified = {window.qcl: window for window in resolved.qcl_windows}
                    for window in plan.inputs.qcl_windows:
                        original = qualified.get(window.qcl)
                        if original is None or window.lower_cm1 < original.lower_cm1 or window.upper_cm1 > original.upper_cm1:
                            raise ValueError("Selected QCL coverage exceeds applicable promoted usable range")
                        for field in ("qualified", "source_id", "minimum_speed_cm1_s", "maximum_speed_cm1_s", "speed_increment_cm1_s", "tuning_settle_s"):
                            if getattr(window, field) != getattr(original, field):
                                raise ValueError(f"QCL characterization changed: {field}; replan and review")
                needed = int(plan.estimates.get("native_storage_bytes") or 0)
                if shutil.disk_usage(operation.output_path).free < needed:
                    raise OSError(f"Insufficient storage for {needed} estimated native bytes")
                if available_memory_bytes() < int(plan.estimates.get("peak_memory_bytes") or 0):
                    raise MemoryError("Declared complete acquisition exceeds available memory; revise the explicit plan")
                controls = snapshot.preliminary or {}
                self._validate_controls(controls, plan, kind)
                result["controls"] = {key: {"run_id": value["run_id"], "path": value["path"]}
                                      for key, value in controls.items() if key in ("dark", "blank", "q0") and isinstance(value, dict)}
            factory = self.backend_factory or (InstalledSlowScanBackend if operation.hardware else SyntheticSlowScanBackend)
            active_backend = backend or factory(self.context, operation)
            active_backend.kind = kind
            if kind == "capability":
                report("configuration", "Checking connected capabilities under exclusive ownership")
                result["readbacks"] = active_backend.discover(check)
                result["status"] = "completed"
            else:
                compiled = compile_timing(plan)
                result["compiled_timing"] = compiled.to_dict()
                active_backend.prepare(plan, compiled, check, report)
                result["readbacks"] = active_backend.readbacks
                self._validate_instrument_controls(controls, active_backend.readbacks)
                if kind == "dark":
                    records = active_backend.acquire_dark(plan, check, report)
                    result["dark_native_records"] = records
                    result["dark"] = self._dark_statistics(records, plan)
                else:
                    for block_index, block in enumerate(compiled.blocks):
                        check()
                        observed = active_backend.acquire_block(block, plan, check, report)
                        for repeat, values in enumerate(observed):
                            names = {name: values[name] for name in ("axis_cm1", "sample", "reference", "timestamps_s", "sample_variance", "reference_variance", "detector_covariance", "valid", "flags") if name in values}
                            sweep = NativeSweep(f"{operation.run_id}:{block.block.block_id}:{repeat}", self.context.mode,
                                plan.settings.condition.condition_id, block.block.segment_id, block.block.direction, repeat,
                                **names, metadata={"compatibility": compatibility(plan),
                                    "configuration_id": plan.settings.condition.configuration_id,
                                    "condition": plan.settings.condition.to_dict(), "qcl": block.block.qcl,
                                    "native_assignment": {key: deepcopy(value) for key, value in values.items() if key not in names},
                                    "effective_resolution_cm1": (plan.selected["intrinsic_resolution_cm1"]**2
                                        + (block.block.scan_speed_cm1_s/plan.selected["sample_rate_hz"])**2
                                        + (block.block.scan_speed_cm1_s*plan.selected["measured_response_s"])**2)**.5,
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
                    report("analysis", "Assessing each direction/replicate before any pooling")
                    for sweep in result["sweeps"]:
                        check()
                        processed = self._process(sweep, controls, plan, kind, check)
                        result["spectra"].append(processed)
                        fit_settings = FitSettings(peak_count=plan.settings.fit_peak_count,
                            line_shape=plan.settings.fit_line_shape, baseline_degree=plan.settings.fit_baseline_degree,
                            fringe_periods_cm1=plan.settings.fit_fringe_periods_cm1)
                        if kind != "blank" and np.count_nonzero(processed.valid) >= max(12, fit_settings.peak_count*6):
                            fitted = fit_spectrum(processed, fit_settings, cancel_check=check)
                            result["fits"].append(fitted)
                            alternate_shape = "lorentzian" if fit_settings.line_shape == "gaussian" else "gaussian"
                            candidates = [fit_settings, replace(fit_settings, line_shape=alternate_shape),
                                replace(fit_settings, baseline_degree=0 if fit_settings.baseline_degree else 1)]
                            if fit_settings.fringe_periods_cm1:
                                candidates.append(replace(fit_settings, fringe_periods_cm1=()))
                            alternatives = fit_model_alternatives(processed, candidates, cancel_check=check)
                            result["fit_alternatives"].append(alternatives)
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
            report("restoration", "Restoring settings and verifying outputs OFF")
            if active_backend is not None:
                try:
                    restored = active_backend.restore()
                except BaseException as exc:
                    restored = {"safe_verified": False, "errors": [str(exc)]}
                result["readbacks"] = deepcopy(active_backend.readbacks)
                # Raw records remain available in memory even if storage failed.
                result["partial_native_records"] = active_backend.raw_records
            result["restoration"] = restored
            if not restored.get("safe_verified", False):
                result["status"] = "failed"
                result["cleanup_error"] = "; ".join(restored.get("errors", ["Restoration unverified"]))
            report("saving", "Preserving native, rejected, interrupted and restoration records")
            result["elapsed_s"] = monotonic()-started
            try:
                save_run(operation.output_path, result, result["sweeps"])
                saved = True
            except BaseException as exc:
                result["status"] = "failed"
                result["storage_error"] = str(exc)
            if operation.hardware:
                self.context.ownership.release(operation.ownership,
                    safe_verified=bool(restored.get("safe_verified")), preservation_verified=saved,
                    detail=result.get("cleanup_error") or result.get("storage_error") or result.get("error") or "Slow scan restored and preserved")
        # Cleanup/preservation failures outrank intentional cancellation.
        if result.get("cleanup_error") or result.get("storage_error"):
            raise RuntimeError("; ".join(x for x in (result.get("cleanup_error"), result.get("storage_error"),
                f"Original outcome: {primary_error}" if primary_error else None) if x)) from primary_error
        if primary_error:
            raise primary_error
        report("complete", "Slow scan saved; pump outputs OFF")
        return result

    @staticmethod
    def _validate_controls(controls, plan, kind):
        if kind == "blank" and plan.settings.mode == "dual":
            raise ValueError("Dual slow scan uses simultaneous matched reference; no routine sequential blank")
        required = []
        if kind in ("blank", "preliminary", "measurement"):
            required.append(("dark", "dark"))
        if kind in ("preliminary", "measurement") and plan.settings.mode == "single":
            required.append(("blank", "blank"))
        if kind == "measurement":
            required.append(("q0", "preliminary"))
            if not controls.get("reviewed"):
                raise ValueError("Explicit preliminary review and Start are required")
        for name, expected_kind in required:
            errors = compatibility_errors(controls.get(name), plan, kind=expected_kind)
            if errors:
                raise ValueError(f"{name}: " + "; ".join(errors))

    @staticmethod
    def _validate_instrument_controls(controls, current):
        actual = current.get("hf2li", {}).get("nodes")
        if actual is None:
            return
        # Oscillator frequency follows the external reference; while safely
        # stopped it is an observation, not a restorable configuration value.
        actual = {path: value for path, value in actual.items() if "/oscs/" not in path}
        for role in ("dark", "blank", "q0"):
            control = controls.get(role)
            if not isinstance(control, dict):
                continue
            previous = control.get("readbacks", {}).get("hf2li", {}).get("nodes")
            if previous is not None:
                previous = {path: value for path, value in previous.items() if "/oscs/" not in path}
            if previous != actual:
                raise ValueError(f"{role} HF2LI actual instrument-state mismatch; reacquire/review compatible data")

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
            values = match.ratio if requested_kind == "unpumped_q0" and match.ratio is not None else match.signal
            variance = match.provenance.get("ratio_variance", match.variance) if requested_kind == "unpumped_q0" else match.variance
            return SpectralControl(result["run_id"]+":"+match.native.sweep_id, requested_kind, sweep.mode,
                sweep.condition_id, match.native.axis_cm1, values, variance,
                match.provenance.get("ratio_valid", match.valid) if requested_kind == "unpumped_q0" else match.valid,
                {"complete": True, "compatibility": compatibility(plan)})
        profile = plan.inputs.scientific_profile
        axis = AxisCorrection(**profile["axis_correction"]) if profile.get("axis_correction") else None
        balance = SpectralControl(**profile["path_balance"]) if profile.get("path_balance") else None
        return process_sweep(sweep, dark=controls.get("dark", {}).get("dark") if controls.get("dark") else None,
            blank=control("blank", "blank") if sweep.mode == "single" and kind != "blank" else None,
            q0=control("q0", "unpumped_q0") if kind == "measurement" else None,
            path_balance=balance, axis_correction=axis, max_gap_cm1=profile.get("control_match_max_gap_cm1"), cancel_check=check)


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
