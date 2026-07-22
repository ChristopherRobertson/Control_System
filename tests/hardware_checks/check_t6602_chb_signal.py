#!/usr/bin/env python3
"""Hold T660-2 CHB at 2 MHz / 150 ns for physical signal verification.

Usage:
    python tests/hardware_checks/check_t6602_chb_signal.py --operator "Name" --confirm-real-hardware --confirm-safe-electrical-routing

Connect T660-2 CHB to an oscilloscope, frequency counter, or a properly
terminated BNC T before running. The script applies safe idle first, starts
only T660-2 CHB, waits until Enter or --duration-s, then applies safe idle.
"""

from __future__ import annotations

from _common import REPO_ROOT, today_stamp, utc_now, write_blocked, write_json

import argparse
import time

from control_app.config_loader import load_config_inventory
from control_app.manifest import new_manifest, write_manifest
from control_app.workflows.timing_recipe_manager import TimingRecipeManager


SIGNAL_RECIPE = {
    "name": "t6602_chb_signal_verification_2mhz",
    "description": "Physical verification of T660-2 CHB only: 2 MHz, 150 ns, positive, 50 ohm.",
    "approved_laser_safety_condition": True,
    "electrical_signal_verification_only": True,
    "t660": {
        "t660_2": {
            "stop_first": True,
            "clock": {
                "frequency": "2MHz",
                "shots": 0,
            },
            "trigger_source": "SYN",
            "force_eod": True,
            "start": True,
            "signals": {
                "hf2li_extref": {"enabled": False},
                "mircat_trig_in": {
                    "delay": 0,
                    "width": "150ns",
                    "polarity": "positive",
                    "termination": "50OHM",
                    "enabled": True,
                },
                "hf2li_daq_trigger": {"enabled": False},
                "t660_1_trig_in": {"enabled": False},
            },
        },
        "t660_1": {
            "stop_first": True,
            "trigger_source": "OFF",
            "force_eod": True,
            "channels": {
                "A": {"enabled": False},
                "B": {"enabled": False},
                "C": {"enabled": False},
                "D": {"enabled": False},
            },
        },
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--confirm-real-hardware", action="store_true", required=True)
    parser.add_argument(
        "--confirm-safe-electrical-routing",
        action="store_true",
        required=True,
        help=(
            "Confirms CHB is connected to a safe scope/frequency-counter path or "
            "the MIRcat emission gate is off before the diagnostic pulse train starts."
        ),
    )
    parser.add_argument(
        "--duration-s",
        type=float,
        default=None,
        help="Optional hold time. Omit to run until Enter is pressed.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = REPO_ROOT / "runs" / f"{today_stamp()}_t6602_chb_signal_verification"
    run_dir.mkdir(parents=True, exist_ok=True)
    command_log_path = run_dir / "command_log.txt"
    manifest_path = run_dir / "run_manifest.json"
    inventory = load_config_inventory(write_files=True)
    readback_paths: list[str] = []
    errors: list[str] = []
    stop_reason = "not_started"

    with command_log_path.open("a", encoding="utf-8") as command_log:
        command_log.write(
            f"{utc_now()} check_t6602_chb_signal start operator={args.operator}\n"
        )
        manager = TimingRecipeManager(inventory, command_log=command_log)
        try:
            safe_before_path = run_dir / "safe_idle_before_chb_verification_readback.json"
            print(
                "Applying safe idle before CHB verification. This touches configured T660 units.",
                flush=True,
            )
            manager.apply_recipe(REPO_ROOT / "recipes" / "safe_idle.yaml", output_path=safe_before_path)
            readback_paths.append(str(safe_before_path))
            print(f"Safe idle readback written to {safe_before_path}", flush=True)

            start_path = run_dir / "t6602_chb_2mhz_150ns_readback.json"
            print("Starting T660-2 CHB only at 2 MHz / 150 ns...", flush=True)
            readback = manager.apply_recipe(SIGNAL_RECIPE, output_path=start_path)
            readback_paths.append(str(start_path))
            write_json(run_dir / "signal_verification_request.json", SIGNAL_RECIPE)

            print(
                "T660-2 CHB_RUNNING: expect 2 MHz period, 150 ns high time, positive polarity, 50 ohm output.",
                flush=True,
            )
            print(f"Readback written to {start_path}", flush=True)
            summarize_chb_readback(readback)
            stop_reason = wait_for_stop(args)
        except KeyboardInterrupt:
            stop_reason = "keyboard_interrupt"
            print("\nKeyboard interrupt received; applying safe idle.", flush=True)
        except Exception as exc:  # noqa: BLE001 - hardware check boundary records exact blocker
            errors.append(str(exc))
        finally:
            try:
                safe_after_path = run_dir / "safe_idle_after_chb_verification_readback.json"
                print("Applying safe idle after CHB verification...", flush=True)
                manager.apply_recipe(REPO_ROOT / "recipes" / "safe_idle.yaml", output_path=safe_after_path)
                readback_paths.append(str(safe_after_path))
                print(f"Safe idle cleanup readback written to {safe_after_path}", flush=True)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"safe_idle cleanup failed: {exc}")

    blocked = bool(errors)
    manifest = new_manifest(
        operator=args.operator,
        inventory=inventory,
        t660_recipes=["recipes/safe_idle.yaml", SIGNAL_RECIPE],
        command_log_paths=[str(command_log_path)],
        device_readback_paths=readback_paths,
        error_state={"has_error": blocked, "errors": errors},
        abort_state={"aborted": False, "reason": stop_reason},
        blocker_status={
            "blocked": blocked,
            "blockers": errors,
            "next_actions": [
                "Verify T660-2 COM7 is connected and not held by another process.",
                "Measure directly at T660-2 CHB with a 50 ohm terminated scope input.",
                "If CHB is correct at the T660 but not at MIRcat TRIG IN, inspect the BNC cable or input adapter.",
            ]
            if blocked
            else [],
        },
    )
    write_manifest(manifest_path, manifest)

    if blocked:
        write_blocked(
            run_dir / "BLOCKED.md",
            title="T660-2 CHB Signal Verification BLOCKED",
            blockers=errors,
            next_actions=manifest["blocker_status"]["next_actions"],
            context={"config_hash": inventory.config_hash, "run_dir": str(run_dir)},
        )
        print(f"BLOCKED see {run_dir / 'BLOCKED.md'}")
        return 2

    print(f"PASS CHB diagnostic stopped cleanly; wrote {run_dir}")
    return 0


def wait_for_stop(args: argparse.Namespace) -> str:
    if args.duration_s is not None:
        deadline = time.time() + args.duration_s
        print(f"Holding CHB for {args.duration_s:g} s. Press Ctrl+C to stop early.", flush=True)
        while time.time() < deadline:
            time.sleep(min(1.0, max(0.0, deadline - time.time())))
        return "duration_elapsed"

    print("CHB is intentionally held ON. Press Enter to stop CHB and apply safe idle.", flush=True)
    input()
    return "operator_enter"


def summarize_chb_readback(readback: dict) -> None:
    t660_2 = (readback.get("devices") or {}).get("t660_2", {})
    queries = t660_2.get("queries") or {}
    chb = ((t660_2.get("channels") or {}).get("B")) or {}
    print("Controller readback:", flush=True)
    print(f"  trigger_source={queries.get('trigger_source')}", flush=True)
    print(f"  synth_frequency={queries.get('synth_frequency')}", flush=True)
    print(f"  CHB enabled={chb.get('enabled')}", flush=True)
    print(f"  CHB timing_mode={chb.get('timing_mode')}", flush=True)
    print(f"  CHB termination={chb.get('termination')}", flush=True)
    print(f"  CHB delay_edge={chb.get('delay_edge')}", flush=True)
    print(f"  CHB width_edge={chb.get('width_edge')}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
