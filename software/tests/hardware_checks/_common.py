"""Shared helpers for real-hardware check scripts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import json
import sys


SOFTWARE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = SOFTWARE_ROOT.parent
if str(SOFTWARE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOFTWARE_ROOT))


def today_stamp() -> str:
    """Return the local YYYYMMDD date stamp for run folders."""

    return datetime.now().strftime("%Y%m%d")


def utc_now() -> str:
    """Return a UTC ISO timestamp."""

    return datetime.now(UTC).isoformat(timespec="seconds")


def write_json(path: str | Path, data: Any) -> Path:
    """Write pretty JSON and return the path."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def write_blocked(
    path: str | Path,
    *,
    title: str,
    blockers: list[str],
    next_actions: list[str],
    context: dict[str, Any] | None = None,
) -> Path:
    """Write a BLOCKED.md file with concrete next actions."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {title}",
        "",
        f"timestamp_utc: {utc_now()}",
        "",
        "## Blockers",
    ]
    lines.extend(f"- {item}" for item in blockers)
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in next_actions)
    if context:
        lines.extend(["", "## Context", "```json", json.dumps(context, indent=2, sort_keys=True), "```"])
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
