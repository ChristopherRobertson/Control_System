#!/usr/bin/env python3
"""Run MIRcat detector alignment with optional T660 external timing.

Usage:
    python software/tests/hardware_checks/check_mircat_detector_alignment.py --operator "Name" --confirm-real-hardware --approved-laser-safety-condition

By default this operational hardware check uses the T660 external timing path.
Pass --use-internal-mircat-timing to use MIRcat internal pulsing
without starting T660-2. The UI Start Alignment button defaults to the internal
MIRcat mode.
"""

from __future__ import annotations

from _common import REPO_ROOT, today_stamp, utc_now, write_blocked

import argparse
import time

from control_app.config_loader import load_config_inventory
from control_app.manifest import new_manifest, write_manifest
from control_app.workflows.mircat_detector_alignment import (
    DEFAULT_PULSE_RATE_HZ,
    DEFAULT_PULSE_WIDTH_NS,
    DEFAULT_QCL,
    DEFAULT_WAVENUMBER_CM1,
    DEFAULT_CURRENT_MA,
    DEFAULT_HF2LI_PRESET,
    EXTERNAL_T660_HF2LI_PRESET,
    ALIGNMENT_TIMING_RECIPE,
    SAFE_IDLE_RECIPE,
    MircatDetectorAlignmentRequest,
    MircatDetectorAlignmentWorkflow,
)
from control_app.workflows.mircat_status_tune import connection_owner_next_actions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--confirm-real-hardware", action="store_true", required=True)
    parser.add_argument(
        "--approved-laser-safety-condition",
        action="store_true",
        help="Required to open MIRcat emission during alignment.",
    )
    parser.add_argument("--wavenumber-cm1", type=float, default=DEFAULT_WAVENUMBER_CM1)
    parser.add_argument("--qcl", type=int, default=DEFAULT_QCL)
    parser.add_argument("--pulse-rate-hz", type=float, default=DEFAULT_PULSE_RATE_HZ)
    parser.add_argument("--pulse-width-ns", type=float, default=DEFAULT_PULSE_WIDTH_NS)
    parser.add_argument(
        "--current-ma",
        type=float,
        default=DEFAULT_CURRENT_MA,
        help="MIRcat QCL current in mA. Defaults to the detector-alignment recipe value.",
    )
    parser.add_argument("--hf2li-preset", default=None)
    parser.add_argument("--tec-timeout-s", type=float, default=120.0)
    parser.add_argument("--tune-timeout-s", type=float, default=120.0)
    parser.add_argument("--poll-interval-s", type=float, default=0.5)
    parser.add_argument(
        "--duration-s",
        type=float,
        default=None,
        help="Optional alignment duration. Omit to run until Enter is pressed.",
    )
    parser.add_argument(
        "--stop-only",
        action="store_true",
        help="Apply T660 safe idle and close/disarm/deinitialize MIRcat without starting alignment.",
    )
    parser.add_argument(
        "--use-internal-mircat-timing",
        action="store_true",
        help="Do not start T660 timing; use MIRcat internal pulse timing for alignment.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = REPO_ROOT / "evidence" / "experiments" / "runs" / f"{today_stamp()}_mircat_detector_alignment"
    run_dir.mkdir(parents=True, exist_ok=True)
    command_log_path = run_dir / "command_log.txt"
    manifest_path = run_dir / "run_manifest.json"
    inventory = load_config_inventory(write_files=True)
    workflow = MircatDetectorAlignmentWorkflow(operator=args.operator, inventory=inventory)

    errors = preflight_blockers(args)
    started = False
    stop_reason = "not_started"

    with command_log_path.open("a", encoding="utf-8") as command_log:
        command_log.write(
            f"{utc_now()} check_mircat_detector_alignment start "
            f"operator={args.operator} stop_only={args.stop_only}\n"
        )
        if not errors:
            try:
                if args.stop_only:
                    workflow.stop_alignment(
                        run_dir=run_dir,
                        command_log=command_log,
                        reason="stop_only",
                    )
                    stop_reason = "stop_only"
                else:
                    request = MircatDetectorAlignmentRequest(
                        wavenumber_cm1=args.wavenumber_cm1,
                        qcl=args.qcl,
                        pulse_rate_hz=args.pulse_rate_hz,
                        pulse_width_ns=args.pulse_width_ns,
                        current_ma=args.current_ma,
                        hf2li_preset=(
                            args.hf2li_preset
                            or (
                                DEFAULT_HF2LI_PRESET
                                if args.use_internal_mircat_timing
                                else EXTERNAL_T660_HF2LI_PRESET
                            )
                        ),
                        tec_timeout_s=args.tec_timeout_s,
                        tune_timeout_s=args.tune_timeout_s,
                        poll_interval_s=args.poll_interval_s,
                        approved_laser_safety_condition=args.approved_laser_safety_condition,
                        use_t660_timing=not args.use_internal_mircat_timing,
                    )
                    workflow.start_alignment(
                        request=request,
                        run_dir=run_dir,
                        command_log=command_log,
                    )
                    started = True
                    stop_reason = wait_for_stop(args)
            except KeyboardInterrupt:
                stop_reason = "keyboard_interrupt"
                print("\nKeyboard interrupt received; stopping alignment.", flush=True)
            except Exception as exc:  # noqa: BLE001 - hardware check boundary records all blockers
                errors.append(str(exc))
            finally:
                if started or workflow.t660_running or workflow.mircat_initialized:
                    try:
                        workflow.stop_alignment(
                            run_dir=run_dir,
                            command_log=command_log,
                            reason=stop_reason,
                        )
                        started = False
                    except Exception as exc:  # noqa: BLE001
                        errors.append(str(exc))

    blocked = bool(errors)
    manifest = new_manifest(
        operator=args.operator,
        inventory=inventory,
        t660_recipes=[SAFE_IDLE_RECIPE] if args.stop_only else [SAFE_IDLE_RECIPE, ALIGNMENT_TIMING_RECIPE],
        mircat_setpoint=workflow.mircat_setpoint,
        mircat_actual_wavelength=workflow.mircat_actual_wavelength,
        hf2li_settings_snapshot=workflow.hf2li_settings_snapshot,
        command_log_paths=[str(command_log_path)],
        device_readback_paths=workflow.device_readback_paths,
        error_state={"has_error": blocked, "errors": errors},
        abort_state={"aborted": False, "reason": stop_reason},
        blocker_status={
            "blocked": blocked,
            "blockers": errors,
            "next_actions": alignment_next_actions(errors) if blocked else [],
        },
    )
    write_manifest(manifest_path, manifest)

    if blocked:
        write_blocked(
            run_dir / "BLOCKED.md",
            title="MIRcat Detector Alignment BLOCKED",
            blockers=errors,
            next_actions=manifest["blocker_status"]["next_actions"],
            context={"run_dir": str(run_dir)},
        )
        print(f"BLOCKED see {run_dir / 'BLOCKED.md'}")
        return 2

    blocked_path = run_dir / "BLOCKED.md"
    if blocked_path.exists():
        blocked_path.unlink()
    if args.stop_only:
        print(f"PASS stopped alignment hardware; wrote {run_dir}")
    else:
        print(f"PASS alignment stopped cleanly; wrote {run_dir}")
    return 0


def wait_for_stop(args: argparse.Namespace) -> str:
    if args.duration_s is not None:
        deadline = time.time() + args.duration_s
        print(
            f"ALIGNMENT_RUNNING for {args.duration_s:g} s. Press Ctrl+C to stop early.",
            flush=True,
        )
        while time.time() < deadline:
            time.sleep(min(1.0, max(0.0, deadline - time.time())))
        return "duration_elapsed"

    print("ALIGNMENT_RUNNING. Press Enter to stop T660 and close MIRcat emission.", flush=True)
    input()
    return "operator_enter"


def preflight_blockers(args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    if args.duration_s is not None and args.duration_s <= 0:
        blockers.append("--duration-s must be positive when provided")
    if args.current_ma is not None and args.current_ma <= 0:
        blockers.append("--current-ma must be positive when provided")
    if not args.stop_only and not args.approved_laser_safety_condition:
        blockers.append("--approved-laser-safety-condition is required to open MIRcat emission")
    return blockers


def alignment_next_actions(errors: list[str]) -> list[str]:
    actions = connection_owner_next_actions(errors)
    actions.extend(
        [
            "Run this script with --stop-only to force T660 safe idle and MIRcat emission off.",
            "Verify T660-2 COM7 and T660-1 COM3 are not held by another process.",
            "Verify T660-2 CHB is physically connected to MIRcat TRIG IN.",
            "Verify T660-2 CHA is physically connected to HF2LI DIO 0 external reference.",
        ]
    )
    return list(dict.fromkeys(actions))


if __name__ == "__main__":
    raise SystemExit(main())
