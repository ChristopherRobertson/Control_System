"""Offline products for a retained, unpumped CH1 scan; never operate hardware.

The complete polling record remains in its source hf2li_native.npz. Controller
marker coordinates require verified per-channel readbacks and remain distinct
from independently calibrated wavelengths. Count alone does not assign markers.
"""
from __future__ import annotations

from control_app.paths import research_output_path

import csv
import os
from pathlib import Path

import numpy as np

from control_app.workflows.phase_scan_data import (
    DETECTOR_INPUT, SINGLE_DETECTOR_MODE, Spectrum, interpolate_supported, save_native, write_json,
)
from control_app.workflows.phase_scan_native import demodulator_samples, sweep_interval_observations
from control_app.workflows.single_detector_marker_identity import controller_marker_identity

ANALYSIS_VERSION = "single-detector-scan/1.2"


def _seconds(ticks, origin, clock):
    return np.asarray([(int(tick)-int(origin))/clock for tick in ticks])


def _gap_count(ticks, clock, rate):
    spacing = np.diff(ticks).astype(float)/clock
    nominal = 1./rate if rate > 0 else float(np.median(spacing))
    gaps = spacing > nominal*1.75
    return int(np.count_nonzero(gaps)), gaps, nominal


def _readback_rate(record, index):
    """Use the quantized device readback, never a nominal requested rate."""
    suffix = f"/demods/{index}/rate"
    for path, entry in record.get("hf2li_detector_settings", {}).items():
        if str(path).lower().endswith(suffix):
            value = entry.get("value") if isinstance(entry, dict) else entry
            if isinstance(value, (int, float)) and np.isfinite(value) and value > 0:
                return float(value)
    return 0.  # _gap_count then uses the median observed native tick spacing.


