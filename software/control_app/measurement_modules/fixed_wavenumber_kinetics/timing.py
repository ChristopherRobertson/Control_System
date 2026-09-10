"""Deterministic finite T660-2 programs for stationary, continuous records.

The probe carrier is separate. Each program authorizes at most one pump; the
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
                   edge_quantum_s: float = EDGE_QUANTUM_S) -> TimingProgram:
    """Compile one event with explicit probe-only baseline/recovery/terminal.

    The frame divider may extend the requested baseline to fit a long record in
    finite frame memory. The extension is reported; capture stays continuous.
    No extra train pulses or implicit table loops can generate another pump.
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
    # Baseline has no pump outputs. Frame 1 generates the authorized event.
    # Reserve terminal frame and at least one event frame in finite memory.
    minimum_period = max(pre_observation_s, max(fd + fw, qd + qw) + FRAME_END_MARGIN_S,
                         (post_observation_s + qd) / (frame_capacity - 2))
    divider = max(1, _cycles_up(minimum_period, input_frequency_hz))
    if divider > MAX_PREDIVIDER:
        raise TimingError("Requested continuous capture cannot fit the T660 32-bit frame predivider at this input rate")
    period = divider / input_frequency_hz
    event_offset = period + qd
    # Include full post-pump support before the all-OFF terminal begins.
    recovery_frames = max(0, _cycles_up(post_observation_s + qd, 1.0 / period) - 1)
    nframes = 3 + recovery_frames
    if nframes > frame_capacity:
        # Decimal calculations avoid normal off-by-one rounding, and the bound
        # remains authoritative in case a supplied rate is itself imprecise.
        raise TimingError("Continuous record exceeds finite table capacity; increase the selected pre-pump interval")
    off_width = quantize_seconds(max(edge_quantum_s, min(fw, qw)), edge_quantum_s)
    off = {ch: {"enabled": False, "delay": "0.00000000000s", "width": _command(off_width),
                "polarity": "negative" if ch == "C" else "positive", "termination": termination} for ch in "ABCD"}
    table = []
    for i in range(nframes):
        channels = deepcopy(off)
        kind = "probe_only_baseline" if i == 0 else "terminal_all_off" if i == nframes - 1 else "recovery"
        if i == 1:
            kind = "pump_event" if pump_enabled else "no_pump_control"
            channels["A"] = {"enabled": pump_enabled, "delay": _command(fd), "width": _command(fw),
                             "polarity": fire_polarity, "termination": termination}
            channels["B"] = {"enabled": pump_enabled, "delay": _command(qd), "width": _command(qw),
                             "polarity": q_switch_polarity, "termination": termination}
        table.append({"index": i, "kind": kind, "offset_s": i * period, "duration_s": period,
                      "channels": channels, "train_count": 0, "train_spacing_s": 0.0,
                      "frame_repetitions": 1, "inert_terminator": i == nframes - 1})
    duration = nframes * period
    return TimingProgram(tuple(table), divider, input_frequency_hz, period, int(pump_enabled),
                         (event_offset,) if pump_enabled else (), duration, event_offset,
                         duration - event_offset, pre_observation_s, post_observation_s)
