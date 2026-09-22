"""Regular app acquisition against stateful, emitting-only-in-simulation devices."""
from copy import deepcopy
from ctypes import POINTER, c_float, c_uint8, c_uint16, cast
from dataclasses import replace
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest

from control_app.devices.hf2li_service import HF2LIService
from control_app.devices.mircat_service import MircatService, MircatConfigurationError
from control_app.workflows.regular_phase_scan import (
    HF2Capabilities, RegularPhaseScanSettings, build_regular_phase_scan_plan,
)
from control_app.workflows.regular_phase_scan_acquisition import RegularPhaseScanAcquirer, regular_event_timing
from control_app.workflows.phase_scan_labone import FinitePhaseDAQ, AcquisitionCapacityError, AcquisitionIntegrityError
from test_phase_scan_acquisition import BlockLaser, BlockTimer, FakeHF, FakeModule, nominal_events


class RegularModule(FakeModule):
    def read(self, flat):
        assert not self.hf.rig.running, "Native transfer must follow safe-idle or abort"
        assert flat and self.executed and not self.cleared
        self.read_count += 1
        self.hf.calls.append("daq_read")
        if self.read_count > 1:
            return {}
        result = {path: [] for path in self.paths}
        duration = self.hf.plan.scan_duration_s
        for event in self.selected_events:
            frame = .1+event.scan_index*self.hf.plan.frame_period_s
            timing, _ = regular_event_timing(event)
            pump = frame+float(timing["channels"]["B"]["delay"][:-1])
            sweep = frame+float(timing["channels"]["C"]["delay"][:-1])
            trigger = pump if self.settings["bits"] == 1 << 17 else sweep
            relative = self.settings["delay"]+np.arange(self.settings["grid/cols"])/self.rate
            ticks = np.uint64(self.hf.origin)+np.round((trigger+relative)*self.hf.get_clockbase()).astype(np.uint64)
            for path in self.paths:
                if path.endswith(".dio"):
                    values = np.zeros(len(ticks), np.uint32)
                    if self.settings["bits"] == 1 << 17:
                        values[relative >= -1e-12] |= 1 << 17
                    else:
                        values[(relative >= -1e-12) & (relative < duration+.00016)] |= 1 << 21
                        for marker in np.linspace(0., duration, self.hf.marker_count):
                            values[(relative >= marker-1e-12) & (relative < marker+.000125)] |= 1 << 22
                else:
                    values = np.full(len(ticks), 1. if path.endswith(".x") else 0.)
                result[path].append({"timestamp": ticks[None, :], "value": values[None, :], "header": {}})
        return result


class RegularHF(FakeHF):
    def __init__(self, rig, plan):
        super().__init__([plan.event_at(i) for i in range(plan.total_scans)])
        self.plan, self.rig, self.marker_count = plan, rig, 21
        self.values = {}
        self.preset = self.load_preset("exploratory_phase_scan_single_detector")
        self.apply_preset(self.preset)
        self.original = self.export_settings_snapshot()
    def apply_preset(self, preset):
        super().apply_preset(preset)
        self.values.update({p: entry["value"] for p, entry in super().export_settings_snapshot()["nodes"].items()})
    def export_settings_snapshot(self, **kwargs):
        output = super().export_settings_snapshot(**kwargs)
        for path, entry in output["nodes"].items():
            entry["value"] = self.values.get(path, entry["value"])
        return output
    def _set_node(self, method, path, value):
        self.values[path] = value
        if path.endswith("/rate"):
            self.rates[int(path.split("/demods/")[1].split("/")[0])] = value
    def sync(self): pass
    def reload_settings_snapshot(self, snapshot):
        for path, entry in snapshot["nodes"].items():
            self._set_node("setDouble", path, entry["value"])
    compare_settings_snapshots = HF2LIService.compare_settings_snapshots
    def create_daq_module(self):
        module = RegularModule(self)
        self.modules.append(module)
        return module


