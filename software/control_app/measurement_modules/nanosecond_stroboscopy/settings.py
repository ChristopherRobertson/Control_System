"""Hardware-free scientific settings. Defaults are labelled simulator examples.

No profile supplies established instrument settings or historical kinetic truth.
Connected settings must be resolved against promoted instrument evidence/readbacks.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Mapping

EXPERIMENT_ID = "nanosecond_stroboscopy"
SCHEMA_VERSION = "1.0"
KERNEL_ID = "sparse_single_probe_demod_impulse"
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
    execution_mode: str = "simulation"
    profile_id: str = "RT-Mb-G"
    illustrative_only: bool = True
    value_source: str = "EXAMPLE ONLY: synthetic demonstration, not operating values"
    wavenumbers_cm1: tuple[float, ...] = (1940.0, 1942.0, 1944.0)
    delays_ns: tuple[float, ...] = (-300.0, -150.0, -60.0, -20.0, 0.0, 20.0, 50.0, 100.0, 200.0, 400.0, 800.0, 1600.0, 4000.0)
    repetitions: int = 3
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
    probe_period_s: float = 1.0
    probe_anchor_ns: float = 300000.0
    fire_to_q_ns: float = 200000.0
    pump_command_width_ns: float = 1000.0
    probe_command_width_ns: float = 100.0
    timing_step_ns: float = 0.01
    optical_delay_offset_ns: float | None = None
    warmup_frames: int = 2
    filter_tail_frames: int = 2
    irf_sigma_ns: float = 12.0
    timing_jitter_ns: float = 3.0
    integration_aperture_ns: float = 20.0
    filter_blur_ns: float = 0.0
    filter_time_constant_s: float = 0.05
    filter_order: int = 1
    hf2li_rate_hz: float = 200.0
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
        for name in ("qualification", "control_records", "control_applicability"):
            if name in values:
                values[name] = dict(values[name])
        return cls(**values)

    def kernel(self) -> dict[str, Any]:
        import math
        x = self.probe_period_s / self.filter_time_constant_s if self.filter_time_constant_s > 0 and self.probe_period_s > 0 else 0.0
        # Residual tail of an order-n cascaded lowpass (gamma impulse response).
        memory = math.exp(-x) * sum(x ** k / math.factorial(k) for k in range(max(1, min(self.filter_order, 8)))) if x < 700 else 0.0
        memory = min(1.0, max(0.0, memory))  # Roundoff at a completely retained tail is not negative bandwidth.
        return {"kernel_id": KERNEL_ID, "irf_sigma_ns": self.irf_sigma_ns,
                "timing_jitter_ns": self.timing_jitter_ns,
                "integration_aperture_ns": self.integration_aperture_ns,
                "filter_blur_ns": self.filter_blur_ns,
                "filter_time_constant_s": self.filter_time_constant_s,
                "filter_order": self.filter_order, "filter_memory_fraction": memory,
                "time_zero_ns": self.time_zero_ns,
                "reset_equivalent": self.reset_equivalent or self.execution_mode == "simulation" and self.reset_residual_fraction == 0,
                "irf_qualified": bool(self.qualification.get("irf_qualified")) or self.execution_mode == "simulation",
                "value_source": self.value_source}


def default_settings(mode: str = "single") -> Settings:
    return Settings(mode=mode)


NanosecondSettings = Settings
