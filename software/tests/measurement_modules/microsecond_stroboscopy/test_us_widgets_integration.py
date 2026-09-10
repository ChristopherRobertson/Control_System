"""Compact host workspace: automatic settings, independent sessions and native data."""
from copy import deepcopy
from functools import partial
from uuid import uuid4
import time

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
    return ContextFactory(save_root_provider=lambda: tmp_path, preference_backend={},
        ownership=HardwareCoordinator(tmp_path / "instrument.lock")).for_experiment("microsecond_stroboscopy")


def wait_for(app, panel):
    deadline = time.monotonic() + 30
    while panel.command_running():
        app.processEvents()
        if time.monotonic() > deadline:
            pytest.fail("Worker did not finish: " + panel.status.text())
        time.sleep(.005)
    app.processEvents()


def simulated_panel(context, mode):
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondPanel
    from control_app.measurement_modules.microsecond_stroboscopy.runner import run_acquisition
    from control_app.measurement_modules.microsecond_stroboscopy.acquisition import SimulatedAcquirer
    return MicrosecondPanel(context.for_mode(mode), hardware=False,
        runner=partial(run_acquisition, acquirer_factory=SimulatedAcquirer))


def small_plan(panel):
    settings = panel.adapter.read_settings()
    settings["spectral_points"] = settings["spectral_points"][1:2]
    settings["delays_us"] = [-100., 100., 1000.]
    settings["averages"] = 1
    panel.adapter.apply_settings(settings)


def record_for(panel, kind="preliminary"):
    points = [{"wavenumber_cm1": point.wavenumber_cm1, "valid": True, "value": 1.0,
               "raw_sample_x": 1.0} for point in panel.plan.settings.spectral_points]
    return {"schema_version": 1, "experiment_id": "microsecond_stroboscopy", "mode": panel.context.mode,
            "kind": kind, "status": "complete", "disposition": "complete", "run_id": str(uuid4()),
            "settings": panel.plan.settings.to_dict(), "native_blocks": [],
            "compatibility": panel.adapter.compatibility(panel.plan, kind=kind),
            "restoration": {"safe_verified": True}, "processing": {"points": points, "maps": {}}}


def test_us_registration_creates_exact_two_compact_independent_hardware_free_tabs(qt_app, context):
    from control_app.measurement_modules.microsecond_stroboscopy.registration import DESCRIPTOR, create_tabs
    from control_app.measurement_host.presentation import CompactMeasurementPanel
    from PySide6.QtWidgets import QCheckBox
    tabs = create_tabs(context)
    assert DESCRIPTOR.experiment_id == "microsecond_stroboscopy"
    assert [(tab.instance_id, tab.title) for tab in tabs] == [
        ("microsecond_stroboscopy:single", "Microsecond Stroboscopy"),
        ("microsecond_stroboscopy:dual", "Dual-Detector Microsecond Stroboscopy")]
    single, dual = [tab.widget for tab in tabs]
    assert single.adapter is not dual.adapter and single.settings_widget is not dual.settings_widget
    single.settings_widget._controls["averages"][0].setValue(1)
    assert single.plan.settings.averages == 1 and dual.plan.settings.averages == 2
    for panel in (single, dual):
        assert isinstance(panel, CompactMeasurementPanel)
        assert panel.plan is not None and not panel.command_running()
        assert not panel.findChildren(QCheckBox) and not hasattr(panel, "review")
        assert "execution_mode" not in panel.settings_widget._controls
        assert not any("temperature" in field or "qualification" in field for field in panel.settings_widget._controls)
        assert panel.adapter.read_settings()["execution_mode"] == "hardware"
        assert not hasattr(panel, "advanced_button")
        assert not panel.advanced_content.isCheckable() and not panel.advanced_content.isHidden()
        assert not panel.start_button.isEnabled()
        assert "Device service unavailable" in panel.validation.text()
        assert panel.settings_widget.delays.cursorPosition() == 0
        panel.resize(1100,780)
        panel.show()
        qt_app.processEvents()
        assert panel.width() == 1100 and panel.height() == 780
        assert panel.splitter.sizes()[0] < 400
        assert panel.advanced_content.isVisible()
        panel.close()
        panel.deleteLater()


