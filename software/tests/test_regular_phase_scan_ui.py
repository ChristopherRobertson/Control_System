"""Offscreen regular Phase Scan app interaction, with synthetic devices only."""
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import csv
import json
import os
import time

import numpy as np
import pytest

from control_app.workflows.regular_phase_scan import HF2Capabilities
from control_app.workflows.regular_phase_scan_runner import RegularPhaseScanRunner


@pytest.fixture
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def capabilities():
    return HF2Capabilities(orders=(1, 4), timeconstants_by_order={1: (2e-6, 10e-6, 50e-6), 4: (8.02e-6, 20.1e-6, 49.99e-6)},
                           rates_sps=(230263.15789473685, 115131.57894736843, 57565.78947368421, 28782.894736842107),
                           verified=True, source="simulated UI device")


def supported_choices(combo):
    """The enabled numeric entries a user can choose, excluding Automatic."""
    return {combo.itemData(index) for index in range(combo.count())
            if combo.itemData(index) is not None and combo.model().item(index).isEnabled()}


def test_window_controls_persist_and_invalid_window_has_brief_solution(qt_app, tmp_path):
    from PySide6.QtCore import QSettings
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    prefs = QSettings(str(tmp_path/'window.ini'), QSettings.Format.IniFormat)
    widget = PhaseScanWidget(runner=RegularPhaseScanRunner(lambda: None, capabilities=capabilities()), preferences=prefs)
    try:
        assert not any(key.startswith('acquisition_') for key in widget.inputs)
        widget.inputs['pre_pump_ms'].setValue(2)
        widget.inputs['post_pump_ms'].setValue(8)
        assert widget.plan.total_scans == 402
        assert '−2 to +8 ms' in widget.summary_values['window'].text()
        assert not widget.validation.text()
        assert 'Estimated effective temporal' not in widget.hf2_status.text()
        restored = PhaseScanWidget(runner=RegularPhaseScanRunner(lambda: None, capabilities=capabilities()), preferences=prefs)
        assert restored.settings().pre_pump_ms == 2 and restored.settings().post_pump_ms == 8
        restored.deleteLater()
        widget.inputs['post_pump_ms'].setValue(80)
        assert widget.plan is None
        assert 'Pump repetition rate' in widget.validation.text()
        assert len(widget.validation.text()) < 180
        assert widget.validation.text().count('.') == 1
    finally:
        widget.deleteLater()


def test_high_rate_25us_plan_displays_unmultiplied_capacity(qt_app):
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    rate, tc = 230263.15789473685, .799995886e-6
    caps = HF2Capabilities(orders=(8,), timeconstants_by_order={8: (tc,)}, rates_sps=(rate,), verified=True)
    widget = PhaseScanWidget(runner=RegularPhaseScanRunner(lambda: None, capabilities=caps))
    try:
        widget.inputs['phase_delay_us'].setValue(25)
        assert widget.plan is not None
        assert widget.background_button.isEnabled()
        text = widget.summary_values['capacity'].text()
        assert '154.5 MB estimated · 536.9 MB advisory' in text
        assert '25%' not in text and '4×' not in text
    finally:
        widget.deleteLater()


def wait_for(qt_app, condition):
    deadline = time.monotonic() + 5
    while not condition() and time.monotonic() < deadline:
        time.sleep(.01)
        qt_app.processEvents()
    assert condition()


