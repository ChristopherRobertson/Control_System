#!/usr/bin/env python3
"""Run the real MIRcat safe status/tune check.

Usage:
    python tests/hardware_checks/check_mircat_status_tune.py --operator "Name" --confirm-real-hardware

The manufacturer MIRcat UI must be closed before this script runs. The Daylight
controller allows only one owner at a time, so an initialization or communication
failure is recorded as BLOCKED rather than replaced with a simulated pass.
"""

from __future__ import annotations

from _common import REPO_ROOT, today_stamp, utc_now, write_blocked

import argparse

from control_app.config_loader import load_config_inventory
from control_app.manifest import new_manifest, write_manifest
from control_app.workflows.mircat_status_tune import (
    DEFAULT_LAMBDA_MID_CM1,
    MircatStatusTune,
    MircatTuneRequest,
    connection_owner_next_actions,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--confirm-real-hardware", action="store_true", required=True)
    parser.add_argument("--wavenumber-cm1", type=float, default=DEFAULT_LAMBDA_MID_CM1)
    parser.add_argument("--qcl", type=int, default=1)
    parser.add_argument("--tec-timeout-s", type=float, default=120.0)
    parser.add_argument("--tune-timeout-s", type=float, default=120.0)
    parser.add_argument("--poll-interval-s", type=float, default=0.5)
    parser.add_argument(
        "--allow-emission-on",
        action="store_true",
        help="Only use with explicit lab approval; omitted for the safe-state gate.",
    )
    parser.add_argument(
        "--approved-laser-safety-condition",
        action="store_true",
        help="Required if --allow-emission-on is used.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = REPO_ROOT / "runs" / f"{today_stamp()}_mircat_status_tune"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_dir = REPO_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    command_log_path = log_dir / f"{today_stamp()}_mircat_status_tune_command_log.txt"
    manifest_path = run_dir / "run_manifest.json"
    inventory = load_config_inventory(write_files=True)

    blockers = preflight_blockers(args, inventory)
    if blockers:
        next_actions = connection_owner_next_actions(blockers)
        manifest = new_manifest(
            operator=args.operator,
            inventory=inventory,
            mircat_setpoint={"value": args.wavenumber_cm1, "units": "cm^-1", "qcl": args.qcl},
            command_log_paths=[str(command_log_path)],
            error_state={"has_error": True, "errors": blockers},
            blocker_status={
                "blocked": True,
                "blockers": blockers,
                "next_actions": next_actions,
            },
        )
        write_manifest(manifest_path, manifest)
        write_blocked(
            run_dir / "BLOCKED.md",
            title="MIRcat Status/Tune BLOCKED",
            blockers=blockers,
            next_actions=next_actions,
            context={},
        )
        command_log_path.write_text(
            f"{utc_now()} BLOCKED before hardware open: {'; '.join(blockers)}\n",
            encoding="utf-8",
        )
        print(f"BLOCKED see {run_dir / 'BLOCKED.md'}")
        return 2

    errors: list[str] = []
    with command_log_path.open("a", encoding="utf-8") as command_log:
        command_log.write(
            f"{utc_now()} check_mircat_status_tune start "
            f"operator={args.operator} wavenumber_cm1={args.wavenumber_cm1} qcl={args.qcl}\n"
        )
        try:
            workflow = MircatStatusTune(operator=args.operator, inventory=inventory)
            workflow.run(
                request=MircatTuneRequest(
                    wavenumber_cm1=args.wavenumber_cm1,
                    qcl=args.qcl,
                    tec_timeout_s=args.tec_timeout_s,
                    tune_timeout_s=args.tune_timeout_s,
                    poll_interval_s=args.poll_interval_s,
                    approved_laser_safety_condition=args.approved_laser_safety_condition,
                    allow_emission_on=args.allow_emission_on,
                ),
                run_dir=run_dir,
                command_log=command_log,
                command_log_paths=[str(command_log_path)],
            )
        except Exception as exc:
            errors.append(str(exc))

    if errors:
        next_actions = connection_owner_next_actions(errors)
        manifest = new_manifest(
            operator=args.operator,
            inventory=inventory,
            mircat_setpoint={"value": args.wavenumber_cm1, "units": "cm^-1", "qcl": args.qcl},
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
            title="MIRcat Status/Tune BLOCKED",
            blockers=errors,
            next_actions=next_actions,
            context={
                "wavenumber_cm1": args.wavenumber_cm1,
                "qcl": args.qcl,
            },
        )
        print(f"BLOCKED see {run_dir / 'BLOCKED.md'}")
        return 2

    blocked_path = run_dir / "BLOCKED.md"
    if blocked_path.exists():
        blocked_path.unlink()
    print(f"PASS wrote {run_dir}")
    return 0


def preflight_blockers(args: argparse.Namespace, inventory) -> list[str]:
    blockers: list[str] = []
    mircat = inventory.devices.get("mircat")
    if not isinstance(mircat, dict):
        blockers.append("hardware_configuration.yaml does not define devices.mircat")
        return blockers
    if not mircat.get("model_number"):
        blockers.append("devices.mircat.model_number is missing")
    if not mircat.get("serial_number"):
        blockers.append("devices.mircat.serial_number is missing")
    if not mircat.get("preferred_port"):
        blockers.append("devices.mircat.preferred_port is missing")
    if args.qcl < 1 or args.qcl > 4:
        blockers.append("QCL must be in the SDK-supported range 1..4")
    if args.wavenumber_cm1 <= 0:
        blockers.append("wavenumber_cm1 must be positive")
    if args.allow_emission_on and not args.approved_laser_safety_condition:
        blockers.append("--allow-emission-on requires --approved-laser-safety-condition")
    return blockers


if __name__ == "__main__":
    raise SystemExit(main())
