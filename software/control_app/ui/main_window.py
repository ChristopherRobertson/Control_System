"""Qt main window shell for the unified instrument interface."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from pathlib import Path
from control_app.paths import default_save_location, default_tab_save_location, get_save_location, set_save_location

from control_app.ui.contracts import WorkflowCommandHandler, WorkflowResult, blocked_handler
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
from control_app.measurement_host.naming import tab_title


try:
    from PySide6.QtCore import QObject, QSettings, QTimer, Signal, Slot, Qt
    from PySide6.QtWidgets import (QMessageBox, QMainWindow, QTabWidget, QWidget,
                                  QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QScrollArea,
                                  QDialog, QDialogButtonBox, QFormLayout, QCheckBox, QSizePolicy, QComboBox)

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
        self._tab_titles_by_instance = {}
        self._tab_save_overrides = {}
        self._save_location_failures = {}
        saved_locations = self.preferences.value("tab_save_locations/v1", {}) if self.preferences else {}
        if isinstance(saved_locations, dict):
            self._tab_save_overrides = {key: Path(value).expanduser().resolve()
                                        for key, value in saved_locations.items()
                                        if isinstance(key, str) and isinstance(value, str) and value.strip()}
        self._switching_detector_mode = False
        self._published_save_roots = {}
        self._published_global_save_root = None
        self.safe_shutdown_completed = False
        self.safe_shutdown_completed_callback: Callable[[], None] | None = None
        self._recovery_worker = None
        self._shutdown_worker = None
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
            instance_save_root_provider=self._save_root_for_instance,
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
            existing_titles=(tab_title("phase_scan", "single"), tab_title("phase_scan", "dual"),
                             "MIRcat", "T660-1", "Nd:YAG", "OPO Iris", "Plotter"),
            existing_instance_ids=tuple(h.instance_id for h in phase_handles),
        )
        self.registration_issues = created.issues
        # Hidden feature pages must not enlarge the established device/Phase
        # Scan pages through QStackedWidget's aggregate minimum-size hint.
        self._measurement_page_policies = tuple(
            (handle.widget, QSizePolicy(handle.widget.sizePolicy())) for handle in created.handles)
        self._measurement_state_bridges = []
        self._tab_handles = {handle.widget: handle for handle in (*phase_handles, *created.handles)}
        for handle in (*phase_handles, *created.handles):
            self.measurement_lifecycle.register(handle)
            self._tab_titles_by_instance[handle.instance_id] = handle.title
            bridge = _MeasurementStateBridge(
                lambda *state, h=handle: self._measurement_state_changed(h, *state), self)
            self._measurement_state_bridges.append(bridge)
            handle.state_changed.connect(bridge.forward)
        for handle in (*created.handles, *phase_handles):
            tabs.addTab(handle.widget, handle.title)
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
        measurement_pages = {widget for widget, _ in self._measurement_page_policies}
        self._legacy_page_policies = tuple(
            (tabs.widget(index), QSizePolicy(tabs.widget(index).sizePolicy()))
            for index in range(tabs.count()) if tabs.widget(index) not in measurement_pages)
        self._update_measurement_page_sizes()
        self.mircat_widget.scan_data_ready_callback = self.scan_plotter_widget.set_rows
        self.mircat_widget.scan_metadata_ready_callback = self.scan_plotter_widget.set_diagnostic_metadata
        central = QWidget()
        layout = QVBoxLayout(central)
        row = QHBoxLayout()
        row.addWidget(QLabel("Detector:"))
        self.detector_mode = QComboBox()
        self.detector_mode.setObjectName("detector_mode")
        self.detector_mode.addItem("Single", "single")
        self.detector_mode.addItem("Dual", "dual")
        row.addWidget(self.detector_mode)
        row.addWidget(QLabel("Save Location:"))
        self.save_location = QLineEdit()
        self._displayed_save_key = None
        self._last_applied_save_location = None
        self.save_location.setObjectName("save_location")
        self.save_location.setToolTip("New files use today's folder and this tab's name. Browse changes this tab's destination only.")
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
        tabs.currentChanged.connect(self._current_tab_changed)
        self.detector_mode.currentIndexChanged.connect(self._detector_mode_changed)
        self.mircat_widget.scan_busy_changed.connect(self._mircat_scan_busy_changed)
        self.iris_widget.busy_changed.connect(self._iris_busy_changed)
        self._save_timer = QTimer(self)
        self._save_timer.timeout.connect(self._update_save_enabled)
        self._save_timer.start(250)
        self._update_host_status()
        # Detector mode always starts Single; per-mode pages remain instantiated.
        self._detector_mode_changed()

    def set_detector_mode(self, mode):
        index = self.detector_mode.findData(mode)
        if index < 0:
            raise ValueError("Detector mode must be single or dual")
        self.detector_mode.setCurrentIndex(index)

    def _detector_mode_changed(self, *_):
        mode = self.detector_mode.currentData()
        selected = self.tabs.currentWidget()
        handle = self._tab_handles.get(selected)
        if handle is not None:
            experiment = handle.instance_id.rsplit(":", 1)[0]
            selected = next((h.widget for h in self._tab_handles.values()
                             if h.instance_id == f"{experiment}:{mode}"), selected)
        self._switching_detector_mode = True
        previous = self.tabs.blockSignals(True)
        try:
            for widget, item in self._tab_handles.items():
                self.tabs.setTabVisible(self.tabs.indexOf(widget), item.instance_id.endswith(":" + mode))
            self.tabs.setCurrentWidget(selected)
        finally:
            self.tabs.blockSignals(previous)
            self._switching_detector_mode = False
        self._current_tab_changed()

    def _current_tab_changed(self, *_):
        if self._switching_detector_mode or self.tabs.currentWidget() is None:
            return
        if self.save_location.isModified():
            self._apply_save_location(refresh=False)
        handle = self._tab_handles.get(self.tabs.currentWidget())
        if handle is not None:
            mode = handle.instance_id.rsplit(":", 1)[1]
            if mode != self.detector_mode.currentData():
                self.set_detector_mode(mode)
                return
        self._update_measurement_page_sizes()
        self._display_save_destination()

    def _save_root_for_instance(self, instance_id):
        title = self._tab_titles_by_instance.get(instance_id)
        if title is None:
            title = tab_title(*instance_id.rsplit(":", 1))
        return self._tab_save_overrides.get(instance_id, default_tab_save_location(title))

    def _current_save_identity(self):
        widget = self.tabs.currentWidget()
        handle = self._tab_handles.get(widget)
        title = self.tabs.tabText(self.tabs.currentIndex())
        key = handle.instance_id if handle else "device:" + title
        return key, title

    @staticmethod
    def _default_save_root(title):
        # Nd:YAG is a device control page, never an output folder name.
        return default_save_location() if title == "Nd:YAG" else default_tab_save_location(title)

    def _display_save_destination(self):
        if self.tabs.currentWidget() is None:
            return
        key, title = self._current_save_identity()
        destination = self._tab_save_overrides.get(key, self._default_save_root(title))
        self._displayed_save_key = key
        self._displayed_save_title = title
        self._last_applied_save_location = destination
        failed = self._save_location_failures.get(key)
        self.save_location.setText(failed[0] if failed else str(destination))
        self.save_location.setModified(bool(failed))
        self.save_location_status.setText(failed[1] if failed else "")
        self._publish_save_destinations()

    def _publish_save_destinations(self):
        # Manual writers use a process-wide destination. Independent offline
        # measurements already own snapshots and do not pin that destination.
        busy = self._manual_destination_busy()
        selected = self._last_applied_save_location
        if not busy and (get_save_location() != selected or self._published_global_save_root != selected):
            set_save_location(selected, create=False)
            callback = getattr(self.command_handler, "output_location_changed", None)
            try:
                if callback:
                    callback(selected)
            except Exception as exc:
                self.measurement_lifecycle.report_error("manual:instrument", f"Output location update failed: {exc}")
            else:
                self._published_global_save_root = selected
        for handle in self.measurement_lifecycle.handles:
            try:
                if handle.command_running():
                    continue
                root = self._save_root_for_instance(handle.instance_id)
                if self._published_save_roots.get(handle.instance_id) != root:
                    handle.output_location_changed(root)
                    self._published_save_roots[handle.instance_id] = root
            except Exception as exc:
                self.measurement_lifecycle.report_error(handle.instance_id, f"Output location update failed: {exc}")
        plot_root = self._tab_save_overrides.get("device:Plotter", default_tab_save_location("Plotter"))
        if not busy and self._published_save_roots.get("device:Plotter") != plot_root:
            self.scan_plotter_widget.destination.setText(str(plot_root))
            self._published_save_roots["device:Plotter"] = plot_root

    def _destination_busy(self):
        return bool(self._close_blockers()) or self.ownership.snapshot()["state"] != "free"

    def _manual_destination_busy(self):
        if self._shutdown_worker is not None:
            return True
        if self.ownership.snapshot()["state"] != "free" or self._recovery_worker is not None:
            return True
        for widget in (self.mircat_widget, self.t660_widget, self.ndyag_widget, self.iris_widget):
            try:
                if widget.command_running():
                    return True
            except Exception as exc:
                self.measurement_lifecycle.report_error("manual:instrument", str(exc))
                return True
        return bool(getattr(self.command_handler, "mircat_scan_active", False)
                    or getattr(self.command_handler, "iris_command_active", False))

    def _update_measurement_page_sizes(self, *_):
        """Fit a selected feature without changing the established page layouts."""
        selected = self.tabs.currentWidget()
        feature_selected = any(widget is selected for widget, _ in self._measurement_page_policies)
        for widget, original in self._measurement_page_policies:
            policy = QSizePolicy(original)
            if widget is not selected:
                policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
                policy.setVerticalPolicy(QSizePolicy.Policy.Ignored)
            widget.setSizePolicy(policy)
            widget.updateGeometry()
        # QStackedWidget also counts pages hidden by the detector selector.
        # Exclude the opposite mode's height after it has been visited, while
        # retaining the established shared width of the two Phase Scan pages.
        # Visible established pages retain their original policies, except while
        # a compact experiment is selected.
        for widget, original in self._legacy_page_policies:
            policy = QSizePolicy(original)
            if feature_selected:
                policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
                policy.setVerticalPolicy(QSizePolicy.Policy.Ignored)
            elif not self.tabs.isTabVisible(self.tabs.indexOf(widget)):
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
        if getattr(self, "_shutdown_worker", None) is not None:
            # A signal/Qt quit during normal close must not launch a second
            # device cleanup while the first worker is still preserving data.
            return WorkflowResult("accepted", "Application shutdown is already running; waiting for cleanup and saving.")
        errors = self.measurement_lifecycle.request_emergency_stop(reason)
        stop = getattr(self.command_handler, "emergency_stop", None)
        result = stop(reason=reason) if callable(stop) else None
        if errors:
            self.measurement_lifecycle.report_error("application", "; ".join(errors))
        return result

    def live_worker_blockers(self):
        """Include analysis workers when deciding whether Qt can be destroyed."""
        blockers = []
        if getattr(self, "_shutdown_worker", None) is not None:
            blockers.append("Application shutdown is still running.")
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
        if self._shutdown_worker is not None:
            return
        if self.tabs.currentWidget() is None:
            return
        self._update_host_status()
        try:
            busy = self._destination_busy()
        except Exception:
            busy = True
        self.save_location.setEnabled(not busy)
        self.browse_save_location.setEnabled(not busy)
        if not self.save_location.isModified():
            key, title = self._current_save_identity()
            expected = self._tab_save_overrides.get(key, self._default_save_root(title))
            if expected != self._last_applied_save_location:
                self._display_save_destination()
            else:
                self._publish_save_destinations()

    def _browse_save_location(self):
        selected = QFileDialog.getExistingDirectory(self, "Choose Save Location", self.save_location.text())
        if selected:
            self.save_location.setText(selected)
            self._apply_save_location()

    def _apply_save_location(self, *, refresh=True):
        try:
            if self._destination_busy():
                raise ValueError("Save Location cannot change while an instrument operation is active")
            key = self._displayed_save_key
            automatic = self._default_save_root(self._displayed_save_title)
            text = self.save_location.text()
            if (text == str(self._last_applied_save_location)
                    and key not in self._tab_save_overrides):
                text = str(automatic)
            selected = set_save_location(text)
            if selected == automatic.resolve():
                self._tab_save_overrides.pop(key, None)
            else:
                self._tab_save_overrides[key] = selected
            if self.preferences:
                self.preferences.setValue("tab_save_locations/v1", {key: str(path)
                                          for key, path in self._tab_save_overrides.items()})
            self._save_location_failures.pop(key, None)
            self.save_location.setModified(False)
            self.save_location_status.clear()
            if refresh:
                self._display_save_destination()
        except (OSError, ValueError) as exc:
            message = f"Save Location not applied: {exc}"
            self._save_location_failures[self._displayed_save_key] = (self.save_location.text(), message)
            self.save_location_status.setText(message)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override name
        """Keep Qt responsive until background safe shutdown has finished."""

        if self.safe_shutdown_completed:
            event.accept()
            return
        if self._shutdown_worker is not None:
            event.ignore()
            return

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
            from control_app.measurement_host.presentation import OperationWorker
            event.ignore()
            self._save_timer.stop()
            self.centralWidget().setEnabled(False)
            self.statusBar().showMessage("Closing: waiting for instrument shutdown and saved records…")
            worker = OperationWorker(lambda _: shutdown(reason="main_window_close"), self)
            self._shutdown_worker = worker
            worker.finished.connect(self._shutdown_finished)
            worker.start()
            return

        self._finish_safe_close()
        event.accept()

    def _finish_safe_close(self):
        self.safe_shutdown_completed = True
        if self.safe_shutdown_completed_callback is not None:
            self.safe_shutdown_completed_callback()
        timer = getattr(self, "_save_timer", None)
        if timer is not None:
            timer.stop()

    def _shutdown_finished(self):
        worker = self._shutdown_worker
        outcome = worker.outcome
        self._shutdown_worker = None
        worker.deleteLater()
        if outcome is not None and outcome.state == "completed" and getattr(outcome.result, "status", None) == "complete":
            self._finish_safe_close()
            self.close()
            return
        message = (outcome.error if outcome is not None and outcome.state != "completed"
                   else str(getattr(getattr(outcome, "result", None), "message", "Shutdown did not complete.")))
        self.centralWidget().setEnabled(True)
        self.statusBar().clearMessage()
        self._save_timer.start()
        self._update_save_enabled()
        self._show_close_error("Safe Shutdown Failed", message + "\n\nThe application remains open; shutdown can be retried.")

    def _close_blockers(self) -> list[str]:
        blockers: list[str] = self.measurement_lifecycle.close_blockers()
        if getattr(self, "_shutdown_worker", None) is not None:
            blockers.append("Application shutdown is still running.")
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