class RegularTimer(BlockTimer):
    def __init__(self, *args):
        super().__init__(*args)
        self.references = {edge: edge-1 if edge % 2 == 0 else 0 for edge in range(1, 9)}
        self.absolute = {edge: 10e-6 if edge % 2 == 0 else 0. for edge in range(1, 9)}
        self.modes = {channel: "DW" for channel in "ABCD"}
    def set_channel_timing_mode(self, channel, mode):
        self.modes[channel] = "RF" if mode in {"RF", "rise_fall"} else "DW"
    def command(self, command, **kwargs):
        if command.startswith("TIME:RELTo"):
            rest = command.removeprefix("TIME:RELTo")
            if rest.endswith("?"):
                return str(self.references[int(rest[:-1])])
            edge, reference = map(int, rest.split())
            self.references[edge] = reference
            return "OK"
        if command.startswith("TIME:QUEue"):
            edge, value = command.removeprefix("TIME:QUEue").split()
            self.absolute[int(edge)] = float(value[:-1])
            return "OK"
        return super().command(command, **kwargs)
    def apply_recipe(self, recipe):
        super().apply_recipe(recipe)
        for channel, values in recipe.get("channels", {}).items():
            if "timing_mode" in values:
                self.set_channel_timing_mode(channel, values["timing_mode"])
                rise = 1+2*"ABCD".index(channel)
                for edge, key in ((rise, "delay"), (rise+1, "width")):
                    value = self.absolute[edge]-self.absolute.get(self.references[edge], 0.)
                    self.channels[channel][key] = f"{value:.12f}s"
    def preload_frame_table(self, frames, **kwargs):
        assert kwargs["predivider"] == round(self.world.hf.plan.frame_period_s*2e6)
        self.frames = frames
        self.world.trace.append("frame_table_preload")
        return {"physical_frame_count": max(2, len(frames)), "acquisition_frame_count": len(frames)}


class RegularLaser(BlockLaser):
    def __init__(self, rig):
        super().__init__(rig)
        self.params = {"qcl": 1, "current_ma": 700., "pulse_rate_hz": 2.2e6, "pulse_width_ns": 120.}
        self.trigger = {"pulse_mode": 1, "process_trigger_mode": 1, "units": 2,
                        "start": 1940., "stop": 1940., "interval": 0.}
        self.marker_width = 100
        self.original = deepcopy((self.params, self.trigger, self.marker_width))
    def get_wavelength_trigger_pulse_width_us(self): return self.marker_width
    def set_wavelength_trigger_pulse_width_us(self, width):
        self.marker_width = width
        return width
    def set_wavelength_trigger_params(self, **kwargs):
        self.trigger = dict(kwargs)
        return dict(kwargs)
    def get_wavelength_trigger_channel_params(self, qcl):
        return {"channel": qcl, "units": 2, "start": self.trigger["start"], "stop": self.trigger["stop"],
                "interval": self.trigger["interval"], "num_triggers": self.rig.hf.marker_count}
    def start_sweep_scan(self, **kwargs):
        if self.emission:
            assert "sweep_settings_verified" in self.rig.trace
        self.sweep = kwargs
        super().start_sweep_scan(**kwargs)
        self.tuned = False
    def turn_emission_on(self, **kwargs):
        assert self.tuned, "MIRcatSDK_TurnEmissionOn returned 94 (LASER_NOT_TUNED)"
        super().turn_emission_on(**kwargs)
    def get_sweep_parameters(self):
        self.rig.trace.append("sweep_settings_verified")
        return {**self.sweep, "scan_rate_cm1_s": self.sweep["scan_rate_cm1_s"]
                if self.rig.fault != "unsupported_speed" else 2000.}


def regular_fixture(tmp_path, *, role="sample", fault=None, host_capacity_bytes=None, settings=None, prepared=True):
    caps = replace(HF2Capabilities(), device_id="dev1234", verified=True)
    plan = build_regular_phase_scan_plan(settings, capabilities=caps)
    rig = SimpleNamespace(units={}, running=False, trace=[], fail_stop=False, interlock=True,
                          fault=fault, cancel=Event())
    rig.hf = RegularHF(rig, plan)
    rig.hf.calls = rig.trace
    rig.laser = RegularLaser(rig)
    adapter = RegularPhaseScanAcquirer(plan, laser_factory=lambda **kw: rig.laser,
        hf_factory=lambda **kw: rig.hf, t660_factory=lambda name, **kw: RegularTimer(rig, name),
        tec_ready_stability_s=0., host_capacity_bytes=host_capacity_bytes)
    adapter.authorize(True)
    if prepared:
        adapter.prepare(plan.settings, SimpleNamespace(path=tmp_path), rig.cancel)
    events = [plan.event_at(i) for i in range(plan.total_scans)]
    if role == "blank": events = [replace(event, pump_enabled=False) for event in events]
    if role == "preliminary": events = events[:1]
    rig.hf.events = events
    return rig, adapter, events


