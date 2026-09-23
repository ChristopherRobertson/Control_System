"""Versioned native records. Array dtype, integer clocks and missing data survive.

Every save appends an immutable revision; interrupted writes leave their files in
place for recovery. The small latest pointer is replaced only after both files
are durable. No hash or digest controls loading or scientific acceptance.
"""
from __future__ import annotations

from control_app.paths import research_output_path

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

import numpy as np

EXPERIMENT_ID = "microsecond_stroboscopy"
SCHEMA_VERSION = 1


def _encode(value, arrays):
    if isinstance(value, np.ndarray):
        if value.dtype.hasobject:
            raise ValueError("Object arrays cannot be retained as native numeric data")
        key = f"array_{len(arrays):06d}"
        arrays[key] = value
        return {"__native_array__": key, "dtype": value.dtype.str, "shape": list(value.shape)}
    if isinstance(value, np.generic):
        return _encode(np.asarray(value), arrays)
    if is_dataclass(value):
        return _encode(asdict(value), arrays)
    if isinstance(value, Mapping):
        return {str(k): _encode(v, arrays) for k, v in value.items()}
    if isinstance(value, tuple):
        return {"__tuple__": [_encode(v, arrays) for v in value]}
    if isinstance(value, list):
        return [_encode(v, arrays) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return {"__float__": repr(value)}
    if isinstance(value, Path):
        return str(value)
    return value


def _decode(value, arrays):
    if isinstance(value, dict):
        if "__native_array__" in value:
            array = arrays[value["__native_array__"]]
            if array.dtype.str != value["dtype"] or list(array.shape) != value["shape"]:
                raise ValueError("Native array shape/dtype metadata is inconsistent")
            return array.copy()
        if set(value) == {"__tuple__"}:
            return tuple(_decode(v, arrays) for v in value["__tuple__"])
        if set(value) == {"__float__"}:
            return float(value["__float__"])
        return {k: _decode(v, arrays) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v, arrays) for v in value]
    return value


def _json_write(path, value):
    with research_output_path(Path(path)).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def preflight_storage(path: str | Path) -> Path:
    """Test the frozen destination before configuring or pumping anything."""
    path = research_output_path(path)
    research_output_path(path).mkdir(parents=True, exist_ok=True)
    probe = path / f".write-check-{uuid4()}"
    _json_write(probe, {"checked_utc": datetime.now(timezone.utc).isoformat()})
    probe.unlink()
    return path


def _validate(record, mode=None, condition_id=None, kind=None):
    if record.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("Incompatible experiment_id: expected microsecond_stroboscopy")
    if type(record.get("schema_version")) is not int or record["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported microsecond stroboscopy schema_version")
    if record.get("mode") not in ("single", "dual") or (mode and record["mode"] != mode):
        raise ValueError("Incompatible detector mode")
    if kind and record.get("record_kind") != kind:
        raise ValueError(f"Expected {kind} record")
    # condition_id remains accepted for older callers; historical condition
    # metadata does not determine whether a native record can be opened.


def save_run(path: str | Path, record: dict) -> Path:
    """Append a complete/partial/rejected revision, preserving all native values."""
    path = preflight_storage(path)
    payload = dict(record)
    payload.setdefault("experiment_id", EXPERIMENT_ID)
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload.setdefault("record_kind", "microsecond_stroboscopy_run")
    _validate(payload, kind="microsecond_stroboscopy_run")
    revision = f"record-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex[:8]}"
    arrays = {}
    encoded = _encode(payload, arrays)
    # Immutable array files are reused when an incremental preservation contains
    # the same observations. Comparison is exact native value/dtype comparison,
    # never a hash gate. This prevents quadratic storage growth across blocks.
    previous = {}
    latest = path / "latest.json"
    if latest.exists():
        pointer = json.loads(latest.read_text(encoding="utf-8"))
        previous_manifest = _local_file(path, pointer["record_file"])
        previous = json.loads(previous_manifest.read_text(encoding="utf-8")).get("native_arrays", {})
    references = {}
    for key, array in arrays.items():
        prior_name = previous.get(key)
        if prior_name:
            prior = np.load(_local_file(path, prior_name), allow_pickle=False, mmap_mode="r")
            equal = prior.dtype == array.dtype and prior.shape == array.shape and np.array_equal(prior, array, equal_nan=array.dtype.kind in "fc")
            # Equal numeric zeros may have distinct sign bits; retain those bits.
            if equal and array.dtype.kind in "fc":
                equal = np.array_equal(prior.reshape(-1).view(np.uint8), np.ascontiguousarray(array).reshape(-1).view(np.uint8))
            del prior
            if equal:
                references[key] = prior_name
                continue
        native = path / f"native-{uuid4()}.npy"
        with research_output_path(native).open("xb") as stream:
            np.save(stream, array, allow_pickle=False)
            stream.flush()
            os.fsync(stream.fileno())
        references[key] = native.name
    manifest = path / f"{revision}.json"
    _json_write(manifest, {"native_arrays": references,
                           "native_bytes": sum((path / name).stat().st_size for name in set(references.values())),
                           "saved_utc": datetime.now(timezone.utc).isoformat(), "record": encoded})
    pointer = path / f".latest-{uuid4()}.json"
    _json_write(pointer, {"record_file": manifest.name})
    os.replace(pointer, path / "latest.json")
    return manifest


def _local_file(parent: Path, name: str) -> Path:
    if not isinstance(name, str) or Path(name).name != name or ":" in name or "\\" in name:
        raise ValueError("Native file references must be local filenames")
    target = (parent / name).resolve()
    if target.parent != parent.resolve():
        raise ValueError("Native file reference escapes run directory")
    return target


def load_run(path: str | Path, mode: str | None = None, condition_id: str | None = None) -> dict:
    path = Path(path)
    if path.is_dir():
        path = path / "latest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if "record_file" in data:
        path = _local_file(path.parent, data["record_file"])
        data = json.loads(path.read_text(encoding="utf-8"))
    if "native_arrays" in data:
        arrays = {key: np.load(_local_file(path.parent, name), allow_pickle=False, mmap_mode="r")
                  for key,name in data["native_arrays"].items()}
        record = _decode(data["record"], arrays)
        arrays.clear()
    else:  # Earlier v1 whole-revision native archives remain readable.
        native = _local_file(path.parent, data["native_file"])
        with np.load(native, allow_pickle=False) as arrays:
            record = _decode(data["record"], arrays)
    _validate(record, mode, condition_id, "microsecond_stroboscopy_run")
    return record


def save_plan(path: str | Path, settings: Any, plan: Any = None) -> None:
    values = settings.to_dict() if hasattr(settings, "to_dict") else dict(settings)
    payload = {"schema_version": SCHEMA_VERSION, "experiment_id": EXPERIMENT_ID,
               "record_kind": "microsecond_stroboscopy_plan", "mode": values["mode"], "settings": values}
    _validate(payload, kind="microsecond_stroboscopy_plan")
    # Explicit Save Plan may replace the selected file. Runs never use this path.
    destination = Path(path)
    temporary = destination.with_name(destination.name + f".{uuid4()}.tmp")
    _json_write(temporary, payload)
    os.replace(temporary, destination)


def load_plan(path: str | Path, mode: str | None = None):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    _validate(data, mode, kind="microsecond_stroboscopy_plan")
    from .settings import StroboscopySettings
    return StroboscopySettings.from_dict(data["settings"])
