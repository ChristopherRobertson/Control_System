"""Generic plan executor; orchestration never branches on device type."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .compiler import ExecutionPlan


class DeviceAdapter(Protocol):
    def execute(self, capability: str, value: Any) -> Any: ...


@dataclass
class ExecutionResult:
    status: str
    records: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


class ExperimentEngine:
    def __init__(self, adapters: dict[str, DeviceAdapter]) -> None:
        self._adapters = dict(adapters)
        self._active: ExecutionPlan | None = None

    def run(self, plan: ExecutionPlan, *, satisfied_prerequisites: set[str]) -> ExecutionResult:
        missing = sorted(set(plan.safety_prerequisites) - satisfied_prerequisites)
        if missing:
            return ExecutionResult("blocked", error="Missing safety prerequisites: " + ", ".join(missing))
        if self._active is not None:
            return ExecutionResult("blocked", error="Another experiment owns the execution engine")
        missing_adapters = sorted(set(plan.resource_ownership) - set(self._adapters))
        if missing_adapters:
            return ExecutionResult("blocked", error="Missing device adapters: " + ", ".join(missing_adapters))
        self._active = plan
        result = ExecutionResult("complete")
        try:
            for step in plan.steps:
                output = self._adapters[step.device].execute(step.capability, step.value)
                result.records.append({"phase": step.phase, "device": step.device, "capability": step.capability, "output": output})
        except Exception as exc:
            result.status = "failed"
            result.error = str(exc)
            self._execute_actions(plan.failure_cleanup_actions, result)
        finally:
            self._active = None
        return result

    def stop(self, plan: ExecutionPlan) -> ExecutionResult:
        result = ExecutionResult("stopped")
        self._execute_actions(plan.stop_actions, result)
        self._active = None
        return result

    def abort_to_safe(self, plan: ExecutionPlan) -> ExecutionResult:
        result = ExecutionResult("aborted")
        self._execute_actions(plan.abort_actions, result)
        self._active = None
        return result

    def _execute_actions(self, actions: tuple[str, ...], result: ExecutionResult) -> None:
        for action in actions:
            device, capability = action.split(".", 1)
            try:
                output = self._adapters[device].execute(capability, True)
                result.records.append({"phase": "cleanup", "device": device, "capability": capability, "output": output})
            except Exception as exc:
                result.records.append({"phase": "cleanup", "device": device, "capability": capability, "error": str(exc)})


class ServiceCapabilityAdapter:
    """Explicit allow-list mapping from capabilities to existing service callables."""

    def __init__(self, operations: dict[str, Any]) -> None:
        if not operations or not all(callable(operation) for operation in operations.values()):
            raise ValueError("adapter operations must be a non-empty callable mapping")
        self._operations = dict(operations)

    def execute(self, capability: str, value: Any) -> Any:
        operation = self._operations.get(capability)
        if operation is None:
            raise ValueError(f"Capability {capability!r} has no adapter operation")
        return operation(value)
