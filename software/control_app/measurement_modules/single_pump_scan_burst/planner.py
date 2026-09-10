"""Finite one-pump early/logarithmic observation planning and provenance."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import ceil, isfinite, log10
from typing import Any, Mapping

from .settings import Capabilities, CONDITION_PROFILES, EXPERIMENT_ID, Settings
from .timing import BurstBlock, compile_block, probe_clock_recipe, quantize

PLAN_VERSION = 1
ANALYSIS_VERSION = "single-pump-bursts-1"
# Conservative Python/JSON retention allowance: four channel dictionaries,
# unit-bearing strings and frame fields, plus each block/idle-step record. Three
# copies cover the scientific plan, detached host snapshot and serialization or
# complete unpumped control table. This is a resource estimate, not a count cap.
PLAN_FRAME_METADATA_BYTES = 4096
PLAN_BLOCK_METADATA_BYTES = 2048
PLAN_METADATA_COPIES = 3


@dataclass(frozen=True)
class Plan:
    settings: Settings
    capabilities: Capabilities
    blocks: tuple[BurstBlock, ...] = ()
    errors: tuple[str, ...] = ()
    readiness: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    selected_values: dict[str, Any] = field(default_factory=dict)
    estimates: dict[str, Any] = field(default_factory=dict)
    steps: tuple[dict[str, Any], ...] = ()
    probe_clock_recipe: dict[str, Any] = field(default_factory=dict)
    schema_version: int = PLAN_VERSION
    experiment_id: str = EXPERIMENT_ID

    @property
    def valid(self) -> bool:
        return not self.errors and bool(self.blocks)

    @property
    def ready(self) -> bool:
        return self.valid and not self.readiness and not self.settings.example_only

    @property
    def total_scans(self) -> int:
        return sum(block.scan_count for block in self.blocks)

    @property
    def pump_count(self) -> int:
        return sum(bool(frame["channels"]["A"]["enabled"] and frame["channels"]["B"]["enabled"])
                   for block in self.blocks for frame in block.frames)

    @property
    def summary(self) -> str:
        if self.errors:
            return "Plan incomplete: " + "; ".join(self.errors)
        e = self.estimates
        return (f"{self.settings.architecture_id}: exactly {self.pump_count} pump command, "
                f"{self.total_scans} scans in {len(self.blocks)} explicit blocks; "
                f"{self.settings.observation_limit_s:g} s observation limit; "
                f"{e.get('native_bytes', 0) / 1e6:.1f} MB native estimate; "
                f"{e.get('wall_time_min_s', 0):g} s minimum wall time. "
                f"{len(self.readiness)} commissioning/readiness items remain.")

    def require_valid(self) -> None:
        if not self.valid:
            raise ValueError("; ".join(self.errors) or "Plan has no finite blocks")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["summary"] = self.summary
        result["instance_id"] = self.settings.instance_id
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Plan":
        if data.get("experiment_id") != EXPERIMENT_ID or data.get("schema_version") != PLAN_VERSION:
            raise ValueError("Incompatible single-pump plan experiment/schema")
        settings = Settings.from_dict(data["settings"])
        if data.get("instance_id", settings.instance_id) != settings.instance_id:
            raise ValueError("Plan detector-mode identity mismatch")
        # Recompile instead of trusting serialized executable timing. Explicit
        # settings and capability records are the portable scientific plan.
        return compile_plan(settings, Capabilities.from_dict(data.get("capabilities", {})))


def logarithmic_times(start_s: float, stop_s: float, count: int) -> tuple[float, ...]:
    if count == 0:
        return ()
    if count < 0 or not 0 < start_s <= stop_s:
        raise ValueError("Logarithmic schedule requires positive increasing time bounds")
    if count == 1:
        return (float(start_s),)
    if start_s == stop_s:
        raise ValueError("Multiple bursts require distinct logarithmic bounds")
    step = (log10(stop_s) - log10(start_s)) / (count - 1)
    return tuple(start_s if i == 0 else stop_s if i == count - 1 else
                 10 ** (log10(start_s) + i * step) for i in range(count))


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def compile_plan(settings: Settings | Mapping[str, Any], capabilities: Capabilities | Mapping[str, Any] | None = None) -> Plan:
    if not isinstance(settings, Settings):
        settings = Settings.from_dict(settings)
    if capabilities is None:
        capabilities = Capabilities()
    elif not isinstance(capabilities, Capabilities):
        capabilities = Capabilities.from_dict(capabilities)
    s, cap = settings, capabilities
    errors: list[str] = []
    readiness: list[str] = []
    warnings: list[str] = [
        "Programmed commands, observed electrical triggers and independently observed optical arrival remain separate.",
        "Cross-block times are requests; actual native timestamps determine elapsed time and missing gaps.",
        "Slow 77 K recovery alone does not establish escape, non-geminate recovery or solvent return.",
    ]
    selected_values: dict[str, Any] = {}

    for name in ("edge_quantum_s", "edge_max_s", "synthesizer_quantum_hz", "synthesizer_max_hz",
                 "train_spacing_min_s", "train_spacing_max_s", "train_spacing_quantum_s",
                 "frame_guard_s", "probe_duty_max", "hf2_aggregate_rate_max_hz"):
        value = getattr(cap, name)
        if not _finite_number(value) or value <= 0:
            errors.append(f"Capability {name} must be finite and positive")
    for name in ("frame_capacity", "predivider_max", "train_count_max"):
        if type(getattr(cap, name)) is not int or getattr(cap, name) <= 0:
            errors.append(f"Capability {name} must be a positive integer")
    if s.blank_source not in {"acquire", "loaded"}:
        errors.append("blank_source must be acquire or loaded")
    if s.probe_during_wait:
        errors.append("Installed single-pump adapter supports dark inter-burst waits only; continuous inter-burst probe requires a qualified stationary hold adapter")

    if s.mode not in {"single", "dual"}:
        errors.append("mode must be single or dual")
    if s.condition_id not in CONDITION_PROFILES:
        errors.append("Select the distinct 77K-HRP-G-S or 77K-Mb-G-S condition profile")
    required_positive = ["scan_start_cm1", "scan_stop_cm1", "scan_speed_cm1_s", "scan_interval_s",
        "observation_limit_s", "sample_rate_hz", "timing_rate_hz", "hf2_filter_tc_s",
        "sample_input_range_v", "probe_rate_hz", "probe_pulse_width_s", "probe_current_ma",
        "pump_fire_to_q_s", "pump_fire_width_s", "pump_q_width_s", "process_width_s"]
    if s.mode == "dual":
        required_positive += ["reference_rate_hz", "reference_filter_tc_s", "reference_input_range_v"]
    if s.later_burst_count and not s.later_burst_times_s:
        required_positive += ["first_later_burst_s"]
    for name in required_positive:
        value = getattr(s, name)
        if not _finite_number(value) or value <= 0:
            errors.append(f"{name} requires an explicit finite positive value")
    if not _finite_number(s.first_scan_delay_s) or s.first_scan_delay_s < 0:
        errors.append("first_scan_delay_s requires an explicit finite nonnegative value")
    if not _finite_number(s.probe_reference_delay_s) or s.probe_reference_delay_s < 0:
        errors.append("Probe relative delay must be finite and nonnegative")
    for name in ("early_scan_count", "scans_per_burst", "final_scan_count", "preliminary_scan_count"):
        value = getattr(s, name)
        if type(value) is not int or value < 1:
            errors.append(f"{name} must be a positive integer")
        elif type(cap.frame_capacity) is int and value + 1 > cap.frame_capacity:
            errors.append(f"{name}: scans plus terminal exceed physical frame capacity; continuous blocks cannot be silently split")
    if type(s.later_burst_count) is not int or s.later_burst_count < 0:
        errors.append("later_burst_count must be a nonnegative integer")
    for name in ("hf2_filter_order",) + (("reference_filter_order",) if s.mode == "dual" else ()):
        if type(getattr(s, name)) is not int or not 1 <= getattr(s, name) <= 8:
            errors.append(f"{name} must be an explicitly selected supported order 1–8")
    if type(s.qcl) is not int or not 1 <= s.qcl <= 4:
        errors.append("qcl must identify an installed QCL (1–4)")
    if len(set((*s.demod_indices, s.timing_demod))) != len(s.demod_indices) + 1:
        errors.append("Sample/reference/timing demodulators must be distinct")
    if s.sample_demod != 0 or (s.mode == "dual" and s.reference_demod != 3) or s.timing_demod != 2:
        errors.append("Installed HF2LI roles require sample demod 0, reference demod 3 and timing demod 2")
    if s.schedule_kind not in {"logarithmic", "information_based"}:
        errors.append("schedule_kind must be logarithmic or information_based")
    if s.schedule_kind == "information_based" and not s.later_burst_times_s:
        errors.append("Information-based scheduling requires explicit prospective later_burst_times_s")
    if s.scan_start_cm1 == s.scan_stop_cm1 and s.scan_start_cm1 is not None:
        errors.append("Scan range must have nonzero width")
    for name in ("pump_polarity", "process_polarity"):
        if getattr(s, name) not in {"positive", "negative"}:
            errors.append(f"{name} must be positive or negative")
    if s.process_polarity != "negative":
        errors.append("Installed MIRcat Process Trigger requires negative pulse polarity (inactive high)")
    if not _finite_number(s.native_chunk_duration_s) or s.native_chunk_duration_s <= 0:
        errors.append("native_chunk_duration_s must be finite and positive")
    if type(s.max_memory_bytes) is not int or s.max_memory_bytes <= 0:
        errors.append("max_memory_bytes must be a positive integer")
    if s.storage_budget_bytes is not None and (type(s.storage_budget_bytes) is not int or s.storage_budget_bytes <= 0):
        errors.append("storage_budget_bytes must be a positive integer when declared")
    for name in ("configuration_time_s", "tuning_settling_time_s", "controls_time_s",
                 "restoration_time_s", "processing_time_s", "upload_seconds_per_frame"):
        value = getattr(s, name)
        if value is not None and (not _finite_number(value) or value < 0):
            errors.append(f"{name} must be finite and nonnegative")
    if s.plateau_enabled:
        if not _finite_number(s.plateau_relative_tolerance) or not 0 < s.plateau_relative_tolerance < 1:
            errors.append("Plateau stopping requires a prospective relative tolerance between zero and one")
        if type(s.plateau_required_bursts) is not int or s.plateau_required_bursts < 3 or not s.plateau_band_windows_cm1:
            errors.append("Plateau stopping requires at least three bursts and explicit per-band windows")
    for window in s.plateau_band_windows_cm1:
        if not isinstance(window, (tuple, list)) or len(window) != 2:
            errors.append("Plateau windows require pairs of cm-1 bounds")
            continue
        lower, upper = window
        if not (_finite_number(lower) and _finite_number(upper) and lower < upper):
            errors.append("Plateau windows require finite increasing cm-1 bounds")

    for name in ("sample_id", "preparation_id", "accepted_state_id", "matrix_id", "cell_id", "position_id",
                 "temperature_identity", "thermal_history_id", "sample_selection_id", "pump_dose_record_id"):
        if not getattr(s, name):
            readiness.append(f"Provide the condition-specific {name}")
    for name in ("measured_temperature_k", "temperature_uncertainty_k", "min_temperature_k", "max_temperature_k",
                 "max_probe_exposure_s", "temperature_check_interval_s"):
        value = getattr(s, name)
        if value is None:
            readiness.append(f"Establish {name} for the illuminated sample")
        elif not _finite_number(value) or value < 0 or (name != "temperature_uncertainty_k" and value == 0):
            errors.append(f"{name} must be finite and positive (uncertainty may be zero)")
    if all(_finite_number(v) for v in (s.measured_temperature_k, s.min_temperature_k, s.max_temperature_k)):
        if not s.min_temperature_k <= s.measured_temperature_k <= s.max_temperature_k:
            errors.append("Measured sample temperature is outside the accepted condition interval")
        elif _finite_number(s.temperature_uncertainty_k) and not (
            s.min_temperature_k <= s.measured_temperature_k - s.temperature_uncertainty_k and
            s.measured_temperature_k + s.temperature_uncertainty_k <= s.max_temperature_k):
            errors.append("Sample temperature uncertainty envelope crosses the accepted condition interval")
    if not cap.frame_feature_verified:
        readiness.append("Verify installed T660-2 Trains and Frames support and capacity under host ownership")
    if not cap.detector_rates_verified:
        readiness.append("Verify selected HF2LI sample/reference/timing rates simultaneously and aggregate throughput")
    if not cap.topology_verified:
        readiness.append("Qualify installed detector tees, receiver loading and Sweep Active high-impedance branch")
    if not cap.optical_pump_observation_available:
        readiness.append("Provide independently observed single optical pump count/time zero in the qualified sample path")
    if not cap.temperature_observation_available:
        readiness.append("Provide qualified illuminated-sample temperature observations before/during/after bursts and waits")
    if not s.probe_during_wait and not cap.probe_idle_control_available:
        errors.append("Selected dark waits require installed probe output control")
    if not s.promoted_bundle_ids or not s.calibration_ids:
        readiness.append("Select applicable explicitly promoted timing, spectral trajectory, detector/filter and dose calibration records")
    if not s.controls_record_ids:
        readiness.append("Select applicable accepted dark, optical/electronic artifact and cryogenic matrix/cell controls")
    if s.example_only:
        readiness.append("EXAMPLE ONLY simulation inputs are not biological operating settings")
    if errors:
        return Plan(s, cap, errors=tuple(errors), readiness=tuple(readiness), warnings=tuple(warnings))

    # Budget the entire finite schedule with integer arithmetic BEFORE generating
    # logarithmic times, frames, detached settings copies or per-block metadata.
    # Explicit information-based times replace the requested logarithmic count.
    selected_burst_count = len(s.later_burst_times_s) if s.later_burst_times_s else s.later_burst_count
    plan_frame_count = (s.early_scan_count + 1 + s.final_scan_count + 1 +
                        selected_burst_count * (s.scans_per_burst + 1) + s.preliminary_scan_count + 1)
    plan_block_count = selected_burst_count + 3  # early, final and preliminary
    frame_metadata_bytes = (plan_frame_count * PLAN_FRAME_METADATA_BYTES +
                            plan_block_count * PLAN_BLOCK_METADATA_BYTES)
    plan_metadata_bytes = frame_metadata_bytes * PLAN_METADATA_COPIES
    resource_estimates = {"plan_frame_count_including_preliminary": plan_frame_count,
        "plan_frame_metadata_bytes": frame_metadata_bytes, "plan_metadata_bytes": plan_metadata_bytes,
        "plan_metadata_basis": "4096 bytes per explicit frame + 2048 bytes per block/idle record, ×3 for plan, host snapshot and serialization/control table"}
    if plan_metadata_bytes > s.max_memory_bytes:
        errors.append("Finite plan frame metadata exceeds the declared RAM budget before schedule allocation")
    if s.storage_budget_bytes is not None and plan_metadata_bytes > s.storage_budget_bytes:
        errors.append("Finite plan frame metadata exceeds the declared storage budget before schedule allocation")
    if errors:
        return Plan(s, cap, errors=tuple(errors), readiness=tuple(readiness), warnings=tuple(warnings),
                    estimates=resource_estimates)

    selected: dict[str, float] = {}
    timing_fields = ("pump_fire_to_q_s", "pump_fire_width_s", "pump_q_width_s", "process_width_s",
                     "first_scan_delay_s", "probe_pulse_width_s")
    for name in timing_fields:
        selected[name] = quantize(getattr(s, name), cap.edge_quantum_s)
    selected["probe_rate_hz"] = quantize(s.probe_rate_hz, cap.synthesizer_quantum_hz)
    if not 0 < selected["probe_rate_hz"] <= cap.synthesizer_max_hz:
        errors.append("Selected probe rate is outside the T660 synthesizer range")
    for name in timing_fields:
        if name != "first_scan_delay_s" and selected[name] <= 0:
            errors.append(f"{name} quantizes to zero on the installed edge grid")
    if errors:
        return Plan(s, cap, errors=tuple(errors), readiness=tuple(readiness), warnings=tuple(warnings))
    if selected["probe_pulse_width_s"] * selected["probe_rate_hz"] > cap.probe_duty_max:
        errors.append("Probe pulse width × rate exceeds the manufacturer's duty limit")
    if s.probe_reference_delay_s + selected["probe_pulse_width_s"] + 62.5e-9 >= 1 / selected["probe_rate_hz"]:
        errors.append("Probe delay/width violates the T660 repetition dead time")
    divider = ceil(s.scan_interval_s * selected["probe_rate_hz"] - 1e-9)
    if not 1 <= divider <= cap.predivider_max:
        errors.append("Scan interval exceeds the installed frame predivider range")
    selected["scan_interval_s"] = divider / selected["probe_rate_hz"]
    for role, requested, choices in (("sample", s.sample_rate_hz, cap.sample_rates_hz),
            ("timing", s.timing_rate_hz, cap.timing_rates_hz),
            *(([("reference", s.reference_rate_hz, cap.reference_rates_hz)]) if s.mode == "dual" else [])):
        if choices and not any(abs(requested - choice) <= 1e-8 * max(1, choice) for choice in choices):
            errors.append(f"Selected {role} rate is absent from installed accepted readbacks")
    aggregate = s.sample_rate_hz + s.timing_rate_hz + (s.reference_rate_hz if s.mode == "dual" else 0.0)
    if aggregate > cap.hf2_aggregate_rate_max_hz:
        errors.append("Combined HF2LI detector and timing throughput exceeds installed aggregate limit")
    for value in (s.scan_start_cm1, s.scan_stop_cm1):
        if cap.wavenumber_min_cm1 is not None and value < cap.wavenumber_min_cm1 or cap.wavenumber_max_cm1 is not None and value > cap.wavenumber_max_cm1:
            errors.append("Scan endpoint is outside the installed calibrated cm-1 range")
    if cap.scan_speed_min_cm1_s is not None and s.scan_speed_cm1_s < cap.scan_speed_min_cm1_s or cap.scan_speed_max_cm1_s is not None and s.scan_speed_cm1_s > cap.scan_speed_max_cm1_s:
        errors.append("Scan speed is outside installed accepted capability limits")
    for name, value in s.to_dict().items():
        if _finite_number(value):
            unit = "cm-1 s-1" if name.endswith("cm1_s") else "cm-1" if name.endswith("cm1") else "Hz" if name.endswith("hz") else "K" if name.endswith("_k") else "s" if name.endswith("_s") else "count / scalar"
            selected_values[name] = {"requested": value, "selected": selected.get(name, value),
                "actual": cap.actual_values.get(name), "unit": unit,
                "source": s.settings_sources.get(name, "EXAMPLE ONLY" if s.example_only else "explicit operator request; qualification required")}
    if errors:
        return Plan(s, cap, errors=tuple(errors), readiness=tuple(readiness), warnings=tuple(warnings), selected_values=selected_values)

    scan_duration = abs(s.scan_stop_cm1 - s.scan_start_cm1) / s.scan_speed_cm1_s
    interval = selected["scan_interval_s"]
    early_end = s.first_scan_delay_s + s.early_scan_count * interval
    final_start = s.observation_limit_s - ((s.final_scan_count - 1) * interval + scan_duration)
    last_later_start = final_start - (s.scans_per_burst + 1) * interval
    try:
        later_times = tuple(float(t) for t in s.later_burst_times_s) if s.later_burst_times_s else logarithmic_times(
            s.first_later_burst_s or 1.0, last_later_start, s.later_burst_count)
        selected_values["later_burst_count"]["selected"] = len(later_times)
        if any(not isfinite(t) or t <= 0 for t in later_times):
            raise ValueError("Later elapsed times must be finite and strictly positive")
        if tuple(sorted(set(later_times))) != later_times:
            raise ValueError("Later elapsed times must be unique and strictly increasing")
        if final_start <= early_end:
            raise ValueError("Observation limit must contain the early train and a separate final state spectrum")
        previous_end = early_end
        for t in later_times:
            if t < previous_end:
                raise ValueError("Requested later burst overlaps the preceding continuous block")
            previous_end = t + (s.scans_per_burst + 1) * interval
        if previous_end > final_start + 1e-9:
            raise ValueError("Later burst overlaps the finite final-state spectrum at the observation limit")
        blocks = [compile_block(s, cap, block_id="early-000", kind="early", elapsed_s=s.first_scan_delay_s,
                    scan_count=s.early_scan_count, pump=True, selected=selected)]
        blocks.extend(compile_block(s, cap, block_id=f"burst-{i:03d}", kind="burst", elapsed_s=t,
                      scan_count=s.scans_per_burst, pump=False, selected=selected) for i, t in enumerate(later_times, 1))
        blocks.append(compile_block(s, cap, block_id="final-000", kind="final", elapsed_s=final_start,
                      scan_count=s.final_scan_count, pump=False, selected=selected))
    except (ValueError, OverflowError) as exc:
        return Plan(s, cap, errors=(str(exc),), readiness=tuple(readiness), warnings=tuple(warnings), selected_values=selected_values)

    acquisition_s = sum(block.duration_s for block in blocks)
    preliminary_s = (s.preliminary_scan_count + 1) * interval
    acquire_blank = s.mode == "single" and s.blank_source == "acquire"
    # A newly acquired single-detector blank follows the whole unpumped scan
    # schedule. Loading a previously compatible complete record avoids that run.
    blank_observation_s = s.observation_limit_s if acquire_blank else 0.0
    control_spectral_s = preliminary_s
    byte_rate = (s.sample_rate_hz + (s.reference_rate_hz if s.mode == "dual" else 0)) * 48 + s.timing_rate_hz * 24
    # Conservative: timing and spectral streams may be retained during the full
    # observation to maintain clock/state evidence. Chunking bounds RAM only.
    native_seconds = s.observation_limit_s + blank_observation_s + control_spectral_s
    native_bytes = ceil(native_seconds * byte_rate * 1.25)
    largest_block_s = max(block.duration_s for block in blocks)
    peak_memory_bytes = plan_metadata_bytes + ceil(byte_rate * (s.native_chunk_duration_s * 3 + largest_block_s * 4))
    total_storage_bytes = native_bytes + plan_metadata_bytes
    exposure_s = ((s.observation_limit_s if s.probe_during_wait else acquisition_s) *
                  (2 if acquire_blank else 1)) + control_spectral_s
    pulse_on_s = exposure_s * selected["probe_pulse_width_s"] * selected["probe_rate_hz"]
    if s.max_probe_exposure_s is not None and pulse_on_s > s.max_probe_exposure_s:
        errors.append("Declared pulse-on probe exposure budget is exceeded by preliminary/bursts/waits")
    if peak_memory_bytes > s.max_memory_bytes:
        errors.append("Native chunk buffer estimate exceeds the declared RAM budget")
    if s.storage_budget_bytes is not None and total_storage_bytes > s.storage_budget_bytes:
        errors.append("Native retention and finite plan metadata exceed the declared storage budget")
    overhead_names = ("configuration_time_s", "tuning_settling_time_s", "controls_time_s", "restoration_time_s", "processing_time_s")
    unknown_overheads = [name for name in overhead_names if getattr(s, name) is None]
    overhead = sum(getattr(s, name) or 0.0 for name in overhead_names)
    frames = sum(len(block.frames) for block in blocks)
    upload = (frames * (2 if acquire_blank else 1) + s.preliminary_scan_count + 1) * (s.upload_seconds_per_frame or 0.0)
    if s.upload_seconds_per_frame is None:
        unknown_overheads.append("upload_seconds_per_frame")
    if unknown_overheads:
        warnings.append("Wall-time estimate is a lower bound; unmeasured overheads: " + ", ".join(unknown_overheads))
    if not s.probe_during_wait:
        warnings.append("Dark idle disables installed T660-1 probe channel B; lock reference A stays on. Re-enable and settle are observed and add real gaps.")
    estimates = {**resource_estimates, "scan_duration_s": scan_duration, "scan_interval_s": interval, "total_scans": sum(b.scan_count for b in blocks),
        "physical_frame_count": frames, "pump_command_count": 1, "block_count": len(blocks),
        "longest_observation_s": s.observation_limit_s, "native_bytes": native_bytes, "total_storage_bytes": total_storage_bytes,
        "native_estimate_basis": "48 bytes/detector sample + 24 bytes/timing sample across entire observation, ×1.25 retention allowance",
        "peak_memory_bytes": peak_memory_bytes, "aggregate_rate_hz": aggregate,
        "memory_estimate_basis": "full finite frame/block metadata ×3, plus three native chunks and four copies of the largest full block for reconstruction",
        "blank_source": s.blank_source if s.mode == "single" else "simultaneous matched reference",
        "blank_observation_s": blank_observation_s,
        "acquisition_s": acquisition_s, "probe_enabled_s": exposure_s, "probe_pulse_on_s": pulse_on_s,
        "dark_wait_s": max(0.0, s.observation_limit_s - acquisition_s),
        "upload_s": upload, "wall_time_min_s": s.observation_limit_s + blank_observation_s + control_spectral_s + overhead + upload,
        "wall_time_basis": "observation + control spectra + measured preparation/controls/tuning/restoration/processing + acknowledged upload estimate; user physical actions are additional",
        "unknown_overheads": unknown_overheads, "automatic_reset": False, "automatic_repeat": False}
    steps: list[dict[str, Any]] = [
        {"kind": "configure", "action": "freeze output root; own instruments; read and preserve initial state"},
        {"kind": "controls", "action": "load/acquire compatible sequential matched blank" if s.mode == "single" else "simultaneous sample/matched-buffer reference; no routine separate blank"},
        {"kind": "preliminary", "action": "acquire stationary unpumped spectra and temperature; explicit preliminary review and Start"},
    ]
    previous = 0.0
    for block in blocks:
        if block.planned_elapsed_s > previous:
            steps.append({"kind": "idle", "start_elapsed_s": previous, "end_elapsed_s": block.planned_elapsed_s,
                          "probe_enabled": s.probe_during_wait, "pump_enabled": False,
                          "temperature_check_interval_s": s.temperature_check_interval_s,
                          "action": "durable native chunks/checkpoints; abortable wait; retain original epoch"})
        steps.append({"kind": block.kind, "block_id": block.block_id, "scan_count": block.scan_count,
            "planned_elapsed_s": block.planned_elapsed_s, "temperature_checks": ["before", "during", "after"],
            "pump_count": 1 if block.pump_enabled else 0})
        previous = block.planned_end_s
    steps.extend(({"kind": "restore", "action": "all pump/process outputs OFF; verify safe instrument restoration; retain failures"},
                  {"kind": "save_analyze", "action": "preserve all native/history/partial records; report band-specific right-censoring and unresolved claims"}))
    return Plan(s, cap, blocks=tuple(blocks), errors=tuple(errors), readiness=tuple(readiness), warnings=tuple(warnings),
                selected_values=selected_values, estimates=estimates, steps=tuple(steps),
                probe_clock_recipe=probe_clock_recipe(s, selected))


def compile_preliminary(plan: Plan, *, kind: str = "preliminary") -> BurstBlock:
    """Use the same selected hardware values, with every pump output OFF."""
    plan.require_valid()
    return compile_block(plan.settings, plan.capabilities, block_id=kind, kind=kind, elapsed_s=0.0,
        scan_count=plan.settings.preliminary_scan_count, pump=False,
        selected={name: row["selected"] for name, row in plan.selected_values.items()})


def compile_blank_blocks(plan: Plan) -> tuple[BurstBlock, ...]:
    """A complete single-detector sequential control uses every planned block."""
    plan.require_valid()
    selected = {name: row["selected"] for name, row in plan.selected_values.items()}
    return tuple(compile_block(plan.settings, plan.capabilities, block_id=f"blank-{block.block_id}",
                 kind=f"blank-{block.kind}", elapsed_s=block.planned_elapsed_s,
                 scan_count=block.scan_count, pump=False, selected=selected) for block in plan.blocks)
