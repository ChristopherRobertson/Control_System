"""Installed adapter E2E through genuine services and in-memory transports only."""
from copy import deepcopy
from dataclasses import replace
import math
import re

import numpy as np
import pytest

from control_app.devices.t660_service import T660Service
from control_app.devices.hf2li_service import HF2LIService
from control_app.devices.mircat_service import MircatService
from control_app.measurement_host.context import ContextFactory
from control_app.measurement_host.ownership import HardwareCoordinator, require_hardware_owner
from control_app.measurement_modules.nanosecond_stroboscopy.adapters import InstalledAdapter
from control_app.measurement_modules.nanosecond_stroboscopy.planner import build_plan
from control_app.measurement_modules.nanosecond_stroboscopy.runner import Runner
from control_app.measurement_modules.nanosecond_stroboscopy.settings import Settings
from control_app.measurement_modules.nanosecond_stroboscopy.persistence import NativeStore, load_run, read_json


class Bench:
    def __init__(self):
        self.units = {}; self.starts = 0; self.pending = False; self.clock = 1.; self.kind = "blank"
        self.optical_pulse_width_ns=100.;self.optical_current_ma=300.;self.optical_pulse_rate_hz=10000.
        self.qcl_calls=[];self.tuned_pulse_width_ns=None
        self.pulse_limits={"max_pulse_rate_hz":3000000.,"max_pulse_width_ns":500.,"max_duty_cycle":30.}
        self.nodes = {}; self.calls = []; self.broken_clock = False; self.refuse_dc = False
        self.missing_first_probe=False;self.shot_delta = 0; self.broken_restore = False; self.alternate_refs = False; self.refuse_oscselect = False; self.refuse_refs = False
    def start(self):
        self.starts += 1; self.pending = True
    def poll(self, duration, *unused):
        if not self.pending:
            times = self.clock + np.arange(1, 42)*.0005
            self.clock = times[-1]
            return self.streams(times, np.zeros(len(times)), np.zeros(len(times)))
        self.pending = False
        period = 1/self.units["t660_1"].frequency
        count = self.units["t660_2"].last+1
        times = self.clock + np.arange(1, int((count+1)*period/.0005)+1)*.0005
        sample, reference = np.zeros(len(times)), np.zeros(len(times))
        epochs = self.clock + .02 + np.arange(self.units["t660_1"].burst_pulses)*period
        for i, epoch in enumerate(epochs):
            if self.missing_first_probe and i==0:continue
            dt = times-epoch; positive = dt >= 0
            impulse = np.exp(-dt[positive]/.005)/.005
            magnitude = 1. if self.kind == "blank" else .8
            if self.kind == "measurement" and i == 1: magnitude *= .97
            sample[positive] += magnitude*impulse
            reference[positive] += impulse
        self.clock = times[-1]
        self.units["t660_1"].shots=count+17 # internal DDS continues after gated outputs finish
        self.units["t660_2"].shots = count+self.shot_delta; self.units["t660_2"].state = "DONE"
        return self.streams(times, sample, reference)
    def streams(self, times, sample, reference):
        streams = {f"/dev18500/demods/{demod}/sample": {"timestamp": np.round(times*210000000).astype(np.uint64),
                "x": values*.8+.05, "y": values*.6-.02} for demod, values in ((0,sample),(3,reference))}
        streams["/dev18500/demods/3/sample"]={key:value[::2] for key,value in streams["/dev18500/demods/3/sample"].items()}
        return streams


def seconds(v):
    for unit, factor in (("ns",1e-9),("us",1e-6),("ms",1e-3),("s",1.)):
        if str(v).endswith(unit): return float(str(v)[:-len(unit)])*factor
    return float(v)


