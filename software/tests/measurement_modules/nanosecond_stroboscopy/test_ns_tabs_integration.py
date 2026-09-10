"""Compact production tabs and explicit simulator injection; no real instruments."""
from copy import deepcopy
from pathlib import Path
import time

import numpy as np
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
    deadline = time.monotonic() + 45
    while panel.command_running():
        app.processEvents()
        if time.monotonic() > deadline:
            pytest.fail("UI operation timed out: " + panel.status.text())
        time.sleep(.005)
    app.processEvents()


@pytest.fixture
def ns_factory(tmp_path):
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_host.ownership import HardwareCoordinator
    preferences, calls = {}, []
    root = [tmp_path / "output"]
    def forbidden_factory(**kwargs):
        calls.append(kwargs)
        raise AssertionError("Physical factory access during simulator/UI verification")
    factory = ContextFactory(
        configuration_provider=lambda: {}, real_device_factories={"hf2li": forbidden_factory},
        preference_backend=preferences, save_root_provider=lambda: root[0],
        ownership=HardwareCoordinator(tmp_path / "instrument.lock"),
    )
    return factory, preferences, root, calls


@pytest.fixture
def ns_pair(ns_qt, ns_factory):
    from control_app.measurement_modules.nanosecond_stroboscopy.widgets import NanosecondPanel
    context = ns_factory[0].for_experiment("nanosecond_stroboscopy")
    pair = [NanosecondPanel(context.for_mode(mode), execution_mode="simulation") for mode in ("single", "dual")]
    yield pair
    for panel in pair:
        if panel.command_running():
            panel.request_abort("Test cleanup")
            wait_idle(ns_qt, panel)
        panel.close()
        panel.deleteLater()
    ns_qt.processEvents()


def test_ns_production_discovery_live_default_compact_no_review(ns_qt, ns_factory):
    from PySide6.QtWidgets import QPlainTextEdit
    from control_app.measurement_host.registry import discover_modules, create_registered_tabs
    from control_app.measurement_host.presentation import CompactMeasurementPanel
    discovery = discover_modules()
    descriptor = next(item for item in discovery.descriptors if item.experiment_id == "nanosecond_stroboscopy")
    created = create_registered_tabs([descriptor], ns_factory[0])
    assert not created.issues
    assert [handle.title for handle in created.handles] == ["Nanosecond Stroboscopy", "Dual-Detector Nanosecond Stroboscopy"]
    for handle in created.handles:
        panel = handle.widget
        assert isinstance(panel, CompactMeasurementPanel)
        assert panel.plan.settings.execution_mode == "connected"
        assert not hasattr(panel, "review")
        assert not hasattr(panel, "advanced_button")
        assert not panel.advanced_group.isCheckable()
        assert not panel.findChildren(QPlainTextEdit)
        assert set(panel.settings_widget.controls) == {"wavenumbers_cm1", "delays_ns", "repetitions", "cycle_interval_s"}
        assert all(control.currentText() == "Auto" for control in panel.settings_widget.override_inputs.values())
        assert len(panel.settings_widget.override_inputs) == (6 if panel.context.mode == "dual" else 3)
        assert panel.plan is not None
        assert not panel.start_button.isEnabled()
        panel.close()
        panel.deleteLater()
    assert ns_factory[3] == []


