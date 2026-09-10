"""Compact host integration and experiment data compatibility, without hardware."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from threading import Event
import json
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
    deadline = time.monotonic()+15
    while not check():
        app.processEvents()
        if time.monotonic() > deadline:
            pytest.fail("Host operation did not finish")
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
            self.store.finalize("complete")
            return {"capabilities": self.plan.capabilities.to_dict(), "complete": True}
        native = {"sample_time_s": np.array([0., .001, .002]), "wavenumber_cm1": np.array([1900., 1925., 1950.]),
                  "sample": np.array([.8, .7, .8]), "scan_index": np.zeros(3, dtype=np.int64)}
        if self.context.mode == "dual":
            native["reference"] = np.ones(3)
        self.store.save_chunk("unpumped-"+kind, native)
        self.store.finalize("complete")
        return {"status": "complete", "complete": True, "native": native, "metadata": self.store.metadata,
                "output_path": str(self.store.path)}

    def run(self, baseline=None, continuation=None):
        self.kind, self.baseline = "measurement", baseline
        while not self.gate.wait(.01):
            if self.cancelled.is_set():
                self.store.finalize("stopped")
                return {"status": "stopped", "output_path": str(self.store.path)}
        self.progress({"stage": "saving", "message": "Saving", "fraction": .95, "elapsed_s": 4.})
        self.store.finalize("complete")
        return {"status": "complete", "output_path": str(self.store.path),
                "data": {"processed": {"time_s": [-.1, .001, 1., 100.], "wavenumber_cm1": [1925.]*4,
                    "delta_absorbance": [0., .2, .1, .05], "ratio": [.8]*4,
                    "scan_index": [0, 1, 2, 3], "direction": [1, 1, 1, 1]}}}


def create_widget(tmp_path, mode="single", roots=None, *, runner_factory=InjectedRunner):
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_modules.single_pump_scan_burst.widgets import SinglePumpScanBurstWidget
    roots = roots or [tmp_path]
    context = ContextFactory(save_root_provider=lambda: roots[0], ownership=object()).for_experiment("single_pump_scan_burst").for_mode(mode)
    return SinglePumpScanBurstWidget(context, runner_factory=runner_factory, hardware=False)


def test_discovery_exact_tabs_compact_essentials_no_operator_gates(qt_app, tmp_path):
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_host.registry import discover_modules, create_registered_tabs
    from control_app.measurement_host.presentation import CompactMeasurementPanel
    from control_app.measurement_modules.single_pump_scan_burst.widgets import ESSENTIALS
    from PySide6.QtWidgets import QDoubleSpinBox, QGroupBox
    def forbidden(**kwargs):
        raise AssertionError("Construction must not instantiate a device")
    factory = ContextFactory(save_root_provider=lambda: tmp_path, ownership=object(), real_device_factories={"hf2li": forbidden})
    descriptors = [item for item in discover_modules().descriptors if item.experiment_id == "single_pump_scan_burst"]
    result = create_registered_tabs(descriptors, factory)
    assert not result.issues
    assert [(item.instance_id, item.title) for item in result.handles] == [
        ("single_pump_scan_burst:single", "Single-Pump Scan Bursts"),
        ("single_pump_scan_burst:dual", "Dual-Detector Single-Pump Scan Bursts")]
    first, second = [item.widget for item in result.handles]
    assert isinstance(first, CompactMeasurementPanel)
    assert first.adapter is not second.adapter
    assert first.plan.valid and second.plan.valid
    expected = {item[0] for item in ESSENTIALS}
    assert {item.objectName() for item in first.settings_widget.findChildren(QDoubleSpinBox)} == expected
    assert len(expected) == 5
    for panel in (first, second):
        assert not hasattr(panel, "review")
        assert not hasattr(panel.settings_widget, "execution")
        assert "sample_id" not in panel.settings_widget.controls
        assert "measured_temperature_k" not in panel.settings_widget.controls
        assert "hardware_evidence" not in panel.settings_widget.controls
        panel._capability_check_attempted = True
        panel.show()
        qt_app.processEvents()
        assert isinstance(panel.advanced_content, QGroupBox)
        assert not panel.advanced_content.isCheckable()
        assert panel.advanced_content.isVisible()
        assert all(control.isVisible() for control in panel.settings_widget.override_controls.values())
        assert "qcl" not in panel.settings_widget.controls
        assert "probe_current_ma" not in panel.settings_widget.controls
        assert "timing_rate_hz" not in panel.settings_widget.controls
        assert len(panel.settings_widget.override_controls) == (6 if panel.context.mode == "single" else 9)
        assert panel.preliminary_button.isEnabled()
        assert panel.adapter.hardware_required("measurement", {"_execution": "simulated"})
        assert not panel.adapter.hardware_required("load_blank", {})
        panel.hide()
        panel.deleteLater()


def test_sample_without_blank_starts_and_compatible_data_are_reused(qt_app, tmp_path):
    panel = create_widget(tmp_path)
    other = create_widget(tmp_path, "dual")
    assert panel.preliminary_button.isEnabled()
    panel.begin("preliminary")
    wait_for(qt_app, lambda: not panel.command_running())
    first = panel.preliminary
    assert first and panel.start_button.isEnabled()
    assert panel.adapter.blank is None
    panel.settings_widget.controls["observation_limit_s"].setValue(2400.)
    assert panel.preliminary is first and panel.start_button.isEnabled()
    speed = panel.settings_widget.controls["scan_speed_cm1_s"]
    speed.setValue(4000.)
    assert not panel.start_button.isEnabled()
    speed.setValue(5000.)
    assert panel.preliminary is first and panel.start_button.isEnabled()
    panel.begin_blank()
    wait_for(qt_app, lambda: not panel.command_running())
    assert panel.adapter.blank and panel.start_button.isEnabled()
    panel.begin("measurement")
    wait_for(qt_app, lambda: not panel.command_running())
    assert panel.result and other.result is None
    assert InjectedRunner.calls[-1].baseline["blank"] is not None
    assert panel.preliminary is first and panel.start_button.isEnabled()
    entered = deepcopy(panel.adapter.read_settings())
    panel.new_run()
    assert panel.result is panel.preliminary is panel.adapter.blank is None
    assert panel.adapter.read_settings() == entered
    assert not other.command_running()
    panel.deleteLater()
    other.deleteLater()


def test_loaded_sample_and_blank_reuse_without_dialog_gate(qt_app, tmp_path):
    producer = create_widget(tmp_path)
    producer.begin("preliminary")
    wait_for(qt_app, lambda: not producer.command_running())
    sample_path = producer.preliminary["output_path"]
    producer.begin_blank()
    wait_for(qt_app, lambda: not producer.command_running())
    blank_path = producer.adapter.blank["output_path"]
    consumer = create_widget(tmp_path)
    consumer.load_run(sample_path)
    wait_for(qt_app, lambda: not consumer.command_running())
    assert consumer.preliminary and consumer.start_button.isEnabled(), consumer.status.text()
    sample = consumer.preliminary
    consumer.settings_widget.controls["observation_limit_s"].setValue(2400.)
    assert consumer.preliminary is sample and consumer.start_button.isEnabled()
    consumer.load_run(blank_path)
    wait_for(qt_app, lambda: not consumer.command_running())
    assert consumer.adapter.blank is not None and consumer.start_button.isEnabled()
    producer.deleteLater()
    consumer.deleteLater()


def test_device_check_can_recover_while_an_advanced_override_is_invalid(qt_app, tmp_path):
    panel = create_widget(tmp_path)
    rate = panel.settings_widget.controls["sample_rate_hz"]
    rate.setEditText("invalid rate")
    assert panel.plan is None
    assert not panel.preliminary_button.isEnabled()
    assert panel.capabilities_button.isEnabled()
    panel.begin_capabilities()
    wait_for(qt_app, lambda: not panel.command_running())
    assert InjectedRunner.calls[-1].kind == "capabilities"
    assert panel.adapter.capabilities is not None
    assert rate.currentText() == "invalid rate"
    assert panel.plan is None
    rate.setEditText("Automatic")
    assert panel.plan is not None and panel.preliminary_button.isEnabled()
    panel.deleteLater()


def test_show_while_instrument_owned_retains_owner_and_allows_later_check(qt_app, tmp_path):
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_host.ownership import HardwareCoordinator
    from control_app.measurement_modules.single_pump_scan_burst.widgets import SinglePumpScanBurstWidget
    cancelled = []
    coordinator = HardwareCoordinator(tmp_path / "instrument.lock")
    owner = coordinator.acquire("other:operation", cancel=lambda reason: cancelled.append(reason))
    class OwnedCapabilityRunner(InjectedRunner):
        def prepare(self, *, kind):
            result = super().prepare(kind=kind)
            self.context.ownership.release(self.operation.ownership, safe_verified=True, preservation_verified=True)
            return result
    def forbidden(**kwargs):
        raise AssertionError("The UI must not instantiate hardware")
    context = ContextFactory(save_root_provider=lambda: tmp_path, ownership=coordinator,
        real_device_factories={"hf2li": forbidden}).for_experiment("single_pump_scan_burst").for_mode("single")
    panel = SinglePumpScanBurstWidget(context, runner_factory=OwnedCapabilityRunner)
    panel.show()
    qt_app.processEvents()
    assert panel.status.text().startswith("Instrument busy")
    assert not panel._capability_check_attempted and not panel.command_running()
    coordinator.assert_owner(owner)
    assert not cancelled
    coordinator.release(owner, safe_verified=True, preservation_verified=True)
    panel.capabilities_button.click()
    wait_for(qt_app, lambda: not panel.command_running())
    assert panel._capability_check_attempted
    assert panel.adapter.capabilities is not None
    assert coordinator.snapshot()["state"] == "free"
    panel.hide()
    panel.deleteLater()


def test_auto_overrides_remain_independent_and_saved_plan_keeps_auto(qt_app, tmp_path):
    panel = create_widget(tmp_path, "dual")
    requested = panel.adapter.read_settings()
    assert requested["sample_rate_hz"] is None and requested["reference_rate_hz"] is None
    panel.settings_widget.controls["sample_rate_hz"].setEditText("10000")
    changed = panel.adapter.read_settings()
    assert changed["sample_rate_hz"] == 10000. and changed["reference_rate_hz"] is None
    assert changed["early_scan_count"] is None and changed["scans_per_burst"] is None
    assert panel.plan.settings.sample_rate_hz == 10000.
    path = tmp_path / "independent-auto.json"
    panel.adapter.save_plan(path, changed, panel.plan)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["settings"]["reference_rate_hz"] is None
    assert saved["settings"]["early_scan_count"] is None
    with pytest.raises(FileExistsError):
        panel.adapter.save_plan(path, changed, panel.plan)
    other = create_widget(tmp_path)
    with pytest.raises(ValueError, match="mode"):
        other.adapter.load_plan(path)
    panel.deleteLater()
    other.deleteLater()


def test_probe_display_units_saved_channel_normalization_and_duty_plumbing(qt_app, tmp_path):
    panel = create_widget(tmp_path)
    rate = panel.settings_widget.controls["probe_rate_hz"]
    width = panel.settings_widget.controls["probe_pulse_width_s"]
    rate.setEditText("1000")
    width.setEditText("400")
    assert panel.plan is None
    assert "duty" in panel.validation.text().lower()
    rate.setEditText("300")
    width.setEditText("150")
    assert panel.plan is None
    assert "Shorten Pulse width" in panel.validation.text()
    width.setEditText("100")
    assert panel.plan is not None
    requested = panel.adapter.read_settings()
    assert requested["probe_rate_hz"] == 300000.
    assert requested["probe_pulse_width_s"] == pytest.approx(100e-9)
    assert requested["qcl"] == panel.plan.settings.qcl == 1
    assert dict(panel.adapter.summarize_plan(panel.plan))["Pulse duty"].startswith("3%")
    path = tmp_path / "fixed-channel.json"
    panel.adapter.save_plan(path, requested, panel.plan)
    legacy = json.loads(path.read_text(encoding="utf-8"))
    legacy["settings"]["qcl"] = 3
    path.write_text(json.dumps(legacy), encoding="utf-8")
    restored = panel.adapter.load_plan(path)
    assert restored["qcl"] == 1
    assert json.loads(path.read_text(encoding="utf-8"))["settings"]["qcl"] == 3
    panel.adapter.apply_settings(restored)
    assert rate.currentText() == "300" and width.currentText() == "100"
    panel.begin("preliminary")
    wait_for(qt_app, lambda: not panel.command_running())
    acquisition = InjectedRunner.calls[-1]
    assert acquisition.plan.settings.qcl == 1
    assert acquisition.plan.settings.probe_rate_hz == 300000.
    assert acquisition.plan.settings.probe_pulse_width_s == pytest.approx(100e-9)
    assert acquisition.operation.settings["probe_rate_hz"] == 300000.
    assert acquisition.operation.settings["probe_pulse_width_s"] == pytest.approx(100e-9)
    panel.deleteLater()


def test_supported_filter_choices_keep_each_detector_independent(qt_app, tmp_path):
    from control_app.measurement_modules.single_pump_scan_burst.settings import Capabilities
    panel = create_widget(tmp_path, "dual")
    settings = panel.settings_widget
    settings.set_capabilities(Capabilities(sample_rates_hz=(10000., 20000.), reference_rates_hz=(5000.,),
        sample_filter_orders=(1, 2), reference_filter_orders=(1, 3),
        sample_timeconstants_by_order={1: (1e-6,), 2: (2e-6,)},
        reference_timeconstants_by_order={1: (3e-6,), 3: (4e-6,)}))
    controls = settings.override_controls
    assert float(controls["sample_rate_hz"].itemText(1)) == 10000.
    assert float(controls["reference_rate_hz"].itemText(1)) == 5000.
    controls["hf2_filter_order"].setEditText("2")
    assert controls["hf2_filter_tc_s"].itemText(1) == "2e-06"
    assert controls["reference_filter_tc_s"].itemText(1) == "3e-06"
    values = settings.read_settings()
    assert values["hf2_filter_order"] == 2
    assert values["reference_filter_order"] is values["reference_filter_tc_s"] is None
    panel.deleteLater()


def test_removed_engineering_overrides_restore_auto_without_editing_old_plan(qt_app, tmp_path):
    panel = create_widget(tmp_path, "dual")
    values = panel.adapter.read_settings()
    values.update(qcl=3, early_scan_count=99, later_burst_count=2, final_scan_count=12,
        scan_interval_s=.5, first_scan_delay_s=.02, sample_input_range_v=.1,
        reference_input_range_v=.2, timing_rate_hz=7000., probe_current_ma=123.,
        pump_fire_to_q_s=.01, schedule_kind="information_based", later_burst_times_s=[1., 2.],
        sample_rate_hz=10000., hf2_filter_order=2, reference_rate_hz=None,
        probe_rate_hz=300000., probe_pulse_width_s=100e-9, scans_per_burst=2)
    panel.adapter.apply_settings(values)
    restored = panel.adapter.read_settings()
    for field in ("early_scan_count", "later_burst_count", "final_scan_count", "scan_interval_s",
                  "first_scan_delay_s", "sample_input_range_v", "reference_input_range_v",
                  "timing_rate_hz", "probe_current_ma", "pump_fire_to_q_s"):
        assert restored[field] is None
    assert restored["qcl"] == 1
    assert restored["schedule_kind"] == "logarithmic" and restored["later_burst_times_s"] == ()
    assert restored["sample_rate_hz"] == 10000. and restored["hf2_filter_order"] == 2
    assert restored["reference_rate_hz"] is None and restored["scans_per_burst"] == 2
    path = tmp_path / "old-engineering-settings.json"
    record = {"schema_version": "single-pump-scan-burst-plan/1", "experiment_id": "single_pump_scan_burst",
              "mode": "dual", "settings": values}
    path.write_text(json.dumps(record), encoding="utf-8")
    loaded = panel.adapter.load_plan(path)
    assert loaded["probe_current_ma"] is loaded["timing_rate_hz"] is None
    assert loaded["probe_rate_hz"] == 300000. and loaded["probe_pulse_width_s"] == pytest.approx(100e-9)
    assert json.loads(path.read_text(encoding="utf-8"))["settings"]["probe_current_ma"] == 123.
    panel.deleteLater()


def test_frozen_output_and_abort_are_scoped(qt_app, tmp_path):
    roots = [tmp_path / "first"]
    panel = create_widget(tmp_path, "dual", roots)
    other = create_widget(tmp_path)
    panel.begin("preliminary")
    wait_for(qt_app, lambda: not panel.command_running())
    InjectedRunner.gate.clear()
    try:
        panel.begin("measurement")
        snapshot = panel.snapshot
        roots[0] = tmp_path / "second"
        panel.output_location_changed(roots[0])
        assert snapshot.operation.output_path.is_relative_to(tmp_path / "first")
        assert not panel.settings_widget.isEnabled()
        assert panel.close_blockers()
        wait_for(qt_app, lambda: panel.adapter._runner is not None)
        panel.request_abort("Stopped by user")
        wait_for(qt_app, lambda: not panel.command_running())
    finally:
        InjectedRunner.gate.set()
    assert panel.status.text().startswith("Acquisition stopped")
    assert not other.command_running()
    assert panel.preliminary is not None
    panel.deleteLater()
    other.deleteLater()


def test_legacy_simulator_preferences_restore_live_automatic_values(qt_app, tmp_path):
    panel = create_widget(tmp_path)
    values = panel.adapter.read_settings()
    values.update(example_only=True, _execution="simulated", probe_rate_hz=123., probe_current_ma=999., sample_rate_hz=42.)
    panel.adapter.apply_settings(values)
    restored = panel.adapter.read_settings()
    assert not restored["example_only"]
    assert "_execution" not in restored
    assert restored["probe_rate_hz"] is restored["probe_current_ma"] is restored["sample_rate_hz"] is None
    assert restored["scan_start_cm1"] == values["scan_start_cm1"]
    panel.deleteLater()


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_connected_workflow_with_injected_virtual_devices_no_blank_gate(qt_app, tmp_path, mode):
    from control_app.measurement_modules.single_pump_scan_burst.settings import Settings
    from control_app.measurement_modules.single_pump_scan_burst.persistence import load_run
    panel = create_widget(tmp_path, mode, runner_factory=None)
    settings = Settings(mode=mode, early_observation_s=.05, observation_limit_s=.5, later_burst_count=2, scans_per_burst=2)
    panel.adapter.apply_settings(settings.to_dict())
    assert panel.plan.valid, panel.validation.text()
    panel.begin("preliminary")
    wait_for(qt_app, lambda: not panel.command_running())
    assert panel.preliminary and panel.start_button.isEnabled(), panel.status.text()
    panel.begin("measurement")
    wait_for(qt_app, lambda: not panel.command_running())
    assert panel.result and panel.result["status"] == "complete", panel.status.text()
    result = load_run(panel.result["output_path"])
    assert len([event for event in result["events"] if event["kind"] == "pump_intent"]) == 1
    assert panel.plot.result["label"] == "ΔAbsorbance"
    assert panel.start_button.isEnabled()
    export = tmp_path / (mode + "-quantitative.csv")
    panel.adapter.export_run(export, panel.result)
    assert "delta_absorbance" in export.read_text(encoding="utf-8").splitlines()[0]
    panel.deleteLater()


def test_native_precision_and_electrical_time_labels_with_sparse_log_support(qt_app):
    from matplotlib.figure import Figure
    from control_app.measurement_modules.single_pump_scan_burst.widgets import BurstPlotAdapter, _display_points
    ticks = np.array([2**60+1, 2**60+2, 2**60+3], dtype=np.uint64)
    native = {"metadata": {"mode": "single"}, "epoch": {"pump_time_s": 1., "pump_timestamp_ticks": 2**60,
        "clockbase_hz": 1000000000, "electrical_observed": True}, "native": {
        "native_sample_ticks": ticks, "sample_time_s": [1., 1., 1.], "clockbase_hz": 1000000000,
        "wavenumber_cm1": [1934.]*3, "sample": [.8, .7, .8]}}
    points = _display_points(native)
    np.testing.assert_allclose(points["time"], [1e-9, 2e-9, 3e-9], rtol=0, atol=1e-24)
    assert points["time_label"] == "Time from trigger (s)"
    raw = {"metadata": {"mode": "dual"}, "summary": {"time_reference": "electrical_trigger"}, "processed": {
        "time_s": [-1., 0., 1e-9, .001, 1000.], "wavenumber_cm1": [1934.]*5,
        "ratio": [1., 1., .5, np.nan, .9], "valid": [True, True, True, False, True],
        "scan_index": [0, 1, 2, 3, 4], "direction": [1]*5}}
    points = _display_points(raw)
    renderer = BurstPlotAdapter()
    renderer.view = "Positive-time logarithmic kinetics"
    renderer.wavenumbers = np.array([1934.])
    figure = Figure()
    renderer.draw(figure, points)
    assert figure.axes[0].get_xscale() == "log"
    assert np.array_equal(figure.axes[0].lines[0].get_xdata(), [1e-9, .001, 1000.])
    assert np.isnan(figure.axes[0].lines[0].get_ydata()[1])
    assert figure.axes[0].lines[0].get_linestyle() == "None"
    assert figure.axes[0].get_xlabel() == "Time from trigger (s)"


def test_kinetic_slice_uses_actual_nearest_point_per_scan_within_resolution(qt_app):
    from matplotlib.figure import Figure
    from control_app.measurement_modules.single_pump_scan_burst.widgets import BurstPlotAdapter, _display_points
    points = _display_points({"metadata": {"mode": "dual", "actual_settings": {"wavenumber_matching_tolerance_cm1": .05}},
        "processed": {"time_s": [0., .1, .2, 1., 1.1, 1.2], "wavenumber_cm1": [1900., 1901., 1902., 1900.02, 1901.02, 1902.02],
            "delta_absorbance": [1., 2., 3., 4., 5., 6.], "scan_index": [0, 0, 0, 1, 1, 1]}})
    renderer = BurstPlotAdapter()
    renderer.wavenumbers = np.asarray([1901.])
    figure = Figure()
    renderer.draw(figure, points)
    np.testing.assert_array_equal(figure.axes[0].lines[0].get_xdata(), [.1, 1.1])
    np.testing.assert_array_equal(figure.axes[0].lines[0].get_ydata(), [2., 5.])
