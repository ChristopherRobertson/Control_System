"""Hardware-free scientific settings; absence of evidence is represented explicitly."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from copy import deepcopy
from typing import Any, Mapping

EXPERIMENT_ID = "steady_state_slow_scan"
SCHEMA_VERSION = "1.0"


def _known(cls, data: Mapping[str, Any]) -> dict[str, Any]:
    values = dict(data)
    unknown = set(values) - {item.name for item in fields(cls)}
    if unknown:
        raise ValueError(f"Unsupported {cls.__name__} fields: {', '.join(sorted(unknown))}")
    return values


@dataclass(frozen=True)
class ConditionIdentity:
    condition_id: str = ""
    sample_id: str = ""
    preparation_id: str = ""
    cell_id: str = ""
    position_id: str = ""
    temperature_id: str = ""
    matrix_id: str = ""
    configuration_id: str = ""
    temperature_k: float | None = None
    temperature_uncertainty_k: float | None = None
    temperature_record_id: str = ""
    state_id: str = "initial"
    exposure_history_id: str = ""
    pH: float | None = None
    cell_reload_id: str = ""
    lot_id: str = ""
    state_verification_id: str = ""
    thermal_history_id: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ConditionIdentity":
        return cls(**_known(cls, data))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SpectralSegment:
    segment_id: str
    qcl: int
    lower_cm1: float
    upper_cm1: float

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SpectralSegment":
        return cls(**_known(cls, data))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SlowScanSettings:
    mode: str = "single"
    condition: ConditionIdentity = field(default_factory=ConditionIdentity)
    lower_cm1: float = 1900.0
    upper_cm1: float = 1975.0
    purpose: str = "survey"
    requested_scan_speed_cm1_s: float = 2.0
    current_ma: float | None = None
    time_constant_s: float | None = None
    filter_order: int | None = None
    reference_time_constant_s: float | None = None
    reference_filter_order: int | None = None
    replicates: int = 2
    repetition_rate_hz: float | None = None
    pulse_width_s: float | None = None
    hardware: bool = True
    calibration_bundle_ids: tuple[str, ...] = ()
    plan_label: str = ""
    imported_requested_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.mode not in ("single", "dual"):
            raise ValueError("Slow scan mode must be single or dual")
        object.__setattr__(self, "calibration_bundle_ids", tuple(self.calibration_bundle_ids))
        object.__setattr__(self, "imported_requested_metadata", deepcopy(self.imported_requested_metadata))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SlowScanSettings":
        data = dict(data)
        if str(data.pop("schema_version", SCHEMA_VERSION)) != SCHEMA_VERSION:
            raise ValueError("Unsupported slow scan plan schema_version")
        if data.pop("experiment_id", EXPERIMENT_ID) != EXPERIMENT_ID:
            raise ValueError("Plan belongs to another experiment")
        instance_id = data.pop("instance_id", None)
        # Old plans can be read without reviving acknowledgement gates.
        data.pop("condition_equilibrated", None)
        data.pop("physical_controls_confirmed", None)
        data.pop("acceptance_reviewer", None)
        data.pop("acceptance_rationale", None)
        # Retain historical requests separately; none can govern acquisition.
        imported = deepcopy(data.get("imported_requested_metadata", {}))
        for name in ("segments", "requested_resolution_cm1", "measured_linewidth_cm1", "sample_rate_hz",
                     "reference_sample_rate_hz", "sample_range_v", "reference_range_v", "settle_s",
                     "marker_interval_cm1", "marker_width_s", "process_pulse_width_s", "dark_duration_s",
                     "fit_peak_count", "fit_line_shape", "fit_baseline_degree", "fit_fringe_periods_cm1", "probe_width_s"):
            if name in data:
                imported[name] = data.pop(name)
        if "probe_rate_hz" in data:
            previous_rate = data.pop("probe_rate_hz")
            imported["probe_rate_hz"] = previous_rate
            data.setdefault("repetition_rate_hz", previous_rate)
        data["imported_requested_metadata"] = imported
        if data.get("requested_scan_speed_cm1_s") is None:
            data["requested_scan_speed_cm1_s"] = 2.0
        values = _known(cls, data)
        if isinstance(values.get("condition"), Mapping):
            values["condition"] = ConditionIdentity.from_dict(values["condition"])
        result = cls(**values)
        if instance_id is not None and instance_id != result.instance_id:
            raise ValueError("Plan instance_id and detector mode disagree")
        return result

    @property
    def instance_id(self) -> str:
        return f"{EXPERIMENT_ID}:{self.mode}"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result.update(schema_version=SCHEMA_VERSION, experiment_id=EXPERIMENT_ID, instance_id=self.instance_id)
        return result


@dataclass(frozen=True)
class QCLWindow:
    qcl: int
    lower_cm1: float
    upper_cm1: float
    minimum_speed_cm1_s: float | None = None
    maximum_speed_cm1_s: float | None = None
    speed_increment_cm1_s: float | None = None
    tuning_settle_s: float | None = None
    source_id: str = ""
    qualified: bool = False


@dataclass(frozen=True)
class PlannerInputs:
    """Detached readbacks and applicable promoted evidence, never live services.

    ``scientific_profile`` holds measured settings, independent sample/reference
    HF2LI configurations, and named evidence IDs. No candidate global recipe is
    imported. ``promoted_bundle_ids`` must come from the host promotion loader.
    """

    scientific_profile: dict[str, Any] = field(default_factory=dict)
    qcl_windows: tuple[QCLWindow, ...] = ()
    supported_sample_rates_hz: tuple[float, ...] = ()
    supported_reference_sample_rates_hz: tuple[float, ...] = ()
    available_demodulators: tuple[int, ...] = ()
    demodulator_roles: dict[str, int] = field(default_factory=lambda: {"sample": 0, "reference": 3, "timing": 2})
    aggregate_max_rate_hz: float | None = None
    timing_rate_hz: float | None = None
    t660_tick_s: float | None = None
    t660_maximum_delay_s: float | None = None
    t660_frame_capacity: int | None = None
    frames_feature_observed: bool = False
    tee_receiver_topology_verified: bool = False
    process_trigger_qualified: bool = False
    wavelength_markers_qualified: bool = False
    promoted_bundle_ids: tuple[str, ...] = ()
    configuration_id: str = ""
    condition_ids: tuple[str, ...] = ()
    modes: tuple[str, ...] = ()
    source_records: tuple[dict[str, Any], ...] = ()
    actual_readbacks: dict[str, Any] = field(default_factory=dict)
    simulation: bool = False

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlannerInputs":
        values = _known(cls, data)
        if "qcl_windows" in values:
            values["qcl_windows"] = tuple(item if isinstance(item, QCLWindow) else QCLWindow(**_known(QCLWindow, item))
                                         for item in values["qcl_windows"])
        for name in ("supported_sample_rates_hz", "supported_reference_sample_rates_hz", "available_demodulators", "promoted_bundle_ids", "condition_ids", "modes", "source_records"):
            if name in values:
                values[name] = tuple(values[name])
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
