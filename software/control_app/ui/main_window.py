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
from control_app.measurement_host.context import ContextFactory
from control_app.measurement_host.device_factories import installed_device_factories
from control_app.measurement_host.legacy_phase_scan import create_phase_scan_tabs
from control_app.measurement_host.lifecycle import MeasurementLifecycle
from control_app.measurement_host.ownership import default_coordinator
from control_app.measurement_host.registry import create_registered_tabs, discover_modules


try:
    from PySide6.QtCore import QObject, QSettings, QTimer, Signal, Slot, Qt
    from PySide6.QtWidgets import (QMessageBox, QMainWindow, QTabWidget, QWidget,
                                  QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QScrollArea,
                                  QDialog, QDialogButtonBox, QFormLayout, QCheckBox, QSizePolicy)

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - import-safe in non-UI environments
    PYSIDE6_AVAILABLE = False
    QMessageBox = object
    QMainWindow = object
    QTabWidget = object


if PYSIDE6_AVAILABLE:
    class _MeasurementStateBridge(QObject):
        """Accept any handle state signal, then deliver on the shell's Qt thread.

        The handle may expose a signal owned by a worker QObject. Forwarding
        only emits a Qt signal; all widget inspection/mutation happens in the
        queued QObject slot, independently of the source object's affinity.
        """

        changed = Signal(object)

        def __init__(self, callback, parent=None):
            super().__init__(parent)
            self.callback = callback
            self.changed.connect(self.deliver, Qt.ConnectionType.QueuedConnection)

        def forward(self, *state):
            self.changed.emit(tuple(state))

        @Slot(object)
        def deliver(self, state):
            self.callback(*state)


    class _InstrumentNotificationBridge(QObject):
        changed = Signal(object)

        def __init__(self, callback, parent=None):
            super().__init__(parent)
            self.callback = callback
            self.changed.connect(self.deliver, Qt.ConnectionType.QueuedConnection)

        @Slot(object)
        def deliver(self, change):
            self.callback(change)


