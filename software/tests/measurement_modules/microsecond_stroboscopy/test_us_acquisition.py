"""Injected installed-service contract and complete hardware-free lifecycle tests."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from control_app.measurement_host import ContextFactory
from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError
from control_app.measurement_modules.microsecond_stroboscopy.acquisition import InstalledAcquirer
from control_app.measurement_modules.microsecond_stroboscopy.runner import run_acquisition, AcquisitionFailure
from control_app.measurement_modules.microsecond_stroboscopy.settings import default_settings, SpectralPoint
from control_app.measurement_modules.microsecond_stroboscopy.planner import build_plan
from control_app.devices.t660_service import _seconds_value


def inputs(mode="dual"):
    s=default_settings(mode)
    return replace(s,spectral_points=(SpectralPoint(1945.),),delays_us=(-500.,1000.),averages=1,
        operating_basis="Injected nonbiological fixture",promoted_bundle_ids=("fixture",),
        response=replace(s.response,sample_rate_sps=10_000.,reference_rate_sps=10_000.,timing_rate_sps=100_000.,
                         integration_aperture_s=.001,qualified=True,qualification_id="response-fixture"),
        timing=replace(s.timing,event_interval_s=.1),
        reset=replace(s.reset,recovery_wait_s=.001,verification_duration_s=.002,equivalent_state_verified=True,
                      equivalence_record_id="reset-fixture"),
        controls=replace(s.controls,baseline_duration_s=.002,preliminary_duration_s=.002,dark_record_id="dark",artifact_record_ids=("artifact",)),
        identity=replace(s.identity,sample_selection_id="sample-selection"))


def profile():
    return {"experiment_id":"microsecond_stroboscopy","profile_id":"fixture","modes":["single","dual"],
        "condition_profile_ids":["RT-Mb-R-K"],"wiring_id":"tee-fixture","reset_equivalence_id":"reset-fixture",
        "response_calibration_id":"response-fixture","tune_tolerance_cm1":.1,"settle_s":0.,"tune_timeout_s":1.,
        "timing_clock_readbacks":{"t660_1":{"clock_lock_status":"LOCKED"},"t660_2":{"clock_connector_mode":"OUT"}},
        "normalization":{"dark_offsets":{role:{"offset":0.,"standard_error":0.,"record_id":"dark"} for role in ("sample","reference")}},
        "timing":{"variable_sync_to_pump_s":0.,"optical_latency_calibration_id":"optical-fixture"},
        "hf2li":{"signal_inputs":{"sample":{"index":0,"ac":False,"impedance_50ohm":False,"differential":False,"range_v":1.},
                                   "reference":{"index":1,"ac":False,"impedance_50ohm":False,"differential":False,"range_v":1.}},
            "pll":{"index":0,"enable":True,"adcselect":4,"freqcenter_hz":1e6,"order":1},
            "phase_shift_deg":{"0":0.,"3":0.},"signed_x_calibration_id":"projection-fixture",
            "integrity_nodes":[{"type":"int","path":"/{device}/status/fixture_overload","expected":0}]}}


class Bus:
    def __init__(self):
        self.now=0.; self.timer=None; self.probe=None; self.pump=None; self.end=None
        self.created=[]; self.pump_count=0; self.fail_close=False; self.overload=0
        self.drop_pump=False; self.bad_reference=False
        self.accumulation=0.


class Timer:
    def __init__(self,name,bus):
        self.name,self.bus=name,bus
        self.device_config={}
        self.recipe={"trigger_source":"OFF","predivider":1,"clock":{"frequency":"1000000Hz"},
            "channels":{c:{"enabled":False,"delay":"0s","width":"0.000001s","polarity":"positive","termination":"50OHM","timing_mode":"delay_width"} for c in "ABCD"}}
        self.references={i:0 for i in range(1,9)}
        if name=="t660_1":bus.probe=self
        else:bus.timer=self
    def connect(self):pass
    def identify(self):return "HIGHLAND,T660,fixture,1"
    def command(self,command,**kwargs):
        if command.startswith("TIME:RELTo"):
            part=command.split("TIME:RELTo")[1]
            if part.endswith("?"):return str(self.references[int(part[:-1])])
            edge,value=part.split();self.references[int(edge)]=int(value)
        return "0"
    def apply_recipe(self,recipe):self.recipe=deepcopy(recipe);return {}
    def set_trigger_source(self,source):self.recipe["trigger_source"]=source
    def disable_channel(self,channel):self.recipe["channels"][channel]["enabled"]=False
    def enable_channel(self,channel):
        self.recipe["channels"][channel]["enabled"]=True
        if self.name=="t660_1" and channel=="C" and getattr(self.bus.timer,"armed",False):
            timer=self.bus.timer; timer.armed=False
            self.bus.end=self.bus.now+len(timer.frames)*timer.period
            event=timer.frames[1]["channels"]["B"]
            self.bus.pump=self.bus.now+timer.period+_seconds_value(event["delay"]) if event["enabled"] else None
            self.bus.pump_count+=int(event["enabled"])
    def start_continuous_clock(self):self.set_trigger_source("SYN")
    def configure_train(self,**kwargs):pass
    def preload_frame_table(self,frames,*,predivider,input_frequency_hz,progress,cancel_check):
        self.frames=frames;self.period=predivider/input_frequency_hz
        for i in range(len(frames)):
            cancel_check();progress(i+1,len(frames))
        return {"physical_frame_count":len(frames),"readback":{"first":0,"last":len(frames)-1,"loop_count":0,"predivider":predivider}}
    def start_frame_table(self):self.armed=True
    def get_frames_status(self):return "DONE" if self.bus.now>=self.bus.end else "RUNNING"
    def get_shot_count(self):return len(self.frames)
    def read_active_settings(self):
        success=lambda value:{"ok":True,"response":str(value)}
        return {"queries":{"trigger_source":success(self.recipe["trigger_source"]),
            "predivider":success(self.recipe.get("predivider",1)),"synth_frequency":success(self.recipe["clock"]["frequency"]),
            "clock_lock_status":success("LOCKED"),"clock_connector_mode":success("OUT"),
            "trigger_input_polarity":success("POS"),"trigger_input_termination":success("50OHM"),"trigger_input_threshold_v":success(2)},
            "channels":{c:{"enabled":success(int(s["enabled"])),"delay_edge":success(s["delay"]),"width_edge":success(s["width"]),
                           "polarity":success(s["polarity"]),"termination":success(s["termination"]),"timing_mode":success("delay_width")} for c,s in self.recipe["channels"].items()}}
    def close(self):
        if self.bus.fail_close and self.name=="t660_2":raise RuntimeError("injected transport close failure")


class Laser:
    def __init__(self,bus):
        self.bus=bus;self.emission=False;self.armed=False;self.wave=1945.;self.rate=1e6;self.width=100.;self.current=100.
        self.trigger={"pulse_mode":0,"process_trigger_mode":0,"start":1945.,"stop":1945.,"interval":0.,"units":1,"dwell_us":0,"after_off_us":0}
    def initialize(self):pass
    def deinitialize(self):pass
    def read_state(self):return {"armed":self.armed,"emission_on":self.emission}
    def get_wavelength_trigger_params(self):return deepcopy(self.trigger)
    def stop_scan_if_needed(self):return 0
    def turn_emission_off(self):self.emission=False
    def get_num_installed_qcls(self):return 1
    def get_qcl_tuning_range(self,qcl):return {"qcl":qcl,"min_cm1":1900.,"max_cm1":2000.}
    def get_qcl_pulse_rate(self,qcl):return self.rate
    def get_qcl_pulse_width(self,qcl):return self.width
    def get_qcl_current(self,qcl):return self.current
    def get_qcl_current_limits(self,qcl):return 0.,500.
    def is_interlock_set(self):return True
    def is_key_switch_set(self):return True
    def get_system_error_word(self):return 0
    def is_tuned(self):return True
    def arm(self):self.armed=True
    def disarm(self):self.armed=False
    def are_tecs_ready(self):return True
    def get_qcl_pulse_limits(self,qcl):return {"max_pulse_rate_hz":2e6,"max_pulse_width_ns":500.,"max_duty_cycle":30.}
    def set_qcl_pulse_params(self,*,qcl,pulse_rate_hz,pulse_width_ns,current_ma=None):
        self.rate,self.width=pulse_rate_hz,pulse_width_ns
        if current_ma is not None:self.current=current_ma
    def set_external_trigger_params(self,*,wavenumber_cm1):
        from control_app.devices.mircat_service import PULSE_MODE_EXTERNAL_TRIGGER,PROC_TRIG_MODE_INTERNAL
        self.trigger.update(pulse_mode=PULSE_MODE_EXTERNAL_TRIGGER,process_trigger_mode=PROC_TRIG_MODE_INTERNAL)
        return deepcopy(self.trigger)
    def set_wavelength_trigger_params(self,**kwargs):self.trigger.update(kwargs);return deepcopy(self.trigger)
    def tune_to_wavenumber(self,wavenumber_cm1,*,qcl):self.wave=wavenumber_cm1
    def turn_emission_on(self,**kwargs):self.emission=True
    def get_actual_wavelength(self):return {"value":self.wave,"units":"cm^-1","light_valid":self.emission}
    def is_emission_on(self):return self.emission


class HF:
    device_id="devfixture"
    def __init__(self,bus):self.bus=bus;self.nodes={};self.demods=[]
    def connect(self):pass
    def close(self):pass
    def sync(self):pass
    def _get_node(self,kind,path):
        if path.endswith("fixture_overload"):return self.bus.overload
        return self.nodes.get(path,{"value":0})["value"]
    def _set_node(self,method,path,value):self.nodes[path]={"type":"int" if method=="setInt" else "double","value":value}
    def export_settings_snapshot(self,**kwargs):return {"nodes":deepcopy(self.nodes),"read_errors":{},"device_id":self.device_id}
    def reload_settings_snapshot(self,snapshot):self.nodes=deepcopy(snapshot["nodes"])
    def compare_settings_snapshots(self,before,after):return {"match":before["nodes"]==after["nodes"]}
    def apply_preset(self,preset):
        for d in preset.settings["demodulators"]:
            for key,value in d.items():
                if key=="index":continue
                node={"timeconstant_s":"timeconstant","rate_sps":"rate"}.get(key,key)
                self._set_node("setDouble",f"/{self.device_id}/demods/{d['index']}/{node}",int(value) if isinstance(value,bool) else value)
        for entry in preset.settings["signal_inputs"].values():
            for key,value in entry.items():
                if key=="index":continue
                node={"impedance_50ohm":"imp50","differential":"diff","range_v":"range"}.get(key,key)
                self._set_node("setDouble",f"/{self.device_id}/sigins/{entry['index']}/{node}",int(value) if isinstance(value,bool) else value)
    def get_clockbase(self):return 1_000_000
    def get_oscillator_frequency(self,index):return 1e6
    def start_acquisition(self,*,demodulators,**kwargs):self.demods=demodulators
    def stop_acquisition(self):self.demods=[]
    def read_acquisition(self,duration_s):
        before=self.bus.now;self.bus.now+=duration_s
        output={}
        for index in self.demods:
            path=f"/{self.device_id}/demods/{index}"
            rate=self.nodes[path+"/rate"]["value"]
            times=before+np.arange(round(duration_s*rate))/rate
            dio=np.zeros(len(times),np.uint32)
            if self.bus.pump is not None and not self.bus.drop_pump:
                dio[(times>=self.bus.pump)&(times<self.bus.pump+30e-6)] = 1<<17
            x=np.full(len(times),.6 if index==0 else 1.)
            if index==0 and self.bus.pump_count:x*=1-self.bus.accumulation
            if index==3 and self.bus.bad_reference:x[:]=0
            output[path+"/sample"]={"timestamp":np.rint(times*1e6).astype(np.uint64),"x":x,"y":np.zeros(len(times)),"dio":dio}
        return {"data":output,"duration_s":duration_s}


def setup(tmp_path,mode="dual",*,installed=False):
    coordinator=HardwareCoordinator(tmp_path/"owner.lock")
    bus=Bus()
    factories={}
    if installed:
        for name in ("t660_1","t660_2","mircat","hf2li"):
            def create(*,configuration,_name=name,**kwargs):
                bus.created.append(_name)
                return Timer(_name,bus) if _name.startswith("t660") else Laser(bus) if _name=="mircat" else HF(bus)
            factories[name]=create
    factory=ContextFactory(configuration_provider=lambda:{"devices":{}},real_device_factories=factories,
        save_root_provider=lambda:tmp_path,ownership=coordinator,
        promoted_bundle_loader=lambda identifier:{"status":"PROMOTED","bundle_id":identifier,"microsecond_stroboscopy":profile()})
    context=factory.for_experiment("microsecond_stroboscopy").for_mode(mode)
    return context,coordinator,bus,factory


def sample_selection(s):
    from control_app.measurement_host.interchange import SampleSpectralSelection,SourceRecord,SpectralWindow
    return SampleSpectralSelection(selection_id=s.identity.sample_selection_id,sample_id=s.identity.sample_id,
        producer_instance_id="microsecond_stroboscopy:single",condition_id=s.identity.condition_id,
        condition={"profile_id":s.condition_profile_id},windows=(SpectralWindow(1944.,1946.,1945.,.01,"accepted fixture band"),),
        source=SourceRecord("sample-native-fixture","fixture/accepted-sample.json","2026-09-09T00:00:00Z","fixture/1"),
        accepted_by="Named fixture reviewer",accepted_utc="2026-09-09T00:00:00Z").to_dict()


def execute(context,s,kind,*,hardware=False,sample_records=None,**kwargs):
    if sample_records is None:
        sample_records=(sample_selection(s),) if hardware else ()
    operation=context.begin_operation(s.to_dict(),hardware=hardware,sample_records=sample_records)
    return run_acquisition(context,operation,build_plan(s),kind=kind,**kwargs)


def test_us_simulation_complete_single_blank_review_and_run(tmp_path):
    context,_,_,_=setup(tmp_path,"single")
    s=inputs("single")
    blank=execute(context,s,"blank")
    assert sum(b["kind"]=="blank_control" for b in blank["native_blocks"])==2
    preliminary=execute(context,s,"preliminary",blank=blank)
    result=execute(context,s,"run",blank=blank,preliminary=preliminary)
    assert result["disposition"]=="complete"
    assert sum(b["kind"]=="pumped" for b in result["native_blocks"])==2
    assert all(b["sample"]["timestamp_ticks"].dtype==np.uint64 for b in result["native_blocks"])


def test_us_installed_injected_apis_and_ownership_through_final_save(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,coordinator,bus,factory=setup(tmp_path,installed=True)
    s=inputs()
    preliminary=execute(context,s,"preliminary",hardware=True)
    from control_app.measurement_modules.microsecond_stroboscopy.persistence import save_run,load_run
    observed=[]
    def preserve(record):
        observed.append(coordinator.snapshot()["state"])
        sibling=factory.for_experiment("microsecond_stroboscopy").for_mode("single")
        with pytest.raises(OwnershipError):sibling.begin_operation({},hardware=True)
        return save_run(tmp_path/"saved",record)
    result=execute(context,s,"run",hardware=True,preliminary=preliminary,preserve=preserve)
    assert result["disposition"]=="complete"
    assert observed and set(observed)=={"owned"}
    assert coordinator.snapshot()["state"]=="free"
    assert bus.pump_count==2
    assert result["restoration"]["safe_verified"]
    assert set(bus.created)=={"hf2li","mircat","t660_1","t660_2"}
    native=load_run(tmp_path/"saved")
    pumped=[b for b in native["native_blocks"] if b["kind"]=="pumped"]
    assert all(len(b["electrical_events_s"])==1 and b["optically_observed_event_count"] is None for b in pumped)
    assert all("actual_delay_s" in b and b["raw_polls"] for b in pumped)


def test_us_cancel_retains_partial_and_cleanup_fault_precedes_stop(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,coordinator,bus,_=setup(tmp_path,installed=True)
    s=inputs()
    preliminary=execute(context,s,"preliminary",hardware=True)
    bus.fail_close=True
    with pytest.raises(AcquisitionFailure) as failed:
        execute(context,s,"run",hardware=True,preliminary=preliminary,cancel=lambda:bus.pump_count>0)
    record=failed.value.record
    assert record["disposition"]=="cleanup_failed"
    assert bus.pump_count==1
    assert any("incomplete" in b["flags"] for b in record["native_blocks"])
    assert coordinator.snapshot()["state"]=="fault"
    assert record["native_path"]


def test_us_missing_pump_never_retries_and_preserves(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,coordinator,bus,_=setup(tmp_path,installed=True)
    s=inputs();preliminary=execute(context,s,"preliminary",hardware=True)
    bus.drop_pump=True
    with pytest.raises(AcquisitionFailure) as failure:
        execute(context,s,"run",hardware=True,preliminary=preliminary)
    assert bus.pump_count==1
    assert failure.value.record["native_path"]
    assert "Variable Sync" in str(failure.value)
    assert coordinator.snapshot()["state"]=="free"


def test_us_storage_failure_before_any_factory(tmp_path):
    context,coordinator,bus,_=setup(tmp_path,installed=True)
    def fail(record):raise OSError("disk full")
    with pytest.raises(AcquisitionFailure) as failure:
        execute(context,inputs(),"preliminary",hardware=True,preserve=fail)
    assert not bus.created
    assert failure.value.record["disposition"]=="preservation_failed"
    assert coordinator.snapshot()["state"]=="fault"


def test_us_cancel_during_preparation_restores_and_retains(tmp_path):
    context,coordinator,bus,_=setup(tmp_path,installed=True)
    result=execute(context,inputs(),"preliminary",hardware=True,cancel=lambda:bool(bus.created))
    assert result["disposition"]=="interrupted"
    assert result["restoration"]["safe_verified"]
    assert coordinator.snapshot()["state"]=="free"
    assert bus.pump_count==0


def test_us_storage_failure_after_pump_keeps_fault_and_in_memory_native(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,coordinator,bus,_=setup(tmp_path,installed=True)
    s=inputs();preliminary=execute(context,s,"preliminary",hardware=True)
    from control_app.measurement_modules.microsecond_stroboscopy.persistence import save_run
    def preserve(record):
        if bus.pump_count:raise OSError("media disconnected after acquisition")
        return save_run(tmp_path/"before-disconnection",record)
    with pytest.raises(AcquisitionFailure) as failure:
        execute(context,s,"run",hardware=True,preliminary=preliminary,preserve=preserve)
    result=failure.value.record
    assert bus.pump_count==1
    assert result["disposition"]=="preservation_failed"
    assert any(b["raw_polls"] for b in result["native_blocks"] if b["kind"]=="pumped")
    assert result["restoration"]["safe_verified"]
    assert coordinator.snapshot()["state"]=="fault"


def test_us_unrecovered_state_stops_next_equivalent_event(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,_,bus,_=setup(tmp_path,installed=True)
    s=inputs();preliminary=execute(context,s,"preliminary",hardware=True)
    bus.accumulation=.1
    with pytest.raises(AcquisitionFailure) as failure:
        execute(context,s,"run",hardware=True,preliminary=preliminary)
    assert bus.pump_count==1
    assert "not recovered" in str(failure.value)
    assert any("unrecovered" in b["flags"] for b in failure.value.record["native_blocks"])


def test_us_normal_abort_during_pumped_block_returns_stopped_result(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,coordinator,bus,_=setup(tmp_path,installed=True)
    s=inputs();preliminary=execute(context,s,"preliminary",hardware=True)
    record=execute(context,s,"run",hardware=True,preliminary=preliminary,cancel=lambda:bus.pump_count>0)
    assert record["disposition"]=="interrupted"
    assert record["message"]=="Acquisition stopped"
    assert record["restoration"]["safe_verified"]
    assert coordinator.snapshot()["state"]=="free"
    assert sum(b["kind"]=="pumped" for b in record["native_blocks"])==1


def test_us_complete_flag_cannot_hide_missing_blank_delay(tmp_path):
    context,_,_,_=setup(tmp_path,"single")
    s=inputs("single")
    blank=execute(context,s,"blank")
    blank["native_blocks"]=[b for b in blank["native_blocks"] if not (b["kind"]=="blank_control" and b["delay_s"]>0)]
    with pytest.raises(AcquisitionFailure,match="missing compatible declared delay"):
        execute(context,s,"preliminary",blank=blank)


@pytest.mark.parametrize("change,message",[
    ("missing","exactly one retained accepted sample selection"),
    ("selection_id","exactly one retained accepted sample selection"),
    ("sample_id","sample_id differs"),
    ("condition_id","condition_id differs"),
    ("outside","outside accepted sample spectral windows"),
    ("duplicate","exactly one retained accepted sample selection"),
    ("rejected","Only accepted sample_spectral_selection"),
])
def test_us_real_sample_record_preflight_rejects_missing_or_incompatible(tmp_path,change,message):
    context,coordinator,bus,_=setup(tmp_path,installed=True)
    s=inputs();selection=sample_selection(s)
    records=[selection]
    if change=="missing":records=[]
    elif change=="duplicate":records=[selection,deepcopy(selection)]
    elif change=="outside":selection["windows"]=[{"lower_cm1":1940.,"upper_cm1":1941.}]
    elif change=="rejected":selection["disposition"]="rejected"
    else:selection[change]="another-identity"
    with pytest.raises(AcquisitionFailure,match=message) as failed:
        execute(context,s,"preliminary",hardware=True,sample_records=records)
    assert not bus.created
    assert failed.value.record["native_path"]
    assert coordinator.snapshot()["state"]=="free"


def test_us_real_sample_window_validation_allows_explicit_off_band(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,_,_,_=setup(tmp_path,installed=True)
    s=inputs()
    s=replace(s,spectral_points=(*s.spectral_points,SpectralPoint(1960.,"outside accepted band","off_band")))
    record=execute(context,s,"preliminary",hardware=True)
    assert record["disposition"]=="complete"
    assert record["operation"]["sample_records"][0]["selection_id"]==s.identity.sample_selection_id
