"""Workflow command handler for the Nd:YAG alignment tab."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

import yaml

from control_app.config_loader import ConfigInventory, load_config_inventory
from control_app.paths import LOG_ROOT, RUN_ROOT, resolve_compat_path
from control_app.devices.t660_service import T660Service
from control_app.ui.contracts import WorkflowCommand, WorkflowResult
from control_app.workflows.ndyag_alignment import (
    NDYAG_ALIGNMENT_TIMING_RECIPE,
    recipe_with_ui_parameters,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager


NDYAG_SAFE_IDLE_RECIPE: dict[str, Any] = {
    "name": "ndyag_safe_idle",
    "description": "Stop Nd:YAG alignment timing and disable both T660 units by channel.",
    "approved_laser_safety_condition": False,
    "t660": {
        "t660_1": {
            "stop_first": True,
            "trigger_source": "OFF",
            "force_eod": True,
            "channels": {
                "A": {"enabled": False},
                "B": {"enabled": False},
                "C": {"enabled": False},
                "D": {"enabled": False},
            },
        },
        "t660_2": {
            "stop_first": True,
            "trigger_source": "OFF",
            "force_eod": True,
            "channels": {
                "A": {"enabled": False},
                "B": {"enabled": False},
                "C": {"enabled": False},
                "D": {"enabled": False},
            },
        },
    },
}


class NdYagWidgetCommandHandler:
    """Command handler for the continuous 10 Hz Nd:YAG alignment workflow."""

    def __init__(
        self,
        *,
        operator: str = "UI",
        inventory: ConfigInventory | None = None,
    ) -> None:
        self.operator = operator
        self.inventory = inventory or load_config_inventory(write_files=False)
        self.config_path = Path(self.inventory.config_path)

    def __call__(self, command: WorkflowCommand) -> WorkflowResult:
        """Handle one Nd:YAG widget command."""

        if command.device_key != "ndyag":
            return WorkflowResult(status="blocked", message=f"Unsupported device {command.device_key}")
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
        name = command.command
        if name == "ndyag.refresh_status":
            readback = self._read_t660_units(command_log)
            return self._complete("Nd:YAG timing status refreshed", command_log, readback=readback)
        if name == "ndyag.safe_idle":
            readback = self._apply_recipe(
                command_log,
                NDYAG_SAFE_IDLE_RECIPE,
                "ndyag_safe_idle_readback.json",
            )
            return self._complete("Nd:YAG timing safe idle applied", command_log, readback=readback)
        if name == "ndyag.load_alignment_10hz":
            if not command.safety_approval:
                return WorkflowResult(
                    status="blocked",
                    message="Safety approval is required before loading continuous Nd:YAG timing.",
                    data={"state": self._state_from_readback(self._read_t660_units(command_log))},
                )
            safe_before = self._apply_recipe(
                command_log,
                NDYAG_SAFE_IDLE_RECIPE,
                "ndyag_safe_idle_before_alignment_readback.json",
            )
            try:
                alignment_recipe = self._alignment_recipe(command)
                alignment = self._apply_recipe(
                    command_log,
                    alignment_recipe,
                    "ndyag_alignment_10hz_readback.json",
                )
            except Exception as exc:  # noqa: BLE001 - recover laser timing to safe idle
                try:
                    safe_after_failure = self._apply_recipe(
                        command_log,
                        NDYAG_SAFE_IDLE_RECIPE,
                        "ndyag_safe_idle_after_failed_alignment_readback.json",
                    )
                    cleanup_state = self._state_from_readback(safe_after_failure)
                    return WorkflowResult(
                        status="failed",
                        message=f"Nd:YAG 10 Hz timing failed and safe idle was reapplied: {exc}",
                        data={
                            "state": cleanup_state,
                            "readback": safe_after_failure,
                            "extra_readbacks": {"safe_idle_before": safe_before},
                            "command_log": str(self._command_log_path()),
                        },
                    )
                except Exception as cleanup_exc:  # noqa: BLE001 - report failed recovery explicitly
                    return WorkflowResult(
                        status="failed",
                        message=(
                            "Nd:YAG 10 Hz timing failed, and safe idle cleanup also failed: "
                            f"{exc}; cleanup: {cleanup_exc}"
                        ),
                        data={
                            "state": self._state_from_readback(safe_before),
                            "readback": safe_before,
                            "command_log": str(self._command_log_path()),
                        },
                    )
            return self._complete(
                f"Nd:YAG 10 Hz alignment timing loaded {self._alignment_mode_message(command)}",
                command_log,
                readback=alignment,
                extra_readbacks={"safe_idle_before": safe_before},
            )
        return WorkflowResult(status="blocked", message=f"Unsupported command {name}")

    def _alignment_recipe(self, command: WorkflowCommand) -> dict[str, Any] | Path:
        has_ui_parameters = any(
            key in command.parameters
            for key in ("q_switch_delay_us", "shot_count", "continuous_mode")
        )
        recipe_path = resolve_compat_path(NDYAG_ALIGNMENT_TIMING_RECIPE)
        if not has_ui_parameters:
            return recipe_path
        with recipe_path.open("r", encoding="utf-8") as handle:
            recipe = yaml.safe_load(handle) or {}
        if not isinstance(recipe, dict):
            raise ValueError(f"{recipe_path} did not parse as a YAML mapping")
        return recipe_with_ui_parameters(
            recipe,
            q_switch_delay_us=command.parameters.get("q_switch_delay_us"),
            shot_count=command.parameters.get("shot_count", 0),
            continuous=bool(command.parameters.get("continuous_mode", True)),
        )

    def _alignment_mode_message(self, command: WorkflowCommand) -> str:
        if bool(command.parameters.get("continuous_mode", True)):
            return "and running continuously"
        return f"for {int(command.parameters.get('shot_count', 0))} shot(s)"

    def _apply_recipe(
        self,
        command_log: TextIO,
        recipe: str | Path | dict[str, Any],
        output_name: str,
    ) -> dict[str, Any]:
        manager = TimingRecipeManager(self.inventory, command_log=command_log)
        output_path = self._run_dir() / output_name
        return manager.apply_recipe(recipe, output_path=output_path)

    def _read_t660_units(self, command_log: TextIO) -> dict[str, Any]:
        devices: dict[str, Any] = {}
        for unit in ("t660_1", "t660_2"):
            service = T660Service.from_config(
                unit,
                config_path=self.config_path,
                command_log=command_log,
            )
            try:
                service.connect()
                service.identify()
                devices[unit] = service.read_active_settings()
            finally:
                service.close()
        return {
            "recipe_name": "ndyag_timing_direct_readback",
            "devices": devices,
            "matches_recipe": None,
            "mismatches": [],
        }

    def _complete(
        self,
        message: str,
        command_log: TextIO,
        *,
        readback: dict[str, Any],
        extra_readbacks: dict[str, Any] | None = None,
    ) -> WorkflowResult:
        state = self._state_from_readback(readback)
        data: dict[str, Any] = {
            "state": state,
            "readback": readback,
            "command_log": str(self._command_log_path()),
        }
        if extra_readbacks:
            data["extra_readbacks"] = extra_readbacks
        return WorkflowResult(status="complete", message=message, data=data)

    def _state_from_readback(self, readback: dict[str, Any]) -> dict[str, Any]:
        devices = readback.get("devices") or {}
        t660_1 = devices.get("t660_1") or {}
        t660_2 = devices.get("t660_2") or {}
        t660_1_queries = t660_1.get("queries") or {}
        t660_2_queries = t660_2.get("queries") or {}
        t660_1_channels = t660_1.get("channels") or {}
        t660_2_channels = t660_2.get("channels") or {}
        fire = t660_1_channels.get("A") or {}
        q_switch = t660_1_channels.get("B") or {}
        drive = t660_2_channels.get("D") or {}
        state: dict[str, Any] = {
            "recipe_name": readback.get("recipe_name"),
            "repetition_rate_hz": 10,
            "shot_count": _response(t660_2_queries.get("shots")),
            "t6602_trigger_source": _response(t660_2_queries.get("trigger_source")),
            "t6602_synth_frequency": _response(t660_2_queries.get("synth_frequency")),
            "t6602_drive_enabled": _response(drive.get("enabled")),
            "t6602_drive_delay": _response(drive.get("delay_edge")),
            "t6602_drive_width": _response(drive.get("width_edge")),
            "t6601_trigger_source": _response(t660_1_queries.get("trigger_source")),
            "fire_enabled": _response(fire.get("enabled")),
            "fire_delay": _response(fire.get("delay_edge")),
            "fire_width": _response(fire.get("width_edge")),
            "q_switch_enabled": _response(q_switch.get("enabled")),
            "q_switch_delay": _response(q_switch.get("delay_edge")),
            "q_switch_width": _response(q_switch.get("width_edge")),
            "matches_recipe": readback.get("matches_recipe"),
            "last_error": _readback_errors(readback),
        }
        return state

    def _run_dir(self) -> Path:
        path = RUN_ROOT / f"{datetime.now().strftime('%Y%m%d')}_ndyag_ui"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _command_log_path(self) -> Path:
        return LOG_ROOT / f"{datetime.now().strftime('%Y%m%d')}_ndyag_ui_command_log.txt"


def _response(value: Any) -> Any:
    if isinstance(value, dict):
        if value.get("ok"):
            return value.get("response")
        return value.get("error")
    return value


def _readback_errors(readback: dict[str, Any]) -> str | None:
    mismatches = readback.get("mismatches") or []
    if mismatches:
        return str(mismatches)
    return None
