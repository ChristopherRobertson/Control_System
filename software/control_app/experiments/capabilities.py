"""Allow-listed device capabilities and fixed physical routing facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Capability:
    name: str
    phase: str
    limits: dict[str, Any] | None = None
    available: bool = True
    reason: str | None = None


class CapabilityRegistry:
    def __init__(self) -> None:
        self._devices: dict[str, dict[str, Capability]] = {}

    def register(self, device: str, *capabilities: Capability) -> None:
        if device in self._devices:
            raise ValueError(f"Capabilities already registered for {device}")
        self._devices[device] = {item.name: item for item in capabilities}

    def devices(self) -> tuple[str, ...]:
        return tuple(self._devices)

    def get(self, device: str, capability: str) -> Capability | None:
        return self._devices.get(device, {}).get(capability)

    def require(self, device: str, capability: str) -> Capability:
        item = self.get(device, capability)
        if item is None:
            raise KeyError(f"{device}.{capability} is not allow-listed")
        if not item.available:
            raise ValueError(f"{device}.{capability} is unavailable: {item.reason}")
        return item


def default_capability_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register(
        "mircat",
        Capability("sdk_ownership", "configure"), Capability("qcl_selection", "configure", {"minimum": 1}),
        Capability("wavenumber_cm1", "configure", {"minimum": 900.0, "maximum": 1800.0}),
        Capability("scan_start_cm1", "configure", {"minimum": 900.0, "maximum": 1800.0}),
        Capability("scan_stop_cm1", "configure", {"minimum": 900.0, "maximum": 1800.0}),
        Capability("scan_rate_cm1_s", "configure", {"exclusive_minimum": 0.0}),
        Capability("repetitions", "configure", {"minimum": 1}), Capability("pulse_rate_hz", "configure", {"exclusive_minimum": 0.0}),
        Capability("pulse_width_ns", "configure", {"exclusive_minimum": 0.0}), Capability("current_ma", "configure", {"exclusive_minimum": 0.0}),
        Capability("pulse_trigger_mode", "configure"), Capability("process_trigger_mode", "configure"),
        Capability("wavelength_trigger_start_cm1", "configure"), Capability("wavelength_trigger_stop_cm1", "configure"),
        Capability("wavelength_trigger_interval_cm1", "configure", {"exclusive_minimum": 0.0}),
        Capability("wavelength_trigger_pulse_width_ns", "configure", {"exclusive_minimum": 0.0}),
        Capability("arm", "arm"), Capability("emission", "arm"), Capability("normal_sweep_start", "run"),
        Capability("stop", "stop"), Capability("disarm", "cleanup"), Capability("deinitialize", "cleanup"),
        Capability("tuning_readback", "verify"), Capability("pulse_limits_readback", "verify"),
        Capability("external_process_trigger", "configure", available=False, reason="The generic builder has no qualified frame/process execution adapter"),
    )
    registry.register(
        "hf2li",
        *(Capability(name, phase) for name, phase in (
            ("preset_selection", "configure"), ("signal_input_settings", "configure"),
            ("pll_external_reference", "configure"), ("demodulator_roles", "configure"),
            ("sample_rate_hz", "configure"), ("time_constant_s", "configure"),
            ("sample_stream", "acquire"), ("reference_stream", "acquire"),
            ("dio_timing_stream", "acquire"), ("complete_dio_word", "acquire"),
            ("continuous_acquisition", "acquire"), ("readback_verification", "verify"),
            ("stop", "stop"), ("disconnect", "cleanup"),
        )),
        Capability("mircat_db9_dio_mapping", "configure"),
    )
    registry.register("t660_1", *(
        Capability(name, phase) for name, phase in (
            ("channel_a_hf2li_extref", "configure"), ("channel_b_mircat_trigger", "configure"),
            ("channel_c_t660_2_trigger", "configure"),
            ("program_timing", "configure"), ("start", "run"), ("stop", "stop"), ("safe_idle", "cleanup"),
        )
    ))
    registry.register("t660_2", *(
        Capability(name, phase) for name, phase in (
            ("channel_a_ndyag_fire", "configure"), ("channel_b_ndyag_q_switch", "configure"),
            ("program_timing", "configure"), ("start", "run"), ("stop", "stop"), ("safe_idle", "cleanup"),
        )
    ), Capability("channel_c_mircat_process_trigger", "configure", available=False, reason="The generic builder has no qualified frame/process execution adapter"))
    registry.register("ndyag", Capability("timing", "configure"), Capability("fire", "run"), Capability("stop", "stop"), Capability("safe_idle", "cleanup"))
    registry.register("picoscope", Capability("capture_settings", "configure"), Capability("arm", "arm"), Capability("capture", "acquire"), Capability("stop", "stop"), Capability("close", "cleanup"))
    return registry


PROHIBITED_ROUTES = {
    "mircat.db9_pin_5", "mircat.db9_pin_6", "mircat.db9_pin_8", "t660_1.channel_d", "t660_2.channel_d"
}
