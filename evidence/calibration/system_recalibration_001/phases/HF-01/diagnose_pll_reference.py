"""Bounded non-emitting T660-2 DIO0 to HF2LI PLL0 diagnostic."""

from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.hf2li_service import HF2LIService  # noqa: E402
from control_app.devices.t660_service import T660Service  # noqa: E402
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
SAFE_IDLE = REPO_ROOT / "instrument" / "recipes" / "safe_idle.yaml"


def stamp():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main():
    path = RAW / "hf01_pll_reference_diagnostic_014.json"
    if path.exists():
        raise FileExistsError(path)
    inventory = load_config_inventory(write_files=False)
    log = (HERE / "command_log.txt").open("a", encoding="utf-8")
    hf = HF2LIService(inventory.devices["hf2li"], command_log=log)
    t660 = T660Service("t660_2", inventory.t660_devices["t660_2"], command_log=log)
    record = {"started_utc": stamp(), "samples": [], "status": "STARTED"}
    original = {}
    original_osc0_frequency = None
    try:
        hf.connect()
        server = hf._require_server()
        dev = hf.device_id
        original_osc0_frequency = float(server.getDouble(f"/{dev}/oscs/0/freq"))
        for node, kind in (
            ("enable", "int"), ("adcselect", "int"), ("freqcenter", "double"),
            ("harmonic", "int"), ("order", "int"), ("adcthreshold", "int"),
        ):
            original[node] = (server.getInt if kind == "int" else server.getDouble)(f"/{dev}/plls/0/{node}")
        t660.connect()
        t660.command("STOP", expect_response=False)
        t660.set_trigger_source("OFF")
        for channel in "ABCD":
            t660.disable_channel(channel)
        for channel in "AB":
            t660.set_channel_delay_width(channel, "0ns", "150ns")
            t660.command(f"CHAN:POS {channel}", expect_response=False)
            t660.command(f"CHAN:50OHM {channel}", expect_response=False)
            t660.enable_channel(channel)
        record["master_clock_before"] = {
            "system_extclk": int(server.getInt(f"/{dev}/system/extclk")),
            "status_plllock_flag": int(server.getInt(f"/{dev}/status/flags/plllock")),
            "status_dcmlock_flag": int(server.getInt(f"/{dev}/status/flags/dcmlock")),
            "flag_semantics": "zero_is_locked_per_HF2_node_documentation",
        }
        if record["master_clock_before"] != {
            "system_extclk": 1,
            "status_plllock_flag": 0,
            "status_dcmlock_flag": 0,
            "flag_semantics": "zero_is_locked_per_HF2_node_documentation",
        }:
            raise RuntimeError(f"HF2LI master clock is not locked: {record['master_clock_before']}")
        retained_center_hz = float(server.getDouble(f"/{dev}/plls/0/freqcenter"))
        target_frequency_hz = 2_000_000.0
        record["retained_pll_center_hz"] = retained_center_hz
        record["target_frequency_hz"] = target_frequency_hz
        t660.set_clock_mode(frequency=f"{target_frequency_hz:.9f}Hz", shots=0)
        t660.set_trigger_source("SYN")
        t660.command("START", expect_response=False)
        server.setInt(f"/{dev}/dios/0/drive", 0)
        server.setInt(f"/{dev}/plls/0/enable", 0)
        server.setInt(f"/{dev}/plls/0/adcselect", 4)
        server.setDouble(f"/{dev}/oscs/0/freq", target_frequency_hz)
        server.setInt(f"/{dev}/plls/0/harmonic", 1)
        server.setInt(f"/{dev}/plls/0/order", 4)
        server.setInt(f"/{dev}/plls/0/adcthreshold", 0)
        server.setInt(f"/{dev}/plls/0/enable", 1)
        server.sync()
        for _ in range(40):
            record["samples"].append({
                "utc": stamp(),
                "locked": int(server.getInt(f"/{dev}/plls/0/locked")),
                "error": float(server.getDouble(f"/{dev}/plls/0/error")),
                "rate": float(server.getDouble(f"/{dev}/plls/0/rate")),
                "freqcenter": float(server.getDouble(f"/{dev}/plls/0/freqcenter")),
                "osc0_frequency": float(server.getDouble(f"/{dev}/oscs/0/freq")),
                "status_plllock": int(server.getInt(f"/{dev}/status/flags/plllock")),
                "status_flags_binary": int(server.getInt(f"/{dev}/status/flags/binary")),
            })
            time.sleep(0.1)
        record["t660_shot_count"] = t660.get_shot_count()
        record["status"] = "CAPTURED"
    except Exception as exc:
        record["status"] = "FAIL"
        record["error"] = str(exc)
    finally:
        try:
            t660.command("STOP", expect_response=False)
            t660.set_trigger_source("OFF")
            for channel in "ABCD":
                t660.disable_channel(channel)
        except Exception as exc:
            record["t660_cleanup_error"] = str(exc)
        t660.close()
        try:
            if original:
                server = hf._require_server()
                dev = hf.device_id
                server.setInt(f"/{dev}/plls/0/enable", 0)
                for node in ("adcselect", "harmonic", "order", "adcthreshold"):
                    server.setInt(f"/{dev}/plls/0/{node}", int(original[node]))
                server.setDouble(f"/{dev}/plls/0/freqcenter", float(original["freqcenter"]))
                if original_osc0_frequency is not None:
                    server.setDouble(
                        f"/{dev}/oscs/0/freq", float(original_osc0_frequency)
                    )
                server.setInt(f"/{dev}/plls/0/enable", int(original["enable"]))
                server.sync()
        except Exception as exc:
            record["hf_cleanup_error"] = str(exc)
        hf.close()
        try:
            manager = TimingRecipeManager(inventory=inventory, command_log=log)
            safe = manager.apply_recipe(SAFE_IDLE, output_path=RAW / "hf01_pll_reference_diagnostic_014_safe_idle.json")
            record["safe_idle"] = {"matches_recipe": safe.get("matches_recipe"), "mismatches": safe.get("mismatches")}
        except Exception as exc:
            record["safe_idle_error"] = str(exc)
        log.close()
        record["finished_utc"] = stamp()
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record.get("status") == "CAPTURED" and record.get("safe_idle", {}).get("matches_recipe") else 1


if __name__ == "__main__":
    raise SystemExit(main())
