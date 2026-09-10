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
        self.channels = {c: False for c in "ABCD"}
        self.channel_settings = {c: {"delay": "200us" if name == "t660_2" and c == "B" else "0s",
            "width": "10us" if name == "t660_2" else "150ns",
            "polarity": "positive", "termination": "50OHM"} for c in "ABCD"}
        self.recipe = {}
    def connect(self): self.touch("connect")
    def close(self): self.touch("close")
    def set_trigger_source(self, value): self.touch("source"); self.source = value
    def force_eod(self): self.touch("force_eod")
    def disable_channel(self, channel): self.touch("channel_off"); self.channels[channel] = False
    def command(self, value, **kwargs): self.touch(value); return "OK"
    def apply_recipe(self, recipe):
        self.touch("apply_recipe")
        self.recipe = recipe
        self.channels = {c: v["enabled"] for c, v in recipe["channels"].items()}
        for c, row in recipe["channels"].items():
            self.channel_settings[c].update({k: row[k] for k in ("delay", "width", "polarity", "termination")})
    def start_continuous_clock(self): self.touch("start_clock"); self.source = "SYN"
    def read_active_settings(self):
        self.touch("readback")
        return {"queries": {"trigger_source": {"ok": True, "response": self.source},
            "synth_frequency": {"ok": True, "response": "100000"},
            "predivider": {"ok": True, "response": "1"},
            "clock_connector_mode": {"ok": True, "response": "OUT" if self.name == "t660_2" else "IN"},
            "clock_lock_status": {"ok": True, "response": "LOCKED"}},
            "channels": {c: {"enabled": {"ok": True, "response": "ON" if on else "OFF"},
                "delay_edge": {"ok": True, "response": self.channel_settings[c]["delay"]},
                "width_edge": {"ok": True, "response": self.channel_settings[c]["width"]},
                "polarity": {"ok": True, "response": "POS" if self.channel_settings[c]["polarity"] == "positive" else "NEG"},
                "termination": {"ok": True, "response": "ON" if self.channel_settings[c]["termination"] == "50OHM" else "OFF"}}
                for c,on in self.channels.items()}}
    def preload_frame_table(self, frames, *, predivider, input_frequency_hz, progress, cancel_check):
        self.touch("pending_upload")
        assert self.source == "OFF"
        self.frames = frames
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
        self.terminal_b_delay = self.channel_settings["B"]["delay"]
        return "DONE"
    def get_shot_count(self): self.touch("shot_count"); return len(self.frames)


class Mircat(Owned):
    def __init__(self): self.calls=[]; self.armed=False; self.emission=False; self.wavenumber=1930.
    def initialize(self): self.touch("initialize")
    def deinitialize(self): self.touch("deinitialize")
    def read_state(self): self.touch("state"); return SimpleNamespace(to_dict=lambda: {"emission_on": self.emission})
    def turn_emission_off(self): self.touch("off"); self.emission=False
    def start_emission(self): self.touch("on"); self.emission=True
    def get_qcl_pulse_rate(self, qcl): self.touch("rate"); return 100000.
    def get_qcl_pulse_width(self, qcl): self.touch("width"); return 150.
    def get_active_qcl(self): self.touch("active_qcl"); return 1
    def get_num_installed_qcls(self): self.touch("qcl_count"); return 1
    def get_qcl_tuning_range(self, qcl): self.touch("qcl_range"); return {"qcl": qcl, "min_cm1": 1800., "max_cm1": 2100.}
    def get_qcl_pulse_limits(self, qcl): self.touch("pulse_limits"); return {"min_pulse_width_ns": 40., "max_pulse_width_ns": 500., "max_duty_cycle_percent": 30.}
    def get_wavelength_trigger_params(self): self.touch("trigger_read"); return dict(pulse_mode=1,process_trigger_mode=1,start=1930.,stop=1930.,interval=0.,units=1,dwell_us=0,after_off_us=0)
    def set_wavelength_trigger_params(self, **kwargs): self.touch("trigger_set"); return kwargs
    def set_qcl_pulse_params(self, **kwargs): self.touch("pulse"); return kwargs
    def set_external_trigger_params(self, **kwargs): self.touch("external")
    def is_interlock_set(self): self.touch("interlock"); return True
    def is_key_switch_set(self): self.touch("key"); return True
    def are_tecs_ready(self): self.touch("TEC"); return True
    def arm(self): self.touch("arm"); self.armed=True
    def disarm(self): self.touch("disarm"); self.armed=False
    def is_laser_armed(self): self.touch("armed"); return self.armed
    def is_emission_on(self): self.touch("emission"); return self.emission
    def tune_to_wavenumber(self, value, *, qcl): self.touch("tune"); self.wavenumber=value
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
    def configure_pll(self, values): self.touch("PLL")
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
