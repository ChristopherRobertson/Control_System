"""Compact user inputs and independent automatic installed-device settings.

The five main inputs describe spectral coverage and observation duration. None
on an advanced setting means automatic, and is retained in the requested plan
so changing one override never freezes unrelated automatic choices.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from copy import deepcopy
from math import ceil, isfinite, log10
from typing import Any, Mapping

EXPERIMENT_ID = "single_pump_scan_burst"
SCHEMA_VERSION = 1
INSTALLED_QCL = 1
PROBE_DUTY_CEILING = 0.30
CONDITION_PROFILES = {
    "77K-HRP-G-S": {"protein": "HRP-CO", "architecture_id": "ARC-77-HRP-SPB",
                    "nominal_temperature_k": 77.0, "populations": ("sample-fitted HRP populations",)},
    "77K-Mb-G-S": {"protein": "MbCO", "architecture_id": "ARC-77-MB-SPB",
                   "nominal_temperature_k": 77.0, "populations": ("A0", "A1", "A3")},
}


@dataclass(frozen=True)
class Settings:
    mode: str = "single"
    condition_id: str = ""
    sample_id: str = ""
    preparation_id: str = ""
    accepted_state_id: str = ""
    matrix_id: str = ""
    cell_id: str = ""
    position_id: str = ""
    temperature_identity: str = ""
    thermal_history_id: str = ""
    measured_temperature_k: float | None = None
    temperature_uncertainty_k: float | None = None
    min_temperature_k: float | None = None
    max_temperature_k: float | None = None
    scan_start_cm1: float | None = 1900.0
    scan_stop_cm1: float | None = 1950.0
    scan_speed_cm1_s: float | None = 5000.0
    early_observation_s: float = 1.0
    scan_interval_s: float | None = None
    first_scan_delay_s: float | None = None
    early_scan_count: int | None = None
    later_burst_count: int | None = None
    scans_per_burst: int | None = None
    final_scan_count: int | None = None
    first_later_burst_s: float | None = None
    observation_limit_s: float | None = 1200.0
    later_burst_times_s: tuple[float, ...] = ()
    schedule_kind: str = "logarithmic"
    preliminary_scan_count: int | None = None
    blank_source: str = "acquire"
    sample_rate_hz: float | None = None
    reference_rate_hz: float | None = None
    timing_rate_hz: float | None = None
    detector_matching_time_tolerance_s: float | None = None
    wavenumber_matching_tolerance_cm1: float | None = None
    sample_demod: int = 0
    reference_demod: int = 3
    timing_demod: int = 2
    hf2_filter_tc_s: float | None = None
    hf2_filter_order: int | None = None
    reference_filter_tc_s: float | None = None
    reference_filter_order: int | None = None
    sample_input_range_v: float | None = None
    reference_input_range_v: float | None = None
    qcl: int | None = None
    probe_rate_hz: float | None = None
    probe_pulse_width_s: float | None = None
    mircat_internal_pulse_rate_hz: float | None = None
    probe_current_ma: float | None = None
    probe_reference_delay_s: float = 0.0
    pump_fire_to_q_s: float | None = None
    pump_fire_width_s: float | None = None
    pump_q_width_s: float | None = None
    process_width_s: float | None = None
    pump_polarity: str = "negative"
    process_polarity: str = "negative"
    pump_dose_record_id: str = ""
    max_probe_exposure_s: float | None = None  # cumulative pulse-on seconds, not wall time
    probe_during_wait: bool = False
    temperature_check_interval_s: float | None = None
    plateau_enabled: bool = False
    plateau_relative_tolerance: float | None = None
    plateau_required_bursts: int = 3
    plateau_band_windows_cm1: tuple[tuple[float, float], ...] = ()
    configuration_time_s: float | None = None
    tuning_settling_time_s: float | None = None
    controls_time_s: float | None = None
    restoration_time_s: float | None = None
    processing_time_s: float | None = None
    upload_seconds_per_frame: float | None = None
    native_chunk_duration_s: float = 0.25
    max_memory_bytes: int = 268435456
    storage_budget_bytes: int | None = None
    calibration_ids: tuple[str, ...] = ()
    promoted_bundle_ids: tuple[str, ...] = ()
    sample_selection_id: str = ""
    controls_record_ids: tuple[str, ...] = ()
    settings_sources: dict[str, str] = field(default_factory=dict)
    hardware_evidence: dict[str, Any] = field(default_factory=dict)
    example_only: bool = False
    schema_version: int = SCHEMA_VERSION
    experiment_id: str = EXPERIMENT_ID

    @property
    def architecture_id(self) -> str:
        return "single_pump_scan_burst"

    @property
    def instance_id(self) -> str:
        return f"{EXPERIMENT_ID}:{self.mode}"

    @property
    def demod_indices(self) -> tuple[int, ...]:
        return (self.sample_demod, self.reference_demod) if self.mode == "dual" else (self.sample_demod,)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Settings":
        copied = dict(data)
        if copied.get("experiment_id", EXPERIMENT_ID) != EXPERIMENT_ID:
            raise ValueError("Settings belong to another experiment")
        if copied.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
            raise ValueError("Unsupported single-pump settings schema version")
        unknown = set(copied) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown settings fields: {', '.join(sorted(unknown))}")
        for name in ("later_burst_times_s", "calibration_ids", "promoted_bundle_ids", "controls_record_ids"):
            if name in copied:
                copied[name] = tuple(copied[name])
        if "plateau_band_windows_cm1" in copied:
            copied["plateau_band_windows_cm1"] = tuple(tuple(pair) for pair in copied["plateau_band_windows_cm1"])
        for name in ("settings_sources", "hardware_evidence"):
            if name in copied:
                copied[name] = dict(copied[name])
        return cls(**copied)


@dataclass(frozen=True)
class Capabilities:
    """Readbacks are supplied by an owned adapter; constructing this does no I/O."""
    frame_capacity: int = 8192
    predivider_max: int = 4294967295
    edge_quantum_s: float = 10e-12
    edge_max_s: float = 3600.0
    synthesizer_quantum_hz: float = 0.02
    synthesizer_max_hz: float = 16000000.0
    train_count_max: int = 4294967295
    train_spacing_min_s: float = 80e-9
    train_spacing_max_s: float = 10.0
    train_spacing_quantum_s: float = 20e-9
    frame_guard_s: float = 1e-6
    probe_duty_max: float = 0.30
    probe_rate_max_hz: float | None = None
    probe_pulse_width_max_s: float | None = None
    mircat_internal_rate_max_hz: float | None = None
    mircat_internal_width_max_s: float | None = None
    probe_current_min_ma: float | None = None
    probe_current_max_ma: float | None = None
    hf2_aggregate_rate_max_hz: float = 700000.0
    sample_rates_hz: tuple[float, ...] = ()
    reference_rates_hz: tuple[float, ...] = ()
    timing_rates_hz: tuple[float, ...] = ()
    scan_speed_min_cm1_s: float | None = None
    scan_speed_max_cm1_s: float | None = None
    wavenumber_min_cm1: float | None = None
    wavenumber_max_cm1: float | None = None
    frame_feature_verified: bool = False
    detector_rates_verified: bool = False
    topology_verified: bool = False
    optical_pump_observation_available: bool = False
    temperature_observation_available: bool = False
    probe_idle_control_available: bool = True
    device_ids: dict[str, str] = field(default_factory=dict)
    source_records: tuple[str, ...] = (
        "references/manuals/T660/Highland Technologies T660 Manual.pdf §§2,3.5,5.2–5.4",
        "instrument/wiring_map.yaml", "instrument/hardware_configuration.yaml",
    )
    actual_values: dict[str, Any] = field(default_factory=dict)
    operating_values: dict[str, Any] = field(default_factory=dict)
    qcl_ranges: tuple[dict[str, Any], ...] = ()
    sample_filter_orders: tuple[int, ...] = ()
    reference_filter_orders: tuple[int, ...] = ()
    sample_timeconstants_by_order: dict[Any, tuple[float, ...]] = field(default_factory=dict)
    reference_timeconstants_by_order: dict[Any, tuple[float, ...]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Capabilities":
        values = dict(data)
        for name in ("sample_rates_hz", "reference_rates_hz", "timing_rates_hz", "source_records",
                     "qcl_ranges", "sample_filter_orders", "reference_filter_orders"):
            if name in values:
                values[name] = tuple(values[name])
        return cls(**values)


ESSENTIAL_FIELDS = ("scan_start_cm1", "scan_stop_cm1", "scan_speed_cm1_s", "early_observation_s", "observation_limit_s")
AUTOMATIC_FIELDS = ("scan_interval_s", "first_scan_delay_s", "early_scan_count", "later_burst_count",
    "scans_per_burst", "final_scan_count", "first_later_burst_s", "preliminary_scan_count",
    "sample_rate_hz", "reference_rate_hz", "timing_rate_hz", "detector_matching_time_tolerance_s",
    "wavenumber_matching_tolerance_cm1", "hf2_filter_tc_s", "hf2_filter_order",
    "reference_filter_tc_s", "reference_filter_order", "sample_input_range_v", "reference_input_range_v",
    "qcl", "probe_rate_hz", "probe_pulse_width_s", "mircat_internal_pulse_rate_hz", "probe_current_ma", "pump_fire_to_q_s",
    "pump_fire_width_s", "pump_q_width_s", "process_width_s", "configuration_time_s", "tuning_settling_time_s",
    "controls_time_s", "restoration_time_s", "processing_time_s", "upload_seconds_per_frame")


def _positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value > 0


def resolve_settings(settings: Settings, *, capabilities: Capabilities | None = None,
                     configuration: Mapping[str, Any] | None = None,
                     promoted_values: Mapping[str, Any] | None = None,
                     installed_readbacks: Mapping[str, Any] | None = None) -> Settings:
    """Resolve each automatic field independently, without qualification gates.

    Detector readbacks take precedence over module configuration defaults.
    The probe carrier instead uses the tab request or the 2 MHz Auto default;
    its internal acceptance rate is derived with 5% headroom.
    Explicit non-None user values remain overrides except legacy QCL routing:
    the installed single-channel MIRcat always resolves to QCL 1. Evidence and sample
    metadata are preserved but never consulted to choose numerical settings.
    The deprecated promoted_values argument is accepted for compatibility only.
    """
    cap = capabilities or Capabilities()
    values = settings.to_dict()
    config = dict(configuration or {})
    module = config.get("single_pump_scan_burst", {})
    configured = dict(module.get("defaults", module.get("settings", {}))) if isinstance(module, Mapping) else {}
    live = dict(cap.operating_values)
    for supplied in (installed_readbacks,):
        if supplied:
            payload = supplied.get("values", supplied)
            if isinstance(payload, Mapping):
                live.update({key: value for key, value in payload.items() if key in AUTOMATIC_FIELDS})

    def choose(name: str, fallback: Any, basis: str, *, use_live: bool = True) -> Any:
        if values[name] is not None:
            return values[name]
        if use_live and live.get(name) is not None:
            value, source = live[name], "live installed readback"
        elif configured.get(name) is not None:
            value, source = configured[name], "installed module configuration"
        else:
            value, source = fallback, basis
        values[name] = deepcopy(value)
        values["settings_sources"][name] = f"automatic: {source}"
        return value

    values["qcl"] = INSTALLED_QCL
    values["settings_sources"]["qcl"] = "installed single-QCL instrument: QCL 1"
    # Historical multi-QCL caches may contain useful QCL 1 readbacks, but never
    # select a channel or lend another channel's operating values to this device.
    qcl_parameters = live.get("qcl_parameters", ())
    if isinstance(qcl_parameters, Mapping):
        matching_qcl = qcl_parameters.get(INSTALLED_QCL, qcl_parameters.get(str(INSTALLED_QCL)))
    else:
        matching_qcl = next((record for record in qcl_parameters if isinstance(record, Mapping) and record.get("qcl") == INSTALLED_QCL), None)
    if live.get("qcl") is not None and live["qcl"] != INSTALLED_QCL:
        for name in ("probe_rate_hz", "probe_pulse_width_s", "mircat_internal_pulse_rate_hz", "probe_current_ma"):
            live.pop(name, None)
    if isinstance(matching_qcl, Mapping):
        for source, target in (("pulse_rate_hz", "mircat_internal_pulse_rate_hz"), ("current_ma", "probe_current_ma")):
            if matching_qcl.get(source) is not None:
                live[target] = matching_qcl[source]
        if matching_qcl.get("pulse_width_ns") is not None:
            live["probe_pulse_width_s"] = matching_qcl["pulse_width_ns"] / 1e9

    # Standing installed pulse topology; each value may be replaced independently
    # by its live readback or explicit override. A missing laser current is kept
    # as None so the service preserves the device's existing current.
    # The internal acceptance clock is distinct from the external opportunity
    # rate and is derived from the selected carrier, never stale readbacks.
    from control_app.measurement_host.laser_settings import MIRCAT_AUTO_REPETITION_RATE_HZ
    if values["probe_rate_hz"] is None:
        values["probe_rate_hz"] = MIRCAT_AUTO_REPETITION_RATE_HZ
        values["settings_sources"]["probe_rate_hz"] = "automatic 2 MHz; duty and acceptance limits validated without reducing the request"
    from control_app.measurement_host.laser_settings import mircat_acceptance_rate_hz, mircat_automatic_width_ns
    if _positive(values["probe_rate_hz"]):
        values["mircat_internal_pulse_rate_hz"] = mircat_acceptance_rate_hz(values["probe_rate_hz"])
        values["settings_sources"]["mircat_internal_pulse_rate_hz"] = "5% above selected T660 rate"
    fallback_width = mircat_automatic_width_ns(values["mircat_internal_pulse_rate_hz"]) / 1e9 if _positive(values["probe_rate_hz"]) else 142e-9
    choose("probe_pulse_width_s", fallback_width, "automatic MIRcat width bounded by 30% internal duty")
    choose("probe_current_ma", None, "preserve existing QCL current")
    choose("sample_input_range_v", 1.0, "installed HF2LI 1 V input range")
    choose("reference_input_range_v", 1.0, "installed HF2LI 1 V input range")
    choose("pump_fire_to_q_s", 179830e-9, "ndyag_alignment_10hz nominal, uncalibrated Fire-to-Q-switch timing")
    choose("pump_fire_width_s", 10e-6, "installed Surelite command width")
    choose("pump_q_width_s", 10e-6, "installed Surelite command width")
    choose("process_width_s", .010, "installed negative MIRcat process-trigger command")
    choose("first_scan_delay_s", 0.0, "earliest scan after Q-switch command")
    timing_candidates = [v for v in cap.timing_rates_hz if _positive(v)]
    choose("timing_rate_hz", max(timing_candidates) if timing_candidates else 230000.0,
           "highest installed timing stream rate" if timing_candidates else "HF2LI 230 kSa/s readout request", use_live=False)
    auto_roles = [("sample_rate_hz", cap.sample_rates_hz)]
    if values["mode"] == "dual":
        auto_roles.append(("reference_rate_hz", cap.reference_rates_hz))
    auto_names = {name for name, _ in auto_roles if values[name] is None}
    if _positive(values["timing_rate_hz"]) and _positive(cap.hf2_aggregate_rate_max_hz):
        available = cap.hf2_aggregate_rate_max_hz - values["timing_rate_hz"] - sum(values[name] for name, _ in auto_roles if name not in auto_names and _positive(values[name]))
        per_auto = max(0., available / max(1, len(auto_names)))
    else:
        per_auto = 230000.0
    for name, candidates in auto_roles:
        supported = [v for v in candidates if _positive(v) and v <= per_auto]
        fallback = max(supported) if supported else min(230000.0, per_auto)
        choose(name, fallback, "highest supported detector rate within aggregate throughput" if supported else
               "provisional detector rate request within aggregate throughput", use_live=False)
    # Keep an unused reference field resolved for portable detector-mode settings.
    if values["mode"] == "single":
        choose("reference_rate_hz", values["sample_rate_hz"], "sample-matched unused reference rate", use_live=False)
    matched_rates = [values["sample_rate_hz"]] + ([values["reference_rate_hz"]] if values["mode"] == "dual" else [])
    rate = min(matched_rates) if all(_positive(v) for v in matched_rates) else 230000.0
    choose("detector_matching_time_tolerance_s", .5 / rate, "half the slower detector sample interval", use_live=False)
    speed = values["scan_speed_cm1_s"] if _positive(values["scan_speed_cm1_s"]) else 5000.0
    choose("wavenumber_matching_tolerance_cm1", speed / rate, "scan distance over the slower detector sample interval", use_live=False)
    for order_name, tc_name, orders, constants in (
        ("hf2_filter_order", "hf2_filter_tc_s", cap.sample_filter_orders, cap.sample_timeconstants_by_order),
        ("reference_filter_order", "reference_filter_tc_s", cap.reference_filter_orders, cap.reference_timeconstants_by_order)):
        order = choose(order_name, min(orders) if orders else 1,
                       "lowest supported order for fast spectral response" if orders else "provisional first-order filter request", use_live=False)
        supported = constants.get(order, constants.get(str(order), ()))
        supported = [v for v in supported if _positive(v)]
        choose(tc_name, min(supported) if supported else .8e-6,
               "shortest supported time constant for selected filter order" if supported else "provisional 0.8 microsecond time-constant request", use_live=False)

    if all(_positive(values[key]) for key in ("scan_start_cm1", "scan_stop_cm1", "scan_speed_cm1_s")):
        duration = abs(values["scan_stop_cm1"] - values["scan_start_cm1"]) / values["scan_speed_cm1_s"]
    else:
        duration = .01  # Invalid essentials are reported by the planner itself.
    if all(isinstance(values[key], (int, float)) and isfinite(values[key]) for key in ("pump_fire_to_q_s", "first_scan_delay_s", "process_width_s")):
        offset = values["pump_fire_to_q_s"] + values["first_scan_delay_s"]
        cadence = offset + max(duration, values["process_width_s"]) + max(.001, duration * .2)
    else:
        cadence = .02
    interval = choose("scan_interval_s", cadence, "scan/process duration plus 20% return allowance (minimum 1 ms)", use_live=False)
    first_delay = values["first_scan_delay_s"] if isinstance(values["first_scan_delay_s"], (int, float)) and isfinite(values["first_scan_delay_s"]) else 0.0
    early_count = max(1, ceil(max(0.0, values["early_observation_s"] - first_delay - duration) / interval) + 1) if _positive(values["early_observation_s"]) and _positive(interval) else 1
    choose("early_scan_count", early_count, "minimum scans whose last scan end covers the requested early horizon", use_live=False)
    choose("scans_per_burst", 3, "three individual spectra per later burst", use_live=False)
    choose("final_scan_count", 3, "three final-state spectra", use_live=False)
    choose("preliminary_scan_count", 3, "three unpumped blank/preliminary spectra", use_live=False)
    early_end = first_delay + values["early_scan_count"] * interval if _positive(values["early_scan_count"]) and _positive(interval) else values["early_observation_s"]
    first_later = choose("first_later_burst_s", max(early_end * 2, early_end + interval * 4), "separate burst after the complete early train", use_live=False)
    ratio = values["observation_limit_s"] / first_later if _positive(values["observation_limit_s"]) and _positive(first_later) else 1
    count = len(values["later_burst_times_s"]) if values["later_burst_times_s"] else max(1, ceil(max(0, log10(ratio)) * 3) + 1)
    choose("later_burst_count", count, "three logarithmic intervals per elapsed-time decade", use_live=False)
    for name, value in (("configuration_time_s", 10.0), ("tuning_settling_time_s", .1), ("controls_time_s", 0.0),
                        ("restoration_time_s", 2.0), ("processing_time_s", 2.0), ("upload_seconds_per_frame", .04)):
        choose(name, value, "preparation/processing estimate; actual stage durations retained")
    return Settings.from_dict(values)


def resolve_live_settings(settings: Settings | Mapping[str, Any], readbacks: Mapping[str, Any] | Capabilities,
                          configuration: Mapping[str, Any] | None = None) -> Settings:
    """Owned adapters supply readbacks; this resolver itself performs no I/O."""
    if not isinstance(settings, Settings):
        settings = Settings.from_dict(settings)
    if isinstance(readbacks, Capabilities):
        return resolve_settings(settings, capabilities=readbacks, configuration=configuration)
    names = {f.name for f in fields(Capabilities)}
    payload = readbacks.get("capabilities", readbacks)
    cap = Capabilities.from_dict({key: value for key, value in payload.items() if key in names})
    return resolve_settings(settings, capabilities=cap, configuration=configuration,
                            installed_readbacks={"values": readbacks.get("values", {})})


def example_settings(mode: str = "single") -> Settings:
    """Explicit nonbiological simulation example, NEVER a commissioned recipe."""
    return Settings(mode=mode, sample_id="EXAMPLE-SAMPLE", preparation_id="EXAMPLE-PREP",
        accepted_state_id="EXAMPLE-HRP-STATE", matrix_id="EXAMPLE-MATRIX", cell_id="EXAMPLE-CELL",
        position_id="EXAMPLE-POSITION", temperature_identity="EXAMPLE-TEMP", thermal_history_id="EXAMPLE-HISTORY",
        measured_temperature_k=77.0, temperature_uncertainty_k=0.5, min_temperature_k=75.0, max_temperature_k=80.0,
        scan_start_cm1=1900.0, scan_stop_cm1=1950.0, scan_speed_cm1_s=5000.0,
        scan_interval_s=0.02, first_scan_delay_s=0.001, early_scan_count=10,
        first_later_burst_s=1.0, observation_limit_s=1200.0, sample_rate_hz=10000.0,
        reference_rate_hz=10000.0, timing_rate_hz=100000.0, hf2_filter_tc_s=0.00001,
        hf2_filter_order=1, reference_filter_tc_s=0.00001, reference_filter_order=1,
        sample_input_range_v=1.0, reference_input_range_v=1.0, qcl=1,
        probe_rate_hz=1000000.0, probe_pulse_width_s=100e-9, probe_current_ma=100.0,
        pump_fire_to_q_s=0.0001, pump_fire_width_s=1e-6, pump_q_width_s=1e-6,
        process_width_s=1e-6, pump_dose_record_id="EXAMPLE-DOSE", max_probe_exposure_s=10.0,
        temperature_check_interval_s=1.0, configuration_time_s=10.0, tuning_settling_time_s=2.0,
        controls_time_s=20.0, restoration_time_s=2.0, processing_time_s=2.0,
        upload_seconds_per_frame=0.04, sample_selection_id="EXAMPLE-SPECTRAL-SELECTION",
        plateau_band_windows_cm1=((1910.0, 1920.0), (1928.0, 1940.0)), example_only=True)
