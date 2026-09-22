"""Prepared Blank/Sample ownership and eventual application cleanup."""
import pytest
from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError, require_hardware_owner
from control_app.workflows.state_machine import WorkflowStateMachine


@pytest.fixture
def coordinator(tmp_path):
    owner = HardwareCoordinator(tmp_path / 'owner.lock')
    yield owner
    owner._unlock_os()


def test_blank_session_resumes_same_sdk_owner_but_excludes_other_users(coordinator):
    token = coordinator.acquire('steady_state_slow_scan:single', operation_id='blank')
    class Device: pass
    device = Device()
    with coordinator.scope(token):
        assert require_hardware_owner(device) == token
    coordinator.park(token, cleanup=lambda: {'safe_verified': True, 'errors': []})
    assert coordinator.has_parked_session(instance_id='steady_state_slow_scan:single')
    assert not coordinator.current_session_idle_verified()
    with pytest.raises(OwnershipError):
        coordinator.acquire('phase_scan:single')
    other = HardwareCoordinator(coordinator.lock_path)
    with pytest.raises(OwnershipError):
        other.acquire('phase_scan:single')
    resumed = coordinator.acquire('steady_state_slow_scan:single', operation_id='sample')
    assert resumed == token
    assert not coordinator.has_parked_session()
    with coordinator.scope(resumed):
        assert require_hardware_owner(device) == token
    coordinator.release(resumed, safe_verified=True)


@pytest.mark.parametrize('failure', ['none', 'result', 'exception'])
def test_close_prepared_session_cleans_once_and_retains_failure(coordinator, failure):
    token = coordinator.acquire('steady_state_slow_scan:single')
    calls = []
    def cleanup():
        coordinator.assert_owner(token)
        calls.append('cleanup')
        if failure == 'exception':
            raise RuntimeError('cleanup failed')
        return {'safe_verified': failure == 'none', 'errors': [] if failure == 'none' else ['failed']}
    coordinator.park(token, cleanup=cleanup)
    if failure == 'none':
        assert coordinator.close_parked_session() is True
        assert coordinator.snapshot()['state'] == 'free'
        assert coordinator.current_session_idle_verified()
    else:
        with pytest.raises((OwnershipError, RuntimeError)):
            coordinator.close_parked_session()
        assert coordinator.snapshot()['state'] == 'fault'
    assert coordinator.close_parked_session() is False
    assert calls == ['cleanup']


def test_wrong_tab_cannot_close_prepared_session(coordinator):
    token = coordinator.acquire('steady_state_slow_scan:single')
    coordinator.park(token, cleanup=lambda: {'safe_verified': True})
    with pytest.raises(OwnershipError):
        coordinator.close_parked_session(instance_id='steady_state_slow_scan:dual')
    assert coordinator.has_parked_session()
    coordinator.close_parked_session()


def test_app_close_finishes_prepared_session_without_duplicate_shutdown(coordinator, tmp_path, monkeypatch):
    machine = WorkflowStateMachine(operator='test', run_dir=tmp_path / 'run', coordinator=coordinator)
    token = coordinator.acquire('steady_state_slow_scan:single')
    calls = []
    coordinator.park(token, cleanup=lambda: calls.append('restore') or {'safe_verified': True, 'errors': []})
    monkeypatch.setattr(machine, '_ui_shutdown_actions', lambda **kwargs: pytest.fail('Repeated device shutdown'))
    assert machine.ui_safe_shutdown().status == 'complete'
    assert calls == ['restore']
    assert coordinator.snapshot()['state'] == 'free'


def test_parked_record_from_previous_process_is_not_reusable(coordinator):
    token = coordinator.acquire('steady_state_slow_scan:single')
    coordinator.park(token, cleanup=lambda: {'safe_verified': True})
    # Simulate process loss: its callback and live SDK session do not survive.
    coordinator._unlock_os()
    restarted = HardwareCoordinator(coordinator.lock_path)
    assert not restarted.has_parked_session()
    assert not restarted.current_session_idle_verified()
    with pytest.raises(OwnershipError):
        restarted.acquire('steady_state_slow_scan:single')
