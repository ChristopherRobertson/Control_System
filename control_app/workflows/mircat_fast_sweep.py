"""Fast MIRcat sweep workflow for rewired QCL spectral acquisition."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO
import json
import threading
import time

import yaml

from control_app.config_loader import ConfigInventory, REPO_ROOT, load_config_inventory
from control_app.devices.hf2li_service import HF2LIService
from control_app.devices.mircat_service import (
    PROC_TRIG_MODE_INTERNAL,
    PULSE_MODE_INTERNAL,
    UNITS_CM1,
    MircatService,
)
from control_app.manifest import new_manifest, write_manifest
from control_app.workflows.mircat_detector_alignment import (
    HF2LI_PRESETS_PATH,
    MAX_DUTY_CYCLE,
    MIRCAT_WAVENUMBER_MAX_CM1,
    MIRCAT_WAVENUMBER_MIN_CM1,
    SAFE_IDLE_RECIPE,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager


DEFAULT_FAST_SWEEP_RECIPE = "recipes/polystyrene_fast_sweep.yaml"
DEFAULT_T660_REFERENCE_RECIPE = "recipes/hf2li_extref_2mhz.yaml"
DEFAULT_HF2LI_PRESET = "standard_spectral_validation"


class MircatFastSweepError(RuntimeError):
    """Raised when the fast sweep cannot safely run."""


@dataclass(frozen=True)
class MircatFastSweepRequest:
    """Operator-approved continuous MIRcat sweep request."""

    sample_name: str = "Polystyrene"
    start_cm1: float = 2076.0
    stop_cm1: float = 1640.0
    scan_rate_cm1_s: float = 43.6
    repetitions: int = 1
    qcl: int = 1
    pulse_rate_hz: float = 2_000_000.0
    pulse_width_ns: float = 150.0
    current_ma: float | None = 1000.0
    pre_sweep_record_s: float = 1.0
    post_sweep_record_s: float = 1.0
    tec_timeout_s: float = 120.0
    tune_timeout_s: float = 120.0
    poll_interval_s: float = 0.5
    approved_laser_safety_condition: bool = False
    hf2li_preset: str = DEFAULT_HF2LI_PRESET
    hf2li_presets_path: str = HF2LI_PRESETS_PATH
    t660_reference_recipe: str = DEFAULT_T660_REFERENCE_RECIPE
    use_t660_ext_ref: bool = False
    require_rewired_mircat_trig_out_to_hf2li_dio0: bool = True
    require_rewired_mircat_trig_out_to_hf2li_dio1: bool = True
    installed_min_cm1: float = MIRCAT_WAVENUMBER_MIN_CM1
    installed_max_cm1: float = MIRCAT_WAVENUMBER_MAX_CM1
    source_recipe_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def sweep_duration_s(self) -> float:
        return abs(self.stop_cm1 - self.start_cm1) / self.scan_rate_cm1_s * self.repetitions

    @property
    def record_duration_s(self) -> float:
        return self.pre_sweep_record_s + self.sweep_duration_s + self.post_sweep_record_s


class MircatFastSweepWorkflow:
    """Run one fast sweep with HF2LI recording and hardware-marker metadata."""

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
        self.raw_data_paths: list[str] = []
        self.command_log_paths: list[str] = []
        self.device_readback_paths: list[str] = []
        self.mircat_setpoint: dict[str, Any] | None = None
        self.mircat_actual_wavelength: dict[str, Any] | None = None
        self.hf2li_settings_snapshot: dict[str, Any] = {}
        self.t660_reference_started = False

    def run(
        self,
        *,
        request: MircatFastSweepRequest,
        run_dir: str | Path,
        command_log: TextIO | None = None,
    ) -> dict[str, Any]:
        """Run a continuous MIRcat sweep and write traceable acquisition artifacts."""

        self._validate_request(request)
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        if command_log is not None and getattr(command_log, "name", None):
            self._remember_command_log(str(command_log.name))

        request_path = self._write_json(run_path / "fast_sweep_request.json", request.to_dict())
        self._remember_readback(request_path)
        summary: dict[str, Any] | None = None
        errors: list[str] = []
        try:
            startup = self._startup(request, run_path=run_path, command_log=command_log)
            acquisition = self._record_and_sweep(
                request,
                run_path=run_path,
                command_log=command_log,
            )
            summary = self._write_summary(
                request=request,
                run_path=run_path,
                startup=startup,
                acquisition=acquisition,
                errors=[],
            )
        except Exception as exc:  # noqa: BLE001 - exact hardware failure is recorded
            errors.append(str(exc))
            summary = self._write_summary(
                request=request,
                run_path=run_path,
                startup={},
                acquisition={},
                errors=errors,
            )
            raise MircatFastSweepError(str(exc)) from exc
        finally:
            cleanup = self._cleanup(run_path=run_path, command_log=command_log)
            if cleanup.get("errors"):
                errors.extend(str(item) for item in cleanup["errors"])

        if errors:
            raise MircatFastSweepError("; ".join(errors))
        return summary

    def write_manifest(
        self,
        *,
        request: MircatFastSweepRequest,
        run_dir: str | Path,
        errors: list[str] | None = None,
        blocked: bool = False,
        blockers: list[str] | None = None,
    ) -> Path:
        """Write a run manifest for the fast-sweep artifacts."""

        error_list = errors or []
        blocker_list = blockers or []
        t660_recipes = [request.t660_reference_recipe] if request.use_t660_ext_ref else []
        if request.use_t660_ext_ref:
            t660_recipes.append(SAFE_IDLE_RECIPE)
        manifest = new_manifest(
            operator=self.operator,
            inventory=self.inventory,
            t660_recipes=t660_recipes,
            mircat_setpoint=self.mircat_setpoint,
            mircat_actual_wavelength=self.mircat_actual_wavelength,
            hf2li_settings_snapshot=self.hf2li_settings_snapshot,
            raw_data_paths=list(dict.fromkeys(self.raw_data_paths)),
            command_log_paths=list(dict.fromkeys(self.command_log_paths)),
            device_readback_paths=list(dict.fromkeys(self.device_readback_paths)),
            error_state={"has_error": bool(error_list), "errors": error_list},
            blocker_status={
                "blocked": blocked or bool(blocker_list),
                "blockers": blocker_list,
                "next_actions": _next_actions(blocked or bool(blocker_list)),
            },
        )
        manifest["fast_sweep"] = {
            "sample_name": request.sample_name,
            "sweep_duration_s": request.sweep_duration_s,
            "record_duration_s": request.record_duration_s,
            "axis_model": "linear_between_hardware_emission_edges",
            "axis_marker_requirement": _axis_marker_requirement(request),
        }
        return write_manifest(Path(run_dir) / "run_manifest.json", manifest)

    def _startup(
        self,
        request: MircatFastSweepRequest,
        *,
        run_path: Path,
        command_log: TextIO | None,
    ) -> dict[str, Any]:
        timing_readback = None
        if request.use_t660_ext_ref:
            timing_manager = TimingRecipeManager(self.inventory, command_log=command_log)
            safe_idle_path = run_path / "safe_idle_before_fast_sweep_readback.json"
            timing_manager.apply_recipe(REPO_ROOT / SAFE_IDLE_RECIPE, output_path=safe_idle_path)
            self._remember_readback(safe_idle_path)
            reference_path = run_path / "hf2li_extref_2mhz_readback.json"
            timing_readback = timing_manager.apply_recipe(
                REPO_ROOT / request.t660_reference_recipe,
                output_path=reference_path,
            )
            self.t660_reference_started = True
            self._remember_readback(reference_path)

        hf2li = HF2LIService.from_config(config_path=self.config_path, command_log=command_log)
        self.hf2li_service = hf2li
        hf2li.connect()
        preset = hf2li.load_preset(request.hf2li_preset, presets_path=request.hf2li_presets_path)
        applied_preset = hf2li.apply_preset(preset)
        snapshot_path = run_path / "hf2li_fast_sweep_settings_snapshot.json"
        snapshot = hf2li.export_settings_snapshot(snapshot_path, preset=preset)
        self._remember_readback(snapshot_path)
        self.hf2li_settings_snapshot = {
            "preset": preset.name,
            "settings_snapshot_path": str(snapshot_path),
            "applied": applied_preset,
            "read_errors": snapshot.get("read_errors", {}),
            "pll": preset.settings.get("pll") or {},
            "demodulators": preset.settings.get("demodulators") or [],
            "acquisition": preset.settings.get("acquisition") or {},
            "labone_plotter_requirement": (
                "Set LabOne Plotter trigger source to HF2LI DIO1 rising after routing "
                "MIRcat TRIG OUT to the HF2LI reference/marker inputs."
            ),
        }
        hf2li_readback_path = self._write_json(
            run_path / "hf2li_fast_sweep_preset_readback.json",
            self.hf2li_settings_snapshot,
        )
        self._remember_readback(hf2li_readback_path)

        service = MircatService.from_config(config_path=self.config_path, command_log=command_log)
        self.mircat_service = service
        service.initialize()
        clear_result = service.clear_system_error()
        error_word = service.get_system_error_word()
        initial_state = service.read_state().to_dict()
        self._assert_ready_to_arm(initial_state)
        if error_word:
            raise MircatFastSweepError(
                f"MIRcat system error word remained nonzero after clear: {error_word}"
            )
        stop_scan_status = service.stop_scan_if_needed()
        cancel_tune_status = service.cancel_manual_tune()
        pulse_limits = service.get_qcl_pulse_limits(request.qcl)
        self._assert_within_pulse_limits(request, pulse_limits)
        pulse_settings = service.set_qcl_pulse_params(
            qcl=request.qcl,
            pulse_rate_hz=request.pulse_rate_hz,
            pulse_width_ns=request.pulse_width_ns,
            current_ma=request.current_ma,
        )
        trigger_readback = service.set_internal_trigger_params(wavenumber_cm1=request.start_cm1)
        self._assert_internal_trigger_readback(trigger_readback, request.start_cm1)
        self._arm_and_confirm(service, request=request, label="before_tec_wait")
        if not service.wait_for_tecs_ready(
            timeout_s=request.tec_timeout_s,
            poll_interval_s=request.poll_interval_s,
        ):
            raise MircatFastSweepError(
                f"MIRcat TECs were not ready within {request.tec_timeout_s:g} s"
            )
        self._arm_and_confirm(service, request=request, label="before_start_tune")
        service.tune_to_wavenumber(request.start_cm1, qcl=request.qcl)
        if not service.wait_for_tuned(
            timeout_s=request.tune_timeout_s,
            poll_interval_s=request.poll_interval_s,
        ):
            raise MircatFastSweepError(
                f"MIRcat did not report tuned at {request.start_cm1:g} cm^-1 before timeout"
            )
        actual_at_start = service.get_actual_wavelength()
        state_before_record = service.read_state().to_dict()

        self.mircat_setpoint = {
            "sample_name": request.sample_name,
            "scan_type": "fast_continuous_sweep",
            "start_cm1": request.start_cm1,
            "stop_cm1": request.stop_cm1,
            "scan_rate_cm1_s": request.scan_rate_cm1_s,
            "repetitions": request.repetitions,
            "qcl": request.qcl,
            "pulse_rate_hz": request.pulse_rate_hz,
            "pulse_width_ns": request.pulse_width_ns,
            "current_ma": request.current_ma,
            "pulse_mode": "internal",
        }
        self.mircat_actual_wavelength = actual_at_start

        startup = {
            "timestamp_utc": _utc_now(),
            "operator": self.operator,
            "config_hash": self.inventory.config_hash,
            "initial_state": initial_state,
            "state_before_record": state_before_record,
            "clear_system_error_result": clear_result,
            "system_error_word_after_clear": error_word,
            "stop_scan_return_code": stop_scan_status,
            "cancel_manual_tune_return_code": cancel_tune_status,
            "pulse_limits": pulse_limits,
            "pulse_settings": pulse_settings,
            "internal_trigger_readback": trigger_readback,
            "actual_at_start_setpoint": actual_at_start,
            "hf2li_settings_snapshot": self.hf2li_settings_snapshot,
            "t660_reference_readback": timing_readback,
            "required_rewire": _required_rewire(request),
        }
        startup_path = self._write_json(run_path / "fast_sweep_startup_readback.json", startup)
        self._remember_readback(startup_path)
        return startup

    def _record_and_sweep(
        self,
        request: MircatFastSweepRequest,
        *,
        run_path: Path,
        command_log: TextIO | None,
    ) -> dict[str, Any]:
        if self.hf2li_service is None or self.mircat_service is None:
            raise MircatFastSweepError("fast-sweep devices were not started")
        hf2li = self.hf2li_service
        service = self.mircat_service
        hf2li.command_log = command_log
        service.command_log = command_log
        acquisition_settings = self.hf2li_settings_snapshot.get("acquisition") or {}
        demodulators = acquisition_settings.get("demodulators") or [0, 3]
        fields = acquisition_settings.get("fields") or ["x", "y", "r"]
        record_holder: dict[str, Any] = {}
        error_holder: list[BaseException] = []

        hf2li.start_acquisition(demodulators=demodulators, fields=fields)

        def poll_record() -> None:
            try:
                record = hf2li.read_acquisition(request.record_duration_s)
                record["fields"] = list(fields)
                record_holder["record"] = record
            except BaseException as exc:  # noqa: BLE001 - transferred to main thread
                error_holder.append(exc)

        poll_thread = threading.Thread(
            target=poll_record,
            name="hf2li-fast-sweep-poll",
            daemon=True,
        )
        poll_thread.start()
        time.sleep(request.pre_sweep_record_s)
        state_before_emission = service.read_state().to_dict()
        service.turn_emission_on(
            approved_laser_safety_condition=request.approved_laser_safety_condition
        )
        emission_on_utc = _utc_now()
        if not service.is_emission_on():
            raise MircatFastSweepError("MIRcat emission gate did not read back ON")
        state_after_emission = service.read_state().to_dict()
        sweep_start_monotonic = time.monotonic()
        sweep_start_command_utc = _utc_now()
        service.start_sweep_scan(
            start_cm1=request.start_cm1,
            stop_cm1=request.stop_cm1,
            scan_rate_cm1_s=request.scan_rate_cm1_s,
            qcl=request.qcl,
            repetitions=request.repetitions,
        )
        state_after_start = service.read_state().to_dict()
        poll_thread.join(timeout=request.record_duration_s + 10.0)
        if poll_thread.is_alive():
            raise MircatFastSweepError("HF2LI acquisition did not finish before timeout")
        if error_holder:
            raise MircatFastSweepError(f"HF2LI acquisition failed: {error_holder[0]}")
        record = record_holder.get("record")
        if not isinstance(record, dict):
            raise MircatFastSweepError("HF2LI acquisition returned no record")
        state_after_record = service.read_state().to_dict()
        actual_after_record = service.get_actual_wavelength()
        stop_scan_status = service.stop_scan_if_needed()
        service.turn_emission_off()
        state_after_stop = service.read_state().to_dict()
        hf2li.stop_acquisition()

        raw_csv = run_path / "hf2li_raw_fast_sweep.csv"
        summary_csv = run_path / "hf2li_summary_fast_sweep.csv"
        save_summary = hf2li.save_record(
            record,
            raw_csv_path=raw_csv,
            summary_csv_path=summary_csv,
        )
        self._remember_raw(raw_csv)
        self._remember_readback(summary_csv)
        self.mircat_actual_wavelength = actual_after_record

        acquisition = {
            "timestamp_utc": _utc_now(),
            "operator": self.operator,
            "config_hash": self.inventory.config_hash,
            "sample_name": request.sample_name,
            "timing": {
                "record_duration_s": request.record_duration_s,
                "pre_sweep_record_s": request.pre_sweep_record_s,
                "expected_sweep_duration_s": request.sweep_duration_s,
                "post_sweep_record_s": request.post_sweep_record_s,
                "emission_on_utc": emission_on_utc,
                "sweep_start_command_utc": sweep_start_command_utc,
                "sweep_start_monotonic_s": sweep_start_monotonic,
            },
            "axis_model": {
                "mode": "linear_between_hardware_emission_edges",
                "start_cm1": request.start_cm1,
                "stop_cm1": request.stop_cm1,
                "requires_labone_marker_export": True,
                "marker_source": "MIRcat TRIG OUT rewired to HF2LI DIO1",
                "note": (
                    "Use the DIO1 Plotter trigger/marker export to trim detector data "
                    "to actual emission start/stop before converting time to wavenumber."
                ),
            },
            "state_before_emission": state_before_emission,
            "state_after_emission": state_after_emission,
            "state_after_start_sweep": state_after_start,
            "state_after_record": state_after_record,
            "state_after_stop": state_after_stop,
            "actual_after_record": actual_after_record,
            "stop_scan_return_code": stop_scan_status,
            "hf2li_demodulators": demodulators,
            "hf2li_fields": fields,
            "raw_csv_path": str(raw_csv),
            "summary_csv_path": str(summary_csv),
            "hf2li_save_summary": save_summary,
        }
        acquisition_path = self._write_json(
            run_path / "fast_sweep_acquisition_metadata.json",
            acquisition,
        )
        acquisition["metadata_path"] = str(acquisition_path)
        self._remember_readback(acquisition_path)
        return acquisition

    def _cleanup(self, *, run_path: Path, command_log: TextIO | None) -> dict[str, Any]:
        errors: list[str] = []
        cleanup: dict[str, Any] = {
            "timestamp_utc": _utc_now(),
            "operator": self.operator,
            "mircat": None,
            "hf2li": None,
            "t660": None,
            "errors": errors,
        }
        if self.hf2li_service is not None:
            try:
                self.hf2li_service.command_log = command_log
                self.hf2li_service.stop_acquisition()
                self.hf2li_service.close()
                cleanup["hf2li"] = "closed"
            except Exception as exc:  # noqa: BLE001
                errors.append(f"HF2LI cleanup failed: {exc}")
            finally:
                self.hf2li_service = None

        if self.mircat_service is not None:
            try:
                self.mircat_service.command_log = command_log
                self.mircat_service.stop_scan_if_needed()
                self.mircat_service.turn_emission_off()
                if self.mircat_service.is_laser_armed():
                    self.mircat_service.disarm()
                state = self.mircat_service.read_state().to_dict()
                self.mircat_service.deinitialize()
                cleanup["mircat"] = {
                    "safe_state": "scan_stopped_emission_off_disarmed_deinitialized",
                    "state": state,
                }
            except Exception as exc:  # noqa: BLE001
                errors.append(f"MIRcat cleanup failed: {exc}")
            finally:
                self.mircat_service = None

        if self.t660_reference_started:
            try:
                safe_idle_path = run_path / "safe_idle_after_fast_sweep_readback.json"
                timing_manager = TimingRecipeManager(self.inventory, command_log=command_log)
                cleanup["t660"] = timing_manager.apply_recipe(
                    REPO_ROOT / SAFE_IDLE_RECIPE,
                    output_path=safe_idle_path,
                )
                self._remember_readback(safe_idle_path)
                self.t660_reference_started = False
            except Exception as exc:  # noqa: BLE001
                errors.append(f"T660 safe_idle failed: {exc}")

        cleanup_path = self._write_json(run_path / "fast_sweep_cleanup_summary.json", cleanup)
        self._remember_readback(cleanup_path)
        return cleanup

    def _write_summary(
        self,
        *,
        request: MircatFastSweepRequest,
        run_path: Path,
        startup: dict[str, Any],
        acquisition: dict[str, Any],
        errors: list[str],
    ) -> dict[str, Any]:
        summary = {
            "timestamp_utc": _utc_now(),
            "operator": self.operator,
            "config_hash": self.inventory.config_hash,
            "status": "PASS" if not errors else "ERROR",
            "sample_name": request.sample_name,
            "request": request.to_dict(),
            "startup": startup,
            "acquisition": acquisition,
            "raw_data_paths": list(dict.fromkeys(self.raw_data_paths)),
            "device_readback_paths": list(dict.fromkeys(self.device_readback_paths)),
            "errors": errors,
            "labone_plotter_setup": _labone_plotter_setup(request),
        }
        summary_path = self._write_json(run_path / "fast_sweep_summary.json", summary)
        self._remember_readback(summary_path)
        return summary

    @staticmethod
    def _validate_request(request: MircatFastSweepRequest) -> None:
        if not request.approved_laser_safety_condition:
            raise MircatFastSweepError(
                "approved_laser_safety_condition=True is required before opening MIRcat emission"
            )
        if (
            not request.use_t660_ext_ref
            and request.require_rewired_mircat_trig_out_to_hf2li_dio0 is not True
        ):
            raise MircatFastSweepError(
                "This fast-sweep workflow requires MIRcat TRIG OUT routed to HF2LI DIO0 EXT REF."
            )
        if request.require_rewired_mircat_trig_out_to_hf2li_dio1 is not True:
            raise MircatFastSweepError(
                "This fast-sweep workflow requires MIRcat TRIG OUT rewired to HF2LI DIO1."
            )
        if request.qcl < 1 or request.qcl > 4:
            raise MircatFastSweepError("QCL must be in the SDK-supported range 1..4")
        for value in (request.start_cm1, request.stop_cm1):
            if value < request.installed_min_cm1 or value > request.installed_max_cm1:
                raise MircatFastSweepError(
                    f"MIRcat wavenumber {value:g} cm^-1 is outside the installed range "
                    f"{request.installed_min_cm1:g}-{request.installed_max_cm1:g} cm^-1"
                )
        if request.scan_rate_cm1_s <= 0:
            raise MircatFastSweepError("scan_rate_cm1_s must be positive")
        if request.repetitions < 1 or request.repetitions > 65535:
            raise MircatFastSweepError("repetitions must be in the range 1..65535")
        if request.pre_sweep_record_s < 0 or request.post_sweep_record_s < 0:
            raise MircatFastSweepError("pre/post sweep record times cannot be negative")
        if request.current_ma is not None and request.current_ma <= 0:
            raise MircatFastSweepError("current_ma must be positive when provided")
        duty_cycle = request.pulse_rate_hz * request.pulse_width_ns * 1.0e-9
        if duty_cycle > MAX_DUTY_CYCLE + 1e-9:
            raise MircatFastSweepError(
                f"MIRcat pulse duty cycle {duty_cycle:.6f} exceeds {MAX_DUTY_CYCLE:.2f}"
            )

    @staticmethod
    def _assert_ready_to_arm(state: dict[str, Any]) -> None:
        if not state.get("connected"):
            raise MircatFastSweepError("MIRcat SDK did not report a laser connection")
        if not state.get("interlock_set"):
            raise MircatFastSweepError("MIRcat interlock is not set")
        if not state.get("key_switch_set"):
            raise MircatFastSweepError("MIRcat key switch is not set")

    @staticmethod
    def _assert_within_pulse_limits(
        request: MircatFastSweepRequest,
        limits: dict[str, Any],
    ) -> None:
        max_rate = float(limits.get("max_pulse_rate_hz") or 0.0)
        max_width = float(limits.get("max_pulse_width_ns") or 0.0)
        if max_rate > 0 and request.pulse_rate_hz > max_rate + 1.0:
            raise MircatFastSweepError(
                f"Requested MIRcat pulse rate {request.pulse_rate_hz:g} Hz exceeds limit {max_rate:g} Hz"
            )
        if max_width > 0 and request.pulse_width_ns > max_width + 1e-6:
            raise MircatFastSweepError(
                f"Requested MIRcat pulse width {request.pulse_width_ns:g} ns exceeds limit {max_width:g} ns"
            )

    @staticmethod
    def _assert_internal_trigger_readback(
        readback: dict[str, Any],
        wavenumber_cm1: float,
    ) -> None:
        if int(readback.get("pulse_mode", -1)) != PULSE_MODE_INTERNAL:
            raise MircatFastSweepError(f"MIRcat pulse mode readback is not internal: {readback}")
        if int(readback.get("process_trigger_mode", -1)) != PROC_TRIG_MODE_INTERNAL:
            raise MircatFastSweepError(
                f"MIRcat process trigger readback is not internal: {readback}"
            )
        if int(readback.get("units", -1)) != UNITS_CM1:
            raise MircatFastSweepError(f"MIRcat trigger units readback is not cm^-1: {readback}")
        for field in ("start", "stop"):
            if abs(float(readback.get(field, 0.0)) - float(wavenumber_cm1)) > 0.05:
                raise MircatFastSweepError(
                    f"MIRcat trigger {field} readback does not match requested start: {readback}"
                )

    @staticmethod
    def _arm_and_confirm(
        service: MircatService,
        *,
        request: MircatFastSweepRequest,
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
        raise MircatFastSweepError(
            "MIRcat did not read back armed after ArmLaser; TuneToWW was not attempted. "
            "Check key switch, interlock, controller state, and whether another MIRcat UI owns the controller."
        )

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

    @staticmethod
    def _write_json(path: str | Path, data: Any) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target


def load_fast_sweep_request(
    recipe_path: str | Path = DEFAULT_FAST_SWEEP_RECIPE,
    *,
    overrides: dict[str, Any] | None = None,
) -> MircatFastSweepRequest:
    """Build a fast-sweep request from YAML plus explicit overrides."""

    path = Path(recipe_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    with path.open("r", encoding="utf-8") as handle:
        recipe = yaml.safe_load(handle) or {}
    if not isinstance(recipe, dict):
        raise MircatFastSweepError(f"fast-sweep recipe must be a mapping: {path}")

    sample = recipe.get("sample") if isinstance(recipe.get("sample"), dict) else {}
    probe = recipe.get("probe") if isinstance(recipe.get("probe"), dict) else {}
    mircat = probe.get("mircat") if isinstance(probe.get("mircat"), dict) else {}
    sweep = probe.get("fast_sweep_cm1") if isinstance(probe.get("fast_sweep_cm1"), dict) else {}
    installed = (
        sweep.get("installed_range_cm1")
        if isinstance(sweep.get("installed_range_cm1"), dict)
        else {}
    )
    hf2li = recipe.get("hf2li") if isinstance(recipe.get("hf2li"), dict) else {}
    timing = recipe.get("timing") if isinstance(recipe.get("timing"), dict) else {}
    wiring = recipe.get("required_wiring") if isinstance(recipe.get("required_wiring"), dict) else {}
    request = MircatFastSweepRequest(
        sample_name=str(sample.get("name") or recipe.get("name") or path.stem),
        start_cm1=float(sweep.get("start", mircat.get("wavenumber_cm1", 2076.0))),
        stop_cm1=float(sweep.get("stop", 1640.0)),
        scan_rate_cm1_s=float(sweep.get("scan_rate_cm1_s", 43.6)),
        repetitions=int(sweep.get("repetitions", 1)),
        qcl=int(mircat.get("qcl", probe.get("qcl", 1))),
        pulse_rate_hz=float(mircat.get("pulse_rate_hz", 2_000_000.0)),
        pulse_width_ns=float(mircat.get("pulse_width_ns", 150.0)),
        current_ma=_optional_float(mircat.get("current_ma", 1000.0)),
        pre_sweep_record_s=float(timing.get("pre_sweep_record_s", 1.0)),
        post_sweep_record_s=float(timing.get("post_sweep_record_s", 1.0)),
        tec_timeout_s=float(mircat.get("tec_timeout_s", 120.0)),
        tune_timeout_s=float(mircat.get("tune_timeout_s", 120.0)),
        poll_interval_s=float(mircat.get("poll_interval_s", 0.5)),
        approved_laser_safety_condition=bool(recipe.get("approved_laser_safety_condition")),
        hf2li_preset=str(recipe.get("hf2li_preset") or hf2li.get("preset") or DEFAULT_HF2LI_PRESET),
        t660_reference_recipe=str(
            timing.get("t660_reference_recipe") or DEFAULT_T660_REFERENCE_RECIPE
        ),
        use_t660_ext_ref=bool(timing.get("use_t660_ext_ref", False)),
        require_rewired_mircat_trig_out_to_hf2li_dio0=bool(
            wiring.get("mircat_trig_out_to_hf2li_dio0", True)
        ),
        require_rewired_mircat_trig_out_to_hf2li_dio1=bool(
            wiring.get("mircat_trig_out_to_hf2li_dio1", True)
        ),
        installed_min_cm1=float(installed.get("min", MIRCAT_WAVENUMBER_MIN_CM1)),
        installed_max_cm1=float(installed.get("max", MIRCAT_WAVENUMBER_MAX_CM1)),
        source_recipe_path=str(path),
    )
    return apply_fast_sweep_overrides(request, overrides or {})


def apply_fast_sweep_overrides(
    request: MircatFastSweepRequest,
    overrides: dict[str, Any],
) -> MircatFastSweepRequest:
    values = {
        key: value
        for key, value in overrides.items()
        if value is not None and hasattr(request, key)
    }
    if not values:
        return request
    return replace(request, **values)


def _axis_marker_requirement(request: MircatFastSweepRequest) -> str:
    if request.use_t660_ext_ref:
        return (
            "T660-2 CHA provides HF2LI DIO0 EXT REF, and MIRcat TRIG OUT must be "
            "captured/exported from HF2LI DIO1 for time-to-wavenumber trimming. "
            "Use this optional mode only after verifying the reference is suitable for the sweep."
        )
    return (
        "MIRcat TRIG OUT must provide the HF2LI reference/marker path and be "
        "captured/exported from LabOne Plotter for article-grade time-to-wavenumber mapping."
    )


def _required_rewire(request: MircatFastSweepRequest) -> dict[str, str]:
    if request.use_t660_ext_ref:
        return {
            "hf2li_ext_ref": "T660-2 CHA -> HF2LI DIO0",
            "plotter_trigger": "MIRcat TRIG OUT -> HF2LI DIO1",
            "mircat_trig_in": "disconnect T660-2 CHB from MIRcat TRIG IN for this sweep",
        }
    return {
        "hf2li_ext_ref": "MIRcat TRIG OUT -> HF2LI DIO0, directly or through a splitter",
        "plotter_trigger": "MIRcat TRIG OUT -> HF2LI DIO1, directly or through a splitter",
        "mircat_trig_in": "disconnect T660-2 CHB from MIRcat TRIG IN for this sweep",
    }


def _labone_plotter_setup(request: MircatFastSweepRequest) -> list[str]:
    if request.use_t660_ext_ref:
        return [
            "T660-2 CHA -> HF2LI DIO0 for EXT REF.",
            "MIRcat TRIG OUT -> HF2LI DIO1 for LabOne Plotter trigger/marker.",
            "Set Plotter trigger to DIO1 rising in LabOne; demodulator transfer trigger remains continuous.",
        ]
    return [
        "MIRcat TRIG OUT -> HF2LI DIO0 for phase-coherent EXT REF.",
        "MIRcat TRIG OUT -> HF2LI DIO1 for LabOne Plotter trigger/marker.",
        "Set Plotter trigger to DIO1 rising in LabOne; demodulator transfer trigger remains continuous.",
    ]


def _next_actions(blocked: bool) -> list[str]:
    if not blocked:
        return []
    return [
        "Confirm the physical rewire: MIRcat TRIG OUT to HF2LI DIO0 EXT REF and HF2LI DIO1 Plotter trigger.",
        "Open LabOne Plotter, set the trigger to DIO1 rising, and verify the marker appears before using the run for article claims.",
        "Close the manufacturer MIRcat UI before rerunning because the SDK controller is single-client.",
    ]


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
