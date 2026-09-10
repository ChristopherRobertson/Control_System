"""Versioned, append-only native retention for fixed-wavenumber observations.

NPZ is used as a numeric container, never a pickle. Device integers, dtypes,
NaNs and detector values survive exactly; JSON contains interpretation metadata.
No hash value is an operational requirement.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

import numpy as np

EXPERIMENT_ID = "fixed_wavenumber_kinetics"
SCHEMA_VERSION = "1.0"


class RecordCompatibilityError(ValueError):
    pass


def json_data(value: Any) -> Any:
    if is_dataclass(value):
        value = value.to_dict() if hasattr(value, "to_dict") else asdict(value)
    if isinstance(value, Mapping):
        return {str(k): json_data(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_data(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_data(value.tolist())
    if isinstance(value, np.generic):
        return json_data(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def _write_json(path: Path, record: Mapping[str, Any], *, exclusive: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "w", encoding="utf-8") as stream:
        json.dump(json_data(record), stream, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def write_json(path: str | Path, record: Mapping[str, Any]) -> Path:
    """Save an explicitly selected plan destination using atomic replacement."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + "." + uuid4().hex + ".pending")
    _write_json(temporary, record)
    os.replace(temporary, target)
    return target


class NativeChunkWriter:
    """Retain each chunk before the next poll; constant memory across chunks.

    Every completed NPZ is recoverable even if writing its journal entry fails.
    Files left with ``.pending`` indicate interrupted writes and are preserved.
    The caller must stop acquisition when append raises; silently dropping a
    chunk or overwriting a rolling buffer is never permitted.
    """

    def __init__(self, run_directory: str | Path):
        self.run_directory = Path(run_directory)
        self.directory = self.run_directory / "native"
        self.directory.mkdir(parents=True, exist_ok=True)
        self._journal = (self.directory / "chunks.jsonl").open("a", encoding="utf-8")
        self._closed = False

    def append(self, chunk: Mapping[str, Any], **metadata: Any) -> dict[str, Any]:
        if self._closed:
            raise ValueError("Native writer is closed")
        arrays: dict[str, np.ndarray] = {}

        def pack(value):
            if isinstance(value, np.ndarray):
                if value.dtype.hasobject:
                    raise TypeError("Object arrays are not native numeric data")
                key = f"array_{len(arrays):05d}"
                arrays[key] = value
                return {"__native_array__": key}
            if isinstance(value, Mapping):
                return {str(k): pack(v) for k, v in value.items()}
            if isinstance(value, (tuple, list)):
                # Preserve list-of-record metadata and numeric scalar precision.
                return [pack(v) for v in value]
            if isinstance(value, np.generic):
                return pack(np.asarray(value))
            return value

        packed = pack(dict(chunk))
        identifier = f"chunk-{uuid4().hex}"
        relative = Path("native") / f"{identifier}.npz"
        final = self.run_directory / relative
        pending = final.with_suffix(".pending")
        envelope = {"schema_version": SCHEMA_VERSION, "chunk": packed,
                    "metadata": json_data(metadata)}
        with pending.open("xb") as output:
            np.savez(output, __metadata__=np.asarray(json.dumps(envelope, allow_nan=False)), **arrays)
            output.flush()
            os.fsync(output.fileno())
        pending.rename(final)
        ref = {"path": relative.as_posix(), "schema_version": SCHEMA_VERSION,
               "byte_size": final.stat().st_size, "native_array_bytes": sum(v.nbytes for v in arrays.values()),
               "created_utc": datetime.now(timezone.utc).isoformat(), **json_data(metadata)}
        self._journal.write(json.dumps(ref, allow_nan=False) + "\n")
        self._journal.flush()
        os.fsync(self._journal.fileno())
        return ref

    def close(self):
        if not self._closed:
            self._journal.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _contained_path(directory: Path, relative: str) -> Path:
    target = (directory / relative).resolve()
    if not target.is_relative_to(directory.resolve()):
        raise ValueError("Native reference must remain inside its run directory")
    return target


def read_native_chunk(run_directory: str | Path, reference: Mapping[str, Any] | str) -> dict[str, Any]:
    relative = reference["path"] if isinstance(reference, Mapping) else reference
    path = _contained_path(Path(run_directory), str(relative))
    with np.load(path, allow_pickle=False) as archive:
        envelope = json.loads(str(archive["__metadata__"].item()))
        if envelope.get("schema_version") != SCHEMA_VERSION:
            raise RecordCompatibilityError("Unsupported native chunk schema_version")

        def unpack(value):
            if isinstance(value, dict):
                if set(value) == {"__native_array__"}:
                    return archive[value["__native_array__"]].copy()
                return {k: unpack(v) for k, v in value.items()}
            return [unpack(v) for v in value] if isinstance(value, list) else value

        result = unpack(envelope["chunk"])
        result.setdefault("metadata", envelope.get("metadata", {}))
        return result


