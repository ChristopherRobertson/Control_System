"""Hardware-free planning for one swept probe scan per pump/phase event.

This module describes requested timing, not measured scan trajectories or a
hardware recipe. In particular, a valid plan does not authorize laser operation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
import math
from typing import Any
from bisect import bisect_right


PHASE_SCAN_EXECUTION_BLOCKER = (
    "A plan alone does not authorize acquisition. Optical acquisition requires connected devices "
    "and per-operation confirmation; a compatible background is required before sample scans. "
    "Unresolved wavelength coordinates remain explicitly provisional."
)


class PhaseScanPlanError(ValueError):
    """An input or a derived timing relationship cannot form a scan plan."""


@dataclass(frozen=True)
class PhaseScanSettings:
    # The T660-1 output is the optical-opportunity clock, not the MIRcat's
    # internal rate setting used to avoid rejecting incoming trigger edges.
    probe_repetition_rate_hz: float = 2_000_000.0
    probe_pulse_width_ns: float = 150.0
    mircat_internal_repetition_rate_hz: float = 2_100_000.0
    mircat_internal_pulse_width_ns: float = 142.0
    start_wavenumber_cm1: float = 1950.0
    stop_wavenumber_cm1: float = 1940.0
    scan_speed_cm1_s: float = 10_000.0
    phase_delay_us: float = 5.0
    rest_period_s: float = 0.300
    repetitions: int = 1
    pre_pump_ms: float = 1.0
    post_pump_ms: float = 5.0
    pump_reference: str = "electrical_sync"


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
    trajectory_time_bounds_s: tuple[float, float] = (0.0, 0.0)
    trajectory_source: str | None = None

    @property
    def calibrated(self) -> bool:
        return self.trajectory_source is not None

    @property
    def frame_period_s(self) -> float:
        return 600_000 / self.settings.probe_repetition_rate_hz

    @property
    def first_phase_delay_us(self) -> float:
        return float(self.first_phase_tick * _fraction(self.settings.phase_delay_us))

    @property
    def scans_per_repetition(self) -> int:
        return self.phases_per_repetition

    @property
    def total_scans(self) -> int:
        return 1 + self.phases_per_repetition * self.settings.repetitions

    @property
    def total_pump_events(self) -> int:
        return self.phases_per_repetition * self.settings.repetitions

    @property
    def last_phase_delay_us(self) -> float:
        return float((self.first_phase_tick + self.phases_per_repetition - 1) * _fraction(self.settings.phase_delay_us))

    @property
    def probe_duty_cycle(self) -> float:
        """Duty cycle of the external T660-1 TTL train (not optical emission)."""
        return float(
            _fraction(self.settings.probe_repetition_rate_hz)
            * _fraction(self.settings.probe_pulse_width_ns) / 1_000_000_000
        )

    @property
    def mircat_internal_duty_cycle(self) -> float:
        return float(
            _fraction(self.settings.mircat_internal_repetition_rate_hz)
            * _fraction(self.settings.mircat_internal_pulse_width_ns) / 1_000_000_000
        )

    @property
    def mircat_internal_rate_margin_hz(self) -> float:
        return float(_fraction(self.settings.mircat_internal_repetition_rate_hz)
                     - _fraction(self.settings.probe_repetition_rate_hz))

    @property
    def nominal_probe_pulses_per_scan(self) -> float:
        return self.scan_duration_s * self.settings.probe_repetition_rate_hz

    @property
    def pump_rate_hz(self) -> float:
        return 1.0 / self.frame_period_s

    @property
    def nominal_duration_s(self) -> float:
        # Each baseline occupies a slot too. There is no trailing rest after the
        # last scan. Instrument preparation/return/settling may take longer.
        return (
            (self.total_scans - 1) * self.frame_period_s
            + .001 + max(.000180, -self.last_phase_delay_us * 1e-6)
            + max(0., self.last_phase_delay_us * 1e-6 + self.trajectory_time_bounds_s[1])
        )

    def event_at(self, scan_index: int) -> PhaseScanEvent:
        """Index a large plan without allocating an array of all its phases."""
        if not 0 <= scan_index < self.total_scans:
            raise IndexError("Scan index is outside this plan")
        if scan_index == 0:
            return PhaseScanEvent(0, 1, None, False, None)
        repetition, phase_index = divmod(scan_index-1, self.phases_per_repetition)
        delay = float((self.first_phase_tick + phase_index) * _fraction(self.settings.phase_delay_us))
        return PhaseScanEvent(scan_index, repetition + 1, phase_index, True, delay)

    def to_dict(self) -> dict[str, Any]:
        """Compact, versioned plan; a baseline is never a zero-delay pump shot."""
        return {
            "schema_version": "4.0",
            "method": "phase_delayed_single_scan",
            "status": "PLANNING_ONLY",
            "settings": asdict(self.settings),
            "derived": {
                "scan_duration_s": self.scan_duration_s,
                "phase_count_per_repetition": self.phases_per_repetition,
                "scans_per_repetition": self.scans_per_repetition,
                "baseline_scans_per_run": 1,
                "total_scans": self.total_scans,
                "total_pump_events": self.total_pump_events,
                "probe_duty_cycle": self.probe_duty_cycle,
                "mircat_internal_duty_cycle": self.mircat_internal_duty_cycle,
                "mircat_internal_rate_margin_hz": self.mircat_internal_rate_margin_hz,
                "nominal_probe_pulses_per_scan": self.nominal_probe_pulses_per_scan,
                "nominal_pump_rate_hz": self.pump_rate_hz,
                "nominal_duration_s": self.nominal_duration_s,
                "frame_period_s": self.frame_period_s,
                "frame_predivider": 600_000,
                "trajectory_calibrated": self.calibrated,
                "trajectory_source": self.trajectory_source,
                "trajectory_time_bounds_s": list(self.trajectory_time_bounds_s),
                "scan_direction": (
                    "decreasing_wavenumber"
                    if self.settings.stop_wavenumber_cm1 < self.settings.start_wavenumber_cm1
                    else "increasing_wavenumber"
                ),
            },
            "sequence": {
                "order": "one_baseline_then_repeat_nominal_phase_set",
                "baseline": "one_unpumped_scan_first_in_run",
                "scans_per_phase_per_repetition": 1,
                "phase_first_us": self.first_phase_delay_us,
                "phase_increment_us": self.settings.phase_delay_us,
                "phase_last_us": self.last_phase_delay_us,
                "phase_interval": "[-pre_pump-max(calibrated_trajectory_time), post_pump-min(calibrated_trajectory_time)], rounded outward to phase steps",
                "observation_window_s": [-self.settings.pre_pump_ms / 1000, self.settings.post_pump_ms / 1000],
                "display_pump_time_ms": self.settings.pre_pump_ms,
                "rest_semantics": "hardware_frame_period_600000_divided_by_2MHz",
                "duration_model": "one_rest_period_slot_per_record_including_baselines_no_trailing_rest",
                "averaging": "corresponding_phase_across_complete_repetitions_keep_raw_records",
                "probe_timing": {
                    "optical_pulse_trigger_mode": "external_trigger",
                    "expected_opportunity_authority": "configured_and_read_back_T660-1_repetition_rate",
                    "t660_1_channels": {"CHA": "HF2LI DIO0 external reference", "CHB": "MIRcat TRIG IN", "CHC": "T660-2 TRIG IN"},
                    "t660_2_channels": {"CHA": "Nd:YAG FIRE", "CHB": "Q-switch", "CHC": "MIRcat Process Trigger"},
                    "t660_1_repetition_rate_hz": self.settings.probe_repetition_rate_hz,
                    "t660_1_trigger_width_ns": self.settings.probe_pulse_width_ns,
                    "mircat_internal_repetition_rate_hz": self.settings.mircat_internal_repetition_rate_hz,
                    "mircat_internal_pulse_width_ns": self.settings.mircat_internal_pulse_width_ns,
                    "mircat_internal_rate_margin_hz": self.mircat_internal_rate_margin_hz,
                },
            },
            "limitations": [
                ("Calibrated trajectory defines hardware delays; observed pump and scan timestamps define reconstruction."
                 if self.calibrated else "Uncalibrated preview only: acquisition requires a calibrated trajectory to replace these nominal bounds."),
                "Phase increment is not a claim of temporal resolution.",
                "Probe pulse count is nominal, not a measured detector sample count.",
                "The higher MIRcat internal rate is not the optical-opportunity rate or HF2LI reference.",
                "Duration excludes initialization, return, settling, and additional sample recovery.",
                "QCL/current, acquisition/filter settings, and calibration require an instrument preset.",
                PHASE_SCAN_EXECUTION_BLOCKER,
            ],
        }


def build_phase_scan_plan(settings: PhaseScanSettings, *,
                          calibrated_trajectory: dict[str, Any] | None = None) -> PhaseScanPlan:
    """Derive phase bounds from calibrated sweep times at requested wavenumbers.

    Without calibration, return an explicitly provisional UI preview. That
    preview must be replaced by a calibrated plan before acquisition is armed.
    Trajectory times are relative to the MIRcat Process Trigger, so Sweep Active
    referenced calibrations must also supply the measured trigger-to-active delay.
    """
    for name, value in asdict(settings).items():
        if name == "pump_reference":
            if value != "electrical_sync":
                raise PhaseScanPlanError("Phase-scan pump timing must use synchronized DIO17 electrical sync")
        elif name == "pre_pump_ms":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise PhaseScanPlanError(f"{name} must be finite")
            if name == "pre_pump_ms" and value < 0:
                raise PhaseScanPlanError("Before Pump must not be negative")
        elif name == "repetitions":
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise PhaseScanPlanError(f"{name.replace('_', ' ').title()} must be a positive whole number")
        elif (
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0
        ):
            raise PhaseScanPlanError(f"{name.replace('_', ' ')} must be a finite positive number")

    span = abs(_fraction(settings.stop_wavenumber_cm1) - _fraction(settings.start_wavenumber_cm1))
    if span == 0:
        raise PhaseScanPlanError("Start and Stop Wavenumber must differ")
    scan_s = span / _fraction(settings.scan_speed_cm1_s)
    earliest_s, latest_s, source = 0., float(scan_s), None
    if calibrated_trajectory is not None:
        earliest_s, latest_s, source = _trajectory_bounds(settings, calibrated_trajectory)
        scan_s = _fraction(latest_s) - _fraction(earliest_s)
    step_s = _fraction(settings.phase_delay_us) / 1_000_000
    first_tick = math.floor((-_fraction(latest_s) - _fraction(settings.pre_pump_ms) / 1000) / step_s)
    last_tick = math.ceil((_fraction(settings.post_pump_ms) / 1000 - _fraction(earliest_s)) / step_s)
    phase_count = last_tick - first_tick + 1
    last_phase_s = last_tick * step_s
    duty = (
        _fraction(settings.probe_repetition_rate_hz)
        * _fraction(settings.probe_pulse_width_ns) / 1_000_000_000
    )
    if duty > Fraction(3, 10):
        raise PhaseScanPlanError(
            f"T660-1 trigger duty cycle is {float(duty):.3%}; reduce trigger rate or width "
            "to stay within the retained 30% ceiling. MIRcat internal duty is checked separately."
        )
    internal_rate = _fraction(settings.mircat_internal_repetition_rate_hz)
    if internal_rate <= _fraction(settings.probe_repetition_rate_hz):
        raise PhaseScanPlanError(
            "MIRcat internal repetition rate must be higher than the T660-1 trigger rate "
            "to retain trigger-acceptance headroom"
        )
    internal_duty = internal_rate * _fraction(settings.mircat_internal_pulse_width_ns) / 1_000_000_000
    if internal_duty > Fraction(3, 10):
        raise PhaseScanPlanError(
            f"MIRcat internal duty cycle is {float(internal_duty):.3%}; reduce its internal "
            "rate or pulse width to stay within the 30% ceiling. Device-specific limits still require readback."
        )
    if _fraction(settings.rest_period_s) < Fraction(1, 10):
        raise PhaseScanPlanError("Rest Period must be at least 0.1 s for the installed 10 Hz pump limit")
    if not math.isclose(settings.probe_repetition_rate_hz, 2_000_000., rel_tol=0., abs_tol=1e-6):
        raise PhaseScanPlanError("Phase-scan clock must be 2 MHz for the 600000 trigger predivider")
    if not math.isclose(settings.rest_period_s, .3, rel_tol=0., abs_tol=1e-9):
        raise PhaseScanPlanError("Frame period must be 0.3 s (600000 / 2 MHz)")
    occupied_s = max(-first_tick * step_s, last_phase_s + _fraction(latest_s)) + Fraction(11, 1000)
    if _fraction(settings.rest_period_s) < occupied_s:
        raise PhaseScanPlanError(
            f"Rest Period must be at least {float(occupied_s):.9g} s "
            "to finish the latest delayed scan and trigger pulse before the next pump event"
        )
    return PhaseScanPlan(settings, phase_count, float(scan_s), first_tick,
                         (earliest_s, latest_s), source)


def _fraction(value: float) -> Fraction:
    return Fraction(str(value))


def _trajectory_bounds(settings: PhaseScanSettings, trajectory: dict[str, Any]) -> tuple[float, float, str]:
    source = str(trajectory.get("source_id") or "").strip()
    if not source:
        raise PhaseScanPlanError("Calibrated trajectory requires a human-readable source_id")
    try:
        times = [float(value) for value in trajectory["time_s"]]
        wavenumbers = [float(value) for value in trajectory["wavenumber_cm1"]]
    except (KeyError, TypeError, ValueError) as exc:
        raise PhaseScanPlanError("Calibrated trajectory requires time_s and wavenumber_cm1 arrays") from exc
    if (len(times) != len(wavenumbers) or len(times) < 2 or
            any(not math.isfinite(value) for value in times + wavenumbers) or
            any(right <= left for left, right in zip(times, times[1:]))):
        raise PhaseScanPlanError("Calibrated trajectory must contain aligned finite values with strictly increasing times")
    direction = 1 if settings.stop_wavenumber_cm1 > settings.start_wavenumber_cm1 else -1
    if any((right-left)*direction <= 0 for left, right in zip(wavenumbers, wavenumbers[1:])):
        raise PhaseScanPlanError("Calibrated trajectory must be monotonic in the requested sweep direction")
    if "scan_speed_cm1_s" in trajectory and not math.isclose(
            float(trajectory["scan_speed_cm1_s"]), settings.scan_speed_cm1_s, rel_tol=1e-9):
        raise PhaseScanPlanError("Calibrated trajectory does not match the requested scan speed")
    reference = trajectory.get("time_reference", "process_trigger")
    offset = 0.
    if reference == "sweep_active":
        try:
            offset = float(trajectory["sweep_active_delay_s"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PhaseScanPlanError("Sweep Active trajectory requires a measured sweep_active_delay_s") from exc
        if not math.isfinite(offset) or offset < 0:
            raise PhaseScanPlanError("sweep_active_delay_s must be finite and nonnegative")
    elif reference != "process_trigger":
        raise PhaseScanPlanError("Trajectory time_reference must be process_trigger or sweep_active")
    if direction < 0:
        wavenumbers, times = wavenumbers[::-1], times[::-1]
    def time_at(wavenumber):
        if not wavenumbers[0] <= wavenumber <= wavenumbers[-1]:
            raise PhaseScanPlanError("Calibrated trajectory does not bracket the requested wavenumber range")
        index = min(max(1, bisect_right(wavenumbers, wavenumber)), len(wavenumbers)-1)
        fraction = (wavenumber-wavenumbers[index-1]) / (wavenumbers[index]-wavenumbers[index-1])
        return times[index-1] + fraction*(times[index]-times[index-1]) + offset
    selected = [time_at(settings.start_wavenumber_cm1), time_at(settings.stop_wavenumber_cm1)]
    if min(selected) < 0:
        raise PhaseScanPlanError("Calibrated sweep times must follow the Process Trigger")
    return min(selected), max(selected), source


def partition_frame_blocks(events, *, capacity: int = 8192) -> tuple[tuple, ...]:
    """Partition a complete nominal sequence into the fewest bounded tables.

    Rebalance a final singleton where possible to avoid an extra inert trigger.
    A genuinely one-record acquisition uses the service's inert terminator.
    """
    if isinstance(capacity, bool) or not isinstance(capacity, int) or not 2 <= capacity <= 8192:
        raise PhaseScanPlanError("Verified T660 frame capacity must be an integer in 2..8192")
    values = tuple(events)
    blocks = [values[start:start+capacity] for start in range(0, len(values), capacity)]
    if len(blocks) > 1 and len(blocks[-1]) == 1 and len(blocks[-2]) >= 3:
        blocks[-1] = blocks[-2][-1:] + blocks[-1]
        blocks[-2] = blocks[-2][:-1]
    return tuple(blocks)


def derive_capture_window(qualified_sweep_active_s: float, *, pretrigger_s: float = .0001,
                          target_duration_s: float = .0026, posttrigger_margin_s: float = .00018,
                          sample_rate_hz: float | None = None) -> dict[str, float]:
    """Cover qualified Sweep Active plus margins, rounding outward to the grid."""
    values = [qualified_sweep_active_s, pretrigger_s, target_duration_s, posttrigger_margin_s]
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
           not math.isfinite(value) or value <= 0 for value in values):
        raise PhaseScanPlanError("Capture duration qualification and margins must be finite positive values")
    duration = max(target_duration_s, pretrigger_s + qualified_sweep_active_s + posttrigger_margin_s)
    pretrigger = pretrigger_s
    if sample_rate_hz is not None:
        if not math.isfinite(sample_rate_hz) or sample_rate_hz <= 0:
            raise PhaseScanPlanError("Capture sample-rate readback must be finite and positive")
        pretrigger = math.ceil(pretrigger * sample_rate_hz) / sample_rate_hz
        duration = math.ceil(max(duration, pretrigger + qualified_sweep_active_s + posttrigger_margin_s)
                             * sample_rate_hz) / sample_rate_hz
    return {"duration_s": duration, "pretrigger_s": pretrigger,
            "qualified_sweep_active_s": float(qualified_sweep_active_s),
            "posttrigger_margin_s": duration-pretrigger-qualified_sweep_active_s}
