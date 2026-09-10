"""Pure, explicitly unit-bearing inputs for microsecond stroboscopy.

The bundled values are EXAMPLE ONLY, useful for planning and simulation.  Neither
constructing settings nor accepting a sample spectrum qualifies an instrument.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
import math
from typing import Any, Mapping

EXPERIMENT_ID = "microsecond_stroboscopy"
SETTINGS_VERSION = 1


@dataclass(frozen=True)
class ConditionProfile:
    profile_id: str
    architecture_id: str
    title: str
    nominal_temperature_k: float | None
    reset_equivalence_required: bool = True
    branch: str = "microsecond"


CONDITION_PROFILES = {
    "RT-Mb-R-K": ConditionProfile("RT-Mb-R-K", "ARC-RT-MB-US", "Room-temperature MbCO", None),
    "77K-Mb-G-F": ConditionProfile("77K-Mb-G-F", "ARC-77-MB-NSUS", "Cryogenic MbCO fast program — microsecond branch", 77.0),
}


@dataclass(frozen=True)
class SpectralPoint:
    wavenumber_cm1: float
    label: str = "local window"
    role: str = "band"  # band, off_band


@dataclass(frozen=True)
class SettingSelection:
    path: str
    requested: float | int
    selected: float | int
    basis: str


@dataclass(frozen=True)
class SampleIdentity:
    sample_id: str = "EXAMPLE-SAMPLE"
    preparation_id: str = "EXAMPLE-PREPARATION"
    cell_id: str = "EXAMPLE-CELL"
    position_id: str = "EXAMPLE-POSITION"
    condition_id: str = "EXAMPLE-CONDITION"
    temperature_record_id: str = ""
    measured_temperature_k: float | None = None
    temperature_uncertainty_k: float | None = None
    matrix_id: str = ""
    thermal_history_id: str = ""
    sample_selection_id: str = ""


@dataclass(frozen=True)
class ResponseSettings:
    hf2_order: int = 1
    hf2_time_constant_s: float = 8e-6
    sample_rate_sps: float = 115_000.0
    reference_rate_sps: float = 115_000.0
    reference_order: int = 1
    reference_time_constant_s: float = 8e-6
    detector_latency_s: float = 0.0
    reference_latency_s: float = 0.0
    integration_aperture_s: float = 25e-6
    jitter_s: float = 1e-6
    time_zero_s: float = 0.0
    reference_alignment_uncertainty_s: float = 0.0
    timing_rate_sps: float = 230_000.0
    sample_demodulator: int = 0
    reference_demodulator: int = 3
    timing_demodulator: int = 2
    qualified: bool = False
    qualification_id: str = ""

    @property
    def effective_sigma_s(self) -> float:
        """RMS kernel width; systematic offsets remain separate from width."""
        return math.sqrt(self.hf2_order * self.hf2_time_constant_s**2
                         + self.integration_aperture_s**2 / 12
                         + self.jitter_s**2 + (1 / self.sample_rate_sps)**2 / 12)


@dataclass(frozen=True)
class TimingSettings:
    probe_rate_hz: float = 1_000_000.0
    probe_width_ns: float = 100.0
    reference_width_ns: float = 100.0
    frame_input_width_ns: float = 100.0
    probe_delay_ns: float = 0.0
    # Frame spacing inside a ONE-pump block, not biological repetition cadence.
    # Recovery and equivalent-state verification are independently budgeted.
    event_interval_s: float = 0.01
    fire_to_q_us: float = 200.0
    fire_width_us: float = 10.0
    q_switch_width_us: float = 10.0
    command_guard_us: float = 100.0
    timing_quantum_ns: float = 0.01  # T660 Manual F5 pp. 5–6: 10 ps
    clock_frequency_quantum_hz: float = 0.02  # DDS command resolution, Manual p. 10
    maximum_probe_duty_fraction: float = 0.30
    maximum_pump_rate_hz: float = 10.0
    frame_capacity: int = 8192
    timing_marker_dio_bit: int = 17


@dataclass(frozen=True)
class ResetSettings:
    method: str = "passive_recovery"
    recovery_wait_s: float = 1.0
    verification_duration_s: float = 0.05
    tolerance_fraction: float = 0.02
    equivalence_record_id: str = ""
    equivalent_state_verified: bool = False
    qualification_id: str = ""
    maximum_wait_s: float = 60.0


@dataclass(frozen=True)
class ControlSettings:
    baseline_duration_s: float = 0.05
    preliminary_duration_s: float = 0.05
    pump_blocked_averages: int = 1
    dark_record_id: str = ""
    artifact_record_ids: tuple[str, ...] = ()
    blank_record_id: str = ""
    background_record_id: str = ""
    physical_action_allowance_s: float = 0.0
    require_dark: bool = True


@dataclass(frozen=True)
class BudgetSettings:
    tuning_estimate_s_per_wavenumber: float = 2.0
    detector_settling_s_per_wavenumber: float = 0.05
    configuration_estimate_s: float = 3.0
    upload_seconds_per_frame: float = 0.08
    acquisition_guard_s_per_block: float = 0.04  # retained 20 ms pre-subscribe + 20 ms final drain
    retrieval_bytes_per_second: float = 2_000_000.0
    restoration_estimate_s: float = 3.0
    save_bytes_per_second: float = 20_000_000.0
    analysis_estimate_s: float = 2.0
    bytes_per_native_sample: int = 96  # retained raw polls plus assembled native streams
    maximum_memory_bytes: int = 2 * 1024**3
    maximum_storage_bytes: int = 20 * 1024**3


@dataclass(frozen=True)
class StroboscopySettings:
    mode: str = "single"
    condition_profile_id: str = "RT-Mb-R-K"
    spectral_points: tuple[SpectralPoint, ...] = field(default_factory=lambda: (
        SpectralPoint(1940.0, "EXAMPLE lower off-band", "off_band"),
        SpectralPoint(1944.0, "EXAMPLE local band"),
        SpectralPoint(1945.0, "EXAMPLE local band"),
        SpectralPoint(1946.0, "EXAMPLE local band"),
        SpectralPoint(1950.0, "EXAMPLE upper off-band", "off_band"),
    ))
    delays_us: tuple[float, ...] = (-100.0, 0.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0)
    averages: int = 2
    response: ResponseSettings = field(default_factory=ResponseSettings)
    timing: TimingSettings = field(default_factory=TimingSettings)
    identity: SampleIdentity = field(default_factory=SampleIdentity)
    reset: ResetSettings = field(default_factory=ResetSettings)
    controls: ControlSettings = field(default_factory=ControlSettings)
    budget: BudgetSettings = field(default_factory=BudgetSettings)
    delay_order: str = "alternating"  # ascending, descending, alternating
    execution_mode: str = "simulation"
    operating_basis: str = "EXAMPLE ONLY — offline planning; no promoted operating settings"
    promoted_bundle_ids: tuple[str, ...] = ()
    calibration_ids: tuple[str, ...] = ()
    value_selections: tuple[SettingSelection, ...] = ()
    settings_version: int = SETTINGS_VERSION
    experiment_id: str = EXPERIMENT_ID

    @property
    def instance_id(self) -> str:
        return f"{EXPERIMENT_ID}:{self.mode}"

    @property
    def condition_profile(self) -> ConditionProfile:
        return CONDITION_PROFILES[self.condition_profile_id]

    @property
    def architecture_id(self) -> str:
        return self.condition_profile.architecture_id

    def to_dict(self) -> dict[str, Any]:
        # JSON-compatible lists, detached on every call, no mutable sessions.
        import json
        return json.loads(json.dumps(asdict(self), allow_nan=False))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "StroboscopySettings":
        data = dict(value)
        permitted = {item.name for item in fields(cls)}
        unknown = set(data) - permitted
        if unknown:
            raise ValueError(f"Unknown stroboscopy settings: {', '.join(sorted(unknown))}")
        for name, model in (("response", ResponseSettings), ("timing", TimingSettings),
                            ("identity", SampleIdentity), ("reset", ResetSettings),
                            ("controls", ControlSettings), ("budget", BudgetSettings)):
            if name in data and not isinstance(data[name], model):
                nested = dict(data[name])
                if name == "controls" and "artifact_record_ids" in nested:
                    nested["artifact_record_ids"] = tuple(nested["artifact_record_ids"])
                data[name] = model(**nested)
        if "spectral_points" in data:
            data["spectral_points"] = tuple(p if isinstance(p, SpectralPoint) else SpectralPoint(**p)
                                             for p in data["spectral_points"])
        if "value_selections" in data:
            data["value_selections"] = tuple(p if isinstance(p, SettingSelection) else SettingSelection(**p)
                                              for p in data["value_selections"])
        for name in ("delays_us", "promoted_bundle_ids", "calibration_ids"):
            if name in data:
                data[name] = tuple(data[name])
        return cls(**data)


def default_settings(mode: str = "single") -> StroboscopySettings:
    if mode not in ("single", "dual"):
        raise ValueError("Detector mode must be single or dual")
    return StroboscopySettings(mode=mode)


def local_spectral_window(lower_cm1: float, upper_cm1: float, step_cm1: float,
                          *, label: str = "measured local band", role: str = "band") -> tuple[SpectralPoint, ...]:
    if not all(math.isfinite(v) for v in (lower_cm1, upper_cm1, step_cm1)) or not 0 < step_cm1 <= upper_cm1 - lower_cm1:
        raise ValueError("A local window needs finite ordered limits and a positive step")
    count = int(math.floor((upper_cm1 - lower_cm1) / step_cm1))
    if count > 100_000:
        raise ValueError("Local spectral window exceeds 100000 points")
    values = [lower_cm1 + i * step_cm1 for i in range(count + 1)]
    if not math.isclose(values[-1], upper_cm1, abs_tol=1e-9):
        values.append(upper_cm1)
    return tuple(SpectralPoint(v, label, role) for v in values)


def information_delay_grid(*, response_width_us: float, recovery_limit_us: float,
                           early_points: int = 9, later_points: int = 12,
                           negative_points: int = 2) -> tuple[float, ...]:
    """IRF-sized prompt grid followed by log coverage; never forces lifetimes."""
    if not math.isfinite(response_width_us) or not math.isfinite(recovery_limit_us) or not 0 < response_width_us < recovery_limit_us:
        raise ValueError("Require 0 < response width < observation limit in microseconds")
    if early_points < 2 or later_points < 2 or negative_points < 0:
        raise ValueError("Need at least two early and later points and nonnegative negative points")
    end_early = min(4 * response_width_us, recovery_limit_us / 2)
    negative = [-response_width_us * (i + 1) for i in range(negative_points)]
    early = [end_early * i / (early_points - 1) for i in range(early_points)]
    later = [end_early * (recovery_limit_us / end_early) ** (i / (later_points - 1)) for i in range(later_points)]
    return tuple(sorted(set(negative + early + later)))


def literature_coverage_example_us() -> dict[str, Any]:
    return {"label": "LITERATURE COVERAGE EXAMPLE ONLY; neither fixed fit rates nor operating values",
            "approximate_component_times_us": [185.0, 1000.0],
            "delays_us": list(information_delay_grid(response_width_us=25.0, recovery_limit_us=10000.0))}