class MemoryT660(T660Service):
    """Use genuine apply_recipe/preload/restore paths, emulate command transport."""
    def __init__(self, name, bench):
        super().__init__(name, {"role": "master_clock_and_pump_timing_trains_frames" if name == "t660_2" else "continuous_probe_reference_and_event_trigger"})
        self.bench=bench; bench.units[name]=self
        self.refs={i:0 if i%2 else i-1 for i in range(1,9)}
        self.rel={i: (20e-6 if name=="t660_2" and i==3 else 0.) if i%2 else 1e-6 for i in range(1,9)}
        if name=="t660_1" and bench.alternate_refs:
            self.refs[3]=1;self.rel[1]=7e-6;self.rel[3]=11e-6
        self.channels={c:{"enabled":"OFF","mode":"DW","polarity":"POS","termination":"ON"} for c in "ABCD"}
        self.frequency=10.; self.source="OFF"; self.state="OFF"; self.last=0; self.shots=0; self.predivider=1
        self.pending={}; self.queued={}
        self.burst_pulses=2;self.burst_triggers=3;self.burst_enabled="OFF";self.gate_mode=0
    def connect(self): require_hardware_owner(self)
    def close(self): self.bench.calls.append((self.name,"close"))
    def abs(self, i): return 0. if i==0 else self.rel[i]+self.abs(self.refs[i])
    def command(self, command, **kwargs):
        require_hardware_owner(self)
        self.bench.calls.append((self.name,command))
        if ";" in command: return ";".join(self.command(c) for c in command.split(";"))
        c=command.lstrip(":")
        if c=="*IDN?": return "Highland,T660,TEST,F5"
        if c=="FEATure:FRAMe?": return "1"
        if c=="TRIG:SOUR?": return self.source
        if c=="TRIG:FREQ:SYN?": return str(self.frequency)
        if c=="TRIG:SHOTS?": return str(self.shots)
        if c=="CLOCk:MODe?": return "IN" if self.name=="t660_1" else "OUT"
        if c=="CLOCk:EXTernaL?": return "ON"
        if c=="CLOCk:FREQuency?": return "10000000"
        if c=="CLOCk:STATus?": return "LOCKED"
        if c=="TRIGger:EXTernal:PREDiv?": return str(self.predivider)
        if c=="TRIGger:INPut:POLarity?": return "POS"
        if c=="TRIGger:INPut:TERMination?": return "50OHM"
        if c=="TRIGger:INPut:VOLTage?": return "2"
        if c=="GATE:MODe?": return str(self.gate_mode)
        if c=="BURst:MODe?": return self.burst_enabled
        if c=="BURst:PULse?":return str(self.burst_pulses)
        if c=="BURst:TRIGger?":return str(self.burst_triggers)
        if c=="TFRame:STATus?": return self.state
        if c=="TRAin:ACTive:CouNT?": return "0"
        if c in ("TFRame:LOOP:FIRST?","TFRame:LOOP:CouNT?"): return "0"
        if c=="TFRame:LOOP:LAST?": return str(self.last)
        match=re.match(r'TIME:RELTo(\d+)\?',c)
        if match:return str(self.refs[int(match[1])])
        match=re.match(r'TIME:RELTo(\d+) (\d+)',c)
        if match:
            edge,target=map(int,match.groups());
            if self.name=="t660_1" and self.bench.refuse_refs and edge==3 and target==0:return "OK"
            value=self.abs(edge)-self.abs(target);self.refs[edge]=target;self.rel[edge]=value;return "OK"
        match=re.match(r'TIME:DEL(\d+)\?',c)
        if match:return f"{self.rel[int(match[1])]:.15g}s"
        match=re.match(r'TIME:(?:DEL|QUEue)(\d+) (.*)',c)
        if match:
            edge=int(match[1]);value=seconds(match[2]);(self.queued if "QUEue" in c else self.rel)[edge]=value;return "OK"
        if c=="TIME:COMmit":self.rel.update(self.queued);self.queued={};return "OK"
        for field,pattern in (("enabled",r'CHAN:ON\? ([ABCD])'),("mode",r'CHAN:TimingMODe\? ([ABCD])'),("termination",r'CHAN:50OHM\? ([ABCD])'),("polarity",r'CHANnel:ACTive:POLarity\? ([ABCD])')):
            match=re.match(pattern,c)
            if match:return self.channels[match[1]][field]
        match=re.match(r'CHAN:(ON|OFF|POS|NEG|50OHM|LOwZ|DelayWidth|RiseFall) ([ABCD])',c)
        if match:
            cmd,ch=match.groups();field="enabled" if cmd in ("ON","OFF") else "polarity" if cmd in ("POS","NEG") else "termination" if cmd in ("50OHM","LOwZ") else "mode"
            self.channels[ch][field]={"50OHM":"ON","LOwZ":"OFF","DelayWidth":"DW","RiseFall":"RF"}.get(cmd,cmd)
            return "OK"
        if c.startswith("TRIG:SOUR "): self.source=c.split()[-1]
        if c.startswith("TRIG:FREQ:SYN "): self.frequency=float(c.split()[-1].removesuffix("Hz"))
        if c.startswith("TRIG:SHOTS "): self.shots=0
        if c.startswith("TFRame:LOOP:LAST "): self.last=int(c.split()[-1])
        if c.startswith("TRIGger:EXTernal:PREDiv "):self.predivider=int(c.split()[-1])
        if c=="TFRame:STArt":self.state="RUNNING"
        if c=="TFRame:STOp":self.state="OFF"
        if c.startswith("BURst:PULse "):self.burst_pulses=int(c.split()[-1])
        if c.startswith("BURst:TRIGger "):self.burst_triggers=int(c.split()[-1])
        if c.startswith("BURst:MODe "):self.burst_enabled=c.split()[-1]
        if c.startswith("GATE:MODe "):self.gate_mode=int(c.split()[-1])
        if c=="GATE:EXECute" and self.name=="t660_1":
            assert self.gate_mode==9 and self.burst_enabled=="ON" and self.burst_triggers==self.burst_pulses+1
            self.bench.start()
        return "OK"


