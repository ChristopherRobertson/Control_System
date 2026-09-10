"""Deterministic installed-route recipes; electrical resolution is not optical IRF.

T660 F5 manual pp. 5-6 specifies a 10 ps edge grid and 0.02 Hz DDS grid.
Only sparse one-probe cycles with a calibrated HF2LI impulse-area estimator are
represented. T660-2 C (process trigger) and both unwired D outputs remain OFF.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Any

from .settings import Settings

HARDWARE_EDGE_GRID_NS = 0.01
DDS_GRID_HZ = 0.02


def quantize_ns(value: float, step_ns: float = HARDWARE_EDGE_GRID_NS) -> float:
    if not math.isfinite(float(value)) or not math.isfinite(float(step_ns)) or step_ns <= 0:
        raise ValueError("Timing and quantization step must be finite, with positive step")
    multiple = step_ns / HARDWARE_EDGE_GRID_NS
    if step_ns < HARDWARE_EDGE_GRID_NS or not math.isclose(multiple, round(multiple), abs_tol=1e-8):
        raise ValueError("T660 edge step must be a multiple of the documented 0.01 ns grid")
    units = (Decimal(str(value)) / Decimal(str(step_ns))).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return float(units * Decimal(str(step_ns)))


def _channel(enabled: bool, delay_ns: float, width_ns: float) -> dict[str, Any]:
    return {"enabled": enabled, "delay": f"{delay_ns:.12g}ns", "width": f"{width_ns:.12g}ns", "polarity": "positive", "termination": "50OHM"}


def inert_frame(settings: Settings, kind: str) -> dict[str, Any]:
    width = quantize_ns(settings.pump_command_width_ns, settings.timing_step_ns)
    channels = {c: _channel(False, 0, width) for c in "ABCD"}
    channels["C"]["polarity"] = "negative"  # Installed active-low Process Trigger: inactive high.
    return {"kind": kind, "channels": channels, "train_count": 0, "train_spacing_s": 80e-9, "frame_repetition": 1}


def event_frames(settings: Settings, requested_delay_ns: float, *, pump_on: bool) -> tuple[dict[str, Any], ...]:
    step = settings.timing_step_ns
    anchor = quantize_ns(settings.probe_anchor_ns, step)
    # optical delay = probe command - Q command + calibrated route offset.
    optical_offset = settings.optical_delay_offset_ns or 0.0
    q = quantize_ns(anchor + optical_offset - requested_delay_ns, step)
    fire = quantize_ns(q - settings.fire_to_q_ns, step)
    if min(q, fire) < 0:
        raise ValueError("Probe anchor must accommodate largest delay and qualified FIRE-to-Q interval")
    event = inert_frame(settings, "pump_probe" if pump_on else "pump_blocked")
    event["channels"]["A"] = _channel(pump_on, fire, quantize_ns(settings.pump_command_width_ns, step))
    event["channels"]["B"] = _channel(pump_on, q, quantize_ns(settings.pump_command_width_ns, step))
    return tuple([inert_frame(settings, "reference_warmup") for _ in range(settings.warmup_frames)] + [event] +
                 [inert_frame(settings, "impulse_tail") for _ in range(settings.filter_tail_frames)] + [inert_frame(settings, "terminal")])


@dataclass(frozen=True)
class TimingCompilation:
    t660_1_recipe: dict[str, Any]
    frames: tuple[dict[str, Any], ...]
    frame_period_s: float
    input_frequency_hz: float
    predivider: int
    quantized_delays_ns: tuple[float, ...]
    electrical_delays_ns: tuple[float, ...]
    requested_probe_period_s: float
    resolution_statement: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compile_timing(settings: Settings | dict[str, Any]) -> TimingCompilation:
    s = Settings.from_dict(settings)
    if s.warmup_frames < 0 or s.filter_tail_frames < 0 or s.warmup_frames + s.filter_tail_frames + 2 > min(s.max_frame_capacity, 8192):
        raise ValueError("An explicitly planned event burst exceeds verified finite frame capacity")
    if s.probe_period_s <= 0 or not math.isfinite(s.probe_period_s):
        raise ValueError("Probe period must be finite and positive")
    frequency = float((Decimal(str(1 / s.probe_period_s)) / Decimal(str(DDS_GRID_HZ))).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * Decimal(str(DDS_GRID_HZ)))
    if frequency <= 0 or frequency > 16000000:
        raise ValueError("Requested period is outside documented T660 DDS frequency/grid; a qualified divided-clock kernel is required")
    period = 1 / frequency
    step = s.timing_step_ns
    anchor = quantize_ns(s.probe_anchor_ns, step)
    width = quantize_ns(s.probe_command_width_ns, step)
    if width <= 0 or anchor < 0 or anchor + width >= period * 1e9 - 1000:
        raise ValueError("Probe pulse must have positive width and finish within its hardware cycle")
    recipe = {"stop_first": True, "trigger_source": "OFF", "predivider": 1,
              "gate_mode": 0, "burst_enabled": False, "clock": {"frequency": f"{frequency:.12g}Hz", "shots": 0},
              "channels": {"A": _channel(True, anchor, width), "B": _channel(True, anchor, width),
                           "C": _channel(True, 0, width), "D": _channel(False, 0, width)}}
    physical, electrical, frames = [], [], []
    offset = s.optical_delay_offset_ns or 0.0
    for delay in s.delays_ns:
        f = event_frames(s, delay, pump_on=True)
        for frame in f:
            for channel in frame["channels"].values():
                end = float(channel["delay"][:-2]) + float(channel["width"][:-2])
                if end >= period * 1e9 - 1000:
                    raise ValueError("FIRE/Q command does not finish before next hardware cycle")
        q = float(f[s.warmup_frames]["channels"]["B"]["delay"][:-2])
        electrical.append(anchor - q)
        physical.append(anchor - q + offset)
        frames.extend(f)
    return TimingCompilation(recipe, tuple(frames), period, frequency, 1, tuple(physical), tuple(electrical), s.probe_period_s,
                             "0.01 ns is the documented electrical command grid only; optical resolution is set by measured IRF, jitter, probe aperture and qualified HF2LI impulse extraction.")
