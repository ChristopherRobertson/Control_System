"""Pure planning, provenance and finite resource accounting for local kinetics."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, replace
import json
import math
import re
from typing import Any, Mapping

from .settings import EXPERIMENT_ID, SCHEMA_VERSION, Position, Settings
from .timing import TimingError, TimingProgram, compile_timing


@dataclass(frozen=True)
class CaptureBlock:
    index: int
    position_index: int
    position_cm1: float
    position_label: str
    repetition_index: int
    event_index: int
    event_count: int
    duration_s: float
    pre_observation_s: float
    post_observation_s: float
    reset_required: bool
    timing: TimingProgram | None
    minimum_event_interval_s: float = 0.0
    fresh_state_record_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["timing"] = self.timing.to_dict() if self.timing else None
        return result


@dataclass(frozen=True)
class Plan:
    settings: Settings
    resolved: dict[str, Any]
    blocks: tuple[CaptureBlock, ...]
    validation_errors: tuple[str, ...]
    readiness_items: tuple[str, ...]
    warnings: tuple[str, ...]
    estimates: dict[str, Any]
    requested: dict[str, Any]
    selected: dict[str, Any]
    actual: dict[str, Any]
    evidence_records: dict[str, Any]
    schema_version: str = SCHEMA_VERSION
    experiment_id: str = EXPERIMENT_ID

    @property
    def ready(self) -> bool:
        """Input-valid and eligible to start the owned connection/resolution step."""
        return not self.validation_errors

    @property
    def operational_ready(self) -> bool:
        """Required operational settings are resolved before acquisition begins."""
        return self.ready and not self.readiness_items

    @property
    def mode(self) -> str:
        return self.settings.mode

    @property
    def instance_id(self) -> str:
        return self.settings.instance_id

    @property
    def positions(self) -> tuple[Position, ...]:
        return self.settings.positions

    @property
    def timing(self) -> TimingProgram | None:
        return self.blocks[0].timing if self.blocks else None

    @property
    def total_pump_events(self) -> int:
        return sum(b.event_count for b in self.blocks)

    def to_dict(self) -> dict[str, Any]:
        # An invalid oversized proposal remains saveable/reviewable without
        # materializing thousands of duplicate frame tables in the UI process.
        compact = (bool(self.validation_errors) and
                   self.estimates.get("serialized_plan_bytes", 0) > 8 * 1024**2)
        block_rows = []
        for block in self.blocks:
            if compact and block.timing is self.timing:
                row = {key: deepcopy(value) for key, value in vars(block).items() if key != "timing"}
                row.update(timing=None, timing_program_ref="selected.finite_timing")
            else:
                row = block.to_dict()
            block_rows.append(row)
        return {"schema_version": self.schema_version, "experiment_id": self.experiment_id,
                "mode": self.mode, "instance_id": self.instance_id, "ready": self.ready,
                "operational_ready": self.operational_ready, "settings": self.settings.to_dict(),
                "resolved": deepcopy(self.resolved), "blocks": block_rows,
                "validation_errors": list(self.validation_errors), "readiness_items": list(self.readiness_items),
                "warnings": list(self.warnings), "estimates": deepcopy(self.estimates),
                "requested": deepcopy(self.requested), "selected": deepcopy(self.selected),
                "actual": deepcopy(self.actual), "evidence_records": deepcopy(self.evidence_records)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Plan":
        if value.get("experiment_id") != EXPERIMENT_ID or value.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Incompatible fixed-wavenumber plan experiment or schema")
        settings = Settings.from_dict(value["settings"])
        if value.get("mode") != settings.mode or value.get("instance_id") != settings.instance_id:
            raise ValueError("Incompatible fixed-wavenumber plan detector mode")
        blocks = []
        shared_timing = None
        for source in value["blocks"]:
            row = deepcopy(dict(source))
            if row.pop("timing_program_ref", None) == "selected.finite_timing":
                if shared_timing is None:
                    shared_timing = TimingProgram.from_dict(value["selected"]["finite_timing"])
                row["timing"] = shared_timing
            if row.get("timing") is not None and not isinstance(row["timing"], TimingProgram):
                row["timing"] = TimingProgram.from_dict(row["timing"])
            blocks.append(CaptureBlock(**row))
        resolved, historical = _qcl1_profile(value["resolved"])
        _remove_unresolved_pulses(resolved)
        resolved.setdefault("mircat", {})["qcl"] = 1
        evidence = deepcopy(value.get("evidence_records", {}))
        pending = list(value["readiness_items"])
        if historical:
            evidence.setdefault("historical_qcl_routing", {})["saved_plan"] = historical
            for key in ("pulse_rate_hz", "pulse_width_ns"):
                if key not in resolved["mircat"]:
                    pending.append(f"Read the current MIRcat QCL1 {key} when connecting")
        errors = list(value["validation_errors"])
        errors.extend(_resolved_pulse_errors(resolved))
        errors.extend(_trigger_errors(settings.probe_rate_hz, settings.probe_width_ns))
        return cls(settings, resolved, tuple(blocks), tuple(dict.fromkeys(errors)),
                   tuple(dict.fromkeys(pending)), tuple(value["warnings"]), deepcopy(value["estimates"]),
                   deepcopy(value["requested"]), deepcopy(value["selected"]), deepcopy(value["actual"]),
                   evidence)


def _positive(value: Any, *, zero: bool = False) -> bool:
    return (not isinstance(value, bool) and isinstance(value, (int, float)) and
            math.isfinite(value) and (value >= 0 if zero else value > 0))


def _integer(value: Any, minimum: int = 1) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def mircat_pulse_errors(params: Mapping[str, Any], external_rate_hz: float,
                        limits: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    """Validate independent MIRcat internal pulses against external triggers.

    SDK ``max_duty_cycle`` is a percentage. Rates are Hz and width is ns,
    therefore internal duty percent = rate * width / 1e7. Both internal and
    external duty have a hard 30% ceiling; tighter SDK limits still apply.
    The internal rate is independent and must exceed the external rate.
    """
    errors = []
    rate, width = params.get("pulse_rate_hz"), params.get("pulse_width_ns")
    if not _positive(rate):
        errors.append("MIRcat internal pulse rate must be finite and positive in Hz")
    if not _positive(width):
        errors.append("MIRcat pulse width must be finite and positive in ns")
    if not _positive(external_rate_hz):
        errors.append("MIRcat external trigger rate must be finite and positive in Hz")
    elif _positive(rate) and rate <= external_rate_hz:
        errors.append("MIRcat internal pulse rate must be strictly greater than the external trigger rate")
    errors.extend(_external_duty_errors(external_rate_hz, width))
    if _positive(rate) and _positive(width) and rate * width > 300_000_000.:
        errors.append(f"MIRcat internal duty cycle {rate * width / 1e7:g}% exceeds the 30% maximum")
    for key, value, label in (("max_pulse_rate_hz", rate, "internal pulse rate"),
                              ("max_pulse_width_ns", width, "pulse width")):
        limit = (limits or {}).get(key)
        if limit is None:
            continue
        if not _positive(limit):
            errors.append(f"MIRcat SDK {key} limit must be finite and positive")
        elif _positive(value) and value > limit:
            errors.append(f"MIRcat {label} {value:g} exceeds SDK {key} limit {limit:g}")
    duty_limit = (limits or {}).get("max_duty_cycle")
    if duty_limit is not None:
        if not _positive(duty_limit, zero=True):
            errors.append("MIRcat SDK max_duty_cycle limit must be a finite nonnegative percentage")
        elif _positive(rate) and _positive(width):
            duty_percent = rate * width / 1e7
            if rate * width > duty_limit * 1e7:
                errors.append(f"MIRcat internal duty cycle {duty_percent:g}% exceeds SDK max_duty_cycle limit {duty_limit:g}%")
    return tuple(errors)


def _trigger_errors(rate, width_ns):
    if _positive(rate) and _positive(width_ns) and rate * (width_ns * 1e-9 + 62.5e-9) >= 1:
        return ("External trigger width and recovery must fit within one T660 period",)
    return ()


def _external_duty_errors(rate: Any, width_ns: Any) -> tuple[str, ...]:
    # Compare in Hz*ns to avoid introducing floating-point boundary error from
    # converting the exact 30% ceiling to a fraction of a second.
    if _positive(rate) and _positive(width_ns) and rate * width_ns > 300_000_000.:
        return (f"External probe repetition rate × MIRcat pulse width gives {rate * width_ns / 1e7:g}% duty; maximum is 30%",)
    return ()


def _qcl1_profile(value: Mapping[str, Any]) -> tuple[dict, dict]:
    """Separate historical routing from the one installed QCL's settings.

    Null pulse fields are merge tombstones: a stale QCL2 source cannot inherit
    lower-priority pulse data and appear to be a current QCL1 readback.
    """
    result, historical = deepcopy(dict(value)), {}
    params = result.get("mircat", {})
    other_qcl = isinstance(params, Mapping) and params.get("qcl", 1) != 1
    if other_qcl:
        historical["mircat"] = deepcopy(params)
        result["mircat"] = {"qcl": 1, "pulse_rate_hz": None, "pulse_width_ns": None}
        if "value_sources" in result:
            result["value_sources"].update({"mircat.pulse_rate_hz": "unresolved",
                "mircat.pulse_width_ns": "unresolved"})
    readback = result.get("mircat_readback")
    if isinstance(readback, Mapping) and (readback.get("qcl", 2 if other_qcl else 1) != 1):
        historical["mircat_readback"] = deepcopy(readback)
        result["mircat_readback"] = {"qcl": 1, "pulse_limits": None}
    elif other_qcl and readback is None:
        result["mircat_readback"] = {"qcl": 1, "pulse_limits": None}
    if "qcl_ranges" in result:
        ranges = result["qcl_ranges"]
        selected = [row for row in ranges if isinstance(row, Mapping) and row.get("qcl") == 1]
        if selected != ranges:
            historical["qcl_ranges"] = deepcopy(ranges)
            result["qcl_ranges"] = selected
    return result, historical


def _remove_unresolved_pulses(value: dict) -> None:
    params = value.get("mircat", {})
    for key in ("pulse_rate_hz", "pulse_width_ns"):
        if key in params and params[key] is None:
            params.pop(key)


def _resolved_pulse_errors(value: Mapping[str, Any]) -> tuple[str, ...]:
    probe, mircat = value.get("probe_recipe", {}), value.get("mircat", {})
    frequency = _frequency_hz(probe.get("clock", {}).get("frequency"))
    divider = probe.get("predivider", 1)
    if frequency is None or not _integer(divider, 0):
        return ()
    external = frequency / max(1, divider)
    if all(key in mircat for key in ("pulse_rate_hz", "pulse_width_ns")):
        return mircat_pulse_errors(mircat, external, value.get("mircat_readback", {}).get("pulse_limits"))
    return _external_duty_errors(external, mircat.get("pulse_width_ns"))


def _merge(left: Mapping, right: Mapping) -> dict:
    result = deepcopy(dict(left))
    for key, value in right.items():
        result[key] = _merge(result[key], value) if isinstance(result.get(key), Mapping) and isinstance(value, Mapping) else deepcopy(value)
    return result


def _validate(s: Settings) -> list[str]:
    errors = []
    from control_app.measurement_host.laser_settings import validate_mircat_limits
    try:
        validate_mircat_limits(width=s.probe_width_ns, wavenumbers=[p.wavenumber_cm1 for p in s.positions])
    except ValueError as exc:
        errors.append(str(exc))
    if not _positive(s.shot_delay_s) or (s.pump_shots > 1 and s.shot_delay_s < .1-1e-12):
        errors.append("Shot Delay must be at least 0.1 s for multiple Pump Shots (10 Hz maximum)")
    if s.time_unit not in ("s", "ms", "µs", "ns"):
        errors.append("Time units must be s, ms, µs or ns")

    if s.mode not in {"single", "dual"}:
        errors.append("Detector mode must be single or dual")
    if not isinstance(s.pump_enabled, bool):
        errors.append("Pump enable must be boolean")
    for name in ("pre_observation_s", "post_observation_s", "chunk_duration_s", "memory_limit_mb", "storage_limit_mb", "tune_timeout_s"):
        if not _positive(getattr(s, name)):
            errors.append(f"{name} must be finite and positive")
    for name in ("technical_repetitions", "events_per_position", "pump_shots"):
        if not _integer(getattr(s, name)):
            errors.append(f"{name} must be a positive finite integer")
    if not _integer(s.event_budget, 0):
        errors.append("event_budget must be a finite nonnegative integer")
    for name in ("sample_rate_sps", "reference_rate_sps", "sample_timeconstant_s", "reference_timeconstant_s",
                 "minimum_event_interval_s", "wavenumber_tolerance_cm1", "reset_observation_s", "probe_rate_hz",
                 "probe_width_ns", "pump_fire_width_s", "pump_q_switch_width_s"):
        if getattr(s, name) is not None and not _positive(getattr(s, name)):
            errors.append(f"{name} must be positive or Automatic")
    for name in ("pump_fire_delay_s", "pump_q_switch_delay_s"):
        if getattr(s, name) is not None and not _positive(getattr(s, name), zero=True):
            errors.append(f"{name} must be nonnegative or Automatic")
    errors.extend(_trigger_errors(s.probe_rate_hz, s.probe_width_ns))
    for name in ("baseline_drift_fraction", "baseline_cv_limit", "reset_tolerance_fraction"):
        if not _positive(getattr(s, name)) or getattr(s, name) >= 1:
            errors.append(f"{name} must lie strictly between zero and one")
    for name in ("sample_filter_order", "reference_filter_order"):
        value = getattr(s, name)
        if value is not None and (not _integer(value) or value > 8):
            errors.append(f"{name} must be an integer from 1 to 8 or Automatic")
    if s.retention_strategy not in {"continuous_to_disk", "bounded_memory"}:
        errors.append("Select continuous_to_disk or bounded_memory retention; ring-buffer overwrite is unsupported")
    for name in ("baseline_window_s", "integration_window_s"):
        window = getattr(s, name)
        if window is not None:
            if len(window) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in window) or window[0] >= window[1]:
                errors.append(f"{name} must be an ordered pair of finite seconds relative to the original pump epoch")
            elif _positive(s.pre_observation_s) and _positive(s.post_observation_s):
                if window[0] < -s.pre_observation_s or window[1] > (0 if name == "baseline_window_s" else s.post_observation_s):
                    errors.append(f"{name} lies outside its requested observation support")
    for pos in s.positions:
        if not _positive(pos.wavenumber_cm1):
            errors.append("Every position must contain a finite positive wavenumber in cm^-1")
        if pos.label not in {"band", "off_band", "control"}:
            errors.append("Position label must be band, off_band, or control")
    if not s.positions:
        errors.append("Enter at least one wavenumber in cm^-1")
    if not errors:
        total = len(s.positions) * s.technical_repetitions * s.events_per_position * s.pump_shots * int(s.pump_enabled)
        if total > s.event_budget:
            errors.append(f"Requested {total} pump events exceed the explicitly authorized finite budget {s.event_budget}")
        if len(s.positions) * s.technical_repetitions * s.events_per_position > 10000:
            errors.append("Maximum 10000 capture blocks")
    return errors


def build_plan(settings: Settings | Mapping[str, Any], configuration: Mapping[str, Any] | None = None,
               evidence: Mapping[str, Any] | None = None, *, purpose: str = "measurement",
               live_readbacks: Mapping[str, Any] | None = None) -> Plan:
    """Plan raw/relative acquisition without opening hardware or requiring files.

    Each None override resolves independently. The precedence is explicit user
    override, current installed readback, optional profile, then configured value.
    Input-valid plans can start the connection step; operational_ready is checked
    after the runner supplies current readbacks under exclusive ownership.
    Material, temperature and historical selection fields are metadata only.
    """
    s = Settings.from_dict(settings)
    from control_app.measurement_host.laser_settings import validate_laser_settings
    lasers = validate_laser_settings(s.laser_settings)
    if purpose not in {"measurement", "preliminary", "blank"}:
        raise ValueError("Unknown acquisition purpose")
    preparation = purpose != "measurement"
    acquisition_settings = (replace(s, pump_enabled=False, event_budget=0,
                                   technical_repetitions=1 if purpose == "preliminary" else s.technical_repetitions,
                                   events_per_position=1 if purpose == "preliminary" else s.events_per_position)
                            if preparation else s)
    config = deepcopy(dict(configuration or {}))
    evidence = deepcopy(dict(evidence or {}))
    local, old_local = _qcl1_profile(config.get(EXPERIMENT_ID, {}))
    profile, old_profile = _qcl1_profile(evidence.get("operating_profile", {}))
    live, old_live = _qcl1_profile(live_readbacks or {})
    historical = {key: value for key, value in (("configured", old_local),
        ("optional_profile", old_profile), ("installed_readback", old_live)) if value}
    if historical:
        evidence.setdefault("historical_qcl_routing", {}).update(historical)
    resolved = _merge(_merge(local, profile), live)
    _remove_unresolved_pulses(resolved)
    sources = {}

    def source_for(path):
        for name, record in (("installed_readback", live), ("optional_profile", profile), ("configured", local)):
            value = record
            for key in path.split("."):
                value = value.get(key) if isinstance(value, Mapping) else None
            if value is not None:
                return name
        return "unresolved"

    errors, pending, warnings = _validate(acquisition_settings), [], []
    pumped = acquisition_settings.pump_enabled
    if pumped and s.pump_shots > 1 and s.shot_delay_s < 1/lasers.get("pump_repetition_rate_hz", 10.)-1e-12:
        errors.append("Shot Delay exceeds the selected Nd:YAG repetition rate; increase Shot Delay or the permitted rate (maximum 10 Hz)")
    roles = ("sample", "reference") if s.mode == "dual" else ("sample",)
    resolved["acquisition_purpose"] = purpose
    resolved["acquisition_class"] = "raw_relative"
    resolved["units"] = {"time": "s", "wavenumber": "cm^-1", "sampling": "samples/s"}
    resolved["actual_readbacks_required"] = ["MIRcat actual position and Tuned", "HF2LI rates/filter/order/ranges/lock",
        "T660 probe clock and finite timing readback", "native detector and electrical marker support"]
    if resolved.get("qualification_kind") == "simulation":
        warnings.append("SIMULATION ONLY: synthetic device settings and observations provide no installed measurement evidence")

    for role in roles:
        selected = deepcopy(dict(resolved.get(role, {})))
        from control_app.measurement_host.hf2_selection import select_supported
        caps = resolved.get("hf2_choices", {})
        profile = caps.get(role, caps if role == "sample" else {})
        requested = {key: getattr(s, f"{role}_{field}") for field, key in
                     (("filter_order", "order"), ("timeconstant_s", "timeconstant_s"), ("rate_sps", "rate_sps"))
                     if getattr(s, f"{role}_{field}") is not None}
        intervals = [v for v in (s.pre_observation_s, s.post_observation_s, s.shot_delay_s if s.pump_shots > 1 else None) if _positive(v)]
        automatic = select_supported(profile, time_scale_s=min(intervals) if intervals else 1., overrides=requested)
        selected.update(automatic)
        for setting_name, key in ((f"{role}_rate_sps", "rate_sps"), (f"{role}_timeconstant_s", "timeconstant_s"),
                                  (f"{role}_filter_order", "order")):
            override = getattr(s, setting_name)
            if override is not None:
                selected[key] = override
            sources[f"{role}.{key}"] = "user_override" if override is not None else source_for(f"{role}.{key}")
            if override is None and key in automatic:
                sources[f"{role}.{key}"] = "automatic from observation interval and supported HF2LI values"
        # An idle HF2 demodulator can report its single-stream maximum, which
        # is not usable with the retained timing stream. Auto lowers that
        # request by the device's binary rate divisors; preparation reads back
        # the actual accepted rate before estimating or acquiring any data.
        if getattr(s, f"{role}_rate_sps") is None and _positive(selected.get("rate_sps")):
            original_rate = selected["rate_sps"]
            choices = resolved.get("supported", {}).get(role, {}).get("rate_sps")
            if original_rate > 231000.:
                candidates = [v for v in (choices or ()) if _positive(v) and v <= 231000.]
                rate = max(candidates) if candidates else original_rate / 2**math.ceil(math.log2(original_rate / 231000.))
                selected["rate_sps"] = rate
                sources[f"{role}.rate_sps"] = "automatic_active_stream_limit; verify installed readback"
        resolved[role] = selected
        if _positive(selected.get("rate_sps")) and min(s.pre_observation_s, s.post_observation_s)*selected["rate_sps"] < 3:
            warnings.append(f"{role.title()} HF2LI sampling provides fewer than three points in the shortest acquisition interval; that timescale cannot yield a resolved kinetics trace")
        for key in ("rate_sps", "timeconstant_s"):
            if not _positive(selected.get(key)):
                pending.append(f"Read current {role} HF2LI {key} when connecting")
        if not _integer(selected.get("order")) or selected.get("order", 0) > 8:
            pending.append(f"Read a supported {role} HF2LI filter order when connecting")
        if not _integer(selected.get("demodulator_index"), 0) or not _integer(selected.get("input_index"), 0):
            pending.append(f"Resolve installed {role} demodulator and input roles when connecting")
        choices = resolved.get("supported", {}).get(role, {})
        for key in ("rate_sps", "timeconstant_s", "order"):
            supported = choices.get(key)
            if supported is None and key == "rate_sps":
                supported = resolved.get(f"{role}_supported_rates_sps")
            if supported and selected.get(key) is not None and selected[key] not in supported:
                errors.append(f"Requested {role} {key} is unsupported by the connected capabilities")
    if s.mode == "dual":
        for key in ("demodulator_index", "input_index"):
            a, b = (resolved.get(role, {}).get(key) for role in ("sample", "reference"))
            if a is not None and b is not None and a == b:
                errors.append(f"Dual detectors require distinct sample/reference {key} roles")

    # Timing and input limits are device/runtime constraints, not qualifications.
    resolved.setdefault("pump_marker_bit", 16)  # Maintained Surelite Fixed Sync wiring.
    resolved["pump_marker_edge"] = "falling"
    resolved.setdefault("maximum_aggregate_rate_sps", 700000.)  # HF2 aggregate manufacturer bound.
    sources["pump_marker_bit"] = source_for("pump_marker_bit") if source_for("pump_marker_bit") != "unresolved" else "maintained_wiring_DIO16"
    for name in ("timing_rate_sps", "tune_tolerance_cm1"):
        if not _positive(resolved.get(name)):
            pending.append(f"Resolve installed {name} when connecting")
        sources[name] = source_for(name)
    # Idle demodulator rates are not a valid multi-stream acquisition request.
    # The timing channel has no user override: select an accepted rate that fits
    # alongside the explicitly selected sample/reference streams.
    timing_rate = resolved.get("timing_rate_sps")
    detector_rates = [resolved.get(role, {}).get("rate_sps") for role in roles]
    if _positive(timing_rate) and all(_positive(rate) for rate in detector_rates):
        available = min(231000., resolved["maximum_aggregate_rate_sps"]
            - sum(detector_rates) - float(resolved.get("other_enabled_rate_sps", 0)))
        if 0 < available < timing_rate:
            caps = resolved.get("hf2_choices", {})
            choices = caps.get("sample", caps).get("rates_sps", ())
            choices = choices or resolved.get("supported", {}).get("sample", {}).get("rate_sps", ())
            accepted = [rate for rate in choices if _positive(rate) and rate <= available]
            if choices and not accepted:
                errors.append("Selected HF2LI detector rates leave no supported rate for the timing stream")
            else:
                resolved["timing_rate_sps"] = max(accepted) if accepted else timing_rate / 2**math.ceil(math.log2(timing_rate/available))
                sources["timing_rate_sps"] = "automatic_active_stream_limit; verify installed readback"
    if s.wavenumber_tolerance_cm1 is not None:
        resolved["tune_tolerance_cm1"] = s.wavenumber_tolerance_cm1
        sources["tune_tolerance_cm1"] = "user_override"
        pending = [item for item in pending if "tune_tolerance_cm1" not in item]
    timing_index = resolved.get("timing_demodulator_index")
    if not _integer(timing_index, 0):
        pending.append("Resolve the installed native timing demodulator when connecting")
    elif timing_index in [resolved.get(role, {}).get("demodulator_index") for role in roles]:
        errors.append("Timing and detector streams require distinct demodulator roles")
    if not _integer(resolved.get("pump_marker_bit"), 0) or resolved.get("pump_marker_bit", 0) > 31:
        errors.append("Native HF2LI pump marker must be a DIO bit in 0..31")
    marker_width = resolved.get("pump_marker_min_width_s")
    if pumped and _positive(marker_width) and _positive(resolved.get("timing_rate_sps")) and marker_width * resolved["timing_rate_sps"] < 2:
        warnings.append("Electrical pump-marker width is shorter than two timing samples; retain the observed count and flag unresolved marker support")
    elif pumped and not _positive(marker_width):
        warnings.append("Electrical marker width is unqualified; retain measured electrical events without an optical-arrival claim")

    # Settling uses an available current value or an explicitly identified filter
    # estimate. It never creates an IRF or a claim of measured time resolution.
    detector_response = [resolved.get(role, {}) for role in roles]
    if not _positive(resolved.get("settling_s"), zero=True):
        if all(_positive(row.get("timeconstant_s")) and _integer(row.get("order")) for row in detector_response):
            resolved["settling_s"] = 5 * max(row["order"] * row["timeconstant_s"] for row in detector_response)
            sources["settling_s"] = "engineering_estimate_5_times_filter_order_times_timeconstant"
            resolved["settling_basis"] = "Five filter-order time constants; engineering settling allowance, not measured IRF"
        else:
            pending.append("Derive settling from the selected connected HF2LI response")
    else:
        sources["settling_s"] = source_for("settling_s")
    if any(getattr(s, f"{role}_{field}") is not None for role in roles for field in ("timeconstant_s", "filter_order")):
        if all(_positive(row.get("timeconstant_s")) and _integer(row.get("order")) for row in detector_response):
            minimum_settling = 5 * max(row["order"] * row["timeconstant_s"] for row in detector_response)
            if _positive(resolved.get("settling_s"), zero=True) and resolved["settling_s"] < minimum_settling:
                resolved["settling_s"] = minimum_settling
                sources["settling_s"] = "engineering_estimate_updated_for_selected_filter"
                resolved["settling_basis"] = "At least five selected filter-order time constants; engineering allowance, not measured IRF"

    probe = deepcopy(dict(resolved.get("probe_recipe", {})))
    mircat = deepcopy(dict(resolved.get("mircat", {})))
    mircat["qcl"] = 1
    timing_values = deepcopy(dict(resolved.get("timing", {})))
    if s.probe_rate_hz is not None:
        # External trigger carrier updates its timing/reference recipients. The
        # MIRcat internal pulse setting remains an independent device value.
        probe.setdefault("clock", {})["frequency"] = f"{s.probe_rate_hz:.12g}Hz"
        probe["predivider"] = 1
        timing_values["input_frequency_hz"] = s.probe_rate_hz
        resolved.setdefault("hf2li", {}).setdefault("pll", {})["freqcenter_hz"] = s.probe_rate_hz
        sources["probe_rate_hz"] = "user_override"
    else:
        sources["probe_rate_hz"] = source_for("probe_recipe.clock.frequency")
    sources["mircat.qcl"] = "installed_topology_QCL1"
    from control_app.measurement_host.laser_settings import MIRCAT_INTERNAL_RATE_HZ, MIRCAT_INTERNAL_WIDTH_NS
    mircat.update(pulse_rate_hz=MIRCAT_INTERNAL_RATE_HZ, pulse_width_ns=MIRCAT_INTERNAL_WIDTH_NS)
    sources["mircat.pulse_rate_hz"] = sources["mircat.pulse_width_ns"] = "provisional_internal_policy"
    if s.probe_width_ns is not None:
        for channel in probe.get("channels", {}).values():
            channel["width"] = f"{s.probe_width_ns:.12g}ns"
        sources["probe_width_ns"] = "user_external_trigger_override"
    for setting_name, key in (("pump_fire_delay_s", "fire_delay_s"), ("pump_q_switch_delay_s", "q_switch_delay_s"),
                              ("pump_fire_width_s", "fire_width_s"), ("pump_q_switch_width_s", "q_switch_width_s")):
        value = getattr(s, setting_name)
        if value is not None:
            timing_values[key] = value
        sources[f"timing.{key}"] = "user_override" if value is not None else source_for(f"timing.{key}")
    # Surelite DAT Mode 2 requires 10 us negative-going FIRE and Q-switch
    # commands (Surelite manual, printed pp. 45-46). Idle T660 readbacks may
    # contain MIRcat-sized pulses; they are not the pump procedure settings.
    for setting_name, key in (("pump_fire_width_s", "fire_width_s"),
                              ("pump_q_switch_width_s", "q_switch_width_s")):
        if getattr(s, setting_name) is None:
            timing_values[key] = 10e-6
            sources[f"timing.{key}"] = "Surelite_DAT_Mode_2_10us_command"
        elif pumped and timing_values[key] < 10e-6:
            errors.append("Nd:YAG FIRE and Q-switch command widths must be at least 10 us")
    if "qcl_current_ma" in lasers:
        mircat["current_ma"] = lasers["qcl_current_ma"]
        sources["mircat.current_ma"] = "user_override"
    if "fire_to_qswitch_us" in lasers:
        gap = lasers["fire_to_qswitch_us"] * 1e-6
        qtime = max(float(timing_values.get("q_switch_delay_s") or gap), gap)
        timing_values.update(fire_delay_s=qtime-gap, q_switch_delay_s=qtime)
        sources["timing.fire_delay_s"] = sources["timing.q_switch_delay_s"] = "user_laser_delay"
    resolved.update(probe_recipe=probe, mircat=mircat, timing=timing_values)
    if not probe:
        pending.append("Read the installed T660-1 probe timing settings when connecting")
    else:
        channels = probe.get("channels", {})
        if set(channels) != set("ABCD") or not all({"enabled", "delay", "width", "polarity", "termination"} <= set(channels[ch]) for ch in "ABCD"):
            pending.append("Resolve complete T660-1 channel enable/delay/width/polarity/termination readbacks")
        elif channels["D"]["enabled"] is not False:
            errors.append("Disconnected T660-1 channel D must remain OFF")
        else:
            from control_app.devices.t660_service import T660Service
            try:
                T660Service.validate_recipe_section("t660_1", probe)
            except (ValueError, RuntimeError) as exc:
                errors.append(f"Probe recipe is unsupported: {exc}")
        frequency = _frequency_hz(probe.get("clock", {}).get("frequency"))
        divider = probe.get("predivider", 1)
        if frequency is None or not _integer(divider, 0):
            pending.append("Read the T660-1 synthesizer frequency and predivider when connecting")
        elif pumped and _positive(timing_values.get("input_frequency_hz")) and not math.isclose(frequency / max(1, divider), timing_values["input_frequency_hz"], rel_tol=1e-9, abs_tol=1e-9):
            errors.append("Probe carrier from T660-1 frequency/predivider differs from the T660-2 frame-input frequency")
    for key in ("qcl", "pulse_width_ns", "pulse_rate_hz"):
        if not _positive(mircat.get(key)):
            pending.append(f"Read the current MIRcat {key} when connecting")
    errors.extend(_resolved_pulse_errors(resolved))
    if not resolved.get("hf2li", {}).get("signal_inputs") or not resolved.get("hf2li", {}).get("pll"):
        pending.append("Read the installed HF2LI signal-input and reference-lock settings when connecting")

    timing = None
    if pumped:
        fields = ("input_frequency_hz", "fire_delay_s", "q_switch_delay_s", "fire_width_s", "q_switch_width_s",
                  "fire_polarity", "q_switch_polarity", "termination")
        missing = [key for key in fields if key not in timing_values]
        if missing:
            pending.append("Read installed pump timing settings when connecting: " + ", ".join(missing))
        elif not errors:
            try:
                options = {key: timing_values[key] for key in fields}
                options.update({key: timing_values[key] for key in ("frame_capacity", "edge_quantum_s") if key in timing_values})
                timing = compile_timing(pre_observation_s=s.pre_observation_s, post_observation_s=s.post_observation_s,
                                        pump_enabled=True, pump_shots=s.pump_shots, shot_delay_s=s.shot_delay_s, **options)
            except (TimingError, TypeError, ValueError) as exc:
                errors.append(f"Timing compilation: {exc}")
    interval = s.minimum_event_interval_s if s.minimum_event_interval_s is not None else .1
    if interval is None:
        interval = resolved.get("minimum_event_interval_s")
        sources["minimum_event_interval_s"] = source_for("minimum_event_interval_s")
    else:
        sources["minimum_event_interval_s"] = "user_override"
    if not _positive(interval):
        interval = max(.1, s.pre_observation_s + s.post_observation_s) if not errors else .1
        sources["minimum_event_interval_s"] = "observation_duration_with_10Hz_source_bound"
    total_events = len(s.positions) * s.technical_repetitions * s.events_per_position if pumped and not errors else 0
    if total_events > 1 and interval < .1:
        errors.append("Requested event interval exceeds the pump manufacturer's 10 Hz maximum")
    if "pump_repetition_rate_hz" in lasers:
        interval = max(interval, 1 / lasers["pump_repetition_rate_hz"])
    resolved["minimum_event_interval_s"] = interval
    resolved["baseline_window_s"] = list(s.baseline_window_s) if s.baseline_window_s else [-s.pre_observation_s, 0.0]
    train_duration = (timing.pump_command_offsets_s[-1]-timing.pump_command_offsets_s[0]
        if timing and timing.pump_command_offsets_s else (s.pump_shots-1)*s.shot_delay_s)
    resolved["integration_window_s"] = list(s.integration_window_s) if s.integration_window_s else [0.0, train_duration+s.post_observation_s]
    for key in ("baseline_drift_fraction", "baseline_cv_limit", "reset_tolerance_fraction"):
        resolved[key] = getattr(s, key)
        sources[key] = "user_diagnostic_setting"
    resolved["value_sources"] = sources
    if not resolved.get("acquisition_response"):
        warnings.append("No measured acquisition response loaded: retain raw/relative traces and leave qualified recovery fits unresolved")
    if not resolved.get("optical_time_zero_record_id"):
        warnings.append("Electrical pump time is distinct from independently measured optical arrival")
    warnings.append("Ordered fixed positions are sequential time traces, not a simultaneous spectrum")

    blocks = []
    if not errors:
        for rep in range(acquisition_settings.technical_repetitions):
            for position_index, position in enumerate(s.positions):
                for event in range(acquisition_settings.events_per_position):
                    idx = len(blocks)
                    duration = timing.duration_s if timing and pumped else s.pre_observation_s + s.post_observation_s + ((s.pump_shots-1)*s.shot_delay_s if pumped else 0.)
                    selected_pre = timing.selected_pre_observation_s if timing and pumped else s.pre_observation_s
                    selected_post = timing.selected_post_observation_s if timing and pumped else s.post_observation_s
                    blocks.append(CaptureBlock(idx, position_index, position.wavenumber_cm1, position.label, rep, event,
                        s.pump_shots if pumped else 0, duration, selected_pre, selected_post, False, timing, float(interval), ""))
    estimates = _estimates(s, resolved, blocks, pending, errors) if not _validate(acquisition_settings) else {
        "basis": "Correct invalid requested settings before resource estimation", "wall_clock_s": None,
        "capture_s": None, "storage_bytes": None, "peak_memory_bytes": None}
    selected = {"positions_cm1": [p.wavenumber_cm1 for p in s.positions], "ordered": True,
                "total_pump_events": sum(b.event_count for b in blocks), "block_count": len(blocks),
                "pre_observation_s": blocks[0].pre_observation_s if blocks else None,
                "post_observation_s": blocks[0].post_observation_s if blocks else None,
                "detectors": {role: deepcopy(resolved.get(role, {})) for role in roles},
                "minimum_event_interval_s": interval, "finite_timing": timing.to_dict() if timing else None}
    return Plan(s, resolved, tuple(blocks), tuple(dict.fromkeys(errors)), tuple(dict.fromkeys(pending)),
                tuple(warnings), estimates, s.to_dict(), selected,
                {"installed_readbacks": deepcopy(dict(live_readbacks))} if live_readbacks else {}, evidence)


def _frequency_hz(value: Any) -> float | None:
    if _positive(value):
        return float(value)
    match = re.fullmatch(r"\s*(\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)\s*(Hz|kHz|MHz)?\s*", str(value), re.IGNORECASE)
    if not match:
        return None
    result = float(match[1]) * {"hz": 1, "khz": 1e3, "mhz": 1e6}[str(match[2] or "Hz").lower()]
    return result if _positive(result) else None


def _estimates(s: Settings, r: dict, blocks: list[CaptureBlock], ready: list[str], errors: list[str]) -> dict:
    roles = ("sample", "reference") if s.mode == "dual" else ("sample",)
    rates = [r.get(role, {}).get("rate_sps") for role in roles] + [r.get("timing_rate_sps")]
    capture = sum(b.duration_s for b in blocks)
    estimate: dict[str, Any] = {"basis": "Selected device-clock captures plus upload, tuning, settling, requested event intervals, restoration, saving and analysis; manual handling excluded",
            "capture_s": capture, "continuous_per_block": True, "retention_strategy": s.retention_strategy,
            "gap_policy": "Retain timestamp gaps and inter-block dead time; never silently interpolate, overwrite or reset the original pump epoch",
            "manual_actions": ["Place the sample and reference as appropriate for the selected detector mode"],
            "wall_clock_s": capture, "wall_clock_is_lower_bound": True, "storage_bytes": None, "peak_memory_bytes": None}
    if not all(_positive(v) for v in rates):
        return estimate
    aggregate = sum(rates)
    throughput = r.get("maximum_aggregate_rate_sps")
    if not _positive(throughput):
        ready.append("Resolve connected HF2LI aggregate throughput including retained timing and both detector streams")
    elif aggregate + float(r.get("other_enabled_rate_sps", 0)) > throughput:
        errors.append("Planned detector and timing streams exceed the connected HF2LI aggregate throughput")
    # 64 bytes/stream sample covers native timestamp, x/y, DIO, auxiliary and
    # status/flags. Three copies accounts for retrieval, analysis and serialization.
    # This is storage budgeting, not a compression promise or a device limit.
    bytes_per_second = aggregate * 64
    largest_capture = max((b.duration_s for b in blocks), default=0)
    # Blank/preliminary work is an explicit operation with its own blocks. It is
    # not a prerequisite silently added to a raw/relative capture estimate.
    preliminary = 0.0
    controls = 0.0
    storage = math.ceil(bytes_per_second * (capture + preliminary + controls) * 1.25 + 1_048_576)
    retained_seconds = largest_capture if s.retention_strategy == "bounded_memory" else min(s.chunk_duration_s * 3, largest_capture)
    peak_memory = math.ceil(bytes_per_second * retained_seconds * 3 + 1_048_576)
    # Timing tables themselves are native provenance. The JSON plan carries one
    # selected table and one table per declared block, so account for these
    # explicitly instead of making a long-record plan an unbounded memory path.
    table = blocks[0].timing if blocks else None
    timing_bytes = len(json.dumps(table.to_dict(), separators=(",", ":")).encode("utf-8")) if table else 0
    plan_bytes = timing_bytes * (len(blocks) + 1) + 4096 * max(1, len(blocks))
    storage += plan_bytes * 3
    peak_memory += plan_bytes * 3
    estimate.update(aggregate_rate_sps=aggregate, estimated_bytes_per_second=bytes_per_second,
                    storage_bytes=storage, peak_memory_bytes=peak_memory,
                    serialized_plan_bytes=plan_bytes,
                    preliminary_s=preliminary, sequential_blank_s=controls)
    if _positive(s.storage_limit_mb) and storage > s.storage_limit_mb * 1024**2:
        errors.append("Full native/control retention exceeds the declared storage budget; shorten the explicit plan or increase the budget")
    if _positive(s.memory_limit_mb) and peak_memory > s.memory_limit_mb * 1024**2:
        errors.append("Planned native retrieval/analysis exceeds the declared memory budget; select bounded chunks or increase the explicit budget")
    estimate["streaming_loss_policy"] = "Monitor native timestamps and receiver loss indicators; preserve and flag gaps without interpolation"
    interval = r.get("minimum_event_interval_s") or 0
    reset = sum(max(0.0, interval - b.post_observation_s - b.pre_observation_s) for b in blocks[:-1] if b.event_count)
    terminal = sum(max(0., b.timing.physical_frame_count*b.timing.frame_period_s-b.duration_s) for b in blocks if b.timing)
    estimate.update(wall_clock_s=capture+reset+terminal, terminal_wait_s=terminal, wall_clock_is_lower_bound=True)
    allowances = r.get("overhead_estimates_s", {})
    required = ("configuration", "upload_per_frame", "tune_per_position", "restoration", "saving", "analysis")
    if all(_positive(allowances.get(key), zero=True) for key in required) and _positive(r.get("settling_s"), zero=True):
        upload = sum((b.timing.physical_frame_count if b.timing else 0) * allowances["upload_per_frame"] for b in blocks)
        prepare = len(blocks) * (allowances["tune_per_position"] + r["settling_s"])
        estimate["wall_clock_s"] = capture + reset + terminal + upload + prepare + sum(allowances[k] for k in ("configuration", "restoration", "saving", "analysis"))
        estimate["wall_clock_is_lower_bound"] = False
        estimate["reset_wait_s"] = reset
        estimate["preparation_s"] = prepare + allowances["configuration"] + upload
    else:
        estimate["unresolved_estimate_terms"] = ["configuration/upload/tuning/restoration/saving/analysis allowances; manual sample handling"]
    return estimate
