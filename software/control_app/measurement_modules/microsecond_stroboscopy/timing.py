"""Deterministic hardware frame compiler for continuous-probe local stroboscopy.

T660-1 A/B/C provide reference/probe/frame triggers.  T660-2 A/B supply FIRE and
Q-switch and C/D stay OFF during fixed-wavenumber acquisition.  Each biological
event is a declared finite block, followed by an independently verified reset.
The clock/frame engine defines electrical edges, never host polling or sleeps.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
import math
from typing import Any, Callable, Iterable, Mapping

from .settings import StroboscopySettings

UINT32_MAX = 2**32 - 1


def _quantize(value: float, quantum: float, *, upward: bool = False) -> float:
    if not math.isfinite(value) or not math.isfinite(quantum) or quantum <= 0:
        raise ValueError("Timing values and quantum must be finite; quantum must be positive")
    x, q = Decimal(str(value)), Decimal(str(quantum))
    return float((x / q).to_integral_value(rounding=ROUND_CEILING if upward else ROUND_HALF_UP) * q)


def _seconds(value: float) -> str:
    # Avoid lossy display precision: preserve the 10 ps command quantum.
    return f"{Decimal(str(value)).normalize():f}s"


def _channel(enabled: bool, delay_s: float, width_s: float) -> dict[str, Any]:
    return {"enabled": bool(enabled), "delay": _seconds(delay_s), "width": _seconds(width_s),
            "polarity": "positive", "termination": "50OHM"}


@dataclass(frozen=True)
class TimingEvent:
    event_index: int
    frame_index: int
    requested_delay_us: float
    selected_delay_us: float
    pump_command_time_s: float  # FIRE edge, not optical arrival
    q_command_time_s: float
    aperture_center_s: float
    aperture_start_s: float
    aperture_stop_s: float
    pumped: bool


@dataclass(frozen=True)
class TimingProgram:
    t6601_recipe: Mapping[str, Any]
    frames: tuple[Mapping[str, Any], ...]
    predivider: int
    input_frequency_hz: float
    frame_period_s: float
    events: tuple[TimingEvent, ...]
    prelude_s: float
    capture_duration_s: float
    requested_event_interval_s: float
    requested_probe_rate_hz: float
    command_quantum_s: float
    train_count: int = 0
    train_spacing_s: float = 0.0
    frame_repeat_count: int = 0
    terminal_padding_frames: int = 1
    timing_origin: str = "programmed electrical commands; requires observed marker and qualified optical latency"
    observable: str = "continuous-probe HF2LI filtered envelope averaged over the declared delay aperture"

    @property
    def duration_s(self) -> float:
        return self.capture_duration_s

    @property
    def physical_frame_count(self) -> int:
        return len(self.frames)

    @property
    def pump_event_count(self) -> int:
        return sum(event.pumped for event in self.events)

    @property
    def aperture_center_s(self) -> float:
        return self.events[0].aperture_center_s

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)

    def upload(self, t6602: Any, *, progress: Callable[[int, int], None] | None = None,
               cancel_check: Callable[[], None] | None = None) -> dict[str, Any]:
        """Use installed pending-field optimization; acknowledge before arming.

        The caller must hold the host operation's exclusive ownership throughout
        upload, capture, restoration and preservation.  This method never arms
        outputs and never creates another hardware session or token.
        """
        if cancel_check:
            cancel_check()
        receipt = t6602.preload_frame_table(
            [dict(frame) for frame in self.frames], predivider=self.predivider,
            input_frequency_hz=self.input_frequency_hz, progress=progress,
            cancel_check=cancel_check)
        actual = receipt.get("physical_frame_count")
        if actual != self.physical_frame_count:
            raise ValueError(f"Timing upload acknowledged {actual} physical frames; expected {self.physical_frame_count}")
        readback = receipt.get("readback", {})
        for field, expected in (("first", 0), ("last", self.physical_frame_count - 1),
                                ("loop_count", 0), ("predivider", self.predivider)):
            if readback.get(field) != expected:
                raise ValueError(f"Timing upload {field} acknowledgment differs from compiled schedule")
        return {"compiled": self.to_dict(), "acknowledged": receipt}


def compile_timing(settings: StroboscopySettings, delays_us: Iterable[float] | None = None,
                   *, pumped: bool = True) -> TimingProgram:
    """Compile a finite one-event block; repetition requires a new reset check.

    A multi-event biological table would prevent independent reset verification,
    so it is rejected explicitly.  The wavelength planner declares all blocks;
    it does not silently split a continuous capture.
    """
    supplied = tuple(float(v) for v in (settings.delays_us if delays_us is None else delays_us))
    if len(supplied) != 1:
        raise ValueError("Compile one declared event per block; independently verify reset before the next biological pump")
    delay_us = supplied[0]
    if not math.isfinite(delay_us):
        raise ValueError("Delay must be finite in microseconds")
    t = settings.timing
    quantum_s = t.timing_quantum_ns * 1e-9
    if not math.isclose(quantum_s, 1e-11, abs_tol=1e-20):
        raise ValueError("Installed T660 delay/width quantum is 10 ps (0.01 ns)")
    if not math.isclose(t.clock_frequency_quantum_hz, .02, abs_tol=1e-12):
        raise ValueError("T660 DDS command frequency quantum is 0.02 Hz")
    frequency = _quantize(t.probe_rate_hz, .02)
    if not 0 < frequency <= 16_000_000:
        raise ValueError("T660 internal trigger frequency must be positive and at most 16 MHz")
    if not math.isfinite(t.event_interval_s) or t.event_interval_s <= 0:
        raise ValueError("Event interval must be finite and positive")
    divider = int((Decimal(str(t.event_interval_s)) * Decimal(str(frequency))).to_integral_value(rounding=ROUND_CEILING))
    if not 1 <= divider <= UINT32_MAX:
        raise ValueError("Requested event interval exceeds T660 unsigned 32-bit predivider capacity")
    period = divider / frequency
    if not 0 < t.maximum_pump_rate_hz <= 10:
        raise ValueError("Surelite pump maximum cannot exceed 10 Hz")
    # There is only ONE enabled pump frame. OFF frame spacing is not a pump
    # cadence; the planner checks actual inter-block command separation.
    if not 0 < t.maximum_probe_duty_fraction <= .30:
        raise ValueError("MIRcat maximum probe duty fraction must be positive and no greater than 0.30")
    widths = tuple(_quantize(value * 1e-9, quantum_s) for value in
                   (t.reference_width_ns, t.probe_width_ns, t.frame_input_width_ns))
    probe_delay = _quantize(t.probe_delay_ns * 1e-9, quantum_s)
    if probe_delay < 0 or min(widths) <= 0:
        raise ValueError("Probe/reference widths must be positive and probe delay nonnegative after quantization")
    if widths[1] * frequency > t.maximum_probe_duty_fraction + 1e-12:
        raise ValueError("Probe width × rate exceeds selected MIRcat duty-cycle bound")
    if max(widths[0], widths[1] + probe_delay, widths[2]) + 62.5e-9 > 1 / frequency:
        raise ValueError("T660 probe edges plus 62.5 ns rearm interval exceed the trigger period")
    lead = _quantize(t.fire_to_q_us * 1e-6, quantum_s)
    guard = _quantize(t.command_guard_us * 1e-6, quantum_s, upward=True)
    fire_width = _quantize(t.fire_width_us * 1e-6, quantum_s)
    q_width = _quantize(t.q_switch_width_us * 1e-6, quantum_s)
    if min(lead, guard, fire_width, q_width) <= 0:
        raise ValueError("FIRE-to-Q lead, guard and command widths must be positive")
    full_delays = tuple(float(v) for v in settings.delays_us)
    if not full_delays or not all(math.isfinite(v) for v in full_delays):
        raise ValueError("The complete declared delay grid must be nonempty and finite")
    aperture = settings.response.integration_aperture_s
    if not math.isfinite(aperture) or aperture <= 0:
        raise ValueError("Integration aperture must be positive and finite")
    # Keep the aperture at a common phase in all independently armed blocks.
    target = _quantize(max(0, max(full_delays)) * 1e-6 + lead + guard + aperture / 2,
                       quantum_s, upward=True)
    q_delay = _quantize(target - delay_us * 1e-6, quantum_s)
    fire_delay = _quantize(q_delay - lead, quantum_s)
    if fire_delay < guard - quantum_s:
        raise ValueError("Delay is outside the declared grid's pre-pump timing guard")
    if max(q_delay + q_width, fire_delay + fire_width, target + aperture / 2) >= period - 1e-6:
        raise ValueError("Requested pump/delay/aperture does not fit inside the selected event frame")
    if t.frame_capacity < 3 or t.frame_capacity > 8192:
        raise ValueError("The finite block needs three frames and installed T660 capacity cannot exceed 8192")
    recipe = {"stop_first": True, "trigger_source": "OFF", "predivider": 1,
              "gate_mode": 0, "burst_enabled": False,
              "clock": {"frequency": f"{frequency:g}Hz", "shots": 0},
              "channels": {
                  "A": _channel(True, 0.0, widths[0]),
                  "B": _channel(True, probe_delay, widths[1]),
                  "C": _channel(True, 0.0, widths[2]),
                  "D": _channel(False, 0.0, quantum_s),
              }}
    off = {ch: _channel(False, 0.0, quantum_s) for ch in "ABCD"}
    active = {"A": _channel(pumped, fire_delay, fire_width),
              "B": _channel(pumped, q_delay, q_width),
              "C": _channel(False, 0.0, quantum_s), "D": _channel(False, 0.0, quantum_s)}
    frames = ({"channels": off, "kind": "pre_pump_baseline", "train_count": 0, "train_spacing_s": 0.0},
              {"channels": active, "kind": "pump_event" if pumped else "pump_blocked_control",
               "train_count": 0, "train_spacing_s": 0.0},
              {"channels": {ch: dict(value) for ch, value in off.items()},
               "kind": "terminal", "inert_terminator": True, "train_count": 0, "train_spacing_s": 0.0})
    event = TimingEvent(0, 1, delay_us, (target - q_delay) * 1e6,
                        period + fire_delay, period + q_delay, period + target,
                        period + target - aperture / 2, period + target + aperture / 2, pumped)
    return TimingProgram(recipe, frames, divider, frequency, period, (event,), period,
                         3 * period, t.event_interval_s, t.probe_rate_hz, quantum_s)
