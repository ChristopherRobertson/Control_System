"""Analyze HF-01 selected-setting, rate-boundary, and channel checks."""

from __future__ import annotations

import csv
import cmath
import json
import math
from pathlib import Path
from typing import Any

from analyze_dual_demod_validation import analyze_anchor, json_safe


HERE = Path(__file__).resolve().parent
ANALYSIS = HERE / "analysis"
RESULT = ANALYSIS / "hf01_selected_confirmation_results.json"
TABLE = ANALYSIS / "hf01_selected_confirmation_summary.csv"
REPORT = ANALYSIS / "hf01_selected_confirmation_report.md"
ANALYSIS_ID = "HF01-ANALYSIS-SELECTED-CONFIRMATION-001"

CONFIGS: dict[str, dict[str, Any]] = {
    "sweep_hrp_in1": {
        "stem": "hf01_selected_sweep_hrp_in1_001",
        "acquisition_id": "HF01-SELECTED-SWEEP-HRP-IN1-001",
        "retained_fraction": 0.5,
        "test_demod_index": 0,
        "reference_demod_index": 1,
    },
    "sweep_hrp_lower_in1": {
        "stem": "hf01_lower_sweep_hrp_in1_001",
        "acquisition_id": "HF01-LOWER-SWEEP-HRP-IN1-001",
        "retained_fraction": 0.5,
        "test_demod_index": 0,
        "reference_demod_index": 1,
    },
    "mbco_in1": {
        "stem": "hf01_selected_mbco_in1_001",
        "acquisition_id": "HF01-SELECTED-MBCO-IN1-001",
        "retained_fraction": 0.5,
        "test_demod_index": 0,
        "reference_demod_index": 1,
    },
    "mbco_lower_in1": {
        "stem": "hf01_lower_mbco_in1_001",
        "acquisition_id": "HF01-LOWER-MBCO-IN1-001",
        "retained_fraction": 0.5,
        "test_demod_index": 0,
        "reference_demod_index": 1,
    },
    "sweep_hrp_in2": {
        "stem": "hf01_selected_sweep_hrp_in2_001",
        "acquisition_id": "HF01-SELECTED-SWEEP-HRP-IN2-001",
        "retained_fraction": 0.5,
        "test_demod_index": 3,
        "reference_demod_index": 4,
    },
    "mbco_in2": {
        "stem": "hf01_selected_mbco_in2_001",
        "acquisition_id": "HF01-SELECTED-MBCO-IN2-001",
        "retained_fraction": 0.5,
        "test_demod_index": 3,
        "reference_demod_index": 4,
    },
    "range_low_in2": {
        "stem": "hf01_range_low_in2_001",
        "acquisition_id": "HF01-RANGE-LOW-IN2-001",
        "retained_fraction": 0.5,
        "test_demod_index": 3,
        "reference_demod_index": 4,
    },
    "range_high_in2": {
        "stem": "hf01_range_high_in2_001",
        "acquisition_id": "HF01-RANGE-HIGH-IN2-001",
        "retained_fraction": 0.5,
        "test_demod_index": 3,
        "reference_demod_index": 4,
    },
}


def available_configs() -> dict[str, dict[str, Any]]:
    return {
        name: config
        for name, config in CONFIGS.items()
        if (HERE / "raw" / f"{config['stem']}_status.json").exists()
        and (HERE / "raw" / f"{config['stem']}_hf2_raw.csv").exists()
    }


def rate_guard(row: dict[str, Any]) -> dict[str, Any]:
    ratio = float(row["rate_readback_sps"]) / float(row["predicted_cutoff_hz_from_readback"])
    return {"rate_to_cutoff_ratio": ratio, "minimum_ratio": 8.0, "pass": ratio >= 8.0}


