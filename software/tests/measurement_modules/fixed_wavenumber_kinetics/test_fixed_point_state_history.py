"""Cross-operation/cross-mode consumption with isolated durable journals."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from control_app.measurement_host import ContextFactory
from control_app.measurement_host.ownership import HardwareCoordinator, require_hardware_owner
from control_app.measurement_modules.fixed_wavenumber_kinetics.planner import build_plan
from control_app.measurement_modules.fixed_wavenumber_kinetics.runner import Runner
from control_app.measurement_modules.fixed_wavenumber_kinetics.simulation import SimulatedDevices, simulation_profile
from control_app.measurement_modules.fixed_wavenumber_kinetics.state_history import StateHistory, StateHistoryError, default_history_path


@pytest.fixture(autouse=True)
def compact_analysis(monkeypatch):
    from control_app.measurement_modules.fixed_wavenumber_kinetics import processing
    monkeypatch.setattr(processing, "analyze_run", lambda *args, **kwargs: {"events": []})


class InjectedOwnedDevices(SimulatedDevices):
    def __init__(self, context, operation, history_path, fail_dispatch=False):
        require_hardware_owner(self)
        super().__init__(context, SimpleNamespace(hardware=False, configuration=operation.configuration))
        self.real_operation = operation
        self.history_path = history_path
        self.fail_dispatch = fail_dispatch
    def read_health(self):
        require_hardware_owner(self)
        return {"reference_locked": True, "clock_locked": True, "external_clock_selected": True, "overload": False}
    def start_event(self, program):
        require_hardware_owner(self)
        entries = list(StateHistory(self.history_path).records())
        assert entries[-1]["record_kind"] == "pump_dispatch_intent"
        assert entries[-1]["run_id"] == self.real_operation.run_id
        super().start_event(program)
        if self.fail_dispatch:
            raise RuntimeError("Injected uncertain dispatch acknowledgement")


def execute(root, history_path, *, mode="dual", cryo=True, position="SYNTHETIC-position", fresh=None,
            faults=None, fail_dispatch=False, hardware=True):
    profile = simulation_profile(mode, condition_profile="cryo_hrp_co" if cryo else "rt_hrp_co")
    profile["settings"].update(position_id=position, post_observation_s=.5)
    if hardware:
        profile["evidence"]["operating_profile"]["qualification_kind"] = "measured"
        profile["configuration"]["fixed_wavenumber_kinetics"]["qualification_kind"] = "measured"
    if fresh is not None:
        profile["evidence"]["operating_profile"]["fresh_state_record"] = fresh
    profile["configuration"]["fixed_point_simulation"] = faults or {}
    context = ContextFactory(configuration_provider=lambda: profile["configuration"], save_root_provider=lambda: root,
        ownership=HardwareCoordinator(root.parent/"instrument-test.lock")).for_experiment("fixed_wavenumber_kinetics").for_mode(mode)
    plan = build_plan(profile["settings"], profile["configuration"], profile["evidence"])
    assert plan.ready, (plan.validation_errors, plan.readiness_items)
    operation = context.begin_operation(settings=profile["settings"], hardware=hardware)
    devices = []
    def factory(ctx, op):
        device = InjectedOwnedDevices(ctx, op, history_path, fail_dispatch=fail_dispatch)
        devices.append(device)
        return device
    result = Runner(context, history_path=history_path,
        device_factory=factory if hardware else None).run(operation, plan)
    return result, devices, profile["settings"]


def fresh_record(settings, record_id="accepted-fresh-state-1"):
    return {"record_id": record_id, "accepted": True,
        **{k: settings[k] for k in ("sample_id", "preparation_id", "cell_id", "condition_id", "position_id")},
        "accepted_by": "Named reviewer", "source_run_id": "state-reset-evidence-run",
        "equivalence_basis": "Measured fresh-position equivalence in retained state characterization"}


def test_fixed_point_cryo_cross_mode_save_root_and_position_cannot_bypass(tmp_path):
    history = tmp_path/"machine-history.jsonl"
    first, devices, _ = execute(tmp_path/"first-save", history, mode="single")
    assert first["status"] == "complete", first.get("error")
    assert devices[0].dispatched == 1
    second, devices, _ = execute(tmp_path/"changed-save", history, mode="dual", position="different-position")
    assert second["status"] == "failed"
    assert "already consumed" in second["error"]
    assert not devices  # State check occurs before any connected constructor.
    rows = list(StateHistory(history).records())
    assert [row["record_kind"] for row in rows] == ["pump_dispatch_intent", "pump_run_outcome"]
    assert rows[1]["baseline"]["stationary"]
    assert "reset" in rows[1]


@pytest.mark.parametrize("faults,fail_dispatch", [({"missing_marker": True}, False), ({}, True)])
def test_fixed_point_failed_delivery_still_consumes_cryo_state(tmp_path, faults, fail_dispatch):
    history = tmp_path/"machine-history.jsonl"
    first, devices, _ = execute(tmp_path/"first", history, faults=faults, fail_dispatch=fail_dispatch)
    assert first["status"] == "failed"
    assert first["events"][0]["state_dispatch_intent"]
    second, devices, _ = execute(tmp_path/"second", history)
    assert second["status"] == "failed" and "already consumed" in second["error"]
    assert not devices


def test_fixed_point_accepted_fresh_state_once_then_never_reused(tmp_path):
    history = tmp_path/"machine-history.jsonl"
    first, _, settings = execute(tmp_path/"first", history)
    fresh = fresh_record({**settings, "position_id": "fresh-position"})
    second, devices, _ = execute(tmp_path/"second", history, mode="single", position="fresh-position", fresh=fresh)
    assert second["status"] == "complete", second.get("error")
    assert devices[0].dispatched == 1
    third, devices, _ = execute(tmp_path/"third", history, position="fresh-position", fresh=fresh)
    assert third["status"] == "failed" and "already consumed" in third["error"]
    assert not devices


@pytest.mark.parametrize("field,value", [("accepted", False), ("cell_id", "other-cell"), ("accepted_by", ""), ("source_run_id", ""), ("equivalence_basis", "")])
def test_fixed_point_fresh_record_requires_matched_reviewed_evidence(tmp_path, field, value):
    history = tmp_path/"machine-history.jsonl"
    _, _, settings = execute(tmp_path/"first", history)
    fresh = fresh_record(settings)
    fresh[field] = value
    result, devices, _ = execute(tmp_path/"next", history, fresh=fresh)
    assert result["status"] == "failed"
    assert "Fresh equivalent state" in result["error"]
    assert not devices


def test_fixed_point_failed_journal_prevents_dispatch(tmp_path, monkeypatch):
    history = tmp_path/"machine-history.jsonl"
    def fail(*args, **kwargs):
        raise StateHistoryError("Injected journal write failure")
    monkeypatch.setattr(StateHistory, "_append", fail)
    result, devices, _ = execute(tmp_path/"first", history)
    assert result["status"] == "failed"
    assert "journal write failure" in result["error"]
    assert devices[0].dispatched == 0


def test_fixed_point_partial_journal_blocks_before_connected_devices(tmp_path):
    history = tmp_path/"machine-history.jsonl"
    history.write_text('{"record_kind":"pump_dispatch_intent"', encoding="utf-8")
    result, devices, _ = execute(tmp_path/"first", history)
    assert result["status"] == "failed"
    assert "unresolved record" in result["error"]
    assert not devices


def test_fixed_point_rt_dispatches_retained_without_cryo_repeat_gate(tmp_path):
    history = tmp_path/"machine-history.jsonl"
    for i in range(2):
        result, devices, _ = execute(tmp_path/f"rt-{i}", history, cryo=False)
        assert result["status"] == "complete", result.get("error")
        assert devices[0].dispatched == 1
    assert len([r for r in StateHistory(history).records() if r["record_kind"] == "pump_dispatch_intent"]) == 2


def test_fixed_point_simulated_cryo_guard_uses_isolated_history(tmp_path):
    history = tmp_path/"simulation-history.jsonl"
    first, _, _ = execute(tmp_path/"sim-one", history, hardware=False)
    second, _, _ = execute(tmp_path/"sim-two", history, hardware=False)
    assert first["status"] == "complete"
    assert second["status"] == "failed" and "already consumed" in second["error"]
    assert all(row.get("simulation") for row in StateHistory(history).records() if row["record_kind"] == "pump_dispatch_intent")


def test_fixed_point_machine_path_does_not_depend_on_save_root(tmp_path, monkeypatch):
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path/"machine"))
    assert default_history_path() == tmp_path/"machine"/"ControlSystem"/"fixed_wavenumber_kinetics_state_history.jsonl"
