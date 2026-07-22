"""Real MIRcat SDK service for the Daylight probe laser."""

from __future__ import annotations

from ctypes import (
    POINTER,
    byref,
    c_bool,
    c_float,
    c_uint8,
    c_uint16,
    c_uint32,
    cdll,
)
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO
import os
import sys
import time

from control_app.config_loader import REPO_ROOT, load_hardware_config


RET_SUCCESS = 0
RET_NO_SYSTEM_FOUND = 30
RET_INITIALIZATION_FAILURE = 32
RET_STOP_SCAN_FAILURE = 67
RET_START_SWEEPSCAN_FAILURE = 71
RET_WW_OUTOFTUNINGRANGE = 80
RET_NO_SCAN_INPROGRESS = 81
RET_EMISSION_ON_FAILURE = 82
RET_EMISSION_ALREADY_OFF = 83
RET_EMISSION_OFF_FAILURE = 84
RET_EMISSION_ALREADY_ON = 85
RET_PULSERATE_OUTOFRANGE = 86
RET_PULSEWIDTH_OUTOFRANGE = 87
RET_CURRENT_OUTOFRANGE = 88
RET_SAVE_SETTINGS_FAILURE = 89
RET_QCL_NUM_OUTOFRANGE = 90
RET_LASER_ALREADY_ARMED = 91
RET_LASER_ALREADY_DISARMED = 92
RET_LASER_NOT_ARMED = 93
RET_LASER_NOT_TUNED = 94
RET_TECS_NOT_AT_SET_TEMPERATURE = 95
RET_CW_NOT_ALLOWED_ON_QCL = 96
RET_INVALID_LASER_MODE = 97
RET_COMM_ERROR = 100
RET_NOT_INITIALIZED = 101
RET_ALREADY_CREATED = 102
RET_START_SWEEP_ADVANCED_SCAN_FAILURE = 103
RET_PASSED_NULL_POINTER = 105
RET_WARNING_DEPRECATED_PARAMETER = 117

UNITS_MICRONS = 1
UNITS_CM1 = 2
PULSE_MODE_INTERNAL = 1
PULSE_MODE_EXTERNAL_TRIGGER = 2
PULSE_MODE_EXTERNAL_PASSTHRU = 3
PROC_TRIG_MODE_INTERNAL = 1
PROC_TRIG_MODE_EXTERNAL = 2
PROC_TRIG_MODE_MANUAL = 3
STATUS_MASK_SCANNING = 0x00000020
STATUS_MASK_MANUAL_TUNING = 0x00000040

RETURN_CODE_NAMES = {
    RET_SUCCESS: "SUCCESS",
    RET_NO_SYSTEM_FOUND: "NO_SYSTEM_FOUND",
    RET_INITIALIZATION_FAILURE: "INITIALIZATION_FAILURE",
    RET_STOP_SCAN_FAILURE: "STOP_SCAN_FAILURE",
    RET_START_SWEEPSCAN_FAILURE: "START_SWEEPSCAN_FAILURE",
    RET_WW_OUTOFTUNINGRANGE: "WW_OUTOFTUNINGRANGE",
    RET_NO_SCAN_INPROGRESS: "NO_SCAN_INPROGRESS",
    RET_EMISSION_ON_FAILURE: "EMISSION_ON_FAILURE",
    RET_EMISSION_ALREADY_OFF: "EMISSION_ALREADY_OFF",
    RET_EMISSION_OFF_FAILURE: "EMISSION_OFF_FAILURE",
    RET_EMISSION_ALREADY_ON: "EMISSION_ALREADY_ON",
    RET_PULSERATE_OUTOFRANGE: "PULSERATE_OUTOFRANGE",
    RET_PULSEWIDTH_OUTOFRANGE: "PULSEWIDTH_OUTOFRANGE",
    RET_CURRENT_OUTOFRANGE: "CURRENT_OUTOFRANGE",
    RET_SAVE_SETTINGS_FAILURE: "SAVE_SETTINGS_FAILURE",
    RET_QCL_NUM_OUTOFRANGE: "QCL_NUM_OUTOFRANGE",
    RET_LASER_ALREADY_ARMED: "LASER_ALREADY_ARMED",
    RET_LASER_ALREADY_DISARMED: "LASER_ALREADY_DISARMED",
    RET_LASER_NOT_ARMED: "LASER_NOT_ARMED",
    RET_LASER_NOT_TUNED: "LASER_NOT_TUNED",
    RET_TECS_NOT_AT_SET_TEMPERATURE: "TECS_NOT_AT_SET_TEMPERATURE",
    RET_CW_NOT_ALLOWED_ON_QCL: "CW_NOT_ALLOWED_ON_QCL",
    RET_INVALID_LASER_MODE: "INVALID_LASER_MODE",
    RET_COMM_ERROR: "COMM_ERROR",
    RET_NOT_INITIALIZED: "NOT_INITIALIZED",
    RET_ALREADY_CREATED: "ALREADY_CREATED",
    RET_START_SWEEP_ADVANCED_SCAN_FAILURE: "START_SWEEP_ADVANCED_SCAN_FAILURE",
    RET_PASSED_NULL_POINTER: "PASSED_NULL_POINTER",
    RET_WARNING_DEPRECATED_PARAMETER: "WARNING_DEPRECATED_PARAMETER",
}


