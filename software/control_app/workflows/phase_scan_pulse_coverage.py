"""PicoScope optical-pulse coverage analysis for Phase Scan attempts.

Expected opportunities come from the configured/read-back T660-2 rate.  Their
phase is propagated between consecutive observed optical edges, so a missing
edge creates an opportunity instead of shifting one global fitted grid.  The
PicoScope EXT is triggered directly by the rising edge of MIRcat DB9 pin 2
Tuned / Sweep Active. CHA and CHB remain independent optical witnesses and are
never used as the timing authority. Legacy CHD-aligned payloads remain readable
when they include their qualified offset metadata.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from control_app.workflows.phase_scan_data import Spectrum, interpolate_supported


COVERAGE_ANALYSIS_VERSION = "phase-scan-pulse-coverage/1.1"


def analyze_scan_pulse_coverage(native: dict, spectrum: Spectrum, settings) -> dict[str, Any]:
    """Classify every bounded optical opportunity in one physical scan attempt."""
    segments = native.get("segments")
    if not isinstance(segments, list) or not segments:
        return _unavailable_report("Native scan has no segment records")
    metadata = spectrum.metadata.get("segment_metadata") or [spectrum.metadata]
    if len(metadata) != len(segments):
        return _unavailable_report("Spectrum/native segment counts differ")
    rate_hz = float(native.get("probe_repetition_rate_hz_readback", math.nan))
    if not np.isfinite(rate_hz) or rate_hz <= 0:
        return _unavailable_report("Positive T660-2 repetition-rate readback is absent")

    reports = []
    for index, (segment, segment_metadata) in enumerate(zip(segments, metadata)):
        pico = segment.get("picoscope")
        if not isinstance(pico, dict):
            reports.append(_unavailable_segment(index, "PicoScope trace is absent"))
            continue
        try:
            start_tick, stop_tick = segment_metadata["sweep_active_ticks"]
            duration_s = (int(stop_tick) - int(start_tick)) / float(segment_metadata["clockbase_hz"])
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
            reports.append(_unavailable_segment(index, f"Invalid observed Sweep Active timing: {exc}"))
            continue
        reports.append(analyze_segment_trace(
            pico,
            pulse_rate_hz=rate_hz,
            sweep_duration_s=duration_s,
            reconstruction_interval_s=float(settings.phase_delay_us) * 1e-6,
            threshold_fraction=float(settings.pulse_detection_threshold_fraction),
            minimum_interval_coverage=float(settings.minimum_reconstruction_interval_coverage),
            consecutive_missing_limit=int(settings.missing_pulse_consecutive_limit),
            segment_index=index,
        ))

    intervals = [interval for report in reports for interval in report["intervals"]]
    expected = sum(report["expected_opportunities"] for report in reports)
    missing = sum(report["missing_opportunities"] for report in reports)
    unclassified = sum(report["unclassified_opportunities"] for report in reports)
    missing_fraction = missing / expected if expected else 1.0
    max_consecutive = max((report["maximum_consecutive_missing"] for report in reports), default=0)
    reasons = []
    if any(report["analysis_status"] != "AVAILABLE" for report in reports):
        reasons.append("PULSE_COVERAGE_ANALYSIS_UNAVAILABLE")
    if any(not interval["acceptable"] for interval in intervals):
        reasons.append("RECONSTRUCTION_INTERVAL_COVERAGE")
    if max_consecutive >= int(settings.missing_pulse_consecutive_limit):
        reasons.append("CONSECUTIVE_MISSING_PULSES")
    if missing_fraction > float(settings.maximum_scan_missing_fraction):
        reasons.append("WHOLE_SCAN_MISSING_FRACTION")
    if unclassified:
        reasons.append("UNCLASSIFIED_OPPORTUNITIES")
    return {
        "analysis_version": COVERAGE_ANALYSIS_VERSION,
        "analysis_status": "AVAILABLE" if not any(
            report["analysis_status"] != "AVAILABLE" for report in reports
        ) else "PARTIAL_OR_UNAVAILABLE",
        "pulse_rate_hz_readback": rate_hz,
        "expected_opportunities": expected,
        "observed_opportunities": expected - missing - unclassified,
        "missing_opportunities": missing,
        "unclassified_opportunities": unclassified,
        "missing_fraction": missing_fraction,
        "maximum_consecutive_missing": max_consecutive,
        "detector_path_discrepancies": sum(report["detector_path_discrepancies"] for report in reports),
        "segments": reports,
        "repeat_reasons": sorted(set(reasons)),
        "reacquire_required": bool(reasons),
        "status": "REACQUIRE" if reasons else "ACCEPTABLE",
        "criteria": {
            "missing_definition": "expected optical pulse absent from both CHA sample and CHB reference",
            "minimum_reconstruction_interval_coverage": float(settings.minimum_reconstruction_interval_coverage),
            "maximum_scan_missing_fraction": float(settings.maximum_scan_missing_fraction),
            "missing_pulse_consecutive_limit": int(settings.missing_pulse_consecutive_limit),
            "threshold_fraction_of_local_baseline_to_pulse_amplitude": float(
                settings.pulse_detection_threshold_fraction
            ),
        },
    }


def analyze_segment_trace(
    pico: dict,
    *,
    pulse_rate_hz: float,
    sweep_duration_s: float,
    reconstruction_interval_s: float,
    threshold_fraction: float,
    minimum_interval_coverage: float,
    consecutive_missing_limit: int,
    segment_index: int = 0,
) -> dict[str, Any]:
    """Analyze one trigger-referenced dual-detector trace over Sweep Active."""
    try:
        a = np.asarray(pico["ch_a_adc"], dtype=float)
        b = np.asarray(pico["ch_b_adc"], dtype=float)
        sample_interval_s = float(pico["sample_interval_ns"]) * 1e-9
        pre_trigger = int(pico["pre_trigger_samples"])
        adc_max = abs(float(pico["maximum_adc_value"]))
    except (KeyError, TypeError, ValueError) as exc:
        return _unavailable_segment(segment_index, f"Invalid PicoScope payload: {exc}")
    if (a.ndim != 1 or b.ndim != 1 or len(a) != len(b) or len(a) < 4 or
            not np.isfinite(sample_interval_s) or sample_interval_s <= 0):
        return _unavailable_segment(segment_index, "PicoScope arrays or sample interval are invalid")
    if sample_interval_s > 48e-9 * (1 + 1e-9):
        return _unavailable_segment(
            segment_index, f"PicoScope sampling is {sample_interval_s * 1e9:g} ns/sample; maximum is 48 ns/sample"
        )
    if int(pico.get("overflow", 0)):
        return _unavailable_segment(
            segment_index, f"PicoScope reported channel overflow mask {int(pico['overflow'])}"
        )
    if not np.isfinite(sweep_duration_s) or sweep_duration_s <= 0:
        return _unavailable_segment(segment_index, "Observed Sweep Active duration is invalid")
    trigger_basis = str(pico.get("external_trigger_basis", "mircat_sweep_active"))
    if trigger_basis == "mircat_sweep_active":
        sweep_start_s = 0.0
        sweep_start_uncertainty_s = 0.0
    else:
        try:
            sweep_start_s = float(pico["sweep_start_offset_s"])
            sweep_start_uncertainty_s = float(pico["sweep_start_uncertainty_s"])
        except (KeyError, TypeError, ValueError) as exc:
            return _unavailable_segment(segment_index, f"Invalid trigger-to-sweep alignment: {exc}")
        if (trigger_basis != "t660_1_chd_process_marker" or
                not np.isfinite(sweep_start_s) or sweep_start_s < 0 or
                not np.isfinite(sweep_start_uncertainty_s) or sweep_start_uncertainty_s < 0 or
                not str(pico.get("trigger_alignment_qualification_id") or "").strip()):
            return _unavailable_segment(segment_index, "Qualified T660-1 CHD trigger alignment is absent")
    sweep_stop_s = sweep_start_s + sweep_duration_s
    times = (np.arange(len(a), dtype=float) - pre_trigger) * sample_interval_s
    if times[0] >= sweep_start_s or times[-1] <= sweep_stop_s:
        return _unavailable_segment(
            segment_index, "PicoScope record does not bracket the complete observed Sweep Active interval"
        )
    period_s = 1.0 / float(pulse_rate_hz)
    detector_a = _detect_channel_pulses(
        times, a, period_s=period_s, threshold_fraction=threshold_fraction, adc_max=adc_max
    )
    detector_b = _detect_channel_pulses(
        times, b, period_s=period_s, threshold_fraction=threshold_fraction, adc_max=adc_max
    )
    opportunities, grid_issues = _local_opportunities(
        detector_a, detector_b, period_s=period_s, start_s=sweep_start_s, stop_s=sweep_stop_s
    )
    if not opportunities:
        return _unavailable_segment(segment_index, "No bounded expected opportunities could be formed")

    for item in opportunities:
        item["time_s"] -= sweep_start_s
    for issue in grid_issues:
        issue["time_s"] -= sweep_start_s
    missing_flags = np.asarray([item["status"] == "missing" for item in opportunities], dtype=bool)
    run_lengths = _run_lengths(missing_flags)
    interval_count = max(1, int(math.ceil(sweep_duration_s / reconstruction_interval_s - 1e-12)))
    edges = np.arange(interval_count + 1, dtype=float) * reconstruction_interval_s
    edges[-1] = sweep_duration_s
    intervals = []
    for region_index, (left, right) in enumerate(zip(edges[:-1], edges[1:])):
        selected = [i for i, item in enumerate(opportunities)
                    if left <= item["time_s"] < right or (region_index == len(edges)-2 and item["time_s"] == right)]
        statuses = [opportunities[i]["status"] for i in selected]
        expected = len(selected)
        unclassified = statuses.count("unclassified")
        missing = statuses.count("missing")
        observed = expected - missing - unclassified
        coverage = observed / expected if expected else 1.0
        max_run = int(max((run_lengths[i] for i in selected), default=0))
        overlapping_grid_issue = any(left <= issue["time_s"] < right for issue in grid_issues)
        acceptable = bool(
            expected and not unclassified and coverage + 1e-12 >= minimum_interval_coverage
            and max_run < consecutive_missing_limit and not overlapping_grid_issue
        )
        intervals.append({
            "segment_index": segment_index,
            "region_index": region_index,
            "start_s": float(left),
            "stop_s": float(right),
            "expected_opportunities": expected,
            "observed_opportunities": observed,
            "missing_opportunities": missing,
            "unclassified_opportunities": unclassified,
            "coverage_fraction": coverage,
            "maximum_consecutive_missing": max_run,
            "both_channels": statuses.count("both"),
            "cha_only": statuses.count("cha_only"),
            "chb_only": statuses.count("chb_only"),
            "detector_path_discrepancies": statuses.count("cha_only") + statuses.count("chb_only"),
            "grid_issue": overlapping_grid_issue,
            "acceptable": acceptable,
        })
    missing = int(missing_flags.sum())
    unclassified = sum(item["status"] == "unclassified" for item in opportunities)
    return {
        "analysis_status": "AVAILABLE",
        "segment_index": segment_index,
        "external_trigger_basis": trigger_basis,
        "sweep_start_offset_s": sweep_start_s,
        "sweep_start_uncertainty_s": sweep_start_uncertainty_s,
        "trigger_alignment_qualification_id": pico.get("trigger_alignment_qualification_id"),
        "sweep_duration_s": sweep_duration_s,
        "sample_interval_ns": sample_interval_s * 1e9,
        "expected_opportunities": len(opportunities),
        "observed_opportunities": len(opportunities) - missing - unclassified,
        "missing_opportunities": missing,
        "unclassified_opportunities": unclassified,
        "missing_fraction": missing / len(opportunities),
        "maximum_consecutive_missing": int(run_lengths.max(initial=0)),
        "detector_path_discrepancies": sum(
            item["status"] in {"cha_only", "chb_only"} for item in opportunities
        ),
        "grid_issues": grid_issues,
        "channel_analysis": {"CHA_sample": detector_a["summary"], "CHB_reference": detector_b["summary"]},
        "intervals": intervals,
    }


def coverage_for_wavenumbers(
    spectrum: Spectrum, coverage_report: dict, target_wavenumbers_cm1
) -> tuple[np.ndarray, np.ndarray]:
    """Map attempt coverage bins onto a common marker-aligned wavenumber grid."""
    target = np.asarray(target_wavenumbers_cm1, dtype=float)
    fractions = np.zeros(target.shape, dtype=float)
    acceptable = np.zeros(target.shape, dtype=bool)
    segments = coverage_report.get("segments") or []
    segment_metadata = spectrum.metadata.get("segment_metadata") or [spectrum.metadata]
    ids = np.zeros(len(spectrum.wavenumber_cm1), dtype=int) if spectrum.segment_id is None else np.asarray(spectrum.segment_id)
    for segment_report in segments:
        index = int(segment_report.get("segment_index", -1))
        if index < 0 or index >= len(segment_metadata) or segment_report.get("analysis_status") != "AVAILABLE":
            continue
        selected = ids == index
        if selected.sum() < 2:
            continue
        metadata = segment_metadata[index]
        try:
            active_start_s = ((int(metadata["sweep_active_ticks"][0]) - int(metadata["timestamp_origin_ticks"])) /
                              float(metadata["clockbase_hz"]))
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
        relative_time = np.asarray(spectrum.sample_time_s)[selected] - active_start_s
        target_time = interpolate_supported(
            np.asarray(spectrum.wavenumber_cm1)[selected], relative_time, target
        )
        intervals = segment_report.get("intervals", [])
        for interval_index, interval in enumerate(intervals):
            inside = (target_time >= float(interval["start_s"])) & (
                (target_time < float(interval["stop_s"])) |
                ((interval_index == len(intervals)-1) & (target_time <= float(interval["stop_s"])))
            )
            fractions[inside] = float(interval["coverage_fraction"])
            acceptable[inside] = bool(interval["acceptable"])
    return fractions, acceptable


def combined_interval_coverage_complete(reports) -> bool:
    """Require every bounded interval to be acceptable in at least one attempt."""
    required: set[tuple[int, int]] = set()
    accepted: set[tuple[int, int]] = set()
    for report in reports:
        for segment in report.get("segments", []):
            if segment.get("analysis_status") != "AVAILABLE":
                continue
            for interval in segment.get("intervals", []):
                key = (int(interval["segment_index"]), int(interval["region_index"]))
                required.add(key)
                if interval.get("acceptable"):
                    accepted.add(key)
    return bool(required and required <= accepted)


def _detect_channel_pulses(times, values, *, period_s, threshold_fraction, adc_max):
    values = np.asarray(values, dtype=float)
    samples_per_period = max(2, int(round(period_s / float(np.median(np.diff(times))))))
    window = max(samples_per_period * 100, 256)
    mask = np.zeros(values.shape, dtype=bool)
    reliable = np.zeros(values.shape, dtype=bool)
    window_reports = []
    for start in range(0, len(values), window):
        stop = min(len(values), start + window)
        block = values[start:stop]
        finite = block[np.isfinite(block)]
        if len(finite) < max(16, (stop-start)//2):
            window_reports.append(_channel_window(start, stop, quality="NONFINITE"))
            continue
        baseline = float(np.median(finite))
        high, low = float(np.quantile(finite, .95)), float(np.quantile(finite, .05))
        upper, lower = high - baseline, baseline - low
        polarity = 1.0 if upper >= lower else -1.0
        amplitude = upper if polarity > 0 else lower
        baseline_population = finite[finite <= baseline] if polarity > 0 else finite[finite >= baseline]
        noise = float(1.4826 * np.median(np.abs(baseline_population - np.median(baseline_population)))) \
            if len(baseline_population) else math.nan
        threshold = baseline + polarity * threshold_fraction * amplitude
        saturation_fraction = float(np.mean(np.abs(finite) >= adc_max * .98)) if adc_max > 0 else 0.0
        quality = "OK"
        if not np.isfinite(amplitude) or amplitude < max(4.0, 6.0 * (noise if np.isfinite(noise) else math.inf)):
            quality = "LOW_SIGNAL_TO_NOISE"
        elif saturation_fraction > .30:
            quality = "SATURATED"
        if quality == "OK":
            reliable[start:stop] = True
            mask[start:stop] = (block >= threshold) if polarity > 0 else (block <= threshold)
        window_reports.append({
            "start_sample": start, "stop_sample": stop, "baseline_adc": baseline,
            "pulse_population_adc": baseline + polarity * amplitude, "threshold_adc": threshold,
            "amplitude_adc": amplitude, "noise_mad_adc": noise, "polarity": "positive" if polarity > 0 else "negative",
            "saturation_fraction": saturation_fraction, "saturation_detected": saturation_fraction > 0,
            "quality": quality,
        })
    transitions = np.diff(np.pad(mask.astype(np.int8), (1, 1)))
    starts, stops = np.flatnonzero(transitions == 1), np.flatnonzero(transitions == -1)
    valid = stops > starts
    starts, stops = starts[valid], stops[valid]
    # The midpoint between the two local threshold crossings is a stable pulse
    # timestamp for either polarity. Calculate all centers together: calling several
    # NumPy reductions for every 2 MHz pulse dominates long-record analysis time.
    centers = ((np.asarray(times)[starts] + np.asarray(times)[stops - 1]) / 2).tolist()
    centers = _deduplicate_centers(centers, minimum_separation_s=.35 * period_s)
    return {
        "centers_s": np.asarray(centers, dtype=float),
        "reliable": reliable,
        "times": np.asarray(times, dtype=float),
        "summary": {
            "detected_pulses": len(centers),
            "reliable_fraction": float(np.mean(reliable)),
            "quality_windows": window_reports,
            "saturation_checked_at_adc_fraction": .98,
            "threshold_method": "local baseline plus configured fraction of local baseline-to-pulse population",
        },
    }


def _local_opportunities(detector_a, detector_b, *, period_s, start_s, stop_s):
    a_times = np.asarray(detector_a["centers_s"], dtype=float)
    b_times = np.asarray(detector_b["centers_s"], dtype=float)
    events = []
    used_a = set()
    match_tolerance_s = .35 * period_s
    # CHB is the primary witness.  CHA matches corroborate it; unmatched CHA
    # events remain explicit detector/path discrepancies, not missing pulses.
    for b_time in b_times:
        # Pulse centers are sorted and already deduplicated. Restrict the nearest-
        # neighbor search to the small time window that can possibly match instead
        # of sorting the distance to every CHA pulse for every CHB pulse. This keeps
        # long 2 MHz records linearithmic without changing the matching rule.
        left = int(np.searchsorted(a_times, b_time - match_tolerance_s, side="left"))
        right = int(np.searchsorted(a_times, b_time + match_tolerance_s, side="right"))
        candidates = [index for index in range(left, right) if index not in used_a]
        if not candidates:
            events.append({"time_s": float(b_time), "a": False, "b": True})
            continue
        index = min(candidates, key=lambda candidate: (abs(a_times[candidate] - b_time), candidate))
        used_a.add(index)
        events.append({"time_s": float((b_time + a_times[index]) / 2), "a": True, "b": True})
    events.extend({"time_s": float(value), "a": True, "b": False}
                  for index, value in enumerate(a_times) if index not in used_a)
    events.sort(key=lambda item: item["time_s"])
    if len(events) < 2:
        return [], []
    compact = []
    for event in events:
        if compact and event["time_s"] - compact[-1]["time_s"] < .35 * period_s:
            previous = compact[-1]
            previous["time_s"] = (previous["time_s"] + event["time_s"]) / 2
            previous["a"] = previous["a"] or event["a"]
            previous["b"] = previous["b"] or event["b"]
        else:
            compact.append(event.copy())
    grid, issues = [compact[0].copy()], []
    for left, right in zip(compact[:-1], compact[1:]):
        delta = right["time_s"] - left["time_s"]
        steps = max(1, int(round(delta / period_s)))
        local_period = delta / steps
        if abs(local_period - period_s) > .20 * period_s:
            issues.append({"time_s": float((left["time_s"] + right["time_s"]) / 2),
                           "local_period_s": local_period, "nominal_period_s": period_s})
        for step in range(1, steps):
            grid.append({"time_s": float(left["time_s"] + delta * step / steps), "a": False, "b": False})
        grid.append(right.copy())
    bounded = []
    for item in grid:
        if not start_s <= item["time_s"] < stop_s:
            continue
        index_a = int(np.clip(np.searchsorted(detector_a["times"], item["time_s"]), 0, len(detector_a["times"])-1))
        index_b = int(np.clip(np.searchsorted(detector_b["times"], item["time_s"]), 0, len(detector_b["times"])-1))
        reliable_a, reliable_b = bool(detector_a["reliable"][index_a]), bool(detector_b["reliable"][index_b])
        if item["a"] and item["b"]:
            status = "both"
        elif item["a"]:
            status = "cha_only"
        elif item["b"]:
            status = "chb_only"
        elif reliable_a and reliable_b:
            status = "missing"
        else:
            status = "unclassified"
        bounded.append({"time_s": item["time_s"], "status": status})
    return bounded, issues


def _run_lengths(flags):
    result = np.zeros(len(flags), dtype=np.int32)
    start = None
    for index, value in enumerate(np.append(flags, False)):
        if value and start is None:
            start = index
        elif not value and start is not None:
            result[start:index] = index - start
            start = None
    return result


def _deduplicate_centers(values, *, minimum_separation_s):
    result = []
    for value in sorted(values):
        if result and value - result[-1] < minimum_separation_s:
            result[-1] = (result[-1] + value) / 2
        else:
            result.append(value)
    return result


def _channel_window(start, stop, *, quality):
    return {"start_sample": start, "stop_sample": stop, "quality": quality}


def _unavailable_segment(index, reason):
    return {
        "analysis_status": "UNAVAILABLE", "segment_index": index, "reason": reason,
        "expected_opportunities": 0, "observed_opportunities": 0, "missing_opportunities": 0,
        "unclassified_opportunities": 0, "missing_fraction": 1.0,
        "maximum_consecutive_missing": 0, "detector_path_discrepancies": 0, "intervals": [],
    }


def _unavailable_report(reason):
    return {
        "analysis_version": COVERAGE_ANALYSIS_VERSION, "analysis_status": "UNAVAILABLE",
        "reason": reason, "expected_opportunities": 0, "observed_opportunities": 0,
        "missing_opportunities": 0, "unclassified_opportunities": 0, "missing_fraction": 1.0,
        "maximum_consecutive_missing": 0, "detector_path_discrepancies": 0,
        "segments": [], "repeat_reasons": ["PULSE_COVERAGE_ANALYSIS_UNAVAILABLE"],
        "reacquire_required": True, "status": "REACQUIRE",
    }
