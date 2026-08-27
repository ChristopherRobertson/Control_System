"""Acquire one of the three HF-01 v3 paired-demodulator model anchors."""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import json
import math
from pathlib import Path
import sys
import threading
import time


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.hf2li_service import HF2LIService  # noqa: E402
from control_app.devices.picoscope_service import PicoScopeService  # noqa: E402
from control_app.devices.t660_service import T660Service  # noqa: E402
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402


HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
SAFE_IDLE = REPO_ROOT / "recipes" / "safe_idle.yaml"
CARRIER_HZ = 2_000_000.0
REFERENCE_HZ = 2_000_013.927086657
PROGRAMMED_VPP = 0.050000
PICO_A_RANGE_V = 0.100
PICO_B_RANGE_V = 10.0

ANCHORS = {
    "fast": {
        "acquisition_id": "HF01-ANCHOR-FAST-V3-001",
        "order": 1,
        "tau_s": 4e-6,
        "predicted_cutoff_hz": 39800.0,
        "requested_rate_sps": 230000.0,
        "offsets_hz": [3980.0, 39800.0, 199000.0],
        "zero_dwell_s": 0.05,
        "step_dwell_s": 0.02,
        "minimum_offset_dwell_s": 0.03,
        "poll_duration_s": 6.0,
    },
    "intermediate": {
        "acquisition_id": "HF01-ANCHOR-INTERMEDIATE-V3-001",
        "order": 4,
        "tau_s": 1e-3,
        "predicted_cutoff_hz": 69.2,
        "requested_rate_sps": 2000.0,
        "offsets_hz": [6.92, 69.2, 346.0, -69.2],
        "zero_dwell_s": 0.20,
        "step_dwell_s": 0.10,
        "minimum_offset_dwell_s": 0.05,
        "poll_duration_s": 8.0,
    },
    "slow": {
        "acquisition_id": "HF01-ANCHOR-SLOW-V3-001",
        "order": 8,
        "tau_s": 0.1,
        "predicted_cutoff_hz": 0.479,
        "requested_rate_sps": 100.0,
        "offsets_hz": [0.0479, 0.479, 2.395],
        "zero_dwell_s": 5.0,
        "step_dwell_s": 2.0,
        "minimum_offset_dwell_s": 2.5,
        "poll_duration_s": 108.0,
    },
}
ANCHORS["slow_r1"] = {
    **ANCHORS["slow"],
    "acquisition_id": "HF01-ANCHOR-SLOW-V3-R1-001",
}
ANCHORS.update(
    {
        "selected_sweep_hrp_in1": {
            "acquisition_id": "HF01-SELECTED-SWEEP-HRP-IN1-001",
            "order": 4,
            "tau_s": 1e-3,
            "predicted_cutoff_hz": 69.09862123437,
            "requested_rate_sps": 899.4654605263158,
            "offsets_hz": [6.909862123437, 69.09862123437, 345.49310617185],
            "zero_dwell_s": 0.25,
            "step_dwell_s": 0.12,
            "minimum_offset_dwell_s": 0.06,
            "poll_duration_s": 9.0,
            "input_index": 0,
            "test_demod_index": 0,
            "reference_demod_index": 1,
            "range_v": 1.0,
            "differential": 0,
            "selected_configuration_ids": ["HF01-SWEEP-SELECTED-001", "HF01-HRP-SELECTED-001"],
            "confirmation_role": "selected_rate",
        },
        "lower_sweep_hrp_in1": {
            "acquisition_id": "HF01-LOWER-SWEEP-HRP-IN1-001",
            "order": 4,
            "tau_s": 1e-3,
            "predicted_cutoff_hz": 69.09862123437,
            "requested_rate_sps": 449.7327302631579,
            "offsets_hz": [6.909862123437, 69.09862123437, 345.49310617185],
            "zero_dwell_s": 0.25,
            "step_dwell_s": 0.12,
            "minimum_offset_dwell_s": 0.06,
            "poll_duration_s": 9.0,
            "input_index": 0,
            "test_demod_index": 0,
            "reference_demod_index": 1,
            "range_v": 1.0,
            "differential": 0,
            "selected_configuration_ids": ["HF01-SWEEP-SELECTED-001", "HF01-HRP-SELECTED-001"],
            "confirmation_role": "immediately_lower_rate",
        },
        "selected_mbco_in1": {
            "acquisition_id": "HF01-SELECTED-MBCO-IN1-001",
            "order": 1,
            "tau_s": 5.6e-6,
            "predicted_cutoff_hz": 28420.436902731715,
            "requested_rate_sps": 230263.15789473685,
            "offsets_hz": [2842.0436902731715, 28420.436902731715, 142102.18451365858],
            "zero_dwell_s": 0.06,
            "step_dwell_s": 0.025,
            "minimum_offset_dwell_s": 0.035,
            "poll_duration_s": 7.0,
            "input_index": 0,
            "test_demod_index": 0,
            "reference_demod_index": 1,
            "range_v": 1.0,
            "differential": 0,
            "selected_configuration_ids": ["HF01-MBCO-SELECTED-001"],
            "confirmation_role": "selected_rate",
        },
        "lower_mbco_in1": {
            "acquisition_id": "HF01-LOWER-MBCO-IN1-001",
            "order": 1,
            "tau_s": 5.6e-6,
            "predicted_cutoff_hz": 28420.436902731715,
            "requested_rate_sps": 115131.57894736843,
            "offsets_hz": [2842.0436902731715, 28420.436902731715, 142102.18451365858],
            "zero_dwell_s": 0.06,
            "step_dwell_s": 0.025,
            "minimum_offset_dwell_s": 0.035,
            "poll_duration_s": 7.0,
            "input_index": 0,
            "test_demod_index": 0,
            "reference_demod_index": 1,
            "range_v": 1.0,
            "differential": 0,
            "selected_configuration_ids": ["HF01-MBCO-SELECTED-001"],
            "confirmation_role": "immediately_lower_rate",
        },
        "selected_sweep_hrp_in2": {
            "acquisition_id": "HF01-SELECTED-SWEEP-HRP-IN2-001",
            "order": 4,
            "tau_s": 1e-3,
            "predicted_cutoff_hz": 69.09862123437,
            "requested_rate_sps": 899.4654605263158,
            "offsets_hz": [6.909862123437, 69.09862123437, 345.49310617185],
            "zero_dwell_s": 0.25,
            "step_dwell_s": 0.12,
            "minimum_offset_dwell_s": 0.06,
            "poll_duration_s": 9.0,
            "input_index": 1,
            "test_demod_index": 3,
            "reference_demod_index": 4,
            "range_v": 1.0,
            "differential": 0,
            "selected_configuration_ids": ["HF01-SWEEP-SELECTED-001", "HF01-HRP-SELECTED-001"],
            "confirmation_role": "signal_input_2_equivalence",
        },
        "selected_mbco_in2": {
            "acquisition_id": "HF01-SELECTED-MBCO-IN2-001",
            "order": 1,
            "tau_s": 5.6e-6,
            "predicted_cutoff_hz": 28420.436902731715,
            "requested_rate_sps": 230263.15789473685,
            "offsets_hz": [2842.0436902731715, 28420.436902731715, 142102.18451365858],
            "zero_dwell_s": 0.06,
            "step_dwell_s": 0.025,
            "minimum_offset_dwell_s": 0.035,
            "poll_duration_s": 7.0,
            "input_index": 1,
            "test_demod_index": 3,
            "reference_demod_index": 4,
            "range_v": 1.0,
            "differential": 0,
            "selected_configuration_ids": ["HF01-MBCO-SELECTED-001"],
            "confirmation_role": "signal_input_2_equivalence",
        },
        "range_low_in2": {
            "acquisition_id": "HF01-RANGE-LOW-IN2-001",
            "order": 4,
            "tau_s": 1e-3,
            "predicted_cutoff_hz": 69.09862123437,
            "requested_rate_sps": 899.4654605263158,
            "offsets_hz": [6.909862123437, 69.09862123437, 345.49310617185],
            "zero_dwell_s": 0.25,
            "step_dwell_s": 0.12,
            "minimum_offset_dwell_s": 0.06,
            "poll_duration_s": 9.0,
            "input_index": 1,
            "test_demod_index": 3,
            "reference_demod_index": 4,
            "range_v": 1.0,
            "differential": 0,
            "programmed_vpp": 0.010,
            "connected_vpp_min": 0.007,
            "connected_vpp_max": 0.025,
            "selected_configuration_ids": ["HF01-SWEEP-SELECTED-001", "HF01-HRP-SELECTED-001", "HF01-MBCO-SELECTED-001"],
            "confirmation_role": "signal_input_2_range_low_endpoint",
        },
        "range_high_in2": {
            "acquisition_id": "HF01-RANGE-HIGH-IN2-001",
            "order": 4,
            "tau_s": 1e-3,
            "predicted_cutoff_hz": 69.09862123437,
            "requested_rate_sps": 899.4654605263158,
            "offsets_hz": [6.909862123437, 69.09862123437, 345.49310617185],
            "zero_dwell_s": 0.25,
            "step_dwell_s": 0.12,
            "minimum_offset_dwell_s": 0.06,
            "poll_duration_s": 9.0,
            "input_index": 1,
            "test_demod_index": 3,
            "reference_demod_index": 4,
            "range_v": 1.0,
            "differential": 0,
            "programmed_vpp": 0.100,
            "connected_vpp_min": 0.080,
            "connected_vpp_max": 0.115,
            "selected_configuration_ids": ["HF01-SWEEP-SELECTED-001", "HF01-HRP-SELECTED-001", "HF01-MBCO-SELECTED-001"],
            "confirmation_role": "signal_input_2_range_high_endpoint",
        },
    }
)


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def solve_three(matrix: list[list[float]], vector: list[float]) -> list[float]:
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-18:
            raise RuntimeError("Singular sine-fit matrix")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [value / scale for value in augmented[column]]
        for row in range(3):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                value - factor * reference
                for value, reference in zip(augmented[row], augmented[column])
            ]
    return [augmented[row][3] for row in range(3)]


