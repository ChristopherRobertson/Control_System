"""Execute the operator-confirmed first nonzero HF-01 AWG measurement."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
import math
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.hf2li_service import HF2LIService  # noqa: E402
from control_app.devices.picoscope_service import PicoScopeService  # noqa: E402
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402


HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
SAFE_IDLE = REPO_ROOT / "instrument" / "recipes" / "safe_idle.yaml"
ACQUISITION_ID = "HF01-AWG-FIRST-ENABLE-R1-001"
WAVEFORM = "SINE"
FREQUENCY_HZ = 2_000_000.0
PROGRAMMED_VPP = 0.050000
PROGRAMMED_OFFSET_V = 0.0
PICO_RANGE_V = 0.100


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def analyze_connected_sine(
    raw_path: Path,
    *,
    maximum_adc: int,
    sample_interval_ns: float,
) -> dict[str, float | int]:
    with raw_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) < 4000:
        raise RuntimeError(f"First-enable capture has only {len(rows)} samples")
    retained = rows[-4000:]
    volts = [int(row["ch_a_adc"]) * PICO_RANGE_V / maximum_adc for row in retained]
    times = [
        index * sample_interval_ns * 1e-9 for index in range(len(retained))
    ]
    offset = sum(volts) / len(volts)
    sin_projection = 2.0 * sum(
        value * math.sin(2.0 * math.pi * FREQUENCY_HZ * time)
        for value, time in zip(volts, times)
    ) / len(volts)
    cos_projection = 2.0 * sum(
        value * math.cos(2.0 * math.pi * FREQUENCY_HZ * time)
        for value, time in zip(volts, times)
    ) / len(volts)
    amplitude_peak = math.hypot(sin_projection, cos_projection)
    predicted = [
        offset
        + sin_projection * math.sin(2.0 * math.pi * FREQUENCY_HZ * time)
        + cos_projection * math.cos(2.0 * math.pi * FREQUENCY_HZ * time)
        for time in times
    ]
    residual_rms = math.sqrt(
        sum((value - model) ** 2 for value, model in zip(volts, predicted))
        / len(volts)
    )
    return {
        "retained_samples": len(volts),
        "retained_cycles": len(volts) * sample_interval_ns * 1e-9 * FREQUENCY_HZ,
        "maximum_adc": maximum_adc,
        "pico_range_v": PICO_RANGE_V,
        "sine_fit_vpp": 2.0 * amplitude_peak,
        "dc_offset_v": offset,
        "observed_peak_absolute_v": max(abs(value) for value in volts),
        "sample_min_v": min(volts),
        "sample_max_v": max(volts),
        "sample_peak_to_peak_v": max(volts) - min(volts),
        "fit_residual_rms_v": residual_rms,
    }


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    status_path = RAW / "hf01_awg_first_enable_r1_status.json"
    if status_path.exists():
        raise FileExistsError(
            f"{ACQUISITION_ID} has already executed; use a new stable acquisition ID"
        )
    record: dict[str, object] = {
        "campaign_id": "system_recalibration_001",
        "phase_id": "HF-01",
        "acquisition_id": ACQUISITION_ID,
        "authorization_id": "HF01-AUTH-001",
        "bounded_repeat_authorization_id": "HF01-AUTH-AMEND-004",
        "first_nonzero_enable_confirmation_id": "HF01-OPCONF-005",
        "started_utc": now(),
        "status": "STARTED",
        "proposed_output": {
            "waveform": WAVEFORM,
            "frequency_hz": FREQUENCY_HZ,
            "pk_to_pk_v": PROGRAMMED_VPP,
            "offset_v": PROGRAMMED_OFFSET_V,
            "trigger": "NONE_CONTINUOUS",
        },
        "source_load": {
            "source_resistance_ohm": 50.0,
            "hf2li_impedance": "HIGH_Z_MINIMUM_500_KOHM",
            "picoscope_a_impedance": "HIGH_Z_NOMINAL_1_MOHM",
            "nominal_parallel_load_ohm": 500000.0,
            "conservative_parallel_load_ohm": 333333.3333333333,
            "expected_connected_vpp_open_voltage_interpretation": [0.0499925, 0.0499950],
            "measurement_guard_vpp": [0.040, 0.110],
        },
    }
    write(status_path, record)
    inventory = load_config_inventory(write_files=False)
    log = (HERE / "command_log.txt").open("a", encoding="utf-8")
    hf = HF2LIService(inventory.devices["hf2li"], command_log=log)
    pico_settings = {
        "resolution": "8BIT",
        "channels": {
            "A": {"enabled": True, "coupling": "DC", "range": "100MV", "analog_offset_v": 0.0},
            "B": {"enabled": False, "coupling": "DC", "range": "100MV", "analog_offset_v": 0.0},
        },
        "external_trigger": {
            "source": "A",
            "threshold_adc": 5000,
            "direction": 2,
            "delay_samples": 0,
            "auto_trigger_ms": 0,
        },
        "total_samples": 5000,
        "pre_trigger_samples": 1000,
        "timebase": 1,
        "timeout_s": 5.0,
    }
    pico = PicoScopeService(
        inventory.devices["picoscope"], pico_settings, command_log=log
    )
    hf_original: dict[str, float | int] = {}
    try:
        manager = TimingRecipeManager(inventory=inventory, command_log=log)
        safe_before = manager.apply_recipe(
            SAFE_IDLE, output_path=RAW / "hf01_awg_first_enable_pre_safe_idle.json"
        )
        record["t660_safe_idle_before"] = {
            "matches_recipe": safe_before.get("matches_recipe"),
            "mismatches": safe_before.get("mismatches"),
        }
        if safe_before.get("matches_recipe") is not True:
            raise RuntimeError("T660 safe idle did not match before first AWG enable")

        hf.connect()
        server = hf._require_server()
        device = hf.device_id
        input_base = f"/{device}/sigins/0"
        hf_original = {
            "ac": int(server.getInt(f"{input_base}/ac")),
            "imp50": int(server.getInt(f"{input_base}/imp50")),
            "diff": int(server.getInt(f"{input_base}/diff")),
            "range": float(server.getDouble(f"{input_base}/range")),
        }
        record["hf2li_input1_before"] = hf_original
        server.setInt(f"{input_base}/ac", 0)
        server.setInt(f"{input_base}/imp50", 0)
        server.setDouble(f"{input_base}/range", 1.0)
        server.sync()
        record["hf2li_input1_staged"] = {
            "ac": int(server.getInt(f"{input_base}/ac")),
            "imp50": int(server.getInt(f"{input_base}/imp50")),
            "diff": int(server.getInt(f"{input_base}/diff")),
            "range": float(server.getDouble(f"{input_base}/range")),
            "system_extclk": int(server.getInt(f"/{device}/system/extclk")),
            "dcm_lock_flag": int(server.getInt(f"/{device}/status/flags/dcmlock")),
            "adcclip_before": int(server.getInt(f"/{device}/status/flags/adcclip/0")),
        }
        staged = record["hf2li_input1_staged"]
        if staged["ac"] != 0 or staged["imp50"] != 0:  # type: ignore[index]
            raise RuntimeError(f"HF2LI Input 1 is not DC/high-impedance: {staged}")
        if staged["system_extclk"] != 1 or staged["dcm_lock_flag"] != 1:  # type: ignore[index]
            raise RuntimeError(f"HF2LI external clock is not selected and locked: {staged}")

        pico.open_unit()
        record["pico_zero_before"] = pico.disable_signal_generator()
        record["pico_sample_timing"] = pico.validate_sample_timing()
        maximum_adc = pico.get_maximum_adc_value()
        raw_path = RAW / "hf01_awg_first_enable_r1_pico.csv"
        record["enable_attempted_utc"] = now()
        record["pico_generator_applied"] = pico.configure_builtin_signal_generator(
            waveform=WAVEFORM,
            frequency_hz=FREQUENCY_HZ,
            pk_to_pk_v=PROGRAMMED_VPP,
            offset_v=PROGRAMMED_OFFSET_V,
        )
        record["nonzero_enabled_utc"] = now()
        record["picoscope_capture"] = pico.capture_block(raw_path)
        record["pico_zero_after_capture"] = pico.disable_signal_generator()
        record["nonzero_disabled_utc"] = now()
        timing = record["pico_sample_timing"]
        measurement = analyze_connected_sine(
            raw_path,
            maximum_adc=maximum_adc,
            sample_interval_ns=float(timing["sample_interval_ns"]),  # type: ignore[index]
        )
        record["connected_voltage_measurement"] = measurement
        record["hf2li_after_output"] = {
            "adcclip": int(server.getInt(f"/{device}/status/flags/adcclip/0")),
            "adc_min": float(server.getDouble(f"/{device}/status/adc0min")),
            "adc_max": float(server.getDouble(f"/{device}/status/adc0max")),
            "system_extclk": int(server.getInt(f"/{device}/system/extclk")),
            "dcm_lock_flag": int(server.getInt(f"/{device}/status/flags/dcmlock")),
        }
        overflow = int(record["picoscope_capture"]["overflow"])  # type: ignore[index]
        hard_stops = {
            "measured_vpp_above_0_120": float(measurement["sine_fit_vpp"]) > 0.120,
            "absolute_peak_above_0_070": float(measurement["observed_peak_absolute_v"]) > 0.070,
            "absolute_offset_above_0_010": abs(float(measurement["dc_offset_v"])) > 0.010,
            "picoscope_overflow": overflow != 0,
            "hf2li_adcclip": int(record["hf2li_after_output"]["adcclip"]) != 0,  # type: ignore[index]
        }
        guard_pass = (
            0.040 <= float(measurement["sine_fit_vpp"]) <= 0.110
            and abs(float(measurement["dc_offset_v"])) <= 0.005
            and not any(hard_stops.values())
        )
        record["hard_stops"] = hard_stops
        record["first_enable_guard_pass"] = guard_pass
        record["status"] = "PASS_FIRST_ENABLE_ENVELOPE" if guard_pass else "FAIL_FIRST_ENABLE_ENVELOPE"
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
            if hf_original:
                server = hf._require_server()
                input_base = f"/{hf.device_id}/sigins/0"
                server.setInt(f"{input_base}/ac", int(hf_original["ac"]))
                server.setInt(f"{input_base}/imp50", int(hf_original["imp50"]))
                server.setInt(f"{input_base}/diff", int(hf_original["diff"]))
                server.setDouble(f"{input_base}/range", float(hf_original["range"]))
                server.sync()
                record["hf2li_input1_restored"] = {
                    "ac": int(server.getInt(f"{input_base}/ac")),
                    "imp50": int(server.getInt(f"{input_base}/imp50")),
                    "diff": int(server.getInt(f"{input_base}/diff")),
                    "range": float(server.getDouble(f"{input_base}/range")),
                }
        except Exception as exc:
            record["hf2li_cleanup_error"] = str(exc)
        hf.close()
        try:
            manager = TimingRecipeManager(inventory=inventory, command_log=log)
            safe_after = manager.apply_recipe(
                SAFE_IDLE, output_path=RAW / "hf01_awg_first_enable_final_safe_idle.json"
            )
            record["t660_safe_idle_after"] = {
                "matches_recipe": safe_after.get("matches_recipe"),
                "mismatches": safe_after.get("mismatches"),
            }
        except Exception as exc:
            record["final_safe_idle_error"] = str(exc)
        log.close()
        record["finished_utc"] = now()
        write(status_path, record)
    print(json.dumps(record, indent=2, sort_keys=True))
    clean = (
        record.get("status") == "PASS_FIRST_ENABLE_ENVELOPE"
        and not any(key.endswith("_error") for key in record)
        and (record.get("t660_safe_idle_after") or {}).get("matches_recipe") is True
    )
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
