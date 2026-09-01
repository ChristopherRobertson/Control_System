import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_seven_tab_gui_shell_instantiates_without_hardware():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from control_app.ui.contracts import blocked_handler
    from control_app.ui.main_window import ControlSystemMainWindow

    app = QApplication.instance() or QApplication([])
    window = ControlSystemMainWindow(blocked_handler("automated smoke test; no hardware"), persist_settings=False)
    assert window.windowTitle() == "IR Spectroscope Control System"
    assert window.tabs.count() == 7
    assert window.save_location.objectName() == "save_location"
    assert [window.tabs.tabText(index) for index in range(7)] == [
        "Experiment Builder",
        "Configured Workflows",
        "Phase Scan",
        "MIRcat",
        "T660-2",
        "Nd:YAG",
        "Plotter",
    ]
    window.deleteLater()
    app.processEvents()
