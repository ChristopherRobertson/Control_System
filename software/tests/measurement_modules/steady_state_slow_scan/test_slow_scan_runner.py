"""End-to-end offline lifecycle checks; never operate physical instruments."""
from dataclasses import replace
from types import SimpleNamespace
from threading import Event

import numpy as np
import pytest

from control_app.measurement_host import ContextFactory
from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError
from control_app.measurement_host.presentation import StartSnapshot
from control_app.measurement_modules.steady_state_slow_scan.settings import SlowScanSettings, ConditionIdentity, SpectralSegment
from control_app.measurement_modules.steady_state_slow_scan.planner import build_plan, simulation_inputs
from control_app.measurement_modules.steady_state_slow_scan.runner import SlowScanRunner, SyntheticSlowScanBackend, compatibility_errors
from control_app.measurement_modules.steady_state_slow_scan.persistence import load_run


class Worker:
    def __init__(self):
        self.cancel_event = Event()
        self.messages = []
        self.message = SimpleNamespace(emit=self.messages.append)
        self.progress = SimpleNamespace(emit=lambda *args: None)
    def check_cancelled(self):
        if self.cancel_event.is_set():
            raise InterruptedError("operator Stop")


def setup(tmp_path, mode="single"):
    coordinator = HardwareCoordinator(tmp_path / "instrument.lock")
    factory = ContextFactory(ownership=coordinator, save_root_provider=lambda: tmp_path)
    context = factory.for_experiment("steady_state_slow_scan").for_mode(mode)
    settings = SlowScanSettings(mode=mode, condition=ConditionIdentity(sample_id="sample-1", preparation_id="prep-1",
        cell_id="cell-1", position_id="position-1", temperature_id="room-1", matrix_id="buffer-1",
        configuration_id="config-1", temperature_k=295., temperature_uncertainty_k=.2, temperature_record_id="T-1"),
        segments=(SpectralSegment("band", 1, 1900., 1910.),), physical_controls_confirmed=True, condition_equilibrated=True)
    plan = build_plan(settings, simulation_inputs(settings))
    return coordinator, context, plan


def operation(context, plan, kind, controls=None, hardware=False):
    host = context.begin_operation(plan.settings.to_dict(), hardware=hardware)
    return StartSnapshot(host, kind, plan, controls or {})


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_complete_guided_slow_scan_retains_native_and_separate_controls(tmp_path, mode):
    _, context, plan = setup(tmp_path, mode)
    runner, worker = SlowScanRunner(context), Worker()
    controls = {"dark": runner.run(operation(context, plan, "dark"), worker)}
    if mode == "single":
        controls["blank"] = runner.run(operation(context, plan, "blank", controls), worker)
    controls["q0"] = runner.run(operation(context, plan, "preliminary", controls), worker)
    controls["reviewed"] = True
    result = runner.run(operation(context, plan, "measurement", controls), worker)
    assert result["status"] == "completed"
    assert result["restoration"]["safe_verified"]
    assert len(result["sweeps"]) == 4
    assert {s.direction for s in result["sweeps"]} == {"forward", "reverse"}
    assert all(s.native is n for s, n in zip(result["spectra"], result["sweeps"]))
    loaded = load_run(result["path"], expected_mode=mode)
    for before, after in zip(result["sweeps"], loaded["sweeps"]):
        np.testing.assert_array_equal(before.sample, after.sample)
        np.testing.assert_array_equal(before.axis_cm1, after.axis_cm1)
    assert result["claims"]["pump_command_count"] == 0
    assert not result["claims"]["instrument_bundle_promoted"]
    assert "restoration" in " ".join(worker.messages)


def test_review_compatibility_rejects_condition_setting_and_mode_changes(tmp_path):
    _, context, plan = setup(tmp_path)
    runner = SlowScanRunner(context)
    dark = runner.run(operation(context, plan, "dark"), Worker())
    assert not compatibility_errors(dark, plan, kind="dark")
    settings = replace(plan.settings, condition=replace(plan.settings.condition, sample_id="another"))
    changed = build_plan(settings, plan.inputs)
    assert "settings mismatch" in " ".join(compatibility_errors(dark, changed))
    assert "Detector mode" in " ".join(compatibility_errors({**dark, "mode": "dual"}, plan))
    assert not compatibility_errors(dark, plan)  # Restored settings clear errors, never approve review.


def test_controls_reject_foreign_identities_and_simulation_for_connected_use(tmp_path):
    _, context, plan = setup(tmp_path)
    dark = SlowScanRunner(context).run(operation(context, plan, "dark"), Worker())
    assert "Experiment identity" in " ".join(compatibility_errors(
        {**dark, "experiment_id": "another_experiment"}, plan))
    assert "instance identity" in " ".join(compatibility_errors(
        {**dark, "instance_id": "steady_state_slow_scan:dual"}, plan))
    connected = replace(plan, settings=replace(plan.settings, hardware=True))
    assert "simulated record" in " ".join(compatibility_errors(dark, connected))
    assert "simulated record" in " ".join(compatibility_errors(
        {**dark, "simulation": False}, connected))
    assert not compatibility_errors({**dark, "simulation": False, "readbacks": {}}, connected)