def channel_equivalence(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    gain1 = complex(first["complex_gain"])
    gain2 = complex(second["complex_gain"])
    gain_difference = abs(abs(gain2 / gain1) - 1.0)
    raw_phase_difference = cmath.phase(gain2 / gain1)
    phase_difference = abs(
        math.atan2(math.sin(raw_phase_difference), math.cos(raw_phase_difference))
    )
    cutoff_difference = abs(
        float(second["fitted_cutoff_hz"]) / float(first["fitted_cutoff_hz"]) - 1.0
    )
    settle1 = float(first["step_response"]["predicted_1_to_99_s"])
    observed1 = [
        float(row["observed_1_to_99_s"])
        for row in first["step_response"]["transitions"]
        if row.get("observed_1_to_99_s") is not None
    ]
    observed2 = [
        float(row["observed_1_to_99_s"])
        for row in second["step_response"]["transitions"]
        if row.get("observed_1_to_99_s") is not None
    ]
    settle_difference = (
        abs(float(sum(observed2) / len(observed2)) / float(sum(observed1) / len(observed1)) - 1.0)
        if observed1 and observed2
        else float("inf")
    )
    noise1 = float(first["zero_noise"]["windows"][0]["complex_rms_v"])
    noise2 = float(second["zero_noise"]["windows"][0]["complex_rms_v"])
    noise_difference = abs(noise2 / noise1 - 1.0) if noise1 else float("inf")
    gain_pass = gain_difference <= 0.03
    phase_pass = phase_difference <= math.radians(5.0)
    cutoff_pass = cutoff_difference <= 0.05
    settling_pass = settle_difference <= 0.05
    noise_pass = noise_difference <= 0.20
    integrity_pass = bool(first["integrity"]["pass"] and second["integrity"]["pass"])
    return {
        "input1_acquisition_id": first["acquisition_id"],
        "input2_acquisition_id": second["acquisition_id"],
        "gain_fractional_difference": gain_difference,
        "gain_limit": 0.03,
        "gain_pass": gain_pass,
        "phase_difference_rad": phase_difference,
        "phase_limit_rad": math.radians(5.0),
        "phase_pass": phase_pass,
        "cutoff_fractional_difference": cutoff_difference,
        "cutoff_limit": 0.05,
        "cutoff_pass": cutoff_pass,
        "settling_fractional_difference": settle_difference,
        "settling_limit": 0.05,
        "settling_pass": settling_pass,
        "zero_noise_fractional_difference": noise_difference,
        "zero_noise_limit": 0.20,
        "zero_noise_pass": noise_pass,
        "no_clipping_or_loss_pass": integrity_pass,
        "pass": gain_pass and phase_pass and cutoff_pass and settling_pass and noise_pass and integrity_pass,
    }


def main() -> int:
    configs = available_configs()
    results = {name: analyze_anchor(name, config) for name, config in configs.items()}
    guards = {name: rate_guard(row) for name, row in results.items()}
    rate_decisions: dict[str, dict[str, Any]] = {}
    for case, selected_name, lower_name in (
        ("sweep_hrp", "sweep_hrp_in1", "sweep_hrp_lower_in1"),
        ("mbco", "mbco_in1", "mbco_lower_in1"),
    ):
        if selected_name in results and lower_name in results:
            rate_decisions[case] = {
                "selected_acquisition_id": results[selected_name]["acquisition_id"],
                "lower_acquisition_id": results[lower_name]["acquisition_id"],
                "selected_confirmation_pass": bool(results[selected_name]["anchor_pass"]),
                "selected_rate_guard": guards[selected_name],
                "lower_electrical_model_pass": bool(results[lower_name]["anchor_pass"]),
                "lower_rate_guard": guards[lower_name],
                "decision": "RETAIN_SELECTED_RATE" if guards[selected_name]["pass"] and not guards[lower_name]["pass"] else "REVIEW",
            }

    equivalence: dict[str, Any] = {}
    if "sweep_hrp_in1" in results and "sweep_hrp_in2" in results:
        equivalence["sweep_hrp"] = channel_equivalence(results["sweep_hrp_in1"], results["sweep_hrp_in2"])
    if "mbco_in1" in results and "mbco_in2" in results:
        equivalence["mbco"] = channel_equivalence(results["mbco_in1"], results["mbco_in2"])

    range_endpoint: dict[str, Any] = {}
    if "range_low_in2" in results and "range_high_in2" in results:
        low = results["range_low_in2"]
        high = results["range_high_in2"]
        low_vpp = sum(float(row["input_vpp"]) for row in low["carrier_results"]) / 3.0
        high_vpp = sum(float(row["input_vpp"]) for row in high["carrier_results"]) / 3.0
        ratio_error = abs((high_vpp / low_vpp) / 10.0 - 1.0)
        gain_ratio = complex(high["complex_gain"]) / complex(low["complex_gain"])
        gain_difference = abs(abs(gain_ratio) - 1.0)
        phase_difference = abs(cmath.phase(gain_ratio))
        range_endpoint = {
            "low_acquisition_id": low["acquisition_id"],
            "high_acquisition_id": high["acquisition_id"],
            "low_measured_connected_vpp": low_vpp,
            "high_measured_connected_vpp": high_vpp,
            "measured_ratio": high_vpp / low_vpp,
            "ratio_fractional_error_from_10x": ratio_error,
            "ratio_limit": 0.03,
            "normalized_gain_fractional_difference": gain_difference,
            "gain_limit": 0.03,
            "phase_difference_rad": phase_difference,
            "phase_limit_rad": math.radians(5.0),
            "no_clipping_or_loss_pass": bool(low["integrity"]["pass"] and high["integrity"]["pass"]),
            "pass": bool(
                low["anchor_pass"]
                and high["anchor_pass"]
                and ratio_error <= 0.03
                and gain_difference <= 0.03
                and phase_difference <= math.radians(5.0)
                and low["integrity"]["pass"]
                and high["integrity"]["pass"]
            ),
        }

    complete = all(name in results for name in CONFIGS)
    selected_pass = all(
        bool(results[name]["anchor_pass"])
        for name in ("sweep_hrp_in1", "mbco_in1")
        if name in results
    )
    rate_pass = len(rate_decisions) == 2 and all(
        row["decision"] == "RETAIN_SELECTED_RATE" for row in rate_decisions.values()
    )
    equivalence_pass = len(equivalence) == 2 and all(row["pass"] for row in equivalence.values())
    range_pass = bool(range_endpoint.get("pass"))
    document = {
        "analysis_id": ANALYSIS_ID,
        "status": "PASS" if complete and selected_pass and rate_pass and equivalence_pass and range_pass else "PARTIAL" if not complete and selected_pass and rate_pass else "FAIL",
        "complete": complete,
        "confirmation_results": results,
        "rate_guards": guards,
        "rate_decisions": rate_decisions,
        "channel_equivalence": equivalence,
        "signal_input_2_range_endpoints": range_endpoint,
        "mbco_feature_limit_unchanged": "physical confirmation validates the selected electrical boundary but does not make the mandatory 1 us feature claimable",
    }
    RESULT.write_text(json.dumps(json_safe(document), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with TABLE.open("w", newline="", encoding="utf-8") as handle:
        fields = ["name", "acquisition_id", "order", "timeconstant_s", "rate_sps", "rate_to_cutoff", "model_confirmation_pass", "clip_loss_clock_integrity_pass"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for name, row in results.items():
            writer.writerow({
                "name": name,
                "acquisition_id": row["acquisition_id"],
                "order": row["order_readback"],
                "timeconstant_s": row["timeconstant_readback_s"],
                "rate_sps": row["rate_readback_sps"],
                "rate_to_cutoff": guards[name]["rate_to_cutoff_ratio"],
                "model_confirmation_pass": row["anchor_pass"],
                "clip_loss_clock_integrity_pass": row["integrity"]["pass"],
            })

    lines = [
        "# HF-01 selected-setting confirmation",
        "",
        f"Analysis ID: `{ANALYSIS_ID}`  ",
        f"Status: **{document['status']}**",
        "",
    ]
    for case, row in rate_decisions.items():
        lines.append(
            f"- {case}: selected rate/cutoff = {row['selected_rate_guard']['rate_to_cutoff_ratio']:.3f}; immediately lower = {row['lower_rate_guard']['rate_to_cutoff_ratio']:.3f}; decision `{row['decision']}`."
        )
    if not equivalence:
        lines.extend(["", "Signal Input 2 equivalence remains pending the single operator-led stimulus exchange."])
    else:
        lines.append("")
        for case, row in equivalence.items():
            lines.append(f"- {case} Signal Input 2 equivalence: {'PASS' if row['pass'] else 'FAIL'}.")
    if range_endpoint:
        lines.append(
            f"- Signal Input 2 range endpoints: {'PASS' if range_endpoint['pass'] else 'FAIL'}; measured {range_endpoint['low_measured_connected_vpp']:.6g} and {range_endpoint['high_measured_connected_vpp']:.6g} Vpp."
        )
    lines.extend(["", "The MbCO electrical boundary result does not remove the analytical 1 us limitation.", ""])
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(json_safe(document), indent=2, sort_keys=True))
    return 0 if document["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
