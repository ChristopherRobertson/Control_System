"""Offline checks for one pumped CH1 timing rehearsal; no hardware or promotion."""
from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np

from control_app.workflows.phase_scan_data import DETECTOR_INPUT, SINGLE_DETECTOR_MODE, write_json
from control_app.workflows.phase_scan_native import demodulator_samples, sweep_interval_observations
from control_app.workflows.single_detector_marker_identity import controller_marker_identity
from control_app.workflows.single_detector_timing_analysis import _actual_rate, _gaps, _seconds


ANALYSIS_VERSION = "single-pump-timing-rehearsal/1.0"


def _decode(record, summary):
    if (record.get("record_kind") != "pump_timing_rehearsal" or
            record.get("record_role") != "single_pump_timing_rehearsal" or
            record.get("pump_timing_rehearsal") is not True):
        raise ValueError("An explicit single_pump_timing_rehearsal record is required")
    if record.get("detector_mode") != SINGLE_DETECTOR_MODE or record.get("detector_input") != DETECTOR_INPUT:
        raise ValueError("The timing rehearsal requires HF2LI CH1 SIG IN + single-detector data")
    clock = float(record["clockbase_hz"])
    if not math.isfinite(clock) or clock <= 0:
        raise ValueError("Invalid HF2LI clockbase")
    cutoff = record.get("pre_process_last_timing_tick")
    if not isinstance(cutoff, (int, np.integer)):
        raise ValueError("The pre-process native timing cutoff is missing")
    cutoff = int(cutoff)
    timing, sample = demodulator_samples(record, 2), demodulator_samples(record, 0)
    ticks, sample_ticks = timing["timestamp"], sample["timestamp"]
    if any(not np.issubdtype(data["timestamp"].dtype, np.integer) for data in (timing, sample)):
        raise ValueError("Native timestamps must retain integer precision")
    if not int(ticks[0]) <= cutoff < int(ticks[-1]):
        raise ValueError("The pre-process cutoff lies outside the native timing stream")
    words = np.asarray(timing["dio"])
    if (words.dtype.kind not in "uif" or not np.isfinite(words).all() or
            np.any(words < 0) or np.any(words > np.iinfo(np.uint32).max) or np.any(words != np.floor(words))):
        raise ValueError("DIO words must be exact uint32 values")
    dio = words.astype(np.uint32)
    timing_rate, sample_rate = _actual_rate(record, 2), _actual_rate(record, 0)
    timing_gaps, sample_gaps = _gaps(ticks, clock, timing_rate), _gaps(sample_ticks, clock, sample_rate)
    pump_high = (dio & (1 << 17)) != 0
    rises = np.flatnonzero(~pump_high[:-1] & pump_high[1:]) + 1
    falls = np.flatnonzero(pump_high[:-1] & ~pump_high[1:]) + 1
    baseline = pump_high[ticks <= cutoff]
    baseline_stable = len(baseline) >= 2 and bool(np.all(baseline == baseline[0]))
    rising_ticks, falling_ticks = [int(t) for t in ticks[rises]], [int(t) for t in ticks[falls]]
    pulse_pairs = [(fall, next((rise for rise in rising_ticks if rise > fall), None)) for fall in falling_ticks]
    complete_pulses = [(fall, rise) for fall, rise in pulse_pairs if rise is not None]
    summary.update(
        clockbase_hz=clock, pre_process_last_timing_tick=cutoff,
        timing_actual_rate_sps=timing_rate, detector_actual_rate_sps=sample_rate,
        timing_sample_interval_s=1/timing_rate, detector_sample_interval_s=1/sample_rate,
        pump_sync_baseline_stable=baseline_stable, pump_sync_baseline_sample_count=len(baseline),
        pump_sync_baseline_high=bool(baseline[0]) if baseline_stable else None,
        pump_sync_initial_high=bool(pump_high[0]), pump_sync_final_high=bool(pump_high[-1]),
        pump_sync_rising_ticks=rising_ticks, pump_sync_falling_ticks=falling_ticks,
        pump_sync_transition_count=len(rises)+len(falls), complete_low_excursion_count=len(complete_pulses),
        pump_sync_low_intervals_ticks=[[a, b] for a, b in complete_pulses],
        pump_sync_low_widths_s=[(b-a)/clock for a, b in complete_pulses],
    )
    reasons = summary["unusable_reasons"]
    if not baseline_stable or not bool(baseline[0]):
        reasons.append("A stable HIGH pre-trigger DIO17 baseline is required by the observed electrical-sync convention")
    if not bool(pump_high[-1]):
        reasons.append("DIO17 has not returned HIGH at capture end")
    pulse_ok = (len(falls) == len(rises) == 1 and cutoff < falling_ticks[0] < rising_ticks[0])
    if not pulse_ok:
        reasons.append("Expected exactly one complete post-cutoff DIO17 HIGH-LOW-HIGH excursion with one falling and one rising edge")
    sync_tick = rising_ticks[0] if len(rising_ticks) == 1 else None
    summary["chosen_pump_sync_rising_tick"] = sync_tick
    if pulse_ok:
        width = (rising_ticks[0]-falling_ticks[0])/clock
        summary["pump_sync_low_width_sampling_bounds_s"] = [max(0., width-1/timing_rate), width+1/timing_rate]
    intervals, marker_bearing, observed_markers = sweep_interval_observations(ticks, dio)
    candidates = [pair for pair in marker_bearing if pair[0] > cutoff]
    summary.update(observed_dio21_intervals=[list(pair) for pair in intervals],
                   observed_marker_ticks=[int(t) for t in observed_markers],
                   post_cutoff_marker_bearing_interval_count=len(candidates))
    if len(candidates) != 1:
        raise ValueError(f"Expected exactly one post-cutoff marker-bearing DIO21 sweep; observed {len(candidates)}")
    start, stop = candidates[0]
    markers = observed_markers[(observed_markers >= start) & (observed_markers <= stop)]
    summary.update(sweep_active_ticks=[start, stop], sweep_duration_s=(stop-start)/clock,
                   marker_ticks=[int(t) for t in markers], markers_observed=len(markers),
                   ancillary_dio21_intervals=[list(pair) for pair in intervals if pair != (start, stop)])
    if bool(dio[-1] & (1 << 21)):
        reasons.append("DIO21 is still HIGH at capture end; an incomplete sweep remains")
    profile = record["scan_profile"]
    nominal_duration = float(profile.get("nominal_sweep_duration_s") or
                             abs(float(profile["stop_cm1"])-float(profile["start_cm1"]))/float(profile["scan_rate_cm1_s"]))
    bounds = np.asarray(profile.get("sweep_duration_bounds_s", [.5*nominal_duration, 1.5*nominal_duration]), dtype=float)
    if bounds.shape != (2,) or not np.isfinite(bounds).all() or not 0 < bounds[0] < bounds[1]:
        raise ValueError("Invalid engineering sweep-duration bounds")
    summary["sweep_duration_engineering_bounds_s"] = bounds.tolist()
    if not bounds[0] <= (stop-start)/clock <= bounds[1]:
        reasons.append("Sweep duration is outside the declared engineering bounds")
    if len(markers) != 21 or profile.get("expected_markers") != 21:
        reasons.append("The wide timing rehearsal requires exactly 21 configured and observed controller markers")
    if np.count_nonzero(observed_markers > cutoff) != len(markers):
        reasons.append("Unexpected post-cutoff wavelength-marker edges occur outside the selected sweep")
    identity = controller_marker_identity(record, len(markers))
    if identity is None:
        reasons.append("Verified per-channel controller marker readbacks are required")
    else:
        summary.update(wavenumber_basis="controller_markers", marker_wavenumbers_cm1=identity["wavenumbers_cm1"],
                       marker_identity_basis=identity["marker_identity_basis"])
    selected = (sample_ticks >= start) & (sample_ticks <= stop)
    magnitude = np.hypot(sample["x"], sample["y"])
    selected_r = magnitude[selected]
    summary.update(native_sample_count=len(sample_ticks), sample_count=len(selected_r),
                   nonfinite_sample_count=int(np.count_nonzero(~np.isfinite(selected_r))),
                   nonpositive_sample_count=int(np.count_nonzero(np.isfinite(selected_r) & (selected_r <= 0))))
    if len(selected_r) < 2 or not np.all(np.isfinite(selected_r) & (selected_r > 0)):
        reasons.append("Every CH1 sample in the sweep must be finite and positive, with at least two samples")
    if len(selected_r):
        leading = (int(sample_ticks[selected][0])-start)/clock
        trailing = (stop-int(sample_ticks[selected][-1]))/clock
        summary.update(leading_gap_s=leading, trailing_gap_s=trailing)
        if leading > 1.75/sample_rate or trailing > 1.75/sample_rate:
            reasons.append("CH1 observations do not cover both sweep boundaries")
    # Start at the saved cutoff before the pump edge; include straddling gaps,
    # the complete pulse, every marker, and the final Sweep Active falling edge.
    guard_stop = max(stop, sync_tick or stop)
    timing_overlap = (ticks[:-1] < guard_stop) & (ticks[1:] > cutoff)
    sample_overlap = (sample_ticks[:-1] < guard_stop) & (sample_ticks[1:] > cutoff)
    timing_gap_count = int(np.count_nonzero(timing_gaps & timing_overlap))
    sample_gap_count = int(np.count_nonzero(sample_gaps & sample_overlap))
    summary.update(continuity_interval_ticks=[cutoff, guard_stop], timing_gap_count=timing_gap_count,
                   detector_gap_count=sample_gap_count, timing_native_gap_count=int(timing_gaps.sum()),
                   detector_native_gap_count=int(sample_gaps.sum()))
    if timing_gap_count or sample_gap_count:
        reasons.append("Native sample gaps occur between the pre-pump cutoff and the completed sweep/pump observations")
    statuses = [entry.get("status", {}) for entry in record.get("hf2li_input_checks", [])]
    if not statuses:
        statuses = [entry.get("hf2li_input_status", {}) for entry in record.get("scan_status_observations", [])]
    clips = [status.get("status/flags/adcclip/0") for status in statuses]
    unknown = sum(not isinstance(value, (int, np.integer)) for value in clips)
    clipped = sum(isinstance(value, (int, np.integer)) and value != 0 for value in clips)
    summary.update(clip_check_count=len(clips), clipped_check_count=int(clipped), clipping_read_error_count=unknown)
    if clipped:
        reasons.append("CH1 clipping was observed")
    if not clips or unknown:
        reasons.append("CH1 clipping status is unavailable")
    if record.get("capture_completed") is not True or record.get("optical_valid") is not True:
        reasons.append("Capture completion and safe shutdown were not verified")
    if record.get("pump_events") != 1:
        reasons.append("Acquisition did not report exactly one completed electrical pump-sync event")
    event = record.get("event", {})
    phase_us = event.get("phase_delay_us")
    if (event.get("pump_enabled") is not True or not isinstance(phase_us, (int, float)) or
            not math.isfinite(phase_us)):
        raise ValueError("A finite programmed phase and pumped event record are required")
    summary["programmed_phase_us"] = phase_us
    if sync_tick is not None:
        marker_age = _seconds(markers, sync_tick, clock)
        offsets = marker_age-float(phase_us)*1e-6
        summary.update(marker_age_from_sync_rise_s=marker_age.tolist(),
                       marker_minus_sync_minus_programmed_phase_s=offsets.tolist(),
                       sweep_start_minus_sync_minus_programmed_phase_s=(start-sync_tick)/clock-float(phase_us)*1e-6)
        if not reasons:
            step, margin, target = 50e-6, 1/timing_rate, (-.001, .005)
            first_unrounded = target[0]-float(np.max(offsets))-margin
            last_unrounded = target[1]-float(np.min(offsets))+margin
            first_tick, last_tick = math.floor(first_unrounded/step), math.ceil(last_unrounded/step)
            summary["phase_coverage_proposal"] = {
                "basis": "one_shot_controller_marker_times_relative_to_electrical_sync_rising",
                "observation_window_s": list(target), "phase_increment_us": 50.,
                "quantization_margin_s_each_direction": margin,
                "marker_time_residual_bounds_s": [float(np.min(offsets)), float(np.max(offsets))],
                "unrounded_phase_bounds_s": [first_unrounded, last_unrounded],
                "first_phase_us": first_tick*50., "last_phase_us": last_tick*50.,
                "phase_count": last_tick-first_tick+1,
                "common_age_bounds_s_after_margin": [first_tick*step+float(np.max(offsets))+margin,
                                                     last_tick*step+float(np.min(offsets))-margin],
                "application_settings_modified": False, "calibration_established": False,
                "limitation": "One shot does not characterize jitter, drift, optical pump arrival, or lock-in response; the sampling margin is not a measured jitter allowance.",
            }
    summary["plot_origin_tick"] = sync_tick if sync_tick is not None else cutoff
    summary["plot_time_basis"] = "electrical_sync_rising" if sync_tick is not None else "pre_process_cutoff_diagnostic"
    return timing, sample, magnitude, timing_gaps, sample_gaps


