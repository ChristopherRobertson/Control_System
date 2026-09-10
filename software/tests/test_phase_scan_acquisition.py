"""Hardware-free finite phase acquisition and shared timing transport fake."""
from copy import deepcopy
import numpy as np
import pytest
from threading import Event
from types import SimpleNamespace
from control_app.workflows.phase_scan import PhaseScanEvent, PhaseScanSettings, build_phase_scan_plan
from control_app.workflows.phase_scan_acquisition import LivePhaseScanAcquirer, event_timing
from control_app.workflows.phase_scan_data import DETECTOR_INPUT, SINGLE_DETECTOR_MODE
from control_app.workflows.single_detector_marker_identity import controller_marker_identity
from control_app.workflows.phase_scan_labone import (
    FinitePhaseDAQ, AcquisitionCapacityError, AcquisitionIntegrityError,
    ResidentCapacityReservation, estimate_capture_bytes,
)

class Timer:
    def __init__(self, world, name):
        self.world, self.name = world, name
        self.device_config = {"serial_number": name}
        self.source, self.shots = "OFF", 0
        self.channels = {ch: {"enabled": False} for ch in "ABCD"}
        self.recipe = {}
        world.units[name] = self

    def connect(self): pass
    def close(self): pass
    def identify(self): return f"Highland,T660,{self.name},fake"
    def set_trigger_source(self, source): self.source = source
    def disable_channel(self, ch):
        if self.world.fail_stop and ch == "A":
            raise RuntimeError("injected stop failure")
        self.channels[ch]["enabled"] = False
    def enable_channel(self, ch): self.channels[ch]["enabled"] = True
    def command(self, command, **kwargs):
        return self.command_sequence([command])[0]
    def command_sequence(self, commands):
        edges = {1: ("A", "delay"), 2: ("A", "width"), 3: ("B", "delay"), 4: ("B", "width"),
                 5: ("C", "delay"), 6: ("C", "width"), 7: ("D", "delay"), 8: ("D", "width")}
        responses = []
        for command in commands:
            words = command.split()
            upper = command.upper()
            if upper == "TRIG:SOUR?":
                responses.append(self.source)
            elif upper.startswith("TRIG:SOUR "):
                self.source = words[-1]
                responses.append("OK")
            elif upper.startswith("CHAN:ON? "):
                responses.append("ON" if self.channels[words[-1]]["enabled"] else "OFF")
            elif upper.startswith("CHAN:ON "):
                self.channels[words[-1]]["enabled"] = True
                responses.append("OK")
            elif upper.startswith("CHAN:OFF "):
                self.channels[words[-1]]["enabled"] = False
                responses.append("OK")
            elif upper.startswith("CHAN:TIMINGMODE? "):
                responses.append("DW")
            elif upper.startswith("CHANNEL:ACTIVE:POLARITY? "):
                responses.append(str(self.channels[words[-1]].get("polarity", "negative")))
            elif upper.startswith("CHAN:50OHM? "):
                responses.append("50OHM")
            elif upper.startswith("TIME:DEL") and upper.endswith("?"):
                edge = int(upper.removeprefix("TIME:DEL").removesuffix("?"))
                channel, key = edges[edge]
                responses.append(str(self.channels[channel].get(key, "0s")).rstrip("s"))
            elif upper.startswith("TIME:DEL"):
                edge = int(words[0].upper().removeprefix("TIME:DEL"))
                channel, key = edges[edge]
                self.channels[channel][key] = words[-1]
                responses.append("OK")
            elif upper.startswith("CHAN:POS "):
                self.channels[words[-1]]["polarity"] = "positive"
                responses.append("OK")
            elif upper.startswith("CHAN:NEG "):
                self.channels[words[-1]]["polarity"] = "negative"
                responses.append("OK")
            else:
                responses.append("OK")
        return responses
    def get_shot_count(self): return self.shots
    def apply_recipe(self, recipe):
        self.recipe = deepcopy(recipe)
        self.source = recipe.get("trigger_source", self.source)
        for ch, values in recipe.get("channels", {}).items():
            self.channels[ch].update(values)

    def read_active_settings(self):
        def query(value): return {"ok": True, "response": str(value)}
        return {"queries": {"trigger_source": query(self.source), "gate_mode": query(0),
                "burst": query("OFF"), "frames_engine": query("OFF"),
                "train_count": query(0), "predivider": query(self.recipe.get("predivider", 1)),
                "synth_frequency": query(self.recipe.get("clock", {}).get("frequency", "2000000Hz"))},
            "channels": {ch: {"enabled": query("ON" if val["enabled"] else "OFF"),
                "delay_edge": query(val.get("delay", "0ns")), "width_edge": query(val.get("width", "10us")),
                "polarity": query(val.get("polarity", "negative")), "termination": query("50OHM"),
                "timing_mode": query("DW")} for ch, val in self.channels.items()}}

    def fire_remote_trigger(self):
        raise AssertionError("AirTimer must supply its experiment-specific trigger")


