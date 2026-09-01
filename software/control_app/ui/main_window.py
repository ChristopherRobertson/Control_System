"""Qt main window shell for the unified instrument interface."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from pathlib import Path
from control_app.paths import get_save_location, set_save_location

from control_app.ui.contracts import WorkflowCommandHandler, blocked_handler
from control_app.ui.widgets.mircat_widget import MircatWidget
from control_app.ui.widgets.ndyag_widget import NdYagWidget
from control_app.ui.widgets.scan_plotter_widget import ScanPlotterWidget
from control_app.ui.widgets.t660_widget import T660Widget
from control_app.ui.widgets.experiment_builder_widget import ExperimentBuilderWidget
from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
from control_app.ui.widgets.workflow_selector_widget import WorkflowSelectorWidget


try:
    from PySide6.QtCore import QSettings, QTimer
    from PySide6.QtWidgets import (QMessageBox, QMainWindow, QTabWidget, QWidget,
                                  QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog)

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
        *,
        persist_settings: bool = False,
    ) -> None:
        if not PYSIDE6_AVAILABLE:
            raise RuntimeError("PySide6 is required to instantiate ControlSystemMainWindow")
        super().__init__()
        self.setWindowTitle("IR Spectroscope Control System")
        handler = command_handler or blocked_handler("No workflow command handler is attached.")
        self.command_handler: Any = handler
        self.preferences = QSettings("ControlSystem", "IRSpectroscope") if persist_settings else None
        self.safe_shutdown_completed = False
        self.safe_shutdown_completed_callback: Callable[[], None] | None = None

        self.tabs = tabs = QTabWidget()
        self.experiment_builder_widget = ExperimentBuilderWidget()
        tabs.addTab(self.experiment_builder_widget, "Experiment Builder")
        self.workflow_selector_widget = WorkflowSelectorWidget(handler)
        tabs.addTab(self.workflow_selector_widget, "Configured Workflows")
        diagnostic = None
        if getattr(handler, "hardware_access", False):
            from control_app.workflows.phase_scan_diagnostic import capture_inhibited_diagnostic
            diagnostic = capture_inhibited_diagnostic
        self.phase_scan_widget = PhaseScanWidget(
            runner=getattr(handler, "phase_scan_runner", None), diagnostic=diagnostic,
            before_start=self._phase_start_blocker,
        )
        tabs.addTab(self.phase_scan_widget, "Phase Scan")
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
        central = QWidget()
        layout = QVBoxLayout(central)
        row = QHBoxLayout()
        row.addWidget(QLabel("Save Location:"))
        self.save_location = QLineEdit(str(get_save_location()))
        self.save_location.setObjectName("save_location")
        self.save_location.setToolTip("Folder for new data and exports. Missing folders are created.")
        self.browse_save_location = QPushButton("Browse…")
        row.addWidget(self.save_location, 1)
        row.addWidget(self.browse_save_location)
        layout.addLayout(row)
        self.save_location_status = QLabel()
        self.save_location_status.setWordWrap(True)
        layout.addWidget(self.save_location_status)
        layout.addWidget(tabs, 1)
        self.setCentralWidget(central)
        self.save_location.editingFinished.connect(self._apply_save_location)
        self.browse_save_location.clicked.connect(self._browse_save_location)
        self.phase_scan_widget.busy_changed.connect(self._phase_busy_changed)
        self._save_timer = QTimer(self)
        self._save_timer.timeout.connect(self._update_save_enabled)
        self._save_timer.start(250)
        saved = self.preferences.value("save_location", "") if self.preferences else ""
        if saved:
            self.save_location.setText(str(saved))
            self._apply_save_location()

    def _phase_start_blocker(self):
        blockers = self._close_blockers()
        if blockers:
            return "Stop other instrument activity first: " + "; ".join(blockers)
        try:
            # Commit the current text, including a path typed just before Start.
            self._apply_save_location()
            if self.save_location_status.text():
                return self.save_location_status.text()
        except Exception as exc:
            return str(exc)
        return None

    def _phase_busy_changed(self, busy):
        setattr(self.command_handler, "phase_scan_active", busy) if hasattr(self.command_handler, "hardware_access") else None
        for index in range(self.tabs.count()):
            if self.tabs.widget(index) is not self.phase_scan_widget:
                self.tabs.setTabEnabled(index, not busy)
        self._update_save_enabled()

    def _update_save_enabled(self):
        try:
            busy = bool(self._close_blockers())
        except Exception:
            busy = True
        self.save_location.setEnabled(not busy)
        self.browse_save_location.setEnabled(not busy)

    def _browse_save_location(self):
        selected = QFileDialog.getExistingDirectory(self, "Choose Save Location", self.save_location.text())
        if selected:
            self.save_location.setText(selected)
            self._apply_save_location()

    def _apply_save_location(self):
        try:
            if self._close_blockers():
                raise ValueError("Save Location cannot change while an instrument operation is active")
            previous = get_save_location()
            selected = set_save_location(self.save_location.text())
            self.save_location.setText(str(selected))
            if selected != previous:
                self.phase_scan_widget.output_location_changed()
                self.scan_plotter_widget.destination.setText(str(selected))
                callback = getattr(self.command_handler, "output_location_changed", None)
                if callback:
                    callback(selected)
            if self.preferences:
                self.preferences.setValue("save_location", str(selected))
            self.save_location_status.clear()
        except (OSError, ValueError) as exc:
            self.save_location_status.setText(f"Save Location not applied: {exc}")

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
            ("Phase Scan", getattr(self, "phase_scan_widget", None)),
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
