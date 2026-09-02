"""Lossless scan records and measured-coordinate absorbance reconstruction.

Raw NPZ records are self-contained, never overwritten, and load without pickle.
No checksums are required to load or process a record.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

from control_app.workflows.phase_scan import PhaseScanEvent, PhaseScanPlan, PhaseScanSettings

SCHEMA_VERSION = "phase-scan/3.0"
ANALYSIS_VERSION = "absolute-absorbance/3.0"
QCL_CURRENT_MA = 1000.0
HF2_PRESET = "campaign_sweep_qualification_candidate"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def write_json(path: Path, payload: Any) -> None:
    """Create a new JSON artifact. Existing records are never replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def save_native(path: Path, payload: Any) -> None:
    """Store nested LabOne payloads with native array dtypes, shapes and ticks."""
    arrays = {}

    def encode(value):
        if isinstance(value, (np.ndarray, np.generic)):
            key = f"array_{len(arrays):05d}"
            array = np.asarray(value)
            if array.dtype.hasobject:
                raise ValueError("Object arrays cannot be saved as native records")
            arrays[key] = array
            return {"__array__": key}
        if isinstance(value, dict):
            return {"__mapping__": [[str(k), encode(v)] for k, v in value.items()]}
        if isinstance(value, (tuple, list)):
            return [encode(item) for item in value]
        if isinstance(value, float) and not np.isfinite(value):
            return {"__nonfinite__": str(value)}
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        raise TypeError(f"Unsupported native value: {type(value).__name__}")

    tree = encode(payload)
    arrays["record_json"] = np.asarray(json.dumps(tree, allow_nan=False))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    temporary = path.with_name(path.name + f".{uuid4().hex}.partial")
    # A failed/incomplete write is retained for diagnosis, not indexed as complete.
    with temporary.open("xb") as handle:
        np.savez_compressed(handle, **arrays)
        handle.flush()
        os.fsync(handle.fileno())
    if path.exists():
        raise FileExistsError(path)
    temporary.rename(path)


def load_native(path: Path) -> Any:
    with np.load(path, allow_pickle=False) as archive:
        def decode(value):
            if isinstance(value, list):
                return [decode(item) for item in value]
            if isinstance(value, dict):
                if "__array__" in value:
                    return archive[value["__array__"]].copy()
                if "__mapping__" in value:
                    return {k: decode(v) for k, v in value["__mapping__"]}
                if "__nonfinite__" in value:
                    return float(value["__nonfinite__"])
            return value
        return decode(json.loads(str(archive["record_json"])))


def acquisition_settings(settings: PhaseScanSettings) -> dict:
    """Explicit background compatibility fields; phase/cadence do not change I0."""
    fields = asdict(settings)
    for name in ("phase_delay_us", "rest_period_s", "repetitions", "pre_pump_ms", "post_pump_ms",
                 "pump_reference", "pump_threshold_v", "missing_pulse_consecutive_limit",
                 "minimum_reconstruction_interval_coverage", "maximum_scan_missing_fraction",
                 "missing_pulse_retry_limit", "pulse_detection_threshold_fraction"):
        fields.pop(name)
    return {**fields, "qcl_current_ma": QCL_CURRENT_MA, "hf2_preset": HF2_PRESET}


class ScanStore:
    def __init__(self, root: Path, kind: str, plan: PhaseScanPlan):
        if kind not in {"run", "background", "diagnostic", "test"}:
            raise ValueError("Unknown Phase Scan record type")
        self.kind = kind
        self.id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ") + "_" + kind
        self.path = Path(root) / "Phase Scan" / datetime.now(UTC).strftime("%Y-%m-%d") / self.id
        self.path.mkdir(parents=True, exist_ok=False)
        self.record_count = 0
        write_json(self.path / "run.json", {
            "schema_version": SCHEMA_VERSION, "run_id": self.id, "kind": kind,
            "created_utc": utc_now(), "plan": plan.to_dict(),
            "acquisition_settings": acquisition_settings(plan.settings),
            "raw_format": "One self-contained NPZ per record; load with load_native, no pickle",
            "scan_index": "scan_index.jsonl", "result": "result.json",
        })

    def save_scan(self, event: PhaseScanEvent, payload: dict, *, attempt_index: int = 0) -> Path:
        if isinstance(attempt_index, bool) or int(attempt_index) != attempt_index or attempt_index < 0:
            raise ValueError("attempt_index must be a nonnegative integer")
        condition = "baseline" if not event.pump_enabled else f"phase_{event.phase_index:06d}"
        path = (self.path / "raw" / f"rep_{event.repetition:04d}" /
                f"scan_{event.scan_index:07d}_{condition}_attempt_{attempt_index:02d}.npz")
        save_native(path, {"schema_version": SCHEMA_VERSION, "event": asdict(event),
                           "attempt_index": attempt_index, **payload})
        with (self.path / "scan_index.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": asdict(event), "path": path.relative_to(self.path).as_posix(),
                                     "attempt_index": attempt_index, "bytes": path.stat().st_size,
                                     "saved_utc": utc_now()}) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.record_count += 1
        return path

    def finish(self, status: str, **details):
        write_json(self.path / "result.json", {
            "status": status, "record_count": self.record_count, "finished_utc": utc_now(), **details,
        })


