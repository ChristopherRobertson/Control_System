"""Generic workflow state machine for UI-dispatched hardware commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO
import json

import yaml

from control_app.config_loader import ConfigInventory, REPO_ROOT, load_config_inventory
from control_app.paths import RECIPE_ROOT, output_run_root, resolve_compat_path
from control_app.promoted_bundles import PromotedBundle, load_promoted_bundle
from control_app.devices.hf2li_service import HF2LIPreset, HF2LIService
from control_app.devices.mircat_service import RET_NOT_INITIALIZED, MircatService
from control_app.devices.picoscope_service import PicoScopeService
from control_app.ui.contracts import WorkflowCommand, WorkflowResult
from control_app.workflows.mircat_widget_commands import (
    MIRCAT_WAVENUMBER_MAX_CM1,
    MIRCAT_WAVENUMBER_MIN_CM1,
    MircatWidgetCommandHandler,
)
from control_app.workflows.iris_widget_commands import IrisWidgetCommandHandler
from control_app.workflows.ndyag_widget_commands import NdYagWidgetCommandHandler
from control_app.workflows.picoscope_settings_test import (
    capture_settings_from_recipe,
    load_recipe as load_picoscope_recipe,
    validate_capture_settings,
)
from control_app.workflows.t660_widget_commands import T660WidgetCommandHandler
from control_app.workflows.timing_recipe_manager import TimingRecipeManager
from control_app.workflows.selectable_workflows import (
    ConfiguredWorkflow,
    SelectableWorkflowError,
    configure_workflow,
    load_workflow_catalog,
)


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
WORKFLOW_DEVICE_KEYS = ("mircat", "t660", "t660_2", "picoscope", "hf2li")
DEVICE_COMMAND_KEYS = WORKFLOW_DEVICE_KEYS + ("ndyag", "opo_iris")
IRIS_MOTION_COMPATIBLE_ACTIVE_WORKFLOWS = frozenset({"ndyag_alignment_10hz"})
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
        bundle_id: str | None = None,
        bundle_root: str | Path | None = None,
    ) -> None:
        self.operator = operator
        self.inventory = inventory or load_config_inventory(config_path, write_files=False)
        self.config_path = Path(self.inventory.config_path)
        self.command_log = command_log
        self.hardware_access = hardware_access
        self.hardware_blocker = hardware_blocker or (
            "Real hardware execution is not enabled for this workflow state-machine run."
        )
        self.promoted_bundle: PromotedBundle | None = (
            load_promoted_bundle(bundle_id, bundle_root) if bundle_id else None
        )
        self.state = INITIAL_STATE
        self.recipe: dict[str, Any] | None = None
        self.recipe_path: Path | None = None
        self.recipe_validation: dict[str, Any] = {}
        self.events: list[WorkflowEvent] = []
        self.blockers: list[str] = []
        self.abort_state: dict[str, Any] = {"aborted": False, "reason": None}
        self._mircat_handler: MircatWidgetCommandHandler | None = None
        self._t660_handler: T660WidgetCommandHandler | None = None
        self._ndyag_handler: NdYagWidgetCommandHandler | None = None
        self._iris_handler: IrisWidgetCommandHandler | None = None
        self.iris_command_active = False
        self.run_dir = self._resolve_run_dir(run_dir)
        self.raw_data_paths: list[str] = []
        self.command_log_paths: list[str] = []
        self.device_readback_paths: list[str] = []
        self.mux_routes: dict[str, Any] = {}
        self.picoscope_settings: dict[str, Any] = {}
        self.mircat_setpoint: dict[str, Any] | None = None
        self.mircat_actual_wavelength: dict[str, Any] | None = None
        self.hf2li_settings_snapshot: dict[str, Any] = {}
        self._picoscope_service: PicoScopeService | None = None
        self._picoscope_capture_settings: dict[str, Any] | None = None
        self._mircat_service: MircatService | None = None
        self._hf2li_service: HF2LIService | None = None
        self._hf2li_preset: HF2LIPreset | None = None
        self._configured_ui_workflow: ConfiguredWorkflow | None = None
        self._active_ui_workflow: ConfiguredWorkflow | None = None
        self.phase_scan_active = False
        self.mircat_scan_active = False
        from threading import Event
        self.mircat_scan_cancel = Event()
        from control_app.workflows.phase_scan_runner import PhaseScanRunner
        from control_app.workflows.phase_scan_acquisition import LivePhaseScanAcquirer
        self.phase_scan_runner = PhaseScanRunner(
            (lambda: LivePhaseScanAcquirer(config_path=self.config_path,
                                          promoted_bundle=self.promoted_bundle)) if hardware_access else None
        )
        if command_log is not None and getattr(command_log, "name", None):
            self._remember_command_log(str(command_log.name))

    def __call__(self, command: WorkflowCommand) -> WorkflowResult:
        """Handle one UI command through the workflow state machine."""

        if self.mircat_scan_active and command.command != 'mircat.start_sweep_scan':
            return WorkflowResult(status="blocked", message="MIRcat Sweep Scan owns the instruments. Use Stop Scan first.")
        if self.phase_scan_active:
            return WorkflowResult(status="blocked", message="Phase Scan owns the instruments. Use Abort Scan first.")
        if self.iris_command_active:
            return WorkflowResult(
                status="blocked",
                message="The OPO iris owns instrument control until its command finishes.",
            )
        name = _normalize_command(command.command)
        if command.device_key == "workflow" and name == "configure_selected":
            return self._configure_selected_workflow(command)
        if command.device_key == "workflow" and name == "run_selected":
            return self._run_selected_workflow(command)
        if command.device_key == "workflow" and name == "stop_selected":
            return self._stop_selected_workflow()
        if name in REQUIRED_WORKFLOW_COMMANDS:
            return self._handle_workflow_command(name, command)
        if command.device_key in DEVICE_COMMAND_KEYS:
            return self._handle_device_command(command)
        result = WorkflowResult(
            status="blocked",
            message=f"Unsupported workflow command {command.command!r}",
            data={"state": self.state},
        )
        self._record(name, self.state, "blocked", result.message, result.data)
        return result

    def output_location_changed(self, selected: Path) -> None:
        """Start future UI artifacts in the selected folder; preserve previous runs."""
        self.run_dir = self._resolve_run_dir(selected / f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_workflow_state_machine")
        # Existing configured workflows point into their previous output folder.
        # Require Configure again rather than redirecting an existing run.
        self._configured_ui_workflow = None

    def _configure_selected_workflow(self, command: WorkflowCommand) -> WorkflowResult:
        """Validate and persist a complete UI workflow plan before Run is enabled."""

        if self._active_ui_workflow is not None:
            return WorkflowResult(
                status="blocked",
                message="Stop the active selected workflow before configuring another workflow.",
            )
        workflow_id = str(command.parameters.get("workflow_id", "")).strip()
        values = command.parameters.get("workflow_parameters")
        if not workflow_id or not isinstance(values, dict):
            return WorkflowResult(
                status="blocked",
                message="Select a workflow and provide its settings before configuring it.",
            )
        plan_dir = (
            output_run_root()
            / "configured_workflows"
            / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        )
        try:
            configured = configure_workflow(workflow_id, values, output_dir=plan_dir)
        except SelectableWorkflowError as exc:
            return WorkflowResult(status="blocked", message=str(exc))
        self._configured_ui_workflow = configured
        return WorkflowResult(
            status="complete",
            message=(
                f"{workflow_id} settings validated and saved. Run is enabled until a setting changes."
            ),
            data={
                "workflow_id": configured.workflow_id,
                "configured_workflow_path": str(configured.saved_path),
                "parameters": configured.parameters,
            },
        )

    def _run_selected_workflow(self, command: WorkflowCommand) -> WorkflowResult:
        """Run only the exact configuration most recently validated and saved."""

        configured = self._configured_ui_workflow
        workflow_id = str(command.parameters.get("workflow_id", ""))
        if configured is None or workflow_id != configured.workflow_id:
            return WorkflowResult(
                status="blocked",
                message="Workflow settings are not configured and saved. Configure & Save first.",
            )
        if configured.safety_approval_required and not command.safety_approval:
            return WorkflowResult(
                status="blocked",
                message="Safety approval is required before this configured workflow can run.",
            )
        delegated = WorkflowCommand(
            device_key=configured.device_key,
            command=configured.command,
            parameters=dict(configured.parameters),
            safety_approval=bool(command.safety_approval),
        )
        result = self._handle_device_command(delegated)
        if result.status == "complete" and configured.stop_command is not None:
            self._active_ui_workflow = configured
        result.data.setdefault("configured_workflow_path", str(configured.saved_path))
        result.data.setdefault("workflow_id", configured.workflow_id)
        return result

    def _stop_selected_workflow(self) -> WorkflowResult:
        """Invoke the configured workflow's established stop/safe-idle command."""

        configured = self._active_ui_workflow or self._configured_ui_workflow
        if configured is None or configured.stop_command is None:
            return WorkflowResult(
                status="blocked",
                message="The selected workflow has no configured stop action.",
            )
        result = self._handle_device_command(
            WorkflowCommand(
                device_key=configured.device_key,
                command=configured.stop_command,
            )
        )
        if result.status == "complete":
            self._active_ui_workflow = None
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

    def ui_close_blockers(self) -> list[str]:
        """Return user actions that must happen before normal UI close."""

        blockers: list[str] = []
        if self.mircat_scan_active:
            blockers.append("MIRcat Sweep Scan is running. Press Stop Scan and wait for shutdown and saving to finish.")
        if self.iris_command_active:
            blockers.append("An OPO iris command is still running. Wait for it to finish.")
        if self._mircat_handler is not None:
            blockers.extend(self._mircat_handler.close_blockers())
        return blockers

    def ui_mircat_scan_blockers(self) -> list[str]:
        blockers = []
        if self._active_ui_workflow is not None:
            blockers.append("Stop the configured workflow before MIRcat Sweep Scan")
        if any(service is not None for service in (
            self._mircat_service, self._picoscope_service, self._hf2li_service,
        )):
            blockers.append("Use workflow Safe Shutdown to release configured device sessions before MIRcat Sweep Scan")
        return blockers

    def run_mircat_scan(self, command, *, progress, on_state):
        if not self.hardware_access:
            return self(command)
        if self._mircat_handler is None:
            self._mircat_handler = MircatWidgetCommandHandler(operator=self.operator)
        self._mircat_handler.scan_cancel = self.mircat_scan_cancel
        self._mircat_handler.scan_progress = progress
        self._mircat_handler.scan_state = on_state
        return self(command)

    def request_mircat_scan_stop(self):
        self.mircat_scan_cancel.set()

    def ui_iris_motion_blockers(self) -> list[str]:
        """Return active acquisition/workflow states that prohibit iris movement."""

        blockers: list[str] = []
        if self.mircat_scan_active:
            blockers.append("MIRcat Sweep Scan owns the instruments")
        if self.phase_scan_active:
            blockers.append("Phase Scan owns the instruments")
        if (
            self._active_ui_workflow is not None
            and self._active_ui_workflow.workflow_id
            not in IRIS_MOTION_COMPATIBLE_ACTIVE_WORKFLOWS
        ):
            blockers.append(
                f"configured workflow {self._active_ui_workflow.workflow_id!r} is active"
            )
        if self._mircat_handler is not None:
            blockers.extend(self._mircat_handler.close_blockers())
        return blockers

    def ui_safe_shutdown(self, *, reason: str = "ui_close") -> WorkflowResult:
        """Run the normal application-close safe shutdown sequence."""

        blockers = self.ui_close_blockers()
        if blockers:
            return WorkflowResult(
                status="blocked",
                message="Some operations must be stopped manually before closing the app.",
                data={"blockers": blockers, "state": self.state},
            )
        return self._ui_shutdown(reason=reason, emergency=False)

    def emergency_stop(self, *, reason: str = "emergency_stop") -> WorkflowResult:
        """Best-effort shutdown for forced process exit paths."""

        self.phase_scan_runner.abort()
        self.request_mircat_scan_stop()
        return self._ui_shutdown(reason=reason, emergency=True)

    def _ui_shutdown(self, *, reason: str, emergency: bool) -> WorkflowResult:
        actions: dict[str, Any] = {
            "reason": reason,
            "emergency": emergency,
            "mircat_widget_shutdown": None,
            "workflow_safe_shutdown": None,
        }
        errors: list[str] = []

        if self._mircat_handler is not None:
            result = self._mircat_handler.shutdown_for_ui_close(
                emergency=emergency,
                reason=reason,
            )
            actions["mircat_widget_shutdown"] = result.to_dict()
            if result.status != "complete":
                errors.append(result.message)

        safe_result = self(
            WorkflowCommand(
                device_key="workflow",
                command="workflow.safe_shutdown",
                parameters={"reason": reason, "emergency": emergency},
            )
        )
        actions["workflow_safe_shutdown"] = safe_result.to_dict()
        if safe_result.status != "complete":
            errors.append(safe_result.message)

        status = "complete" if not errors else "failed"
        message = (
            "Application shutdown safe-state commands completed."
            if not errors
            else "Application shutdown safe-state commands reported errors: " + "; ".join(errors)
        )
        return WorkflowResult(
            status=status,
            message=message,
            data={
                "state": self.state,
                "actions": actions,
                "errors": errors,
            },
        )

    def _resolve_run_dir(self, run_dir: str | Path | None) -> Path:
        if run_dir is None:
            target = output_run_root() / f"{datetime.now().strftime('%Y%m%d')}_workflow_state_machine"
        else:
            target = Path(run_dir)
            if not target.is_absolute():
                target = resolve_compat_path(target)
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
                    "command_path": _command_path(command.device_key),
                },
            )
            self._record(command.command, self.state, "blocked", message, result.data)
            return result

        if command.device_key == "mircat":
            if self._mircat_handler is None:
                self._mircat_handler = MircatWidgetCommandHandler(operator=self.operator)
            result = self._mircat_handler(command)
        elif command.device_key == "t660_2":
            if self._t660_handler is None:
                self._t660_handler = T660WidgetCommandHandler(
                    operator=self.operator,
                    inventory=self.inventory,
                )
            result = self._t660_handler(command)
        elif command.device_key == "ndyag":
            if self._ndyag_handler is None:
                self._ndyag_handler = NdYagWidgetCommandHandler(
                    operator=self.operator,
                    inventory=self.inventory,
                )
            result = self._ndyag_handler(command)
        elif command.device_key == "opo_iris":
            motion_blockers = self.ui_iris_motion_blockers()
            if motion_blockers:
                return WorkflowResult(
                    status="blocked",
                    message=(
                        "Iris control is unavailable during instrument activity: "
                        + "; ".join(motion_blockers)
                    ),
                )
            if self._iris_handler is None:
                self._iris_handler = IrisWidgetCommandHandler(
                    operator=self.operator,
                    inventory=self.inventory,
                )
            self.iris_command_active = True
            try:
                result = self._iris_handler(command)
            finally:
                self.iris_command_active = False
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
                        "Arduino MUX remains bypassed/inactive",
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
                "hardware_action_sent": True,
                "safe_actions": safe_actions,
            },
        )

    def _route_scope_signal(self, command: WorkflowCommand) -> WorkflowResult:
        recipe = self._require_recipe()
        pico_recipe_path = recipe.get("picoscope_recipe") or recipe.get("pico_capture_recipe")
        pico_settings = self._validate_picoscope_recipe(pico_recipe_path)
        data = {
            "state": "SCOPE_ROUTE_VALIDATED",
            "mux_routes": {},
            "mux_bypassed": True,
            "scope_routing": "Direct wiring only; Arduino MUX is inactive.",
            "picoscope_settings": pico_settings,
            "picoscope_independent_of_arduino_mux": True,
        }
        if not self.hardware_access:
            return self._blocked_hardware(
                command.command,
                "SCOPE_ROUTE_VALIDATED",
                "PicoScope settings were validated with Arduino MUX bypassed; no hardware command was sent.",
                data,
            )

        picoscope_readback = self._apply_picoscope_settings(pico_settings)
        self.mux_routes = {}
        self.picoscope_settings = picoscope_readback
        data.update(
            {
                "state": "SCOPE_ROUTE_APPLIED",
                "hardware_action_sent": True,
                "picoscope_settings": picoscope_readback,
            }
        )
        return self._complete(
            command.command,
            "SCOPE_ROUTE_APPLIED",
            "PicoScope settings were applied; Arduino MUX routing remained bypassed.",
            data,
        )

    def _program_timing_recipe(self, command: WorkflowCommand) -> WorkflowResult:
        recipe = self._require_recipe()
        timing_recipe = command.parameters.get("timing_recipe") or recipe.get("timing_recipe")
        if not timing_recipe:
            raise WorkflowStateMachineError("active campaign recipe does not define timing_recipe")
        manager = TimingRecipeManager(self.inventory)
        validation = manager.validate_recipe(resolve_compat_path(str(timing_recipe)))
        self.recipe_validation["timing_recipe"] = validation
        data = {
            "state": "TIMING_RECIPE_VALIDATED",
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
        readback_path = self._artifact_path(f"workflow_{Path(str(timing_recipe)).stem}_readback.json")
        readback = manager.apply_recipe(resolve_compat_path(str(timing_recipe)), output_path=readback_path)
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
            "MIRcat was tuned with emission off and HF2LI was configured with the recipe-selected preset.",
            data,
        )

    def _acquire_point(self, command: WorkflowCommand) -> WorkflowResult:
        recipe = self._require_recipe()
        point = command.parameters.get("point") or _first_scan_point(recipe)
        data = {
            "state": "ACQUIRE_POINT_VALIDATED",
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

        mircat_point_readback = self._prepare_mircat_for_point(point, point_index=0)
        acquisition = self._acquire_hf2li_point(
            point,
            point_index=0,
            prefix="point",
            mircat_point_readback=mircat_point_readback,
        )
        data.update(
            {
                "state": "ACQUIRING_POINT",
                "hardware_action_sent": True,
                "raw_data_created": True,
                "mircat_point_readback": mircat_point_readback,
                "acquisition": acquisition,
            }
        )
        return self._complete(
            command.command,
            "ACQUIRING_POINT",
            "Acquire-point collected real HF2LI detector data for the selected campaign point.",
            data,
        )

    def _acquire_scan(self, command: WorkflowCommand) -> WorkflowResult:
        recipe = self._require_recipe()
        scan_points = _scan_points(recipe)
        data = {
            "state": "ACQUIRE_SCAN_VALIDATED",
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

        acquisitions = []
        for index, point in enumerate(scan_points):
            mircat_point_readback = self._prepare_mircat_for_point(point, point_index=index)
            acquisitions.append(
                self._acquire_hf2li_point(
                    point,
                    point_index=index,
                    prefix="scan",
                    mircat_point_readback=mircat_point_readback,
                )
            )
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
            "Acquire-scan collected real HF2LI detector data for every selected campaign scan point.",
            data,
        )

    def _abort_to_safe(self, command: WorkflowCommand) -> WorkflowResult:
        reason = str(command.parameters.get("reason") or "campaign workflow abort")
        self.abort_state = {
            "aborted": True,
            "reason": reason,
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        data = {
            "state": "ABORT_LOGGED",
            "abort_state": self.abort_state,
            "safe_actions_required": [
                "Stop acquisition",
                "MIRcat emission off",
                "T660 outputs off",
                "Arduino MUX remains bypassed/inactive",
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
            "recipe_path": picoscope_recipe["recipe_path"],
            "settings": settings,
            "sample_timing_validation": timing_validation,
            "picoscope_model": device_config.get("model"),
            "picoscope_serial": device_config.get("serial_number"),
        }
        self._write_readback("workflow_picoscope_settings_readback.json", readback)
        return readback

    def _safe_tune_mircat(self, recipe: dict[str, Any]) -> dict[str, Any]:
        setpoint = _mircat_setpoint(recipe)
        probe = recipe.get("probe") if isinstance(recipe.get("probe"), dict) else {}
        mircat = probe.get("mircat") if isinstance(probe.get("mircat"), dict) else {}
        qcl = int(setpoint["qcl"])
        emission_requested = _mircat_emission_requested(recipe)
        approved = bool(recipe.get("approved_laser_safety_condition"))
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
        trigger_settings = _configure_mircat_trigger_mode(
            service,
            mircat,
            wavenumber_cm1=float(setpoint["wavenumber_cm1"]),
        )
        if emission_requested:
            service.turn_emission_on(approved_laser_safety_condition=approved)
        else:
            service.turn_emission_off()
        actual = service.get_actual_wavelength()
        state_after = service.read_state().to_dict()
        self.mircat_setpoint = setpoint
        self.mircat_actual_wavelength = actual
        readback = {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "setpoint": setpoint,
            "actual_wavelength": actual,
            "pulse_settings": pulse_settings,
            "trigger_settings": trigger_settings,
            "emission_requested": emission_requested,
            "emission_on": bool(state_after.get("emission_on")),
            "state_before": state_before,
            "state_after": state_after,
        }
        self._write_readback("workflow_mircat_arm_readback.json", readback)
        return readback

    def _prepare_mircat_for_point(
        self,
        point: dict[str, Any],
        *,
        point_index: int,
    ) -> dict[str, Any]:
        if self._mircat_service is None:
            raise WorkflowStateMachineError("arm_measurement must complete before MIRcat scan points")
        recipe = self._require_recipe()
        probe = recipe.get("probe") if isinstance(recipe.get("probe"), dict) else {}
        mircat = probe.get("mircat") if isinstance(probe.get("mircat"), dict) else {}
        setpoint = _mircat_setpoint(recipe)
        wavenumber_cm1 = float(point.get("wavenumber_cm1", setpoint["wavenumber_cm1"]))
        qcl = int(point.get("qcl", setpoint["qcl"]))
        emission_requested = _mircat_emission_requested(recipe)
        approved = bool(recipe.get("approved_laser_safety_condition"))
        service = self._mircat_service

        state_before = service.read_state().to_dict()
        service.turn_emission_off()
        service.tune_to_wavenumber(wavenumber_cm1, qcl=qcl)
        if not service.wait_for_tuned(
            timeout_s=float(mircat.get("tune_timeout_s", 120.0)),
            poll_interval_s=float(mircat.get("poll_interval_s", 0.5)),
        ):
            raise WorkflowStateMachineError(
                f"MIRcat did not report tuned at {wavenumber_cm1:g} cm^-1 before timeout"
            )
        trigger_settings = _configure_mircat_trigger_mode(
            service,
            mircat,
            wavenumber_cm1=wavenumber_cm1,
        )
        if emission_requested:
            service.turn_emission_on(approved_laser_safety_condition=approved)
        else:
            service.turn_emission_off()
        actual = service.get_actual_wavelength()
        state_after = service.read_state().to_dict()
        readback = {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "point_index": point_index,
            "setpoint": {
                "wavenumber_cm1": wavenumber_cm1,
                "units": "cm^-1",
                "qcl": qcl,
            },
            "actual_wavelength": actual,
            "trigger_settings": trigger_settings,
            "emission_requested": emission_requested,
            "emission_on": bool(state_after.get("emission_on")),
            "state_before": state_before,
            "state_after": state_after,
        }
        readback_path = self._write_readback(
            f"mircat_readback_scan_{_point_slug(point, point_index)}.json",
            readback,
        )
        readback["readback_path"] = str(readback_path)
        self.mircat_setpoint = readback["setpoint"]
        self.mircat_actual_wavelength = actual
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
        snapshot_path = self._artifact_path("workflow_hf2li_arm_settings_snapshot.json")
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
        mircat_point_readback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._hf2li_service is None or self._hf2li_preset is None:
            raise WorkflowStateMachineError("arm_measurement must complete before acquisition")
        service = self._hf2li_service
        preset = self._hf2li_preset
        acquisition = preset.settings.get("acquisition") or {}
        duration_s = float(point.get("dwell_s", acquisition.get("duration_s", 5.0)))
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
            "point_index": point_index,
            "point": point,
            "preset": preset.name,
            "duration_s": duration_s,
            "dwell_s": point.get("dwell_s", duration_s),
            "demodulators": demodulators,
            "fields": fields,
            "mircat_point_readback": mircat_point_readback,
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
            "label": label,
            "mircat": None,
            "t660": None,
            "arduino_mux": "bypassed_inactive",
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
                stop_status = self._mircat_service.stop_scan_if_needed()
                if stop_status == RET_NOT_INITIALIZED:
                    actions["mircat"] = {
                        "safe_state": "already_deinitialized",
                        "stop_scan_return_code": stop_status,
                    }
                else:
                    self._mircat_service.turn_emission_off()
                    self._mircat_service.disarm()
                    state = self._mircat_service.read_state().to_dict()
                    self._mircat_service.deinitialize()
                    actions["mircat"] = {
                        "safe_state": "emission_off_disarmed_deinitialized",
                        "state": state,
                    }
            except Exception as exc:  # noqa: BLE001
                errors.append(f"MIRcat safe shutdown failed: {exc}")
            finally:
                self._mircat_service = None

        try:
            manager = TimingRecipeManager(self.inventory, command_log=self.command_log)
            output_path = self._artifact_path(f"workflow_{label}_safe_idle_readback.json")
            actions["t660"] = manager.apply_recipe(RECIPE_ROOT / "safe_idle.yaml", output_path=output_path)
            self._remember_readback(output_path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"T660 safe_idle failed: {exc}")

        readback_path = self._write_readback(f"workflow_{label}_safe_actions.json", actions)
        actions["readback_path"] = str(readback_path)
        if errors:
            raise WorkflowStateMachineError("; ".join(errors))
        return actions

    def _load_recipe(self, recipe_path_value: Any) -> None:
        if self.recipe is not None:
            return
        if recipe_path_value is None or not str(recipe_path_value).strip():
            raise WorkflowStateMachineError(
                "No campaign recipe was supplied. Legacy sample defaults are archived; "
                "provide an explicitly approved campaign recipe path."
            )
        recipe_path = Path(str(recipe_path_value))
        if not recipe_path.is_absolute():
            recipe_path = resolve_compat_path(recipe_path)
        if not recipe_path.exists():
            raise WorkflowStateMachineError(f"workflow recipe not found: {recipe_path}")
        with recipe_path.open("r", encoding="utf-8") as handle:
            recipe = yaml.safe_load(handle) or {}
        if not isinstance(recipe, dict):
            raise WorkflowStateMachineError(f"workflow recipe must be a mapping: {recipe_path}")
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
                "workflow recipe missing required keys: " + ", ".join(missing)
            )
        if not isinstance(recipe.get("delay_list_ns"), list) or not recipe["delay_list_ns"]:
            raise WorkflowStateMachineError("workflow recipe delay_list_ns must be a nonempty list")
        if _mircat_emission_requested(recipe) and not bool(recipe.get("approved_laser_safety_condition")):
            raise WorkflowStateMachineError(
                "MIRcat emission requires approved_laser_safety_condition in the acquisition recipe"
            )
        if _pump_enabled(recipe) and not bool(recipe.get("approved_laser_safety_condition")):
            raise WorkflowStateMachineError(
                "pump-enabled acquisition requires approved_laser_safety_condition in the acquisition recipe"
            )

    def _validate_mircat_request(self, recipe: dict[str, Any]) -> None:
        setpoint = _mircat_setpoint(recipe)
        values = [float(setpoint["wavenumber_cm1"])]
        scan = _scan_definition(recipe) or {}
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
            raise WorkflowStateMachineError("workflow recipe does not define hf2li_preset")
        presets_path = RECIPE_ROOT / "hf2li_presets.yaml"
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
            raise WorkflowStateMachineError("workflow recipe does not define picoscope_recipe")
        recipe, resolved_path = load_picoscope_recipe(resolve_compat_path(str(recipe_path)))
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


def _mircat_setpoint(recipe: dict[str, Any]) -> dict[str, Any]:
    probe = recipe.get("probe")
    if not isinstance(probe, dict):
        raise WorkflowStateMachineError("workflow recipe probe section must be a mapping")
    direct = probe.get("mircat")
    if isinstance(direct, dict):
        if "wavenumber_cm1" not in direct:
            raise WorkflowStateMachineError("workflow recipe probe.mircat does not define wavenumber_cm1")
        value = float(direct["wavenumber_cm1"])
        qcl = int(direct.get("qcl", probe.get("qcl", 1)))
    else:
        if "wavenumber_cm1" not in probe:
            raise WorkflowStateMachineError("workflow recipe probe does not define wavenumber_cm1")
        value = float(probe["wavenumber_cm1"])
        qcl = int(probe.get("qcl", 1))
    scan = _scan_definition(recipe)
    return {
        "wavenumber_cm1": value,
        "units": "cm^-1",
        "qcl": qcl,
        "scan_cm1": scan,
    }


def _scan_definition(recipe: dict[str, Any]) -> dict[str, Any] | None:
    probe = recipe.get("probe")
    if not isinstance(probe, dict):
        return None
    scan = probe.get("scan_cm1")
    if isinstance(scan, dict):
        return scan
    return None


def _scan_points(recipe: dict[str, Any]) -> list[dict[str, Any]]:
    scan = _scan_definition(recipe) or {}
    if not isinstance(scan, dict):
        return [_first_scan_point(recipe)]
    start = float(scan.get("start", _mircat_setpoint(recipe)["wavenumber_cm1"]))
    stop = float(scan.get("stop", start))
    step = abs(float(scan.get("step", 1.0)))
    if step <= 0:
        raise WorkflowStateMachineError("scan_cm1 step must be positive")
    dwell_s = float(scan.get("dwell_s_per_point", scan.get("dwell_s", 5.0)))
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
                "dwell_s": dwell_s,
            }
        )
        current += direction * step
    return points


