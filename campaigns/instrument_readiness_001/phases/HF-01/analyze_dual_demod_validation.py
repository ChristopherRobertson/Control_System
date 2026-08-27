"""Apply HF01-MODEL-RESIDUAL-v2 to the three dual-demodulator anchors.

This analysis is intentionally self-contained and was frozen before the v3
anchor data were acquired.  Demodulator 0 is the test filter and demodulator 1
is the same-clock wideband reference.
"""

from __future__ import annotations

from array import array
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
ANALYSIS = HERE / "analysis"
CLOCKBASE_HZ = 210_000_000.0
CRITERION_VERSION = "HF01-MODEL-RESIDUAL-v3"

ANCHORS: dict[str, dict[str, Any]] = {
    "fast": {
        "stem": "hf01_anchor_fast_v3_001",
        "acquisition_id": "HF01-ANCHOR-FAST-V3-001",
        "retained_fraction": 0.5,
    },
    "intermediate": {
        "stem": "hf01_anchor_intermediate_v3_001",
        "acquisition_id": "HF01-ANCHOR-INTERMEDIATE-V3-001",
        "retained_fraction": 0.5,
    },
    "slow": {
        "stem": "hf01_anchor_slow_v3_r1_001",
        "acquisition_id": "HF01-ANCHOR-SLOW-V3-R1-001",
        "retained_fraction": 0.8,
    },
}


def wrap_phase(value: float) -> float:
    return float(math.atan2(math.sin(value), math.cos(value)))


def transfer(order: int, tau_s: float, frequency_hz: float) -> complex:
    return complex(1.0 + 2j * math.pi * frequency_hz * tau_s) ** (-order)


def response_magnitude(order: int, tau_s: float, frequency_hz: float) -> float:
    return abs(transfer(order, tau_s, frequency_hz))


def step_fraction(order: int, tau_s: float, time_s: float) -> float:
    scaled = max(0.0, time_s) / tau_s
    survival = math.exp(-scaled) * sum(
        scaled**index / math.factorial(index) for index in range(order)
    )
    return 1.0 - survival


def step_crossing_time(order: int, tau_s: float, fraction: float) -> float:
    lower = 0.0
    upper = max(tau_s, 1e-12)
    while step_fraction(order, tau_s, upper) < fraction:
        upper *= 2.0
    for _ in range(80):
        midpoint = 0.5 * (lower + upper)
        if step_fraction(order, tau_s, midpoint) < fraction:
            lower = midpoint
        else:
            upper = midpoint
    return 0.5 * (lower + upper)


