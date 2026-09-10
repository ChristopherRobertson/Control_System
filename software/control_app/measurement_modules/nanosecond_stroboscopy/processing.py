"""Native-support spectral reconstruction, independent of any sibling experiment."""
from __future__ import annotations

import math
from collections import defaultdict
from copy import deepcopy

import numpy as np

ANALYSIS_VERSION = "ns-native-support-1"
FATAL_FLAGS = {"clipped", "clipping", "overload", "unlock", "unlocked", "missing_trigger",
               "trigger_count_error", "count_mismatch", "reset_failed", "reset_failure",
               "temperature_invalid", "tuning_failed", "unsupported_reference", "missing_pump",
               "per_event_optical_pump_unobserved", "unsupported_sample", "invalid_detector_covariance"}


def _stream(stream):
    if stream is None:
        return np.array([]), np.array([]), np.array([]), np.array([], dtype=bool)
    if not isinstance(stream, dict):
        stream = {"value": [stream], "timestamp_s": [0.]}
    values = np.atleast_1d(np.asarray(stream.get("value", []), dtype=float))
    timestamps = np.atleast_1d(np.asarray(stream.get("timestamp_s", []), dtype=float))
    variances = np.broadcast_to(np.asarray(stream.get("variance", np.nan), dtype=float), values.shape)
    valid = np.broadcast_to(np.asarray(stream.get("valid", True), dtype=bool), values.shape).copy()
    if values.ndim != 1 or timestamps.shape != values.shape:
        raise ValueError("Native stream values and timestamps must be matching one-dimensional arrays")
    valid &= np.isfinite(values) & np.isfinite(timestamps)
    return timestamps - float(stream.get("group_delay_s", 0.)), values, variances, valid


def align_detectors(sample, reference, *, tolerance_s=0.):
    """One-to-one timestamp matches after recorded delay correction; no interpolation."""
    if not math.isfinite(tolerance_s) or tolerance_s < 0:
        raise ValueError("Alignment tolerance must be finite and nonnegative")
    st, sv, svar, svalid = _stream(sample)
    rt, rv, rvar, rvalid = _stream(reference)
    si, ri = [], []
    for index, stamp in enumerate(st):
        if not svalid[index]:
            continue
        candidates = np.flatnonzero(rvalid & (np.abs(rt - stamp) <= tolerance_s))
        # Ambiguous matches are unsupported, not arbitrarily assigned.
        if len(candidates) == 1:
            match = int(candidates[0])
            reciprocal = np.flatnonzero(svalid & (np.abs(st - rt[match]) <= tolerance_s))
            if len(reciprocal) == 1:
                si.append(index)
                ri.append(match)
    return dict(sample_indices=si, reference_indices=ri, sample=sv[si], reference=rv[ri],
                sample_variance=svar[si], reference_variance=rvar[ri],
                missing_sample_indices=[i for i in range(len(st)) if i not in si])


def _mean_variance(values, variances):
    if not len(values):
        return float("nan"), float("nan")
    average = float(np.mean(values))
    variance = float(np.sum(variances) / len(values)**2) if np.all(np.isfinite(variances) & (variances >= 0)) else float("nan")
    # Empirical variation is an additional conservative floor; unknown single-point
    # uncertainty stays unknown instead of becoming a perfect observation.
    if len(values) > 1:
        empirical = float(np.var(values, ddof=1) / len(values))
        variance = max(variance, empirical) if math.isfinite(variance) else empirical
    return average, variance


def spectral_observable(event, mode):
    flags = list(event.get("quality_flags", []))
    reset = event.get("reset_evidence", {})
    if isinstance(reset, dict) and reset.get("equivalent") is False:
        flags.append("reset_failed")
    if mode not in ("single", "dual"):
        raise ValueError("Detector mode must be single or dual")
    if mode == "single":
        _, sample, variance, valid = _stream(event.get("sample"))
        valid &= sample > 0
        value, uncertainty = _mean_variance(sample[valid], variance[valid])
        indices = np.flatnonzero(valid).tolist()
        if not indices:
            flags.append("unsupported_sample")
        return dict(value=value, variance=uncertainty, sample=value, reference=None,
                    covariance=None, flags=flags, sample_indices=indices)
    matched = align_detectors(event.get("sample"), event.get("reference"),
                              tolerance_s=event.get("alignment_tolerance_s", 0.))
    valid = (matched["sample"] > 0) & (matched["reference"] > 0)
    sample, vs = _mean_variance(matched["sample"][valid], matched["sample_variance"][valid])
    reference, vr = _mean_variance(matched["reference"][valid], matched["reference_variance"][valid])
    covariance = event.get("sample_reference_covariance")
    if covariance is None and np.count_nonzero(valid) > 1:
        covariance = float(np.cov(matched["sample"][valid], matched["reference"][valid], ddof=1)[0, 1] / np.count_nonzero(valid))
    value = variance = float("nan")
    if sample > 0 and reference > 0:
        value = sample / reference
        if covariance is not None and all(math.isfinite(v) for v in (vs, vr, covariance)):
            if abs(covariance) <= math.sqrt(vs*vr) + 1e-15:
                variance = max(0., value**2 * (vs/sample**2 + vr/reference**2 - 2*covariance/(sample*reference)))
            else:
                flags.append("invalid_detector_covariance")
    else:
        flags.append("unsupported_reference")
    return dict(value=value, variance=variance, sample=sample, reference=reference,
                covariance=covariance, flags=flags, sample_indices=matched["sample_indices"],
                reference_indices=matched["reference_indices"])