def iter_native_chunks(record: Mapping[str, Any], base_directory: str | Path | None = None) -> Iterator[dict]:
    directory = Path(base_directory or record.get("run_directory", "."))
    for ref in record.get("native_chunks", ()):
        if "sample" in ref:
            yield dict(ref)  # Convenient injected/retained in-memory scientific records.
        else:
            chunk = read_native_chunk(directory, ref)
            chunk["metadata"] = {**dict(ref), **chunk.get("metadata", {})}
            yield chunk


def validate_record(record: Mapping[str, Any], *, mode: str | None = None,
                    condition_id: str | None = None) -> None:
    if record.get("experiment_id") != EXPERIMENT_ID:
        raise RecordCompatibilityError("Incompatible experiment_id")
    if record.get("schema_version") not in (SCHEMA_VERSION, 1):
        raise RecordCompatibilityError("Incompatible run schema_version")
    actual_mode = record.get("mode")
    if actual_mode not in ("single", "dual") or (mode is not None and actual_mode != mode):
        raise RecordCompatibilityError("Incompatible detector mode")
    if "instance_id" in record and record["instance_id"] != f"{EXPERIMENT_ID}:{actual_mode}":
        raise RecordCompatibilityError("Incompatible instance_id")
    settings = record.get("settings", record.get("plan", {}).get("settings", {}))
    actual_condition = record.get("condition_id", settings.get("condition_id", settings.get("condition", {}).get("condition_id")))
    if condition_id is not None and condition_id != actual_condition:
        raise RecordCompatibilityError("Incompatible condition_id")


def save_run(record: Mapping[str, Any], path: str | Path) -> Path:
    validate_record(record)
    target = Path(path)
    if target.suffix.lower() != ".json":
        target = target / "run.json"
    return _write_json(target, record)


def load_run(path: str | Path, mode: str | None = None, condition_id: str | None = None) -> dict:
    target = Path(path)
    if target.is_dir():
        target = target / "run.json"
    record = json.loads(target.read_text(encoding="utf-8"))
    validate_record(record, mode=mode, condition_id=condition_id)
    # A moved complete run remains loadable; relative native paths establish parentage.
    record["run_directory"] = str(target.parent.resolve())
    return record


def load_analysis_inputs(record: Mapping[str, Any]) -> dict[str, dict | None]:
    """Resolve only the explicit saved parents required to reproduce analysis.

    ``analysis_inputs`` maps ``blank`` and ``preliminary`` to records containing
    a stable ``run_id`` and ``native_path`` to that parent's saved run JSON (or
    complete run directory). Absolute paths and paths relative to this run's
    directory are supported. No nearest-file search, identity substitution, or
    invented baseline is allowed. Absent references remain None so processing
    can report missing support; an explicit but unavailable parent is an error.
    Native chunk paths must remain inside the referenced parent's directory.
    """
    validate_record(record)
    references = record.get("analysis_inputs", {})
    if not isinstance(references, Mapping):
        raise RecordCompatibilityError("analysis_inputs must be an explicit parent-reference mapping")
    settings = record.get("settings", record.get("plan", {}).get("settings", {}))
    condition = record.get("condition_id", settings.get("condition_id"))
    result = {"blank": None, "preliminary": None}
    for kind in result:
        reference = references.get(kind)
        if reference is None:
            continue
        if (not isinstance(reference, Mapping) or not reference.get("run_id")
                or not isinstance(reference.get("native_path"), (str, os.PathLike)) or not reference.get("native_path")):
            raise RecordCompatibilityError(f"{kind} parent needs an explicit run_id and native_path")
        if not condition:
            raise RecordCompatibilityError("The current run needs a condition_id to resolve compatible analysis parents")
        path = Path(reference["native_path"])
        if not path.is_absolute():
            if not record.get("run_directory"):
                raise RecordCompatibilityError(f"Relative {kind} parent needs the current run_directory")
            path = Path(record["run_directory"]) / path
        try:
            parent = load_run(path, mode=record["mode"], condition_id=condition)
        except (OSError, ValueError, TypeError) as exc:
            raise RecordCompatibilityError(f"Cannot load explicit {kind} parent {path}: {exc}") from exc
        if parent.get("run_id") != reference["run_id"]:
            raise RecordCompatibilityError(f"{kind} parent run_id differs from the recorded source")
        for identity in ("experiment_id", "mode", "condition_id"):
            if identity in reference and reference[identity] != parent.get(identity):
                raise RecordCompatibilityError(f"{kind} parent {identity} differs from its recorded source reference")
        if "schema_version" in reference and reference["schema_version"] not in (SCHEMA_VERSION, 1):
            raise RecordCompatibilityError(f"{kind} parent reference has unsupported schema_version")
        if parent.get("kind") != kind:
            raise RecordCompatibilityError(f"{kind} parent has incompatible record kind {parent.get('kind')!r}")
        if parent.get("status") not in ("complete", "completed"):
            raise RecordCompatibilityError(f"{kind} parent did not complete; it cannot supply a compatible analysis baseline")
        # Parent metadata alone cannot silently replace its missing observations.
        chunks = parent.get("native_chunks", ())
        if not chunks:
            raise RecordCompatibilityError(f"{kind} parent contains no retained native observations")
        for chunk in chunks:
            if not isinstance(chunk, Mapping) or not chunk.get("path"):
                raise RecordCompatibilityError(f"{kind} parent lacks a saved native chunk reference")
            try:
                native = _contained_path(Path(parent["run_directory"]), str(chunk["path"]))
            except ValueError as exc:
                raise RecordCompatibilityError(f"{kind} parent native path is invalid: {exc}") from exc
            if not native.is_file():
                raise RecordCompatibilityError(f"{kind} parent native observation is unavailable: {native}")
        parent["source_reference"] = dict(reference)
        result[kind] = parent
    return result


