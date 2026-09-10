"""Version 1 of the repository measurement-module boundary.

This module intentionally imports neither Qt nor device SDKs. A descriptor is
declarative; only its factory constructs widgets, on the application's Qt thread.
"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, Callable, Mapping, Protocol, Sequence

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget
    from .context import MeasurementContext
    from .interchange import InstrumentStateChange

API_VERSION = 1
MODES = ("single", "dual")
_EXPERIMENT_ID = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


class ContractError(ValueError):
    """A module does not implement the supported boundary."""


def validate_experiment_id(value: str) -> str:
    if not isinstance(value, str) or not _EXPERIMENT_ID.fullmatch(value):
        raise ContractError(f"Invalid experiment_id {value!r}; use stable lowercase snake_case")
    return value


def validate_instance_id(value: str) -> str:
    if not isinstance(value, str) or ":" not in value:
        raise ContractError(f"Invalid instance_id {value!r}; expected <experiment_id>:<single|dual>")
    experiment_id, mode = value.rsplit(":", 1)
    validate_experiment_id(experiment_id)
    if mode not in MODES:
        raise ContractError(f"Unsupported detector mode: {mode!r}")
    return value


def _validate_callable(callback: Any, name: str, *args: Any) -> None:
    if not callable(callback):
        raise ContractError(f"{name} must be callable")
    try:
        signature = inspect.signature(callback)
    except (ValueError, TypeError):
        # Some Qt/C extension callables have no Python signature. Invocation
        # still uses the documented boundary; their connectability is checked.
        return
    try:
        signature.bind(*args)
    except TypeError as exc:
        raise ContractError(f"{name} has an incompatible signature: {exc}") from exc


class StateNotification(Protocol):
    """A Qt signal (normally Signal(bool)) whose emission updates app state."""

    def connect(self, callback: Callable[..., None]) -> Any: ...


class DeviceFactory(Protocol):
    """Construct one fresh device using the operation's detached configuration.

    Simulation factories have the same signature and never fall back to real
    hardware. kwargs contain only explicit operation-selected constructor inputs.
    """

    def __call__(self, *, configuration: Mapping[str, Any], **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class TabHandle:
    """One independently owned top-level measurement tab.

    Lifecycle callables run on the UI thread and must not block. Abort requests
    signal cancellation; they do not claim that restoration or saving finished.
    State changes must be emitted through a Qt signal for queued cross-thread
    delivery. The widget itself owns runner, baseline, review and cancellation.
    """

    instance_id: str
    title: str
    widget: QWidget
    command_running: Callable[[], bool]
    close_blockers: Callable[[], Sequence[str]]
    request_abort: Callable[[str], None]
    output_location_changed: Callable[[Path], None]
    instrument_state_changed: Callable[[InstrumentStateChange], None]
    state_changed: StateNotification


@dataclass(frozen=True)
class ModuleDescriptor:
    """Export exactly one DESCRIPTOR from <experiment_id>/registration.py."""

    api_version: int
    experiment_id: str
    display_order: int
    create_tabs: Callable[[MeasurementContext], Sequence[TabHandle]]


def validate_descriptor(descriptor: Any, *, directory_id: str | None = None) -> ModuleDescriptor:
    if not isinstance(descriptor, ModuleDescriptor):
        raise ContractError("registration.DESCRIPTOR must be a ModuleDescriptor")
    if type(descriptor.api_version) is not int or descriptor.api_version != API_VERSION:
        raise ContractError(
            f"Incompatible module API {descriptor.api_version!r}; host supports {API_VERSION}"
        )
    validate_experiment_id(descriptor.experiment_id)
    if directory_id is not None and descriptor.experiment_id != directory_id:
        raise ContractError(
            f"Descriptor ID {descriptor.experiment_id!r} differs from directory ID {directory_id!r}"
        )
    if type(descriptor.display_order) is not int:
        raise ContractError("display_order must be an integer")
    _validate_callable(descriptor.create_tabs, "create_tabs", object())
    return descriptor


def validate_handles(descriptor: ModuleDescriptor, handles: Sequence[TabHandle]) -> tuple[TabHandle, ...]:
    """Validate the entire pair atomically before publishing either tab."""
    from PySide6.QtWidgets import QWidget

    pair = tuple(handles)
    if len(pair) != 2:
        raise ContractError(f"{descriptor.experiment_id} must create exactly two handles")
    expected = {f"{descriptor.experiment_id}:{mode}" for mode in MODES}
    if any(not isinstance(handle, TabHandle) for handle in pair):
        raise ContractError("create_tabs must return TabHandle objects")
    if {handle.instance_id for handle in pair} != expected:
        raise ContractError(f"Expected instance IDs {sorted(expected)}")
    if any(not isinstance(handle.title, str) or not handle.title.strip() for handle in pair):
        raise ContractError("Tab titles must be nonempty strings")
    if len({handle.title.casefold().strip() for handle in pair}) != 2:
        raise ContractError("Each tab must have a unique top-level title")
    if pair[0].widget is pair[1].widget:
        raise ContractError("Single and dual handles must own distinct widgets")
    for handle in pair:
        if not isinstance(handle.title, str) or not handle.title.strip():
            raise ContractError("Tab titles must be nonempty strings")
        if not isinstance(handle.widget, QWidget):
            raise ContractError(f"{handle.instance_id} widget must be a QWidget")
        for name in ("command_running", "close_blockers"):
            _validate_callable(getattr(handle, name), f"{handle.instance_id}.{name}")
        for name in ("request_abort", "output_location_changed", "instrument_state_changed"):
            _validate_callable(getattr(handle, name), f"{handle.instance_id}.{name}", object())
        if not callable(getattr(handle.state_changed, "connect", None)):
            raise ContractError(f"{handle.instance_id}.state_changed must expose signal.connect")
    return tuple(sorted(pair, key=lambda item: MODES.index(item.instance_id.rsplit(":", 1)[1])))