def test_manual_dropdowns_are_supported_and_dependent(qt_app):
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    caps = capabilities()
    widget = PhaseScanWidget(runner=RegularPhaseScanRunner(lambda: None, capabilities=caps))
    widget.advanced_group.setChecked(True)
    choices = widget.override_inputs
    assert all(not combo.isEditable() for combo in choices.values())
    assert {choices["rate_sps"].itemData(i) for i in range(1, choices["rate_sps"].count())} == set(caps.rates_sps)
    choices["order"].setCurrentIndex(choices["order"].findData(4))
    choices["timeconstant_s"].setCurrentIndex(choices["timeconstant_s"].findData(49.99e-6))
    assert widget.plan.hf2_selection["requested"]["timeconstant_s"] == 49.99e-6
    choices["order"].setCurrentIndex(choices["order"].findData(1))
    assert widget.plan is None  # explicit incompatible override is not rewritten
    invalid = choices["timeconstant_s"]
    assert "unsupported" in invalid.currentText()
    assert invalid.currentData() == 49.99e-6
    assert not invalid.model().item(invalid.currentIndex()).isEnabled()
    assert invalid.itemData(0) is None and invalid.itemText(0) == "Automatic"
    assert invalid.model().item(0).isEnabled()
    assert supported_choices(invalid) == set(caps.timeconstants_by_order[1])
    widget.restore_auto_button.click()
    assert widget.plan is not None and widget._overrides == {}
    assert widget.plan.hf2_selection["mode"] == "automatic"
    widget.deleteLater()


def test_settings_persist_without_restoring_acquisition_authority(qt_app, tmp_path):
    from PySide6.QtCore import QSettings
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    prefs = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    first = PhaseScanWidget(preferences=prefs)
    first.inputs["pump_repetition_rate_hz"].setValue(5)
    first.inputs["phase_delay_us"].setValue(100)
    second = PhaseScanWidget(preferences=prefs)
    assert second.settings().pump_repetition_rate_hz == 5
    assert second.settings().phase_delay_us == 100
    assert not second.start_button.isEnabled()
    assert not second.review_checkbox.isChecked()
    assert second.runner.background is None
    first.deleteLater()
    second.deleteLater()


def test_saved_plan_load_recalculates_and_new_run_clears_session(qt_app, tmp_path):
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    runner = RegularPhaseScanRunner(lambda: None, capabilities=HF2Capabilities(verified=True))
    widget = PhaseScanWidget(runner=runner)
    try:
        widget.inputs['phase_delay_us'].setValue(100)
        payload = widget.plan.to_dict()
        payload['derived']['total_scans'] = 999999  # derived values are not trusted on load
        path = tmp_path/'plan.json'
        path.write_text(json.dumps(payload))
        widget.inputs['phase_delay_us'].setValue(50)
        widget.load_plan(path)
        assert widget.inputs['phase_delay_us'].value() == 100
        assert widget.plan.total_scans == 162
        assert widget.plan.hf2_selection['mode'] == 'automatic'
        widget.show_reconstruction(reconstruction())
        runner.preliminary = {'old': True}
        runner.preliminary_reviewed = True
        runner.last_readback = {'old': True}
        runner.cancel.set()
        widget.new_run_button.click()
        assert runner.preliminary is runner.background is None
        assert not runner.last_readback and not runner.cancel.is_set()
        assert widget.reconstruction.result is None
        assert widget.background_button.isEnabled()
        assert not widget.start_button.isEnabled()
    finally:
        widget.deleteLater()


def test_capacity_warning_allows_plan_and_current_settings_replace_old_readback(qt_app):
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    widget = PhaseScanWidget(runner=RegularPhaseScanRunner(lambda: None, capabilities=HF2Capabilities(verified=True, max_retained_bytes=1_000_000)))
    try:
        widget.actual_settings.setText('Old acquisition readback')
        widget.inputs['post_pump_ms'].setValue(2)
        widget.inputs['phase_delay_us'].setValue(5)
        assert widget.plan is not None and widget.background_button.isEnabled()
        assert widget.validation.text().startswith('Warning:')
        assert 'Old acquisition' not in widget.actual_settings.text()
        assert 'Selected:' in widget.actual_settings.text()
        assert '+2 ms' in widget.summary_values['window'].text()
    finally:
        widget.deleteLater()


def test_mouse_toolbar_returns_from_pan_and_zoom(qt_app):
    from control_app.ui.widgets.phase_scan_surface import PhaseScanReconstructionWidget
    widget = PhaseScanReconstructionWidget()
    widget.set_result(reconstruction())
    try:
        for action in ('pan', 'zoom'):
            widget.toolbar._actions[action].trigger()
            assert widget.toolbar.mode
            widget.select_action.trigger()
            assert not widget.toolbar.mode
            assert not widget.canvas.widgetlock.locked()
        assert widget.time_label.text().startswith('Time:')
        assert widget.spectral_label.text().startswith('Wavenumber:')
        assert not hasattr(widget, 'reset_button') and not hasattr(widget, 'image_button')
    finally:
        widget.deleteLater()


