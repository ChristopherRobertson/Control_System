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
    if Path("C:/Windows/Fonts/arial.ttf").exists():
        from PySide6.QtGui import QFont, QFontDatabase
        font_id = QFontDatabase.addApplicationFont("C:/Windows/Fonts/arial.ttf")
        instance.setFont(QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 9))
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
@pytest.mark.parametrize("partial_factories", [False, True])
def test_fixed_point_offline_activation_never_acquires_hardware(app, tmp_path, monkeypatch, mode, partial_factories):
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append("hardware access")
        raise AssertionError("Offline activation must not acquire or construct hardware")
    monkeypatch.setattr(HardwareCoordinator, "acquire", forbidden)
    factories = {name: forbidden for name in ("t660_1", "t660_2", "mircat")} if partial_factories else {}
    pair, _ = tabs(tmp_path, real_device_factories=factories)
    panel = pair[0 if mode == "single" else 1].widget
    panel.show()
    for _ in range(3):
        app.processEvents()
    assert not panel.command_running()
    assert not panel.check_device_button.isEnabled()
    assert panel.status.text() == "Connected instruments unavailable"
    panel.check_device()
    assert not attempts and not (tmp_path/"host.lock").exists()
    for handle in pair:
        handle.widget.close()
        handle.widget.deleteLater()


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_fixed_point_complete_developer_workflow_save_reload_and_new_run(app, tmp_path, mode):
    pair, _ = tabs(tmp_path)
    panel = pair[0 if mode == "single" else 1].widget
    sibling = pair[1 if mode == "single" else 0].widget
    panel._example()
    assert panel.plan is not None, panel.validation.text()
    assert panel.plan.ready
    if mode == "single":
        panel.begin_blank()
        wait(app, panel)
        assert panel.adapter.blank is not None, panel.status.text()
    panel.begin("preliminary")
    wait(app, panel)
    assert panel.preliminary is not None, panel.status.text()
    assert not hasattr(panel, "review")
    assert panel.start_button.isEnabled(), panel.validation.text()
    assert not panel.adapter.validate_preliminary(panel.preliminary, panel.plan)
    panel.begin("measurement")
    wait(app, panel)
    assert panel.result is not None, panel.status.text()
    assert panel.result["status"] == "complete", panel.result
    assert panel.result["simulation"]
    assert len(panel.result["events"][0]["pump_timestamps"]) == 1
    assert panel.start_button.isEnabled()
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
    assert single.plan is not None
    assert not hasattr(single, "review")
    single.editor.wavenumber.setValue(0)
    assert single.plan is None
    single.editor.wavenumber.setValue(1930)
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
    assert len(lines) == 2


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


def test_fixed_point_essential_inputs_and_independent_automatic_overrides(app, tmp_path):
    from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QDoubleSpinBox, QSpinBox
    pair, _ = tabs(tmp_path)
    for handle in pair:
        panel = handle.widget
        panel.editor.wavenumber.setValue(1930)
        assert panel.plan.ready and panel.start_button.isEnabled()
        assert panel.editor.values()["execution"] == "connected"
        assert not panel.findChildren(QCheckBox)
        assert not hasattr(panel.editor, "profile")
        assert not hasattr(panel.editor, "execution")
        assert not panel.advanced_content.isVisible()
        essential = panel.editor.findChildren(QLineEdit) + panel.editor.findChildren(QDoubleSpinBox) + panel.editor.findChildren(QSpinBox) + panel.editor.findChildren(QComboBox)
        # Internal spin-box line edits are not additional visible inputs.
        assert len(panel.editor.fields) > 6
        panel.editor.fields["sample_rate_sps"].setText("1234")
        values = panel.editor.values()["settings"]
        assert values["sample_rate_sps"] == 1234
        assert values["sample_timeconstant_s"] is None and values["sample_filter_order"] is None
        if handle.instance_id.endswith(":dual"):
            assert values["reference_rate_sps"] is None
        panel.editor.restore_automatic()
        assert panel.editor.values()["settings"]["sample_rate_sps"] is None
        panel.deleteLater()


def test_fixed_point_loaded_simulation_plan_cannot_switch_normal_execution(app, tmp_path):
    pair, _ = tabs(tmp_path)
    panel = pair[1].widget
    panel._example()
    envelope = panel.editor.values()
    assert envelope["execution"] == "simulation"
    panel.adapter.apply_settings(envelope)
    assert panel.editor.values()["execution"] == "connected"
    assert panel.adapter.hardware_required("measurement", panel.editor.values())
    assert not panel.adapter.hardware_required("load_blank", panel.editor.values())
    for handle in pair:
        handle.widget.deleteLater()