def analyze_pico_capture(
    path: Path,
    *,
    frequency_hz: float | None,
    maximum_adc: int,
    sample_interval_ns: float,
) -> dict[str, float | int | None]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    retained = rows[-4000:]
    a = [int(row["ch_a_adc"]) * PICO_A_RANGE_V / maximum_adc for row in retained]
    b = [int(row["ch_b_adc"]) * PICO_B_RANGE_V / maximum_adc for row in retained]
    result: dict[str, float | int | None] = {
        "retained_samples": len(retained),
        "a_mean_v": sum(a) / len(a),
        "a_rms_v": math.sqrt(sum(value * value for value in a) / len(a)),
        "a_sample_vpp": max(a) - min(a),
        "a_peak_absolute_v": max(abs(value) for value in a),
        "b_sample_vpp": max(b) - min(b),
        "sine_fit_vpp": None,
        "sine_fit_offset_v": None,
        "sine_fit_residual_rms_v": None,
    }
    if frequency_hz is None:
        return result
    times = [index * sample_interval_ns * 1e-9 for index in range(len(a))]
    sine = [math.sin(2.0 * math.pi * frequency_hz * value) for value in times]
    cosine = [math.cos(2.0 * math.pi * frequency_hz * value) for value in times]
    design = [sine, cosine, [1.0] * len(a)]
    normal = [
        [sum(left * right for left, right in zip(design[i], design[j])) for j in range(3)]
        for i in range(3)
    ]
    target = [sum(term * value for term, value in zip(column, a)) for column in design]
    sin_coefficient, cos_coefficient, offset = solve_three(normal, target)
    predicted = [
        sin_coefficient * s + cos_coefficient * c + offset
        for s, c in zip(sine, cosine)
    ]
    result.update(
        {
            "sine_fit_vpp": 2.0 * math.hypot(sin_coefficient, cos_coefficient),
            "sine_fit_offset_v": offset,
            "sine_fit_phase_rad": math.atan2(cos_coefficient, sin_coefficient),
            "sine_fit_residual_rms_v": math.sqrt(
                sum((value - model) ** 2 for value, model in zip(a, predicted)) / len(a)
            ),
        }
    )
    return result


