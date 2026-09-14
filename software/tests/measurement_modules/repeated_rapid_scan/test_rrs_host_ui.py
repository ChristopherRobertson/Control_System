"""Compact production tabs, direct acquisition and independent native sessions."""
import json
import os
from dataclasses import replace
from pathlib import Path
import time

import pytest
import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from control_app.measurement_host.context import ContextFactory
from control_app.measurement_host.ownership import HardwareCoordinator
from control_app.measurement_host.registry import discover_modules, create_registered_tabs
from control_app.measurement_host.interchange import InstrumentStateChange, DeviceConfigurationChange
from control_app.measurement_modules.repeated_rapid_scan.registration import DESCRIPTOR
from control_app.measurement_modules.repeated_rapid_scan.settings import example_settings


@pytest.fixture
def app():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


@pytest.fixture
def tabs(app, tmp_path):
    coordinator = HardwareCoordinator(tmp_path / "instrument.lock")
    preferences = {}
    factory = ContextFactory(save_root_provider=lambda: tmp_path,
        preference_backend=preferences, ownership=coordinator)
    result = create_registered_tabs((DESCRIPTOR,), factory)
    assert not result.issues
    yield result.handles
    for handle in result.handles:
        assert not handle.command_running()
        handle.widget.deleteLater()
    app.processEvents()


def wait(app, panel, timeout=30):
    deadline = time.monotonic()+timeout
    while panel.command_running():
        app.processEvents()
        if time.monotonic() > deadline:
            panel.request_abort("test timeout")
            pytest.fail(panel.status.text())
        time.sleep(.005)
    app.processEvents()
    return panel.status.text()


def small_plan(panel):
    settings = replace(example_settings(panel.context.mode), phase_offsets_s=(0.,), directions=("forward",),
                       controls=("probe_only",), pre_scans=3, post_scans=24)
    from control_app.measurement_modules.repeated_rapid_scan.simulation import SimulationAcquirer
    panel.adapter.acquirer_factory = SimulationAcquirer
    panel.adapter.apply_settings(settings.to_dict())
    panel.refresh_plan()
    assert panel.plan is not None, panel.validation.text()


def test_rrs_actual_pair_discovery_and_construction_are_hardware_free(app, tmp_path):
    def forbidden(**kwargs):
        raise AssertionError("Factory invoked while constructing tabs")
    factory = ContextFactory(real_device_factories={name: forbidden for name in ("hf2li", "mircat", "t660_1", "t660_2")},
                             save_root_provider=lambda: tmp_path, ownership=HardwareCoordinator(tmp_path / "discovery.lock"))
    discovered = discover_modules()
    assert DESCRIPTOR in discovered.descriptors
    result = create_registered_tabs((DESCRIPTOR,), factory)
    assert not result.issues
    assert [h.title for h in result.handles] == ["Rapid Scan Phase Delay", "DD Rapid Scan Phase Delay"]
    assert [h.instance_id for h in result.handles] == ["repeated_rapid_scan:single", "repeated_rapid_scan:dual"]
    single, dual = [h.widget for h in result.handles]
    assert single.adapter.session is not dual.adapter.session
    assert single.settings_widget is not dual.settings_widget
    assert single.context.preferences.namespace == "measurements/repeated_rapid_scan/single/v1/"
    assert dual.context.preferences.namespace == "measurements/repeated_rapid_scan/dual/v1/"
    for handle in result.handles:
        handle.widget.deleteLater()


