"""Hardware-free scientific readiness, deterministic blocks and complete budgets."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
import math
from typing import Any, Mapping

from .settings import (CONDITION_PROFILES, EXPERIMENT_ID, SETTINGS_VERSION,
                       StroboscopySettings, ResponseSettings, TimingSettings)
from .timing import TimingProgram, compile_timing

PLAN_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Qualification:
    """Detached optional historical profile; ordinary acquisition needs none."""
    data: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Qualification":
        import copy
        payload = value.get("microsecond_stroboscopy", value)
        return cls(copy.deepcopy(dict(payload)))

    def to_dict(self) -> dict[str, Any]:
        import copy
        return copy.deepcopy(dict(self.data))

    @property
    def profile_id(self) -> str:
        return str(self.data.get("profile_id", ""))


@dataclass(frozen=True)
class InstalledCapabilities:
    """Detached readbacks; no SDK discovery occurs in construction or planning."""
    data: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "InstalledCapabilities":
        import copy
        return cls(copy.deepcopy(dict(value)))

    def to_dict(self) -> dict[str, Any]:
        import copy
        return copy.deepcopy(dict(self.data))


@dataclass(frozen=True)
class ReadinessIssue:
    code: str
    message: str
    severity: str  # error = physically invalid, blocker = readiness, warning = science


@dataclass(frozen=True)
class Readiness:
    issues: tuple[ReadinessIssue, ...]

    @property
    def errors(self) -> tuple[str, ...]:
        return tuple(issue.message for issue in self.issues if issue.severity == "error")

    @property
    def blockers(self) -> tuple[str, ...]:
        return tuple(issue.message for issue in self.issues if issue.severity == "blocker")

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(issue.message for issue in self.issues if issue.severity == "warning")

    @property
    def hardware_ready(self) -> bool:
        return not self.errors and not self.blockers

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {"errors": list(self.errors), "blockers": list(self.blockers),
                "warnings": list(self.warnings), "hardware_ready": self.hardware_ready,
                "issues": [asdict(issue) for issue in self.issues]}


@dataclass(frozen=True)
class AcquisitionBlock:
    block_id: str
    kind: str  # sequential_blank, preliminary, baseline, pump_blocked, pumped
    wavelength_index: int
    wavenumber_cm1: float
    label: str
    spectral_role: str
    delay_index: int | None = None
    delay_us: float | None = None
    average_index: int | None = None
    event_index: int | None = None
    expected_pump_events: int = 0
    capture_duration_s: float = 0.0
    recovery_wait_s: float = 0.0
    reset_verification_s: float = 0.0
    physical_frame_count: int = 0
    timing_program: TimingProgram | None = None
    requires_reset_equivalence: bool = False


@dataclass(frozen=True)
class DurationBudget:
    configuration_s: float = 0.0
    tuning_s: float = 0.0
    detector_settling_s: float = 0.0
    sequential_blank_s: float = 0.0
    preliminary_s: float = 0.0
    baseline_s: float = 0.0
    pump_blocked_s: float = 0.0
    pumped_capture_s: float = 0.0
    recovery_s: float = 0.0
    reset_verification_s: float = 0.0
    post_run_verification_s: float = 0.0
    acquisition_guard_s: float = 0.0
    protocol_s: float = 0.0
    upload_s: float = 0.0
    retrieval_s: float = 0.0
    restoration_s: float = 0.0
    saving_s: float = 0.0
    analysis_s: float = 0.0
    physical_actions_s: float = 0.0
    event_count: int = 0
    control_event_count: int = 0
    blank_control_event_count: int = 0
    total_block_count: int = 0
    total_frame_count: int = 0
    native_sample_count: int = 0
    memory_bytes: int = 0
    storage_bytes: int = 0
    wall_clock_s: float = 0.0
    estimate_basis: str = "Provisional non-overlap estimate with maintained T660 command delays, native subscription overhead and cumulative retention; transport, integrity checks, tuning and saving durations vary"
    open_ended_actions: tuple[str, ...] = ()

    @property
    def total_duration_s(self) -> float:
        return self.wall_clock_s

    @property
    def duration_s(self) -> float:
        return self.wall_clock_s

    @property
    def pump_events(self) -> int:
        return self.event_count

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StroboscopyPlan:
    settings: StroboscopySettings
    blocks: tuple[AcquisitionBlock, ...]
    budget: DurationBudget
    readiness: Readiness
    values: Mapping[str, Mapping[str, Any]]
    condition_profile: Mapping[str, Any]
    observable: str = "Continuous-probe HF2LI envelope; aperture average referenced to observed electrical Variable Sync, with optical correction only when measured"
    plan_schema_version: int = PLAN_SCHEMA_VERSION
    experiment_id: str = EXPERIMENT_ID

    @property
    def mode(self) -> str:
        return self.settings.mode

    @property
    def errors(self) -> tuple[str, ...]:
        return self.readiness.errors

    @property
    def warnings(self) -> tuple[str, ...]:
        return self.readiness.warnings

    @property
    def hardware_ready(self) -> bool:
        return self.readiness.hardware_ready

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["settings"] = self.settings.to_dict()
        value["readiness"] = self.readiness.to_dict()
        return value


def _number(value: Any, *, minimum: float | None = None, strict: bool = False) -> bool:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        return False
    return minimum is None or (value > minimum if strict else value >= minimum)


def _integer(value: Any, minimum: int = 0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _payload(value: Qualification | InstalledCapabilities | Mapping | None) -> dict[str, Any]:
    return {} if value is None else value.to_dict() if hasattr(value, "to_dict") else dict(value)


def resolve_settings(settings: StroboscopySettings | Mapping[str, Any],
                     capabilities: InstalledCapabilities | Mapping[str, Any] | None = None) -> StroboscopySettings:
    """Derive dependent settings from the delay grid and actual installed menus.

    Every dotted path in ``manual_overrides`` is independently preserved. Without
    connected menus, numerical values remain provisional requests, never invented
    capability observations. The acquisition adapter validates actual readbacks.
    """
    if not isinstance(settings, StroboscopySettings):
        settings = StroboscopySettings.from_dict(settings)
    if not settings.delays_us or any(not _number(v) for v in settings.delays_us):
        return settings
    data, caps = settings.to_dict(), _payload(capabilities)
    manual = set(settings.manual_overrides)
    for path in manual:
        section, separator, field_name = path.partition(".")
        if not separator or section not in ("response", "timing", "reset", "controls", "budget") or field_name not in data[section]:
            raise ValueError(f"Unknown Advanced override {path!r}")
    def automatic(section: str, name: str, value: Any) -> None:
        if f"{section}.{name}" not in manual:
            data[section][name] = value
    automatic("reset", "method", "passive_recovery")
    actual = caps.get("actual_values", {})
    timing_readbacks = caps.get("timing_settings", {})
    for section, defaults, names in (
        ("response", ResponseSettings(), ("hf2_order", "hf2_time_constant_s", "reference_order", "reference_time_constant_s",
          "sample_rate_sps", "reference_rate_sps", "timing_rate_sps",
          "detector_latency_s", "reference_latency_s", "jitter_s", "time_zero_s", "reference_alignment_uncertainty_s")),
        ("timing", TimingSettings(), ("probe_rate_hz", "probe_width_ns", "reference_width_ns", "frame_input_width_ns",
          "probe_delay_ns", "fire_to_q_us", "fire_width_us", "q_switch_width_us", "command_guard_us")),
    ):
        for name in names:
            value = actual.get(f"{section}.{name}", timing_readbacks.get(name) if section == "timing" else None)
            automatic(section, name, value if value is not None else getattr(defaults, name))
    gaps = [b-a for a,b in zip(sorted(set(settings.delays_us)), sorted(set(settings.delays_us))[1:]) if b>a]
    step_s = min(gaps) * 1e-6 if gaps else max(abs(settings.delays_us[0])*1e-6, 25e-6)
    target_tc = max(.8e-6, step_s/4)
    desired_aperture = max(step_s/2, 1e-6)
    r = data["response"]
    roles = (("sample", "hf2_order", "hf2_time_constant_s", "sample_rate_sps"),)
    if settings.mode == "dual":
        roles += (("reference", "reference_order", "reference_time_constant_s", "reference_rate_sps"),)
    for role, order_field, tc_field, rate_field in roles:
        profile = _detector_capabilities(caps, role) if caps.get("verified") else {}
        orders = tuple(value for value in profile.get("orders", ()) if _integer(value, 1) and value <= 8)
        constants = profile.get("timeconstants_by_order", {})
        rates = tuple(value for value in profile.get("rates_sps", ()) if _number(value, minimum=0, strict=True) and value <= 231_000)
        candidates = []
        for order in orders:
            if "response."+order_field in manual and order != r[order_field]:
                continue
            for tc in constants.get(order, constants.get(str(order), ())):
                if not _number(tc, minimum=.8e-6):
                    continue
                if "response."+tc_field in manual and not math.isclose(tc, r[tc_field], rel_tol=1e-9, abs_tol=1e-15):
                    continue
                candidates.append((order, tc))
        if candidates:
            # Choose the least filtering sufficient for the requested grid; no
            # biological lifetime or other experiment's filter default enters.
            order, tc = min(candidates, key=lambda item: (abs(item[0]-1), abs(math.log(item[1]/target_tc))))
            automatic("response", order_field, order)
            automatic("response", tc_field, tc)
        elif not caps.get("verified"):
            automatic("response", order_field, 1)
            automatic("response", tc_field, target_tc)
        if rates:
            target_rate = 3/desired_aperture
            adequate = [rate for rate in rates if rate >= target_rate]
            automatic("response", rate_field, min(adequate) if adequate else max(rates))
    if caps.get("verified") and _number(caps.get("timing_rate_sps"), minimum=0, strict=True):
        automatic("response", "timing_rate_sps", caps["timing_rate_sps"])
    active_rates = [r["sample_rate_sps"]] + ([r["reference_rate_sps"]] if settings.mode == "dual" else [])
    if all(_number(rate, minimum=0, strict=True) for rate in active_rates):
        automatic("response", "integration_aperture_s", max(desired_aperture, 3/min(active_rates)))
    t = data["timing"]
    if all(_number(t[name], minimum=0, strict=True) for name in ("fire_to_q_us", "command_guard_us", "q_switch_width_us", "fire_width_us")) and _number(r["integration_aperture_s"], minimum=0, strict=True):
        aperture = r["integration_aperture_s"]
        target = max(0., max(settings.delays_us))*1e-6+t["fire_to_q_us"]*1e-6+t["command_guard_us"]*1e-6+aperture/2
        final_edge = max(target-min(settings.delays_us)*1e-6+t["q_switch_width_us"]*1e-6,
                         target+aperture/2)
        automatic("timing", "event_interval_s", max(.001, math.ceil((final_edge+2e-6)/.001)*.001))
    if _number(settings.event_spacing_s, minimum=0, strict=True) and _number(t["event_interval_s"], minimum=0, strict=True):
        # Complete capture and next aperture geometry contribute to event
        # spacing. Waiting is a minimum separation, never a precise edge clock.
        span_s = (max(settings.delays_us)-min(settings.delays_us))*1e-6
        # Budget estimates never shorten the requested physical wait. Only the
        # programmed capture and explicit observation duration contribute here.
        overhead = 3*t["event_interval_s"]+data["reset"]["verification_duration_s"]
        if _number(overhead, minimum=0):
            automatic("reset", "recovery_wait_s", max(0., settings.event_spacing_s-overhead+span_s))
    _retain_selections(settings, data, basis="Automatic dependent choice from requested delays and installed readbacks where available")
    return StroboscopySettings.from_dict(data)


def acquisition_signature(settings: StroboscopySettings | Mapping[str, Any], *, kind: str | None = None) -> dict[str, Any]:
    """Physical acquisition compatibility, excluding optional historical data.

    Blank/preliminary reuse does not depend on requested event count or delays;
    callers independently verify that the retained native coverage is adequate.
    """
    if isinstance(settings, Mapping) and "wavenumbers_cm1" in settings:
        import copy
        signature = copy.deepcopy(dict(settings))
        if kind in ("blank", "preliminary", "baseline", "control"):
            for key in ("delays_us", "averages", "event_spacing_s", "delay_order", "reset", "controls"):
                signature.pop(key, None)
            signature.get("response", {}).pop("integration_aperture_s", None)
            signature["timing"] = {key: value for key, value in signature.get("timing", {}).items()
                if key in ("probe_rate_hz", "probe_width_ns", "reference_width_ns", "probe_delay_ns")}
        return signature
    if not isinstance(settings, StroboscopySettings):
        settings = StroboscopySettings.from_dict(settings)
    response = asdict(settings.response)
    response.pop("qualified", None)
    response.pop("qualification_id", None)
    signature = {"experiment_id": settings.experiment_id, "mode": settings.mode,
        "wavenumbers_cm1": sorted(point.wavenumber_cm1 for point in settings.spectral_points),
        "response": response, "timing": asdict(settings.timing)}
    if kind not in ("blank", "preliminary", "baseline", "control"):
        signature.update(delays_us=list(settings.delays_us), averages=settings.averages,
            event_spacing_s=settings.event_spacing_s, delay_order=settings.delay_order,
            reset={key: getattr(settings.reset, key) for key in ("recovery_wait_s", "verification_duration_s", "tolerance_fraction")},
            controls={key: getattr(settings.controls, key) for key in ("baseline_duration_s", "preliminary_duration_s", "pump_blocked_averages")})
    else:
        # Stationary controls have no transient aperture or frame phase. Their
        # detector filtering and native support still must match/be adequate.
        signature["response"].pop("integration_aperture_s", None)
        signature["timing"] = {key: value for key, value in signature["timing"].items()
            if key in ("probe_rate_hz", "probe_width_ns", "reference_width_ns", "probe_delay_ns")}
    return signature


acquisition_compatibility = acquisition_signature


def build_plan(settings: StroboscopySettings | Mapping[str, Any],
               capabilities: InstalledCapabilities | Mapping[str, Any] | None = None,
               qualification: Qualification | Mapping[str, Any] | None = None, *, kind: str = "run") -> StroboscopyPlan:
    """Return an inspectable plan even when live readiness is unavailable."""
    if not isinstance(settings, StroboscopySettings):
        settings = StroboscopySettings.from_dict(settings)
    cap, qual = _payload(capabilities), _payload(qualification)
    issues: list[ReadinessIssue] = []
    def issue(code: str, message: str, severity: str = "error") -> None:
        issues.append(ReadinessIssue(code, message, severity))
    try:
        settings = resolve_settings(settings, cap)
    except (ValueError, TypeError, OverflowError) as exc:
        issue("dependent_settings", str(exc))
    s, r, t = settings, settings.response, settings.timing
    if kind not in ("run", "blank", "preliminary"):
        issue("operation_kind", "Operation kind must be run, blank or preliminary")
    if kind == "blank" and s.mode == "dual":
        issue("dual_blank", "Dual mode records its reference simultaneously; a separate full blank operation is not supported")
    if s.experiment_id != EXPERIMENT_ID or s.settings_version != SETTINGS_VERSION:
        issue("settings_identity", "Plan experiment/schema is incompatible with microsecond_stroboscopy v1")
    if s.mode not in ("single", "dual"):
        issue("detector_mode", "Detector mode must be single or dual")
    profile = CONDITION_PROFILES.get(s.condition_profile_id)
    if s.execution_mode not in ("simulation", "hardware"):
        issue("execution_mode", "Execution mode must be simulation or hardware")
    if s.delay_order not in ("ascending", "descending", "alternating"):
        issue("delay_order", "Delay order must be ascending, descending or alternating")
    if not _integer(s.averages, 1):
        issue("averages", "Averages must be a positive integer")
    if not _number(s.event_spacing_s, minimum=.1):
        issue("event_spacing", "Requested event spacing must be finite and at least 100 ms for the installed 10 Hz pump limit")
    if not s.spectral_points or len(s.spectral_points) > 100_000:
        issue("spectral_points", "Declare between 1 and 100000 measured band/off-band spectral points")
    if any(not _number(p.wavenumber_cm1, minimum=0, strict=True) or p.role not in ("band", "off_band") for p in s.spectral_points):
        issue("spectral_axis", "Wavenumbers must be positive finite cm⁻¹ with band/off_band roles")
    if len({p.wavenumber_cm1 for p in s.spectral_points}) != len(s.spectral_points):
        issue("duplicate_wavenumber", "Duplicate spectral coordinates require explicit repeat blocks, not duplicate grid points")
    if not s.delays_us or len(s.delays_us) > 100_000 or any(not _number(v) for v in s.delays_us):
        issue("delay_grid", "Delay grid must contain 1–100000 finite values in microseconds")
    if len(set(s.delays_us)) != len(s.delays_us):
        issue("duplicate_delays", "Duplicate delays belong in averages; delay coordinates must be distinct")
    for name in ("hf2_order", "reference_order"):
        if not _integer(getattr(r, name), 1) or getattr(r, name) > 8:
            issue(name, f"HF2LI {name} must be an integer from 1 through 8")
    for name in ("hf2_time_constant_s", "reference_time_constant_s"):
        if not _number(getattr(r, name), minimum=.8e-6):
            issue(name, f"HF2LI {name} must be finite and at least the documented 0.8 µs minimum; validate actual readback")
    for name in ("sample_rate_sps", "reference_rate_sps", "timing_rate_sps", "integration_aperture_s"):
        if not _number(getattr(r, name), minimum=0, strict=True):
            issue(name, f"{name} must be finite and positive")
    for name in ("detector_latency_s", "reference_latency_s", "time_zero_s"):
        if not _number(getattr(r, name)):
            issue(name, f"{name} must be finite")
    for name in ("jitter_s", "reference_alignment_uncertainty_s"):
        if not _number(getattr(r, name), minimum=0):
            issue(name, f"{name} must be finite and nonnegative")
    active_demods = [r.sample_demodulator, r.timing_demodulator] + ([r.reference_demodulator] if s.mode == "dual" else [])
    if any(not _integer(v) or v > 5 for v in active_demods) or len(set(active_demods)) != len(active_demods):
        issue("demodulator_roles", "Detector and timing roles require distinct installed demodulators from 0 through 5")
    if (r.sample_demodulator, r.reference_demodulator, r.timing_demodulator) != (0, 3, 2):
        issue("installed_demodulator_roles", "Installed adapter supports sample demodulator 0 (Signal 1), reference 3 (Signal 2) and timing 2; other mappings require qualified adapter support")
    if t.timing_marker_dio_bit != 17:
        issue("timing_marker_route", "Installed timing adapter observes Variable Sync on HF2LI DIO17; no independently positioned DIO1 gate is connected")
    rates = [r.sample_rate_sps, r.timing_rate_sps] + ([r.reference_rate_sps] if s.mode == "dual" else [])
    if all(_number(v, minimum=0, strict=True) for v in rates):
        if any(v > 231_000 for v in rates):
            issue("stream_rate", "Two or three active HF2LI streams cannot each exceed approximately 230 kSa/s (actual divisor readback required)")
        if sum(rates) > 700_000:
            issue("aggregate_rate", "Aggregate sample/reference/timing rate exceeds HF2LI 700 kSa/s readout capacity")
    for name in ("recovery_wait_s", "verification_duration_s", "tolerance_fraction", "maximum_wait_s"):
        if not _number(getattr(s.reset, name), minimum=0, strict=name != "recovery_wait_s"):
            issue(name, f"Reset {name} must be finite and {'nonnegative' if name == 'recovery_wait_s' else 'positive'}")
    if s.reset.method not in ("passive_recovery", "manual_thermal_reset", "manual_fresh_position", "manual_replacement"):
        issue("reset_method", "Unknown reset method; no automatic stage, flow or temperature adapter is installed")
    if not _integer(s.controls.pump_blocked_averages):
        issue("control_count", "Pump-blocked averages must be a nonnegative integer")
    for name in ("baseline_duration_s", "preliminary_duration_s", "physical_action_allowance_s"):
        if not _number(getattr(s.controls, name), minimum=0, strict=name != "physical_action_allowance_s"):
            issue(name, f"Control {name} must be finite and nonnegative (capture windows strictly positive)")
    for item in fields(s.budget):
        value = getattr(s.budget, item.name)
        if not _number(value, minimum=0, strict=("bytes_per" in item.name or "maximum_" in item.name)):
            issue("budget_" + item.name, f"Budget {item.name} is invalid")
    # Historical condition, identity, calibration and review metadata never gate
    # ordinary native/relative acquisition. Actual instrument validation remains.
    if not cap or not cap.get("verified", False):
        issue("installed_readbacks", "Actual installed response/rate readbacks will be checked when devices are configured", "warning")
    elif numeric_values_safe(r):
        _check_capabilities(s, cap, issue)
    if not r.qualified:
        issue("response_qualification", "Optical response is not calibrated; preserve raw/relative observations without a resolved optical-lifetime claim", "warning")
    if not qual.get("timing", {}).get("optical_latency_calibration_id"):
        issue("optical_time_zero", "Delay is referenced to observed electrical timing; sample-plane optical arrival is not independently established", "warning")
    if s.mode == "dual" and not s.controls.background_record_id:
        issue("absolute_background", "No measured path-balance B: expose S/R and ΔA from Q/Q0, not absolute transmission/absorbance", "warning")
    if len([p for p in s.spectral_points if p.role == "band"]) < 3:
        issue("band_area_support", "Fewer than three band coordinates cannot support a local band-area claim", "warning")
    if len([p for p in s.spectral_points if p.role == "off_band"]) < 2:
        issue("off_band_support", "Add measured off-band controls on both sides where accessible", "warning")
    # Science warnings describe resolution; only physically invalid settings are errors.
    numeric_ok = not any(i.severity == "error" for i in issues)
    if numeric_ok:
        _science_warnings(s, issue)
    values: dict[str, dict[str, Any]] = {}
    for name, value in asdict(r).items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            path = "response." + name
            selection = next((item for item in s.value_selections if item.path == path and item.selected == value), None)
            values[path] = {"requested": selection.requested if selection else value, "selected": value,
                "actual": cap.get("actual_values", {}).get("response." + name),
                "basis": selection.basis if selection else "explicit requested value; actual connected readback required"}
    blocks: list[AcquisitionBlock] = []
    programs: dict[tuple[float, bool], TimingProgram] = {}
    if numeric_ok:
        try:
            programs = {(delay, pumped): compile_timing(s, [delay], pumped=pumped)
                        for delay in s.delays_us for pumped in (False, True)}
        except (ValueError, OverflowError) as exc:
            issue("timing_hardware", str(exc))
    if programs and not any(i.severity == "error" for i in issues):
        first_program = next(iter(programs.values()))
        values["timing.probe_rate_hz"] = {"requested": t.probe_rate_hz, "selected": first_program.input_frequency_hz,
            "actual": cap.get("actual_values", {}).get("timing.probe_rate_hz"), "basis": "T660 0.02 Hz DDS quantization"}
        values["timing.event_interval_s"] = {"requested": t.event_interval_s, "selected": first_program.frame_period_s,
            "actual": None, "basis": "integer predivider rounded upward; no optical cadence inferred"}
        blocks = _make_blocks(s, programs, kind=kind)
        elapsed, last_pump = 0.0, None
        for block in blocks:
            if block.expected_pump_events and block.timing_program:
                pump_time = elapsed + block.timing_program.events[0].q_command_time_s
                if last_pump is not None and pump_time - last_pump < 1 / t.maximum_pump_rate_hz - 1e-12:
                    issue("pump_cadence", "Scheduled biological pump commands are closer than the Surelite 10 Hz limit; increase recovery/frame duration")
                    break
                last_pump = pump_time
            elapsed += block.capture_duration_s + block.recovery_wait_s + block.reset_verification_s
    budget = _budget(s, blocks, kind=kind)
    if blocks and budget.memory_bytes > s.budget.maximum_memory_bytes:
        issue("memory_budget", f"Declared native capture needs {budget.memory_bytes} bytes; exceeds selected memory budget")
    if blocks and budget.storage_bytes > s.budget.maximum_storage_bytes:
        issue("storage_budget", f"Declared native preservation needs approximately {budget.storage_bytes} bytes; exceeds storage budget")
    return StroboscopyPlan(s, tuple(blocks), budget, Readiness(tuple(issues)), values,
                          asdict(profile) if profile else {})


def _check_qualification(s: StroboscopySettings, q: Mapping[str, Any], issue: Any) -> None:
    """Historical profile metadata is informational, never an acquisition gate."""
    if q.get("experiment_id") not in (None, EXPERIMENT_ID):
        issue("historical_profile", "Retained profile belongs to a different historical experiment; no operating values were applied", "warning")


def numeric_values_safe(response: Any) -> bool:
    return all(_number(value) for value in (response.hf2_order, response.reference_order,
        response.hf2_time_constant_s, response.reference_time_constant_s,
        response.sample_rate_sps, response.reference_rate_sps, response.timing_rate_sps))


def _close_to_any(value: float, choices: Any) -> bool:
    return any(_number(item) and math.isclose(value, item, rel_tol=1e-9, abs_tol=1e-15) for item in choices)


def _detector_capabilities(caps: Mapping[str, Any], role: str) -> Mapping[str, Any]:
    return caps.get(role, caps if role == "sample" else {})


def _check_capabilities(s: StroboscopySettings, caps: Mapping[str, Any], issue: Any) -> None:
    r = s.response
    roles = (("sample", r.hf2_order, r.hf2_time_constant_s, r.sample_rate_sps,
              "hf2_time_constant_s", "sample_rate_sps"),)
    if s.mode == "dual":
        roles += (("reference", r.reference_order, r.reference_time_constant_s, r.reference_rate_sps,
                   "reference_time_constant_s", "reference_rate_sps"),)
    actual = caps.get("actual_values", {})
    for role, order, tc, rate, tc_field, rate_field in roles:
        profile = _detector_capabilities(caps, role)
        orders = profile.get("orders", ())
        if not orders or not profile.get("rates_sps") or not profile.get("timeconstants_by_order"):
            order_field = "hf2_order" if role == "sample" else "reference_order"
            observed = (actual.get("response." + order_field), actual.get("response." + tc_field),
                        actual.get("response." + rate_field))
            if all(_close_to_any(selected, (readback,)) for selected, readback in zip((order, tc, rate), observed)):
                continue
            issue("capability_menu_" + role, f"Connected {role} order, time-constant and rate readback menus are incomplete, and exact selected-setting readbacks are unavailable", "error")
            continue
        if order not in orders:
            issue("unsupported_order_" + role, f"Requested {role} HF2 order {order} was not accepted by installed-device capability discovery")
        constants = profile.get("timeconstants_by_order", {})
        menu = constants.get(order, constants.get(str(order), ()))
        if not _close_to_any(tc, menu) and not _close_to_any(tc, (actual.get("response." + tc_field),)):
            issue("manual_tc_" + role, f"Requested {role} time constant {tc:g} s lacks an accepted idempotent readback for order {order}; choose a supported value or explicitly validate the manual override", "error")
        if not _close_to_any(rate, profile["rates_sps"]) and not _close_to_any(rate, (actual.get("response." + rate_field),)):
            issue("manual_rate_" + role, f"Requested {role} rate {rate:g} Sa/s is not an installed readback value; choose a supported actual rate (do not relabel its quantization)", "error")
    timing = caps.get("timing_rate_sps")
    if not _number(timing, minimum=0, strict=True):
        issue("timing_rate_capability", "Connected timing-stream rate readback is unavailable", "error")
    elif not math.isclose(r.timing_rate_sps, timing, rel_tol=1e-9, abs_tol=1e-9):
        issue("timing_rate_selection", f"Requested timing rate {r.timing_rate_sps:g} differs from connected {timing:g} Sa/s; use the actual selected value", "error")
    expected = (0, 2, 3) if s.mode == "dual" else (0, 2)
    if tuple(sorted(caps.get("enabled_streams", ()))) != expected:
        issue("active_streams", f"Connected active streams must be {expected}; aggregate bandwidth with additional streams is unverified", "error")
    maximum = caps.get("aggregate_rate_limit_sps", 700_000.)
    total = r.sample_rate_sps + r.timing_rate_sps + (r.reference_rate_sps if s.mode == "dual" else 0)
    if not _number(maximum, minimum=0, strict=True) or total > min(maximum, 700_000.):
        issue("installed_aggregate_rate", "Selected sample/reference/timing streams exceed connected aggregate throughput")


def select_supported_response(settings: StroboscopySettings,
                              capabilities: InstalledCapabilities | Mapping[str, Any],
                              *, preserve_fields: tuple[str, ...] = ()) -> StroboscopySettings:
    """Explicit automatic-choice action using actual independently read settings.

    Nearest supported rate/time constant is selected only when this function is
    deliberately invoked; build_plan itself preserves every manual input.
    ``preserve_fields`` contains response field names or ``response.<name>``.
    """
    caps = _payload(capabilities)
    if not caps.get("verified"):
        raise ValueError("Automatic supported choices require verified installed capability readbacks")
    result = settings.to_dict()
    response = result["response"]
    preserve = {name.removeprefix("response.") for name in preserve_fields}
    roles = (("sample", "hf2_order", "hf2_time_constant_s", "sample_rate_sps"),)
    if settings.mode == "dual":
        roles += (("reference", "reference_order", "reference_time_constant_s", "reference_rate_sps"),)
    for role, order_field, tc_field, rate_field in roles:
        profile = _detector_capabilities(caps, role)
        orders, rates = profile.get("orders", ()), profile.get("rates_sps", ())
        if not orders or not rates:
            raise ValueError(f"Incomplete installed {role} capability menus")
        if order_field not in preserve:
            response[order_field] = min(orders, key=lambda value: abs(value - response[order_field]))
        order = response[order_field]
        constants = profile.get("timeconstants_by_order", {})
        menu = constants.get(order, constants.get(str(order), ()))
        if not menu:
            raise ValueError(f"No installed time constants for {role} order {order}")
        if tc_field not in preserve:
            response[tc_field] = min(menu, key=lambda value: abs(math.log(value / response[tc_field])))
        if rate_field not in preserve:
            response[rate_field] = min(rates, key=lambda value: abs(math.log(value / response[rate_field])))
    if "timing_rate_sps" not in preserve:
        rate = caps.get("timing_rate_sps")
        if not _number(rate, minimum=0, strict=True):
            raise ValueError("Installed timing-stream rate is unavailable")
        response["timing_rate_sps"] = rate
    _retain_selections(settings, result, basis="Explicit automatic choice from installed idempotent readback menus")
    return StroboscopySettings.from_dict(result)


def capabilities_from_readbacks(settings: StroboscopySettings,
                               readbacks: Mapping[str, Any]) -> InstalledCapabilities:
    """Translate the installed adapter's preserved HF2 settings into evidence.

    Every active role and enable comes from returned LabOne nodes; missing nodes
    are left missing and cause readiness failure. No settings are fabricated.
    """
    nodes = readbacks.get("hf2li", {}).get("nodes", {})
    device_id = readbacks.get("hf2li_device")
    if not device_id or not nodes:
        return InstalledCapabilities.from_dict({"verified": False})
    def node(index: int, name: str) -> Any:
        return nodes.get(f"/{device_id}/demods/{index}/{name}", {}).get("value")
    actual = {}
    # The adapter retains the timing actually selected/configured during prepare.
    # Carry it through the HF-only connected replan so Auto does not revert to a
    # provisional nominal clock after that clock was configured differently.
    configured_timing = readbacks.get("actual_settings", {}).get("timing", {})
    for field_name in asdict(settings.timing):
        value = configured_timing.get(field_name)
        if value is not None:
            actual["timing." + field_name] = value
    for field_name, index, suffix in (("hf2_order", 0, "order"), ("hf2_time_constant_s", 0, "timeconstant"),
        ("sample_rate_sps", 0, "rate"), ("reference_order", 3, "order"),
        ("reference_time_constant_s", 3, "timeconstant"), ("reference_rate_sps", 3, "rate"),
        ("timing_rate_sps", 2, "rate")):
        value = node(index, suffix)
        if value is not None:
            actual["response." + field_name] = value
    enables = [node(i, "enable") for i in range(6)]
    result = {"verified": not readbacks.get("hf2li", {}).get("read_errors") and all(value in (0, 1) for value in enables),
              "device_id": device_id, "actual_values": actual,
              "enabled_streams": tuple(i for i, value in enumerate(enables) if value == 1),
              "timing_rate_sps": node(2, "rate"), "source": "preserved connected selected-setting readbacks"}
    return InstalledCapabilities.from_dict(result)


def _science_warnings(s: StroboscopySettings, issue: Any) -> None:
    r = s.response
    positive = sorted(v for v in s.delays_us if v >= 0)
    width_us = r.effective_sigma_s * 1e6
    spacings = [b - a for a, b in zip(sorted(s.delays_us), sorted(s.delays_us)[1:])]
    if spacings and min(spacings) < width_us:
        issue("subresponse_grid", f"Smallest programmed delay step is below the estimated {width_us:.3g} µs RMS response; finer steps do not improve physical response", "warning")
    if min(s.delays_us) >= -3 * width_us:
        issue("negative_delay", "Negative-delay controls do not extend beyond three estimated response widths", "warning")
    if positive and max(positive) < 8 * width_us:
        issue("recovery_coverage", "Observation window spans fewer than eight response widths; recovery/offset may remain unidentifiable", "warning")
    if r.integration_aperture_s * r.sample_rate_sps < 2:
        issue("aperture_sampling", "Sample aperture contains fewer than two expected native HF2 points; preserve missing support rather than interpolate", "warning")
    if s.mode == "dual" and r.integration_aperture_s * r.reference_rate_sps < 2:
        issue("reference_sampling", "Reference aperture contains fewer than two expected native points; matched support may be absent", "warning")
    if _number(s.timing.probe_rate_hz, minimum=0, strict=True) and 1 / s.timing.probe_rate_hz > r.effective_sigma_s:
        issue("probe_period", "Probe period exceeds the modeled response width; calibrate sampled carrier response before claiming resolved kinetics", "warning")
    if s.mode == "dual" and (r.hf2_order != r.reference_order or r.hf2_time_constant_s != r.reference_time_constant_s
                              or r.detector_latency_s != r.reference_latency_s):
        issue("dual_response_mismatch", "Detector filters/latencies differ; model both responses and match calibrated delay support before forming S/R", "warning")
    if s.controls.pump_blocked_averages == 0:
        issue("pump_blocked_missing", "No in-run pump-blocked delay control is scheduled", "warning")
    issue("recovery_not_assumed", "Final sampled delay does not demonstrate recovery by itself; observed pre/post-state and reset criteria decide acceptance", "warning")


def _make_blocks(s: StroboscopySettings, programs: Mapping[tuple[float, bool], TimingProgram], *, kind: str = "run") -> list[AcquisitionBlock]:
    result: list[AcquisitionBlock] = []
    pump_index = 0
    def append(wi: int, kind: str, *, duration: float = 0, delay_index: int | None = None,
               average_index: int | None = None, program: TimingProgram | None = None) -> None:
        nonlocal pump_index
        point = s.spectral_points[wi]
        pumped = kind == "pumped"
        delay = None if delay_index is None else s.delays_us[delay_index]
        result.append(AcquisitionBlock(f"w{wi:05d}-{kind}-{len(result):08d}", kind, wi,
            point.wavenumber_cm1, point.label, point.role, delay_index, delay, average_index,
            pump_index if pumped else None, int(pumped), program.duration_s if program else duration,
            s.reset.recovery_wait_s if pumped else 0, s.reset.verification_duration_s if pumped else 0,
            program.physical_frame_count if program else 0, program, False))
        pump_index += int(pumped)
    # Optional blank/preliminary operations are budgeted when explicitly chosen.
    # Normal Sample/Start covers only its own acquisition, without review gates.
    if kind == "blank":
        for wi in range(len(s.spectral_points)):
            append(wi, "sequential_blank", duration=s.controls.baseline_duration_s)
            for average in range(s.averages):
                for di in range(len(s.delays_us)):
                    append(wi, "blank_control", delay_index=di, average_index=average,
                           program=programs[s.delays_us[di], False])
        return result
    if kind == "preliminary":
        for wi in range(len(s.spectral_points)):
            append(wi, "preliminary", duration=s.controls.preliminary_duration_s)
        return result
    for wi in range(len(s.spectral_points)):
        append(wi, "baseline", duration=s.controls.baseline_duration_s)
        order = sorted(range(len(s.delays_us)), key=lambda i: s.delays_us[i], reverse=s.delay_order == "descending")
        for average in range(s.averages):
            current = list(reversed(order)) if s.delay_order == "alternating" and average % 2 else order
            for di in current:
                if average < s.controls.pump_blocked_averages:
                    append(wi, "pump_blocked", delay_index=di, average_index=average, program=programs[s.delays_us[di], False])
                append(wi, "pumped", delay_index=di, average_index=average, program=programs[s.delays_us[di], True])
        for average in range(s.averages, s.controls.pump_blocked_averages):
            for di in order:
                append(wi, "pump_blocked", delay_index=di, average_index=average, program=programs[s.delays_us[di], False])
        append(wi, "post_run", duration=s.reset.verification_duration_s)
        # Final recovery is an additional wait before the post-run observation.
        from dataclasses import replace
        result[-1] = replace(result[-1], recovery_wait_s=s.reset.recovery_wait_s)
    return result


def _budget(s: StroboscopySettings, blocks: list[AcquisitionBlock], *, kind: str = "run") -> DurationBudget:
    if not blocks:
        return DurationBudget()
    b, r = s.budget, s.response
    sum_kind = lambda kind: sum(block.capture_duration_s for block in blocks if block.kind == kind)
    frame_blocks = sum(block.physical_frame_count > 0 for block in blocks)
    observations = sum(block.physical_frame_count == 0 for block in blocks) + sum(block.reset_verification_s > 0 for block in blocks)
    guard_s = frame_blocks * b.acquisition_guard_s_per_block
    # HF2 subscription begins before the four arm/enable commands. The final
    # status query and bounded polling overrun also arrive in retained polls.
    # Count these native samples without double-counting their wall time.
    total_capture = sum(block.capture_duration_s + block.reset_verification_s for block in blocks) + guard_s + frame_blocks*b.native_protocol_seconds_per_block
    rate = r.sample_rate_sps + r.timing_rate_sps + (r.reference_rate_sps if s.mode == "dual" else 0)
    samples = math.ceil(total_capture * rate)
    # Arrays + raw immutable preservation plus indexing/metadata allowance.
    storage = math.ceil(samples * b.bytes_per_native_sample * 1.15)
    # Runner currently retains cumulative arrays until final preservation; it
    # cannot budget only the largest block as if completed blocks were unloaded.
    memory = math.ceil(samples * b.bytes_per_native_sample * 2.5)
    frame_count = sum(block.physical_frame_count for block in blocks)
    open_actions = []
    if kind == "blank":
        open_actions.append("Loading the optional blank is a physical action with no fixed duration")
    seconds = dict(configuration_s=b.configuration_estimate_s,
        tuning_s=len(s.spectral_points) * b.tuning_estimate_s_per_wavenumber,
        detector_settling_s=len(s.spectral_points) * b.detector_settling_s_per_wavenumber,
        sequential_blank_s=sum_kind("sequential_blank") + sum_kind("blank_control"), preliminary_s=sum_kind("preliminary"),
        baseline_s=sum_kind("baseline"), pump_blocked_s=sum_kind("pump_blocked"),
        pumped_capture_s=sum_kind("pumped"), recovery_s=sum(block.recovery_wait_s for block in blocks),
        reset_verification_s=sum(block.reset_verification_s for block in blocks),
        post_run_verification_s=sum_kind("post_run"), acquisition_guard_s=guard_s,
        protocol_s=frame_blocks*b.capture_protocol_seconds_per_block + observations*b.observation_protocol_seconds_per_block,
        upload_s=frame_blocks*b.upload_fixed_seconds_per_block + frame_count*b.upload_seconds_per_frame,
        retrieval_s=storage / b.retrieval_bytes_per_second, restoration_s=b.restoration_estimate_s,
        saving_s=storage / b.save_bytes_per_second, analysis_s=b.analysis_estimate_s,
        physical_actions_s=s.controls.physical_action_allowance_s)
    return DurationBudget(**seconds, event_count=sum(block.expected_pump_events for block in blocks),
        control_event_count=sum(block.kind == "pump_blocked" for block in blocks),
        blank_control_event_count=sum(block.kind == "blank_control" for block in blocks), total_block_count=len(blocks),
        total_frame_count=frame_count, native_sample_count=samples, memory_bytes=memory, storage_bytes=storage,
        wall_clock_s=sum(seconds.values()), open_ended_actions=tuple(open_actions))


def apply_qualified_recommendations(settings: StroboscopySettings, qualification: Qualification | Mapping[str, Any],
                                   *, override_fields: tuple[str, ...] = ()) -> StroboscopySettings:
    """Explicit user-selected automatic choices, preserving named manual edits.

    This never runs implicitly during planning. Recommended settings must be
    scoped to this biological condition/mode. Dot paths in ``override_fields``
    preserve manual valid overrides, even outside the qualified envelope (which
    then appears as a readiness item).
    """
    q = _payload(qualification)
    data = settings.to_dict()
    recommendations = q.get("operating_settings", {})
    for section, values in recommendations.items():
        if section not in ("response", "timing", "reset", "budget") or not isinstance(values, Mapping):
            raise ValueError("Qualified operating settings may only contain response, timing, reset and budget mappings")
        for name, value in values.items():
            if f"{section}.{name}" not in override_fields:
                if name not in data[section]:
                    raise ValueError(f"Unknown qualified setting {section}.{name}")
                data[section][name] = value
    data["operating_basis"] = f"Applicable promoted profile {q.get('profile_id', 'historical settings')}; explicit manual overrides retained"
    _retain_selections(settings, data, basis=f"Explicit recommended setting from applicable profile {q.get('profile_id', 'historical settings')}")
    return StroboscopySettings.from_dict(data)


def _retain_selections(settings: StroboscopySettings, updated: dict[str, Any], *, basis: str) -> None:
    records = {item.path: asdict(item) for item in settings.value_selections}
    original = settings.to_dict()
    for section in ("response", "timing", "reset", "budget"):
        for name, selected in updated[section].items():
            requested = original[section][name]
            if isinstance(selected, (float, int)) and not isinstance(selected, bool) and selected != requested:
                path = f"{section}.{name}"
                prior = records.get(path)
                if prior and prior["selected"] == requested:
                    requested = prior["requested"]
                records[path] = {"path": path, "requested": requested, "selected": selected, "basis": basis}
    updated["value_selections"] = list(records.values())
