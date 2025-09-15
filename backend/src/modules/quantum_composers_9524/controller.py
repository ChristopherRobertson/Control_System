"""
Quantum Composers 9524 Signal Generator Controller (Phase 1 UI scaffolding)

This controller provides an in-memory, validated state model for the
Quantum Composers 9524 signal generator. It is designed to support
Phase 1 UI development and end-to-end frontend→backend dispatch without
requiring live hardware. No serial/SDK I/O is performed in this phase.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, Any, Optional

import toml

logger = logging.getLogger(__name__)


@dataclass
class SystemSettings:
    pulse_mode: str = "Continuous"  # Continuous | Burst | Single
    period_s: float = 0.0001
    burst_count: int = 10
    auto_start: bool = False
    duty_cycle_on_counts: int = 4
    duty_cycle_off_counts: int = 2


@dataclass
class ChannelSettings:
    enabled: bool = True
    delay_s: float = 0.0
    width_s: float = 0.000001
    channel_mode: str = "Normal"  # Normal | Invert
    sync_source: str = "T0"
    duty_on: int = 2
    duty_off: int = 3
    burst_count: int = 5
    polarity: str = "Normal"
    output_mode: str = "TTL/CMOS"
    amplitude_v: float = 5.0
    wait_count: int = 0
    multiplexer: Dict[str, bool] = field(default_factory=lambda: {"A": False, "B": False, "C": False, "D": False})
    gate_mode: str = "Disabled"


@dataclass
class ExternalTrigger:
    trigger_mode: str = "Disabled"  # Disabled | Enabled
    trigger_edge: str = "Rising"    # Rising | Falling
    trigger_threshold_v: float = 2.5
    gate_mode: str = "Disabled"     # Disabled | Enabled
    gate_logic: str = "High"         # High | Low
    gate_threshold_v: float = 2.5


class QuantumComposers9524Controller:
    """Phase 1 controller with validated, in-memory state.

    Reads numeric ranges from `hardware_configuration.toml` so UI helper text
    and backend validation are aligned with documentation.
    """

    def __init__(self) -> None:
        self.connected: bool = False
        self.running: bool = False

        # Load config (ranges + connection info)
        self.config = self._load_config()
        self.ranges = self.config.get("parameters", {})

        # State models
        self.system = SystemSettings()
        self.channels: Dict[str, ChannelSettings] = {
            "A": ChannelSettings(enabled=True, multiplexer={"A": True, "B": False, "C": False, "D": False}),
            "B": ChannelSettings(enabled=False),
            "C": ChannelSettings(enabled=False),
            "D": ChannelSettings(enabled=False),
        }
        self.external = ExternalTrigger()

        # Device information (static for Phase 1)
        self.device_info: Dict[str, Any] = {
            "model": "Quantum Composers 9524",
            "serial_number": self.config.get("serial_number", "11496"),
            "firmware_version": self.config.get("firmware_version", "3.0.0.13"),
            "fpga_version": self.config.get("fpga_version", "2.0.2.8"),
            "transport": self.config.get("connection_type", "USB"),
            "port": self.config.get("port"),
            "baud_rate": self.config.get("baud_rate"),
        }

        # Last error snapshot
        self.last_error: Optional[str] = None
        self.last_error_code: Optional[int] = None

    # --------------------------- Config loading ---------------------------
    def _load_config(self) -> Dict[str, Any]:
        path = Path(__file__).parents[4] / "hardware_configuration.toml"
        try:
            cfg = toml.load(path)
            return cfg.get("quantum_composers_9524", {})
        except Exception as e:
            logger.warning(f"QC9524: failed to read hardware_configuration.toml: {e}")
            return {}

    # ------------------------------ Helpers -------------------------------
    def _clamp(self, value: float, min_key: str, max_key: str) -> float:
        lo = float(self.ranges.get(min_key, value))
        hi = float(self.ranges.get(max_key, value))
        if value < lo:
            return lo
        if value > hi:
            return hi
        return value

    def _clamp_int(self, value: int, min_key: str, max_key: str) -> int:
        lo = int(self.ranges.get(min_key, value))
        hi = int(self.ranges.get(max_key, value))
        if value < lo:
            return lo
        if value > hi:
            return hi
        return value

    # ------------------------------ Actions -------------------------------
    async def connect(self) -> bool:
        """Mark connected. Phase 1 does not open ports; validates config exists."""
        if not self.config.get("port"):
            self.last_error = "Missing COM port in hardware_configuration.toml"
            self.connected = False
            return False
        self.connected = True
        self.last_error = None
        await self._broadcast_state_update()
        return True

    async def disconnect(self) -> bool:
        self.connected = False
        self.running = False
        await self._broadcast_state_update()
        return True

    async def start_output(self) -> bool:
        if not self.connected:
            raise RuntimeError("Device not connected")
        self.running = True
        await self._broadcast_state_update()
        return True

    async def stop_output(self) -> bool:
        self.running = False
        await self._broadcast_state_update()
        return True

    async def set_system_config(self, cfg: Dict[str, Any]) -> bool:
        if "period_s" in cfg:
            cfg["period_s"] = float(self._clamp(float(cfg["period_s"]), "period_min_s", "period_max_s"))
        if "burst_count" in cfg:
            cfg["burst_count"] = int(self._clamp_int(int(cfg["burst_count"]), "burst_count_min", "burst_count_max"))
        if "duty_cycle_on_counts" in cfg:
            cfg["duty_cycle_on_counts"] = int(self._clamp_int(int(cfg["duty_cycle_on_counts"]), "duty_cycle_on_min", "duty_cycle_on_max"))
        if "duty_cycle_off_counts" in cfg:
            cfg["duty_cycle_off_counts"] = int(self._clamp_int(int(cfg["duty_cycle_off_counts"]), "duty_cycle_off_min", "duty_cycle_off_max"))
        for k, v in cfg.items():
            setattr(self.system, k, v)
        await self._broadcast_state_update()
        return True

    async def set_channel_config(self, channel: str, cfg: Dict[str, Any]) -> bool:
        ch = self.channels.get(channel)
        if not ch:
            raise ValueError(f"Invalid channel: {channel}")
        if "delay_s" in cfg:
            cfg["delay_s"] = float(self._clamp(float(cfg["delay_s"]), "delay_min_s", "delay_max_s"))
        if "width_s" in cfg:
            cfg["width_s"] = float(self._clamp(float(cfg["width_s"]), "width_min_s", "width_max_s"))
        if "amplitude_v" in cfg:
            cfg["amplitude_v"] = float(self._clamp(float(cfg["amplitude_v"]), "amplitude_min_v", "amplitude_max_v"))
        if "burst_count" in cfg:
            cfg["burst_count"] = int(max(1, int(cfg["burst_count"])) )
        for k, v in cfg.items():
            setattr(ch, k, v)
        await self._broadcast_state_update()
        return True

    async def set_external_trigger_config(self, cfg: Dict[str, Any]) -> bool:
        if "trigger_threshold_v" in cfg:
            cfg["trigger_threshold_v"] = float(self._clamp(float(cfg["trigger_threshold_v"]), "trigger_threshold_min_v", "trigger_threshold_max_v"))
        if "gate_threshold_v" in cfg:
            cfg["gate_threshold_v"] = float(self._clamp(float(cfg["gate_threshold_v"]), "gate_threshold_min_v", "gate_threshold_max_v"))
        for k, v in cfg.items():
            setattr(self.external, k, v)
        await self._broadcast_state_update()
        return True

    async def send_command(self, command: str) -> str:
        if not self.connected:
            raise RuntimeError("Device not connected")
        logger.info(f"QC9524 command (Phase 1 echo): {command}")
        return f"echo: {command}"

    async def get_status(self) -> Dict[str, Any]:
        return {
            "connected": self.connected,
            "running": self.running,
            "system_settings": asdict(self.system),
            "channels": {k: asdict(v) for k, v in self.channels.items()},
            "external_trigger": asdict(self.external),
            "device_info": self.device_info,
            "ranges": self.ranges,
            "last_error": self.last_error,
            "last_error_code": self.last_error_code,
        }

    async def _broadcast_state_update(self) -> None:
        # Phase 1: no live WebSocket broadcasting implemented.
        pass
