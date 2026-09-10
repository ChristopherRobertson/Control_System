"""Real host presentation integration, isolated settings and explicit review."""
from copy import deepcopy
from dataclasses import replace
import importlib
import os
import time
from types import SimpleNamespace

import numpy as np
import pytest


@pytest.fixture
def qt_app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


@pytest.fixture
def context(tmp_path):
    from control_app.measurement_host import ContextFactory
    from control_app.measurement_host.ownership import HardwareCoordinator
    preferences = {}
    return ContextFactory(save_root_provider=lambda: tmp_path,
                          preference_backend=preferences,
                          ownership=HardwareCoordinator(tmp_path / "instrument.lock")).for_experiment("microsecond_stroboscopy")


def wait_for(app, panel):
    deadline = time.monotonic() + 20
    while panel.command_running():
        app.processEvents()
        if time.monotonic() > deadline:
            pytest.fail("Worker did not finish")
        time.sleep(.005)
    app.processEvents()


def record_for(panel, kind="preliminary"):
    blocks = []
    points = []
    for point in panel.plan.settings.spectral_points:
        stream = {"timestamp_s": np.array([0., 1e-6]), "x": np.ones(2)}
        blocks.append({"wavenumber_cm1": point.wavenumber_cm1, "kind": kind, "sample": stream,
                       "completed_utc": "2026-09-10T00:00:00Z"})
        points.append({"wavenumber_cm1": point.wavenumber_cm1, "valid": True, "value": 1.0})
        if kind == "blank":
            for delay in panel.plan.settings.delays_us:
                for average in range(panel.plan.settings.averages):
                    blocks.append({"wavenumber_cm1": point.wavenumber_cm1, "kind": "blank_control", "sample": stream,
                                   "delay_s": delay*1e-6, "average_index": average,
                                   "completed_utc": "2026-09-10T00:00:00Z"})
    return {"schema_version": 1, "experiment_id": "microsecond_stroboscopy", "mode": panel.context.mode,
            "kind": kind, "status": "complete", "disposition": "complete", "run_id": "native-test-run",
            "settings": panel.plan.settings.to_dict(), "native_blocks": blocks,
            "compatibility": panel.adapter.compatibility(panel.plan),
            "restoration": {"safe_verified": True}, "processing": {"points": points, "maps": {}}}


def test_us_registration_creates_exact_two_independent_hardware_free_tabs(qt_app, context):
    from control_app.measurement_modules.microsecond_stroboscopy.registration import DESCRIPTOR, create_tabs
    tabs = create_tabs(context)
    assert DESCRIPTOR.experiment_id == "microsecond_stroboscopy"
    assert [(tab.instance_id, tab.title) for tab in tabs] == [
        ("microsecond_stroboscopy:single", "Microsecond Stroboscopy"),
        ("microsecond_stroboscopy:dual", "Dual-Detector Microsecond Stroboscopy")]
    single, dual = [tab.widget for tab in tabs]
    assert single.plan is not None and dual.plan is not None
    assert single.adapter is not dual.adapter and single.settings_widget is not dual.settings_widget
    single.settings_widget._controls["averages"][0].setValue(1)
    assert single.plan.settings.averages == 1 and dual.plan.settings.averages == 2
    assert single.context.preferences.namespace == "measurements/microsecond_stroboscopy/single/v1/"
    assert dual.context.preferences.namespace == "measurements/microsecond_stroboscopy/dual/v1/"
    assert not single.preliminary_button.isEnabled()
    assert dual.preliminary_button.isEnabled()
    for tab in tabs:
        tab.widget.deleteLater()


def test_us_actual_host_discovery_preserves_reserved_phase_scan_pair(qt_app, tmp_path):
    from control_app.measurement_host import ContextFactory, discover_modules, create_registered_tabs
    discovered = discover_modules()
    assert not discovered.issues
    assert [entry.experiment_id for entry in discovered.descriptors] == ["microsecond_stroboscopy"]
    result = create_registered_tabs(discovered, ContextFactory(save_root_provider=lambda: tmp_path),
        existing_titles=("Phase Scan", "Dual-Detector Phase Scan"),
        existing_instance_ids=("phase_scan:single", "phase_scan:dual"))
    assert not result.issues
    assert {handle.instance_id for handle in result.handles} == {"microsecond_stroboscopy:single", "microsecond_stroboscopy:dual"}
    for handle in result.handles:
        handle.widget.deleteLater()


