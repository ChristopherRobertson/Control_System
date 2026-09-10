"""Independent fixed-point science: valid support, uncertainty and recovery.

All times derive from retained device ticks. No gap is interpolated. Recovery
models describe apparent fixed-point response, not band area or a mechanism.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
import math
from typing import Any

import numpy as np

from .persistence import EXPERIMENT_ID, SCHEMA_VERSION, iter_native_chunks, validate_record

ANALYSIS_VERSION = "fixed-point-analysis-1.1"
CLAIM_LIMITS = (
    "Sequential positions are individual fixed-point observations, not a simultaneous spectrum.",
    "A fixed-point amplitude is not full band area and does not establish a microscopic pathway.",
    "Direct HF2LI time precision does not establish nanosecond kinetic resolution.",
    "Electrical pump markers do not independently establish optical arrival or chemical time zero.",
)


class AnalysisCancelled(RuntimeError):
    pass


def _cancelled(cancel):
    if cancel is not None and (cancel() if callable(cancel) else cancel.is_set()):
        raise AnalysisCancelled("Analysis stopped; native data retained")


def _mapping(value):
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    return dict(value)


def compatibility_projection(value) -> dict:
    """Compare data-producing settings, never optional descriptive metadata.

    Temperature, material/sample labels, evidence IDs and qualification status
    remain in the saved record. They do not invalidate observed raw baselines.
    Optional response models affect only an explicitly requested kinetic fit.
    """
    source = _mapping(value)
    source = source.get("plan", source)
    settings = source.get("settings", {})
    resolved = source.get("resolved", {})
    result = {key: source[key] for key in ("experiment_id", "mode", "schema_version") if key in source}
    if result.get("schema_version") == 1:
        result["schema_version"] = SCHEMA_VERSION
    result["settings"] = {key: settings[key] for key in (
        "mode", "sample_rate_sps", "reference_rate_sps", "sample_timeconstant_s", "reference_timeconstant_s",
        "sample_filter_order", "reference_filter_order") if key in settings}
    if "positions" in settings:
        result["settings"]["positions_cm1"] = [
            position.get("wavenumber_cm1", position.get("position_cm1")) if isinstance(position, Mapping) else position
            for position in settings["positions"]]
    # These are actual selected acquisition settings. Keeping the projection
    # explicit prevents new annotation/evidence fields from becoming gates.
    result["resolved"] = {key: resolved[key] for key in (
        "sample", "reference", "hf2li", "probe_recipe", "mircat", "timing_demodulator_index",
        "timing_rate_sps", "pump_marker_bit") if key in resolved}
    for role in ("sample", "reference"):
        if role in result["resolved"]:
            result["resolved"][role] = {key: resolved[role][key] for key in (
                "demodulator_index", "input_index", "rate_sps", "timeconstant_s", "order",
                "range_v", "gain", "ac", "impedance_50ohm", "differential") if key in resolved[role]}
    def without_annotations(item):
        if isinstance(item, Mapping):
            return {key: without_annotations(value) for key, value in item.items()
                    if key not in ("record_id", "configuration_id", "qualification_kind", "measured", "promoted",
                                   "accepted", "accepted_by", "condition_id", "condition_profile", "temperature_id",
                                   "temperature_k", "temperature_K", "material", "protein", "sample_id", "sample_label",
                                   "preparation_id", "cell_id", "position_id", "notes", "description", "label",
                                   "value_sources", "actual_readbacks_required")
                    and not key.endswith(("_record_id", "_record_ids"))
                    and not any(word in key.lower() for word in ("hash", "checksum", "digest"))}
        if isinstance(item, (list, tuple)):
            return [without_annotations(value) for value in item]
        return item
    result["resolved"] = without_annotations(result["resolved"])
    return result


def compatible_record(record, plan) -> tuple[bool, tuple[str, ...]]:
    left, right = compatibility_projection(record), compatibility_projection(plan)
    mismatches = []

    def compare(a, b, path):
        if isinstance(a, Mapping) and isinstance(b, Mapping):
            for key in sorted(set(a) | set(b)):
                if key not in a or key not in b:
                    mismatches.append(f"{path}{key}: missing compatibility value")
                else:
                    compare(a[key], b[key], f"{path}{key}.")
        elif isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            if list(a) != list(b):
                mismatches.append(f"{path.rstrip('.')}: changed")
        elif a != b:
            mismatches.append(f"{path.rstrip('.')}: {a!r} differs from {b!r}")

    compare(left, right, "")
    return not mismatches, tuple(mismatches)


def time_from_ticks(timestamps, epoch: int, clockbase_hz: float) -> np.ndarray:
    ticks = np.asarray(timestamps)
    if ticks.dtype.kind not in "iu":
        raise ValueError("Device timestamps must retain their original integer ticks")
    if not np.isfinite(clockbase_hz) or clockbase_hz <= 0:
        raise ValueError("clockbase_hz must be finite and positive")
    # Subtract as Python integers before converting to float: large uint64 clocks
    # must neither underflow before the epoch nor lose low timestamp bits.
    return np.fromiter(((int(t) - int(epoch)) / clockbase_hz for t in ticks), float, len(ticks))


def _stream_values(stream) -> np.ndarray:
    if "value" in stream:
        return np.asarray(stream["value"], dtype=float)
    x = np.asarray(stream.get("x", ()), dtype=float)
    y = np.asarray(stream.get("y", np.zeros_like(x)), dtype=float)
    if x.shape != y.shape:
        raise ValueError("Native detector x/y shapes differ")
    return np.hypot(x, y)


def _valid_stream(stream, count):
    valid = np.ones(count, dtype=bool)
    for key, invert in (("valid", False), ("clipped", True), ("unlocked", True), ("gap", True)):
        if key in stream:
            mask = np.asarray(stream[key], dtype=bool)
            if mask.ndim == 0:
                mask = np.full(count, bool(mask))
            if mask.shape != (count,):
                raise ValueError(f"Native {key} mask length differs from detector stream")
            valid &= ~mask if invert else mask
    return valid


def align_detectors(sample: Mapping, reference: Mapping | None, *, tolerance_ticks: int = 0) -> dict:
    """One-to-one matching on device ticks; unmatched sample support remains NaN.

    Nonzero tolerance must be a calibrated timestamp-alignment tolerance supplied
    by the caller. It does not interpolate, duplicate or shift native observations.
    """
    st = np.asarray(sample.get("timestamp", sample.get("timestamps", ())))
    s = _stream_values(sample)
    if st.shape != s.shape or st.dtype.kind not in "iu":
        raise ValueError("Sample timestamps must be integer ticks matching detector values")
    if tolerance_ticks < 0:
        raise ValueError("Timestamp tolerance cannot be negative")
    sv = _valid_stream(sample, len(s)) & np.isfinite(s)
    r, ri = np.full(len(s), np.nan), np.full(len(s), -1, dtype=int)
    valid = np.zeros(len(s), dtype=bool)
    flags = []
    if len(st) > 1 and any(int(b) <= int(a) for a, b in zip(st[:-1], st[1:])):
        flags.append("nonmonotonic_sample_timestamps")
    if reference is None:
        flags.append("missing_reference")
    else:
        rt = np.asarray(reference.get("timestamp", reference.get("timestamps", ())))
        rv = _stream_values(reference)
        if rt.shape != rv.shape or rt.dtype.kind not in "iu":
            raise ValueError("Reference timestamps must be integer ticks matching detector values")
        good = _valid_stream(reference, len(rv)) & np.isfinite(rv) & (rv > 0)
        if len(rt) > 1 and any(int(b) <= int(a) for a, b in zip(rt[:-1], rt[1:])):
            flags.append("nonmonotonic_reference_timestamps")
        else:
            previous = -1
            for i, tick in enumerate(st):
                candidate = int(np.searchsorted(rt, tick))
                options = [j for j in (candidate - 1, candidate) if 0 <= j < len(rt) and j > previous]
                if not options:
                    continue
                j = min(options, key=lambda k: abs(int(rt[k]) - int(tick)))
                if abs(int(rt[j]) - int(tick)) <= tolerance_ticks:
                    previous, ri[i], r[i] = j, j, rv[j]
                    valid[i] = sv[i] and good[j] and s[i] > 0
            if np.any(ri < 0):
                flags.append("unmatched_reference_support")
            if np.any(~good):
                flags.append("invalid_reference")
    if np.any(~sv):
        flags.append("invalid_sample")
    if any(k.startswith("nonmonotonic") for k in flags):
        valid[:] = False
    return {"timestamp": st.copy(), "sample": s, "reference": r,
            "reference_index": ri, "valid": valid, "quality_flags": flags}


def baseline_statistics(time_s, values, *, window_s=None, maximum_relative_drift=0.01,
                        minimum_points=8) -> dict:
    t, y = np.asarray(time_s, float), np.asarray(values, float)
    valid = np.isfinite(t) & np.isfinite(y)
    if window_s is not None:
        valid &= (t >= window_s[0]) & (t <= window_s[1])
    t, y = t[valid], y[valid]
    if len(t) < minimum_points or np.ptp(t) <= 0:
        return {"stationary": False, "count": len(t), "mean": float(np.mean(y)) if len(y) else None,
                "reason": "Insufficient finite stationary-baseline support"}
    centered = t - np.mean(t)
    matrix = np.column_stack((np.ones(len(t)), centered))
    parameters = np.linalg.lstsq(matrix, y, rcond=None)[0]
    residual = y - matrix @ parameters
    noise = float(np.std(residual, ddof=2))
    mean, slope = map(float, parameters)
    drift = abs(slope) * float(np.ptp(t)) / max(abs(mean), np.finfo(float).tiny)
    half = len(y) // 2
    half_shift = abs(float(np.mean(y[half:]) - np.mean(y[:half]))) / max(abs(mean), np.finfo(float).tiny)
    # Absolute/relative effect thresholds are prospective settings. A tiny but
    # statistically significant drift does not fail solely because N is large.
    stationary = drift <= maximum_relative_drift and half_shift <= maximum_relative_drift
    return {"stationary": bool(stationary), "count": len(t), "mean": mean,
            "standard_deviation": float(np.std(y, ddof=1)), "noise_standard_deviation": noise,
            "standard_error": noise / math.sqrt(len(t)), "slope_per_s": slope,
            "relative_drift": drift, "relative_half_shift": half_shift,
            "maximum_relative_drift": maximum_relative_drift,
            "reason": "Stationary within the selected tolerance" if stationary else "Pre-pump baseline drift exceeds the selected tolerance"}


def normalize_trace(sample, reference=None, *, mode="dual", time_s=None, baseline_window_s=None,
                    q0=None, q0_variance=0.0, blank_mean=None, blank_variance=0.0,
                    background_factor=None, background_record_id=None,
                    sample_variance=None, reference_variance=None, covariance=None,
                    maximum_relative_drift=0.01, tolerance_ticks=0) -> dict:
    if mode not in ("single", "dual"):
        raise ValueError("Unknown detector mode")
    if mode == "single" and not (blank_mean is not None and np.isfinite(blank_mean) and blank_mean > 0):
        # A sequential blank is optional for ordinary raw/relative work. Use
        # only an observed sample baseline; do not populate a fictitious R or B.
        timestamps = np.asarray(sample.get("timestamp", sample.get("timestamps", ())))
        signal = _stream_values(sample)
        valid = _valid_stream(sample, len(signal)) & np.isfinite(signal) & (signal > 0)
        baseline = baseline_statistics(time_s, np.where(valid, signal, np.nan), window_s=baseline_window_s,
                                       maximum_relative_drift=maximum_relative_drift) if time_s is not None else {}
        s0 = q0
        s0_variance = q0_variance
        if s0 is None and baseline.get("stationary"):
            s0 = baseline["mean"]
            s0_variance = baseline["standard_error"] ** 2
        relative = np.full(len(signal), np.nan)
        quality = []
        if s0 is not None and np.isfinite(s0) and s0 > 0:
            relative[valid] = signal[valid] / s0
        else:
            quality.append("missing_observed_sample_baseline")
        if baseline and not baseline.get("stationary"):
            quality.append("nonstationary_baseline")
        variance = np.full(len(signal), np.nan)
        if sample_variance is not None and s0 is not None and s0 > 0:
            supplied = np.broadcast_to(np.asarray(sample_variance, float), signal.shape)
            supported = valid & np.isfinite(supplied) & (supplied >= 0)
            variance[supported] = supplied[supported] / s0 ** 2 + signal[supported] ** 2 * s0_variance / s0 ** 4
        with np.errstate(divide="ignore", invalid="ignore"):
            delta = -np.log10(relative)
            delta_variance = variance / (relative ** 2 * math.log(10) ** 2)
        return {"timestamp": timestamps.copy(), "sample": signal, "reference": np.full(len(signal), np.nan),
                "valid": valid, "ratio": relative, "relative_signal": relative,
                "ratio_label": "Baseline-relative signal S/S0 (observed sample baseline)",
                "normalization_kind": "observed_sample_baseline", "q0": None, "s0": s0,
                "q0_variance": None, "s0_variance": s0_variance, "baseline": baseline,
                "delta_absorbance": delta, "delta_absorbance_label": "Relative log signal -log10(S/S0)",
                "absolute_absorbance": None, "background_factor": None, "background_record_id": None,
                "ratio_variance": variance, "delta_absorbance_variance": delta_variance,
                "quality_flags": quality, "analysis_notes": ["No sequential blank selected; Q=S/R and absolute absorbance are unavailable."],
                "uncertainty_inputs": {"sample_variance": sample_variance, "sample_baseline_variance": s0_variance}}
    if mode == "dual":
        result = align_detectors(sample, reference, tolerance_ticks=tolerance_ticks)
    else:
        st = np.asarray(sample.get("timestamp", sample.get("timestamps", ())))
        s = _stream_values(sample)
        valid_blank = blank_mean is not None and np.isfinite(blank_mean) and blank_mean > 0
        result = {"timestamp": st.copy(), "sample": s, "reference": np.full(len(s), blank_mean if valid_blank else np.nan),
                  "valid": _valid_stream(sample, len(s)) & np.isfinite(s) & (s > 0) & valid_blank,
                  "quality_flags": [] if valid_blank else ["missing_compatible_sequential_blank"]}
    s, r, valid = result["sample"], result["reference"], result["valid"]
    ratio = np.full(len(s), np.nan)
    np.divide(s, r, out=ratio, where=valid)
    baseline = baseline_statistics(time_s, ratio, window_s=baseline_window_s,
                                   maximum_relative_drift=maximum_relative_drift) if time_s is not None else {}
    if q0 is None and baseline.get("stationary"):
        q0 = baseline["mean"]
        q0_variance = baseline["standard_error"] ** 2
    delta = np.full(len(s), np.nan)
    if q0 is not None and np.isfinite(q0) and q0 > 0:
        delta[valid] = -np.log10(ratio[valid] / q0)
    else:
        result["quality_flags"].append("missing_compatible_unpumped_q0")
    if baseline and not baseline.get("stationary"):
        result["quality_flags"].append("nonstationary_baseline")

    variance = np.full(len(s), np.nan)
    covariance_inputs = {"sample_variance": sample_variance, "reference_variance": reference_variance,
                         "sample_reference_covariance": covariance, "q0_variance": q0_variance}
    if sample_variance is not None and (reference_variance is not None or mode == "single"):
        vs = np.broadcast_to(np.asarray(sample_variance, float), s.shape)
        vr = np.broadcast_to(np.asarray(reference_variance if mode == "dual" else blank_variance, float), r.shape)
        cov = np.broadcast_to(np.asarray(0.0 if covariance is None else covariance, float), s.shape)
        covariance_valid = (vs >= 0) & (vr >= 0) & (abs(cov) <= np.sqrt(vs * vr) + np.finfo(float).eps)
        good = valid & covariance_valid
        variance[good] = vs[good] / r[good] ** 2 + s[good] ** 2 * vr[good] / r[good] ** 4 - 2 * s[good] * cov[good] / r[good] ** 3
        variance[good] = np.maximum(0, variance[good])
        if np.any(valid & ~covariance_valid):
            result["quality_flags"].append("invalid_covariance_inputs")
    da_variance = np.full(len(s), np.nan)
    if q0 is not None and q0 > 0:
        da_variance[valid] = (variance[valid] / ratio[valid] ** 2 + q0_variance / q0 ** 2) / math.log(10) ** 2
    absolute = None
    if background_factor is not None:
        if not background_record_id or not np.isfinite(background_factor) or background_factor <= 0:
            result["quality_flags"].append("invalid_measured_background_factor")
        else:
            absolute = np.full(len(s), np.nan)
            absolute[valid] = -np.log10(ratio[valid] / background_factor)
    result.update(ratio=ratio, ratio_label="Reference-normalized signal Q = S/R" if mode == "dual" else "Sequential-blank-normalized signal Q",
                  normalization_kind="matched_reference" if mode == "dual" else "measured_sequential_blank",
                  relative_signal=ratio / q0 if q0 is not None and q0 > 0 else np.full(len(s), np.nan),
                  delta_absorbance_label="Delta absorbance -log10(Q/Q0)",
                  delta_absorbance=delta, absolute_absorbance=absolute, background_factor=background_factor,
                  background_record_id=background_record_id, q0=q0, q0_variance=q0_variance, baseline=baseline,
                  ratio_variance=variance, delta_absorbance_variance=da_variance, uncertainty_inputs=covariance_inputs)
    return result


def response_convolved_exponential(time_s, tau_s: float, response: Mapping) -> np.ndarray:
    """Convolution of H(t) exp(-t/tau) with a characterized response.

    ``kernel_time_s``/``kernel_weight`` are measured impulse quadrature weights
    (areas, not amplitudes). A measured first-order response is also supported.
    No default response is silently assigned to an uncharacterized detector.
    """
    if not response.get("record_id") or not response.get("measured", False):
        raise ValueError("A measured acquisition-response record is required for fitting")
    if tau_s <= 0:
        raise ValueError("Recovery time must be positive")
    t = np.asarray(time_s, float)
    if "kernel_time_s" in response:
        kt, kw = np.asarray(response["kernel_time_s"], float), np.asarray(response["kernel_weight"], float)
        if kt.ndim != 1 or kt.shape != kw.shape or len(kt) < 1 or not np.all(np.isfinite(kt)) or not np.all(np.isfinite(kw)) or np.sum(kw) <= 0:
            raise ValueError("Invalid measured response kernel")
        result = np.zeros_like(t)
        # Loop over kernel samples, never allocate len(trace) x len(kernel).
        for delay, weight in zip(kt, kw / np.sum(kw)):
            support = t >= delay
            result[support] += weight * np.exp(-(t[support] - delay) / tau_s)
        return result
    tr = float(response.get("time_constant_s", response.get("timeconstant_s", float("nan"))))
    if not np.isfinite(tr) or tr <= 0:
        raise ValueError("Measured response time_constant_s must be positive")
    result, support = np.zeros_like(t), t >= 0
    positive = t[support]
    if abs(tau_s - tr) <= 1e-6 * tr:
        result[support] = positive / tr * np.exp(-positive / tr)
    else:
        result[support] = tau_s / (tau_s - tr) * (np.exp(-positive / tau_s) - np.exp(-positive / tr))
    return result


def fit_recovery(time_s, values, response: Mapping | None, *, standard_error=None,
                 tau_bounds_s=None, cancel=None) -> dict:
    """Variable-projection exponential + offset + drift, convolved before fitting.

    Weighted least squares supplies residual covariance and a profile interval.
    The profile interval is conditional on the supplied response and independent
    noise model; residual autocorrelation is exposed for that limitation.
    """
    _cancelled(cancel)
    t, y = np.asarray(time_s, float), np.asarray(values, float)
    valid = np.isfinite(t) & np.isfinite(y)
    if response is None or not response.get("measured") or not response.get("record_id"):
        return {"status": "unresolved_response", "reason": "Measured acquisition response is required; no lifetime fitted"}
    sigma = np.ones(len(y)) if standard_error is None else np.asarray(standard_error, float)
    valid &= np.isfinite(sigma) & (sigma > 0)
    tfit, yfit, weight = t[valid], y[valid], 1 / sigma[valid]
    post = tfit[tfit >= 0]
    if len(tfit) < 12 or len(post) < 8 or np.ptp(post) <= 0:
        return {"status": "insufficient_support", "reason": "Too few valid recovery observations"}
    resolution = float(response.get("resolution_s", response.get("time_constant_s", response.get("timeconstant_s", float("nan")))))
    if not np.isfinite(resolution) or resolution <= 0:
        return {"status": "unresolved_response", "reason": "Measured response resolution is required; no lifetime fitted"}
    diffs = np.diff(np.unique(tfit))
    analysis_resolution = max(resolution, float(np.median(diffs[diffs > 0])))
    lower, upper = tau_bounds_s or (max(float(np.min(diffs[diffs > 0])) / 10, resolution / 20), np.ptp(post) * 100)
    if not 0 < lower < upper:
        raise ValueError("Invalid apparent recovery bounds")

    def solve(logtau):
        _cancelled(cancel)
        kernel = response_convolved_exponential(tfit, math.exp(logtau), response)
        design = np.column_stack((kernel, np.ones(len(tfit)), tfit))
        beta = np.linalg.lstsq(design * weight[:, None], yfit * weight, rcond=None)[0]
        residual = (yfit - design @ beta) * weight
        return float(residual @ residual), beta, design

    grid = np.linspace(math.log(lower), math.log(upper), 100)
    scores = np.asarray([solve(value)[0] for value in grid])
    best = int(np.argmin(scores))
    a, b = grid[max(0, best - 1)], grid[min(len(grid) - 1, best + 1)]
    phi = (math.sqrt(5) - 1) / 2
    for _ in range(48):
        c, d = b - phi * (b - a), a + phi * (b - a)
        if solve(c)[0] < solve(d)[0]:
            b = d
        else:
            a = c
    logtau = (a + b) / 2
    cost, beta, design = solve(logtau)
    tau = math.exp(logtau)
    prediction = np.full(len(y), np.nan)
    prediction[valid] = design @ beta
    residual = np.full(len(y), np.nan)
    residual[valid] = yfit - prediction[valid]
    variance = cost / max(1, len(tfit) - 4)
    eps = 1e-4
    derivative = beta[0] * (response_convolved_exponential(tfit, tau * math.exp(eps), response) - response_convolved_exponential(tfit, tau * math.exp(-eps), response)) / (2 * eps * tau)
    jacobian = np.column_stack((design, derivative)) * weight[:, None]
    covariance_matrix = np.linalg.pinv(jacobian.T @ jacobian) * variance
    stderr = np.sqrt(np.maximum(0, np.diag(covariance_matrix)))
    threshold = cost + 3.841 * (1.0 if standard_error is not None else max(variance, np.finfo(float).eps))
    # Fine local profiling avoids reporting only a coarse-grid interval.
    profile = np.unique(np.concatenate((grid, np.linspace(max(math.log(lower), logtau - 1), min(math.log(upper), logtau + 1), 121), [logtau])))
    profile_scores = np.asarray([solve(value)[0] for value in profile])
    accepted = profile[profile_scores <= threshold]
    interval = [float(math.exp(accepted[0])), float(math.exp(accepted[-1]))]
    residual_valid = residual[valid]
    autocorrelation = float(np.corrcoef(residual_valid[:-1], residual_valid[1:])[0, 1]) if np.std(residual_valid) > 0 else 0.0
    unresolved = tau < analysis_resolution or abs(beta[0]) <= 3 * stderr[0] or interval[1] >= upper * 0.99
    return {"status": "unresolved_apparent_component" if unresolved else "apparent_recovery_fit",
            "model": "measured_response * [amplitude H(t) exp(-t/tau)] + offset + drift*t",
            "parameter_order": ["amplitude", "offset", "drift_per_s", "tau_s"],
            "amplitude": float(beta[0]), "offset": float(beta[1]), "drift_per_s": float(beta[2]), "tau_s": tau,
            "standard_errors": stderr, "parameter_covariance": covariance_matrix,
            "tau_profile_95_s": interval, "profile_tau_s": np.exp(profile), "profile_cost": profile_scores,
            "prediction": prediction, "residuals": residual, "residual_lag1_correlation": autocorrelation,
            "residual_rms": float(np.sqrt(np.mean(residual_valid ** 2))), "valid_count": int(valid.sum()),
            "response_record_id": response["record_id"], "response_resolution_s": resolution,
            "analysis_sampling_resolution_s": analysis_resolution,
            "uncertainty_limit": "Conditional on measured response and supplied noise; serial correlation and response uncertainty may widen intervals.",
            "claim": "Apparent instrument-resolved fixed-point recovery only"}


def recovery_evidence(time_s, delta_absorbance, *, window_s=None, absolute_tolerance=0.001) -> dict:
    t, y = np.asarray(time_s, float), np.asarray(delta_absorbance, float)
    finite = np.isfinite(t) & np.isfinite(y) & (t >= 0)
    if not np.any(finite):
        return {"recovered": False, "status": "no_valid_post_event_support"}
    stop = float(np.max(t[finite]))
    start = float(np.min(t[finite]))
    window = window_s or (start + 0.9 * (stop - start), stop)
    tail = finite & (t >= window[0]) & (t <= window[1])
    if tail.sum() < 3:
        return {"recovered": False, "status": "insufficient_recovery_support", "observation_limit_s": stop}
    mean = float(np.mean(y[tail]))
    error = float(np.std(y[tail], ddof=1) / math.sqrt(tail.sum()))
    peak = float(np.max(abs(y[finite])))
    recovered = abs(mean) + 1.96 * error <= absolute_tolerance
    return {"recovered": recovered, "status": "return_within_tolerance" if recovered else "incomplete_recovery_right_censored",
            "tail_delta_absorbance": mean, "tail_standard_error": error, "absolute_tolerance": absolute_tolerance,
            "remaining_fixed_point_fraction": abs(mean) / peak if peak else None,
            "observation_limit_s": stop, "claim_limit": "Return at this fixed point alone does not establish full spectral/state reset equivalence"}


def aggregate_events(events) -> dict:
    """Only pool equivalent events at the same position on identical support."""
    eligible, excluded = [], []
    for event in events:
        if event.get("kind", "sample") in ("blank", "preliminary", "no_pump", "off_band"):
            excluded.append({"event_index": event.get("event_index"), "reason": "Control retained individually"})
        elif not event.get("equivalent_state", False):
            excluded.append({"event_index": event.get("event_index"), "reason": "Equivalent-state reset not established"})
        elif event.get("quality_flags"):
            excluded.append({"event_index": event.get("event_index"), "reason": "Quality flags; shown individually"})
        else:
            eligible.append(event)
    groups = {}
    for event in eligible:
        groups.setdefault(event.get("position_cm1"), []).append(event)
    aggregates = []
    for position, group in groups.items():
        common = set(map(float, group[0]["time_s"]))
        for event in group[1:]:
            common &= set(map(float, event["time_s"]))
        ticks = np.asarray(sorted(common))
        if len(ticks) == 0:
            excluded.extend({"event_index": event.get("event_index"), "reason": "No identical relative timestamp support for this position; events retained individually"} for event in group)
            continue
        stack = []
        for event in group:
            index = {float(t): i for i, t in enumerate(event["time_s"])}
            stack.append([event["delta_absorbance"][index[t]] for t in ticks])
        stack = np.asarray(stack)
        count = np.sum(np.isfinite(stack), axis=0)
        mean = np.divide(np.nansum(stack, axis=0), count, out=np.full(len(ticks), np.nan), where=count > 0)
        variance = np.divide(np.nansum((stack - mean) ** 2, axis=0), count - 1, out=np.full(len(ticks), np.nan), where=count > 1)
        aggregates.append({"position_cm1": position, "time_s": ticks, "mean_delta_absorbance": mean,
                           "standard_error": np.sqrt(variance / np.maximum(count, 1)), "valid_event_count": count,
                           "event_indices": [event.get("event_index") for event in group]})
    trends = [{"event_index": e.get("event_index"), "acquisition_order": e.get("acquisition_order", i),
               "position_cm1": e.get("position_cm1"), "dose": e.get("dose"),
               "amplitude": e.get("recovery_fit", {}).get("amplitude"), "baseline_mean": e.get("baseline", {}).get("mean"),
               "recovery": e.get("recovery")} for i, e in enumerate(events)]
    return {"aggregates": aggregates, "excluded": excluded, "order_dose_trends": trends,
            "independence_limit": "Technical events do not replace independent sample preparations"}


def _blank_at_position(blank, position_index):
    if not blank:
        return None, 0.0
    # A full sequential blank must have completed every declared position.
    if blank.get("status") not in ("complete", "completed") or blank.get("kind") != "blank":
        return None, 0.0
    for event in blank.get("events", blank.get("analysis", {}).get("events", ())):
        if event.get("position_index", 0) == position_index:
            baseline = event.get("baseline", {})
            if baseline.get("stationary"):
                mean = baseline.get("mean")
                variance = baseline.get("standard_error", baseline.get("std", 0.0) / math.sqrt(max(1, baseline.get("count", 1)))) ** 2
                return mean, variance
    return None, 0.0


def analyze_run(record, preliminary=None, blank=None, cancel=None, *, max_points=100_000,
                max_points_per_event=6000) -> dict:
    """Reprocess retained chunks with an explicit, bounded analysis point budget.

    Full native acquisition is retained unchanged. Two passes select regularly
    spaced actual observations and event endpoints, so plotting/fitting a long
    run never concatenates its entire native trace. Selection is disclosed as
    an analysis subset; gap masks and discarded support are never filled.
    Streaming native baseline statistics, when supplied by acquisition, take
    precedence over the subset estimate. This is not hidden acquisition dead time.
    """
    _cancelled(cancel)
    validate_record(record)
    mode = record.get("mode", "single")
    settings = record.get("settings", record.get("plan", {}).get("settings", {}))
    flags = list(record.get("quality_flags", ()))
    if max_points < 16 or max_points_per_event < 16:
        raise ValueError("Analysis point budgets must permit at least 16 observations")
    if preliminary is not None:
        compatible, reasons = compatible_record(preliminary, record)
        if not compatible:
            flags.extend(f"preliminary incompatible: {reason}" for reason in reasons)
    blank_compatible = blank is not None and compatible_record(blank, record)[0]
    if mode == "single" and record.get("kind") != "blank" and not blank_compatible:
        if blank is not None:
            flags.append("incompatible_sequential_blank_acquisition_settings")
        blank = None
    if mode == "dual":
        blank = None
    groups: dict[int, dict] = {}
    event_metadata = {int(event.get("event_index", i)): event for i, event in enumerate(record.get("events", ()))}
    for chunk in iter_native_chunks(record):
        _cancelled(cancel)
        metadata = {**chunk.get("metadata", {}), **{k: chunk[k] for k in ("event_index", "position_index", "kind") if k in chunk}}
        index = int(metadata.get("event_index", 0))
        ts = np.asarray(chunk.get("sample", {}).get("timestamp", ()))
        group = groups.setdefault(index, {"count": 0, "metadata": metadata, "first_tick": None})
        group["count"] += len(ts)
        if len(ts) and group["first_tick"] is None:
            group["first_tick"] = int(ts[0])
    if not groups:
        return {"analysis_version": ANALYSIS_VERSION, "events": [], "quality_flags": [*flags, "no_retained_native_data"], "claim_limits": CLAIM_LIMITS}
    budget = min(max_points_per_event, max(16, max_points // len(groups)))
    for index, group in groups.items():
        group["stride"] = max(1, math.ceil(group["count"] / max(1, budget - 2)))
        group["seen"] = 0
        group["values"] = {k: [] for k in ("timestamp", "sample", "reference", "valid", "gap")}
        group["flags"] = []
        group["clockbase_hz"] = event_metadata.get(index, {}).get("clockbase_hz")
    for chunk in iter_native_chunks(record):
        _cancelled(cancel)
        metadata = {**chunk.get("metadata", {}), **{k: chunk[k] for k in ("event_index", "position_index", "kind") if k in chunk}}
        group = groups[int(metadata.get("event_index", 0))]
        stream = chunk.get("sample", {})
        timestamps = np.asarray(stream.get("timestamp", ()))
        if len(timestamps) == 0:
            continue
        clock = float(chunk.get("clockbase_hz", group["clockbase_hz"] or record.get("clockbase_hz", 1)))
        group["clockbase_hz"] = clock
        if mode == "dual":
            matched = align_detectors(stream, chunk.get("reference"))
        else:
            signal = _stream_values(stream)
            matched = {"timestamp": timestamps, "sample": signal, "reference": np.full(len(signal), np.nan),
                       "valid": _valid_stream(stream, len(signal)) & np.isfinite(signal) & (signal > 0), "quality_flags": []}
        group["flags"].extend(matched["quality_flags"])
        # Detect missing native time support before decimation; insert a visible
        # NaN at the next selected point so plotting cannot bridge a native gap.
        rate = settings.get("sample_rate_sps") or record.get("plan", {}).get("resolved", {}).get("sample", {}).get("rate_sps")
        gap = np.zeros(len(timestamps), dtype=bool)
        if rate:
            expected = clock / float(rate)
            ticks = [group.get("last_tick", int(timestamps[0]) - expected), *map(int, timestamps)]
            gap = np.asarray([b - a > 1.6 * expected or b <= a for a, b in zip(ticks[:-1], ticks[1:])])
        group["last_tick"] = int(timestamps[-1])
        if np.any(gap):
            group["flags"].append("native_timestamp_gap")
        index = np.arange(len(timestamps)) + group["seen"]
        selected = (index % group["stride"] == 0) | (index == group["count"] - 1)
        indices = np.flatnonzero(selected)
        gap_prefix = np.cumsum(gap)
        previous_selected = -1
        selected_gap = []
        for j in indices:
            has_gap = bool(gap_prefix[j] - (gap_prefix[previous_selected] if previous_selected >= 0 else 0)) or bool(group.get("pending_gap", False))
            selected_gap.append(has_gap)
            group["pending_gap"] = False
            previous_selected = j
        if len(indices):
            group["pending_gap"] = bool(np.any(gap[indices[-1] + 1:]))
        else:
            group["pending_gap"] = bool(group.get("pending_gap", False) or np.any(gap))
        if len(indices):
            for name in ("timestamp", "sample", "reference", "valid"):
                group["values"][name].append(matched[name][selected])
            group["values"]["gap"].append(np.asarray(selected_gap, dtype=bool))
        group["seen"] += len(timestamps)
    results = []
    response = record.get("measured_response", record.get("acquisition_response", record.get("plan", {}).get("resolved", {}).get("acquisition_response")))
    for index, group in sorted(groups.items()):
        _cancelled(cancel)
        meta = {**group["metadata"], **event_metadata.get(index, {})}
        arrays = {k: np.concatenate(v) if v else np.asarray([]) for k, v in group["values"].items()}
        if not len(arrays["timestamp"]):
            continue
        epoch = meta.get("original_pump_timestamp")
        pumped = int(meta.get("expected_pump_count", 0)) > 0
        if epoch is None:
            epoch = group["first_tick"]
            if pumped:
                group["flags"].append("missing_observed_pump_epoch")
        time = time_from_ticks(arrays["timestamp"], int(epoch), group["clockbase_hz"])
        window = settings.get("baseline_window_s") if pumped else (float(time[0]), float(time[-1]))
        if window is None:
            window = (-float(settings.get("pre_observation_s", 1.0)), 0.0)
        blank_mean, blank_variance = _blank_at_position(blank, int(meta.get("position_index", 0)))
        native_baseline = meta.get("baseline", {})
        q0 = None
        q0_variance = 0.0
        if native_baseline.get("stationary"):
            q0 = native_baseline.get("mean")
            q0_variance = native_baseline.get("std", 0.0) ** 2 / max(1, native_baseline.get("count", 1))
            if mode == "single" and blank_mean:
                q0_variance = q0_variance / blank_mean ** 2 + q0 ** 2 * blank_variance / blank_mean ** 4
                q0 /= blank_mean
        sample = {"timestamp": arrays["timestamp"], "value": arrays["sample"], "valid": arrays["valid"] & ~arrays["gap"]}
        reference = {"timestamp": arrays["timestamp"], "value": arrays["reference"]}
        kind = record.get("kind", "measurement")
        if kind == "blank":
            stats = baseline_statistics(time, np.where(sample["valid"], arrays["sample"], np.nan), window_s=(time[0], time[-1]),
                                         maximum_relative_drift=settings.get("baseline_drift_fraction", 0.01))
            normalized = {"sample": arrays["sample"], "reference": arrays["reference"], "ratio": np.full(len(time), np.nan),
                          "delta_absorbance": np.full(len(time), np.nan), "absolute_absorbance": None,
                          "normalization_kind": "raw_blank", "ratio_label": "Blank detector signal; no sample ratio",
                          "delta_absorbance_label": "Blank-only record; no sample-relative log signal",
                          "baseline": native_baseline or stats, "quality_flags": [] if stats["stationary"] else ["nonstationary_baseline"]}
        else:
            background = record.get("background_balance", {})
            if "positions" in background:
                background = next((value for value in background["positions"] if value.get("position_cm1") == meta.get("position_cm1")), {})
            background_applicable = (background.get("measured") and background.get("mode") == mode
                                     and background.get("position_cm1") == meta.get("position_cm1"))
            pre_support = sample["valid"] & (time >= window[0]) & (time <= window[1])
            uncertainty = {}
            if mode == "dual":
                pre_support &= np.isfinite(arrays["reference"]) & (arrays["reference"] > 0)
                if pre_support.sum() > 2:
                    detector_covariance = np.cov(arrays["sample"][pre_support], arrays["reference"][pre_support], ddof=1)
                    uncertainty = {"sample_variance": detector_covariance[0, 0],
                                   "reference_variance": detector_covariance[1, 1],
                                   "covariance": detector_covariance[0, 1]}
            elif pre_support.sum() > 2:
                uncertainty = {"sample_variance": np.var(arrays["sample"][pre_support], ddof=1)}
            normalized = normalize_trace(sample, reference if mode == "dual" else None, mode=mode,
                                         time_s=time, baseline_window_s=window, q0=q0, q0_variance=q0_variance,
                                         blank_mean=blank_mean, blank_variance=blank_variance,
                                         background_factor=background.get("factor") if background_applicable else None,
                                         background_record_id=background.get("record_id"),
                                         maximum_relative_drift=settings.get("baseline_drift_fraction", 0.01), **uncertainty)
            normalized["uncertainty_inputs"]["detector_covariance_source"] = "Matched pre-pump actual observations in the disclosed bounded analysis subset"
            if background and not background_applicable:
                normalized.setdefault("analysis_notes", []).append("Supplied background factor does not support absolute absorbance at this detector mode/position; raw and relative data are unchanged.")
            if native_baseline:
                normalized["baseline"] = {**normalized["baseline"], **native_baseline, "native_streaming_statistics": True}
                if native_baseline.get("stationary"):
                    normalized["quality_flags"] = [flag for flag in normalized["quality_flags"] if flag != "nonstationary_baseline"]
        event_flags = list(dict.fromkeys([*flags, *group["flags"], *normalized["quality_flags"]]))
        if len(meta.get("pump_timestamps", ())) != int(meta.get("expected_pump_count", 0)):
            event_flags.append("observed_pump_count_mismatch")
        result = {**meta, **normalized, "event_index": index, "kind": "no_pump" if not pumped and kind == "measurement" else kind,
                  "wavenumber_cm1": meta.get("position_cm1"), "time_s": time, "original_pump_timestamp": meta.get("original_pump_timestamp"),
                  "analysis_epoch_timestamp": int(epoch), "quality_flags": event_flags,
                  "native_count": group["count"], "analysis_count": len(time), "analysis_stride": group["stride"],
                  "analysis_sampling": "Every stride-th actual native observation plus endpoint; no interpolation",
                  "measured_pump_time_s": [time_from_ticks(np.asarray([v], dtype=np.uint64), int(epoch), group["clockbase_hz"])[0] for v in meta.get("pump_timestamps", ())]}
        result["gap_mask"] = arrays["gap"]
        # Keep magnitude at clipped points visible, but never draw through an
        # unobserved time interval. Exact pre-mask values remain in native files.
        result["sample"] = np.where(arrays["gap"], np.nan, result["sample"])
        result["reference"] = np.where(arrays["gap"], np.nan, result["reference"])
        if "off" in str(meta.get("position_label", "")).lower():
            result["kind"] = "off_band"
        result["recovery_fit"] = fit_recovery(time, normalized["delta_absorbance"], response, cancel=cancel) if pumped and meta.get("original_pump_timestamp") is not None else {"status": "unpumped_control" if not pumped else "unresolved_time_zero"}
        fraction = float(settings.get("reset_tolerance_fraction", 0.02))
        recovery_tolerance = math.log10(1 + fraction) if 0 < fraction < 1 else 0.0
        result["recovery"] = recovery_evidence(time, normalized["delta_absorbance"], absolute_tolerance=recovery_tolerance) if pumped else {"status": "unpumped_control", "recovered": False}
        integration = settings.get("integration_window_s")
        if integration:
            keep = (time >= integration[0]) & (time <= integration[1]) & np.isfinite(normalized["delta_absorbance"])
            result["integration_window_summary"] = {"window_s": integration, "valid_count": int(keep.sum()),
                "mean_delta_absorbance": float(np.mean(normalized["delta_absorbance"][keep])) if keep.any() else None,
                "standard_error": float(np.std(normalized["delta_absorbance"][keep], ddof=1) / math.sqrt(keep.sum())) if keep.sum() > 1 else None,
                "claim": "Mean over observed support; gaps excluded and not interpolated"}
        results.append(result)
    all_flags = list(dict.fromkeys([*flags, *(flag for event in results for flag in event["quality_flags"])]))
    return {"analysis_version": ANALYSIS_VERSION, "schema_version": SCHEMA_VERSION, "experiment_id": EXPERIMENT_ID,
            "mode": mode, "events": results, "quality_flags": all_flags, "claim_limits": CLAIM_LIMITS,
            "analysis_point_budget": max_points, "native_values_preserved": True,
            "response": response, **aggregate_events(results)}
