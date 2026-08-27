"""Framework-neutral experiment-builder controller for desktop or CLI UIs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .capabilities import CapabilityRegistry, default_capability_registry
from .compiler import ExecutionPlan, compile_experiment
from .engine import ExecutionResult, ExperimentEngine
from .models import ExperimentDefinition
from .processing import ProcessingRegistry, default_processing_registry, export_standard_result
from .validation import ConstraintViolation, validate_experiment


class ExperimentBuilder:
    """Own the complete create-to-export lifecycle without workflow identifiers."""

    def __init__(self, *, capabilities: CapabilityRegistry | None = None, processing: ProcessingRegistry | None = None) -> None:
        self.capabilities = capabilities or default_capability_registry()
        self.processing = processing or default_processing_registry()
        self.definition: ExperimentDefinition | None = None
        self.plan: ExecutionPlan | None = None
        self.result: dict[str, Any] | None = None

    def create(self, document: dict[str, Any]) -> ExperimentDefinition:
        self.definition = ExperimentDefinition.from_dict(document)
        self.plan = None
        return self.definition

    def reload(self, path: str | Path) -> ExperimentDefinition:
        self.definition = ExperimentDefinition.load(path)
        self.plan = None
        return self.definition

    def validate(self) -> tuple[ConstraintViolation, ...]:
        return validate_experiment(self._definition(), self.capabilities)

    def save(self, path: str | Path) -> Path:
        return self._definition().save(path)

    def configure(self, plan_path: str | Path) -> ExecutionPlan:
        self.plan = compile_experiment(self._definition(), self.capabilities)
        self.plan.save(plan_path)
        return self.plan

    def run(self, engine: ExperimentEngine, *, satisfied_prerequisites: set[str]) -> ExecutionResult:
        if self.plan is None:
            raise RuntimeError("Configure and save an immutable plan before running")
        execution = engine.run(self.plan, satisfied_prerequisites=satisfied_prerequisites)
        self.result = {"status": execution.status, "records": execution.records, "error": execution.error}
        return execution

    def stop(self, engine: ExperimentEngine) -> ExecutionResult:
        return engine.stop(self._plan())

    def abort_to_safe(self, engine: ExperimentEngine) -> ExecutionResult:
        return engine.abort_to_safe(self._plan())

    def process(self, raw: dict[str, Any]) -> dict[str, Any]:
        definition = self._definition()
        method = definition.processing.get("method")
        if not isinstance(method, str):
            raise ValueError("processing.method is required")
        self.result = self.processing.process(method, raw, definition.processing)
        return self.result

    def export(self, path: str | Path) -> Path:
        if self.result is None:
            raise RuntimeError("No run or processed result is available")
        definition = self._definition()
        format_name = definition.export.get("format")
        if not isinstance(format_name, str):
            raise ValueError("export.format is required")
        return export_standard_result(self.result, definition.to_dict(), path, format_name)

    def _definition(self) -> ExperimentDefinition:
        if self.definition is None:
            raise RuntimeError("No experiment definition is loaded")
        return self.definition

    def _plan(self) -> ExecutionPlan:
        if self.plan is None:
            raise RuntimeError("No configured plan is available")
        return self.plan