def _events(record):
    if record is None:
        return []
    return record.get("events", []) if isinstance(record, dict) else record


def _baselines(record, mode):
    groups = defaultdict(list)
    for event in _events(record):
        obs = spectral_observable(event, mode)
        if obs["value"] > 0 and not set(obs["flags"]) & FATAL_FLAGS:
            groups[float(event["wavenumber_cm1"])].append(obs)
    return {wave: _mean_variance(np.array([o["value"] for o in observations]),
                                np.array([o["variance"] for o in observations]))
            for wave, observations in groups.items()}


def validate_native_baseline(record, settings, kind="preliminary"):
    """Require complete wavelength support, and the full blank event schedule."""
    from .settings import Settings, KERNEL_ID
    from .planner import build_plan
    from .persistence import compatibility_conflicts
    selected = Settings.from_dict(settings)
    if not isinstance(record, dict):
        return [f"A completed compatible {kind} record is required"]
    errors = []
    for field, expected in (("experiment_id", "nanosecond_stroboscopy"), ("mode", selected.mode),
                            ("kind", kind), ("status", "completed")):
        if record.get(field) != expected:
            errors.append(f"{kind}.{field}: expected {expected!r}, got {record.get(field)!r}")
    errors.extend(compatibility_conflicts(record.get("settings", {}), selected.to_dict()))
    events = record.get("events", [])
    accepted = []
    for event in events:
        pump = event.get("pump_evidence", {})
        if event.get("condition") not in ("unpumped", "pump_blocked", "blank", "preliminary") or pump.get("optical_pulse_count") != 0 or pump.get("commanded") is True:
            errors.append(f"{kind} event {event.get('event_id')}: unpumped native evidence is required; a pumped event cannot supply blank or Q0")
            continue
        try:
            observable = spectral_observable(event, selected.mode)
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(f"{kind} event {event.get('event_id')}: {exc}")
            continue
        if event.get("kernel_id") != KERNEL_ID:
            errors.append(f"{kind} event {event.get('event_id')}: acquisition kernel differs")
            continue
        if not math.isfinite(observable["value"]) or observable["value"] <= 0 or set(observable["flags"]) & FATAL_FLAGS:
            errors.append(f"{kind} event {event.get('event_id')}: invalid native detector support or quality")
            continue
        accepted.append(event)
    plan = build_plan(selected)
    required_waves = {e.wavenumber_cm1 for e in plan.events}
    missing = required_waves - {e.get("wavenumber_cm1") for e in accepted}
    if missing:
        errors.append(f"{kind}: missing valid measured wavenumbers_cm1 {sorted(missing)}")
    if not accepted:
        errors.append(f"{kind}: no valid native events")
    if kind == "blank":
        def key(event):
            return (event.get("wavenumber_cm1"), event.get("requested_delay_ns"), event.get("repetition"),
                    event.get("requested_condition", event.get("condition")))
        from dataclasses import asdict
        from collections import Counter
        required = Counter(key(asdict(event)) for event in plan.events)
        retained = Counter(key(event) for event in accepted)
        missing_events = required - retained
        if missing_events:
            errors.append(f"blank: incomplete sequential delay/control schedule ({sum(missing_events.values())} required events missing)")
    return errors


def _log_ratio(value, base, variance, base_variance):
    if not (math.isfinite(value) and value > 0 and math.isfinite(base) and base > 0):
        return float("nan"), float("nan")
    result = -math.log10(value/base)
    var = (variance/value**2 + base_variance/base**2) / math.log(10.)**2
    return result, math.sqrt(var) if math.isfinite(var) and var >= 0 else float("nan")


