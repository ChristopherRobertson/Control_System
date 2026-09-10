"""Typed, hardware-free planning with separate structural and readiness checks."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .settings import (EXPERIMENT_ID, MIRCAT_QCL, AcquisitionIntent, RepeatedRapidScanSettings,
                       validate_mircat_pulse_pair, validate_probe_optical_pulse_pair)
from .timing import CompiledMovie, T660_FRAME_CAPACITY, compile_movie


@dataclass(frozen=True)
class HardwareCapabilities:
    frame_capacity: int = T660_FRAME_CAPACITY
    max_aggregate_rate_hz: float | None = None
    max_movie_bytes: int | None = None
    available_memory_bytes: int | None = None
    selected_baseline_bytes: int = 0
    available_demodulators: tuple[int, ...] = (0, 1, 2, 3, 4, 5)
    connected_readback_id: str = ""
    detector_roles_verified: bool = False
    receiver_topology_verified: bool = False
    continuous_recording_verified: bool = False
    actual_sample_rate_hz: float | None = None
    actual_reference_rate_hz: float | None = None
    acquisition_timing_rate_hz: float | None = None
    actual_scan_period_s: float | None = None
    supported_sample_rates_hz: tuple[float, ...] = ()
    live_settings: dict[str, Any] = field(default_factory=dict)
    scan_transition_s: float | None = None
    unsupported_automatic_actions: tuple[str, ...] = ("sample exchange", "pump blocking", "temperature control", "position change")


@dataclass(frozen=True)
class CalibrationEvidence:
    calibration_ids: tuple[str, ...] = ()
    source: str = ""
    promoted: bool = False
    trajectory_id: str = ""
    electrical_timing_id: str = ""
    response_id: str = ""
    detector_id: str = ""
    topology_id: str = ""
    reset_equivalence_id: str = ""
    optical_time_zero_id: str = ""
    condition_id: str = ""
    applicable_settings: dict[str, Any] = field(default_factory=dict)
    operating_values: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReadinessItem:
    code: str
    message: str
    blocks_hardware: bool = False


@dataclass(frozen=True)
class MoviePlan:
    movie_id: str
    phase_index: int
    requested_phase_s: float
    selected_phase_s: float
    direction: str
    control: str
    repeat_index: int
    pump_count: int
    compiled: CompiledMovie
    qualification_scans: int
    required_action: str = ""

    @property
    def frames(self):
        return self.compiled.frames

    @property
    def duration_s(self) -> float:
        return self.compiled.duration_s

    @property
    def scans_per_movie(self) -> int:
        return self.compiled.expected_scan_count


@dataclass(frozen=True)
class RepeatedRapidScanPlan:
    settings: RepeatedRapidScanSettings
    movies: tuple[MoviePlan, ...]
    capabilities: HardwareCapabilities
    calibration: CalibrationEvidence
    readiness_items: tuple[ReadinessItem, ...]
    requested: dict[str, Any]
    selected: dict[str, Any]
    actual: dict[str, Any]
    estimates: dict[str, Any]
    schema_version: int = 1
    experiment_id: str = EXPERIMENT_ID

    @property
    def mode(self) -> str:
        return self.settings.mode

    @property
    def condition_id(self) -> str:
        return self.settings.condition_id

    @property
    def ready_for_hardware(self) -> bool:
        return not any(item.blocks_hardware for item in self.readiness_items)

    @property
    def pump_count(self) -> int:
        return sum(movie.pump_count for movie in self.movies)

    @property
    def movie_count(self) -> int:
        return len(self.movies)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RepeatedRapidScanPlan":
        if value.get("experiment_id") != EXPERIMENT_ID or value.get("schema_version") != 1:
            raise ValueError("Incompatible repeated_rapid_scan plan identity/schema")
        # Compiled commands are always rebuilt and structurally validated from
        # editable science settings; saved readbacks remain informational.
        return build_plan(RepeatedRapidScanSettings.from_dict(value["settings"]),
                          capabilities=value.get("capabilities"), calibration=value.get("calibration"))


def _typed(value: Any, cls):
    if value is None:
        return cls()
    if isinstance(value, cls):
        return value
    if not isinstance(value, Mapping):
        raise ValueError(f"{cls.__name__} must be a typed value or mapping")
    data = dict(value)
    for key in ("available_demodulators", "supported_sample_rates_hz", "unsupported_automatic_actions", "calibration_ids"):
        if key in data:
            data[key] = tuple(data[key])
    return cls(**data)


def resolve_intent_settings(intent: AcquisitionIntent | Mapping[str, Any], *, mode: str = "single",
                            base_settings: RepeatedRapidScanSettings | Mapping[str, Any] | None = None,
                            capabilities: HardwareCapabilities | Mapping[str, Any] | None = None,
                            overrides: Mapping[str, Any] | None = None) -> RepeatedRapidScanSettings:
    """Resolve essential intent from actual readbacks and independent overrides.

    Existing values remain requests when no readback is available. No calibration,
    temperature, evidence acceptance, or condition label participates in choice.
    Scan periods are rounded up to whole carrier cycles; phases use the native
    10 ps grid. Overrides persist separately from the selected numeric values.
    """
    if not isinstance(intent, AcquisitionIntent):
        intent = AcquisitionIntent.from_dict(intent)
    intent.validate()
    base = base_settings or RepeatedRapidScanSettings(mode=mode)
    if isinstance(base, Mapping):
        base = RepeatedRapidScanSettings.from_dict(base)
    if mode not in ("single", "dual"):
        raise ValueError("mode must be single or dual")
    caps = _typed(capabilities, HardwareCapabilities)
    manual = dict(base.manual_overrides if overrides is None else overrides)
    # Optional MIRcat members are independently automatic: a saved null is not
    # a command to erase a known connected value or copy the external TTL pair.
    for name in ("mircat_pulse_rate_hz", "mircat_pulse_width_ns", "mircat_current_ma"):
        if manual.get(name) is None:
            manual.pop(name, None)
    protected = {"mode", "execution", "condition", "experiment_id", "schema_version", "acquisition_intent",
                 "manual_overrides", "historical_ui_settings", "scan_start_cm1", "scan_stop_cm1", "repeats", "phase_offsets_s", "post_scans"}
    known = set(base.__dataclass_fields__)
    if set(manual) - (known - protected):
        raise ValueError("Unsupported manual overrides: " + ", ".join(sorted(set(manual) - (known - protected))))
    live = {key: value for key, value in caps.live_settings.items() if key in known - protected and value is not None}
    for cap_name, field_name in (("actual_sample_rate_hz", "sample_rate_hz"),
                                  ("actual_reference_rate_hz", "reference_rate_hz")):
        actual_value = getattr(caps, cap_name)
        if actual_value is not None:
            live.setdefault(field_name, actual_value)
    data = base.to_dict()
    data.update(live)
    data.update(manual)
    data.update(mode=mode, execution="hardware", scan_start_cm1=intent.spectral_min_cm1,
                scan_stop_cm1=intent.spectral_max_cm1, repeats=intent.repeats)
    if caps.available_memory_bytes is not None and "memory_limit_bytes" not in manual:
        if type(caps.available_memory_bytes) is not int or caps.available_memory_bytes <= 0:
            raise ValueError("available host memory must be a positive integer byte count")
        # Retained-run accounting already includes reconstructed arrays. Reserve
        # half the currently available RAM for the UI and other active programs.
        data["memory_limit_bytes"] = max(1, caps.available_memory_bytes // 2)
    width = intent.spectral_max_cm1 - intent.spectral_min_cm1
    frequency = float(data["probe_frequency_hz"])
    speed = float(data["scan_speed_cm1_s"])
    if not math.isfinite(frequency) or frequency <= 0 or not math.isfinite(speed) or speed <= 0:
        raise ValueError("probe frequency and scan speed must be positive finite values")
    if "measured_scan_period_s" in manual:
        period = float(manual["measured_scan_period_s"])
    else:
        same_window = (caps.live_settings.get("scan_start_cm1", base.scan_start_cm1) == intent.spectral_min_cm1
                       and caps.live_settings.get("scan_stop_cm1", base.scan_stop_cm1) == intent.spectral_max_cm1)
        measured = caps.actual_scan_period_s or live.get("measured_scan_period_s")
        if measured is not None and same_window and "scan_speed_cm1_s" not in manual:
            proposed = float(measured)
        else:
            transition = 0.0 if caps.scan_transition_s is None else float(caps.scan_transition_s)
            if not math.isfinite(transition) or transition < 0:
                raise ValueError("scan transition duration must be nonnegative and finite")
            proposed = width / speed + transition
        # A process pulse must finish before the next frame. This is an explicit
        # automatic cadence choice, not an unnoticed mutation of a scan-speed override.
        minimum = max(float(data["process_delay_s"]) + float(data["process_pulse_width_s"]),
                      float(data["fire_pulse_width_s"]), float(data["qswitch_pulse_width_s"])) + 2e-6
        proposed = max(proposed, minimum)
        cycles = int((Decimal(str(proposed)) * Decimal(str(frequency))).to_integral_value(rounding=ROUND_CEILING))
        period = cycles / frequency
    if not math.isfinite(period) or period <= 0:
        raise ValueError("scan period must be positive and finite")
    quantum = Decimal("0.00000000001")
    phases = tuple(float((Decimal(str(period)) * index / intent.phase_count / quantum).to_integral_value(rounding=ROUND_HALF_UP) * quantum)
                   for index in range(intent.phase_count))
    if len(set(phases)) != len(phases) or phases[-1] >= period:
        raise ValueError("phase count exceeds the timing grid available within this scan period")
    post = max(1, int((Decimal(str(intent.observation_duration_s)) / Decimal(str(period))).to_integral_value(rounding=ROUND_CEILING)))
    data.update(measured_scan_period_s=period, phase_offsets_s=phases, post_scans=post)
    for field_name in ("sample_rate_hz", "reference_rate_hz"):
        if field_name == "reference_rate_hz" and mode != "dual":
            continue
        rates = tuple(float(rate) for rate in caps.supported_sample_rates_hz)
        if rates:
            if any(not math.isfinite(rate) or rate <= 0 for rate in rates):
                raise ValueError("connected sample-rate choices must be finite and positive")
            target = float(data[field_name])
            data[field_name] = min(rates, key=lambda rate: (abs(rate-target), rate))
    for field_name, fractions in (("band_windows_cm1", ((.2, .8),)),
                                  ("offband_windows_cm1", ((0., .1), (.9, 1.)))):
        if field_name not in manual:
            clipped = [(max(float(lo), intent.spectral_min_cm1), min(float(hi), intent.spectral_max_cm1))
                       for lo, hi in data[field_name] if min(float(hi), intent.spectral_max_cm1) > max(float(lo), intent.spectral_min_cm1)]
            data[field_name] = clipped or [(intent.spectral_min_cm1 + width*lo, intent.spectral_min_cm1 + width*hi) for lo, hi in fractions]
    # Keep every optional annotation, including temperature, verbatim.
    data["condition"]["sample_id"] = intent.sample_name.strip()
    data["acquisition_intent"] = intent.to_dict()
    data["manual_overrides"] = manual
    basis = "connected readbacks" if live or caps.actual_scan_period_s is not None else "initial requests; readbacks unavailable"
    data["value_source"] = f"Automatic intent resolution from {basis}; independent overrides retained. Band/off-band windows are editable analysis inputs, not identified measurements."
    return RepeatedRapidScanSettings.from_dict(data)


def build_plan_from_intent(intent: AcquisitionIntent | Mapping[str, Any], *, mode: str = "single",
                           base_settings=None, capabilities=None, overrides=None) -> RepeatedRapidScanPlan:
    settings = resolve_intent_settings(intent, mode=mode, base_settings=base_settings,
                                       capabilities=capabilities, overrides=overrides)
    return build_plan(settings, capabilities=capabilities)


def build_plan(settings: RepeatedRapidScanSettings | Mapping[str, Any], capabilities=None,
               calibration=None) -> RepeatedRapidScanPlan:
    if isinstance(settings, Mapping):
        settings = RepeatedRapidScanSettings.from_dict(settings)
    settings.validate()
    caps = _typed(capabilities, HardwareCapabilities)
    evidence = _typed(calibration, CalibrationEvidence)
    movies: list[MoviePlan] = []
    number = 0
    for repeat in range(settings.repeats):
        # Counterbalance direction and phase ordering between technical repeats.
        directions = settings.directions if repeat % 2 == 0 else tuple(reversed(settings.directions))
        phases = tuple(enumerate(settings.phase_offsets_s))
        if repeat % 2:
            phases = tuple(reversed(phases))
        for direction in directions:
            for phase_index, phase in phases:
                for control in ("sample", *settings.controls):
                    number += 1
                    compiled = compile_movie(settings, phase, pump_enabled=control in ("sample", "pump_blocked"), direction=direction)
                    action = {"sample": "Sample recovery movie with one pump and retained pre-pump scans",
                              "pump_blocked": "Manually block the pump; confirm physical state (no installed shutter); one observed electrical event, zero sample optical events",
                              "dark": "Manually establish detector-dark condition; retain restoration record",
                              "probe_only": "Pump commands inhibited; retain probe-only full movie"}[control]
                    movies.append(MoviePlan(f"movie-{number:04d}", phase_index, phase, compiled.selected_phase_s,
                                            direction, control, repeat, int(control in ("sample", "pump_blocked")), compiled,
                                            0, action))
    first = movies[0].compiled
    if first.physical_frame_count > caps.frame_capacity:
        raise ValueError(f"uninterrupted movie exceeds connected frame capacity {caps.frame_capacity}; no splitting is performed")
    active_demods = (settings.sample_demodulator,) + ((settings.reference_demodulator,) if settings.mode == "dual" else ())
    if not set(active_demods) <= set(caps.available_demodulators):
        raise ValueError("selected detector demodulators are unavailable on the installed recorder")
    rate = settings.sample_rate_hz + (settings.reference_rate_hz if settings.mode == "dual" else 0)
    aggregate = rate + (caps.acquisition_timing_rate_hz or 0.0)
    if caps.max_aggregate_rate_hz is not None and aggregate > caps.max_aggregate_rate_hz:
        raise ValueError("full detector and timing aggregate rate exceeds connected HF2LI throughput; scans will not be silently slowed")
    if caps.supported_sample_rates_hz:
        for selected_rate in (settings.sample_rate_hz,) + ((settings.reference_rate_hz,) if settings.mode == "dual" else ()):
            if not any(math.isclose(selected_rate, available, rel_tol=1e-10) for available in caps.supported_sample_rates_hz):
                raise ValueError("sample rate is not supported; select an explicit connected rate")
    # Native timestamp + x/y + DIO + flags + uncertainty/alignment metadata.
    native_bytes_per_sample = 64
    movie_native = math.ceil(first.duration_s * aggregate) * native_bytes_per_sample
    # Retain native payload, reconstructed columns, validity and response arrays.
    movie_memory = movie_native * 3 + len(first.frames) * 2048
    if movie_memory > min(settings.memory_limit_bytes, caps.max_movie_bytes or settings.memory_limit_bytes):
        raise ValueError("full uninterrupted movie exceeds memory budget; no circular reuse, split or scan slowing is permitted")
    if type(caps.selected_baseline_bytes) is not int or caps.selected_baseline_bytes < 0:
        raise ValueError("selected baseline bytes must be a measured nonnegative byte count")
    # Start does not acquire a separate blank or qualification train. Conservatively
    # include one unpumped sample movie per direction even when S0 may be reusable.
    # Retained loaded records are counted only when their measured footprint is supplied.
    active_movies = tuple(movie for movie in movies if settings.execution == "simulation" or movie.control in ("sample", "probe_only"))
    qualification_s = 0.0
    measurement_s = sum(movie.duration_s for movie in active_movies)
    blank_s = 0.0
    preliminary_s = first.duration_s * len(settings.directions)
    total_capture_count = len(active_movies) + len(settings.directions)
    acquisition_s = measurement_s + preliminary_s
    native_total = math.ceil(acquisition_s * aggregate) * native_bytes_per_sample
    storage_bytes = native_total * 3 + total_capture_count * 32768 + caps.selected_baseline_bytes
    if storage_bytes > settings.storage_limit_bytes:
        raise ValueError("retained native, reconstructed and control records exceed storage budget")
    retained_run_memory = native_total * 6 + total_capture_count * len(first.frames) * 4096 + caps.selected_baseline_bytes
    if retained_run_memory > settings.memory_limit_bytes:
        raise ValueError("complete retained run exceeds memory budget, including sample baseline, selected loaded records, native chunks and results; reduce the explicit movie/repeat plan or raise a justified budget")
    def unpumped_commands(movie, count=None):
        frames = []
        for frame in movie.compiled.frames[:count]:
            channels = {channel: {**values, "enabled": values["enabled"] and channel not in "AB"}
                        for channel, values in frame["channels"].items()}
            frames.append({**frame, "channels": channels})
        if count is not None:
            frames.append(movie.compiled.frames[-1])
        return replace(movie.compiled, frames=tuple(frames)).command_count
    upload_commands = sum(movie.compiled.command_count for movie in active_movies)
    upload_commands += len(settings.directions) * unpumped_commands(movies[0])
    upload_s = upload_commands * settings.upload_acknowledgment_s
    # Recovery assessment uses the recorded movie interval. There is no extra
    # timer-based reset wait or implicit extension after the finite movie.
    reset_s = 0.0
    wall = (settings.preparation_s + acquisition_s + upload_s + total_capture_count * settings.tuning_settling_s
            + reset_s + settings.restoration_s + settings.analysis_s + storage_bytes / settings.storage_bytes_per_second)
    # Acquire blank is an explicit separate action. Expose its costs without
    # charging ordinary Start for data it will not acquire.
    blank_action_s = sum(movie.duration_s for movie in movies) if settings.mode == "single" else 0.0
    blank_action_native = math.ceil(blank_action_s * aggregate) * native_bytes_per_sample
    blank_action_count = len(movies) if settings.mode == "single" else 0
    blank_action_upload = sum(unpumped_commands(movie) for movie in movies) * settings.upload_acknowledgment_s if blank_action_count else 0.0
    blank_action_storage = blank_action_native * 3 + blank_action_count * 32768
    blank_action_memory = blank_action_native * 6 + blank_action_count * len(first.frames) * 4096
    blank_action_wall = ((settings.preparation_s + blank_action_s + blank_action_upload
                         + blank_action_count * settings.tuning_settling_s + settings.restoration_s
                         + settings.analysis_s + blank_action_storage / settings.storage_bytes_per_second)
                        if blank_action_count else 0.0)
    readiness = _readiness(settings, caps, evidence)
    requested = {"qcl": MIRCAT_QCL, "scan_period_s": settings.measured_scan_period_s, "phase_offsets_s": list(settings.phase_offsets_s),
                 "sample_rate_hz": settings.sample_rate_hz, "reference_rate_hz": settings.reference_rate_hz,
                 "scan_speed_cm1_s": settings.scan_speed_cm1_s,
                 "mircat_pulse_rate_hz": settings.mircat_pulse_rate_hz,
                 "mircat_pulse_width_ns": settings.mircat_pulse_width_ns,
                 "mircat_current_ma": settings.mircat_current_ma,
                 "probe_frequency_hz": settings.probe_frequency_hz,
                 "probe_pulse_width_s": settings.probe_pulse_width_s}
    requested.update(settings.manual_overrides)
    if settings.acquisition_intent:
        requested["acquisition_intent"] = dict(settings.acquisition_intent)
    selected = {**requested, "qcl": MIRCAT_QCL, "scan_period_s": first.scan_period_s,
                "sample_rate_hz": settings.sample_rate_hz, "reference_rate_hz": settings.reference_rate_hz,
                "phase_offsets_s": [compile_movie(settings, phase).selected_phase_s for phase in settings.phase_offsets_s],
                "predivider": first.predivider, "probe_frequency_hz": first.input_frequency_hz,
                "mircat_pulse_rate_hz": settings.mircat_pulse_rate_hz,
                "mircat_pulse_width_ns": settings.mircat_pulse_width_ns,
                "mircat_current_ma": settings.mircat_current_ma,
                "mircat_duty_fraction": validate_mircat_pulse_pair(settings.mircat_pulse_rate_hz,
                                                                  settings.mircat_pulse_width_ns),
                "probe_optical_duty_fraction": validate_probe_optical_pulse_pair(first.input_frequency_hz,
                                                                                  settings.mircat_pulse_width_ns),
                "probe_repetition_rate_basis": "T660 external trigger cadence in MIRcat external-pulse mode 2",
                "optical_pulse_width_basis": "MIRcat SDK optical width in ns; external TTL width is separate"}
    actual = {"sample_rate_hz": caps.actual_sample_rate_hz, "reference_rate_hz": caps.actual_reference_rate_hz,
              "scan_period_s": caps.actual_scan_period_s, "readback_id": caps.connected_readback_id,
              "timing_rate_hz": caps.acquisition_timing_rate_hz, "live_settings": dict(caps.live_settings),
              "available_memory_bytes": caps.available_memory_bytes,
              "selected_baseline_bytes": caps.selected_baseline_bytes,
              "pump_timestamps": "available only in acquired native records"}
    estimates = {"movie_count": len(movies), "pump_count": sum(movie.pump_count for movie in movies),
                 "scans_per_movie": first.expected_scan_count, "movie_duration_s": first.duration_s,
                 "physical_frames_per_movie": first.physical_frame_count,
                 "terminal_inhibit_duration_s": first.scan_period_s,
                 "spectral_record_duration_s": first.frames[-1]["programmed_frame_start_s"],
                 "movie_native_bytes": movie_native, "movie_memory_bytes": movie_memory,
                 "retained_run_memory_bytes": retained_run_memory,
                 "storage_bytes": storage_bytes, "aggregate_rate_hz": aggregate,
                 "timing_stream_estimate_known": caps.acquisition_timing_rate_hz is not None,
                 "upload_commands": upload_commands, "upload_s": upload_s,
                 "total_capture_count": total_capture_count,
                 "acquisition_movie_count": len(active_movies),
                 "omitted_control_count": len(movies) - len(active_movies),
                 "selected_baseline_bytes": caps.selected_baseline_bytes,
                 "blank_action_acquisition_s": blank_action_s,
                 "blank_action_upload_s": blank_action_upload,
                 "blank_action_memory_bytes": blank_action_memory,
                 "blank_action_storage_bytes": blank_action_storage,
                 "blank_action_wall_time_s": blank_action_wall,
                 "qualification_s": qualification_s, "preliminary_s": preliminary_s, "blank_s": blank_s,
                 "acquisition_s": acquisition_s, "reset_allowance_s": reset_s, "wall_time_s": wall,
                 "estimate_basis": "Start: finite sample/probe-only movies, conservative automatic sample baseline per direction, acknowledged upload, preparation/settling, restoration, saving and analysis. Recovery is observed within each movie; no additional reset timer or qualification. Optional Acquire blank is estimated separately; supplied measured loaded-record bytes are retained.",
                 "planning_scan_duration_s": (settings.scan_stop_cm1 - settings.scan_start_cm1) / settings.scan_speed_cm1_s,
                 "planning_filter_smear_cm1": settings.scan_speed_cm1_s * settings.sample_filter_timeconstant_s,
                 "planning_only": "width/speed, phase+n*period and filter-smear relationships never replace native timestamps/trajectories"}
    return RepeatedRapidScanPlan(settings, tuple(movies), caps, evidence, tuple(readiness), requested, selected, actual, estimates)


def _readiness(settings, caps, evidence):
    """Observability notes only; absent metadata never inhibits acquisition."""
    items = []
    if not caps.connected_readback_id:
        items.append(ReadinessItem("connected_readbacks", "Actual instrument values will be recorded when connected.", False))
    if caps.acquisition_timing_rate_hz is None:
        items.append(ReadinessItem("timing_throughput", "Timing-stream rate is unknown; current memory estimate excludes that unknown rate.", False))
    if not evidence.trajectory_id:
        items.append(ReadinessItem("trajectory", "Calibrated wavelength trajectory unavailable; retain native detector/timing data and label any nominal axis.", False))
    if not evidence.optical_time_zero_id:
        items.append(ReadinessItem("optical_time_zero", "Optical time zero is unknown; use observed electrical-sync-relative times.", False))
    if not evidence.response_id:
        items.append(ReadinessItem("response", "Measured response kernel unavailable; raw/relative acquisition remains available and kinetic fits must state their response basis.", False))
    return items


def resolve_operating_settings(settings, *, promoted_bundle: Mapping[str, Any], installed_readbacks: Mapping[str, Any]):
    """Load optional operating values without making evidence an execution gate."""
    evidence = _typed(promoted_bundle, CalibrationEvidence)
    prohibited = {"experiment_id", "schema_version", "mode", "execution", "condition"}
    if set(evidence.operating_values) & prohibited:
        raise ValueError("instrument operating values cannot replace experiment/mode/condition identity")
    selected = replace(settings, **evidence.operating_values, calibration_ids=evidence.calibration_ids,
                       value_source=evidence.source)
    plan = build_plan(selected, capabilities=installed_readbacks, calibration=evidence)
    requested = {name: getattr(settings, name) for name in plan.requested if hasattr(settings, name)}
    requested["qcl"] = MIRCAT_QCL
    requested["scan_period_s"] = settings.measured_scan_period_s
    requested["phase_offsets_s"] = list(settings.phase_offsets_s)
    requested["value_source"] = settings.value_source
    return replace(plan, requested=requested)


def resolve_calibration_from_bundle(manifest: Mapping[str, Any]) -> CalibrationEvidence:
    """Read the experiment section of a bundle accepted by the host loader.

    ``MeasurementContext.promoted_bundle`` checks the canonical registry first.
    This conversion does not perform promotion and accepts neither raw campaign
    evidence nor a sample spectral-selection record as instrument calibration.
    """
    if manifest.get("status") != "PROMOTED" or not manifest.get("bundle_id"):
        raise ValueError("host-loaded manifest must identify an explicitly PROMOTED bundle")
    section = manifest.get(EXPERIMENT_ID)
    if not isinstance(section, Mapping) or not isinstance(section.get("calibration"), Mapping):
        raise ValueError("promoted bundle lacks repeated_rapid_scan.calibration applicability data")
    values = dict(section["calibration"])
    values["source"] = f"instrument/promoted_bundles/{manifest['bundle_id']}"
    values["promoted"] = True
    return _typed(values, CalibrationEvidence)


def save_plan(plan: RepeatedRapidScanPlan, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(plan.to_dict(), indent=2, allow_nan=False), encoding="utf-8")
    return target


def load_plan(path: str | Path, *, mode: str | None = None, condition_id: str | None = None) -> RepeatedRapidScanPlan:
    result = RepeatedRapidScanPlan.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
    if mode is not None and result.mode != mode:
        raise ValueError(f"Plan detector mode {result.mode!r} is incompatible with {mode!r}")
    # condition_id is retained as a compatible legacy argument; scientific
    # condition labels/temperature annotations do not alter operational planning.
    return result