class MemoryServer:
    def __init__(self,bench): self.bench=bench; self.nodes=bench.nodes
    def setInt(self,path,value):
        if self.bench.broken_restore and path.endswith("sigins/0/ac") and value==1:
            raise RuntimeError("injected original AC restore failure")
        if self.bench.refuse_oscselect and path.endswith("demods/0/oscselect") and value==0:value=1
        self.nodes[path]=int(value)
    def setDouble(self,path,value): self.nodes[path]=float(value)
    def getInt(self,path):
        if path.endswith("/clockbase"):return 210000000
        if path.endswith("/status/flags/plllock"):return int(self.bench.broken_clock)
        if path in self.nodes:return int(self.nodes[path])
        if path.endswith("/order"):return 1
        if path.endswith("/sigins/0/ac") or path.endswith("/sigins/1/ac"):return 1
        if path.endswith("/demods/3/adcselect"):return 1
        if path.endswith("/sinc"):return 1
        return 0
    def getDouble(self,path):
        if self.bench.refuse_dc and path.endswith("/oscs/0/freq") and self.nodes.get(path)==0:return 1.
        if path in self.nodes:return float(self.nodes[path])
        if path.endswith("/timeconstant"):return .005
        if path.endswith("demods/3/rate"):return 1000.
        if path.endswith("/rate"):return 2000.
        if path.endswith("/range"):return 1.
        if path.endswith("/freq"):return 2000000.
        return 0.
    def getString(self,path):return "test"
    def setString(self,path,value):self.nodes[path]=value
    def sync(self):pass
    def subscribe(self,path):pass
    def unsubscribe(self,path):pass
    def poll(self,*args):return self.bench.poll(*args)
    def disconnect(self):self.bench.calls.append(("hf2li","close"))


class MemoryHF(HF2LIService):
    def __init__(self,bench):super().__init__({"device_id":"18500"});self.bench=bench
    def connect(self):require_hardware_owner(self);self._server=MemoryServer(self.bench);self._device_id="dev18500"


class MemoryMircat(MircatService):
    """Strict SDK result shapes while emulating only physical I/O methods."""
    def __init__(self,bench):
        super().__init__({});self.bench=bench;self.emission=False;self.armed=False;self.wave=1942.
        self.trigger={"pulse_mode":0,"process_trigger_mode":0,"start":1942.,"stop":1942.,"interval":0.,"units":1,"dwell_us":0,"after_off_us":0}
    def initialize(self):require_hardware_owner(self)
    def deinitialize(self):self.bench.calls.append(("mircat","close"))
    def _qcl(self,index,action):
        self.bench.qcl_calls.append((action,index))
        assert index==1, "Legacy selectors must never route device I/O to another QCL"
    def get_num_installed_qcls(self):return 3 # historical controller metadata
    def get_active_qcl(self):return 2 # never use this historical selector for pulse reads
    def get_qcl_pulse_rate(self,qcl):
        self._qcl(qcl,"pulse_rate");return self.bench.optical_pulse_rate_hz
    def get_qcl_pulse_width(self,qcl):
        self._qcl(qcl,"pulse_width");return self.bench.optical_pulse_width_ns
    def get_qcl_current_limits(self,qcl):
        self._qcl(qcl,"current_limits");return (0., 1000.)
    def get_qcl_current(self,qcl):
        self._qcl(qcl,"current");return self.bench.optical_current_ma
    def get_qcl_tuning_range(self,qcl):
        self._qcl(qcl,"range");return {"qcl":1,"min_cm1":1900.,"max_cm1":2000.}
    def get_qcl_pulse_limits(self,qcl):
        self._qcl(qcl,"limits");return deepcopy(self.bench.pulse_limits)
    def get_wavelength_trigger_params(self):return deepcopy(self.trigger)
    def set_wavelength_trigger_params(self,**kwargs):self.trigger.update(kwargs);return deepcopy(self.trigger)
    def set_qcl_pulse_params(self,**kwargs):
        self._qcl(kwargs["qcl"],"set_params")
        self.bench.optical_pulse_rate_hz=kwargs["pulse_rate_hz"]
        self.bench.optical_pulse_width_ns=kwargs["pulse_width_ns"]
        self.bench.optical_current_ma=kwargs["current_ma"]
        return deepcopy(kwargs)
    def read_state(self):raise AssertionError("Generic legacy state getter may choose active QCL 2")
    def turn_emission_off(self):self.emission=False
    def is_connected(self):return True
    def _call(self,name,*args):
        require_hardware_owner(self)
        assert name=="MIRcatSDK_TurnEmissionOn"
        self.emission=True;return 0
    def is_emission_on(self):return self.emission
    def is_laser_armed(self):return self.armed
    def arm(self):self.armed=True
    def disarm(self):self.armed=False
    def get_system_error_word(self):return 0
    def is_interlock_set(self):return True
    def is_key_switch_set(self):return True
    def are_tecs_ready(self):return True
    def is_tuned(self):return True
    def tune_to_wavenumber(self,wavenumber_cm1,*,qcl):
        self._qcl(qcl,"tune");self.wave=wavenumber_cm1
        if self.bench.tuned_pulse_width_ns is not None:self.bench.optical_pulse_width_ns=self.bench.tuned_pulse_width_ns
    def get_actual_wavelength(self):return {"value":self.wave,"units":"cm^-1","light_valid":self.emission}