class MircatError(RuntimeError):
    """Base error for MIRcat service failures."""


class MircatConfigurationError(MircatError):
    """Raised when MIRcat configuration or SDK runtime setup is unusable."""


class MircatCommandError(MircatError):
    """Raised when a MIRcat SDK call returns an unexpected code."""


class MircatSafetyError(MircatError):
    """Raised when a requested laser action is not safety-approved."""


@dataclass(frozen=True)
class MircatState:
    """State snapshot from the real MIRcat SDK."""

    timestamp_utc: str
    connected: bool | None = None
    api_version: str | None = None
    num_qcls: int | None = None
    interlock_set: bool | None = None
    key_switch_set: bool | None = None
    armed: bool | None = None
    tec_ready: bool | None = None
    tuned: bool | None = None
    set_wavelength: float | None = None
    set_wavelength_units: str | None = None
    preferred_qcl: int | None = None
    actual_wavelength: float | None = None
    actual_wavelength_units: str | None = None
    light_valid: bool | None = None
    emission_on: bool | None = None
    scan_in_progress: bool | None = None
    scan_active: bool | None = None
    scan_paused: bool | None = None
    current_scan_number: int | None = None
    scan_percent: int | None = None
    scan_current_wavelength: float | None = None
    scan_current_wavelength_units: str | None = None
    scan_waiting_process_trigger: bool | None = None
    scan_tec_in_progress: bool | None = None
    scan_motion_in_progress: bool | None = None
    status_mask: int | None = None
    status_mask_scanning: bool | None = None
    manual_tuning: bool | None = None
    active_qcl: int | None = None
    qcl_pulse_rate_hz: float | None = None
    qcl_pulse_width_ns: float | None = None
    system_error_word: int | None = None
    last_return_code: int | None = None
    last_return_code_name: str | None = None
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable state dictionary."""

        return asdict(self)


class MircatService:
    """Thin ctypes wrapper around the real MIRcat SDK DLL."""

    def __init__(
        self,
        device_config: dict[str, Any],
        *,
        sdk_path: str | Path | None = None,
        command_log: TextIO | None = None,
    ) -> None:
        self.device_config = device_config
        self.sdk_path = sdk_path
        self.command_log = command_log
        self._sdk = None
        self._initialized = False
        self.last_return_code: int | None = None

    @classmethod
    def from_config(
        cls,
        *,
        config_path: str | Path | None = None,
        sdk_path: str | Path | None = None,
        command_log: TextIO | None = None,
    ) -> "MircatService":
        """Create a MIRcat service from hardware_configuration.yaml."""

        config, _, _ = load_hardware_config(config_path)
        devices = config.get("devices") or {}
        device_config = devices.get("mircat")
        if not isinstance(device_config, dict):
            raise MircatConfigurationError("mircat missing from hardware configuration")
        return cls(device_config, sdk_path=sdk_path, command_log=command_log)

    def initialize(self) -> None:
        """Load the SDK and initialize the real MIRcat controller."""

        if self._sdk is None:
            self._sdk = self._load_sdk()
            self._bind_functions()
        self._check(self._call("MIRcatSDK_Initialize"), "MIRcatSDK_Initialize")
        self._initialized = True

    def deinitialize(self) -> None:
        """Deinitialize the SDK session if it is active."""

        if self._sdk is None:
            return
        status = self._call("MIRcatSDK_DeInitialize")
        if status not in {RET_SUCCESS, RET_NOT_INITIALIZED}:
            self._raise(status, "MIRcatSDK_DeInitialize")
        self._initialized = False
        self._sdk = None

    def get_api_version(self) -> str:
        """Return the SDK API version string."""

        major = c_uint16()
        minor = c_uint16()
        patch = c_uint16()
        self._check(
            self._call("MIRcatSDK_GetAPIVersion", byref(major), byref(minor), byref(patch)),
            "MIRcatSDK_GetAPIVersion",
        )
        return f"{major.value}.{minor.value}.{patch.value}"

    def get_num_installed_qcls(self) -> int:
        """Return the number of installed QCL channels."""

        count = c_uint8()
        self._check(
            self._call("MIRcatSDK_GetNumInstalledQcls", byref(count)),
            "MIRcatSDK_GetNumInstalledQcls",
        )
        return int(count.value)

    def is_connected(self) -> bool:
        """Return whether the SDK reports a valid laser connection."""

        return self._bool_call("MIRcatSDK_IsConnectedToLaser")

    def is_interlock_set(self) -> bool:
        """Return whether the interlock circuit is closed."""

        return self._bool_call("MIRcatSDK_IsInterlockedStatusSet")

    def is_key_switch_set(self) -> bool:
        """Return whether the key switch is set."""

        return self._bool_call("MIRcatSDK_IsKeySwitchStatusSet")

    def is_laser_armed(self) -> bool:
        """Return whether the laser is armed."""

        return self._bool_call("MIRcatSDK_IsLaserArmed")

    def are_tecs_ready(self) -> bool:
        """Return whether all TECs are at set temperature."""

        return self._bool_call("MIRcatSDK_AreTECsAtSetTemperature")

    def is_tuned(self) -> bool:
        """Return whether the laser is tuned."""

        return self._bool_call("MIRcatSDK_IsTuned")

    def is_emission_on(self) -> bool:
        """Return whether the MIRcat emission gate is on."""

        return self._bool_call("MIRcatSDK_IsEmissionOn")

    def get_system_error_word(self) -> int:
        """Return the MIRcat system error word."""

        error_word = c_uint16()
        self._check(
            self._call("MIRcatSDK_GetSystemErrorWord", byref(error_word)),
            "MIRcatSDK_GetSystemErrorWord",
        )
        return int(error_word.value)

    def get_status_mask(self) -> int:
        """Return the MIRcat status mask."""

        status_mask = c_uint32()
        self._check(
            self._call("MIRcatSDK_GetStatusMask", byref(status_mask)),
            "MIRcatSDK_GetStatusMask",
        )
        return int(status_mask.value)

    def clear_system_error(self) -> bool:
        """Attempt to clear a system error and return the SDK's boolean result."""

        cleared = c_bool(False)
        self._check(
            self._call("MIRcatSDK_ClearSystemError", byref(cleared)),
            "MIRcatSDK_ClearSystemError",
        )
        return bool(cleared.value)

    def arm(self) -> None:
        """Arm the laser, accepting the SDK's already-armed return code."""

        status = self._call("MIRcatSDK_ArmLaser")
        if status not in {RET_SUCCESS, RET_LASER_ALREADY_ARMED}:
            self._raise(status, "MIRcatSDK_ArmLaser")

    def disarm(self) -> None:
        """Disarm the laser, accepting the SDK's already-disarmed return code."""

        status = self._call("MIRcatSDK_DisarmLaser")
        if status not in {RET_SUCCESS, RET_LASER_ALREADY_DISARMED, RET_LASER_ALREADY_ARMED}:
            self._raise(status, "MIRcatSDK_DisarmLaser")

    def wait_for_tecs_ready(self, *, timeout_s: float, poll_interval_s: float) -> bool:
        """Poll TEC readiness until ready or timeout."""

        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self.are_tecs_ready():
                return True
            time.sleep(poll_interval_s)
        return False

    def tune_to_wavenumber(self, wavenumber_cm1: float, *, qcl: int) -> None:
        """Tune to a wavenumber in cm^-1 using the preferred QCL."""

        self._check(
            self._call(
                "MIRcatSDK_TuneToWW",
                c_float(float(wavenumber_cm1)),
                c_uint8(UNITS_CM1),
                c_uint8(int(qcl)),
            ),
            "MIRcatSDK_TuneToWW",
        )

    def start_sweep_scan(
        self,
        *,
        start_cm1: float,
        stop_cm1: float,
        scan_rate_cm1_s: float,
        qcl: int,
        repetitions: int = 1,
    ) -> None:
        """Start a unidirectional sweep scan in cm^-1."""

        self._check(
            self._call(
                "MIRcatSDK_StartSweepScan",
                c_float(float(start_cm1)),
                c_float(float(stop_cm1)),
                c_float(float(scan_rate_cm1_s)),
                c_uint8(UNITS_CM1),
                c_uint16(int(repetitions)),
                c_bool(False),
                c_uint8(int(qcl)),
            ),
            "MIRcatSDK_StartSweepScan",
        )

    def wait_for_tuned(self, *, timeout_s: float, poll_interval_s: float) -> bool:
        """Poll tuned status until tuned or timeout."""

        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self.is_tuned():
                return True
            time.sleep(poll_interval_s)
        return False

    def get_set_wavelength(self) -> dict[str, Any]:
        """Return the current target wavelength/wavenumber readback."""

        value = c_float()
        units = c_uint8()
        qcl = c_uint8()
        self._check(
            self._call("MIRcatSDK_GetTuneWW", byref(value), byref(units), byref(qcl)),
            "MIRcatSDK_GetTuneWW",
        )
        return {
            "value": float(value.value),
            "units": units_name(int(units.value)),
            "preferred_qcl": int(qcl.value),
        }

    def get_scan_status(self) -> dict[str, Any]:
        """Return the active scan/tune status fields from the SDK."""

        in_progress = c_bool(False)
        active = c_bool(False)
        paused = c_bool(False)
        current_scan = c_uint16()
        percent = c_uint16()
        current_ww = c_float()
        units = c_uint8()
        tec_in_progress = c_bool(False)
        motion_in_progress = c_bool(False)
        self._check(
            self._call(
                "MIRcatSDK_GetScanStatus",
                byref(in_progress),
                byref(active),
                byref(paused),
                byref(current_scan),
                byref(percent),
                byref(current_ww),
                byref(units),
                byref(tec_in_progress),
                byref(motion_in_progress),
            ),
            "MIRcatSDK_GetScanStatus",
        )
        return {
            "scan_in_progress": bool(in_progress.value),
            "scan_active": bool(active.value),
            "scan_paused": bool(paused.value),
            "current_scan_number": int(current_scan.value),
            "scan_percent": int(percent.value),
            "scan_current_wavelength": float(current_ww.value),
            "scan_current_wavelength_units": units_name(int(units.value)),
            "scan_tec_in_progress": bool(tec_in_progress.value),
            "scan_motion_in_progress": bool(motion_in_progress.value),
        }

    def get_scan_waiting_process_trigger(self) -> bool:
        """Return whether a scan is waiting for a process trigger."""

        waiting = c_bool(False)
        self._check(
            self._call("MIRcatSDK_GetScanWaitingProcessTrigger", byref(waiting)),
            "MIRcatSDK_GetScanWaitingProcessTrigger",
        )
        return bool(waiting.value)

    def get_active_qcl(self) -> int:
        """Return the active QCL reported by the SDK."""

        qcl = c_uint8()
        self._check(
            self._call("MIRcatSDK_GetActiveQcl", byref(qcl)),
            "MIRcatSDK_GetActiveQcl",
        )
        return int(qcl.value)

    def get_qcl_pulse_rate(self, qcl: int) -> float:
        """Return the pulse rate for a QCL in Hz."""

        value = c_float()
        self._check(
            self._call("MIRcatSDK_GetQCLPulseRate", c_uint8(int(qcl)), byref(value)),
            "MIRcatSDK_GetQCLPulseRate",
        )
        return float(value.value)

    def get_qcl_pulse_width(self, qcl: int) -> float:
        """Return the pulse width for a QCL in nanoseconds."""

        value = c_float()
        self._check(
            self._call("MIRcatSDK_GetQCLPulseWidth", c_uint8(int(qcl)), byref(value)),
            "MIRcatSDK_GetQCLPulseWidth",
        )
        return float(value.value)

    def get_qcl_current(self, qcl: int) -> float:
        """Return the current setting for a QCL in milliamps."""

        value = c_float()
        self._check(
            self._call("MIRcatSDK_GetQCLCurrent", c_uint8(int(qcl)), byref(value)),
            "MIRcatSDK_GetQCLCurrent",
        )
        return float(value.value)

    def set_qcl_pulse_params(
        self,
        *,
        qcl: int,
        pulse_rate_hz: float,
        pulse_width_ns: float,
        current_ma: float | None = None,
    ) -> dict[str, Any]:
        """Set pulse rate/width, preserving current unless a value is explicitly supplied."""

        previous_current_ma = self.get_qcl_current(qcl)
        current_ma_used = previous_current_ma if current_ma is None else float(current_ma)
        self._check(
            self._call(
                "MIRcatSDK_SetQCLParams",
                c_uint8(int(qcl)),
                c_float(float(pulse_rate_hz)),
                c_float(float(pulse_width_ns)),
                c_float(float(current_ma_used)),
            ),
            "MIRcatSDK_SetQCLParams",
        )
        return {
            "qcl": int(qcl),
            "pulse_rate_hz": self.get_qcl_pulse_rate(qcl),
            "pulse_width_ns": self.get_qcl_pulse_width(qcl),
            "preserved_current_ma": previous_current_ma,
            "current_ma_used": current_ma_used,
            "current_source": "preserved_existing" if current_ma is None else "requested",
        }

    def get_qcl_pulse_limits(self, qcl: int) -> dict[str, float]:
        """Return pulse-rate, pulse-width, and duty-cycle limits for a QCL."""

        max_rate_hz = c_float()
        max_width_ns = c_float()
        max_duty_cycle = c_float()
        self._check(
            self._call(
                "MIRcatSDK_GetQCLPulseLimits",
                c_uint8(int(qcl)),
                byref(max_rate_hz),
                byref(max_width_ns),
                byref(max_duty_cycle),
            ),
            "MIRcatSDK_GetQCLPulseLimits",
        )
        return {
            "qcl": int(qcl),
            "max_pulse_rate_hz": float(max_rate_hz.value),
            "max_pulse_width_ns": float(max_width_ns.value),
            "max_duty_cycle": float(max_duty_cycle.value),
        }

    def get_wavelength_trigger_params(self) -> dict[str, Any]:
        """Return MIRcat wavelength-trigger/pulse-trigger settings."""

        pulse_mode = c_uint8()
        proc_mode = c_uint8()
        start = c_float()
        stop = c_float()
        interval = c_float()
        units = c_uint8()
        dwell_us = c_uint32()
        after_off_us = c_uint32()
        self._check(
            self._call(
                "MIRcatSDK_GetWlTrigParams",
                byref(pulse_mode),
                byref(proc_mode),
                byref(start),
                byref(stop),
                byref(interval),
                byref(units),
                byref(dwell_us),
                byref(after_off_us),
            ),
            "MIRcatSDK_GetWlTrigParams",
        )
        return {
            "pulse_mode": int(pulse_mode.value),
            "pulse_mode_name": pulse_mode_name(int(pulse_mode.value)),
            "process_trigger_mode": int(proc_mode.value),
            "process_trigger_mode_name": process_trigger_mode_name(int(proc_mode.value)),
            "start": float(start.value),
            "stop": float(stop.value),
            "interval": float(interval.value),
            "units": int(units.value),
            "units_name": units_name(int(units.value)),
            "dwell_us": int(dwell_us.value),
            "after_off_us": int(after_off_us.value),
        }

    def set_wavelength_trigger_params(
        self,
        *,
        pulse_mode: int,
        process_trigger_mode: int,
        start: float,
        stop: float,
        interval: float,
        units: int,
        dwell_us: int = 0,
        after_off_us: int = 0,
    ) -> dict[str, Any]:
        """Set MIRcat wavelength-trigger/pulse-trigger settings and return readback."""

        self._check(
            self._call(
                "MIRcatSDK_SetWlTrigParams",
                c_uint8(int(pulse_mode)),
                c_uint8(int(process_trigger_mode)),
                c_float(float(start)),
                c_float(float(stop)),
                c_float(float(interval)),
                c_uint8(int(units)),
                c_uint32(int(dwell_us)),
                c_uint32(int(after_off_us)),
            ),
            "MIRcatSDK_SetWlTrigParams",
        )
        return self.get_wavelength_trigger_params()

    def get_wavelength_trigger_pulse_width_us(self) -> int:
        """Return the DB9 wavelength-trigger output pulse width in microseconds."""

        width_us = c_uint16()
        self._check(
            self._call("MIRcatSDK_GetWlTrigPulseWidth", byref(width_us)),
            "MIRcatSDK_GetWlTrigPulseWidth",
        )
        return int(width_us.value)

    def set_wavelength_trigger_pulse_width_us(self, width_us: int) -> int:
        """Set and verify the DB9 wavelength-trigger output pulse width."""

        width = int(width_us)
        if width <= 0 or width > 65535:
            raise ValueError("Wavelength-trigger pulse width must be from 1 through 65535 us")
        self._check(
            self._call("MIRcatSDK_SetWlTrigPulseWidth", c_uint16(width)),
            "MIRcatSDK_SetWlTrigPulseWidth",
        )
        return self.get_wavelength_trigger_pulse_width_us()

    def set_external_trigger_params(self, *, wavenumber_cm1: float) -> dict[str, Any]:
        """Configure one optical pulse per external TTL rising edge."""

        return self.set_wavelength_trigger_params(
            pulse_mode=PULSE_MODE_EXTERNAL_TRIGGER,
            process_trigger_mode=PROC_TRIG_MODE_INTERNAL,
            start=float(wavenumber_cm1),
            stop=float(wavenumber_cm1),
            interval=0.0,
            units=UNITS_CM1,
            dwell_us=0,
            after_off_us=0,
        )

    def set_external_sweep_trigger_params(
        self,
        *,
        start_cm1: float,
        stop_cm1: float,
        wavelength_trigger_interval_cm1: float,
        external_process_trigger: bool = False,
    ) -> dict[str, Any]:
        """Configure external laser pulses and sparse sweep wavelength markers."""

        interval = float(wavelength_trigger_interval_cm1)
        if interval <= 0:
            raise ValueError("wavelength_trigger_interval_cm1 must be positive")
        return self.set_wavelength_trigger_params(
            pulse_mode=PULSE_MODE_EXTERNAL_TRIGGER,
            process_trigger_mode=(
                PROC_TRIG_MODE_EXTERNAL if external_process_trigger else PROC_TRIG_MODE_INTERNAL
            ),
            start=float(start_cm1),
            stop=float(stop_cm1),
            interval=interval,
            units=UNITS_CM1,
            dwell_us=0,
            after_off_us=0,
        )

    def set_internal_trigger_params(self, *, wavenumber_cm1: float) -> dict[str, Any]:
        """Configure MIRcat internal pulse timing at the current QCL pulse parameters."""

        return self.set_wavelength_trigger_params(
            pulse_mode=PULSE_MODE_INTERNAL,
            process_trigger_mode=PROC_TRIG_MODE_INTERNAL,
            start=float(wavenumber_cm1),
            stop=float(wavenumber_cm1),
            interval=0.0,
            units=UNITS_CM1,
            dwell_us=0,
            after_off_us=0,
        )

    def get_actual_wavelength(self) -> dict[str, Any]:
        """Return actual wavelength/wavenumber and light-valid readback."""

        value = c_float()
        units = c_uint8()
        light_valid = c_bool(False)
        self._check(
            self._call("MIRcatSDK_GetActualWW", byref(value), byref(units), byref(light_valid)),
            "MIRcatSDK_GetActualWW",
        )
        return {
            "value": float(value.value),
            "units": units_name(int(units.value)),
            "light_valid": bool(light_valid.value),
        }

    def cancel_manual_tune(self) -> int:
        """Cancel single-tune/manual-tune mode, allowing a no-scan return as already clear."""

        status = self._call("MIRcatSDK_CancelManualTuneMode")
        if status not in {RET_SUCCESS, RET_NO_SCAN_INPROGRESS}:
            self._raise(status, "MIRcatSDK_CancelManualTuneMode")
        return status

    def turn_emission_on(self, *, approved_laser_safety_condition: bool) -> None:
        """Open the emission gate only when an explicit safety approval flag is true."""

        if not approved_laser_safety_condition:
            raise MircatSafetyError(
                "MIRcat emission-on requires approved_laser_safety_condition=True"
            )
        status = self._call("MIRcatSDK_TurnEmissionOn")
        if status not in {RET_SUCCESS, RET_EMISSION_ALREADY_ON}:
            self._raise(status, "MIRcatSDK_TurnEmissionOn")

    def turn_emission_off(self) -> None:
        """Close the emission gate, accepting the already-off return code."""

        status = self._call("MIRcatSDK_TurnEmissionOff")
        if status not in {RET_SUCCESS, RET_EMISSION_ALREADY_OFF}:
            self._raise(status, "MIRcatSDK_TurnEmissionOff")

    def stop_scan_if_needed(self) -> int:
        """Stop any scan in progress, allowing already-safe SDK states."""

        status = self._call("MIRcatSDK_StopScanInProgress")
        if status not in {RET_SUCCESS, RET_NO_SCAN_INPROGRESS, RET_NOT_INITIALIZED}:
            self._raise(status, "MIRcatSDK_StopScanInProgress")
        return status

    def read_state(self) -> MircatState:
        """Read the status fields required by the Day 5 MIRcat widget."""

        errors: list[str] = []
        connected = self._safe_value(self.is_connected, errors)
        api_version = self._safe_value(self.get_api_version, errors)
        num_qcls = self._safe_value(self.get_num_installed_qcls, errors)
        interlock = self._safe_value(self.is_interlock_set, errors)
        key_switch = self._safe_value(self.is_key_switch_set, errors)
        armed = self._safe_value(self.is_laser_armed, errors)
        tec_ready = self._safe_value(self.are_tecs_ready, errors)
        tuned = self._safe_value(self.is_tuned, errors)
        setpoint = self._safe_value(self.get_set_wavelength, errors)
        actual = self._safe_value(self.get_actual_wavelength, errors)
        emission = self._safe_value(self.is_emission_on, errors)
        scan_status = self._safe_value(self.get_scan_status, errors)
        scan_waiting = self._safe_value(self.get_scan_waiting_process_trigger, errors)
        status_mask = self._safe_value(self.get_status_mask, errors)
        active_qcl = self._safe_value(self.get_active_qcl, errors)
        pulse_qcl = _first_positive_int(active_qcl, _dict_value(setpoint, "preferred_qcl"), 1)
        pulse_rate = self._safe_value(lambda: self.get_qcl_pulse_rate(pulse_qcl), errors)
        pulse_width = self._safe_value(lambda: self.get_qcl_pulse_width(pulse_qcl), errors)
        error_word = self._safe_value(self.get_system_error_word, errors)

        return MircatState(
            timestamp_utc=datetime.now(UTC).isoformat(timespec="seconds"),
            connected=connected,
            api_version=api_version,
            num_qcls=num_qcls,
            interlock_set=interlock,
            key_switch_set=key_switch,
            armed=armed,
            tec_ready=tec_ready,
            tuned=tuned,
            set_wavelength=_dict_value(setpoint, "value"),
            set_wavelength_units=_dict_value(setpoint, "units"),
            preferred_qcl=_dict_value(setpoint, "preferred_qcl"),
            actual_wavelength=_dict_value(actual, "value"),
            actual_wavelength_units=_dict_value(actual, "units"),
            light_valid=_dict_value(actual, "light_valid"),
            emission_on=emission,
            scan_in_progress=_dict_value(scan_status, "scan_in_progress"),
            scan_active=_dict_value(scan_status, "scan_active"),
            scan_paused=_dict_value(scan_status, "scan_paused"),
            current_scan_number=_dict_value(scan_status, "current_scan_number"),
            scan_percent=_dict_value(scan_status, "scan_percent"),
            scan_current_wavelength=_dict_value(scan_status, "scan_current_wavelength"),
            scan_current_wavelength_units=_dict_value(
                scan_status, "scan_current_wavelength_units"
            ),
            scan_waiting_process_trigger=scan_waiting,
            scan_tec_in_progress=_dict_value(scan_status, "scan_tec_in_progress"),
            scan_motion_in_progress=_dict_value(scan_status, "scan_motion_in_progress"),
            status_mask=status_mask,
            status_mask_scanning=_status_mask_set(status_mask, STATUS_MASK_SCANNING),
            manual_tuning=_status_mask_set(status_mask, STATUS_MASK_MANUAL_TUNING),
            active_qcl=active_qcl,
            qcl_pulse_rate_hz=pulse_rate,
            qcl_pulse_width_ns=pulse_width,
            system_error_word=error_word,
            last_return_code=self.last_return_code,
            last_return_code_name=return_code_name(self.last_return_code),
            last_error="; ".join(errors) if errors else None,
        )

    def _load_sdk(self):
        candidates = [str(path) for path in self._sdk_candidates()]
        errors: list[str] = []
        for candidate in candidates:
            try:
                candidate_path = Path(candidate)
                if sys.platform.startswith("win") and candidate_path.parent.exists():
                    os.add_dll_directory(str(candidate_path.parent))
                sdk = cdll.LoadLibrary(str(candidate_path))
                self._log(f"loaded MIRcat SDK {candidate_path}")
                return sdk
            except OSError as exc:
                errors.append(f"{candidate}: {exc}")
        raise MircatConfigurationError(
            "MIRcat SDK DLL not available: "
            + "; ".join(errors)
            + ". If the manufacturer UI is open, close it before connecting."
        )

    def _sdk_candidates(self) -> list[Path]:
        configured = self.sdk_path or self.device_config.get("sdk_path")
        candidates: list[Path] = []
        if configured:
            candidates.append(self._resolve_path(configured))
        search_paths = self.device_config.get("sdk_search_paths") or []
        if isinstance(search_paths, list):
            for directory in search_paths:
                candidates.append(self._resolve_path(directory) / "MIRcatSDK.dll")
        candidates.extend(
            [
                REPO_ROOT / "docs" / "MIRcat" / "SDK" / "bin" / "MIRcatSDK.dll",
                Path(
                    r"C:\Program Files\National Instruments\LabVIEW 2025\user.lib"
                    r"\MIRcatSDKx64-1\MIRcatSDK.dll"
                ),
                Path("MIRcatSDK.dll"),
            ]
        )
        unique: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate)
            if key not in seen:
                unique.append(candidate)
                seen.add(key)
        return unique

    def _resolve_path(self, value: Any) -> Path:
        candidate = Path(str(value))
        if candidate.is_absolute():
            return candidate
        return REPO_ROOT / candidate

    def _bind_functions(self) -> None:
        assert self._sdk is not None
        sdk = self._sdk
        sdk.MIRcatSDK_Initialize.restype = c_uint32
        sdk.MIRcatSDK_DeInitialize.restype = c_uint32
        sdk.MIRcatSDK_GetAPIVersion.argtypes = [
            POINTER(c_uint16),
            POINTER(c_uint16),
            POINTER(c_uint16),
        ]
        sdk.MIRcatSDK_GetAPIVersion.restype = c_uint32
        sdk.MIRcatSDK_GetNumInstalledQcls.argtypes = [POINTER(c_uint8)]
        sdk.MIRcatSDK_GetNumInstalledQcls.restype = c_uint32
        for name in [
            "MIRcatSDK_IsConnectedToLaser",
            "MIRcatSDK_IsInterlockedStatusSet",
            "MIRcatSDK_IsKeySwitchStatusSet",
            "MIRcatSDK_IsEmissionOn",
            "MIRcatSDK_IsLaserArmed",
            "MIRcatSDK_AreTECsAtSetTemperature",
            "MIRcatSDK_IsTuned",
        ]:
            function = getattr(sdk, name)
            function.argtypes = [POINTER(c_bool)]
            function.restype = c_uint32
        sdk.MIRcatSDK_ClearSystemError.argtypes = [POINTER(c_bool)]
        sdk.MIRcatSDK_ClearSystemError.restype = c_uint32
        sdk.MIRcatSDK_GetSystemErrorWord.argtypes = [POINTER(c_uint16)]
        sdk.MIRcatSDK_GetSystemErrorWord.restype = c_uint32
        sdk.MIRcatSDK_GetStatusMask.argtypes = [POINTER(c_uint32)]
        sdk.MIRcatSDK_GetStatusMask.restype = c_uint32
        sdk.MIRcatSDK_ArmLaser.restype = c_uint32
        sdk.MIRcatSDK_DisarmLaser.restype = c_uint32
        sdk.MIRcatSDK_GetScanStatus.argtypes = [
            POINTER(c_bool),
            POINTER(c_bool),
            POINTER(c_bool),
            POINTER(c_uint16),
            POINTER(c_uint16),
            POINTER(c_float),
            POINTER(c_uint8),
            POINTER(c_bool),
            POINTER(c_bool),
        ]
        sdk.MIRcatSDK_GetScanStatus.restype = c_uint32
        sdk.MIRcatSDK_GetScanWaitingProcessTrigger.argtypes = [POINTER(c_bool)]
        sdk.MIRcatSDK_GetScanWaitingProcessTrigger.restype = c_uint32
        sdk.MIRcatSDK_GetActiveQcl.argtypes = [POINTER(c_uint8)]
        sdk.MIRcatSDK_GetActiveQcl.restype = c_uint32
        sdk.MIRcatSDK_StopScanInProgress.restype = c_uint32
        sdk.MIRcatSDK_StartSweepScan.argtypes = [
            c_float,
            c_float,
            c_float,
            c_uint8,
            c_uint16,
            c_bool,
            c_uint8,
        ]
        sdk.MIRcatSDK_StartSweepScan.restype = c_uint32
        sdk.MIRcatSDK_TuneToWW.argtypes = [c_float, c_uint8, c_uint8]
        sdk.MIRcatSDK_TuneToWW.restype = c_uint32
        sdk.MIRcatSDK_GetTuneWW.argtypes = [POINTER(c_float), POINTER(c_uint8), POINTER(c_uint8)]
        sdk.MIRcatSDK_GetTuneWW.restype = c_uint32
        sdk.MIRcatSDK_GetActualWW.argtypes = [
            POINTER(c_float),
            POINTER(c_uint8),
            POINTER(c_bool),
        ]
        sdk.MIRcatSDK_GetActualWW.restype = c_uint32
        sdk.MIRcatSDK_CancelManualTuneMode.restype = c_uint32
        sdk.MIRcatSDK_TurnEmissionOn.restype = c_uint32
        sdk.MIRcatSDK_TurnEmissionOff.restype = c_uint32
        sdk.MIRcatSDK_GetQCLPulseRate.argtypes = [c_uint8, POINTER(c_float)]
        sdk.MIRcatSDK_GetQCLPulseRate.restype = c_uint32
        sdk.MIRcatSDK_GetQCLPulseWidth.argtypes = [c_uint8, POINTER(c_float)]
        sdk.MIRcatSDK_GetQCLPulseWidth.restype = c_uint32
        sdk.MIRcatSDK_GetQCLCurrent.argtypes = [c_uint8, POINTER(c_float)]
        sdk.MIRcatSDK_GetQCLCurrent.restype = c_uint32
        sdk.MIRcatSDK_SetQCLParams.argtypes = [c_uint8, c_float, c_float, c_float]
        sdk.MIRcatSDK_SetQCLParams.restype = c_uint32
        sdk.MIRcatSDK_GetQCLPulseLimits.argtypes = [
            c_uint8,
            POINTER(c_float),
            POINTER(c_float),
            POINTER(c_float),
        ]
        sdk.MIRcatSDK_GetQCLPulseLimits.restype = c_uint32
        sdk.MIRcatSDK_GetWlTrigParams.argtypes = [
            POINTER(c_uint8),
            POINTER(c_uint8),
            POINTER(c_float),
            POINTER(c_float),
            POINTER(c_float),
            POINTER(c_uint8),
            POINTER(c_uint32),
            POINTER(c_uint32),
        ]
        sdk.MIRcatSDK_GetWlTrigParams.restype = c_uint32
        sdk.MIRcatSDK_SetWlTrigParams.argtypes = [
            c_uint8,
            c_uint8,
            c_float,
            c_float,
            c_float,
            c_uint8,
            c_uint32,
            c_uint32,
        ]
        sdk.MIRcatSDK_SetWlTrigParams.restype = c_uint32
        sdk.MIRcatSDK_GetWlTrigPulseWidth.argtypes = [POINTER(c_uint16)]
        sdk.MIRcatSDK_GetWlTrigPulseWidth.restype = c_uint32
        sdk.MIRcatSDK_SetWlTrigPulseWidth.argtypes = [c_uint16]
        sdk.MIRcatSDK_SetWlTrigPulseWidth.restype = c_uint32

    def _bool_call(self, name: str) -> bool:
        value = c_bool(False)
        self._check(self._call(name, byref(value)), name)
        return bool(value.value)

    def _safe_value(self, callback, errors: list[str]) -> Any:
        try:
            return callback()
        except MircatError as exc:
            errors.append(str(exc))
            return None

    def _call(self, name: str, *args) -> int:
        if self._sdk is None:
            raise MircatCommandError("MIRcat SDK is not loaded")
        status = int(getattr(self._sdk, name)(*args))
        self.last_return_code = status
        self._log(f"{name} -> {status} ({return_code_name(status)})")
        return status

    def _check(self, status: int, label: str) -> None:
        if status != RET_SUCCESS:
            self._raise(status, label)

    def _raise(self, status: int, label: str) -> None:
        name = return_code_name(status)
        hint = ""
        if status in {RET_NO_SYSTEM_FOUND, RET_INITIALIZATION_FAILURE, RET_COMM_ERROR}:
            hint = "; close the manufacturer MIRcat UI and verify no other process owns the controller"
        raise MircatCommandError(f"{label} returned {status} ({name}){hint}")

    def _log(self, message: str) -> None:
        if self.command_log is None:
            return
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        try:
            self.command_log.write(f"{timestamp} mircat {message}\n")
            self.command_log.flush()
        except ValueError:
            self.command_log = None