def test_rrs_single_guided_blank_preliminary_measurement_and_saved_loading(app, tabs, tmp_path):
    panel, sibling = [h.widget for h in tabs]
    small_plan(panel)
    assert panel.start_button.isEnabled()
    panel.begin_auxiliary("blank")
    wait(app, panel)
    assert panel.adapter.session.blank, panel.status.text()
    panel.begin("preliminary")
    wait(app, panel)
    assert panel.preliminary is not None, panel.status.text()
    panel.begin("measurement")
    wait(app, panel)
    assert panel.result is not None, panel.status.text()
    assert panel.result["status"] == "complete"
    assert panel.result["processed"]
    assert sibling.preliminary is None and sibling.result is None
    path = Path(panel.result["output_path"])
    assert path.is_relative_to(tmp_path / "measurements" / "repeated_rapid_scan" / "single")
    assert (path / "run.json").exists()
    loaded = panel.adapter.load_run(path)
    assert loaded["run_id"] == panel.result["run_id"]
    panel.plots.set_result(loaded)
    panel.plots.scan.set_index(0)
    panel.plots.scan.input.stepBy(1)
    assert panel.plots.scan.index == 1
    export = tmp_path / "native_coordinates.csv"
    panel.adapter.export_run(export, loaded)
    assert "time_s,wavenumber_cm1" in export.read_text()
    settings = panel.adapter.read_settings()
    panel.new_run()
    assert panel.adapter.read_settings() == settings
    assert panel.preliminary is None and panel.result is None and panel.adapter.session.blank is None
    assert (path / "run.json").exists()


def test_rrs_dual_simultaneous_workflow_no_routine_blank(app, tabs):
    single, panel = [h.widget for h in tabs]
    small_plan(panel)
    panel.begin("preliminary")
    wait(app, panel)
    assert panel.preliminary is not None, panel.status.text()
    assert all(scan.reference is not None for m in panel.preliminary["native_movies"] for scan in m.scans)
    panel.begin("measurement")
    wait(app, panel)
    assert panel.result is not None, panel.status.text()
    assert panel.result["status"] == "complete"
    assert panel.adapter.session.blank is None
    assert single.adapter.session.preliminary is None


def test_rrs_standard_native_load_reuses_saved_sample(app, tabs):
    panel = tabs[1].widget
    small_plan(panel)
    panel.begin("preliminary")
    wait(app, panel)
    path = Path(panel.preliminary["output_path"])
    settings = panel.adapter.read_settings()
    panel.new_run()
    assert panel.adapter.session.preliminary is None
    panel._launch(lambda _worker: panel.adapter.load_run(path), "load_run", path)
    wait(app, panel)
    assert panel.result["kind"] == "preliminary"
    assert panel.adapter.session.preliminary is panel.result
    assert panel.adapter.compatible_preliminary(panel.plan) is panel.result
    assert panel.adapter.read_settings() == settings
    assert panel.start_button.isEnabled()


def test_rrs_compatible_sample_auto_reuse_and_metadata_never_gate(app, tabs):
    panel = tabs[1].widget
    small_plan(panel)
    panel.begin("preliminary")
    wait(app, panel)
    candidate = panel.preliminary
    assert candidate, panel.status.text()
    original = panel.adapter.read_settings()
    changed = json.loads(json.dumps(original))
    changed["condition"]["temperature_K"] = 77.
    changed["condition"]["state_verification_ids"] = ["annotation-only"]
    panel.adapter.apply_settings(changed)
    panel.refresh_plan()
    assert panel.preliminary is candidate
    assert panel.start_button.isEnabled()
    panel.settings_widget.sample.setText("Other sample")
    panel.refresh_plan()
    assert panel.preliminary is None
    assert panel.start_button.isEnabled()  # Start acquires its own compatible baseline.
    panel.adapter.apply_settings(original)
    panel.refresh_plan()
    assert panel.preliminary is candidate
    event = InstrumentStateChange("manual:mircat", (panel.context.instance_id,),
        (DeviceConfigurationChange("mircat", "scan_speed", 10., 11.),), "manual adjustment")
    panel.instrument_state_changed(event)
    assert panel.preliminary is None
    panel.instrument_state_changed(InstrumentStateChange("manual:mircat", (panel.context.instance_id,),
        (DeviceConfigurationChange("mircat", "scan_speed", 11., 10.),), "restored"))
    assert panel.preliminary is candidate


