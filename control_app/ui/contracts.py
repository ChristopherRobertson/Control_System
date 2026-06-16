"""Framework-neutral UI contracts for device widgets and workflow commands."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Literal, Protocol


ParameterKind = Literal["float", "int", "bool", "choice", "text"]
ControlKind = Literal["command", "danger", "guarded"]
CommandStatus = Literal["accepted", "blocked", "failed", "complete"]


@dataclass(frozen=True)
class ParameterField:
    """User-editable parameter surfaced by a device widget."""

    key: str
    label: str
    kind: ParameterKind
    default: Any
    units: str | None = None
    choices: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable field definition."""

        return asdict(self)


@dataclass(frozen=True)
class StatusField:
    """Status value surfaced by a device widget."""

    key: str
    label: str
    units: str | None = None
    critical: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable field definition."""

        return asdict(self)


@dataclass(frozen=True)
class WidgetControl:
    """A control button that dispatches a named workflow command."""

    key: str
    label: str
    command: str
    kind: ControlKind = "command"
    safety_approval_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable control definition."""

        return asdict(self)


@dataclass(frozen=True)
class DeviceWidgetSpec:
    """Stable description of a widget that can be folded into the full UI."""

    device_key: str
    title: str
    status_fields: tuple[StatusField, ...]
    parameter_fields: tuple[ParameterField, ...]
    controls: tuple[WidgetControl, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable widget definition."""

        return asdict(self)


@dataclass(frozen=True)
class WorkflowCommand:
    """Command emitted by UI widgets and handled by workflow routines."""

    device_key: str
    command: str
    parameters: dict[str, Any] = field(default_factory=dict)
    safety_approval: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable command dictionary."""

        return asdict(self)


@dataclass(frozen=True)
class WorkflowResult:
    """Workflow command result returned to a widget."""

    status: CommandStatus
    message: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable result dictionary."""

        return asdict(self)


class WorkflowCommandHandler(Protocol):
    """Callable protocol for UI-to-workflow command dispatch."""

    def __call__(self, command: WorkflowCommand) -> WorkflowResult:
        """Handle a workflow command."""


def blocked_handler(message: str) -> Callable[[WorkflowCommand], WorkflowResult]:
    """Return a command handler that blocks all commands with a fixed message."""

    def _handler(command: WorkflowCommand) -> WorkflowResult:
        return WorkflowResult(
            status="blocked",
            message=message,
            data={"command": command.to_dict()},
        )

    return _handler
