"""Reapply Pico programmed-zero output and T660 safe idle before timing wiring."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.picoscope_service import PicoScopeService  # noqa: E402
from control_app.workflows.picoscope_settings_test import (  # noqa: E402
    capture_settings_from_recipe,
    load_recipe,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402


HERE = Path(__file__).resolve().parent
SAFE_IDLE = REPO_ROOT / "instrument" / "recipes" / "safe_idle.yaml"
PICO_RECIPE = REPO_ROOT / "instrument" / "recipes" / "picoscope_settings_test.yaml"


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main() -> int:
    record = {
        "phase_id": "HF-01",
        "authorization_id": "HF01-AUTH-001",
        "started_utc": now(),
        "purpose": "program Pico generator zero and apply T660 safe idle before timing-copy cable moves",
        "picoscope": {"status": "NOT_ATTEMPTED"},
        "t660": {"status": "NOT_ATTEMPTED"},
    }
    inventory = load_config_inventory(write_files=False)
    with (HERE / "command_log.txt").open("a", encoding="utf-8") as log:
        pico_recipe, _ = load_recipe(PICO_RECIPE)
        pico = PicoScopeService(
            inventory.devices["picoscope"],
            capture_settings_from_recipe(pico_recipe),
            command_log=log,
        )
        try:
            pico.open_unit()
            record["picoscope"] = {
                "status": "PASS",
                "serial": inventory.devices["picoscope"].get("serial_number"),
                "generator": pico.disable_signal_generator(),
            }
        finally:
            if pico._is_open:
                pico.disable_signal_generator()
                pico.close_unit()

        manager = TimingRecipeManager(inventory=inventory, command_log=log)
        readback = manager.apply_recipe(
            SAFE_IDLE,
            output_path=HERE / "pre_timing_wiring_t660_safe_idle_readback.json",
        )
        record["t660"] = {
            "status": "PASS" if readback.get("matches_recipe") else "FAIL",
            "matches_recipe": readback.get("matches_recipe"),
            "mismatches": readback.get("mismatches"),
        }
    record["finished_utc"] = now()
    record["status"] = (
        "PASS"
        if record["picoscope"].get("status") == "PASS"
        and record["t660"].get("status") == "PASS"
        else "FAIL"
    )
    (HERE / "pre_timing_wiring_safe_state_status.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
