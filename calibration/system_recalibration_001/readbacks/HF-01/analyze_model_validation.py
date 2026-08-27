"""Apply the frozen HF-01 magnitude residual criterion to retained acquisitions."""

from array import array
import csv
import json
import math
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
ANALYSIS = HERE / "analysis"
CLOCKBASE_HZ = 210_000_000.0

RETAINED = {
    "fast": {
        "stem": "hf01_anchor_fast_r2_001",
        "retained_fraction": 0.5,
        "role": "primary_anchor",
    },
    "intermediate": {
        "stem": "hf01_anchor_intermediate_r1_001",
        "retained_fraction": 0.5,
        "role": "primary_anchor",
    },
    "slow": {
        "stem": "hf01_anchor_slow_r3_001",
        "retained_fraction": 0.8,
        "role": "primary_anchor",
    },
    "targeted": {
        "stem": "hf01_target_highorder_001",
        "retained_fraction": 0.5,
        "role": "diagnostic_only_superseded_trigger",
    },
}


def response_magnitude(order: int, tau_s: float, frequency_hz: float) -> float:
    return float(
        (1.0 + (2.0 * math.pi * abs(frequency_hz) * tau_s) ** 2)
        ** (-order / 2.0)
    )


def load_complex(path: Path) -> tuple[np.ndarray, np.ndarray]:
    tx = array("q")
    ty = array("q")
    x = array("d")
    y = array("d")
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["path"].endswith(".x"):
                tx.append(int(row["timestamp"]))
                x.append(float(row["value"]))
            else:
                ty.append(int(row["timestamp"]))
                y.append(float(row["value"]))
    timestamps = np.frombuffer(tx, dtype=np.int64)
    timestamps_y = np.frombuffer(ty, dtype=np.int64)
    if not np.array_equal(timestamps, timestamps_y):
        raise RuntimeError(f"X/Y timestamp mismatch in {path}")
    return timestamps, np.frombuffer(x, dtype=np.float64) + 1j * np.frombuffer(
        y, dtype=np.float64
    )


def analyze_segment(
    timestamps: np.ndarray,
    values: np.ndarray,
    start_tick: int,
    end_tick: int,
    retained_fraction: float,
) -> dict[str, float | int]:
    indices = np.flatnonzero((timestamps >= start_tick) & (timestamps < end_tick))
    if len(indices) < 8:
        raise RuntimeError(f"Only {len(indices)} samples in retained segment")
    first = int(len(indices) * retained_fraction)
    indices = indices[first:]
    seconds = (timestamps[indices] - start_tick) / CLOCKBASE_HZ
    phase = np.unwrap(np.angle(values[indices]))
    slope, intercept = np.polyfit(seconds, phase, 1)
    phase_residual = phase - (slope * seconds + intercept)
    magnitudes = np.abs(values[indices])
    return {
        "retained_samples": int(len(indices)),
        "observed_frequency_hz": float(slope / (2.0 * math.pi)),
        "phase_at_segment_start_rad": float(
            math.atan2(math.sin(intercept), math.cos(intercept))
        ),
        "phase_fit_rms_rad": float(np.sqrt(np.mean(phase_residual**2))),
        "output_magnitude_mean_v": float(np.mean(magnitudes)),
        "output_magnitude_std_v": float(np.std(magnitudes, ddof=1)),
    }


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