def test_all_signed_blank_delays_match_pumped_sequence_and_use_250us():
    plan = build_regular_phase_scan_plan()
    assert plan.total_scans == 322
    for i in range(plan.total_scans):
        event = plan.event_at(i)
        pumped, duration = regular_event_timing(event)
        blank, blank_duration = regular_event_timing(replace(event, pump_enabled=False))
        assert pumped["channels"]["C"] == blank["channels"]["C"]
        assert duration == blank_duration and duration < plan.frame_period_s
        assert not any(blank["channels"][ch]["enabled"] for ch in "ABD")
        a, b = [float(pumped["channels"][ch]["delay"][:-1]) for ch in "AB"]
        assert b-a == pytest.approx(250e-6, abs=1e-12)


def test_t660_signed_frequency_readback_restores_with_explicit_hz(tmp_path, monkeypatch):
    rig, adapter, _ = regular_fixture(tmp_path, role="blank")
    for unit in rig.units.values():
        saved = deepcopy(adapter._original_timing[unit.name]["readback"])
        saved["queries"]["synth_frequency"] = {"ok": True, "response": "+002000000.000000"}
        monkeypatch.setattr(unit, "read_active_settings", lambda saved=saved: deepcopy(saved))
        adapter._before_timing_configuration(unit)
        resolved = adapter._original_timing[unit.name]
        assert resolved["readback"]["queries"]["synth_frequency"]["response"] == "+002000000.000000"
        assert resolved["safe_restore_recipe"]["clock"]["frequency"] == "2000000Hz"
    monkeypatch.undo()
    adapter.close()
    assert json.loads((tmp_path/"restoration.json").read_text())["settings_restored_and_outputs_inhibited"]


@pytest.mark.parametrize("setting_fault", [False, True])
def test_restore_retains_drifting_pll_center_but_checks_settings(tmp_path, monkeypatch, setting_fault):
    rig, adapter, _ = regular_fixture(tmp_path, role="blank")
    center = f"/{rig.hf.device_id}/plls/0/freqcenter"
    order = f"/{rig.hf.device_id}/plls/0/order"
    adapter._original_hf["nodes"][center] = {"type": "double", "value": 1957250.5983473577}
    export = rig.hf.export_settings_snapshot
    reload = rig.hf.reload_settings_snapshot

    def reload_without_observation(snapshot):
        assert center not in snapshot["nodes"]
        reload(snapshot)

    def drifting_readback(**kwargs):
        result = export(**kwargs)
        result["nodes"][center] = {"type": "double", "value": 1960521.700106419}
        if setting_fault:
            result["nodes"][order]["value"] += 1
        return result

    monkeypatch.setattr(rig.hf, "reload_settings_snapshot", reload_without_observation)
    monkeypatch.setattr(rig.hf, "export_settings_snapshot", drifting_readback)
    if setting_fault:
        with pytest.raises(RuntimeError, match="plls/0/order"):
            adapter.close()
    else:
        adapter.close()
    restored = json.loads((tmp_path/"restoration.json").read_text())
    assert restored["settings_restored_and_outputs_inhibited"] is not setting_fault
    comparison = restored["instruments"]["hf2li"]["comparison"]
    assert comparison["match"] is not setting_fault
    observation = comparison["external_reference_observations"][center]
    assert observation["before"]["value"] == 1957250.5983473577
    assert observation["after"]["value"] == 1960521.700106419


def test_regular_frames_reproduce_retained_successful_hardware_recipe():
    directory = Path(__file__).resolve().parents[2]/"evidence/experiments/runs/single_detector_ftir_20260906T203723_580408Z"
    path = directory/"full_phase_sample_10hz_01/Phase Scan/2026-09-06/20260906T234340_176401Z_run/acquisition_preflight.json"
    if not path.is_file():
        pytest.skip("Retained hardware evidence is not installed in this checkout")
    observed = json.loads(path.read_text())["timing_recipe"]
    plan = build_regular_phase_scan_plan()
    assert [regular_event_timing(plan.event_at(i))[0] for i in range(plan.total_scans)] == observed["frame_tables"][0]
    assert round(plan.frame_period_s*plan.settings.probe_repetition_rate_hz) == observed["frame_predivider"]


