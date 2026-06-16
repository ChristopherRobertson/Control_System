"""Entrypoint for the Qt desktop control interface."""

from __future__ import annotations

import sys

from control_app.ui.main_window import ControlSystemMainWindow
from control_app.workflows.mircat_widget_commands import MircatWidgetCommandHandler


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
    window = ControlSystemMainWindow(command_handler=MircatWidgetCommandHandler())
    window.resize(900, 720)
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
