"""Actual registered slow-scan tabs exercised with retained synthetic records."""
from copy import deepcopy
from pathlib import Path
import time

import numpy as np
import pytest


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    application = QApplication.instance() or QApplication([])
    yield application
    application.processEvents()


def wait_for(app, panel, timeout=30):
    deadline = time.monotonic() + timeout
    while panel.command_running():
        app.processEvents()
        if time.monotonic() > deadline:
            panel.request_abort("test timeout")
            pytest.fail(f"Slow-scan UI operation did not finish: {panel.status.text()}")
        time.sleep(.005)
    app.processEvents()


def settings(mode="single"):
    from control_app.measurement_modules.steady_state_slow_scan.settings import (
        ConditionIdentity, SlowScanSettings, SpectralSegment,
    )
    return SlowScanSettings(mode=mode,
        condition=ConditionIdentity(sample_id="sample-1", preparation_id="prep-1", cell_id="cell-1",
            position_id="position-1", temperature_id="room-temperature-observation-1", matrix_id="buffer-1",
            configuration_id="configuration-1", temperature_k=295., temperature_uncertainty_k=.3,
            temperature_record_id="temperature-readback-1"),
        segments=(SpectralSegment("window-1", 1, 1900., 1904.),),
        condition_equilibrated=True, physical_controls_confirmed=True).to_dict()


@pytest.fixture
def tabs(app, tmp_path):
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_host.registry import create_registered_tabs
    from control_app.measurement_modules.steady_state_slow_scan.registration import DESCRIPTOR

    def forbidden(**kwargs):
        raise AssertionError("UI construction must not create connected devices")

    preferences = {}
    destination = [tmp_path]
    factory = ContextFactory(configuration_provider=lambda: {}, ownership=object(),
        real_device_factories={"hf2li": forbidden, "mircat": forbidden},
        preference_backend=preferences, save_root_provider=lambda: destination[0])
    created = create_registered_tabs((DESCRIPTOR,), factory)
    assert not created.issues
    yield created.handles, preferences, destination
    for handle in created.handles:
        if handle.command_running():
            handle.request_abort("test cleanup")
            wait_for(app, handle.widget)
        handle.widget.close()
        handle.widget.deleteLater()
    app.processEvents()


def stage(panel, role):
    panel.physical_stage.setCurrentIndex(panel.physical_stage.findData(role))
    panel.physical_confirm.setChecked(True)


def prepare(app, panel):
    panel.settings_editor.apply_settings(settings(panel.context.mode))
    stage(panel, "dark")
    assert panel.plan is not None, panel.validation.text()
    panel.begin_control("dark")
    wait_for(app, panel)
    assert panel.adapter.controls["dark"] is not None, panel.status.text()
    if panel.context.mode == "single":
        stage(panel, "blank")
        panel.begin_control("blank")
        wait_for(app, panel)
        assert panel.adapter.controls["blank"] is not None, panel.status.text()
    stage(panel, "sample")
    panel.begin("preliminary")
    wait_for(app, panel)
    assert panel.preliminary is not None, panel.status.text()


