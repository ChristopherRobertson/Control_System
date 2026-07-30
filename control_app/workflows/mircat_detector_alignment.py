"""MIRcat detector-alignment workflow with ordered external-trigger startup."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO
import json
import time

from control_app.config_loader import ConfigInventory, REPO_ROOT, load_config_inventory
from control_app.devices.hf2li_service import HF2LIService
from control_app.devices.mircat_service import (
    PROC_TRIG_MODE_INTERNAL,
    PULSE_MODE_INTERNAL,
    PULSE_MODE_EXTERNAL_TRIGGER,
    UNITS_CM1,
    MircatService,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager


DEFAULT_WAVENUMBER_CM1 = 1850.0
DEFAULT_QCL = 1
DEFAULT_PULSE_RATE_HZ = 2_000_000.0
DEFAULT_PULSE_WIDTH_NS = 150.0
DEFAULT_CURRENT_MA = 1000.0
DEFAULT_USE_T660_TIMING = False
DEFAULT_HF2LI_PRESET = "detector_alignment_internal"
EXTERNAL_T660_HF2LI_PRESET = "detector_alignment"
HF2LI_PRESETS_PATH = "recipes/hf2li_presets.yaml"
MAX_DUTY_CYCLE = 0.30
MIRCAT_WAVENUMBER_MIN_CM1 = 1638.8
MIRCAT_WAVENUMBER_MAX_CM1 = 2077.3
ALIGNMENT_TIMING_RECIPE = "recipes/mircat_detector_alignment_2mhz.yaml"
SAFE_IDLE_RECIPE = "recipes/safe_idle.yaml"


class MircatDetectorAlignmentError(RuntimeError):
    """Raised when the detector-alignment workflow cannot safely run."""


@dataclass(frozen=True)
class MircatDetectorAlignmentRequest:
    """Operator-approved MIRcat detector-alignment request."""

    wavenumber_cm1: float = DEFAULT_WAVENUMBER_CM1
    qcl: int = DEFAULT_QCL
    pulse_rate_hz: float = DEFAULT_PULSE_RATE_HZ
    pulse_width_ns: float = DEFAULT_PULSE_WIDTH_NS
    current_ma: float | None = DEFAULT_CURRENT_MA
    hf2li_preset: str = DEFAULT_HF2LI_PRESET
    hf2li_presets_path: str = HF2LI_PRESETS_PATH
    use_t660_timing: bool = DEFAULT_USE_T660_TIMING
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
        self.hf2li_service: HF2LIService | None = None
        self.mircat_initialized = False
        self.t660_running = False
        self.uses_t660_timing = False
        self.device_readback_paths: list[str] = []
        self.command_log_paths: list[str] = []
        self.mircat_setpoint: dict[str, Any] | None = None
        self.mircat_actual_wavelength: dict[str, Any] | None = None
        self.hf2li_settings_snapshot: dict[str, Any] = {}

    def start_alignment(
        self,
        *,
        request: MircatDetectorAlignmentRequest,
        run_dir: str | Path,
        command_log: TextIO | None = None,
        existing_mircat_service: MircatService | None = None,
        existing_mircat_initialized: bool = False,
    ) -> dict[str, Any]:
        """Configure MIRcat, open emission, then optionally start T660-2 timing."""

        self._validate_request(request)
        self.uses_t660_timing = bool(request.use_t660_timing)
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
            timing_manager = None
            safe_idle_path = None
            safe_idle_readback = None
            if request.use_t660_timing:
                timing_manager = TimingRecipeManager(self.inventory, command_log=command_log)
                safe_idle_path = run_path / "safe_idle_before_alignment_readback.json"
                safe_idle_readback = timing_manager.apply_recipe(
                    REPO_ROOT / SAFE_IDLE_RECIPE,
                    output_path=safe_idle_path,
                )
                self._remember_readback(safe_idle_path)

            service = existing_mircat_service or MircatService.from_config(
                config_path=self.config_path,
                command_log=command_log,
            )
            service.command_log = command_log
            self.mircat_service = service
            if existing_mircat_initialized:
                self.mircat_initialized = True
            else:
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
            pulse_mode_name = "external_trigger" if request.use_t660_timing else "internal"
            if request.use_t660_timing:
                wltrig_readback = service.set_external_trigger_params(
                    wavenumber_cm1=request.wavenumber_cm1
                )
                self._assert_external_trigger_readback(wltrig_readback, request.wavenumber_cm1)
            else:
                wltrig_readback = service.set_internal_trigger_params(
                    wavenumber_cm1=request.wavenumber_cm1
                )
                self._assert_internal_trigger_readback(wltrig_readback, request.wavenumber_cm1)
            laser_parameters_path = self._write_json(
                run_path / "mircat_alignment_laser_parameters.json",
                {
                    "timestamp_utc": _utc_now(),
                    "operator": self.operator,
                    "requested_operation": {
                        "wavenumber_cm1": request.wavenumber_cm1,
                        "qcl": request.qcl,
                        "pulse_rate_hz": request.pulse_rate_hz,
                        "pulse_width_ns": request.pulse_width_ns,
                        "current_ma": request.current_ma,
                        "operation": f"{pulse_mode_name}_pulsed",
                    },
                    "pulse_limits": pulse_limits,
                    "pulse_settings_readback": pulse_settings,
                    "wavelength_trigger_readback": wltrig_readback,
                },
            )
            self._remember_readback(laser_parameters_path)

            arm_before_tec = self._arm_and_confirm(
                service,
                request=request,
                label="before_tec_wait",
            )
            if not service.wait_for_tecs_ready(
                timeout_s=request.tec_timeout_s,
                poll_interval_s=request.poll_interval_s,
            ):
                raise MircatDetectorAlignmentError(
                    f"MIRcat TECs were not ready within {request.tec_timeout_s:g} s"
                )
            arm_before_tune = self._arm_and_confirm(
                service,
                request=request,
                label="before_tune",
            )
            state_before_tune = service.read_state().to_dict()
            arm_readback_path = self._write_json(
                run_path / "mircat_alignment_arm_readback.json",
                {
                    "timestamp_utc": _utc_now(),
                    "operator": self.operator,
                    "arm_attempts_before_tec_wait": arm_before_tec,
                    "arm_attempts_before_tune": arm_before_tune,
                    "state_before_tune": state_before_tune,
                },
            )
            self._remember_readback(arm_readback_path)
            service.tune_to_wavenumber(request.wavenumber_cm1, qcl=request.qcl)
            if not service.wait_for_tuned(
                timeout_s=request.tune_timeout_s,
                poll_interval_s=request.poll_interval_s,
            ):
                raise MircatDetectorAlignmentError(
                    f"MIRcat did not report tuned within {request.tune_timeout_s:g} s"
                )
            if request.use_t660_timing:
                wltrig_after_tune_readback = service.set_external_trigger_params(
                    wavenumber_cm1=request.wavenumber_cm1
                )
                self._assert_external_trigger_readback(
                    wltrig_after_tune_readback,
                    request.wavenumber_cm1,
                )
            else:
                wltrig_after_tune_readback = service.set_internal_trigger_params(
                    wavenumber_cm1=request.wavenumber_cm1
                )
                self._assert_internal_trigger_readback(
                    wltrig_after_tune_readback,
                    request.wavenumber_cm1,
                )

            hf2li_readback = self._configure_hf2li_alignment(
                request=request,
                run_path=run_path,
                command_log=command_log,
            )
            actual_before_ttl = service.get_actual_wavelength()
            service.turn_emission_on(
                approved_laser_safety_condition=request.approved_laser_safety_condition
            )
            if not service.is_emission_on():
                raise MircatDetectorAlignmentError("MIRcat emission gate did not read back ON")
            state_after_emission = service.read_state().to_dict()

            alignment_readback_path = None
            alignment_readback = None
            if request.use_t660_timing:
                if timing_manager is None:
                    raise MircatDetectorAlignmentError("T660 timing manager was not initialized")
                alignment_readback_path = run_path / "mircat_detector_alignment_2mhz_readback.json"
                alignment_readback = timing_manager.apply_recipe(
                    REPO_ROOT / request.timing_recipe,
                    output_path=alignment_readback_path,
                )
                self.t660_running = True
                self._remember_readback(alignment_readback_path)

            if request.use_t660_timing and request.settle_after_t660_start_s > 0:
                time.sleep(request.settle_after_t660_start_s)
            state_after_t660_start = service.read_state().to_dict()
            actual_after_ttl = service.get_actual_wavelength()
            self.mircat_setpoint = {
                "value": request.wavenumber_cm1,
                "units": "cm^-1",
                "qcl": request.qcl,
                "pulse_rate_hz": request.pulse_rate_hz,
                "pulse_width_ns": request.pulse_width_ns,
                "current_ma": request.current_ma,
                "pulse_mode": pulse_mode_name,
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
                "status": "RUNNING_FOR_ALIGNMENT",
                "request": request.to_dict(),
                "timing_mode": "external_t660" if request.use_t660_timing else "mircat_internal",
                "safe_idle_before_alignment": str(safe_idle_path) if safe_idle_path else None,
                "safe_idle_before_alignment_matches_recipe": (
                    safe_idle_readback.get("matches_recipe") if safe_idle_readback else None
                ),
                "mircat_clear_system_error_result": clear_result,
                "mircat_system_error_word_after_clear": system_error_word,
                "mircat_stop_scan_return_code": stop_scan_status,
                "mircat_cancel_manual_tune_return_code": cancel_manual_tune_status,
                "mircat_pulse_limits": pulse_limits,
                "mircat_pulse_settings": pulse_settings,
                "mircat_wavelength_trigger_readback": wltrig_readback,
                "mircat_laser_parameters_readback": str(laser_parameters_path),
                "mircat_arm_readback": str(arm_readback_path),
                "mircat_wavelength_trigger_after_tune_readback": wltrig_after_tune_readback,
                "mircat_actual_before_t660": actual_before_ttl,
                "mircat_actual_after_t660": actual_after_ttl,
                "hf2li_settings_snapshot": hf2li_readback,
                "t660_alignment_readback": (
                    str(alignment_readback_path) if alignment_readback_path else None
                ),
                "t660_alignment_matches_recipe": (
                    alignment_readback.get("matches_recipe") if alignment_readback else None
                ),
                "state_readback": str(state_path),
                "stop_instruction": (
                    "Use the caller stop control. In the UI, press Emission Off; "
                    "in the hardware-check script, press Enter or run --stop-only."
                ),
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
        safe_idle_applied = False
        if self.t660_running or self.uses_t660_timing:
            try:
                timing_manager = TimingRecipeManager(self.inventory, command_log=command_log)
                timing_manager.apply_recipe(REPO_ROOT / SAFE_IDLE_RECIPE, output_path=safe_idle_path)
                self.t660_running = False
                safe_idle_applied = True
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
            else:
                service.command_log = command_log
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

        hf2li_close_result = None
        if self.hf2li_service is not None:
            try:
                self.hf2li_service.command_log = command_log
                self.hf2li_service.close()
                hf2li_close_result = "closed"
            except Exception as exc:  # noqa: BLE001
                errors.append(f"HF2LI close failed: {exc}")
                hf2li_close_result = f"error: {exc}"
            finally:
                self.hf2li_service = None

        summary = {
            "timestamp_utc": _utc_now(),
            "operator": self.operator,
            "status": "STOPPED" if not errors else "STOP_ERRORS",
            "reason": reason,
            "uses_t660_timing": self.uses_t660_timing,
            "safe_idle_after_alignment": str(safe_idle_path) if safe_idle_applied else None,
            "mircat_state_before_shutdown": state_before,
            "mircat_state_after_shutdown": state_after,
            "hf2li_close_result": hf2li_close_result,
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
        if request.current_ma is not None and request.current_ma <= 0:
            raise MircatDetectorAlignmentError("MIRcat current_ma must be positive when provided")
        if not str(request.hf2li_preset).strip():
            raise MircatDetectorAlignmentError("hf2li_preset must be a non-empty preset name")
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

    @staticmethod
    def _assert_internal_trigger_readback(
        readback: dict[str, Any],
        wavenumber_cm1: float,
    ) -> None:
        if int(readback.get("pulse_mode", -1)) != PULSE_MODE_INTERNAL:
            raise MircatDetectorAlignmentError(f"MIRcat pulse mode readback is not internal: {readback}")
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

    @staticmethod
    def _arm_and_confirm(
        service: MircatService,
        *,
        request: MircatDetectorAlignmentRequest,
        label: str,
    ) -> list[dict[str, Any]]:
        attempts: list[dict[str, Any]] = []
        service.arm()
        deadline = time.time() + max(float(request.poll_interval_s) * 20.0, 10.0)
        attempt = 1
        while time.time() <= deadline:
            direct_armed = service.is_laser_armed()
            state = service.read_state().to_dict()
            armed = bool(direct_armed or state.get("armed"))
            attempts.append(
                {
                    "timestamp_utc": _utc_now(),
                    "label": label,
                    "attempt": attempt,
                    "direct_is_laser_armed": direct_armed,
                    "state": state,
                    "confirmed_armed": armed,
                }
            )
            if armed:
                return attempts
            attempt += 1
            time.sleep(max(float(request.poll_interval_s), 0.1))
        raise MircatDetectorAlignmentError(
            "MIRcat did not read back armed after ArmLaser; TuneToWW was not attempted. "
            "Check key switch, interlock, controller state, and whether another MIRcat UI owns the controller."
        )

    def _configure_hf2li_alignment(
        self,
        *,
        request: MircatDetectorAlignmentRequest,
        run_path: Path,
        command_log: TextIO | None,
    ) -> dict[str, Any]:
        service = HF2LIService.from_config(
            config_path=self.config_path,
            command_log=command_log,
        )
        self.hf2li_service = service
        service.connect()
        preset = service.load_preset(
            request.hf2li_preset,
            presets_path=request.hf2li_presets_path,
        )
        applied = service.apply_preset(preset)
        snapshot_path = run_path / "hf2li_detector_alignment_settings_snapshot.json"
        snapshot = service.export_settings_snapshot(snapshot_path, preset=preset)
        self._remember_readback(snapshot_path)

        preset_settings = preset.settings
        readback = {
            "preset": preset.name,
            "settings_snapshot_path": str(snapshot_path),
            "applied": applied,
            "read_errors": snapshot.get("read_errors", {}),
            "pll_external_reference": preset_settings.get("pll") or {},
            "demodulators": preset_settings.get("demodulators") or [],
            "labone_plotter": preset_settings.get("labone_plotter") or {},
        }
        readback_path = self._write_json(
            run_path / "hf2li_detector_alignment_preset_readback.json",
            readback,
        )
        readback["preset_readback_path"] = str(readback_path)
        self._remember_readback(readback_path)
        self.hf2li_settings_snapshot = dict(readback)
        return readback

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
