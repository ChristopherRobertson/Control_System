"""Compact registered tabs exercised through shared workers; no real devices."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from threading import Event
import json
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
    from control_app.measurement_modules.steady_state_slow_scan.settings import SlowScanSettings, SpectralSegment
    return SlowScanSettings(mode=mode, lower_cm1=1900., upper_cm1=1904.,
        segments=(SpectralSegment("window-1", 1, 1900., 1904.),)).to_dict()


def inject_backend(panel, backend_type=None):
    from control_app.measurement_modules.steady_state_slow_scan.runner import SlowScanRunner, SyntheticSlowScanBackend
    from control_app.measurement_modules.steady_state_slow_scan.planner import build_plan, simulation_inputs
    class InjectedBackend(backend_type or SyntheticSlowScanBackend):
        def resolve_plan(self, settings, check):
            check()
            return build_plan(settings, replace(simulation_inputs(settings), simulation=False))
    panel.adapter.runner = SlowScanRunner(panel.context, backend_factory=InjectedBackend)


@pytest.fixture
def tabs(app, tmp_path):
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_host.ownership import HardwareCoordinator
    from control_app.measurement_host.registry import create_registered_tabs
    from control_app.measurement_modules.steady_state_slow_scan.registration import DESCRIPTOR
    def forbidden(**kwargs):
        raise AssertionError("UI construction must not create connected devices")
    preferences, destination = {}, [tmp_path]
    factory = ContextFactory(configuration_provider=lambda: {},
        ownership=HardwareCoordinator(tmp_path / "instrument.lock"),
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


def test_compact_tabs_construct_without_devices_or_approval_state(app, tabs):
    from PySide6.QtWidgets import QCheckBox
    from control_app.measurement_host.presentation import CompactMeasurementPanel
    handles, preferences, _ = tabs
    assert [h.title for h in handles] == ["Slow Scan", "Dual-Detector Slow Scan"]
    first, second = (h.widget for h in handles)
    assert isinstance(first, CompactMeasurementPanel)
    assert first.adapter.runner is second.adapter.runner is None
    assert not first.findChildren(QCheckBox) and not second.findChildren(QCheckBox)
    assert not hasattr(first, "review") and not hasattr(first, "state_acceptance")
    assert not hasattr(first.settings_editor, "hardware")
    assert first.settings_editor.read_settings()["hardware"] is True
    assert first.start_button.isEnabled(), first.validation.text()
    assert second.start_button.isEnabled(), second.validation.text()
    assert first.adapter.validate_preliminary(None, first.plan) == ()
    assert first.settings_editor.segments.rowCount() == 0
    requested = first.settings_editor.read_settings()
    requested["condition"]["sample_id"] = "one tab only"
    first.settings_editor.apply_settings(requested)
    assert second.settings_editor.read_settings()["condition"]["sample_id"] == ""
    from PySide6.QtWidgets import QLabel, QLineEdit
    for panel in (first, second):
        labels = " ".join(label.text() for label in panel.settings_editor.advanced_widget.findChildren(QLabel))
        assert not any(word in labels.casefold() for word in ("temperature", "thermal", "preparation", "metadata", "exposure"))
        assert not any(editor.objectName() in requested["condition"] for editor in panel.findChildren(QLineEdit))
    assert all(key.startswith("measurements/steady_state_slow_scan/single/v1/") for key in preferences)


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_shown_compact_sample_without_preliminary_saves_loads_and_exports(app, tabs, mode, tmp_path):
    panel = tabs[0][0 if mode == "single" else 1].widget
    panel.resize(1100, 780)
    panel.show()
    app.processEvents()
    assert panel.width() == 1100 and panel.height() == 780
    assert not panel.advanced_content.isVisible()
    assert not panel.preliminary_button.isVisible()
    assert panel.settings_editor.isVisible()
    assert panel.plot.isVisible()
    panel.settings_editor.apply_settings(settings(mode))
    inject_backend(panel)
    panel.begin("measurement")
    snapshot = panel.snapshot
    assert snapshot.operation.hardware is True
    wait_for(app, panel)
    assert panel.result is not None, panel.status.text()
    assert panel.result["status"] == "completed"
    assert panel.adapter.controls["dark"] is not None
    assert panel.adapter.controls["q0"]["run_id"] == panel.result["run_id"]
    assert panel.result["spectra"][0].quantity == ("raw_sample_signal" if mode == "single" else "reference_normalized_ratio")
    assert len(panel.result["spectra"]) == 4
    assert len(panel.plot.figure.axes) == 2
    panel.analysis_button.setChecked(True)
    app.processEvents()
    assert panel.height() == 780
    assert panel.plot.canvas.geometry().bottom() < panel.plot.height()
    assert panel.settings_editor.read_settings()["sample_rate_hz"] is None
    source = Path(panel.result["path"])
    assert (source / "run.json").is_file()
    panel.save_plan(tmp_path / f"{mode}.json")
    wait_for(app, panel)
    assert json.loads((tmp_path / f"{mode}.json").read_text())["settings"]["sample_rate_hz"] is None
    panel.new_run()
    assert panel.result is panel.preliminary is None
    assert panel.adapter.controls == {"dark": None, "blank": None, "q0": None}
    panel.load_plan(tmp_path / f"{mode}.json")
    wait_for(app, panel)
    panel.load_run(source)
    wait_for(app, panel)
    assert panel.result["run_id"] == snapshot.operation.run_id
    panel.export_run(tmp_path / f"{mode}-export.json")
    wait_for(app, panel)
    assert (tmp_path / f"{mode}-export.npz").is_file()
    panel.band_lower.setText("1901")
    panel.band_upper.setText("1903")
    panel.export_selection(tmp_path / f"{mode}-selection.json")
    wait_for(app, panel)
    assert (tmp_path / f"{mode}-selection.json").is_file(), panel.status.text()


def test_independent_auto_overrides_roundtrip_and_optional_metadata(app, tabs, tmp_path):
    panel = tabs[0][1].widget
    editor = panel.settings_editor
    editor.override_inputs["time_constant_s"].setText("0.017")
    editor.override_inputs["reference_sample_rate_hz"].setText("112.0")
    loaded = editor.read_settings()
    loaded["condition"].update(condition_id="Arbitrary buffer condition", temperature_k=77.)
    editor.apply_settings(loaded)
    requested = editor.read_settings()
    assert requested["time_constant_s"] == .017
    assert requested["sample_rate_hz"] is None
    assert requested["reference_sample_rate_hz"] == 112.
    assert requested["reference_time_constant_s"] is None
    editor.apply_settings({**requested, "hardware": False})
    assert editor.read_settings()["hardware"] is True
    editor.restore_automatic()
    assert all(editor.read_settings()[key] is None for key in editor.override_inputs)
    assert editor.read_settings()["condition"] == loaded["condition"]
    assert panel.start_button.isEnabled(), panel.validation.text()
    assert editor.lower.value() == 1900.
    assert editor.upper.value() == 1975.


def test_blank_and_dark_records_reject_wrong_kind_or_status_without_metadata_gates(app, tabs):
    panel = tabs[0][0].widget
    record = {"kind": "blank", "mode": "single", "status": "completed",
              "experiment_id": "steady_state_slow_scan", "instance_id": panel.context.instance_id,
              "settings": {"condition": {"condition_id": "another optional label"}}}
    panel.adapter.accept_control("blank", record)
    assert panel.adapter.controls["blank"]["settings"] == record["settings"]
    with pytest.raises(ValueError, match="completed"):
        panel.adapter.accept_control("blank", {**record, "status": "cancelled"})
    with pytest.raises(ValueError, match="another measurement"):
        panel.adapter.accept_control("blank", {**record, "experiment_id": "another"})


def test_refit_preserves_original_native_and_linked_slice_navigation(app, tabs):
    panel = tabs[0][1].widget
    panel.settings_editor.apply_settings(settings("dual"))
    inject_backend(panel)
    panel.begin("measurement")
    wait_for(app, panel)
    assert panel.result is not None, panel.status.text()
    native_path = Path(panel.result["path"]) / "run.json"
    original = native_path.read_bytes()
    panel.sweep_choice.setCurrentIndex(1)
    panel.spectral_slice.set_index(1)
    panel.spectral_slice.input.stepBy(1)
    assert panel.spectral_slice.index != 1
    panel.refit()
    wait_for(app, panel)
    assert Path(panel.result["analysis_path"]).is_file(), panel.status.text()
    assert native_path.read_bytes() == original
    assert panel._displayed is panel.result


def test_blank_is_reused_after_metadata_edit_and_saved_run_load(app, tabs):
    from control_app.measurement_modules.steady_state_slow_scan.runner import SyntheticSlowScanBackend
    panel = tabs[0][0].widget
    class InjectedConnectedReadbacks(SyntheticSlowScanBackend):
        def prepare(self, *args):
            super().prepare(*args)
            # Emulate connected readbacks for this reuse test. Native records
            # remain explicitly synthetic, and no real device factory is used.
            self.readbacks = {"injected_fixture": True}
    panel.settings_editor.apply_settings(settings())
    inject_backend(panel, InjectedConnectedReadbacks)
    panel.begin_control("blank")
    wait_for(app, panel)
    blank = panel.adapter.controls["blank"]
    assert blank is not None, panel.status.text()
    loaded = panel.settings_editor.read_settings()
    loaded["condition"].update(condition_id="Arbitrary later label", temperature_k="Not measured")
    panel.settings_editor.apply_settings(loaded)
    assert panel.start_button.isEnabled(), panel.validation.text()
    panel.begin("measurement")
    wait_for(app, panel)
    assert panel.result is not None, panel.status.text()
    assert "automatic_dark" not in panel.result
    assert panel.result["spectra"][0].quantity == "sequential_blank_absorbance"
    panel.adapter.controls["blank"] = None
    panel.load_run(blank["path"])
    wait_for(app, panel)
    assert panel.adapter.controls["blank"]["run_id"] == blank["run_id"]


def test_stop_uses_shared_worker_and_preserves_partial_run(app, tabs):
    from control_app.measurement_modules.steady_state_slow_scan.runner import SyntheticSlowScanBackend
    from control_app.measurement_modules.steady_state_slow_scan.persistence import load_run
    panel = tabs[0][0].widget
    entered = Event()
    class SlowPreparation(SyntheticSlowScanBackend):
        def prepare(self, plan, compiled, check, report):
            super().prepare(plan, compiled, check, report)
            entered.set()
            while True:
                time.sleep(.005)
                check()
    panel.settings_editor.apply_settings(settings())
    inject_backend(panel, SlowPreparation)
    panel.begin("measurement")
    assert entered.wait(5)
    assert panel.close_blockers()
    panel.request_abort("Stop from UI test")
    wait_for(app, panel)
    record = panel.adapter.runner.last_result
    assert load_run(record["path"])["status"] == "cancelled"
    assert record["restoration"]["safe_verified"]
    assert not panel.close_blockers()
    assert panel.context.ownership.snapshot()["state"] == "free"
    panel.new_run()
    assert panel.start_button.isEnabled()


def test_capability_operation_contends_and_releases_without_complete_plan(app, tabs):
    from control_app.measurement_host.ownership import OwnershipError
    from control_app.measurement_modules.steady_state_slow_scan.runner import SyntheticSlowScanBackend
    first, second = (handle.widget for handle in tabs[0])
    entered, finish = Event(), Event()
    class Backend(SyntheticSlowScanBackend):
        def discover(self, check):
            entered.set()
            while not finish.wait(.005):
                check()
            self.readbacks = {"t660_frame_capacity": 8192}
            return self.readbacks
    inject_backend(first, Backend)
    inject_backend(second, Backend)
    first.settings_editor.lower.setValue(2000.)
    first.settings_editor.override_inputs["filter_order"].setText("unfinished number")
    assert first.plan is None
    try:
        first.begin_control("capability")
        assert entered.wait(5)
        with pytest.raises(OwnershipError):
            second.begin_control("capability")
        assert first.snapshot.operation.hardware
    finally:
        finish.set()
        wait_for(app, first)
    assert first.adapter.readbacks["t660_frame_capacity"] == 8192
    assert first.context.ownership.snapshot()["state"] == "free"


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
