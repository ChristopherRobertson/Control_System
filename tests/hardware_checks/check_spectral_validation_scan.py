#!/usr/bin/env python3
"""Run one workflow-backed RSI spectral-validation scan.

Usage:
    python tests/hardware_checks/check_spectral_validation_scan.py \
        --operator "Name" --recipe recipes/polystyrene_validation.yaml

Without --confirm-real-hardware this check validates workflow construction and
writes BLOCKED.md rather than creating detector data. Real hardware acquisition
must be run from native Windows Python with the MIRcat manufacturer UI closed.
"""

from __future__ import annotations

from _common import REPO_ROOT, today_stamp, utc_now, write_blocked, write_json

import argparse
from pathlib import Path

import yaml

from control_app.config_loader import load_config_inventory
from control_app.manifest import new_manifest, write_manifest
from control_app.ui.contracts import WorkflowCommand
from control_app.workflows.state_machine import WorkflowStateMachine


DEFAULT_RECIPE = "recipes/myoglobin_co_validation.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", default="Codex")
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument(
        "--confirm-real-hardware",
        action="store_true",
        help="Permit real hardware service calls and data-producing acquisition.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    recipe_path = _resolve_recipe(args.recipe)
    recipe = _load_recipe(recipe_path)
    recipe_name = str(recipe.get("name") or recipe_path.stem)
    run_dir = REPO_ROOT / "calibration" / f"{today_stamp()}_{recipe_name}"
    run_dir.mkdir(parents=True, exist_ok=True)
    command_log_path = run_dir / "command_log.txt"
    summary_path = run_dir / "spectral_validation_summary.json"
    event_log_path = run_dir / "workflow_event_log.json"
    manifest_path = run_dir / "run_manifest.json"

    inventory = load_config_inventory(write_files=True)
    hardware_blocker = _hardware_blocker(args.confirm_real_hardware)
    results: list[dict[str, object]] = []

    with command_log_path.open("w", encoding="utf-8") as command_log:
        command_log.write(
            f"{utc_now()} check_spectral_validation_scan start "
            f"operator={args.operator} recipe={recipe_path} "
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
        for command in _commands(str(recipe_path)):
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
    summary = {
        "timestamp_utc": utc_now(),
        "operator": args.operator,
        "recipe_path": str(recipe_path),
        "hardware_access_confirmed": args.confirm_real_hardware,
        "command_results": results,
        "blockers": blockers,
        "status": "BLOCKED" if blockers else "PASS",
    }
    write_json(summary_path, summary)

    manifest = new_manifest(
        operator=args.operator,
        inventory=inventory,
        t660_recipes=[str(recipe_path), str(REPO_ROOT / str(recipe.get("timing_recipe")))],
        mux_routes=(artifacts or {}).get("mux_routes", {}),
        mircat_setpoint=(artifacts or {}).get("mircat_setpoint"),
        mircat_actual_wavelength=(artifacts or {}).get("mircat_actual_wavelength"),
        hf2li_settings_snapshot=(artifacts or {}).get("hf2li_settings_snapshot", {}),
        picoscope_settings=(artifacts or {}).get("picoscope_settings", {}),
        raw_data_paths=(artifacts or {}).get("raw_data_paths", []),
        command_log_paths=list(
            dict.fromkeys([str(command_log_path), *((artifacts or {}).get("command_log_paths", []))])
        ),
        device_readback_paths=list(
            dict.fromkeys(
                [
                    str(summary_path),
                    str(event_log_path),
                    str(recipe_path),
                    *((artifacts or {}).get("device_readback_paths", [])),
                ]
            )
        ),
        error_state={"has_error": bool(failures), "errors": failures},
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
            title=f"{recipe_name} Spectral Validation BLOCKED",
            blockers=blockers,
            next_actions=manifest["blocker_status"]["next_actions"],
            context={
                "recipe": str(recipe_path),
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


def _resolve_recipe(recipe: str) -> Path:
    path = Path(recipe)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"recipe not found: {path}")
    return path


def _load_recipe(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"recipe must be a mapping: {path}")
    return data


def _commands(recipe: str) -> list[WorkflowCommand]:
    return [
        WorkflowCommand(
            device_key="workflow",
            command="workflow.startup_check",
            parameters={"recipe_path": recipe},
        ),
        WorkflowCommand(device_key="workflow", command="workflow.route_scope_signal"),
        WorkflowCommand(device_key="workflow", command="workflow.arm_measurement"),
        WorkflowCommand(device_key="workflow", command="workflow.program_timing_recipe"),
        WorkflowCommand(device_key="workflow", command="workflow.acquire_scan"),
        WorkflowCommand(device_key="workflow", command="workflow.safe_shutdown"),
    ]


def _hardware_blocker(confirmed: bool) -> str:
    if confirmed:
        return (
            "The workflow reached a real-hardware command boundary that requires "
            "the device-specific service to complete successfully."
        )
    return (
        "Real hardware execution was not enabled. Re-run from native Windows "
        "Python with --confirm-real-hardware only after the T660 units, MIRcat "
        "single-client SDK session, PicoScope, HF2LI LabOne server, "
        "detector inputs, sample, FTIR metadata, and laser-safety conditions are confirmed."
    )


def _next_actions(confirmed: bool) -> list[str]:
    actions = [
        "Keep the recorded BLOCKED status; do not create detector data or traces for article claims.",
        "Close the manufacturer MIRcat UI because the controller is single-client.",
        "Verify T660 COM ports, direct scope/HF2LI wiring, PicoScope USB/driver visibility, and HF2LI LabOne dev18500.",
        "Confirm sample identity, FTIR metadata, detector protection, beam blocks, and approved laser-safety conditions.",
    ]
    if not confirmed:
        actions.append("Re-run with --confirm-real-hardware only when the real acquisition is approved.")
    return actions


if __name__ == "__main__":
    raise SystemExit(main())
