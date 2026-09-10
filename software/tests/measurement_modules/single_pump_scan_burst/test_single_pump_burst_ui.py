"""Real host tab construction and interaction; injected operations only."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from threading import Event
import time

import numpy as np
import pytest


@pytest.fixture
def qt_app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def wait_for(app, check):
    limit = time.monotonic()+10
    while not check():
        app.processEvents()
        if time.monotonic() > limit:
            pytest.fail("Host worker did not finish")
        time.sleep(.005)
    app.processEvents()


class InjectedRunner:
    calls = []
    gate = Event()
    gate.set()

    def __init__(self, context, plan, operation, *, store, progress):
        self.context, self.plan, self.operation = context, plan, operation
        self.store, self.progress = store, progress
        self.cancelled = Event()
        self.calls.append(self)

    def cancel(self, reason):
        self.cancelled.set()

    def prepare(self, *, kind):
        self.kind = kind
        if kind == "capabilities":
            from control_app.measurement_modules.single_pump_scan_burst.settings import Capabilities
            self.store.finalize("completed")
            return {"capabilities": Capabilities().to_dict(), "complete": True}
        native = {"sample_time_s": np.array([0., .001, .002]), "wavenumber_cm1": np.array([1900., 1925., 1950.]),
                  "sample": np.array([.8, .7, .8]), "scan_index": np.zeros(3, dtype=np.int64)}
        if self.context.mode == "dual":
            native["reference"] = np.ones(3)
        self.store.save_chunk(kind, native)
        self.store.finalize("completed")
        return {"complete": True, "native": native, "output_path": str(self.store.path)}

    def run(self, review, baseline=None, continuation=None):
        self.kind, self.review, self.baseline = "measurement", review, baseline
        while not self.gate.wait(.01):
            if self.cancelled.is_set():
                self.store.finalize("stopped")
                return {"status": "stopped", "output_path": str(self.store.path)}
        self.progress({"stage": "saving", "message": "Native records", "fraction": .95,
                       "elapsed_s": 4., "remaining_s": 1., "remaining_basis": "processing estimate"})
        self.store.finalize("completed")
        return {"status": "completed", "output_path": str(self.store.path),
                "data": {"processed": {"time_s": [-.1, .001, 1., 100.], "wavenumber_cm1": [1925.]*4,
                    "delta_absorbance": [0., .2, .1, .05], "sample": [.8]*4,
                    "scan_index": [0, 1, 2, 3], "direction": [1, 1, 1, 1]}}}


def create_widget(tmp_path, mode="single", roots=None):
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_modules.single_pump_scan_burst.widgets import SinglePumpScanBurstWidget
    roots = roots or [tmp_path]
    context = ContextFactory(save_root_provider=lambda: roots[0], ownership=object()).for_experiment("single_pump_scan_burst").for_mode(mode)
    panel = SinglePumpScanBurstWidget(context, runner_factory=InjectedRunner)
    panel.settings_widget.load_example()
    return panel


def test_real_package_discovery_constructs_exact_two_tabs_without_devices(qt_app, tmp_path):
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_host.registry import discover_modules, create_registered_tabs
    def forbidden(**kwargs):
        raise AssertionError("Construction must not instantiate any device")
    factory = ContextFactory(save_root_provider=lambda: tmp_path, ownership=object(),
                             real_device_factories={"hf2li": forbidden, "mircat": forbidden})
    descriptors = [item for item in discover_modules().descriptors if item.experiment_id == "single_pump_scan_burst"]
    result = create_registered_tabs(descriptors, factory)
    assert not result.issues
    assert [(item.instance_id, item.title) for item in result.handles] == [
        ("single_pump_scan_burst:single", "Single-Pump Scan Bursts"),
        ("single_pump_scan_burst:dual", "Dual-Detector Single-Pump Scan Bursts")]
    first, second = [item.widget for item in result.handles]
    assert first.adapter is not second.adapter
    assert first.settings_widget is not second.settings_widget
    assert first.context.preferences.namespace == "measurements/single_pump_scan_burst/single/v1/"
    assert second.context.preferences.namespace == "measurements/single_pump_scan_burst/dual/v1/"
    assert not first.start_button.isEnabled()
    assert first.capabilities_button.isEnabled()  # Discovery can resolve an incomplete plan.
    for panel in (first, second):
        panel.deleteLater()


def test_single_blank_review_start_output_freeze_invalidation_and_new_run(qt_app, tmp_path):
    roots = [tmp_path / "initial"]
    panel = create_widget(tmp_path, roots=roots)
    other = create_widget(tmp_path, "dual")
    assert panel.plan is not None and other.plan is not None
    assert not panel.preliminary_button.isEnabled()
    with pytest.raises(ValueError, match="blank"):
        panel.begin("preliminary")
    panel.begin_blank()
    wait_for(qt_app, lambda: not panel.command_running())
    assert panel.adapter.blank["complete"] and panel.preliminary is None
    assert panel.preliminary_button.isEnabled()
    panel.begin("preliminary")
    wait_for(qt_app, lambda: not panel.command_running())
    assert panel.preliminary and not panel.start_button.isEnabled()
    panel.review.setChecked(True)
    InjectedRunner.gate.clear()
    try:
        panel.begin("measurement")
        snapshot = panel.snapshot
        assert panel.command_running() and panel.close_blockers()
        roots[0] = tmp_path / "different"
        panel.output_location_changed(roots[0])
        assert snapshot.operation.output_path.is_relative_to(tmp_path / "initial")
        assert not snapshot.operation.output_path.is_relative_to(roots[0])
        assert not panel.settings_widget.isEnabled()
    finally:
        InjectedRunner.gate.set()
        wait_for(qt_app, lambda: not panel.command_running())
    assert panel.result and other.result is None and other.adapter.blank is None
    assert panel.plot.result is not None
    old = deepcopy(panel.adapter.read_settings())
    panel.settings_widget.controls["scan_speed_cm1_s"].setText("4000")
    assert panel.preliminary is None and not panel.review.isChecked()
    assert "scan_speed_cm1_s" in panel.blank_status.text()
    panel.adapter.apply_settings(old)
    assert panel.preliminary_button.isEnabled() and not panel.review.isChecked()
    panel.new_run()
    assert panel.result is panel.preliminary is panel.adapter.blank is None
    assert panel.adapter.read_settings() == old
    assert not panel.plot.figure.axes
    panel.deleteLater()
    other.deleteLater()


def test_dual_no_blank_independent_cancel_and_plan_schema(qt_app, tmp_path):
    panel = create_widget(tmp_path, "dual")
    other = create_widget(tmp_path, "single")
    assert panel.preliminary_button.isEnabled()
    panel.begin("preliminary")
    wait_for(qt_app, lambda: not panel.command_running())
    assert panel.preliminary and panel.adapter.blank is None
    panel.review.setChecked(True)
    InjectedRunner.gate.clear()
    try:
        panel.begin("measurement")
        wait_for(qt_app, lambda: panel.adapter._runner is not None)
        panel.request_abort("Stopped by user")
        wait_for(qt_app, lambda: not panel.command_running())
    finally:
        InjectedRunner.gate.set()
    assert panel.status.text().startswith("Acquisition stopped")
    assert not other.command_running() and other.adapter._runner is None
    path = tmp_path / "dual-plan.json"
    panel.adapter.save_plan(path, panel.adapter.read_settings(), panel.plan)
    with pytest.raises(ValueError, match="mode"):
        other.adapter.load_plan(path)
    with pytest.raises(FileExistsError):
        panel.adapter.save_plan(path, panel.adapter.read_settings(), panel.plan)
    panel.deleteLater()
    other.deleteLater()


def test_native_log_plot_excludes_baseline_and_preserves_sparse_support(qt_app):
    from matplotlib.figure import Figure
    from control_app.measurement_modules.single_pump_scan_burst.widgets import BurstPlotAdapter, _display_points
    raw = {"processed": {"time_s": [-1., 0., 1e-9, .001, 1000.], "wavenumber_cm1": [1934.]*5,
        "ratio": [1., 1., .5, np.nan, .9], "valid": [True, True, True, False, True],
        "scan_index": [0, 1, 2, 3, 4], "direction": [1]*5}}
    points = _display_points(raw)
    renderer = BurstPlotAdapter()
    renderer.view = "Positive-time logarithmic kinetics"
    renderer.wavenumbers = np.array([1934.])
    figure = Figure()
    renderer.draw(figure, points)
    axes = figure.axes[0]
    assert axes.get_xscale() == "log"
    assert np.array_equal(axes.lines[0].get_xdata(), [1e-9, .001, 1000.])
    assert np.isnan(axes.lines[0].get_ydata()[1])
    assert axes.lines[0].get_linestyle() == "None"  # No curve bridges unobserved waits.
    assert "Reference-normalized" in axes.get_ylabel()
    assert "Absorbance" not in axes.get_ylabel()
    points["burst"] = np.array([0, 0, 0, 0, 1])
    renderer.view = "Early linear kinetics"
    early = Figure()
    renderer.draw(early, points)
    assert early.axes[0].get_xscale() == "linear"
    assert np.array_equal(early.axes[0].lines[0].get_xdata(), [-1., 0., 1e-9, .001])


def test_explicit_capabilities_check_uses_host_worker_without_optics(qt_app, tmp_path):
    panel = create_widget(tmp_path, "dual")
    panel.begin_capabilities()
    wait_for(qt_app, lambda: not panel.command_running())
    assert InjectedRunner.calls[-1].kind == "capabilities"
    assert panel.adapter.capabilities is not None
    assert panel.preliminary is None and not panel.review.isChecked()
    panel.deleteLater()


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_integrated_virtual_instruments_complete_guided_one_pump_run(qt_app, tmp_path, mode):
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_modules.single_pump_scan_burst.widgets import SinglePumpScanBurstWidget
    from control_app.measurement_modules.single_pump_scan_burst.settings import example_settings
    from control_app.measurement_modules.single_pump_scan_burst.persistence import load_run
    context = ContextFactory(save_root_provider=lambda: tmp_path, ownership=object()).for_experiment("single_pump_scan_burst").for_mode(mode)
    panel = SinglePumpScanBurstWidget(context)
    settings = replace(example_settings(mode), observation_limit_s=4., first_later_burst_s=.5,
                       later_burst_count=3, temperature_check_interval_s=.1)
    panel.settings_widget.apply_settings({**settings.to_dict(), "_execution": "simulated"})
    assert panel.plan is not None, panel.validation.text()
    if mode == "single":
        panel.begin_blank()
        wait_for(qt_app, lambda: not panel.command_running())
        assert panel.adapter.blank is not None, panel.status.text()
    panel.begin("preliminary")
    wait_for(qt_app, lambda: not panel.command_running())
    assert panel.preliminary is not None, panel.status.text()
    panel.review.setChecked(True)
    panel.begin("measurement")
    wait_for(qt_app, lambda: not panel.command_running())
    assert panel.result is not None, panel.status.text()
    assert panel.result["status"] == "complete"
    run = load_run(panel.result["output_path"])
    assert len([event for event in run["events"] if event["kind"] == "pump_intent"]) == 1
    assert len([event for event in run["events"] if event["kind"] == "pump_epoch_observed"]) == 1
    assert panel.plot.result is not None
    assert np.max(panel.plot.result["time"]) >= settings.observation_limit_s
    assert panel.plot.result["label"] == "ΔAbsorbance"
    assert panel.preliminary is None and not panel.review.isChecked() and not panel.start_button.isEnabled()
    assert settings.accepted_state_id in panel.adapter.used_accepted_states
    assert len(panel.summary.text().splitlines()) <= 7
    export = tmp_path / (mode + "-quantitative.csv")
    panel.adapter.export_run(export, panel.result)
    assert "delta_absorbance" in export.read_text(encoding="utf-8").splitlines()[0]
    panel.new_run()
    assert settings.accepted_state_id in panel.adapter.used_accepted_states
    assert "already has a pump" in panel.status.text()
    panel.deleteLater()


def test_explicit_continuation_uses_retained_epoch_without_replacement_pump(qt_app, tmp_path):
    import json
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_modules.single_pump_scan_burst.widgets import SinglePumpScanBurstWidget
    from control_app.measurement_modules.single_pump_scan_burst.settings import example_settings
    from control_app.measurement_modules.single_pump_scan_burst.persistence import load_run
    from control_app.measurement_modules.single_pump_scan_burst.runner import BurstRunner
    def stop_during_wait(context, plan, operation, *, store, progress):
        runner = BurstRunner(context, plan, operation, store=store)
        def update(message):
            progress(message)
            if runner.pump_intent and message.get("stage") == "recovery_wait":
                runner.cancel("Interrupted observation test")
        runner.callback = update
        return runner
    context = ContextFactory(save_root_provider=lambda: tmp_path, ownership=object()).for_experiment("single_pump_scan_burst").for_mode("dual")
    panel = SinglePumpScanBurstWidget(context, runner_factory=stop_during_wait)
    settings = replace(example_settings("dual"), observation_limit_s=4., first_later_burst_s=1., later_burst_count=3, temperature_check_interval_s=.1)
    panel.adapter.apply_settings({**settings.to_dict(), "_execution": "simulated"})
    panel.begin("preliminary")
    wait_for(qt_app, lambda: not panel.command_running())
    panel.review.setChecked(True)
    panel.begin("measurement")
    wait_for(qt_app, lambda: not panel.command_running())
    original_path = panel.snapshot.operation.output_path
    original = load_run(original_path)
    assert original["status"] == "stopped", panel.status.text()
    proof_path = tmp_path / "continuity-proof.json"
    proof_path.write_text(json.dumps({"accepted_by": "Named continuity reviewer", "uninterrupted_native_clock": True,
        "unchanged_sample_state": True, "native_now_s": original["checkpoint"]["state"]["epoch"]["pump_time_s"] + .6}), encoding="utf-8")
    panel.adapter.runner_factory = None
    panel.load_continuation(original_path, proof_path)
    wait_for(qt_app, lambda: not panel.command_running())
    assert panel.adapter.continuation is not None, panel.status.text()
    assert not panel.start_button.isEnabled() and "continuation" in panel.start_button.text()
    panel.review.setChecked(True)
    panel.begin("measurement")
    wait_for(qt_app, lambda: not panel.command_running())
    assert panel.result is not None and panel.result["status"] == "complete", panel.status.text()
    resumed = load_run(panel.result["output_path"])
    assert Path(resumed["output_path"]) != original_path
    assert not any(event["kind"] == "pump_intent" for event in resumed["events"])
    assert any(event["kind"] == "explicit_continuation" for event in resumed["events"])
    assert load_run(original_path)["status"] == "stopped"
    panel.deleteLater()


def test_accepted_sample_and_promoted_bundle_fill_only_supported_unset_values(qt_app, tmp_path):
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_host.interchange import SampleSpectralSelection, SourceRecord, SpectralWindow, save_sample_selection
    from control_app.measurement_modules.single_pump_scan_burst.widgets import SinglePumpScanBurstWidget
    from control_app.promoted_bundles import PromotedBundle
    bundle = PromotedBundle("selected-instrument-bundle", tmp_path, {"measurement_modules": {"single_pump_scan_burst": {
        "settings": {"sample_rate_hz": 8000., "scan_stop_cm1": 1929., "hardware_evidence": {"source_record": "qualified-recipe"}}}}})
    context = ContextFactory(save_root_provider=lambda: tmp_path, ownership=object(),
        promoted_bundle_loader=lambda identity: bundle).for_experiment("single_pump_scan_burst").for_mode("dual")
    panel = SinglePumpScanBurstWidget(context)
    panel.settings_widget.controls["scan_stop_cm1"].setText("1940")
    selection = SampleSpectralSelection("sample-selection-001", "sample-001", "steady_state_slow_scan:dual",
        SourceRecord("source-run", "retained/spectrum", "2026-09-09T00:00:00+00:00", "selection/1"),
        "77K-HRP-G-S", {"matrix_id": "qualified-matrix", "measured_temperature_k": 77.2,
                         "temperature_identity": "sample-thermometry-001", "accepted_state_id": "cryogenic-state-001"},
        (SpectralWindow(1901., 1915., 1907., .1), SpectralWindow(1920., 1930., 1925., .1)),
        "Named sample reviewer", "2026-09-09T00:00:00+00:00")
    path = tmp_path / "accepted-selection.json"
    save_sample_selection(selection, path)
    panel.load_sample_selection(path)
    values = panel.adapter.read_settings()
    assert values["scan_start_cm1"] == 1901. and values["scan_stop_cm1"] == 1940.
    assert values["plateau_band_windows_cm1"] == [[1901., 1915.], [1920., 1930.]]
    assert values["measured_temperature_k"] == 77.2 and values["matrix_id"] == "qualified-matrix"
    assert values["sample_rate_hz"] is None  # Sample acceptance does not establish instrument settings.
    values["promoted_bundle_ids"] = ["selected-instrument-bundle"]
    panel.adapter.apply_settings(values)
    panel._resolve_bundles()
    resolved = panel.adapter.read_settings()
    assert resolved["sample_rate_hz"] == 8000. and resolved["scan_stop_cm1"] == 1940.
    assert resolved["hardware_evidence"] == {"source_record": "qualified-recipe"}
    assert resolved["settings_sources"]["sample_rate_hz"] == "selected-instrument-bundle"
    assert panel.adapter.selected_records().sample_records[0]["selection_id"] == "sample-selection-001"
    assert panel.adapter.selected_records().calibration_records[0]["bundle_id"] == "selected-instrument-bundle"
    panel.deleteLater()
