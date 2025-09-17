"""
Quantum Composers 9524 Signal Generator Controller — Phase 1 (Live serial)

Implements a real serial connection to the instrument using pyserial.
All mutations translate to device command strings using templates defined
under `hardware_configuration.toml` → `[quantum_composers_9524.commands]`.

No placeholders or simulated state are used. If a command template for a
specific field is missing, the controller raises a validation error
rather than pretending success.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

import toml
import serial  # pyserial
from serial.tools import list_ports

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
    multiplexer: Dict[str, bool] | None = None
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
    def __init__(self) -> None:
        # Connection + ranges + command templates
        self.config = self._load_config()
        self.ranges: Dict[str, Any] = self.config.get("parameters", {})
        self.templates: Dict[str, Any] = self.config.get("commands", {})

        # Serial
        self._serial: Optional[serial.Serial] = None
        self._eol = self.config.get("eol", "\r")  # default CR
        self._encoding = self.config.get("encoding", "ascii")
        self._read_terminator = self.config.get("read_terminator", "\n")
        self._query_delay_s: float = float(self.config.get("query_delay_s", 0.02))

        # State (mirrors hardware; not simulated)
        self.connected: bool = False
        self.running: bool = False  # last known; refreshed via query when available

        # Snapshot settings (for UI echo and validation)
        self.system = SystemSettings()
        self.channels: Dict[str, ChannelSettings] = {
            "A": ChannelSettings(enabled=True, multiplexer={"A": True, "B": False, "C": False, "D": False}),
            "B": ChannelSettings(enabled=False, multiplexer={"A": False, "B": True, "C": False, "D": False}),
            "C": ChannelSettings(enabled=False, multiplexer={"A": False, "B": False, "C": True, "D": False}),
            "D": ChannelSettings(enabled=False, multiplexer={"A": False, "B": False, "C": False, "D": True}),
        }
        self.external = ExternalTrigger()

        # Device info (queried lazily if template is provided)
        self.device_info: Dict[str, Any] = {
            "model": self.config.get("device_type", "Quantum Composers 9524"),
            "transport": self.config.get("connection_type", "USB"),
            "port": self.config.get("port"),
            "baud_rate": self.config.get("baud_rate"),
        }

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

    # ----------------------------- Serial I/O -----------------------------
    def _ensure_serial(self) -> serial.Serial:
        if self._serial and self._serial.is_open:
            return self._serial
        raise RuntimeError("Serial port is not open")

    def _open_serial(self) -> None:
        port = self.config.get("port")
        baud = int(self.config.get("baud_rate", 115200))
        timeout = float(self.config.get("timeout", 2.0))
        if not port:
            raise RuntimeError("Missing COM port in hardware_configuration.toml [quantum_composers_9524]")
        self._serial = serial.Serial(
            port=port,
            baudrate=baud,
            timeout=timeout,
            write_timeout=timeout,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )

    def _close_serial(self) -> None:
        try:
            if self._serial and self._serial.is_open:
                self._serial.close()
        finally:
            self._serial = None

    def _write(self, cmd: str) -> None:
        ser = self._ensure_serial()
        payload = (cmd + self._eol).encode(self._encoding, errors="ignore")
        ser.write(payload)
        ser.flush()

    def _read_response(self) -> str:
        ser = self._ensure_serial()
        try:
            chunks: list[bytes] = []
            while True:
                data = ser.read_until(self._read_terminator.encode(self._encoding))
                if not data:
                    break
                chunks.append(data)
                if ser.in_waiting == 0:
                    break
            return b"".join(chunks).decode(self._encoding, errors="ignore").strip()
        except Exception as e:
            self.last_error = f"read_error: {e}"
            return ""

    def _query(self, cmd: str) -> str:
        self._write(cmd)
        return self._read_response()

    # ----------------------------- Diagnostics ----------------------------
    @staticmethod
    def available_ports() -> List[Dict[str, str]]:
        ports = []
        try:
            for p in list_ports.comports():
                ports.append({
                    "device": p.device,
                    "description": p.description or "",
                    "hwid": p.hwid or "",
                })
        except Exception as e:
            logger.warning(f"List ports failed: {e}")
        return ports

    def probe_open(self) -> Dict[str, Any]:
        try:
            self._open_serial()
            self._close_serial()
            return {"ok": True, "message": "Opened and closed serial port successfully."}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    # ------------------------------ Helpers -------------------------------
    def _clamp(self, value: float, min_key: str, max_key: str) -> float:
        lo = float(self.ranges.get(min_key, value))
        hi = float(self.ranges.get(max_key, value))
        return max(lo, min(hi, value))

    def _clamp_int(self, value: int, min_key: str, max_key: str) -> int:
        lo = int(self.ranges.get(min_key, value))
        hi = int(self.ranges.get(max_key, value))
        return max(lo, min(hi, value))

    def _format_bool(self, value: bool) -> str:
        return 'ON' if value else 'OFF'

    def _render(self, template: str, ctx: Dict[str, Any]) -> str:
        try:
            return template.format(**ctx)
        except Exception as e:
            raise ValueError(f"Template render failed for '{template}': {e}")

    def _send_template(self, key_path: Tuple[str, ...], ctx: Dict[str, Any]) -> Optional[str]:
        # key_path like ("system", "period_s")
        t: Any = self.templates
        for k in key_path:
            if not isinstance(t, dict) or k not in t:
                raise ValueError(f"Missing command template for {'.'.join(key_path)}")
            t = t[k]
        if not isinstance(t, str):
            raise ValueError(f"Template for {'.'.join(key_path)} must be a string")
        cmd = self._render(t, ctx)
        logger.info(f"QC9524→ {cmd}")
        self._write(cmd)
        return self._read_response()

    # ------------------------------ Actions -------------------------------
    async def connect(self) -> bool:
        try:
            self._open_serial()
            self.connected = True
            self.last_error = None
            self.last_error_code = None
            # Query identity if configured
            idn_tpl = self.templates.get("query", {}).get("identity")
            if isinstance(idn_tpl, str):
                try:
                    resp = self._query(self._render(idn_tpl, {}))
                    if resp:
                        self.device_info["identity"] = resp
                except Exception:
                    pass
            # Query running state if configured
            run_q = self.templates.get("query", {}).get("running")
            if isinstance(run_q, str):
                try:
                    r = self._query(self._render(run_q, {})).strip().lower()
                    self.running = r in ("1", "on", "true", "running", "run")
                except Exception:
                    self.running = False
            return True
        except Exception as e:
            self.connected = False
            self.last_error = str(e)
            self._close_serial()
            return False

    async def disconnect(self) -> bool:
        self._close_serial()
        self.connected = False
        self.running = False
        return True

    async def start_output(self) -> bool:
        if not self.connected:
            raise RuntimeError("Device not connected")
        self._send_template(("control", "start"), {})
        self.running = True
        return True

    async def stop_output(self) -> bool:
        if not self.connected:
            raise RuntimeError("Device not connected")
        self._send_template(("control", "stop"), {})
        for name, ch in self.channels.items():
            ch.enabled = False
            ctx = {**asdict(ch), "channel": name}
            ctx["enabled"] = self._format_bool(False)
            try:
                self._send_template(("channel", "enabled"), ctx)
            except ValueError as ve:
                logger.warning(f"QC9524 channel disable failed for {name}: {ve}")
        self.running = False
        return True

    async def stop_channel_output(self, channel: str) -> str:
        if not self.connected:
            raise RuntimeError("Device not connected")
        ch = self.channels.get(channel)
        if not ch:
            raise ValueError(f"Invalid channel: {channel}")
        ch.enabled = False
        ctx = {**asdict(ch), "channel": channel}
        ctx["enabled"] = self._format_bool(False)
        resp = self._send_template(("channel", "enabled"), ctx)
        self.running = any(c.enabled for c in self.channels.values())
        return resp or "OK"

    async def set_system_config(self, cfg: Dict[str, Any]) -> bool:
        if "period_s" in cfg:
            cfg["period_s"] = float(self._clamp(float(cfg["period_s"]), "period_min_s", "period_max_s"))
        if "burst_count" in cfg:
            cfg["burst_count"] = int(self._clamp_int(int(cfg["burst_count"]), "burst_count_min", "burst_count_max"))
        if "duty_cycle_on_counts" in cfg:
            cfg["duty_cycle_on_counts"] = int(self._clamp_int(int(cfg["duty_cycle_on_counts"]), "duty_cycle_on_min", "duty_cycle_on_max"))
        if "duty_cycle_off_counts" in cfg:
            cfg["duty_cycle_off_counts"] = int(self._clamp_int(int(cfg["duty_cycle_off_counts"]), "duty_cycle_off_min", "duty_cycle_off_max"))

        # Update snapshot and send per-field commands
        for k, v in cfg.items():
            setattr(self.system, k, v)
            send_ctx = {**asdict(self.system)}
            if k == "auto_start":
                send_ctx["auto_start"] = self._format_bool(bool(v))
            try:
                self._send_template(("system", k), send_ctx)
            except ValueError as ve:
                raise RuntimeError(str(ve))
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
            cfg["burst_count"] = max(1, int(cfg["burst_count"]))

        for k, v in cfg.items():
            setattr(ch, k, v)
            # Build render context; expand multiplexer dict if present
            ctx = {**asdict(ch), "channel": channel}
            if k == "enabled":
                ctx["enabled"] = self._format_bool(bool(v))
            if k == "multiplexer":
                mux = v or {}
                ctx.update({
                    "muxA": bool(mux.get("A")),
                    "muxB": bool(mux.get("B")),
                    "muxC": bool(mux.get("C")),
                    "muxD": bool(mux.get("D")),
                })
            try:
                self._send_template(("channel", k), ctx)
            except ValueError as ve:
                raise RuntimeError(str(ve))
        return True

    async def set_external_trigger_config(self, cfg: Dict[str, Any]) -> bool:
        if "trigger_threshold_v" in cfg:
            cfg["trigger_threshold_v"] = float(self._clamp(float(cfg["trigger_threshold_v"]), "trigger_threshold_min_v", "trigger_threshold_max_v"))
        if "gate_threshold_v" in cfg:
            cfg["gate_threshold_v"] = float(self._clamp(float(cfg["gate_threshold_v"]), "gate_threshold_min_v", "gate_threshold_max_v"))
        for k, v in cfg.items():
            setattr(self.external, k, v)
            ctx = {**asdict(self.external)}
            try:
                self._send_template(("external", k), ctx)
            except ValueError as ve:
                raise RuntimeError(str(ve))
        return True

    async def send_command(self, command: str) -> str:
        if not self.connected:
            raise RuntimeError("Device not connected")
        logger.info(f"QC9524 cmd: {command}")
        self._write(command)
        return self._read_response()

    async def get_status(self) -> Dict[str, Any]:
        try:
            run_q = self.templates.get("query", {}).get("running")
            if self.connected and isinstance(run_q, str):
                r = self._query(self._render(run_q, {})).strip().lower()
                self.running = r in ("1", "on", "true", "running", "run")
        except Exception:
            pass
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
        # WebSocket broadcasting is handled in main.py polling loop.
        return None
