"""MIRcat detector-alignment workflow with ordered external-trigger startup."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO
import json
import time

from control_app.config_loader import ConfigInventory, REPO_ROOT, load_config_inventory
from control_app.devices.mircat_service import (
    PROC_TRIG_MODE_INTERNAL,
    PULSE_MODE_EXTERNAL_TRIGGER,
    UNITS_CM1,
    MircatService,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager


DEFAULT_WAVENUMBER_CM1 = 1858.0
DEFAULT_QCL = 1
DEFAULT_PULSE_RATE_HZ = 2_000_000.0
DEFAULT_PULSE_WIDTH_NS = 150.0
MAX_DUTY_CYCLE = 0.30
MIRCAT_WAVENUMBER_MIN_CM1 = 1638.8
MIRCAT_WAVENUMBER_MAX_CM1 = 2077.3
ALIGNMENT_TIMING_RECIPE = "recipes/mircat_detector_alignment_2mhz.yaml"
SAFE_IDLE_RECIPE = "recipes/safe_idle.yaml"


class MircatDetectorAlignmentError(RuntimeError):
    """Raised when the detector-alignment workflow cannot safely run."""


@dataclass(frozen=True)
class MircatDetectorAlignmentRequest:
    """Operator-approved MIRcat/T660 external-trigger alignment request."""

    wavenumber_cm1: float = DEFAULT_WAVENUMBER_CM1
    qcl: int = DEFAULT_QCL
    pulse_rate_hz: float = DEFAULT_PULSE_RATE_HZ
    pulse_width_ns: float = DEFAULT_PULSE_WIDTH_NS
    current_ma: float | None = None
    tec_timeout_s: float = 120.0
    tune_timeout_s: float = 120.0
    poll_interval_s: float = 0.5
    settle_after_t660_start_s: float = 0.5
    approved_laser_safety_condition: bool = False
    timing_recipe: str = ALIGNMENT_TIMING_RECIPE

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable request dictionary."""

        return asdict(self)