def test_plot_resize_and_subplot_toolbar_have_no_layout_warnings(qt_app):
    import warnings
    from control_app.ui.widgets.phase_scan_surface import PhaseScanReconstructionWidget
    widget = PhaseScanReconstructionWidget()
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            widget.set_result(reconstruction())
            widget.show()
            for width, height in ((1000, 750), (650, 500), (450, 350)):
                widget.resize(width, height)
                qt_app.processEvents()
                widget.figure.subplots_adjust(top=.88)
                widget.canvas.draw()
            assert not [w for w in caught if 'layout' in str(w.message)]
            assert widget.figure.subplotpars.top == .88
    finally:
        widget.deleteLater()


def test_main_window_fits_short_desktop_with_scrollable_forms(qt_app):
    from control_app.ui.main_window import ControlSystemMainWindow
    window = ControlSystemMainWindow()
    try:
        window.resize(1100, 780)
        window.show()
        qt_app.processEvents()
        assert window.minimumSizeHint().height() < 780
        assert window.height() == 780
        assert window.workspace_scroll.widget() is window.tabs
        for index in range(window.tabs.count()):
            window.tabs.setCurrentIndex(index)
            qt_app.processEvents()
            assert window.height() == 780
    finally:
        window.deleteLater()


def test_loading_plan_replaces_stale_blank_error(qt_app, tmp_path):
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    from control_app.workflows.regular_phase_scan_data import experiment_contract
    runner = RegularPhaseScanRunner(lambda: None, capabilities=HF2Capabilities(verified=True))
    widget = PhaseScanWidget(runner=runner)
    try:
        original = widget.plan.to_dict()
        matching = tmp_path/'matching.json'
        matching.write_text(json.dumps(original))
        runner.background = SimpleNamespace(settings=experiment_contract(widget.plan))
        widget.inputs['phase_delay_us'].setValue(100)
        incompatible = tmp_path/'incompatible.json'
        incompatible.write_text(json.dumps(widget.plan.to_dict()))
        widget.load_plan(incompatible)
        assert 'incompatible' in widget.scan_status.text()
        assert not widget.test_button.isEnabled()
        widget.load_plan(matching)
        assert widget.scan_status.text() == 'Plan and selected buffer blank match.'
        assert widget.test_button.isEnabled()
        widget.load_plan(incompatible)
        assert 'incompatible' in widget.scan_status.text()
    finally:
        widget.deleteLater()


def test_plan_load_retries_previously_rejected_blank(qt_app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    from control_app.workflows.regular_phase_scan_data import experiment_contract
    runner = RegularPhaseScanRunner(lambda: None, capabilities=HF2Capabilities(verified=True))
    widget = PhaseScanWidget(runner=runner)
    try:
        matching = tmp_path/'matching.json'
        matching.write_text(json.dumps(widget.plan.to_dict()))
        contract = experiment_contract(widget.plan)
        calls = []
        def load(path, plan):
            calls.append(path)
            if plan.settings.phase_delay_us != 50:
                raise ValueError('phase spacing differs')
            runner.background = SimpleNamespace(settings=contract)
        monkeypatch.setattr(runner, 'load_background', load)
        monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *a: str(tmp_path/'blank'))
        widget.inputs['phase_delay_us'].setValue(100)
        widget._load_background()
        assert 'Blank cannot be used' in widget.scan_status.text()
        widget.load_plan(matching)
        assert len(calls) == 2
        assert widget._pending_background_path is None
        assert widget.scan_status.text() == 'Plan and selected buffer blank match.'
        assert widget.test_button.isEnabled()
    finally:
        widget.deleteLater()


