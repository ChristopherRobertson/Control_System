"""Lossless scan records and measured-coordinate absorbance reconstruction.

Raw NPZ records are self-contained, never overwritten, and load without pickle.
No checksums are required to load or process a record.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import math
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

from control_app.workflows.phase_scan import PhaseScanEvent, PhaseScanPlan, PhaseScanSettings

SCHEMA_VERSION = "phase-scan/5.0"
ANALYSIS_VERSION = "absolute-absorbance/4.1"
QCL_CURRENT_MA = 750.0
HF2_PRESET = "exploratory_phase_scan_single_detector"
SINGLE_DETECTOR_MODE = "single_ch1_buffer_blank"
DUAL_DETECTOR_MODE = "dual_detector"
DETECTOR_INPUT = "HF2LI CH1 SIG IN +"


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


def save_native(path: Path, payload: Any, *, compressed: bool = True) -> None:
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
        writer = np.savez_compressed if compressed else np.savez
        writer(handle, **arrays)
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
                 "pump_reference"):
        fields.pop(name)
    return {**fields, "qcl_current_ma": QCL_CURRENT_MA, "hf2_preset": HF2_PRESET,
            "detector_mode": SINGLE_DETECTOR_MODE, "detector_input": DETECTOR_INPUT,
            "normalization": "CH1_sample / prior_CH1_buffer_blank"}


def compatible_readbacks(left, right):
    """Compare settings with one shared tolerance for device readback rounding."""
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(compatible_readbacks(left[k], right[k]) for k in left)
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(compatible_readbacks(a, b) for a, b in zip(left, right))
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-12)
    return left == right


class ScanStore:
    """Save the retained finite acquisition once, after timing has stopped."""

    def __init__(self, root: Path, kind: str, plan: PhaseScanPlan, *, compress_raw: bool = True):
        if kind not in {"run", "background", "diagnostic", "test"}:
            raise ValueError("Unknown Phase Scan record type")
        self.kind = kind
        self.id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ") + "_" + kind
        self.path = Path(root) / "Phase Scan" / datetime.now(UTC).strftime("%Y-%m-%d") / self.id
        self.path.mkdir(parents=True, exist_ok=False)
        self.record_count = 0
        self.compress_raw = bool(compress_raw)
        write_json(self.path / "run.json", {
            "schema_version": SCHEMA_VERSION, "run_id": self.id, "kind": kind,
            "created_utc": utc_now(), "plan": plan.to_dict(),
            "run_classification": "EXPLORATORY_PROOF_OF_CONCEPT",
            "publication_eligible": False,
            "publication_warning": "Preliminary proof-of-concept output only; not validated or eligible for publication.",
            "acquisition_settings": acquisition_settings(plan.settings),
            "raw_format": ("Diagnostic records; load with load_native, no pickle" if kind == "diagnostic" else
                           "One consolidated acquisition NPZ; load with load_native, no pickle"),
            "raw_storage": {
                "save_after_acquisition": True,
                "compressed": self.compress_raw,
                "completion_rule": "The retained acquisition is atomically saved before analysis and result.json",
            },
            "scan_index": "scan_index.jsonl", "result": "result.json",
        })

    def save_block(self, records: list[tuple[PhaseScanEvent, dict]], *, native=None) -> Path:
        """Persist nominal records and native bounded blocks without discarding partial data.

        The caller owns acquisition timing and calls this only after the block
        sequence has completed or stopped. A run has exactly one raw artifact.
        """
        path = self.path / "raw" / "acquisition.npz"
        payload = {"schema_version": SCHEMA_VERSION,
                   "records": [{**values, "event": asdict(event)} for event, values in records],
                   "native": native}
        save_native(path, payload, compressed=self.compress_raw)
        self.record_count = len(records)
        saved = utc_now()
        with (self.path / "scan_index.jsonl").open("x", encoding="utf-8") as handle:
            for index, (event, _) in enumerate(records):
                handle.write(json.dumps({"event": asdict(event),
                                         "path": path.relative_to(self.path).as_posix(),
                                         "record_index": index, "saved_utc": saved}) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return path

    def save_scan(self, event: PhaseScanEvent, payload: dict) -> Path:
        """Retain compatibility for the separate inhibited timing diagnostic."""
        if self.kind != "diagnostic":
            raise RuntimeError("Optical Phase Scan records must be saved as a consolidated block")
        path = self.path / "raw" / f"scan_{event.scan_index:07d}.npz"
        save_native(path, {"schema_version": SCHEMA_VERSION, **payload, "event": asdict(event)},
                    compressed=self.compress_raw)
        with (self.path / "scan_index.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": asdict(event), "path": path.relative_to(self.path).as_posix(),
                                     "bytes": path.stat().st_size, "saved_utc": utc_now()}) + "\n")
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
    reference_r: np.ndarray | None
    sample_time_s: np.ndarray
    pump_time_s: float | None
    metadata: dict
    segment_id: np.ndarray | None = None

    @property
    def detector_mode(self):
        # Version 4 and earlier spectra contain actual simultaneous reference
        # observations. Absence of the mode never invents a reference detector.
        mode = self.metadata.get("detector_mode", DUAL_DETECTOR_MODE)
        if mode not in {SINGLE_DETECTOR_MODE, DUAL_DETECTOR_MODE}:
            raise ValueError(f"Unknown detector mode: {mode}")
        return mode

    def validate(self):
        values = [np.asarray(v, dtype=float) for v in (self.wavenumber_cm1, self.sample_r,
                  self.sample_time_s)]
        if self.detector_mode == SINGLE_DETECTOR_MODE:
            if self.reference_r is not None:
                raise ValueError("Single-detector spectra must not contain a CH2 reference array")
            if self.metadata.get("detector_input", DETECTOR_INPUT) != DETECTOR_INPUT:
                raise ValueError("Single-detector spectra require HF2LI CH1 SIG IN +")
        else:
            if self.reference_r is None:
                raise ValueError("Legacy dual-detector spectra require actual reference samples")
            values.append(np.asarray(self.reference_r, dtype=float))
        if any(v.ndim != 1 for v in values) or len({len(v) for v in values}) != 1 or len(values[0]) < 2:
            raise ValueError("A spectrum requires at least two equally sized 1D arrays")
        if not self.metadata.get("optical_valid"):
            raise ValueError("Dark/diagnostic records cannot be used as optical spectra or backgrounds")
        basis = self.metadata.get("wavenumber_basis")
        if basis not in {"measured", "controller_markers", "nominal_sweep_bounds"}:
            raise ValueError("Wavenumber coordinates need an explicit measured, controller-marker, or provisional sweep-bound basis")
        if basis in {"controller_markers", "nominal_sweep_bounds"} and not self.metadata.get("provisional"):
            raise ValueError("Controller or nominal coordinates must be explicitly marked provisional")
        if basis == "controller_markers" and not self.metadata.get("marker_identity_basis"):
            raise ValueError("Controller-marker coordinates require explicit marker readback provenance")
        if not np.isfinite(values[0]).all() or not np.isfinite(values[2]).all():
            raise ValueError("Wavenumber and acquisition timestamps must be finite")
        delta = np.diff(values[0])
        if not (np.all(delta > 0) or np.all(delta < 0)):
            raise ValueError("A spectrum must be one monotonic sweep segment")
        if not np.all(np.diff(values[2]) > 0):
            raise ValueError("Acquisition timestamps must increase")
        if self.segment_id is not None and np.asarray(self.segment_id).shape != values[0].shape:
            raise ValueError("Segment IDs must match spectral samples")
        return self

    def ratio(self):
        self.validate()
        if self.detector_mode != DUAL_DETECTOR_MODE:
            raise ValueError("A single-detector ratio requires a separate buffer blank; use transmission")
        sample, ref = np.asarray(self.sample_r), np.asarray(self.reference_r)
        valid = np.isfinite(sample) & np.isfinite(ref) & (sample > 0) & (ref > 0)
        ratio = np.full(sample.shape, np.nan)
        np.divide(sample, ref, out=ratio, where=valid)
        return ratio

    def normalization_signal(self):
        """Measured CH1 magnitude, or an actual legacy simultaneous S/R ratio."""
        self.validate()
        if self.detector_mode == DUAL_DETECTOR_MODE:
            return self.ratio()
        signal = np.asarray(self.sample_r, dtype=float)
        return np.where(np.isfinite(signal) & (signal > 0), signal, np.nan)

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
    left_candidate = np.clip(indices-1, 0, len(x)-1)
    right_candidate = np.minimum(indices, len(x)-1)
    nearest = np.where(np.abs(target-x[left_candidate]) <= np.abs(target-x[right_candidate]),
                       left_candidate, right_candidate)
    # Subtracting measured floating-point timestamps can displace an endpoint
    # by a few ULPs. Treat numerical equality as an observed point, so the
    # requested -1 ms/+5 ms boundaries do not become artificial empty rows.
    tolerance = 8 * np.finfo(float).eps * max(1., float(np.max(np.abs(x))))
    exact = np.abs(target-x[nearest]) <= tolerance
    result[exact] = y[nearest[exact]]
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


def _average_duplicate_coordinates(x, y):
    """Average observations that share one measured coordinate.

    Adjacent phase commands can resolve to the same native HF2LI tick when the
    requested phase increment is close to the timing-stream sample interval.
    They are repeated observations at one measured time, not an invalid axis.
    """
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    unique, inverse = np.unique(x, return_inverse=True)
    if len(unique) == len(x):
        return x, y
    finite = np.isfinite(y)
    total = np.zeros(len(unique), dtype=float)
    count = np.zeros(len(unique), dtype=np.uint32)
    np.add.at(total, inverse[finite], y[finite])
    np.add.at(count, inverse[finite], 1)
    averaged = np.full(len(unique), np.nan)
    np.divide(total, count, out=averaged, where=count > 0)
    return unique, averaged


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


def absorbance_from_ratios(ratio, reference) -> np.ndarray:
    """Apply the logarithm after matched transmission ratios have been formed."""
    ratio, reference = np.asarray(ratio, dtype=float), np.asarray(reference, dtype=float)
    if ratio.shape != reference.shape:
        raise ValueError("Sample/reference and background ratios must have matching shapes")
    valid = np.isfinite(ratio) & np.isfinite(reference) & (ratio > 0) & (reference > 0)
    result = np.full(ratio.shape, np.nan)
    result[valid] = -np.log10(ratio[valid] / reference[valid])
    return result


def transmission(scan: Spectrum, background: Spectrum) -> np.ndarray:
    """Pair CH1 sample and prior buffer blank on supported wavenumbers.

    Legacy dual-detector spectra retain their ratio-of-ratios normalization.
    A sample baseline cannot serve as the buffer blank for the experiment.
    """
    signal = scan.normalization_signal()
    reference_signal = background.normalization_signal()
    if scan.detector_mode != background.detector_mode:
        raise ValueError("Sample and background detector modes must match")
    if scan.metadata["wavenumber_basis"] != background.metadata["wavenumber_basis"]:
        raise ValueError("Sample and background wavenumber bases must match; rederive both on the same supported coordinate basis")
    if scan.detector_mode == SINGLE_DETECTOR_MODE:
        if background.metadata.get("record_role") != "buffer_blank" or background.pump_time_s is not None:
            raise ValueError("Single-detector normalization requires an unpumped buffer blank")
        for key in ("acquisition_settings", "hf2li_detector_settings", "hf2li_device"):
            if (key in scan.metadata or key in background.metadata) and not compatible_readbacks(scan.metadata.get(key), background.metadata.get(key)):
                raise ValueError(f"Sample and buffer blank {key} must match")
    reference = interpolate_spectrum(background, reference_signal, scan.wavenumber_cm1)
    valid = np.isfinite(signal) & np.isfinite(reference) & (signal > 0) & (reference > 0)
    result = np.full(signal.shape, np.nan)
    np.divide(signal, reference, out=result, where=valid)
    return result


def absorbance(scan: Spectrum, background: Spectrum) -> np.ndarray:
    """A = -log10(CH1_sample/CH1_blank), preserving legacy paired ratios."""
    ratio = transmission(scan, background)
    result = np.full(ratio.shape, np.nan)
    valid = np.isfinite(ratio) & (ratio > 0)
    result[valid] = -np.log10(ratio[valid])
    return result


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


def _reconstruct_entries(entries, metadata_spectra, background, plan, *, cancel=None, strict_phase_gaps=False):
    finite_ages = [v[1][np.isfinite(v[1])] for v in entries]
    if not any(len(values) for values in finite_ages):
        raise ValueError("No common measured wavelength support")
    wn = np.sort(np.asarray(background.wavenumber_cm1))
    wn = wn[np.linspace(0, len(wn)-1, min(len(wn), 1024), dtype=int)]
    step = plan.settings.phase_delay_us * 1e-6
    start = -plan.settings.pre_pump_ms / 1000
    stop = plan.settings.post_pump_ms / 1000
    first = -int(np.floor(-start / step + 1e-9))
    last = int(np.floor(stop / step + 1e-9))
    if (last-first+1)*len(wn) > 16_000_000:
        raise ValueError("Requested reconstruction exceeds 16 million cells; increase Phase Delay or narrow the time window")
    regular = np.arange(first, last+1, dtype=np.int64) * step
    tolerance = 8 * np.finfo(float).eps * max(1., abs(start), abs(stop))
    interior = regular[(regular > start+tolerance) & (regular < stop-tolerance)]
    # Keep the requested endpoints even when the nominal step does not divide
    # the observation interval. Only these boundary intervals are shorter.
    times = np.concatenate(([start], interior, [stop]))
    if len(times)*len(wn) > 16_000_000:
        raise ValueError("Requested reconstruction exceeds 16 million cells; increase Phase Delay or narrow the time window")
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
            a, v = _average_duplicate_coordinates(a, v)
            if len(a) < 2:
                continue
            # Large timing holes are unsupported; never draw across a missing phase.
            gap = plan.settings.phase_delay_us*1e-6 * 1.75
            if not strict_phase_gaps:
                gap = max(gap, np.median(np.diff(np.sort(a))) * 1.75)
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
    wavenumber_bases = sorted({s.metadata.get("wavenumber_basis") for s in [*metadata_spectra, background]})
    warnings = sorted({warning for s in [*metadata_spectra, background] for warning in s.metadata.get("warnings", [])})
    provisional = any(s.metadata.get("provisional", False) for s in metadata_spectra) or background.metadata.get("provisional", False)
    single_detector = background.detector_mode == SINGLE_DETECTOR_MODE
    normalization = "-log10(CH1_sample / prior_CH1_buffer_blank)" if single_detector else "-log10((S/R)/(S0/R0))"
    limitations = ["Phase increment is not temporal resolution.",
                  "No lock-in impulse-response deconvolution or unmeasured delay correction.",
                  "Unsupported regions remain NaN; no extrapolation."]
    if "controller_markers" in wavenumber_bases:
        limitations.append("Wavenumber coordinates follow observed markers and verified controller readbacks; independent absolute wavelength calibration is not established.")
    if single_detector:
        limitations.extend(["The prior buffer blank is a sequential intensity reference; laser and detector drift are not canceled by a simultaneous reference channel.",
                            "Standard error describes repetition scatter conditional on the saved blank; shared buffer-blank uncertainty is not propagated.",
                            "Unpumped sample baselines remain separate from the buffer blank; output is absorbance relative to the buffer blank, not pump-induced delta absorbance."])
    return {"analysis_version": ANALYSIS_VERSION, "wavenumber_cm1": wn, "time_s": times,
            "detector_mode": background.detector_mode, "normalization": normalization,
            "wavenumber_bases": wavenumber_bases,
            "background_role": background.metadata.get("record_role", "legacy_background"),
            "absorbance": mean, "repetition_count": counts, "standard_error": stderr,
            "time_basis": "native_sample_time_minus_observed_reference", "pump_reference_bases": bases,
            "display_pump_time_ms": 0.,
            "observation_window_s": [-plan.settings.pre_pump_ms/1000, plan.settings.post_pump_ms/1000],
            "provisional": provisional, "warnings": warnings,
            "limitations": limitations}
