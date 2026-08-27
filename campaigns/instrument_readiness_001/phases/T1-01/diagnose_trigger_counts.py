"""Focused T1-01 trigger-count diagnostic followed by verified safe idle."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import time


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.t660_service import T660Service  # noqa: E402
from control_app.workflows.timing_calibration_procedure import (  # noqa: E402
    MEASUREMENT_STEPS,
    TimingCalibrationProcedure,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402


HERE = Path(__file__).resolve().parent
OUT = HERE / "setup_1_extref_to_fire"
SAFE_IDLE = REPO_ROOT / "instrument" / "recipes" / "safe_idle.yaml"


def main() -> int:
    inventory = load_config_inventory(write_files=False)
    step = next(item for item in MEASUREMENT_STEPS if item.step == "4")
    recipe = TimingCalibrationProcedure(
        operator="Christopher Robertson", inventory=inventory
    ).build_step_recipe(step, programmed_delay_ns=0)
    log = (OUT / "trigger_count_diagnostic_command_log.txt").open("a", encoding="utf-8")
    manager = TimingRecipeManager(inventory=inventory, command_log=log)
    result = {"started_utc": datetime.now(UTC).isoformat(), "status": "STARTING"}
    services = {}
    try:
        active = manager.apply_recipe(
            recipe, output_path=OUT / "trigger_count_diagnostic_active_readback.json"
        )
        if not active["matches_recipe"]:
            raise RuntimeError("active recipe mismatch")
        for unit in ("t660_1", "t660_2"):
            service = T660Service(
                unit, inventory.t660_devices[unit], command_log=log
            )
            service.connect()
            services[unit] = service
        before = {unit: service.get_shot_count() for unit, service in services.items()}
        time.sleep(2.0)
        after = {unit: service.get_shot_count() for unit, service in services.items()}
        result.update(
            {
                "active_recipe_matches": True,
                "observation_interval_s": 2.0,
                "shot_counts_before": before,
                "shot_counts_after": after,
                "shot_count_changes": {
                    unit: after[unit] - before[unit] for unit in before
                },
                "status": "PASS",
            }
        )
    except BaseException as exc:
        result.update({"status": "FAIL", "error": str(exc)})
        raise
    finally:
        for service in services.values():
            service.close()
        safe = manager.apply_recipe(
            SAFE_IDLE, output_path=OUT / "trigger_count_diagnostic_safe_idle.json"
        )
        result["final_safe_idle_matches"] = safe["matches_recipe"]
        result["finished_utc"] = datetime.now(UTC).isoformat()
        log.close()
        (OUT / "trigger_count_diagnostic.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
