"""Lossless, versioned run preservation, including partial and rejected records.

JSON describes the record tree; NumPy arrays retain their exact native dtypes,
ticks, values and NaN representations in NPZ. No digest is an operational gate.
The manifest is committed last, and interrupted writes remain as partial files.
"""
from __future__ import annotations

from control_app.paths import research_output_path

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from uuid import uuid4

import numpy as np

from . import data
from .data import EXPERIMENT_ID, SCHEMA_VERSION, SavedRun

_TYPES = {name: value for name, value in vars(data).items()
          if isinstance(value, type) and is_dataclass(value)}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _identifier(value: str, label: str) -> str:
    if not value or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", value) or value in (".", ".."):
        raise ValueError(f"Invalid {label}: use a stable filename-safe identifier")
    # Windows drive/path separators are excluded even when IDs elsewhere allow ':'.
    if ":" in value:
        raise ValueError(f"{label} may not contain a drive separator")
    return value


def _encode(value: Any, arrays: dict[str, np.ndarray]) -> Any:
    if isinstance(value, (np.ndarray, np.generic)):
        array = np.asarray(value)
        if array.dtype.hasobject:
            raise TypeError("Object arrays cannot be safely preserved as native numeric streams")
        key = f"array_{len(arrays):06d}"
        arrays[key] = array
        return {"$array": key, "scalar": isinstance(value, np.generic)}
    if is_dataclass(value) and not isinstance(value, type):
        return {"$record": type(value).__name__, "fields": {f.name: _encode(getattr(value, f.name), arrays) for f in fields(value)}}
    if isinstance(value, Mapping):
        return {"$mapping": [[_encode(k, arrays), _encode(v, arrays)] for k, v in value.items()]}
    if isinstance(value, tuple):
        return {"$tuple": [_encode(item, arrays) for item in value]}
    if isinstance(value, list):
        return [_encode(item, arrays) for item in value]
    if isinstance(value, Path):
        return {"$path": str(value)}
    if isinstance(value, bytes):
        key = f"array_{len(arrays):06d}"
        arrays[key] = np.frombuffer(value, dtype=np.uint8).copy()
        return {"$bytes": key}
    if isinstance(value, float) and not np.isfinite(value):
        return {"$float": value.hex()}
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError(f"Cannot preserve unsupported record value {type(value).__name__}; supply explicit native data")


def _decode(value: Any, arrays: Mapping[str, np.ndarray]) -> Any:
    if isinstance(value, list):
        return [_decode(item, arrays) for item in value]
    if not isinstance(value, dict):
        return value
    if "$array" in value:
        array = np.array(arrays[value["$array"]], copy=True)
        return array[()] if value.get("scalar") else array
    if "$bytes" in value:
        return arrays[value["$bytes"]].tobytes()
    if "$tuple" in value:
        return tuple(_decode(item, arrays) for item in value["$tuple"])
    if "$mapping" in value:
        return {_decode(k, arrays): _decode(v, arrays) for k, v in value["$mapping"]}
    if "$path" in value:
        return Path(value["$path"])
    if "$float" in value:
        return float.fromhex(value["$float"])
    if "$record" in value:
        payload = {k: _decode(v, arrays) for k, v in value["fields"].items()}
        cls = _TYPES.get(value["$record"])
        return cls(**payload) if cls else payload
    raise ValueError("Unrecognized versioned run record encoding")


