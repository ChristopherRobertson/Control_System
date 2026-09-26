"""Real shell navigation and destinations, using isolated ownership and settings."""
import os
import json
from datetime import date
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings

from control_app import paths
from control_app.measurement_host.naming import EXPERIMENT_ORDER, tab_title
from control_app.measurement_host.ownership import HardwareCoordinator
from control_app.ui import main_window
from control_app.ui.contracts import blocked_handler


class LocalDate(date):
    current = date(2026, 9, 14)

    @classmethod
    def today(cls):
        return cls.current


@pytest.fixture
def shell(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(paths, "RUN_ROOT", tmp_path / "runs")
    monkeypatch.setattr(paths, "date", LocalDate)
    monkeypatch.setattr(LocalDate, "current", date(2026, 9, 14))
    monkeypatch.setattr(paths, "_selected_save_location", None)
    preferences = QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)
    # An obsolete global destination and a remembered Dual setting cannot
    # override the newly requested default startup policy.
    preferences.setValue("save_location", str(tmp_path / "old shared root"))
    preferences.setValue("detector_mode", "dual")
    monkeypatch.setattr(main_window, "QSettings", lambda *args: preferences)
    coordinator = HardwareCoordinator(tmp_path / "owner.lock")
    handler = blocked_handler("No hardware in shell tests")
    handler.coordinator = coordinator
    published = []
    handler.output_location_changed = published.append
    window = main_window.ControlSystemMainWindow(handler, persist_settings=True)
    app.processEvents()
    yield window, coordinator, preferences, published
    window._save_timer.stop()
    window.deleteLater()
    app.processEvents()


def visible_titles(window):
    return [window.tabs.tabText(i) for i in range(window.tabs.count()) if window.tabs.isTabVisible(i)]


def test_uniform_experiment_sections_and_bottom_actions(shell):
    from PySide6.QtWidgets import QGroupBox, QCheckBox
    window = shell[0]
    expected = ["Acquire Blank", "Load Blank", "Acquire Sample (Pump Off)",
                "Load Sample (Unpumped)", "Start Acquisition", "Abort Acquisition", "New Run"]
    geometry = {}
    for handle in window.measurement_lifecycle.handles:
        panel = handle.widget
        assert [button.text() for button in panel.standard_actions] == expected
        assert len({button.parentWidget() for button in panel.standard_actions}) == 1
        assert panel.instructions_group.title() == "Instructions and Experiment Summary"
        if handle.instance_id.endswith(":dual"):
            assert not panel.standard_actions[0].isEnabled()
            assert not panel.standard_actions[1].isEnabled()
        for group in panel.findChildren(QGroupBox):
            if group.title() in ("MIRcat Settings", "Nd:YAG + OPO Settings", "HF2LI Settings"):
                size = (group.minimumWidth(), group.maximumWidth(), group.minimumHeight(), group.maximumHeight())
                assert geometry.setdefault(group.title(), size) == size
        assert all(check.isHidden() for check in panel.findChildren(QCheckBox) if "review" in check.text().lower())


def handle(window, instance_id):
    return next(item for item in window.measurement_lifecycle.handles if item.instance_id == instance_id)


def select(window, instance_id):
    item = handle(window, instance_id)
    window.tabs.setCurrentWidget(item.widget)
    return item


def test_exact_order_and_modes_retain_page_state_and_device_access(shell):
    window, coordinator, _, _ = shell
    assert window.registration_issues == ()
    assert window.detector_mode.currentText() == "Single"
    assert window.tabs.currentWidget() is handle(window, "steady_state_slow_scan:single").widget
    tail = ["MIRcat", "T660-1", "Nd:YAG", "OPO Iris", "Plotter"]
    for mode in ("single", "dual"):
        window.set_detector_mode(mode)
        assert visible_titles(window) == [tab_title(key, mode) for key in EXPERIMENT_ORDER] + tail
    single = select(window, "steady_state_slow_scan:single").widget
    single.settings_widget.plan_label.setText("single sample")
    window.set_detector_mode("dual")
    dual = window.tabs.currentWidget()
    dual.settings_widget.plan_label.setText("dual sample")
    window.set_detector_mode("single")
    assert window.tabs.currentWidget() is single
    assert single.settings_widget.plan_label.text() == "single sample"
    window.set_detector_mode("dual")
    assert window.tabs.currentWidget() is dual
    assert dual.settings_widget.plan_label.text() == "dual sample"
    window.tabs.setCurrentWidget(window.mircat_widget)
    window.set_detector_mode("single")
    assert window.tabs.currentWidget() is window.mircat_widget
    assert len(window.measurement_lifecycle.handles) == 12
    assert window.tabs.count() == 17
    assert not coordinator.lock_path.exists()


