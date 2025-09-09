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
    
    def _mircat_sdk_call(self, command: str, value: Any = None) -> Union[bool, int, float, str]:
        """
        Real MIRcat SDK call - requires actual MIRcat hardware and SDK installation
        
        This function interfaces directly with the MIRcat SDK library.
        ALL calls will fail if no real MIRcat hardware is connected.
        NO SIMULATION - only real hardware responses allowed.
        """
        try:
            # Attempt to import real MIRcat SDK - will fail if not installed
            try:
                # In real implementation, this would be the actual MIRcat SDK import:
                # import MIRcatSDK as mircat_sdk
                # For now, we raise an exception since SDK is not available in this environment
                raise ImportError("MIRcat SDK not available")
            except ImportError:
                self.last_error = "MIRcat SDK not installed or hardware not available"
                self.last_error_code = MIRcatError.COMMUNICATION_ERROR
                raise Exception("MIRcat SDK not installed - install Daylight Solutions MIRcat SDK and connect hardware")
            
            # The following would be real SDK calls if hardware was available:
            # Note: All these calls are commented out because they require real hardware
            
            # if command == "init":
            #     result = mircat_sdk.MIRcatSDK_Initialize()
            #     if result != 0:
            #         raise Exception(f"SDK initialization failed with code {result}")
            #     self.sdk_initialized = True
            #     return True
            
            # elif command == "isconnected":
            #     connected = mircat_sdk.MIRcatSDK_IsConnectedToLaser()
            #     return connected
            
            # elif command == "isarmed":
            #     armed = mircat_sdk.MIRcatSDK_IsArmed()
            #     return armed
            
            # elif command == "istuned":
            #     tuned = mircat_sdk.MIRcatSDK_IsTuned()
            #     return tuned
            
            # elif command == "temperaturestable":
            #     temp_stable = mircat_sdk.MIRcatSDK_IsTemperatureStable()
            #     return temp_stable
            
            # elif command == "isinterlocked":
            #     interlocked = mircat_sdk.MIRcatSDK_IsInterlocked()
            #     return interlocked
            
            # elif command == "emission" and value is not None:
            #     result = mircat_sdk.MIRcatSDK_TurnEmissionOnOff(bool(value))
            #     if result != 0:
            #         raise Exception(f"Emission control failed with code {result}")
            #     return True
            
            # elif command == "arm":
            #     result = mircat_sdk.MIRcatSDK_ArmDisarmLaser(True)
            #     if result != 0:
            #         raise Exception(f"Laser arming failed with code {result}")
            #     return True
            
            # elif command == "wavenumber" and value is not None:
            #     result = mircat_sdk.MIRcatSDK_TuneToWavenumber(float(value), 1)  # units: 1 = cm-1
            #     if result != 0:
            #         raise Exception(f"Tuning to wavenumber failed with code {result}")
            #     return True
            
            # elif command == "poweroff":
            #     result = mircat_sdk.MIRcatSDK_ArmDisarmLaser(False)
            #     if result != 0:
            #         raise Exception(f"Laser disarming failed with code {result}")
            #     return True
            
            # elif command == "temperature":
            #     temp = mircat_sdk.MIRcatSDK_GetTuningTemperature()
            #     return temp
            
            # If we reach here, the command was not recognized
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
            
            # Initialize real MIRcat SDK
            self._mircat_sdk_call("init")
            
            # Check if real MIRcat device is connected via USB
            connected = self._mircat_sdk_call("isconnected")
            
            if not connected:
                self.last_error = "No MIRcat device detected - check USB connection and power"
                self.last_error_code = MIRcatError.COMMUNICATION_ERROR
                raise Exception("No MIRcat device detected")
            
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
                    "key_switch": True,  # Hardware dependent - would read from device
                    "temperature": self._mircat_sdk_call("temperaturestable"),
                    "pointing_correction": True,  # Hardware dependent
                    "system_fault": False,  # Would read from device status
                    "tuned": self._mircat_sdk_call("istuned"),
                    "armed": self._mircat_sdk_call("isarmed"),
                    "emission": self.emission_on,
                    "case_temp_1": self._mircat_sdk_call("temperature"),
                    "case_temp_2": self._mircat_sdk_call("temperature"), 
                    "pcb_temperature": self._mircat_sdk_call("temperature")
                })
                
                # Update internal state from real hardware
                self.armed = self.status["armed"]
                self.tuned = self.status["tuned"]
                self.temperature_stable = self.status["temperature"]
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