@dataclass
class Spectrum:
    wavenumber_cm1: np.ndarray
    sample_r: np.ndarray
    reference_r: np.ndarray
    sample_time_s: np.ndarray
    pump_time_s: float | None
    metadata: dict
    segment_id: np.ndarray | None = None

    def validate(self):
        values = [np.asarray(v, dtype=float) for v in (self.wavenumber_cm1, self.sample_r,
                  self.reference_r, self.sample_time_s)]
        if any(v.ndim != 1 for v in values) or len({len(v) for v in values}) != 1 or len(values[0]) < 2:
            raise ValueError("A spectrum requires at least two equally sized 1D arrays")
        if not self.metadata.get("optical_valid"):
            raise ValueError("Dark/diagnostic records cannot be used as optical spectra or backgrounds")
        if self.metadata.get("wavenumber_basis") not in {"measured", "nominal_sweep_bounds"}:
            raise ValueError("Wavenumber coordinates need an explicit measured or provisional sweep-bound basis")
        if self.metadata.get("wavenumber_basis") == "nominal_sweep_bounds" and not self.metadata.get("provisional"):
            raise ValueError("Nominal coordinates must be explicitly marked provisional")
        if not np.isfinite(values[0]).all() or not np.isfinite(values[3]).all():
            raise ValueError("Wavenumber and acquisition timestamps must be finite")
        delta = np.diff(values[0])
        if not (np.all(delta > 0) or np.all(delta < 0)):
            raise ValueError("A spectrum must be one monotonic sweep segment")
        if not np.all(np.diff(values[3]) > 0):
            raise ValueError("Acquisition timestamps must increase")
        if self.segment_id is not None and np.asarray(self.segment_id).shape != values[0].shape:
            raise ValueError("Segment IDs must match spectral samples")
        return self

    def ratio(self):
        self.validate()
        sample, ref = np.asarray(self.sample_r), np.asarray(self.reference_r)
        valid = np.isfinite(sample) & np.isfinite(ref) & (sample > 0) & (ref > 0)
        ratio = np.full(sample.shape, np.nan)
        np.divide(sample, ref, out=ratio, where=valid)
        return ratio

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        return cls(**value).validate()


def interpolate_supported(x, y, target, *, max_gap=None):
    """Interpolate adjacent valid samples only: no extrapolation or gap bridging."""
    x, y, target = (np.asarray(v, dtype=float) for v in (x, y, target))
    order = np.argsort(x)
    x, y = x[order], y[order]
    result = np.full(target.shape, np.nan)
    if not len(x):
        return result
    if len(np.unique(x)) != len(x):
        raise ValueError("Duplicate interpolation coordinates")
    indices = np.searchsorted(x, target)
    exact = (indices < len(x)) & (x[np.minimum(indices, len(x)-1)] == target)
    result[exact] = y[indices[exact]]
    interior = (~exact) & (indices > 0) & (indices < len(x))
    right = indices[interior]
    left = right - 1
    width = x[right] - x[left]
    valid = np.isfinite(y[left]) & np.isfinite(y[right])
    if max_gap is not None:
        valid &= width <= max_gap
    calculated = y[left] + (target[interior]-x[left]) / width * (y[right]-y[left])
    result[interior] = np.where(valid, calculated, np.nan)
    return result


