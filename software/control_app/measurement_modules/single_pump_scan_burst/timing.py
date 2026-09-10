"""Deterministic T660 frame compiler; no device access and no host edge timers.

The installed host service stages every pending field once, then uploads only
changed fields with STORE acknowledgments. Its bounded frame API deliberately
uses train count zero, which still emits the first pulse of each enabled channel.
One frame per scan makes the unique pump and every later OFF state explicit.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from typing import Any, Mapping

from .settings import Capabilities, Settings


def quantize(value: float, quantum: float, *, ceiling: bool = False) -> float:
    q = Decimal(str(quantum))
    return float((Decimal(str(value)) / q).to_integral_value(
        rounding=ROUND_CEILING if ceiling else ROUND_HALF_UP) * q)


@dataclass(frozen=True)
class BurstBlock:
    block_id: str
    kind: str
    planned_elapsed_s: float
    scan_count: int
    duration_s: float
    pump_enabled: bool
    frames: tuple[dict[str, Any], ...]
    predivider: int
    frame_period_s: float
    first_process_delay_s: float
    scan_duration_s: float
    requested_elapsed_s: float
    timing_basis: str = "observed HF2LI native timestamps relative to retained pump observation; optical offset separate when available"
    temperature_checks: tuple[str, ...] = ()
    idle_state_after: str = "probe output disabled; reference and epoch retained; pump outputs disabled"

    @property
    def planned_end_s(self) -> float:
        return self.planned_elapsed_s + (self.scan_count - 1) * self.frame_period_s + self.scan_duration_s

    @property
    def physical_frame_count(self) -> int:
        return len(self.frames)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BurstBlock":
        values = dict(data)
        values["frames"] = tuple(dict(frame) for frame in values["frames"])
        values["temperature_checks"] = tuple(values.get("temperature_checks", ()))
        return cls(**values)


def compile_block(settings: Settings, capabilities: Capabilities, *, block_id: str,
                  kind: str, elapsed_s: float, scan_count: int, pump: bool,
                  selected: Mapping[str, float]) -> BurstBlock:
    """Compile one declared uninterrupted scan block, including inert padding."""
    if scan_count < 1 or scan_count + 1 > capabilities.frame_capacity:
        raise ValueError(f"{block_id}: {scan_count} scans plus terminal frame exceed the "
                         f"{capabilities.frame_capacity}-frame capacity; continuous blocks cannot be silently split")
    frequency = selected["probe_rate_hz"]
    period = selected["scan_interval_s"]
    divider = int(round(period * frequency))
    if not 1 <= divider <= capabilities.predivider_max:
        raise ValueError(f"{block_id}: frame predivider exceeds installed uint32 range")
    q_delay = selected["pump_fire_to_q_s"]
    # All scan frames have the same C offset, so their process edges remain on
    # one hardware grid even though only the first frame contains a pump.
    process_delay = q_delay + selected["first_scan_delay_s"]
    scan_duration = abs(settings.scan_stop_cm1 - settings.scan_start_cm1) / settings.scan_speed_cm1_s
    widths = (selected["pump_fire_width_s"], selected["pump_q_width_s"], selected["process_width_s"])

    def channel(delay: float, width: float, enabled: bool, polarity: str) -> dict[str, Any]:
        return {"enabled": enabled, "delay": f"{delay:.12f}s", "width": f"{width:.12f}s",
                "polarity": polarity, "termination": "50OHM"}

    table = []
    for index in range(scan_count + 1):
        terminal = index == scan_count
        pumped = pump and index == 0 and not terminal
        table.append({
            "frame_index": index,
            "kind": "terminal" if terminal else ("pump_and_scan" if pumped else "scan_only"),
            "scan_index": None if terminal else index,
            "train_count": 0, "train_spacing_s": capabilities.train_spacing_min_s,
            "frame_repetition": 1, "inert_terminator": terminal,
            "channels": {
                "A": channel(0.0, widths[0], pumped, settings.pump_polarity),
                "B": channel(q_delay, widths[1], pumped, settings.pump_polarity),
                "C": channel(process_delay, widths[2], not terminal, settings.process_polarity),
                "D": channel(0.0, capabilities.edge_quantum_s, False, "positive"),
            },
        })
    if process_delay + scan_duration >= period - capabilities.frame_guard_s:
        raise ValueError(f"{block_id}: scan duration and process offset do not fit the scan interval; "
                         "increase the interval or scan speed")
    for frame in table:
        for value in frame["channels"].values():
            delay = float(value["delay"][:-1])
            width = float(value["width"][:-1])
            if delay + width >= period - capabilities.frame_guard_s:
                raise ValueError(f"{block_id}: channel delay + width violates next-frame guard")
            if delay + width > capabilities.edge_max_s:
                raise ValueError(f"{block_id}: channel timing exceeds T660 edge range")
    return BurstBlock(block_id=block_id, kind=kind, planned_elapsed_s=elapsed_s,
        scan_count=scan_count, duration_s=(scan_count + 1) * period,
        pump_enabled=pump, frames=tuple(table), predivider=divider, frame_period_s=period,
        first_process_delay_s=process_delay, scan_duration_s=scan_duration,
        requested_elapsed_s=elapsed_s,
        idle_state_after=("probe remains at selected rate; exposure budget includes wait" if settings.probe_during_wait
                          else "probe B disabled; reference A retained; pump A/B disabled"))


def probe_clock_recipe(settings: Settings, selected: Mapping[str, float]) -> dict[str, Any]:
    """Generic installed A/B/C topology using selected values, never Phase Scan defaults."""
    width = selected["probe_pulse_width_s"]
    return {"stop_first": True, "trigger_source": "OFF", "predivider": 1,
        "gate_mode": 0, "burst_enabled": False,
        "clock": {"frequency": f"{selected['probe_rate_hz']:.12g}Hz", "shots": 0},
        "channels": {ch: {"enabled": ch != "D", "delay": f"{settings.probe_reference_delay_s if ch == 'B' else 0:.12f}s",
            "width": f"{width:.12f}s", "polarity": "positive", "termination": "50OHM"}
            for ch in "ABCD"}}