def test_restart_resets_experiment_inputs_and_ignores_old_disk_preferences(shell):
    from PySide6.QtWidgets import QLineEdit
    window, _, preferences, _ = shell
    defaults = {}
    for mode in ("single", "dual"):
        instance = f"steady_state_slow_scan:{mode}"
        editor = handle(window, instance).widget.settings_widget
        defaults[mode] = editor.read_settings()
        editor.plan_label.setText("Previous launch sample")
        editor.scan_speed.setValue(123)
        editor.fields["repetition_rate_hz"].setText("1000")
        saved = editor.read_settings()
        preferences.setValue(f"measurements/steady_state_slow_scan/{mode}/v1/settings", json.dumps(saved))
    phase_defaults = []
    for mode, widget in (("single", window.phase_scan_widget), ("dual", window.dual_detector_phase_scan_widget)):
        phase_defaults.append({key: control.text() if isinstance(control, QLineEdit) else control.value()
                               for key, control in widget.inputs.items()})
        old = json.dumps({"inputs": {key: "Previous launch label" if isinstance(control, QLineEdit) else control.maximum()
                                     for key, control in widget.inputs.items()}})
        preferences.setValue(widget.preference_key, old)
        preferences.setValue(f"measurements/phase_scan/{mode}/v1/settings", old)
    preferences.sync()
    original_disk_values = {key: preferences.value(key) for key in preferences.allKeys()}
    restarted = main_window.ControlSystemMainWindow(persist_settings=True)
    try:
        assert restarted.registration_issues == ()
        for mode in ("single", "dual"):
            editor = handle(restarted, f"steady_state_slow_scan:{mode}").widget.settings_widget
            assert editor.read_settings() == defaults[mode]
        for widget, expected in zip((restarted.phase_scan_widget, restarted.dual_detector_phase_scan_widget), phase_defaults):
            assert {key: control.text() if isinstance(control, QLineEdit) else control.value()
                               for key, control in widget.inputs.items()} == expected
            assert widget._overrides == {}
        # Every experiment gets a launch-local preference namespace, including
        # modules that persist edits only when planning or starting a run.
        for item in window.measurement_lifecycle.handles:
            experiment, mode = item.instance_id.rsplit(":", 1)
            old_context = window.measurement_context_factory.for_experiment(experiment).for_mode(mode)
            new_context = restarted.measurement_context_factory.for_experiment(experiment).for_mode(mode)
            old_context.preferences.setValue("restart_probe", "previous launch")
            assert new_context.preferences.value("restart_probe") is None
        assert {key: preferences.value(key) for key in preferences.allKeys()} == original_disk_values
    finally:
        restarted._save_timer.stop()
        restarted.deleteLater()


def test_each_tab_uses_its_exact_title_and_unique_frozen_run_folder(shell):
    window, _, _, _ = shell
    for item in window.measurement_lifecycle.handles:
        window.tabs.setCurrentWidget(item.widget)
        expected = paths.RUN_ROOT / "2026-09-14" / item.title
        assert Path(window.save_location.text()) == expected
        window._apply_save_location()
        assert not expected.exists()
        experiment, mode = item.instance_id.rsplit(":", 1)
        context = window.measurement_context_factory.for_experiment(experiment).for_mode(mode)
        operation = context.begin_operation({"sample": "test"}, hardware=False)
        assert operation.save_root == expected
        assert operation.output_path == expected / operation.run_id
        assert not operation.output_path.exists()
    for widget, title in ((window.mircat_widget, "MIRcat"), (window.t660_widget, "T660-1"),
                          (window.ndyag_widget, ""), (window.iris_widget, "OPO Iris"),
                          (window.scan_plotter_widget, "Plotter")):
        window.tabs.setCurrentWidget(widget)
        assert Path(window.save_location.text()) == paths.RUN_ROOT / "2026-09-14" / title
    assert not paths.RUN_ROOT.exists()


