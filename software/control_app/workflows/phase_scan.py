"""Hardware-free planning for one swept probe scan per pump/phase event.

This module describes requested timing, not measured scan trajectories or a
hardware recipe. In particular, a valid plan does not authorize laser operation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
import math
from typing import Any


PHASE_SCAN_EXECUTION_BLOCKER = (
    "A plan alone does not authorize acquisition. Optical acquisition requires connected devices "
    "and per-operation confirmation; a compatible background is required before sample scans. "
    "Unresolved wavelength coordinates remain explicitly provisional."
)


class PhaseScanPlanError(ValueError):
    """An input or a derived timing relationship cannot form a scan plan."""


@dataclass(frozen=True)
class PhaseScanSettings:
    probe_repetition_rate_hz: float = 2_000_000.0
    probe_pulse_width_ns: float = 150.0
    start_wavenumber_cm1: float = 1950.0
    stop_wavenumber_cm1: float = 1940.0
    scan_speed_cm1_s: float = 10_000.0
    phase_delay_us: float = 5.0
    rest_period_s: float = 0.250
    repetitions: int = 1
    pre_pump_ms: float = 2.0
    post_pump_ms: float = 5.0
    pump_reference: str = "electrical_sync"
    pump_threshold_v: float = 0.1
    missing_pulse_consecutive_limit: int = 2
    minimum_reconstruction_interval_coverage: float = 0.90
    maximum_scan_missing_fraction: float = 0.05
    missing_pulse_retry_limit: int = 3
    pulse_detection_threshold_fraction: float = 0.30


@dataclass(frozen=True)
class PhaseScanEvent:
    """One planned record; indices are zero based, repetition is one based."""

    scan_index: int
    repetition: int
    phase_index: int | None
    pump_enabled: bool
    phase_delay_us: float | None


@dataclass(frozen=True)
class PhaseScanPlan:
    settings: PhaseScanSettings
    phases_per_repetition: int
    scan_duration_s: float
    first_phase_tick: int

    @property
    def first_phase_delay_us(self) -> float:
        return float(self.first_phase_tick * _fraction(self.settings.phase_delay_us))

    @property
    def scans_per_repetition(self) -> int:
        return self.phases_per_repetition + 1

    @property
    def total_scans(self) -> int:
        return self.scans_per_repetition * self.settings.repetitions

    @property
    def total_pump_events(self) -> int:
        return self.phases_per_repetition * self.settings.repetitions

    @property
    def last_phase_delay_us(self) -> float:
        return float((self.first_phase_tick + self.phases_per_repetition - 1) * _fraction(self.settings.phase_delay_us))

    @property
    def probe_duty_cycle(self) -> float:
        return float(
            _fraction(self.settings.probe_repetition_rate_hz)
            * _fraction(self.settings.probe_pulse_width_ns) / 1_000_000_000
        )

    @property
    def nominal_probe_pulses_per_scan(self) -> float:
        return self.scan_duration_s * self.settings.probe_repetition_rate_hz

    @property
    def pump_rate_hz(self) -> float:
        return 1.0 / self.settings.rest_period_s

    @property
    def nominal_duration_s(self) -> float:
        # Each baseline occupies a slot too. There is no trailing rest after the
        # last scan. Instrument preparation/return/settling may take longer.
        return (
            (self.total_scans - 1) * self.settings.rest_period_s
            + self.last_phase_delay_us / 1_000_000
            + self.scan_duration_s
        )

    def event_at(self, scan_index: int) -> PhaseScanEvent:
        """Index a large plan without allocating an array of all its phases."""
        if not 0 <= scan_index < self.total_scans:
            raise IndexError("Scan index is outside this plan")
        repetition, within_set = divmod(scan_index, self.scans_per_repetition)
        if within_set == 0:
            return PhaseScanEvent(scan_index, repetition + 1, None, False, None)
        phase_index = within_set - 1
        delay = float((self.first_phase_tick + phase_index) * _fraction(self.settings.phase_delay_us))
        return PhaseScanEvent(scan_index, repetition + 1, phase_index, True, delay)

    def to_dict(self) -> dict[str, Any]:
        """Compact, versioned plan; a baseline is never a zero-delay pump shot."""
        return {
            "schema_version": "3.0",
            "method": "phase_delayed_single_scan",
            "status": "PLANNING_ONLY",
            "settings": asdict(self.settings),
            "derived": {
                "scan_duration_s": self.scan_duration_s,
                "phase_count_per_repetition": self.phases_per_repetition,
                "scans_per_repetition": self.scans_per_repetition,
                "baseline_scans_per_repetition": 1,
                "total_scans": self.total_scans,
                "total_pump_events": self.total_pump_events,
                "probe_duty_cycle": self.probe_duty_cycle,
                "nominal_probe_pulses_per_scan": self.nominal_probe_pulses_per_scan,
                "nominal_pump_rate_hz": self.pump_rate_hz,
                "nominal_duration_s": self.nominal_duration_s,
                "scan_direction": (
                    "decreasing_wavenumber"
                    if self.settings.stop_wavenumber_cm1 < self.settings.start_wavenumber_cm1
                    else "increasing_wavenumber"
                ),
            },
            "sequence": {
                "order": "repeat_entire_set",
                "baseline": "one_unpumped_scan_first_in_each_set",
                "scans_per_phase_per_repetition": 1,
                "phase_first_us": self.first_phase_delay_us,
                "phase_increment_us": self.settings.phase_delay_us,
                "phase_last_us": self.last_phase_delay_us,
                "phase_interval": "[-pre_pump - nominal_scan_duration, post_pump], rounded outward to phase steps",
                "observation_window_s": [-self.settings.pre_pump_ms / 1000, self.settings.post_pump_ms / 1000],
                "display_pump_time_ms": self.settings.pre_pump_ms,
                "rest_semantics": "minimum_pump_to_pump_interval_not_post_scan_sleep",
                "duration_model": "one_rest_period_slot_per_record_including_baselines_no_trailing_rest",
                "averaging": "corresponding_phase_across_complete_repetitions_keep_raw_records",
                "missing_pulse_workaround": {
                    "analysis_order": "analyze all nominal scans before targeted same-delay retries and reconstruction",
                    "picoscope_channels": {"CHA": "sample detector", "CHB": "reference detector primary witness"},
                    "missing_definition": "expected optical pulse absent from both detector channels",
                    "reconstruction_interval_s": self.settings.phase_delay_us * 1e-6,
                    "minimum_interval_coverage": self.settings.minimum_reconstruction_interval_coverage,
                    "consecutive_missing_limit": self.settings.missing_pulse_consecutive_limit,
                    "maximum_scan_missing_fraction": self.settings.maximum_scan_missing_fraction,
                    "additional_attempt_limit": self.settings.missing_pulse_retry_limit,
                    "merge": "observed-marker-aligned reconstruction bins weighted by pulse coverage",
                },
            },
            "limitations": [
                "Nominal linear trajectory only; use measured pump and scan timing for reconstruction.",
                "Phase increment is not a claim of temporal resolution.",
                "Probe pulse count is nominal, not a measured detector sample count.",
                "Duration excludes initialization, return, settling, and additional sample recovery.",
                "QCL/current, acquisition/filter settings, and calibration require an instrument preset.",
                PHASE_SCAN_EXECUTION_BLOCKER,
            ],
        }


def build_phase_scan_plan(settings: PhaseScanSettings) -> PhaseScanPlan:
    """Cover the requested pump-relative window at every point of a nominal sweep."""
    for name, value in asdict(settings).items():
        if name == "pump_reference":
            if value not in {"electrical_sync", "auxin0", "auxin1"}:
                raise PhaseScanPlanError("Select electrical sync, Aux In 1, or Aux In 2 for pump timing")
        elif name in {"pre_pump_ms", "pump_threshold_v"}:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise PhaseScanPlanError(f"{name} must be finite")
            if name == "pre_pump_ms" and value < 0:
                raise PhaseScanPlanError("Before Pump must not be negative")
            if name == "pump_threshold_v" and not -10 < value < 10:
                raise PhaseScanPlanError("Pump threshold must lie inside the Aux input ±10 V range")
        elif name in {"repetitions", "missing_pulse_consecutive_limit", "missing_pulse_retry_limit"}:
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise PhaseScanPlanError(f"{name.replace('_', ' ').title()} must be a positive whole number")
        elif name in {"minimum_reconstruction_interval_coverage", "maximum_scan_missing_fraction",
                      "pulse_detection_threshold_fraction"}:
            if (isinstance(value, bool) or not isinstance(value, (int, float)) or
                    not math.isfinite(value) or not 0 < value <= 1):
                raise PhaseScanPlanError(f"{name.replace('_', ' ')} must be greater than zero and at most one")
        elif (
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0
        ):
            raise PhaseScanPlanError(f"{name.replace('_', ' ')} must be a finite positive number")

    span = abs(_fraction(settings.stop_wavenumber_cm1) - _fraction(settings.start_wavenumber_cm1))
    if span == 0:
        raise PhaseScanPlanError("Start and Stop Wavenumber must differ")
    scan_s = span / _fraction(settings.scan_speed_cm1_s)
    step_s = _fraction(settings.phase_delay_us) / 1_000_000
    first_tick = -math.ceil((scan_s + _fraction(settings.pre_pump_ms) / 1000) / step_s)
    last_tick = math.ceil((_fraction(settings.post_pump_ms) / 1000) / step_s)
    phase_count = last_tick - first_tick + 1
    last_phase_s = last_tick * step_s
    duty = (
        _fraction(settings.probe_repetition_rate_hz)
        * _fraction(settings.probe_pulse_width_ns) / 1_000_000_000
    )
    if duty > Fraction(3, 10):
        raise PhaseScanPlanError(
            f"Probe duty cycle is {float(duty):.3%}; reduce repetition rate or pulse width "
            "to stay within the MIRcat 30% ceiling. Device-specific limits still require readback."
        )
    if _fraction(settings.rest_period_s) < Fraction(1, 10):
        raise PhaseScanPlanError("Rest Period must be at least 0.1 s for the installed 10 Hz pump limit")
    occupied_s = max(-first_tick * step_s, last_phase_s + scan_s) + Fraction(1, 100)
    if _fraction(settings.rest_period_s) < occupied_s:
        raise PhaseScanPlanError(
            f"Rest Period must be at least {float(occupied_s):.9g} s "
            "to finish the latest delayed scan and trigger pulse before the next pump event"
        )
    return PhaseScanPlan(settings, phase_count, float(scan_s), first_tick)


def _fraction(value: float) -> Fraction:
    return Fraction(str(value))