def live_context(tmp_path,bench,mode="dual"):
    owner=HardwareCoordinator(tmp_path/"owner.lock")
    factories={"hf2li":lambda **kw:MemoryHF(bench), "mircat":lambda **kw:MemoryMircat(bench),
        "t660_1":lambda **kw:MemoryT660("t660_1",bench), "t660_2":lambda **kw:MemoryT660("t660_2",bench)}
    context=ContextFactory(real_device_factories=factories,ownership=owner,save_root_provider=lambda:tmp_path/"output").for_experiment("nanosecond_stroboscopy").for_mode(mode)
    return context,owner


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_ns_real_installed_adapter_connected_blank_sample_and_raw_run(tmp_path, mode):
    bench=Bench();bench.alternate_refs=True;ctx,owner=live_context(tmp_path,bench,mode)
    settings=replace(Settings(mode=mode),wavenumbers_cm1=(1942.,),delays_ns=(-100.,100.),repetitions=1,
        cycle_interval_s=.1,reset_interval_s=0.)
    plan=build_plan(settings)
    assert plan.connected_ready and not plan.timing
    def run(kind,**kwargs):
        bench.kind=kind
        result=Runner(ctx).run(ctx.begin_operation(settings.to_dict(),hardware=True),plan,kind=kind,**kwargs)
        assert result["status"]=="completed",result["error"]
        assert owner.snapshot()["state"]=="free"
        return result
    blank=run("blank") if mode=="single" else None
    sample=run("preliminary",blank=blank)
    run_record=run("measurement",blank=blank,baseline=sample)
    assert run_record["baseline_comparison"]==[]
    assert isinstance(run_record["readbacks"]["capabilities"]["fire_to_q_ns"],float)
    assert run_record["readbacks"]["demodulation"]=="internal_zero_frequency"
    assert all(e["sample"]["estimator"]=="uncalibrated_complex_impulse_area" for e in run_record["events"])
    assert all(e["calibrated_optical_delay_ns"] is None for e in run_record["events"])
    assert all(e["sample"]["valid"][0] for e in run_record["events"])
    loaded=load_run(run_record["output_path"])
    np.testing.assert_array_equal(loaded["events"][0]["native_device_data"][0]["data"]["/dev18500/demods/0/sample"]["x"],
        run_record["events"][0]["native_device_data"][0]["data"]["/dev18500/demods/0/sample"]["x"])
    assert run_record["readbacks"]["hf2li"]["nodes"]["/dev18500/sigins/0/ac"]["value"]==0
    assert bench.nodes["/dev18500/sigins/0/ac"]==1 # restored original AC coupling
    assert bench.nodes["/dev18500/demods/0/sinc"]==1 # restored original sinc
    assert bench.starts>0
    assert bench.units["t660_1"].refs[3]==1
    assert bench.units["t660_1"].burst_pulses==2 and bench.units["t660_1"].burst_triggers==3
    assert sum(name=="t660_1" and command=="GATE:EXECute" for name,command in bench.calls)==bench.starts
    if mode=="dual":
        native=run_record["events"][0]["native_device_data"][1]["data"]
        assert len(native["/dev18500/demods/0/sample"]["timestamp"])>len(native["/dev18500/demods/3/sample"]["timestamp"])
        assert run_record["events"][0]["sample"]["timestamp_ticks"][0]==run_record["events"][0]["reference"]["timestamp_ticks"][0]
        assert np.all(run_record["result"]["coverage"]>0)