def smooth(values: np.ndarray, sample_rate_sps: float) -> np.ndarray:
    del sample_rate_sps
    window = min(3, max(1, len(values) // 10))
    if window <= 1:
        return values
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(values, kernel, mode="same")


def first_persistent_crossing(
    values: np.ndarray,
    *,
    threshold: float,
    direction: str,
    start_index: int = 0,
) -> int | None:
    hold = max(3, min(25, len(values) // 20))
    if direction == "above":
        condition = values >= threshold
    else:
        condition = values <= threshold
    for index in range(start_index, max(start_index, len(values) - hold + 1)):
        if bool(np.all(condition[index : index + hold])):
            return index
    return None


def analyze_steps(
    timestamps: np.ndarray,
    values: np.ndarray,
    segments: list[dict[str, object]],
    order: int,
    tau_s: float,
    rate_sps: float,
) -> dict[str, object]:
    predicted_1_s = step_crossing_time(order, tau_s, 0.01)
    predicted_99_s = step_crossing_time(order, tau_s, 0.99)
    predicted_1_to_99_s = predicted_99_s - predicted_1_s
    transitions = []
    steady_gains = []
    last_rise_steady: float | None = None
    for index, segment in enumerate(segments):
        label = str(segment["label"])
        if not (label.startswith("step_rise_") or label.startswith("step_fall_")):
            continue
        end_tick = (
            int(segments[index + 1]["device_tick_before"])
            if index + 1 < len(segments)
            else int(timestamps[-1])
        )
        selected = np.flatnonzero(
            (timestamps >= int(segment["device_tick_after"]))
            & (timestamps < end_tick)
        )
        if len(selected) < 12:
            transitions.append({"label": label, "status": "INSUFFICIENT_SAMPLES"})
            continue
        time_s = (timestamps[selected] - timestamps[selected][0]) / CLOCKBASE_HZ
        magnitude = np.abs(values[selected])
        filtered = smooth(magnitude, rate_sps)
        edge = max(2, len(filtered) // 20)
        filtered = filtered[edge:-edge]
        time_s = time_s[edge:-edge]
        if len(filtered) < 8:
            transitions.append({"label": label, "status": "INSUFFICIENT_SAMPLES"})
            continue
        if label.startswith("step_rise_"):
            steady = float(np.mean(filtered[-max(3, len(filtered) // 5) :]))
            normalized = filtered / steady
            crossing_1 = first_persistent_crossing(
                normalized, threshold=0.01, direction="above"
            )
            crossing_99 = (
                first_persistent_crossing(
                    normalized,
                    threshold=0.99,
                    direction="above",
                    start_index=crossing_1 or 0,
                )
                if crossing_1 is not None
                else None
            )
            overshoot = max(0.0, float(np.max(normalized)) - 1.0)
            steady_gains.append(steady)
            last_rise_steady = steady
        else:
            steady = (
                last_rise_steady
                if last_rise_steady is not None
                else float(np.max(filtered))
            )
            normalized = filtered / steady
            crossing_1 = first_persistent_crossing(
                normalized, threshold=0.99, direction="below"
            )
            crossing_99 = (
                first_persistent_crossing(
                    normalized,
                    threshold=0.01,
                    direction="below",
                    start_index=crossing_1 or 0,
                )
                if crossing_1 is not None
                else None
            )
            overshoot = max(0.0, float(np.max(normalized)) - 1.0)
        observed = (
            float(time_s[crossing_99] - time_s[crossing_1])
            if crossing_1 is not None and crossing_99 is not None
            else None
        )
        transitions.append(
            {
                "label": label,
                "status": "EVALUATED" if observed is not None else "NOT_RESOLVED",
                "observed_1_to_99_s": observed,
                "predicted_1_to_99_s": predicted_1_to_99_s,
                "settling_pass": (
                    observed <= 1.2 * predicted_1_to_99_s
                    if observed is not None
                    else None
                ),
                "absolute_overshoot": overshoot,
                "overshoot_pass": overshoot <= 0.05,
            }
        )
    evaluated = [row for row in transitions if row["status"] == "EVALUATED"]
    settling_pass = bool(evaluated) and all(
        bool(row["settling_pass"]) and bool(row["overshoot_pass"])
        for row in evaluated
    )
    gain_difference = (
        (max(steady_gains) - min(steady_gains)) / float(np.mean(steady_gains))
        if len(steady_gains) >= 2
        else None
    )
    return {
        "predicted_1_percent_s": predicted_1_s,
        "predicted_99_percent_s": predicted_99_s,
        "predicted_1_to_99_s": predicted_1_to_99_s,
        "transitions": transitions,
        "evaluated_transition_count": len(evaluated),
        "settling_and_overshoot_pass": settling_pass,
        "rising_final_gain_fractional_span": gain_difference,
        "rising_falling_final_gain_pass": (
            gain_difference <= 0.05 if gain_difference is not None else None
        ),
    }


def analyze_zero_noise(
    timestamps: np.ndarray,
    values: np.ndarray,
    segments: list[dict[str, object]],
    scale: float,
    order: int,
    tau_s: float,
) -> dict[str, object]:
    windows = []
    for index, segment in enumerate(segments):
        if segment["kind"] != "zero":
            continue
        end_tick = (
            int(segments[index + 1]["device_tick_before"])
            if index + 1 < len(segments)
            else int(timestamps[-1])
        )
        selected = np.flatnonzero(
            (timestamps >= int(segment["device_tick_after"]))
            & (timestamps < end_tick)
        )
        if len(selected) < 8:
            continue
        selected = selected[len(selected) // 2 :]
        window = values[selected]
        windows.append(
            {
                "label": segment["label"],
                "samples": int(len(window)),
                "x_rms_v": float(np.std(window.real, ddof=1)),
                "y_rms_v": float(np.std(window.imag, ddof=1)),
                "complex_rms_v": float(
                    np.sqrt(np.var(window.real, ddof=1) + np.var(window.imag, ddof=1))
                ),
            }
        )
    enbw_hz = math.gamma(order - 0.5) / (
        4.0 * math.sqrt(math.pi) * math.gamma(order) * tau_s
    )
    median_complex_rms = float(np.median([row["complex_rms_v"] for row in windows]))
    return {
        "window_count": len(windows),
        "windows": windows,
        "manufacturer_enbw_hz": enbw_hz,
        "median_complex_output_rms_v": median_complex_rms,
        "equivalent_input_complex_rms_v": median_complex_rms / scale,
        "equivalent_input_noise_density_v_per_sqrt_hz": (
            median_complex_rms / scale / math.sqrt(enbw_hz)
        ),
    }


def analyze_acquisition(name: str, config: dict[str, object]) -> dict[str, object]:
    stem = str(config["stem"])
    status_path = RAW / f"{stem}_status.json"
    raw_path = RAW / f"{stem}_hf2_raw.csv"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    timestamps, values = load_complex(raw_path)
    retained_fraction = float(config["retained_fraction"])
    rows = []
    segments = status["segments"]
    for index, segment in enumerate(segments):
        if segment["kind"] not in {"carrier", "offset_carrier"}:
            continue
        end_tick = (
            int(segments[index + 1]["device_tick_before"])
            if index + 1 < len(segments)
            else int(timestamps[-1])
        )
        row = analyze_segment(
            timestamps,
            values,
            int(segment["device_tick_after"]),
            end_tick,
            retained_fraction,
        )
        row.update(
            {
                "label": segment["label"],
                "kind": segment["kind"],
                "commanded_offset_hz": float(segment.get("offset_hz", 0.0)),
                "input_vpp": float(segment["monitor"]["analysis"]["sine_fit_vpp"]),
                "input_fit_residual_rms_v": float(
                    segment["monitor"]["analysis"]["sine_fit_residual_rms_v"]
                ),
            }
        )
        rows.append(row)
    order = int(status["hf2li_staged"]["order"])
    tau_s = float(status["hf2li_staged"]["timeconstant_s"])
    scale_estimates = []
    for row in rows:
        if row["kind"] != "carrier":
            continue
        predicted = response_magnitude(order, tau_s, float(row["observed_frequency_hz"]))
        scale_estimate = float(row["output_magnitude_mean_v"]) / (
            0.5 * float(row["input_vpp"]) * predicted
        )
        row["predicted_normalized_magnitude"] = predicted
        row["scale_estimate_v_per_v_peak"] = scale_estimate
        scale_estimates.append(scale_estimate)
    scale = float(np.mean(scale_estimates))
    scale_sem = float(
        np.std(scale_estimates, ddof=1) / np.sqrt(len(scale_estimates))
    )
    carrier_scale_fractional_span = (
        (max(scale_estimates) - min(scale_estimates)) / scale
        if len(scale_estimates) >= 2
        else float("inf")
    )
    offset_results = []
    for row in rows:
        if row["kind"] != "offset_carrier":
            continue
        observed_frequency = float(row["observed_frequency_hz"])
        measured = float(row["output_magnitude_mean_v"]) / (
            0.5 * float(row["input_vpp"]) * scale
        )
        predicted = response_magnitude(order, tau_s, observed_frequency)
        output_u_rel = (
            float(row["output_magnitude_std_v"])
            / math.sqrt(int(row["retained_samples"]))
            / float(row["output_magnitude_mean_v"])
        )
        input_u_rel = (
            float(row["input_fit_residual_rms_v"])
            / math.sqrt(4000.0)
            / (0.5 * float(row["input_vpp"]))
        )
        scale_u_rel = scale_sem / scale
        standard_uncertainty = measured * math.sqrt(
            output_u_rel**2 + input_u_rel**2 + scale_u_rel**2
        )
        residual = measured - predicted
        threshold = max(0.05, 3.0 * standard_uncertainty)
        offset_results.append(
            {
                **row,
                "predicted_normalized_magnitude": predicted,
                "measured_normalized_magnitude": measured,
                "normalized_magnitude_residual": residual,
                "combined_standard_uncertainty": standard_uncertainty,
                "acceptance_threshold": threshold,
                "magnitude_pass": abs(residual) <= threshold,
            }
        )
    magnitude_pass = all(bool(row["magnitude_pass"]) for row in offset_results)
    candidates = np.geomspace(tau_s / 3.0, tau_s * 3.0, 4001)
    fit_errors = []
    for candidate in candidates:
        fit_errors.append(
            sum(
                (
                    float(row["measured_normalized_magnitude"])
                    - response_magnitude(
                        order,
                        float(candidate),
                        float(row["observed_frequency_hz"]),
                    )
                )
                ** 2
                for row in offset_results
            )
        )
    fitted_tau_s = float(candidates[int(np.argmin(fit_errors))])
    cutoff_factor = math.sqrt(2.0 ** (1.0 / order) - 1.0) / (2.0 * math.pi)
    predicted_cutoff_hz = cutoff_factor / tau_s
    fitted_cutoff_hz = cutoff_factor / fitted_tau_s
    cutoff_relative_residual = (fitted_cutoff_hz - predicted_cutoff_hz) / predicted_cutoff_hz
    magnitude_rms_residual = float(
        math.sqrt(
            sum(float(row["normalized_magnitude_residual"]) ** 2 for row in offset_results)
            / len(offset_results)
        )
    )
    step_results = analyze_steps(
        timestamps,
        values,
        segments,
        order,
        tau_s,
        float(status["hf2li_staged"]["rate_sps"]),
    )
    noise_results = analyze_zero_noise(
        timestamps, values, segments, scale, order, tau_s
    )
    return {
        "name": name,
        "role": config["role"],
        "acquisition_id": status["acquisition_id"],
        "status_path": str(status_path),
        "raw_path": str(raw_path),
        "order_readback": order,
        "timeconstant_readback_s": tau_s,
        "rate_readback_sps": float(status["hf2li_staged"]["rate_sps"]),
        "scale_v_per_v_peak": scale,
        "scale_standard_uncertainty": scale_sem,
        "carrier_scale_fractional_span": carrier_scale_fractional_span,
        "carrier_repeatability_pass": carrier_scale_fractional_span <= 0.05,
        "carrier_segments": [row for row in rows if row["kind"] == "carrier"],
        "offset_results": offset_results,
        "magnitude_pass": magnitude_pass,
        "normalized_rms_magnitude_residual": magnitude_rms_residual,
        "normalized_rms_magnitude_residual_pass": magnitude_rms_residual <= 0.05,
        "fitted_timeconstant_s": fitted_tau_s,
        "predicted_cutoff_hz_from_readback": predicted_cutoff_hz,
        "fitted_cutoff_hz": fitted_cutoff_hz,
        "cutoff_relative_residual": cutoff_relative_residual,
        "cutoff_pass": abs(cutoff_relative_residual) <= 0.10,
        "step_response": step_results,
        "zero_noise": noise_results,
        "phase_and_complex_response": {
            "status": "NOT_EVALUABLE_FROM_RECORDED_CLOCK_DOMAINS",
            "reason": (
                "The PicoScope input phase and HF2LI complex output were not "
                "timestamp-synchronized to a shared edge during the anchor records; "
                "the HF2LI status/time command brackets are quantized at about 65.5 ms, "
                "so per-frequency source phase and delay cannot be removed."
            ),
            "phase_residual_pass": None,
            "normalized_rms_complex_residual_pass": None,
            "group_delay_pass": None,
        },
        "integrity": {
            "acquisition_status": status["status"],
            "pll_locked": status["hf2li_after"]["pll_locked"],
            "adcclip": status["hf2li_after"]["adcclip"],
            "demodsampleloss": status["hf2li_after"]["demodsampleloss"],
            "master_clock_locked": (
                status["hf2li_after"]["external_clock"] == 1
                and status["hf2li_after"]["pll_lock_flag"] == 0
                and status["hf2li_after"]["dcm_lock_flag"] == 0
            ),
            "final_safe_idle": status["t660_safe_idle_after"]["matches_recipe"],
        },
    }


def main() -> None:
    results = [analyze_acquisition(name, config) for name, config in RETAINED.items()]
    by_name = {str(row["name"]): row for row in results}
    primary_names = ("fast", "intermediate", "slow")
    magnitude_passing = [
        name
        for name in primary_names
        if bool(by_name[name]["magnitude_pass"])
        and bool(by_name[name]["normalized_rms_magnitude_residual_pass"])
        and bool(by_name[name]["cutoff_pass"])
        and bool(by_name[name]["carrier_repeatability_pass"])
    ]
    positive = next(
        row
        for row in by_name["intermediate"]["offset_results"]
        if float(row["commanded_offset_hz"]) > 0
        and abs(float(row["commanded_offset_hz"]) - 69.2) < 1.0
    )
    negative = next(
        row
        for row in by_name["intermediate"]["offset_results"]
        if float(row["commanded_offset_hz"]) < 0
    )
    sign_pair_magnitude_difference = abs(
        float(positive["measured_normalized_magnitude"])
        - float(negative["measured_normalized_magnitude"])
    ) / (
        0.5
        * (
            float(positive["measured_normalized_magnitude"])
            + float(negative["measured_normalized_magnitude"])
        )
    )
    unevaluable_metrics = [
        "per-frequency phase residual",
        "normalized RMS complex residual",
        "group delay",
        "intermediate positive/negative phase-sign reversal",
    ]
    overall = {
        "analysis_id": "HF01-ANALYSIS-MODEL-VALIDATION-001",
        "criterion_version": "HF01-MODEL-RESIDUAL-v1",
        "manufacturer_model": "H_n(f) = [1 + i 2 pi f tau]^-n",
        "primary_anchor_acquisitions": [
            by_name[name]["acquisition_id"] for name in primary_names
        ],
        "diagnostic_only_acquisition": by_name["targeted"]["acquisition_id"],
        "results": results,
        "magnitude_passing_primary_regions": magnitude_passing,
        "all_primary_magnitude_and_repeatability_metrics_pass": len(magnitude_passing) == 3,
        "fast_anchor_integrity_disposition": (
            "REJECT_ACQUISITION: step_rise_1 carrier scale is inconsistent with "
            "step_rise_2 and step_rise_3, so the fast magnitude/cutoff residuals "
            "cannot be interpreted as a manufacturer-model rejection."
        ),
        "intermediate_sign_pair": {
            "fractional_magnitude_difference": sign_pair_magnitude_difference,
            "magnitude_symmetry_pass": sign_pair_magnitude_difference <= 0.05,
            "phase_sign_reversal_pass": None,
        },
        "slow_anchor_configuration_disposition": {
            "requested_timeconstant_s": 0.1,
            "installed_readback_timeconstant_s": by_name["slow"]["timeconstant_readback_s"],
            "nearest_supported_write_diagnostic": "HF01-HF2-TC-MAP-DIAG-001",
            "analysis_basis": "installed node readback",
        },
        "targeted_point_disposition": (
            "DIAGNOSTIC_ONLY; the apparent slow-anchor magnitude failure that invoked "
            "this point was caused by comparing data to the requested 100 ms value "
            "instead of the installed 71.153 ms readback."
        ),
        "unevaluable_frozen_metrics": unevaluable_metrics,
        "overall_model_verdict": "NOT_VALIDATED",
        "stopping_rule": (
            "The frozen criterion requires every phase and complex-response metric to "
            "pass. Those metrics are not identifiable from the recorded unsynchronized "
            "PicoScope/HF2LI phase domains, and the single targeted point does not fix "
            "that acquisition-design limitation."
        ),
        "downstream_disposition": (
            "STOP_FOR_PROSPECTIVE_HF01_AMENDMENT; do not compute or select experiment "
            "configurations from the unvalidated model"
        ),
    }
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    json_path = ANALYSIS / "hf01_model_validation_results.json"
    json_path.write_text(json.dumps(overall, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    csv_path = ANALYSIS / "hf01_model_validation_magnitude_residuals.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "acquisition_id", "region", "order", "timeconstant_s", "rate_sps",
            "label", "commanded_offset_hz", "observed_frequency_hz",
            "measured_normalized_magnitude", "predicted_normalized_magnitude",
            "normalized_magnitude_residual", "combined_standard_uncertainty",
            "acceptance_threshold", "magnitude_pass",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            for row in result["offset_results"]:
                writer.writerow(
                    {
                        "acquisition_id": result["acquisition_id"],
                        "region": result["name"],
                        "order": result["order_readback"],
                        "timeconstant_s": result["timeconstant_readback_s"],
                        "rate_sps": result["rate_readback_sps"],
                        **{key: row[key] for key in fieldnames if key in row},
                    }
                )
    print(json.dumps(overall, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
