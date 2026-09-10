"""Pointwise scan-burst observables on measured support, without gap filling.

Each point retains its native trajectory time. Sparse bursts are not an
equivalent-time surface and no recovery mechanism is inferred from slowness.
"""
from __future__ import annotations

from enum import IntFlag
import math
import numpy as np

ANALYSIS_VERSION = "single-pump-pointwise/2"


class Quality(IntFlag):
    INVALID_SAMPLE = 1
    INVALID_REFERENCE = 2
    UNMATCHED_REFERENCE = 4
    MISSING_BASELINE = 8
    CLIPPED = 16
    UNLOCKED = 32
    INVALID_TRAJECTORY = 64
    INVALID_BLANK = 128
    INVALID_UNCERTAINTY = 256


def _vector(record, key, count=None, default=None, dtype=float):
    value = record.get(key, default)
    if value is None:
        raise ValueError(f"Missing native {key}")
    array = np.asarray(value, dtype=dtype)
    if array.ndim == 0 and count is not None:
        array = np.full(count, array, dtype=dtype)
    if array.ndim != 1 or (count is not None and len(array) != count):
        raise ValueError(f"{key} must be a pointwise vector of length {count}")
    return array


def _nearest_indices(source, target, tolerance):
    """Match existing samples only; never synthesize an intermediate value."""
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Matching tolerance must be finite and nonnegative")
    source, target = np.asarray(source), np.asarray(target)
    valid_source = np.flatnonzero(np.isfinite(source))
    result = np.full(len(target), -1, int)
    if not len(valid_source):
        return result
    order = valid_source[np.argsort(source[valid_source], kind="stable")]
    ordered = source[order]
    positions = np.searchsorted(ordered, target)
    left, right = np.clip(positions-1, 0, len(order)-1), np.clip(positions, 0, len(order)-1)
    nearest = np.where(abs(ordered[left]-target) <= abs(ordered[right]-target), left, right)
    valid = np.isfinite(target) & (abs(ordered[nearest]-target) <= tolerance)
    result[valid] = order[nearest[valid]]
    return result


def detector_ratio(native, *, mode, time_tolerance_s=0., wavenumber_tolerance_cm1=0.):
    signal = _vector(native, "sample")
    n = len(signal)
    times = _vector(native, "sample_time_s", n)
    wn = _vector(native, "wavenumber_cm1", n)
    flags = _vector(native, "flags", n, 0, np.int64).copy()
    flags[~np.isfinite(signal) | (signal <= 0)] |= Quality.INVALID_SAMPLE
    flags[~np.isfinite(times) | ~np.isfinite(wn)] |= Quality.INVALID_TRAJECTORY
    for key, bit in (("clipped", Quality.CLIPPED), ("unlocked", Quality.UNLOCKED)):
        flags[_vector(native, key, n, False, bool)] |= bit
    sample_var = _vector(native, "sample_variance", n, np.nan)
    ratio, variance = signal.copy(), sample_var.copy()
    matched_reference = np.full(n, np.nan)
    covariance = _vector(native, "sample_reference_covariance", n, np.nan)
    if mode == "dual":
        reference = _vector(native, "reference")
        if not len(reference):
            flags |= Quality.INVALID_REFERENCE | Quality.UNMATCHED_REFERENCE
            return {"ratio": np.full(n, np.nan), "variance": np.full(n, np.nan), "quality_flags": flags,
                    "matched_reference": matched_reference, "covariance": covariance,
                    "sample_time_s": times, "wavenumber_cm1": wn}
        rt = _vector(native, "reference_time_s", len(reference), times if len(reference) == n else None)
        rw = _vector(native, "reference_wavenumber_cm1", len(reference), wn if len(reference) == n else None)
        indices = _nearest_indices(rt, times, time_tolerance_s)
        safe = np.maximum(indices, 0)
        matched = (indices >= 0) & (abs(rw[safe] - wn) <= wavenumber_tolerance_cm1)
        # Reference/sample scan identities must coincide when provided.
        if "reference_scan_index" in native:
            matched &= _vector(native, "reference_scan_index", len(reference), dtype=int)[safe] == _vector(native, "scan_index", n, 0, int)
        flags[~matched] |= Quality.UNMATCHED_REFERENCE
        matched_reference[matched] = reference[safe[matched]]
        flags[~np.isfinite(matched_reference) | (matched_reference <= 0)] |= Quality.INVALID_REFERENCE
        if "reference_clipped" in native:
            flags[_vector(native, "reference_clipped", len(reference), dtype=bool)[safe]] |= Quality.CLIPPED
        if "reference_unlocked" in native:
            flags[_vector(native, "reference_unlocked", len(reference), dtype=bool)[safe]] |= Quality.UNLOCKED
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            ratio = signal / matched_reference
            rv = _vector(native, "reference_variance", len(reference), np.nan)[safe]
            variance = sample_var / matched_reference**2 + signal**2*rv/matched_reference**4 - 2*signal*covariance/matched_reference**3
        known = np.isfinite(sample_var) & np.isfinite(rv) & np.isfinite(covariance)
        invalid_cov = known & ((sample_var < 0) | (rv < 0) | (covariance**2 > sample_var*rv*(1+1e-12)))
        flags[invalid_cov] |= Quality.INVALID_UNCERTAINTY
        variance[invalid_cov | ~known] = np.nan
    elif mode != "single":
        raise ValueError("Detector mode must be single or dual")
    flags[~np.isfinite(ratio) | (ratio <= 0)] |= Quality.INVALID_SAMPLE
    ratio[flags != 0] = np.nan
    variance[flags != 0] = np.nan
    return {"ratio": ratio, "variance": variance, "quality_flags": flags,
            "matched_reference": matched_reference, "covariance": covariance,
            "sample_time_s": times, "wavenumber_cm1": wn}


