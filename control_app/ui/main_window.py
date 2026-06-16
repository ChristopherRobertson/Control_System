"""Qt main window shell for the unified instrument interface."""

from __future__ import annotations

from control_app.ui.contracts import WorkflowCommandHandler, blocked_handler
from control_app.ui.widgets.mircat_widget import MircatWidget


try:
    from PySide6.QtWidgets import QMainWindow, QTabWidget

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - import-safe in non-UI environments
    PYSIDE6_AVAILABLE = False
    QMainWindow = object
    QTabWidget = object


class ControlSystemMainWindow(QMainWindow):
    """Main desktop shell composed from independent device widgets."""

    def __init__(self, command_handler: WorkflowCommandHandler | None = None) -> None:
        if not PYSIDE6_AVAILABLE:
            raise RuntimeError("PySide6 is required to instantiate ControlSystemMainWindow")
        super().__init__()
        self.setWindowTitle("IR Spectroscope Control System")
        handler = command_handler or blocked_handler("No workflow command handler is attached.")

        tabs = QTabWidget()
        self.mircat_widget = MircatWidget(handler)
        tabs.addTab(self.mircat_widget, "MIRcat")
        self.setCentralWidget(tabs)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override name
        """Prevent application shutdown while hardware commands are still active."""

        if self.mircat_widget.command_running():
            self.mircat_widget.closeEvent(event)
            return
        super().closeEvent(event)
