"""Default no-device layout in the real, fully discovered desktop shell.

Segoe UI 9 and genuine validation/status rows reproduce the geometry that an
isolated descriptor or a loaded-data fixture can hide. No settings are changed,
no instrument is constructed, and normal app startup/shutdown is not invoked.
"""
from pathlib import Path
import sys
import time

import pytest


def _settle(app, duration=0.15):
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    app.processEvents()


def _assert_complete_visibility(widget, ancestor, *, label):
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtGui import QRegion

    bounds = QRect(widget.mapTo(ancestor, QPoint(0, 0)), widget.size())
    assert ancestor.isAncestorOf(widget), f"{label} is outside its intended container"
    assert widget.isVisibleTo(ancestor), f"{label} is not visible"
    assert ancestor.rect().contains(bounds), (
        f"{label}: control {bounds.getRect()} exceeds viewport {ancestor.rect().getRect()}"
    )
    clipped = QRegion(widget.rect()) - widget.visibleRegion()
    assert widget.isVisible() and clipped.isEmpty(), (
        f"{label}: actual visible region {widget.visibleRegion().boundingRect().getRect()} "
        f"does not cover the complete control {widget.rect().getRect()}"
    )


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_fixed_point_default_all_tab_shell_keeps_overrides_and_plan_files_visible(
        tmp_path, monkeypatch, mode):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("QT_SCALE_FACTOR", "1")
    monkeypatch.setenv("QT_FONT_DPI", "96")
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QFont, QFontDatabase, QFontInfo
    from PySide6.QtWidgets import QApplication, QPushButton
    from control_app.measurement_host import context, ownership
    from control_app.ui import main_window
    from control_app.ui.contracts import blocked_handler

    font_file = Path("C:/Windows/Fonts/segoeui.ttf")
    if not font_file.is_file():
        pytest.skip("This Windows geometry regression requires the actual Segoe UI font")
    app = QApplication.instance() or QApplication([])
    previous_font = app.font()
    font_id = QFontDatabase.addApplicationFont(str(font_file))
    assert font_id >= 0, "The required Segoe UI font could not be loaded"
    app.setFont(QFont("Segoe UI", 9))
    assert QFontInfo(app.font()).family() == "Segoe UI"
    assert app.font().pointSizeF() == 9
    assert app.platformName() == "offscreen"

    attempts, callback_errors = [], []

    def forbidden(boundary):
        def reject(*_args, **_kwargs):
            attempts.append(boundary)
            raise AssertionError(f"Default offline layout attempted hardware access: {boundary}")
        return reject

    monkeypatch.setattr(ownership.HardwareCoordinator, "acquire", forbidden("HardwareCoordinator.acquire"))
    monkeypatch.setattr(context._ScopedDevices, "create", forbidden("_ScopedDevices.create"))
    monkeypatch.setattr(main_window, "installed_device_factories", forbidden("installed_device_factories"))
    monkeypatch.setattr(sys, "excepthook", lambda kind, value, _traceback: callback_errors.append(f"{kind.__name__}: {value}"))
    lock_path = tmp_path / "instrument.lock"
    handler = blocked_handler("Offline default-shell layout test; no hardware")
    handler.coordinator = ownership.HardwareCoordinator(lock_path)
    window = None
    try:
        # Deliberately use default discovery. No descriptor filtering or module
        # patch can conceal the other tabs' contribution to shell geometry.
        window = main_window.ControlSystemMainWindow(handler, persist_settings=False)
        assert not window.registration_issues, window.registration_issues
        assert window.tabs.count() == 17
        assert window.preferences is None
        handles = tuple(window.measurement_lifecycle.handles)
        handle = next(h for h in handles if h.instance_id == f"fixed_wavenumber_kinetics:{mode}")
        panel = handle.widget
        initial_settings = panel.editor.values()
        assert panel.editor.wavenumber.value() == 0
        assert panel.editor.positions.text() == ""
        assert panel.plan is None and panel.preliminary is None and panel.result is None

        window.resize(1100, 780)
        window.show()
        _settle(app)
        window.tabs.setCurrentWidget(panel)
        _settle(app)
        assert (window.width(), window.height()) == (1100, 780)
        assert panel.editor.values() == initial_settings
        assert window.tabs.currentWidget() is panel

        # These are the real default-state rows, not substituted fixture text.
        assert panel.validation.text().strip()
        assert "wavenumber" in panel.validation.text().casefold()
        assert panel.status.text().startswith("Connected instruments unavailable")
        assert not panel.command_running()
        assert not hasattr(panel, "check_device_button")
        assert not panel.start_button.isEnabled()
        viewport = panel.settings_scroll.viewport()
        # Instructions belong to the right-hand summary, never the controls.
        assert panel.instructions_group.isAncestorOf(panel.validation)
        assert panel.instructions_group.isAncestorOf(panel.status)
        assert not panel.left_panel.isAncestorOf(panel.validation)

        assert panel.advanced_content.isVisible()
        assert not panel.advanced_content.isCheckable()
        override_names = ["probe_rate_hz", "probe_width_ns"]
        roles = ("sample", "reference") if mode == "dual" else ("sample",)
        override_names.extend(f"{role}_{suffix}" for role in roles
                              for suffix in ("rate_sps", "timeconstant_s", "filter_order"))
        for name in override_names:
            editor = panel.editor.fields[name]
            assert editor.placeholderText() == "Automatic"
            expected = panel.editor.MIRCAT_DEFAULTS.get(name)
            assert float(editor.text()) == expected if expected is not None else editor.text() == ""
            panel.settings_scroll.ensureWidgetVisible(editor)
            app.processEvents()
            _assert_complete_visibility(editor, viewport, label=name)
        restore = [button for button in panel.advanced_content.findChildren(QPushButton)
                   if button.isVisibleTo(panel.advanced_content) and "restore" in button.text().casefold() and "auto" in button.text().casefold()]
        assert len(restore) == 1
        for label, control in (("Restore automatic settings", restore[0]),
                               ("Save plan", panel.save_plan_button), ("Load plan", panel.load_plan_button)):
            panel.settings_scroll.ensureWidgetVisible(control)
            app.processEvents()
            _assert_complete_visibility(control, viewport, label=label)

        # Device sections scroll inside the settings pane, as on Phase Scan.
        # The outer workspace and horizontal settings axis never scroll.
        assert panel.settings_scroll.horizontalScrollBar().value() == 0
        assert panel.settings_scroll.horizontalScrollBar().maximum() == 0
        for scrollbar in (window.workspace_scroll.horizontalScrollBar(), window.workspace_scroll.verticalScrollBar()):
            assert scrollbar.value() == 0
            assert scrollbar.maximum() == 0
        assert window.tabs.usesScrollButtons()
        assert not attempts
        assert not callback_errors
        assert not lock_path.exists()
    finally:
        if window is not None:
            # close() invokes production safe-shutdown logic; delete only the
            # inert test widgets and timers, as in the read-only capture harness.
            window.deleteLater()
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()
        app.setFont(previous_font)
        QFontDatabase.removeApplicationFont(font_id)
    assert not attempts
    assert not callback_errors
