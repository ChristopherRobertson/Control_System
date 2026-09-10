"""Owned installed-device acquisition for one pump and explicit scan bursts.

HF2LI poll records retain their native ticks. Host waits only prepare blocks;
T660 frames execute edges and HF2LI DIO observations define their actual times.
Electrical timing is usable directly. Optional optical and thermal observations
remain metadata and never substitute a claim the installed devices cannot make.
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


def acquisition_identity(settings):
    """Only measured-data-affecting selections determine baseline compatibility."""
    names = ("experiment_id", "mode", "scan_start_cm1", "scan_stop_cm1", "scan_speed_cm1_s", "scan_interval_s",
        "qcl", "probe_rate_hz", "probe_pulse_width_s", "probe_current_ma", "sample_demod", "reference_demod",
        "timing_demod", "sample_rate_hz", "reference_rate_hz", "timing_rate_hz", "hf2_filter_order", "hf2_filter_tc_s",
        "reference_filter_order", "reference_filter_tc_s", "sample_input_range_v", "reference_input_range_v")
    result = {name: field(settings, name) for name in names}
    if result["mode"] == "single":
        result = {name: value for name, value in result.items() if not name.startswith("reference_")}
    return result


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
                       scan_direction_high_increasing=True, pump_active_high=True):
    """Reconstruct only bracketed controller-marker support, keeping gaps NaN."""
    timing = streams[timing_demod]
    ticks = np.asarray(timing["timestamp"])
    words = np.asarray(timing["dio"], dtype=np.uint32)
    if ticks.ndim != 1 or ticks.size < 2 or np.any(ticks[1:] <= ticks[:-1]):
        raise ReadinessError("Timing stream has missing, duplicate or decreasing native ticks")
    starts = rising_edges(ticks, words, 21)
    ends = rising_edges(ticks, ~words, 21)
    marker_ticks = rising_edges(ticks, words, 22)
    pump_ticks = rising_edges(ticks, words if pump_active_high else ~words, 17)
    if len(starts) != expected_scans:
        raise ReadinessError(f"Observed {len(starts)} sweep starts; planned {expected_scans}")
    result = {"native_timing_ticks": ticks, "native_dio": words,
              "native_pump_sync_ticks": pump_ticks, "native_sweep_start_ticks": starts,
              "pump_electrical_edge": np.asarray("rising" if pump_active_high else "falling"),
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
        # Legacy material/calibration/evidence selections remain in the retained
        # settings only. Ordinary acquisition has no evidence-driven recipe.
        module_config = self.config.get("single_pump_scan_burst", {})
        self.recipe = deepcopy(module_config.get("diagnostics", {})) if isinstance(module_config, Mapping) else {}
        self._build_recipe()
        self.stream_sequence = 0
        self.last_native_time = None
        self.clockbase = None
        self._polls = []
        self._reference_ready = False
        self._health = []
        self._capture_cleanup_errors = []
        self._probe_enabled_at = None
        self.observed_probe_pulse_on_s = 0.
        self._inspection_only = False

    def _build_recipe(self):
        # Surelite Variable Sync is a separate output from T660's command
        # inputs. Manual 996-0207 p59 (PDF p69) specifies negative-going TTL;
        # its front-panel delay is variable, so this is electrical time only.
        if "pump_sync_active_high" not in self.recipe:
            self.recipe["pump_sync_active_high"] = False
            self.recipe["pump_sync_polarity_source"] = "Surelite Manual 996-0207 p59, Variable Sync OUT"
        else:
            self.recipe.setdefault("pump_sync_polarity_source", "frozen installed diagnostic pump_sync_active_high")
        selected = {key: value["selected"] for key, value in self.plan.selected_values.items()}
        self.recipe["probe_clock_recipe"] = deepcopy(data(field(self.plan, "probe_clock_recipe", {})))
        self.recipe["frame_input_frequency_hz"] = selected.get("probe_rate_hz", self.settings.probe_rate_hz)
        start, stop, speed = self.settings.scan_start_cm1, self.settings.scan_stop_cm1, self.settings.scan_speed_cm1_s
        trajectory = self.recipe.setdefault("trajectory", {})
        trajectory.update(start_cm1=start, stop_cm1=stop, scan_speed_cm1_s=speed, qcl=1)
        if start is not None and stop is not None and speed:
            interval = abs(stop - start) / 10.
            trajectory.setdefault("marker_interval_cm1", interval)
            trajectory.setdefault("marker_width_us", max(1, min(65535, int(interval / speed * 1e6 / 4))))
        width = selected.get("probe_pulse_width_s", self.settings.probe_pulse_width_s)
        internal_rate = field(field(self.plan.capabilities, "operating_values", {}), "mircat_internal_pulse_rate_hz",
                              field(self.settings, "mircat_internal_pulse_rate_hz"))
        self.recipe["qcl_pulse_parameters"] = {"qcl": 1,
            "pulse_rate_hz": internal_rate, "pulse_width_ns": None if width is None else width * 1e9,
            "current_ma": self.settings.probe_current_ma}
        hf = self.recipe.setdefault("hf2li", {})
        hf.setdefault("aggregate_limit_sps", field(self.plan.capabilities, "hf2_aggregate_rate_max_hz", 700000.))
        for role, index, voltage in (("sample", 0, self.settings.sample_input_range_v), ("reference", 1, self.settings.reference_input_range_v)):
            if role == "reference" and self.settings.mode != "dual":
                continue
            # Both receivers remain connected through the installed tees. Keep
            # input coupling/termination unless an explicit setting is supplied.
            hf.setdefault("signal_inputs", {}).setdefault(role, {}).update(index=index, range_v=voltage)
        hf["demodulators"] = []
        for index, rate, tc, order, adc in ((0, self.settings.sample_rate_hz, self.settings.hf2_filter_tc_s, self.settings.hf2_filter_order, 0),
                (3, self.settings.reference_rate_hz, self.settings.reference_filter_tc_s, self.settings.reference_filter_order, 1),
                (2, self.settings.timing_rate_hz, self.settings.hf2_filter_tc_s, self.settings.hf2_filter_order, 0)):
            if index == 3 and self.settings.mode != "dual":
                continue
            hf["demodulators"].append({"index": index, "enable": True, "adcselect": adc, "oscselect": 0,
                "harmonic": 1, "rate_sps": rate, "timeconstant_s": tc, "order": order, "trigger": 0})
        # DIO0 is the installed lock-in reference. Preserve the live PLL order;
        # its center follows this operation's selected clock rather than a recipe.
        hf.setdefault("pll", {}).update(index=0, enable=True, adcselect=4, harmonic=1,
                                        freqcenter_hz=self.recipe["frame_input_frequency_hz"])
        self.recipe["detector_matching"] = {
            "time_tolerance_s": field(self.settings, "detector_matching_time_tolerance_s", 0.) or 0.,
            "wavenumber_tolerance_cm1": field(self.settings, "wavenumber_matching_tolerance_cm1", 0.) or 0.}

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
        requested_devices = ["hf2li", "t660_1", "t660_2", "mircat"]
        if (self.recipe.get("capture_optical_diagnostic") and self.recipe.get("picoscope_capture_settings")
                and "picoscope" in self.context.devices.available(hardware=self.operation.hardware)):
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
            try:
                self.devices["sample_temperature"] = self.context.devices.create("sample_temperature", self.operation)
            except Exception as exc:
                self.store.append_event("optional_temperature_unavailable", {"error": str(exc)})
        self.hf, self.clock, self.timing, self.qcl = (
            self.devices[name] for name in ("hf2li", "t660_1", "t660_2", "mircat"))
        self.pico = self.devices.get("picoscope")
        self._preserve()
        self.idle()
        from .planner import compile_plan
        capabilities = self._live_capabilities()
        requested = field(self.plan, "requested_settings", None) or self.settings
        self.plan = compile_plan(requested, capabilities)
        self.plan.require_valid()
        self.settings = self.plan.settings
        self._build_recipe()
        hf = self.recipe.get("hf2li", {})
        demods = deepcopy(hf.get("demodulators", []))
        self.sample_demod, self.reference_demod, self.timing_demod = 0, (3 if self.operation.instance_id.endswith(":dual") else None), 2
        expected = {0, 2} | ({3} if self.reference_demod is not None else set())
        if {int(d["index"]) for d in demods if d.get("enable")} != expected:
            raise ReadinessError("Installed roles require demod 0 sample, demod 2 DIO, and demod 3 reference in dual mode")
        if sum(float(d["rate_sps"]) for d in demods if d.get("enable")) > float(hf.get("aggregate_limit_sps", 0)):
            raise ReadinessError("Selected aggregate HF2LI throughput exceeds connected device capacity")
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
            raise ReadinessError("T660-1 probe/reference/frame table must start inhibited with unwired D disabled")
        self.clock.apply_recipe(probe)
        pulse = self.recipe["qcl_pulse_parameters"]
        self._validate_probe_parameters(pulse, external_rate_hz=self.recipe["frame_input_frequency_hz"])
        applied = self.qcl.set_qcl_pulse_params(**pulse)
        self.qcl_readbacks = {"qcl": pulse["qcl"], "pulse_rate_hz": applied["pulse_rate_hz"],
            "pulse_width_ns": applied["pulse_width_ns"], "current_ma": self.qcl.get_qcl_current(pulse["qcl"])}
        self.store.append_event("qcl_pulse_readback", {"requested": pulse, "actual": self.qcl_readbacks})
        self._validate_probe_parameters(self.qcl_readbacks, external_rate_hz=self.recipe["frame_input_frequency_hz"])
        for key in ("pulse_rate_hz", "pulse_width_ns", "current_ma"):
            if pulse[key] is not None and not math.isclose(float(self.qcl_readbacks[key]), float(pulse[key]), rel_tol=1e-6, abs_tol=1e-5):
                raise ReadinessError(f"MIRcat {key} readback differs from the selected setting")
        self.qcl.arm()
        self.store.append_event("native_subscription_policy", {
            "policy": "bounded acquisition blocks and native-clock observation pages",
            "unobserved_intervals": "instrument programming, tuning, and intervals between clock observations",
            "native_clock_reset": False})
        self.temperature()
        return {"hf2li": self.hf.export_settings_snapshot(preset=self._hf_preset),
                "probe_recipe": probe, "clockbase_hz": self.clockbase, "qcl_pulse_parameters": self.qcl_readbacks,
                "actual_settings": self.settings.to_dict(), "capabilities": capabilities.to_dict(),
                "optical_arrival_observed": False, "time_reference": "electrical_trigger"}

    def _live_capabilities(self):
        """Resolve actual installed values within the host ownership scope."""
        from .settings import Capabilities
        method = self.hf.discover_dual_phase_scan_capabilities if self.settings.mode == "dual" else self.hf.discover_phase_scan_capabilities
        try:
            observed = self._call(method, timeout_s=180)
        except Exception as exc:
            # This host error distinguishes an unsuccessful read/probe from a
            # failed restoration of settings changed during capability discovery.
            # Closing that session cannot make the latter state verified again.
            if "HF2LI capability discovery restoration failed:" in str(exc):
                self._capture_cleanup_errors.append(str(exc))
            raise
        sample, reference = observed.get("sample", observed), observed.get("reference", {})
        values = {}
        nodes = self.original.get("hf2li", {}).get("nodes", {})
        for name, index, suffix in (("sample_rate_hz", 0, "rate"), ("reference_rate_hz", 3, "rate"),
                ("timing_rate_hz", 2, "rate"), ("hf2_filter_order", 0, "order"), ("hf2_filter_tc_s", 0, "timeconstant"),
                ("reference_filter_order", 3, "order"), ("reference_filter_tc_s", 3, "timeconstant")):
            record = nodes.get(f"/{self.hf.device_id}/demods/{index}/{suffix}", {})
            if record.get("value") is not None:
                values[name] = record["value"]
        for name, index in (("sample_input_range_v", 0), ("reference_input_range_v", 1)):
            record = nodes.get(f"/{self.hf.device_id}/sigins/{index}/range", {})
            if record.get("value") is not None:
                values[name] = record["value"]
        interval = self.qcl.get_qcl_tuning_range(1)
        ranges = [{"qcl": 1, "minimum_cm1": interval["min_cm1"], "maximum_cm1": interval["max_cm1"]}]
        frequency = self.original["t660_1"]["readback"]["queries"]["synth_frequency"]
        if not frequency.get("ok"):
            raise ReadinessError("Cannot read the external T660 probe repetition rate")
        text = str(frequency["response"]).strip().lower()
        scale = 1.
        for suffix, factor in (("mhz", 1e6), ("khz", 1e3), ("hz", 1.)):
            if text.endswith(suffix):
                text, scale = text[:-len(suffix)], factor
                break
        external_rate = float(text) * scale
        if not math.isfinite(external_rate) or external_rate <= 0:
            raise ReadinessError("External T660 probe repetition readback must be finite and positive")
        values.update(qcl=1, probe_current_ma=self.qcl.get_qcl_current(1), probe_rate_hz=external_rate,
            probe_pulse_width_s=self.qcl.get_qcl_pulse_width(1) / 1e9,
            mircat_internal_pulse_rate_hz=self.qcl.get_qcl_pulse_rate(1))
        limits = self.original["mircat"]["pulse_limits"]
        current_min, current_max = self.original["mircat"]["current_limits_ma"]
        raw = {"sample_rates_hz": tuple(sample["rates_sps"]), "reference_rates_hz": tuple(reference.get("rates_sps", ())),
            "timing_rates_hz": (float(observed["timing_rate_sps"]),), "detector_rates_verified": bool(observed["verified"]),
            "frame_capacity": int(self.timing.verified_frame_capacity()), "frame_feature_verified": True,
            "device_ids": {"hf2li": self.hf.device_id, "t660_2": self.timing.identify()},
            "actual_values": {"hf2li": observed, "operating_values": values}, "operating_values": values,
            "qcl_ranges": tuple(ranges), "mircat_internal_rate_max_hz": limits["max_pulse_rate_hz"],
            "mircat_internal_width_max_s": limits["max_pulse_width_ns"] / 1e9,
            "probe_current_min_ma": current_min, "probe_current_max_ma": current_max,
            "probe_duty_max": min(.30, limits["max_duty_cycle"] / 100.),
            "sample_filter_orders": tuple(sample.get("orders", ())),
            "reference_filter_orders": tuple(reference.get("orders", ())),
            "sample_timeconstants_by_order": sample.get("timeconstants_by_order", {}),
            "reference_timeconstants_by_order": reference.get("timeconstants_by_order", {})}
        return Capabilities.from_dict({k: v for k, v in raw.items() if k in Capabilities.__dataclass_fields__})

    def inspect_capabilities(self):
        self.check()
        self._inspection_only = True
        for name, method in (("hf2li", "connect"), ("t660_1", "connect"), ("t660_2", "connect"), ("mircat", "initialize")):
            unit = self.context.devices.create(name, self.operation)
            self.devices[name] = unit
            self._call(getattr(unit, method))
        self.hf, self.clock, self.timing, self.qcl = (self.devices[name] for name in ("hf2li", "t660_1", "t660_2", "mircat"))
        self._preserve()
        capabilities = self._live_capabilities()
        return {"capabilities": capabilities.to_dict(), "readbacks": capabilities.actual_values}

    def _preserve(self):
        from control_app.devices.hf2li_service import HF2LIPreset
        # Include ALL demods because configuration disables inactive streams.
        self._hf_preset = HF2LIPreset("single-pump-preservation", {"demodulators": [{"index": i} for i in range(6)]})
        self.original["hf2li"] = self.hf.export_settings_snapshot(preset=self._hf_preset)
        if self.original["hf2li"].get("read_errors"):
            raise ReadinessError("Cannot preserve complete HF2LI original readbacks")
        self.original["mircat"] = {"trigger": self.qcl.get_wavelength_trigger_params(),
            "marker_width_us": self.qcl.get_wavelength_trigger_pulse_width_us(),
            "qcls": [{"qcl": 1, "pulse_rate_hz": self.qcl.get_qcl_pulse_rate(1),
                      "pulse_width_ns": self.qcl.get_qcl_pulse_width(1), "current_ma": self.qcl.get_qcl_current(1)}],
            "pulse_limits": self.qcl.get_qcl_pulse_limits(1),
            "current_limits_ma": self.qcl.get_qcl_current_limits(1)}
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

    def _validate_probe_parameters(self, pulse, *, external_rate_hz=None):
        """Validate QCL1's internal pulse and independent external triggering."""
        from .timing import duty_exceeds
        if pulse.get("qcl") != 1:
            raise ReadinessError("Only installed QCL 1 may receive pulse settings")
        rate, width = float(pulse["pulse_rate_hz"]), float(pulse["pulse_width_ns"])
        limits = self.original["mircat"]["pulse_limits"]
        for value, maximum, label in ((rate, limits["max_pulse_rate_hz"], "internal pulse rate"),
                (width, limits["max_pulse_width_ns"], "pulse width")):
            if not math.isfinite(value) or value <= 0 or not math.isfinite(maximum) or maximum <= 0 or value > maximum:
                raise ReadinessError(f"MIRcat {label} is outside the QCL1 vendor limit")
        vendor_duty = float(limits["max_duty_cycle"]) / 100.
        if not math.isfinite(vendor_duty) or vendor_duty <= 0:
            raise ReadinessError("MIRcat QCL1 duty limit is invalid")
        ceiling = min(.30, vendor_duty)
        if duty_exceeds(rate, width / 1e9, ceiling):
            raise ReadinessError("MIRcat internal pulse duty exceeds the QCL1 vendor/30% limit")
        if external_rate_hz is not None:
            external = float(external_rate_hz)
            if not math.isfinite(external) or external <= 0 or external >= rate:
                raise ReadinessError("MIRcat internal pulse rate must exceed the external repetition rate")
            if duty_exceeds(external, width / 1e9, ceiling):
                raise ReadinessError("External repetition rate times pulse width exceeds the vendor/30% limit")
        current = pulse.get("current_ma")
        if current is not None:
            low, high = self.original["mircat"]["current_limits_ma"]
            if not all(math.isfinite(float(v)) for v in (current, low, high)) or not low <= float(current) <= high:
                raise ReadinessError("MIRcat current is outside the QCL1 vendor limits")

    def temperature(self):
        """Optional observation only; absent/stale temperature does not gate data."""
        thermometer = self.devices.get("sample_temperature")
        try:
            record = data(thermometer.read_temperature()) if thermometer else deepcopy(self.recipe.get("sample_temperature_observation", {}))
        except Exception as exc:
            record = {"observation_error": str(exc)}
        if record:
            import json
            from .persistence import json_value
            try:
                record = json_value(record)
                json.dumps(record, allow_nan=False)
            except (ValueError, TypeError):
                record = {"observation_error": "Optional temperature observation was not finite serializable metadata"}
            self.store.append_event("temperature", record)
        return record or None

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
        self.qcl.tune_to_wavenumber(start, qcl=1)
        self._wait(self.qcl.is_tuned, 45, "MIRcat tuning")
        trigger = self.qcl.set_external_sweep_trigger_params(start_cm1=start, stop_cm1=stop,
            wavelength_trigger_interval_cm1=float(trajectory["marker_interval_cm1"]), external_process_trigger=True)
        self.store.append_event("mircat_trigger_mode", {"block_id": field(block, "block_id"), "actual": trigger})
        from control_app.devices.mircat_service import PULSE_MODE_EXTERNAL_TRIGGER, PROC_TRIG_MODE_EXTERNAL
        if trigger.get("pulse_mode") != PULSE_MODE_EXTERNAL_TRIGGER or trigger.get("process_trigger_mode") != PROC_TRIG_MODE_EXTERNAL:
            raise ReadinessError("MIRcat did not accept external pulse and external process triggering")
        self.qcl.set_wavelength_trigger_pulse_width_us(int(trajectory["marker_width_us"]))
        # This explicit Blank/Sample/Start operation authorizes emission. The
        # installed service still enforces the actual key/interlock/TEC state.
        self.qcl.start_emission()
        self.qcl.cancel_manual_tune()
        expected = {"start_cm1": start, "stop_cm1": stop, "scan_rate_cm1_s": float(trajectory["scan_speed_cm1_s"]),
                    "qcl": 1, "repetitions": int(field(block, "scan_count"))}
        self._call(lambda: self.qcl.start_sweep_scan(**expected))
        actual = self.qcl.get_sweep_parameters()
        for key in ("start_cm1", "stop_cm1", "scan_rate_cm1_s", "repetitions"):
            if not math.isclose(float(actual[key]), float(expected[key]), rel_tol=1e-6, abs_tol=1e-5):
                raise ReadinessError(f"MIRcat rejected selected {key}")
        identity = self.qcl.get_wavelength_trigger_channel_params(1)
        direction = 1 if identity["stop"] >= identity["start"] else -1
        self.marker_targets = identity["start"] + direction * abs(identity["interval"]) * np.arange(int(identity["num_triggers"]))
        if (identity.get("channel") != 1 or not len(self.marker_targets)
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
        self._read_health()

    def _read_health(self):
        health = self.hf.read_acquisition_health(reference_pll=0,
            input_indices=(0, 1) if self.settings.mode == "dual" else (0,))
        self.store.append_event("hf2li_health", health)
        self._health[:] = [health]
        if health.get("overload") is True:
            raise ReadinessError("HF2LI reports detector ADC overload; native records retained")
        if health.get("reference_locked") is False or health.get("clock_locked") is False:
            raise ReadinessError("HF2LI reports an unlocked reference or clock; native records retained")
        return health

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

    def _start_native_subscription(self):
        roles = {self.sample_demod, self.timing_demod}
        if self.reference_demod is not None:
            roles.add(self.reference_demod)
        self.hf.start_acquisition(demodulators=sorted(roles), fields=("x", "y", "dio"))

    def _finish_probe_interval(self, block):
        if self._probe_enabled_at is None:
            return None
        self.clock.disable_channel("B")
        elapsed = monotonic() - self._probe_enabled_at
        self._probe_enabled_at = None
        duty = float(self.settings.probe_rate_hz) * float(self.settings.probe_pulse_width_s)
        exposure = {"block_id": field(block, "block_id"), "enabled_command_interval_s": elapsed,
            "pulse_on_upper_bound_s": elapsed * duty, "pulse_duty_fraction": duty,
            "basis": "host monotonic before probe enable command through acknowledged disable"}
        self.store.append_event("probe_enabled_interval", exposure)
        self.observed_probe_pulse_on_s += exposure["pulse_on_upper_bound_s"]
        return exposure

    def capture_block(self, block, *, pump_allowed=False, before_fire=None):
        self.check()
        self._start_native_subscription()
        try:
            return self._capture_block(block, pump_allowed=pump_allowed, before_fire=before_fire)
        finally:
            # Stop immediately also on cancellation/SDK failure. Generic restore
            # repeats physical inhibit and retains any failed cleanup action.
            for label, callback in (("probe interval", lambda: self._finish_probe_interval(block)),
                                    ("native unsubscribe", self.hf.stop_acquisition)):
                try:
                    callback()
                except Exception as exc:
                    self._capture_cleanup_errors.append(f"{label}: {exc}")

    def _capture_block(self, block, *, pump_allowed=False, before_fire=None):
        self.check()
        self._polls = []
        self._poll()  # explicit pretrigger native support
        started, start_error = False, None
        def start():
            nonlocal started, start_error
            self.check()
            if started:
                raise ReadinessError("The finite table has already been started; no automatic pump repeat")
            started = True
            try:
                if before_fire:
                    before_fire()  # durable pump intent BEFORE enabling its hardware table
                self.timing.start_frame_table()
                self._probe_enabled_at = monotonic()
                self.clock.enable_channel("B")
                self.clock.enable_channel("C")
            except BaseException as exc:
                start_error = exc
                raise
        diagnostic = None
        if pump_allowed and self.pico is not None:
            try:
                diagnostic = self.pico.capture_block_data(after_arm=start, while_waiting=self._poll,
                                                          before_transfer=self.check)
            except AcquisitionStopped:
                raise
            except Exception as exc:
                if start_error is not None:
                    raise start_error
                self.store.append_event("optional_diagnostic_error", {"device": "picoscope", "error": str(exc)})
                if not started:
                    start()
            if diagnostic is not None:
                self.store.save_chunk(f"pico-{field(block, 'block_id')}", flatten_native(diagnostic))
        else:
            start()
        deadline = monotonic() + float(field(block, "duration_s")) + float(self.recipe.get("block_timeout_margin_s", 10))
        last_thermal = monotonic()
        while True:
            self._poll()
            if monotonic() - last_thermal >= .5:
                self.progress(stage="acquisition", message="Native HF2LI spectral and DIO capture", temperature=self.temperature())
                self._read_health()
                last_thermal = monotonic()
            status = self.timing.get_frames_status()
            if status == "DONE":
                break
            if status == "ERROR":
                raise ReadinessError("T660 finite table reported ERROR")
            if monotonic() > deadline:
                raise TimeoutError("Native finite table did not complete before its declared bound")
        self._poll()
        # Disable the probe before slow timing readbacks/restoration commands.
        # The command interval is a conservative enabled-duration bound, not a
        # measured optical dose or a new source of pump timing precision.
        exposure = self._finish_probe_interval(block)
        self.hf.stop_acquisition()
        self._read_health()
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
            scan_direction_high_increasing=self.recipe.get("scan_direction_high_increasing", True),
            pump_active_high=self.recipe["pump_sync_active_high"])
        result["clipped"] = np.abs(result["sample"]) >= float(self.settings.sample_input_range_v)
        if self.reference_demod is not None:
            result["reference_clipped"] = np.abs(result["reference"]) >= float(self.settings.reference_input_range_v)
        observed_count = len(result["native_pump_sync_ticks"])
        if observed_count != (1 if pump_allowed else 0):
            raise ReadinessError(f"Observed electrical pump count {observed_count}; expected {int(pump_allowed)}; no retry")
        epoch = None
        if pump_allowed:
            tick = int(result["native_pump_sync_ticks"][0])
            epoch = {"pump_time_s": tick / self.clockbase, "pump_timestamp_ticks": tick,
                "clock_domain": "HF2LI_native_clock", "clockbase_hz": self.clockbase, "device_id": self.hf.device_id,
                "electrical_sync_tick": tick, "electrically_observed": True, "independently_observed": False,
                "electrical_trigger_edge": "rising" if self.recipe["pump_sync_active_high"] else "falling",
                "electrical_sync_source": "Surelite Variable Sync OUT on HF2LI DIO17",
                "electrical_sync_polarity_source": self.recipe["pump_sync_polarity_source"],
                "optical_arrival_observed": False, "time_reference": "electrical_trigger",
                "optical_resolution": "unresolved", "sample_state": self.state_evidence()}
            if diagnostic is not None:
                try:
                    epoch = self._optical_epoch(diagnostic, result)
                except (KeyError, ValueError) as exc:
                    self.store.append_event("optical_timing_unresolved", {"reason": str(exc)})
        result["time_reference"] = np.asarray((epoch or {}).get("time_reference", "electrical_trigger"))
        return {"native": result, "epoch": epoch, "observed_scan_count": len(result["native_sweep_start_ticks"]),
                "observed_pump_count": observed_count, "end_native_time_s": self.last_native_time,
                "probe_pulse_on_upper_bound_s": exposure["pulse_on_upper_bound_s"]}

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
                "sample_state": self.state_evidence(), "independently_observed": True, "electrically_observed": True,
                "optical_arrival_observed": True, "time_reference": "optical_arrival"}

    def native_now(self):
        self._polls = []
        self._start_native_subscription()
        try:
            self._poll()
        finally:
            self._polls = []
            self.hf.stop_acquisition()
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
        epoch = continuation["epoch"]
        if epoch.get("device_id") != self.hf.device_id or int(epoch.get("clockbase_hz", 0)) != self.clockbase:
            raise ReadinessError("Retained pump clock differs from the connected recorder; continuation cannot reset time zero")
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
        errors, records = list(self._capture_cleanup_errors), {}
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
        if self._inspection_only:
            # Discovery restores its own temporary HF2 settings. Merely checking
            # connected devices must not inhibit timing or change laser state.
            for name, unit in self.devices.items():
                closer = "deinitialize" if name == "mircat" else "close"
                attempt(name + "-close", getattr(unit, closer))
            return {"safe_verified": not errors, "errors": errors, "records": records,
                    "restoration_target": "capability session closure; timing and laser operating state preserved"}
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
            original_pulse = next((item for item in original["qcls"] if item.get("qcl") == 1), None)
            def restore_pulse():
                if original_pulse is None:
                    raise RuntimeError("Original installed QCL1 pulse settings are unavailable")
                self._validate_probe_parameters(original_pulse)
                return qcl.set_qcl_pulse_params(**{**original_pulse, "qcl": 1})
            attempt("qcl-1-settings", restore_pulse)
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
                if original_pulse is None:
                    raise RuntimeError("Original installed QCL1 pulse settings are unavailable")
                actual_pulse = {"qcl": 1}
                for key, getter in (("pulse_rate_hz", qcl.get_qcl_pulse_rate), ("pulse_width_ns", qcl.get_qcl_pulse_width),
                                    ("current_ma", qcl.get_qcl_current)):
                    actual_pulse[key] = getter(1)
                records["qcl-1-restored-pulse"] = actual_pulse
                self._validate_probe_parameters(actual_pulse)
                for key in ("pulse_rate_hz", "pulse_width_ns", "current_ma"):
                    if not math.isclose(float(actual_pulse[key]), float(original_pulse[key]), rel_tol=1e-6, abs_tol=1e-5):
                        raise RuntimeError(f"QCL 1 original {key} did not restore")
                return {"trigger": actual, "marker_width_us": original["marker_width_us"]}
            attempt("qcl-settings-verification", verify_qcl_settings)
        for name in ("t660_1", "t660_2"):
            if name in self.devices:
                if name in self.original:
                    def restore_timing(u=self.devices[name], saved=self.original[name], device_name=name):
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
                        actual_references = {}
                        for edge in range(1, 9):
                            try:
                                actual_references[str(edge)] = int(u.command(f"TIME:RELTo{edge}?"))
                            except Exception as exc:
                                actual_references[str(edge)] = {"error": str(exc)}
                        records[device_name + "-restored-references"] = {
                            "expected": saved["references"], "actual": actual_references}
                        after["references"] = actual_references
                        if actual_references != saved["references"]:
                            raise RuntimeError("Timing edge references did not restore")
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
                # Broad read_state() also reads pulse settings of the SDK's
                # reported active QCL. Use only these unindexed state getters;
                # all operation pulse-parameter reads remain explicitly QCL1.
                actual = {}
                for label, getter in (("scan", qcl.get_scan_status), ("emission_on", qcl.is_emission_on),
                        ("armed", qcl.is_laser_armed), ("scan_waiting_process_trigger", qcl.get_scan_waiting_process_trigger)):
                    try:
                        observed = data(getter())
                        if label == "scan":
                            actual.update(observed)
                        else:
                            actual[label] = observed
                    except Exception as exc:
                        actual.setdefault("read_errors", {})[label] = str(exc)
                records["mircat-final-state"] = actual
                required_off = ("emission_on", "armed", "scan_in_progress", "scan_active",
                                "scan_paused", "scan_waiting_process_trigger")
                failed = [key for key in required_off if field(actual, key) is not False]
                if failed:
                    raise RuntimeError("MIRcat safe-off readback failed: " + ", ".join(failed))
                return actual
            attempt("mircat-safe-verification", verify_qcl)
        if any(thread.is_alive() for thread in self.pending):
            errors.append("Instrument SDK programming still in progress; physical state unverified")
        for name, unit in self.devices.items():
            closer = {"hf2li": "close", "t660_1": "close", "t660_2": "close", "mircat": "deinitialize", "picoscope": "close_unit"}.get(name)
            if closer:
                attempt(name + "-close", getattr(unit, closer))
        return {"safe_verified": not errors, "errors": errors, "records": records,
                "restoration_target": "original detector/QCL settings and inhibited timing outputs; never repeat a pump"}
