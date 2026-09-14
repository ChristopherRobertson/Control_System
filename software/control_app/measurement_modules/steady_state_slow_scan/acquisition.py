"""Installed-device slow-scan adapter. All calls execute inside host ownership.

Polling retrieves native data and observes completion; T660 frames schedule all
electrical edges. The typed planner declares one descending QCL-1 trajectory.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
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
        self.direction_bits = {}

    def _create(self, name):
        device = self.context.devices.create(name, self.operation)
        # Register before connection so an exception cannot orphan an SDK.
        self.devices[name] = device
        return device

    def connect(self, check):
        validate_topology(self.operation.configuration)
        if self.devices:
            if set(self.devices) == {"t660_2", "t660_1", "hf2li", "mircat"}:
                return
            raise RuntimeError("Cannot reuse an incomplete instrument connection")
        for name in ("t660_2", "t660_1", "hf2li", "mircat"):
            check()
            device = self._create(name)
            if name == "mircat":
                device.initialize()
            else:
                device.connect()
        self.hf, self.qcl = self.devices["hf2li"], self.devices["mircat"]
        self.units = {name: self.devices[name] for name in ("t660_1", "t660_2")}
        if self.qcl.get_num_installed_qcls() < 1:
            raise RuntimeError("Installed QCL 1 is unavailable")

    def discover(self, check):
        """Owned explicit operation; no optical emission or timing starts."""
        self.connect(check)
        if not self.before:
            self._snapshot()
        self.inhibit()
        # Generic stable HF service capability implementation uses the maintained
        # detector roles, irrespective of the historical method in its name.
        callback = self.hf.discover_phase_scan_capabilities if self.context.mode == "single" else self.hf.discover_dual_phase_scan_capabilities
        capabilities = callback()
        check()
        pulse_params = {str(i): {"pulse_rate_hz": self.qcl.get_qcl_pulse_rate(i), "pulse_width_ns": self.qcl.get_qcl_pulse_width(i),
                                "current_ma": self.qcl.get_qcl_current(i)} for i in (1,)}
        self.readbacks = {"hf2li": capabilities, "hf2li_settings": self.hf.export_settings_snapshot(preset=self.snapshot_preset),
            "qcl_windows": [self.qcl.get_qcl_tuning_range(1)],
            "qcl_pulse_params": pulse_params,
            "qcl_pulse_limits": {"1": self.qcl.get_qcl_pulse_limits(1)},
            "qcl_cw_allowed": {"1": self.qcl.is_cw_allowed(1)},
            "qcl_cw_current_limits": {"1": self.qcl.get_qcl_cw_current_limits(1)},
            "qcl_current_limits": {"1": self.qcl.get_qcl_current_limits(1)},
            "marker_width_us": self.qcl.get_wavelength_trigger_pulse_width_us(),
            "probe_width_s": self.before["t660_1"]["absolute_edges_s"]["4"] - self.before["t660_1"]["absolute_edges_s"]["3"],
            "probe_width_basis": "Difference of retained absolute falling/rising T660-1 B edges",
            "t660_1": self.units["t660_1"].read_active_settings(), "t660_2": self.units["t660_2"].read_active_settings(),
            "t660_frame_capacity": self.units["t660_2"].verified_frame_capacity(),
            "mircat_state": {"qcl": 1, "current_ma": pulse_params["1"]["current_ma"],
                             "pulse_width_ns": pulse_params["1"]["pulse_width_ns"], "pulse_rate_hz": pulse_params["1"]["pulse_rate_hz"]}}
        try:
            self.readbacks["sweep"] = self.qcl.get_sweep_parameters()
        except Exception as exc:
            # No previous sweep is normal; the entered speed governs this scan.
            self.readbacks["previous_sweep_unavailable"] = str(exc)
        return deepcopy(self.readbacks)

    def resolve_plan(self, settings, check):
        """Resolve Auto settings under existing ownership, before any emission."""
        from .planner import build_plan, inputs_from_context
        draft = build_plan(settings)
        if draft.errors:
            raise ValueError("; ".join(draft.errors))
        readbacks = self.discover(check)
        plan = build_plan(settings, inputs_from_context(self.context, settings, readbacks,
                                                      configuration=self.operation.configuration))
        plan.require_ready(hardware=True)
        return plan

    def _snapshot(self):
        from control_app.devices.hf2li_service import HF2LIPreset
        self.snapshot_preset = HF2LIPreset("steady_state_slow_scan_restore_v1",
            {"demodulators": [{"index": i, "sinc": False, "phaseshift": 0.} for i in range(6)],
             "oscillators": [{"index": 1}], "pll": {"index": 1}})
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
                      "pulse_width_ns": self.qcl.get_qcl_pulse_width(i), "current_ma": self.qcl.get_qcl_current(i),
                      "laser_mode": self.qcl.get_qcl_operating_mode(i), "temperature_c": self.qcl.get_qcl_set_temperature(i)}
                     for i in (1,)]}

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
        if not self.before:
            self._snapshot()
        self.inhibit()
        check()
        actual_pulse, _, _ = self._configure_qcl_pulses(plan)
        from .planner import current_to_requested_range_v
        requested_range = current_to_requested_range_v(actual_pulse["current_ma"])
        selected = deepcopy(plan.selected)
        selected["current_ma"] = actual_pulse["current_ma"]
        selected["pulse_width_s"] = actual_pulse["pulse_width_ns"] * 1e-9
        selected["mircat_internal_rate_hz"] = actual_pulse["pulse_rate_hz"]
        selected["repetition_rate_hz"] = actual_pulse["pulse_rate_hz"]
        selected["pulse_duty_fraction"] = (selected["repetition_rate_hz"] * selected["pulse_width_s"]
                                           if plan.settings.laser_mode == "pulsed" else None)
        selected["requested_input_range_v"] = requested_range
        for role, label in (("sample", "ch1"), ("reference", "ch2")):
            if role == "reference" and plan.settings.mode == "single": continue
            selected["hf2li"]["sigins"][label]["range_v"] = requested_range
        profile = deepcopy(plan.inputs.scientific_profile)
        profile["qcl_pulse_params"]["1"].update({field: actual_pulse[field] for field in ("current_ma", "pulse_rate_hz", "pulse_width_ns")})
        plan = replace(plan, selected=selected, inputs=replace(plan.inputs, scientific_profile=profile))
        self.plan = plan
        self.readbacks["qcl_selected_pulse"] = deepcopy(actual_pulse)
        from control_app.devices.hf2li_service import HF2LIPreset
        roles = plan.inputs.demodulator_roles
        hf_profile = plan.selected["hf2li"]
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
        self.hf.configure_pll({"index": 1, "enable": False})
        preset = HF2LIPreset("steady_state_slow_scan_v1", {"signal_inputs": hf_profile["sigins"],
            "pll": hf_profile["pll"], "demodulators": demods, "oscillators": hf_profile["oscillators"]})
        self.hf.apply_preset(preset)
        self.readbacks["hf2li"] = self.hf.export_settings_snapshot(preset=self.snapshot_preset)
        if self.readbacks["hf2li"].get("read_errors"):
            raise RuntimeError("HF2LI configured readbacks are incomplete")
        for suffix, expected in (("plls/1/enable", 0), ("oscs/1/freq", 0.)):
            if self.readbacks["hf2li"]["nodes"][f"/{self.hf.device_id}/{suffix}"]["value"] != expected:
                raise ValueError(f"HF2LI {suffix} must be zero for detector recording")
        for item in demods:
            for key, node in (("rate_sps", "rate"), ("timeconstant_s", "timeconstant"), ("order", "order"), ("adcselect", "adcselect"),
                              ("oscselect", "oscselect"), ("harmonic", "harmonic"), ("trigger", "trigger"), ("enable", "enable")):
                actual = self.readbacks["hf2li"]["nodes"][f"/{self.hf.device_id}/demods/{item['index']}/{node}"]["value"]
                if not math.isclose(actual, item[key], rel_tol=1e-6, abs_tol=1e-12):
                    raise ValueError(f"HF2LI demodulator {item['index']} {key}: selected {item[key]}, actual {actual}")
            for key in ("sinc", "phaseshift"):
                if key in item and self.readbacks["hf2li"]["nodes"][f"/{self.hf.device_id}/demods/{item['index']}/{key}"]["value"] != item[key]:
                    raise ValueError(f"HF2LI detector {key} readback differs")
        for label, item in hf_profile["sigins"].items():
            for key, node in (("ac", "ac"), ("impedance_50ohm", "imp50"), ("differential", "diff"), ("range_v", "range")):
                actual = self.readbacks["hf2li"]["nodes"][f"/{self.hf.device_id}/sigins/{item['index']}/{node}"]["value"]
                if key == "range_v":
                    if not math.isfinite(actual) or actual <= 0:
                        raise ValueError("HF2LI returned invalid detector input range")
                    item["range_v"] = actual
                    role = "sample" if item["index"] == 0 else "reference"
                    selected[f"{role}_range_v"] = actual
                    continue
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
            raise ValueError("Aggregate HF2LI rate exceeds the installed throughput")
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
            query = self.readbacks[name]["queries"]
            connector = _response(query["clock_connector_mode"]).upper()
            status = _response(query["clock_lock_status"]).upper()
            frequency = _quantity(_response(query["clock_external_frequency_hz"]))
            if (name == "t660_1" and (connector not in ("IN", "INP", "INPUT") or status != "LOCKED")) or (
                name == "t660_2" and (connector not in ("OUT", "OUTPUT") or status not in ("INTL", "INTERNAL"))):
                raise ValueError(f"{name} clock_lock_status/connector invalid: {status}/{connector}")
            if frequency != 10000000:
                raise ValueError(f"{name} installed 10 MHz clock reports {frequency} Hz")
        self._validate_live_pulses(plan, "probe_recipe_applied")
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
        self.readbacks["detector_input_ranges"] = {"basis": selected["input_range_basis"],
            "actual_current_ma": actual_pulse["current_ma"], "requested_range_v": requested_range,
            "actual_ranges_v": {label: item["range_v"] for label, item in hf_profile["sigins"].items()}}
        self.configured = True
        self.verify_pump_off()
        report("configuration", "Instrument settings and pump inhibition verified")
        return plan

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
        self._wait_reference_lock(check)
        self._wait(plan.selected["settle_s"], check)
        self._health()
        self._validate_live_pulses(plan, "dark_reference_started")
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
        if scan.qcl != 1:
            raise ValueError("Slow scan can route only installed QCL 1")
        if scan.direction != "reverse" or not scan.start_cm1 > scan.stop_cm1:
            raise ValueError("Slow scan requires a descending Start-to-End trajectory")
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
        report("tuning/settling", f"{scan.segment_id} {scan.direction}: settle {scan.settle_s:g} s")
        self._wait(scan.settle_s, check)
        pulse_observation = self._validate_live_pulses(plan, "after_tune", block_id=scan.block_id)
        actual_pulse = pulse_observation["pulse"]
        pulse_limits, current_limits = pulse_observation["pulse_limits"], pulse_observation["current_limits"]
        interval = plan.selected["marker_interval_cm1"]
        self.qcl.set_wavelength_trigger_params(pulse_mode=1, process_trigger_mode=2,
            start=scan.start_cm1, stop=scan.stop_cm1, interval=interval, units=2, dwell_us=0, after_off_us=0)
        trigger = self.qcl.get_wavelength_trigger_params()
        if trigger["pulse_mode"] != 1 or trigger["process_trigger_mode"] != 2 or trigger["units"] != 2:
            raise ValueError("MIRcat requires internal pulse timing, external process triggers and cm^-1 units")
        width = round(plan.selected["marker_width_s"]*1e6)
        if self.qcl.set_wavelength_trigger_pulse_width_us(width) != width:
            raise ValueError("MIRcat marker width readback differs")
        self.qcl.cancel_manual_tune()
        self.qcl.start_sweep_scan(start_cm1=scan.start_cm1, stop_cm1=scan.stop_cm1,
                                  scan_rate_cm1_s=scan.scan_speed_cm1_s, qcl=1, repetitions=scan.replicates)
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
        self.readbacks.setdefault(scan.block_id, {}).update({"sweep": actual, "markers": marker_params, "pulse": actual_pulse, "upload": upload,
                                         "installed_coverage": coverage, "installed_pulse_limits": pulse_limits,
                                         "installed_current_limits": current_limits, "trigger": trigger})
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
            self._wait_reference_lock(check)
            self._wait(scan.settle_s, check)
            self._health()
            check()
            self._validate_live_pulses(plan, "before_emission", block_id=scan.block_id)
            self.qcl.start_emission()
            self.units["t660_2"].start_frame_table()
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
        hf_profile = plan.selected["hf2li"]
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
            bit = sweep["direction_bit"]
            configured_bits = profile.get("direction_bit_by_direction", {})
            expected_direction = configured_bits.get(scan.direction, self.direction_bits.get(scan.direction))
            opposite = "reverse" if scan.direction == "forward" else "forward"
            other_bit = configured_bits.get(opposite, self.direction_bits.get(opposite))
            mismatch = ((expected_direction is not None and bit != expected_direction) or
                        (other_bit is not None and bit == other_bit))
            if mismatch:
                sweep["flags"] = tuple(sweep["flags"]) + ("observed_direction_mismatch",)
                sweep["valid"][:] = False
            elif "direction_changed_inside_sweep" not in sweep["flags"]:
                self.direction_bits.setdefault(scan.direction, bit)
        self.readbacks["direction_bit_observation"] = {
            "association": deepcopy(self.direction_bits),
            "basis": "Observed stable DIO bit associated with commanded and read-back sweep direction in this operation"}
        self.readbacks[scan.block_id]["native_streams"] = streams
        self.readbacks[scan.block_id]["flags"] = flags
        return observed

    def _configure_qcl_pulses(self, plan):
        qcl_params = plan.inputs.scientific_profile["qcl_pulse_params"]["1"]
        pulse_limits = self.qcl.get_qcl_pulse_limits(1)
        cw = plan.settings.laser_mode == "cw"
        current_limits = self.qcl.get_qcl_cw_current_limits(1) if cw else self.qcl.get_qcl_current_limits(1)
        if cw and not self.qcl.is_cw_allowed(1):
            raise ValueError("Connected QCL 1 does not support CW")
        optical_width = qcl_params["pulse_width_ns"] * 1e-9
        duty_limit = min(.30, pulse_limits["max_duty_cycle"] / 100.)
        if not cw and (qcl_params["pulse_rate_hz"] > pulse_limits["max_pulse_rate_hz"] or
            qcl_params["pulse_width_ns"] > pulse_limits["max_pulse_width_ns"] or
            qcl_params["pulse_rate_hz"] * optical_width > duty_limit + 1e-12):
            raise ValueError("Selected QCL pulse/current parameters exceed connected controller limits")
        if not min(current_limits) <= qcl_params["current_ma"] <= max(current_limits):
            raise ValueError("Selected QCL current exceeds connected mode-specific limits")
        actual = self.qcl.set_qcl_operating_params(qcl=1, **qcl_params,
            temperature_c=self.before["mircat"]["qcls"][0]["temperature_c"], laser_mode=2 if cw else 1)
        self.readbacks["configured_pulse_limits"] = {"pulse_limits": deepcopy(pulse_limits), "current_limits": deepcopy(current_limits)}
        record = self._validate_live_pulses(plan, "pulse_parameters_programmed", read_dds=False)
        observed = record["pulse"]
        actual.update(observed, current_ma_observed=observed["current_ma"])
        return actual, pulse_limits, current_limits

    def _validate_live_pulses(self, plan, stage, *, block_id=None, read_dds=True):
        """Read only: retain current QCL-1/DDS state before checking emission."""
        record = {"stage": stage, "block_id": block_id, "pulse": {}, "valid": False}
        self.readbacks.setdefault("pulse_observations", []).append(record)
        if block_id is not None:
            self.readbacks.setdefault(block_id, {}).setdefault("pulse_observations", []).append(record)
        try:
            for key, getter in (("pulse_rate_hz", self.qcl.get_qcl_pulse_rate),
                                ("pulse_width_ns", self.qcl.get_qcl_pulse_width), ("current_ma", self.qcl.get_qcl_current)):
                record["pulse"][key] = getter(1)
            record["pulse_limits"] = self.qcl.get_qcl_pulse_limits(1)
            cw = plan.settings.laser_mode == "cw"
            record["laser_mode"] = self.qcl.get_qcl_operating_mode(1)
            record["temperature_c"] = self.qcl.get_qcl_set_temperature(1)
            record["current_limits"] = self.qcl.get_qcl_cw_current_limits(1) if cw else self.qcl.get_qcl_current_limits(1)
            if record["laser_mode"] != (2 if cw else 1) or (cw and not self.qcl.is_cw_allowed(1)):
                raise ValueError("MIRcat laser mode readback differs or CW is unavailable")
            if not math.isclose(record["temperature_c"], self.before["mircat"]["qcls"][0]["temperature_c"], abs_tol=1e-5):
                raise ValueError("MIRcat temperature setpoint changed")
            if stage == "before_emission":
                record["trigger"] = self.qcl.get_wavelength_trigger_params()
                if any(record["trigger"].get(key) != value for key, value in
                       (("pulse_mode", 1), ("process_trigger_mode", 2), ("units", 2))):
                    raise ValueError("MIRcat pulse/process trigger mode changed before emission")
            if read_dds:
                record["t660_1"] = self.units["t660_1"].read_active_settings()
                queries = record["t660_1"]["queries"]
                record["external_rate_hz"] = _quantity(_response(queries["synth_frequency"]))
                record["predivider"] = int(_response(queries["predivider"]))
            else:
                record["external_rate_hz"] = plan.selected["probe_rate_hz"]
                record["cadence_basis"] = "Selected cadence; DDS not programmed yet"
        except Exception as exc:
            record["read_error"] = str(exc)
            raise
        observed, limits = record["pulse"], record["pulse_limits"]
        external = record["external_rate_hz"]
        expected = plan.inputs.scientific_profile["qcl_pulse_params"]["1"]
        record["selected"] = {**deepcopy(expected), "external_rate_hz": plan.selected["probe_rate_hz"]}
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in (*observed.values(), external, *limits.values(), *record["current_limits"])):
            raise ValueError("MIRcat/DDS returned nonfinite pulse or limit readbacks")
        width = observed["pulse_width_ns"] * 1e-9
        duty_limit = min(.30, limits["max_duty_cycle"] / 100.)
        record.update(external_duty_fraction=None, external_clock_role="Process Trigger timing only",
                      internal_duty_fraction=None if cw else observed["pulse_rate_hz"]*width, duty_limit_fraction=duty_limit)
        if not cw and (width <= 0 or observed["pulse_rate_hz"] <= 0 or
            record["internal_duty_fraction"] > duty_limit + 1e-12 or
            observed["pulse_rate_hz"] > limits["max_pulse_rate_hz"] or observed["pulse_width_ns"] > limits["max_pulse_width_ns"]):
            raise ValueError("MIRcat observed pulse duty/internal rate/current exceeds connected limits")
        if not min(record["current_limits"]) <= observed["current_ma"] <= max(record["current_limits"]):
            raise ValueError("MIRcat observed current exceeds connected mode-specific limits")
        if read_dds and (record["predivider"] != 1 or not math.isclose(external, plan.selected["probe_rate_hz"], rel_tol=1e-9)):
            raise ValueError("T660 actual DDS cadence/predivider changed from the selected setting")
        for field, value in observed.items():
            if not math.isclose(value, expected[field], rel_tol=1e-6, abs_tol=1e-6):
                raise ValueError(f"MIRcat {field} readback differs from the selected setting")
        original_limits = self.readbacks.get("configured_pulse_limits")
        if original_limits and (record["pulse_limits"] != original_limits["pulse_limits"] or
                                tuple(record["current_limits"]) != tuple(original_limits["current_limits"])):
            raise ValueError("MIRcat pulse/current limits changed after configuration")
        record["valid"] = True
        return record

    def _wait_reference_lock(self, check, timeout_s=10.):
        """Reference-only preparation; hardware frames still schedule all edges."""
        deadline = monotonic() + timeout_s
        while True:
            check()
            if self._health(allow_reference_unlock=True)["reference_locked"]:
                return
            if monotonic() >= deadline:
                raise TimeoutError("HF2LI reference lock timeout")
            self._wait(min(.025, deadline - monotonic()), check)

    def _health(self, *, allow_reference_unlock=False):
        self.verify_pump_off()
        if not self.qcl.is_interlock_set() or not self.qcl.is_key_switch_set() or self.qcl.get_system_error_word():
            raise RuntimeError("MIRcat interlock/key/error state is invalid")
        profile = self.plan.selected["hf2li"]
        frequency = self.hf.get_oscillator_frequency(1)
        if not math.isfinite(frequency) or abs(frequency) > 1e-9:
            raise RuntimeError("HF2LI detector oscillator must remain at zero frequency")
        inputs = (0, 1) if self.plan.settings.mode == "dual" else (0,)
        health = self.hf.read_acquisition_health(reference_pll=int(profile["pll"]["index"]), input_indices=inputs)
        self.readbacks.setdefault("health_observations", []).append(deepcopy(health))
        reference_valid = health.get("reference_locked") is True or (allow_reference_unlock and health.get("reference_locked") is False)
        if not reference_valid or health.get("clock_locked") is not True or health.get("overload") is not False:
            raise RuntimeError(f"HF2LI lock/clipping health is not valid: {health}")
        return health

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
                attempt(f"restore QCL {params['qcl']}", lambda p=params: qcl.set_qcl_operating_params(**p))
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
                              "pulse_width_ns": qcl.get_qcl_pulse_width(index), "current_ma": qcl.get_qcl_current(index),
                              "laser_mode": qcl.get_qcl_operating_mode(index), "temperature_c": qcl.get_qcl_set_temperature(index)}
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
                pll_enabled = {path: item for path, item in snapshot["nodes"].items() if "/plls/" in path and path.endswith("/enable")}
                hf.configure_demodulators([{"index": index, "enable": False} for index in range(6)])
                hf.configure_pll({"index": 1, "enable": False})
                snapshot["nodes"] = {path: item for path, item in snapshot["nodes"].items()
                                     if path not in enabled and path not in pll_enabled and "/oscs/0/" not in path}
                # Restore filters/rates with every spectral stream disabled; the
                # original aggregate becomes active only after all rates return.
                detail = hf.reload_settings_snapshot(snapshot)
                hf.reload_settings_snapshot({"nodes": pll_enabled})
                hf.reload_settings_snapshot({"nodes": enabled})
                return detail
            attempt("restore HF2LI", restore_hf)
            def check_hf():
                actual = hf.export_settings_snapshot(preset=self.snapshot_preset)
                expected = deepcopy(self.before["hf2li"])
                expected["nodes"] = {path: item for path, item in expected["nodes"].items() if "/oscs/0/" not in path}
                if expected["nodes"].get(f"/{hf.device_id}/plls/1/enable", {}).get("value"):
                    expected["nodes"].pop(f"/{hf.device_id}/oscs/1/freq", None)
                comparison = hf.compare_settings_snapshots(expected, actual)
                if not comparison["match"] or actual.get("read_errors"):
                    raise RuntimeError(str(comparison))
                comparison["observed_oscillator_nodes"] = {path: item for path, item in actual["nodes"].items() if "/oscs/" in path}
                comparison["oscillator_note"] = "Manual detector oscillator restored and compared; externally controlled oscillator frequencies retained as observations"
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
                qcl = self.devices["mircat"]
                observed = {"read_errors": {}}
                # Retain all available final observations even when one getter
                # fails. A successful stop/disarm command is not a readback.
                records["MIRcat final idle readbacks"] = observed
                for key, getter in (("emission_on", qcl.is_emission_on), ("armed", qcl.is_laser_armed),
                                    ("scan_status", qcl.get_scan_status),
                                    ("waiting_for_process_trigger", qcl.get_scan_waiting_process_trigger)):
                    try:
                        observed[key] = getter()
                    except Exception as exc:
                        observed[key] = None
                        observed["read_errors"][key] = str(exc)
                scan = observed.get("scan_status")
                scan = scan if isinstance(scan, dict) else {}
                expected_false = {key: observed.get(key) for key in ("emission_on", "armed", "waiting_for_process_trigger")}
                expected_false.update({key: scan.get(key) for key in ("scan_in_progress", "scan_active", "scan_paused")})
                unresolved = [name for name, value in expected_false.items() if value is not False]
                if unresolved or observed["read_errors"]:
                    raise RuntimeError("MIRcat safe idle is unverified: " + ", ".join(unresolved or observed["read_errors"]))
                return observed
            attempt("verify MIRcat safe idle", verify_qcl)
        for name, device in reversed(tuple(self.devices.items())):
            attempt(f"close {name}", device.deinitialize if name == "mircat" else device.close)
        return {"safe_verified": not errors, "errors": errors, "records": records,
                "policy": "Restore configuration with both timing engines and all optical outputs inhibited; never restart prior emission."}