def _spectral_match(source, target, values, *, tolerance_cm1=0., sequential=False):
    """Use measured coordinates and direction without synthesizing support."""
    sw = _vector(source, "wavenumber_cm1")
    tw = _vector(target, "wavenumber_cm1")
    ss = _vector(source, "scan_index", len(sw), 0, int)
    ts = _vector(target, "scan_index", len(tw), 0, int)
    sd = _vector(source, "direction", len(sw), 1, int)
    td = _vector(target, "direction", len(tw), 1, int)
    output = np.full(len(tw), np.nan)
    for direction in np.unique(td):
        for scan in np.unique(ts) if sequential else (None,):
            target_mask = (td == direction) & ((ts == scan) if sequential else True)
            source_mask = (sd == direction) & ((ss == scan) if sequential else True)
            positions = np.flatnonzero(source_mask)
            if not len(positions):
                continue
            nearest = _nearest_indices(sw[positions], tw[target_mask], tolerance_cm1)
            matched = nearest >= 0
            out_positions = np.flatnonzero(target_mask)[matched]
            output[out_positions] = np.asarray(values)[positions[nearest[matched]]]
    return output


def process_block(native, baseline, *, mode, pump_time_s, blank=None, baseline_blank=None, balance=None,
                  time_tolerance_s=0., wavenumber_tolerance_cm1=0., cancel=None):
    if cancel:
        cancel()
    if not np.isfinite(pump_time_s):
        raise ValueError("A retained pump timing reference is required")
    current = detector_ratio(native, mode=mode, time_tolerance_s=time_tolerance_s,
                             wavenumber_tolerance_cm1=wavenumber_tolerance_cm1)
    base = detector_ratio(baseline, mode=mode, time_tolerance_s=time_tolerance_s,
                          wavenumber_tolerance_cm1=wavenumber_tolerance_cm1)
    q, qvar = current["ratio"].copy(), current["variance"].copy()
    q0, q0var = base["ratio"].copy(), base["variance"].copy()
    flags = current["quality_flags"].copy()
    absolute, transmission = None, None
    if mode == "single" and blank is not None:
        blank_data = detector_ratio(blank, mode="single")
        b = _spectral_match(blank, native, blank_data["ratio"], tolerance_cm1=wavenumber_tolerance_cm1)
        # A blank is reusable for matching measured trajectories. Its scan
        # ordinal and the observation schedule are not spectral coordinates.
        base_blank = blank if baseline_blank is None else baseline_blank
        base_blank_data = blank_data if baseline_blank is None else detector_ratio(base_blank, mode="single")
        b0 = _spectral_match(base_blank, baseline, base_blank_data["ratio"], tolerance_cm1=wavenumber_tolerance_cm1)
        bv = _spectral_match(blank, native, blank_data["variance"], tolerance_cm1=wavenumber_tolerance_cm1)
        b0v = _spectral_match(base_blank, baseline, base_blank_data["variance"], tolerance_cm1=wavenumber_tolerance_cm1)
        flags[~np.isfinite(b) | (b <= 0)] |= Quality.INVALID_BLANK
        with np.errstate(divide="ignore", invalid="ignore"):
            qvar = qvar/b**2 + q**2*bv/b**4
            q0var = q0var/b0**2 + q0**2*b0v/b0**4
            q /= b
            q0 /= b0
        transmission = q.copy()
        with np.errstate(divide="ignore", invalid="ignore"):
            absolute = -np.log10(transmission)
    matched_q0 = _spectral_match(baseline, native, q0, tolerance_cm1=wavenumber_tolerance_cm1)
    matched_q0var = _spectral_match(baseline, native, q0var, tolerance_cm1=wavenumber_tolerance_cm1)
    flags[~np.isfinite(matched_q0) | (matched_q0 <= 0)] |= Quality.MISSING_BASELINE
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        delta = -np.log10(q / matched_q0)
        # Assumes separate preliminary noise independent of pumped observations;
        # unknown covariance/variance remains unknown instead of becoming zero.
        delta_var = (qvar/q**2 + matched_q0var/matched_q0**2) / math.log(10)**2
    if mode == "dual" and balance is not None:
        bvalues = _vector(balance, "balance")
        factor = _spectral_match(balance, native, bvalues, tolerance_cm1=wavenumber_tolerance_cm1)
        with np.errstate(divide="ignore", invalid="ignore"):
            transmission = np.where(factor > 0, q/factor, np.nan)
            absolute = -np.log10(transmission)
    valid = (flags == 0) & np.isfinite(delta)
    delta[~valid], delta_var[~valid] = np.nan, np.nan
    if absolute is not None:
        absolute[flags != 0] = np.nan
    if cancel:
        cancel()
    point_times = current["sample_time_s"]-float(pump_time_s)
    if all(key in native for key in ("native_sample_ticks", "pump_timestamp_ticks", "clockbase_hz")):
        ticks = np.asarray(native["native_sample_ticks"])
        pump_tick = int(np.asarray(native["pump_timestamp_ticks"]).item())
        clockbase = float(np.asarray(native["clockbase_hz"]).item())
        if ticks.shape != point_times.shape or ticks.dtype.kind not in "iu" or not math.isfinite(clockbase) or clockbase <= 0:
            raise ValueError("Pointwise tick timing requires aligned integer ticks and a positive native clockbase")
        # Python integers preserve sign and avoid unsigned underflow before
        # conversion. Tick differences remain precise even after long uptime.
        point_times = np.fromiter((int(tick)-pump_tick for tick in ticks), dtype=float, count=len(ticks))/clockbase
        point_times -= float(np.asarray(native.get("pump_optical_offset_s", 0.)).item())
        if bool(np.asarray(native.get("sample_response_correction_applied", native.get("detector_response_correction_applied", False))).item()):
            point_times -= float(np.asarray(native.get("sample_latency_s", 0.)).item())
    time_reference = str(np.asarray(native.get("time_reference", "retained_epoch")).item())
    return {"analysis_version": ANALYSIS_VERSION,
            "time_s": point_times,
            "time_reference": time_reference,
            "optical_arrival_observed": time_reference == "optical_arrival",
            "sample_time_s": current["sample_time_s"], "wavenumber_cm1": current["wavenumber_cm1"],
            "ratio": q, "q0": matched_q0, "delta_absorbance": delta, "variance": delta_var,
            "ratio_variance": qvar, "sample_reference_covariance": current["covariance"],
            "absorbance": absolute, "transmission": transmission, "valid": valid, "quality_flags": flags,
            "scan_index": _vector(native, "scan_index", len(q), 0, int),
            "direction": _vector(native, "direction", len(q), 1, int),
            "normalization": ("-log10(Q/Q0)" if mode == "dual" else
                              "-log10((S/blank)/(S0/blank0))" if blank is not None else "-log10(S/S0)"),
            "absolute_label": ("Absorbance" if absolute is not None else
                               "Reference-normalized signal Q=S/R" if mode == "dual" else "Sample signal S"),
            "limitations": ["Pointwise measured scan trajectory; no interpolation across gaps.",
                            "Apparent recovery alone does not establish a molecular mechanism.",
                            "Baseline covariance with pumped measurements is assumed zero; unknown uncertainty remains NaN."]}


