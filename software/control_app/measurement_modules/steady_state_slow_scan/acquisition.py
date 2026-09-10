"""Installed-device slow-scan adapter. All calls execute inside host ownership.

Polling retrieves native data and observes completion; T660 frames schedule all
electrical edges. Each direction/QCL block is declared by the typed planner.
"""
from __future__ import annotations

from copy import deepcopy
import math
import re
from time import monotonic
from threading import Event

from .native import retain_chunk, observed_sweeps


def _response(item):
    if not item.get("ok"):
        raise RuntimeError(f"Cannot preserve/read instrument settings: {item}")
    return str(item["response"]).strip()


def _off(value):
    return str(value).strip().upper() in ("0", "OFF", "FALSE")


def _quantity(value):
    """Parse retained controller numeric fields without discarding the raw text."""
    match = re.fullmatch(r"\s*([+-]?[0-9.]+(?:[eE][+-]?[0-9]+)?)\s*(ps|ns|us|ms|s|Hz|kHz|MHz)?\s*", str(value), re.I)
    if not match:
        raise ValueError(f"Unrecognized controller numeric readback {value!r}")
    scale = {"ps": 1e-12, "ns": 1e-9, "us": 1e-6, "ms": 1e-3, "s": 1., "hz": 1., "khz": 1e3, "mhz": 1e6, "": 1.}
    result = float(match[1]) * scale[(match[2] or "").lower()]
    if not math.isfinite(result):
        raise ValueError("Nonfinite controller readback")
    return result


def _absolute_edges(settings, references):
    offsets = {str(2 * index + edge): _quantity(_response(settings["channels"][channel][key]))
               for index, channel in enumerate("ABCD") for edge, key in ((1, "delay_edge"), (2, "width_edge"))}
    values = {"0": 0.}
    def resolve(edge, visiting=()):
        if edge in values:
            return values[edge]
        if edge in visiting or str(references.get(edge)) not in {str(index) for index in range(9)}:
            raise ValueError("Cannot preserve cyclic or invalid T660 timing references")
        values[edge] = offsets[edge] + resolve(str(references[edge]), (*visiting, edge))
        return values[edge]
    for edge in offsets:
        resolve(edge)
    return values


def validate_topology(configuration):
    """Check maintained connected routes, never invent a shutter or sensor."""
    expected = {"t660_1": {"A": "hf2li_extref", "B": "mircat_trig_in", "C": "t660_2_trig_in", "D": None},
                "t660_2": {"A": "ndyag_fire", "B": "ndyag_q_switch", "C": "mircat_db9_pin_4_process_trigger", "D": None}}
    for name, channels in expected.items():
        if dict(configuration.get("devices", {}).get(name, {}).get("channel_map", {})) != channels:
            raise ValueError(f"Installed {name} routes differ from the supported slow-scan topology")
    routes = configuration.get("timing_routes", {})
    for name, bit in (("mircat_db9_pin_1", 20), ("mircat_db9_pin_2", 21), ("mircat_db9_pin_3", 22)):
        if routes.get("observed_timing_inputs", {}).get(name, {}).get("hf2li_dio_bit") != bit:
            raise ValueError(f"Installed {name} timing route is missing or incompatible")
    if routes.get("optional_acquisition_window", {}).get("connected"):
        raise ValueError("This adapter requires the maintained unwired DIO1 topology")
    if len(configuration.get("system", {}).get("default_detector_connections", ())) != 2:
        raise ValueError("Both maintained detector tee/receiver paths must be declared")


