"""Measured-coordinate dual-detector normalization and reproducible records.

The reference is simultaneous; the separately reviewed sample baseline is Q0,
never an optical path balance B. Missing support remains missing throughout.
"""
from __future__ import annotations

from control_app.paths import research_output_path

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
import csv
import json

import numpy as np

from control_app.workflows.phase_scan_data import (
    DUAL_DETECTOR_MODE, Spectrum, _reconstruct_entries, compatible_readbacks,
    interpolate_spectrum, interpolate_supported, load_native, save_native, utc_now, write_json,
)
from control_app.workflows.regular_phase_scan_data import (
    RegularScanStore, compatibility_conflicts as _compatibility_conflicts,
    stable_device_configuration as _stable_device_configuration,
)

SCHEMA_VERSION = "dual-detector-phase-scan/1.0"
ANALYSIS_VERSION = "simultaneous-reference-normalization/1.0"
DETECTOR_MODE = DUAL_DETECTOR_MODE
INVALID_REASONS = {
    1: "missing_or_nonfinite_sample", 2: "nonpositive_sample",
    4: "missing_or_nonfinite_reference", 8: "nonpositive_reference",
    16: "unsupported_measured_wavenumber", 32: "unsupported_reference_timestamp",
    64: "detector_timestamps_not_simultaneous", 128: "unsupported_unpumped_baseline",
    256: "nonpositive_logarithm_argument", 512: "unsupported_channel_balance",
    1024: "unsupported_phase_reconstruction",
    2048: "sample_reference_ratio_outside_floating_point_range",
}


def compatibility_conflicts(left, right, prefix=""):
    return [text.replace("saved blank", "saved baseline").replace("blank ", "baseline ")
            for text in _compatibility_conflicts(left, right, prefix)]


def _selected_configuration(selection):
    selection = selection.get("selected", selection)
    keys = ("order", "timeconstant_s", "rate_sps", "timing_rate_sps", "enabled_streams",
            "filter_group_delay_s", "input", "adcselect", "demodulator", "signal",
            "device_id", "oscselect", "harmonic")
    result = {key: deepcopy(selection[key]) for key in keys if key in selection}
    for role in ("sample", "reference"):
        config = selection.get(role, selection.get("detectors", {}).get(role))
        if config is not None:
            result[role] = _selected_configuration(config)
    return result


def experiment_contract(plan):
    assignments = getattr(plan, "detector_assignments", None)
    if not assignments or not all(role in assignments for role in ("sample", "reference")):
        raise ValueError("A dual-detector plan needs maintained sample/reference assignments")
    return {
        "detector_mode": DUAL_DETECTOR_MODE, "settings": asdict(plan.settings),
        "scan_count": plan.total_scans, "frame_period_s": plan.frame_period_s,
        "first_phase_delay_us": plan.first_phase_delay_us,
        "last_phase_delay_us": plan.last_phase_delay_us, "fire_to_qswitch_us": 250.,
        "detector_assignments": deepcopy(assignments),
        "hf2li_selected": _selected_configuration(plan.hf2_selection),
        "channel_balance_calibration": deepcopy(getattr(plan, "channel_balance_calibration", {}) or {}),
    }


def stable_device_configuration(readback):
    result = _stable_device_configuration(readback)
    for key in ("detector_assignments", "channel_balance_calibration", "timing_assignments"):
        if key in readback:
            result[key] = deepcopy(readback[key])
    return result


def _supported_by_segment(x, values, target, segments=None, target_segments=None, *, max_gap=None):
    x, values, target = (np.asarray(v) for v in (x, values, target))
    segments = np.zeros(len(x), int) if segments is None else np.asarray(segments)
    output = np.full(target.shape, np.nan)
    for segment in np.unique(segments):
        indices = np.flatnonzero((segments == segment) & np.isfinite(x))
        if not len(indices):
            continue
        # An unknown coordinate is a break in support, even when removing it
        # would leave two plausible endpoints on the same monotonic segment.
        for run in np.split(indices, np.flatnonzero(np.diff(indices) != 1)+1):
            axis = x[run]
            gap = max_gap
            if gap is None and len(axis) > 1:
                gap = np.median(np.abs(np.diff(axis))) * 1.75
            part = interpolate_supported(axis, values[run], target, max_gap=gap)
            valid = np.isfinite(part)
            if target_segments is not None:
                valid &= np.asarray(target_segments) == segment
            output[valid] = part[valid]
    return output


