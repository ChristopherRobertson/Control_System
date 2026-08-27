"""Versioned data model for declarative experiment definitions.

Definitions are data only.  Unknown keys are rejected and no field can contain
Python, shell, SDK calls, or arbitrary routing instructions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal
import json

import yaml


SCHEMA_VERSION = "1.0"
FieldKind = Literal["float", "integer", "boolean", "choice", "text", "list"]


class ExperimentSchemaError(ValueError):
    """Raised when an experiment document is not valid data for this schema."""


@dataclass(frozen=True)
class Condition:
    field: str
    equals: Any

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Condition":
        _reject_unknown(value, {"field", "equals"}, "condition")
        return cls(field=_required_text(value, "field"), equals=value.get("equals"))


@dataclass(frozen=True)
class FieldDefinition:
    key: str
    label: str
    kind: FieldKind
    default: Any = None
    units: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[Any, ...] = ()
    required: bool = True
    user_adjustable: bool = True
    help_text: str = ""
    visible_when: Condition | None = None
    enabled_when: Condition | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "FieldDefinition":
        allowed = {
            "key", "label", "type", "default", "units", "minimum", "maximum",
            "choices", "required", "user_adjustable", "help_text", "visible_when",
            "enabled_when",
        }
        _reject_unknown(value, allowed, "field definition")
        kind = value.get("type")
        if kind not in ("float", "integer", "boolean", "choice", "text", "list"):
            raise ExperimentSchemaError(f"Unsupported field type {kind!r}")
        choices = value.get("choices", ())
        if not isinstance(choices, (list, tuple)):
            raise ExperimentSchemaError("field choices must be a list")
        return cls(
            key=_required_text(value, "key"), label=_required_text(value, "label"), kind=kind,
            default=value.get("default"), units=_optional_text(value.get("units")),
            minimum=_optional_number(value.get("minimum")), maximum=_optional_number(value.get("maximum")),
            choices=tuple(choices), required=_bool(value.get("required", True), "required"),
            user_adjustable=_bool(value.get("user_adjustable", True), "user_adjustable"),
            help_text=str(value.get("help_text", "")),
            visible_when=_condition(value.get("visible_when")),
            enabled_when=_condition(value.get("enabled_when")),
        )


@dataclass(frozen=True)
class DeviceConfiguration:
    device: str
    capabilities: dict[str, Any]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DeviceConfiguration":
        _reject_unknown(value, {"device", "capabilities"}, "device configuration")
        capabilities = value.get("capabilities")
        if not isinstance(capabilities, dict):
            raise ExperimentSchemaError("device capabilities must be a mapping")
        return cls(device=_required_text(value, "device"), capabilities=dict(capabilities))


@dataclass(frozen=True)
class Behavior:
    actions: tuple[str, ...]

    @classmethod
    def from_value(cls, value: Any, label: str) -> "Behavior":
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
            raise ExperimentSchemaError(f"{label}.actions must be a non-empty string list")
        return cls(tuple(value))


@dataclass(frozen=True)
class ExperimentDefinition:
    schema_version: str
    experiment_id: str
    name: str
    description: str
    experiment_type: str
    required_devices: tuple[str, ...]
    resource_ownership: dict[str, str]
    fields: tuple[FieldDefinition, ...]
    values: dict[str, Any]
    devices: tuple[DeviceConfiguration, ...]
    acquisition: dict[str, Any]
    processing: dict[str, Any]
    export: dict[str, Any]
    safety_prerequisites: tuple[str, ...]
    stop: Behavior
    abort_to_safe: Behavior
    failure_cleanup: Behavior
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ExperimentDefinition":
        allowed = {
            "schema_version", "experiment_id", "name", "description", "experiment_type",
            "required_devices", "resource_ownership", "fields", "values", "devices",
            "acquisition", "processing", "export", "safety_prerequisites", "stop",
            "abort_to_safe", "failure_cleanup", "metadata",
        }
        _reject_unknown(value, allowed, "experiment definition")
        if value.get("schema_version") != SCHEMA_VERSION:
            raise ExperimentSchemaError(
                f"Unsupported schema_version {value.get('schema_version')!r}; expected {SCHEMA_VERSION!r}"
            )
        fields = _mapping_list(value.get("fields"), "fields", FieldDefinition.from_dict)
        devices = _mapping_list(value.get("devices"), "devices", DeviceConfiguration.from_dict)
        required = _string_list(value.get("required_devices"), "required_devices")
        prerequisites = _string_list(value.get("safety_prerequisites"), "safety_prerequisites")
        ownership = _mapping(value.get("resource_ownership"), "resource_ownership")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in ownership.items()):
            raise ExperimentSchemaError("resource_ownership keys and values must be text")
        return cls(
            schema_version=SCHEMA_VERSION, experiment_id=_required_text(value, "experiment_id"),
            name=_required_text(value, "name"), description=str(value.get("description", "")),
            experiment_type=_required_text(value, "experiment_type"), required_devices=required,
            resource_ownership=dict(ownership), fields=fields, values=_mapping(value.get("values"), "values"),
            devices=devices, acquisition=_mapping(value.get("acquisition"), "acquisition"),
            processing=_mapping(value.get("processing"), "processing"),
            export=_mapping(value.get("export"), "export"), safety_prerequisites=prerequisites,
            stop=Behavior.from_value(_behavior_actions(value.get("stop"), "stop"), "stop"),
            abort_to_safe=Behavior.from_value(_behavior_actions(value.get("abort_to_safe"), "abort_to_safe"), "abort_to_safe"),
            failure_cleanup=Behavior.from_value(_behavior_actions(value.get("failure_cleanup"), "failure_cleanup"), "failure_cleanup"),
            metadata=_mapping(value.get("metadata", {}), "metadata"),
        )

    @classmethod
    def load(cls, path: str | Path) -> "ExperimentDefinition":
        source = Path(path)
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ExperimentSchemaError("experiment document must be a mapping")
        return cls.from_dict(raw)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for item in result["fields"]:
            item["type"] = item.pop("kind")
        return result

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = self.to_dict()
        if target.suffix.lower() == ".json":
            target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        else:
            target.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        return target


def _reject_unknown(value: Any, allowed: set[str], label: str) -> None:
    if not isinstance(value, dict):
        raise ExperimentSchemaError(f"{label} must be a mapping")
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ExperimentSchemaError(f"Unknown {label} key(s): {', '.join(unknown)}")


def _required_text(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise ExperimentSchemaError(f"{key} must be non-empty text")
    return result.strip()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ExperimentSchemaError("units must be text")
    return value


def _optional_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExperimentSchemaError("minimum/maximum must be numeric")
    return float(value)


def _bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ExperimentSchemaError(f"{label} must be Boolean")
    return value


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExperimentSchemaError(f"{label} must be a mapping")
    return dict(value)


def _string_list(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ExperimentSchemaError(f"{label} must be a string list")
    return tuple(value)


def _mapping_list(value: Any, label: str, factory: Any) -> tuple[Any, ...]:
    if not isinstance(value, list):
        raise ExperimentSchemaError(f"{label} must be a list")
    return tuple(factory(item) for item in value)


def _condition(value: Any) -> Condition | None:
    return None if value is None else Condition.from_dict(value)


def _behavior_actions(value: Any, label: str) -> Any:
    _reject_unknown(value, {"actions"}, label)
    return value.get("actions")
