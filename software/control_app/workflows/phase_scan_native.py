"""Convert native HF2LI streams using observed, identified wavelength markers.

The hardware adapter must identify each marker's wavelength and observe the
pump event. This module never substitutes SDK command time for device time.
"""
from __future__ import annotations

import numpy as np

from control_app.workflows.phase_scan_data import Spectrum, interpolate_supported


def demodulator_samples(record: dict, index: int) -> dict:
    streams = [payload for chunk in record["native_chunks"] for path, payload in chunk["data"].items()
               if path.lower().endswith(f"/demods/{index}/sample")]
    if not streams:
        raise ValueError(f"No native data for demodulator {index}")
    fields = ("timestamp", "x", "y", "dio", "auxin0", "auxin1")
    arrays = {name: np.concatenate([s[name] for s in streams]) for name in fields}
    t = arrays["timestamp"]
    if len(t) < 2 or np.any(t[1:] <= t[:-1]):
        raise ValueError("Native timestamps must increase without duplicates")
    if any(v.ndim != 1 or len(v) != len(t) for v in arrays.values()):
        raise ValueError("Native stream fields have inconsistent dimensions")
    return arrays


def high_intervals(ticks, high):
    """Complete low/high/low intervals only; never invent a missing edge."""
    high = np.asarray(high, dtype=bool)
    starts = np.flatnonzero(~high[:-1] & high[1:]) + 1
    stops = np.flatnonzero(high[:-1] & ~high[1:]) + 1
    return [(int(ticks[start]), int(ticks[stops[stops > start][0]]))
            for start in starts if np.any(stops > start)]


def sweep_interval_observations(ticks, dio):
    """Return DIO21 intervals and those independently identified by markers.

    The installed timing stream can also expose a complete 10 ms process-event
    interval on DIO21 during pumped records.  A real wavelength sweep is the
    unique DIO21 interval containing at least two DIO22 wavelength-marker
    rising edges.  The ancillary interval is retained, never deleted or used
    as the wavelength/time basis.
    """
    ticks = np.asarray(ticks)
    dio = np.asarray(dio, dtype=np.uint32)
    intervals = high_intervals(ticks, (dio & (1 << 21)) != 0)
    marker_high = (dio & (1 << 22)) != 0
    marker_rises = ticks[np.flatnonzero(~marker_high[:-1] & marker_high[1:]) + 1]
    marker_bearing = [
        interval for interval in intervals
        if np.count_nonzero((marker_rises >= interval[0]) & (marker_rises <= interval[1])) >= 2
    ]
    return intervals, marker_bearing, marker_rises


def select_sweep_active_interval(ticks, dio):
    """Select one marker-identified sweep, preserving ancillary DIO21 highs."""
    intervals, marker_bearing, marker_rises = sweep_interval_observations(ticks, dio)
    if len(marker_bearing) == 1:
        selected = marker_bearing[0]
    elif not marker_bearing and len(intervals) == 1:
        # Preserve the established provisional-axis path when wavelength
        # markers are missing but exactly one complete Sweep Active exists.
        selected = intervals[0]
    else:
        raise ValueError(
            "Expected one identifiable complete Sweep Active interval for this QCL; "
            f"observed {len(intervals)} DIO21 intervals and {len(marker_bearing)} marker-bearing intervals"
        )
    ancillary = [interval for interval in intervals if interval != selected]
    markers = marker_rises[(marker_rises >= selected[0]) & (marker_rises <= selected[1])]
    return selected, markers, intervals, ancillary


def pump_reference_tick(record, reference, threshold_v):
    timing = demodulator_samples(record, 2)
    if reference == "electrical_sync":
        high = (timing["dio"].astype(np.uint32) & (1 << 17)) != 0
    else:
        signal = np.asarray(timing[reference], dtype=float)
        if not np.isfinite(signal).all() or np.any(np.abs(signal) >= 10):
            raise ValueError("Selected pump Aux input is invalid or outside ±10 V")
        high = signal >= threshold_v
    edges = np.flatnonzero(~high[:-1] & high[1:]) + 1
    if len(edges) != 1:
        label = "Nd:YAG Variable Sync on DIO17" if reference == "electrical_sync" else reference
        raise ValueError(f"Expected one pump-reference rising edge on {label}; observed {len(edges)}. Native data retained.")
    return int(timing["timestamp"][edges[0]])