def _write_csv(path, decoded, summary):
    timing, sample, magnitude, timing_gaps, sample_gaps = decoded
    origin, clock = summary["plot_origin_tick"], summary["clockbase_hz"]
    start, stop = summary["sweep_active_ticks"]
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["stream", "timestamp_ticks", "time_from_origin_s", "time_basis", "CH1_x_V", "CH1_y_V", "CH1_R_V",
                         "DIO17", "DIO21", "DIO22", "inside_sweep", "native_gap_before"])
        for name, data, gaps in (("sample_demod0", sample, sample_gaps), ("timing_demod2", timing, timing_gaps)):
            for i, tick in enumerate(data["timestamp"]):
                values = [data["x"][i], data["y"][i], magnitude[i]] if name == "sample_demod0" else ["", "", ""]
                word = int(data["dio"][i])
                writer.writerow([name, int(tick), (int(tick)-origin)/clock, summary["plot_time_basis"], *values,
                                 *[int(bool(word & (1 << bit))) for bit in (17, 21, 22)],
                                 start <= int(tick) <= stop, bool(i and gaps[i-1])])


def _plot(path, decoded, summary):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    timing, sample, magnitude, timing_gaps, sample_gaps = decoded
    origin, clock = summary["plot_origin_tick"], summary["clockbase_hz"]
    sample_ms, timing_ms = _seconds(sample["timestamp"], origin, clock)*1000, _seconds(timing["timestamp"], origin, clock)*1000
    start, stop = [(tick-origin)/clock*1000 for tick in summary["sweep_active_ticks"]]
    left, right = min(start, 0.)-.2, max(stop, 0.)+.2
    sample_window = (sample_ms >= left) & (sample_ms <= right)
    timing_window = (timing_ms >= left) & (timing_ms <= right)
    figure = Figure(figsize=(10, 8), constrained_layout=True)
    FigureCanvasAgg(figure)
    axes = figure.subplots(3, 1, gridspec_kw={"height_ratios": [2, 2, 1.2]})
    values = magnitude.copy()
    values[np.r_[False, sample_gaps]] = np.nan
    axes[0].plot(sample_ms[sample_window], values[sample_window], linewidth=.8, color="#247aa6")
    axes[0].set(ylabel="CH1 lock-in R (V)")
    dio = timing["dio"].astype(np.uint32)
    for bit, offset, label in ((21, 0., "DIO21 Sweep Active"), (22, 1.5, "DIO22 wavelength marker"), (17, 3., "DIO17 electrical pump sync")):
        levels = ((dio & (1 << bit)) != 0).astype(float)+offset
        levels[np.r_[False, timing_gaps]] = np.nan
        axes[1].step(timing_ms[timing_window], levels[timing_window], where="post", linewidth=.8, label=label)
    axes[1].legend(loc="upper right", fontsize=8)
    axes[1].set(ylabel="Digital level + display offset", xlabel="Time from electrical sync rising edge (ms)")
    for axis in axes[:2]:
        axis.set_xlim(left, right)
        axis.axvline(0, color="gray", linestyle=":", linewidth=.8)
        axis.grid(alpha=.2)
    zoom = np.abs(timing_ms) <= .05
    axes[2].step(timing_ms[zoom]*1000, ((dio[zoom] & (1 << 17)) != 0).astype(float), where="post", linewidth=1.)
    axes[2].set(xlim=(-50, 50), ylim=(-.15, 1.15), yticks=[0, 1], ylabel="DIO17", xlabel="Electrical sync detail (µs; rising edge = 0)")
    axes[2].axvline(0, color="gray", linestyle=":", linewidth=.8)
    axes[2].grid(alpha=.2)
    figure.suptitle(f"One-pump timing rehearsal · {summary['status']}\nElectrical sync rising edge; optical pump arrival is unverified")
    if summary["plot_time_basis"] != "electrical_sync_rising":
        axes[1].set_xlabel("Time from pre-process cutoff (ms; no unique sync rising edge)")
        axes[2].set_xlabel("Pre-process cutoff detail (µs; diagnostic origin)")
    with path.open("xb") as handle:
        figure.savefig(handle, format="png", dpi=150)