def _decode(record, summary):
    if record.get("detector_mode") != SINGLE_DETECTOR_MODE:
        raise ValueError("An explicitly declared single CH1 record is required")
    if record.get("detector_input", DETECTOR_INPUT) != DETECTOR_INPUT:
        raise ValueError("The detector must be HF2LI CH1 SIG IN +")
    profile = record["scan_profile"]
    clock = float(record["clockbase_hz"])
    if not np.isfinite(clock) or clock <= 0:
        raise ValueError("A positive finite measured HF2LI clockbase is required")
    timing = demodulator_samples(record, 2)
    ticks, dio = timing["timestamp"], timing["dio"].astype(np.uint32)
    intervals, marker_bearing, observed = sweep_interval_observations(ticks, dio)
    summary["observed_sweep_active_intervals"] = [list(pair) for pair in intervals]
    cutoff = record.get("pre_process_last_timing_tick")
    candidates = [interval for interval in marker_bearing if cutoff is None or interval[0] > int(cutoff)]
    summary["pre_process_last_timing_tick"] = None if cutoff is None else int(cutoff)
    summary["observed_complete_sweeps"] = len(candidates)
    summary["observed_complete_dio21_intervals"] = len(intervals)
    if len(candidates) != 1:
        raise ValueError(f"Expected exactly one post-trigger marker-bearing Sweep Active interval; found {len(candidates)}")
    if (cutoff is None and bool(dio[0] & (1 << 21))) or bool(dio[-1] & (1 << 21)):
        raise ValueError("Polling record contains an incomplete Sweep Active interval")
    start, stop = candidates[0]
    ancillary = [interval for interval in intervals if interval != candidates[0]]
    summary["ancillary_dio21_intervals_ignored"] = [list(interval) for interval in ancillary]
    if ancillary:
        summary["warnings"].append(f"Ignored {len(ancillary)} ancillary or pre-trigger DIO21 interval(s); all native intervals remain preserved")
    duration = (stop-start)/clock
    nominal_duration = float(profile.get("nominal_sweep_duration_s") or
                             abs(float(profile["stop_cm1"])-float(profile["start_cm1"]))/float(profile["scan_rate_cm1_s"]))
    if not np.isfinite(nominal_duration) or nominal_duration <= 0:
        raise ValueError("A positive finite nominal sweep duration is required")
    summary["duration_engineering_bounds_s"] = [.5*nominal_duration, 1.5*nominal_duration]
    summary["sweep_duration_s"] = duration
    if not .5*nominal_duration <= duration <= 1.5*nominal_duration:
        raise ValueError("Observed sweep duration is outside 0.5 to 1.5 times the requested duration; a process echo cannot supply a blank")
    markers = observed[(observed >= start) & (observed <= stop)]
    selected_timing = (ticks >= start) & (ticks <= stop)
    timing_gaps, _, _ = _gap_count(ticks[selected_timing], clock, _readback_rate(record, 2))
    sample = demodulator_samples(record, 0)
    selected = (sample["timestamp"] >= start) & (sample["timestamp"] <= stop)
    sample_ticks = sample["timestamp"][selected]
    if len(sample_ticks) < 2:
        raise ValueError("Fewer than two CH1 samples lie inside the observed sweep")
    seconds = _seconds(sample_ticks, start, clock)
    magnitude = np.hypot(sample["x"][selected], sample["y"][selected])
    positive = np.isfinite(magnitude) & (magnitude > 0)
    gap_count, gaps, sample_interval = _gap_count(sample_ticks, clock, _readback_rate(record, 0))
    statuses = [entry.get("status", {}) for entry in record.get("hf2li_input_checks", [])]
    if not statuses:
        statuses = [entry.get("hf2li_input_status", {}) for entry in record.get("scan_status_observations", [])]
    clips = [status.get("status/flags/adcclip/0") for status in statuses]
    unknown_clips = sum(not isinstance(value, (int, np.integer)) for value in clips)
    clipped = sum(isinstance(value, (int, np.integer)) and value != 0 for value in clips)
    pump_levels = (dio & (1 << 17)) != 0
    pump_high = int(np.count_nonzero(pump_levels))
    pump_transitions = int(np.count_nonzero(pump_levels[1:] != pump_levels[:-1]))
    baseline = pump_levels[ticks <= int(cutoff)] if cutoff is not None else pump_levels[ticks < start]
    stable_baseline = len(baseline) >= 2 and bool(np.all(baseline == baseline[0]))
    pump_baseline_high = bool(baseline[0]) if stable_baseline else None
    summary.update(
        sweep_active_ticks=[start, stop], sweep_duration_s=duration,
        marker_ticks=markers.tolist(), markers_observed=len(markers),
        markers_expected=profile.get("expected_markers"), timing_gap_count=timing_gaps,
        sample_count=len(magnitude), positive_sample_count=int(positive.sum()),
        nonfinite_sample_count=int(np.count_nonzero(~np.isfinite(magnitude))),
        nonpositive_sample_count=int(np.count_nonzero(np.isfinite(magnitude) & (magnitude <= 0))),
        detector_gap_count=gap_count, clip_check_count=len(clips), clipped_check_count=int(clipped),
        clipping_read_error_count=unknown_clips, pump_high_sample_count=pump_high,
        pump_sync_transition_count=pump_transitions, pump_sync_baseline_high=pump_baseline_high,
        pump_sync_baseline_sample_count=len(baseline), pump_sync_baseline_stable=stable_baseline,
        pump_outputs_disabled_readback_verified=record.get("pump_outputs_disabled_readback_verified", False),
        leading_gap_s=float(seconds[0]), trailing_gap_s=float(duration-seconds[-1]),
        detector_sample_interval_s=sample_interval,
    )
    reasons = summary["unusable_reasons"]
    warnings = summary["warnings"]
    if not record.get("optical_valid"):
        reasons.append("Capture completion and safe shutdown were not verified")
    if clipped:
        reasons.append("CH1 clipping was observed")
    if not clips or unknown_clips:
        reasons.append("CH1 clipping status is unavailable for one or more checks")
    if not stable_baseline:
        reasons.append("A stable pre-trigger DIO17 baseline could not be established")
    if pump_transitions:
        reasons.append("DIO17 changed level during the unpumped record; pump sync activity is unresolved")
    if record.get("pump_events") != 0:
        reasons.append("An unpumped scan is required; pump event status is nonzero or unresolved")
    if record.get("pump_outputs_disabled_readback_verified") is not True:
        reasons.append("Disabled pump timing outputs were not verified")
    warnings.append("DIO17 is checked for changes from its observed idle level; no transitions and disabled timing outputs do not independently verify absence of optical pump light")
    if int(positive.sum()) < 2:
        reasons.append("Fewer than two finite positive CH1 readings are available")
    if timing_gaps:
        reasons.append("Timing stream has gaps within the sweep; marker/edge observations may be missing")
    if gap_count or not positive.all():
        warnings.append("Invalid readings and detector gaps are unsupported; ratios must not interpolate across them")
    if summary["leading_gap_s"] > sample_interval*1.75 or summary["trailing_gap_s"] > sample_interval*1.75:
        warnings.append("Detector samples do not cover both observed sweep boundaries; no extrapolation is allowed")

    identified = record.get("marker_wavenumbers_cm1")
    identity_basis = record.get("marker_identity_basis")
    use_markers = identified is not None and bool(identity_basis) and len(markers) >= 2 and not timing_gaps
    if use_markers:
        identified = np.asarray(identified, dtype=float)
        use_markers = (identified.ndim == 1 and len(identified) == len(markers)
                       and np.isfinite(identified).all()
                       and (np.all(np.diff(identified) > 0) or np.all(np.diff(identified) < 0)))
    basis, trajectory = "measured", "independently_identified_markers"
    if not use_markers:
        controller_identity = controller_marker_identity(record, len(markers))
        if controller_identity is not None:
            if timing_gaps:
                raise ValueError("Controller-marker coordinates require a continuous timing stream")
            identified = np.asarray(controller_identity["wavenumbers_cm1"], dtype=float)
            identity_basis = controller_identity["marker_identity_basis"]
            basis, trajectory = "controller_markers", "observed_markers_with_controller_readback"
            use_markers = True
            warnings.append("Controller-marker wavenumbers use observed marker ticks and verified channel readbacks; independent absolute wavelength calibration is not established")
    if use_markers:
        selected_axis = (sample_ticks >= markers[0]) & (sample_ticks <= markers[-1])
        wn = interpolate_supported(_seconds(markers, start, clock), identified, seconds[selected_axis])
    else:
        selected_axis = np.ones(len(sample_ticks), dtype=bool)
        wn = float(profile["start_cm1"]) + (float(profile["stop_cm1"])-float(profile["start_cm1"]))*seconds/duration
        basis, trajectory = "nominal_sweep_bounds", "observed_sweep_bounds_preview"
        warnings.append("PROVISIONAL wavenumber axis: endpoint marker identities are unresolved; marker count alone is not an absolute wavelength assignment")
        identity_basis = None
    provisional = basis != "measured"
    summary.update(wavenumber_basis=basis, provisional=provisional,
                   marker_identity_basis=identity_basis, axis_sample_count=int(selected_axis.sum()))
    if int(selected_axis.sum()) < 2 or int(positive[selected_axis].sum()) < 2:
        reasons.append("Fewer than two valid CH1 samples have supported wavenumber coordinates")
    metadata = {"optical_valid": not reasons, "detector_mode": SINGLE_DETECTOR_MODE,
                "detector_input": DETECTOR_INPUT, "sample_demodulator": 0, "reference_demodulator": None,
                "record_role": record.get("record_role", "unknown"), "wavenumber_basis": basis,
                "provisional": provisional, "trajectory_method": trajectory,
                "marker_identity_basis": identity_basis, "marker_ticks": markers.tolist(),
                "observed_dio21_intervals": [list(interval) for interval in intervals],
                "ancillary_dio21_intervals_ignored": [list(interval) for interval in ancillary],
                "pump_time_basis": "unpumped", "timestamp_origin_ticks": start, "clockbase_hz": clock,
                "pump_sync_baseline_high": pump_baseline_high, "pump_sync_transition_count": pump_transitions,
                "pump_outputs_disabled_readback_verified": record.get("pump_outputs_disabled_readback_verified", False),
                "analysis_version": ANALYSIS_VERSION, "warnings": warnings,
                "native_source": summary["native_source"], "quality_usable": not reasons}
    for key in ("acquisition_settings", "hf2li_detector_settings", "hf2li_device"):
        if key in record:
            metadata[key] = record[key]
    # Explicit segments preserve native detector dropouts during later blank interpolation.
    segments = np.r_[0, np.cumsum(gaps)].astype(np.int64)
    spectrum = Spectrum(wn, magnitude[selected_axis], None, seconds[selected_axis], None,
                        metadata, segments[selected_axis])
    if not reasons:
        spectrum.validate()
    summary["usable_for_ratio"] = not reasons
    summary["usable_as_background"] = not reasons and metadata["record_role"] == "buffer_blank"
    if metadata["record_role"] == "buffer_blank":
        warnings.append("Sequential blank normalization does not cancel temporal source/detector drift; shared blank uncertainty is not repetition scatter")
    return spectrum