def units_name(value: int) -> str:
    """Return a stable unit label from the SDK unit code."""

    if value == UNITS_MICRONS:
        return "microns"
    if value == UNITS_CM1:
        return "cm^-1"
    return f"unknown:{value}"


def pulse_mode_name(value: int) -> str:
    """Return a readable MIRcat pulse-trigger mode label."""

    if value == PULSE_MODE_INTERNAL:
        return "internal"
    if value == PULSE_MODE_EXTERNAL_TRIGGER:
        return "external_trigger"
    if value == PULSE_MODE_EXTERNAL_PASSTHRU:
        return "external_passthru"
    return f"unknown:{value}"


def process_trigger_mode_name(value: int) -> str:
    """Return a readable MIRcat process-trigger mode label."""

    if value == PROC_TRIG_MODE_INTERNAL:
        return "internal"
    if value == PROC_TRIG_MODE_EXTERNAL:
        return "external"
    if value == PROC_TRIG_MODE_MANUAL:
        return "manual"
    return f"unknown:{value}"


def return_code_name(value: int | None) -> str | None:
    """Return a readable return-code name."""

    if value is None:
        return None
    return RETURN_CODE_NAMES.get(int(value), "UNKNOWN")


def _dict_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return None


def _first_positive_int(*values: Any) -> int:
    for value in values:
        try:
            candidate = int(value)
        except (TypeError, ValueError):
            continue
        if candidate > 0:
            return candidate
    return 1


def _status_mask_set(status_mask: int | None, flag: int) -> bool | None:
    if status_mask is None:
        return None
    return bool(int(status_mask) & flag)
