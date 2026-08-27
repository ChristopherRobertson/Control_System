"""Raw-poll HF2LI DIO around one bounded MC-01 Process Trigger."""

from __future__ import annotations

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
from control_app.devices.t660_service import T660Service  # noqa: E402

HERE = Path(__file__).resolve().parent


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    stem = "raw_dio_process_diagnostic"
    record = {
        "authorization_id": "MC01-AUTH-002",
        "acquisition_id": "MC01-DIO-DIAGNOSTIC-002",
        "started_utc": datetime.now(UTC).isoformat(),
        "method": "raw HF2LI subscription/poll; no DAQ grid interpolation",
        "hf2li_device": "dev18500",
        "timing_demodulator_api_index": 2,
        "dio_mapping": {"pin1_scan_direction": 20, "pin2_tuned_sweep_active": 21, "pin3_wavelength_trigger": 22},
        "status": "STARTED",
    }
    status_path = HERE / f"{stem}_status.json"
    write(status_path, record)
    inventory = load_config_inventory(write_files=False)
    log = (HERE / f"{stem}_command_log.txt").open("a", encoding="utf-8")
    hf = HF2LIService(inventory.devices["hf2li"], command_log=log)
    t660 = T660Service("t660_1", inventory.t660_devices["t660_1"], command_log=log)
    trigger_error: list[str] = []
    trigger_issued = False
    try:
        hf.connect()
        record["hf2li_clockbase_hz"] = hf.get_clockbase()
        t660.connect()
        record["t660_identity"] = t660.identify()
        t660.command("STOP", expect_response=False)
        t660.set_trigger_source("OFF")
        for channel in "ABCD":
            t660.disable_channel(channel)
        t660.force_eod()
        t660.set_channel_delay_width("C", "0ns", "10ms")
        t660.command("CHAN:NEG C", expect_response=False)
        t660.command("CHAN:50OHM C", expect_response=False)
        t660.enable_channel("C")
        t660.set_trigger_source("REM")
        t660.command("START", expect_response=False)
        record["t660_staged_readback"] = t660.read_active_settings()
        t660.reset_shot_counter()
        record["shot_count_before"] = t660.get_shot_count()

        def issue() -> None:
            nonlocal trigger_issued
            try:
                time.sleep(0.5)
                t660.fire_remote_trigger()
                trigger_issued = True
                record["trigger_issued_utc"] = datetime.now(UTC).isoformat()
            except Exception as exc:  # captured into the stable status record
                trigger_error.append(str(exc))

        hf.start_acquisition(demodulators=[2], fields=["dio"])
        worker = threading.Thread(target=issue, name="mc01-one-trigger")
        worker.start()
        try:
            dio_record = hf.read_acquisition(4.0)
            dio_record["fields"] = ["dio"]
        finally:
            worker.join()
            hf.stop_acquisition()
        if trigger_error:
            raise RuntimeError(trigger_error[0])
        record["shot_count_after"] = t660.get_shot_count()
        record["hf2li_export"] = hf.save_record(
            dio_record,
            raw_csv_path=HERE / f"{stem}_raw.csv",
            summary_csv_path=HERE / f"{stem}_summary.csv",
        )
        record["status"] = "CAPTURED_ONE_TRIGGER_RAW_POLL"
    finally:
        try:
            t660.command("STOP", expect_response=False)
            t660.set_trigger_source("OFF")
            t660.disable_channel("C")
            t660.force_eod()
            record["t660_post_readback"] = t660.read_active_settings()
        except Exception as exc:
            record["t660_cleanup_error"] = str(exc)
        t660.close()
        hf.close()
        log.close()
        record["trigger_was_issued"] = trigger_issued
        record["finished_utc"] = datetime.now(UTC).isoformat()
        write(status_path, record)
    if record.get("shot_count_before") != 0 or record.get("shot_count_after") != 1:
        raise RuntimeError(f"unexpected T660 shot-count result: {record}")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
