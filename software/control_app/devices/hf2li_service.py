"""Real Zurich Instruments HF2LI LabOne service adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from numbers import Integral
from pathlib import Path
from typing import Any, Callable, Iterable, TextIO
import csv
import json
import math
import os
import re
import sys

import yaml

from control_app.config_loader import load_hardware_config
from control_app.paths import RECIPE_ROOT, resolve_compat_path


DEFAULT_LABONE_PACKAGE_PATHS = (
    r"C:\Users\Chris\AppData\Local\Control_System\runtimes\zhinst_26_4_py312",
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
    """Named HF2LI preset loaded from instrument/recipes/hf2li_presets.yaml."""

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
        presets_path: str | Path = RECIPE_ROOT / "hf2li_presets.yaml",
    ) -> HF2LIPreset:
        """Load one named HF2LI preset from YAML."""

        path = Path(presets_path)
        if not path.is_absolute():
            path = resolve_compat_path(path)
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
        """Configure detector demodulators, with optional sinc and phase settings.

        ``sinc`` enables the additional filter; ``phaseshift`` is in degrees.
        Omitting either optional field leaves that device setting untouched.
        """

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
                ("sinc", "setInt", _bool_int(settings["sinc"]) if settings.get("sinc") is not None else None),
                ("phaseshift", "setDouble", settings.get("phaseshift")),
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

    def create_daq_module(self):
        """Create a real LabOne Data Acquisition Module without starting it."""
        factory = getattr(self._require_server(), "dataAcquisitionModule", None)
        if factory is None:
            raise HF2LIError("The installed LabOne API has no Data Acquisition Module")
        return factory()

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

        from control_app.measurement_host.ownership import check_bound_hardware_owner
        check_bound_hardware_owner(self)
        if self._server is None:
            return
        errors, remaining = [], []
        for path in self._subscribed_paths:
            try:
                self._server.unsubscribe(path)
                self._log(f"unsubscribe {path}")
            except Exception as exc:
                errors.append(f"unsubscribe {path} failed: {exc}")
                remaining.append(path)
        self._subscribed_paths = remaining
        try:
            self.sync()
        except Exception as exc:
            errors.append(f"final synchronization failed: {exc}")
        if errors:
            raise HF2LIConnectionError("; ".join(errors))

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
        subscribed_paths = {
            str(item).lower() for item in (record.get("subscribed_paths") or [])
        }
        for path, payload in data.items():
            path_text = str(path)
            if subscribed_paths and path_text.lower() not in subscribed_paths:
                # DAQ Module reads also return module settings and metadata
                # such as /device="dev18500". They are provenance, not sample
                # streams, and must not be coerced to numeric CSV rows.
                continue
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

    def read_acquisition_health(
        self, *, reference_pll: int = 0, input_indices: Iterable[int] = (0, 1)
    ) -> dict[str, Any]:
        """Read live HF2 health without changing settings or acquisition streams.

        Indices are zero-based. ``reference_locked`` is the selected enabled
        reference PLL's lock; a disabled or unreadable enable state gives None.
        ``clock_locked`` combines the internal clock-generation PLL and digital
        clock manager. It does not independently verify an external 10 MHz
        source: ``external_clock_selected`` reports only the configured source.
        ``overload`` covers ADC clipping on the selected signal inputs only.

        Reads are sequential, not an atomic or per-sample hardware snapshot.
        ``timestamp_utc`` is the host observation time. Missing, unreadable or
        nonbinary node values remain unknown (None), with errors retained by
        full node path. There is no cached all-clear fallback. Connection and
        ownership preconditions raise normally; individual SDK read failures
        are retained in ``read_errors``. No connect, set, sync, poll or subscribe
        is performed. Node meanings and polarity follow the HF2 node reference:
        https://docs.zhinst.com/hf2_user_manual/nodedoc.html
        """
        from control_app.measurement_host.ownership import OwnershipError

        def valid_index(value):
            return isinstance(value, Integral) and not isinstance(value, bool) and value in (0, 1)

        indices = tuple(input_indices)
        if not valid_index(reference_pll):
            raise ValueError("reference_pll must be the zero-based HF2 PLL index 0 or 1")
        if not indices or any(not valid_index(index) for index in indices) or len(set(indices)) != len(indices):
            raise ValueError("input_indices must contain distinct zero-based HF2 signal input indices 0 or 1")
        reference_pll = int(reference_pll)
        indices = tuple(int(index) for index in indices)
        self._require_server()
        base = f"/{self.device_id}"
        timestamp_utc = datetime.now(UTC).isoformat()
        nodes: dict[str, dict[str, Any]] = {}
        read_errors: dict[str, str] = {}

        def read_flag(suffix, *, inverted=False):
            # Recheck ownership before every transport call. Never turn an
            # expired operation token into an ordinary unavailable health node.
            server = self._require_server()
            path = base + suffix
            try:
                raw = server.getInt(path)
                if not isinstance(raw, Integral) or raw not in (0, 1):
                    raise ValueError(f"Expected binary integer 0 or 1, received {raw!r}")
                raw = int(raw)
                nodes[path] = {"type": "int", "value": raw}
                return (raw == 0) if inverted else (raw == 1)
            except OwnershipError:
                raise
            except Exception as exc:
                read_errors[path] = f"{type(exc).__name__}: {exc}"
                return None

        def all_locked(states):
            if any(state is False for state in states):
                return False
            return True if all(state is True for state in states) else None

        enabled = read_flag(f"/plls/{reference_pll}/enable")
        reference_flag = read_flag(f"/plls/{reference_pll}/locked")
        clock_pll = read_flag("/status/flags/plllock", inverted=True)
        clock_dcm = read_flag("/status/flags/dcmlock", inverted=True)
        external_selected = read_flag("/system/extclk")
        inputs = {}
        for index in indices:
            clipped = read_flag(f"/status/flags/adcclip/{index}")
            inputs[str(index)] = {"input_index": index, "adc_clipped": clipped, "overload": clipped}
        clipping = [state["adc_clipped"] for state in inputs.values()]
        overload = True if any(state is True for state in clipping) else (
            False if all(state is False for state in clipping) else None
        )
        self._require_server()
        return {
            "schema_version": "hf2li-acquisition-health/1",
            "timestamp_utc": timestamp_utc,
            "device_id": self.device_id,
            "reference_locked": reference_flag if enabled is True else None,
            "clock_locked": all_locked((clock_pll, clock_dcm)),
            "clock_lock_basis": "internal_clock_generation_pll_and_digital_clock_manager",
            "external_clock_selected": external_selected,
            "external_reference_locked": None,
            "overload": overload,
            "overload_scope": "selected_signal_input_adc_clipping",
            "inputs": inputs,
            "reference": {"pll_index": reference_pll, "enabled": enabled, "locked": reference_flag},
            "clock": {"pll_locked": clock_pll, "dcm_locked": clock_dcm},
            "nodes": nodes,
            "read_errors": read_errors,
        }

    def discover_phase_scan_capabilities(self) -> dict[str, Any]:
        return self._discover_phase_scan_capabilities((0,))

    def discover_dual_phase_scan_capabilities(self) -> dict[str, Any]:
        """Probe both detector demods with all three streams enabled, restoring nodes."""
        return self._discover_phase_scan_capabilities((0, 3))

    def discover_slow_scan_capabilities(self, *, dual=False, filter_requests=None) -> dict[str, Any]:
        """Verify selected filters and available rates without a filter sweep.

        Auto retains each detector's current filter. Explicit requests are
        checked by the device. The established Phase Scan enumeration remains
        separate because its menus need the complete filter choices.
        """
        return self._discover_phase_scan_capabilities((0, 3) if dual else (0,),
                                                     filter_requests=filter_requests or {})

    def _discover_phase_scan_capabilities(self, detector_indices: tuple[int, ...], *,
                                          filter_requests=None) -> dict[str, Any]:
        """Probe accepted demodulator settings, then restore the prior settings.

        This is configuration-only: no poll, DAQ execution, signal output or
        external instrument command. Only values actually returned by this
        HF2 are offered to the phase-scan dropdowns. The bounded requests are
        candidates from the HF2 manual, not a universal supported-value list.
        The actual detector streams and DIO carrier are part of each profile.
        """
        base = f"/{self.device_id}/demods"
        paths = [(f"{base}/{i}/{node}", kind) for i in range(6)
                 for node, kind in (("enable", "int"), ("order", "int"),
                                    ("timeconstant", "double"), ("rate", "double"))]
        before = {path: {"type": kind, "value": self._get_node(kind, path)} for path, kind in paths}
        observations = []
        expected_streams = tuple(sorted((*detector_indices, 2)))
        profiles = {}
        def set_read(node, value, kind="double"):
            self._set_node("setInt" if kind == "int" else "setDouble", node, value)
            self.sync()
            actual = self._get_node(kind, node)
            if not isinstance(actual, (int, float)) or not math.isfinite(actual):
                raise HF2LIConfigurationError(f"Nonfinite HF2LI capability readback at {node}")
            observations.append({"node": node, "requested": value, "actual": actual})
            return actual
        def unique(values, candidate):
            return not any(math.isclose(candidate, value, rel_tol=1e-9, abs_tol=1e-15) for value in values)
        discovery_error = None
        try:
            for i in range(6):
                set_read(f"{base}/{i}/enable", int(i in expected_streams), "int")
            # Published max readout for 2–3 active HF2 demodulators: ~230 kSa/s.
            # The actual oscillator divisor gives 230263... on dev18500.
            timing = set_read(f"{base}/2/rate", 230000.)
            if not 16000 <= timing <= 231000:
                raise HF2LIConfigurationError("HF2LI cannot provide the documented timing rate with the enabled streams")
            for demod in detector_indices:
                orders, constants, rates = [], {}, set()
                prefix = f"{base}/{demod}"
                top = set_read(f"{prefix}/rate", 230000.)
                if not 0 < top <= 231000:
                    raise HF2LIConfigurationError(f"HF2LI demod {demod} exceeds the documented active-stream readout rate")
                for exponent in range(15):
                    try:
                        actual = set_read(f"{prefix}/rate", top / 2**exponent)
                    except Exception as exc:
                        observations.append({"node": f"{prefix}/rate", "requested": top / 2**exponent,
                                             "rejected": str(exc)})
                        continue
                    if 0 < actual <= 231000 and unique(rates, actual):
                        repeated = set_read(f"{prefix}/rate", actual)
                        if math.isclose(actual, repeated, rel_tol=1e-9, abs_tol=1e-12):
                            rates.add(float(actual))
                # Documented orders 1–8, TC >= 0.8 us; only idempotent actual
                # readbacks enter each detector's supported-value dropdowns.
                selected_filter = None if filter_requests is None else filter_requests.get(demod, {})
                if selected_filter is None:
                    candidate_orders = range(1, 9)
                    candidate_constants = tuple(value * 1e-6 for value in (.8, 1., 2., 5., 8., 10., 20., 50., 100., 200., 500., 1000.))
                else:
                    order = selected_filter.get("order")
                    tau = selected_filter.get("timeconstant_s")
                    order = before[f"{prefix}/order"]["value"] if order is None else order
                    tau = before[f"{prefix}/timeconstant"]["value"] if tau is None else tau
                    if type(order) is not int or not 1 <= order <= 8 or not isinstance(tau, (int, float)) or not math.isfinite(tau) or tau <= 0:
                        raise HF2LIConfigurationError("Invalid requested Slow Scan filter")
                    candidate_orders, candidate_constants = (order,), (tau,)
                for order in candidate_orders:
                    try:
                        accepted_order = set_read(f"{prefix}/order", order, "int")
                        if accepted_order != order:
                            continue
                        values = []
                        for requested_tau in candidate_constants:
                            try:
                                actual = set_read(f"{prefix}/timeconstant", requested_tau)
                                if actual > 0 and unique(values, actual):
                                    repeated = set_read(f"{prefix}/timeconstant", actual)
                                    if math.isclose(actual, repeated, rel_tol=1e-9, abs_tol=1e-15):
                                        values.append(float(actual))
                            except Exception as exc:
                                observations.append({"demodulator": demod, "order": order,
                                    "requested_timeconstant_s": requested_tau, "rejected": str(exc)})
                        if values:
                            orders.append(order)
                            constants[order] = tuple(sorted(values))
                    except Exception as exc:
                        observations.append({"demodulator": demod, "order": order, "rejected": str(exc)})
                if not rates or not orders:
                    raise HF2LIConfigurationError(f"No stable HF2LI demod {demod} phase-scan capabilities were returned")
                profiles[demod] = {"orders": tuple(orders), "timeconstants_by_order": constants,
                                   "rates_sps": tuple(sorted(rates))}
            # Recheck the streams together at their highest accepted rates.
            for demod, profile in profiles.items():
                set_read(f"{base}/{demod}/rate", max(profile["rates_sps"]))
            timing = set_read(f"{base}/2/rate", timing)
            for demod, profile in profiles.items():
                if self._get_node("double", f"{base}/{demod}/rate") != max(profile["rates_sps"]):
                    raise HF2LIConfigurationError(f"HF2LI demod {demod} rate changed with all requested streams enabled")
            if timing + sum(max(p["rates_sps"]) for p in profiles.values()) > 700000:
                raise HF2LIConfigurationError("HF2LI active streams exceed the documented cumulative 700 kSa/s readout capacity")
            enabled = tuple(i for i in range(6) if self._get_node("int", f"{base}/{i}/enable"))
            if enabled != expected_streams:
                raise HF2LIConfigurationError("HF2LI enabled-stream readbacks changed during discovery")
            common = {"device_id": self.device_id,
                    "timing_rate_sps": timing, "enabled_streams": enabled, "verified": True,
                    "source": f"{self.device_id} configuration readbacks {datetime.now(UTC).isoformat()}",
                    "readback_records": tuple(observations)}
            if detector_indices == (0,):
                return {**common, **profiles[0]}
            return {**common, "sample": {**common, **profiles[0]},
                    "reference": {**common, **profiles[3]}}
        except Exception as exc:
            discovery_error = exc
            raise
        finally:
            failures = []
            # Disable first; restore filters/rates before reinstating enables.
            for i in range(6):
                try:
                    self._set_node("setInt", f"{base}/{i}/enable", 0)
                except Exception as exc:
                    failures.append(str(exc))
            for enable_pass in (False, True):
                for path, item in before.items():
                    if path.endswith("/enable") != enable_pass:
                        continue
                    try:
                        self._set_node("setInt" if item["type"] == "int" else "setDouble", path, item["value"])
                    except Exception as exc:
                        failures.append(f"{path}: {exc}")
            try:
                self.sync()
            except Exception as exc:
                failures.append(f"restoration sync: {exc}")
            for path, item in before.items():
                try:
                    actual = self._get_node(item["type"], path)
                    if not math.isclose(actual, item["value"], rel_tol=1e-9, abs_tol=1e-12):
                        failures.append(f"{path}: restoration readback differs")
                except Exception as exc:
                    failures.append(f"{path}: {exc}")
            if failures:
                raise HF2LIConfigurationError("HF2LI capability discovery restoration failed: " + "; ".join(failures)) from discovery_error

    def close(self) -> None:
        """Close the LabOne session if the API exposes disconnect."""

        from control_app.measurement_host.ownership import check_bound_hardware_owner
        check_bound_hardware_owner(self)
        errors = []
        try:
            self.stop_acquisition()
        except Exception as exc:
            errors.append(str(exc))
        if self._server is not None:
            disconnect = getattr(self._server, "disconnect", None)
            if disconnect is not None:
                try:
                    disconnect()
                    self._server = None
                except Exception as exc:
                    errors.append(f"disconnect failed: {exc}")
            else:
                self._server = None
        if errors:
            raise HF2LIConnectionError("; ".join(errors))

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
        optional_demod_nodes: dict[int, set[str]] = {}
        if preset is not None:
            for settings in (preset.settings.get("signal_inputs") or {}).values():
                if isinstance(settings, dict):
                    input_indices.add(int(settings.get("index", 0)))
            for settings in preset.settings.get("demodulators") or []:
                if isinstance(settings, dict) and "index" in settings:
                    demod_indices.add(int(settings["index"]))
                    oscillator_indices.add(int(settings.get("oscselect", 0)))
                    optional_demod_nodes.setdefault(int(settings["index"]), set()).update(
                        node for node in ("sinc", "phaseshift") if node in settings
                    )
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
            # These newer settings are opt-in per demodulator so legacy
            # snapshots retain exactly their established node footprint.
            for node, value_type in (("sinc", "int"), ("phaseshift", "double")):
                if node in optional_demod_nodes.get(index, ()):
                    yield f"{base}/{node}", value_type

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
        from control_app.measurement_host.ownership import check_bound_hardware_owner
        check_bound_hardware_owner(self)
        if self._server is None:
            raise HF2LIConnectionError("LabOne server is not connected")
        return self._server

    def _load_labone_module(self):
        from control_app.measurement_host.ownership import require_hardware_owner
        require_hardware_owner(self)
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


def _flatten_sequence(value: Any) -> list[Any]:
    """Flatten scalar, vector, or DAQ-module grid arrays in row-major order."""

    if value is None:
        return []
    reshape = getattr(value, "reshape", None)
    tolist = getattr(value, "tolist", None)
    if callable(reshape) and callable(tolist):
        try:
            return list(reshape(-1).tolist())
        except (TypeError, ValueError):
            pass
    result: list[Any] = []
    for item in _as_sequence(value):
        if isinstance(item, (str, bytes)):
            result.append(item)
        elif hasattr(item, "__iter__"):
            result.extend(_flatten_sequence(item))
        else:
            result.append(item)
    return result
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
        values_seq = _flatten_sequence(values)
        timestamps_seq = _flatten_sequence(timestamps)
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
        timestamps = _flatten_sequence(chunk.get("timestamp"))
        for field in requested_fields:
            if field not in chunk:
                continue
            values = _flatten_sequence(chunk.get(field))
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
