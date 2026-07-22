"""Workflow command handler for the T660-2 desktop widget."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from control_app.config_loader import ConfigInventory, REPO_ROOT, load_config_inventory
from control_app.devices.t660_service import T660Service
from control_app.ui.contracts import WorkflowCommand, WorkflowResult
from control_app.workflows.timing_recipe_manager import TimingRecipeManager


T6602_UI_RATE = "2MHz"
T6602_UI_WIDTH = "150ns"
T6602_UI_CHA_DELAY = 0
T6602_UI_CHB_DELAY = "5ms"


class T660WidgetCommandHandler:
    """Stateful command handler for fixed-purpose T660-2 controls."""

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
        """Handle one T660-2 widget command."""

        if command.device_key != "t660_2":
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
                    data={"command_log": str(log_path), "config_hash": self.inventory.config_hash},
                )

    def _handle(self, command: WorkflowCommand, command_log: TextIO) -> WorkflowResult:
        name = command.command
        if name == "t660_2.refresh_status":
            readback = self._read_t6602(command_log)
            return self._complete(
                "T660-2 status refreshed",
                command_log,
                readback=readback,
            )
        if name == "t660_2.safe_idle":
            readback = self._apply_recipe(
                command_log,
                REPO_ROOT / "recipes" / "safe_idle.yaml",
                "safe_idle_readback.json",
            )
            return self._complete("T660 safe idle applied", command_log, readback=readback)
        if name == "t660_2.apply_manual_cha":
            source = str(command.parameters.get("trigger_source", "SYN")).strip().upper()
            if source != "SYN":
                return WorkflowResult(
                    status="blocked",
                    message="Apply + Start CHA Only requires trigger source SYN. Use Safe Idle to stop CHA.",
                )
            frequency = str(command.parameters.get("frequency", "")).strip()
            delay = str(command.parameters.get("cha_delay", "")).strip()
            width = str(command.parameters.get("cha_width", "")).strip()
            if not frequency or not delay or not width:
                return WorkflowResult(
                    status="blocked",
                    message="Synth frequency, CHA delay, and CHA width are required.",
                )
            readback = self._apply_recipe(
                command_log,
                _manual_cha_recipe(frequency=frequency, delay=delay, width=width),
                "t6602_manual_cha_readback.json",
            )
            return self._complete(
                f"T660-2 CHA started: SYN, {frequency}, delay {delay}, width {width}; all other outputs are off",
                command_log,
                readback=readback,
            )
        if name == "t660_2.start_cha":
            readback = self._apply_recipe(
                command_log,
                _fixed_recipe(enable_cha=True, enable_chb=False),
                "t6602_cha_2mhz_150ns_readback.json",
            )
            return self._complete("T660-2 CHA started at 2 MHz / 150 ns", command_log, readback=readback)
        if name == "t660_2.start_chb":
            if not command.safety_approval:
                return WorkflowResult(
                    status="blocked",
                    message="Safety approval is required before enabling T660-2 CHB to MIRcat TRIG IN.",
                    data={"state": self._state_from_readback(self._read_t6602(command_log))},
                )
            readback = self._apply_recipe(
                command_log,
                _fixed_recipe(enable_cha=False, enable_chb=True),
                "t6602_chb_2mhz_150ns_delay_5ms_readback.json",
            )
            return self._complete(
                "T660-2 CHB started at 2 MHz / 150 ns with 5 ms delay",
                command_log,
                readback=readback,
            )
        if name == "t660_2.start_cha_chb":
            if not command.safety_approval:
                return WorkflowResult(
                    status="blocked",
                    message="Safety approval is required before enabling T660-2 CHB to MIRcat TRIG IN.",
                    data={"state": self._state_from_readback(self._read_t6602(command_log))},
                )
            readback = self._apply_recipe(
                command_log,
                _fixed_recipe(enable_cha=True, enable_chb=True),
                "t6602_cha_chb_2mhz_150ns_delay_5ms_readback.json",
            )
            return self._complete(
                "T660-2 CHA and CHB started; CHB delay set to 5 ms",
                command_log,
                readback=readback,
            )
        return WorkflowResult(status="blocked", message=f"Unsupported command {name}")

    def _apply_recipe(
        self,
        command_log: TextIO,
        recipe: str | Path | dict[str, Any],
        output_name: str,
    ) -> dict[str, Any]:
        manager = TimingRecipeManager(self.inventory, command_log=command_log)
        output_path = self._run_dir() / output_name
        return manager.apply_recipe(recipe, output_path=output_path)

    def _read_t6602(self, command_log: TextIO) -> dict[str, Any]:
        service = T660Service.from_config(
            "t660_2",
            config_path=self.config_path,
            command_log=command_log,
        )
        try:
            service.connect()
            service.identify()
            return {
                "recipe_name": "t660_2_direct_readback",
                "devices": {"t660_2": service.read_active_settings()},
                "matches_recipe": None,
                "mismatches": [],
            }
        finally:
            service.close()

    def _complete(
        self,
        message: str,
        command_log: TextIO,
        *,
        readback: dict[str, Any],
    ) -> WorkflowResult:
        state = self._state_from_readback(readback)
        return WorkflowResult(
            status="complete",
            message=message,
            data={
                "state": state,
                "readback": readback,
                "command_log": str(self._command_log_path()),
                "config_hash": self.inventory.config_hash,
            },
        )

    def _state_from_readback(self, readback: dict[str, Any]) -> dict[str, Any]:
        device = (readback.get("devices") or {}).get("t660_2", {})
        queries = device.get("queries") or {}
        channels = device.get("channels") or {}
        state: dict[str, Any] = {
            "timestamp": device.get("timestamp_utc"),
            "identity": _response(queries.get("identity")),
            "trigger_source": _response(queries.get("trigger_source")),
            "synth_frequency": _response(queries.get("synth_frequency")),
            "shots": _response(queries.get("shots")),
            "matches_recipe": readback.get("matches_recipe"),
            "last_error": _readback_errors(readback),
        }
        for channel in ("A", "B", "C", "D"):
            settings = channels.get(channel) or {}
            prefix = f"channel_{channel.lower()}"
            state[f"{prefix}_enabled"] = _response(settings.get("enabled"))
            state[f"{prefix}_mode"] = _response(settings.get("timing_mode"))
            state[f"{prefix}_termination"] = _response(settings.get("termination"))
            state[f"{prefix}_delay"] = _response(settings.get("delay_edge"))
            state[f"{prefix}_width"] = _response(settings.get("width_edge"))
        return state

    def _run_dir(self) -> Path:
        path = REPO_ROOT / "runs" / f"{datetime.now().strftime('%Y%m%d')}_t6602_ui"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _command_log_path(self) -> Path:
        return REPO_ROOT / "logs" / f"{datetime.now().strftime('%Y%m%d')}_t660_ui_command_log.txt"


def _fixed_recipe(*, enable_cha: bool, enable_chb: bool) -> dict[str, Any]:
    return {
        "name": "t6602_ui_fixed_2mhz_150ns",
        "description": "Fixed T660-2 UI recipe: 2 MHz / 150 ns on CHA and/or CHB.",
        "approved_laser_safety_condition": enable_chb,
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
                "clock": {
                    "frequency": T6602_UI_RATE,
                    "shots": 0,
                },
                "trigger_source": "SYN",
                "force_eod": True,
                "start": True,
                "signals": {
                    "hf2li_extref": {
                        "delay": T6602_UI_CHA_DELAY,
                        "width": T6602_UI_WIDTH,
                        "polarity": "positive",
                        "termination": "50OHM",
                        "enabled": enable_cha,
                    },
                    "mircat_trig_in": {
                        "delay": T6602_UI_CHB_DELAY,
                        "width": T6602_UI_WIDTH,
                        "polarity": "positive",
                        "termination": "50OHM",
                        "enabled": enable_chb,
                    },
                    "hf2li_daq_trigger": {"enabled": False},
                    "t660_1_trig_in": {"enabled": False},
                },
            },
        },
    }


def _manual_cha_recipe(*, frequency: str, delay: str, width: str) -> dict[str, Any]:
    """Laser-safe manual reference recipe: only T660-2 CHA may be active."""

    recipe = _fixed_recipe(enable_cha=True, enable_chb=False)
    t660_2 = recipe["t660"]["t660_2"]
    t660_2["clock"]["frequency"] = frequency
    t660_2["signals"]["hf2li_extref"]["delay"] = delay
    t660_2["signals"]["hf2li_extref"]["width"] = width
    recipe["name"] = "t6602_ui_manual_cha_reference"
    recipe["description"] = "Manual, CHA-only reference diagnostic; all laser-driving channels are disabled."
    return recipe


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
