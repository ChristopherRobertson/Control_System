"""Offline analysis for one T2-01 installed-route sweep."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import sys


REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.workflows.timing_calibration_procedure import fit_delay_sweep  # noqa: E402
from control_app.workflows.timing_trace_analysis import analyze_pico_trace  # noqa: E402


PHASE_DIR = Path(__file__).resolve().parent
DELAYS_NS = (0, 100, 1_000, 10_000, 100_000, 1_000_000)
THRESHOLDS = (3000, 4000, 5000, 6000, 7000)
SCOPE_CORRECTION_NS = 0.10994707329952519
SCOPE_CORRECTION_U_NS = 0.5817073941913165
ADC_FULL_SCALE = 32512.0
RANGE_V = 10.0
SETUPS = {
    "1": "setup_1_extref_to_daq",
    "2": "setup_2_extref_to_mircat",
    "3": "setup_3_extref_to_t6601",
}


def crossing(values: list[int], level: float, rising: bool, start: int = 1) -> float:
    for index in range(max(1, start), len(values)):
        previous, current = values[index - 1], values[index]
        crossed = previous < level <= current if rising else previous > level >= current
        if crossed:
            span = current - previous
            return float(index) if span == 0 else index - 1 + (level - previous) / span
    raise RuntimeError(f"no {'rising' if rising else 'falling'} crossing")


def samples(path: Path) -> tuple[list[int], list[int]]:
    a, b = [], []
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            a.append(int(row["ch_a_adc"]))
            b.append(int(row["ch_b_adc"]))
    return a, b


def pulse_metrics(values: list[int], interval_ns: float, pretrigger: int) -> dict:
    baseline = statistics.median(values[: max(100, min(pretrigger, 500))])
    peak = max(values)
    trough = min(values)
    positive = peak - baseline
    negative = baseline - trough
    if positive >= negative:
        polarity = "positive"
        amplitude = positive
        p10, p50, p90 = (baseline + fraction * amplitude for fraction in (0.1, 0.5, 0.9))
        e10 = crossing(values, p10, True)
        e50 = crossing(values, p50, True)
        e90 = crossing(values, p90, True)
        try:
            f50 = crossing(values, p50, False, int(e90) + 1)
        except RuntimeError:
            f50 = None
    else:
        polarity = "negative"
        amplitude = negative
        p10, p50, p90 = (baseline - fraction * amplitude for fraction in (0.1, 0.5, 0.9))
        e10 = crossing(values, p10, False)
        e50 = crossing(values, p50, False)
        e90 = crossing(values, p90, False)
        try:
            f50 = crossing(values, p50, True, int(e90) + 1)
        except RuntimeError:
            f50 = None
    return {
        "polarity": polarity,
        "amplitude_adc": amplitude,
        "amplitude_v": amplitude * RANGE_V / ADC_FULL_SCALE,
        "width_50_percent_ns": (
            (f50 - e50) * interval_ns if f50 is not None else None
        ),
        "rise_10_90_ns": (e90 - e10) * interval_ns,
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
    parser.add_argument("setup", choices=SETUPS)
    parser.add_argument("--directory-name", default="")
    args = parser.parse_args()
    directory = PHASE_DIR / (args.directory_name or SETUPS[args.setup])
    all_rows = []
    per_delay = []
    fidelity = {
        "A": {"amplitude_v": [], "width_50_percent_ns": [], "rise_10_90_ns": [], "polarity": []},
        "B": {"amplitude_v": [], "width_50_percent_ns": [], "rise_10_90_ns": [], "polarity": []},
    }
    threshold_means: dict[str, dict[str, float]] = {}
    interpolation_differences = []

    for delay_ns in DELAYS_NS:
        attempts = directory / f"capture_attempts_{delay_ns}ns.csv"
        accepted = []
        with attempts.open("r", newline="", encoding="utf-8") as handle:
            accepted = [row for row in csv.DictReader(handle) if row["status"] == "ACCEPTED"]
        if len(accepted) != 100:
            raise RuntimeError(f"{delay_ns} ns has {len(accepted)} accepted traces")
        threshold_values = {threshold: [] for threshold in THRESHOLDS}
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
                )
                threshold_values[threshold].append(measured["measured_separation_ns"])
                if threshold == 5000:
                    nominal.append(measured["measured_separation_ns"])
                    nearest = (
                        round(measured["target_edge_sample"])
                        - round(measured["reference_edge_sample"])
                    ) * interval
                    interpolation_differences.append(abs(nearest - measured["measured_separation_ns"]))
            a, b = samples(path)
            for channel, values in (("A", a), ("B", b)):
                metrics = pulse_metrics(values, interval, int(row["pre_trigger_samples"]))
                for name in ("amplitude_v", "width_50_percent_ns", "rise_10_90_ns", "polarity"):
                    if metrics[name] is not None:
                        fidelity[channel][name].append(metrics[name])
        corrected = [value - SCOPE_CORRECTION_NS for value in nominal]
        point = {
            "programmed_delay_ns": delay_ns,
            "mean_raw_measured_ns": statistics.fmean(nominal),
            "mean_corrected_measured_ns": statistics.fmean(corrected),
            "mean_corrected_residual_ns": statistics.fmean(corrected) - delay_ns,
            "jitter_std_ns": statistics.stdev(corrected),
            "standard_error_ns": statistics.stdev(corrected) / math.sqrt(len(corrected)),
            "sample_interval_ns": float(accepted[0]["sample_interval_ns"]),
            "accepted": len(accepted),
        }
        per_delay.append(point)
        all_rows.extend(corrected)
        threshold_means[str(delay_ns)] = {
            str(threshold): statistics.fmean(values) - SCOPE_CORRECTION_NS
            for threshold, values in threshold_values.items()
        }

    fit = fit_delay_sweep(per_delay)
    residuals = {
        str(point["programmed_delay_ns"]): point["mean_corrected_measured_ns"]
        - (
            fit["fixed_offset_intercept_ns"]
            + fit["slope"] * point["programmed_delay_ns"]
        )
        for point in per_delay
    }
    threshold_half_ranges = [
        (max(values.values()) - min(values.values())) / 2
        for values in threshold_means.values()
    ]
    result = {
        "status": "PASS",
        "setup": args.setup,
        "sign_convention": "physical target arrival minus physical EXT REF arrival",
        "scope_correction": {
            "source": "MS-02 midpoint of two complete connection realizations",
            "chb_minus_cha_ns": SCOPE_CORRECTION_NS,
            "combined_standard_uncertainty_ns": SCOPE_CORRECTION_U_NS,
            "application": "corrected = raw CHB-minus-CHA - scope correction",
        },
        "per_delay": per_delay,
        "fit": fit,
        "fit_residuals_ns": residuals,
        "threshold_sensitivity": {
            "thresholds_adc": list(THRESHOLDS),
            "corrected_means_by_delay_ns": threshold_means,
            "maximum_half_range_ns": max(threshold_half_ranges),
        },
        "interpolation_sensitivity": {
            "comparison": "linear threshold interpolation versus nearest sample per trace",
            "absolute_difference_ns": summary(interpolation_differences),
        },
        "pulse_fidelity": {
            channel: {
                "polarity": sorted(set(metrics["polarity"])),
                "amplitude_v": summary(metrics["amplitude_v"]),
                "width_50_percent_ns": summary(metrics["width_50_percent_ns"]),
                "width_unavailable_trace_count": 600 - len(metrics["width_50_percent_ns"]),
                "rise_10_90_ns": summary(metrics["rise_10_90_ns"]),
            }
            for channel, metrics in fidelity.items()
        },
        "uncertainty_note": (
            "MS-02 scope correction uncertainty is recorded separately and is common to all "
            "points; fit_delay_sweep includes repeatability, sample-resolution, and 2 ppm timebase terms."
        ),
        "user_input_required": [
            "PicoScope calibration certificate and calibration age"
        ],
    }
    (directory / "analysis.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
