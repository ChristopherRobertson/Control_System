#!/usr/bin/env python3
"""Plan or execute the complete operator-guided timing calibration.

Plan review (default; never opens hardware):
    python check_complete_timing_calibration.py --operator "Name"

Hardware execution of the previously reviewed, unchanged package (still requires
the same frozen options and exact interactive phrases at every setup):
    python check_complete_timing_calibration.py --operator "Name" --execute \
      --reviewed-plan-dir calibration/<reviewed-plan-directory> \
      --confirm-real-hardware --confirm-plan-reviewed \
      --confirm-safe-electrical-routing \
      --photodetector-response-delay-ns <value> \
      --photodetector-response-uncertainty-ns <value> \
      --photodetector-response-source <record> \
      --photodetector-identifier <id> \
      --photodetector-cable-identifier <id> \
      --photodetector-characterization-date <YYYY-MM-DD> \
      --photodetector-path-description <description> \
      --photodetector-maximum-latency-ns <value> \
      --sample-path-standard-uncertainty-ns <value> \
      --step7-load-match-method <description> \
      --step7-load-match-standard-uncertainty-ns <value> \
      --measurement-assembly-record <identifiers>

Every plan invocation creates a unique directory. Execution consumes that prior
plan directory once and refuses an existing acquisition. Existing run data is
never overwritten, and no RSI draft or shared calibration file is updated.
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
    validate_reviewed_plan_artifacts,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Open real hardware after preflight and per-step interactive confirmations. Default is plan-only.",
    )
    parser.add_argument("--confirm-real-hardware", action="store_true")
    parser.add_argument("--confirm-plan-reviewed", action="store_true")
    parser.add_argument("--confirm-safe-electrical-routing", action="store_true")
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
    try:
        separations = _parse_separations(args.separations_ns)
        if reviewed_plan_mode:
            if not args.execute:
                raise ValueError("--reviewed-plan-dir is only valid with --execute")
            if args.run_dir:
                raise ValueError("--run-dir and --reviewed-plan-dir are mutually exclusive")
            run_dir = Path(args.reviewed_plan_dir)
            if not run_dir.is_absolute():
                run_dir = REPO_ROOT / run_dir
            run_dir = run_dir.resolve()
            allowed_root = (REPO_ROOT / "calibration").resolve()
            run_dir.relative_to(allowed_root)
            if not run_dir.is_dir():
                raise ValueError(f"reviewed plan directory does not exist: {run_dir}")
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
            validate_reviewed_plan_artifacts(run_dir, requested_plan)
            status_path = run_dir / "workflow_status.json"
            if not status_path.is_file():
                raise ValueError("reviewed plan directory lacks workflow_status.json")
            status = json.loads(status_path.read_text(encoding="utf-8"))
            if status.get("hardware_opened") is not False or status.get("status") != "PLAN_ONLY_READY_FOR_REVIEW":
                raise ValueError(
                    "reviewed plan status does not prove a prior hardware_opened:false plan-only invocation"
                )
            plan_paths = {
                "json": str(run_dir / "timing_calibration_plan.json"),
                "markdown": str(run_dir / "timing_calibration_plan.md"),
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

    if not args.execute or not reviewed_plan_mode:
        write_json(
            run_dir / "workflow_status.json",
            {
                "status": "PLAN_ONLY_READY_FOR_REVIEW",
                "hardware_opened": False,
                "execution_requested_but_blocked_pending_prior_review": bool(
                    args.execute
                ),
                "rsi_drafts_updated": False,
                "canonical_calibration_updated": False,
                "plan_paths": plan_paths,
            },
        )
        print(f"PLAN ONLY wrote {plan_paths['markdown']}")
        print(f"Run directory: {run_dir}")
        if args.execute:
            print(
                "BLOCKED hardware: review this plan, then invoke --execute with --reviewed-plan-dir pointing to this directory."
            )
            return 2
        return 0

    blockers = _execution_blockers(args)
    if blockers:
        next_actions = [
            "Review timing_calibration_plan.md with the operator.",
            (
                f"Re-run with --execute --reviewed-plan-dir {run_dir} and all three --confirm-* flags after review."
                if not reviewed_plan_mode
                else "If any frozen value is incomplete or wrong, generate and review a new unique plan-only directory; never edit or reuse this plan."
            ),
            "Expect exact interactive cable/electrical-routing phrases and the Step 7 Enter-key laser-area preflight before outputs are enabled.",
        ]
        write_blocked(
            run_dir / "BLOCKED.md",
            title="Timing Calibration Hardware Execution BLOCKED",
            blockers=blockers,
            next_actions=next_actions,
            context={"run_dir": str(run_dir), "plan_paths": plan_paths},
        )
        manifest = new_manifest(
            operator=args.operator,
            inventory=inventory,
            t660_recipes={"plan": plan_paths, "optical_recipe": args.optical_recipe},
            picoscope_settings={"recipe_path": args.picoscope_recipe},
            device_readback_paths=list(plan_paths.values()),
            error_state={"has_error": True, "errors": blockers},
            blocker_status={"blocked": True, "blockers": blockers, "next_actions": next_actions},
        )
        write_manifest(run_dir / "run_manifest.json", manifest)
        write_json(
            run_dir / "workflow_status.json",
            {
                "status": "EXECUTION_BLOCKED_PREHARDWARE",
                "hardware_access_attempted": False,
                "hardware_opened": False,
                "blockers": blockers,
                "rsi_drafts_updated": False,
                "canonical_calibration_updated": False,
            },
        )
        print(f"BLOCKED see {run_dir / 'BLOCKED.md'}")
        return 2

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

    with command_log_path.open("x", encoding="utf-8") as command_log:
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
    print(f"Consolidated table: {summary['outputs']['consolidated_markdown']}")
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


def _execution_blockers(args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    if not args.reviewed_plan_dir.strip():
        blockers.append(
            "Hardware execution requires --reviewed-plan-dir pointing to a prior unchanged plan-only run; this invocation only generated a new plan for review."
        )
    if args.run_dir:
        requested = Path(args.run_dir)
        if not requested.is_absolute():
            requested = REPO_ROOT / requested
        allowed_root = (REPO_ROOT / "calibration").resolve()
        try:
            requested.resolve().relative_to(allowed_root)
        except ValueError:
            blockers.append(
                "Hardware acquisition --run-dir must be inside repository calibration/."
            )
    if not args.confirm_real_hardware:
        blockers.append("Real hardware execution was not confirmed.")
    if not args.confirm_plan_reviewed:
        blockers.append("Prehardware measurement plan review was not confirmed.")
    if not args.confirm_safe_electrical_routing:
        blockers.append("Safe electrical routing and destination-disconnect practice was not confirmed.")
    step7_values = {
        "--photodetector-response-delay-ns": args.photodetector_response_delay_ns,
        "--photodetector-response-uncertainty-ns": args.photodetector_response_uncertainty_ns,
        "--photodetector-response-source": args.photodetector_response_source.strip() or None,
        "--photodetector-identifier": args.photodetector_identifier.strip() or None,
        "--photodetector-cable-identifier": args.photodetector_cable_identifier.strip() or None,
        "--photodetector-characterization-date": args.photodetector_characterization_date.strip() or None,
        "--photodetector-maximum-latency-ns": args.photodetector_maximum_latency_ns,
        "--photodetector-path-description": args.photodetector_path_description.strip() or None,
        "--sample-path-standard-uncertainty-ns": args.sample_path_standard_uncertainty_ns,
        "--step7-load-match-method": args.step7_load_match_method.strip() or None,
        "--step7-load-match-standard-uncertainty-ns": args.step7_load_match_standard_uncertainty_ns,
        "--measurement-assembly-record": args.measurement_assembly_record.strip() or None,
    }
    missing = [flag for flag, value in step7_values.items() if value is None]
    if missing:
        blockers.append(
            "Step 7 correction values are required before hardware execution: "
            + ", ".join(missing)
        )
    for flag in (
        "--photodetector-response-delay-ns",
        "--photodetector-response-uncertainty-ns",
        "--sample-path-standard-uncertainty-ns",
        "--step7-load-match-standard-uncertainty-ns",
    ):
        value = step7_values[flag]
        if value is not None and value < 0:
            blockers.append(f"{flag} must be non-negative.")
    if args.photodetector_minimum_latency_ns < 0:
        blockers.append("--photodetector-minimum-latency-ns must be non-negative.")
    if (
        args.photodetector_maximum_latency_ns is not None
        and args.photodetector_maximum_latency_ns
        <= args.photodetector_minimum_latency_ns
    ):
        blockers.append(
            "--photodetector-maximum-latency-ns must be greater than the minimum latency."
        )
    return blockers


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
