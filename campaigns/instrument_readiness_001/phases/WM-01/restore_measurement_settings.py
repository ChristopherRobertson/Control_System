"""Restore required WM-01 measurement settings after a rejected attempt."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys

PHASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PHASE_DIR.parents[3]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.devices.coherent_wavemaster_service import CoherentWaveMasterService


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def read_settings(meter):
    return {
        "autocalibration": meter.get_autocalibration(),
        "mode": meter.get_mode(),
        "units": meter.get_units(),
        "period_s": meter.get_period_s(),
    }


def main() -> int:
    path = PHASE_DIR / "raw" / "settings_restoration_after_acq0005.json"
    if path.exists():
        raise SystemExit(f"refusing to overwrite {path}")
    with (PHASE_DIR / "command_log.txt").open("a", encoding="utf-8", newline="\n") as log:
        meter = CoherentWaveMasterService.from_config(allow_settings=True, command_log=log)
        meter.connect()
        start = now()
        initial = read_settings(meter)
        try:
            meter.set_units("A")
            meter.set_mode("P")
            meter.set_autocalibration(True)
            meter.set_period_s(0)
            final = read_settings(meter)
            blocked = meter.get_measurement()
        finally:
            meter.close()
    record = {
        "schema_version": "1.0.0",
        "campaign_id": "system_recalibration_001",
        "phase_id": "WM-01",
        "phase_run_id": "WM01-RUN-20260821",
        "start_utc": start,
        "end_utc": now(),
        "initial_settings": initial,
        "final_settings": final,
        "required_settings_restored": final == {"autocalibration": "ON", "mode": "P", "units": "A", "period_s": 0},
        "blocked_control_raw": blocked.raw,
        "blocked_control_quality": blocked.quality,
        "blocked_control_numeric_value": blocked.value,
    }
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0 if record["required_settings_restored"] and blocked.value is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