def test_ns_phase_laser_requests_reach_installed_adapter_and_restore(tmp_path, monkeypatch):
    monkeypatch.setattr(MemoryMircat, "get_qcl_current_limits", lambda self, qcl: (0., 500.))
    bench = Bench()
    ctx, owner = live_context(tmp_path, bench)
    settings = replace(Settings(mode="dual"), wavenumbers_cm1=(1942.,), delays_ns=(0.,),
        repetitions=1, cycle_interval_s=.1, laser_settings={"qcl_current_ma": 400., "probe_pulse_width_ns": 120.})
    result = Runner(ctx).run(ctx.begin_operation(settings.to_dict(), hardware=True), build_plan(settings), kind="preliminary")
    assert result["status"] == "completed", result["error"]
    assert result["readbacks"]["requested_mircat_pulse"]["pulse_width_ns"] == 142.
    assert result["readbacks"]["requested_mircat_pulse"]["current_ma"] == 400.
    assert bench.optical_pulse_width_ns == 100.
    assert bench.optical_current_ma == 300.
    assert owner.snapshot()["state"] == "free"


def test_ns_real_installed_dc_rejection_retains_failure_and_restores(tmp_path):
    bench=Bench();bench.refuse_dc=True;ctx,owner=live_context(tmp_path,bench)
    settings=replace(Settings(mode="dual"),wavenumbers_cm1=(1942.,),delays_ns=(0.,),repetitions=1,cycle_interval_s=.1)
    result=Runner(ctx).run(ctx.begin_operation(settings.to_dict(),hardware=True),build_plan(settings),kind="preliminary")
    assert result["status"]=="failed"
    assert "rejected internal DC" in result["error"]
    assert not bench.starts
    assert owner.snapshot()["state"]=="free"


def test_ns_external_pll_center_drift_does_not_fail_restoration(tmp_path, monkeypatch):
    original = MemoryServer.getDouble
    def read(self, path):
        if path.endswith("/plls/0/freqcenter"):
            return 1900000. + self.bench.clock
        return original(self, path)
    monkeypatch.setattr(MemoryServer, "getDouble", read)
    bench = Bench()
    context, owner = live_context(tmp_path, bench, "single")
    settings = replace(Settings(mode="single"), wavenumbers_cm1=(1942.,),
        delays_ns=(0.,), repetitions=1, cycle_interval_s=.1, reset_interval_s=0.)
    result = Runner(context).run(context.begin_operation(settings.to_dict(), hardware=True),
        build_plan(settings), kind="blank")
    assert result["status"] == "completed", result.get("error")
    assert owner.snapshot()["state"] == "free"
    assert ("mircat","close") in bench.calls


@pytest.mark.parametrize("fault", ["clock", "shots", "missing_prefix", "restore", "append", "abort"])
def test_ns_real_installed_fault_and_abort_preserve_native_and_attempt_cleanup(tmp_path, fault):
    bench=Bench();ctx,owner=live_context(tmp_path,bench)
    bench.broken_clock=fault=="clock";bench.shot_delta=int(fault=="shots");bench.broken_restore=fault=="restore"
    settings=replace(Settings(mode="dual"),wavenumbers_cm1=(1942.,),delays_ns=(0.,),repetitions=1,cycle_interval_s=.1)
    bench.missing_first_probe=fault=="missing_prefix"
    operation=ctx.begin_operation(settings.to_dict(),hardware=True)
    class Store(NativeStore):
        def append_event(self,event):
            if fault=="append":raise OSError("injected durable journal failure")
            super().append_event(event)
    class Worker:
        def check_cancelled(self):
            if fault=="abort" and bench.starts and not bench.pending:raise InterruptedError("injected operator Stop")
    result=Runner(ctx,store_factory=Store).run(operation,build_plan(settings),kind="preliminary",worker=Worker())
    assert result["status"]==("cancelled" if fault=="abort" else "failed"),result["error"]
    assert owner.snapshot()["state"]==("fault" if fault in ("restore","append") else "free")
    assert all((name,"close") in bench.calls for name in ("mircat","hf2li","t660_1","t660_2"))
    if fault=="clock":
        assert bench.starts==0
        assert result["readbacks"]["health"][-1]["clock_locked"] is False
    else:
        assert bench.starts==1
    retained=load_run(result["output_path"])
    if fault=="append":
        assert len(retained["events"])==1
        assert retained["preservation_verified"] is False
        np.testing.assert_array_equal(retained["events"][0]["sample"]["value"], result["events"][0]["sample"]["value"])
    if fault=="missing_prefix":
        assert len(retained["events"])==1
        assert not retained["events"][0]["sample"]["valid"][0]
        assert "pulse_assignment_unresolved" in retained["events"][0]["quality_flags"]
    if fault=="shots":
        assert not retained["events"]
        from pathlib import Path
        assert read_json(Path(result["output_path"])/"interrupted_native_tail.json")
    if fault in ("restore","append"):
        ctx.ownership.release(operation.ownership,safe_verified=True,preservation_verified=True,detail="Injected test teardown")


