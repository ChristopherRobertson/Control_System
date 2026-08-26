"""Qualify WM-01 serial ownership, reconnect, and offline rejection behavior."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys

PHASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PHASE_DIR.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_app.devices.coherent_wavemaster_service import (
    CoherentWaveMasterService,
    WaveMasterCommunicationError,
    parse_identity_reply,
    parse_measurement_reply,
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def rejected(callable_obj) -> dict[str, str | bool]:
    try:
        callable_obj()
    except Exception as exc:  # the retained evidence records the exact class
        return {"rejected": True, "exception_type": type(exc).__name__, "message": str(exc)}
    return {"rejected": False, "exception_type": "", "message": "unexpected acceptance"}


def main() -> int:
    out_path = PHASE_DIR / "raw" / "communication_qualification.json"
    log_path = PHASE_DIR / "command_log.txt"
    with log_path.open("a", encoding="utf-8", newline="\n") as log:
        start = utc_now()
        primary = CoherentWaveMasterService.from_config(command_log=log)
        primary.connect()
        first_identity = primary.identify().raw

        secondary = CoherentWaveMasterService.from_config(command_log=log)
        exclusive = rejected(secondary.connect)
        secondary.close()

        primary.close()
        reconnect = CoherentWaveMasterService.from_config(command_log=log)
        reconnect.connect()
        second_identity = reconnect.identify().raw
        reconnect_measurement = reconnect.get_measurement()
        reconnect.close()

        offline = {
            "malformed_identity": rejected(lambda: parse_identity_reply("*IDN$ incomplete")),
            "missing_value_field": rejected(lambda: parse_measurement_reply("VAL$ 12345")),
            "malformed_time_tag": rejected(lambda: parse_measurement_reply("VAL$ stale,540.000")),
            "unknown_status": rejected(lambda: parse_measurement_reply("VAL$ 12345,UNKNOWN STATE")),
            "multi_line_non_numeric": parse_measurement_reply("VAL$ 12345,MULTI-LINE").value is None,
            "saturated_non_numeric": parse_measurement_reply("VAL$ 12346,SATURATED").value is None,
            "no_signal_non_numeric": parse_measurement_reply("VAL$ 12347,NO SIGNAL").value is None,
        }
        record = {
            "schema_version": "1.0.0",
            "campaign_id": "system_recalibration_001",
            "phase_id": "WM-01",
            "phase_run_id": "WM01-RUN-20260821",
            "start_utc": start,
            "end_utc": utc_now(),
            "exclusive_ownership_attempt": exclusive,
            "close_reopen_reconnect": {
                "first_identity": first_identity,
                "second_identity": second_identity,
                "identity_agreement": first_identity == second_identity,
                "measurement_raw": reconnect_measurement.raw,
                "measurement_quality": reconnect_measurement.quality,
                "measurement_numeric_value": reconnect_measurement.value,
            },
            "offline_response_rejection": offline,
        }
        out_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    ok = (
        exclusive["rejected"]
        and record["close_reopen_reconnect"]["identity_agreement"]
        and all(item["rejected"] for item in list(offline.values())[:4])
        and all(offline[key] for key in list(offline)[4:])
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