@pytest.mark.parametrize("index", [0, 1])
def test_rrs_start_without_review_or_blank_acquires_relative_movie(app, tabs, index):
    from PySide6.QtWidgets import QCheckBox
    panel = tabs[index].widget
    small_plan(panel)
    assert not panel.findChildren(QCheckBox)
    assert not hasattr(panel, "review") and not hasattr(panel, "physical_ready")
    assert panel.adapter.read_settings()["execution"] == "hardware"
    panel.begin("measurement")
    wait(app, panel)
    assert panel.result is not None, panel.status.text()
    assert panel.result["status"] == "complete"
    assert panel.result["processed"]
    assert panel.adapter.session.blank is None
    assert all(np.isfinite(p.delta_absorbance).any() for movie in panel.result["processed"] for p in movie.points)
    assert all(not np.isfinite(p.absolute_absorbance).any() for movie in panel.result["processed"] for p in movie.points)
    raw_only = dict(panel.result)
    raw_only["processed"] = [replace(movie, points=[replace(point,
        delta_absorbance=np.full_like(point.delta_absorbance, np.nan)) for point in movie.points])
        for movie in panel.result["processed"]]
    panel.plots.set_result(raw_only)
    assert panel.plots.quantity.currentData() == "normalized_signal"
    assert not panel.plots.quantity.model().item(0).isEnabled()


def test_rrs_plan_mode_rejection_and_preserving_preferences(app, tabs, tmp_path):
    single, dual = [h.widget for h in tabs]
    small_plan(single)
    path = tmp_path / "plan.json"
    single.adapter.save_plan(path, single.adapter.read_settings(), single.plan)
    assert single.adapter.load_plan(path) == single.adapter.read_settings()
    with pytest.raises(ValueError, match="detector mode"):
        dual.adapter.load_plan(path)
    with pytest.raises(FileExistsError):
        single.adapter.save_plan(path, single.adapter.read_settings(), single.plan)


def test_rrs_native_fit_action_persists_separate_analysis_and_residuals(app, tabs):
    panel = tabs[1].widget
    small_plan(panel)
    panel.begin("preliminary")
    wait(app, panel)
    panel.begin("measurement")
    wait(app, panel)
    assert panel.result is not None, panel.status.text()
    original_path = panel.result["output_path"]
    axis = np.linspace(1897., 1952., 1001)
    windows = panel.plan.settings.band_windows_cm1
    shape = sum(np.exp(-.5*((axis-(a+b)/2)/((b-a)/3))**2) for a,b in windows)
    panel.adapter.fit_model = {
        "kernel": {"measured": True, "calibration_id": "synthetic-identity-kernel-v1",
                   "response_basis": "electrical_sync", "delays_s": [0.], "weights": [1.],
                   "description": "Explicit known-truth simulated response, not installed instrument evidence"},
        "spectral_template": {"record_id": "synthetic-two-band-template", "description": "Known simulated spectrum",
                              "wavenumbers_cm1": axis.tolist(), "values": shape.tolist()},
        "tau_bounds_s": [.08, .3],
    }
    panel._fit_movie()
    wait(app, panel)
    assert "fit_analysis" in panel.result, panel.status.text()
    fit = panel.result["fit_analysis"]["fits_by_direction"]["forward"]
    assert fit.apparent_tau_s == pytest.approx(.15, rel=.02)
    assert panel.result["output_path"] != original_path
    assert (Path(original_path)/"run.json").exists()
    assert "apparent" in panel.fit_summary.text()
    assert panel.plots.view.currentText() == "Fit residuals"


def test_rrs_compact_layout_keeps_plot_and_independent_auto_overrides(app, tabs):
    from control_app.measurement_host.presentation import CompactMeasurementPanel
    from control_app.measurement_modules.repeated_rapid_scan.planner import HardwareCapabilities
    panel = tabs[1].widget
    assert isinstance(panel, CompactMeasurementPanel)
    panel.resize(1100, 780)
    panel.show()
    app.processEvents()
    assert panel.splitter.count() == 2
    assert panel.summary_group.isVisible()
    from PySide6.QtWidgets import QGroupBox
    assert isinstance(panel.advanced_content, QGroupBox)
    assert panel.advanced_content.isVisible()
    assert not panel.advanced_content.isCheckable()
    assert not hasattr(panel, "advanced_button")
    assert panel.size().height() == 780
    assert panel.plots.height() >= 350
    settings = panel.settings_widget
    settings.override_inputs["sample_filter_order"].setEditText("2")
    settings.set_capabilities(HardwareCapabilities(live_settings={"sample_rate_hz": 8000., "sample_filter_order": 6}))
    selected = settings.read()
    assert selected["sample_filter_order"] == 2 and selected["sample_rate_hz"] == 8000.
    assert selected["manual_overrides"] == {"sample_filter_order": 2}
    settings.restore_automatic()
    assert settings.read()["sample_filter_order"] == 6
    panel.hide()


