"""Production module in the unmodified host shell, with no connected devices."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication


def test_us_actual_host_shell_loads_only_pair_and_keeps_phase_scan(tmp_path):
    from control_app.measurement_modules.microsecond_stroboscopy.registration import DESCRIPTOR
    from control_app.ui.main_window import ControlSystemMainWindow
    from control_app.ui.contracts import blocked_handler
    from control_app.measurement_host.ownership import HardwareCoordinator
    app = QApplication.instance() or QApplication([])
    handler = blocked_handler("microsecond integration; no hardware")
    handler.coordinator = HardwareCoordinator(tmp_path / "instrument.lock")
    window = ControlSystemMainWindow(handler, module_discovery=(DESCRIPTOR,))
    try:
        for mode, expected in (
            ("single", ["Microsecond Stroboscopy", "Phase Scan"]),
            ("dual", ["DD Microsecond Stroboscopy", "DD Phase Scan"]),
        ):
            window.set_detector_mode(mode)
            titles = [window.tabs.tabText(i) for i in range(window.tabs.count()) if window.tabs.isTabVisible(i)]
            assert titles[:2] == expected
        handles = window.measurement_lifecycle.handles
        us = [h for h in handles if h.instance_id.startswith("microsecond_stroboscopy:")]
        assert len(us) == 2 and us[0].widget.adapter is not us[1].widget.adapter
        assert not any(h.command_running() for h in us)
        assert all(not h.close_blockers() for h in us)
        assert not window.measurement_lifecycle.instrument_events
    finally:
        window.deleteLater()
        app.processEvents()
