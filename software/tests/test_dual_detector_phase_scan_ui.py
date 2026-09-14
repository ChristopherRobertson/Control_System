"""Shared phase-scan UI parity and dual session isolation, without hardware."""
from dataclasses import replace
import json
from types import SimpleNamespace

import numpy as np
import pytest

from test_regular_phase_scan_ui import qt_app, supported_choices
from control_app.workflows.dual_detector_phase_scan import DualHF2Capabilities
from control_app.workflows.dual_detector_phase_scan_runner import DualDetectorPhaseScanRunner
from control_app.workflows.regular_phase_scan_runner import RegularPhaseScanRunner
from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget


def dual_widget(**kwargs):
    caps = DualHF2Capabilities()
    caps = replace(caps, verified=True, sample=replace(caps.sample, verified=True), reference=replace(caps.reference, verified=True))
    runner = DualDetectorPhaseScanRunner(lambda: None, capabilities=caps)
    return PhaseScanWidget(runner=runner, dual_detector=True, **kwargs)


@pytest.mark.parametrize("cleanup_fault", [False, True])
def test_dual_user_stop_is_concise_and_cleanup_failures_stay_visible(qt_app, tmp_path, monkeypatch, cleanup_fault):
    from PySide6.QtWidgets import QMessageBox
    from control_app import paths
    from test_dual_detector_phase_scan_runner import SimulatedAcquirer
    from test_regular_phase_scan_ui import wait_for
    calls = []
    class WaitingAcquirer(SimulatedAcquirer):
        def capture_block(self, events, cancel):
            calls.append("capture")
            cancel.wait(5)
            if not cancel.is_set():
                raise RuntimeError("test cancellation was not received")
            self.partial_blocks.append({"sample": [1.], "reference": [2.]})
            raise InterruptedError("operator requested stop")
    acquirer = WaitingAcquirer(cleanup_fault=cleanup_fault)
    widget = dual_widget()
    widget.runner.acquirer_factory = lambda: acquirer
    monkeypatch.setattr(paths, "_selected_save_location", tmp_path)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    try:
        widget.test_button.click()
        wait_for(qt_app, lambda: bool(calls))
        widget.abort_button.click()
        wait_for(qt_app, lambda: not widget.command_running())
        text = widget.scan_status.text()
        if cleanup_fault:
            assert text.startswith("RuntimeError: Safe shutdown or restoration failed:")
            assert "simulated restoration failure" in text
        else:
            assert text.startswith("Acquisition stopped. Data: ")
            assert "RuntimeError" not in text and "InterruptedError" not in text
        assert str(tmp_path) in text
        assert not widget.runner.preliminary_reviewed and widget.runner.preliminary is None
        assert widget.inputs["scan_speed_cm1_s"].isEnabled()
        assert not widget.start_button.isEnabled()
        assert acquirer.calls.count("close") == 1
        assert list(tmp_path.rglob("acquisition.npz"))
    finally:
        widget.deleteLater()


def test_shared_controls_and_independent_preferences(qt_app, tmp_path):
    from PySide6.QtCore import QSettings
    prefs = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    single = PhaseScanWidget(runner=RegularPhaseScanRunner(), preferences=prefs)
    dual = dual_widget(preferences=prefs)
    try:
        assert set(single.inputs) == set(dual.inputs)
        for key in single.inputs:
            a, b = single.inputs[key], dual.inputs[key]
            assert (a.minimum(), a.maximum(), a.decimals()) == (b.minimum(), b.maximum(), b.decimals())
        assert dual.background_button.isHidden() and dual.load_background_button.isHidden()
        assert not single.background_button.isHidden()
        assert dual.test_button.isEnabled() and not dual.start_button.isEnabled()
        assert "reference path" in dual.execution.text()
        assert len(dual.override_inputs) == 6
        dual.advanced_group.setChecked(True)
        assert all(supported_choices(combo) for combo in dual.override_inputs.values())
        dual.inputs["pump_repetition_rate_hz"].setValue(5)
        assert single.settings().pump_repetition_rate_hz == 10
        assert "5 Hz" in dual.summary_values["pump"].text()
        assert "Sample:" in dual.summary_values["hf2"].text()
        assert "Reference:" in dual.summary_values["hf2"].text()
        reopened = dual_widget(preferences=prefs)
        try:
            assert reopened.settings().pump_repetition_rate_hz == 5
            assert prefs.contains("regular_phase_scan") and prefs.contains("dual_detector_phase_scan")
        finally:
            reopened.deleteLater()
    finally:
        single.deleteLater()
        dual.deleteLater()