def test_manual_slice_coordinates_link_to_sliders_and_preserve_missing_data(qt_app):
    from control_app.ui.widgets.phase_scan_surface import PhaseScanReconstructionWidget
    widget = PhaseScanReconstructionWidget()
    try:
        assert not widget.time_input.isEnabled()
        widget.set_result(reconstruction())
        widget.time_input.setValue(-.8)
        widget.time_input.editingFinished.emit()
        widget.wavenumber_input.setValue(1910)
        widget.wavenumber_input.editingFinished.emit()
        assert widget.time_slider.value() == widget.spectral_slider.value() == 0
        assert widget.time_input.value() == -1
        assert widget.wavenumber_input.value() == 1900
        assert 'missing / unsupported' in widget.cursor.text()
        assert np.isnan(widget.spectral_axes.lines[0].get_ydata()[0])
        widget.spectral_slider.setValue(2)
        widget.time_slider.setValue(2)
        assert widget.wavenumber_input.value() == 2000
        assert widget.time_input.value() == 1
        widget.mode.setCurrentIndex(1)
        assert widget.time_input.value() == 1
        np.testing.assert_equal(widget.time_axes.lines[0].get_ydata(), reconstruction()['delta_absorbance'][:, 2])
        widget.clear_result()
        assert not widget.time_input.isEnabled() and not widget.wavenumber_input.isEnabled()
    finally:
        widget.deleteLater()


def reconstruction():
    return {"wavenumber_cm1": np.array([1900., 1950., 2000.]), "time_s": np.array([-.001, 0., .001]),
            "absorbance": np.array([[np.nan, .2, .3], [.1, .2, .3], [.15, .25, .35]]),
            "delta_absorbance": np.array([[np.nan, 0., 0.], [0., 0., 0.], [.05, .05, .05]]),
            "baseline_absorbance": np.array([.1, .2, .3]), "pump_reference_bases": ["electrical_sync"]}


def test_reconstruction_mode_linked_slices_cursor_and_reset(qt_app):
    from control_app.ui.widgets.phase_scan_surface import PhaseScanReconstructionWidget
    widget = PhaseScanReconstructionWidget()
    result = reconstruction()
    widget.set_result(result)
    widget.canvas.draw()
    widget.mode.setCurrentIndex(1)
    assert widget.axes.get_ylabel() == "ΔAbsorbance"
    widget.time_slider.setValue(2)
    widget.spectral_slider.setValue(1)
    np.testing.assert_equal(widget.spectral_axes.lines[0].get_ydata(), result["delta_absorbance"][2])
    np.testing.assert_equal(widget.time_axes.lines[0].get_ydata(), result["delta_absorbance"][:, 1])
    event = SimpleNamespace(xdata=-1., inaxes=widget.time_axes)
    widget._cursor_move(event)
    assert "-1 ms" in widget.cursor.text()
    widget.time_slider.setValue(0)
    widget.spectral_slider.setValue(0)
    assert "missing / unsupported" in widget.cursor.text()
    widget.axes.view_init(elev=60, azim=80)
    widget.toolbar._actions["home"].trigger()
    assert widget.axes.elev == 20 and widget.axes.azim == 25
    assert "Electrical sync" in widget.axes.get_zlabel()
    widget.deleteLater()


def test_load_export_image_keeps_missing_values_and_existing_files(qt_app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from control_app.ui.widgets.phase_scan_surface import PhaseScanReconstructionWidget, export_quantitative_csv
    from control_app.workflows.phase_scan_data import save_native
    result = reconstruction()
    path = tmp_path / "run"
    save_native(path / "processed" / "reconstruction.npz", result)
    widget = PhaseScanReconstructionWidget(save_root_provider=lambda: tmp_path)
    widget.load_run(path)
    np.testing.assert_equal(widget.result["absorbance"], result["absorbance"])
    np.testing.assert_equal(widget.result["delta_absorbance"], result["delta_absorbance"])
    target = tmp_path / "quantitative.csv"
    export_quantitative_csv(target, widget.result)
    rows = list(csv.reader(target.open(encoding="utf-8")))
    assert len(rows) == 10 and rows[1][2] == "nan"
    assert "electrical_pump_sync" in rows[0][1]
    assert "unpumped_baseline_absorbance" in rows[0]
    with pytest.raises(FileExistsError):
        export_quantitative_csv(target, widget.result)
    image = tmp_path / "plot.png"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(image), "PNG (*.png)"))
    widget.toolbar._actions["save_figure"].trigger()
    assert image.stat().st_size > 1000
    widget.deleteLater()