def align_detector_spectrum(sample_time_s, sample_r, sample_wavenumber_cm1,
                            reference_time_s, reference_r, reference_wavenumber_cm1, *,
                            sample_filter_delay_s, reference_filter_delay_s, metadata,
                            pump_time_s=None, sample_segment_id=None, reference_segment_id=None):
    """Match measured wavelength AND physical acquisition time, preserving gaps.

    Input timestamps are native clock-derived times. Wavenumbers must already
    be evaluated from observed markers at timestamp minus the detector delay.
    The output timestamps use that effective time. Delay subtraction is an
    explicit low-frequency filter-delay estimate, not impulse deconvolution.
    """
    st, sv, sw, rt, rv, rw = [np.asarray(v, dtype=float) for v in (
        sample_time_s, sample_r, sample_wavenumber_cm1,
        reference_time_s, reference_r, reference_wavenumber_cm1)]
    for times, values, wn, role in ((st, sv, sw, "sample"), (rt, rv, rw, "reference")):
        if times.ndim != 1 or times.shape != values.shape or times.shape != wn.shape:
            raise ValueError(f"{role} native timestamps, signal and measured wavelengths must match")
        if len(times) < 2 or not np.isfinite(times).all() or not np.all(np.diff(times) > 0):
            raise ValueError(f"{role} needs increasing finite native timestamps")
    delays = np.asarray([sample_filter_delay_s, reference_filter_delay_s], float)
    if not np.isfinite(delays).all() or (delays < 0).any():
        raise ValueError("Both detector filter delays must be explicit finite nonnegative values")
    effective_st, effective_rt = st-delays[0], rt-delays[1]
    selected = np.isfinite(sw)
    if selected.sum() < 2:
        raise ValueError("Fewer than two sample points have measured wavelength support after filter delay")
    segments = None if sample_segment_id is None else np.asarray(sample_segment_id)[selected]
    sw, sv, effective_st = sw[selected], sv[selected], effective_st[selected]
    valid_reference = np.where(np.isfinite(rv) & (rv > 0), rv, np.nan)
    reference_on_wn = _supported_by_segment(rw, valid_reference, sw, reference_segment_id, segments)
    time_on_wn = _supported_by_segment(rw, effective_rt, sw, reference_segment_id, segments)
    # A missing tick must not be bridged merely because wavelength mapping is smooth.
    reference_on_time = _supported_by_segment(effective_rt, valid_reference, effective_st,
        reference_segment_id, segments, max_gap=np.median(np.diff(effective_rt))*1.75)
    interval = min(np.median(np.diff(st)), np.median(np.diff(rt)))
    tolerance = max(interval*1e-3, 32*np.finfo(float).eps*max(1., np.max(np.abs(st)), np.max(np.abs(rt))))
    simultaneous = np.isfinite(time_on_wn) & (np.abs(time_on_wn-effective_st) <= tolerance)
    reasons = np.zeros(len(sw), np.uint16)
    reasons[~np.isfinite(sv)] |= 1
    reasons[np.isfinite(sv) & (sv <= 0)] |= 2
    # Retain whether an invalid reference endpoint was missing or nonpositive.
    for flag, bad in ((4, ~np.isfinite(rv)), (8, np.isfinite(rv) & (rv <= 0))):
        affected = _supported_by_segment(rw, bad.astype(float), sw, reference_segment_id, segments)
        reasons[np.nan_to_num(affected, nan=0.) > 0] |= flag
    reasons[~np.isfinite(time_on_wn)] |= 16
    reasons[~np.isfinite(reference_on_time)] |= 32
    reasons[np.isfinite(time_on_wn) & ~simultaneous] |= 64
    reasons[~np.isfinite(reference_on_wn) & ((reasons & (4 | 8 | 16)) == 0)] |= 16
    supported = simultaneous & np.isfinite(reference_on_time) & np.isfinite(reference_on_wn)
    reference_on_wn[~supported] = np.nan
    details = deepcopy(metadata)
    details.update(detector_mode=DUAL_DETECTOR_MODE, alignment={
        "method": "measured_wavenumber_with_effective_timestamp_agreement",
        "wavenumbers_evaluated_at": "native_timestamp_minus_detector_filter_delay",
        "sample_filter_delay_s": float(delays[0]), "reference_filter_delay_s": float(delays[1]),
        "filter_delay_basis": "HF2LI configured low-frequency group-delay estimate; no deconvolution",
        "timestamp_tolerance_s": float(tolerance),
        "sample_native_time_s": st.copy(), "reference_native_time_s": rt.copy(),
        "sample_selected_native_indices": np.flatnonzero(selected),
        "sample_outside_marker_support_indices": np.flatnonzero(~selected),
        "reference_measured_wavenumber_cm1": rw.copy(), "reference_native_r": rv.copy(),
        "invalid_reasons": reasons, "invalid_reason_definitions": INVALID_REASONS,
    })
    return Spectrum(sw, sv, reference_on_wn, effective_st, pump_time_s, details, segments).validate()


