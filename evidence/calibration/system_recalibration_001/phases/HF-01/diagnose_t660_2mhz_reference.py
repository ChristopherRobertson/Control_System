"""Measure the temporary T660-2 channel-B copy of the 2 MHz DIO0 reference."""

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
import statistics
import sys

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.picoscope_service import PicoScopeService  # noqa: E402
from control_app.devices.t660_service import T660Service  # noqa: E402
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
SAFE_IDLE = REPO_ROOT / "instrument" / "recipes" / "safe_idle.yaml"


def stamp():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main():
    status_path = RAW / "hf01_t660_2mhz_reference_diagnostic_001.json"
    raw_path = RAW / "hf01_t660_2mhz_reference_diagnostic_001_pico.csv"
    if status_path.exists():
        raise FileExistsError(status_path)
    inventory = load_config_inventory(write_files=False)
    log = (HERE / "command_log.txt").open("a", encoding="utf-8")
    settings = {
        "resolution": "8BIT",
        "channels": {
            "A": {"enabled": True, "coupling": "DC", "range": "100MV", "analog_offset_v": 0.0},
            "B": {"enabled": True, "coupling": "DC", "range": "10V", "analog_offset_v": 0.0},
        },
        "external_trigger": {"source": "B", "threshold_adc": 5000, "direction": 2, "delay_samples": 0, "auto_trigger_ms": 0},
        "total_samples": 5000,
        "pre_trigger_samples": 1000,
        "timebase": 1,
        "timeout_s": 5.0,
    }
    pico = PicoScopeService(inventory.devices["picoscope"], settings, command_log=log)
    t660 = T660Service("t660_2", inventory.t660_devices["t660_2"], command_log=log)
    record = {"started_utc": stamp(), "status": "STARTED"}
    try:
        pico.open_unit()
        record["pico_zero_before"] = pico.disable_signal_generator()
        maximum = pico.get_maximum_adc_value()
        timing = pico.validate_sample_timing()
        t660.connect()
        t660.command("STOP", expect_response=False)
        t660.set_trigger_source("OFF")
        for channel in "ABCD": t660.disable_channel(channel)
        for channel in "AB":
            t660.set_channel_delay_width(channel, "0ns", "150ns")
            t660.command(f"CHAN:POS {channel}", expect_response=False)
            t660.command(f"CHAN:50OHM {channel}", expect_response=False)
            t660.enable_channel(channel)
        t660.set_clock_mode(frequency="2MHz", shots=0)
        t660.set_trigger_source("SYN")
        t660.command("START", expect_response=False)
        record["capture"] = pico.capture_block(raw_path)
        t660.command("STOP", expect_response=False)
        with raw_path.open(newline="", encoding="utf-8") as handle:
            values = [int(row["ch_b_adc"]) * 10.0 / maximum for row in csv.DictReader(handle)]
        threshold = (statistics.median(values[:800]) + max(values)) / 2.0
        rises = [i for i in range(1, len(values)) if values[i-1] < threshold <= values[i]]
        intervals = [(b-a) * float(timing["sample_interval_ns"]) * 1e-9 for a,b in zip(rises,rises[1:])]
        record["measurement"] = {
            "sample_min_v": min(values), "sample_max_v": max(values),
            "sample_vpp": max(values)-min(values), "rising_edges": len(rises),
            "mean_period_s": statistics.mean(intervals),
            "frequency_hz": 1.0/statistics.mean(intervals),
            "period_standard_deviation_s": statistics.stdev(intervals),
        }
        record["status"] = "PASS" if 1_990_000 <= record["measurement"]["frequency_hz"] <= 2_010_000 else "FAIL"
    except Exception as exc:
        record["status"] = "FAIL"
        record["error"] = str(exc)
    finally:
        try:
            if pico._is_open:
                record["pico_zero_final"] = pico.disable_signal_generator(); pico.stop(); pico.close_unit()
        except Exception as exc: record["pico_cleanup_error"] = str(exc)
        try:
            t660.command("STOP", expect_response=False); t660.set_trigger_source("OFF")
            for channel in "ABCD": t660.disable_channel(channel)
        except Exception as exc: record["t660_cleanup_error"] = str(exc)
        t660.close()
        try:
            safe = TimingRecipeManager(inventory=inventory, command_log=log).apply_recipe(SAFE_IDLE, output_path=RAW / "hf01_t660_2mhz_reference_diagnostic_001_safe_idle.json")
            record["safe_idle"] = {"matches_recipe": safe.get("matches_recipe"), "mismatches": safe.get("mismatches")}
        except Exception as exc: record["safe_idle_error"] = str(exc)
        log.close(); record["finished_utc"] = stamp()
        status_path.write_text(json.dumps(record, indent=2, sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record.get("status") == "PASS" and record.get("safe_idle",{}).get("matches_recipe") else 1


if __name__ == "__main__": raise SystemExit(main())
