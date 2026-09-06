#!/usr/bin/env python3
"""Repeat safe-idle T660 application/readback on real hardware.

Usage:
    python software/tests/hardware_checks/check_t660_reproducibility.py --operator "Name" --confirm-real-hardware

The script opens the configured real T660-1 and T660-2 sessions. If either unit
is unavailable, it writes evidence/experiments/runs/YYYYMMDD_t660_reproducibility/BLOCKED.md and
exits nonzero. It does not simulate T660 responses.
"""

from __future__ import annotations

from _common import REPO_ROOT, today_stamp, utc_now, write_blocked, write_json

import argparse
from datetime import UTC, datetime
from pathlib import Path
import yaml

from control_app.config_loader import load_config_inventory
from control_app.devices.t660_service import T660Service
from control_app.manifest import new_manifest, write_manifest
from control_app.workflows.timing_recipe_manager import TimingRecipeManager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--confirm-real-hardware", action="store_true", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = REPO_ROOT / "evidence" / "experiments" / "runs" / f"{today_stamp()}_t660_reproducibility_{datetime.now(UTC):%H%M%S%fZ}"
    run_dir.mkdir(parents=True, exist_ok=False)
    command_log_path = run_dir / "command_log.txt"
    readback_path = run_dir / "t660_readback_before_after.json"
    error_flags_path = run_dir / "error_flags.json"
    manifest_path = run_dir / "run_manifest.json"
    inventory = load_config_inventory(write_files=True)
    safe_recipe = yaml.safe_load((REPO_ROOT / "instrument" / "recipes" / "safe_idle.yaml").read_text(encoding="utf-8"))
    resolved = TimingRecipeManager(inventory).validate_recipe(safe_recipe)["resolved_settings"]
    results: list[dict] = []
    errors: list[str] = []

    with command_log_path.open("a", encoding="utf-8") as command_log:
        command_log.write(f"{utc_now()} check_t660_reproducibility start operator={args.operator}\n")
        try:
            for cycle in range(1, 6):
                cycle_result = {"cycle": cycle, "devices": {}}
                results.append(cycle_result)
                for unit in ("t660_1", "t660_2"):
                    service = T660Service.from_config(
                        unit,
                        config_path=inventory.config_path,
                        command_log=command_log,
                        timeout_s=0.5,
                    )
                    try:
                        service.connect()
                        identity = service.identify()
                        firmware = service.get_firmware_version()
                        before = service.read_active_settings()
                        service.apply_recipe(resolved[unit])
                        after = service.read_active_settings()
                        service.force_eod()
                        cycle_result["devices"][unit] = {
                            "identity": identity,
                            "firmware": firmware,
                            "before": before,
                            "after": after,
                        }
                        mismatches = TimingRecipeManager._compare_readback({unit: resolved[unit]}, {unit: after})
                        cycle_result["devices"][unit]["mismatches"] = mismatches
                        if mismatches:
                            raise RuntimeError(f"{unit} safe-idle state did not verify: {mismatches}")
                    finally:
                        service.close()
                cycle_result["complete"] = True
        except Exception as exc:
            errors.append(str(exc))

    write_json(readback_path, {"cycles": results})
    blocked = bool(errors)
    error_flags = {
        "timestamp_utc": utc_now(),
        "blocked": blocked,
        "errors": errors,
        "cycles_completed": sum(result.get("complete", False) for result in results),
    }
    write_json(error_flags_path, error_flags)
    manifest = new_manifest(
        operator=args.operator,
        inventory=inventory,
        t660_recipes=["instrument/recipes/safe_idle.yaml"],
        raw_data_paths=[],
        command_log_paths=[str(command_log_path)],
        device_readback_paths=[str(readback_path), str(error_flags_path)],
        error_state={"has_error": blocked, "errors": errors},
        blocker_status={
            "blocked": blocked,
            "blockers": errors,
            "next_actions": [
                "Run from Windows Python if WSL cannot open COM ports.",
                "Verify T660-1 COM3 and T660-2 COM7 are connected and not held by another process.",
            ]
            if blocked
            else [],
        },
    )
    write_manifest(manifest_path, manifest)
    if blocked:
        write_blocked(
            run_dir / "BLOCKED.md",
            title="T660 Reproducibility BLOCKED",
            blockers=errors,
            next_actions=manifest["blocker_status"]["next_actions"],
            context={"run_dir": str(run_dir)},
        )
        print(f"BLOCKED see {run_dir / 'BLOCKED.md'}")
        return 2
    print(f"PASS wrote {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
