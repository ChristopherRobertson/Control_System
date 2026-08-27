"""Complete analytical HF-01 evaluation over the installed parameter domains."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from functools import lru_cache
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
RAW_SPACE = HERE / "raw" / "hf01_hf2_supported_parameter_space_001.json"
MODEL = HERE / "analysis" / "hf01_dual_demod_model_validation_results.json"
OUT_DIR = HERE / "analysis"
TABLE = OUT_DIR / "hf01_candidate_disposition.csv"
RESULT = OUT_DIR / "hf01_supported_configuration_analysis.json"
REPORT = OUT_DIR / "hf01_supported_configuration_report.md"
CONFIGS = HERE / "selected_configurations.json"

ANALYSIS_ID = "HF01-ANALYSIS-SUPPORTED-CONFIGURATIONS-001"
SETTLING_99 = {1: 4.6, 2: 6.6, 3: 8.4, 4: 10.0, 5: 11.6, 6: 13.1, 7: 14.6, 8: 16.0}
EXPECTED_SIGNAL_MIN_V = 0.2448
EXPECTED_SIGNAL_MAX_V = 0.4651
BYTES_PER_TIMESTAMPED_COMPLEX_SAMPLE = 32


def stamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def cutoff_factor(order: int) -> float:
    return math.sqrt(2 ** (1.0 / order) - 1.0) / (2.0 * math.pi)


def enbw_hz(order: int, tau_s: float) -> float:
    return math.gamma(order - 0.5) / (
        4.0 * math.sqrt(math.pi) * tau_s * math.gamma(order)
    )


def response(order: int, tau_s: float, characteristic_s: float) -> tuple[float, float]:
    """Magnitude and phase at angular frequency 1/characteristic_s."""
    ratio = tau_s / characteristic_s
    return (1.0 + ratio * ratio) ** (-order / 2.0), -order * math.atan(ratio)


def input_mode_name(row: dict[str, object]) -> str:
    return "_".join(
        (
            "AC" if int(row["ac"]) else "DC",
            "50OHM" if int(row["impedance_50ohm"]) else "HIGHZ",
            "DIFF" if int(row["differential"]) else "SINGLE",
        )
    )


def disposition(
    *,
    experiment: str,
    range_v: float,
    mode: dict[str, object],
    readout: dict[str, object],
    order: int,
    rate: float,
) -> tuple[str, str]:
    if not bool(readout["applicable"]):
        return "OUTSIDE_VALID_ENVELOPE", str(readout["reason"])
    if int(mode["differential"]):
        return "OUTSIDE_VALID_ENVELOPE", "installed detector and HF-01 stimulus use one coaxial + input; no - input source is present"
    if int(mode["impedance_50ohm"]):
        return "OUTSIDE_VALID_ENVELOPE", "50 ohm loading changes the previously observed high-impedance detector voltage and is not detector-qualified"
    if int(mode["ac"]):
        return "DOMINATED", "AC coupling adds a 1 kHz input high-pass and uncertainty without a retained-case benefit"
    if range_v < 2.0 * EXPECTED_SIGNAL_MAX_V:
        return "OUTSIDE_VALID_ENVELOPE", "range is below twice the largest prior detector output"
    if range_v > 1.2:
        return "DOMINATED", "larger range adds noise margin after the 1 V nominal range satisfies headroom"
    selected = {
        "sweep": (4, 899.4654605263158),
        "hrp": (4, 899.4654605263158),
        "mbco": (1, 230263.15789473685),
    }
    selected_order, selected_rate = selected[experiment]
    if order == selected_order and math.isclose(rate, selected_rate, rel_tol=1e-12):
        if experiment == "mbco":
            return "SELECTED_BOUNDARY_OUTSIDE_MANDATORY_FEATURE", "least-memory dual-channel setting with valid 8x bandwidth sampling; HF2LI still cannot preserve 1 us"
        return "SELECTED", "retained design knee; immediately lower installed rate violates the 8x bandwidth guard"
    return "PARETO_NOT_SELECTED", "analytical cell remains represented; its full time-constant interval trades monotonically lower noise for greater delay and memory"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    space = json.loads(RAW_SPACE.read_text(encoding="utf-8"))
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    if space.get("status") != "PASS":
        raise RuntimeError("installed supported-space readback did not pass")
    if model.get("overall_status") != "PASS" or not model.get("computational_selection_authorized"):
        raise RuntimeError("manufacturer model has not passed the v3 gate")

    anchor_by_name = {row["name"]: row for row in model["anchors"]}
    noise_densities = {
        row["name"]: row["zero_noise"]["windows"][0]["complex_rms_v"]
        / math.sqrt(row["zero_noise"]["manufacturer_enbw_hz"])
        for row in model["anchors"]
    }
    conservative_noise_density = max(noise_densities.values())
    min_tc = float(space["timeconstant_domain"]["minimum_readback_s"])
    max_tc = float(space["timeconstant_domain"]["maximum_readback_s"])
    rates = [float(value) for value in space["dual_channel_rate_ladder_sps"]]
    ranges = space["input_ranges"]
    modes = space["input_modes"]
    readouts = space["readout_modes"]

    experiments = {
        "sweep": {
            "configuration_id": "HF01-SWEEP-SELECTED-001",
            "duration_s": 30.0,
            "characteristic_s": 1.0 / 40.0,
            "proxy": "response coefficient for one cm-1 of scan travel at 40 cm-1/s; not a feature-width acceptance threshold",
            "selected_tau_s": 0.0010018887078828383,
        },
        "hrp": {
            "configuration_id": "HF01-HRP-SELECTED-001",
            "duration_s": 4.605,
            "characteristic_s": 1.0,
            "proxy": "representative one-second recovery timescale",
            "selected_tau_s": 0.0010018887078828383,
        },
        "mbco": {
            "configuration_id": "HF01-MBCO-SELECTED-001",
            "duration_s": 0.010,
            "characteristic_s": 1.0e-6,
            "proxy": "mandatory one-microsecond retained feature",
            "selected_tau_s": 5.600017467592051e-6,
        },
    }

    fields = [
        "candidate_id", "experiment", "configuration_id", "range_requested_v", "range_readback_v",
        "headroom_above_2x_prior_max_v", "input_mode", "readout_mode", "order", "rate_sps",
        "timeconstant_domain_min_s", "timeconstant_sampling_valid_min_s", "timeconstant_domain_max_s",
        "least_memory_evaluation_tau_s", "cutoff_hz", "rate_to_cutoff_ratio", "enbw_hz",
        "predicted_complex_noise_rms_v", "predicted_noise_fraction_of_prior_min_signal",
        "response_proxy_definition", "response_magnitude", "attenuation_fraction", "phase_rad",
        "low_frequency_group_delay_s", "settling_99_s", "sweep_peak_shift_cm1",
        "sweep_kernel_sigma_cm1", "sweep_native_spacing_cm1", "hrp_samples_per_100ms",
        "mbco_samples_per_1us", "two_channel_samples", "estimated_data_bytes",
        "estimated_throughput_bytes_s", "model_residual_fraction", "model_cutoff_residual_fraction",
        "combined_fractional_uncertainty_proxy", "total_error_proxy", "disposition", "reason",
    ]
    counts: dict[str, int] = {}
    selected_rows: list[dict[str, object]] = []
    row_number = 0
    with TABLE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for experiment, exp in experiments.items():
            for range_row in ranges:
                range_requested = float(range_row["requested_v"])
                range_readback = float(range_row["readback_v"])
                for mode in modes:
                    for readout in readouts:
                        for order in range(1, 9):
                            anchor = (
                                anchor_by_name["fast"]
                                if order == 1
                                else anchor_by_name["slow"]
                                if order >= 7
                                else anchor_by_name["intermediate"]
                            )
                            model_residual = float(anchor["normalized_rms_complex_residual"])
                            cutoff_residual = abs(float(anchor["cutoff_relative_residual"]))
                            for rate in rates:
                                row_number += 1
                                sampling_min = max(min_tc, 8.0 * cutoff_factor(order) / rate)
                                tau = min(sampling_min, max_tc)
                                status, reason = disposition(
                                    experiment=experiment,
                                    range_v=range_readback,
                                    mode=mode,
                                    readout=readout,
                                    order=order,
                                    rate=rate,
                                )
                                if status.startswith("SELECTED"):
                                    tau = float(exp["selected_tau_s"])
                                cutoff = cutoff_factor(order) / tau
                                bandwidth = enbw_hz(order, tau)
                                magnitude, phase = response(order, tau, float(exp["characteristic_s"]))
                                range_scale = range_readback / 0.10056357463684712
                                noise = conservative_noise_density * math.sqrt(bandwidth) * range_scale
                                noise_fraction = noise / EXPECTED_SIGNAL_MIN_V
                                uncertainty = math.sqrt(noise_fraction**2 + model_residual**2 + cutoff_residual**2)
                                bias = 1.0 - magnitude
                                total_error = bias * bias + noise_fraction * noise_fraction + model_residual * model_residual
                                duration = float(exp["duration_s"])
                                samples = 2.0 * rate * duration
                                out = {
                                    "candidate_id": f"HF01-CAND-{row_number:06d}",
                                    "experiment": experiment,
                                    "configuration_id": exp["configuration_id"],
                                    "range_requested_v": range_requested,
                                    "range_readback_v": range_readback,
                                    "headroom_above_2x_prior_max_v": range_readback - 2.0 * EXPECTED_SIGNAL_MAX_V,
                                    "input_mode": input_mode_name(mode),
                                    "readout_mode": readout["name"],
                                    "order": order,
                                    "rate_sps": rate,
                                    "timeconstant_domain_min_s": min_tc,
                                    "timeconstant_sampling_valid_min_s": sampling_min,
                                    "timeconstant_domain_max_s": max_tc,
                                    "least_memory_evaluation_tau_s": tau,
                                    "cutoff_hz": cutoff,
                                    "rate_to_cutoff_ratio": rate / cutoff,
                                    "enbw_hz": bandwidth,
                                    "predicted_complex_noise_rms_v": noise,
                                    "predicted_noise_fraction_of_prior_min_signal": noise_fraction,
                                    "response_proxy_definition": exp["proxy"],
                                    "response_magnitude": magnitude,
                                    "attenuation_fraction": bias,
                                    "phase_rad": phase,
                                    "low_frequency_group_delay_s": order * tau,
                                    "settling_99_s": SETTLING_99[order] * tau,
                                    "sweep_peak_shift_cm1": order * tau * 40.0,
                                    "sweep_kernel_sigma_cm1": math.sqrt(order) * tau * 40.0,
                                    "sweep_native_spacing_cm1": 40.0 / rate,
                                    "hrp_samples_per_100ms": rate * 0.1,
                                    "mbco_samples_per_1us": rate * 1.0e-6,
                                    "two_channel_samples": samples,
                                    "estimated_data_bytes": samples * BYTES_PER_TIMESTAMPED_COMPLEX_SAMPLE,
                                    "estimated_throughput_bytes_s": 2.0 * rate * BYTES_PER_TIMESTAMPED_COMPLEX_SAMPLE,
                                    "model_residual_fraction": model_residual,
                                    "model_cutoff_residual_fraction": cutoff_residual,
                                    "combined_fractional_uncertainty_proxy": uncertainty,
                                    "total_error_proxy": total_error,
                                    "disposition": status,
                                    "reason": reason,
                                }
                                writer.writerow(out)
                                counts[status] = counts.get(status, 0) + 1
                                if status.startswith("SELECTED"):
                                    selected_rows.append(out)

    # There is one selected row for every input-range/mode/readout copy that
    # reaches the selected order/rate. Retain only the canonical valid row.
    selected_rows = [
        row for row in selected_rows
        if row["input_mode"] == "DC_HIGHZ_SINGLE"
        and row["readout_mode"] == "continuous_timestamped_xy"
        and math.isclose(float(row["range_requested_v"]), 1.0)
    ]
    by_experiment = {row["experiment"]: row for row in selected_rows}
    if set(by_experiment) != set(experiments):
        raise RuntimeError("did not obtain exactly one canonical selected row per experiment")

    config_common = {
        "device_id": "dev18500",
        "signal_inputs": {
            "0": {"ac": 0, "impedance_50ohm": 0, "differential": 0, "range_requested_v": 1.0},
            "1": {"ac": 0, "impedance_50ohm": 0, "differential": 0, "range_requested_v": 1.0},
        },
        "demodulator_assignments": {"sample": 0, "reference": 3},
        "oscselect": 0,
        "harmonic": 1,
        "trigger": 0,
        "readout": "continuous_timestamped_xy_plus_full_dio",
        "external_master_clock": 1,
        "reference": {"pll": 0, "source": "DIO0", "center_hz": 2000000.0},
    }
    configs = {
        "schema_version": "HF01-SELECTED-CONFIG-v1",
        "analysis_id": ANALYSIS_ID,
        "generated_utc": stamp(),
        "common": config_common,
        "configurations": {
            "HF01-SWEEP-SELECTED-001": {
                "order": 4, "timeconstant_requested_s": 0.001,
                "timeconstant_readback_s": 0.0010018887078828383,
                "rate_readback_sps": 899.4654605263158,
                "immediately_lower_rate_sps": 449.7327302631579,
                "status": "SELECTED_WITH_DYNAMIC_VALIDITY_ENVELOPE",
            },
            "HF01-HRP-SELECTED-001": {
                "alias_of_numeric_settings": "HF01-SWEEP-SELECTED-001",
                "order": 4, "timeconstant_requested_s": 0.001,
                "timeconstant_readback_s": 0.0010018887078828383,
                "rate_readback_sps": 899.4654605263158,
                "immediately_lower_rate_sps": 449.7327302631579,
                "status": "SELECTED_WITH_EARLY_FEATURE_VALIDITY_ENVELOPE",
            },
            "HF01-MBCO-SELECTED-001": {
                "order": 1, "timeconstant_requested_s": 5.6e-6,
                "timeconstant_readback_s": 5.600017467592051e-6,
                "rate_readback_sps": 230263.15789473685,
                "immediately_lower_rate_sps": 115131.57894736843,
                "status": "BOUNDARY_CONFIGURATION_OUTSIDE_MANDATORY_1US_ENVELOPE",
            },
        },
        "reload_equivalence": {
            "integers_and_strings": "exact",
            "doubles": "relative difference <= 1e-9 or identical observed device quantization",
        },
    }
    CONFIGS.write_text(json.dumps(configs, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    results = {
        "analysis_id": ANALYSIS_ID,
        "generated_utc": stamp(),
        "model_source": "HF01-MODEL-RESIDUAL-v3",
        "supported_space_source": space["acquisition_id"],
        "candidate_row_count": row_number,
        "disposition_counts": counts,
        "continuous_timeconstant_coverage": {
            "minimum_s": min_tc,
            "maximum_s": max_tc,
            "method": "each discrete cell retains the complete continuous interval and its sampling-valid lower boundary; metrics are evaluated at the least-memory endpoint and monotonic noise-memory tradeoff covers all larger values",
        },
        "prior_detector_interval_v": {
            "minimum": EXPECTED_SIGNAL_MIN_V,
            "maximum": EXPECTED_SIGNAL_MAX_V,
            "source": "docs/ui_hardware_control_reference.md prior successful HF2LI/MIRcat record",
            "use_limit": "range headroom only; DET-01/DET-02 must establish operational detector noise and clipping",
        },
        "noise_density_v_per_sqrt_hz": noise_densities,
        "conservative_noise_density_v_per_sqrt_hz": conservative_noise_density,
        "selected": by_experiment,
        "challengers": [],
        "challenger_reason": "none invoked: rate boundaries are fixed by the 8x bandwidth guard and no HF2LI challenger can overcome the MbCO dual-channel 1 us sampling failure",
        "mbco_mandatory_feature_preserved": False,
        "overall_status": "SELECTED_WITH_MBCO_LIMITATION",
    }
    RESULT.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    s = by_experiment["sweep"]
    h = by_experiment["hrp"]
    m = by_experiment["mbco"]
    REPORT.write_text(
        "\n".join(
            [
                "# HF-01 supported-configuration analysis",
                "",
                f"Analysis ID: `{ANALYSIS_ID}`  ",
                "Status: **SELECTED WITH MBCO LIMITATION**",
                "",
                "The candidate table covers all 11 installed ranges, eight input modes, three readout modes, eight filter orders, 21 dual-channel rates, and the complete writable time-constant interval. The continuous interval is retained analytically rather than replaced by an arbitrary finite time-constant grid.",
                "",
                "## Selections",
                "",
                "| ID | Order | Time constant readback | Rate | Key envelope |",
                "|---|---:|---:|---:|---|",
                f"| `HF01-SWEEP-SELECTED-001` | 4 | {float(s['least_memory_evaluation_tau_s']):.12g} s | {float(s['rate_sps']):.12g} Sa/s | {float(s['sweep_peak_shift_cm1']):.4g} cm-1 kernel mean shift and {float(s['sweep_kernel_sigma_cm1']):.4g} cm-1 kernel sigma at 40 cm-1/s; AR-01 retains final feature-tolerance authority. |",
                f"| `HF01-HRP-SELECTED-001` | 4 | {float(h['least_memory_evaluation_tau_s']):.12g} s | {float(h['rate_sps']):.12g} Sa/s | {float(h['settling_99_s']):.4g} s 99% memory, {float(h['hrp_samples_per_100ms']):.3g} samples per provisional 100 ms interval. |",
                f"| `HF01-MBCO-SELECTED-001` | 1 | {float(m['least_memory_evaluation_tau_s']):.12g} s | {float(m['rate_sps']):.12g} Sa/s | Boundary setting only: {float(m['mbco_samples_per_1us']):.3g} sample per 1 us and {float(m['attenuation_fraction']):.3%} attenuation at the 1 us characteristic scale; mandatory 1 us preservation fails. |",
                "",
                "The sweep and HRP IDs are explicit numeric aliases but retain separate applicability envelopes. No challenger is invoked. The 1 V nominal, DC, high-impedance, single-ended input mode is selected because it is the smallest installed range above twice the prior 0.4651 V detector maximum and matches the established one-coax detector topology.",
                "",
                "## Limits",
                "",
                "Sweep feature width and final distortion tolerances, HRP's fastest accepted early feature and precision target, and installed-detector noise remain downstream measurements. The table therefore reports their Pareto coefficients and validity envelopes rather than inventing thresholds. MbCO is a hard negative result: with two analog streams the maximum rate supplies only 0.230 sample per mandatory 1 us feature, so no HF2LI filter configuration can preserve that claim.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
