"""Read historical pump-state records as optional provenance.

The acquisition runner does not consult or write this journal. Historical
entries remain readable, including incomplete and interrupted observations;
they do not grant permission or prevent a raw or relative measurement.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Mapping


def default_history_path() -> Path:
    return Path(os.environ.get("PROGRAMDATA") or tempfile.gettempdir()) / "ControlSystem" / "fixed_wavenumber_kinetics_state_history.jsonl"


class StateHistoryError(ValueError):
    """An explicitly loaded historical record cannot be read."""


class StateHistory:
    """Compatibility reader for old journals; never an operation gate."""
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else default_history_path()

    def records(self):
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                try:
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError("historical row is not an object")
                except (ValueError, TypeError) as exc:
                    raise StateHistoryError(f"Historical record cannot be decoded at {self.path}:{number}") from exc
                yield row

    def check(self, settings: Mapping, resolved: Mapping | None = None) -> dict:
        """Return advisory matches for callers loading an older saved project."""
        fields = ("sample_id", "preparation_id", "cell_id", "condition_id")
        rows = [row for row in self.records() if row.get("record_kind") == "pump_dispatch_intent"
            and all(row.get("state", {}).get(key) == settings.get(key) for key in fields)]
        return {"history_path": str(self.path), "previous_dispatches": rows,
            "advisory_only": True, "acquisition_blocked": False}