def validate_dual_spectrum(spectrum):
    spectrum.validate()
    if spectrum.metadata.get("detector_mode") != DUAL_DETECTOR_MODE:
        raise ValueError("Select dual-detector data; single-detector records cannot supply a simultaneous reference")
    if spectrum.metadata.get("wavenumber_basis") not in {"measured", "controller_markers"}:
        raise ValueError("Dual-detector normalization requires measured wavelength support")
    alignment = spectrum.metadata.get("alignment", {})
    if alignment.get("method") != "measured_wavenumber_with_effective_timestamp_agreement":
        raise ValueError("Dual-detector data need retained detector filter-delay and timestamp alignment")
    return spectrum


def sample_reference_ratio(spectrum):
    validate_dual_spectrum(spectrum)
    sample, reference = np.asarray(spectrum.sample_r, float), np.asarray(spectrum.reference_r, float)
    valid = np.isfinite(sample) & (sample > 0) & np.isfinite(reference) & (reference > 0)
    ratio = np.full(sample.shape, np.nan)
    with np.errstate(over="ignore", under="ignore", divide="ignore", invalid="ignore"):
        np.divide(sample, reference, out=ratio, where=valid)
    ratio[~np.isfinite(ratio) | (ratio <= 0)] = np.nan
    return ratio


def _ratio_invalid_reasons(spectrum, ratio):
    reasons = np.asarray(spectrum.metadata["alignment"]["invalid_reasons"], np.uint16).copy()
    sample, reference = np.asarray(spectrum.sample_r, float), np.asarray(spectrum.reference_r, float)
    reasons[~np.isfinite(sample)] |= 1
    reasons[np.isfinite(sample) & (sample <= 0)] |= 2
    positive = np.isfinite(sample) & (sample > 0) & np.isfinite(reference) & (reference > 0)
    reasons[positive & ~np.isfinite(ratio)] |= 2048
    return reasons


def validate_baseline(spectrum, plan=None):
    validate_dual_spectrum(spectrum)
    if spectrum.pump_time_s is not None:
        raise ValueError("The sample/reference baseline must be unpumped")
    if np.isfinite(sample_reference_ratio(spectrum)).sum() < 2:
        raise ValueError("The preliminary sample/reference baseline needs two supported positive measurements")
    if plan is not None and spectrum.metadata.get("acquisition_settings"):
        conflicts = compatibility_conflicts(spectrum.metadata["acquisition_settings"], experiment_contract(plan))
        if conflicts:
            raise ValueError("Preliminary baseline incompatible: " + "; ".join(conflicts))
    return spectrum