class InstalledSlowScanBackend:
    """Fresh services, independent subscriptions, verified safe-idle restoration."""
    def __init__(self, context, operation):
        self.context, self.operation = context, operation
        self.devices = {}
        self.before = {}
        self.readbacks = {}
        self.raw_records = []
        self.chunk_index = 0
        self._stop_wait = Event()
        self.plan = None
        self.configured = False
        self.time_origin_ticks = None

    def _create(self, name):
        device = self.context.devices.create(name, self.operation)
        # Register before connection so an exception cannot orphan an SDK.
        self.devices[name] = device
        return device

    def connect(self, check):
        validate_topology(self.operation.configuration)
        for name in ("t660_2", "t660_1", "hf2li", "mircat"):
            check()
            device = self._create(name)
            if name == "mircat":
                device.initialize()
            else:
                device.connect()
        self.hf, self.qcl = self.devices["hf2li"], self.devices["mircat"]
        self.units = {name: self.devices[name] for name in ("t660_1", "t660_2")}

    def discover(self, check):
        """Owned explicit operation; no optical emission or timing starts."""
        self.connect(check)
        # Generic stable HF service capability implementation uses the maintained
        # detector roles, irrespective of the historical method in its name.
        callback = self.hf.discover_phase_scan_capabilities if self.context.mode == "single" else self.hf.discover_dual_phase_scan_capabilities
        capabilities = callback()
        check()
        self.readbacks = {"hf2li": capabilities,
            "qcl_windows": [self.qcl.get_qcl_tuning_range(i) for i in range(1, self.qcl.get_num_installed_qcls()+1)],
            "t660_frame_capacity": self.units["t660_2"].verified_frame_capacity(),
            "mircat_state": self.qcl.read_state().to_dict()}
        return deepcopy(self.readbacks)

    def _snapshot(self):
        from control_app.devices.hf2li_service import HF2LIPreset
        self.snapshot_preset = HF2LIPreset("steady_state_slow_scan_restore_v1",
            {"demodulators": [{"index": i} for i in range(6)]})
        self.before["hf2li"] = self.hf.export_settings_snapshot(preset=self.snapshot_preset)
        if self.before["hf2li"].get("read_errors"):
            raise RuntimeError("HF2LI original settings could not all be retained")
        for name, unit in self.units.items():
            saved = unit.read_active_settings()
            for item in saved["queries"].values():
                _response(item)
            for values in saved["channels"].values():
                for item in values.values():
                    _response(item)
            references = {str(edge): int(unit.command(f"TIME:RELTo{edge}?")) for edge in range(1, 9)}
            self.before[name] = {"settings": saved, "references": references,
                                 "absolute_edges_s": _absolute_edges(saved, references)}
        self.before["mircat"] = {"trigger": self.qcl.get_wavelength_trigger_params(),
            "marker_width_us": self.qcl.get_wavelength_trigger_pulse_width_us(),
            "qcls": [{"qcl": i, "pulse_rate_hz": self.qcl.get_qcl_pulse_rate(i),
                      "pulse_width_ns": self.qcl.get_qcl_pulse_width(i), "current_ma": self.qcl.get_qcl_current(i)}
                     for i in range(1, self.qcl.get_num_installed_qcls()+1)]}

    def inhibit(self):
        errors = []
        for name in ("t660_2", "t660_1"):
            unit = self.devices.get(name)
            if unit is None:
                continue
            commands = [("trigger OFF", lambda u=unit: u.set_trigger_source("OFF")),
                        ("STOP", lambda u=unit: u.command("STOP", expect_response=False))]
            # The maintained T660-1 is the continuous probe/reference source;
            # only T660-2 provides the verified Trains and Frames extension.
            if name == "t660_2":
                commands.append(("frames STOP", lambda u=unit: u.command("TFRame:STOp", expect_response=False)))
            for label, callback in commands + [
                (f"channel {ch} OFF", lambda u=unit, c=ch: u.disable_channel(c)) for ch in "ABCD"]:
                try:
                    callback()
                except Exception as exc:
                    errors.append(f"{name} {label}: {exc}")
        qcl = self.devices.get("mircat")
        if qcl is not None:
            for label, callback in (("emission OFF", qcl.turn_emission_off), ("stop scan", qcl.stop_scan_if_needed)):
                try:
                    callback()
                except Exception as exc:
                    errors.append(f"MIRcat {label}: {exc}")
        if errors:
            raise RuntimeError("; ".join(errors))

    def verify_pump_off(self):
        unit = self.units["t660_2"]
        for channel in "ABD":
            value = unit.command(f"CHAN:ON? {channel}")
            if not _off(value):
                raise RuntimeError(f"T660-2 {channel} output is not inhibited")

    def prepare(self, plan, compiled, check, report):
        self.plan = plan
        self.connect(check)
        self._snapshot()
        self.inhibit()
        check()
        profile = plan.inputs.scientific_profile
        from control_app.devices.hf2li_service import HF2LIPreset
        roles = plan.inputs.demodulator_roles
        hf_profile = profile["hf2li"]
        demods = []
        for role in ("sample", "reference", "timing"):
            if role == "reference" and plan.settings.mode == "single":
                continue
            item = deepcopy(hf_profile[role])
            item["index"] = roles[role]
            item["enable"] = True
            if role == "sample":
                item.update(rate_sps=plan.selected["sample_rate_hz"], order=plan.selected["filter_order"],
                            timeconstant_s=plan.selected["time_constant_s"])
            elif role == "timing":
                item["rate_sps"] = plan.inputs.timing_rate_hz
            demods.append(item)
        self.hf.configure_demodulators([{"index": i, "enable": False} for i in range(6)])
        preset = HF2LIPreset("steady_state_slow_scan_v1", {"signal_inputs": hf_profile["sigins"],
            "pll": hf_profile["pll"], "demodulators": demods})
        self.hf.apply_preset(preset)
        self.readbacks["hf2li"] = self.hf.export_settings_snapshot(preset=self.snapshot_preset)
        if self.readbacks["hf2li"].get("read_errors"):
            raise RuntimeError("HF2LI configured readbacks are incomplete")
        for item in demods:
            for key, node in (("rate_sps", "rate"), ("timeconstant_s", "timeconstant"), ("order", "order"), ("adcselect", "adcselect"),
                              ("oscselect", "oscselect"), ("harmonic", "harmonic"), ("trigger", "trigger"), ("enable", "enable")):
                actual = self.readbacks["hf2li"]["nodes"][f"/{self.hf.device_id}/demods/{item['index']}/{node}"]["value"]
                if not math.isclose(actual, item[key], rel_tol=1e-6, abs_tol=1e-12):
                    raise ValueError(f"HF2LI demodulator {item['index']} {key}: selected {item[key]}, actual {actual}")
        for label, item in hf_profile["sigins"].items():
            for key, node in (("ac", "ac"), ("impedance_50ohm", "imp50"), ("differential", "diff"), ("range_v", "range")):
                actual = self.readbacks["hf2li"]["nodes"][f"/{self.hf.device_id}/sigins/{item['index']}/{node}"]["value"]
                if not math.isclose(actual, item[key], rel_tol=1e-6, abs_tol=1e-12):
                    raise ValueError(f"HF2LI {label} {key}: selected {item[key]}, actual {actual}")
        pll = hf_profile["pll"]
        for key, node in (("enable", "enable"), ("adcselect", "adcselect"), ("freqcenter_hz", "freqcenter"),
                          ("harmonic", "harmonic"), ("order", "order"), ("adcthreshold", "adcthreshold")):
            actual = self.readbacks["hf2li"]["nodes"][f"/{self.hf.device_id}/plls/{pll['index']}/{node}"]["value"]
            if not math.isclose(actual, pll[key], rel_tol=1e-6, abs_tol=1e-12):
                raise ValueError(f"HF2LI external PLL {key}: selected {pll[key]}, actual {actual}")
        rates = [item["rate_sps"] for item in demods]
        if sum(rates) > plan.inputs.aggregate_max_rate_hz:
            raise ValueError("Aggregate HF2LI rate exceeds the qualified installed throughput")
        self.clockbase = self.hf.get_clockbase()
        # A generic recipe changes edge offsets but does not clear persistent
        # TIME:RELTo references. Ground each pulse's leading edge at the trigger
        # before configuring probe/reference pulses (Programming Guide pp 53/57).
        for edge in (1, 3, 5, 7):
            self.units["t660_1"].command(f"TIME:RELTo{edge} 0", expect_response=False)
        self.units["t660_1"].apply_recipe(compiled.probe_recipe)
        self.units["t660_1"].set_trigger_source("OFF")
        # Physical 10 MHz distribution is unchanged; preserve and check readbacks.
        for name, unit in self.units.items():
            self.readbacks[name] = unit.read_active_settings()
            for key, expected in profile["t660_clock_readbacks"][name].items():
                actual = _response(self.readbacks[name]["queries"][key])
                if actual.upper() != str(expected).strip().upper():
                    raise ValueError(f"{name} {key}: qualified {expected}, actual {actual}")
        clock_actual = _quantity(_response(self.readbacks["t660_1"]["queries"]["synth_frequency"]))
        if not math.isclose(clock_actual, plan.selected["probe_rate_hz"], rel_tol=1e-9):
            raise ValueError(f"Probe synthesizer selected {plan.selected['probe_rate_hz']} Hz, actual {clock_actual} Hz")
        for channel in "ABC":
            readback = self.readbacks["t660_1"]["channels"][channel]
            width = _quantity(_response(readback["width_edge"]))
            delay = _quantity(_response(readback["delay_edge"]))
            if abs(width - compiled.selected["probe_width_s"]) > plan.inputs.t660_tick_s or abs(delay) > plan.inputs.t660_tick_s:
                raise ValueError(f"T660-1 {channel} probe edge readback differs from the quantized schedule")
        for edge in (1, 3, 5, 7):
            if int(self.units["t660_1"].command(f"TIME:RELTo{edge}?")) != 0:
                raise ValueError(f"T660-1 leading edge {edge} is not referenced to its hardware trigger")
        self.readbacks["before"] = deepcopy(self.before)
        self.configured = True
        self.verify_pump_off()
        report("configuration", "Instrument settings and pump inhibition verified")

    def _wait(self, seconds, check):
        deadline = monotonic()+seconds
        while monotonic() < deadline:
            check()
            self._stop_wait.wait(min(.025, max(0., deadline-monotonic())))

    def _poll(self, duration, check, records):
        deadline = monotonic()+duration
        while monotonic() < deadline:
            check()
            record = self.hf.read_acquisition(min(.05, max(.001, deadline-monotonic())))
            records.append(record)
            self.raw_records.append(record)
            retain_chunk(self.operation.output_path / "native_chunks", self.chunk_index, record)
            self.chunk_index += 1

    def acquire_dark(self, plan, check, report):
        self.inhibit()
        # DIO0 reference is needed even with emission OFF. B/C remain OFF.
        self.units["t660_1"].enable_channel("A")
        self.units["t660_1"].start_continuous_clock()
        roles = plan.inputs.demodulator_roles
        demods = [roles["sample"], roles["timing"]]
        if plan.settings.mode == "dual":
            demods.append(roles["reference"])
        records = []
        self.hf.start_acquisition(demodulators=demods)
        try:
            report("acquisition", "Detector dark; MIRcat emission OFF; pump OFF")
            self._poll(plan.selected["dark_duration_s"], check, records)
        finally:
            self.hf.stop_acquisition()
            self.inhibit()
        return records

    def acquire_block(self, block, plan, check, report):
        scan = block.block
        self.inhibit()
        check()
        profile = plan.inputs.scientific_profile
        coverage = self.qcl.get_qcl_tuning_range(scan.qcl)
        if not coverage["min_cm1"] <= min(scan.start_cm1, scan.stop_cm1) < max(scan.start_cm1, scan.stop_cm1) <= coverage["max_cm1"]:
            raise ValueError("Declared QCL segment is outside the connected module's tuning range")
        self.qcl.cancel_manual_tune()
        self.qcl.arm()
        deadline = monotonic()+profile.get("tune_timeout_s", 60.)
        while not self.qcl.are_tecs_ready():
            check()
            if monotonic() > deadline:
                raise TimeoutError("MIRcat TEC readiness timeout")
            self._wait(.025, check)
        self.qcl.tune_to_wavenumber(scan.start_cm1, qcl=scan.qcl)
        while not self.qcl.is_tuned():
            check()
            if monotonic() > deadline:
                raise TimeoutError("MIRcat tune timeout")
            self._wait(.025, check)
        report("tuning/settling", f"{scan.segment_id} {scan.direction}: characterized settle {scan.settle_s:g} s")
        self._wait(scan.settle_s, check)
        qcl_params = profile["qcl_pulse_params"][str(scan.qcl)]
        pulse_limits = self.qcl.get_qcl_pulse_limits(scan.qcl)
        current_limits = self.qcl.get_qcl_current_limits(scan.qcl)
        if (qcl_params["pulse_rate_hz"] > pulse_limits["max_pulse_rate_hz"] or
            qcl_params["pulse_width_ns"] > pulse_limits["max_pulse_width_ns"] or
            qcl_params["pulse_rate_hz"] * qcl_params["pulse_width_ns"] * 1e-9 > pulse_limits["max_duty_cycle"] / 100. or
            not min(current_limits) <= qcl_params["current_ma"] <= max(current_limits)):
            raise ValueError("Selected QCL pulse/current parameters exceed connected controller limits")
        if (plan.selected["probe_rate_hz"] > pulse_limits["max_pulse_rate_hz"] or
            plan.selected["probe_width_s"] * 1e9 > pulse_limits["max_pulse_width_ns"] or
            plan.selected["probe_rate_hz"] * plan.selected["probe_width_s"] > pulse_limits["max_duty_cycle"] / 100.):
            raise ValueError("External probe pulse requests exceed connected QCL receiver limits")
        actual_pulse = self.qcl.set_qcl_pulse_params(qcl=scan.qcl, **qcl_params)
        for field in ("pulse_rate_hz", "pulse_width_ns"):
            if not math.isclose(actual_pulse[field], qcl_params[field], rel_tol=1e-6):
                raise ValueError(f"MIRcat {field} readback differs from the qualified profile")
        actual_current = self.qcl.get_qcl_current(scan.qcl)
        if not math.isclose(actual_current, qcl_params["current_ma"], rel_tol=1e-6, abs_tol=1e-6):
            raise ValueError("MIRcat current readback differs from the qualified profile")
        actual_pulse["current_ma_observed"] = actual_current
        interval = plan.selected["marker_interval_cm1"]
        self.qcl.set_external_sweep_trigger_params(start_cm1=scan.start_cm1, stop_cm1=scan.stop_cm1,
            wavelength_trigger_interval_cm1=interval, external_process_trigger=True)
        trigger = self.qcl.get_wavelength_trigger_params()
        if trigger["pulse_mode"] != 2 or trigger["process_trigger_mode"] != 2 or trigger["units"] != 2:
            raise ValueError("MIRcat requires observed external pulse/process triggers and cm^-1 units")
        width = round(plan.selected["marker_width_s"]*1e6)
        if self.qcl.set_wavelength_trigger_pulse_width_us(width) != width:
            raise ValueError("MIRcat marker width readback differs")
        self.qcl.cancel_manual_tune()
        self.qcl.start_sweep_scan(start_cm1=scan.start_cm1, stop_cm1=scan.stop_cm1,
                                  scan_rate_cm1_s=scan.scan_speed_cm1_s, qcl=scan.qcl, repetitions=scan.replicates)
        actual = self.qcl.get_sweep_parameters()
        for name, expected in (("start_cm1", scan.start_cm1), ("stop_cm1", scan.stop_cm1),
                               ("scan_rate_cm1_s", scan.scan_speed_cm1_s), ("repetitions", scan.replicates)):
            if not math.isclose(actual[name], expected, rel_tol=1e-6, abs_tol=1e-5):
                raise ValueError(f"MIRcat {name}: selected {expected}, read back {actual[name]}")
        if not self.qcl.get_scan_waiting_process_trigger():
            raise RuntimeError("MIRcat is not waiting for the external Process Trigger")
        marker_identity = profile["marker_channel_by_qcl"]
        marker_params = self.qcl.get_wavelength_trigger_channel_params(int(marker_identity[str(scan.qcl)]))
        if marker_params.get("units") != 2 or not math.isclose(abs(marker_params["interval"]), interval, rel_tol=1e-6):
            raise ValueError("Controller marker units/spacing differ from the declared trajectory")
        if int(marker_params["num_triggers"]) != scan.expected_marker_count:
            raise ValueError("Controller marker count differs from the declared trajectory")
        direction = 1 if scan.stop_cm1 > scan.start_cm1 else -1
        targets = [float(marker_params["start"])+direction*i*abs(float(marker_params["interval"]))
                   for i in range(int(marker_params["num_triggers"]))]
        if not all(min(scan.start_cm1, scan.stop_cm1)-1e-5 <= v <= max(scan.start_cm1, scan.stop_cm1)+1e-5 for v in targets):
            raise ValueError("Controller markers lie outside the declared QCL segment")
        report("timing-table upload", f"{scan.block_id}: uploading acknowledged pending fields")
        upload = self.units["t660_2"].preload_frame_table(**block.upload_kwargs(
            progress=lambda done, total: report("timing-table upload", f"Acknowledged {done}/{total} frames"),
            cancel_check=check))
        self.verify_pump_off()
        self.readbacks[scan.block_id] = {"sweep": actual, "markers": marker_params, "pulse": actual_pulse, "upload": upload,
                                         "installed_coverage": coverage, "installed_pulse_limits": pulse_limits,
                                         "installed_current_limits": current_limits, "trigger": trigger}
        roles = plan.inputs.demodulator_roles
        demods = [roles["sample"], roles["timing"]]
        if plan.settings.mode == "dual":
            demods.append(roles["reference"])
        records = []
        self.hf.start_acquisition(demodulators=demods)
        try:
            # Reference locks while probe and frame input are inhibited.
            unit = self.units["t660_1"]
            unit.enable_channel("A")
            unit.start_continuous_clock()
            self._wait(scan.settle_s, check)
            self._health()
            self.qcl.turn_emission_on(approved_laser_safety_condition=plan.settings.physical_controls_confirmed)
            self.units["t660_2"].start_frame_table()
            unit.enable_channel("B")
            unit.enable_channel("C")
            report("acquisition", f"{scan.block_id}: {scan.replicates} sweeps; FIRE/Q-switch OFF")
            deadline = monotonic()+block.record_duration_s+max(2., scan.settle_s)
            while True:
                self._poll(.05, check, records)
                self._health()
                status = self.units["t660_2"].get_frames_status()
                if status == "DONE":
                    break
                if status in ("OFF", "ERROR"):
                    raise RuntimeError(f"Unexpected T660 frames status {status}")
                if monotonic() > deadline:
                    raise TimeoutError("Declared finite slow-scan block did not complete")
            # Final poll drains samples after the terminal OFF frame.
            self._poll(.05, check, records)
            shots = self.units["t660_2"].get_shot_count()
            self.readbacks[scan.block_id]["observed_controller_shots"] = shots
            if shots != block.physical_frame_count:
                raise RuntimeError(f"T660 shot count {shots} differs from {block.physical_frame_count} physical frames")
        finally:
            # All actions attempted by outer restoration even if either fails.
            self.inhibit()
            self.hf.stop_acquisition()
        report("retrieval", f"{scan.block_id}: assigning native samples from observed controller markers")
        hf_profile = profile["hf2li"]
        reference_cfg = hf_profile.get("reference", {})
        observed, streams, flags = observed_sweeps(records,
            sample_demodulator=roles["sample"], reference_demodulator=roles["reference"] if plan.settings.mode == "dual" else None,
            timing_demodulator=roles["timing"], clockbase_hz=self.clockbase, marker_targets_cm1=targets,
            expected_sweeps=scan.replicates, sample_rate_sps=plan.selected["sample_rate_hz"],
            reference_rate_sps=reference_cfg.get("rate_sps"),
            sample_group_delay_s=profile.get("sample_group_delay_s", 0.),
            reference_group_delay_s=profile.get("reference_group_delay_s", 0.),
            marker_gap_limit_s=1.8*interval/scan.scan_speed_cm1_s)
        for sweep in observed:
            block_origin = int(sweep["time_origin_ticks"])
            if self.time_origin_ticks is None:
                self.time_origin_ticks = block_origin
            sweep["timestamps_s"] = sweep["timestamps_s"] + (block_origin - self.time_origin_ticks) / self.clockbase
            sweep["block_time_origin_ticks"] = block_origin
            sweep["time_origin_ticks"] = self.time_origin_ticks
            expected_direction = profile["direction_bit_by_direction"][scan.direction]
            if sweep["direction_bit"] != expected_direction:
                sweep["flags"] = tuple(sweep["flags"]) + ("observed_direction_mismatch",)
                sweep["valid"][:] = False
        self.readbacks[scan.block_id]["native_streams"] = streams
        self.readbacks[scan.block_id]["flags"] = flags
        return observed

    def _health(self):
        self.verify_pump_off()
        if not self.qcl.is_interlock_set() or not self.qcl.is_key_switch_set() or self.qcl.get_system_error_word():
            raise RuntimeError("MIRcat interlock/key/error state is invalid")
        profile = self.plan.inputs.scientific_profile
        # Node identities must be qualified in the operating profile; status is
        # not inferred from oscillator frequency or a successful SDK call.
        nodes = profile["hf2li_health_nodes"]
        for item in nodes:
            path = item["path"].format(device=self.hf.device_id)
            actual = self.hf._get_node(item["type"], path)
            if actual != item["healthy_value"]:
                raise RuntimeError(f"HF2LI lock/clipping status {path}: {actual}")

    def restore(self):
        records, errors = {}, []
        def attempt(name, call):
            try:
                records[name] = call()
            except Exception as exc:
                errors.append(f"{name}: {exc}")
        if self.devices:
            attempt("safe_idle", self.inhibit)
        if "hf2li" in self.devices:
            attempt("unsubscribe", self.devices["hf2li"].stop_acquisition)
        if "mircat" in self.before:
            qcl = self.devices["mircat"]
            for params in self.before["mircat"]["qcls"]:
                attempt(f"restore QCL {params['qcl']}", lambda p=params: qcl.set_qcl_pulse_params(**p))
            trigger = self.before["mircat"]["trigger"]
            args = {key: trigger[key] for key in ("pulse_mode", "process_trigger_mode", "start", "stop", "interval", "units", "dwell_us", "after_off_us")}
            attempt("restore marker parameters", lambda: qcl.set_wavelength_trigger_params(**args))
            attempt("restore marker width", lambda: qcl.set_wavelength_trigger_pulse_width_us(self.before["mircat"]["marker_width_us"]))
            attempt("disarm", qcl.disarm)
            def check_qcl():
                current = {"trigger": qcl.get_wavelength_trigger_params(), "marker_width_us": qcl.get_wavelength_trigger_pulse_width_us(), "qcls": []}
                for expected in self.before["mircat"]["qcls"]:
                    index = expected["qcl"]
                    actual = {"qcl": index, "pulse_rate_hz": qcl.get_qcl_pulse_rate(index),
                              "pulse_width_ns": qcl.get_qcl_pulse_width(index), "current_ma": qcl.get_qcl_current(index)}
                    current["qcls"].append(actual)
                    for key, value in expected.items():
                        if not math.isclose(actual[key], value, rel_tol=1e-6, abs_tol=1e-8):
                            raise RuntimeError(f"MIRcat QCL {index} {key} restoration readback differs")
                for key, value in args.items():
                    if not math.isclose(current["trigger"][key], value, rel_tol=1e-6, abs_tol=1e-8):
                        raise RuntimeError(f"MIRcat trigger {key} restoration readback differs")
                if current["marker_width_us"] != self.before["mircat"]["marker_width_us"]:
                    raise RuntimeError("MIRcat marker width restoration readback differs")
                return current
            attempt("verify MIRcat restoration", check_qcl)
        if "hf2li" in self.before:
            hf = self.devices["hf2li"]
            def restore_hf():
                snapshot = deepcopy(self.before["hf2li"])
                enabled = {path: item for path, item in snapshot["nodes"].items() if "/demods/" in path and path.endswith("/enable")}
                hf.configure_demodulators([{"index": index, "enable": False} for index in range(6)])
                snapshot["nodes"] = {path: item for path, item in snapshot["nodes"].items() if path not in enabled and "/oscs/" not in path}
                # Restore filters/rates with every spectral stream disabled; the
                # original aggregate becomes active only after all rates return.
                detail = hf.reload_settings_snapshot(snapshot)
                hf.reload_settings_snapshot({"nodes": enabled})
                return detail
            attempt("restore HF2LI", restore_hf)
            def check_hf():
                actual = hf.export_settings_snapshot(preset=self.snapshot_preset)
                expected = deepcopy(self.before["hf2li"])
                expected["nodes"] = {path: item for path, item in expected["nodes"].items() if "/oscs/" not in path}
                comparison = hf.compare_settings_snapshots(expected, actual)
                if not comparison["match"] or actual.get("read_errors"):
                    raise RuntimeError(str(comparison))
                comparison["observed_oscillator_nodes"] = {path: item for path, item in actual["nodes"].items() if "/oscs/" in path}
                comparison["oscillator_note"] = "Stopped external-reference frequency is retained as observation, not restored or compared as a setting"
                return comparison
            attempt("verify HF2LI restoration", check_hf)
        for name in ("t660_1", "t660_2"):
            if name not in self.before:
                continue
            unit, saved = self.devices[name], self.before[name]
            def restore_timing(u=unit, s=saved):
                original = s["settings"]
                queries = original["queries"]
                recipe = {"stop_first": True, "trigger_source": "OFF", "gate_mode": 0, "burst_enabled": False,
                    "predivider": int(_response(queries["predivider"])),
                    "clock": {"frequency": _response(queries["synth_frequency"])}, "channels": {}}
                receiver_fields = ("trigger_input_polarity", "trigger_input_termination", "trigger_input_threshold_v")
                if all(key in queries for key in receiver_fields):
                    term = _response(queries["trigger_input_termination"])
                    term = {"1": "50OHM", "0": "HIZ"}.get(term, term)
                    recipe["external_trigger"] = {"polarity": _response(queries["trigger_input_polarity"]),
                                                  "termination": term, "threshold_v": _quantity(_response(queries["trigger_input_threshold_v"]))}
                # Rebuild the captured absolute edges in neutral rise/fall mode,
                # then restore the saved references and original channel modes.
                # Passing delay+width to apply_recipe would force delay/width mode.
                for channel in "ABCD":
                    u.set_channel_timing_mode(channel, "rise_fall")
                for edge in range(1, 9):
                    u.command(f"TIME:RELTo{edge} 0", expect_response=False)
                for index in range(4):
                    rising, falling = str(index * 2 + 1), str(index * 2 + 2)
                    u.command(f"TIME:QUEue{rising} 0s", expect_response=False)
                    u.command(f"TIME:QUEue{falling} {s['absolute_edges_s'][falling]:.12g}s", expect_response=False)
                    u.command(f"TIME:QUEue{rising} {s['absolute_edges_s'][rising]:.12g}s", expect_response=False)
                u.command("TIME:COMmit", expect_response=False)
                for edge, reference in s["references"].items():
                    u.command(f"TIME:RELTo{edge} {reference}", expect_response=False)
                for ch, values in original["channels"].items():
                    termination = _response(values["termination"])
                    termination = {"1": "50OHM", "0": "LOWZ"}.get(termination, termination)
                    recipe["channels"][ch] = {"enabled": False, "polarity": _response(values["polarity"]),
                        "termination": termination, "timing_mode": _response(values["timing_mode"])}
                u.apply_recipe(recipe)
                actual = u.read_active_settings()
                for channel, values in original["channels"].items():
                    for key in ("delay_edge", "width_edge"):
                        if not math.isclose(_quantity(_response(actual["channels"][channel][key])), _quantity(_response(values[key])), abs_tol=1e-11, rel_tol=0.):
                            raise RuntimeError(f"{u.name} channel {channel} {key} restoration readback differs")
                    if _response(actual["channels"][channel]["timing_mode"]).upper() != _response(values["timing_mode"]).upper():
                        raise RuntimeError(f"{u.name} channel {channel} timing mode restoration readback differs")
                for edge, reference in s["references"].items():
                    if int(u.command(f"TIME:RELTo{edge}?")) != reference:
                        raise RuntimeError(f"{u.name} edge {edge} reference restoration readback differs")
                return actual
            attempt(f"restore {name} safely", restore_timing)
        # Independent final OFF readbacks determine safety; completion is not proof.
        for name in ("t660_1", "t660_2"):
            if name not in self.devices:
                continue
            def verify(u=self.devices[name]):
                values = {ch: u.command(f"CHAN:ON? {ch}") for ch in "ABCD"}
                if not all(_off(v) for v in values.values()):
                    raise RuntimeError(f"Output inhibition unverified: {values}")
                if str(u.command("TRIG:SOUR?")).strip().upper() != "OFF":
                    raise RuntimeError("Trigger source not OFF")
                return values
            attempt(f"verify {name} OFF", verify)
        if "mircat" in self.devices:
            def verify_qcl():
                if self.devices["mircat"].is_emission_on():
                    raise RuntimeError("MIRcat emission remains ON")
                return {"emission_on": False}
            attempt("verify emission OFF", verify_qcl)
        for name, device in reversed(tuple(self.devices.items())):
            attempt(f"close {name}", device.deinitialize if name == "mircat" else device.close)
        return {"safe_verified": not errors, "errors": errors, "records": records,
                "policy": "Restore configuration with both timing engines and all optical outputs inhibited; never restart prior emission."}
