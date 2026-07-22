"""Real Zurich Instruments HF2LI LabOne service adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable, TextIO
import csv
import json
import math
import os
import re
import sys

import yaml

from control_app.config_loader import REPO_ROOT, load_hardware_config


DEFAULT_LABONE_PACKAGE_PATHS = (
    r"C:\Users\Chris\AppData\Local\Temp\zhinst_26_4",
)
DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_SERVER_PORT = 8005
DEFAULT_API_LEVEL = 1
DEFAULT_DEVICE_INTERFACE = "USB"
DEFAULT_SUBSCRIBE_FIELDS = ("x", "y", "r")


class HF2LIError(RuntimeError):
    """Base error for HF2LI service failures."""


class HF2LIConfigurationError(HF2LIError):
    """Raised when HF2LI configuration or presets are missing."""


class HF2LIConnectionError(HF2LIError):
    """Raised when LabOne or the configured HF2LI cannot be reached."""


@dataclass(frozen=True)
class HF2LIPreset:
    """Named HF2LI preset loaded from recipes/hf2li_presets.yaml."""

    name: str
    settings: dict[str, Any]


class HF2LIService:
    """Real LabOne adapter for a configured Zurich Instruments HF2LI."""

    def __init__(
        self,
        device_config: dict[str, Any],
        *,
        command_log: TextIO | None = None,
    ) -> None:
        self.device_config = device_config
        self.command_log = command_log
        self._zi_module = None
        self._server = None
        self._device_id: str | None = None
        self._subscribed_paths: list[str] = []

    @classmethod
    def from_config(
        cls,
        *,
        config_path: str | Path | None = None,
        command_log: TextIO | None = None,
    ) -> "HF2LIService":
        """Create a service from hardware_configuration.yaml."""

        config, _, _ = load_hardware_config(config_path)
        devices = config.get("devices") or {}
        device_config = devices.get("hf2li")
        if not isinstance(device_config, dict):
            raise HF2LIConfigurationError("hf2li missing from hardware configuration")
        return cls(device_config, command_log=command_log)

    @property
    def device_id(self) -> str:
        """Return the selected LabOne device ID."""

        if self._device_id is None:
            raise HF2LIConnectionError("HF2LI device ID has not been discovered")
        return self._device_id

    def connect(self) -> None:
        """Connect to the real LabOne API server."""

        zi = self._load_labone_module()
        host = str(self.device_config.get("server_host") or DEFAULT_SERVER_HOST)
        port = int(self.device_config.get("server_port") or DEFAULT_SERVER_PORT)
        api_level = int(self.device_config.get("api_level") or DEFAULT_API_LEVEL)
        self._log(f"connect ziDAQServer host={host} port={port} api_level={api_level}")
        try:
            self._server = zi.ziDAQServer(host, port, api_level)
        except Exception as exc:  # LabOne raises extension-specific exceptions.
            raise HF2LIConnectionError(
                f"LabOne API server connection failed at {host}:{port}: {exc}"
            ) from exc
        self._device_id = self.resolve_device_id()

    def discover_device_ids(self) -> list[str]:
        """Discover visible or connected LabOne device IDs."""

        server = self._require_server()
        discovered: set[str] = set()
        attempts = [
            ("getList", "/zi/devices/connected"),
            ("getList", "/zi/devices/visible"),
            ("getString", "/zi/devices/connected"),
            ("getString", "/zi/devices/visible"),
            ("listNodes", "/"),
        ]
        for method_name, path in attempts:
            method = getattr(server, method_name, None)
            if method is None:
                continue
            try:
                value = method(path)
            except Exception as exc:
                self._log(f"discovery {method_name} {path} failed: {exc}")
                continue
            discovered.update(_extract_device_ids(value))

        configured = self._configured_device_id()
        if configured and configured not in discovered and self._device_has_nodes(configured):
            discovered.add(configured)
        result = sorted(discovered)
        self._log(f"discovered_devices={result}")
        return result

    def resolve_device_id(self) -> str:
        """Select the configured device ID after discovery."""

        configured = self._configured_device_id()
        discovered = self.discover_device_ids()
        if configured:
            if discovered and configured not in discovered:
                raise HF2LIConnectionError(
                    f"configured HF2LI {configured} not discovered; discovered={discovered}"
                )
            if not discovered and not self._device_has_nodes(configured):
                raise HF2LIConnectionError(
                    f"configured HF2LI {configured} is not reachable through LabOne"
                )
            self._connect_device_if_supported(configured)
            return configured
        if not discovered:
            raise HF2LIConnectionError("no LabOne HF2LI device IDs were discovered")
        self._connect_device_if_supported(discovered[0])
        return discovered[0]

    def load_preset(
        self,
        name: str,
        *,
        presets_path: str | Path = REPO_ROOT / "recipes" / "hf2li_presets.yaml",
    ) -> HF2LIPreset:
        """Load one named HF2LI preset from YAML."""

        path = Path(presets_path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        presets = data.get("presets")
        if not isinstance(presets, dict) or name not in presets:
            raise HF2LIConfigurationError(f"HF2LI preset {name!r} not found in {path}")
        preset = presets[name]
        if not isinstance(preset, dict):
            raise HF2LIConfigurationError(f"HF2LI preset {name!r} must be a mapping")
        return HF2LIPreset(name=name, settings=preset)

    def apply_preset(self, preset: HF2LIPreset) -> dict[str, Any]:
        """Apply CH1/CH2 inputs, PLL, and demodulator settings from a preset."""

        self.configure_signal_inputs(preset.settings.get("signal_inputs") or {})
        self.configure_pll(preset.settings.get("pll") or {})
        self.configure_oscillators(preset.settings.get("oscillators") or [])
        self.configure_demodulators(preset.settings.get("demodulators") or [])
        self.sync()
        applied = {
            "preset": preset.name,
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "device_id": self.device_id,
        }
        self._log(f"applied_preset={preset.name}")
        return applied

    def configure_signal_inputs(self, signal_inputs: dict[str, Any]) -> None:
        """Configure HF2LI Signal Input 1 and Signal Input 2 nodes."""

        for label, settings in signal_inputs.items():
            if not isinstance(settings, dict):
                raise HF2LIConfigurationError(f"signal input {label!r} must be a mapping")
            index = int(settings.get("index", _default_input_index(str(label))))
            base = f"/{self.device_id}/sigins/{index}"
            setters = {
                "ac": ("setInt", f"{base}/ac", _bool_int(settings.get("ac"))),
                "impedance_50ohm": (
                    "setInt",
                    f"{base}/imp50",
                    _bool_int(settings.get("impedance_50ohm")),
                ),
                "differential": (
                    "setInt",
                    f"{base}/diff",
                    _bool_int(settings.get("differential")),
                ),
                "range_v": ("setDouble", f"{base}/range", settings.get("range_v")),
            }
            for key, (method, path, value) in setters.items():
                if settings.get(key) is not None:
                    self._set_node(method, path, value)

    def configure_pll(self, pll: dict[str, Any]) -> None:
        """Configure the HF2LI PLL external reference path."""

        if not pll:
            return
        index = int(pll.get("index", 0))
        base = f"/{self.device_id}/plls/{index}"
        if pll.get("enable") is not None:
            self._set_node("setInt", f"{base}/enable", 0)
        setters = [
            ("adcselect", "setInt", pll.get("adcselect")),
            ("freqcenter", "setDouble", pll.get("freqcenter_hz")),
            ("harmonic", "setInt", pll.get("harmonic")),
            ("order", "setInt", pll.get("order")),
            ("adcthreshold", "setInt", pll.get("adcthreshold")),
        ]
        for node, method, value in setters:
            if value is not None:
                self._set_node(method, f"{base}/{node}", value)
        if pll.get("enable") is not None:
            self._set_node("setInt", f"{base}/enable", _bool_int(pll.get("enable")))

    def configure_oscillators(self, oscillators: Iterable[dict[str, Any]]) -> None:
        """Configure HF2LI internal oscillator frequencies used by demodulators."""

        for settings in oscillators:
            if not isinstance(settings, dict):
                raise HF2LIConfigurationError("each oscillator preset must be a mapping")
            index = int(settings["index"])
            base = f"/{self.device_id}/oscs/{index}"
            frequency_hz = settings.get("frequency_hz")
            if frequency_hz is not None:
                self._set_node("setDouble", f"{base}/freq", frequency_hz)

    def configure_demodulators(self, demodulators: Iterable[dict[str, Any]]) -> None:
        """Configure HF2LI demodulators used for detector CH1/CH2."""

        for settings in demodulators:
            if not isinstance(settings, dict):
                raise HF2LIConfigurationError("each demodulator preset must be a mapping")
            index = int(settings["index"])
            base = f"/{self.device_id}/demods/{index}"
            setters = [
                ("enable", "setInt", _bool_int(settings.get("enable"))),
                ("adcselect", "setInt", settings.get("adcselect")),
                ("oscselect", "setInt", settings.get("oscselect")),
                ("harmonic", "setInt", settings.get("harmonic")),
                ("order", "setInt", settings.get("order")),
                ("timeconstant", "setDouble", settings.get("timeconstant_s")),
                ("rate", "setDouble", settings.get("rate_sps")),
                ("trigger", "setInt", settings.get("trigger")),
            ]
            for node, method, value in setters:
                if value is not None:
                    self._set_node(method, f"{base}/{node}", value)

    def export_settings_snapshot(
        self,
        path: str | Path | None = None,
        *,
        preset: HF2LIPreset | None = None,
    ) -> dict[str, Any]:
        """Read back HF2LI settings and optionally write a JSON snapshot."""

        nodes = list(self._snapshot_nodes(preset))
        snapshot: dict[str, Any] = {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "device_id": self.device_id,
            "preset": preset.name if preset else None,
            "nodes": {},
            "read_errors": {},
        }
        for node_path, value_type in nodes:
            try:
                value = self._get_node(value_type, node_path)
            except Exception as exc:
                snapshot["read_errors"][node_path] = str(exc)
                continue
            snapshot["nodes"][node_path] = {"type": value_type, "value": value}
        if path is not None:
            self._write_json(path, snapshot)
        return snapshot

    def reload_settings_snapshot(self, snapshot_or_path: str | Path | dict[str, Any]) -> dict[str, Any]:
        """Reload settings from a previously exported HF2LI settings snapshot."""

        if isinstance(snapshot_or_path, (str, Path)):
            with Path(snapshot_or_path).open("r", encoding="utf-8") as handle:
                snapshot = json.load(handle)
        else:
            snapshot = snapshot_or_path
        nodes = snapshot.get("nodes")
        if not isinstance(nodes, dict):
            raise HF2LIConfigurationError("HF2LI settings snapshot has no nodes mapping")
        applied: list[str] = []
        for path, item in nodes.items():
            if not isinstance(item, dict):
                continue
            value_type = str(item.get("type"))
            value = item.get("value")
            if value_type == "int":
                self._set_node("setInt", path, value)
            elif value_type == "double":
                self._set_node("setDouble", path, value)
            elif value_type == "string":
                self._set_node("setString", path, value)
            else:
                continue
            applied.append(path)
        self.sync()
        return {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "device_id": self.device_id,
            "applied_node_count": len(applied),
            "applied_nodes": applied,
        }

    def compare_settings_snapshots(
        self,
        before: dict[str, Any],
        after: dict[str, Any],
        *,
        double_tolerance: float = 1e-9,
    ) -> dict[str, Any]:
        """Compare two HF2LI settings snapshots after reload."""

        mismatches: list[dict[str, Any]] = []
        before_nodes = before.get("nodes") or {}
        after_nodes = after.get("nodes") or {}
        for path, before_item in before_nodes.items():
            after_item = after_nodes.get(path)
            if after_item is None:
                mismatches.append({"path": path, "before": before_item, "after": None})
                continue
            b_value = before_item.get("value")
            a_value = after_item.get("value")
            value_type = before_item.get("type")
            if value_type == "double":
                equal = abs(float(b_value) - float(a_value)) <= double_tolerance
            else:
                equal = b_value == a_value
            if not equal:
                mismatches.append({"path": path, "before": b_value, "after": a_value})
        return {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "match": not mismatches,
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
            "before_read_errors": before.get("read_errors", {}),
            "after_read_errors": after.get("read_errors", {}),
        }

    def start_acquisition(
        self,
        *,
        demodulators: Iterable[int],
        fields: Iterable[str] = DEFAULT_SUBSCRIBE_FIELDS,
    ) -> list[str]:
        """Subscribe to real HF2LI demodulator sample nodes."""

        server = self._require_server()
        self._subscribed_paths = []
        for demod in demodulators:
            path = f"/{self.device_id}/demods/{int(demod)}/sample"
            server.subscribe(path)
            self._subscribed_paths.append(path)
            self._log(f"subscribe {path} fields={list(fields)}")
        self.sync()
        return list(self._subscribed_paths)

    def read_acquisition(self, duration_s: float) -> dict[str, Any]:
        """Poll real HF2LI data for the requested duration."""

        server = self._require_server()
        if not self._subscribed_paths:
            raise HF2LIError("HF2LI acquisition has not been started")
        self._log(f"poll duration_s={duration_s}")
        try:
            data = server.poll(float(duration_s), 1000, 0, True)
        except Exception as exc:
            raise HF2LIError(f"HF2LI poll failed: {exc}") from exc
        return {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "duration_s": float(duration_s),
            "subscribed_paths": list(self._subscribed_paths),
            "data": data,
        }

    def stop_acquisition(self) -> None:
        """Unsubscribe all paths used by this service acquisition."""

        if self._server is None:
            return
        for path in self._subscribed_paths:
            try:
                self._server.unsubscribe(path)
                self._log(f"unsubscribe {path}")
            except Exception as exc:
                self._log(f"unsubscribe {path} failed: {exc}")
        self._subscribed_paths = []
        self.sync()

    def acquire_record(
        self,
        *,
        duration_s: float,
        demodulators: Iterable[int],
        fields: Iterable[str] = DEFAULT_SUBSCRIBE_FIELDS,
    ) -> dict[str, Any]:
        """Start, poll, and stop one real HF2LI acquisition record."""

        self.start_acquisition(demodulators=demodulators, fields=fields)
        try:
            record = self.read_acquisition(duration_s)
            record["fields"] = list(fields)
            return record
        finally:
            self.stop_acquisition()

    def acquire_digital_triggered_record(
        self,
        *,
        duration_s: float,
        demodulators: Iterable[int],
        trigger_demodulator: int,
        bits: int,
        bit_mask: int,
        fields: Iterable[str] = DEFAULT_SUBSCRIBE_FIELDS,
    ) -> dict[str, Any]:
        """Capture one DAQ-module shot on a positive edge of a DIO condition.

        A demodulator ``sample.dio`` node carries the global HF2LI DIO word;
        ``trigger_demodulator`` therefore identifies the spare demodulator used
        as the timing monitor, not a detector channel.
        """
        server = self._require_server()
        factory = getattr(server, "dataAcquisitionModule", None)
        if factory is None:
            raise HF2LIError("LabOne dataAcquisitionModule is unavailable")
        module = factory()
        paths = [f"/{self.device_id}/demods/{int(item)}/sample" for item in demodulators]
        try:
            module.set("device", self.device_id)
            module.set("type", 2)  # LabOne digital trigger
            module.set("triggernode", f"/{self.device_id}/demods/{int(trigger_demodulator)}/sample.dio")
            module.set("edge", 1)  # positive condition edge
            module.set("bits", int(bits))
            module.set("bitmask", int(bit_mask))
            module.set("count", 1)
            module.set("endless", 0)  # one Count=1 shot must terminate after its duration
            module.set("duration", float(duration_s))
            module.set("delay", 0.0)
            for path in paths:
                module.subscribe(path)
            module.execute()
            deadline = datetime.now(UTC).timestamp() + float(duration_s) + 15.0
            while not bool(module.finished()):
                if datetime.now(UTC).timestamp() > deadline:
                    raise HF2LIError(
                        "HF2LI DAQ did not complete after the digital trigger "
                        f"(Demod {trigger_demodulator} DIO, bits={bits}, bit_mask={bit_mask}). "
                        "The configured DIO bit did not show the expected low-to-high transition."
                    )
                import time
                time.sleep(0.01)
            data = module.read(True)
            return {
                "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "duration_s": float(duration_s),
                "fields": list(fields),
                "data": data,
                "digital_trigger": {"demodulator": int(trigger_demodulator), "bits": int(bits), "bit_mask": int(bit_mask)},
            }
        finally:
            try:
                module.finish()
                module.clear()
            except Exception:
                pass

    def acquire_continuous_daq_record(
        self,
        *,
        duration_s: float,
        demodulators: Iterable[int],
        fields: Iterable[str] = DEFAULT_SUBSCRIBE_FIELDS,
        grid_cols: int | None = None,
        after_execute: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Record one continuous interval using LabOne's DAQ Module."""
        server = self._require_server()
        factory = getattr(server, "dataAcquisitionModule", None)
        if factory is None:
            raise HF2LIError("LabOne dataAcquisitionModule is unavailable")
        module = factory()
        # DAQ modules require concrete streaming nodes.  Unlike ``poll()``,
        # subscribing to the aggregate ``.../sample`` node can return no data
        # on an HF2LI even though the demodulators are visibly producing data.
        # X/Y are used to derive R in the export step; DIO is needed only for
        # the spare timing demodulator, but including it on every requested
        # demodulator is harmless and makes the record self-describing.
        paths: list[str] = []
        requested_field_list = [str(field).lower() for field in fields]
        requested_fields = set(requested_field_list)
        for item in demodulators:
            base = f"/{self.device_id}/demods/{int(item)}/sample"
            if "r" in requested_fields or "x" in requested_fields:
                paths.append(f"{base}.x")
            if "r" in requested_fields or "y" in requested_fields:
                paths.append(f"{base}.y")
            if "dio" in requested_fields:
                paths.append(f"{base}.dio")
        try:
            module.set("device", self.device_id)
            module.set("type", 0)  # LabOne DAQ continuous acquisition
            module.set("count", 1)
            module.set("endless", 0)
            module.set("duration", float(duration_s))
            if grid_cols is not None:
                if int(grid_cols) < 2:
                    raise HF2LIError("HF2LI DAQ grid_cols must be at least 2")
                # Exact mode preserves the device timestamps and makes the
                # grid long enough to contain the complete requested sweep.
                module.set("grid/mode", 4)
                module.set("grid/cols", int(grid_cols))
            for path in paths:
                module.subscribe(path)
            module.execute()
            if after_execute is not None:
                after_execute()
            # In continuous mode LabOne produces back-to-back bursts. The
            # caller's requested interval is therefore the stop condition.
            import time
            time.sleep(float(duration_s))
            # Read while the module is still active. Some HF2/LabOne builds
            # discard a continuous burst when ``finish()`` is called first.
            data = module.read(True)
            module.finish()
            # Exact grids are delivered by some HF2/LabOne versions only as
            # the module is finished. Preserve both the live data already
            # read and that final buffered grid.
            data = _merge_module_data(data, module.read(True))
            return {
                "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "duration_s": float(duration_s),
                "fields": requested_field_list,
                "data": data,
                "daq_mode": "continuous",
                "subscribed_paths": paths,
                "grid_cols": grid_cols,
            }
        finally:
            try:
                module.finish()
                module.clear()
            except Exception:
                pass

    def save_record(
        self,
        record: dict[str, Any],
        *,
        raw_csv_path: str | Path,
        summary_csv_path: str | Path,
    ) -> dict[str, Any]:
        """Save real HF2LI poll data and a compact per-node CSV summary."""

        raw_rows: list[dict[str, Any]] = []
        data = record.get("data") or {}
        if not isinstance(data, dict):
            raise HF2LIError("HF2LI poll returned an unsupported data structure")
        requested_fields = record.get("fields") or list(DEFAULT_SUBSCRIBE_FIELDS)
        for path, payload in data.items():
            path_text = str(path)
            if path_text.endswith("/sample"):
                raw_rows.extend(_normalized_sample_rows_from_sample(path_text, payload, requested_fields))
            else:
                raw_rows.extend(_normalized_sample_rows(path_text, payload))
        if not raw_rows:
            raise HF2LIError("HF2LI poll returned no sample rows")

        raw_path = Path(raw_csv_path)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        with raw_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["path", "timestamp", "sample_index", "value"])
            writer.writeheader()
            writer.writerows(raw_rows)

        summary_rows = _summary_rows(raw_rows)
        summary_path = Path(summary_csv_path)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with summary_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "path",
                    "sample_count",
                    "mean",
                    "rms",
                    "minimum",
                    "maximum",
                    "first_timestamp",
                    "last_timestamp",
                ],
            )
            writer.writeheader()
            writer.writerows(summary_rows)
        return {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "raw_csv_path": str(raw_path),
            "summary_csv_path": str(summary_path),
            "path_count": len(summary_rows),
            "sample_count": len(raw_rows),
        }

    def sync(self) -> None:
        """Flush LabOne set commands to the device."""

        server = self._require_server()
        sync = getattr(server, "sync", None)
        if sync is not None:
            sync()

    def get_clockbase(self) -> int:
        """Return the HF2LI device-timestamp clock rate in ticks per second."""

        server = self._require_server()
        try:
            return int(server.getInt(f"/{self.device_id}/clockbase"))
        except Exception as exc:
            raise HF2LIError(f"Unable to read HF2LI timestamp clockbase: {exc}") from exc

    def get_oscillator_frequency(self, index: int) -> float:
        """Read the actual frequency of an HF2LI oscillator/reference."""

        server = self._require_server()
        try:
            return float(server.getDouble(f"/{self.device_id}/oscs/{int(index)}/freq"))
        except Exception as exc:
            raise HF2LIError(
                f"Unable to read HF2LI oscillator {int(index) + 1} frequency: {exc}"
            ) from exc

    def close(self) -> None:
        """Close the LabOne session if the API exposes disconnect."""

        self.stop_acquisition()
        if self._server is not None:
            disconnect = getattr(self._server, "disconnect", None)
            if disconnect is not None:
                try:
                    disconnect()
                except Exception as exc:
                    self._log(f"disconnect failed: {exc}")
            self._server = None

    def _configured_device_id(self) -> str | None:
        value = self.device_config.get("device_id") or self.device_config.get("serial_number")
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return text if text.lower().startswith("dev") else f"dev{text}"

    def _connect_device_if_supported(self, device_id: str) -> None:
        server = self._require_server()
        connect_device = getattr(server, "connectDevice", None)
        if connect_device is None:
            return
        interface = str(self.device_config.get("interface") or DEFAULT_DEVICE_INTERFACE)
        try:
            connect_device(device_id, interface)
            self._log(f"connectDevice device={device_id} interface={interface}")
        except Exception as exc:
            self._log(f"connectDevice device={device_id} interface={interface} failed: {exc}")

    def _device_has_nodes(self, device_id: str) -> bool:
        server = self._require_server()
        list_nodes = getattr(server, "listNodes", None)
        if list_nodes is None:
            return False
        try:
            nodes = list_nodes(f"/{device_id}", 0)
        except Exception as exc:
            self._log(f"listNodes /{device_id} failed: {exc}")
            return False
        return bool(nodes)

    def _snapshot_nodes(self, preset: HF2LIPreset | None) -> Iterable[tuple[str, str]]:
        device = self.device_id
        input_indices = {0, 1}
        demod_indices = {0, 3}
        pll_indices = {0}
        oscillator_indices = {0}
        if preset is not None:
            for settings in (preset.settings.get("signal_inputs") or {}).values():
                if isinstance(settings, dict):
                    input_indices.add(int(settings.get("index", 0)))
            for settings in preset.settings.get("demodulators") or []:
                if isinstance(settings, dict) and "index" in settings:
                    demod_indices.add(int(settings["index"]))
                    oscillator_indices.add(int(settings.get("oscselect", 0)))
            pll = preset.settings.get("pll") or {}
            if isinstance(pll, dict):
                pll_indices.add(int(pll.get("index", 0)))
            for settings in preset.settings.get("oscillators") or []:
                if isinstance(settings, dict) and "index" in settings:
                    oscillator_indices.add(int(settings["index"]))
        for index in sorted(input_indices):
            base = f"/{device}/sigins/{index}"
            yield f"{base}/ac", "int"
            yield f"{base}/imp50", "int"
            yield f"{base}/diff", "int"
            yield f"{base}/range", "double"
        for index in sorted(pll_indices):
            base = f"/{device}/plls/{index}"
            yield f"{base}/enable", "int"
            yield f"{base}/adcselect", "int"
            yield f"{base}/freqcenter", "double"
            yield f"{base}/harmonic", "int"
            yield f"{base}/order", "int"
            yield f"{base}/adcthreshold", "int"
        for index in sorted(oscillator_indices):
            base = f"/{device}/oscs/{index}"
            yield f"{base}/freq", "double"
        for index in sorted(demod_indices):
            base = f"/{device}/demods/{index}"
            yield f"{base}/enable", "int"
            yield f"{base}/adcselect", "int"
            yield f"{base}/oscselect", "int"
            yield f"{base}/harmonic", "int"
            yield f"{base}/order", "int"
            yield f"{base}/timeconstant", "double"
            yield f"{base}/rate", "double"
            yield f"{base}/trigger", "int"

    def _set_node(self, method_name: str, path: str, value: Any) -> None:
        server = self._require_server()
        method = getattr(server, method_name)
        try:
            if method_name == "setDouble":
                method(path, float(value))
            elif method_name == "setInt":
                method(path, int(value))
            else:
                method(path, value)
        except Exception as exc:
            raise HF2LIError(f"{method_name} {path}={value!r} failed: {exc}") from exc
        self._log(f"{method_name} {path} {value}")

    def _get_node(self, value_type: str, path: str) -> Any:
        server = self._require_server()
        if value_type == "int":
            return int(server.getInt(path))
        if value_type == "double":
            return float(server.getDouble(path))
        if value_type == "string":
            return str(server.getString(path))
        raise HF2LIConfigurationError(f"unsupported node type {value_type!r}")

    def _require_server(self):
        if self._server is None:
            raise HF2LIConnectionError("LabOne server is not connected")
        return self._server

    def _load_labone_module(self):
        if self._zi_module is not None:
            return self._zi_module
        _add_labone_package_paths(self.device_config)
        try:
            import zhinst.ziPython as zi
        except ImportError as exc:
            raise HF2LIConfigurationError(
                "zhinst.ziPython is not importable; install LabOne Python API or set "
                "ZHINST_PYTHON_PATH to the package directory"
            ) from exc
        self._zi_module = zi
        return zi

    def _write_json(self, path: str | Path, data: Any) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target

    def _log(self, message: str) -> None:
        if self.command_log is None:
            return
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        try:
            self.command_log.write(f"{timestamp} hf2li {message}\n")
            self.command_log.flush()
        except ValueError:
            self.command_log = None