class FakeModule:
    def __init__(self, hf):
        self.hf, self.settings, self.paths = hf, {}, []
        self.executed = self.cleared = False
        self.read_count = 0
        self.events = None

    def set(self, node, value): self.settings[node] = value
    def subscribe(self, path): self.paths.append(path)
    def getString(self, node): return self.settings[node]
    def getInt(self, node):
        if node == "buffercount": return 4
        if node == "historylength" and self.hf.shrink_history: return 1
        return self.settings[node]
    def getDouble(self, node):
        if node == "buffersize": return .1
        if node == "duration": return self.settings["grid/cols"] / self.rate
        return self.settings[node]
    @property
    def rate(self):
        return max(self.hf.rates[int(path.split("/demods/")[1].split("/")[0])] for path in self.paths)
    def execute(self):
        assert not self.cleared
        self.executed = True
        self.events = tuple(self.hf.events)
        self.hf.calls.append("daq_arm")
    def finished(self): return False  # The extra integrity guard remains armed.
    def progress(self):
        return [len(self.selected_events) / self.settings["count"]]
    @property
    def selected_events(self):
        events = self.events if self.events is not None else self.hf.events
        return [e for e in events if e.pump_enabled] if self.settings["bits"] == 1 << 17 else events
    def read(self, flat):
        assert flat and self.executed and not self.cleared
        self.read_count += 1
        self.hf.calls.append("daq_read")
        if self.hf.read_failure and self.paths[0].endswith(".x"):
            raise RuntimeError("sample loss detected by installed DAQ")
        if self.hf.payloads is not None:
            return self.hf.payloads[id(self)]
        if self.read_count > 1:
            return {}  # Running read() consumes complete native records.
        result = {path: [] for path in self.paths}
        for event in self.selected_events:
            recipe, _ = event_timing(event)
            channels = recipe["channels"]
            frame = .1 + event.scan_index*.3
            pump = frame + float(channels["A"]["delay"][:-1]) + .000180
            sweep = frame + float(channels["C"]["delay"][:-1])
            trigger = pump if self.settings["bits"] == 1 << 17 else sweep
            relative = self.settings["delay"] + np.arange(self.settings["grid/cols"])/self.rate
            ticks = np.array([self.hf.origin+round((trigger+t)*self.hf.get_clockbase()) for t in relative], dtype=np.uint64)
            for path in self.paths:
                if path.endswith(".dio"):
                    bits = np.zeros(len(ticks), np.uint32)
                    if self.settings["bits"] == 1 << 17:
                        bits[relative >= -1e-12] |= 1 << 17
                    else:
                        bits[(relative >= -1e-12) & (relative < .00232)] |= 1 << 21
                        bits[(relative >= .001) & (relative < .00232)] |= 1 << 20
                        for marker in (0, .001, .002):
                            bits[(relative >= marker-1e-12) & (relative < marker+.00008)] |= 1 << 22
                    values = bits
                else:
                    values = np.full(len(ticks), 1. if path.endswith(".x") else 0.)
                result[path].append({"timestamp": ticks[None, :], "value": values[None, :], "header": {}})
        return result
    def finish(self): self.hf.calls.append("daq_finish")
    def clear(self): self.cleared = True


class FakeHF:
    device_id = "dev1234"
    origin = 2**60
    def __init__(self, events):
        self.events = list(events)
        self.rates = {0: 20_000., 2: 50_000.}
        self.modules, self.calls = [], []
        self.shrink_history = self.read_failure = False
        self.payloads = None
        self.clipping = {0: 0, 1: 1}  # CH2 status must never block CH1 acquisition.
        self.snapshot_overrides = {}
    def get_clockbase(self): return 100_000_000
    def _get_node(self, kind, path):
        if "adcclip" in path:
            self.calls.append(path)
            return self.clipping[int(path.rsplit("/", 1)[1])]
        return self.rates[int(path.split("/demods/")[1].split("/")[0])]
    def create_daq_module(self):
        module = FakeModule(self)
        self.modules.append(module)
        return module
    def close(self): pass
    def connect(self): pass
    def get_oscillator_frequency(self, index): return 2_000_000.
    def load_preset(self, name):
        from control_app.devices.hf2li_service import HF2LIService
        return HF2LIService.load_preset(self, name)
    def apply_preset(self, preset):
        if hasattr(self, 'verify_reference_only'):
            self.verify_reference_only()
        self.preset = preset
        for demod in preset.settings["demodulators"]:
            if "rate_sps" in demod: self.rates[demod["index"]] = demod["rate_sps"]
    def export_settings_snapshot(self, **kwargs):
        nodes = {}
        rename = {"rate_sps": "rate", "timeconstant_s": "timeconstant", "freqcenter_hz": "freqcenter",
                  "impedance_50ohm": "imp50", "differential": "diff", "range_v": "range"}
        for group, configurations in (("sigins", self.preset.settings["signal_inputs"].values()),
                                      ("demods", self.preset.settings["demodulators"]),
                                      ("plls", [self.preset.settings["pll"]])):
            for config in configurations:
                for key, value in config.items():
                    if key != "index":
                        path = f"/{self.device_id}/{group}/{config['index']}/{rename.get(key, key)}"
                        actual = self.snapshot_overrides.get(path, int(value) if isinstance(value, bool) else value)
                        nodes[path] = {"type": "double" if isinstance(value, float) else "int", "value": actual}
        return {"device_id": self.device_id, "read_errors": {}, "nodes": nodes}


def fake_reservation(hf, modules, readbacks, required):
    # Explicit test collaborator, not a invented method on a real SDK/server.
    assert len(modules) == len(readbacks) == 3
    assert all(not m.executed for m in modules)
    return ResidentCapacityReservation(required + 1024, "fake-reservation-1", "test-only resident allocator")


def nominal_events():
    return [PhaseScanEvent(0, 1, None, False, None),
            PhaseScanEvent(1, 1, 0, True, -3200.),
            PhaseScanEvent(2, 1, 1, True, 5000.)]


def daq_fixture(events=None):
    hf = FakeHF(events or nominal_events())
    daq = FinitePhaseDAQ(hf, events=hf.events, duration_s=.0026, pretrigger_s=.0001,
                        capacity_verifier=fake_reservation)
    return hf, daq


def test_finite_sweep_active_trigger_history_retention_and_minimal_subscriptions():
    hf, daq = daq_fixture()
    assert not any(m.executed for m in hf.modules)
    for module, expected in zip(hf.modules, (3, 3, 2)):
        assert module.settings["type"] == 2
        assert module.settings["edge"] == 1
        assert module.settings["triggernode"].endswith("/demods/2/sample.dio")
        assert module.settings["count"] == module.settings["historylength"] == expected + 1
        assert module.settings["grid/overwrite"] == module.settings["grid/waterfall"] == 0
        assert module.settings["endless"] == module.settings["save/saveonread"] == 0
        assert module.settings["flags"] == 0xC
    assert hf.modules[0].settings["bits"] == hf.modules[1].settings["bits"] == 1 << 21
    assert hf.modules[2].settings["bits"] == 1 << 17
    assert list(map(lambda m: len(m.paths), hf.modules)) == [2, 1, 1]
    assert all("/demods/3/" not in path for module in hf.modules for path in module.paths)
    assert .0026 <= hf.modules[0].getDouble("duration") <= .0027
    assert hf.modules[2].settings["grid/cols"] == 4
    daq.arm()
    assert daq.expected_records_received() and not daq.finished()
    assert not any(m.read_count for m in hf.modules)


