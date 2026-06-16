"""Service adapter for real Highland Technologies T660 delay generators."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO
import socket
import time

from control_app.config_loader import load_hardware_config


CHANNEL_EDGES = {
    "A": (1, 2),
    "B": (3, 4),
    "C": (5, 6),
    "D": (7, 8),
}


class T660Error(RuntimeError):
    """Base error for T660 service failures."""


class T660ConfigurationError(T660Error):
    """Raised when required T660 configuration is missing."""


class T660CommandError(T660Error):
    """Raised when a T660 command reports an error."""


class T660Service:
    """Real hardware command session for a configured T660 unit."""

    def __init__(
        self,
        name: str,
        device_config: dict[str, Any],
        *,
        timeout_s: float = 0.5,
        command_log: TextIO | None = None,
    ) -> None:
        self.name = name
        self.device_config = device_config
        self.timeout_s = timeout_s
        self.command_log = command_log
        self._serial = None
        self._socket: socket.socket | None = None

    @classmethod
    def from_config(
        cls,
        name: str,
        *,
        config_path: str | Path | None = None,
        command_log: TextIO | None = None,
        timeout_s: float = 0.5,
    ) -> "T660Service":
        """Create a service for a T660 device in hardware_configuration.yaml."""

        config, _, _ = load_hardware_config(config_path)
        devices = config.get("devices") or {}
        device_config = devices.get(name)
        if not isinstance(device_config, dict):
            raise T660ConfigurationError(f"{name} not found in hardware configuration")
        return cls(name, device_config, timeout_s=timeout_s, command_log=command_log)

    def connect(self) -> None:
        """Open the configured serial or TCP command session."""

        interface = self.device_config.get("interface")
        if interface is None:
            interface = "tcp" if self.device_config.get("host") else "serial"

        if interface == "serial":
            port = self.device_config.get("preferred_port") or self.device_config.get("port")
            baudrate = self.device_config.get("baudrate")
            if not port or not baudrate:
                raise T660ConfigurationError(f"{self.name} serial port/baudrate missing")
            try:
                import serial
            except ImportError as exc:
                raise T660ConfigurationError("pyserial is required for T660 serial control") from exc
            self._serial = serial.Serial(
                port=str(port),
                baudrate=int(baudrate),
                timeout=self.timeout_s,
                write_timeout=self.timeout_s,
            )
        elif interface == "tcp":
            host = self.device_config.get("host")
            port = self.device_config.get("tcp_port") or self.device_config.get("port")
            if not host or not port:
                raise T660ConfigurationError(f"{self.name} TCP host/port missing")
            self._socket = socket.create_connection((str(host), int(port)), timeout=self.timeout_s)
            self._socket.settimeout(self.timeout_s)
        else:
            raise T660ConfigurationError(f"{self.name} unsupported interface {interface!r}")

        self._set_p500_session()

    def identify(self) -> str:
        """Return the T660 identity string."""

        return self.command("*IDN?")

    def get_firmware_version(self) -> str:
        """Return the firmware string if the unit reports it."""

        identity = self.command("*IDN?")
        parts = [part.strip() for part in identity.split(",")]
        if len(parts) >= 4 and parts[3]:
            return parts[3]
        return self.command("IDentify")

    def force_eod(self) -> str:
        """Force an end-of-delay event."""

        return self.command("FEOD")

    def set_clock_mode(
        self,
        mode: str | None = None,
        *,
        frequency: str | float | int | None = None,
        shots: int | None = None,
    ) -> None:
        """Configure documented trigger synthesizer frequency and shot count."""

        if frequency is not None:
            self.command(f"TRIG:FREQ:SYN {frequency}", expect_response=False)
        if shots is not None:
            self.command(f"TRIG:SHOTS {int(shots)}", expect_response=False)
        if mode is not None:
            normalized = str(mode).upper()
            if normalized not in {"OFF", "SYN", "EXT", "INT"}:
                raise T660ConfigurationError(f"unsupported T660 trigger mode {mode!r}")
            self.set_trigger_source(normalized)

    def set_trigger_source(self, source: str) -> None:
        """Set the T660 trigger source to OFF, SYN, EXT, or INT."""

        normalized = str(source).upper()
        if normalized not in {"OFF", "SYN", "EXT", "INT"}:
            raise T660ConfigurationError(f"unsupported T660 trigger source {source!r}")
        self.command(f"TRIG:SOUR {normalized}", expect_response=False)

    def set_channel_delay_width(self, channel: str, delay: str, width: str) -> None:
        """Set a channel to delay-width mode with active delay and width."""

        ch = self._channel(channel)
        rising_edge, falling_edge = CHANNEL_EDGES[ch]
        self.command(f"CHAN:DelayWidth {ch}", expect_response=False)
        self.command(f"TIME:DEL{rising_edge} {delay}", expect_response=False)
        self.command(f"TIME:DEL{falling_edge} {width}", expect_response=False)

    def enable_channel(self, channel: str) -> None:
        """Enable a channel output."""

        self.command(f"CHAN:ON {self._channel(channel)}", expect_response=False)

    def disable_channel(self, channel: str) -> None:
        """Disable a channel output."""

        self.command(f"CHAN:OFF {self._channel(channel)}", expect_response=False)

    def apply_recipe(self, recipe: dict[str, Any]) -> dict[str, Any]:
        """Apply one T660 unit's recipe section through documented commands."""

        applied: dict[str, Any] = {"device": self.name, "commands": []}

        if recipe.get("stop_first", False):
            self.command("STOP", expect_response=False)
            applied["commands"].append("STOP")

        clock = recipe.get("clock") or {}
        if clock:
            self.set_clock_mode(
                clock.get("mode"),
                frequency=clock.get("frequency"),
                shots=clock.get("shots"),
            )
            applied["clock"] = clock

        if "trigger_source" in recipe:
            self.set_trigger_source(str(recipe["trigger_source"]))
            applied["trigger_source"] = recipe["trigger_source"]

        channels = recipe.get("channels") or {}
        for channel, settings in channels.items():
            ch = self._channel(channel)
            if not isinstance(settings, dict):
                raise T660ConfigurationError(f"{self.name} channel {ch} settings must be a mapping")
            if "delay" in settings or "width" in settings:
                if "delay" not in settings or "width" not in settings:
                    raise T660ConfigurationError(
                        f"{self.name} channel {ch} needs both delay and width"
                    )
                self.set_channel_delay_width(ch, str(settings["delay"]), str(settings["width"]))
            polarity = settings.get("polarity")
            if polarity:
                normalized = str(polarity).lower()
                if normalized in {"positive", "pos", "+"}:
                    self.command(f"CHAN:POS {ch}", expect_response=False)
                elif normalized in {"negative", "neg", "-"}:
                    self.command(f"CHAN:NEG {ch}", expect_response=False)
                else:
                    raise T660ConfigurationError(
                        f"{self.name} channel {ch} unsupported polarity {polarity!r}"
                    )
            termination = settings.get("termination")
            if termination:
                normalized = str(termination).upper()
                if normalized in {"50OHM", "50", "ON"}:
                    self.command(f"CHAN:50OHM {ch}", expect_response=False)
                elif normalized in {"LOWZ", "LOW_Z", "OFF"}:
                    self.command(f"CHAN:LOwZ {ch}", expect_response=False)
                else:
                    raise T660ConfigurationError(
                        f"{self.name} channel {ch} unsupported termination {termination!r}"
                    )
            if settings.get("enabled") is True:
                self.enable_channel(ch)
            elif settings.get("enabled") is False:
                self.disable_channel(ch)
            applied.setdefault("channels", {})[ch] = settings

        if recipe.get("force_eod", False):
            self.force_eod()
            applied["force_eod"] = True

        if recipe.get("start", False):
            self.command("START", expect_response=False)
            applied["start"] = True

        return applied

    def read_active_settings(self) -> dict[str, Any]:
        """Query active timing, trigger, and channel settings."""

        settings: dict[str, Any] = {
            "device": self.name,
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "queries": {},
        }
        for label, command in [
            ("identity", "*IDN?"),
            ("firmware", "IDentify"),
            ("trigger_source", "TRIG:SOUR?"),
            ("synth_frequency", "TRIG:FREQ:SYN?"),
            ("shots", "TRIG:SHOTS?"),
        ]:
            settings["queries"][label] = self._safe_query(command)

        channel_settings: dict[str, Any] = {}
        for channel, edges in CHANNEL_EDGES.items():
            channel_settings[channel] = {
                "enabled": self._safe_query(f"CHAN:ON? {channel}"),
                "timing_mode": self._safe_query(f"CHAN:TimingMODe? {channel}"),
                "termination": self._safe_query(f"CHAN:50OHM? {channel}"),
                "delay_edge": self._safe_query(f"TIME:DEL{edges[0]}?"),
                "width_edge": self._safe_query(f"TIME:DEL{edges[1]}?"),
            }
        settings["channels"] = channel_settings
        return settings

    def close(self) -> None:
        """Close the hardware command session."""

        if self._serial is not None:
            self._serial.close()
            self._serial = None
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def command(
        self,
        command: str,
        *,
        expect_response: bool = True,
        delay_s: float = 0.04,
    ) -> str:
        """Send one command and return the raw text response."""

        if self._serial is None and self._socket is None:
            raise T660Error(f"{self.name} is not connected")
        if self._serial is not None:
            self._serial.reset_input_buffer()
            self._serial.write((command + "\r").encode("ascii"))
            self._serial.flush()
            time.sleep(delay_s)
            response = self._read_serial()
        else:
            assert self._socket is not None
            self._socket.sendall((command + "\r").encode("ascii"))
            time.sleep(delay_s)
            response = self._read_socket()

        self._log(command, response)
        stripped = response.strip()
        if stripped.startswith("??") or stripped.startswith("?"):
            raise T660CommandError(f"{self.name} command {command!r} failed: {stripped}")
        if expect_response and not stripped:
            raise T660CommandError(f"{self.name} command {command!r} returned no response")
        return stripped

    def _set_p500_session(self) -> None:
        """Select P500-style commands using documented short or long form."""

        errors: list[str] = []
        for command in ("ZM P500", "ZMode P500"):
            try:
                self.command(command, expect_response=False)
                return
            except T660CommandError as exc:
                errors.append(str(exc))
        raise T660CommandError(
            f"{self.name} could not enter P500 command mode: {'; '.join(errors)}"
        )

    def _safe_query(self, command: str) -> dict[str, Any]:
        try:
            return {"ok": True, "response": self.command(command)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _read_serial(self) -> str:
        lines: list[str] = []
        deadline = time.time() + self.timeout_s
        assert self._serial is not None
        while time.time() < deadline:
            line = self._serial.readline()
            if not line:
                break
            text = line.decode("ascii", errors="replace").strip()
            if text:
                lines.append(text)
        return "\n".join(lines)

    def _read_socket(self) -> str:
        chunks: list[bytes] = []
        deadline = time.time() + self.timeout_s
        assert self._socket is not None
        while time.time() < deadline:
            try:
                chunk = self._socket.recv(4096)
            except TimeoutError:
                break
            if not chunk:
                break
            chunks.append(chunk)
            if b"\n" in chunk or b"\r" in chunk:
                break
        return b"".join(chunks).decode("ascii", errors="replace").strip()

    def _log(self, command: str, response: str) -> None:
        if self.command_log is None:
            return
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        self.command_log.write(f"{timestamp} {self.name} << {command}\n")
        if response:
            for line in response.splitlines():
                self.command_log.write(f"{timestamp} {self.name} >> {line}\n")
        self.command_log.flush()

    @staticmethod
    def _channel(channel: str) -> str:
        ch = str(channel).upper()
        if ch not in CHANNEL_EDGES:
            raise T660ConfigurationError(f"unsupported T660 channel {channel!r}")
        return ch