def test_tiny_span_rejected_before_connecting_any_instrument(tmp_path):
    caps = replace(HF2Capabilities(), verified=True)
    # The planner rejects this too. Deliberately tamper with a resolved plan
    # to verify the executor independently checks before opening devices.
    plan = replace(build_regular_phase_scan_plan(capabilities=caps),
                   settings=RegularPhaseScanSettings(stop_wavenumber_cm1=1999.9999),
                   scan_duration_s=1e-8)
    adapter = RegularPhaseScanAcquirer(plan)
    adapter.authorize(True)
    with pytest.raises(ValueError, match="shorter than two HF2LI detector sample"):
        adapter.prepare(plan.settings, SimpleNamespace(path=tmp_path), Event())
    assert adapter.qcl is adapter.hf is None and not adapter.units


@pytest.mark.parametrize("role,count", [("blank", 322), ("sample", 322), ("preliminary", 1)])
def test_regular_complete_sequence_deferred_native_read_and_restoration(tmp_path, role, count):
    rig, adapter, events = regular_fixture(tmp_path, role=role)
    blocks = adapter.prepare_blocks(adapter.plan, events, rig.cancel)
    assert len(blocks) == 1 and len(blocks[0]["events"]) == count
    assert blocks[0]["daq"].read_policy == "deferred"
    capacity = blocks[0]["daq"].capacity
    assert all(m["allocation_margin_fraction"] == 0 for m in capacity["modules"])
    assert capacity["required_bytes"] == sum(m["payload_bytes"] + m["metadata_bytes"] for m in capacity["modules"])
    raw, spectra = adapter.capture_block(blocks[0], rig.cancel)
    assert len(spectra) == count
    assert all(s.metadata["wavenumber_basis"] == "controller_markers" for _, s in spectra)
    assert all(s.reference_r is None for _, s in spectra)
    assert rig.laser.start_count == 2 and rig.laser.repetitions == count  # dark preflight + actual sequence
    assert rig.trace.count("emission_enable") == rig.trace.count("frames_start") == 1
    assert rig.trace.index("sweep_settings_verified") < rig.trace.index("emission_enable")
    assert rig.trace.index("t660_2_safe_stop") < rig.trace.index("daq_read")
    assert raw["labone"]["read_call_count"] == 3
    assert all(o["sequence_complete"] and not o["partial_salvage"] for o in raw["labone"]["read_phase_observations"])
    if role != "sample":
        assert all(s.pump_time_s is None for _, s in spectra)
        assert not any(f["channels"][ch]["enabled"] for f in blocks[0]["frames"] for ch in "AB")
    adapter.close()
    restored = json.loads((tmp_path/"restoration.json").read_text())
    assert restored["settings_restored_and_outputs_inhibited"]
    assert rig.laser.original == (rig.laser.params, rig.laser.trigger, rig.laser.marker_width)
    assert not rig.laser.emission and not rig.laser.armed
    assert all(unit.source == "OFF" for unit in rig.units.values())


@pytest.mark.parametrize("fault", ["cancel", "engine", "unsupported_speed", "count"])
def test_regular_abort_preserves_native_records_and_restores(tmp_path, fault):
    rig, adapter, events = regular_fixture(tmp_path, role="preliminary", fault=fault)
    block = adapter.prepare_blocks(adapter.plan, events, rig.cancel)[0]
    with pytest.raises((RuntimeError, InterruptedError)):
        adapter.capture_block(block, rig.cancel)
    partial = adapter.partial_blocks[0]
    assert partial["error"] and not partial["optical_valid"]
    if fault == "unsupported_speed":
        assert "emission_enable" not in rig.trace
        assert partial["labone"]["capture_not_started"]
    else:
        assert partial["labone"]["read_chunks"]
        assert all(o["partial_salvage"] for o in partial["labone"]["read_phase_observations"])
    adapter.close()
    assert not rig.laser.emission and not rig.laser.armed
    assert json.loads((tmp_path/"restoration.json").read_text())["settings_restored_and_outputs_inhibited"]


