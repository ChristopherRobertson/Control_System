"""Qt main window shell for the unified instrument interface."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from pathlib import Path
from control_app.paths import RUN_ROOT, default_save_location, get_save_location, set_save_location

from control_app.ui.contracts import WorkflowCommandHandler, blocked_handler
from control_app.ui.widgets.mircat_widget import MircatWidget
from control_app.ui.widgets.iris_widget import IrisWidget
from control_app.ui.widgets.ndyag_widget import NdYagWidget
from control_app.ui.widgets.scan_plotter_widget import ScanPlotterWidget
from control_app.ui.widgets.t660_widget import T660Widget
from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget


try:
    from PySide6.QtCore import QSettings, QTimer
    from PySide6.QtWidgets import (QMessageBox, QMainWindow, QTabWidget, QWidget,
                                  QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QScrollArea)

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
        self.phase_scan_widget = PhaseScanWidget(
            runner=getattr(handler, "phase_scan_runner", None),
            before_start=self._phase_start_blocker, preferences=self.preferences,
        )
        tabs.addTab(self.phase_scan_widget, "Phase Scan")
        self.dual_detector_phase_scan_widget = PhaseScanWidget(
            runner=getattr(handler, "dual_detector_phase_scan_runner", None),
            before_start=self._phase_start_blocker, preferences=self.preferences, dual_detector=True,
        )
        tabs.addTab(self.dual_detector_phase_scan_widget, "Dual-Detector Phase Scan")
        self.mircat_widget = MircatWidget(handler, before_scan=self._mircat_scan_start_blocker)
        tabs.addTab(self.mircat_widget, "MIRcat")
        self.t660_widget = T660Widget(handler)
        tabs.addTab(self.t660_widget, "T660-1")
        self.ndyag_widget = NdYagWidget(handler)
        tabs.addTab(self.ndyag_widget, "Nd:YAG")
        self.iris_widget = IrisWidget(handler, before_start=self._iris_start_blocker)
        tabs.addTab(self.iris_widget, "OPO Iris")
        self.scan_plotter_widget = ScanPlotterWidget()
        tabs.addTab(self.scan_plotter_widget, "Plotter")
        self.mircat_widget.scan_data_ready_callback = self.scan_plotter_widget.set_rows
        self.mircat_widget.scan_metadata_ready_callback = self.scan_plotter_widget.set_diagnostic_metadata
        central = QWidget()
        layout = QVBoxLayout(central)
        row = QHBoxLayout()
        row.addWidget(QLabel("Save Location:"))
        self.save_location = QLineEdit(str(get_save_location()))
        self._last_applied_save_location = get_save_location()
        self._using_daily_save_location = self._last_applied_save_location == default_save_location()
        self.save_location.setObjectName("save_location")
        self.save_location.setToolTip("Defaults to today's YYYY-MM-DD folder under evidence/experiments/runs. Missing folders are created when used.")
        self.browse_save_location = QPushButton("Browse…")
        row.addWidget(self.save_location, 1)
        row.addWidget(self.browse_save_location)
        layout.addLayout(row)
        self.save_location_status = QLabel()
        self.save_location_status.setWordWrap(True)
        layout.addWidget(self.save_location_status)
        # Instrument forms can be taller than a monitor's usable desktop.
        # Scroll the workspace instead of imposing their combined minimum
        # size on the native window (especially on secondary monitors).
        self.workspace_scroll = QScrollArea()
        self.workspace_scroll.setWidgetResizable(True)
        self.workspace_scroll.setWidget(tabs)
        layout.addWidget(self.workspace_scroll, 1)
        self.setCentralWidget(central)
        self.save_location.editingFinished.connect(self._apply_save_location)
        self.browse_save_location.clicked.connect(self._browse_save_location)
        self.phase_scan_widget.busy_changed.connect(lambda busy: self._phase_busy_changed(busy, self.phase_scan_widget))
        self.dual_detector_phase_scan_widget.busy_changed.connect(lambda busy: self._phase_busy_changed(busy, self.dual_detector_phase_scan_widget))
        self.mircat_widget.scan_busy_changed.connect(self._mircat_scan_busy_changed)
        self.iris_widget.busy_changed.connect(self._iris_busy_changed)
        self._save_timer = QTimer(self)
        self._save_timer.timeout.connect(self._update_save_enabled)
        self._save_timer.start(250)
        saved = self.preferences.value("save_location", "") if self.preferences else ""
        if saved:
            # Upgrade the old undated default; keep custom destinations.
            if Path(str(saved)).expanduser().resolve() == RUN_ROOT.resolve():
                saved = str(default_save_location())
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

    def _phase_busy_changed(self, busy, active_widget=None):
        setattr(self.command_handler, "phase_scan_active", busy) if hasattr(self.command_handler, "hardware_access") else None
        for index in range(self.tabs.count()):
            if self.tabs.widget(index) is not (active_widget or self.phase_scan_widget):
                self.tabs.setTabEnabled(index, not busy)
        self._update_save_enabled()

    def _iris_start_blocker(self):
        blockers = self._close_blockers()
        handler_blockers = getattr(self.command_handler, "ui_iris_motion_blockers", None)
        if callable(handler_blockers):
            blockers.extend(str(blocker) for blocker in handler_blockers())
        blockers = list(dict.fromkeys(blockers))
        if blockers:
            return "Stop other instrument activity first: " + "; ".join(blockers)
        return None

    def _mircat_scan_start_blocker(self):
        blocker = self._phase_start_blocker()
        if blocker:
            return blocker
        check = getattr(self.command_handler, "ui_mircat_scan_blockers", None)
        blockers = check() if callable(check) else []
        return "; ".join(blockers) if blockers else None

    def _mircat_scan_busy_changed(self, busy):
        if hasattr(self.command_handler, "mircat_scan_active"):
            self.command_handler.mircat_scan_active = busy
            if busy:
                self.command_handler.mircat_scan_cancel.clear()
        if busy:
            self.phase_scan_widget.runner.invalidate_background()
            self.dual_detector_phase_scan_widget.runner.invalidate_background()
        self.phase_scan_widget._update_buttons()
        self.dual_detector_phase_scan_widget._update_buttons()
        for index in range(self.tabs.count()):
            if self.tabs.widget(index) is not self.mircat_widget:
                self.tabs.setTabEnabled(index, not busy)
        self._update_save_enabled()

    def _iris_busy_changed(self, busy):
        for index in range(self.tabs.count()):
            if self.tabs.widget(index) is not self.iris_widget:
                self.tabs.setTabEnabled(index, not busy)
        self._update_save_enabled()

    def _update_save_enabled(self):
        try:
            busy = bool(self._close_blockers())
        except Exception:
            busy = True
        self.save_location.setEnabled(not busy)
        self.browse_save_location.setEnabled(not busy)
        if (not busy and self._using_daily_save_location and not self.save_location.hasFocus()
                and self.save_location.text() == str(self._last_applied_save_location)
                and self._last_applied_save_location != default_save_location()):
            self._apply_save_location()

    def _browse_save_location(self):
        selected = QFileDialog.getExistingDirectory(self, "Choose Save Location", self.save_location.text())
        if selected:
            self.save_location.setText(selected)
            self._apply_save_location()

    def _apply_save_location(self):
        try:
            if self._close_blockers():
                raise ValueError("Save Location cannot change while an instrument operation is active")
            previous = self._last_applied_save_location
            if self._using_daily_save_location and self.save_location.text() == str(previous):
                self.save_location.setText(str(default_save_location()))
            selected = set_save_location(self.save_location.text())
            self.save_location.setText(str(selected))
            self._last_applied_save_location = selected
            self._using_daily_save_location = selected == default_save_location().resolve()
            if selected != previous:
                self.phase_scan_widget.output_location_changed()
                self.dual_detector_phase_scan_widget.output_location_changed()
                self.scan_plotter_widget.destination.setText(str(selected))
                callback = getattr(self.command_handler, "output_location_changed", None)
                if callback:
                    callback(selected)
            if self.preferences:
                if selected == default_save_location().resolve():
                    # Resolve the next launch's date afresh instead of saving
                    # today's automatic folder as a permanent destination.
                    self.preferences.remove("save_location")
                else:
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
            ("Phase Scan", getattr(self, "phase_scan_widget", None)),
            ("Dual-Detector Phase Scan", getattr(self, "dual_detector_phase_scan_widget", None)),
            ("MIRcat", self.mircat_widget),
            ("T660-1", self.t660_widget),
            ("Nd:YAG", self.ndyag_widget),
            ("OPO Iris", self.iris_widget),
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