def analyze_single_pump_timing_rehearsal(directory, record):
    """Save timing observations only after the complete native file is preserved."""
    directory = Path(directory).resolve()
    native_path = directory / "hf2li_native.npz"
    if not native_path.is_file():
        raise FileNotFoundError("Preserve complete hf2li_native.npz before offline timing analysis")
    json_path, csv_path, plot_path = [directory / f"pump_timing_analysis.{ext}" for ext in ("json", "csv", "png")]
    if any(path.exists() for path in (json_path, csv_path, plot_path)):
        raise FileExistsError("Pump timing artifacts already exist; preserve them")
    summary = {
        "analysis_version": ANALYSIS_VERSION, "native_source": "hf2li_native.npz",
        "record_kind": record.get("record_kind"), "record_role": record.get("record_role"),
        "run_classification": "EXPLORATORY_PROOF_OF_CONCEPT", "publication_eligible": False,
        "usable_for_timing": False, "usable_for_ratio": False, "usable_as_background": False,
        "spectral_analysis_allowed": False, "trajectory_promoted": False,
        "provisional": True, "independently_calibrated": False,
        "pump_time_basis": "electrical_sync", "pump_reference_edge": "rising_return_to_idle",
        "optical_pump_arrival_verified": False, "phase_coverage_proposal": None,
        "unusable_reasons": [], "warnings": list(record.get("warnings", [])) + [
            "DIO17 rising is the return-to-idle electrical sync convention; neither this edge nor the falling edge establishes optical arrival at the sample.",
            "Controller-marker coordinates are not independently calibrated wavelengths.",
            "Native edge timing is quantized by the measured timing sample interval; integer clock ticks do not remove sampling uncertainty.",
            "A single shot cannot establish jitter, drift, optical time zero, or lock-in impulse response; proposed phase bounds are not promoted application settings.",
        ],
    }
    try:
        decoded = _decode(record, summary)
    except (ValueError, KeyError, TypeError, IndexError, OverflowError) as exc:
        summary["unusable_reasons"].append(str(exc))
        summary["status"] = "UNUSABLE"
        write_json(json_path, summary)
        return summary
    summary["usable_for_timing"] = not summary["unusable_reasons"]
    summary["status"] = "USABLE_TIMING_REHEARSAL" if summary["usable_for_timing"] else "UNUSABLE"
    _write_csv(csv_path, decoded, summary)
    _plot(plot_path, decoded, summary)
    summary.update(csv_path=str(csv_path), plot_path=str(plot_path))
    write_json(json_path, summary)
    return summary
