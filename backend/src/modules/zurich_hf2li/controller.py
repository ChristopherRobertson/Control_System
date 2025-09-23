"""
Zurich Instruments HF2LI Controller (Phase 1 - live LabOne API)

This module implements a thin wrapper around Zurich Instruments' LabOne
Data Server via the official `zhinst` Python package. It provides a
connection lifecycle and generic helpers to get/set node values so the
frontend can wire concrete controls without stubs or simulation.

Notes
- API level 6 is used for HF2 devices.
- We avoid hardcoding an exhaustive node map. Instead, the routes expose
  generic `nodes/get` and `nodes/set` operations that pass through to
  LabOne. This guarantees that real API calls are made and responses are
  truthful.
- Device discovery is supported when `device_id` is set to "AUTO".
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
from array import array as array_type
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import toml

logger = logging.getLogger(__name__)


Number = Union[int, float]
Scalar = Union[Number, bool, str]


def _read_hardware_config() -> Dict[str, Any]:
    path = Path(__file__).parents[4] / "hardware_configuration.toml"
    try:
        cfg = toml.load(path)
        return cfg.get("zurich_hf2li", {})
    except Exception as e:
        logger.warning("HF2LI: failed to read hardware_configuration.toml: %s", e)
        return {}


@dataclass
class HF2LIStatus:
    connected: bool
    server_connected: bool
    host: Optional[str]
    data_server_port: Optional[int]
    api_level: Optional[int]
    device_id: Optional[str]
    server_version: Optional[str]
    device_present: Optional[bool]
    last_error: Optional[str]


class ZurichHF2LIController:
    def __init__(self) -> None:
        self.config: Dict[str, Any] = _read_hardware_config()
        self.host: str = os.getenv("LABONE_HOST", self.config.get("host", "127.0.0.1"))
        self.data_server_port: int = int(os.getenv("LABONE_DATA_PORT", self.config.get("data_server_port", 8005)))
        # Device id must be in LabOne notation, e.g., "dev18500"; "AUTO" enables discovery.
        self.device_id: str = os.getenv("HF2LI_DEVICE_ID", self.config.get("device_id", "AUTO"))

        self._daq = None  # type: ignore[attr-defined]
        self._api_level = 1
        self._connected: bool = False
        self._server_connected: bool = False
        self._server_version: Optional[str] = None
        self._device_present: Optional[bool] = None
        self.last_error: Optional[str] = None

    # ---------------------------- Core helpers ----------------------------
    def _ensure_daq(self):
        if self._daq is None:
            raise RuntimeError("LabOne Data Server is not connected")
        return self._daq

    # ------------------------------ Connect -------------------------------
    async def connect(self) -> bool:
        """Connect to LabOne Data Server and validate the target device.

        Returns True on success. This performs real API calls using the
        `zhinst.core.ziDAQServer` client. On failure, `last_error` is set.
        """
        try:
            # Resolve zhinst imports lazily so other modules don't require it.
            from zhinst.core import ziDAQServer, ziDiscovery
        except Exception as e:  # pragma: no cover - import error path
            self.last_error = f"zhinst import error: {e}"
            logger.exception("HF2LI: failed to import zhinst")
            return False

        try:
            self._daq = ziDAQServer(self.host, self.data_server_port, self._api_level)
            self._server_connected = True
        except Exception as e:
            self.last_error = f"Failed to connect to LabOne Data Server at {self.host}:{self.data_server_port}: {e}"
            logger.exception(self.last_error)
            self._server_connected = False
            self._daq = None
            return False

        # Try to read a server version string as a basic sanity check.
        try:
            self._server_version = self._daq.getString("/zi/about/version")  # type: ignore[attr-defined]
        except Exception:
            # Not all servers expose this string; ignore but keep connected.
            self._server_version = None

        # Device validation
        dev_id = self.device_id
        if not dev_id or dev_id.upper() == "AUTO":
            # Discover devices and prefer HF2LI.
            try:
                disc = ziDiscovery()
                entries = disc.findAll()
                # entries like ['HF2LI-DEV18500', '...']
                hf2 = next((e for e in entries if str(e).upper().startswith("HF2LI-DEV")), None)
                if hf2:
                    dev_id = disc.find(hf2)
                else:
                    # Fall back to the first device entry if present
                    dev_id = disc.find(entries[0]) if entries else None
            except Exception as e:
                logger.warning("HF2LI: device discovery failed: %s", e)
                dev_id = None

        if dev_id is None:
            self._connected = False
            self._device_present = False
            self.last_error = "No compatible device found via discovery; set [zurich_hf2li].device_id to 'dev<serial>'."
            return False

        # Probe a simple subtree on the device to confirm presence.
        try:
            subtree = f"/{dev_id}/*"
            result = self._daq.get(subtree, flat=True, settingsonly=True)  # type: ignore[attr-defined]
            self._device_present = bool(result)
            self._connected = True and self._device_present
            self.device_id = dev_id
            return True if self._device_present else False
        except Exception as e:
            self._connected = False
            self._device_present = False
            self.last_error = f"Device probe failed for {dev_id}: {e}"
            logger.exception(self.last_error)
            return False

    async def disconnect(self) -> None:
        try:
            if self._daq is not None:
                # There is no explicit close; deleting the object drops the connection.
                try:
                    self._daq.setDebugLevelConsole(0)  # noop but forces call
                except Exception:
                    pass
        finally:
            self._daq = None
            self._connected = False
            self._server_connected = False

    # ------------------------------ Status --------------------------------
    async def get_status(self) -> Dict[str, Any]:
        return {
            "connected": bool(self._connected),
            "server_connected": bool(self._server_connected),
            "host": self.host,
            "data_server_port": self.data_server_port,
            "api_level": self._api_level,
            "device_id": self.device_id,
            "server_version": self._server_version,
            "device_present": self._device_present,
            "last_error": self.last_error,
        }

    # ------------------------------ Nodes ---------------------------------
    def _coerce_and_set(self, path: str, value: Scalar) -> None:
        daq = self._ensure_daq()
        try:
            if isinstance(value, bool):
                daq.setInt(path, int(value))
            elif isinstance(value, int):
                daq.setInt(path, value)
            elif isinstance(value, float):
                daq.setDouble(path, float(value))
            else:
                daq.setString(path, str(value))
        except Exception as e:
            raise RuntimeError(f"set failed for '{path}' -> {value}: {e}")

    def _simplify_value(self, value: Any) -> Any:
        if hasattr(value, 'tolist'):
            value = value.tolist()
        elif isinstance(value, array_type):
            value = list(value)

        if isinstance(value, (list, tuple)):
            simplified = [self._simplify_value(v) for v in value]
            if len(simplified) == 1:
                return simplified[0]
            return simplified
        if isinstance(value, dict):
            return {k: self._simplify_value(v) for k, v in value.items()}
        return value

    def _extract_value(self, raw: Dict[str, Any]) -> Any:
        # The structure returned by get(flat=True) is a dict of path->{...}.
        # Each leaf commonly exposes 'value' (list) or 'vector'. Extract the
        # first scalar when possible to simplify UI consumption.
        for _path, payload in raw.items():
            if isinstance(payload, dict):
                if "value" in payload:
                    return self._simplify_value(payload["value"])
                if "vector" in payload:
                    return self._simplify_value(payload["vector"])
                if "string" in payload:
                    return payload["string"]
            return self._simplify_value(payload)
        return None

    async def get_nodes(self, paths: Iterable[str]) -> Dict[str, Any]:
        daq = self._ensure_daq()
        out: Dict[str, Any] = {}
        for path in paths:
            try:
                data = daq.get(path, flat=True, settingsonly=False)
                out[path] = self._extract_value(data)
            except Exception as e:
                out[path] = {"error": str(e)}
        return out

    async def set_nodes(self, settings: Iterable[Tuple[str, Scalar]]) -> Dict[str, Any]:
        daq = self._ensure_daq()
        results: Dict[str, Any] = {}
        for path, value in settings:
            try:
                self._coerce_and_set(path, value)
                results[path] = "ok"
            except Exception as e:
                results[path] = {"error": str(e)}
        try:
            # Ensure the server processed all sets before returning
            daq.sync()  # type: ignore[attr-defined]
        except Exception:
            pass
        return results

    async def zero_demod_phase(self, demod_index: int) -> float:
        if demod_index < 0:
            raise ValueError("demod_index must be non-negative")
        daq = self._ensure_daq()
        if not self.device_id:
            raise RuntimeError("HF2LI device id not resolved; connect first")

        base = f"/{self.device_id}/demods/{demod_index}"
        sample_path = f"{base}/sample"
        phase_path = f"{base}/phaseshift"

        try:
            sample = daq.getSample(sample_path)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - hardware specific
            raise RuntimeError(f"Failed to acquire demod sample for {demod_index}: {exc}")

        try:
            x_val = float(sample.get("x", [0.0])[0])
            y_val = float(sample.get("y", [0.0])[0])
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"Unexpected demod sample payload: {sample}: {exc}")

        if x_val == 0.0 and y_val == 0.0:
            raise RuntimeError("Demodulator sample is zero; cannot determine phase")

        current_phase_data = await self.get_nodes([phase_path])
        current_phase_raw = current_phase_data.get(phase_path, 0.0)
        try:
            current_phase = float(current_phase_raw)
        except Exception:
            current_phase = 0.0

        measured_phase = math.degrees(math.atan2(y_val, x_val))
        new_phase = current_phase - measured_phase

        # Wrap to [-180, 180)
        new_phase = ((new_phase + 180.0) % 360.0) - 180.0

        try:
            self._coerce_and_set(phase_path, new_phase)
            daq.sync()  # type: ignore[attr-defined]
        except Exception as exc:
            raise RuntimeError(f"Failed to apply phase shift {new_phase:.3f}°: {exc}")

        return new_phase



