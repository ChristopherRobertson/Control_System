"""Identity-bound serial service for the permanent Thorlabs ELL15 iris."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import time
from typing import Any, Callable, TextIO

from control_app.config_loader import load_hardware_config
from control_app.devices.serial_support import SerialIdentityError, resolve_serial_port


class ELL15Error(RuntimeError):
    """Base error for ELL15 service failures."""


class ELL15ConfigurationError(ELL15Error):
    """Raised when the ELL15 configuration is missing or inconsistent."""


class ELL15CommunicationError(ELL15Error):
    """Raised when the ELL15 reply is missing, malformed, or reports an error."""


class ELL15MotionAuthorizationError(ELL15Error):
    """Raised when a caller requests movement from a query-only session."""


@dataclass(frozen=True)
class ELL15Identity:
    address: str
    model_code_hex: str
    serial_number: str
    manufacture_year: int
    firmware_field_hex: str
    hardware_field_hex: str
    travel_counts: int
    counts_per_mm: int

    @property
    def maximum_aperture_mm(self) -> float:
        return self.travel_counts / self.counts_per_mm


class ELL15IrisService:
    """Control one ELL15 through its USB serial converter.

    Connection and all readbacks are non-moving.  Motion methods require an
    explicit ``allow_motion=True`` construction argument so ordinary status
    inspection cannot change the optical path accidentally.
    """

    def __init__(
        self,
        device_config: dict[str, Any],
        *,
        allow_motion: bool = False,
        timeout_s: float = 2.0,
        command_log: TextIO | None = None,
        serial_factory: Callable[..., Any] | None = None,
        ports_provider: Callable[[], Any] | None = None,
    ) -> None:
        self.device_config = device_config
        self.allow_motion = allow_motion
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
        allow_motion: bool = False,
        timeout_s: float = 2.0,
        command_log: TextIO | None = None,
    ) -> "ELL15IrisService":
        config, _, _ = load_hardware_config(config_path)
        device = (config.get("devices") or {}).get("opo_iris")
        if not isinstance(device, dict):
            raise ELL15ConfigurationError("devices.opo_iris is not configured")
        return cls(
            device,
            allow_motion=allow_motion,
            timeout_s=timeout_s,
            command_log=command_log,
        )

    def connect(self) -> None:
        if self._serial is not None:
            return
        try:
            import serial
        except ImportError as exc:  # pragma: no cover - dependency gate
            raise ELL15ConfigurationError("pyserial is required for iris control") from exc
        ports = self.ports_provider() if self.ports_provider is not None else None
        try:
            port = resolve_serial_port(self.device_config, ports=ports)
        except SerialIdentityError as exc:
            raise ELL15ConfigurationError(str(exc)) from exc
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
            rtscts=False,
            dsrdtr=False,
        )
        try:
            self.identify()
        except Exception:
            self.close()
            raise

    def identify(self) -> ELL15Identity:
        reply = self._exchange("in", final_prefix="IN")
        identity = parse_identity_reply(reply)
        expected_serial = str(self.device_config.get("serial_number") or "")
        if expected_serial and identity.serial_number != expected_serial:
            raise ELL15CommunicationError(
                f"iris serial mismatch: expected {expected_serial}, "
                f"received {identity.serial_number}"
            )
        expected_model = str(self.device_config.get("protocol_model_code_hex") or "")
        if expected_model and identity.model_code_hex.casefold() != expected_model.casefold():
            raise ELL15CommunicationError(
                f"iris model mismatch: expected {expected_model}, "
                f"received {identity.model_code_hex}"
            )
        comparisons = {
            "manufacture_year": identity.manufacture_year,
            "firmware_field_hex": identity.firmware_field_hex,
            "hardware_field_hex": identity.hardware_field_hex,
            "encoder_counts_per_mm": identity.counts_per_mm,
        }
        for field, observed in comparisons.items():
            expected = self.device_config.get(field)
            if expected is not None and str(expected).casefold() != str(observed).casefold():
                raise ELL15CommunicationError(
                    f"iris {field} mismatch: expected {expected}, received {observed}"
                )
        expected_maximum = self.device_config.get("maximum_aperture_mm")
        if expected_maximum is not None and abs(
            float(expected_maximum) - identity.maximum_aperture_mm
        ) > 1e-9:
            raise ELL15CommunicationError(
                "iris maximum_aperture_mm mismatch: expected "
                f"{expected_maximum}, received {identity.maximum_aperture_mm}"
            )
        return identity

    def get_aperture_mm(self) -> float:
        reply = self._exchange("gp", final_prefix="PO")
        counts = parse_position_reply(reply)
        scale = int(self.device_config.get("encoder_counts_per_mm", 1000))
        return counts / scale

    def get_status(self) -> int:
        """Return and clear the device status register as specified by Thorlabs."""

        reply = self._exchange("gs", final_prefix="GS")
        return int(reply[3:5], 16)

    def set_aperture_mm(
        self, diameter_mm: float, *, require_open_side_approach: bool = True
    ) -> float:
        """Move to an absolute diameter and return its readback.

        ELL15 repeatability is improved when the target is approached from a
        larger aperture.  By default this method refuses a move that violates
        that condition; the caller must first perform an explicitly authorized
        larger-aperture move.
        """

        self._require_motion()
        minimum = float(self.device_config.get("minimum_aperture_mm", 1.0))
        maximum = float(self.device_config.get("maximum_aperture_mm", 11.5))
        increment = float(self.device_config.get("minimum_incremental_motion_mm", 0.01))
        diameter = float(diameter_mm)
        if not minimum <= diameter <= maximum:
            raise ELL15ConfigurationError(
                f"aperture {diameter} mm is outside {minimum}..{maximum} mm"
            )
        rounded = round(diameter / increment) * increment
        if abs(rounded - diameter) > 1e-9:
            raise ELL15ConfigurationError(
                f"aperture must be an integer multiple of {increment} mm"
            )
        current = self.get_aperture_mm()
        if require_open_side_approach and current < diameter - 1e-9:
            raise ELL15MotionAuthorizationError(
                "target must be approached from a larger aperture; move to the "
                "qualified open-side starting point first"
            )
        if abs(current - diameter) <= 1e-9:
            return current
        scale = int(self.device_config.get("encoder_counts_per_mm", 1000))
        counts = int(round(diameter * scale))
        reply = self._exchange(f"ma{counts & 0xFFFFFFFF:08X}", final_prefix="PO")
        return parse_position_reply(reply) / scale

    def home(self) -> float:
        self._require_motion()
        reply = self._exchange("ho0", final_prefix="PO", timeout_s=6.0)
        return parse_position_reply(reply) / int(
            self.device_config.get("encoder_counts_per_mm", 1000)
        )

    def set_autohome(self, enabled: bool) -> float:
        self._require_motion()
        reply = self._exchange(f"ah{1 if enabled else 0}", final_prefix="PO", timeout_s=6.0)
        return parse_position_reply(reply) / int(
            self.device_config.get("encoder_counts_per_mm", 1000)
        )

    def identity_snapshot(self) -> dict[str, Any]:
        identity = self.identify()
        return {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "identity": asdict(identity),
            "maximum_aperture_mm_from_identity": identity.maximum_aperture_mm,
            "aperture_readback_mm": self.get_aperture_mm(),
            "motion_authorized": self.allow_motion,
        }

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def __enter__(self) -> "ELL15IrisService":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _exchange(
        self, command: str, *, final_prefix: str, timeout_s: float | None = None
    ) -> str:
        if self._serial is None:
            raise ELL15CommunicationError("iris is not connected")
        address = str(self.device_config.get("device_address", "0"))
        payload = f"{address}{command}".encode("ascii")
        self._serial.reset_input_buffer()
        self._serial.write(payload)
        self._serial.flush()
        deadline = time.monotonic() + (timeout_s or self.timeout_s)
        replies: list[str] = []
        final: str | None = None
        while time.monotonic() < deadline:
            raw = self._serial.readline()
            if not raw:
                continue
            text = raw.decode("ascii", errors="replace").strip()
            if not text:
                continue
            replies.append(text)
            self._log(payload.decode("ascii"), text)
            if len(text) >= 3 and text[0] == address and text[1:3] == final_prefix:
                final = text
                break
            if len(text) >= 5 and text[1:3] == "GS":
                status = int(text[3:5], 16)
                if status not in (0, 9):
                    raise ELL15CommunicationError(
                        f"iris returned status {status} for {payload!r}"
                    )
        if final is None:
            raise ELL15CommunicationError(
                f"no {final_prefix} reply for {payload!r}; received {replies!r}"
            )
        return final

    def _require_motion(self) -> None:
        if not self.allow_motion:
            raise ELL15MotionAuthorizationError(
                "iris motion requires an explicitly motion-authorized service session"
            )

    def _log(self, command: str, response: str) -> None:
        if self.command_log is None:
            return
        stamp = datetime.now(UTC).isoformat(timespec="milliseconds")
        self.command_log.write(f"{stamp} opo_iris << {command}\n")
        self.command_log.write(f"{stamp} opo_iris >> {response}\n")
        self.command_log.flush()


def parse_identity_reply(reply: str) -> ELL15Identity:
    text = reply.strip()
    if len(text) != 33 or text[1:3] != "IN":
        raise ELL15CommunicationError(f"malformed identity reply {reply!r}")
    try:
        return ELL15Identity(
            address=text[0],
            model_code_hex=text[3:5],
            serial_number=text[5:13],
            manufacture_year=int(text[13:17]),
            firmware_field_hex=text[17:19],
            hardware_field_hex=text[19:21],
            travel_counts=int(text[21:25], 16),
            counts_per_mm=int(text[25:33], 16),
        )
    except ValueError as exc:
        raise ELL15CommunicationError(f"malformed identity reply {reply!r}") from exc


def parse_position_reply(reply: str) -> int:
    text = reply.strip()
    if len(text) != 11 or text[1:3] != "PO":
        raise ELL15CommunicationError(f"malformed position reply {reply!r}")
    try:
        unsigned = int(text[3:11], 16)
    except ValueError as exc:
        raise ELL15CommunicationError(f"malformed position reply {reply!r}") from exc
    return unsigned - (1 << 32) if unsigned & (1 << 31) else unsigned


def main() -> int:
    parser = argparse.ArgumentParser(description="Identity-bound ELL15 iris service")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--diameter-mm", type=float)
    parser.add_argument("--allow-motion", action="store_true")
    args = parser.parse_args()
    if args.diameter_mm is not None and not args.allow_motion:
        parser.error("--diameter-mm requires --allow-motion")
    with ELL15IrisService.from_config(
        config_path=args.config, allow_motion=args.allow_motion
    ) as iris:
        result: dict[str, Any] = {"before": iris.identity_snapshot()}
        if args.diameter_mm is not None:
            result["commanded_diameter_mm"] = args.diameter_mm
            result["aperture_readback_mm"] = iris.set_aperture_mm(args.diameter_mm)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