def _add_labone_package_paths(device_config: dict[str, Any]) -> None:
    configured = device_config.get("python_package_paths") or []
    if isinstance(configured, str):
        configured = [configured]
    env_paths = []
    for key in ("ZHINST_PYTHON_PATH", "LABONE_PYTHON_PATH"):
        value = os.environ.get(key)
        if value:
            env_paths.extend(value.split(os.pathsep))
    for raw_path in [*env_paths, *configured, *DEFAULT_LABONE_PACKAGE_PATHS]:
        if not raw_path:
            continue
        path = str(Path(str(raw_path)).expanduser())
        if path not in sys.path:
            sys.path.insert(0, path)


def _merge_module_data(first: Any, second: Any) -> dict[str, Any]:
    """Combine successive DAQ Module reads without losing a final burst."""

    merged: dict[str, Any] = {}
    for source in (first, second):
        if not isinstance(source, dict):
            continue
        for path, payload in source.items():
            if path not in merged:
                merged[path] = payload
                continue
            prior = merged[path] if isinstance(merged[path], list) else [merged[path]]
            current = payload if isinstance(payload, list) else [payload]
            merged[path] = prior + current
    return merged


def _extract_device_ids(value: Any) -> set[str]:
    text_items: list[str] = []
    if isinstance(value, bytes):
        text_items.append(value.decode("ascii", errors="replace"))
    elif isinstance(value, str):
        text_items.append(value)
    elif isinstance(value, Iterable):
        for item in value:
            text_items.extend(_extract_device_ids(item))
    else:
        text_items.append(str(value))
    devices: set[str] = set()
    for item in text_items:
        for match in re.findall(r"\bdev\d+\b", item, flags=re.IGNORECASE):
            devices.add(match.lower())
    return devices


