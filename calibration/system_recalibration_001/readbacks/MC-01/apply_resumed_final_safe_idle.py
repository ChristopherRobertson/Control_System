"""Apply and verify final T660 safe idle after resumed MC-01."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402

HERE = Path(__file__).resolve().parent
SAFE_IDLE = REPO_ROOT / "recipes" / "safe_idle.yaml"


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    status_path = HERE / "resumed_final_safe_idle_status.json"
    record = {
        "authorization_id": "MC01-AUTH-002",
        "started_utc": datetime.now(UTC).isoformat(),
        "purpose": "final T660 safe idle after resumed MC-01 active and SDK qualification",
        "mircat_sdk_connection_used_during_this_operation": False,
        "output_enable_during_this_operation": False,
        "laser_emission_during_this_operation": False,
        "t660_safe_idle": {"status": "NOT_ATTEMPTED"},
    }
    write(status_path, record)
    log = (HERE / "resumed_final_safe_idle_command_log.txt").open("a", encoding="utf-8")
    manager = TimingRecipeManager(inventory=load_config_inventory(write_files=False), command_log=log)
    try:
        readback = manager.apply_recipe(SAFE_IDLE, output_path=HERE / "resumed_final_safe_idle_readback.json")
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
        write(status_path, record)
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
