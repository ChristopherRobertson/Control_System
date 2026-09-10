"""Owned, stationary-wavenumber acquisition using the installed device services.

HF2LI poll timestamps are retained in their original clock domain. DIO17 is an
electrical Variable Sync observation; an optional latency calibration can locate
an estimated sample pump arrival, but never turns it into an optical observation.
No host timer schedules an optical edge and no biological event is retried.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from io import StringIO
import math
import time
from typing import Any

import numpy as np


class AcquisitionStopped(Exception):
    """Normal operator cancellation, with all partial records retained."""


class AcquisitionIntegrityError(RuntimeError):
    pass


def data(value):
    from control_app.measurement_host.context import thaw_data
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return thaw_data(asdict(value) if is_dataclass(value) else value)


def _value(settings, group, *names, default=None):
    section = settings.get(group, {})
    for name in names:
        if name in section:
            return section[name]
    return default


def _response(mapping, key):
    item = mapping.get(key, {})
    if not item.get("ok"):
        raise AcquisitionIntegrityError(f"Missing successful readback: {key}: {item}")
    return str(item["response"]).strip()


def _number(value):
    from control_app.devices.t660_service import _seconds_value
    return _seconds_value(value)


def _equal(expected, actual, label, *, tolerance=1e-8):
    if isinstance(expected, (float, int)) and not isinstance(expected, bool):
        matched = actual is not None and math.isfinite(float(actual)) and math.isclose(
            float(expected), float(actual), rel_tol=tolerance, abs_tol=1e-12)
    else:
        matched = expected == actual
    if not matched:
        raise AcquisitionIntegrityError(f"{label}: selected {expected!r}, readback {actual!r}")


def assemble_streams(polls, device_id, clockbase):
    """Concatenate observed fields without sorting, deduplication or gap filling."""
    result = {}
    for role, index in (("sample", 0), ("reference", 3), ("timing", 2)):
        entries = []
        path = f"/{device_id}/demods/{index}/sample".lower()
        for poll in polls:
            for name, value in poll.get("data", {}).items():
                if name.lower() == path and isinstance(value, dict):
                    entries.append(value)
        stream = {}
        for name in {k for entry in entries for k in entry}:
            arrays = [np.asarray(entry[name]).reshape(-1) for entry in entries if name in entry]
            if arrays:
                stream[name] = np.concatenate(arrays)
        if "timestamp" in stream:
            stream["timestamp_ticks"] = stream["timestamp"].copy()
            stream["timestamp_s"] = stream["timestamp"].astype(np.float64) / clockbase
        result[role] = stream
    return result


def electrical_edges(timing, bit=17):
    ticks = np.asarray(timing.get("timestamp_s", []), dtype=float)
    dio = np.asarray(timing.get("dio", []), dtype=np.uint64)
    if ticks.size != dio.size or ticks.size < 2:
        return np.array([], dtype=float)
    high = (dio & (np.uint64(1) << np.uint64(bit))) != 0
    return ticks[1:][high[1:] & ~high[:-1]]


class InstalledAcquirer:
    """All services are fresh context-owned factories, including injected tests."""

    def __init__(self, context, operation, settings, profile, *, cancel, progress):
        self.context, self.operation = context, operation
        self.settings, self.profile = data(settings), deepcopy(profile)
        self.profile.update(self.profile.get("timing", {}))
        # A historical checkbox is not a measured response calibration.
        self.settings["response"]["qualified"]=False
        self.settings["response"]["qualification_id"]=""
        self.cancel, self.progress = cancel, progress
        self.devices, self.original, self.readbacks = {}, {}, {}
        self.log = StringIO()
        self.current_block = None
        self.clockbase = None
        self.preset = None

    def check(self):
        if self.cancel():
            raise AcquisitionStopped("Acquisition stopped")

    def wait(self, seconds, stage):
        """Interruptible settling/recovery only; this never schedules device edges."""
        self.check()
        self.progress(stage)
        until = time.monotonic() + max(0, seconds)
        while time.monotonic() < until:
            self.check()
            time.sleep(min(.02, max(0, until-time.monotonic())))

    def _wait_for(self, callback, timeout, label):
        self.check()
        until = time.monotonic() + timeout
        while not callback():
            self.check()
            if time.monotonic() >= until:
                raise AcquisitionIntegrityError(label)
            time.sleep(.02)

    def _create(self, name):
        self.check()
        device = self.context.devices.create(name, self.operation, command_log=self.log)
        self.devices[name] = device  # Keep even a partly connected service for cleanup.
        return device

    def _snapshot_timer(self, unit):
        snapshot = unit.read_active_settings()
        query = snapshot["queries"]
        recipe = {"stop_first": True, "trigger_source": "OFF", "gate_mode": 0,
                  "burst_enabled": False, "predivider": int(_response(query, "predivider")),
                  "clock": {"frequency": _response(query, "synth_frequency")}, "channels": {}}
        for channel, observed in snapshot["channels"].items():
            recipe["channels"][channel] = {"enabled": False, "delay": _response(observed, "delay_edge"),
                "width": _response(observed, "width_edge"), "polarity": _response(observed, "polarity"),
                "termination": _response(observed, "termination"), "timing_mode": _response(observed, "timing_mode")}
        recipe["external_trigger"] = {"polarity": _response(query, "trigger_input_polarity"),
            "termination": _response(query, "trigger_input_termination"),
            "threshold_v": float(_response(query, "trigger_input_threshold_v"))}
        references = {str(edge): int(unit.command(f"TIME:RELTo{edge}?")) for edge in range(1, 9)}
        self.original[unit.name] = {"readback": snapshot, "recipe": recipe, "edge_references": references}

    def _verify_timer(self, unit, recipe):
        actual = unit.read_active_settings()
        if "trigger_source" in recipe:
            _equal(recipe["trigger_source"], _response(actual["queries"], "trigger_source"), unit.name+" source")
        if "predivider" in recipe:
            _equal(recipe["predivider"],int(_response(actual["queries"],"predivider")),unit.name+" predivider")
        if "clock" in recipe:
            frequency = lambda value:float(str(value).lower().removesuffix("hz"))
            _equal(frequency(recipe["clock"]["frequency"]),frequency(_response(actual["queries"],"synth_frequency")),unit.name+" frequency")
        for channel, selected in recipe.get("channels", {}).items():
            observed = actual["channels"][channel]
            state = _response(observed, "enabled").upper()
            if state not in ("0", "1", "ON", "OFF"):
                raise AcquisitionIntegrityError(f"Unrecognized channel state: {state}")
            _equal(bool(selected["enabled"]), state in ("1", "ON"), unit.name+" "+channel)
            for key, field in (("delay", "delay_edge"), ("width", "width_edge")):
                if key in selected:
                    _equal(_number(selected[key]), _number(_response(observed, field)), unit.name+" "+channel+key)
            if "polarity" in selected:
                from control_app.devices.t660_service import _normalize_polarity
                _equal(_normalize_polarity(selected["polarity"],field="polarity"),
                    _normalize_polarity(_response(observed,"polarity"),field="polarity"),unit.name+" "+channel+" polarity")
            if "termination" in selected:
                from control_app.devices.t660_service import _normalize_channel_termination
                _equal(_normalize_channel_termination(selected["termination"]),
                    _normalize_channel_termination(_response(observed,"termination")),unit.name+" "+channel+" termination")
        return actual

    def prepare(self, program):
        self.progress("Configuration: preserving original settings and inhibiting sources")
        for name in ("t660_2", "t660_1"):
            unit = self._create(name)
            unit.connect()
            configured = self.operation.configuration.get("devices", {}).get(name, {})
            serial = configured.get("serial_number")
            identity = unit.identify()
            if serial and str(serial) not in [part.strip() for part in identity.split(",")]:
                raise AcquisitionIntegrityError(f"Unexpected {name} identity: {identity}")
            self._snapshot_timer(unit)
            unit.set_trigger_source("OFF")
            unit.command("STOP", expect_response=False)
            for channel in "ABCD":
                unit.disable_channel(channel)
        probe = self.devices["t660_1"]
        # Pending recipes are absolute from each trigger; stale rising-edge
        # references from manual work must not alter this method's timing.
        for edge in (1,3,5,7):
            probe.command(f"TIME:RELTo{edge} 0",expect_response=False)
        recipe = deepcopy(program.t6601_recipe)
        recipe["trigger_source"] = "OFF"
        for channel in "BCD":
            recipe["channels"][channel]["enabled"] = False
        probe.apply_recipe(recipe)
        self.readbacks["probe_reference_only"] = self._verify_timer(probe, recipe)
        probe.start_continuous_clock()
        self.probe_recipe = deepcopy(program.t6601_recipe)
        self.readbacks["requested_probe_recipe"]=deepcopy(program.t6601_recipe)
        observed_probe=self.readbacks["probe_reference_only"]
        self.probe_recipe["clock"]["frequency"]=_response(observed_probe["queries"],"synth_frequency")
        self.probe_recipe["channels"]["B"]["width"]=_response(observed_probe["channels"]["B"],"width_edge")

        laser = self._create("mircat")
        laser.initialize()
        self.check()
        self.original["mircat"] = {"state": self._laser_state(),
            "trigger": laser.get_wavelength_trigger_params(), "qcls": []}
        laser.stop_scan_if_needed()
        laser.turn_emission_off()
        self.original["mircat"]["qcls"].append({"qcl": 1,
            "pulse_rate_hz": laser.get_qcl_pulse_rate(1),
            "pulse_width_ns": laser.get_qcl_pulse_width(1), "current_ma": laser.get_qcl_current(1)})
        self._laser_integrity(require_tuned=False)
        laser.arm()
        self._wait_for(laser.are_tecs_ready, self.profile.get("tune_timeout_s", 45), "MIRcat TEC not ready")

        hf = self._create("hf2li")
        hf.connect()
        from control_app.devices.hf2li_service import HF2LIPreset
        self.preset = HF2LIPreset("microsecond-stroboscopy-owned-snapshot", {
            "demodulators": [{"index": i,"sinc":False,"phaseshift":0.} for i in range(6)]})
        original = hf.export_settings_snapshot(preset=self.preset)
        if original.get("read_errors"):
            raise AcquisitionIntegrityError(f"Cannot preserve HF2LI settings: {original['read_errors']}")
        self.original["hf2li"] = original
        config = self._hf_configuration(original,program)
        phases = config.get("phase_shift_deg",{})
        for index in (0,3) if self.settings["mode"]=="dual" else (0,):
            path = f"/{hf.device_id}/demods/{index}/phaseshift"
            original["nodes"][path] = {"type":"double","value":hf._get_node("double",path)}
            phase = phases.get(str(index),phases.get(index))
            if phase is not None:
                hf._set_node("setDouble",path,phase)
                hf.sync()
                _equal(phase,hf._get_node("double",path),"HF2LI selected phase")
        response = self.settings["response"]
        demods = []
        active = {0, 2, 3} if self.settings["mode"] == "dual" else {0, 2}
        for index in range(6):
            demod = {"index": index, "enable": index in active, "trigger": 0}
            if index in active:
                role = "reference" if index == 3 else "sample"
                demod.update(adcselect=1 if index == 3 else 0, oscselect=0, harmonic=1,
                    sinc=False,
                    order=response["reference_order"] if index == 3 else response["hf2_order"],
                    timeconstant_s=response["reference_time_constant_s"] if index == 3 else response["hf2_time_constant_s"],
                    rate_sps=response["timing_rate_sps"] if index == 2 else response[role+"_rate_sps"])
            demods.append(demod)
        config["demodulators"] = demods
        hf.apply_preset(HF2LIPreset("microsecond-stroboscopy-installed", config))
        actual = hf.export_settings_snapshot(preset=self.preset)
        for path in original["nodes"]:
            if path.endswith("/phaseshift"):
                actual["nodes"][path]={"type":"double","value":hf._get_node("double",path)}
        if actual.get("read_errors"):
            raise AcquisitionIntegrityError("HF2LI configuration readback failed")
        for entry in demods:
            for key, node in (("enable", "enable"), ("adcselect", "adcselect"), ("oscselect", "oscselect"),
                ("order", "order"), ("harmonic", "harmonic"), ("trigger", "trigger"), ("sinc","sinc"),
                ("timeconstant_s", "timeconstant"), ("rate_sps", "rate")):
                if key in entry:
                    selected = int(entry[key]) if key == "enable" else entry[key]
                    item = actual.get("nodes", {}).get(f"/{hf.device_id}/demods/{entry['index']}/{node}", {})
                    value=item.get("value")
                    if key in ("timeconstant_s","rate_sps","order") and entry["enable"]:
                        if not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
                            raise AcquisitionIntegrityError(f"Invalid actual HF2LI demod {entry['index']} {node}: {value!r}")
                        if key=="order" and (int(value)!=value or not 1<=value<=8):
                            raise AcquisitionIntegrityError("HF2LI actual filter order is outside supported bounds")
                    else:
                        _equal(selected,value,f"HF2LI demod {entry['index']} {node}")
        for entry in config.get("signal_inputs", {}).values():
            for key, node in (("ac", "ac"), ("impedance_50ohm", "imp50"), ("differential", "diff"), ("range_v", "range")):
                if key in entry:
                    _equal(int(entry[key]) if isinstance(entry[key], bool) else entry[key],
                        actual["nodes"].get(f"/{hf.device_id}/sigins/{entry['index']}/{node}", {}).get("value"), "HF2LI "+node)
        self.clockbase = hf.get_clockbase()
        if not math.isfinite(self.clockbase) or self.clockbase <= 0:
            raise AcquisitionIntegrityError("Invalid HF2LI clockbase")
        self.readbacks["hf2li"] = actual
        self.readbacks["hf2li_device"] = hf.device_id
        self.readbacks["signed_x_calibration_id"] = config.get("signed_x_calibration_id")
        self.readbacks["hf2li_requested"]=deepcopy(config)
        response_fields={0:{"order":"hf2_order","timeconstant":"hf2_time_constant_s","rate":"sample_rate_sps"},
                         3:{"order":"reference_order","timeconstant":"reference_time_constant_s","rate":"reference_rate_sps"},
                         2:{"rate":"timing_rate_sps"}}
        for index,fields in response_fields.items():
            if index not in active:
                continue
            for node,field in fields.items():
                self.settings["response"][field]=actual["nodes"][f"/{hf.device_id}/demods/{index}/{node}"]["value"]
        self.settings["timing"]["probe_rate_hz"]=float(self.probe_recipe["clock"]["frequency"].lower().removesuffix("hz"))
        self.settings["timing"]["probe_width_ns"]=float(Decimal(str(_number(self.probe_recipe["channels"]["B"]["width"]))) * Decimal("1e9"))
        self.readbacks["actual_settings"]=deepcopy(self.settings)
        self._wait_for(lambda:math.isclose(hf.get_oscillator_frequency(0),program.input_frequency_hz,rel_tol=.001),
                       10.,"HF2LI did not follow the active DIO0 reference")
        self._input_integrity()
        self.check()
        return self.readbacks

    def _hf_configuration(self, snapshot, program):
        """Preserve installed receiver settings; configure the wired DIO0 PLL."""
        hf=self.devices["hf2li"]
        config=deepcopy(self.profile.get("hf2li",{}))
        nodes=snapshot["nodes"]
        def observed(path):
            if path not in nodes:
                raise AcquisitionIntegrityError(f"Required connected configuration readback missing: {path}")
            return nodes[path]["value"]
        if not config.get("signal_inputs"):
            config["signal_inputs"]={}
            for index,role in ((0,"sample"),(1,"reference")):
                config["signal_inputs"][role]={"index":index,
                    **{key:observed(f"/{hf.device_id}/sigins/{index}/{node}") for key,node in
                       (("ac","ac"),("impedance_50ohm","imp50"),("differential","diff"),("range_v","range"))}}
        # The maintained wiring sends T660-1 A to DIO0; HF2 adcselect 4 is
        # its digital external-reference input. This is a device configuration,
        # not a claim about optical pulse timing or sample state.
        pll={"index":0,"enable":True,"adcselect":4,"harmonic":1,
             "order":observed(f"/{hf.device_id}/plls/0/order"),
             "adcthreshold":observed(f"/{hf.device_id}/plls/0/adcthreshold")}
        pll.update(config.get("pll",{}))
        pll["freqcenter_hz"]=program.input_frequency_hz
        config["pll"]=pll
        return config

    def _laser_state(self):
        """Physical state without the shared widget's active-QCL pulse reads."""
        laser=self.devices["mircat"]
        state={}
        errors={}
        for field,callback in (("armed",laser.is_laser_armed),("emission_on",laser.is_emission_on),
                               ("scan_waiting_process_trigger",laser.get_scan_waiting_process_trigger)):
            try:
                state[field]=callback()
            except Exception as exc:
                state[field]=None
                errors[field]=str(exc)
        try:
            scan=laser.get_scan_status()
        except Exception as exc:
            scan={}
            errors["scan_status"]=str(exc)
        for field in ("scan_in_progress","scan_active","scan_paused"):
            state[field]=scan.get(field)
        if errors:
            state["read_errors"]=errors
        return state

    def _verify_probe_limits(self,rate,width,limits,role="External probe"):
        numeric=(rate,width,limits["max_pulse_rate_hz"],limits["max_pulse_width_ns"],limits["max_duty_cycle"])
        if not all(isinstance(value,(float,int)) and math.isfinite(value) and value>0 for value in numeric):
            raise AcquisitionIntegrityError(f"Invalid {role} parameters or MIRcat QCL 1 limits")
        duty=Decimal(str(rate))*Decimal(str(width))*Decimal("1e-9")
        allowed=min(Decimal("0.30"),Decimal(str(self.settings["timing"]["maximum_probe_duty_fraction"])))
        if duty>allowed:
            raise AcquisitionIntegrityError(f"{role} exceeds MIRcat duty fraction limit (at most 0.30)")
        if rate>limits["max_pulse_rate_hz"] or width>limits["max_pulse_width_ns"] or duty*100>Decimal(str(limits["max_duty_cycle"])):
            raise AcquisitionIntegrityError(f"{role} exceeds installed MIRcat rate/width/duty limits")

    def _laser_integrity(self, require_tuned=True):
        laser = self.devices["mircat"]
        if not laser.is_interlock_set() or not laser.is_key_switch_set() or laser.get_system_error_word():
            raise AcquisitionIntegrityError("MIRcat interlock, key or system error")
        if require_tuned and not laser.is_tuned():
            raise AcquisitionIntegrityError("MIRcat lost tuned state")

    def _input_integrity(self):
        hf = self.devices["hf2li"]
        expected = self.probe_recipe["clock"]["frequency"]
        rate = float(str(expected).lower().removesuffix("hz"))
        if not math.isclose(hf.get_oscillator_frequency(0), rate, rel_tol=.001):
            raise AcquisitionIntegrityError("HF2LI lost external reference lock")
        health=hf.read_acquisition_health(reference_pll=0,input_indices=(0,1) if self.settings["mode"]=="dual" else (0,))
        self.readbacks.setdefault("health_observations",[]).append(deepcopy(health))
        if self.current_block is not None:
            self.current_block.setdefault("health_observations",[]).append(deepcopy(health))
        if health.get("overload") is True:
            raise AcquisitionIntegrityError("HF2LI signal input ADC clipping / overload")
        if health.get("reference_locked") is False or health.get("clock_locked") is False:
            raise AcquisitionIntegrityError("HF2LI reported loss of reference or internal clock lock")
        unknown=[key for key in ("reference_locked","clock_locked","overload") if health.get(key) is None]
        if unknown and self.current_block is not None:
            flag="health_status_unknown"
            if flag not in self.current_block.setdefault("flags",[]):
                self.current_block["flags"].append(flag)

    def tune(self, wavenumber):
        self.check()
        self.progress(f"Tuning / settling: {wavenumber:g} cm⁻¹")
        probe, laser = self.devices["t660_1"], self.devices["mircat"]
        probe.disable_channel("B")
        probe.disable_channel("C")
        laser.turn_emission_off()
        selected = 1  # Exactly one installed QCL; saved channel hints cannot reroute it.
        tuning_range=laser.get_qcl_tuning_range(1)
        if not tuning_range["min_cm1"]<=wavenumber<=tuning_range["max_cm1"]:
            raise AcquisitionIntegrityError("Installed QCL 1 does not cover requested wavenumber")
        timing = self.settings["timing"]
        rate = float(str(self.probe_recipe["clock"]["frequency"]).lower().removesuffix("hz"))
        width = timing["mircat_pulse_width_ns"]
        trigger_width=timing["probe_width_ns"]
        limits = laser.get_qcl_pulse_limits(selected)
        self._verify_probe_limits(rate,width,limits)
        # Internal pulse parameters are a separate device constraint. The T660
        # carrier controls external timing and must retain internal rate headroom.
        internal_rate=self.profile.get("mircat_internal_rate_hz",laser.get_qcl_pulse_rate(1))
        internal_width=width
        self._verify_probe_limits(internal_rate,internal_width,limits,"MIRcat internal pulse")
        if internal_rate<=rate:
            raise AcquisitionIntegrityError("MIRcat internal pulse rate must be strictly greater than the external trigger rate")
        current = self.profile.get("qcl_current_ma",laser.get_qcl_current(selected))
        low,high = laser.get_qcl_current_limits(selected)
        if not low<=current<=high:
            raise AcquisitionIntegrityError("Selected MIRcat current exceeds installed QCL limits")
        laser.set_qcl_pulse_params(qcl=1, pulse_rate_hz=internal_rate, pulse_width_ns=internal_width,
            current_ma=self.profile.get("qcl_current_ma"))
        def verify_internal():
            current_limits=laser.get_qcl_current_limits(1)
            pulse_limits=laser.get_qcl_pulse_limits(1)
            actual={"qcl":1,"pulse_rate_hz":laser.get_qcl_pulse_rate(1),
                "pulse_width_ns":laser.get_qcl_pulse_width(1),"current_ma":laser.get_qcl_current(1),
                "external_probe_rate_hz":rate,"probe_trigger_width_ns":trigger_width,
                "limits":deepcopy(pulse_limits),"current_limits_ma":list(current_limits),"maximum_duty_fraction":.30}
            self.readbacks["mircat_qcl"]=1
            self.readbacks["mircat_pulse_parameters"]=actual
            _equal(internal_rate,actual["pulse_rate_hz"],"MIRcat internal pulse rate",tolerance=1e-6)
            _equal(internal_width,actual["pulse_width_ns"],"MIRcat internal width",tolerance=1e-6)
            _equal(current,actual["current_ma"],"MIRcat QCL 1 current",tolerance=1e-6)
            self._verify_probe_limits(actual["pulse_rate_hz"],actual["pulse_width_ns"],pulse_limits,"MIRcat internal pulse readback")
            self._verify_probe_limits(rate,actual["pulse_width_ns"],pulse_limits,"Emitted optical pulse readback")
            if actual["pulse_rate_hz"]<=rate:
                raise AcquisitionIntegrityError("MIRcat internal pulse rate readback must be strictly greater than the external trigger rate")
            if not current_limits[0]<=actual["current_ma"]<=current_limits[1]:
                raise AcquisitionIntegrityError("MIRcat current readback exceeds installed QCL 1 limits")
            self.settings["timing"]["probe_rate_hz"]=rate
            self.settings["timing"]["probe_width_ns"]=trigger_width
            self.settings["timing"]["mircat_pulse_width_ns"]=actual["pulse_width_ns"]
            self.readbacks["actual_settings"]=deepcopy(self.settings)
        verify_internal()
        trigger = laser.set_external_trigger_params(wavenumber_cm1=wavenumber)
        from control_app.devices.mircat_service import PULSE_MODE_EXTERNAL_TRIGGER, PROC_TRIG_MODE_INTERNAL
        _equal(PULSE_MODE_EXTERNAL_TRIGGER, trigger.get("pulse_mode"), "MIRcat external pulse mode")
        _equal(PROC_TRIG_MODE_INTERNAL, trigger.get("process_trigger_mode"), "MIRcat stationary process mode")
        laser.tune_to_wavenumber(wavenumber, qcl=selected)
        self._wait_for(laser.is_tuned, self.profile.get("tune_timeout_s", 45), "MIRcat tune timeout")
        self._laser_integrity()
        verify_internal()
        self.check()
        laser.start_emission()
        probe.enable_channel("B")
        self.wait(self.profile.get("settle_s", 0), "Settling: requested optical and detector interval")
        actual = laser.get_actual_wavelength()
        if actual.get("units") != "cm^-1" or not actual.get("light_valid") or abs(actual["value"]-wavenumber) > self.profile["tune_tolerance_cm1"]:
            raise AcquisitionIntegrityError(f"MIRcat actual wavenumber/light-valid mismatch: {actual}")
        self.readbacks["wavenumber"] = actual
        return actual

    def observe(self, duration, block):
        """Unpumped control with probe operating and pump source inhibited."""
        self.current_block = block
        block.update(raw_polls=[], flags=[], readbacks=deepcopy(self.readbacks))
        hf, timer = self.devices["hf2li"], self.devices["t660_2"]
        self.devices["t660_1"].disable_channel("C")
        timer.set_trigger_source("OFF")
        hf.start_acquisition(demodulators=[0, 2, 3] if self.settings["mode"] == "dual" else [0, 2])
        try:
            # Duration is data collection, not a pump/probe edge schedule.
            remaining = duration
            while remaining > 0:
                self.check()
                period = min(.05, remaining)
                block["raw_polls"].append(hf.read_acquisition(period))
                self._input_integrity()
                self._laser_integrity()
                remaining -= period
        finally:
            block.update(assemble_streams(block["raw_polls"], hf.device_id, self.clockbase))
            if self.settings["mode"] == "single":
                block["reference"] = None
            hf.stop_acquisition()
        self._assign_timing(block)
        self._verify_native(block)
        return block

    def capture(self, program, block):
        self.current_block = block
        block["raw_polls"] = []
        block["flags"] = []
        block["program"] = data(program)
        block["readbacks"] = deepcopy(self.readbacks)
        self.check()
        timer, probe, hf = self.devices["t660_2"], self.devices["t660_1"], self.devices["hf2li"]
        probe.disable_channel("C")
        self.progress("Timing-table upload: acknowledged pending-field frames")
        block["timing_upload"] = program.upload(timer,
            progress=lambda done, total: self.progress(f"Timing-table upload: {done}/{total} acknowledged frames"),
            cancel_check=self.check)
        self._input_integrity()
        self._laser_integrity()
        self.progress("Acquisition: HF2LI native sample/reference and electrical timing streams")
        hf.start_acquisition(demodulators=[0, 2, 3] if self.settings["mode"] == "dual" else [0, 2], fields=["x", "y", "dio"])
        try:
            # Subscribe/sync and retain an observed baseline before enabling the
            # finite frame engine. All later edges come from the uploaded table.
            block["raw_polls"].append(hf.read_acquisition(.02))
            self.check()
            timer.start_frame_table()
            probe.enable_channel("C")
            duration = getattr(program, "capture_duration_s", getattr(program, "duration_s", None))
            deadline = time.monotonic() + duration + self.profile.get("capture_timeout_margin_s", 5)
            while True:
                self.check()
                block["raw_polls"].append(hf.read_acquisition(min(.05, duration)))
                self._input_integrity()
                self._laser_integrity()
                state = timer.get_frames_status()
                if state == "ERROR":
                    raise AcquisitionIntegrityError("T660 frame engine error")
                if state == "DONE":
                    # Terminal frame is inert. Preserve any final buffered
                    # samples before stopping the subscription.
                    block["raw_polls"].append(hf.read_acquisition(.02))
                    break
                if time.monotonic() >= deadline:
                    raise AcquisitionIntegrityError("Finite timing block did not finish")
            block["shot_counter_readback"] = timer.get_shot_count()
            if block["shot_counter_readback"] != program.physical_frame_count:
                raise AcquisitionIntegrityError("T660 accepted-trigger count differs from physical frame count")
            block["frame_engine_status"] = state
        finally:
            # A partial poll already in memory is assembled even when the next
            # poll, stop, readback or cancellation fails.
            block.update(assemble_streams(block["raw_polls"], hf.device_id, self.clockbase))
            if self.settings["mode"] == "single":
                block["reference"] = None
            probe.disable_channel("C")
            timer.set_trigger_source("OFF")
            timer.command("STOP", expect_response=False)
            hf.stop_acquisition()
        self._assign_timing(block)
        self._verify_native(block)
        return block

    def _verify_native(self, block):
        timing=block.get("timing",{})
        clock=np.asarray(timing.get("timestamp_s",[]),dtype=float)
        dio=np.asarray(timing.get("dio",[]))
        timing_rate=self.settings["response"]["timing_rate_sps"]
        if len(clock)<2 or len(clock)!=len(dio) or np.any(np.diff(clock)<=0) or np.any(np.diff(clock)>1.6/timing_rate):
            block["flags"].append("incomplete")
            raise AcquisitionIntegrityError("Native electrical timing stream is missing or discontinuous")
        for role in ("sample","reference") if self.settings["mode"]=="dual" else ("sample",):
            stream = block[role]
            ts = np.asarray(stream.get("timestamp_s",[]),dtype=float)
            x = np.asarray(stream.get("x",[]),dtype=float)
            rate = self.settings["response"][role+"_rate_sps"]
            if len(ts)<2 or len(ts)!=len(x) or np.any(~np.isfinite(x)) or np.any(np.diff(ts)<=0):
                block["flags"].append("incomplete")
                raise AcquisitionIntegrityError(f"{role} native timestamps/values are incomplete or nonmonotonic")
            if "flags" in stream and np.any(np.asarray(stream["flags"])!=0):
                block["flags"].append("stream_status_nonzero")
            if np.any(np.diff(ts)>1.6/rate):
                block["flags"].append("incomplete")
                raise AcquisitionIntegrityError(f"{role} native data contain a missing-sample gap")
            if block.get("program") and ts[-1]-ts[0]<block["program"]["capture_duration_s"]-1/rate:
                block["flags"].append("incomplete")
                raise AcquisitionIntegrityError(f"{role} native stream does not span the declared finite block")
            if block["kind"]=="pumped" and block.get("integration_origin_s") is not None:
                shift = self.settings["response"]["reference_latency_s"]-self.settings["response"]["detector_latency_s"] if role=="reference" else 0
                start,stop = block["aperture_start_s"]+shift,block["aperture_stop_s"]+shift
                if ts[0]>start or ts[-1]<stop or np.sum((ts>=start)&(ts<=stop))<2:
                    block["flags"].append("insufficient_aperture_support")
                    continue
                if role=="sample":
                    block["actual_delay_s"] = float(np.mean(ts[(ts>=start)&(ts<=stop)])-block["integration_origin_s"])

    def _assign_timing(self, block):
        edges = electrical_edges(block["timing"])
        block["electrical_events_s"] = edges
        pumped = block["kind"] == "pumped"
        expected = 1 if pumped else 0
        if len(edges) != expected:
            block["flags"].append("electrical_event_count_mismatch")
            raise AcquisitionIntegrityError(f"Variable Sync events {len(edges)} != commanded {expected}; no retry")
        block["optically_observed_event_count"] = None
        block["optical_origin_s"] = None
        block["timing_origin_source"] = "unresolved"
        if pumped:
            electrical=float(edges[0])
            block["electrical_origin_s"]=electrical
            latency = self.profile.get("variable_sync_to_pump_s")
            valid_latency=isinstance(latency,(int,float)) and math.isfinite(latency) and bool(self.profile.get("optical_latency_calibration_id"))
            if valid_latency:
                origin = electrical+latency
                block["optical_origin_s"] = origin
                block["timing_origin_source"] = "electrical Variable Sync plus selected optical latency calibration"
                block["optical_latency_calibration_id"] = self.profile["optical_latency_calibration_id"]
                block["delay_basis"]="calibrated_optical_origin"
            else:
                origin=electrical
                block["timing_origin_source"]="observed electrical Variable Sync; absolute optical origin unresolved"
                block["delay_basis"]="electrical_relative"
                block["flags"].append("unresolved_optical_origin")
            block["integration_origin_s"]=origin
            center = origin + block["delay_s"]
            aperture = self.settings["response"]["integration_aperture_s"]
            block["aperture_start_s"], block["aperture_stop_s"] = center-aperture/2, center+aperture/2
        else:
            # Control integration uses measured common support; no nonexistent
            # pump time zero is manufactured for an unpumped record.
            timestamps = np.asarray(block["sample"].get("timestamp_s", []))
            if timestamps.size:
                block["aperture_start_s"], block["aperture_stop_s"] = float(timestamps[0]), float(timestamps[-1])

    def close(self):
        errors, restored = [], {}
        notification_errors=[]
        try:
            self.progress("Restoration: inhibit outputs, restore preserved settings, verify readbacks")
        except Exception as exc:
            notification_errors.append(str(exc))
        def attempt(label, callback):
            try:
                restored[label] = callback()
            except Exception as exc:
                errors.append(f"{label}: {exc}")
        # Every action is attempted even if another device cannot be reached.
        for name in ("t660_2", "t660_1"):
            if name not in self.devices:
                continue
            unit = self.devices[name]
            attempt(name+" source OFF", lambda u=unit: u.set_trigger_source("OFF"))
            attempt(name+" STOP", lambda u=unit: u.command("STOP", expect_response=False))
            if name == "t660_2":
                attempt(name+" frames OFF", lambda u=unit: u.command("TFRame:STOp", expect_response=False))
                for stage in ("ACTIVE", "NEXT", "QUEUE"):
                    attempt(name+" train "+stage, lambda u=unit, s=stage: u.configure_train(count=0, stage=s))
            for channel in "ABCD":
                attempt(name+" inhibit "+channel, lambda u=unit, c=channel: u.disable_channel(c))
        laser = self.devices.get("mircat")
        if laser:
            attempt("MIRcat emission OFF", laser.turn_emission_off)
            attempt("MIRcat scan stop", laser.stop_scan_if_needed)
            # Physical closure applies even to a service that failed before its
            # original settings snapshot. Deinitializing the SDK is not disarm.
            attempt("MIRcat disarm", laser.disarm)
            if "mircat" in self.original:
                original = self.original["mircat"]
                for selected in original["qcls"]:
                    if selected.get("qcl")==1:
                        attempt("MIRcat QCL restore 1", lambda s=selected: laser.set_qcl_pulse_params(qcl=1,
                            **{key:s[key] for key in ("pulse_rate_hz","pulse_width_ns","current_ma")}))
                fields = ("pulse_mode", "process_trigger_mode", "start", "stop", "interval", "units", "dwell_us", "after_off_us")
                attempt("MIRcat trigger restore", lambda: laser.set_wavelength_trigger_params(**{k:original["trigger"][k] for k in fields}))
            def verify_laser_safe():
                state=self._laser_state()
                restored["MIRcat final state"]=state
                for field in ("armed","emission_on","scan_in_progress","scan_active",
                              "scan_paused","scan_waiting_process_trigger"):
                    if state.get(field) is not False:
                        raise AcquisitionIntegrityError(f"MIRcat final {field} is not verified OFF: {state.get(field)!r}")
                return state
            attempt("MIRcat safe verified", verify_laser_safe)
        hf = self.devices.get("hf2li")
        if hf:
            attempt("HF2LI stop", hf.stop_acquisition)
            if "hf2li" in self.original:
                attempt("HF2LI restore", lambda: hf.reload_settings_snapshot(self.original["hf2li"]))
                def verify_hf():
                    after = hf.export_settings_snapshot(preset=self.preset)
                    for path in self.original["hf2li"]["nodes"]:
                        if path.endswith("/phaseshift"):
                            after["nodes"][path]={"type":"double","value":hf._get_node("double",path)}
                    difference = hf.compare_settings_snapshots(self.original["hf2li"], after)
                    if difference.get("match") is not True or after.get("read_errors"):
                        raise AcquisitionIntegrityError(str(difference))
                    return after
                attempt("HF2LI restored verified", verify_hf)
        for name in ("t660_2", "t660_1"):
            if name not in self.devices:
                continue
            unit = self.devices[name]
            if name in self.original:
                original = self.original[name]
                attempt(name+" settings restore", lambda u=unit, o=original: u.apply_recipe(o["recipe"]))
                for edge, reference in original["edge_references"].items():
                    attempt(name+" edge "+edge, lambda u=unit,e=edge,r=reference: u.command(f"TIME:RELTo{e} {r}", expect_response=False))
                references = restored[name+" edge references"] = {}
                for edge, reference in original["edge_references"].items():
                    def verify_reference(u=unit, e=edge, expected=reference, observed=references):
                        entry = observed[e] = {"expected": expected, "actual": None}
                        try:
                            entry["actual"] = int(u.command(f"TIME:RELTo{e}?"))
                        except Exception as exc:
                            entry["error"] = str(exc)
                            raise
                        _equal(expected, entry["actual"], u.name+" TIME:RELTo"+e)
                        return entry["actual"]
                    # Read every captured reference even when another edge
                    # failed. Equal delay/width scalars alone cannot establish
                    # that the restored physical timing relationships match.
                    attempt(name+" edge "+edge+" verified", verify_reference)
                attempt(name+" restored verified", lambda u=unit,o=original: self._verify_timer(u,o["recipe"]))
            else:
                attempt(name+" safe verified", lambda u=unit: self._verify_timer(u,{"trigger_source":"OFF", "channels":{c:{"enabled":False} for c in "ABCD"}}))
        for name, device in self.devices.items():
            attempt(name+" close", device.deinitialize if name == "mircat" else device.close)
        return {"safe_verified": not errors, "settings_restored": not errors,
            "errors": errors, "notification_errors":notification_errors,
            "original": self.original, "verification": restored, "command_log": self.log.getvalue()}


