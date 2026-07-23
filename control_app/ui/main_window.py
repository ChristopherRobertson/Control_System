"""Qt main window shell for the unified instrument interface."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from control_app.ui.contracts import WorkflowCommandHandler, blocked_handler
from control_app.ui.widgets.mircat_widget import MircatWidget
from control_app.ui.widgets.ndyag_widget import NdYagWidget
from control_app.ui.widgets.scan_plotter_widget import ScanPlotterWidget
from control_app.ui.widgets.t660_widget import T660Widget
from control_app.ui.widgets.experiment_builder_widget import ExperimentBuilderWidget
from control_app.ui.widgets.workflow_selector_widget import WorkflowSelectorWidget


try:
    from PySide6.QtWidgets import QMessageBox, QMainWindow, QTabWidget

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - import-safe in non-UI environments
    PYSIDE6_AVAILABLE = False
    QMessageBox = object
    QMainWindow = object
    QTabWidget = object


class ControlSystemMainWindow(QMainWindow):
    """Main desktop shell composed from independent device widgets."""

    def __init__(
        self,
        command_handler: WorkflowCommandHandler | None = None,
    ) -> None:
        if not PYSIDE6_AVAILABLE:
            raise RuntimeError("PySide6 is required to instantiate ControlSystemMainWindow")
        super().__init__()
        self.setWindowTitle("IR Spectroscope Control System")
        handler = command_handler or blocked_handler("No workflow command handler is attached.")
        self.command_handler: Any = handler
        self.safe_shutdown_completed = False
        self.safe_shutdown_completed_callback: Callable[[], None] | None = None

        tabs = QTabWidget()
        self.experiment_builder_widget = ExperimentBuilderWidget()
        tabs.addTab(self.experiment_builder_widget, "Experiment Builder")
        self.workflow_selector_widget = WorkflowSelectorWidget(handler)
        tabs.addTab(self.workflow_selector_widget, "Legacy Workflows")
        self.mircat_widget = MircatWidget(handler)
        tabs.addTab(self.mircat_widget, "MIRcat")
        self.t660_widget = T660Widget(handler)
        tabs.addTab(self.t660_widget, "T660-2")
        self.ndyag_widget = NdYagWidget(handler)
        tabs.addTab(self.ndyag_widget, "Nd:YAG")
        self.scan_plotter_widget = ScanPlotterWidget()
        tabs.addTab(self.scan_plotter_widget, "Plotter")
        self.mircat_widget.scan_data_ready_callback = self.scan_plotter_widget.set_rows
        self.workflow_selector_widget.scan_data_ready_callback = self.scan_plotter_widget.set_rows
        self.setCentralWidget(tabs)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override name
        """Run safe shutdown before allowing application close."""

        try:
            blockers = self._close_blockers()
        except Exception as exc:  # noqa: BLE001 - Qt close handlers must not leak exceptions
            self._show_close_error(
                "Close Check Failed",
                "The application could not verify whether hardware commands are still running.\n\n"
                f"{type(exc).__name__}: {exc}\n\n"
                "The application will remain open. Stop active workflows manually, then try closing "
                "again.",
            )
            event.ignore()
            return
        if blockers:
            self._show_close_error(
                "Close Blocked",
                "The application cannot close yet.\n\n"
                + "\n".join(f"- {blocker}" for blocker in blockers),
            )
            event.ignore()
            return

        shutdown = getattr(self.command_handler, "ui_safe_shutdown", None)
        if callable(shutdown):
            try:
                result = shutdown(reason="main_window_close")
            except Exception as exc:  # noqa: BLE001 - show operator instructions instead of crashing
                self._show_close_error(
                    "Safe Shutdown Failed",
                    "Safe shutdown raised an unexpected error, so the application will remain open.\n\n"
                    f"{type(exc).__name__}: {exc}\n\n"
                    "Use Safe Idle on the T660/Nd:YAG tabs and Emission Off, Disarm, "
                    "or Deinitialize on the MIRcat tab before trying to close again.",
                )
                event.ignore()
                return
            status = getattr(result, "status", None)
            message = str(getattr(result, "message", result))
            if status != "complete":
                instructions = (
                    "Safe shutdown did not complete, so the application will remain open.\n\n"
                    f"{message}\n\n"
                    "Use Safe Idle on the T660/Nd:YAG tabs and Emission Off, Disarm, "
                    "or Deinitialize on the MIRcat tab. If the UI cannot control hardware, "
                    "physically stop/disable the instruments before exiting."
                )
                self._show_close_error("Safe Shutdown Failed", instructions)
                event.ignore()
                return

        self.safe_shutdown_completed = True
        if self.safe_shutdown_completed_callback is not None:
            self.safe_shutdown_completed_callback()
        event.accept()

    def _close_blockers(self) -> list[str]:
        blockers: list[str] = []
        candidates = (
            ("Experiment Builder", getattr(self, "experiment_builder_widget", None)),
            ("Workflow", getattr(self, "workflow_selector_widget", None)),
            ("MIRcat", self.mircat_widget),
            ("T660-2", self.t660_widget),
            ("Nd:YAG", self.ndyag_widget),
        )
        for label, widget in candidates:
            if widget is None:
                continue
            if widget.command_running():
                blockers.append(
                    f"{label} command is still running. Wait for it to finish, or use "
                    "the relevant Stop, Emission Off, Safe Idle, or Deinitialize control, "
                    "then close the app."
                )

        handler_blockers = getattr(self.command_handler, "ui_close_blockers", None)
        if callable(handler_blockers):
            blockers.extend(str(blocker) for blocker in handler_blockers())
        return blockers

    def _show_close_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)
