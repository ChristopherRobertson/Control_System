"""Convert bracketed HF2LI demodulator samples into KaleidaGraph scan CSV."""

from __future__ import annotations

import csv
from bisect import bisect_left
import math
from pathlib import Path
from typing import Iterable

from control_app.devices.hf2li_service import _normalized_sample_rows, _normalized_sample_rows_from_sample


def export_kaleidagraph_scan(
    rows: Iterable[tuple[float, float, float]], *, output_path: str | Path
) -> Path:
    """Write validated ``wavenumber, sample, reference`` data for a sweep plot."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Wavenumber (cm^-1)", "Sample (V)", "Reference (V)"])
        for wavenumber, sample, reference in rows:
            writer.writerow([f"{wavenumber:.9g}", f"{sample:.9g}", f"{reference:.9g}"])
    return path


def export_kaleidagraph_from_hf2li_raw(
    raw_csv_path: str | Path,
    *,
    output_path: str | Path,
    start_cm1: float,
    stop_cm1: float,
    sample_demodulator: int = 0,
    reference_demodulator: int = 3,
) -> Path:
    """Pair HF2LI R samples and assign a linear wavenumber axis.

    The caller supplies data already bounded by the MIRcat ``Tuned`` DAQ trigger.
    """
    grouped: dict[int, list[float]] = {sample_demodulator: [], reference_demodulator: []}
    with Path(raw_csv_path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            path = row.get("path", "")
            for demodulator in grouped:
                if f"/demods/{demodulator}/sample.r" in path:
                    grouped[demodulator].append(float(row["value"]))
    count = min(len(grouped[sample_demodulator]), len(grouped[reference_demodulator]))
    if count < 2:
        raise ValueError("HF2LI raw record contains fewer than two paired Sample/Reference R points")
    rows = (
        (
            start_cm1 + (stop_cm1 - start_cm1) * index / (count - 1),
            grouped[sample_demodulator][index],
            grouped[reference_demodulator][index],
        )
        for index in range(count)
    )
    return export_kaleidagraph_scan(rows, output_path=output_path)


def kaleidagraph_rows_from_hf2li_record(
    record: dict,
    *,
    start_cm1: float,
    stop_cm1: float,
    sample_demodulator: int = 0,
    reference_demodulator: int = 3,
    timing_demodulator: int = 2,
    end_bit: int = 21,
    nominal_duration_ticks: float | None = None,
    nominal_start_offset_ticks: float = 0.0,
    initial_settling_ticks: float = 0.0,
    use_dio_end_marker: bool = True,
    retain_full_record: bool = False,
) -> tuple[list[tuple[float, float, float]], dict[str, int | float]]:
    """Crop a triggered sweep at the MIRcat ``Tuned`` end transition.

    The DAQ starts from MIRcat TRIG OUT. ``sample.dio`` on the spare timing
    demodulator contains the global DIO word at every timing sample; DIO21's
    first low-to-high transition is the physical sweep-end marker.
    """
    samples = _sample_field_series(record, demodulator=sample_demodulator, field="r")
    references = _sample_field_series(record, demodulator=reference_demodulator, field="r")
    dio_samples = _sample_field_series(record, demodulator=timing_demodulator, field="dio")
    if len(samples) < 2 or len(references) < 2:
        raise ValueError("HF2LI record contains fewer than two Sample/Reference R points")
    if retain_full_record:
        start_timestamp = max(samples[0][0], references[0][0])
        end_timestamp = min(samples[-1][0], references[-1][0])
        kept_samples = [
            (timestamp, value)
            for timestamp, value in samples
            if start_timestamp <= timestamp <= end_timestamp
        ]
        if len(kept_samples) < 2 or end_timestamp <= start_timestamp:
            raise ValueError("HF2LI full streaming record contains fewer than two paired detector points")
        ref_timestamps = [timestamp for timestamp, _ in references]
        span = end_timestamp - start_timestamp
        rows = [
            (
                start_cm1 + (stop_cm1 - start_cm1) * (timestamp - start_timestamp) / span,
                sample,
                _interpolate(references, ref_timestamps, timestamp),
            )
            for timestamp, sample in kept_samples
        ]
        return rows, {
            "start_timestamp": start_timestamp,
            "retained_start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "start_method": "full_streaming_record",
            "end_method": "full_streaming_record",
            "retained_sample_count": len(rows),
        }
    if use_dio_end_marker and len(dio_samples) < 2:
        raise ValueError(
            "HF2LI record contains no usable DIO timing stream. "
            "Verify LabOne Demodulator 3 (API index 2) is enabled and subscribed."
        )

    end_mask = 1 << int(end_bit)
    end_timestamp = (
        _first_rising_timestamp(dio_samples, bit_mask=end_mask)
        if use_dio_end_marker
        else None
    )
    if end_timestamp is None and nominal_duration_ticks is None:
        observed = sorted({int(value) for _, value in dio_samples})[:8]
        raise ValueError(
            f"No DIO{end_bit} low-to-high end transition was captured "
            f"on API demodulator {timing_demodulator}; observed DIO values include {observed}."
        )

    if nominal_duration_ticks is None:
        # The DAQ hardware trigger is DIO19 with zero configured delay. The
        # first paired detector sample is the earliest measured point after it.
        start_timestamp = max(samples[0][0], references[0][0])
        start_method = "first_detector_sample_after_hardware_trigger"
        end_method = "dio_end_marker"
    else:
        if end_timestamp is None:
            # The present DB9-to-DIO mapping has not produced a usable Tuned
            # edge.  For the slow sweep workflow the DAQ is armed first and
            # the MIRcat StartSweepScan command is issued after a prescribed
            # pre-delay, so use that deterministic timing interval rather
            # than guessing which unrelated DIO bit is the endpoint.
            start_timestamp = (
                max(samples[0][0], references[0][0])
                + max(0.0, float(nominal_start_offset_ticks))
            )
            end_timestamp = start_timestamp + float(nominal_duration_ticks)
            start_method = "first_detector_sample_plus_configured_pre_delay"
            end_method = "commanded_duration_after_configured_start"
        else:
            start_timestamp = end_timestamp - float(nominal_duration_ticks)
            start_method = "end_marker_minus_commanded_duration"
            end_method = "dio_end_marker"
    if end_timestamp <= start_timestamp:
        raise ValueError("MIRcat Tuned end marker precedes the first detector sample")
    retained_start_timestamp = start_timestamp + max(0.0, float(initial_settling_ticks))
    if retained_start_timestamp >= end_timestamp:
        raise ValueError("Initial settling interval is longer than the measured sweep")
    kept_samples = [
        (timestamp, value)
        for timestamp, value in samples
        if retained_start_timestamp <= timestamp <= end_timestamp
    ]
    if len(kept_samples) < 2:
        raise ValueError("Fewer than two Sample points remain between sweep start and Tuned end marker")

    ref_timestamps = [timestamp for timestamp, _ in references]
    rows: list[tuple[float, float, float]] = []
    span = end_timestamp - start_timestamp
    for timestamp, sample in kept_samples:
        reference = _interpolate(references, ref_timestamps, timestamp)
        fraction = (timestamp - start_timestamp) / span
        wavenumber = start_cm1 + (stop_cm1 - start_cm1) * fraction
        rows.append((wavenumber, sample, reference))
    return rows, {
        "start_timestamp": start_timestamp,
        "retained_start_timestamp": retained_start_timestamp,
        "end_timestamp": end_timestamp,
        "end_bit": int(end_bit),
        "timing_demodulator_api_index": int(timing_demodulator),
        "start_method": start_method,
        "end_method": end_method,
        "dio_end_marker_captured": end_method == "dio_end_marker",
        "initial_settling_ticks": max(0.0, float(initial_settling_ticks)),
        "retained_sample_count": len(rows),
    }


def segmented_kaleidagraph_rows_from_hf2li_record(
    record: dict,
    *,
    wavelength_targets_cm1: Iterable[float],
    sweep_active_bit: int,
    wavelength_trigger_bit: int,
    sample_demodulator: int = 0,
    reference_demodulator: int = 3,
    timing_demodulator: int = 2,
) -> tuple[list[tuple[float, float, float]], dict[str, object]]:
    """Calibrate detector samples independently inside each active QCL segment.

    The complete DIO word is sampled on ``timing_demodulator``. Rising edges
    of ``sweep_active_bit`` delimit physical QCL sweeps and rising edges of
    ``wavelength_trigger_bit`` are paired, in acquisition order, with the
    configured MIRcat wavelength targets. No detector sample from an inactive
    interval is retained and interpolation never crosses such an interval.

    At least two wavelength anchors are required in every retained segment.
    This deliberately rejects an under-constrained wavelength axis instead of
    filling it from host timing or the commanded average scan rate.
    """
    samples = _sample_field_series(record, demodulator=sample_demodulator, field="r")
    references = _sample_field_series(record, demodulator=reference_demodulator, field="r")
    dio = _sample_field_series(record, demodulator=timing_demodulator, field="dio")
    targets = [float(value) for value in wavelength_targets_cm1]
    if len(samples) < 2 or len(references) < 2:
        raise ValueError("HF2LI record contains fewer than two Sample/Reference R points")
    if len(dio) < 2:
        raise ValueError("HF2LI record contains no usable complete DIO-word stream")
    if not targets:
        raise ValueError("No configured MIRcat wavelength-trigger targets were supplied")
    if sweep_active_bit == wavelength_trigger_bit:
        raise ValueError("Sweep Active and Wavelength Trigger must map to different HF2LI DIO bits")

    active_mask = 1 << int(sweep_active_bit)
    trigger_mask = 1 << int(wavelength_trigger_bit)
    segments = _high_intervals(dio, bit_mask=active_mask)
    trigger_times = _rising_timestamps(dio, bit_mask=trigger_mask)
    if not segments:
        raise ValueError(f"No DIO{sweep_active_bit} Sweep Active high segment was captured")
    if len(trigger_times) != len(targets):
        raise ValueError(
            "Captured wavelength-trigger edge count does not match configured targets "
            f"({len(trigger_times)} edges, {len(targets)} targets); refusing an ambiguous calibration"
        )

    anchors = list(zip(trigger_times, targets))
    reference_times = [timestamp for timestamp, _ in references]
    rows: list[tuple[float, float, float]] = []
    segment_metadata: list[dict[str, object]] = []
    for index, (segment_start, segment_end) in enumerate(segments):
        # Intervals are half-open: the DIO sample at ``segment_end`` already
        # reports Sweep Active low and must not leak into the valid record.
        segment_anchors = [anchor for anchor in anchors if segment_start <= anchor[0] < segment_end]
        segment_samples = [item for item in samples if segment_start <= item[0] < segment_end]
        if not segment_samples:
            continue
        if len(segment_anchors) < 2:
            raise ValueError(
                f"Sweep Active segment {index + 1} has {len(segment_anchors)} wavelength anchor(s); "
                "at least two are required for an independent time-to-wavenumber calibration"
            )
        anchor_times = [timestamp for timestamp, _ in segment_anchors]
        segment_rows = []
        for timestamp, sample in segment_samples:
            wavenumber = _interpolate_or_extrapolate(segment_anchors, anchor_times, timestamp)
            reference = _interpolate(references, reference_times, timestamp)
            segment_rows.append((wavenumber, sample, reference))
        rows.extend(segment_rows)
        segment_metadata.append(
            {
                "index": index,
                "start_timestamp": segment_start,
                "end_timestamp": segment_end,
                "anchor_count": len(segment_anchors),
                "sample_count": len(segment_rows),
                "first_anchor_cm1": segment_anchors[0][1],
                "last_anchor_cm1": segment_anchors[-1][1],
            }
        )
    if not rows:
        raise ValueError("No detector samples occurred while Sweep Active was high")
    return rows, {
        "calibration_method": "per_sweep_active_segment_wavelength_trigger_interpolation",
        "sweep_active_bit": int(sweep_active_bit),
        "wavelength_trigger_bit": int(wavelength_trigger_bit),
        "timing_demodulator_api_index": int(timing_demodulator),
        "configured_anchor_count": len(targets),
        "captured_anchor_count": len(trigger_times),
        "segment_count": len(segment_metadata),
        "segments": segment_metadata,
        "retained_sample_count": len(rows),
    }


def dio_bit_diagnostics(
    record: dict, *, timing_demodulator: int = 2, clockbase_hz: float
) -> dict[str, object]:
    """Summarize every observed DIO bit without assigning physical labels."""

    dio = _sample_field_series(record, demodulator=timing_demodulator, field="dio")
    if len(dio) < 2:
        raise ValueError("HF2LI record contains no usable complete DIO-word stream")
    if clockbase_hz <= 0:
        raise ValueError("HF2LI clockbase must be positive")
    observed_or = 0
    changed = 0
    previous = int(dio[0][1])
    for _, value in dio:
        word = int(value)
        observed_or |= word
        changed |= previous ^ word
        previous = word
    candidate_mask = observed_or | changed
    bits: list[dict[str, object]] = []
    for bit in range(32):
        mask = 1 << bit
        if not candidate_mask & mask:
            continue
        intervals = _high_intervals(dio, bit_mask=mask)
        rising = _rising_timestamps(dio, bit_mask=mask)
        falling = _falling_timestamps(dio, bit_mask=mask)
        durations_s = [(end - start) / clockbase_hz for start, end in intervals]
        rising_spacing_s = [
            (right - left) / clockbase_hz for left, right in zip(rising, rising[1:])
        ]
        bits.append(
            {
                "bit": bit,
                "mask": mask,
                "initial_high": bool(int(dio[0][1]) & mask),
                "final_high": bool(int(dio[-1][1]) & mask),
                "rising_edge_count": len(rising),
                "falling_edge_count": len(falling),
                "high_interval_count": len(intervals),
                "high_durations_s": durations_s,
                "rising_edge_spacings_s": rising_spacing_s,
            }
        )
    return {
        "timing_demodulator_api_index": int(timing_demodulator),
        "clockbase_hz": float(clockbase_hz),
        "first_timestamp": dio[0][0],
        "last_timestamp": dio[-1][0],
        "sample_count": len(dio),
        "observed_word_values": sorted({int(value) for _, value in dio}),
        "bits": bits,
    }


def _sample_field_series(record: dict, *, demodulator: int, field: str) -> list[tuple[float, float]]:
    """Extract and timestamp-sort one LabOne sample field from DAQ data."""
    needle = f"/demods/{int(demodulator)}/sample"
    # The DAQ Module returns concrete subscriptions as separate nodes, e.g.
    # ``.../sample.x`` with a ``value`` matrix, whereas poll() commonly
    # returns one aggregate ``.../sample`` record containing x/y/dio fields.
    # Support both response shapes.
    if field == "r":
        direct_r = _node_value_series(record, needle=needle, suffix=".r")
        if direct_r:
            return direct_r
        x_series = _node_value_series(record, needle=needle, suffix=".x")
        y_series = _node_value_series(record, needle=needle, suffix=".y")
        if x_series and y_series:
            count = min(len(x_series), len(y_series))
            return [
                (x_series[index][0], math.hypot(x_series[index][1], y_series[index][1]))
                for index in range(count)
            ]
    else:
        direct = _node_value_series(record, needle=needle, suffix=f".{field}")
        if direct:
            return direct

    series: list[tuple[float, float]] = []
    for path, payload in (record.get("data") or {}).items():
        if needle not in str(path).lower():
            continue
        chunks = payload if isinstance(payload, list) else [payload]
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            timestamps = _as_list(chunk.get("timestamp"))
            if field in chunk:
                values = _as_list(chunk.get(field))
            elif field == "r" and "x" in chunk and "y" in chunk:
                # LabOne's native demodulator sample contains X/Y. The UI's R
                # trace is their magnitude and is not always returned as a
                # separate ``r`` array by the API.
                x_values = _as_list(chunk["x"])
                y_values = _as_list(chunk["y"])
                values = [
                    math.hypot(float(_scalar(x)), float(_scalar(y)))
                    for x, y in zip(x_values, y_values)
                ]
            else:
                continue
            for index, value in enumerate(values):
                if index >= len(timestamps):
                    continue
                series.append((float(_scalar(timestamps[index])), float(_scalar(value))))
    return sorted(series, key=lambda item: item[0])


def _node_value_series(record: dict, *, needle: str, suffix: str) -> list[tuple[float, float]]:
    """Read a concrete DAQ subscription node with timestamp/value arrays."""

    series: list[tuple[float, float]] = []
    expected_path = f"{needle}{suffix}"
    for path, payload in (record.get("data") or {}).items():
        path_text = str(path).lower()
        if not path_text.endswith(expected_path):
            continue
        chunks = payload if isinstance(payload, list) else [payload]
        for chunk in chunks:
            if not isinstance(chunk, dict) or "timestamp" not in chunk or "value" not in chunk:
                continue
            timestamps = _flatten_scalars(chunk["timestamp"])
            values = _flatten_scalars(chunk["value"])
            for timestamp, value in zip(timestamps, values):
                series.append((float(timestamp), float(value)))
    return sorted(series, key=lambda item: item[0])


def _first_rising_timestamp(series: list[tuple[float, float]], *, bit_mask: int) -> float | None:
    previous_high = bool(int(series[0][1]) & bit_mask)
    for timestamp, value in series[1:]:
        current_high = bool(int(value) & bit_mask)
        if not previous_high and current_high:
            return timestamp
        previous_high = current_high
    return None


def _rising_timestamps(series: list[tuple[float, float]], *, bit_mask: int) -> list[float]:
    previous_high = bool(int(series[0][1]) & bit_mask)
    timestamps: list[float] = []
    for timestamp, value in series[1:]:
        current_high = bool(int(value) & bit_mask)
        if not previous_high and current_high:
            timestamps.append(timestamp)
        previous_high = current_high
    return timestamps


def _falling_timestamps(series: list[tuple[float, float]], *, bit_mask: int) -> list[float]:
    previous_high = bool(int(series[0][1]) & bit_mask)
    timestamps: list[float] = []
    for timestamp, value in series[1:]:
        current_high = bool(int(value) & bit_mask)
        if previous_high and not current_high:
            timestamps.append(timestamp)
        previous_high = current_high
    return timestamps


def _high_intervals(series: list[tuple[float, float]], *, bit_mask: int) -> list[tuple[float, float]]:
    """Return sampled high intervals, closing a final high at the last timestamp."""
    intervals: list[tuple[float, float]] = []
    start = series[0][0] if int(series[0][1]) & bit_mask else None
    for timestamp, value in series[1:]:
        high = bool(int(value) & bit_mask)
        if high and start is None:
            start = timestamp
        elif not high and start is not None:
            intervals.append((start, timestamp))
            start = None
    if start is not None:
        intervals.append((start, series[-1][0]))
    return intervals


def _interpolate(series: list[tuple[float, float]], timestamps: list[float], timestamp: float) -> float:
    """Linearly interpolate a reference value onto a Sample timestamp."""
    index = bisect_left(timestamps, timestamp)
    if index <= 0:
        return series[0][1]
    if index >= len(series):
        return series[-1][1]
    left_time, left_value = series[index - 1]
    right_time, right_value = series[index]
    if right_time == left_time:
        return right_value
    fraction = (timestamp - left_time) / (right_time - left_time)
    return left_value + (right_value - left_value) * fraction


def _interpolate_or_extrapolate(
    series: list[tuple[float, float]], timestamps: list[float], timestamp: float
) -> float:
    """Piecewise-linear calibration, using the nearest two anchors at edges."""
    index = bisect_left(timestamps, timestamp)
    if index <= 0:
        left, right = series[0], series[1]
    elif index >= len(series):
        left, right = series[-2], series[-1]
    else:
        left, right = series[index - 1], series[index]
    if right[0] == left[0]:
        raise ValueError("Two wavelength-trigger anchors have the same HF2LI timestamp")
    fraction = (timestamp - left[0]) / (right[0] - left[0])
    return left[1] + (right[1] - left[1]) * fraction


def _as_list(value: object) -> list:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    return value if isinstance(value, list) else [value]


def _flatten_scalars(value: object) -> list[object]:
    """Flatten LabOne's 1xN DAQ matrices without altering scalar values."""

    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        flattened: list[object] = []
        for item in value:
            flattened.extend(_flatten_scalars(item))
        return flattened
    return [value]


def _scalar(value: object) -> object:
    return value.item() if hasattr(value, "item") else value
