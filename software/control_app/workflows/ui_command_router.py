"""Workflow command router for the desktop UI."""

from __future__ import annotations

from control_app.ui.contracts import WorkflowCommand, WorkflowCommandHandler, WorkflowResult


class WorkflowCommandRouter:
    """Route widget commands to device-specific workflow handlers."""

    def __init__(self, handlers: dict[str, WorkflowCommandHandler]) -> None:
        self.handlers = dict(handlers)

    def __call__(self, command: WorkflowCommand) -> WorkflowResult:
        """Dispatch a workflow command by device key."""

        handler = self.handlers.get(command.device_key)
        if handler is None:
            return WorkflowResult(
                status="blocked",
                message=f"No workflow handler registered for {command.device_key}",
                data={"command": command.to_dict()},
            )
        return handler(command)
