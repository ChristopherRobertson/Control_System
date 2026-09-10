"""Hardware-free scientific inputs for the two fixed-point measurement modes.

Defaults are editable planning proposals, never established operating values.
Recipe fields default to None and must be resolved from an applicable record.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, Mapping

EXPERIMENT_ID = "fixed_wavenumber_kinetics"
SCHEMA_VERSION = "1.0"
CONDITION_PROFILES = {
    "rt_hrp_co": {"protein": "HRP–CO", "temperature_regime": "room_temperature", "purpose": "local discovery and selected-band long recovery"},
    "rt_mbco": {"protein": "MbCO", "temperature_regime": "room_temperature", "purpose": "A1-first discovery; A0/A3 require measured quantification"},
    "cryo_hrp_co": {"protein": "HRP–CO", "temperature_regime": "cryogenic", "purpose": "one-event observation unless a fresh equivalent state is established"},
    "cryo_mbco": {"protein": "MbCO", "temperature_regime": "cryogenic", "purpose": "A1-first one-event observation; no assumed reset"},
}


@dataclass(frozen=True)
class Position:
    wavenumber_cm1: float
    label: str = "band"
    selection_record_id: str = ""
    band_assignment: str = ""

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | "Position" | float) -> "Position":
        if isinstance(value, cls):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return cls(float(value))
        unknown = set(value) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown position fields: {', '.join(sorted(unknown))}")
        return cls(**dict(value))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Settings:
    mode: str = "single"
    condition_profile: str = "rt_hrp_co"
    condition_id: str = ""
    sample_id: str = ""
    preparation_id: str = ""
    cell_id: str = ""
    position_id: str = ""
    temperature_id: str = ""
    temperature_k: float | None = None
    positions: tuple[Position, ...] = ()
    pre_observation_s: float = 1.0
    post_observation_s: float = 10.0
    event_budget: int = 1
    technical_repetitions: int = 1
    events_per_position: int = 1
    pump_enabled: bool = True
    minimum_event_interval_s: float | None = None
    baseline_window_s: tuple[float, float] | None = None
    integration_window_s: tuple[float, float] | None = None
    baseline_drift_fraction: float = 0.01
    baseline_cv_limit: float = 0.05
    reset_tolerance_fraction: float = 0.02
    reset_observation_s: float | None = None
    sample_rate_sps: float | None = None
    reference_rate_sps: float | None = None
    sample_timeconstant_s: float | None = None
    reference_timeconstant_s: float | None = None
    sample_filter_order: int | None = None
    reference_filter_order: int | None = None
    retention_strategy: str = "continuous_to_disk"
    chunk_duration_s: float = 1.0
    memory_limit_mb: float = 256.0
    storage_limit_mb: float = 10240.0
    tune_timeout_s: float = 60.0
    wavenumber_tolerance_cm1: float | None = None
    dark_control_record_id: str = ""
    artifact_control_record_id: str = ""
    fresh_state_record_ids: tuple[str, ...] = ()
    background_balance_record_id: str = ""
    notes: str = ""

    @property
    def instance_id(self) -> str:
        return f"{EXPERIMENT_ID}:{self.mode}"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | "Settings") -> "Settings":
        if isinstance(value, cls):
            return value
        data = dict(value)
        unknown = set(data) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown fixed-wavenumber settings: {', '.join(sorted(unknown))}")
        data["positions"] = tuple(Position.from_dict(v) for v in data.get("positions", ()))
        for name in ("baseline_window_s", "integration_window_s", "fresh_state_record_ids"):
            if data.get(name) is not None:
                data[name] = tuple(data[name])
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["positions"] = [p.to_dict() for p in self.positions]
        for key in ("baseline_window_s", "integration_window_s", "fresh_state_record_ids"):
            if result[key] is not None:
                result[key] = list(result[key])
        return result