def snapshot_nodes(server, device: str, nodes: list[tuple[str, str]]) -> dict[str, float | int]:
    result: dict[str, float | int] = {}
    for suffix, kind in nodes:
        path = f"/{device}/{suffix}"
        result[suffix] = (
            int(server.getInt(path)) if kind == "int" else float(server.getDouble(path))
        )
    return result


def restore_nodes(server, device: str, snapshot: dict[str, float | int], nodes: list[tuple[str, str]]) -> None:
    if "plls/0/enable" in snapshot:
        server.setInt(f"/{device}/plls/0/enable", 0)
    for suffix, kind in nodes:
        if suffix not in snapshot or suffix == "plls/0/enable":
            continue
        path = f"/{device}/{suffix}"
        if kind == "int":
            server.setInt(path, int(snapshot[suffix]))
        else:
            server.setDouble(path, float(snapshot[suffix]))
    if "plls/0/enable" in snapshot:
        server.setInt(f"/{device}/plls/0/enable", int(snapshot["plls/0/enable"]))
    server.sync()


def main(anchor_name: str) -> int:
    plan = ANCHORS[anchor_name]
    input_index = int(plan.get("input_index", 0))
    test_demod_index = int(plan.get("test_demod_index", 0))
    reference_demod_index = int(plan.get("reference_demod_index", 1))
    programmed_vpp = float(plan.get("programmed_vpp", PROGRAMMED_VPP))
    connected_vpp_min = float(plan.get("connected_vpp_min", 0.040))
    connected_vpp_max = float(plan.get("connected_vpp_max", 0.110))
    acquisition_id = str(plan["acquisition_id"])
    stem = acquisition_id.lower().replace("-", "_")
    status_path = RAW / f"{stem}_status.json"
    if status_path.exists():
        raise FileExistsError(f"{acquisition_id} already exists; use a new stable ID")
    RAW.mkdir(parents=True, exist_ok=True)
    record: dict[str, object] = {
        "campaign_id": "system_recalibration_001",
        "phase_id": "HF-01",
        "acquisition_id": acquisition_id,
        "authorization_id": "HF01-AUTH-001",
        "bounded_repeat_authorization_id": "HF01-AUTH-AMEND-005",
        "criterion_version": "HF01-MODEL-RESIDUAL-v3",
        "plan_version": "HF01-PLAN-v3",
        "validation_design_version": "HF01-VALIDATION-DESIGN-v3",
        "anchor_name": anchor_name,
        "anchor_plan": plan,
        "confirmation_role": plan.get("confirmation_role"),
        "selected_configuration_ids": plan.get("selected_configuration_ids", []),
        "reference_frequency_hz": REFERENCE_HZ,
        "reference_frequency_source_analysis_id": "HF01-ANALYSIS-REFERENCE-REFINEMENT-001",
        "experiment_identity": None,
        "started_utc": now(),
        "status": "STARTED",
        "segments": [],
    }
    write(status_path, record)
    inventory = load_config_inventory(write_files=False)
    log = (HERE / "command_log.txt").open("a", encoding="utf-8")
    hf_control = HF2LIService(inventory.devices["hf2li"], command_log=log)
    hf_data = HF2LIService(inventory.devices["hf2li"], command_log=log)
    t660 = T660Service("t660_2", inventory.t660_devices["t660_2"], command_log=log)
    pico_settings = {
        "resolution": "8BIT",
        "channels": {
            "A": {"enabled": True, "coupling": "DC", "range": "100MV", "analog_offset_v": 0.0},
            "B": {"enabled": True, "coupling": "DC", "range": "10V", "analog_offset_v": 0.0},
        },
        "external_trigger": {
            "source": "A",
            "threshold_adc": 5000,
            "direction": 2,
            "delay_samples": 0,
            "auto_trigger_ms": 100,
        },
        "total_samples": 5000,
        "pre_trigger_samples": 1000,
        "timebase": 1,
        "timeout_s": 5.0,
    }
    pico = PicoScopeService(inventory.devices["picoscope"], pico_settings, command_log=log)
    node_spec = [
        ("dios/0/drive", "int"),
        ("oscs/0/freq", "double"),
        (f"sigins/{input_index}/ac", "int"),
        (f"sigins/{input_index}/imp50", "int"),
        (f"sigins/{input_index}/diff", "int"),
        (f"sigins/{input_index}/range", "double"),
        ("plls/0/enable", "int"),
        ("plls/0/adcselect", "int"),
        ("plls/0/freqcenter", "double"),
        ("plls/0/harmonic", "int"),
        ("plls/0/order", "int"),
        ("plls/0/adcthreshold", "int"),
        *[(f"demods/{index}/{suffix}", kind) for index in (test_demod_index, reference_demod_index) for suffix, kind in (("enable", "int"), ("adcselect", "int"), ("oscselect", "int"), ("harmonic", "int"), ("order", "int"), ("timeconstant", "double"), ("rate", "double"), ("trigger", "int"))],
    ]
    original: dict[str, float | int] = {}
    data_thread: threading.Thread | None = None
    data_result: dict[str, object] = {}
    data_errors: list[str] = []
    poll_entered = threading.Event()
    try:
        manager = TimingRecipeManager(inventory=inventory, command_log=log)
        safe = manager.apply_recipe(SAFE_IDLE, output_path=RAW / f"{stem}_pre_safe_idle.json")
        if safe.get("matches_recipe") is not True:
            raise RuntimeError("T660 safe idle mismatch before anchor")
        record["t660_safe_idle_before"] = {"matches_recipe": True, "mismatches": []}

        hf_control.connect()
        hf_data.connect()
        server = hf_control._require_server()
        device = hf_control.device_id
        original = snapshot_nodes(server, device, node_spec)
        record["hf2li_before"] = original
        record["clock_before"] = {
            "clockbase_hz": hf_control.get_clockbase(),
            "system_extclk": int(server.getInt(f"/{device}/system/extclk")),
            "pll_lock_flag": int(server.getInt(f"/{device}/status/flags/plllock")),
            "dcm_lock_flag": int(server.getInt(f"/{device}/status/flags/dcmlock")),
            "lock_flag_semantics": "zero_is_locked_per_HF2_node_documentation",
        }
        if not (
            record["clock_before"]["system_extclk"] == 1  # type: ignore[index]
            and record["clock_before"]["pll_lock_flag"] == 0  # type: ignore[index]
            and record["clock_before"]["dcm_lock_flag"] == 0  # type: ignore[index]
        ):
            raise RuntimeError(f"HF2LI external master clock is not locked: {record['clock_before']}")

        t660.connect()
        t660.command("STOP", expect_response=False)
        t660.set_trigger_source("OFF")
        for channel in "ABCD":
            t660.disable_channel(channel)
        t660.force_eod()
        for channel in "AB":
            t660.set_channel_delay_width(channel, "0ns", "150ns")
            t660.command(f"CHAN:POS {channel}", expect_response=False)
            t660.command(f"CHAN:50OHM {channel}", expect_response=False)
            t660.enable_channel(channel)
        t660.set_clock_mode(frequency=f"{REFERENCE_HZ:.9f}Hz", shots=0)
        t660.set_trigger_source("SYN")
        t660.command("START", expect_response=False)
        record["t660_reference_started_utc"] = now()

        server.setInt(f"/{device}/dios/0/drive", 0)
        server.setInt(f"/{device}/sigins/{input_index}/ac", 0)
        server.setInt(f"/{device}/sigins/{input_index}/imp50", 0)
        server.setInt(f"/{device}/sigins/{input_index}/diff", int(plan.get("differential", 1)))
        server.setDouble(f"/{device}/sigins/{input_index}/range", float(plan.get("range_v", 0.1)))
        server.setInt(f"/{device}/plls/0/enable", 0)
        server.setInt(f"/{device}/plls/0/adcselect", 4)
        server.setDouble(f"/{device}/oscs/0/freq", REFERENCE_HZ)
        server.setDouble(f"/{device}/plls/0/freqcenter", REFERENCE_HZ)
        server.setInt(f"/{device}/plls/0/harmonic", 1)
        server.setInt(f"/{device}/plls/0/order", 4)
        server.setInt(f"/{device}/plls/0/adcthreshold", 0)
        server.setInt(f"/{device}/plls/0/enable", 1)
        test_demod = f"/{device}/demods/{test_demod_index}"
        reference_demod = f"/{device}/demods/{reference_demod_index}"
        minimum_timeconstant_s = float(
            server.getDouble(f"/{device}/system/properties/mintimeconstant")
        )
        for demod_path in (test_demod, reference_demod):
            server.setInt(f"{demod_path}/enable", 0)
            server.setInt(f"{demod_path}/adcselect", input_index)
            server.setInt(f"{demod_path}/oscselect", 0)
            server.setInt(f"{demod_path}/harmonic", 1)
            server.setInt(f"{demod_path}/trigger", 0)
        server.setInt(f"{test_demod}/order", int(plan["order"]))
        server.setDouble(f"{test_demod}/timeconstant", float(plan["tau_s"]))
        server.setDouble(f"{test_demod}/rate", float(plan["requested_rate_sps"]))
        server.setInt(f"{reference_demod}/order", 1)
        server.setDouble(f"{reference_demod}/timeconstant", minimum_timeconstant_s)
        server.setDouble(
            f"{reference_demod}/rate", float(plan["requested_rate_sps"])
        )
        server.setInt(f"{test_demod}/enable", 1)
        server.setInt(f"{reference_demod}/enable", 1)
        server.sync()
        lock_deadline = time.time() + 8.0
        while time.time() < lock_deadline and int(server.getInt(f"/{device}/plls/0/locked")) != 1:
            time.sleep(0.05)
        if int(server.getInt(f"/{device}/plls/0/locked")) != 1:
            raise RuntimeError("HF2LI PLL0 did not lock to the T660-2 DIO0 reference")
        time.sleep(3.0)
        test_rate_sps = float(server.getDouble(f"{test_demod}/rate"))
        reference_rate_sps = float(server.getDouble(f"{reference_demod}/rate"))
        if abs(test_rate_sps - reference_rate_sps) > 1e-9 * max(
            test_rate_sps, reference_rate_sps, 1.0
        ):
            raise RuntimeError(
                "HF2LI test/reference output rates do not match: "
                f"{test_rate_sps} versus {reference_rate_sps}"
            )
        record["hf2li_staged"] = {
            "signal_input_index": input_index,
            "signal_input_ac": int(server.getInt(f"/{device}/sigins/{input_index}/ac")),
            "signal_input_imp50": int(server.getInt(f"/{device}/sigins/{input_index}/imp50")),
            "signal_input_diff": int(server.getInt(f"/{device}/sigins/{input_index}/diff")),
            "signal_input_range_v": float(server.getDouble(f"/{device}/sigins/{input_index}/range")),
            "pll0_locked": int(server.getInt(f"/{device}/plls/0/locked")),
            "pll0_frequency_hz": float(server.getDouble(f"/{device}/plls/0/freqcenter")),
            "osc0_frequency_hz": float(server.getDouble(f"/{device}/oscs/0/freq")),
            "order": int(server.getInt(f"{test_demod}/order")),
            "timeconstant_s": float(server.getDouble(f"{test_demod}/timeconstant")),
            "rate_sps": test_rate_sps,
            "test_demod": {
                "index": test_demod_index,
                "adcselect": int(server.getInt(f"{test_demod}/adcselect")),
                "oscselect": int(server.getInt(f"{test_demod}/oscselect")),
                "harmonic": int(server.getInt(f"{test_demod}/harmonic")),
                "order": int(server.getInt(f"{test_demod}/order")),
                "timeconstant_s": float(
                    server.getDouble(f"{test_demod}/timeconstant")
                ),
                "rate_sps": test_rate_sps,
                "trigger": int(server.getInt(f"{test_demod}/trigger")),
                "enable": int(server.getInt(f"{test_demod}/enable")),
            },
            "reference_demod": {
                "index": reference_demod_index,
                "adcselect": int(server.getInt(f"{reference_demod}/adcselect")),
                "oscselect": int(server.getInt(f"{reference_demod}/oscselect")),
                "harmonic": int(server.getInt(f"{reference_demod}/harmonic")),
                "order": int(server.getInt(f"{reference_demod}/order")),
                "timeconstant_s": float(
                    server.getDouble(f"{reference_demod}/timeconstant")
                ),
                "rate_sps": reference_rate_sps,
                "trigger": int(server.getInt(f"{reference_demod}/trigger")),
                "enable": int(server.getInt(f"{reference_demod}/enable")),
            },
            "locked_stabilization_s": 3.0,
            "external_clock": int(server.getInt(f"/{device}/system/extclk")),
            "pll_lock_flag": int(server.getInt(f"/{device}/status/flags/plllock")),
            "dcm_lock_flag": int(server.getInt(f"/{device}/status/flags/dcmlock")),
            "lock_flag_semantics": "zero_is_locked_per_HF2_node_documentation",
        }

        pico.open_unit()
        record["pico_zero_before"] = pico.disable_signal_generator()
        record["pico_sample_timing"] = pico.validate_sample_timing()
        maximum_adc = pico.get_maximum_adc_value()
        interval_ns = float(record["pico_sample_timing"]["sample_interval_ns"])  # type: ignore[index]

        hf_data.start_acquisition(demodulators=[test_demod_index, reference_demod_index], fields=["x", "y"])

        def read_data() -> None:
            try:
                poll_entered.set()
                result = hf_data.read_acquisition(float(plan["poll_duration_s"]))
                result["fields"] = ["x", "y"]
                result["demodulators"] = [test_demod_index, reference_demod_index]
                data_result["record"] = result
            except Exception as exc:
                data_errors.append(str(exc))

        data_thread = threading.Thread(target=read_data, name=f"hf01-{anchor_name}-poll")
        data_thread.start()
        if not poll_entered.wait(timeout=2.0):
            raise RuntimeError("HF2LI anchor poll did not start")
        time.sleep(0.2)

        segments: list[dict[str, object]] = record["segments"]  # type: ignore[assignment]

        def device_tick() -> int:
            return int(server.getInt(f"/{device}/status/time"))

        def set_zero(label: str) -> None:
            before = device_tick()
            applied = pico.disable_signal_generator()
            after = device_tick()
            segments.append({
                "label": label,
                "kind": "zero",
                "frequency_hz": 0.0,
                "programmed_vpp": 0.0,
                "device_tick_before": before,
                "device_tick_after": after,
                "utc": now(),
                "applied": applied,
            })

        def set_carrier(label: str, offset_hz: float) -> None:
            frequency = CARRIER_HZ + offset_hz
            before = device_tick()
            applied = pico.configure_builtin_signal_generator(
                waveform="SINE",
                frequency_hz=frequency,
                pk_to_pk_v=programmed_vpp,
                offset_v=0.0,
            )
            after = device_tick()
            segments.append({
                "label": label,
                "kind": "carrier" if offset_hz == 0 else "offset_carrier",
                "offset_hz": offset_hz,
                "frequency_hz": frequency,
                "programmed_vpp": programmed_vpp,
                "device_tick_before": before,
                "device_tick_after": after,
                "utc": now(),
                "applied": applied,
            })

        def capture_monitor(label: str, frequency_hz: float | None) -> dict[str, object]:
            path = RAW / f"{stem}_{label}_pico.csv"
            capture = pico.capture_block(path)
            analysis = analyze_pico_capture(
                path,
                frequency_hz=frequency_hz,
                maximum_adc=maximum_adc,
                sample_interval_ns=interval_ns,
            )
            if frequency_hz is not None:
                measured_vpp = float(analysis["sine_fit_vpp"] or 0.0)
                if not connected_vpp_min <= measured_vpp <= connected_vpp_max:
                    raise RuntimeError(f"Connected voltage guard failed at {label}: {measured_vpp} Vpp")
                if abs(float(analysis["sine_fit_offset_v"] or 0.0)) > 0.005:
                    raise RuntimeError(f"Connected offset guard failed at {label}: {analysis}")
            if int(capture["overflow"]) != 0:
                raise RuntimeError(f"PicoScope overflow at {label}")
            if int(server.getInt(f"/{device}/status/flags/adcclip/{input_index}")) != 0:
                raise RuntimeError(f"HF2LI ADC clipping at {label}")
            return {"capture": capture, "analysis": analysis}

        set_zero("zero_baseline")
        segments[-1]["monitor"] = capture_monitor("zero_baseline", None)
        time.sleep(float(plan["zero_dwell_s"]))

        for replicate in range(1, 4):
            rise_label = f"step_rise_{replicate}"
            set_carrier(rise_label, 0.0)
            segments[-1]["monitor"] = capture_monitor(rise_label, CARRIER_HZ)
            time.sleep(float(plan["step_dwell_s"]))
            fall_label = f"step_fall_{replicate}"
            set_zero(fall_label)
            segments[-1]["monitor"] = capture_monitor(fall_label, None)
            time.sleep(float(plan["step_dwell_s"]))

        for index, offset in enumerate(plan["offsets_hz"], start=1):  # type: ignore[union-attr]
            label = f"offset_{index}"
            set_carrier(label, float(offset))
            segments[-1]["monitor"] = capture_monitor(label, CARRIER_HZ + float(offset))
            dwell = max(
                float(plan["minimum_offset_dwell_s"]),
                3.0 / abs(float(offset)),
            )
            segments[-1]["dwell_s"] = dwell
            time.sleep(dwell)
            set_zero(f"offset_{index}_end_zero")
            time.sleep(0.2 if anchor_name.startswith("slow") else 0.02)

        record["pico_zero_after_segments"] = pico.disable_signal_generator()
        if data_thread is not None:
            data_thread.join(timeout=float(plan["poll_duration_s"]) + 10.0)
        if data_thread is not None and data_thread.is_alive():
            raise RuntimeError("HF2LI anchor poll did not finish")
        if data_errors:
            raise RuntimeError(data_errors[0])
        hf_data.stop_acquisition()
        hf_record = data_result.get("record")
        if not isinstance(hf_record, dict):
            raise RuntimeError("HF2LI anchor record missing")
        record["hf2li_export"] = hf_data.save_record(
            hf_record,
            raw_csv_path=RAW / f"{stem}_hf2_raw.csv",
            summary_csv_path=RAW / f"{stem}_hf2_summary.csv",
        )
        record["hf2li_after"] = {
            "adcclip": int(server.getInt(f"/{device}/status/flags/adcclip/{input_index}")),
            "demodsampleloss": int(server.getInt(f"/{device}/status/flags/demodsampleloss")),
            "pll_locked": int(server.getInt(f"/{device}/plls/0/locked")),
            "external_clock": int(server.getInt(f"/{device}/system/extclk")),
            "pll_lock_flag": int(server.getInt(f"/{device}/status/flags/plllock")),
            "dcm_lock_flag": int(server.getInt(f"/{device}/status/flags/dcmlock")),
            "lock_flag_semantics": "zero_is_locked_per_HF2_node_documentation",
        }
        if any(record["hf2li_after"][key] != 0 for key in ("adcclip", "demodsampleloss")):  # type: ignore[index]
            raise RuntimeError(f"HF2LI integrity flag after anchor: {record['hf2li_after']}")
        if not (
            record["hf2li_after"]["external_clock"] == 1  # type: ignore[index]
            and record["hf2li_after"]["pll_lock_flag"] == 0  # type: ignore[index]
            and record["hf2li_after"]["dcm_lock_flag"] == 0  # type: ignore[index]
        ):
            raise RuntimeError(f"HF2LI external master clock lost lock: {record['hf2li_after']}")
        record["status"] = "CAPTURED"
    except Exception as exc:
        record["status"] = "FAIL"
        record["error"] = str(exc)
    finally:
        try:
            if pico._is_open:
                record["pico_zero_final"] = pico.disable_signal_generator()
                pico.stop()
                pico.close_unit()
        except Exception as exc:
            record["pico_cleanup_error"] = str(exc)
        try:
            if data_thread is not None and data_thread.is_alive():
                data_thread.join(timeout=2.0)
            hf_data.stop_acquisition()
        except Exception as exc:
            record["hf2li_data_cleanup_error"] = str(exc)
        hf_data.close()
        try:
            if original:
                server = hf_control._require_server()
                restore_nodes(server, hf_control.device_id, original, node_spec)
                record["hf2li_restored"] = snapshot_nodes(
                    server, hf_control.device_id, node_spec
                )
        except Exception as exc:
            record["hf2li_restore_error"] = str(exc)
        hf_control.close()
        try:
            t660.command("STOP", expect_response=False)
            t660.set_trigger_source("OFF")
            for channel in "ABCD":
                t660.disable_channel(channel)
            t660.force_eod()
            record["t660_reference_shot_count"] = t660.get_shot_count()
        except Exception as exc:
            record["t660_cleanup_error"] = str(exc)
        t660.close()
        try:
            manager = TimingRecipeManager(inventory=inventory, command_log=log)
            safe = manager.apply_recipe(
                SAFE_IDLE, output_path=RAW / f"{stem}_final_safe_idle.json"
            )
            record["t660_safe_idle_after"] = {
                "matches_recipe": safe.get("matches_recipe"),
                "mismatches": safe.get("mismatches"),
            }
        except Exception as exc:
            record["final_safe_idle_error"] = str(exc)
        log.close()
        record["finished_utc"] = now()
        write(status_path, record)
    print(json.dumps(record, indent=2, sort_keys=True))
    clean = (
        record.get("status") == "CAPTURED"
        and not any(key.endswith("_error") for key in record)
        and (record.get("t660_safe_idle_after") or {}).get("matches_recipe") is True
    )
    return 0 if clean else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("anchor", choices=tuple(ANCHORS))
    arguments = parser.parse_args()
    raise SystemExit(main(arguments.anchor))
