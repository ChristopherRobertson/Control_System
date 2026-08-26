"""Verify WM-01 documented setting/readback and local-control restoration."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys

PHASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PHASE_DIR.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_app.devices.coherent_wavemaster_service import CoherentWaveMasterService


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> int:
    out = PHASE_DIR / "raw" / "settings_and_local_control.json"
    with (PHASE_DIR / "command_log.txt").open("a", encoding="utf-8", newline="\n") as log:
        meter = CoherentWaveMasterService.from_config(allow_settings=True, command_log=log)
        meter.connect()
        start = now()
        initial = {
            "autocalibration": meter.get_autocalibration(),
            "mode": meter.get_mode(),
            "units": meter.get_units(),
            "period_s": meter.get_period_s(),
        }
        actions: list[dict[str, str | bool]] = []
        local_restored = False
        try:
            for name, action in [
                ("autocalibration_on", lambda: meter.set_autocalibration(True)),
                ("pulsed_mode", lambda: meter.set_mode("P")),
                ("air_nanometres", lambda: meter.set_units("A")),
                ("period_disabled", lambda: meter.set_period_s(0)),
                ("remote_control", meter.set_remote),
            ]:
                action()
                actions.append({"action": name, "readback_agreed": True})
        finally:
            # Local control is the required restoration even if an earlier
            # same-value setting verification fails.
            meter.set_local()
            local_restored = True
            final = {
                "autocalibration": meter.get_autocalibration(),
                "mode": meter.get_mode(),
                "units": meter.get_units(),
                "period_s": meter.get_period_s(),
            }
            meter.close()
        record = {
            "schema_version": "1.0.0",
            "campaign_id": "system_recalibration_001",
            "phase_id": "WM-01",
            "phase_run_id": "WM01-RUN-20260821",
            "start_utc": start,
            "end_utc": now(),
            "initial_settings": initial,
            "setting_actions": actions,
            "final_settings": final,
            "same_value_restoration_agreement": initial == final,
            "local_control_restored": local_restored,
        }
        out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0 if record["same_value_restoration_agreement"] and local_restored else 2


if __name__ == "__main__":
    raise SystemExit(main())