def test_applying_custom_destination_and_new_day_stays_lazy(shell, tmp_path, monkeypatch):
    window, _, _, _ = shell
    target = tmp_path / "custom" / "new experiment"
    window.save_location.setText(str(target))
    window.save_location.setModified(True)
    window._apply_save_location()
    assert not target.exists()
    monkeypatch.setattr(LocalDate, "current", date(2026, 9, 15))
    window.set_detector_mode("dual")
    window._apply_save_location()
    assert not paths.RUN_ROOT.exists()


def test_mode_and_midnight_switches_do_not_retarget_active_work(shell):
    window, coordinator, _, published = shell
    item = select(window, "steady_state_slow_scan:single")
    context = item.widget.context
    operation = context.begin_operation({"sample": "original"}, hardware=True)
    item.widget._busy = True
    original = operation.save_root
    published.clear()
    try:
        LocalDate.current = date(2026, 9, 15)
        window.set_detector_mode("dual")
        window._update_save_enabled()
        assert Path(window.save_location.text()) == paths.RUN_ROOT / "2026-09-15" / "DD Slow Scan"
        assert operation.save_root == original
        assert operation.output_path.parent == original
        assert paths.get_save_location() == original
        assert published == []
        assert not window.save_location.isEnabled()
        assert any(item.title in reason for reason in window._close_blockers())
    finally:
        item.widget._busy = False
        coordinator.release(operation.ownership, safe_verified=True)
    window._update_save_enabled()
    assert paths.get_save_location() == paths.RUN_ROOT / "2026-09-15" / "DD Slow Scan"
    assert context.begin_operation({}).save_root == paths.RUN_ROOT / "2026-09-15" / "Slow Scan"


def test_custom_destinations_are_per_tab_and_survive_restart(shell, tmp_path):
    window, _, preferences, published = shell
    target = tmp_path / "custom single"
    window.save_location.setText(str(target))
    window._apply_save_location()
    assert not target.exists()
    assert window.save_location_status.text() == ""
    assert Path(window.save_location.text()) == target
    assert published[-1] == target
    window.set_detector_mode("dual")
    assert Path(window.save_location.text()) == paths.RUN_ROOT / "2026-09-14" / "DD Slow Scan"
    window.set_detector_mode("single")
    assert Path(window.save_location.text()) == target
    assert preferences.value("tab_save_locations/v1") == {"steady_state_slow_scan:single": str(target)}
    restarted = main_window.ControlSystemMainWindow(window.command_handler, persist_settings=True)
    try:
        assert restarted.detector_mode.currentData() == "single"
        assert Path(restarted.save_location.text()) == target
    finally:
        restarted._save_timer.stop()
        restarted.deleteLater()


def test_restored_dated_destination_uses_today_and_rolls_after_midnight(shell):
    window, coordinator, preferences, _ = shell
    stale = paths.RUN_ROOT / "2026-09-01" / "Slow Scan"
    preferences.setValue("tab_save_locations/v1", {"steady_state_slow_scan:single": str(stale)})
    restarted = main_window.ControlSystemMainWindow(window.command_handler, persist_settings=True)
    try:
        today = paths.RUN_ROOT / "2026-09-14" / "Slow Scan"
        assert Path(restarted.save_location.text()) == today
        item = handle(restarted, "steady_state_slow_scan:single")
        operation = item.widget.context.begin_operation({})
        assert operation.save_root == today
        LocalDate.current = date(2026, 9, 15)
        restarted._update_save_enabled()
        tomorrow = paths.RUN_ROOT / "2026-09-15" / "Slow Scan"
        assert Path(restarted.save_location.text()) == tomorrow
        assert item.widget.context.begin_operation({}).save_root == tomorrow
        assert operation.output_path.parent == today
        assert not stale.exists() and not tomorrow.exists()
    finally:
        restarted._save_timer.stop()
        restarted.deleteLater()


