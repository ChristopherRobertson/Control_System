"""Deterministic finite T660-2 programs for stationary, continuous records.

The probe carrier is separate. Each program authorizes a finite user-selected shot count; the
runner executes the requested finite sequence and cadence. No host clock defines
a pump edge. Manufacturer bounds: T660 Manual F5 pp. 6, 8, 10, 24–28 (10 ps,
3600 s delay+width, 32-bit predivider, 8192 frames). The service uses an extra
1 us frame-end margin; these programs satisfy that service contract.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import math
from typing import Any, Mapping

EDGE_QUANTUM_S = 1e-11
MAX_CHANNEL_END_S = 3600.0
MAX_PREDIVIDER = 2**32 - 1
MAX_PHYSICAL_FRAMES = 8192
FRAME_END_MARGIN_S = 2e-6


class TimingError(ValueError):
    pass


def quantize_seconds(value: float, quantum_s: float = EDGE_QUANTUM_S, *, upward: bool = False) -> float:
    if isinstance(value, bool) or not math.isfinite(float(value)) or value < 0:
        raise TimingError("Time must be finite and nonnegative in seconds")
    if not math.isfinite(quantum_s) or quantum_s <= 0:
        raise TimingError("Timing quantum must be finite and positive")
    q = Decimal(str(quantum_s))
    return float((Decimal(str(value)) / q).to_integral_value(rounding=ROUND_CEILING if upward else ROUND_HALF_UP) * q)


def _cycles_up(seconds: float, rate_hz: float) -> int:
    return int((Decimal(str(seconds)) * Decimal(str(rate_hz))).to_integral_value(rounding=ROUND_CEILING))


def _command(value: float) -> str:
    return f"{value:.11f}s"


@dataclass(frozen=True)
class TimingProgram:
    frames: tuple[dict[str, Any], ...]
    predivider: int
    input_frequency_hz: float
    frame_period_s: float
    expected_pump_count: int
    pump_command_offsets_s: tuple[float, ...]
    duration_s: float
    selected_pre_observation_s: float
    selected_post_observation_s: float
    requested_pre_observation_s: float
    requested_post_observation_s: float
    train_count: int = 0
    train_spacing_s: float = 0.0
    frame_repetitions: int = 1
    loop_count: int = 0
    terminal_padding_frames: int = 1
    pump_epoch_basis: str = "programmed Q-switch command; observed electrical marker and independent optical arrival retained separately"
    schema_version: str = "1.0"

    @property
    def physical_frame_count(self) -> int:
        return len(self.frames)

    def to_dict(self) -> dict[str, Any]:
        result = deepcopy(asdict(self))
        result["frames"] = list(result["frames"])
        result["pump_command_offsets_s"] = list(result["pump_command_offsets_s"])
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TimingProgram":
        data = deepcopy(dict(value))
        data["frames"] = tuple(data["frames"])
        data["pump_command_offsets_s"] = tuple(data["pump_command_offsets_s"])
        return cls(**data)


def compile_timing(*, pre_observation_s: float, post_observation_s: float,
                   input_frequency_hz: float, fire_delay_s: float, q_switch_delay_s: float,
                   fire_width_s: float, q_switch_width_s: float, pump_enabled: bool = True,
                   fire_polarity: str = "positive", q_switch_polarity: str = "positive",
                   termination: str = "50OHM", frame_capacity: int = MAX_PHYSICAL_FRAMES,
                   edge_quantum_s: float = EDGE_QUANTUM_S, pump_shots: int = 1,
                   shot_delay_s: float = .1) -> TimingProgram:
    """Compile a continuous trial with pre-first-shot and post-last-shot capture.

    FIRE precedes each Q-switch by the selected delay. No hidden repetitions
    or host timers define the shot edges; the final hardware frame is inert.
    """
    for name, value in (("pre_observation_s", pre_observation_s), ("post_observation_s", post_observation_s),
                        ("input_frequency_hz", input_frequency_hz)):
        if isinstance(value, bool) or not math.isfinite(float(value)) or value <= 0:
            raise TimingError(f"{name} must be finite and positive")
    if not isinstance(pump_enabled, bool):
        raise TimingError("pump_enabled must be boolean")
    if not isinstance(frame_capacity, int) or not 3 <= frame_capacity <= MAX_PHYSICAL_FRAMES:
        raise TimingError("Frame capacity must be an integer in 3..8192")
    if input_frequency_hz > 16e6:
        raise TimingError("Probe/frame-input source exceeds T660 16 MHz synthesizer bound")
    quantum_ratio = edge_quantum_s / EDGE_QUANTUM_S
    if edge_quantum_s < EDGE_QUANTUM_S or not math.isclose(quantum_ratio, round(quantum_ratio), rel_tol=0, abs_tol=1e-7):
        raise TimingError("Selected edge quantum must be an integer multiple of the documented 10 ps resolution")
    fd, qd, fw, qw = (quantize_seconds(v, edge_quantum_s) for v in
                      (fire_delay_s, q_switch_delay_s, fire_width_s, q_switch_width_s))
    if fw <= 0 or qw <= 0 or qd < fd:
        raise TimingError("Pump widths must be positive and Q-switch must not precede FIRE")
    if max(fd + fw, qd + qw) > MAX_CHANNEL_END_S:
        raise TimingError("Channel delay plus width exceeds the documented 3600 s range")
    if fire_polarity not in {"positive", "negative"} or q_switch_polarity not in {"positive", "negative"}:
        raise TimingError("Unknown pump polarity")
    if termination not in {"50OHM", "LOWZ"}:
        raise TimingError("Unsupported output termination")
    if type(pump_shots) is not int or not 1 <= pump_shots <= frame_capacity - 1:
        raise TimingError("Pump Shots must be an integer within the finite timing capacity")
    if pump_shots > 1 and (not math.isfinite(shot_delay_s) or shot_delay_s < .1-1e-12):
        raise TimingError("Shot Delay must be at least 0.1 s (Nd:YAG maximum 10 Hz)")
    shot_delay_s = max(.1, shot_delay_s)
    gap = qd - fd
    # The user's pre-pump value describes the analysis window. Hardware may
    # need to start earlier to deliver FIRE before Q-switch; retain that lead-in
    # natively and crop it only when forming the pump-relative trace.
    first = quantize_seconds(max(pre_observation_s, gap), edge_quantum_s, upward=True)
    # FIRE and Q-switch can occupy different frames. This preserves the
    # requested pre-pump duration even when Q-switch lands on a frame boundary.
    divider = max(1, _cycles_up(shot_delay_s if pump_shots > 1 else
        max(first, (first + post_observation_s) / (frame_capacity - 1), gap + fw + FRAME_END_MARGIN_S), input_frequency_hz))
    if divider > MAX_PREDIVIDER:
        raise TimingError("Requested timing exceeds the T660 32-bit frame divider")
    period = divider / input_frequency_hz
    offsets = tuple(float(Decimal(str(first)) + i * Decimal(str(period))) for i in range(pump_shots)) if pump_enabled else ()
    last = offsets[-1] if offsets else first
    capture_end = last + post_observation_s
    nframes = _cycles_up(capture_end, 1 / period) + 1
    if nframes > frame_capacity:
        raise TimingError("Trial exceeds finite timing-table capacity; reduce shots or acquisition duration")
    # OFF frames must preserve the electrical idle level. In particular, loading
    # a positive-polarity OFF Q-switch frame before a negative pulse can itself
    # create a trigger transition, even while the frame engine is inhibited.
    polarities = {"A": fire_polarity, "B": q_switch_polarity, "C": "negative", "D": "positive"}
    off = {ch: {"enabled": False, "delay": _command(0), "width": _command(edge_quantum_s),
                "polarity": polarities[ch], "termination": termination} for ch in "ABCD"}
    table = [{"index": i, "kind": "terminal_all_off" if i == nframes-1 else "acquisition",
              "offset_s": i*period, "duration_s": period, "channels": deepcopy(off),
              "train_count": 0, "train_spacing_s": 0., "frame_repetitions": 1,
              "inert_terminator": i == nframes-1} for i in range(nframes)]
    for shot in offsets:
        for channel, edge, width, polarity in (("A", float(Decimal(str(shot))-Decimal(str(gap))), fw, fire_polarity), ("B", shot, qw, q_switch_polarity)):
            index = int(Decimal(str(edge)) // Decimal(str(period)))
            delay = quantize_seconds(max(0., edge-index*period), edge_quantum_s)
            if delay + width + FRAME_END_MARGIN_S > period or delay + width > MAX_CHANNEL_END_S:
                raise TimingError("Pump pulse crosses a timing-frame boundary; adjust Shot Delay or acquisition timing")
            table[index]["channels"][channel] = {"enabled": True, "delay": _command(delay),
                "width": _command(width), "polarity": polarity, "termination": termination}
            table[index]["kind"] = "pump_shot"
    return TimingProgram(tuple(table), divider, input_frequency_hz, period, len(offsets), offsets,
        capture_end, first, post_observation_s, pre_observation_s, post_observation_s)