class MircatDetectorAlignmentWorkflow:
    """Start and stop the MIRcat detector-alignment pulse train."""

    def __init__(
        self,
        *,
        operator: str,
        inventory: ConfigInventory | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        self.operator = operator
        self.inventory = inventory or load_config_inventory(config_path, write_files=False)
        self.config_path = Path(self.inventory.config_path)
        self.mircat_service: MircatService | None = None
        self.mircat_initialized = False
        self.t660_running = False
        self.device_readback_paths: list[str] = []
        self.command_log_paths: list[str] = []
        self.mircat_setpoint: dict[str, Any] | None = None
        self.mircat_actual_wavelength: dict[str, Any] | None = None

    def start_alignment(
        self,
        *,
        request: MircatDetectorAlignmentRequest,
        run_dir: str | Path,
        command_log: TextIO | None = None,
    ) -> dict[str, Any]:
        """Configure MIRcat, open emission, then start the T660-2 timing recipe."""

        self._validate_request(request)
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        if command_log is not None and getattr(command_log, "name", None):
            self._remember_command_log(str(command_log.name))

        request_path = self._write_json(run_path / "alignment_request.json", request.to_dict())
        self._remember_readback(request_path)
        summary_path = run_path / "alignment_start_summary.json"
        state_path = run_path / "mircat_alignment_state_readback.json"

        cleanup_errors: list[str] = []
        try:
            timing_manager = TimingRecipeManager(self.inventory, command_log=command_log)
            safe_idle_path = run_path / "safe_idle_before_alignment_readback.json"
            safe_idle_readback = timing_manager.apply_recipe(
                REPO_ROOT / SAFE_IDLE_RECIPE,
                output_path=safe_idle_path,
            )
            self._remember_readback(safe_idle_path)

            service = MircatService.from_config(
                config_path=self.config_path,
                command_log=command_log,
            )
            self.mircat_service = service
            service.initialize()
            self.mircat_initialized = True
            clear_result = service.clear_system_error()
            system_error_word = service.get_system_error_word()
            if system_error_word:
                raise MircatDetectorAlignmentError(
                    f"MIRcat system error word remained nonzero after clear: {system_error_word}"
                )

            initial_state = service.read_state().to_dict()
            self._assert_ready_to_arm(initial_state)
            stop_scan_status = service.stop_scan_if_needed()
            cancel_manual_tune_status = service.cancel_manual_tune()

            pulse_limits = service.get_qcl_pulse_limits(request.qcl)
            self._assert_within_pulse_limits(request, pulse_limits)
            pulse_settings = service.set_qcl_pulse_params(
                qcl=request.qcl,
                pulse_rate_hz=request.pulse_rate_hz,
                pulse_width_ns=request.pulse_width_ns,
                current_ma=request.current_ma,
            )
            wltrig_readback = service.set_external_trigger_params(
                wavenumber_cm1=request.wavenumber_cm1
            )
            self._assert_external_trigger_readback(wltrig_readback, request.wavenumber_cm1)

            service.arm()
            if not service.wait_for_tecs_ready(
                timeout_s=request.tec_timeout_s,
                poll_interval_s=request.poll_interval_s,
            ):
                raise MircatDetectorAlignmentError(
                    f"MIRcat TECs were not ready within {request.tec_timeout_s:g} s"
                )
            service.tune_to_wavenumber(request.wavenumber_cm1, qcl=request.qcl)
            if not service.wait_for_tuned(
                timeout_s=request.tune_timeout_s,
                poll_interval_s=request.poll_interval_s,
            ):
                raise MircatDetectorAlignmentError(
                    f"MIRcat did not report tuned within {request.tune_timeout_s:g} s"
                )

            actual_before_ttl = service.get_actual_wavelength()
            service.turn_emission_on(
                approved_laser_safety_condition=request.approved_laser_safety_condition
            )
            if not service.is_emission_on():
                raise MircatDetectorAlignmentError("MIRcat emission gate did not read back ON")
            state_after_emission = service.read_state().to_dict()

            alignment_readback_path = run_path / "mircat_detector_alignment_2mhz_readback.json"
            alignment_readback = timing_manager.apply_recipe(
                REPO_ROOT / request.timing_recipe,
                output_path=alignment_readback_path,
            )
            self.t660_running = True
            self._remember_readback(alignment_readback_path)

            if request.settle_after_t660_start_s > 0:
                time.sleep(request.settle_after_t660_start_s)
            state_after_t660_start = service.read_state().to_dict()
            actual_after_ttl = service.get_actual_wavelength()
            self.mircat_setpoint = {
                "value": request.wavenumber_cm1,
                "units": "cm^-1",
                "qcl": request.qcl,
                "pulse_rate_hz": request.pulse_rate_hz,
                "pulse_width_ns": request.pulse_width_ns,
                "pulse_mode": "external_trigger",
            }
            self.mircat_actual_wavelength = actual_after_ttl

            self._write_json(
                state_path,
                {
                    "initial_state": initial_state,
                    "state_after_emission_before_t660": state_after_emission,
                    "state_after_t660_start": state_after_t660_start,
                },
            )
            self._remember_readback(state_path)

            summary = {
                "timestamp_utc": _utc_now(),
                "operator": self.operator,
                "config_hash": self.inventory.config_hash,
                "status": "RUNNING_FOR_ALIGNMENT",
                "request": request.to_dict(),
                "safe_idle_before_alignment": str(safe_idle_path),
                "safe_idle_before_alignment_matches_recipe": safe_idle_readback.get(
                    "matches_recipe"
                ),
                "mircat_clear_system_error_result": clear_result,
                "mircat_system_error_word_after_clear": system_error_word,
                "mircat_stop_scan_return_code": stop_scan_status,
                "mircat_cancel_manual_tune_return_code": cancel_manual_tune_status,
                "mircat_pulse_limits": pulse_limits,
                "mircat_pulse_settings": pulse_settings,
                "mircat_wavelength_trigger_readback": wltrig_readback,
                "mircat_actual_before_t660": actual_before_ttl,
                "mircat_actual_after_t660": actual_after_ttl,
                "t660_alignment_readback": str(alignment_readback_path),
                "t660_alignment_matches_recipe": alignment_readback.get("matches_recipe"),
                "state_readback": str(state_path),
                "stop_instruction": "Press Enter in the workflow terminal or run --stop-only.",
                "cleanup_errors": cleanup_errors,
            }
            self._write_json(summary_path, summary)
            self._remember_readback(summary_path)
            return summary
        except Exception as exc:  # noqa: BLE001 - hardware workflow must clean up all failures
            cleanup_errors.extend(self._cleanup_after_failed_start(run_path, command_log))
            failure_summary = {
                "timestamp_utc": _utc_now(),
                "operator": self.operator,
                "status": "FAILED_CLEANUP_ATTEMPTED",
                "error": str(exc),
                "cleanup_errors": cleanup_errors,
                "request": request.to_dict(),
            }
            self._write_json(summary_path, failure_summary)
            self._remember_readback(summary_path)
            raise MircatDetectorAlignmentError(str(exc)) from exc

    def stop_alignment(
        self,
        *,
        run_dir: str | Path,
        command_log: TextIO | None = None,
        reason: str = "operator_stop",
    ) -> dict[str, Any]:
        """Stop T660 timing, close MIRcat emission, disarm, and deinitialize."""

        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        if command_log is not None and getattr(command_log, "name", None):
            self._remember_command_log(str(command_log.name))

        errors: list[str] = []
        safe_idle_path = run_path / "safe_idle_after_alignment_readback.json"
        try:
            timing_manager = TimingRecipeManager(self.inventory, command_log=command_log)
            timing_manager.apply_recipe(REPO_ROOT / SAFE_IDLE_RECIPE, output_path=safe_idle_path)
            self.t660_running = False
            self._remember_readback(safe_idle_path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"T660 safe_idle failed: {exc}")

        service = self.mircat_service
        initialized_here = False
        state_before: dict[str, Any] | None = None
        state_after: dict[str, Any] | None = None
        try:
            if service is None:
                service = MircatService.from_config(
                    config_path=self.config_path,
                    command_log=command_log,
                )
                self.mircat_service = service
            if not self.mircat_initialized:
                service.initialize()
                self.mircat_initialized = True
                initialized_here = True
            state_before = service.read_state().to_dict()
            service.turn_emission_off()
            if service.is_laser_armed():
                service.disarm()
            state_after = service.read_state().to_dict()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"MIRcat shutdown failed: {exc}")
        finally:
            if service is not None and (self.mircat_initialized or initialized_here):
                try:
                    service.deinitialize()
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"MIRcat deinitialize failed: {exc}")
                self.mircat_initialized = False
                self.mircat_service = None

        summary = {
            "timestamp_utc": _utc_now(),
            "operator": self.operator,
            "status": "STOPPED" if not errors else "STOP_ERRORS",
            "reason": reason,
            "safe_idle_after_alignment": str(safe_idle_path),
            "mircat_state_before_shutdown": state_before,
            "mircat_state_after_shutdown": state_after,
            "errors": errors,
        }
        summary_path = self._write_json(run_path / "alignment_stop_summary.json", summary)
        self._remember_readback(summary_path)
        if errors:
            raise MircatDetectorAlignmentError("; ".join(errors))
        return summary

    def _cleanup_after_failed_start(
        self,
        run_path: Path,
        command_log: TextIO | None,
    ) -> list[str]:
        errors: list[str] = []
        try:
            self.stop_alignment(
                run_dir=run_path,
                command_log=command_log,
                reason="failed_start_cleanup",
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
        return errors

    @staticmethod
    def _validate_request(request: MircatDetectorAlignmentRequest) -> None:
        if not request.approved_laser_safety_condition:
            raise MircatDetectorAlignmentError(
                "approved_laser_safety_condition=True is required before opening MIRcat emission"
            )
        if request.qcl < 1 or request.qcl > 4:
            raise MircatDetectorAlignmentError("QCL must be in the SDK-supported range 1..4")
        if (
            request.wavenumber_cm1 < MIRCAT_WAVENUMBER_MIN_CM1
            or request.wavenumber_cm1 > MIRCAT_WAVENUMBER_MAX_CM1
        ):
            raise MircatDetectorAlignmentError(
                f"MIRcat wavenumber {request.wavenumber_cm1:g} cm^-1 is outside "
                f"{MIRCAT_WAVENUMBER_MIN_CM1:g}-{MIRCAT_WAVENUMBER_MAX_CM1:g} cm^-1"
            )
        duty_cycle = request.pulse_rate_hz * request.pulse_width_ns * 1.0e-9
        if duty_cycle > MAX_DUTY_CYCLE + 1e-9:
            raise MircatDetectorAlignmentError(
                f"MIRcat pulse duty cycle {duty_cycle:.6f} exceeds {MAX_DUTY_CYCLE:.2f}"
            )

    @staticmethod
    def _assert_ready_to_arm(state: dict[str, Any]) -> None:
        if not state.get("connected"):
            raise MircatDetectorAlignmentError("MIRcat SDK did not report a laser connection")
        if not state.get("interlock_set"):
            raise MircatDetectorAlignmentError("MIRcat interlock is not set")
        if not state.get("key_switch_set"):
            raise MircatDetectorAlignmentError("MIRcat key switch is not set")

    @staticmethod
    def _assert_within_pulse_limits(
        request: MircatDetectorAlignmentRequest,
        limits: dict[str, Any],
    ) -> None:
        max_rate = float(limits.get("max_pulse_rate_hz") or 0.0)
        max_width = float(limits.get("max_pulse_width_ns") or 0.0)
        if max_rate > 0 and request.pulse_rate_hz > max_rate + 1.0:
            raise MircatDetectorAlignmentError(
                f"Requested MIRcat pulse rate {request.pulse_rate_hz:g} Hz exceeds limit {max_rate:g} Hz"
            )
        if max_width > 0 and request.pulse_width_ns > max_width + 1e-6:
            raise MircatDetectorAlignmentError(
                f"Requested MIRcat pulse width {request.pulse_width_ns:g} ns exceeds limit {max_width:g} ns"
            )

    @staticmethod
    def _assert_external_trigger_readback(
        readback: dict[str, Any],
        wavenumber_cm1: float,
    ) -> None:
        if int(readback.get("pulse_mode", -1)) != PULSE_MODE_EXTERNAL_TRIGGER:
            raise MircatDetectorAlignmentError(f"MIRcat pulse mode readback is not external trigger: {readback}")
        if int(readback.get("process_trigger_mode", -1)) != PROC_TRIG_MODE_INTERNAL:
            raise MircatDetectorAlignmentError(
                f"MIRcat process trigger readback is not internal: {readback}"
            )
        if int(readback.get("units", -1)) != UNITS_CM1:
            raise MircatDetectorAlignmentError(f"MIRcat trigger units readback is not cm^-1: {readback}")
        for field in ("start", "stop"):
            if abs(float(readback.get(field, 0.0)) - float(wavenumber_cm1)) > 0.05:
                raise MircatDetectorAlignmentError(
                    f"MIRcat trigger {field} readback does not match requested wavenumber: {readback}"
                )

    def _remember_readback(self, path: str | Path) -> None:
        text = str(path)
        if text not in self.device_readback_paths:
            self.device_readback_paths.append(text)

    def _remember_command_log(self, path: str | Path) -> None:
        text = str(path)
        if text not in self.command_log_paths:
            self.command_log_paths.append(text)

    @staticmethod
    def _write_json(path: str | Path, data: Any) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