def test_us_hardware_start_requires_readiness_even_with_checked_review(qt_app, context):
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondPanel
    from control_app.measurement_host.interchange import SampleSpectralSelection, SourceRecord, SpectralWindow
    panel = MicrosecondPanel(context.for_mode("dual"))
    settings = panel.adapter.read_settings()
    settings["identity"]["sample_selection_id"] = "review-selection"
    panel.adapter.sample_records = (SampleSpectralSelection(
        selection_id="review-selection", sample_id=settings["identity"]["sample_id"],
        producer_instance_id="microsecond_stroboscopy:single",
        source=SourceRecord("review-source", "native/review.json", "2026-09-10T00:00:00Z", "1"),
        condition_id=settings["identity"]["condition_id"], condition={},
        windows=(SpectralWindow(1944., 1946.),), accepted_by="Test reviewer",
        accepted_utc="2026-09-10T01:00:00Z").to_dict(),)
    panel.adapter.apply_settings(settings)
    panel.settings_widget._controls["execution_mode"][0].setCurrentText("hardware")
    panel.preliminary = record_for(panel)
    panel.review.setChecked(True)
    assert panel.plan is not None and panel.plan.readiness.blockers
    assert not panel.start_button.isEnabled()
    with pytest.raises(ValueError, match="readiness"):
        panel.begin("measurement")
    assert not panel.review.isChecked()
    assert not panel.command_running()
    panel.deleteLater()


def test_us_capability_check_selects_supported_nonmanual_choices_and_preserves_editable_override(qt_app, context):
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondPanel
    panel = MicrosecondPanel(context.for_mode("dual"))
    manual = panel.settings_widget._controls["response.hf2_time_constant_s"][0]
    manual.setValue(12.0)  # Display µs; intentionally absent from the discovered menu.
    capabilities = {"verified": True, "timing_rate_sps": 200000.,
        "sample": {"orders": [1], "rates_sps": [100000.], "timeconstants_by_order": {1: [10e-6, 20e-6]}},
        "reference": {"orders": [2], "rates_sps": [100000.], "timeconstants_by_order": {2: [20e-6]}}}
    panel._launch(lambda worker: {"capabilities": capabilities}, "check_capabilities")
    wait_for(qt_app, panel)
    values = panel.adapter.read_settings()["response"]
    assert values["sample_rate_sps"] == values["reference_rate_sps"] == 100000.
    assert values["reference_order"] == 2
    assert values["reference_time_constant_s"] == pytest.approx(20e-6)
    assert values["timing_rate_sps"] == 200000.
    assert values["hf2_time_constant_s"] == pytest.approx(12e-6)
    assert manual.isEnabled() and not panel.start_button.isEnabled()
    assert any("time constant" in error for error in panel.plan.readiness.blockers)
    assert "Supported choices applied" in panel.status.text()
    assert "Manual overrides retained and editable" in panel.status.text()
    panel.deleteLater()


def test_us_compatibility_change_restore_explains_mismatch_without_granting_review(qt_app, context):
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondPanel
    panel = MicrosecondPanel(context.for_mode("single"))
    panel.adapter.blank = record_for(panel, "blank")
    panel.preliminary = record_for(panel)
    panel._update_controls()
    panel.review.setChecked(True)
    assert panel.start_button.isEnabled()
    field = panel.settings_widget._controls["identity.cell_id"][0]
    original = field.text()
    field.setText("cell-two")
    assert not panel.review.isChecked() and not panel.start_button.isEnabled()
    assert "identity.cell_id" in panel.review_summary.text()
    assert panel.preliminary is not None
    field.setText(original)
    assert "identity.cell_id" not in panel.review_summary.text()
    assert panel.review.isEnabled() and not panel.review.isChecked()
    panel.deleteLater()


def test_us_instrument_restore_clears_stale_error_but_needs_review(qt_app, context):
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondPanel
    panel = MicrosecondPanel(context.for_mode("dual"))
    panel.preliminary = record_for(panel)
    panel.review.setChecked(True)
    change = lambda old, new: SimpleNamespace(changes=[SimpleNamespace(device_id="hf2li", configuration_key="range", previous_value=old, new_value=new)])
    panel.instrument_state_changed(change(1., 2.))
    assert "hf2li.range" in panel.review_summary.text()
    panel.instrument_state_changed(change(2., 1.))
    assert "hf2li.range" not in panel.review_summary.text()
    assert not panel.review.isChecked()
    panel.deleteLater()


