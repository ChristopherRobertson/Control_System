"""Reviewed unpumped baseline and explicit continuous dual-detector acquisition."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace

import numpy as np

from control_app.workflows.phase_scan_data import save_native, utc_now, write_json
from control_app.workflows.phase_scan_runner import OPTICAL_ADAPTER_BLOCKER
from control_app.workflows.regular_phase_scan_runner import RegularPhaseScanRunner, _preservation_progress


class DualDetectorPhaseScanRunner(RegularPhaseScanRunner):
    """Keep Q0 separate from simultaneous Q and from any calibrated balance B."""

    def __init__(self, *args, calibration_provider=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.calibration_provider = calibration_provider
        self.requested_channel_balance = {}

    @property
    def baseline(self):
        return self.preliminary

    def refresh_capabilities(self):
        from control_app.workflows.dual_detector_phase_scan import DualHF2Capabilities, discover_dual_phase_scan_capabilities
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("Cannot discover settings during an acquisition")
        try:
            capabilities = (self.capability_provider or discover_dual_phase_scan_capabilities)()
            self.set_capabilities(capabilities)
            return capabilities
        except BaseException:
            if self.capabilities is not None:
                self.capabilities = replace(DualHF2Capabilities.from_dict(self.capabilities), verified=False)
            raise
        finally:
            self._lock.release()

    def configuration_preview(self, settings, overrides=None):
        from control_app.workflows.dual_detector_phase_scan import build_dual_detector_phase_scan_plan
        plan = build_dual_detector_phase_scan_plan(settings, capabilities=self.capabilities, overrides=overrides,
            channel_balance_calibration=deepcopy(self.requested_channel_balance))
        calibration = self._calibration(plan)
        return self._plan_with_calibration(plan, calibration)

    def _contract_for(self, settings_or_plan):
        from control_app.workflows.dual_detector_phase_scan_data import experiment_contract
        if hasattr(settings_or_plan, "event_at"):
            calibration = self._calibration(settings_or_plan)
            resolved = self._plan_with_calibration(settings_or_plan, calibration)
            return experiment_contract(resolved)
        return {"settings": asdict(settings_or_plan)}

    def baseline_conflicts(self, settings_or_plan):
        from control_app.workflows.dual_detector_phase_scan_data import compatibility_conflicts
        if self.preliminary is None:
            return ["Acquire and review the preliminary unpumped sample/reference spectrum"]
        try:
            expected = self._contract_for(settings_or_plan)
        except ValueError as exc:
            self.preliminary_reviewed = False
            return [str(exc)]
        saved = self.preliminary["experiment_contract"]
        if list(expected) == ["settings"]:
            saved = {"settings": saved["settings"]}
        conflicts = compatibility_conflicts(saved, expected)
        if hasattr(settings_or_plan, "event_at") and not conflicts:
            try:
                current = self._calibration(settings_or_plan)
                current_contract = None if current is None else current.contract()
                previous = self.preliminary.get("channel_balance")
                previous_contract = None if previous is None else previous.contract()
                conflicts.extend(compatibility_conflicts(previous_contract, current_contract, "channel balance"))
            except ValueError as exc:
                conflicts.append(str(exc))
        if conflicts:
            self.preliminary_reviewed = False
        return conflicts

    background_conflicts = baseline_conflicts

    def background_matches(self, settings_or_plan):
        return not self.baseline_conflicts(settings_or_plan)

    def preliminary_matches(self, settings_or_plan):
        return not self.baseline_conflicts(settings_or_plan)

    def load_background(self, path, plan=None):
        raise ValueError("Dual-detector mode measures the reference path simultaneously; a single-detector buffer blank is incompatible")

    def mark_preliminary_reviewed(self):
        if self.preliminary is None:
            raise ValueError("Acquire and inspect the preliminary unpumped sample/reference spectrum first")
        if not self.preliminary_reviewed:
            review_path = self.preliminary["path"] / "review.json"
            if review_path.exists():
                from datetime import UTC, datetime
                review_path = self.preliminary["path"] / ("review_"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")+".json")
            write_json(review_path, {
                "reviewed_utc": utc_now(), "action": "operator_confirmed_unpumped_sample_reference_review",
                "pump_acquisition_authorized": False,
                "experiment_contract": self.preliminary["experiment_contract"]})
        self.preliminary_reviewed = True

    def _calibration(self, plan):
        if self.calibration_provider is not None:
            return self.calibration_provider(plan)
        from control_app.workflows.dual_detector_phase_scan_data import load_channel_balance
        return load_channel_balance(plan=plan)

    @staticmethod
    def _plan_with_calibration(plan, calibration):
        from control_app.workflows.dual_detector_phase_scan_data import compatibility_conflicts
        requested = plan.channel_balance_calibration or {}
        actual = {} if calibration is None else calibration.contract()
        if requested:
            # An ID-only saved plan selects that bundle. A plan that already
            # resolved its validity/version also freezes those fields; runtime
            # must not silently replace it with a changed calibration contract.
            selected_fields = {key: actual[key] for key in requested if key in actual}
            conflicts = compatibility_conflicts(requested, selected_fields, "selected channel balance")
            if conflicts:
                raise ValueError("Selected channel-balance calibration is absent or changed: " + "; ".join(conflicts))
        return replace(plan, channel_balance_calibration=deepcopy(actual))

    def execute(self, kind, root, plan, *, on_scan=lambda *args: None,
                progress=lambda message: None, laser_authorized=False):
        from control_app.workflows.dual_detector_phase_scan_data import (
            DETECTOR_MODE, DualScanStore, baseline_values, compatibility_conflicts,
            experiment_contract, reconstruct_sequence, save_dual_reconstruction_csv,
            stable_device_configuration, validate_baseline,
            save_dual_spectrum_csv,
        )
        from control_app.workflows.dual_detector_phase_scan import DualDetectorPhaseScanPlan
        if kind not in {"test", "run"}:
            raise ValueError("Dual-detector mode supports preliminary sample/reference and pumped acquisitions only")
        if not isinstance(plan, DualDetectorPhaseScanPlan):
            raise ValueError("A single-detector plan cannot be used for dual-detector acquisition")
        if not self.available:
            raise RuntimeError(OPTICAL_ADAPTER_BLOCKER)
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("Dual-Detector Phase Scan is already acquiring")
        store = acquirer = result = None
        error = cleanup_error = None
        records, native_blocks = [], []
        readback = {}
        closed = False
        baseline = self.preliminary
        calibration = None
        acquisition_started_utc = None

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
            calibration = self._calibration(plan)
            plan = self._plan_with_calibration(plan, calibration)
            if kind == "test":
                self.invalidate_background()
                baseline = None
            elif self.baseline_conflicts(plan) or not self.preliminary_reviewed:
                raise ValueError("Acquire and explicitly review a compatible preliminary unpumped sample/reference spectrum before starting the pump")
            acquirer = self.acquirer_factory()
            self._active_acquirer = acquirer
            if hasattr(acquirer, "resolve_plan"):
                plan = acquirer.resolve_plan(plan)
            contract = experiment_contract(plan)
            if kind == "run":
                conflicts = self.baseline_conflicts(plan)
                if conflicts:
                    raise ValueError("Resolved experiment differs from the reviewed baseline: " + "; ".join(conflicts))
                previous = baseline.get("channel_balance")
                if compatibility_conflicts(None if previous is None else previous.contract(),
                                           None if calibration is None else calibration.contract()):
                    self.preliminary_reviewed = False
                    raise ValueError("Channel-balance calibration changed; acquire and review a new preliminary spectrum")
            store = DualScanStore(root, kind, plan)
            if hasattr(acquirer, "authorize"):
                acquirer.authorize(laser_authorized)
            acquirer.progress = progress
            progress("Checking continuous-sequence timing capacity, both detector streams and available memory…")
            readback = acquirer.prepare(plan.settings, store, self.cancel)
            self.last_readback = readback
            self._check()
            if baseline is not None:
                conflicts = compatibility_conflicts(stable_device_configuration(baseline["readback"]),
                                                     stable_device_configuration(readback), "actual instrument settings")
                if conflicts:
                    self.preliminary_reviewed = False
                    raise ValueError("Reviewed baseline incompatible after instrument configuration: " + "; ".join(conflicts))
            expected = [plan.event_at(index) for index in range(plan.total_scans if kind == "run" else 1)]
            progress("Checking the complete timing table and allocating acquisition memory…")
            blocks = acquirer.prepare_blocks(plan, expected, self.cancel)
            if len(blocks) != 1:
                raise ValueError("The full sequence must fit one continuous acquisition; no splitting is performed")
            self._check()
            progress(f"Preparing one continuous sequence of {len(expected):,} simultaneous sample/reference scans…")
            acquisition_started_utc = utc_now()
            native, captured = acquirer.capture_block(blocks[0], self.cancel)
            native_blocks.append(native)
            records.extend(captured)
            self._check()
            if [event for event, _ in records] != expected:
                raise ValueError("Acquisition returned missing, duplicate, reordered or unexpected scan records")
            for event, spectrum in records:
                if spectrum.detector_mode != DETECTOR_MODE or spectrum.reference_r is None:
                    raise ValueError("Dual-detector acquisition requires simultaneous sample and reference records")
                spectrum.metadata.update(record_role="pumped_sample_reference" if event.pump_enabled else
                    "unpumped_sample_reference_baseline", acquisition_id=store.id,
                    record_id=f"{store.id}/scan_{event.scan_index:07d}", sequence_position=event.scan_index,
                    acquisition_settings=contract, acquisition_utc=acquisition_started_utc,
                    acquisition_utc_basis="host UTC immediately before continuous capture; relative timing uses native electrical sync",
                    **{key: readback[key] for key in ("hf2li_device", "hf2li_detector_settings") if key in readback})
            close()
        except KeyboardInterrupt:
            error = InterruptedError("Dual-Detector Phase Scan interrupted by operator")
        except Exception as exc:
            error = exc
        finally:
            close()

        # Serialize all received native streams before processing. On any
        # exception the shared adapter includes its unchanged partial blocks.
        try:
            if store is not None:
                _preservation_progress(progress, "Saving available native records…")
                retained_baseline = None if baseline is None else {
                    "source": str(baseline["path"]), "spectrum": baseline["spectrum"].to_dict(),
                    "experiment_contract": baseline["experiment_contract"], "device_settings": baseline["readback"],
                    "reviewed": True, "channel_balance": None if baseline.get("channel_balance") is None else baseline["channel_balance"].to_dict()}
                native = {"blocks": native_blocks, "partial_blocks": getattr(acquirer, "partial_blocks", []),
                          "acquisition_started_utc": acquisition_started_utc,
                          "device_settings": readback, "experiment_contract": experiment_contract(plan),
                          "hf2li_requested_selected": deepcopy(plan.hf2_selection),
                          "unpumped_baseline": retained_baseline, "channel_balance": None if calibration is None else calibration.to_dict(),
                          "calculation": "Q=S/R; delta_absorbance=-log10(Q/Q0); absolute_absorbance=-log10(Q/B) only with validated B"}
                store.save_block([(event, {"spectrum": spectrum.to_dict()}) for event, spectrum in records], native=native)
                if error is None and cleanup_error is None:
                    self._check()
                    if kind == "test":
                        spectrum = records[0][1]
                        validate_baseline(spectrum, plan)
                        values = baseline_values(spectrum, calibration)
                        if not np.isfinite(values["values"]).any():
                            raise ValueError("No supported simultaneous sample/reference samples; native records retained")
                        result = {"kind": kind, "path": store.path, "spectrum": spectrum, **values,
                                  "experiment_contract": experiment_contract(plan), "readback": readback,
                                  "plan": plan, "channel_balance": calibration}
                        save_native(store.path / "processed" / "preliminary.npz", {
                            "spectrum": spectrum.to_dict(), **values,
                            "experiment_contract": experiment_contract(plan),
                            "channel_balance": None if calibration is None else calibration.to_dict()})
                        save_dual_spectrum_csv(store.path / "processed" / "preliminary.csv", spectrum, calibration)
                        on_scan(spectrum.wavenumber_cm1, values["values"], "Preliminary unpumped sample/reference spectrum")
                    else:
                        progress("Matching both detectors and the reviewed unpumped baseline by measured wavelength…")
                        reconstruction = reconstruct_sequence(records, baseline["spectrum"], plan,
                                                               calibration=calibration, cancel=self._check)
                        if not np.isfinite(reconstruction["delta_absorbance"]).any():
                            raise ValueError("No supported reconstructed delta-absorbance cells; native records retained")
                        reconstruction.update(experiment_contract=experiment_contract(plan), device_settings=readback,
                            hf2li_resolution=readback.get("hf2li_resolution", deepcopy(plan.hf2_selection)),
                            preliminary_source=str(baseline["path"]), run_id=store.id)
                        save_native(store.path / "processed" / "reconstruction.npz", reconstruction)
                        save_dual_reconstruction_csv(store.path / "processed" / "reconstruction.csv", reconstruction)
                        result = {"kind": kind, "path": store.path, "reconstruction": reconstruction,
                                  "readback": readback, "plan": plan}
        except KeyboardInterrupt:
            error = error or InterruptedError("Dual-Detector Phase Scan interrupted by operator")
        except Exception as exc:
            # Keep a retention failure visible even when the operator stopped
            # the preceding acquisition successfully.
            error = exc if error is None or isinstance(error, InterruptedError) else error
        finally:
            try:
                if self.cancel.is_set() and error is None:
                    error = InterruptedError("Dual-Detector Phase Scan aborted")
                if store is not None:
                    status = ("FAILED_SAFE_STATE_UNVERIFIED" if cleanup_error else "ABORTED" if isinstance(error, InterruptedError)
                              else "INCOMPLETE" if error else "COMPLETE")
                    store.finish(status, error=str(error) if error else None,
                                 cleanup_error=str(cleanup_error) if cleanup_error else None,
                                 safe_shutdown_and_restoration_verified=cleanup_error is None, publication_eligible=False)
                if error is None and cleanup_error is None and kind == "test":
                    self.preliminary = result
            finally:
                self._active_acquirer = None
                self._lock.release()
        if cleanup_error is not None:
            raise RuntimeError(f"Safe shutdown or restoration failed: {cleanup_error}. Data: {store.path if store else 'none'}") from cleanup_error
        if isinstance(error, InterruptedError):
            location = f"Data: {store.path}" if store is not None else "No run was created."
            raise InterruptedError(f"Acquisition stopped. {location}") from error
        if error is not None:
            raise RuntimeError(f"{error}. Data: {store.path if store else 'none'}") from error
        return result
