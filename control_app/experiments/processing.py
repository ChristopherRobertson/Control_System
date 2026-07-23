"""Allow-listed processing and result export operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
import csv
import json


Processor = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


class ProcessingRegistry:
    def __init__(self) -> None:
        self._processors: dict[str, Processor] = {}

    def register(self, name: str, processor: Processor) -> None:
        if name in self._processors:
            raise ValueError(f"Processor {name!r} is already registered")
        self._processors[name] = processor

    def process(self, name: str, raw: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
        if name not in self._processors:
            raise ValueError(f"Processing method {name!r} is not allow-listed")
        return self._processors[name](raw, settings)


def default_processing_registry() -> ProcessingRegistry:
    registry = ProcessingRegistry()
    registry.register("identity", lambda raw, settings: {"data": raw, "settings": settings})
    return registry


def export_standard_result(result: dict[str, Any], definition: dict[str, Any], path: str | Path, format_name: str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    envelope = {"format_version": "1.0", "experiment": definition, "result": result}
    if format_name == "json":
        target.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif format_name == "csv":
        rows = result.get("rows")
        if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
            raise ValueError("CSV export requires a non-empty result.rows list of mappings")
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    else:
        raise ValueError(f"Export format {format_name!r} is not allow-listed")
    return target