def test_capacity_size_is_readback_grid_plus_representation_metadata_and_margin():
    hf, daq = daq_fixture()
    estimates = daq.capacity["modules"]
    assert estimates[0]["payload_bytes"] == 2 * 53 * 4 * 16
    assert estimates[0]["metadata_bytes"] == 2 * 4 * 4096
    assert daq.capacity["required_bytes"] == sum(m["estimated_bytes"] for m in estimates)
    assert daq.capacity["required_bytes"] == 96000
    direct = estimate_capture_bytes(signal_paths=["sample.x"], grid_cols=10, count=2, duration_s=.001, rate_sps=10_000.)
    assert direct["estimated_bytes"] == (320+8192)*1.25


@pytest.mark.parametrize("failure", ["host_budget", "small", "history", "invalid_provider"])
def test_capacity_fails_before_arming_or_emission(failure):
    hf = FakeHF(nominal_events())
    verifier = fake_reservation
    if failure == "host_budget": verifier = None
    if failure == "small": verifier = lambda *a: ResidentCapacityReservation(10, "too-small", "test allocator")
    if failure == "history": hf.shrink_history = True
    if failure == "invalid_provider": verifier = lambda *a: {"capacity_ok": True}
    with pytest.raises(AcquisitionCapacityError):
        FinitePhaseDAQ(hf, events=hf.events, duration_s=.0026, pretrigger_s=.0001,
                       capacity_verifier=verifier, host_capacity_bytes=1 if failure == "host_budget" else 64*1024*1024)
    assert not any(m.executed for m in hf.modules)
    assert all(m.cleared for m in hf.modules)


def test_independent_pump_timestamps_are_kept_before_and_after_detector_window():
    hf, daq = daq_fixture()
    daq.arm(); daq.mark_sequence_complete()
    records = daq.records()
    assert records[0][1]["pump_event_tick"] is None
    assert records[1][1]["pump_event_tick"] > records[1][1]["sweep_event_tick"] + 260000
    assert records[2][1]["pump_event_tick"] < records[2][1]["sweep_event_tick"] - 10000
    assert all(len(record[1]["native_chunks"]) == 1 for record in records)
    assert all(record[1]["detector_mode"] == SINGLE_DETECTOR_MODE for record in records)
    assert all(record[1]["detector_input"] == DETECTOR_INPUT for record in records)
    assert all(len(record[1]["native_chunks"][0]["data"]) == 2 for record in records)
    assert all(m.read_count == 1 for m in hf.modules)


@pytest.mark.parametrize("failure", ["count", "duplicate", "nonmonotonic", "drop", "overflow", "clip", "two_sweeps", "wrong_pump"])
def test_integrity_faults_preserve_native_without_retry(failure):
    hf, daq = daq_fixture()
    daq.arm()
    hf.payloads = {id(m): m.read(True) for m in hf.modules}
    detector = hf.payloads[id(hf.modules[0])]
    path = hf.modules[0].paths[0]
    record = detector[path][0]
    if failure == "count": detector[path].pop()
    if failure == "duplicate": detector[path][1] = deepcopy(record)
    if failure == "nonmonotonic": record["timestamp"][0, 2] = record["timestamp"][0, 1]
    if failure == "drop": record["timestamp"][0, 3:] += 10000
    if failure == "overflow": record["header"]["overflow"] = 1
    if failure == "clip": record["header"]["clipped"] = 1
    if failure == "two_sweeps":
        timing = hf.payloads[id(hf.modules[1])][hf.modules[1].paths[0]][0]["value"]
        timing[0, 30:32] &= np.uint32(~(1 << 21) & 0xffffffff)
    if failure == "wrong_pump":
        for r in hf.payloads[id(hf.modules[2])][hf.modules[2].paths[0]]:
            r["timestamp"] += 2000000
    daq.mark_sequence_complete()
    with pytest.raises(AcquisitionIntegrityError): daq.records()
    assert daq.raw["modules"]
    assert hf.calls.count("daq_arm") == 3


def test_unpumped_baseline_has_pump_guard_and_rejects_an_accidental_event():
    hf, daq = daq_fixture([nominal_events()[0]])
    daq.arm()
    hf.payloads = {id(m): m.read(True) for m in hf.modules}
    module = hf.modules[2]
    assert module.settings["count"] == 1
    hf.payloads[id(module)][module.paths[0]] = [{"value": [[0, 1 << 17]], "timestamp": [[1, 2]]}]
    daq.mark_sequence_complete()
    with pytest.raises(AcquisitionIntegrityError, match="Exact record count"):
        daq.records()


def test_failed_module_read_salvages_other_modules():
    hf, daq = daq_fixture()
    daq.arm(); daq.mark_sequence_complete(); hf.read_failure = True
    with pytest.raises(AcquisitionIntegrityError, match="sample loss"):
        daq.read()
    partial = daq.read(partial=True)
    assert set(partial["modules"]) == {"timing", "pump_events"}
    assert partial["read_errors"]


@pytest.mark.parametrize("delay", [-3200, 0, 5000])
def test_frame_pulses_have_signed_phase_and_baseline_pump_inhibition(delay):
    recipe, _ = event_timing(PhaseScanEvent(1, 1, 0, True, delay))
    fire, qswitch, process = [float(recipe["channels"][ch]["delay"][:-1]) for ch in "ABC"]
    assert min(fire, qswitch, process) >= 0
    assert process-fire-.000180 == pytest.approx(delay*1e-6)
    assert qswitch-fire == pytest.approx(.000179830)
    baseline, _ = event_timing(nominal_events()[0])
    assert all(not baseline["channels"][ch]["enabled"] for ch in "ABD")
    assert baseline["channels"]["C"]["enabled"]


