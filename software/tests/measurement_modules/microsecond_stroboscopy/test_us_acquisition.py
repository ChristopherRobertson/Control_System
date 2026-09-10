"""Injected installed-service contract and complete hardware-free lifecycle tests."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from control_app.measurement_host import ContextFactory
from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError
from control_app.measurement_modules.microsecond_stroboscopy.acquisition import InstalledAcquirer, SimulatedAcquirer
from control_app.measurement_modules.microsecond_stroboscopy.runner import run_acquisition, AcquisitionFailure
from control_app.measurement_modules.microsecond_stroboscopy.settings import default_settings, SpectralPoint
from control_app.measurement_modules.microsecond_stroboscopy.planner import build_plan
from control_app.devices.t660_service import _seconds_value


def inputs(mode="dual"):
    s=default_settings(mode)
    return replace(s,spectral_points=(SpectralPoint(1945.),),delays_us=(-500.,1000.),averages=1,
        operating_basis="Injected nonbiological fixture",promoted_bundle_ids=(),
        manual_overrides=tuple("response."+key for key in s.response.__dataclass_fields__)+("timing.event_interval_s","reset.recovery_wait_s"),
        response=replace(s.response,sample_rate_sps=10_000.,reference_rate_sps=10_000.,timing_rate_sps=100_000.,
                         integration_aperture_s=.001,qualified=False,qualification_id=""),
        timing=replace(s.timing,event_interval_s=.1),
        reset=replace(s.reset,recovery_wait_s=.001,verification_duration_s=.002,equivalent_state_verified=False,
                      equivalence_record_id=""),
        controls=replace(s.controls,baseline_duration_s=.002,preliminary_duration_s=.002,dark_record_id="",artifact_record_ids=()),
        identity=replace(s.identity,sample_selection_id=""))


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
        self.negative_sample=False;self.nonfinite_sample=False;self.reference_locked=True;self.health_unknown=False
        self.actual_sample_rate=None;self.interlock=True
        self.phase_shift=0.;self.initial_sinc=True


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
        bus.laser=self;self.initialized=False;self.deinitialized=False;self.scanning=False
        self.trigger={"pulse_mode":0,"process_trigger_mode":0,"start":1945.,"stop":1945.,"interval":0.,"units":1,"dwell_us":0,"after_off_us":0}
    def initialize(self):self.initialized=True
    def deinitialize(self):self.deinitialized=True
    def read_state(self):return {"armed":self.armed,"emission_on":self.emission,
        "scan_in_progress":self.scanning,"scan_active":self.scanning,"scan_paused":False,"scan_waiting_process_trigger":False}
    def get_wavelength_trigger_params(self):return deepcopy(self.trigger)
    def stop_scan_if_needed(self):self.scanning=False;return 0
    def turn_emission_off(self):self.emission=False
    def get_num_installed_qcls(self):return 1
    def get_qcl_tuning_range(self,qcl):return {"qcl":qcl,"min_cm1":1900.,"max_cm1":2000.}
    def get_qcl_pulse_rate(self,qcl):return self.rate
    def get_qcl_pulse_width(self,qcl):return self.width
    def get_qcl_current(self,qcl):return self.current
    def get_qcl_current_limits(self,qcl):return 0.,500.
    def is_interlock_set(self):return self.bus.interlock
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
    def start_emission(self):self.emission=True
    def get_actual_wavelength(self):return {"value":self.wave,"units":"cm^-1","light_valid":self.emission}
    def is_emission_on(self):return self.emission


class HF:
    device_id="devfixture"
    def __init__(self,bus):
        self.bus=bus;self.nodes={};self.demods=[]
        for index in range(6):
            for key,value in {"enable":0,"adcselect":int(index==3),"oscselect":0,"harmonic":1,"order":1,
                              "timeconstant":8e-6,"rate":100_000. if index==2 else 10_000.,"trigger":0,"phaseshift":self.bus.phase_shift,"sinc":int(self.bus.initial_sinc)}.items():
                self._set_node("setDouble",f"/{self.device_id}/demods/{index}/{key}",value)
        for index in (0,1):
            for key,value in {"ac":0,"imp50":0,"diff":0,"range":1.}.items():
                self._set_node("setDouble",f"/{self.device_id}/sigins/{index}/{key}",value)
        for key,value in {"enable":0,"adcselect":4,"freqcenter":1e6,"harmonic":1,"order":1,"adcthreshold":0}.items():
            self._set_node("setDouble",f"/{self.device_id}/plls/0/{key}",value)
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
    def read_acquisition_health(self,**kwargs):
        return {"schema_version":"hf2li-acquisition-health/1","reference_locked":None if self.bus.health_unknown else self.bus.reference_locked,
            "clock_locked":True,"overload":bool(self.bus.overload),"external_clock_selected":True,
            "external_reference_locked":None,"read_errors":{"unavailable_fixture_node":"unavailable"} if self.bus.health_unknown else {},"nodes":{}}
    def apply_preset(self,preset):
        for key,value in preset.settings.get("pll",{}).items():
            if key=="index":continue
            node={"freqcenter_hz":"freqcenter"}.get(key,key)
            self._set_node("setDouble",f"/{self.device_id}/plls/0/{node}",int(value) if isinstance(value,bool) else value)
        for d in preset.settings["demodulators"]:
            for key,value in d.items():
                if key=="index":continue
                node={"timeconstant_s":"timeconstant","rate_sps":"rate"}.get(key,key)
                if d["index"]==0 and node=="rate" and self.bus.actual_sample_rate is not None:
                    value=self.bus.actual_sample_rate
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
            if index==0 and self.bus.negative_sample:x*=-1
            if index==0 and self.bus.nonfinite_sample:x[0]=np.nan
            if index==3 and self.bus.bad_reference:x[:]=0
            output[path+"/sample"]={"timestamp":np.rint(times*1e6).astype(np.uint64),"x":x,"y":np.zeros(len(times)),"dio":dio}
        return {"data":output,"duration_s":duration_s}


def setup(tmp_path,mode="dual",*,installed=False,runtime=None,lifecycle=None):
    coordinator=HardwareCoordinator(tmp_path/"owner.lock")
    bus=Bus()
    factories={}
    if installed:
        for name in ("t660_1","t660_2","mircat","hf2li"):
            def create(*,configuration,_name=name,**kwargs):
                bus.created.append(_name)
                return Timer(_name,bus) if _name.startswith("t660") else Laser(bus) if _name=="mircat" else HF(bus)
            factories[name]=create
    def no_promotion_lookup(identifier):raise AssertionError("Acquisition must not require a promotion lookup")
    configuration={"devices":{}}
    if runtime is not None:configuration["microsecond_stroboscopy"]=runtime
    factory=ContextFactory(configuration_provider=lambda:configuration,real_device_factories=factories,
        save_root_provider=lambda:tmp_path,ownership=coordinator,promoted_bundle_loader=no_promotion_lookup,lifecycle=lifecycle)
    context=factory.for_experiment("microsecond_stroboscopy").for_mode(mode)
    return context,coordinator,bus,factory


def execute(context,s,kind,*,hardware=False,sample_records=(),**kwargs):
    operation=context.begin_operation(s.to_dict(),hardware=hardware,sample_records=sample_records)
    if not hardware:
        kwargs.setdefault("acquirer_factory",SimulatedAcquirer)
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


def test_us_nonrecovery_is_retained_without_blocking_requested_events(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,_,bus,_=setup(tmp_path,installed=True)
    s=inputs();preliminary=execute(context,s,"preliminary",hardware=True)
    bus.accumulation=.1
    record=execute(context,s,"run",hardware=True,preliminary=preliminary)
    assert bus.pump_count==2
    assert record["disposition"]=="complete"
    assert any("reset_nonrecovery" in b["flags"] for b in record["native_blocks"] if b["kind"]=="pumped")


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


def test_us_incompatible_optional_blank_is_ignored_and_raw_run_continues(tmp_path):
    context,_,_,_=setup(tmp_path,"single")
    s=inputs("single")
    blank=execute(context,s,"blank")
    blank["settings"]["mode"]="dual"
    blank["requested_settings"]["mode"]="dual"
    record=execute(context,s,"run",blank=blank)
    assert record["disposition"]=="complete"
    assert "blank_record" not in record
    assert record["unused_optional_records"]


def test_us_single_real_run_needs_no_blank_preliminary_or_scientific_approvals(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,coordinator,bus,_=setup(tmp_path,"single",installed=True)
    s=inputs("single")
    s=replace(s,condition_profile_id="77K-Mb-G-F",identity=replace(s.identity,measured_temperature_k=None,
              temperature_uncertainty_k=None,temperature_record_id="",sample_selection_id=""))
    record=execute(context,s,"run",hardware=True,sample_records=())
    assert record["disposition"]=="complete"
    assert bus.pump_count==2 and coordinator.snapshot()["state"]=="free"
    pumped=[b for b in record["native_blocks"] if b["kind"]=="pumped"]
    assert all(b["optical_origin_s"] is None and b["electrical_origin_s"] is not None for b in pumped)
    assert all(b["delay_basis"]=="electrical_relative" and "unresolved_optical_origin" in b["flags"] for b in pumped)
    assert all("aperture_start_s" in b and "actual_delay_s" in b for b in pumped)


def test_us_compatible_records_survive_temperature_and_annotation_changes(tmp_path):
    context,_,_,_=setup(tmp_path,"single")
    s=inputs("single")
    blank=execute(context,s,"blank")
    preliminary=execute(context,s,"preliminary",blank=blank)
    changed=replace(s,identity=replace(s.identity,temperature_record_id="later annotation",measured_temperature_k=77.,sample_selection_id="optional-id"),
                    operating_basis="updated note",condition_profile_id="77K-Mb-G-F")
    record=execute(context,changed,"run",blank=blank,preliminary=preliminary)
    assert record["blank_record"]["run_id"]==blank["run_id"]
    assert record["preliminary"]["run_id"]==preliminary["run_id"]
    assert record["disposition"]=="complete"
    baseline=next(block for block in record["native_blocks"] if block["kind"]=="baseline")
    assert baseline["preliminary_baseline_comparison"]["acquisition_gate"] is False


@pytest.mark.parametrize("failure,message",[("overload","ADC clipping"),("reference_locked","loss of reference"),("interlock","interlock"),("nonfinite_sample","incomplete")])
def test_us_actual_hardware_failures_still_stop_and_restore(tmp_path,monkeypatch,failure,message):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,coordinator,bus,_=setup(tmp_path,installed=True)
    setattr(bus,failure,False if failure in ("reference_locked","interlock") else True)
    with pytest.raises(AcquisitionFailure,match=message) as failed:
        execute(context,inputs(),"run",hardware=True)
    assert bus.pump_count==0
    assert failed.value.record["native_path"]
    assert coordinator.snapshot()["state"]=="free"


def test_us_negative_x_and_unknown_health_remain_native_without_fabrication(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,_,bus,_=setup(tmp_path,installed=True)
    bus.negative_sample=True;bus.health_unknown=True
    record=execute(context,inputs(),"run",hardware=True)
    assert record["disposition"]=="complete"
    assert all(np.all(b["sample"]["x"]<0) for b in record["native_blocks"])
    assert any(b.get("health_observations") and "health_status_unknown" in b["flags"] for b in record["native_blocks"])


def test_us_device_rounding_is_retained_as_actual_supported_response(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,_,bus,_=setup(tmp_path,installed=True)
    bus.actual_sample_rate=5000.
    record=execute(context,inputs(),"run",hardware=True)
    assert record["requested_settings"]["response"]["sample_rate_sps"]==10000.
    assert record["actual_settings"]["response"]["sample_rate_sps"]==5000.
    assert record["settings"]["response"]["sample_rate_sps"]==5000.
    assert record["disposition"]=="complete"


def test_us_no_implicit_simulation_fallback(tmp_path):
    context,_,_,_=setup(tmp_path,"single")
    s=inputs("single")
    operation=context.begin_operation(s.to_dict(),hardware=False)
    with pytest.raises(AcquisitionFailure,match="developer simulation must be explicitly injected"):
        run_acquisition(context,operation,build_plan(s),kind="run")


def test_us_hardware_phase_change_omits_optional_blank_without_gating_run(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,_,bus,_=setup(tmp_path,"single",installed=True)
    s=inputs("single")
    blank=execute(context,s,"blank",hardware=True)
    bus.phase_shift=90.
    record=execute(context,s,"run",hardware=True,blank=blank)
    assert record["disposition"]=="complete" and "blank_record" not in record
    assert any("phaseshift" in item["reason"] for item in record["unused_optional_records"])


def test_us_sinc_is_explicitly_disabled_and_original_value_restored(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,_,_,_=setup(tmp_path,installed=True)
    record=execute(context,inputs(),"preliminary",hardware=True)
    path="/devfixture/demods/0/sinc"
    assert record["readbacks"]["hf2li"]["nodes"][path]["value"]==0
    assert record["restoration"]["original"]["hf2li"]["nodes"][path]["value"]==1
    assert record["restoration"]["verification"]["HF2LI restored verified"]["nodes"][path]["value"]==1


def test_us_throwing_start_lifecycle_cannot_strand_ownership(tmp_path):
    class Lifecycle:
        def notify_state(self,instance,busy,state):
            raise RuntimeError("injected lifecycle callback failure")
    context,coordinator,bus,_=setup(tmp_path,installed=True,lifecycle=Lifecycle())
    with pytest.raises(AcquisitionFailure,match="lifecycle callback failure") as failed:
        execute(context,inputs(),"run",hardware=True)
    assert not bus.created
    assert coordinator.snapshot()["state"]=="free"
    assert failed.value.record["restoration"]["safe_verified"]
    assert failed.value.record["native_path"]


def test_us_throwing_cosmetic_progress_cannot_skip_cleanup_or_saving(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,coordinator,_,_=setup(tmp_path,installed=True)
    def broken(message):raise RuntimeError("closed progress widget")
    record=execute(context,inputs(),"run",hardware=True,progress=broken)
    assert record["disposition"]=="complete"
    assert record["restoration"]["safe_verified"] and record["native_path"]
    assert record["notification_errors"]
    assert coordinator.snapshot()["state"]=="free"


def test_us_small_preliminary_uses_its_own_budget_before_and_after_connection(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,coordinator,bus,_=setup(tmp_path,installed=True)
    s=inputs()
    preliminary_memory=build_plan(s,kind="preliminary").budget.memory_bytes
    s=replace(s,budget=replace(s.budget,maximum_memory_bytes=preliminary_memory*2))
    assert any("memory budget" in error for error in build_plan(s,kind="run").readiness.errors)
    assert not build_plan(s,kind="preliminary").readiness.errors
    record=execute(context,s,"preliminary",hardware=True)
    assert record["disposition"]=="complete" and bus.pump_count==0
    assert coordinator.snapshot()["state"]=="free"


def _initialize_active_laser(laser):
    laser.initialized=True
    laser.armed=laser.emission=laser.scanning=True


def test_us_cleanup_disarms_originally_armed_laser_and_verifies_physical_state(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    monkeypatch.setattr(Laser,"initialize",_initialize_active_laser)
    context,coordinator,bus,_=setup(tmp_path,installed=True)
    record=execute(context,inputs(),"preliminary",hardware=True)
    restoration=record["restoration"]
    assert restoration["original"]["mircat"]["state"]["armed"] is True
    final=restoration["verification"]["MIRcat final state"]
    assert all(value is False for value in final.values())
    assert restoration["safe_verified"] and bus.laser.deinitialized
    assert coordinator.snapshot()["state"]=="free"


@pytest.mark.parametrize("interruption",["snapshot_failure","cancel"])
def test_us_partial_laser_preparation_without_snapshot_still_closes_physically(tmp_path,monkeypatch,interruption):
    monkeypatch.setattr(Laser,"initialize",_initialize_active_laser)
    context,coordinator,bus,_=setup(tmp_path,installed=True)
    if interruption=="snapshot_failure":
        def fail_snapshot(self):raise RuntimeError("trigger snapshot unavailable")
        monkeypatch.setattr(Laser,"get_wavelength_trigger_params",fail_snapshot)
        with pytest.raises(AcquisitionFailure,match="trigger snapshot unavailable") as failed:
            execute(context,inputs(),"preliminary",hardware=True)
        record=failed.value.record
    else:
        record=execute(context,inputs(),"preliminary",hardware=True,
            cancel=lambda:bool(getattr(bus,"laser",None) and bus.laser.initialized))
        assert record["disposition"]=="interrupted"
    restoration=record["restoration"]
    assert "mircat" not in restoration["original"]
    assert restoration["safe_verified"] and bus.laser.deinitialized
    assert all(value is False for value in restoration["verification"]["MIRcat final state"].values())
    assert record["native_path"] and coordinator.snapshot()["state"]=="free"


@pytest.mark.parametrize("command,field",[("disarm","armed"),("turn_emission_off","emission_on"),("stop_scan_if_needed","scan_in_progress")])
def test_us_unclosed_laser_readback_prevents_safe_release_even_after_cancel(tmp_path,monkeypatch,command,field):
    monkeypatch.setattr(Laser,"initialize",_initialize_active_laser)
    monkeypatch.setattr(Laser,command,lambda self:None)
    context,coordinator,bus,_=setup(tmp_path,installed=True)
    with pytest.raises(AcquisitionFailure,match="not verified OFF") as failed:
        execute(context,inputs(),"preliminary",hardware=True,
            cancel=lambda:bool(getattr(bus,"laser",None) and bus.laser.initialized))
    record=failed.value.record
    assert record["disposition"]=="cleanup_failed"
    assert record["restoration"]["verification"]["MIRcat final state"][field] is True
    assert not record["restoration"]["safe_verified"] and bus.laser.deinitialized
    assert record["native_path"] and coordinator.snapshot()["state"]=="fault"


def test_us_reference_copy_memory_failure_releases_unused_operation(tmp_path,monkeypatch):
    from control_app.measurement_modules.microsecond_stroboscopy import runner
    context,coordinator,bus,_=setup(tmp_path,installed=True)
    s=inputs()
    operation=context.begin_operation(s.to_dict(),hardware=True)
    def fail_copy(record):raise MemoryError("retained reference allocation failed")
    monkeypatch.setattr(runner,"deepcopy",fail_copy)
    with pytest.raises(MemoryError,match="retained reference allocation failed"):
        run_acquisition(context,operation,build_plan(s),kind="run",preliminary={"native_blocks":[]})
    assert not bus.created
    assert coordinator.snapshot()["state"]=="free"


def _observe_timer_reference_restoration(monkeypatch,bus,ignored=None):
    """Change references only; fake delay/width readbacks remain unchanged."""
    original_init,original_command=Timer.__init__,Timer.command
    queries={name:[] for name in ("t660_1","t660_2")}
    restoring=False
    def initialize(self,name,shared):
        original_init(self,name,shared)
        self.references={edge:edge-1 for edge in range(1,9)}
    def command(self,text,**kwargs):
        if restoring and text.startswith("TIME:RELTo"):
            suffix=text.removeprefix("TIME:RELTo")
            if suffix.endswith("?"):
                queries[self.name].append(int(suffix[:-1]))
            elif ignored==(self.name,int(suffix.split()[0])):
                return "0"  # Silent ignored restoration command.
        return original_command(self,text,**kwargs)
    def progress(message):
        nonlocal restoring
        if message.startswith("Restoration:"):
            restoring=True
            for timer in (bus.probe,bus.timer):
                timer.references={edge:edge for edge in range(1,9)}
    monkeypatch.setattr(Timer,"__init__",initialize)
    monkeypatch.setattr(Timer,"command",command)
    return progress,queries


@pytest.mark.parametrize("device",["t660_1","t660_2"])
@pytest.mark.parametrize("ignored_edge",[1,8])
def test_us_ignored_edge_reference_restore_retains_all_readbacks_and_faults(tmp_path,monkeypatch,device,ignored_edge):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,coordinator,bus,_=setup(tmp_path,installed=True)
    progress,queries=_observe_timer_reference_restoration(monkeypatch,bus,(device,ignored_edge))
    with pytest.raises(AcquisitionFailure,match=f"{device} TIME:RELTo{ignored_edge}") as failed:
        execute(context,inputs(),"preliminary",hardware=True,progress=progress)
    record=failed.value.record
    restoration=record["restoration"]
    assert record["disposition"]=="cleanup_failed"
    assert not restoration["safe_verified"] and not restoration["settings_restored"]
    assert coordinator.snapshot()["state"]=="fault" and record["native_path"]
    for name in ("t660_1","t660_2"):
        observed=restoration["verification"][name+" edge references"]
        assert set(observed)=={str(edge) for edge in range(1,9)}
        assert queries[name]==list(range(1,9))
        for edge in range(1,9):
            assert observed[str(edge)]["expected"]==edge-1
            assert observed[str(edge)]["actual"]==(edge if (name,edge)==(device,ignored_edge) else edge-1)
        original=restoration["original"][name]["readback"]["channels"]
        actual=restoration["verification"][name+" restored verified"]["channels"]
        for channel in "ABCD":
            for field in ("delay_edge","width_edge"):
                assert actual[channel][field]==original[channel][field]


def test_us_successful_edge_reference_restore_verifies_every_captured_edge(tmp_path,monkeypatch):
    monkeypatch.setattr(InstalledAcquirer,"wait",lambda self,*args:self.check())
    context,coordinator,bus,_=setup(tmp_path,installed=True)
    progress,queries=_observe_timer_reference_restoration(monkeypatch,bus)
    record=execute(context,inputs(),"preliminary",hardware=True,progress=progress)
    restoration=record["restoration"]
    assert record["disposition"]=="complete"
    assert restoration["safe_verified"] and restoration["settings_restored"]
    assert coordinator.snapshot()["state"]=="free"
    for name in ("t660_1","t660_2"):
        observed=restoration["verification"][name+" edge references"]
        assert set(observed)==set(restoration["original"][name]["edge_references"])
        assert queries[name]==list(range(1,9))
        assert all(item=={"expected":edge-1,"actual":edge-1} for edge,item in ((int(key),value) for key,value in observed.items()))
