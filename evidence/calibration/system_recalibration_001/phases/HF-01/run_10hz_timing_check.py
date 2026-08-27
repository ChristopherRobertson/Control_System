"""Run one uniquely identified 10 Hz T660/Pico/HF2 DIO timing check."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import threading
import time


REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.hf2li_service import HF2LIService  # noqa: E402
from control_app.devices.picoscope_service import PicoScopeService  # noqa: E402
from control_app.devices.t660_service import T660Service  # noqa: E402
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402


HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
SAFE_IDLE = REPO_ROOT / "instrument" / "recipes" / "safe_idle.yaml"
ACQUISITION_ID = "HF01-TIMING10-R5-001"


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    inventory = load_config_inventory(write_files=False)
    record: dict[str, object] = {
        "campaign_id": "system_recalibration_001",
        "phase_id": "HF-01",
        "acquisition_id": ACQUISITION_ID,
        "authorization_id": "HF01-AUTH-001",
        "authorization_amendment_id": "HF01-AUTH-AMEND-004",
        "criterion_version": "HF01-TIMING-COPY-v3",
        "started_utc": now(),
        "purpose": "single bounded 10 Hz digital reference-copy and marker-copy timestamp check",
        "laser_state": "nonemitting; timing routes operator-confirmed away from MIRcat and T660-1",
        "awg_state": "PROGRAMMED_ZERO_OUTPUT",
        "requested_events": 10,
        "status": "STARTED",
    }
    status_path = RAW / "hf01_timing10_r5_status.json"
    if status_path.exists():
        raise FileExistsError(
            f"{ACQUISITION_ID} has already executed; use a new stable acquisition ID"
        )
    write(status_path, record)
    log = (HERE / "command_log.txt").open("a", encoding="utf-8")
    hf = HF2LIService(inventory.devices["hf2li"], command_log=log)
    t660 = T660Service("t660_2", inventory.t660_devices["t660_2"], command_log=log)
    pico_settings = {
        "resolution": "8BIT",
        "channels": {
            "A": {"enabled": True, "coupling": "DC", "range": "10V", "analog_offset_v": 0.0},
            "B": {"enabled": True, "coupling": "DC", "range": "10V", "analog_offset_v": 0.0},
        },
        "external_trigger": {
            "source": "EXT",
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
    demod_original: dict[str, object] = {}
    hf_thread: threading.Thread | None = None
    hf_result: dict[str, object] = {}
    thread_errors: list[str] = []
    hf_poll_entered = threading.Event()
    try:
        hf.connect()
        server = hf._require_server()
        device = hf.device_id
        demod = f"/{device}/demods/2"
        demod_original = {
            "enable": int(server.getInt(f"{demod}/enable")),
            "rate": float(server.getDouble(f"{demod}/rate")),
            "trigger": int(server.getInt(f"{demod}/trigger")),
        }
        record["hf2li_before"] = {
            "device_id": device,
            "clockbase_hz": hf.get_clockbase(),
            "system_extclk": int(server.getInt(f"/{device}/system/extclk")),
            "pll_lock_flag": int(server.getInt(f"/{device}/status/flags/plllock")),
            "dcm_lock_flag": int(server.getInt(f"/{device}/status/flags/dcmlock")),
            "lock_flag_semantics": "zero_is_locked_per_HF2_node_documentation",
            "demod2": demod_original,
        }
        server.setInt(f"/{device}/system/extclk", 1)
        server.setDouble(f"{demod}/rate", 460000.0)
        server.setInt(f"{demod}/trigger", 0)
        server.setInt(f"{demod}/enable", 1)
        server.sync()
        clock_deadline = time.time() + 8.0
        while time.time() < clock_deadline:
            if (
                int(server.getInt(f"/{device}/system/extclk")) == 1
                and int(server.getInt(f"/{device}/status/flags/plllock")) == 0
                and int(server.getInt(f"/{device}/status/flags/dcmlock")) == 0
            ):
                break
            time.sleep(0.1)
        record["hf2li_staged"] = {
            "system_extclk": int(server.getInt(f"/{device}/system/extclk")),
            "pll_lock_flag": int(server.getInt(f"/{device}/status/flags/plllock")),
            "dcm_lock_flag": int(server.getInt(f"/{device}/status/flags/dcmlock")),
            "lock_flag_semantics": "zero_is_locked_per_HF2_node_documentation",
            "demod2_enable": int(server.getInt(f"{demod}/enable")),
            "demod2_rate_sps": float(server.getDouble(f"{demod}/rate")),
            "demod2_trigger": int(server.getInt(f"{demod}/trigger")),
        }
        if not (
            record["hf2li_staged"]["system_extclk"] == 1  # type: ignore[index]
            and record["hf2li_staged"]["pll_lock_flag"] == 0  # type: ignore[index]
            and record["hf2li_staged"]["dcm_lock_flag"] == 0  # type: ignore[index]
        ):
            raise RuntimeError(
                f"HF2LI external master clock did not lock: {record['hf2li_staged']}"
            )

        t660.connect()
        record["t660_identity"] = t660.identify()
        t660.command("STOP", expect_response=False)
        t660.set_trigger_source("OFF")
        for channel in "ABCD":
            t660.disable_channel(channel)
        t660.force_eod()
        for channel in "ABCD":
            t660.set_channel_delay_width(channel, "0ns", "1ms")
            t660.command(f"CHAN:POS {channel}", expect_response=False)
            t660.command(f"CHAN:50OHM {channel}", expect_response=False)
            t660.enable_channel(channel)
        t660.set_clock_mode(frequency="10Hz", shots=0)
        record["t660_staged_readback"] = t660.read_active_settings()
        record["t660_shot_count_before"] = t660.get_shot_count()

        hf.start_acquisition(demodulators=[2], fields=["dio"])

        def read_hf() -> None:
            try:
                record["hf2li_poll_called_utc"] = now()
                hf_poll_entered.set()
                hf_result["record"] = hf.read_acquisition(1.3)
                record["hf2li_poll_returned_utc"] = now()
            except Exception as exc:
                thread_errors.append(str(exc))

        pico.open_unit()
        record["pico_zero_before"] = pico.disable_signal_generator()

        def start_timing() -> None:
            nonlocal hf_thread
            hf_thread = threading.Thread(target=read_hf, name="hf01-dio-poll")
            hf_thread.start()
            if not hf_poll_entered.wait(timeout=2.0):
                raise RuntimeError("HF2LI DIO poll did not enter before T660 start")
            time.sleep(0.1)
            t660.set_trigger_source("SYN")
            t660.command("START", expect_response=False)
            record["t660_started_utc"] = now()

        record["picoscope_capture"] = pico.capture_rapid_blocks(
            RAW / "hf01_timing10_r5_pico_rapid.csv",
            capture_count=10,
            after_arm=start_timing,
        )
        t660.command("STOP", expect_response=False)
        record["t660_stopped_utc"] = now()
        record["t660_shot_count_after"] = t660.get_shot_count()
        record["pico_zero_after"] = pico.disable_signal_generator()
        if hf_thread is not None:
            hf_thread.join(timeout=5.0)
        if hf_thread is not None and hf_thread.is_alive():
            raise RuntimeError("HF2LI DIO poll thread did not finish")
        if thread_errors:
            raise RuntimeError(thread_errors[0])
        hf.stop_acquisition()
        dio_record = hf_result.get("record")
        if not isinstance(dio_record, dict):
            raise RuntimeError("HF2LI DIO record is missing")
        dio_record["fields"] = ["dio"]
        hf2_raw_path = RAW / "hf01_timing10_r5_hf2_raw.csv"
        record["hf2li_export"] = hf.save_record(
            dio_record,
            raw_csv_path=hf2_raw_path,
            summary_csv_path=RAW / "hf01_timing10_r5_hf2_summary.csv",
        )
        if record["hf2li_export"]["path_count"] != 1:  # type: ignore[index]
            raise RuntimeError(
                f"HF2LI DIO export path count was not one: {record['hf2li_export']}"
            )
        with hf2_raw_path.open(newline="", encoding="utf-8") as handle:
            dio_samples = [
                (int(row["timestamp"]), int(float(row["value"])))
                for row in csv.DictReader(handle)
            ]
        dio_values = [value for _, value in dio_samples]

        def rising_edge_timestamps(bit: int) -> list[int]:
            return [
                current_timestamp
                for (_, previous), (current_timestamp, current) in zip(
                    dio_samples, dio_samples[1:]
                )
                if (previous & bit) == 0 and (current & bit) != 0
            ]

        dio0_edges = rising_edge_timestamps(0x1)
        dio1_edges = rising_edge_timestamps(0x2)
        clockbase_hz = int(record["hf2li_before"]["clockbase_hz"])  # type: ignore[index]
        last_copy_edge = max(dio0_edges + dio1_edges) if dio0_edges or dio1_edges else None
        stream_margin_after_last_edge_s = (
            (dio_samples[-1][0] - last_copy_edge) / clockbase_hz
            if dio_samples and last_copy_edge is not None
            else None
        )
        record["hf2li_dio_validation"] = {
            "samples": len(dio_values),
            "dio0_high_samples": sum((value & 0x1) != 0 for value in dio_values),
            "dio1_high_samples": sum((value & 0x2) != 0 for value in dio_values),
            "dio0_rising_edges": len(dio0_edges),
            "dio1_rising_edges": len(dio1_edges),
            "dio0_rising_timestamps": dio0_edges,
            "dio1_rising_timestamps": dio1_edges,
            "dio1_minus_dio0_edge_ticks": [
                dio1 - dio0 for dio0, dio1 in zip(dio0_edges, dio1_edges)
            ],
            "stream_margin_after_last_copy_edge_s": stream_margin_after_last_edge_s,
        }
        if len(dio0_edges) != 10 or len(dio1_edges) != 10:
            raise RuntimeError(
                "HF2LI DIO rising-edge mismatch "
                f"DIO0={len(dio0_edges)} DIO1={len(dio1_edges)}; expected exactly 10 each"
            )
        if stream_margin_after_last_edge_s is None or stream_margin_after_last_edge_s < 0.1:
            raise RuntimeError(
                "HF2LI DIO stream margin after final edge was "
                f"{stream_margin_after_last_edge_s}; expected at least 0.1 s"
            )
        capture = record["picoscope_capture"]
        if capture["processed_captures"] != 10:  # type: ignore[index]
            raise RuntimeError(f"PicoScope processed capture count was {capture}")
        if any(capture["overflow_by_capture"]):  # type: ignore[index]
            raise RuntimeError(f"PicoScope overflow in timing check: {capture}")
        if record["t660_shot_count_before"] != 0 or record["t660_shot_count_after"] != 10:
            raise RuntimeError(
                f"T660 shot-count mismatch before={record['t660_shot_count_before']} after={record['t660_shot_count_after']}"
            )
        record["status"] = "CAPTURED_EXACTLY_10_EVENTS"
    except Exception as exc:
        record["status"] = "FAIL"
        record["error"] = str(exc)
    finally:
        try:
            if pico._is_open:
                pico.disable_signal_generator()
                pico.stop()
                pico.close_unit()
        except Exception as exc:
            record["pico_cleanup_error"] = str(exc)
        try:
            t660.command("STOP", expect_response=False)
            t660.set_trigger_source("OFF")
            for channel in "ABCD":
                t660.disable_channel(channel)
            t660.force_eod()
            record["t660_post_readback"] = t660.read_active_settings()
        except Exception as exc:
            record["t660_cleanup_error"] = str(exc)
        t660.close()
        try:
            if hf_thread is not None and hf_thread.is_alive():
                hf_thread.join(timeout=2.0)
            hf.stop_acquisition()
            if demod_original:
                server = hf._require_server()
                demod = f"/{hf.device_id}/demods/2"
                server.setInt(f"{demod}/enable", int(demod_original["enable"]))
                server.setDouble(f"{demod}/rate", float(demod_original["rate"]))
                server.setInt(f"{demod}/trigger", int(demod_original["trigger"]))
                server.sync()
                record["hf2li_demod2_restored"] = {
                    "enable": int(server.getInt(f"{demod}/enable")),
                    "rate": float(server.getDouble(f"{demod}/rate")),
                    "trigger": int(server.getInt(f"{demod}/trigger")),
                }
                record["hf2li_external_clock_retained"] = int(
                    server.getInt(f"/{hf.device_id}/system/extclk")
                )
                record["hf2li_master_clock_final"] = {
                    "system_extclk": int(server.getInt(f"/{hf.device_id}/system/extclk")),
                    "pll_lock_flag": int(
                        server.getInt(f"/{hf.device_id}/status/flags/plllock")
                    ),
                    "dcm_lock_flag": int(
                        server.getInt(f"/{hf.device_id}/status/flags/dcmlock")
                    ),
                    "lock_flag_semantics": "zero_is_locked_per_HF2_node_documentation",
                }
        except Exception as exc:
            record["hf2li_cleanup_error"] = str(exc)
        hf.close()
        try:
            manager = TimingRecipeManager(inventory=inventory, command_log=log)
            safe = manager.apply_recipe(
                SAFE_IDLE, output_path=RAW / "hf01_timing10_r5_final_safe_idle.json"
            )
            record["final_t660_safe_idle"] = {
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
        record.get("status") == "CAPTURED_EXACTLY_10_EVENTS"
        and not any(key.endswith("_error") for key in record)
        and (record.get("final_t660_safe_idle") or {}).get("matches_recipe") is True
    )
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
