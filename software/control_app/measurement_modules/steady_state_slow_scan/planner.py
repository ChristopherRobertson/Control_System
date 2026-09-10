"""Deterministic spectral planning from requests and explicit instrument evidence.

No device modules are imported here. Native sampling and the characterized HF2LI
response jointly constrain speed; "slow" is not assigned a fixed scan rate.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import math
from typing import Any, Mapping

from .settings import CONDITION_PROFILES, PlannerInputs, QCLWindow, SlowScanSettings


def _positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


@dataclass(frozen=True)
class ScanBlock:
    block_id: str
    segment_id: str
    qcl: int
    direction: str
    start_cm1: float
    stop_cm1: float
    scan_speed_cm1_s: float
    scan_duration_s: float
    settle_s: float
    replicates: int
    frame_period_s: float
    frame_predivider: int
    expected_marker_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SlowScanPlan:
    settings: SlowScanSettings
    inputs: PlannerInputs
    requested: dict[str, Any]
    selected: dict[str, Any]
    actual: dict[str, Any]
    blocks: tuple[ScanBlock, ...]
    estimates: dict[str, Any]
    errors: tuple[str, ...]
    readiness: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.errors and not self.readiness

    def require_ready(self, *, hardware: bool = True) -> None:
        issues = list(self.errors)
        if hardware:
            issues.extend(self.readiness)
            if self.inputs.simulation:
                issues.append("Simulation evidence cannot authorize connected hardware")
        if not self.blocks:
            issues.append("The spectral trajectory has unresolved operating values")
        if issues:
            raise ValueError("; ".join(dict.fromkeys(issues)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0", "experiment_id": "steady_state_slow_scan",
            "instance_id": self.settings.instance_id, "settings": self.settings.to_dict(),
            "inputs": self.inputs.to_dict(), "requested": deepcopy(self.requested),
            "selected": deepcopy(self.selected), "actual": deepcopy(self.actual),
            "blocks": [block.to_dict() for block in self.blocks], "estimates": deepcopy(self.estimates),
            "errors": list(self.errors), "readiness": list(self.readiness), "warnings": list(self.warnings),
        }


def build_plan(settings: SlowScanSettings | Mapping[str, Any], inputs: PlannerInputs | Mapping[str, Any] | None = None) -> SlowScanPlan:
    if not isinstance(settings, SlowScanSettings):
        settings = SlowScanSettings.from_dict(settings)
    if not isinstance(inputs, PlannerInputs):
        inputs = PlannerInputs.from_dict(inputs or {})
    # Detach mutable caller mappings so a saved plan cannot silently change.
    settings = SlowScanSettings.from_dict(settings.to_dict())
    inputs = PlannerInputs.from_dict(deepcopy(inputs.to_dict()))
    profile = inputs.scientific_profile
    errors: list[str] = []
    readiness: list[str] = []
    warnings: list[str] = []
    selected: dict[str, Any] = {}
    blocks: list[ScanBlock] = []

    def resolve(name: str, *, positive: bool = True) -> Any:
        requested = getattr(settings, name, None)
        value = requested if requested is not None else profile.get(name)
        if value is None:
            readiness.append(f"Resolve {name} from applicable characterization and installed readback")
        elif positive and not _positive(value):
            errors.append(f"{name} must be finite and positive")
            value = None
        selected[name] = value
        return value

    if not _positive(settings.requested_resolution_cm1):
        errors.append("requested_resolution_cm1 must be finite and positive")
    if not isinstance(settings.replicates, int) or isinstance(settings.replicates, bool) or not 1 <= settings.replicates <= 8192:
        errors.append("replicates must be an integer in 1..8192")
    elif settings.replicates < 2:
        warnings.append("One replicate per direction cannot establish within-direction repeatability")
    if settings.fit_line_shape not in ("gaussian", "lorentzian"):
        errors.append("Unsupported fit_line_shape")
    if not isinstance(settings.fit_peak_count, int) or not 1 <= settings.fit_peak_count <= 8:
        errors.append("fit_peak_count must be an integer in 1..8")
    if settings.fit_baseline_degree not in (0, 1, 2):
        errors.append("fit_baseline_degree must be in 0..2")
    if any(not _positive(value) for value in settings.fit_fringe_periods_cm1):
        errors.append("Fringe periods must be finite and positive cm^-1 values")
    if not settings.segments:
        errors.append("Declare at least one supported QCL segment")
    if len({s.segment_id for s in settings.segments}) != len(settings.segments):
        errors.append("Spectral segment IDs must be unique")
    condition = settings.condition
    for name in ("sample_id", "preparation_id", "cell_id", "position_id", "temperature_id", "matrix_id", "configuration_id"):
        if not str(getattr(condition, name)).strip():
            readiness.append(f"Record condition.{name}")
    if not settings.condition_equilibrated:
        readiness.append("Record sample temperature equilibration; no installed automatic temperature control is assumed")
    if not settings.physical_controls_confirmed:
        readiness.append("Confirm required manual sample/background and optical dark actions")
    if not _positive(condition.temperature_k) or not condition.temperature_record_id:
        readiness.append("Measured illuminated-sample temperature and its source remain unresolved")
    if condition.temperature_uncertainty_k is None:
        readiness.append("Record measured-temperature uncertainty")
    elif not isinstance(condition.temperature_uncertainty_k, (int, float)) or not math.isfinite(condition.temperature_uncertainty_k) or condition.temperature_uncertainty_k < 0:
        errors.append("Temperature uncertainty must be finite and nonnegative")
    if CONDITION_PROFILES[condition.condition_id]["temperature_regime"] == "cryogenic":
        if not condition.thermal_history_id:
            readiness.append("Cryogenic condition requires its own matrix and thermal-history record")
        warnings.append("Cryogenic centers and baselines are fitted independently; nominal 77 K is not a temperature observation")
    if inputs.configuration_id != condition.configuration_id or not inputs.configuration_id:
        readiness.append("Applicable evidence must identify this exact optical configuration")
    if condition.condition_id not in inputs.condition_ids:
        readiness.append("Operating profile applicability does not include this independent condition")
    if settings.mode not in inputs.modes:
        readiness.append("Operating profile applicability does not include this detector mode")
    if not inputs.promoted_bundle_ids and not inputs.simulation:
        readiness.append("No explicitly promoted instrument bundle has been supplied")
    if settings.calibration_bundle_ids and set(settings.calibration_bundle_ids) != set(inputs.promoted_bundle_ids):
        readiness.append("Selected calibration bundle identities differ from supplied promoted evidence")
    for flag, message in (
        (inputs.tee_receiver_topology_verified, "Installed detector tee/receiver topology is unqualified"),
        (inputs.process_trigger_qualified, "Active-low MIRcat process-trigger sequence requires applicable qualification"),
        (inputs.wavelength_markers_qualified, "MIRcat direction, Sweep Active and wavelength-marker mapping require qualification"),
        (inputs.frames_feature_observed, "Connected T660-2 Trains and Frames feature has not been observed"),
    ):
        if not flag:
            readiness.append(message)
    if inputs.simulation:
        warnings.append("SIMULATION ONLY: synthetic capabilities and values do not establish hardware readiness")

    linewidth = resolve("measured_linewidth_cm1")
    rate = resolve("sample_rate_hz")
    tau = resolve("time_constant_s")
    order = resolve("filter_order")
    if order is not None and (int(order) != order or not 1 <= order <= 8):
        errors.append("HF2LI filter_order must be an integer in 1..8")
        order = None
    requested_speed = resolve("requested_scan_speed_cm1_s")
    settle = resolve("settle_s")
    marker_interval = resolve("marker_interval_cm1")
    marker_width = resolve("marker_width_s")
    probe_rate = resolve("probe_rate_hz")
    probe_width = resolve("probe_width_s")
    process_width = resolve("process_pulse_width_s")
    dark_duration = resolve("dark_duration_s")
    response = profile.get("measured_response_s")
    intrinsic = profile.get("intrinsic_resolution_cm1")
    if not _positive(response):
        readiness.append("Measured HF2LI/detector response duration at the selected filter is required")
        response = None
    if not _positive(intrinsic):
        readiness.append("Characterized intrinsic spectral resolution is required")
        intrinsic = None
    if not profile.get("response_calibration_id"):
        readiness.append("HF2LI response calibration identity is missing")
    if not profile.get("axis_calibration_id"):
        readiness.append("Applicable spectral-axis calibration identity is missing")
    if not profile.get("probe_calibration_id"):
        readiness.append("Applicable MIRcat probe pulse characterization identity is missing")
    for field_name in ("time_constant_s", "filter_order", "probe_rate_hz", "probe_width_s", "process_pulse_width_s", "marker_width_s", "marker_interval_cm1"):
        if selected.get(field_name) is not None and profile.get(field_name) != selected[field_name]:
            bounds = profile.get("qualified_override_ranges", {}).get(field_name)
            if not (isinstance(bounds, (tuple, list)) and len(bounds) == 2 and
                    bounds[0] <= selected[field_name] <= bounds[1]):
                readiness.append(f"{field_name} override is outside this profile's explicit characterized applicability")
    selected["measured_response_s"] = response
    selected["intrinsic_resolution_cm1"] = intrinsic
    selected["hf2li"] = deepcopy(profile.get("hf2li", {}))
    selected["demodulator_roles"] = dict(inputs.demodulator_roles)
    selected["timing_rate_hz"] = inputs.timing_rate_hz
    selected["qcl_currents_ma"] = deepcopy(profile.get("qcl_currents_ma", {}))
    for role in (("sample", "timing") if settings.mode == "single" else ("sample", "reference", "timing")):
        index = inputs.demodulator_roles.get(role)
        if index not in inputs.available_demodulators:
            readiness.append(f"Installed HF2LI {role} demodulator API index {index} is unverified")
        role_profile = selected["hf2li"].get(role, {})
        if not role_profile:
            readiness.append(f"Applicable independent HF2LI {role} input/filter/reference configuration is missing")
        elif not {"adcselect", "oscselect", "harmonic", "order", "timeconstant_s", "rate_sps", "trigger"} <= set(role_profile):
            readiness.append(f"HF2LI {role} configuration requires adcselect/oscselect/harmonic/order/timeconstant_s/rate_sps/trigger")
    hf_profile = selected["hf2li"]
    for input_name in (("ch1",) if settings.mode == "single" else ("ch1", "ch2")):
        signal_input = hf_profile.get("sigins", {}).get(input_name, {})
        if not {"index", "ac", "impedance_50ohm", "differential", "range_v"} <= set(signal_input):
            readiness.append(f"HF2LI {input_name} requires independently qualified range, coupling, impedance and differential readbacks")
    if not {"index", "enable", "adcselect", "freqcenter_hz", "harmonic", "order", "adcthreshold"} <= set(hf_profile.get("pll", {})):
        readiness.append("HF2LI external DIO0 PLL configuration is unresolved")
    if not profile.get("hf2li_health_nodes"):
        readiness.append("Qualified HF2LI unlock/clipping health-node checks are required")
    if set(profile.get("direction_bit_by_direction", {})) != {"forward", "reverse"}:
        readiness.append("Qualified forward/reverse DIO direction-bit identities are required")
    for device in ("t660_1", "t660_2"):
        if not {"clock_connector_mode", "clock_external_lock_enabled", "clock_external_frequency_hz", "clock_lock_status"} <= set(profile.get("t660_clock_readbacks", {}).get(device, {})):
            readiness.append(f"Qualified {device} external-clock routing and lock-state readbacks are required")
    for segment in settings.segments:
        pulse = profile.get("qcl_pulse_params", {}).get(str(segment.qcl), {})
        if not {"pulse_rate_hz", "pulse_width_ns", "current_ma"} <= set(pulse):
            readiness.append(f"QCL {segment.qcl} requires applicable rate, width and current pulse characterization")
        elif not all(_positive(pulse[name]) for name in ("pulse_rate_hz", "pulse_width_ns", "current_ma")):
            errors.append(f"QCL {segment.qcl} pulse acceptance settings must be finite and positive")
        acceptance = profile.get("external_pulse_acceptance", {}).get(str(segment.qcl), {})
        if not acceptance.get("source_id"):
            readiness.append(f"QCL {segment.qcl} external probe pulse acceptance evidence is missing")
        elif probe_rate and probe_width:
            if not all(_positive(acceptance.get(name)) for name in ("maximum_rate_hz", "minimum_width_s", "maximum_width_s", "maximum_duty_cycle")):
                readiness.append(f"QCL {segment.qcl} external pulse acceptance limits are incomplete")
            elif (probe_rate > acceptance["maximum_rate_hz"] or not acceptance["minimum_width_s"] <= probe_width <= acceptance["maximum_width_s"]
                  or probe_rate * probe_width > acceptance["maximum_duty_cycle"]):
                errors.append(f"QCL {segment.qcl} selected external pulses exceed applicable acceptance limits")
        if str(segment.qcl) not in profile.get("marker_channel_by_qcl", {}):
            readiness.append(f"QCL {segment.qcl} wavelength-trigger channel identity is unresolved")
        elif not isinstance(profile["marker_channel_by_qcl"][str(segment.qcl)], int) or not 1 <= profile["marker_channel_by_qcl"][str(segment.qcl)] <= 255:
            errors.append("MIRcat wavelength-trigger channel identities are one-based 1..255")
    roles = [inputs.demodulator_roles.get(role) for role in (("sample", "timing") if settings.mode == "single" else ("sample", "reference", "timing"))]
    if len(set(roles)) != len(roles):
        errors.append("Sample, reference and timing demodulators must be distinct")
    if inputs.supported_sample_rates_hz:
        valid_rates = sorted(set(r for r in inputs.supported_sample_rates_hz if _positive(r)))
        if rate is not None:
            eligible = [r for r in valid_rates if r >= rate]
            if not eligible:
                errors.append("Requested native sample rate exceeds connected supported HF2LI rates")
            else:
                selected["sample_rate_hz"] = rate = eligible[0]
    else:
        readiness.append("Connected HF2LI supported native sampling rates are unresolved")
    reference_rate = None
    if settings.mode == "dual":
        reference = hf_profile.get("reference", {})
        reference_rate = reference.get("rate_sps")
        reference_response = reference.get("measured_response_s")
        if not _positive(reference_rate):
            readiness.append("Reference detector native sampling rate is unresolved")
            reference_rate = None
        elif (inputs.supported_reference_sample_rates_hz or inputs.supported_sample_rates_hz) and reference_rate not in (inputs.supported_reference_sample_rates_hz or inputs.supported_sample_rates_hz):
            errors.append("Reference detector native sampling rate is unsupported")
        if not _positive(reference_response):
            readiness.append("Independently characterized reference detector/HF2LI response duration is unresolved")
        elif response:
            response = max(response, reference_response)
            selected["measured_response_s"] = response
    selected["reference_sample_rate_hz"] = reference_rate
    aggregate = None
    if rate and _positive(inputs.timing_rate_hz):
        aggregate = rate + (reference_rate or 0.) + inputs.timing_rate_hz
        if not _positive(inputs.aggregate_max_rate_hz):
            readiness.append("Aggregate HF2LI throughput for detector and timing streams is unresolved")
        elif aggregate > inputs.aggregate_max_rate_hz:
            errors.append("Aggregate HF2LI detector plus timing sample rate exceeds installed throughput")
    else:
        readiness.append("Connected timing-stream sample rate is unresolved")
    selected["aggregate_rate_hz"] = aggregate
    if tau and order:
        selected["nominal_filter_3db_hz"] = math.sqrt(2 ** (1 / order) - 1) / (2 * math.pi * tau)
        if response and response < order * tau:
            warnings.append("Measured response is shorter than n*tau; verify its definition and uncertainty before accepting line widths")
    if probe_rate and probe_width and probe_rate * probe_width >= 1:
        errors.append("Probe pulse width must be shorter than its period")
    if process_width and not 0.001 <= process_width <= 0.100:
        errors.append("MIRcat process pulse must be within manufacturer 1–100 ms; applicable qualification is still required")
    if marker_width and inputs.timing_rate_hz and marker_width * inputs.timing_rate_hz < 2:
        errors.append("Wavelength-marker high interval needs at least two native timing samples")
    if not _positive(inputs.t660_tick_s) or not _positive(inputs.t660_maximum_delay_s):
        readiness.append("T660 timing resolution and maximum delay require documented installed capabilities")
    if not isinstance(inputs.t660_frame_capacity, int) or inputs.t660_frame_capacity < 2:
        readiness.append("Verified T660 physical frame capacity is unresolved")
    elif isinstance(settings.replicates, int) and settings.replicates + 1 > inputs.t660_frame_capacity:
        errors.append("Declared continuous block exceeds verified T660 frame capacity; no implicit splitting is permitted")

    resolution = settings.requested_resolution_cm1
    target_step = min(resolution / 2, linewidth / 6) if linewidth and _positive(resolution) else None
    selected["target_native_spacing_cm1"] = target_step
    if intrinsic and _positive(resolution) and intrinsic >= resolution:
        errors.append("Requested spectral resolution is below characterized intrinsic instrument resolution")
    budget = math.sqrt(max(0., resolution ** 2 - intrinsic ** 2)) if intrinsic and _positive(resolution) else None
    qcl_windows = {window.qcl: window for window in inputs.qcl_windows}
    for segment in settings.segments:
        if not segment.segment_id.strip() or not isinstance(segment.qcl, int) or segment.qcl < 1:
            errors.append("Each segment needs a nonempty ID and positive integer QCL identity")
        if not _positive(segment.lower_cm1) or not _positive(segment.upper_cm1) or segment.lower_cm1 >= segment.upper_cm1:
            errors.append(f"{segment.segment_id}: require finite lower_cm1 < upper_cm1")
            continue
        window = qcl_windows.get(segment.qcl)
        if window is None:
            readiness.append(f"{segment.segment_id}: installed and calibrated QCL {segment.qcl} window is unresolved")
            continue
        if segment.lower_cm1 < window.lower_cm1 or segment.upper_cm1 > window.upper_cm1:
            errors.append(f"{segment.segment_id}: range crosses QCL {segment.qcl} supported bounds; declare separate module segments")
        if not window.qualified or not window.source_id:
            readiness.append(f"{segment.segment_id}: QCL usable-range/speed/settling characterization is missing")
        if not all(_positive(value) for value in (window.minimum_speed_cm1_s, window.maximum_speed_cm1_s, window.speed_increment_cm1_s, window.tuning_settle_s)):
            readiness.append(f"{segment.segment_id}: resolve measured QCL speed range, speed increment and tuning settling")
            continue
        if not all(_positive(value) for value in (requested_speed, rate, target_step, response, budget, settle, probe_rate, process_width, marker_interval)):
            continue
        # Native spacing and response smear share the resolution budget. The
        # quadrature model is declared, not an asserted measured final linewidth.
        limiting_rate = min(rate, reference_rate) if reference_rate else rate
        speed_limit = min(limiting_rate * target_step, budget / math.sqrt((1 / limiting_rate) ** 2 + response ** 2), window.maximum_speed_cm1_s)
        speed = min(requested_speed, speed_limit)
        increment = window.speed_increment_cm1_s
        speed = math.floor((speed + increment * 1e-10) / increment) * increment
        if speed < window.minimum_speed_cm1_s:
            errors.append(f"{segment.segment_id}: measured minimum scan speed cannot meet requested sampling/resolution/filter constraints")
            continue
        if speed < requested_speed:
            warnings.append(f"{segment.segment_id}: selected {speed:g} cm^-1/s from requested {requested_speed:g} to satisfy native sampling and response limits")
        duration = (segment.upper_cm1 - segment.lower_cm1) / speed
        settling = max(settle, window.tuning_settle_s, response)
        # A process event occurs after settling. Tail retains filter response;
        # the next event is scheduled by a divided hardware clock, never sleep.
        required_period = settling + process_width + duration + response + 2 * (inputs.t660_tick_s or 0.)
        divisor = math.ceil(required_period * probe_rate)
        if divisor > 2 ** 32 - 1:
            errors.append(f"{segment.segment_id}: frame predivider exceeds the T660 uint32 limit")
            continue
        period = divisor / probe_rate
        marker_count = math.floor((segment.upper_cm1 - segment.lower_cm1) / marker_interval + 1e-9) + 1
        if marker_count < 2:
            errors.append(f"{segment.segment_id}: at least two observed wavelength anchors are required")
        if marker_width and marker_width >= marker_interval / speed:
            errors.append(f"{segment.segment_id}: marker pulses overlap at the selected trajectory speed")
        for direction, start, stop in (("forward", segment.lower_cm1, segment.upper_cm1), ("reverse", segment.upper_cm1, segment.lower_cm1)):
            blocks.append(ScanBlock(f"{segment.segment_id}:{direction}", segment.segment_id, segment.qcl,
                                    direction, start, stop, speed, duration, settling, settings.replicates,
                                    period, divisor, marker_count))
    selected["resolution_estimate_basis"] = "sqrt(intrinsic_cm1^2 + (speed/native_rate)^2 + (speed*measured_response_s)^2); validate empirically"
    selected["commanded_pump_events"] = 0
    selected["electrical_pump_events"] = None
    selected["optical_pump_events"] = None
    selected["time_zero_irf_status"] = "not measured by static spectroscopy; no optical-arrival claim"
    selected["axes_authority"] = "observed qualified wavelength markers inside each observed Sweep Active interval"
    selected["temperature_actions"] = "manual preparation and recorded equilibration; no temperature controller assumed"
    selected["module_transitions"] = "explicit stop, configure, tune and readiness check before every declared block"
    estimate_values = profile.get("overhead_estimates_s", {})
    overheads: dict[str, float | None] = {}
    for name in ("configuration", "upload_per_frame", "restoration", "saving", "analysis", "physical_preparation", "review", "reset"):
        value = estimate_values.get(name)
        overheads[name] = float(value) if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 else None
    if any(value is None for value in overheads.values()):
        warnings.append("Wall-clock estimate is a lower bound until preparation, review, upload, restoration, saving, analysis and reset durations are supplied")
    acquisition_s = sum((block.replicates + 1) * block.frame_period_s for block in blocks)
    preparation_s = float(dark_duration or 0)
    # Sequential blank in single only; dual acquires simultaneous matched buffer.
    controls_s = acquisition_s if settings.mode == "single" else 0.
    preliminary_s = acquisition_s
    physical_frames = sum(block.replicates + 1 for block in blocks)
    known_overhead = sum(value for key, value in overheads.items() if key != "upload_per_frame" and value is not None)
    upload_s = (overheads["upload_per_frame"] or 0.) * physical_frames * (3 if settings.mode == "single" else 2)
    total_capture = preparation_s + controls_s + preliminary_s + acquisition_s
    native_samples = math.ceil(total_capture * aggregate) if aggregate else None
    storage_bytes = native_samples * 64 if native_samples is not None else None
    estimates = {
        "sample_acquisition_s": acquisition_s, "dark_s": preparation_s, "control_acquisition_s": controls_s,
        "preliminary_s": preliminary_s, "acknowledged_upload_s": upload_s, "overhead_s": overheads,
        "wall_clock_s": total_capture + known_overhead + upload_s,
        "wall_clock_is_lower_bound": any(value is None for value in overheads.values()),
        "basis": "finite physical frame periods including inert terminators, single-only sequential blank, preliminary, dark, and declared overhead",
        "native_samples": native_samples, "native_storage_bytes": storage_bytes,
        "peak_memory_bytes": storage_bytes * 3 if storage_bytes is not None else None,
        "storage_basis": "64 bytes per native detector/timing row; peak memory conservatively 3x, excludes optional scope captures",
        "sample_sweep_count": len(blocks) * settings.replicates if isinstance(settings.replicates, int) else None,
        "sample_physical_frame_count": physical_frames, "pump_event_count": 0,
    }
    return SlowScanPlan(settings, inputs, settings.to_dict(), selected, deepcopy(inputs.actual_readbacks), tuple(blocks), estimates,
                        tuple(dict.fromkeys(errors)), tuple(dict.fromkeys(readiness)), tuple(dict.fromkeys(warnings)))


def inputs_from_context(context: Any, settings: SlowScanSettings, readbacks: Mapping[str, Any] | None = None) -> PlannerInputs:
    """Read only selected promoted manifests; host loader establishes promotion.

    A bundle supplies ``steady_state_slow_scan.planner_inputs``. Unknown/missing
    content is reported, never replaced by the candidate sweep or Phase recipe.
    Installed results can fill capability fields but cannot invent qualification.
    """
    payload: dict[str, Any] = {}
    sources: list[dict[str, Any]] = []
    for bundle_id in settings.calibration_bundle_ids:
        bundle = context.promoted_bundle(bundle_id)
        section = bundle.manifest.get("steady_state_slow_scan", {})
        data = section.get("planner_inputs", {})
        if not data:
            raise ValueError(f"Promoted bundle {bundle_id} does not contain a steady_state_slow_scan planner_inputs profile")
        for key, value in data.items():
            if key in payload and payload[key] != value:
                raise ValueError(f"Selected promoted bundles disagree on {key}; select one applicable operating profile")
            payload[key] = deepcopy(value)
        sources.append({"source_id": bundle_id, "path": str(bundle.path), "kind": "promoted_instrument_bundle"})
    payload["promoted_bundle_ids"] = tuple(settings.calibration_bundle_ids)
    payload["source_records"] = tuple(sources)
    if readbacks:
        original_readbacks = deepcopy(dict(readbacks))
        readbacks = deepcopy(dict(readbacks))
        hf = readbacks.get("hf2li", {})
        if hf.get("verified"):
            sample = hf.get("sample", hf)
            reference = hf.get("reference", {})
            readbacks["supported_sample_rates_hz"] = sample.get("rates_sps", ())
            readbacks["supported_reference_sample_rates_hz"] = reference.get("rates_sps", ())
            readbacks["available_demodulators"] = hf.get("enabled_streams", ())
            readbacks["timing_rate_hz"] = hf.get("timing_rate_sps")
            rates = tuple(sample.get("rates_sps", ()))
            reference_rates = tuple(reference.get("rates_sps", ()))
            if rates and hf.get("timing_rate_sps"):
                # Discovery rechecks these maximum rates together. Retain this
                # observed aggregate bound instead of inventing a device ceiling.
                readbacks["aggregate_max_rate_hz"] = max(rates) + (max(reference_rates) if reference_rates else 0.) + hf["timing_rate_sps"]
        if readbacks.get("t660_frame_capacity"):
            readbacks["frames_feature_observed"] = True
        allowed = {"qcl_windows", "supported_sample_rates_hz", "supported_reference_sample_rates_hz", "available_demodulators", "aggregate_max_rate_hz",
                   "timing_rate_hz", "t660_tick_s", "t660_maximum_delay_s", "t660_frame_capacity", "frames_feature_observed"}
        for key, value in readbacks.items():
            if key in allowed:
                if key == "qcl_windows":
                    # Preserve qualified usable ranges only where installed ranges
                    # contain them. Connected nominal ranges are never calibration.
                    previous = {int(w["qcl"]): w for w in payload.get(key, ())}
                    qualified = {}
                    for observed in value:
                        observed = dict(observed)
                        if "min_cm1" in observed:
                            observed["lower_cm1"] = observed.pop("min_cm1")
                        if "max_cm1" in observed:
                            observed["upper_cm1"] = observed.pop("max_cm1")
                        qcl = int(observed["qcl"])
                        if qcl in previous:
                            existing = previous[qcl]
                            existing["lower_cm1"] = max(existing["lower_cm1"], observed["lower_cm1"])
                            existing["upper_cm1"] = min(existing["upper_cm1"], observed["upper_cm1"])
                            qualified[qcl] = existing
                        else:
                            qualified[qcl] = {**observed, "qualified": False}
                    payload[key] = tuple(qualified.values())
                else:
                    payload[key] = deepcopy(value)
        payload["actual_readbacks"] = original_readbacks
    return PlannerInputs.from_dict(payload)


def simulation_inputs(settings: SlowScanSettings) -> PlannerInputs:
    """Explicit synthetic fixture profile, never used automatically for hardware."""
    profile = {
        "measured_linewidth_cm1": 2., "requested_scan_speed_cm1_s": 2., "sample_rate_hz": 1000.,
        "time_constant_s": .001, "filter_order": 2, "settle_s": .02,
        "marker_interval_cm1": .1, "marker_width_s": .001, "probe_rate_hz": 100000.,
        "probe_width_s": 1e-6, "process_pulse_width_s": .001, "dark_duration_s": .1,
        "measured_response_s": .01, "intrinsic_resolution_cm1": .05,
        "response_calibration_id": "SIMULATED-HF", "axis_calibration_id": "SIMULATED-AXIS",
        "probe_calibration_id": "SIMULATED-PROBE", "qcl_currents_ma": {str(s.qcl): 1. for s in settings.segments},
        "hf2li": {
            "sample": {"adcselect": 0, "oscselect": 0, "harmonic": 1, "order": 2, "timeconstant_s": .001, "rate_sps": 1000., "trigger": 0},
            "reference": {"adcselect": 1, "oscselect": 0, "harmonic": 1, "order": 2, "timeconstant_s": .001, "rate_sps": 1000., "trigger": 0, "measured_response_s": .01},
            "timing": {"adcselect": 0, "oscselect": 0, "harmonic": 1, "order": 1, "timeconstant_s": .001, "rate_sps": 10000., "trigger": 0},
            "sigins": {"ch1": {"index": 0, "ac": False, "impedance_50ohm": False, "differential": False, "range_v": 1.},
                       "ch2": {"index": 1, "ac": False, "impedance_50ohm": False, "differential": False, "range_v": 1.}},
            "pll": {"index": 0, "enable": True, "adcselect": 8, "freqcenter_hz": 100000., "harmonic": 1, "order": 1, "adcthreshold": 0},
        },
        "qcl_pulse_params": {str(segment.qcl): {"pulse_rate_hz": 100000., "pulse_width_ns": 1000., "current_ma": 1.} for segment in settings.segments},
        "external_pulse_acceptance": {str(segment.qcl): {"source_id": "SIMULATED-ACCEPTANCE", "maximum_rate_hz": 200000.,
            "minimum_width_s": 1e-8, "maximum_width_s": 2e-6, "maximum_duty_cycle": .3} for segment in settings.segments},
        "marker_channel_by_qcl": {str(segment.qcl): segment.qcl for segment in settings.segments},
        "direction_bit_by_direction": {"forward": 1, "reverse": 0},
        "t660_clock_readbacks": {
            "t660_1": {"clock_connector_mode": "IN", "clock_external_lock_enabled": "1", "clock_external_frequency_hz": "10000000", "clock_lock_status": "LOCKED"},
            "t660_2": {"clock_connector_mode": "OUT", "clock_external_lock_enabled": "0", "clock_external_frequency_hz": "10000000", "clock_lock_status": "INTERNAL"},
        },
        "hf2li_health_nodes": [{"path": "/{device}/status/flags/binary", "type": "int", "healthy_value": 0}],
        "overhead_estimates_s": {name: 0. for name in ("configuration", "upload_per_frame", "restoration", "saving", "analysis", "physical_preparation", "review", "reset")},
    }
    windows = tuple(QCLWindow(qcl, min(s.lower_cm1 for s in settings.segments if s.qcl == qcl),
                             max(s.upper_cm1 for s in settings.segments if s.qcl == qcl), .001, 100., .001, .02, "SIMULATED-QCL", True)
                    for qcl in sorted({segment.qcl for segment in settings.segments}))
    return PlannerInputs(scientific_profile=profile, qcl_windows=windows,
                         supported_sample_rates_hz=(100., 1000., 10000.), available_demodulators=(0, 2, 3),
                         aggregate_max_rate_hz=30000., timing_rate_hz=10000., t660_tick_s=1e-9,
                         t660_maximum_delay_s=10., t660_frame_capacity=8192, frames_feature_observed=True,
                         tee_receiver_topology_verified=True, process_trigger_qualified=True, wavelength_markers_qualified=True,
                         configuration_id=settings.condition.configuration_id, condition_ids=(settings.condition.condition_id,),
                         modes=(settings.mode,), simulation=True, source_records=({"source_id": "SIMULATED", "kind": "synthetic_fixture"},))