def test_table_upload_progress_is_throttled_and_precedes_actual_scan(tmp_path, monkeypatch):
    import control_app.workflows.phase_scan_acquisition as acquisition
    rig, adapter, events = regular_fixture(tmp_path, role="blank")
    block = adapter.prepare_blocks(adapter.plan, events, rig.cancel)[0]
    timer = rig.units["t660_2"]
    original = timer.preload_frame_table
    observations = []
    adapter.progress = lambda message: observations.append((message, rig.trace.count("emission_enable")))

    def preload(frames, *, progress, cancel_check, **kwargs):
        clock = [acquisition.monotonic()]
        with monkeypatch.context() as local:
            local.setattr(acquisition, "monotonic", lambda: clock[0])
            progress(0, len(frames))
            for count in range(1, len(frames)+1):
                cancel_check()
                clock[0] += .2
                progress(count, len(frames))
                cancel_check()
        return original(frames, **kwargs)

    monkeypatch.setattr(timer, "preload_frame_table", preload)
    raw, records = adapter.capture_block(block, rig.cancel)
    uploads = [(text, emission_count) for text, emission_count in observations if text.startswith("Loading timing table:")]
    assert 2 < len(uploads) < len(events)/2
    assert all(emission_count == 0 for _, emission_count in uploads)
    assert "0/322" in uploads[0][0] and "322/322" in uploads[-1][0]
    assert raw["timing_table_load"]["acknowledged_frames"] == 322
    messages = [text for text, _ in observations]
    scanning = next(text for text in messages if text.startswith("Scanning "))
    assert messages.index(scanning) > messages.index(uploads[-1][0])
    assert "0.0 s elapsed" in scanning and "nominal sequence 32.2 s" in scanning
    assert any(text.startswith("Sequence complete; retrieving") for text in messages)
    assert any(text.startswith("Processed 322 retrieved scans") for text in messages)
    assert len(records) == 322 and raw["labone"]["read_call_count"] == 3
    adapter.close()


def test_abort_during_table_upload_retains_load_progress_and_restores_before_emission(tmp_path, monkeypatch):
    rig, adapter, events = regular_fixture(tmp_path, role="blank")
    block = adapter.prepare_blocks(adapter.plan, events, rig.cancel)[0]

    def preload(frames, *, progress, cancel_check, **kwargs):
        progress(0, len(frames))
        progress(1, len(frames))
        rig.cancel.set()
        cancel_check()
        raise AssertionError("The next frame must not be uploaded")

    monkeypatch.setattr(rig.units["t660_2"], "preload_frame_table", preload)
    with pytest.raises(InterruptedError, match="aborted"):
        adapter.capture_block(block, rig.cancel)
    partial = adapter.partial_blocks[0]
    assert partial["timing_table_load"]["acknowledged_frames"] == 1
    assert partial["labone"]["capture_not_started"]
    assert "emission_enable" not in rig.trace and "frames_start" not in rig.trace
    assert not any(module.read_count for module in rig.hf.modules)
    adapter.close()
    assert json.loads((tmp_path/"restoration.json").read_text())["settings_restored_and_outputs_inhibited"]


def test_scan_progress_uses_elapsed_time_without_extra_counter_reads_or_native_transfer(tmp_path, monkeypatch):
    import control_app.workflows.phase_scan_acquisition as acquisition
    rig, adapter, events = regular_fixture(tmp_path, role="blank")
    block = adapter.prepare_blocks(adapter.plan, events, rig.cancel)[0]
    timer, messages = rig.units["t660_2"], []
    original_status, original_count = timer.get_frames_status, timer.get_shot_count
    calls = {"status": 0, "counter": 0}
    clock = [acquisition.monotonic()]

    def monotonic():
        clock[0] += 1.1
        return clock[0]

    def status():
        calls["status"] += 1
        return "RUNNING" if calls["status"] <= 4 else original_status()

    def counter():
        calls["counter"] += 1
        return original_count()

    monkeypatch.setattr(acquisition, "monotonic", monotonic)
    monkeypatch.setattr(timer, "get_frames_status", status)
    monkeypatch.setattr(timer, "get_shot_count", counter)
    adapter.progress = messages.append
    raw, records = adapter.capture_block(block, rig.cancel)
    updates = [message for message in messages if "controller running" in message]
    assert updates and all("elapsed; nominal sequence" in message for message in updates)
    assert calls["counter"] == 2  # Established before/after verification only.
    assert raw["labone"]["read_call_count"] == 3
    assert all(observation["sequence_complete"] for observation in raw["labone"]["read_phase_observations"])
    adapter.close()


