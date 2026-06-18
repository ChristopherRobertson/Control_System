"""Workflow for independent Arduino MUX diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO
import csv
import json

from control_app.config_loader import ConfigInventory, load_config_inventory
from control_app.devices.arduino_mux_service import ArduinoMuxService
from control_app.manifest import new_manifest, write_manifest


class ArduinoMuxDiagnosticError(RuntimeError):
    """Raised when the Arduino MUX diagnostic cannot run or fails."""


class ArduinoMuxDiagnostic:
    """Verify Arduino MUX identity, output routes, readback, and safe idle."""

    def __init__(
        self,
        *,
        operator: str,
        inventory: ConfigInventory | None = None,
        config_path: str | Path | None = None,
        command_log: TextIO | None = None,
    ) -> None:
        self.operator = operator
        self.inventory = inventory or load_config_inventory(config_path, write_files=False)
        self.config_path = Path(self.inventory.config_path)
        self.command_log = command_log

    def run(
        self,
        *,
        output_a_route: str,
        output_b_route: str,
        output_ext_route: str,
        run_dir: str | Path,
        command_log_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run the real Arduino MUX diagnostic and write evidence files."""

        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        calibration_dir = Path("calibration")
        calibration_dir.mkdir(parents=True, exist_ok=True)

        requested_routes = {
            "output_a": output_a_route,
            "output_b": output_b_route,
            "output_ext": output_ext_route,
        }
        self._validate_routes(requested_routes)

        device_config = self.inventory.devices.get("arduino_mux")
        if not isinstance(device_config, dict):
            raise ArduinoMuxDiagnosticError("arduino_mux missing from hardware configuration")

        mux = ArduinoMuxService.from_config(config_path=self.config_path, command_log=self.command_log)
        route_responses: dict[str, str] = {}
        status_before: str | None = None
        status_after: str | None = None
        route_readback: dict[str, Any] | None = None
        safe_idle_response: str | None = None
        try:
            mux.connect()
            identity = mux.identify()
            firmware_version = mux.get_version()
            protocol_version = mux.get_protocol_version()
            status_before = mux.get_status()
            self._validate_identity(device_config, identity, firmware_version, protocol_version)

            route_responses["output_a"] = mux.set_output_a_route(output_a_route)
            route_responses["output_b"] = mux.set_output_b_route(output_b_route)
            route_responses["output_ext"] = mux.set_output_ext_route(output_ext_route)
            self._validate_route_responses(route_responses)
            route_readback = mux.query_active_route()
            self._validate_latched_routes(route_readback, requested_routes)
            status_after = mux.get_status()
            safe_idle_response = mux.safe_idle()
        finally:
            mux.close()

        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        summary = {
            "timestamp_utc": timestamp,
            "operator": self.operator,
            "config_hash": self.inventory.config_hash,
            "identity": identity,
            "firmware_version": firmware_version,
            "protocol_version": protocol_version,
            "status_before_routes": status_before,
            "requested_routes": requested_routes,
            "route_responses": route_responses,
            "route_readback": route_readback,
            "status_after_routes": status_after,
            "safe_idle_response": safe_idle_response,
            "status": "PASS",
        }

        status_path = calibration_dir / "arduino_mux_status.json"
        status_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        route_log = calibration_dir / "arduino_mux_route_verification.csv"
        self._append_route_verification(route_log, summary)

        manifest = new_manifest(
            operator=self.operator,
            inventory=self.inventory,
            mux_routes={
                "requested_routes": requested_routes,
                "route_responses": route_responses,
                "route_readback": route_readback or {},
            },
            command_log_paths=command_log_paths or [],
            device_readback_paths=[str(status_path), str(route_log)],
            blocker_status={"blocked": False, "blockers": [], "next_actions": []},
        )
        write_manifest(run_path / "run_manifest.json", manifest)
        return summary

    def _validate_routes(self, requested_routes: dict[str, str]) -> None:
        for mux_output, route_name in requested_routes.items():
            if not route_name:
                raise ArduinoMuxDiagnosticError(f"No route configured for {mux_output}")
            route_config = self.inventory.mux_routes.get(route_name)
            if not isinstance(route_config, dict):
                raise ArduinoMuxDiagnosticError(
                    f"MUX route {route_name!r} is not defined in hardware_configuration.yaml"
                )
            if route_config.get("mux_output") != mux_output:
                raise ArduinoMuxDiagnosticError(
                    f"MUX route {route_name!r} is configured for "
                    f"{route_config.get('mux_output')!r}, not {mux_output!r}"
                )

    def _validate_identity(
        self,
        device_config: dict[str, Any],
        identity: str | None,
        firmware_version: str | None,
        protocol_version: str | None,
    ) -> None:
        expected_identity = device_config.get("expected_identity")
        if expected_identity and identity != expected_identity:
            raise ArduinoMuxDiagnosticError(
                f"Arduino MUX identity mismatch: expected {expected_identity!r}, got {identity!r}"
            )
        expected_firmware = device_config.get("firmware_version")
        if expected_firmware and firmware_version != expected_firmware:
            raise ArduinoMuxDiagnosticError(
                "Arduino MUX firmware mismatch: "
                f"expected {expected_firmware!r}, got {firmware_version!r}"
            )
        expected_protocol = device_config.get("protocol_version")
        if expected_protocol and protocol_version != expected_protocol:
            raise ArduinoMuxDiagnosticError(
                "Arduino MUX protocol mismatch: "
                f"expected {expected_protocol!r}, got {protocol_version!r}"
            )

    def _validate_route_responses(self, responses: dict[str, str]) -> None:
        for mux_output, response in responses.items():
            if not response:
                raise ArduinoMuxDiagnosticError(f"Arduino MUX {mux_output} route command returned no response")
            if "ERROR" in response.upper():
                raise ArduinoMuxDiagnosticError(
                    f"Arduino MUX {mux_output} route command failed: {response}"
                )
            if "OK ROUTE" not in response.upper():
                raise ArduinoMuxDiagnosticError(
                    f"Arduino MUX {mux_output} route command did not confirm OK ROUTE: {response}"
                )

    def _validate_latched_routes(
        self,
        route_readback: dict[str, Any] | None,
        requested_routes: dict[str, str],
    ) -> None:
        if not isinstance(route_readback, dict):
            raise ArduinoMuxDiagnosticError("Arduino MUX route readback is missing")
        latched = route_readback.get("latched_routes")
        if not isinstance(latched, dict):
            raise ArduinoMuxDiagnosticError("Arduino MUX route readback did not include latched_routes")
        for mux_output, route_name in requested_routes.items():
            if latched.get(mux_output) != route_name:
                raise ArduinoMuxDiagnosticError(
                    f"Arduino MUX latched {mux_output}={latched.get(mux_output)!r}, "
                    f"expected {route_name!r}"
                )

    def _append_route_verification(self, route_log: Path, summary: dict[str, Any]) -> None:
        write_header = not route_log.exists()
        latched = {}
        route_readback = summary.get("route_readback")
        if isinstance(route_readback, dict) and isinstance(route_readback.get("latched_routes"), dict):
            latched = route_readback["latched_routes"]
        with route_log.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "timestamp_utc",
                    "operator",
                    "config_hash",
                    "requested_output_a_route",
                    "returned_or_echoed_output_a_route",
                    "requested_output_b_route",
                    "returned_or_echoed_output_b_route",
                    "requested_output_ext_route",
                    "returned_or_echoed_output_ext_route",
                    "verification_status",
                    "notes",
                ],
            )
            if write_header:
                writer.writeheader()
            requested = summary["requested_routes"]
            writer.writerow(
                {
                    "timestamp_utc": summary["timestamp_utc"],
                    "operator": self.operator,
                    "config_hash": self.inventory.config_hash,
                    "requested_output_a_route": requested["output_a"],
                    "returned_or_echoed_output_a_route": latched.get("output_a"),
                    "requested_output_b_route": requested["output_b"],
                    "returned_or_echoed_output_b_route": latched.get("output_b"),
                    "requested_output_ext_route": requested["output_ext"],
                    "returned_or_echoed_output_ext_route": latched.get("output_ext"),
                    "verification_status": "PASS",
                    "notes": "",
                }
            )