def test_manually_selected_past_date_rolls_and_preserves_custom_suffix(shell, tmp_path):
    window = shell[0]
    selected = tmp_path / "custom" / "2026-09-01" / "trial group"
    window.save_location.setText(str(selected))
    window._apply_save_location()
    expected = tmp_path / "custom" / "2026-09-14" / "trial group"
    assert Path(window.save_location.text()) == expected
    assert not expected.exists()


def test_manual_token_pins_legacy_destination_even_without_a_running_widget(shell):
    window, coordinator, _, published = shell
    window.tabs.setCurrentWidget(window.mircat_widget)
    original = paths.get_save_location()
    token = coordinator.acquire("manual:mircat", purpose="simulated retained session")
    published.clear()
    try:
        select(window, "fixed_wavenumber_kinetics:dual")
        window._update_save_enabled()
        assert Path(window.save_location.text()).name == "DD Fixed Wavenumber"
        assert paths.get_save_location() == original
        assert published == []
        assert not window.save_location.isEnabled()
    finally:
        coordinator.release(token, safe_verified=True)


def test_edited_path_is_committed_to_departing_tab(shell, tmp_path):
    window, _, _, _ = shell
    target = tmp_path / "edited single"
    window.save_location.setText(str(target))
    window.save_location.setModified(True)
    window.set_detector_mode("dual")
    assert Path(window.save_location.text()).name == "DD Slow Scan"
    window.set_detector_mode("single")
    assert Path(window.save_location.text()) == target


def test_failed_edit_remains_reviewable_after_mode_switch(shell, tmp_path, monkeypatch):
    window, _, _, _ = shell
    original = paths.get_save_location()
    target = tmp_path / "unwritable"
    real_set_location = main_window.set_save_location

    def reject_explicit(value, *, create=False):
        if Path(value) == target:
            raise PermissionError("Injected unwritable folder")
        return real_set_location(value, create=create)

    monkeypatch.setattr(main_window, "set_save_location", reject_explicit)
    window.save_location.setText(str(target))
    window.save_location.setModified(True)
    window.set_detector_mode("dual")
    assert Path(window.save_location.text()).name == "DD Slow Scan"
    window.set_detector_mode("single")
    assert window.save_location.text() == str(target)
    assert window.save_location.isModified()
    assert "Injected unwritable folder" in window.save_location_status.text()
    assert paths.get_save_location() == original
    assert not target.exists()
    monkeypatch.setattr(main_window, "set_save_location", real_set_location)
    window._apply_save_location()
    assert Path(window.save_location.text()) == target
    assert window.save_location_status.text() == ""


def test_offline_work_does_not_redirect_new_manual_device_output(shell):
    window, coordinator, _, published = shell
    item = select(window, "steady_state_slow_scan:single")
    operation = item.widget.context.begin_operation({}, hardware=False)
    item.widget._busy = True
    try:
        window.tabs.setCurrentWidget(window.mircat_widget)
        expected = paths.default_tab_save_location("MIRcat")
        assert coordinator.snapshot()["state"] == "free"
        assert paths.get_save_location() == expected
        assert published[-1] == expected
        assert operation.output_path.parent.name == "Slow Scan"
        window.tabs.setCurrentWidget(window.ndyag_widget)
        assert paths.get_save_location() == paths.default_save_location()
        assert published[-1] == paths.default_save_location()
        assert operation.output_path.parent.name == "Slow Scan"
    finally:
        item.widget._busy = False


def test_closed_shell_stops_publishing_destinations(shell):
    window, _, _, _ = shell
    assert window._save_timer.isActive()
    window.close()
    assert window.safe_shutdown_completed
    assert not window._save_timer.isActive()
