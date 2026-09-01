"""Cancellable background/run lifecycle independent of Qt and device transport."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock
from time import monotonic
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


class ScanAcquirer(Protocol):
    """Adapter contract: retain raw acquisition and provide measured coordinates.

    prepare returns stable read-back acquisition settings (no timestamps) and
    verifies current=1000 mA, coverage, routing and readiness. capture executes
    exactly one sweep/event and supplies native payload plus Spectrum; the
    timestamps must share a device clock. close must stop outputs on every exit.
    Provisional wavelength previews must be labeled as such. Command time is
    never substituted for an observed pump-reference timestamp.
    """
    def prepare(self, settings: PhaseScanSettings, store: ScanStore, cancel: Event) -> dict: ...
    def capture(self, event: PhaseScanEvent, cancel: Event) -> tuple[dict, Spectrum]: ...
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
        store = None
        acquirer = None
        background = self.background
        result, error, cleanup_error = None, None, None
        candidate = None
        try:
            if kind == "background":
                self.invalidate_background()
            elif not self.background_matches(plan.settings):
                raise ValueError("Capture a successful background at these acquisition settings first")
            store = ScanStore(root, kind, plan)
            self._check()
            if kind == "run":
                time_points = int((plan.settings.pre_pump_ms+plan.settings.post_pump_ms)*1000/plan.settings.phase_delay_us)+1
                if time_points * min(len(background.spectrum.wavenumber_cm1), 1024) > 16_000_000:
                    raise ValueError("Requested reconstruction exceeds 16 million cells; increase Phase Delay or narrow the time window")
            acquirer = self.acquirer_factory()
            self._active_acquirer = acquirer
            if hasattr(acquirer, "authorize"):
                acquirer.authorize(laser_authorized)
            acquirer.progress = progress
            progress("Preparing acquisition and recording device settings…")
            readback = acquirer.prepare(plan.settings, store, self.cancel)
            self._check()
            if kind != "background" and not compatible_readbacks(background.device_settings, readback):
                self.invalidate_background()
                raise ValueError("Instrument settings changed since the background; capture it again")
            if kind == "background":
                event = plan.event_at(0)
                native, spectrum = acquirer.capture(event, self.cancel)
                # Preserve data even when validation/processing subsequently rejects it.
                path = store.save_scan(event, {"native": native, "spectrum": spectrum.to_dict()})
                self._check()
                spectrum.validate()
                if np.isfinite(spectrum.ratio()).sum() < 2:
                    raise ValueError("Background has fewer than two valid detector samples; no valid I0 reference")
                save_scan_csv(store.path / "processed" / "background.csv", spectrum, spectrum.ratio(), background=True)
                candidate = Background(spectrum, native, acquisition_settings(plan.settings), readback, path)
                result = {"kind": kind, "path": store.path, "background": candidate}
            else:
                save_native(store.path / "background" / "background.npz", {
                    "source": str(background.path), "native": background.native,
                    "spectrum": background.spectrum.to_dict(), "settings": background.settings,
                    "device_settings": background.device_settings,
                })
                records = []
                previous_start = None
                scan_count = 1 if kind == "test" else plan.total_scans
                for index in range(scan_count):
                    if previous_start is not None:
                        self.cancel.wait(max(0, plan.settings.rest_period_s - (monotonic()-previous_start)))
                    self._check()
                    event = plan.event_at(index)
                    progress(f"Scan {index+1:,}/{scan_count:,} · set {event.repetition}")
                    previous_start = monotonic()
                    native, spectrum = acquirer.capture(event, self.cancel)
                    raw_path = store.save_scan(event, {"native": native, "spectrum": spectrum.to_dict()})
                    self._check()
                    values = absorbance(spectrum, background.spectrum)
                    if not np.isfinite(values).any():
                        raise ValueError("No valid absorbance samples overlap this background; raw scan retained")
                    age = (np.asarray(spectrum.sample_time_s) - spectrum.pump_time_s
                           if spectrum.pump_time_s is not None else np.full(values.shape, np.nan))
                    save_native(store.path / "processed" / "scans" / raw_path.name,
                                {"wavenumber_cm1": spectrum.wavenumber_cm1, "absorbance": values,
                                 "time_after_pump_s": age, "source": raw_path.relative_to(store.path).as_posix(),
                                 "coordinate_metadata": spectrum.metadata, "segment_id": spectrum.segment_id,
                                 "background_coordinate_metadata": background.spectrum.metadata})
                    records.append((event, spectrum))
                    save_scan_csv(store.path / "processed" / "scans" / raw_path.with_suffix(".csv").name, spectrum, values)
                    label = f"Scan {index+1:,} · set {event.repetition}"
                    if spectrum.metadata.get("provisional") or background.spectrum.metadata.get("provisional"):
                        label += " · PROVISIONAL wavenumber axis"
                    on_scan(spectrum.wavenumber_cm1, values, label)
                    if kind == "test":
                        result = {"kind": kind, "path": store.path, "spectrum": spectrum, "absorbance": values,
                                  "warnings": sorted(set(spectrum.metadata.get("warnings", []) + background.spectrum.metadata.get("warnings", [])))}
                if kind != "test":
                    progress("Reconstructing observed wavelength/time coordinates and averaging repetitions…")
                    reconstruction = reconstruct(records, background.spectrum, plan, cancel=self._check)
                    if not np.isfinite(reconstruction["absorbance"]).any():
                        raise ValueError("No supported absorbance surface in the selected window; native data retained for diagnosis")
                    save_native(store.path / "processed" / "reconstruction.npz", reconstruction)
                    result = {"kind": kind, "path": store.path, "reconstruction": reconstruction}
        except Exception as exc:
            error = exc
        finally:
            if acquirer is not None:
                try:
                    acquirer.close()
                except Exception as exc:
                    cleanup_error = exc
            try:
                if store is not None:
                    status = ("FAILED_SAFE_STATE_UNVERIFIED" if cleanup_error else
                              "ABORTED" if isinstance(error, InterruptedError) or self.cancel.is_set() else
                              "FAILED" if error else "COMPLETE")
                    store.finish(status, error=str(error) if error else None,
                                 cleanup_error=str(cleanup_error) if cleanup_error else None)
                if self.cancel.is_set() and error is None:
                    error = InterruptedError("Phase Scan aborted")
                if candidate is not None and error is None and cleanup_error is None:
                    self.background = candidate
            finally:
                self._active_acquirer = None
                self._lock.release()
        if cleanup_error:
            raise RuntimeError(f"Safe shutdown failed: {cleanup_error}. Data: {store.path}") from cleanup_error
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


def save_scan_csv(path, spectrum, values, *, background=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    ages = np.full(len(values), np.nan) if spectrum.pump_time_s is None else np.asarray(spectrum.sample_time_s)-spectrum.pump_time_s
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["wavenumber_cm-1", "background_S0_R0" if background else "absorbance",
                         "reference_relative_time_s", "sample_R_V", "reference_R_V", "wavenumber_basis", "pump_time_basis"])
        for wn, value, age, sample, reference in zip(spectrum.wavenumber_cm1, values, ages, spectrum.sample_r, spectrum.reference_r):
            writer.writerow([wn, value, age, sample, reference, spectrum.metadata.get("wavenumber_basis"),
                             spectrum.metadata.get("pump_time_basis", "unpumped")])