def test_saved_run_without_delta_disables_delta_control(qt_app):
    from control_app.ui.widgets.phase_scan_surface import PhaseScanReconstructionWidget
    result = reconstruction()
    del result["delta_absorbance"]
    widget = PhaseScanReconstructionWidget()
    widget.set_result(result)
    assert not widget.mode.model().item(1).isEnabled()
    widget.deleteLater()


@pytest.mark.parametrize("cleanup_fault", [False, True])
def test_capability_refresh_and_abort_restore_ui(qt_app, monkeypatch, tmp_path, cleanup_fault):
    from PySide6.QtWidgets import QMessageBox
    from control_app import paths
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    from test_regular_phase_scan_data import SimulatedAcquirer
    caps = replace(HF2Capabilities(), verified=True)
    calls = []
    class WaitingAcquirer(SimulatedAcquirer):
        def capture_block(self, block, cancel):
            calls.append("capture")
            while not cancel.wait(.01):
                pass
            self.partial_blocks.append({"cancelled_scan": 0})
            raise InterruptedError("simulated abort")
        def close(self):
            calls.append("restored")
            if cleanup_fault:
                raise RuntimeError("simulated restoration failure")
    runner = RegularPhaseScanRunner(WaitingAcquirer, capability_provider=lambda: caps)
    widget = PhaseScanWidget(runner=runner)
    monkeypatch.setattr(paths, "_selected_save_location", tmp_path)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    def wait_for(condition):
        deadline = time.monotonic()+5
        while not condition() and time.monotonic() < deadline:
            time.sleep(.01)
            qt_app.processEvents()
        assert condition()
    assert not widget.background_button.isEnabled()
    widget.refresh_capabilities_button.click()
    wait_for(lambda: not widget.command_running())
    assert widget.background_button.isEnabled()
    widget.background_button.click()
    wait_for(lambda: "capture" in calls)
    assert not widget.inputs["scan_speed_cm1_s"].isEnabled()
    widget.abort_button.click()
    wait_for(lambda: not widget.command_running())
    assert "restored" in calls
    assert widget.inputs["scan_speed_cm1_s"].isEnabled()
    assert not widget.start_button.isEnabled()
    if cleanup_fault:
        assert widget.scan_status.text().startswith("RuntimeError: Safe shutdown or restoration failed:")
        assert "simulated restoration failure" in widget.scan_status.text()
    else:
        assert widget.scan_status.text().startswith("Acquisition stopped. Data: ")
        assert "RuntimeError" not in widget.scan_status.text()
        assert "InterruptedError" not in widget.scan_status.text()
    assert list(tmp_path.rglob("acquisition.npz"))
    widget.deleteLater()


def test_offline_retained_choices_are_immediately_editable_without_device_access(qt_app):
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    runner = RegularPhaseScanRunner()
    widget = PhaseScanWidget(runner=runner)
    widget.advanced_group.setChecked(True)
    retained = HF2Capabilities()
    expected = {
        "order": set(retained.orders),
        "timeconstant_s": {value for group in retained.timeconstants_by_order.values() for value in group},
        "rate_sps": set(retained.rates_sps),
    }
    for key, combo in widget.override_inputs.items():
        assert combo.isEnabled() and not combo.isEditable()
        assert supported_choices(combo) == expected[key]
        assert combo.model().item(combo.findData(None)).isEnabled()
        combo.setCurrentIndex(combo.findData(next(iter(expected[key]))))
        assert widget._overrides[key] in expected[key]
    assert widget.plan is not None and not widget.plan.hf2_selection["capability_verified"]
    assert runner.capabilities is None
    assert not widget.background_button.isEnabled()
    assert not widget.refresh_capabilities_button.isEnabled()
    widget.deleteLater()


