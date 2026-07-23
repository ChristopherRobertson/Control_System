#!/usr/bin/env python3
"""Run one rewired fast MIRcat spectral sweep.

Usage:
    py tests\\hardware_checks\\check_mircat_fast_sweep.py --operator "Chris" \
        --confirm-real-hardware --confirm-laser-safety \
        --confirm-mircat-trig-out-to-hf2li-dio0-and-dio1

This workflow is for the rewired fast path:
- MIRcat TRIG OUT -> HF2LI DIO0 EXT REF.
- MIRcat TRIG OUT -> HF2LI DIO1 for the LabOne Plotter trigger/marker.
- T660-2 CHB disconnected from MIRcat TRIG IN.
"""

from __future__ import annotations

from _common import REPO_ROOT, utc_now, write_blocked, write_json

import argparse
from datetime import datetime
from pathlib import Path

from control_app.config_loader import load_config_inventory
from control_app.workflows.mircat_fast_sweep import (
    DEFAULT_FAST_SWEEP_RECIPE,
    MircatFastSweepWorkflow,
    apply_fast_sweep_overrides,
    load_fast_sweep_request,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", default="Codex")
    parser.add_argument("--recipe", default=DEFAULT_FAST_SWEEP_RECIPE)
    parser.add_argument("--sample-name")
    parser.add_argument("--start-cm1", type=float)
    parser.add_argument("--stop-cm1", type=float)
    parser.add_argument("--scan-rate-cm1-s", type=float)
    parser.add_argument("--repetitions", type=int)
    parser.add_argument("--pre-sweep-record-s", type=float)
    parser.add_argument("--post-sweep-record-s", type=float)
    parser.add_argument(
        "--confirm-real-hardware",
        action="store_true",
        help="Permit real MIRcat, HF2LI, and optional T660 calls.",
    )
    parser.add_argument(
        "--confirm-laser-safety",
        action="store_true",
        help="Confirm approved conditions for opening MIRcat emission.",
    )
    parser.add_argument(
        "--confirm-mircat-trig-out-to-hf2li-dio0-and-dio1",
        "--confirm-rewired-mircat-trig-out-to-hf2li-dio1",
        dest="confirm_mircat_trig_out_to_hf2li_dio0_and_dio1",
        action="store_true",
        help="Confirm MIRcat TRIG OUT is connected/split to HF2LI DIO0 and DIO1, and T660-2 CHB is not driving MIRcat TRIG IN.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    recipe_path = _resolve_recipe(args.recipe)
    request = load_fast_sweep_request(recipe_path)
    request = apply_fast_sweep_overrides(
        request,
        {
            "sample_name": args.sample_name,
            "start_cm1": args.start_cm1,
            "stop_cm1": args.stop_cm1,
            "scan_rate_cm1_s": args.scan_rate_cm1_s,
            "repetitions": args.repetitions,
            "pre_sweep_record_s": args.pre_sweep_record_s,
            "post_sweep_record_s": args.post_sweep_record_s,
            "approved_laser_safety_condition": args.confirm_laser_safety,
            "require_rewired_mircat_trig_out_to_hf2li_dio0": (
                args.confirm_mircat_trig_out_to_hf2li_dio0_and_dio1
            ),
            "require_rewired_mircat_trig_out_to_hf2li_dio1": (
                args.confirm_mircat_trig_out_to_hf2li_dio0_and_dio1
            ),
        },
    )

    safe_name = "".join(ch if ch.isalnum() else "_" for ch in request.sample_name.lower()).strip("_")
    run_dir = REPO_ROOT / "calibration" / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}_fast_sweep"
    run_dir.mkdir(parents=True, exist_ok=True)
    command_log_path = run_dir / "command_log.txt"
    summary_path = run_dir / "fast_sweep_check_summary.json"
    inventory = load_config_inventory(write_files=True)
    workflow = MircatFastSweepWorkflow(operator=args.operator, inventory=inventory)

    blockers = _preflight_blockers(args)
    with command_log_path.open("w", encoding="utf-8") as command_log:
        command_log.write(
            f"{utc_now()} check_mircat_fast_sweep start "
            f"operator={args.operator} recipe={recipe_path} "
            f"confirm_real_hardware={args.confirm_real_hardware} "
            f"confirm_laser_safety={args.confirm_laser_safety} "
            "confirm_mircat_trig_out_to_hf2li_dio0_and_dio1="
            f"{args.confirm_mircat_trig_out_to_hf2li_dio0_and_dio1}\n"
        )
        if blockers:
            workflow.command_log_paths.append(str(command_log_path))
            summary = {
                "timestamp_utc": utc_now(),
                "operator": args.operator,
                "config_hash": inventory.config_hash,
                "recipe_path": str(recipe_path),
                "request": request.to_dict(),
                "status": "BLOCKED",
                "blockers": blockers,
            }
            write_json(summary_path, summary)
            workflow.device_readback_paths.append(str(summary_path))
            manifest_path = workflow.write_manifest(
                request=request,
                run_dir=run_dir,
                blocked=True,
                blockers=blockers,
            )
            blocked_path = _write_blocked(run_dir, blockers, manifest_path, command_log_path)
            print(f"BLOCKED see {blocked_path}")
            return 2

        errors: list[str] = []
        try:
            summary = workflow.run(
                request=request,
                run_dir=run_dir,
                command_log=command_log,
            )
        except Exception as exc:  # noqa: BLE001 - hardware check records exact blocker
            errors.append(str(exc))
            summary = {
                "timestamp_utc": utc_now(),
                "operator": args.operator,
                "config_hash": inventory.config_hash,
                "recipe_path": str(recipe_path),
                "request": request.to_dict(),
                "status": "FAILED",
                "errors": errors,
            }
        write_json(summary_path, summary)
        workflow.device_readback_paths.append(str(summary_path))

    manifest_path = workflow.write_manifest(
        request=request,
        run_dir=run_dir,
        errors=errors,
        blocked=bool(errors),
        blockers=errors,
    )
    if errors:
        blocked_path = _write_blocked(run_dir, errors, manifest_path, command_log_path)
        print(f"FAILED see {blocked_path}")
        return 1
    print(f"PASS wrote {run_dir}")
    return 0


def _resolve_recipe(recipe: str) -> Path:
    path = Path(recipe)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"recipe not found: {path}")
    return path


