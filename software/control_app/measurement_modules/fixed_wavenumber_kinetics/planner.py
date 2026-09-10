"""Pure planning, provenance and finite resource accounting for local kinetics."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, replace
import json
import math
import re
from typing import Any, Mapping

from .settings import CONDITION_PROFILES, EXPERIMENT_ID, SCHEMA_VERSION, Position, Settings
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
        return not self.validation_errors and not self.readiness_items

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
                "mode": self.mode, "instance_id": self.instance_id, "ready": self.ready, "settings": self.settings.to_dict(),
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
        return cls(settings, deepcopy(value["resolved"]), tuple(blocks), tuple(value["validation_errors"]),
                   tuple(value["readiness_items"]), tuple(value["warnings"]), deepcopy(value["estimates"]),
                   deepcopy(value["requested"]), deepcopy(value["selected"]), deepcopy(value["actual"]),
                   deepcopy(value.get("evidence_records", {})))


def _positive(value: Any, *, zero: bool = False) -> bool:
    return (not isinstance(value, bool) and isinstance(value, (int, float)) and
            math.isfinite(value) and (value >= 0 if zero else value > 0))


def _integer(value: Any, minimum: int = 1) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _merge(left: Mapping, right: Mapping) -> dict:
    result = deepcopy(dict(left))
    for key, value in right.items():
        result[key] = _merge(result[key], value) if isinstance(result.get(key), Mapping) and isinstance(value, Mapping) else deepcopy(value)
    return result


def _validate(s: Settings) -> list[str]:
    errors = []
    if s.mode not in {"single", "dual"}:
        errors.append("Detector mode must be single or dual")
    if s.condition_profile not in CONDITION_PROFILES:
        errors.append("Select an available protein/temperature condition profile")
    if not isinstance(s.pump_enabled, bool):
        errors.append("Pump enable must be boolean")
    for name in ("pre_observation_s", "post_observation_s", "chunk_duration_s", "memory_limit_mb", "storage_limit_mb", "tune_timeout_s"):
        if not _positive(getattr(s, name)):
            errors.append(f"{name} must be finite and positive")
    for name in ("technical_repetitions", "events_per_position"):
        if not _integer(getattr(s, name)):
            errors.append(f"{name} must be a positive finite integer")
    if not _integer(s.event_budget, 0):
        errors.append("event_budget must be a finite nonnegative integer")
    for name in ("sample_rate_sps", "reference_rate_sps", "sample_timeconstant_s", "reference_timeconstant_s",
                 "minimum_event_interval_s", "wavenumber_tolerance_cm1", "temperature_k", "reset_observation_s"):
        if getattr(s, name) is not None and not _positive(getattr(s, name)):
            errors.append(f"{name} must be positive or Automatic")
    for name in ("baseline_drift_fraction", "baseline_cv_limit", "reset_tolerance_fraction"):
        if not _positive(getattr(s, name)) or getattr(s, name) >= 1:
            errors.append(f"{name} must lie strictly between zero and one")
    for name in ("sample_filter_order", "reference_filter_order"):
        value = getattr(s, name)
        if value is not None and (not _integer(value) or value > 8):
            errors.append(f"{name} must be an integer from 1 to 8 or Automatic")
    if s.retention_strategy not in {"continuous_to_disk", "bounded_memory"}:
        errors.append("Select continuous_to_disk or bounded_memory retention; ring-buffer overwrite is unsupported")
    if not errors and s.chunk_duration_s > s.pre_observation_s + s.post_observation_s:
        errors.append("Retrieval chunk duration exceeds the requested complete record")
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
    if not errors:
        total = len(s.positions) * s.technical_repetitions * s.events_per_position * int(s.pump_enabled)
        if total > s.event_budget:
            errors.append(f"Requested {total} pump events exceed the explicitly authorized finite budget {s.event_budget}")
        if len(s.positions) * s.technical_repetitions * s.events_per_position > 10000:
            errors.append("More than 10000 separately reviewed capture blocks exceeds this planner's bounded schedule")
        if s.condition_profile.startswith("cryo") and total > 1:
            errors.append("Cryogenic no-repeat rule: an explicitly established fresh equivalent state requires a separate operation; no installed automatic state-establishment adapter is available")
    return errors


def build_plan(settings: Settings | Mapping[str, Any], configuration: Mapping[str, Any] | None = None,
               evidence: Mapping[str, Any] | None = None, *, purpose: str = "measurement") -> Plan:
    """Resolve an editable plan without discovery, device imports or hardware I/O.

    ``configuration['fixed_wavenumber_kinetics']`` supplies installed method
    capabilities; ``evidence['operating_profile']`` supplies accepted settings.
    A promoted bundle loader validates instrument provenance before supplying
    this mapping. Sample selection is a separate versioned exchange record.
    Unresolved readiness does not prevent saving or inspecting a plan.
    """
    s = Settings.from_dict(settings)
    if purpose not in {"measurement", "preliminary", "blank"}:
        raise ValueError("Unknown acquisition purpose")
    preparation = purpose != "measurement"
    acquisition_settings = (replace(s, pump_enabled=False, event_budget=0,
                                   technical_repetitions=1 if purpose == "preliminary" else s.technical_repetitions,
                                   events_per_position=1 if purpose == "preliminary" else s.events_per_position)
                            if preparation else s)
    config, evidence = deepcopy(dict(configuration or {})), deepcopy(dict(evidence or {}))
    errors, ready, warnings = _validate(acquisition_settings), [], []
    local = config.get(EXPERIMENT_ID, {})
    profile = evidence.get("operating_profile", {})
    resolved = _merge(local, profile)
    resolved["acquisition_purpose"] = purpose
    resolved["units"] = {"time": "s", "wavenumber": "cm^-1", "sampling": "samples/s", "temperature": "K"}
    resolved["actual_readbacks_required"] = ["MIRcat Tuned and actual position", "HF2LI rates/filter/order/ranges/lock",
                                               "T660 table/predivider/clock/finite count", "retained marker and detector support"]
    if not profile.get("record_id") or profile.get("qualification_kind") not in {"measured", "simulation"}:
        ready.append("Load an applicable measured operating profile; defaults and literature examples do not authorize a recipe")
    simulation = profile.get("qualification_kind") == "simulation"
    if simulation:
        warnings.append("SIMULATION ONLY: synthetic profile values and records provide no installed-system or sample readiness evidence")
    if profile.get("condition_profile") != s.condition_profile:
        ready.append("Operating profile protein/temperature condition does not match settings")
    if profile.get("condition_id") != s.condition_id:
        ready.append("Operating profile condition identity does not match settings")
    for name in ("condition_id", "sample_id", "preparation_id", "cell_id", "position_id", "temperature_id"):
        if not getattr(s, name):
            ready.append(f"Enter the {name.replace('_', ' ')}")
    if s.temperature_k is None:
        warnings.append("Sample temperature is unentered: a condition label alone does not establish actual temperature or a temperature-dependent claim")
    if s.condition_profile.startswith("cryo"):
        if s.temperature_k is None:
            ready.append("Cryogenic observation requires an entered measured temperature in kelvin from the retained condition record")
        temperature_qualified = (_positive(profile.get("temperature_uncertainty_k"), zero=True) or
            (profile.get("temperature_status") in {"measured", "condition_source_measured"} and
             bool(profile.get("temperature_record_id"))))
        if not temperature_qualified:
            ready.append("Cryogenic temperature needs explicit profile uncertainty in kelvin or a measured condition-source status tied to the retained temperature record; no automatic sensor is assumed")
    if not s.positions:
        ready.append("Select at least one measured band or off-band position; nominal literature centers are not selected positions")
    required_records = ["topology_record_id", "acquisition_response_record_id", "temperature_record_id", "configuration_id"]
    if s.pump_enabled and not preparation:
        required_records.append("dose_record_id")
    for name in required_records:
        if not resolved.get(name):
            ready.append(f"Applicable {name.replace('_', ' ')} is unresolved")
    if s.pump_enabled and not preparation and not s.dark_control_record_id:
        ready.append("Load an applicable dark-control record")
    if s.pump_enabled and not preparation and not s.artifact_control_record_id:
        ready.append("Load applicable no-pump/off-band artifact controls")
    # An accepted sample spectral-selection exchange can come from any producer;
    # it is intentionally not treated as promoted instrument calibration.
    selection_issues = []
    selection = _selection_projection(evidence.get("sample_selection", {}), selection_issues)
    for p in s.positions if not preparation else ():
        if not p.selection_record_id:
            ready.append(f"Position {p.wavenumber_cm1:g} cm^-1 needs its accepted measured selection record ID")
    if selection and not preparation:
        if selection.get("accepted") is not True:
            ready.append("Sample spectral-selection record has not been accepted")
        for field in ("sample_id", "condition_id", "preparation_id", "cell_id"):
            if selection.get(field) != getattr(s, field):
                ready.append(f"Sample spectral-selection {field} does not match")
        if not selection.get("schema_version") or not selection.get("record_id"):
            ready.append("Sample spectral-selection exchange needs a schema version and stable record ID")
        selected_rows = selection.get("positions", [])
        for p in s.positions:
            if p.selection_record_id != selection.get("record_id") or not any(
                    _positive(row.get("wavenumber_cm1")) and math.isclose(row["wavenumber_cm1"], p.wavenumber_cm1, abs_tol=1e-9, rel_tol=0)
                    for row in selected_rows):
                ready.append(f"Measured selection does not cover position {p.wavenumber_cm1:g} cm^-1")
    elif s.positions and not preparation:
        ready.append("Load the versioned measured sample spectral-selection record for the ordered positions")
    if not preparation:
        ready.extend(selection_issues)
    if "mbco" in s.condition_profile and s.positions and not preparation:
        bands = [p for p in s.positions if p.label == "band"]
        if bands and bands[0].band_assignment.upper().replace("₁", "1") != "A1":
            ready.append("MbCO discovery starts at a measured A1 band; A0/A3 are conditional extensions")
        quantified = set(selection.get("quantified_extensions", ()))
        for p in bands:
            if p.band_assignment.upper() in {"A0", "A3"} and p.band_assignment.upper() not in quantified:
                ready.append(f"MbCO {p.band_assignment} extension needs measured spectral separation and pump-signal quantification")
    # Detector settings resolve independently; throughput includes every enabled
    # demodulator stream, including the separate retained digital marker stream.
    roles = ("sample", "reference") if s.mode == "dual" else ("sample",)
    for role in roles:
        role_record = deepcopy(dict(resolved.get(role, {})))
        for setting_name, key in ((f"{role}_rate_sps", "rate_sps"), (f"{role}_timeconstant_s", "timeconstant_s"),
                                  (f"{role}_filter_order", "order")):
            if getattr(s, setting_name) is not None:
                role_record[key] = getattr(s, setting_name)
        resolved[role] = role_record
        for key in ("rate_sps", "timeconstant_s"):
            if not _positive(role_record.get(key)):
                ready.append(f"Resolve measured {role} HF2LI {key}")
        if not _integer(role_record.get("order")) or role_record.get("order", 0) > 8:
            ready.append(f"Resolve supported {role} HF2LI filter order")
        if not _integer(role_record.get("demodulator_index"), 0) or not _integer(role_record.get("input_index"), 0):
            ready.append(f"Resolve maintained {role} demodulator and signal-input roles")
        choices = local.get("supported", {}).get(role, {})
        for key in ("rate_sps", "timeconstant_s", "order"):
            if choices.get(key) and role_record.get(key) not in choices[key]:
                errors.append(f"Requested {role} {key} is unsupported by the supplied installed capabilities")
        # Overrides are permitted only inside the measured response envelope.
        accepted = profile.get(role, {})
        for key in ("rate_sps", "timeconstant_s", "order"):
            if role_record.get(key) != accepted.get(key) and not _within_envelope(role_record.get(key), resolved.get("validity_envelope", {}).get(f"{role}.{key}")):
                ready.append(f"{role} {key} override lacks applicable measured acquisition-response evidence")
    if s.mode == "dual" and resolved.get("sample", {}).get("demodulator_index") == resolved.get("reference", {}).get("demodulator_index"):
        ready.append("Dual detectors require distinct demodulator roles")
    if s.mode == "dual" and resolved.get("sample", {}).get("input_index") == resolved.get("reference", {}).get("input_index"):
        ready.append("Dual detectors require distinct sample and reference signal inputs")
    for name in ("settling_s", "timing_rate_sps", "tune_tolerance_cm1"):
        if not _positive(resolved.get(name), zero=name == "settling_s"):
            ready.append(f"Resolve characterized {name}")
    if s.wavenumber_tolerance_cm1 is not None:
        if not _within_envelope(s.wavenumber_tolerance_cm1, resolved.get("validity_envelope", {}).get("tune_tolerance_cm1")) and s.wavenumber_tolerance_cm1 != profile.get("tune_tolerance_cm1"):
            ready.append("Wavenumber tolerance override exceeds its measured validity envelope")
        resolved["tune_tolerance_cm1"] = s.wavenumber_tolerance_cm1
    if not _integer(resolved.get("timing_demodulator_index"), 0):
        ready.append("Resolve an independently enabled timing demodulator stream")
    elif resolved.get("timing_demodulator_index") in [resolved.get(r, {}).get("demodulator_index") for r in roles]:
        ready.append("Timing stream must have a distinct demodulator role")
    if resolved.get("pump_marker_bit") != 16:
        ready.append("Installed pump electrical marker is Surelite Fixed Sync on HF2LI DIO16; qualify any changed topology")
    if not _positive(resolved.get("pump_marker_min_width_s")):
        ready.append("Resolve the measured minimum electrical pump-marker width")
    elif _positive(resolved.get("timing_rate_sps")) and resolved["pump_marker_min_width_s"] * resolved["timing_rate_sps"] < 2:
        ready.append("Timing stream cannot qualify two samples across the shortest measured pump marker")
    for section in ("probe_recipe", "mircat", "hf2li"):
        if not resolved.get(section):
            ready.append(f"Resolve the complete applicable {section} configuration")
    if resolved.get("probe_recipe"):
        probe_channels = resolved["probe_recipe"].get("channels", {})
        if set(probe_channels) != set("ABCD") or probe_channels.get("D", {}).get("enabled") is not False:
            ready.append("Probe recipe must configure A/B/C/D and leave disconnected channel D OFF")
        elif not all({"enabled", "delay", "width", "polarity", "termination"} <= set(probe_channels[ch]) for ch in "ABCD"):
            ready.append("Probe recipe must explicitly specify every channel's enable/delay/width/polarity/termination")
        else:
            from control_app.devices.t660_service import T660Service
            try:
                T660Service.validate_recipe_section("t660_1", resolved["probe_recipe"])
            except (ValueError, RuntimeError) as exc:
                errors.append(f"Probe recipe is unsupported: {exc}")
        if any(probe_channels.get(ch, {}).get("enabled") is not True for ch in "ABC"):
            ready.append("Stationary probe recipe must enable the maintained A reference, B MIRcat probe and C frame-input roles")
        frequency = _frequency_hz(resolved["probe_recipe"].get("clock", {}).get("frequency"))
        divider = resolved["probe_recipe"].get("predivider", 1)
        timing_rate = resolved.get("timing", {}).get("input_frequency_hz")
        if frequency is None or not _integer(divider, 0):
            ready.append("Resolve explicit T660-1 synthesizer frequency and probe predivider")
        elif _positive(timing_rate) and not math.isclose(frequency / max(1, divider), timing_rate, rel_tol=1e-9, abs_tol=1e-9):
            errors.append("Probe carrier from T660-1 synthesizer/predivider differs from the selected T660-2 frame-input frequency")
    if resolved.get("mircat"):
        for key in ("qcl", "pulse_width_ns", "pulse_rate_hz"):
            if not _positive(resolved["mircat"].get(key)):
                ready.append(f"Resolve explicit MIRcat {key}")
    if resolved.get("hf2li") and (not resolved["hf2li"].get("signal_inputs") or not resolved["hf2li"].get("pll")):
        ready.append("Resolve independently characterized HF2LI signal-input loading/ranges and PLL settings")
    if not resolved.get("optical_time_zero_record_id"):
        warnings.append("Optical time zero is unresolved: retain electrical pump epoch; do not claim sample optical arrival or nanosecond kinetics")
    warnings.extend(("Sequential fixed positions are acquired in explicit order and are not a simultaneous spectrum",
                     "Fixed-point traces establish apparent local amplitude/recovery, not full band area or a microscopic pathway",
                     "Technical repetitions from one preparation are not independent biological preparations"))
    total_events = len(s.positions) * s.technical_repetitions * s.events_per_position if not errors and s.pump_enabled and not preparation else 0
    interval = s.minimum_event_interval_s if s.minimum_event_interval_s is not None else resolved.get("minimum_event_interval_s")
    if total_events > 1:
        if not _positive(interval):
            ready.append("Later events require a measured minimum accepted sample interval, independent of probe carrier rate")
        elif interval < 0.1:
            errors.append("Accepted event interval would exceed the pump manufacturer's 10 Hz maximum")
        if not resolved.get("reset_record_id") and not s.condition_profile.startswith("cryo"):
            ready.append("Later equivalent events require an applicable measured recovery/reset record")
        if s.minimum_event_interval_s is not None and _positive(profile.get("minimum_event_interval_s")) and interval < profile["minimum_event_interval_s"]:
            ready.append("Requested cadence is faster than the measured accepted recovery/reset interval")
    resolved["minimum_event_interval_s"] = interval
    resolved["baseline_window_s"] = list(s.baseline_window_s) if s.baseline_window_s else [-s.pre_observation_s, 0.0]
    resolved["integration_window_s"] = list(s.integration_window_s) if s.integration_window_s else [0.0, s.post_observation_s]
    resolved["baseline_drift_fraction"] = s.baseline_drift_fraction
    resolved["baseline_cv_limit"] = s.baseline_cv_limit
    resolved["reset_tolerance_fraction"] = s.reset_tolerance_fraction
    for key in ("baseline_drift_fraction", "baseline_cv_limit", "reset_tolerance_fraction"):
        if getattr(s, key) != profile.get(key) and not _within_envelope(getattr(s, key), profile.get("validity_envelope", {}).get(key)):
            ready.append(f"Selected {key} is a proposal without an applicable measured/justified condition-profile criterion")
    timing = None
    timing_fields = ("input_frequency_hz", "fire_delay_s", "q_switch_delay_s", "fire_width_s", "q_switch_width_s",
                     "fire_polarity", "q_switch_polarity", "termination")
    timing_values = resolved.get("timing", {})
    missing_timing_fields = [name for name in timing_fields if name not in profile.get("timing", {})]
    if missing_timing_fields:
        ready.append("Resolve explicit measured operating-profile timing fields: " + ", ".join(missing_timing_fields))
    elif not errors:
        try:
            options = {key: timing_values[key] for key in timing_fields}
            for key in ("frame_capacity", "edge_quantum_s"):
                if key in timing_values:
                    options[key] = timing_values[key]
            timing = compile_timing(pre_observation_s=s.pre_observation_s, post_observation_s=s.post_observation_s,
                                    pump_enabled=acquisition_settings.pump_enabled, **options)
        except (TimingError, TypeError, ValueError) as exc:
            errors.append(f"Timing compilation: {exc}")
    blocks = []
    if not errors:
        for rep in range(acquisition_settings.technical_repetitions):
            for position_index, position in enumerate(s.positions):
                for event in range(acquisition_settings.events_per_position):
                    idx = len(blocks)
                    pumped = acquisition_settings.pump_enabled
                    # The runner first verifies stationary native observations
                    # with the event engine inhibited. The preloaded all-OFF
                    # frame then protects the event start; both intervals are
                    # acquired without restarting the HF2LI subscription.
                    duration = s.pre_observation_s + (timing.duration_s if timing and pumped else s.post_observation_s)
                    selected_pre = s.pre_observation_s + timing.selected_pre_observation_s if timing and pumped else s.pre_observation_s
                    selected_post = timing.selected_post_observation_s if timing and pumped else s.post_observation_s
                    blocks.append(CaptureBlock(idx, position_index, position.wavenumber_cm1, position.label, rep, event,
                        int(pumped), duration, selected_pre, selected_post,
                        bool(idx and acquisition_settings.pump_enabled), timing, float(interval or 0),
                        s.fresh_state_record_ids[idx - 1] if idx and idx - 1 < len(s.fresh_state_record_ids) else ""))
    estimates = _estimates(s, resolved, blocks, ready, errors) if not _validate(s) else {
        "basis": "Correct invalid requested settings before resource estimation", "wall_clock_s": None,
        "capture_s": None, "storage_bytes": None, "peak_memory_bytes": None}
    selected = {"positions_cm1": [p.wavenumber_cm1 for p in s.positions], "ordered": True,
                "total_pump_events": sum(b.event_count for b in blocks), "block_count": len(blocks),
                "pre_observation_s": blocks[0].pre_observation_s if blocks else None,
                "post_observation_s": blocks[0].post_observation_s if blocks else None,
                "detectors": {role: deepcopy(resolved.get(role, {})) for role in roles},
                "minimum_event_interval_s": interval,
                "finite_timing": timing.to_dict() if timing else None}
    return Plan(s, resolved, tuple(blocks), tuple(dict.fromkeys(errors)), tuple(dict.fromkeys(ready)),
                tuple(warnings), estimates, s.to_dict(), selected, {}, evidence)


def _within_envelope(value: Any, envelope: Any) -> bool:
    if isinstance(envelope, Mapping) and _positive(value):
        return envelope.get("minimum", -math.inf) <= value <= envelope.get("maximum", math.inf)
    return isinstance(envelope, (list, tuple)) and value in envelope


def _frequency_hz(value: Any) -> float | None:
    if _positive(value):
        return float(value)
    match = re.fullmatch(r"\s*(\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)\s*(Hz|kHz|MHz)?\s*", str(value), re.IGNORECASE)
    if not match:
        return None
    result = float(match[1]) * {"hz": 1, "khz": 1e3, "mhz": 1e6}[str(match[2] or "Hz").lower()]
    return result if _positive(result) else None


def _selection_projection(source: Mapping[str, Any], readiness: list[str]) -> dict[str, Any]:
    """Consume the frozen host exchange without changing retained source data."""
    if not source or source.get("record_kind") != "sample_spectral_selection":
        return dict(source)
    from control_app.measurement_host.interchange import sample_selection_from_dict
    try:
        selection = sample_selection_from_dict(source)
    except (ValueError, TypeError) as exc:
        readiness.append(f"Invalid host sample-selection exchange: {exc}")
        return {}
    condition = dict(selection.condition)
    return {"record_id": selection.selection_id, "schema_version": selection.schema_version,
            "accepted": selection.disposition == "accepted", "sample_id": selection.sample_id,
            "condition_id": selection.condition_id, "preparation_id": condition.get("preparation_id"),
            "cell_id": condition.get("cell_id"),
            "positions": [{"wavenumber_cm1": window.center_cm1} for window in selection.windows if window.center_cm1 is not None],
            "quantified_extensions": condition.get("quantified_extensions", [])}


def _estimates(s: Settings, r: dict, blocks: list[CaptureBlock], ready: list[str], errors: list[str]) -> dict:
    roles = ("sample", "reference") if s.mode == "dual" else ("sample",)
    rates = [r.get(role, {}).get("rate_sps") for role in roles] + [r.get("timing_rate_sps")]
    capture = sum(b.duration_s for b in blocks)
    estimate: dict[str, Any] = {"basis": "Selected device-clock captures; explicit per-block upload/tune/settle/reset plus preliminary/control, restoration, saving and analysis allowances; manual handling unbounded",
            "capture_s": capture, "continuous_per_block": True, "retention_strategy": s.retention_strategy,
            "gap_policy": "Retain timestamp gaps and inter-block dead time; never silently interpolate, overwrite or reset the original pump epoch",
            "manual_actions": ["Load sample/cell or matched blank when prompted", "Establish documented fresh state where requested; no installed position/temperature automation is assumed"],
            "wall_clock_s": None, "storage_bytes": None, "peak_memory_bytes": None}
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
    preliminary = (s.pre_observation_s + s.post_observation_s) * len(s.positions)
    controls = preliminary if s.mode == "single" else 0.0
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
    if s.retention_strategy == "continuous_to_disk" and not r.get("continuous_poll_lossless_qualified", False):
        ready.append("Continuous native streaming needs qualified poll-loss/backpressure behavior and explicit timestamp gap detection")
    interval = r.get("minimum_event_interval_s") or 0
    reset = sum(max(0.0, interval - b.post_observation_s) for b in blocks[:-1] if b.event_count)
    allowances = r.get("overhead_estimates_s", {})
    required = ("configuration", "upload_per_frame", "tune_per_position", "restoration", "saving", "analysis")
    if all(_positive(allowances.get(key), zero=True) for key in required) and _positive(r.get("settling_s"), zero=True):
        upload = sum((b.timing.physical_frame_count if b.timing else 0) * allowances["upload_per_frame"] for b in blocks)
        prepare = len(blocks) * (allowances["tune_per_position"] + r["settling_s"])
        estimate["wall_clock_s"] = capture + preliminary + controls + reset + upload + prepare + sum(allowances[k] for k in ("configuration", "restoration", "saving", "analysis"))
        estimate["reset_wait_s"] = reset
        estimate["preparation_s"] = prepare + allowances["configuration"] + upload
    else:
        estimate["unresolved_estimate_terms"] = ["configuration/upload/tuning/restoration/saving/analysis allowances; manual sample handling"]
    return estimate
