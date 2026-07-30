#!/usr/bin/env python3
"""Legacy/internal complete timing implementation.

This module remains for regression coverage and reusable implementation code.
It is not the operator-facing calibration workflow. Active campaigns are
orchestrated by Codex one phase and one operator action at a time.
"""

from __future__ import annotations

from _common import REPO_ROOT, utc_now, write_blocked, write_json

import argparse
import json
from pathlib import Path

from control_app.config_loader import load_config_inventory
from control_app.manifest import new_manifest, write_manifest
from control_app.workflows.timing_trace_analysis import (
    DEFAULT_SEPARATIONS_NS,
    DEFAULT_SHOT_COUNT,
)
from control_app.workflows.timing_calibration_procedure import (
    DEFAULT_OPTICAL_RECIPE,
    SafeIdleVerificationError,
    TimingCalibrationProcedure,
    create_unique_run_directory,
    load_execution_plan,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Open real hardware after preflight and per-step interactive confirmations. Default is plan-only.",
    )
    parser.add_argument(
        "--execution-scope",
        choices=("MS-01", "COMPLETE"),
        default="MS-01",
        help="Hardware execution boundary. Defaults to MS-01 and stops after the normal and swapped splitter captures.",
    )
    parser.add_argument(
        "--picoscope-recipe",
        default="recipes/picoscope_settings_test.yaml",
        help="Base two-channel PicoScope capture settings.",
    )
    parser.add_argument(
        "--optical-recipe",
        default=DEFAULT_OPTICAL_RECIPE,
        help="Approved 10 Hz FIRE/Q-switch recipe used only in Step 7.",
    )
    parser.add_argument(
        "--shot-count",
        type=int,
        default=DEFAULT_SHOT_COUNT,
        help="Repeated shots per delay/setup (default 100).",
    )
    parser.add_argument(
        "--reduced-set-rationale",
        default="",
        help="Required when --shot-count is not the complete default of 100.",
    )
    parser.add_argument(
        "--separations-ns",
        default=",".join(str(value) for value in DEFAULT_SEPARATIONS_NS),
        help="Must remain the complete six-point sweep: 0,100,1000,10000,100000,1000000.",
    )
    parser.add_argument(
        "--photodetector-edge",
        choices=("rising", "falling"),
        default="rising",
        help="Observed photodetector pulse edge for Step 7.",
    )
    parser.add_argument(
        "--photodetector-threshold-adc",
        type=int,
        default=5000,
        help="Signed PicoScope ADC threshold for the Step 7 photodetector edge.",
    )
    parser.add_argument(
        "--photodetector-minimum-latency-ns",
        type=float,
        default=5.0,
        help="Minimum Q-switch-to-detector latency accepted as optical rather than coincident EMI.",
    )
    parser.add_argument(
        "--photodetector-maximum-latency-ns",
        type=float,
        default=None,
        help="Reviewed upper Q-switch-to-OPO latency bound; edges outside this window are rejected.",
    )
    parser.add_argument(
        "--photodetector-response-delay-ns",
        type=float,
        default=None,
        help="Known detector plus upstream detector-cable response delay to subtract, in ns.",
    )
    parser.add_argument(
        "--photodetector-response-uncertainty-ns",
        type=float,
        default=None,
        help="Standard uncertainty of the detector response-delay correction, in ns.",
    )
    parser.add_argument("--photodetector-response-source", default="")
    parser.add_argument("--photodetector-identifier", default="")
    parser.add_argument("--photodetector-cable-identifier", default="")
    parser.add_argument("--photodetector-characterization-date", default="")
    parser.add_argument(
        "--photodetector-path-description",
        default="",
        help="Sample-position or sample-equivalent placement and optical path-length record.",
    )
    parser.add_argument(
        "--sample-path-standard-uncertainty-ns",
        type=float,
        default=None,
        help="Standard uncertainty from detector placement/path-length equivalence.",
    )
    parser.add_argument(
        "--step7-load-match-method",
        default="",
        help="How MS-00C reproduces the actual Nd:YAG Q-switch input load while probing.",
    )
    parser.add_argument(
        "--step7-load-match-standard-uncertainty-ns",
        type=float,
        default=None,
        help="Standard uncertainty assigned to Step 0c load equivalence.",
    )
    parser.add_argument(
        "--measurement-assembly-record",
        default="",
        help="Identifiers for splitter, E_A, E_B, final Q-switch cable, and Step 7 monitor lead.",
    )
    parser.add_argument(
        "--run-dir",
        default="",
        help="Optional new path. It must not already exist. Default is a timestamp+UUID directory under calibration/.",
    )
    parser.add_argument(
        "--reviewed-plan-dir",
        default="",
        help="Existing plan-only directory under calibration/ to execute. Required with --execute; it is never rewritten.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    reviewed_plan_mode = bool(args.reviewed_plan_dir.strip())
    reviewed_plan_dir: Path | None = None
    try:
        separations = _parse_separations(args.separations_ns)
        if reviewed_plan_mode:
            if not args.execute:
                raise ValueError("--reviewed-plan-dir is only valid with --execute")
            reviewed_plan_dir = Path(args.reviewed_plan_dir)
            if not reviewed_plan_dir.is_absolute():
                reviewed_plan_dir = REPO_ROOT / reviewed_plan_dir
            reviewed_plan_dir = reviewed_plan_dir.resolve()
            allowed_root = (REPO_ROOT / "calibration").resolve()
            reviewed_plan_dir.relative_to(allowed_root)
            if not reviewed_plan_dir.is_dir():
                raise ValueError(
                    f"reviewed plan directory does not exist: {reviewed_plan_dir}"
                )
            if args.run_dir:
                run_dir = Path(args.run_dir)
                if not run_dir.is_absolute():
                    run_dir = REPO_ROOT / run_dir
                run_dir = run_dir.resolve()
            else:
                campaign_dir = reviewed_plan_dir.parent.parent
                run_dir = campaign_dir / "readbacks" / args.execution_scope
            run_dir.mkdir(parents=True, exist_ok=True)
        else:
            run_dir = create_unique_run_directory(
                requested_path=args.run_dir or None,
            )
    except Exception as exc:  # noqa: BLE001 - CLI reports an exact prehardware failure
        print(f"ERROR {exc}")
        return 2

    inventory = load_config_inventory(write_files=False)
    plan_workflow = TimingCalibrationProcedure(operator=args.operator, inventory=inventory)
    plan_kwargs = _plan_kwargs(args, separations)
    try:
        if reviewed_plan_mode:
            requested_plan = plan_workflow.build_plan(**plan_kwargs)
            load_execution_plan(reviewed_plan_dir, requested_plan)
            plan_paths = {
                "json": str(reviewed_plan_dir / "timing_calibration_plan.json"),
                "markdown": str(reviewed_plan_dir / "timing_calibration_plan.md"),
            }
        else:
            plan_paths = plan_workflow.write_plan(run_dir, **plan_kwargs)
    except Exception as exc:  # noqa: BLE001 - no hardware has opened
        if not reviewed_plan_mode:
            write_json(
                run_dir / "workflow_status.json",
                {"status": "PLAN_VALIDATION_FAILED", "error": str(exc), "hardware_opened": False},
            )
        print(f"ERROR plan validation failed: {exc}")
        return 2

    if not args.execute:
        write_json(
            run_dir / "workflow_status.json",
            {
                "status": "PLAN_ONLY_READY_FOR_REVIEW",
                "hardware_opened": False,
                "rsi_drafts_updated": False,
                "canonical_calibration_updated": False,
                "plan_paths": plan_paths,
            },
        )
        print(f"PLAN ONLY wrote {plan_paths['markdown']}")
        print(f"Run directory: {run_dir}")
        return 0

    command_log_path = run_dir / "command_log.txt"
    summary: dict | None = None
    errors: list[str] = []
    unsafe_state_unverified = False
    interrupted = False
    hardware_status: dict = {
        "status": "EXECUTION_STARTING",
        "hardware_access_attempted": False,
        "hardware_opened": False,
        "rsi_drafts_updated": False,
        "canonical_calibration_updated": False,
    }
    write_json(run_dir / "workflow_status.json", hardware_status)

    def record_hardware_state(state: str) -> None:
        if state == "OPEN_ATTEMPT":
            hardware_status["status"] = "HARDWARE_OPEN_ATTEMPT"
            hardware_status["hardware_access_attempted"] = True
            hardware_status["hardware_opened"] = None
        elif state == "OPENED":
            hardware_status["status"] = "HARDWARE_EXECUTION_IN_PROGRESS"
            hardware_status["hardware_access_attempted"] = True
            hardware_status["hardware_opened"] = True
        else:
            raise ValueError(f"unknown hardware state {state!r}")
        write_json(run_dir / "workflow_status.json", hardware_status)

    with command_log_path.open("a", encoding="utf-8") as command_log:
        command_log.write(
            f"{utc_now()} complete timing calibration start operator={args.operator} "
            f"run_dir={run_dir}\n"
        )
        workflow = TimingCalibrationProcedure(
            operator=args.operator,
            inventory=inventory,
            command_log=command_log,
        )
        try:
            summary = workflow.run(
                run_dir=run_dir,
                plan_dir=reviewed_plan_dir,
                execution_scope=args.execution_scope,
                picoscope_recipe_path=args.picoscope_recipe,
                optical_recipe_path=args.optical_recipe,
                separations_ns=separations,
                shot_count=args.shot_count,
                reduced_set_rationale=args.reduced_set_rationale.strip() or None,
                photodetector_edge=args.photodetector_edge,
                photodetector_threshold_adc=args.photodetector_threshold_adc,
                photodetector_minimum_latency_ns=args.photodetector_minimum_latency_ns,
                photodetector_maximum_latency_ns=args.photodetector_maximum_latency_ns,
                photodetector_response_delay_ns=args.photodetector_response_delay_ns,
                photodetector_response_uncertainty_ns=args.photodetector_response_uncertainty_ns,
                photodetector_response_source=args.photodetector_response_source.strip() or None,
                photodetector_identifier=args.photodetector_identifier.strip() or None,
                photodetector_cable_identifier=args.photodetector_cable_identifier.strip() or None,
                photodetector_characterization_date=args.photodetector_characterization_date.strip() or None,
                photodetector_path_description=args.photodetector_path_description.strip() or None,
                sample_path_standard_uncertainty_ns=args.sample_path_standard_uncertainty_ns,
                step7_load_match_method=args.step7_load_match_method.strip() or None,
                step7_load_match_standard_uncertainty_ns=args.step7_load_match_standard_uncertainty_ns,
                measurement_assembly_record=args.measurement_assembly_record.strip() or None,
                hardware_state_callback=record_hardware_state,
            )
        except BaseException as exc:  # noqa: BLE001 - interrupts still require final status/manifest
            error_text = str(exc).strip() or type(exc).__name__
            errors.append(error_text)
            unsafe_state_unverified = isinstance(exc, SafeIdleVerificationError)
            interrupted = _exception_chain_contains_interrupt(exc)
            command_log.write(f"{utc_now()} timing calibration stopped: {error_text}\n")

    blocked = bool(errors)
    if summary is None:
        partial_raw = sorted(
            str(path)
            for path in (run_dir / "raw_pico_traces").rglob("*.csv")
        ) if (run_dir / "raw_pico_traces").exists() else []
        partial_readbacks = sorted(
            str(path)
            for path in (run_dir / "timing_readbacks").rglob("*.json")
        ) if (run_dir / "timing_readbacks").exists() else []
        summary = {
            "raw_data_paths": partial_raw,
            "device_readback_paths": partial_readbacks,
            "outputs": {},
            "capture_profiles": {},
        }
    manifest = new_manifest(
        operator=args.operator,
        inventory=inventory,
        t660_recipes={
            "generated_electrical_recipes": True,
            "optical_recipe": args.optical_recipe,
            "plan": plan_paths,
            "separations_ns": separations,
            "shot_count": args.shot_count,
            "reduced_set_rationale": args.reduced_set_rationale.strip() or None,
            "execution_scope": args.execution_scope,
        },
        picoscope_settings={
            "recipe_path": args.picoscope_recipe,
            "capture_profiles": summary.get("capture_profiles", {}),
            "trigger_source": "PicoScope CHA",
        },
        timing_offset_file=(summary.get("outputs") or {}).get("derived_recipe_corrections_yaml"),
        raw_data_paths=summary.get("raw_data_paths", []),
        command_log_paths=[str(command_log_path)],
        device_readback_paths=summary.get("device_readback_paths", []) + list(plan_paths.values()),
        error_state={"has_error": blocked, "errors": errors},
        abort_state={"aborted": blocked, "reason": errors[0] if errors else None},
        blocker_status={
            "blocked": blocked,
            "blockers": errors,
            "next_actions": (
                [
                    "Treat the output state as UNKNOWN: do not touch cabling or enter the beam area.",
                    "Use the approved emergency/manual T660 STOP and laser shutdown procedure, then visually/electrically verify every output is off.",
                    "Record the manual recovery separately; do not change this run's unsafe-state status.",
                ]
                if unsafe_state_unverified
                else [
                    "Keep the verified safe-idle state and inspect command_log.txt plus partial readbacks.",
                    "Correct the stated setup or trace issue, then start a new unique run; do not reuse this directory.",
                ]
            )
            if blocked
            else [],
        },
    )
    write_manifest(run_dir / "run_manifest.json", manifest)
    final_hardware_status = {
        **hardware_status,
        "status": (
            "BLOCKED_UNSAFE_STATE_UNVERIFIED"
            if unsafe_state_unverified
            else ("BLOCKED" if blocked else "PASS")
        ),
        "errors": errors,
        "unsafe_state_unverified": unsafe_state_unverified,
        "interrupted": interrupted,
        "execution_scope": args.execution_scope,
        "rsi_drafts_updated": False,
        "canonical_calibration_updated": False,
    }
    write_json(run_dir / "workflow_status.json", final_hardware_status)
    if blocked:
        write_blocked(
            run_dir / "BLOCKED.md",
            title=(
                "UNSAFE STATE UNVERIFIED — MANUAL INTERVENTION REQUIRED"
                if unsafe_state_unverified
                else "Timing Calibration Stopped in Verified Safe Idle"
            ),
            blockers=errors,
            next_actions=manifest["blocker_status"]["next_actions"],
            context={
                "run_dir": str(run_dir),
                "partial_data_preserved": True,
                "unsafe_state_unverified": unsafe_state_unverified,
            },
        )
        print(f"BLOCKED see {run_dir / 'BLOCKED.md'}")
        return 130 if interrupted else 2
    print(f"PASS wrote {run_dir}")
    primary_report = (
        summary["outputs"].get("consolidated_markdown")
        or summary["outputs"].get("best_effort_final_report_markdown")
    )
    print(f"Final report: {primary_report}")
    return 0


def _plan_kwargs(args: argparse.Namespace, separations: list[int]) -> dict:
    return {
        "separations_ns": separations,
        "shot_count": args.shot_count,
        "reduced_set_rationale": args.reduced_set_rationale.strip() or None,
        "picoscope_recipe_path": args.picoscope_recipe,
        "optical_recipe_path": args.optical_recipe,
        "photodetector_edge": args.photodetector_edge,
        "photodetector_threshold_adc": args.photodetector_threshold_adc,
        "photodetector_minimum_latency_ns": args.photodetector_minimum_latency_ns,
        "photodetector_maximum_latency_ns": args.photodetector_maximum_latency_ns,
        "photodetector_response_delay_ns": args.photodetector_response_delay_ns,
        "photodetector_response_uncertainty_ns": args.photodetector_response_uncertainty_ns,
        "photodetector_response_source": args.photodetector_response_source.strip() or None,
        "photodetector_identifier": args.photodetector_identifier.strip() or None,
        "photodetector_cable_identifier": args.photodetector_cable_identifier.strip() or None,
        "photodetector_characterization_date": args.photodetector_characterization_date.strip() or None,
        "photodetector_path_description": args.photodetector_path_description.strip() or None,
        "sample_path_standard_uncertainty_ns": args.sample_path_standard_uncertainty_ns,
        "step7_load_match_method": args.step7_load_match_method.strip() or None,
        "step7_load_match_standard_uncertainty_ns": args.step7_load_match_standard_uncertainty_ns,
        "measurement_assembly_record": args.measurement_assembly_record.strip() or None,
    }


def _parse_separations(value: str) -> list[int]:
    try:
        parsed = [int(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise ValueError("--separations-ns must be comma-separated integers") from exc
    if parsed != list(DEFAULT_SEPARATIONS_NS):
        raise ValueError(
            "complete procedure requires --separations-ns 0,100,1000,10000,100000,1000000"
        )
    return parsed


def _exception_chain_contains_interrupt(exc: BaseException) -> bool:
    """Return true when an interrupt was wrapped during safe finalization."""

    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (KeyboardInterrupt, SystemExit)):
            return True
        current = current.__cause__ or current.__context__
    return False


if __name__ == "__main__":
    raise SystemExit(main())
