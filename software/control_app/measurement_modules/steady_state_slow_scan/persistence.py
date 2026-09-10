"""Versioned experiment data and standalone host spectral-state interchange.

Native arrays live in a lossless, pickle-free NPZ alongside readable metadata.
Schema, mode, condition and configuration are compatibility requirements; no
checksum or previously recorded hash is ever a loading or acceptance gate.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

from .processing import (ANALYSIS_VERSION, AxisCorrection, FitResult, FitSettings,
                         NativeSweep, PeakFit, ProcessedSpectrum, SpectralControl)

EXPERIMENT_ID = "steady_state_slow_scan"
SCHEMA_VERSION = 1
_TYPES = {kind.__name__: kind for kind in (AxisCorrection, FitResult, FitSettings, NativeSweep,
                                         PeakFit, ProcessedSpectrum, SpectralControl)}


def _plain(value):
    if is_dataclass(value):
        return {item.name: _plain(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, np.ndarray):
        return _plain(value.tolist())
    if isinstance(value, np.generic):
        return _plain(value.item())
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    raise TypeError(f"Persist only explicit data, not {type(value).__name__}")


def _mode(settings, explicit=None):
    mode = explicit or settings.get("mode")
    if mode not in ("single", "dual"):
        raise ValueError("A slow-scan record requires explicit single/dual mode")
    return mode


def _condition_id(settings):
    condition = settings.get("condition", {})
    return settings.get("condition_id") or (condition.get("condition_id") if isinstance(condition, Mapping) else None)


def _validate_envelope(data, kind, expected_mode=None, expected_condition_id=None):
    if data.get("schema_version") != SCHEMA_VERSION or type(data.get("schema_version")) is not int:
        raise ValueError("Unsupported slow-scan schema_version")
    if data.get("experiment_id") != EXPERIMENT_ID or data.get("record_kind") != kind:
        raise ValueError(f"Expected {EXPERIMENT_ID} {kind} record")
    mode = _mode(data)
    if data.get("instance_id") != f"{EXPERIMENT_ID}:{mode}":
        raise ValueError("Record instance_id does not match experiment/mode")
    if expected_mode is not None and expected_mode != mode:
        raise ValueError(f"Detector mode mismatch: expected {expected_mode}, received {mode}")
    if expected_condition_id is not None and data.get("condition_id") != expected_condition_id:
        raise ValueError("Condition mismatch; this record belongs to a different sample/temperature profile")


def _write_json_exclusive(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Prior native/rejected/analysis/acceptance records cannot be silently replaced.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
    return path


def save_plan(path, settings, *, mode=None, plan=None):
    settings = _plain(settings)
    mode = _mode(settings, mode)
    return _write_json_exclusive(path, {"schema_version": SCHEMA_VERSION, "experiment_id": EXPERIMENT_ID,
        "record_kind": "slow_scan_plan", "instance_id": f"{EXPERIMENT_ID}:{mode}", "mode": mode,
        "condition_id": _condition_id(settings), "created_utc": datetime.now(timezone.utc).isoformat(),
        "plan_id": str(uuid4()), "settings": settings, "derived_plan": _plain(plan)})


def load_plan(path, *, expected_mode=None, expected_condition_id=None):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    _validate_envelope(data, "slow_scan_plan", expected_mode, expected_condition_id)
    settings = data["settings"]
    if _mode(settings, data["mode"]) != data["mode"] or (settings.get("mode") and settings["mode"] != data["mode"]):
        raise ValueError("Plan settings detector mode disagrees with envelope")
    if _condition_id(settings) != data.get("condition_id"):
        raise ValueError("Plan settings condition disagrees with envelope")
    return settings


def _encode(value, arrays):
    if isinstance(value, np.ndarray):
        if value.dtype.hasobject:
            raise TypeError("Native object arrays are unsupported; use explicit scalar records")
        key = f"native_{len(arrays):06d}"
        arrays[key] = value
        return {"__native_array__": key, "dtype": value.dtype.str, "shape": list(value.shape)}
    if isinstance(value, np.generic):
        # Scalar timestamps must retain integer precision just like arrays.
        return _encode(value.item(), arrays)
    if isinstance(value, Path):
        return {"__path__": str(value)}
    if is_dataclass(value):
        payload = {item.name: _encode(getattr(value, item.name), arrays) for item in fields(value)}
        if type(value).__name__ in _TYPES:
            return {"__dataclass__": type(value).__name__, "fields": payload}
        return payload
    if isinstance(value, Mapping):
        return {str(key): _encode(item, arrays) for key, item in value.items()}
    if isinstance(value, tuple):
        return {"__tuple__": [_encode(item, arrays) for item in value]}
    if isinstance(value, list):
        return [_encode(item, arrays) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return {"__nonfinite__": "nan" if math.isnan(value) else ("inf" if value > 0 else "-inf")}
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if hasattr(value, "to_dict"):
        return _encode(value.to_dict(), arrays)
    raise TypeError(f"Run contains unsupported mutable service {type(value).__name__}")


def _decode(value, arrays):
    if isinstance(value, list):
        return [_decode(item, arrays) for item in value]
    if not isinstance(value, dict):
        return value
    if "__native_array__" in value:
        result = np.array(arrays[value["__native_array__"]], copy=True)
        # Dtype/shape are format semantics, not an additional hash gate.
        if result.dtype.str != value["dtype"] or list(result.shape) != value["shape"]:
            raise ValueError("Native array dtype/shape disagrees with its schema")
        return result
    if "__nonfinite__" in value:
        return float(value["__nonfinite__"])
    if "__path__" in value:
        return Path(value["__path__"])
    if "__tuple__" in value:
        return tuple(_decode(item, arrays) for item in value["__tuple__"])
    if "__dataclass__" in value:
        name = value["__dataclass__"]
        if name not in _TYPES:
            raise ValueError(f"Unsupported native data type {name}")
        return _TYPES[name](**{key: _decode(item, arrays) for key, item in value["fields"].items()})
    return {key: _decode(item, arrays) for key, item in value.items()}


def save_run(output_dir, run_mapping, sweeps=None):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    metadata_path = output / "run.json"
    array_path = output / "native.npz"
    if metadata_path.exists() or array_path.exists():
        raise FileExistsError("Run destination contains native data; choose a new run or analysis record")
    run = dict(run_mapping)
    if sweeps is not None:
        run["sweeps"] = list(sweeps)
    mode = _mode(run)
    run.setdefault("path", output)
    arrays = {}
    encoded = _encode(run, arrays)
    payload = {"schema_version": SCHEMA_VERSION, "experiment_id": EXPERIMENT_ID,
        "record_kind": "slow_scan_run", "instance_id": f"{EXPERIMENT_ID}:{mode}", "mode": mode,
        "condition_id": run.get("condition_id") or _condition_id(_plain(run.get("settings", {}))),
        "created_utc": datetime.now(timezone.utc).isoformat(), "analysis_version": ANALYSIS_VERSION,
        "native_file": "native.npz", "run": encoded}
    # Serialize all metadata before opening a native file; failures retain raw chunks
    # already written by acquisition and do not leave a falsely complete manifest.
    json.dumps(payload, allow_nan=False)
    with array_path.open("xb") as stream:
        np.savez(stream, **arrays)
        stream.flush()
    return _write_json_exclusive(metadata_path, payload)


def _validate_run_identities(run, mode, condition_id):
    """Associate scientific objects by readable identity, never list position."""
    if run.get("mode") != mode or run.get("condition_id") != condition_id:
        raise ValueError("Run detector mode/condition disagrees with envelope")
    if run.get("experiment_id", EXPERIMENT_ID) != EXPERIMENT_ID or run.get(
            "instance_id", f"{EXPERIMENT_ID}:{mode}") != f"{EXPERIMENT_ID}:{mode}":
        raise ValueError("Run experiment/instance identity disagrees with envelope")
    settings = _plain(run.get("settings", {}))
    if settings.get("mode") != mode or _condition_id(settings) != condition_id:
        raise ValueError("Run settings detector mode/condition disagrees with envelope")
    if settings.get("experiment_id", EXPERIMENT_ID) != EXPERIMENT_ID or settings.get(
            "instance_id", f"{EXPERIMENT_ID}:{mode}") != f"{EXPERIMENT_ID}:{mode}":
        raise ValueError("Run settings experiment/instance identity disagrees with envelope")
    sweeps = {}
    for sweep in run.get("sweeps", ()):
        if not isinstance(sweep, NativeSweep) or sweep.mode != mode or sweep.condition_id != condition_id:
            raise ValueError("Native sweep experiment/mode/condition is incompatible with run")
        if sweep.sweep_id in sweeps:
            raise ValueError("Duplicate native sweep identity")
        sweeps[sweep.sweep_id] = sweep
    spectra = {}
    for spectrum in run.get("spectra", ()):
        if not isinstance(spectrum, ProcessedSpectrum):
            raise ValueError("Processed spectrum must retain its typed native sweep")
        native = spectrum.native
        original = sweeps.get(native.sweep_id)
        identity = ("mode", "condition_id", "segment_id", "direction", "replicate")
        if original is None or any(getattr(native, key) != getattr(original, key) for key in identity):
            raise ValueError("Processed spectrum native identity is incompatible with its retained sweep")
        if len(native.axis_cm1) != len(original.axis_cm1):
            raise ValueError("Processed spectrum native support length disagrees with retained sweep")
        if native.sweep_id in spectra:
            raise ValueError("Duplicate processed spectrum sweep identity")
        spectra[native.sweep_id] = spectrum
    def validate_fit(fit):
        if not isinstance(fit, FitResult):
            raise ValueError("Fit results must retain typed scientific provenance")
        sweep_id = fit.provenance.get("sweep_id")
        spectrum = spectra.get(sweep_id)
        if (spectrum is None or fit.provenance.get("condition_id") != condition_id or
                fit.provenance.get("quantity") != spectrum.quantity):
            raise ValueError("Fit condition/sweep/quantity identity is incompatible with its processed spectrum")
        for name in ("fitted", "baseline", "residuals", "valid"):
            if np.asarray(getattr(fit, name)).shape != spectrum.signal.shape:
                raise ValueError("Fit support shape disagrees with its associated spectrum")
        return sweep_id
    primary = set()
    for fit in run.get("fits", ()):
        sweep_id = validate_fit(fit)
        if sweep_id in primary:
            raise ValueError("Duplicate primary fit for one sweep identity")
        primary.add(sweep_id)
    for alternatives in run.get("fit_alternatives", ()):
        for fit in alternatives:
            validate_fit(fit)


def load_run(path, *, expected_mode=None, expected_condition_id=None):
    path = Path(path)
    if path.is_dir():
        path = path / "run.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    _validate_envelope(data, "slow_scan_run", expected_mode, expected_condition_id)
    # Native file references are intentionally relative to this preserved package.
    native_file = data.get("native_file")
    if not isinstance(native_file, str) or Path(native_file).name != native_file:
        raise ValueError("Native file must name a file within this run package")
    with np.load(path.parent / native_file, allow_pickle=False) as arrays:
        run = _decode(data["run"], arrays)
    _validate_run_identities(run, data["mode"], data.get("condition_id"))
    run["path"] = path.parent
    if run.get("analysis_path") or native_file != "native.npz":
        previous = run.get("analysis_path")
        actual = str(path.resolve())
        if previous and previous != actual:
            run.setdefault("source_locations", []).append({"original_analysis_path": previous})
        run["analysis_path"] = actual
    return run


def export_run(path, run):
    """Create an immutable portable analysis JSON plus exact array sidecar.

    This is a new analysis revision, never a replacement for original native,
    preliminary, interrupted or rejected records. load_run reads the export too.
    """
    path = Path(path)
    if path.suffix.lower() != ".json":
        path = path.with_suffix(".json")
    sidecar = path.with_suffix(".npz")
    if path.exists() or sidecar.exists():
        raise FileExistsError("Export already exists; use a new analysis record name")
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = _mode(run)
    arrays = {}
    payload = {"schema_version": SCHEMA_VERSION, "experiment_id": EXPERIMENT_ID,
        "record_kind": "slow_scan_run", "instance_id": f"{EXPERIMENT_ID}:{mode}", "mode": mode,
        "condition_id": run.get("condition_id") or _condition_id(_plain(run.get("settings", {}))),
        "created_utc": datetime.now(timezone.utc).isoformat(), "analysis_version": ANALYSIS_VERSION,
        "native_file": sidecar.name, "run": _encode({**run, "analysis_path": str(path)}, arrays)}
    json.dumps(payload, allow_nan=False)
    with sidecar.open("xb") as stream:
        np.savez(stream, **arrays)
    return _write_json_exclusive(path, payload)


def export_selection(run, path, *, windows, accepted_by, acceptance):
    """Export an explicitly accepted state via the standalone host data contract.

    Sample-state acceptance is a named scientific review. It neither changes a
    campaign phase nor promotes an instrument bundle. Ratio spectra remain
    reference-normalized ratios even when a bounded sample-state selection is
    accepted. A calibrated center claim requires applicable axis provenance.
    """
    from control_app.measurement_host.interchange import (
        SampleSpectralSelection, SourceRecord, SpectralWindow, save_sample_selection,
    )
    if run.get("status") not in ("complete", "completed"):
        raise ValueError("Only a complete retained run can support sample-state acceptance")
    if run.get("simulation") or run.get("readbacks", {}).get("simulation"):
        raise ValueError("Simulation spectra cannot authorize acceptance of a physical sample-state record")
    if run.get("restoration", {}).get("safe_verified") is not True:
        raise ValueError("Sample-state acceptance requires verified safe restoration")
    if not accepted_by.strip() or not acceptance.get("sample_state_accepted") or not acceptance.get("review_complete"):
        raise ValueError("Sample-state acceptance requires a named reviewer and an explicit completed review")
    if not acceptance.get("configuration_id") or not str(acceptance.get("rationale", "")).strip():
        raise ValueError("Acceptance requires configuration identity and a bounded scientific rationale")
    settings = _plain(run.get("settings", {}))
    condition = settings.get("condition", {})
    if not isinstance(condition, dict):
        condition = {"profile": condition}
    sample_id = condition.get("sample_id") or settings.get("sample_id")
    if not sample_id:
        raise ValueError("An accepted sample record requires the actual sample_id")
    configuration_id = condition.get("configuration_id") or settings.get("configuration_id")
    if configuration_id != acceptance["configuration_id"]:
        raise ValueError("Acceptance configuration identity does not match the retained sample condition")
    for identity in ("preparation_id", "cell_id", "position_id", "temperature_id"):
        if not condition.get(identity):
            raise ValueError(f"Accepted sample-state record requires {identity}")
    selected_windows = tuple(window if isinstance(window, SpectralWindow) else SpectralWindow(**window) for window in windows)
    if not selected_windows:
        raise ValueError("Select at least one bounded spectral window")
    spectra = tuple(run.get("spectra", ()))
    fits = tuple(run.get("fits", ()))
    if not spectra or not fits:
        raise ValueError("Selection acceptance requires retained spectra and independently fitted results")
    _validate_run_identities(run, _mode(run), run.get("condition_id") or _condition_id(settings))
    critical_flags = {"saturation", "clipping", "unlock", "reference_unlocked", "detector_clipping",
        "unexpected_electrical_pump_sync", "sweep_trigger_count_mismatch", "wavelength_marker_count_mismatch",
        "direction_changed_inside_sweep", "observed_direction_mismatch", "missing_reference_support", "invalid_reference_signal",
        "invalid_detector_covariance", "dark_not_applied"}
    present_flags = {flag for spectrum in spectra for flag in spectrum.flags}
    if critical_flags & present_flags:
        raise ValueError("Sample-state acceptance blocked by retained native quality faults: " + ", ".join(sorted(critical_flags & present_flags)))
    if any("fit_not_converged" in fit.flags or "fit_parameters_not_identifiable" in fit.flags for fit in fits):
        raise ValueError("Fit convergence/identifiability is unresolved; retain an exploratory analysis")
    quantities = sorted({spectrum.quantity for spectrum in spectra})
    if any(window.center_cm1 is not None for window in selected_windows):
        if any(not spectrum.provenance.get("axis_calibration_id") for spectrum in spectra):
            raise ValueError("Fitted-center acceptance requires applicable spectral-axis calibration")
        if any(window.center_cm1 is not None and window.uncertainty_cm1 is None for window in selected_windows):
            raise ValueError("Accepted fitted centers require explicit uncertainty")
    for window in selected_windows:
        # Identify the selected segment from its observed extent, then require
        # every retained direction/replicate there to support the selection.
        segments = {spectrum.native.segment_id for spectrum in spectra
                    if np.any(np.isfinite(spectrum.axis_cm1)) and
                    np.nanmin(spectrum.axis_cm1) <= window.lower_cm1 and
                    np.nanmax(spectrum.axis_cm1) >= window.upper_cm1}
        if not segments:
            raise ValueError("Selected window has no retained valid spectral support")
        relevant = {spectrum.native.sweep_id: spectrum for spectrum in spectra if spectrum.native.segment_id in segments}
        relevant_fits = {fit.provenance["sweep_id"]: fit for fit in fits if fit.provenance["sweep_id"] in relevant}
        for sweep in run.get("sweeps", ()):
            if sweep.segment_id in segments and sweep.sweep_id not in relevant:
                raise ValueError("Selected segment has a retained sweep without a processed spectrum")
        for sweep_id, spectrum in relevant.items():
            selected = np.isfinite(spectrum.axis_cm1) & (spectrum.axis_cm1 >= window.lower_cm1) & (spectrum.axis_cm1 <= window.upper_cm1)
            support = (np.any(spectrum.valid) and np.any(selected) and np.all(spectrum.valid[selected]) and
                       np.nanmin(spectrum.axis_cm1[spectrum.valid]) <= window.lower_cm1 and
                       np.nanmax(spectrum.axis_cm1[spectrum.valid]) >= window.upper_cm1)
            if not support:
                raise ValueError(f"Selected window has incomplete valid support in sweep {sweep_id}")
            fit = relevant_fits.get(sweep_id)
            if fit is None or not np.all(fit.valid[selected]):
                raise ValueError(f"Selected window lacks a fitted result on its native support in sweep {sweep_id}")
        if window.center_cm1 is not None:
            matching_peaks = [peak for fit in relevant_fits.values() for peak in fit.peaks
                              if abs(peak.center_cm1 - window.center_cm1) <= 1e-6]
            if not matching_peaks:
                raise ValueError("Selected fitted center is not present in the retained fit results")
            if window.uncertainty_cm1 + 1e-12 < min(peak.center_uncertainty_cm1 for peak in matching_peaks):
                raise ValueError("Selected uncertainty understates the retained fit/axis uncertainty")
    mode = _mode(run)
    source_path = str(run.get("analysis_path") or (Path(run.get("path", ".")) / "run.json"))
    if not Path(source_path).is_file():
        raise ValueError("Accept a sample selection only after its native run or analysis revision has been retained")
    source = SourceRecord(str(run["run_id"]), source_path,
        run.get("started_utc") or run.get("operation", {}).get("started_utc") or run.get("created_utc")
        or datetime.now(timezone.utc).isoformat(), ANALYSIS_VERSION)
    condition = {**condition, "configuration_id": acceptance["configuration_id"],
        "spectral_quantities": quantities, "analysis_version": ANALYSIS_VERSION,
        "acceptance_rationale": acceptance["rationale"], "acceptance_provenance": _plain(acceptance),
        "instrument_bundle_promoted": False, "campaign_phase_accepted": False,
        "fit_models": [_plain(fit.settings) for fit in fits],
        "fit_uncertainty": [fit.provenance.get("uncertainty_method") for fit in fits]}
    record = SampleSpectralSelection(selection_id=str(uuid4()), sample_id=sample_id,
        producer_instance_id=f"{EXPERIMENT_ID}:{mode}", source=source,
        condition_id=run.get("condition_id") or _condition_id(settings), condition=condition,
        windows=selected_windows, accepted_by=accepted_by, accepted_utc=datetime.now(timezone.utc).isoformat(),
        uncertainty_description="Center uncertainty in cm^-1 combines local full-Jacobian fit covariance and applicable axis uncertainty; model alternatives retained in source run")
    return save_sample_selection(record, path)
