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
    p = replace(plan(mode, execution_mode="connected"), readiness=())
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


def test_ns_acquisition_reset_failure_stops_without_retry(tmp_path):
    ctx, _, _ = context(tmp_path, "dual")
    p = plan("dual", reset_residual_fraction=.2)
    baseline = execute(ctx, p, "preliminary")
    result = execute(ctx, p, "measurement", baseline=baseline)
    assert result["status"] == "failed"
    assert "reset_failed" in result["error"]
    assert len(result["events"]) < len(p.events)
    assert result["events"][-1]["reset_evidence"]["equivalent"] is False


def test_ns_installed_readiness_has_exact_missing_pulse_kernel_reasons():
    reasons = installed_readiness({}, Settings().to_dict(), {})
    assert any("sparse probe cadence" in r for r in reasons)
    assert any("integration aperture" in r for r in reasons)
    assert any("optical pump observation" in r for r in reasons)
    assert not any("hash" in r for r in reasons)


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
    p = plan()
    timing = compile_timing(p.settings)
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


def installed_extract_fixture(tmp_path):
    """Retained LabOne poll shape: demod sample dictionaries with native ticks."""
    from copy import deepcopy
    from control_app.measurement_modules.nanosecond_stroboscopy.adapters import data
    ctx, _, _ = context(tmp_path, "dual")
    p = plan("dual", optical_delay_offset_ns=7.)
    op = ctx.begin_operation(p.settings.to_dict())
    adapter = InstalledAdapter(ctx, op, p)
    ev = data(p.events[0])
    count = len(ev["frames"])
    t = np.arange(500, (count + 1) * 1000 + 1, dtype=float) / 1000
    ticks = (t * 1000000).round().astype(np.uint64)
    epochs = np.arange(1, count + 1, dtype=float)
    impulse = np.zeros(len(t))
    dio = np.zeros(len(t), dtype=np.uint32)
    for epoch in epochs:
        dt = t - epoch
        pulse = dt >= 0
        impulse[pulse] += np.exp(-dt[pulse]/.05)/.05
        dio[(dt >= 0) & (dt < .004)] |= 1 << 19
    relative = np.arange(0, 801)/1000
    gain = np.trapezoid(np.exp(-relative/.05)/.05, relative)
    calibration = {"projection_phase_rad": 0., "integration_window_s": [0., .8],
        "baseline_window_s": [-.1, -.02], "impulse_area_gain": gain,
        "maximum_sample_gap_s": .0011, "calibration_id": "injected-native-impulse-v1",
        "integrated_variance": .001, "gain_relative_variance": .0001}
    adapter.qualification = {"impulse_calibration": {"sample": calibration, "reference": deepcopy(calibration)},
        "qualification_id": "injected-kernel-v1", "optical_delay_offset_ns": 7.,
        "optical_timing_calibration_id": "injected-optical-v1", "sample_reference_covariance": .00001,
        "probe_period_tolerance_s": .00001}
    adapter.readbacks = {"clockbase": 1000000, "wavelength": {"value": 1942., "units": "cm^-1", "light_valid": True}}
    native = {"timestamp_utc": "2026-09-09T00:00:00Z", "duration_s": float(t[-1]-t[0]), "data": {
        "/dev18500/demods/0/sample": {"timestamp": ticks.copy(), "x": .2+3.5*impulse, "y": np.zeros(len(t))},
        "/dev18500/demods/3/sample": {"timestamp": ticks.copy(), "x": .4+7.*impulse, "y": np.zeros(len(t))},
        "/dev18500/demods/2/sample": {"timestamp": ticks.copy(), "dio": dio}}}
    adapter.pending_native = [native]
    return adapter, ev


def test_ns_installed_extract_native_stream_observable_and_optical_provenance(tmp_path):
    from copy import deepcopy
    adapter, ev = installed_extract_fixture(tmp_path)
    original = deepcopy(adapter.pending_native)
    event = adapter._extract(ev, "measurement")
    assert event["sample"]["value"][0] == pytest.approx(3.5, rel=.003)
    assert event["reference"]["value"][0] == pytest.approx(7., rel=.003)
    assert event["sample"]["timestamp_s"][0] == 3.
    assert event["sample_reference_covariance"] == .00001
    assert event["calibrated_optical_delay_ns"] == pytest.approx(ev["electrical_delay_ns"] + 7.)
    assert event["observed_electrical_delay_ns"] is None
    assert event["pump_evidence"]["optical_pulse_count"] is None
    assert "per_event_optical_pump_unobserved" in event["quality_flags"]
    for path, stream in original[0]["data"].items():
        for field, values in stream.items():
            np.testing.assert_array_equal(event["native_device_data"][0]["data"][path][field], values)
    # Acquiring an unpumped sample does not invent a pump or label null optical
    # counts as a failed pump observation.
    unpumped = adapter._extract(ev, "preliminary")
    assert unpumped["pump_evidence"]["optical_pulse_count"] == 0
    assert not unpumped["quality_flags"]


