"""Selecting workflow destinations must not create empty run directories."""
import json
from control_app.workflows import state_machine
from control_app.measurement_host.ownership import HardwareCoordinator


def test_startup_and_destination_changes_do_not_create_directories(tmp_path, monkeypatch):
    root = tmp_path / "runs"
    monkeypatch.setattr(state_machine, "output_run_root", lambda: root)
    monkeypatch.setattr(state_machine, "LOG_ROOT", tmp_path/"logs")
    machine = state_machine.WorkflowStateMachine(operator="test", hardware_access=False,
        coordinator=HardwareCoordinator(tmp_path/"owner.lock"))
    assert machine.run_dir.parent == tmp_path/"logs"/"workflow_diagnostics"
    assert not root.exists()
    for title in ("Slow Scan", "Fixed Wavenumber", "Slow Scan"):
        machine.output_location_changed(root/title)
        assert not root.exists()
    readback = machine._write_readback("readback.json", {"simulation": True})
    assert json.loads(readback.read_text()) == {"simulation": True}
    saved_dir = machine.run_dir
    machine.output_location_changed(root/"Phase Scan")
    assert machine.run_dir == saved_dir
    assert readback.exists()
    assert not root.exists()


def test_explicit_destination_is_created_by_first_write(tmp_path):
    target = tmp_path/"selected"/"run"
    machine = state_machine.WorkflowStateMachine(operator="test", hardware_access=False,
        run_dir=target, coordinator=HardwareCoordinator(tmp_path/"owner.lock"))
    assert machine.run_dir == target and not target.exists()
    machine._write_readback("state.json", {"simulation": True})
    assert (target/"state.json").is_file()
