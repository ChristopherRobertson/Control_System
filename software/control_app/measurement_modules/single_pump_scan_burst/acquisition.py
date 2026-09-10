"""Owned installed-device acquisition for one optical pump and explicit bursts.

HF2LI poll records retain their native ticks. Host waits only prepare blocks;
T660 frames execute edges and HF2LI DIO observations define their actual times.
The default wiring has no independent optical pump detector or sample thermometer:
those readiness gaps are explicit, never substituted by electrical sync or TECs.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextvars import copy_context
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import math
from threading import Thread
from time import monotonic

import numpy as np


class AcquisitionStopped(RuntimeError):
    pass


class ReadinessError(ValueError):
    pass


def data(value):
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    return dict(value) if isinstance(value, Mapping) else value


def field(value, name, default=None):
    return value.get(name, default) if isinstance(value, Mapping) else getattr(value, name, default)


def flatten_native(record, prefix=""):
    """Flatten SDK trees without coercing any native numeric dtype."""
    result = {}
    for key, value in record.items():
        name = prefix + str(key).replace("/", "_").replace(".", "_")
        if isinstance(value, Mapping):
            result.update(flatten_native(value, name + "__"))
        elif isinstance(value, (list, tuple)) and value and isinstance(value[0], Mapping):
            for index, item in enumerate(value):
                result.update(flatten_native(item, name + f"_{index}__"))
        elif value is not None:
            array = np.asarray(value)
            if not array.dtype.hasobject:
                result[name] = array
    return result


def rising_edges(ticks, words, bit):
    ticks, words = np.asarray(ticks), np.asarray(words, dtype=np.uint32)
    high = (words & np.uint32(1 << bit)) != 0
    # A high first sample is an unknown edge, never an invented event at t[0].
    return ticks[np.flatnonzero(high[1:] & ~high[:-1]) + 1]


def reconstruct_native(streams, *, clockbase_hz, markers_cm1, expected_scans, sample_demod=0,
                       reference_demod=None, timing_demod=2, sample_latency_s=None, reference_latency_s=None,
                       scan_direction_high_increasing=True):
    """Reconstruct only bracketed controller-marker support, keeping gaps NaN."""
    timing = streams[timing_demod]
    ticks = np.asarray(timing["timestamp"])
    words = np.asarray(timing["dio"], dtype=np.uint32)
    if ticks.ndim != 1 or ticks.size < 2 or np.any(ticks[1:] <= ticks[:-1]):
        raise ReadinessError("Timing stream has missing, duplicate or decreasing native ticks")
    starts = rising_edges(ticks, words, 21)
    ends = rising_edges(ticks, ~words, 21)
    marker_ticks = rising_edges(ticks, words, 22)
    pump_ticks = rising_edges(ticks, words, 17)
    if len(starts) != expected_scans:
        raise ReadinessError(f"Observed {len(starts)} sweep starts; planned {expected_scans}")
    result = {"native_timing_ticks": ticks, "native_dio": words,
              "native_pump_sync_ticks": pump_ticks, "native_sweep_start_ticks": starts,
              "clockbase_hz": np.asarray(clockbase_hz), "time_basis": np.asarray("HF2LI_native_clock")}
    targets = np.sort(np.asarray(markers_cm1, dtype=float))
    for role, demod in (("sample", sample_demod), ("reference", reference_demod)):
        if demod is None:
            continue
        source = streams[demod]
        dticks = np.asarray(source["timestamp"])
        if dticks.ndim != 1 or dticks.size < 2 or dticks.dtype.kind not in "iu" or np.any(dticks[1:] <= dticks[:-1]):
            raise ReadinessError(f"Missing or unordered {role} native detector stream")
        latency = sample_latency_s if role == "sample" else reference_latency_s
        correction = float(latency or 0.)
        if not math.isfinite(correction) or correction < 0:
            raise ReadinessError("Detector response latency must be a finite nonnegative calibrated delay")
        signal = np.hypot(source["x"], source["y"]) if "x" in source else np.asarray(source["r"])
        if signal.shape != dticks.shape:
            raise ReadinessError(f"{role} native detector values and timestamps do not align")
        wn = np.full(dticks.shape, np.nan)
        scan = np.full(dticks.shape, -1, dtype=np.int64)
        direction = np.zeros(dticks.shape, dtype=np.int8)
        flags = np.zeros(dticks.shape, dtype=np.uint32)
        for index, start in enumerate(starts):
            ending = ends[ends > start]
            if not ending.size:
                raise ReadinessError("Missing observed sweep end; native trajectory is incomplete")
            stop = ending[0]
            if index + 1 < starts.size and stop >= starts[index + 1]:
                raise ReadinessError("Ambiguous overlapping native sweep activity")
            marks = marker_ticks[(marker_ticks >= start) & (marker_ticks <= stop)]
            mask = (dticks >= start) & (dticks <= stop)
            scan[mask] = index
            idx = np.searchsorted(ticks, start)
            sign = 1 if bool(words[idx] & (1 << 20)) == scan_direction_high_increasing else -1
            direction[mask] = sign
            if marks.size != targets.size or marks.size < 2:
                flags[mask] |= 1
                continue
            ordered = targets if sign > 0 else targets[::-1]
            inside = mask & (dticks >= marks[0]) & (dticks <= marks[-1])
            # Subtract integers BEFORE float conversion to protect large ticks.
            relative_ticks = (dticks[inside] - marks[0]).astype(float) - correction * clockbase_hz
            wn[inside] = np.interp(relative_ticks, (marks - marks[0]).astype(float), ordered,
                                  left=np.nan, right=np.nan)
        result[f"native_{role}_ticks"] = dticks
        result[f"{role}_time_s"] = dticks.astype(float) / float(clockbase_hz) - correction
        result[f"{role}_latency_s"] = np.asarray(correction)
        result[f"{role}_response_correction_applied"] = np.asarray(latency is not None)
        result[f"{role}_time_interpretation"] = np.asarray("calibrated detector-latency corrected" if latency is not None else "HF2LI output sample time; optical detector/filter response unresolved")
        result[role] = np.asarray(signal)
        result["wavenumber_cm1" if role == "sample" else "reference_wavenumber_cm1"] = wn
        if role == "sample":
            result.update(scan_index=scan, direction=direction, flags=flags)
        for name, array in source.items():
            result[f"native_{role}_{name}"] = np.asarray(array)
    return result


class ConnectedBurstAdapter:
    """Fresh host service instances. Every method is called in the owner scope."""
    def __init__(self, context, operation, plan, *, cancel, progress, store):
        self.context, self.operation, self.plan = context, operation, plan
        self.settings, self.cancel, self.progress, self.store = plan.settings, cancel, progress, store
        self.devices, self.original, self.pending = {}, {}, []
        from control_app.measurement_host.context import thaw_data
        self.config = thaw_data(operation.configuration)
        self.recipe = deepcopy(field(self.settings, "hardware_evidence", {}).get("operating_configuration", {}))
        # This package owns its operating schema. Promoted evidence supplies the
        # topology/calibration; selected unit-bearing settings supply commands.
        if self.recipe:
            selected = {key: value["selected"] for key, value in plan.selected_values.items()}
            self.recipe["probe_clock_recipe"] = deepcopy(data(field(plan, "probe_clock_recipe", {})))
            self.recipe["frame_input_frequency_hz"] = selected.get("probe_rate_hz", self.settings.probe_rate_hz)
            self.recipe.setdefault("trajectory", {}).update(start_cm1=self.settings.scan_start_cm1,
                stop_cm1=self.settings.scan_stop_cm1, scan_speed_cm1_s=self.settings.scan_speed_cm1_s, qcl=self.settings.qcl)
            self.recipe["qcl_pulse_parameters"] = {"qcl": self.settings.qcl,
                "pulse_rate_hz": self.recipe["frame_input_frequency_hz"], "pulse_width_ns": selected.get("probe_pulse_width_s", self.settings.probe_pulse_width_s) * 1e9,
                "current_ma": self.settings.probe_current_ma}
            hf = self.recipe.setdefault("hf2li", {})
            for role, index, voltage in (("sample", 0, self.settings.sample_input_range_v), ("reference", 1, self.settings.reference_input_range_v)):
                if role == "reference" and self.settings.mode != "dual":
                    continue
                hf.setdefault("signal_inputs", {}).setdefault(role, {}).update(index=index, range_v=voltage)
            demods = []
            for index, rate, tc, order, adc in ((0, self.settings.sample_rate_hz, self.settings.hf2_filter_tc_s, self.settings.hf2_filter_order, 0),
                    (3, self.settings.reference_rate_hz, self.settings.reference_filter_tc_s, self.settings.reference_filter_order, 1),
                    (2, self.settings.timing_rate_hz, self.settings.hf2_filter_tc_s, self.settings.hf2_filter_order, 0)):
                if index == 3 and self.settings.mode != "dual":
                    continue
                demods.append({"index": index, "enable": True, "adcselect": adc, "oscselect": 0,
                    "harmonic": 1, "rate_sps": rate, "timeconstant_s": tc, "order": order, "trigger": 0})
            hf["demodulators"] = demods
        self.stream_sequence = 0
        self.last_native_time = None
        self.clockbase = None
        self._polls = []
        self._reference_ready = False

    def check(self):
        if self.cancel.is_set():
            raise AcquisitionStopped("Acquisition stopped")

    def _call(self, callback, *, timeout_s=45):
        """Cancellation while SDK programming; unsettled calls prevent safe release."""
        self.check()
        result, errors = [], []
        def target():
            try:
                result.append(callback())
            except BaseException as exc:
                errors.append(exc)
        thread = Thread(target=copy_context().run, args=(target,), daemon=True)
        self.pending.append(thread)
        thread.start()
        deadline = monotonic() + timeout_s
        while thread.is_alive():
            self.check()
            if monotonic() > deadline:
                raise TimeoutError("Instrument programming did not finish; retained ownership fault required")
            self.cancel.wait(.02)
        if errors:
            raise errors[0]
        return result[0] if result else None

    def configure(self, *, pumped=False):
        self.check()
        if not self.recipe:
            raise ReadinessError("Load a promoted single_pump_scan_burst operating configuration; no Phase Scan defaults apply")
        requested_devices = ["hf2li", "t660_1", "t660_2", "mircat"]
        if pumped or self.recipe.get("capture_preliminary_diagnostics"):
            requested_devices.append("picoscope")
        for name in requested_devices:
            self.check()
            kwargs = {"capture_settings": deepcopy(self.recipe["picoscope_capture_settings"])} if name == "picoscope" else {}
            unit = self.context.devices.create(name, self.operation, **kwargs)
            self.devices[name] = unit
            method = {"hf2li": "connect", "t660_1": "connect", "t660_2": "connect",
                      "mircat": "initialize", "picoscope": "open_unit"}[name]
            self._call(getattr(unit, method))
        if "sample_temperature" in self.context.devices.available(hardware=self.operation.hardware):
            self.devices["sample_temperature"] = self.context.devices.create("sample_temperature", self.operation)
        self.hf, self.clock, self.timing, self.qcl = (
            self.devices[name] for name in ("hf2li", "t660_1", "t660_2", "mircat"))
        self.pico = self.devices.get("picoscope")
        self._preserve()
        self.idle()
        self._validate_routes(pumped)
        hf = self.recipe.get("hf2li", {})
        demods = deepcopy(hf.get("demodulators", []))
        self.sample_demod, self.reference_demod, self.timing_demod = 0, (3 if self.operation.instance_id.endswith(":dual") else None), 2
        expected = {0, 2} | ({3} if self.reference_demod is not None else set())
        if {int(d["index"]) for d in demods if d.get("enable")} != expected:
            raise ReadinessError("Installed roles require demod 0 sample, demod 2 DIO, and demod 3 reference in dual mode")
        if sum(float(d["rate_sps"]) for d in demods if d.get("enable")) > float(hf.get("aggregate_limit_sps", 0)):
            raise ReadinessError("Selected aggregate HF2LI throughput exceeds qualified connected capacity")
        self.hf.configure_demodulators([{"index": i, "enable": False} for i in range(6)])
        self.hf.configure_signal_inputs(hf.get("signal_inputs", {}))
        self.hf.configure_pll(hf.get("pll", {}))
        self.hf.configure_demodulators(demods)
        self.hf.sync()
        for selection in hf.get("signal_inputs", {}).values():
            if "range_v" in selection:
                actual = self.hf._get_node("double", f"/{self.hf.device_id}/sigins/{selection['index']}/range")
                if not math.isclose(float(actual), float(selection["range_v"]), rel_tol=1e-7):
                    raise ReadinessError("HF2LI detector input range readback differs from the selected range")
        for selection in demods:
            index = int(selection["index"])
            for key, node, typ in (("rate_sps", "rate", "double"), ("order", "order", "int"),
                                   ("timeconstant_s", "timeconstant", "double")):
                if key in selection:
                    actual = self.hf._get_node(typ, f"/{self.hf.device_id}/demods/{index}/{node}")
                    if not math.isclose(float(actual), float(selection[key]), rel_tol=1e-7, abs_tol=1e-12):
                        raise ReadinessError(f"HF2LI demod {index} {key} changed: selected {selection[key]}, actual {actual}")
        self.clockbase = int(self.hf.get_clockbase())
        probe = deepcopy(self.recipe.get("probe_clock_recipe"))
        if not probe or probe.get("trigger_source") != "OFF" or probe.get("channels", {}).get("D", {}).get("enabled"):
            raise ReadinessError("Provide a qualified inhibited T660-1 probe/reference/frame-input recipe, D disabled")
        self.clock.apply_recipe(probe)
        self.qcl.set_qcl_pulse_params(**self.recipe["qcl_pulse_parameters"])
        self.qcl.arm()
        self.hf.start_acquisition(demodulators=sorted(expected), fields=("x", "y", "dio"))
        self.temperature()
        return {"hf2li": self.hf.export_settings_snapshot(preset=self._hf_preset),
                "probe_recipe": probe, "clockbase_hz": self.clockbase,
                "readiness": deepcopy(self.recipe.get("qualifications", {}))}

    def inspect_capabilities(self):
        self.check()
        hf = self.context.devices.create("hf2li", self.operation)
        self.devices["hf2li"] = hf
        self._call(hf.connect)
        method = hf.discover_dual_phase_scan_capabilities if self.settings.mode == "dual" else hf.discover_phase_scan_capabilities
        # These are host SERVICE readback probes, not imports of Phase Scan's
        # scientific runner, settings, presets or normalization.
        readback = self._call(method, timeout_s=180)
        from .settings import Capabilities
        self.hf = hf
        timer = self.context.devices.create("t660_2", self.operation)
        self.devices["t660_2"] = timer
        self._call(timer.connect)
        frame_capacity = timer.verified_frame_capacity()
        frame_status = timer.get_frames_status()
        frame_identity = timer.identify()
        qualifications = self.recipe.get("qualifications", {})
        topology = all(qualifications.get(key, {}).get("accepted") and qualifications.get(key, {}).get("record_id")
                       for key in ("tee_receiver_topology", "clock_transfer", "trajectory", "detector_roles"))
        optical = self.recipe.get("optical_pump_diagnostic", {})
        optical_ready = (bool(optical.get("accepted")) and bool(optical.get("calibration_id"))
            and optical.get("signal_kind") == "independent_optical_pump"
            and optical.get("channel") in ("A", "B") and bool(optical.get("preserves_spectral_detector_topology"))
            and isinstance(self.recipe.get("picoscope_capture_settings"), dict))
        thermal_ready = False
        thermal_error = None
        try:
            record = self.temperature()
            thermal_ready = record.get("temperature_identity") == self.settings.temperature_identity
        except (KeyError, ValueError) as exc:
            thermal_error = str(exc)
        sample = readback.get("sample", readback)
        reference = readback.get("reference", {})
        cap = Capabilities(frame_capacity=int(frame_capacity), frame_feature_verified=frame_status in ("OFF", "DONE") and bool(frame_identity),
            sample_rates_hz=tuple(sample["rates_sps"]), reference_rates_hz=tuple(reference.get("rates_sps", ())),
            timing_rates_hz=(float(readback["timing_rate_sps"]),), detector_rates_verified=bool(readback["verified"]),
            topology_verified=bool(topology), optical_pump_observation_available=bool(optical_ready),
            temperature_observation_available=bool(thermal_ready),
            device_ids={"hf2li": hf.device_id, "t660_2": frame_identity},
            actual_values={"hf2li": readback, "t660_2": {"capacity": frame_capacity, "status": frame_status},
                           "qualifications": qualifications, "temperature_error": thermal_error})
        return {"capabilities": cap.to_dict(), "readbacks": cap.actual_values}

    def _validate_routes(self, pumped):
        qualifications = self.recipe.get("qualifications", {})
        for key in ("tee_receiver_topology", "clock_transfer", "trajectory", "detector_roles"):
            item = qualifications.get(key, {})
            if not item.get("accepted") or not item.get("record_id"):
                raise ReadinessError(f"Applicable accepted {key} qualification is required")
        if pumped:
            diagnostic = self.recipe.get("optical_pump_diagnostic", {})
            if (not diagnostic.get("accepted") or not diagnostic.get("calibration_id")
                    or diagnostic.get("channel") not in ("A", "B")
                    or diagnostic.get("signal_kind") != "independent_optical_pump"):
                raise ReadinessError("Independent optical pump observation is unqualified: default Pico A/B are MIR detectors; DIO17 is electrical")
            if not diagnostic.get("preserves_spectral_detector_topology"):
                raise ReadinessError("Optical pump diagnostic route must preserve this mode's qualified HF2LI spectral detector topology")

    def _preserve(self):
        from control_app.devices.hf2li_service import HF2LIPreset
        # Include ALL demods because configuration disables inactive streams.
        self._hf_preset = HF2LIPreset("single-pump-preservation", {"demodulators": [{"index": i} for i in range(6)]})
        self.original["hf2li"] = self.hf.export_settings_snapshot(preset=self._hf_preset)
        if self.original["hf2li"].get("read_errors"):
            raise ReadinessError("Cannot preserve complete HF2LI original readbacks")
        self.original["mircat"] = {"trigger": self.qcl.get_wavelength_trigger_params(),
            "marker_width_us": self.qcl.get_wavelength_trigger_pulse_width_us(),
            "qcls": [{"qcl": q, "pulse_rate_hz": self.qcl.get_qcl_pulse_rate(q),
                      "pulse_width_ns": self.qcl.get_qcl_pulse_width(q), "current_ma": self.qcl.get_qcl_current(q)}
                     for q in range(1, self.qcl.get_num_installed_qcls() + 1)]}
        for name in ("t660_1", "t660_2"):
            unit = self.devices[name]
            self.original[name] = {"readback": unit.read_active_settings(),
                                   "references": {str(i): int(unit.command(f"TIME:RELTo{i}?")) for i in range(1, 9)}}
            saved = self.original[name]
            from control_app.devices.t660_service import _seconds_value
            relative = {}
            for index, channel in enumerate("ABCD"):
                for edge, key in ((2 * index + 1, "delay_edge"), (2 * index + 2, "width_edge")):
                    observed = saved["readback"]["channels"][channel][key]
                    if not observed.get("ok"):
                        raise ReadinessError(f"Cannot preserve {name} {channel} {key}")
                    relative[edge] = _seconds_value(observed["response"])
            absolute = {0: 0.}
            def resolve(edge, ancestors=()):
                if edge in absolute:
                    return absolute[edge]
                if edge in ancestors or str(edge) not in saved["references"]:
                    raise ReadinessError(f"Cannot preserve cyclic/unknown {name} edge reference")
                absolute[edge] = relative[edge] + resolve(saved["references"][str(edge)], (*ancestors, edge))
                return absolute[edge]
            for edge in range(1, 9):
                resolve(edge)
            saved["absolute_edge_seconds"] = {str(k): v for k, v in absolute.items()}
        self.store.save_record("original-instrument-state", self.original)

    def temperature(self):
        thermometer = self.devices.get("sample_temperature")
        record = data(thermometer.read_temperature()) if thermometer else deepcopy(self.recipe.get("sample_temperature_observation", {}))
        if not record.get("observation_id") or not record.get("temperature_identity"):
            raise ReadinessError("Provide a measured illuminated-sample temperature observation, identity and uncertainty; MIRcat TEC is not sample temperature")
        measured = datetime.fromisoformat(record["observed_utc"])
        age = (datetime.now(timezone.utc) - measured).total_seconds()
        if age < 0 or age > float(record.get("valid_for_s", 0)):
            raise ReadinessError("Sample temperature observation is stale; a guided new measurement or installed thermometer is required")
        value, uncertainty = float(record["temperature_k"]), float(record["uncertainty_k"])
        if not math.isfinite(value) or not math.isfinite(uncertainty) or uncertainty < 0:
            raise ReadinessError("Invalid sample temperature observation")
        self.store.append_event("temperature", record)
        return record

    def program_block(self, block, *, pump_allowed=False):
        self.check()
        self.idle()
        self.clock.apply_recipe(deepcopy(self.recipe["probe_clock_recipe"]))
        frames = deepcopy(list(field(block, "frames")))
        enabled = sum(bool(f["channels"]["A"]["enabled"]) or bool(f["channels"]["B"]["enabled"]) for f in frames)
        if enabled != (1 if pump_allowed else 0):
            raise ReadinessError("Frame table violates exactly one pump in the first block and zero in every later block")
        upload = self.timing.preload_frame_table(frames, predivider=int(field(block, "predivider")),
            input_frequency_hz=float(self.recipe["frame_input_frequency_hz"]),
            progress=lambda completed, total: self.progress(stage="upload", message=f"Acknowledged timing frames {completed}/{total}",
                                                           fraction=completed / total), cancel_check=self.check)
        self.store.append_event("timing_upload", {"block_id": field(block, "block_id"), **upload})
        self.check()
        trajectory = self.recipe["trajectory"]
        start, stop = float(trajectory["start_cm1"]), float(trajectory["stop_cm1"])
        self.qcl.tune_to_wavenumber(start, qcl=int(trajectory["qcl"]))
        self._wait(self.qcl.is_tuned, 45, "MIRcat tuning")
        self.qcl.set_external_sweep_trigger_params(start_cm1=start, stop_cm1=stop,
            wavelength_trigger_interval_cm1=float(trajectory["marker_interval_cm1"]), external_process_trigger=True)
        self.qcl.set_wavelength_trigger_pulse_width_us(int(trajectory["marker_width_us"]))
        self.qcl.turn_emission_on(approved_laser_safety_condition=bool(self.recipe.get("laser_safety_approved")))
        self.qcl.cancel_manual_tune()
        expected = {"start_cm1": start, "stop_cm1": stop, "scan_rate_cm1_s": float(trajectory["scan_speed_cm1_s"]),
                    "qcl": int(trajectory["qcl"]), "repetitions": int(field(block, "scan_count"))}
        self._call(lambda: self.qcl.start_sweep_scan(**expected))
        actual = self.qcl.get_sweep_parameters()
        for key in ("start_cm1", "stop_cm1", "scan_rate_cm1_s", "repetitions"):
            if not math.isclose(float(actual[key]), float(expected[key]), rel_tol=1e-6, abs_tol=1e-5):
                raise ReadinessError(f"MIRcat rejected selected {key}")
        identity = self.qcl.get_wavelength_trigger_channel_params(int(trajectory["qcl"]))
        direction = 1 if identity["stop"] >= identity["start"] else -1
        self.marker_targets = identity["start"] + direction * abs(identity["interval"]) * np.arange(int(identity["num_triggers"]))
        if (identity.get("channel") != int(trajectory["qcl"]) or not len(self.marker_targets)
                or not math.isclose(self.marker_targets[-1], identity["stop"], abs_tol=1e-4)
                or not math.isclose(identity["start"], start, abs_tol=1e-4)
                or not math.isclose(identity["stop"], stop, abs_tol=1e-4)):
            raise ReadinessError("Controller wavelength marker count, interval or bounds disagree with selected trajectory")
        if len(self.marker_targets) < 2 or identity.get("units_name") not in ("cm-1", "cm^-1", "cm⁻¹", "wavenumber_cm1"):
            # SDK uses its cm^-1 enum; retain accepted numeric unit as well.
            if identity.get("units") != 2 or len(self.marker_targets) < 2:
                raise ReadinessError("MIRcat marker identities do not establish cm^-1 trajectory support")
        self.store.append_event("mircat_block_readback", {"block_id": field(block, "block_id"), "requested": expected,
                                                         "actual": actual, "marker_identity": identity})
        self._wait(self.qcl.get_scan_waiting_process_trigger, 30, "MIRcat process-trigger readiness")
        # Restore the lock-in reference while probe and frame-input outputs are
        # inhibited; settling cannot emit a pump or initiate a sweep.
        self.clock.disable_channel("B")
        self.clock.disable_channel("C")
        self.clock.enable_channel("A")
        self.clock.set_trigger_source("SYN")
        self.clock.command("START", expect_response=False)
        self._reference_ready = True
        deadline = monotonic() + float(self.settings.tuning_settling_time_s or 0)
        while monotonic() < deadline:
            self.check()
            self.cancel.wait(.025)
        frequency = self.hf.get_oscillator_frequency(0)
        if not math.isclose(float(frequency), float(self.settings.probe_rate_hz), rel_tol=.02):
            raise ReadinessError("HF2LI reference frequency does not follow the selected T660-1 reference")

    def _wait(self, predicate, timeout_s, label):
        deadline = monotonic() + timeout_s
        while not predicate():
            self.check()
            if monotonic() > deadline:
                raise TimeoutError(label)
            self.cancel.wait(.02)

    def _poll(self):
        self.check()
        record = self.hf.read_acquisition(.025)
        self.store.save_chunk(f"hf2-native-{self.stream_sequence:08d}", flatten_native(record))
        self.stream_sequence += 1
        native = record.get("data", {})
        self._polls.append(native)
        for path, item in native.items():
            if f"/demods/{self.timing_demod}/" in path and "timestamp" in item and len(item["timestamp"]):
                self.last_native_time = int(item["timestamp"][-1]) / self.clockbase
        self.check()

    def capture_block(self, block, *, pump_allowed=False, before_fire=None):
        self.check()
        self._polls = []
        self._poll()  # explicit pretrigger native support
        def start():
            self.check()
            if before_fire:
                before_fire()  # durable pump intent BEFORE enabling its hardware table
            self.timing.start_frame_table()
            # Software enables the finite engine. Precise frames use native clock pulses.
            self.clock.enable_channel("B")
            self.clock.enable_channel("C")
        diagnostic = None
        if pump_allowed:
            diagnostic = self.pico.capture_block_data(after_arm=start, while_waiting=self._poll,
                                                      before_transfer=self.check)
            self.store.save_chunk(f"pico-{field(block, 'block_id')}", flatten_native(diagnostic))
        else:
            start()
        deadline = monotonic() + float(field(block, "duration_s")) + float(self.recipe.get("block_timeout_margin_s", 10))
        last_thermal = monotonic()
        while True:
            self._poll()
            if monotonic() - last_thermal >= .5:
                self.progress(stage="acquisition", message="Native HF2LI spectral and DIO capture", temperature=self.temperature())
                if not math.isclose(self.hf.get_oscillator_frequency(0), self.settings.probe_rate_hz, rel_tol=.02):
                    raise ReadinessError("HF2LI reference unlocked during acquisition; native data retained")
                for input_index in ((0, 1) if self.reference_demod is not None else (0,)):
                    if self.hf._get_node("int", f"/{self.hf.device_id}/status/flags/adcclip/{input_index}"):
                        raise ReadinessError(f"HF2LI input {input_index + 1} clipping; native records retained")
                last_thermal = monotonic()
            status = self.timing.get_frames_status()
            if status == "DONE":
                break
            if status == "ERROR":
                raise ReadinessError("T660 finite table reported ERROR")
            if monotonic() > deadline:
                raise TimeoutError("Native finite table did not complete before its declared bound")
        self._poll()
        self.idle()
        streams = {}
        for native in self._polls:
            for path, item in native.items():
                if "/demods/" not in path or not isinstance(item, Mapping):
                    continue
                demod = int(path.split("/demods/")[1].split("/")[0])
                dest = streams.setdefault(demod, {})
                for name, values in item.items():
                    arr = np.asarray(values)
                    if arr.ndim == 1:
                        dest.setdefault(name, []).append(arr)
        streams = {d: {k: np.concatenate(v) for k, v in tree.items()} for d, tree in streams.items()}
        self._polls = []
        result = reconstruct_native(streams, clockbase_hz=self.clockbase, markers_cm1=self.marker_targets,
            expected_scans=int(field(block, "scan_count")), sample_demod=self.sample_demod,
            reference_demod=self.reference_demod, timing_demod=self.timing_demod,
            sample_latency_s=self.recipe.get("detector_response", {}).get("sample_latency_s"),
            reference_latency_s=self.recipe.get("detector_response", {}).get("reference_latency_s"),
            scan_direction_high_increasing=self.recipe["qualifications"]["trajectory"].get("scan_direction_high_increasing", True))
        result["clipped"] = np.abs(result["sample"]) >= float(self.settings.sample_input_range_v)
        if self.reference_demod is not None:
            result["reference_clipped"] = np.abs(result["reference"]) >= float(self.settings.reference_input_range_v)
        observed_count = len(result["native_pump_sync_ticks"])
        if observed_count != (1 if pump_allowed else 0):
            raise ReadinessError(f"Observed electrical pump count {observed_count}; expected {int(pump_allowed)}; no retry")
        epoch = self._optical_epoch(diagnostic, result) if pump_allowed else None
        return {"native": result, "epoch": epoch, "observed_scan_count": len(result["native_sweep_start_ticks"]),
                "observed_pump_count": observed_count, "end_native_time_s": self.last_native_time}

    def _optical_epoch(self, record, native):
        spec = self.recipe["optical_pump_diagnostic"]
        if record is None or record.get("overflow"):
            raise ReadinessError("Independent optical pump capture missing or clipped; no replacement pump")
        wave = np.asarray(record[f"ch_{spec['channel'].lower()}_adc"])
        signal = wave * int(spec.get("polarity", 1))
        above = signal > float(spec["threshold_adc"])
        edges = np.flatnonzero(above[1:] & ~above[:-1]) + 1
        lo, hi = spec["arrival_window_samples"]
        if len(edges) != 1 or not lo <= edges[0] <= hi:
            raise ReadinessError(f"Observed {len(edges)} qualified optical pump events; one required, no retry")
        # Pico EXT is observed Sweep Active, also recorded in HF2LI DIO21.
        dt = (int(edges[0]) - int(record["pre_trigger_samples"])) * float(record["sample_interval_ns"]) * 1e-9
        pump = float(native["native_sweep_start_ticks"][0]) / self.clockbase + dt + float(spec["pico_to_hf2_transfer_s"])
        return {"pump_time_s": pump, "pump_timestamp_ticks": int(native["native_sweep_start_ticks"][0]),
                "optical_offset_s": dt + float(spec["pico_to_hf2_transfer_s"]),
                "clock_domain": "HF2LI_native_clock", "clockbase_hz": self.clockbase,
                "device_id": self.hf.device_id, "electrical_sync_tick": int(native["native_pump_sync_ticks"][0]),
                "optical_sample_index": int(edges[0]), "optical_event_count": 1,
                "optical_calibration_id": spec["calibration_id"], "uncertainty_s": float(spec["uncertainty_s"]),
                "sample_state": self.state_evidence(), "independently_observed": True}

    def native_now(self):
        self._polls = []
        self._poll()
        self._polls = []
        if self.last_native_time is None:
            raise ReadinessError("No current native clock observation; host time cannot establish a pump epoch")
        return self.last_native_time

    def state_evidence(self):
        identities = {key: getattr(self.settings, key) for key in ("condition_id", "sample_id", "preparation_id", "accepted_state_id",
            "matrix_id", "cell_id", "position_id", "temperature_identity", "thermal_history_id")}
        return {**identities, "device_id": getattr(self.hf, "device_id", None),
                "configuration_record_id": self.recipe.get("configuration_record_id"),
                "clock_epoch_id": self.recipe.get("clock_epoch_id")}

    def verify_continuation(self, continuation):
        proof = continuation.get("state_evidence") or self.recipe.get("continuation_evidence", {})
        if not proof.get("accepted_by") or not proof.get("uninterrupted_native_clock") or not proof.get("unchanged_sample_state"):
            raise ReadinessError("Cannot establish retained native pump epoch and sample state; preserve incomplete result and start an explicitly new state")
        epoch = continuation["epoch"]
        if epoch.get("sample_state") != self.state_evidence() or not self.state_evidence().get("clock_epoch_id"):
            raise ReadinessError("Continuation instrument/sample/clock epoch identity mismatch")
        if self.native_now() <= float(epoch["pump_time_s"]):
            raise ReadinessError("Native clock reset or epoch ambiguous; replacement pumping is prohibited")

    def idle(self):
        # Physical idle does not imply a reset biological state.
        for name in ("t660_2", "t660_1"):
            unit = self.devices.get(name)
            if unit:
                keep_reference = name == "t660_1" and self._reference_ready
                if not keep_reference:
                    unit.set_trigger_source("OFF")
                    unit.command("STOP", expect_response=False)
                if name == "t660_2":
                    unit.command("TFRame:STOp", expect_response=False)
                for channel in ("BCD" if keep_reference else "ABCD"):
                    unit.disable_channel(channel)
        if "mircat" in self.devices:
            self.devices["mircat"].turn_emission_off()
            self.devices["mircat"].stop_scan_if_needed()

    def restore(self):
        errors, records = [], {}
        # Do not race restoration writes against a still-running SDK call.
        # The coordinator fault retains the coupled instrument until explicit
        # recovery; no fresh run can take it over while the outcome is unknown.
        if any(thread.is_alive() for thread in self.pending):
            return {"safe_verified": False, "errors": ["Instrument SDK programming still in progress; concurrent restoration refused"],
                    "records": {"pending_commands": sum(t.is_alive() for t in self.pending)}}
        def attempt(label, callback):
            try:
                records[label] = callback()
            except Exception as exc:
                errors.append(f"{label}: {exc}")
        # Continue all cleanup actions after any failure.
        for name in ("t660_2", "t660_1"):
            unit = self.devices.get(name)
            if unit:
                attempt(name + "-inhibit", lambda u=unit: u.set_trigger_source("OFF"))
                attempt(name + "-stop", lambda u=unit: u.command("STOP", expect_response=False))
                if name == "t660_2":
                    attempt(name + "-frames-stop", lambda u=unit: u.command("TFRame:STOp", expect_response=False))
                    for stage in ("ACTIVE", "NEXT", "QUEUE"):
                        attempt(name + "-train-" + stage, lambda u=unit, s=stage: u.configure_train(count=0, stage=s))
                # TFRame STOP may reinstall pre-frame channel enables. Disable
                # channels after stopping that engine, and verify after all writes.
                for channel in "ABCD":
                    attempt(name + "-disable-" + channel, lambda u=unit, c=channel: u.disable_channel(c))
        qcl = self.devices.get("mircat")
        if qcl:
            attempt("emission-off", qcl.turn_emission_off)
            attempt("scan-stop", qcl.stop_scan_if_needed)
            attempt("disarm", qcl.disarm)
        hf = self.devices.get("hf2li")
        if hf:
            attempt("unsubscribe", hf.stop_acquisition)
            if "hf2li" in self.original:
                def restore_hf():
                    restore_settings = deepcopy(self.original["hf2li"])
                    # An oscillator following an external PLL is an observation,
                    # not a restorable setting while the safe-idle reference is off.
                    restore_settings["nodes"] = {p: v for p, v in restore_settings["nodes"].items() if "/oscs/" not in p}
                    hf.reload_settings_snapshot(restore_settings)
                    comparison = hf.compare_settings_snapshots(restore_settings, hf.export_settings_snapshot(preset=self._hf_preset))
                    if not comparison["match"]:
                        raise RuntimeError(str(comparison))
                    return comparison
                attempt("hf2li-settings", restore_hf)
        if qcl and "mircat" in self.original:
            original = self.original["mircat"]
            for item in original["qcls"]:
                attempt(f"qcl-{item['qcl']}-settings", lambda p=item: qcl.set_qcl_pulse_params(**p))
            allowed = ("pulse_mode", "process_trigger_mode", "start", "stop", "interval", "units", "dwell_us", "after_off_us")
            attempt("qcl-trigger-settings", lambda: qcl.set_wavelength_trigger_params(**{k: v for k, v in original["trigger"].items() if k in allowed}))
            attempt("qcl-marker-width", lambda: qcl.set_wavelength_trigger_pulse_width_us(original["marker_width_us"]))
            def verify_qcl_settings():
                actual = qcl.get_wavelength_trigger_params()
                for key in allowed:
                    if key in original["trigger"] and (key not in actual or not math.isclose(float(actual[key]), float(original["trigger"][key]), rel_tol=1e-7, abs_tol=1e-6)):
                        raise RuntimeError(f"MIRcat original trigger setting {key} did not restore")
                if qcl.get_wavelength_trigger_pulse_width_us() != original["marker_width_us"]:
                    raise RuntimeError("MIRcat original marker width did not restore")
                for settings in original["qcls"]:
                    index = settings["qcl"]
                    for key, getter in (("pulse_rate_hz", qcl.get_qcl_pulse_rate), ("pulse_width_ns", qcl.get_qcl_pulse_width),
                                        ("current_ma", qcl.get_qcl_current)):
                        if not math.isclose(float(getter(index)), float(settings[key]), rel_tol=1e-6, abs_tol=1e-5):
                            raise RuntimeError(f"QCL {index} original {key} did not restore")
                return {"trigger": actual, "marker_width_us": original["marker_width_us"]}
            attempt("qcl-settings-verification", verify_qcl_settings)
        for name in ("t660_1", "t660_2"):
            if name in self.devices:
                if name in self.original:
                    def restore_timing(u=self.devices[name], saved=self.original[name]):
                        from control_app.devices.t660_service import _seconds_value
                        def response(item):
                            if not item.get("ok"):
                                raise RuntimeError("Original timing readback unavailable")
                            return str(item["response"]).strip()
                        for channel in "ABCD":
                            u.set_channel_timing_mode(channel, "rise_fall")
                        for edge in range(1, 9):
                            u.command(f"TIME:RELTo{edge} 0", expect_response=False)
                        absolute = saved["absolute_edge_seconds"]
                        for rising in (1, 3, 5, 7):
                            u.command(f"TIME:QUEue{rising} 0s", expect_response=False)
                            u.command(f"TIME:QUEue{rising+1} {absolute[str(rising+1)]:.12f}s", expect_response=False)
                            u.command(f"TIME:QUEue{rising} {absolute[str(rising)]:.12f}s", expect_response=False)
                        u.command("TIME:COMmit", expect_response=False)
                        for edge, reference in saved["references"].items():
                            u.command(f"TIME:RELTo{edge} {reference}", expect_response=False)
                        original = saved["readback"]
                        recipe = {"stop_first": True, "trigger_source": "OFF", "gate_mode": 0, "burst_enabled": False,
                            "predivider": int(response(original["queries"]["predivider"])),
                            "clock": {"frequency": response(original["queries"]["synth_frequency"])}, "channels": {}}
                        for channel, values in original["channels"].items():
                            recipe["channels"][channel] = {"enabled": False, "timing_mode": response(values["timing_mode"]),
                                "polarity": response(values["polarity"]), "termination": response(values["termination"])}
                        u.apply_recipe(recipe)
                        after = u.read_active_settings()
                        for channel, values in original["channels"].items():
                            for key in ("delay_edge", "width_edge"):
                                if not math.isclose(_seconds_value(response(values[key])), _seconds_value(response(after["channels"][channel][key])), abs_tol=1e-11):
                                    raise RuntimeError(f"Timing {channel} {key} did not restore")
                        return after
                    attempt(name + "-inhibited-settings", restore_timing)
                # Never restore active pump trains or a running source. Retain the
                # complete original state; inhibited readbacks are the safe target.
                def verify(u=self.devices[name]):
                    actual = u.read_active_settings()
                    if str(actual["queries"]["trigger_source"].get("response", "")).upper() != "OFF":
                        raise RuntimeError("Trigger source did not inhibit")
                    for channel, item in actual["channels"].items():
                        if str(item["enabled"].get("response", "")).strip().upper() not in ("0", "OFF"):
                            raise RuntimeError(f"Channel {channel} did not disable")
                    return actual
                attempt(name + "-safe-verification", verify)
        if qcl:
            def verify_qcl():
                if qcl.is_emission_on() or qcl.is_laser_armed():
                    raise RuntimeError("MIRcat safe-off readback failed")
                return {"emission_on": False, "armed": False}
            attempt("mircat-safe-verification", verify_qcl)
        if any(thread.is_alive() for thread in self.pending):
            errors.append("Instrument SDK programming still in progress; physical state unverified")
        for name, unit in self.devices.items():
            closer = {"hf2li": "close", "t660_1": "close", "t660_2": "close", "mircat": "deinitialize", "picoscope": "close_unit"}.get(name)
            if closer:
                attempt(name + "-close", getattr(unit, closer))
        return {"safe_verified": not errors, "errors": errors, "records": records,
                "restoration_target": "original detector/QCL settings and inhibited timing outputs; never repeat a pump"}