def test_missing_qualification_is_rejected_without_device_connections():
    adapter = LivePhaseScanAcquirer()
    with pytest.raises(RuntimeError, match="qualified calibrated sweep trajectory"):
        adapter.resolve_plan(build_phase_scan_plan(PhaseScanSettings()))
    assert not adapter.units and adapter.qcl is adapter.hf is None


def test_user_authorization_is_required_before_preparing_devices(tmp_path):
    adapter = LivePhaseScanAcquirer()
    with pytest.raises(PermissionError):
        adapter.prepare(PhaseScanSettings(), SimpleNamespace(path=tmp_path), Event())
    assert not adapter.units


class BlockTimer(Timer):
    def configure_continuous_clock(self, **kwargs):
        self.world.trace.append("clock_preload")
        recipe = {"trigger_source": "OFF", "clock": {"frequency": "2000000Hz"},
                  "channels": {c: {"enabled": c != "D", "delay": "0ns", "width": "150ns",
                                    "polarity": "positive", "termination": "50OHM"} for c in "ABCD"}}
        self.apply_recipe(recipe)
        return recipe
    def verified_frame_capacity(self): return 8192
    def preload_frame_table(self, frames, **kwargs):
        assert not self.world.running
        assert kwargs["predivider"] == 600000
        self.frames = frames
        self.world.trace.append("frame_table_preload")
        return {"physical_frame_count": max(2, len(frames)), "acquisition_frame_count": len(frames)}
    def start_frame_table(self):
        assert all(m.executed for m in self.world.hf.modules)
        assert self.world.units['t660_1'].source == 'SYN'
        assert not self.world.units['t660_1'].channels['C']['enabled']
        self.world.trace.append("frames_start")
        self.world.frame_armed = True
        self.source = "EXT"
    def start_continuous_clock(self):
        assert self.channels['A']['enabled']
        assert all(not self.channels[channel]['enabled'] for channel in 'BCD')
        assert not self.world.running and not any(m.executed for m in self.world.hf.modules)
        self.world.trace.append("clock_start")
        self.source = "SYN"
    def enable_channel(self, channel):
        if self.name == 't660_1' and channel in 'BC':
            assert all(m.executed for m in self.world.hf.modules)
            assert self.world.frame_armed
            self.world.trace.append('probe_enable' if channel == 'B' else 'event_clock_enable')
            if channel == 'C':
                assert self.channels['B']['enabled']
                self.world.running = True
                timer = self.world.units['t660_2']
                timer.shots += max(2, len(timer.frames))
        return super().enable_channel(channel)
    def get_frames_status(self):
        self.world.trace.append("frame_status")
        if self.world.fault == "interlock": self.world.interlock = False
        if self.world.fault == "cancel": self.world.cancel.set()
        if self.world.fault == "engine": return "ERROR"
        if self.world.fault == "count": self.shots += 1
        return "DONE"
    def command(self, command, **kwargs):
        if command == "STOP":
            self.world.trace.append(self.name+"_safe_stop")
            self.world.running = False
        return super().command(command, **kwargs)


class BlockLaser:
    def __init__(self, rig):
        self.rig = rig
        self.params = {}
        self.armed = self.emission = self.tuned = False
        self.start_count = self.tune_count = 0
    def initialize(self): pass
    def deinitialize(self): pass
    def is_interlock_set(self): return self.rig.interlock
    def is_key_switch_set(self): return self.rig.fault != "key"
    def get_system_error_word(self): return 0
    def stop_scan_if_needed(self): pass
    def turn_emission_off(self): self.emission = False
    def set_red_laser_pointer_enabled(self, enabled): assert not enabled
    def cancel_manual_tune(self):
        assert self.rig.units["t660_1"].source != "SYN" or not self.rig.units["t660_1"].channels["B"]["enabled"]
        if self.rig.fault == "cancel_tune" and self.tuned: raise RuntimeError("manual tune cancellation failed")
    def get_num_installed_qcls(self): return 1
    def get_qcl_tuning_range(self, qcl): return {"qcl": qcl, "min_cm1": 1800., "max_cm1": 2100.}
    def get_qcl_pulse_limits(self, qcl):
        return {"max_pulse_rate_hz": 3e6, "max_pulse_width_ns": 500., "max_duty_cycle": 30.}
    def get_qcl_current_limits(self, qcl): return 100., 1500.
    def set_qcl_pulse_params(self, **kwargs): self.params = kwargs
    def get_qcl_current(self, qcl): return self.params["current_ma"]
    def get_qcl_pulse_rate(self, qcl): return self.params["pulse_rate_hz"]
    def get_qcl_pulse_width(self, qcl): return self.params["pulse_width_ns"]
    def set_external_sweep_trigger_params(self, **kwargs):
        self.trigger = {"pulse_mode": 2, "process_trigger_mode": 2, "units": 2,
                        "start": kwargs["start_cm1"], "stop": kwargs["stop_cm1"],
                        "interval": kwargs["wavelength_trigger_interval_cm1"]}
        return self.trigger
    def get_wavelength_trigger_params(self): return self.trigger
    def set_wavelength_trigger_pulse_width_us(self, width): return width
    def arm(self): self.armed = True
    def disarm(self): self.armed = False
    def is_laser_armed(self): return self.armed
    def are_tecs_ready(self): return True
    def tune_to_wavenumber(self, value, **kwargs): self.tuned = True; self.tune_count += 1
    def is_tuned(self): return self.tuned
    def turn_emission_on(self, **kwargs):
        assert kwargs["approved_laser_safety_condition"]
        assert not self.rig.running
        probe = self.rig.units['t660_1']
        assert probe.source == 'SYN' and probe.channels['A']['enabled']
        assert not probe.channels['B']['enabled'] and not probe.channels['C']['enabled']
        self.rig.trace.append("emission_enable")
        self.emission = True
    def is_emission_on(self): return self.emission
    def start_sweep_scan(self, **kwargs):
        self.rig.trace.append("sweep_block_start")
        self.start_count += 1
        self.repetitions = kwargs["repetitions"]
        if self.rig.fault == "reset_internal": self.params["pulse_rate_hz"] = 2e6
    def get_scan_waiting_process_trigger(self): return True
    def get_scan_status(self): return {"scan_in_progress": False}
    def read_state(self):
        return SimpleNamespace(to_dict=lambda: {"emission_on": self.emission, "armed": self.armed, "scan_in_progress": False})


