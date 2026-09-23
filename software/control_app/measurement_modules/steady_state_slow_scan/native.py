"""Native HF2LI stream retention and conservative controller-marker assignment.

No regular grid is manufactured. The marker-to-time segments are recorded as
an engineering reconstruction, never as an independently calibrated axis.
"""
from __future__ import annotations

from control_app.paths import research_output_path

import json
from pathlib import Path
from collections.abc import Mapping
import numpy as np


def retain_chunk(directory, index, record):
    """Write every returned SDK value before interpretation, including failures."""
    directory = research_output_path(directory)
    research_output_path(directory).mkdir(parents=True, exist_ok=True)
    arrays = {}
    def pack(value):
        if isinstance(value, np.ndarray):
            key = f"array_{len(arrays)}"
            arrays[key] = value
            return {"native_array": key, "dtype": value.dtype.str, "shape": list(value.shape)}
        if isinstance(value, Mapping):
            return {str(k): pack(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [pack(v) for v in value]
        if isinstance(value, np.generic):
            # Preserve scalar dtype too, rather than float-casting uint64 ticks.
            return pack(np.asarray(value))
        return value
    payload = pack(record)
    stem = f"chunk_{index:06d}"
    with (research_output_path(directory / f"{stem}.npz")).open("xb") as stream:
        np.savez(stream, **arrays)
    with (research_output_path(directory / f"{stem}.json")).open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2)
    return str(directory / f"{stem}.json")


def combine_poll_streams(records, demodulator):
    """Concatenate in returned order; retain duplicate/missing ticks explicitly."""
    parts = {}
    for record in records:
        for path, sample in record.get("data", {}).items():
            if f"/demods/{demodulator}/sample" != path.lower()[path.lower().find('/demods/'):]:
                continue
            if not isinstance(sample, Mapping):
                raise ValueError("Expected native HF2LI poll sample mapping")
            for key, value in sample.items():
                array = np.asarray(value)
                if array.ndim == 1:
                    parts.setdefault(key, []).append(array)
    return {key: np.concatenate(values) for key, values in parts.items()}


def seconds_from_ticks(ticks, origin, clockbase_hz):
    """Subtract integer epochs before float conversion (uint64 precision)."""
    ticks = np.asarray(ticks)
    if not np.issubdtype(ticks.dtype, np.integer):
        raise ValueError("Native HF2LI timestamps must be integer clock ticks")
    return np.asarray([int(tick)-int(origin) for tick in ticks], dtype=np.float64) / clockbase_hz


def observed_sweeps(records, *, sample_demodulator, reference_demodulator,
                    timing_demodulator, clockbase_hz, marker_targets_cm1,
                    expected_sweeps, sample_rate_sps, reference_rate_sps=None,
                    sample_group_delay_s=0., reference_group_delay_s=0.,
                    marker_gap_limit_s=None):
    """Return native slices aligned by time, plus quality flags and native streams.

    Missing marker counts invalidate that sweep's axis rather than assigning
    later markers to invented positions. Sample/reference alignment is nearest
    observed timestamp within half the slower stream interval; no gap filling.
    """
    streams = {"sample": combine_poll_streams(records, sample_demodulator),
               "timing": combine_poll_streams(records, timing_demodulator)}
    if reference_demodulator is not None:
        streams["reference"] = combine_poll_streams(records, reference_demodulator)
    if any("timestamp" not in value for value in streams.values()):
        raise ValueError("Missing HF2LI sample/reference/timing stream")
    origin = min(int(value["timestamp"][0]) for value in streams.values() if len(value["timestamp"]))
    timing = streams["timing"]
    tt = seconds_from_ticks(timing["timestamp"], origin, clockbase_hz)
    dio = np.asarray(timing["dio"], dtype=np.uint64)
    if len(tt) != len(dio) or len(tt) < 2 or np.any(np.diff(tt) <= 0):
        raise ValueError("Invalid or repeated native timing timestamps")
    active = (dio & (1 << 21)) != 0
    starts = np.flatnonzero(np.diff(active.astype(int)) == 1)+1
    stops = np.flatnonzero(np.diff(active.astype(int)) == -1)+1
    marker = (dio & (1 << 22)) != 0
    edges = np.flatnonzero(np.diff(marker.astype(int)) == 1)+1
    flags = []
    # Surelite sync may idle HIGH. Preserve setup-time excursions separately:
    # only an edge overlapping Sweep Active contaminates a slow-scan spectrum.
    # The full timing stream remains retained for diagnosis.
    pump_sync = ((dio >> 17) & 1).astype(int)
    pump_edges = np.flatnonzero(np.diff(pump_sync) != 0) + 1
    pump_edges_in_sweep = pump_edges[active[pump_edges] | active[pump_edges-1]]
    if len(pump_edges_in_sweep):
        flags.append("unexpected_electrical_pump_sync")
    if len(pump_edges) > len(pump_edges_in_sweep):
        flags.append("electrical_pump_sync_outside_sweep")
    if len(starts) != expected_sweeps or len(stops) != expected_sweeps:
        flags.append("sweep_trigger_count_mismatch")
    st = seconds_from_ticks(streams["sample"]["timestamp"], origin, clockbase_hz)-sample_group_delay_s
    sample = np.hypot(streams["sample"]["x"], streams["sample"]["y"])
    if len(st) != len(sample) or np.any(np.diff(st) <= 0):
        raise ValueError("Invalid or repeated sample timestamps")
    rt = reference = None
    if reference_demodulator is not None:
        rt = seconds_from_ticks(streams["reference"]["timestamp"], origin, clockbase_hz)-reference_group_delay_s
        reference = np.hypot(streams["reference"]["x"], streams["reference"]["y"])
        if len(rt) != len(reference) or np.any(np.diff(rt) <= 0):
            raise ValueError("Invalid or repeated reference timestamps")
    result = []
    targets = np.asarray(marker_targets_cm1, dtype=float)
    for start in starts:
        end_candidates = stops[stops > start]
        if not len(end_candidates):
            continue  # Partial native stream still retained by the journal.
        stop = end_candidates[0]
        indices = np.flatnonzero((st >= tt[start]) & (st < tt[stop]))
        times = st[indices]
        axis = np.full(len(indices), np.nan)
        marks = edges[(edges >= start) & (edges < stop)]
        local = list(flags)
        if len(marks) != len(targets) or len(marks) < 2:
            local.append("wavelength_marker_count_mismatch")
        else:
            for i in range(len(marks)-1):
                a, b = tt[marks[i]], tt[marks[i+1]]
                if marker_gap_limit_s is not None and b-a > marker_gap_limit_s:
                    local.append("missing_marker_interval")
                    continue
                chosen = (times >= a) & (times <= b)
                axis[chosen] = targets[i] + (times[chosen]-a)/(b-a)*(targets[i+1]-targets[i])
        valid = np.isfinite(axis) & np.isfinite(sample[indices])
        aligned = None
        alignment = {}
        if rt is not None:
            right = np.searchsorted(rt, times).clip(0, len(rt)-1)
            left = np.maximum(right-1, 0)
            match = np.where(abs(rt[left]-times) <= abs(rt[right]-times), left, right)
            tolerance = .51/min(sample_rate_sps, reference_rate_sps)
            support = abs(rt[match]-times) <= tolerance
            aligned = np.where(support, reference[match], np.nan)
            valid &= support & np.isfinite(aligned) & (aligned > 0)
            if not np.all(support):
                local.append("missing_reference_support")
            if np.any(support & (~np.isfinite(aligned) | (aligned <= 0))):
                local.append("invalid_reference_signal")
            reused = len(np.unique(match[support])) < int(np.count_nonzero(support))
            alignment = {"reference_native_indices": np.where(support, match, -1),
                         "reference_time_mismatch_s": rt[match]-times,
                         "reference_alignment_tolerance_s": tolerance,
                         "reference_alignment_policy": "nearest observed sample; no interpolation",
                         "reference_samples_reused": reused}
            if reused:
                local.append("shared_reference_temporal_covariance_unresolved")
        gaps = np.flatnonzero(np.diff(times) > 1.8/sample_rate_sps)
        if len(gaps):
            local.append("native_sample_gap")
            # Explicit NaN breaks adjacent to lost intervals prevent plotting or
            # fitting across them; original values remain in sample and streams.
            valid[gaps+1] = False
        direction_words = np.unique(((dio[start:stop] >> 20) & 1))
        if len(direction_words) != 1:
            local.append("direction_changed_inside_sweep")
        result.append({"axis_cm1": axis, "sample": sample[indices], "reference": aligned,
                       "timestamps_s": times, "valid": valid, "flags": tuple(dict.fromkeys(local)),
                       "direction_bit": int(direction_words[0]), "native_indices": indices,
                       "marker_ticks": timing["timestamp"][marks], "time_origin_ticks": origin, **alignment})
    return result, streams, tuple(dict.fromkeys(flags))
