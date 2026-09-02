"""Workflow command handler for the permanent OPO iris desktop widget."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TextIO

from control_app.config_loader import ConfigInventory, load_config_inventory
from control_app.devices.ell15_iris_service import ELL15IrisService
from control_app.paths import output_log_root
from control_app.ui.contracts import WorkflowCommand, WorkflowResult


IRIS_DEFAULT_STEP_MM = 0.10


class IrisWidgetCommandHandler:
    """Connect, command, read back, and release the ELL15 for each UI action."""

    def __init__(
        self,
        *,
        operator: str = "UI",
        inventory: ConfigInventory | None = None,
        service_factory: Callable[..., ELL15IrisService] | None = None,
    ) -> None:
        self.operator = operator
        self.inventory = inventory or load_config_inventory(write_files=False)
        self.config_path = Path(self.inventory.config_path)
        device = self.inventory.devices.get("opo_iris")
        if not isinstance(device, dict):
            raise ValueError("hardware configuration does not define devices.opo_iris")
        self.device_config = device
        self.service_factory = service_factory

    def __call__(self, command: WorkflowCommand) -> WorkflowResult:
        """Handle one iris widget command without retaining the serial port."""

        if command.device_key != "opo_iris":
            return WorkflowResult(
                status="blocked", message=f"Unsupported device {command.device_key}"
            )
        if command.command not in {
            "opo_iris.refresh_status",
            "opo_iris.step_down",
            "opo_iris.step_up",
            "opo_iris.set_diameter",
        }:
            return WorkflowResult(
                status="blocked", message=f"Unsupported command {command.command}"
            )

        log_path = self._command_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as command_log:
            command_log.write(
                f"{datetime.now().isoformat(timespec='seconds')} ui_command "
                f"{command.command} operator={self.operator}\n"
            )
            try:
                return self._handle(command, command_log, log_path)
            except Exception as exc:  # noqa: BLE001 - UI boundary reports device failures
                return WorkflowResult(
                    status="failed",
                    message=str(exc),
                    data={"command_log": str(log_path)},
                )

    def _handle(
        self,
        command: WorkflowCommand,
        command_log: TextIO,
        log_path: Path,
    ) -> WorkflowResult:
        moving = command.command != "opo_iris.refresh_status"
        service = self._make_service(allow_motion=moving, command_log=command_log)
        try:
            service.connect()
            identity = service.identify()
            current = service.get_aperture_mm()
            if not moving:
                return self._complete(
                    "Iris diameter refreshed",
                    current=current,
                    identity=identity,
                    log_path=log_path,
                )

            target_result = self._target_for(command, current)
            if isinstance(target_result, WorkflowResult):
                return target_result
            target = target_result
            self._move_from_open_side(service, current=current, target=target)
            readback = service.get_aperture_mm()
            action = {
                "opo_iris.step_down": "decreased",
                "opo_iris.step_up": "increased",
                "opo_iris.set_diameter": "set",
            }[command.command]
            return self._complete(
                f"Iris diameter {action} to {target:.2f} mm; readback {readback:.2f} mm",
                current=readback,
                identity=identity,
                log_path=log_path,
                target=target,
            )
        finally:
            service.close()

    def _target_for(
        self, command: WorkflowCommand, current: float
    ) -> float | WorkflowResult:
        minimum = float(self.device_config.get("minimum_aperture_mm", 1.0))
        maximum = float(self.device_config.get("maximum_aperture_mm", 11.5))
        increment = float(self.device_config.get("minimum_incremental_motion_mm", 0.01))
        try:
            if command.command == "opo_iris.set_diameter":
                target = float(command.parameters["diameter_mm"])
            else:
                step = float(command.parameters.get("step_mm", IRIS_DEFAULT_STEP_MM))
                if step <= 0:
                    raise ValueError("step must be greater than zero")
                direction = -1.0 if command.command == "opo_iris.step_down" else 1.0
                target = current + direction * step
        except (KeyError, TypeError, ValueError) as exc:
            return WorkflowResult(
                status="blocked",
                message=f"Enter a valid iris diameter in millimetres ({exc}).",
            )

        target = round(target, 10)
        if not minimum <= target <= maximum:
            return WorkflowResult(
                status="blocked",
                message=(
                    f"Requested iris diameter {target:g} mm is outside the configured "
                    f"range {minimum:.2f}-{maximum:.2f} mm."
                ),
            )
        nearest_increment = round(target / increment) * increment
        if abs(nearest_increment - target) > 1e-9:
            return WorkflowResult(
                status="blocked",
                message=f"Iris diameter must use {increment:.2f} mm increments.",
            )
        return target

    def _move_from_open_side(
        self,
        service: ELL15IrisService,
        *,
        current: float,
        target: float,
    ) -> None:
        """Finish at the target from a larger aperture whenever travel permits."""

        maximum = float(self.device_config.get("maximum_aperture_mm", 11.5))
        if target > current + 1e-9:
            service.set_aperture_mm(maximum, require_open_side_approach=False)
            if target < maximum - 1e-9:
                service.set_aperture_mm(target)
            return
        service.set_aperture_mm(target)

    def _make_service(
        self, *, allow_motion: bool, command_log: TextIO
    ) -> ELL15IrisService:
        if self.service_factory is not None:
            return self.service_factory(
                allow_motion=allow_motion,
                command_log=command_log,
            )
        return ELL15IrisService.from_config(
            config_path=self.config_path,
            allow_motion=allow_motion,
            command_log=command_log,
        )

    def _complete(
        self,
        message: str,
        *,
        current: float,
        identity: Any,
        log_path: Path,
        target: float | None = None,
    ) -> WorkflowResult:
        minimum = float(self.device_config.get("minimum_aperture_mm", 1.0))
        maximum = float(self.device_config.get("maximum_aperture_mm", 11.5))
        state = {
            "current_diameter_mm": current,
            "identity": f"ELL15 S/N {identity.serial_number}",
            "configured_range": f"{minimum:.2f}-{maximum:.2f} mm",
        }
        data: dict[str, Any] = {
            "state": state,
            "readback": {
                "current_diameter_mm": current,
                "target_diameter_mm": target,
                "device_serial_number": identity.serial_number,
            },
            "command_log": str(log_path),
        }
        return WorkflowResult(status="complete", message=message, data=data)

    def _command_log_path(self) -> Path:
        return output_log_root() / (
            f"{datetime.now().strftime('%Y%m%d')}_opo_iris_ui_command_log.txt"
        )