class RepeatingBlockTimer(BlockTimer):
    """Model frame DONE/restoration and per-block counters across real captures."""
    def __init__(self, *args):
        super().__init__(*args)
        self.engine_state = "OFF"
        self.engine_transitions = ["OFF"]
        self.preload_states = []
        self.pre_frame_channels = deepcopy(self.channels)

    def preload_frame_table(self, frames, **kwargs):
        probe = self.world.units["t660_1"]
        assert probe.source == "SYN" and probe.channels["A"]["enabled"]
        assert all(not probe.channels[c]["enabled"] for c in "BCD")
        assert self.source == "OFF" and not self.world.running
        active_modules = [m for m in self.world.hf.modules if not m.cleared]
        assert len(active_modules) == 3 and not any(m.executed for m in active_modules)
        self.preload_states.append((self.engine_state, self.shots))
        # preload_frame_table inhibits the source, stops/restores the engine,
        # then clears the shot counter before staging the next bounded table.
        self.command("TFRame:STOp", expect_response=False)
        self.shots = 0
        return super().preload_frame_table(frames, **kwargs)

    def start_frame_table(self):
        assert self.engine_state == "OFF" and self.shots == 0
        active_modules = [m for m in self.world.hf.modules if not m.cleared]
        assert len(active_modules) == 3 and all(m.executed for m in active_modules)
        self.pre_frame_channels = deepcopy(self.channels)
        super().start_frame_table()
        self.engine_state = "RUNNING"
        self.engine_transitions.append(self.engine_state)

    def get_frames_status(self):
        assert self.engine_state in {"RUNNING", "DONE"}
        state = super().get_frames_status()
        if state != self.engine_state:
            self.engine_transitions.append(state)
        self.engine_state = state
        self.channels = deepcopy(self.frames[-1]["channels"])
        return state

    def command(self, command, **kwargs):
        if command == "TFRame:STOp":
            assert self.source == "OFF" and not self.world.running
            self.channels = deepcopy(self.pre_frame_channels)
            self.engine_state = "OFF"
            self.engine_transitions.append(self.engine_state)
            self.world.frame_armed = False
        return super().command(command, **kwargs)


def live_fixture(tmp_path, fault=None, capacity_verifier=fake_reservation, settings=None, snapshot_overrides=None,
                  prepare=True, timer_type=BlockTimer):
    rig = SimpleNamespace(units={}, running=False, trace=[], fail_stop=False, interlock=True,
                          fault=fault, cancel=Event())
    rig.hf = FakeHF(nominal_events())
    rig.hf.snapshot_overrides = snapshot_overrides or {}
    rig.hf.calls = rig.trace
    rig.laser = BlockLaser(rig)
    def verify_reference_only():
        probe, pump = rig.units['t660_1'], rig.units['t660_2']
        assert probe.source == 'SYN' and probe.channels['A']['enabled']
        assert all(not probe.channels[channel]['enabled'] for channel in 'BCD')
        assert pump.source == 'OFF' and all(not pump.channels[channel]['enabled'] for channel in 'ABCD')
        assert not rig.laser.emission and not rig.running
        assert not any(module.executed for module in rig.hf.modules)
        rig.trace.append('hf_configuration_with_reference_only')
        if rig.fault == 'hf_configuration':
            raise RuntimeError('injected HF configuration failure')
    rig.hf.verify_reference_only = verify_reference_only
    trajectory = {"source_id": "qualified-test-trajectory", "time_s": [0., .002], "wavenumber_cm1": [1950., 1940.]}
    adapter = LivePhaseScanAcquirer(laser_factory=lambda **kw: rig.laser,
        hf_factory=lambda **kw: rig.hf, t660_factory=lambda name, **kw: timer_type(rig, name),
        qualified_trajectory=trajectory, qualified_sweep_active_s=.00232,
        tec_ready_stability_s=0., capacity_verifier=capacity_verifier)
    adapter.authorize(True)
    if prepare:
        # The synthetic 2 ms waveform covers this explicit narrow range.
        fixture_settings = settings or PhaseScanSettings(start_wavenumber_cm1=1950, stop_wavenumber_cm1=1940)
        adapter.preparation_readback = adapter.prepare(fixture_settings, SimpleNamespace(path=tmp_path), rig.cancel)
    return rig, adapter


def test_live_block_is_preloaded_armed_once_and_never_serializes_during_frames(tmp_path, monkeypatch):
    import control_app.workflows.phase_scan_acquisition as live
    from io import StringIO
    rig, adapter = live_fixture(tmp_path)
    original_write = live.write_json
    def checked_write(*args):
        assert not rig.running
        original_write(*args)
    monkeypatch.setattr(live, "write_json", checked_write)
    original_convert = live.spectrum_from_sweep
    def checked_convert(*args, **kwargs):
        assert not rig.running
        rig.trace.append("spectrum_conversion")
        return original_convert(*args, **kwargs)
    monkeypatch.setattr(live, "spectrum_from_sweep", checked_convert)
    blocks = adapter.prepare_blocks(adapter.plan, rig.hf.events, rig.cancel)
    assert len(blocks) == 1 and isinstance(adapter.log, StringIO)
    assert not any(m.executed for m in rig.hf.modules)
    raw, spectra = adapter.capture_block(blocks[0], rig.cancel)
    assert not rig.running and len(spectra) == 3
    assert rig.laser.start_count == rig.laser.tune_count == 1
    assert rig.laser.repetitions == 3
    assert rig.trace.count("frame_table_preload") == rig.trace.count("frames_start") == 1
    assert rig.trace.index("frame_table_preload") < rig.trace.index("emission_enable") < rig.trace.index("frames_start")
    assert rig.trace.index('clock_start') < rig.trace.index('hf_configuration_with_reference_only') < rig.trace.index('daq_arm')
    assert rig.trace.index('frames_start') < rig.trace.index('probe_enable') < rig.trace.index('event_clock_enable')
    assert rig.trace.count('clock_start') == 1
    assert max(i for i, value in enumerate(rig.trace) if value == "daq_read") < rig.trace.index("t660_1_safe_stop")
    assert rig.trace.index("t660_2_safe_stop") < rig.trace.index("spectrum_conversion")
    assert rig.hf.calls.count("daq_arm") == 3
    assert rig.hf.calls.count("daq_read") == 3
    assert not (tmp_path / "commands.txt").exists()
    assert raw["labone"]["modules"] and all(s.metadata["optical_valid"] for _, s in spectra)
    assert all(s.reference_r is None and s.detector_mode == SINGLE_DETECTOR_MODE for _, s in spectra)
    assert all("/adcclip/1" not in call for call in rig.trace)
    adapter.close(); adapter.close()
    assert all(rig.trace.count(name+"_safe_stop") == 1 for name in ("t660_1", "t660_2"))
    assert not rig.running and not rig.laser.armed and not rig.laser.emission
    assert (tmp_path / "commands.txt").exists()


