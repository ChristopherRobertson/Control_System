"""Typed, hardware-free planning with separate structural and readiness checks."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .settings import EXPERIMENT_ID, RepeatedRapidScanSettings
from .timing import CompiledMovie, T660_FRAME_CAPACITY, compile_movie


@dataclass(frozen=True)
class HardwareCapabilities:
    frame_capacity: int = T660_FRAME_CAPACITY
    max_aggregate_rate_hz: float | None = None
    max_movie_bytes: int | None = None
    available_demodulators: tuple[int, ...] = (0, 1, 2, 3, 4, 5)
    connected_readback_id: str = ""
    detector_roles_verified: bool = False
    receiver_topology_verified: bool = False
    continuous_recording_verified: bool = False
    actual_sample_rate_hz: float | None = None
    actual_reference_rate_hz: float | None = None
    acquisition_timing_rate_hz: float = 0.0
    actual_scan_period_s: float | None = None
    supported_sample_rates_hz: tuple[float, ...] = ()
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
    blocks_hardware: bool = True


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
                    action = {"sample": "Verify sample and pump path; accept pre-pump stationarity before arming",
                              "pump_blocked": "Manually block the pump; confirm physical state (no installed shutter); one observed electrical event, zero sample optical events",
                              "dark": "Manually establish detector-dark condition; retain restoration record",
                              "probe_only": "Pump commands inhibited; retain probe-only full movie"}[control]
                    movies.append(MoviePlan(f"movie-{number:04d}", phase_index, phase, compiled.selected_phase_s,
                                            direction, control, repeat, int(control in ("sample", "pump_blocked")), compiled,
                                            settings.pre_scans if control == "sample" else 0, action))
    first = movies[0].compiled
    if first.physical_frame_count > caps.frame_capacity:
        raise ValueError(f"uninterrupted movie exceeds connected frame capacity {caps.frame_capacity}; no splitting is performed")
    active_demods = (settings.sample_demodulator,) + ((settings.reference_demodulator,) if settings.mode == "dual" else ())
    if not set(active_demods) <= set(caps.available_demodulators):
        raise ValueError("selected detector demodulators are unavailable on the installed recorder")
    rate = settings.sample_rate_hz + (settings.reference_rate_hz if settings.mode == "dual" else 0)
    aggregate = rate + caps.acquisition_timing_rate_hz
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
    qualification_s = sum(movie.qualification_scans + 1 for movie in movies if movie.qualification_scans) * first.scan_period_s
    # The single sequential blank repeats the full phase/control schedule. The
    # sample preliminary supplies one unpumped movie per direction in both modes.
    # The runner retains those records alongside native chunks/results until the
    # run is preserved, so capacity must cover the entire in-memory run as well.
    measurement_s = sum(movie.duration_s for movie in movies)
    blank_s = measurement_s if settings.mode == "single" else 0.0
    preliminary_s = first.duration_s * len(settings.directions)
    acquisition_s = measurement_s + qualification_s + preliminary_s + blank_s
    native_total = math.ceil(acquisition_s * aggregate) * native_bytes_per_sample
    storage_bytes = native_total * 3 + len(movies) * 32768
    if storage_bytes > settings.storage_limit_bytes:
        raise ValueError("retained native, reconstructed and control records exceed storage budget")
    retained_run_memory = native_total * 6 + len(movies) * len(first.frames) * 4096
    if retained_run_memory > settings.memory_limit_bytes:
        raise ValueError("complete retained run exceeds memory budget, including blank/preliminary, native chunks and results; reduce the explicit movie/repeat plan or raise a justified budget")
    def unpumped_commands(movie, count=None):
        frames = []
        for frame in movie.compiled.frames[:count]:
            channels = {channel: {**values, "enabled": values["enabled"] and channel not in "AB"}
                        for channel, values in frame["channels"].items()}
            frames.append({**frame, "channels": channels})
        if count is not None:
            frames.append(movie.compiled.frames[-1])
        return replace(movie.compiled, frames=tuple(frames)).command_count
    upload_commands = sum(movie.compiled.command_count for movie in movies)
    if settings.mode == "single":
        upload_commands += sum(unpumped_commands(movie) for movie in movies)
    upload_commands += len(settings.directions) * unpumped_commands(movies[0])
    upload_commands += sum(unpumped_commands(movie, movie.qualification_scans) for movie in movies if movie.qualification_scans)
    upload_s = upload_commands * settings.upload_acknowledgment_s
    reset_s = sum(movie.control == "sample" for movie in movies) * settings.recovery.max_reset_wait_s
    total_capture_count = len(movies) * (2 if settings.mode == "single" else 1) + len(settings.directions) + sum(bool(movie.qualification_scans) for movie in movies)
    wall = (settings.preparation_s + acquisition_s + upload_s + total_capture_count * settings.tuning_settling_s
            + reset_s + settings.restoration_s + settings.analysis_s + storage_bytes / settings.storage_bytes_per_second)
    readiness = _readiness(settings, caps, evidence)
    requested = {"scan_period_s": settings.measured_scan_period_s, "phase_offsets_s": list(settings.phase_offsets_s),
                 "sample_rate_hz": settings.sample_rate_hz, "reference_rate_hz": settings.reference_rate_hz,
                 "scan_speed_cm1_s": settings.scan_speed_cm1_s}
    selected = {**requested, "scan_period_s": first.scan_period_s,
                "phase_offsets_s": [compile_movie(settings, phase).selected_phase_s for phase in settings.phase_offsets_s],
                "predivider": first.predivider, "probe_frequency_hz": first.input_frequency_hz}
    actual = {"sample_rate_hz": caps.actual_sample_rate_hz, "reference_rate_hz": caps.actual_reference_rate_hz,
              "scan_period_s": caps.actual_scan_period_s, "readback_id": caps.connected_readback_id,
              "pump_timestamps": "available only in acquired native records"}
    estimates = {"movie_count": len(movies), "pump_count": sum(movie.pump_count for movie in movies),
                 "scans_per_movie": first.expected_scan_count, "movie_duration_s": first.duration_s,
                 "physical_frames_per_movie": first.physical_frame_count,
                 "terminal_inhibit_duration_s": first.scan_period_s,
                 "spectral_record_duration_s": first.frames[-1]["programmed_frame_start_s"],
                 "movie_native_bytes": movie_native, "movie_memory_bytes": movie_memory,
                 "retained_run_memory_bytes": retained_run_memory,
                 "storage_bytes": storage_bytes, "aggregate_rate_hz": aggregate,
                 "upload_commands": upload_commands, "upload_s": upload_s,
                 "total_capture_count": total_capture_count,
                 "qualification_s": qualification_s, "preliminary_s": preliminary_s, "blank_s": blank_s,
                 "acquisition_s": acquisition_s, "reset_allowance_s": reset_s, "wall_time_s": wall,
                 "estimate_basis": "Full finite movies, separate pre-pump qualification, preliminary/blank, acknowledged pending-field upload, settling, maximum reset allowance, restoration, saving and analysis; actual recovery may stop the sequence.",
                 "planning_scan_duration_s": (settings.scan_stop_cm1 - settings.scan_start_cm1) / settings.scan_speed_cm1_s,
                 "planning_filter_smear_cm1": settings.scan_speed_cm1_s * settings.sample_filter_timeconstant_s,
                 "planning_only": "width/speed, phase+n*period and filter-smear relationships never replace native timestamps/trajectories"}
    return RepeatedRapidScanPlan(settings, tuple(movies), caps, evidence, tuple(readiness), requested, selected, actual, estimates)


def _readiness(settings, caps, evidence):
    items = []
    def need(condition, code, message, blocking=True):
        if not condition:
            items.append(ReadinessItem(code, message, blocking))
    need(bool(caps.connected_readback_id), "connected_readbacks", "Connected capability/readback identity is unresolved.")
    need(caps.detector_roles_verified, "detector_roles", "Verify sample Signal 1 / reference Signal 2 demodulator roles and actual rates.")
    need(caps.receiver_topology_verified, "receiver_topology", "Qualify the installed HF2LI/PicoScope tee loads and receiver transfer.")
    need(caps.continuous_recording_verified, "continuous_recording", "Qualify finite uninterrupted full-memory HF2LI recording and aggregate throughput.")
    need(caps.max_aggregate_rate_hz is not None, "aggregate_throughput", "Connected aggregate detector and timing throughput is unresolved.")
    need(evidence.promoted and evidence.source.startswith("instrument/promoted_bundles/"), "promoted_calibration", "Load applicable explicitly promoted instrument evidence; the built-in example does not authorize hardware.")
    for key, label in (("trajectory_id", "scan trajectory/marker mapping"), ("electrical_timing_id", "electrical clock/latency mapping"),
                       ("response_id", "native scan/filter response"), ("detector_id", "detector linearity and range"),
                       ("topology_id", "installed receiver topology"), ("reset_equivalence_id", "condition-specific equivalent-state reset")):
        need(bool(getattr(evidence, key)), key, f"Applicable {label} record is unresolved.")
    need(bool(settings.condition.sample_selection_id), "sample_selection", "Load an accepted versioned sample spectral selection covering bands and off-band baseline.")
    need(bool(settings.condition.state_verification_ids), "sample_state", "Record accepted sample preparation and pre-run state verification.")
    need(all(getattr(settings.condition, key) != "unassigned" for key in ("sample_id", "preparation_id", "cell_id", "position_id")),
         "sample_identity", "Assign sample, independent preparation, cell and illuminated-position identities.")
    need(evidence.condition_id == settings.condition_id, "condition_applicability", "Reset/calibration applicability does not identify this condition.")
    need(bool(evidence.applicable_settings), "operating_applicability", "Promoted evidence must specify applicable scan, probe, pump and detector settings.")
    required = ("scan_start_cm1", "scan_stop_cm1", "measured_scan_period_s", "scan_speed_cm1_s",
                "probe_frequency_hz", "probe_pulse_width_s", "process_delay_s", "process_pulse_width_s",
                "fire_to_qswitch_s", "fire_pulse_width_s", "qswitch_pulse_width_s", "sample_demodulator",
                "sample_input_range_v", "sample_filter_order", "sample_filter_timeconstant_s", "sample_rate_hz")
    if settings.mode == "dual":
        required += ("reference_demodulator", "reference_input_range_v", "reference_filter_order",
                     "reference_filter_timeconstant_s", "reference_rate_hz")
    for key in required:
        need(key in evidence.applicable_settings and evidence.applicable_settings[key] == getattr(settings, key),
             f"applicability_{key}", f"Selected {key} is not supported by the loaded applicability record.")
    need(bool(evidence.optical_time_zero_id), "optical_time_zero", "Optical time zero/IRF is unresolved: report electrical-sync-relative times and bounded claims.", False)
    need(bool(settings.condition.temperature_record_id), "temperature_evidence", "Temperature is a requested condition; no measured temperature record supports a quantitative temperature claim.", False)
    need(bool(settings.condition.concentration_metadata), "concentration_mass_balance", "Concentration/free-CO/mass-balance evidence is absent; report apparent recovery without assigning solvent mechanism.", False)
    return items


def resolve_operating_settings(settings, *, promoted_bundle: Mapping[str, Any], installed_readbacks: Mapping[str, Any]):
    """Apply explicit promoted values, then retain connected actuals separately.

    An ordinary sample-selection record cannot masquerade as an instrument bundle.
    Caller supplies the bundle loaded from the canonical promoted registry.
    """
    evidence = _typed(promoted_bundle, CalibrationEvidence)
    if not evidence.promoted or not evidence.source.startswith("instrument/promoted_bundles/"):
        raise ValueError("operating values require an explicitly promoted instrument bundle")
    if evidence.condition_id != settings.condition_id:
        raise ValueError("promoted operating profile is incompatible with the selected condition")
    prohibited = {"experiment_id", "schema_version", "mode", "execution", "condition"}
    if set(evidence.operating_values) & prohibited:
        raise ValueError("instrument operating values cannot replace experiment/mode/condition identity")
    selected = replace(settings, **evidence.operating_values, calibration_ids=evidence.calibration_ids,
                       value_source=evidence.source)
    plan = build_plan(selected, capabilities=installed_readbacks, calibration=evidence)
    requested = {name: getattr(settings, name) for name in plan.requested if hasattr(settings, name)}
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
    if condition_id is not None and result.condition_id != condition_id:
        raise ValueError("Plan condition is incompatible with the selected sample condition")
    return result
