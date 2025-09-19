"""
Zurich Instruments HF2LI Controller (Phase 1 – live LabOne API)

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
import os
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
        self._api_level = 6
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

    def _extract_value(self, raw: Dict[str, Any]) -> Any:
        # The structure returned by get(flat=True) is a dict of path->{...}.
        # Each leaf commonly exposes 'value' (list) or 'vector'. Extract the
        # first scalar when possible to simplify UI consumption.
        for _path, payload in raw.items():
            if isinstance(payload, dict):
                if "value" in payload:
                    val = payload["value"]
                    if isinstance(val, list) and val:
                        return val[0]
                    return val
                # Some nodes use 'vector' for arrays
                if "vector" in payload:
                    vec = payload["vector"]
                    if isinstance(vec, list) and len(vec) == 1 and isinstance(vec[0], list) and vec[0]:
                        return vec[0][0]
                    return vec
                # Strings may be in 'string'
                if "string" in payload:
                    return payload["string"]
            # Fallback to the payload itself
            return payload
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