@pytest.mark.parametrize("fault", ["interlock", "cancel", "engine", "count", "cancel_tune", "reset_internal"])
def test_live_fault_stops_immediately_preserves_block_and_close_is_idempotent(tmp_path, fault):
    rig, adapter = live_fixture(tmp_path, fault)
    block = adapter.prepare_blocks(adapter.plan, rig.hf.events, rig.cancel)[0]
    with pytest.raises((RuntimeError, InterruptedError)):
        adapter.capture_block(block, rig.cancel)
    assert not rig.running and not rig.laser.emission and not rig.laser.armed
    if fault in {"cancel_tune", "reset_internal"}:
        assert adapter.partial_blocks[0]["labone"]["capture_not_started"]
        assert not any(module.executed for module in rig.hf.modules)
    else:
        assert adapter.partial_blocks[0]["labone"]["modules"]
    assert adapter.partial_blocks[0]["error"]
    adapter.close(); adapter.close()
    assert all(rig.trace.count(name+"_safe_stop") == 1 for name in ("t660_1", "t660_2"))
    assert rig.trace.count("frames_start") <= 1 and rig.laser.start_count <= 1


@pytest.mark.parametrize("failure", ["missing_sweep_edge", "reconstruction"])
def test_rejected_live_validation_never_marks_salvaged_block_optically_valid(tmp_path, monkeypatch, failure):
    import control_app.workflows.phase_scan_acquisition as live
    rig, adapter = live_fixture(tmp_path)
    block = adapter.prepare_blocks(adapter.plan, rig.hf.events, rig.cancel)[0]
    if failure == "missing_sweep_edge":
        original_read = FakeModule.read
        def read_without_sweep_edge(module, flat):
            payload = original_read(module, flat)
            if module.settings["bits"] == 1 << 21 and module.paths[0].endswith(".dio"):
                for record in payload.get(module.paths[0], []):
                    record["value"] &= np.uint32(~(1 << 21) & 0xffffffff)
            return payload
        monkeypatch.setattr(FakeModule, "read", read_without_sweep_edge)
        expected_error = "Expected exactly one DIO21 rising event"
    else:
        def reject_reconstruction(*args, **kwargs):
            raise ValueError("injected reconstruction rejection")
        monkeypatch.setattr(live, "spectrum_from_sweep", reject_reconstruction)
        expected_error = "injected reconstruction rejection"
    with pytest.raises((AcquisitionIntegrityError, ValueError), match=expected_error):
        adapter.capture_block(block, rig.cancel)
    partial = adapter.partial_blocks[0]
    assert partial["optical_valid"] is False
    assert partial["labone"]["modules"] and partial["labone"]["read_chunks"]
    assert not rig.running and not rig.laser.emission and not rig.laser.armed
    assert all(m.cleared for m in rig.hf.modules)
    adapter.close()


@pytest.mark.parametrize("second_block_failure", [False, True])
def test_incremental_capture_restarts_second_block_with_fresh_daq_and_safe_frame_state(
        tmp_path, second_block_failure):
    rig, adapter = live_fixture(tmp_path, capacity_verifier=None, timer_type=RepeatingBlockTimer)
    events = [PhaseScanEvent(i, 1, i, True, 0.) for i in range(18)]
    blocks = adapter.prepare_blocks(adapter.plan, events, rig.cancel)
    assert [len(block["events"]) for block in blocks] == [16, 2]
    assert blocks[1]["daq"] is None
    rig.hf.events = blocks[0]["events"]
    first, spectra = adapter.capture_block(blocks[0], rig.cancel)
    assert first["optical_valid"] is True and len(spectra) == 16
    assert (first["shot_counter_before"], first["shot_counter_after"]) == (0, 16)
    probe, timer = rig.units["t660_1"], rig.units["t660_2"]
    assert timer.engine_state == "DONE" and timer.source == "OFF"
    assert probe.source == "SYN" and probe.channels["A"]["enabled"]
    assert all(not probe.channels[c]["enabled"] for c in "BCD")
    assert not rig.running and not rig.laser.emission and rig.laser.armed
    assert all(m.cleared for m in rig.hf.modules) and adapter._active_daq is None
    assert blocks[1]["daq"] is None
    rig.hf.events = blocks[1]["events"]
    if second_block_failure:
        rig.fault = "engine"
        with pytest.raises(AcquisitionIntegrityError, match="frame engine reported an error"):
            adapter.capture_block(blocks[1], rig.cancel)
        partial = adapter.partial_blocks[0]
        assert partial["block_index"] == 1 and partial["optical_valid"] is False
        assert partial["labone"]["modules"] and partial["labone"]["read_chunks"]
        assert first["optical_valid"] is True
    else:
        second, spectra = adapter.capture_block(blocks[1], rig.cancel)
        assert second["optical_valid"] is True and len(spectra) == 2
        assert [event for event, _ in spectra] == list(blocks[1]["events"])
        assert (second["shot_counter_before"], second["shot_counter_after"]) == (0, 2)
        assert not adapter.partial_blocks
    assert timer.preload_states == [("OFF", 0), ("DONE", 16)]
    assert timer.engine_transitions == ["OFF", "OFF", "RUNNING", "DONE", "OFF", "RUNNING",
                                        "ERROR" if second_block_failure else "DONE", "OFF"]
    assert rig.trace.count("clock_start") == 1
    assert rig.trace.count("frames_start") == rig.laser.start_count == 2
    assert len(rig.hf.modules) == 6 and all(m.cleared for m in rig.hf.modules)
    assert not rig.running and not rig.laser.emission and not rig.laser.armed
    assert all(unit.source == "OFF" for unit in rig.units.values())
    assert all(not unit.channels[c]["enabled"] for unit in rig.units.values() for c in "ABCD")
    assert adapter._active_daq is None
    adapter.close()