def test_ns_raw_area_preserves_integer_epoch_and_rejects_incomplete_support():
    clockbase=210000000;epoch_tick=2**60+17
    offsets=np.arange(-500,1801,dtype=np.int64)*105000
    times=offsets/clockbase
    impulse=np.where(times>=0,np.exp(-np.maximum(times,0)/.05)/.05,0.)
    stream={"timestamp":(np.uint64(epoch_tick)+offsets.astype(np.uint64)),"x":.2+impulse*.6,"y":-.1+impulse*.8}
    integrated=InstalledAdapter._raw_area(stream,epoch_tick/clockbase,1.,clockbase,epoch_ticks=epoch_tick)
    assert integrated["valid"][0]
    assert int(integrated["timestamp_ticks"][0])==epoch_tick
    assert integrated["value"][0]==pytest.approx(1.,abs=.006)
    assert integrated["signed_area_x"]/integrated["signed_area_y"]==pytest.approx(.75)
    truncated={key:value[times<=.4] for key,value in stream.items()}
    unsupported=InstalledAdapter._raw_area(truncated,epoch_tick/clockbase,1.,clockbase,epoch_ticks=epoch_tick)
    assert not unsupported["valid"][0]
    assert "truncated_native_aperture" in unsupported["quality_flags"]
    gap={key:np.delete(value,np.arange(700,730)) for key,value in stream.items()}
    unsupported=InstalledAdapter._raw_area(gap,epoch_tick/clockbase,1.,clockbase,epoch_ticks=epoch_tick)
    assert "native_sample_gap" in unsupported["quality_flags"]
    noisy={**stream,"x":np.sin(2*np.pi*times*73)*.1,"y":np.cos(2*np.pi*times*41)*.1}
    unsupported=InstalledAdapter._raw_area(noisy,epoch_tick/clockbase,1.,clockbase,epoch_ticks=epoch_tick)
    assert not unsupported["valid"][0]
    assert "low_snr_integrated_signal" in unsupported["quality_flags"]


def test_ns_raw_area_retains_nonreturning_detector_tail_without_ratio_support():
    times=np.arange(-.25,.901,.001)
    impulse=np.where(times>=0,np.exp(-np.maximum(times,0)/.5),0.)
    stream={"timestamp":np.round((times+1)*1000000).astype(np.uint64),"x":impulse,"y":impulse*.5}
    integrated=InstalledAdapter._raw_area(stream,1.,1.,1000000)
    assert integrated["value"][0]>0
    assert not integrated["valid"][0]
    assert "nonreturning_detector_tail" in integrated["quality_flags"]
    assert not integrated["tail_support"]["returned_to_baseline"]


@pytest.mark.parametrize("fault", ["oscselect", "references"])
def test_ns_live_actual_configuration_refusal_stops_before_any_pulses(tmp_path, fault):
    bench=Bench();bench.alternate_refs=True
    bench.refuse_oscselect=fault=="oscselect";bench.refuse_refs=fault=="references"
    ctx,owner=live_context(tmp_path,bench)
    settings=replace(Settings(mode="dual"),wavenumbers_cm1=(1942.,),delays_ns=(0.,),repetitions=1,cycle_interval_s=.1)
    operation=ctx.begin_operation(settings.to_dict(),hardware=True)
    result=Runner(ctx).run(operation,build_plan(settings),kind="preliminary")
    assert result["status"]=="failed"
    assert "internal DC oscillator" in result["error"] if fault=="oscselect" else "shot-relative" in result["error"]
    assert not bench.starts
    assert owner.snapshot()["state"]=="fault",result["error"]
    ctx.ownership.release(operation.ownership,safe_verified=True,preservation_verified=True,detail="Injected test teardown")


