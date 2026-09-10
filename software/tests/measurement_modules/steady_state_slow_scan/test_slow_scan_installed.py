"""Exercise genuine installed adapters using host-owned injected instrument services."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from control_app.measurement_host import ContextFactory
from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError
from control_app.measurement_modules.steady_state_slow_scan import acquisition
from control_app.measurement_modules.steady_state_slow_scan.acquisition import InstalledSlowScanBackend
from control_app.measurement_modules.steady_state_slow_scan.planner import build_plan, simulation_inputs
from control_app.measurement_modules.steady_state_slow_scan.settings import SlowScanSettings, ConditionIdentity, SpectralSegment
from control_app.measurement_modules.steady_state_slow_scan.timing import compile_timing


class VirtualClock:
    def __init__(self):
        self.time = 0.
    def advance(self, seconds):
        self.time += seconds
    def now(self):
        return self.time


class InjectedService:
    def __init__(self, guard):
        self.guard = guard
        self.calls = []
        self.closed = False

    def touch(self, name):
        self.guard()
        self.calls.append(name)

    def connect(self):
        self.touch("connect")

    def close(self):
        self.touch("close")
        self.closed = True


class TimingService(InjectedService):
    def __init__(self, name, guard):
        super().__init__(guard)
        self.name = name
        self.channels = {ch: False for ch in "ABCD"}
        self.source = "OFF"
        self.frames = []
        self.recipes = []
        self.shot_error = 0
        self.fail_disable = False
        self.references = {edge: edge - 1 if edge % 2 == 0 else 0 for edge in range(1, 9)}
        self.absolute = {0: 0., **{edge: 1e-6 if edge % 2 == 0 else 0. for edge in range(1, 9)}}
        self.pending = {}
        self.modes = {channel: "DW" for channel in "ABCD"}
        self.receiver = {"polarity": "positive", "termination": "50OHM", "threshold_v": 2.}

    def set_trigger_source(self, source):
        self.touch(f"source {source}")
        self.source = source

    def disable_channel(self, channel):
        self.touch(f"disable {channel}")
        if self.fail_disable and channel == "A":
            raise RuntimeError("injected OFF acknowledgment failure")
        self.channels[channel] = False

    def enable_channel(self, channel):
        self.touch(f"enable {channel}")
        assert not (self.name == "t660_2" and channel in "AB"), "A pump output was enabled"
        self.channels[channel] = True

    def command(self, text, **kwargs):
        self.touch(text)
        if self.name == "t660_1" and text.startswith("TFRame:"):
            raise RuntimeError("T660-1 does not support the Trains and Frames extension")
        if text.startswith("TIME:RELTo") and text.endswith("?"):
            return str(self.references[int(text.removeprefix("TIME:RELTo").removesuffix("?"))])
        if text.startswith("TIME:RELTo"):
            edge, reference = text.removeprefix("TIME:RELTo").split()
            self.references[int(edge)] = int(reference)
        if text.startswith("TIME:QUEue"):
            edge, value = text.removeprefix("TIME:QUEue").split()
            self.pending[int(edge)] = acquisition._quantity(value)
        if text == "TIME:COMmit":
            self.absolute.update(self.pending)
            self.pending.clear()
        if text.startswith("CHAN:ON?"):
            return "1" if self.channels[text[-1]] else "0"
        if text == "TRIG:SOUR?":
            return self.source
        return "0"

    def read_active_settings(self):
        self.touch("read_active_settings")
        response = lambda value: {"ok": True, "response": str(value)}
        return {"queries": {"predivider": response(1), "synth_frequency": response("100000Hz"),
                            "clock_connector_mode": response("IN" if self.name == "t660_1" else "OUT"),
                            "clock_external_lock_enabled": response("1" if self.name == "t660_1" else "0"),
                            "clock_external_frequency_hz": response("10000000"),
                            "clock_lock_status": response("LOCKED" if self.name == "t660_1" else "INTERNAL"),
                            "trigger_input_polarity": response(self.receiver["polarity"]),
                            "trigger_input_termination": response(self.receiver["termination"]),
                            "trigger_input_threshold_v": response(self.receiver["threshold_v"])},
                "channels": {ch: {"delay_edge": response(f"{self.absolute[index * 2 + 1] - self.absolute[self.references[index * 2 + 1]]:.12g}s"),
                                  "width_edge": response(f"{self.absolute[index * 2 + 2] - self.absolute[self.references[index * 2 + 2]]:.12g}s"),
                                  "polarity": response("positive"), "termination": response("50OHM"),
                                  "timing_mode": response(self.modes[ch])} for index, ch in enumerate("ABCD")}}

    def set_channel_timing_mode(self, channel, mode):
        self.touch("set_channel_timing_mode")
        self.modes[channel] = "RF" if str(mode).upper() in ("RISE_FALL", "RF") else "DW"
        if self.modes[channel] == "DW":
            rising = 2 * "ABCD".index(channel) + 1
            self.references[rising + 1] = rising

    def apply_recipe(self, recipe):
        self.touch("apply_recipe")
        self.recipes.append(deepcopy(recipe))
        self.source = recipe["trigger_source"]
        if "external_trigger" in recipe:
            self.receiver = deepcopy(recipe["external_trigger"])
        for ch, value in recipe["channels"].items():
            if self.name == "t660_2" and ch in "AB":
                assert value["enabled"] is False
            self.channels[ch] = value["enabled"]
            if "delay" in value:
                self.set_channel_timing_mode(ch, "delay_width")
                rising = 2 * "ABCD".index(ch) + 1
                self.absolute[rising] = self.absolute[self.references[rising]] + acquisition._quantity(value["delay"])
                self.absolute[rising + 1] = self.absolute[rising] + acquisition._quantity(value["width"])
            elif "timing_mode" in value:
                self.set_channel_timing_mode(ch, value["timing_mode"])

    def start_continuous_clock(self):
        self.touch("start_continuous_clock")
        self.source = "SYN"

    def preload_frame_table(self, *, frames, predivider, input_frequency_hz, progress, cancel_check):
        self.touch("preload_frame_table")
        assert self.source == "OFF"
        progress(0, len(frames))
        for index, frame in enumerate(frames):
            cancel_check()
            assert set(frame["channels"]) == set("ABCD")
            assert not frame["channels"]["A"]["enabled"]
            assert not frame["channels"]["B"]["enabled"]
            progress(index + 1, len(frames))
        self.frames = deepcopy(frames)
        self.receiver = {"polarity": "positive", "termination": "50OHM", "threshold_v": 2.}
        return {"physical_frame_count": len(frames), "acknowledged": True}

    def start_frame_table(self):
        self.touch("start_frame_table")
        self.source = "EXT"

    def get_frames_status(self):
        self.touch("get_frames_status")
        return "DONE"

    def get_shot_count(self):
        self.touch("get_shot_count")
        return len(self.frames) + self.shot_error

    def verified_frame_capacity(self):
        self.touch("verified_frame_capacity")
        return 8192


class QCLService(InjectedService):
    def __init__(self, guard):
        super().__init__(guard)
        self.emission = False
        self.sweep = {}
        self.pulse = {"pulse_rate_hz": 100000., "pulse_width_ns": 1000., "current_ma": 1.}
        self.trigger = {"pulse_mode": 2, "process_trigger_mode": 1, "start": 1900., "stop": 1900.4,
                        "interval": .1, "units": 2, "dwell_us": 0, "after_off_us": 0}
        self.width_us = 1000
        self.sweep_generation = 0
        self.bad_readback = False

    def initialize(self): self.touch("initialize")
    def deinitialize(self): self.close()
    def arm(self): self.touch("arm")
    def disarm(self): self.touch("disarm")
    def cancel_manual_tune(self): self.touch("cancel_manual_tune")
    def are_tecs_ready(self): self.touch("are_tecs_ready"); return True
    def is_tuned(self): self.touch("is_tuned"); return True
    def tune_to_wavenumber(self, *args, **kwargs): self.touch("tune_to_wavenumber")
    def get_num_installed_qcls(self): self.touch("get_num_installed_qcls"); return 1
    def get_qcl_tuning_range(self, qcl): self.touch("get_qcl_tuning_range"); return {"qcl": qcl, "min_cm1": 1800., "max_cm1": 2000.}
    def get_qcl_pulse_limits(self, qcl): return {"max_pulse_rate_hz": 200000., "max_pulse_width_ns": 2000., "max_duty_cycle": 30.}
    def get_qcl_current_limits(self, qcl): return (0., 10.)
    def get_qcl_pulse_rate(self, qcl): return self.pulse["pulse_rate_hz"]
    def get_qcl_pulse_width(self, qcl): return self.pulse["pulse_width_ns"]
    def get_qcl_current(self, qcl): return self.pulse["current_ma"]
    def get_wavelength_trigger_params(self): return deepcopy(self.trigger)
    def get_wavelength_trigger_pulse_width_us(self): return self.width_us
    def is_interlock_set(self): return True
    def is_key_switch_set(self): return True
    def get_system_error_word(self): return 0
    def get_scan_waiting_process_trigger(self): return True
    def is_emission_on(self): return self.emission

    def set_qcl_pulse_params(self, *, qcl, **params):
        self.touch("set_qcl_pulse_params")
        self.pulse = deepcopy(params)
        return deepcopy(params)

    def set_external_sweep_trigger_params(self, **params):
        self.touch("set_external_sweep_trigger_params")
        self.trigger.update(start=params["start_cm1"], stop=params["stop_cm1"],
                            interval=params["wavelength_trigger_interval_cm1"], process_trigger_mode=2)

    def set_wavelength_trigger_pulse_width_us(self, width):
        self.touch("set_wavelength_trigger_pulse_width_us")
        self.width_us = width
        return width

    def set_wavelength_trigger_params(self, **params):
        self.touch("set_wavelength_trigger_params")
        self.trigger = deepcopy(params)

    def start_sweep_scan(self, **params):
        self.touch("start_sweep_scan")
        self.sweep = deepcopy(params)
        self.sweep_generation += 1

    def get_sweep_parameters(self):
        result = deepcopy(self.sweep)
        if self.bad_readback:
            result["scan_rate_cm1_s"] *= 2
        return result

    def get_wavelength_trigger_channel_params(self, channel):
        interval = self.trigger["interval"]
        count = round(abs(self.trigger["stop"] - self.trigger["start"]) / interval) + 1
        return {"start": self.trigger["start"], "interval": interval, "num_triggers": count, "units": 2}

    def turn_emission_off(self): self.touch("turn_emission_off"); self.emission = False
    def stop_scan_if_needed(self): self.touch("stop_scan_if_needed")
    def turn_emission_on(self, **kwargs): self.touch("turn_emission_on"); self.emission = True


class HFService(InjectedService):
    device_id = "devTEST"

    def __init__(self, guard, clock, services):
        super().__init__(guard)
        self.clock, self.services = clock, services
        self.nodes = {f"/{self.device_id}/demods/{i}/{field}": {"type": "int" if field in ("order", "adcselect", "enable") else "double", "value": value}
                      for i in range(6) for field, value in (("rate", 1000.), ("timeconstant", .001), ("order", 2), ("adcselect", 0),
                                                            ("oscselect", 0), ("harmonic", 1), ("trigger", 0), ("enable", 0))}
        for index in (0, 1):
            for node, value in (("ac", 0), ("imp50", 0), ("diff", 0), ("range", 1.)):
                self.nodes[f"/{self.device_id}/sigins/{index}/{node}"] = {"value": value, "type": "double" if node == "range" else "int"}
        for node, value in (("enable", 1), ("adcselect", 8), ("freqcenter", 100000.), ("harmonic", 1), ("order", 1), ("adcthreshold", 0)):
            self.nodes[f"/{self.device_id}/plls/0/{node}"] = {"value": value, "type": "double" if node == "freqcenter" else "int"}
        self.presets, self.subscriptions = [], []
        self.delivered = set()
        self.bad_readback = False
        self.bad_health = False
        self.bad_restoration = False
        self.oscillator_drift = False
        self.reload_calls = []
        self.native_delivered = []

    def export_settings_snapshot(self, **kwargs):
        self.touch("export_settings_snapshot")
        result = {"nodes": deepcopy(self.nodes), "read_errors": []}
        if self.bad_readback and self.presets:
            result["nodes"][f"/{self.device_id}/demods/0/rate"]["value"] += 1.
        return result

    def configure_demodulators(self, values):
        self.touch("configure_demodulators")
        names = {"rate_sps": "rate", "timeconstant_s": "timeconstant", "order": "order", "adcselect": "adcselect", "enable": "enable",
                 "oscselect": "oscselect", "harmonic": "harmonic", "trigger": "trigger"}
        for item in values:
            for key, node in names.items():
                if key in item:
                    self.nodes[f"/{self.device_id}/demods/{item['index']}/{node}"]["value"] = item[key]

    def apply_preset(self, preset):
        self.touch("apply_preset")
        self.presets.append(deepcopy(preset.settings))
        self.configure_demodulators(preset.settings["demodulators"])
        for item in preset.settings["signal_inputs"].values():
            for key, node in (("ac", "ac"), ("impedance_50ohm", "imp50"), ("differential", "diff"), ("range_v", "range")):
                self.nodes[f"/{self.device_id}/sigins/{item['index']}/{node}"]["value"] = item[key]
        item = preset.settings["pll"]
        for key, node in (("enable", "enable"), ("adcselect", "adcselect"), ("freqcenter_hz", "freqcenter"), ("harmonic", "harmonic"), ("order", "order"), ("adcthreshold", "adcthreshold")):
            self.nodes[f"/{self.device_id}/plls/{item['index']}/{node}"]["value"] = item[key]

    def reload_settings_snapshot(self, snapshot):
        self.touch("reload_settings_snapshot")
        self.reload_calls.append(deepcopy(snapshot["nodes"]))
        self.nodes.update(deepcopy(snapshot["nodes"]))
        self.bad_readback = False
        if self.bad_restoration:
            self.nodes[next(iter(self.nodes))]["value"] += 1
        if self.oscillator_drift:
            self.nodes[f"/{self.device_id}/oscs/0/freq"] = {"value": 3., "type": "double"}

    def compare_settings_snapshots(self, before, after):
        return {"match": all(after["nodes"].get(key) == value for key, value in before["nodes"].items())}

    def get_clockbase(self): return 1000000.
    def _get_node(self, *args): self.touch("health_readback"); return int(self.bad_health)
    def start_acquisition(self, *, demodulators): self.touch("start_acquisition"); self.subscriptions.append(tuple(demodulators))
    def stop_acquisition(self): self.touch("stop_acquisition")

    def read_acquisition(self, duration):
        self.touch("read_acquisition")
        self.clock.advance(duration)
        qcl = self.services["mircat"]
        generation = qcl.sweep_generation if qcl.emission else "dark"
        if generation in self.delivered:
            return {"data": {}}
        self.delivered.add(generation)
        times = np.arange(0., 1.05, .0001)
        epoch = 0 if generation == "dark" else generation * 5_000_000
        ticks = np.uint64(2 ** 54 + epoch) + np.rint(times * 1e6).astype(np.uint64)
        dio = np.zeros(len(times), dtype=np.uint64)
        if generation != "dark":
            for rep in range(qcl.sweep["repetitions"]):
                start = .1 + rep * .4
                active = (times >= start) & (times <= start + .22)
                dio[active] |= np.uint64(1 << 21)
                if qcl.sweep["start_cm1"] < qcl.sweep["stop_cm1"]:
                    dio[active] |= np.uint64(1 << 20)
                for step in range(5):
                    edge = start + .005 + step * .05
                    dio[(times >= edge) & (times <= edge + .001)] |= np.uint64(1 << 22)
        sample_ticks = ticks[::10]
        data = {f"/{self.device_id}/demods/0/sample": {"timestamp": sample_ticks, "x": np.linspace(.8, .9, len(sample_ticks)), "y": np.zeros(len(sample_ticks))},
                f"/{self.device_id}/demods/2/sample": {"timestamp": ticks, "dio": dio},
                f"/{self.device_id}/demods/3/sample": {"timestamp": sample_ticks, "x": np.ones(len(sample_ticks)), "y": np.zeros(len(sample_ticks))}}
        record = {"data": data}
        self.native_delivered.append(record)
        return record


def configured(tmp_path, monkeypatch, mode="dual"):
    from pathlib import Path
    configuration_path = Path(__file__).resolve().parents[4] / "instrument" / "hardware_configuration.yaml"
    config = yaml.safe_load(configuration_path.read_text(encoding="utf-8"))
    coordinator = HardwareCoordinator(tmp_path / "owned.lock")
    active, services = {}, {}
    clock = VirtualClock()
    monkeypatch.setattr(acquisition, "monotonic", clock.now)
    def guard():
        coordinator.assert_owner(active["operation"].ownership)
    def make(name):
        def factory(*, configuration):
            guard()
            device = HFService(guard, clock, services) if name == "hf2li" else QCLService(guard) if name == "mircat" else TimingService(name, guard)
            services[name] = device
            return device
        return factory
    context = ContextFactory(configuration_provider=lambda: config, save_root_provider=lambda: tmp_path,
                             real_device_factories={name: make(name) for name in ("hf2li", "mircat", "t660_1", "t660_2")},
                             ownership=coordinator).for_experiment("steady_state_slow_scan").for_mode(mode)
    settings = SlowScanSettings(mode=mode, segments=(SpectralSegment("band", 1, 1900., 1900.4),),
                                condition=ConditionIdentity(configuration_id="fixture-config"), physical_controls_confirmed=True)
    inputs = simulation_inputs(settings)
    profile = deepcopy(inputs.scientific_profile)
    profile["hf2li"]["reference"].update(order=3, timeconstant_s=.002, rate_sps=1000.)
    profile["hf2li"]["sigins"]["ch2"]["range_v"] = .3
    plan = build_plan(settings, replace(inputs, scientific_profile=profile))
    compiled = compile_timing(plan)
    operation = context.begin_operation(settings.to_dict(), hardware=True)
    active["operation"] = operation
    backend = InstalledSlowScanBackend(context, operation)
    backend._stop_wait = SimpleNamespace(wait=clock.advance)
    return context, coordinator, operation, backend, plan, compiled, services


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_owned_installed_adapter_dark_and_both_directions_retain_native(tmp_path, monkeypatch, mode):
    context, coordinator, operation, backend, plan, compiled, services = configured(tmp_path, monkeypatch, mode)
    updates = []
    with context.hardware_scope(operation):
        backend.prepare(plan, compiled, lambda: None, lambda *args: updates.append(args))
        dark = backend.acquire_dark(plan, lambda: None, lambda *args: updates.append(args))
        assert dark
        trajectories = []
        for block in compiled.blocks:
            trajectories.extend(backend.acquire_block(block, plan, lambda: None, lambda *args: updates.append(args)))
        result = backend.restore()
    assert result["safe_verified"], result["errors"]
    assert len(trajectories) == 4
    assert {sweep["direction_bit"] for sweep in trajectories} == {0, 1}
    assert trajectories[2]["timestamps_s"][0] > trajectories[1]["timestamps_s"][-1]
    assert len({sweep["time_origin_ticks"] for sweep in trajectories}) == 1
    assert all(np.count_nonzero(sweep["valid"]) > 100 for sweep in trajectories)
    assert all(not sweep["flags"] for sweep in trajectories)
    assert any("Acknowledged" in message[1] for message in updates)
    preset = services["hf2li"].presets[0]
    demods = {item["index"]: item for item in preset["demodulators"]}
    assert demods[0]["order"] == 2
    if mode == "dual":
        assert demods[3]["order"] == 3 and demods[3]["timeconstant_s"] == .002
        assert preset["signal_inputs"]["ch2"]["range_v"] == .3
    else:
        assert 3 not in demods
    assert all(not value for name in ("t660_1", "t660_2") for value in services[name].channels.values())
    assert all(device.closed for device in services.values())
    files = list((operation.output_path / "native_chunks").glob("*.npz"))
    assert len(files) == len(backend.raw_records)
    first = np.load(files[0])
    assert any(array.dtype == np.uint64 and array.max() > 2 ** 53 for array in first.values())
    context.ownership.release(operation.ownership, safe_verified=True, preservation_verified=True, detail="Injected-device records saved")
    assert coordinator.snapshot()["state"] == "free"


@pytest.mark.parametrize("fault", ["hf_readback", "qcl_readback", "shot_count", "health"])
def test_installed_readback_and_count_faults_restore_pump_off(tmp_path, monkeypatch, fault):
    context, _, operation, backend, plan, compiled, services = configured(tmp_path, monkeypatch)
    with context.hardware_scope(operation):
        if fault == "hf_readback":
            original = backend._create
            def create(name):
                device = original(name)
                if name == "hf2li":
                    device.bad_readback = True
                return device
            monkeypatch.setattr(backend, "_create", create)
            with pytest.raises(ValueError, match="HF2LI demodulator"):
                backend.prepare(plan, compiled, lambda: None, lambda *args: None)
        else:
            backend.prepare(plan, compiled, lambda: None, lambda *args: None)
            services["mircat"].bad_readback = fault == "qcl_readback"
            services["t660_2"].shot_error = 1 if fault == "shot_count" else 0
            services["hf2li"].bad_health = fault == "health"
            with pytest.raises((ValueError, RuntimeError), match="MIRcat|shot count|clipping"):
                backend.acquire_block(compiled.blocks[0], plan, lambda: None, lambda *args: None)
        restored = backend.restore()
    assert restored["safe_verified"], restored["errors"]
    assert not services["mircat"].emission
    assert all(not value for value in services["t660_2"].channels.values())
    context.ownership.release(operation.ownership, safe_verified=True, preservation_verified=True, detail="Injected failure safely restored")


def test_installed_cleanup_failure_keeps_truthful_fault_and_attempts_other_devices(tmp_path, monkeypatch):
    context, coordinator, operation, backend, plan, compiled, services = configured(tmp_path, monkeypatch)
    with context.hardware_scope(operation):
        backend.prepare(plan, compiled, lambda: None, lambda *args: None)
        services["hf2li"].bad_restoration = True
        services["t660_2"].fail_disable = True
        restored = backend.restore()
    assert not restored["safe_verified"]
    assert any("OFF acknowledgment" in error for error in restored["errors"])
    assert any("HF2LI restoration" in error for error in restored["errors"])
    assert all(device.closed for device in services.values())
    context.ownership.release(operation.ownership, safe_verified=False, preservation_verified=True, detail="Injected cleanup failure retained")
    assert coordinator.snapshot()["state"] == "fault"


def test_injected_installed_services_are_created_only_under_host_ownership(tmp_path, monkeypatch):
    context, coordinator, operation, backend, plan, compiled, services = configured(tmp_path, monkeypatch)
    assert not services
    with context.hardware_scope(operation):
        backend.prepare(plan, compiled, lambda: None, lambda *args: None)
        restored = backend.restore()
    context.ownership.release(operation.ownership, safe_verified=restored["safe_verified"], preservation_verified=True, detail="owned test complete")
    with pytest.raises(OwnershipError):
        services["t660_2"].set_trigger_source("EXT")


@pytest.mark.parametrize("stage", ["tuning", "upload", "acquisition"])
def test_installed_cancellation_in_each_stage_keeps_off_and_preserves_partial(tmp_path, monkeypatch, stage):
    context, _, operation, backend, plan, compiled, services = configured(tmp_path, monkeypatch)
    with context.hardware_scope(operation):
        backend.prepare(plan, compiled, lambda: None, lambda *args: None)
        def cancel():
            if ((stage == "tuning" and "tune_to_wavenumber" in services["mircat"].calls) or
                (stage == "upload" and "preload_frame_table" in services["t660_2"].calls) or
                (stage == "acquisition" and services["hf2li"].native_delivered)):
                raise InterruptedError("Acquisition stopped")
        with pytest.raises(InterruptedError, match="Acquisition stopped"):
            backend.acquire_block(compiled.blocks[0], plan, cancel, lambda *args: None)
        restored = backend.restore()
    assert restored["safe_verified"], restored["errors"]
    if stage == "acquisition":
        assert backend.raw_records
        assert list((operation.output_path / "native_chunks").glob("*.npz"))
    assert not services["mircat"].emission
    assert all(not value for value in services["t660_2"].channels.values())
    context.ownership.release(operation.ownership, safe_verified=True, preservation_verified=True, detail="Injected cancellation retained")


def test_installed_clock_mismatch_blocks_before_emission(tmp_path, monkeypatch):
    context, _, operation, backend, plan, compiled, services = configured(tmp_path, monkeypatch)
    original = backend._create
    def create(name):
        device = original(name)
        if name == "t660_1":
            read = device.read_active_settings
            def snapshot():
                values = read()
                values["queries"]["clock_lock_status"]["response"] = "UNLOCKED"
                return values
            device.read_active_settings = snapshot
        return device
    monkeypatch.setattr(backend, "_create", create)
    with context.hardware_scope(operation):
        with pytest.raises(ValueError, match="clock_lock_status"):
            backend.prepare(plan, compiled, lambda: None, lambda *args: None)
        restored = backend.restore()
    assert "turn_emission_on" not in services["mircat"].calls
    assert restored["safe_verified"]
    context.ownership.release(operation.ownership, safe_verified=True, preservation_verified=True, detail="Clock failure retained")


def test_installed_wrong_direction_is_retained_but_invalid(tmp_path, monkeypatch):
    context, _, operation, backend, plan, compiled, services = configured(tmp_path, monkeypatch)
    plan.inputs.scientific_profile["direction_bit_by_direction"]["forward"] = 0
    with context.hardware_scope(operation):
        backend.prepare(plan, compiled, lambda: None, lambda *args: None)
        sweeps = backend.acquire_block(compiled.blocks[0], plan, lambda: None, lambda *args: None)
        restored = backend.restore()
    assert all("observed_direction_mismatch" in sweep["flags"] for sweep in sweeps)
    assert all(not np.any(sweep["valid"]) for sweep in sweeps)
    assert all(len(sweep["sample"]) > 0 for sweep in sweeps)
    context.ownership.release(operation.ownership, safe_verified=restored["safe_verified"], preservation_verified=True, detail="Direction evidence retained")


def test_nondefault_relative_edges_and_rise_fall_mode_restore_exactly(tmp_path, monkeypatch):
    context, _, operation, backend, plan, compiled, services = configured(tmp_path, monkeypatch)
    create_original = backend._create
    captured = {}
    def create(name):
        device = create_original(name)
        if name.startswith("t660"):
            device.absolute.update({1: 2e-6, 2: 3e-6, 3: 5e-6, 4: 7e-6, 5: 12e-6, 6: 15e-6})
            device.references.update({3: 1, 5: 1, 6: 3})
            device.modes["C"] = "RF"
            device.receiver = {"polarity": "negative", "termination": "HIZ", "threshold_v": 1.3}
            captured[name] = deepcopy((device.absolute, device.references, device.modes, device.receiver))
        return device
    monkeypatch.setattr(backend, "_create", create)
    with context.hardware_scope(operation):
        backend.prepare(plan, compiled, lambda: None, lambda *args: None)
        assert all(services["t660_1"].references[edge] == 0 for edge in (1, 3, 5, 7))
        backend.acquire_block(compiled.blocks[0], plan, lambda: None, lambda *args: None)
        restored = backend.restore()
    assert restored["safe_verified"], restored["errors"]
    for name, expected in captured.items():
        device = services[name]
        assert device.absolute == pytest.approx(expected[0])
        assert device.references == expected[1]
        assert device.modes == expected[2]
        assert device.receiver == expected[3]
        assert "TIME:COMmit" in device.calls
    context.ownership.release(operation.ownership, safe_verified=True, preservation_verified=True, detail="Restoration graph verified")


def test_hf_restore_defers_enables_and_retains_external_oscillator_drift_as_observation(tmp_path, monkeypatch):
    context, _, operation, backend, plan, compiled, services = configured(tmp_path, monkeypatch)
    original = backend._create
    def create(name):
        device = original(name)
        if name == "hf2li":
            device.nodes[f"/{device.device_id}/oscs/0/freq"] = {"value": 100000., "type": "double"}
            device.oscillator_drift = True
        return device
    monkeypatch.setattr(backend, "_create", create)
    with context.hardware_scope(operation):
        backend.prepare(plan, compiled, lambda: None, lambda *args: None)
        restored = backend.restore()
    assert restored["safe_verified"], restored["errors"]
    hf = services["hf2li"]
    assert len(hf.reload_calls) == 2
    assert all(not ("/demods/" in path and path.endswith("/enable")) for path in hf.reload_calls[0])
    assert all("/demods/" in path and path.endswith("/enable") for path in hf.reload_calls[1])
    assert all("/oscs/" not in path for batch in hf.reload_calls for path in batch)
    assert restored["records"]["verify HF2LI restoration"]["observed_oscillator_nodes"]
    context.ownership.release(operation.ownership, safe_verified=True, preservation_verified=True, detail="Observed oscillator drift retained")


def test_mircat_ignored_restore_command_is_detected_by_independent_readback(tmp_path, monkeypatch):
    context, coordinator, operation, backend, plan, compiled, services = configured(tmp_path, monkeypatch)
    original = backend._create
    def create(name):
        device = original(name)
        if name == "mircat":
            device.pulse["current_ma"] = 3.
        return device
    monkeypatch.setattr(backend, "_create", create)
    with context.hardware_scope(operation):
        backend.prepare(plan, compiled, lambda: None, lambda *args: None)
        backend.acquire_block(compiled.blocks[0], plan, lambda: None, lambda *args: None)
        services["mircat"].set_qcl_pulse_params = lambda **kwargs: kwargs
        restored = backend.restore()
    assert not restored["safe_verified"]
    assert any("current_ma restoration" in error for error in restored["errors"])
    assert not services["mircat"].emission
    context.ownership.release(operation.ownership, safe_verified=False, preservation_verified=True, detail="MIRcat restoration failure retained")
    assert coordinator.snapshot()["state"] == "fault"


def test_safe_idle_uses_frame_commands_only_on_the_frame_capable_generator(tmp_path, monkeypatch):
    context, _, operation, backend, plan, compiled, services = configured(tmp_path, monkeypatch)
    with context.hardware_scope(operation):
        backend.prepare(plan, compiled, lambda: None, lambda *args: None)
        backend.inhibit()
        restored = backend.restore()
    assert restored["safe_verified"], restored["errors"]
    assert not any(command.startswith("TFRame:") for command in services["t660_1"].calls)
    assert "TFRame:STOp" in services["t660_2"].calls
    context.ownership.release(operation.ownership, safe_verified=True, preservation_verified=True, detail="Frame capability exclusion verified")
