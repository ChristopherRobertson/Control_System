"""Drive app.main's real Qt shutdown timers with synthetic workers and no devices."""
from __future__ import annotations

import os
import signal
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6 import QtWidgets
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QApplication, QWidget

from control_app.measurement_host.contracts import TabHandle
from control_app.measurement_host.lifecycle import MeasurementLifecycle
from control_app.measurement_host.ownership import HardwareCoordinator
from control_app.ui.contracts import WorkflowResult
from control_app.ui.main_window import ControlSystemMainWindow


class _SyntheticTab(QWidget):
    state_changed = Signal(bool)

    def __init__(self, instance_id, parent):
        super().__init__(parent)
        self.instance_id = instance_id
        self.busy = False
        self.aborts = []

    def handle(self):
        return TabHandle(self.instance_id, self.instance_id, self,
                         lambda: self.busy, lambda: ("Native saving",) if self.busy else (),
                         self.aborts.append, lambda path: None, lambda change: None, self.state_changed)


class _AppFacade:
    """Use the actual event loop, retaining only this main invocation's callbacks."""

    def __init__(self, real_app, events):
        self.real_app = real_app
        self.events = events
        self.callbacks = []
        self.aboutToQuit = SimpleNamespace(connect=self._connect)

    def _connect(self, callback):
        self.callbacks.append(callback)
        self.real_app.aboutToQuit.connect(callback)

    def exec(self):
        return self.real_app.exec()

    def quit(self):
        self.events.append(("app_requested_quit", None))
        self.real_app.quit()