def test_plan_modes_and_new_run_preserve_settings_and_files(qt_app, tmp_path):
    dual = dual_widget()
    single = PhaseScanWidget()
    try:
        path = tmp_path / "dual.json"
        path.write_text(json.dumps(dual.plan.to_dict()))
        dual.inputs["pump_repetition_rate_hz"].setValue(5)
        dual.load_plan(path)
        assert dual.settings().pump_repetition_rate_hz == 10
        with pytest.raises(ValueError, match="single-detector"):
            single.load_plan(path)
        single_path = tmp_path / "single.json"
        single_path.write_text(json.dumps(single.plan.to_dict()))
        with pytest.raises(ValueError, match="single-detector"):
            dual.load_plan(single_path)
        before = dual.settings()
        dual.runner.preliminary_reviewed = True
        dual._new_run()
        assert dual.runner.preliminary is None and not dual.runner.preliminary_reviewed
        assert not dual.review_checkbox.isChecked()
        assert dual.settings() == before and path.exists() and single_path.exists()
        assert "sample/reference" in dual.scan_status.text()
    finally:
        dual.deleteLater()
        single.deleteLater()


def test_dual_main_window_keeps_offline_tabs_accessible_on_short_desktop(qt_app):
    from control_app.ui.main_window import ControlSystemMainWindow
    window = ControlSystemMainWindow()
    try:
        dual = window.dual_detector_phase_scan_widget
        assert window.tabs.tabText(window.tabs.indexOf(dual)) == "DD Phase Scan"
        window.resize(1100, 780)
        window.show()
        window.tabs.setCurrentWidget(dual)
        qt_app.processEvents()
        assert window.height() == 780
        window._phase_busy_changed(True, dual)
        assert window.tabs.isTabEnabled(window.tabs.indexOf(dual))
        # Hardware exclusion is enforced by backend ownership; opening another
        # tab for plan editing or native-data inspection remains independent.
        assert window.tabs.isTabEnabled(window.tabs.indexOf(window.phase_scan_widget))
        window._phase_busy_changed(False, dual)
        assert all(window.tabs.isTabEnabled(i) for i in range(window.tabs.count()))
    finally:
        window.deleteLater()


def test_preliminary_is_labeled_ratio(qt_app):
    dual = dual_widget()
    try:
        dual.set_latest_scan([1900, 1950, 2000], [.5, np.nan, .6])
        assert dual.canvas.y_label == "Sample/reference ratio"
        assert "sample/reference spectrum" in dual.preliminary_status.text()
        assert np.isnan(dual.canvas.points[1][1])
    finally:
        dual.deleteLater()


def test_baseline_approval_invalidation_and_compatible_plan_clears_error(qt_app, tmp_path):
    from control_app.workflows.dual_detector_phase_scan_data import experiment_contract
    dual = dual_widget()
    try:
        saved = tmp_path / "matching.json"
        saved.write_text(json.dumps(dual.plan.to_dict()))
        dual.runner.preliminary = {"experiment_contract": experiment_contract(dual.plan),
                                   "path": tmp_path, "channel_balance": None}
        dual._update_buttons()
        dual.review_checkbox.setChecked(True)
        assert dual.start_button.isEnabled() and dual.runner.preliminary_reviewed
        dual.inputs["pump_repetition_rate_hz"].setValue(5)
        assert not dual.start_button.isEnabled()
        assert not dual.review_checkbox.isChecked() and not dual.runner.preliminary_reviewed
        incompatible = tmp_path / "incompatible.json"
        incompatible.write_text(json.dumps(dual.plan.to_dict()))
        dual.load_plan(incompatible)
        assert "incompatible" in dual.scan_status.text()
        dual.load_plan(saved)
        assert "match" in dual.scan_status.text() and "incompatible" not in dual.scan_status.text()
        assert dual.review_checkbox.isEnabled() and not dual.start_button.isEnabled()
        dual.review_checkbox.setChecked(True)
        assert dual.start_button.isEnabled()
        # A second explicit review is recorded without overwriting the first.
        assert (tmp_path / "review.json").exists()
        assert len(list(tmp_path.glob("review*.json"))) == 2
        dual._overrides["reference_rate_sps"] = 1.
        dual._refresh_plan()
        assert dual.plan is None and not dual.runner.preliminary_reviewed
        assert not dual.review_checkbox.isChecked()
    finally:
        dual.deleteLater()


