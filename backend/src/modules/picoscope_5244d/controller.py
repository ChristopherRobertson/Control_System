"""
PicoScope 5244D Oscilloscope Controller

Implements control functions for the PicoScope 5244D MSO oscilloscope
using PicoSDK. Connection succeeds only if the SDK opens a device.
"""

import os
import toml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from ctypes import byref, c_int16, create_string_buffer

logger = logging.getLogger(__name__)


class PicoScope5244DController:
    """Controller for PicoScope 5244D MSO Oscilloscope"""

    def __init__(self):
        self.connected = False
        self.acquiring = False
        self.config = self._load_config()
        self.channels = {
            'A': {'enabled': True, 'range': '±2V', 'coupling': 'DC', 'offset': 0.0},
            'B': {'enabled': True, 'range': '±2V', 'coupling': 'DC', 'offset': 0.0},
            'C': {'enabled': False, 'range': '±2V', 'coupling': 'DC', 'offset': 0.0},
            'D': {'enabled': False, 'range': '±2V', 'coupling': 'DC', 'offset': 0.0}
        }
        self.timebase = {
            'scale': '1ms/div',
            'samples': 1000000,
            'duration': 10.0
        }
        self.trigger = {
            'source': 'Channel A',
            'level': 0.0,
            'direction': 'Rising',
            'enabled': True
        }

        # PicoSDK handle and info
        self._ps = None  # module ref after import
        self._handle: Optional[c_int16] = None
        self.model: Optional[str] = None
        self.serial: Optional[str] = None
        self.driver_version: Optional[str] = None
        self.transport: str = self.config.get('connection_type', 'USB')
        self.last_error: Optional[str] = None
        self.last_error_code: Optional[int] = None

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from hardware_configuration.toml"""
        config_path = Path(__file__).parent.parent.parent.parent.parent / "hardware_configuration.toml"
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = toml.load(f)
            return config.get('picoscope_5244d', {})
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}

    def _prepare_dll_search_paths(self) -> None:
        """Ensure Windows DLL search path includes PicoSDK lib directory.

        Order of resolution:
        - Env var `PICO_SDK_PATH`
        - Config `sdk_path` from hardware_configuration.toml
        - Program Files default: C:\\Program Files\\Pico Technology\\SDK
        """
        if os.name != 'nt':
            return
        candidates = []
        env_path = os.environ.get('PICO_SDK_PATH')
        if env_path:
            candidates.append(env_path)
        cfg_path = self.config.get('sdk_path')
        if cfg_path:
            candidates.append(cfg_path)
        prog_files = os.environ.get('ProgramFiles', r"C:\\Program Files")
        candidates.append(os.path.join(prog_files, 'Pico Technology', 'SDK'))

        # Add their lib subfolder if present; add root too for good measure
        for base in candidates:
            for path in (base, os.path.join(base, 'lib')):
                if os.path.isdir(path):
                    try:
                        os.add_dll_directory(path)  # type: ignore[attr-defined]
                    except Exception:
                        pass

    def _require_sdk(self):
        if self._ps is not None:
            return
        try:
            self._prepare_dll_search_paths()
            from picosdk.ps5000a import ps5000a as ps  # type: ignore
            self._ps = ps
        except Exception as e:
            raise RuntimeError(f"PicoSDK (picosdk.ps5000a) not available: {e}")

    def _get_unit_info(self, info_code: int, buf_len: int = 64) -> str:
        assert self._ps is not None and self._handle is not None
        buf = create_string_buffer(buf_len)
        req = c_int16()
        # ps5000aGetUnitInfo(handle, infoString, stringLength, requiredSize, info)
        status = self._ps.ps5000aGetUnitInfo(self._handle, buf, c_int16(buf_len), byref(req), info_code)
        if status != 0:
            # Non-zero is error; best effort logging
            self.last_error_code = int(status)
            logger.warning(f"ps5000aGetUnitInfo({info_code}) returned {status}")
            return ""
        return buf.value.decode(errors='ignore')

    async def connect(self) -> bool:
        """Connect to PicoScope device using PicoSDK. Sets connected=True only on success."""
        try:
            logger.info("Connecting to PicoScope 5244D via PicoSDK...")
            self._require_sdk()

            # Open any available unit
            self._handle = c_int16()
            status = self._ps.ps5000aOpenUnit(byref(self._handle), None)
            if status != 0:
                self.connected = False
                self.last_error_code = int(status)
                self.last_error = f"ps5000aOpenUnit failed with code {status}"
                raise RuntimeError(self.last_error)

            # Fetch device info (codes based on PicoSDK PICO_INFO)
            # 3 = VARIANT_INFO, 4 = BATCH_AND_SERIAL, 0 = DRIVER_VERSION
            self.model = self._get_unit_info(3) or "PicoScope 5000A"
            self.serial = self._get_unit_info(4) or None
            self.driver_version = self._get_unit_info(0) or None

            self.connected = True
            self.acquiring = False
            self.last_error = None
            self.last_error_code = None
            await self._broadcast_state_update()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to PicoScope: {e}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from PicoScope device"""
        try:
            if self._ps is not None and self._handle is not None:
                try:
                    self._ps.ps5000aCloseUnit(self._handle)
                except Exception as e:
                    logger.warning(f"Error during ps5000aCloseUnit: {e}")
            self._handle = None
            self.connected = False
            self.acquiring = False
            await self._broadcast_state_update()
            return True
        except Exception as e:
            logger.error(f"Failed to disconnect from PicoScope: {e}")
            return False

    async def start_acquisition(self) -> bool:
        """Start data acquisition (not yet implemented)."""
        if not self.connected:
            raise Exception("Device not connected")
        raise Exception("Start acquisition not implemented yet")

    async def stop_acquisition(self) -> bool:
        """Stop data acquisition (not yet implemented)."""
        if not self.connected:
            return True
        raise Exception("Stop acquisition not implemented yet")

    async def set_channel_config(self, channel: str, config: Dict[str, Any]) -> bool:
        """Configure oscilloscope channel (state updated; SDK call TBD)."""
        if channel not in self.channels:
            raise Exception(f"Invalid channel: {channel}")
        self.channels[channel].update(config)
        await self._broadcast_state_update()
        return True

    async def set_timebase_config(self, config: Dict[str, Any]) -> bool:
        """Configure timebase settings (state updated; SDK call TBD)."""
        self.timebase.update(config)
        await self._broadcast_state_update()
        return True

    async def set_trigger_config(self, config: Dict[str, Any]) -> bool:
        """Configure trigger settings (state updated; SDK call TBD)."""
        self.trigger.update(config)
        await self._broadcast_state_update()
        return True

    async def auto_setup(self) -> bool:
        """Perform auto setup (not yet implemented)."""
        raise Exception("Auto setup not implemented yet")

    async def get_status(self) -> Dict[str, Any]:
        """Get current device status"""
        return {
            "connected": self.connected,
            "acquiring": self.acquiring,
            "channels": self.channels,
            "timebase": self.timebase,
            "trigger": self.trigger,
            "model": self.model,
            "serial": self.serial,
            "driver_version": self.driver_version,
            "transport": self.transport,
            "last_error": self.last_error,
            "last_error_code": self.last_error_code,
        }

    async def _broadcast_state_update(self) -> None:
        """Broadcast state update via WebSocket (global endpoint polls periodically)."""
        logger.info("PicoScope state updated")
        # The global /ws/{device} endpoint in main.py polls controller status.
        return None
