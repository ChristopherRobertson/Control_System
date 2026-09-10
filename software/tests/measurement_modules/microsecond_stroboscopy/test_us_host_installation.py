"""Production module in the unmodified host shell, with no connected devices."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication


def test_us_actual_host_shell_loads_only_pair_and_keeps_phase_scan():
    from control_app.measurement_modules.microsecond_stroboscopy.registration import DESCRIPTOR
    from control_app.ui.main_window import ControlSystemMainWindow
    app = QApplication.instance() or QApplication([])
    window = ControlSystemMainWindow(module_discovery=(DESCRIPTOR,))
    try:
        titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
        assert titles[:4] == ["Phase Scan", "Dual-Detector Phase Scan", "Microsecond Stroboscopy", "Dual-Detector Microsecond Stroboscopy"]
        handles = window.measurement_lifecycle.handles
        us = [h for h in handles if h.instance_id.startswith("microsecond_stroboscopy:")]
        assert len(us) == 2 and us[0].widget.adapter is not us[1].widget.adapter
        assert not any(h.command_running() for h in us)
        assert all(not h.close_blockers() for h in us)
        assert not window.measurement_lifecycle.instrument_events
    finally:
        window.deleteLater()
        app.processEvents()
