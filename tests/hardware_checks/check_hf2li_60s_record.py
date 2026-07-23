#!/usr/bin/env python3
"""Capture a real 60 s HF2LI detector record through LabOne.

Usage:
    python tests/hardware_checks/check_hf2li_60s_record.py --operator "Name" --confirm-real-hardware

This check never simulates detector data. If LabOne, the configured HF2LI, or
the approved detector input is unavailable, it writes BLOCKED.md and a manifest
instead of creating artificial data.
"""

from __future__ import annotations

from _common import REPO_ROOT, today_stamp, utc_now, write_blocked

import argparse
from pathlib import Path

from control_app.config_loader import load_config_inventory
from control_app.manifest import new_manifest, write_manifest
from control_app.workflows.hf2li_60s_record import HF2LIRecordWorkflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--confirm-real-hardware", action="store_true", required=True)
    parser.add_argument("--preset", default="dark_baseline")
    parser.add_argument("--duration-s", type=float, default=60.0)
    parser.add_argument("--presets-path", default="recipes/hf2li_presets.yaml")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = REPO_ROOT / "calibration" / f"{today_stamp()}_hf2li_60s_record"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_dir = REPO_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    command_log_path = log_dir / f"{today_stamp()}_hf2li_60s_record_command_log.txt"
    manifest_path = run_dir / "run_manifest.json"
    inventory = load_config_inventory(write_files=True)

    errors: list[str] = []
    with command_log_path.open("a", encoding="utf-8") as command_log:
        command_log.write(
            f"{utc_now()} check_hf2li_60s_record start operator={args.operator} "
            f"preset={args.preset} duration_s={args.duration_s}\n"
        )
        try:
            workflow = HF2LIRecordWorkflow(operator=args.operator, inventory=inventory)
            workflow.run(
                run_dir=run_dir,
                preset_name=args.preset,
                duration_s=args.duration_s,
                command_log=command_log,
                command_log_paths=[str(command_log_path)],
                presets_path=args.presets_path,
            )
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")

    if errors:
        next_actions = _next_actions(errors)
        manifest = new_manifest(
            operator=args.operator,
            inventory=inventory,
            hf2li_settings_snapshot={
                "preset": args.preset,
                "presets_path": args.presets_path,
                "settings_snapshot_path": None,
                "settings_reload_comparison_path": None,
            },
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
            title="HF2LI 60 s Record BLOCKED",
            blockers=errors,
            next_actions=next_actions,
            context={
                "config_hash": inventory.config_hash,
                "config_path": inventory.config_path,
                "preset": args.preset,
                "duration_s": args.duration_s,
                "command_log": str(command_log_path),
            },
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
    if "zhinst.ziPython" in joined:
        return [
            "Run with Windows Python and keep C:\\Users\\Chris\\AppData\\Local\\Temp\\zhinst_26_4 available, or set ZHINST_PYTHON_PATH to the LabOne Python API directory.",
            "Install the Zurich Instruments LabOne Python API if the temporary package directory is no longer present.",
            "Re-run the HF2LI 60 s record check after the import path is fixed.",
        ]
    if "LabOne API server connection failed" in joined:
        return [
            "Start the Zurich Instruments LabOne Data Server on 127.0.0.1:8005.",
            "Verify the HF2LI is connected and visible in LabOne before rerunning.",
            "Keep using the configured device dev18500 from hardware_configuration.yaml unless the operator updates the configuration.",
        ]
    if "not discovered" in joined or "not reachable" in joined:
        return [
            "Verify HF2LI dev18500 is powered, connected, and visible in LabOne.",
            "Confirm hardware_configuration.yaml device_id matches the LabOne device ID.",
            "Re-run only after LabOne discovery shows the configured HF2LI.",
        ]
    if "returned no sample rows" in joined:
        return [
            "Verify CH1/CH2 detector outputs are connected to HF2LI Signal Input 1 and Signal Input 2.",
            "Verify the selected preset demodulators are enabled and have nonzero sample rates.",
            "Repeat the acquisition without changing data files manually.",
        ]
    return [
        "Review the HF2LI command log for the exact LabOne node or connection error.",
        "Verify LabOne, HF2LI dev18500, and approved detector input are available.",
        "Re-run the hardware check; do not substitute synthetic detector data.",
    ]


if __name__ == "__main__":
    raise SystemExit(main())
