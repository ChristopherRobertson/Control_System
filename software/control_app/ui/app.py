"""Entrypoint for the Qt desktop control interface."""

from __future__ import annotations

import atexit
import os
import signal
import sys
import traceback
from datetime import UTC, datetime

from control_app.config_loader import load_config_inventory
from control_app.paths import DIAGNOSTIC_ROOT
from control_app.ui.main_window import ControlSystemMainWindow
from control_app.workflows.state_machine import WorkflowStateMachine


def main() -> int:
    """Launch the desktop UI shell."""

    try:
        from PySide6.QtCore import QEventLoop, QTimer
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        raise RuntimeError(
            "PySide6 is required for the desktop UI. Install software/requirements-ui.txt "
            "in the Windows Python environment used for the packaged app."
        ) from exc

    app = QApplication(sys.argv)
    offline = "--offline" in sys.argv
    inventory = load_config_inventory(write_files=False)
    handler = WorkflowStateMachine(
        operator="UI",
        inventory=inventory,
        hardware_access=not offline,
        bundle_id=os.environ.get("CONTROL_SYSTEM_BUNDLE_ID"),
    )
    window = ControlSystemMainWindow(
        command_handler=handler,
        persist_settings=True,
        connect_devices_on_startup=not offline,
    )
    window.resize(1100, 780)
    if "--mircat-scan" in sys.argv:
        window.tabs.setCurrentWidget(window.mircat_widget)
        window.mircat_widget.parameter_tabs.setCurrentIndex(1)
    window.show()
    shutdown_state = {"safe_completed": False, "exit_pending": False, "tearing_down": False}

    def mark_safe_shutdown_completed() -> None:
        shutdown_state["safe_completed"] = True

    window.safe_shutdown_completed_callback = mark_safe_shutdown_completed

    def emergency_stop(reason: str):
        if shutdown_state["safe_completed"]:
            return
        try:
            return window.request_emergency_stop(reason)
        except Exception:  # noqa: BLE001 - emergency-exit hooks must not crash Qt/Python teardown
            _log_emergency_stop_error(reason)

    def finish_requested_exit():
        # The Qt event loop remains alive for queued worker results and native
        # preservation. An unrelated offline worker is waited for, not aborted.
        if window.live_worker_blockers():
            return
        exit_timer.stop()
        result = emergency_stop("signal_cleanup_completed")
        shutdown_state["exit_pending"] = False
        if result is not None and result.status == "complete":
            mark_safe_shutdown_completed()
            app.quit()
        else:
            window._show_close_error("Shutdown needs attention", getattr(result, "message",
                                     "Safe shutdown could not be verified; application remains open."))

    exit_timer = QTimer(window)
    exit_timer.setInterval(100)
    exit_timer.timeout.connect(finish_requested_exit)

    def handle_signal(signum, _frame) -> None:
        if not shutdown_state["exit_pending"]:
            shutdown_state["exit_pending"] = True
            emergency_stop(f"signal_{signum}")
            exit_timer.start()

    def prepare_qt_teardown():
        if shutdown_state["safe_completed"] or shutdown_state["tearing_down"]:
            return
        shutdown_state["tearing_down"] = True
        emergency_stop("qt_about_to_quit")
        # An external QApplication.quit() also must not destroy active QThreads.
        # Keep processing their signals until cleanup/preservation has finished.
        if window.live_worker_blockers():
            drain = QEventLoop()
            poll = QTimer()
            poll.setInterval(100)
            poll.timeout.connect(lambda: drain.quit() if not window.live_worker_blockers() else None)
            poll.start()
            drain.exec()
            poll.stop()
        result = emergency_stop("qt_workers_drained")
        if result is not None and result.status == "complete":
            mark_safe_shutdown_completed()

    app.aboutToQuit.connect(prepare_qt_teardown)
    atexit.register(lambda: emergency_stop("python_atexit"))
    for signal_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, signal_name):
            signal.signal(getattr(signal, signal_name), handle_signal)
    return int(app.exec())


def _log_emergency_stop_error(reason: str) -> None:
    """Record emergency-stop hook failures without raising during process exit."""

    try:
        log_path = DIAGNOSTIC_ROOT / f"{datetime.now().strftime('%Y%m%d')}_ui_shutdown_errors.txt"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(
                f"{datetime.now(UTC).isoformat(timespec='seconds')} emergency_stop "
                f"reason={reason} failed\n"
            )
            handle.write(traceback.format_exc())
            handle.write("\n")
    except Exception:  # noqa: BLE001 - never raise from an emergency-exit logging fallback
        return


if __name__ == "__main__":
    raise SystemExit(main())
