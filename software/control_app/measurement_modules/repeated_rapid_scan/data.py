"""Versioned native records for repeated movies; no hardware imports or hash gates.

Native arrays deliberately remain unchanged, including integer device ticks, NaNs,
rejected data and partial records. Derived coordinates live in separate records.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

EXPERIMENT_ID = "repeated_rapid_scan"
SCHEMA_VERSION = 1
ANALYSIS_VERSION = "rrs-native-1"


@dataclass(frozen=True)
class ClockCorrection:
    """common seconds = (native-origin)*unit*scale + offset - latency.

    Offset includes a documented shared epoch, not an invented pump phase.
    """
    clock_id: str
    offset_s: float = 0.0
    scale: float = 1.0
    latency_s: float = 0.0
    calibration_id: str = ""
    uncertainty_s: float | None = None
    description: str = ""


@dataclass(frozen=True)
class NativeStream:
    timestamps_s: Any
    values: Any
    variance: Any = None
    flags: Mapping[str, Any] = field(default_factory=dict)
    clock_id: str = "hf2li"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    timestamp_unit_s: float = 1.0
    timestamp_origin: int | float = 0


@dataclass(frozen=True)
class ScanTrajectory:
    timestamps_s: Any
    wavenumbers_cm1: Any
    calibration_id: str
    direction: str = "forward"
    clock_id: str = "hf2li"
    timestamp_unit_s: float = 1.0
    timestamp_origin: int | float = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NativeScan:
    scan_index: int
    sample: NativeStream
    trajectory: ScanTrajectory
    reference: NativeStream | None = None
    flags: Sequence[str] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    sample_reference_covariance: Any = None


@dataclass(frozen=True)
class PumpObservation:
    timestamp_s: int | float
    clock_id: str = "timing"
    basis: str = "electrical_sync"
    independently_observed: bool = True
    observation_id: str = ""
    uncertainty_s: float | None = None
    timestamp_unit_s: float = 1.0
    timestamp_origin: int | float = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NativeMovie:
    movie_id: str
    phase_offset_s: float
    scans: Sequence[NativeScan]
    pump_observations: Sequence[PumpObservation]
    mode: str
    condition_id: str
    status: str = "complete"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    clock_corrections: Sequence[ClockCorrection] = ()
    experiment_id: str = EXPERIMENT_ID
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True)
class SpectrumSupport:
    direction: str
    wavenumbers_cm1: Any
    values: Any
    variance: Any = None
    valid: Any = None


@dataclass(frozen=True)
class SpectralBaseline:
    record_id: str
    mode: str
    condition_id: str
    spectra: Sequence[SpectrumSupport]
    kind: str = "q0"
    complete: bool = True
    accepted: bool = False
    compatibility: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    experiment_id: str = EXPERIMENT_ID
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True)
class ReconstructedPoints:
    scan_index: int
    direction: str
    time_s: Any
    wavenumbers_cm1: Any
    normalized_signal: Any
    delta_absorbance: Any
    absolute_absorbance: Any
    variance_normalized: Any
    variance_delta_absorbance: Any
    valid: Any
    flags: Mapping[str, Any]
    gaps_s: Sequence[tuple[float, float]] = ()
    native_sample_indices: Any = None
    reference_indices: Any = None


@dataclass(frozen=True)
class BandKinetic:
    movie_id: str
    scan_index: int
    direction: str
    window_cm1: tuple[float, float]
    area: float
    variance: float
    earliest_time_s: float
    latest_time_s: float
    coverage_fraction: float
    valid: bool
    kind: str = "band"


@dataclass(frozen=True)
class ReconstructedMovie:
    movie_id: str
    mode: str
    condition_id: str
    points: Sequence[ReconstructedPoints]
    band_kinetics: Sequence[BandKinetic]
    time_zero_basis: str
    status: str
    warnings: Sequence[str] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)
    analysis_version: str = ANALYSIS_VERSION


@dataclass(frozen=True)
class StateAssessment:
    accepted: bool
    reasons: Sequence[str]
    metrics: Mapping[str, Any]


@dataclass(frozen=True)
class NativeKernel:
    """Measured filter/IRF quadrature: evaluate source at (t-delay, nu).

    Optional wavelength_offsets_cm1 supplies measured scan/filter coupling at
    each quadrature point. Positive delay is causal filter memory.
    """
    delays_s: Any
    weights: Any
    calibration_id: str
    wavelength_offsets_cm1: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecoveryFit:
    apparent_tau_s: float
    amplitude: float
    offset: float
    covariance: Any
    residuals: Any
    predicted: Any
    tau_interval_s: tuple[float, float]
    identifiable: bool
    kernel_id: str
    valid_native_indices: Any
    warnings: Sequence[str] = ()
    model: str = "apparent_single_recovery_with_native_kernel"
    claim: str = "Apparent recovery; no molecular mechanism is established by this fit."


@dataclass(frozen=True)
class SavedRun:
    run_id: str
    mode: str
    record: Mapping[str, Any]
    created_utc: str
    path: Path
    schema_version: int = SCHEMA_VERSION


def compatibility_mismatches(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> tuple[str, ...]:
    """Compare explicit identities and settings, never checksums or digests."""
    def equivalent(left: Any, right: Any) -> bool:
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            return set(left) == set(right) and all(equivalent(left[k], right[k]) for k in left)
        if isinstance(left, (list, tuple, np.ndarray)) or isinstance(right, (list, tuple, np.ndarray)):
            try:
                return bool(np.array_equal(left, right, equal_nan=True))
            except (TypeError, ValueError):
                return list(left) == list(right)
        return bool(left == right)
    return tuple(f"{key}: expected {value!r}, found {actual.get(key)!r}"
                 for key, value in expected.items() if not equivalent(value, actual.get(key)))
