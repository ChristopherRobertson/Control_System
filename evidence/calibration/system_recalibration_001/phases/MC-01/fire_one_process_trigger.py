"""Issue one bounded 10 ms active-low MIRcat Process Trigger for MC-01."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.t660_service import T660Service  # noqa: E402

HERE = Path(__file__).resolve().parent


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    repeat = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    if repeat not in {1, 2, 3}:
        raise ValueError("repeat must be 1, 2, or 3")
    stem = f"repeat_{repeat}_process_trigger"
    record = {
        "authorization_id": "MC01-AUTH-002",
        "acquisition_id": f"MC01-ACTIVE-REPEAT-{repeat:03d}",
        "started_utc": datetime.now(UTC).isoformat(),
        "command_count_requested": 1,
        "channel": "T660-1 CHC",
        "destination": "MIRcat DB9 pin 4 Process Trigger",
        "polarity": "negative_active_low",
        "width": "10ms",
        "termination": "50OHM",
        "other_channels_enabled": False,
        "status": "STARTED",
    }
    write(HERE / f"{stem}_status.json", record)
    inventory = load_config_inventory(write_files=False)
    log = (HERE / f"{stem}_command_log.txt").open("a", encoding="utf-8")
    service = T660Service("t660_1", inventory.t660_devices["t660_1"], command_log=log)
    fired = False
    try:
        service.connect()
        record["identity"] = service.identify()
        service.command("STOP", expect_response=False)
        service.set_trigger_source("OFF")
        for channel in "ABCD":
            service.disable_channel(channel)
        service.force_eod()
        service.set_channel_delay_width("C", "0ns", "10ms")
        service.command("CHAN:NEG C", expect_response=False)
        service.command("CHAN:50OHM C", expect_response=False)
        service.enable_channel("C")
        service.set_trigger_source("REM")
        record["staged_readback"] = service.read_active_settings()
        service.reset_shot_counter()
        record["shot_count_before"] = service.get_shot_count()
        service.fire_remote_trigger()
        fired = True
        record["trigger_issued_utc"] = datetime.now(UTC).isoformat()
        time.sleep(0.1)
        record["shot_count_after"] = service.get_shot_count()
        record["status"] = "ONE_TRIGGER_ISSUED"
    finally:
        try:
            service.set_trigger_source("OFF")
            service.disable_channel("C")
            service.force_eod()
            record["post_trigger_readback"] = service.read_active_settings()
        finally:
            service.close()
            log.close()
        record["trigger_was_issued"] = fired
        record["finished_utc"] = datetime.now(UTC).isoformat()
        write(HERE / f"{stem}_status.json", record)
    if record.get("shot_count_before") != 0 or record.get("shot_count_after") != 1:
        raise RuntimeError(f"unexpected T660 shot-count result: {record}")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
