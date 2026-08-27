"""Complete HF-01 contract tables from retained acquisition and analysis records."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
ANALYSIS = HERE / "analysis"
PHASE_RUN_ID = "system_recalibration_001_HF-01_001"
CAMPAIGN_ID = "system_recalibration_001"
PHASE_ID = "HF-01"
OPERATOR_ID = "Christopher_Robertson"


ACQUISITIONS: dict[str, dict[str, Any]] = {
    "HF01-HF2-MASTER-CLOCK-DIAG-001": {
        "file": "hf01_hf2_master_clock_diagnostic_001.json", "parent": "",
        "config": "HF01-CLOCK-DISTRIBUTION-DIAG-v1", "kind": "clock_diagnostic",
        "condition": "HF01-COND-HF2-MASTER-CLOCK-DIAG", "planned": "false", "accepted": "true", "rejection": "",
        "notes": "Valid diagnostic identified an unlocked external master-clock distribution before recovery; no physical change.",
    },
    "HF01-CLOCK-DISTRIBUTION-RECOVERY-001": {
        "file": "hf01_clock_distribution_recovery_001.json", "parent": "HF01-HF2-MASTER-CLOCK-DIAG-001",
        "config": "HF01-CLOCK-DISTRIBUTION-RECOVERY-v1", "kind": "clock_recovery",
        "condition": "HF01-COND-CLOCK-RECOVERY", "planned": "false", "accepted": "true", "rejection": "",
        "notes": "T660-1 returned to external 10 MHz input and locked; HF2LI external master clock locked; installed splitter wiring unchanged.",
    },
    "HF01-PLL-ANALOG-REFERENCE-DIAG-001": {
        "file": "hf01_pll_analog_reference_diagnostic_001.json", "parent": "HF01-CLOCK-DISTRIBUTION-RECOVERY-001",
        "config": "HF01-PLL-REFERENCE-DIAG-v1", "kind": "reference_diagnostic",
        "condition": "HF01-COND-PLL-ANALOG-DIAG", "planned": "false", "accepted": "false", "rejection": "HF01-DIAG-ANALOG-REFERENCE-UNLOCKED",
        "notes": "Bounded diagnostic did not lock PLL0 to the analog reference candidate; the retained DIO0 external-reference route was used.",
    },
    "HF01-ANCHOR-FAST-V3-001": {
        "file": "hf01_anchor_fast_v3_001_status.json", "parent": "HF01-ANCHOR-FAST-V2-001",
        "config": "HF01-VALIDATION-DESIGN-v3", "kind": "instrument_model_anchor",
        "condition": "HF01-COND-ANCHOR-FAST-V3", "planned": "true", "accepted": "true", "rejection": "",
        "notes": "Accepted fast paired-demodulator primary model anchor.",
    },
    "HF01-ANCHOR-INTERMEDIATE-V3-001": {
        "file": "hf01_anchor_intermediate_v3_001_status.json", "parent": "HF01-ANCHOR-INTERMEDIATE-R1-001",
        "config": "HF01-VALIDATION-DESIGN-v3", "kind": "instrument_model_anchor",
        "condition": "HF01-COND-ANCHOR-INTERMEDIATE-V3", "planned": "true", "accepted": "true", "rejection": "",
        "notes": "Accepted intermediate paired-demodulator primary model anchor including positive/negative cutoff pair.",
    },
    "HF01-ANCHOR-SLOW-V3-001": {
        "file": "hf01_anchor_slow_v3_001_status.json", "parent": "HF01-ANCHOR-SLOW-R3-001",
        "config": "HF01-VALIDATION-DESIGN-v3", "kind": "instrument_model_anchor",
        "condition": "HF01-COND-ANCHOR-SLOW-V3", "planned": "true", "accepted": "false", "rejection": "HF01-REJECT-SLOW-SETTLING-REPLICATE",
        "notes": "Electrically clean record preserved; one rising transition exceeded the prospective 120 percent settling limit and invoked one identical-setting repeat.",
    },
    "HF01-ANCHOR-SLOW-V3-R1-001": {
        "file": "hf01_anchor_slow_v3_r1_001_status.json", "parent": "HF01-ANCHOR-SLOW-V3-001",
        "config": "HF01-VALIDATION-DESIGN-v3", "kind": "instrument_model_anchor",
        "condition": "HF01-COND-ANCHOR-SLOW-V3-R1", "planned": "true", "accepted": "true", "rejection": "",
        "notes": "Accepted identical-setting slow-anchor integrity repeat; all frozen v3 metrics pass.",
    },
    "HF01-HF2-SUPPORTED-SPACE-001": {
        "file": "hf01_hf2_supported_parameter_space_001.json", "parent": "",
        "config": "HF01-SUPPORTED-SPACE-v1", "kind": "configuration_readback",
        "condition": "HF01-COND-SUPPORTED-SPACE", "planned": "true", "accepted": "true", "rejection": "",
        "notes": "Installed supported orders ranges modes rates and continuous time-constant domain read back with original settings restored.",
    },
    "HF01-SELECTED-SWEEP-HRP-IN1-001": {
        "file": "hf01_selected_sweep_hrp_in1_001_status.json", "parent": "",
        "config": "HF01-SWEEP-HRP-SELECTED-ALIAS-001", "kind": "selected_configuration_confirmation",
        "condition": "HF01-COND-SELECTED-SWEEP-HRP-IN1", "planned": "true", "accepted": "true", "rejection": "",
        "notes": "Signal Input 1 confirmation for the numerically aliased sweep and HRP configurations.",
    },
    "HF01-LOWER-SWEEP-HRP-IN1-001": {
        "file": "hf01_lower_sweep_hrp_in1_001_status.json", "parent": "HF01-SELECTED-SWEEP-HRP-IN1-001",
        "config": "HF01-SWEEP-HRP-LOWER-RATE-001", "kind": "rate_neighbor_confirmation",
        "condition": "HF01-COND-LOWER-SWEEP-HRP-IN1", "planned": "true", "accepted": "false", "rejection": "HF01-REJECT-RATE-GUARD",
        "notes": "Valid electrical record; immediately lower rate rejected because rate-to-cutoff ratio is 6.509 below the required 8.",
    },
    "HF01-SELECTED-MBCO-IN1-001": {
        "file": "hf01_selected_mbco_in1_001_status.json", "parent": "",
        "config": "HF01-MBCO-SELECTED-001", "kind": "selected_configuration_confirmation",
        "condition": "HF01-COND-SELECTED-MBCO-IN1", "planned": "true", "accepted": "true", "rejection": "",
        "notes": "Signal Input 1 confirmation of the fastest valid two-channel MbCO boundary configuration; mandatory 1 us preservation remains failed analytically.",
    },
    "HF01-LOWER-MBCO-IN1-001": {
        "file": "hf01_lower_mbco_in1_001_status.json", "parent": "HF01-SELECTED-MBCO-IN1-001",
        "config": "HF01-MBCO-LOWER-RATE-001", "kind": "rate_neighbor_confirmation",
        "condition": "HF01-COND-LOWER-MBCO-IN1", "planned": "true", "accepted": "false", "rejection": "HF01-REJECT-RATE-GUARD",
        "notes": "Immediately lower rate rejected because the 4.051 rate-to-cutoff ratio fails the required 8 and the electrical model confirmation also fails.",
    },
    "HF01-SELECTED-SWEEP-HRP-IN2-001": {
        "file": "hf01_selected_sweep_hrp_in2_001_status.json", "parent": "HF01-SELECTED-SWEEP-HRP-IN1-001",
        "config": "HF01-SWEEP-HRP-SELECTED-ALIAS-001", "kind": "channel_equivalence_confirmation",
        "condition": "HF01-COND-SELECTED-SWEEP-HRP-IN2", "planned": "true", "accepted": "true", "rejection": "",
        "notes": "Signal Input 2 selected-setting confirmation; channel-equivalence limits pass.",
    },
    "HF01-SELECTED-MBCO-IN2-001": {
        "file": "hf01_selected_mbco_in2_001_status.json", "parent": "HF01-SELECTED-MBCO-IN1-001",
        "config": "HF01-MBCO-SELECTED-001", "kind": "channel_equivalence_confirmation",
        "condition": "HF01-COND-SELECTED-MBCO-IN2", "planned": "true", "accepted": "true", "rejection": "",
        "notes": "Signal Input 2 selected-setting confirmation; channel-equivalence limits pass while the 1 us applicability limitation remains.",
    },
    "HF01-RANGE-LOW-IN2-001": {
        "file": "hf01_range_low_in2_001_status.json", "parent": "HF01-SELECTED-SWEEP-HRP-IN2-001",
        "config": "HF01-RANGE-ENDPOINT-v1", "kind": "range_endpoint_confirmation",
        "condition": "HF01-COND-RANGE-LOW-IN2", "planned": "true", "accepted": "true", "rejection": "",
        "notes": "Signal Input 2 low connected-amplitude endpoint; no clipping or loss.",
    },
    "HF01-RANGE-HIGH-IN2-001": {
        "file": "hf01_range_high_in2_001_status.json", "parent": "HF01-RANGE-LOW-IN2-001",
        "config": "HF01-RANGE-ENDPOINT-v1", "kind": "range_endpoint_confirmation",
        "condition": "HF01-COND-RANGE-HIGH-IN2", "planned": "true", "accepted": "true", "rejection": "",
        "notes": "Signal Input 2 high connected-amplitude endpoint; measured endpoint ratio passes and no clipping or loss occurred.",
    },
    "HF01-CONFIG-RELOAD-001": {
        "file": "hf01_selected_configuration_reload_001.json", "parent": "",
        "config": "HF01-SELECTED-CONFIG-v1", "kind": "configuration_reload_equivalence",
        "condition": "HF01-COND-CONFIG-RELOAD", "planned": "true", "accepted": "true", "rejection": "",
        "notes": "All three restorable IDs loaded twice; integer nodes exact and double-node differences zero; original HF2 settings restored.",
    },
    "HF01-PRE-RESTORATION-SAFE-STATE-001": {
        "file": "hf01_pre_restoration_safe_state_001.json", "parent": "",
        "config": "HF01-ELECTRONIC-SAFE-IDLE-v1", "kind": "electronic_safe_state",
        "condition": "HF01-COND-PRE-RESTORATION-SAFE", "planned": "true", "accepted": "true", "rejection": "",
        "notes": "Current safe-idle readback before timing-cable restoration; Pico AWG zero and T660 safe idle match.",
    },
    "HF01-FINAL-RESTORATION-STATE-001": {
        "file": "hf01_final_restoration_state_001.json", "parent": "",
        "config": "HF01-FINAL-RESTORATION-v1", "kind": "final_restoration_readback",
        "condition": "HF01-COND-FINAL-RESTORATION", "planned": "true", "accepted": "false", "rejection": "HF01-REJECT-COM3-CONTENTION",
        "notes": "Retained failed attempt: Windows denied COM3 access before the T660 readback; no hardware state change was inferred.",
    },
    "HF01-FINAL-RESTORATION-STATE-R1-001": {
        "file": "hf01_final_restoration_state_r1_001.json", "parent": "HF01-FINAL-RESTORATION-STATE-001",
        "config": "HF01-FINAL-RESTORATION-v1", "kind": "final_restoration_readback",
        "condition": "HF01-COND-FINAL-RESTORATION-R1", "planned": "true", "accepted": "true", "rejection": "",
        "notes": "Final readback passes: T660 safe idle Pico AWG zero HF2 prechange configuration exact and status flags clean after operator-confirmed default wiring.",
    },
}


ACQ_HEADERS = "campaign_id,phase_id,phase_run_id,acquisition_id,parent_acquisition_id,start_utc,end_utc,operator_id,configuration_id,calibration_bundle_id,sample_id,measurement_kind,condition_set_id,replicate_index,planned,accepted,rejection_code,raw_primary_artifact_id,notes".split(",")
COND_HEADERS = "campaign_id,phase_id,acquisition_id,condition_set_id,condition_name,value_text,value_number,unit,source,uncertainty_value,uncertainty_unit,uncertainty_type,notes".split(",")
MEAS_HEADERS = "campaign_id,phase_id,acquisition_id,result_set_id,quantity_name,value,unit,statistic,reference_plane,sign_convention,correction_state,standard_uncertainty,coverage_factor,expanded_uncertainty,quality_flag,analysis_artifact_id,notes".split(",")
EXCL_HEADERS = "campaign_id,phase_id,acquisition_id,decision_utc,decision_maker,exclusion_code,criterion_version,reason,downstream_effect,superseded_by_acquisition_id,notes".split(",")
LEDGER_HEADERS = "ledger_id,timestamp_utc,actor,action,expected_state,observed_state,evidence_artifact_id,decision,notes".split(",")
LINK_HEADERS = "campaign_id,phase_id,phase_run_id,calibration_bundle_id,calibration_quantity_id,source_campaign_id,source_phase_id,source_artifact_id,value_used,unit,standard_uncertainty,validity_status,notes".split(",")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(({key: row.get(key, "") for key in headers} for row in rows))


def append_unique(rows: list[dict[str, str]], key_fields: tuple[str, ...], additions: list[dict[str, Any]]) -> None:
    seen = {tuple(row.get(field, "") for field in key_fields) for row in rows}
    for addition in additions:
        key = tuple(str(addition.get(field, "")) for field in key_fields)
        if key not in seen:
            rows.append({field: str(value) if value is not None else "" for field, value in addition.items()})
            seen.add(key)


def raw_records() -> dict[str, tuple[Path, dict[str, Any]]]:
    result: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(RAW.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        acquisition_id = data.get("acquisition_id")
        if not acquisition_id:
            continue
        current = result.get(str(acquisition_id))
        priority = int("status" in path.stem or path.stem.endswith("_001"))
        current_priority = -1 if current is None else int("status" in current[0].stem or current[0].stem.endswith("_001"))
        if current is None or priority > current_priority:
            result[str(acquisition_id)] = (path, data)
    return result


def artifact_ids() -> dict[str, str]:
    path = HERE / "artifacts.csv"
    if not path.exists():
        return {}
    return {row["relative_path"]: row["artifact_id"] for row in read_csv(path)}


def build_acquisitions(records: dict[str, tuple[Path, dict[str, Any]]]) -> None:
    path = HERE / "acquisition_index.csv"
    rows = read_csv(path)
    additions: list[dict[str, Any]] = []
    for acquisition_id, definition in ACQUISITIONS.items():
        raw_path = RAW / definition["file"]
        data = json.loads(raw_path.read_text(encoding="utf-8"))
        additions.append({
            "campaign_id": CAMPAIGN_ID, "phase_id": PHASE_ID, "phase_run_id": PHASE_RUN_ID,
            "acquisition_id": acquisition_id, "parent_acquisition_id": definition["parent"],
            "start_utc": data.get("started_utc") or data.get("start_utc") or "",
            "end_utc": data.get("finished_utc") or data.get("end_utc") or "",
            "operator_id": OPERATOR_ID, "configuration_id": definition["config"],
            "calibration_bundle_id": "", "sample_id": "", "measurement_kind": definition["kind"],
            "condition_set_id": definition["condition"], "replicate_index": "1",
            "planned": definition["planned"], "accepted": definition["accepted"],
            "rejection_code": definition["rejection"], "raw_primary_artifact_id": "", "notes": definition["notes"],
        })
    append_unique(rows, ("acquisition_id",), additions)

    ids = artifact_ids()
    for row in rows:
        record = records.get(row["acquisition_id"])
        if record is None:
            continue
        relative = record[0].relative_to(HERE.parents[1]).as_posix()
        if ids.get(relative):
            row["raw_primary_artifact_id"] = ids[relative]
    write_csv(path, ACQ_HEADERS, rows)


def condition_row(acquisition_id: str, condition_set_id: str, name: str, *, text: str = "", number: Any = "", unit: str = "", source: str = "device readback", notes: str = "") -> dict[str, Any]:
    return {"campaign_id": CAMPAIGN_ID, "phase_id": PHASE_ID, "acquisition_id": acquisition_id, "condition_set_id": condition_set_id,
            "condition_name": name, "value_text": text, "value_number": number, "unit": unit, "source": source,
            "uncertainty_value": "", "uncertainty_unit": "", "uncertainty_type": "", "notes": notes}


def build_conditions(records: dict[str, tuple[Path, dict[str, Any]]]) -> None:
    path = HERE / "conditions.csv"
    rows = read_csv(path)
    additions: list[dict[str, Any]] = []
    for acquisition_id, definition in ACQUISITIONS.items():
        data = records[acquisition_id][1]
        condition = definition["condition"]
        additions.append(condition_row(acquisition_id, condition, "acquisition_status", text=str(data.get("status", ""))))
        plan = data.get("anchor_plan") or {}
        staged = data.get("hf2li_staged") or {}
        if plan:
            additions.extend([
                condition_row(acquisition_id, condition, "filter_order_requested", number=plan.get("order", ""), unit="count", source="prospective plan"),
                condition_row(acquisition_id, condition, "timeconstant_requested", number=plan.get("tau_s", ""), unit="s", source="prospective plan"),
                condition_row(acquisition_id, condition, "output_rate_requested", number=plan.get("requested_rate_sps", ""), unit="Sa/s", source="prospective plan"),
                condition_row(acquisition_id, condition, "signal_input_index", number=plan.get("input_index", 0), unit="index", source="prospective plan"),
                condition_row(acquisition_id, condition, "range_requested", number=plan.get("range_v", ""), unit="V", source="prospective plan"),
            ])
        if staged:
            additions.extend([
                condition_row(acquisition_id, condition, "filter_order_readback", number=staged.get("order", ""), unit="count"),
                condition_row(acquisition_id, condition, "timeconstant_readback", number=staged.get("timeconstant_s", ""), unit="s"),
                condition_row(acquisition_id, condition, "output_rate_readback", number=staged.get("rate_sps", ""), unit="Sa/s"),
                condition_row(acquisition_id, condition, "range_readback", number=staged.get("signal_input_range_v", staged.get("sigins0_range_v", "")), unit="V"),
            ])
        if data.get("t660_safe_idle") is not None:
            additions.append(condition_row(acquisition_id, condition, "t660_safe_idle", text="PASS" if data["t660_safe_idle"].get("matches_recipe") else "FAIL"))
        elif data.get("t660_safe_idle_after") is not None:
            additions.append(condition_row(acquisition_id, condition, "t660_safe_idle_after", text="PASS" if data["t660_safe_idle_after"].get("matches_recipe") else "FAIL"))

    space = records["HF01-HF2-SUPPORTED-SPACE-001"][1]
    additions.extend([
        condition_row("HF01-HF2-SUPPORTED-SPACE-001", "HF01-COND-SUPPORTED-SPACE", "supported_range_count", number=len(space["input_ranges"]), unit="count"),
        condition_row("HF01-HF2-SUPPORTED-SPACE-001", "HF01-COND-SUPPORTED-SPACE", "supported_order_count", number=len(space["filter_orders"]), unit="count"),
        condition_row("HF01-HF2-SUPPORTED-SPACE-001", "HF01-COND-SUPPORTED-SPACE", "dual_channel_rate_count", number=len(space["dual_channel_rate_ladder_sps"]), unit="count"),
        condition_row("HF01-HF2-SUPPORTED-SPACE-001", "HF01-COND-SUPPORTED-SPACE", "timeconstant_minimum", number=space["timeconstant_domain"]["minimum_readback_s"], unit="s"),
        condition_row("HF01-HF2-SUPPORTED-SPACE-001", "HF01-COND-SUPPORTED-SPACE", "timeconstant_maximum", number=space["timeconstant_domain"]["maximum_readback_s"], unit="s"),
    ])
    append_unique(rows, ("acquisition_id", "condition_name"), additions)
    write_csv(path, COND_HEADERS, rows)


def measurement(acquisition_id: str, result_set_id: str, name: str, value: Any, unit: str, *, statistic: str = "derived", plane: str = "HF2LI electronic signal path", correction: str = "derived", uncertainty: Any = "", quality: str = "PASS", analysis_id: str = "", notes: str = "") -> dict[str, Any]:
    return {"campaign_id": CAMPAIGN_ID, "phase_id": PHASE_ID, "acquisition_id": acquisition_id, "result_set_id": result_set_id,
            "quantity_name": name, "value": value, "unit": unit, "statistic": statistic, "reference_plane": plane,
            "sign_convention": "", "correction_state": correction, "standard_uncertainty": uncertainty, "coverage_factor": "1" if uncertainty != "" else "",
            "expanded_uncertainty": "", "quality_flag": quality, "analysis_artifact_id": analysis_id, "notes": notes}


def build_measurements() -> None:
    path = HERE / "measurements.csv"
    rows = read_csv(path)
    for row in rows:
        if row.get("correction_state") == "analysis":
            row["correction_state"] = "derived"
    additions: list[dict[str, Any]] = []
    model = json.loads((ANALYSIS / "hf01_dual_demod_model_validation_results.json").read_text(encoding="utf-8"))
    for anchor in model["anchors"]:
        acquisition_id = anchor["acquisition_id"]
        result_id = f"HF01-RESULT-V3-{anchor['name'].upper()}"
        analysis_id = model["analysis_id"]
        additions.extend([
            measurement(acquisition_id, result_id, "normalized_rms_corrected_complex_residual", anchor["normalized_rms_complex_residual"], "ratio", analysis_id=analysis_id),
            measurement(acquisition_id, result_id, "cutoff_relative_residual", anchor["cutoff_relative_residual"], "ratio", analysis_id=analysis_id),
            measurement(acquisition_id, result_id, "paired_pipeline_delay", anchor["pipeline_delay"]["fitted_s"], "s", uncertainty=anchor["pipeline_delay"]["standard_uncertainty_s"], analysis_id=analysis_id),
            measurement(acquisition_id, result_id, "zero_noise_complex_rms", anchor["zero_noise"]["median_complex_output_rms_v"], "V", statistic="median", correction="raw", analysis_id=analysis_id),
            measurement(acquisition_id, result_id, "manufacturer_enbw", anchor["zero_noise"]["manufacturer_enbw_hz"], "Hz", analysis_id=analysis_id),
        ])
    additions.append(measurement("HF01-ANCHOR-SLOW-V3-001", "HF01-RESULT-V3-SLOW-REJECTED", "anchor_acceptance", 0, "boolean", quality="REJECTED", analysis_id=model["analysis_id"], notes="One rising transition exceeded the 120 percent settling limit; identical-setting R1 passed."))

    supported = json.loads((ANALYSIS / "hf01_supported_configuration_analysis.json").read_text(encoding="utf-8"))
    analysis_id = supported["analysis_id"]
    additions.append(measurement("HF01-HF2-SUPPORTED-SPACE-001", "HF01-RESULT-SUPPORTED-SELECTION", "candidate_configuration_count", supported["candidate_row_count"], "count", statistic="count", analysis_id=analysis_id))
    for name, selected in supported["selected"].items():
        acquisition_id = "HF01-SELECTED-MBCO-IN1-001" if name == "mbco" else "HF01-SELECTED-SWEEP-HRP-IN1-001"
        result_id = f"HF01-RESULT-SELECTED-{name.upper()}"
        additions.extend([
            measurement(acquisition_id, result_id, "filter_order", selected["order"], "count", analysis_id=analysis_id),
            measurement(acquisition_id, result_id, "timeconstant_readback", selected["least_memory_evaluation_tau_s"], "s", analysis_id=analysis_id),
            measurement(acquisition_id, result_id, "output_rate", selected["rate_sps"], "Sa/s", analysis_id=analysis_id),
            measurement(acquisition_id, result_id, "rate_to_cutoff_ratio", selected["rate_to_cutoff_ratio"], "ratio", analysis_id=analysis_id),
            measurement(acquisition_id, result_id, "attenuation_fraction", selected["attenuation_fraction"], "fraction", analysis_id=analysis_id),
        ])
        if name == "mbco":
            additions.append(measurement(acquisition_id, result_id, "samples_per_mandatory_1us_feature", selected["mbco_samples_per_1us"], "sample/feature", quality="LIMITATION", analysis_id=analysis_id, notes="Mandatory 1 us feature is outside the valid HF2LI two-channel envelope."))

    confirmation = json.loads((ANALYSIS / "hf01_selected_confirmation_results.json").read_text(encoding="utf-8"))
    analysis_id = confirmation["analysis_id"]
    for name, decision in confirmation["rate_decisions"].items():
        additions.extend([
            measurement(decision["selected_acquisition_id"], f"HF01-RESULT-RATE-{name.upper()}", "rate_to_cutoff_ratio", decision["selected_rate_guard"]["rate_to_cutoff_ratio"], "ratio", quality="PASS", analysis_id=analysis_id),
            measurement(decision["lower_acquisition_id"], f"HF01-RESULT-RATE-{name.upper()}-LOWER", "rate_to_cutoff_ratio", decision["lower_rate_guard"]["rate_to_cutoff_ratio"], "ratio", quality="REJECTED", analysis_id=analysis_id),
        ])
    for name, equivalent in confirmation["channel_equivalence"].items():
        acquisition_id = equivalent["input2_acquisition_id"]
        result_id = f"HF01-RESULT-CHANNEL-EQUIVALENCE-{name.upper()}"
        for quantity in ("gain_fractional_difference", "phase_difference_rad", "cutoff_fractional_difference", "settling_fractional_difference", "zero_noise_fractional_difference"):
            unit = "rad" if quantity == "phase_difference_rad" else "ratio"
            additions.append(measurement(acquisition_id, result_id, quantity, equivalent[quantity], unit, analysis_id=analysis_id))
    endpoints = confirmation["signal_input_2_range_endpoints"]
    additions.extend([
        measurement(endpoints["low_acquisition_id"], "HF01-RESULT-RANGE-IN2", "connected_amplitude_vpp", endpoints["low_measured_connected_vpp"], "V", statistic="measured Vpp", plane="PicoScope channel A connected tee monitor", correction="raw", analysis_id=analysis_id),
        measurement(endpoints["high_acquisition_id"], "HF01-RESULT-RANGE-IN2", "connected_amplitude_vpp", endpoints["high_measured_connected_vpp"], "V", statistic="measured Vpp", plane="PicoScope channel A connected tee monitor", correction="raw", analysis_id=analysis_id),
        measurement(endpoints["high_acquisition_id"], "HF01-RESULT-RANGE-IN2", "high_to_low_amplitude_ratio", endpoints["measured_ratio"], "ratio", analysis_id=analysis_id),
    ])
    additions.extend([
        measurement("HF01-CONFIG-RELOAD-001", "HF01-RESULT-CONFIG-RELOAD", "maximum_reload_relative_difference", 0, "ratio", analysis_id="HF01-CONFIG-RELOAD-001", notes="All observed double differences were zero; integer nodes matched exactly."),
        measurement("HF01-FINAL-RESTORATION-STATE-R1-001", "HF01-RESULT-FINAL-RESTORATION", "restored_hf2_node_match_count", 25, "count", statistic="count", quality="PASS", analysis_id="HF01-FINAL-RESTORATION-STATE-R1-001"),
        measurement("HF01-FINAL-RESTORATION-STATE-R1-001", "HF01-RESULT-FINAL-RESTORATION", "unclean_hf2_status_flag_count", 0, "count", statistic="count", quality="PASS", analysis_id="HF01-FINAL-RESTORATION-STATE-R1-001"),
    ])
    append_unique(rows, ("acquisition_id", "result_set_id", "quantity_name", "statistic"), additions)
    write_csv(path, MEAS_HEADERS, rows)


def build_exclusions() -> None:
    path = HERE / "exclusions.csv"
    rows = read_csv(path)
    additions = [
        {"campaign_id": CAMPAIGN_ID, "phase_id": PHASE_ID, "acquisition_id": "HF01-PLL-ANALOG-REFERENCE-DIAG-001", "decision_utc": "2026-08-26T20:26:41.686946Z", "decision_maker": "Codex", "exclusion_code": "HF01-DIAG-ANALOG-REFERENCE-UNLOCKED", "criterion_version": "HF01-REFERENCE-ROUTE-v1", "reason": "PLL0 did not lock to the bounded analog-reference candidate.", "downstream_effect": "Retain DIO0 as the external-reference route.", "superseded_by_acquisition_id": "", "notes": "Diagnostic retained; no laser or optical action."},
        {"campaign_id": CAMPAIGN_ID, "phase_id": PHASE_ID, "acquisition_id": "HF01-ANCHOR-SLOW-V3-001", "decision_utc": "2026-08-26T22:23:20Z", "decision_maker": "Codex", "exclusion_code": "HF01-REJECT-SLOW-SETTLING-REPLICATE", "criterion_version": "HF01-MODEL-RESIDUAL-v3", "reason": "One rising transition exceeded 120 percent of predicted 1 to 99 percent settling.", "downstream_effect": "Do not use as the primary slow anchor.", "superseded_by_acquisition_id": "HF01-ANCHOR-SLOW-V3-R1-001", "notes": "The prospectively permitted one identical-setting repeat passed."},
        {"campaign_id": CAMPAIGN_ID, "phase_id": PHASE_ID, "acquisition_id": "HF01-LOWER-SWEEP-HRP-IN1-001", "decision_utc": "2026-08-26T22:57:00Z", "decision_maker": "Codex", "exclusion_code": "HF01-REJECT-RATE-GUARD", "criterion_version": "HF01-RATE-GUARD-v1", "reason": "Rate-to-cutoff ratio 6.509 is below the required 8.", "downstream_effect": "Retain 899.4654605263158 Sa/s for sweep and HRP.", "superseded_by_acquisition_id": "HF01-SELECTED-SWEEP-HRP-IN1-001", "notes": "Electrical data remain retained."},
        {"campaign_id": CAMPAIGN_ID, "phase_id": PHASE_ID, "acquisition_id": "HF01-LOWER-MBCO-IN1-001", "decision_utc": "2026-08-26T22:57:00Z", "decision_maker": "Codex", "exclusion_code": "HF01-REJECT-RATE-GUARD", "criterion_version": "HF01-RATE-GUARD-v1", "reason": "Rate-to-cutoff ratio 4.051 is below the required 8 and the electrical model confirmation fails.", "downstream_effect": "Retain 230263.15789473685 Sa/s as the MbCO boundary rate.", "superseded_by_acquisition_id": "HF01-SELECTED-MBCO-IN1-001", "notes": "This does not cure the mandatory 1 us limitation."},
        {"campaign_id": CAMPAIGN_ID, "phase_id": PHASE_ID, "acquisition_id": "HF01-SELECTED-MBCO-IN1-001", "decision_utc": "2026-08-26T22:57:00Z", "decision_maker": "Codex", "exclusion_code": "HF01-LIMIT-MBCO-1US", "criterion_version": "HF01-SELECTION-v1", "reason": "Fastest valid dual-channel configuration supplies 0.230 sample per 1 us and modeled attenuation is 82.421 percent.", "downstream_effect": "Configuration may be used only as an explicitly limited boundary; it is not valid for the mandatory 1 us MbCO claim.", "superseded_by_acquisition_id": "", "notes": "No supported HF2LI configuration satisfies this requirement."},
        {"campaign_id": CAMPAIGN_ID, "phase_id": PHASE_ID, "acquisition_id": "HF01-FINAL-RESTORATION-STATE-001", "decision_utc": "2026-08-26T23:49:00.839654Z", "decision_maker": "Codex", "exclusion_code": "HF01-REJECT-COM3-CONTENTION", "criterion_version": "HF01-FINAL-RESTORATION-v1", "reason": "Windows denied COM3 access before the first T660 readback.", "downstream_effect": "No final-state claim from this attempt; use the retained R1 readback.", "superseded_by_acquisition_id": "HF01-FINAL-RESTORATION-STATE-R1-001", "notes": "No hardware state change was inferred from the failed attempt."},
    ]
    append_unique(rows, ("acquisition_id", "exclusion_code"), additions)
    write_csv(path, EXCL_HEADERS, rows)


def build_ledger() -> None:
    path = HERE / "action_ledger.csv"
    rows = read_csv(path)
    additions = [
        ["HF01-LEDGER-0043", "2026-08-26T22:19:37.487915Z", "Codex", "Captured the v3 fast paired-demodulator anchor", "Exact common timestamps and all frozen integrity/model metrics", "Fast primary anchor passed", "HF01-ANCHOR-FAST-V3-001", "ACCEPT_PRIMARY_ANCHOR", "No fourth point or physical grid"],
        ["HF01-LEDGER-0044", "2026-08-26T22:20:30.997101Z", "Codex", "Captured the v3 intermediate paired-demodulator anchor", "All metrics plus positive/negative cutoff pair", "Intermediate primary anchor passed", "HF01-ANCHOR-INTERMEDIATE-V3-001", "ACCEPT_PRIMARY_ANCHOR", "No later phase"],
        ["HF01-LEDGER-0045", "2026-08-26T22:22:56.689836Z", "Codex", "Captured the v3 slow paired-demodulator anchor", "Six transitions satisfy the frozen settling rule", "One rising transition exceeded 120 percent of prediction", "HF01-ANCHOR-SLOW-V3-001", "REPEAT_IDENTICAL_SETTING_ONCE", "Rejected record preserved"],
        ["HF01-LEDGER-0046", "2026-08-26T22:25:44.374134Z", "Codex", "Captured the identical-setting v3 slow-anchor repeat", "All frozen v3 metrics pass", "Slow repeat passed", "HF01-ANCHOR-SLOW-V3-R1-001", "ACCEPT_PRIMARY_ANCHOR", "Original slow record retained as rejected"],
        ["HF01-LEDGER-0047", "2026-08-26T22:27:00Z", "Codex", "Applied the v3 three-anchor model criterion", "Exactly three primary anchors pass", "Fast intermediate and accepted slow repeat all pass", "HF01-ANALYSIS-DUAL-DEMOD-MODEL-001", "AUTHORIZE_COMPUTATIONAL_SELECTION", "No challenger or fourth model point"],
        ["HF01-LEDGER-0048", "2026-08-26T22:32:55.989270Z", "Codex", "Read back the installed supported HF2LI parameter space", "Complete discrete modes plus continuous time-constant interval", "11 ranges 8 orders 21 dual-channel rates 8 input modes and 3 readout modes retained", "HF01-HF2-SUPPORTED-SPACE-001", "PASS_SUPPORTED_SPACE", "Original settings restored"],
        ["HF01-LEDGER-0049", "2026-08-26T22:35:32.004175Z", "Codex", "Evaluated all supported configurations computationally", "Select one configuration per experiment or document impossibility", "133056 candidates evaluated; sweep and HRP selected; MbCO retained only as a boundary outside 1 us", "HF01-ANALYSIS-SUPPORTED-CONFIGURATIONS-001", "SELECT_WITH_MBCO_LIMITATION", "No challenger invoked"],
        ["HF01-LEDGER-0050", "2026-08-26T22:37:44.284638Z", "Codex", "Confirmed selected sweep and HRP settings on Signal Input 1", "Selected rate and electrical model confirmation pass", "All confirmation guards pass", "HF01-SELECTED-SWEEP-HRP-IN1-001", "ACCEPT_SELECTED_RATE", "Separate sweep and HRP IDs remain explicit aliases"],
        ["HF01-LEDGER-0051", "2026-08-26T22:38:23.653032Z", "Codex", "Confirmed the immediately lower sweep and HRP rate", "Lower rate fails the 8 times bandwidth guard", "Rate-to-cutoff ratio 6.509", "HF01-LOWER-SWEEP-HRP-IN1-001", "REJECT_LOWER_RATE", "Electrical record retained"],
        ["HF01-LEDGER-0052", "2026-08-26T22:39:20.127989Z", "Codex", "Confirmed the selected MbCO boundary settings on Signal Input 1", "Fastest valid rate passes electrical guards", "Rate-to-cutoff ratio 8.102 and model confirmation pass", "HF01-SELECTED-MBCO-IN1-001", "ACCEPT_BOUNDARY_CONFIGURATION", "Mandatory 1 us claim remains outside envelope"],
        ["HF01-LEDGER-0053", "2026-08-26T22:40:05.780446Z", "Codex", "Confirmed the immediately lower MbCO rate", "Lower rate fails rate and model guards", "Rate-to-cutoff ratio 4.051 and model confirmation fail", "HF01-LOWER-MBCO-IN1-001", "REJECT_LOWER_RATE", "Electrical record retained"],
        ["HF01-LEDGER-0054", "2026-08-26T22:52:34.195205Z", "Codex", "Confirmed selected sweep and HRP settings on Signal Input 2", "Channel equivalence within frozen limits", "All gain phase cutoff settling noise clipping and loss checks pass", "HF01-SELECTED-SWEEP-HRP-IN2-001", "PASS_CHANNEL_EQUIVALENCE", "Operator move is HF01-OPCONF-006"],
        ["HF01-LEDGER-0055", "2026-08-26T22:53:23.562390Z", "Codex", "Confirmed selected MbCO boundary settings on Signal Input 2", "Channel equivalence within frozen limits", "All equivalence checks pass", "HF01-SELECTED-MBCO-IN2-001", "PASS_CHANNEL_EQUIVALENCE", "Mandatory 1 us limitation unchanged"],
        ["HF01-LEDGER-0056", "2026-08-26T22:56:00.297224Z", "Codex", "Captured the Signal Input 2 low range endpoint", "Safe connected endpoint with no clipping or loss", "Measured 0.0103725863 Vpp", "HF01-RANGE-LOW-IN2-001", "ACCEPT_RANGE_ENDPOINT", "PicoScope channel A is connected-voltage authority"],
        ["HF01-LEDGER-0057", "2026-08-26T22:56:34.686770Z", "Codex", "Captured the Signal Input 2 high range endpoint", "Endpoint ratio within 3 percent of 10 times", "Measured 0.101188680 Vpp and ratio error 2.446 percent", "HF01-RANGE-HIGH-IN2-001", "PASS_RANGE_ENDPOINTS", "No clipping or loss"],
        ["HF01-LEDGER-0058", "2026-08-26T22:57:00Z", "Codex", "Applied selected-setting rate channel and range criteria", "All selected confirmations pass and lower rates reject", "Analysis status PASS", "HF01-ANALYSIS-SELECTED-CONFIRMATION-001", "ACCEPT_SELECTED_CONFIRMATIONS", "No ambiguity challenger invoked"],
        ["HF01-LEDGER-0059", "2026-08-26T22:58:44.225176Z", "Codex", "Loaded each selected configuration twice and restored the prechange HF2LI settings", "Exact integer and bounded double reload equivalence", "All integer nodes exact and every observed double difference zero", "HF01-CONFIG-RELOAD-001", "PASS_RELOAD_EQUIVALENCE", "Original HF2LI settings restored exactly"],
        ["HF01-LEDGER-0060", "2026-08-26T22:59:42.3040771Z", "Christopher Robertson", "Confirmed the stimulus cable had been moved to HF2LI Signal Input 2", "Signal Input 2 topology for retained confirmations", "RG58-01 moved from Input 1 to Input 2 before the Input 2 acquisition block", "HF01-OPCONF-006", "ACCEPT_INPUT2_TOPOLOGY", "Timestamp is record time; session ordering establishes the move preceded the Input 2 acquisitions"],
        ["HF01-LEDGER-0061", "2026-08-26T23:40:53.949720Z", "Codex", "Refreshed electronic safe idle before timing-cable restoration", "T660 outputs disabled and Pico generator zero", "All guards pass", "HF01-PRE-RESTORATION-SAFE-STATE-001", "PASS_PRE_RESTORATION_SAFE_IDLE", "No laser action"],
        ["HF01-LEDGER-0062", "2026-08-26T23:34:58.7512426Z", "Christopher Robertson", "Disconnected RG58-01 from HF2LI Input 2", "HF2LI free of temporary stimulus", "RG58-01 remained attached to isolated tee", "HF01-OPCONF-007", "ACCEPT_RESTORATION_MOVE", "Generator already zero"],
        ["HF01-LEDGER-0063", "2026-08-26T23:36:01.9094099Z", "Christopher Robertson", "Disconnected stimulus tee from PicoScope SIGNAL OUT", "Generator physically isolated", "Both RG58 cables remained attached to tee", "HF01-OPCONF-008", "ACCEPT_RESTORATION_MOVE", ""],
        ["HF01-LEDGER-0064", "2026-08-26T23:39:55.9999470Z", "Christopher Robertson", "Disconnected RG58-02 from PicoScope channel A", "Temporary stimulus assembly isolated from instruments", "Both RG58 cables disconnected from instruments and retained on tee", "HF01-OPCONF-009", "ACCEPT_RESTORATION_MOVE", "Operator corrected a cable-ID typo"],
        ["HF01-LEDGER-0065", "2026-08-26T23:43:00.0037601Z", "Christopher Robertson", "Disconnected T660-2 B cable from PicoScope B", "Cable ready for default destination", "Cable remained at T660-2 B", "HF01-OPCONF-010", "ACCEPT_RESTORATION_MOVE", "Safe idle verified"],
        ["HF01-LEDGER-0066", "2026-08-26T23:43:21.6217601Z", "Christopher Robertson", "Connected T660-2 B to MIRcat TRIG IN", "Default B route restored", "Connection confirmed", "HF01-OPCONF-011", "RESTORE_DEFAULT_ROUTE", "Output remained disabled"],
        ["HF01-LEDGER-0067", "2026-08-26T23:47:27.8326649Z", "Christopher Robertson", "Disconnected T660-2 D cable from PicoScope EXT", "Cable ready for default destination", "Cable remained at T660-2 D", "HF01-OPCONF-012", "ACCEPT_RESTORATION_MOVE", "Safe idle verified"],
        ["HF01-LEDGER-0068", "2026-08-26T23:47:50.4799516Z", "Christopher Robertson", "Connected T660-2 D to T660-1 TRIG IN", "Default D route restored", "Connection confirmed", "HF01-OPCONF-013", "RESTORE_DEFAULT_ROUTE", "Outputs remained disabled"],
        ["HF01-LEDGER-0069", "2026-08-26T23:48:22.5562080Z", "Christopher Robertson", "Confirmed default wiring configuration", "All default routes restored and temporary assembly removed", "Default wiring confirmed", "HF01-OPCONF-014", "ACCEPT_PHYSICAL_RESTORATION", "Standing default exclusions imported without repetitive questioning"],
        ["HF01-LEDGER-0070", "2026-08-26T23:49:00.839654Z", "Codex", "Attempted final electronic restoration readback", "Verify all devices after physical restoration", "Windows denied COM3 access before readback", "HF01-FINAL-RESTORATION-STATE-001", "RETAIN_FAILED_ATTEMPT_AND_RETRY", "No hardware state inferred"],
        ["HF01-LEDGER-0071", "2026-08-26T23:49:42.437171Z", "Codex", "Repeated final electronic restoration readback under a new stable ID", "T660 safe idle Pico zero HF2 settings exact and flags clean", "All final guards pass", "HF01-FINAL-RESTORATION-STATE-R1-001", "PASS_FINAL_RESTORATION", "No later phase or promotion"],
    ]
    dictionaries = [dict(zip(LEDGER_HEADERS, row, strict=True)) for row in additions]
    append_unique(rows, ("ledger_id",), dictionaries)
    write_csv(path, LEDGER_HEADERS, rows)


def build_links() -> None:
    path = HERE / "calibration_links.csv"
    rows = read_csv(path)
    additions = []
    for quantity, source, validity, notes in (
        ("HF01-SWEEP-SELECTED-001", "selected_configurations.json", "PROVISIONAL_VALID_WITH_ENVELOPE", "Electrical response and restorable settings; AR-01 retains final optical feature-tolerance authority."),
        ("HF01-HRP-SELECTED-001", "selected_configurations.json", "PROVISIONAL_VALID_WITH_ENVELOPE", "Numeric alias of sweep settings with a separate HRP applicability envelope."),
        ("HF01-MBCO-SELECTED-001", "selected_configurations.json", "LIMITED_OUTSIDE_MANDATORY_1US", "Fastest valid HF2LI boundary setting; not valid for the mandatory 1 us claim."),
        ("HF01-DUAL-DEMOD-MODEL-v3", "analysis/hf01_dual_demod_model_validation_results.json", "VALID", "Three sparse anchors pass the frozen manufacturer-model criterion."),
        ("HF01-TIMING-COPY-v3", "analysis/hf01_timing10_r3_results.json", "VALID", "Accepted acquisition is HF01-TIMING10-R5-001."),
    ):
        additions.append({"campaign_id": CAMPAIGN_ID, "phase_id": PHASE_ID, "phase_run_id": PHASE_RUN_ID,
                          "calibration_bundle_id": "HF01-PROVISIONAL-ELECTRICAL-RESPONSE-v1", "calibration_quantity_id": quantity,
                          "source_campaign_id": CAMPAIGN_ID, "source_phase_id": PHASE_ID, "source_artifact_id": source,
                          "value_used": "", "unit": "", "standard_uncertainty": "", "validity_status": validity, "notes": notes})
    append_unique(rows, ("calibration_bundle_id", "calibration_quantity_id"), additions)
    write_csv(path, LINK_HEADERS, rows)


def main() -> None:
    records = raw_records()
    missing = sorted(set(ACQUISITIONS) - set(records))
    if missing:
        raise RuntimeError(f"Missing retained raw records: {missing}")
    build_acquisitions(records)
    build_conditions(records)
    build_measurements()
    build_exclusions()
    build_ledger()
    build_links()


if __name__ == "__main__":
    main()