@dataclass(frozen=True)
class ChannelBalanceCalibration:
    bundle_id: str
    source: str
    manifest: dict
    wavenumber_cm1: np.ndarray
    response_ratio: np.ndarray
    segment_id: np.ndarray | None = None

    def validate(self, plan=None, *, experiment=None, at_utc=None, device_settings=None):
        manifest = self.manifest
        if (manifest.get("status") != "PROMOTED" or manifest.get("kind") != "dual_detector_channel_balance"
                or manifest.get("bundle_id") != self.bundle_id or not manifest.get("schema_version")
                or manifest.get("validation", {}).get("status") != "VALIDATED"
                or not manifest.get("validation", {}).get("reviewer")
                or manifest.get("equivalent_optical_contents") is not True):
            raise ValueError("Absolute absorbance requires a validated promoted channel/path-balance calibration")
        validity = manifest.get("validity", {})
        if not validity.get("detector_assignments") or not validity.get("hf2li_selected"):
            raise ValueError("Channel balance is missing its detector/configuration validity scope")
        instant = datetime.now(UTC) if at_utc is None else datetime.fromisoformat(str(at_utc).replace("Z", "+00:00"))
        if instant.tzinfo is None:
            raise ValueError("Channel-balance applicability requires an explicit UTC acquisition timestamp")
        for name, expired in (("valid_until_utc", True), ("valid_from_utc", False)):
            boundary = validity.get(name)
            if boundary:
                timestamp = datetime.fromisoformat(str(boundary).replace("Z", "+00:00"))
                if timestamp.tzinfo is None or (instant > timestamp if expired else instant < timestamp):
                    raise ValueError("Channel-balance calibration is outside its validity period")
        if plan is not None:
            experiment = experiment_contract(plan)
        if experiment is not None:
            for key in ("detector_assignments", "hf2li_selected"):
                if not compatible_readbacks(validity[key], experiment.get(key)):
                    raise ValueError(f"Channel-balance {key} differs from the resolved dual-detector configuration")
            optional = {"settings": experiment.get("settings"), "experiment_contract": experiment,
                        "hf2li_detector_settings": (device_settings or {}).get("hf2li_detector_settings")}
            for key, current in optional.items():
                if key in validity:
                    conflicts = _scope_conflicts(validity[key], current, key)
                    if conflicts:
                        raise ValueError("Channel-balance applicability differs: " + "; ".join(conflicts))
        known = {"detector_assignments", "hf2li_selected", "valid_until_utc", "valid_from_utc",
                 "settings", "experiment_contract", "hf2li_detector_settings", "note"}
        unknown = set(validity)-known
        if unknown:
            raise ValueError("Channel-balance applicability contains unsupported requirements: " + ", ".join(sorted(unknown)))
        wn, ratio = np.asarray(self.wavenumber_cm1, float), np.asarray(self.response_ratio, float)
        if (wn.ndim != 1 or wn.shape != ratio.shape or len(wn) < 2 or not np.isfinite(wn).all()
                or not (np.all(np.diff(wn) > 0) or np.all(np.diff(wn) < 0))):
            raise ValueError("Channel balance needs a monotonic measured wavelength axis and matching response ratios")
        if self.segment_id is not None and np.asarray(self.segment_id).shape != wn.shape:
            raise ValueError("Channel-balance segment IDs do not match its wavelength axis")
        return self

    def to_dict(self):
        return asdict(self)

    def contract(self):
        return {"bundle_id": self.bundle_id, "source": self.source,
                "schema_version": self.manifest.get("schema_version"),
                "validation": deepcopy(self.manifest.get("validation")),
                "validity": deepcopy(self.manifest.get("validity"))}


def _scope_conflicts(required, actual, prefix=""):
    """A calibration can bound a subset of settings, but none may be ignored."""
    if isinstance(required, dict):
        if not isinstance(actual, dict):
            return [f"{prefix}: missing applicable configuration"]
        return [issue for key, value in required.items()
                for issue in _scope_conflicts(value, actual.get(key), f"{prefix}.{key}")]
    return [] if compatible_readbacks(required, actual) else [f"{prefix}: outside calibration scope"]


