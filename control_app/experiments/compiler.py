"""Compile validated definitions into immutable execution plans."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
import json

from .capabilities import CapabilityRegistry, default_capability_registry
from .models import ExperimentDefinition
from .validation import require_valid


@dataclass(frozen=True)
class PlanStep:
    phase: str
    device: str
    capability: str
    value: Any


@dataclass(frozen=True)
class ExecutionPlan:
    plan_version: str
    experiment_id: str
    compiled_at_utc: str
    resource_ownership: Mapping[str, str]
    steps: tuple[PlanStep, ...]
    acquisition: Mapping[str, Any]
    processing: Mapping[str, Any]
    export: Mapping[str, Any]
    safety_prerequisites: tuple[str, ...]
    stop_actions: tuple[str, ...]
    abort_actions: tuple[str, ...]
    failure_cleanup_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_version": self.plan_version, "experiment_id": self.experiment_id,
            "compiled_at_utc": self.compiled_at_utc,
            "resource_ownership": dict(self.resource_ownership),
            "steps": [asdict(step) for step in self.steps], "acquisition": dict(self.acquisition),
            "processing": dict(self.processing), "export": dict(self.export),
            "safety_prerequisites": list(self.safety_prerequisites), "stop_actions": list(self.stop_actions),
            "abort_actions": list(self.abort_actions), "failure_cleanup_actions": list(self.failure_cleanup_actions),
        }

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target


def compile_experiment(definition: ExperimentDefinition, registry: CapabilityRegistry | None = None) -> ExecutionPlan:
    registry = registry or default_capability_registry()
    require_valid(definition, registry)
    steps: list[PlanStep] = []
    for configuration in definition.devices:
        for name, value in configuration.capabilities.items():
            capability = registry.require(configuration.device, name)
            steps.append(PlanStep(capability.phase, configuration.device, name, value))
    order = {name: index for index, name in enumerate(("configure", "verify", "arm", "run", "acquire"))}
    steps.sort(key=lambda item: order.get(item.phase, 99))
    return ExecutionPlan(
        "1.0", definition.experiment_id, datetime.now(UTC).isoformat(timespec="seconds"),
        MappingProxyType(dict(definition.resource_ownership)), tuple(steps),
        MappingProxyType(dict(definition.acquisition)), MappingProxyType(dict(definition.processing)),
        MappingProxyType(dict(definition.export)), definition.safety_prerequisites,
        definition.stop.actions, definition.abort_to_safe.actions, definition.failure_cleanup.actions,
    )
