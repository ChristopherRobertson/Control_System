"""Offline observations for one unpumped CH1 timing rehearsal.

No wavelength coordinates, pump delays, calibration, or promoted trajectories
are produced. The caller must preserve the complete native record first.
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from control_app.workflows.phase_scan_data import DETECTOR_INPUT, SINGLE_DETECTOR_MODE, write_json
from control_app.workflows.phase_scan_native import demodulator_samples, sweep_interval_observations


ANALYSIS_VERSION = "single-detector-timing-rehearsal/1.0"


def _seconds(ticks, origin, clock):
    # Subtract integer ticks before converting, including timestamps above 2**53.
    return np.asarray([(int(tick) - int(origin)) / clock for tick in ticks])


def _actual_rate(record, index):
    for path, entry in record.get("hf2li_detector_settings", {}).items():
        if str(path).lower().endswith(f"/demods/{index}/rate"):
            value = entry.get("value") if isinstance(entry, dict) else entry
            if isinstance(value, (int, float)) and np.isfinite(value) and value > 0:
                return float(value)
    raise ValueError(f"Actual HF2LI demodulator {index} sample-rate readback is missing or invalid")


def _gaps(ticks, clock, rate):
    spacing = np.asarray([(int(b) - int(a)) / clock for a, b in zip(ticks[:-1], ticks[1:])])
    return spacing > 1.75 / rate


def _decode(record, summary):
    if record.get("record_kind") != "timing_rehearsal" or record.get("record_role") != "pump_off_timing_rehearsal":
        raise ValueError("An explicit pump_off_timing_rehearsal record with timing_rehearsal kind is required")
    if record.get("detector_mode") != SINGLE_DETECTOR_MODE or record.get("detector_input") != DETECTOR_INPUT:
        raise ValueError("The timing rehearsal requires HF2LI CH1 SIG IN + single-detector data")
    clock = float(record["clockbase_hz"])
    if not np.isfinite(clock) or clock <= 0:
        raise ValueError("Invalid HF2LI clockbase")
    cutoff = record.get("pre_process_last_timing_tick")
    if not isinstance(cutoff, (int, np.integer)):
        raise ValueError("The pre-process native timing cutoff is missing")
    cutoff = int(cutoff)
    profile = record["scan_profile"]
    bounds = np.asarray(profile.get("sweep_duration_bounds_s", []), dtype=float)
    if bounds.shape != (2,) or not np.isfinite(bounds).all() or not 0 < bounds[0] < bounds[1]:
        raise ValueError("Explicit positive engineering sweep-duration bounds are required")
    timing = demodulator_samples(record, 2)
    sample = demodulator_samples(record, 0)
    ticks, dio = timing["timestamp"], timing["dio"].astype(np.uint32)
    if not int(ticks[0]) <= cutoff < int(ticks[-1]):
        raise ValueError("The pre-process timing cutoff is outside the preserved timing stream")
    intervals, marker_bearing, observed_markers = sweep_interval_observations(ticks, dio)
    candidates = [interval for interval in marker_bearing if interval[0] > cutoff]
    summary.update(clockbase_hz=clock, pre_process_last_timing_tick=cutoff,
                   sweep_duration_bounds_s=bounds.tolist(), duration_bounds_basis="predeclared_engineering_only",
                   observed_dio21_intervals=[list(pair) for pair in intervals],
                   post_cutoff_marker_bearing_interval_count=len(candidates),
                   observed_marker_ticks=[int(tick) for tick in observed_markers])
    if len(candidates) != 1:
        raise ValueError(f"Expected one complete post-cutoff marker-bearing DIO21 interval; observed {len(candidates)}")
    start, stop = candidates[0]
    duration_ticks = stop - start
    duration = duration_ticks / clock
    markers = observed_markers[(observed_markers >= start) & (observed_markers <= stop)]
    marker_offsets_ticks = [int(tick) - start for tick in markers]
    marker_spacing_ticks = [int(b) - int(a) for a, b in zip(markers[:-1], markers[1:])]
    sample_ticks = sample["timestamp"]
    selected_sample = (sample_ticks >= start) & (sample_ticks <= stop)
    if np.count_nonzero(selected_sample) < 2:
        raise ValueError("Fewer than two native CH1 samples lie inside the selected sweep")
    sample_rate, timing_rate = _actual_rate(record, 0), _actual_rate(record, 2)
    sample_gaps = _gaps(sample_ticks, clock, sample_rate)
    timing_gaps = _gaps(ticks, clock, timing_rate)
    # Include gaps that straddle a sweep edge; selecting only interior samples
    # would hide a missing leading or trailing observation.
    sample_overlap = (sample_ticks[:-1] < stop) & (sample_ticks[1:] > start)
    timing_overlap = (ticks[:-1] < stop) & (ticks[1:] > start)
    detector_gap_count = int(np.count_nonzero(sample_gaps & sample_overlap))
    timing_gap_count = int(np.count_nonzero(timing_gaps & timing_overlap))
    magnitude = np.hypot(sample["x"], sample["y"])
    finite = np.isfinite(magnitude[selected_sample])
    statuses = [entry.get("status", {}) for entry in record.get("hf2li_input_checks", [])]
    if not statuses:
        statuses = [entry.get("hf2li_input_status", {}) for entry in record.get("scan_status_observations", [])]
    clips = [status.get("status/flags/adcclip/0") for status in statuses]
    unknown_clips = sum(not isinstance(value, (int, np.integer)) for value in clips)
    clipped = sum(isinstance(value, (int, np.integer)) and value != 0 for value in clips)
    pump_levels = (dio & (1 << 17)) != 0
    rises = np.flatnonzero(~pump_levels[:-1] & pump_levels[1:]) + 1
    falls = np.flatnonzero(pump_levels[:-1] & ~pump_levels[1:]) + 1
    baseline = pump_levels[ticks <= cutoff]
    stable_baseline = len(baseline) >= 2 and bool(np.all(baseline == baseline[0]))
    selected_ticks = sample_ticks[selected_sample]
    leading_gap = (int(selected_ticks[0]) - start) / clock
    trailing_gap = (stop - int(selected_ticks[-1])) / clock
    summary.update(
        sweep_active_ticks=[start, stop], sweep_duration_ticks=duration_ticks, sweep_duration_s=duration,
        marker_ticks=[int(tick) for tick in markers], marker_offset_ticks=marker_offsets_ticks,
        marker_offsets_s=[value / clock for value in marker_offsets_ticks],
        marker_spacing_ticks=marker_spacing_ticks, marker_spacing_s=[value / clock for value in marker_spacing_ticks],
        markers_observed=len(markers), markers_expected=profile.get("expected_markers"),
        ancillary_dio21_intervals=[list(pair) for pair in intervals if pair != (start, stop)],
        detector_actual_rate_sps=sample_rate, timing_actual_rate_sps=timing_rate,
        detector_sample_interval_s=1 / sample_rate, timing_sample_interval_s=1 / timing_rate,
        native_sample_count=len(sample_ticks), sample_count=int(np.count_nonzero(selected_sample)),
        nonfinite_sample_count=int(np.count_nonzero(~finite)),
        nonpositive_sample_count=int(np.count_nonzero(magnitude[selected_sample] <= 0)),
        detector_gap_count=detector_gap_count, timing_gap_count=timing_gap_count,
        detector_native_gap_count=int(np.count_nonzero(sample_gaps)),
        timing_native_gap_count=int(np.count_nonzero(timing_gaps)),
        leading_gap_s=leading_gap, trailing_gap_s=trailing_gap,
        clip_check_count=len(clips), clipped_check_count=int(clipped), clipping_read_error_count=int(unknown_clips),
        pump_sync_baseline_stable=stable_baseline, pump_sync_baseline_sample_count=len(baseline),
        pump_sync_baseline_high=bool(baseline[0]) if stable_baseline else None,
        pump_sync_rising_ticks=[int(tick) for tick in ticks[rises]],
        pump_sync_falling_ticks=[int(tick) for tick in ticks[falls]],
        pump_sync_transition_count=len(rises) + len(falls),
        pump_outputs_disabled_readback_verified=record.get("pump_outputs_disabled_readback_verified", False),
    )
    reasons = summary["unusable_reasons"]
    if not record.get("capture_completed") or not record.get("optical_valid"):
        reasons.append("Capture completion and safe shutdown were not verified")
    if not bounds[0] <= duration <= bounds[1]:
        reasons.append("Observed sweep duration is outside the predeclared engineering bounds")
    if bool(dio[-1] & (1 << 21)):
        reasons.append("A post-cutoff DIO21 high interval is incomplete at capture end")
    expected = profile.get("expected_markers")
    if expected is not None and (not isinstance(expected, (int, np.integer)) or len(markers) != expected):
        reasons.append("Observed marker count differs from the configured count; completeness is unresolved")
    if not stable_baseline:
        reasons.append("A stable pre-trigger DIO17 baseline could not be established")
    if len(rises) or len(falls):
        reasons.append("DIO17 changed level during the unpumped record; pump sync activity is unresolved")
    if record.get("pump_events") != 0:
        reasons.append("An unpumped record is required; pump event status is nonzero or unresolved")
    if record.get("pump_outputs_disabled_readback_verified") is not True:
        reasons.append("Disabled pump timing outputs were not verified")
    if clipped:
        reasons.append("CH1 clipping was observed")
    if not clips or unknown_clips:
        reasons.append("CH1 clipping status is unavailable for one or more checks")
    if timing_gap_count or detector_gap_count:
        reasons.append("Native sample gaps overlap the sweep; timing or detector observations may be missing")
    if not finite.all():
        reasons.append("CH1 contains nonfinite samples inside the sweep")
    if leading_gap > 1.75 / sample_rate or trailing_gap > 1.75 / sample_rate:
        reasons.append("CH1 native samples do not cover both observed sweep boundaries")
    if summary["detector_native_gap_count"] or summary["timing_native_gap_count"]:
        summary["warnings"].append("Native gaps are retained and reported; DIO17 activity cannot be excluded inside a gap")
    return timing, sample, timing_gaps, sample_gaps, magnitude


def _write_waveforms(path, decoded, summary):
    timing, sample, timing_gaps, sample_gaps, magnitude = decoded
    start, stop = summary["sweep_active_ticks"]
    clock = summary["clockbase_hz"]
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["stream", "timestamp_ticks", "time_from_sweep_active_s", "CH1_x_V", "CH1_y_V", "CH1_R_V",
                         "DIO21", "DIO22", "DIO17", "inside_sweep", "native_gap_before"])
        for label, data, gaps in (("sample_demod0", sample, sample_gaps), ("timing_demod2", timing, timing_gaps)):
            for index, tick in enumerate(data["timestamp"]):
                bits = int(data["dio"][index])
                values = [data["x"][index], data["y"][index], magnitude[index]] if label == "sample_demod0" else ["", "", ""]
                writer.writerow([label, int(tick), (int(tick) - start) / clock, *values,
                                 int(bool(bits & (1 << 21))), int(bool(bits & (1 << 22))), int(bool(bits & (1 << 17))),
                                 start <= int(tick) <= stop, bool(index and gaps[index - 1])])


def _plot(path, decoded, summary):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    timing, sample, timing_gaps, sample_gaps, magnitude = decoded
    start, stop = summary["sweep_active_ticks"]
    clock = summary["clockbase_hz"]
    duration = summary["sweep_duration_s"]
    figure = Figure(figsize=(10, 7), constrained_layout=True)
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 1, sharex=True)
    values = np.asarray(magnitude, dtype=float).copy()
    values[np.r_[False, sample_gaps]] = np.nan
    sample_ms = _seconds(sample["timestamp"], start, clock) * 1e3
    timing_ms = _seconds(timing["timestamp"], start, clock) * 1e3
    duration_ms = duration * 1e3
    limits = (-.2 * duration_ms, 1.2 * duration_ms)
    sample_window = (sample_ms >= limits[0]) & (sample_ms <= limits[1])
    timing_window = (timing_ms >= limits[0]) & (timing_ms <= limits[1])
    axes[0].plot(sample_ms[sample_window], values[sample_window], color="#247aa6", linewidth=.9)
    axes[0].set(ylabel="CH1 lock-in R (V)")
    dio = timing["dio"].astype(np.uint32)
    for bit, offset, label in ((21, 0, "DIO21 Sweep Active"), (22, 1.5, "DIO22 marker"), (17, 3, "DIO17 pump sync")):
        levels = ((dio & (1 << bit)) != 0).astype(float) + offset
        levels[np.r_[False, timing_gaps]] = np.nan
        axes[1].step(timing_ms[timing_window], levels[timing_window], where="post", linewidth=.9, label=label)
    axes[1].set(xlabel="Time from observed Sweep Active rising edge (ms)", ylabel="DIO levels (offset for display)")
    axes[1].legend(loc="upper right", fontsize=8)
    for axis in axes:
        axis.set_xlim(*limits)
        axis.axvline(0, color="gray", linestyle=":", linewidth=.7)
        axis.axvline(duration * 1e3, color="gray", linestyle=":", linewidth=.7)
        axis.grid(alpha=.2)
    figure.suptitle(f"Pump-off single-detector timing rehearsal · {summary['status']}\nObserved time only · no wavelength or process-trigger latency assignment")
    with path.open("xb") as handle:
        figure.savefig(handle, format="png", dpi=140)


def analyze_single_detector_timing_rehearsal(directory, record):
    """Create non-overwriting timing observations from an already saved record."""
    directory = Path(directory).resolve()
    native_path = directory / "hf2li_native.npz"
    if not native_path.is_file():
        raise FileNotFoundError("Preserve the complete hf2li_native.npz before offline analysis")
    json_path, csv_path, plot_path = [directory / f"timing_analysis.{extension}" for extension in ("json", "csv", "png")]
    if any(path.exists() for path in (json_path, csv_path, plot_path)):
        raise FileExistsError("Timing analysis artifacts already exist; preserve them")
    summary = {
        "analysis_version": ANALYSIS_VERSION, "native_source": str(native_path),
        "record_kind": record.get("record_kind"), "record_role": record.get("record_role"),
        "detector_mode": record.get("detector_mode"), "detector_input": record.get("detector_input"),
        "run_classification": "EXPLORATORY_PROOF_OF_CONCEPT", "publication_eligible": False,
        "usable_for_ratio": False, "usable_as_background": False, "spectral_analysis_allowed": False,
        "usable_for_timing_rehearsal": False, "wavenumber_assignment": None, "trajectory_promoted": False,
        "time_basis": "native_HF2LI_ticks_relative_to_observed_Sweep_Active_rise",
        "process_trigger_timestamp_recorded_in_HF2LI": False, "process_trigger_latency_s": None,
        "host_process_trigger_utc": record.get("process_trigger_utc"),
        "unusable_reasons": [], "warnings": list(record.get("warnings", [])) + [
            "No process-trigger edge timestamp is recorded in the HF2LI timebase; host UTC and the pre-process cutoff do not establish process-trigger latency.",
            "Marker ticks and spacing are observations only; marker count does not identify wavelengths or establish a calibrated trajectory.",
            "Sweep-duration bounds are predeclared engineering checks, not metrological acceptance limits.",
            "Observed digital edges are sample-quantized; native ticks do not remove edge sampling uncertainty or qualify optical timing/filter response.",
            "A stable DIO17 idle level and disabled pump timing outputs do not independently establish the absence of optical pump light.",
        ],
    }
    try:
        decoded = _decode(record, summary)
    except (ValueError, KeyError, TypeError, IndexError, OverflowError) as exc:
        summary["unusable_reasons"].append(str(exc))
        summary["status"] = "UNUSABLE"
        write_json(json_path, summary)
        return summary
    summary["usable_for_timing_rehearsal"] = not summary["unusable_reasons"]
    summary["status"] = "USABLE_TIMING_REHEARSAL" if summary["usable_for_timing_rehearsal"] else "UNUSABLE"
    _write_waveforms(csv_path, decoded, summary)
    _plot(plot_path, decoded, summary)
    summary.update(csv_path=str(csv_path), plot_path=str(plot_path))
    write_json(json_path, summary)
    return summary
