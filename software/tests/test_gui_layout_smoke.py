import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_six_tab_gui_shell_instantiates_without_hardware():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from control_app.ui.contracts import blocked_handler
    from control_app.ui.main_window import ControlSystemMainWindow

    app = QApplication.instance() or QApplication([])
    window = ControlSystemMainWindow(blocked_handler("automated smoke test; no hardware"))
    assert window.windowTitle() == "IR Spectroscope Control System"
    assert window.centralWidget().count() == 6
    assert [window.centralWidget().tabText(index) for index in range(6)] == [
        "Experiment Builder",
        "Configured Workflows",
        "MIRcat",
        "T660-2",
        "Nd:YAG",
        "Plotter",
    ]
    window.deleteLater()
    app.processEvents()
