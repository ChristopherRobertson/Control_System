"""Versioned experiment data and standalone host spectral-state interchange.

Native arrays live in a lossless, pickle-free NPZ alongside readable metadata.
Schema, detector mode and scientific array associations are validated; optional
sample and temperature annotations never control loading or operation. No
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
    # expected_condition_id remains an accepted legacy argument. Condition is
    # optional descriptive metadata, not an operating or data-loading gate.


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
    if run.get("mode") != mode:
        raise ValueError("Run detector mode disagrees with envelope")
    if run.get("experiment_id", EXPERIMENT_ID) != EXPERIMENT_ID or run.get(
            "instance_id", f"{EXPERIMENT_ID}:{mode}") != f"{EXPERIMENT_ID}:{mode}":
        raise ValueError("Run experiment/instance identity disagrees with envelope")
    settings = _plain(run.get("settings", {}))
    if settings.get("mode") != mode:
        raise ValueError("Run settings detector mode disagrees with envelope")
    if settings.get("experiment_id", EXPERIMENT_ID) != EXPERIMENT_ID or settings.get(
            "instance_id", f"{EXPERIMENT_ID}:{mode}") != f"{EXPERIMENT_ID}:{mode}":
        raise ValueError("Run settings experiment/instance identity disagrees with envelope")
    sweeps = {}
    for sweep in run.get("sweeps", ()):
        if not isinstance(sweep, NativeSweep) or sweep.mode != mode:
            raise ValueError("Native sweep detector mode is incompatible with run")
        if sweep.sweep_id in sweeps:
            raise ValueError("Duplicate native sweep identity")
        sweeps[sweep.sweep_id] = sweep
    spectra = {}
    for spectrum in run.get("spectra", ()):
        if not isinstance(spectrum, ProcessedSpectrum):
            raise ValueError("Processed spectrum must retain its typed native sweep")
        native = spectrum.native
        original = sweeps.get(native.sweep_id)
        identity = ("mode", "segment_id", "direction", "replicate")
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
        if spectrum is None or fit.provenance.get("quantity") != spectrum.quantity:
            raise ValueError("Fit sweep/quantity identity is incompatible with its processed spectrum")
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
    original_parent = run.get("path")
    automatic_dark = run.get("automatic_dark")
    if original_parent and isinstance(automatic_dark, dict):
        parent_id = str(run.get("run_id", ""))
        same_parent_record = (automatic_dark.get("source_run_id") == parent_id or
                              automatic_dark.get("run_id") == parent_id + ":dark")
        def points_to_original_parent(value):
            return bool(value) and Path(value).resolve() == Path(original_parent).resolve()
        if (same_parent_record and points_to_original_parent(automatic_dark.get("path")) and
                Path(original_parent).resolve() != path.parent.resolve()):
            automatic_dark["source_locations"] = list(automatic_dark.get("source_locations", ())) + [
                {"original_parent_path": str(automatic_dark["path"])}]
            automatic_dark["path"] = str(path.parent.resolve())
            # This control is embedded in this package. External dark, blank
            # and Q0 references are provenance and must not be retargeted.
            reference = run.get("controls", {}).get("dark")
            if (isinstance(reference, dict) and reference.get("run_id") == automatic_dark.get("run_id") and
                    points_to_original_parent(reference.get("path"))):
                reference["path"] = str(path.parent.resolve())
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


def export_selection(run, path, *, windows, accepted_by="", acceptance=None):
    """Export operator-selected windows through the existing standalone contract.

    Calling this function is the export intent. The host's legacy ``accepted``
    disposition means the operator selected these windows; it does not certify
    physical sample state, temperature, calibration or instrument readiness.
    Optional legacy review fields are retained as metadata and never authorize
    or block export. Invalid fitted claims are omitted while raw windows remain.
    """
    from control_app.measurement_host.interchange import (
        SampleSpectralSelection, SourceRecord, SpectralWindow, save_sample_selection,
    )
    destination = Path(path)
    if destination.exists():
        raise FileExistsError("Selection already exists; use a new export record")
    metadata = _plain(acceptance or {})
    settings = _plain(run.get("settings", {}))
    mode = _mode(run)
    _validate_run_identities(run, mode, run.get("condition_id"))
    condition = settings.get("condition", {})
    condition = dict(condition) if isinstance(condition, dict) else {"annotation": condition}
    spectra = tuple(run.get("spectra", ()))
    fits = tuple(run.get("fits", ()))
    requested = tuple(window if isinstance(window, SpectralWindow) else SpectralWindow(**window) for window in windows)
    if not requested:
        raise ValueError("Select at least one spectral window")
    if not spectra:
        raise ValueError("Window export requires retained spectral observations; export native data for an unfinished scan")
    selected_windows, limitations, support = [], [], []
    quality_flags = sorted({flag for spectrum in spectra for flag in spectrum.flags})
    for index, window in enumerate(requested):
        observed = []
        for spectrum in spectra:
            axis = np.asarray(spectrum.axis_cm1, float)
            native_signal = np.asarray(spectrum.native.sample, float)
            finite = np.isfinite(axis) & np.isfinite(native_signal)
            chosen = finite & (axis >= window.lower_cm1) & (axis <= window.upper_cm1)
            if (np.any(chosen) and np.nanmin(axis[finite]) <= window.lower_cm1 and
                    np.nanmax(axis[finite]) >= window.upper_cm1):
                observed.append(spectrum)
                support.append({"window": index, "sweep_id": spectrum.native.sweep_id,
                    "raw_observation_count": int(np.count_nonzero(chosen)),
                    "valid_processed_count": int(np.count_nonzero(chosen & spectrum.valid)),
                    "quality_flags": list(spectrum.flags)})
        if not observed:
            raise ValueError("Selected window has no retained native spectral support")
        if any(item["raw_observation_count"] != item["valid_processed_count"] for item in support if item["window"] == index):
            limitations.append(f"Window {index + 1}: raw observations include invalid or missing normalized support; gaps remain in the source")
        if window.center_cm1 is not None:
            sweep_ids = {spectrum.native.sweep_id for spectrum in observed}
            matches = [(fit, peak) for fit in fits if fit.provenance.get("sweep_id") in sweep_ids
                       and not {"fit_not_converged", "fit_parameters_not_identifiable"}.intersection(fit.flags)
                       for peak in fit.peaks if abs(peak.center_cm1 - window.center_cm1) <= 1e-6
                       and np.isfinite(peak.center_uncertainty_cm1) and peak.center_uncertainty_cm1 >= 0]
            if not matches:
                limitations.append(f"Window {index + 1}: fitted-center claim omitted because no valid associated fit supports it")
                window = SpectralWindow(window.lower_cm1, window.upper_cm1, label=window.label)
            else:
                required = min(peak.center_uncertainty_cm1 for _, peak in matches)
                supplied = window.uncertainty_cm1
                uncertainty = max(required, supplied) if supplied is not None else required
                if supplied is not None and supplied < required:
                    limitations.append(f"Window {index + 1}: uncertainty increased to the retained fit uncertainty")
                window = SpectralWindow(window.lower_cm1, window.upper_cm1, window.center_cm1,
                                        uncertainty, window.label)
        selected_windows.append(window)
    axis_calibrated = bool(spectra) and all(spectrum.provenance.get("axis_calibration_id") for spectrum in spectra)
    if not axis_calibrated:
        limitations.append("Native spectral axis is not established as calibrated; fitted uncertainties exclude unavailable axis uncertainty")
    if run.get("simulation") or run.get("readbacks", {}).get("simulation"):
        limitations.append("Simulated data: no physical sample observation")
    if run.get("status") not in ("complete", "completed"):
        limitations.append("Partial or failed run: only retained observations are exported")
    if run.get("restoration", {}).get("safe_verified") is not True:
        limitations.append("Safe restoration was not verified in this source record")
    run_id = str(run["run_id"])
    sample_id = condition.get("sample_id") or settings.get("sample_id")
    condition_id = run.get("condition_id") or _condition_id(settings)
    actual_sample_id, actual_condition_id = bool(sample_id), bool(condition_id)
    sample_id = sample_id or f"unidentified-sample:{run_id}"
    condition_id = condition_id or f"unidentified-condition:{run_id}"
    source_path = Path(run.get("analysis_path") or (Path(run.get("path", ".")) / "run.json"))
    if not source_path.is_file():
        # Export is also a preservation action when no native package was saved.
        source_path = export_run(destination.with_name(destination.stem + "-source-" + str(uuid4()) + ".json"), run)
    source = SourceRecord(run_id, str(source_path),
        run.get("started_utc") or run.get("operation", {}).get("started_utc") or run.get("created_utc")
        or datetime.now(timezone.utc).isoformat(), ANALYSIS_VERSION)
    condition.update({"spectral_quantities": sorted({spectrum.quantity for spectrum in spectra}),
        "analysis_version": ANALYSIS_VERSION, "sample_identity_provided": actual_sample_id,
        "condition_identity_provided": actual_condition_id,
        "missing_identity_policy": "Run-local record identifiers do not identify an actual sample or temperature",
        "acceptance_scope": "Operator selected spectral windows; no physical sample-state qualification",
        "acceptance_provenance": {"action": "operator_export", "operator_metadata": metadata},
        "physical_sample_state_accepted": False, "instrument_bundle_promoted": False,
        "campaign_phase_accepted": False, "axis_calibrated": axis_calibrated,
        "source_status": run.get("status", "unspecified"), "quality_flags": quality_flags,
        "limitations": limitations, "support_summary": support,
        "fit_models": [_plain(fit.settings) for fit in fits],
        "fit_uncertainty": [fit.provenance.get("uncertainty_method") for fit in fits]})
    record = SampleSpectralSelection(selection_id=str(uuid4()), sample_id=sample_id,
        producer_instance_id=f"{EXPERIMENT_ID}:{mode}", source=source,
        condition_id=condition_id, condition=condition, windows=tuple(selected_windows),
        accepted_by=str(accepted_by or "").strip() or "operator export", accepted_utc=datetime.now(timezone.utc).isoformat(),
        uncertainty_description="Fitted-center uncertainties are conditional on the retained model and noise inputs; calibrated-axis uncertainty is included only where available. Source limitations and native support remain explicit.")
    return save_sample_selection(record, destination)