def test_us_actual_host_discovery_preserves_reserved_phase_scan_pair(qt_app, tmp_path):
    from control_app.measurement_host import ContextFactory, discover_modules, create_registered_tabs
    discovered = discover_modules()
    assert not discovered.issues
    selected = [entry for entry in discovered.descriptors if entry.experiment_id == "microsecond_stroboscopy"]
    assert len(selected) == 1
    result = create_registered_tabs(selected, ContextFactory(save_root_provider=lambda: tmp_path),
        existing_titles=("Phase Scan", "Dual-Detector Phase Scan"),
        existing_instance_ids=("phase_scan:single", "phase_scan:dual"))
    assert not result.issues
    assert {handle.instance_id for handle in result.handles} == {"microsecond_stroboscopy:single", "microsecond_stroboscopy:dual"}
    for handle in result.handles:
        handle.widget.deleteLater()


def test_us_advanced_overrides_are_independent_and_roundtrip_microseconds(qt_app, context):
    panel = simulated_panel(context, "dual")
    controls = panel.settings_widget
    path = "response.hf2_time_constant_s"
    assert not controls._controls[path][0].isEnabled()
    controls.override_modes[path].setCurrentText("Override")
    controls._controls[path][0].setValue(12.)
    assert controls.read_settings()["response"]["hf2_time_constant_s"] == pytest.approx(12e-6)
    assert controls.read_settings()["manual_overrides"] == [path]
    assert controls.override_modes["response.sample_rate_sps"].currentText() == "Auto"
    controls.override_modes["response.sample_rate_sps"].setCurrentText("Override")
    controls.override_modes[path].setCurrentText("Auto")
    assert controls.read_settings()["manual_overrides"] == ["response.sample_rate_sps"]
    assert controls._controls["response.sample_rate_sps"][0].isEnabled()
    controls.restore_automatic()
    assert not controls.read_settings()["manual_overrides"]
    panel.deleteLater()


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_us_only_pertinent_overrides_and_exact_mircat_labels(qt_app, context, mode):
    from PySide6.QtWidgets import QLabel
    panel = simulated_panel(context, mode)
    expected = {"response.hf2_order", "response.hf2_time_constant_s", "response.sample_rate_sps",
                "response.integration_aperture_s", "timing.probe_rate_hz", "timing.mircat_pulse_width_ns"}
    if mode == "dual":
        expected |= {"response.reference_order", "response.reference_time_constant_s", "response.reference_rate_sps"}
    assert set(panel.settings_widget.override_modes) == expected
    labels = {label.text() for label in panel.settings_widget.advanced_widget.findChildren(QLabel)}
    assert {"Repetition rate", "Pulse width"} <= labels
    assert not any("QCL" in label for label in labels)
    assert not hasattr(panel.settings_widget, "off_band") and not hasattr(panel.settings_widget, "delay_order")
    panel.deleteLater()


def test_us_removed_editors_reset_current_values_and_preserve_historical_provenance(qt_app, context):
    from control_app.measurement_modules.microsecond_stroboscopy.settings import default_settings
    panel = simulated_panel(context, "single")
    settings = panel.adapter.read_settings()
    settings["response"]["detector_latency_s"] = 4e-6
    settings["manual_overrides"] = ["response.detector_latency_s", "timing.probe_rate_hz", "timing.probe_width_ns"]
    settings["timing"]["probe_rate_hz"] = 80000.
    settings["timing"]["probe_width_ns"] = 150.
    settings["timing"].pop("mircat_pulse_width_ns")
    settings["delay_order"] = "descending"
    settings["identity"]["sample_id"] = "retained-sample"
    settings["spectral_points"][0]["role"] = "off_band"
    panel.adapter.apply_settings(settings)
    panel.settings_widget.restore_automatic()
    saved = panel.adapter.read_settings()
    assert saved["manual_overrides"] == []
    assert saved["response"]["detector_latency_s"] == default_settings("single").response.detector_latency_s
    assert saved["timing"]["probe_width_ns"] == default_settings("single").timing.probe_width_ns
    assert saved["timing"]["mircat_pulse_width_ns"] == 100.
    assert saved["delay_order"] == "alternating"
    assert saved["historical_overrides"]["response.detector_latency_s"] == 4e-6
    assert saved["historical_overrides"]["timing.probe_width_ns"] == 150.
    assert saved["historical_overrides"]["delay_order"] == "descending"
    assert saved["identity"]["sample_id"] == "retained-sample"
    assert saved["spectral_points"][0]["role"] == "off_band"
    panel.settings_widget.save_preferences()
    reloaded = simulated_panel(context, "single")
    assert reloaded.adapter.read_settings()["historical_overrides"] == saved["historical_overrides"]
    assert reloaded.adapter.read_settings()["manual_overrides"] == []
    panel.deleteLater(); reloaded.deleteLater()


