#!/usr/bin/env python3
"""Exercise asynchronous window shutdown with isolated handlers, never devices."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import _common  # noqa: F401
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from control_app import paths
from control_app.measurement_host.ownership import HardwareCoordinator
from control_app.ui.contracts import WorkflowResult, blocked_handler
from control_app.ui.main_window import ControlSystemMainWindow


def main() -> int:
    app = QApplication.instance() or QApplication([])
    previous_root, previous_selection = paths.RUN_ROOT, paths._selected_save_location
    try:
        with TemporaryDirectory(prefix="control-close-check-") as folder:
            paths.RUN_ROOT = Path(folder) / "runs"
            for outcome in ("exception", "failed", "complete"):
                handler = blocked_handler("Shutdown regression; no hardware")
                handler.coordinator = HardwareCoordinator(Path(folder) / (outcome + ".lock"))
                def shutdown(*, reason, expected=outcome):
                    if expected == "exception":
                        raise RuntimeError("Injected shutdown failure")
                    return WorkflowResult(expected, "Injected shutdown result")
                handler.ui_safe_shutdown = shutdown
                window = ControlSystemMainWindow(handler, module_discovery=())
                errors, completed = [], []
                window._show_close_error = lambda *args: errors.append(args)
                window.safe_shutdown_completed_callback = lambda: completed.append(True)
                try:
                    window.show()
                    window.close()
                    deadline = time.monotonic() + 3
                    while window._shutdown_worker is not None and time.monotonic() < deadline:
                        app.processEvents()
                        time.sleep(.002)
                    assert window._shutdown_worker is None
                    assert window.safe_shutdown_completed == (outcome == "complete")
                    assert bool(completed) == (outcome == "complete")
                    assert bool(errors) == (outcome != "complete")
                    assert window.isVisible() == (outcome != "complete")
                finally:
                    window._save_timer.stop()
                    window.deleteLater()
                    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    finally:
        paths.RUN_ROOT, paths._selected_save_location = previous_root, previous_selection
    print("PASS asynchronous UI close is exception-safe and retains failed shutdowns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
