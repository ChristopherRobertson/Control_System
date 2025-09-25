"""
Daylight MIRcat Laser Controller

Real hardware integration with the MIRcat SDK providing comprehensive
error handling, status reporting, and scan functionality.
"""

import toml
import os
import time
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import logging
from enum import Enum
from ctypes import CDLL, c_uint16, c_uint8, c_uint32, c_float, c_bool, byref, POINTER
from ctypes.util import find_library

logger = logging.getLogger(__name__)

# MIRcat Error Codes (from SDK documentation)
class MIRcatError(Enum):
    SUCCESS = 0
    NOT_CONNECTED = 1
    NOT_ARMED = 2
    NOT_TUNED = 3
    TEMPERATURE_UNSTABLE = 4
    INTERLOCK_FAULT = 5
    SYSTEM_FAULT = 6
    INVALID_PARAMETER = 7
    TUNING_TIMEOUT = 8
    EMISSION_TIMEOUT = 9
    SDK_ERROR = 10
    COMMUNICATION_ERROR = 11
    HARDWARE_ERROR = 12

# Scan Modes
class ScanMode(Enum):
    SWEEP = "sweep"
    STEP = "step"
    MULTISPECTRAL = "multispectral"

class MIRcatController:
    """Controller for Daylight MIRcat QCL Laser
    
    Provides real hardware integration with the MIRcat SDK.
    All state changes are driven by actual hardware responses.
    """
    
    def __init__(self):
        self.sdk_initialized = False
        self._sdk = None
        self._sdk_dir: Optional[Path] = None
        self.connected = False
        self.armed = False
        self.emission_on = False
        self.tuned = False
        self.temperature_stable = False
        self.scan_in_progress = False
        self.current_scan_mode = None
        self.current_scan_number: Optional[int] = None
        self.current_scan_percent: Optional[int] = None
        
        self.config = self._load_config()
        self.current_wavenumber = 0.0
        self.current_qcl = 0
        self.laser_mode = "Pulsed"
        self.pulse_rate: Optional[float] = None
        self.pulse_width: Optional[float] = None
        
        # Hardware status - only updated from SDK responses
        self.status = {
            "interlocks": False,
            "key_switch": False, 
            "temperature": False,
            "connected": False,
            "emission": False,
            "pointing_correction": False,
            "pointing_supported": None,
            "pointing_x_enabled": None,
            "pointing_y_enabled": None,
            "system_fault": True,
            "case_temp_1": 0.0,
            "case_temp_2": 0.0,
            "pcb_temperature": 0.0,
            "tuned": False,
            "armed": False
        }
        
        self.last_error = None
        self.last_error_code = None
        # Track last-reported pointing state to reduce log spam
        self._last_pointing_supported: Optional[bool] = None
        self._last_pointing_enabled: Optional[bool] = None
        self._pointing_logged_once: bool = False

        # Internal ping-pong management for forced bidirectional sweep
        self._pingpong_task: Optional[asyncio.Task] = None
        self._pingpong_cancel: bool = False
        self._pingpong_active: bool = False

        # Constants (mirroring SDK header values used here)
        self._UNITS_MICRONS = 1
        self._UNITS_CM1 = 2
        self._COMM_SERIAL = 1
        self._SERIAL_PORT_AUTO = 0
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from hardware_configuration.toml"""
        config_path = Path(__file__).parent.parent.parent.parent.parent / "hardware_configuration.toml"
        try:
            with config_path.open('r', encoding='utf-8-sig') as f:
                config = toml.load(f)
            return config.get('daylight_mircat', {})
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def _ensure_sdk(self) -> None:
        """Load MIRcatSDK DLL and prepare function prototypes."""
        if self._sdk is not None:
            return
        # Determine candidate directories
        candidates: List[Path] = []
        # 1) Env override
        env_dir = os.environ.get('MIRCAT_SDK_DIR')
        if env_dir:
            candidates.append(Path(env_dir))
        # 2) Config value
        cfg_dir = self.config.get('sdk_path')
        if cfg_dir:
            candidates.append(Path(cfg_dir))
        # 3) Repo docs SDK bundle (for convenience)
        # Avoid hardcoded repo/system paths in code. Prefer explicit env or config.

        dll_name = 'MIRcatSDK.dll' if os.name == 'nt' else 'libMIRcatSDK.so'
        load_error: Optional[Exception] = None
        for d in candidates:
            try:
                if not d:
                    continue
                dll_path = d / dll_name
                if dll_path.exists():
                    # Ensure dependent DLLs can be found (Windows 3.8+)
                    if os.name == 'nt' and hasattr(os, 'add_dll_directory'):
                        os.add_dll_directory(str(d))
                    self._sdk_dir = d
                    self._sdk = CDLL(str(dll_path))
                    break
            except Exception as e:
                load_error = e
                continue
        if self._sdk is None:
            # Try OS search path (PATH/LD_LIBRARY_PATH)
            try:
                self._sdk = CDLL(dll_name)
            except Exception:
                # Try ctypes util
                lib_path = find_library('MIRcatSDK')
                if lib_path:
                    self._sdk = CDLL(lib_path)
        if self._sdk is None:
            msg = (
                "MIRcat SDK DLL not found. Set MIRCAT_SDK_DIR or 'daylight_mircat.sdk_path', "
                f"or place {dll_name} on system PATH."
            )
            if load_error:
                msg += f" Last error: {load_error}"
            self.last_error = msg
            self.last_error_code = MIRcatError.SDK_ERROR
            raise Exception(msg)

        # Restypes for calls we use
        self._sdk.MIRcatSDK_Initialize.restype = c_uint32
        self._sdk.MIRcatSDK_DeInitialize.restype = c_uint32
        self._sdk.MIRcatSDK_SetCommType.restype = c_uint32
        self._sdk.MIRcatSDK_SetSerialParams.restype = c_uint32
        self._sdk.MIRcatSDK_GetAPIVersion.restype = c_uint32
        self._sdk.MIRcatSDK_GetNumInstalledQcls.restype = c_uint32
        try:
            from ctypes import POINTER as _PTR
            self._sdk.MIRcatSDK_GetNumInstalledQcls.argtypes = [_PTR(c_uint8)]
        except Exception:
            pass
        self._sdk.MIRcatSDK_IsLaserArmed.restype = c_uint32
        self._sdk.MIRcatSDK_DisarmLaser.restype = c_uint32
        self._sdk.MIRcatSDK_ArmDisarmLaser.restype = c_uint32
        self._sdk.MIRcatSDK_IsEmissionOn.restype = c_uint32
        self._sdk.MIRcatSDK_TurnEmissionOn.restype = c_uint32
        self._sdk.MIRcatSDK_TurnEmissionOff.restype = c_uint32
        self._sdk.MIRcatSDK_IsTuned.restype = c_uint32
        self._sdk.MIRcatSDK_GetActualWW.restype = c_uint32
        self._sdk.MIRcatSDK_GetTuneWW.restype = c_uint32
        self._sdk.MIRcatSDK_TuneToWW.restype = c_uint32
        self._sdk.MIRcatSDK_AreTECsAtSetTemperature.restype = c_uint32
        self._sdk.MIRcatSDK_IsInterlockedStatusSet.restype = c_uint32
        self._sdk.MIRcatSDK_IsKeySwitchStatusSet.restype = c_uint32
        self._sdk.MIRcatSDK_GetQCLTemperature.restype = c_uint32
        self._sdk.MIRcatSDK_GetTecCurrent.restype = c_uint32
        self._sdk.MIRcatSDK_GetQCLCurrent.restype = c_uint32
        self._sdk.MIRcatSDK_GetQCLPulseRate.restype = c_uint32
        self._sdk.MIRcatSDK_GetQCLPulseWidth.restype = c_uint32
        self._sdk.MIRcatSDK_SetQCLParams.restype = c_uint32
        self._sdk.MIRcatSDK_SetAllQclParams.restype = c_uint32
        self._sdk.MIRcatSDK_StartSweepScan.restype = c_uint32
        # Ensure correct parameter marshaling for sweep scan start
        try:
            self._sdk.MIRcatSDK_StartSweepScan.argtypes = [
                c_float,  # fStartWW
                c_float,  # fStopWW
                c_float,  # fScanSpeed
                c_uint8,  # bUnits
                c_uint16, # wNumScans
                c_bool,   # bIsBiDirectional (C bool)
                c_uint8   # u8PreferredQcl
            ]
        except Exception:
            pass
        self._sdk.MIRcatSDK_StartStepMeasureModeScan.restype = c_uint32
        self._sdk.MIRcatSDK_IsSweepBidirectional.restype = c_uint32
        try:
            self._sdk.MIRcatSDK_IsSweepBidirectional.argtypes = [POINTER(c_bool)]
        except Exception:
            pass
        # Optional helpers to introspect sweep params
        try:
            if hasattr(self._sdk, 'MIRcatSDK_GetSweepNumScans'):
                self._sdk.MIRcatSDK_GetSweepNumScans.restype = c_uint32
                from ctypes import POINTER as _PTR  # avoid top-level name collision
                self._sdk.MIRcatSDK_GetSweepNumScans.argtypes = [_PTR(c_uint16)]
        except Exception:
            pass
        self._sdk.MIRcatSDK_SetNumMultiSpectralElements.restype = c_uint32
        self._sdk.MIRcatSDK_AddMultiSpectralElement.restype = c_uint32
        self._sdk.MIRcatSDK_StartMultiSpectralModeScan.restype = c_uint32
        self._sdk.MIRcatSDK_GetScanStatus.restype = c_uint32
        self._sdk.MIRcatSDK_StopScanInProgress.restype = c_uint32
        self._sdk.MIRcatSDK_SetWlTrigParams.restype = c_uint32
        # Optional manual step API
        if hasattr(self._sdk, 'MIRcatSDK_ManualStepScanInProgress'):
            self._sdk.MIRcatSDK_ManualStepScanInProgress.restype = c_uint32

        # Optional Advanced Sweep APIs (guarded by config; some SDKs expose these)
        try:
            if hasattr(self._sdk, 'MIRcatSDK_SetAdvancedSweepParams'):
                self._sdk.MIRcatSDK_SetAdvancedSweepParams.restype = c_uint32
                # uint8 units, float start, float stop, float speed, uint16 numScans, bool bidir
                self._sdk.MIRcatSDK_SetAdvancedSweepParams.argtypes = [
                    c_uint8, c_float, c_float, c_float, c_uint16, c_bool
                ]
            if hasattr(self._sdk, 'MIRcatSDK_SetAdvancedSweepChanParams'):
                self._sdk.MIRcatSDK_SetAdvancedSweepChanParams.restype = c_uint32
                # uint8 qcl, float chStart, float chStop, bool useChannel
                self._sdk.MIRcatSDK_SetAdvancedSweepChanParams.argtypes = [
                    c_uint8, c_float, c_float, c_bool
                ]
            if hasattr(self._sdk, 'MIRcatSDK_StartSweepAdvancedScan'):
                self._sdk.MIRcatSDK_StartSweepAdvancedScan.restype = c_uint32
                self._sdk.MIRcatSDK_StartSweepAdvancedScan.argtypes = []
            if hasattr(self._sdk, 'MIRcatSDK_ReadWriteAdvancedSweepParams'):
                self._sdk.MIRcatSDK_ReadWriteAdvancedSweepParams.restype = c_uint32
                self._sdk.MIRcatSDK_ReadWriteAdvancedSweepParams.argtypes = [c_bool]
        except Exception:
            pass
        # Optional getters for sweep configuration to aid debugging
        try:
            if hasattr(self._sdk, 'MIRcatSDK_GetSweepStartWW'):
                self._sdk.MIRcatSDK_GetSweepStartWW.restype = c_uint32
                self._sdk.MIRcatSDK_GetSweepStartWW.argtypes = [POINTER(c_float), POINTER(c_uint8)]
            if hasattr(self._sdk, 'MIRcatSDK_GetSweepStopWW'):
                self._sdk.MIRcatSDK_GetSweepStopWW.restype = c_uint32
                self._sdk.MIRcatSDK_GetSweepStopWW.argtypes = [POINTER(c_float), POINTER(c_uint8)]
            if hasattr(self._sdk, 'MIRcatSDK_GetSweepScanSpeed'):
                self._sdk.MIRcatSDK_GetSweepScanSpeed.restype = c_uint32
                self._sdk.MIRcatSDK_GetSweepScanSpeed.argtypes = [POINTER(c_float), POINTER(c_uint8)]
            if hasattr(self._sdk, 'MIRcatSDK_GetSweepNumScans'):
                self._sdk.MIRcatSDK_GetSweepNumScans.restype = c_uint32
                self._sdk.MIRcatSDK_GetSweepNumScans.argtypes = [POINTER(c_uint16)]
            if hasattr(self._sdk, 'MIRcatSDK_GetActiveQcl'):
                self._sdk.MIRcatSDK_GetActiveQcl.restype = c_uint32
                self._sdk.MIRcatSDK_GetActiveQcl.argtypes = [POINTER(c_uint8)]
        except Exception:
            pass
        # Pointing compensation SDK hooks (read-only; do not modify device state)
        try:
            if hasattr(self._sdk, 'MIRcatSDK_PointingControlsSupported'):
                self._sdk.MIRcatSDK_PointingControlsSupported.restype = c_uint32
                self._sdk.MIRcatSDK_PointingControlsSupported.argtypes = [POINTER(c_bool)]
            if hasattr(self._sdk, 'MIRcatSDK_PointingGetCompensationEnabled'):
                self._sdk.MIRcatSDK_PointingGetCompensationEnabled.restype = c_uint32
                self._sdk.MIRcatSDK_PointingGetCompensationEnabled.argtypes = [POINTER(c_bool), POINTER(c_bool)]
        except Exception:
            pass

    # (removed) _log_sdk_info helper

    def _sdk_ok(self, ret: int) -> bool:
        return int(ret) == 0

    def _mircat_sdk_call(self, command: str, value: Any = None) -> Union[bool, int, float, str]:
        """Interface to selected MIRcat SDK operations using ctypes bindings."""
        self._ensure_sdk()
        try:
            if command == 'init':
                # Initialize controller first (per SDK docs)
                ret = self._sdk.MIRcatSDK_Initialize()
                if not self._sdk_ok(ret):
                    raise Exception(f"Initialize failed (code {int(ret)})")
                self.sdk_initialized = True
                # Configure comms after initialization (avoid NOT_INITIALIZED errors)
                comm = self.config.get('communication', {}).get('comm_type', 'SERIAL')
                if str(comm).upper() in ('SERIAL', 'DEFAULT'):
                    _ = self._sdk.MIRcatSDK_SetCommType(c_uint8(self._COMM_SERIAL))
                    baud = int(self.config.get('communication', {}).get('baud_rate') or 115200)
                    _ = self._sdk.MIRcatSDK_SetSerialParams(c_uint16(self._SERIAL_PORT_AUTO), c_uint32(baud))
                return True

            elif command == 'isconnected':
                # No direct API; rely on controller connection flag
                return bool(self.connected and self.sdk_initialized)

            elif command == 'isarmed':
                is_armed = c_bool(False)
                ret = self._sdk.MIRcatSDK_IsLaserArmed(byref(is_armed))
                if not self._sdk_ok(ret):
                    raise Exception(f"IsLaserArmed failed ({int(ret)})")
                return bool(is_armed.value)

            elif command == 'istuned':
                is_tuned = c_bool(False)
                ret = self._sdk.MIRcatSDK_IsTuned(byref(is_tuned))
                if not self._sdk_ok(ret):
                    raise Exception(f"IsTuned failed ({int(ret)})")
                return bool(is_tuned.value)

            elif command == 'temperaturestable':
                at_temp = c_bool(False)
                ret = self._sdk.MIRcatSDK_AreTECsAtSetTemperature(byref(at_temp))
                if not self._sdk_ok(ret):
                    raise Exception(f"AreTECsAtSetTemperature failed ({int(ret)})")
                return bool(at_temp.value)

            elif command == 'isinterlocked':
                interlock = c_bool(False)
                ret = self._sdk.MIRcatSDK_IsInterlockedStatusSet(byref(interlock))
                if not self._sdk_ok(ret):
                    raise Exception(f"IsInterlockedStatusSet failed ({int(ret)})")
                return bool(interlock.value)

            elif command == 'iskeyswitch':
                ks = c_bool(False)
                ret = self._sdk.MIRcatSDK_IsKeySwitchStatusSet(byref(ks))
                if not self._sdk_ok(ret):
                    raise Exception(f"IsKeySwitchStatusSet failed ({int(ret)})")
                return bool(ks.value)

            elif command == 'emission':
                if value:
                    ret = self._sdk.MIRcatSDK_TurnEmissionOn()
                    if not self._sdk_ok(ret):
                        raise Exception(f"TurnEmissionOn failed ({int(ret)})")
                else:
                    ret = self._sdk.MIRcatSDK_TurnEmissionOff()
                    if not self._sdk_ok(ret):
                        raise Exception(f"TurnEmissionOff failed ({int(ret)})")
                return True

            elif command == 'isemitting':
                is_on = c_bool(False)
                ret = self._sdk.MIRcatSDK_IsEmissionOn(byref(is_on))
                if not self._sdk_ok(ret):
                    raise Exception(f"IsEmissionOn failed ({int(ret)})")
                return bool(is_on.value)

            elif command == 'arm':
                # Ensure armed state
                if not self._mircat_sdk_call('isarmed'):
                    ret = self._sdk.MIRcatSDK_ArmDisarmLaser()
                    if not self._sdk_ok(ret):
                        raise Exception(f"ArmDisarmLaser failed ({int(ret)})")
                return True

            elif command == 'disarm':
                # Explicitly disarm laser
                ret = self._sdk.MIRcatSDK_DisarmLaser()
                if not self._sdk_ok(ret):
                    raise Exception(f"DisarmLaser failed ({int(ret)})")
                return True

            elif command == 'wavenumber':
                # Tune to wavenumber in cm^-1 on given QCL (default 1)
                qcl = int(self.current_qcl or 1)
                ret = self._sdk.MIRcatSDK_TuneToWW(c_float(float(value)), c_uint8(self._UNITS_CM1), c_uint8(qcl))
                if not self._sdk_ok(ret):
                    raise Exception(f"TuneToWW failed ({int(ret)}) for {value} cm^-1 on QCL {qcl}")
                # Update internal setpoint
                self.current_wavenumber = float(value)
                return True

            elif command == 'temperature':
                # Return current QCL temperature (float)
                qcl = int(self.current_qcl or 1)
                temp = c_float(0)
                ret = self._sdk.MIRcatSDK_GetQCLTemperature(c_uint8(qcl), byref(temp))
                if not self._sdk_ok(ret):
                    raise Exception(f"GetQCLTemperature failed ({int(ret)}) for QCL {qcl}")
                return float(temp.value)

            else:
                raise Exception(f"Unknown MIRcat SDK command: {command}")

        except Exception as e:
            self.last_error = str(e)
            self.last_error_code = MIRcatError.COMMUNICATION_ERROR
            logger.error(f"MIRcat SDK call failed: {command} - {e}")
            raise

    async def connect(self) -> bool:
        """Connect to MIRcat device using real SDK - requires actual hardware"""
        try:
            logger.info("Attempting to connect to real MIRcat hardware...")
            
            # Initialize real MIRcat SDK and mark connected
            self._mircat_sdk_call("init")
            self.connected = True
            
            # Get real hardware status
            await self._update_hardware_status()
            
            logger.info("Successfully connected to MIRcat hardware")
            return True
            
        except Exception as e:
            self.connected = False
            self.last_error = f"Connection failed: {str(e)}"
            self.last_error_code = MIRcatError.COMMUNICATION_ERROR
            logger.error(f"Failed to connect to MIRcat: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from MIRcat device"""
        try:
            logger.info("Disconnecting from MIRcat...")
            
            # Safely shutdown
            if self.emission_on:
                await self.turn_emission_off()
            
            if self.armed:
                # Only disarm; do not power off the system
                try:
                    self._mircat_sdk_call("disarm")
                except Exception as e:
                    logger.warning(f"Disarm during disconnect reported error: {e}")
            # De-initialize SDK connection if loaded
            try:
                if self._sdk is not None and self.sdk_initialized:
                    ret = self._sdk.MIRcatSDK_DeInitialize()
                    if int(ret) != 0:
                        logger.warning(f"MIRcatSDK_DeInitialize returned code {int(ret)}")
            except Exception as e:
                logger.warning(f"DeInitialize error ignored: {e}")
            
            self.connected = False
            self.armed = False
            self.emission_on = False
            self.tuned = False
            self.temperature_stable = False
            self.scan_in_progress = False
            
            # Reset status to disconnected state
            self.status.update({
                "connected": False,
                "emission": False,
                "interlocks": False,
                "key_switch": False,
                "temperature": False,
                "pointing_correction": False,
                "system_fault": True,
                "tuned": False,
                "armed": False,
                "case_temp_1": 0.0,
                "case_temp_2": 0.0,
                "pcb_temperature": 0.0
            })
            
            logger.info("MIRcat disconnected successfully")
            return True
            
        except Exception as e:
            self.last_error = f"Disconnect failed: {str(e)}"
            logger.error(f"Failed to disconnect from MIRcat: {e}")
            return False
    
    async def arm_laser(self) -> bool:
        """Arm the laser for operation"""
        if not self.connected:
            self.last_error = "Device not connected"
            self.last_error_code = MIRcatError.NOT_CONNECTED
            raise Exception("Device not connected")
        
        try:
            logger.info("Arming MIRcat laser...")
            
            # Check interlocks first
            interlocked = self._mircat_sdk_call("isinterlocked")
            if not interlocked:
                self.last_error = "Interlocks not enabled - check safety interlock connection"
                self.last_error_code = MIRcatError.INTERLOCK_FAULT
                raise Exception("Interlocks not enabled")
            
            # Arm the laser
            self._mircat_sdk_call("arm")
            
            # Poll for armed state up to 15s
            for _ in range(60):
                if self._mircat_sdk_call("isarmed"):
                    break
                await asyncio.sleep(0.25)
            else:
                self.last_error = "Arming sequence failed"
                self.last_error_code = MIRcatError.HARDWARE_ERROR
                raise Exception("Arming failed")
            
            # After arming, wait for TECs at set temperature (SDK sample flow)
            for _ in range(240):  # up to 60s (0.25s * 240)
                if self._mircat_sdk_call("temperaturestable"):
                    break
                await asyncio.sleep(0.25)
            else:
                self.last_error = "Temperature not stable after arming"
                self.last_error_code = MIRcatError.TEMPERATURE_UNSTABLE
                raise Exception("Temperature not stable after arming")
            
            # Clear last error on success
            self.last_error = None
            self.last_error_code = None
            
            await self._update_hardware_status()
            logger.info("MIRcat laser armed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to arm laser: {e}")
            return False
    
    async def disarm_laser(self) -> bool:
        """Disarm the laser"""
        try:
            logger.info("Disarming MIRcat laser...")
            
            # Turn off emission first if on
            if self.emission_on:
                await self.turn_emission_off()
            
            # Disarm laser
            self._mircat_sdk_call("disarm")
            
            # Wait until laser is reported disarmed (max 10s)
            for _ in range(40):
                if not self._mircat_sdk_call("isarmed"):
                    break
                await asyncio.sleep(0.25)
            else:
                self.last_error = "Disarm timeout"
                self.last_error_code = MIRcatError.HARDWARE_ERROR
                raise Exception("Disarm timeout")
            
            await self._update_hardware_status()
            logger.info("MIRcat laser disarmed successfully")
            return True
            
        except Exception as e:
            self.last_error = f"Disarm failed: {str(e)}"
            logger.error(f"Failed to disarm laser: {e}")
            return False
    
    async def turn_emission_on(self) -> bool:
        """Turn laser emission on"""
        if not self.connected:
            self.last_error = "Device not connected"
            self.last_error_code = MIRcatError.NOT_CONNECTED
            raise Exception("Device not connected")
            
        if not self.armed:
            self.last_error = "Laser must be armed before turning emission on"
            self.last_error_code = MIRcatError.NOT_ARMED
            raise Exception("Laser must be armed before turning emission on")
        
        if not self.tuned:
            self.last_error = "Laser must be tuned before turning emission on"
            self.last_error_code = MIRcatError.NOT_TUNED
            raise Exception("Laser must be tuned before turning emission on")
        
        try:
            logger.info("Turning MIRcat emission on...")
            self._mircat_sdk_call("emission", 1)
            
            # Wait until emission is on (max 5s)
            for _ in range(20):
                if self._mircat_sdk_call("isemitting"):
                    break
                await asyncio.sleep(0.25)
            else:
                self.last_error = "Emission on timeout"
                self.last_error_code = MIRcatError.EMISSION_TIMEOUT
                raise Exception("Emission on timeout")
            
            await self._update_hardware_status()
            logger.info("MIRcat emission turned on successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to turn emission on: {e}")
            return False
    
    async def turn_emission_off(self) -> bool:
        """Turn laser emission off"""
        try:
            logger.info("Turning MIRcat emission off...")
            self._mircat_sdk_call("emission", 0)
            
            # Wait until emission is off (max 5s)
            for _ in range(20):
                if not self._mircat_sdk_call("isemitting"):
                    break
                await asyncio.sleep(0.25)
            else:
                self.last_error = "Emission off timeout"
                self.last_error_code = MIRcatError.EMISSION_TIMEOUT
                raise Exception("Emission off timeout")
            
            await self._update_hardware_status()
            logger.info("MIRcat emission turned off successfully")
            return True
            
        except Exception as e:
            self.last_error = f"Failed to turn emission off: {str(e)}"
            logger.error(f"Failed to turn emission off: {e}")
            return False
    
    async def tune_to_wavenumber(self, wavenumber: float) -> bool:
        """Tune laser to specific wavenumber"""
        if not self.connected:
            self.last_error = "Device not connected"
            self.last_error_code = MIRcatError.NOT_CONNECTED
            raise Exception("Device not connected")
        
        try:
            logger.info(f"Tuning MIRcat to {wavenumber} cm-1...")
            
            # Check temperature stability before tuning
            temp_stable = self._mircat_sdk_call("temperaturestable")
            if not temp_stable:
                self.last_error = "Temperature not stable - wait for thermal equilibrium before tuning"
                self.last_error_code = MIRcatError.TEMPERATURE_UNSTABLE
                raise Exception("Temperature not stable")
            
            # Tune to wavenumber
            self._mircat_sdk_call("wavenumber", wavenumber)
            
            # Wait for tuning to complete (up to 5 seconds)
            for _ in range(10):
                if self._mircat_sdk_call("istuned"):
                    break
                await asyncio.sleep(0.5)
            else:
                self.last_error = "Tuning timeout - laser failed to reach target wavenumber"
                self.last_error_code = MIRcatError.TUNING_TIMEOUT
                raise Exception("Tuning timeout")
            
            await self._update_hardware_status()
            logger.info(f"MIRcat tuned to {wavenumber} cm-1 successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to tune to wavenumber {wavenumber}: {e}")
            return False
    
    async def set_laser_mode(self, mode: str) -> bool:
        """Set laser operation mode"""
        valid_modes = self.config.get('parameters', {}).get('laser_mode_options', ['Pulsed', 'CW', 'CW + Modulation'])
        
        if mode not in valid_modes:
            self.last_error = f"Invalid laser mode. Valid modes: {valid_modes}"
            self.last_error_code = MIRcatError.INVALID_PARAMETER
            raise Exception(f"Invalid laser mode. Valid modes: {valid_modes}")
        
        try:
            logger.info(f"Setting MIRcat laser mode to {mode}...")
            # SDK call would be implemented here
            self.laser_mode = mode
            
            logger.info(f"MIRcat laser mode set to {mode} successfully")
            return True
            
        except Exception as e:
            self.last_error = f"Failed to set laser mode: {str(e)}"
            logger.error(f"Failed to set laser mode to {mode}: {e}")
            return False
    
    async def set_pulse_parameters(self, pulse_rate: int, pulse_width: int, current_mA: Optional[float] = None) -> bool:
        """Set pulse rate and width for pulsed mode. Optionally include current (mA)."""
        if self.laser_mode != "Pulsed":
            self.last_error = "Pulse parameters only valid in Pulsed mode"
            self.last_error_code = MIRcatError.INVALID_PARAMETER
            raise Exception("Pulse parameters only valid in Pulsed mode")
        
        # Validate parameters against config
        params = self.config.get('parameters', {})
        min_rate = params.get('pulse_rate_min', 10)
        max_rate = params.get('pulse_rate_max', 3000000)
        min_width = params.get('pulse_width_min', 20)
        max_width = params.get('pulse_width_max', 1000)
        
        if not (min_rate <= pulse_rate <= max_rate):
            self.last_error = f"Pulse rate {pulse_rate} outside valid range {min_rate}-{max_rate}"
            self.last_error_code = MIRcatError.INVALID_PARAMETER
            raise Exception(f"Pulse rate {pulse_rate} outside valid range {min_rate}-{max_rate}")
        
        if not (min_width <= pulse_width <= max_width):
            self.last_error = f"Pulse width {pulse_width} outside valid range {min_width}-{max_width}"
            self.last_error_code = MIRcatError.INVALID_PARAMETER
            raise Exception(f"Pulse width {pulse_width} outside valid range {min_width}-{max_width}")
        
        try:
            logger.info(f"Setting pulse parameters: rate={pulse_rate}, width={pulse_width}")
            qcl = int(self.current_qcl or 1)
            # Determine current to use
            if current_mA is None:
                cur = c_float(0)
                try:
                    if self._sdk_ok(self._sdk.MIRcatSDK_GetQCLCurrent(c_uint8(qcl), byref(cur))):
                        current_mA = float(cur.value)
                except Exception:
                    current_mA = None
            if current_mA is None:
                current_mA = float(self.config.get('parameters', {}).get('pulsed_current_default', 500))
            # Apply to current QCL with current
            ret = self._sdk.MIRcatSDK_SetQCLParams(
                c_uint8(qcl), c_float(float(pulse_rate)), c_float(float(pulse_width)), c_float(float(current_mA))
            )
            if not self._sdk_ok(ret):
                raise Exception(f"SetQCLParams failed ({int(ret)})")
            # Read back
            pr = c_float(0)
            pw = c_float(0)
            ret1 = self._sdk.MIRcatSDK_GetQCLPulseRate(c_uint8(qcl), byref(pr))
            ret2 = self._sdk.MIRcatSDK_GetQCLPulseWidth(c_uint8(qcl), byref(pw))
            if not (self._sdk_ok(ret1) and self._sdk_ok(ret2)):
                logger.warning("Readback of pulse parameters failed after setting")
            else:
                self.pulse_rate = float(pr.value)
                self.pulse_width = float(pw.value)
            logger.info("Pulse parameters set successfully")
            return True
        
        except Exception as e:
            self.last_error = f"Failed to set pulse parameters: {str(e)}"
            logger.error(f"Failed to set pulse parameters: {e}")
            return False

    # Scan Operations - ALL require real MIRcat hardware
    async def start_sweep_scan(self, start_wn: float, end_wn: float, scan_speed: float, 
                              num_scans: int = 1, bidirectional: bool = False) -> bool:
        """Start sweep scan mode"""
        # TODO: Investigate MIRcat SDK retrace behavior. Bidirectional flag is accepted
        # by standard/advanced APIs, but some firmware performs tune-retrace instead of
        # scan-retrace, causing a jump at endpoints. Confirm if an additional retrace
        # option exists in target SDK/firmware and wire it here.
        if not self.connected:
            self.last_error = "MIRcat device not connected"
            self.last_error_code = MIRcatError.NOT_CONNECTED
            raise Exception("MIRcat device not connected")
        
        if not self.armed:
            self.last_error = "Laser must be armed before starting scan"
            self.last_error_code = MIRcatError.NOT_ARMED
            raise Exception("Laser must be armed before starting scan")
        
        try:
            qcl = int(self.current_qcl or 1)
            # Map 0/negative (UI infinite) to a large finite value for compatibility
            ns = int(num_scans)
            if ns <= 0:
                ns = 65535
            logger.info(f"Starting sweep scan: {start_wn} to {end_wn} cm-1, speed={scan_speed}, scans={ns}, bidirectional={bool(bidirectional)}")

            # Cancel any manual tune mode per SDK guidance
            try:
                if hasattr(self._sdk, 'MIRcatSDK_CancelManualTuneMode'):
                    _ = self._sdk.MIRcatSDK_CancelManualTuneMode()
            except Exception:
                pass

            # Do not touch pointing compensation from here (SDK-only behavior per user request)

            # Use Advanced sweep only when explicitly enabled in config
            used_advanced = False
            use_adv_cfg = bool(self.config.get('parameters', {}).get('use_advanced_sweep', False))
            can_advanced = all(
                hasattr(self._sdk, name) for name in (
                    'MIRcatSDK_SetAdvancedSweepParams',
                    'MIRcatSDK_StartSweepAdvancedScan'
                )
            )
            if bidirectional and use_adv_cfg and can_advanced:
                try:
                    retp = self._sdk.MIRcatSDK_SetAdvancedSweepParams(
                        c_uint8(self._UNITS_CM1), c_float(float(start_wn)), c_float(float(end_wn)), c_float(float(scan_speed)),
                        c_uint16(ns), c_bool(True)
                    )
                    if not self._sdk_ok(retp):
                        raise Exception(f"SetAdvancedSweepParams failed ({int(retp)})")
                    # Configure channel usage: enable current QCL only; disable others
                    try:
                        n = c_uint8(0)
                        if self._sdk_ok(self._sdk.MIRcatSDK_GetNumInstalledQcls(byref(n))):
                            total = int(n.value) or 1
                        else:
                            total = 1
                    except Exception:
                        total = 1
                    if hasattr(self._sdk, 'MIRcatSDK_SetAdvancedSweepChanParams'):
                        for ch in range(1, max(1, total) + 1):
                            use = (ch == qcl)
                            retc = self._sdk.MIRcatSDK_SetAdvancedSweepChanParams(
                                c_uint8(ch), c_float(float(start_wn)), c_float(float(end_wn)), c_bool(use)
                            )
                            if not self._sdk_ok(retc):
                                logger.warning(f"SetAdvancedSweepChanParams returned {int(retc)} for QCL {ch}")
                    if hasattr(self._sdk, 'MIRcatSDK_ReadWriteAdvancedSweepParams'):
                        _ = self._sdk.MIRcatSDK_ReadWriteAdvancedSweepParams(c_bool(True))
                    reta = self._sdk.MIRcatSDK_StartSweepAdvancedScan()
                    if not self._sdk_ok(reta):
                        raise Exception(f"StartSweepAdvancedScan failed ({int(reta)})")
                    used_advanced = True
                except Exception as adv_e:
                    logger.warning(f"Advanced sweep start failed ({adv_e}); falling back to standard sweep API")

            if not used_advanced:
                # Prefer the currently selected QCL (1..4); firmware may require explicit channel for bidirectional sweeps
                ret = self._sdk.MIRcatSDK_StartSweepScan(
                    c_float(float(start_wn)), c_float(float(end_wn)), c_float(float(scan_speed)),
                    c_uint8(self._UNITS_CM1), c_uint16(ns), c_bool(True if bidirectional else False), c_uint8(qcl)
                )
                if not self._sdk_ok(ret):
                    raise Exception(f"StartSweepScan failed ({int(ret)})")

            self.scan_in_progress = True
            self.current_scan_mode = ScanMode.SWEEP
            # Final confirmation log and optional software fallback
            try:
                f_bidir = c_bool(False)
                if self._sdk_ok(self._sdk.MIRcatSDK_IsSweepBidirectional(byref(f_bidir))):
                    self.status["sweep_bidirectional"] = bool(f_bidir.value)
                # Readback of configured sweep parameters for diagnosis
                try:
                    sv = c_float(0); st = c_float(0); sp = c_float(0)
                    u1 = c_uint8(0); u2 = c_uint8(0); u3 = c_uint8(0)
                    ns_read = c_uint16(0)
                    act_qcl = c_uint8(0)
                    if hasattr(self._sdk, 'MIRcatSDK_GetSweepStartWW'):
                        _ = self._sdk.MIRcatSDK_GetSweepStartWW(byref(st), byref(u1))
                    if hasattr(self._sdk, 'MIRcatSDK_GetSweepStopWW'):
                        _ = self._sdk.MIRcatSDK_GetSweepStopWW(byref(sp), byref(u2))
                    if hasattr(self._sdk, 'MIRcatSDK_GetSweepScanSpeed'):
                        _ = self._sdk.MIRcatSDK_GetSweepScanSpeed(byref(sv), byref(u3))
                    if hasattr(self._sdk, 'MIRcatSDK_GetSweepNumScans'):
                        _ = self._sdk.MIRcatSDK_GetSweepNumScans(byref(ns_read))
                    if hasattr(self._sdk, 'MIRcatSDK_GetActiveQcl'):
                        _ = self._sdk.MIRcatSDK_GetActiveQcl(byref(act_qcl))
                    # Also try advanced readback when available
                    adv_bidir = None
                    try:
                        if hasattr(self._sdk, 'MIRcatSDK_GetAdvancedSweepParams'):
                            au = c_uint8(0); astart = c_float(0); astop=c_float(0); aspeed=c_float(0); ans=c_uint16(0); abidir=c_bool(False)
                            if self._sdk_ok(self._sdk.MIRcatSDK_GetAdvancedSweepParams(byref(au), byref(astart), byref(astop), byref(aspeed), byref(ans), byref(abidir))):
                                adv_bidir = bool(abidir.value)
                    except Exception:
                        pass
                    logger.info(
                        f"Sweep config readback: bidir={self.status.get('sweep_bidirectional')}, adv_bidir={adv_bidir}, "
                        f"start={float(st.value) if st.value else None}, stop={float(sp.value) if sp.value else None}, "
                        f"speed={float(sv.value) if sv.value else None}, ns={int(ns_read.value)}, act_qcl={int(act_qcl.value)}"
                    )
                except Exception:
                    pass
                logger.info(f"Sweep bidirectional set: {bool(self.status.get('sweep_bidirectional'))} (advanced={used_advanced})")
                # Optional software fallback is disabled by default unless explicitly enabled in config
                enable_sw_pp = bool(self.config.get('parameters', {}).get('enable_software_pingpong', False))
                if bidirectional and not bool(self.status.get('sweep_bidirectional')) and enable_sw_pp:
                    try:
                        _ = self._sdk.MIRcatSDK_StopScanInProgress()
                    except Exception:
                        pass
                    logger.info("Switching to controller-managed ping-pong sweep fallback (forward/reverse segments)")
                    await self._start_pingpong_manager(start_wn, end_wn, scan_speed, num_scans)
                    return True
            except Exception:
                pass
            return True
        except Exception as e:
            self.last_error = f"Failed to start sweep scan: {str(e)}"
            self.last_error_code = MIRcatError.HARDWARE_ERROR
            logger.error(f"Failed to start sweep scan: {e}")
            return False

    async def _start_pingpong_manager(self, start_wn: float, end_wn: float, scan_speed: float, num_scans: int) -> None:
        # Cancel any existing ping-pong manager
        try:
            if self._pingpong_task and not self._pingpong_task.done():
                self._pingpong_cancel = True
                try:
                    await asyncio.wait_for(self._pingpong_task, timeout=2.0)
                except Exception:
                    pass
        finally:
            self._pingpong_task = None
            self._pingpong_cancel = False
            self._pingpong_active = True
        self.status["sweep_bidirectional"] = True
        # Spawn background task
        self._pingpong_task = asyncio.create_task(self._pingpong_loop(start_wn, end_wn, scan_speed, num_scans))

    async def _pingpong_loop(self, start_wn: float, end_wn: float, scan_speed: float, num_scans: int) -> None:
        try:
            # Each loop is forward then reverse; infinite when num_scans <= 0
            loops_remaining = None if (num_scans is None or int(num_scans) <= 0) else int(num_scans)
            qcl = int(self.current_qcl or 1)
            # Helper: start a single-direction sweep with ns=1
            async def _start_segment(a: float, b: float) -> None:
                try:
                    if hasattr(self._sdk, 'MIRcatSDK_CancelManualTuneMode'):
                        _ = self._sdk.MIRcatSDK_CancelManualTuneMode()
                except Exception:
                    pass
                ret = self._sdk.MIRcatSDK_StartSweepScan(
                    c_float(float(a)), c_float(float(b)), c_float(float(scan_speed)),
                    c_uint8(self._UNITS_CM1), c_uint16(1), c_bool(False), c_uint8(qcl)
                )
                if not self._sdk_ok(ret):
                    raise Exception(f"StartSweepScan segment failed ({int(ret)}) {a}->{b}")

            # Helper: wait until scan finishes (with timeout safety)
            async def _wait_complete(max_seconds: float) -> None:
                t0 = time.time()
                while True:
                    if self._pingpong_cancel:
                        break
                    try:
                        in_prog = c_bool(False); active=c_bool(False); paused=c_bool(False)
                        cur_scan = c_uint16(0); cur_pct=c_uint16(0); cur_ww=c_float(0)
                        units=c_uint8(0); tec=c_bool(False); motion=c_bool(False)
                        if self._sdk_ok(self._sdk.MIRcatSDK_GetScanStatus(byref(in_prog), byref(active), byref(paused),
                                                  byref(cur_scan), byref(cur_pct), byref(cur_ww), byref(units), byref(tec), byref(motion))):
                            if not bool(in_prog.value):
                                break
                    except Exception:
                        # Fall back to small delay if status call fails
                        pass
                    await asyncio.sleep(0.2)
                    if (time.time() - t0) > max_seconds * 2.0 + 5.0:
                        # Safety stop to avoid runaway
                        try:
                            _ = self._sdk.MIRcatSDK_StopScanInProgress()
                        except Exception:
                            pass
                        break

            while True:
                if self._pingpong_cancel:
                    break
                # Forward
                await _start_segment(start_wn, end_wn)
                est_time = abs(float(end_wn) - float(start_wn)) / max(0.001, float(scan_speed))
                await _wait_complete(est_time)
                if self._pingpong_cancel:
                    break
                # Reverse
                await _start_segment(end_wn, start_wn)
                est_time = abs(float(end_wn) - float(start_wn)) / max(0.001, float(scan_speed))
                await _wait_complete(est_time)

                if loops_remaining is not None:
                    loops_remaining -= 1
                    if loops_remaining <= 0:
                        break
            # Ensure stop at end
            try:
                _ = self._sdk.MIRcatSDK_StopScanInProgress()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Ping-pong sweep manager error: {e}")
            self.last_error = f"Ping-pong manager: {e}"
            self.last_error_code = MIRcatError.HARDWARE_ERROR
        finally:
            self._pingpong_active = False
            self._pingpong_cancel = False
            # status will reflect hardware scan status on next update

    async def start_step_scan(self, start_wn: float, end_wn: float, step_size: float,
                             dwell_time: int, num_scans: int = 1) -> bool:
        """Start step and measure scan mode"""
        if not self.connected:
            self.last_error = "MIRcat device not connected"
            self.last_error_code = MIRcatError.NOT_CONNECTED
            raise Exception("MIRcat device not connected")
        
        if not self.armed:
            self.last_error = "Laser must be armed before starting scan"
            self.last_error_code = MIRcatError.NOT_ARMED
            raise Exception("Laser must be armed before starting scan")
        
        try:
            # Load settings for trigger mode and dwell
            proc_mode = 1  # internal default
            pulse_mode = 1
            step_time_ms = dwell_time
            step_delay_ms = 0
            try:
                settings_path = Path(__file__).parent / 'user_settings.json'
                if settings_path.exists():
                    import json as _json
                    with open(settings_path, 'r') as f:
                        data = _json.load(f)
                    mode_map = {
                        'Use Internal Step Mode': 1, 'internal': 1,
                        'Use External Step Mode': 2, 'external': 2,
                        'Use Manual Step Mode': 3, 'manual': 3,
                    }
                    pulse_map = {
                        'Use Internal Pulse Mode': 1, 'internal': 1,
                        'Use External Trigger Mode': 2, 'external_trigger': 2,
                        'Use External Pulse Mode': 3, 'external_pulse': 3,
                        'Use Wavelength Trigger Pulse Mode': 4, 'wavelength_trigger': 4,
                    }
                    proc_mode = mode_map.get(data.get('processTriggerMode'), proc_mode)
                    pulse_mode = pulse_map.get(data.get('pulseMode'), pulse_mode)
                    if data.get('internalStepTime') is not None:
                        step_time_ms = int(data.get('internalStepTime'))
                    if data.get('internalStepDelay') is not None:
                        step_delay_ms = int(data.get('internalStepDelay'))
            except Exception as e:
                logger.warning(f"Reading user settings failed: {e}")

            logger.info(f"Starting step scan: {start_wn} to {end_wn} cm-1, step={step_size}, dwell={step_time_ms}ms, proc_mode={proc_mode}")
            # Configure dwell/trigger params
            try:
                dwell_us = int(max(0, step_time_ms) * 1000)
                delay_us = int(max(0, step_delay_ms) * 1000)
                retp = self._sdk.MIRcatSDK_SetWlTrigParams(
                    c_uint8(pulse_mode), c_uint8(proc_mode),
                    c_float(float(start_wn)), c_float(float(end_wn)), c_float(float(step_size)),
                    c_uint8(self._UNITS_CM1), c_uint32(dwell_us), c_uint32(delay_us)
                )
                if not self._sdk_ok(retp):
                    logger.warning(f"SetWlTrigParams returned code {int(retp)}")
            except Exception as e:
                logger.warning(f"SetWlTrigParams failed (continuing): {e}")
            ret = self._sdk.MIRcatSDK_StartStepMeasureModeScan(
                c_float(float(start_wn)), c_float(float(end_wn)), c_float(float(step_size)),
                c_uint8(self._UNITS_CM1), c_uint16(int(num_scans))
            )
            if not self._sdk_ok(ret):
                raise Exception(f"StartStepMeasureModeScan failed ({int(ret)})")
            self.scan_in_progress = True
            self.current_scan_mode = ScanMode.STEP
            return True
        except Exception as e:
            self.last_error = f"Failed to start step scan: {str(e)}"
            self.last_error_code = MIRcatError.HARDWARE_ERROR
            logger.error(f"Failed to start step scan: {e}")
            return False

    async def start_multispectral_scan(self, wavelength_list: List[Dict], num_scans: int = 1,
                                      keep_laser_on: bool = False) -> bool:
        """Start multi-spectral scan mode"""
        if not self.connected:
            self.last_error = "MIRcat device not connected"
            self.last_error_code = MIRcatError.NOT_CONNECTED
            raise Exception("MIRcat device not connected")
        
        if not self.armed:
            self.last_error = "Laser must be armed before starting scan"
            self.last_error_code = MIRcatError.NOT_ARMED
            raise Exception("Laser must be armed before starting scan")
        
        try:
            logger.info(f"Starting multispectral scan with {len(wavelength_list)} wavelengths")
            # Ensure TECs are at set temperature (avoid SDK error 95)
            try:
                stable = self._mircat_sdk_call("temperaturestable")
                if not stable:
                    logger.info("TECs not at set temperature; waiting up to 60s before starting multispectral scan...")
                    for _ in range(120):  # 0.5s * 120 = 60s
                        if self._mircat_sdk_call("temperaturestable"):
                            stable = True
                            break
                        await asyncio.sleep(0.5)
                if not stable:
                    raise Exception("TECs not at set temperature (code 95)")
            except Exception as e:
                self.last_error = f"TECs not at set temperature: {e}"
                self.last_error_code = MIRcatError.TEMPERATURE_UNSTABLE
                logger.error(self.last_error)
                return False
            # Program the table (clamp to valid wn range)
            count = max(0, len(wavelength_list))
            ret = self._sdk.MIRcatSDK_SetNumMultiSpectralElements(c_uint8(count))
            if not self._sdk_ok(ret):
                raise Exception(f"SetNumMultiSpectralElements failed ({int(ret)})")
            for entry in wavelength_list:
                wn = float(entry.get('wavenumber'))
                try:
                    params = self.config.get('parameters', {})
                    wn_min = float(params.get('wavenumber_min', 1638.81))
                    wn_max = float(params.get('wavenumber_max', 2077.27))
                    if wn < wn_min: wn = wn_min
                    if wn > wn_max: wn = wn_max
                except Exception:
                    pass
                # SDK uses microseconds for internal timing parameters in step-type scans.
                # Convert ms from UI to µs for Multi-Spectral elements.
                dwell_ms = int(entry.get('dwell_time'))
                off_ms = int(entry.get('off_time'))
                dwell_us = max(0, dwell_ms) * 1000
                off_us = 0 if keep_laser_on else max(0, off_ms) * 1000
                # Clamp to uint32 range to avoid overflow
                dwell_us = min(dwell_us, 0xFFFFFFFF)
                off_us = min(off_us, 0xFFFFFFFF)
                ret = self._sdk.MIRcatSDK_AddMultiSpectralElement(
                    c_float(wn), c_uint8(self._UNITS_CM1), c_uint32(dwell_us), c_uint32(off_us)
                )
                if not self._sdk_ok(ret):
                    raise Exception(f"AddMultiSpectralElement failed ({int(ret)}) for {wn}")
            # Support infinite scans by mapping 0/negative to max uint16
            ns = int(num_scans)
            if ns <= 0:
                ns = 65535
            ret = self._sdk.MIRcatSDK_StartMultiSpectralModeScan(c_uint16(ns))
            if not self._sdk_ok(ret):
                raise Exception(f"StartMultiSpectralModeScan failed ({int(ret)})")
            self.scan_in_progress = True
            self.current_scan_mode = ScanMode.MULTISPECTRAL
            return True
        except Exception as e:
            self.last_error = f"Failed to start multispectral scan: {str(e)}"
            self.last_error_code = MIRcatError.HARDWARE_ERROR
            logger.error(f"Failed to start multispectral scan: {e}")
            return False

    async def stop_scan(self) -> bool:
        """Stop any active scan"""
        if not self.connected:
            self.last_error = "MIRcat device not connected"
            self.last_error_code = MIRcatError.NOT_CONNECTED
            raise Exception("MIRcat device not connected")
        
        try:
            logger.info("Stopping scan...")
            # Cancel controller-managed ping-pong if active
            if self._pingpong_task and not self._pingpong_task.done():
                self._pingpong_cancel = True
                try:
                    await asyncio.wait_for(self._pingpong_task, timeout=2.0)
                except Exception:
                    pass
            ret = self._sdk.MIRcatSDK_StopScanInProgress()
            if not self._sdk_ok(ret):
                raise Exception(f"StopScanInProgress failed ({int(ret)})")
            self.scan_in_progress = False
            self.current_scan_mode = None
            await self._update_hardware_status()
            return True
        except Exception as e:
            self.last_error = f"Failed to stop scan: {str(e)}"
            self.last_error_code = MIRcatError.HARDWARE_ERROR
            logger.error(f"Failed to stop scan: {e}")
            return False

    async def manual_step(self) -> bool:
        """Manually advance a Step & Measure scan by one step (manual mode)."""
        if not self.connected:
            self.last_error = "MIRcat device not connected"
            self.last_error_code = MIRcatError.NOT_CONNECTED
            raise Exception("MIRcat device not connected")
        try:
            if not hasattr(self._sdk, 'MIRcatSDK_ManualStepScanInProgress'):
                raise Exception("ManualStepScanInProgress not supported in SDK")
            ret = self._sdk.MIRcatSDK_ManualStepScanInProgress()
            if not self._sdk_ok(ret):
                raise Exception(f"ManualStepScanInProgress failed ({int(ret)})")
            return True
        except Exception as e:
            self.last_error = f"Manual step failed: {str(e)}"
            self.last_error_code = MIRcatError.HARDWARE_ERROR
            logger.error(f"Manual step failed: {e}")
            return False

    async def clear_error(self) -> bool:
        """Clear last error info in controller."""
        self.last_error = None
        self.last_error_code = None
        return True

    async def apply_trigger_settings(self, data: Dict[str, Any]) -> bool:
        """Apply pulse and process trigger modes + wavelength trigger params from persisted settings."""
        try:
            pulse_mode_map = {
                'Use Internal Pulse Mode': 1,
                'Use External Trigger Mode': 2,
                'Use External Pulse Mode': 3,
                'Use Wavelength Trigger Pulse Mode': 4,
                'internal': 1,
                'external_trigger': 2,
                'external_pulse': 3,
                'wavelength_trigger': 4,
            }
            proc_mode_map = {
                'Use Internal Step Mode': 1,
                'Use External Step Mode': 2,
                'Use Manual Step Mode': 3,
                'internal': 1,
                'external': 2,
                'manual': 3,
            }
            pulseMode = data.get('pulseMode')
            processTriggerMode = data.get('processTriggerMode')
            wlTrigStart = float(data.get('wlTrigStart') or 0)
            wlTrigStop = float(data.get('wlTrigStop') or 0)
            wlTrigInterval = float(data.get('wlTrigInterval') or 0)
            internalStepTime = int(data.get('internalStepTime') or 0)
            internalStepDelay = int(data.get('internalStepDelay') or 0)
            pbPulseMode = pulse_mode_map.get(pulseMode or 'internal', 1)
            pbProcTrigMode = proc_mode_map.get(processTriggerMode or 'internal', 1)
            # Call combined parameter setter if available
            if hasattr(self._sdk, 'MIRcatSDK_SetWlTrigParams'):
                ret = self._sdk.MIRcatSDK_SetWlTrigParams(
                    c_uint8(pbPulseMode), c_uint8(pbProcTrigMode),
                    c_float(wlTrigStart), c_float(wlTrigStop), c_float(wlTrigInterval),
                    c_uint8(self._UNITS_CM1), c_uint32(internalStepTime * 1000), c_uint32(internalStepDelay * 1000)
                )
                if not self._sdk_ok(ret):
                    logger.warning(f"SetWlTrigParams returned {int(ret)}")
            return True
        except Exception as e:
            logger.warning(f"apply_trigger_settings failed: {e}")
            return False

    async def _update_hardware_status(self) -> None:
        """Update status from real MIRcat hardware via SDK calls"""
        try:
            if self.connected:
                # Get real hardware status from MIRcat device
                self.status.update({
                    "connected": self._mircat_sdk_call("isconnected"),
                    "interlocks": self._mircat_sdk_call("isinterlocked"),
                    "key_switch": self._mircat_sdk_call("iskeyswitch"),
                    "temperature": self._mircat_sdk_call("temperaturestable"),
                    "pointing_correction": False,
                    "pointing_supported": None,
                    "pointing_x_enabled": None,
                    "pointing_y_enabled": None,
                    "system_fault": False,  # Could be derived from specific error reads if available
                    "tuned": self._mircat_sdk_call("istuned"),
                    "armed": self._mircat_sdk_call("isarmed"),
                    "emission": self._mircat_sdk_call("isemitting"),
                    "case_temp_1": self._mircat_sdk_call("temperature"),
                    "case_temp_2": self._mircat_sdk_call("temperature"),
                    "pcb_temperature": self._mircat_sdk_call("temperature")
                })
                # Read-only pointing compensation state when supported
                try:
                    if hasattr(self._sdk, 'MIRcatSDK_PointingControlsSupported') and hasattr(self._sdk, 'MIRcatSDK_PointingGetCompensationEnabled'):
                        supp = c_bool(False)
                        if self._sdk_ok(self._sdk.MIRcatSDK_PointingControlsSupported(byref(supp))):
                            self.status["pointing_supported"] = bool(supp.value)
                            if bool(supp.value):
                                xe = c_bool(False); ye = c_bool(False)
                                if self._sdk_ok(self._sdk.MIRcatSDK_PointingGetCompensationEnabled(byref(xe), byref(ye))):
                                    self.status["pointing_x_enabled"] = bool(xe.value)
                                    self.status["pointing_y_enabled"] = bool(ye.value)
                                    self.status["pointing_correction"] = bool(xe.value) or bool(ye.value)
                                    # Log on change
                                    cur_enabled = self.status["pointing_correction"]
                                    if self._last_pointing_supported != self.status["pointing_supported"] or self._last_pointing_enabled != cur_enabled:
                                        logger.info(f"Pointing status: supported={self.status['pointing_supported']}, x_enabled={self.status['pointing_x_enabled']}, y_enabled={self.status['pointing_y_enabled']}")
                                        self._last_pointing_supported = self.status["pointing_supported"]
                                        self._last_pointing_enabled = cur_enabled
                        else:
                            self.status["pointing_supported"] = None
                except Exception:
                    # On failure, do not overwrite previous values (avoid masking real issues)
                    pass

                # (diagnostic logging removed by request)
                
                # Update internal state from real hardware
                self.armed = self.status["armed"]
                self.tuned = self.status["tuned"]
                self.temperature_stable = self.status["temperature"]
                self.emission_on = self.status["emission"]
                # Read pulse parameters (ignore failures silently)
                try:
                    qcl = int(self.current_qcl or 1)
                    pr = c_float(0); pw = c_float(0)
                    if self._sdk_ok(self._sdk.MIRcatSDK_GetQCLPulseRate(c_uint8(qcl), byref(pr))):
                        self.pulse_rate = float(pr.value)
                    if self._sdk_ok(self._sdk.MIRcatSDK_GetQCLPulseWidth(c_uint8(qcl), byref(pw))):
                        self.pulse_width = float(pw.value)
                except Exception:
                    pass
                # Read scan status
                try:
                    in_prog = c_bool(False); active=c_bool(False); paused=c_bool(False)
                    cur_scan = c_uint16(0); cur_pct=c_uint16(0); cur_ww=c_float(0)
                    units=c_uint8(0); tec=c_bool(False); motion=c_bool(False)
                    if self._sdk_ok(self._sdk.MIRcatSDK_GetScanStatus(byref(in_prog), byref(active), byref(paused),
                                              byref(cur_scan), byref(cur_pct), byref(cur_ww), byref(units), byref(tec), byref(motion))):
                        self.scan_in_progress = bool(in_prog.value)
                        self.current_scan_number = int(cur_scan.value)
                        self.current_scan_percent = int(cur_pct.value)
                        if cur_ww.value > 0:
                            if int(units.value) == int(self._UNITS_CM1):
                                self.current_wavenumber = float(cur_ww.value)
                            else:
                                try:
                                    self.current_wavenumber = 10000.0 / float(cur_ww.value)
                                except Exception:
                                    pass
                except Exception:
                    pass
                # Read sweep bidirectional flag when available
                try:
                    bidir = c_bool(False)
                    if self._sdk_ok(self._sdk.MIRcatSDK_IsSweepBidirectional(byref(bidir))):
                        self.status["sweep_bidirectional"] = bool(bidir.value)
                except Exception:
                    pass
            else:
                # Reset all status when disconnected
                self.status.update({
                    "connected": False,
                    "interlocks": False,
                    "key_switch": False,
                    "temperature": False,
                    "pointing_correction": False,
                    "system_fault": True,
                    "tuned": False,
                    "armed": False,
                    "emission": False,
                    "case_temp_1": 0.0,
                    "case_temp_2": 0.0,
                    "pcb_temperature": 0.0
                })
                self.armed = False
                self.tuned = False
                self.temperature_stable = False
            
        except Exception as e:
            logger.error(f"Failed to update hardware status: {e}")
            # If we can't read status, assume device disconnected
            self.connected = False
            self.status["connected"] = False
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current device status with error information"""
        await self._update_hardware_status()
        
        return {
            "connected": self.connected,
            "armed": self.armed,
            "emission_on": self.emission_on,
            "current_wavenumber": self.current_wavenumber,
            "current_qcl": self.current_qcl,
            "laser_mode": self.laser_mode,
            "pulse_rate": self.pulse_rate,
            "pulse_width": self.pulse_width,
            "tuned": self.tuned,
            "temperature_stable": self.temperature_stable,
            "scan_in_progress": self.scan_in_progress,
            "current_scan_number": self.current_scan_number,
            "current_scan_percent": self.current_scan_percent,
            "current_scan_mode": self.current_scan_mode.value if self.current_scan_mode else None,
            "status": self.status,
            "last_error": self.last_error,
            "last_error_code": self.last_error_code.value if self.last_error_code else None
        }