def band_summary(processed, lower_cm1, upper_cm1, *, plateau_tolerance=None,
                 plateau_points=3, plateau_min_span_s=0.):
    """Band-specific apparent residuals, normalized to the first observed bleach.

    These are finite-window observed fractions, not the total photolyzed or
    geminate population. Missing/unsupported scans never satisfy a plateau.
    """
    if not np.isfinite([lower_cm1, upper_cm1]).all() or lower_cm1 > upper_cm1:
        raise ValueError("Band bounds must be finite and ordered")
    if plateau_points < 2:
        raise ValueError("Plateau requires at least two prospectively selected observations")
    wn, times = np.asarray(processed["wavenumber_cm1"]), np.asarray(processed["time_s"])
    values, scans = np.asarray(processed["delta_absorbance"]), np.asarray(processed["scan_index"])
    in_band = (wn >= lower_cm1) & (wn <= upper_cm1)
    rows = []
    for scan in dict.fromkeys(scans.tolist()):
        mask = (scans == scan) & in_band
        valid = mask & np.isfinite(values) & np.isfinite(times)
        complete = bool(mask.any() and valid.sum() == mask.sum())
        rows.append({"scan_index": int(scan), "time_s": float(np.mean(times[valid])) if valid.any() else None,
                     "time_min_s": float(np.min(times[valid])) if valid.any() else None,
                     "time_max_s": float(np.max(times[valid])) if valid.any() else None,
                     "delta_absorbance": float(np.mean(values[valid])) if valid.any() else None,
                     "support_points": int(valid.sum()), "complete": complete})
    observed = [r for r in rows if r["complete"] and r["time_s"] > 0]
    first = observed[0]["delta_absorbance"] if observed else None
    last = observed[-1]["delta_absorbance"] if observed else None
    fraction = last/first if first is not None and first < 0 and last is not None else None
    tail = rows[-plateau_points:]
    plateau = False
    if plateau_tolerance is not None:
        if not math.isfinite(plateau_tolerance) or plateau_tolerance < 0:
            raise ValueError("Prospective plateau tolerance must be finite and nonnegative")
        if len(tail) == plateau_points and all(r["complete"] and r["time_s"] > 0 for r in tail):
            v = np.asarray([r["delta_absorbance"] for r in tail])
            plateau = bool(np.ptp(v) <= plateau_tolerance and tail[-1]["time_s"]-tail[0]["time_s"] >= plateau_min_span_s)
    return {"band_cm1": [lower_cm1, upper_cm1], "observations": rows,
            "unrecovered_fraction": fraction, "fraction_basis": "last/first observed negative band signal; not total photolysis",
            "plateau": plateau, "right_censored": fraction is not None and fraction > 0,
            "mechanism": "apparent recovery; mechanism unestablished"}


