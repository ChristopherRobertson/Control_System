"""Actual host discovery and both nanosecond panels; no physical instruments."""
from copy import deepcopy
from pathlib import Path
import time

import pytest


@pytest.fixture
def ns_qt(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def wait_idle(app, panel):
    deadline = time.monotonic() + 40
    while panel.command_running():
        app.processEvents()
        if time.monotonic() >= deadline:
            pytest.fail("Panel background operation timed out: " + panel.status.text())
        time.sleep(.005)
    app.processEvents()


@pytest.fixture
def ns_pair(ns_qt, tmp_path):
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_host.ownership import HardwareCoordinator
    from control_app.measurement_host.registry import create_registered_tabs
    from control_app.measurement_modules.nanosecond_stroboscopy.registration import DESCRIPTOR
    preferences, hardware_calls = {}, []
    root = [tmp_path / "output"]
    def forbidden_factory(**kwargs):
        hardware_calls.append(kwargs)
        raise AssertionError("A simulator panel accessed a physical factory")
    factory = ContextFactory(
        configuration_provider=lambda: {},
        real_device_factories={"hf2li": forbidden_factory, "mircat": forbidden_factory},
        ownership=HardwareCoordinator(tmp_path / "instrument.lock"),
        preference_backend=preferences, save_root_provider=lambda: root[0],
    )
    activated = create_registered_tabs([DESCRIPTOR], factory)
    assert not activated.issues
    assert not hardware_calls
    yield activated.handles, preferences, root, hardware_calls
    for handle in activated.handles:
        if handle.command_running():
            handle.request_abort("Test cleanup")
            wait_idle(ns_qt, handle.widget)
        handle.widget.close()
        handle.widget.deleteLater()
    ns_qt.processEvents()


def test_ns_production_discovery_creates_exact_independent_pair_without_hardware(ns_pair):
    from control_app.measurement_host.registry import discover_modules
    discovery = discover_modules()
    descriptors = [item for item in discovery.descriptors if item.experiment_id == "nanosecond_stroboscopy"]
    assert len(descriptors) == 1
    handles, preferences, _root, calls = ns_pair
    assert [handle.title for handle in handles] == ["Nanosecond Stroboscopy", "Dual-Detector Nanosecond Stroboscopy"]
    assert [handle.instance_id for handle in handles] == ["nanosecond_stroboscopy:single", "nanosecond_stroboscopy:dual"]
    single, dual = [handle.widget for handle in handles]
    assert single.adapter is not dual.adapter and single.settings_widget is not dual.settings_widget
    assert single.plan is not dual.plan
    assert single.plan.settings.execution_mode == dual.plan.settings.execution_mode == "simulation"
    assert not single.start_button.isEnabled() and not dual.start_button.isEnabled()
    assert not single.preliminary_button.isEnabled() and dual.preliminary_button.isEnabled()
    assert all(key.startswith("measurements/nanosecond_stroboscopy/") for key in preferences)
    assert any("/single/v1/" in key for key in preferences)
    assert any("/dual/v1/" in key for key in preferences)
    assert calls == []


def test_ns_both_real_panels_complete_simulator_workflow_load_export_and_reset(ns_qt, ns_pair, tmp_path):
    handles, _preferences, root, calls = ns_pair
    single, dual = [handle.widget for handle in handles]
    single.begin_blank()
    wait_idle(ns_qt, single)
    assert single.adapter.blank is not None, single.status.text()
    assert single.adapter.blank["status"] == "completed", single.status.text()
    assert len(single.adapter.blank["events"]) == len(single.plan.events)
    assert dual.adapter.blank is None
    single.begin("preliminary")
    dual.begin("preliminary")
    wait_idle(ns_qt, single)
    wait_idle(ns_qt, dual)
    for panel in (single, dual):
        assert panel.preliminary is not None, panel.status.text()
        assert not panel.adapter.validate_review(panel.preliminary, panel.plan)
        assert not panel.start_button.isEnabled()
        panel.review.setChecked(True)
        panel.begin("measurement")
    frozen = single.snapshot.operation.output_path
    root[0] = tmp_path / "next-output"
    handles[0].output_location_changed(root[0])
    for panel in (single, dual):
        wait_idle(ns_qt, panel)
        assert panel.result and panel.result["status"] == "completed", panel.status.text()
        assert panel.result["result"]["coverage"].sum() > 0
        assert len(panel.plot.figure.axes) >= 4
        assert panel.time_slice.input.suffix() == " ns"
        assert panel.time_slice.input.decimals() == 2
        assert panel.time_slice.coordinates[1] != 0
        panel.time_slice.set_index(0)
        panel.time_slice.input.stepBy(1)
        assert panel.time_slice.index == 1
    assert Path(single.result["output_path"]) == frozen
    assert calls == []
    assert "operation finished" in dual.elapsed.text()
    export = tmp_path / "ns-export.csv"
    dual.export_run(export)
    wait_idle(ns_qt, dual)
    assert "quantized_delay_ns" in export.read_text()
    assert not dual.result["result"]["absolute_available"]
    assert dual.quantity.findData("absolute_absorbance") == -1
    assert dual.condition.findData("pump_blocked") >= 0
    dual.condition.setCurrentIndex(dual.condition.findData("pump_blocked"))
    assert dual.plot_adapter.condition == "pump_blocked"
    assert not dual.quantity.model().item(dual.quantity.findData("ratio")).isEnabled()
    dual.condition.setCurrentIndex(0)
    assert dual.quantity.model().item(dual.quantity.findData("ratio")).isEnabled()
    native_path = single.result["output_path"]
    settings = single.adapter.read_settings()
    single.new_run()
    assert single.result is single.preliminary is single.adapter.blank is None
    assert single.adapter.read_settings() == settings
    assert dual.result is not None and dual.preliminary is not None
    assert not single.review.isChecked()
    assert Path(native_path).exists()
    single.load_run(native_path)
    wait_idle(ns_qt, single)
    assert single.result["events"]
    assert single.preliminary is None and not single.review.isChecked()
    dual.load_run(native_path)
    wait_idle(ns_qt, dual)
    assert "mode" in dual.status.text().lower()


def test_ns_settings_mismatch_clears_review_then_restores_without_approval(ns_qt, ns_pair):
    dual = ns_pair[0][1].widget
    dual.begin("preliminary")
    wait_idle(ns_qt, dual)
    assert dual.preliminary, dual.status.text()
    dual.review.setChecked(True)
    original = dual.adapter.read_settings()
    changed = deepcopy(original)
    changed["sample_id"] = "different-sample"
    dual.adapter.apply_settings(changed)
    dual.refresh_plan()
    assert not dual.review.isChecked() and not dual.start_button.isEnabled()
    assert "sample_id" in dual.validation.text()
    dual.adapter.apply_settings(original)
    dual.refresh_plan()
    assert not dual.validation.text()
    assert dual.preliminary is not None
    assert not dual.review.isChecked() and not dual.start_button.isEnabled()


def test_ns_instrument_change_rechecks_baseline_and_retained_state(ns_qt, ns_pair):
    from control_app.measurement_host.interchange import DeviceConfigurationChange, InstrumentStateChange
    dual = ns_pair[0][1].widget
    dual.begin("preliminary")
    wait_idle(ns_qt, dual)
    assert dual.preliminary, dual.status.text()
    dual.review.setChecked(True)
    event = InstrumentStateChange(
        producer_instance_id="nanosecond_stroboscopy:single", recipients=("nanosecond_stroboscopy:dual",),
        changes=(DeviceConfigurationChange("hf2li", "reference_range", 1., 2.),), reason="Range changed",
    )
    dual.instrument_state_changed(event)
    assert not dual.review.isChecked()
    assert "reference_range" in dual.validation.text()
    reverse = InstrumentStateChange(
        producer_instance_id="nanosecond_stroboscopy:single", recipients=("nanosecond_stroboscopy:dual",),
        changes=(DeviceConfigurationChange("hf2li", "reference_range", 2., 1.),), reason="Range restored",
    )
    dual.instrument_state_changed(reverse)
    assert dual.preliminary is not None
    assert not dual.validation.text()
    assert not dual.review.isChecked()


def test_ns_plan_loading_mode_and_incomplete_baseline_rejected(ns_qt, ns_pair, tmp_path):
    single, dual = [handle.widget for handle in ns_pair[0]]
    path = tmp_path / "single-plan.json"
    single.save_plan(path)
    wait_idle(ns_qt, single)
    assert path.exists(), single.status.text()
    dual.load_plan(path)
    wait_idle(ns_qt, dual)
    assert "mode" in dual.status.text().lower()
    dual.begin("preliminary")
    wait_idle(ns_qt, dual)
    assert dual.preliminary, dual.status.text()
    incomplete = deepcopy(dual.preliminary)
    incomplete["events"] = incomplete["events"][:1]
    assert any("missing valid measured" in error for error in dual.adapter.validate_review(incomplete, dual.plan))


def test_ns_settings_are_editable_and_precision_never_becomes_milliseconds(ns_pair):
    single, dual = [handle.widget for handle in ns_pair[0]]
    settings = single.settings_widget
    settings.controls["delays_ns"].setText("-300, -150, -50, 0, 10, 30, 100, 500, 2000")
    settings.controls["delays_ns"].editingFinished.emit()
    assert single.plan.settings.delays_ns[4] == 10
    assert dual.plan.settings.delays_ns[4] == 0
    assert "10" in single.summary.text()
    assert "ns" in single.summary.text()
    settings.controls["temperature_k"].setText("77.1")
    settings.controls["temperature_k"].editingFinished.emit()
    assert settings.read_settings()["temperature_k"] == 77.1


def test_ns_prospective_simulation_and_complete_timing_display(ns_qt, ns_pair):
    dual = ns_pair[0][1].widget
    dual.evaluate_schedule()
    wait_idle(ns_qt, dual)
    assert "Prospective known-truth simulation" in dual.result_note.text(), dual.status.text()
    assert "does not grant" in dual.result_note.text()
    assert dual.preliminary is None and not dual.review.isChecked()
    dual.show_plan_details()
    from PySide6.QtWidgets import QPlainTextEdit
    text = dual._plan_dialog.findChild(QPlainTextEdit).toPlainText()
    assert '"channels"' in text and '"electrical_delays_ns"' in text
    assert '"event-0000001"' in text
    dual._plan_dialog.close()


def test_ns_promoted_bundle_resolves_settings_and_stays_separate_from_sample(ns_pair, monkeypatch, tmp_path):
    from control_app.promoted_bundles import PromotedBundle
    dual = ns_pair[0][1].widget
    domain = dual.adapter.read_settings()
    domain.pop("qualification")
    domain.pop("calibration_ids")
    domain["optical_delay_offset_ns"] = 12.5
    domain["irf_sigma_ns"] = 5.
    payload = {"settings_domain": domain, "optical_timing_qualified": True,
               "selected_probe_qualified": True, "kernel_id": "sparse_single_probe_demod_impulse"}
    bundle = PromotedBundle("test-instrument-bundle", tmp_path, {"nanosecond_stroboscopy": payload})
    monkeypatch.setattr(dual.context, "promoted_bundle", lambda bundle_id: bundle)
    dual.bundle_id.setText(bundle.bundle_id)
    dual.load_bundle()
    settings = dual.adapter.read_settings()
    assert settings["calibration_ids"] == (bundle.bundle_id,)
    assert settings["irf_sigma_ns"] == 5.
    assert settings["optical_delay_offset_ns"] == 12.5
    assert settings["qualification"]["irf_qualified"]
    assert settings["execution_mode"] == "simulation"
    assert dual.adapter.sample_records == []
    assert len(dual.adapter.selected_records().calibration_records) == 1
    payload["settings_domain"]["mode"] = "single"
    with pytest.raises(ValueError, match="mode differs"):
        dual.load_bundle()


def test_ns_sample_selection_windows_and_condition_rechecked(ns_pair, tmp_path):
    from control_app.measurement_host.interchange import (
        SampleSpectralSelection, SourceRecord, SpectralWindow, save_sample_selection,
    )
    dual = ns_pair[0][1].widget
    record = SampleSpectralSelection(
        selection_id="selection-1", sample_id="sample-1", producer_instance_id="nanosecond_stroboscopy:dual",
        source=SourceRecord("source-run", "relative/sample.json", "2026-01-01T00:00:00+00:00", "1"),
        condition_id="condition-1", condition={"profile_id": "RT-Mb-G"},
        windows=(SpectralWindow(1964., 1966., 1965., .1, "A1"),),
        accepted_by="test reviewer", accepted_utc="2026-01-01T00:00:00+00:00",
    )
    path = save_sample_selection(record, tmp_path / "selection.json")
    dual.load_selection(path)
    assert dual.plan.settings.wavenumbers_cm1 == (1965.,)
    assert dual.plan.settings.sample_id == "sample-1"
    assert dual.adapter.calibration_records == []
    settings = dual.adapter.read_settings()
    settings["condition_id"] = "incompatible-condition"
    dual.adapter.apply_settings(settings)
    dual.refresh_plan()
    assert "condition_id" in dual.validation.text()
    with pytest.raises(ValueError, match="condition identity"):
        dual.load_selection(path)
