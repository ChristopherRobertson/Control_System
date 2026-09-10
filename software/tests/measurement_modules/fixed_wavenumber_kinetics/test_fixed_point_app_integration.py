"""Actual module registration and guided workflow tests; no device I/O."""
from copy import deepcopy
from pathlib import Path
import time

import pytest

from control_app.measurement_host import ContextFactory
from control_app.measurement_host.ownership import HardwareCoordinator


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    instance = QApplication.instance() or QApplication([])
    yield instance
    instance.processEvents()


def wait(app, panel):
    deadline = time.monotonic()+25
    while panel.command_running():
        app.processEvents()
        if time.monotonic() > deadline:
            pytest.fail("Guided worker did not complete")
        time.sleep(.005)
    app.processEvents()


def tabs(tmp_path, **kwargs):
    from control_app.measurement_modules.fixed_wavenumber_kinetics.registration import create_tabs
    prefs = {}
    context = ContextFactory(save_root_provider=lambda: tmp_path, preference_backend=prefs,
                             ownership=HardwareCoordinator(tmp_path/"host.lock"), **kwargs).for_experiment("fixed_wavenumber_kinetics")
    return create_tabs(context), prefs


def test_fixed_point_real_pair_constructs_without_hardware_and_scopes_preferences(app, tmp_path):
    def forbidden(**_):
        pytest.fail("Construction touched a device")
    pair, prefs = tabs(tmp_path, real_device_factories={"hf2li": forbidden, "mircat": forbidden})
    from control_app.measurement_host.contracts import validate_handles
    from control_app.measurement_modules.fixed_wavenumber_kinetics.registration import DESCRIPTOR
    validate_handles(DESCRIPTOR, pair)
    assert [h.title for h in pair] == ["Fixed-Wavenumber Kinetics", "Dual-Detector Fixed-Wavenumber Kinetics"]
    assert [h.instance_id for h in pair] == ["fixed_wavenumber_kinetics:single", "fixed_wavenumber_kinetics:dual"]
    assert pair[0].widget.adapter is not pair[1].widget.adapter
    assert all(key.startswith("measurements/fixed_wavenumber_kinetics/") for key in prefs)
    assert not pair[0].widget.start_button.isEnabled()
    for handle in pair:
        handle.widget.deleteLater()


def test_fixed_point_package_is_discovered_and_activated_by_unmodified_host(app, tmp_path):
    from control_app.measurement_host import discover_modules, create_registered_tabs
    discovery = discover_modules()
    selected = [descriptor for descriptor in discovery.descriptors if descriptor.experiment_id == "fixed_wavenumber_kinetics"]
    assert len(selected) == 1
    assert not [issue for issue in discovery.issues if "fixed_wavenumber_kinetics" in issue.module]
    factory = ContextFactory(save_root_provider=lambda: tmp_path,
                             ownership=HardwareCoordinator(tmp_path/"discovery.lock"))
    result = create_registered_tabs(selected, factory)
    assert not result.issues
    assert len(result.handles) == 2
    assert result.handles[0].instance_id == "fixed_wavenumber_kinetics:single"
    assert result.handles[1].instance_id == "fixed_wavenumber_kinetics:dual"
    for handle in result.handles:
        handle.widget.deleteLater()


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_fixed_point_complete_guided_simulation_review_save_reload_and_new_run(app, tmp_path, mode):
    pair, _ = tabs(tmp_path)
    panel = pair[0 if mode == "single" else 1].widget
    sibling = pair[1 if mode == "single" else 0].widget
    panel._example()
    assert panel.plan is not None, panel.validation.text()
    assert panel._preparation_plan.ready, panel._preparation_plan.readiness_items
    if mode == "single":
        panel.begin_blank()
        wait(app, panel)
        assert panel.adapter.blank is not None, panel.status.text()
    panel.begin("preliminary")
    wait(app, panel)
    assert panel.preliminary is not None, panel.status.text()
    assert not panel.review.isChecked()
    assert not panel.start_button.isEnabled()
    panel.review.setChecked(True)
    assert panel.plan.ready, panel.plan.readiness_items
    assert panel.start_button.isEnabled(), panel.validation.text()
    assert not panel.adapter.validate_review(panel.preliminary, panel.plan), panel.adapter.validate_review(panel.preliminary, panel.plan)
    panel.begin("measurement")
    wait(app, panel)
    assert panel.result is not None, panel.status.text()
    assert panel.result["status"] == "complete", panel.result
    assert panel.result["simulation"]
    assert len(panel.result["events"][0]["pump_timestamps"]) == 1
    assert panel.preliminary is None and not panel.review.isChecked()
    assert not panel.start_button.isEnabled()
    assert Path(panel.result["run_directory"]).is_relative_to(tmp_path/"measurements"/"fixed_wavenumber_kinetics"/mode)
    assert (Path(panel.result["run_directory"])/"run.json").exists()
    assert sibling.result is None and sibling.preliminary is None and sibling.adapter.blank is None
    record_path = Path(panel.result["run_directory"])
    expected_settings = panel.editor.values()
    panel.new_run()
    assert panel.editor.values() == expected_settings
    assert panel.preliminary is None and panel.result is None and panel.adapter.blank is None
    panel.load_run(record_path)
    wait(app, panel)
    assert panel.result["run_id"]
    panel.quantity.setCurrentIndex(1)
    panel.time_control.input.stepBy(1)
    panel.plot.canvas.draw()
    for handle in pair:
        handle.widget.deleteLater()


