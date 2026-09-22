"""Append-only native records; no hash or digest is an acceptance condition."""
from __future__ import annotations

import base64
import csv
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from collections.abc import Mapping

import numpy as np

EXPERIMENT_ID = "nanosecond_stroboscopy"
SCHEMA_VERSION = 1


def _encode(value):
    if isinstance(value, np.ndarray):
        if value.dtype.hasobject:
            raise TypeError("Object arrays are not native numeric data")
        return {"__ndarray__": base64.b64encode(value.tobytes(order="C")).decode("ascii"),
                "dtype": value.dtype.str, "shape": list(value.shape)}
    if isinstance(value, np.generic):
        return {"__numpy_scalar__": _encode(np.asarray(value))}
    if is_dataclass(value):
        return _encode(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return {"__float__": value.hex()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported native value {type(value).__name__}")


def _decode(value):
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "__ndarray__" in value:
        dtype = np.dtype(value["dtype"])
        if dtype.hasobject:
            raise ValueError("Object arrays cannot be loaded")
        return np.frombuffer(base64.b64decode(value["__ndarray__"], validate=True),
                             dtype=dtype).reshape(value["shape"]).copy()
    if "__numpy_scalar__" in value:
        return _decode(value["__numpy_scalar__"])[()]
    if "__float__" in value:
        return float.fromhex(value["__float__"])
    return {key: _decode(item) for key, item in value.items()}


def write_json(path, payload):
    """Exclusive creation preserves previous records even for repeated exports."""
    text = json.dumps(_encode(payload), allow_nan=False, indent=2)
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_json(path):
    return _decode(json.loads(Path(path).read_text(encoding="utf-8")))


def compatibility_conflicts(left, right, prefix="settings"):
    """Return precise scientific mismatches using values, IDs and versions."""
    left, right = _encode(left), _encode(right)
    if isinstance(left, dict) and isinstance(right, dict):
        errors = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                errors.append(f"{prefix}.{key}: missing from one record")
            else:
                errors.extend(compatibility_conflicts(left[key], right[key], f"{prefix}.{key}"))
        return errors
    if left != right:
        return [f"{prefix}: retained {left!r} differs from selected {right!r}"]
    return []


def acquisition_settings(settings):
    """The acquisition contract excludes optional annotations and analysis priors.

    Blank/sample compatibility is not approval of a biological condition. Saved
    detector readbacks are checked separately after connected configuration.
    """
    from .settings import Settings
    selected = Settings.from_dict(settings).to_dict()
    fields = ("experiment_id", "mode", "execution_mode", "wavenumbers_cm1",
              "off_band_wavenumbers_cm1", "delays_ns", "conditions", "cycle_interval_s")
    contract = {key: selected[key] for key in fields if key in selected}
    contract["overrides"] = {key: value for key, value in selected.get("overrides", {}).items()
                             if value not in (None, "Auto", "auto")}
    optical = {key: value for key, value in selected.get("laser_settings", {}).items()
               if key in ("qcl_current_ma", "probe_pulse_width_ns", "probe_repetition_rate_hz", "pump_repetition_rate_hz", "fire_to_qswitch_us")}
    if optical:
        contract["laser_settings"] = optical
    return contract


def acquisition_conflicts(retained, selected):
    old, new = acquisition_settings(retained), acquisition_settings(selected)
    errors = []
    # Measured support may contain additional points or a different order. Only
    # missing requested support makes an otherwise identical baseline unusable.
    old_waves = set(old.pop("wavenumbers_cm1", ())) | set(old.pop("off_band_wavenumbers_cm1", ()))
    new_waves = set(new.pop("wavenumbers_cm1", ())) | set(new.pop("off_band_wavenumbers_cm1", ()))
    for key, available, required in (
        ("wavenumbers_cm1", old_waves, new_waves),
        ("delays_ns", set(old.pop("delays_ns", ())), set(new.pop("delays_ns", ()))),
        ("conditions", set(old.pop("conditions", ())), set(new.pop("conditions", ()))),
    ):
        if required - available:
            errors.append(f"settings.{key}: retained support misses {sorted(required - available)}")
    return errors + compatibility_conflicts(old, new)


def _validate_envelope(record, expected_mode=None):
    if record.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("Incompatible experiment_id; expected nanosecond_stroboscopy")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported nanosecond stroboscopy schema_version")
    mode = record.get("mode")
    if mode not in ("single", "dual") or (expected_mode is not None and mode != expected_mode):
        raise ValueError(f"Incompatible detector mode: {mode!r}; expected {expected_mode!r}")
    if record.get("instance_id") != f"{EXPERIMENT_ID}:{mode}":
        raise ValueError("Incompatible instance_id")


def _envelope(mode):
    if mode not in ("single", "dual"):
        raise ValueError("Detector mode must be single or dual")
    return dict(schema_version=SCHEMA_VERSION, experiment_id=EXPERIMENT_ID,
                instance_id=f"{EXPERIMENT_ID}:{mode}", mode=mode,
                created_utc=datetime.now(timezone.utc).isoformat())


def save_plan(path, settings, plan=None, *, mode=None):
    settings = asdict(settings) if is_dataclass(settings) else dict(settings)
    record = _envelope(mode or settings.get("mode", "single"))
    record.update(kind="plan", settings=settings, plan=plan)
    write_json(path, record)


def load_plan(path, *, expected_mode=None):
    record = read_json(path)
    _validate_envelope(record, expected_mode)
    if record.get("kind") != "plan":
        raise ValueError("This record is not a stroboscopy plan")
    return record["settings"]


class NativeStore:
    """One frozen host output path. Events are durable before the next pump."""

    def __init__(self, output_path, *, mode, settings, kind="measurement", operation=None):
        self.path = Path(output_path)
        self.path.mkdir(parents=True, exist_ok=False)
        self.manifest = _envelope(mode)
        self.manifest.update(kind=kind, settings=settings, status="interrupted",
                             operation=operation.to_dict() if hasattr(operation, "to_dict") else operation,
                             native_encoding="numpy dtype/shape/base64 bytes; JSON scalar roundtrip")
        write_json(self.path / "manifest.json", self.manifest)
        self.events = self.path / "events.jsonl"
        self.events.touch(exist_ok=False)
        self.finished = False

    def append_event(self, event):
        if self.finished:
            raise RuntimeError("Cannot append to a finalized native run")
        text = json.dumps(_encode(event), allow_nan=False, separators=(",", ":"))
        with self.events.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(text + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def save_record(self, name, payload):
        if Path(name).name != name or name in (".", "..", "manifest.json", "events.jsonl", "finish.json"):
            raise ValueError("Record name must be a new local filename")
        write_json(self.path / (name if name.endswith(".json") else name + ".json"), payload)

    def finish(self, status, *, restoration=None, result=None, error="", **details):
        if status not in ("completed", "cancelled", "failed", "interrupted", "rejected"):
            raise ValueError(f"Invalid run status {status!r}")
        write_json(self.path / "finish.json", dict(status=status, restoration=restoration,
                   result=result, error=error, finished_utc=datetime.now(timezone.utc).isoformat(), **details))
        self.finished = True
        return self.path


def load_run(path, expected_mode=None, expected_settings=None):
    path = Path(path)
    record = read_json(path / "manifest.json")
    _validate_envelope(record, expected_mode)
    if expected_settings is not None:
        conflicts = acquisition_conflicts(record["settings"], expected_settings)
        if conflicts:
            raise ValueError("Incompatible retained settings: " + "; ".join(conflicts))
    events, journal_errors = [], []
    with (path / "events.jsonl").open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            try:
                events.append(_decode(json.loads(line)))
            except (ValueError, TypeError) as exc:
                # Retain all complete events after a torn write; never invent the tail.
                journal_errors.append(f"Native journal line {number}: {exc}")
    if (path / "finish.json").exists():
        record.update(read_json(path / "finish.json"))
    rescue_path = path / "emergency_native_events.json"
    if rescue_path.exists():
        rescue = read_json(rescue_path)
        record["emergency_native_events"] = rescue
        # Keep the entire rescue file separately even where it duplicates a
        # durable journal event. Add only missing identities to the loaded view.
        identities = {event.get("event_id") for event in events}
        for event in rescue:
            if event.get("event_id") not in identities:
                events.append(event)
                identities.add(event.get("event_id"))
        record["preservation_verified"] = False
    record.update(events=events, native_path=str(path), output_path=str(path), journal_errors=journal_errors)
    if "run_id" not in record:
        record["run_id"] = (record.get("operation") or {}).get("run_id", path.name)
    if journal_errors:
        record["status"] = "interrupted"
    return record


def export_csv(path, result):
    """Native values remain in the run; CSV is a coordinate-explicit derivative."""
    if "result" in result and "wavenumbers_cm1" not in result:
        result = result["result"] or {}
    with Path(path).open("x", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["wavenumber_cm1", "quantized_delay_ns", "optical_delay_ns", "delta_a", "standard_uncertainty", "accepted_events"])
        for i, wave in enumerate(result.get("wavenumbers_cm1", [])):
            for j, delay in enumerate(result.get("delays_ns", [])):
                writer.writerow([wave, delay, result["optical_delay_ns"][i][j], result["delta_a"][i][j],
                                 result["uncertainty"][i][j], result["coverage"][i][j]])
