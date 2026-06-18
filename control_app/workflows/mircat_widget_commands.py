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
DEFAULT_SCAN_START_CM1 = 1848.0
DEFAULT_SCAN_STOP_CM1 = 1868.0
DEFAULT_SCAN_RATE_CM1_S = 1.0
DEFAULT_PULSE_RATE_HZ = 100000.0
DEFAULT_PULSE_WIDTH_NS = 500.0
MAX_PULSE_DUTY_CYCLE = 0.30


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
            qcl = int(command.parameters.get("qcl", 1))
            pulse_settings = self._pulse_settings(command)
            applied_pulse_settings = service.set_qcl_pulse_params(qcl=qcl, **pulse_settings)
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
            service.tune_to_wavenumber(wavenumber_cm1, qcl=qcl)
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
            return self._complete(
                "MIRcat tuned with emission kept off",
                command_log,
                extra_data={"pulse_settings": applied_pulse_settings},
            )
        if name == "mircat.configure_pulse":
            self._require_initialized()
            qcl = int(command.parameters.get("qcl", 1))
            pulse_settings = service.set_qcl_pulse_params(qcl=qcl, **self._pulse_settings(command))
            return self._complete(
                "MIRcat QCL pulse parameters applied",
                command_log,
                extra_data={"pulse_settings": pulse_settings},
            )
        if name == "mircat.start_sweep_scan":
            self._require_initialized()
            if not command.safety_approval:
                return WorkflowResult(
                    status="blocked",
                    message="Safety approval must be checked before starting a MIRcat scan.",
                    data={"command_log": str(self._command_log_path())},
                )
            self._assert_interlocks(service)
            service.arm()
            if not service.wait_for_tecs_ready(
                timeout_s=float(command.parameters.get("tec_timeout_s", 120.0)),
                poll_interval_s=float(command.parameters.get("poll_interval_s", 0.5)),
            ):
                return WorkflowResult(
                    status="blocked",
                    message="MIRcat TECs did not reach set temperature before scan timeout.",
                    data={"command_log": str(self._command_log_path())},
                )
            qcl = int(command.parameters.get("qcl", 1))
            start_cm1 = float(
                command.parameters.get("scan_start_cm1", DEFAULT_SCAN_START_CM1)
            )
            stop_cm1 = float(command.parameters.get("scan_stop_cm1", DEFAULT_SCAN_STOP_CM1))
            range_blocker = self._wavenumber_range_blocker(start_cm1, stop_cm1)
            if range_blocker:
                return WorkflowResult(
                    status="blocked",
                    message=range_blocker,
                    data={"command_log": str(self._command_log_path())},
                )
            scan_rate_cm1_s = self._positive_float(
                command.parameters.get("scan_rate_cm1_s", DEFAULT_SCAN_RATE_CM1_S),
                "Scan rate",
            )
            repetitions = int(command.parameters.get("scan_repetitions", 1))
            if repetitions < 1 or repetitions > 65535:
                return WorkflowResult(
                    status="blocked",
                    message="Scan repetitions must be in the range 1..65535.",
                    data={"command_log": str(self._command_log_path())},
                )
            pulse_settings = service.set_qcl_pulse_params(qcl=qcl, **self._pulse_settings(command))
            service.cancel_manual_tune()
            service.start_sweep_scan(
                start_cm1=start_cm1,
                stop_cm1=stop_cm1,
                scan_rate_cm1_s=scan_rate_cm1_s,
                qcl=qcl,
                repetitions=repetitions,
            )
            return self._complete(
                "MIRcat sweep scan started",
                command_log,
                extra_data={
                    "scan_request": {
                        "start_cm1": start_cm1,
                        "stop_cm1": stop_cm1,
                        "scan_rate_cm1_s": scan_rate_cm1_s,
                        "repetitions": repetitions,
                        "qcl": qcl,
                    },
                    "pulse_settings": pulse_settings,
                },
            )
        if name == "mircat.stop_scan":
            self._require_initialized()
            stop_status = service.stop_scan_if_needed()
            service.turn_emission_off()
            return self._complete(
                "MIRcat scan stopped and emission gate closed",
                command_log,
                extra_data={"stop_scan_return_code": stop_status},
            )
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

    def _complete(
        self,
        message: str,
        command_log: TextIO,
        *,
        extra_data: dict[str, object] | None = None,
    ) -> WorkflowResult:
        service = self._service(command_log)
        data = {
            "state": service.read_state().to_dict(),
            "command_log": str(self._command_log_path()),
            "config_hash": self.inventory.config_hash,
        }
        if extra_data:
            data.update(extra_data)
        return WorkflowResult(
            status="complete",
            message=message,
            data=data,
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

    def _wavenumber_range_blocker(self, *values_cm1: float) -> str | None:
        for value in values_cm1:
            if value < MIRCAT_WAVENUMBER_MIN_CM1 or value > MIRCAT_WAVENUMBER_MAX_CM1:
                return (
                    "Requested MIRcat wavenumber is outside the installed range "
                    f"{MIRCAT_WAVENUMBER_MIN_CM1:g}-{MIRCAT_WAVENUMBER_MAX_CM1:g} cm^-1."
                )
        return None

    def _positive_float(self, value: object, label: str) -> float:
        parsed = float(value)
        if parsed <= 0:
            raise MircatError(f"{label} must be positive")
        return parsed

    def _pulse_settings(self, command: WorkflowCommand) -> dict[str, float]:
        pulse_rate_hz = self._positive_float(
            command.parameters.get("pulse_rate_hz", DEFAULT_PULSE_RATE_HZ),
            "Pulse repetition rate",
        )
        pulse_width_ns = self._positive_float(
            command.parameters.get("pulse_width_ns", DEFAULT_PULSE_WIDTH_NS),
            "Pulse width",
        )
        duty_cycle = pulse_rate_hz * pulse_width_ns * 1.0e-9
        if duty_cycle > MAX_PULSE_DUTY_CYCLE:
            raise MircatError(
                "MIRcat pulse duty cycle must not exceed 30% "
                f"(rate_hz * width_ns * 1e-9 = {duty_cycle:.3f})."
            )
        return {"pulse_rate_hz": pulse_rate_hz, "pulse_width_ns": pulse_width_ns}

    def _command_log_path(self) -> Path:
        return REPO_ROOT / "logs" / f"{datetime.now().strftime('%Y%m%d')}_mircat_ui_command_log.txt"