def reconstruct(events, baseline, *, mode, blank=None, balance=None, cancel=None, kernel=None):
    """Reconstruct command bins with independently calibrated optical coordinates.

    No point is filled across a missing wavelength, delay, reference or baseline.
    Technical repetitions are averaged, never counted as independent preparations.
    Shared Q0 uncertainty is retained separately and does not average down with shots.
    """
    events = list(events)
    q0 = _baselines(baseline, mode)
    backgrounds = _baselines(blank, "single") if mode == "single" else {}
    waves = sorted({float(e["wavenumber_cm1"]) for e in events})
    delays = sorted({float(e["quantized_delay_ns"]) for e in events})
    shape = len(waves), len(delays)
    arrays = {key: np.full(shape, np.nan) for key in ("delta_a", "uncertainty", "ratio", "absolute_absorbance", "optical_delay_ns", "measured_wavenumber_cm1", "baseline_uncertainty")}
    coverage = np.zeros(shape, dtype=np.int64)
    groups, outputs = defaultdict(list), []
    for event in events:
        if cancel:
            cancel()
        obs = spectral_observable(event, mode)
        wave, delay = float(event["wavenumber_cm1"]), float(event["quantized_delay_ns"])
        flags = list(obs["flags"])
        optical = event.get("calibrated_optical_delay_ns")
        if optical is None or not math.isfinite(float(optical)):
            flags.append("optical_delay_unresolved")
        if wave not in q0:
            flags.append("missing_unpumped_baseline")
        if mode == "single" and wave not in backgrounds:
            flags.append("missing_sequential_blank")
        condition = event.get("condition", "pump_on")
        if condition in ("pump_on", "pumped", "sample") and event.get("pump_evidence", {}).get("optical_pulse_count") != 1:
            flags.append("missing_pump")
        base, base_var = q0.get(wave, (float("nan"), float("nan")))
        value, uncertainty = _log_ratio(obs["value"], base, obs["variance"], base_var)
        fatal = set(flags) & (FATAL_FLAGS | {"optical_delay_unresolved", "missing_unpumped_baseline", "missing_sequential_blank", "invalid_detector_covariance"})
        if fatal:
            value = uncertainty = float("nan")
        output = dict(event_id=event.get("event_id"), wavenumber_cm1=wave, quantized_delay_ns=delay,
                      measured_wavenumber_cm1=event.get("measured_wavenumber_cm1"),
                      calibrated_optical_delay_ns=optical, condition=condition, observable=obs,
                      delta_a=value, uncertainty=uncertainty, flags=flags,
                      repetition=event.get("repetition"), position_id=event.get("position_id"))
        outputs.append(output)
        if condition in ("pump_on", "pumped", "sample") and math.isfinite(value):
            groups[(wave, delay)].append(output)
    for (wave, delay), observations in groups.items():
        i, j = waves.index(wave), delays.index(delay)
        observable, variance = _mean_variance(np.array([o["observable"]["value"] for o in observations]),
                                              np.array([o["observable"]["variance"] for o in observations]))
        base, base_var = q0[wave]
        delta, std = _log_ratio(observable, base, variance, base_var)
        arrays["delta_a"][i, j], arrays["uncertainty"][i, j] = delta, std
        arrays["ratio"][i, j] = observable
        arrays["baseline_uncertainty"][i, j] = math.sqrt(base_var)/base/math.log(10.) if math.isfinite(base_var) else np.nan
        arrays["optical_delay_ns"][i, j] = np.mean([o["calibrated_optical_delay_ns"] for o in observations])
        if all(o["measured_wavenumber_cm1"] is not None for o in observations):
            arrays["measured_wavenumber_cm1"][i, j] = np.mean([o["measured_wavenumber_cm1"] for o in observations])
        coverage[i, j] = len(observations)
        if mode == "single" and wave in backgrounds:
            arrays["absolute_absorbance"][i, j] = _log_ratio(observable, backgrounds[wave][0], variance, backgrounds[wave][1])[0]
        if mode == "dual" and balance is not None:
            # The caller loads a separately validated promoted B; Q0 cannot be B.
            if balance.get("kind") != "measured_path_balance" or not balance.get("calibration_id") or not balance.get("bundle_id"):
                raise ValueError("Absolute absorbance requires a measured, applicable path-balance B record")
            bw = list(balance.get("wavenumbers_cm1", []))
            if wave in bw:
                b = float(balance["values"][bw.index(wave)])
                arrays["absolute_absorbance"][i, j] = _log_ratio(observable, b, variance, float("nan"))[0]
    fits = []
    if kernel is not None:
        from .simulation import identify_lifetime
        for i, wave in enumerate(waves):
            if cancel:
                cancel()
            fit = identify_lifetime(arrays["optical_delay_ns"][i], arrays["delta_a"][i], arrays["uncertainty"][i], kernel)
            if float(kernel.get("filter_memory_fraction", 0)) > .001:
                # Bins combine counterbalanced events. Their native chronology is
                # retained, but fitting bins as a chronological stream is invalid.
                fit.update(outcome="prompt_unresolved_bound", lifetime_ns=None,
                           lifetime_interval_ns=None, upper_bound_ns=None)
                fit.setdefault("reasons", []).append("Residual filter history is not negligible; command-bin averages cannot replace the retained acquisition order")
            fits.append(dict(wavenumber_cm1=wave, **fit))
    controls = {}
    for condition in sorted({o["condition"] for o in outputs} - {"pump_on", "pumped", "sample"}):
        control_map, control_count = np.full(shape, np.nan), np.zeros(shape, dtype=np.int64)
        cells = defaultdict(list)
        for output in outputs:
            if output["condition"] == condition and math.isfinite(output["delta_a"]):
                cells[(output["wavenumber_cm1"], output["quantized_delay_ns"])].append(output["delta_a"])
        for (wave, delay), values in cells.items():
            i, j = waves.index(wave), delays.index(delay)
            control_map[i, j], control_count[i, j] = np.mean(values), len(values)
        controls[condition] = dict(delta_a=control_map, coverage=control_count)
    return dict(analysis_version=ANALYSIS_VERSION, mode=mode, wavenumbers_cm1=waves, delays_ns=delays,
                delay_axis="Quantized command bins (ns); calibrated optical coordinates stored separately",
                **arrays, coverage=coverage, event_results=outputs, fits=fits, controls=controls,
                signal_label="Sample/reference ratio Q" if mode == "dual" else "Sample spectral signal",
                absolute_available=bool(mode == "single" and backgrounds or mode == "dual" and balance),
                uncertainty_basis="Delta method including detector covariance and common unpumped baseline; technical repeats only",
                claim="Instrument-supported Delta A; molecular pathway, temperature and resolved lifetime require independent qualifications")