def interpolate_spectrum(spectrum: Spectrum, values, target):
    """Keep QCL gaps and native sample gaps separate when pairing spectra."""
    wn = np.asarray(spectrum.wavenumber_cm1)
    values = np.asarray(values)
    segments = np.zeros(len(wn), dtype=int) if spectrum.segment_id is None else np.asarray(spectrum.segment_id)
    result = np.full(np.asarray(target).shape, np.nan)
    for segment in np.unique(segments):
        selected = segments == segment
        if selected.sum() < 2:
            continue
        spacing = np.median(np.abs(np.diff(wn[selected])))
        part = interpolate_supported(wn[selected], values[selected], target, max_gap=spacing*1.75)
        supported = np.isfinite(part)
        result[supported] = part[supported]
    return result


def absorbance(scan: Spectrum, background: Spectrum) -> np.ndarray:
    """A = -log10[(S/R)/(S0/R0)], retaining invalid readings as gaps."""
    ratio = scan.ratio()
    reference = interpolate_spectrum(background, background.ratio(), scan.wavenumber_cm1)
    valid = np.isfinite(ratio) & np.isfinite(reference) & (ratio > 0) & (reference > 0)
    result = np.full(ratio.shape, np.nan)
    result[valid] = -np.log10(ratio[valid] / reference[valid])
    return result


def reconstruct_attempts(attempts: list[dict], background: Spectrum, plan: PhaseScanPlan, *, cancel=None) -> dict:
    """Merge aligned valid regions from all attempts, then reconstruct a surface.

    Each attempt retains its own marker-derived wavelength/time coordinates.
    Coverage weights are mapped to a common background-supported wavenumber grid;
    deficient regions remain NaN and contributor weights are retained per event
    and reconstruction wavenumber.
    """
    from control_app.workflows.phase_scan_pulse_coverage import (
        combined_interval_coverage_complete, coverage_for_wavenumbers,
    )

    pumped = [item for item in attempts if item["event"].pump_enabled]
    expected = {(r, p) for r in range(1, plan.settings.repetitions+1)
                for p in range(plan.phases_per_repetition)}
    keys = {(item["event"].repetition, item["event"].phase_index) for item in pumped}
    if keys != expected:
        raise ValueError("Reconstruction requires at least one retained attempt for every phase")
    background.validate()
    wn = np.sort(np.asarray(background.wavenumber_cm1))
    wn = wn[np.linspace(0, len(wn)-1, min(len(wn), 1024), dtype=int)]
    groups = []
    for key in sorted(expected):
        group = sorted((item for item in pumped
                        if (item["event"].repetition, item["event"].phase_index) == key),
                       key=lambda item: item["attempt_index"])
        groups.append(group)
    maximum_attempts = max(len(group) for group in groups)
    contribution_weights = np.zeros((len(groups), len(wn), maximum_attempts), dtype=np.float32)
    coverage_complete = np.zeros((len(groups), len(wn)), dtype=bool)
    event_scan_indices = np.zeros(len(groups), dtype=np.int64)
    event_repetitions = np.zeros(len(groups), dtype=np.int32)
    event_phase_indices = np.zeros(len(groups), dtype=np.int64)
    source_paths: list[list[str | None]] = []
    entries = []
    event_complete = []
    spectra_for_metadata = []
    for group_index, group in enumerate(groups):
        if cancel:
            cancel()
        event = group[0]["event"]
        event_scan_indices[group_index] = event.scan_index
        event_repetitions[group_index] = event.repetition
        event_phase_indices[group_index] = int(event.phase_index)
        source_paths.append([str(item["source"]) for item in group] + [None] * (maximum_attempts-len(group)))
        ages, values, weights, supported = [], [], [], []
        for item in group:
            spectrum = item["spectrum"].validate()
            spectra_for_metadata.append(spectrum)
            if spectrum.pump_time_s is None or not np.isfinite(spectrum.pump_time_s):
                raise ValueError("An observed pump timestamp is required for every pumped scan attempt")
            if spectrum.metadata.get("pump_time_basis") not in {"measured", "electrical_sync", "aux_input"}:
                raise ValueError("Commanded phase delays cannot substitute for measured pump timing")
            age = interpolate_spectrum(
                spectrum, np.asarray(spectrum.sample_time_s)-spectrum.pump_time_s, wn
            )
            value = interpolate_spectrum(spectrum, absorbance(spectrum, background), wn)
            fraction, acceptable = coverage_for_wavenumbers(spectrum, item["coverage"], wn)
            support = np.isfinite(age) & np.isfinite(value)
            weight = np.where(support & acceptable, fraction, 0.0)
            ages.append(age)
            values.append(value)
            weights.append(weight)
            supported.append(support)
        age_array, value_array, weight_array = np.asarray(ages), np.asarray(values), np.asarray(weights)
        supported_any = np.any(np.asarray(supported), axis=0)
        total_weight = np.sum(weight_array, axis=0)
        valid = total_weight > 0
        merged_age = np.full(len(wn), np.nan)
        merged_value = np.full(len(wn), np.nan)
        merged_age[valid] = np.sum(np.where(np.isfinite(age_array), age_array, 0.0) * weight_array,
                                          axis=0)[valid] / total_weight[valid]
        merged_value[valid] = np.sum(np.where(np.isfinite(value_array), value_array, 0.0) * weight_array,
                                            axis=0)[valid] / total_weight[valid]
        normalized = np.zeros_like(weight_array)
        np.divide(weight_array, total_weight, out=normalized, where=total_weight > 0)
        contribution_weights[group_index, :, :len(group)] = normalized.T.astype(np.float32)
        coverage_complete[group_index] = valid
        event_complete.append(bool(
            np.all(valid[supported_any]) and np.any(supported_any) and
            combined_interval_coverage_complete([item["coverage"] for item in group])
        ))
        entries.append((event, merged_age, merged_value))
    result = _reconstruct_entries(
        entries, spectra_for_metadata, background, plan, cancel=cancel, allow_empty=True
    )
    complete = bool(all(event_complete))
    quality_status = "COMPLETE" if complete else "INCOMPLETE_MISSING_PULSE_COVERAGE"
    result.update({
        "completion_status": quality_status,
        "publication_eligible": complete,
        "deficient_missing_pulse_coverage": not complete,
        "merge_event_scan_index": event_scan_indices,
        "merge_event_repetition": event_repetitions,
        "merge_event_phase_index": event_phase_indices,
        "merge_target_wavenumber_cm1": wn,
        "merge_coverage_complete": coverage_complete,
        "merge_contribution_weights": contribution_weights,
        "merge_attempt_sources": source_paths,
        "merge_weight_meaning": "normalized pulse-coverage fraction among acceptable aligned attempts",
    })
    if not complete:
        warning = ("INCOMPLETE_MISSING_PULSE_COVERAGE: deficient regions are NaN; "
                   "outputs are diagnostic only and must not be used for publication.")
        result["warnings"] = sorted(set(result["warnings"] + [warning]))
        result["limitations"] = result["limitations"] + [warning]
    return result