def _default_input_index(label: str) -> int:
    normalized = label.lower().replace("_", "")
    if normalized in {"ch2", "channel2", "input2", "sigin2"}:
        return 1
    return 0


def _bool_int(value: Any) -> int:
    return 1 if bool(value) else 0


def _as_sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    try:
        return list(value)
    except TypeError:
        return [value]


def _normalized_sample_rows(path: str, payload: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    chunks = payload if isinstance(payload, list) else [payload]
    sample_index = 0
    field_name = path.rsplit(".", 1)[-1]
    for chunk in chunks:
        if isinstance(chunk, dict):
            values = (
                chunk.get("value")
                if "value" in chunk
                else chunk.get(field_name, chunk.get(field_name.lower()))
            )
            timestamps = chunk.get("timestamp")
        else:
            values = chunk
            timestamps = None
        values_seq = _as_sequence(values)
        timestamps_seq = _as_sequence(timestamps)
        for index, value in enumerate(values_seq):
            timestamp = timestamps_seq[index] if index < len(timestamps_seq) else ""
            rows.append(
                {
                    "path": path,
                    "timestamp": _scalar(timestamp),
                    "sample_index": sample_index,
                    "value": float(_scalar(value)),
                }
            )
            sample_index += 1
    return rows


def _normalized_sample_rows_from_sample(
    path: str,
    payload: Any,
    requested_fields: Iterable[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    chunks = payload if isinstance(payload, list) else [payload]
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        timestamps = _as_sequence(chunk.get("timestamp"))
        for field in requested_fields:
            if field not in chunk:
                continue
            values = _as_sequence(chunk.get(field))
            for index, value in enumerate(values):
                timestamp = timestamps[index] if index < len(timestamps) else ""
                rows.append(
                    {
                        "path": f"{path}.{field}",
                        "timestamp": _scalar(timestamp),
                        "sample_index": index,
                        "value": float(_scalar(value)),
                    }
                )
    return rows


def _scalar(value: Any) -> Any:
    item = value
    if hasattr(item, "item"):
        return item.item()
    return item


def _summary_rows(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in raw_rows:
        grouped.setdefault(str(row["path"]), []).append(row)
    summaries: list[dict[str, Any]] = []
    for path, rows in sorted(grouped.items()):
        values = [float(row["value"]) for row in rows]
        count = len(values)
        mean = sum(values) / count
        rms = math.sqrt(sum(value * value for value in values) / count)
        summaries.append(
            {
                "path": path,
                "sample_count": count,
                "mean": mean,
                "rms": rms,
                "minimum": min(values),
                "maximum": max(values),
                "first_timestamp": rows[0]["timestamp"],
                "last_timestamp": rows[-1]["timestamp"],
            }
        )
    return summaries
