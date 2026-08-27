"""Validate the unified phase DAG and non-destructive evidence mappings."""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "campaigns/registry/phase_registry.yaml"
EVIDENCE = ROOT / "campaigns/registry/evidence_locations.yaml"


class RegistryError(RuntimeError):
    pass


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise RegistryError(f"expected a mapping: {path}")
    return data


def validate() -> list[str]:
    registry = load_yaml(REGISTRY)
    evidence = load_yaml(EVIDENCE)
    phases = registry.get("phases")
    if not isinstance(phases, list) or not phases:
        raise RegistryError("phase registry has no phases")
    titles = registry.get("titles") or {}
    if not isinstance(titles, dict):
        raise RegistryError("phase registry titles must be a mapping")

    by_id: dict[str, dict] = {}
    for phase in phases:
        if not isinstance(phase, dict) or not phase.get("phase_id"):
            raise RegistryError(f"invalid phase row: {phase!r}")
        phase_id = str(phase["phase_id"])
        if phase_id in by_id:
            raise RegistryError(f"duplicate phase_id: {phase_id}")
        if not str(titles.get(phase_id, "")).strip():
            raise RegistryError(f"missing title for phase_id: {phase_id}")
        by_id[phase_id] = phase
        plan = ROOT / str(phase.get("plan", ""))
        if not plan.is_file():
            raise RegistryError(f"missing plan for {phase_id}: {plan}")

    incoming = {phase_id: 0 for phase_id in by_id}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for phase_id, phase in by_id.items():
        for dependency in phase.get("depends_on") or []:
            if dependency not in by_id:
                raise RegistryError(f"{phase_id} has unknown dependency {dependency}")
            incoming[phase_id] += 1
            outgoing[str(dependency)].append(phase_id)
        for dependency in phase.get("optional_dependencies") or []:
            if dependency not in by_id:
                raise RegistryError(
                    f"{phase_id} has unknown optional dependency {dependency}"
                )

    queue = deque(sorted(key for key, count in incoming.items() if count == 0))
    order: list[str] = []
    while queue:
        current = queue.popleft()
        order.append(current)
        for child in sorted(outgoing[current]):
            incoming[child] -= 1
            if incoming[child] == 0:
                queue.append(child)
    if len(order) != len(by_id):
        cyclic = sorted(key for key, count in incoming.items() if count)
        raise RegistryError(f"hard-dependency cycle: {cyclic}")

    locations = evidence.get("locations") or {}
    for phase_id, phase in by_id.items():
        if phase.get("status") not in {"historical_complete", "in_progress"}:
            continue
        key = str(phase.get("evidence_key") or phase_id)
        item = locations.get(key)
        if not isinstance(item, dict) or not item.get("path"):
            raise RegistryError(f"{phase_id} lacks an evidence-location mapping")
        path = ROOT / str(item["path"])
        if not path.exists():
            raise RegistryError(f"mapped evidence path is missing for {phase_id}: {path}")

    required_edges = {
        "HF-01.1": {"HF-01"},
        "AR-01": {"HF-01.1"},
        "PF-00": {"AR-01"},
        "SV-02A": {"PF-00"},
        "SV-02B": {"SV-02A"},
        "QB-01M": {"R9"},
        "MB-01": {"R9"},
    }
    for phase_id, required in required_edges.items():
        actual = set(by_id[phase_id].get("depends_on") or [])
        missing = required - actual
        if missing:
            raise RegistryError(f"{phase_id} is missing required dependencies {missing}")
    if by_id["QB-01M"].get("status") != "optional":
        raise RegistryError("QB-01M must remain optional")

    return order


def main() -> int:
    order = validate()
    print(f"PHASE_REGISTRY_PASS phases={len(order)}")
    print("TOPOLOGICAL_ORDER=" + " -> ".join(order))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