def aligned_attempt_coverage_complete(attempts: list[dict], background: Spectrum) -> bool:
    """Return whether aligned valid regions collectively cover one phase event."""
    from control_app.workflows.phase_scan_pulse_coverage import (
        combined_interval_coverage_complete, coverage_for_wavenumbers,
    )

    if not attempts:
        return False
    background.validate()
    wn = np.sort(np.asarray(background.wavenumber_cm1))
    wn = wn[np.linspace(0, len(wn)-1, min(len(wn), 1024), dtype=int)]
    supported_any = np.zeros(len(wn), dtype=bool)
    accepted_any = np.zeros(len(wn), dtype=bool)
    for item in attempts:
        spectrum = item["spectrum"].validate()
        values = interpolate_spectrum(spectrum, absorbance(spectrum, background), wn)
        support = np.isfinite(values)
        _, acceptable = coverage_for_wavenumbers(spectrum, item["coverage"], wn)
        supported_any |= support
        accepted_any |= support & acceptable
    return bool(
        np.any(supported_any) and np.all(accepted_any[supported_any]) and
        combined_interval_coverage_complete([item["coverage"] for item in attempts])
    )


def reconstruct(records: list[tuple[PhaseScanEvent, Spectrum]], background: Spectrum,
                plan: PhaseScanPlan, *, cancel=None) -> dict:
    """Regrid each repetition using measured per-point pump ages, then average.

    Unpumped baselines remain separate records and are not a fictitious time row.
    The grid is limited for display/storage size; all native points remain saved.
    """
    pumped = [(event, spectrum) for event, spectrum in records if event.pump_enabled]
    if len(pumped) != plan.total_pump_events:
        raise ValueError("Reconstruction requires the complete phase set in every repetition")
    expected = {(r, p) for r in range(1, plan.settings.repetitions+1) for p in range(plan.phases_per_repetition)}
    if {(e.repetition, e.phase_index) for e, _ in pumped} != expected:
        raise ValueError("Missing or duplicated phase records")
    background.validate()
    wn = np.sort(np.asarray(background.wavenumber_cm1))
    # Do not claim additional spectral information by upsampling the background.
    wn = wn[np.linspace(0, len(wn)-1, min(len(wn), 1024), dtype=int)]
    entries = []
    for event, spectrum in pumped:
        if cancel:
            cancel()
        spectrum.validate()
        if spectrum.pump_time_s is None or not np.isfinite(spectrum.pump_time_s):
            raise ValueError("An observed pump timestamp is required for every pumped scan")
        if spectrum.metadata.get("pump_time_basis") not in {"measured", "electrical_sync", "aux_input"}:
            raise ValueError("Commanded phase delays cannot substitute for measured pump timing")
        age = np.asarray(spectrum.sample_time_s) - spectrum.pump_time_s
        entries.append((event, interpolate_spectrum(spectrum, age, wn),
                        interpolate_spectrum(spectrum, absorbance(spectrum, background), wn)))
    return _reconstruct_entries(entries, [s for _, s in pumped], background, plan, cancel=cancel)


