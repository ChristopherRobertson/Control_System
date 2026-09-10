"""Real application shell integration; the blocked handler prevents hardware."""
import pytest


def test_ns_host_shell_discovers_both_tabs_and_preserves_phase_scan(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from control_app.ui.contracts import blocked_handler
    from control_app.ui.main_window import ControlSystemMainWindow
    app = QApplication.instance() or QApplication([])
    window = ControlSystemMainWindow(blocked_handler("nanosecond integration; no hardware"), persist_settings=False)
    titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    for title in ("Phase Scan", "Dual-Detector Phase Scan", "Nanosecond Stroboscopy", "Dual-Detector Nanosecond Stroboscopy"):
        assert titles.count(title) == 1
    assert titles.index("Nanosecond Stroboscopy") < titles.index("Dual-Detector Nanosecond Stroboscopy")
    window.close()
    app.processEvents()
