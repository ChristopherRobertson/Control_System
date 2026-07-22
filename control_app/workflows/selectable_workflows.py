"""Validated catalog and configure-before-run plans for the workflow UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from control_app.config_loader import REPO_ROOT


CATALOG_PATH = REPO_ROOT / "recipes" / "ui_workflows.yaml"


class SelectableWorkflowError(ValueError):
    pass


@dataclass(frozen=True)
class ConfiguredWorkflow:
    workflow_id: str
    device_key: str
    command: str
    stop_command: str | None
    parameters: dict[str, Any]
    safety_approval_required: bool
    fingerprint: str
    saved_path: Path


def load_workflow_catalog(path: str | Path = CATALOG_PATH) -> dict[str, dict[str, Any]]:
    source = Path(path)
    payload = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    workflows = payload.get("workflows")
    if not isinstance(workflows, dict) or not workflows:
        raise SelectableWorkflowError(f"No workflows are defined in {source}")
    validated: dict[str, dict[str, Any]] = {}
    for workflow_id, definition in workflows.items():
        if not isinstance(definition, dict):
            raise SelectableWorkflowError(f"Workflow {workflow_id!r} must be a mapping")
        for required in ("label", "device_key", "command", "parameters"):
            if required not in definition:
                raise SelectableWorkflowError(f"Workflow {workflow_id!r} is missing {required}")
        validated[str(workflow_id)] = definition
    return validated


def public_workflow_catalog(path: str | Path = CATALOG_PATH) -> list[dict[str, Any]]:
    return [
        {"id": workflow_id, **definition}
        for workflow_id, definition in load_workflow_catalog(path).items()
    ]


def validate_workflow_parameters(definition: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    schemas = definition.get("parameters") or {}
    unknown = sorted(set(values) - set(schemas))
    if unknown:
        raise SelectableWorkflowError("Unknown workflow parameter(s): " + ", ".join(unknown))
    result: dict[str, Any] = {}
    for key, schema in schemas.items():
        if not isinstance(schema, dict):
            raise SelectableWorkflowError(f"Parameter schema {key!r} must be a mapping")
        raw = values.get(key, schema.get("default"))
        kind = str(schema.get("type", "text"))
        try:
            if kind == "bool":
                value = bool(raw)
            elif kind == "int":
                value = int(raw)
            elif kind == "float":
                value = float(raw)
            else:
                value = str(raw)
        except (TypeError, ValueError) as exc:
            raise SelectableWorkflowError(f"Invalid value for {key}: {raw!r}") from exc
        if kind in {"int", "float"}:
            if schema.get("minimum") is not None and value < schema["minimum"]:
                raise SelectableWorkflowError(f"{key} is below its minimum {schema['minimum']}")
            if schema.get("maximum") is not None and value > schema["maximum"]:
                raise SelectableWorkflowError(f"{key} is above its maximum {schema['maximum']}")
        result[str(key)] = value
    return result


def workflow_fingerprint(workflow_id: str, parameters: dict[str, Any]) -> str:
    encoded = json.dumps(
        {"workflow_id": workflow_id, "parameters": parameters},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def configure_workflow(
    workflow_id: str,
    parameters: dict[str, Any],
    *,
    output_dir: str | Path,
    catalog_path: str | Path = CATALOG_PATH,
) -> ConfiguredWorkflow:
    catalog = load_workflow_catalog(catalog_path)
    if workflow_id not in catalog:
        raise SelectableWorkflowError(f"Unknown or non-viable workflow {workflow_id!r}")
    definition = catalog[workflow_id]
    validated = validate_workflow_parameters(definition, parameters)
    fingerprint = workflow_fingerprint(workflow_id, validated)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "configured_workflow.json"
    snapshot = {
        "configured_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "workflow_id": workflow_id,
        "label": definition["label"],
        "device_key": definition["device_key"],
        "command": definition["command"],
        "stop_command": definition.get("stop_command"),
        "timing_recipe": definition.get("timing_recipe"),
        "fixed_settings": definition.get("fixed_settings", {}),
        "parameters": validated,
        "safety_approval_required": bool(definition.get("safety_approval_required", False)),
        "fingerprint": fingerprint,
    }
    target.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ConfiguredWorkflow(
        workflow_id=workflow_id,
        device_key=str(definition["device_key"]),
        command=str(definition["command"]),
        stop_command=(str(definition["stop_command"]) if definition.get("stop_command") else None),
        parameters=validated,
        safety_approval_required=bool(definition.get("safety_approval_required", False)),
        fingerprint=fingerprint,
        saved_path=target,
    )
