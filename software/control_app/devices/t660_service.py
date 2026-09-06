"""Service adapter for real Highland Technologies T660 delay generators."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO
import math
import socket
import time

from control_app.config_loader import load_hardware_config


CHANNEL_EDGES = {
    "A": (1, 2),
    "B": (3, 4),
    "C": (5, 6),
    "D": (7, 8),
}

TRIGGER_SOURCES = {"OFF", "SYN", "EXT", "INT", "REM"}
UINT32_MAX = (1 << 32) - 1
# T660 Manual, revision F5, sections 5.3 and 5.4: indices 0..8191.
T660_FRAME_CAPACITY = 8192
T660_FRAME_CAPACITY_SOURCE = "Highland T660 Manual F5, sections 5.3-5.4"


class T660Error(RuntimeError):
    """Base error for T660 service failures."""


class T660ConfigurationError(T660Error):
    """Raised when required T660 configuration is missing."""


class T660CommandError(T660Error):
    """Raised when a T660 command reports an error."""


class T660Service:
    """Real hardware command session for a configured T660 unit."""

    def __init__(
        self,
        name: str,
        device_config: dict[str, Any],
        *,
        timeout_s: float = 0.5,
        command_log: TextIO | None = None,
    ) -> None:
        self.name = name
        self.device_config = device_config
        self.timeout_s = timeout_s
        self.command_log = command_log
        self._serial = None
        self._socket: socket.socket | None = None

    @classmethod
    def from_config(
        cls,
        name: str,
        *,
        config_path: str | Path | None = None,
        command_log: TextIO | None = None,
        timeout_s: float = 0.5,
    ) -> "T660Service":
        """Create a service for a T660 device in hardware_configuration.yaml."""

        config, _, _ = load_hardware_config(config_path)
        devices = config.get("devices") or {}
        device_config = devices.get(name)
        if not isinstance(device_config, dict):
            raise T660ConfigurationError(f"{name} not found in hardware configuration")
        return cls(name, device_config, timeout_s=timeout_s, command_log=command_log)

    def connect(self) -> None:
        """Open the configured serial or TCP command session."""

        interface = self.device_config.get("interface")
        if interface is None:
            interface = "tcp" if self.device_config.get("host") else "serial"

        if interface == "serial":
            port = self.device_config.get("preferred_port") or self.device_config.get("port")
            baudrate = self.device_config.get("baudrate")
            if not port or not baudrate:
                raise T660ConfigurationError(f"{self.name} serial port/baudrate missing")
            try:
                import serial
            except ImportError as exc:
                raise T660ConfigurationError("pyserial is required for T660 serial control") from exc
            self._serial = serial.Serial(
                port=str(port),
                baudrate=int(baudrate),
                timeout=self.timeout_s,
                write_timeout=self.timeout_s,
            )
        elif interface == "tcp":
            host = self.device_config.get("host")
            port = self.device_config.get("tcp_port") or self.device_config.get("port")
            if not host or not port:
                raise T660ConfigurationError(f"{self.name} TCP host/port missing")
            self._socket = socket.create_connection((str(host), int(port)), timeout=self.timeout_s)
            self._socket.settimeout(self.timeout_s)
        else:
            raise T660ConfigurationError(f"{self.name} unsupported interface {interface!r}")

        self._set_p500_session()

    def identify(self) -> str:
        """Return the T660 identity string."""

        return self.command("*IDN?")

    def get_firmware_version(self) -> str:
        """Return the firmware string if the unit reports it."""

        identity = self.command("*IDN?")
        parts = [part.strip() for part in identity.split(",")]
        if len(parts) >= 4 and parts[3]:
            return parts[3]
        raise T660CommandError(
            f"{self.name} returned malformed *IDN? response {identity!r}"
        )

    def force_eod(self) -> str:
        """Force an end-of-delay event."""

        return self.command("FEOD")

    def set_clock_mode(
        self,
        mode: str | None = None,
        *,
        frequency: str | float | int | None = None,
        shots: int | None = None,
    ) -> None:
        """Configure the synthesizer and optionally reset its elapsed-shot counter.

        On the T660, ``TRIG:SHOTS <n>`` clears the elapsed-shot counter; it does
        not limit a run to *n* shots. Finite acquisition is enforced by the
        calling workflow issuing STOP after its requested captures.
        """

        if frequency is not None:
            self.command(f"TRIG:FREQ:SYN {frequency}", expect_response=False)
        if shots is not None:
            shot_counter_reset = _integer_value(shots, field="clock.shots")
            self.command(f"TRIG:SHOTS {shot_counter_reset}", expect_response=False)
        if mode is not None:
            self.set_trigger_source(str(mode))

    def set_trigger_source(self, source: str) -> None:
        """Set the T660 trigger source to OFF, SYN, EXT, INT, or REM."""

        normalized = str(source).strip().upper()
        if normalized not in TRIGGER_SOURCES:
            raise T660ConfigurationError(f"unsupported T660 trigger source {source!r}")
        self.command(f"TRIG:SOUR {normalized}", expect_response=False)

    def reset_shot_counter(self) -> None:
        """Clear the elapsed-shot counter without implying a finite-shot limit."""

        self.command("TRIG:SHOTS 0", expect_response=False)

    def set_external_trigger_predivider(self, divisor: int) -> None:
        """Set the documented predivider (0 and 1 both mean divide by one)."""
        value = _uint32_value(divisor, field="predivider")
        self.command(f"TRIGger:EXTernal:PREDiv {value}", expect_response=False)

    def verified_frame_capacity(self) -> int:
        """Check the actual feature, then use the manufacturer's documented limit.

        The T660 provides a feature query, but no frame-memory-size query. Do
        not infer this capability from a configured role or a free memory guess.
        """
        available = self.command("FEATure:FRAMe?").strip()
        if available != "1":
            raise T660ConfigurationError(
                f"{self.name} does not report Trains and Frames support: {available!r}"
            )
        return T660_FRAME_CAPACITY

    def configure_train(self, *, count: int = 0, spacing_s: float = 80e-9,
                        stage: str = "QUEue") -> None:
        """Set additional pulses per shot; count zero disables train repetition."""
        count = _uint32_value(count, field="train.count")
        normalized = str(stage).upper()
        stages = {"ACTIVE": "ACTive", "NEXT": "NEXT", "QUEUE": "QUEue"}
        if normalized not in stages:
            raise T660ConfigurationError("train stage must be ACTive, NEXT, or QUEue")
        spacing = float(spacing_s)
        # Use the stricter operational manual minimum (80 ns) and a 20 ns grid.
        if (not math.isfinite(spacing) or not 80e-9 <= spacing <= 10.0 or
                not math.isclose(spacing / 20e-9, round(spacing / 20e-9), abs_tol=1e-6)):
            raise T660ConfigurationError("train spacing must be 80 ns..10 s on the 20 ns grid")
        prefix = f"TRAin:{stages[normalized]}"
        self.command(f"{prefix}:CouNT {count}", expect_response=False)
        self.command(f"{prefix}:SPACe {spacing:.12g}s", expect_response=False)

    def configure_continuous_clock(self, *, frequency_hz: float = 2_000_000.0,
                                   pulse_width_ns: float = 150.0) -> dict[str, Any]:
        """Preconfigure T660-1 A/B/C for the common 2 MHz clock, source OFF."""
        frequency, width = float(frequency_hz), float(pulse_width_ns)
        if (not math.isfinite(frequency) or not math.isclose(frequency, 2_000_000.0) or
                not math.isfinite(width) or width <= 0 or frequency * width / 1e9 > .3):
            raise T660ConfigurationError("phase-scan clock requires 2 MHz and a positive width at most 30% duty")
        settings = {
            "stop_first": True, "trigger_source": "OFF", "predivider": 1,
            "gate_mode": 0, "burst_enabled": False,
            "clock": {"frequency": f"{frequency:g}Hz", "shots": 0},
            "channels": {channel: {"enabled": channel != "D", "delay": "0ns",
                "width": f"{width:g}ns", "polarity": "positive", "termination": "50OHM"}
                for channel in "ABCD"},
        }
        self.set_trigger_source("OFF")
        for rising, _ in CHANNEL_EDGES.values():
            self.command(f"TIME:RELTo{rising} 0", expect_response=False)
        self.apply_recipe(settings)
        return settings

    def start_continuous_clock(self) -> None:
        """Enable the preconfigured clock after finite acquisition is armed."""
        self.set_trigger_source("SYN")
        self.command("START", expect_response=False)

    def preload_frame_table(self, frames: list[dict[str, Any]], *,
                            predivider: int = 600_000,
                            input_frequency_hz: float = 2_000_000.0) -> dict[str, Any]:
        """Load a bounded finite table with trigger input disabled throughout.

        Frame entries contain a complete ``channels`` mapping, using the same
        delay/width, polarity and termination fields as a recipe. Only pending
        staging commands are used while storing frames. A single acquisition
        needs an inert second frame because the hardware requires FIRST < LAST.
        No software-trigger/per-record programming fallback is provided.
        """
        if not frames:
            raise T660ConfigurationError("frame table must contain at least one acquisition")
        capacity = self.verified_frame_capacity()
        if len(frames) > capacity:
            raise T660ConfigurationError(f"frame table needs {len(frames)} entries; verified capacity is {capacity}")
        divisor = _uint32_value(predivider, field="predivider")
        frequency = float(input_frequency_hz)
        if not math.isfinite(frequency) or frequency <= 0:
            raise T660ConfigurationError("frame input frequency must be finite and positive")
        frame_period_s = max(divisor, 1) / frequency
        table = list(frames)
        # Validate the entire block before any instrument mutation.
        for index, frame in enumerate(table):
            channels = frame.get("channels")
            if not isinstance(channels, dict) or set(channels) != set("ABCD"):
                raise T660ConfigurationError(f"frame {index} must explicitly configure A/B/C/D")
            self.validate_recipe_section(self.name, {"channels": channels})
            for channel, settings in channels.items():
                if not {"enabled", "delay", "width", "polarity", "termination"} <= set(settings):
                    raise T660ConfigurationError(f"frame {index} channel {channel} has incomplete settings")
                if _seconds_value(settings["delay"]) < 0 or _seconds_value(settings["width"]) <= 0:
                    raise T660ConfigurationError("frame delays must be nonnegative and widths positive")
                if _seconds_value(settings["delay"]) + _seconds_value(settings["width"]) >= frame_period_s - 1e-6:
                    raise T660ConfigurationError("frame channel timing must finish before the next frame trigger")
        if len(table) == 1:
            table.append({"channels": {ch: {**table[0]["channels"][ch], "enabled": False}
                                         for ch in "ABCD"}, "inert_terminator": True})
        self.set_trigger_source("OFF")
        self.command("STOP", expect_response=False)
        self.command("TFRame:STOp", expect_response=False)
        self.set_external_trigger_predivider(divisor)
        self.command("GATE:MODe 0", expect_response=False)
        self.command("BURst:MODe OFF", expect_response=False)
        self.command("TRIGger:INPut:POLarity POSitive", expect_response=False)
        self.command("TRIGger:INPut:TERMination 50OHM", expect_response=False)
        self.command("TRIGger:INPut:VOLTage 2", expect_response=False)
        self.reset_shot_counter()
        for channel in "ABCD":
            self.set_channel_timing_mode(channel, "delay_width")
            self.command(f"TIME:RELTo{CHANNEL_EDGES[channel][0]} 0", expect_response=False)
        for stage in ("ACTIVE", "NEXT", "QUEUE"):
            self.configure_train(count=0, stage=stage)
        for index, frame in enumerate(table):
            commands = []
            for channel in "ABCD":
                settings = frame["channels"][channel]
                rising, falling = CHANNEL_EDGES[channel]
                commands.append(f":TIME:QUEue{rising} {settings['delay']}")
                commands.append(f":TIME:QUEue{falling} {settings['width']}")
                commands.append(f":CHANnel:QUEue:MODe {channel}, {'ON' if settings['enabled'] else 'OFF'}")
                polarity = _normalize_polarity(settings["polarity"], field="polarity")
                commands.append(f":CHANnel:QUEue:POLarity {channel}, {polarity}")
                termination = _normalize_channel_termination(settings["termination"])
                commands.append(f":CHANnel:QUEue:TERMination {channel}, {termination}")
            commands.append(f":TFRame:STORe {index}")
            self.command_sequence(commands)
        self.command("TFRame:LOOP:FIRST 0", expect_response=False)
        self.command(f"TFRame:LOOP:LAST {len(table)-1}", expect_response=False)
        self.command("TFRame:LOOP:CouNT 0", expect_response=False)
        self.command("TFRame:LoadCouNT 0", expect_response=False)
        expected = {"first": ("TFRame:LOOP:FIRST?", 0),
                    "last": ("TFRame:LOOP:LAST?", len(table)-1),
                    "loop_count": ("TFRame:LOOP:CouNT?", 0),
                    "predivider": ("TRIGger:EXTernal:PREDiv?", divisor)}
        readback = {}
        for field, (command, value) in expected.items():
            actual = int(self.command(command))
            if actual != value:
                raise T660CommandError(f"{self.name} {field} readback {actual} != {value}")
            readback[field] = actual
        return {"acquisition_frame_count": len(frames), "physical_frame_count": len(table),
                "inert_terminator_count": len(table)-len(frames),
                "capacity": capacity, "capacity_source": T660_FRAME_CAPACITY_SOURCE,
                "frame_period_s": frame_period_s, "input_frequency_hz": frequency,
                "readback": readback}

    def start_frame_table(self) -> None:
        """Arm the finite engine, then accept divided external triggers."""
        # Changing trigger configuration may force EOD. Select EXT while STOP
        # still inhibits triggers, before the engine has loaded its first frame.
        # START only removes that inhibit (Programming Guide pp. 61-62).
        self.set_trigger_source("EXT")
        self.command("TFRame:STArt", expect_response=False)
        self.command("START", expect_response=False)

    def get_frames_status(self) -> str:
        status = self.command("TFRame:STATus?").strip().upper()
        if status not in {"OFF", "RUNNING", "DONE", "ERROR"}:
            raise T660CommandError(f"{self.name} invalid frames-engine status {status!r}")
        return status

    def get_shot_count(self) -> int:
        """Return the elapsed-shot counter."""

        return int(self.command("TRIG:SHOTS?"))

    def fire_remote_trigger(self) -> None:
        """Issue exactly one software trigger while the source is REM."""

        self.command("TRIG:EXECute")

    def set_channel_delay_width(self, channel: str, delay: str, width: str) -> None:
        """Set a channel to delay-width mode with active delay and width."""

        ch = self._channel(channel)
        rising_edge, falling_edge = CHANNEL_EDGES[ch]
        self.set_channel_timing_mode(ch, "delay_width")
        self.command(f"TIME:DEL{rising_edge} {delay}", expect_response=False)
        self.command(f"TIME:DEL{falling_edge} {width}", expect_response=False)

    def set_channel_timing_mode(self, channel: str, mode: str) -> None:
        """Set a channel to documented delay-width or rise-fall timing mode."""

        ch = self._channel(channel)
        normalized = _normalize_timing_mode(mode)
        command_mode = "DelayWidth" if normalized == "DW" else "RiseFall"
        self.command(f"CHAN:{command_mode} {ch}", expect_response=False)

    def enable_channel(self, channel: str) -> None:
        """Enable a channel output."""

        self.command(f"CHAN:ON {self._channel(channel)}", expect_response=False)

    def disable_channel(self, channel: str) -> None:
        """Disable a channel output."""

        self.command(f"CHAN:OFF {self._channel(channel)}", expect_response=False)

    def apply_recipe(self, recipe: dict[str, Any]) -> dict[str, Any]:
        """Apply one T660 unit's recipe section through documented commands."""

        self.validate_recipe_section(self.name, recipe)
        applied: dict[str, Any] = {"device": self.name, "commands": []}

        if "finite_frame_count" in recipe:
            channels = _finite_recipe_channels(recipe)
            count = int(recipe["finite_frame_count"])
            applied["timing_table"] = self.preload_frame_table(
                [{"channels": channels} for _ in range(count)],
                predivider=int(recipe.get("predivider", 1)),
                input_frequency_hz=float(recipe["frame_input_frequency_hz"]),
            )
            if recipe.get("start", False):
                self.start_frame_table()
                applied["start"] = True
            return applied

        if recipe.get("stop_first", False):
            self.command("STOP", expect_response=False)
            applied["commands"].append("STOP")

        if recipe.get("frames_engine") is not None:
            if not self._supports_frames_engine():
                raise T660ConfigurationError(
                    f"{self.name} does not have the configured Trains and Frames feature"
                )
            self.command("TFRame:STOp", expect_response=False)
            # The frame engine and train registers persist between workflows.
            # Clear every staging bank before returning to single-shot timing.
            for stage in ("ACTIVE", "NEXT", "QUEUE"):
                self.configure_train(count=0, stage=stage)
            applied["frames_engine"] = "OFF"

        if "predivider" in recipe:
            predivider = _uint32_value(recipe["predivider"], field="predivider")
            self.command(
                f"TRIGger:EXTernal:PREDiv {predivider}",
                expect_response=False,
            )
            applied["predivider"] = predivider

        if "gate_mode" in recipe:
            gate_mode = _integer_value(recipe["gate_mode"], field="gate_mode")
            self.command("GATE:MODe 0", expect_response=False)
            applied["gate_mode"] = gate_mode

        if "burst_enabled" in recipe:
            burst_enabled = _boolean_value(
                recipe["burst_enabled"], field="burst_enabled"
            )
            self.command(
                f"BURst:MODe {'ON' if burst_enabled else 'OFF'}",
                expect_response=False,
            )
            applied["burst_enabled"] = burst_enabled

        external_trigger = recipe.get("external_trigger") or {}
        if external_trigger:
            polarity = _normalize_polarity(
                external_trigger.get("polarity", "positive"),
                field="external_trigger.polarity",
            )
            self.command(
                "TRIGger:INPut:POLarity POSitive"
                if polarity == "POS"
                else "TRIGger:INPut:POLarity NEGative",
                expect_response=False,
            )
            termination = _normalize_trigger_termination(
                external_trigger.get("termination", "50OHM")
            )
            self.command(
                f"TRIGger:INPut:TERMination {termination}",
                expect_response=False,
            )
            threshold_v = float(external_trigger.get("threshold_v", 2.0))
            self.command(
                f"TRIGger:INPut:VOLTage {threshold_v:g}",
                expect_response=False,
            )
            applied["external_trigger"] = {
                "polarity": "positive" if polarity == "POS" else "negative",
                "termination": termination,
                "threshold_v": threshold_v,
            }

        clock = recipe.get("clock") or {}
        if clock:
            self.set_clock_mode(
                clock.get("mode"),
                frequency=clock.get("frequency"),
                shots=clock.get("shots"),
            )
            applied["clock"] = clock

        if "trigger_source" in recipe:
            self.set_trigger_source(str(recipe["trigger_source"]))
            applied["trigger_source"] = recipe["trigger_source"]

        channels = recipe.get("channels") or {}
        for channel, settings in channels.items():
            ch = self._channel(channel)
            if "delay" in settings or "width" in settings:
                self.set_channel_delay_width(ch, str(settings["delay"]), str(settings["width"]))
            elif "timing_mode" in settings:
                self.set_channel_timing_mode(ch, str(settings["timing_mode"]))
            if "polarity" in settings:
                normalized = _normalize_polarity(
                    settings["polarity"], field=f"channel {ch} polarity"
                )
                if normalized == "POS":
                    self.command(f"CHAN:POS {ch}", expect_response=False)
                else:
                    self.command(f"CHAN:NEG {ch}", expect_response=False)
            if "termination" in settings:
                normalized = _normalize_channel_termination(settings["termination"])
                if normalized == "50OHM":
                    self.command(f"CHAN:50OHM {ch}", expect_response=False)
                else:
                    self.command(f"CHAN:LOwZ {ch}", expect_response=False)
            if "enabled" in settings:
                enabled = _boolean_value(
                    settings["enabled"], field=f"channel {ch} enabled"
                )
                if enabled:
                    self.enable_channel(ch)
                else:
                    self.disable_channel(ch)
            applied.setdefault("channels", {})[ch] = settings

        if recipe.get("force_eod", False):
            self.force_eod()
            applied["force_eod"] = True

        if recipe.get("start", False):
            self.command("START", expect_response=False)
            applied["start"] = True

        return applied

    @staticmethod
    def validate_recipe_section(name: str, recipe: dict[str, Any]) -> None:
        """Validate one resolved unit section without opening hardware."""

        if not isinstance(recipe, dict):
            raise T660ConfigurationError(f"{name} recipe must be a mapping")
        for field in ("stop_first", "force_eod", "start"):
            if field in recipe:
                _boolean_value(recipe[field], field=f"{name}.{field}")
        if "frames_engine" in recipe:
            frames_mode = str(recipe["frames_engine"]).strip().upper()
            if frames_mode != "OFF":
                raise T660ConfigurationError(
                    f"{name} unsupported frames_engine mode {recipe['frames_engine']!r}"
                )
        if "finite_frame_count" in recipe:
            count = _uint32_value(recipe["finite_frame_count"], field="finite_frame_count")
            if not 1 <= count <= T660_FRAME_CAPACITY:
                raise T660ConfigurationError("finite_frame_count must be in 1..8192")
            if str(recipe.get("trigger_source", "")).upper() != "EXT":
                raise T660ConfigurationError("finite frame recipes require external triggering")
            try:
                frequency = float(recipe["frame_input_frequency_hz"])
            except (KeyError, TypeError, ValueError) as exc:
                raise T660ConfigurationError("finite frame recipes require frame_input_frequency_hz") from exc
            if not math.isfinite(frequency) or frequency <= 0:
                raise T660ConfigurationError("frame input frequency must be finite and positive")
            channels = _finite_recipe_channels(recipe)
            period = max(_uint32_value(recipe.get("predivider", 1), field="predivider"), 1) / frequency
            for channel, settings in channels.items():
                if not {"enabled", "delay", "width", "polarity", "termination"} <= set(settings):
                    raise T660ConfigurationError(f"finite frame channel {channel} is incomplete")
                delay, width = _seconds_value(settings["delay"]), _seconds_value(settings["width"])
                if delay < 0 or width <= 0 or delay + width >= period - 1e-6:
                    raise T660ConfigurationError("finite channel timing must finish before the next frame trigger")
        if "predivider" in recipe:
            _uint32_value(recipe["predivider"], field=f"{name}.predivider")
        if "gate_mode" in recipe:
            gate_mode = _integer_value(recipe["gate_mode"], field=f"{name}.gate_mode")
            if gate_mode != 0:
                raise T660ConfigurationError(
                    "calibration recipes only support gate_mode 0 (disabled)"
                )
        if "burst_enabled" in recipe:
            _boolean_value(
                recipe["burst_enabled"], field=f"{name}.burst_enabled"
            )
        if "trigger_source" in recipe:
            source = str(recipe["trigger_source"]).strip().upper()
            if source not in TRIGGER_SOURCES:
                raise T660ConfigurationError(
                    f"unsupported T660 trigger source {recipe['trigger_source']!r}"
                )

        external_trigger = recipe.get("external_trigger")
        if external_trigger is not None:
            if not isinstance(external_trigger, dict):
                raise T660ConfigurationError(
                    f"{name} external_trigger must be a mapping"
                )
            if external_trigger:
                _normalize_polarity(
                    external_trigger.get("polarity", "positive"),
                    field=f"{name}.external_trigger.polarity",
                )
                _normalize_trigger_termination(
                    external_trigger.get("termination", "50OHM")
                )
                try:
                    threshold_v = float(external_trigger.get("threshold_v", 2.0))
                except (TypeError, ValueError) as exc:
                    raise T660ConfigurationError(
                        f"{name} external trigger threshold_v must be numeric"
                    ) from exc
                if not math.isfinite(threshold_v) or not 0.25 <= threshold_v <= 3.3009:
                    raise T660ConfigurationError(
                        "external trigger threshold_v must be within 0.25..3.3009 V"
                    )

        clock = recipe.get("clock")
        if clock is not None:
            if not isinstance(clock, dict):
                raise T660ConfigurationError(f"{name} clock must be a mapping")
            if clock.get("mode") is not None:
                source = str(clock["mode"]).strip().upper()
                if source not in TRIGGER_SOURCES:
                    raise T660ConfigurationError(
                        f"unsupported T660 trigger mode {clock['mode']!r}"
                    )
            if clock.get("shots") is not None:
                _integer_value(clock["shots"], field=f"{name}.clock.shots")

        channels = recipe.get("channels")
        if channels is not None and not isinstance(channels, dict):
            raise T660ConfigurationError(f"{name} channels must be a mapping")
        for channel, settings in (channels or {}).items():
            ch = T660Service._channel(channel)
            if not isinstance(settings, dict):
                raise T660ConfigurationError(
                    f"{name} channel {ch} settings must be a mapping"
                )
            has_delay = "delay" in settings
            has_width = "width" in settings
            if has_delay != has_width:
                raise T660ConfigurationError(
                    f"{name} channel {ch} needs both delay and width"
                )
            if "timing_mode" in settings:
                timing_mode = _normalize_timing_mode(settings["timing_mode"])
                if (has_delay or has_width) and timing_mode != "DW":
                    raise T660ConfigurationError(
                        f"{name} channel {ch} delay/width requires delay-width mode"
                    )
            if "polarity" in settings:
                _normalize_polarity(
                    settings["polarity"], field=f"{name} channel {ch} polarity"
                )
            if "termination" in settings:
                _normalize_channel_termination(settings["termination"])
            if "enabled" in settings:
                _boolean_value(
                    settings["enabled"], field=f"{name} channel {ch} enabled"
                )

    def read_active_settings(self) -> dict[str, Any]:
        """Query active timing, trigger, and channel settings."""

        settings: dict[str, Any] = {
            "device": self.name,
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "queries": {},
        }
        identity = self._safe_query("*IDN?")
        settings["queries"]["identity"] = identity
        if identity.get("ok"):
            parts = [
                part.strip()
                for part in str(identity.get("response", "")).split(",")
            ]
            settings["queries"]["firmware"] = {
                "ok": len(parts) >= 4 and bool(parts[3]),
                "response": parts[3] if len(parts) >= 4 else "",
                "source": "*IDN?",
            }
        else:
            settings["queries"]["firmware"] = dict(identity)

        query_commands = [
            ("trigger_source", "TRIG:SOUR?"),
            ("synth_frequency", "TRIG:FREQ:SYN?"),
            # Physical 10 MHz CLOCK routing is distinct from the pulse-trigger
            # synthesizer. These are informational readbacks, never setters.
            ("clock_connector_mode", "CLOCk:MODe?"),
            ("clock_external_lock_enabled", "CLOCk:EXTernaL?"),
            ("clock_external_frequency_hz", "CLOCk:FREQuency?"),
            ("clock_lock_status", "CLOCk:STATus?"),
            ("shots", "TRIG:SHOTS?"),
            ("predivider", "TRIGger:EXTernal:PREDiv?"),
            ("trigger_input_polarity", "TRIGger:INPut:POLarity?"),
            ("trigger_input_termination", "TRIGger:INPut:TERMination?"),
            ("trigger_input_threshold_v", "TRIGger:INPut:VOLTage?"),
            ("gate_mode", "GATE:MODe?"),
            ("burst", "BURst:MODe?"),
        ]
        if self._supports_frames_engine():
            query_commands.append(("frames_engine", "TFRame:STATus?"))
            query_commands.append(("train_count", "TRAin:ACTive:CouNT?"))
        for label, command in query_commands:
            settings["queries"][label] = self._safe_query(command)

        channel_settings: dict[str, Any] = {}
        for channel, edges in CHANNEL_EDGES.items():
            channel_settings[channel] = {
                "enabled": self._safe_query(f"CHAN:ON? {channel}"),
                "timing_mode": self._safe_query(f"CHAN:TimingMODe? {channel}"),
                "termination": self._safe_query(f"CHAN:50OHM? {channel}"),
                "polarity": self._safe_query(
                    f"CHANnel:ACTive:POLarity? {channel}"
                ),
                "delay_edge": self._safe_query(f"TIME:DEL{edges[0]}?"),
                "width_edge": self._safe_query(f"TIME:DEL{edges[1]}?"),
            }
        settings["channels"] = channel_settings
        return settings

    def close(self) -> None:
        """Close the hardware command session."""

        if self._serial is not None:
            self._serial.close()
            self._serial = None
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def command(
        self,
        command: str,
        *,
        expect_response: bool = True,
        delay_s: float = 0.04,
    ) -> str:
        """Send one command and return the raw text response."""

        if self._serial is None and self._socket is None:
            raise T660Error(f"{self.name} is not connected")
        if self._serial is not None:
            self._serial.reset_input_buffer()
            self._serial.write((command + "\r").encode("ascii"))
            self._serial.flush()
            time.sleep(delay_s)
            response = self._read_serial()
        else:
            assert self._socket is not None
            self._socket.sendall((command + "\r").encode("ascii"))
            time.sleep(delay_s)
            response = self._read_socket()

        self._log(command, response)
        stripped = response.strip()
        if stripped.startswith("??") or stripped.startswith("?"):
            raise T660CommandError(f"{self.name} command {command!r} failed: {stripped}")
        if expect_response and not stripped:
            raise T660CommandError(f"{self.name} command {command!r} returned no response")
        return stripped

    def command_sequence(self, commands: list[str] | tuple[str, ...]) -> list[str]:
        """Execute one documented semicolon-delimited P500 command line.

        The T660 processes every command in the line before replying. This is
        useful for timing updates that must become active between one-shot REM
        events without paying a serial round trip for every edge setting.
        """
        values = [str(value).strip() for value in commands]
        if not values or any(not value or ";" in value for value in values):
            raise T660ConfigurationError("T660 command sequences require nonempty individual commands")
        response = self.command(";".join(values))
        parts = [part.strip() for part in response.split(";")]
        if len(parts) != len(values):
            raise T660CommandError(
                f"{self.name} compound command returned {len(parts)} responses for {len(values)} commands: {response!r}"
            )
        failed = [part for part in parts if part.startswith("?") or not part]
        if failed:
            raise T660CommandError(f"{self.name} compound command failed: {response}")
        return parts

    def _set_p500_session(self) -> None:
        """Select P500-style commands using documented short or long form."""

        errors: list[str] = []
        for command in ("ZM P500", "ZMode P500"):
            try:
                self.command(command)
                return
            except T660CommandError as exc:
                errors.append(str(exc))
        raise T660CommandError(
            f"{self.name} could not enter P500 command mode: {'; '.join(errors)}"
        )

    def _safe_query(self, command: str) -> dict[str, Any]:
        try:
            return {"ok": True, "response": self.command(command)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _supports_frames_engine(self) -> bool:
        role = str(self.device_config.get("role", "")).lower()
        return "trains_frames" in role

    def _read_serial(self) -> str:
        lines: list[str] = []
        deadline = time.time() + self.timeout_s
        assert self._serial is not None
        while time.time() < deadline:
            line = self._serial.readline()
            if not line:
                break
            text = line.decode("ascii", errors="replace").strip()
            if text:
                lines.append(text)
                break
        return "\n".join(lines)

    def _read_socket(self) -> str:
        chunks: list[bytes] = []
        deadline = time.time() + self.timeout_s
        assert self._socket is not None
        while time.time() < deadline:
            try:
                chunk = self._socket.recv(4096)
            except TimeoutError:
                break
            if not chunk:
                break
            chunks.append(chunk)
            if b"\n" in chunk or b"\r" in chunk:
                break
        return b"".join(chunks).decode("ascii", errors="replace").strip()

    def _log(self, command: str, response: str) -> None:
        if self.command_log is None:
            return
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        try:
            self.command_log.write(f"{timestamp} {self.name} << {command}\n")
            if response:
                for line in response.splitlines():
                    self.command_log.write(f"{timestamp} {self.name} >> {line}\n")
            self.command_log.flush()
        except ValueError:
            self.command_log = None

    @staticmethod
    def _channel(channel: str) -> str:
        ch = str(channel).upper()
        if ch not in CHANNEL_EDGES:
            raise T660ConfigurationError(f"unsupported T660 channel {channel!r}")
        return ch


def _integer_value(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise T660ConfigurationError(f"{field} must be an integer, not a boolean")
    try:
        converted = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise T660ConfigurationError(f"{field} must be an integer") from exc
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError):
        numeric = float(converted)
    if not math.isfinite(numeric) or numeric != converted:
        raise T660ConfigurationError(f"{field} must be an integer")
    return converted


def _finite_recipe_channels(recipe: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Complete only disabled frame slots; enabled pulse settings stay explicit."""
    requested = recipe.get("channels") or {}
    if set(requested) != set("ABCD"):
        raise T660ConfigurationError("finite frame recipes must explicitly configure A/B/C/D")
    disabled = {"enabled": False, "delay": "0ns", "width": "150ns",
                "polarity": "positive", "termination": "50OHM"}
    return {channel: ({**disabled, **settings} if settings.get("enabled") is False
                      else dict(settings)) for channel, settings in requested.items()}


def _seconds_value(value: Any) -> float:
    text = str(value).strip().lower()
    scale = 1.0
    for suffix, multiplier in (("ps", 1e-12), ("ns", 1e-9), ("us", 1e-6), ("ms", 1e-3), ("s", 1.0)):
        if text.endswith(suffix):
            text, scale = text[:-len(suffix)], multiplier
            break
    try:
        seconds = float(text) * scale
    except (ValueError, OverflowError) as exc:
        raise T660ConfigurationError(f"invalid frame time {value!r}") from exc
    if not math.isfinite(seconds):
        raise T660ConfigurationError("frame time must be finite")
    return seconds


def _uint32_value(value: Any, *, field: str) -> int:
    converted = _integer_value(value, field=field)
    if not 0 <= converted <= UINT32_MAX:
        raise T660ConfigurationError(f"{field} must be within 0..{UINT32_MAX}")
    return converted


def _boolean_value(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise T660ConfigurationError(f"{field} must be a YAML boolean")
    return value


def _normalize_polarity(value: Any, *, field: str) -> str:
    normalized = str(value).strip().upper()
    if normalized in {"POSITIVE", "POS", "+"}:
        return "POS"
    if normalized in {"NEGATIVE", "NEG", "-"}:
        return "NEG"
    raise T660ConfigurationError(f"unsupported {field} {value!r}")


def _normalize_trigger_termination(value: Any) -> str:
    normalized = str(value).strip().upper()
    if normalized in {"50OHM", "50", "50R", "ON"}:
        return "50OHM"
    if normalized in {"HIZ", "HI_Z", "NONE", "OFF"}:
        return "HIZ"
    raise T660ConfigurationError(
        f"unsupported external trigger termination {value!r}"
    )


def _normalize_channel_termination(value: Any) -> str:
    normalized = str(value).strip().upper()
    if normalized in {"50OHM", "50", "50R", "ON"}:
        return "50OHM"
    if normalized in {"LOWZ", "LOW_Z", "NONE", "OFF"}:
        return "LOWZ"
    raise T660ConfigurationError(f"unsupported channel termination {value!r}")


def _normalize_timing_mode(value: Any) -> str:
    normalized = str(value).strip().upper().replace("_", "").replace("-", "")
    if normalized in {"DW", "DELAYWIDTH"}:
        return "DW"
    if normalized in {"RF", "RISEFALL"}:
        return "RF"
    raise T660ConfigurationError(f"unsupported channel timing mode {value!r}")