def load_channel_balance(plan=None, registry_root=None):
    """Read only explicitly promoted compatible balance bundles; never raw evidence.

    No valid registered balance means the ratio/delta workflow stays available.
    Multiple matching calibrations require an explicit bundle ID in the plan.
    """
    from control_app.paths import PROMOTED_BUNDLE_ROOT
    from control_app.promoted_bundles import load_bundle_registry, load_promoted_bundle, PromotedBundleError
    root = Path(registry_root or PROMOTED_BUNDLE_ROOT).resolve()
    try:
        registry = load_bundle_registry(root)
    except PromotedBundleError:
        return None
    requested = getattr(plan, "channel_balance_calibration", {}) or {}
    requested_id = requested.get("bundle_id") if isinstance(requested, dict) else None
    matches = []
    for row in registry["bundles"]:
        if not isinstance(row, dict) or row.get("status") != "PROMOTED":
            continue
        if requested_id and row.get("bundle_id") != requested_id:
            continue
        try:
            bundle = load_promoted_bundle(row["bundle_id"], root)
            bundle.path.resolve().relative_to(root)
            if bundle.manifest.get("kind") != "dual_detector_channel_balance":
                continue
            path = (bundle.path / bundle.manifest["response_ratio_file"]).resolve()
            path.relative_to(bundle.path.resolve())
            data = load_native(path)
            calibration = ChannelBalanceCalibration(bundle.bundle_id, str(path), bundle.manifest,
                data["wavenumber_cm1"], data["response_ratio"], data.get("segment_id")).validate(plan)
            matches.append(calibration)
        except (PromotedBundleError, OSError, ValueError, KeyError, TypeError):
            continue
    if requested_id and not matches:
        raise ValueError("The selected promoted channel-balance calibration is absent, invalid or incompatible")
    if len(matches) > 1:
        raise ValueError("More than one compatible channel-balance bundle is promoted; select its bundle ID in the plan")
    return matches[0] if matches else None


def _balance_on_spectrum(spectrum, calibration):
    if not isinstance(calibration, ChannelBalanceCalibration):
        raise ValueError("Absolute absorbance requires a validated promoted channel/path-balance calibration")
    contract = spectrum.metadata.get("acquisition_settings", {})
    if not contract.get("detector_assignments") or not contract.get("hf2li_selected"):
        raise ValueError("Absolute absorbance requires retained detector/configuration applicability for this spectrum")
    calibration.validate(experiment=contract, at_utc=spectrum.metadata.get("acquisition_utc"),
                         device_settings=spectrum.metadata)
    response = np.asarray(calibration.response_ratio, float)
    return _supported_by_segment(calibration.wavenumber_cm1,
        np.where(np.isfinite(response) & (response > 0), response, np.nan), spectrum.wavenumber_cm1,
        calibration.segment_id, spectrum.segment_id)


def absolute_absorbance(spectrum, calibration):
    ratio = sample_reference_ratio(spectrum)
    balance = _balance_on_spectrum(spectrum, calibration)
    return _log_ratio(ratio, balance)


def _log_ratio(numerator, denominator):
    numerator, denominator = np.asarray(numerator, float), np.asarray(denominator, float)
    valid = np.isfinite(numerator) & (numerator > 0) & np.isfinite(denominator) & (denominator > 0)
    result = np.full(numerator.shape, np.nan)
    # Difference of logarithms avoids overflow/underflow in the positive ratio.
    result[valid] = -np.log10(numerator[valid])+np.log10(denominator[valid])
    return result


def baseline_values(spectrum, calibration=None):
    ratio = sample_reference_ratio(spectrum)
    reasons = _ratio_invalid_reasons(spectrum, ratio)
    result = {"sample_reference_ratio": ratio, "values": ratio, "display_mode": "sample_reference_ratio",
              "invalid_reasons": reasons, "invalid_reason_definitions": INVALID_REASONS}
    if calibration is not None:
        values = absolute_absorbance(spectrum, calibration)
        reasons[np.isfinite(ratio) & ~np.isfinite(values)] |= 512
        result.update(absorbance=values, values=values, display_mode="absorbance")
    return result


