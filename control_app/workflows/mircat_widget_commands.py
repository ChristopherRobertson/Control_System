"""Workflow command handler for the MIRcat desktop widget."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TextIO

from control_app.config_loader import REPO_ROOT, load_config_inventory
from control_app.devices.mircat_service import RET_NOT_INITIALIZED, MircatError, MircatService
from control_app.manifest import new_manifest, write_manifest
from control_app.ui.contracts import WorkflowCommand, WorkflowResult
from control_app.workflows.mircat_detector_alignment import (
    ALIGNMENT_TIMING_RECIPE,
    DEFAULT_CURRENT_MA,
    DEFAULT_HF2LI_PRESET,
    DEFAULT_PULSE_RATE_HZ as ALIGNMENT_DEFAULT_PULSE_RATE_HZ,
    DEFAULT_PULSE_WIDTH_NS as ALIGNMENT_DEFAULT_PULSE_WIDTH_NS,
    DEFAULT_USE_T660_TIMING,
    DEFAULT_WAVENUMBER_CM1,
    EXTERNAL_T660_HF2LI_PRESET,
    SAFE_IDLE_RECIPE,
    MircatDetectorAlignmentRequest,
    MircatDetectorAlignmentWorkflow,
)
from control_app.workflows.mircat_sweep_scan import run_sweep_scan
import yaml


MIRCAT_WAVENUMBER_MIN_CM1 = 1638.8
MIRCAT_WAVENUMBER_MAX_CM1 = 2077.3
DEFAULT_SCAN_START_CM1 = 2050.0
DEFAULT_SCAN_STOP_CM1 = 1650.0
DEFAULT_SCAN_RATE_CM1_S = 40.0
DEFAULT_PULSE_RATE_HZ = ALIGNMENT_DEFAULT_PULSE_RATE_HZ
DEFAULT_PULSE_WIDTH_NS = ALIGNMENT_DEFAULT_PULSE_WIDTH_NS
MAX_PULSE_DUTY_CYCLE = 0.30


class MircatWidgetCommandHandler:
    """Stateful workflow command handler used by the MIRcat Qt widget."""

    def __init__(self, *, operator: str = "UI") -> None:
        self.operator = operator
        self.inventory = load_config_inventory(write_files=False)
        self.service: MircatService | None = None
        self.initialized = False
        self.alignment_workflow: MircatDetectorAlignmentWorkflow | None = None
        self.alignment_run_dir: Path | None = None
        self.alignment_running = False
        self.scan_running = False

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
        name = command.command
        if name == "mircat.start_detector_alignment":
            return self._start_detector_alignment(command, command_log)
        if name == "mircat.stop_detector_alignment":
            return self._stop_detector_alignment(
                command_log,
                reason="ui_stop_alignment",
                message="Detector alignment stopped",
            )
        if name == "mircat.emission_off" and self.alignment_workflow is not None:
            return self._stop_detector_alignment(
                command_log,
                reason="ui_emission_off",
                message="Detector alignment stopped and MIRcat emission off",
            )
        if name == "mircat.stop_scan" and self.alignment_workflow is not None:
            return self._stop_detector_alignment(
                command_log,
                reason="ui_stop_scan",
                message="Detector alignment stopped",
            )
        if name == "mircat.disarm" and self.alignment_workflow is not None:
            return self._stop_detector_alignment(
                command_log,
                reason="ui_disarm",
                message="Detector alignment stopped and MIRcat disarmed",
            )
        if name == "mircat.deinitialize" and self.alignment_workflow is not None:
            return self._stop_detector_alignment(
                command_log,
                reason="ui_deinitialize",
                message="Detector alignment stopped and MIRcat deinitialized",
            )

        service = self._service(command_log)
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
                command.parameters.get("wavenumber_cm1", DEFAULT_WAVENUMBER_CM1)
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
            return self._start_current_wiring_sweep(command, command_log)
        if name == "mircat.start_sweep_scan_legacy":
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
            self.scan_running = True
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
            self.scan_running = False
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
            service.stop_scan_if_needed()
            service.turn_emission_off()
            self.scan_running = False
            return self._complete("MIRcat emission off", command_log)
        if name == "mircat.disarm":
            self._require_initialized()
            service.stop_scan_if_needed()
            service.turn_emission_off()
            service.disarm()
            self.scan_running = False
            return self._complete("MIRcat disarmed", command_log)
        if name == "mircat.deinitialize":
            if self.initialized:
                service.stop_scan_if_needed()
                service.turn_emission_off()
                service.disarm()
                service.deinitialize()
            self.initialized = False
            self.scan_running = False
            self.service = None
            return WorkflowResult(status="complete", message="MIRcat deinitialized")
        if name == "mircat.emission_on":
            self._require_initialized()
            service.turn_emission_on(
                approved_laser_safety_condition=bool(command.safety_approval)
            )
            return self._complete("MIRcat emission gate opened", command_log)
        return WorkflowResult(status="blocked", message=f"Unsupported command {name}")

    def _start_current_wiring_sweep(
        self, command: WorkflowCommand, command_log: TextIO
    ) -> WorkflowResult:
        """Run the all-device TRIG-OUT-started sweep workflow."""
        if not command.safety_approval:
            return WorkflowResult(status="blocked", message="Safety approval must be checked before starting a MIRcat scan.")
        recipe_path = REPO_ROOT / "recipes" / "mircat_sweep_scan.yaml"
        recipe = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
        mircat = recipe["mircat"]
        for key, target in (("scan_start_cm1", "start_cm1"), ("scan_stop_cm1", "stop_cm1"), ("scan_rate_cm1_s", "scan_rate_cm1_s"), ("scan_repetitions", "repetitions"), ("pulse_rate_hz", "pulse_rate_hz"), ("pulse_width_ns", "pulse_width_ns")):
            if key in command.parameters:
                mircat[target] = command.parameters[key]
        run_dir = REPO_ROOT / "runs" / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_mircat_sweep_scan"
        try:
            result = run_sweep_scan(request=recipe, run_dir=run_dir, command_log=command_log)
        except Exception as exc:  # noqa: BLE001
            return WorkflowResult(status="failed", message=str(exc), data={"run_dir": str(run_dir)})
        return WorkflowResult(status="complete", message="MIRcat sweep completed; data are held in the Plotter until exported or replaced.", data={"run_dir": str(run_dir), **result})

    def _start_detector_alignment(
        self,
        command: WorkflowCommand,
        command_log: TextIO,
    ) -> WorkflowResult:
        if self.alignment_workflow is not None or self.alignment_running:
            return WorkflowResult(
                status="blocked",
                message=(
                    "Detector alignment is already running. Press Emission Off before "
                    "starting another alignment."
                ),
                data={"run_dir": str(self.alignment_run_dir) if self.alignment_run_dir else None},
            )
        if not command.safety_approval:
            return WorkflowResult(
                status="blocked",
                message="Safety approval must be checked before starting detector alignment.",
                data={"command_log": str(self._command_log_path())},
            )
        use_t660_timing = bool(
            command.parameters.get("use_t660_timing", DEFAULT_USE_T660_TIMING)
        )
        existing_service = self.service if self.initialized else None

        run_dir = (
            REPO_ROOT
            / "runs"
            / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_mircat_detector_alignment_ui"
        )
        workflow = MircatDetectorAlignmentWorkflow(
            operator=self.operator,
            inventory=self.inventory,
        )
        request = MircatDetectorAlignmentRequest(
            wavenumber_cm1=float(command.parameters.get("wavenumber_cm1", DEFAULT_WAVENUMBER_CM1)),
            qcl=int(command.parameters.get("qcl", 1)),
            pulse_rate_hz=self._positive_float(
                command.parameters.get("pulse_rate_hz", DEFAULT_PULSE_RATE_HZ),
                "Pulse repetition rate",
            ),
            pulse_width_ns=self._positive_float(
                command.parameters.get("pulse_width_ns", DEFAULT_PULSE_WIDTH_NS),
                "Pulse width",
            ),
            current_ma=self._positive_float(
                command.parameters.get("current_ma", DEFAULT_CURRENT_MA),
                "Current",
            ),
            hf2li_preset=str(
                command.parameters.get(
                    "hf2li_preset",
                    EXTERNAL_T660_HF2LI_PRESET if use_t660_timing else DEFAULT_HF2LI_PRESET,
                )
            ),
            use_t660_timing=use_t660_timing,
            tec_timeout_s=float(command.parameters.get("tec_timeout_s", 120.0)),
            tune_timeout_s=float(command.parameters.get("tune_timeout_s", 120.0)),
            poll_interval_s=float(command.parameters.get("poll_interval_s", 0.5)),
            approved_laser_safety_condition=bool(command.safety_approval),
        )
        try:
            summary = workflow.start_alignment(
                request=request,
                run_dir=run_dir,
                command_log=command_log,
                existing_mircat_service=existing_service,
                existing_mircat_initialized=existing_service is not None,
            )
        except Exception:
            if existing_service is not None:
                self.service = None
                self.initialized = False
            raise
        self.alignment_workflow = workflow
        self.alignment_run_dir = run_dir
        self.alignment_running = True
        self.service = workflow.mircat_service
        self.initialized = self.service is not None
        manifest_path = self._write_alignment_manifest(
            workflow=workflow,
            run_dir=run_dir,
            status="running",
            errors=[],
            stop_reason=None,
        )
        state = self.service.read_state().to_dict() if self.service is not None else {}
        return WorkflowResult(
            status="complete",
            message="Detector alignment running; press Emission Off to stop.",
            data={
                "state": state,
                "run_dir": str(run_dir),
                "manifest": str(manifest_path),
                "alignment_summary": summary,
                "used_existing_mircat_session": existing_service is not None,
                "command_log": str(self._command_log_path()),
                "config_hash": self.inventory.config_hash,
            },
        )

    def _stop_detector_alignment(
        self,
        command_log: TextIO,
        *,
        reason: str,
        message: str,
    ) -> WorkflowResult:
        workflow = self.alignment_workflow
        run_dir = self.alignment_run_dir
        if workflow is None or run_dir is None:
            return WorkflowResult(
                status="blocked",
                message="No UI-started detector alignment is running.",
                data={"command_log": str(self._command_log_path())},
            )

        errors: list[str] = []
        stop_summary: dict[str, object] = {}
        try:
            stop_summary = workflow.stop_alignment(
                run_dir=run_dir,
                command_log=command_log,
                reason=reason,
            )
        except Exception as exc:  # noqa: BLE001 - UI stop path must report cleanup errors
            errors.append(str(exc))
            stop_summary = {"error": str(exc)}
        finally:
            self.alignment_workflow = None
            self.alignment_run_dir = None
            self.alignment_running = False
            self.scan_running = False
            self.initialized = False
            self.service = None

        manifest_path = self._write_alignment_manifest(
            workflow=workflow,
            run_dir=run_dir,
            status="stopped" if not errors else "stop_errors",
            errors=errors,
            stop_reason=reason,
        )
        state = {}
        if isinstance(stop_summary, dict):
            maybe_state = stop_summary.get("mircat_state_after_shutdown")
            if isinstance(maybe_state, dict):
                state = maybe_state
        return WorkflowResult(
            status="complete" if not errors else "failed",
            message=message if not errors else f"{message} with errors: {'; '.join(errors)}",
            data={
                "state": state,
                "run_dir": str(run_dir),
                "manifest": str(manifest_path),
                "alignment_stop_summary": stop_summary,
                "command_log": str(self._command_log_path()),
                "config_hash": self.inventory.config_hash,
            },
        )

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
        if duty_cycle > MAX_PULSE_DUTY_CYCLE + 1.0e-9:
            raise MircatError(
                "MIRcat pulse duty cycle must not exceed 30% "
                f"(rate_hz * width_ns * 1e-9 = {duty_cycle:.6f})."
            )
        current_ma = self._positive_float(
            command.parameters.get("current_ma", DEFAULT_CURRENT_MA),
            "Current",
        )
        return {
            "pulse_rate_hz": pulse_rate_hz,
            "pulse_width_ns": pulse_width_ns,
            "current_ma": current_ma,
        }

    def _write_alignment_manifest(
        self,
        *,
        workflow: MircatDetectorAlignmentWorkflow,
        run_dir: Path,
        status: str,
        errors: list[str],
        stop_reason: str | None,
    ) -> Path:
        next_actions = []
        if errors:
            next_actions.append(
                "Review alignment_stop_summary.json and rerun after correcting the reported stop error."
            )
        manifest = new_manifest(
            operator=self.operator,
            inventory=self.inventory,
            t660_recipes=(
                [SAFE_IDLE_RECIPE, ALIGNMENT_TIMING_RECIPE]
                if workflow.uses_t660_timing
                else []
            ),
            mircat_setpoint=workflow.mircat_setpoint,
            mircat_actual_wavelength=workflow.mircat_actual_wavelength,
            hf2li_settings_snapshot=workflow.hf2li_settings_snapshot,
            command_log_paths=workflow.command_log_paths,
            device_readback_paths=workflow.device_readback_paths,
            error_state={"has_error": bool(errors), "errors": errors},
            abort_state={"aborted": False, "reason": stop_reason},
            blocker_status={
                "blocked": bool(errors),
                "blockers": errors,
                "next_actions": next_actions,
            },
        )
        manifest["alignment_status"] = status
        return write_manifest(run_dir / "run_manifest.json", manifest)

    def _command_log_path(self) -> Path:
        return REPO_ROOT / "logs" / f"{datetime.now().strftime('%Y%m%d')}_mircat_ui_command_log.txt"

    def close_blockers(self) -> list[str]:
        """Return user actions required before normal application close."""

        blockers: list[str] = []
        if self.alignment_running or self.alignment_workflow is not None:
            blockers.append(
                "MIRcat detector alignment is running. Press Emission Off or Stop Alignment "
                "in the MIRcat tab, wait for the stop message, then close the app."
            )
        if self.scan_running:
            blockers.append(
                "MIRcat sweep scan is running. Press Stop Scan in the MIRcat tab, wait for "
                "the stopped message, then close the app."
            )
        return blockers

    def shutdown_for_ui_close(self, *, emergency: bool, reason: str) -> WorkflowResult:
        """Close MIRcat emission/session state for application shutdown."""

        blockers = self.close_blockers()
        if blockers and not emergency:
            return WorkflowResult(
                status="blocked",
                message="MIRcat must be manually stopped before closing the app.",
                data={"blockers": blockers},
            )

        log_path = self._command_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as command_log:
            command_log.write(
                f"{datetime.now().isoformat(timespec='seconds')} ui_shutdown "
                f"emergency={emergency} reason={reason} operator={self.operator}\n"
            )
            errors: list[str] = []
            actions: dict[str, object] = {
                "emergency": emergency,
                "reason": reason,
                "alignment_stop": None,
                "mircat_shutdown": None,
                "command_log": str(log_path),
            }

            if self.alignment_workflow is not None or self.alignment_running:
                stop_result = self._stop_detector_alignment(
                    command_log,
                    reason=reason,
                    message="MIRcat detector alignment stopped for application shutdown",
                )
                actions["alignment_stop"] = stop_result.to_dict()
                if stop_result.status == "failed":
                    errors.append(stop_result.message)

            if self.service is not None and self.initialized:
                try:
                    self.service.command_log = command_log
                    stop_status = self.service.stop_scan_if_needed()
                    if stop_status == RET_NOT_INITIALIZED:
                        # A separate workflow may already have closed the process-wide SDK
                        # session.  The MIRcat is then already deinitialized and cannot be
                        # made safer through this stale client instance.
                        actions["mircat_shutdown"] = {
                            "safe_state": "already_deinitialized",
                            "stop_scan_return_code": stop_status,
                        }
                    else:
                        self.service.turn_emission_off()
                        self.service.disarm()
                        state = self.service.read_state().to_dict()
                        self.service.deinitialize()
                        actions["mircat_shutdown"] = {
                            "safe_state": "scan_stopped_emission_off_disarmed_deinitialized",
                            "state_before_deinitialize": state,
                        }
                except Exception as exc:  # noqa: BLE001 - shutdown path reports exact hardware error
                    errors.append(f"MIRcat shutdown failed: {exc}")
                finally:
                    self.service = None
                    self.initialized = False
                    self.scan_running = False

            if errors:
                return WorkflowResult(
                    status="failed",
                    message="; ".join(errors),
                    data=actions,
                )
            return WorkflowResult(
                status="complete",
                message="MIRcat is stopped, emission off, disarmed, and deinitialized.",
                data=actions,
            )