@pytest.mark.parametrize("index", [0, 1])
def test_rrs_visible_overrides_control_emitted_cadence_and_optical_width(app, tabs, index):
    from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox
    panel = tabs[index].widget
    panel.resize(1100, 780)
    panel.show()
    app.processEvents()
    widget = panel.settings_widget
    expected = {"scan_speed_cm1_s", "sample_rate_hz", "sample_filter_order",
                "sample_filter_timeconstant_s", "probe_frequency_hz", "mircat_pulse_width_ns"}
    if index == 1:
        expected |= {"reference_rate_hz", "reference_filter_order", "reference_filter_timeconstant_s"}
    assert set(widget.override_inputs) == expected
    assert isinstance(panel.advanced_content, QGroupBox)
    assert panel.advanced_content.isVisible() and not panel.advanced_content.isCheckable()
    assert all(control.isVisible() for control in widget.override_inputs.values())
    assert all("qcl" not in control.objectName().lower() for control in panel.findChildren(QComboBox))
    form = widget.advanced.layout()
    assert isinstance(form, QFormLayout)
    rate = widget.override_inputs["probe_frequency_hz"]
    width = widget.override_inputs["mircat_pulse_width_ns"]
    assert form.labelForField(rate).text() == "Repetition rate (Hz)"
    assert form.labelForField(width).text() == "Pulse width (ns)"
    rate.setEditText("2000000")
    width.setEditText("150")
    width.lineEdit().editingFinished.emit()
    assert panel.plan is not None, panel.validation.text()
    selected = panel.plan.settings
    assert selected.mircat_pulse_rate_hz is None
    assert selected.mircat_pulse_width_ns == 150.
    assert selected.probe_frequency_hz == 2_000_000.
    assert selected.probe_pulse_width_s == 150e-9
    width.setEditText("150.01")
    width.lineEdit().editingFinished.emit()
    assert panel.plan is None and "30%" in panel.validation.text()
    assert not panel.start_button.isEnabled()
    width.setCurrentIndex(0)
    width.lineEdit().editingFinished.emit()
    assert widget.read()["manual_overrides"] == {"probe_frequency_hz": 2_000_000.}
    panel.hide()


def test_rrs_user_edits_refresh_plan_and_precise_overrides_roundtrip(app, tabs):
    from control_app.measurement_modules.repeated_rapid_scan.planner import HardwareCapabilities
    panel = tabs[1].widget
    widget = panel.settings_widget
    widget.inputs["observation_duration_s"].setValue(2.)
    assert panel.plan.settings.post_scans == 20
    widget.override_inputs["sample_filter_order"].setCurrentIndex(1)
    assert panel.plan.settings.manual_overrides["sample_filter_order"] == 4
    settings = widget.read()
    settings["manual_overrides"]["mircat_pulse_width_ns"] = 142.12345678901
    widget.apply(settings)
    assert widget.read()["mircat_pulse_width_ns"] == 142.12345678901
    widget.set_capabilities(HardwareCapabilities(live_settings={
        "mircat_pulse_rate_hz": 2_000_000., "mircat_pulse_width_ns": 150.}))
    width = widget.override_inputs["mircat_pulse_width_ns"]
    width.setCurrentIndex(width.findText("150"))
    assert widget.read()["mircat_pulse_width_ns"] == 150.
    assert widget.read()["mircat_pulse_rate_hz"] == 2_000_000.
    precise = widget.read()
    precise["acquisition_intent"]["observation_duration_s"] = .1004
    precise["acquisition_intent"]["spectral_min_cm1"] = 1898.0004
    widget.apply(precise)
    assert widget.read()["acquisition_intent"]["observation_duration_s"] == .1004
    assert widget.read()["scan_start_cm1"] == 1898.0004


