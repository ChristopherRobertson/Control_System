"""Workflow command handler for the MIRcat desktop widget."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TextIO

from control_app.config_loader import REPO_ROOT, load_config_inventory
from control_app.devices.mircat_service import MircatError, MircatService
from control_app.ui.contracts import WorkflowCommand, WorkflowResult
from control_app.workflows.mircat_status_tune import DEFAULT_LAMBDA_MID_CM1


MIRCAT_WAVENUMBER_MIN_CM1 = 1638.8
MIRCAT_WAVENUMBER_MAX_CM1 = 2077.3


class MircatWidgetCommandHandler:
    """Stateful workflow command handler used by the MIRcat Qt widget."""

    def __init__(self, *, operator: str = "UI") -> None:
        self.operator = operator
        self.inventory = load_config_inventory(write_files=False)
        self.service: MircatService | None = None
        self.initialized = False

    def __call__(self, command: WorkflowCommand) -> WorkflowResult:
        """Handle one MIRcat widget command."""

        if command.device_key != "mircat":
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
        service = self._service(command_log)
        name = command.command
        if name == "mircat.initialize":
            service.initialize()
            self.initialized = True
            return self._complete("MIRcat initialized", command_log)
        if name == "mircat.refresh_status":
            self._require_initialized()
            return self._complete("MIRcat status refreshed", command_log)
        if name == "mircat.arm":
            self._require_initialized()
            self._assert_interlocks(service)
            service.arm()
            return self._complete("MIRcat armed", command_log)
        if name == "mircat.safe_tune":
            self._require_initialized()
            self._assert_interlocks(service)
            service.arm()
            if not service.wait_for_tecs_ready(
                timeout_s=float(command.parameters.get("tec_timeout_s", 120.0)),
                poll_interval_s=float(command.parameters.get("poll_interval_s", 0.5)),
            ):
                return WorkflowResult(
                    status="blocked",
                    message="MIRcat TECs did not reach set temperature before timeout.",
                    data={"command_log": str(self._command_log_path())},
                )
            wavenumber_cm1 = float(
                command.parameters.get("wavenumber_cm1", DEFAULT_LAMBDA_MID_CM1)
            )
            if (
                wavenumber_cm1 < MIRCAT_WAVENUMBER_MIN_CM1
                or wavenumber_cm1 > MIRCAT_WAVENUMBER_MAX_CM1
            ):
                return WorkflowResult(
                    status="blocked",
                    message=(
                        "Requested MIRcat wavenumber is outside the installed range "
                        f"{MIRCAT_WAVENUMBER_MIN_CM1:g}-{MIRCAT_WAVENUMBER_MAX_CM1:g} cm^-1."
                    ),
                    data={"command_log": str(self._command_log_path())},
                )
            service.tune_to_wavenumber(wavenumber_cm1, qcl=int(command.parameters.get("qcl", 1)))
            if not service.wait_for_tuned(
                timeout_s=float(command.parameters.get("tune_timeout_s", 120.0)),
                poll_interval_s=float(command.parameters.get("poll_interval_s", 0.5)),
            ):
                return WorkflowResult(
                    status="blocked",
                    message="MIRcat did not report tuned before timeout.",
                    data={"command_log": str(self._command_log_path())},
                )
            service.turn_emission_off()
            return self._complete("MIRcat tuned with emission kept off", command_log)
        if name == "mircat.cancel_manual_tune":
            self._require_initialized()
            service.cancel_manual_tune()
            return self._complete("Manual tune cancelled or already clear", command_log)
        if name == "mircat.emission_off":
            self._require_initialized()
            service.turn_emission_off()
            return self._complete("MIRcat emission off", command_log)
        if name == "mircat.disarm":
            self._require_initialized()
            service.turn_emission_off()
            service.disarm()
            return self._complete("MIRcat disarmed", command_log)
        if name == "mircat.deinitialize":
            if self.initialized:
                service.turn_emission_off()
                service.disarm()
                service.deinitialize()
            self.initialized = False
            self.service = None
            return WorkflowResult(status="complete", message="MIRcat deinitialized")
        if name == "mircat.emission_on":
            self._require_initialized()
            service.turn_emission_on(
                approved_laser_safety_condition=bool(command.safety_approval)
            )
            return self._complete("MIRcat emission gate opened", command_log)
        return WorkflowResult(status="blocked", message=f"Unsupported command {name}")

    def _service(self, command_log: TextIO) -> MircatService:
        if self.service is None:
            device_config = self.inventory.devices.get("mircat")
            if not isinstance(device_config, dict):
                raise MircatError("mircat missing from hardware configuration")
            self.service = MircatService(device_config, command_log=command_log)
        else:
            self.service.command_log = command_log
        return self.service

    def _complete(self, message: str, command_log: TextIO) -> WorkflowResult:
        service = self._service(command_log)
        return WorkflowResult(
            status="complete",
            message=message,
            data={"state": service.read_state().to_dict(), "command_log": str(self._command_log_path())},
        )

    def _assert_interlocks(self, service: MircatService) -> None:
        if not service.is_interlock_set():
            raise MircatError("MIRcat interlock is not set")
        if not service.is_key_switch_set():
            raise MircatError("MIRcat key switch is not set")

    def _require_initialized(self) -> None:
        if not self.initialized or self.service is None:
            raise MircatError(
                "MIRcat is not initialized. Close the manufacturer UI, then initialize first."
            )

    def _command_log_path(self) -> Path:
        return REPO_ROOT / "logs" / f"{datetime.now().strftime('%Y%m%d')}_mircat_ui_command_log.txt"
