"""Serial service for a Coherent WaveMaster wavelength meter."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import time
from typing import Any, Callable, TextIO

from control_app.config_loader import load_hardware_config
from control_app.devices.serial_support import (
    SerialIdentityError,
    unresolved_fields,
    resolve_serial_port,
)


class WaveMasterError(RuntimeError):
    """Base error for WaveMaster service failures."""


class WaveMasterConfigurationError(WaveMasterError):
    """Raised when required WaveMaster configuration is unresolved."""


class WaveMasterCommunicationError(WaveMasterError):
    """Raised for missing, malformed, or error replies."""


@dataclass(frozen=True)
class WaveMasterIdentity:
    manufacturer: str
    model: str
    serial_number: str
    firmware_revision: str
    raw: str


@dataclass(frozen=True)
class WaveMasterMeasurement:
    time_tag_10ms: int
    value_text: str
    value: float | None
    quality: str
    raw: str


class CoherentWaveMasterService:
    """Identity-bound WaveMaster serial session.

    Query operations are always available after connection.  Commands that
    change mode, units, autocalibration, or front-panel ownership require an
    explicit ``allow_settings=True`` session.
    """

    def __init__(
        self,
        device_config: dict[str, Any],
        *,
        allow_settings: bool = False,
        timeout_s: float = 2.0,
        command_log: TextIO | None = None,
        serial_factory: Callable[..., Any] | None = None,
        ports_provider: Callable[[], Any] | None = None,
    ) -> None:
        self.device_config = device_config
        self.allow_settings = allow_settings
        self.timeout_s = timeout_s
        self.command_log = command_log
        self.serial_factory = serial_factory
        self.ports_provider = ports_provider
        self._serial: Any | None = None

    @classmethod
    def from_config(
        cls,
        *,
        config_path: str | Path | None = None,
        allow_settings: bool = False,
        timeout_s: float = 2.0,
        command_log: TextIO | None = None,
    ) -> "CoherentWaveMasterService":
        config, _, _ = load_hardware_config(config_path)
        device = (config.get("devices") or {}).get("wavemaster")
        if not isinstance(device, dict):
            raise WaveMasterConfigurationError("devices.wavemaster is not configured")
        return cls(
            device,
            allow_settings=allow_settings,
            timeout_s=timeout_s,
            command_log=command_log,
        )

    def phase_entry_gaps(self) -> list[str]:
        fields = self.device_config.get("phase_entry_required_fields") or []
        if not isinstance(fields, list):
            raise WaveMasterConfigurationError(
                "phase_entry_required_fields must be a list"
            )
        return unresolved_fields(self.device_config, [str(item) for item in fields])

    def assert_phase_entry_ready(self) -> None:
        gaps = self.phase_entry_gaps()
        if gaps:
            raise WaveMasterConfigurationError(
                "WM-01 entry is blocked by [VALUE_REQUIRED] fields: "
                + ", ".join(gaps)
            )

    def connect(self) -> None:
        self.assert_phase_entry_ready()
        if self._serial is not None:
            return
        try:
            import serial
        except ImportError as exc:  # pragma: no cover - dependency gate
            raise WaveMasterConfigurationError("pyserial is required") from exc
        ports = self.ports_provider() if self.ports_provider is not None else None
        try:
            port = resolve_serial_port(self.device_config, ports=ports)
        except SerialIdentityError as exc:
            raise WaveMasterConfigurationError(str(exc)) from exc
        factory = self.serial_factory or serial.Serial
        self._serial = factory(
            port=port,
            baudrate=int(self.device_config.get("baudrate", 9600)),
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout_s,
            write_timeout=self.timeout_s,
            xonxoff=False,
            rtscts=True,
            dsrdtr=False,
        )
        try:
            self.identify()
        except Exception:
            self.close()
            raise

    def identify(self) -> WaveMasterIdentity:
        identity = parse_identity_reply(self.query("*IDN?"))
        expected = str(self.device_config.get("serial_number") or "")
        if identity.serial_number != expected:
            raise WaveMasterCommunicationError(
                f"WaveMaster serial mismatch: expected {expected}, "
                f"received {identity.serial_number}"
            )
        expected_firmware = str(self.device_config.get("firmware_revision") or "")
        if identity.firmware_revision != expected_firmware:
            raise WaveMasterCommunicationError(
                f"WaveMaster firmware mismatch: expected {expected_firmware}, "
                f"received {identity.firmware_revision}"
            )
        expected_model = str(self.device_config.get("model_number") or "")
        if expected_model and identity.model.casefold() != expected_model.casefold():
            raise WaveMasterCommunicationError(
                f"WaveMaster model mismatch: expected {expected_model}, "
                f"received {identity.model}"
            )
        return identity

    def self_test(self) -> int:
        response = self.query("*TST?")
        value = response.split("$", 1)[-1].strip()
        try:
            return int(value, 16)
        except ValueError as exc:
            raise WaveMasterCommunicationError(
                f"malformed self-test reply {response!r}"
            ) from exc

    def get_autocalibration(self) -> str:
        return self._query_value("CAL?")

    def get_mode(self) -> str:
        return self._query_value("MDE?")

    def get_units(self) -> str:
        return self._query_value("UNI?")

    def get_period_s(self) -> int:
        return int(self._query_value("PRD?"))

    def get_measurement(self) -> WaveMasterMeasurement:
        return parse_measurement_reply(self.query("VAL?"))

    def set_autocalibration(self, enabled: bool) -> None:
        expected = "ON" if enabled else "OFF"
        self._setting_with_readback(f"CAL {expected}", "CAL?", expected)

    def set_mode(self, mode: str) -> None:
        normalized = str(mode).strip().upper()
        if normalized not in {"C", "A", "P"}:
            raise WaveMasterConfigurationError("mode must be C, A, or P")
        self._setting_with_readback(f"MDE {normalized}", "MDE?", normalized)

    def set_units(self, units: str) -> None:
        normalized = str(units).strip().upper()
        if normalized not in {"A", "V", "F", "W"}:
            raise WaveMasterConfigurationError("units must be A, V, F, or W")
        self._setting_with_readback(f"UNI {normalized}", "UNI?", normalized)

    def set_period_s(self, seconds: int) -> None:
        value = int(seconds)
        if value not in (0,) and value < 5:
            raise WaveMasterConfigurationError(
                "period must be 0 (disabled) or at least 5 seconds"
            )
        self._setting_with_readback(f"PRD {value}", "PRD?", str(value))

    def set_local(self) -> None:
        self._setting_with_readback("LOC", "LOC?", "LOC")

    def set_remote(self) -> None:
        self._setting_with_readback("REM", "REM?", "REM")

    def identity_snapshot(self) -> dict[str, Any]:
        identity = self.identify()
        return {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "identity": asdict(identity),
            "self_test_hex": f"0x{self.self_test():02X}",
            "autocalibration": self.get_autocalibration(),
            "mode": self.get_mode(),
            "units": self.get_units(),
            "period_s": self.get_period_s(),
        }

    def query(self, command: str) -> str:
        normalized = command.strip().upper()
        if not normalized.endswith("?"):
            raise WaveMasterConfigurationError("query must end with '?'")
        return self._exchange(normalized)

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def __enter__(self) -> "CoherentWaveMasterService":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _query_value(self, command: str) -> str:
        response = self.query(command)
        if "$" not in response:
            raise WaveMasterCommunicationError(f"malformed reply {response!r}")
        return response.split("$", 1)[1].strip()

    def _setting_with_readback(
        self, command: str, readback_query: str, expected: str
    ) -> None:
        if not self.allow_settings:
            raise WaveMasterConfigurationError(
                "WaveMaster setting changes require allow_settings=True"
            )
        self._write_only(command)
        actual = self._query_value(readback_query)
        if actual.strip().upper() != expected.strip().upper():
            raise WaveMasterCommunicationError(
                f"WaveMaster setting verification failed for {command!r}: "
                f"expected {expected!r}, received {actual!r}"
            )

    def _write_only(self, command: str) -> None:
        """Transmit a documented setting command that does not return a reply."""

        if self._serial is None:
            raise WaveMasterCommunicationError("WaveMaster is not connected")
        self._serial.reset_input_buffer()
        payload = (command + "\r").encode("ascii")
        self._serial.write(payload)
        self._serial.flush()
        self._log(command, "[NO_DIRECT_REPLY]")

    def _exchange(self, command: str) -> str:
        if self._serial is None:
            raise WaveMasterCommunicationError("WaveMaster is not connected")
        self._serial.reset_input_buffer()
        payload = (command + "\r").encode("ascii")
        self._serial.write(payload)
        self._serial.flush()
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            raw = self._serial.readline()
            if not raw:
                continue
            response = raw.decode("ascii", errors="replace").strip()
            if not response:
                continue
            self._log(command, response)
            if response.startswith("ERR$"):
                raise WaveMasterCommunicationError(response)
            return response
        raise WaveMasterCommunicationError(f"no reply for {command!r}")

    def _log(self, command: str, response: str) -> None:
        if self.command_log is None:
            return
        stamp = datetime.now(UTC).isoformat(timespec="milliseconds")
        self.command_log.write(f"{stamp} wavemaster << {command}\n")
        self.command_log.write(f"{stamp} wavemaster >> {response}\n")
        self.command_log.flush()


def parse_identity_reply(reply: str) -> WaveMasterIdentity:
    text = reply.strip()
    payload = text.split("$", 1)[1] if "$" in text else text
    fields = [item.strip() for item in payload.split(",")]
    if len(fields) != 4 or not all(fields):
        raise WaveMasterCommunicationError(f"malformed identity reply {reply!r}")
    return WaveMasterIdentity(*fields, raw=text)


def parse_measurement_reply(reply: str) -> WaveMasterMeasurement:
    text = reply.strip()
    if not text.startswith("VAL$"):
        raise WaveMasterCommunicationError(f"malformed measurement reply {reply!r}")
    payload = text[4:]
    fields = payload.split(",", 1)
    if len(fields) != 2:
        raise WaveMasterCommunicationError(f"malformed measurement reply {reply!r}")
    try:
        time_tag = int(fields[0].strip())
    except ValueError as exc:
        raise WaveMasterCommunicationError(
            f"malformed measurement time tag {reply!r}"
        ) from exc
    value_text = fields[1].strip()
    quality = value_text.casefold().replace("-", "_").replace(" ", "_")
    value: float | None = None
    if quality not in {"saturated", "multi_line", "no_signal"}:
        match = re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", value_text)
        if match is None:
            raise WaveMasterCommunicationError(
                f"unknown WaveMaster measurement value {value_text!r}"
            )
        value = float(value_text)
        quality = "valid"
    return WaveMasterMeasurement(time_tag, value_text, value, quality, text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Coherent WaveMaster serial service")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    meter = CoherentWaveMasterService.from_config(config_path=args.config)
    gaps = meter.phase_entry_gaps()
    if args.preflight or gaps:
        print(
            json.dumps(
                {
                    "phase_id": "WM-01",
                    "ready": not gaps,
                    "value_required_fields": gaps,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if not gaps else 2
    with meter:
        result = meter.identity_snapshot()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
