"""Focused PT-01 PicoScope ownership and T660 safe-idle preflight."""

from __future__ import annotations

import argparse
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


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="initial_preflight")
    args = parser.parse_args()
    record = {
        "operator": "Christopher Robertson",
        "phase": "PT-01",
        "started_utc": datetime.now(UTC).isoformat(),
        "purpose": "exclusive PicoScope ownership and T660 safe-idle/readback before PT-01 cable handling",
        "picoscope": {"ownership": "NOT_ATTEMPTED"},
        "t660_safe_idle": {"status": "NOT_ATTEMPTED"},
    }
    status_path = HERE / f"{args.label}_status.json"
    write_json(status_path, record)
    inventory = load_config_inventory(write_files=False)
    pico_config = inventory.devices["picoscope"]
    pico_recipe, _ = load_recipe(PICO_RECIPE)
    pico = PicoScopeService(pico_config, capture_settings_from_recipe(pico_recipe))
    try:
        pico.open_unit()
        record["picoscope"] = {
            "ownership": "PASS",
            "configured_model": pico_config.get("model"),
            "configured_serial_number": pico_config.get("serial_number"),
            "sdk_serial_number": pico_config.get("sdk_serial_number"),
        }
    except BaseException as exc:
        record["picoscope"] = {"ownership": "FAIL", "error": str(exc)}
        raise
    finally:
        try:
            pico.close_unit()
        except BaseException as exc:
            record["picoscope"]["close_error"] = str(exc)
        write_json(status_path, record)

    log = (HERE / f"{args.label}_command_log.txt").open("a", encoding="utf-8")
    manager = TimingRecipeManager(inventory=inventory, command_log=log)
    try:
        readback = manager.apply_recipe(
            SAFE_IDLE, output_path=HERE / f"{args.label}_safe_idle_readback.json"
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