def spectrum_from_sweep(record, *, start_cm1, stop_cm1, targets_cm1, origin_tick,
                        pump_tick=None, pump_reference="electrical_sync"):
    """Use identified markers, or label an observed-sweep-bound preview explicitly.

    Unresolved marker counts must never be renumbered. Such records retain all
    raw data and use a provisional axis between observed sweep-active edges.
    This preview is useful for initial air/polymer tests, not calibration.
    """
    if not record.get("optical_valid"):
        raise ValueError("An inhibited record cannot become an optical spectrum")
    timing = demodulator_samples(record, 2)
    ticks, dio = timing["timestamp"], timing["dio"].astype(np.uint32)
    (start, stop), markers, intervals, ancillary = select_sweep_active_interval(ticks, dio)
    targets = np.asarray(targets_cm1, dtype=float)
    identified = len(markers) == len(targets) and len(markers) >= 2
    warnings = ["Optical timing, filter response, and wavelength accuracy have not been qualified."]
    if ancillary:
        warnings.append(
            f"Ignored {len(ancillary)} complete ancillary DIO21 interval(s) without wavelength markers; "
            "all intervals remain preserved in native data."
        )
    if identified:
        map_ticks, map_wn = markers, targets
    else:
        map_ticks = np.array([start, stop], dtype=np.uint64)
        map_wn = np.array([start_cm1, stop_cm1])
        warnings.append(f"PROVISIONAL wavenumber axis: {len(markers)} markers observed, {len(targets)} expected; linear between Sweep Active edges.")
    clockbase = float(record["clockbase_hz"])
    if not np.isfinite(clockbase) or clockbase <= 0:
        raise ValueError("Invalid HF2LI clockbase")
    def seconds(values):
        return np.asarray([(int(t)-int(origin_tick))/clockbase for t in values])
    sample, reference = demodulator_samples(record, 0), demodulator_samples(record, 3)
    sample_t, ref_t = seconds(sample["timestamp"]), seconds(reference["timestamp"])
    selected = (sample["timestamp"] >= map_ticks[0]) & (sample["timestamp"] <= map_ticks[-1])
    if np.count_nonzero(selected) < 2:
        raise ValueError("Fewer than two detector samples within the sweep; reduce scan speed or increase detector readout rate")
    aligned = interpolate_supported(ref_t, np.hypot(reference["x"], reference["y"]), sample_t[selected],
                                    max_gap=float(np.median(np.diff(ref_t)))*1.75)
    tick_spacing = float(np.median(np.diff(ticks).astype(float))) / clockbase
    metadata = {"optical_valid": True, "wavenumber_basis": "measured" if identified else "nominal_sweep_bounds",
                "provisional": not identified, "trajectory_method": "identified_markers" if identified else "observed_sweep_bounds_preview",
                "pump_time_basis": ("unpumped" if pump_tick is None else "electrical_sync" if pump_reference == "electrical_sync" else "aux_input"),
                "pump_reference": pump_reference, "timestamp_origin_ticks": int(origin_tick), "clockbase_hz": clockbase,
                "timing_sample_interval_s": tick_spacing, "marker_ticks": markers.tolist(),
                "expected_marker_wavenumbers_cm1": targets.tolist(), "sweep_active_ticks": [start, stop],
                "observed_dio21_intervals": [list(value) for value in intervals],
                "ancillary_dio21_intervals_ignored": [list(value) for value in ancillary],
                "warnings": warnings}
    if pump_tick is not None and pump_reference == "electrical_sync":
        warnings.append("Time zero is observed Nd:YAG electrical sync, not measured optical arrival at the sample.")
    return Spectrum(interpolate_supported(seconds(map_ticks), map_wn, sample_t[selected]),
                    np.hypot(sample["x"], sample["y"])[selected], aligned, sample_t[selected],
                    None if pump_tick is None else (int(pump_tick)-int(origin_tick))/clockbase, metadata).validate()


def marker_spectrum(record: dict, *, marker_ticks, marker_wavenumbers_cm1,
                    pump_tick: int | None, sample_demod=0, reference_demod=3) -> Spectrum:
    """Align detectors in device time, then map samples between measured markers.

    Input marker ticks must be validated observations, in chronological order,
    from a single sweep segment. Absolute marker wavelengths must be identified
    by the adapter; missed or unidentified markers must not be renumbered.
    """
    if not record.get("optical_valid"):
        raise ValueError("An inhibited/dark record cannot become an optical spectrum")
    sample, reference = demodulator_samples(record, sample_demod), demodulator_samples(record, reference_demod)
    ticks, wn = np.asarray(marker_ticks), np.asarray(marker_wavenumbers_cm1, dtype=float)
    if ticks.ndim != 1 or wn.ndim != 1 or len(ticks) != len(wn) or len(ticks) < 2:
        raise ValueError("At least two identified, observed wavelength markers are required")
    if not np.issubdtype(ticks.dtype, np.integer) or np.any(ticks[1:] <= ticks[:-1]):
        raise ValueError("Marker ticks must be strictly increasing native integers")
    if not np.isfinite(wn).all() or not (np.all(np.diff(wn) > 0) or np.all(np.diff(wn) < 0)):
        raise ValueError("Markers must identify one monotonic wavelength segment")
    clockbase = float(record["clockbase_hz"])
    if not np.isfinite(clockbase) or clockbase <= 0:
        raise ValueError("A positive measured clockbase is required")
    origin = min(int(sample["timestamp"][0]), int(reference["timestamp"][0]), int(ticks[0]),
                 int(pump_tick) if pump_tick is not None else int(ticks[0]))

    def seconds(values):
        # Subtract as integers before conversion: retain precision above 2**53
        # and avoid unsigned wraparound for pre-pump samples.
        return np.asarray([(int(t)-origin)/clockbase for t in values])

    sample_t, reference_t, marker_t = seconds(sample["timestamp"]), seconds(reference["timestamp"]), seconds(ticks)
    selected = (sample_t >= marker_t[0]) & (sample_t <= marker_t[-1])
    reference_r = np.hypot(reference["x"], reference["y"])
    aligned_ref = interpolate_supported(reference_t, reference_r, sample_t[selected],
                                        max_gap=float(np.median(np.diff(reference_t))) * 1.5)
    result = Spectrum(
        interpolate_supported(marker_t, wn, sample_t[selected]),
        np.hypot(sample["x"], sample["y"])[selected], aligned_ref, sample_t[selected],
        (int(pump_tick)-origin)/clockbase if pump_tick is not None else None,
        {"optical_valid": True, "wavenumber_basis": "measured", "trajectory_method": "identified_markers",
         "pump_time_basis": "measured" if pump_tick is not None else "unpumped",
         "timestamp_origin_ticks": origin, "clockbase_hz": clockbase,
         "marker_ticks": ticks.tolist(), "marker_wavenumbers_cm1": wn.tolist(),
         "sample_demodulator": sample_demod, "reference_demodulator": reference_demod},
    )
    return result.validate()