def test_show_checks_automatically_but_construction_does_not_and_pending_menus_work(qt_app):
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    entered, release = Event(), Event()
    calls = []
    def provider():
        calls.append("check")
        entered.set()
        assert release.wait(5), "test must release the simulated capability check"
        return capabilities()
    def never_acquire():
        pytest.fail("Showing the phase-scan tab must not construct an acquisition device")
    runner = RegularPhaseScanRunner(never_acquire, capability_provider=provider)
    widget = PhaseScanWidget(runner=runner)
    try:
        assert calls == [] and not widget.command_running()
        widget.advanced_group.setChecked(True)
        widget.show()
        wait_for(qt_app, entered.is_set)
        assert calls == ["check"] and widget.command_running()
        assert all(control.isEnabled() for control in widget.inputs.values())
        assert all(combo.isEnabled() and supported_choices(combo) for combo in widget.override_inputs.values())
        assert not widget.background_button.isEnabled()
        widget.inputs["pump_repetition_rate_hz"].setValue(5)
        order = widget.override_inputs["order"]
        order.setCurrentIndex(order.findData(4))
        assert widget._overrides["order"] == 4
        release.set()
        wait_for(qt_app, lambda: not widget.command_running())
        assert runner.capabilities.verified
        assert widget.settings().pump_repetition_rate_hz == 5
        assert widget.plan.hf2_selection["requested"]["order"] == 4
        assert widget.background_button.isEnabled()
        widget.hide()
        widget.show()
        qt_app.processEvents()
        assert calls == ["check"]  # a successful check is not repeated on every show
    finally:
        release.set()
        wait_for(qt_app, lambda: not widget.command_running())
        widget.close()
        widget.deleteLater()


def test_successful_device_choices_are_cached_and_reopened_without_verification(qt_app, tmp_path):
    from PySide6.QtCore import QSettings
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    caps = replace(capabilities(), readback_records=({"simulated_discovery_record": True},))
    prefs = QSettings(str(tmp_path / "cached_choices.ini"), QSettings.Format.IniFormat)
    checked = []
    first_runner = RegularPhaseScanRunner(lambda: None, capability_provider=lambda: caps)
    first = PhaseScanWidget(runner=first_runner, preferences=prefs)
    try:
        first.refresh_capabilities_button.click()
        wait_for(qt_app, lambda: not first.command_running())
        first.advanced_group.setChecked(True)
        first.override_inputs["order"].setCurrentIndex(first.override_inputs["order"].findData(4))
        first.override_inputs["timeconstant_s"].setCurrentIndex(first.override_inputs["timeconstant_s"].findData(49.99e-6))
        cached = json.loads(str(prefs.value("regular_phase_scan_hf2_choices")))
        assert not cached["verified"]
        assert cached["orders"] == list(caps.orders)
        assert cached["readback_records"] == []
        second_runner = RegularPhaseScanRunner(lambda: None, capability_provider=lambda: checked.append("check") or caps)
        second = PhaseScanWidget(runner=second_runner, preferences=prefs)
        try:
            assert checked == []  # restoring the cache does not access hardware
            assert second_runner.capabilities is not None and not second_runner.capabilities.verified
            assert second_runner.capabilities.source == caps.source
            assert supported_choices(second.override_inputs["rate_sps"]) == set(caps.rates_sps)
            assert supported_choices(second.override_inputs["timeconstant_s"]) == set(caps.timeconstants_by_order[4])
            assert second._overrides == first._overrides
            assert second.plan is not None and not second.plan.hf2_selection["capability_verified"]
            assert not second.background_button.isEnabled()
            assert not second.start_button.isEnabled()
        finally:
            second.deleteLater()
    finally:
        wait_for(qt_app, lambda: not first.command_running())
        first.deleteLater()