def reconstruct_sequence(records, baseline, plan, *, calibration=None, cancel=None):
    """Calculate each measured S/R divided by the separately reviewed Q0 first."""
    if isinstance(baseline, dict):
        baseline = baseline["spectrum"]
    elif not isinstance(baseline, Spectrum):
        baseline = baseline.spectrum
    validate_baseline(baseline, plan)
    if calibration is not None:
        calibration.validate(plan)
    if [event for event, _ in records] != [plan.event_at(i) for i in range(plan.total_scans)]:
        raise ValueError("Dual-detector sequence has missing, duplicate, reordered or unexpected phase records")
    wn = np.sort(np.asarray(baseline.wavenumber_cm1))
    wn = wn[np.linspace(0, len(wn)-1, min(len(wn), 1024), dtype=int)]
    baseline_ratio = sample_reference_ratio(baseline)
    entries = {"sample_reference_ratio": [], "delta_absorbance": []}
    if calibration is not None:
        entries["absorbance"] = []
    pumped, per_scan, reasons_per_scan = [], {name: [] for name in entries}, []
    for event, spectrum in records:
        if cancel:
            cancel()
        ratio = sample_reference_ratio(spectrum)
        q0 = interpolate_spectrum(baseline, baseline_ratio, spectrum.wavenumber_cm1)
        values = {"sample_reference_ratio": ratio, "delta_absorbance": _log_ratio(ratio, q0)}
        reasons = _ratio_invalid_reasons(spectrum, ratio)
        reasons[~np.isfinite(q0) | (q0 <= 0)] |= 128
        reasons[np.isfinite(ratio) & (ratio <= 0)] |= 256
        if calibration is not None:
            values["absorbance"] = absolute_absorbance(spectrum, calibration)
            reasons[np.isfinite(ratio) & ~np.isfinite(values["absorbance"])] |= 512
        reasons_per_scan.append({"scan_index": event.scan_index, "wavenumber_cm1": spectrum.wavenumber_cm1,
                                "invalid_reasons": reasons})
        for name, value in values.items():
            per_scan[name].append(interpolate_spectrum(spectrum, value, wn))
        if event.pump_enabled:
            if spectrum.pump_time_s is None or not np.isfinite(spectrum.pump_time_s):
                raise ValueError("Every pumped dual-detector scan needs observed electrical pump sync")
            if spectrum.metadata.get("pump_time_basis") not in {"measured", "electrical_sync", "aux_input"}:
                raise ValueError("Commanded phase delays cannot replace measured pump timestamps")
            age = interpolate_spectrum(spectrum, spectrum.sample_time_s-spectrum.pump_time_s, wn)
            for name in entries:
                entries[name].append((event, age, per_scan[name][-1]))
            pumped.append(spectrum)
        elif spectrum.pump_time_s is not None:
            raise ValueError("An unpumped dual-detector scan contains an electrical pump event")
    reconstructions = {name: _reconstruct_entries(items, pumped, baseline, plan, cancel=cancel, strict_phase_gaps=True)
                       for name, items in entries.items()}
    result = {key: value for key, value in reconstructions["delta_absorbance"].items() if key != "absorbance"}
    for name, reconstructed in reconstructions.items():
        result[name] = reconstructed["absorbance"]
        result[name+"_standard_error"] = reconstructed["standard_error"]
        result[name+"_repetition_count"] = reconstructed["repetition_count"]
        result["per_scan_"+name] = np.asarray(per_scan[name])
        result[name+"_invalid_reasons"] = np.where(np.isfinite(result[name]), 0, 1024).astype(np.uint16)
    result.update(schema_version=SCHEMA_VERSION, analysis_version=ANALYSIS_VERSION,
        detector_mode=DUAL_DETECTOR_MODE, normalization="Q=S/R; delta_absorbance=-log10(Q/Q0)",
        experiment_contract=experiment_contract(plan),
        acquisition_utc=records[0][1].metadata.get("acquisition_utc", utc_now()),
        baseline_matching="separate_reviewed_unpumped_sample_reference_baseline_by_measured_wavenumber",
        baseline_record_id=baseline.metadata.get("record_id"), baseline_spectrum=baseline.to_dict(),
        baseline_sample_reference_ratio=interpolate_spectrum(baseline, baseline_ratio, wn),
        sequence_unpumped_spectrum=records[0][1].to_dict(),
        scan_index=np.asarray([event.scan_index for event, _ in records], np.int64),
        channel_balance_calibration=None if calibration is None else calibration.to_dict(),
        absolute_absorbance_available=calibration is not None,
        native_invalid_reasons=reasons_per_scan, invalid_reason_definitions=INVALID_REASONS,
        time_label="Time relative to electrical pump sync (s)", optical_arrival_calibrated=False,
        time_basis="native_sample_time_minus_estimated_detector_filter_delay_minus_observed_electrical_sync",
        completion_status="COMPLETE", publication_eligible=False)
    result.pop("background_role", None)
    missing_q0 = ~np.isfinite(result["baseline_sample_reference_ratio"])
    result["delta_absorbance_invalid_reasons"][:, missing_q0] |= 128
    if calibration is not None:
        balance_grid = _supported_by_segment(calibration.wavenumber_cm1,
            np.where(np.asarray(calibration.response_ratio) > 0, calibration.response_ratio, np.nan),
            wn, calibration.segment_id)
        result["absorbance_invalid_reasons"][:, ~np.isfinite(balance_grid)] |= 512
        result["channel_balance_response_ratio"] = balance_grid
    result["limitations"] = [
        "Phase increment is not temporal resolution; both detector filters and sample rates limit resolution.",
        "Configured low-frequency group delays align detector times; filter responses are not deconvolved.",
        "Q0 is the separately retained preliminary unpumped sample/reference baseline, matched by measured wavelength.",
        "Unsupported regions remain missing; no extrapolation, smoothing or additional normalization.",
        "Standard errors describe repetition scatter; shared baseline and calibration uncertainty are not propagated.",
        "Time zero is electrical pump sync; optical pump arrival has not been calibrated.",
    ]
    if calibration is None:
        result["limitations"].append("No validated channel/path balance is available; S/R is not absolute transmission.")
    else:
        result["absolute_normalization"] = "T=Q/B; absorbance=-log10(T)"
    return validate_reconstruction(result)