@pytest.mark.parametrize("kind", ["preliminary", "measurement"])
def test_required_controls_and_review_are_not_fabricated(tmp_path, kind):
    _, context, plan = setup(tmp_path)
    runner = SlowScanRunner(context)
    with pytest.raises(ValueError, match="dark|review"):
        runner.run(operation(context, plan, kind), Worker())
    assert runner.last_result["status"] == "failed"
    assert load_run(runner.last_result["path"])["status"] == "failed"


@pytest.mark.parametrize("cancel_stage", ["prepare", "acquire", "processing"])
def test_cancel_preserves_partial_and_always_restores(tmp_path, cancel_stage, monkeypatch):
    _, context, plan = setup(tmp_path)
    worker = Worker()
    restored = []
    class Backend(SyntheticSlowScanBackend):
        def prepare(self, *args):
            super().prepare(*args)
            if cancel_stage == "prepare":
                worker.cancel_event.set()
                worker.check_cancelled()
        def acquire_dark(self, *args):
            if cancel_stage == "acquire":
                worker.cancel_event.set()
                worker.check_cancelled()
            return super().acquire_dark(*args)
        def restore(self):
            restored.append(True)
            return super().restore()
    if cancel_stage == "processing":
        monkeypatch.setattr(SlowScanRunner, "_dark_statistics", staticmethod(lambda *args: (_ for _ in ()).throw(InterruptedError("Acquisition stopped during processing"))))
    runner = SlowScanRunner(context, backend_factory=Backend)
    with pytest.raises(InterruptedError):
        runner.run(operation(context, plan, "dark"), worker)
    assert restored == [True]
    assert load_run(runner.last_result["path"])["status"] == "cancelled"


def test_cleanup_failure_overrides_stop_and_is_retained(tmp_path):
    _, context, plan = setup(tmp_path)
    class Backend(SyntheticSlowScanBackend):
        def prepare(self, *args):
            raise InterruptedError("operator stopped")
        def restore(self):
            return {"safe_verified": False, "errors": ["pump OFF readback failed"]}
    runner = SlowScanRunner(context, backend_factory=Backend)
    with pytest.raises(RuntimeError, match="pump OFF readback failed"):
        runner.run(operation(context, plan, "dark"), Worker())
    assert load_run(runner.last_result["path"])["cleanup_error"] == "pump OFF readback failed"


def test_storage_failure_is_truthful_and_retains_in_memory_native(tmp_path, monkeypatch):
    _, context, plan = setup(tmp_path)
    from control_app.measurement_modules.steady_state_slow_scan import persistence
    monkeypatch.setattr(persistence, "save_run", lambda *args: (_ for _ in ()).throw(OSError("disk unavailable")))
    runner = SlowScanRunner(context)
    with pytest.raises(RuntimeError, match="disk unavailable"):
        runner.run(operation(context, plan, "dark"), Worker())
    assert runner.last_result["restoration"]["safe_verified"]
    assert runner.last_result["dark_native_records"]


def test_ownership_held_through_cleanup_saving_and_sibling_manual_contention(tmp_path, monkeypatch):
    coordinator, context, plan = setup(tmp_path)
    sibling = ContextFactory(ownership=coordinator).for_experiment("steady_state_slow_scan").for_mode("dual")
    real_plan = replace(plan, inputs=replace(plan.inputs, simulation=False), readiness=())
    from control_app.measurement_modules.steady_state_slow_scan import planner, persistence
    monkeypatch.setattr(planner, "inputs_from_context", lambda *a: real_plan.inputs)
    calls = []
    class Backend(SyntheticSlowScanBackend):
        def prepare(self, *args):
            context.ownership.assert_owner(self.operation.ownership)
            with pytest.raises(OwnershipError):
                sibling.begin_operation({}, hardware=True)
            with pytest.raises(OwnershipError):
                coordinator.acquire("manual_control:single", purpose="manual adjustment")
            calls.append("acquire")
            super().prepare(*args)
        def restore(self):
            context.ownership.assert_owner(self.operation.ownership)
            calls.append("restore")
            return super().restore()
    save = persistence.save_run
    def save_owned(*args):
        assert coordinator.snapshot()["state"] == "owned"
        calls.append("save")
        return save(*args)
    monkeypatch.setattr(persistence, "save_run", save_owned)
    SlowScanRunner(context, backend_factory=Backend).run(operation(context, real_plan, "dark", hardware=True), Worker())
    assert calls == ["acquire", "restore", "save"]
    assert coordinator.snapshot()["state"] == "free"


def test_frozen_save_root_stays_with_operation(tmp_path):
    _, context, plan = setup(tmp_path)
    snapshot = operation(context, plan, "dark")
    result = SlowScanRunner(context).run(snapshot, Worker())
    assert str(tmp_path / "measurements" / "steady_state_slow_scan" / "single") in result["path"]