def test_ns_raw_burst_rejects_correct_count_at_inconsistent_physical_cadence():
    from types import SimpleNamespace
    adapter=object.__new__(InstalledAdapter)
    adapter.settings={"mode":"dual","optical_delay_offset_ns":None,"reset_interval_s":0.}
    adapter.plan=SimpleNamespace(timing={"frame_period_s":1.})
    adapter.readbacks={"clockbase":1000000.,"raw_kernel":{},"wavelength":{"wavenumber_cm1":1942.}}
    adapter.detector_settings={index:{"order":1,"timeconstant_s":.02,"rate_sps":1000.} for index in (0,3)}
    times=np.arange(0,5,.001);signal=np.zeros(len(times))
    for epoch in (.5,1.5,2.9,3.5):
        positive=times>=epoch
        signal[positive]+=np.exp(-(times[positive]-epoch)/.02)
    native={"timestamp":np.round(times*1000000).astype(np.uint64),"x":signal,"y":signal*.5}
    adapter.pending_native=[{"data":{f"/dev18500/demods/{index}/sample":deepcopy(native) for index in (0,3)}}]
    event={"frames":[{}]*4,"frame_index":1,"condition":"pump_on","quantized_delay_ns":0.,"requested_delay_ns":0.}
    result=adapter._extract_raw(event,"measurement")
    assert "probe_envelope_cadence_mismatch" in result["quality_flags"]
    assert not result["sample"]["valid"][0]
    assert result["native_device_data"][0]["data"]["/dev18500/demods/0/sample"]["timestamp"].dtype==np.uint64


@pytest.mark.parametrize("changed", ["optical_width", "optical_current", "input_range"])
def test_ns_live_changed_actual_instrument_settings_keep_raw_but_exclude_normalization(tmp_path, changed):
    bench=Bench();ctx,owner=live_context(tmp_path,bench,"single")
    settings=replace(Settings(mode="single"),wavenumbers_cm1=(1942.,),delays_ns=(0.,),repetitions=1,cycle_interval_s=.1)
    plan=build_plan(settings)
    def run(kind,**kwargs):
        bench.kind=kind
        result=Runner(ctx).run(ctx.begin_operation(settings.to_dict(),hardware=True),plan,kind=kind,**kwargs)
        assert result["status"]=="completed",result["error"]
        assert owner.snapshot()["state"]=="free"
        return result
    blank=run("blank")
    baseline=run("preliminary",blank=blank)
    if changed=="optical_width":bench.optical_pulse_width_ns=150.
    elif changed=="optical_current":bench.optical_current_ma=325.
    else:bench.nodes["/dev18500/sigins/0/range"]=2.
    result=run("measurement",blank=blank,baseline=baseline)
    assert result["baseline_comparison"]
    assert all("baseline_instrument_mismatch" in event["quality_flags"] for event in result["events"])
    assert all(event["sample"]["valid"][0] and event["sample"]["value"][0]>0 for event in result["events"])
    assert not np.any(result["result"]["coverage"])
    assert np.all(np.isnan(result["result"]["delta_a"]))
    assert load_run(result["output_path"])["events"][0]["native_device_data"]


@pytest.mark.parametrize("rate,width,vendor_duty,completed", [
    (600000.,500.,50.,True),
    (600000.01,500.,50.,False),
    (100000.,500.,4.,False),
    (1000001.,100.,50.,False),
    (10000.,2000.1,50.,False),
])
def test_ns_live_actual_optical_duty_is_inclusive_and_keeps_vendor_limits(tmp_path, rate, width, vendor_duty, completed):
    bench=Bench();bench.optical_pulse_rate_hz=rate;bench.optical_pulse_width_ns=width
    bench.pulse_limits={"max_pulse_rate_hz":3000000. if completed else 1000000.,"max_pulse_width_ns":2000.,"max_duty_cycle":vendor_duty}
    ctx,owner=live_context(tmp_path,bench)
    settings=replace(Settings(mode="dual"),wavenumbers_cm1=(1942.,),delays_ns=(0.,),repetitions=1,cycle_interval_s=.1)
    result=Runner(ctx).run(ctx.begin_operation(settings.to_dict(),hardware=True),build_plan(settings),kind="preliminary")
    assert result["status"]==("completed" if completed else "failed"),result["error"]
    assert owner.snapshot()["state"]=="free",result["error"]
    assert all(index==1 for _,index in bench.qcl_calls)
    if completed:
        pulse=result["readbacks"]["mircat_pulse"]
        assert pulse["configured_duty_cycle_fraction"]==pytest.approx(.2982)
        assert pulse["external_probe_rate_hz"]!=pulse["internal_rate_hz"]
        assert pulse["external_probe_duty_cycle_fraction"]<pulse["configured_duty_cycle_fraction"]
    else:
        assert not bench.starts
        assert not any(action=="set_params" for action,_ in bench.qcl_calls)


