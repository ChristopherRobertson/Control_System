"""Show dependency-ready phases from the unified registry without authorizing them."""

from __future__ import annotations

from pathlib import Path

import yaml

from validate_phase_registry import REGISTRY, validate


def main() -> int:
    order = validate()
    data = yaml.safe_load(Path(REGISTRY).read_text(encoding="utf-8"))
    phases = {str(item["phase_id"]): item for item in data["phases"]}
    complete = {
        phase_id
        for phase_id, item in phases.items()
        if item.get("status") == "historical_complete"
    }
    in_progress = [
        phase_id for phase_id in order if phases[phase_id].get("status") == "in_progress"
    ]
    ready = []
    for phase_id in order:
        item = phases[phase_id]
        if item.get("status") != "planned":
            continue
        dependencies = set(item.get("depends_on") or [])
        if dependencies <= complete:
            ready.append(phase_id)

    print("DEPENDENCY_STATUS_ONLY_NO_EXECUTION_AUTHORIZATION")
    print("IN_PROGRESS=" + (", ".join(in_progress) if in_progress else "none"))
    print("DEPENDENCY_READY_PLANNED=" + (", ".join(ready) if ready else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
