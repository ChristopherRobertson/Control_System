"""Hardware-free, unit-bearing inputs for a single irreversible pump epoch.

Unset operating values are intentional: EXPERIMENTS.md supplies scientific
requirements, not qualified laser, timing or lock-in settings.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from copy import deepcopy
from typing import Any, Mapping

EXPERIMENT_ID = "single_pump_scan_burst"
SCHEMA_VERSION = 1
CONDITION_PROFILES = {
    "77K-HRP-G-S": {"protein": "HRP-CO", "architecture_id": "ARC-77-HRP-SPB",
                    "nominal_temperature_k": 77.0, "populations": ("sample-fitted HRP populations",)},
    "77K-Mb-G-S": {"protein": "MbCO", "architecture_id": "ARC-77-MB-SPB",
                   "nominal_temperature_k": 77.0, "populations": ("A0", "A1", "A3")},
}


@dataclass(frozen=True)
class Settings:
    mode: str = "single"
    condition_id: str = "77K-HRP-G-S"
    sample_id: str = ""
    preparation_id: str = ""
    accepted_state_id: str = ""
    matrix_id: str = ""
    cell_id: str = ""
    position_id: str = ""
    temperature_identity: str = ""
    thermal_history_id: str = ""
    measured_temperature_k: float | None = None
    temperature_uncertainty_k: float | None = None
    min_temperature_k: float | None = None
    max_temperature_k: float | None = None
    scan_start_cm1: float | None = None
    scan_stop_cm1: float | None = None
    scan_speed_cm1_s: float | None = None
    scan_interval_s: float | None = None
    first_scan_delay_s: float | None = None
    early_scan_count: int = 10
    later_burst_count: int = 8
    scans_per_burst: int = 3
    final_scan_count: int = 3
    first_later_burst_s: float | None = None
    observation_limit_s: float | None = None
    later_burst_times_s: tuple[float, ...] = ()
    schedule_kind: str = "logarithmic"
    preliminary_scan_count: int = 3
    blank_source: str = "acquire"
    sample_rate_hz: float | None = None
    reference_rate_hz: float | None = None
    timing_rate_hz: float | None = None
    sample_demod: int = 0
    reference_demod: int = 3
    timing_demod: int = 2
    hf2_filter_tc_s: float | None = None
    hf2_filter_order: int | None = None
    reference_filter_tc_s: float | None = None
    reference_filter_order: int | None = None
    sample_input_range_v: float | None = None
    reference_input_range_v: float | None = None
    qcl: int | None = None
    probe_rate_hz: float | None = None
    probe_pulse_width_s: float | None = None
    probe_current_ma: float | None = None
    probe_reference_delay_s: float = 0.0
    pump_fire_to_q_s: float | None = None
    pump_fire_width_s: float | None = None
    pump_q_width_s: float | None = None
    process_width_s: float | None = None
    pump_polarity: str = "positive"
    process_polarity: str = "negative"
    pump_dose_record_id: str = ""
    max_probe_exposure_s: float | None = None  # cumulative pulse-on seconds, not wall time
    probe_during_wait: bool = False
    temperature_check_interval_s: float | None = None
    plateau_enabled: bool = False
    plateau_relative_tolerance: float | None = None
    plateau_required_bursts: int = 3
    plateau_band_windows_cm1: tuple[tuple[float, float], ...] = ()
    configuration_time_s: float | None = None
    tuning_settling_time_s: float | None = None
    controls_time_s: float | None = None
    restoration_time_s: float | None = None
    processing_time_s: float | None = None
    upload_seconds_per_frame: float | None = None
    native_chunk_duration_s: float = 0.25
    max_memory_bytes: int = 268435456
    storage_budget_bytes: int | None = None
    calibration_ids: tuple[str, ...] = ()
    promoted_bundle_ids: tuple[str, ...] = ()
    sample_selection_id: str = ""
    controls_record_ids: tuple[str, ...] = ()
    settings_sources: dict[str, str] = field(default_factory=dict)
    hardware_evidence: dict[str, Any] = field(default_factory=dict)
    example_only: bool = False
    schema_version: int = SCHEMA_VERSION
    experiment_id: str = EXPERIMENT_ID

    @property
    def architecture_id(self) -> str:
        return CONDITION_PROFILES.get(self.condition_id, {}).get("architecture_id", "")

    @property
    def instance_id(self) -> str:
        return f"{EXPERIMENT_ID}:{self.mode}"

    @property
    def demod_indices(self) -> tuple[int, ...]:
        return (self.sample_demod, self.reference_demod) if self.mode == "dual" else (self.sample_demod,)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Settings":
        copied = dict(data)
        if copied.get("experiment_id", EXPERIMENT_ID) != EXPERIMENT_ID:
            raise ValueError("Settings belong to another experiment")
        if copied.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
            raise ValueError("Unsupported single-pump settings schema version")
        unknown = set(copied) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown settings fields: {', '.join(sorted(unknown))}")
        for name in ("later_burst_times_s", "calibration_ids", "promoted_bundle_ids", "controls_record_ids"):
            if name in copied:
                copied[name] = tuple(copied[name])
        if "plateau_band_windows_cm1" in copied:
            copied["plateau_band_windows_cm1"] = tuple(tuple(pair) for pair in copied["plateau_band_windows_cm1"])
        for name in ("settings_sources", "hardware_evidence"):
            if name in copied:
                copied[name] = dict(copied[name])
        return cls(**copied)


@dataclass(frozen=True)
class Capabilities:
    """Readbacks are supplied by an owned adapter; constructing this does no I/O."""
    frame_capacity: int = 8192
    predivider_max: int = 4294967295
    edge_quantum_s: float = 10e-12
    edge_max_s: float = 3600.0
    synthesizer_quantum_hz: float = 0.02
    synthesizer_max_hz: float = 16000000.0
    train_count_max: int = 4294967295
    train_spacing_min_s: float = 80e-9
    train_spacing_max_s: float = 10.0
    train_spacing_quantum_s: float = 20e-9
    frame_guard_s: float = 1e-6
    probe_duty_max: float = 0.30
    hf2_aggregate_rate_max_hz: float = 700000.0
    sample_rates_hz: tuple[float, ...] = ()
    reference_rates_hz: tuple[float, ...] = ()
    timing_rates_hz: tuple[float, ...] = ()
    scan_speed_min_cm1_s: float | None = None
    scan_speed_max_cm1_s: float | None = None
    wavenumber_min_cm1: float | None = None
    wavenumber_max_cm1: float | None = None
    frame_feature_verified: bool = False
    detector_rates_verified: bool = False
    topology_verified: bool = False
    optical_pump_observation_available: bool = False
    temperature_observation_available: bool = False
    probe_idle_control_available: bool = True
    device_ids: dict[str, str] = field(default_factory=dict)
    source_records: tuple[str, ...] = (
        "references/manuals/T660/Highland Technologies T660 Manual.pdf §§2,3.5,5.2–5.4",
        "instrument/wiring_map.yaml", "instrument/hardware_configuration.yaml",
    )
    actual_values: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Capabilities":
        values = dict(data)
        for name in ("sample_rates_hz", "reference_rates_hz", "timing_rates_hz", "source_records"):
            if name in values:
                values[name] = tuple(values[name])
        return cls(**values)


def resolve_settings(settings: Settings, *, promoted_values: Mapping[str, Any] | None = None,
                     installed_readbacks: Mapping[str, Any] | None = None) -> Settings:
    """Fill only unset fields from caller-validated promoted bundles/readbacks.

    Each source mapping carries ``record_id`` and ``values``. The host promotion
    loader must validate promotion before passing bundle values here; sample
    selections are a different data type and never serve as instrument bundles.
    User overrides are preserved, including their named evidence sources.
    """
    values = settings.to_dict()
    empty_resolvable = {"hardware_evidence", "calibration_ids", "controls_record_ids", "promoted_bundle_ids"}
    for source_kind, source in (("promoted", promoted_values), ("installed_readback", installed_readbacks)):
        if not source:
            continue
        if not source.get("record_id") or not isinstance(source.get("values"), Mapping):
            raise ValueError("Resolved values require a record_id and values mapping")
        for key, value in source["values"].items():
            if key not in values or key in {"mode", "condition_id", "experiment_id", "schema_version"}:
                continue
            if values[key] is None or (key in empty_resolvable and not values[key]):
                values[key] = deepcopy(value)
                # A human-readable record ID remains the operational source;
                # retain source category separately without changing that ID.
                values["settings_sources"][key] = str(source["record_id"])
                values["settings_sources"][f"{key}:source_kind"] = source_kind
    return Settings.from_dict(values)


def example_settings(mode: str = "single") -> Settings:
    """Explicit nonbiological simulation example, NEVER a commissioned recipe."""
    return Settings(mode=mode, sample_id="EXAMPLE-SAMPLE", preparation_id="EXAMPLE-PREP",
        accepted_state_id="EXAMPLE-HRP-STATE", matrix_id="EXAMPLE-MATRIX", cell_id="EXAMPLE-CELL",
        position_id="EXAMPLE-POSITION", temperature_identity="EXAMPLE-TEMP", thermal_history_id="EXAMPLE-HISTORY",
        measured_temperature_k=77.0, temperature_uncertainty_k=0.5, min_temperature_k=75.0, max_temperature_k=80.0,
        scan_start_cm1=1900.0, scan_stop_cm1=1950.0, scan_speed_cm1_s=5000.0,
        scan_interval_s=0.02, first_scan_delay_s=0.001, early_scan_count=10,
        first_later_burst_s=1.0, observation_limit_s=1200.0, sample_rate_hz=10000.0,
        reference_rate_hz=10000.0, timing_rate_hz=100000.0, hf2_filter_tc_s=0.00001,
        hf2_filter_order=1, reference_filter_tc_s=0.00001, reference_filter_order=1,
        sample_input_range_v=1.0, reference_input_range_v=1.0, qcl=1,
        probe_rate_hz=1000000.0, probe_pulse_width_s=100e-9, probe_current_ma=100.0,
        pump_fire_to_q_s=0.0001, pump_fire_width_s=1e-6, pump_q_width_s=1e-6,
        process_width_s=1e-6, pump_dose_record_id="EXAMPLE-DOSE", max_probe_exposure_s=10.0,
        temperature_check_interval_s=1.0, configuration_time_s=10.0, tuning_settling_time_s=2.0,
        controls_time_s=20.0, restoration_time_s=2.0, processing_time_s=2.0,
        upload_seconds_per_frame=0.04, sample_selection_id="EXAMPLE-SPECTRAL-SELECTION",
        plateau_band_windows_cm1=((1910.0, 1920.0), (1928.0, 1940.0)), example_only=True)