def test_ns_live_optical_duty_uses_fresh_post_tune_readback_then_restores_qcl1(tmp_path, monkeypatch):
    bench=Bench();bench.optical_pulse_rate_hz=600000.;bench.optical_pulse_width_ns=500.
    bench.tuned_pulse_width_ns=501.
    bench.pulse_limits={"max_pulse_rate_hz":3000000.,"max_pulse_width_ns":2000.,"max_duty_cycle":50.}
    original = MemoryMircat.set_qcl_pulse_params
    def corrupt_readback(self, **kwargs):
        result = original(self, **kwargs)
        if kwargs["pulse_width_ns"] == 142.:
            self.bench.optical_pulse_width_ns = 501.
        return result
    monkeypatch.setattr(MemoryMircat, "set_qcl_pulse_params", corrupt_readback)
    ctx,owner=live_context(tmp_path,bench)
    settings=replace(Settings(mode="dual"),wavenumbers_cm1=(1942.,),delays_ns=(0.,),repetitions=1,cycle_interval_s=.1)
    result=Runner(ctx).run(ctx.begin_operation(settings.to_dict(),hardware=True),build_plan(settings),kind="preliminary")
    assert result["status"]=="failed" and "readback differs" in result["error"]
    assert result["readbacks"]["requested_mircat_pulse"]["pulse_width_ns"]==142.
    assert not bench.starts
    assert ("set_params",1) in bench.qcl_calls
    assert bench.optical_pulse_width_ns==500.
    assert owner.snapshot()["state"]=="free",result["error"]


@pytest.mark.parametrize("wave,completed", [(1942.,True),(2050.,False)])
def test_ns_live_legacy_selectors_never_choose_a_second_qcl(tmp_path,wave,completed):
    bench=Bench();ctx,owner=live_context(tmp_path,bench)
    settings=replace(Settings(mode="dual"),wavenumbers_cm1=(wave,),delays_ns=(0.,),repetitions=1,cycle_interval_s=.1,
                     metadata={"qcl":2,"preferred_qcl":2,"active_qcl":2,"historical_qcl2_range_cm1":[2000.,2100.]})
    settings=Settings.from_dict({**settings.to_dict(),"qcl":2,"overrides":{"qcl_index":3}})
    assert settings.qcl==1
    result=Runner(ctx).run(ctx.begin_operation(settings.to_dict(),hardware=True),build_plan(settings),kind="preliminary")
    assert result["status"]==("completed" if completed else "failed"),result["error"]
    assert all(index==1 for _,index in bench.qcl_calls)
    assert owner.snapshot()["state"]=="free"
    if completed:
        assert ("tune",1) in bench.qcl_calls
        assert result["readbacks"]["wavelength"]["qcl"]==1
        assert result["settings"]["metadata"]["preferred_qcl"]==2 # retained annotation
    else:
        assert "QCL 1 tuning range" in result["error"]
        assert not bench.starts and not any(action=="tune" for action,_ in bench.qcl_calls)


def test_ns_optical_duty_checks_external_cadence_independently_and_exactly():
    from control_app.measurement_modules.nanosecond_stroboscopy.adapters import _validate_optical_pulses, ReadinessError
    limits={"max_pulse_rate_hz":1000000.,"max_pulse_width_ns":2000.,"max_duty_cycle":50.}
    assert _validate_optical_pulses(10000.,500.,600000.,limits)["external_probe_duty_cycle_fraction"]==pytest.approx(.30)
    with pytest.raises(ReadinessError,match="External probe cadence.*30%"):
        _validate_optical_pulses(10000.,500.,600000.0000000001,limits)
    with pytest.raises(ReadinessError,match="configured optical pulse rate.*30%"):
        _validate_optical_pulses(600000.0000000001,500.,10.,limits)
