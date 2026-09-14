"""Pure finite process-frame compiler with permanently inhibited pump outputs.

T660-1 supplies the selected probe/reference clock and T660-2's external input.
T660-2 C generates active-low MIRcat process pulses. Hardware
dividers and frame fields define edges; host scheduling only separates explicitly
declared QCL/direction blocks. The existing service owns acknowledged pending-
field upload, cancellation and readback; this module does not duplicate it.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Any, Callable

from .planner import ScanBlock, SlowScanPlan


def quantize_seconds(requested_s: float, tick_s: float, maximum_s: float, *, allow_zero: bool = False) -> float:
    """Round to the documented device grid; report the selected value separately."""
    if not all(math.isfinite(value) for value in (requested_s, tick_s, maximum_s)) or tick_s <= 0 or maximum_s <= 0:
        raise ValueError("Timing quantization needs finite positive resolution and maximum delay")
    if requested_s < 0 or (requested_s == 0 and not allow_zero):
        raise ValueError("Timing value must be positive (or an explicitly allowed zero delay)")
    tick = Decimal(str(tick_s))
    result = float((Decimal(str(requested_s)) / tick).to_integral_value(rounding=ROUND_HALF_UP) * tick)
    if result > maximum_s or (result <= 0 and not allow_zero):
        raise ValueError("Timing value cannot be represented within the device range")
    return result


def _channel(*, enabled: bool, delay_s: float, width_s: float, polarity: str = "positive", termination: str = "50OHM") -> dict[str, Any]:
    return {"enabled": enabled, "delay": f"{delay_s:.12g}s", "width": f"{width_s:.12g}s",
            "polarity": polarity, "termination": termination}


@dataclass(frozen=True)
class TimingBlock:
    block: ScanBlock
    frames: tuple[dict[str, Any], ...]
    input_frequency_hz: float
    predivider: int
    physical_frame_count: int
    record_duration_s: float
    expected_process_events: int

    def upload_kwargs(self, *, progress: Callable[[int, int], None] | None = None,
                      cancel_check: Callable[[], None] | None = None) -> dict[str, Any]:
        """Exact ``T660Service.preload_frame_table`` arguments, detached per call."""
        return {"frames": deepcopy(list(self.frames)), "predivider": self.predivider,
                "input_frequency_hz": self.input_frequency_hz, "progress": progress, "cancel_check": cancel_check}

    def to_dict(self) -> dict[str, Any]:
        return {"block": self.block.to_dict(), "frames": deepcopy(list(self.frames)),
                "input_frequency_hz": self.input_frequency_hz, "predivider": self.predivider,
                "physical_frame_count": self.physical_frame_count, "record_duration_s": self.record_duration_s,
                "expected_process_events": self.expected_process_events}


@dataclass(frozen=True)
class CompiledTiming:
    blocks: tuple[TimingBlock, ...]
    probe_recipe: dict[str, Any]
    safe_idle_recipes: dict[str, dict[str, Any]]
    requested: dict[str, Any]
    selected: dict[str, Any]
    event_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": "1.0", "experiment_id": "steady_state_slow_scan",
                "blocks": [block.to_dict() for block in self.blocks], "probe_recipe": deepcopy(self.probe_recipe),
                "safe_idle_recipes": deepcopy(self.safe_idle_recipes), "requested": deepcopy(self.requested),
                "selected": deepcopy(self.selected), "event_counts": dict(self.event_counts),
                "electrical_event_counts": None, "optical_event_counts": None,
                "edge_authority": "programmed T660 fields, not independently observed electrical or optical arrival"}


def assert_pump_inhibited(timing: CompiledTiming) -> None:
    for block in timing.blocks:
        for frame in block.frames:
            if set(frame["channels"]) != set("ABCD"):
                raise ValueError("Every frame must explicitly define all four channels")
            if frame["channels"]["A"]["enabled"] or frame["channels"]["B"]["enabled"]:
                raise ValueError("Slow scan pump FIRE and Q-switch must remain OFF in every frame")
    for device, recipe in timing.safe_idle_recipes.items():
        if recipe["trigger_source"] != "OFF" or any(channel["enabled"] for channel in recipe["channels"].values()):
            raise ValueError(f"Unsafe cleanup recipe for {device}")


def compile_timing(plan: SlowScanPlan) -> CompiledTiming:
    """Compile only a complete finite schedule; no implicit splitting or I/O."""
    plan.require_ready(hardware=False)
    inp, values = plan.inputs, plan.selected
    tick, maximum = inp.t660_tick_s, inp.t660_maximum_delay_s
    if tick is None or maximum is None:
        raise ValueError("Resolve T660 time quantization before timing compilation")
    probe_rate = values.get("probe_rate_hz")
    if not isinstance(probe_rate, (int, float)) or not math.isfinite(probe_rate) or probe_rate <= 0:
        raise ValueError("Probe frequency is unresolved")
    for name in ("probe_width_s", "process_pulse_width_s", "planning_response_s"):
        if not isinstance(values.get(name), (int, float)) or not math.isfinite(values[name]) or values[name] <= 0:
            raise ValueError(f"Resolve {name} before timing compilation")
    probe_width = quantize_seconds(values["probe_width_s"], tick, maximum)
    process_width = quantize_seconds(values["process_pulse_width_s"], tick, maximum)
    if probe_width >= 1 / probe_rate:
        raise ValueError("Quantized probe width exceeds clock period")
    if not .001 <= process_width <= .100:
        raise ValueError("Quantized process width is outside manufacturer 1–100 ms limits")
    # Disabled channel timing remains legal and explicit. Its width has no
    # physical emitted pulse and is never presented as an observed event.
    inert_width = min(probe_width, process_width)
    disabled = {channel: _channel(enabled=False, delay_s=0., width_s=inert_width) for channel in "ABCD"}
    safe_idle_recipes = {
        device: {"stop_first": True, "trigger_source": "OFF", "force_eod": True,
                 "predivider": 1, "gate_mode": 0, "burst_enabled": False,
                 "channels": deepcopy(disabled), **({"frames_engine": "OFF"} if device == "t660_2" else {})}
        for device in ("t660_1", "t660_2")
    }
    probe_recipe = {"stop_first": True, "trigger_source": "OFF", "force_eod": True,
                    "predivider": 1, "gate_mode": 0, "burst_enabled": False,
                    "clock": {"frequency": f"{probe_rate:.12g}Hz", "shots": 0},
                    "channels": {channel: _channel(enabled=channel in "ABC", delay_s=0., width_s=probe_width)
                                 for channel in "ABCD"}}
    compiled: list[TimingBlock] = []
    delays: dict[str, float] = {}
    for block in plan.blocks:
        if block.direction != "reverse" or not block.start_cm1 > block.stop_cm1:
            raise ValueError("Slow scan requires a descending Start-to-End trajectory")
        if not isinstance(inp.t660_frame_capacity, int) or block.replicates + 1 > inp.t660_frame_capacity:
            raise ValueError("Declared continuous block exceeds verified physical frame memory")
        delay = quantize_seconds(block.settle_s, tick, maximum, allow_zero=True)
        delays[block.block_id] = delay
        if delay + process_width >= block.frame_period_s - 1e-6:
            raise ValueError("Process pulse must finish before the following hardware frame trigger")
        if delay + process_width + block.scan_duration_s + values["planning_response_s"] > block.frame_period_s + tick:
            raise ValueError("Quantized process event leaves insufficient complete-sweep/response support")
        frames = []
        for replicate in range(block.replicates):
            channels = deepcopy(disabled)
            # Negative polarity idles C high and generates the selected low
            # pulse on DB9 pin 4. A/B/D stay OFF, including during settling.
            channels["C"] = _channel(enabled=True, delay_s=delay, width_s=process_width, polarity="negative")
            frames.append({"frame_id": f"{block.block_id}:replicate-{replicate + 1}", "replicate": replicate + 1,
                           "direction": block.direction, "segment_id": block.segment_id,
                           "channels": channels, "commanded_pump_events": 0,
                           "commanded_process_events": 1})
        terminal_channels = deepcopy(frames[-1]["channels"])
        for channel in terminal_channels.values():
            channel["enabled"] = False
        frames.append({"frame_id": f"{block.block_id}:terminal", "inert_terminator": True,
                       "channels": terminal_channels, "commanded_pump_events": 0, "commanded_process_events": 0})
        physical_count = len(frames)
        compiled.append(TimingBlock(block, tuple(frames), probe_rate, block.frame_predivider, physical_count,
                                    physical_count * block.frame_period_s, block.replicates))
    result = CompiledTiming(tuple(compiled), probe_recipe, safe_idle_recipes,
                            {"probe_width_s": values["probe_width_s"], "process_pulse_width_s": values["process_pulse_width_s"]},
                            {"probe_width_s": probe_width, "process_pulse_width_s": process_width,
                             "process_delay_s_by_block": delays, "tick_s": tick,
                             "probe_frequency_hz": probe_rate, "probe_frequency_actual_hz": None},
                            {"pump_fire": 0, "pump_q_switch": 0, "process": sum(b.expected_process_events for b in compiled),
                             "physical_frames": sum(b.physical_frame_count for b in compiled), "declared_blocks": len(compiled)})
    assert_pump_inhibited(result)
    return result