def _preflight_blockers(args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    if not args.confirm_real_hardware:
        blockers.append(
            "Real hardware execution was not confirmed. Re-run from native Windows Python with --confirm-real-hardware."
        )
    if not args.confirm_laser_safety:
        blockers.append(
            "Laser safety approval was not confirmed. Re-run only after beam path, detector protection, and operator conditions are approved."
        )
    if not args.confirm_mircat_trig_out_to_hf2li_dio0_and_dio1:
        blockers.append(
            "Required rewire was not confirmed: MIRcat TRIG OUT -> HF2LI DIO0 EXT REF and HF2LI DIO1 Plotter trigger, with T660-2 CHB disconnected from MIRcat TRIG IN."
        )
    return blockers


def _write_blocked(
    run_dir: Path,
    blockers: list[str],
    manifest_path: Path,
    command_log_path: Path,
) -> Path:
    return write_blocked(
        run_dir / "BLOCKED.md",
        title="MIRcat Fast Sweep BLOCKED",
        blockers=blockers,
        next_actions=[
            "Confirm MIRcat TRIG OUT reaches both HF2LI DIO0 EXT REF and HF2LI DIO1 Plotter trigger before using fast-sweep data for article claims.",
            "Close the manufacturer MIRcat UI before rerunning because the SDK controller is single-client.",
            "Keep the manifest and BLOCKED file with the run folder for traceability.",
        ],
        context={
            "manifest": str(manifest_path),
            "command_log": str(command_log_path),
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())