def load_synchronized_complex(
    path: Path,
    test_demod: int = 0,
    reference_demod: int = 1,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    streams: dict[tuple[int, str], tuple[array[int], array[float]]] = {
        (demod, field): (array("q"), array("d"))
        for demod in (test_demod, reference_demod)
        for field in ("x", "y")
    }
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            normalized = row["path"].lower()
            matched: tuple[int, str] | None = None
            for key in streams:
                suffix = f"/demods/{key[0]}/sample.{key[1]}"
                if normalized.endswith(suffix):
                    matched = key
                    break
            if matched is None:
                continue
            timestamps, values = streams[matched]
            timestamps.append(int(row["timestamp"]))
            values.append(float(row["value"]))

    converted: dict[tuple[int, str], tuple[np.ndarray, np.ndarray]] = {}
    for key, (timestamp_buffer, value_buffer) in streams.items():
        converted[key] = (
            np.frombuffer(timestamp_buffer, dtype=np.int64),
            np.frombuffer(value_buffer, dtype=np.float64),
        )
        if len(converted[key][0]) == 0:
            raise RuntimeError(f"Missing demodulator stream {key} in {path}")

    for demod in (test_demod, reference_demod):
        tx, x = converted[(demod, "x")]
        ty, y = converted[(demod, "y")]
        if not np.array_equal(tx, ty):
            raise RuntimeError(f"Demodulator {demod} X/Y timestamps do not match")
        if len(x) != len(y):
            raise RuntimeError(f"Demodulator {demod} X/Y lengths do not match")
    t0_full = converted[(test_demod, "x")][0]
    t1_full = converted[(reference_demod, "x")][0]
    if len(t0_full) < 2 or len(t1_full) < 2:
        raise RuntimeError("HF2LI streams do not contain enough samples")
    overlap_start = max(int(t0_full[0]), int(t1_full[0]))
    overlap_end = min(int(t0_full[-1]), int(t1_full[-1]))
    slice0 = slice(
        int(np.searchsorted(t0_full, overlap_start, side="left")),
        int(np.searchsorted(t0_full, overlap_end, side="right")),
    )
    slice1 = slice(
        int(np.searchsorted(t1_full, overlap_start, side="left")),
        int(np.searchsorted(t1_full, overlap_end, side="right")),
    )
    t0 = t0_full[slice0]
    t1 = t1_full[slice1]
    if not np.array_equal(t0, t1):
        raise RuntimeError(
            "Demodulators 0 and 1 do not have an exact common timestamp grid"
        )
    if len(t0) < 2 or bool(np.any(np.diff(t0) <= 0)):
        raise RuntimeError("HF2LI timestamps are not strictly monotonic")
    z0 = converted[(test_demod, "x")][1][slice0] + 1j * converted[(test_demod, "y")][1][slice0]
    z1 = converted[(reference_demod, "x")][1][slice1] + 1j * converted[(reference_demod, "y")][1][slice1]
    return t0, z0, z1, {
        "exact_retained_test_reference_timestamp_match": True,
        "strictly_monotonic_timestamps": True,
        "sample_count_per_complex_stream": int(len(t0)),
        "test_raw_sample_count": int(len(t0_full)),
        "reference_raw_sample_count": int(len(t1_full)),
        "test_endpoint_samples_not_in_overlap": int(len(t0_full) - len(t0)),
        "reference_endpoint_samples_not_in_overlap": int(len(t1_full) - len(t1)),
        "first_timestamp": int(t0[0]),
        "last_timestamp": int(t0[-1]),
    }


def segment_indices(
    timestamps: np.ndarray,
    segments: list[dict[str, Any]],
    index: int,
    retained_fraction: float,
) -> np.ndarray:
    segment = segments[index]
    end_tick = (
        int(segments[index + 1]["device_tick_before"])
        if index + 1 < len(segments)
        else int(timestamps[-1]) + 1
    )
    selected = np.flatnonzero(
        (timestamps >= int(segment["device_tick_after"]))
        & (timestamps < end_tick)
    )
    if len(selected) < 8:
        raise RuntimeError(
            f"Only {len(selected)} samples in segment {segment['label']}"
        )
    first = min(len(selected) - 8, int(len(selected) * retained_fraction))
    return selected[first:]


def identify_nonzero_runs(reference: np.ndarray) -> tuple[list[tuple[int, int]], float]:
    """Return contiguous connected-stimulus intervals from the reference demodulator."""

    magnitude = np.abs(reference)
    low = float(np.quantile(magnitude, 0.10))
    high = float(np.quantile(magnitude, 0.99))
    if high <= low or high < 10.0 * max(low, 1e-15):
        raise RuntimeError("Reference demodulator does not resolve connected stimulus")
    threshold = 0.5 * (low + high)
    connected = magnitude >= threshold
    # A single decimated sample can momentarily straddle the transition level.
    # Bridge only sub-grid gaps of at most eight samples; longer gaps remain
    # independent physical stimulus intervals.
    gap_edges = np.diff(np.concatenate(([True], connected, [True])).astype(np.int8))
    gap_starts = np.flatnonzero(gap_edges == -1)
    gap_ends = np.flatnonzero(gap_edges == 1)
    for start, end in zip(gap_starts, gap_ends):
        if 0 < int(start) and int(end) < len(connected) and int(end - start) <= 8:
            connected[start:end] = True
    edges = np.diff(np.concatenate(([False], connected, [False])).astype(np.int8))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    runs = [
        (int(start), int(end))
        for start, end in zip(starts, ends)
        if int(end - start) >= 8
    ]
    return runs, threshold


def complex_statistics(values: np.ndarray) -> dict[str, Any]:
    if len(values) < 3:
        raise RuntimeError("At least three samples are required")
    mean = complex(np.mean(values))
    centered = values - mean
    complex_std = float(
        math.sqrt(np.var(centered.real, ddof=1) + np.var(centered.imag, ddof=1))
    )
    return {
        "mean": mean,
        "complex_std": complex_std,
        "complex_standard_uncertainty": complex_std / math.sqrt(len(values)),
        "samples": int(len(values)),
    }


def observed_frequency(
    timestamps: np.ndarray,
    reference: np.ndarray,
    commanded_offset_hz: float,
    rate_sps: float,
) -> tuple[float, float, float]:
    seconds = (timestamps - timestamps[0]) / CLOCKBASE_HZ
    phase = np.unwrap(np.angle(reference))
    slope, intercept = np.polyfit(seconds, phase, 1)
    residual = phase - (slope * seconds + intercept)
    alias_hz = float(slope / (2.0 * math.pi))
    reconstructed_hz = alias_hz + round(
        (commanded_offset_hz - alias_hz) / rate_sps
    ) * rate_sps
    return reconstructed_hz, alias_hz, float(np.sqrt(np.mean(residual**2)))


def crossing_time(
    times: np.ndarray,
    values: np.ndarray,
    fraction: float,
    direction: str,
) -> tuple[float | None, float | None]:
    if direction == "rising":
        candidates = np.flatnonzero((values[:-1] < fraction) & (values[1:] >= fraction))
        persistent = values >= fraction
    else:
        candidates = np.flatnonzero((values[:-1] > fraction) & (values[1:] <= fraction))
        persistent = values <= fraction
    hold = min(3, max(1, len(values) // 20))
    candidates = np.asarray(
        [
            index
            for index in candidates
            if bool(np.all(persistent[index + 1 : index + 1 + hold]))
        ],
        dtype=int,
    )
    if len(candidates) == 0:
        return None, None
    index = int(candidates[0])
    delta = float(values[index + 1] - values[index])
    interpolation = 0.0 if delta == 0 else (fraction - float(values[index])) / delta
    interpolation = min(1.0, max(0.0, interpolation))
    crossing = float(times[index] + interpolation * (times[index + 1] - times[index]))
    local_start = max(0, index - 4)
    local_end = min(len(values), index + 6)
    local_times = times[local_start:local_end]
    local_values = values[local_start:local_end]
    if len(local_times) < 3:
        return crossing, None
    local_slope, local_intercept = np.polyfit(local_times, local_values, 1)
    scatter = float(
        np.std(local_values - (local_slope * local_times + local_intercept), ddof=1)
    )
    uncertainty = None if local_slope == 0 else abs(scatter / local_slope)
    return crossing, uncertainty


def analyze_step_transitions(
    timestamps: np.ndarray,
    test: np.ndarray,
    reference: np.ndarray,
    segments: list[dict[str, Any]],
    test_order: int,
    test_tau_s: float,
    reference_tau_s: float,
    rate_sps: float,
    pipeline_delay_s: float,
    pipeline_delay_standard_uncertainty_s: float,
) -> dict[str, Any]:
    predicted_1_s = step_crossing_time(test_order, test_tau_s, 0.01)
    predicted_99_s = step_crossing_time(test_order, test_tau_s, 0.99)
    predicted_settling_s = predicted_99_s - predicted_1_s
    predicted_test_50_s = step_crossing_time(test_order, test_tau_s, 0.5)
    predicted_reference_50_s = step_crossing_time(1, reference_tau_s, 0.5)
    predicted_group_delay_s = predicted_test_50_s - predicted_reference_50_s
    sample_interval_s = 1.0 / rate_sps
    rows: list[dict[str, Any]] = []
    steady_test_levels: list[float] = []

    for index, segment in enumerate(segments):
        label = str(segment["label"])
        if not (label.startswith("step_rise_") or label.startswith("step_fall_")):
            continue
        end_tick = (
            int(segments[index + 1]["device_tick_before"])
            if index + 1 < len(segments)
            else int(timestamps[-1]) + 1
        )
        selected = np.flatnonzero(
            (timestamps >= int(segment["device_tick_before"]))
            & (timestamps < end_tick)
        )
        if len(selected) < 12:
            rows.append({"label": label, "status": "INSUFFICIENT_SAMPLES"})
            continue
        times = (timestamps[selected] - timestamps[selected][0]) / CLOCKBASE_HZ
        test_magnitude = np.abs(test[selected])
        reference_magnitude = np.abs(reference[selected])
        edge_count = max(3, min(len(selected) // 8, int(rate_sps * 0.002)))
        edge_count = min(edge_count, max(3, len(selected) // 4))
        initial_test = float(np.mean(test_magnitude[:edge_count]))
        final_test = float(np.mean(test_magnitude[-edge_count:]))
        initial_reference = float(np.mean(reference_magnitude[:edge_count]))
        final_reference = float(np.mean(reference_magnitude[-edge_count:]))
        test_delta = final_test - initial_test
        reference_delta = final_reference - initial_reference
        if abs(test_delta) < 1e-12 or abs(reference_delta) < 1e-12:
            rows.append({"label": label, "status": "EDGE_NOT_IDENTIFIED"})
            continue
        normalized_test = (test_magnitude - initial_test) / test_delta
        normalized_reference = (
            reference_magnitude - initial_reference
        ) / reference_delta
        direction = "rising"
        reference_50_s, reference_50_u_s = crossing_time(
            times, normalized_reference, 0.5, direction
        )
        test_50_s, test_50_u_s = crossing_time(times, normalized_test, 0.5, direction)
        test_1_s, test_1_u_s = crossing_time(times, normalized_test, 0.01, direction)
        test_99_s, test_99_u_s = crossing_time(times, normalized_test, 0.99, direction)
        resolved = all(
            value is not None
            for value in (reference_50_s, test_50_s, test_1_s, test_99_s)
        )
        if not resolved:
            rows.append({"label": label, "status": "EDGE_NOT_IDENTIFIED"})
            continue
        observed_settling_s = float(test_99_s - test_1_s)  # type: ignore[operator]
        observed_group_delay_uncorrected_s = float(test_50_s - reference_50_s)  # type: ignore[operator]
        observed_group_delay_s = observed_group_delay_uncorrected_s - pipeline_delay_s
        group_u_s = math.sqrt(
            float(test_50_u_s or 0.0) ** 2
            + float(reference_50_u_s or 0.0) ** 2
            + pipeline_delay_standard_uncertainty_s**2
        )
        group_threshold_s = max(
            0.05 * max(abs(predicted_group_delay_s), sample_interval_s),
            sample_interval_s,
            3.0 * group_u_s,
        )
        settling_u_s = math.sqrt(
            float(test_1_u_s or 0.0) ** 2 + float(test_99_u_s or 0.0) ** 2
        )
        if label.startswith("step_rise_"):
            overshoot = max(
                0.0,
                float(np.max(normalized_test)) - 1.0,
                -float(np.min(normalized_test)),
            )
            steady_test_levels.append(final_test)
        else:
            overshoot = max(
                0.0,
                float(np.max(normalized_test)) - 1.0,
                -float(np.min(normalized_test)),
            )
            steady_test_levels.append(initial_test)
        rows.append(
            {
                "label": label,
                "status": "EVALUATED",
                "reference_edge_50_s": reference_50_s,
                "test_edge_50_s": test_50_s,
                "observed_1_to_99_s": observed_settling_s,
                "predicted_1_to_99_s": predicted_settling_s,
                "settling_standard_uncertainty_s": settling_u_s,
                "settling_limit_s": 1.2 * predicted_settling_s,
                "settling_pass": observed_settling_s <= 1.2 * predicted_settling_s,
                "absolute_overshoot": overshoot,
                "overshoot_pass": overshoot <= 0.05,
                "observed_relative_group_delay_uncorrected_s": observed_group_delay_uncorrected_s,
                "observed_relative_group_delay_s": observed_group_delay_s,
                "predicted_relative_group_delay_s": predicted_group_delay_s,
                "group_delay_residual_s": observed_group_delay_s
                - predicted_group_delay_s,
                "group_delay_standard_uncertainty_s": group_u_s,
                "group_delay_threshold_s": group_threshold_s,
                "group_delay_pass": abs(observed_group_delay_s - predicted_group_delay_s)
                <= group_threshold_s,
            }
        )

    evaluated = [row for row in rows if row.get("status") == "EVALUATED"]
    gain_span = (
        (max(steady_test_levels) - min(steady_test_levels))
        / float(np.mean(steady_test_levels))
        if len(steady_test_levels) >= 2
        else None
    )
    all_six = len(evaluated) == 6
    return {
        "sample_interval_s": sample_interval_s,
        "predicted_1_percent_s": predicted_1_s,
        "predicted_99_percent_s": predicted_99_s,
        "predicted_1_to_99_s": predicted_settling_s,
        "predicted_relative_group_delay_s": predicted_group_delay_s,
        "pipeline_delay_correction_s": pipeline_delay_s,
        "pipeline_delay_standard_uncertainty_s": pipeline_delay_standard_uncertainty_s,
        "transitions": rows,
        "evaluated_transition_count": len(evaluated),
        "reference_edges_identified_pass": all_six,
        "settling_and_overshoot_pass": all_six
        and all(bool(row["settling_pass"]) and bool(row["overshoot_pass"]) for row in evaluated),
        "group_delay_pass": all_six and all(bool(row["group_delay_pass"]) for row in evaluated),
        "rising_falling_final_gain_fractional_span": gain_span,
        "rising_falling_final_gain_pass": gain_span is not None and gain_span <= 0.05,
    }


def analyze_zero_noise(
    timestamps: np.ndarray,
    test: np.ndarray,
    segments: list[dict[str, Any]],
    order: int,
    tau_s: float,
) -> dict[str, Any]:
    windows: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        if segment["kind"] != "zero":
            continue
        end_tick = (
            int(segments[index + 1]["device_tick_before"])
            if index + 1 < len(segments)
            else int(timestamps[-1]) + 1
        )
        selected = np.flatnonzero(
            (timestamps >= int(segment["device_tick_after"]))
            & (timestamps < end_tick)
        )
        if len(selected) < 8:
            continue
        selected = selected[len(selected) // 2 :]
        values = test[selected]
        windows.append(
            {
                "label": segment["label"],
                "samples": int(len(values)),
                "complex_rms_v": float(
                    math.sqrt(np.var(values.real, ddof=1) + np.var(values.imag, ddof=1))
                ),
            }
        )
    enbw_hz = math.gamma(order - 0.5) / (
        4.0 * math.sqrt(math.pi) * math.gamma(order) * tau_s
    )
    return {
        "window_count": len(windows),
        "windows": windows,
        "manufacturer_enbw_hz": enbw_hz,
        "median_complex_output_rms_v": (
            float(np.median([row["complex_rms_v"] for row in windows]))
            if windows
            else None
        ),
    }


def validate_integrity(status: dict[str, Any]) -> dict[str, Any]:
    staged = status["hf2li_staged"]
    test = staged["test_demod"]
    reference = staged["reference_demod"]
    input_index = int(staged.get("signal_input_index", 0))
    input_range_v = float(
        staged.get("signal_input_range_v", staged.get("sigins0_range_v"))
    )
    pico_rows: list[dict[str, Any]] = []
    for segment in status["segments"]:
        monitor = segment.get("monitor")
        if not monitor:
            continue
        analysis = monitor["analysis"]
        residual = float(analysis.get("sine_fit_residual_rms_v") or 0.0)
        peak_with_expanded_uncertainty = float(analysis["a_peak_absolute_v"]) + (
            3.0 * residual / math.sqrt(max(1, int(analysis["retained_samples"])))
        )
        pico_rows.append(
            {
                "label": segment["label"],
                "overflow": int(monitor["capture"]["overflow"]),
                "peak_with_expanded_uncertainty_v": peak_with_expanded_uncertainty,
                "eighty_percent_range_v": 0.8 * input_range_v,
                "range_margin_pass": peak_with_expanded_uncertainty
                < 0.8 * input_range_v,
            }
        )
    settings_pass = (
        int(test["index"]) == int(status["anchor_plan"].get("test_demod_index", 0))
        and int(reference["index"]) == int(status["anchor_plan"].get("reference_demod_index", 1))
        and int(test["enable"]) == 1
        and int(reference["enable"]) == 1
        and int(test["adcselect"]) == int(reference["adcselect"]) == input_index
        and int(test["oscselect"]) == int(reference["oscselect"]) == 0
        and int(test["harmonic"]) == int(reference["harmonic"]) == 1
        and int(reference["order"]) == 1
        and int(test["trigger"]) == int(reference["trigger"]) == 0
        and int(test["order"]) == int(status["anchor_plan"]["order"])
        and math.isclose(
            float(test["timeconstant_s"]),
            float(staged["timeconstant_s"]),
            rel_tol=1e-12,
        )
        and math.isclose(
            float(test["rate_sps"]), float(reference["rate_sps"]), rel_tol=1e-9
        )
    )
    after = status["hf2li_after"]
    lock_pass = (
        int(after["pll_locked"]) == 1
        and int(after["external_clock"]) == 1
        and int(after["pll_lock_flag"]) == 0
        and int(after["dcm_lock_flag"]) == 0
    )
    status_pass = (
        status["status"] == "CAPTURED"
        and int(after["adcclip"]) == 0
        and int(after["demodsampleloss"]) == 0
        and status["t660_safe_idle_after"]["matches_recipe"] is True
        and not any(key.endswith("_error") for key in status)
    )
    pico_pass = bool(pico_rows) and all(
        row["overflow"] == 0 and bool(row["range_margin_pass"]) for row in pico_rows
    )
    return {
        "acquisition_and_safe_idle_pass": status_pass,
        "clock_lock_pass": lock_pass,
        "demodulator_settings_pass": settings_pass,
        "picoscope_voltage_and_overflow_pass": pico_pass,
        "picoscope_segments": pico_rows,
        "pass": status_pass and lock_pass and settings_pass and pico_pass,
    }


def fit_timeconstant(
    order: int,
    readback_tau_s: float,
    rows: list[dict[str, Any]],
) -> tuple[float, float]:
    candidates = np.geomspace(readback_tau_s / 3.0, readback_tau_s * 3.0, 5001)
    observed = np.asarray([complex(row["measured_response_complex"]) for row in rows])
    frequencies = np.asarray([float(row["observed_frequency_hz"]) for row in rows])
    uncertainties = np.asarray(
        [max(float(row["complex_standard_uncertainty"]), 1e-12) for row in rows]
    )
    predictions = np.asarray(
        [
            [transfer(order, float(candidate), float(frequency)) for frequency in frequencies]
            for candidate in candidates
        ],
        dtype=complex,
    )
    errors = np.sum(np.abs(predictions - observed) ** 2 / uncertainties**2, axis=1)
    fitted_index = int(np.argmin(errors))
    fitted_tau = float(candidates[fitted_index])

    rng = np.random.default_rng(66001 + order)
    trials: list[float] = []
    for _ in range(300):
        noise = rng.normal(size=len(rows)) + 1j * rng.normal(size=len(rows))
        synthetic = observed + noise * uncertainties / math.sqrt(2.0)
        trial_errors = np.sum(
            np.abs(predictions - synthetic[np.newaxis, :]) ** 2 / uncertainties**2,
            axis=1,
        )
        trials.append(float(candidates[int(np.argmin(trial_errors))]))
    tau_u = float(np.std(trials, ddof=1))
    return fitted_tau, tau_u


def analyze_anchor(name: str, config: dict[str, Any]) -> dict[str, Any]:
    stem = str(config["stem"])
    status_path = RAW / f"{stem}_status.json"
    raw_path = RAW / f"{stem}_hf2_raw.csv"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("acquisition_id") != config["acquisition_id"]:
        raise RuntimeError(f"Unexpected acquisition ID in {status_path}")
    if status.get("criterion_version") != CRITERION_VERSION:
        raise RuntimeError(f"Unexpected criterion version in {status_path}")

    timestamps, test_values, reference_values, timestamp_integrity = load_synchronized_complex(
        raw_path,
        int(config.get("test_demod_index", 0)),
        int(config.get("reference_demod_index", 1)),
    )
    integrity = validate_integrity(status)
    integrity["timestamp_stream"] = timestamp_integrity
    integrity["pass"] = bool(integrity["pass"]) and bool(
        timestamp_integrity["exact_retained_test_reference_timestamp_match"]
        and timestamp_integrity["strictly_monotonic_timestamps"]
    )

    segments: list[dict[str, Any]] = status["segments"]
    retained_fraction = float(config["retained_fraction"])
    test_settings = status["hf2li_staged"]["test_demod"]
    reference_settings = status["hf2li_staged"]["reference_demod"]
    order = int(test_settings["order"])
    tau_s = float(test_settings["timeconstant_s"])
    rate_sps = float(test_settings["rate_sps"])
    reference_tau_s = float(reference_settings["timeconstant_s"])

    nonzero_runs, reference_connected_threshold = identify_nonzero_runs(reference_values)
    nonzero_segments = [
        segment
        for segment in segments
        if segment["kind"] in {"carrier", "offset_carrier"}
    ]
    if len(nonzero_runs) != len(nonzero_segments):
        raise RuntimeError(
            "Reference-demodulator connected-run count does not match the declared "
            f"segments: {len(nonzero_runs)} versus {len(nonzero_segments)}"
        )

    segment_rows: list[dict[str, Any]] = []
    for segment, (run_start, run_end) in zip(nonzero_segments, nonzero_runs):
        run_indices = np.arange(run_start, run_end, dtype=int)
        first = min(len(run_indices) - 8, int(len(run_indices) * retained_fraction))
        selected = run_indices[first:]
        reference_floor = max(1e-12, 1e-6 * float(np.median(np.abs(reference_values[selected]))))
        selected = selected[np.abs(reference_values[selected]) > reference_floor]
        if len(selected) < 8:
            raise RuntimeError(f"Reference amplitude too low in {segment['label']}")
        ratio = test_values[selected] / reference_values[selected]
        stats = complex_statistics(ratio)
        commanded_offset = float(segment.get("offset_hz", 0.0))
        frequency_hz, alias_hz, phase_fit_rms = observed_frequency(
            timestamps[selected], reference_values[selected], commanded_offset, rate_sps
        )
        segment_rows.append(
            {
                "label": segment["label"],
                "kind": segment["kind"],
                "commanded_offset_hz": commanded_offset,
                "observed_frequency_hz": frequency_hz,
                "observed_alias_frequency_hz": alias_hz,
                "reference_phase_fit_rms_rad": phase_fit_rms,
                "ratio_mean_complex": stats["mean"],
                "ratio_complex_std": stats["complex_std"],
                "ratio_complex_standard_uncertainty": stats[
                    "complex_standard_uncertainty"
                ],
                "retained_samples": stats["samples"],
                "reference_gated_run_start_timestamp": int(timestamps[run_start]),
                "reference_gated_run_end_timestamp": int(timestamps[run_end - 1]),
                "input_vpp": float(segment["monitor"]["analysis"]["sine_fit_vpp"]),
            }
        )

    carriers = [row for row in segment_rows if row["kind"] == "carrier"]
    if len(carriers) != 3:
        raise RuntimeError(f"Expected three carrier replicates, found {len(carriers)}")
    for row in carriers:
        carrier_frequency = float(row["observed_frequency_hz"])
        carrier_model_ratio = transfer(order, tau_s, carrier_frequency) / transfer(
            1, reference_tau_s, carrier_frequency
        )
        row["baseline_model_ratio_complex"] = carrier_model_ratio
        row["model_corrected_gain_complex"] = (
            complex(row["ratio_mean_complex"]) / carrier_model_ratio
        )
        row["model_corrected_gain_standard_uncertainty"] = (
            float(row["ratio_complex_standard_uncertainty"])
            / abs(carrier_model_ratio)
        )
    gain = complex(
        np.mean([row["model_corrected_gain_complex"] for row in carriers])
    )
    carrier_between = np.asarray(
        [complex(row["model_corrected_gain_complex"]) for row in carriers]
    ) - gain
    gain_u = math.sqrt(
        sum(
            float(row["model_corrected_gain_standard_uncertainty"]) ** 2
            for row in carriers
        )
        / len(carriers) ** 2
        + (
            float(
                np.var(carrier_between.real, ddof=1)
                + np.var(carrier_between.imag, ddof=1)
            )
            / len(carriers)
        )
    )
    carrier_results: list[dict[str, Any]] = []
    for row in carriers:
        gain_estimate = complex(row["model_corrected_gain_complex"])
        normalized_deviation = abs(gain_estimate / gain - 1.0)
        combined_u = math.sqrt(
            (
                float(row["model_corrected_gain_standard_uncertainty"])
                / abs(gain)
            )
            ** 2
            + (abs(gain_estimate) * gain_u / abs(gain) ** 2) ** 2
        )
        threshold = max(0.05, 3.0 * combined_u)
        carrier_results.append(
            {
                **row,
                "normalized_complex_deviation": normalized_deviation,
                "combined_standard_uncertainty": combined_u,
                "acceptance_threshold": threshold,
                "pass": normalized_deviation <= threshold,
            }
        )
    carrier_repeatability_pass = all(bool(row["pass"]) for row in carrier_results)

    response_rows: list[dict[str, Any]] = []
    for row in segment_rows:
        if row["kind"] != "offset_carrier":
            continue
        frequency_hz = float(row["observed_frequency_hz"])
        normalized_ratio = complex(row["ratio_mean_complex"]) / gain
        reference_response = transfer(1, reference_tau_s, frequency_hz)
        predicted_test = transfer(order, tau_s, frequency_hz)
        predicted_ratio = predicted_test / reference_response
        measured_test = normalized_ratio * reference_response
        normalized_ratio_u = math.sqrt(
            (float(row["ratio_complex_standard_uncertainty"]) / abs(gain)) ** 2
            + (abs(complex(row["ratio_mean_complex"])) * gain_u / abs(gain) ** 2) ** 2
        )
        test_complex_u = abs(reference_response) * normalized_ratio_u
        magnitude_residual = abs(measured_test) - abs(predicted_test)
        phase_residual = wrap_phase(np.angle(measured_test) - np.angle(predicted_test))
        phase_u = test_complex_u / max(abs(measured_test), 1e-15)
        magnitude_threshold = max(0.05, 3.0 * test_complex_u)
        phase_threshold = max(math.radians(5.0), 3.0 * phase_u)
        response_rows.append(
            {
                **row,
                "reference_response_complex": reference_response,
                "normalized_ratio_complex": normalized_ratio,
                "predicted_ratio_complex": predicted_ratio,
                "measured_response_uncorrected_complex": measured_test,
                "measured_response_complex": measured_test,
                "predicted_response_complex": predicted_test,
                "measured_normalized_magnitude": abs(measured_test),
                "predicted_normalized_magnitude": abs(predicted_test),
                "magnitude_residual": magnitude_residual,
                "measured_phase_rad": float(np.angle(measured_test)),
                "predicted_phase_rad": float(np.angle(predicted_test)),
                "phase_residual_rad": phase_residual,
                "phase_residual_uncorrected_rad": phase_residual,
                "complex_standard_uncertainty": test_complex_u,
                "phase_standard_uncertainty_rad": phase_u,
                "magnitude_acceptance_threshold": magnitude_threshold,
                "phase_acceptance_threshold_rad": phase_threshold,
                "magnitude_pass": abs(magnitude_residual) <= magnitude_threshold,
                "phase_pass": abs(phase_residual) <= phase_threshold,
            }
        )

    angular_frequencies = np.asarray(
        [2.0 * math.pi * float(row["observed_frequency_hz"]) for row in response_rows]
    )
    raw_phase_residuals = np.asarray(
        [float(row["phase_residual_uncorrected_rad"]) for row in response_rows]
    )
    raw_phase_uncertainties = np.asarray(
        [max(float(row["phase_standard_uncertainty_rad"]), 1e-6) for row in response_rows]
    )
    phase_weights = 1.0 / raw_phase_uncertainties**2
    delay_denominator = float(np.sum(phase_weights * angular_frequencies**2))
    if delay_denominator <= 0.0:
        raise RuntimeError("Pipeline-delay fit is singular")
    pipeline_delay_s = float(
        np.sum(phase_weights * angular_frequencies * raw_phase_residuals)
        / delay_denominator
    )
    pipeline_delay_u_s = math.sqrt(1.0 / delay_denominator)
    sample_interval_s = 1.0 / rate_sps
    pipeline_delay_bound_pass = abs(pipeline_delay_s) <= sample_interval_s

    for row in response_rows:
        frequency_hz = float(row["observed_frequency_hz"])
        uncorrected = complex(row["measured_response_uncorrected_complex"])
        corrected = uncorrected * np.exp(-2j * math.pi * frequency_hz * pipeline_delay_s)
        predicted = complex(row["predicted_response_complex"])
        base_complex_u = float(row["complex_standard_uncertainty"])
        delay_complex_u = abs(corrected) * 2.0 * math.pi * abs(frequency_hz) * pipeline_delay_u_s
        combined_complex_u = math.sqrt(base_complex_u**2 + delay_complex_u**2)
        phase_u = combined_complex_u / max(abs(corrected), 1e-15)
        phase_residual = wrap_phase(np.angle(corrected) - np.angle(predicted))
        phase_threshold = max(math.radians(5.0), 3.0 * phase_u)
        row["measured_response_complex"] = corrected
        row["measured_phase_rad"] = float(np.angle(corrected))
        row["phase_residual_rad"] = phase_residual
        row["complex_standard_uncertainty"] = combined_complex_u
        row["phase_standard_uncertainty_rad"] = phase_u
        row["phase_acceptance_threshold_rad"] = phase_threshold
        row["phase_pass"] = abs(phase_residual) <= phase_threshold

    complex_rms = float(
        math.sqrt(
            np.mean(
                [
                    abs(
                        complex(row["measured_response_complex"])
                        - complex(row["predicted_response_complex"])
                    )
                    ** 2
                    for row in response_rows
                ]
            )
        )
    )
    fitted_tau_s, fitted_tau_u_s = fit_timeconstant(order, tau_s, response_rows)
    cutoff_factor = math.sqrt(2.0 ** (1.0 / order) - 1.0) / (2.0 * math.pi)
    predicted_cutoff_hz = cutoff_factor / tau_s
    fitted_cutoff_hz = cutoff_factor / fitted_tau_s
    fitted_cutoff_u_hz = cutoff_factor * fitted_tau_u_s / fitted_tau_s**2
    cutoff_relative_residual = (
        fitted_cutoff_hz - predicted_cutoff_hz
    ) / predicted_cutoff_hz
    cutoff_relative_u = fitted_cutoff_u_hz / predicted_cutoff_hz
    cutoff_threshold = max(0.10, 3.0 * cutoff_relative_u)

    step_results = analyze_step_transitions(
        timestamps,
        test_values,
        reference_values,
        segments,
        order,
        tau_s,
        reference_tau_s,
        rate_sps,
        pipeline_delay_s,
        pipeline_delay_u_s,
    )
    noise_results = analyze_zero_noise(timestamps, test_values, segments, order, tau_s)
    anchor_pass = (
        bool(integrity["pass"])
        and carrier_repeatability_pass
        and all(bool(row["magnitude_pass"]) for row in response_rows)
        and all(bool(row["phase_pass"]) for row in response_rows)
        and complex_rms <= 0.05
        and abs(cutoff_relative_residual) <= cutoff_threshold
        and bool(step_results["reference_edges_identified_pass"])
        and bool(step_results["settling_and_overshoot_pass"])
        and bool(step_results["group_delay_pass"])
        and bool(step_results["rising_falling_final_gain_pass"])
        and pipeline_delay_bound_pass
    )
    return {
        "name": name,
        "acquisition_id": status["acquisition_id"],
        "status_path": str(status_path),
        "raw_path": str(raw_path),
        "order_readback": order,
        "timeconstant_readback_s": tau_s,
        "reference_timeconstant_readback_s": reference_tau_s,
        "rate_readback_sps": rate_sps,
        "reference_connected_threshold_v": reference_connected_threshold,
        "reference_connected_run_count": len(nonzero_runs),
        "pipeline_delay": {
            "fitted_s": pipeline_delay_s,
            "standard_uncertainty_s": pipeline_delay_u_s,
            "one_sample_bound_s": sample_interval_s,
            "bound_pass": pipeline_delay_bound_pass,
            "interpretation": "constant paired-demodulator pipeline nuisance",
        },
        "complex_gain": gain,
        "complex_gain_standard_uncertainty": gain_u,
        "carrier_results": carrier_results,
        "carrier_repeatability_pass": carrier_repeatability_pass,
        "response_results": response_rows,
        "magnitude_pass": all(bool(row["magnitude_pass"]) for row in response_rows),
        "phase_pass": all(bool(row["phase_pass"]) for row in response_rows),
        "normalized_rms_complex_residual": complex_rms,
        "normalized_rms_complex_residual_pass": complex_rms <= 0.05,
        "fitted_timeconstant_s": fitted_tau_s,
        "fitted_timeconstant_standard_uncertainty_s": fitted_tau_u_s,
        "predicted_cutoff_hz_from_readback": predicted_cutoff_hz,
        "fitted_cutoff_hz": fitted_cutoff_hz,
        "fitted_cutoff_standard_uncertainty_hz": fitted_cutoff_u_hz,
        "cutoff_relative_residual": cutoff_relative_residual,
        "cutoff_acceptance_threshold": cutoff_threshold,
        "cutoff_pass": abs(cutoff_relative_residual) <= cutoff_threshold,
        "step_response": step_results,
        "zero_noise": noise_results,
        "integrity": integrity,
        "anchor_pass": anchor_pass,
    }


def json_safe(value: Any) -> Any:
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def intermediate_sign_pair(result: dict[str, Any]) -> dict[str, Any]:
    rows = result["response_results"]
    positive = min(
        (row for row in rows if float(row["commanded_offset_hz"]) > 0),
        key=lambda row: abs(float(row["commanded_offset_hz"]) - 69.2),
    )
    negative = next(row for row in rows if float(row["commanded_offset_hz"]) < 0)
    magnitude_difference = abs(
        float(positive["measured_normalized_magnitude"])
        - float(negative["measured_normalized_magnitude"])
    ) / (
        0.5
        * (
            float(positive["measured_normalized_magnitude"])
            + float(negative["measured_normalized_magnitude"])
        )
    )
    magnitude_u = math.sqrt(
        float(positive["complex_standard_uncertainty"]) ** 2
        + float(negative["complex_standard_uncertainty"]) ** 2
    ) / max(
        0.5
        * (
            float(positive["measured_normalized_magnitude"])
            + float(negative["measured_normalized_magnitude"])
        ),
        1e-15,
    )
    phase_sum = wrap_phase(
        float(positive["measured_phase_rad"]) + float(negative["measured_phase_rad"])
    )
    phase_u = math.sqrt(
        float(positive["phase_standard_uncertainty_rad"]) ** 2
        + float(negative["phase_standard_uncertainty_rad"]) ** 2
    )
    magnitude_threshold = max(0.05, 3.0 * magnitude_u)
    phase_threshold = max(math.radians(5.0), 3.0 * phase_u)
    return {
        "positive_label": positive["label"],
        "negative_label": negative["label"],
        "magnitude_fractional_difference": magnitude_difference,
        "magnitude_standard_uncertainty": magnitude_u,
        "magnitude_acceptance_threshold": magnitude_threshold,
        "magnitude_pass": magnitude_difference <= magnitude_threshold,
        "phase_sum_rad": phase_sum,
        "phase_standard_uncertainty_rad": phase_u,
        "phase_acceptance_threshold_rad": phase_threshold,
        "phase_sign_reversal_pass": abs(phase_sum) <= phase_threshold,
        "pass": magnitude_difference <= magnitude_threshold
        and abs(phase_sum) <= phase_threshold,
    }


def write_outputs(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_name = {str(row["name"]): row for row in results}
    sign_pair = intermediate_sign_pair(by_name["intermediate"])
    overall_pass = all(bool(row["anchor_pass"]) for row in results) and bool(
        sign_pair["pass"]
    )
    document = {
        "campaign_id": "system_recalibration_001",
        "phase_id": "HF-01",
        "analysis_id": "HF01-ANALYSIS-DUAL-DEMOD-MODEL-001",
        "criterion_version": CRITERION_VERSION,
        "plan_version": "HF01-PLAN-v3",
        "validation_design_version": "HF01-VALIDATION-DESIGN-v3",
        "method": (
            "Exact-timestamp complex ratio of HF2LI demodulator 0 to same-clock "
            "wideband demodulator 1, with explicit reference-filter correction"
        ),
        "anchors": results,
        "intermediate_positive_negative_pair": sign_pair,
        "primary_anchor_pass_count": sum(bool(row["anchor_pass"]) for row in results),
        "primary_anchor_required_count": 3,
        "overall_status": "PASS" if overall_pass else "FAIL",
        "computational_selection_authorized": overall_pass,
    }
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    json_path = ANALYSIS / "hf01_dual_demod_model_validation_results.json"
    json_path.write_text(
        json.dumps(json_safe(document), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    csv_path = ANALYSIS / "hf01_dual_demod_model_residuals.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "anchor",
            "acquisition_id",
            "label",
            "commanded_offset_hz",
            "observed_frequency_hz",
            "measured_magnitude",
            "predicted_magnitude",
            "magnitude_residual",
            "magnitude_threshold",
            "magnitude_pass",
            "measured_phase_deg",
            "predicted_phase_deg",
            "phase_residual_deg",
            "phase_threshold_deg",
            "phase_pass",
            "complex_standard_uncertainty",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for anchor in results:
            for row in anchor["response_results"]:
                writer.writerow(
                    {
                        "anchor": anchor["name"],
                        "acquisition_id": anchor["acquisition_id"],
                        "label": row["label"],
                        "commanded_offset_hz": row["commanded_offset_hz"],
                        "observed_frequency_hz": row["observed_frequency_hz"],
                        "measured_magnitude": row["measured_normalized_magnitude"],
                        "predicted_magnitude": row["predicted_normalized_magnitude"],
                        "magnitude_residual": row["magnitude_residual"],
                        "magnitude_threshold": row["magnitude_acceptance_threshold"],
                        "magnitude_pass": row["magnitude_pass"],
                        "measured_phase_deg": math.degrees(row["measured_phase_rad"]),
                        "predicted_phase_deg": math.degrees(row["predicted_phase_rad"]),
                        "phase_residual_deg": math.degrees(row["phase_residual_rad"]),
                        "phase_threshold_deg": math.degrees(
                            row["phase_acceptance_threshold_rad"]
                        ),
                        "phase_pass": row["phase_pass"],
                        "complex_standard_uncertainty": row[
                            "complex_standard_uncertainty"
                        ],
                    }
                )

    report_path = ANALYSIS / "hf01_dual_demod_model_validation_report.md"
    lines = [
        "# HF-01 dual-demodulator model validation",
        "",
        f"Analysis: `HF01-ANALYSIS-DUAL-DEMOD-MODEL-001`  ",
        f"Criterion: `{CRITERION_VERSION}`  ",
        f"Overall status: **{document['overall_status']}**",
        "",
        "The analysis uses exact-timestamp complex division of demodulator 0 by",
        "demodulator 1. The demodulator 1 transfer function is explicitly restored",
        "to reconstruct the filter-under-test response.",
        "",
        "| Anchor | Integrity | Magnitude | Phase | Complex RMS | Cutoff | Steps | Group delay | Result |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        steps = row["step_response"]
        lines.append(
            "| {name} | {integrity} | {magnitude} | {phase} | {complex_rms} | "
            "{cutoff} | {steps} | {group} | {result} |".format(
                name=row["name"],
                integrity="PASS" if row["integrity"]["pass"] else "FAIL",
                magnitude="PASS" if row["magnitude_pass"] else "FAIL",
                phase="PASS" if row["phase_pass"] else "FAIL",
                complex_rms="PASS" if row["normalized_rms_complex_residual_pass"] else "FAIL",
                cutoff="PASS" if row["cutoff_pass"] else "FAIL",
                steps="PASS" if steps["settling_and_overshoot_pass"] else "FAIL",
                group="PASS" if steps["group_delay_pass"] else "FAIL",
                result="PASS" if row["anchor_pass"] else "FAIL",
            )
        )
    lines.extend(
        [
            "",
            "The intermediate positive/negative pair is **{}**. Computational".format(
                "PASS" if sign_pair["pass"] else "FAIL"
            ),
            "selection is {} under the frozen phase plan.".format(
                "authorized" if overall_pass else "not authorized"
            ),
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "document": document,
        "json_path": str(json_path),
        "csv_path": str(csv_path),
        "report_path": str(report_path),
    }


def main() -> int:
    results = [analyze_anchor(name, config) for name, config in ANCHORS.items()]
    output = write_outputs(results)
    print(json.dumps(json_safe(output), indent=2, sort_keys=True))
    return 0 if output["document"]["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
