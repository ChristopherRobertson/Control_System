"""Slow shutdown must not freeze Qt or destroy a running cleanup worker."""
import os
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from control_app import paths
from control_app.measurement_host.ownership import HardwareCoordinator
from control_app.ui.contracts import WorkflowResult, blocked_handler
from control_app.ui.main_window import ControlSystemMainWindow


@pytest.fixture
def close_window(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(paths, "RUN_ROOT", tmp_path / "runs")
    monkeypatch.setattr(paths, "_selected_save_location", None)
    handler = blocked_handler("Shutdown test; no devices")
    handler.coordinator = HardwareCoordinator(tmp_path / "owner.lock")
    window = ControlSystemMainWindow(handler, module_discovery=())
    errors = []
    window._show_close_error = lambda *args: errors.append(args)
    window.show()
    app.processEvents()
    yield app, window, handler, errors
    assert window._shutdown_worker is None
    window._save_timer.stop()
    window.deleteLater()
    app.processEvents()


def spin_until(app, predicate):
    deadline = time.monotonic() + 3
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.002)
    assert predicate()


def test_slow_close_keeps_qt_alive_and_waits_for_native_preservation(close_window, tmp_path):
    app, window, handler, errors = close_window
    entered, release = threading.Event(), threading.Event()
    saved = tmp_path / "preserved.txt"
    calls, pulses, completion = [], [], []
    ui_thread = threading.get_ident()

    def shutdown(*, reason):
        calls.append((reason, threading.get_ident()))
        entered.set()
        assert release.wait(2)
        saved.write_text("native preservation complete")
        return WorkflowResult("complete", "Safe and saved")

    handler.ui_safe_shutdown = shutdown
    window.safe_shutdown_completed_callback = lambda: completion.append((saved.exists(), threading.get_ident()))
    heartbeat = QTimer()
    heartbeat.setInterval(5)
    heartbeat.timeout.connect(lambda: pulses.append(not release.is_set()))
    heartbeat.start()
    watchdog = threading.Timer(.5, release.set)
    watchdog.start()
    try:
        start = time.monotonic()
        window.close()
        returned = time.monotonic() - start
        spin_until(app, entered.is_set)
        assert returned < .25, "closeEvent blocked the GUI on hardware cleanup"
        assert window.isVisible() and not window.safe_shutdown_completed
        assert not window.centralWidget().isEnabled()
        assert not window._save_timer.isActive()
        assert window.live_worker_blockers() and window._close_blockers()
        handler.emergency_stop = lambda **kwargs: pytest.fail("Concurrent shutdown must not run")
        assert window.request_emergency_stop("external_exit").status == "accepted"
        window.close()  # Repeated clicks cannot start concurrent shutdowns.
        spin_until(app, lambda: bool(pulses))
        assert any(pulses)
        release.set()
        spin_until(app, lambda: window.safe_shutdown_completed)
        assert completion == [(True, ui_thread)]
        assert len(calls) == 1 and calls[0][1] != ui_thread
        assert not window.isVisible() and window._shutdown_worker is None
        assert not errors
    finally:
        release.set()
        watchdog.cancel()
        heartbeat.stop()
        spin_until(app, lambda: window._shutdown_worker is None)


@pytest.mark.parametrize("failure", ["exception", "failed", "blocked"])
def test_failed_shutdown_keeps_window_open_and_can_retry(close_window, failure):
    app, window, handler, errors = close_window
    def shutdown(*, reason):
        if failure == "exception":
            raise RuntimeError("Injected cleanup failure")
        return WorkflowResult(failure, "Injected cleanup failure")
    handler.ui_safe_shutdown = shutdown
    window.close()
    spin_until(app, lambda: window._shutdown_worker is None)
    assert window.isVisible() and not window.safe_shutdown_completed
    assert window.centralWidget().isEnabled() and window._save_timer.isActive()
    assert len(errors) == 1 and "Injected cleanup failure" in errors[0][1]
    handler.ui_safe_shutdown = lambda **kwargs: WorkflowResult("complete", "Retried successfully")
    window.close()
    spin_until(app, lambda: window.safe_shutdown_completed)
    assert not window.isVisible()


def test_active_measurement_blocks_close_without_starting_shutdown(close_window, monkeypatch):
    app, window, handler, errors = close_window
    calls = []
    handler.ui_safe_shutdown = lambda **kwargs: calls.append(kwargs)
    monkeypatch.setattr(window.phase_scan_widget, "command_running", lambda: True)
    window.close()
    app.processEvents()
    assert window.isVisible() and window._shutdown_worker is None
    assert window._save_timer.isActive() and calls == []
    assert errors[0][0] == "Close Blocked"


@pytest.mark.parametrize("retry,external", [(False, False), (True, False), (False, True)])
def test_real_app_event_loop_exits_cleanly_in_subprocess(tmp_path, retry, external):
    import subprocess
    import sys
    from pathlib import Path

    script = r'''
import sys, time
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from control_app.ui import app as entrypoint
from control_app.ui.main_window import ControlSystemMainWindow
from control_app.ui.contracts import blocked_handler, WorkflowResult
from control_app.measurement_host.ownership import HardwareCoordinator

handler = blocked_handler("Subprocess test; no hardware")
handler.coordinator = HardwareCoordinator(Path(sys.argv[1]) / "private.lock")
calls = []
def shutdown(**kwargs):
    calls.append(kwargs)
    time.sleep(.08)
    if sys.argv[2] == "True" and len(calls) == 1:
        return WorkflowResult("failed", "Injected failure")
    return WorkflowResult("complete", "Saved and safe")
handler.ui_safe_shutdown = shutdown
class TestWindow(ControlSystemMainWindow):
    def __init__(self, **kwargs):
        kwargs["persist_settings"] = False
        super().__init__(**kwargs)
        self._show_close_error = lambda *_: QTimer.singleShot(0, self.close)
    def show(self):
        super().show()
        QTimer.singleShot(0, self.close)
        if sys.argv[3] == "True":
            QTimer.singleShot(20, QApplication.instance().quit)
        QTimer.singleShot(8000, lambda: QApplication.instance().exit(9))
entrypoint.WorkflowStateMachine = lambda **kwargs: handler
entrypoint.load_config_inventory = lambda **kwargs: None
entrypoint.ControlSystemMainWindow = TestWindow
result = entrypoint.main()
assert result == 0, result
assert len(calls) == (2 if sys.argv[2] == "True" else 1), calls
print("CLEAN_EXIT")
'''
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", CONTROL_SYSTEM_RUN_ROOT=str(tmp_path / "runs"))
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path), str(retry), str(external)],
                            cwd=Path(__file__).resolve().parents[1], env=env,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CLEAN_EXIT" in result.stdout
    assert "QThread: Destroyed" not in result.stderr
