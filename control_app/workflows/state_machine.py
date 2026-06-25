"""Add-only workflow state machine for UI-dispatched hardware commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO
import json

import yaml

from control_app.config_loader import ConfigInventory, REPO_ROOT, load_config_inventory
from control_app.devices.arduino_mux_service import ArduinoMuxService
from control_app.devices.hf2li_service import HF2LIPreset, HF2LIService
from control_app.devices.mircat_service import MircatService
from control_app.devices.picoscope_service import PicoScopeService
from control_app.ui.contracts import WorkflowCommand, WorkflowResult
from control_app.workflows.mircat_widget_commands import (
    MIRCAT_WAVENUMBER_MAX_CM1,
    MIRCAT_WAVENUMBER_MIN_CM1,
    MircatWidgetCommandHandler,
)
from control_app.workflows.mux_widget_commands import MuxWidgetCommandHandler
from control_app.workflows.picoscope_settings_test import (
    capture_settings_from_recipe,
    load_recipe as load_picoscope_recipe,
    validate_capture_settings,
)
from control_app.workflows.t660_widget_commands import T660WidgetCommandHandler
from control_app.workflows.timing_recipe_manager import TimingRecipeManager


REQUIRED_WORKFLOW_COMMANDS = (
    "startup_check",
    "safe_shutdown",
    "route_scope_signal",
    "program_timing_recipe",
    "arm_measurement",
    "acquire_point",
    "acquire_scan",
    "abort_to_safe",
)
WORKFLOW_DEVICE_KEYS = ("mircat", "t660", "t660_2", "picoscope", "arduino_mux", "hf2li")
INITIAL_STATE = "SAFE_IDLE"
HARDWARE_REQUIRED_STATES = {
    "SAFE_SHUTDOWN_SENT",
    "SCOPE_ROUTE_APPLIED",
    "TIMING_RECIPE_PROGRAMMED",
    "MEASUREMENT_ARMED",
    "ACQUIRING_POINT",
    "ACQUIRING_SCAN",
}


class WorkflowStateMachineError(RuntimeError):
    """Raised when workflow construction or validation fails."""


@dataclass(frozen=True)
class WorkflowEvent:
    """One state-machine command event."""

    timestamp_utc: str
    command: str
    from_state: str
    to_state: str
    status: str
    message: str
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable event dictionary."""

        return {
            "timestamp_utc": self.timestamp_utc,
            "command": self.command,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "status": self.status,
            "message": self.message,
            "data": self.data,
        }