def test_fixed_point_start_needs_no_profile_blank_preliminary_or_metadata(app, tmp_path):
    pair, _ = tabs(tmp_path)
    for handle in pair:
        panel = handle.widget
        panel.editor.wavenumber.setValue(1930)
        assert panel.plan.ready
        assert panel.start_button.isEnabled(), panel.validation.text()
        assert panel.adapter.blank is None and panel.preliminary is None
        assert panel.adapter.validate_preliminary(None, panel.plan) == ()
        values = panel.editor.values()
        values["settings"].update(condition_profile="cryo_mbco", temperature_k=10,
            condition_id="arbitrary", sample_id="arbitrary", fresh_state_record_ids=[])
        panel.editor.apply(values)
        assert panel.start_button.isEnabled()
        assert not panel.adapter.validate_preliminary(None, panel.plan)
        panel.deleteLater()


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_fixed_point_compact_real_factories_check_and_direct_start(app, tmp_path, mode):
    from test_fixed_point_installed_adapter import build_connected_fixture
    from control_app.measurement_modules.fixed_wavenumber_kinetics.registration import create_tabs
    fixture = build_connected_fixture(tmp_path, mode)
    pair = create_tabs(fixture.context_factory.for_experiment("fixed_wavenumber_kinetics"))
    panel = pair[0 if mode == "single" else 1].widget
    # Discovery is independent of acquisition inputs and never emits or configures.
    panel.editor.fields["sample_rate_sps"].setText("invalid acquisition value")
    assert panel.plan is None
    panel.check_device()
    wait(app, panel)
    assert panel.adapter.live_readbacks.get("source_kind") == "connected_readbacks", panel.status.text()
    for service in fixture.state["services"].values():
        assert not {"on", "arm", "tune", "source", "inputs", "demods"}.intersection(service.calls)
    panel.editor.apply({"settings": fixture.settings.to_dict()})
    assert panel.start_button.isEnabled()
    assert panel.preliminary is None and panel.adapter.blank is None
    assert panel.editor.values()["execution"] == "connected"
    panel.begin("measurement")
    wait(app, panel)
    record = panel.result
    assert record and record["status"] == "complete", panel.status.text()
    assert not record["simulation"]
    assert record["live_readbacks"]["source_kind"] == "connected_readbacks"
    assert fixture.state["core"].dispatched == 1
    assert "on" in fixture.state["services"]["mircat"].calls
    assert "pending_upload" in fixture.state["services"]["t660_2"].calls
    assert record["native_chunks"] and record["preservation_verified"]
    assert panel.start_button.isEnabled()
    event = record["analysis"]["events"][0]
    if mode == "single":
        assert event["normalization_kind"] == "observed_sample_baseline"
        assert "Baseline-relative" in panel.quantity.itemText(1)
    assert pair[1 if mode == "single" else 0].widget.result is None
    for handle in pair:
        handle.widget.deleteLater()


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_fixed_point_compact_real_optional_blank_sample_reuse(app, tmp_path, mode):
    from test_fixed_point_installed_adapter import build_connected_fixture
    from control_app.measurement_modules.fixed_wavenumber_kinetics.registration import create_tabs
    fixture = build_connected_fixture(tmp_path, mode)
    pair = create_tabs(fixture.context_factory.for_experiment("fixed_wavenumber_kinetics"))
    panel = pair[0 if mode == "single" else 1].widget
    panel.editor.apply({"settings": fixture.settings.to_dict()})
    if mode == "single":
        panel.begin_blank()
        wait(app, panel)
        assert panel.adapter.blank, panel.status.text()
    panel.begin("preliminary")
    wait(app, panel)
    assert panel.preliminary, panel.status.text()
    panel.begin("measurement")
    wait(app, panel)
    assert panel.result and panel.result["status"] == "complete", panel.status.text()
    assert "preliminary" in panel.result["analysis_inputs"], panel.result.get("optional_record_notes")
    if mode == "single":
        assert "blank" in panel.result["analysis_inputs"], panel.result.get("optional_record_notes")
    for handle in pair:
        handle.widget.deleteLater()


def test_fixed_point_compact_real_abort_contention_and_frozen_destination(app, tmp_path, monkeypatch):
    from threading import Event
    from test_fixed_point_installed_adapter import build_connected_fixture, HF2
    from control_app.measurement_modules.fixed_wavenumber_kinetics.registration import create_tabs
    fixture = build_connected_fixture(tmp_path, "dual")
    entered, unblock = Event(), Event()
    original = HF2.read_acquisition
    def blocked_poll(service, duration_s):
        if not entered.is_set():
            entered.set()
            assert unblock.wait(5)
        return original(service, duration_s)
    monkeypatch.setattr(HF2, "read_acquisition", blocked_poll)
    pair = create_tabs(fixture.context_factory.for_experiment("fixed_wavenumber_kinetics"))
    single, dual = (h.widget for h in pair)
    dual.editor.apply({"settings": fixture.settings.to_dict()})
    single.editor.wavenumber.setValue(1930)
    dual.begin("measurement")
    deadline = time.monotonic()+5
    while not entered.is_set():
        app.processEvents()
        assert time.monotonic() < deadline
        time.sleep(.005)
    original_destination = dual.snapshot.operation.output_path
    try:
        with pytest.raises(Exception, match="owned"):
            single.begin("measurement")
        with pytest.raises(Exception, match="owned"):
            HardwareCoordinator(tmp_path/"exclusive.lock").acquire("manual:controls")
        dual.output_location_changed(tmp_path/"next")
        assert dual.snapshot.operation.output_path == original_destination
        dual.request_abort("Stopped by test")
    finally:
        unblock.set()
    wait(app, dual)
    assert "Acquisition stopped" in dual.status.text()
    record = dual.adapter.last_record
    assert record["status"] == "stopped" and record["preservation_verified"]
    assert Path(record["run_directory"]) == original_destination
    assert record["native_chunks"]
    assert not dual.close_blockers()
    for handle in pair:
        handle.widget.deleteLater()