def test_cleanup_disables_channels_after_frame_stop_restores_previous_configuration():
    calls = []
    class RestoringTimer:
        name = "t660_2"
        source = "EXT"
        enabled = dict.fromkeys("ABCD", True)
        def set_trigger_source(self, source):
            self.source = source
            calls.append("source_" + source)
        def command(self, command, **kwargs):
            calls.append(command)
            if command == "TFRame:STOp":
                assert self.source == "OFF" and "STOP" in calls
                self.enabled = dict.fromkeys("ABCD", True)
        def disable_channel(self, channel):
            calls.append("disable_" + channel)
            self.enabled[channel] = False
    timer = RestoringTimer()
    LivePhaseScanAcquirer._stop_unit(timer)
    assert timer.source == "OFF" and not any(timer.enabled.values())
    assert calls.index("TFRame:STOp") < min(calls.index("disable_" + c) for c in "ABCD")


def controller_marker_record():
    readback = {"channel": 1, "units": 2, "start": 1950., "stop": 1940., "interval": 5., "num_triggers": 3}
    return {"scan_profile": {"qcl": 1, "start_cm1": 1950., "stop_cm1": 1940., "marker_interval_cm1": 5.},
            "mircat_marker_channel_checks": [
                {"source": "MIRcatSDK_GetWlTrigChanParams", "available": True, "channel": 1,
                 "context": context, "timestamp_utc": "2026-09-06T00:00:00+00:00", "readback": deepcopy(readback)}
                for context in ("configured", "after_sweep_setup")]}


def test_controller_marker_identity_requires_observed_count_and_preserves_provisional_basis():
    record = controller_marker_record()
    identity = controller_marker_identity(record, 3)
    assert identity["wavenumbers_cm1"] == [1950., 1945., 1940.]
    assert identity["wavenumber_basis"] == "controller_markers"
    assert identity["provisional"] and not identity["independently_calibrated"]
    assert identity["marker_identity_basis"]["readback"] == record["mircat_marker_channel_checks"][-1]["readback"]
    identity["marker_identity_basis"]["readback"]["start"] = 1
    assert record["mircat_marker_channel_checks"][-1]["readback"]["start"] == 1950.
    assert controller_marker_identity({}, 3) is None
    record["mircat_marker_channel_checks"][-1] = {"context": "after_sweep_setup", "available": False, "error": "unsupported"}
    assert controller_marker_identity(record, 3) is None


@pytest.mark.parametrize("fault", ["observed_count", "endpoint", "configured_changed", "channel", "profile_interval", "nan"])
def test_controller_marker_identity_rejects_conflicting_advertised_evidence(fault):
    record = controller_marker_record()
    readback = record["mircat_marker_channel_checks"][-1]["readback"]
    count = 3
    if fault == "observed_count": count = 2
    if fault == "endpoint": readback["num_triggers"] = 4; count = 4
    if fault == "configured_changed": record["mircat_marker_channel_checks"][0]["readback"]["interval"] = 4.
    if fault == "channel": record["scan_profile"]["qcl"] = 2
    if fault == "profile_interval": record["scan_profile"]["marker_interval_cm1"] = 10.
    if fault == "nan": readback["start"] = float("nan")
    with pytest.raises(ValueError):
        controller_marker_identity(record, count)


def test_controller_marker_identity_converts_native_micron_spacing_without_linear_cm1_guess():
    record = controller_marker_record()
    record.pop("scan_profile")
    for observation in record["mircat_marker_channel_checks"]:
        observation["readback"].update(units=1, start=5., stop=6., interval=.5)
    identity = controller_marker_identity(record, 3)
    np.testing.assert_allclose(identity["wavenumbers_cm1"], [2000., 10000/5.5, 10000/6.])


@pytest.mark.parametrize("sdk_available", [True, False])
def test_phase_capture_preserves_marker_readback_and_does_not_claim_absolute_calibration(tmp_path, monkeypatch, sdk_available):
    def marker_readback(laser, channel):
        assert channel == 1 and laser.start_count == 1
        assert not any(module.executed for module in laser.rig.hf.modules)
        return {"channel": 1, "units": 2, "start": 1950., "stop": 1940., "interval": 5., "num_triggers": 3}
    if sdk_available:
        monkeypatch.setattr(BlockLaser, "get_wavelength_trigger_channel_params", marker_readback, raising=False)
    rig, adapter = live_fixture(tmp_path)
    block = adapter.prepare_blocks(adapter.plan, rig.hf.events, rig.cancel)[0]
    raw, spectra = adapter.capture_block(block, rig.cancel)
    observation = raw["mircat_marker_channel_checks"][0]
    assert observation["context"] == "after_block_setup" and observation["available"] is sdk_available
    for _, spectrum in spectra:
        assert spectrum.metadata["mircat_marker_channel_checks"] == raw["mircat_marker_channel_checks"]
        assert spectrum.metadata["wavenumber_basis"] == ("controller_markers" if sdk_available else "nominal_sweep_bounds")
        assert spectrum.metadata["provisional"]
        if sdk_available:
            assert not spectrum.metadata["independently_calibrated"]
            assert spectrum.metadata["marker_identity_basis"]["readback"] == observation["readback"]
    adapter.close()


