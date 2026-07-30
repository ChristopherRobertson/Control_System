#!/usr/bin/env python3
"""Apply Day 3 timing recipes to real T660 hardware and save readbacks.

Usage:
    python tests/hardware_checks/check_timing_recipes.py --operator "Name" --confirm-real-hardware

If a T660 handshake fails or a readback mismatch occurs, the script writes
calibration/YYYYMMDD_timing_recipe_readbacks/BLOCKED.md and exits nonzero.
"""

from __future__ import annotations

from _common import REPO_ROOT, today_stamp, utc_now, write_blocked

import argparse

from control_app.config_loader import load_config_inventory
from control_app.manifest import new_manifest, write_manifest
from control_app.workflows.timing_recipe_manager import TimingRecipeManager


RECIPE_OUTPUTS = [
    ("recipes/safe_idle.yaml", "safe_idle_recipe_readback.json"),
    ("recipes/timing_calibration.yaml", "timing_calibration_recipe_readback.json"),
    ("recipes/pump_probe_single_point.yaml", "pump_probe_single_point_recipe_readback.json"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--confirm-real-hardware", action="store_true", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = REPO_ROOT / "calibration" / f"{today_stamp()}_timing_recipe_readbacks"
    run_dir.mkdir(parents=True, exist_ok=True)
    command_log_path = run_dir / "command_log.txt"
    manifest_path = run_dir / "run_manifest.json"
    inventory = load_config_inventory(write_files=True)
    errors: list[str] = []
    readback_paths: list[str] = []

    with command_log_path.open("a", encoding="utf-8") as command_log:
        command_log.write(f"{utc_now()} check_timing_recipes start operator={args.operator}\n")
        manager = TimingRecipeManager(inventory, command_log=command_log)
        for recipe_path, output_name in RECIPE_OUTPUTS:
            output_path = run_dir / output_name
            try:
                manager.apply_recipe(REPO_ROOT / recipe_path, output_path=output_path)
                readback_paths.append(str(output_path))
            except Exception as exc:
                errors.append(f"{recipe_path}: {exc}")
                break

    blocked = bool(errors)
    manifest = new_manifest(
        operator=args.operator,
        inventory=inventory,
        t660_recipes=[item[0] for item in RECIPE_OUTPUTS],
        command_log_paths=[str(command_log_path)],
        device_readback_paths=readback_paths,
        error_state={"has_error": blocked, "errors": errors},
        blocker_status={
            "blocked": blocked,
            "blockers": errors,
            "next_actions": [
                "Verify configured T660 COM ports are accessible.",
                "Run check_t660_reproducibility.py before timing recipe readbacks.",
                "Resolve any readback mismatch before using recipes in scans.",
            ]
            if blocked
            else [],
        },
    )
    write_manifest(manifest_path, manifest)
    if blocked:
        write_blocked(
            run_dir / "BLOCKED.md",
            title="Timing Recipe Readbacks BLOCKED",
            blockers=errors,
            next_actions=manifest["blocker_status"]["next_actions"],
            context={"run_dir": str(run_dir)},
        )
        print(f"BLOCKED see {run_dir / 'BLOCKED.md'}")
        return 2
    blocked_path = run_dir / "BLOCKED.md"
    if blocked_path.exists():
        blocked_path.unlink()
    print(f"PASS wrote {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
