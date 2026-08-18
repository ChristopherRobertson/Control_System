"""Non-emitting MIRcat SDK readback/set/restore qualification for MC-01."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_app.devices.mircat_service import (  # noqa: E402
    MircatService,
    PROC_TRIG_MODE_EXTERNAL,
    PROC_TRIG_MODE_INTERNAL,
)

HERE = Path(__file__).resolve().parent


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    status_path = HERE / "sdk_control_qualification.json"
    record = {
        "authorization_id": "MC01-AUTH-002",
        "acquisition_id": "MC01-SDK-QUAL-001",
        "started_utc": datetime.now(UTC).isoformat(),
        "commands_excluded": ["arm", "emission_on", "tune", "start_scan"],
        "status": "STARTED",
    }
    write(status_path, record)
    log = (HERE / "sdk_control_qualification_command_log.txt").open("a", encoding="utf-8")
    service = MircatService.from_config(command_log=log)
    try:
        service.initialize()
        before_state = service.read_state().to_dict()
        record["sdk_api_version"] = before_state.get("api_version")
        record["before_state"] = before_state
        if before_state.get("armed") is not False:
            raise RuntimeError("SDK qualification requires disarmed MIRcat")
        if before_state.get("emission_on") is not False:
            raise RuntimeError("SDK qualification requires emission off")
        if before_state.get("scan_in_progress") is not False:
            raise RuntimeError("SDK qualification requires no scan in progress")

        initial = service.get_wavelength_trigger_params()
        record["initial_trigger_readback"] = initial
        common = {
            "pulse_mode": initial["pulse_mode"],
            "start": initial["start"],
            "stop": initial["stop"],
            "interval": initial["interval"],
            "units": initial["units"],
            "dwell_us": initial["dwell_us"],
            "after_off_us": initial["after_off_us"],
        }
        external = service.set_wavelength_trigger_params(
            process_trigger_mode=PROC_TRIG_MODE_EXTERNAL, **common
        )
        record["external_mode_readback"] = external
        if external["process_trigger_mode"] != PROC_TRIG_MODE_EXTERNAL:
            raise RuntimeError(f"external process-trigger readback mismatch: {external}")

        restored = service.set_wavelength_trigger_params(
            process_trigger_mode=PROC_TRIG_MODE_INTERNAL, **common
        )
        record["restored_internal_mode_readback"] = restored
        if restored["process_trigger_mode"] != PROC_TRIG_MODE_INTERNAL:
            raise RuntimeError(f"internal process-trigger restore mismatch: {restored}")

        after_state = service.read_state().to_dict()
        record["after_state"] = after_state
        if after_state.get("armed") or after_state.get("emission_on") or after_state.get("scan_in_progress"):
            raise RuntimeError(f"unsafe post-qualification MIRcat state: {after_state}")
        record["status"] = "PASS"
    finally:
        service.deinitialize()
        log.close()
        record["finished_utc"] = datetime.now(UTC).isoformat()
        write(status_path, record)
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