def test_slow_scan_exact_discovery_hardware_free_construction_and_independent_settings(app, tabs):
    from control_app.measurement_host.registry import discover_modules
    handles, preferences, _ = tabs
    assert "steady_state_slow_scan" in [d.experiment_id for d in discover_modules().descriptors]
    assert [h.title for h in handles] == ["Slow Scan", "Dual-Detector Slow Scan"]
    assert [h.instance_id for h in handles] == ["steady_state_slow_scan:single", "steady_state_slow_scan:dual"]
    first, second = (h.widget for h in handles)
    assert first is not second and first.adapter is not second.adapter
    assert first.adapter.runner is second.adapter.runner is None
    first.settings_editor.fields["sample_id"].setText("single-only")
    assert second.settings_editor.fields["sample_id"].text() == ""
    assert all(key.startswith("measurements/steady_state_slow_scan/single/v1/") for key in preferences)
    assert not first.start_button.isEnabled() and not second.start_button.isEnabled()


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_slow_scan_guided_physical_controls_preliminary_review_measure_save_load_new_run(app, tabs, mode, tmp_path):
    handles, preferences, destination = tabs
    panel = handles[0 if mode == "single" else 1].widget
    other = handles[1 if mode == "single" else 0].widget
    # Exercise real layout/resize delivery too: hidden widgets cannot detect
    # a form accidentally retained by both old and new QScrollArea instances.
    panel.resize(1600, 1120)
    panel.show()
    app.processEvents()
    panel.settings_editor.apply_settings(settings(mode))
    with pytest.raises(ValueError, match="physical staging"):
        panel.begin_control("dark")
    prepare(app, panel)
    assert not panel.start_button.isEnabled()
    assert len(panel.preliminary["spectra"]) == 4
    assert panel.plot.figure.axes[0].name == "rectilinear"
    assert len(panel.plot.figure.axes) == 2
    assert panel.peak_table.rowCount() == 1
    assert other.preliminary is None and other.adapter.controls["dark"] is None
    if mode == "dual":
        assert panel.adapter.controls["blank"] is None
        with pytest.raises(ValueError, match="simultaneous"):
            panel.adapter.accept_control("blank", {})
    panel.review.setChecked(True)
    assert panel.start_button.isEnabled()
    panel.begin("measurement")
    snapshot = panel.snapshot
    frozen_root = snapshot.operation.save_root
    destination[0] = tmp_path / "new_root"
    panel.output_location_changed(destination[0])
    wait_for(app, panel)
    assert panel.result is not None, panel.status.text()
    assert panel._displayed is panel.result
    assert panel.result["status"] == "completed"
    assert "estimated remaining" not in panel.elapsed.text()
    assert Path(panel.result["path"]).is_relative_to(frozen_root)
    assert snapshot.operation.save_root == frozen_root
    assert Path(panel.result["path"], "run.json").is_file()
    assert panel.result["restoration"]["pump_outputs"] == {"FIRE": False, "Q-switch": False}
    saved_run = Path(panel.result["path"])
    selected_settings = panel.adapter.read_settings()
    panel.save_plan(tmp_path / f"{mode}.plan.json")
    wait_for(app, panel)
    import json
    saved_plan = json.loads((tmp_path / f"{mode}.plan.json").read_text())
    assert saved_plan["derived_plan"]["compiled_timing"]["event_counts"]["pump_fire"] == 0
    panel.new_run()
    assert panel.result is panel.preliminary is None
    assert panel.adapter.controls == {"dark": None, "blank": None}
    assert panel.settings_editor.fields["sample_id"].text() == "sample-1"
    assert (saved_run / "run.json").exists()
    panel.load_plan(tmp_path / f"{mode}.plan.json")
    wait_for(app, panel)
    assert panel.adapter.read_settings()["condition"] == selected_settings["condition"]
    panel.load_run(saved_run)
    wait_for(app, panel)
    assert panel.result["run_id"] == snapshot.operation.run_id
    assert panel.review.isChecked() is False
    assert other.result is None
    panel.export_run(tmp_path / f"{mode}_export.json")
    wait_for(app, panel)
    assert (tmp_path / f"{mode}_export.json").is_file()


def test_slow_scan_condition_profiles_retain_independent_identities(app, tabs):
    panel = tabs[0][0].widget
    editor = panel.settings_editor
    editor.fields["sample_id"].setText("room-sample")
    editor.fields["temperature_id"].setText("room-observation")
    editor.condition.setCurrentIndex(editor.condition.findData("77k_hrp_co"))
    assert editor.fields["sample_id"].text() == ""
    assert editor.fields["temperature_id"].text() == ""
    editor.fields["sample_id"].setText("cryo-sample")
    editor.fields["temperature_id"].setText("cryo-observation")
    editor.condition.setCurrentIndex(editor.condition.findData("rt_hrp_co"))
    assert editor.fields["sample_id"].text() == "room-sample"
    assert editor.fields["temperature_id"].text() == "room-observation"
    editor.condition.setCurrentIndex(editor.condition.findData("77k_hrp_co"))
    assert editor.fields["sample_id"].text() == "cryo-sample"


def test_slow_scan_review_invalidates_with_specific_mismatch_then_clears_without_approval(app, tabs):
    panel = tabs[0][0].widget
    prepare(app, panel)
    panel.review.setChecked(True)
    panel.settings_editor.fields["sample_id"].setText("other-sample")
    assert not panel.review.isChecked()
    assert "condition.sample_id differs" in panel.control_status.text()
    assert panel.preliminary is None
    panel.settings_editor.fields["sample_id"].setText("sample-1")
    assert "differs" not in panel.control_status.text()
    assert not panel.review.isChecked() and not panel.start_button.isEnabled()


