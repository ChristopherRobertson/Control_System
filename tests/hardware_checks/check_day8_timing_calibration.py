#!/usr/bin/env python3
"""Run or validate Day 8 electrical timing calibration.

Usage examples:
    python tests/hardware_checks/check_day8_timing_calibration.py --operator "Name"
    python tests/hardware_checks/check_day8_timing_calibration.py --operator "Name" --confirm-real-hardware --confirm-safe-electrical-routing --confirm-scope-ch-a-trigger --cabling-note "Direct BNC routes verified by operator"

Without all hardware confirmations this check writes BLOCKED.md and a manifest
without opening devices. With confirmations, it programs real T660 outputs,
captures real PicoScope traces using CH A as the internal trigger, and writes
calibration/timing_offsets.yaml.
"""

from __future__ import annotations

from _common import REPO_ROOT, today_stamp, utc_now, write_blocked, write_json

import argparse
from pathlib import Path

from control_app.config_loader import load_config_inventory
from control_app.manifest import new_manifest, write_manifest
from control_app.workflows.day8_timing_calibration import (
    DEFAULT_SEPARATIONS_NS,
    DEFAULT_SHOT_COUNT,
    Day8TimingCalibration,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--confirm-real-hardware", action="store_true")
    parser.add_argument("--confirm-safe-electrical-routing", action="store_true")
    parser.add_argument("--confirm-scope-ch-a-trigger", action="store_true")
    parser.add_argument(
        "--confirm-picoscope-ext-reference",
        action="store_true",
        help="Legacy splitter-based mode flag; not required for CH A trigger Day 8 captures.",
    )
    parser.add_argument(
        "--cabling-note",
        default="",
        help="Operator note identifying direct PicoScope CH A and CH B cabling.",
    )
    parser.add_argument(
        "--picoscope-recipe",
        default="recipes/picoscope_settings_test.yaml",
        help="PicoScope capture recipe used for timing traces.",
    )
    parser.add_argument(
        "--shot-count",
        type=int,
        default=DEFAULT_SHOT_COUNT,
        help="Shots per pair/separation. Default is 100.",
    )
    parser.add_argument(
        "--separations-ns",
        default=",".join(str(value) for value in DEFAULT_SEPARATIONS_NS),
        help="Comma-separated programmed separations in ns.",
    )
    parser.add_argument(
        "--pair",
        action="append",
        dest="pairs",
        help="Optional pair_id to run. Repeat to select multiple pairs.",
    )
    parser.add_argument(
        "--reduced-set-rationale",
        default="",
        help="Required if shot count or separation list differs from Day 8 defaults.",
    )
    parser.add_argument(
        "--run-dir",
        default="",
        help="Optional run directory. Defaults to runs/YYYYMMDD_day8_timing_calibration.",
    )
    parser.add_argument(
        "--article-root",
        default="",
        help="Optional Article 1 RSI root for table/figure exports after acquisition.",
    )
    parser.add_argument(
        "--diagnostic-channel-skew",
        action="store_true",
        help=(
            "Run T660 channel-skew diagnostic pairs without merging into calibration/ "
            "or exporting Article outputs."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir) if args.run_dir else REPO_ROOT / "runs" / f"{today_stamp()}_day8_timing_calibration"
    if not run_dir.is_absolute():
        run_dir = REPO_ROOT / run_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    log_dir = REPO_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    command_log_path = log_dir / f"{today_stamp()}_day8_timing_calibration_command_log.txt"
    manifest_path = run_dir / "run_manifest.json"
    inventory = load_config_inventory(write_files=False)
    separations_ns = _parse_separations(args.separations_ns)
    reduced_set_rationale = args.reduced_set_rationale.strip() or None
    workflow = Day8TimingCalibration(operator=args.operator, inventory=inventory)

    blockers = _preflight_blockers(args)
    try:
        plan = workflow.validate_plan(
            separations_ns=separations_ns,
            shot_count=args.shot_count,
            reduced_set_rationale=reduced_set_rationale,
            pair_ids=args.pairs,
            include_diagnostic_pairs=args.diagnostic_channel_skew,
        )
        plan["operator_cabling_note"] = args.cabling_note
        plan["diagnostic_channel_skew"] = args.diagnostic_channel_skew
        plan_path = write_json(run_dir / "day8_timing_plan.json", plan)
    except Exception as exc:  # noqa: BLE001 - manifest records exact blocker
        plan_path = None
        blockers.append(f"Prehardware Day 8 timing plan validation failed: {exc}")

    with command_log_path.open("a", encoding="utf-8") as command_log:
        command_log.write(
            f"{utc_now()} check_day8_timing_calibration start "
            f"operator={args.operator} real_hardware={args.confirm_real_hardware} "
            f"safe_electrical_routing={args.confirm_safe_electrical_routing} "
            f"scope_ch_a_trigger={args.confirm_scope_ch_a_trigger} "
            f"diagnostic_channel_skew={args.diagnostic_channel_skew}\n"
        )
        if blockers:
            command_log.write(f"{utc_now()} check_day8_timing_calibration blocked before hardware\n")
        else:
            try:
                summary = workflow.run(
                    run_dir=run_dir,
                    picoscope_recipe_path=args.picoscope_recipe,
                    separations_ns=separations_ns,
                    shot_count=args.shot_count,
                    pair_ids=args.pairs,
                    reduced_set_rationale=reduced_set_rationale,
                    confirm_safe_electrical_routing=args.confirm_safe_electrical_routing,
                    article_root=args.article_root or None,
                    command_log_paths=[str(command_log_path)],
                    diagnostic_only=args.diagnostic_channel_skew,
                    include_diagnostic_pairs=args.diagnostic_channel_skew,
                )
                manifest = new_manifest(
                    operator=args.operator,
                    inventory=inventory,
                    t660_recipes={
                        "base_recipe": "recipes/timing_calibration.yaml",
                        "generated_day8_timing_recipes": True,
                        "diagnostic_channel_skew": args.diagnostic_channel_skew,
                        "separations_ns": separations_ns,
                        "pair_ids": args.pairs or "all_day8_pairs",
                    },
                    mux_routes={"route_identity_path": summary.get("route_identity_path")},
                    picoscope_settings=summary.get("picoscope_settings", {}),
                    timing_offset_file=summary.get("timing_offsets_yaml"),
                    raw_data_paths=summary["raw_data_paths"],
                    command_log_paths=[str(command_log_path)],
                    device_readback_paths=summary["device_readback_paths"],
                    blocker_status={"blocked": False, "blockers": [], "next_actions": []},
                )
                write_manifest(manifest_path, manifest)
                blocked_path = run_dir / "BLOCKED.md"
                if blocked_path.exists():
                    blocked_path.unlink()
                print(f"PASS wrote {run_dir}")
                return 0
            except Exception as exc:  # noqa: BLE001 - manifest records exact hardware blocker
                blockers.append(str(exc))

    next_actions = _next_actions(blockers)
    device_readbacks = [str(path) for path in (plan_path,) if path is not None]
    manifest = new_manifest(
        operator=args.operator,
        inventory=inventory,
        t660_recipes={
            "base_recipe": "recipes/timing_calibration.yaml",
            "planned_day8_timing_recipes": True,
            "diagnostic_channel_skew": args.diagnostic_channel_skew,
            "separations_ns": separations_ns,
            "shot_count": args.shot_count,
            "pair_ids": args.pairs or "all_day8_pairs",
        },
                    picoscope_settings={
                        "recipe_path": args.picoscope_recipe,
                        "trigger_source": "PicoScope channel A",
                        "scope_ch_a_trigger_confirmed": args.confirm_scope_ch_a_trigger,
                    },
        command_log_paths=[str(command_log_path)],
        device_readback_paths=device_readbacks,
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
        title="Day 8 Timing Calibration BLOCKED",
        blockers=blockers,
        next_actions=next_actions,
        context={
            "config_hash": inventory.config_hash,
            "run_dir": str(run_dir),
                    "picoscope_recipe": args.picoscope_recipe,
                    "article_root": args.article_root,
                    "cabling_note": args.cabling_note,
                },
    )
    print(f"BLOCKED see {run_dir / 'BLOCKED.md'}")
    return 2


def _parse_separations(value: str) -> list[int]:
    try:
        parsed = [int(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise SystemExit("--separations-ns must be a comma-separated list of integers") from exc
    if not parsed:
        raise SystemExit("--separations-ns must include at least one value")
    return parsed


def _preflight_blockers(args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    if not args.confirm_real_hardware:
        blockers.append("Real hardware acquisition was not confirmed.")
    if not args.confirm_safe_electrical_routing:
        blockers.append(
            "Safe electrical timing routing was not confirmed; laser-driving timing outputs must remain disabled."
        )
    if not args.confirm_scope_ch_a_trigger:
        blockers.append("PicoScope CH A internal trigger/cabling was not confirmed.")
    if not args.cabling_note.strip():
        blockers.append("Operator cabling note for PicoScope CH A and CH B is required.")
    if args.confirm_real_hardware and len(args.pairs or []) != 1:
        blockers.append(
            "Run exactly one --pair per physical cable setup; move the two PicoScope cables before running the next pair."
        )
    return blockers


def _next_actions(blockers: list[str]) -> list[str]:
    joined = " ".join(blockers)
    actions = [
        "Confirm direct PicoScope CH A and CH B cabling for the selected Day 8 timing pair.",
        "Confirm laser-driving timing outputs are disconnected from emitters or otherwise approved for electrical-only timing.",
        "Close any software already holding the PicoScope or T660 serial ports.",
        "Re-run this check with --confirm-real-hardware, --confirm-safe-electrical-routing, --confirm-scope-ch-a-trigger, --pair, and --cabling-note.",
    ]
    if "PICO_NOT_FOUND" in joined or "PicoSDK" in joined:
        actions.insert(2, "Verify the PicoScope 5244D is connected and the ps5000a driver is loadable.")
    if "serial" in joined.lower() or "COM" in joined:
        actions.insert(2, "Verify configured T660 COM ports are available to the active Python process.")
    return actions


if __name__ == "__main__":
    raise SystemExit(main())
