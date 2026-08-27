"""Apply and verify T660-only safe idle after MC-01 GUI configuration."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402


HERE = Path(__file__).resolve().parent
SAFE_IDLE = REPO_ROOT / "instrument" / "recipes" / "safe_idle.yaml"


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    status_path = HERE / "postconfiguration_safe_idle_status.json"
    record = {
        "campaign_id": "system_recalibration_001",
        "phase_id": "MC-01",
        "phase_run_id": "system_recalibration_001_MC-01_001",
        "started_utc": datetime.now(UTC).isoformat(),
        "purpose": "T660-only safe idle after GUI configuration and before inhibited control",
        "mircat_sdk_connection_used": False,
        "output_enable_authorized": False,
        "laser_emission_authorized": False,
        "t660_safe_idle": {"status": "NOT_ATTEMPTED"},
    }
    write_json(status_path, record)
    inventory = load_config_inventory(write_files=False)
    log = (HERE / "postconfiguration_safe_idle_command_log.txt").open(
        "a", encoding="utf-8"
    )
    manager = TimingRecipeManager(inventory=inventory, command_log=log)
    try:
        readback = manager.apply_recipe(
            SAFE_IDLE,
            output_path=HERE / "postconfiguration_safe_idle_readback.json",
        )
        record["t660_safe_idle"] = {
            "status": "PASS" if readback["matches_recipe"] else "FAIL",
            "matches_recipe": readback["matches_recipe"],
            "mismatches": readback["mismatches"],
        }
        if not readback["matches_recipe"]:
            raise RuntimeError("safe-idle readback mismatch")
    finally:
        log.close()
        record["finished_utc"] = datetime.now(UTC).isoformat()
        write_json(status_path, record)
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