def test_ns_single_and_dual_simulated_workflow_start_without_review(ns_qt, ns_pair, ns_factory, tmp_path):
    single, dual = ns_pair
    single.begin_blank()
    wait_idle(ns_qt, single)
    assert single.adapter.blank and single.adapter.blank["status"] == "completed", single.status.text()
    assert dual.adapter.blank is None
    for panel in ns_pair:
        panel.begin("preliminary")
        wait_idle(ns_qt, panel)
        assert panel.preliminary, panel.status.text()
        assert panel.start_button.isEnabled(), panel.status.text()
        panel.begin("measurement")
    frozen = single.snapshot.operation.output_path
    ns_factory[2][0] = tmp_path / "next"
    single.output_location_changed(ns_factory[2][0])
    for panel in ns_pair:
        wait_idle(ns_qt, panel)
        assert panel.result and panel.result["status"] == "completed", panel.status.text()
        assert panel.result["result"]["coverage"].sum() > 0
        assert panel.result_note.text().startswith("Example data")
        assert panel.time_slice.input.suffix() == " ns"
        panel.time_slice.set_index(0)
        panel.time_slice.input.stepBy(1)
        assert panel.time_slice.index == 1
    assert Path(single.result["output_path"]) == frozen
    assert ns_factory[3] == []
    assert not dual.result["result"]["absolute_available"]
    assert dual.quantity.findData("absolute_absorbance") < 0
    settings = single.adapter.read_settings()
    saved = single.result["output_path"]
    single.new_run()
    assert single.preliminary is single.result is single.adapter.blank is None
    assert single.adapter.read_settings() == settings
    assert dual.result is not None
    single.load_run(saved)
    wait_idle(ns_qt, single)
    assert single.result["events"] and single.preliminary is None
    dual.load_run(saved)
    wait_idle(ns_qt, dual)
    assert "mode" in dual.status.text().lower()


def test_ns_baseline_reuse_ignores_metadata_and_averages_but_rechecks_timing(ns_qt, ns_pair):
    dual = ns_pair[1]
    dual.begin("preliminary")
    wait_idle(ns_qt, dual)
    assert dual.start_button.isEnabled(), dual.status.text()
    baseline = dual.preliminary
    original = dual.adapter.read_settings()
    metadata = deepcopy(original)
    metadata["metadata"] = {"run_label": "sample B", "notes": "Optional provenance"}
    metadata["repetitions"] += 1
    dual.adapter.apply_settings(metadata)
    dual.refresh_plan()
    assert dual.preliminary is baseline
    assert dual.start_button.isEnabled()
    changed = deepcopy(metadata)
    changed["cycle_interval_s"] *= 2
    dual.adapter.apply_settings(changed)
    dual.refresh_plan()
    assert not dual.start_button.isEnabled()
    dual.adapter.apply_settings(original)
    dual.refresh_plan()
    assert dual.start_button.isEnabled()


def test_ns_individual_auto_overrides_remain_auto_after_other_edits(ns_pair):
    single, dual = ns_pair
    controls = single.settings_widget
    controls.override_inputs["filter_order"].setCurrentText("2")
    assert controls.read_settings()["overrides"] == {"filter_order": 2}
    before = single.plan.resolved_settings.probe_period_s
    controls.controls["cycle_interval_s"].setValue(3.)
    assert controls.read_settings()["overrides"] == {"filter_order": 2}
    assert "probe_period_s" not in controls.override_inputs
    assert single.plan.resolved_settings.probe_period_s != before
    assert dual.adapter.read_settings()["overrides"] == {}
    assert "reference_hf2li_rate_hz" in dual.settings_widget.override_inputs
    assert "reference_hf2li_rate_hz" not in controls.override_inputs
    legacy = controls.read_settings()
    legacy["overrides"]["probe_period_s"] = 999.
    legacy["qcl"] = 2
    controls.apply_settings(legacy)
    single.refresh_plan()
    normalized = controls.read_settings()
    assert normalized["overrides"] == {"filter_order": 2}
    assert normalized["metadata"]["legacy_timing_overrides"]["probe_period_s"] == 999.
    assert normalized["qcl"] == 1
    assert single.plan.resolved_settings.probe_period_s != 999.
    controls.restore_auto()
    assert controls.read_settings()["overrides"] == {}


def test_ns_missing_optical_timing_still_displays_raw_map_and_programmed_kinetics(ns_pair):
    panel = ns_pair[1]
    values = np.array([[.1, .2, .3], [.2, .3, .4]])
    run = {"mode": "dual", "kind": "measurement", "events": [], "settings": {}, "result": {
        "wavenumbers_cm1": [1940., 1942.], "delays_ns": [-100., 0., 100.],
        "delta_a": values, "coverage": np.ones_like(values), "uncertainty": np.full_like(values, .01),
        "optical_delay_ns": np.full_like(values, np.nan), "fits": [], "controls": {}, "absolute_available": False,
    }}
    panel.show_result(run)
    kinetic = panel.plot.figure.axes[-1]
    assert kinetic.get_xlabel() == "Programmed delay (ns)"
    assert np.isfinite(kinetic.lines[0].get_ydata()).all()
    assert len(panel.plot.figure.axes) >= 3
    assert "Example data" not in panel.result_note.text()
    run["readbacks"] = {"execution": "simulation"}
    panel.show_result(run)
    assert panel.result_note.text() == "Example data"


