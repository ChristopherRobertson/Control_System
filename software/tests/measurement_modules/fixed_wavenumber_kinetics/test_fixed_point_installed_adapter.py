"""Installed API path exercised with owned injected services, never hardware."""
from copy import deepcopy
from types import SimpleNamespace

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
    def start_continuous_clock(self): self.touch("start_clock"); self.source = "SYN"
    def read_active_settings(self):
        self.touch("readback")
        return {"queries": {"trigger_source": {"ok": True, "response": self.source},
            "synth_frequency": {"ok": True, "response": "100000"},
            "predivider": {"ok": True, "response": "1"},
            "clock_connector_mode": {"ok": True, "response": "OUT" if self.name == "t660_2" else "IN"},
            "clock_lock_status": {"ok": True, "response": "LOCKED"}},
            "channels": {c: {"enabled": {"ok": True, "response": "ON" if on else "OFF"},
                "delay_edge": {"ok": True, "response": "0"}, "width_edge": {"ok": True, "response": "150ns"}}
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
    def get_frames_status(self): self.touch("frames_status"); return "DONE"
    def get_shot_count(self): self.touch("shot_count"); return len(self.frames)


class Mircat(Owned):
    def __init__(self): self.calls=[]; self.armed=False; self.emission=False; self.wavenumber=1930.
    def initialize(self): self.touch("initialize")
    def deinitialize(self): self.touch("deinitialize")
    def read_state(self): self.touch("state"); return SimpleNamespace(to_dict=lambda: {"emission_on": self.emission})
    def turn_emission_off(self): self.touch("off"); self.emission=False
    def turn_emission_on(self, *, approved_laser_safety_condition): self.touch("on"); assert approved_laser_safety_condition; self.emission=True
    def get_qcl_pulse_rate(self, qcl): self.touch("rate"); return 100000.
    def get_qcl_pulse_width(self, qcl): self.touch("width"); return 150.
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
                self.nodes[f"/{self.device_id}/demods/{i}/{key}"]={"value":0,"type":"double"}
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
    def get_clockbase(self): self.touch("clockbase"); return 210000000
    def read_acquisition_health(self, *, reference_pll, input_indices):
        self.touch("health")
        return {"reference_locked":True,"clock_locked":True,"external_clock_selected":True,"overload":False,"read_errors":{}}
    def start_acquisition(self, *, demodulators, fields): self.touch("subscribe"); self.state["core"].start_stream()
    def read_acquisition(self, duration_s):
        self.touch("poll")
        chunk=self.state["core"].read(duration_s)
        return {"data": {f"/{self.device_id}/demods/{index}/sample":chunk[role] for role,index in (("sample",0),("reference",3),("timing",2))},"timestamp_utc":"2026-09-09T00:00:00Z"}
    def stop_acquisition(self): self.touch("unsubscribe"); self.state["core"].stop_stream()
    def reload_settings_snapshot(self, before): self.touch("restore"); self.nodes=deepcopy(before["nodes"])
    def compare_settings_snapshots(self, before, after): self.touch("verify_restore"); return {"match":before==after}


def test_fixed_point_installed_services_complete_under_host_ownership(tmp_path):
    profile=simulation_profile("dual")
    profile["evidence"]["operating_profile"]["qualification_kind"]="measured"
    profile["configuration"]["fixed_wavenumber_kinetics"]["qualification_kind"]="measured"
    state={}
    services={"t660_1": Timing(state,"t660_1"),"t660_2":Timing(state,"t660_2"),"mircat":Mircat(),"hf2li":HF2(state)}
    factories={name:(lambda *,configuration, service=service:service) for name,service in services.items()}
    context=ContextFactory(configuration_provider=lambda:profile["configuration"],real_device_factories=factories,
        save_root_provider=lambda:tmp_path,ownership=HardwareCoordinator(tmp_path/"exclusive.lock")).for_experiment("fixed_wavenumber_kinetics").for_mode("dual")
    plan=build_plan(profile["settings"],profile["configuration"],profile["evidence"])
    assert plan.ready,plan.readiness_items
    operation=context.begin_operation(settings=profile["settings"],hardware=True)
    core=SimulatedDevices(context, SimpleNamespace(hardware=False,configuration=operation.configuration))
    core.configure(plan.resolved,lambda:None)
    state["core"]=core
    result=Runner(context, history_path=tmp_path/"state-history.jsonl").run(operation,plan)
    assert result["status"]=="complete",result.get("error",result.get("cleanup_error",result.get("analysis_error")))
    assert result["restoration"]["safe_verified"] and result["preservation_verified"]
    assert core.dispatched==1
    assert "pending_upload" in services["t660_2"].calls
    assert "health" in services["hf2li"].calls and "verify_restore" in services["hf2li"].calls
    # Release occurred only after native_run and final analyzed run were written.
    with pytest.raises(Exception): services["hf2li"].sync()


def test_fixed_point_simulation_profile_rejected_before_connected_factory(tmp_path):
    profile=simulation_profile("dual")
    context=ContextFactory(configuration_provider=lambda:profile["configuration"],
        real_device_factories={"hf2li":lambda **kwargs:pytest.fail("No connected factory allowed")},
        save_root_provider=lambda:tmp_path,ownership=HardwareCoordinator(tmp_path/"exclusive.lock")).for_experiment("fixed_wavenumber_kinetics").for_mode("dual")
    plan=build_plan(profile["settings"],profile["configuration"],profile["evidence"])
    operation=context.begin_operation(settings=profile["settings"],hardware=True)
    result=Runner(context, history_path=tmp_path/"state-history.jsonl").run(operation,plan)
    assert result["status"]=="failed"
    assert "Synthetic operating profile" in result["error"]
    assert result["preservation_verified"]