def test_full_sequence_memory_preflight_does_not_split_or_emit(tmp_path):
    rig, adapter, events = regular_fixture(tmp_path, host_capacity_bytes=1024)
    with pytest.raises(AcquisitionCapacityError, match="host bytes"):
        adapter.prepare_blocks(adapter.plan, events, rig.cancel)
    assert not any(m.executed for m in rig.hf.modules)
    assert not rig.laser.emission and not rig.laser.start_count
    adapter.close()


def test_regular_memory_preflight_uses_available_ram_not_advisory_budget(tmp_path, monkeypatch):
    import control_app.workflows.regular_phase_scan_acquisition as acquisition
    rig, adapter, events = regular_fixture(tmp_path)
    adapter.max_retained_bytes = 1
    monkeypatch.setattr(acquisition, "available_host_memory_bytes", lambda: 4_000_000_000)
    blocks = adapter.prepare_blocks(adapter.plan, events, rig.cancel)
    assert blocks[0]['estimated_bytes'] > adapter.max_retained_bytes
    adapter.close()


def test_user_cadence_and_scan_speed_drive_one_whole_sequence(tmp_path):
    settings = RegularPhaseScanSettings(pump_repetition_rate_hz=5., scan_speed_cm1_s=5000., phase_delay_us=1000.)
    rig, adapter, events = regular_fixture(tmp_path, settings=settings)
    blocks = adapter.prepare_blocks(adapter.plan, events, rig.cancel)
    raw, records = adapter.capture_block(blocks[0], rig.cancel)
    assert len(blocks) == 1 and len(records) == len(events) > 16
    assert rig.laser.sweep["scan_rate_cm1_s"] == 5000.
    assert adapter.preparation_readback["effective_pump_repetition_rate_hz"] == 5.
    preflight = json.loads((tmp_path/"acquisition_preflight.json").read_text())
    assert preflight["timing_recipe"]["frame_predivider"] == 400000
    assert raw["labone"]["read_call_count"] == 3
    adapter.close()


def test_deferred_daq_cannot_be_drained_before_sequence_completion():
    hf = FakeHF(nominal_events())
    daq = FinitePhaseDAQ(hf, events=hf.events, duration_s=.0026, pretrigger_s=.0001,
                        read_policy="deferred", max_events=322)
    daq.arm()
    with pytest.raises(AcquisitionIntegrityError, match="deferred"):
        daq.drain()
    assert not any(m.read_count for m in hf.modules)
    daq.drain(partial=True)
    assert all(m.read_count == 1 for m in hf.modules)
    daq.close()


def test_readback_getters_use_documented_abi_without_starting_scan():
    class SDK:
        def __init__(self): self.calls = []
        def reading(self, value, unit, result):
            cast(value, POINTER(c_float)).contents.value = result
            cast(unit, POINTER(c_uint8)).contents.value = 2
            return 0
        def MIRcatSDK_GetSweepStartWW(self, value, unit): return self.reading(value, unit, 2000.)
        def MIRcatSDK_GetSweepStopWW(self, value, unit): return self.reading(value, unit, 1900.)
        def MIRcatSDK_GetSweepScanSpeed(self, value, unit): return self.reading(value, unit, 10000.)
        def MIRcatSDK_GetSweepNumScans(self, value):
            assert type(value._obj) is c_uint16
            cast(value, POINTER(c_uint16)).contents.value = 322
            return 0
    service = MircatService({})
    service._sdk = SDK()
    result = service.get_sweep_parameters()
    assert result["scan_rate_cm1_s"] == 10000 and result["repetitions"] == 322
    service._sdk = SimpleNamespace()
    with pytest.raises(MircatConfigurationError, match="does not provide"):
        service.get_sweep_parameters()