def test_rrs_native_plot_retains_detector_offset_and_unsigned_backstep():
    from control_app.measurement_modules.repeated_rapid_scan.data import NativeStream, NativeScan, NativeMovie, ScanTrajectory
    from control_app.measurement_modules.repeated_rapid_scan.widgets import native_detector_coordinates
    origin = 2**53 + 100
    sample = NativeStream(np.array([origin+2, origin+1], dtype=np.uint64), [1., 2.],
                          timestamp_origin=origin, timestamp_unit_s=.001)
    reference = NativeStream(np.array([origin+4, origin+5], dtype=np.uint64), [1., 1.],
                             timestamp_origin=origin, timestamp_unit_s=.001)
    trajectory = ScanTrajectory(np.array([origin, origin+10], dtype=np.uint64), [1900., 1901.], "",
                                timestamp_origin=origin, timestamp_unit_s=.001)
    scan = NativeScan(0, sample, trajectory, reference)
    movie = NativeMovie("native", 0., [scan], [], "dual", "sample")
    traces = native_detector_coordinates(scan, movie)
    assert traces[0][1] == pytest.approx([.002, .001])
    assert traces[1][1] == pytest.approx([.004, .005])


def test_rrs_check_device_with_invalid_spectral_inputs_is_owned_read_only(app, tabs):
    from control_app.measurement_modules.repeated_rapid_scan.simulation import SimulationAcquirer
    calls = []
    class QueryAcquirer(SimulationAcquirer):
        def discover(self, worker):
            calls.append(self.context.ownership.snapshot()["state"])
            self.readbacks = {"capabilities": {}}
        def prepare(self, worker):
            raise AssertionError("A device check must not prepare emission")
    panel = tabs[0].widget
    panel.adapter.acquirer_factory = QueryAcquirer
    panel.settings_widget.inputs["spectral_min_cm1"].setValue(2000.)
    assert panel.plan is None
    assert panel.capability_button.isEnabled()
    panel.begin_auxiliary("capabilities")
    wait(app, panel)
    assert calls == ["owned"], panel.status.text()
    assert panel.context.ownership.snapshot()["state"] == "free"
    assert panel.adapter.runner.last_result["status"] == "complete"


def test_rrs_production_pair_installs_in_main_window_without_sibling_packages(app, tmp_path):
    from control_app.ui.main_window import ControlSystemMainWindow
    from control_app.ui.contracts import blocked_handler
    handler = blocked_handler("rapid-scan integration; no hardware")
    handler.coordinator = HardwareCoordinator(tmp_path / "instrument.lock")
    window = ControlSystemMainWindow(handler, module_discovery=(DESCRIPTOR,))
    try:
        titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
        assert titles.count("Rapid Scan Phase Delay") == 1
        assert titles.count("DD Rapid Scan Phase Delay") == 1
        assert "Phase Scan" in titles and "DD Phase Scan" in titles
        for mode, title in (("single", "Rapid Scan Phase Delay"), ("dual", "DD Rapid Scan Phase Delay")):
            window.set_detector_mode(mode)
            visible = [window.tabs.tabText(i) for i in range(window.tabs.count()) if window.tabs.isTabVisible(i)]
            assert visible[0] == title
    finally:
        window.deleteLater()


def test_rrs_full_shell_keeps_every_settings_control_in_view(app, tmp_path):
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtGui import QFont, QFontDatabase
    from control_app.ui.contracts import blocked_handler
    from control_app.ui.main_window import ControlSystemMainWindow
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    previous_font = app.font()
    app.setFont(QFont("Segoe UI", 9))
    handler = blocked_handler("Injected layout test")
    handler.coordinator = HardwareCoordinator(tmp_path / "layout.lock")
    window = ControlSystemMainWindow(handler, module_discovery=(DESCRIPTOR,))
    window.phase_scan_widget._capability_check_attempted = True
    window.dual_detector_phase_scan_widget._capability_check_attempted = True
    window.resize(1100, 780)
    window.show()
    try:
        for mode in ("single", "dual"):
            panel = next(window.tabs.widget(i) for i in range(window.tabs.count())
                         if window.tabs.widget(i).objectName() == f"repeated_rapid_scan:{mode}")
            window.tabs.setCurrentWidget(panel)
            for _ in range(3):
                app.processEvents()
            window.grab().save(str(tmp_path / f"layout-{mode}.png"))
            viewport = panel.settings_scroll.viewport()
            controls = [panel.settings_widget.sample, *panel.settings_widget.inputs.values(),
                        *panel.settings_widget.override_inputs.values(),
                        panel.settings_widget.restore_auto_button, panel.capability_button,
                        panel.save_plan_button, panel.load_plan_button]
            for control in controls:
                assert control.isVisible()
                bounds = QRect(control.mapTo(viewport, QPoint()), control.size())
                assert viewport.rect().contains(bounds), (mode, control.objectName(), bounds)
            for control in (panel.start_button, panel.abort_button, panel.preliminary_button):
                assert panel.rect().contains(QRect(control.mapTo(panel, QPoint()), control.size()))
            assert panel.settings_scroll.verticalScrollBar().maximum() == 0
            assert panel.settings_scroll.horizontalScrollBar().maximum() == 0
            assert window.workspace_scroll.verticalScrollBar().maximum() == 0
    finally:
        window.hide()
        window.deleteLater()
        app.setFont(previous_font)


