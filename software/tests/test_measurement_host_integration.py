"""Installed pair integration, legacy compatibility, and complete app lifecycle."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QApplication, QWidget

from control_app.measurement_host.context import ContextFactory
from control_app.measurement_host.contracts import ModuleDescriptor, TabHandle
from control_app.measurement_host.interchange import DeviceConfigurationChange, InstrumentStateChange
from control_app.measurement_host.lifecycle import MeasurementLifecycle
from control_app.measurement_host.ownership import HardwareCoordinator
from control_app.measurement_host.registry import discover_modules


@pytest.fixture
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance
    instance.processEvents()


class DummyTab(QWidget):
    busy_changed = Signal(bool)

    def __init__(self, context):
        super().__init__()
        self.context = context
        self.busy = False
        self.aborts = []
        self.destinations = []
        self.changes = []

    def handle(self, title):
        return TabHandle(self.context.instance_id, title, self, lambda: self.busy,
                         lambda: ["Saving records"] if self.busy else [], self.aborts.append,
                         self.destinations.append, self.changes.append, self.busy_changed)


def pair_factory(context):
    return tuple(DummyTab(context.for_mode(mode)).handle(f"{context.experiment_id} {mode}")
                 for mode in ("single", "dual"))


def test_independent_packages_install_together_without_shell_edits(app, tmp_path, monkeypatch):
    """Actual registration imports from separate directories plus broken SDK isolation."""
    from control_app.ui.main_window import ControlSystemMainWindow
    ids = ("steady_state_slow_scan", "fixed_wavenumber_kinetics", "nanosecond_stroboscopy",
           "microsecond_stroboscopy", "repeated_rapid_scan", "single_pump_scan_burst")
    package = tmp_path / "independent_measurements"
    package.mkdir()
    (package / "__init__.py").write_text("")
    for index, experiment_id in enumerate(ids):
        folder = package / experiment_id
        folder.mkdir()
        (folder / "registration.py").write_text(
            "from control_app.measurement_host import ModuleDescriptor\n"
            "from test_measurement_host_integration import pair_factory\n"
            f"DESCRIPTOR = ModuleDescriptor(1, {experiment_id!r}, {index}, pair_factory)\n")
    broken = package / "unavailable_sdk"
    broken.mkdir()
    (broken / "registration.py").write_text("raise ImportError('optional device SDK unavailable')\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    discovery = discover_modules(package_name="independent_measurements")
    window = ControlSystemMainWindow(module_discovery=discovery)
    try:
        assert window.tabs.count() == 19
        assert [window.tabs.tabText(i) for i in range(14, 19)] == ["MIRcat", "T660-1", "Nd:YAG", "OPO Iris", "Plotter"]
        assert window.tab_selector.count() == 19
        assert len({window.tabs.tabText(i) for i in range(19)}) == 19
        assert "optional device SDK unavailable" in window.host_status.text()
        handles = window.measurement_lifecycle.handles
        assert len({h.instance_id for h in handles}) == 14
        for index in range(19):
            window.tab_selector.setCurrentIndex(index)
            assert window.tabs.currentIndex() == index
        offline = handles[2]
        offline.widget.busy = True
        offline.state_changed.emit(True)
        assert all(window.tabs.isTabEnabled(i) for i in range(19))
        assert any(offline.title in blocker for blocker in window._close_blockers())
        offline.widget.busy = False
    finally:
        window.deleteLater()


def test_lifecycle_targets_local_owner_and_preserves_offline_work(app, tmp_path):
    coordinator = HardwareCoordinator(tmp_path / "instrument.lock")
    lifecycle = MeasurementLifecycle(coordinator)
    contexts = ContextFactory(ownership=coordinator, save_root_provider=lambda: tmp_path)
    handles = pair_factory(contexts.for_experiment("nanosecond_stroboscopy"))
    for handle in handles:
        lifecycle.register(handle)
        handle.widget.busy = True
    token = coordinator.acquire(handles[1].instance_id)
    try:
        lifecycle.request_emergency_stop("operator emergency")
        assert handles[1].widget.aborts == ["operator emergency"]
        assert handles[0].widget.aborts == []
        assert len(lifecycle.close_blockers()) == 2
        event = InstrumentStateChange("manual:mircat", (handles[0].instance_id,),
            (DeviceConfigurationChange("mircat", "scan_speed_cm1_s", 100, 200),), "scan speed changed")
        lifecycle.publish_instrument_state(event)
        assert handles[0].widget.changes == [event]
        assert handles[1].widget.changes == []
        lifecycle.output_location_changed(tmp_path / "next")
        assert all(h.widget.destinations == [tmp_path / "next"] for h in handles)
    finally:
        coordinator.release(token, safe_verified=True)
        for h in handles:
            h.widget.deleteLater()


def test_failed_close_callback_does_not_hide_other_blockers(app, tmp_path):
    lifecycle = MeasurementLifecycle(HardwareCoordinator(tmp_path / "instrument.lock"))
    contexts = ContextFactory()
    from dataclasses import replace
    single, dual = pair_factory(contexts.for_experiment("fixed_wavenumber_kinetics"))
    def fail():
        raise RuntimeError("broken optional close callback")
    lifecycle.register(replace(single, close_blockers=fail))
    dual.widget.busy = True
    lifecycle.register(dual)
    blockers = lifecycle.close_blockers()
    assert any("broken optional close callback" in item for item in blockers)
    assert any(dual.title in item for item in blockers)
    single.widget.deleteLater()
    dual.widget.deleteLater()


def test_legacy_preferences_read_through_without_cross_mode_writes(app, tmp_path):
    from control_app.measurement_host.legacy_phase_scan import create_phase_scan_tabs
    prefs = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    prefs.setValue("regular_phase_scan", json.dumps({"inputs": {"pre_pump_ms": 3}}))
    prefs.setValue("dual_detector_phase_scan", json.dumps({"inputs": {"pre_pump_ms": 7}}))
    before = prefs.value("regular_phase_scan")
    context = ContextFactory(preference_backend=prefs).for_experiment("phase_scan")
    single, dual = create_phase_scan_tabs(context, legacy_preferences=prefs)
    try:
        assert single.widget.settings().pre_pump_ms == 3
        assert dual.widget.settings().pre_pump_ms == 7
        single.widget.inputs["pre_pump_ms"].setValue(5)
        assert dual.widget.settings().pre_pump_ms == 7
        assert prefs.value("regular_phase_scan") == before
        saved = json.loads(prefs.value("measurements/phase_scan/single/v1/settings"))
        assert saved["inputs"]["pre_pump_ms"] == 5
        assert single.widget.runner is not dual.widget.runner
        assert single.widget.runner.cancel is not dual.widget.runner.cancel
    finally:
        single.widget.deleteLater()
        dual.widget.deleteLater()


def test_phase_scan_freezes_destination_and_plan_before_worker_dispatch(app, tmp_path, monkeypatch):
    import control_app.ui.widgets.phase_scan_widget as phase_ui
    from control_app.workflows.regular_phase_scan import HF2Capabilities
    from control_app.workflows.regular_phase_scan_runner import RegularPhaseScanRunner
    from PySide6.QtWidgets import QMessageBox
    class QueuedWorker(QObject):
        message = Signal(str)
        scan = Signal(object, object, str)
        configured = Signal(object)
        result = Signal(object)
        stopped = Signal(str)
        failed = Signal(str)
        finished = Signal()
        def __init__(self, operation, parent=None):
            super().__init__(parent)
            self.operation = operation
        def start(self):
            pass
    monkeypatch.setattr(phase_ui, "_PhaseWorker", QueuedWorker)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    roots = [tmp_path / "original"]
    runner = RegularPhaseScanRunner(lambda: None, capabilities=HF2Capabilities(verified=True))
    seen = []
    runner.execute = lambda kind, root, plan, **kwargs: seen.append((root, plan))
    widget = phase_ui.PhaseScanWidget(runner=runner, save_root_provider=lambda: roots[0])
    try:
        original = widget.plan
        widget._begin("background")
        roots[0] = tmp_path / "changed"
        original.hf2_selection["test_mutation"] = "later edit"
        widget.worker.operation(widget.worker)
        assert seen[0][0] == (tmp_path / "original").resolve()
        assert "test_mutation" not in seen[0][1].hf2_selection
        widget.worker.finished.emit()
    finally:
        widget.deleteLater()


def test_worker_instrument_notifications_are_queued_to_recipient_gui_thread(app):
    """Publishing from a scientific worker must not invoke recipient Qt code there."""
    from dataclasses import replace
    from threading import Thread, get_ident
    import time
    from PySide6.QtCore import QThread
    from control_app.ui.main_window import ControlSystemMainWindow
    received = []
    gui_ident = get_ident()

    def factory(context):
        single, dual = pair_factory(context)
        def record(change):
            received.append((change, get_ident(), QThread.currentThread() is dual.widget.thread()))
        return single, replace(dual, instrument_state_changed=record)

    descriptor = ModuleDescriptor(1, "microsecond_stroboscopy", 10, factory)
    window = ControlSystemMainWindow(module_discovery=(descriptor,))
    try:
        single, dual = window.measurement_lifecycle.handles[-2:]
        event = InstrumentStateChange(single.instance_id, (dual.instance_id,),
            (DeviceConfigurationChange("hf2li", "sample_rate_sps", 1000, 2000),), "New acquisition readbacks")
        failures = []
        def publish():
            try:
                single.widget.context.lifecycle.publish_instrument_state(event)
            except Exception as exc:
                failures.append(exc)
        worker = Thread(target=publish)
        worker.start()
        worker.join(timeout=2)
        assert not worker.is_alive() and failures == []
        assert received == []  # Delivery requires the GUI event loop.
        deadline = time.monotonic() + 2
        while not received and time.monotonic() < deadline:
            app.processEvents()
        assert received == [(event, gui_ident, True)]
        assert window.measurement_lifecycle.instrument_events[-1] == event
    finally:
        window.deleteLater()


def test_persistent_close_fault_does_not_hide_recovery_or_claim_a_running_worker(app, monkeypatch):
    from dataclasses import replace
    from control_app.ui import main_window

    def factory(context):
        single, dual = pair_factory(context)
        return replace(single, close_blockers=lambda: ["Restoration remains unverified"]), dual

    descriptor = ModuleDescriptor(1, "single_pump_scan_burst", 10, factory)
    window = main_window.ControlSystemMainWindow(module_discovery=(descriptor,))
    opened = []
    def inspect_dialog(dialog):
        opened.append(dialog.windowTitle())
        return main_window.QDialog.DialogCode.Rejected
    monkeypatch.setattr(main_window.QDialog, "exec", inspect_dialog)
    try:
        assert any("Restoration remains unverified" in item for item in window._close_blockers())
        assert window.live_worker_blockers() == []
        window._review_recovery()
        assert opened == ["Verify instrument recovery"]
        active = window.measurement_lifecycle.handles[-1].widget
        active.busy = True
        assert window.live_worker_blockers()
        window._review_recovery()
        assert len(opened) == 1  # Real work still blocks recovery until preservation ends.
        active.busy = False
    finally:
        window.deleteLater()


def test_legacy_simulations_can_start_while_another_handle_owns_hardware(app, tmp_path):
    from control_app.ui.contracts import blocked_handler
    from control_app.ui.main_window import ControlSystemMainWindow
    coordinator = HardwareCoordinator(tmp_path / "simulation-independence.lock")
    handler = blocked_handler("No hardware access in this test")
    handler.coordinator = coordinator
    window = ControlSystemMainWindow(command_handler=handler, module_discovery=())
    token = coordinator.acquire("nanosecond_stroboscopy:single")
    try:
        assert window.phase_scan_widget.before_start() is None
        assert window.dual_detector_phase_scan_widget.before_start() is None
        assert window._phase_start_blocker(hardware=True)
        assert coordinator.snapshot()["owner"]["instance_id"] == "nanosecond_stroboscopy:single"
    finally:
        coordinator.release(token, safe_verified=True, preservation_verified=True)
        window.deleteLater()


def test_worker_owned_handle_state_signal_updates_shell_only_on_gui_thread(app):
    from dataclasses import replace
    from threading import get_ident
    import time
    from PySide6.QtCore import QThread, Slot
    from control_app.ui.main_window import ControlSystemMainWindow

    class WorkerState(QObject):
        changed = Signal(bool, str)
        delivered = Signal()

        @Slot()
        def publish(self):
            self.changed.emit(True, "native saving")
            self.delivered.emit()

    source = WorkerState()
    thread = QThread()
    source.moveToThread(thread)
    thread.started.connect(source.publish)

    def factory(context):
        single, dual = pair_factory(context)
        return replace(single, state_changed=source.changed), dual

    descriptor = ModuleDescriptor(1, "repeated_rapid_scan", 10, factory)
    window = ControlSystemMainWindow(module_discovery=(descriptor,))
    original = window._measurement_state_changed
    calls = []
    gui_ident = get_ident()
    def record(handle, *state):
        calls.append((handle.instance_id, state, get_ident(), QThread.currentThread() is window.thread()))
        original(handle, *state)
    window._measurement_state_changed = record
    try:
        thread.start()
        deadline = time.monotonic() + 3
        while not calls and time.monotonic() < deadline:
            app.processEvents()
        assert calls == [("repeated_rapid_scan:single", (True, "native saving"), gui_ident, True)]
        assert window.measurement_lifecycle.states["repeated_rapid_scan:single"] == {
            "busy": True, "state": "native saving"}
    finally:
        source.deleteLater()
        thread.quit()
        assert thread.wait(2000)
        window.deleteLater()
