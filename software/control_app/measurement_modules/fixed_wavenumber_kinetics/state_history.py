"""Durable biological pump-state provenance, independent of runs and tab modes.

The host's exclusive instrument ownership serializes real dispatch operations.
An intent is fsynced before dispatch and is never erased by a missing marker,
failed acquisition, New run, changed save root or a different detector tab.
There are no digest comparisons or mutable shared acquisition sessions here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Mapping
from uuid import uuid4


IDENTITY_FIELDS = ("sample_id", "preparation_id", "cell_id", "condition_id", "position_id")
BIOLOGICAL_FIELDS = IDENTITY_FIELDS[:-1]
SCHEMA_VERSION = 1


class StateHistoryError(RuntimeError):
    """Consumed-state evidence cannot authorize the proposed event."""


def default_history_path() -> Path:
    base = Path(os.environ.get("PROGRAMDATA") or tempfile.gettempdir())
    return base / "ControlSystem" / "fixed_wavenumber_kinetics_state_history.jsonl"


def _identity(settings: Mapping) -> dict:
    result = {}
    for field in IDENTITY_FIELDS:
        value = settings.get(field)
        if not isinstance(value, str) or not value.strip():
            raise StateHistoryError(f"State history requires the measured {field}")
        result[field] = value
    return result


class StateHistory:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else default_history_path()

    def records(self):
        """Stream the append-only record. Ambiguous journal damage is explicit."""
        try:
            stream = self.path.open("r", encoding="utf-8")
        except FileNotFoundError:
            return
        except OSError as exc:
            raise StateHistoryError(f"Consumed-state journal cannot be read at {self.path}: {exc}") from exc
        with stream:
            for number, line in enumerate(stream, 1):
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict) or record.get("schema_version") != SCHEMA_VERSION:
                        raise ValueError("unsupported state-history schema")
                    if record.get("record_kind") not in {"pump_dispatch_intent", "pump_run_outcome"}:
                        raise ValueError("unknown state-history record kind")
                    if record["record_kind"] == "pump_dispatch_intent":
                        _identity(record["state"])
                        if not record.get("dispatch_id") or not record.get("run_id"):
                            raise ValueError("missing dispatch/run identity")
                except (ValueError, KeyError, TypeError) as exc:
                    raise StateHistoryError(
                        f"Consumed-state journal has an unresolved record at {self.path}:{number}; "
                        "preserve it and reconstruct state provenance before another biological pump"
                    ) from exc
                yield record

    def check(self, settings: Mapping, resolved: Mapping) -> dict:
        identity = _identity(settings)
        consumed = []
        used_fresh_ids = set()
        for record in self.records():
            if record["record_kind"] != "pump_dispatch_intent":
                continue
            if record.get("fresh_state_record_id"):
                used_fresh_ids.add(record["fresh_state_record_id"])
            if all(record["state"][field] == identity[field] for field in BIOLOGICAL_FIELDS):
                consumed.append({"dispatch_id": record["dispatch_id"], "run_id": record["run_id"],
                    "instance_id": record.get("instance_id"), "position_id": record["state"]["position_id"]})
        fresh = resolved.get("fresh_state_record")
        cryogenic = str(settings.get("condition_profile", "")).startswith("cryo")
        if fresh is not None:
            if not isinstance(fresh, Mapping) or fresh.get("accepted") is not True:
                raise StateHistoryError("Fresh equivalent state requires an accepted measured record, not a checkbox")
            record_id = fresh.get("record_id")
            if not isinstance(record_id, str) or not record_id.strip():
                raise StateHistoryError("Fresh equivalent state record_id is missing")
            for field in ("accepted_by", "source_run_id", "equivalence_basis"):
                if not isinstance(fresh.get(field), str) or not fresh[field].strip():
                    raise StateHistoryError(f"Fresh equivalent state record requires a named {field}")
            mismatches = [field for field in IDENTITY_FIELDS if fresh.get(field) != identity[field]]
            if mismatches:
                raise StateHistoryError("Fresh equivalent state record does not match " + ", ".join(mismatches))
            if record_id in used_fresh_ids:
                raise StateHistoryError(f"Fresh equivalent state record {record_id!r} was already consumed by a pump dispatch")
        elif cryogenic and consumed:
            raise StateHistoryError(
                "This cryogenic sample/preparation/cell/condition was already consumed by a pump dispatch; "
                "an accepted fresh_state_record matching all identities is required. Changing the "
                "position, save location or detector mode does not establish a fresh equivalent state."
            )
        return {"state": identity, "previous_dispatches": consumed,
            "fresh_state_record_id": fresh["record_id"] if fresh is not None else None,
            "fresh_state_record": dict(fresh) if fresh is not None else None,
            "history_path": str(self.path)}

    def _append(self, record: Mapping) -> None:
        # The caller holds host ownership until the durable write and all later
        # hardware cleanup and native preservation finish.
        payload = json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise StateHistoryError(f"Pump state could not be durably journaled at {self.path}: {exc}; no new pump command is authorized") from exc

    def consume(self, settings: Mapping, resolved: Mapping, operation, event: Mapping) -> dict:
        verified = self.check(settings, resolved)
        record = {"schema_version": SCHEMA_VERSION, "record_kind": "pump_dispatch_intent",
            "dispatch_id": str(uuid4()), "created_utc": datetime.now(timezone.utc).isoformat(),
            "run_id": operation.run_id, "instance_id": operation.instance_id,
            "simulation": not operation.hardware,
            "condition_profile": settings["condition_profile"], "state": verified["state"],
            "fresh_state_record_id": verified["fresh_state_record_id"],
            "fresh_state_record": verified["fresh_state_record"],
            "event_index": event["event_index"], "position_cm1": event.get("position_cm1"),
            "baseline": event.get("baseline"), "reset_record_id": resolved.get("reset_record_id"),
            "meaning": "State consumed conservatively before pump command; observed delivery is recorded separately"}
        self._append(record)
        return record

    def outcome(self, operation, record: Mapping) -> None:
        from .persistence import json_data
        for event in record.get("events", ()):
            intent = event.get("state_dispatch_intent")
            if not intent:
                continue
            self._append(json_data({"schema_version": SCHEMA_VERSION, "record_kind": "pump_run_outcome",
                "created_utc": datetime.now(timezone.utc).isoformat(), "run_id": operation.run_id,
                "instance_id": operation.instance_id, "dispatch_id": intent["dispatch_id"],
                "status": record.get("status"), "error": record.get("error"),
                "baseline": event.get("baseline"), "reset": event.get("reset"),
                "pump_timestamps": event.get("pump_timestamps", []),
                "original_pump_timestamp": event.get("original_pump_timestamp"),
                "restoration_safe_verified": record.get("restoration", {}).get("safe_verified")}))