@pytest.mark.parametrize("mismatch", ["missing", "extra"])
def test_ns_installed_extract_probe_count_mismatch_rejected(tmp_path, mismatch):
    adapter, ev = installed_extract_fixture(tmp_path)
    stream = adapter.pending_native[0]["data"]["/dev18500/demods/2/sample"]
    if mismatch == "missing":
        stream["dio"][stream["timestamp"] >= len(ev["frames"]) * 1000000] = 0
    else:
        stream["dio"][10:13] = 1 << 19
    with pytest.raises(ValueError, match="probe pulse count differs"):
        adapter._extract(ev, "measurement")


def test_ns_installed_restore_attempts_every_inhibit_bank_and_device_after_failure(tmp_path):
    adapter, _ = installed_extract_fixture(tmp_path)
    calls = []
    class Timing:
        def __init__(self, name): self.name = name
        def set_trigger_source(self, source): calls.append((self.name, "source", source))
        def command(self, command, **kwargs):
            calls.append((self.name, command))
            if self.name == "t660_2" and command == "TFRame:STOp":
                raise RuntimeError("injected failed frame stop")
        def disable_channel(self, channel): calls.append((self.name, "disable", channel))
        def configure_train(self, *, count, stage):
            calls.append((self.name, "train", stage))
            if stage == "ACTIVE": raise RuntimeError("injected active bank error")
        def close(self): calls.append((self.name, "close"))
    class QCL:
        def turn_emission_off(self):
            calls.append(("mircat", "off"))
            raise RuntimeError("injected emission off error")
        def disarm(self): calls.append(("mircat", "disarm"))
        def deinitialize(self): calls.append(("mircat", "close"))
    class HF:
        def stop_acquisition(self): calls.append(("hf2li", "stop"))
        def close(self): calls.append(("hf2li", "close"))
    adapter.devices = {"t660_1": Timing("t660_1"), "t660_2": Timing("t660_2"), "hf2li": HF(), "mircat": QCL()}
    report = adapter.restore()
    assert report["safe_verified"] is False
    assert len(report["errors"]) == 2
    for bank in ("ACTIVE", "NEXT", "QUEUE"):
        assert ("t660_2", "train", bank) in calls
    for device in adapter.devices:
        assert (device, "close") in calls
    assert ("mircat", "disarm") in calls
    assert ("hf2li", "stop") in calls

def test_ns_installed_mircat_service_signature_and_actual_wavelength_shape(tmp_path):
    from unittest.mock import create_autospec
    from control_app.devices.mircat_service import MircatService
    adapter, _ = installed_extract_fixture(tmp_path)
    qcl = create_autospec(MircatService, instance=True)
    qcl.is_tuned.return_value = True
    qcl.is_laser_armed.return_value = False
    qcl.get_actual_wavelength.return_value = {"value": 1942., "units": "cm^-1", "light_valid": True}
    adapter.devices = {"mircat": qcl}
    adapter.qualification.update(qcl_index=1, tune_timeout_s=1., settling_s=0., wavenumber_tolerance_cm1=.1)
    adapter.tune(1942.)
    qcl.set_external_trigger_params.assert_called_once_with(wavenumber_cm1=1942.)
    qcl.tune_to_wavenumber.assert_called_once_with(1942., qcl=1)
    qcl.turn_emission_on.assert_called_once_with(approved_laser_safety_condition=True)
    assert adapter.readbacks["wavelength"]["units"] == "cm^-1"


def test_ns_installed_mircat_trigger_readback_mismatch_is_restoration_failure(tmp_path):
    from unittest.mock import create_autospec
    from control_app.devices.mircat_service import MircatService
    adapter, _ = installed_extract_fixture(tmp_path)
    qcl = create_autospec(MircatService, instance=True)
    trigger = {"pulse_mode": 0, "process_trigger_mode": 0, "start": 1942., "stop": 1942.,
               "interval": 0., "units": 1, "dwell_us": 0, "after_off_us": 0}
    qcl.get_wavelength_trigger_params.return_value = {**trigger, "pulse_mode": 1}
    qcl.read_state.return_value = {"emission_on": False, "armed": False}
    adapter.devices = {"mircat": qcl}
    adapter.before["mircat"] = {"trigger": trigger, "qcl": 1, "pulse_rate_hz": 1., "pulse_width_ns": 20., "current_ma": 40.}
    report = adapter.restore()
    assert report["safe_verified"] is False
    assert "trigger pulse_mode did not restore" in ";".join(report["errors"])
    qcl.set_wavelength_trigger_params.assert_called_once_with(**trigger)
    qcl.deinitialize.assert_called_once()
