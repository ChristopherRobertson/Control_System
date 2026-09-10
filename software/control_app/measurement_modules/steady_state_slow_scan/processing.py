"""Native-preserving static spectroscopy. No device or other experiment imports.

The detector ratio is Q=S/R, delta absorbance is -log10(Q/Q0), and an
applicable measured path balance B alone permits A=-log10(Q/B). Controls are
matched by declared support; no default resampling or missing-interval filling.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

ANALYSIS_VERSION = "steady-state-slow-scan-analysis/1"


def _array(value, *, size=None, dtype=None):
    result = np.array(value, dtype=dtype, copy=True)
    if result.ndim != 1 or (size is not None and len(result) != size):
        raise ValueError("Native arrays must be one dimensional and have equal lengths")
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class NativeSweep:
    sweep_id: str
    mode: str
    condition_id: str
    segment_id: str
    direction: str
    replicate: int
    axis_cm1: np.ndarray
    sample: np.ndarray
    timestamps_s: np.ndarray
    reference: np.ndarray | None = None
    sample_variance: np.ndarray | None = None
    reference_variance: np.ndarray | None = None
    detector_covariance: np.ndarray | None = None
    valid: np.ndarray | None = None
    flags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.mode not in ("single", "dual") or self.direction not in ("forward", "reverse"):
            raise ValueError("Sweep mode/direction must be explicit single/dual and forward/reverse")
        for name in ("sweep_id", "segment_id"):
            if not getattr(self, name):
                raise ValueError(f"{name} is required")
        size = len(self.axis_cm1)
        for name in ("axis_cm1", "sample", "timestamps_s", "reference", "sample_variance",
                     "reference_variance", "detector_covariance", "valid"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _array(value, size=size))
        object.__setattr__(self, "flags", tuple(self.flags))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True)
class SpectralControl:
    control_id: str
    kind: str
    mode: str
    condition_id: str
    axis_cm1: np.ndarray
    values: np.ndarray
    variance: np.ndarray | None = None
    valid: np.ndarray | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        size = len(self.axis_cm1)
        for name in ("axis_cm1", "values", "variance", "valid"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _array(value, size=size))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True)
class AxisCorrection:
    calibration_id: str
    configuration_id: str
    lower_cm1: float
    upper_cm1: float
    offset_cm1: float = 0.0
    scale: float = 1.0
    uncertainty_cm1: float = 0.0
    applicable: bool = True

    def __post_init__(self):
        values = (self.lower_cm1, self.upper_cm1, self.offset_cm1, self.scale, self.uncertainty_cm1)
        if not all(np.isfinite(v) for v in values) or self.lower_cm1 > self.upper_cm1:
            raise ValueError("Axis calibration requires finite ordered support")
        if self.scale <= 0 or self.uncertainty_cm1 < 0 or not self.calibration_id:
            raise ValueError("Axis calibration scale, identity and uncertainty are invalid")


@dataclass(frozen=True)
class ProcessedSpectrum:
    native: NativeSweep
    axis_cm1: np.ndarray
    signal: np.ndarray
    variance: np.ndarray
    valid: np.ndarray
    quantity: str
    ratio: np.ndarray | None = None
    delta_absorbance: np.ndarray | None = None
    absorbance: np.ndarray | None = None
    flags: tuple[str, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        for name in ("axis_cm1", "signal", "variance", "valid", "ratio", "delta_absorbance", "absorbance"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _array(value, size=len(self.native.axis_cm1)))
        object.__setattr__(self, "flags", tuple(self.flags))


def _variance(value, size):
    return np.full(size, np.nan) if value is None else np.asarray(value, dtype=float).copy()


def _control_compatible(sweep, control, kind):
    if control.mode != sweep.mode:
        raise ValueError(f"{kind} detector mode mismatch: {control.mode} != {sweep.mode}")
    if control.kind != kind:
        raise ValueError(f"Expected {kind}, received {control.kind}")
    def operational(value):
        if not isinstance(value, Mapping):
            return value
        annotations = {"condition", "condition_id", "sample_id", "preparation_id", "cell_id", "position_id",
            "temperature_id", "temperature_k", "temperature_uncertainty_k", "temperature_record_id", "matrix_id",
            "configuration_id", "state_id", "exposure_history_id", "pH", "cell_reload_id", "lot_id",
            "state_verification_id", "thermal_history_id", "calibration_bundle_ids", "promoted_bundle_ids",
            "acceptance_reviewer", "acceptance_rationale", "review_complete", "condition_equilibrated",
            "physical_controls_confirmed", "plan_label", "purpose", "hardware", "metadata", "annotations",
            "notes", "operator", "description", "imported_requested_metadata",
            "requested_resolution_cm1", "measured_linewidth_cm1"}
        return {key: operational(item) for key, item in value.items()
                if key not in annotations and not key.startswith("fit_")}
    expected = operational(sweep.metadata.get("compatibility", {}))
    actual = operational(control.metadata.get("compatibility", {}))
    if kind == "path_balance":
        # Instrument/path calibration is reusable data, not a frozen sample run.
        # Its applicability is explicit and cannot depend on mutable fit choices.
        applicability = dict(control.metadata.get("applicability", {}))
        configuration = control.metadata.get("configuration_id") or applicability.get("configuration_id") or control.metadata.get("compatibility", {}).get("configuration_id")
        sweep_configuration = sweep.metadata.get("configuration_id") or sweep.metadata.get("compatibility", {}).get("configuration_id")
        if not configuration or configuration != sweep_configuration:
            raise ValueError("path_balance compatibility mismatch for configuration_id")
        candidates = {**expected, **dict(sweep.metadata.get("condition", {})), **dict(sweep.metadata)}
        for key, value in applicability.items():
            if candidates.get(key) != value:
                raise ValueError(f"path_balance applicability mismatch for {key}")
        return
    for key, value in expected.items():
        if actual.get(key) != value:
            raise ValueError(f"{kind} compatibility mismatch for {key}")


def match_support(target_axis, source_axis, source_values, source_variance=None,
                  source_valid=None, *, max_gap_cm1=None, tolerance_cm1=1e-8):
    """Match exact native points; interpolation is opt-in and bounded per interval.

    Invalid samples split support. An interpolation never jumps over an invalid
    observation or a gap larger than the explicit maximum. Duplicate native
    coordinates are ambiguous and excluded instead of silently pooled.
    """
    target = np.asarray(target_axis, dtype=float)
    axis = np.asarray(source_axis, dtype=float)
    values = np.asarray(source_values, dtype=float)
    variance = _variance(source_variance, len(axis))
    valid = np.isfinite(axis) & np.isfinite(values)
    if source_valid is not None:
        valid &= np.asarray(source_valid, dtype=bool)
    if len(axis) != len(values) or variance.shape != axis.shape:
        raise ValueError("Control native arrays have inconsistent lengths")
    if not len(axis):
        return np.full(target.shape, np.nan), np.full(target.shape, np.nan), np.zeros(target.shape, bool)
    if max_gap_cm1 is not None and (not np.isfinite(max_gap_cm1) or max_gap_cm1 <= 0):
        raise ValueError("max_gap_cm1 must be a positive explicit interpolation bound")
    order = np.argsort(axis, kind="stable")
    axis, values, variance, valid = axis[order], values[order], variance[order], valid[order]
    duplicates = np.r_[False, np.diff(axis) <= tolerance_cm1] | np.r_[np.diff(axis) <= tolerance_cm1, False]
    valid &= ~duplicates
    out = np.full(target.shape, np.nan)
    out_var = np.full(target.shape, np.nan)
    supported = np.zeros(target.shape, bool)
    for i, point in enumerate(target):
        if not np.isfinite(point) or not len(axis):
            continue
        right = int(np.searchsorted(axis, point))
        matches = [j for j in (right - 1, right) if 0 <= j < len(axis) and abs(axis[j] - point) <= tolerance_cm1]
        if matches:
            j = min(matches, key=lambda index: abs(axis[index] - point))
            if valid[j]:
                out[i], out_var[i], supported[i] = values[j], variance[j], True
        elif max_gap_cm1 is not None and 0 < right < len(axis):
            left = right - 1
            gap = axis[right] - axis[left]
            if valid[left] and valid[right] and 0 < gap <= max_gap_cm1:
                weight = (point - axis[left]) / gap
                out[i] = (1 - weight) * values[left] + weight * values[right]
                out_var[i] = (1 - weight) ** 2 * variance[left] + weight ** 2 * variance[right]
                supported[i] = True
    return out, out_var, supported


def align_detector_streams(sample_timestamps, reference_timestamps, reference_values,
                           *, tolerance_s, reference_valid=None):
    """One-to-one nearest timestamp alignment, without interpolating detector data."""
    if tolerance_s < 0 or not np.isfinite(tolerance_s):
        raise ValueError("A finite nonnegative alignment tolerance_s is required")
    target = np.asarray(sample_timestamps, dtype=np.longdouble)
    times = np.asarray(reference_timestamps, dtype=np.longdouble)
    values = np.asarray(reference_values)
    if len(times) != len(values):
        raise ValueError("Reference timestamp/value lengths differ")
    allowed = np.ones(len(times), bool) if reference_valid is None else np.asarray(reference_valid, bool)
    output = np.full(len(target), np.nan)
    indices = np.full(len(target), -1, dtype=int)
    used = set()
    for i, timestamp in enumerate(target):
        distances = np.abs(times - timestamp)
        choices = np.argsort(distances, kind="stable")
        for j in choices:
            if distances[j] > tolerance_s:
                break
            if j not in used and allowed[j] and np.isfinite(values[j]) and np.isfinite(distances[j]):
                indices[i], output[i] = j, values[j]
                used.add(j)
                break
    return output, indices, indices >= 0


def process_sweep(sweep: NativeSweep, *, dark=None, blank=None, q0=None, path_balance=None,
                  axis_correction: AxisCorrection | None = None, max_gap_cm1=None,
                  cancel_check: Callable[[], Any] | None = None) -> ProcessedSpectrum:
    """Process one direction/replicate only. Missing uncertainty stays unknown (NaN)."""
    if cancel_check:
        cancel_check()
    size = len(sweep.axis_cm1)
    axis = np.asarray(sweep.axis_cm1, float).copy()
    sample = np.asarray(sweep.sample, float).copy()
    sample_var = _variance(sweep.sample_variance, size)
    valid = np.isfinite(axis) & np.isfinite(sample)
    if sweep.valid is not None:
        valid &= np.asarray(sweep.valid, bool)
    flags = list(sweep.flags)
    provenance = {"analysis_version": ANALYSIS_VERSION, "sweep_id": sweep.sweep_id,
                  "pooling": "none; individual sweep retained", "control_ids": {},
                  "support_matching": "exact native coordinates" if max_gap_cm1 is None else
                  f"explicit linear control interpolation; max_gap_cm1={max_gap_cm1}",
                  "axis_uncertainty_cm1": None, "uncertainty": "Missing variance is unknown, never zero"}
    reference = None if sweep.reference is None else np.asarray(sweep.reference, float).copy()
    reference_var = _variance(sweep.reference_variance, size)
    covariance = _variance(sweep.detector_covariance, size)
    if dark is not None:
        if not isinstance(dark, Mapping):
            raise ValueError("Dark must explicitly map sample/reference values and uncertainty")
        if "sample" not in dark or (sweep.mode == "dual" and "reference" not in dark):
            raise ValueError("Dark is missing a required detector channel")
        sample -= np.asarray(dark.get("sample", 0), float)
        if "sample_variance" in dark:
            sample_var += np.asarray(dark["sample_variance"], float)
        else:
            sample_var[:] = np.nan
        if reference is not None:
            reference -= np.asarray(dark.get("reference", 0), float)
            if "reference_variance" in dark:
                reference_var += np.asarray(dark["reference_variance"], float)
            else:
                reference_var[:] = np.nan
            # Covariance of independent sample/reference dark estimates adds.
            if "detector_covariance" in dark:
                covariance += np.asarray(dark["detector_covariance"], float)
            else:
                covariance[:] = np.nan
        provenance["dark"] = {key: value for key, value in dark.items() if key.endswith("id")}
    else:
        flags.append("dark_not_applied")
    ratio = delta = absorbance = ratio_variance = ratio_valid = None
    signal = sample.copy()
    variance = sample_var.copy()
    quantity = "raw_sample_signal"
    if sweep.mode == "dual":
        if reference is None:
            raise ValueError("Dual-detector normalization requires a native reference stream")
        valid &= np.isfinite(reference) & (reference > 0)
        ratio = np.full(size, np.nan)
        ratio[valid] = sample[valid] / reference[valid]
        with np.errstate(divide="ignore", invalid="ignore"):
            variance = (sample_var / reference ** 2 + sample ** 2 * reference_var / reference ** 4
                        - 2 * sample * covariance / reference ** 3)
        covariance_bad = (np.isfinite(covariance) & np.isfinite(sample_var) & np.isfinite(reference_var)
                          & (np.abs(covariance) > np.sqrt(np.maximum(0, sample_var * reference_var)) + 1e-15))
        valid &= ~covariance_bad
        if np.any(covariance_bad):
            flags.append("invalid_detector_covariance")
        signal, quantity = ratio.copy(), "reference_normalized_ratio"
        ratio_variance = variance.copy()
        ratio_valid = valid.copy()
        if blank is not None:
            raise ValueError("Dual mode uses simultaneous matched reference and explicit B; not a sequential blank")
    elif blank is not None:
        _control_compatible(sweep, blank, "blank")
        if not blank.metadata.get("complete", False):
            flags.append("partial_blank_support")
        background, background_var, support = match_support(axis, blank.axis_cm1, blank.values,
            blank.variance, blank.valid, max_gap_cm1=max_gap_cm1)
        valid &= support & (background > 0) & (sample > 0)
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = sample / background
            ratio_var = sample_var / background ** 2 + sample ** 2 * background_var / background ** 4
            absorbance = -np.log10(ratio)
            variance = ratio_var / (ratio ** 2 * np.log(10) ** 2)
        signal, quantity = absorbance.copy(), "sequential_blank_absorbance"
        ratio_variance = ratio_var
        ratio_valid = valid.copy()
        provenance["control_ids"]["blank"] = blank.control_id
        provenance["blank_assumption"] = "sequential sample and blank noise independent; drift assessed separately"
    if q0 is not None:
        if ratio is None:
            raise ValueError("An unpumped Q0 comparison requires a normalized ratio or compatible sequential blank")
        _control_compatible(sweep, q0, "unpumped_q0")
        baseline, baseline_var, support = match_support(axis, q0.axis_cm1, q0.values,
            q0.variance, q0.valid, max_gap_cm1=max_gap_cm1)
        delta_valid = valid & support & (baseline > 0) & (ratio > 0)
        delta = np.full(size, np.nan)
        delta[delta_valid] = -np.log10(ratio[delta_valid] / baseline[delta_valid])
        provenance["control_ids"]["q0"] = q0.control_id
        provenance["delta_absorbance_variance"] = np.where(delta_valid,
            ratio_variance / (ratio ** 2 * np.log(10) ** 2) + baseline_var / (baseline ** 2 * np.log(10) ** 2), np.nan)
        provenance["delta_absorbance_valid"] = delta_valid.copy()
    if path_balance is not None:
        if sweep.mode != "dual":
            flags.append("path_balance_not_applied")
            provenance["path_balance_limitation"] = "B is a dual-detector calibration"
            path_balance = None
        else:
            try:
                _control_compatible(sweep, path_balance, "path_balance")
                if not path_balance.metadata.get("calibration_id") or not path_balance.metadata.get("applicable"):
                    raise ValueError("Applicable measured path-balance calibration B was not supplied")
            except ValueError as exc:
                flags.append("path_balance_not_applied")
                provenance["path_balance_limitation"] = str(exc)
                path_balance = None
    if path_balance is not None:
        balance, balance_var, support = match_support(axis, path_balance.axis_cm1, path_balance.values,
            path_balance.variance, path_balance.valid, max_gap_cm1=max_gap_cm1)
        valid &= support & (balance > 0) & (ratio > 0)
        with np.errstate(divide="ignore", invalid="ignore"):
            absorbance = -np.log10(ratio / balance)
            variance = (variance / ratio ** 2 + balance_var / balance ** 2) / np.log(10) ** 2
        signal, quantity = absorbance.copy(), "calibrated_absorbance"
        provenance["control_ids"]["path_balance"] = path_balance.control_id
        provenance["path_balance_calibration_id"] = path_balance.metadata["calibration_id"]
        provenance["normalization_assumption"] = "B independent of sample acquisition; detector covariance retained"
    if axis_correction is not None:
        configuration = sweep.metadata.get("configuration_id", sweep.metadata.get("compatibility", {}).get("configuration_id"))
        in_support = (axis >= axis_correction.lower_cm1) & (axis <= axis_correction.upper_cm1)
        if not axis_correction.applicable or configuration != axis_correction.configuration_id:
            provenance["axis_limitation"] = "Spectral-axis correction is not applicable to this configuration"
        elif np.any(np.isfinite(axis) & ~in_support):
            provenance["axis_limitation"] = "Native axis lies outside calibrated correction support"
        else:
            axis = axis_correction.offset_cm1 + axis_correction.scale * axis
            provenance["axis_calibration_id"] = axis_correction.calibration_id
            provenance["axis_uncertainty_cm1"] = axis_correction.uncertainty_cm1
    if not provenance.get("axis_calibration_id"):
        flags.append("spectral_axis_uncalibrated")
    valid &= np.isfinite(signal)
    negative_variance = np.isfinite(variance) & (variance < -1e-15)
    if np.any(negative_variance):
        valid &= ~negative_variance
        flags.append("invalid_negative_variance")
    variance = np.where(np.isfinite(variance), np.maximum(variance, 0), np.nan)
    signal[~valid] = np.nan
    variance[~valid] = np.nan
    if ratio is not None:
        ratio[~np.isfinite(ratio)] = np.nan
        ratio[~ratio_valid] = np.nan
        provenance["ratio_variance"] = np.where(ratio_valid, ratio_variance, np.nan)
        provenance["ratio_valid"] = ratio_valid.copy()
    if absorbance is not None:
        absorbance[~valid] = np.nan
    if np.count_nonzero(~valid):
        flags.append("missing_or_invalid_support")
    if np.any(~np.isfinite(variance[valid])):
        flags.append("uncertainty_inputs_incomplete")
    if cancel_check:
        cancel_check()
    return ProcessedSpectrum(sweep, axis, signal, variance, valid, quantity, ratio, delta,
                             absorbance, tuple(dict.fromkeys(flags)), provenance)


@dataclass(frozen=True)
class FitSettings:
    peak_count: int = 1
    line_shape: str = "gaussian"
    baseline_degree: int = 1
    fringe_periods_cm1: tuple[float, ...] = ()
    initial_centers_cm1: tuple[float, ...] = ()
    lower_cm1: float | None = None
    upper_cm1: float | None = None
    max_iterations: int = 180
    selection_reason: str = "Prospectively chosen component count; centers and widths are free"
    peak_polarity: str = "auto"

    def __post_init__(self):
        if not 0 <= self.peak_count <= 8 or self.line_shape not in ("gaussian", "lorentzian"):
            raise ValueError("Supported fits have 0..8 components with Gaussian or Lorentzian line shape")
        if self.baseline_degree not in (0, 1, 2):
            raise ValueError("Supported baselines are constant, linear or quadratic")
        if self.peak_polarity not in ("auto", "positive", "negative"):
            raise ValueError("Peak polarity must be auto, positive or negative")
        if any(not np.isfinite(p) or p <= 0 for p in self.fringe_periods_cm1):
            raise ValueError("Fringe periods must be finite positive cm^-1 values")
        if self.initial_centers_cm1 and len(self.initial_centers_cm1) != self.peak_count:
            raise ValueError("Initial centers are free starting guesses; supply one per component")
        object.__setattr__(self, "fringe_periods_cm1", tuple(self.fringe_periods_cm1))
        object.__setattr__(self, "initial_centers_cm1", tuple(self.initial_centers_cm1))


@dataclass(frozen=True)
class PeakFit:
    component: int
    center_cm1: float
    center_uncertainty_cm1: float
    width_fwhm_cm1: float
    width_uncertainty_cm1: float
    height: float
    height_uncertainty: float
    integrated_area: float
    area_uncertainty: float


@dataclass(frozen=True)
class FitResult:
    settings: FitSettings
    peaks: tuple[PeakFit, ...]
    fitted: np.ndarray
    baseline: np.ndarray
    residuals: np.ndarray
    covariance: np.ndarray
    parameter_names: tuple[str, ...]
    parameters: np.ndarray
    aicc: float
    residual_rms: float
    residual_lag1_correlation: float
    valid: np.ndarray
    flags: tuple[str, ...]
    provenance: Mapping[str, Any]


def _line(x, center, width, shape):
    u = (x - center) / width
    return np.exp(-.5 * u * u) if shape == "gaussian" else 1 / (1 + u * u)


def fit_spectrum(spectrum: ProcessedSpectrum, settings: FitSettings | None = None, *,
                 cancel_check: Callable[[], Any] | None = None) -> FitResult:
    """Joint free-center, free-width nonlinear fit with full overlap covariance.

    NumPy damped least squares avoids imposing an optional SciPy dependency.
    Parameter covariance is a local asymptotic approximation; alternatives and
    residual autocorrelation expose its limitations. RT centers are never loaded.
    """
    settings = settings or FitSettings()
    x_all = np.asarray(spectrum.axis_cm1, float)
    y_all = np.asarray(spectrum.signal, float)
    valid = np.asarray(spectrum.valid, bool).copy() & np.isfinite(x_all) & np.isfinite(y_all)
    if settings.lower_cm1 is not None:
        valid &= x_all >= settings.lower_cm1
    if settings.upper_cm1 is not None:
        valid &= x_all <= settings.upper_cm1
    x, y = x_all[valid], y_all[valid]
    order = np.argsort(x)
    x, y = x[order], y[order]
    nbase = settings.baseline_degree + 1 + 2 * len(settings.fringe_periods_cm1)
    nparams = nbase + settings.peak_count * 3
    if len(x) <= nparams + 2 or len(np.unique(x)) <= nparams + 2 or np.ptp(x) <= 0:
        raise ValueError("Insufficient independent valid native support for selected model")
    midpoint, span = (x.max() + x.min()) / 2, np.ptp(x)
    polarity = -1. if settings.peak_polarity == "negative" or (
        settings.peak_polarity == "auto" and spectrum.quantity in ("reference_normalized_ratio", "raw_sample_signal")) else 1.
    def design(points):
        t = (points - midpoint) / span
        columns = [t ** degree for degree in range(settings.baseline_degree + 1)]
        for period in settings.fringe_periods_cm1:
            columns.extend((np.sin(2 * np.pi * (points - midpoint) / period),
                            np.cos(2 * np.pi * (points - midpoint) / period)))
        return np.column_stack(columns)
    basis = design(x)
    observation_variance = np.asarray(spectrum.variance)[valid][order]
    known_noise = np.all(np.isfinite(observation_variance) & (observation_variance > 0))
    sigma = np.sqrt(observation_variance) if known_noise else np.ones(len(x))
    # Normalize x/width optimization coordinates to avoid cm^-1 scale conditioning.
    def evaluate(parameters, points=x, matrix=basis):
        model = matrix @ parameters[:nbase]
        for peak in range(settings.peak_count):
            logheight, center_scaled, logwidth = parameters[nbase + 3 * peak:nbase + 3 * peak + 3]
            model = model + polarity * np.exp(logheight) * _line(points, midpoint + span * center_scaled,
                                                     span * np.exp(logwidth), settings.line_shape)
        return model
    def project(parameters):
        result = parameters.copy()
        minimum_width = max(np.min(np.diff(np.unique(x))) * .25, span * 1e-5)
        for peak in range(settings.peak_count):
            start = nbase + 3 * peak
            result[start] = np.clip(result[start], -35, 35)
            result[start + 1] = np.clip(result[start + 1], -.5, .5)
            result[start + 2] = np.clip(result[start + 2], np.log(minimum_width / span), np.log(1.0))
        return result
    def jacobian(parameters):
        columns = []
        for j in range(nparams):
            epsilon = 1e-5 * max(1, abs(parameters[j]))
            a, b = parameters.copy(), parameters.copy()
            a[j] += epsilon
            b[j] -= epsilon
            columns.append((evaluate(a) - evaluate(b)) / (2 * epsilon) / sigma)
        return np.column_stack(columns)
    # Iteratively downweight positive band departures only for initialization.
    coefficients = np.linalg.lstsq(basis, y, rcond=None)[0]
    for _ in range(6):
        residual = y - basis @ coefficients
        departure = residual * polarity
        weights = np.where(departure > np.quantile(departure, .55), .12, 1.)
        coefficients = np.linalg.lstsq(basis * weights[:, None], y * weights, rcond=None)[0]
    departures = polarity * (y - basis @ coefficients)
    if settings.initial_centers_cm1:
        centers = list(settings.initial_centers_cm1)
        if any(not x.min() <= center <= x.max() for center in centers):
            raise ValueError("Initial center guesses must lie in this spectrum's selected support")
    else:
        # Smooth initialization only; all residual fitting uses exact native points.
        smooth = np.convolve(departures, np.ones(5) / 5, mode="same")
        candidates = [i for i in range(1, len(x) - 1) if smooth[i] >= smooth[i-1] and smooth[i] >= smooth[i+1]]
        candidates.sort(key=lambda i: smooth[i], reverse=True)
        centers = []
        for candidate in candidates:
            if all(abs(x[candidate] - center) >= span / max(8, 4 * settings.peak_count) for center in centers):
                centers.append(float(x[candidate]))
                if len(centers) == settings.peak_count:
                    break
        fallback = np.linspace(x.min() + .15 * span, x.max() - .15 * span, max(1, settings.peak_count))
        for point in fallback:
            if len(centers) >= settings.peak_count:
                break
            centers.append(float(point))
        centers = sorted(centers)
    center_sets = [centers[:settings.peak_count]]
    if settings.peak_count > 1 and not settings.initial_centers_cm1:
        # An unresolved shoulder need not make a separate local maximum. Add
        # starts from the observed positive band mass, never literature centers.
        mass = np.maximum(departures - .15 * np.max(departures), 0)
        if np.sum(mass) > 0:
            cumulative = np.cumsum(mass) / np.sum(mass)
            for extent in (.65, .9):
                quantiles = np.linspace((1 - extent) / 2, (1 + extent) / 2, settings.peak_count)
                center_sets.append(np.interp(quantiles, cumulative, x).tolist())
    initializations = []
    for guessed_centers in center_sets:
        for width_fraction in ((.035, .075, .14) if settings.peak_count else (.075,)):
            initial = list(coefficients)
            for center in guessed_centers:
                height = max(float(np.interp(center, x, departures)), float(np.ptp(y)) * .1, 1e-10)
                initial.extend((np.log(height), (center - midpoint) / span, np.log(width_fraction)))
            initializations.append(np.asarray(initial))
    best = None
    for initial in initializations:
        parameters = project(initial)
        damping, converged = 1e-3, False
        for iteration in range(settings.max_iterations):
            if cancel_check:
                cancel_check()
            residual = (y - evaluate(parameters)) / sigma
            score = float(residual @ residual)
            matrix = jacobian(parameters)
            normal = matrix.T @ matrix
            gradient = matrix.T @ residual
            if np.max(np.abs(gradient)) < 1e-9:
                converged = True
                break
            diagonal = np.maximum(np.diag(normal), 1e-12)
            try:
                step = np.linalg.solve(normal + damping * np.diag(diagonal), gradient)
            except np.linalg.LinAlgError:
                damping *= 10
                continue
            candidate = project(parameters + step)
            new_residual = (y - evaluate(candidate)) / sigma
            new_score = float(new_residual @ new_residual)
            if new_score < score:
                parameters = candidate
                damping = max(damping / 3, 1e-12)
                if abs(score - new_score) <= 1e-10 * max(1, score) or np.linalg.norm(step) < 1e-8:
                    converged = True
                    break
            else:
                damping *= 8
                if damping > 1e16:
                    break
        score = float(np.sum(((y - evaluate(parameters)) / sigma) ** 2))
        if best is None or score < best[0]:
            best = score, parameters, converged
    score, parameters, converged = best
    matrix = jacobian(parameters)
    normal = matrix.T @ matrix
    dof = len(x) - nparams
    covariance_internal = np.linalg.pinv(normal, rcond=1e-13) * (1.0 if known_noise else score / dof)
    # Public parameters are physical [baseline coefficients, height, center, width].
    physical = parameters.copy()
    transform = np.ones(nparams)
    names = [f"baseline_{j}" for j in range(nbase)]
    for peak in range(settings.peak_count):
        j = nbase + peak * 3
        physical[j:j+3] = (polarity * np.exp(parameters[j]), midpoint + span * parameters[j+1], span * np.exp(parameters[j+2]))
        transform[j:j+3] = (physical[j], span, physical[j+2])
        names.extend((f"peak_{peak+1}_height", f"peak_{peak+1}_center_cm1", f"peak_{peak+1}_scale_cm1"))
    covariance = covariance_internal * transform[:, None] * transform[None, :]
    axis_uncertainty = spectrum.provenance.get("axis_uncertainty_cm1")
    axis_variance = float(axis_uncertainty) ** 2 if axis_uncertainty is not None else 0.
    # A calibrated offset error is common to component centers, not independent
    # noise that should increase uncertainty in their relative splitting.
    center_indices = [nbase + peak * 3 + 1 for peak in range(settings.peak_count)]
    for first in center_indices:
        for second in center_indices:
            covariance[first, second] += axis_variance
    width_factor = 2 * np.sqrt(2 * np.log(2)) if settings.line_shape == "gaussian" else 2.
    area_factor = np.sqrt(2 * np.pi) if settings.line_shape == "gaussian" else np.pi
    peaks = []
    for peak in range(settings.peak_count):
        j = nbase + peak * 3
        height, center, width = physical[j:j+3]
        area_gradient = np.array((width * area_factor, 0., height * area_factor))
        area_variance = area_gradient @ covariance[j:j+3, j:j+3] @ area_gradient
        peaks.append(PeakFit(peak + 1, float(center), float(np.sqrt(max(0, covariance[j+1,j+1]))),
            float(width * width_factor), float(np.sqrt(max(0, covariance[j+2,j+2])) * width_factor),
            float(height), float(np.sqrt(max(0, covariance[j,j]))), float(height * width * area_factor),
            float(np.sqrt(max(0, area_variance)))))
    fitted = np.full(len(x_all), np.nan)
    baseline = np.full(len(x_all), np.nan)
    fitted[valid] = evaluate(parameters, x_all[valid], design(x_all[valid]))
    baseline[valid] = design(x_all[valid]) @ parameters[:nbase]
    residuals = y_all - fitted
    ordered_residuals = residuals[valid][order]
    rms = float(np.sqrt(np.mean(ordered_residuals ** 2)))
    lag1 = float(np.corrcoef(ordered_residuals[:-1], ordered_residuals[1:])[0, 1]) if rms > 1e-15 else 0.
    if known_noise:
        likelihood = score + float(np.sum(np.log(2 * np.pi * observation_variance)))
    else:
        likelihood = len(x) * np.log(max(float(np.sum(ordered_residuals ** 2)) / len(x), np.finfo(float).tiny))
    information_parameters = nparams + (0 if known_noise else 1)  # fitted noise scale is a parameter too
    aicc = float(likelihood + 2 * information_parameters +
                 2 * information_parameters * (information_parameters + 1) / (len(x) - information_parameters - 1))
    flags = []
    if not converged:
        flags.append("fit_not_converged")
    if np.linalg.matrix_rank(normal, tol=np.max(np.abs(normal)) * 1e-12) < nparams:
        flags.append("fit_parameters_not_identifiable")
    if abs(lag1) > .35:
        flags.append("correlated_residuals_compare_baseline_and_line_shape")
    if not known_noise:
        flags.append("fit_noise_estimated_from_residuals")
    if axis_uncertainty is None:
        flags.append("center_uncertainty_excludes_unresolved_axis_calibration")
    if any(peak.center_cm1 - peak.width_fwhm_cm1 / 2 <= x.min() or
           peak.center_cm1 + peak.width_fwhm_cm1 / 2 >= x.max() for peak in peaks):
        flags.append("fit_component_truncated_by_selected_support")
    return FitResult(settings, tuple(sorted(peaks, key=lambda peak: peak.center_cm1)), fitted, baseline, residuals,
        covariance, tuple(names), physical, aicc, rms, lag1, valid, tuple(flags),
        {"analysis_version": ANALYSIS_VERSION, "condition_id": spectrum.native.condition_id,
         "sweep_id": spectrum.native.sweep_id, "quantity": spectrum.quantity,
         "uncertainty_method": "local full-Jacobian covariance; independent axis uncertainty added to centers",
         "noise_basis": "supplied observation variance" if known_noise else "estimated from residual sum of squares/dof",
         "component_policy": settings.selection_reason, "center_policy": "all centers independently fitted in this condition",
         "integrated_area_definition": "analytic full-component integral; extrapolation beyond observed support is model dependent",
         "axis_covariance": "common calibrated axis-offset variance included between all peak centers",
         "effective_resolution_cm1": spectrum.native.metadata.get("effective_resolution_cm1"),
         "support_points": len(x), "degrees_of_freedom": dof})


def fit_model_alternatives(spectrum, settings: Sequence[FitSettings], *, cancel_check=None):
    """Retain every prospective model; ascending AICc is advisory, not acceptance."""
    return tuple(sorted((fit_spectrum(spectrum, item, cancel_check=cancel_check) for item in settings),
                        key=lambda result: result.aicc))


def assess_sweeps(spectra: Sequence[ProcessedSpectrum], *, maximum_rms_difference=None,
                  max_gap_cm1=None):
    """Report pairwise repeatability/drift/direction without automatically pooling."""
    comparisons = []
    for first_index, first in enumerate(spectra):
        for second in spectra[first_index + 1:]:
            if (first.native.mode, first.native.segment_id, first.quantity) != (
                    second.native.mode, second.native.segment_id, second.quantity):
                continue
            aligned, _, supported = match_support(first.axis_cm1, second.axis_cm1, second.signal,
                second.variance, second.valid, max_gap_cm1=max_gap_cm1)
            support = first.valid & supported
            differences = aligned[support] - first.signal[support]
            rms = float(np.sqrt(np.mean(differences ** 2))) if len(differences) else None
            elapsed = (float(np.nanmedian(second.native.timestamps_s)) - float(np.nanmedian(first.native.timestamps_s)))
            mean = float(np.mean(differences)) if len(differences) else None
            comparisons.append({"first_sweep": first.native.sweep_id, "second_sweep": second.native.sweep_id,
                "direction_comparison": first.native.direction != second.native.direction, "matched_points": len(differences),
                "rms_difference": rms, "mean_difference": mean, "elapsed_s": elapsed,
                "apparent_drift_per_s": mean / elapsed if mean is not None and elapsed != 0 else None,
                "within_prespecified_tolerance": None if maximum_rms_difference is None or rms is None else rms <= maximum_rms_difference,
                "quality_flags": list(dict.fromkeys(first.flags + second.flags))})
    return {"comparisons": comparisons, "pooled": False,
            "acceptance": "Review direction, repeatability, drift and native quality flags before pooling"}


def compare_states(before: FitResult, after: FitResult, *, center_tolerance_cm1=None,
                   area_fraction_tolerance=None):
    """Compare independently fitted pre/post peaks in center order with explicit limits."""
    if before.provenance.get("quantity") != after.provenance.get("quantity"):
        raise ValueError("Pre/post-state spectral quantity mismatch")
    if len(before.peaks) != len(after.peaks):
        return {"accepted": False, "reason": "Component counts differ; component correspondence is unresolved", "peaks": []}
    rows = []
    for first, second in zip(before.peaks, after.peaks):
        shift = second.center_cm1 - first.center_cm1
        fraction = second.integrated_area / first.integrated_area - 1 if first.integrated_area else None
        rows.append({"component": first.component, "center_shift_cm1": shift,
            "center_shift_uncertainty_cm1": float(np.hypot(first.center_uncertainty_cm1, second.center_uncertainty_cm1)),
            "width_change_cm1": second.width_fwhm_cm1 - first.width_fwhm_cm1, "area_fraction_change": fraction,
            "center_within_tolerance": None if center_tolerance_cm1 is None else abs(shift) <= center_tolerance_cm1,
            "area_within_tolerance": None if area_fraction_tolerance is None or fraction is None else abs(fraction) <= area_fraction_tolerance})
    accepted = None if center_tolerance_cm1 is None or area_fraction_tolerance is None else all(
        row["center_within_tolerance"] and row["area_within_tolerance"] for row in rows)
    return {"accepted": accepted, "reason": "Independent fits paired by center order; component assignments remain conditional", "peaks": rows,
            "before_metadata_condition_id": before.provenance.get("condition_id"),
            "after_metadata_condition_id": after.provenance.get("condition_id"),
            "baseline_rms_change": float(np.nanmean(after.baseline) - np.nanmean(before.baseline))}
