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
        def apply_safe_idle(self, *args, **kwargs):
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
        SimpleNamespace(apply_safe_idle=lambda *args, **kwargs: {'matches_recipe': True}))
    token = machine.coordinator.acquire('manual:recovery', recovery=True)
    with machine.coordinator.scope(token):
        machine._send_safe_actions('test', ui_shutdown={'reason': 'close', 'emergency': False})
    assert calls == ['widget']
    machine.coordinator.release(token, safe_verified=True)

@pytest.mark.parametrize('fail', [False, True])
def test_safe_idle_units_overlap_and_both_finish(machine, monkeypatch, tmp_path, fail):
    from control_app.workflows.timing_recipe_manager import TimingRecipeManager, TimingRecipeError
    barrier = Barrier(2)
    finished = []
    def apply(self, recipe, *, output_path):
        require_hardware_owner(self)
        unit = next(iter(recipe['t660']))
        barrier.wait(timeout=3)
        finished.append(unit)
        if fail and unit == 't660_1':
            raise RuntimeError('unit1 error')
        return {'devices': {unit: {'checked': True}}, 'matches_recipe': True}
    monkeypatch.setattr(TimingRecipeManager, 'apply_recipe', apply)
    token = machine.coordinator.acquire('manual:recovery', recovery=True)
    manager = TimingRecipeManager(machine.inventory)
    with machine.coordinator.scope(token):
        if fail:
            with pytest.raises(TimingRecipeError, match='unit1 error'):
                manager.apply_safe_idle(output_path=tmp_path / 'idle.json')
        else:
            assert manager.apply_safe_idle(output_path=tmp_path / 'idle.json')['matches_recipe']
    assert sorted(finished) == ['t660_1', 't660_2']
    machine.coordinator.release(token, safe_verified=not fail)


def test_separate_optical_clients_overlap(machine, monkeypatch):
    barrier = Barrier(4)
    class Detector:
        def stop(self): pass
        def close_unit(self): self.close()
        def close(self): barrier.wait(timeout=3)
    machine._picoscope_service = Detector()
    machine._hf2li_service = Detector()
    machine._mircat_handler = SimpleNamespace(shutdown_for_ui_close=lambda **kwargs:
        barrier.wait(timeout=3) is not None and WorkflowResult('complete', 'closed', {'mircat_shutdown': {'safe_state': 'closed'}}))
    monkeypatch.setattr(module, 'TimingRecipeManager', lambda *args, **kwargs:
        SimpleNamespace(apply_safe_idle=lambda **kwargs: barrier.wait(timeout=3)))
    token = machine.coordinator.acquire('manual:recovery', recovery=True)
    with machine.coordinator.scope(token):
        machine._send_safe_actions('test', ui_shutdown={'reason': 'close', 'emergency': False})
    machine.coordinator.release(token, safe_verified=True)


def test_retained_alignment_cleanup_is_reused_without_overlapping_ports(machine, monkeypatch):
    calls = []
    def close(**kwargs):
        calls.append('alignment')
        return WorkflowResult('complete', 'closed', {'alignment_stop': {'data': {'alignment_stop_summary':
            {'status': 'STOPPED', 'safe_idle_after_alignment': 'retained.json', 'hf2li_close_result': 'closed'}}}})
    hf = SimpleNamespace(close=lambda: pytest.fail('Duplicate alignment HF close'))
    machine._hf2li_service = hf
    machine._mircat_handler = SimpleNamespace(alignment_workflow=SimpleNamespace(hf2li_service=hf), shutdown_for_ui_close=close)
    monkeypatch.setattr(module.MircatService, 'from_config', lambda **kwargs: pytest.fail('Duplicate MIRcat teardown'))
    monkeypatch.setattr(module, 'TimingRecipeManager', lambda *args, **kwargs: pytest.fail('Duplicate timing teardown'))
    token = machine.coordinator.acquire('manual:recovery', recovery=True)
    with machine.coordinator.scope(token):
        actions = machine._send_safe_actions('test', ui_shutdown={'reason': 'close', 'emergency': True})
    assert calls == ['alignment']
    assert actions['t660']['reused_alignment_safe_idle'] == 'retained.json'
    machine.coordinator.release(token, safe_verified=True)
