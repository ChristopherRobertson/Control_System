"""Real application shell integration; the blocked handler prevents hardware."""
import pytest


def test_ns_host_shell_discovers_both_tabs_and_preserves_phase_scan(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from control_app.ui.contracts import blocked_handler
    from control_app.measurement_host.ownership import HardwareCoordinator
    from control_app.ui.main_window import ControlSystemMainWindow
    app = QApplication.instance() or QApplication([])
    handler = blocked_handler("nanosecond integration; no hardware")
    handler.coordinator = HardwareCoordinator(tmp_path / "instrument.lock")
    window = ControlSystemMainWindow(handler, persist_settings=False)
    titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    for title in ("Phase Scan", "DD Phase Scan", "Nanosecond Stroboscopy", "DD Nanosecond Stroboscopy"):
        assert titles.count(title) == 1
    assert titles.index("Nanosecond Stroboscopy") < titles.index("DD Nanosecond Stroboscopy")
    for mode, visible_title, hidden_title in (
        ("single", "Nanosecond Stroboscopy", "DD Nanosecond Stroboscopy"),
        ("dual", "DD Nanosecond Stroboscopy", "Nanosecond Stroboscopy"),
    ):
        window.set_detector_mode(mode)
        visible = [window.tabs.tabText(i) for i in range(window.tabs.count()) if window.tabs.isTabVisible(i)]
        assert visible_title in visible and hidden_title not in visible
    window.close()
    window.deleteLater()
    app.processEvents()
