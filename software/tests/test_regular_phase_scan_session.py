"""Persistent phase experiments against simulated devices, never live hardware."""
from copy import deepcopy
import json

import pytest

from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError
from control_app.workflows.regular_phase_scan_runner import RegularPhaseScanRunner
from control_app.workflows.regular_phase_scan_data import RegularScanStore, load_background_sequence
from test_regular_phase_scan_acquisition import regular_fixture
from test_regular_phase_scan_ui import qt_app, capabilities


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    rig, adapter, _ = regular_fixture(tmp_path, prepared=False)
    coordinator = HardwareCoordinator(tmp_path / "owner.lock")
    counts = {"factory": 0, "prepare": 0, "close": 0}
    prepare, close, blocks = adapter.prepare, adapter.close, adapter.prepare_blocks

    def factory():
        counts["factory"] += 1
        return adapter

    def prepare_once(*args):
        counts["prepare"] += 1
        return prepare(*args)

    def close_once():
        counts["close"] += 1
        return close()

    def select_events(plan, events, cancel):
        rig.hf.events = events
        return blocks(plan, events, cancel)

    monkeypatch.setattr(adapter, "prepare", prepare_once)
    monkeypatch.setattr(adapter, "close", close_once)
    monkeypatch.setattr(adapter, "prepare_blocks", select_events)
    runner = RegularPhaseScanRunner(factory, coordinator=coordinator, hardware_access=True)
    yield rig, adapter, runner, coordinator, counts
    if coordinator.has_parked_session():
        coordinator.close_parked_session()
    coordinator._unlock_os()


def acquire(runner, adapter, root, kind):
    return runner.execute(kind, root, adapter.plan, laser_authorized=True)


def assert_retained(rig, adapter, runner, coordinator):
    assert runner.experiment_session_active
    assert coordinator.has_parked_session(instance_id=runner.instance_id)
    assert not adapter._closed and not adapter._safed
    assert rig.laser.armed and not rig.laser.emission
    assert rig.units["t660_1"].source == "SYN"
    assert rig.units["t660_1"].channels["A"]["enabled"]
    assert all(not rig.units["t660_1"].channels[c]["enabled"] for c in "BCD")
    assert rig.units["t660_2"].source == "OFF"
    assert all(not v["enabled"] for v in rig.units["t660_2"].channels.values())


def test_blank_preliminary_pumped_share_reference_connections_settings_and_owner(experiment, tmp_path, monkeypatch):
    rig, adapter, runner, coordinator, counts = experiment
    blank = acquire(runner, adapter, tmp_path, "background")
    assert_retained(rig, adapter, runner, coordinator)
    original = deepcopy(adapter._original_hf)
    configured = deepcopy(rig.hf.values)
    owner = coordinator.snapshot()["owner"]
    def no_reconfiguration(*args, **kwargs):
        pytest.fail("Retained devices must not reconnect or reapply the HF2LI preset")
    monkeypatch.setattr(rig.hf, "apply_preset", no_reconfiguration)
    monkeypatch.setattr(rig.hf, "connect", no_reconfiguration)
    monkeypatch.setattr(rig.laser, "initialize", no_reconfiguration)
    for unit in rig.units.values():
        monkeypatch.setattr(unit, "connect", no_reconfiguration)
    assert counts == {"factory": 1, "prepare": 1, "close": 0}
    with pytest.raises(OwnershipError):
        coordinator.acquire("another_measurement")
    for operation in (runner.refresh_capabilities, runner.invalidate_background):
        with pytest.raises(RuntimeError, match="End the current"):
            operation()
    with pytest.raises(ValueError, match="successful restoration"):
        load_background_sequence(blank["path"], adapter.plan)
    preliminary = acquire(runner, adapter, tmp_path, "test")
    assert_retained(rig, adapter, runner, coordinator)
    assert coordinator.snapshot()["owner"] == owner
    assert rig.hf.values == configured
    assert adapter._original_hf == original
    assert counts == {"factory": 1, "prepare": 1, "close": 0}
    assert "t660_1_safe_stop" not in rig.trace
    runner.mark_preliminary_reviewed()
    result = acquire(runner, adapter, tmp_path, "run")
    assert counts == {"factory": 1, "prepare": 1, "close": 1}
    assert not runner.experiment_session_active
    assert coordinator.snapshot()["state"] == "free"
    assert not rig.laser.armed and not rig.laser.emission
    for stage in (blank, preliminary):
        status = json.loads((stage["path"] / "result.json").read_text())
        assert status["status"] == "COMPLETE"
        assert status["safe_shutdown_and_restoration_verified"] is False
        assert status["experiment_session"]["interstage_verified"]
        closed = json.loads((stage["path"] / "experiment_session_close.json").read_text())
        assert closed["safe_verified"]
        assert closed["restoration_path"] == str(result["path"] / "restoration.json")
    assert load_background_sequence(blank["path"], adapter.plan).records