def _run_main(monkeypatch, tmp_path, *, owner_id, external_quit=False, safe_result=True):
    """No real handler/service is constructed; only the production Qt routing runs."""
    from control_app.ui import app as entrypoint

    real_app = QApplication.instance() or QApplication([])
    prior_quit_policy = real_app.quitOnLastWindowClosed()
    real_app.setQuitOnLastWindowClosed(False)
    events, signal_handlers, exit_callbacks = [], {}, []
    facade = _AppFacade(real_app, events)
    coordinator = HardwareCoordinator(tmp_path / "app_lifecycle.lock")
    offline_id = "fixed_wavenumber_kinetics:dual"
    tab_ids = ("phase_scan:single", "phase_scan:dual", "nanosecond_stroboscopy:single", offline_id)
    window_ref = []

    class SyntheticHandler:
        def __init__(self):
            self.coordinator = coordinator

        def emergency_stop(self, *, reason):
            window = window_ref[0]
            events.append(("emergency", reason))
            if window.live_worker_blockers():
                return WorkflowResult("accepted", "Owner cancellation requested; saving still runs")
            events.append(("final_safety_check", reason))
            return WorkflowResult("complete" if safe_result else "failed",
                                  "Verified safe after native saving" if safe_result else "Restoration unverified")

    handler = SyntheticHandler()

    class SyntheticWindow(QWidget):
        # Exercise the actual generic shell routing from the actual app main.
        request_emergency_stop = ControlSystemMainWindow.request_emergency_stop
        live_worker_blockers = ControlSystemMainWindow.live_worker_blockers

        def __init__(self, *, command_handler, persist_settings, connect_devices_on_startup):
            super().__init__()
            assert command_handler is handler and persist_settings
            assert connect_devices_on_startup
            window_ref.append(self)
            self.command_handler = handler
            self.measurement_lifecycle = MeasurementLifecycle(coordinator)
            self._recovery_worker = None
            self.mircat_widget = self.t660_widget = self.ndyag_widget = self.iris_widget = (
                SimpleNamespace(command_running=lambda: False))
            self.workers = {identity: _SyntheticTab(identity, self) for identity in tab_ids}
            for tab in self.workers.values():
                self.measurement_lifecycle.register(tab.handle())
            self.workers[owner_id].busy = True
            self.workers[offline_id].busy = True
            self.token = coordinator.acquire(owner_id, purpose="simulated app shutdown test")
            self.close_errors = []
            self.watchdog = QTimer(self)
            self.watchdog.setSingleShot(True)
            self.watchdog.timeout.connect(self._timeout)

        def show(self):
            # main() has installed signal handlers by the time this event runs.
            QTimer.singleShot(0, self._request_exit)
            self.watchdog.start(2000)

        def _request_exit(self):
            QTimer.singleShot(40, self._finish_hardware)
            QTimer.singleShot(160, self._finish_offline)
            if external_quit:
                events.append(("external_quit", None))
                real_app.quit()
            else:
                signal_handlers[signal.SIGINT](signal.SIGINT, None)
                # Repeated signals while exit is pending must not duplicate stop.
                signal_handlers[signal.SIGINT](signal.SIGINT, None)

        def _finish_hardware(self):
            events.append(("native_records_saved", owner_id))
            coordinator.release(self.token, safe_verified=True, preservation_verified=True)
            self.workers[owner_id].busy = False

        def _finish_offline(self):
            events.append(("offline_results_saved", offline_id))
            self.workers[offline_id].busy = False

        def _show_close_error(self, title, message):
            self.close_errors.append((title, message))
            events.append(("shutdown_needs_attention", message))
            # Failure must leave app.main open. End only this test's event loop
            # after recording that the application did not request a quit.
            QTimer.singleShot(0, self._test_only_quit)

        def _test_only_quit(self):
            events.append(("test_only_quit", None))
            real_app.quit()

        def _timeout(self):
            events.append(("watchdog_timeout", None))
            for worker in self.workers.values():
                worker.busy = False
            real_app.quit()

    def create_handler(**kwargs):
        assert kwargs["hardware_access"] is True  # The real handler remains replaced.
        return handler

    monkeypatch.setattr(QtWidgets, "QApplication", lambda argv: facade)
    monkeypatch.setattr(entrypoint, "WorkflowStateMachine", create_handler)
    monkeypatch.setattr(entrypoint, "ControlSystemMainWindow", SyntheticWindow)
    monkeypatch.setattr(entrypoint, "load_config_inventory", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(entrypoint.sys, "argv", ["simulated-app-lifecycle"])
    monkeypatch.setattr(entrypoint.signal, "signal", lambda number, callback: signal_handlers.__setitem__(number, callback))
    monkeypatch.setattr(entrypoint.atexit, "register", exit_callbacks.append)
    try:
        assert entrypoint.main() == 0
        window = window_ref[0]
        window.watchdog.stop()
        before_atexit = len(events)
        assert len(exit_callbacks) == 1
        exit_callbacks[0]()
        after_exit_events = events[before_atexit:]
        assert not any(name == "watchdog_timeout" for name, _ in events)
        assert coordinator.snapshot()["state"] == "free"
        return SimpleNamespace(events=events, after_exit_events=after_exit_events,
                               aborts={key: list(worker.aborts) for key, worker in window.workers.items()},
                               close_errors=list(window.close_errors), offline_id=offline_id)
    finally:
        for callback in facade.callbacks:
            real_app.aboutToQuit.disconnect(callback)
        for window in window_ref:
            window.watchdog.stop()
            window.deleteLater()
        real_app.processEvents()
        real_app.setQuitOnLastWindowClosed(prior_quit_policy)


@pytest.mark.parametrize("owner_id", ["phase_scan:single", "phase_scan:dual", "nanosecond_stroboscopy:single"])
def test_signal_shutdown_waits_for_native_and_offline_saving(monkeypatch, tmp_path, owner_id):
    result = _run_main(monkeypatch, tmp_path, owner_id=owner_id)
    assert result.aborts[owner_id] == [f"signal_{signal.SIGINT}"]
    assert all(not reasons for identity, reasons in result.aborts.items() if identity != owner_id)
    names = [name for name, _ in result.events]
    assert names.index("native_records_saved") < names.index("offline_results_saved") < names.index("final_safety_check")
    assert names.index("final_safety_check") < names.index("app_requested_quit")
    assert [reason for name, reason in result.events if name == "emergency"] == [
        f"signal_{signal.SIGINT}", "signal_cleanup_completed"]
    assert result.close_errors == [] and result.after_exit_events == []


def test_external_qt_quit_drains_workers_before_final_safe_check(monkeypatch, tmp_path):
    owner_id = "nanosecond_stroboscopy:single"
    result = _run_main(monkeypatch, tmp_path, owner_id=owner_id, external_quit=True)
    assert result.aborts[owner_id] == ["qt_about_to_quit"]
    assert result.aborts[result.offline_id] == []
    names = [name for name, _ in result.events]
    assert names.index("external_quit") < names.index("native_records_saved")
    assert names.index("offline_results_saved") < names.index("final_safety_check")
    assert [reason for name, reason in result.events if name == "final_safety_check"] == ["qt_workers_drained"]
    assert result.after_exit_events == []  # Successful final verification set the safe flag.


def test_failed_signal_shutdown_does_not_quit_or_mark_safe(monkeypatch, tmp_path):
    result = _run_main(monkeypatch, tmp_path, owner_id="phase_scan:dual", safe_result=False)
    assert result.close_errors == [("Shutdown needs attention", "Restoration unverified")]
    assert result.aborts[result.offline_id] == []
    names = [name for name, _ in result.events]
    assert "app_requested_quit" not in names
    assert names.index("offline_results_saved") < names.index("shutdown_needs_attention") < names.index("test_only_quit")
    # app.main's atexit hook still tries safety cleanup: a failed worker-drained
    # check was not misrepresented as safe completion.
    assert result.after_exit_events == [("emergency", "python_atexit"), ("final_safety_check", "python_atexit")]


def test_connection_banner_collapses_repeated_tab_failures():
    from control_app.ui.main_window import _connection_status_messages
    error = 'T660Error: t660_2: Windows denied access to COM7. Original error: access denied'
    errors = [f'{tab}: Settings unavailable: {error}' for tab in ('nano:dual', 'rapid:single', 'rapid:dual')]
    messages = _connection_status_messages({'t660_2': error}, errors)
    assert len(messages) == 1
    assert 'COM7 access denied' in messages[0]
    assert len(messages[0]) < 120
    assert _connection_status_messages({}, ['unrelated failure']) == ['unrelated failure']
