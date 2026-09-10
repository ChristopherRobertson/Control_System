"""Standalone v1 sample selections and explicit instrument-change notifications.

These records contain selections and provenance, never another feature's engine.
Sample-derived acceptance is deliberately distinct from instrument promotion.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any
from uuid import uuid4

from .context import freeze_data, thaw_data
from .contracts import ContractError, validate_instance_id

INTERCHANGE_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field_name} must be a nonempty string")


def _timestamp(value: str, field_name: str) -> None:
    _text(value, field_name)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{field_name} must be an ISO 8601 UTC timestamp") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ContractError(f"{field_name} must specify UTC")


def _version(value: Any) -> None:
    if type(value) is not int or value != INTERCHANGE_VERSION:
        raise ContractError(f"Unsupported interchange schema_version {value!r}; expected {INTERCHANGE_VERSION}")


def _number(value: Any, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ContractError(f"{field_name} must be finite numeric data")


@dataclass(frozen=True)
class SpectralWindow:
    lower_cm1: float
    upper_cm1: float
    center_cm1: float | None = None
    uncertainty_cm1: float | None = None
    label: str = ""

    def __post_init__(self):
        _number(self.lower_cm1, "lower_cm1")
        _number(self.upper_cm1, "upper_cm1")
        if self.lower_cm1 > self.upper_cm1:
            raise ContractError("Spectral window lower_cm1 cannot exceed upper_cm1")
        if self.center_cm1 is not None:
            _number(self.center_cm1, "center_cm1")
            if not self.lower_cm1 <= self.center_cm1 <= self.upper_cm1:
                raise ContractError("center_cm1 must lie inside its selected window")
        if self.uncertainty_cm1 is not None:
            _number(self.uncertainty_cm1, "uncertainty_cm1")
            if self.uncertainty_cm1 < 0:
                raise ContractError("uncertainty_cm1 cannot be negative")
        if not isinstance(self.label, str):
            raise ContractError("Window label must be a string")

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class SourceRecord:
    """A stable producer/source reference; no hash-matching acceptance gate."""

    producer_run_id: str
    native_path: str
    created_utc: str
    software_version: str

    def __post_init__(self):
        for name in ("producer_run_id", "native_path", "software_version"):
            _text(getattr(self, name), name)
        _timestamp(self.created_utc, "created_utc")

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class SampleSpectralSelection:
    """An accepted sample selection, usable without the producing module installed."""

    selection_id: str
    sample_id: str
    producer_instance_id: str
    source: SourceRecord
    condition_id: str
    condition: Mapping[str, Any]
    windows: tuple[SpectralWindow, ...]
    accepted_by: str
    accepted_utc: str
    uncertainty_description: str = "Uncertainty not supplied"
    schema_version: int = INTERCHANGE_VERSION
    record_kind: str = "sample_spectral_selection"
    disposition: str = "accepted"

    def __post_init__(self):
        object.__setattr__(self, "condition", freeze_data(self.condition))
        object.__setattr__(self, "windows", tuple(self.windows))
        validate_sample_selection(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version, "record_kind": self.record_kind,
            "disposition": self.disposition, "selection_id": self.selection_id,
            "sample_id": self.sample_id, "producer_instance_id": self.producer_instance_id,
            "source": self.source.to_dict(), "condition_id": self.condition_id,
            "condition": thaw_data(self.condition), "windows": [window.to_dict() for window in self.windows],
            "accepted_by": self.accepted_by, "accepted_utc": self.accepted_utc,
            "uncertainty_description": self.uncertainty_description,
        }


@dataclass(frozen=True)
class PromotedCalibrationReference:
    """Selection identity only. The injected promoted_bundle loader verifies promotion.

    Constructing this reference does not promote anything or establish readiness.
    It cannot be consumed by validate_sample_selection.
    """

    bundle_id: str
    calibration_id: str
    schema_version: int = INTERCHANGE_VERSION
    record_kind: str = "promoted_instrument_calibration"

    def __post_init__(self):
        _version(self.schema_version)
        _text(self.bundle_id, "bundle_id")
        _text(self.calibration_id, "calibration_id")
        if self.record_kind != "promoted_instrument_calibration":
            raise ContractError("A promoted calibration reference must retain its record kind")


def validate_sample_selection(record: Any) -> SampleSpectralSelection:
    if not isinstance(record, SampleSpectralSelection):
        raise ContractError("Expected a SampleSpectralSelection; instrument calibration is a separate record type")
    _version(record.schema_version)
    if record.record_kind != "sample_spectral_selection" or record.disposition != "accepted":
        raise ContractError("Only accepted sample_spectral_selection records are supported")
    validate_instance_id(record.producer_instance_id)
    for name in ("selection_id", "sample_id", "condition_id", "accepted_by", "uncertainty_description"):
        _text(getattr(record, name), name)
    _timestamp(record.accepted_utc, "accepted_utc")
    if not isinstance(record.source, SourceRecord):
        raise ContractError("source must be a SourceRecord")
    if not isinstance(record.condition, Mapping):
        raise ContractError("condition must be an explicit data mapping")
    if not record.windows or any(not isinstance(item, SpectralWindow) for item in record.windows):
        raise ContractError("At least one SpectralWindow is required")
    return record


def sample_selection_from_dict(data: Mapping[str, Any]) -> SampleSpectralSelection:
    """Validate untrusted standalone JSON without importing a feature package."""
    if not isinstance(data, Mapping):
        raise ContractError("Sample selection must be a mapping")
    if data.get("record_kind") != "sample_spectral_selection":
        raise ContractError("Expected sample_spectral_selection, not instrument calibration")
    _version(data.get("schema_version"))
    try:
        values = dict(data)
        values["source"] = SourceRecord(**values["source"])
        values["windows"] = tuple(SpectralWindow(**item) for item in values["windows"])
        return SampleSpectralSelection(**values)
    except (KeyError, TypeError) as exc:
        raise ContractError(f"Invalid sample selection fields: {exc}") from exc


def load_sample_selection(path: str | Path) -> SampleSpectralSelection:
    return sample_selection_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def save_sample_selection(record: SampleSpectralSelection, path: str | Path) -> Path:
    validate_sample_selection(record)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Never silently replace a prior acceptance record.
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(record.to_dict(), stream, indent=2, allow_nan=False)
        stream.write("\n")
    return destination


@dataclass(frozen=True)
class DeviceConfigurationChange:
    device_id: str
    configuration_key: str
    previous_value: Any
    new_value: Any

    def __post_init__(self):
        _text(self.device_id, "device_id")
        _text(self.configuration_key, "configuration_key")
        object.__setattr__(self, "previous_value", freeze_data(self.previous_value))
        object.__setattr__(self, "new_value", freeze_data(self.new_value))

    def to_dict(self) -> dict[str, Any]:
        return {"device_id": self.device_id, "configuration_key": self.configuration_key,
                "previous_value": thaw_data(self.previous_value), "new_value": thaw_data(self.new_value)}


@dataclass(frozen=True)
class InstrumentStateChange:
    """Advisory invalidation; recipients decide what to review, never mutate peers."""

    producer_instance_id: str
    recipients: tuple[str, ...]
    changes: tuple[DeviceConfigurationChange, ...]
    reason: str
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_utc: str = field(default_factory=_utc_now)
    schema_version: int = INTERCHANGE_VERSION

    def __post_init__(self):
        object.__setattr__(self, "recipients", tuple(self.recipients))
        object.__setattr__(self, "changes", tuple(self.changes))
        validate_instrument_state_change(self)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "event_id": self.event_id,
                "producer_instance_id": self.producer_instance_id, "recipients": list(self.recipients),
                "changes": [item.to_dict() for item in self.changes], "reason": self.reason,
                "occurred_utc": self.occurred_utc}


def validate_instrument_state_change(change: Any) -> InstrumentStateChange:
    if not isinstance(change, InstrumentStateChange):
        raise ContractError("Expected an InstrumentStateChange")
    _version(change.schema_version)
    for name in ("producer_instance_id", "event_id", "reason"):
        _text(getattr(change, name), name)
    _timestamp(change.occurred_utc, "occurred_utc")
    if not change.recipients or len(set(change.recipients)) != len(change.recipients):
        raise ContractError("Instrument changes must name distinct explicit recipients")
    for recipient in change.recipients:
        validate_instance_id(recipient)
    if not change.changes or any(not isinstance(item, DeviceConfigurationChange) for item in change.changes):
        raise ContractError("Instrument changes must identify device/configuration changes")
    return change


def instrument_state_change_from_dict(data: Mapping[str, Any]) -> InstrumentStateChange:
    if not isinstance(data, Mapping):
        raise ContractError("Instrument change must be a mapping")
    _version(data.get("schema_version"))
    try:
        values = dict(data)
        values["changes"] = tuple(DeviceConfigurationChange(**item) for item in values["changes"])
        return InstrumentStateChange(**values)
    except (KeyError, TypeError) as exc:
        raise ContractError(f"Invalid instrument change fields: {exc}") from exc