class PlateauTracker:
    """Bounded prospective per-band plateau checks across separate bursts.

    An unsupported point/empty band breaks the plateau sequence. Baseline noise
    and IRF are not converted into mechanistic lifetime claims by this rule.
    """
    def __init__(self, windows_cm1, *, relative_tolerance=None, required_bursts=3):
        from collections import deque
        if required_bursts < 3:
            raise ValueError("Plateau requires at least three declared bursts")
        if relative_tolerance is not None and not 0 < relative_tolerance < 1:
            raise ValueError("Prospective relative plateau tolerance must lie between zero and one")
        self.windows = tuple(tuple(pair) for pair in windows_cm1)
        if any(len(pair) != 2 or not np.isfinite(pair).all() or pair[0] >= pair[1] for pair in self.windows):
            raise ValueError("Plateau band windows require finite increasing cm-1 bounds")
        self.tolerance, self.count = relative_tolerance, required_bursts
        self.tails = [deque(maxlen=required_bursts) for _ in self.windows]
        self.first = [None for _ in self.windows]
        self.last = [None for _ in self.windows]
        self.last_block = None

    def update(self, processed, block_id):
        if block_id == self.last_block:
            raise ValueError("A plateau observation cannot count the same burst twice")
        self.last_block = block_id
        wn, values, times = (np.asarray(processed[name]) for name in ("wavenumber_cm1", "delta_absorbance", "time_s"))
        bands = []
        for i, (lo, hi) in enumerate(self.windows):
            mask = (wn >= lo) & (wn <= hi) & (times > 0)
            complete = bool(mask.any() and np.isfinite(values[mask]).all())
            mean = float(np.mean(values[mask])) if complete else None
            observation = {"block_id": str(block_id), "value": mean,
                "time_min_s": float(np.min(times[mask])) if mask.any() else None,
                "time_max_s": float(np.max(times[mask])) if mask.any() else None,
                "support_points": int(mask.sum()), "complete": complete}
            self.tails[i].append(observation)
            if self.first[i] is None and complete:
                self.first[i] = observation
            if complete:
                self.last[i] = observation
            first, last = self.first[i], self.last[i]
            denominator = first["value"] if first else None
            plateau = False
            if (self.tolerance is not None and denominator is not None and denominator < 0
                    and len(self.tails[i]) == self.count and all(r["complete"] for r in self.tails[i])):
                plateau = bool(np.ptp([r["value"] for r in self.tails[i]]) <= abs(denominator)*self.tolerance)
            fraction = last["value"]/denominator if last and denominator is not None and denominator < 0 else None
            bands.append({"band_cm1": [lo, hi], "first_observation": first, "last_observation": last,
                "recent_observations": list(self.tails[i]), "plateau": plateau,
                "unrecovered_fraction": fraction, "right_censored": fraction is not None and fraction > 0,
                "fraction_basis": "last/first observed band mean; unresolved prompt loss is not measured"})
        return {"bands": bands, "reached": bool(bands) and all(b["plateau"] for b in bands),
                "relative_tolerance": self.tolerance, "required_bursts": self.count,
                "mechanism": "apparent recovery; mechanism unestablished"}


