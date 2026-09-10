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
from typing import Mapping

import numpy as np


class AcquisitionStopped(RuntimeError):
    """An intentional stop, distinct from acquisition or restoration failure."""


def mapping(value):
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    return dict(value)


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


class InstalledDevices:
    """One operation's fresh services; caller holds host scope through close."""

    def __init__(self, context, operation):
        self.context, self.operation = context, operation
        self.services = {}
        self.before = {}
        self.resolved = {}
        self.streaming = False
        self.readbacks = {}

    def connect(self, check):
        for name in ("t660_2", "t660_1", "mircat", "hf2li"):
            check()
            service = self.context.devices.create(name, self.operation)
            self.services[name] = service  # Retain even a partly connected service.
            getattr(service, "initialize" if name == "mircat" else "connect")()
            if name.startswith("t660"):
                self.before[name] = service.read_active_settings()
                queries = self.before[name]["queries"]
                clock_mode = _query_value(queries, "clock_connector_mode").upper()
                expected_modes = {"OUT"} if name == "t660_2" else {"INP", "IN"}
                if clock_mode not in expected_modes:
                    raise RuntimeError(f"{name} 10 MHz clock connector role differs from maintained topology")
                if name == "t660_1" and _query_value(queries, "clock_lock_status").upper() != "LOCKED":
                    raise RuntimeError("T660-1 is not locked to installed T660-2 10 MHz clock")
                service.set_trigger_source("OFF")
                service.force_eod()
                for channel in "ABCD":
                    service.disable_channel(channel)
            elif name == "mircat":
                self.before[name] = service.read_state().to_dict()
                service.turn_emission_off()
            else:
                from control_app.devices.hf2li_service import HF2LIPreset
                self.snapshot_preset = HF2LIPreset("fixed_point_restoration", {
                    "demodulators": [{"index": i} for i in range(6)]})
                self.before[name] = service.export_settings_snapshot(preset=self.snapshot_preset)
                if self.before[name].get("read_errors"):
                    raise RuntimeError("Cannot preserve HF2LI configuration: incomplete initial readback")

    def configure(self, resolved, check):
        self.resolved = deepcopy(dict(resolved))
        check()
        hf = self.services["hf2li"]
        hf_profile = self.resolved.get("hf2li", {})
        if not hf_profile.get("signal_inputs") or not hf_profile.get("pll"):
            raise RuntimeError("Qualified HF2LI input loading/ranges and PLL profile are required")
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
                if not math.isclose(float(value), float(profile[field]), rel_tol=1e-7, abs_tol=1e-12):
                    raise RuntimeError(f"HF2LI {field} differs from selected supported value: {value}")
        rates = [float(nodes[f"/{hf.device_id}/demods/{i}/rate"]["value"])
            for i in range(6) if nodes[f"/{hf.device_id}/demods/{i}/enable"]["value"]]
        if sum(rates) > 700000:
            raise RuntimeError("HF2LI enabled aggregate throughput exceeds 700 kSa/s")
        timing_actual = nodes[f"/{hf.device_id}/demods/{timing_index}/rate"]["value"]
        if not math.isclose(timing_actual, self.resolved["timing_rate_sps"], rel_tol=1e-7):
            raise RuntimeError("Timing stream rate differs from qualified marker-capture rate")
        self.clockbase_hz = hf.get_clockbase()
        recipe = deepcopy(self.resolved["probe_recipe"])
        recipe.update(trigger_source="OFF", stop_first=True)
        self.services["t660_1"].apply_recipe(recipe)
        self.services["t660_1"].start_continuous_clock()
        mircat = self.services["mircat"]
        params = self.resolved["mircat"]
        qcl = int(params["qcl"])
        self.before["mircat_pulse"] = {"qcl": qcl,
            "pulse_rate_hz": mircat.get_qcl_pulse_rate(qcl),
            "pulse_width_ns": mircat.get_qcl_pulse_width(qcl)}
        self.before["mircat_trigger"] = mircat.get_wavelength_trigger_params()
        self.readbacks["mircat_pulse"] = mircat.set_qcl_pulse_params(**params)
        for key in ("pulse_rate_hz", "pulse_width_ns"):
            if not math.isclose(float(self.readbacks["mircat_pulse"][key]), float(params[key]), rel_tol=1e-6):
                raise RuntimeError(f"MIRcat selected {key} differs from actual pulse readback")
        self.readbacks["hf2li"] = actual
        self.readbacks["probe"] = self.services["t660_1"].read_active_settings()
        probe_state = self.readbacks["probe"]
        queries = probe_state["queries"]
        expected_rate = _physical_number(recipe["clock"]["frequency"])
        if not math.isclose(_physical_number(_query_value(queries, "synth_frequency")), expected_rate, rel_tol=1e-7):
            raise RuntimeError("T660-1 probe frequency readback differs from qualified selection")
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
        check()

    def read_health(self):
        """Use the foundation's read-only health service under bound ownership."""
        hf = self.services["hf2li"]
        inputs = (0, 1) if self.context.mode == "dual" else (0,)
        return hf.read_acquisition_health(reference_pll=0, input_indices=inputs)

    def tune(self, wavenumber_cm1, settings, check, progress):
        mircat = self.services["mircat"]
        mircat.turn_emission_off()
        mircat.set_external_trigger_params(wavenumber_cm1=wavenumber_cm1)
        if not mircat.is_interlock_set() or not mircat.is_key_switch_set():
            raise RuntimeError("MIRcat interlock or key switch is not ready")
        mircat.arm()
        deadline = time.monotonic() + settings["tune_timeout_s"]
        while not mircat.are_tecs_ready():
            check()
            if time.monotonic() >= deadline:
                raise RuntimeError("MIRcat TEC readiness timeout")
            time.sleep(.05)
        mircat.tune_to_wavenumber(wavenumber_cm1, qcl=int(self.resolved["mircat"]["qcl"]))
        while not mircat.is_tuned():
            check()
            if time.monotonic() >= deadline:
                raise RuntimeError("MIRcat actual Tuned timeout")
            time.sleep(.05)
        mircat.turn_emission_on(approved_laser_safety_condition=True)
        actual = mircat.get_actual_wavelength()
        if (actual.get("units") != "cm^-1" or not actual.get("light_valid") or
                abs(actual["value"] - wavenumber_cm1) > self.resolved["tune_tolerance_cm1"]):
            raise RuntimeError(f"MIRcat actual wavenumber is not within the measured tolerance: {actual}")
        settling_end = time.monotonic() + float(self.resolved["settling_s"])
        while time.monotonic() < settling_end:
            check()
            progress({"stage": "tuning/settling", "message": "Waiting measured detector/HF2LI settling"})
            time.sleep(min(.05, max(0, settling_end-time.monotonic())))
        return {"requested_cm1": wavenumber_cm1, "actual": actual, "tuned": mircat.is_tuned(),
                "settling_s": self.resolved["settling_s"]}

    def upload(self, program, check, progress):
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
                result[role] = {str(k): np.asarray(v).copy() for k, v in stream.items()}
            else:
                raise RuntimeError("Unexpected HF2LI native poll structure; no flattening or interpolation applied")
        return result

    def start_event(self, program):
        self.services["t660_2"].start_frame_table()

    def finish_event(self):
        service = self.services["t660_2"]
        return {"frames_status": service.get_frames_status(), "frame_shot_count": service.get_shot_count()}

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
                def verify(s=service):
                    state = s.read_active_settings()
                    q = state["queries"]["trigger_source"]
                    if not q.get("ok") or q.get("response", "").upper() != "OFF":
                        raise RuntimeError("Trigger source OFF not verified")
                    for channel in state["channels"].values():
                        enabled = channel["enabled"]
                        if not enabled.get("ok") or str(enabled.get("response")).upper() not in {"0", "OFF"}:
                            raise RuntimeError("Channel OFF not verified")
                    return state
                attempt(f"{name} safe readback", verify)
        mircat = self.services.get("mircat")
        if mircat:
            attempt("MIRcat emission OFF", mircat.turn_emission_off)
            attempt("MIRcat cancel tune", mircat.cancel_manual_tune)
            attempt("MIRcat stop scan", mircat.stop_scan_if_needed)
            if self.before.get("mircat_pulse"):
                attempt("MIRcat pulse restoration", lambda: mircat.set_qcl_pulse_params(**self.before["mircat_pulse"]))
            if self.before.get("mircat_trigger"):
                old = self.before["mircat_trigger"]
                allowed = ("pulse_mode", "process_trigger_mode", "start", "stop", "interval", "units", "dwell_us", "after_off_us")
                if all(k in old for k in allowed):
                    attempt("MIRcat trigger restoration", lambda: mircat.set_wavelength_trigger_params(**{k:old[k] for k in allowed}))
            attempt("MIRcat disarm", mircat.disarm)
            def verify_mircat():
                if mircat.is_emission_on() or mircat.is_laser_armed():
                    raise RuntimeError("MIRcat emission OFF/disarmed not verified")
                return {"emission_on": False, "armed": False}
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
                attempt("HF2LI restore settings", lambda: hf.reload_settings_snapshot(self.before["hf2li"]))
                def verify_hf():
                    after = hf.export_settings_snapshot(preset=self.snapshot_preset)
                    result = hf.compare_settings_snapshots(self.before["hf2li"], after)
                    if not result["match"] or after.get("read_errors"):
                        raise RuntimeError(f"HF2LI restoration mismatch: {result}")
                    return result
                attempt("HF2LI restoration readback", verify_hf)
        for name, service in reversed(list(self.services.items())):
            attempt(f"{name} close", getattr(service, "deinitialize" if name == "mircat" else "close"))
        return {"safe_verified": not errors, "errors": errors, "actions": actions,
            "preservation_errors": preservation_errors,
            "restoration_policy": "Restore HF2LI and MIRcat pulse configuration; T660 outputs disabled and MIRcat emission off/disarmed"}
