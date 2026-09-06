import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_eight_tab_gui_shell_instantiates_without_hardware():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from control_app.ui.contracts import blocked_handler
    from control_app.ui.main_window import ControlSystemMainWindow

    app = QApplication.instance() or QApplication([])
    window = ControlSystemMainWindow(blocked_handler("automated smoke test; no hardware"), persist_settings=False)
    assert window.windowTitle() == "IR Spectroscope Control System"
    assert window.tabs.count() == 8
    assert window.save_location.objectName() == "save_location"
    assert [window.tabs.tabText(index) for index in range(8)] == [
        "Experiment Builder",
        "Configured Workflows",
        "Phase Scan",
        "MIRcat",
        "T660-1",
        "Nd:YAG",
        "OPO Iris",
        "Plotter",
    ]
    assert window.iris_widget.current_diameter_label.text() == "-- mm"
    assert window.iris_widget.target_diameter.objectName() == "iris_target_diameter"
    window.deleteLater()
    app.processEvents()


def test_iris_tab_refreshes_and_applies_direct_entry_asynchronously():
    import time

    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QPushButton

    from control_app.ui.contracts import WorkflowResult
    from control_app.ui.widgets.iris_widget import IrisWidget

    app = QApplication.instance() or QApplication([])
    commands = []

    def handler(command):
        commands.append(command)
        diameter = float(command.parameters.get("diameter_mm", 7.4))
        return WorkflowResult(
            status="complete",
            message="test readback",
            data={
                "state": {
                    "current_diameter_mm": diameter,
                    "identity": "ELL15 S/N 11500020",
                    "configured_range": "1.00-11.50 mm",
                }
            },
        )

    def wait_for_idle(widget):
        deadline = time.monotonic() + 2
        while widget.command_running() and time.monotonic() < deadline:
            app.processEvents()
        app.processEvents()
        assert not widget.command_running()

    widget = IrisWidget(handler)
    widget.show()
    app.processEvents()
    wait_for_idle(widget)
    assert commands[0].command == "opo_iris.refresh_status"
    assert widget.current_diameter_label.text() == "7.40 mm"

    widget.target_diameter.setText("6.25")
    widget.findChild(QPushButton, "iris_set_diameter").click()
    wait_for_idle(widget)
    assert commands[-1].parameters["diameter_mm"] == "6.25"
    assert widget.current_diameter_label.text() == "6.25 mm"
    widget.close()
    widget.deleteLater()
    app.processEvents()