def test_us_plan_roundtrip_modes_and_scoped_new_run(qt_app, context, tmp_path):
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondPanel
    single, dual = [MicrosecondPanel(context.for_mode(mode)) for mode in ("single", "dual")]
    path = tmp_path / "single-plan.json"
    single.save_plan(path)
    wait_for(qt_app, single)
    single.settings_widget._controls["averages"][0].setValue(3)
    single.load_plan(path)
    wait_for(qt_app, single)
    assert single.plan.settings.averages == 2
    dual.load_plan(path)
    wait_for(qt_app, dual)
    assert "mode" in dual.status.text().lower()
    dual.preliminary = record_for(dual)
    single.adapter.blank = record_for(single, "blank")
    single.preliminary = record_for(single)
    single.new_run()
    assert single.adapter.blank is None and single.preliminary is None
    assert dual.preliminary is not None and path.exists()
    single.deleteLater(); dual.deleteLater()


def test_us_saved_blank_complete_compatible_and_rejected_in_other_mode(qt_app, context, tmp_path):
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondPanel
    from control_app.measurement_modules.microsecond_stroboscopy.persistence import save_run
    panel = MicrosecondPanel(context.for_mode("single"))
    record = record_for(panel, "blank")
    save_run(tmp_path / "blank", record)
    panel.load_blank(tmp_path / "blank")
    wait_for(qt_app, panel)
    assert panel.adapter.blank is not None and panel.preliminary_button.isEnabled()
    record["status"] = record["disposition"] = "interrupted"
    save_run(tmp_path / "partial", record)
    panel.load_blank(tmp_path / "partial")
    wait_for(qt_app, panel)
    assert "interrupted" in panel.status.text()
    assert panel.adapter.blank["disposition"] == "complete"
    panel.deleteLater()


def test_us_numeric_nonuniform_slices_and_gap_preservation(qt_app):
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondViews
    views = MicrosecondViews()
    matrix = np.array([[.1, np.nan], [.03, .02], [.005, .003]])
    record = {"kind": "run", "mode": "dual", "processing": {
        "points": [], "maps": {"wavenumber_cm1": [1944., 1946.], "delay_s": [0., 25e-6, .001],
                                "delta_absorbance": matrix, "sample_reference_ratio": np.ones((3, 2))},
        "coverage": {"missing_points": 1}, "kinetics": []}}
    views.set_record(record)
    views.time_control.set_index(0)
    views.time_control.input.stepBy(1)
    assert views.time_index == 1
    assert views.time_control.input.value() == pytest.approx(.025)
    views.spectral_control.set_index(0)
    views.spectral_control.input.stepBy(1)
    assert views.spectral_index == 1
    assert np.isnan(record["processing"]["maps"]["delta_absorbance"][0, 1])
    assert views.quantity_control.findData("absolute_absorbance") == -1
    assert len(views.plots) == 4
    views.deleteLater()


def test_us_kinetic_fit_prediction_residuals_and_uncertainty_are_visible(qt_app):
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondViews
    views = MicrosecondViews()
    delays = np.asarray([0., 25e-6, 100e-6, .001])
    values = np.asarray([.1, .08, .04, .001])
    fit = {"disposition": "apparent_recovery", "delays_s": delays, "prediction": values*.99,
           "residuals": values*.01, "taus_s": [.000185], "tau_interval95_s": [[.00017, .00020]],
           "aicc": 5., "criterion": "AICc, improvement > 6", "identifiability_condition": 20.}
    record = {"kind": "run", "mode": "dual", "processing": {"points": [],
        "maps": {"wavenumber_cm1": [1945.], "delay_s": delays, "delta_absorbance": values[:, None],
                 "standard_error": np.full((4, 1), .001)},
        "kinetics": [{"wavenumber_cm1": 1945., "delay_s": delays, "value": values, "fit": fit},
                     {"label": "A1 measured", "delay_s": delays, "area": values*2,
                      "standard_error": np.full(4, .002), "fit": fit}], "coverage": {}}}
    views.set_record(record)
    assert "95% CI" in views.analysis_summary.text() and "AICc" in views.analysis_summary.text()
    assert len(views.plots[2].figure.axes) == 2
    assert len(views.plots[2].figure.axes[1].lines) == 2
    views.band_control.setCurrentIndex(1)
    assert views.plots[2].figure.axes[0].get_ylabel() == "Band area (ΔA cm⁻¹)"
    views.deleteLater()


