"""End-to-end offline lifecycle checks; never operate physical instruments."""
from dataclasses import replace
from types import SimpleNamespace
from threading import Event

import numpy as np
import pytest

from control_app.measurement_host import ContextFactory
from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError
from control_app.measurement_host.presentation import StartSnapshot
from control_app.measurement_modules.steady_state_slow_scan.settings import SlowScanSettings, ConditionIdentity
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
    settings = SlowScanSettings(mode=mode, hardware=False, condition=ConditionIdentity(sample_id="sample-1", preparation_id="prep-1",
        cell_id="cell-1", position_id="position-1", temperature_id="room-1", matrix_id="buffer-1",
        configuration_id="config-1", temperature_k=295., temperature_uncertainty_k=.2, temperature_record_id="T-1"),
        lower_cm1=1900., upper_cm1=1910.)
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


def test_control_compatibility_ignores_metadata_but_detects_acquisition_changes(tmp_path):
    _, context, plan = setup(tmp_path)
    runner = SlowScanRunner(context)
    dark = runner.run(operation(context, plan, "dark"), Worker())
    assert not compatibility_errors(dark, plan, kind="dark")
    settings = replace(plan.settings, condition=replace(plan.settings.condition, sample_id="another"))
    changed = build_plan(settings, plan.inputs)
    assert not compatibility_errors(dark, changed)
    changed = build_plan(replace(settings, replicates=3), plan.inputs)
    assert "settings mismatch" in " ".join(compatibility_errors(dark, changed))
    assert "Detector mode" in " ".join(compatibility_errors({**dark, "mode": "dual"}, plan))
    assert not compatibility_errors(dark, plan)


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


@pytest.mark.parametrize("mode", ["single", "dual"])
@pytest.mark.parametrize("kind", ["preliminary", "measurement"])
def test_direct_sample_acquires_dark_without_approval_or_blank(tmp_path, kind, mode):
    _, context, plan = setup(tmp_path, mode)
    runner = SlowScanRunner(context)
    result = runner.run(operation(context, plan, kind), Worker())
    assert result["status"] == "completed"
    assert result["dark_native_records"]
    assert result["automatic_dark"]["dark"]["sample"] == pytest.approx(.001)
    assert result["spectra"][0].quantity == ("raw_sample_signal" if mode == "single" else "reference_normalized_ratio")
    assert load_run(result["path"])["status"] == "completed"


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


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_normal_factory_resolves_live_plan_under_ownership(tmp_path, monkeypatch, mode):
    coordinator, context, plan = setup(tmp_path, mode)
    from control_app.measurement_modules.steady_state_slow_scan import acquisition
    connected = replace(plan, settings=replace(plan.settings, hardware=True),
                        inputs=replace(plan.inputs, simulation=False), readiness=())
    calls = []
    class InjectedInstalled(SyntheticSlowScanBackend):
        def resolve_plan(self, settings, check):
            context.ownership.assert_owner(self.operation.ownership)
            calls.append("resolve")
            check()
            return connected
        def prepare(self, *args):
            calls.append("prepare")
            super().prepare(*args)
    monkeypatch.setattr(acquisition, "InstalledSlowScanBackend", InjectedInstalled)
    result = SlowScanRunner(context).run(operation(context, connected, "measurement", hardware=True), Worker())
    assert calls == ["resolve", "prepare"]
    assert result["status"] == "completed"
    assert result["plan"]["inputs"]["simulation"] is False
    assert coordinator.snapshot()["state"] == "free"


def test_automatic_dark_reuse_and_incompatible_blank_do_not_block_raw_sample(tmp_path):
    _, context, plan = setup(tmp_path)
    runner = SlowScanRunner(context)
    blank = runner.run(operation(context, plan, "blank"), Worker())
    controls = {"dark": blank["automatic_dark"], "blank": {**blank, "mode": "dual"}}
    result = runner.run(operation(context, plan, "measurement", controls), Worker())
    assert "dark_native_records" not in result  # Reuses the observed dark.
    assert result["controls"]["dark"]["run_id"] == blank["automatic_dark"]["run_id"]
    assert result["unused_controls"]["blank"]
    assert result["spectra"][0].quantity == "raw_sample_signal"