def test_slow_scan_plot_preserves_reversed_native_axes_missing_intervals_and_ratio_label(app):
    from control_app.measurement_host.presentation import PlotPanel
    from control_app.measurement_modules.steady_state_slow_scan.processing import NativeSweep, process_sweep
    from control_app.measurement_modules.steady_state_slow_scan.widgets import SpectrumPlotAdapter
    x = np.array([9., 8.9, 8.8, 5., 4.9, 4.8])
    native = NativeSweep("reverse-1", "dual", "rt_hrp_co", "one", "reverse", 0,
        x, np.ones(6), np.arange(6.), reference=np.full(6, 2.))
    spectrum = process_sweep(native)
    original = native.axis_cm1.copy()
    plot = PlotPanel(SpectrumPlotAdapter())
    plot.set_result({"spectrum": spectrum, "view": "ratio"})
    assert "ratio Q = S/R" in plot.figure.axes[0].get_ylabel()
    assert np.isnan(plot.figure.axes[0].lines[0].get_xdata()).any()
    np.testing.assert_array_equal(native.axis_cm1, original)
    plot.set_result({"spectrum": spectrum, "view": "absorbance"})
    assert "no applicable calibration" in plot.figure.axes[0].texts[0].get_text()
    plot.close()
    plot.deleteLater()


def test_slow_scan_mode_and_condition_native_loading_rejected(app, tabs, tmp_path):
    from control_app.measurement_modules.steady_state_slow_scan.persistence import save_plan
    single, dual = (h.widget for h in tabs[0])
    path = tmp_path / "single_plan.json"
    save_plan(path, settings("single"))
    with pytest.raises(ValueError, match="mode mismatch"):
        dual.adapter.load_plan(path)
    prepare(app, single)
    original = single.preliminary
    wrong = deepcopy(original)
    wrong["settings"]["condition"]["configuration_id"] = "different-config"
    assert any("configuration_id" in error for error in single.adapter.compatibility_errors(wrong, single.plan))


def test_slow_scan_instrument_changes_invalidate_only_recipient(app, tabs):
    from control_app.measurement_host.interchange import DeviceConfigurationChange, InstrumentStateChange
    first, second = (h.widget for h in tabs[0])
    prepare(app, first)
    first.review.setChecked(True)
    first.instrument_state_changed(InstrumentStateChange(
        producer_instance_id="phase_scan:single", recipients=(first.context.instance_id,),
        changes=(DeviceConfigurationChange("hf2li", "range_v", 1., 2.),), reason="Detector range adjusted"))
    assert not first.review.isChecked()
    assert "hf2li.range_v" in first.review_summary.text()
    assert "Instrument state changed" in ";".join(first.adapter.control_errors(first.plan))
    assert second.adapter._instrument_generation == 0


def test_slow_scan_abort_during_preparation_retains_partial_and_allows_new_run(app, tabs):
    from control_app.measurement_modules.steady_state_slow_scan.runner import SlowScanRunner, SyntheticSlowScanBackend
    from threading import Event
    panel, sibling = (h.widget for h in tabs[0])
    entered = Event()

    class WaitingBackend(SyntheticSlowScanBackend):
        def prepare(self, plan, compiled, check, report):
            super().prepare(plan, compiled, check, report)
            entered.set()
            while True:
                check()
                time.sleep(.002)

    panel.settings_editor.apply_settings(settings())
    panel.adapter.runner = SlowScanRunner(panel.context, backend_factory=WaitingBackend)
    stage(panel, "dark")
    panel.begin_control("dark")
    assert entered.wait(5)
    assert panel.close_blockers()
    panel.request_abort("operator abort")
    wait_for(app, panel)
    assert panel.status.text().startswith("Acquisition stopped")
    assert panel.adapter.runner.last_result["status"] == "cancelled"
    assert Path(panel.adapter.runner.last_result["path"], "run.json").exists()
    assert sibling.adapter.runner is None
    assert not panel.close_blockers()
    panel.new_run()
    assert panel.adapter.runner is None


def test_slow_scan_refit_preserves_original_native_and_sweep_navigation(app, tabs):
    panel = tabs[0][1].widget
    prepare(app, panel)
    old_path = Path(panel.preliminary["path"])
    original = (old_path / "run.json").read_bytes()
    panel.sweep_choice.setCurrentIndex(1)
    assert "reverse" in panel.sweep_choice.currentText() or "forward" in panel.sweep_choice.currentText()
    panel.spectral_slice.set_index(1)
    panel.spectral_slice.input.stepBy(1)
    assert panel.spectral_slice.index != 1
    panel.refit()
    wait_for(app, panel)
    assert panel.result is not None, panel.status.text()
    assert panel._displayed is panel.result
    assert Path(panel.result["analysis_path"]).is_file()
    assert (old_path / "run.json").read_bytes() == original
    assert len(panel.result["fit_alternatives"][0]) == 3
    assert len(panel.plot.figure.axes) == 2


