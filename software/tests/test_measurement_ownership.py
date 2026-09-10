"""Real OS locking and synthetic hardware lifecycle; never contact devices."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event, Thread
from types import SimpleNamespace

import pytest

from control_app.measurement_host.ownership import (
    HardwareCoordinator, OwnershipError, check_bound_hardware_owner, require_hardware_owner,
)
from control_app.ui.contracts import WorkflowCommand, WorkflowResult
from control_app.workflows.state_machine import WorkflowStateMachine
from control_app.workflows.regular_phase_scan_runner import RegularPhaseScanRunner
from control_app.workflows.dual_detector_phase_scan_runner import DualDetectorPhaseScanRunner


@pytest.fixture
def coordinator(tmp_path):
    coordinator = HardwareCoordinator(tmp_path / "instrument.lock")
    yield coordinator
    # Fault tests intentionally retain ownership. Explicit test-only teardown
    # closes the OS handle without falsely writing a safe/free transition.
    coordinator._unlock_os()


def test_thread_contenders_and_stale_callbacks(coordinator):
    entered = Event()
    finish = Event()
    tokens = []
    def hold():
        token = coordinator.acquire("steady_state_slow_scan:single", cancel=lambda reason: finish.set())
        tokens.append(token)
        entered.set()
        assert finish.wait(5)
        coordinator.release(token, safe_verified=True)
    worker = Thread(target=hold)
    worker.start()
    assert entered.wait(5)
    with pytest.raises(OwnershipError):
        coordinator.acquire("nanosecond_stroboscopy:dual")
    assert coordinator.request_emergency_stop("test emergency") == []
    worker.join(5)
    second = coordinator.acquire("fixed_wavenumber_kinetics:single")
    with pytest.raises(OwnershipError, match="stale"):
        coordinator.release(tokens[0], safe_verified=True)
    coordinator.assert_owner(second)
    with pytest.raises(OwnershipError):
        coordinator.assert_owner(replace(second, token_id="late-completion"))
    coordinator.release(second, safe_verified=True)


def _child(lock_path, code):
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).parents[1]))
    return subprocess.run([sys.executable, "-c", code, str(lock_path)], env=env,
                          capture_output=True, text=True, timeout=15)


def test_os_lock_excludes_other_process_then_crash_requires_recovery(coordinator):
    token = coordinator.acquire("manual:ndyag", purpose="persistent alignment")
    attempted = _child(coordinator.lock_path, """
import sys
from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError
c = HardwareCoordinator(sys.argv[1])
try: c.acquire('phase_scan:dual')
except OwnershipError: sys.exit(23)
sys.exit(99)
""")
    assert attempted.returncode == 23, attempted.stderr
    coordinator.release(token, safe_verified=True)
    crashed = _child(coordinator.lock_path, """
