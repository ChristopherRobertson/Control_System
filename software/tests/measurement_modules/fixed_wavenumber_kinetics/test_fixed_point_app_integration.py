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
    assert [h.title for h in pair] == ["Fixed Wavenumber", "DD Fixed Wavenumber"]
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
    assert not hasattr(panel, "check_device_button")
    assert panel.status.text().startswith("Connected instruments unavailable")
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
    assert not hasattr(panel, "quantity")
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
    assert len(lines) == 1


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
    from PySide6.QtWidgets import QCheckBox, QGroupBox, QLabel
    pair, _ = tabs(tmp_path)
    for handle in pair:
        panel = handle.widget
        panel.editor.wavenumber.setValue(1930)
        assert panel.plan.ready and panel.start_button.isEnabled()
        assert panel.editor.values()["execution"] == "connected"
        assert not panel.findChildren(QCheckBox)
        assert not hasattr(panel.editor, "profile")
        assert not hasattr(panel.editor, "execution")
        panel.show()
        app.processEvents()
        assert isinstance(panel.advanced_content, QGroupBox)
        assert panel.advanced_content.isVisible() and not panel.advanced_content.isCheckable()
        assert not hasattr(panel, "advanced_button")
        labels = [label.text() for label in panel.findChildren(QLabel)]
        assert "Repetition Rate" in labels and "Pulse Width" in labels
        assert any(label.lower().endswith("time constant (s)") for label in labels) and "Filter time (s)" not in labels
        assert not any("QCL" in text for text in labels)
        assert not {"memory_limit_mb", "tune_timeout_s", "pump_fire_delay_s", "baseline_cv_limit"}.intersection(panel.editor.fields)
        assert all(control.isVisible() for control in panel.editor.fields.values())
        panel.editor.fields["sample_rate_sps"].setText("1234")
        values = panel.editor.values()["settings"]
        assert values["sample_rate_sps"] == 1234
        assert values["sample_timeconstant_s"] is None and values["sample_filter_order"] is None
        if handle.instance_id.endswith(":dual"):
            assert values["reference_rate_sps"] is None
        panel.editor.restore_automatic()
        assert panel.editor.values()["settings"]["sample_rate_sps"] is None
        panel.close()
        panel.deleteLater()


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_fixed_point_compact_overrides_migrate_removed_settings_and_preserve_positions(app, tmp_path, mode):
    from control_app.measurement_modules.fixed_wavenumber_kinetics.settings import Settings
    pair, _ = tabs(tmp_path)
    panel = pair[0 if mode == "single" else 1].widget
    settings = Settings(mode=mode).to_dict()
    settings.update(positions=[{"wavenumber_cm1": 1930., "label": "band"},
        {"wavenumber_cm1": 1940., "label": "off_band", "selection_record_id": "measured-position-2"}],
        baseline_window_s=[-0.8, -0.2], memory_limit_mb=512., technical_repetitions=2,
        probe_rate_hz=2000000., probe_width_ns=100., sample_timeconstant_s=0.0001,
        pre_observation_s=0.0002, post_observation_s=0.000000123, pump_q_switch_delay_s=0.000213)
    panel.editor.apply({"settings": settings})
    values = panel.editor.values()["settings"]
    assert values["positions"] == settings["positions"]
    assert values["baseline_window_s"] is None and values["memory_limit_mb"] == 256.
    assert values["pump_q_switch_delay_s"] is None
    assert values["technical_repetitions"] == 1 and values["event_budget"] == 2
    historical = panel.editor.values()["historical_ui_settings"]
    assert historical["baseline_window_s"] == [-0.8, -0.2] and historical["memory_limit_mb"] == 512.
    assert historical["pump_q_switch_delay_s"] == 0.000213 and historical["technical_repetitions"] == 2
    assert settings["pump_q_switch_delay_s"] == 0.000213  # Original saved input is untouched.
    assert values["probe_rate_hz"] == 2000000. and values["probe_width_ns"] == 100.
    assert values["sample_timeconstant_s"] == 0.0001 and values["sample_rate_sps"] is None
    assert values["pre_observation_s"] == 0.0002 and values["post_observation_s"] == 0.000000123
    panel.editor.positions.setText("1940, 1920")
    changed = panel.editor.values()["settings"]
    assert changed["positions"][1]["selection_record_id"] == "measured-position-2"
    assert changed["positions"][2] == {"wavenumber_cm1": 1920.}
    panel.editor.wavenumber.setValue(1940)
    panel.editor.positions.setText("1930, 1920")
    reordered = panel.editor.values()["settings"]["positions"]
    assert reordered[0]["selection_record_id"] == "measured-position-2"
    assert reordered[1] == settings["positions"][0]
    panel.editor.wavenumber.setValue(1925)
    assert panel.editor.values()["settings"]["positions"][0] == {"wavenumber_cm1": 1925.}
    panel.editor.restore_automatic()
    restored = panel.editor.values()["settings"]
    assert restored["probe_rate_hz"] == 2_000_000 and restored["probe_width_ns"] == 150
    assert restored["pump_q_switch_delay_s"] is None
    assert restored["baseline_window_s"] is None and restored["memory_limit_mb"] == 256.
    panel.editor.apply(panel.editor.values())
    assert panel.editor.values()["historical_ui_settings"] == historical
    for handle in pair:
        handle.widget.deleteLater()


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
    panel.editor.apply({"settings": {**fixture.settings.to_dict(), "probe_rate_hz": 100000.}})
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
        assert not hasattr(panel, "quantity")
    assert pair[1 if mode == "single" else 0].widget.result is None
    for handle in pair:
        handle.widget.deleteLater()


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_fixed_point_visible_pulse_controls_reach_installed_transports(app, tmp_path, mode):
    from test_fixed_point_installed_adapter import build_connected_fixture
    from control_app.measurement_modules.fixed_wavenumber_kinetics.registration import create_tabs
    fixture = build_connected_fixture(tmp_path, mode)
    pair = create_tabs(fixture.context_factory.for_experiment("fixed_wavenumber_kinetics"))
    panel = pair[0 if mode == "single" else 1].widget
    panel.editor.apply({"settings": {**fixture.settings.to_dict(), "probe_rate_hz": 100000.}})
    saved = panel.editor.values()
    saved["settings"]["pump_q_switch_delay_s"] = 0.000213
    panel.editor.apply(saved)
    panel.editor.fields["probe_rate_hz"].setText("80000")
    panel.editor.fields["probe_width_ns"].setText("120")
    panel.begin("measurement")
    wait(app, panel)
    assert panel.result["status"] == "complete", panel.status.text()
    selected = panel.result["plan"]["resolved"]
    assert selected["probe_recipe"]["clock"]["frequency"] == "80000Hz"
    assert selected["mircat"]["qcl"] == 1 and selected["mircat"]["pulse_width_ns"] == 142.
    pulse = panel.result["events"][0]["tuning"]["mircat_internal_pulse"]
    assert pulse["external_probe_rate_hz"] == 80000. and pulse["pulse_rate_hz"] == 2100000.
    assert pulse["pulse_width_ns"] == 142.
    assert pulse["current_ma"] == 1000.
    assert fixture.state["services"]["mircat"].pulse(1)["current_ma"] == 500.
    assert selected["timing"]["q_switch_delay_s"] == 0.00025
    assert panel.result["plan"]["evidence_records"]["historical_ui_settings"]["pump_q_switch_delay_s"] == 0.000213
    assert any(write["qcl"] == 1 and write["pulse_rate_hz"] == 2100000. and write["pulse_width_ns"] == 142. for write in fixture.state["services"]["mircat"].pulse_writes)
    assert panel.result["preservation_verified"] and panel.result["restoration"]["safe_verified"]
    for handle in pair:
        handle.widget.deleteLater()


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_fixed_point_compact_real_optional_blank_sample_reuse(app, tmp_path, mode):
    from test_fixed_point_installed_adapter import build_connected_fixture
    from control_app.measurement_modules.fixed_wavenumber_kinetics.registration import create_tabs
    fixture = build_connected_fixture(tmp_path, mode)
    pair = create_tabs(fixture.context_factory.for_experiment("fixed_wavenumber_kinetics"))
    panel = pair[0 if mode == "single" else 1].widget
    panel.editor.apply({"settings": {**fixture.settings.to_dict(), "probe_rate_hz": 100000.}})
    inputs = panel.editor.lasers.inputs
    inputs["start_wavenumber_cm1"].setValue(1930.)
    inputs["stop_wavenumber_cm1"].setValue(1930.)
    assert not inputs["step_size_cm1"].isEnabled()
    assert panel.editor.lasers.points() == [1930.]
    if mode == "single":
        panel.begin_blank()
        wait(app, panel)
        assert panel.adapter.blank, panel.status.text()
    panel.begin("preliminary")
    wait(app, panel)
    assert panel.preliminary, panel.status.text()
    from control_app.measurement_modules.fixed_wavenumber_kinetics.processing import compatible_record
    assert compatible_record(panel.preliminary, panel.plan)[0], compatible_record(panel.preliminary, panel.plan)[1]
    panel.begin("measurement")
    wait(app, panel)
    assert panel.result and panel.result["status"] == "complete", panel.status.text()
    assert "preliminary" not in panel.result["analysis_inputs"], panel.result.get("optional_record_notes")
    if mode == "single":
        assert "blank" not in panel.result["analysis_inputs"], panel.result.get("optional_record_notes")
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
    dual.editor.apply({"settings": {**fixture.settings.to_dict(), "probe_rate_hz": 100000.}})
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
    panel.editor.apply({"settings": {**fixture.settings.to_dict(), "probe_rate_hz": 100000.}})
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
    assert len(figure.axes) == 1
    assert figure.axes[0].lines[0].get_label() == "Sample magnitude"
    event["ratio"] = np.array([np.nan]*3)
    figure.clear()
    renderer.draw(figure, record)
    assert len(figure.axes) == 1
    assert figure.axes[0].lines[0].get_label() == "Sample magnitude"


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_fixed_point_actual_shell_fits_and_keeps_plot_labels_visible(app, tmp_path, mode):
    import numpy as np
    from PySide6.QtCore import QPoint, QRect
    from control_app.ui.main_window import ControlSystemMainWindow
    from control_app.ui.contracts import blocked_handler
    from control_app.measurement_host.registry import DiscoveryResult
    from control_app.measurement_modules.fixed_wavenumber_kinetics.registration import DESCRIPTOR
    handler = blocked_handler("Injected layout test")
    handler.coordinator = HardwareCoordinator(tmp_path/"shell.lock")
    window = ControlSystemMainWindow(command_handler=handler, module_discovery=DiscoveryResult((DESCRIPTOR,), ()))
    pair = [handle for handle in window.measurement_lifecycle.handles
            if handle.instance_id.startswith("fixed_wavenumber_kinetics:")]
    for handle in pair:
        handle.widget._capability_check_attempted = True
    panel = next(handle.widget for handle in pair if handle.instance_id.endswith(":" + mode))
    panel.editor.wavenumber.setValue(1930)
    event = {"time_s": np.linspace(-.2, 3., 40), "sample": np.ones(40), "ratio": np.ones(40),
             "delta_absorbance": np.zeros(40), "wavenumber_cm1": 1930., "recovery_fit": {}}
    panel.show_record({"mode": panel.context.mode, "analysis": {"events": [event]}})
    window.resize(1100, 780)
    window.set_detector_mode(mode)
    window.tabs.setCurrentWidget(panel)
    window.show()
    app.processEvents()
    panel.plot.canvas.draw()
    assert window.size().height() == 780
    assert window.workspace_scroll.verticalScrollBar().maximum() == 0
    renderer = panel.plot.canvas.get_renderer()
    assert panel.plot.figure.axes[-1].xaxis.label.get_window_extent(renderer).y0 >= 0
    assert panel.start_button.isVisible()
    assert panel.advanced_content.isVisible() and not panel.advanced_content.isCheckable()
    viewport = panel.settings_scroll.viewport()
    assert panel.isVisible()
    for control in (*panel.editor.fields.values(), *panel.editor.lasers.extra_inputs.values(), panel.editor.time_units,
                    panel.save_plan_button, panel.load_plan_button):
        # QSpinBox's focus rectangle excludes its frame; request the complete
        # control so a partly visible frame does not count as fully scrolled in.
        center = control.mapTo(panel.settings_scroll.widget(), control.rect().center())
        panel.settings_scroll.ensureVisible(center.x(), center.y(), control.width() // 2, control.height() // 2 + 20)
        app.processEvents()
        assert viewport.rect().contains(QRect(control.mapTo(viewport, QPoint()), control.size()))
    assert panel.settings_scroll.horizontalScrollBar().maximum() == 0
    assert panel.save_plan_button.geometry().top() == panel.load_plan_button.geometry().top()
    assert panel.save_plan_button.geometry().right() < panel.load_plan_button.geometry().left()
    window.hide()
    window.deleteLater()
    app.processEvents()


def test_startup_high_idle_rate_enables_actions_after_range_entry(app, tmp_path):
    from test_fixed_kinetics_planner import profile_case
    pair, _ = tabs(tmp_path)
    try:
        for handle in pair:
            panel = handle.widget
            _, evidence = profile_case(panel.context.mode)
            live = evidence["operating_profile"]
            live["timing_rate_sps"] = 1842105.2631578948
            live["maximum_aggregate_rate_sps"] = 700000.
            panel.adapter.live_readbacks = live
            panel.refresh_plan()
            assert not panel.start_button.isEnabled()
            assert "wavenumber" in panel.status.text().lower()
            inputs = panel.editor.lasers.inputs
            inputs["start_wavenumber_cm1"].setValue(1942.)
            inputs["stop_wavenumber_cm1"].setValue(1940.)
            inputs["step_size_cm1"].setValue(2.)
            panel.refresh_plan()
            assert panel.plan is not None, panel.validation.text()
            assert not panel.preliminary_button.isEnabled()
            assert panel.start_button.isEnabled()
            if hasattr(panel, "blank_button"):
                assert not panel.blank_button.isEnabled()
            assert panel.start_button.toolTip() == ""
    finally:
        for handle in pair:
            handle.widget.deleteLater()


def test_single_wavenumber_live_summary_and_acquisition_readiness(app, tmp_path):
    pair, _ = tabs(tmp_path)
    try:
        for handle in pair:
            panel = handle.widget
            def summary():
                return "\n".join(label.text() for label in panel.summary_values.values())
            assert "Set Start Wavenumber to proceed" in summary()
            assert "Set Stop Wavenumber to proceed" in summary()
            inputs = panel.editor.lasers.inputs
            inputs["start_wavenumber_cm1"].setValue(1940)
            assert "Set Start Wavenumber to proceed" not in summary()
            assert "Set Stop Wavenumber to proceed" in summary()
            inputs["stop_wavenumber_cm1"].setValue(1940)
            assert not inputs["step_size_cm1"].isEnabled()
            inputs["step_size_cm1"].setValue(0)
            assert panel.editor.lasers.points() == [1940]
            assert panel.plan is not None, summary()
            if panel.context.mode == "single":
                assert not panel.blank_button.isEnabled()
            assert panel.start_button.isEnabled()
            assert "Set Stop Wavenumber" not in summary()
            inputs["stop_wavenumber_cm1"].setValue(1938)
            assert inputs["step_size_cm1"].isEnabled()
            assert panel.plan is None  # zero step must now be corrected
            inputs["step_size_cm1"].setValue(2)
            assert panel.plan is not None
    finally:
        for handle in pair:
            handle.widget.deleteLater()
