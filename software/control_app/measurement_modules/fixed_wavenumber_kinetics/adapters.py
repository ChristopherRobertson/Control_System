"""Owned installed-device operations for stationary HF2LI recording.

No constructor in this module touches hardware. Native polling never schedules an
edge: finite T660 tables do that, and HF2LI DIO supplies the electrical epoch.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
import math
import re
import time
from datetime import datetime, timezone
from typing import Mapping

import numpy as np


class AcquisitionStopped(RuntimeError):
    """An intentional stop, distinct from acquisition or restoration failure."""


def mapping(value):
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if is_dataclass(value):
        value = asdict(value)
    def detach(item):
        if isinstance(item, Mapping):
            return {str(key): detach(child) for key, child in item.items()}
        if isinstance(item, (tuple, list)):
            return [detach(child) for child in item]
        return item
    return detach(value)


def check_cancel(cancel):
    if cancel is not None and (cancel.is_set() if hasattr(cancel, "is_set") else cancel()):
        raise AcquisitionStopped("Acquisition stopped")


def _physical_number(value):
    match = re.fullmatch(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([a-zA-Z]*)\s*", str(value))
    if not match:
        raise RuntimeError(f"Unrecognized physical readback {value!r}")
    units = {"": 1., "s": 1., "ns": 1e-9, "us": 1e-6, "ms": 1e-3,
             "ps": 1e-12, "hz": 1., "khz": 1e3, "mhz": 1e6}
    if match[2].lower() not in units:
        raise RuntimeError(f"Unrecognized readback unit {match[2]!r}")
    return float(match[1])*units[match[2].lower()]


def _query_value(queries, key):
    row = queries.get(key, {})
    if not row.get("ok"):
        raise RuntimeError(f"Required {key} readback unavailable: {row}")
    return row["response"]


def _channel_settings(row, *, enabled):
    polarity = str(_query_value(row, "polarity")).upper()
    termination = str(_query_value(row, "termination")).upper()
    if polarity not in {"POS", "POSITIVE", "+", "NEG", "NEGATIVE", "-"}:
        raise RuntimeError(f"Unrecognized T660 channel polarity {polarity!r}")
    if termination not in {"ON", "1", "50", "50OHM", "OFF", "0", "LOWZ"}:
        raise RuntimeError(f"Unrecognized T660 channel termination {termination!r}")
    return {"enabled": enabled,
        "delay": f"{_physical_number(_query_value(row, 'delay_edge')):.12g}s",
        "width": f"{_physical_number(_query_value(row, 'width_edge')):.12g}s",
        "polarity": "negative" if polarity in {"NEG", "NEGATIVE", "-"} else "positive",
        "termination": "50OHM" if termination in {"ON", "1", "50", "50OHM"} else "LOWZ"}


def _timing_mode(row):
    value = str(_query_value(row, "timing_mode")).upper().replace("_", "").replace("-", "")
    if value in {"DW", "DELAYWIDTH"}:
        return "DW"
    if value in {"RF", "RISEFALL"}:
        return "RF"
    raise RuntimeError(f"Unrecognized T660 timing mode {value!r}")


def _snapshot_timing_topology(service, snapshot):
    """Read references without changing them, including during a live check."""
    references = snapshot["edge_references"] = {}
    for edge in range(1, 9):
        command = f"TIME:RELTo{edge}?"
        response = service.command(command)
        reference = int(response)
        if not 0 <= reference <= 8 or reference == edge:
            raise RuntimeError(f"Invalid T660 reference for edge {edge}: {response!r}")
        references[str(edge)] = {"ok": True, "response": response, "source": command}
    remaining = {}
    for index, channel in enumerate("ABCD"):
        row = snapshot["channels"][channel]
        if _timing_mode(row) == "DW" and int(references[str(2*index+2)]["response"]) != 2*index+1:
            raise RuntimeError(f"T660 {channel} delay-width falling reference is not its rising edge")
        remaining[2*index+1] = _physical_number(_query_value(row, "delay_edge"))
        remaining[2*index+2] = _physical_number(_query_value(row, "width_edge"))
    absolute = {0: 0.}
    while remaining:
        resolved = [edge for edge in remaining if int(references[str(edge)]["response"]) in absolute]
        if not resolved:
            snapshot["absolute_timing_basis"] = "Cyclic reference graph requires an inhibited readback"
            return
        for edge in resolved:
            absolute[edge] = remaining.pop(edge)+absolute[int(references[str(edge)]["response"])]
    snapshot["absolute_channel_timing"] = {c: {"delay_s": absolute[2*i+1],
        "width_s": absolute[2*i+2]-absolute[2*i+1]} for i, c in enumerate("ABCD")}
    snapshot["absolute_timing_basis"] = "Read-only composition of native edge delays and references to shot start"


def _capture_absolute_timing_inhibited(service, snapshot):
    if "absolute_channel_timing" in snapshot:
        return
    # T660 Programming Guide pp53,77: RELTo changes the expression basis,
    # not the absolute physical edge delay. Never perform this during a live
    # read-only check; the caller has disabled the source and all outputs.
    absolute = {}
    for index, channel in enumerate("ABCD"):
        rising, falling = 2*index+1, 2*index+2
        for edge in (rising, falling) if _timing_mode(snapshot["channels"][channel]) == "RF" else (rising,):
            old_reference = int(snapshot["edge_references"][str(edge)]["response"])
            checks = snapshot.setdefault("absolute_reference_checks", {})[str(edge)] = {
                "original_reference": old_reference, "reference_for_absolute": None,
                "absolute_delay_s": None, "restored_reference": None}
            try:
                service.command(f"TIME:RELTo{edge} 0", expect_response=False)
                checks["reference_for_absolute"] = service.command(f"TIME:RELTo{edge}?")
                if int(checks["reference_for_absolute"]) != 0:
                    raise RuntimeError(f"Edge {edge} reference 0 not verified before absolute delay readback")
                checks["delay_readback"] = service.command(f"TIME:DEL{edge}?")
                absolute[edge] = _physical_number(checks["delay_readback"])
                checks["absolute_delay_s"] = absolute[edge]
            finally:
                service.command(f"TIME:RELTo{edge} {old_reference}", expect_response=False)
                checks["restored_reference"] = service.command(f"TIME:RELTo{edge}?")
                if int(checks["restored_reference"]) != old_reference:
                    raise RuntimeError(f"Edge {edge} original reference {old_reference} not restored after absolute delay readback")
        if falling not in absolute:
            absolute[falling] = absolute[rising]+_physical_number(_query_value(snapshot["channels"][channel], "width_edge"))
    snapshot["absolute_channel_timing"] = {c: {"delay_s": absolute[2*i+1],
        "width_s": absolute[2*i+2]-absolute[2*i+1]} for i, c in enumerate("ABCD")}
    snapshot["absolute_timing_basis"] = "Inhibited absolute readback with original edge reference expression restored immediately"


def _absolute_channel_settings(snapshot, channel, *, enabled):
    selected = _channel_settings(snapshot["channels"][channel], enabled=enabled)
    if "absolute_channel_timing" not in snapshot:
        raise RuntimeError("Absolute T660 timing unresolved in read-only check; cyclic references require an inhibited acquisition readback")
    absolute = snapshot["absolute_channel_timing"][channel]
    selected.update(delay=f"{absolute['delay_s']:.12g}s", width=f"{absolute['width_s']:.12g}s")
    return selected


def _verify_timing_inhibited(service):
    state = service.read_active_settings()
    if str(_query_value(state["queries"], "trigger_source")).upper() != "OFF":
        raise RuntimeError("T660 source OFF not verified before timing configuration")
    if any(str(_query_value(row, "enabled")).upper() not in {"0", "OFF"} for row in state["channels"].values()):
        raise RuntimeError("T660 channel OFF not verified before timing configuration")
    return state


class InstalledDevices:
    """One operation's fresh services; caller holds host scope through close."""

    def __init__(self, context, operation):
        self.context, self.operation = context, operation
        self.services = {}
        self.before = {}
        self.resolved = {}
        self.streaming = False
        self.readbacks = {}

    def connect(self, check, *, prepare=True):
        self.prepared = prepare
        for name in ("t660_2", "t660_1", "mircat", "hf2li"):
            check()
            service = self.context.devices.create(name, self.operation)
            self.services[name] = service  # Retain even a partly connected service.
            getattr(service, "initialize" if name == "mircat" else "connect")()
            if name.startswith("t660"):
                self.before[name] = service.read_active_settings()
                _snapshot_timing_topology(service, self.before[name])
                queries = self.before[name]["queries"]
                clock_mode = _query_value(queries, "clock_connector_mode").upper()
                expected_modes = {"OUT"} if name == "t660_2" else {"INP", "IN"}
                if clock_mode not in expected_modes:
                    raise RuntimeError(f"{name} 10 MHz clock connector role differs from maintained topology")
                if name == "t660_1" and _query_value(queries, "clock_lock_status").upper() != "LOCKED":
                    raise RuntimeError("T660-1 is not locked to installed T660-2 10 MHz clock")
                if prepare:
                    service.set_trigger_source("OFF")
                    service.force_eod()
                    for channel in "ABCD":
                        service.disable_channel(channel)
                    _verify_timing_inhibited(service)
                    _capture_absolute_timing_inhibited(service, self.before[name])
                    for index, channel in enumerate("ABCD"):
                        service.set_channel_timing_mode(channel, "delay_width")
                        service.command(f"TIME:RELTo{2*index+1} 0", expect_response=False)
            elif name == "mircat":
                # A broad vendor state snapshot may follow its active-QCL field.
                # This installed topology has exactly one QCL; read it directly.
                self.before[name] = {"qcl": 1, "emission_on": service.is_emission_on(),
                    "armed": service.is_laser_armed(), "interlock_set": service.is_interlock_set(),
                    "key_switch_set": service.is_key_switch_set(), "tecs_ready": service.are_tecs_ready(),
                    "pulse_rate_hz": service.get_qcl_pulse_rate(1),
                    "pulse_width_ns": service.get_qcl_pulse_width(1)}
                if prepare:
                    service.turn_emission_off()
            else:
                from control_app.devices.hf2li_service import HF2LIPreset
                self.snapshot_preset = HF2LIPreset("fixed_point_restoration", {
                    "include_reference_clock": True,
                    "demodulators": [{"index": i} for i in range(6)]})
                self.before[name] = service.export_settings_snapshot(preset=self.snapshot_preset)
                if self.before[name].get("read_errors"):
                    raise RuntimeError("Cannot preserve HF2LI configuration: incomplete initial readback")

    def discover_operating_profile(self, settings, check, progress, *, probe_capabilities=False):
        """Derive a runnable selection from current installed readbacks.

        Only the optional capability probe temporarily configures HF2LI nodes;
        the service restores them. No calibration file or sample approval is
        needed. Observed device settings do not imply calibrated time zero/IRF.
        """
        settings = mapping(settings)
        check()
        hf, mircat = self.services["hf2li"], self.services["mircat"]
        nodes = self.before["hf2li"]["nodes"]
        def node(path):
            return nodes[f"/{hf.device_id}/{path}"]["value"]
        source = f"Connected readbacks {datetime.now(timezone.utc).isoformat()}"
        profile = {"source_kind": "connected_readbacks", "source": source,
            "record_id": f"device-readbacks-{self.operation.run_id}",
            "sources": {}, "readbacks": deepcopy(self.before),
            "maximum_aggregate_rate_sps": 700000., "timing_demodulator_index": 2,
            "pump_marker_bit": 16, "pump_marker_edge": "falling",
            "pump_marker_qualification": "installed Surelite Fixed Sync electrical DIO16 HIGH-to-LOW edge; optical arrival unresolved",
            "continuous_poll_lossless_qualified": False,
            "acquisition_response": {}, "supported": {},
            "overhead_estimates_s": {"configuration": 5., "upload_per_frame": .05,
                "tune_per_position": 2., "restoration": 3., "saving": 1., "analysis": 1.}}
        from control_app.measurement_host.application_session import cached_hf2_choices
        capabilities = cached_hf2_choices(hf, self.context.mode)
        profile["hf2_choices"] = capabilities
        profiles = {"sample": capabilities.get("sample", capabilities), "reference": capabilities.get("reference", {})}
        if probe_capabilities:
            progress({"stage": "configuration", "message": "Reading accepted HF2LI detector capabilities"})
            method = hf.discover_dual_phase_scan_capabilities if self.context.mode == "dual" else hf.discover_phase_scan_capabilities
            capabilities = method()
            check()
            profiles = {"sample": capabilities.get("sample", capabilities)}
            if self.context.mode == "dual":
                profiles["reference"] = capabilities["reference"]
            profile["capabilities"] = capabilities
        for role, index, input_index in (("sample", 0, 0), ("reference", 3, 1)):
            if role == "reference" and self.context.mode != "dual":
                continue
            current = {"demodulator_index": index, "input_index": input_index,
                "rate_sps": float(node(f"demods/{index}/rate")),
                "timeconstant_s": float(node(f"demods/{index}/timeconstant")),
                "order": int(node(f"demods/{index}/order"))}
            cap = profiles.get(role, {})
            profile[role] = current
            if cap:
                profile["supported"][role] = {"rate_sps": list(cap["rates_sps"]),
                    "order": list(cap["orders"]),
                    "timeconstant_s": sorted({v for values in cap.get("timeconstants_by_order", {}).values() for v in values})}
            profile["sources"][role] = source
        profile["timing_rate_sps"] = float(node("demods/2/rate"))
        profile["clockbase_hz"] = hf.get_clockbase()
        probe_before = self.before["t660_1"]
        probe_clock = _physical_number(_query_value(probe_before["queries"], "synth_frequency"))
        probe_divider = int(_query_value(probe_before["queries"], "predivider"))
        if probe_divider < 0:
            raise RuntimeError("T660-1 predivider must be nonnegative")
        probe_frequency = probe_clock / max(1, probe_divider)
        profile["probe_recipe"] = {"stop_first": True, "trigger_source": "OFF", "predivider": probe_divider,
            "gate_mode": 0, "burst_enabled": False, "clock": {"frequency": f"{probe_clock:.12g}Hz", "shots": 0},
            "channels": {c: _absolute_channel_settings(probe_before, c, enabled=c != "D") for c in "ABCD"}}
        profile["timing"] = {"input_frequency_hz": probe_frequency}
        try:
            pump = self.before["t660_2"]
            fire, qswitch = _absolute_channel_settings(pump, "A", enabled=False), _absolute_channel_settings(pump, "B", enabled=False)
            profile["timing"].update(fire_delay_s=_physical_number(fire["delay"]),
                q_switch_delay_s=_physical_number(qswitch["delay"]), fire_width_s=_physical_number(fire["width"]),
                q_switch_width_s=_physical_number(qswitch["width"]), fire_polarity=fire["polarity"],
                q_switch_polarity=qswitch["polarity"], termination=fire["termination"])
        except (RuntimeError, KeyError, TypeError) as exc:
            profile["pump_readback_error"] = str(exc)
        profile["hf2li"] = {"signal_inputs": {}, "pll": {"index": 0, "enable": True,
            "adcselect": 4, "freqcenter_hz": probe_frequency, "harmonic": 1,
            "order": int(node("plls/0/order")), "adcthreshold": int(node("plls/0/adcthreshold"))}}
        for role, index in (("sample", 0), ("reference", 1)):
            if role == "reference" and self.context.mode != "dual":
                continue
            profile["hf2li"]["signal_inputs"][role] = {"index": index,
                "ac": bool(node(f"sigins/{index}/ac")), "impedance_50ohm": bool(node(f"sigins/{index}/imp50")),
                "differential": bool(node(f"sigins/{index}/diff")), "range_v": float(node(f"sigins/{index}/range"))}
        qcl_range = self._read_qcl1_range()
        profile["qcl_ranges"] = [qcl_range]
        for selected in settings.get("positions", ()):
            if not qcl_range["min_cm1"] <= float(selected["wavenumber_cm1"]) <= qcl_range["max_cm1"]:
                raise RuntimeError("Selected wavenumber lies outside installed MIRcat QCL 1 range")
        profile["mircat"] = {"qcl": 1, "pulse_rate_hz": mircat.get_qcl_pulse_rate(1),
            "pulse_width_ns": mircat.get_qcl_pulse_width(1)}
        profile["mircat_readback"] = {**profile["mircat"], "pulse_limits": mircat.get_qcl_pulse_limits(1)}
        profile["settling_s"] = max(10*p["timeconstant_s"]*p["order"] for p in (profile[r] for r in ("sample", "reference") if r in profile))
        profile["settling_basis"] = "Conservative 10 × filter order × live time constant; estimated filter settling, not measured acquisition response"
        # Tuned state is not an assertion of optical calibration accuracy.
        profile["tune_tolerance_cm1"] = .05
        profile["tune_tolerance_basis"] = "Operational 0.05 cm^-1 tune/readback tolerance, not SDK floating-point precision or optical calibration"
        profile["sources"].update(probe_recipe=source, mircat=source, timing=source, hf2li=source)
        profile["warnings"] = ["Optical time zero and acquisition response are uncalibrated unless optional records are supplied",
            "Pump sync observability is determined from retained DIO observations; fine timestamps do not establish optical resolution"]
        check()
        return profile

    read_operating_settings = discover_operating_profile

    def _external_probe_rate(self):
        recipe = self.resolved["probe_recipe"]
        return _physical_number(recipe["clock"]["frequency"]) / max(1, int(recipe.get("predivider", 1)))

    def _read_qcl1_range(self):
        actual = self.services["mircat"].get_qcl_tuning_range(1)
        if int(actual.get("qcl", 1)) != 1:
            raise RuntimeError("MIRcat QCL 1 range readback identifies a different QCL")
        low, high = float(actual["min_cm1"]), float(actual["max_cm1"])
        if not math.isfinite(low) or not math.isfinite(high) or low > high:
            raise RuntimeError("MIRcat QCL 1 range readback is invalid")
        return {**actual, "qcl": 1, "min_cm1": low, "max_cm1": high}

    def _verify_mircat_pulse(self, expected):
        from .planner import mircat_pulse_errors
        mircat = self.services["mircat"]
        actual = {"qcl": 1, "pulse_rate_hz": mircat.get_qcl_pulse_rate(1),
                  "pulse_width_ns": mircat.get_qcl_pulse_width(1)}
        if "current_ma" in expected:
            actual["current_ma"] = mircat.get_qcl_current(1)
        errors = mircat_pulse_errors(actual, self._external_probe_rate(), mircat.get_qcl_pulse_limits(1))
        if errors:
            raise RuntimeError("; ".join(errors))
        for key in ("pulse_rate_hz", "pulse_width_ns", *(("current_ma",) if "current_ma" in expected else ())):
            if not math.isclose(float(actual[key]), float(expected[key]), rel_tol=1e-6):
                raise RuntimeError(f"MIRcat QCL 1 {key} differs from selected internal setting")
        actual["external_probe_rate_hz"] = self._external_probe_rate()
        self.readbacks.setdefault("mircat_pulses_by_qcl", {})["1"] = actual
        return actual

    def configure(self, resolved, check):
        self.resolved = deepcopy(dict(resolved))
        check()
        from .planner import mircat_pulse_errors
        mircat = self.services["mircat"]
        supplied = self.resolved.get("mircat", {})
        from control_app.measurement_host.laser_settings import MIRCAT_INTERNAL_RATE_HZ, MIRCAT_INTERNAL_WIDTH_NS
        params = {"qcl": 1, "pulse_rate_hz": MIRCAT_INTERNAL_RATE_HZ,
            "pulse_width_ns": MIRCAT_INTERNAL_WIDTH_NS}
        sources = self.resolved.setdefault("value_sources", {})
        if sources.get("mircat.current_ma") == "user_override":
            low, high = mircat.get_qcl_current_limits(1)
            if not low <= supplied["current_ma"] <= high:
                raise RuntimeError("Requested MIRcat current exceeds installed QCL limits")
            params["current_ma"] = supplied["current_ma"]
        sources["mircat.pulse_width_ns"] = "provisional_internal_policy"
        sources["mircat.pulse_rate_hz"] = "provisional_internal_policy"
        sources["mircat.qcl"] = "single installed QCL 1"
        self.resolved["mircat"] = params
        self.resolved["qcl_ranges"] = [self._read_qcl1_range()]
        errors = mircat_pulse_errors(params, self._external_probe_rate(),
            mircat.get_qcl_pulse_limits(1))
        if errors:
            raise RuntimeError("; ".join(errors))
        hf = self.services["hf2li"]
        hf_profile = self.resolved.get("hf2li", {})
        if not hf_profile.get("signal_inputs") or not hf_profile.get("pll"):
            raise RuntimeError("HF2LI input loading/ranges and PLL device settings are missing")
        hf.configure_reference_clock(external=True)
        hf.configure_signal_inputs(hf_profile["signal_inputs"])
        hf.configure_pll(hf_profile["pll"])
        detector_profiles = [self.resolved["sample"]]
        if self.context.mode == "dual":
            detector_profiles.append(self.resolved["reference"])
        demods = [{"index": i, "enable": False} for i in range(6)]
        for profile in detector_profiles:
            demods.append({"index": profile["demodulator_index"], "enable": True,
                "adcselect": profile["input_index"], "oscselect": 0, "harmonic": 1,
                "order": profile["order"], "timeconstant_s": profile["timeconstant_s"],
                "rate_sps": profile["rate_sps"], "trigger": 0})
        timing_index = int(self.resolved.get("timing_demodulator_index", 2))
        if timing_index in [p["demodulator_index"] for p in detector_profiles]:
            raise RuntimeError("Timing and detector demodulators must be distinct")
        demods.append({"index": timing_index, "enable": True, "adcselect": 0,
            "oscselect": 0, "harmonic": 1, "order": 1,
            "timeconstant_s": self.resolved["sample"]["timeconstant_s"],
            "rate_sps": self.resolved["timing_rate_sps"], "trigger": 0})
        hf.configure_demodulators(demods)
        hf.sync()
        actual = hf.export_settings_snapshot(preset=self.snapshot_preset)
        if actual.get("read_errors"):
            raise RuntimeError("HF2LI selected settings could not be read back completely")
        nodes = actual["nodes"]
        for profile in detector_profiles:
            for field, node in (("rate_sps", "rate"), ("order", "order"),
                                ("timeconstant_s", "timeconstant"), ("input_index", "adcselect")):
                value = nodes[f"/{hf.device_id}/demods/{profile['demodulator_index']}/{node}"]["value"]
                if field in {"input_index", "order"} and int(value) != int(profile[field]):
                    raise RuntimeError(f"HF2LI {field} differs from the requested value: {value}")
                if not math.isfinite(float(value)) or (field in {"rate_sps", "timeconstant_s"} and float(value) <= 0):
                    raise RuntimeError(f"Invalid actual HF2LI {field}: {value}")
                profile.setdefault("requested", {})[field] = profile[field]
                profile[field] = value
        rates = [float(nodes[f"/{hf.device_id}/demods/{i}/rate"]["value"])
            for i in range(6) if nodes[f"/{hf.device_id}/demods/{i}/enable"]["value"]]
        if sum(rates) > 700000:
            raise RuntimeError("HF2LI enabled aggregate throughput exceeds 700 kSa/s")
        timing_actual = nodes[f"/{hf.device_id}/demods/{timing_index}/rate"]["value"]
        if not math.isfinite(timing_actual) or timing_actual <= 0:
            raise RuntimeError("Timing stream rate readback is invalid")
        self.resolved["timing_rate_sps"] = timing_actual
        self.clockbase_hz = hf.get_clockbase()
        recipe = deepcopy(self.resolved["probe_recipe"])
        recipe.update(trigger_source="OFF", stop_first=True)
        self.services["t660_1"].apply_recipe(recipe)
        self.services["t660_1"].start_continuous_clock()
        mircat = self.services["mircat"]
        params = self.resolved["mircat"]
        self._qcl1_original_pulse = {"qcl": 1,
            "pulse_rate_hz": mircat.get_qcl_pulse_rate(1),
            "pulse_width_ns": mircat.get_qcl_pulse_width(1)}
        if "current_ma" in params:
            self._qcl1_original_pulse["current_ma"] = mircat.get_qcl_current(1)
        self.before["mircat_pulse"] = deepcopy(self._qcl1_original_pulse)
        self.before["mircat_trigger"] = mircat.get_wavelength_trigger_params()
        self.readbacks["mircat_pulse_command"] = mircat.set_qcl_pulse_params(**params)
        self.readbacks["mircat_pulse"] = self._verify_mircat_pulse(params)
        self._qcl1_selected_pulse = deepcopy(params)
        self.readbacks["hf2li"] = actual
        self.readbacks["probe"] = self.services["t660_1"].read_active_settings()
        probe_state = self.readbacks["probe"]
        queries = probe_state["queries"]
        expected_rate = _physical_number(recipe["clock"]["frequency"])
        if not math.isclose(_physical_number(_query_value(queries, "synth_frequency")), expected_rate, rel_tol=1e-7):
            raise RuntimeError("T660-1 probe frequency readback differs from selected setting")
        if int(_query_value(queries, "predivider")) != int(recipe.get("predivider", 1)):
            raise RuntimeError("T660-1 probe predivider readback differs")
        for channel, selected in recipe["channels"].items():
            channel_state = probe_state["channels"][channel]
            on = _query_value(channel_state, "enabled").upper() in {"ON", "1"}
            if on != selected["enabled"]:
                raise RuntimeError(f"T660-1 {channel} enable readback differs")
            for setting, field in (("delay", "delay_edge"), ("width", "width_edge")):
                if not math.isclose(_physical_number(_query_value(channel_state, field)), _physical_number(selected[setting]), rel_tol=1e-7, abs_tol=5e-12):
                    raise RuntimeError(f"T660-1 {channel} {setting} readback differs")
        self.readbacks["health"] = self.read_health()
        self.resolved["settling_s"] = max(float(self.resolved.get("settling_s", 0.)),
            max(10*p["timeconstant_s"]*p["order"] for p in detector_profiles))
        check()

    def read_health(self):
        """Use the foundation's read-only health service under bound ownership."""
        hf = self.services["hf2li"]
        inputs = (0, 1) if self.context.mode == "dual" else (0,)
        return hf.read_acquisition_health(reference_pll=0, input_indices=inputs)

    def tune(self, wavenumber_cm1, settings, check, progress):
        mircat = self.services["mircat"]
        mircat.turn_emission_off()
        qcl_range = self._read_qcl1_range()
        if not qcl_range["min_cm1"] <= wavenumber_cm1 <= qcl_range["max_cm1"]:
            raise RuntimeError("Selected wavenumber lies outside installed MIRcat QCL 1 range")
        if not hasattr(self, "_qcl1_selected_pulse"):
            raise RuntimeError("MIRcat QCL 1 pulse configuration has not been verified")
        selected_pulse = deepcopy(self._qcl1_selected_pulse)
        self.resolved["mircat"] = deepcopy(selected_pulse)
        self.resolved["qcl_ranges"] = [qcl_range]
        mircat.set_external_trigger_params(wavenumber_cm1=wavenumber_cm1)
        self._verify_mircat_pulse(selected_pulse)
        if not mircat.is_interlock_set() or not mircat.is_key_switch_set():
            raise RuntimeError("MIRcat interlock or key switch is not ready")
        mircat.arm()
        deadline = time.monotonic() + settings["tune_timeout_s"]
        while not mircat.are_tecs_ready():
            check()
            if time.monotonic() >= deadline:
                raise RuntimeError("MIRcat TEC readiness timeout")
            time.sleep(.05)
        mircat.tune_to_wavenumber(wavenumber_cm1, qcl=1)
        while not mircat.is_tuned():
            check()
            if time.monotonic() >= deadline:
                raise RuntimeError("MIRcat actual Tuned timeout")
            time.sleep(.05)
        actual_pulse = self._verify_mircat_pulse(selected_pulse)
        mircat.start_emission()
        actual = mircat.get_actual_wavelength()
        value = float(actual["value"])
        if actual.get("units") == "microns" and value > 0:
            value = 10000. / value
        elif actual.get("units") != "cm^-1":
            raise RuntimeError(f"MIRcat returned unsupported wavelength units: {actual}")
        actual = {**actual, "wavenumber_cm1": value}
        if (not math.isfinite(value) or not actual.get("light_valid") or
                abs(value - wavenumber_cm1) > self.resolved["tune_tolerance_cm1"]):
            raise RuntimeError(f"MIRcat actual wavenumber is not within the operational readback tolerance: {actual}")
        settling_end = time.monotonic() + float(self.resolved["settling_s"])
        while time.monotonic() < settling_end:
            check()
            progress({"stage": "tuning/settling", "message": "Waiting selected detector/HF2LI settling interval"})
            time.sleep(min(.05, max(0, settling_end-time.monotonic())))
        return {"requested_cm1": wavenumber_cm1, "actual": actual, "qcl": 1, "tuned": mircat.is_tuned(),
                "settling_s": self.resolved["settling_s"], "mircat_internal_pulse": actual_pulse}

    def upload(self, program, check, progress):
        self._cancel_check = check
        return self.services["t660_2"].preload_frame_table(
            list(program["frames"]), predivider=program["predivider"],
            input_frequency_hz=program["input_frequency_hz"], cancel_check=check,
            progress=lambda n, total: progress({"stage": "acknowledged timing-table upload",
                "completed": n, "total": total, "message": f"Acknowledged {n}/{total} frames"}))

    def start_stream(self):
        indices = [self.resolved["sample"]["demodulator_index"],
                   self.resolved.get("timing_demodulator_index", 2)]
        if self.context.mode == "dual":
            indices.append(self.resolved["reference"]["demodulator_index"])
        self.services["hf2li"].start_acquisition(demodulators=indices, fields=("x", "y", "dio"))
        self.streaming = True

    def read(self, duration_s):
        hf = self.services["hf2li"]
        raw = hf.read_acquisition(duration_s)
        data = raw.get("data", {})
        result = {"clockbase_hz": self.clockbase_hz, "retrieved_utc": raw.get("timestamp_utc"),
                  "requested_poll_duration_s": duration_s, "health": self.read_health()}
        roles = {"sample": self.resolved["sample"]["demodulator_index"],
                 "timing": self.resolved.get("timing_demodulator_index", 2)}
        if self.context.mode == "dual":
            roles["reference"] = self.resolved["reference"]["demodulator_index"]
        for role, index in roles.items():
            stream = data.get(f"/{hf.device_id}/demods/{index}/sample", {})
            if isinstance(stream, Mapping):
                # SDK streams also carry nested headers. Preserve that metadata
                # as mappings instead of converting it into object arrays.
                result[role] = deepcopy(dict(stream))
            else:
                raise RuntimeError("Unexpected HF2LI native poll structure; no flattening or interpolation applied")
        return result

    def start_event(self, program):
        self._terminal_wait_s = max(0., len(program["frames"])*program["frame_period_s"]-program["duration_s"]) + 2.
        self.services["t660_2"].start_frame_table()

    def finish_event(self):
        service = self.services["t660_2"]
        deadline = time.monotonic() + getattr(self, "_terminal_wait_s", 2.)
        status = service.get_frames_status()
        while status != "DONE" and time.monotonic() < deadline:
            self._cancel_check()
            time.sleep(.01)
            status = service.get_frames_status()
        return {"frames_status": status, "frame_shot_count": service.get_shot_count()}

    def timing_status(self):
        """Read finite-engine evidence before cleanup overwrites it; never fire."""
        service = self.services["t660_2"]
        return {"frames_status": service.get_frames_status(),
                "frame_shot_count": service.get_shot_count()}

    def idle(self, duration_s, check):
        deadline = time.monotonic() + duration_s
        while time.monotonic() < deadline:
            check()
            time.sleep(min(.02, max(0., deadline-time.monotonic())))

    def stop_stream(self):
        if self.streaming:
            self.services["hf2li"].stop_acquisition()
            self.streaming = False

    def cleanup(self, retain_tail=None):
        errors, actions = [], []
        preservation_errors = []
        def attempt(label, function):
            try:
                value = function()
                actions.append({"action": label, "ok": True, "readback": value})
                return value
            except Exception as exc:
                errors.append(f"{label}: {exc}")
                actions.append({"action": label, "ok": False, "error": str(exc)})
        if not getattr(self, "prepared", True):
            for name, service in reversed(list(self.services.items())):
                attempt(f"{name} close read-only session", getattr(service, "deinitialize" if name == "mircat" else "close"))
            return {"safe_verified": not errors, "errors": errors, "actions": actions,
                "preservation_errors": [], "restoration_policy": "Inspect settings without acquisition/configuration changes; normal MIRcat session close may disable an existing red alignment pointer"}
        for name in ("t660_2", "t660_1"):
            service = self.services.get(name)
            if service:
                attempt(f"{name} source OFF", lambda s=service: s.set_trigger_source("OFF"))
                attempt(f"{name} STOP", lambda s=service: s.command("STOP", expect_response=False))
                if name == "t660_2":
                    attempt("finite engine stop", lambda: service.command("TFRame:STOp", expect_response=False))
                attempt(f"{name} force EOD", service.force_eod)
                for channel in "ABCD":
                    attempt(f"{name} {channel} OFF", lambda s=service, c=channel: s.disable_channel(c))
                inhibited = attempt(f"{name} verify OFF before timing restoration", lambda s=service: _verify_timing_inhibited(s))
                def restore_timing(s=service, key=name):
                    if inhibited is None:
                        raise RuntimeError("Timing restoration skipped because source/channel OFF could not be verified")
                    before = self.before[key]
                    if "absolute_channel_timing" not in before:
                        return {"skipped": "No absolute snapshot; acquisition timing was not configured"}
                    for index, channel in enumerate("ABCD"):
                        s.set_channel_timing_mode(channel, "delay_width")
                        s.command(f"TIME:RELTo{2*index+1} 0", expect_response=False)
                    recipe = {"stop_first": True, "trigger_source": "OFF", "force_eod": True,
                        "predivider": int(_physical_number(_query_value(before["queries"], "predivider"))),
                        "clock": {"frequency": f"{_physical_number(_query_value(before['queries'], 'synth_frequency')):.12g}Hz"},
                        "channels": {c: _absolute_channel_settings(before, c, enabled=False) for c in "ABCD"}}
                    if key == "t660_2":
                        recipe["frames_engine"] = "OFF"
                    # A finite table's terminal frame changes ACTIVE delays.
                    # Restore the user's readback values with all outputs OFF,
                    # so the next automatic run cannot inherit terminal zeros.
                    return s.apply_recipe(recipe)
                attempt(f"{name} inactive timing restoration", restore_timing)
                if inhibited is not None:
                    for channel in "ABCD":
                        attempt(f"{name} {channel} timing mode restoration", lambda s=service, key=name, c=channel:
                            s.set_channel_timing_mode(c, _timing_mode(self.before[key]["channels"][c])))
                    for edge in range(1, 9):
                        attempt(f"{name} edge {edge} reference restoration", lambda s=service, key=name, e=edge:
                            s.command(f"TIME:RELTo{e} {int(self.before[key]['edge_references'][str(e)]['response'])}", expect_response=False))
                def verify(s=service, key=name):
                    state = s.read_active_settings()
                    _snapshot_timing_topology(s, state)
                    q = state["queries"]["trigger_source"]
                    if not q.get("ok") or q.get("response", "").upper() != "OFF":
                        raise RuntimeError("Trigger source OFF not verified")
                    for channel in state["channels"].values():
                        enabled = channel["enabled"]
                        if not enabled.get("ok") or str(enabled.get("response")).upper() not in {"0", "OFF"}:
                            raise RuntimeError("Channel OFF not verified")
                    if "absolute_channel_timing" in self.before[key]:
                        _capture_absolute_timing_inhibited(s, state)
                        for channel in "ABCD":
                            for field in ("delay_s", "width_s"):
                                expected = self.before[key]["absolute_channel_timing"][channel][field]
                                observed = state["absolute_channel_timing"][channel][field]
                                if not math.isclose(expected, observed, rel_tol=1e-6, abs_tol=1e-11):
                                    raise RuntimeError(f"{channel} absolute {field} restoration mismatch")
                    for field in ("synth_frequency", "predivider"):
                        expected = _physical_number(_query_value(self.before[key]["queries"], field))
                        observed = _physical_number(_query_value(state["queries"], field))
                        if not math.isclose(expected, observed, rel_tol=1e-7):
                            raise RuntimeError(f"{field} restoration mismatch")
                    for channel in "ABCD":
                        if _timing_mode(state["channels"][channel]) != _timing_mode(self.before[key]["channels"][channel]):
                            raise RuntimeError(f"{channel} timing mode restoration mismatch")
                        expected = _channel_settings(self.before[key]["channels"][channel], enabled=False)
                        observed = _channel_settings(state["channels"][channel], enabled=False)
                        for field in ("delay", "width"):
                            if not math.isclose(_physical_number(expected[field]), _physical_number(observed[field]), rel_tol=1e-6, abs_tol=1e-11):
                                raise RuntimeError(f"{channel} {field} restoration mismatch")
                        if any(expected[field] != observed[field] for field in ("polarity", "termination")):
                            raise RuntimeError(f"{channel} polarity/termination restoration mismatch")
                    for edge in range(1, 9):
                        if int(state["edge_references"][str(edge)]["response"]) != int(self.before[key]["edge_references"][str(edge)]["response"]):
                            raise RuntimeError(f"Edge {edge} reference restoration mismatch")
                    return state
                attempt(f"{name} safe readback", verify)
        mircat = self.services.get("mircat")
        if mircat:
            attempt("MIRcat emission OFF", mircat.turn_emission_off)
            attempt("MIRcat cancel tune", mircat.cancel_manual_tune)
            attempt("MIRcat stop scan", mircat.stop_scan_if_needed)
            if getattr(self, "_qcl1_original_pulse", None):
                attempt("MIRcat pulse restoration", lambda: mircat.set_qcl_pulse_params(**self._qcl1_original_pulse))
            if self.before.get("mircat_trigger"):
                old = self.before["mircat_trigger"]
                allowed = ("pulse_mode", "process_trigger_mode", "start", "stop", "interval", "units", "dwell_us", "after_off_us")
                if all(k in old for k in allowed):
                    attempt("MIRcat trigger restoration", lambda: mircat.set_wavelength_trigger_params(**{k:old[k] for k in allowed}))
            attempt("MIRcat disarm", mircat.disarm)
            def verify_mircat():
                if mircat.is_emission_on() or mircat.is_laser_armed():
                    raise RuntimeError("MIRcat emission OFF/disarmed not verified")
                pulses = {}
                expected_pulses = [self._qcl1_original_pulse] if getattr(self, "_qcl1_original_pulse", None) else []
                for expected in expected_pulses:
                    actual = {"pulse_rate_hz": mircat.get_qcl_pulse_rate(1),
                              "pulse_width_ns": mircat.get_qcl_pulse_width(1)}
                    if "current_ma" in expected:
                        actual["current_ma"] = mircat.get_qcl_current(1)
                    if any(not math.isclose(float(actual[key]), float(expected[key]), rel_tol=1e-6)
                           for key in actual):
                        raise RuntimeError("MIRcat QCL 1 internal pulse restoration mismatch")
                    pulses["1"] = actual
                return {"emission_on": False, "armed": False, "pulse_settings": pulses}
            attempt("MIRcat safe readback", verify_mircat)
        hf = self.services.get("hf2li")
        if hf:
            if self.streaming and retain_tail is not None:
                # Inhibit physical timing and emission FIRST, then retrieve one
                # bounded poll of already available native data before unsubscribe.
                try:
                    retain_tail(self.read(.001))
                    actions.append({"action": "final native retrieval", "ok": True,
                        "requested_poll_duration_s": .001, "maximum_retrieval_polls": 1})
                except Exception as exc:
                    preservation_errors.append(f"Final native retrieval: {exc}")
                    actions.append({"action": "final native retrieval", "ok": False,
                        "error": str(exc), "loss_boundary": "available device tail could not be certified retained"})
            attempt("HF2LI unsubscribe", self.stop_stream)
            if "hf2li" in self.before:
                expected_hf = deepcopy(self.before["hf2li"])
                # Installed HF2 external-reference center is a readback, not a
                # writable setpoint. Keep it in the original evidence only.
                observed_paths = {f"/{hf.device_id}/plls/0/freqcenter"}
                if expected_hf["nodes"].get(f"/{hf.device_id}/plls/0/enable", {}).get("value"):
                    observed_paths.add(f"/{hf.device_id}/oscs/0/freq")
                expected_hf["nodes"] = {p: v for p, v in expected_hf["nodes"].items() if p not in observed_paths}
                attempt("HF2LI restore settings", lambda: hf.reload_settings_snapshot(expected_hf))
                def verify_hf():
                    after = hf.export_settings_snapshot(preset=self.snapshot_preset)
                    observed = {p: v for p, v in after["nodes"].items() if p in observed_paths}
                    after["nodes"] = {p: v for p, v in after["nodes"].items() if p not in observed_paths}
                    result = hf.compare_settings_snapshots(expected_hf, after)
                    if not result["match"] or after.get("read_errors"):
                        raise RuntimeError(f"HF2LI restoration mismatch: {result}")
                    result["external_reference_observations"] = observed
                    return result
                attempt("HF2LI restoration readback", verify_hf)
        for name, service in reversed(list(self.services.items())):
            attempt(f"{name} close", getattr(service, "deinitialize" if name == "mircat" else "close"))
        return {"safe_verified": not errors, "errors": errors, "actions": actions,
            "preservation_errors": preservation_errors,
            "restoration_policy": "Restore HF2LI, MIRcat pulse and inactive T660 channel timing configuration; T660 outputs disabled and MIRcat emission off/disarmed"}