@pytest.mark.parametrize("repair", ["longer_timeconstant", "higher_rate", "automatic_timeconstant", "automatic_rate", "restore_automatic"])
def test_aliasing_advisory_keeps_choices_and_can_be_adjusted(qt_app, repair):
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    caps = capabilities()
    widget = PhaseScanWidget(runner=RegularPhaseScanRunner(lambda: None, capabilities=caps))
    try:
        widget.advanced_group.setChecked(True)
        choices = widget.override_inputs
        choices["rate_sps"].setCurrentIndex(choices["rate_sps"].findData(min(caps.rates_sps)))
        choices["timeconstant_s"].setCurrentIndex(choices["timeconstant_s"].findData(8.02e-6))
        assert choices["order"].currentData() is None
        assert "order" not in widget._overrides
        assert widget.plan is not None
        assert all(combo.isEnabled() for combo in choices.values())
        assert supported_choices(choices["timeconstant_s"]) == {value for group in caps.timeconstants_by_order.values() for value in group}
        assert widget._overrides == {"rate_sps": min(caps.rates_sps), "timeconstant_s": 8.02e-6}
        assert "Aliasing advisory" in widget.hf2_status.text()
        assert widget.background_button.isEnabled()
        if repair == "longer_timeconstant":
            choices["timeconstant_s"].setCurrentIndex(choices["timeconstant_s"].findData(49.99e-6))
            assert widget._overrides["rate_sps"] == min(caps.rates_sps)
        elif repair == "higher_rate":
            choices["rate_sps"].setCurrentIndex(choices["rate_sps"].findData(max(caps.rates_sps)))
            assert widget._overrides["timeconstant_s"] == 8.02e-6
        elif repair == "automatic_timeconstant":
            choices["timeconstant_s"].setCurrentIndex(choices["timeconstant_s"].findData(None))
            assert "timeconstant_s" not in widget._overrides
        elif repair == "automatic_rate":
            choices["rate_sps"].setCurrentIndex(choices["rate_sps"].findData(None))
            assert "rate_sps" not in widget._overrides
        else:
            widget.restore_auto_button.click()
            assert widget._overrides == {}
        assert widget.plan is not None and widget.background_button.isEnabled()
    finally:
        widget.deleteLater()


@pytest.mark.parametrize("initially_verified", [False, True])
def test_failed_device_check_retains_editable_choices_and_retry_recovers(qt_app, initially_verified):
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    caps = capabilities()
    calls = []
    def provider():
        calls.append("check")
        if len(calls) == 1:
            raise RuntimeError("simulated connected-device read failed")
        return caps
    runner = RegularPhaseScanRunner(lambda: None, capabilities=replace(caps, verified=initially_verified), capability_provider=provider)
    widget = PhaseScanWidget(runner=runner)
    try:
        widget.advanced_group.setChecked(True)
        expected = {key: supported_choices(combo) for key, combo in widget.override_inputs.items()}
        widget.refresh_capabilities_button.click()
        wait_for(qt_app, lambda: not widget.command_running())
        assert "simulated connected-device read failed" in widget.scan_status.text()
        assert {key: supported_choices(combo) for key, combo in widget.override_inputs.items()} == expected
        assert all(combo.isEnabled() for combo in widget.override_inputs.values())
        assert not widget.background_button.isEnabled()
        assert not widget.plan.hf2_selection["capability_verified"]
        assert widget.refresh_capabilities_button.isEnabled()
        widget.override_inputs["timeconstant_s"].setCurrentIndex(widget.override_inputs["timeconstant_s"].findData(49.99e-6))
        assert widget._overrides["timeconstant_s"] == 49.99e-6
        widget.refresh_capabilities_button.click()
        wait_for(qt_app, lambda: not widget.command_running())
        assert calls == ["check", "check"]
        assert widget.plan.hf2_selection["capability_verified"]
        assert widget.plan.hf2_selection["requested"]["timeconstant_s"] == 49.99e-6
        assert widget.background_button.isEnabled()
    finally:
        wait_for(qt_app, lambda: not widget.command_running())
        widget.deleteLater()
