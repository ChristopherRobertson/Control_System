"""Per-tab owned acquisition lifecycle with native preservation before release."""
from __future__ import annotations

from copy import deepcopy
from threading import Event
import time

from .adapters import InstalledAdapter, ReadinessError, data, settings_data
from .persistence import NativeStore


class SimulationAdapter:
    """Pure forward-model device substitute, never falls back to real factories."""
    def __init__(self, context, operation, plan, *, check=lambda: None, progress=lambda *a: None, retain=lambda *a: None):
        self.context, self.operation, self.plan = context, operation, plan
        self.check, self.progress = check, progress
        self.settings = data(getattr(plan, "resolved_settings", None) or plan.settings)
        self.epoch_s, self.index = 0.0, 0
        self.filter_previous = 0.0
        self.pending_native = []

    def prepare(self):
        self.check()
        return {"execution": "simulation", "hardware_access": False, "value_source": "Synthetic known-truth data; no commissioning claim"}

    def tune(self, wavenumber):
        self.check()
        self.wavenumber = wavenumber

    def acquire(self, event, *, kind="measurement"):
        import numpy as np
        from .simulation import convolved_response
        self.check()
        s, ev = self.settings, data(event)
        rng = np.random.default_rng(s["random_seed"] + self.index)
        delay = ev["quantized_delay_ns"]
        kernel = (getattr(self.plan, "resolved_settings", None) or self.plan.settings).kernel()
        response = float(np.asarray(convolved_response(np.array([delay]), s["candidate_lifetime_ns"], kernel)).reshape(-1)[0])
        center = float(np.mean(s["wavenumbers_cm1"]))
        spectral = float(np.exp(-.5 * ((ev["wavenumber_cm1"] - center) / 2.0) ** 2))
        pumped = kind == "measurement" and ev["condition"] == "pump_on"
        amplitude = s["expected_amplitude"] * spectral * response if pumped else 0.0
        amplitude += s["drift_per_event"] * self.index if kind == "measurement" else 0.0
        residual = s["reset_residual_fraction"] * self.index * s["expected_amplitude"] if pumped else 0.0
        amplitude += residual
        memory = float(kernel.get("filter_memory_fraction", 0))
        self.filter_previous = amplitude * (1 - memory) + memory * self.filter_previous
        amplitude = self.filter_previous
        q0 = 10 ** (-.1 * spectral)
        # Shared detector fluctuation is retained as covariance, rather than
        # being independently averaged away before computing S/R.
        noise = float(s["noise_sd"])
        common = float(rng.normal(0, noise * .5))
        reference = 1.0 + common + float(rng.normal(0, noise))
        sample = (1.0 if kind == "blank" else q0 * 10 ** (-amplitude)) * (1.0 + common) + float(rng.normal(0, noise))
        epoch = self.epoch_s
        self.epoch_s += len(ev["frames"]) * self.plan.timing["frame_period_s"] + s["reset_interval_s"]
        self.index += 1
        def stream(value):
            return {"timestamp_s": np.array([epoch]), "value": np.array([value]),
                    "variance": np.array([noise * noise * 1.25]), "valid": np.array([True]), "group_delay_s": 0.0,
                    "estimator": "simulated_calibrated_signed_impulse_area"}
        result = {k: v for k, v in ev.items() if k != "frames"}
        result.update(sample=stream(sample), requested_condition=ev["condition"],
            condition=ev["condition"] if kind == "measurement" else "unpumped",
            calibrated_optical_delay_ns=delay, observed_electrical_delay_ns=ev.get("electrical_delay_ns", delay),
            optical_delay_source="synthetic_known_truth", quality_flags=[] if not residual else ["reset_failed"],
            acquisition_kernel=kernel, measured_wavenumber_cm1=ev["wavenumber_cm1"],
            pump_evidence={"commanded": pumped, "optical_pulse_count": int(pumped), "source": "synthetic_known_truth"},
            reset_evidence={"equivalent": residual == 0, "source": "synthetic_known_truth", "residual_delta_a": residual},
            native_device_data={"simulated": True, "sample": np.array([sample]), "reference": np.array([reference]),
                "known_truth_delta_a": amplitude, "epoch_s": epoch, "no_hardware_timestamp_claim": True})
        if s["mode"] == "dual":
            result["reference"] = stream(reference)
            result["sample_reference_covariance"] = noise * noise * .25
        return result

    def restore(self):
        return {"safe_verified": True, "errors": [], "hardware_access": False, "detail": "Simulation has no instrument sessions"}