def test_us_simulated_full_single_guided_workflow(qt_app, context):
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondPanel
    panel = MicrosecondPanel(context.for_mode("single"))
    settings = panel.adapter.read_settings()
    settings["spectral_points"] = settings["spectral_points"][1:2]
    settings["delays_us"] = [-100., 100., 1000.]
    settings["averages"] = 1
    panel.adapter.apply_settings(settings)
    panel.begin("blank")
    wait_for(qt_app, panel)
    assert panel.adapter.blank is not None, panel.status.text()
    panel.begin("preliminary")
    wait_for(qt_app, panel)
    assert panel.preliminary is not None, panel.status.text()
    assert not panel.start_button.isEnabled()
    panel.review.setChecked(True)
    assert panel.start_button.isEnabled()
    panel.begin("measurement")
    wait_for(qt_app, panel)
    assert panel.result is not None, panel.status.text()
    assert panel.result["disposition"] == "complete"
    assert panel.result["restoration"]["safe_verified"]
    assert panel.result["native_path"]
    panel.deleteLater()


def test_us_simulated_dual_preliminary_and_owned_abort(qt_app, context):
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondPanel
    panel = MicrosecondPanel(context.for_mode("dual"))
    settings = panel.adapter.read_settings()
    settings["spectral_points"] = settings["spectral_points"][1:2]
    settings["delays_us"] = [-100., 100., 1000.]
    settings["averages"] = 1
    panel.adapter.apply_settings(settings)
    panel.begin("preliminary")
    wait_for(qt_app, panel)
    assert panel.preliminary is not None, panel.status.text()
    assert panel.adapter.blank is None
    panel.review.setChecked(True)
    panel.begin("measurement")
    panel.request_abort("Operator stop")
    wait_for(qt_app, panel)
    assert "Acquisition stopped" in panel.status.text(), panel.status.text()
    assert panel.adapter.last_record is not None
    assert panel.adapter.last_record["restoration"]["safe_verified"]
    assert not panel.close_blockers()
    panel.new_run()
    assert panel.preliminary is None and panel.result is None
    panel.deleteLater()


def test_us_storage_failure_retains_native_until_retry_without_clearing_host_fault(qt_app, context, tmp_path, monkeypatch):
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondPanel
    from control_app.measurement_modules.microsecond_stroboscopy import persistence
    panel = MicrosecondPanel(context.for_mode("single"))
    settings = panel.adapter.read_settings()
    settings["spectral_points"] = settings["spectral_points"][1:2]
    settings["delays_us"] = [-100., 100.]
    settings["averages"] = 1
    panel.adapter.apply_settings(settings)
    original_save = persistence.save_run
    def fail_after_native_arrives(path, record):
        if record.get("native_blocks"):
            raise OSError("Injected full destination")
        return original_save(path, record)
    monkeypatch.setattr(persistence, "save_run", fail_after_native_arrives)
    panel.begin("blank")
    wait_for(qt_app, panel)
    assert panel.adapter.last_record["preservation_error"] == "Injected full destination"
    retained = panel.adapter.last_record["native_blocks"][0]["sample"]["x"].copy()
    assert len(retained) > 0 and panel.close_blockers()
    assert not panel.new_run_button.isEnabled()
    with pytest.raises(RuntimeError, match="Retry native save"):
        panel.new_run()
    # Model a pre-existing host fault; offline preservation must never recover it.
    token = panel.context.ownership.acquire(purpose="Injected unresolved instrument restoration")
    panel.context.ownership.release(token, safe_verified=False, preservation_verified=False, detail="Injected instrument fault")
    fault_before = panel.context.ownership.snapshot()
    monkeypatch.setattr(persistence, "save_run", original_save)
    panel.retry_native_save(tmp_path / "writable-recovery")
    wait_for(qt_app, panel)
    assert not panel.close_blockers() and panel.new_run_button.isEnabled(), panel.status.text()
    saved = persistence.load_run(panel.adapter.last_record["native_path"], mode="single")
    assert np.array_equal(saved["native_blocks"][0]["sample"]["x"], retained)
    assert saved["preservation_error"] == "Injected full destination"
    assert saved["preservation_recovery"]["saved"] is True
    assert saved["preservation_recovery"]["instrument_fault_cleared"] is False
    assert panel.context.ownership.snapshot() == fault_before
    panel.new_run()
    assert panel.adapter.last_record is None
    panel.deleteLater()
