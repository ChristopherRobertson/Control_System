"""Exercise genuine installed adapters using host-owned injected instrument services."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import math

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
        self.frequency_hz = 100000.
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
        return {"queries": {"predivider": response(1), "synth_frequency": response(f"{self.frequency_hz:.12g}Hz"),
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
        if "clock" in recipe:
            self.frequency_hz = acquisition._quantity(recipe["clock"]["frequency"])
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
        self.armed = False
        self.scan_status = {"scan_in_progress": False, "scan_active": False, "scan_paused": False}
        self.waiting_for_process_trigger = False
        self.sweep = {}
        self.sweep_history = []
        self.trigger_history = []
        self.tune_history = []
        self.pulse = {"pulse_rate_hz": 120000., "pulse_width_ns": 1000., "current_ma": 500.}
        self.pulse_history = []
        self.trigger = {"pulse_mode": 2, "process_trigger_mode": 1, "start": 1900., "stop": 1900.4,
                        "interval": .1, "units": 2, "dwell_us": 0, "after_off_us": 0}
        self.width_us = 1000
        self.sweep_generation = 0
        self.bad_readback = False

    def initialize(self): self.touch("initialize")
    def deinitialize(self): self.close()
    def arm(self): self.touch("arm"); self.armed = True
    def disarm(self): self.touch("disarm"); self.armed = False
    def is_laser_armed(self): self.touch("is_laser_armed"); return self.armed
    def get_scan_status(self): self.touch("get_scan_status"); return deepcopy(self.scan_status)
    def cancel_manual_tune(self): self.touch("cancel_manual_tune")
    def are_tecs_ready(self): self.touch("are_tecs_ready"); return True
    def is_tuned(self): self.touch("is_tuned"); return True
    def tune_to_wavenumber(self, *args, **kwargs): self.touch("tune_to_wavenumber"); self.tune_history.append((args,kwargs))
    def get_num_installed_qcls(self): self.touch("get_num_installed_qcls"); return 1
    def get_qcl_tuning_range(self, qcl): self.touch("get_qcl_tuning_range"); return {"qcl": qcl, "min_cm1": 1800., "max_cm1": 2000.}
    def get_qcl_pulse_limits(self, qcl): return {"max_pulse_rate_hz": 200000., "max_pulse_width_ns": 2000., "max_duty_cycle": 30.}
    def get_qcl_current_limits(self, qcl): assert qcl == 1; return (0., 1000.)
    def get_qcl_pulse_rate(self, qcl): return self.pulse["pulse_rate_hz"]
    def get_qcl_pulse_width(self, qcl): return self.pulse["pulse_width_ns"]
    def get_qcl_current(self, qcl): return self.pulse["current_ma"]
    def get_wavelength_trigger_params(self): return deepcopy(self.trigger)
    def get_wavelength_trigger_pulse_width_us(self): return self.width_us
    def is_interlock_set(self): return True
    def is_key_switch_set(self): return True
    def get_system_error_word(self): return 0
    def read_state(self): return SimpleNamespace(to_dict=lambda: {"emission_on": self.emission, "interlock": True})
    def get_scan_waiting_process_trigger(self): self.touch("get_scan_waiting_process_trigger"); return self.waiting_for_process_trigger
    def is_emission_on(self): return self.emission

    def set_qcl_pulse_params(self, *, qcl, **params):
        assert qcl == 1
        self.touch("set_qcl_pulse_params")
        self.pulse_history.append(deepcopy(params))
        self.pulse = deepcopy(params)
        return deepcopy(params)

    def set_external_sweep_trigger_params(self, **params):
        self.touch("set_external_sweep_trigger_params")
        self.trigger_history.append(deepcopy(params))
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
        self.sweep_history.append(deepcopy(params))
        self.sweep_generation += 1
        self.scan_status.update(scan_in_progress=True, scan_active=True)
        self.waiting_for_process_trigger = True

    def get_sweep_parameters(self):
        result = deepcopy(self.sweep or {"start_cm1": 1900., "stop_cm1": 1900.4, "scan_rate_cm1_s": 2., "repetitions": 2})
        if self.bad_readback:
            result["scan_rate_cm1_s"] *= 2
        return result

    def get_wavelength_trigger_channel_params(self, channel):
        interval = self.trigger["interval"]
        count = math.floor(abs(self.trigger["stop"] - self.trigger["start"]) / interval + 1e-8) + 1
        return {"start": self.trigger["start"], "interval": interval, "num_triggers": count, "units": 2}

    def turn_emission_off(self): self.touch("turn_emission_off"); self.emission = False
    def stop_scan_if_needed(self):
        self.touch("stop_scan_if_needed")
        self.scan_status.update(scan_in_progress=False, scan_active=False, scan_paused=False)
        self.waiting_for_process_trigger = False
    def start_emission(self): self.touch("start_emission"); self.emission = True


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
        self.coerce_range_to = None

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
                if key == "range_v" and self.coerce_range_to is not None:
                    self.nodes[f"/{self.device_id}/sigins/{item['index']}/{node}"]["value"] = min(item[key], self.coerce_range_to)
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
    def discover_phase_scan_capabilities(self):
        self.touch("discover_phase_scan_capabilities")
        return {"device_id": self.device_id, "verified": True, "source": "injected connected transport", "rates_sps": (100., 1000., 10000.),
                "orders": (1, 2, 3, 4), "timeconstants_by_order": {i: (.0001, .001, .002, .01) for i in range(1, 5)},
                "timing_rate_sps": 10000., "enabled_streams": (0, 2)}
    def discover_dual_phase_scan_capabilities(self):
        self.touch("discover_dual_phase_scan_capabilities")
        single = self.discover_phase_scan_capabilities()
        return {**single, "sample": deepcopy(single), "reference": deepcopy(single), "enabled_streams": (0, 2, 3)}
    def read_acquisition_health(self, **kwargs):
        self.touch("read_acquisition_health")
        return {"reference_locked": not self.bad_health, "clock_locked": True, "overload": False,
                "external_clock_selected": True, "external_reference_locked": None, "nodes": {}, "read_errors": {}}
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
        duration = abs(qcl.sweep.get("stop_cm1", 1900.4)-qcl.sweep.get("start_cm1", 1900.))/qcl.sweep.get("scan_rate_cm1_s", 2.)
        count = qcl.get_wavelength_trigger_channel_params(1)["num_triggers"]
        block_duration = qcl.sweep.get("repetitions", 2)*(duration+.1)+.2
        times = np.arange(0., block_duration, .0001)
        epoch = 0 if generation == "dark" else generation * 5_000_000
        ticks = np.uint64(2 ** 54 + epoch) + np.rint(times * 1e6).astype(np.uint64)
        dio = np.zeros(len(times), dtype=np.uint64)
        if generation != "dark":
            for rep in range(qcl.sweep["repetitions"]):
                start = .1 + rep * (duration+.1)
                active = (times >= start) & (times <= start + duration+.02)
                dio[active] |= np.uint64(1 << 21)
                if qcl.sweep["start_cm1"] < qcl.sweep["stop_cm1"]:
                    dio[active] |= np.uint64(1 << 20)
                for step in range(count):
                    edge = start + .005 + step * qcl.trigger["interval"]/qcl.sweep["scan_rate_cm1_s"]
                    dio[(times >= edge) & (times <= edge + qcl.width_us*1e-6)] |= np.uint64(1 << 22)
        sample_rate = self.nodes[f"/{self.device_id}/demods/0/rate"]["value"]
        sample_ticks = ticks[::max(1, round(10000/sample_rate))]
        reference_rate = self.nodes[f"/{self.device_id}/demods/3/rate"]["value"]
        reference_ticks = ticks[::max(1, round(10000/reference_rate))]
        sample = np.linspace(.001, .0011, len(sample_ticks)) if generation == "dark" else np.linspace(.8, .9, len(sample_ticks))
        reference = np.linspace(.0014, .0015, len(reference_ticks)) if generation == "dark" else np.ones(len(reference_ticks))
        data = {f"/{self.device_id}/demods/0/sample": {"timestamp": sample_ticks, "x": sample, "y": np.zeros(len(sample_ticks))},
                f"/{self.device_id}/demods/2/sample": {"timestamp": ticks, "dio": dio},
                f"/{self.device_id}/demods/3/sample": {"timestamp": reference_ticks, "x": reference, "y": np.zeros(len(reference_ticks))}}
        record = {"data": data}
        self.native_delivered.append(record)
        return record


def configured(tmp_path, monkeypatch, mode="dual", *, live=False, settings_override=None):
    from pathlib import Path
    configuration_path = Path(__file__).resolve().parents[4] / "instrument" / "hardware_configuration.yaml"
    config = yaml.safe_load(configuration_path.read_text(encoding="utf-8"))
    coordinator = HardwareCoordinator(tmp_path / "owned.lock")
    active, services = {}, {}
    clock = VirtualClock()
    monkeypatch.setattr(acquisition, "monotonic", clock.now)
    monkeypatch.setattr(acquisition, "Event", lambda: SimpleNamespace(wait=clock.advance))
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
    settings = SlowScanSettings(mode=mode, lower_cm1=1900., upper_cm1=1900.4,
                                requested_scan_speed_cm1_s=2., time_constant_s=.001, reference_time_constant_s=.002, reference_filter_order=3,
                                condition=ConditionIdentity(configuration_id="fixture-config"))
    if live:
        settings = SlowScanSettings(mode=mode, lower_cm1=1900., upper_cm1=1900.4, requested_scan_speed_cm1_s=2.)
        plan, compiled = build_plan(settings), None
    else:
        inputs = simulation_inputs(settings)
        profile = deepcopy(inputs.scientific_profile)
        profile["hf2li"]["reference"].update(order=3, timeconstant_s=.002, rate_sps=1000.)
        profile["hf2li"]["sigins"]["ch2"]["range_v"] = .3
        plan = build_plan(settings, replace(inputs, scientific_profile=profile))
        compiled = compile_timing(plan)
    if settings_override is not None:
        settings = settings_override
        plan, compiled = build_plan(settings), None
    operation = context.begin_operation(settings.to_dict(), hardware=True)
    active["operation"] = operation
    backend = InstalledSlowScanBackend(context, operation)
    backend._stop_wait = SimpleNamespace(wait=clock.advance)
    return context, coordinator, operation, backend, plan, compiled, services


def worker():
    return SimpleNamespace(check_cancelled=lambda: None, message=SimpleNamespace(emit=lambda *args: None),
                           progress=SimpleNamespace(emit=lambda *args: None))


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_default_runner_resolves_live_factories_acquires_automatic_dark_and_sample(tmp_path, monkeypatch, mode):
    from control_app.measurement_host.presentation import StartSnapshot
    from control_app.measurement_modules.steady_state_slow_scan.runner import SlowScanRunner
    from control_app.measurement_modules.steady_state_slow_scan.persistence import load_run
    context, coordinator, operation, _, draft, _, services = configured(tmp_path, monkeypatch, mode, live=True)
    assert not services and not draft.errors and draft.readiness
    result = SlowScanRunner(context).run(StartSnapshot(operation, "measurement", draft, {}), worker())
    assert result["status"] == "completed"
    assert result["simulation"] is False and not result["plan"]["inputs"]["simulation"]
    assert not result["plan"]["inputs"]["promoted_bundle_ids"]
    assert result["plan"]["selected"]["measured_response_s"] is None
    assert result["plan"]["selected"]["intrinsic_resolution_cm1"] is None
    assert result["automatic_dark"]["dark"]["sample"] < .01
    assert len(result["sweeps"]) == 2 and len(result["spectra"]) == 2
    assert all(np.count_nonzero(item.valid) > 20 for item in result["spectra"])
    assert all(item.metadata["effective_resolution_cm1"] is None for item in result["sweeps"])
    assert result["readbacks"]["direction_bit_observation"]["association"] == {"reverse": 0}
    assert result["restoration"]["safe_verified"]
    assert all(device.closed for device in services.values())
    assert all(not enabled for name in ("t660_1", "t660_2") for enabled in services[name].channels.values())
    assert not services["mircat"].emission
    assert "start_emission" in services["mircat"].calls
    assert services["hf2li"].calls.count("connect") == 1
    loaded = load_run(result["path"], expected_mode=mode)
    assert len(loaded["sweeps"]) == 2 and loaded["restoration"]["safe_verified"]
    assert loaded["partial_native_records"]
    assert coordinator.snapshot()["state"] == "free"


@pytest.mark.parametrize("outcome", ["success", "timeout", "cancelled"])
def test_reference_lock_wait_is_bounded_cancellable_and_retains_observations(tmp_path, monkeypatch, outcome):
    context, _, operation, backend, plan, compiled, services = configured(tmp_path, monkeypatch)
    checks = []
    with context.hardware_scope(operation):
        backend.prepare(plan, compiled, lambda: None, lambda *args: None)
        original = services["hf2li"].read_acquisition_health
        def health(**kwargs):
            observed = original(**kwargs)
            checks.append(observed)
            observed["reference_locked"] = outcome == "success" and len(checks) >= 4
            return observed
        services["hf2li"].read_acquisition_health = health
        def check():
            if outcome == "cancelled" and len(checks) >= 3:
                raise InterruptedError("operator Stop while waiting for reference")
        if outcome == "success":
            assert backend.acquire_dark(plan, check, lambda *args: None)
        else:
            with pytest.raises(TimeoutError if outcome == "timeout" else InterruptedError, match="reference"):
                backend.acquire_dark(plan, check, lambda *args: None)
        restored = backend.restore()
    assert len(checks) >= 3
    assert any(row["reference_locked"] is False for row in backend.readbacks["health_observations"])
    assert restored["safe_verified"]
    assert not services["mircat"].emission and "start_emission" not in services["mircat"].calls
    context.ownership.release(operation.ownership, safe_verified=True, preservation_verified=True, detail="Reference wait retained")


def test_runtime_auto_probe_width_uses_absolute_edges_in_rise_fall_mode(tmp_path, monkeypatch):
    context, _, operation, backend, draft, _, services = configured(tmp_path, monkeypatch, live=True)
    original = backend._create
    def create(name):
        device = original(name)
        if name == "t660_1":
            device.absolute.update({3: 3e-6, 4: 4e-6})
            device.references.update({3: 0, 4: 0})
            device.modes["B"] = "RF"
        return device
    monkeypatch.setattr(backend, "_create", create)
    with context.hardware_scope(operation):
        plan = backend.resolve_plan(draft.settings, lambda: None)
        assert plan.selected["probe_width_s"] == pytest.approx(1e-6)
        assert plan.actual["t660_1"]["channels"]["B"]["width_edge"]["response"] == "4e-06s"
        restored = backend.restore()
    assert restored["safe_verified"], restored["errors"]
    context.ownership.release(operation.ownership, safe_verified=True, preservation_verified=True, detail="Absolute pulse width observed")


@pytest.mark.parametrize("mode", ["single", "dual"])
@pytest.mark.parametrize("outcome", ["fault", "cancelled"])
def test_default_installed_runner_preserves_failure_and_stop_partials(tmp_path, monkeypatch, mode, outcome):
    from control_app.measurement_host.presentation import StartSnapshot
    from control_app.measurement_modules.steady_state_slow_scan.runner import SlowScanRunner
    from control_app.measurement_modules.steady_state_slow_scan.persistence import load_run
    context, coordinator, operation, _, draft, _, services = configured(tmp_path, monkeypatch, mode, live=True)
    if outcome == "fault":
        monkeypatch.setattr(TimingService, "get_shot_count", lambda self: len(self.frames) + 1)
    active_worker = worker()
    def check():
        hf = services.get("hf2li")
        if outcome == "cancelled" and hf and any(isinstance(item, int) for item in hf.delivered):
            raise InterruptedError("operator Stop after a native poll")
    active_worker.check_cancelled = check
    runner = SlowScanRunner(context)
    with pytest.raises(RuntimeError if outcome == "fault" else InterruptedError, match="shot count|Stop"):
        runner.run(StartSnapshot(operation, "measurement", draft, {}), active_worker)
    result = runner.last_result
    assert result["status"] == ("failed" if outcome == "fault" else "cancelled")
    assert result["partial_native_records"] and result["automatic_dark"]
    assert result["restoration"]["safe_verified"]
    assert all(device.closed for device in services.values())
    assert all(not enabled for name in ("t660_1", "t660_2") for enabled in services[name].channels.values())
    assert not services["mircat"].emission
    loaded = load_run(result["path"], expected_mode=mode)
    assert loaded["status"] == result["status"] and loaded["partial_native_records"]
    assert coordinator.snapshot()["state"] == "free"


def test_live_direction_mapping_can_be_inverted_and_is_learned_from_observed_sweeps(tmp_path, monkeypatch):
    from control_app.measurement_host.presentation import StartSnapshot
    from control_app.measurement_modules.steady_state_slow_scan.runner import SlowScanRunner
    original = HFService.read_acquisition
    def read(self, duration):
        record = original(self, duration)
        timing = record.get("data", {}).get(f"/{self.device_id}/demods/2/sample")
        if timing is not None and self.services["mircat"].emission:
            active = (timing["dio"] & np.uint64(1 << 21)) != 0
            timing["dio"][active] ^= np.uint64(1 << 20)
        return record
    monkeypatch.setattr(HFService, "read_acquisition", read)
    context, _, operation, _, draft, _, _ = configured(tmp_path, monkeypatch, live=True)
    result = SlowScanRunner(context).run(StartSnapshot(operation, "measurement", draft, {}), worker())
    assert result["status"] == "completed"
    assert result["readbacks"]["direction_bit_observation"]["association"] == {"reverse": 1}
    assert all(np.any(item.valid) for item in result["spectra"])


def test_default_installed_single_blank_then_sample_reuses_controls_on_distinct_native_coordinates(tmp_path, monkeypatch):
    from control_app.measurement_host.presentation import StartSnapshot
    from control_app.measurement_modules.steady_state_slow_scan.runner import SlowScanRunner
    from control_app.measurement_modules.steady_state_slow_scan.persistence import load_run
    blank_context, _, blank_operation, _, blank_draft, _, _ = configured(tmp_path / "blank", monkeypatch, "single", live=True)
    blank = SlowScanRunner(blank_context).run(StartSnapshot(blank_operation, "blank", blank_draft, {}), worker())
    assert blank["status"] == "completed" and blank["automatic_dark"]
    # Independent connected polls do not land on identical native coordinates.
    # Offset the sample timestamps within the explicit bounded support policy.
    original = HFService.read_acquisition
    def read(self, duration):
        record = original(self, duration)
        sample = record.get("data", {}).get(f"/{self.device_id}/demods/0/sample")
        if sample is not None:
            sample["timestamp"] = sample["timestamp"] + np.uint64(100)
        return record
    monkeypatch.setattr(HFService, "read_acquisition", read)
    context, coordinator, operation, _, draft, _, services = configured(tmp_path / "sample", monkeypatch, "single", live=True)
    controls = {"blank": blank, "dark": blank["automatic_dark"]}
    result = SlowScanRunner(context).run(StartSnapshot(operation, "measurement", draft, controls), worker())
    assert result["status"] == "completed" and result["simulation"] is False
    assert "automatic_dark" not in result and "dark" not in services["hf2li"].delivered
    assert not result.get("unused_controls")
    assert result["controls"]["blank"]["run_id"] == blank["run_id"]
    assert result["controls"]["dark"]["run_id"] == blank["automatic_dark"]["run_id"]
    for sample, control in zip(result["spectra"], blank["spectra"]):
        assert sample.quantity == "sequential_blank_absorbance"
        assert not np.array_equal(sample.native.axis_cm1, control.native.axis_cm1)
        assert np.count_nonzero(sample.valid) > 20
        assert np.all(np.isfinite(sample.signal[sample.valid]))
        assert sample.provenance["control_ids"]["blank"].startswith(blank["run_id"])
    loaded = load_run(result["path"], expected_mode="single")
    assert loaded["controls"] == result["controls"] and loaded["restoration"]["safe_verified"]
    assert all(device.closed for device in services.values()) and not services["mircat"].emission
    assert coordinator.snapshot()["state"] == "free"


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_owned_installed_adapter_dark_and_descending_repetitions_retain_native(tmp_path, monkeypatch, mode):
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
    assert len(trajectories) == 2
    assert {sweep["direction_bit"] for sweep in trajectories} == {0}
    assert trajectories[1]["timestamps_s"][0] > trajectories[0]["timestamps_s"][-1]
    assert len({sweep["time_origin_ticks"] for sweep in trajectories}) == 1
    assert all(np.count_nonzero(sweep["valid"]) > 100 for sweep in trajectories)
    assert all(not sweep["flags"] for sweep in trajectories)
    assert any("Acknowledged" in message[1] for message in updates)
    preset = services["hf2li"].presets[0]
    demods = {item["index"]: item for item in preset["demodulators"]}
    assert demods[0]["order"] == 2
    if mode == "dual":
        assert demods[3]["order"] == 3 and demods[3]["timeconstant_s"] == .002
        assert preset["signal_inputs"]["ch2"]["range_v"] == .002
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
            with pytest.raises((ValueError, RuntimeError, TimeoutError), match="MIRcat|shot count|clipping|lock timeout"):
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
    assert "start_emission" not in services["mircat"].calls
    assert restored["safe_verified"]
    context.ownership.release(operation.ownership, safe_verified=True, preservation_verified=True, detail="Clock failure retained")


def test_installed_wrong_direction_is_retained_but_invalid(tmp_path, monkeypatch):
    context, _, operation, backend, plan, compiled, services = configured(tmp_path, monkeypatch)
    plan.inputs.scientific_profile["direction_bit_by_direction"]["reverse"] = 1
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


@pytest.mark.parametrize("mode", ["single", "dual"])
@pytest.mark.parametrize("current,requested", [(500.,1.),(750.,1.75),(1000.,2.)])
def test_current_drives_requested_range_and_real_coercion_is_used_and_restored(tmp_path, monkeypatch, mode, current, requested):
    from control_app.measurement_host.presentation import StartSnapshot
    from control_app.measurement_modules.steady_state_slow_scan.runner import SlowScanRunner
    settings = SlowScanSettings(mode=mode,lower_cm1=1900.,upper_cm1=1900.4,current_ma=current,pulse_width_s=1.5e-6)
    context, coordinator, operation, _, draft, _, services = configured(tmp_path,monkeypatch,mode,live=True,settings_override=settings)
    original = HFService.__init__
    def initialize(self,*args):
        original(self,*args)
        self.coerce_range_to = 1.5
    monkeypatch.setattr(HFService,"__init__",initialize)
    monkeypatch.setattr(QCLService,"read_state",lambda self: (_ for _ in ()).throw(AssertionError("Broad active-QCL state forbidden")))
    result = SlowScanRunner(context).run(StartSnapshot(operation,"measurement",draft,{}),worker())
    assert result["status"] == "completed" and not result["fits"]
    record = result["readbacks"]["detector_input_ranges"]
    assert record["actual_current_ma"] == current and record["requested_range_v"] == requested
    actual_range = min(requested,1.5)
    selected = result["plan"]["selected"]
    for role,label in (("sample","ch1"),("reference","ch2")):
        if role == "reference" and mode == "single": continue
        assert services["hf2li"].presets[0]["signal_inputs"][label]["range_v"] == requested
        assert selected[f"{role}_range_v"] == actual_range
        assert selected["hf2li"]["sigins"][label]["range_v"] == actual_range
        assert result["compatibility"]["selected"]["hf2li"]["sigins"][label]["range_v"] == actual_range
    assert any(row["current_ma"] == current and row["pulse_width_ns"] == pytest.approx(1500.) for row in services["mircat"].pulse_history)
    assert selected["pulse_width_s"] == pytest.approx(1.5e-6) and selected["probe_width_s"] == 1e-6
    assert services["mircat"].pulse["current_ma"] == 500.
    assert services["mircat"].pulse["pulse_width_ns"] == 1000.
    assert result["restoration"]["safe_verified"] and coordinator.snapshot()["state"] == "free"


@pytest.mark.parametrize("fault", ["external_duty","internal_duty","observed_duty","vendor_duty"])
def test_optical_duty_is_rechecked_before_emission_for_internal_and_external_rates(tmp_path,monkeypatch,fault):
    context, _, operation, backend, plan, compiled, services = configured(tmp_path,monkeypatch)
    pulse = plan.inputs.scientific_profile["qcl_pulse_params"]["1"]
    if fault == "external_duty": pulse["pulse_width_ns"] = 4000.
    if fault == "internal_duty": pulse.update(pulse_rate_hz=190000.,pulse_width_ns=2000.)
    if fault == "observed_duty":
        pulse.update(pulse_rate_hz=150000.,pulse_width_ns=2000.)
        original = QCLService.get_qcl_pulse_width
        monkeypatch.setattr(QCLService,"get_qcl_pulse_width",lambda self,qcl:original(self,qcl)*(1+1e-7))
    if fault == "vendor_duty":
        original = QCLService.get_qcl_pulse_limits
        monkeypatch.setattr(QCLService,"get_qcl_pulse_limits",lambda self,qcl:{**original(self,qcl),"max_duty_cycle":10.})
    with context.hardware_scope(operation):
        with pytest.raises(ValueError,match="duty|controller limits"):
            backend.prepare(plan,compiled,lambda:None,lambda *args:None)
        restored = backend.restore()
    assert "start_emission" not in services["mircat"].calls and not services["mircat"].emission
    assert restored["safe_verified"], restored["errors"]
    context.ownership.release(operation.ownership,safe_verified=True,preservation_verified=True,detail="Optical duty rejection retained")


def test_prepared_plan_retains_accepted_sdk_float_readbacks_for_compatibility(tmp_path,monkeypatch):
    context, _, operation, backend, draft, _, services = configured(tmp_path,monkeypatch,live=True)
    original = QCLService.get_qcl_pulse_width
    monkeypatch.setattr(QCLService,"get_qcl_pulse_width",lambda self,qcl:original(self,qcl)*(1+1e-7))
    with context.hardware_scope(operation):
        plan = backend.resolve_plan(draft.settings,lambda:None)
        compiled = compile_timing(plan)
        actual = backend.prepare(plan,compiled,lambda:None,lambda *args:None)
        observed = services["mircat"].get_qcl_pulse_width(1)
        assert actual.selected["pulse_width_s"] == observed*1e-9
        assert actual.inputs.scientific_profile["qcl_pulse_params"]["1"]["pulse_width_ns"] == observed
        assert actual.requested == plan.requested
        restored = backend.restore()
    assert restored["safe_verified"]
    context.ownership.release(operation.ownership,safe_verified=True,preservation_verified=True,detail="Actual SDK pulse readback retained")


@pytest.mark.parametrize("fault", ["dds_after_recipe", "dds_after_start", "width_after_trigger", "current_after_sweep",
                                   "limits_after_sweep", "current_after_tune", "internal_after_trigger", "current_limits_after_trigger"])
def test_fresh_readonly_pulse_checks_catch_changes_after_configuration_before_emission(tmp_path,monkeypatch,fault):
    context, _, operation, backend, plan, compiled, services = configured(tmp_path,monkeypatch)
    create = backend._create
    def factory(name):
        device = create(name)
        if name == "t660_1" and fault.startswith("dds"):
            method = "apply_recipe" if fault == "dds_after_recipe" else "start_continuous_clock"
            original = getattr(device,method)
            def changed(*args,**kwargs):
                value = original(*args,**kwargs)
                device.frequency_hz = 110000.
                return value
            setattr(device,method,changed)
        if name == "mircat" and not fault.startswith("dds"):
            method = "tune_to_wavenumber" if fault == "current_after_tune" else "start_sweep_scan" if fault.endswith("sweep") else "set_external_sweep_trigger_params"
            original = getattr(device,method)
            def changed(*args,**kwargs):
                value = original(*args,**kwargs)
                if fault.startswith("width"): device.pulse["pulse_width_ns"] = 1500.
                elif fault.startswith("internal"): device.pulse["pulse_rate_hz"] = 130000.
                elif fault == "limits_after_sweep":
                    getter = device.get_qcl_pulse_limits
                    device.get_qcl_pulse_limits = lambda qcl:{**getter(qcl),"max_duty_cycle":25.}
                elif fault == "current_limits_after_trigger": device.get_qcl_current_limits = lambda qcl:(0.,999.)
                else: device.pulse["current_ma"] = 300.
                return value
            setattr(device,method,changed)
        return device
    monkeypatch.setattr(backend,"_create",factory)
    with context.hardware_scope(operation):
        if fault == "dds_after_recipe":
            with pytest.raises(ValueError,match="DDS"):
                backend.prepare(plan,compiled,lambda:None,lambda *args:None)
        else:
            actual_plan = backend.prepare(plan,compiled,lambda:None,lambda *args:None)
            programmed_count = len(services["mircat"].pulse_history)
            with pytest.raises(ValueError,match="DDS|readback differs|limits changed"):
                backend.acquire_block(compiled.blocks[0],actual_plan,lambda:None,lambda *args:None)
            # No setter during the final checks may hide a changed actual value.
            assert len(services["mircat"].pulse_history) == programmed_count
        rejected = [row for row in backend.readbacks["pulse_observations"] if not row["valid"]]
        assert rejected
        observed = rejected[-1]
        assert observed["pulse"] and observed["pulse_limits"] and observed["current_limits"]
        if fault.startswith("dds"):
            assert observed["external_rate_hz"] == 110000.
            assert observed["external_duty_fraction"] == pytest.approx(.11)
        elif fault == "current_after_tune": assert observed["stage"] == "after_tune"
        else: assert observed["stage"] == "before_emission"
        assert "start_emission" not in services["mircat"].calls
        restored = backend.restore()
    assert restored["safe_verified"],restored["errors"]
    assert not services["mircat"].emission
    context.ownership.release(operation.ownership,safe_verified=True,preservation_verified=True,detail="Fresh pulse readback failure retained")


@pytest.mark.parametrize("fault", ["ignored_disarm", "ignored_stop", "unknown_armed", "scan_read_error", "missing_scan_flags", "unknown_waiting"])
def test_final_mircat_idle_verification_retains_fault_and_attempts_all_cleanup(tmp_path,monkeypatch,fault):
    from control_app.measurement_host.presentation import StartSnapshot
    from control_app.measurement_modules.steady_state_slow_scan.runner import SlowScanRunner
    from control_app.measurement_modules.steady_state_slow_scan.persistence import load_run
    context, coordinator, operation, _, draft, _, services = configured(tmp_path,monkeypatch,live=True)
    if fault == "ignored_disarm":
        monkeypatch.setattr(QCLService,"disarm",lambda self:self.touch("disarm"))
    elif fault == "ignored_stop":
        monkeypatch.setattr(QCLService,"stop_scan_if_needed",lambda self:self.touch("stop_scan_if_needed"))
    elif fault == "unknown_armed":
        def read(self): self.touch("is_laser_armed"); return None
        monkeypatch.setattr(QCLService,"is_laser_armed",read)
    elif fault in ("scan_read_error","missing_scan_flags"):
        def read(self):
            self.touch("get_scan_status")
            if fault == "scan_read_error": raise OSError("injected final scan status uncertainty")
            return {"scan_active":False}
        monkeypatch.setattr(QCLService,"get_scan_status",read)
    elif fault == "unknown_waiting":
        original = QCLService.get_scan_waiting_process_trigger
        def read(self):
            value = original(self)
            return None if "disarm" in self.calls else value
        monkeypatch.setattr(QCLService,"get_scan_waiting_process_trigger",read)
    runner = SlowScanRunner(context)
    with pytest.raises(RuntimeError,match="safe idle is unverified"):
        runner.run(StartSnapshot(operation,"measurement",draft,{}),worker())
    result = runner.last_result
    assert result["status"] == "failed" and not result["restoration"]["safe_verified"]
    record = result["restoration"]["records"]["MIRcat final idle readbacks"]
    assert set(record) == {"emission_on","armed","scan_status","waiting_for_process_trigger","read_errors"}
    assert record["emission_on"] is False
    if fault == "ignored_disarm": assert record["armed"] is True
    if fault == "ignored_stop":
        assert record["scan_status"]["scan_active"] is True and record["waiting_for_process_trigger"] is True
    if fault == "scan_read_error": assert "injected" in record["read_errors"]["scan_status"]
    assert result["partial_native_records"]
    assert all(device.closed for device in services.values())
    calls = services["mircat"].calls
    assert calls.index("is_laser_armed") < calls.index("close")
    assert calls.index("get_scan_status") < calls.index("close")
    assert calls[-2] == "get_scan_waiting_process_trigger" and calls[-1] == "close"
    assert all(not value for name in ("t660_1","t660_2") for value in services[name].channels.values())
    assert coordinator.snapshot()["state"] == "fault"
    loaded = load_run(result["path"],expected_mode="dual")
    assert loaded["restoration"]["records"]["MIRcat final idle readbacks"] == record


@pytest.mark.parametrize("mode,sample_request,reference_request", [("single",10000.,None),("dual",10000.,1000.),("dual",None,10000.)])
def test_installed_sampling_overrides_configure_independent_native_rates_and_persist(tmp_path,monkeypatch,mode,sample_request,reference_request):
    from control_app.measurement_host.presentation import StartSnapshot
    from control_app.measurement_modules.steady_state_slow_scan.runner import SlowScanRunner
    from control_app.measurement_modules.steady_state_slow_scan.persistence import load_run
    settings = SlowScanSettings(mode=mode,lower_cm1=1900.,upper_cm1=1900.4,
        requested_scan_speed_cm1_s=2.,requested_sample_rate_hz=sample_request,requested_reference_sample_rate_hz=reference_request)
    context, coordinator, operation, _, draft, _, services = configured(tmp_path,monkeypatch,mode,live=True,settings_override=settings)
    result = SlowScanRunner(context).run(StartSnapshot(operation,"measurement",draft,{}),worker())
    assert result["status"] == "completed" and result["restoration"]["safe_verified"]
    expected = {"sample":sample_request or 1000.}
    if mode == "dual": expected["reference"] = reference_request or 1000.
    demods = {item["index"]:item for item in services["hf2li"].presets[0]["demodulators"]}
    first_record = services["hf2li"].native_delivered[0]["data"]
    for role,rate in expected.items():
        index = 0 if role == "sample" else 3
        assert demods[index]["rate_sps"] == rate
        assert result["plan"]["selected"]["hf2li"][role]["rate_sps"] == rate
        ticks = first_record[f"/devTEST/demods/{index}/sample"]["timestamp"]
        assert np.all(np.diff(ticks) == round(1e6/rate))
    assert all(np.count_nonzero(spectrum.valid) > 20 for spectrum in result["spectra"])
    loaded = load_run(result["path"],expected_mode=mode)
    for field,requested in (("requested_sample_rate_hz",sample_request),("requested_reference_sample_rate_hz",reference_request)):
        assert result["settings"][field] == loaded["settings"][field] == requested
        assert result["plan"]["requested"][field] == requested
    assert loaded["plan"]["selected"]["hf2li"] == result["plan"]["selected"]["hf2li"]
    assert coordinator.snapshot()["state"] == "free"


@pytest.mark.parametrize("mode", ["single","dual"])
def test_installed_default_descending_scan_uses_total_repetitions_without_ascending_commands(tmp_path,monkeypatch,mode):
    from control_app.measurement_host.presentation import StartSnapshot
    from control_app.measurement_modules.steady_state_slow_scan.runner import SlowScanRunner
    from control_app.measurement_modules.steady_state_slow_scan.persistence import load_run
    settings = SlowScanSettings(mode=mode,replicates=3)
    def coverage(self,qcl):
        self.touch("get_qcl_tuning_range")
        assert qcl == 1
        return {"qcl":1,"min_cm1":1600.,"max_cm1":2100.}
    monkeypatch.setattr(QCLService,"get_qcl_tuning_range",coverage)
    context, coordinator, operation, _, draft, _, services = configured(tmp_path,monkeypatch,mode,live=True,settings_override=settings)
    result = SlowScanRunner(context).run(StartSnapshot(operation,"measurement",draft,{}),worker())
    assert result["status"] == "completed" and result["restoration"]["safe_verified"]
    assert services["mircat"].sweep_history == [{"start_cm1":2050.,"stop_cm1":1650.,"scan_rate_cm1_s":40.,"qcl":1,"repetitions":3}]
    assert len(services["mircat"].trigger_history) == 1
    assert all(row["start_cm1"] == 2050. and row["stop_cm1"] == 1650. for row in services["mircat"].trigger_history)
    assert services["mircat"].tune_history == [((2050.,),{"qcl":1})]
    assert len(result["sweeps"]) == len(result["spectra"]) == 3
    for sweep in result["sweeps"]:
        assert sweep.direction == "reverse"
        axis = sweep.axis_cm1[np.asarray(sweep.valid,bool)]
        assert len(axis) > 100 and np.all(np.diff(axis) < 0)
        assert 1650. <= axis[-1] < axis[0] <= 2050.
    assert result["compiled_timing"]["event_counts"]["process"] == 3
    assert result["compiled_timing"]["event_counts"]["physical_frames"] == 4
    assert len(services["t660_2"].frames) == 4 and services["t660_2"].frames[-1]["inert_terminator"]
    assert all(not frame["channels"][name]["enabled"] for frame in services["t660_2"].frames for name in "ABD")
    assert result["plan"]["estimates"]["sample_sweep_count"] == 3
    loaded = load_run(result["path"],expected_mode=mode)
    assert len(loaded["sweeps"]) == 3 and all(sweep.direction == "reverse" for sweep in loaded["sweeps"])
    assert coordinator.snapshot()["state"] == "free"
