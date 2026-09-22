"""App-owned blank, preliminary review and continuous pumped acquisition."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from threading import Event, Lock
from uuid import uuid4

import numpy as np

from control_app.measurement_host.ownership import default_coordinator

from control_app.workflows.phase_scan_data import (
    DETECTOR_INPUT, SINGLE_DETECTOR_MODE, absorbance, save_native, transmission, utc_now, write_json,
)
from control_app.workflows.phase_scan_runner import OPTICAL_ADAPTER_BLOCKER, save_scan_csv
from control_app.workflows.regular_phase_scan_data import (
    BackgroundSequence, RegularScanStore, compatibility_conflicts, experiment_contract,
    load_background_sequence, reconstruct_sequence, save_regular_reconstruction_csv,
    stable_device_configuration, validate_blank_sequence,
)


def _preservation_progress(callback, message):
    """A failed status display must not interrupt cleanup or native retention."""
    try:
        callback(message)
    except Exception:
        pass


@dataclass(frozen=True)
class PhaseScanOperationSelection:
    """Detached legacy selection captured before dispatch; no hardware access."""
    instance_id: str
    background: object
    preliminary: object
    preliminary_reviewed: bool
    calibration: object = None


class RegularPhaseScanRunner:
    """A resolved blank/sample pair keeps identical sequence and detector settings."""
    def __init__(self, acquirer_factory=None, *, capabilities=None, capability_provider=None,
                 coordinator=None, hardware_access=False, instance_id="phase_scan:single"):
        self.coordinator = coordinator or default_coordinator()
        self.hardware_access = bool(hardware_access)
        self.instance_id = instance_id
        self._ownership_token = None
        self.status_callback_errors = []
        self.acquirer_factory = acquirer_factory
        self.capabilities = capabilities
        self.capability_provider = capability_provider
        self.background = None
        self.preliminary = None
        self.preliminary_reviewed = False
        self.last_readback = {}
        self.cancel = Event()
        self._lock = Lock()
        self._active_acquirer = None
        self._faulted_acquirer = None
        self._prepared_acquirer = None

    @property
    def experiment_session_active(self):
        return self._prepared_acquirer is not None

    def _require_no_session(self):
        if self.experiment_session_active:
            raise RuntimeError("End the current phase experiment before changing settings or selecting another blank")

    def _close_prepared(self):
        acquirer, self._prepared_acquirer = self._prepared_acquirer, None
        if acquirer is None:
            return {"safe_verified": True, "errors": []}
        try:
            acquirer.close()
            return {"safe_verified": True, "errors": []}
        except BaseException as exc:
            self._faulted_acquirer = acquirer
            return {"safe_verified": False, "errors": [str(exc)]}

    def end_experiment(self):
        """Finish a retained session from a worker, including its final evidence."""
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("Abort and wait for the active acquisition before ending the experiment")
        try:
            if self.hardware_access:
                self.coordinator.close_parked_session(instance_id=self.instance_id)
            else:
                result = self._close_prepared()
                if not result["safe_verified"]:
                    raise RuntimeError("; ".join(result["errors"]))
            self._clear_background()
        finally:
            self._lock.release()

    @property
    def hardware_cleanup_pending(self):
        acquirer = self._active_acquirer or self._faulted_acquirer
        worker = getattr(acquirer, "_start_thread", None)
        return bool(self.hardware_access and worker is not None and worker.is_alive())

    @property
    def available(self):
        return self.acquirer_factory is not None

    def set_capabilities(self, capabilities):
        self._require_no_session()
        if self._lock.locked():
            raise RuntimeError("Cannot replace capabilities during an operation")
        self.capabilities = capabilities

    def refresh_capabilities(self):
        self._require_no_session()
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("Cannot discover settings during an acquisition")
        ownership = None
        succeeded = False
        try:
            ownership = self._begin_hardware("capability_discovery")
            if self.capability_provider is None:
                from control_app.workflows.regular_phase_scan import discover_regular_capabilities
                capabilities = discover_regular_capabilities()
            else:
                capabilities = self.capability_provider()
            self.capabilities = capabilities
            succeeded = True
            return capabilities
        except BaseException:
            # Retain the choices so a failed device check never traps the
            # editor, but do not keep stale authority to start acquisition.
            if self.capabilities is not None:
                from control_app.workflows.regular_phase_scan import HF2Capabilities
                self.capabilities = replace(HF2Capabilities.from_dict(self.capabilities), verified=False)
            raise
        finally:
            try:
                self._finish_hardware(ownership, safe_verified=succeeded, preservation_verified=True,
                                      detail="Capability discovery and restoration completed" if succeeded else "Capability discovery failed; explicit recovery required")
            finally:
                self._lock.release()

    def _begin_hardware(self, purpose):
        if not self.hardware_access:
            return None
        token = self.coordinator.acquire(self.instance_id, purpose=purpose, cancel=lambda reason: self.abort())
        scope = self.coordinator.scope(token)
        scope.__enter__()
        self._ownership_token = token
        return token, scope

    def _finish_hardware(self, ownership, *, retained=False, **outcome):
        if ownership is None:
            return
        token, scope = ownership
        try:
            if retained:
                try:
                    self.coordinator.park(token, cleanup=self._close_prepared,
                        detail="Phase experiment retained; reference running, emission and scan triggers off")
                except BaseException:
                    cleanup = self._close_prepared()
                    self.coordinator.release(token, safe_verified=cleanup["safe_verified"],
                        preservation_verified=outcome.get("preservation_verified", False),
                        detail="Phase experiment retention failed; cleanup attempted")
                    raise
            else:
                self.coordinator.release(token, **outcome)
        finally:
            scope.__exit__(None, None, None)
            self._ownership_token = None

    def _safe_progress(self, callback):
        self.status_callback_errors = []
        def report(message):
            try:
                callback(message)
            except Exception as exc:
                self.status_callback_errors.append(f"{type(exc).__name__}: {exc}")
        return report

    def configuration_preview(self, settings, overrides=None):
        from control_app.workflows.regular_phase_scan import build_regular_phase_scan_plan
        return build_regular_phase_scan_plan(settings, capabilities=self.capabilities, overrides=overrides)

    def _contract_for(self, settings_or_plan):
        if hasattr(settings_or_plan, "event_at"):
            return experiment_contract(settings_or_plan)
        # UI field edits can report conflicts before HF2LI resolution. This
        # intentionally compares every settings field, including cadence.
        return {"settings": asdict(settings_or_plan)}

    def background_conflicts(self, settings_or_plan):
        if self.background is None:
            return ["Acquire or select a complete matching buffer-blank sequence"]
        expected = self._contract_for(settings_or_plan)
        saved = self.background.settings
        if list(expected) == ["settings"]:
            saved = {"settings": saved["settings"]}
        return compatibility_conflicts(saved, expected)

    def background_matches(self, settings_or_plan):
        return not self.background_conflicts(settings_or_plan)

    def preliminary_matches(self, settings_or_plan):
        if self.preliminary is None or not self.background_matches(settings_or_plan):
            return False
        expected = self._contract_for(settings_or_plan)
        saved = self.preliminary["experiment_contract"]
        if list(expected) == ["settings"]:
            saved = {"settings": saved["settings"]}
        return not compatibility_conflicts(saved, expected)

    def mark_preliminary_reviewed(self):
        if self._lock.locked():
            raise RuntimeError("Cannot change preliminary review during an operation")
        if self.preliminary is None:
            raise ValueError("Acquire and inspect the preliminary unpumped sample spectrum first")
        if not self.preliminary_reviewed:
            write_json(self.preliminary["path"] / "review.json", {
                "reviewed_utc": utc_now(), "action": "operator_confirmed_preliminary_spectral_review",
                "pump_acquisition_authorized": False,
            })
        self.preliminary_reviewed = True

    def invalidate_background(self):
        self._require_no_session()
        if self._lock.locked():
            raise RuntimeError("Cannot replace baseline selections during an operation")
        self._clear_background()

    def _clear_background(self):
        self.background = None
        self.preliminary = None
        self.preliminary_reviewed = False

    def _capture_operation_selection(self, plan):
        return PhaseScanOperationSelection(self.instance_id, deepcopy(self.background),
            deepcopy(self.preliminary), bool(self.preliminary_reviewed))

    def freeze_operation_selection(self, plan):
        """Freeze selected baseline/review data for an about-to-dispatch worker."""
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("Cannot freeze another operation while this runner is busy")
        try:
            return self._capture_operation_selection(plan)
        finally:
            self._lock.release()

    def load_background(self, path, plan=None):
        self._require_no_session()
        if self._lock.locked():
            raise RuntimeError("Cannot replace a blank during acquisition")
        background = load_background_sequence(path, plan)
        self.background = background
        self.preliminary = None
        self.preliminary_reviewed = False
        self.last_readback = background.device_settings
        return background

    def abort(self):
        self.cancel.set()

    def _check(self):
        if self.cancel.is_set():
            raise InterruptedError("Phase Scan aborted")

    def execute(self, kind, root, plan, *, on_scan=lambda *args: None,
                progress=lambda message: None, laser_authorized=False, selection_snapshot=None):
        if kind not in {"background", "test", "run"}:
            raise ValueError("Regular Phase Scan supports blank, preliminary spectrum and pumped phase scan only")
        if not self.available:
            raise RuntimeError(OPTICAL_ADAPTER_BLOCKER)
        if self.experiment_session_active and kind == "background":
            self._require_no_session()
        plan, root = deepcopy(plan), Path(root)
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("Phase Scan is already acquiring")
        progress = self._safe_progress(progress)
        ownership = None
        preservation_verified = True
        store = acquirer = candidate = result = None
        error = cleanup_error = None
        records, native_blocks = [], []
        readback = {}
        closed = False
        retained = False
        session_record = None
        background = preliminary = None

        def preserve(callback, *args, **kwargs):
            nonlocal preservation_verified
            preservation_verified = False
            result = callback(*args, **kwargs)
            preservation_verified = True
            return result

        def close():
            nonlocal closed, cleanup_error
            if acquirer is not None and not closed:
                closed = True
                try:
                    _preservation_progress(progress, "Restoring safe idle and instrument settings…")
                    acquirer.close()
                except BaseException as exc:
                    cleanup_error = exc

        try:
            self._check()
            selected = deepcopy(selection_snapshot) if selection_snapshot is not None else self._capture_operation_selection(plan)
            if selected.instance_id != self.instance_id:
                raise ValueError("Selected baseline belongs to a different measurement instance")
            background, preliminary = selected.background, selected.preliminary
            def background_conflicts(frozen_plan):
                if background is None:
                    return ["Acquire or select a complete matching buffer-blank sequence"]
                return compatibility_conflicts(background.settings, experiment_contract(frozen_plan))
            if kind == "background":
                self._clear_background()
                background = preliminary = None
            else:
                conflicts = background_conflicts(plan)
                if conflicts:
                    raise ValueError("Buffer blank incompatible: " + "; ".join(conflicts))
                if kind == "test":
                    self.preliminary = None
                    self.preliminary_reviewed = False
                    preliminary = None
                elif (preliminary is None or
                      compatibility_conflicts(preliminary["experiment_contract"], experiment_contract(plan))):
                    raise ValueError("Acquire a compatible preliminary unpumped sample spectrum before starting the pump")
            ownership = self._begin_hardware(kind)
            acquirer, self._prepared_acquirer = self._prepared_acquirer, None
            resuming = acquirer is not None
            acquirer = acquirer if resuming else self.acquirer_factory()
            self._active_acquirer = acquirer
            persistent = callable(getattr(acquirer, "begin_experiment_session", None))
            if persistent and not resuming:
                acquirer.begin_experiment_session(uuid4().hex)
            if hasattr(acquirer, "resolve_plan"):
                plan = acquirer.resolve_plan(plan)
            # A resolver may reject stale capabilities. It must not silently
            # alter the already captured blank/sample experiment.
            contract = experiment_contract(plan)
            if kind != "background":
                conflicts = background_conflicts(plan)
                if conflicts:
                    raise ValueError("Resolved experiment differs from the buffer blank: " + "; ".join(conflicts))
            store = RegularScanStore(root, kind, plan)
            if hasattr(acquirer, "authorize"):
                acquirer.authorize(laser_authorized)
            acquirer.progress = progress
            progress("Checking full-sequence timing capacity, acquisition memory and instrument readbacks…")
            readback = (acquirer.resume_experiment(plan.settings, store, self.cancel) if resuming else
                        acquirer.prepare(plan.settings, store, self.cancel))
            self.last_readback = readback
            self._check()
            if kind != "background":
                conflicts = compatibility_conflicts(stable_device_configuration(background.device_settings),
                                                     stable_device_configuration(readback), "actual instrument settings")
                if conflicts:
                    raise ValueError("Buffer blank incompatible after hardware configuration: " + "; ".join(conflicts))
            expected = [plan.event_at(i) for i in range(plan.total_scans if kind != "test" else 1)]
            if kind == "background":
                expected = [replace(event, pump_enabled=False) for event in expected]
            progress("Checking the complete timing table and allocating acquisition memory…")
            blocks = acquirer.prepare_blocks(plan, expected, self.cancel)
            if len(blocks) != 1:
                raise ValueError("This experiment requires one continuous acquisition; the full timing table or native data cannot fit without splitting")
            self._check()
            progress(f"Preparing one continuous sequence of {len(expected):,} scans…")
            native, captured = acquirer.capture_block(blocks[0], self.cancel)
            native_blocks.append(native)
            records.extend(captured)
            self._check()
            if [event for event, _ in records] != expected:
                raise ValueError("Acquisition returned missing, duplicate, reordered or unexpected scan records")
            for event, spectrum in records:
                spectrum.metadata.update({
                    "record_role": ("buffer_blank" if kind == "background" else
                                    "unpumped_sample_preliminary" if kind == "test" else
                                    "pumped_sample" if event.pump_enabled else "unpumped_sample_baseline"),
                    "detector_mode": SINGLE_DETECTOR_MODE, "detector_input": DETECTOR_INPUT,
                    "acquisition_id": store.id, "record_id": f"{store.id}/scan_{event.scan_index:07d}",
                    "sequence_position": event.scan_index, "acquisition_settings": contract,
                    **{key: readback[key] for key in ("hf2li_device", "hf2li_detector_settings") if key in readback},
                })
                if background is not None:
                    spectrum.metadata["background_source"] = str(background.path)
            if persistent and kind in {"background", "test"}:
                session_record = acquirer.retain_experiment()
                retained = True
            else:
                close()
        except KeyboardInterrupt:
            error = InterruptedError("Phase Scan interrupted by operator")
        except Exception as exc:
            error = exc
        finally:
            if not retained or error is not None:
                close()
                retained = False

        # Retention takes precedence over reconstruction even on abort. Partial
        # native chunks reported by the acquisition adapter remain unmodified.
        try:
            if store is not None:
                _preservation_progress(progress, "Saving available native records…")
                native = {"blocks": native_blocks,
                          "partial_blocks": getattr(acquirer, "partial_blocks", []),
                          "device_settings": readback, "experiment_contract": experiment_contract(plan),
                          "hf2li_requested_selected": getattr(plan, "hf2_selection", {}),
                          "background": None if background is None else {
                              "source": str(background.path), "experiment_contract": background.settings,
                              "device_settings": background.device_settings,
                              "records": [{"event": asdict(e), "spectrum": s.to_dict()}
                                          for e, s in background.records]},
                          "preliminary_source": None if preliminary is None else str(preliminary["path"])}
                preservation_verified = False
                raw_path = store.save_block([(e, {"spectrum": s.to_dict()}) for e, s in records], native=native)
                preservation_verified = True
                if error is None and cleanup_error is None:
                    self._check()
                    if kind == "background":
                        validate_blank_sequence(records, plan)
                        candidate = BackgroundSequence(records, native, experiment_contract(plan), readback, raw_path)
                        preserve(save_scan_csv, store.path / "processed" / "blank_first_scan.csv", candidate.spectrum,
                                      candidate.spectrum.normalization_signal(), background=True, publication_eligible=False)
                        result = {"kind": kind, "path": store.path, "background": candidate,
                                  "readback": readback, "plan": plan}
                    elif kind == "test":
                        spectrum = records[0][1]
                        if spectrum.pump_time_s is not None:
                            raise ValueError("Preliminary sample spectrum contains an unexpected electrical pump event")
                        values = absorbance(spectrum, background.spectrum)
                        if not np.isfinite(values).any():
                            raise ValueError("No measured wavelength support overlaps the matching buffer blank")
                        preserve(save_scan_csv, store.path / "processed" / "preliminary.csv", spectrum, values,
                                      transmission_values=transmission(spectrum, background.spectrum), publication_eligible=False)
                        preserve(save_native, store.path / "processed" / "preliminary.npz", {
                            "spectrum": spectrum.to_dict(), "absorbance": values,
                            "transmission": transmission(spectrum, background.spectrum)})
                        result = {"kind": kind, "path": store.path, "spectrum": spectrum, "absorbance": values,
                                  "experiment_contract": experiment_contract(plan), "readback": readback, "plan": plan}
                        on_scan(spectrum.wavenumber_cm1, values, "Preliminary unpumped sample absorption")
                    else:
                        progress("Reconstructing measured electrical pump times with the matching blank scan at each sequence position…")
                        reconstruction = reconstruct_sequence(records, background, plan, cancel=self._check)
                        if not np.isfinite(reconstruction["absorbance"]).any():
                            raise ValueError("No supported reconstructed absorbance cells; native records retained")
                        reconstruction.update({"experiment_contract": experiment_contract(plan), "device_settings": readback,
                                               "hf2li_resolution": readback.get("hf2li_resolution", getattr(plan, "hf2_selection", {})),
                                               "preliminary_source": str(preliminary["path"]), "run_id": store.id})
                        preserve(save_native, store.path / "processed" / "reconstruction.npz", reconstruction)
                        preserve(save_regular_reconstruction_csv, store.path / "processed" / "reconstruction.csv", reconstruction)
                        result = {"kind": kind, "path": store.path, "reconstruction": reconstruction,
                                  "readback": readback, "plan": plan}
        except KeyboardInterrupt:
            error = error or InterruptedError("Phase Scan interrupted by operator")
        except Exception as exc:
            # A failed save after cancellation must still be reported as a
            # failure, rather than claiming that the requested stop completed.
            if error is None or isinstance(error, InterruptedError):
                error = exc
            else:
                error = RuntimeError(f"Acquisition failed: {error}; subsequent processing/preservation failed: {exc}")
        finally:
            try:
                if self.cancel.is_set() and error is None:
                    error = InterruptedError("Phase Scan aborted")
                if retained and (error is not None or not preservation_verified):
                    close()
                    retained = False
                if store is not None:
                    status = ("FAILED_SAFE_STATE_UNVERIFIED" if cleanup_error else
                              "ABORTED" if isinstance(error, InterruptedError) else
                              "INCOMPLETE" if error else "COMPLETE")
                    preservation_verified_before_finish = preservation_verified
                    preservation_verified = False
                    try:
                        store.finish(status, error=str(error) if error else None,
                                     cleanup_error=str(cleanup_error) if cleanup_error else None,
                                     safe_shutdown_and_restoration_verified=not retained and cleanup_error is None,
                                     experiment_session=session_record,
                                     publication_eligible=False, status_callback_errors=list(self.status_callback_errors))
                    except BaseException:
                        close()
                        retained = False
                        raise
                    preservation_verified = preservation_verified_before_finish
                if error is None and cleanup_error is None:
                    if candidate is not None:
                        self.background = candidate
                    if kind == "test":
                        self.preliminary = result
                    if retained:
                        self._prepared_acquirer = acquirer
                        result["experiment_session"] = session_record
            finally:
                self._faulted_acquirer = acquirer if cleanup_error is not None or not preservation_verified else None
                self._active_acquirer = None
                try:
                    self._finish_hardware(ownership, retained=retained, safe_verified=cleanup_error is None,
                        preservation_verified=preservation_verified,
                        detail=f"Phase Scan outcome; cleanup={cleanup_error}; error={error}; data={store.path if store else None}")
                finally:
                    self._lock.release()
        if cleanup_error is not None:
            raise RuntimeError(f"Safe shutdown or restoration failed: {cleanup_error}. Data: {store.path if store else 'none'}") from cleanup_error
        if isinstance(error, InterruptedError):
            location = f"Data: {store.path}" if store is not None else "No run was created."
            raise InterruptedError(f"Acquisition stopped. {location}") from error
        if error is not None:
            raise RuntimeError(f"{error}. Data: {store.path if store else 'none'}") from error
        return result