class ControlSystemMainWindow(QMainWindow):
    """Main desktop shell composed from independent device widgets."""

    def __init__(
        self,
        command_handler: WorkflowCommandHandler | None = None,
        *,
        persist_settings: bool = False,
        module_discovery=None,
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
        self._recovery_worker = None
        self.ownership = getattr(handler, "coordinator", None) or default_coordinator()
        self.measurement_lifecycle = MeasurementLifecycle(self.ownership)
        setattr(handler, "measurement_lifecycle", self.measurement_lifecycle)
        self._instrument_bridge = _InstrumentNotificationBridge(self.measurement_lifecycle.deliver_instrument_state, self)
        self.measurement_lifecycle.instrument_dispatcher = self._instrument_bridge.changed.emit
        setattr(handler, "instrument_state_change_callback", self._manual_instrument_changed)
        inventory = getattr(handler, "inventory", None)
        self.measurement_context_factory = ContextFactory(
            configuration_provider=lambda: inventory.to_dict() if inventory is not None else {},
            real_device_factories=(installed_device_factories()
                                   if getattr(handler, "hardware_access", False) else {}),
            simulated_device_factories=getattr(handler, "simulated_device_factories", {}),
            preference_backend=self.preferences, ownership=self.ownership,
            lifecycle=self.measurement_lifecycle, save_root_provider=get_save_location,
        )

        self.tabs = tabs = QTabWidget()
        tabs.setUsesScrollButtons(True)
        tabs.tabBar().setExpanding(False)
        phase_handles = create_phase_scan_tabs(
            self.measurement_context_factory.for_experiment("phase_scan"),
            single_runner=getattr(handler, "phase_scan_runner", None),
            dual_runner=getattr(handler, "dual_detector_phase_scan_runner", None),
            before_start=self._phase_start_blocker, legacy_preferences=self.preferences,
        )
        self.phase_scan_widget, self.dual_detector_phase_scan_widget = (h.widget for h in phase_handles)
        discovered = discover_modules() if module_discovery is None else module_discovery
        created = create_registered_tabs(
            discovered, self.measurement_context_factory,
            existing_titles=("Phase Scan", "Dual-Detector Phase Scan", "MIRcat", "T660-1", "Nd:YAG", "OPO Iris", "Plotter"),
            existing_instance_ids=tuple(h.instance_id for h in phase_handles),
        )
        self.registration_issues = created.issues
        # Hidden feature pages must not enlarge the established device/Phase
        # Scan pages through QStackedWidget's aggregate minimum-size hint.
        self._measurement_page_policies = tuple(
            (handle.widget, QSizePolicy(handle.widget.sizePolicy())) for handle in created.handles)
        self._measurement_state_bridges = []
        for handle in (*phase_handles, *created.handles):
            self.measurement_lifecycle.register(handle)
            tabs.addTab(handle.widget, handle.title)
            bridge = _MeasurementStateBridge(
                lambda *state, h=handle: self._measurement_state_changed(h, *state), self)
            self._measurement_state_bridges.append(bridge)
            handle.state_changed.connect(bridge.forward)
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
        tabs.currentChanged.connect(self._update_measurement_page_sizes)
        self._update_measurement_page_sizes()
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
        self.host_status = QLabel()
        self.host_status.setWordWrap(True)
        layout.addWidget(self.host_status)
        self.recovery_button = QPushButton("Review instrument recovery…")
        self.recovery_button.clicked.connect(self._review_recovery)
        layout.addWidget(self.recovery_button)
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
        self.mircat_widget.scan_busy_changed.connect(self._mircat_scan_busy_changed)
        self.iris_widget.busy_changed.connect(self._iris_busy_changed)
        self._save_timer = QTimer(self)
        self._save_timer.timeout.connect(self._update_save_enabled)
        self._save_timer.start(250)
        self._update_host_status()
        saved = self.preferences.value("save_location", "") if self.preferences else ""
        if saved:
            # Upgrade the old undated default; keep custom destinations.
            if Path(str(saved)).expanduser().resolve() == RUN_ROOT.resolve():
                saved = str(default_save_location())
            self.save_location.setText(str(saved))
            self._apply_save_location()

    def _update_measurement_page_sizes(self, *_):
        """Use a feature's native sizing only while that feature is selected."""
        selected = self.tabs.currentWidget()
        for widget, original in self._measurement_page_policies:
            policy = QSizePolicy(original)
            if widget is not selected:
                policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
                policy.setVerticalPolicy(QSizePolicy.Policy.Ignored)
            widget.setSizePolicy(policy)
            widget.updateGeometry()
        self.tabs.updateGeometry()

    def _phase_start_blocker(self, hardware=True):
        if not hardware:
            # Simulations use the already selected destination and their own
            # frozen root; a live instrument owner does not block their work.
            return None
        blockers = []
        state = self.ownership.snapshot()
        if state["state"] != "free":
            blockers.append(f"Instrument {state['state']}: {state.get('owner')}. {state.get('detail', '')}")
        handler_blockers = getattr(self.command_handler, "ui_close_blockers", None)
        if callable(handler_blockers):
            blockers.extend(handler_blockers())
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
        # Compatibility hook for existing callers; ownership is enforced by
        # backend tokens while every tab remains available for offline work.
        self._update_save_enabled()

    def _measurement_state_changed(self, handle, *state):
        busy = bool(state[0]) if state else bool(handle.command_running())
        self.measurement_lifecycle.notify_state(handle.instance_id, busy, str(state[1]) if len(state) > 1 else "")
        self._update_save_enabled()

    def _update_host_status(self):
        messages = [f"{issue.module}: {issue.stage}: {issue.message}" for issue in self.registration_issues]
        state = self.ownership.snapshot()
        if state["state"] != "free":
            owner = state.get("owner") or {}
            messages.append(f"Instrument {state['state']}: {owner.get('instance_id', 'unknown owner')}. {state.get('detail', '')}")
        messages.extend(self.measurement_lifecycle.errors[-3:])
        self.host_status.setText("\n".join(messages))
        self.host_status.setVisible(bool(messages))
        self.recovery_button.setVisible(state["state"] != "free" and callable(
            getattr(self.command_handler, "ui_recover_instrument", None)))
        self.recovery_button.setEnabled(self._recovery_worker is None)

    def _review_recovery(self):
        """Explicit, recorded verification of a fault; never repeat acquisition."""
        if self._recovery_worker is not None or self.live_worker_blockers():
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Verify instrument recovery")
        layout = QVBoxLayout(dialog)
        explanation = QLabel("First stop emission and timing outputs using the owning controls. "
                             "Inspect the retained native, partial, cleanup and restoration records. "
                             "Identify the evidence for the two confirmations below. Recovery runs "
                             "the safe-shutdown checks and records your verification; it never restarts a measurement.")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        form = QFormLayout()
        operator, evidence = QLineEdit(), QLineEdit()
        form.addRow("Verified by", operator)
        form.addRow("Recovery evidence file", evidence)
        layout.addLayout(form)
        browse = QPushButton("Select evidence file…")
        def select_evidence():
            path, _ = QFileDialog.getOpenFileName(dialog, "Recovery evidence", str(get_save_location()))
            if path:
                evidence.setText(path)
        browse.clicked.connect(select_evidence)
        layout.addWidget(browse)
        restoration = QCheckBox("I verified instrument restoration against the retained configuration records")
        preservation = QCheckBox("I verified preservation of all required native and partial data")
        layout.addWidget(restoration)
        layout.addWidget(preservation)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not (operator.text().strip() and evidence.text().strip() and restoration.isChecked() and preservation.isChecked()):
            self._show_close_error("Recovery verification incomplete", "A named verifier, evidence file and both verified outcomes are required.")
            return
        from control_app.measurement_host.presentation import OperationWorker
        operator_name, evidence_path = operator.text().strip(), evidence.text().strip()
        worker = OperationWorker(lambda _: self.command_handler.ui_recover_instrument(
            operator=operator_name, evidence=evidence_path,
            restoration_verified=True, preservation_verified=True), self)
        self._recovery_worker = worker
        worker.finished.connect(self._recovery_finished)
        worker.start()
        self._update_save_enabled()

    def _recovery_finished(self):
        worker, self._recovery_worker = self._recovery_worker, None
        outcome = worker.outcome
        worker.deleteLater()
        if outcome is not None and outcome.state == "failed":
            self.measurement_lifecycle.report_error("recovery", outcome.error)
            self._show_close_error("Recovery failed", outcome.error)
        elif outcome is not None and getattr(outcome.result, "status", None) != "complete":
            self._show_close_error("Recovery incomplete", str(getattr(outcome.result, "message", outcome.result)))
        self._update_save_enabled()

    def request_emergency_stop(self, reason):
        """Cancel all registered live hardware operations, preserving offline work."""
        errors = self.measurement_lifecycle.request_emergency_stop(reason)
        stop = getattr(self.command_handler, "emergency_stop", None)
        result = stop(reason=reason) if callable(stop) else None
        if errors:
            self.measurement_lifecycle.report_error("application", "; ".join(errors))
        return result

    def live_worker_blockers(self):
        """Include analysis workers when deciding whether Qt can be destroyed."""
        blockers = []
        for handle in self.measurement_lifecycle.handles:
            try:
                if handle.command_running():
                    blockers.append(f"{handle.title} worker is still running.")
            except Exception as exc:
                blockers.append(f"{handle.title}: cannot verify worker completion: {exc}")
        if self._recovery_worker is not None:
            blockers.append("Instrument recovery verification is running.")
        for widget in (self.mircat_widget, self.t660_widget, self.ndyag_widget, self.iris_widget):
            if widget.command_running():
                blockers.append("A manual device worker is still running.")
        return blockers

    def _manual_instrument_changed(self, device_ids, configuration_changes=None, reason="Manual instrument configuration changed"):
        from control_app.measurement_host.interchange import DeviceConfigurationChange, InstrumentStateChange
        changes = tuple(DeviceConfigurationChange(str(device), str(key), None, value)
                        for device in device_ids
                        for key, value in (configuration_changes or {"configuration": "changed"}).items())
        if not changes:
            return
        self._instrument_bridge.changed.emit(InstrumentStateChange(
            producer_instance_id="manual:instrument", reason=str(reason), changes=changes,
            recipients=tuple(h.instance_id for h in self.measurement_lifecycle.handles),
        ))

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
            self._manual_instrument_changed(("mircat", "t660_1", "t660_2"),
                                            {"acquisition_configuration": "manual sweep"}, "MIRcat Sweep Scan started")
        self._update_save_enabled()

    def _iris_busy_changed(self, busy):
        self._update_save_enabled()

    def _update_save_enabled(self):
        self._update_host_status()
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
                self.measurement_lifecycle.output_location_changed(selected)
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
        blockers: list[str] = self.measurement_lifecycle.close_blockers()
        if self._recovery_worker is not None:
            blockers.append("Instrument recovery verification is running.")
        candidates = (
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