def _first_scan_point(recipe: dict[str, Any]) -> dict[str, Any]:
    return {
        "wavenumber_cm1": _mircat_setpoint(recipe)["wavenumber_cm1"],
        "delay_ns": recipe["delay_list_ns"][0],
        "hf2li_preset": recipe.get("hf2li_preset"),
        "dwell_s": _point_dwell_s(recipe),
    }


def _point_dwell_s(recipe: dict[str, Any]) -> float:
    scan = _scan_definition(recipe) or {}
    if isinstance(scan, dict):
        return float(scan.get("dwell_s_per_point", scan.get("dwell_s", 5.0)))
    return 5.0


def _mircat_emission_requested(recipe: dict[str, Any]) -> bool:
    probe = recipe.get("probe") if isinstance(recipe.get("probe"), dict) else {}
    mircat = probe.get("mircat") if isinstance(probe.get("mircat"), dict) else {}
    return bool(
        mircat.get("emission_allowed")
        or mircat.get("allow_emission_on")
        or mircat.get("emission_on")
    )


def _pump_enabled(recipe: dict[str, Any]) -> bool:
    pump = recipe.get("pump") if isinstance(recipe.get("pump"), dict) else {}
    return bool(
        pump.get("enabled")
        or pump.get("emission_allowed")
        or pump.get("fire_pump")
    )


def _configure_mircat_trigger_mode(
    service: MircatService,
    mircat: dict[str, Any],
    *,
    wavenumber_cm1: float,
) -> dict[str, Any] | None:
    pulse_mode = mircat.get("pulse_mode")
    pulse_mode_value = _optional_int(mircat.get("pulse_mode_value"))
    if str(pulse_mode).lower() == "external_trigger" or pulse_mode_value == 2:
        return service.set_external_trigger_params(wavenumber_cm1=wavenumber_cm1)
    return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _point_slug(point: dict[str, Any], point_index: int) -> str:
    wavenumber = str(point.get("wavenumber_cm1", "unknown")).replace(".", "p").replace("-", "m")
    delay = str(point.get("delay_ns", "unknown")).replace(".", "p").replace("-", "m")
    return f"{point_index:03d}_wn_{wavenumber}_delay_{delay}ns"
