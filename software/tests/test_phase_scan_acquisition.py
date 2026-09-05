"""Hardware-free finite phase acquisition and shared timing transport fake."""
from copy import deepcopy
import numpy as np
import pytest
from threading import Event
from types import SimpleNamespace
from control_app.workflows.phase_scan import PhaseScanEvent, PhaseScanSettings, build_phase_scan_plan
from control_app.workflows.phase_scan_acquisition import LivePhaseScanAcquirer, event_timing
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
    def execute(self): self.executed = True; self.hf.calls.append("daq_arm")
    def finished(self): return False  # The extra integrity guard remains armed.
    def progress(self):
        return [len(self.selected_events) / self.settings["count"]]
    @property
    def selected_events(self):
        return [e for e in self.hf.events if e.pump_enabled] if self.settings["bits"] == 1 << 17 else self.hf.events
    def read(self, flat):
        assert flat and self.executed
        self.read_count += 1
        self.hf.calls.append("daq_read")
        if self.hf.read_failure and self.paths[0].endswith(".x"):
            raise RuntimeError("sample loss detected by installed DAQ")
        if self.hf.payloads is not None:
            return self.hf.payloads[id(self)]
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
                if path.endswith(".bits"):
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
        self.rates = {0: 20_000., 2: 50_000., 3: 20_000.}
        self.modules, self.calls = [], []
        self.shrink_history = self.read_failure = False
        self.payloads = None
    def get_clockbase(self): return 100_000_000
    def _get_node(self, kind, path):
        if "adcclip" in path: return 0
        return self.rates[int(path.split("/demods/")[1].split("/")[0])]
    def create_daq_module(self):
        module = FakeModule(self)
        self.modules.append(module)
        return module
    def close(self): pass
    def connect(self): pass
    def get_oscillator_frequency(self, index): return 2_000_000.
    def load_preset(self, name):
        from control_app.devices.hf2li_service import HF2LIPreset
        return HF2LIPreset(name, {"signal_inputs": {}, "pll": {"freqcenter_hz": 2e6},
            "demodulators": [{"index": i, "enable": True, "rate_sps": self.rates[i],
                             "timeconstant_s": 50e-6, "order": 4} for i in (0, 2, 3)]})
    def apply_preset(self, preset):
        self.preset = preset
        for demod in preset.settings["demodulators"]:
            if "rate_sps" in demod: self.rates[demod["index"]] = demod["rate_sps"]
    def export_settings_snapshot(self, **kwargs):
        return {"device_id": self.device_id, "read_errors": {}, "nodes": {
            f"/{self.device_id}/demods/{i}/rate": {"type": "double", "value": self.rates[i]} for i in self.rates}}


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
        assert module.settings["triggernode"].endswith("/demods/2/sample.bits")
        assert module.settings["count"] == module.settings["historylength"] == expected + 1
        assert module.settings["grid/overwrite"] == module.settings["grid/waterfall"] == 0
        assert module.settings["endless"] == module.settings["save/saveonread"] == 0
        assert module.settings["flags"] == 0xC
    assert hf.modules[0].settings["bits"] == hf.modules[1].settings["bits"] == 1 << 21
    assert hf.modules[2].settings["bits"] == 1 << 17
    assert list(map(lambda m: len(m.paths), hf.modules)) == [4, 1, 1]
    assert .0026 <= hf.modules[0].getDouble("duration") <= .0027
    assert hf.modules[2].settings["grid/cols"] == 4
    daq.arm()
    assert daq.expected_records_received() and not daq.finished()
    assert not any(m.read_count for m in hf.modules)


def test_capacity_size_is_readback_grid_plus_representation_metadata_and_margin():
    hf, daq = daq_fixture()
    estimates = daq.capacity["modules"]
    assert estimates[0]["payload_bytes"] == 4 * 53 * 4 * 16
    assert estimates[0]["metadata_bytes"] == 4 * 4 * 4096
    assert daq.capacity["required_bytes"] == sum(m["estimated_bytes"] for m in estimates)
    assert daq.capacity["required_bytes"] == 145440
    direct = estimate_capture_bytes(signal_paths=["sample.x"], grid_cols=10, count=2, duration_s=.001, rate_sps=10_000.)
    assert direct["estimated_bytes"] == (320+8192)*1.25