def test_us_repetition_rate_and_pulse_width_plumb_to_duty_validation(qt_app, context):
    panel = simulated_panel(context, "single")
    fields = panel.settings_widget
    for path in ("timing.probe_rate_hz", "timing.mircat_pulse_width_ns"):
        fields.override_modes[path].setCurrentText("Override")
    fields._controls["timing.probe_rate_hz"][0].setValue(1000.)
    fields._controls["timing.mircat_pulse_width_ns"][0].setValue(400.)
    values = fields.read_settings()
    assert values["timing"]["probe_rate_hz"] == 1e6
    assert values["timing"]["mircat_pulse_width_ns"] == 400.
    assert panel.plan is None and "30%" in panel.validation.text()
    fields._controls["timing.mircat_pulse_width_ns"][0].setValue(100.)
    assert panel.plan is not None, panel.validation.text()
    assert panel.plan.settings.timing.probe_rate_hz == 1e6
    assert panel.plan.settings.timing.mircat_pulse_width_ns == 100.
    panel.deleteLater()


def test_us_first_show_checks_capabilities_once_through_shared_owned_operation(qt_app, tmp_path, monkeypatch):
    from control_app.measurement_host import ContextFactory
    from control_app.measurement_host.ownership import HardwareCoordinator
    from control_app.measurement_modules.microsecond_stroboscopy import runner
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondPanel
    calls=[]
    def no_factory(*args, **kwargs):
        pytest.fail("Rendering constructed a physical device")
    context=ContextFactory(save_root_provider=lambda:tmp_path, preference_backend={},
        ownership=HardwareCoordinator(tmp_path / "capabilities.lock"),
        real_device_factories={"hf2li": no_factory}).for_experiment("microsecond_stroboscopy").for_mode("dual")
    def discover(context,operation,**kwargs):
        assert operation.hardware and context.ownership.snapshot()["state"] == "owned"
        calls.append(operation)
        context.ownership.release(operation.ownership,safe_verified=True,preservation_verified=True)
        return {"capabilities":{"verified":False}}
    monkeypatch.setattr(runner,"discover_capabilities",discover)
    panel=MicrosecondPanel(context)
    panel.settings_widget.delays.setText("unfinished edit")
    assert panel.plan is None
    assert calls == []
    panel.show();qt_app.processEvents();wait_for(qt_app,panel)
    assert len(calls)==1, panel.status.text()
    panel.hide();panel.show();qt_app.processEvents()
    assert len(calls)==1
    panel.close();panel.deleteLater()


def test_us_capability_resolution_keeps_independent_manual_override(qt_app, context):
    panel = simulated_panel(context, "dual")
    fields = panel.settings_widget
    fields.override_modes["response.hf2_time_constant_s"].setCurrentText("Override")
    fields._controls["response.hf2_time_constant_s"][0].setValue(20.)
    panel.adapter.capabilities = {"verified": True, "timing_rate_sps": 200000., "enabled_streams": [0,2,3],
        "sample": {"orders": [1], "rates_sps": [100000.], "timeconstants_by_order": {1: [10e-6, 20e-6]}},
        "reference": {"orders": [2], "rates_sps": [100000.], "timeconstants_by_order": {2: [20e-6]}}}
    panel.refresh_plan()
    assert panel.plan is not None, panel.validation.text()
    response = panel.plan.settings.response
    assert response.hf2_time_constant_s == pytest.approx(20e-6)
    assert response.sample_rate_sps == response.reference_rate_sps == 100000.
    assert response.reference_order == 2
    assert fields._controls["response.reference_time_constant_s"][0].value() == pytest.approx(20.)
    assert fields.manual_override_fields == {"response.hf2_time_constant_s"}
    panel.deleteLater()


