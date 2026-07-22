"""Minimal real PicoScope 5000A/5000D block-capture service."""

from __future__ import annotations

from ctypes import (
    POINTER,
    byref,
    c_float,
    c_int16,
    c_int32,
    c_uint32,
    cdll,
    create_string_buffer,
)
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, TextIO
import csv
import os
import sys
import time

from control_app.config_loader import REPO_ROOT, load_hardware_config


PICO_OK = 0
PICO_STATUS_NAMES = {
    0: "PICO_OK",
    3: "PICO_NOT_FOUND",
    12: "PICO_INVALID_HANDLE",
    13: "PICO_INVALID_PARAMETER",
    15: "PICO_INVALID_VOLTAGE_RANGE",
    17: "PICO_INVALID_TRIGGER_CHANNEL",
    282: "PICO_POWER_SUPPLY_NOT_CONNECTED",
    286: "PICO_USB3_0_DEVICE_NON_USB3_0_PORT",
    288: "PICO_INVALID_DEVICE_RESOLUTION",
}
CHANNELS = {"A": 0, "B": 1}
COUPLING = {"AC": 0, "DC": 1}
TRIGGER_SOURCES = {"A": 0, "B": 1, "EXT": 4}
RANGES = {
    "10MV": 0,
    "20MV": 1,
    "50MV": 2,
    "100MV": 3,
    "200MV": 4,
    "500MV": 5,
    "1V": 6,
    "2V": 7,
    "5V": 8,
    "10V": 9,
    "20V": 10,
    "50V": 11,
}
RESOLUTIONS = {"8BIT": 0, "12BIT": 1, "14BIT": 2, "15BIT": 3, "16BIT": 4}


class PicoScopeError(RuntimeError):
    """Base error for PicoScope service failures."""


class PicoScopeConfigurationError(PicoScopeError):
    """Raised when required PicoScope config is absent."""


