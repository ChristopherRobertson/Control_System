"""Native/lifecycle verification using only injected devices and temporary roots."""
from dataclasses import replace

import numpy as np
import pytest

from control_app.measurement_host.context import ContextFactory
from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError, require_hardware_owner
from control_app.measurement_modules.nanosecond_stroboscopy.adapters import InstalledAdapter, installed_readiness, integrate_impulse
from control_app.measurement_modules.nanosecond_stroboscopy.persistence import NativeStore, load_run
from control_app.measurement_modules.nanosecond_stroboscopy.planner import build_plan
from control_app.measurement_modules.nanosecond_stroboscopy.runner import Runner, SimulationAdapter
from control_app.measurement_modules.nanosecond_stroboscopy.settings import Settings


def plan(mode="single", **updates):
    updates.setdefault("execution_mode", "simulation")
    return build_plan(replace(Settings(mode=mode), wavenumbers_cm1=(1942.,),
        delays_ns=(-300., -100., 0., 100., 400., 1600., 4000.), repetitions=1, **updates))


def context(tmp_path, mode="single", **kw):
    coordinator = kw.pop("ownership", HardwareCoordinator(tmp_path / "owner.lock"))
    factory = ContextFactory(save_root_provider=lambda: tmp_path / "output", ownership=coordinator, **kw)
    return factory.for_experiment("nanosecond_stroboscopy").for_mode(mode), coordinator, factory


def execute(ctx, p, kind, **kwargs):
    op = ctx.begin_operation(p.settings.to_dict(), hardware=p.settings.execution_mode == "connected")
    return Runner(ctx).run(op, p, kind=kind, **kwargs)


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_ns_acquisition_complete_native_workflow(tmp_path, mode):
    ctx, _, _ = context(tmp_path, mode)
    p = plan(mode)
    blank = execute(ctx, p, "blank") if mode == "single" else None
    if blank:
        assert len(blank["events"]) == len(p.events)
        assert all(not e["pump_evidence"]["commanded"] for e in blank["events"])
    baseline = execute(ctx, p, "preliminary", blank=blank)
    assert baseline["status"] == "completed", baseline["error"]
    result = execute(ctx, p, "measurement", baseline=baseline, blank=blank,
                     scientific_context={"ui_instrument_state": {"hf2li.range": 1.}})
    assert result["status"] == "completed", result["error"]
    assert result["result"]["coverage"].min() > 0
    retained = load_run(result["output_path"], expected_mode=mode)
    assert retained["ui_instrument_state"] == {"hf2li.range": 1.}
    for original, reloaded in zip(result["events"], retained["events"]):
        assert np.array_equal(original["sample"]["value"], reloaded["sample"]["value"])
    assert retained["restoration"]["safe_verified"]


def test_ns_acquisition_incomplete_blank_stops_before_device_creation(tmp_path):
    ctx, _, _ = context(tmp_path)
    p = plan()
    blank = execute(ctx, p, "blank")
    blank["events"] = blank["events"][:1]
    result = execute(ctx, p, "preliminary", blank=blank)
    assert result["status"] == "failed"
    assert "blank" in result["error"].lower()
    assert not result["events"]
    assert result["restoration"]["safe_verified"]


def test_ns_acquisition_cancellation_preparation_preserves_status(tmp_path):
    ctx, _, _ = context(tmp_path)
    p = plan()
    worker = type("Worker", (), {"check_cancelled": lambda self: (_ for _ in ()).throw(InterruptedError("stop"))})()
    result = execute(ctx, p, "blank", worker=worker)
    assert result["status"] == "cancelled"
    assert load_run(result["output_path"])["status"] == "cancelled"
    assert result["preservation_verified"]


class InjectedAdapter(SimulationAdapter):
    def prepare(self):
        with self.context.hardware_scope(self.operation):
            self.device = self.context.devices.create("hf2li", self.operation)
            assert require_hardware_owner() == self.operation.ownership
        return {"injected_device": True}


def connected_fixture(tmp_path, mode="dual"):
    calls = []
    def factory(*, configuration):
        calls.append(require_hardware_owner())
        return object()
    ctx, owner, factory_context = context(tmp_path, mode, real_device_factories={"hf2li": factory})
    simulated = plan(mode)
    p = replace(simulated, settings=replace(simulated.settings, execution_mode="connected"),
                resolved_settings=replace(simulated.resolved_settings, execution_mode="connected"), readiness=())
    return ctx, owner, factory_context, p, calls


