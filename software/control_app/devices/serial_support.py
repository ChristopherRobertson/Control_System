"""Shared serial-port identity and unresolved-value helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


VALUE_REQUIRED = "[VALUE_REQUIRED]"


class SerialIdentityError(RuntimeError):
    """Raised when a configured serial device cannot be identified uniquely."""


def is_value_required(value: Any) -> bool:
    """Return whether a configuration value is the explicit unresolved marker."""

    return isinstance(value, str) and value.strip() == VALUE_REQUIRED


def unresolved_fields(
    device_config: dict[str, Any], required_fields: Iterable[str]
) -> list[str]:
    """Return required top-level fields that are absent or unresolved."""

    unresolved: list[str] = []
    for field in required_fields:
        value = device_config.get(field)
        if value is None or value == "" or is_value_required(value):
            unresolved.append(str(field))
    return unresolved


def resolve_serial_port(
    device_config: dict[str, Any], *, ports: Iterable[Any] | None = None
) -> str:
    """Resolve a COM device by adapter identity, with a verified port fallback.

    COM assignments may change.  When USB identity fields exist, this function
    matches VID, PID, and the adapter or port-interface serial before accepting
    ``preferred_port``.  The latter remains an observation, not device identity.
    """

    if ports is None:
        try:
            from serial.tools import list_ports
        except ImportError as exc:  # pragma: no cover - dependency gate
            raise SerialIdentityError("pyserial is required for port discovery") from exc
        ports = list_ports.comports()
    candidates = list(ports)

    preferred = device_config.get("preferred_port")
    port_serial = device_config.get("port_serial_number")
    usb_serial = device_config.get("usb_serial_number")
    vid = _parse_hex(device_config.get("usb_vid_hex"), "usb_vid_hex")
    pid = _parse_hex(device_config.get("usb_pid_hex"), "usb_pid_hex")

    unresolved_identity = [
        name
        for name, value in (
            ("preferred_port", preferred),
            ("port_serial_number", port_serial),
            ("usb_serial_number", usb_serial),
            ("usb_vid_hex", device_config.get("usb_vid_hex")),
            ("usb_pid_hex", device_config.get("usb_pid_hex")),
        )
        if value in (None, "") or is_value_required(value)
    ]
    if unresolved_identity:
        raise SerialIdentityError(
            "serial identity is unresolved: " + ", ".join(unresolved_identity)
        )

    matches = []
    for port in candidates:
        serial_number = str(getattr(port, "serial_number", "") or "")
        serial_match = serial_number.casefold() == str(port_serial).casefold()
        if not serial_match and usb_serial:
            # FTDI exposes an interface suffix (for example A) on some ports.
            serial_match = serial_number.casefold().startswith(str(usb_serial).casefold())
        if (
            serial_match
            and getattr(port, "vid", None) == vid
            and getattr(port, "pid", None) == pid
        ):
            matches.append(port)

    if len(matches) == 1:
        return str(matches[0].device)
    if len(matches) > 1:
        raise SerialIdentityError(
            f"multiple serial ports match configured adapter identity: "
            f"{[str(item.device) for item in matches]}"
        )

    preferred_matches = [
        item
        for item in candidates
        if str(getattr(item, "device", "")).casefold() == str(preferred).casefold()
    ]
    if preferred_matches:
        item = preferred_matches[0]
        observed = (
            getattr(item, "vid", None),
            getattr(item, "pid", None),
            str(getattr(item, "serial_number", "") or ""),
        )
        raise SerialIdentityError(
            f"preferred port {preferred!r} is present but its identity {observed!r} "
            "does not match the configured adapter"
        )
    raise SerialIdentityError("configured serial adapter is not present")


def _parse_hex(value: Any, field: str) -> int:
    if value in (None, "") or is_value_required(value):
        raise SerialIdentityError(f"{field} is unresolved")
    try:
        return int(str(value), 16)
    except ValueError as exc:
        raise SerialIdentityError(f"{field} must contain a hexadecimal value") from exc