@pytest.mark.parametrize("fault", ["health_overload", "cleanup"])
def test_fixed_point_compact_real_failure_and_cleanup_precedence(app, tmp_path, monkeypatch, fault):
    from test_fixed_point_installed_adapter import build_connected_fixture, HF2
    from control_app.measurement_modules.fixed_wavenumber_kinetics.registration import create_tabs
    if fault == "cleanup":
        monkeypatch.setattr(HF2, "compare_settings_snapshots", lambda *args: {"match": False})
    fixture = build_connected_fixture(tmp_path, "dual", faults={"health_overload": True} if fault != "cleanup" else {})
    pair = create_tabs(fixture.context_factory.for_experiment("fixed_wavenumber_kinetics"))
    panel = pair[1].widget
    panel.editor.apply({"settings": fixture.settings.to_dict()})
    panel.begin("measurement")
    wait(app, panel)
    record = panel.adapter.last_record
    assert record and record["status"] != "complete"
    assert record["preservation_verified"]
    assert "off" in fixture.state["services"]["mircat"].calls
    if fault == "cleanup":
        assert record["status"] == "cleanup_failed"
        assert panel.close_blockers()
    else:
        assert fixture.state["core"].dispatched == 0
        assert not panel.close_blockers()
    for handle in pair:
        handle.widget.deleteLater()


def test_fixed_point_plot_relative_fallback_and_sequential_blank_labels():
    import numpy as np
    from matplotlib.figure import Figure
    from control_app.measurement_modules.fixed_wavenumber_kinetics.widgets import TraceRenderer
    renderer = TraceRenderer()
    renderer.quantity = "absolute_absorbance"
    event = {"time_s": np.array([0., .1, .2]), "sample": np.array([1., .9, .95]),
        "reference": np.array([2., 2., 2.]), "ratio": np.array([1., .9, .95]),
        "ratio_label": "Baseline-relative signal S/S0", "normalization_kind": "observed_sample_baseline",
        "wavenumber_cm1": 1930., "recovery_fit": {}}
    record = {"mode": "single", "analysis": {"events": [event]}}
    figure = Figure()
    renderer.draw(figure, record)
    assert len(figure.axes[0].lines) == 1  # No simultaneous-reference implication.
    assert figure.axes[1].lines[0].get_label() == "Baseline-relative signal S/S0"
    event["ratio"] = np.array([np.nan]*3)
    figure.clear()
    renderer.draw(figure, record)
    assert not figure.axes[1].lines
    assert figure.axes[1].texts[0].get_text() == "No normalized signal"


@pytest.mark.parametrize("index", [2, 3])
def test_fixed_point_actual_shell_fits_and_keeps_plot_labels_visible(app, tmp_path, index):
    import numpy as np
    from control_app.ui.main_window import ControlSystemMainWindow
    from control_app.ui.contracts import blocked_handler
    from control_app.measurement_host.registry import DiscoveryResult
    from control_app.measurement_modules.fixed_wavenumber_kinetics.registration import DESCRIPTOR
    handler = blocked_handler("Injected layout test")
    handler.coordinator = HardwareCoordinator(tmp_path/"shell.lock")
    window = ControlSystemMainWindow(command_handler=handler, module_discovery=DiscoveryResult((DESCRIPTOR,), ()))
    for position in (2, 3):
        window.tabs.widget(position)._capability_check_attempted = True
    panel = window.tabs.widget(index)
    panel.editor.wavenumber.setValue(1930)
    event = {"time_s": np.linspace(-.2, 3., 40), "sample": np.ones(40), "ratio": np.ones(40),
             "delta_absorbance": np.zeros(40), "wavenumber_cm1": 1930., "recovery_fit": {}}
    panel.show_record({"mode": panel.context.mode, "analysis": {"events": [event]}})
    window.resize(1100, 780)
    window.tabs.setCurrentIndex(index)
    window.show()
    app.processEvents()
    panel.plot.canvas.draw()
    assert window.size().height() == 780
    assert window.workspace_scroll.verticalScrollBar().maximum() == 0
    renderer = panel.plot.canvas.get_renderer()
    assert panel.plot.figure.axes[-1].xaxis.label.get_window_extent(renderer).y0 >= 0
    assert panel.start_button.isVisible()
    window.hide()
    window.deleteLater()
    app.processEvents()
