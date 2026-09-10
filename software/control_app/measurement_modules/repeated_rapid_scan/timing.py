"""Deterministic finite T660 schedules; timestamps remain acquisition evidence.

Each table contains *all* scan opportunities in one declared movie and a final
all-disabled terminal frame. A/B are enabled once only when an electrical pump
is authorized, C advances the MIRcat during scan frames, and D is explicitly
disabled. No software sleep creates a pulse edge.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .settings import RepeatedRapidScanSettings

T660_FRAME_CAPACITY = 8192
T660_EDGE_QUANTUM_S = 10e-12
T660_DDS_QUANTUM_HZ = 0.02
T660_SOURCE = "references/manuals/T660/Highland Technologies T660 Manual.pdf §§2, 3.5, 5.3-5.4"


def _decimal(value: float) -> Decimal:
    return Decimal(str(value))


def _quantize(value: float, quantum: float) -> float:
    return float((_decimal(value) / _decimal(quantum)).to_integral_value(rounding=ROUND_HALF_UP) * _decimal(quantum))


def _same(left: float, right: float, quantum: float) -> bool:
    # Absorb only machine representation noise; never a meaningful fraction of
    # a carrier cycle (which would silently accept unrequested phase changes).
    return abs(left - right) <= max(1e-15, min(1e-12, quantum * 1e-8))


def _time(value: float) -> str:
    return f"{value:.12g}s"


@dataclass(frozen=True)
class CompiledMovie:
    frames: tuple[dict[str, Any], ...]
    predivider: int
    input_frequency_hz: float
    requested_scan_period_s: float
    scan_period_s: float
    requested_phase_s: float
    selected_phase_s: float
    duration_s: float
    pump_command_s: float | None
    fire_command_s: float | None
    crossing_scan_index: int
    expected_scan_count: int
    physical_frame_count: int
    electrical_pump_count: int
    timing_quantum_s: float
    continuous_clock_recipe: dict[str, Any]
    source: str = T660_SOURCE
    timing_basis: str = "programmed T660 T0; observed native clocks required for reconstruction"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def command_count(self) -> int:
        """Pending-field commands + one acknowledged STORE per frame."""
        previous: dict[tuple[str, str], Any] = {}
        count = 0
        for frame in self.frames:
            pending = {(channel, field): value for channel, values in frame["channels"].items() for field, value in values.items()}
            count += sum(previous.get(key) != value for key, value in pending.items()) + 1
            previous = pending
        return count


def compile_movie(settings: RepeatedRapidScanSettings, phase_offset_s: float = 0.0, *,
                  pump_enabled: bool = True, direction: str = "forward") -> CompiledMovie:
    settings.validate()
    if direction not in ("forward", "reverse"):
        raise ValueError("direction must be forward or reverse")
    if not 0 <= phase_offset_s < settings.measured_scan_period_s:
        raise ValueError("phase must lie within one measured scan period")
    if not _same(settings.timing_quantum_s, T660_EDGE_QUANTUM_S, 1e-15):
        raise ValueError("installed T660 edge resolution is 10 ps; a different grid requires a supported device")
    frequency = _quantize(settings.probe_frequency_hz, T660_DDS_QUANTUM_HZ)
    if not _same(frequency, settings.probe_frequency_hz, T660_DDS_QUANTUM_HZ):
        raise ValueError("probe frequency must lie on the T660 0.02 Hz DDS grid")
    if not 0 < frequency <= 16e6:
        raise ValueError("probe frequency exceeds the T660 DDS range")
    if settings.probe_pulse_width_s + 62.5e-9 >= 1.0 / frequency:
        raise ValueError("probe width plus T660 EOD must fit the selected carrier period")
    divisor = int((_decimal(settings.measured_scan_period_s) * _decimal(frequency)).to_integral_value(rounding=ROUND_HALF_UP))
    if not 1 <= divisor <= 2**32 - 1:
        raise ValueError("scan period exceeds the T660 uint32 external predivider range")
    period = divisor / frequency
    if not settings.allow_period_quantization and not _same(period, settings.measured_scan_period_s, 1 / frequency):
        raise ValueError("scan period is not an integer number of carrier cycles; explicitly accept quantization or change the request")
    phase = _quantize(phase_offset_s, T660_EDGE_QUANTUM_S)
    if not settings.allow_phase_quantization and not _same(phase, phase_offset_s, T660_EDGE_QUANTUM_S):
        raise ValueError("phase is not on the 10 ps grid; explicitly accept quantization or change the request")
    if phase >= period:
        raise ValueError("selected phase rounds outside its scan opportunity")
    total = settings.pre_scans + 1 + settings.post_scans
    physical_count = total + 1
    if physical_count > T660_FRAME_CAPACITY:
        raise ValueError(f"uninterrupted movie needs {total} scan frames plus one terminal frame ({physical_count} total), exceeding {T660_FRAME_CAPACITY}; no splitting or scan slowing is allowed")
    widths = {"A": settings.fire_pulse_width_s, "B": settings.qswitch_pulse_width_s,
              "C": settings.process_pulse_width_s, "D": T660_EDGE_QUANTUM_S}
    for name, value in widths.items():
        if not _same(value, _quantize(value, T660_EDGE_QUANTUM_S), T660_EDGE_QUANTUM_S):
            raise ValueError(f"channel {name} width is not representable on the 10 ps grid")
    for name in ("fire_to_qswitch_s", "process_delay_s", "probe_pulse_width_s"):
        if not _same(getattr(settings, name), _quantize(getattr(settings, name), T660_EDGE_QUANTUM_S), T660_EDGE_QUANTUM_S):
            raise ValueError(f"{name} is not representable on the 10 ps grid")
    pump = float(_decimal(period) * settings.pre_scans + _decimal(phase)) if pump_enabled else None
    fire = float(_decimal(pump) - _decimal(settings.fire_to_qswitch_s)) if pump_enabled else None
    if fire is not None and fire < 0:
        raise ValueError("pre-scans do not accommodate the configured Fire to Q-switch interval")
    placements: dict[str, tuple[int, float]] = {}
    for channel, event_time in (("A", fire), ("B", pump)):
        if event_time is not None:
            # Decimal prevents an exact frame-boundary pulse slipping into the
            # preceding frame because of floating-point division.
            frame_index = int((_decimal(event_time) / _decimal(period)).to_integral_value(rounding="ROUND_FLOOR"))
            offset = _quantize(event_time - frame_index * period, T660_EDGE_QUANTUM_S)
            if abs(offset - period) < T660_EDGE_QUANTUM_S:
                frame_index += 1
                offset = 0.0
            placements[channel] = (frame_index, offset)
    frames = []
    for index in range(total):
        channels = {}
        for channel in "ABCD":
            placed = placements.get(channel)
            enabled = channel == "C" or (placed is not None and placed[0] == index)
            delay = settings.process_delay_s if channel == "C" else (placed[1] if enabled else 0.0)
            if delay + widths[channel] > 3600.0:
                raise ValueError(f"frame {index} channel {channel} exceeds the documented 3600 s edge range")
            # The maintained uploader validates disabled-channel widths too.
            if delay + widths[channel] >= period - 1e-6:
                raise ValueError(f"frame {index} channel {channel} edge/width does not finish before the next frame; change the explicit plan")
            channels[channel] = {"enabled": bool(enabled), "delay": _time(delay), "width": _time(widths[channel]),
                                 "polarity": "negative" if channel == "C" else "positive", "termination": "50OHM"}
        role = "pre_pump" if index < settings.pre_scans else "pump_crossing" if index == settings.pre_scans else "post_pump"
        frames.append({"scan_index": index, "role": role, "direction": direction,
                       "programmed_scan_start_s": float(_decimal(period) * index),
                       "programmed_frame_start_s": float(_decimal(period) * index), "channels": channels})
    terminal_channels = {channel: {**settings, "enabled": False, "delay": "0s"}
                         for channel, settings in frames[-1]["channels"].items()}
    frames.append({"scan_index": None, "role": "terminal_inhibit", "terminal_inhibit": True,
                   "direction": direction, "programmed_scan_start_s": None,
                   "programmed_frame_start_s": float(_decimal(period) * total),
                   "channels": terminal_channels})
    for channel in ("A", "B"):
        if sum(frame["channels"][channel]["enabled"] for frame in frames) != int(pump_enabled):
            raise ValueError("compiled movie must contain exactly one Fire and one Q-switch command per authorized event")
    clock = {"stop_first": True, "trigger_source": "OFF", "predivider": 1,
             "gate_mode": 0, "burst_enabled": False, "clock": {"frequency": f"{frequency:.12g}Hz", "shots": 0},
             "channels": {channel: {"enabled": channel != "D", "delay": "0s", "width": _time(settings.probe_pulse_width_s),
                                    "polarity": "positive", "termination": "50OHM"} for channel in "ABCD"}}
    return CompiledMovie(frames=tuple(frames), predivider=divisor, input_frequency_hz=frequency,
                         requested_scan_period_s=settings.measured_scan_period_s, scan_period_s=period,
                         requested_phase_s=phase_offset_s, selected_phase_s=phase,
                         duration_s=float(_decimal(period) * physical_count), pump_command_s=pump,
                         fire_command_s=fire, crossing_scan_index=settings.pre_scans,
                         expected_scan_count=total, physical_frame_count=physical_count,
                         electrical_pump_count=int(pump_enabled), timing_quantum_s=T660_EDGE_QUANTUM_S,
                         continuous_clock_recipe=clock)