import os, sys
from control_app.measurement_host.ownership import HardwareCoordinator
c = HardwareCoordinator(sys.argv[1])
c.acquire('single_pump_scan_burst:dual', purpose='intentional synthetic crash')
os._exit(7)
""")
    assert crashed.returncode == 7, crashed.stderr
    with pytest.raises(OwnershipError, match="recovery"):
        coordinator.acquire("phase_scan:single")
    recovery = coordinator.acquire("manual:recovery", recovery=True)
    coordinator.release(recovery, safe_verified=True, detail="Synthetic safe readbacks and preservation verified")
    journal = [json.loads(line) for line in coordinator.journal_path.read_text().splitlines()]
    assert any(row["owner"]["instance_id"] == "single_pump_scan_burst:dual" for row in journal)
    assert coordinator.snapshot()["state"] == "free"


@pytest.mark.parametrize("safe,preserved", [(False, True), (True, False), (False, False)])
def test_fault_retains_owner_until_explicit_verified_recovery(coordinator, safe, preserved):
    token = coordinator.acquire("phase_scan:dual")
    coordinator.release(token, safe_verified=safe, preservation_verified=preserved, detail="Native/restoration fault")
    assert coordinator.snapshot()["state"] == "fault"
    with pytest.raises(OwnershipError):
        coordinator.acquire("manual:mircat")
    # Owner cleanup is still permitted while ordinary starts are blocked.
    with coordinator.scope(token):
        assert require_hardware_owner() == token
    recovery = coordinator.acquire("manual:recovery", recovery=True)
    with pytest.raises(OwnershipError):
        coordinator.release(token, safe_verified=True)
    coordinator.release(recovery, safe_verified=True, preservation_verified=True)


def test_real_backend_requires_owner_and_sessions_reject_stale_tokens(coordinator):
    service = SimpleNamespace()
    with pytest.raises(OwnershipError, match="before real device"):
        require_hardware_owner(service)
    token = coordinator.acquire("phase_scan:single")
    with coordinator.scope(token):
        require_hardware_owner(service)
    # Acquirer helper threads use this pinned session without shared contexts.
    check_bound_hardware_owner(service)
    coordinator.release(token, safe_verified=True)
    with pytest.raises(OwnershipError, match="stale"):
        check_bound_hardware_owner(service)


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_phase_runner_retains_through_native_finish_and_ignores_status_callback(coordinator, tmp_path, monkeypatch, mode):
    if mode == "single":
        from test_regular_phase_scan_data import SimulatedAcquirer, plan
        from control_app.workflows.regular_phase_scan_data import RegularScanStore as Store
        runner = RegularPhaseScanRunner(lambda: SimulatedAcquirer(blank=True), coordinator=coordinator, hardware_access=True)
        kind = "background"
    else:
        from test_dual_detector_phase_scan_runner import SimulatedAcquirer, plan
        from control_app.workflows.dual_detector_phase_scan_data import DualScanStore as Store
        runner = DualDetectorPhaseScanRunner(SimulatedAcquirer, coordinator=coordinator, hardware_access=True)
        kind = "test"
    finish = Store.finish
    def retained(store, *args, **kwargs):
        assert coordinator.snapshot()["owner"]["instance_id"] == f"phase_scan:{mode}"
        with pytest.raises(OwnershipError):
            coordinator.acquire("manual:mircat")
        return finish(store, *args, **kwargs)
    monkeypatch.setattr(Store, "finish", retained)
    def failed_display(message):
        raise ValueError("detached status widget")
    result = runner.execute(kind, tmp_path, plan(), progress=failed_display)
    assert (result["path"] / "raw" / "acquisition.npz").exists()
    assert runner.status_callback_errors
    assert coordinator.snapshot()["state"] == "free"


@pytest.mark.parametrize("mode", ["single", "dual"])
@pytest.mark.parametrize("failure", ["cleanup", "save", "finish"])
def test_runner_faults_retain_fault_provenance(coordinator, tmp_path, monkeypatch, mode, failure):
    if mode == "single":
        from test_regular_phase_scan_data import SimulatedAcquirer, plan
        from control_app.workflows.regular_phase_scan_data import RegularScanStore as Store
        runner = RegularPhaseScanRunner(lambda: SimulatedAcquirer(blank=True, cleanup_fault=failure == "cleanup"),
                                       coordinator=coordinator, hardware_access=True)
        kind = "background"
    else:
        from test_dual_detector_phase_scan_runner import SimulatedAcquirer, plan
        from control_app.workflows.dual_detector_phase_scan_data import DualScanStore as Store
        runner = DualDetectorPhaseScanRunner(lambda: SimulatedAcquirer(cleanup_fault=failure == "cleanup"),
                                            coordinator=coordinator, hardware_access=True)
        kind = "test"
    def fail(*args, **kwargs):
        raise OSError("synthetic preservation failure")
    if failure != "cleanup":
        monkeypatch.setattr(Store, "save_block" if failure == "save" else "finish", fail)
    with pytest.raises((RuntimeError, OSError)):
        runner.execute(kind, tmp_path, plan())
    assert coordinator.snapshot()["state"] == "fault"
    assert not runner._lock.locked()


def test_capability_factory_is_excluded_before_hardware_access(coordinator):
    calls = []
    runner = RegularPhaseScanRunner(capability_provider=lambda: calls.append("discovery"),
                                   coordinator=coordinator, hardware_access=True)
    token = coordinator.acquire("manual:ndyag")
    with pytest.raises(OwnershipError):
        runner.refresh_capabilities()
    assert calls == []
    coordinator.release(token, safe_verified=True)


def test_manual_persistent_alignment_blocks_other_devices_but_owner_stop_works(coordinator, tmp_path, monkeypatch):
    machine = WorkflowStateMachine(operator="test", run_dir=tmp_path, coordinator=coordinator)
    sent = []
    def dispatch(command):
        sent.append(command.command)
        require_hardware_owner()
        return WorkflowResult(status="complete", message="Synthetic readback verified")
    monkeypatch.setattr(machine, "_dispatch_command", dispatch)
    assert machine(WorkflowCommand("ndyag", "ndyag.load_alignment_10hz")).status == "complete"
    assert machine(WorkflowCommand("ndyag", "ndyag.refresh_status")).status == "complete"
    assert coordinator.snapshot()["state"] == "owned"
    assert machine(WorkflowCommand("opo_iris", "opo_iris.set_diameter")).status == "blocked"
    assert machine(WorkflowCommand("ndyag", "ndyag.safe_idle")).status == "complete"
    assert coordinator.snapshot()["state"] == "free"
    assert "opo_iris.set_diameter" not in sent


def test_emergency_targets_live_dual_owner_without_cancelling_simulations(coordinator, tmp_path):
    machine = WorkflowStateMachine(operator="test", run_dir=tmp_path, coordinator=coordinator)
    dual = machine.dual_detector_phase_scan_runner
    token = coordinator.acquire("phase_scan:dual", cancel=lambda reason: dual.abort())
    dual._lock.acquire()
    try:
        result = machine.emergency_stop(reason="test")
        assert result.status == "accepted"
        assert dual.cancel.is_set()
        assert not machine.phase_scan_runner.cancel.is_set()
        assert coordinator.snapshot()["state"] == "owned"
    finally:
        dual._lock.release()
        coordinator.release(token, safe_verified=True)


def test_named_recovery_requires_evidence_and_fresh_safe_checks(coordinator, tmp_path, monkeypatch):
    machine = WorkflowStateMachine(operator="test", run_dir=tmp_path, coordinator=coordinator)
    token = coordinator.acquire("phase_scan:single")
    coordinator.release(token, safe_verified=False, detail="synthetic restoration fault")
    evidence = tmp_path / "operator_verification.txt"
    evidence.write_text("All original settings restored; retained native arrays saved and inspected.")
    monkeypatch.setattr(machine, "_ui_shutdown_actions", lambda **kwargs:
                        WorkflowResult(status="complete", message="Synthetic actual safe readbacks verified"))
    kwargs = dict(operator="Named reviewer", evidence=evidence, restoration_verified=True, preservation_verified=True)
    assert machine.ui_recover_instrument(**{**kwargs, "preservation_verified": False}).status == "blocked"
    assert coordinator.snapshot()["state"] == "fault"
    result = machine.ui_recover_instrument(**kwargs)
    assert result.status == "complete"
    record = json.loads(Path(result.data["recovery_record"]).read_text())
    assert record["operator"] == "Named reviewer"
    assert record["previous_ownership"]["state"] == "fault"
    assert record["safe_shutdown_actions"]["status"] == "complete"
    assert coordinator.snapshot()["state"] == "free"


def test_owner_manual_cleanup_allowed_after_failure_but_fault_is_preserved(coordinator, tmp_path, monkeypatch):
    machine = WorkflowStateMachine(operator="test", run_dir=tmp_path, coordinator=coordinator)
    sent = []
    def dispatch(command):
        sent.append(command.command)
        require_hardware_owner()
        return WorkflowResult(status="complete" if command.command.endswith("safe_idle") else "failed", message="synthetic outcome")
    monkeypatch.setattr(machine, "_dispatch_command", dispatch)
    assert machine(WorkflowCommand("ndyag", "ndyag.load_alignment_10hz")).status == "failed"
    assert machine(WorkflowCommand("ndyag", "ndyag.refresh_status")).status == "blocked"
    assert machine(WorkflowCommand("ndyag", "ndyag.safe_idle")).status == "complete"
    assert coordinator.snapshot()["state"] == "fault"
    assert sent == ["ndyag.load_alignment_10hz", "ndyag.safe_idle"]


def test_output_edit_is_deferred_for_persistent_manual_operation(coordinator, tmp_path, monkeypatch):
    machine = WorkflowStateMachine(operator="test", run_dir=tmp_path / "original", coordinator=coordinator)
    monkeypatch.setattr(machine, "_dispatch_command", lambda command: WorkflowResult(status="complete", message="synthetic"))
    machine(WorkflowCommand("ndyag", "ndyag.load_alignment_10hz"))
    machine.output_location_changed(tmp_path / "next")
    assert machine.run_dir == tmp_path / "original"
    machine(WorkflowCommand("ndyag", "ndyag.safe_idle"))
    assert machine.run_dir.parent == tmp_path / "next"


def test_native_backend_entry_points_refuse_unowned_connections():
    from control_app.devices.mircat_service import MircatService
    from control_app.devices.hf2li_service import HF2LIService
    from control_app.devices.picoscope_service import PicoScopeService
    from control_app.devices.t660_service import T660Service
    from control_app.devices.ell15_iris_service import ELL15IrisService
    # Empty configs cannot contact any device even if the ownership guard
    # regresses; assert the specific guard fails before SDK or config work.
    operations = [MircatService({}).initialize, HF2LIService({}).connect,
                  PicoScopeService({}, {}).open_unit, T660Service("synthetic", {}).connect,
                  ELL15IrisService({}).connect]
    for operation in operations:
        with pytest.raises(OwnershipError, match="Acquire coupled spectrometer"):
            operation()


def test_generic_shutdown_does_not_clear_abandoned_provenance(coordinator, tmp_path, monkeypatch):
    coordinator.acquire("phase_scan:dual")
    coordinator._unlock_os()  # Simulate an expired handle without a safe record.
    other = HardwareCoordinator(coordinator.lock_path)
    machine = WorkflowStateMachine(operator="test", run_dir=tmp_path, coordinator=other)
    monkeypatch.setattr(machine, "_ui_shutdown_actions", lambda **kwargs:
                        WorkflowResult(status="complete", message="Synthetic outputs inhibited"))
    try:
        result = machine._ui_shutdown(reason="explicit test shutdown", emergency=True)
        assert result.status == "failed"
        assert "preservation remain unverified" in result.message
        assert other.snapshot()["state"] == "fault"
    finally:
        other._unlock_os()


def test_blocked_sweep_start_cannot_release_persistent_mircat_alignment(coordinator, tmp_path, monkeypatch):
    machine = WorkflowStateMachine(operator="test", run_dir=tmp_path, coordinator=coordinator)
    machine._mircat_handler = SimpleNamespace(initialized=True, alignment_running=True)
    monkeypatch.setattr(machine, "_dispatch_command", lambda command:
        WorkflowResult(status="blocked" if command.command == "mircat.start_sweep_scan" else "complete",
                       message="Stop alignment before Start Scan"))
    machine(WorkflowCommand("mircat", "mircat.start_detector_alignment"))
    owner = coordinator.snapshot()["owner"]
    assert machine(WorkflowCommand("mircat", "mircat.start_sweep_scan")).status == "blocked"
    assert coordinator.snapshot()["owner"] == owner
    assert coordinator.snapshot()["state"] == "owned"


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_predispatch_selection_is_detached_from_later_baseline_and_review_edits(tmp_path, mode):
    import numpy as np
    if mode == "single":
        from test_regular_phase_scan_data import reviewed_runner, plan
        runner = reviewed_runner(tmp_path)
    else:
        from test_dual_detector_phase_scan_runner import reviewed_runner, plan
        runner, _ = reviewed_runner(tmp_path)
    requested = plan()
    selected = runner.freeze_operation_selection(requested)
    original_source = str(runner.preliminary["path"])
    if mode == "single":
        for _, spectrum in runner.background.records:
            spectrum.sample_r[:] = 999
    runner.preliminary["path"] = tmp_path / "later-selection"
    runner.invalidate_background()
    def forbidden_after_dispatch(plan):
        raise AssertionError("Calibration provider was called after dispatch")
    if mode == "dual":
        runner.calibration_provider = forbidden_after_dispatch
    result = runner.execute("run", tmp_path, requested, selection_snapshot=selected)
    reconstructed = result["reconstruction"]
    assert reconstructed["preliminary_source"] == original_source
    values = reconstructed["delta_absorbance"]
    assert np.isfinite(values).any()
    if mode == "dual":
        assert np.allclose(values[np.isfinite(values)], .1)


def test_setters_reject_midrun_selection_mutations(tmp_path):
    from test_regular_phase_scan_data import SimulatedAcquirer, plan
    runner = RegularPhaseScanRunner(lambda: SimulatedAcquirer(blank=True))
    attempts = []
    def progress(message):
        for mutation in (runner.invalidate_background, runner.mark_preliminary_reviewed,
                         lambda: runner.set_capabilities(None)):
            with pytest.raises(RuntimeError, match="during an operation"):
                mutation()
            attempts.append(True)
    runner.execute("background", tmp_path, plan(), progress=progress)
    assert attempts


def test_hf2_cleanup_attempts_all_actions_and_reports_failures():
    from control_app.devices.hf2li_service import HF2LIService, HF2LIConnectionError
    attempts = []
    def unsubscribe(path):
        attempts.append(path)
        raise OSError("unsubscribe failed")
    def disconnect():
        attempts.append("disconnect")
        raise OSError("disconnect failed")
    service = HF2LIService({})
    service._server = SimpleNamespace(unsubscribe=unsubscribe, disconnect=disconnect, sync=lambda: None)
    service._subscribed_paths = ["first", "second"]
    with pytest.raises(HF2LIConnectionError) as caught:
        service.close()
    assert attempts == ["first", "second", "disconnect"]
    assert "unsubscribe failed" in str(caught.value) and "disconnect failed" in str(caught.value)
    assert service._server is not None


def test_only_scoped_explicit_recovery_can_adopt_prior_sdk_session(coordinator):
    from control_app.measurement_host.ownership import adopt_recovery_session
    service = SimpleNamespace()
    original = coordinator.acquire("manual:mircat")
    with coordinator.scope(original):
        require_hardware_owner(service)
    coordinator.release(original, safe_verified=False)
    recovery = coordinator.acquire("manual:recovery", recovery=True)
    with pytest.raises(OwnershipError):
        adopt_recovery_session(service)
    with coordinator.scope(recovery):
        adopt_recovery_session(service)
        assert require_hardware_owner(service) == recovery
    coordinator.release(recovery, safe_verified=True)


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_acquisition_and_secondary_retention_errors_are_both_reported(coordinator, tmp_path, monkeypatch, mode):
    if mode == "single":
        from test_regular_phase_scan_data import SimulatedAcquirer, plan
        from control_app.workflows.regular_phase_scan_data import RegularScanStore as Store
        runner = RegularPhaseScanRunner(lambda: SimulatedAcquirer(blank=True, fault=RuntimeError("capture broke")),
                                       coordinator=coordinator, hardware_access=True)
        kind = "background"
    else:
        from test_dual_detector_phase_scan_runner import SimulatedAcquirer, plan
        from control_app.workflows.dual_detector_phase_scan_data import DualScanStore as Store
        runner = DualDetectorPhaseScanRunner(lambda: SimulatedAcquirer(fault=RuntimeError("capture broke")),
                                            coordinator=coordinator, hardware_access=True)
        kind = "test"
    def fail_save(*args, **kwargs):
        raise OSError("disk broke")
    monkeypatch.setattr(Store, "save_block", fail_save)
    with pytest.raises(RuntimeError) as caught:
        runner.execute(kind, tmp_path, plan())
    assert "capture broke" in str(caught.value) and "disk broke" in str(caught.value)
    assert coordinator.snapshot()["state"] == "fault"


def test_emergency_after_fault_does_not_cancel_later_offline_work(coordinator):
    cancelled = []
    token = coordinator.acquire("steady_state_slow_scan:single", cancel=lambda reason: cancelled.append(reason))
    coordinator.release(token, safe_verified=False)
    assert coordinator.request_emergency_stop("later unrelated analysis") == []
    assert cancelled == []
    assert coordinator.snapshot()["state"] == "fault"


@pytest.mark.parametrize("state,expected", [
    ({"armed": False, "emission_on": False, "scan_in_progress": False}, "complete"),
    ({"armed": False, "emission_on": True, "scan_in_progress": False}, "failed"),
    ({"armed": False, "emission_on": False, "scan_in_progress": None}, "failed"),
])
def test_manual_deinitialize_verifies_final_readback_and_retains_it(state, expected):
    from io import StringIO
    from control_app.workflows.mircat_widget_commands import MircatWidgetCommandHandler
    calls = []
    service = SimpleNamespace(
        stop_scan_if_needed=lambda: calls.append("stop"), turn_emission_off=lambda: calls.append("off"),
        disarm=lambda: calls.append("disarm"), read_state=lambda: SimpleNamespace(to_dict=lambda: state),
        deinitialize=lambda: calls.append("deinitialize"), command_log=None)
    handler = MircatWidgetCommandHandler()
    handler.service, handler.initialized = service, True
    result = handler._handle(WorkflowCommand("mircat", "mircat.deinitialize"), StringIO())
    assert result.status == expected
    assert calls == ["stop", "off", "disarm", "deinitialize"]
    assert result.data["state_before_deinitialize"] == state
    assert not handler.initialized
