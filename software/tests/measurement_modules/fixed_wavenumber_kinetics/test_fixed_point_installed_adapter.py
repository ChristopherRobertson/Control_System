"""Installed API path exercised with owned injected services, never hardware."""
from copy import deepcopy
from types import SimpleNamespace
from dataclasses import replace
import threading

import pytest

from control_app.measurement_host import ContextFactory
from control_app.measurement_host.ownership import HardwareCoordinator, require_hardware_owner
from control_app.measurement_modules.fixed_wavenumber_kinetics.planner import build_plan
from control_app.measurement_modules.fixed_wavenumber_kinetics.runner import Runner
from control_app.measurement_modules.fixed_wavenumber_kinetics.simulation import SimulatedDevices, simulation_profile


class Owned:
    def touch(self, action):
        require_hardware_owner(self)
        self.calls.append(action)


class Timing(Owned):
    def __init__(self, state, name):
        self.state, self.name, self.calls = state, name, []
        self.source = "OFF"
        self.synth_frequency_hz, self.predivider = 100000., 1
        self.channels = {c: False for c in "ABCD"}
        self.channel_settings = {c: {"delay": "200us" if name == "t660_2" and c == "B" else "0s",
            "width": "10us" if name == "t660_2" else "150ns",
            "polarity": "positive", "termination": "50OHM"} for c in "ABCD"}
        self.references = {e: e-1 if e % 2 == 0 else 0 for e in range(1, 9)}
        self.modes = {c: "DW" for c in "ABCD"}
        self.absolute = {0: 0.}
        for i, c in enumerate("ABCD"):
            self.absolute[2*i+1] = 200e-6 if name == "t660_2" and c == "B" else 0.
            self.absolute[2*i+2] = self.absolute[2*i+1]+(10e-6 if name == "t660_2" else 150e-9)
        self.recipe = {}
    def connect(self): self.touch("connect")
    def close(self): self.touch("close")
    def set_trigger_source(self, value): self.touch("source"); self.source = value
    def force_eod(self): self.touch("force_eod")
    def disable_channel(self, channel): self.touch("channel_off"); self.channels[channel] = False
    def command(self, value, **kwargs):
        self.touch(value)
        if value.startswith("TIME:RELTo"):
            if value.endswith("?"):
                return str(self.references[int(value.removeprefix("TIME:RELTo")[:-1])])
            assert self.source == "OFF" and not any(self.channels.values())
            edge, reference = map(int, value.removeprefix("TIME:RELTo").split())
            channel = "ABCD"[(edge-1)//2]
            if self.state.get("ignore_reference_restore") != (edge, reference):
                if edge % 2 or self.modes[channel] == "RF":
                    self.references[edge] = reference
        if value.startswith("TIME:DEL") and value.endswith("?"):
            edge = int(value.removeprefix("TIME:DEL")[:-1])
            return f"{self.absolute[edge]-self.absolute[self.references[edge]]:.12g}s"
        return "OK"
    def set_channel_timing_mode(self, channel, mode):
        self.touch("timing_mode")
        assert self.source == "OFF" and not any(self.channels.values())
        self.modes[channel] = "DW" if mode in {"DW", "delay_width"} else "RF"
        if self.modes[channel] == "DW":
            rising = 2*"ABCD".index(channel)+1
            self.references[rising+1] = rising
    def apply_recipe(self, recipe):
        from control_app.measurement_modules.fixed_wavenumber_kinetics.adapters import _physical_number
        self.touch("apply_recipe")
        self.recipe = recipe
        self.__dict__.setdefault("recipes", []).append(deepcopy(recipe))
        if recipe.get("clock", {}).get("frequency") is not None:
            self.synth_frequency_hz = _physical_number(recipe["clock"]["frequency"])
        self.predivider = recipe.get("predivider", self.predivider)
        self.channels = {c: v["enabled"] for c, v in recipe["channels"].items()}
        for c, row in recipe["channels"].items():
            self.channel_settings[c].update({k: row[k] for k in ("delay", "width", "polarity", "termination")})
            rising = 2*"ABCD".index(c)+1
            self.modes[c] = "DW"
            self.references[rising+1] = rising
            self.absolute[rising] = self.absolute[self.references[rising]]+_physical_number(row["delay"])
            self.absolute[rising+1] = self.absolute[rising]+_physical_number(row["width"])
    def start_continuous_clock(self): self.touch("start_clock"); self.source = "SYN"
    def read_active_settings(self):
        self.touch("readback")
        return {"queries": {"trigger_source": {"ok": True, "response": self.source},
            "synth_frequency": {"ok": True, "response": str(self.synth_frequency_hz)},
            "predivider": {"ok": True, "response": str(self.predivider)},
            "clock_connector_mode": {"ok": True, "response": "OUT" if self.name == "t660_2" else "IN"},
            "clock_lock_status": {"ok": True, "response": "LOCKED"}},
            "channels": {c: {"enabled": {"ok": True, "response": "ON" if on else "OFF"},
                "timing_mode": {"ok": True, "response": self.modes[c]},
                "delay_edge": {"ok": True, "response": self.command(f"TIME:DEL{2*'ABCD'.index(c)+1}?")},
                "width_edge": {"ok": True, "response": self.command(f"TIME:DEL{2*'ABCD'.index(c)+2}?")},
                "polarity": {"ok": True, "response": "POS" if self.channel_settings[c]["polarity"] == "positive" else "NEG"},
                "termination": {"ok": True, "response": "ON" if self.channel_settings[c]["termination"] == "50OHM" else "OFF"}}
                for c,on in self.channels.items()}}
    def preload_frame_table(self, frames, *, predivider, input_frequency_hz, progress, cancel_check):
        self.touch("pending_upload")
        assert self.source == "OFF"
        for i, c in enumerate("ABCD"):
            self.set_channel_timing_mode(c, "DW")
            self.command(f"TIME:RELTo{2*i+1} 0")
        self.frames = frames
        self.predivider = predivider
        self.period = predivider/input_frequency_hz
        for n in range(len(frames)+1): cancel_check(); progress(n, len(frames))
        return {"physical_frame_count": len(frames), "predivider": predivider}
    def start_frame_table(self):
        self.touch("start_frames")
        assert self.state["core"].read_count >= 1, "pump started before actual stationary baseline"
        offsets = [f["offset_s"]+float(f["channels"]["B"]["delay"][:-1]) for f in self.frames if f["channels"]["B"]["enabled"]]
        self.state["core"].start_event({"frames": self.frames, "pump_command_offsets_s": offsets})
    def get_frames_status(self):
        self.touch("frames_status")
        self.channel_settings = deepcopy(self.frames[-1]["channels"])
        self.channels = {c: row["enabled"] for c, row in self.channel_settings.items()}
        for i, c in enumerate("ABCD"):
            self.absolute[2*i+1] = float(self.channel_settings[c]["delay"][:-1])
            self.absolute[2*i+2] = self.absolute[2*i+1]+float(self.channel_settings[c]["width"][:-1])
        self.terminal_b_delay = self.channel_settings["B"]["delay"]
        return "DONE"
    def get_shot_count(self): self.touch("shot_count"); return len(self.frames)


def _inject_relative_timing(monkeypatch, *, cyclic=False):
    original = Timing.__init__
    def initialize(self, state, name):
        original(self, state, name)
        if name == "t660_2":
            self.references[3] = 1
            self.modes["B"] = "RF"
            self.references[4] = 2
            if cyclic:
                self.references[1] = 3
            self.original_references = deepcopy(self.references)
            self.original_modes = deepcopy(self.modes)
            self.original_absolute = deepcopy(self.absolute)
    monkeypatch.setattr(Timing, "__init__", initialize)


@pytest.mark.parametrize("mode", ["single", "dual"])
@pytest.mark.parametrize("cyclic", [False, True])
def test_fixed_point_restores_full_relative_timing_topology(tmp_path, monkeypatch, mode, cyclic):
    _inject_relative_timing(monkeypatch, cyclic=cyclic)
    fixture = build_connected_fixture(tmp_path, mode)
    operation = fixture.context.begin_operation(settings=fixture.settings.to_dict(), hardware=True)
    result = Runner(fixture.context).run(operation, fixture.plan)
    pump = fixture.state["services"]["t660_2"]
    assert result["status"] == "complete", result.get("error", result.get("cleanup_error"))
    assert pump.references == pump.original_references
    assert pump.modes == pump.original_modes
    assert pump.absolute == pytest.approx(pump.original_absolute)
    before = result["initial_states"]["t660_2"]
    assert int(before["edge_references"]["3"]["response"]) == 1
    assert before["channels"]["B"]["timing_mode"]["response"] == "RF"
    assert before["absolute_channel_timing"]["B"]["width_s"] == pytest.approx(10e-6)
    assert result["plan"]["resolved"]["timing"]["q_switch_delay_s"] == pytest.approx(200e-6)
    assert pump.source == "OFF" and not any(pump.channels.values())


def test_fixed_point_reference_restoration_mismatch_prevents_safe_claim(tmp_path, monkeypatch):
    _inject_relative_timing(monkeypatch)
    status = Timing.get_frames_status
    def ignore_restoration(self):
        value = status(self)
        self.state["ignore_reference_restore"] = (3, 1)
        return value
    monkeypatch.setattr(Timing, "get_frames_status", ignore_restoration)
    fixture = build_connected_fixture(tmp_path)
    operation = fixture.context.begin_operation(settings=fixture.settings.to_dict(), hardware=True)
    result = Runner(fixture.context).run(operation, fixture.plan)
    assert result["status"] == "cleanup_failed"
    assert "reference restoration mismatch" in result["cleanup_error"]
    assert not result["restoration"]["safe_verified"] and result["preservation_verified"]
    assert (operation.output_path/"run.json").exists()


def test_fixed_point_cyclic_reference_common_offset_is_not_false_restoration(tmp_path, monkeypatch):
    _inject_relative_timing(monkeypatch, cyclic=True)
    command = Timing.command
    def corrupt_absolute_restoration(self, value, **kwargs):
        response = command(self, value, **kwargs)
        if self.name == "t660_2" and value == "TIME:RELTo8 7" and "frames_status" in self.calls:
            # This changes neither references nor any raw relative readback in
            # the A/B cycle. Only an absolute inhibited check detects it.
            for edge in (1, 2, 3, 4):
                self.absolute[edge] += 100e-9
        return response
    monkeypatch.setattr(Timing, "command", corrupt_absolute_restoration)
    fixture = build_connected_fixture(tmp_path)
    operation = fixture.context.begin_operation(settings=fixture.settings.to_dict(), hardware=True)
    result = Runner(fixture.context).run(operation, fixture.plan)
    assert result["status"] == "cleanup_failed"
    assert "absolute delay_s restoration mismatch" in result["cleanup_error"]
    assert not result["restoration"]["safe_verified"] and result["preservation_verified"]


def test_fixed_point_read_only_reference_snapshot_does_not_modify_live_basis(tmp_path, monkeypatch):
    _inject_relative_timing(monkeypatch)
    connect = Timing.connect
    def connected_with_existing_output(self):
        connect(self)
        if self.name == "t660_2":
            self.source = "SYN"
            self.channels["A"] = True
    monkeypatch.setattr(Timing, "connect", connected_with_existing_output)
    fixture = build_connected_fixture(tmp_path)
    operation = fixture.context.begin_operation(settings=fixture.settings.to_dict(), hardware=True)
    profile = Runner(fixture.context).discover(operation, fixture.settings)
    pump = fixture.state["services"]["t660_2"]
    assert pump.references == pump.original_references and pump.modes == pump.original_modes
    assert not any(call.startswith("TIME:RELTo") and not call.endswith("?") for call in pump.calls)
    assert "timing_mode" not in pump.calls
    assert pump.source == "SYN" and pump.channels["A"]
    assert profile["timing"]["q_switch_width_s"] == pytest.approx(10e-6)


def test_fixed_point_reference_query_failure_inhibits_without_inventing_restoration(tmp_path, monkeypatch):
    command = Timing.command
    def failed_reference(self, value, **kwargs):
        if value == "TIME:RELTo3?":
            self.touch(value)
            raise RuntimeError("Injected missing edge-reference readback")
        return command(self, value, **kwargs)
    monkeypatch.setattr(Timing, "command", failed_reference)
    fixture = build_connected_fixture(tmp_path)
    operation = fixture.context.begin_operation(settings=fixture.settings.to_dict(), hardware=True)
    result = Runner(fixture.context).run(operation, fixture.plan)
    pump = fixture.state["services"]["t660_2"]
    assert result["status"] == "cleanup_failed"
    assert "missing edge-reference readback" in result["error"]
    assert fixture.state["core"].dispatched == 0
    assert pump.source == "OFF" and not any(pump.channels.values())
    assert not result["restoration"]["safe_verified"]
    assert result["preservation_verified"] and (operation.output_path/"run.json").exists()
    import json
    saved = json.loads((operation.output_path/"run.json").read_text(encoding="utf-8"))
    before = saved["initial_states"]["t660_2"]
    assert before["channels"]["B"]["delay_edge"]["response"] == "0.0002s"
    assert set(before["edge_references"]) == {"1", "2"}


class Mircat(Owned):
    def __init__(self):
        self.calls=[]; self.armed=False; self.emission=False; self.wavenumber=1930.
        self.pulses = {}
    def pulse(self, qcl):
        return self.pulses.setdefault(qcl, {"pulse_rate_hz":110000., "pulse_width_ns":150.})
    def initialize(self): self.touch("initialize")
    def deinitialize(self): self.touch("deinitialize")
    def read_state(self): self.touch("state"); return SimpleNamespace(to_dict=lambda: {"emission_on": self.emission})
    def turn_emission_off(self): self.touch("off"); self.emission=False
    def start_emission(self): self.touch("on"); self.emission=True
    def qcl_call(self, method, qcl):
        self.touch(method)
        self.__dict__.setdefault("qcl_calls", []).append((method, qcl))
    def get_qcl_pulse_rate(self, qcl): self.qcl_call("rate", qcl); return self.pulse(qcl)["pulse_rate_hz"]
    def get_qcl_pulse_width(self, qcl): self.qcl_call("width", qcl); return self.pulse(qcl)["pulse_width_ns"]
    def get_active_qcl(self): self.touch("active_qcl"); return 1
    def get_num_installed_qcls(self): self.touch("qcl_count"); return 1
    def get_qcl_tuning_range(self, qcl): self.qcl_call("qcl_range", qcl); return {"qcl": qcl, "min_cm1": 1800., "max_cm1": 2100.}
    def get_qcl_pulse_limits(self, qcl): self.qcl_call("pulse_limits", qcl); return {"max_pulse_rate_hz": 3000000., "max_pulse_width_ns": 500., "max_duty_cycle": 30.}
    def get_wavelength_trigger_params(self): self.touch("trigger_read"); return dict(pulse_mode=1,process_trigger_mode=1,start=1930.,stop=1930.,interval=0.,units=1,dwell_us=0,after_off_us=0)
    def set_wavelength_trigger_params(self, **kwargs): self.touch("trigger_set"); return kwargs
    def set_qcl_pulse_params(self, **kwargs):
        self.qcl_call("pulse", kwargs["qcl"])
        self.__dict__.setdefault("pulse_writes", []).append(deepcopy(kwargs))
        self.pulse(kwargs["qcl"]).update({k:kwargs[k] for k in ("pulse_rate_hz", "pulse_width_ns")})
        return kwargs
    def set_external_trigger_params(self, **kwargs): self.touch("external")
    def is_interlock_set(self): self.touch("interlock"); return True
    def is_key_switch_set(self): self.touch("key"); return True
    def are_tecs_ready(self): self.touch("TEC"); return True
    def arm(self): self.touch("arm"); self.armed=True
    def disarm(self): self.touch("disarm"); self.armed=False
    def is_laser_armed(self): self.touch("armed"); return self.armed
    def is_emission_on(self): self.touch("emission"); return self.emission
    def tune_to_wavenumber(self, value, *, qcl): self.qcl_call("tune", qcl); self.wavenumber=value
    def is_tuned(self): self.touch("tuned"); return True
    def get_actual_wavelength(self): self.touch("actual"); return {"value": self.wavenumber,"units":"cm^-1","light_valid":True}
    def cancel_manual_tune(self): self.touch("cancel_tune")
    def stop_scan_if_needed(self): self.touch("stop_scan")


class HF2(Owned):
    device_id="devINJECTED"
    def __init__(self, state):
        self.state=state; self.calls=[]; self.nodes={}
        for i in range(6):
            for key in ("enable","adcselect","oscselect","harmonic","order","timeconstant","rate","trigger"):
                initial = {"order":1,"timeconstant":.001,"rate":10000. if i == 2 else 1000.,"harmonic":1}.get(key,0)
                self.nodes[f"/{self.device_id}/demods/{i}/{key}"]={"value":initial,"type":"double"}
        for i in (0,1):
            for key in ("ac","imp50","diff","range"):
                self.nodes[f"/{self.device_id}/sigins/{i}/{key}"]={"value":1. if key == "range" else 0,"type":"double"}
        for key,value in {"order":1,"adcthreshold":0}.items():
            self.nodes[f"/{self.device_id}/plls/0/{key}"]={"value":value,"type":"int"}
    def connect(self): self.touch("connect")
    def close(self): self.touch("close")
    def sync(self): self.touch("sync")
    def export_settings_snapshot(self, *, preset=None): self.touch("snapshot"); return {"nodes":deepcopy(self.nodes),"read_errors":{}}
    def configure_signal_inputs(self, values): self.touch("inputs")
    def configure_pll(self, values): self.touch("PLL"); self.configured_pll = deepcopy(values)
    def configure_demodulators(self, values):
        self.touch("demods")
        for row in values:
            for k,v in row.items():
                if k == "index": continue
                key={"rate_sps":"rate","timeconstant_s":"timeconstant"}.get(k,k)
                self.nodes[f"/{self.device_id}/demods/{row['index']}/{key}"]={"value":v,"type":"double"}
        core = self.state.get("core")
        if core is not None:
            for role,index in (("sample",0),("reference",3)):
                if role in core.resolved:
                    for field,node in (("rate_sps","rate"),("timeconstant_s","timeconstant"),("order","order")):
                        core.resolved[role][field] = self.nodes[f"/{self.device_id}/demods/{index}/{node}"]["value"]
            core.resolved["timing_rate_sps"] = self.nodes[f"/{self.device_id}/demods/2/rate"]["value"]
    def get_clockbase(self): self.touch("clockbase"); return 210000000
    def read_acquisition_health(self, *, reference_pll, input_indices):
        self.touch("health")
        faults = self.state["core"].faults
        return {"reference_locked":not faults.get("health_unlocked",False),"clock_locked":True,
            "external_clock_selected":True,"overload":bool(faults.get("health_overload",False)),"read_errors":{}}
    def start_acquisition(self, *, demodulators, fields): self.touch("subscribe"); self.state["core"].start_stream()
    def read_acquisition(self, duration_s):
        self.touch("poll")
        chunk=self.state["core"].read(duration_s)
        return {"data": {f"/{self.device_id}/demods/{index}/sample":chunk[role] for role,index in (("sample",0),("reference",3),("timing",2)) if role in chunk},"timestamp_utc":"2026-09-09T00:00:00Z"}
    def stop_acquisition(self): self.touch("unsubscribe"); self.state["core"].stop_stream()
    def reload_settings_snapshot(self, before): self.touch("restore"); self.nodes=deepcopy(before["nodes"])
    def compare_settings_snapshots(self, before, after): self.touch("verify_restore"); return {"match":before==after}


def build_connected_fixture(tmp_path, mode="dual", *, faults=None):
    """Fresh owned service transports per operation, with no calibration/profile files."""
    from control_app.measurement_modules.fixed_wavenumber_kinetics.settings import Settings, Position
    state = {"services": {}, "operations": []}
    configuration = {"fixed_point_simulation": faults or {}}
    def factory(name):
        def create(*, configuration):
            if name == "t660_2":
                core = SimulatedDevices(SimpleNamespace(mode="dual"), SimpleNamespace(hardware=False, configuration=configuration))
                core.configure(simulation_profile("dual")["configuration"]["fixed_wavenumber_kinetics"], lambda:None)
                state["core"] = core
                state["services"] = {}
                state["operations"].append(state["services"])
            service = Timing(state,name) if name.startswith("t660") else (Mircat() if name == "mircat" else HF2(state))
            state["services"][name] = service
            return service
        return create
    context_factory = ContextFactory(configuration_provider=lambda:configuration,
        real_device_factories={name:factory(name) for name in ("t660_1","t660_2","mircat","hf2li")},
        save_root_provider=lambda:tmp_path, ownership=HardwareCoordinator(tmp_path/"exclusive.lock"))
    context = context_factory.for_experiment("fixed_wavenumber_kinetics").for_mode(mode)
    settings = Settings(mode=mode, positions=(Position(1930.),), pre_observation_s=.2,
        post_observation_s=3., chunk_duration_s=.2)
    return SimpleNamespace(context_factory=context_factory, context=context, settings=settings,
        plan=build_plan(settings), state=state, configuration=configuration)


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_fixed_point_installed_services_complete_under_host_ownership(tmp_path, mode):
    fixture = build_connected_fixture(tmp_path, mode)
    context, plan = fixture.context, fixture.plan
    assert plan.ready and not plan.operational_ready
    operation=context.begin_operation(settings=fixture.settings.to_dict(),hardware=True)
    result=Runner(context).run(operation,plan)
    services,core=fixture.state["services"],fixture.state["core"]
    assert result["status"]=="complete",result.get("error",result.get("cleanup_error",result.get("analysis_error")))
    assert result["restoration"]["safe_verified"] and result["preservation_verified"]
    assert core.dispatched==1
    assert "pending_upload" in services["t660_2"].calls
    assert "health" in services["hf2li"].calls and "verify_restore" in services["hf2li"].calls
    assert result["live_readbacks"]["source_kind"] == "connected_readbacks"
    assert result["plan"]["resolved"]["sample"]["rate_sps"] == 1000.
    assert result["settings"]["sample_id"] == ""
    # Release occurred only after native_run and final analyzed run were written.
    with pytest.raises(Exception): services["hf2li"].sync()


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_fixed_point_connected_check_is_read_only_and_preserved(tmp_path, mode):
    fixture = build_connected_fixture(tmp_path, mode)
    operation = fixture.context.begin_operation(settings=fixture.settings.to_dict(),hardware=True)
    profile = Runner(fixture.context).discover(operation,fixture.settings)
    assert profile["sample"]["rate_sps"] == 1000.
    assert "supported" not in profile or profile["supported"] == {}
    for service in fixture.state["services"].values():
        assert not {"source","channel_off","off","on","apply_recipe","inputs","PLL","demods","arm","tune"}.intersection(service.calls)
    assert (operation.output_path/"run.json").exists()


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_fixed_point_optional_controls_then_direct_run_use_fresh_services(tmp_path, mode):
    fixture = build_connected_fixture(tmp_path, mode)
    for kind in ("blank","preliminary","measurement"):
        operation=fixture.context.begin_operation(settings=fixture.settings.to_dict(),hardware=True)
        result=Runner(fixture.context).run(operation,fixture.plan,kind=kind)
        assert result["status"] == "complete", result.get("error")
        assert fixture.state["core"].dispatched == (1 if kind == "measurement" else 0)
    assert len(fixture.state["operations"]) == 3


@pytest.mark.parametrize("mode", ["single", "dual"])
@pytest.mark.parametrize("fault", ["health_unlocked", "health_overload"])
def test_fixed_point_real_health_fault_preserves_owned_cleanup(tmp_path, mode, fault):
    fixture = build_connected_fixture(tmp_path,mode,faults={fault:True})
    operation=fixture.context.begin_operation(settings=fixture.settings.to_dict(),hardware=True)
    result=Runner(fixture.context).run(operation,fixture.plan)
    assert result["status"] == "failed"
    assert fixture.state["core"].dispatched == 0
    assert result["restoration"]["safe_verified"] and result["preservation_verified"]


@pytest.mark.parametrize("mode", ["single", "dual"])
@pytest.mark.parametrize("stage", ["acknowledged timing-table upload", "acquisition"])
def test_fixed_point_real_abort_retains_native_and_restores(tmp_path, mode, stage):
    fixture = build_connected_fixture(tmp_path,mode)
    operation=fixture.context.begin_operation(settings=fixture.settings.to_dict(),hardware=True)
    cancel=threading.Event()
    result=Runner(fixture.context).run(operation,fixture.plan,cancel=cancel,
        progress=lambda event:cancel.set() if event["stage"] == stage else None)
    assert result["status"] == "stopped"
    assert result["restoration"]["safe_verified"] and result["preservation_verified"]
    assert (operation.output_path/"run.json").exists()


def test_fixed_point_real_cleanup_failure_has_precedence(tmp_path, monkeypatch):
    fixture = build_connected_fixture(tmp_path)
    def fail_disarm(self):
        self.touch("disarm")
        raise RuntimeError("Injected disarm failure")
    monkeypatch.setattr(Mircat,"disarm",fail_disarm)
    operation=fixture.context.begin_operation(settings=fixture.settings.to_dict(),hardware=True)
    result=Runner(fixture.context).run(operation,fixture.plan)
    assert result["status"] == "cleanup_failed"
    assert "Injected disarm failure" in result["cleanup_error"]
    assert result["preservation_verified"]


def test_fixed_point_actual_settings_change_ignores_stale_optional_blank(tmp_path):
    fixture = build_connected_fixture(tmp_path,"single")
    operation=fixture.context.begin_operation(settings=fixture.settings.to_dict(),hardware=True)
    blank=Runner(fixture.context).run(operation,fixture.plan,kind="blank")
    settings=replace(fixture.settings,sample_timeconstant_s=.002)
    plan=build_plan(settings)
    operation2=fixture.context.begin_operation(settings=settings.to_dict(),hardware=True)
    result=Runner(fixture.context).run(operation2,plan,blank=blank)
    assert result["status"] == "complete",result.get("error")
    assert result["optional_record_notes"]
    assert "blank" not in result["analysis_inputs"]
    assert result["plan"]["resolved"]["sample"]["timeconstant_s"] == .002


def test_fixed_point_terminal_frame_does_not_replace_next_run_pump_readbacks(tmp_path):
    fixture = build_connected_fixture(tmp_path)
    operation = fixture.context.begin_operation(settings=fixture.settings.to_dict(), hardware=True)
    result = Runner(fixture.context).run(operation, fixture.plan)
    pump = fixture.state["services"]["t660_2"]
    assert result["status"] == "complete", result.get("cleanup_error")
    assert float(pump.terminal_b_delay[:-1]) == 0.
    assert pump.channel_settings["B"]["delay"] == "0.0002s"
    assert pump.source == "OFF" and not any(pump.channels.values())
    assert pump.recipe["frames_engine"] is False
    restored = [r for r in result["restoration"]["actions"] if r["action"] == "t660_2 inactive timing restoration"]
    assert restored and restored[0]["ok"]


@pytest.mark.parametrize("mode", ["single", "dual"])
@pytest.mark.parametrize("divider", [0, 1, 2])
def test_fixed_point_distinct_mircat_internal_and_external_rates_persist_across_operations(tmp_path, monkeypatch, mode, divider):
    persistent_pulses = {1: {"pulse_rate_hz": 2300000., "pulse_width_ns": 100.}}
    original_init = Mircat.__init__
    def persistent_init(service):
        original_init(service)
        service.pulses = persistent_pulses
    monkeypatch.setattr(Mircat, "__init__", persistent_init)
    original_read = Timing.read_active_settings
    def two_mhz_read(service):
        state = original_read(service)
        state["queries"]["synth_frequency"]["response"] = "2000000Hz"
        state["queries"]["predivider"]["response"] = str(divider)
        return state
    monkeypatch.setattr(Timing, "read_active_settings", two_mhz_read)
    fixture = build_connected_fixture(tmp_path, mode)
    for _ in range(2):
        operation = fixture.context.begin_operation(settings=fixture.settings.to_dict(), hardware=True)
        result = Runner(fixture.context).run(operation, fixture.plan)
        assert result["status"] == "complete", result.get("error", result.get("cleanup_error"))
        assert result["live_readbacks"]["mircat"]["pulse_rate_hz"] == 2300000.
        assert result["plan"]["resolved"]["mircat"]["pulse_rate_hz"] == 2300000.
        assert result["plan"]["resolved"]["probe_recipe"]["clock"]["frequency"] == "2000000Hz"
        pulse = result["events"][0]["tuning"]["mircat_internal_pulse"]
        assert result["plan"]["resolved"]["probe_recipe"]["predivider"] == divider
        assert pulse["pulse_rate_hz"] == 2300000. and pulse["external_probe_rate_hz"] == 2000000./max(1, divider)
        assert persistent_pulses[1] == {"pulse_rate_hz": 2300000., "pulse_width_ns": 100.}
        assert result["restoration"]["safe_verified"] and result["preservation_verified"]


@pytest.mark.parametrize("rate,width,expected_error", [
    (100000., 150., "greater"), (3100000., 50., "rate"), (2300000., 200., "duty")])
def test_fixed_point_invalid_internal_pulse_configuration_fails_before_emission(tmp_path, monkeypatch, rate, width, expected_error):
    original_init = Mircat.__init__
    def configured_init(service):
        original_init(service)
        service.pulses = {1: {"pulse_rate_hz": rate, "pulse_width_ns": width}}
    monkeypatch.setattr(Mircat, "__init__", configured_init)
    fixture = build_connected_fixture(tmp_path, "dual")
    operation = fixture.context.begin_operation(settings=fixture.settings.to_dict(), hardware=True)
    result = Runner(fixture.context).run(operation, fixture.plan)
    assert result["status"] == "failed", result
    assert expected_error in result["error"].lower()
    assert "on" not in fixture.state["services"]["mircat"].calls
    assert fixture.state["core"].dispatched == 0
    assert result["restoration"]["safe_verified"] and result["preservation_verified"]


def test_fixed_point_external_mode_must_preserve_selected_internal_rate(tmp_path, monkeypatch):
    def resetting_external_mode(service, **kwargs):
        service.touch("external")
        service.pulse(1)["pulse_rate_hz"] = 100000.
    monkeypatch.setattr(Mircat, "set_external_trigger_params", resetting_external_mode)
    fixture = build_connected_fixture(tmp_path, "dual")
    operation = fixture.context.begin_operation(settings=fixture.settings.to_dict(), hardware=True)
    result = Runner(fixture.context).run(operation, fixture.plan)
    assert result["status"] == "failed"
    assert "greater" in result["error"].lower()
    assert "on" not in fixture.state["services"]["mircat"].calls
    assert fixture.state["services"]["mircat"].pulse(1)["pulse_rate_hz"] == 110000.
    assert result["restoration"]["safe_verified"] and result["preservation_verified"]


@pytest.mark.parametrize("ignored_reference,expected_status,error", [
    (0, "failed", "reference 0 not verified"),
    (3, "cleanup_failed", "original reference 3 not restored")])
def test_fixed_point_absolute_readback_requires_verified_reference_writes(tmp_path, monkeypatch, ignored_reference, expected_status, error):
    import json
    _inject_relative_timing(monkeypatch, cyclic=True)
    initialize = Timing.__init__
    def ignored_write(self, state, name):
        initialize(self, state, name)
        if name == "t660_2":
            state["ignore_reference_restore"] = (1, ignored_reference)
    monkeypatch.setattr(Timing, "__init__", ignored_write)
    fixture = build_connected_fixture(tmp_path)
    operation = fixture.context.begin_operation(settings=fixture.settings.to_dict(), hardware=True)
    result = Runner(fixture.context).run(operation, fixture.plan)
    assert result["status"] == expected_status
    assert error in result["error"]
    assert fixture.state["core"].dispatched == 0
    assert result["preservation_verified"]
    saved = json.loads((operation.output_path/"run.json").read_text(encoding="utf-8"))
    before = saved["initial_states"]["t660_2"]
    assert "absolute_channel_timing" not in before
    checks = before["absolute_reference_checks"]["1"]
    pump = fixture.state["services"]["t660_2"]
    assert pump.source == "OFF" and not any(pump.channels.values())
    if ignored_reference == 0:
        assert checks["absolute_delay_s"] is None and "delay_readback" not in checks
        assert int(checks["reference_for_absolute"]) == 3
        assert pump.references == pump.original_references
    else:
        assert int(checks["restored_reference"]) == 0
        assert not result["restoration"]["safe_verified"]


def _inject_stale_multi_qcl_metadata(monkeypatch):
    initialize = Mircat.__init__
    def old_active_channel(self):
        initialize(self)
        self.pulses = {1: {"pulse_rate_hz": 2300000., "pulse_width_ns": 100.},
            2: {"pulse_rate_hz": 700000., "pulse_width_ns": 300.}}
    def ranges(self, qcl):
        self.qcl_call("qcl_range", qcl)
        return {"qcl": qcl, "min_cm1": 1800. if qcl == 1 else 2150.,
            "max_cm1": 2100. if qcl == 1 else 2500.}
    def broad_state_must_not_select_active_qcl(self):
        raise AssertionError("Broad state snapshot would follow stale active QCL 2")
    monkeypatch.setattr(Mircat, "__init__", old_active_channel)
    monkeypatch.setattr(Mircat, "get_active_qcl", lambda self: self.touch("active_qcl") or 2)
    monkeypatch.setattr(Mircat, "get_num_installed_qcls", lambda self: self.touch("qcl_count") or 2)
    monkeypatch.setattr(Mircat, "get_qcl_tuning_range", ranges)
    monkeypatch.setattr(Mircat, "read_state", broad_state_must_not_select_active_qcl)


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_fixed_point_stale_qcl2_metadata_cannot_route_any_installed_operation(tmp_path, monkeypatch, mode):
    from control_app.measurement_modules.fixed_wavenumber_kinetics.adapters import InstalledDevices
    _inject_stale_multi_qcl_metadata(monkeypatch)
    stale = {"qcl": 2, "pulse_rate_hz": 700000., "pulse_width_ns": 300.}
    class LegacySelection(InstalledDevices):
        def configure(self, resolved, check):
            old = deepcopy(resolved)
            old["mircat"] = deepcopy(stale)
            old.setdefault("value_sources", {})["mircat.pulse_width_ns"] = "user_override"
            super().configure(old, check)
            # Historical selection metadata cannot redirect tune or cleanup.
            self.resolved["mircat"] = deepcopy(stale)
            self.resolved["qcl_ranges"] = [{"qcl": 2, "min_cm1": 1800., "max_cm1": 2500.}]
            self.before["mircat_extra_pulses"] = {"2": deepcopy(stale)}
    fixture = build_connected_fixture(tmp_path, mode)
    plan = fixture.plan.to_dict()
    plan["resolved"]["mircat"] = deepcopy(stale)
    operation = fixture.context.begin_operation(settings=fixture.settings.to_dict(), hardware=True)
    result = Runner(fixture.context, device_factory=LegacySelection).run(operation, plan)
    mircat = fixture.state["services"]["mircat"]
    assert result["status"] == "complete", result.get("error", result.get("cleanup_error"))
    assert {qcl for _, qcl in mircat.qcl_calls} == {1}
    assert not {"active_qcl", "qcl_count"}.intersection(mircat.calls)
    assert result["plan"]["resolved"]["mircat"] == {"qcl": 1, "pulse_rate_hz": 2300000., "pulse_width_ns": 100.}
    assert result["events"][0]["tuning"]["qcl"] == 1
    assert mircat.pulses[2] == {"pulse_rate_hz": 700000., "pulse_width_ns": 300.}
    assert all(row["qcl"] == 1 and row["pulse_rate_hz"] == 2300000. and row["pulse_width_ns"] == 100.
        for row in mircat.pulse_writes)
    assert result["restoration"]["safe_verified"]


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_fixed_point_all_positions_must_fit_qcl1_before_any_emission(tmp_path, monkeypatch, mode):
    from control_app.measurement_modules.fixed_wavenumber_kinetics.settings import Position
    _inject_stale_multi_qcl_metadata(monkeypatch)
    fixture = build_connected_fixture(tmp_path, mode)
    settings = replace(fixture.settings, positions=(Position(1930.), Position(2200.)), event_budget=2)
    operation = fixture.context.begin_operation(settings=settings.to_dict(), hardware=True)
    result = Runner(fixture.context).run(operation, build_plan(settings))
    mircat = fixture.state["services"]["mircat"]
    assert result["status"] == "failed" and "QCL 1 range" in result["error"]
    assert "on" not in mircat.calls and "tune" not in mircat.calls
    assert {qcl for _, qcl in mircat.qcl_calls} == {1}
    assert fixture.state["core"].dispatched == 0
    assert result["restoration"]["safe_verified"] and result["preservation_verified"]


def test_fixed_point_tune_rechecks_qcl1_range_before_emission(tmp_path, monkeypatch):
    _inject_stale_multi_qcl_metadata(monkeypatch)
    read_range = Mircat.get_qcl_tuning_range
    def changing_range(self, qcl):
        actual = read_range(self, qcl)
        if sum(method == "qcl_range" for method, _ in self.qcl_calls) >= 3:
            actual.update(min_cm1=1800., max_cm1=1920.)
        return actual
    monkeypatch.setattr(Mircat, "get_qcl_tuning_range", changing_range)
    fixture = build_connected_fixture(tmp_path)
    operation = fixture.context.begin_operation(settings=fixture.settings.to_dict(), hardware=True)
    result = Runner(fixture.context).run(operation, fixture.plan)
    mircat = fixture.state["services"]["mircat"]
    assert result["status"] == "failed" and "QCL 1 range" in result["error"]
    assert "on" not in mircat.calls and "tune" not in mircat.calls
    assert {qcl for _, qcl in mircat.qcl_calls} == {1}


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_fixed_point_changed_repetition_and_width_reach_qcl1_devices(tmp_path, monkeypatch, mode):
    _inject_stale_multi_qcl_metadata(monkeypatch)
    fixture = build_connected_fixture(tmp_path, mode)
    settings = replace(fixture.settings, probe_rate_hz=80000., probe_width_ns=120.)
    operation = fixture.context.begin_operation(settings=settings.to_dict(), hardware=True)
    result = Runner(fixture.context).run(operation, build_plan(settings))
    services = fixture.state["services"]
    assert result["status"] == "complete", result.get("error", result.get("cleanup_error"))
    pulse = result["events"][0]["tuning"]["mircat_internal_pulse"]
    assert pulse == {"qcl": 1, "pulse_rate_hz": 2300000., "pulse_width_ns": 120., "external_probe_rate_hz": 80000.}
    assert services["t660_1"].recipes[0]["clock"]["frequency"] == "80000Hz"
    assert services["hf2li"].configured_pll["freqcenter_hz"] == 80000.
    assert services["mircat"].pulse_writes[0] == {"qcl": 1, "pulse_rate_hz": 2300000., "pulse_width_ns": 120.}
    assert services["mircat"].pulse_writes[-1] == {"qcl": 1, "pulse_rate_hz": 2300000., "pulse_width_ns": 100.}
    assert services["t660_1"].synth_frequency_hz == 100000.
    assert result["restoration"]["safe_verified"]
