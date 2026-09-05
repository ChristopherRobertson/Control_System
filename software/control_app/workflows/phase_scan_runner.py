"""Finite phase acquisition, consolidated retention, and single-pass reconstruction."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock
from typing import Protocol
import csv
import math

import numpy as np

from control_app.workflows.phase_scan import PhaseScanEvent, PhaseScanPlan, PhaseScanSettings
from control_app.workflows.phase_scan_data import (
    ScanStore, Spectrum, absorbance, acquisition_settings, reconstruct, save_native,
)

OPTICAL_ADAPTER_BLOCKER = (
    "No optical acquisition adapter is attached in this session. "
    "Use the normal hardware-enabled GUI launcher for optical scans."
)
RUN_CLASSIFICATION = "EXPLORATORY_PROOF_OF_CONCEPT"
PUBLICATION_WARNING = (
    "EXPLORATORY_PROOF_OF_CONCEPT: preliminary output only; not validated or eligible for publication."
)


class ScanAcquirer(Protocol):
    """Preflight all blocks, acquire preloaded sequences, and retain partial data.

    capture_block arms LabOne before starting the timing table and reads after
    completion. No disk writes occur there. close is idempotent and attempts
    every safe-state action even if an earlier action fails.
    """
    def prepare(self, settings: PhaseScanSettings, store: ScanStore, cancel: Event) -> dict: ...
    def prepare_blocks(self, plan: PhaseScanPlan, events: list[PhaseScanEvent], cancel: Event) -> list: ...
    def capture_block(self, block, cancel: Event) -> tuple[dict, list[tuple[PhaseScanEvent, Spectrum]]]: ...
    def close(self) -> None: ...


@dataclass
class Background:
    spectrum: Spectrum
    native: dict
    settings: dict
    device_settings: dict
    path: Path


class PhaseScanRunner:
    def __init__(self, acquirer_factory=None):
        self.acquirer_factory = acquirer_factory
        self.background: Background | None = None
        self.cancel = Event()
        self._lock = Lock()
        self._active_acquirer = None

    @property
    def available(self):
        return self.acquirer_factory is not None

    def background_matches(self, settings):
        return self.background is not None and self.background.settings == acquisition_settings(settings)

    def invalidate_background(self):
        self.background = None

    def abort(self):
        self.cancel.set()

    def _check(self):
        if self.cancel.is_set():
            raise InterruptedError("Phase Scan aborted")

    def execute(self, kind: str, root: Path, plan: PhaseScanPlan, *, on_scan=lambda *args: None,
                progress=lambda text: None, laser_authorized=False) -> dict:
        if kind not in {"background", "run", "test"}:
            raise ValueError("Unknown acquisition operation")
        if not self.available:
            raise RuntimeError(OPTICAL_ADAPTER_BLOCKER)
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("Phase Scan is already running")
        store = acquirer = result = candidate = None
        error = cleanup_error = None
        closed = False
        records, native_blocks = [], []
        background, readback = self.background, {}

        def close_acquirer():
            nonlocal closed, cleanup_error
            if acquirer is not None and not closed:
                closed = True
                try:
                    acquirer.close()
                except BaseException as exc:
                    cleanup_error = exc

        try:
            self._check()
            if kind == "background":
                self.invalidate_background()
            elif not self.background_matches(plan.settings):
                raise ValueError("Capture a successful background at these acquisition settings first")
            acquirer = self.acquirer_factory()
            self._active_acquirer = acquirer
            if hasattr(acquirer, "resolve_plan"):
                plan = acquirer.resolve_plan(plan)
            store = ScanStore(root, kind, plan)
            if hasattr(acquirer, "authorize"):
                acquirer.authorize(laser_authorized)
            acquirer.progress = progress
            progress("Preparing finite acquisition and verifying retention capacity…")
            readback = acquirer.prepare(plan.settings, store, self.cancel)
            self._check()
            if kind != "background" and not compatible_readbacks(background.device_settings, readback):
                self.invalidate_background()
                raise ValueError("Instrument settings changed since the background; capture it again")
            if kind == "run":
                points = int((plan.settings.pre_pump_ms + plan.settings.post_pump_ms)
                             * 1000 / plan.settings.phase_delay_us) + 3
                if points * min(len(background.spectrum.wavenumber_cm1), 1024) > 16_000_000:
                    raise ValueError("Requested reconstruction exceeds 16 million cells; increase Phase Delay or narrow the time window")
            expected = [plan.event_at(i) for i in range(plan.total_scans if kind == "run" else 1)]
            blocks = acquirer.prepare_blocks(plan, expected, self.cancel)
            if not blocks:
                raise ValueError("Finite acquisition preflight produced no blocks")
            self._check()
            for index, block in enumerate(blocks):
                self._check()
                progress(f"Acquiring finite block {index + 1}/{len(blocks)}; data retained in LabOne…")
                native, captured = acquirer.capture_block(block, self.cancel)
                native_blocks.append(native)
                records.extend(captured)
                self._check()
            close_acquirer()
            if cleanup_error:
                raise RuntimeError(f"Safe shutdown failed: {cleanup_error}")
            if [event for event, _ in records] != expected:
                raise ValueError("Acquisition integrity: missing, duplicated, reordered, or unexpected frame records")
        except KeyboardInterrupt:
            error = InterruptedError("Phase Scan interrupted by operator")
        except Exception as exc:
            error = exc
        finally:
            close_acquirer()

        # Serialize once after timing has stopped, including all available data
        # when acquisition, integrity validation, or operator cancellation fails.
        try:
            if acquirer is not None:
                native_blocks.extend(getattr(acquirer, "partial_blocks", []))
            if store is not None:
                native = {"blocks": native_blocks, "device_settings": readback}
                if background is not None and kind != "background":
                    native["background"] = {
                        "source": str(background.path), "native": background.native,
                        "spectrum": background.spectrum.to_dict(), "settings": background.settings,
                        "device_settings": background.device_settings,
                    }
                raw_path = store.save_block(
                    [(event, {"spectrum": spectrum.to_dict()}) for event, spectrum in records], native=native)
                if error is None and cleanup_error is None:
                    self._check()
                    for _, spectrum in records:
                        spectrum.validate()
                    if kind == "background":
                        spectrum = records[0][1]
                        if np.isfinite(spectrum.ratio()).sum() < 2:
                            raise ValueError("Background has fewer than two valid detector samples; no valid I0 reference")
                        save_scan_csv(store.path / "processed" / "background.csv", spectrum, spectrum.ratio(),
                                      background=True, run_quality_status=RUN_CLASSIFICATION, publication_eligible=False)
                        candidate = Background(spectrum, native, acquisition_settings(plan.settings), readback, raw_path)
                        result = {"kind": kind, "path": store.path, "background": candidate}
                    else:
                        for event, spectrum in records:
                            self._check()
                            values = absorbance(spectrum, background.spectrum)
                            if not np.isfinite(values).any():
                                raise ValueError("No valid absorbance samples overlap this background; native block retained")
                            on_scan(spectrum.wavenumber_cm1, values,
                                    f"Scan {event.scan_index + 1:,}/{len(records):,} · set {event.repetition}")
                        if kind == "test":
                            spectrum = records[0][1]
                            save_scan_csv(store.path / "processed" / "test.csv", spectrum, values,
                                          run_quality_status=RUN_CLASSIFICATION, publication_eligible=False)
                            result = {"kind": kind, "path": store.path, "spectrum": spectrum, "absorbance": values,
                                      "run_classification": RUN_CLASSIFICATION, "publication_eligible": False,
                                      "warnings": sorted(set(spectrum.metadata.get("warnings", []) +
                                                             background.spectrum.metadata.get("warnings", []) +
                                                             [PUBLICATION_WARNING]))}
                        else:
                            progress("Reconstructing the complete nominal dataset using measured pump times…")
                            reconstruction = reconstruct(records, background.spectrum, plan, cancel=self._check)
                            reconstruction.update({"completion_status": "COMPLETE", "publication_eligible": False,
                                                   "run_classification": RUN_CLASSIFICATION})
                            reconstruction["warnings"] = sorted(set(reconstruction.get("warnings", []) + [PUBLICATION_WARNING]))
                            reconstruction["limitations"] = list(reconstruction.get("limitations", [])) + [PUBLICATION_WARNING]
                            if not np.isfinite(reconstruction["absorbance"]).any():
                                raise ValueError("No supported absorbance surface in the selected window; native block retained")
                            save_native(store.path / "processed" / "reconstruction.npz", reconstruction)
                            save_reconstruction_csv(store.path / "processed" / "reconstruction.csv", reconstruction)
                            result = {"kind": kind, "path": store.path, "reconstruction": reconstruction}
        except KeyboardInterrupt:
            error = error or InterruptedError("Phase Scan interrupted by operator")
        except Exception as exc:
            error = error or exc
        finally:
            try:
                if self.cancel.is_set() and error is None:
                    error = InterruptedError("Phase Scan aborted")
                if store is not None:
                    status = ("FAILED_SAFE_STATE_UNVERIFIED" if cleanup_error else
                              "ABORTED" if isinstance(error, InterruptedError) or self.cancel.is_set() else
                              "INCOMPLETE" if error else "COMPLETE")
                    store.finish(status, error=str(error) if error else None,
                                 cleanup_error=str(cleanup_error) if cleanup_error else None,
                                 run_classification=RUN_CLASSIFICATION, publication_eligible=False,
                                 publication_warning=PUBLICATION_WARNING)
                if candidate is not None and error is None and cleanup_error is None:
                    self.background = candidate
            finally:
                self._active_acquirer = None
                self._lock.release()
        if cleanup_error:
            raise RuntimeError(f"Safe shutdown failed: {cleanup_error}. Data: {store.path if store else 'none'}") from cleanup_error
        if error:
            raise RuntimeError(f"{error}. Data: {store.path if store else 'none'}") from error
        return result


def compatible_readbacks(left, right):
    """Compare acquisition settings without rejecting harmless float readback rounding."""
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(compatible_readbacks(left[k], right[k]) for k in left)
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(compatible_readbacks(a, b) for a, b in zip(left, right))
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-12)
    return left == right


def save_reconstruction_csv(path, reconstruction):
    path.parent.mkdir(parents=True, exist_ok=True)
    quality = reconstruction.get("completion_status", "UNKNOWN")
    eligible = bool(reconstruction.get("publication_eligible", False))
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["wavenumber_cm-1", "time_after_pump_s", "absorbance", "standard_error",
                         "repetition_count", "run_quality_status", "publication_eligible"])
        for row, time_s in enumerate(reconstruction["time_s"]):
            for column, wn in enumerate(reconstruction["wavenumber_cm1"]):
                writer.writerow([wn, time_s, reconstruction["absorbance"][row, column],
                                 reconstruction["standard_error"][row, column],
                                 reconstruction["repetition_count"][row, column], quality, eligible])


def save_scan_csv(path, spectrum, values, *, background=False,
                  run_quality_status="COMPLETE", publication_eligible=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    ages = np.full(len(values), np.nan) if spectrum.pump_time_s is None else np.asarray(spectrum.sample_time_s)-spectrum.pump_time_s
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["wavenumber_cm-1", "background_S0_R0" if background else "absorbance",
                         "reference_relative_time_s", "sample_R_V", "reference_R_V", "wavenumber_basis",
                         "pump_time_basis", "run_quality_status", "publication_eligible"])
        for wn, value, age, sample, reference in zip(spectrum.wavenumber_cm1, values, ages, spectrum.sample_r, spectrum.reference_r):
            writer.writerow([wn, value, age, sample, reference, spectrum.metadata.get("wavenumber_basis"),
                             spectrum.metadata.get("pump_time_basis", "unpumped"),
                             run_quality_status, publication_eligible])
