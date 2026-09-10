"""Dual-detector planning using the maintained regular sequence and HF2 filters.

Retained readbacks provide an offline preview only. A connected configuration
check probes both optical demodulators with the DIO carrier enabled; no data or
hardware output is acquired during discovery.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import math

from control_app.workflows.phase_scan import PhaseScanPlanError
from control_app.workflows.regular_phase_scan import (
    HF2Capabilities, HF2_SPECIFICATION, HF2_FILTER_DOCUMENTATION,
    RegularPhaseScanPlan, RegularPhaseScanSettings,
    build_regular_phase_scan_plan, select_hf2_settings,
)

SCHEMA_VERSION = "dual_detector_phase_scan_v1"
ENABLED_STREAMS = (0, 2, 3)
SOURCE_RECORD = ("evidence/experiments/runs/exploratory_air_checkout_20260902T224505_935642Z/"
                 "slow_scan_once/restore_fast_hf2li_snapshot.json")
ASSIGNMENT_SOURCES = (
    "instrument/wiring_map.yaml#detector_signal_paths",
    "instrument/default_wiring_state.md#detector-signal-paths",
    "instrument/recipes/hf2li_presets.yaml#detector_alignment",
    SOURCE_RECORD,
)


def detector_assignments():
    """Explicit physical roles from wiring records, separate from channel names."""
    return {
        role: {"role": role, "input": input_index, "adcselect": input_index,
               "demodulator": demod, "signal": "r", "oscselect": 0, "harmonic": 1,
               "input_label": f"HF2LI Signal {input_index+1} In (+)",
               "provenance": list(ASSIGNMENT_SOURCES)}
        for role, input_index, demod in (("sample", 0, 0), ("reference", 1, 3))
    }


def _preview_detector():
    return HF2Capabilities(enabled_streams=ENABLED_STREAMS, source=SOURCE_RECORD)


@dataclass(frozen=True)
class DualDetectorPhaseScanSettings(RegularPhaseScanSettings):
    pass


@dataclass(frozen=True)
class DualHF2Capabilities:
    sample: HF2Capabilities = field(default_factory=_preview_detector)
    reference: HF2Capabilities = field(default_factory=_preview_detector)
    device_id: str = "dev18500"
    timing_rate_sps: float = 230263.15789473685
    enabled_streams: tuple[int, ...] = ENABLED_STREAMS
    source: str = SOURCE_RECORD
    verified: bool = False
    tuning_ranges: tuple = ((1, 1638.8068850219217, 2077.2745597378685),)
    timing_table_capacity: int = 8192
    max_retained_bytes: int = 512 * 1024 * 1024
    readback_records: tuple = ()

    # Existing summary/plan plumbing can read common detector properties while
    # detector override menus use sample/reference profiles explicitly.
    @property
    def orders(self):
        return self.sample.orders

    @property
    def rates_sps(self):
        return self.sample.rates_sps

    @property
    def timeconstants_by_order(self):
        return self.sample.timeconstants_by_order

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict) or not {"sample", "reference"} <= value.keys():
            raise PhaseScanPlanError("Dual-detector capabilities require separate sample and reference profiles; check the connected device")
        data = {key: item for key, item in value.items() if key in cls.__dataclass_fields__}
        for role in ("sample", "reference"):
            data[role] = HF2Capabilities.from_dict(data[role])
        for key in ("enabled_streams", "tuning_ranges", "readback_records"):
            if key in data:
                data[key] = tuple(data[key])
        if "tuning_ranges" in data:
            data["tuning_ranges"] = tuple(tuple(row) for row in data["tuning_ranges"])
        return cls(**data)


DualDetectorCapabilities = DualHF2Capabilities


def _split_overrides(overrides):
    selected = {"sample": {}, "reference": {}}
    for key, value in dict(overrides or {}).items():
        role, name = (key.split("_", 1) if key.startswith(("sample_", "reference_"))
                      else ("sample", key))
        if name not in ("order", "timeconstant_s", "rate_sps"):
            raise PhaseScanPlanError(f"Unknown dual-detector HF2LI override: {key}")
        if name in selected[role] and selected[role][name] != value:
            raise PhaseScanPlanError(f"Conflicting {role} HF2LI overrides for {name}")
        selected[role][name] = value
    return selected


def select_dual_hf2_settings(settings, capabilities=None, overrides=None):
    caps = DualHF2Capabilities.from_dict(capabilities) if capabilities is not None else DualHF2Capabilities()
    if tuple(caps.enabled_streams) != ENABLED_STREAMS:
        raise PhaseScanPlanError("Dual-detector capabilities require sample demod 0, reference demod 3 and timing demod 2 enabled; check the connected device")
    requested = _split_overrides(overrides)
    roles = detector_assignments()
    channels = {}
    for role in ("sample", "reference"):
        profile = HF2Capabilities.from_dict(getattr(caps, role))
        if tuple(profile.enabled_streams) != ENABLED_STREAMS:
            raise PhaseScanPlanError(f"The {role} HF2LI profile was not checked with all three streams enabled; check the connected device")
        if profile.device_id != caps.device_id or profile.timing_rate_sps != caps.timing_rate_sps:
            raise PhaseScanPlanError(f"The {role} profile has a different device or timing rate; check the connected device")
        try:
            chosen = select_hf2_settings(settings, profile, requested[role], _expected_streams=ENABLED_STREAMS)
        except PhaseScanPlanError as exc:
            raise PhaseScanPlanError(str(exc).replace("CH1", role.title()).replace("two-stream", "three-stream")) from exc
        channels[role] = {**chosen, **roles[role]}
    total_rate = caps.timing_rate_sps + sum(channels[role]["rate_sps"] for role in channels)
    if max(caps.timing_rate_sps, *(c["rate_sps"] for c in channels.values())) > 231000 or total_rate > 700000:
        raise PhaseScanPlanError("Selected sample, reference and timing rates exceed HF2 three-stream transfer capacity; choose supported lower rates or check the connected device. No requested value was changed.")
    sample, reference = channels["sample"], channels["reference"]
    # Quadrature is an explicit conservative engineering estimate of the two
    # detector responses; it is neither deconvolution nor optical calibration.
    temporal = math.hypot(sample["temporal_resolution_s"], reference["temporal_resolution_s"])
    rise = math.hypot(sample["filter_rise_time_s"], reference["filter_rise_time_s"])
    met = temporal <= sample["target_temporal_resolution_s"]
    warnings = [f"{role.title()}: {channel['warning']}" for role, channel in channels.items() if channel["warning"]]
    if not met and not warnings:
        warnings.append("The combined detector response exceeds the requested resolution; phase spacing is not achievable temporal resolution.")
    selection = {**sample, "sample": sample, "reference": reference, "detectors": channels,
        "detector_roles": roles, "enabled_streams": list(ENABLED_STREAMS),
        "mode": "manual" if overrides else "automatic", "requested": dict(overrides or {}),
        "capability_source": caps.source, "capability_verified": bool(caps.verified and
            all(channel["capability_verified"] for channel in channels.values())),
        "combined_rate_sps": total_rate, "temporal_resolution_s": temporal,
        "filter_rise_time_s": rise, "spectral_broadening_cm1": settings.scan_speed_cm1_s*rise,
        "effective_spectral_resolution_cm1": settings.scan_speed_cm1_s*temporal,
        "differential_filter_delay_s": sample["filter_group_delay_s"]-reference["filter_group_delay_s"],
        "resolution_target_met": met, "warning": " ".join(warnings),
        "estimate_basis": "Quadrature of both cascaded-RC detector responses and measured sample intervals; filter group delays are estimates, not calibrated optical arrival",
        "documentation": [HF2_SPECIFICATION, HF2_FILTER_DOCUMENTATION]}
    return selection


@dataclass(frozen=True)
class DualDetectorPhaseScanPlan(RegularPhaseScanPlan):
    detector_assignments: dict = field(default_factory=detector_assignments)
    channel_balance_calibration: dict = field(default_factory=dict)

    def to_dict(self):
        document = super().to_dict()
        document.update(schema_version=SCHEMA_VERSION, method="dual_detector_phase_scan",
            detector_mode="simultaneous_sample_reference", detector_assignments=self.detector_assignments,
            channel_balance_calibration=self.channel_balance_calibration)
        document.pop("detector_input", None)
        document["sequence"].pop("blank", None)
        document["sequence"].update(preliminary="unpumped_sample_and_matched_buffer_reference",
            reference="simultaneously_recorded_through_matched_buffer_blank")
        document["normalization"] = {"ratio": "Q(nu,t) = S(nu,t) / R(nu,t)",
            "baseline": "Q0(nu), separately retained unpumped sample/reference ratio",
            "delta_absorbance": "-log10(Q(nu,t) / Q0(nu))",
            "absolute_absorbance": "-log10(Q(nu,t) / B(nu)); only with applicable promoted channel-balance calibration",
            "matching": "detector timestamps corrected by recorded estimated group delay, measured wavenumber and measured electrical pump sync",
            "missing_data": "unsupported, nonpositive and invalid regions remain missing with reasons; no extrapolation"}
        document["limitations"] = [
            "Measured controller markers define wavelength; unsupported measured coverage remains missing.",
            "Time is relative to electrical pump sync; optical arrival is not calibrated.",
            "Both detector filter delays and resolution are engineering estimates; no deconvolution is applied.",
            "Uncorrected sample/reference ratio is not absolute transmission or absorbance."]
        return document


def build_dual_detector_phase_scan_plan(settings=None, capabilities=None, overrides=None, *, channel_balance_calibration=None):
    settings = settings or DualDetectorPhaseScanSettings()
    if not isinstance(settings, DualDetectorPhaseScanSettings):
        raise PhaseScanPlanError("Dual-Detector Phase Scan requires a dual-detector plan; single-detector plans cannot be loaded in this mode")
    caps = DualHF2Capabilities.from_dict(capabilities) if capabilities is not None else DualHF2Capabilities()
    # Reuse all cadence, signed scheduling, trigger, allocation and trajectory
    # checks from the regular planner with this explicitly resolved selection.
    geometry_caps = replace(caps.sample, tuning_ranges=caps.tuning_ranges,
        timing_table_capacity=caps.timing_table_capacity, max_retained_bytes=caps.max_retained_bytes)
    base = build_regular_phase_scan_plan(settings, geometry_caps,
        _selection=lambda: select_dual_hf2_settings(settings, caps, overrides))
    selection = base.hf2_selection
    if base.scan_duration_s < 2/selection["reference"]["rate_sps"]:
        raise PhaseScanPlanError("The scan is shorter than two reference-detector sample intervals; increase the span, reduce speed or select a supported higher reference rate")
    capacity = dict(base.capacity)
    ref_samples = math.ceil(base.capture_window["duration_s"]*selection["reference"]["rate_sps"])
    extra_payload = base.total_scans*ref_samples*2*16
    extra_metadata = base.total_scans*2*4096
    capacity["estimated_uncompressed_payload_bytes"] += extra_payload
    capacity["metadata_allowance_bytes"] += extra_metadata
    capacity["estimated_retained_bytes"] += extra_payload + extra_metadata
    estimated = capacity["estimated_retained_bytes"]
    capacity["warning"] = (f"Warning: estimated dual-detector record storage is {estimated/1e6:.1f} MB; increase Phase-delay spacing to reduce memory use."
                           if estimated > caps.max_retained_bytes else "")
    return DualDetectorPhaseScanPlan(
        settings=base.settings, phases_per_repetition=base.phases_per_repetition,
        scan_duration_s=base.scan_duration_s, first_phase_tick=base.first_phase_tick,
        trajectory_time_bounds_s=base.trajectory_time_bounds_s, trajectory_source=base.trajectory_source,
        hf2_selection=selection, capture_window=base.capture_window, capacity=capacity,
        channel_balance_calibration=dict(channel_balance_calibration or {}))


def discover_dual_capabilities(config_path=None, *, hf_factory=None, laser_factory=None):
    from control_app.devices.hf2li_service import HF2LIService
    from control_app.devices.mircat_service import MircatService
    hf = hf_factory() if hf_factory else HF2LIService.from_config(config_path=config_path)
    laser = laser_factory() if laser_factory else MircatService.from_config(config_path=config_path)
    try:
        hf.connect()
        capabilities = hf.discover_dual_phase_scan_capabilities()
        laser.initialize()
        ranges = [laser.get_qcl_tuning_range(i) for i in range(1, laser.get_num_installed_qcls()+1)]
        capabilities["tuning_ranges"] = tuple((r["qcl"], r["min_cm1"], r["max_cm1"]) for r in ranges)
        return DualHF2Capabilities.from_dict(capabilities)
    finally:
        try:
            hf.close()
        finally:
            laser.deinitialize()


discover_dual_phase_scan_capabilities = discover_dual_capabilities