def test_live_insufficient_capacity_preflight_emits_nothing(tmp_path):
    rig, adapter = live_fixture(tmp_path, capacity_verifier=None)
    adapter.max_retained_bytes = 1
    with pytest.raises(AcquisitionCapacityError, match="Run retention estimate"):
        adapter.prepare_blocks(adapter.plan, rig.hf.events, rig.cancel)
    adapter.close()
    assert "emission_enable" not in rig.trace and "frames_start" not in rig.trace


def test_default_host_capture_prepares_only_first_small_block(tmp_path):
    rig, adapter = live_fixture(tmp_path, capacity_verifier=None)
    events = [PhaseScanEvent(i, 1, i, True, 0.) for i in range(33)]
    blocks = adapter.prepare_blocks(adapter.plan, events, rig.cancel)
    assert [event for block in blocks for event in block["events"]] == events
    assert all(len(block["events"]) <= 16 for block in blocks)
    assert blocks[0]["daq"].incremental
    assert all(block["daq"] is None for block in blocks[1:])
    assert len(rig.hf.modules) == 3
    assert not any(module.executed for module in rig.hf.modules)
    assert "emission_enable" not in rig.trace and "frames_start" not in rig.trace
    adapter.close()


def test_incremental_service_waits_until_arm_and_stops_after_close():
    calls = []
    adapter = LivePhaseScanAcquirer()
    adapter._active_daq = SimpleNamespace(incremental=True, armed=False, closed=False,
                                          drain=lambda: calls.append("drained"))
    adapter._service_daq()
    assert not calls
    adapter._active_daq.armed = True
    adapter._service_daq()
    assert calls == ["drained"]
    adapter._active_daq.closed = True
    adapter._service_daq()
    assert calls == ["drained"]


def test_reference_only_preflight_does_not_enable_optical_or_frame_outputs(tmp_path):
    rig, adapter = live_fixture(tmp_path)
    try:
        probe, timer = rig.units['t660_1'], rig.units['t660_2']
        assert probe.source == 'SYN' and probe.channels['A']['enabled']
        assert all(not probe.channels[c]['enabled'] for c in 'BCD')
        assert timer.source == 'OFF' and all(not timer.channels[c]['enabled'] for c in 'ABCD')
        assert timer.shots == 0 and not rig.laser.emission
        assert rig.trace.index('clock_start') < rig.trace.index('hf_configuration_with_reference_only')
    finally:
        adapter.close()
    assert all(not unit.channels[c]['enabled'] for unit in rig.units.values() for c in 'ABCD')
    assert all(unit.source == 'OFF' for unit in rig.units.values())


def test_failed_hf_preparation_stops_the_already_running_reference_on_cleanup(tmp_path):
    rig, adapter = live_fixture(tmp_path, fault='hf_configuration', prepare=False)
    with pytest.raises(RuntimeError, match='injected HF configuration failure'):
        adapter.prepare(PhaseScanSettings(start_wavenumber_cm1=1950, stop_wavenumber_cm1=1940),
                        SimpleNamespace(path=tmp_path), rig.cancel)
    adapter.close()
    assert 'clock_start' in rig.trace and 'frames_start' not in rig.trace
    assert 'emission_enable' not in rig.trace
    assert all(unit.source == 'OFF' for unit in rig.units.values())
    assert all(not unit.channels[c]['enabled'] for unit in rig.units.values() for c in 'ABCD')


@pytest.mark.parametrize("trajectory,message", [
    ({"time_s": [0., .005]}, "exceeds the qualified"),
    ({"time_s": [0., .002], "sweep_active_delay_s": .001}, "outside the qualified"),
])
def test_contradictory_trajectory_and_active_interval_fail_before_devices(trajectory, message):
    adapter = LivePhaseScanAcquirer(qualified_trajectory={"source_id": "test", "wavenumber_cm1": [1950., 1940.],
                                                        **trajectory}, qualified_sweep_active_s=.00232)
    with pytest.raises(RuntimeError, match=message):
        adapter.resolve_plan(build_phase_scan_plan(PhaseScanSettings(start_wavenumber_cm1=1950, stop_wavenumber_cm1=1940)))
    assert not adapter.units


def test_blank_and_phase_step_changes_retain_identical_full_hf2_configuration(tmp_path):
    first, blank = live_fixture(tmp_path / "blank")
    second, phase = live_fixture(tmp_path / "phase", settings=PhaseScanSettings(
        start_wavenumber_cm1=1950, stop_wavenumber_cm1=1940, phase_delay_us=100.))
    try:
        blank_settings = blank.preparation_readback["hf2li_detector_settings"]
        assert blank_settings == phase.preparation_readback["hf2li_detector_settings"]
        assert blank_settings["/dev1234/sigins/0/diff"]["value"] == 0
        assert blank_settings["/dev1234/demods/0/adcselect"]["value"] == 0
        assert blank_settings["/dev1234/demods/3/enable"]["value"] == 0
        assert blank_settings["/dev1234/demods/2/enable"]["value"] == 1
        assert blank_settings["/dev1234/demods/2/rate"]["value"] == 200000.
        assert blank_settings["/dev1234/plls/0/adcselect"]["value"] == 4
        assert all("/sigins/1/" not in path for path in blank_settings)
    finally:
        # This fixture does not create the runner's run directories.
        blank.store = phase.store = None
        blank.close(); phase.close()


@pytest.mark.parametrize("node,value", [
    ("sigins/0/diff", 1), ("demods/0/adcselect", 1),
    ("demods/0/timeconstant", .001), ("demods/3/enable", 1),
    ("demods/2/trigger", 1), ("plls/0/adcselect", 0),
])
def test_wrong_single_detector_or_timing_configuration_fails_preflight(tmp_path, node, value):
    with pytest.raises(RuntimeError, match="readback differs"):
        live_fixture(tmp_path, snapshot_overrides={f"/dev1234/{node}": value})


def test_single_detector_clipping_still_rejects_acquisition(tmp_path):
    rig, adapter = live_fixture(tmp_path)
    try:
        rig.hf.clipping[0] = 1
        with pytest.raises(AcquisitionIntegrityError, match="input 1 clipping"):
            adapter._input_integrity("test")
    finally:
        adapter.close()