class SimulatedAcquirer:
    """Explicit synthetic source; never a fallback for a failed real connection."""
    def __init__(self, context, operation, settings, profile, *, cancel, progress):
        self.settings, self.cancel, self.progress = data(settings), cancel, progress
        self.current_block = None
        self.counter = 0
        self.rng = np.random.default_rng(731)

    def check(self):
        if self.cancel():
            raise AcquisitionStopped("Acquisition stopped")

    def wait(self, seconds, stage):
        self.progress(stage+" (simulation; accelerated)")
        self.check()

    def prepare(self, program):
        self.check()
        self.progress("Configuration: explicit synthetic instruments")
        return {"simulation": True, "timing_observation": "synthetic fixture"}

    def tune(self, wavenumber):
        self.check()
        self.progress(f"Tuning / settling: {wavenumber:g} cm⁻¹ (simulation)")
        return {"value": wavenumber, "units": "cm^-1", "light_valid": True, "simulation": True}

    def capture(self, program, block):
        block["program"] = data(program)
        return self.observe(self.settings["response"]["integration_aperture_s"], block)

    def observe(self, duration, block):
        self.current_block = block
        self.check()
        self.counter += 1
        from .processing import ResponseKernel
        response = self.settings["response"]
        kernel = ResponseKernel.from_mapping(response)
        pumped = block["kind"] == "pumped"
        delay = float(block.get("delay_s", 0))
        aperture = response["integration_aperture_s"]
        clockbase = 210_000_000
        origin = self.counter*10.
        count = max(12, min(4096, int(duration*response["sample_rate_sps"])))
        times = origin + delay + (np.arange(count)-(count-1)/2) / response["sample_rate_sps"]
        wave = block["wavenumber_cm1"]
        spectral = math.exp(-.5*((wave-1945.)/1.2)**2)
        baseline = .6*(1-.1*spectral)
        truth = -.01*spectral*float(kernel.recovery(np.array([delay]), .0007)[0]) if pumped else 0.
        common = self.rng.normal(0, 2e-5, count)
        reference = 1+common+self.rng.normal(0, 1e-5, count)
        sample = baseline*10**(-truth)*reference + self.rng.normal(0, 1e-5, count)
        def stream(t, x):
            ticks = np.rint(t*clockbase).astype(np.uint64)
            return {"timestamp_ticks": ticks, "timestamp_s":ticks.astype(float)/clockbase,
                    "x":x, "y":np.zeros(count), "dio":np.zeros(count,dtype=np.uint32)}
        block.update(sample=stream(times,sample),
            reference=stream(times+response["reference_latency_s"]-response["detector_latency_s"],reference) if self.settings["mode"]=="dual" else None,
            timing={"timestamp_s": np.array([origin-1e-5,origin,origin+1e-5]),
                    "dio":np.array([0,1<<17,0] if pumped else [0,0,0],dtype=np.uint32)},
            aperture_start_s=float(times[0]),aperture_stop_s=float(times[-1]),
            electrical_events_s=np.array([origin]) if pumped else np.array([]),
            optical_origin_s=origin if pumped else None, timing_origin_source="synthetic known clock; not hardware observation",
            flags=[], simulation=True, readbacks={"simulation":True},
            simulation_truth={"tau_s":.0007,"delta_absorbance":truth,"baseline":baseline})
        self.progress("Acquisition: synthetic native detector block")
        return block

    def close(self):
        self.progress("Restoration: simulated outputs closed")
        return {"safe_verified":True,"settings_restored":True,"errors":[],"simulation":True}
