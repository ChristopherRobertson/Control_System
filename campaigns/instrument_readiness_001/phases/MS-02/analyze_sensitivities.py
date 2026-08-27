"""Offline MS-02 sensitivity and pulse-fidelity analysis of MS-01 raw traces."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import statistics
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.workflows.timing_calibration_procedure import (  # noqa: E402
    derive_measurement_system_corrections,
)
from control_app.workflows.timing_trace_analysis import analyze_pico_trace  # noqa: E402


HERE = Path(__file__).resolve().parent
MS01 = HERE.parent / "MS-01"
THRESHOLDS = (3000, 4000, 5000, 6000, 7000)
SAMPLE_INTERVAL_NS = 2.0


def accepted_paths(orientation: str) -> list[Path]:
    table = MS01 / orientation / "capture_attempts.csv"
    paths: list[Path] = []
    with table.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["status"] == "ACCEPTED":
                paths.append(Path(row["raw_path"]))
    if len(paths) != 100:
        raise RuntimeError(f"{orientation}: expected 100 accepted paths, got {len(paths)}")
    return paths


def samples(path: Path) -> tuple[list[int], list[int]]:
    a: list[int] = []
    b: list[int] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            a.append(int(row["ch_a_adc"]))
            b.append(int(row["ch_b_adc"]))
    return a, b


def crossing(values: list[int], level: float, rising: bool) -> float:
    for index in range(1, len(values)):
        previous, current = values[index - 1], values[index]
        crossed = previous < level <= current if rising else previous > level >= current
        if crossed:
            span = current - previous
            return float(index) if span == 0 else (index - 1) + (level - previous) / span
    raise RuntimeError(f"no {'rising' if rising else 'falling'} crossing at {level}")


def pulse_metrics(values: list[int]) -> dict:
    baseline = statistics.median(values[:500])
    peak = max(values)
    amplitude = peak - baseline
    if amplitude <= 0:
        raise RuntimeError("non-positive pulse amplitude")
    p10 = baseline + 0.1 * amplitude
    p50 = baseline + 0.5 * amplitude
    p90 = baseline + 0.9 * amplitude
    rise10 = crossing(values, p10, True)
    rise50 = crossing(values, p50, True)
    rise90 = crossing(values, p90, True)
    fall50 = crossing(values[int(rise90) + 1 :], p50, False) + int(rise90) + 1
    return {
        "baseline_adc": baseline,
        "peak_adc": peak,
        "amplitude_adc": amplitude,
        "rise_10_90_ns": (rise90 - rise10) * SAMPLE_INTERVAL_NS,
        "width_50_percent_ns": (fall50 - rise50) * SAMPLE_INTERVAL_NS,
    }


def summarize(values: list[float]) -> dict:
    return {
        "mean": statistics.fmean(values),
        "sample_standard_deviation": statistics.stdev(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def main() -> int:
    normal_paths = accepted_paths("normal")
    swapped_paths = accepted_paths("swapped")
    threshold_results: dict[str, dict] = {}
    interpolation_rows: list[dict] = []
    fidelity: dict[str, dict[str, list[float]]] = {
        key: {metric: [] for metric in ("baseline_adc", "peak_adc", "amplitude_adc", "rise_10_90_ns", "width_50_percent_ns")}
        for key in ("normal_A", "normal_B", "swapped_A", "swapped_B")
    }

    for threshold in THRESHOLDS:
        rows: list[dict] = []
        for orientation, measurement_id, paths in (
            ("normal", "MS-00A", normal_paths),
            ("swapped", "MS-00B", swapped_paths),
        ):
            for path in paths:
                result = analyze_pico_trace(
                    path,
                    sample_interval_ns=SAMPLE_INTERVAL_NS,
                    threshold_adc=threshold,
                )
                rows.append(
                    {
                        "measurement_id": measurement_id,
                        "measured_separation_ns": result["measured_separation_ns"],
                        "sample_interval_ns": SAMPLE_INTERVAL_NS,
                    }
                )
                if threshold == 5000:
                    nearest = (
                        round(result["target_edge_sample"])
                        - round(result["reference_edge_sample"])
                    ) * SAMPLE_INTERVAL_NS
                    interpolation_rows.append(
                        {
                            "measurement_id": measurement_id,
                            "linear_ns": result["measured_separation_ns"],
                            "nearest_sample_ns": nearest,
                        }
                    )
        correction = derive_measurement_system_corrections(rows)
        threshold_results[str(threshold)] = {
            "normal_mean_b_minus_a_ns": correction["normal_mean_b_minus_a_ns"],
            "swapped_mean_b_minus_a_ns": correction["swapped_mean_b_minus_a_ns"],
            "scope_b_minus_a_ns": correction[
                "scope_channel_and_fixed_lead_b_minus_a_ns"
            ],
            "splitter_s2_minus_s1_ns": correction["splitter_branch_2_minus_1_ns"],
        }

    for orientation, paths in (("normal", normal_paths), ("swapped", swapped_paths)):
        for path in paths:
            a, b = samples(path)
            for channel, values in (("A", a), ("B", b)):
                metrics = pulse_metrics(values)
                bucket = fidelity[f"{orientation}_{channel}"]
                for name, value in metrics.items():
                    bucket[name].append(float(value))

    scope_by_threshold = [item["scope_b_minus_a_ns"] for item in threshold_results.values()]
    splitter_by_threshold = [item["splitter_s2_minus_s1_ns"] for item in threshold_results.values()]
    linear_rows = [
        {
            "measurement_id": row["measurement_id"],
            "measured_separation_ns": row["linear_ns"],
            "sample_interval_ns": SAMPLE_INTERVAL_NS,
        }
        for row in interpolation_rows
    ]
    nearest_rows = [
        {
            "measurement_id": row["measurement_id"],
            "measured_separation_ns": row["nearest_sample_ns"],
            "sample_interval_ns": SAMPLE_INTERVAL_NS,
        }
        for row in interpolation_rows
    ]
    linear = derive_measurement_system_corrections(linear_rows)
    nearest = derive_measurement_system_corrections(nearest_rows)
    result = {
        "status": "OFFLINE_ANALYSIS_PASS",
        "source": str(MS01),
        "thresholds_adc": list(THRESHOLDS),
        "trigger_threshold_adc": 5000,
        "sample_interval_ns": SAMPLE_INTERVAL_NS,
        "timebase": 1,
        "threshold_results": threshold_results,
        "threshold_sensitivity": {
            "scope_half_range_ns": (max(scope_by_threshold) - min(scope_by_threshold)) / 2,
            "splitter_half_range_ns": (
                max(splitter_by_threshold) - min(splitter_by_threshold)
            )
            / 2,
        },
        "interpolation_sensitivity": {
            "method_comparison": "linear threshold interpolation versus nearest sample",
            "linear_scope_b_minus_a_ns": linear[
                "scope_channel_and_fixed_lead_b_minus_a_ns"
            ],
            "nearest_scope_b_minus_a_ns": nearest[
                "scope_channel_and_fixed_lead_b_minus_a_ns"
            ],
            "scope_absolute_difference_ns": abs(
                linear["scope_channel_and_fixed_lead_b_minus_a_ns"]
                - nearest["scope_channel_and_fixed_lead_b_minus_a_ns"]
            ),
            "linear_splitter_s2_minus_s1_ns": linear[
                "splitter_branch_2_minus_1_ns"
            ],
            "nearest_splitter_s2_minus_s1_ns": nearest[
                "splitter_branch_2_minus_1_ns"
            ],
            "splitter_absolute_difference_ns": abs(
                linear["splitter_branch_2_minus_1_ns"]
                - nearest["splitter_branch_2_minus_1_ns"]
            ),
        },
        "pulse_fidelity": {
            key: {metric: summarize(values) for metric, values in metrics.items()}
            for key, metrics in fidelity.items()
        },
        "timebase_accuracy": {
            "data_sheet_bound_ppm": 2.0,
            "drift_ppm_per_year": 1.0,
            "calibration_age_status": "USER_INPUT_REQUIRED",
        },
        "remaining_required_hardware_evidence": [
            "controlled splitter disconnection/reconnection repeatability"
        ],
        "user_input_required": [
            "PicoScope calibration certificate and calibration age",
            "CLOCK-SPLITTER-01 manufacturer bandwidth/insertion-loss/impedance specifications",
        ],
    }
    (HERE / "offline_analysis.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