def save_run(root: str | Path, mode: str | None = None, run_id: str | None = None, *,
             record: Mapping[str, Any] | None = None, movies: Sequence[Any] = (),
             plan: Any = None, results: Sequence[Any] = (),
             metadata: Mapping[str, Any] | None = None) -> Path:
    """Persist to host-reserved exact path, or build hierarchy for standalone use.

    ``save_run(operation.output_path, record=record)`` uses that exact directory.
    Supplying ``run_id`` creates ``root/repeated_rapid_scan/mode/run_id``.
    Existing run/native files are never overwritten, and serialization failure
    leaves the caller's in-memory native records unchanged.
    """
    payload = dict(record) if record is not None else {
        "native_movies": tuple(movies), "plan": plan, "processed": tuple(results),
        "metadata": dict(metadata or {}),
    }
    mode = mode or payload.get("mode") or (getattr(movies[0], "mode", None) if movies else None)
    if mode not in ("single", "dual"):
        raise ValueError("Run mode must be single or dual")
    target = research_output_path(root).expanduser().resolve()
    if run_id is not None:
        target = target / EXPERIMENT_ID / mode / _identifier(run_id, "run_id")
    else:
        run_id = str(payload.get("run_id") or target.name or uuid4().hex)
    research_output_path(target).mkdir(parents=True, exist_ok=True)
    if (target/"run.json").exists() or (target/"native.npz").exists():
        raise FileExistsError(f"A preserved run already exists at {target}")
    payload.setdefault("run_id", run_id)
    payload.setdefault("mode", mode)
    arrays: dict[str, np.ndarray] = {}
    encoded = _encode(payload, arrays)
    created = _utc()
    manifest = {"experiment_id": EXPERIMENT_ID, "schema_version": SCHEMA_VERSION,
                "record_kind": "repeated_rapid_scan_run", "mode": mode,
                "instance_id": f"{EXPERIMENT_ID}:{mode}", "run_id": run_id,
                "created_utc": created, "native_file": "native.npz",
                "array_inventory": {key: {"shape": list(array.shape), "dtype": str(array.dtype),
                                           "bytes": int(array.nbytes)} for key,array in arrays.items()},
                "record": encoded}
    # Use exclusive partial-file creation. A failed save remains inspectable;
    # no restoration, rejected record or prior run is erased to retry a write.
    token = uuid4().hex
    partial_native = target/f"native.{token}.partial.npz"
    partial_manifest = target/f"run.{token}.partial.json"
    with research_output_path(partial_native).open("xb") as handle:
        np.savez(handle, **arrays)
        handle.flush()
        os.fsync(handle.fileno())
    with research_output_path(partial_manifest).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(partial_native, target/"native.npz")
    os.replace(partial_manifest, target/"run.json")
    return target


def load_run(path: str | Path, *, expected_mode: str | None = None,
             expected_condition_id: str | None = None) -> SavedRun:
    target = Path(path).expanduser().resolve()
    manifest_path = target if target.is_file() else target/"run.json"
    target = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("experiment_id") != EXPERIMENT_ID or manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Incompatible experiment or run schema version")
    mode = manifest.get("mode")
    if mode not in ("single", "dual") or manifest.get("instance_id") != f"{EXPERIMENT_ID}:{mode}":
        raise ValueError("Incompatible detector mode or instance identity")
    if expected_mode is not None and mode != expected_mode:
        raise ValueError(f"Detector mode mismatch: expected {expected_mode}, found {mode}")
    if manifest.get("native_file") != "native.npz":
        raise ValueError("Run schema requires its local native.npz record")
    with np.load(target/"native.npz", allow_pickle=False) as archive:
        payload = _decode(manifest["record"], archive)
    if not isinstance(payload, Mapping):
        raise ValueError("Run record must contain an explicit mapping")
    native_movies = payload.get("native_movies", payload.get("movies", ()))
    for movie in native_movies:
        if isinstance(movie, data.NativeMovie):
            if movie.mode != mode or movie.experiment_id != EXPERIMENT_ID or movie.schema_version != SCHEMA_VERSION:
                raise ValueError("Saved native movie has incompatible experiment/mode/version")
            if expected_condition_id is not None and movie.condition_id != expected_condition_id:
                raise ValueError(f"Condition mismatch: expected {expected_condition_id}, found {movie.condition_id}")
    condition = payload.get("condition_id", payload.get("metadata", {}).get("condition_id"))
    if expected_condition_id is not None and condition is not None and condition != expected_condition_id:
        raise ValueError(f"Condition mismatch: expected {expected_condition_id}, found {condition}")
    return SavedRun(str(manifest["run_id"]), mode, payload, str(manifest["created_utc"]), target)


def save_baseline(path: str | Path, baseline: data.SpectralBaseline) -> Path:
    """Keep sequential backgrounds and unpumped baselines as separate records."""
    return save_run(path, record={"mode": baseline.mode, "condition_id": baseline.condition_id,
                                 "baseline": baseline, "record_kind": "spectral_baseline"})


def load_baseline(path: str | Path, *, expected_mode: str | None = None,
                  expected_condition_id: str | None = None) -> data.SpectralBaseline:
    saved = load_run(path, expected_mode=expected_mode, expected_condition_id=expected_condition_id)
    baseline = saved.record.get("baseline")
    if not isinstance(baseline, data.SpectralBaseline):
        raise ValueError("The selected record does not contain a versioned spectral baseline")
    if baseline.schema_version != SCHEMA_VERSION or baseline.experiment_id != EXPERIMENT_ID:
        raise ValueError("Incompatible spectral baseline schema")
    return baseline