class WorkflowStateMachine:
    """Route UI commands through explicit workflow states before services."""

    def __init__(
        self,
        *,
        operator: str,
        inventory: ConfigInventory | None = None,
        config_path: str | Path | None = None,
        command_log: TextIO | None = None,
        hardware_access: bool = True,
        hardware_blocker: str | None = None,
        run_dir: str | Path | None = None,
    ) -> None:
        self.operator = operator
        self.inventory = inventory or load_config_inventory(config_path, write_files=False)
        self.config_path = Path(self.inventory.config_path)
        self.command_log = command_log
        self.hardware_access = hardware_access
        self.hardware_blocker = hardware_blocker or (
            "Real hardware execution is not enabled for this workflow state-machine run."
        )
        self.state = INITIAL_STATE
        self.recipe: dict[str, Any] | None = None
        self.recipe_path: Path | None = None
        self.recipe_validation: dict[str, Any] = {}
        self.events: list[WorkflowEvent] = []
        self.blockers: list[str] = []
        self.abort_state: dict[str, Any] = {"aborted": False, "reason": None}
        self._mircat_handler: MircatWidgetCommandHandler | None = None
        self._mux_handler: MuxWidgetCommandHandler | None = None
        self._t660_handler: T660WidgetCommandHandler | None = None
        self.run_dir = self._resolve_run_dir(run_dir)
        self.raw_data_paths: list[str] = []
        self.command_log_paths: list[str] = []
        self.device_readback_paths: list[str] = []
        self.mux_routes: dict[str, Any] = {}
        self.picoscope_settings: dict[str, Any] = {}
        self.mircat_setpoint: dict[str, Any] | None = None
        self.mircat_actual_wavelength: dict[str, Any] | None = None
        self.hf2li_settings_snapshot: dict[str, Any] = {}
        self._arduino_mux_service: ArduinoMuxService | None = None
        self._picoscope_service: PicoScopeService | None = None
        self._picoscope_capture_settings: dict[str, Any] | None = None
        self._mircat_service: MircatService | None = None
        self._hf2li_service: HF2LIService | None = None
        self._hf2li_preset: HF2LIPreset | None = None
        if command_log is not None and getattr(command_log, "name", None):
            self._remember_command_log(str(command_log.name))

    def __call__(self, command: WorkflowCommand) -> WorkflowResult:
        """Handle one UI command through the workflow state machine."""

        name = _normalize_command(command.command)
        if name in REQUIRED_WORKFLOW_COMMANDS:
            return self._handle_workflow_command(name, command)
        if command.device_key in WORKFLOW_DEVICE_KEYS:
            return self._handle_device_command(command)
        result = WorkflowResult(
            status="blocked",
            message=f"Unsupported workflow command {command.command!r}",
            data={"state": self.state, "config_hash": self.inventory.config_hash},
        )
        self._record(name, self.state, "blocked", result.message, result.data)
        return result

    def export_event_log(self, path: str | Path) -> Path:
        """Write state-machine events as JSON."""

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps([event.to_dict() for event in self.events], indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        return target

    def artifact_summary(self) -> dict[str, Any]:
        """Return artifact paths and manifest fields produced by real delegates."""

        return {
            "run_dir": str(self.run_dir),
            "raw_data_paths": list(dict.fromkeys(self.raw_data_paths)),
            "command_log_paths": list(dict.fromkeys(self.command_log_paths)),
            "device_readback_paths": list(dict.fromkeys(self.device_readback_paths)),
            "mux_routes": self.mux_routes,
            "picoscope_settings": self.picoscope_settings,
            "mircat_setpoint": self.mircat_setpoint,
            "mircat_actual_wavelength": self.mircat_actual_wavelength,
            "hf2li_settings_snapshot": self.hf2li_settings_snapshot,
        }

    def _resolve_run_dir(self, run_dir: str | Path | None) -> Path:
        if run_dir is None:
            target = REPO_ROOT / "runs" / f"{datetime.now().strftime('%Y%m%d')}_workflow_state_machine"
        else:
            target = Path(run_dir)
            if not target.is_absolute():
                target = REPO_ROOT / target
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _artifact_path(self, filename: str) -> Path:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        return self.run_dir / filename

    def _write_readback(self, filename: str, data: Any) -> Path:
        path = self._artifact_path(filename)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._remember_readback(path)
        return path

    def _remember_raw(self, path: str | Path) -> None:
        text = str(path)
        if text not in self.raw_data_paths:
            self.raw_data_paths.append(text)

    def _remember_readback(self, path: str | Path) -> None:
        text = str(path)
        if text not in self.device_readback_paths:
            self.device_readback_paths.append(text)

    def _remember_command_log(self, path: str | Path) -> None:
        text = str(path)
        if text not in self.command_log_paths:
            self.command_log_paths.append(text)

    def _handle_workflow_command(
        self, name: str, command: WorkflowCommand
    ) -> WorkflowResult:
        handlers = {
            "startup_check": self._startup_check,
            "safe_shutdown": self._safe_shutdown,
            "route_scope_signal": self._route_scope_signal,
            "program_timing_recipe": self._program_timing_recipe,
            "arm_measurement": self._arm_measurement,
            "acquire_point": self._acquire_point,
            "acquire_scan": self._acquire_scan,
            "abort_to_safe": self._abort_to_safe,
        }
        try:
            return handlers[name](command)
        except Exception as exc:  # noqa: BLE001 - workflow boundary records exact blocker
            message = f"{type(exc).__name__}: {exc}"
            self.blockers.append(message)
            data = {
                "state": self.state,
                "config_hash": self.inventory.config_hash,
                "command": command.to_dict(),
            }
            self._record(name, self.state, "failed", message, data)
            return WorkflowResult(status="failed", message=message, data=data)

    def _handle_device_command(self, command: WorkflowCommand) -> WorkflowResult:
        if not self.hardware_access:
            message = (
                f"{command.device_key} command {command.command!r} was not sent: "
                f"{self.hardware_blocker}"
            )
            self.blockers.append(message)
            result = WorkflowResult(
                status="blocked",
                message=message,
                data={
                    "state": self.state,
                    "config_hash": self.inventory.config_hash,
                    "command_path": _command_path(command.device_key),
                },
            )
            self._record(command.command, self.state, "blocked", message, result.data)
            return result

        if command.device_key == "mircat":
            if self._mircat_handler is None:
                self._mircat_handler = MircatWidgetCommandHandler(operator=self.operator)
            result = self._mircat_handler(command)
        elif command.device_key == "arduino_mux":
            if self._mux_handler is None:
                self._mux_handler = MuxWidgetCommandHandler(
                    operator=self.operator,
                    inventory=self.inventory,
                )
            result = self._mux_handler(command)
        elif command.device_key == "t660_2":
            if self._t660_handler is None:
                self._t660_handler = T660WidgetCommandHandler(
                    operator=self.operator,
                    inventory=self.inventory,
                )
            result = self._t660_handler(command)
        else:
            message = (
                f"{command.device_key} direct widget command namespace is not exposed; "
                "use the add-only workflow commands."
            )
            result = WorkflowResult(
                status="blocked",
                message=message,
                data={
                    "state": self.state,
                    "config_hash": self.inventory.config_hash,
                    "command_path": _command_path(command.device_key),
                },
            )
        self._record(command.command, self.state, result.status, result.message, result.data)
        return result

    def _startup_check(self, command: WorkflowCommand) -> WorkflowResult:
        self._load_recipe(command.parameters.get("recipe_path"))
        missing = [
            key for key in WORKFLOW_DEVICE_KEYS if key != "t660" and key not in self.inventory.devices
        ]
        if not self.inventory.t660_devices:
            missing.append("t660")
        if missing:
            raise WorkflowStateMachineError(
                "hardware_configuration.yaml is missing devices: " + ", ".join(sorted(missing))
            )
        data = {
            "state": "STARTUP_CHECKED",
            "config_hash": self.inventory.config_hash,
            "config_path": self.inventory.config_path,
            "recipe_path": str(self.recipe_path) if self.recipe_path else None,
            "required_commands": list(REQUIRED_WORKFLOW_COMMANDS),
            "command_paths": {key: _command_path(key) for key in WORKFLOW_DEVICE_KEYS},
            "hardware_access": self.hardware_access,
        }
        return self._complete(
            command.command,
            "STARTUP_CHECKED",
            "Startup configuration and recipe checks passed.",
            data,
        )

    def _safe_shutdown(self, command: WorkflowCommand) -> WorkflowResult:
        if not self.hardware_access:
            return self._blocked_hardware(
                command.command,
                "SAFE_SHUTDOWN_VALIDATED",
                "Safe-shutdown command sequence was constructed, but no real hardware command was sent.",
                {
                    "required_safe_actions": [
                        "MIRcat emission off",
                        "MIRcat disarm/deinitialize if connected",
                        "T660 safe_idle recipe",
                        "Arduino MUX safe idle",
                        "HF2LI unsubscribe/stop acquisition if active",
                        "PicoScope stop/close if active",
                    ],
                },
            )
        safe_actions = self._send_safe_actions("safe_shutdown")
        return self._complete(
            command.command,
            "SAFE_SHUTDOWN_SENT",
            "Safe-shutdown commands were sent to real hardware services and readbacks were recorded.",
            {
                "state": "SAFE_SHUTDOWN_SENT",
                "config_hash": self.inventory.config_hash,
                "hardware_action_sent": True,
                "safe_actions": safe_actions,
            },
        )

    def _route_scope_signal(self, command: WorkflowCommand) -> WorkflowResult:
        recipe = self._require_recipe()
        routes = _recipe_routes(recipe, self.inventory)
        for output_key, route_name in routes.items():
            route_config = self.inventory.mux_routes.get(route_name)
            expected_output = output_key.removesuffix("_route")
            if not isinstance(route_config, dict):
                raise WorkflowStateMachineError(
                    f"MUX route {route_name!r} is not defined in hardware_configuration.yaml"
                )
            if route_config.get("mux_output") != expected_output:
                raise WorkflowStateMachineError(
                    f"MUX route {route_name!r} is configured for "
                    f"{route_config.get('mux_output')!r}, not {expected_output!r}"
                )
        pico_recipe_path = recipe.get("picoscope_recipe") or recipe.get("pico_capture_recipe")
        pico_settings = self._validate_picoscope_recipe(pico_recipe_path)
        data = {
            "state": "SCOPE_ROUTE_VALIDATED",
            "config_hash": self.inventory.config_hash,
            "mux_routes": routes,
            "picoscope_settings": pico_settings,
            "picoscope_independent_of_arduino_mux": True,
        }
        if not self.hardware_access:
            return self._blocked_hardware(
                command.command,
                "SCOPE_ROUTE_VALIDATED",
                "Arduino MUX route and PicoScope settings construction were validated; no hardware command was sent.",
                data,
            )

        mux_readback = self._apply_arduino_mux_routes(routes)
        picoscope_readback = self._apply_picoscope_settings(pico_settings)
        self.mux_routes = {
            "requested_routes": mux_readback["requested_routes"],
            "route_responses": mux_readback["route_responses"],
            "route_readback": mux_readback["route_readback"],
        }
        self.picoscope_settings = picoscope_readback
        data.update(
            {
                "state": "SCOPE_ROUTE_APPLIED",
                "hardware_action_sent": True,
                "mux_readback": mux_readback,
                "picoscope_settings": picoscope_readback,
            }
        )
        return self._complete(
            command.command,
            "SCOPE_ROUTE_APPLIED",
            "Arduino MUX routes and PicoScope settings were applied through independent real device services.",
            data,
        )

    def _program_timing_recipe(self, command: WorkflowCommand) -> WorkflowResult:
        recipe = self._require_recipe()
        timing_recipe = command.parameters.get("timing_recipe") or recipe.get("timing_recipe")
        if not timing_recipe:
            raise WorkflowStateMachineError("Myoglobin-CO recipe does not define timing_recipe")
        manager = TimingRecipeManager(self.inventory)
        validation = manager.validate_recipe(REPO_ROOT / str(timing_recipe))
        self.recipe_validation["timing_recipe"] = validation
        data = {
            "state": "TIMING_RECIPE_VALIDATED",
            "config_hash": self.inventory.config_hash,
            "timing_recipe": str(timing_recipe),
            "timing_validation": validation,
        }
        if not self.hardware_access:
            return self._blocked_hardware(
                command.command,
                "TIMING_RECIPE_VALIDATED",
                "Timing recipe resolved and passed safety validation; no T660 command was sent.",
                data,
            )

        manager = TimingRecipeManager(self.inventory, command_log=self.command_log)
        readback_path = self._artifact_path(f"day7_{Path(str(timing_recipe)).stem}_readback.json")
        readback = manager.apply_recipe(REPO_ROOT / str(timing_recipe), output_path=readback_path)
        self._remember_readback(readback_path)
        data.update(
            {
                "state": "TIMING_RECIPE_PROGRAMMED",
                "hardware_action_sent": True,
                "timing_readback_path": str(readback_path),
                "timing_readback": readback,
            }
        )
        return self._complete(
            command.command,
            "TIMING_RECIPE_PROGRAMMED",
            "Timing recipe was programmed on real T660 hardware and readback matched the recipe.",
            data,
        )

    def _arm_measurement(self, command: WorkflowCommand) -> WorkflowResult:
        recipe = self._require_recipe()
        self._validate_mircat_request(recipe)
        hf2li_preset = self._validate_hf2li_preset(recipe.get("hf2li_preset"))
        data = {
            "state": "MEASUREMENT_ARM_VALIDATED",
            "config_hash": self.inventory.config_hash,
            "mircat_setpoint": _mircat_setpoint(recipe),
            "mircat_parameter_change": {
                "validated": True,
                "hardware_action_sent": False,
            },
            "hf2li_preset": hf2li_preset,
            "laser_safety_approved": bool(recipe.get("approved_laser_safety_condition")),
        }
        if not self.hardware_access:
            return self._blocked_hardware(
                command.command,
                "MEASUREMENT_ARM_VALIDATED",
                "MIRcat parameter change and measurement arm command were validated; MIRcat, HF2LI, T660, PicoScope, and pump hardware were not armed.",
                data,
            )

        mircat_readback = self._safe_tune_mircat(recipe)
        hf2li_readback = self._arm_hf2li(hf2li_preset)
        data.update(
            {
                "state": "MEASUREMENT_ARMED",
                "hardware_action_sent": True,
                "mircat_parameter_change": {
                    "validated": True,
                    "hardware_action_sent": True,
                    "emission_on": False,
                },
                "mircat_readback": mircat_readback,
                "hf2li_readback": hf2li_readback,
            }
        )
        return self._complete(
            command.command,
            "MEASUREMENT_ARMED",
            "MIRcat was tuned with emission off and HF2LI was configured with the Myoglobin-CO preset.",
            data,
        )

    def _acquire_point(self, command: WorkflowCommand) -> WorkflowResult:
        recipe = self._require_recipe()
        point = command.parameters.get("point") or _first_scan_point(recipe)
        data = {
            "state": "ACQUIRE_POINT_VALIDATED",
            "config_hash": self.inventory.config_hash,
            "point": point,
            "raw_data_created": False,
        }
        if not self.hardware_access:
            return self._blocked_hardware(
                command.command,
                "ACQUIRE_POINT_VALIDATED",
                "Acquire-point command was validated only; no detector or scope data were acquired.",
                data,
            )

        acquisition = self._acquire_hf2li_point(point, point_index=0, prefix="point")
        data.update(
            {
                "state": "ACQUIRING_POINT",
                "hardware_action_sent": True,
                "raw_data_created": True,
                "acquisition": acquisition,
            }
        )
        return self._complete(
            command.command,
            "ACQUIRING_POINT",
            "Acquire-point collected real HF2LI detector data for the selected Myoglobin-CO point.",
            data,
        )

    def _acquire_scan(self, command: WorkflowCommand) -> WorkflowResult:
        recipe = self._require_recipe()
        scan_points = _scan_points(recipe)
        data = {
            "state": "ACQUIRE_SCAN_VALIDATED",
            "config_hash": self.inventory.config_hash,
            "planned_point_count": len(scan_points),
            "first_point": scan_points[0] if scan_points else None,
            "last_point": scan_points[-1] if scan_points else None,
            "raw_data_created": False,
        }
        if not self.hardware_access:
            return self._blocked_hardware(
                command.command,
                "ACQUIRE_SCAN_VALIDATED",
                "Acquire-scan command was validated only; no detector data or PicoScope traces were created.",
                data,
            )

        acquisitions = [
            self._acquire_hf2li_point(point, point_index=index, prefix="scan")
            for index, point in enumerate(scan_points)
        ]
        data.update(
            {
                "state": "ACQUIRING_SCAN",
                "hardware_action_sent": True,
                "raw_data_created": True,
                "acquisitions": acquisitions,
            }
        )
        return self._complete(
            command.command,
            "ACQUIRING_SCAN",
            "Acquire-scan collected real HF2LI detector data for every Myoglobin-CO scan point.",
            data,
        )

    def _abort_to_safe(self, command: WorkflowCommand) -> WorkflowResult:
        reason = str(command.parameters.get("reason") or "Day 7 validation abort path")
        self.abort_state = {
            "aborted": True,
            "reason": reason,
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        data = {
            "state": "ABORT_LOGGED",
            "config_hash": self.inventory.config_hash,
            "abort_state": self.abort_state,
            "safe_actions_required": [
                "Stop acquisition",
                "MIRcat emission off",
                "T660 outputs off",
                "Arduino MUX safe idle",
            ],
        }
        if not self.hardware_access:
            return self._blocked_hardware(
                command.command,
                "ABORT_LOGGED",
                "Abort was logged; hardware safe actions were not sent in this pre-hardware validation run.",
                data,
            )

        safe_actions = self._send_safe_actions("abort_to_safe")
        data.update(
            {
                "state": "ABORT_LOGGED",
                "hardware_action_sent": True,
                "safe_actions": safe_actions,
            }
        )
        return self._complete(
            command.command,
            "ABORT_LOGGED",
            "Abort was logged and real safe-state commands were sent where services were active.",
            data,
        )

    def _apply_arduino_mux_routes(self, routes: dict[str, str]) -> dict[str, Any]:
        service = self._arduino_mux_service
        if service is None:
            service = ArduinoMuxService.from_config(
                config_path=self.config_path,
                command_log=self.command_log,
            )
            service.connect()
            self._arduino_mux_service = service

        requested_routes = {
            "output_a": routes["output_a_route"],
            "output_b": routes["output_b_route"],
            "output_ext": routes["output_ext_route"],
        }
        identity = service.identify()
        firmware_version = service.get_version()
        protocol_version = service.get_protocol_version()
        status_before = service.get_status()
        route_responses = {
            "output_a": service.set_output_a_route(requested_routes["output_a"]),
            "output_b": service.set_output_b_route(requested_routes["output_b"]),
            "output_ext": service.set_output_ext_route(requested_routes["output_ext"]),
        }
        for output, response in route_responses.items():
            _assert_ok_route_response(output, response)
        route_readback = service.query_active_route()
        _assert_latched_routes(route_readback, requested_routes)
        status_after = service.get_status()
        readback = {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "config_hash": self.inventory.config_hash,
            "identity": identity,
            "firmware_version": firmware_version,
            "protocol_version": protocol_version,
            "status_before_routes": status_before,
            "requested_routes": requested_routes,
            "route_responses": route_responses,
            "route_readback": route_readback,
            "status_after_routes": status_after,
        }
        self._write_readback("day7_arduino_mux_route_readback.json", readback)
        return readback

    def _apply_picoscope_settings(self, picoscope_recipe: dict[str, Any]) -> dict[str, Any]:
        settings = picoscope_recipe["settings"]
        self._picoscope_capture_settings = dict(settings)
        device_config = self.inventory.devices.get("picoscope")
        if not isinstance(device_config, dict):
            raise WorkflowStateMachineError("picoscope missing from hardware_configuration.yaml")
        service = PicoScopeService(device_config, settings, command_log=self.command_log)
        self._picoscope_service = service
        try:
            service.open_unit()
            service.apply_capture_settings()
            timing_validation = service.validate_sample_timing()
            service.stop()
        finally:
            service.close_unit()
            self._picoscope_service = None

        readback = {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "config_hash": self.inventory.config_hash,
            "recipe_path": picoscope_recipe["recipe_path"],
            "settings": settings,
            "sample_timing_validation": timing_validation,
            "picoscope_model": device_config.get("model"),
            "picoscope_serial": device_config.get("serial_number"),
        }
        self._write_readback("day7_picoscope_settings_readback.json", readback)
        return readback

    def _safe_tune_mircat(self, recipe: dict[str, Any]) -> dict[str, Any]:
        setpoint = _mircat_setpoint(recipe)
        probe = recipe.get("probe") if isinstance(recipe.get("probe"), dict) else {}
        mircat = probe.get("mircat") if isinstance(probe.get("mircat"), dict) else {}
        qcl = int(setpoint["qcl"])
        service = self._mircat_service
        if service is None:
            device_config = self.inventory.devices.get("mircat")
            if not isinstance(device_config, dict):
                raise WorkflowStateMachineError("mircat missing from hardware_configuration.yaml")
            service = MircatService(device_config, command_log=self.command_log)
            service.initialize()
            self._mircat_service = service

        state_before = service.read_state().to_dict()
        if not service.is_interlock_set():
            raise WorkflowStateMachineError("MIRcat interlock is not set")
        if not service.is_key_switch_set():
            raise WorkflowStateMachineError("MIRcat key switch is not set")
        service.arm()
        pulse_settings = service.set_qcl_pulse_params(
            qcl=qcl,
            pulse_rate_hz=float(mircat.get("pulse_rate_hz", 100000.0)),
            pulse_width_ns=float(mircat.get("pulse_width_ns", 500.0)),
        )
        if not service.wait_for_tecs_ready(
            timeout_s=float(mircat.get("tec_timeout_s", 120.0)),
            poll_interval_s=float(mircat.get("poll_interval_s", 0.5)),
        ):
            raise WorkflowStateMachineError("MIRcat TECs did not reach set temperature before timeout")
        service.tune_to_wavenumber(float(setpoint["wavenumber_cm1"]), qcl=qcl)
        if not service.wait_for_tuned(
            timeout_s=float(mircat.get("tune_timeout_s", 120.0)),
            poll_interval_s=float(mircat.get("poll_interval_s", 0.5)),
        ):
            raise WorkflowStateMachineError("MIRcat did not report tuned before timeout")
        service.turn_emission_off()
        actual = service.get_actual_wavelength()
        state_after = service.read_state().to_dict()
        self.mircat_setpoint = setpoint
        self.mircat_actual_wavelength = actual
        readback = {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "config_hash": self.inventory.config_hash,
            "setpoint": setpoint,
            "actual_wavelength": actual,
            "pulse_settings": pulse_settings,
            "emission_on": False,
            "state_before": state_before,
            "state_after": state_after,
        }
        self._write_readback("day7_mircat_arm_readback.json", readback)
        return readback

    def _arm_hf2li(self, preset_name: str) -> dict[str, Any]:
        if self._hf2li_service is None:
            self._hf2li_service = HF2LIService.from_config(
                config_path=self.config_path,
                command_log=self.command_log,
            )
            self._hf2li_service.connect()
        service = self._hf2li_service
        preset = service.load_preset(preset_name)
        applied = service.apply_preset(preset)
        snapshot_path = self._artifact_path("day7_hf2li_arm_settings_snapshot.json")
        snapshot = service.export_settings_snapshot(snapshot_path, preset=preset)
        self._remember_readback(snapshot_path)
        self._hf2li_preset = preset
        self.hf2li_settings_snapshot = {
            "preset": preset_name,
            "settings_snapshot_path": str(snapshot_path),
            "applied": applied,
            "read_errors": snapshot.get("read_errors", {}),
        }
        return dict(self.hf2li_settings_snapshot)

    def _acquire_hf2li_point(
        self,
        point: dict[str, Any],
        *,
        point_index: int,
        prefix: str,
    ) -> dict[str, Any]:
        if self._hf2li_service is None or self._hf2li_preset is None:
            raise WorkflowStateMachineError("arm_measurement must complete before acquisition")
        service = self._hf2li_service
        preset = self._hf2li_preset
        acquisition = preset.settings.get("acquisition") or {}
        duration_s = float(acquisition.get("duration_s", 5.0))
        demodulators = acquisition.get("demodulators") or [0, 3]
        fields = acquisition.get("fields") or ["x", "y", "r"]
        slug = _point_slug(point, point_index)
        raw_csv = self._artifact_path(f"hf2li_raw_{prefix}_{slug}.csv")
        summary_csv = self._artifact_path(f"hf2li_summary_{prefix}_{slug}.csv")
        record = service.acquire_record(
            duration_s=duration_s,
            demodulators=demodulators,
            fields=fields,
        )
        save_summary = service.save_record(
            record,
            raw_csv_path=raw_csv,
            summary_csv_path=summary_csv,
        )
        metadata = {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "config_hash": self.inventory.config_hash,
            "point_index": point_index,
            "point": point,
            "preset": preset.name,
            "duration_s": duration_s,
            "demodulators": demodulators,
            "fields": fields,
            "raw_csv_path": str(raw_csv),
            "summary_csv_path": str(summary_csv),
            "save_summary": save_summary,
        }
        metadata_path = self._write_readback(f"hf2li_metadata_{prefix}_{slug}.json", metadata)
        self._remember_raw(raw_csv)
        self._remember_readback(summary_csv)
        metadata["metadata_path"] = str(metadata_path)
        return metadata

    def _send_safe_actions(self, label: str) -> dict[str, Any]:
        actions: dict[str, Any] = {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "config_hash": self.inventory.config_hash,
            "label": label,
            "mircat": None,
            "t660": None,
            "arduino_mux": None,
            "picoscope": None,
            "hf2li": None,
        }
        errors: list[str] = []

        if self._picoscope_service is not None:
            try:
                self._picoscope_service.stop()
                self._picoscope_service.close_unit()
                actions["picoscope"] = "stopped_and_closed"
            except Exception as exc:  # noqa: BLE001 - safe-state report records exact device failure
                errors.append(f"PicoScope safe stop failed: {exc}")
            finally:
                self._picoscope_service = None

        if self._hf2li_service is not None:
            try:
                self._hf2li_service.close()
                actions["hf2li"] = "closed"
            except Exception as exc:  # noqa: BLE001
                errors.append(f"HF2LI close failed: {exc}")
            finally:
                self._hf2li_service = None
                self._hf2li_preset = None

        if self._mircat_service is not None:
            try:
                self._mircat_service.stop_scan_if_needed()
                self._mircat_service.turn_emission_off()
                self._mircat_service.disarm()
                state = self._mircat_service.read_state().to_dict()
                self._mircat_service.deinitialize()
                actions["mircat"] = {"safe_state": "emission_off_disarmed_deinitialized", "state": state}
            except Exception as exc:  # noqa: BLE001
                errors.append(f"MIRcat safe shutdown failed: {exc}")
            finally:
                self._mircat_service = None

        try:
            manager = TimingRecipeManager(self.inventory, command_log=self.command_log)
            output_path = self._artifact_path(f"day7_{label}_safe_idle_readback.json")
            actions["t660"] = manager.apply_recipe(REPO_ROOT / "recipes" / "safe_idle.yaml", output_path=output_path)
            self._remember_readback(output_path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"T660 safe_idle failed: {exc}")

        mux_service = self._arduino_mux_service
        try:
            if mux_service is None:
                mux_service = ArduinoMuxService.from_config(
                    config_path=self.config_path,
                    command_log=self.command_log,
                )
                mux_service.connect()
            response = mux_service.safe_idle()
            actions["arduino_mux"] = {"safe_idle_response": response}
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Arduino MUX safe idle failed: {exc}")
        finally:
            if mux_service is not None:
                try:
                    mux_service.close()
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"Arduino MUX close failed: {exc}")
            self._arduino_mux_service = None

        readback_path = self._write_readback(f"day7_{label}_safe_actions.json", actions)
        actions["readback_path"] = str(readback_path)
        if errors:
            raise WorkflowStateMachineError("; ".join(errors))
        return actions

    def _load_recipe(self, recipe_path_value: Any) -> None:
        if self.recipe is not None:
            return
        recipe_path = Path(str(recipe_path_value or "recipes/myoglobin_co_acquisition.yaml"))
        if not recipe_path.is_absolute():
            recipe_path = REPO_ROOT / recipe_path
        if not recipe_path.exists():
            raise WorkflowStateMachineError(f"Myoglobin-CO recipe not found: {recipe_path}")
        with recipe_path.open("r", encoding="utf-8") as handle:
            recipe = yaml.safe_load(handle) or {}
        if not isinstance(recipe, dict):
            raise WorkflowStateMachineError(f"Myoglobin-CO recipe must be a mapping: {recipe_path}")
        self.recipe = recipe
        self.recipe_path = recipe_path
        self._validate_recipe_shape(recipe)

    def _require_recipe(self) -> dict[str, Any]:
        self._load_recipe(None)
        assert self.recipe is not None
        return self.recipe

    def _validate_recipe_shape(self, recipe: dict[str, Any]) -> None:
        required = {
            "probe",
            "pump",
            "delay_list_ns",
            "controls",
            "file_naming",
            "go_no_go_criteria",
            "hf2li_preset",
            "timing_recipe",
            "picoscope_recipe",
        }
        missing = sorted(key for key in required if key not in recipe)
        if missing:
            raise WorkflowStateMachineError(
                "Myoglobin-CO recipe missing required keys: " + ", ".join(missing)
            )
        if not isinstance(recipe.get("delay_list_ns"), list) or not recipe["delay_list_ns"]:
            raise WorkflowStateMachineError("Myoglobin-CO recipe delay_list_ns must be a nonempty list")
        if bool(recipe.get("approved_laser_safety_condition")):
            raise WorkflowStateMachineError(
                "Day 7 Myoglobin-CO recipe must remain non-emitting until operator approval is recorded"
            )

    def _validate_mircat_request(self, recipe: dict[str, Any]) -> None:
        setpoint = _mircat_setpoint(recipe)
        values = [float(setpoint["wavenumber_cm1"])]
        scan = setpoint.get("co_band_scan_cm1") or {}
        if isinstance(scan, dict):
            values.extend(float(scan[key]) for key in ("start", "stop") if key in scan)
        for value in values:
            if value < MIRCAT_WAVENUMBER_MIN_CM1 or value > MIRCAT_WAVENUMBER_MAX_CM1:
                raise WorkflowStateMachineError(
                    f"MIRcat wavenumber {value:g} cm^-1 is outside the installed range "
                    f"{MIRCAT_WAVENUMBER_MIN_CM1:g}-{MIRCAT_WAVENUMBER_MAX_CM1:g} cm^-1"
                )

    def _validate_hf2li_preset(self, preset_name: Any) -> str:
        if not preset_name:
            raise WorkflowStateMachineError("Myoglobin-CO recipe does not define hf2li_preset")
        presets_path = REPO_ROOT / "recipes" / "hf2li_presets.yaml"
        with presets_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        presets = data.get("presets") if isinstance(data, dict) else None
        if not isinstance(presets, dict) or str(preset_name) not in presets:
            raise WorkflowStateMachineError(
                f"HF2LI preset {preset_name!r} is not defined in {presets_path}"
            )
        return str(preset_name)

    def _validate_picoscope_recipe(self, recipe_path: Any) -> dict[str, Any]:
        if not recipe_path:
            raise WorkflowStateMachineError("Myoglobin-CO recipe does not define picoscope_recipe")
        recipe, resolved_path = load_picoscope_recipe(REPO_ROOT / str(recipe_path))
        settings = capture_settings_from_recipe(recipe)
        device_config = self.inventory.devices.get("picoscope")
        if not isinstance(device_config, dict):
            raise WorkflowStateMachineError("picoscope missing from hardware_configuration.yaml")
        validate_capture_settings(settings, device_config)
        return {"recipe_path": str(resolved_path), "settings": settings}

    def _complete(
        self,
        command_name: str,
        to_state: str,
        message: str,
        data: dict[str, Any],
    ) -> WorkflowResult:
        from_state = self.state
        self.state = to_state
        data = dict(data)
        data.setdefault("state", self.state)
        data.setdefault("config_hash", self.inventory.config_hash)
        self._record(command_name, from_state, "complete", message, data)
        return WorkflowResult(status="complete", message=message, data=data)

    def _blocked_hardware(
        self,
        command_name: str,
        to_state: str,
        message: str,
        data: dict[str, Any],
    ) -> WorkflowResult:
        from_state = self.state
        self.state = to_state
        hardware_message = f"{message} Blocker: {self.hardware_blocker}"
        data = dict(data)
        data.setdefault("state", self.state)
        data.setdefault("config_hash", self.inventory.config_hash)
        data["hardware_blocker"] = self.hardware_blocker
        data["hardware_action_sent"] = False
        if to_state in HARDWARE_REQUIRED_STATES or "not sent" in message.lower():
            self.blockers.append(hardware_message)
        self._record(command_name, from_state, "blocked", hardware_message, data)
        return WorkflowResult(status="blocked", message=hardware_message, data=data)

    def _record(
        self,
        command_name: str,
        from_state: str,
        status: str,
        message: str,
        data: dict[str, Any],
    ) -> None:
        event = WorkflowEvent(
            timestamp_utc=datetime.now(UTC).isoformat(timespec="seconds"),
            command=command_name,
            from_state=from_state,
            to_state=self.state,
            status=status,
            message=message,
            data=data,
        )
        self.events.append(event)
        if self.command_log is None:
            return
        self.command_log.write(
            f"{event.timestamp_utc} state_machine command={command_name} "
            f"status={status} from={from_state} to={self.state} message={message}\n"
        )
        self.command_log.flush()


def _normalize_command(command: str) -> str:
    value = str(command)
    return value.removeprefix("workflow.")


def _command_path(device_key: str) -> list[str]:
    return [
        "UI button",
        "WorkflowCommand",
        "WorkflowStateMachine",
        f"{device_key} DeviceAdapter/Service",
    ]


def _recipe_routes(recipe: dict[str, Any], inventory: ConfigInventory) -> dict[str, str]:
    configured = recipe.get("mux_checkpoint_routes")
    if isinstance(configured, dict):
        return {
            "output_a_route": str(configured.get("output_a_route") or ""),
            "output_b_route": str(configured.get("output_b_route") or ""),
            "output_ext_route": str(configured.get("output_ext_route") or ""),
        }
    diagnostic = inventory.mux_routes.get("diagnostic")
    if not isinstance(diagnostic, dict):
        raise WorkflowStateMachineError("mux_routes.diagnostic is not defined")
    return {
        "output_a_route": str(diagnostic.get("output_a_route") or ""),
        "output_b_route": str(diagnostic.get("output_b_route") or ""),
        "output_ext_route": str(diagnostic.get("output_ext_route") or ""),
    }


def _mircat_setpoint(recipe: dict[str, Any]) -> dict[str, Any]:
    probe = recipe.get("probe")
    if not isinstance(probe, dict):
        raise WorkflowStateMachineError("Myoglobin-CO recipe probe section must be a mapping")
    direct = probe.get("mircat")
    if isinstance(direct, dict):
        value = float(direct.get("wavenumber_cm1", 1858.0))
        qcl = int(direct.get("qcl", probe.get("qcl", 1)))
    else:
        value = float(probe.get("wavenumber_cm1", 1858.0))
        qcl = int(probe.get("qcl", 1))
    return {
        "wavenumber_cm1": value,
        "units": "cm^-1",
        "qcl": qcl,
        "co_band_scan_cm1": probe.get("co_band_scan_cm1"),
    }


def _scan_points(recipe: dict[str, Any]) -> list[dict[str, Any]]:
    probe = recipe.get("probe") or {}
    scan = probe.get("co_band_scan_cm1") if isinstance(probe, dict) else {}
    if not isinstance(scan, dict):
        return [_first_scan_point(recipe)]
    start = float(scan.get("start", _mircat_setpoint(recipe)["wavenumber_cm1"]))
    stop = float(scan.get("stop", start))
    step = abs(float(scan.get("step", 1.0)))
    if step <= 0:
        raise WorkflowStateMachineError("CO-band scan step must be positive")
    points: list[dict[str, Any]] = []
    direction = 1.0 if stop >= start else -1.0
    current = start
    while (direction > 0 and current <= stop + 1e-9) or (
        direction < 0 and current >= stop - 1e-9
    ):
        points.append(
            {
                "wavenumber_cm1": round(current, 6),
                "delay_ns": recipe["delay_list_ns"][0],
                "hf2li_preset": recipe.get("hf2li_preset"),
            }
        )
        current += direction * step
    return points


def _first_scan_point(recipe: dict[str, Any]) -> dict[str, Any]:
    return {
        "wavenumber_cm1": _mircat_setpoint(recipe)["wavenumber_cm1"],
        "delay_ns": recipe["delay_list_ns"][0],
        "hf2li_preset": recipe.get("hf2li_preset"),
    }


def _assert_ok_route_response(output: str, response: str | None) -> None:
    text = str(response or "")
    if not text:
        raise WorkflowStateMachineError(f"Arduino MUX {output} route command returned no response")
    upper = text.upper()
    if "ERROR" in upper:
        raise WorkflowStateMachineError(f"Arduino MUX {output} route command failed: {text}")
    if "OK ROUTE" not in upper:
        raise WorkflowStateMachineError(
            f"Arduino MUX {output} route command did not confirm OK ROUTE: {text}"
        )


def _assert_latched_routes(route_readback: dict[str, Any], requested: dict[str, str]) -> None:
    latched = route_readback.get("latched_routes") if isinstance(route_readback, dict) else None
    if not isinstance(latched, dict):
        raise WorkflowStateMachineError("Arduino MUX route readback did not include latched_routes")
    for output, route_name in requested.items():
        if latched.get(output) != route_name:
            raise WorkflowStateMachineError(
                f"Arduino MUX latched {output}={latched.get(output)!r}, expected {route_name!r}"
            )


def _point_slug(point: dict[str, Any], point_index: int) -> str:
    wavenumber = str(point.get("wavenumber_cm1", "unknown")).replace(".", "p").replace("-", "m")
    delay = str(point.get("delay_ns", "unknown")).replace(".", "p").replace("-", "m")
    return f"{point_index:03d}_wn_{wavenumber}_delay_{delay}ns"