def test_legacy_record_compatibility_ignores_retired_procedure_metadata(tmp_path):
    _, context, plan = setup(tmp_path)
    dark = SlowScanRunner(context).run(operation(context, plan, "dark"), Worker())
    legacy = {**dark, "compatibility": {"settings": {**plan.settings.to_dict(),
        "physical_controls_confirmed": True, "condition_equilibrated": True},
        "selected": plan.selected, "calibration_bundle_ids": ["old-profile"],
        "configuration_id": "old-user-label"}}
    changed = replace(plan, settings=replace(plan.settings, plan_label="new label", imported_requested_metadata={"fit_peak_count": 2},
        condition=replace(plan.settings.condition, temperature_k=77., sample_id="new sample")))
    assert not compatibility_errors(legacy, changed)


def test_malformed_optional_calibration_does_not_lose_raw_acquisition(tmp_path):
    _, context, plan = setup(tmp_path)
    profile = {**plan.inputs.scientific_profile, "axis_correction": {"unknown": "legacy"},
               "path_balance": {"source": "incomplete"}}
    plan = replace(plan, inputs=replace(plan.inputs, scientific_profile=profile))
    result = SlowScanRunner(context).run(operation(context, plan, "measurement"), Worker())
    assert result["status"] == "completed"
    assert result["spectra"][0].quantity == "raw_sample_signal"
    assert set(result["spectra"][0].provenance["calibration_omitted"]) == {"axis_correction", "path_balance"}
    assert load_run(result["path"])["sweeps"]


def test_changed_qcl_current_invalidates_relative_control(tmp_path):
    _, context, plan = setup(tmp_path)
    blank = SlowScanRunner(context).run(operation(context, plan, "blank"), Worker())
    profile = {**plan.inputs.scientific_profile, "qcl_pulse_params": {"1": {
        **plan.inputs.scientific_profile["qcl_pulse_params"]["1"], "current_ma": 2.}}}
    changed = replace(plan, inputs=replace(plan.inputs, scientific_profile=profile))
    assert "qcl_pulse_params" in " ".join(compatibility_errors(blank, changed))


def test_new_acquisition_has_no_implicit_peak_model_from_legacy_settings(tmp_path):
    _, context, plan = setup(tmp_path)
    retired = {"fit_peak_count": 8, "fit_line_shape": "lorentzian", "fit_baseline_degree": 2,
               "fit_fringe_periods_cm1": [1.], "requested_resolution_cm1": .00001,
               "measured_linewidth_cm1": .00002}
    migrated = SlowScanSettings.from_dict({**plan.settings.to_dict(), **retired})
    changed = build_plan(migrated, plan.inputs)
    result = SlowScanRunner(context).run(operation(context, changed, "measurement"), Worker())
    assert result["status"] == "completed"
    assert result["fits"] == result["fit_alternatives"] == []
    assert result["analysis_policy"]["peak_model"] is None
    assert all(s.metadata["qcl"] == 1 for s in result["sweeps"])
    assert [block.to_dict() for block in changed.blocks] == [block.to_dict() for block in plan.blocks]
    assert load_run(result["path"])["settings"]["imported_requested_metadata"]["fit_peak_count"] == 8


def test_control_compatibility_uses_prepared_actual_input_ranges(tmp_path):
    from copy import deepcopy
    _, context, plan = setup(tmp_path)
    class Backend(SyntheticSlowScanBackend):
        def prepare(self, planned, compiled, check, report):
            super().prepare(planned, compiled, check, report)
            selected = deepcopy(planned.selected)
            selected["hf2li"]["sigins"]["ch1"]["range_v"] = 1.5
            return replace(planned, selected=selected)
    runner = SlowScanRunner(context, backend_factory=Backend)
    dark = runner.run(operation(context, plan, "dark"), Worker())
    assert dark["plan"]["selected"]["hf2li"]["sigins"]["ch1"]["range_v"] == 1.5
    sample = runner.run(operation(context, plan, "measurement", {"dark": dark}), Worker())
    assert "dark_native_records" not in sample
    assert sample["controls"]["dark"]["run_id"] == dark["run_id"]
