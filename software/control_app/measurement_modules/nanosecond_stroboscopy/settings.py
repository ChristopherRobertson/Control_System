"""Requested inputs and automatic hardware-readback resolution.

Metadata and scientific calibrations annotate interpretation; they do not gate
raw acquisition. Only explicitly overridden values cease to follow Auto.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from typing import Any, Mapping

EXPERIMENT_ID = "nanosecond_stroboscopy"
SCHEMA_VERSION = "1.0"
KERNEL_ID = "sparse_dc_complex_probe_area_v2"
PROFILES = {
    "RT-HRP-G": {"architecture_id": "ARC-RT-HRP-NS", "protein": "HRP", "cryogenic": False, "populations": ("CO-1", "CO-2")},
    "RT-Mb-G": {"architecture_id": "ARC-RT-MB-NS", "protein": "MbCO", "cryogenic": False, "populations": ("A1",)},
    "77K-HRP-G-F": {"architecture_id": "ARC-77-HRP-NS", "protein": "HRP", "cryogenic": True, "populations": ("CO-1", "CO-2")},
    "77K-Mb-G-F": {"architecture_id": "ARC-77-MB-NSUS", "protein": "MbCO", "cryogenic": True, "populations": ("A0", "A1", "A3")},
}


@dataclass(frozen=True)
class Settings:
    experiment_id: str = EXPERIMENT_ID
    schema_version: str = SCHEMA_VERSION
    mode: str = "single"
    execution_mode: str = "connected"
    profile_id: str = ""
    illustrative_only: bool = False
    value_source: str = "Requested inputs and connected device readbacks"
    wavenumbers_cm1: tuple[float, ...] = (1940.0, 1942.0, 1944.0)
    delays_ns: tuple[float, ...] = (-300.0, -150.0, -60.0, -20.0, 0.0, 20.0, 50.0, 100.0, 200.0, 400.0, 800.0, 1600.0, 4000.0)
    repetitions: int = 3
    cycle_interval_s: float = 1.0
    overrides: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    conditions: tuple[str, ...] = ("pump_on", "pump_blocked")
    ordering: str = "counterbalanced"
    random_seed: int = 271828
    selected_populations: tuple[str, ...] = ("A1",)
    quantified_populations: tuple[str, ...] = ()
    sample_selection_id: str = ""
    sample_id: str = ""
    condition_id: str = ""
    preparation_id: str = ""
    cell_id: str = ""
    matrix_id: str = ""
    day_id: str = ""
    position_ids: tuple[str, ...] = ()
    temperature_k: float | None = None
    temperature_uncertainty_k: float | None = None
    temperature_record_id: str = ""
    reset_method: str = "spectral_recovery"
    reset_equivalent: bool = False
    reset_record_id: str = ""
    reset_interval_s: float = 1.0
    probe_period_s: float | None = None
    probe_anchor_ns: float | None = None
    fire_to_q_ns: float | None = None
    pump_command_width_ns: float | None = None
    probe_command_width_ns: float | None = None
    timing_step_ns: float | None = None
    optical_delay_offset_ns: float | None = None
    fire_command_width_ns: float | None = None
    q_command_width_ns: float | None = None
    reference_command_width_ns: float | None = None
    event_trigger_width_ns: float | None = None
    warmup_frames: int | None = None
    filter_tail_frames: int | None = None
    irf_sigma_ns: float | None = None
    timing_jitter_ns: float | None = None
    integration_aperture_ns: float | None = None
    filter_blur_ns: float = 0.0
    filter_time_constant_s: float | None = None
    filter_order: int | None = None
    hf2li_rate_hz: float | None = None
    reference_filter_time_constant_s: float | None = None
    reference_filter_order: int | None = None
    reference_hf2li_rate_hz: float | None = None
    demodulator_sample: int = 0
    demodulator_reference: int = 3
    noise_sd: float = 0.0001
    expected_amplitude: float = -0.01
    candidate_lifetime_ns: float = 250.0
    time_zero_ns: float = 0.0
    drift_per_event: float = 0.0
    reset_residual_fraction: float = 0.0
    off_band_wavenumbers_cm1: tuple[float, ...] = ()
    control_records: dict[str, str] = field(default_factory=dict)
    control_applicability: dict[str, str] = field(default_factory=dict)
    calibration_ids: tuple[str, ...] = ()
    qualification: dict[str, Any] = field(default_factory=dict)
    confirmatory: bool = False
    preparation_estimate_s: float = 30.0
    tune_settle_estimate_s: float = 3.0
    upload_frame_estimate_s: float = 0.2
    processing_estimate_s: float = 3.0
    restoration_estimate_s: float = 3.0
    preliminary_event_count: int = 3
    blank_event_count: int = 3
    max_pump_events: int = 10000
    max_storage_bytes: int = 1000000000
    max_frame_capacity: int = 8192

    @property
    def instance_id(self) -> str:
        return f"{EXPERIMENT_ID}:{self.mode}"

    @property
    def architecture_id(self) -> str:
        return PROFILES.get(self.profile_id, {}).get("architecture_id", "unknown")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | "Settings") -> "Settings":
        if isinstance(value, cls):
            return value
        values = dict(value)
        known = {f.name for f in fields(cls)}
        unknown = set(values) - known
        if unknown:
            raise ValueError(f"Unknown nanosecond settings fields: {', '.join(sorted(unknown))}")
        for name in ("wavenumbers_cm1", "delays_ns", "conditions", "selected_populations", "quantified_populations", "position_ids", "off_band_wavenumbers_cm1", "calibration_ids"):
            if name in values:
                values[name] = tuple(values[name])
        for name in ("qualification", "control_records", "control_applicability", "overrides", "metadata"):
            if name in values:
                values[name] = dict(values[name])
        return cls(**values)

    def kernel(self) -> dict[str, Any]:
        import math
        tau, period = self.filter_time_constant_s, self.probe_period_s
        order = self.filter_order or 1
        x = period / tau if tau and period else 0.0
        memory = math.exp(-x) * sum(x ** k / math.factorial(k) for k in range(max(1, min(order, 8)))) if x < 700 else 0.0
        return {"kernel_id": KERNEL_ID, "irf_sigma_ns": self.irf_sigma_ns or 0.0,
                "timing_jitter_ns": self.timing_jitter_ns or 0.0,
                "integration_aperture_ns": self.integration_aperture_ns or 0.0,
                "filter_blur_ns": self.filter_blur_ns,
                "filter_time_constant_s": tau, "filter_order": order,
                "filter_memory_fraction": min(1.0, max(0.0, memory)),
                "time_zero_ns": self.time_zero_ns,
                "reset_equivalent": self.reset_equivalent or self.execution_mode == "simulation" and self.reset_residual_fraction == 0,
                "irf_qualified": (self.irf_sigma_ns is not None and self.optical_delay_offset_ns is not None) or self.execution_mode == "simulation",
                "value_source": self.value_source}


def default_settings(mode: str = "single") -> Settings:
    return Settings(mode=mode)


NanosecondSettings = Settings


ADVANCED_FIELDS = (
    "probe_period_s", "probe_anchor_ns", "fire_to_q_ns",
    "fire_command_width_ns", "q_command_width_ns", "probe_command_width_ns",
    "event_trigger_width_ns", "timing_step_ns",
    "warmup_frames", "filter_tail_frames", "filter_time_constant_s", "filter_order",
    "hf2li_rate_hz",
    "reference_filter_time_constant_s", "reference_filter_order", "reference_hf2li_rate_hz",
)
INTEGER_ADVANCED_FIELDS = {"warmup_frames", "filter_tail_frames", "filter_order", "reference_filter_order", "demodulator_sample", "demodulator_reference"}


@dataclass(frozen=True)
class Resolution:
    settings: Settings
    sources: dict[str, str]
    unresolved: tuple[str, ...]
    errors: tuple[str, ...]


def resolve_settings(settings: Settings | Mapping[str, Any], capabilities: Mapping[str, Any] | None = None) -> Resolution:
    """Resolve Auto afresh without changing requested settings or their overrides.

    Capabilities are flat live readbacks supplied by the owned device lifecycle.
    Absent numeric readbacks defer timing compilation until preparation; they do
    not invent an operating recipe or prevent the operator from pressing Start.
    """
    import math
    s = Settings.from_dict(settings)
    caps = dict(capabilities or {})
    sources = {"reset_interval_s": "No additional software reset wait; selected hardware cycles provide event spacing"}
    values, errors = {"reset_interval_s": 0.0}, []
    examples = {"fire_to_q_ns": 200000.0, "pump_command_width_ns": 1000.0,
                "probe_command_width_ns": 100.0, "filter_time_constant_s": .05,
                "filter_order": 1, "hf2li_rate_hz": 200.0}
    if s.execution_mode == "simulation":
        for name, value in examples.items():
            caps.setdefault(name, value)
    for name in s.overrides:
        if name not in ADVANCED_FIELDS:
            errors.append(f"Unsupported advanced override: {name}")
    def select(name, automatic=None, source="Derived automatically"):
        override = s.overrides.get(name)
        if override is not None and override != "Auto":
            if isinstance(override, bool) or not isinstance(override, (int, float)) or not math.isfinite(override):
                errors.append(f"{name} override must be a finite number or Auto")
                value = None
            elif name in INTEGER_ADVANCED_FIELDS and int(override) != override:
                errors.append(f"{name} override must be an integer or Auto")
                value = None
            else:
                value = int(override) if name in INTEGER_ADVANCED_FIELDS else float(override)
            sources[name] = "Explicit override"
        else:
            value = automatic
            sources[name] = source if value is not None else "Read during connected preparation"
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                errors.append(f"Live/automatic {name} must be a finite number")
                value = None
            elif value is not None and name in INTEGER_ADVANCED_FIELDS:
                if int(value) != value:
                    errors.append(f"Live/automatic {name} must be an integer")
                    value = None
                else:
                    value = int(value)
        values[name] = value
        return value
    for name in ("fire_to_q_ns", "pump_command_width_ns", "probe_command_width_ns", "filter_time_constant_s", "filter_order", "hf2li_rate_hz"):
        select(name, caps.get(name), "Live device readback" if capabilities and name in capabilities else "EXAMPLE ONLY simulator value")
    for name, sample_name in (("reference_filter_time_constant_s", "filter_time_constant_s"), ("reference_filter_order", "filter_order"), ("reference_hf2li_rate_hz", "hf2li_rate_hz")):
        fallback = values[sample_name] if s.execution_mode == "simulation" else None
        select(name, caps.get(name, fallback), "Independent reference device readback" if capabilities else "EXAMPLE ONLY simulator value")
    for tc_name, rate_name in (("filter_time_constant_s", "hf2li_rate_hz"), ("reference_filter_time_constant_s", "reference_hf2li_rate_hz")):
        tc, rate = values[tc_name], values[rate_name]
        if tc is not None and rate is not None and tc > 0 and rate > 0 and s.overrides.get(tc_name) in (None, "Auto"):
            values[tc_name] = max(tc, 4 / rate)
            sources[tc_name] = "Auto: max(live time constant, 4 / selected export rate) for sampled pulse-area support"
    for name in ("fire_command_width_ns", "q_command_width_ns"):
        select(name, caps.get(name, values["pump_command_width_ns"]), "Live device pulse width")
    for name in ("reference_command_width_ns", "event_trigger_width_ns"):
        select(name, caps.get(name, values["probe_command_width_ns"]), "Live device pulse width")
    select("timing_step_ns", .01, "T660 documented 10 ps electrical command grid")
    values["demodulator_sample"], values["demodulator_reference"] = 0, 3
    sources["demodulator_sample"] = "Installed sample Signal 1 / demodulator 0"
    sources["demodulator_reference"] = "Installed reference Signal 2 / demodulator 3"
    tau, order = values["filter_time_constant_s"], values["filter_order"]
    # A separated lowpass impulse must fit before the following probe. This
    # depends on the actual filter, not a assumed molecular reset or lifetime.
    support = 16 * order * tau if isinstance(tau, (int, float)) and isinstance(order, (int, float)) and tau > 0 and order > 0 else None
    if s.mode == "dual":
        rtau, rorder = values["reference_filter_time_constant_s"], values["reference_filter_order"]
        reference_support = 16 * rorder * rtau if isinstance(rtau, (int, float)) and isinstance(rorder, (int, float)) and rtau > 0 and rorder > 0 else None
        support = max(support, reference_support) if support is not None and reference_support is not None else None
    period = max(s.cycle_interval_s, support) if support is not None and isinstance(s.cycle_interval_s, (int, float)) else None
    select("probe_period_s", period, "Max(requested cycle, 16 × live filter order × time constant)")
    width_values = [values[n] for n in ("fire_command_width_ns", "q_command_width_ns", "probe_command_width_ns", "event_trigger_width_ns")]
    anchor = None
    if values["fire_to_q_ns"] is not None and all(v is not None for v in width_values) and s.delays_ns:
        anchor = values["fire_to_q_ns"] + max(0.0, max(s.delays_ns)) + max(width_values) + 1000.0
    select("probe_anchor_ns", anchor, "Live FIRE-to-Q + largest requested delay + command width + 1 µs frame guard")
    select("warmup_frames", 1, "One complete probe-only baseline cycle")
    select("filter_tail_frames", 1, "One complete retained post-event cycle")
    required = ("probe_period_s", "probe_anchor_ns", "fire_to_q_ns", "fire_command_width_ns", "q_command_width_ns", "probe_command_width_ns", "reference_command_width_ns", "event_trigger_width_ns", "filter_time_constant_s", "filter_order", "hf2li_rate_hz")
    if s.mode == "dual":
        required += ("reference_filter_time_constant_s", "reference_filter_order", "reference_hf2li_rate_hz")
    unresolved = tuple(name for name in required if values.get(name) is None)
    for name, value in values.items():
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
            errors.append(f"Live/selected {name} is not a finite numeric value")
    if values["pump_command_width_ns"] is None:
        values["pump_command_width_ns"] = values["fire_command_width_ns"]
    if s.execution_mode == "simulation":
        values.update(irf_sigma_ns=s.irf_sigma_ns if s.irf_sigma_ns is not None else 12.0,
                      timing_jitter_ns=s.timing_jitter_ns if s.timing_jitter_ns is not None else 3.0,
                      integration_aperture_ns=s.integration_aperture_ns if s.integration_aperture_ns is not None else 20.0,
                      value_source="EXAMPLE ONLY simulator values")
    return Resolution(replace(s, **values), sources, unresolved, tuple(errors))