def test_dual_surface_numeric_inputs_toolbar_export_and_new_run(qt_app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from test_dual_detector_phase_scan_data import synthetic_result
    from test_regular_phase_scan_ui import reconstruction
    from control_app.workflows.phase_scan_data import save_native
    from control_app.ui.widgets.phase_scan_surface import export_quantitative_csv
    dual = dual_widget(save_root_provider=lambda: tmp_path)
    try:
        result = synthetic_result()
        dual.show_reconstruction(result)
        surface = dual.reconstruction
        assert [surface.mode.itemData(i) for i in range(surface.mode.count())] == ["delta_absorbance", "sample_reference_ratio"]
        assert surface.time_input.decimals() == 3 and surface.wavenumber_input.decimals() == 2
        surface.time_input.setValue(.77)
        surface.time_input.editingFinished.emit()
        assert surface.time_input.value() == round(result["time_s"][surface.time_slider.value()]*1000, 3)
        surface.wavenumber_input.setValue(1999.24)
        surface.wavenumber_input.editingFinished.emit()
        assert surface.wavenumber_input.value() == result["wavenumber_cm1"][surface.spectral_slider.value()]
        surface.mode.setCurrentIndex(1)
        assert surface.axes.get_ylabel() == "Sample/reference ratio"
        surface.toolbar.pan()
        surface.select_action.trigger()
        assert not surface.toolbar.mode
        surface.toolbar.zoom()
        surface.select_action.trigger()
        assert not surface.toolbar.mode
        surface.axes.view_init(elev=55, azim=50)
        surface.toolbar._actions["home"].trigger()
        assert surface.axes.elev == 20
        image = tmp_path / "dual.png"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(image), "PNG (*.png)"))
        surface.toolbar._actions["save_figure"].trigger()
        assert image.stat().st_size > 1000
        export_quantitative_csv(tmp_path / "dual.csv", result)
        assert "sample_reference_ratio" in (tmp_path / "dual.csv").read_text()
        path = tmp_path / "saved"
        save_native(path / "processed" / "reconstruction.npz", result)
        dual._new_run()
        surface.load_run(path)
        np.testing.assert_equal(surface.result["delta_absorbance"], result["delta_absorbance"])
        wrong = tmp_path / "single"
        save_native(wrong / "processed" / "reconstruction.npz", reconstruction())
        with pytest.raises(ValueError, match="single-detector"):
            surface.load_run(wrong)
        assert surface.result is not None
    finally:
        dual.deleteLater()


def test_app_preliminary_review_pumped_acquisition_and_fresh_run(qt_app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from control_app import paths
    from test_dual_detector_phase_scan_runner import SimulatedAcquirer
    from test_regular_phase_scan_ui import wait_for
    dual = dual_widget()
    dual.runner.acquirer_factory = SimulatedAcquirer
    monkeypatch.setattr(paths, "_selected_save_location", tmp_path)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    try:
        dual.inputs["stop_wavenumber_cm1"].setValue(1998)
        dual.inputs["scan_speed_cm1_s"].setValue(1000)
        dual.inputs["phase_delay_us"].setValue(500)
        dual.test_button.click()
        wait_for(qt_app, lambda: not dual.command_running())
        assert dual.runner.preliminary is not None
        assert dual.review_checkbox.isEnabled() and not dual.start_button.isEnabled()
        assert dual.canvas.y_label == "Sample/reference ratio"
        dual.review_checkbox.click()
        assert dual.start_button.isEnabled()
        dual.start_button.click()
        wait_for(qt_app, lambda: not dual.command_running())
        result = dual.reconstruction.result
        assert result is not None
        np.testing.assert_allclose(result["delta_absorbance"][np.isfinite(result["delta_absorbance"])], .1)
        before = dual.settings()
        saved_paths = list(tmp_path.rglob("acquisition.npz"))
        assert len(saved_paths) == 2
        dual.new_run_button.click()
        assert dual.settings() == before and dual.runner.preliminary is None
        assert dual.reconstruction.result is None
        assert not dual.review_checkbox.isChecked() and not dual.start_button.isEnabled()
        assert all(path.exists() for path in saved_paths)
    finally:
        wait_for(qt_app, lambda: not dual.command_running())
        dual.deleteLater()
