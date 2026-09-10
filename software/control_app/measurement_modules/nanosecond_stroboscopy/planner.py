"""Typed wavelength-major equivalent-time plan, budgets and scientific readiness."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random
from typing import Any

from .settings import EXPERIMENT_ID, KERNEL_ID, PROFILES, Settings
from .timing import compile_timing, event_frames

# Conservative bound for the explicit Python plan, distinct from native file
# storage. This is a software materialization limit, not an instrument limit.
PLAN_MATERIALIZATION_LIMIT_BYTES = 256 * 1024 * 1024
ESTIMATED_FRAME_OBJECT_BYTES = 4096
ESTIMATED_EVENT_OBJECT_BYTES = 2048


@dataclass(frozen=True)
class Event:
    event_id: str
    wavenumber_cm1: float
    requested_delay_ns: float
    quantized_delay_ns: float
    condition: str
    repetition: int
    frames: tuple[dict[str, Any], ...]
    frame_index: int
    kernel_id: str
    position_id: str
    block_id: str
    electrical_delay_ns: float
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def connected_ready(self) -> bool:
        return not self.errors and not self.readiness


def build_plan(settings: Settings | dict[str, Any]) -> Plan:
    s = Settings.from_dict(settings)
    errors, readiness, warnings = [], [], []
    # Runtime type checking is deliberate: JSON allows strings, booleans, NaN and
    # null where dataclass type hints alone would not protect the timing compiler.
    defaults = Settings()
    for name, default in defaults.to_dict().items():
        value = getattr(s, name)
        if isinstance(default, bool):
            valid = isinstance(value, bool)
        elif isinstance(default, int):
            valid = isinstance(value, int) and not isinstance(value, bool)
        elif isinstance(default, float) or name in ("temperature_k", "temperature_uncertainty_k", "optical_delay_offset_ns"):
            valid = value is None and default is None or isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        elif isinstance(default, str):
            valid = isinstance(value, str)
        elif isinstance(default, dict):
            valid = isinstance(value, dict)
        elif isinstance(default, (tuple, list)):
            valid = isinstance(value, (tuple, list))
            if valid and name in ("wavenumbers_cm1", "delays_ns", "off_band_wavenumbers_cm1"):
                valid = all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value)
            elif valid:
                valid = all(isinstance(v, str) for v in value)
        else:
            valid = True
        if not valid:
            errors.append(f"{name} has an invalid type or non-finite value")
    if errors:
        return Plan(s, (), tuple(errors), (), (), {}, {})
    if s.experiment_id != EXPERIMENT_ID or s.schema_version != "1.0":
        errors.append("Incompatible experiment identity or settings schema")
    if s.mode not in ("single", "dual") or s.execution_mode not in ("simulation", "connected"):
        errors.append("Detector mode/execution mode is unsupported")
    if s.profile_id not in PROFILES:
        errors.append("Unknown protein/temperature profile")
    if s.ordering not in ("randomized", "counterbalanced"):
        errors.append("Delay and condition order must be randomized or counterbalanced")
    for name in ("wavenumbers_cm1", "delays_ns", "off_band_wavenumbers_cm1"):
        values = getattr(s, name)
        if (not values and name != "off_band_wavenumbers_cm1") or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            errors.append(f"{name} must contain finite numeric values")
        elif len(set(values)) != len(values):
            errors.append(f"{name} contains duplicate native coordinates")
    if any(v <= 0 for v in (*s.wavenumbers_cm1, *s.off_band_wavenumbers_cm1)):
        errors.append("Wavenumbers must be positive in cm^-1")
    if not isinstance(s.repetitions, int) or not 1 <= s.repetitions <= 100000:
        errors.append("Technical repetitions must be an integer in 1..100000")
    if not s.conditions or any(c not in ("pump_on", "pump_blocked", "dark", "pump_only", "matrix_control") for c in s.conditions):
        errors.append("Unsupported control condition")
    for field in ("warmup_frames", "filter_tail_frames", "preliminary_event_count", "blank_event_count"):
        if not isinstance(getattr(s, field), int) or getattr(s, field) < 0:
            errors.append(f"{field} must be a nonnegative integer")
    for field in ("probe_period_s", "reset_interval_s", "pump_command_width_ns", "probe_command_width_ns", "timing_step_ns", "hf2li_rate_hz", "filter_time_constant_s", "noise_sd", "candidate_lifetime_ns"):
        if not math.isfinite(getattr(s, field)) or getattr(s, field) <= 0:
            errors.append(f"{field} must be finite and positive")
    for field in ("irf_sigma_ns", "timing_jitter_ns", "integration_aperture_ns", "filter_blur_ns", "fire_to_q_ns", "probe_anchor_ns", "preparation_estimate_s", "tune_settle_estimate_s", "upload_frame_estimate_s", "processing_estimate_s", "restoration_estimate_s"):
        if not math.isfinite(getattr(s, field)) or getattr(s, field) < 0:
            errors.append(f"{field} must be finite and nonnegative")
    if not isinstance(s.filter_order, int) or not 1 <= s.filter_order <= 8:
        errors.append("HF2LI filter order must be an integer in 1..8")
    if not 0 <= s.demodulator_sample <= 5 or not 0 <= s.demodulator_reference <= 5:
        errors.append("HF2LI demodulator indices must be in 0..5 and reconciled with installed readbacks")
    if s.temperature_k is not None and s.temperature_k <= 0 or s.temperature_uncertainty_k is not None and s.temperature_uncertainty_k < 0:
        errors.append("Measured temperature must be positive kelvin and uncertainty nonnegative")
    if not 0 <= s.reset_residual_fraction < 1:
        errors.append("Reset residual fraction must be in [0,1)")
    if any(not isinstance(getattr(s, f), int) or getattr(s, f) < 1 for f in ("max_storage_bytes", "max_pump_events", "max_frame_capacity")):
        errors.append("Storage, pump-event and frame-capacity budgets must be positive integers")
    if s.max_frame_capacity > 8192:
        errors.append("Frame capacity cannot exceed documented T660 8192 entries")
    if not s.position_ids == tuple(dict.fromkeys(s.position_ids)):
        errors.append("Position identities must be distinct; duplicate IDs cannot demonstrate fresh-state reset")
    if s.mode == "dual" and s.demodulator_sample == s.demodulator_reference:
        errors.append("Sample and reference require independent demodulator assignments")
    if s.illustrative_only:
        warnings.append("EXAMPLE ONLY simulator values; no operating settings or biological lifetime is established")
        readiness.append("Replace illustrative settings with applicable promoted calibration and installed readbacks")
    if not s.calibration_ids:
        readiness.append("No applicable promoted instrument bundle is selected; registry creation is not promotion")
    q = s.qualification
    required = {
        "pulse_selection_qualified": "Qualify exactly one MIRcat probe per retained cycle and its sample heating/amplitude stability",
        "hf2li_impulse_qualified": "Qualify HF2LI signed demodulator impulse projection, pretrigger baseline, integration support, gain and filter history for the sparse single-probe kernel",
        "reference_lock_qualified": "Demonstrate HF2LI reference lock and phase stability at the actual quantized sparse-probe frequency",
        "irf_qualified": "Load measured sample-plane optical time zero/IRF, jitter and reference-path timing calibration",
        "tee_transfer_qualified": "Qualify both installed adapter/tee/receiver paths with HF2LI and PicoScope attached",
        "tuning_qualified": "Select accepted Tuned/readiness and detector/HF2LI settling criteria",
        "pump_observation_qualified": "Provide independent optical pump observation; programmed FIRE/Q and electrical DIO alone are insufficient",
        "spectral_selection_accepted": "Load accepted sample-fitted local spectral-selection record for this condition",
    }
    readiness.extend(message for key, message in required.items() if not q.get(key))
    if s.optical_delay_offset_ns is None:
        readiness.append("Calibrated optical route offset is unresolved; requested/command delays cannot be labelled optical arrival")
    if not s.reset_equivalent or not s.reset_record_id:
        readiness.append("Demonstrate equivalent initial sample state and retain reset evidence before every biological pump")
    if not all((s.sample_id, s.preparation_id, s.cell_id, s.condition_id)):
        readiness.append("Enter sample, preparation, cell and condition identities")
    profile = PROFILES.get(s.profile_id, {})
    if profile.get("protein") == "HRP" and len(s.selected_populations) < 2:
        readiness.append("HRP requires both sample-fitted CO populations and local baseline/off-band support")
    if s.profile_id == "RT-Mb-G":
        if "A1" not in s.selected_populations:
            readiness.append("RT MbCO is A1-first; include accepted sample-fitted A1 support")
        if any(p in ("A0", "A3") and p not in s.quantified_populations for p in s.selected_populations):
            readiness.append("RT MbCO A0/A3 extension needs measured quantifiability for each added state")
    if profile.get("cryogenic"):
        if not s.matrix_id or s.temperature_k is None or s.temperature_uncertainty_k is None or not s.temperature_record_id:
            readiness.append("Cryogenic condition needs measured illuminated-sample temperature/uncertainty and matrix/thermal-history identity; nominal 77 K is insufficient")
        if s.reset_method != "spectral_recovery":
            readiness.append("Installed adapters have no automatic fresh-position/thermal/flow reset actuator; physical reset needs an independently qualified per-event workflow")
    if not s.off_band_wavenumbers_cm1:
        readiness.append("Specify measured off-band spectral support and applicable artifact controls")
    if not s.sample_selection_id:
        readiness.append("No accepted versioned sample spectral-selection record is linked")
    if "pump_blocked" not in s.conditions:
        readiness.append("Include pump-blocked controls in the finite event budget")
    for control in ("dark", "pump_only", "matched_buffer", "state_before_after"):
        if not s.control_records.get(control) and not s.control_applicability.get(control):
            readiness.append(f"Record {control} control or explicit applicability/physical-action reason")
    if any(c in s.conditions for c in ("dark", "pump_only", "matrix_control")):
        readiness.append("Dark/pump-only/matrix control conditions require physical preparation; no connected shutter or cell exchange actuator is installed")
    waves = tuple(dict.fromkeys((*s.wavenumbers_cm1, *s.off_band_wavenumbers_cm1)))
    expected = len(waves) * len(s.delays_ns) * max(s.repetitions, 0) * len(s.conditions)
    expected_pumps = len(waves) * len(s.delays_ns) * max(s.repetitions, 0) * sum(c in ("pump_on", "pump_only") for c in s.conditions)
    frames_per = max(0, s.warmup_frames + s.filter_tail_frames + 2)
    plan_memory_bytes = expected * (ESTIMATED_EVENT_OBJECT_BYTES + frames_per * ESTIMATED_FRAME_OBJECT_BYTES)
    if expected > 1000000:
        errors.append("Plan exceeds one million explicit events; reduce schedule before materializing native records")
    if frames_per > min(s.max_frame_capacity, 8192):
        errors.append("An explicitly planned event burst exceeds verified finite frame capacity")
    if expected_pumps > s.max_pump_events:
        errors.append("Planned biological pump events exceed declared dose/event limit")
    if plan_memory_bytes > PLAN_MATERIALIZATION_LIMIT_BYTES:
        errors.append("Estimated explicit plan memory exceeds the 256 MiB materialization limit; reduce the schedule before allocation")
    timing = None
    simulation_summary = None
    if not errors:
        try:
            timing = compile_timing(s)
        except (ValueError, OverflowError) as exc:
            errors.append(str(exc))
    if timing is not None:
        if len(set(timing.quantized_delays_ns)) != len(s.delays_ns):
            errors.append("Distinct requested delays collapse onto the selected electrical command grid")
        if not math.isclose(timing.frame_period_s, s.probe_period_s, rel_tol=1e-9):
            warnings.append(f"Requested probe period {s.probe_period_s:g} s selects {timing.frame_period_s:g} s on documented 0.02 Hz DDS grid")
        burst_period = (s.warmup_frames + s.filter_tail_frames + 2) * timing.frame_period_s
        if burst_period < 0.1 - 1e-12:
            errors.append("Finite bursts permit pump cadence above the installed 10 Hz maximum")
        support = 3 * math.hypot(s.irf_sigma_ns, s.timing_jitter_ns) + s.integration_aperture_ns / 2 + 3 * s.filter_blur_ns
        if sum(d < s.time_zero_ns - support for d in s.delays_ns) < 2:
            readiness.append("Plan at least two negative delays outside measured IRF/aperture support")
        near = sorted(d for d in s.delays_ns if abs(d - s.time_zero_ns) <= support)
        early_spacing = max(2 * math.hypot(s.irf_sigma_ns, s.timing_jitter_ns), s.integration_aperture_ns, s.timing_step_ns)
        if len(near) < 3 or any(b - a > early_spacing for a, b in zip(near, near[1:])):
            readiness.append("Add dense response/earliest-recovery points at spacing supported by measured IRF, jitter and aperture")
        if max(s.delays_ns) < max(1000, 4 * s.candidate_lifetime_ns):
            readiness.append("Add justified later/bridge points beyond early recovery to distinguish lifetime from persistent offset")
        if s.filter_tail_frames * timing.frame_period_s < 5 * s.filter_time_constant_s:
            readiness.append("Impulse tail/filter memory exceeds planned retained tail; extend explicit tail or qualify a truncation correction")
        if s.warmup_frames * timing.frame_period_s < 5 * s.filter_time_constant_s:
            readiness.append("Probe-only warmup is shorter than five filter constants; qualify lock settling or extend warmup")
        if s.confirmatory:
            from .simulation import evaluate_schedule
            simulated = evaluate_schedule(s.delays_ns, s.candidate_lifetime_ns, s.expected_amplitude, s.kernel(), noise_sd=s.noise_sd, repetitions=s.repetitions, trials=8, seed=s.random_seed)
            simulation_summary = {key: value for key, value in simulated.items() if key != "fits"}
            if simulated["resolved_fraction"] < .8 or simulated["relative_bias"] is None or abs(simulated["relative_bias"]) > .1 or simulated["interval_coverage"] < .75:
                readiness.append("Current IRF/noise/reset forward simulation does not support confirmatory lifetime identification; report prompt/unresolved bounds or redesign schedule")
            if not q.get("forward_simulation_accepted") or not q.get("forward_simulation_record_id"):
                readiness.append("Confirmatory schedule requires accepted IRF/noise/reset-aware known-truth recovery and identifiability evidence")
            if not q.get("preparation_replication_justified"):
                readiness.append("Confirmatory replication must follow pilot variance; technical repetitions are not independent preparations")
    events = []
    # Native/JSON storage is also preflighted before allocating even one Event.
    preflight_period = timing.frame_period_s if timing else max(s.probe_period_s, 0)
    preflight_prep = (expected if s.mode == "single" else 0) + len(waves)
    preflight_samples = math.ceil((expected + preflight_prep) * frames_per * preflight_period * max(s.hf2li_rate_hz, 0))
    preflight_streams = 3 if s.mode == "dual" else 2
    preflight_native_bytes = preflight_samples * preflight_streams * 7 * 8
    preflight_storage_bytes = preflight_native_bytes * 4 + (expected + preflight_prep) * 4096
    if preflight_storage_bytes > s.max_storage_bytes:
        errors.append("Projected native stream storage exceeds selected storage budget")
    if not errors and timing:
        rng = random.Random(s.random_seed)
        pump_ordinal = 0
        for wi, nu in enumerate(waves):
            pairs = [(di, c, rep) for rep in range(s.repetitions) for di in range(len(s.delays_ns)) for c in s.conditions]
            if s.ordering == "randomized":
                rng.shuffle(pairs)
            else:
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
                if s.reset_method == "fresh_position":
                    position = s.position_ids[pump_ordinal] if pump_ordinal < len(s.position_ids) else "unassigned"
                    if condition in ("pump_on", "pump_only"):
                        pump_ordinal += 1
                else:
                    position = s.position_ids[0] if s.position_ids else "unassigned"
                events.append(Event(f"event-{index + 1:07d}", nu, s.delays_ns[di], timing.quantized_delays_ns[di], condition, rep,
                                    event_frames(s, s.delays_ns[di], pump_on=condition in ("pump_on", "pump_only")), s.warmup_frames,
                                    KERNEL_ID, position, f"wavenumber-{wi + 1:05d}", timing.electrical_delays_ns[di]))
    n = expected
    pump_count = expected_pumps
    frames_per = s.warmup_frames + s.filter_tail_frames + 2
    physical_frames = n * frames_per
    if frames_per > s.max_frame_capacity:
        errors.append("An explicitly planned event burst exceeds verified finite frame capacity")
    if pump_count > s.max_pump_events:
        errors.append("Planned biological pump events exceed declared dose/event limit")
    if s.reset_method == "fresh_position" and len(s.position_ids) < pump_count:
        readiness.append("Fresh-position reset needs one proven equivalent position per pump event; positions cannot silently cycle")
    period = preflight_period
    blank_n = n if s.mode == "single" else 0
    preliminary_n = len(waves)
    prep_n = blank_n + preliminary_n
    all_frames = physical_frames + prep_n * frames_per
    native_samples = math.ceil(all_frames * period * s.hf2li_rate_hz) if math.isfinite(s.hf2li_rate_hz) else 0
    channels = 2 if s.mode == "dual" else 1
    streams = channels + 1  # Independent demodulator 2 records installed DIO timing.
    # x,y,timestamp,frequency,phase,dio, flags plus record overhead; JSON upper estimate.
    native_bytes = native_samples * streams * 7 * 8
    storage_bytes = native_bytes * 4 + (n + prep_n) * 4096
    if storage_bytes > s.max_storage_bytes:
        errors.append("Projected native stream storage exceeds selected storage budget")
    acquisition_s = physical_frames * period
    reset_s = pump_count * s.reset_interval_s
    operations = 3 if s.mode == "single" else 2
    preparation_s = operations * s.preparation_estimate_s + prep_n * frames_per * period
    tune_s = len(waves) * (3 if s.mode == "single" else 2) * s.tune_settle_estimate_s
    upload_s = all_frames * s.upload_frame_estimate_s
    restoration_s = operations * s.restoration_estimate_s
    processing_s = operations * s.processing_estimate_s
    total_s = acquisition_s + reset_s + preparation_s + tune_s + upload_s + restoration_s + processing_s
    budget = {"event_count": n, "pump_event_count": pump_count, "control_event_count": n - pump_count,
              "preliminary_event_count": preliminary_n, "blank_event_count": blank_n,
              "physical_frame_count": physical_frames, "frames_per_event_burst": frames_per,
              "probe_pulse_count": all_frames, "preparation_frame_count": prep_n * frames_per,
              "reset_count": pump_count, "fresh_positions_required": pump_count if s.reset_method == "fresh_position" else 0,
              "native_sample_count": native_samples, "native_bytes": native_bytes, "storage_bytes": storage_bytes,
              "memory_bytes": native_bytes + plan_memory_bytes, "plan_memory_bytes": plan_memory_bytes,
              "plan_memory_limit_bytes": PLAN_MATERIALIZATION_LIMIT_BYTES, "materialized_event_count": len(events),
              "detector_count": channels, "stream_count": streams,
              "aggregate_rate_hz": streams * s.hf2li_rate_hz, "acquisition_s": acquisition_s,
              "reset_s": reset_s, "preparation_s": preparation_s, "tune_settle_s": tune_s,
              "timing_upload_s": upload_s, "restoration_s": restoration_s,
              "processing_s": processing_s, "total_s": total_s,
              "forward_simulation": simulation_summary,
              "estimate_basis": "Explicit event bursts include probe-only warmup, one retained event, impulse tail and terminal; conservative additional reset per pump, blank/preliminary, tuning, acknowledged upload, restoration and analysis. Replace illustrative timing with retained measurements; operator physical actions are unbounded."}
    return Plan(s, tuple(events), tuple(dict.fromkeys(errors)), tuple(dict.fromkeys(readiness)), tuple(warnings), budget, timing.to_dict() if timing else {})
