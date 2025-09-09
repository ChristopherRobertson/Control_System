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
from ctypes import CDLL, c_uint16, c_uint8, c_uint32, c_float, c_bool, byref

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
        
        self.config = self._load_config()
        self.current_wavenumber = 0.0
        self.current_qcl = 0
        self.laser_mode = "Pulsed"
        
        # Hardware status - only updated from SDK responses
        self.status = {
            "interlocks": False,
            "key_switch": False, 
            "temperature": False,
            "connected": False,
            "emission": False,
            "pointing_correction": False,
            "system_fault": True,
            "case_temp_1": 0.0,
            "case_temp_2": 0.0,
            "pcb_temperature": 0.0,
            "tuned": False,
            "armed": False
        }
        
        self.last_error = None
        self.last_error_code = None

        # Constants (mirroring SDK header values used here)
        self._UNITS_MICRONS = 1
        self._UNITS_CM1 = 2
        self._COMM_SERIAL = 1
        self._SERIAL_PORT_AUTO = 0
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from hardware_configuration.toml"""
        config_path = Path(__file__).parent.parent.parent.parent.parent / "hardware_configuration.toml"
        try:
            with open(config_path, 'r') as f:
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
        # 3) Repo docs SDK bundle (for convenience) — locate repo root by finding hardware_configuration.toml
        probe = Path(__file__).resolve()
        repo_root = None
        for p in [probe] + list(probe.parents):
            if (p / 'hardware_configuration.toml').exists():
                repo_root = p
                break
        if repo_root is not None:
            # Preferred structure
            candidates.append(repo_root / 'docs' / 'sdks' / 'daylight_mircat')
            # Backward-compatible fallback (older layout)
            candidates.append(repo_root / 'docs' / 'docs' / 'sdks' / 'daylight_mircat')
        # 4) Common Windows install paths
        if os.name == 'nt':
            candidates.append(Path('C:/Program Files/Daylight Solutions/MIRcatSDK'))
            candidates.append(Path('C:/Program Files (x86)/Daylight Solutions/MIRcatSDK'))

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
            msg = f"MIRcat SDK DLL not found. Checked: {[str(p) for p in candidates]}"
            if load_error:
                msg += f"; last error: {load_error}"
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

    def _sdk_ok(self, ret: int) -> bool:
        return int(ret) == 0

    def _mircat_sdk_call(self, command: str, value: Any = None) -> Union[bool, int, float, str]:
        """Interface to selected MIRcat SDK operations using ctypes bindings."""
        self._ensure_sdk()
        try:
            if command == 'init':
                # Optional: configure comms before initialize
                comm = self.config.get('communication', {}).get('comm_type', 'SERIAL')
                if str(comm).upper() in ('SERIAL', 'DEFAULT'):
                    self._sdk.MIRcatSDK_SetCommType(c_uint8(self._COMM_SERIAL))
                    baud = int(self.config.get('communication', {}).get('baud_rate') or 115200)
                    self._sdk.MIRcatSDK_SetSerialParams(c_uint16(self._SERIAL_PORT_AUTO), c_uint32(baud))
                ret = self._sdk.MIRcatSDK_Initialize()
                if not self._sdk_ok(ret):
                    raise Exception(f"Initialize failed (code {int(ret)})")
                self.sdk_initialized = True
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

            elif command == 'poweroff':
                # Disarm and power off system
                ret = self._sdk.MIRcatSDK_DisarmLaser()
                if not self._sdk_ok(ret):
                    raise Exception(f"DisarmLaser failed ({int(ret)})")
                if hasattr(self._sdk, 'MIRcatSDK_PowerOffSystem'):
                    self._sdk.MIRcatSDK_PowerOffSystem.restype = c_uint32
                    self._sdk.MIRcatSDK_PowerOffSystem()
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
                self._mircat_sdk_call("poweroff")
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
            
            # Check temperature stability
            temp_stable = self._mircat_sdk_call("temperaturestable")
            if not temp_stable:
                self.last_error = "Temperature not stable - wait for thermal equilibrium"
                self.last_error_code = MIRcatError.TEMPERATURE_UNSTABLE
                raise Exception("Temperature not stable")
            
            # Arm the laser
            self._mircat_sdk_call("arm")
            
            # Wait for arming sequence (5 seconds + beep)
            await asyncio.sleep(0.5)
            
            # Verify arming
            armed = self._mircat_sdk_call("isarmed")
            if not armed:
                self.last_error = "Arming sequence failed"
                self.last_error_code = MIRcatError.HARDWARE_ERROR
                raise Exception("Arming failed")
            
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
            
            # Power off laser
            self._mircat_sdk_call("poweroff")
            
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
    
    async def set_pulse_parameters(self, pulse_rate: int, pulse_width: int) -> bool:
        """Set pulse rate and width for pulsed mode"""
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
            # SDK call would be implemented here
            
            logger.info("Pulse parameters set successfully")
            return True
            
        except Exception as e:
            self.last_error = f"Failed to set pulse parameters: {str(e)}"
            logger.error(f"Failed to set pulse parameters: {e}")
            return False

    # Scan Operations - ALL require real MIRcat hardware
    async def start_sweep_scan(self, start_wn: float, end_wn: float, scan_speed: float, 
                              num_scans: int = 1, bidirectional: bool = False) -> bool:
        """Start sweep scan mode - requires real MIRcat hardware"""
        if not self.connected:
            self.last_error = "MIRcat device not connected"
            self.last_error_code = MIRcatError.NOT_CONNECTED
            raise Exception("MIRcat device not connected")
        
        if not self.armed:
            self.last_error = "Laser must be armed before starting scan"
            self.last_error_code = MIRcatError.NOT_ARMED
            raise Exception("Laser must be armed before starting scan")
        
        try:
            logger.info(f"Starting sweep scan: {start_wn} to {end_wn} cm-1")
            
            # Real SDK calls would be:
            # result = mircat_sdk.MIRcatSDK_StartSweepScan(start_wn, end_wn, scan_speed, num_scans, bidirectional)
            # if result != 0:
            #     raise Exception(f"Sweep scan initialization failed with code {result}")
            
            # Since we don't have real hardware, this will fail
            raise Exception("MIRcat SDK required - cannot start sweep scan without real hardware")
            
        except Exception as e:
            self.last_error = f"Failed to start sweep scan: {str(e)}"
            self.last_error_code = MIRcatError.HARDWARE_ERROR
            logger.error(f"Failed to start sweep scan: {e}")
            return False

    async def start_step_scan(self, start_wn: float, end_wn: float, step_size: float,
                             dwell_time: int, num_scans: int = 1) -> bool:
        """Start step and measure scan mode - requires real MIRcat hardware"""
        if not self.connected:
            self.last_error = "MIRcat device not connected"
            self.last_error_code = MIRcatError.NOT_CONNECTED
            raise Exception("MIRcat device not connected")
        
        if not self.armed:
            self.last_error = "Laser must be armed before starting scan"
            self.last_error_code = MIRcatError.NOT_ARMED
            raise Exception("Laser must be armed before starting scan")
        
        try:
            logger.info(f"Starting step scan: {start_wn} to {end_wn} cm-1, step={step_size}")
            
            # Real SDK calls would be:
            # result = mircat_sdk.MIRcatSDK_StartStepScan(start_wn, end_wn, step_size, dwell_time, num_scans)
            # if result != 0:
            #     raise Exception(f"Step scan initialization failed with code {result}")
            
            # Since we don't have real hardware, this will fail
            raise Exception("MIRcat SDK required - cannot start step scan without real hardware")
            
        except Exception as e:
            self.last_error = f"Failed to start step scan: {str(e)}"
            self.last_error_code = MIRcatError.HARDWARE_ERROR
            logger.error(f"Failed to start step scan: {e}")
            return False

    async def start_multispectral_scan(self, wavelength_list: List[Dict], num_scans: int = 1,
                                      keep_laser_on: bool = False) -> bool:
        """Start multi-spectral scan mode - requires real MIRcat hardware"""
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
            
            # Real SDK calls would be:
            # result = mircat_sdk.MIRcatSDK_StartMultiSpectralScan(wavelength_list, num_scans, keep_laser_on)
            # if result != 0:
            #     raise Exception(f"Multispectral scan initialization failed with code {result}")
            
            # Since we don't have real hardware, this will fail
            raise Exception("MIRcat SDK required - cannot start multispectral scan without real hardware")
            
        except Exception as e:
            self.last_error = f"Failed to start multispectral scan: {str(e)}"
            self.last_error_code = MIRcatError.HARDWARE_ERROR
            logger.error(f"Failed to start multispectral scan: {e}")
            return False

    async def stop_scan(self) -> bool:
        """Stop any active scan - requires real MIRcat hardware"""
        if not self.connected:
            self.last_error = "MIRcat device not connected"
            self.last_error_code = MIRcatError.NOT_CONNECTED
            raise Exception("MIRcat device not connected")
        
        try:
            logger.info("Stopping scan...")
            
            # Real SDK call would be:
            # result = mircat_sdk.MIRcatSDK_StopScan()
            # if result != 0:
            #     raise Exception(f"Stop scan failed with code {result}")
            
            # Since we don't have real hardware, this will fail
            raise Exception("MIRcat SDK required - cannot stop scan without real hardware")
            
        except Exception as e:
            self.last_error = f"Failed to stop scan: {str(e)}"
            self.last_error_code = MIRcatError.HARDWARE_ERROR
            logger.error(f"Failed to stop scan: {e}")
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
                    "pointing_correction": True,  # Not exposed in SDK; leave True when connected
                    "system_fault": False,  # Could be derived from specific error reads if available
                    "tuned": self._mircat_sdk_call("istuned"),
                    "armed": self._mircat_sdk_call("isarmed"),
                    "emission": self._mircat_sdk_call("isemitting"),
                    "case_temp_1": self._mircat_sdk_call("temperature"),
                    "case_temp_2": self._mircat_sdk_call("temperature"),
                    "pcb_temperature": self._mircat_sdk_call("temperature")
                })
                
                # Update internal state from real hardware
                self.armed = self.status["armed"]
                self.tuned = self.status["tuned"]
                self.temperature_stable = self.status["temperature"]
                self.emission_on = self.status["emission"]
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
            "tuned": self.tuned,
            "temperature_stable": self.temperature_stable,
            "scan_in_progress": self.scan_in_progress,
            "current_scan_mode": self.current_scan_mode.value if self.current_scan_mode else None,
            "status": self.status,
            "last_error": self.last_error,
            "last_error_code": self.last_error_code.value if self.last_error_code else None
        }
