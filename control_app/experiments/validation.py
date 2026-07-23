"""Field-level and cross-device experiment constraints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capabilities import CapabilityRegistry, PROHIBITED_ROUTES, default_capability_registry
from .models import ExperimentDefinition, FieldDefinition


@dataclass(frozen=True)
class ConstraintViolation:
    path: str
    message: str
    code: str


def validate_experiment(
    definition: ExperimentDefinition,
    registry: CapabilityRegistry | None = None,
) -> tuple[ConstraintViolation, ...]:
    registry = registry or default_capability_registry()
    errors: list[ConstraintViolation] = []
    schemas = {item.key: item for item in definition.fields}
    if len(schemas) != len(definition.fields):
        errors.append(_error("fields", "Field keys must be unique", "duplicate_field"))
    unknown_values = sorted(set(definition.values) - set(schemas))
    for key in unknown_values:
        errors.append(_error(f"values.{key}", "No field schema exists for this value", "unknown_field"))
    for key, schema in schemas.items():
        value = definition.values.get(key, schema.default)
        errors.extend(_validate_field(schema, value))

    configured = {item.device: item for item in definition.devices}
    for device in definition.required_devices:
        if device not in registry.devices():
            errors.append(_error("required_devices", f"Unknown device {device!r}", "unknown_device"))
        if device not in configured:
            errors.append(_error("devices", f"Required device {device!r} has no configuration", "missing_device"))
        if device not in definition.resource_ownership:
            errors.append(_error("resource_ownership", f"Required device {device!r} has no owner", "missing_owner"))
    for device, config in configured.items():
        if device not in definition.required_devices:
            errors.append(_error(f"devices.{device}", "Configured device is not declared required", "undeclared_device"))
        for name, value in config.capabilities.items():
            capability = registry.get(device, name)
            path = f"devices.{device}.{name}"
            if capability is None:
                errors.append(_error(path, "Capability is not allow-listed", "unknown_capability"))
                continue
            if not capability.available and _is_enabled(value):
                errors.append(_error(path, capability.reason or "Capability is unavailable", "unavailable_capability"))
            errors.extend(_validate_limits(path, value, capability.limits or {}))

    errors.extend(_cross_device_constraints(definition, configured))
    for label, behavior in (("stop", definition.stop), ("abort_to_safe", definition.abort_to_safe), ("failure_cleanup", definition.failure_cleanup)):
        for action in behavior.actions:
            if not _action_is_available(action, registry):
                errors.append(_error(f"{label}.actions", f"Unknown or unavailable action {action!r}", "unsafe_action"))
    return tuple(errors)


def require_valid(definition: ExperimentDefinition, registry: CapabilityRegistry | None = None) -> None:
    errors = validate_experiment(definition, registry)
    if errors:
        raise ValueError("; ".join(f"{item.path}: {item.message}" for item in errors))


def _validate_field(schema: FieldDefinition, value: Any) -> list[ConstraintViolation]:
    path = f"values.{schema.key}"
    if value is None:
        return [_error(path, "A value is required", "required")] if schema.required else []
    valid = {
        "float": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool), "choice": value in schema.choices,
        "text": isinstance(value, str), "list": isinstance(value, list),
    }[schema.kind]
    errors = [] if valid else [_error(path, f"Expected {schema.kind}", "type")]
    if valid and schema.kind in ("float", "integer"):
        if schema.minimum is not None and value < schema.minimum:
            errors.append(_error(path, f"Must be at least {schema.minimum}", "minimum"))
        if schema.maximum is not None and value > schema.maximum:
            errors.append(_error(path, f"Must be at most {schema.maximum}", "maximum"))
    return errors


def _validate_limits(path: str, value: Any, limits: dict[str, Any]) -> list[ConstraintViolation]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return []
    errors = []
    if "minimum" in limits and value < limits["minimum"]:
        errors.append(_error(path, f"Below device minimum {limits['minimum']}", "device_minimum"))
    if "maximum" in limits and value > limits["maximum"]:
        errors.append(_error(path, f"Above device maximum {limits['maximum']}", "device_maximum"))
    if "exclusive_minimum" in limits and value <= limits["exclusive_minimum"]:
        errors.append(_error(path, f"Must be greater than {limits['exclusive_minimum']}", "positive"))
    return errors


def _cross_device_constraints(definition: ExperimentDefinition, configured: dict[str, Any]) -> list[ConstraintViolation]:
    errors: list[ConstraintViolation] = []
    mircat = configured.get("mircat")
    if mircat:
        settings = mircat.capabilities
        rate = settings.get("pulse_rate_hz")
        width = settings.get("pulse_width_ns")
        if isinstance(rate, (int, float)) and isinstance(width, (int, float)):
            duty_cycle = float(rate) * float(width) * 1e-9
            if duty_cycle <= 0 or duty_cycle > 1:
                errors.append(_error("devices.mircat", f"Invalid duty cycle {duty_cycle:.6g}", "duty_cycle"))
        if settings.get("pulse_trigger_mode") == "external":
            master = configured.get("t660_2")
            if not master or not _is_enabled(master.capabilities.get("channel_b_mircat_trigger")):
                errors.append(_error("devices.mircat.pulse_trigger_mode", "External laser triggering requires T660-2 CHB to MIRcat TRIG IN", "trigger_route"))
        if settings.get("process_trigger_mode") == "external":
            errors.append(_error("devices.mircat.process_trigger_mode", "External Process Trigger is unavailable pending experimental confirmation", "unconfirmed_process_trigger"))
    duration = definition.acquisition.get("duration_s")
    if duration is not None and (isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0):
        errors.append(_error("acquisition.duration_s", "Acquisition duration must be positive", "positive"))
    routes = definition.metadata.get("routes", [])
    if isinstance(routes, list):
        for route in routes:
            if route in PROHIBITED_ROUTES:
                errors.append(_error("metadata.routes", f"Route {route!r} must not be driven", "prohibited_route"))
    return errors


def _action_is_available(action: str, registry: CapabilityRegistry) -> bool:
    parts = action.split(".", 1)
    if len(parts) != 2:
        return False
    capability = registry.get(parts[0], parts[1])
    return capability is not None and capability.available


def _is_enabled(value: Any) -> bool:
    return value not in (None, False, "off", "disabled", "internal")


def _error(path: str, message: str, code: str) -> ConstraintViolation:
    return ConstraintViolation(path, message, code)
