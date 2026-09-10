"""Deterministic spectral planning from requests and explicit instrument evidence.

No device modules are imported here. Native sampling and the selected HF2LI
response jointly constrain speed; "slow" is not assigned a fixed scan rate.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, replace
import math
import re
import struct
from typing import Any, Mapping

from .settings import PlannerInputs, QCLWindow, SlowScanSettings, SpectralSegment


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
        issues = [*self.errors, *self.readiness]
        if hardware:
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



def _filter(order, tau):
    def crossing(level):
        low, high = 0., 100.
        for _ in range(60):
            x = (low + high) / 2
            if 1 - math.exp(-x) * sum(x ** k / math.factorial(k) for k in range(order)) < level:
                low = x
            else:
                high = x
        return (low + high) / 2
    return {"rise_s": (crossing(.9) - crossing(.1)) * tau, "settle_s": crossing(.999) * tau,
            "group_delay_s": order * tau, "bandwidth_hz": math.sqrt(2 ** (1 / order) - 1) / (2 * math.pi * tau)}


def _segments(settings, inputs):
    if settings.segments:
        return settings.segments
    result, cursor = [], settings.lower_cm1
    while cursor < settings.upper_cm1:
        candidates = [window for window in inputs.qcl_windows if window.lower_cm1 <= cursor < window.upper_cm1]
        if not candidates:
            future = [window.lower_cm1 for window in inputs.qcl_windows if cursor < window.lower_cm1 < settings.upper_cm1]
            if not future:
                break
            cursor = min(future)
            continue
        window = max(candidates, key=lambda item: item.upper_cm1)
        end = min(window.upper_cm1, settings.upper_cm1)
        result.append(SpectralSegment(f"segment-{len(result)+1}", window.qcl, cursor, end))
        cursor = end
    return tuple(result)


def build_plan(settings, inputs=None):
    """Plan raw/relative spectra; missing scientific qualifications are warnings."""
    settings = SlowScanSettings.from_dict(settings.to_dict() if isinstance(settings, SlowScanSettings) else settings)
    inputs = PlannerInputs.from_dict(deepcopy(inputs.to_dict() if isinstance(inputs, PlannerInputs) else inputs or {}))
    profile, selected = inputs.scientific_profile, {}
    errors, readiness, warnings, blocks = [], [], [], []
    resolution = settings.requested_resolution_cm1
    if not _positive(resolution): errors.append("Spectral resolution must be finite and positive")
    if type(settings.replicates) is not int or not 1 <= settings.replicates <= 8191: errors.append("Replicates must be an integer in 1..8191")
    if not _positive(settings.lower_cm1) or not _positive(settings.upper_cm1) or settings.lower_cm1 >= settings.upper_cm1:
        errors.append("Enter finite lower < upper wavenumbers")
    if settings.fit_line_shape not in ("gaussian", "lorentzian") or settings.fit_baseline_degree not in (0, 1, 2): errors.append("Unsupported peak/baseline model")
    if type(settings.fit_peak_count) is not int or not 1 <= settings.fit_peak_count <= 8: errors.append("Peak count must be in 1..8")
    if any(not _positive(value) for value in settings.fit_fringe_periods_cm1): errors.append("Fringe periods must be finite and positive")
    names = ("measured_linewidth_cm1", "requested_scan_speed_cm1_s", "sample_rate_hz", "time_constant_s", "filter_order",
             "reference_sample_rate_hz", "reference_time_constant_s", "reference_filter_order", "sample_range_v", "reference_range_v",
             "settle_s", "marker_interval_cm1", "marker_width_s", "probe_rate_hz", "probe_width_s", "process_pulse_width_s", "dark_duration_s")
    for name in names:
        if getattr(settings, name) is not None and not _positive(getattr(settings, name)): errors.append(f"{name} must be Auto or finite and positive")
    for segment in settings.segments:
        if type(segment.qcl) is not int or not 0 <= segment.qcl <= 255 or not segment.segment_id.strip(): errors.append("Segment needs a label and QCL Auto (0) or installed number")
        if not _positive(segment.lower_cm1) or not _positive(segment.upper_cm1) or segment.lower_cm1 >= segment.upper_cm1: errors.append("Invalid segment bounds")
    if len({segment.segment_id for segment in settings.segments}) != len(settings.segments): errors.append("Segment labels must be unique")
    if errors:
        return SlowScanPlan(settings, inputs, settings.to_dict(), selected, deepcopy(inputs.actual_readbacks), (), {}, tuple(errors), (), ())
    warnings.extend(profile.get("runtime_warnings", ()))
    if not profile.get("axis_calibration_id"): warnings.append("Controller-marker axis; calibrated wavenumber uncertainty unavailable")
    if not profile.get("response_calibration_id"): warnings.append("HF2LI broadening/settling are nominal filter estimates, not measured instrument response")
    if not inputs.tee_receiver_topology_verified: warnings.append("Receiver loading and detector linearity uncalibrated; retain raw/relative units")
    if not inputs.process_trigger_qualified or not inputs.wavelength_markers_qualified: warnings.append("Native event counts and directions are checked per sweep; optical timing remains uncalibrated")
    if inputs.simulation: warnings.append("Injected test fixture; not a connected-device fallback")
    segments = _segments(settings, inputs)
    if not segments: readiness.append("Connect MIRcat to resolve requested coverage")
    if segments and not settings.segments and sum(s.upper_cm1-s.lower_cm1 for s in segments) < settings.upper_cm1-settings.lower_cm1-1e-8:
        warnings.append("Requested range contains unsupported QCL intervals; explicit segment gaps are retained")
    hf = deepcopy(profile.get("hf2li", {}))
    roles = inputs.demodulator_roles
    for role in (("sample", "reference", "timing") if settings.mode == "dual" else ("sample", "timing")):
        if roles.get(role) not in inputs.available_demodulators: readiness.append(f"Connect HF2LI to resolve {role} stream")
    if not inputs.frames_feature_observed or not inputs.t660_frame_capacity: readiness.append("Connect T660-2 to resolve finite frame capability")
    elif settings.replicates + 1 > inputs.t660_frame_capacity: errors.append("Continuous block exceeds physical frame memory; reduce replicates")
    timing_rate = inputs.timing_rate_hz
    if not _positive(timing_rate): readiness.append("Connected HF2LI timing rate unavailable")
    seed = settings.requested_scan_speed_cm1_s or profile.get("requested_scan_speed_cm1_s")
    estimates_by_role, rates = {}, []
    for role in (("sample", "reference") if settings.mode == "dual" else ("sample",)):
        fields = ("sample_rate_hz", "time_constant_s", "filter_order") if role == "sample" else ("reference_sample_rate_hz", "reference_time_constant_s", "reference_filter_order")
        previous = hf.get(role, {})
        caps = profile.get("hf2li_capabilities", {}).get(role, {})
        orders = tuple(value for value in caps.get("orders", (previous.get("order"),)) if type(value) is int and 1 <= value <= 8)
        order_request = getattr(settings, fields[2])
        if order_request is not None and (type(order_request) is not int or order_request not in orders): errors.append(f"{role} filter order unsupported"); continue
        if not orders: readiness.append(f"Connected {role} filter orders unavailable"); continue
        order = order_request or min(orders, key=lambda value: abs(value-previous.get("order", value)))
        constant_map = caps.get("timeconstants_by_order", {})
        constants = tuple(value for value in constant_map.get(order, constant_map.get(str(order), (previous.get("timeconstant_s"),))) if _positive(value))
        if not constants: readiness.append(f"Connected {role} time constants unavailable"); continue
        tau_request = getattr(settings, fields[1])
        if tau_request is not None:
            tau = min(constants, key=lambda value: abs(value-tau_request))
            if not math.isclose(tau, tau_request, rel_tol=1e-6, abs_tol=1e-12): errors.append(f"{role} time constant unsupported; choose Auto or a connected value"); continue
        else:
            initial_speed = seed or resolution / (2 * _filter(order, previous.get("timeconstant_s") or min(constants))["rise_s"])
            target = resolution / (2 * initial_speed * _filter(order, 1.)["rise_s"])
            tau = max((value for value in constants if value <= target), default=min(constants))
        response = _filter(order, tau)
        if not _positive(seed): seed = resolution / (2*response["rise_s"])
        supported = inputs.supported_sample_rates_hz if role == "sample" else (inputs.supported_reference_sample_rates_hz or inputs.supported_sample_rates_hz)
        supported = tuple(sorted(value for value in supported if _positive(value)))
        if not supported: readiness.append(f"Connected {role} sample rates unavailable"); continue
        rate_request = getattr(settings, fields[0])
        if rate_request is not None:
            rate = min(supported, key=lambda value: abs(value-rate_request))
            if not math.isclose(rate, rate_request, rel_tol=1e-6, abs_tol=1e-9): errors.append(f"{role} sample rate unsupported; choose Auto or a connected value"); continue
        else:
            minimum = max(4 * seed / resolution, 2 * response["bandwidth_hz"])
            rate = next((value for value in supported if value >= minimum), supported[-1])
        hf[role] = {**previous, "order": order, "timeconstant_s": tau, "rate_sps": rate}
        selected.update({fields[0]: rate, fields[1]: tau, fields[2]: order, f"{role}_filter_estimate": response})
        input_name = "ch1" if role == "sample" else "ch2"
        input_range = getattr(settings, f"{role}_range_v") or hf.get("sigins", {}).get(input_name, {}).get("range_v")
        if not _positive(input_range): readiness.append(f"Connected {role} input range unavailable")
        else:
            hf.setdefault("sigins", {}).setdefault(input_name, {})["range_v"] = input_range
            selected[f"{role}_range_v"] = input_range
        estimates_by_role[role] = response
        rates.append(rate)
    selected.update(hf2li=hf, demodulator_roles=dict(roles), timing_rate_hz=timing_rate)
    aggregate = sum(rates) + timing_rate if rates and _positive(timing_rate) else None
    selected["aggregate_rate_hz"] = aggregate
    if aggregate and inputs.aggregate_max_rate_hz and aggregate > inputs.aggregate_max_rate_hz: errors.append("Combined detector/timing rate exceeds connected throughput")
    response = max((value["rise_s"] for value in estimates_by_role.values()), default=0.)
    filter_settle = max((value["settle_s"] for value in estimates_by_role.values()), default=0.)
    selected.update(nominal_response_s=response, planning_response_s=response, measured_response_s=profile.get("measured_response_s"),
                    response_basis="nominal cascaded-RC 10–90% rise estimate", intrinsic_resolution_cm1=profile.get("intrinsic_resolution_cm1"),
                    intrinsic_resolution_known=_positive(profile.get("intrinsic_resolution_cm1")))
    linewidth = settings.measured_linewidth_cm1 or profile.get("measured_linewidth_cm1")
    target_step = min(resolution/2, linewidth/6) if _positive(linewidth) else resolution/2
    selected["target_native_spacing_cm1"] = target_step
    def choose(name, auto=None):
        value = getattr(settings, name)
        if value is None: value = auto if auto is not None else profile.get(name)
        if not _positive(value): readiness.append(f"Connect instruments to resolve {name}"); value = None
        selected[name] = value
        return value
    probe_rate, probe_width = choose("probe_rate_hz"), choose("probe_width_s")
    if probe_rate:
        probe_rate = selected["probe_rate_hz"] = round(probe_rate/.02)*.02
        if probe_rate > 16e6 or (probe_width and probe_rate*(probe_width+62.5e-9) >= 1): errors.append("Probe exceeds documented T660 repetition/width limit")
    process = choose("process_pulse_width_s", profile.get("process_pulse_width_s", .010))
    if process and not .001 <= process <= .1: errors.append("MIRcat process pulse must be in manufacturer 1–100 ms range")
    settle = choose("settle_s", filter_settle or None)
    dark = choose("dark_duration_s", max(20/min(rates), filter_settle) if rates else None)
    marker_width = choose("marker_width_s")
    if marker_width:
        marker_width = selected["marker_width_s"] = round(marker_width*1e6)/1e6
        if not 1e-6 <= marker_width <= .065535: errors.append("Marker width must fit 1–65535 us register")
        if timing_rate and marker_width*timing_rate < 2: errors.append("Marker pulse needs at least two timing samples")
    span = min((segment.upper_cm1-segment.lower_cm1 for segment in segments), default=0.)
    interval = choose("marker_interval_cm1", min(span, max(resolution, 4*(seed or 0.)*(marker_width or 0.))) if span else None)
    if not inputs.t660_tick_s or not inputs.t660_maximum_delay_s: readiness.append("T660 timing capabilities unavailable")
    for segment in segments:
        windows = [w for w in inputs.qcl_windows if w.lower_cm1 <= segment.lower_cm1 < segment.upper_cm1 <= w.upper_cm1 and (not segment.qcl or w.qcl == segment.qcl)]
        if not windows:
            if inputs.qcl_windows: errors.append(f"{segment.segment_id}: range crosses installed QCL bounds")
            else: readiness.append(f"Connect MIRcat to resolve {segment.segment_id} coverage")
            continue
        window = min(windows, key=lambda value: value.qcl)
        if not all(_positive(value) for value in (seed, probe_rate, process, settle, interval)) or not rates or not response: continue
        speed_limit = min(min(rates)*target_step, resolution/math.hypot(response, 1/min(rates)))
        speed = struct.unpack("f", struct.pack("f", settings.requested_scan_speed_cm1_s or min(seed, speed_limit)))[0]
        effective = math.sqrt((profile.get("intrinsic_resolution_cm1") or 0.)**2 + (speed/min(rates))**2 + (speed*response)**2)
        if effective > resolution*1.00001: warnings.append(f"{segment.segment_id}: estimated broadening exceeds requested resolution; raw acquisition remains available")
        if window.maximum_speed_cm1_s and speed > window.maximum_speed_cm1_s: errors.append("Requested speed exceeds supplied installed limit")
        if window.minimum_speed_cm1_s and speed < window.minimum_speed_cm1_s: errors.append("Requested speed is below supplied installed limit")
        duration = (segment.upper_cm1-segment.lower_cm1)/speed
        settle_s = max(settle, window.tuning_settle_s or 0.)
        divider = math.ceil((settle_s+process+duration+filter_settle+2*(inputs.t660_tick_s or 0.))*probe_rate)
        if divider > 2**32-1: errors.append("Frame period exceeds T660 divider range"); continue
        count = math.floor((segment.upper_cm1-segment.lower_cm1)/interval+1e-8)+1
        if not 2 <= count <= 65535: errors.append("Marker schedule needs 2–65535 targets")
        if marker_width and marker_width >= interval/speed: errors.append("Wavelength marker pulses overlap")
        for direction, start, stop in (("forward", segment.lower_cm1, segment.upper_cm1), ("reverse", segment.upper_cm1, segment.lower_cm1)):
            blocks.append(ScanBlock(f"{segment.segment_id}:{direction}", segment.segment_id, window.qcl, direction, start, stop, speed, duration, settle_s, settings.replicates, divider/probe_rate, divider, count))
    if not hf.get("pll") or not hf.get("timing"): readiness.append("Connected HF2LI reference/timing configuration unavailable")
    if hf.get("pll") and probe_rate: hf["pll"]["freqcenter_hz"] = probe_rate
    native_spacing = max((block.scan_speed_cm1_s/min(rates) for block in blocks), default=target_step)
    selected.update(control_match_max_gap_cm1=2*native_spacing, control_matching_basis="bounded local support matching within two selected native sample spacings; no calibration claim",
        commanded_pump_events=0, electrical_pump_events=None, optical_pump_events=None, axes_authority="observed controller wavelength markers in native Sweep Active intervals",
        time_zero_irf_status="not established by static spectroscopy", resolution_estimate_basis="quadrature of native sampling and nominal HF2LI rise plus applicable known intrinsic resolution")
    # Native compatibility/normalization consumes this explicit engineering policy.
    profile["control_match_max_gap_cm1"] = selected["control_match_max_gap_cm1"]
    acquisition_s = sum((block.replicates+1)*block.frame_period_s for block in blocks)
    controls_s = acquisition_s if settings.mode == "single" else 0.
    capture = acquisition_s+(dark or 0.)
    native_samples = math.ceil(capture*aggregate) if aggregate else None
    storage = native_samples*64 if native_samples else None
    estimates = {"sample_acquisition_s": acquisition_s, "dark_s": dark or 0., "control_acquisition_s": controls_s, "preliminary_s": 0., "wall_clock_s": capture,
        "wall_clock_is_lower_bound": True, "basis": "finite frame durations plus automatic dark; upload, tuning, restoration and saving add elapsed time",
        "native_samples": native_samples, "native_storage_bytes": storage, "peak_memory_bytes": storage*3 if storage else None,
        "sample_sweep_count": len(blocks)*settings.replicates, "sample_physical_frame_count": sum(block.replicates+1 for block in blocks), "pump_event_count": 0}
    return SlowScanPlan(settings, inputs, settings.to_dict(), selected, deepcopy(inputs.actual_readbacks), tuple(blocks), estimates,
        tuple(dict.fromkeys(errors)), tuple(dict.fromkeys(readiness)), tuple(dict.fromkeys(warnings)))


def _numeric_readback(value):
    if isinstance(value, Mapping):
        if not value.get("ok"):
            return None
        value = value.get("response")
    match = re.fullmatch(r"\s*([+-]?[\d.]+(?:[eE][+-]?\d+)?)\s*(ps|ns|us|ms|s|Hz|kHz|MHz)?\s*", str(value), re.I)
    if not match:
        return None
    scale = {"": 1., "ps": 1e-12, "ns": 1e-9, "us": 1e-6, "ms": 1e-3, "s": 1., "hz": 1., "khz": 1e3, "mhz": 1e6}
    value = float(match[1])*scale[(match[2] or "").lower()]
    return value if math.isfinite(value) else None


def resolve_runtime_inputs(configuration, readbacks, settings=None):
    """Pure conversion of owned installed-device readbacks into uncalibrated inputs."""
    readbacks = deepcopy(dict(readbacks))
    caps, snapshot = readbacks.get("hf2li", {}), readbacks.get("hf2li_settings", {})
    device = caps.get("device_id", snapshot.get("device_id", ""))
    nodes = snapshot.get("nodes", {})
    def node(suffix, default=None):
        return nodes.get(f"/{device}/{suffix}", {}).get("value", default)
    sample_caps, reference_caps = caps.get("sample", caps), caps.get("reference", {})
    t1 = readbacks.get("t660_1", {})
    profile = {"hf2li": {"sigins": {}, "pll": {}}, "hf2li_capabilities": {"sample": sample_caps, "reference": reference_caps},
        "qcl_pulse_params": deepcopy(readbacks.get("qcl_pulse_params", {})), "marker_channel_by_qcl": {},
        "process_pulse_width_s": .010,
        "marker_width_s": (readbacks.get("marker_width_us") or 0)*1e-6,
        "requested_scan_speed_cm1_s": readbacks.get("sweep", {}).get("scan_rate_cm1_s"),
        "probe_rate_hz": _numeric_readback(t1.get("queries", {}).get("synth_frequency")),
        "probe_width_s": readbacks.get("probe_width_s"),
        "runtime_warnings": ["Controller ranges/settings are installed readbacks, not instrument calibration"]}
    for role, index in (("sample", 0), ("reference", 3), ("timing", 2)):
        profile["hf2li"][role] = {"adcselect": 1 if role == "reference" else 0, "oscselect": 0, "harmonic": 1,
            "order": int(node(f"demods/{index}/order", 1)), "timeconstant_s": node(f"demods/{index}/timeconstant"),
            "rate_sps": node(f"demods/{index}/rate"), "trigger": 0}
    for index in (0, 1):
        profile["hf2li"]["sigins"][f"ch{index+1}"] = {"index": index, "ac": False, "differential": False,
            "impedance_50ohm": bool(node(f"sigins/{index}/imp50", False)), "range_v": node(f"sigins/{index}/range")}
    # Maintained wiring DIO0 uses PLL ADC selection 4; use live pulse frequency.
    profile["hf2li"]["pll"] = {"index": 0, "enable": True, "adcselect": 4, "freqcenter_hz": profile["probe_rate_hz"],
        "harmonic": 1, "order": int(node("plls/0/order", 1)), "adcthreshold": int(node("plls/0/adcthreshold", 0))}
    windows = []
    for row in readbacks.get("qcl_windows", ()):
        qcl = int(row["qcl"])
        windows.append(QCLWindow(qcl, row.get("min_cm1", row.get("lower_cm1")), row.get("max_cm1", row.get("upper_cm1")), source_id="MIRcatSDK_GetQclTuningRange"))
        profile["marker_channel_by_qcl"][str(qcl)] = qcl
    sample_rates = tuple(sample_caps.get("rates_sps", ()))
    reference_rates = tuple(reference_caps.get("rates_sps", ()))
    timing_rate = caps.get("timing_rate_sps")
    aggregate = max(sample_rates, default=0)+max(reference_rates, default=0)+(timing_rate or 0)
    return PlannerInputs(scientific_profile=profile, qcl_windows=tuple(windows), supported_sample_rates_hz=sample_rates,
        supported_reference_sample_rates_hz=reference_rates, available_demodulators=tuple(caps.get("enabled_streams", ())),
        aggregate_max_rate_hz=aggregate or None, timing_rate_hz=timing_rate, t660_tick_s=10e-12, t660_maximum_delay_s=3600.,
        t660_frame_capacity=readbacks.get("t660_frame_capacity"), frames_feature_observed=bool(readbacks.get("t660_frame_capacity")),
        configuration_id=str(configuration.get("system", {}).get("name", "installed")), actual_readbacks=readbacks,
        source_records=({"source_id": caps.get("source", "connected-readbacks"), "kind": "installed_readback"},
                        {"source_id": "T660-Manual-F5", "path": "references/manuals/T660/Highland Technologies T660 Manual.pdf", "pages": "6,8,10", "kind": "manufacturer_specification"}))


def inputs_from_context(context, settings, readbacks=None, *, configuration=None):
    inputs = resolve_runtime_inputs(context.configuration() if configuration is None else configuration, readbacks or {}, settings)
    for bundle_id in settings.calibration_bundle_ids:
        try:
            bundle = context.promoted_bundle(bundle_id)
            profile = bundle.manifest.get("steady_state_slow_scan", {}).get("planner_inputs", {}).get("scientific_profile", {})
            # These models have explicit numeric/configuration/support guards in
            # processing. Promotion alone cannot establish their applicability.
            for name in ("axis_correction", "path_balance"):
                if name in profile:
                    inputs.scientific_profile[name] = deepcopy(profile[name])
            unchecked = {name: deepcopy(profile[name]) for name in
                         ("measured_response_s", "intrinsic_resolution_cm1", "sample_group_delay_s",
                          "reference_group_delay_s", "direction_bit_by_direction") if name in profile}
            if unchecked:
                inputs.scientific_profile.setdefault("unapplied_calibration_fields", {})[bundle_id] = unchecked
                inputs.scientific_profile["runtime_warnings"].append(
                    f"Optional calibration {bundle_id}: response/delay/direction applicability is unresolved; fields not applied")
            inputs = replace(inputs, promoted_bundle_ids=(*inputs.promoted_bundle_ids, bundle_id),
                source_records=(*inputs.source_records, {"source_id": bundle_id, "path": str(bundle.path), "kind": "optional_promoted_calibration"}))
        except Exception as exc:
            inputs.scientific_profile["runtime_warnings"].append(f"Optional calibration {bundle_id}: {exc}")
    return inputs


def simulation_inputs(settings: SlowScanSettings) -> PlannerInputs:
    """Explicit synthetic fixture profile, never used automatically for hardware."""
    effective_segments = settings.segments or (SpectralSegment("range", 1, settings.lower_cm1, settings.upper_cm1),)
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
    profile["hf2li_capabilities"] = {role: {"orders": (1, 2, 3, 4), "timeconstants_by_order": {order: (.0001, .001, .002, .01) for order in range(1, 5)}}
                                    for role in ("sample", "reference")}
    for segment in effective_segments:
        profile["qcl_pulse_params"][str(segment.qcl or 1)] = {"pulse_rate_hz": 100000., "pulse_width_ns": 1000., "current_ma": 1.}
        profile["marker_channel_by_qcl"][str(segment.qcl or 1)] = segment.qcl or 1
    windows = tuple(QCLWindow(qcl, min(s.lower_cm1 for s in effective_segments if (s.qcl or 1) == qcl),
                             max(s.upper_cm1 for s in effective_segments if (s.qcl or 1) == qcl), source_id="SIMULATED-QCL")
                    for qcl in sorted({segment.qcl or 1 for segment in effective_segments}))
    return PlannerInputs(scientific_profile=profile, qcl_windows=windows,
                         supported_sample_rates_hz=(100., 1000., 10000.), available_demodulators=(0, 2, 3),
                         aggregate_max_rate_hz=30000., timing_rate_hz=10000., t660_tick_s=1e-9,
                         t660_maximum_delay_s=10., t660_frame_capacity=8192, frames_feature_observed=True,
                         tee_receiver_topology_verified=True, process_trigger_qualified=True, wavelength_markers_qualified=True,
                         configuration_id=settings.condition.configuration_id, condition_ids=(settings.condition.condition_id,),
                         modes=(settings.mode,), simulation=True, source_records=({"source_id": "SIMULATED", "kind": "synthetic_fixture"},))
