"""Hardware-free, unit-explicit requests and optional scientific annotations."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from decimal import Decimal
import math
from typing import Any, Mapping

EXPERIMENT_ID = "repeated_rapid_scan"
SCHEMA_VERSION = 1
MIRCAT_QCL = 1
MIRCAT_MAX_DUTY_FRACTION = Decimal("0.30")


@dataclass(frozen=True)
class ConditionProfile:
    condition_id: str = "sample"
    sample_id: str = "Sample"
    preparation_id: str = "unassigned"
    cell_id: str = "unassigned"
    position_id: str = "unassigned"
    protein: str = ""
    temperature_K: float | None = None
    temperature_record_id: str = ""
    sample_selection_id: str = ""
    concentration_metadata: dict[str, Any] = field(default_factory=dict)
    artifact_control_ids: tuple[str, ...] = ()
    state_verification_ids: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class RecoveryCriteria:
    band_relative_tolerance: float = 0.03
    offband_absolute_tolerance: float = 0.003
    consecutive_scans: int = 3
    min_recovery_s: float = 0.0
    max_reset_wait_s: float = 30.0
    stationarity_relative_tolerance: float = 0.03


@dataclass(frozen=True)
class RepeatedRapidScanSettings:
    mode: str = "single"
    execution: str = "hardware"
    condition: ConditionProfile = field(default_factory=ConditionProfile)
    phase_offsets_s: tuple[float, ...] = (0.0, 0.025, 0.05, 0.075)
    pre_scans: int = 5
    post_scans: int = 100
    repeats: int = 1
    directions: tuple[str, ...] = ("forward", "reverse")
    controls: tuple[str, ...] = ("probe_only",)
    scan_start_cm1: float = 1898.0
    scan_stop_cm1: float = 1951.0
    band_windows_cm1: tuple[tuple[float, float], ...] = ((1903.0, 1907.0), (1942.0, 1946.0))
    offband_windows_cm1: tuple[tuple[float, float], ...] = ((1898.0, 1901.0), (1948.0, 1951.0))
    measured_scan_period_s: float = 0.1
    scan_speed_cm1_s: float = 530.0
    sample_rate_hz: float = 2000.0
    reference_rate_hz: float = 2000.0
    sample_demodulator: int = 0
    reference_demodulator: int = 3
    sample_input_range_v: float = 1.0
    reference_input_range_v: float = 1.0
    sample_filter_order: int = 4
    reference_filter_order: int = 4
    sample_filter_timeconstant_s: float = 0.001
    reference_filter_timeconstant_s: float = 0.001
    # In MIRcat external-pulse mode 2 this trigger frequency sets the emitted
    # optical repetition rate. The electrical TTL width is separate.
    probe_frequency_hz: float = 1000000.0
    probe_pulse_width_s: float = 150e-9
    # QCL1 internal optical pulse settings; None preserves the connected member.
    mircat_pulse_rate_hz: float | None = None
    mircat_pulse_width_ns: float | None = None
    mircat_current_ma: float | None = None
    process_pulse_width_s: float = 0.001
    process_delay_s: float = 0.0
    fire_to_qswitch_s: float = 200e-6
    fire_pulse_width_s: float = 10e-6
    qswitch_pulse_width_s: float = 10e-6
    timing_quantum_s: float = 10e-12
    allow_phase_quantization: bool = False
    allow_period_quantization: bool = False
    recovery: RecoveryCriteria = field(default_factory=RecoveryCriteria)
    tuning_settling_s: float = 5.0
    preparation_s: float = 60.0
    restoration_s: float = 5.0
    analysis_s: float = 10.0
    upload_acknowledgment_s: float = 0.012
    storage_bytes_per_second: float = 20_000_000.0
    memory_limit_bytes: int = 512 * 1024 * 1024
    storage_limit_bytes: int = 10 * 1024 * 1024 * 1024
    value_source: str = "Initial requests; connected readbacks are not yet available. Band windows are nominal analysis inputs."
    calibration_ids: tuple[str, ...] = ()
    instrument_state_id: str = "unverified"
    acquisition_intent: dict[str, Any] = field(default_factory=dict)
    manual_overrides: dict[str, Any] = field(default_factory=dict)
    historical_ui_settings: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION
    experiment_id: str = EXPERIMENT_ID

    @property
    def condition_id(self) -> str:
        return self.condition.condition_id

    @property
    def instance_id(self) -> str:
        return f"{EXPERIMENT_ID}:{self.mode}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RepeatedRapidScanSettings":
        data = dict(value)
        unknown = set(data) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError("Unsupported settings fields: " + ", ".join(sorted(unknown)))
        if isinstance(data.get("condition"), Mapping):
            condition = dict(data["condition"])
            for key in ("artifact_control_ids", "state_verification_ids"):
                if key in condition:
                    condition[key] = tuple(condition[key])
            data["condition"] = ConditionProfile(**condition)
        if isinstance(data.get("recovery"), Mapping):
            data["recovery"] = RecoveryCriteria(**data["recovery"])
        for name in ("phase_offsets_s", "directions", "controls", "calibration_ids"):
            if name in data:
                data[name] = tuple(data[name])
        for name in ("band_windows_cm1", "offband_windows_cm1"):
            if name in data:
                data[name] = tuple(tuple(window) for window in data[name])
        result = cls(**data)
        result.validate()
        return result

    def validate(self) -> None:
        if self.experiment_id != EXPERIMENT_ID or self.schema_version != SCHEMA_VERSION:
            raise ValueError("Incompatible repeated_rapid_scan settings identity/schema")
        if self.mode not in ("single", "dual") or self.execution not in ("simulation", "hardware"):
            raise ValueError("mode must be single/dual and execution simulation/hardware")
        if not isinstance(self.condition, ConditionProfile) or not isinstance(self.recovery, RecoveryCriteria):
            raise ValueError("condition and recovery must be typed profiles")
        for name in ("pre_scans", "post_scans", "repeats", "memory_limit_bytes", "storage_limit_bytes"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        positive = ("measured_scan_period_s", "scan_speed_cm1_s", "sample_rate_hz", "reference_rate_hz",
                    "sample_input_range_v", "reference_input_range_v", "sample_filter_timeconstant_s",
                    "reference_filter_timeconstant_s", "probe_frequency_hz", "probe_pulse_width_s",
                    "process_pulse_width_s", "fire_to_qswitch_s", "fire_pulse_width_s", "qswitch_pulse_width_s",
                    "timing_quantum_s", "storage_bytes_per_second")
        for name in positive:
            _finite(getattr(self, name), name, positive=True)
        validate_mircat_pulse_pair(self.mircat_pulse_rate_hz, self.mircat_pulse_width_ns)
        validate_probe_optical_pulse_pair(self.probe_frequency_hz, self.mircat_pulse_width_ns)
        if self.mircat_current_ma is not None:
            _finite(self.mircat_current_ma, "mircat_current_ma", positive=True)
        if not isinstance(self.manual_overrides, Mapping):
            raise ValueError("manual_overrides must be a mapping")
        if {"qcl", "qcl_id", "qcl_index", "mircat_qcl"} & self.manual_overrides.keys():
            raise ValueError("Repeated Rapid-Scan uses QCL1 only; QCL selection is not a manual override")
        # Saved intent may contain a request different from selected/readback
        # values. Validate that effective pair as well, including one-member
        # overrides. An unknown automatic member is validated at live resolution.
        pulse_override = {name: value for name, value in self.manual_overrides.items() if value is not None}
        validate_mircat_pulse_pair(pulse_override.get("mircat_pulse_rate_hz", self.mircat_pulse_rate_hz),
                                  pulse_override.get("mircat_pulse_width_ns", self.mircat_pulse_width_ns))
        validate_probe_optical_pulse_pair(pulse_override.get("probe_frequency_hz", self.probe_frequency_hz),
                                         pulse_override.get("mircat_pulse_width_ns", self.mircat_pulse_width_ns))
        for name in ("process_delay_s", "tuning_settling_s", "preparation_s", "restoration_s", "analysis_s", "upload_acknowledgment_s"):
            _finite(getattr(self, name), name, nonnegative=True)
        _finite(self.scan_start_cm1, "scan_start_cm1")
        _finite(self.scan_stop_cm1, "scan_stop_cm1")
        if self.scan_start_cm1 >= self.scan_stop_cm1:
            raise ValueError("scan_start_cm1 must be below scan_stop_cm1")
        # Temperature and scientific evidence are annotations, never execution
        # or compatibility inputs. Only values used by hardware are validated.
        if not self.phase_offsets_s or len(set(self.phase_offsets_s)) != len(self.phase_offsets_s):
            raise ValueError("phase offsets must be a nonempty unique sequence")
        for phase in self.phase_offsets_s:
            _finite(phase, "phase_offset_s", nonnegative=True)
            if phase >= self.measured_scan_period_s:
                raise ValueError("phase offset must be less than one measured scan period")
        if not self.directions or len(set(self.directions)) != len(self.directions) or not set(self.directions) <= {"forward", "reverse"}:
            raise ValueError("directions must contain distinct forward/reverse choices")
        if len(set(self.controls)) != len(self.controls) or not set(self.controls) <= {"probe_only", "pump_blocked", "dark"}:
            raise ValueError("controls support probe_only, pump_blocked and dark; physical actions are explicit")
        for name in ("band_windows_cm1", "offband_windows_cm1"):
            windows = getattr(self, name)
            for window in windows:
                if len(window) != 2 or not all(math.isfinite(x) for x in window):
                    raise ValueError(f"{name} requires finite lower/upper pairs in cm^-1")
                if not self.scan_start_cm1 <= window[0] < window[1] <= self.scan_stop_cm1:
                    raise ValueError(f"{name} must be contained within the spectral window")
        for name in ("sample_demodulator", "reference_demodulator"):
            if type(getattr(self, name)) is not int or not 0 <= getattr(self, name) <= 5:
                raise ValueError(f"{name} must be an HF2LI demodulator index 0..5")
        if self.mode == "dual" and self.sample_demodulator == self.reference_demodulator:
            raise ValueError("dual detectors require independently configured demodulators")
        for name in ("sample_filter_order", "reference_filter_order"):
            if type(getattr(self, name)) is not int or not 1 <= getattr(self, name) <= 8:
                raise ValueError(f"{name} must be an integer in 1..8")
        if type(self.recovery.consecutive_scans) is not int or self.recovery.consecutive_scans < 2:
            raise ValueError("consecutive_scans must be an integer at least two")
        for name in ("band_relative_tolerance", "offband_absolute_tolerance", "stationarity_relative_tolerance"):
            _finite(getattr(self.recovery, name), name, positive=True)
        for name in ("min_recovery_s", "max_reset_wait_s"):
            _finite(getattr(self.recovery, name), name, nonnegative=True)


def _finite(value: Any, name: str, *, positive=False, nonnegative=False) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if (positive and value <= 0) or (nonnegative and value < 0):
        raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'}")


def validate_mircat_pulse_pair(rate_hz: float | None, width_ns: float | None) -> float | None:
    """Validate QCL1 internal optical duty; connected vendor limits also apply.

    Unknown members stay unknown until readback. Decimal multiplication avoids
    rejecting an exact 30% boundary due to binary floating-point multiplication.
    The external T660 carrier and TTL width do not enter this optical product.
    """
    return _validate_optical_duty_pair(rate_hz, width_ns, "mircat_pulse_rate_hz", "MIRcat internal repetition rate")


def validate_probe_optical_pulse_pair(rate_hz: float | None, width_ns: float | None) -> float | None:
    """Validate emitted mode-2 cadence times the MIRcat SDK optical width.

    The emitted cadence is the external T660 trigger frequency. The independent
    internal MIRcat rate is validated separately; the TTL trigger width enters
    neither optical duty calculation. Lower connected vendor limits still apply.
    """
    return _validate_optical_duty_pair(rate_hz, width_ns, "probe_frequency_hz", "Emitted probe repetition rate")


def _validate_optical_duty_pair(rate_hz, width_ns, rate_name, label) -> float | None:
    for name, value in ((rate_name, rate_hz), ("mircat_pulse_width_ns", width_ns)):
        if value is not None:
            _finite(value, name, positive=True)
    if rate_hz is None or width_ns is None:
        return None
    duty = Decimal(str(rate_hz)) * Decimal(str(width_ns)) * Decimal("1e-9")
    if duty > MIRCAT_MAX_DUTY_FRACTION:
        raise ValueError(f"{label} times optical pulse width must be at most 30% duty (0.30)")
    return float(duty)


def example_settings(mode: str = "single") -> RepeatedRapidScanSettings:
    result = RepeatedRapidScanSettings(mode=mode, execution="simulation",
                                      controls=("probe_only", "pump_blocked"),
                                      condition=ConditionProfile(condition_id="example-hrp-room-temperature",
                                          sample_id="unassigned", protein="HRP-CO", temperature_K=298.15,
                                          notes="EXAMPLE ONLY: simulated condition annotation"),
                                      value_source="EXAMPLE ONLY: explicit simulation fixture; no connected readbacks")
    result.validate()
    return result


@dataclass(frozen=True)
class AcquisitionIntent:
    """The operator's essential request; instrument choices are resolved later."""
    sample_name: str = "Sample"
    spectral_min_cm1: float = 1898.0
    spectral_max_cm1: float = 1951.0
    observation_duration_s: float = 10.0
    phase_count: int = 4
    repeats: int = 1

    def validate(self) -> None:
        if not isinstance(self.sample_name, str) or not self.sample_name.strip():
            raise ValueError("sample_name must be a nonempty name")
        _finite(self.spectral_min_cm1, "spectral_min_cm1")
        _finite(self.spectral_max_cm1, "spectral_max_cm1")
        if self.spectral_min_cm1 >= self.spectral_max_cm1:
            raise ValueError("spectral_min_cm1 must be below spectral_max_cm1")
        _finite(self.observation_duration_s, "observation_duration_s", positive=True)
        for name in ("phase_count", "repeats"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AcquisitionIntent":
        result = cls(**dict(value))
        result.validate()
        return result

    @classmethod
    def from_settings(cls, settings: RepeatedRapidScanSettings | Mapping[str, Any]) -> "AcquisitionIntent":
        if isinstance(settings, Mapping):
            settings = RepeatedRapidScanSettings.from_dict(settings)
        if settings.acquisition_intent:
            return cls.from_dict(settings.acquisition_intent)
        sample = settings.condition.sample_id
        result = cls("Sample" if sample in ("", "unassigned") else sample,
                     settings.scan_start_cm1, settings.scan_stop_cm1,
                     settings.post_scans * settings.measured_scan_period_s,
                     len(settings.phase_offsets_s), settings.repeats)
        result.validate()
        return result
