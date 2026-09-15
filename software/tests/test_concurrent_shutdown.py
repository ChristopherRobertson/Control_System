"""Shutdown reuses local cleanup and overlaps only independent SDK branches."""
from threading import Barrier, get_ident
from types import SimpleNamespace
import pytest
from control_app.measurement_host.ownership import HardwareCoordinator, require_hardware_owner
from control_app.workflows.state_machine import WorkflowStateMachine, WorkflowStateMachineError
from control_app.ui.contracts import WorkflowResult
from control_app.workflows import state_machine as module


@pytest.fixture
def machine(tmp_path):
    owner = HardwareCoordinator(tmp_path / 'owner.lock')
    machine = WorkflowStateMachine(operator='test', run_dir=tmp_path / 'run', coordinator=owner)
    yield machine
    owner._unlock_os()


def test_clean_measurement_close_does_not_reconnect_or_verify(machine, monkeypatch):
    token = machine.coordinator.acquire('steady_state_slow_scan:single')
    machine.coordinator.release(token, safe_verified=True, preservation_verified=True)
    monkeypatch.setattr(machine, '_ui_shutdown_actions', lambda **kwargs: pytest.fail('Repeated hardware cleanup'))
    result = machine.ui_safe_shutdown()
    assert result.status == 'complete'
    assert result.data['reused_verified_idle'] is True


def test_idle_receipt_is_local_and_invalidated_by_new_work(machine):
    owner = machine.coordinator
    assert not owner.current_session_idle_verified()
    token = owner.acquire('phase_scan:single')
    owner.release(token, safe_verified=True)
    assert owner.current_session_idle_verified()
    other = HardwareCoordinator(owner.lock_path)
    assert not other.current_session_idle_verified()
    token = other.acquire('phase_scan:dual')
    other.release(token, safe_verified=True)
    assert not owner.current_session_idle_verified()
    token = owner.acquire('phase_scan:single')
    assert not owner.current_session_idle_verified()
    owner.release(token, safe_verified=False, preservation_verified=False)
    assert not owner.current_session_idle_verified()


def test_emergency_does_not_skip_fresh_cleanup(machine, monkeypatch):
    token = machine.coordinator.acquire('phase_scan:single')
    machine.coordinator.release(token, safe_verified=True)
    calls = []
    monkeypatch.setattr(machine, '_ui_shutdown_actions', lambda **kwargs: calls.append(kwargs) or WorkflowResult('complete', 'checked'))
    assert machine._ui_shutdown(reason='test emergency', emergency=True).status == 'complete'
    assert len(calls) == 1


@pytest.mark.parametrize('fail', [False, True])
def test_independent_branches_overlap_and_retain_ownership_context(machine, monkeypatch, fail):
    rendezvous = Barrier(2)
    threads = []
    finished = []
    class Laser:
        def initialize(self):
            require_hardware_owner(self)
            threads.append(get_ident())
            rendezvous.wait(timeout=3)
            if fail:
                raise RuntimeError('synthetic optical failure')
        def stop_scan_if_needed(self): return 0
        def turn_emission_off(self): pass
        def disarm(self): pass
        def read_state(self): return SimpleNamespace(to_dict=lambda: dict(emission_on=False, armed=False, scan_in_progress=False))
        def deinitialize(self): finished.append('laser')
    class Timing:
        def __init__(self, *args, **kwargs): pass
        def apply_recipe(self, *args, **kwargs):
            require_hardware_owner(self)
            threads.append(get_ident())
            rendezvous.wait(timeout=3)
            finished.append('timing')
            return {'matches_recipe': True}
    monkeypatch.setattr(module.MircatService, 'from_config', lambda **kwargs: Laser())
    monkeypatch.setattr(module, 'TimingRecipeManager', Timing)
    token = machine.coordinator.acquire('manual:recovery', recovery=True)
    with machine.coordinator.scope(token):
        if fail:
            with pytest.raises(WorkflowStateMachineError, match='synthetic optical failure'):
                machine._send_safe_actions('test')
        else:
            assert machine._send_safe_actions('test')['mircat']['state']['emission_on'] is False
    assert len(set(threads)) == 2
    assert 'timing' in finished
    assert machine.coordinator.snapshot()['state'] == 'owned'
    machine.coordinator.release(token, safe_verified=not fail)


def test_mircat_widget_close_does_not_reconnect_singleton_sdk(machine, monkeypatch):
    calls = []
    machine._mircat_handler = SimpleNamespace(shutdown_for_ui_close=lambda **kwargs:
        calls.append('widget') or WorkflowResult('complete', 'closed', {'mircat_shutdown': {'safe_state': 'closed'}}))
    monkeypatch.setattr(module.MircatService, 'from_config', lambda **kwargs: pytest.fail('Duplicate MIRcat connection'))
    monkeypatch.setattr(module, 'TimingRecipeManager', lambda *args, **kwargs:
        SimpleNamespace(apply_recipe=lambda *args, **kwargs: {'matches_recipe': True}))
    token = machine.coordinator.acquire('manual:recovery', recovery=True)
    with machine.coordinator.scope(token):
        machine._send_safe_actions('test', ui_shutdown={'reason': 'close', 'emergency': False})
    assert calls == ['widget']
    machine.coordinator.release(token, safe_verified=True)
