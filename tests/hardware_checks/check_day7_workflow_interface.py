#!/usr/bin/env python3
"""Exercise the Day 7 add-only workflow interface.

Usage:
    python tests/hardware_checks/check_day7_workflow_interface.py --operator "Name"

By default this check validates configuration loading, recipe parsing, state
machine command construction, and pre-hardware safety gates. It does not create
device responses or acquisition data. Real hardware execution must be run from
the approved Windows hardware environment with --confirm-real-hardware.
"""

from __future__ import annotations

from _common import REPO_ROOT, today_stamp, utc_now, write_blocked, write_json

import argparse
from pathlib import Path

from control_app.config_loader import load_config_inventory
from control_app.manifest import new_manifest, write_manifest
from control_app.ui.contracts import WorkflowCommand
from control_app.workflows.state_machine import WorkflowStateMachine


DEFAULT_RECIPE = "recipes/myoglobin_co_acquisition.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", default="Codex")
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument(
        "--confirm-real-hardware",
        action="store_true",
        help="Permit the workflow to call real hardware services where implemented.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = REPO_ROOT / "runs" / f"{today_stamp()}_day7_workflow_interface"
    run_dir.mkdir(parents=True, exist_ok=True)
    command_log_path = run_dir / "command_log.txt"
    summary_path = run_dir / "workflow_summary.json"
    event_log_path = run_dir / "workflow_event_log.json"
    manifest_path = run_dir / "run_manifest.json"

    inventory = load_config_inventory(write_files=True)
    hardware_blocker = _hardware_blocker(args.confirm_real_hardware)
    results: list[dict[str, object]] = []

    with command_log_path.open("w", encoding="utf-8") as command_log:
        command_log.write(
            f"{utc_now()} check_day7_workflow_interface start "
            f"operator={args.operator} recipe={args.recipe} "
            f"confirm_real_hardware={args.confirm_real_hardware}\n"
        )
        machine = WorkflowStateMachine(
            operator=args.operator,
            inventory=inventory,
            command_log=command_log,
            hardware_access=args.confirm_real_hardware,
            hardware_blocker=hardware_blocker,
            run_dir=run_dir,
        )
        for command in _commands(args.recipe):
            result = machine(command)
            results.append(
                {
                    "device_key": command.device_key,
                    "command": command.command,
                    "parameters": command.parameters,
                    "status": result.status,
                    "message": result.message,
                    "data": result.data,
                }
            )
        machine.export_event_log(event_log_path)
        artifacts = machine.artifact_summary()

    blockers = [
        str(item["message"])
        for item in results
        if item["status"] in {"blocked", "failed"}
    ]
    failures = [
        str(item["message"])
        for item in results
        if item["status"] == "failed"
    ]
    route_result = _first_result(results, "workflow.route_scope_signal")
    arm_result = _first_result(results, "workflow.arm_measurement")

    summary = {
        "timestamp_utc": utc_now(),
        "operator": args.operator,
        "config_hash": inventory.config_hash,
        "recipe_path": str((REPO_ROOT / args.recipe).resolve()),
        "hardware_access_confirmed": args.confirm_real_hardware,
        "command_results": results,
        "blockers": blockers,
        "status": "BLOCKED" if blockers else "PASS",
    }
    write_json(summary_path, summary)

    picoscope_settings = {}
    mux_routes = {}
    if route_result:
        data = route_result.get("data")
        if isinstance(data, dict):
            picoscope_settings = data.get("picoscope_settings", {})
            mux_routes = data.get("mux_routes", {})
    mircat_setpoint = None
    hf2li_snapshot = {}
    if arm_result:
        data = arm_result.get("data")
        if isinstance(data, dict):
            mircat_setpoint = data.get("mircat_setpoint")
            hf2li_snapshot = {"preset": data.get("hf2li_preset")}
    if isinstance(artifacts, dict):
        picoscope_settings = artifacts.get("picoscope_settings") or picoscope_settings
        mux_routes = artifacts.get("mux_routes") or mux_routes
        mircat_setpoint = artifacts.get("mircat_setpoint") or mircat_setpoint
        hf2li_snapshot = artifacts.get("hf2li_settings_snapshot") or hf2li_snapshot

    manifest = new_manifest(
        operator=args.operator,
        inventory=inventory,
        t660_recipes=[DEFAULT_RECIPE, "recipes/pump_probe_single_point.yaml"],
        mux_routes=mux_routes,
        mircat_setpoint=mircat_setpoint,
        mircat_actual_wavelength=(artifacts or {}).get("mircat_actual_wavelength"),
        hf2li_settings_snapshot=hf2li_snapshot,
        picoscope_settings=picoscope_settings,
        raw_data_paths=(artifacts or {}).get("raw_data_paths", []),
        command_log_paths=list(
            dict.fromkeys([str(command_log_path), *((artifacts or {}).get("command_log_paths", []))])
        ),
        device_readback_paths=list(
            dict.fromkeys(
                [
                    str(summary_path),
                    str(event_log_path),
                    str(REPO_ROOT / args.recipe),
                    *((artifacts or {}).get("device_readback_paths", [])),
                ]
            )
        ),
        error_state={"has_error": bool(failures), "errors": failures},
        abort_state=_abort_state(results),
        blocker_status={
            "blocked": bool(blockers),
            "blockers": blockers,
            "next_actions": _next_actions(args.confirm_real_hardware) if blockers else [],
        },
    )
    write_manifest(manifest_path, manifest)

    blocked_path = run_dir / "BLOCKED.md"
    if blockers:
        write_blocked(
            blocked_path,
            title="Day 7 Workflow Interface BLOCKED",
            blockers=blockers,
            next_actions=manifest["blocker_status"]["next_actions"],
            context={
                "config_hash": inventory.config_hash,
                "recipe": args.recipe,
                "manifest": str(manifest_path),
                "command_log": str(command_log_path),
            },
        )
        print(f"BLOCKED see {blocked_path}")
        return 2

    if blocked_path.exists():
        blocked_path.unlink()
    print(f"PASS wrote {run_dir}")
    return 0


def _commands(recipe: str) -> list[WorkflowCommand]:
    return [
        WorkflowCommand(
            device_key="workflow",
            command="workflow.startup_check",
            parameters={"recipe_path": recipe},
        ),
        WorkflowCommand(device_key="workflow", command="workflow.route_scope_signal"),
        WorkflowCommand(device_key="workflow", command="workflow.program_timing_recipe"),
        WorkflowCommand(device_key="workflow", command="workflow.arm_measurement"),
        WorkflowCommand(device_key="workflow", command="workflow.acquire_point"),
        WorkflowCommand(device_key="workflow", command="workflow.acquire_scan"),
        WorkflowCommand(
            device_key="workflow",
            command="workflow.abort_to_safe",
            parameters={"reason": "Day 7 abort-path logging verification"},
        ),
        WorkflowCommand(device_key="workflow", command="workflow.safe_shutdown"),
    ]


def _first_result(results: list[dict[str, object]], command: str) -> dict[str, object] | None:
    for result in results:
        if result.get("command") == command:
            return result
    return None


def _abort_state(results: list[dict[str, object]]) -> dict[str, object]:
    result = _first_result(results, "workflow.abort_to_safe")
    if not result:
        return {"aborted": False, "reason": None}
    data = result.get("data")
    if isinstance(data, dict) and isinstance(data.get("abort_state"), dict):
        return data["abort_state"]
    return {"aborted": result.get("status") in {"blocked", "complete"}, "reason": result.get("message")}


def _hardware_blocker(confirmed: bool) -> str:
    if confirmed:
        return (
            "The Day 7 state machine reached a real-hardware command boundary that "
            "requires a device-specific approved check before data-producing acquisition."
        )
    return (
        "Real hardware execution was not enabled for this run. Re-run from native "
        "Windows Python with --confirm-real-hardware only after the T660 units, "
        "MIRcat single-client SDK session, PicoScope, Arduino MUX, HF2LI LabOne "
        "server, detector inputs, and laser-safety conditions are confirmed."
    )


def _next_actions(confirmed: bool) -> list[str]:
    actions = [
        "Keep the recorded BLOCKED status; do not create detector data or traces for Day 7 validation.",
        "Close the manufacturer MIRcat UI before any approved MIRcat hardware run because the controller is single-client.",
        "Verify T660 COM ports, Arduino MUX COM port, PicoScope USB/driver visibility, and HF2LI LabOne dev18500 before hardware execution.",
        "Confirm sample readiness, pump fluence measurement plan, beam blocks, detector protection, and laser-safety approval before arm/acquire commands.",
    ]
    if not confirmed:
        actions.append(
            "Re-run this script with native Windows Python and --confirm-real-hardware only when the safe real-hardware exercise is approved."
        )
    return actions


if __name__ == "__main__":
    raise SystemExit(main())
