"""Focused T2-01 PicoScope ownership and T660 safe-idle preflight."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.picoscope_service import PicoScopeService  # noqa: E402
from control_app.workflows.picoscope_settings_test import (  # noqa: E402
    capture_settings_from_recipe,
    load_recipe,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402


EVIDENCE_DIR = Path(__file__).resolve().parent
SAFE_IDLE_RECIPE = REPO_ROOT / "recipes" / "safe_idle.yaml"
PICO_RECIPE = REPO_ROOT / "recipes" / "picoscope_settings_test.yaml"


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="preflight")
    args = parser.parse_args()
    status_path = EVIDENCE_DIR / f"{args.label}_status.json"
    command_log_path = EVIDENCE_DIR / f"{args.label}_command_log.txt"
    readback_path = EVIDENCE_DIR / f"{args.label}_safe_idle_readback.json"
    record = {
        "operator": "Christopher Robertson",
        "phase": "T2-01",
        "started_utc": datetime.now(UTC).isoformat(),
        "purpose": "exclusive PicoScope ownership and T660 safe-idle/readback before first cable change",
        "process_inventory": {
            "competing_python_or_picoscope_process_found": False,
            "basis": "Windows process inventory immediately before this utility",
        },
        "picoscope": {"ownership": "NOT_ATTEMPTED"},
        "t660_safe_idle": {"status": "NOT_ATTEMPTED"},
    }
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
        record["finished_utc"] = datetime.now(UTC).isoformat()
        write_json(status_path, record)

    command_log = command_log_path.open("a", encoding="utf-8")
    manager = TimingRecipeManager(inventory=inventory, command_log=command_log)
    try:
        readback = manager.apply_recipe(
            SAFE_IDLE_RECIPE,
            output_path=readback_path,
        )
        record["t660_safe_idle"] = {
            "status": "PASS" if readback["matches_recipe"] else "FAIL",
            "matches_recipe": readback["matches_recipe"],
            "mismatches": readback["mismatches"],
        }
        if not readback["matches_recipe"]:
            raise RuntimeError("safe-idle readback did not match the authoritative recipe")
    except BaseException as exc:
        record["t660_safe_idle"] = {"status": "FAIL", "error": str(exc)}
        raise
    finally:
        command_log.close()
        record["finished_utc"] = datetime.now(UTC).isoformat()
        write_json(status_path, record)

    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