@pytest.mark.parametrize("failure", ["unavailable", "small", "history", "invalid_provider"])
def test_capacity_fails_before_arming_or_emission(failure):
    hf = FakeHF(nominal_events())
    verifier = fake_reservation
    if failure == "unavailable": verifier = None
    if failure == "small": verifier = lambda *a: ResidentCapacityReservation(10, "too-small", "test allocator")
    if failure == "history": hf.shrink_history = True
    if failure == "invalid_provider": verifier = lambda *a: {"capacity_ok": True}
    with pytest.raises(AcquisitionCapacityError):
        FinitePhaseDAQ(hf, events=hf.events, duration_s=.0026, pretrigger_s=.0001, capacity_verifier=verifier)
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
        self.world.trace.append("frames_start")
        self.world.running = True
        self.source = "EXT"
        self.shots += max(2, len(self.frames))
    def start_continuous_clock(self):
        assert self.world.running
        self.world.trace.append("clock_start")
        self.source = "SYN"
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
        assert all(m.executed for m in self.rig.hf.modules)
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


def live_fixture(tmp_path, fault=None, capacity_verifier=fake_reservation):
    rig = SimpleNamespace(units={}, running=False, trace=[], fail_stop=False, interlock=True,
                          fault=fault, cancel=Event())
    rig.hf = FakeHF(nominal_events())
    rig.hf.calls = rig.trace
    rig.laser = BlockLaser(rig)
    trajectory = {"source_id": "qualified-test-trajectory", "time_s": [0., .002], "wavenumber_cm1": [1950., 1940.]}
    adapter = LivePhaseScanAcquirer(laser_factory=lambda **kw: rig.laser,
        hf_factory=lambda **kw: rig.hf, t660_factory=lambda name, **kw: BlockTimer(rig, name),
        qualified_trajectory=trajectory, qualified_sweep_active_s=.00232,
        tec_ready_stability_s=0., capacity_verifier=capacity_verifier)
    adapter.authorize(True)
    adapter.prepare(PhaseScanSettings(), SimpleNamespace(path=tmp_path), rig.cancel)
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
    assert max(i for i, value in enumerate(rig.trace) if value == "daq_read") < rig.trace.index("t660_1_safe_stop")
    assert rig.trace.index("t660_2_safe_stop") < rig.trace.index("spectrum_conversion")
    assert rig.hf.calls.count("daq_arm") == 3
    assert rig.hf.calls.count("daq_read") == 3
    assert not (tmp_path / "commands.txt").exists()
    assert raw["labone"]["modules"] and all(s.metadata["optical_valid"] for _, s in spectra)
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
    assert adapter.partial_blocks[0]["labone"]["modules"]
    assert adapter.partial_blocks[0]["error"]
    adapter.close(); adapter.close()
    assert all(rig.trace.count(name+"_safe_stop") == 1 for name in ("t660_1", "t660_2"))
    assert rig.trace.count("frames_start") <= 1 and rig.laser.start_count <= 1


def test_live_insufficient_capacity_preflight_emits_nothing(tmp_path):
    rig, adapter = live_fixture(tmp_path, capacity_verifier=None)
    with pytest.raises(AcquisitionCapacityError, match="resident-history capacity is unverified"):
        adapter.prepare_blocks(adapter.plan, rig.hf.events, rig.cancel)
    adapter.close()
    assert "emission_enable" not in rig.trace and "frames_start" not in rig.trace
    assert not any(m.executed for m in rig.hf.modules)


@pytest.mark.parametrize("trajectory,message", [
    ({"time_s": [0., .005]}, "exceeds the qualified"),
    ({"time_s": [0., .002], "sweep_active_delay_s": .001}, "outside the qualified"),
])
def test_contradictory_trajectory_and_active_interval_fail_before_devices(trajectory, message):
    adapter = LivePhaseScanAcquirer(qualified_trajectory={"source_id": "test", "wavenumber_cm1": [1950., 1940.],
                                                        **trajectory}, qualified_sweep_active_s=.00232)
    with pytest.raises(RuntimeError, match=message):
        adapter.resolve_plan(build_phase_scan_plan(PhaseScanSettings()))
    assert not adapter.units
