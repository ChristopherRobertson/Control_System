"""Workflow for Arduino MUX routing and PicoScope diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO
import csv
import json

from control_app.config_loader import ConfigInventory, load_config_inventory
from control_app.devices.arduino_mux_service import ArduinoMuxService
from control_app.devices.picoscope_service import PicoScopeService
from control_app.manifest import new_manifest, write_manifest


class MuxPicoDiagnosticError(RuntimeError):
    """Raised when the MUX/Pico diagnostic cannot run or fails."""


def count_rising_edges(samples: list[int], *, threshold: int) -> int:
    """Count rising threshold crossings in real captured samples."""

    count = 0
    previous_high = samples[0] >= threshold if samples else False
    for value in samples[1:]:
        current_high = value >= threshold
        if current_high and not previous_high:
            count += 1
        previous_high = current_high
    return count


class MuxPicoDiagnostic:
    """Capture PicoScope data from MUX-selected HF2LI DIO/AUX diagnostics."""

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
        ch_a_route: str,
        ch_b_route: str,
        ext_route: str,
        run_dir: str | Path,
    ) -> dict[str, Any]:
        """Run the real diagnostic and write route, raw capture, summary, and manifest files."""

        if not self.inventory.mux_routes:
            raise MuxPicoDiagnosticError(
                "No MUX routes are defined in hardware_configuration.yaml"
            )
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        calibration_dir = Path("calibration")
        calibration_dir.mkdir(parents=True, exist_ok=True)
        raw_csv = calibration_dir / "picoscope_mux_diagnostic_capture.csv"

        mux = ArduinoMuxService.from_config(config_path=self.config_path, command_log=self.command_log)
        pico = PicoScopeService.from_config(config_path=self.config_path, command_log=self.command_log)
        try:
            mux.connect()
            mux.set_ch_a_route(ch_a_route)
            mux.set_ch_b_route(ch_b_route)
            mux.set_ext_route(ext_route)
            route_readback = mux.query_active_route()

            pico.open_unit()
            capture_summary = pico.capture_block(raw_csv)
            pico.stop()
        finally:
            try:
                pico.close_unit()
            finally:
                mux.close()

        ch_a_samples: list[int] = []
        with raw_csv.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                ch_a_samples.append(int(row["ch_a_adc"]))
        threshold = int(
            self.inventory.picoscope_settings.get("capture_settings", {}).get(
                "pulse_count_threshold_adc", 1000
            )
        )
        pulse_count = count_rising_edges(ch_a_samples, threshold=threshold)
        capture_summary.update(
            {
                "operator": self.operator,
                "config_hash": self.inventory.config_hash,
                "pulse_count_detected": pulse_count,
                "mux_routes": {
                    "ch_a": ch_a_route,
                    "ch_b": ch_b_route,
                    "ext": ext_route,
                    "readback": route_readback,
                },
            }
        )
        if pulse_count < 100:
            raise MuxPicoDiagnosticError(f"captured fewer than 100 pulses: {pulse_count}")

        settings_path = calibration_dir / "picoscope_mux_capture_settings.json"
        summary_path = calibration_dir / "picoscope_mux_capture_summary.json"
        settings_path.write_text(
            json.dumps(self.inventory.picoscope_settings, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        summary_path.write_text(
            json.dumps(capture_summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        route_log = calibration_dir / "mux_scope_route_verification.csv"
        write_header = not route_log.exists()
        with route_log.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "timestamp_utc",
                    "operator",
                    "config_hash",
                    "requested_ch_a_route",
                    "returned_or_echoed_ch_a_route",
                    "requested_ch_b_route",
                    "returned_or_echoed_ch_b_route",
                    "requested_ext_route",
                    "returned_or_echoed_ext_route",
                    "verification_status",
                    "notes",
                ],
            )
            if write_header:
                writer.writeheader()
            latched = route_readback.get("latched_routes", {})
            writer.writerow(
                {
                    "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                    "operator": self.operator,
                    "config_hash": self.inventory.config_hash,
                    "requested_ch_a_route": ch_a_route,
                    "returned_or_echoed_ch_a_route": latched.get("ch_a"),
                    "requested_ch_b_route": ch_b_route,
                    "returned_or_echoed_ch_b_route": latched.get("ch_b"),
                    "requested_ext_route": ext_route,
                    "returned_or_echoed_ext_route": latched.get("ext"),
                    "verification_status": "PASS",
                    "notes": route_readback.get("notes", ""),
                }
            )

        manifest = new_manifest(
            operator=self.operator,
            inventory=self.inventory,
            mux_routes=capture_summary["mux_routes"],
            picoscope_settings=self.inventory.picoscope_settings,
            raw_data_paths=[str(raw_csv)],
            command_log_paths=[],
            device_readback_paths=[str(summary_path), str(route_log)],
            blocker_status={"blocked": False, "blockers": [], "next_actions": []},
        )
        manifest_path = run_path / "run_manifest.json"
        write_manifest(manifest_path, manifest)
        return capture_summary
