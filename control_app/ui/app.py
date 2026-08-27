"""Entrypoint for the Qt desktop control interface."""

from __future__ import annotations

import atexit
import os
import signal
import sys
import traceback
from datetime import UTC, datetime

from control_app.config_loader import load_config_inventory
from control_app.paths import LOG_ROOT
from control_app.ui.main_window import ControlSystemMainWindow
from control_app.workflows.state_machine import WorkflowStateMachine


def main() -> int:
    """Launch the desktop UI shell."""

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        raise RuntimeError(
            "PySide6 is required for the desktop UI. Install requirements-ui.txt "
            "in the Windows Python environment used for the packaged app."
        ) from exc

    app = QApplication(sys.argv)
    inventory = load_config_inventory(write_files=False)
    handler = WorkflowStateMachine(
        operator="UI",
        inventory=inventory,
        hardware_access=True,
        bundle_id=os.environ.get("CONTROL_SYSTEM_BUNDLE_ID"),
    )
    window = ControlSystemMainWindow(
        command_handler=handler,
    )
    window.resize(1100, 780)
    window.show()
    shutdown_state = {"safe_completed": False, "emergency_done": False}

    def mark_safe_shutdown_completed() -> None:
        shutdown_state["safe_completed"] = True

    window.safe_shutdown_completed_callback = mark_safe_shutdown_completed

    def emergency_stop(reason: str) -> None:
        if shutdown_state["emergency_done"] or shutdown_state["safe_completed"]:
            return
        shutdown_state["emergency_done"] = True
        stop = getattr(handler, "emergency_stop", None)
        if callable(stop):
            try:
                stop(reason=reason)
            except Exception:  # noqa: BLE001 - emergency-exit hooks must not crash Qt/Python teardown
                _log_emergency_stop_error(reason)

    def handle_signal(signum, _frame) -> None:
        try:
            emergency_stop(f"signal_{signum}")
        finally:
            app.quit()

    app.aboutToQuit.connect(lambda: emergency_stop("qt_about_to_quit"))
    atexit.register(lambda: emergency_stop("python_atexit"))
    for signal_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, signal_name):
            signal.signal(getattr(signal, signal_name), handle_signal)
    return int(app.exec())


def _log_emergency_stop_error(reason: str) -> None:
    """Record emergency-stop hook failures without raising during process exit."""

    try:
        log_path = LOG_ROOT / f"{datetime.now().strftime('%Y%m%d')}_ui_shutdown_errors.txt"
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