def test_slow_scan_raw_view_keeps_native_when_normalization_lacks_support(app):
    from control_app.measurement_host.presentation import PlotPanel
    from control_app.measurement_modules.steady_state_slow_scan.processing import NativeSweep, process_sweep
    from control_app.measurement_modules.steady_state_slow_scan.widgets import SpectrumPlotAdapter
    x = np.array([1900., 1901., 1902.])
    native = NativeSweep("bad-reference", "dual", "rt_hrp_co", "one", "forward", 0,
                         x, np.array([1., 2., 3.]), np.arange(3.), reference=np.array([1., 0., 1.]))
    spectrum = process_sweep(native)
    assert not spectrum.valid[1]
    plot = PlotPanel(SpectrumPlotAdapter())
    plot.set_result({"spectrum": spectrum, "view": "sample"})
    np.testing.assert_array_equal(plot.figure.axes[0].lines[0].get_ydata(), native.sample)
    plot.deleteLater()


def test_slow_scan_fits_match_sweep_identity_when_an_earlier_spectrum_has_no_fit(app, tabs):
    from control_app.measurement_modules.steady_state_slow_scan.processing import NativeSweep, process_sweep, fit_spectrum
    panel = tabs[0][1].widget
    short_axis = np.linspace(1800., 1801., 3)
    fit_axis = np.linspace(1900., 1904., 120)
    short = process_sweep(NativeSweep("short", "dual", "rt_hrp_co", "short-window", "forward", 0,
        short_axis, np.ones(3), np.arange(3.), reference=np.ones(3)))
    good = process_sweep(NativeSweep("fittable", "dual", "rt_hrp_co", "fitted-window", "reverse", 0,
        fit_axis, 1 - .1*np.exp(-.5*((fit_axis-1902)/.4)**2), np.arange(120.), reference=np.ones(120)))
    fit = fit_spectrum(good)
    panel.display_result({"spectra": [short, good], "fits": [fit]})
    assert panel.peak_table.rowCount() == 0
    assert len(panel.plot.figure.axes) == 1
    panel.sweep_choice.setCurrentIndex(1)
    assert panel.peak_table.rowCount() == 1
    assert float(panel.peak_table.item(0, 0).text()) == pytest.approx(1902., abs=.01)
    assert len(panel.plot.figure.axes) == 2


def test_slow_scan_capability_operation_with_incomplete_plan_contends_and_releases(app, tmp_path):
    from threading import Event
    from control_app.measurement_host import ContextFactory
    from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError
    from control_app.measurement_modules.steady_state_slow_scan.widgets import SlowScanPanel
    from control_app.measurement_modules.steady_state_slow_scan.runner import SlowScanRunner, SyntheticSlowScanBackend
    entered, finish = Event(), Event()
    coordinator = HardwareCoordinator(tmp_path / "injected.lock")
    factory = ContextFactory(ownership=coordinator, save_root_provider=lambda: tmp_path)
    context = factory.for_experiment("steady_state_slow_scan")
    first, second = (SlowScanPanel(context.for_mode(mode)) for mode in ("single", "dual"))

    class InjectedCapabilityBackend(SyntheticSlowScanBackend):
        def discover(self, check):
            entered.set()
            while not finish.wait(.005):
                check()
            self.readbacks = {"t660_frame_capacity": 8192}
            return self.readbacks

    try:
        for panel in (first, second):
            panel.settings_editor.hardware.setChecked(True)
            panel.adapter.runner = SlowScanRunner(panel.context, backend_factory=InjectedCapabilityBackend)
        assert first.plan is None  # No sample identity/segments or operating values supplied.
        first.begin_control("capability")
        assert entered.wait(5)
        assert first.snapshot.operation.hardware
        with pytest.raises(OwnershipError):
            second.begin_control("capability")
        manual = factory.for_experiment("manual_controls").for_mode("single")
        with pytest.raises(OwnershipError):
            manual.begin_operation({}, hardware=True, purpose="injected manual adjustment")
        finish.set()
        wait_for(app, first)
        assert coordinator.snapshot()["state"] == "free"
        assert first.adapter.readbacks["t660_frame_capacity"] == 8192
        assert not first.review.isChecked()
    finally:
        finish.set()
        if first.command_running():
            first.request_abort("test cleanup")
            wait_for(app, first)
        for panel in (first, second):
            panel.deleteLater()
