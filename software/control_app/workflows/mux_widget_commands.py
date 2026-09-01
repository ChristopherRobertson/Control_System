"""Workflow command handler for the Arduino MUX desktop widget."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from control_app.config_loader import ConfigInventory, load_config_inventory
from control_app.paths import output_log_root
from control_app.devices.arduino_mux_service import (
    ArduinoMuxConfigurationError,
    ArduinoMuxError,
    ArduinoMuxService,
)
from control_app.ui.contracts import WorkflowCommand, WorkflowResult


MUX_TARGET_OUTPUTS = {
    "output_a": "output_a",
    "output_b": "output_b",
    "output_ext": "output_ext",
}
MUX_DISABLED_MESSAGE = (
    "Arduino MUX is disabled and bypassed. Use direct scope/HF2LI input wiring "
    "until the MUX is rewired and requalified."
)


def mux_enabled(inventory: ConfigInventory) -> bool:
    """Return whether the Arduino MUX is active in the loaded hardware config."""

    device = inventory.devices.get("arduino_mux")
    topology = inventory.mux_settings
    if isinstance(device, dict) and device.get("enabled") is False:
        return False
    if isinstance(topology, dict) and topology.get("enabled") is False:
        return False
    return True


def build_mux_route_options(inventory: ConfigInventory) -> dict[str, tuple[str, ...]]:
    """Return configured route names grouped by Arduino MUX output."""

    if not mux_enabled(inventory):
        return {target: () for target in MUX_TARGET_OUTPUTS}
    options: dict[str, list[str]] = {target: [] for target in MUX_TARGET_OUTPUTS}
    for route_name, route_config in inventory.mux_routes.items():
        if not isinstance(route_config, dict):
            continue
        for target, mux_output in MUX_TARGET_OUTPUTS.items():
            if route_config.get("mux_output") == mux_output:
                options[target].append(str(route_name))
    return {target: tuple(routes) for target, routes in options.items()}


def build_mux_default_routes(inventory: ConfigInventory) -> dict[str, str]:
    """Return documented diagnostic route defaults when configured."""

    if not mux_enabled(inventory):
        return {}
    diagnostic = inventory.mux_routes.get("diagnostic")
    if not isinstance(diagnostic, dict):
        return {}
    return {
        "output_a_route": str(diagnostic.get("output_a_route") or ""),
        "output_b_route": str(diagnostic.get("output_b_route") or ""),
        "output_ext_route": str(diagnostic.get("output_ext_route") or ""),
    }


def build_mux_route_labels(inventory: ConfigInventory) -> dict[str, str]:
    """Return operator-facing labels for configured MUX route names."""

    if not mux_enabled(inventory):
        return {}
    labels: dict[str, str] = {}
    for route_name, route_config in inventory.mux_routes.items():
        if not isinstance(route_config, dict):
            continue
        labels[str(route_name)] = _route_signal_label(route_config)
    return labels


class MuxWidgetCommandHandler:
    """Stateful workflow command handler used by the Arduino MUX Qt widget."""

    def __init__(
        self,
        *,
        operator: str = "UI",
        inventory: ConfigInventory | None = None,
    ) -> None:
        self.operator = operator
        self.inventory = inventory or load_config_inventory(write_files=False)
        self.config_path = Path(self.inventory.config_path)
        self.service: ArduinoMuxService | None = None
        self.connected = False

    def __call__(self, command: WorkflowCommand) -> WorkflowResult:
        """Handle one Arduino MUX widget command."""

        if command.device_key != "arduino_mux":
            return WorkflowResult(status="blocked", message=f"Unsupported device {command.device_key}")
        if not mux_enabled(self.inventory):
            return WorkflowResult(
                status="blocked",
                message=MUX_DISABLED_MESSAGE,
                data={
                    "state": {"connected": False, "disabled": True},
                    "command": command.to_dict(),
                },
            )
        log_path = self._command_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as command_log:
            command_log.write(
                f"{datetime.now().isoformat(timespec='seconds')} ui_command "
                f"{command.command} operator={self.operator}\n"
            )
            try:
                return self._handle(command, command_log)
            except Exception as exc:  # noqa: BLE001 - UI command boundary reports all failures
                return WorkflowResult(
                    status="failed",
                    message=str(exc),
                    data={"command_log": str(log_path)},
                )

    def _handle(self, command: WorkflowCommand, command_log: TextIO) -> WorkflowResult:
        service = self._service(command_log)
        name = command.command
        if name == "arduino_mux.connect":
            service.connect()
            self.connected = True
            return self._complete("Arduino MUX connected", command_log)
        if name == "arduino_mux.refresh_status":
            self._require_connected()
            return self._complete("Arduino MUX status refreshed", command_log)
        if name == "arduino_mux.apply_routes":
            self._require_connected()
            requested = {
                "output_a": str(command.parameters.get("output_a_route", "")).strip(),
                "output_b": str(command.parameters.get("output_b_route", "")).strip(),
                "output_ext": str(command.parameters.get("output_ext_route", "")).strip(),
            }
            for target, route_name in requested.items():
                self._validate_route(target, route_name)
            responses: dict[str, str] = {}
            for target, route_name in requested.items():
                if target == "output_a":
                    responses[target] = service.set_output_a_route(route_name)
                elif target == "output_b":
                    responses[target] = service.set_output_b_route(route_name)
                elif target == "output_ext":
                    responses[target] = service.set_output_ext_route(route_name)
            return self._complete(
                "Arduino MUX routes applied",
                command_log,
                extra_data={"requested_routes": requested, "route_responses": responses},
            )
        if name == "arduino_mux.safe_idle":
            self._require_connected()
            response = service.safe_idle()
            return self._complete(
                "Arduino MUX set to safe idle",
                command_log,
                extra_data={"safe_idle_response": response},
            )
        if name == "arduino_mux.disconnect":
            if self.service is not None:
                self.service.close()
            self.connected = False
            self.service = None
            return WorkflowResult(
                status="complete",
                message="Arduino MUX disconnected",
                data={
                    "state": self._read_state(),
                    "command_log": str(self._command_log_path()),
                },
            )
        return WorkflowResult(status="blocked", message=f"Unsupported command {name}")

    def _service(self, command_log: TextIO) -> ArduinoMuxService:
        if self.service is None:
            self.service = ArduinoMuxService.from_config(
                config_path=self.config_path,
                command_log=command_log,
            )
        else:
            self.service.command_log = command_log
        return self.service

    def _complete(
        self,
        message: str,
        command_log: TextIO,
        *,
        extra_data: dict[str, object] | None = None,
    ) -> WorkflowResult:
        data: dict[str, object] = {
            "state": self._read_state(),
            "command_log": str(self._command_log_path()),
        }
        if extra_data:
            data.update(extra_data)
        return WorkflowResult(status="complete", message=message, data=data)

    def _read_state(self) -> dict[str, Any]:
        state: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "connected": self.connected,
            "identity": None,
            "firmware_version": None,
            "status_response": None,
            "route_readback": None,
            "output_a_route": None,
            "output_b_route": None,
            "output_ext_route": None,
            "last_error": None,
        }
        if not self.connected or self.service is None:
            return state

        errors: list[str] = []
        identity = self._safe_value(self.service.identify, errors)
        version = self._safe_value(self.service.get_version, errors)
        status = self._safe_value(self.service.get_status, errors)
        route_readback = self._safe_value(self.service.query_active_route, errors)
        latched = route_readback.get("latched_routes", {}) if isinstance(route_readback, dict) else {}
        state.update(
            {
                "identity": identity,
                "firmware_version": version,
                "status_response": status,
                "route_readback": route_readback,
                "output_a_route": latched.get("output_a"),
                "output_b_route": latched.get("output_b"),
                "output_ext_route": latched.get("output_ext"),
                "last_error": "; ".join(errors) if errors else None,
            }
        )
        return state

    def _safe_value(self, callback, errors: list[str]) -> Any:
        try:
            return callback()
        except Exception as exc:  # noqa: BLE001 - readback failures should not drop the connection
            errors.append(str(exc))
            return None

    def _validate_route(self, target: str, route_name: str) -> None:
        if not route_name:
            raise ArduinoMuxConfigurationError(f"No route selected for {target}")
        route_config = self.inventory.mux_routes.get(route_name)
        if not isinstance(route_config, dict):
            raise ArduinoMuxConfigurationError(
                f"MUX route {route_name!r} is not defined in hardware_configuration.yaml"
            )
        expected_output = MUX_TARGET_OUTPUTS[target]
        if route_config.get("mux_output") != expected_output:
            raise ArduinoMuxConfigurationError(
                f"MUX route {route_name!r} is configured for "
                f"{route_config.get('mux_output')!r}, not {expected_output!r}"
            )

    def _require_connected(self) -> None:
        if not self.connected or self.service is None:
            raise ArduinoMuxError("Arduino MUX is not connected. Connect before routing signals.")

    def _command_log_path(self) -> Path:
        return output_log_root() / f"{datetime.now().strftime('%Y%m%d')}_mux_ui_command_log.txt"


def _route_signal_label(route_config: dict[str, Any]) -> str:
    source_device = str(route_config.get("source_device") or "").upper()
    source_signal = str(route_config.get("source_signal") or "")
    if source_device and source_signal:
        return f"{source_device} {source_signal}"
    return source_signal or "Configured signal"