def test_ns_acquisition_owned_through_save_and_sibling_manual_contention(tmp_path):
    ctx, owner, factories, p, calls = connected_fixture(tmp_path)
    sibling = factories.for_experiment("nanosecond_stroboscopy").for_mode("single")
    states = []
    class Store(NativeStore):
        def finish(self, *args, **kwargs):
            states.append(owner.snapshot()["state"])
            with pytest.raises(OwnershipError):
                sibling.begin_operation({}, hardware=True)
            with pytest.raises(OwnershipError):
                owner.acquire("manual:controls")
            return super().finish(*args, **kwargs)
    op = ctx.begin_operation(p.settings.to_dict(), hardware=True)
    result = Runner(ctx, adapter_factory=InjectedAdapter, store_factory=Store).run(op, p, kind="preliminary")
    assert result["status"] == "completed", result["error"]
    assert calls == [op.ownership]
    assert states == ["owned"]
    assert owner.snapshot()["state"] == "free"


@pytest.mark.parametrize("failure", ["restore", "save", "append"])
def test_ns_acquisition_fault_precedence_and_ownership_retention(tmp_path, failure):
    ctx, owner, _, p, _ = connected_fixture(tmp_path)
    class Adapter(InjectedAdapter):
        def acquire(self, event, **kwargs):
            if failure == "restore":
                raise InterruptedError("Acquisition stopped")
            return super().acquire(event, **kwargs)
        def restore(self):
            if failure == "restore":
                return {"safe_verified": False, "errors": ["injected T660 disable failed"]}
            return super().restore()
    class Store(NativeStore):
        def append_event(self, event):
            if failure == "append":
                raise OSError("injected event journal failure")
            return super().append_event(event)
        def finish(self, *args, **kwargs):
            if failure == "save":
                raise OSError("injected final storage failure")
            return super().finish(*args, **kwargs)
    op = ctx.begin_operation(p.settings.to_dict(), hardware=True)
    result = Runner(ctx, adapter_factory=Adapter, store_factory=Store).run(op, p, kind="preliminary")
    assert result["status"] == "failed"
    assert owner.snapshot()["state"] == "fault"
    if failure == "restore":
        assert result["error"].startswith("Restoration failed")
        assert "Original outcome" in result["error"]
    else:
        assert not result["preservation_verified"]
    if failure == "append":
        rescued = load_run(result["output_path"])
        assert len(rescued["events"]) == 1
        assert rescued["preservation_verified"] is False
        np.testing.assert_array_equal(rescued["events"][0]["sample"]["value"], result["events"][0]["sample"]["value"])
    # Only the injected test token is released for temporary-file teardown.
    ctx.ownership.release(op.ownership, safe_verified=True, preservation_verified=True, detail="Injected test teardown")


def test_ns_acquisition_normal_abort_retains_completed_event(tmp_path):
    ctx, _, _ = context(tmp_path, "dual")
    p = plan("dual")
    runner = Runner(ctx)
    class Adapter(SimulationAdapter):
        def acquire(self, event, **kwargs):
            result = super().acquire(event, **kwargs)
            runner.request_abort()
            return result
    runner.adapter_factory = Adapter
    op = ctx.begin_operation(p.settings.to_dict())
    result = runner.run(op, p, kind="preliminary")
    assert result["status"] == "cancelled"
    assert len(load_run(result["output_path"])["events"]) == 1


def test_ns_acquisition_reset_history_limits_claims_without_stopping_raw(tmp_path):
    ctx, _, _ = context(tmp_path, "dual")
    p = plan("dual", reset_residual_fraction=.2)
    baseline = execute(ctx, p, "preliminary")
    result = execute(ctx, p, "measurement", baseline=baseline)
    assert result["status"] == "completed", result["error"]
    assert any("reset_failed" in event["quality_flags"] for event in result["events"])
    assert len(result["events"]) == len(p.events)
    assert any(event["reset_evidence"]["equivalent"] is False for event in result["events"])


def test_ns_installed_readiness_does_not_gate_raw_on_scientific_metadata():
    assert installed_readiness({}, Settings().to_dict(), {}) == ()