@pytest.mark.parametrize("finish", ["end", "app_close"])
def test_retained_session_explicit_and_application_cleanup(experiment, tmp_path, finish):
    rig, adapter, runner, coordinator, counts = experiment
    blank = acquire(runner, adapter, tmp_path, "background")
    if finish == "end":
        runner.end_experiment()
        runner.end_experiment()
    else:
        from control_app.workflows.state_machine import WorkflowStateMachine
        machine = WorkflowStateMachine(operator="test", run_dir=tmp_path / "app", coordinator=coordinator)
        assert machine.ui_safe_shutdown().status == "complete"
    assert counts["close"] == 1
    assert not runner.experiment_session_active
    assert coordinator.snapshot()["state"] == "free"
    assert json.loads((blank["path"] / "experiment_session_close.json").read_text())["safe_verified"]


@pytest.mark.parametrize("fault", ["settings", "reference", "abort"])
def test_resume_fault_closes_session_and_preserves_blank(experiment, tmp_path, monkeypatch, fault):
    rig, adapter, runner, coordinator, counts = experiment
    blank = acquire(runner, adapter, tmp_path, "background")
    original_status = (blank["path"] / "result.json").read_bytes()
    if fault == "settings":
        rig.hf.values[f"/{rig.hf.device_id}/demods/0/order"] += 1
    elif fault == "reference":
        monkeypatch.setattr(rig.hf, "get_oscillator_frequency", lambda _: 100.)
    else:
        def abort(*args):
            runner.abort()
            raise InterruptedError("requested stop")
        monkeypatch.setattr(adapter, "capture_block", abort)
    with pytest.raises((RuntimeError, InterruptedError)):
        acquire(runner, adapter, tmp_path, "test")
    assert counts["close"] == 1
    assert not runner.experiment_session_active
    assert coordinator.snapshot()["state"] == "free"
    assert (blank["path"] / "result.json").read_bytes() == original_status
    assert not rig.laser.emission


def test_save_failure_cannot_leave_prepared_hardware_or_accept_blank(experiment, tmp_path, monkeypatch):
    rig, adapter, runner, coordinator, counts = experiment
    def fail(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(RegularScanStore, "finish", fail)
    with pytest.raises(OSError, match="disk full"):
        acquire(runner, adapter, tmp_path, "background")
    assert counts["close"] == 1
    assert not runner.experiment_session_active and runner.background is None
    assert coordinator.snapshot()["state"] == "fault"
    assert not rig.laser.emission and not rig.laser.armed


def test_ui_freezes_session_settings_and_ends_in_worker(qt_app, tmp_path):
    from types import SimpleNamespace
    from time import monotonic
    from PySide6.QtCore import QSettings
    from PySide6.QtTest import QTest
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    runner = RegularPhaseScanRunner(lambda: None, capabilities=capabilities())
    closed = []
    runner._prepared_acquirer = SimpleNamespace(close=lambda: closed.append(True))
    widget = PhaseScanWidget(runner=runner,
        before_start=lambda: "Invalid save location must not prevent ending an experiment",
        preferences=QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat),
        save_root_provider=lambda: tmp_path)
    try:
        widget._update_buttons()
        assert widget.abort_button.text() == "End experiment" and widget.abort_button.isEnabled()
        assert not widget.background_button.isEnabled()
        assert not widget.load_background_button.isEnabled()
        assert not hasattr(widget, "refresh_capabilities_button")
        assert not widget.load_plan_button.isEnabled()
        assert all(not control.isEnabled() for control in widget.inputs.values())
        widget.abort_button.click()
        deadline = monotonic() + 5
        while widget.command_running() and monotonic() < deadline:
            QTest.qWait(10)
        assert not widget.command_running()
        assert closed == [True] and not runner.experiment_session_active
        assert "Experiment ended" in widget.scan_status.text()
        assert all(control.isEnabled() for control in widget.inputs.values())
    finally:
        widget.deleteLater()