def _reconstruct_entries(entries, metadata_spectra, background, plan, *, cancel=None, allow_empty=False):
    finite_ages = [v[1][np.isfinite(v[1])] for v in entries]
    if not allow_empty and not any(len(values) for values in finite_ages):
        raise ValueError("No common measured wavelength support")
    wn = np.sort(np.asarray(background.wavenumber_cm1))
    wn = wn[np.linspace(0, len(wn)-1, min(len(wn), 1024), dtype=int)]
    step = plan.settings.phase_delay_us * 1e-6
    first = -int(np.floor(plan.settings.pre_pump_ms / 1000 / step + 1e-9))
    last = int(np.floor(plan.settings.post_pump_ms / 1000 / step + 1e-9))
    if (last-first+1)*len(wn) > 16_000_000:
        raise ValueError("Requested reconstruction exceeds 16 million cells; increase Phase Delay or narrow the time window")
    times = np.arange(first, last+1, dtype=np.int64) * step
    total = np.zeros((len(times), len(wn)))
    total2 = np.zeros_like(total)
    counts = np.zeros(total.shape, dtype=np.uint32)
    for repetition in range(1, plan.settings.repetitions+1):
        subset = [item for item in entries if item[0].repetition == repetition]
        age, values = np.asarray([item[1] for item in subset]), np.asarray([item[2] for item in subset])
        for column in range(len(wn)):
            if cancel:
                cancel()
            valid = np.isfinite(age[:, column])
            # Missing optical values remain in the interpolation vector as NaN.
            a, v = age[valid, column], values[valid, column]
            if len(a) < 2:
                continue
            # Large timing holes are unsupported; never draw across a missing phase.
            gap = max(plan.settings.phase_delay_us*1e-6 * 1.75, np.median(np.diff(np.sort(a))) * 1.75)
            result = interpolate_supported(a, v, times, max_gap=gap)
            valid = np.isfinite(result)
            total[valid, column] += result[valid]
            total2[valid, column] += result[valid]**2
            counts[valid, column] += 1
    mean = np.full(total.shape, np.nan)
    np.divide(total, counts, out=mean, where=counts > 0)
    stderr = np.full_like(mean, np.nan)
    valid = counts > 1
    stderr[valid] = np.sqrt(np.maximum(0, total2[valid] - total[valid]**2/counts[valid]) /
                            (counts[valid]-1)/counts[valid])
    bases = sorted({s.metadata.get("pump_time_basis", "unknown") for s in metadata_spectra})
    warnings = sorted({warning for s in metadata_spectra for warning in s.metadata.get("warnings", [])})
    provisional = any(s.metadata.get("provisional", False) for s in metadata_spectra) or background.metadata.get("provisional", False)
    return {"analysis_version": ANALYSIS_VERSION, "wavenumber_cm1": wn, "time_s": times,
            "absorbance": mean, "repetition_count": counts, "standard_error": stderr,
            "time_basis": "native_sample_time_minus_observed_reference", "pump_reference_bases": bases,
            "display_pump_time_ms": plan.settings.pre_pump_ms,
            "observation_window_s": [-plan.settings.pre_pump_ms/1000, plan.settings.post_pump_ms/1000],
            "provisional": provisional, "warnings": warnings,
            "limitations": ["Phase increment is not temporal resolution.",
                            "No lock-in impulse-response deconvolution or unmeasured delay correction.",
                            "Unsupported regions remain NaN; no extrapolation."]}