def population_kinetics(result, selection, kernel, *, cancel=None):
    """Data-only selected population windows; never infer population labels.

    Report local band areas and fit the measured point nearest each accepted
    centre. The point-fit comparison is labelled as such; band-area uncertainty
    cannot be inferred without the spectral covariance matrix.
    """
    from control_app.measurement_host.interchange import sample_selection_from_dict
    from .simulation import fit_shared_lifetimes
    selected = sample_selection_from_dict(selection)
    waves = np.asarray(result["wavenumbers_cm1"])
    populations, traces, used = [], [], set()
    for window in selected.windows:
        if cancel:
            cancel()
        indices = np.flatnonzero((waves >= window.lower_cm1) & (waves <= window.upper_cm1))
        if window.center_cm1 is None or not len(indices):
            populations.append(dict(label=window.label, outcome="insufficient_support", reason="No accepted centre with measured local support"))
            continue
        index = int(indices[np.argmin(abs(waves[indices] - window.center_cm1))])
        if index in used:
            populations.append(dict(label=window.label, outcome="insufficient_support", reason="Overlapping populations select the same measured point; no independent state kinetics"))
            continue
        used.add(index)
        traces.append(dict(delay_ns=result["optical_delay_ns"][index], delta_a=result["delta_a"][index], uncertainty=result["uncertainty"][index]))
        populations.append(dict(label=window.label, selected_center_cm1=window.center_cm1,
                                measured_point_cm1=float(waves[index]),
                                band=band_kinetics(result, window.lower_cm1, window.upper_cm1)))
    comparison = fit_shared_lifetimes(traces, kernel) if float(kernel.get("filter_memory_fraction", 0)) <= .001 else dict(outcome="prompt_unresolved_bound", reason="Non-negligible native filter chronology cannot be fitted from averaged bins")
    return dict(selection_id=selected.selection_id, populations=populations, point_comparison=comparison,
                interpretation="Comparison uses native supported point kinetics selected by accepted spectral windows; band areas require spectral covariance for lifetime inference")


def band_kinetics(result, lower_cm1, upper_cm1):
    """Trapezoid band area only when the entire selected measured support exists."""
    waves = np.asarray(result["wavenumbers_cm1"])
    indices = np.flatnonzero((waves >= lower_cm1) & (waves <= upper_cm1))
    delta = np.asarray(result["delta_a"])
    area = np.full(delta.shape[1], np.nan)
    if len(indices) > 1:
        values = delta[indices]
        complete = np.all(np.isfinite(values), axis=0)
        area[complete] = np.trapezoid(values[:, complete], waves[indices], axis=0)
    return dict(delays_ns=deepcopy(result["delays_ns"]), area_delta_a_cm1=area,
                lower_cm1=lower_cm1, upper_cm1=upper_cm1,
                uncertainty="Band covariance is required for quantitative integrated-area uncertainty")