def test_app_start_gate_allows_only_the_retained_phase_tab(qt_app, tmp_path):
    from types import SimpleNamespace
    from control_app.ui.main_window import ControlSystemMainWindow
    coordinator = HardwareCoordinator(tmp_path / "gate.lock")
    token = coordinator.acquire("phase_scan:single")
    coordinator.park(token, cleanup=lambda: {"safe_verified": True})
    window = SimpleNamespace(ownership=coordinator, command_handler=SimpleNamespace(),
        _apply_save_location=lambda: None, save_location_status=SimpleNamespace(text=lambda: ""))
    try:
        gate = ControlSystemMainWindow._phase_start_blocker
        assert gate(window, instance_id="phase_scan:single") is None
        assert gate(window, instance_id="phase_scan:dual")
        assert gate(window)
    finally:
        coordinator.close_parked_session()


def test_actual_window_buttons_continue_retained_experiment(experiment, qt_app, tmp_path, monkeypatch):
    from dataclasses import replace
    from time import monotonic, sleep
    from PySide6.QtWidgets import QMessageBox
    from control_app.ui.contracts import blocked_handler
    from control_app.ui.main_window import ControlSystemMainWindow
    from control_app.workflows.regular_phase_scan import HF2Capabilities

    rig, adapter, runner, coordinator, counts = experiment
    runner.set_capabilities(replace(HF2Capabilities(), device_id="dev1234", verified=True))
    handler = blocked_handler("Only simulated phase devices are available")
    handler.coordinator = coordinator
    handler.phase_scan_runner = runner
    window = ControlSystemMainWindow(command_handler=handler, module_discovery=())
    widget = window.phase_scan_widget
    confirmations = []
    def confirm(*args):
        confirmations.append(args[2])
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, "question", confirm)

    def finish_worker():
        deadline = monotonic() + 20
        while widget.command_running() and monotonic() < deadline:
            sleep(.01)
            qt_app.processEvents()
        assert not widget.command_running(), widget.scan_status.text()

    try:
        window.tabs.setCurrentWidget(widget)
        window.save_location.setText(str(tmp_path))
        window._apply_save_location()
        assert not window.save_location_status.text()
        assert widget.background_button.isEnabled()
        widget.background_button.click()
        finish_worker()
        assert_retained(rig, adapter, runner, coordinator)
        assert window._destination_busy()
        assert not window.save_location.isEnabled()
        assert widget.test_button.isEnabled()
        widget.test_button.click()
        assert len(confirmations) == 2, widget.scan_status.text()
        finish_worker()
        assert runner.preliminary is not None, widget.scan_status.text()
        assert runner.preliminary["path"].is_relative_to(tmp_path)
        assert not window.save_location_status.text()
        assert_retained(rig, adapter, runner, coordinator)
        widget.review_checkbox.setChecked(True)
        assert widget.start_button.isEnabled()
        widget.start_button.click()
        assert len(confirmations) == 3, widget.scan_status.text()
        finish_worker()
        assert widget._pending_result["kind"] == "run", widget.scan_status.text()
        assert counts == {"factory": 1, "prepare": 1, "close": 1}
        assert coordinator.snapshot()["state"] == "free"
    finally:
        finish_worker()
        window.deleteLater()