def test_rrs_presentation_failure_does_not_strand_completed_worker(app, tabs, monkeypatch):
    panel = tabs[1].widget
    small_plan(panel)
    def fail(_result):
        raise ValueError("injected plot failure")
    monkeypatch.setattr(panel.plots, "set_result", fail)
    panel.begin("preliminary")
    wait(app, panel)
    assert "Presentation failed" in panel.status.text()
    assert panel.worker is None and not panel.close_blockers()
    assert panel.adapter.session.preliminary is not None


def test_rrs_promoted_dual_background_selected_separately_from_q0(app, tmp_path):
    from types import SimpleNamespace
    from control_app.measurement_modules.repeated_rapid_scan.data import SpectralBaseline, SpectrumSupport
    from control_app.measurement_modules.repeated_rapid_scan.persistence import save_baseline
    root = tmp_path / "promoted-example"
    background = SpectralBaseline("measured-B", "dual", "example-hrp-room-temperature",
        (SpectrumSupport("forward", np.array([1898., 1951.]), np.array([1.1, 1.2])),),
        kind="background", complete=True, accepted=True)
    save_baseline(root / "balance", background)
    manifest = {"status": "PROMOTED", "bundle_id": "test-installed-response",
                "repeated_rapid_scan": {"calibration": {"condition_id": background.condition_id},
                                        "device_configuration": {}, "background_file": "balance"}}
    factory = ContextFactory(save_root_provider=lambda: tmp_path,
        promoted_bundle_loader=lambda _id: SimpleNamespace(bundle_id=manifest["bundle_id"], manifest=manifest, path=root))
    handles = create_registered_tabs((DESCRIPTOR,), factory).handles
    try:
        adapter = handles[1].widget.adapter
        record = adapter.read_bundle(manifest["bundle_id"])
        adapter.apply_bundle(record)
        assert adapter.session.background.record_id == "measured-B"
        assert adapter.session.blank is None and adapter.session.preliminary is None
        selected = adapter.selected_records().calibration_records[0]
        assert "background" not in selected and selected["background_record_id"] == "measured-B"
    finally:
        for handle in handles:
            handle.widget.deleteLater()


def test_rrs_storage_failure_keeps_native_until_explicit_preservation(app, tabs, monkeypatch):
    import control_app.measurement_modules.repeated_rapid_scan.runner as runner_module
    panel = tabs[1].widget
    small_plan(panel)
    original = runner_module.RepeatedRapidScanRunner
    def fail_save(*args, **kwargs):
        raise OSError("injected disk full")
    monkeypatch.setattr(runner_module, "RepeatedRapidScanRunner", lambda context, **kwargs: original(context, saver=fail_save, **kwargs))
    panel.begin("preliminary")
    wait(app, panel)
    retained = panel.adapter.runner.last_result
    assert retained["native_movies"] and retained["status"] == "preservation_failed"
    assert panel.close_blockers()
    panel.new_run()
    assert panel.adapter.runner.last_result is retained
    with pytest.raises(ValueError, match="Save retained records"):
        panel.begin("preliminary")
    panel._preserve_retained()
    wait(app, panel)
    assert retained["recovered_to"]
    assert (Path(retained["recovered_to"])/"run.json").exists()
    assert panel.context.ownership.snapshot()["state"] == "fault"
    assert "host instrument recovery" in panel.close_blockers()[0]
    panel.new_run()
    assert panel.adapter.runner is None
