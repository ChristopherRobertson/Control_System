#!/usr/bin/env python3
"""Run real Arduino MUX and PicoScope diagnostic capture.

Usage:
    python tests/hardware_checks/check_mux_picoscope_capture.py --operator "Name" --confirm-real-hardware

The script uses only routes and Pico capture settings documented in
hardware_configuration.yaml. Missing MUX routes, missing firmware command
templates, missing Pico settings, unavailable hardware, or fewer than 100 real
captured threshold crossings are BLOCKED/FAIL conditions, never simulated passes.

This diagnostic is for MUX-selected HF2LI DIO/AUX signals. T660 TTL timing
outputs are direct routes to MIRcat, Nd:YAG, and HF2LI timing inputs, not MUX
inputs.
"""

from __future__ import annotations

from _common import REPO_ROOT, today_stamp, utc_now, write_blocked

import argparse

from control_app.config_loader import load_config_inventory
from control_app.manifest import new_manifest, write_manifest
from control_app.workflows.mux_pico_diagnostic import MuxPicoDiagnostic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--confirm-real-hardware", action="store_true", required=True)
    parser.add_argument("--ch-a-route")
    parser.add_argument("--ch-b-route")
    parser.add_argument("--ext-route")
    return parser.parse_args()


def _configured_route(inventory, key: str) -> str | None:
    diagnostics = inventory.mux_routes.get("diagnostic") if inventory.mux_routes else None
    if isinstance(diagnostics, dict):
        value = diagnostics.get(key)
        if isinstance(value, str):
            return value
    return None


def main() -> int:
    args = parse_args()
    run_dir = REPO_ROOT / "runs" / f"{today_stamp()}_mux_picoscope_diagnostic"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_dir = REPO_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    command_log_path = log_dir / f"{today_stamp()}_mux_picoscope_command_log.txt"
    manifest_path = run_dir / "run_manifest.json"
    inventory = load_config_inventory(write_files=True)
    blockers: list[str] = []

    if not inventory.mux_routes:
        blockers.append("hardware_configuration.yaml does not define MUX routes")
    command_protocol = inventory.devices.get("arduino_mux", {}).get("command_protocol")
    required_mux_commands = {
        "set_ch_a_route",
        "set_ch_b_route",
        "set_ext_route",
    }
    if not isinstance(command_protocol, dict) or not required_mux_commands.issubset(
        command_protocol.keys()
    ):
        blockers.append("hardware_configuration.yaml does not define Arduino MUX command_protocol templates")
    capture_settings = inventory.picoscope_settings.get("capture_settings")
    if not isinstance(capture_settings, dict):
        blockers.append("hardware_configuration.yaml does not define PicoScope capture settings")

    ch_a_route = args.ch_a_route or _configured_route(inventory, "ch_a_route")
    ch_b_route = args.ch_b_route or _configured_route(inventory, "ch_b_route")
    ext_route = args.ext_route or _configured_route(inventory, "ext_route")
    if not ch_a_route or not ch_b_route or not ext_route:
        blockers.append("diagnostic CH A, CH B, and EXT routes are not configured")

    if blockers:
        next_actions = []
        if any("MUX routes" in blocker or "diagnostic" in blocker for blocker in blockers):
            next_actions.append("Add documented MUX route names and diagnostic CH A/CH B/EXT routes to hardware_configuration.yaml.")
        if any("command_protocol" in blocker for blocker in blockers):
            next_actions.append("Add documented Arduino MUX firmware command templates for CH A, CH B, and EXT route selection.")
        if any("PicoScope capture settings" in blocker for blocker in blockers):
            next_actions.append("Add PicoScope resolution, CH A/B ranges/coupling, external trigger, sample count/timebase, and pulse-count threshold settings.")
        next_actions.append("Re-run only after the configuration is updated by the operator.")
        manifest = new_manifest(
            operator=args.operator,
            inventory=inventory,
            mux_routes={},
            picoscope_settings=inventory.picoscope_settings,
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
            title="MUX/Pico Diagnostic BLOCKED",
            blockers=blockers,
            next_actions=manifest["blocker_status"]["next_actions"],
            context={"config_hash": inventory.config_hash},
        )
        command_log_path.write_text(
            f"{utc_now()} BLOCKED before hardware open: {'; '.join(blockers)}\n",
            encoding="utf-8",
        )
        print(f"BLOCKED see {run_dir / 'BLOCKED.md'}")
        return 2

    errors: list[str] = []
    with command_log_path.open("a", encoding="utf-8") as command_log:
        command_log.write(f"{utc_now()} check_mux_picoscope_capture start operator={args.operator}\n")
        try:
            diagnostic = MuxPicoDiagnostic(
                operator=args.operator,
                inventory=inventory,
                command_log=command_log,
            )
            diagnostic.run(
                ch_a_route=ch_a_route,
                ch_b_route=ch_b_route,
                ext_route=ext_route,
                run_dir=run_dir,
            )
        except Exception as exc:
            errors.append(str(exc))

    if errors:
        manifest = new_manifest(
            operator=args.operator,
            inventory=inventory,
            mux_routes={
                "ch_a_route": ch_a_route,
                "ch_b_route": ch_b_route,
                "ext_route": ext_route,
            },
            picoscope_settings=inventory.picoscope_settings,
            command_log_paths=[str(command_log_path)],
            error_state={"has_error": True, "errors": errors},
            blocker_status={
                "blocked": True,
                "blockers": errors,
                "next_actions": [
                    "Verify Arduino MUX serial access and firmware protocol.",
                    "Verify PicoSDK ps5000a driver installation and PicoScope USB connection.",
                    "Verify the selected MUX route carries the expected HF2LI DIO/AUX diagnostic signal before capture.",
                ],
            },
        )
        write_manifest(manifest_path, manifest)
        write_blocked(
            run_dir / "BLOCKED.md",
            title="MUX/Pico Diagnostic BLOCKED",
            blockers=errors,
            next_actions=manifest["blocker_status"]["next_actions"],
            context={"config_hash": inventory.config_hash},
        )
        print(f"BLOCKED see {run_dir / 'BLOCKED.md'}")
        return 2
    print(f"PASS wrote {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
