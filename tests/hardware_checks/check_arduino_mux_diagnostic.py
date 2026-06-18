#!/usr/bin/env python3
"""Run the real Arduino MUX diagnostic without using the PicoScope.

Usage:
    python tests/hardware_checks/check_arduino_mux_diagnostic.py --operator "Name" --confirm-real-hardware

This check verifies only the independent Arduino MUX device: serial identity,
firmware/protocol readback, configured MUX output route commands, route
readback, and safe idle. It does not import PicoSDK, open the PicoScope, capture
waveforms, or validate any oscilloscope input.
"""

from __future__ import annotations

from _common import REPO_ROOT, today_stamp, utc_now, write_blocked

import argparse

from control_app.config_loader import load_config_inventory
from control_app.manifest import new_manifest, write_manifest
from control_app.workflows.arduino_mux_diagnostic import ArduinoMuxDiagnostic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--confirm-real-hardware", action="store_true", required=True)
    parser.add_argument("--output-a-route")
    parser.add_argument("--output-b-route")
    parser.add_argument("--output-ext-route")
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
    run_dir = REPO_ROOT / "runs" / f"{today_stamp()}_arduino_mux_diagnostic"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_dir = REPO_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    command_log_path = log_dir / f"{today_stamp()}_arduino_mux_command_log.txt"
    manifest_path = run_dir / "run_manifest.json"
    inventory = load_config_inventory(write_files=True)
    blockers: list[str] = []

    command_protocol = inventory.devices.get("arduino_mux", {}).get("command_protocol")
    required_mux_commands = {
        "identify",
        "version",
        "protocol",
        "status",
        "query_active_route",
        "set_output_a_route",
        "set_output_b_route",
        "set_output_ext_route",
        "safe_idle",
    }
    if not isinstance(command_protocol, dict) or not required_mux_commands.issubset(
        command_protocol.keys()
    ):
        blockers.append("hardware_configuration.yaml does not define complete Arduino MUX command_protocol templates")

    output_a_route = args.output_a_route or _configured_route(inventory, "output_a_route")
    output_b_route = args.output_b_route or _configured_route(inventory, "output_b_route")
    output_ext_route = args.output_ext_route or _configured_route(inventory, "output_ext_route")
    if not output_a_route or not output_b_route or not output_ext_route:
        blockers.append("diagnostic MUX Output A, Output B, and Output EXT routes are not configured")

    if blockers:
        next_actions = []
        if any("command_protocol" in blocker for blocker in blockers):
            next_actions.append("Add documented Arduino MUX firmware command templates for Output A, Output B, and Output EXT route selection.")
        if any("diagnostic" in blocker for blocker in blockers):
            next_actions.append("Add documented mux_routes.diagnostic output_a_route, output_b_route, and output_ext_route values.")
        next_actions.append("Re-run only after hardware_configuration.yaml is updated by the operator.")
        manifest = new_manifest(
            operator=args.operator,
            inventory=inventory,
            mux_routes={},
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
            title="Arduino MUX Diagnostic BLOCKED",
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
        command_log.write(f"{utc_now()} check_arduino_mux_diagnostic start operator={args.operator}\n")
        try:
            diagnostic = ArduinoMuxDiagnostic(
                operator=args.operator,
                inventory=inventory,
                command_log=command_log,
            )
            diagnostic.run(
                output_a_route=output_a_route,
                output_b_route=output_b_route,
                output_ext_route=output_ext_route,
                run_dir=run_dir,
                command_log_paths=[str(command_log_path)],
            )
        except Exception as exc:
            errors.append(str(exc))

    if errors:
        next_actions = _hardware_next_actions(errors)
        manifest = new_manifest(
            operator=args.operator,
            inventory=inventory,
            mux_routes={
                "output_a_route": output_a_route,
                "output_b_route": output_b_route,
                "output_ext_route": output_ext_route,
            },
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
            title="Arduino MUX Diagnostic BLOCKED",
            blockers=errors,
            next_actions=next_actions,
            context={"config_hash": inventory.config_hash},
        )
        print(f"BLOCKED see {run_dir / 'BLOCKED.md'}")
        return 2

    blocked_path = run_dir / "BLOCKED.md"
    if blocked_path.exists():
        blocked_path.unlink()
    print(f"PASS wrote {run_dir}")
    return 0


def _hardware_next_actions(errors: list[str]) -> list[str]:
    joined = " ".join(errors)
    if "could not open port" in joined.lower() or "access is denied" in joined.lower():
        return [
            "Verify the Arduino MUX is connected at the configured preferred_port.",
            "Close any serial monitor or application that already has the Arduino port open.",
            "Update hardware_configuration.yaml only if Windows assigned a different COM port.",
            "Re-run the Arduino MUX diagnostic; do not use the PicoScope to unblock this check.",
        ]
    if "identity mismatch" in joined or "firmware mismatch" in joined or "protocol mismatch" in joined:
        return [
            "Flash the configured Arduino MUX firmware sketch or update hardware_configuration.yaml to the verified firmware identity/version.",
            "Re-run the Arduino MUX diagnostic after the firmware identity, version, and protocol readbacks match.",
        ]
    if "UNKNOWN_ROUTE" in joined or "ROUTE_TARGET_MISMATCH" in joined:
        return [
            "Verify mux_routes entries match the route names compiled into the Arduino MUX firmware.",
            "Update the firmware route table or hardware_configuration.yaml so route names and mux_output assignments match.",
            "Re-run the Arduino MUX diagnostic after the route table is aligned.",
        ]
    return [
        "Review the Arduino MUX command log.",
        "Verify Arduino serial access, firmware command protocol, and route table.",
        "Re-run the Arduino MUX diagnostic after the MUX-only blocker is corrected.",
    ]


if __name__ == "__main__":
    raise SystemExit(main())
