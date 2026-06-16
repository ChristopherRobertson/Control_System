"""Serial service for a real Arduino-controlled MUX."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO
import time

from control_app.config_loader import load_hardware_config


class ArduinoMuxError(RuntimeError):
    """Base error for Arduino MUX service failures."""


class ArduinoMuxConfigurationError(ArduinoMuxError):
    """Raised when hardware configuration lacks required MUX details."""


class ArduinoMuxService:
    """Real serial wrapper for a configured Arduino MUX controller."""

    def __init__(
        self,
        device_config: dict[str, Any],
        routes: dict[str, Any],
        *,
        timeout_s: float = 1.0,
        command_log: TextIO | None = None,
    ) -> None:
        self.device_config = device_config
        self.routes = routes
        self.timeout_s = timeout_s
        self.command_log = command_log
        self._serial = None
        self._latched_routes: dict[str, str] = {}

    @classmethod
    def from_config(
        cls,
        *,
        config_path: str | Path | None = None,
        command_log: TextIO | None = None,
        timeout_s: float = 1.0,
    ) -> "ArduinoMuxService":
        """Create a service from hardware_configuration.yaml."""

        config, _, _ = load_hardware_config(config_path)
        devices = config.get("devices") or {}
        device_config = devices.get("arduino_mux")
        if not isinstance(device_config, dict):
            raise ArduinoMuxConfigurationError("arduino_mux missing from hardware configuration")
        routes = (
            config.get("mux_routes")
            or config.get("routes", {}).get("mux")
            or device_config.get("routes", {})
        )
        if not isinstance(routes, dict):
            routes = {}
        return cls(device_config, routes, timeout_s=timeout_s, command_log=command_log)

    def connect(self) -> None:
        """Open the configured real serial port."""

        port = self.device_config.get("preferred_port") or self.device_config.get("port")
        baudrate = self.device_config.get("baudrate")
        if not port or not baudrate:
            raise ArduinoMuxConfigurationError("Arduino MUX serial port/baudrate missing")
        try:
            import serial
        except ImportError as exc:
            raise ArduinoMuxConfigurationError("pyserial is required for Arduino MUX control") from exc
        self._serial = serial.Serial(
            port=str(port),
            baudrate=int(baudrate),
            timeout=self.timeout_s,
            write_timeout=self.timeout_s,
        )
        time.sleep(2.0)

    def identify(self) -> str | None:
        """Query controller identity if the firmware command is configured."""

        command = self._protocol().get("identify")
        if not command:
            return None
        return self._command(command)

    def get_version(self) -> str | None:
        """Query firmware version if the firmware command is configured."""

        command = self._protocol().get("version")
        if not command:
            return None
        return self._command(command)

    def set_ch_a_route(self, route_name: str) -> str:
        """Set PicoScope CH A to a documented MUX route."""

        return self._set_route("ch_a", route_name)

    def set_ch_b_route(self, route_name: str) -> str:
        """Set PicoScope CH B to a documented MUX route."""

        return self._set_route("ch_b", route_name)

    def set_ext_route(self, route_name: str) -> str:
        """Set PicoScope EXT trigger to a documented MUX route."""

        return self._set_route("ext", route_name)

    def query_active_route(self) -> dict[str, Any]:
        """Return hardware route readback or the last latched command state."""

        query = self._protocol().get("query_active_route")
        if query:
            return {
                "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "response": self._command(query),
                "latched_routes": dict(self._latched_routes),
            }
        return {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "response": None,
            "latched_routes": dict(self._latched_routes),
            "notes": "Firmware route query is not configured; latched_routes records commands sent successfully.",
        }

    def close(self) -> None:
        """Close the serial port."""

        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def _set_route(self, target: str, route_name: str) -> str:
        if route_name not in self.routes:
            raise ArduinoMuxConfigurationError(
                f"MUX route {route_name!r} is not defined in hardware_configuration.yaml"
            )
        command_key = f"set_{target}_route"
        template = self._protocol().get(command_key)
        if not template:
            raise ArduinoMuxConfigurationError(
                f"Arduino MUX command template {command_key!r} is missing from hardware_configuration.yaml"
            )
        response = self._command(str(template).format(route=route_name))
        self._latched_routes[target] = route_name
        return response

    def _protocol(self) -> dict[str, Any]:
        protocol = self.device_config.get("command_protocol") or {}
        if not isinstance(protocol, dict):
            raise ArduinoMuxConfigurationError("arduino_mux command_protocol must be a mapping")
        return protocol

    def _command(self, command: str) -> str:
        if self._serial is None:
            raise ArduinoMuxError("Arduino MUX is not connected")
        self._serial.reset_input_buffer()
        self._serial.write((command + "\n").encode("ascii"))
        self._serial.flush()
        deadline = time.time() + self.timeout_s
        lines: list[str] = []
        while time.time() < deadline:
            line = self._serial.readline()
            if not line:
                break
            text = line.decode("ascii", errors="replace").strip()
            if text:
                lines.append(text)
        response = "\n".join(lines)
        self._log(command, response)
        return response

    def _log(self, command: str, response: str) -> None:
        if self.command_log is None:
            return
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        self.command_log.write(f"{timestamp} arduino_mux << {command}\n")
        if response:
            for line in response.splitlines():
                self.command_log.write(f"{timestamp} arduino_mux >> {line}\n")
        self.command_log.flush()

