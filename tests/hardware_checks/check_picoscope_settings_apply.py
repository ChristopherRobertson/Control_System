#!/usr/bin/env python3
"""Apply PicoScope settings from a recipe through the real ps5000a driver.

Usage:
    python tests/hardware_checks/check_picoscope_settings_apply.py --operator "Name" --confirm-real-hardware

This check sends configuration calls to the real PicoScope driver. It does not
simulate a scope and does not claim a measured waveform.
"""

from __future__ import annotations

from _common import REPO_ROOT, today_stamp, utc_now, write_blocked

import argparse

from control_app.config_loader import load_config_inventory
from control_app.manifest import new_manifest, write_manifest
from control_app.workflows.picoscope_settings_test import PicoScopeSettingsTest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--confirm-real-hardware", action="store_true", required=True)
    parser.add_argument(
        "--recipe",
        default="recipes/picoscope_settings_test.yaml",
        help="PicoScope settings recipe to apply",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = REPO_ROOT / "runs" / f"{today_stamp()}_picoscope_settings_test"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_dir = REPO_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    command_log_path = log_dir / f"{today_stamp()}_picoscope_settings_test_command_log.txt"
    manifest_path = run_dir / "run_manifest.json"
    inventory = load_config_inventory(write_files=True)

    errors: list[str] = []
    with command_log_path.open("a", encoding="utf-8") as command_log:
        command_log.write(
            f"{utc_now()} check_picoscope_settings_apply start "
            f"operator={args.operator} recipe={args.recipe}\n"
        )
        try:
            test = PicoScopeSettingsTest(operator=args.operator, inventory=inventory)
            test.run(
                recipe_path=args.recipe,
                run_dir=run_dir,
                command_log=command_log,
                command_log_paths=[str(command_log_path)],
            )
        except Exception as exc:
            errors.append(str(exc))

    if errors:
        next_actions = _next_actions(errors)
        manifest = new_manifest(
            operator=args.operator,
            inventory=inventory,
            picoscope_settings=inventory.picoscope_settings,
            command_log_paths=[str(command_log_path)],
            error_state={"has_error": True, "errors": errors},
            blocker_status={
                "blocked": True,
                "blockers": errors,
                "next_actions": next_actions,
            },
        )
        write_manifest(manifest_path, manifest)
        write_blocked(
            run_dir / "BLOCKED.md",
            title="PicoScope Settings Test BLOCKED",
            blockers=errors,
            next_actions=next_actions,
            context={"recipe": args.recipe},
        )
        print(f"BLOCKED see {run_dir / 'BLOCKED.md'}")
        return 2

    blocked_path = run_dir / "BLOCKED.md"
    if blocked_path.exists():
        blocked_path.unlink()
    print(f"PASS wrote {run_dir}")
    return 0


def _next_actions(errors: list[str]) -> list[str]:
    joined = " ".join(errors)
    if "PICO_NOT_FOUND" in joined:
        return [
            "Verify the PicoScope 5244D is connected by USB, powered if required, and visible in Windows Device Manager or PicoScope 7.",
            "Close PicoScope GUI or any other process that may already have the unit open.",
            "Verify hardware_configuration.yaml serial_number matches the serial string reported by PicoSDK/PicoScope, or temporarily remove the serial_number for discovery.",
            "Re-run this check with native Windows Python after Windows can see the unit.",
        ]
    if "ps5000a.dll" in joined:
        return [
            "Keep running this check with native Windows Python; the current blocker is ps5000a.dll visibility.",
            "Install PicoSDK or add the folder containing ps5000a.dll and its dependencies to PATH.",
            "Verify the configured PicoScope driver_search_paths point to folders that contain ps5000a.dll and picoipp.dll.",
            "Re-run this check after the driver is loadable.",
        ]
    return [
        "Review the Pico status code in the command log.",
        "Verify the PicoScope 5244D is connected by USB and not held open by PicoScope GUI.",
        "Adjust recipes/picoscope_settings_test.yaml only if the test settings should differ.",
        "Re-run this check with native Windows Python.",
    ]


if __name__ == "__main__":
    raise SystemExit(main())
