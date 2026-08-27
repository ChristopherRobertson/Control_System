"""Offline analysis for one T1-01 electrical sweep."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.workflows.timing_calibration_procedure import fit_delay_sweep  # noqa: E402
from control_app.workflows.timing_trace_analysis import analyze_pico_trace  # noqa: E402


HERE = Path(__file__).resolve().parent
DELAYS_NS = (0, 100, 1_000, 10_000, 100_000, 1_000_000)
THRESHOLDS = (3000, 4000, 5000, 6000, 7000)
SCOPE_CORRECTION_NS = 0.10994707329952519
SCOPE_CORRECTION_U_NS = 0.5817073941913165
ADC_FULL_SCALE = 32512.0
RANGE_V = 10.0
STEPS = {
    "4": ("setup_1_extref_to_fire", "rising", "falling", "positive", "negative"),
    "5": ("setup_2_fire_to_qswitch", "falling", "falling", "negative", "negative"),
    "6": ("setup_3_extref_to_qswitch", "rising", "falling", "positive", "negative"),
}


def crossing(values: list[int], level: float, edge: str, start: int = 1) -> float:
    for index in range(max(start, 1), len(values)):
        previous, current = values[index - 1], values[index]
        crossed = (
            previous < level <= current
            if edge == "rising"
            else previous > level >= current
        )
        if crossed:
            span = current - previous
            return float(index) if span == 0 else index - 1 + (level - previous) / span
    raise RuntimeError(f"no {edge} crossing")


def load_samples(path: Path) -> tuple[list[int], list[int]]:
    a, b = [], []
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            a.append(int(row["ch_a_adc"]))
            b.append(int(row["ch_b_adc"]))
    return a, b


def pulse_metrics(values: list[int], interval_ns: float, polarity: str) -> dict:
    baseline = statistics.median(values[:500])
    if polarity == "positive":
        amplitude = max(values) - baseline
        levels = [baseline + fraction * amplitude for fraction in (0.1, 0.5, 0.9)]
        e10 = crossing(values, levels[0], "rising")
        e50 = crossing(values, levels[1], "rising")
        e90 = crossing(values, levels[2], "rising")
        returned = crossing(values, levels[1], "falling", int(e90) + 1)
    else:
        amplitude = baseline - min(values)
        levels = [baseline - fraction * amplitude for fraction in (0.1, 0.5, 0.9)]
        e10 = crossing(values, levels[0], "falling")
        e50 = crossing(values, levels[1], "falling")
        e90 = crossing(values, levels[2], "falling")
        returned = crossing(values, levels[1], "rising", int(e90) + 1)
    return {
        "amplitude_v": amplitude * RANGE_V / ADC_FULL_SCALE,
        "width_50_percent_ns": (returned - e50) * interval_ns,
        "transition_10_90_ns": (e90 - e10) * interval_ns,
    }


def summary(values: list[float]) -> dict:
    return {
        "mean": statistics.fmean(values),
        "sample_standard_deviation": statistics.stdev(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=STEPS)
    parser.add_argument("--directory-name", default="")
    args = parser.parse_args()
    directory_name, ref_edge, target_edge, ref_polarity, target_polarity = STEPS[args.step]
    directory = HERE / (args.directory_name or directory_name)
    per_delay = []
    threshold_means = {}
    interpolation = []
    fidelity = {
        "A": {"amplitude_v": [], "width_50_percent_ns": [], "transition_10_90_ns": []},
        "B": {"amplitude_v": [], "width_50_percent_ns": [], "transition_10_90_ns": []},
    }

    for delay_ns in DELAYS_NS:
        with (directory / f"capture_attempts_{delay_ns}ns.csv").open(
            "r", newline="", encoding="utf-8"
        ) as handle:
            accepted = [row for row in csv.DictReader(handle) if row["status"] == "ACCEPTED"]
        if len(accepted) != 100:
            raise RuntimeError(f"{delay_ns} ns has {len(accepted)} accepted traces")
        by_threshold = {threshold: [] for threshold in THRESHOLDS}
        nominal = []
        for row in accepted:
            path = Path(row["raw_path"])
            interval = float(row["sample_interval_ns"])
            for threshold in THRESHOLDS:
                measured = analyze_pico_trace(
                    path,
                    sample_interval_ns=interval,
                    threshold_adc=threshold,
                    programmed_separation_ns=float(delay_ns),
                    reference_edge=ref_edge,
                    target_edge=target_edge,
                )
                by_threshold[threshold].append(measured["measured_separation_ns"])
                if threshold == 5000:
                    nominal.append(measured["measured_separation_ns"])
                    nearest = (
                        round(measured["target_edge_sample"])
                        - round(measured["reference_edge_sample"])
                    ) * interval
                    interpolation.append(abs(nearest - measured["measured_separation_ns"]))
            a, b = load_samples(path)
            for channel, values, polarity in (
                ("A", a, ref_polarity),
                ("B", b, target_polarity),
            ):
                metrics = pulse_metrics(values, interval, polarity)
                for name, value in metrics.items():
                    fidelity[channel][name].append(value)

        corrected = [value - SCOPE_CORRECTION_NS for value in nominal]
        sd = statistics.stdev(corrected)
        per_delay.append(
            {
                "programmed_delay_ns": delay_ns,
                "mean_raw_measured_ns": statistics.fmean(nominal),
                "mean_scope_corrected_measured_ns": statistics.fmean(corrected),
                "mean_corrected_measured_ns": statistics.fmean(corrected),
                "mean_scope_corrected_residual_ns": statistics.fmean(corrected) - delay_ns,
                "jitter_std_ns": sd,
                "standard_error_ns": sd / math.sqrt(len(corrected)),
                "sample_interval_ns": float(accepted[0]["sample_interval_ns"]),
                "accepted": len(accepted),
            }
        )
        threshold_means[str(delay_ns)] = {
            str(threshold): statistics.fmean(values) - SCOPE_CORRECTION_NS
            for threshold, values in by_threshold.items()
        }

    fit = fit_delay_sweep(per_delay)
    residuals = {
        str(point["programmed_delay_ns"]): point["mean_corrected_measured_ns"]
        - (fit["fixed_offset_intercept_ns"] + fit["slope"] * point["programmed_delay_ns"])
        for point in per_delay
    }
    half_ranges = [
        (max(values.values()) - min(values.values())) / 2
        for values in threshold_means.values()
    ]
    result = {
        "status": "PASS_PROVISIONAL_ADAPTER_CORRECTION_REQUIRED",
        "step": args.step,
        "scope_correction": {
            "chb_minus_cha_ns": SCOPE_CORRECTION_NS,
            "combined_standard_uncertainty_ns": SCOPE_CORRECTION_U_NS,
        },
        "measurement_adapter_correction": {
            "status": "USER_INPUT_REQUIRED_AND_HARDWARE_CHARACTERIZATION_REQUIRED",
            "applied_ns": None,
            "note": "No zero was assigned; fit is corrected for PicoScope path only.",
        },
        "fit_scope_corrected_provisional": fit,
        "fit_residuals_ns": residuals,
        "per_delay": per_delay,
        "threshold_sensitivity": {
            "thresholds_adc": list(THRESHOLDS),
            "maximum_half_range_ns": max(half_ranges),
            "scope_corrected_means_by_delay_ns": threshold_means,
        },
        "interpolation_sensitivity": {
            "comparison": "linear interpolation versus nearest sample",
            "absolute_difference_ns": summary(interpolation),
        },
        "pulse_fidelity": {
            "A": {
                "polarity": ref_polarity,
                **{name: summary(values) for name, values in fidelity["A"].items()},
            },
            "B": {
                "polarity": target_polarity,
                **{name: summary(values) for name, values in fidelity["B"].items()},
            },
        },
    }
    (directory / "analysis.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