class DualScanStore(RegularScanStore):
    """Independent metadata and output root, sharing lossless partial retention."""
    def __init__(self, root, kind, plan):
        if kind not in {"test", "run"}:
            raise ValueError("Dual-detector scanning has preliminary and pumped runs; no separate blank step")
        self.kind = kind
        self.id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")+"_"+kind
        self.path = research_output_path(root)/"Dual-Detector Phase Scan"/datetime.now(UTC).strftime("%Y-%m-%d")/self.id
        research_output_path(self.path).mkdir(parents=True, exist_ok=False)
        self.compress_raw, self.record_count = True, 0
        write_json(self.path/"run.json", {
            "schema_version": SCHEMA_VERSION, "detector_mode": DUAL_DETECTOR_MODE,
            "run_id": self.id, "kind": kind, "created_utc": utc_now(), "plan": plan.to_dict(),
            "experiment_contract": experiment_contract(plan),
            "normalization": "Q=S/R; delta_absorbance=-log10(Q/Q0); absolute absorbance requires promoted B",
            "native_source": "raw/acquisition.npz", "publication_eligible": False})

    def save_block(self, records, *, native):
        path = self.path/"raw"/"acquisition.npz"
        save_native(path, {"schema_version": SCHEMA_VERSION, "detector_mode": DUAL_DETECTOR_MODE,
            "records": [{"event": asdict(e), **payload} for e, payload in records], "native": native})
        self.record_count = len(records)
        with (research_output_path(self.path/"scan_index.jsonl")).open("x", encoding="utf-8") as handle:
            for index, (event, _) in enumerate(records):
                handle.write(json.dumps({"event": asdict(event), "path": "raw/acquisition.npz", "record_index": index})+"\n")
        return path


