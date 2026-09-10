"""Hardware-free event planning with independent Auto overrides and live resolution.

Every material and temperature uses this same procedure. Missing scientific
calibration limits interpretation; only executable timing/device constraints
are acquisition errors. Device reads occur later through the owned lifecycle.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random
from typing import Any, Mapping

from .settings import EXPERIMENT_ID, KERNEL_ID, Settings, resolve_settings
from .timing import compile_timing, event_frames

PLAN_MATERIALIZATION_LIMIT_BYTES = 256 * 1024 * 1024
ESTIMATED_FRAME_OBJECT_BYTES = 4096
ESTIMATED_EVENT_OBJECT_BYTES = 2048


@dataclass(frozen=True)
class Event:
    event_id: str
    wavenumber_cm1: float
    requested_delay_ns: float
    quantized_delay_ns: float | None
    condition: str
    repetition: int
    frames: tuple[dict[str, Any], ...]
    frame_index: int
    kernel_id: str
    position_id: str
    block_id: str
    electrical_delay_ns: float | None
    observed_electrical_delay_ns: float | None = None
    calibrated_optical_delay_ns: float | None = None


@dataclass(frozen=True)
class Plan:
    settings: Settings
    events: tuple[Event, ...]
    errors: tuple[str, ...]
    readiness: tuple[str, ...]
    warnings: tuple[str, ...]
    budget: dict[str, Any]
    timing: dict[str, Any]
    acquisition_layout: str = "explicit_event_bursts_at_fixed_wavenumber"
    resolved_settings: Settings | None = None
    resolution_sources: dict[str, str] | None = None
    unresolved: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def connected_ready(self) -> bool:
        # Pending live reads are performed automatically during preparation.
        return not self.errors


def _finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def build_plan(settings: Settings | dict[str, Any], capabilities: Mapping[str, Any] | None = None) -> Plan:
    requested = Settings.from_dict(settings)
    errors, warnings = [], []
    if requested.experiment_id != EXPERIMENT_ID or requested.schema_version != "1.0":
        errors.append("Incompatible experiment identity or settings schema")
    if requested.mode not in ("single", "dual") or requested.execution_mode not in ("simulation", "connected"):
        errors.append("Unsupported detector or execution mode")
    for name in ("wavenumbers_cm1", "delays_ns", "off_band_wavenumbers_cm1"):
        values = getattr(requested, name)
        if not isinstance(values, (tuple, list)):
            errors.append(f"{name} requires a numeric sequence")
        elif (not values and name != "off_band_wavenumbers_cm1") or any(not _finite_number(v) for v in values):
            errors.append(f"{name} requires finite numeric values")
        elif len(set(values)) != len(values):
            errors.append(f"{name} contains duplicate coordinates")
    if not isinstance(requested.overrides, dict):
        errors.append("Advanced overrides must be a field mapping")
    if errors:
        return Plan(requested, (), tuple(errors), (), (), {}, {})
    if any(_finite_number(v) and v <= 0 for v in (*requested.wavenumbers_cm1, *requested.off_band_wavenumbers_cm1)):
        errors.append("Wavenumbers must be positive cm^-1")
    if not isinstance(requested.repetitions, int) or isinstance(requested.repetitions, bool) or not 1 <= requested.repetitions <= 100000:
        errors.append("Averages must be an integer in 1..100000")
    for name in ("cycle_interval_s",):
        value = getattr(requested, name)
        if not _finite_number(value) or value < 0 or name == "cycle_interval_s" and value == 0:
            errors.append(f"{name} must be finite and {'positive' if name == 'cycle_interval_s' else 'nonnegative'} seconds")
    if requested.ordering not in ("randomized", "counterbalanced", "sequential"):
        errors.append("Unsupported delay ordering")
    if not requested.conditions or any(c not in ("pump_on", "pump_blocked", "dark", "pump_only", "matrix_control") for c in requested.conditions):
        errors.append("Unsupported measurement condition")
    elif len(set(requested.conditions)) != len(requested.conditions):
        errors.append("Duplicate measurement conditions")
    for name in ("max_storage_bytes", "max_pump_events", "max_frame_capacity"):
        value = getattr(requested, name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            errors.append(f"{name} must be a positive integer")
    if isinstance(requested.max_frame_capacity, int) and requested.max_frame_capacity > 8192:
        errors.append("T660 frame capacity cannot exceed documented 8192 entries")
    for name in ("preparation_estimate_s", "tune_settle_estimate_s", "upload_frame_estimate_s", "processing_estimate_s", "restoration_estimate_s"):
        if not _finite_number(getattr(requested, name)) or getattr(requested, name) < 0:
            errors.append(f"{name} must be finite and nonnegative")
    if errors:
        return Plan(requested, (), tuple(errors), (), (), {}, {})
    resolution = resolve_settings(requested, capabilities)
    s = resolution.settings
    errors.extend(resolution.errors)
    for name in ("probe_period_s", "fire_command_width_ns", "q_command_width_ns", "probe_command_width_ns", "reference_command_width_ns", "event_trigger_width_ns", "timing_step_ns", "hf2li_rate_hz", "filter_time_constant_s", "reference_filter_time_constant_s", "reference_hf2li_rate_hz"):
        value = getattr(s, name)
        if value is not None and value <= 0:
            errors.append(f"Selected {name} must be positive")
    for name in ("probe_anchor_ns", "fire_to_q_ns"):
        value = getattr(s, name)
        if value is not None and value < 0:
            errors.append(f"Selected {name} must be nonnegative")
    for name in ("warmup_frames", "filter_tail_frames"):
        value = getattr(s, name)
        if value is not None and (not isinstance(value, int) or value < 0):
            errors.append(f"Selected {name} must be a nonnegative integer")
    if s.filter_order is not None and not 1 <= s.filter_order <= 8:
        errors.append("HF2LI filter order must be in 1..8")
    if s.reference_filter_order is not None and not 1 <= s.reference_filter_order <= 8:
        errors.append("Reference HF2LI filter order must be in 1..8")
    detector_filters = [("sample", s.filter_time_constant_s, s.hf2li_rate_hz)]
    if s.mode == "dual":
        detector_filters.append(("reference", s.reference_filter_time_constant_s, s.reference_hf2li_rate_hz))
    for role, tc, rate in detector_filters:
        if tc is not None and rate is not None and tc > 0 and rate > 0 and tc * rate < 4 - 1e-9:
            errors.append(f"Selected {role} filter time constant/export rate undersamples the pulse envelope; need at least four samples per time constant for the area estimator")
    if any(not isinstance(getattr(s, name), int) or not 0 <= getattr(s, name) <= 5 for name in ("demodulator_sample", "demodulator_reference")):
        errors.append("HF2LI demodulator indices must be in 0..5")
    if s.demodulator_sample == 2 or s.demodulator_reference == 2 or s.mode == "dual" and s.demodulator_sample == s.demodulator_reference:
        errors.append("Detector demodulators must be distinct from each other and installed timing demodulator 2")
    waves = tuple(dict.fromkeys((*s.wavenumbers_cm1, *s.off_band_wavenumbers_cm1)))
    n = len(waves) * len(s.delays_ns) * s.repetitions * len(s.conditions)
    pump_count = len(waves) * len(s.delays_ns) * s.repetitions * sum(c in ("pump_on", "pump_only") for c in s.conditions)
    frames_per = (s.warmup_frames or 0) + (s.filter_tail_frames or 0) + 2
    plan_bytes = n * (ESTIMATED_EVENT_OBJECT_BYTES + frames_per * ESTIMATED_FRAME_OBJECT_BYTES)
    if n > 1000000 or plan_bytes > PLAN_MATERIALIZATION_LIMIT_BYTES:
        errors.append("Estimated explicit plan memory exceeds the 256 MiB materialization limit; reduce schedule before allocation")
    if frames_per > s.max_frame_capacity:
        errors.append("An event burst exceeds verified finite frame capacity")
    if pump_count > s.max_pump_events:
        errors.append("Planned pump events exceed the selected event budget")
    timing = None
    if not errors and not resolution.unresolved:
        try:
            timing = compile_timing(s)
            if len(set(timing.quantized_delays_ns)) != len(s.delays_ns):
                errors.append("Distinct requested delays collapse onto the selected hardware command grid")
        except (ValueError, TypeError, OverflowError) as exc:
            errors.append(str(exc))
    period = timing.frame_period_s if timing else s.probe_period_s or s.cycle_interval_s
    if period * frames_per < .1:
        errors.append("Finite event bursts exceed the installed 10 Hz pump maximum")
    if timing and not math.isclose(period, s.probe_period_s, rel_tol=1e-9):
        warnings.append(f"Requested probe cycle {s.probe_period_s:g} s selects {period:g} s on T660 DDS grid")
    if requested.execution_mode == "simulation":
        warnings.append("EXAMPLE ONLY simulation; generated signals and instrument values are not connected observations")
    if s.optical_delay_offset_ns is None:
        warnings.append("Optical time zero is unavailable: retain electrical command bins and relative spectral response; resolved lifetime remains unavailable")
    blank_n = n if s.mode == "single" else 0
    preliminary_n = len(waves)
    prep_n = blank_n + preliminary_n
    physical_frames = n * frames_per
    all_frames = (n + prep_n) * frames_per
    channels = streams = 2 if s.mode == "dual" else 1
    pre_capture_s = min(.2, period / 4)
    filter_terms = [(s.filter_time_constant_s, s.filter_order)]
    if s.mode == "dual":
        filter_terms.append((s.reference_filter_time_constant_s, s.reference_filter_order))
    filter_tail_s = max(8 * tc * order for tc, order in filter_terms) if all(tc is not None and order is not None for tc, order in filter_terms) else None
    post_capture_s = period + filter_tail_s if filter_tail_s is not None else None
    capture_per_event_s = pre_capture_s + frames_per * period + post_capture_s if post_capture_s is not None else None
    native_capture_s = (n + prep_n) * capture_per_event_s if capture_per_event_s is not None else None
    # The pre-live preview is a lower-bound estimate; unresolved filter tails
    # stay None and never become invented native storage/sample counts.
    preview_capture_per_event_s = capture_per_event_s if capture_per_event_s is not None else pre_capture_s + (frames_per + 1) * period
    rate = s.hf2li_rate_hz
    rates = [rate] + ([s.reference_hf2li_rate_hz] if s.mode == "dual" else [])
    aggregate_rate = sum(rates) if all(r is not None for r in rates) else None
    native_samples = math.ceil(native_capture_s * aggregate_rate) if aggregate_rate is not None and native_capture_s is not None else None
    native_bytes = native_samples * 7 * 8 if native_samples is not None else None
    storage_bytes = native_bytes * 4 + (n + prep_n) * 4096 if native_bytes is not None else None
    if storage_bytes is not None and storage_bytes > s.max_storage_bytes:
        errors.append("Projected native stream storage exceeds selected storage budget")
    events = []
    if not errors:
        rng = random.Random(s.random_seed)
        for wi, nu in enumerate(waves):
            pairs = [(di, c, rep) for rep in range(s.repetitions) for di in range(len(s.delays_ns)) for c in s.conditions]
            if s.ordering == "randomized":
                rng.shuffle(pairs)
            elif s.ordering == "counterbalanced":
                pairs = []
                for rep in range(s.repetitions):
                    ds = list(range(len(s.delays_ns)))
                    if (rep + wi) % 2:
                        ds.reverse()
                    for di in ds:
                        cs = list(s.conditions)
                        if (di + rep + wi) % 2:
                            cs.reverse()
                        pairs.extend((di, c, rep) for c in cs)
            for di, condition, rep in pairs:
                index = len(events)
                frame_table = event_frames(s, s.delays_ns[di], pump_on=condition in ("pump_on", "pump_only")) if timing else ()
                events.append(Event(f"event-{index + 1:07d}", nu, s.delays_ns[di], timing.quantized_delays_ns[di] if timing else None,
                                    condition, rep, frame_table, s.warmup_frames or 0, KERNEL_ID,
                                    s.position_ids[0] if s.position_ids else "", f"wavenumber-{wi + 1:05d}",
                                    timing.electrical_delays_ns[di] if timing else None))
    operations = 3 if s.mode == "single" else 2
    acquisition_s = n * preview_capture_per_event_s
    reset_s = pump_count * s.reset_interval_s
    preparation_s = operations * s.preparation_estimate_s + prep_n * preview_capture_per_event_s
    tune_s = len(waves) * operations * s.tune_settle_estimate_s
    upload_s = all_frames * s.upload_frame_estimate_s
    restoration_s = operations * s.restoration_estimate_s
    processing_s = operations * s.processing_estimate_s
    total_s = acquisition_s + reset_s + preparation_s + tune_s + upload_s + restoration_s + processing_s
    budget = {"event_count": n, "pump_event_count": pump_count, "control_event_count": n - pump_count,
              "preliminary_event_count": preliminary_n, "blank_event_count": blank_n,
              "physical_frame_count": physical_frames, "frames_per_event_burst": frames_per,
              "probe_pulse_count": all_frames, "preparation_frame_count": prep_n * frames_per,
              "reset_count": pump_count, "native_sample_count": native_samples,
              "pre_capture_per_event_s": pre_capture_s, "filter_tail_capture_s": filter_tail_s,
              "post_capture_per_event_s": post_capture_s, "capture_per_event_s": capture_per_event_s,
              "native_capture_s": native_capture_s, "capture_estimate_complete": capture_per_event_s is not None,
              "native_bytes": native_bytes, "storage_bytes": storage_bytes,
              "memory_bytes": native_bytes + plan_bytes if native_bytes is not None else plan_bytes,
              "plan_memory_bytes": plan_bytes, "plan_memory_limit_bytes": PLAN_MATERIALIZATION_LIMIT_BYTES,
              "materialized_event_count": len(events), "detector_count": channels, "stream_count": streams,
              "aggregate_rate_hz": aggregate_rate,
              "acquisition_s": acquisition_s, "reset_s": reset_s, "preparation_s": preparation_s,
              "tune_settle_s": tune_s, "timing_upload_s": upload_s, "restoration_s": restoration_s,
              "processing_s": processing_s, "total_s": total_s, "forward_simulation": None,
              "estimate_basis": "Each retained event includes min(0.2 s, period/4) pre-capture, all finite hardware frames, then one full period plus the slowest active detector's 8 × order × time constant filter tail. Includes blank/preliminary captures, tuning, upload, restoration and analysis. No software reset wait. Before live readback, duration is a lower bound excluding the unresolved filter tail; native capture/sample/storage quantities remain unresolved."}
    # Pending readback messages inform the preview; they are not Start gates.
    readiness = tuple(f"Read {name} automatically during connected preparation" for name in resolution.unresolved)
    timing_data = timing.to_dict() if timing else {}
    if timing is not None:
        timing_data["finite_probe_burst"] = {"pulse_count": frames_per, "trigger_period_count": frames_per + 1,
                                              "gate_mode": 9, "executions_per_event": 1,
                                              "start_command": "GATE:EXECute", "configuration": "Owned adapter commands after inhibited base recipe"}
    return Plan(requested, tuple(events), tuple(dict.fromkeys(errors)), readiness, tuple(warnings), budget,
                timing_data, resolved_settings=s, resolution_sources=resolution.sources,
                unresolved=resolution.unresolved)