def recover_native_references(run_directory: str | Path) -> list[dict]:
    """Discover all fully written native chunks after interrupted manifest saving."""
    directory = Path(run_directory)
    refs = []
    for path in sorted((directory / "native").glob("*.npz")):
        relative = path.relative_to(directory).as_posix()
        chunk = read_native_chunk(directory, relative)
        reference = {"path": relative, "byte_size": path.stat().st_size,
                     **chunk.get("metadata", {})}
        ticks = next((np.asarray(chunk.get(role, {}).get("timestamp", ())) for role in ("sample", "reference", "timing")
                      if len(chunk.get(role, {}).get("timestamp", ()))), np.asarray([]))
        first = int(ticks[0]) if len(ticks) else None
        refs.append((first, path.stat().st_mtime_ns, reference))
    # UUID filenames never imply acquisition order. Restore clock order, with
    # filesystem UTC timestamps only for malformed chunks lacking device ticks.
    refs.sort(key=lambda item: (item[0] is None, item[0] if item[0] is not None else item[1]))
    return [item[2] for item in refs]


def export_stroboscopic_handoff(record: Mapping[str, Any], path: str | Path,
                                *, selected_times_s=()) -> Path:
    """File exchange carries discovery evidence, never fabricates ns kinetics."""
    validate_record(record)
    return _write_json(Path(path), {
        "schema_version": SCHEMA_VERSION, "record_kind": "fixed_point_discovery_handoff",
        "producer_experiment_id": EXPERIMENT_ID, "producer_instance_id": f"{EXPERIMENT_ID}:{record['mode']}",
        "source_run_id": record.get("run_id"), "source_native_path": record.get("run_directory"),
        "condition": record.get("plan", {}).get("settings", record.get("settings", {})),
        "suggested_time_window_s": list(selected_times_s),
        "observed_events": record.get("events", []),
        "measured_acquisition_response": record.get("measured_response"),
        "requires": ["compatible accepted sample selection", "measured optical time zero and complete IRF",
                     "accepted equivalent-state reset before each repeated event"],
        "claim_limit": "Direct HF2LI fixed-point data do not establish nanosecond kinetics. Open this evidence alongside an existing stroboscopic data product; no other experiment package is required.",
    })


def export_analysis_csv(record: Mapping[str, Any], path: str | Path) -> Path:
    import csv
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as stream:
        fields = ["event_index", "position_cm1", "time_s", "sample", "reference", "ratio", "delta_absorbance", "absolute_absorbance"]
        writer = csv.writer(stream)
        writer.writerow(fields)
        for event in record.get("analysis", {}).get("events", ()):
            for i, moment in enumerate(event.get("time_s", ())):
                row = [event.get("event_index"), event.get("position_cm1"), moment]
                for name in fields[3:]:
                    value = event.get(name)
                    row.append("" if value is None else value[i])
                writer.writerow(row)
    return target