def load_spectral_record(path, block_id=None):
    """Load one bounded reconstructed block, skipping raw SDK poll chunks."""
    from pathlib import Path
    import json
    from .persistence import _inside
    root = Path(path)
    with (root / "events.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            event = json.loads(line)
            if event["kind"] != "native_chunk":
                continue
            payload = event["payload"]
            name = payload.get("block_id", "")
            if block_id is not None and name not in (block_id, "spectral-"+block_id, "blank-"+block_id,
                                                     "unpumped-"+block_id, "unpumped-blank-"+block_id):
                continue
            # Reading raw polls just to identify them can scale with dark waits.
            arrays = payload.get("arrays", {})
            if not all(key in arrays for key in ("sample", "sample_time_s", "wavenumber_cm1")):
                continue
            with np.load(_inside(root, payload["path"]), allow_pickle=False) as data:
                return {key: data[key] for key in data.files}
    raise ValueError(f"No retained spectral record for {block_id or 'preliminary'} in {root}")


def analyze_run(run_path, baseline_bundle=None, cancel_check=None, progress=None, *, store=None):
    """Stream bounded spectral blocks into reproducible quantitative artifacts.

    Used before normal finalization and for explicit offline reanalysis. It
    never alters the pump epoch, original arrays, disposition or prior analysis.
    """
    from pathlib import Path
    from uuid import uuid4
    import json
    from .persistence import RunStore, load_run, _inside
    root = Path(run_path)
    loaded = load_run(root)
    settings = loaded["metadata"].get("plan", {}).get("settings", loaded["metadata"].get("settings", {}))
    actual_settings = root / "records" / "actual-settings.json"
    if actual_settings.is_file():
        settings = json.loads(actual_settings.read_text(encoding="utf-8")).get("settings", settings)
    mode = loaded["metadata"]["mode"]
    if baseline_bundle is None:
        baseline_bundle = json.loads((root / "records" / "selected-baselines.json").read_text(encoding="utf-8"))
    preliminary = baseline_bundle.get("preliminary") or baseline_bundle
    if not preliminary or not (preliminary.get("output_path") or preliminary.get("native") is not None):
        raise ValueError("No sample baseline supplied; raw acquisition remains available")
    base_native = load_spectral_record(preliminary["output_path"]) if preliminary.get("output_path") else preliminary["native"]
    blank_record = baseline_bundle.get("blank")
    epochs = [e["payload"] for e in loaded["events"] if e["kind"] == "pump_epoch_observed"]
    if not epochs:
        epochs = [e["payload"]["epoch"] for e in loaded["events"] if e["kind"] == "explicit_continuation"]
    if not epochs or not (epochs[-1].get("independently_observed") or epochs[-1].get("electrically_observed")):
        raise ValueError("No observed pump timing reference is retained")
    epoch = epochs[-1]
    time_reference = "optical_arrival" if epoch.get("independently_observed") else "electrical_trigger"
    plateau_enabled = bool(settings.get("plateau_enabled"))
    windows = settings.get("plateau_band_windows_cm1", ()) if plateau_enabled else ()
    tracker = PlateauTracker(windows, relative_tolerance=settings.get("plateau_relative_tolerance") if plateau_enabled else None,
                             required_bursts=settings.get("plateau_required_bursts", 3) if plateau_enabled else 3)
    parents = [e["payload"].get("source_output_path") for e in loaded["events"] if e["kind"] == "explicit_continuation"]
    prior_summary = prime_tracker(tracker, parents[-1], cancel=cancel_check) if parents and parents[-1] else None
    owned_store = store or RunStore(root, {}, create=False)
    native_entries = [e["payload"] for e in loaded["events"] if e["kind"] == "native_chunk"
                      and e["payload"].get("block_id", "").startswith("spectral-")]
    processed_paths, processed_versions, summary = [], set(), prior_summary or {"bands": [], "reached": False}
    for index, entry in enumerate(native_entries):
        if cancel_check:
            cancel_check()
        block_id = entry["block_id"].removeprefix("spectral-")
        existing = root / "chunks" / ("processed-"+block_id+".npz")
        committed = any(e["kind"] == "native_chunk" and e["payload"].get("block_id") == "processed-"+block_id for e in loaded["events"])
        if committed:
            with np.load(existing, allow_pickle=False) as source:
                processed = {key: source[key] for key in source.files}
            relative = existing.relative_to(root).as_posix()
        else:
            with np.load(_inside(root, entry["path"]), allow_pickle=False) as source:
                native = {key: source[key] for key in source.files}
            native.setdefault("time_reference", time_reference)
            blank_native, first_blank = None, None
            if mode == "single" and blank_record:
                try:
                    blank_native = load_spectral_record(blank_record["output_path"], block_id)
                except ValueError:
                    # New blanks are compact spectra, while v1 runs may have
                    # retained an entire unpumped schedule. Both remain usable.
                    blank_native = load_spectral_record(blank_record["output_path"])
                first_blank = load_spectral_record(blank_record["output_path"])
            evidence = settings.get("hardware_evidence", {}).get("operating_configuration", {})
            matching = evidence.get("detector_matching", {})
            time_tolerance = settings.get("detector_matching_time_tolerance_s")
            spectral_tolerance = settings.get("wavenumber_matching_tolerance_cm1")
            processed = process_block(native, base_native, mode=mode, pump_time_s=epoch["pump_time_s"],
                blank=blank_native, baseline_blank=first_blank,
                time_tolerance_s=float(time_tolerance if time_tolerance is not None else matching.get("time_tolerance_s", 0.)),
                wavenumber_tolerance_cm1=float(spectral_tolerance if spectral_tolerance is not None else matching.get("wavenumber_tolerance_cm1", 0.)), cancel=cancel_check)
            arrays = {k: v for k, v in processed.items() if isinstance(v, np.ndarray) or np.isscalar(v)}
            relative = owned_store.save_chunk("processed-"+block_id, arrays)
        processed_versions.add(str(np.asarray(processed.get("analysis_version", "legacy_unversioned")).item()))
        processed_paths.append(relative)
        summary = tracker.update(processed, block_id)
        if progress:
            progress({"stage": "analysis", "message": f"Processed {index+1}/{len(native_entries)} retained spectral blocks",
                      "fraction": (index+1)/max(1, len(native_entries))})
    summary.update(analysis_version=ANALYSIS_VERSION, processed_analysis_versions=sorted(processed_versions),
        processed_block_count=len(processed_paths),
        equations=("Delta A=-log10(Q/Q0); Q=S/R" if mode == "dual" else
                   "Delta A=-log10(Q/Q0); Q=S/blank" if blank_record else "Delta A=-log10(S/S0)"),
        prior_observation_path=parents[-1] if parents else None,
        parent_native_paths=[e["path"] for e in native_entries],
        baseline_source=preliminary.get("output_path"), blank_source=blank_record.get("output_path") if blank_record else None,
        time_reference=time_reference, optical_arrival_observed=bool(epoch.get("independently_observed")),
        claim="Apparent recovery on observed scan support; optical arrival and response resolution are reported only when measured")
    owned_store.save_record("analysis-"+uuid4().hex, summary)
    return {"output_path": str(root), "processed_paths": processed_paths, "summary": summary}


def prime_tracker(tracker, source_path, *, cancel=None):
    """Restore the observed initial population across explicitly linked runs.

    Original arrays stay in their original run. No missing burst is invented.
    A missing early analysis leaves fractions unavailable until explicit offline
    reanalysis; it never resets the physical epoch or fires a replacement pump.
    """
    from pathlib import Path
    from .persistence import load_run, _inside
    chain, seen = [], set()
    current = Path(source_path).resolve()
    while current is not None:
        if cancel:
            cancel()
        if current in seen:
            raise ValueError("Cyclic continuation provenance")
        seen.add(current)
        loaded = load_run(current)
        chain.append(loaded)
        parents = [e["payload"].get("source_output_path") for e in loaded["events"] if e["kind"] == "explicit_continuation"]
        current = Path(parents[-1]).resolve() if parents and parents[-1] else None
    summary = None
    for source in reversed(chain):
        for event in source["events"]:
            if cancel:
                cancel()
            if event["kind"] != "native_chunk" or not event["payload"].get("block_id", "").startswith("processed-"):
                continue
            with np.load(_inside(Path(source["path"]), event["payload"]["path"]), allow_pickle=False) as arrays:
                processed = {key: arrays[key] for key in arrays.files}
            summary = tracker.update(processed, source["path"]+"/"+event["payload"]["block_id"])
    return summary