class Runner:
    def __init__(self, context, *, adapter_factory=None, store_factory=NativeStore):
        self.context = context
        self.adapter_factory, self.store_factory = adapter_factory, store_factory
        self.cancel_event = Event()
        self.abort_reason = "Acquisition stopped"
        self.progress_errors = []

    def request_abort(self, reason="Acquisition stopped"):
        self.abort_reason = str(reason)
        self.cancel_event.set()

    def run(self, operation, plan, *, kind="measurement", baseline=None, blank=None, worker=None, scientific_context=None):
        # Ownership mismatch is never repaired by releasing someone else's token.
        if operation.instance_id != self.context.instance_id:
            raise ValueError("Operation belongs to a different detector instance")
        settings = settings_data(plan)
        started = time.monotonic()
        result = {"experiment_id": "nanosecond_stroboscopy", "instance_id": self.context.instance_id,
            "schema_version": 1, "mode": self.context.mode, "kind": kind, "settings": settings,
            "events": [], "status": "failed", "error": "", "result": None,
            "output_path": str(operation.output_path), "run_id": operation.run_id,
            **deepcopy(scientific_context or {})}
        adapter, store = None, None
        primary, cleanup = None, []
        safe, preserved = True, False
        retention_failed = []
        def check():
            if self.cancel_event.is_set():
                raise InterruptedError(self.abort_reason)
            if worker is not None:
                callback = getattr(worker, "check_cancelled", None)
                if callback:
                    callback()
                event = getattr(worker, "cancel_event", None)
                if event is not None and event.is_set():
                    raise InterruptedError("Acquisition stopped")
        def progress(stage, done=0, total=1, detail=""):
            elapsed = time.monotonic() - started
            estimate = float(getattr(plan, "budget", {}).get("total_s", 0))
            remaining = max(0, estimate-elapsed)
            text = f"{stage}: {detail} | elapsed {elapsed:.1f} s; estimated remaining {remaining:.1f} s (planned stage/event budget; physical actions unbounded)"
            result["stage"] = stage
            try:
                self.context.lifecycle.notify_state(True, stage)
                if worker:
                    signal = getattr(worker, "message", None)
                    if hasattr(signal, "emit"):
                        signal.emit(text)
                    signal = getattr(worker, "progress", None)
                    if hasattr(signal, "emit"):
                        signal.emit(int(done), max(1, int(total)))
                    elif callable(signal):
                        signal(stage, done, total, text)
            except Exception as exc:
                self.progress_errors.append(str(exc))
        def retain(name, payload):
            # Exclusive stable filenames; callback is inside hardware ownership.
            try:
                store.save_record(name, payload)
            except Exception as exc:
                retention_failed.append(str(exc))
                raise
        try:
            progress("configuration", detail=kind)
            store = self.store_factory(operation.output_path, mode=self.context.mode, settings=settings, kind=kind, operation=operation)
            store.save_record("plan", data(plan))
            store.save_record("scientific_context", deepcopy(scientific_context or {}))
            check()
            if settings.get("mode") != self.context.mode:
                raise ValueError("Plan belongs to a different detector mode")
            if kind not in ("measurement", "preliminary", "blank"):
                raise ValueError("Unknown acquisition kind")
            if kind == "blank" and self.context.mode != "single":
                raise ValueError("Dual mode acquires simultaneous Q0; a routine sequential blank is not part of this workflow")
            if data(operation.settings) != data(settings):
                raise ValueError("Execution settings differ from the immutable start snapshot")
            if bool(operation.hardware) != (settings.get("execution_mode") == "connected"):
                raise ValueError("Hardware ownership and selected execution mode differ")
            if plan.errors:
                raise ValueError("; ".join(plan.errors))
            selection = next((data(r) for r in operation.sample_records
                if isinstance(data(r), dict) and data(r).get("record_kind") == "sample_spectral_selection"
                and data(r).get("selection_id") == settings.get("sample_selection_id")), None)
            # Optional sample/calibration records affect interpretation only.
            # Actual device values are resolved under ownership in prepare().
            if kind in ("measurement", "preliminary") and self.context.mode == "single":
                self._validate_baseline(blank, settings, "blank")
            if kind == "measurement":
                self._validate_baseline(baseline, settings, "preliminary")
            factory = self.adapter_factory or (InstalledAdapter if operation.hardware else SimulationAdapter)
            adapter = factory(self.context, operation, plan, check=check, progress=progress, retain=retain)
            result["readbacks"] = adapter.prepare()
            plan = adapter.plan
            resolved_settings = getattr(plan, "resolved_settings", None) or plan.settings
            result["resolved_settings"] = data(resolved_settings)
            store.save_record("resolved_plan", data(plan))
            result["baseline_comparison"] = self._compare_readbacks(result["readbacks"], baseline, blank)
            if kind == "preliminary":
                selected = []
                covered = set()
                for event in plan.events:
                    if event.wavenumber_cm1 not in covered:
                        covered.add(event.wavenumber_cm1)
                        selected.append(event)
            else:
                selected = plan.events
            wavelength = None
            for index, event in enumerate(selected):
                check()
                if event.wavenumber_cm1 != wavelength:
                    wavelength = event.wavenumber_cm1
                    progress("tuning/settling", index, len(selected), f"{wavelength:g} cm^-1")
                    adapter.tune(wavelength)
                progress("acquisition", index, len(selected), f"{event.event_id}: {event.requested_delay_ns:g} ns")
                acquired = adapter.acquire(event, kind=kind)
                acquired.setdefault("requested_condition", event.condition)
                if result.get("baseline_comparison"):
                    acquired.setdefault("quality_flags", []).append("baseline_instrument_mismatch")
                acquired.update(sample_id=settings.get("sample_id"), condition_id=settings.get("condition_id"),
                    preparation_id=settings.get("preparation_id"), cell_id=settings.get("cell_id"), temperature_record_id=settings.get("temperature_record_id"))
                from .processing import spectral_observable, FATAL_FLAGS
                try:
                    observable = spectral_observable(acquired, settings["mode"])
                    acquired["quality_flags"] = list(dict.fromkeys([*acquired.get("quality_flags", []), *observable["flags"]]))
                except (ValueError, TypeError, KeyError) as exc:
                    acquired["quality_flags"] = [*acquired.get("quality_flags", []), "missing_support"]
                    acquired["acquisition_validation_error"] = str(exc)
                # Keep the in-memory native event even if the journal append fails.
                result["events"].append(acquired)
                try:
                    store.append_event(acquired)
                except Exception as exc:
                    retention_failed.append(str(exc))
                    raise
                progress("retrieval", index + 1, len(selected), f"retained {len(result['events'])} events")
                fatal = {"clipped", "clipping", "overload", "unlock", "unlocked", "clock_unlocked", "trigger_count_error", "unsupported_reference", "unsupported_sample", "missing_support"}.intersection(acquired.get("quality_flags", []))
                if fatal:
                    raise ReadinessError("Retained hardware fault; stopping before another pulse: " + ", ".join(sorted(fatal)))
            result["status"] = "completed"
        except InterruptedError as exc:
            primary = exc
            result["status"] = "cancelled"
        except Exception as exc:
            primary = exc
            result["status"] = "failed"
        finally:
            # Abort never skips restoration, preservation or the ownership fault
            # decision. A cleanup failure takes precedence over normal stop text.
            progress("restoration")
            if adapter is not None:
                try:
                    result["restoration"] = adapter.restore()
                    safe = bool(result["restoration"].get("safe_verified"))
                    cleanup.extend(result["restoration"].get("errors", []))
                    if not safe and not cleanup:
                        cleanup.append("Instrument safe restoration could not be verified")
                except Exception as exc:
                    safe = False
                    cleanup.append(f"{type(exc).__name__}: {exc}")
                    result["restoration"] = {"safe_verified": False, "errors": cleanup}
            else:
                result["restoration"] = {"safe_verified": True, "errors": [], "detail": "No device adapter was constructed"}
            if cleanup:
                result["status"] = "failed"
            if primary:
                result["error"] = f"{type(primary).__name__}: {primary}"
            if cleanup:
                result["error"] = "Restoration failed: " + "; ".join(cleanup) + (" | Original outcome: " + result["error"] if result["error"] else "")
            if result["events"] and not cleanup:
                try:
                    progress("analysis")
                    check()
                    from .processing import reconstruct
                    if kind == "measurement":
                        result["result"] = reconstruct(result["events"], self._events(baseline), mode=self.context.mode,
                            blank=self._events(blank), kernel=resolved_settings.kernel(), cancel=check,
                            balance=self._balance(adapter, settings))
                        result["result"].setdefault("absolute_limitations", []).extend(getattr(adapter, "balance_limitations", []))
                        if selection is not None:
                            try:
                                from .processing import population_kinetics
                                result["result"]["population_analysis"] = population_kinetics(
                                    result["result"], selection, resolved_settings.kernel(), cancel=check)
                            except InterruptedError:
                                raise
                            except (ValueError, TypeError, KeyError) as exc:
                                result["result"]["population_analysis"] = {"status": "unavailable", "limitation": str(exc)}
                    else:
                        result["result"] = {"kind": kind, "events": deepcopy(result["events"]),
                            "quantity": "sequential blank" if kind == "blank" else ("Q0 = S/R" if self.context.mode == "dual" else "unpumped sample")}
                except InterruptedError as exc:
                    if result["status"] == "completed":
                        result["status"] = "cancelled"
                        result["error"] = str(exc)
                except Exception as exc:
                    result["status"] = "failed"
                    result["error"] += f" | Analysis failed: {type(exc).__name__}: {exc}"
            if adapter is not None and hasattr(adapter, "readbacks"):
                result["readbacks"] = deepcopy(adapter.readbacks)
            progress("saving")
            result["elapsed_s"] = time.monotonic() - started
            try:
                if store is None:
                    raise OSError("Native store could not be created")
                if primary is not None and adapter is not None and getattr(adapter, "pending_native", None):
                    store.save_record("interrupted_native_tail", adapter.pending_native)
                if retention_failed and result["events"]:
                    store.save_record("emergency_native_events", result["events"])
                store.finish(result["status"], restoration=result["restoration"], result=result["result"], error=result["error"],
                    elapsed_s=result["elapsed_s"], readbacks=result.get("readbacks", {}),
                    resolved_settings=result.get("resolved_settings"), baseline_comparison=result.get("baseline_comparison", []), **deepcopy(scientific_context or {}))
                preserved = not retention_failed
                if retention_failed:
                    result["error"] += " | Required native retention failed: " + "; ".join(retention_failed)
            except Exception as exc:
                result["status"] = "failed"
                result["error"] += f" | Native preservation failed: {type(exc).__name__}: {exc}"
            result["preservation_verified"] = preserved
            if operation.hardware:
                try:
                    self.context.ownership.release(operation.ownership, safe_verified=safe,
                        preservation_verified=preserved, detail=result["error"] or "Restoration and native preservation verified")
                except Exception as exc:
                    result["status"] = "failed"
                    result["error"] += f" | Ownership release failed: {exc}"
            try:
                self.context.lifecycle.notify_state(False, result["status"])
                if result["status"] == "failed":
                    self.context.lifecycle.report_error(result["error"])
            except Exception as exc:
                self.progress_errors.append(str(exc))
        return result

    @staticmethod
    def _compare_readbacks(current, baseline, blank):
        """Changed actual instrument kernels invalidate normalization, not raw recording."""
        from .persistence import compatibility_conflicts
        messages = []
        for label, record in (("sample baseline", baseline), ("blank", blank)):
            if not isinstance(record, dict): continue
            previous = record.get("readbacks", {}).get("raw_kernel")
            now = current.get("raw_kernel")
            if previous is not None and now is not None:
                messages.extend(f"{label}: {msg}" for msg in compatibility_conflicts(previous, now, prefix="actual_kernel"))
        return messages

    @staticmethod
    def _balance(adapter, settings):
        qualification = getattr(adapter, "qualification", {})
        value = qualification.get("path_balance")
        if not isinstance(value, dict):
            return None
        for key in ("mode", "condition_id"):
            if value.get(key) is not None and value[key] != settings.get(key):
                adapter.balance_limitations = [f"Optional measured path balance {key} does not apply to this acquisition"]
                return None
        return deepcopy(value)

    @staticmethod
    def _events(record):
        if isinstance(record, dict):
            return record.get("events", [])
        return record or []

    def _validate_baseline(self, record, settings, kind):
        from .processing import validate_native_baseline
        errors = validate_native_baseline(record, settings, kind=kind)
        if errors:
            raise ValueError("; ".join(errors))


def run(context, snapshot, worker=None, *, blank=None):
    return Runner(context).run(snapshot.operation, snapshot.plan, kind=snapshot.kind,
        baseline=snapshot.preliminary, blank=blank, worker=worker)


def acquire_preliminary(context, snapshot, worker=None, *, blank=None):
    return Runner(context).run(snapshot.operation, snapshot.plan, kind="preliminary", blank=blank, worker=worker)