def test_ns_plan_loading_incompatible_mode_and_native_baseline_support(ns_qt, ns_pair, tmp_path):
    single, dual = ns_pair
    plan_path = tmp_path / "single-plan.json"
    single.save_plan(plan_path)
    wait_idle(ns_qt, single)
    assert plan_path.exists()
    dual.load_plan(plan_path)
    wait_idle(ns_qt, dual)
    assert "mode" in dual.status.text().lower()
    dual.begin("preliminary")
    wait_idle(ns_qt, dual)
    incomplete = deepcopy(dual.preliminary)
    incomplete["events"] = incomplete["events"][:1]
    assert any("missing valid measured" in error for error in dual.adapter.validate_preliminary(incomplete, dual.plan))


def test_ns_instrument_change_invalidates_only_its_receiver(ns_qt, ns_pair):
    from control_app.measurement_host.interchange import DeviceConfigurationChange, InstrumentStateChange
    dual = ns_pair[1]
    dual.begin("preliminary")
    wait_idle(ns_qt, dual)
    assert dual.start_button.isEnabled()
    change = InstrumentStateChange(
        producer_instance_id="nanosecond_stroboscopy:single", recipients=("nanosecond_stroboscopy:dual",),
        changes=(DeviceConfigurationChange("hf2li", "reference_range", 1., 2.),), reason="Range changed")
    dual.instrument_state_changed(change)
    assert not dual.start_button.isEnabled()
    assert "reference_range" in dual.status.text()
    restored = InstrumentStateChange(
        producer_instance_id="nanosecond_stroboscopy:single", recipients=("nanosecond_stroboscopy:dual",),
        changes=(DeviceConfigurationChange("hf2li", "reference_range", 2., 1.),), reason="Range restored")
    dual.instrument_state_changed(restored)
    assert dual.start_button.isEnabled()


def test_ns_compact_pages_fit_actual_app_without_outer_scrolling(ns_qt, tmp_path):
    from PySide6.QtGui import QFont, QFontDatabase
    from control_app.ui.contracts import blocked_handler
    from control_app.ui.main_window import ControlSystemMainWindow
    from control_app.measurement_host.ownership import HardwareCoordinator
    handler = blocked_handler("Compact UI verification; no hardware")
    handler.coordinator = HardwareCoordinator(tmp_path / "render.lock")
    previous_font = ns_qt.font()
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/arial.ttf")
    ns_qt.setFont(QFont("Arial", 9))
    window = ControlSystemMainWindow(handler, persist_settings=False)
    try:
        window.resize(1100, 780)
        window.show()
        for handle in window.measurement_lifecycle.handles:
            if handle.instance_id.startswith("nanosecond_stroboscopy:"):
                window.tabs.setCurrentWidget(handle.widget)
                ns_qt.processEvents()
                assert window.width() == 1100 and window.height() == 780
                assert window.workspace_scroll.verticalScrollBar().maximum() == 0
                assert window.workspace_scroll.horizontalScrollBar().maximum() == 0
                assert handle.widget.plot.width() > handle.widget.left_panel.width()
                assert handle.widget.advanced_group.isVisible()
                assert handle.widget.settings_scroll.verticalScrollBar().maximum() == 0
                assert handle.widget.settings_scroll.horizontalScrollBar().maximum() == 0
                for control in handle.widget.settings_widget.override_inputs.values():
                    assert control.isVisibleTo(handle.widget)
    finally:
        window.deleteLater()
        ns_qt.processEvents()
        ns_qt.setFont(previous_font)
