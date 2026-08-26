"""Capture the authorized WM-01 initial electronic qualification snapshot."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

PHASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PHASE_DIR.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_app.devices.coherent_wavemaster_service import CoherentWaveMasterService


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> int:
    output = PHASE_DIR / "raw" / "initial_electronic_snapshot.json"
    log_path = PHASE_DIR / "command_log.txt"
    with log_path.open("a", encoding="utf-8", newline="\n") as command_log:
        command_log.write(f"{utc_now()} WM-01 initial electronic capture start\n")
        meter = CoherentWaveMasterService.from_config(command_log=command_log)
        meter.connect()
        try:
            identity = meter.identify()
            snapshot = {
                "schema_version": "1.0.0",
                "campaign_id": "system_recalibration_001",
                "phase_id": "WM-01",
                "phase_run_id": "WM01-RUN-20260821",
                "capture_start_utc": utc_now(),
                "connection": {
                    "preferred_port": meter.device_config["preferred_port"],
                    "usb_vid_hex": meter.device_config["usb_vid_hex"],
                    "usb_pid_hex": meter.device_config["usb_pid_hex"],
                    "usb_serial_number": meter.device_config["usb_serial_number"],
                    "port_serial_number": meter.device_config["port_serial_number"],
                    "adapter_model": meter.device_config["usb_adapter_model"],
                    "driver_provider": meter.device_config["driver_provider"],
                    "driver_version": meter.device_config["driver_version_observed"],
                    "baudrate": meter.device_config["baudrate"],
                    "bytesize": meter.device_config["bytesize"],
                    "parity": meter.device_config["parity"],
                    "stopbits": meter.device_config["stopbits"],
                    "flow_control": meter.device_config["flow_control"],
                },
                "identity": asdict(identity),
                "self_test_raw_value_hex": f"0x{meter.self_test():02X}",
                "settings_readback": {
                    "autocalibration": meter.get_autocalibration(),
                    "mode": meter.get_mode(),
                    "units": meter.get_units(),
                    "period_s": meter.get_period_s(),
                },
                "blocked_measurement": asdict(meter.get_measurement()),
                "capture_end_utc": utc_now(),
                "interpretation_limits": [
                    "The self-test byte is retained natively pending documented bit interpretation.",
                    "No Signal, Saturated, and Multi-Line are non-numeric outcomes.",
                    "This capture does not establish optical wavelength or spectral-power fractions.",
                ],
            }
        finally:
            meter.close()
        output.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        command_log.write(f"{utc_now()} WM-01 initial electronic capture end\n")
    print(json.dumps(snapshot, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
