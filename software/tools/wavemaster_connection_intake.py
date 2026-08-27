"""Read-only WaveMaster connection intake; never edits campaign configuration."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_app.devices.coherent_wavemaster_service import parse_identity_reply


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Collect read-only WaveMaster/adapter identity observations needed "
            "to resolve WM-01 entry placeholders."
        )
    )
    parser.add_argument("--port", required=True, help="Observed COM port, e.g. COM6")
    parser.add_argument(
        "--confirm-cable-inspected",
        action="store_true",
        help="Confirm that the straight-through RTS/CTS cable was inspected.",
    )
    args = parser.parse_args()
    if not args.confirm_cable_inspected:
        parser.error("--confirm-cable-inspected is required")

    try:
        import serial
        from serial.tools import list_ports
    except ImportError as exc:
        raise SystemExit("pyserial is required for WaveMaster intake") from exc

    observed = [item for item in list_ports.comports() if item.device == args.port]
    if len(observed) != 1:
        available = [item.device for item in list_ports.comports()]
        raise SystemExit(
            f"port {args.port!r} was not identified uniquely; available={available!r}"
        )
    port_info = observed[0]
    meter = serial.Serial(
        port=args.port,
        baudrate=9600,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=2.0,
        write_timeout=2.0,
        xonxoff=False,
        rtscts=True,
        dsrdtr=False,
    )
    try:
        meter.reset_input_buffer()
        meter.write(b"*IDN?\r")
        meter.flush()
        deadline = time.monotonic() + 2.0
        raw = b""
        while time.monotonic() < deadline and not raw:
            raw = meter.readline()
        if not raw:
            raise SystemExit("WaveMaster returned no *IDN? response")
        response = raw.decode("ascii", errors="replace").strip()
        identity = parse_identity_reply(response)
    finally:
        meter.close()

    vid = getattr(port_info, "vid", None)
    pid = getattr(port_info, "pid", None)
    result = {
        "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "purpose": "PRE-WM-01_CONNECTION_INTAKE_ONLY",
        "phase_authorized": False,
        "observed_config_values": {
            "serial_number": identity.serial_number,
            "instrument_identity_response": identity.raw,
            "firmware_revision": identity.firmware_revision,
            "preferred_port": str(port_info.device),
            "usb_vid_hex": f"{vid:04X}" if isinstance(vid, int) else "[VALUE_REQUIRED]",
            "usb_pid_hex": f"{pid:04X}" if isinstance(pid, int) else "[VALUE_REQUIRED]",
            "port_serial_number": str(
                getattr(port_info, "serial_number", "") or "[VALUE_REQUIRED]"
            ),
            "usb_adapter_model": str(
                getattr(port_info, "description", "") or "[VALUE_REQUIRED]"
            ),
        },
        "still_requires_independent_observation": [
            "usb_serial_number",
            "driver_provider",
            "driver_version_observed",
        ],
        "note": (
            "This query does not start or qualify WM-01 and does not edit "
            "hardware_configuration.yaml. Review every observation before "
            "replacing a [VALUE_REQUIRED] field."
        ),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