def analyze_single_detector_scan(directory, record, *, native_source=None):
    """Write CH1-only derived artifacts after the caller has preserved all native data."""
    directory = research_output_path(directory).resolve()
    native_path = Path(native_source).resolve() if native_source is not None else directory / "hf2li_native.npz"
    if not native_path.is_file():
        raise FileNotFoundError("Preserve the complete hf2li_native.npz before offline analysis")
    research_output_path(directory).mkdir(parents=True, exist_ok=True)
    output_names = ("ch1_spectrum.npz", "ch1_spectrum.csv", "single_detector_scan.png", "analysis.json")
    if any((directory / name).exists() for name in output_names):
        raise FileExistsError("Single-detector analysis artifacts already exist; preserve them")
    summary = {"analysis_version": ANALYSIS_VERSION, "detector_mode": SINGLE_DETECTOR_MODE,
               "detector_input": DETECTOR_INPUT, "record_role": record.get("record_role", "unknown"),
               "native_source": Path(os.path.relpath(native_path, directory)).as_posix(),
               "native_source_size_bytes": native_path.stat().st_size,
               "artifact_kind": "derived_spectrum_from_preserved_native", "publication_eligible": False,
               "run_classification": "EXPLORATORY_PROOF_OF_CONCEPT", "pump_events": record.get("pump_events"),
               "usable_for_ratio": False, "usable_as_background": False,
               "unusable_reasons": [], "warnings": list(record.get("warnings", []))}
    try:
        spectrum = _decode(record, summary)
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        summary["unusable_reasons"].append(str(exc))
        summary["status"] = "UNUSABLE"
        write_json(directory / "analysis.json", summary)
        return summary
    spectrum_path = directory / "ch1_spectrum.npz"
    csv_path = directory / "ch1_spectrum.csv"
    plot_path = directory / "single_detector_scan.png"
    if any(path.exists() for path in (spectrum_path, csv_path, plot_path, directory / "analysis.json")):
        raise FileExistsError("Single-detector analysis artifacts already exist; preserve them")
    save_native(spectrum_path, {"schema_version": "single-detector-spectrum/1.0", "spectrum": spectrum.to_dict()})
    with research_output_path(csv_path).open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["wavenumber_cm-1", "CH1_R_V", "time_from_sweep_active_s", "segment_id",
                         "positive_finite", "wavenumber_basis", "record_role", "detector_mode", "usable_for_ratio"])
        writer.writerows((wn, r, timestamp, segment, bool(np.isfinite(r) and r > 0),
                          spectrum.metadata["wavenumber_basis"], summary["record_role"],
                          SINGLE_DETECTOR_MODE, summary["usable_for_ratio"])
                         for wn, r, timestamp, segment in zip(spectrum.wavenumber_cm1, spectrum.sample_r,
                                                             spectrum.sample_time_s, spectrum.segment_id))
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    figure = Figure(figsize=(10, 5), constrained_layout=True)
    FigureCanvasAgg(figure)
    axis = figure.subplots()
    values = np.where(np.isfinite(spectrum.sample_r) & (spectrum.sample_r > 0), spectrum.sample_r, np.nan)
    values[np.r_[False, np.diff(spectrum.segment_id) != 0]] = np.nan
    axis.plot(spectrum.wavenumber_cm1, values, color="#247aa6", linewidth=.8)
    axis.invert_xaxis()
    axis_label = ("Controller-marker wavenumber (cm⁻¹)" if summary["wavenumber_basis"] == "controller_markers"
                  else "Provisional wavenumber (cm⁻¹)" if summary["provisional"] else "Wavenumber (cm⁻¹)")
    axis.set(xlabel=axis_label,
             ylabel="CH1 lock-in R (V)")
    axis.grid(alpha=.25)
    status = "USABLE_PROVISIONAL" if summary["usable_for_ratio"] and summary["provisional"] else "USABLE" if summary["usable_for_ratio"] else "UNUSABLE"
    figure.suptitle(f"{summary['record_role'].replace('_', ' ')} · HF2LI CH1 SIG IN +\n{status} · exploratory")
    figure.savefig(research_output_path(plot_path), dpi=140)
    summary.update(status=status, spectrum_path=str(spectrum_path), csv_path=str(csv_path), plot_path=str(plot_path))
    write_json(directory / "analysis.json", summary)
    return summary