class PicoScopeService:
    """Real block capture adapter using the PicoSDK ps5000a C API."""

    def __init__(
        self,
        device_config: dict[str, Any],
        capture_settings: dict[str, Any],
        *,
        command_log: TextIO | None = None,
    ) -> None:
        self.device_config = device_config
        self.capture_settings = capture_settings
        self.command_log = command_log
        self._driver = None
        self._handle = c_int16()
        self._is_open = False

    @classmethod
    def from_config(
        cls,
        *,
        config_path: str | Path | None = None,
        command_log: TextIO | None = None,
    ) -> "PicoScopeService":
        """Create a PicoScope service from hardware_configuration.yaml."""

        config, _, _ = load_hardware_config(config_path)
        devices = config.get("devices") or {}
        device_config = devices.get("picoscope")
        if not isinstance(device_config, dict):
            raise PicoScopeConfigurationError("picoscope missing from hardware configuration")
        capture_settings = (
            device_config.get("capture_settings")
            or config.get("picoscope_settings")
            or config.get("acquisition", {}).get("picoscope")
        )
        if not isinstance(capture_settings, dict):
            raise PicoScopeConfigurationError(
                "PicoScope capture settings are missing; recipe-driven workflows "
                "must pass capture settings from the selected recipe"
            )
        return cls(device_config, capture_settings, command_log=command_log)

    def open_unit(self) -> None:
        """Open the configured PicoScope unit."""

        self._driver = self._load_driver()
        serial = self.device_config.get("sdk_serial_number") or self.device_config.get(
            "serial_number"
        )
        serial_buffer = create_string_buffer(str(serial).encode("ascii")) if serial else None
        resolution = str(self.capture_settings.get("resolution", "8BIT")).upper()
        resolution_value = RESOLUTIONS.get(resolution)
        if resolution_value is None:
            raise PicoScopeConfigurationError(f"unsupported PicoScope resolution {resolution!r}")
        status = self._driver.ps5000aOpenUnit(
            byref(self._handle),
            serial_buffer,
            resolution_value,
        )
        self._check(status, "ps5000aOpenUnit")
        self._is_open = True

    def set_device_resolution(self, resolution: str) -> None:
        """Set PicoScope hardware resolution."""

        self._require_open()
        value = RESOLUTIONS.get(resolution.upper())
        if value is None:
            raise PicoScopeConfigurationError(f"unsupported PicoScope resolution {resolution!r}")
        status = self._driver.ps5000aSetDeviceResolution(self._handle, value)
        self._check(status, "ps5000aSetDeviceResolution")

    def configure_channels(self) -> None:
        """Configure CH A and CH B coupling/ranges from the config."""

        self._require_open()
        channels = self.capture_settings.get("channels")
        if not isinstance(channels, dict):
            raise PicoScopeConfigurationError("PicoScope channels settings missing")
        for channel_name in ("A", "B"):
            settings = channels.get(channel_name) or channels.get(channel_name.lower())
            if not isinstance(settings, dict):
                raise PicoScopeConfigurationError(f"PicoScope channel {channel_name} settings missing")
            enabled = 1 if settings.get("enabled", True) else 0
            coupling = COUPLING.get(str(settings.get("coupling", "DC")).upper())
            voltage_range = RANGES.get(str(settings.get("range", "5V")).upper())
            if coupling is None or voltage_range is None:
                raise PicoScopeConfigurationError(
                    f"PicoScope channel {channel_name} coupling/range unsupported"
                )
            status = self._driver.ps5000aSetChannel(
                self._handle,
                CHANNELS[channel_name],
                enabled,
                coupling,
                voltage_range,
                c_float_or_zero(settings.get("analog_offset_v", 0.0)),
            )
            self._check(status, f"ps5000aSetChannel {channel_name}")

    def set_external_trigger(self) -> None:
        """Configure a simple external trigger from the config."""

        self._require_open()
        trigger = self.capture_settings.get("external_trigger")
        if not isinstance(trigger, dict):
            raise PicoScopeConfigurationError("PicoScope external_trigger settings missing")
        enabled = 1
        source_name = str(trigger.get("source", "EXT")).upper()
        source = TRIGGER_SOURCES.get(source_name)
        if source is None:
            raise PicoScopeConfigurationError(
                f"PicoScope trigger source {source_name!r} is unsupported"
            )
        threshold_adc = int(trigger.get("threshold_adc", trigger.get("threshold_counts", 1000)))
        direction = int(trigger.get("direction", 2))
        delay = int(trigger.get("delay_samples", 0))
        auto_trigger_ms = int(trigger.get("auto_trigger_ms", 0))
        status = self._driver.ps5000aSetSimpleTrigger(
            self._handle,
            enabled,
            source,
            threshold_adc,
            direction,
            delay,
            auto_trigger_ms,
        )
        self._check(status, "ps5000aSetSimpleTrigger")

    def apply_capture_settings(self) -> None:
        """Apply resolution, channel, and external-trigger settings without a capture."""

        if self.capture_settings.get("resolution"):
            self.set_device_resolution(str(self.capture_settings["resolution"]))
        self.configure_channels()
        self.set_external_trigger()

    def validate_sample_timing(self) -> dict[str, Any]:
        """Ask the device to validate recipe sample count and timebase."""

        self._require_open()
        total_samples = int(self.capture_settings.get("total_samples", 0))
        if total_samples <= 0:
            raise PicoScopeConfigurationError("PicoScope total_samples must be positive")
        timebase = int(self.capture_settings.get("timebase", 0))
        if timebase < 0:
            raise PicoScopeConfigurationError("PicoScope timebase must be non-negative")

        interval_ns = c_float()
        max_samples = c_int32()
        status = self._driver.ps5000aGetTimebase2(
            self._handle,
            timebase,
            total_samples,
            byref(interval_ns),
            byref(max_samples),
            0,
        )
        self._check(status, "ps5000aGetTimebase2")
        return {
            "timebase": timebase,
            "requested_samples": total_samples,
            "sample_interval_ns": float(interval_ns.value),
            "max_samples": int(max_samples.value),
        }

    def capture_block(
        self,
        raw_csv_path: str | Path,
        *,
        after_arm: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Capture a real block and save raw CH A/B ADC samples to CSV."""

        self._require_open()
        self.configure_channels()
        self.set_external_trigger()

        total_samples = int(self.capture_settings.get("total_samples", 0))
        if total_samples <= 0:
            raise PicoScopeConfigurationError("PicoScope total_samples must be positive")
        pre_trigger = int(self.capture_settings.get("pre_trigger_samples", 0))
        post_trigger = total_samples - pre_trigger
        if post_trigger <= 0:
            raise PicoScopeConfigurationError("PicoScope post-trigger sample count must be positive")
        timebase = int(self.capture_settings.get("timebase", 1))
        segment_index = 0

        buffer_a = (c_int16 * total_samples)()
        buffer_b = (c_int16 * total_samples)()
        for channel_name, buffer in (("A", buffer_a), ("B", buffer_b)):
            status = self._driver.ps5000aSetDataBuffer(
                self._handle,
                CHANNELS[channel_name],
                buffer,
                total_samples,
                segment_index,
                0,
            )
            self._check(status, f"ps5000aSetDataBuffer {channel_name}")

        time_indisposed = c_int32()
        status = self._driver.ps5000aRunBlock(
            self._handle,
            pre_trigger,
            post_trigger,
            timebase,
            byref(time_indisposed),
            segment_index,
            None,
            None,
        )
        self._check(status, "ps5000aRunBlock")
        if after_arm is not None:
            self._log("PicoScope armed; invoking one-shot trigger callback")
            after_arm()

        ready = c_int16(0)
        deadline = time.time() + float(self.capture_settings.get("timeout_s", 10.0))
        while time.time() < deadline and not ready.value:
            status = self._driver.ps5000aIsReady(self._handle, byref(ready))
            self._check(status, "ps5000aIsReady")
            time.sleep(0.01)
        if not ready.value:
            raise PicoScopeError("PicoScope block capture timed out before ready")

        sample_count = c_uint32(total_samples)
        overflow = c_int16()
        status = self._driver.ps5000aGetValues(
            self._handle,
            0,
            byref(sample_count),
            1,
            0,
            segment_index,
            byref(overflow),
        )
        self._check(status, "ps5000aGetValues")

        raw_path = Path(raw_csv_path)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        with raw_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["sample_index", "ch_a_adc", "ch_b_adc"])
            for index in range(sample_count.value):
                writer.writerow([index, int(buffer_a[index]), int(buffer_b[index])])

        summary = {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "picoscope_model": self.device_config.get("model"),
            "picoscope_serial": self.device_config.get("serial_number"),
            "resolution": self.capture_settings.get("resolution"),
            "total_samples": int(sample_count.value),
            "overflow": int(overflow.value),
            "raw_data_file": str(raw_path),
        }
        return summary

    def stop(self) -> None:
        """Stop the PicoScope if it is open."""

        if self._driver is not None and self._is_open:
            status = self._driver.ps5000aStop(self._handle)
            self._check(status, "ps5000aStop")

    def close_unit(self) -> None:
        """Close the PicoScope unit."""

        if self._driver is not None and self._is_open:
            status = self._driver.ps5000aCloseUnit(self._handle)
            self._check(status, "ps5000aCloseUnit")
            self._is_open = False
        if self._driver is not None:
            self._driver = None

    def _load_driver(self):
        candidates: list[str] = []
        driver_path = self.device_config.get("driver_path")
        if driver_path:
            candidates.append(str(self._resolve_driver_path(driver_path)))
        search_paths = self.device_config.get("driver_search_paths") or []
        if isinstance(search_paths, list):
            for directory in search_paths:
                directory_path = self._resolve_driver_path(directory)
                if sys.platform.startswith("win") and directory_path.exists():
                    os.add_dll_directory(str(directory_path))
                    self._log(f"added PicoSDK DLL directory {directory_path}")
                candidates.append(str(directory_path / "ps5000a.dll"))
        names = (
            ["ps5000a.dll"]
            if sys.platform.startswith("win")
            else ["libps5000a.so", "libps5000a.dylib"]
        )
        candidates.extend(names)
        errors: list[str] = []
        for name in candidates:
            try:
                driver = cdll.LoadLibrary(name)
                self._log(f"loaded PicoSDK driver {name}")
                return driver
            except OSError as exc:
                errors.append(f"{name}: {exc}")
        raise PicoScopeError("PicoSDK ps5000a driver not available: " + "; ".join(errors))

    def _resolve_driver_path(self, path: Any) -> Path:
        candidate = Path(str(path))
        if candidate.is_absolute():
            return candidate
        return REPO_ROOT / candidate

    def _require_open(self) -> None:
        if self._driver is None:
            raise PicoScopeError("PicoScope unit is not open")

    def _check(self, status: int, label: str) -> None:
        self._log(f"{label} -> {int(status)}")
        if int(status) != PICO_OK:
            status_name = PICO_STATUS_NAMES.get(int(status), "UNKNOWN")
            raise PicoScopeError(
                f"{label} failed with Pico status {int(status)} ({status_name})"
            )

    def _log(self, message: str) -> None:
        if self.command_log is None:
            return
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        self.command_log.write(f"{timestamp} picoscope {message}\n")
        self.command_log.flush()


def c_float_or_zero(value: Any):
    """Create a ctypes float without importing it into the public namespace."""

    from ctypes import c_float

    return c_float(float(value or 0.0))