def test_ns_installed_impulse_projection_retains_signed_observable_and_gaps():
    t = np.linspace(-.1, 1.0, 1101)
    impulse = np.where(t >= 0, np.exp(-t/.1) / .1, 0)
    area = np.trapezoid(impulse[(t >= 0) & (t <= .8)], t[(t >= 0) & (t <= .8)])
    raw = {"timestamp": np.round((t+2)*100000).astype(np.uint64), "x": .2 + 3.5*impulse, "y": np.zeros(len(t))}
    config = {"projection_phase_rad": 0, "integration_window_s": [0., .8], "baseline_window_s": [-.1, -.02],
        "impulse_area_gain": area, "maximum_sample_gap_s": .002, "calibration_id": "injected-impulse",
        "integrated_variance": .01, "gain_relative_variance": .001}
    original = raw["timestamp"].copy()
    integrated = integrate_impulse(raw, 2., clockbase=100000, calibration=config)
    assert integrated["value"][0] == pytest.approx(3.5, rel=.01)
    assert integrated["variance"][0] > .01
    np.testing.assert_array_equal(raw["timestamp"], original)
    broken = {k: np.delete(v, np.arange(300, 330)) for k, v in raw.items()}
    with pytest.raises(ValueError, match="Missing native support"):
        integrate_impulse(broken, 2., clockbase=100000, calibration=config)

def test_ns_installed_pending_table_uses_acknowledged_deltas_and_cancel():
    from control_app.devices.t660_service import T660Service
    from control_app.measurement_modules.nanosecond_stroboscopy.timing import compile_timing
    class AckDevice(T660Service):
        def __init__(self):
            super().__init__("t660_2", {"frames_engine": True})
            self.lines = []
            self.last = 0
        def command(self, command, **kwargs):
            self.lines.append(command)
            if command == "FEATure:FRAMe?":
                return "1"
            if command.startswith("TFRame:LOOP:LAST "):
                self.last = int(command.split()[-1])
            if command == "TFRame:LOOP:LAST?":
                return str(self.last)
            if command == "TRIGger:EXTernal:PREDiv?":
                return "1"
            if command in ("TFRame:LOOP:FIRST?", "TFRame:LOOP:CouNT?"):
                return "0"
            return ";".join("OK" for _ in command.split(";"))
    p = plan(overrides={"warmup_frames": 2})
    timing = compile_timing(p.resolved_settings)
    unit = AckDevice()
    progress = []
    result = unit.preload_frame_table(list(p.events[0].frames), predivider=1,
        input_frequency_hz=timing.input_frequency_hz, progress=lambda a, b: progress.append((a, b)))
    stores = [line for line in unit.lines if ":TFRame:STORe" in line]
    assert len(stores[0].split(";")) == 21  # full A/B/C/D pending fields + STORE
    assert stores[1] == ":TFRame:STORe 1"  # unchanged warmup pending fields retained
    assert progress[-1] == (len(p.events[0].frames), len(p.events[0].frames))
    assert result["readback"]["last"] == len(p.events[0].frames) - 1
    assert not any(line == "START" for line in unit.lines)
    cancelled = AckDevice()
    state = {"done": 0}
    def check():
        if state["done"] == 2:
            raise InterruptedError("injected table upload cancellation")
    with pytest.raises(InterruptedError):
        cancelled.preload_frame_table(list(p.events[0].frames), predivider=1,
            input_frequency_hz=timing.input_frequency_hz, cancel_check=check,
            progress=lambda done, total: state.update(done=done))
    assert not any(line == "START" for line in cancelled.lines)


def test_ns_installed_bad_compound_ack_is_rejected():
    from control_app.devices.t660_service import T660Service, T660CommandError
    class BadAck(T660Service):
        def command(self, command, **kwargs):
            return "OK"
    unit = BadAck("t660_2", {})
    with pytest.raises(T660CommandError, match="responses"):
        unit.command_sequence([":TIME:QUEue1 1ns", ":TFRame:STORe 0"])

@pytest.mark.parametrize("bad", ["bad_reference", "clipped", "unlock", "trigger_count_error", "malformed_native"])
def test_ns_acquisition_rejected_native_preserved_before_next_pump(tmp_path, bad):
    ctx, _, _ = context(tmp_path, "dual")
    p = plan("dual")
    baseline = execute(ctx, p, "preliminary")
    class Adapter(SimulationAdapter):
        def acquire(self, event, **kwargs):
            acquired = super().acquire(event, **kwargs)
            if bad == "bad_reference":
                acquired["reference"]["value"][0] = 0
            elif bad == "malformed_native":
                acquired["sample"]["timestamp_s"] = np.array([0, 1])
            else:
                acquired["quality_flags"].append(bad)
            return acquired
    op = ctx.begin_operation(p.settings.to_dict())
    result = Runner(ctx, adapter_factory=Adapter).run(op, p, kind="measurement", baseline=baseline)
    assert result["status"] == "failed"
    assert len(result["events"]) == 1
    assert len(load_run(result["output_path"])["events"]) == 1
