#!/usr/bin/env python3
"""Validate application close handling does not leak shutdown exceptions through Qt."""

from __future__ import annotations

import _common  # noqa: F401 - adds repository root to sys.path

from control_app.ui.contracts import WorkflowResult
from control_app.ui.main_window import ControlSystemMainWindow


def main() -> int:
    window = _window(_FailingShutdownHandler())
    event = _FakeCloseEvent()
    ControlSystemMainWindow.closeEvent(window, event)
    assert event.ignored is True
    assert event.accepted is False
    assert window.close_errors
    assert window.close_errors[-1][0] == "Safe Shutdown Failed"

    completed = {"value": False}
    window = _window(_CompleteShutdownHandler())
    window.safe_shutdown_completed_callback = lambda: completed.__setitem__("value", True)
    event = _FakeCloseEvent()
    ControlSystemMainWindow.closeEvent(window, event)
    assert event.accepted is True
    assert event.ignored is False
    assert window.safe_shutdown_completed is True
    assert completed["value"] is True

    window = _window(_BlockedShutdownHandler())
    event = _FakeCloseEvent()
    ControlSystemMainWindow.closeEvent(window, event)
    assert event.ignored is True
    assert window.close_errors[-1][0] == "Safe Shutdown Failed"

    print("PASS UI close shutdown behavior is exception-safe")
    return 0


def _window(handler) -> ControlSystemMainWindow:
    window = ControlSystemMainWindow.__new__(ControlSystemMainWindow)
    window.command_handler = handler
    window.safe_shutdown_completed = False
    window.safe_shutdown_completed_callback = None
    window.mircat_widget = _FakeWidget(False)
    window.t660_widget = _FakeWidget(False)
    window.ndyag_widget = _FakeWidget(False)
    window.close_errors = []
    window._show_close_error = lambda title, message: window.close_errors.append((title, message))
    return window


class _FakeCloseEvent:
    def __init__(self) -> None:
        self.accepted = False
        self.ignored = False

    def accept(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True


class _FakeWidget:
    def __init__(self, running: bool) -> None:
        self.running = running

    def command_running(self) -> bool:
        return self.running


class _FailingShutdownHandler:
    def ui_close_blockers(self) -> list[str]:
        return []

    def ui_safe_shutdown(self, *, reason: str) -> WorkflowResult:
        raise RuntimeError(f"shutdown failed for {reason}")


class _CompleteShutdownHandler:
    def ui_close_blockers(self) -> list[str]:
        return []

    def ui_safe_shutdown(self, *, reason: str) -> WorkflowResult:
        return WorkflowResult(status="complete", message=f"closed: {reason}")


class _BlockedShutdownHandler:
    def ui_close_blockers(self) -> list[str]:
        return []

    def ui_safe_shutdown(self, *, reason: str) -> WorkflowResult:
        return WorkflowResult(status="failed", message=f"not closed: {reason}")


if __name__ == "__main__":
    raise SystemExit(main())