def test_us_plan_roundtrip_modes_and_scoped_new_run(qt_app, context, tmp_path):
    single, dual = [simulated_panel(context, mode) for mode in ("single", "dual")]
    for field, value in (("timing.probe_rate_hz", 800.), ("timing.mircat_pulse_width_ns", 150.)):
        single.settings_widget.override_modes[field].setCurrentText("Override")
        single.settings_widget._controls[field][0].setValue(value)
    path = tmp_path / "single-plan.json"
    single.save_plan(path);wait_for(qt_app,single)
    single.settings_widget._controls["averages"][0].setValue(1)
    single.load_plan(path);wait_for(qt_app,single)
    assert single.plan.settings.averages == 2
    assert single.plan.settings.timing.probe_rate_hz == 800000.
    assert single.plan.settings.timing.mircat_pulse_width_ns == 150.
    assert single.settings_widget.override_modes["timing.mircat_pulse_width_ns"].currentText() == "Override"
    dual.load_plan(path);wait_for(qt_app,dual)
    assert "mode" in dual.status.text().lower()
    dual.preliminary = record_for(dual)
    blank=single.adapter.blank=record_for(single,"blank")
    single.preliminary=record_for(single)
    single.new_run()
    assert single.adapter.blank is blank and single.preliminary is None
    assert dual.preliminary is not None and path.exists()
    single.deleteLater();dual.deleteLater()


def test_us_loaded_blank_is_reusable_without_manual_approval(qt_app, context, tmp_path):
    from control_app.measurement_modules.microsecond_stroboscopy.persistence import save_run
    panel=simulated_panel(context,"single")
    record=record_for(panel,"blank")
    save_run(tmp_path / "blank", record)
    panel.load_run(tmp_path / "blank");wait_for(qt_app,panel)
    assert panel.adapter.reusable(panel.adapter.blank,panel.plan,kind="blank") is not None
    assert panel.start_button.isEnabled()
    assert panel.views.record is not None
    panel.deleteLater()


def test_us_native_run_loading_keeps_original_hidden_settings(qt_app, context, tmp_path):
    from control_app.measurement_modules.microsecond_stroboscopy.persistence import save_run
    panel = simulated_panel(context, "single")
    current = panel.adapter.read_settings()
    record = record_for(panel, "preliminary")
    record["settings"]["timing"]["probe_width_ns"] = 175.
    record["settings"]["response"]["detector_latency_s"] = 7e-6
    record["settings"]["manual_overrides"] = ["timing.probe_width_ns", "response.detector_latency_s"]
    record["settings"]["delay_order"] = "descending"
    save_run(tmp_path / "historical-native", record)
    panel.load_run(tmp_path / "historical-native"); wait_for(qt_app, panel)
    assert panel.views.record["settings"] == record["settings"]
    assert panel.adapter.read_settings() == current
    panel.deleteLater()


def test_us_single_acquires_without_external_blank_or_preliminary(qt_app, context):
    panel=simulated_panel(context,"single")
    small_plan(panel)
    assert panel.start_button.isEnabled() and panel.adapter.blank is None
    panel.begin("measurement");wait_for(qt_app,panel)
    assert panel.result is not None, panel.status.text()
    assert panel.result["disposition"] == "complete"
    assert panel.result["restoration"]["safe_verified"] and panel.result["native_path"]
    assert "absolute_absorbance" not in panel.result.get("processing",{}).get("maps",{})
    panel.deleteLater()


def test_us_dual_preliminary_and_abort_keep_native_and_allow_new_run(qt_app, context):
    panel=simulated_panel(context,"dual")
    small_plan(panel)
    panel.begin("preliminary");wait_for(qt_app,panel)
    assert panel.preliminary is not None, panel.status.text()
    assert panel.adapter.blank is None and panel.start_button.isEnabled()
    panel.begin("measurement");panel.request_abort("Operator stop");wait_for(qt_app,panel)
    assert "Acquisition stopped" in panel.status.text(),panel.status.text()
    assert panel.adapter.last_record is not None
    assert panel.adapter.last_record["restoration"]["safe_verified"]
    panel.new_run()
    assert panel.preliminary is None and panel.result is None
    panel.deleteLater()


def test_us_native_plot_retains_negative_signed_x(qt_app):
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondViews
    views=MicrosecondViews()
    record={"kind":"preliminary","mode":"single","processing":{"maps":{},"points":[
        {"wavenumber_cm1":1945.,"value":float("nan"),"valid":False,"raw_sample_x":-0.4}]}}
    views.set_record(record)
    axis=views.plots[0].figure.axes[0]
    assert axis.get_ylabel()=="Sample X"
    assert axis.lines[0].get_ydata()[0] == pytest.approx(-.4)
    views.deleteLater()


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


def test_us_storage_failure_retains_native_until_retry_without_clearing_host_fault(qt_app, context, tmp_path, monkeypatch):
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondPanel
    from control_app.measurement_modules.microsecond_stroboscopy import persistence
    panel = simulated_panel(context, "single")
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
