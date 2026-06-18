"""Entrypoint for the Qt desktop control interface."""

from __future__ import annotations

import sys

from control_app.config_loader import load_config_inventory
from control_app.ui.main_window import ControlSystemMainWindow
from control_app.workflows.mux_widget_commands import (
    build_mux_default_routes,
    build_mux_route_labels,
    build_mux_route_options,
)
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
    )
    window = ControlSystemMainWindow(
        command_handler=handler,
        mux_route_options=build_mux_route_options(inventory),
        mux_route_labels=build_mux_route_labels(inventory),
        mux_default_routes=build_mux_default_routes(inventory),
    )
    window.resize(1100, 780)
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
