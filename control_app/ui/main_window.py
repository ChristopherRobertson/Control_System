"""Qt main window shell for the unified instrument interface."""

from __future__ import annotations

from control_app.ui.contracts import WorkflowCommandHandler, blocked_handler
from control_app.ui.widgets.mircat_widget import MircatWidget
from control_app.ui.widgets.mux_widget import MuxWidget
from control_app.ui.widgets.t660_widget import T660Widget


try:
    from PySide6.QtWidgets import QMainWindow, QTabWidget

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - import-safe in non-UI environments
    PYSIDE6_AVAILABLE = False
    QMainWindow = object
    QTabWidget = object


class ControlSystemMainWindow(QMainWindow):
    """Main desktop shell composed from independent device widgets."""

    def __init__(
        self,
        command_handler: WorkflowCommandHandler | None = None,
        *,
        mux_route_options: dict[str, tuple[str, ...]] | None = None,
        mux_route_labels: dict[str, str] | None = None,
        mux_default_routes: dict[str, str] | None = None,
    ) -> None:
        if not PYSIDE6_AVAILABLE:
            raise RuntimeError("PySide6 is required to instantiate ControlSystemMainWindow")
        super().__init__()
        self.setWindowTitle("IR Spectroscope Control System")
        handler = command_handler or blocked_handler("No workflow command handler is attached.")

        tabs = QTabWidget()
        self.mircat_widget = MircatWidget(handler)
        tabs.addTab(self.mircat_widget, "MIRcat")
        self.t660_widget = T660Widget(handler)
        tabs.addTab(self.t660_widget, "T660-2")
        self.mux_widget = MuxWidget(
            handler,
            route_options=mux_route_options,
            route_labels=mux_route_labels,
            default_routes=mux_default_routes,
        )
        tabs.addTab(self.mux_widget, "MUX")
        self.setCentralWidget(tabs)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override name
        """Prevent application shutdown while hardware commands are still active."""

        for widget in (self.mircat_widget, self.t660_widget, self.mux_widget):
            if widget.command_running():
                widget.closeEvent(event)
                return
        super().closeEvent(event)