def test_fixed_point_plan_mode_rejection_and_invalidation_are_explicit(app, tmp_path):
    pair, _ = tabs(tmp_path)
    single, dual = (h.widget for h in pair)
    single._example()
    path = tmp_path/"single-plan.json"
    single.adapter.save_plan(path, single.adapter.read_settings(), single.plan)
    with pytest.raises(ValueError, match="mode"):
        dual.adapter.load_plan(path)
    single.editor.fields["post_observation_s"].setValue(4)
    assert "post_observation_s" in single.status.text()
    assert not single.review.isChecked()
    single.editor.fields["event_budget"].setValue(0)
    assert single.plan is None
    single.editor.fields["event_budget"].setValue(1)
    assert single.plan is not None
    assert not single.validation.text()
    for h in pair:
        h.widget.deleteLater()


def test_fixed_point_simulation_does_not_contend_with_owned_instrument(app, tmp_path):
    coordinator = HardwareCoordinator(tmp_path/"shared.lock")
    context = ContextFactory(save_root_provider=lambda: tmp_path, ownership=coordinator)
    single = context.for_experiment("fixed_wavenumber_kinetics").for_mode("single")
    dual = context.for_experiment("fixed_wavenumber_kinetics").for_mode("dual")
    token = single.ownership.acquire(purpose="injected connected operation")
    with pytest.raises(Exception, match="owned"):
        dual.begin_operation({}, hardware=True)
    with pytest.raises(Exception, match="owned"):
        coordinator.acquire("manual:controls")
    offline = dual.begin_operation({}, hardware=False)
    assert offline.ownership is None
    with pytest.raises(RuntimeError, match="another tab"):
        dual.ownership.release(token, safe_verified=True)
    single.ownership.release(token, safe_verified=True, preservation_verified=True)


def test_fixed_point_plot_markers_and_aggregates_never_invent_pumps_or_mix_units():
    import numpy as np
    from matplotlib.figure import Figure
    from control_app.measurement_modules.fixed_wavenumber_kinetics.widgets import TraceRenderer
    renderer = TraceRenderer()
    renderer.view = "aggregate"
    renderer.quantity = "ratio"
    t = np.asarray([0., .1, .2, .3])
    event = {"time_s": t, "sample": t+1, "ratio": t+2, "delta_absorbance": t,
             "wavenumber_cm1": 1930., "original_pump_timestamp": None, "recovery_fit": {}}
    record = {"mode": "single", "kind": "measurement", "analysis": {"events": [event],
        "aggregates": [{"position_cm1": 1930., "time_s": t, "mean_delta_absorbance": t,
                        "event_indices": [0, 1]}]}}
    figure = Figure()
    renderer.draw(figure, record)
    labels = [line.get_label() for axes in figure.axes for line in axes.lines]
    assert not any("pump marker" in label for label in labels)
    assert not any("equivalent events" in label for label in labels)
    event["original_pump_timestamp"] = 100
    event["measured_pump_time_s"] = [.1]
    figure.clear()
    renderer.draw(figure, record)
    lines = [line for axes in figure.axes for line in axes.lines if "pump marker" in line.get_label()]
    assert len(lines) == 3


def test_fixed_point_fault_blocks_close_after_worker_finishes(app, tmp_path):
    pair, _ = tabs(tmp_path)
    panel = pair[0].widget
    token = panel.context.ownership.acquire(purpose="injected cleanup fault")
    panel.context.ownership.release(token, safe_verified=False, preservation_verified=True, detail="Injected restoration failure")
    assert not panel.command_running()
    assert any("recovery" in reason for reason in panel.close_blockers())
    panel.context.ownership.release(token, safe_verified=True, preservation_verified=True)
    assert not panel.close_blockers()
    for handle in pair:
        handle.widget.deleteLater()


def test_fixed_point_stale_selection_can_be_cleared_for_standalone_preliminary(app, tmp_path):
    from control_app.measurement_modules.fixed_wavenumber_kinetics.simulation import simulation_profile
    pair, _ = tabs(tmp_path)
    panel = pair[1].widget
    panel._example()
    panel.editor.sample_selection = simulation_profile("dual")["evidence"]["sample_selection"]
    panel.editor.fields["sample_id"].setText("new-sample")
    assert panel._preparation_plan is not None and panel._preparation_plan.ready
    assert panel.plan is not None and not panel.plan.ready
    panel._clear_selection()
    assert panel.editor.sample_selection is None
    assert panel._preparation_plan.ready
    for handle in pair:
        handle.widget.deleteLater()
