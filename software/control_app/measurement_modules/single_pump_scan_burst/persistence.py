"""Durable append-only native records for a non-repeatable observation.

JSON is metadata; NPZ retains each native numeric dtype without pickle or a
hash-matching gate. Each block is committed before the next dark wait. A crash
may leave an explicitly reported truncated last journal line or orphan chunk;
neither is repaired into a successful observation.
"""
from __future__ import annotations

from control_app.paths import research_output_path

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from uuid import uuid4

import numpy as np

EXPERIMENT_ID = "single_pump_scan_burst"
SCHEMA_VERSION = "single-pump-scan-burst/1"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def json_value(value):
    if hasattr(value, "to_dict"):
        return json_value(value.to_dict())
    if is_dataclass(value):
        return json_value(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def _safe_name(name):
    name = str(name)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) or name in (".", ".."):
        raise ValueError("Record name must be a simple stable identifier")
    return name


def write_json(path, data, *, replace=False):
    """Flush a new file then publish it; never overwrite a native record."""
    path = Path(path)
    if path.exists() and not replace:
        raise FileExistsError(path)
    temporary = path.with_name(path.name + ".pending-" + uuid4().hex)
    with research_output_path(temporary).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(json_value(data), stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if replace:
        os.replace(temporary, path)
    else:
        # Hard-link publication is exclusive on Windows and POSIX. The pending
        # file remains visible if publication fails; no old artifact is lost.
        os.link(temporary, path)
        temporary.unlink()


class RunStore:
    def __init__(self, path, metadata, *, create=True):
        self.path = research_output_path(path)
        self.metadata = json_value(metadata)
        self.metadata.setdefault("schema_version", SCHEMA_VERSION)
        self.metadata.setdefault("experiment_id", EXPERIMENT_ID)
        if create:
            research_output_path(self.path).mkdir(parents=True, exist_ok=False)
            (research_output_path(self.path / "chunks")).mkdir()
            (research_output_path(self.path / "records")).mkdir()
            (research_output_path(self.path / "checkpoints")).mkdir()
            write_json(self.path / "metadata.json", self.metadata)
            self.sequence = 0
            self.append_event("created", {"created_utc": utc_now()})
        else:
            loaded = load_run(self.path)
            self.metadata = loaded["metadata"]
            self.sequence = max((e["sequence"] for e in loaded["events"]), default=-1) + 1
            if loaded["journal_errors"]:
                raise ValueError("Interrupted journal must be preserved; continue in a new linked record")

    def append_event(self, kind, payload):
        event = {"sequence": self.sequence, "event_id": str(uuid4()), "utc": utc_now(),
                 "kind": str(kind), "payload": json_value(payload)}
        data = (json.dumps(event, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
        with (research_output_path(self.path / "events.jsonl")).open("ab") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        self.sequence += 1
        return event

    def save_chunk(self, block_id, native):
        name = _safe_name(block_id)
        destination = self.path / "chunks" / (name + ".npz")
        arrays = {}
        for key, value in native.items():
            if isinstance(value, Mapping):
                raise ValueError(f"Native {key}: flatten nested arrays; use save_record for metadata")
            array = np.asarray(value)
            if array.dtype.hasobject:
                raise ValueError(f"Native {key}: object arrays are not a portable native stream")
            arrays[str(key)] = array
        # Exclusive creation prevents silent reuse of a block ID. An interrupted
        # file remains an artifact and is never considered a committed chunk.
        with research_output_path(destination).open("xb") as stream:
            np.savez(stream, **arrays)
            stream.flush()
            os.fsync(stream.fileno())
        relative = destination.relative_to(self.path).as_posix()
        self.append_event("native_chunk", {"block_id": name, "path": relative,
                          "byte_size": destination.stat().st_size,
                          "arrays": {k: {"dtype": str(v.dtype), "shape": list(v.shape)} for k, v in arrays.items()}})
        return relative

    def save_record(self, name, mapping):
        destination = self.path / "records" / (_safe_name(name) + ".json")
        write_json(destination, mapping)
        relative = destination.relative_to(self.path).as_posix()
        self.append_event("record", {"path": relative, "byte_size": destination.stat().st_size})
        return relative

    def checkpoint(self, state):
        checkpoint = {"utc": utc_now(), "sequence": self.sequence, "state": json_value(state)}
        name = f"checkpoint-{self.sequence:08d}-{uuid4().hex}.json"
        write_json(self.path / "checkpoints" / name, checkpoint)
        self.append_event("checkpoint", {"path": f"checkpoints/{name}"})
        write_json(self.path / "current.json", checkpoint, replace=True)
        return checkpoint

    def finalize(self, status, **fields):
        manifest = {"schema_version": SCHEMA_VERSION, "experiment_id": EXPERIMENT_ID,
                    "status": str(status), "closed_utc": utc_now(), **json_value(fields)}
        self.append_event("finalized", manifest)
        # Each finalization is retained even if an explicitly resumed run updates
        # the convenience pointer. Continuation never authorizes another pump.
        write_json(self.path / "records" / f"finalization-{self.sequence:08d}.json", manifest)
        write_json(self.path / "manifest.json", manifest, replace=True)
        return manifest


def _inside(root, relative):
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError("Native record path escapes its observation directory")
    return candidate


def load_run(path, expected_mode=None, expected_condition_id=None):
    """Load a run; condition labels remain metadata, including in legacy files.

    ``expected_condition_id`` is retained for callers of the original schema.
    It does not select an acquisition procedure or restrict loading.
    """
    path = Path(path)
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("experiment_id") != EXPERIMENT_ID or metadata.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Incompatible experiment or run schema")
    for key, expected in (("mode", expected_mode),):
        if expected is not None and metadata.get(key) != expected:
            raise ValueError(f"Incompatible {key}: saved {metadata.get(key)!r}; requested {expected!r}")
    events, errors = [], []
    journal = path / "events.jsonl"
    if journal.exists():
        with journal.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                try:
                    event = json.loads(line)
                    if event["sequence"] != len(events):
                        raise ValueError("Journal sequence discontinuity")
                    events.append(event)
                except (ValueError, KeyError) as exc:
                    errors.append(f"Journal line {line_number}: {exc}")
                    break
    chunks = [event["payload"]["path"] for event in events if event["kind"] == "native_chunk"]
    for relative in chunks:
        if not _inside(path, relative).is_file():
            errors.append(f"Missing committed native chunk: {relative}")
    checkpoint = {}
    checkpoints = [e for e in events if e["kind"] == "checkpoint"]
    if checkpoints:
        checkpoint = json.loads(_inside(path, checkpoints[-1]["payload"]["path"]).read_text(encoding="utf-8"))
    finalized = [e["payload"] for e in events if e["kind"] == "finalized"]
    manifest = finalized[-1] if finalized else {"status": "incomplete", "reason": "No durable finalization"}
    if errors:
        manifest = {**manifest, "status": "incomplete", "journal_errors": errors}
    return {"path": str(path), "output_path": str(path), "metadata": metadata, "events": events,
            "checkpoint": checkpoint, "manifest": manifest, "status": manifest["status"],
            "chunks": chunks, "journal_errors": errors}


def iter_chunks(path, *, cancel=None):
    # Stream the journal as well as arrays: dark-wait temperature history and
    # native poll count can grow with the observation without a RAM backlog.
    path = Path(path)
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("Incompatible experiment")
    with (path / "events.jsonl").open(encoding="utf-8") as journal:
        for line in journal:
            if cancel:
                cancel()
            try:
                event = json.loads(line)
            except ValueError:
                return  # Retain prior committed chunks, not the torn tail.
            if event["kind"] != "native_chunk":
                continue
            with np.load(_inside(path, event["payload"]["path"]), allow_pickle=False) as source:
                yield {key: source[key] for key in source.files}


def compatibility_conflicts(saved, requested, prefix=""):
    """Explicit structural comparison, never a digest acceptance gate."""
    saved, requested = json_value(saved), json_value(requested)
    if isinstance(saved, dict) and isinstance(requested, dict):
        result = []
        for key in sorted(set(saved) | set(requested)):
            name = f"{prefix}.{key}" if prefix else key
            if key not in saved or key not in requested:
                result.append(f"{name}: missing from {'saved record' if key not in saved else 'requested plan'}")
            else:
                result.extend(compatibility_conflicts(saved[key], requested[key], name))
        return result
    if saved == requested:
        return []
    return [f"{prefix}: saved {saved!r}; requested {requested!r}"]
