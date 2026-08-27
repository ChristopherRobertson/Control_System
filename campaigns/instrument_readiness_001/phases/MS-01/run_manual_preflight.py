"""Direct MS-01 ownership and safe-idle preflight.

This is intentionally not a complete-workflow runner. It opens the configured
PicoScope once, releases it, then applies and reads back the repository
safe-idle recipe on both T660 units.
"""

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


EVIDENCE_DIR = Path(__file__).resolve().parent
SAFE_IDLE_RECIPE = REPO_ROOT / "instrument" / "recipes" / "safe_idle.yaml"
PICO_RECIPE = REPO_ROOT / "instrument" / "recipes" / "picoscope_settings_test.yaml"


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    record: dict = {
        "started_utc": datetime.now(UTC).isoformat(),
        "purpose": "MS-01 direct ownership and safe-idle/readback preflight",
        "previous_process_check": {
            "device_control_process_found": False,
            "windows_serial_inventory": "USER_INPUT_REQUIRED",
        },
        "picoscope": {"ownership": "NOT_ATTEMPTED"},
        "t660_safe_idle": {"status": "NOT_ATTEMPTED"},
    }
    write_json(EVIDENCE_DIR / "preflight_status.json", record)

    inventory = load_config_inventory(write_files=False)
    pico_config = inventory.devices["picoscope"]
    pico_recipe, _ = load_recipe(PICO_RECIPE)
    pico_settings = capture_settings_from_recipe(pico_recipe)
    pico = PicoScopeService(pico_config, pico_settings)

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
        record["finished_utc"] = datetime.now(UTC).isoformat()
        write_json(EVIDENCE_DIR / "preflight_status.json", record)
        raise
    finally:
        try:
            pico.close_unit()
        except BaseException as exc:
            record["picoscope"]["close_error"] = str(exc)

    manager = TimingRecipeManager(
        inventory=inventory,
        command_log=(EVIDENCE_DIR / "preflight_command_log.txt").open(
            "a", encoding="utf-8"
        ),
    )
    try:
        readback = manager.apply_recipe(
            SAFE_IDLE_RECIPE,
            output_path=EVIDENCE_DIR / "safe_idle_initial_readback.json",
        )
        record["t660_safe_idle"] = {
            "status": "PASS" if readback["matches_recipe"] else "FAIL",
            "matches_recipe": readback["matches_recipe"],
            "mismatches": readback["mismatches"],
            "readback_path": str(
                EVIDENCE_DIR / "safe_idle_initial_readback.json"
            ),
        }
    except BaseException as exc:
        record["t660_safe_idle"] = {"status": "FAIL", "error": str(exc)}
        raise
    finally:
        manager.command_log.close()
        record["finished_utc"] = datetime.now(UTC).isoformat()
        write_json(EVIDENCE_DIR / "preflight_status.json", record)

    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