def validate_reconstruction(result):
    if result.get("schema_version") != SCHEMA_VERSION or result.get("detector_mode") != DUAL_DETECTOR_MODE:
        raise ValueError("Select a saved Dual-Detector Phase Scan dataset; single-detector or legacy data are incompatible")
    wn, times = [np.asarray(result[key], float) for key in ("wavenumber_cm1", "time_s")]
    if any(axis.ndim != 1 or not len(axis) or not np.isfinite(axis).all() or not np.all(np.diff(axis) > 0)
           for axis in (wn, times)):
        raise ValueError("Dual-detector reconstruction axes must be finite and increasing")
    for name in ("sample_reference_ratio", "delta_absorbance"):
        values = np.asarray(result[name])
        if values.shape != (len(times), len(wn)) or np.isinf(values).any():
            raise ValueError(f"Saved {name} does not match its axes or contains infinity")
    if "absorbance" in result:
        calibration = result.get("channel_balance_calibration")
        if not isinstance(calibration, dict):
            raise ValueError("Absolute absorbance cannot be displayed without retained validated channel balance")
        if not result.get("acquisition_utc") or not result.get("experiment_contract"):
            raise ValueError("Saved absolute absorbance requires acquisition UTC and detector/configuration applicability")
        ChannelBalanceCalibration(**calibration).validate(experiment=result["experiment_contract"],
            at_utc=result["acquisition_utc"], device_settings=result.get("device_settings"))
        values = np.asarray(result["absorbance"])
        if values.shape != (len(times), len(wn)) or np.isinf(values).any():
            raise ValueError("Absolute absorbance does not match the saved axes or contains infinity")
    return result


def load_dual_run(path):
    path = Path(path)
    if path.is_dir():
        path = path/"processed"/"reconstruction.npz"
    result = validate_reconstruction(load_native(path))
    result.setdefault("source_path", str(path))
    return result


def save_dual_reconstruction_csv(path, result):
    validate_reconstruction(result)
    path = research_output_path(path)
    research_output_path(path.parent).mkdir(parents=True, exist_ok=True)
    quantities = ["sample_reference_ratio", "delta_absorbance"]
    if "absorbance" in result:
        quantities.append("absorbance")
    with research_output_path(path).open("x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["wavenumber_cm-1", "time_from_electrical_pump_sync_s", *quantities,
                         "unpumped_baseline_sample_reference_ratio",
                         *[name+"_standard_error" for name in quantities],
                         *[name+"_repetition_count" for name in quantities],
                         *[name+"_invalid_reason_codes" for name in quantities],
                         *[name+"_invalid_reason_text" for name in quantities],
                         "baseline_record_id", "channel_balance_bundle_id"])
        calibration = result.get("channel_balance_calibration") or {}
        for row, time in enumerate(result["time_s"]):
            for col, wn in enumerate(result["wavenumber_cm1"]):
                reasons = [int(result[name+"_invalid_reasons"][row, col]) for name in quantities]
                texts = [";".join(label for flag, label in INVALID_REASONS.items() if reason & flag) for reason in reasons]
                writer.writerow([wn, time, *(result[name][row, col] for name in quantities),
                    result["baseline_sample_reference_ratio"][col],
                    *(result[name+"_standard_error"][row, col] for name in quantities),
                    *(result[name+"_repetition_count"][row, col] for name in quantities),
                    *reasons, *texts,
                    result.get("baseline_record_id", ""), calibration.get("bundle_id", "")])


def save_dual_spectrum_csv(path, spectrum, calibration=None):
    values = baseline_values(spectrum, calibration)
    path = research_output_path(path)
    research_output_path(path.parent).mkdir(parents=True, exist_ok=True)
    names = ["sample_reference_ratio"] + (["absorbance"] if calibration is not None else [])
    with research_output_path(path).open("x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["wavenumber_cm-1", "effective_sample_time_s", "sample_r", "reference_r", *names, "invalid_reasons"])
        for i, wn in enumerate(spectrum.wavenumber_cm1):
            writer.writerow([wn, spectrum.sample_time_s[i], spectrum.sample_r[i], spectrum.reference_r[i],
                             *(values[name][i] for name in names), int(values["invalid_reasons"][i])])
