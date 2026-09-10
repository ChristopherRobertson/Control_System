"""Native trajectory reconstruction and bounded apparent-recovery analysis.

No reconstructed image pixels are treated as independent measurements. Detector
streams are matched on observed timestamps, never interpolated across missing
support. Only calibrated trajectory markers are interpolated within their
declared continuous support. Forward and reverse observations remain separate.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from .data import (ANALYSIS_VERSION, BandKinetic, ClockCorrection, NativeKernel,
                   NativeMovie, NativeScan, ReconstructedMovie,
                   ReconstructedPoints, RecoveryFit, SpectralBaseline,
                   SpectrumSupport, StateAssessment, compatibility_mismatches)


class ProcessingCancelled(InterruptedError):
    pass


def _check_cancel(cancelled: Callable[[], bool] | None) -> None:
    if cancelled and cancelled():
        raise ProcessingCancelled("Acquisition stopped during analysis")


def aligned_seconds(values: Any, *, unit_s: float = 1.0, origin: int | float = 0,
                    correction: ClockCorrection | None = None) -> np.ndarray:
    """Subtract native integer origin before floating conversion (large ticks)."""
    native = np.asarray(values)
    if np.issubdtype(native.dtype, np.integer) and isinstance(origin, (int, np.integer)):
        relative = np.array([int(v) - int(origin) for v in native.reshape(-1)], dtype=float).reshape(native.shape)
    else:
        relative = np.asarray(native, dtype=float) - origin
    c = correction or ClockCorrection("shared")
    if not np.isfinite(unit_s) or unit_s <= 0 or not np.isfinite(c.scale) or c.scale <= 0:
        raise ValueError("Clock scale and native timestamp unit must be positive finite values")
    return relative * unit_s * c.scale + c.offset_s - c.latency_s


def _time(stream: Any, clocks: Mapping[str, ClockCorrection]) -> np.ndarray:
    return aligned_seconds(stream.timestamps_s, unit_s=stream.timestamp_unit_s,
                           origin=stream.timestamp_origin, correction=clocks.get(stream.clock_id))


def _array(value: Any, n: int, default: float = np.nan) -> np.ndarray:
    if value is None:
        return np.full(n, default, dtype=float)
    result = np.asarray(value, dtype=float)
    if result.ndim == 0:
        return np.full(n, result.item(), dtype=float)
    if result.shape != (n,):
        raise ValueError(f"Native data length mismatch: expected {n}, found {result.shape}")
    return result


def _flags(stream: Any, n: int) -> dict[str, np.ndarray]:
    flags = stream.flags
    if not isinstance(flags, Mapping):
        return {str(flag): np.ones(n, dtype=bool) for flag in flags}
    return {str(name): np.broadcast_to(np.asarray(flag, dtype=bool), (n,)).copy()
            for name, flag in flags.items()}


def _nearest(source: np.ndarray, target: np.ndarray, tolerance: float) -> tuple[np.ndarray, np.ndarray]:
    indices = np.full(len(target), -1, dtype=int)
    supported = np.zeros(len(target), dtype=bool)
    finite = np.flatnonzero(np.isfinite(source))
    if not len(finite):
        return indices, supported
    order = finite[np.argsort(source[finite], kind="stable")]
    ordered = source[order]
    pos = np.searchsorted(ordered, target)
    left, right = np.maximum(0, pos - 1), np.minimum(len(order) - 1, pos)
    choose = np.where(np.abs(ordered[left] - target) <= np.abs(ordered[right] - target), left, right)
    indices[:] = order[choose]
    supported = np.isfinite(target) & (np.abs(source[indices] - target) <= tolerance)
    indices[~supported] = -1
    return indices, supported


def _native_normalized(scan: NativeScan, mode: str, clocks: Mapping[str, ClockCorrection],
                       alignment_tolerance_s: float) -> tuple[np.ndarray, ...]:
    times = _time(scan.sample, clocks)
    n = len(times)
    sample = _array(scan.sample.values, n)
    flags = _flags(scan.sample, n)
    for flag in scan.flags:
        flags[f"scan_{flag}"] = np.ones(n, dtype=bool)
    flags["nonfinite_sample"] = ~np.isfinite(sample)
    flags["nonpositive_sample"] = sample <= 0
    flags["nonfinite_timestamp"] = ~np.isfinite(times)
    variance_sample = _array(scan.sample.variance, n)
    reference_indices = np.full(n, -1, dtype=int)
    normalized, variance = sample.copy(), variance_sample.copy()
    if mode == "dual":
        normalized[:], variance[:] = np.nan, np.nan
        flags["missing_reference"] = np.ones(n, dtype=bool)
        if scan.reference is not None:
            rtimes = _time(scan.reference, clocks)
            ref = _array(scan.reference.values, len(rtimes))
            reference_indices, support = _nearest(rtimes, times, alignment_tolerance_s)
            # A reference observation cannot count as simultaneous support for two
            # sample observations merely because a broad tolerance was requested.
            used: set[int] = set()
            for i in np.flatnonzero(support):
                index = int(reference_indices[i])
                if index in used:
                    support[i] = False
                    reference_indices[i] = -1
                else:
                    used.add(index)
            idx = np.maximum(reference_indices, 0)
            refs = ref[idx] if len(ref) else np.full(n, np.nan)
            valid_ref = support & np.isfinite(refs) & (refs > 0)
            flags["missing_reference"] = ~support
            flags["bad_reference"] = support & ~valid_ref
            for name, mask in _flags(scan.reference, len(rtimes)).items():
                flags[f"reference_{name}"] = support & mask[idx] if len(mask) else np.zeros(n, bool)
            with np.errstate(invalid="ignore", divide="ignore"):
                normalized[valid_ref] = sample[valid_ref] / refs[valid_ref]
                vr = _array(scan.reference.variance, len(rtimes))[idx] if len(rtimes) else np.full(n, np.nan)
                # Absent detector covariance is unknown, never implicitly zero.
                cov = _array(scan.sample_reference_covariance, n)
                variance[valid_ref] = (variance_sample / refs**2 + sample**2 * vr / refs**4
                                       - 2 * sample * cov / refs**3)[valid_ref]
            flags["invalid_covariance"] = np.isfinite(variance) & (variance < -1e-14)
            variance = np.where(variance >= -1e-14, np.maximum(variance, 0), np.nan)
    valid = np.isfinite(normalized) & (normalized > 0)
    for mask in flags.values():
        valid &= ~mask
    return times, normalized, variance, valid, flags, reference_indices


def _spectral_coordinates(scan: NativeScan, times: np.ndarray,
                          clocks: Mapping[str, ClockCorrection]) -> tuple[np.ndarray, np.ndarray]:
    trajectory = scan.trajectory
    marker_times = _time(trajectory, clocks)
    nu = _array(trajectory.wavenumbers_cm1, len(marker_times))
    output = np.full(len(times), np.nan)
    valid = np.zeros(len(times), dtype=bool)
    if not trajectory.calibration_id or len(marker_times) < 2:
        return output, valid
    if not np.all(np.isfinite(marker_times)) or not np.all(np.isfinite(nu)) or np.any(np.diff(marker_times) <= 0):
        return output, valid
    output = np.interp(times, marker_times, nu, left=np.nan, right=np.nan)
    valid = np.isfinite(output)
    max_gap = trajectory.metadata.get("max_marker_gap_s")
    if max_gap is not None:
        pos = np.clip(np.searchsorted(marker_times, times), 1, len(marker_times)-1)
        valid &= (marker_times[pos] - marker_times[pos-1] <= float(max_gap)) | np.isin(times, marker_times)
        output[~valid] = np.nan
    return output, valid


def baseline_mismatches(baseline: SpectralBaseline, movie: NativeMovie,
                        *, background: bool = False) -> tuple[str, ...]:
    errors = list(compatibility_mismatches(
        {"experiment_id": movie.experiment_id, "schema_version": movie.schema_version,
         "mode": movie.mode, "condition_id": movie.condition_id},
        {name: getattr(baseline, name) for name in ("experiment_id", "schema_version", "mode", "condition_id")}))
    if not baseline.complete:
        errors.append("Reference record is incomplete")
    if not baseline.accepted:
        errors.append("Reference record has not been accepted")
    expected_kind = "background" if background else ("q0" if movie.mode == "dual" else "single_baseline")
    if baseline.kind != expected_kind:
        errors.append(f"Reference kind mismatch: expected {expected_kind}, found {baseline.kind}")
    errors.extend(compatibility_mismatches(movie.metadata.get("compatibility", {}), baseline.compatibility))
    recorded_axes = baseline.metadata.get("trajectory_calibration_ids_by_direction", {})
    for scan in movie.scans:
        identities = recorded_axes.get(scan.trajectory.direction)
        if identities is not None and scan.trajectory.calibration_id not in identities:
            errors.append(f"Trajectory calibration mismatch for {scan.trajectory.direction}: {scan.trajectory.calibration_id}")
    return tuple(errors)


def _reference_values(baseline: SpectralBaseline, direction: str, nu: np.ndarray,
                      tolerance_cm1: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values, variance = np.full(len(nu), np.nan), np.full(len(nu), np.nan)
    supported = np.zeros(len(nu), dtype=bool)
    spectra = _merge_spectra(baseline.spectra)
    for spectrum in spectra:
        if spectrum.direction != direction:
            continue
        axis = np.asarray(spectrum.wavenumbers_cm1, dtype=float)
        indices, support = _nearest(axis, nu, tolerance_cm1)
        if not len(axis):
            continue
        idx = np.maximum(indices, 0)
        svalues = _array(spectrum.values, len(axis))
        variance[support] = _array(spectrum.variance, len(axis))[idx[support]]
        values[support] = svalues[idx[support]]
        source_valid = np.ones(len(axis), bool) if spectrum.valid is None else np.asarray(spectrum.valid, bool)
        supported |= support & source_valid[idx] & np.isfinite(values) & (values > 0)
    return values, variance, supported


def reconstruct_movie(movie: NativeMovie, baseline: SpectralBaseline | None = None,
                      background: SpectralBaseline | None = None, *,
                      band_windows_cm1: Sequence[Sequence[float]] = (),
                      offband_windows_cm1: Sequence[Sequence[float]] = (),
                      alignment_tolerance_s: float = 0.0,
                      spectral_match_tolerance_cm1: float = 1e-6,
                      cancelled: Callable[[], bool] | None = None) -> ReconstructedMovie:
    if movie.experiment_id != "repeated_rapid_scan" or movie.schema_version != 1 or movie.mode not in ("single", "dual"):
        raise ValueError("Incompatible experiment, mode or native movie schema")
    for candidate, is_background in ((baseline, False), (background, True)):
        if candidate is not None:
            problems = baseline_mismatches(candidate, movie, background=is_background)
            if problems:
                raise ValueError("; ".join(problems))
    # Remove the common epoch before adding any sub-nanosecond native offsets.
    # Subtracting two float64 Unix timestamps afterward would erase fine timing.
    clock_anchor = movie.clock_corrections[0].offset_s if movie.clock_corrections else 0.0
    clocks = {clock.clock_id: replace(clock, offset_s=clock.offset_s-clock_anchor)
              for clock in movie.clock_corrections}
    expected_count = int(movie.metadata.get("expected_pump_count", 1))
    if expected_count not in (0, 1):
        raise ValueError("A repeated recovery movie authorizes exactly one pump, or zero for an explicit control")
    observed = tuple(p for p in movie.pump_observations if p.independently_observed)
    warnings: list[str] = []
    pump_valid = len(observed) == expected_count and len(movie.pump_observations) == expected_count
    if not pump_valid:
        warnings.append(f"Pump observation count mismatch: expected {expected_count}, independently observed {len(observed)}")
    epoch = 0.0
    basis = "unpumped_control" if expected_count == 0 else "unresolved"
    if pump_valid and expected_count == 1:
        pump = observed[0]
        epoch = float(aligned_seconds([pump.timestamp_s], unit_s=pump.timestamp_unit_s,
                                     origin=pump.timestamp_origin, correction=clocks.get(pump.clock_id))[0])
        if not np.isfinite(epoch):
            pump_valid = False
            warnings.append("Independent pump observation has no finite native timestamp")
        basis = pump.basis
        if basis == "calibrated_optical_time_zero":
            warnings.append("Time zero uses calibrated electrical-to-optical correction; optical arrival was not independently observed for each event")
        elif basis != "optical_arrival":
            warnings.append("Time zero uses observed electrical sync; optical arrival/IRF remains unverified")
    all_clocks = {s.sample.clock_id for s in movie.scans} | {s.trajectory.clock_id for s in movie.scans}
    all_clocks |= {s.reference.clock_id for s in movie.scans if s.reference is not None}
    all_clocks |= {p.clock_id for p in observed}
    missing_clocks = all_clocks - set(clocks) if len(all_clocks) > 1 else set()
    if missing_clocks:
        warnings.append("Missing documented cross-clock alignment: " + ", ".join(sorted(missing_clocks)))
    points: list[ReconstructedPoints] = []
    kinetics: list[BandKinetic] = []
    for scan in movie.scans:
        _check_cancel(cancelled)
        times, q, vq, valid, flags, reference_indices = _native_normalized(scan, movie.mode, clocks, alignment_tolerance_s)
        nu, spectral_valid = _spectral_coordinates(scan, times, clocks)
        flags["missing_calibrated_trajectory"] = ~spectral_valid
        flags["unresolved_pump_epoch"] = np.full(len(times), not pump_valid)
        flags["unresolved_clock_alignment"] = np.full(len(times), bool(missing_clocks))
        valid &= spectral_valid & pump_valid & (not missing_clocks)
        delta, absolute, vdelta = (np.full(len(times), np.nan) for _ in range(3))
        direction = scan.trajectory.direction
        if baseline is not None:
            q0, vq0, support = _reference_values(baseline, direction, nu, spectral_match_tolerance_cm1)
            flags["missing_baseline_support"] = ~support
            valid &= support
            with np.errstate(divide="ignore", invalid="ignore"):
                delta[valid] = -np.log10(q[valid] / q0[valid])
                vdelta[valid] = ((vq/q**2 + vq0/q0**2) / np.log(10)**2)[valid]
        if background is not None:
            b, _, support = _reference_values(background, direction, nu, spectral_match_tolerance_cm1)
            flags["missing_background_support"] = ~support
            absolute_valid = valid & support
            absolute[absolute_valid] = -np.log10(q[absolute_valid]/b[absolute_valid])
        dt = np.diff(times)
        expected_spacing = scan.sample.metadata.get("expected_sample_interval_s")
        threshold = float(expected_spacing)*1.5 if expected_spacing is not None else (np.median(dt[dt>0])*1.5 if np.any(dt>0) else np.inf)
        gap_indices = np.flatnonzero((dt > threshold) | (dt <= 0))
        gaps = tuple((float(times[i]-epoch), float(times[i+1]-epoch)) for i in gap_indices)
        flags["nonmonotonic_timestamp"] = np.r_[False, dt <= 0] if len(times) else np.zeros(0, bool)
        valid &= ~flags["nonmonotonic_timestamp"]
        result = ReconstructedPoints(scan.scan_index, direction, times-epoch, nu, q, delta,
                                     absolute, vq, vdelta, valid, flags, gaps,
                                     np.arange(len(times)), reference_indices)
        points.append(result)
        for kind, windows in (("band", band_windows_cm1), ("offband", offband_windows_cm1)):
            kinetics.extend(_band_integral(movie.movie_id, result, tuple(map(float, window)), kind) for window in windows)
    if baseline is None:
        warnings.append("Unpumped sample baseline absent: reference-normalized signal only; delta absorbance unavailable")
    if background is None:
        warnings.append("Measured background/path balance B absent: absolute absorbance unavailable")
    status = movie.status if pump_valid and not missing_clocks else "rejected"
    return ReconstructedMovie(movie.movie_id, movie.mode, movie.condition_id, tuple(points), tuple(kinetics),
                              basis, status, tuple(warnings),
                              {"native_movie_id": movie.movie_id, "requested_phase_offset_s": movie.phase_offset_s,
                               "baseline_id": getattr(baseline, "record_id", None),
                               "background_id": getattr(background, "record_id", None),
                               "clock_corrections": movie.clock_corrections,
                               "analysis_version": ANALYSIS_VERSION,
                               "uncertainty_assumptions": "Independent baseline acquisition; temporal filter correlation is not included in pointwise variances",
                               "direction_pooling": "not_performed", "fitted_support": "native_points_only"})


def _band_integral(movie_id: str, points: ReconstructedPoints, window: tuple[float, float], kind: str) -> BandKinetic:
    nu, time, y = map(np.asarray, (points.wavenumbers_cm1, points.time_s, points.delta_absorbance))
    in_window = (nu >= window[0]) & (nu <= window[1])
    valid = np.asarray(points.valid) & np.isfinite(y) & in_window
    n = len(nu)
    weights = np.zeros(n)
    coverage = 0.0
    # Integrate only adjacent native samples: invalid points and timestamp gaps
    # remain holes, even when sorting wavelengths would conceal the omission.
    for i in range(max(0, n-1)):
        if not (valid[i] and valid[i+1]):
            continue
        if any(min(time[i:i+2]) <= min(gap) and max(time[i:i+2]) >= max(gap) for gap in points.gaps_s):
            continue
        width = abs(nu[i+1]-nu[i])
        weights[i:i+2] += width/2
        coverage += width
    area = float(np.dot(weights, np.nan_to_num(y, nan=0))) if np.any(weights) else float("nan")
    variances = np.asarray(points.variance_delta_absorbance)
    selected = weights > 0
    variance = float(np.dot(weights[selected]**2, variances[selected])) if np.any(selected) and np.all(np.isfinite(variances[selected])) else float("nan")
    fraction = min(1.0, coverage/(window[1]-window[0])) if window[1]>window[0] else 0.0
    return BandKinetic(movie_id, points.scan_index, points.direction, window, area, variance,
                       float(np.min(time[valid])) if np.any(valid) else float("nan"),
                       float(np.max(time[valid])) if np.any(valid) else float("nan"),
                       fraction, bool(fraction >= .8 and np.any(selected)), kind)


def build_baseline(movie: NativeMovie, *, kind: str | None = None,
                   pre_pump_only: bool = True, record_id: str | None = None,
                   accepted: bool = False, alignment_tolerance_s: float = 0.0) -> SpectralBaseline:
    reconstructed = reconstruct_movie(movie, alignment_tolerance_s=alignment_tolerance_s)
    grouped: dict[str, dict[float, list[tuple[float, float]]]] = defaultdict(lambda: defaultdict(list))
    complete_support = True
    for points in reconstructed.points:
        selected = np.asarray(points.valid).copy()
        if pre_pump_only and movie.pump_observations:
            selected &= np.asarray(points.time_s) < 0
        calibrated = np.isfinite(points.wavenumbers_cm1)
        if pre_pump_only and movie.pump_observations:
            calibrated &= np.asarray(points.time_s) < 0
        if np.any(calibrated):
            complete_support &= bool(np.all(np.asarray(points.valid)[calibrated]))
            complete_support &= not any((not pre_pump_only or not movie.pump_observations or gap[0] < 0) for gap in points.gaps_s)
        for nu, value, variance in zip(np.asarray(points.wavenumbers_cm1)[selected],
                                       np.asarray(points.normalized_signal)[selected],
                                       np.asarray(points.variance_normalized)[selected]):
            grouped[points.direction][float(nu)].append((float(value), float(variance)))
    spectra = []
    for direction, bins in grouped.items():
        axis = sorted(bins)
        values, variances = [], []
        for nu in axis:
            pairs = np.asarray(bins[nu])
            values.append(np.mean(pairs[:, 0]))
            variances.append(np.sum(pairs[:,1])/len(pairs)**2 if np.all(np.isfinite(pairs[:,1])) else np.nan)
        spectra.append(SpectrumSupport(direction, np.array(axis), np.array(values), np.array(variances), np.ones(len(axis), bool)))
    return SpectralBaseline(record_id or f"{movie.movie_id}-{kind or 'baseline'}", movie.mode, movie.condition_id,
                            tuple(spectra), kind or ("q0" if movie.mode == "dual" else "single_baseline"),
                            movie.status == "complete" and reconstructed.status != "rejected" and bool(spectra) and complete_support, accepted,
                            movie.metadata.get("compatibility", {}), {"source_movie_id": movie.movie_id,
                            "pre_pump_only": pre_pump_only, "analysis_version": ANALYSIS_VERSION,
                            "trajectory_calibration_ids_by_direction":{
                                direction:tuple(dict.fromkeys(s.trajectory.calibration_id for s in movie.scans if s.trajectory.direction==direction))
                                for direction in dict.fromkeys(s.trajectory.direction for s in movie.scans)}})


def _merge_spectra(spectra: Sequence[SpectrumSupport]) -> tuple[SpectrumSupport, ...]:
    """Average repeats at exact measured coordinates without direction pooling."""
    grouped: dict[str, dict[float, list[tuple[float,float]]]] = defaultdict(lambda: defaultdict(list))
    for spectrum in spectra:
        axis = np.asarray(spectrum.wavenumbers_cm1, float)
        values, variance = _array(spectrum.values, len(axis)), _array(spectrum.variance, len(axis))
        valid = np.ones(len(axis), bool) if spectrum.valid is None else np.asarray(spectrum.valid, bool)
        for nu,value,var in zip(axis[valid],values[valid],variance[valid]):
            if np.isfinite(nu) and np.isfinite(value) and value>0:
                grouped[spectrum.direction][float(nu)].append((float(value),float(var)))
    merged = []
    for direction, bins in grouped.items():
        axis = sorted(bins)
        values, variances = [], []
        for nu in axis:
            pairs = np.asarray(bins[nu])
            values.append(np.mean(pairs[:,0]))
            variances.append(np.sum(pairs[:,1])/len(pairs)**2 if np.all(np.isfinite(pairs[:,1])) else np.nan)
        merged.append(SpectrumSupport(direction,np.array(axis),np.array(values),np.array(variances),np.ones(len(axis),bool)))
    return tuple(merged)


def combine_baselines(baselines: Sequence[SpectralBaseline], *, record_id: str,
                       accepted: bool | None = None) -> SpectralBaseline:
    if not baselines:
        raise ValueError("At least one complete directional baseline is required")
    first = baselines[0]
    calibration_ids: dict[str, tuple[str, ...]] = {}
    identities = {name:getattr(first,name) for name in ("experiment_id","schema_version","mode","condition_id","kind")}
    for candidate in baselines[1:]:
        errors = compatibility_mismatches(identities,{name:getattr(candidate,name) for name in identities})
        errors += compatibility_mismatches(first.compatibility,candidate.compatibility)
        if errors:
            raise ValueError("Cannot combine incompatible baseline records: "+"; ".join(errors))
    for candidate in baselines:
        for direction, ids in candidate.metadata.get("trajectory_calibration_ids_by_direction",{}).items():
            if direction in calibration_ids and set(ids)!=set(calibration_ids[direction]):
                raise ValueError(f"Cannot combine changed {direction} trajectory calibrations without new review")
            calibration_ids[direction]=tuple(ids)
    return replace(first,record_id=record_id,spectra=_merge_spectra(tuple(s for b in baselines for s in b.spectra)),
                   complete=all(b.complete for b in baselines),
                   accepted=all(b.accepted for b in baselines) if accepted is None else accepted,
                   metadata={"source_record_ids":tuple(b.record_id for b in baselines),
                             "trajectory_calibration_ids_by_direction":calibration_ids,
                             "direction_pooling":"not_performed","analysis_version":ANALYSIS_VERSION})


def _state_observables(scans: Sequence[NativeScan], windows: Sequence[Sequence[float]], band_count: int) -> tuple[np.ndarray, list[str]]:
    result, reasons = [], []
    for scan in scans:
        _, q, _, valid, _, _ = _native_normalized(scan, "dual" if scan.reference is not None else "single", {}, 0.0)
        t = _time(scan.sample, {})
        nu, support = _spectral_coordinates(scan, t, {})
        valid &= support
        off_support = np.zeros(len(nu), bool)
        for lower, upper in windows[band_count:]:
            off_support |= (nu >= lower) & (nu <= upper) & valid
        local_log = np.full(len(nu), np.nan)
        if np.count_nonzero(off_support) >= 2:
            # Local log-ratio contrast after a measured off-band line removal.
            # This is a relative population proxy, never an assertion that raw
            # Q is absolute transmission or -log(Q) absolute absorbance.
            local_log[valid] = -np.log10(q[valid])
            line = np.polyfit(nu[off_support], local_log[off_support], 1)
            local_log -= np.polyval(line, nu)
        dt = np.diff(t)
        interval = scan.sample.metadata.get("expected_sample_interval_s")
        threshold = 1.5*float(interval) if interval is not None else (1.5*np.median(dt[dt>0]) if np.any(dt>0) else np.inf)
        if np.any((dt > threshold) | (dt <= 0)):
            reasons.append(f"scan {scan.scan_index}: native sampling has missing or nonmonotonic support")
        row = []
        for window_index, (lower, upper) in enumerate(windows):
            selected = (nu >= lower) & (nu <= upper)
            if np.count_nonzero(selected) < 2 or not np.all(valid[selected]):
                row.append(np.nan)
                reasons.append(f"scan {scan.scan_index}: missing or rejected support in {lower:g}–{upper:g} cm-1")
            else:
                order = np.argsort(nu[selected])
                if window_index < band_count:
                    row.append(float(np.trapezoid(local_log[selected][order], nu[selected][order])))
                else:
                    row.append(float(np.trapezoid(q[selected][order], nu[selected][order])/(upper-lower)))
        result.append(row)
    return np.asarray(result, dtype=float), reasons


def assess_stationarity(scans: Sequence[NativeScan], band_windows_cm1: Sequence[Sequence[float]],
                         offband_windows_cm1: Sequence[Sequence[float]], *, relative_tolerance: float = .02,
                         minimum_scans: int = 3, **_: Any) -> StateAssessment:
    reasons: list[str] = []
    windows = tuple(band_windows_cm1) + tuple(offband_windows_cm1)
    if not band_windows_cm1 or not offband_windows_cm1:
        reasons.append("Stationarity requires selected band and off-band windows")
    if len(scans) < minimum_scans:
        reasons.append(f"Stationarity requires {minimum_scans} complete pre-pump scans")
    directions = {scan.trajectory.direction for scan in scans}
    if len(directions) > 1:
        separate = {direction: assess_stationarity([scan for scan in scans if scan.trajectory.direction == direction],
                    band_windows_cm1, offband_windows_cm1, relative_tolerance=relative_tolerance,
                    minimum_scans=minimum_scans) for direction in directions}
        return StateAssessment(all(item.accepted for item in separate.values()),
                               tuple(f"{direction}: {reason}" for direction,item in separate.items() for reason in item.reasons),
                               {"by_direction": separate, "direction_pooling": "not_performed"})
    values, support_reasons = _state_observables(scans, windows, len(band_windows_cm1))
    reasons.extend(support_reasons)
    excursion = np.full(len(windows), np.nan)
    if values.size:
        denominator = np.maximum(np.abs(np.mean(values, axis=0)), 1e-15)
        excursion = np.ptp(values, axis=0)/denominator
        if not np.all(np.isfinite(excursion)) or np.any(excursion > relative_tolerance):
            reasons.append("Pre-pump band/off-band scan train exceeds stationarity tolerance")
    else:
        reasons.append("No measured pre-pump scan-train evidence")
    return StateAssessment(not reasons, tuple(dict.fromkeys(reasons)), {"observables": values,
                            "relative_excursion": excursion, "relative_tolerance": relative_tolerance,
                            "scan_count": len(scans), "windows_cm1": windows})


def assess_recovery(pre_scans: Sequence[NativeScan], post_scans: Sequence[NativeScan],
                    band_windows_cm1: Sequence[Sequence[float]], offband_windows_cm1: Sequence[Sequence[float]], *,
                    band_relative_tolerance: float = .02, offband_absolute_tolerance: float = .001,
                    consecutive_scans: int = 3, **_: Any) -> StateAssessment:
    reasons: list[str] = []
    if not band_windows_cm1 or not offband_windows_cm1:
        reasons.append("Reset requires both band-population and off-band evidence")
    if not pre_scans or len(post_scans) < consecutive_scans:
        reasons.append("Insufficient measured pre-pump or consecutive reset scans")
    windows = tuple(band_windows_cm1)+tuple(offband_windows_cm1)
    directions = {scan.trajectory.direction for scan in (*pre_scans, *post_scans)}
    if len(directions) > 1:
        separate = {direction: assess_recovery([scan for scan in pre_scans if scan.trajectory.direction == direction],
                    [scan for scan in post_scans if scan.trajectory.direction == direction], band_windows_cm1,
                    offband_windows_cm1, band_relative_tolerance=band_relative_tolerance,
                    offband_absolute_tolerance=offband_absolute_tolerance, consecutive_scans=consecutive_scans)
                    for direction in directions}
        return StateAssessment(all(item.accepted for item in separate.values()),
                               tuple(f"{direction}: {reason}" for direction,item in separate.items() for reason in item.reasons),
                               {"by_direction": separate, "direction_pooling": "not_performed",
                                "next_equivalent_pump_permitted": all(item.accepted for item in separate.values())})
    before, er1 = _state_observables(pre_scans, windows, len(band_windows_cm1))
    after, er2 = _state_observables(post_scans[-consecutive_scans:], windows, len(band_windows_cm1))
    reasons.extend(er1+er2)
    difference = np.full(after.shape, np.nan)
    if before.size and after.size:
        center = np.mean(before, axis=0)
        difference = after-center
        nb = len(band_windows_cm1)
        band_deviation = np.abs(difference[:, :nb])/np.maximum(np.abs(center[:nb]), 1e-15)
        if not np.all(np.isfinite(band_deviation)) or np.any(band_deviation > band_relative_tolerance):
            reasons.append("Bound-band populations have not returned to the accepted pre-pump state")
        offband_deviation = np.abs(difference[:, nb:])
        if not np.all(np.isfinite(offband_deviation)) or np.any(offband_deviation > offband_absolute_tolerance):
            reasons.append("Off-band baseline has not returned to the accepted pre-pump state")
    return StateAssessment(not reasons, tuple(dict.fromkeys(reasons)), {"pre_observables": before,
                            "final_observables": after, "difference": difference,
                            "consecutive_scans": consecutive_scans,
                            "outcome": "recovered" if not reasons else "duration_limited_incomplete_recovery",
                            "next_equivalent_pump_permitted": not reasons})


def fit_apparent_recovery(points: ReconstructedPoints | Sequence[ReconstructedPoints], kernel: NativeKernel, *,
                          spectral_shape: Callable[[np.ndarray], np.ndarray] | None = None,
                          tau_bounds_s: tuple[float, float] = (1e-6, 1e4),
                          grid_size: int = 500, cancelled: Callable[[], bool] | None = None) -> RecoveryFit:
    """Profile a single exponential directly at native (nu,t) with measured kernel.

    The spectral template is a prospectively chosen band/line-shape model. The
    constant default is appropriate only to a spectrally flat/selected local
    signal. Kernel quadrature can supply per-point trajectory offsets, accounting
    for filter memory while the laser is moving. No SciPy dependency is required.
    """
    groups = [points] if isinstance(points, ReconstructedPoints) else list(points)
    t = np.concatenate([np.asarray(p.time_s) for p in groups])
    nu = np.concatenate([np.asarray(p.wavenumbers_cm1) for p in groups])
    y = np.concatenate([np.asarray(p.delta_absorbance) for p in groups])
    variance = np.concatenate([np.asarray(p.variance_delta_absorbance) for p in groups])
    valid = np.concatenate([np.asarray(p.valid) for p in groups]) & np.isfinite(t) & np.isfinite(nu) & np.isfinite(y)
    delays, weights = np.asarray(kernel.delays_s, float), np.asarray(kernel.weights, float)
    if not kernel.calibration_id or delays.ndim != 1 or delays.shape != weights.shape or not len(delays):
        raise ValueError("A measured, identified native acquisition kernel is required")
    if np.any(~np.isfinite(delays)) or np.any(~np.isfinite(weights)) or np.any(weights < 0) or weights.sum() <= 0:
        raise ValueError("Kernel quadrature must be finite with nonnegative nonzero weights")
    weights = weights/weights.sum()
    offsets = np.zeros((len(t), len(delays)))
    if kernel.wavelength_offsets_cm1 is not None:
        supplied = np.asarray(kernel.wavelength_offsets_cm1, float)
        offsets = np.broadcast_to(supplied, (len(valid), len(delays)))
    shape = spectral_shape or (lambda axis: np.ones_like(axis))
    spectral = np.asarray(shape(nu[:, None] + offsets), dtype=float)
    spectral = np.broadcast_to(spectral, offsets.shape).copy()
    active = weights > 0
    kernel_support = np.all(np.isfinite(offsets[:, active]) & np.isfinite(spectral[:, active]), axis=1)
    unsupported_count = int(np.count_nonzero(valid & ~kernel_support))
    valid &= kernel_support
    indices = np.flatnonzero(valid)
    if len(indices) < 5:
        raise ValueError("At least five valid native observations with measured kernel/template support are required")
    t, nu, y, variance, spectral = t[valid], nu[valid], y[valid], variance[valid], spectral[valid]
    spectral[:, ~active] = 0
    elapsed = t[:, None]-delays[None, :]
    precision = np.ones(len(y))
    weighted = np.isfinite(variance) & (variance > 0)
    if np.all(weighted):
        precision = 1/variance
    root_precision = np.sqrt(precision)
    if not 0 < tau_bounds_s[0] < tau_bounds_s[1] or grid_size < 10:
        raise ValueError("Positive ordered tau bounds and at least ten profile points are required")
    taus = np.geomspace(*tau_bounds_s, grid_size)
    costs = []
    best_cost = np.inf
    best_coeff, best_design = None, None
    for tau in taus:
        _check_cancel(cancelled)
        kinetic = np.sum(spectral * np.where(elapsed >= 0, np.exp(-np.maximum(elapsed, 0)/tau), 0) * weights, axis=1)
        design = np.column_stack((kinetic, np.ones(len(y))))
        coeff = np.linalg.lstsq(design*root_precision[:, None], y*root_precision, rcond=None)[0]
        residual = y-design@coeff
        cost = float(np.dot(residual*precision, residual))
        costs.append(cost)
        if cost < best_cost:
            best_cost, best_coeff, best_design = cost, coeff, design
    best = int(np.argmin(costs))
    tau, coeff, design = float(taus[best]), best_coeff, best_design
    predicted = design@coeff
    residuals = y-predicted
    noise_scale = 1.0 if np.all(weighted) else max(float(costs[best])/max(1, len(y)-3), np.finfo(float).eps)
    profile = np.asarray(costs)
    supported = np.flatnonzero(profile <= costs[best]+3.841459*noise_scale)
    # A discrete grid must not produce a spuriously zero-width confidence
    # interval. Bracket the crossing with the neighboring evaluated candidates;
    # the resulting interval explicitly includes finite profiling resolution.
    interval = (float(taus[max(0,int(supported[0])-1)]),
                float(taus[min(len(taus)-1,int(supported[-1])+1)]))
    derivative = np.sum(spectral*np.where(elapsed>=0, np.exp(-np.maximum(elapsed,0)/tau)*np.maximum(elapsed,0)/tau**2, 0)*weights, axis=1)*coeff[0]
    jacobian = np.column_stack((design[:,0], design[:,1], derivative))
    covariance = np.linalg.pinv(jacobian.T@(precision[:,None]*jacobian))*noise_scale
    identifiable = best not in (0,len(taus)-1) and interval[0] > taus[0] and interval[1] < taus[-1] and np.linalg.matrix_rank(jacobian) == 3
    warnings = [] if identifiable else ["Lifetime is not identifiable within the selected bounds and native support"]
    if not np.all(weighted):
        warnings.append("Detector uncertainty incomplete; residual-based homoscedastic uncertainty used")
    if spectral_shape is None:
        warnings.append("Constant spectral template used; restrict interpretation to a justified flat/local signal")
    warnings.append("Profile interval is conditional on the supplied spectral model, time zero and acquisition kernel")
    warnings.append("Profile confidence bounds conservatively include the neighboring lifetime grid points")
    warnings.append("Kernel model is linear in delta absorbance; validate the small-signal approximation against measured intensity/filter transfer")
    if unsupported_count:
        warnings.append(f"{unsupported_count} native points excluded from fitting because filter history/template support is unobserved")
    return RecoveryFit(tau,float(coeff[0]),float(coeff[1]),covariance,residuals,predicted,interval,
                       identifiable,kernel.calibration_id,indices,tuple(warnings))


def native_kernel_for_movie(movie: NativeMovie, calibration: Mapping[str, Any], *,
                             cancelled: Callable[[], bool] | None = None) -> NativeKernel:
    """Evaluate measured response quadrature along the actual observed trajectory.

    Analysis-only model files require an identified measured response, its time
    basis and a justified spectral model; loading one never promotes calibration
    or authorizes acquisition. Missing filter history remains NaN/excluded.
    """
    required = ("calibration_id", "delays_s", "weights", "response_basis")
    if not all(key in calibration for key in required) or calibration.get("measured") is not True:
        raise ValueError("Fit kernel requires measured=true, calibration_id, delays_s, weights and response_basis")
    if not str(calibration["calibration_id"]).strip():
        raise ValueError("Measured kernel calibration_id must be explicit")
    basis = calibration["response_basis"]
    if basis not in ("electrical_sync", "optical_arrival", "calibrated_optical_time_zero"):
        raise ValueError("Kernel response_basis must be electrical_sync, optical_arrival or calibrated_optical_time_zero")
    if len(movie.pump_observations) != 1 or not movie.pump_observations[0].independently_observed:
        raise ValueError("Native recovery fitting requires one independently observed pump")
    if movie.pump_observations[0].basis != basis:
        raise ValueError("Measured kernel time basis differs from the movie pump observation basis")
    delays, weights = np.asarray(calibration["delays_s"],float), np.asarray(calibration["weights"],float)
    if delays.ndim != 1 or delays.shape != weights.shape or not len(delays) or np.any(~np.isfinite(delays)):
        raise ValueError("Measured kernel delay/weight quadrature has invalid shape or values")
    if np.any(~np.isfinite(weights)) or np.any(weights<0) or weights.sum()<=0:
        raise ValueError("Measured kernel weights must be nonnegative and have positive sum")
    clock_anchor = movie.clock_corrections[0].offset_s if movie.clock_corrections else 0.
    clocks = {c.clock_id:replace(c,offset_s=c.offset_s-clock_anchor) for c in movie.clock_corrections}
    histories = []
    for scan in movie.scans:
        marker_t, marker_nu = _time(scan.trajectory, clocks),np.asarray(scan.trajectory.wavenumbers_cm1,float)
        if scan.trajectory.calibration_id and len(marker_t)>1 and np.all(np.isfinite(marker_t)) and np.all(np.diff(marker_t)>0):
            histories.append((scan.trajectory,marker_t,marker_nu))
    offsets = []
    for scan in movie.scans:
        _check_cancel(cancelled)
        times = _time(scan.sample,clocks)
        nu,_ = _spectral_coordinates(scan,times,clocks)
        source_t = times[:,None]-delays[None,:]
        source_nu = np.full(source_t.shape,np.nan)
        for trajectory,marker_t,marker_nu in histories:
            supported = (source_t>=marker_t[0]) & (source_t<=marker_t[-1])
            max_gap = trajectory.metadata.get("max_marker_gap_s")
            if max_gap is not None:
                where = np.clip(np.searchsorted(marker_t,source_t),1,len(marker_t)-1)
                supported &= (marker_t[where]-marker_t[where-1]<=float(max_gap)) | np.isin(source_t,marker_t)
            source_nu[supported] = np.interp(source_t[supported],marker_t,marker_nu)
        offsets.append(source_nu-nu[:,None])
    return NativeKernel(delays,weights,str(calibration["calibration_id"]),
                        np.concatenate(offsets,axis=0) if offsets else np.empty((0,len(delays))),
                        {"response_basis":basis,"source_calibration":dict(calibration),
                         "trajectory_calibration_ids":tuple(dict.fromkeys(s.trajectory.calibration_id for s in movie.scans)),
                         "unobserved_history":"excluded_without_extrapolation"})


def fit_recovery_model(native_movie: NativeMovie, reconstructed_movie: ReconstructedMovie,
                        analysis_inputs: Mapping[str, Any],
                        cancelled: Callable[[], bool] | None = None) -> dict[str, Any]:
    """Apply an explicit measured-kernel/spectral-template model by direction."""
    if native_movie.movie_id != reconstructed_movie.movie_id or native_movie.mode != reconstructed_movie.mode:
        raise ValueError("Fit native and reconstructed movie identity mismatch")
    if reconstructed_movie.status == "rejected":
        raise ValueError("Rejected timing/clock reconstruction cannot support a recovery fit")
    for key in ("kernel","spectral_template","tau_bounds_s"):
        if key not in analysis_inputs:
            raise ValueError(f"Analysis model requires explicit {key}")
    template = analysis_inputs["spectral_template"]
    for key in ("wavenumbers_cm1","values","record_id","description"):
        if key not in template or (key in ("record_id","description") and not str(template[key]).strip()):
            raise ValueError(f"Spectral template requires {key}")
    axis, values = np.asarray(template["wavenumbers_cm1"],float),np.asarray(template["values"],float)
    if axis.ndim != 1 or values.shape != axis.shape or len(axis)<2 or np.any(np.diff(axis)<=0) or not np.all(np.isfinite(axis)) or not np.all(np.isfinite(values)):
        raise ValueError("Spectral template must have finite values on a strictly increasing measured wavenumber axis")
    if not np.any(values):
        raise ValueError("A zero spectral template cannot identify recovery amplitude")
    def spectral_shape(nu):
        result = np.interp(nu,axis,values,left=np.nan,right=np.nan)
        for lower,upper in template.get("excluded_intervals_cm1",()):
            result[(nu>=lower)&(nu<=upper)] = np.nan
        return result
    kernel = native_kernel_for_movie(native_movie,analysis_inputs["kernel"],cancelled=cancelled)
    if len(reconstructed_movie.points)!=len(native_movie.scans) or any(p.scan_index!=s.scan_index for p,s in zip(reconstructed_movie.points,native_movie.scans)):
        raise ValueError("Native fit requires original scan ordering and exact reconstructed point correspondence")
    directions = tuple(dict.fromkeys(p.direction for p in reconstructed_movie.points))
    fits = {}
    for direction in directions:
        _check_cancel(cancelled)
        row_mask = np.concatenate([np.full(len(p.time_s),p.direction==direction) for p in reconstructed_movie.points])
        directional_kernel = replace(kernel,wavelength_offsets_cm1=np.asarray(kernel.wavelength_offsets_cm1)[row_mask])
        points = tuple(p for p in reconstructed_movie.points if p.direction==direction)
        fits[direction] = fit_apparent_recovery(points,directional_kernel,spectral_shape=spectral_shape,
                        tau_bounds_s=tuple(map(float,analysis_inputs["tau_bounds_s"])),
                        grid_size=int(analysis_inputs.get("grid_size",500)),cancelled=cancelled)
    return {"movie_id":native_movie.movie_id,"fits_by_direction":fits,"analysis_inputs":dict(analysis_inputs),
            "provenance":{"analysis_version":ANALYSIS_VERSION,"template_record_id":template["record_id"],
                          "kernel_calibration_id":kernel.calibration_id,"time_zero_basis":reconstructed_movie.time_zero_basis,
                          "direction_pooling":"not_performed","support":"native_observations_with_measured_filter_history",
                          "covariance_parameter_order":("amplitude","offset","apparent_tau_s"),
                          "response_model":"Linearized delta absorbance kernel; small-signal approximation must be validated",
                          "claim":"Apparent recovery; concentration, mass balance and artifact evidence are required for mechanistic claims"}}
