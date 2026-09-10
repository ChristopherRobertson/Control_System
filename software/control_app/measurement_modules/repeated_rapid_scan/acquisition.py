"""Owned installed-device acquisition of finite, uninterrupted recovery movies.

No Phase Scan scientific engine is imported.  HF2LI's native poll subscriptions
remain active for the whole declared movie, including flyback and pump crossing.
Polls only drain native buffers: the acknowledged T660 table defines every edge.
The normal path records directly from installed configuration and native readbacks.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
import math
import re
from time import monotonic
from typing import Any, Mapping

import numpy as np


def plain(value):
    if is_dataclass(value):
        return {k: plain(v) for k, v in asdict(value).items()}
    if isinstance(value, Mapping):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value


def get(value, name, default=None):
    return value.get(name, default) if isinstance(value, Mapping) else getattr(value, name, default)


def notify(worker, message, completed=None, total=None):
    """A failed UI callback cannot interrupt safety or preservation."""
    try:
        worker.message.emit(str(message))
        if completed is not None:
            worker.progress.emit(int(completed), int(total))
    except Exception:
        pass


def available_memory_bytes():
    """Read available host memory; unknown stays unknown."""
    try:
        import psutil
        return int(psutil.virtual_memory().available)
    except (ImportError, OSError):
        try:
            import ctypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                    *[(name, ctypes.c_ulonglong) for name in ("total_phys", "available_phys", "total_page", "available_page", "total_virtual", "available_virtual", "available_extended")]]
            value = MemoryStatus()
            value.length = ctypes.sizeof(value)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
                return int(value.available_phys)
        except (AttributeError, OSError):
            pass
    return None


def seconds(text):
    match = re.fullmatch(r"\s*([-+\d.eE]+)\s*(ns|us|ms|s)?\s*", str(text))
    if not match:
        raise ValueError(f"Invalid T660 time readback {text!r}")
    return float(match[1]) * {None: 1., "s": 1., "ms": 1e-3, "us": 1e-6, "ns": 1e-9}[match[2]]


def rising_edges(ticks, values, bit):
    high = (np.asarray(values, dtype=np.uint32) & (1 << int(bit))) != 0
    # A stream beginning high is an incomplete edge, never a fabricated rise.
    return np.asarray(ticks)[np.flatnonzero(np.diff(high.astype(np.int8)) == 1) + 1]


def native_demod(chunks, index):
    """Collect original native values in arrival order; never repair duplicates/gaps."""
    fields = {}
    suffix = f"/demods/{int(index)}/sample"
    for chunk in chunks:
        for path, payload in chunk.get("data", {}).items():
            if not str(path).lower().endswith(suffix):
                continue
            items = payload if isinstance(payload, (list, tuple)) else (payload,)
            for item in items:
                for key, value in item.items():
                    if key in ("timestamp", "x", "y", "dio", "r", "flags", "frequency", "auxin0", "auxin1"):
                        fields.setdefault(key, []).append(np.asarray(value).reshape(-1))
    return {key: np.concatenate(values) for key, values in fields.items()}


def decode_native_movie(chunks, movie_plan, settings, readbacks, *, status="complete"):
    """Identify each scan by observed sweep intervals and calibrated markers.

    The controller identifies marker wavenumbers.  No requested scan period or
    phase offset participates in sample time/wavelength reconstruction.
    """
    from .data import NativeMovie, NativeScan, NativeStream, PumpObservation, ScanTrajectory, ClockCorrection
    roles = readbacks["roles"]
    clockbase = int(readbacks["clockbase_hz"])
    timing = native_demod(chunks, roles["timing_demodulator"])
    if "timestamp" not in timing or "dio" not in timing:
        raise ValueError("HF2LI timing stream is absent; native chunks retained")
    ticks, dio = timing["timestamp"], timing["dio"]
    bits = readbacks["marker_bits"]
    origin = int(ticks[0])
    high = (dio.astype(np.uint32) & (1 << bits["sweep_active"])) != 0
    starts = np.flatnonzero(np.diff(high.astype(np.int8)) == 1) + 1
    ends = np.flatnonzero(np.diff(high.astype(np.int8)) == -1) + 1
    markers = rising_edges(ticks, dio, bits["wavelength_trigger"])
    expected_axis = np.asarray(readbacks["marker_wavenumbers_cm1"], dtype=float)
    all_sample = native_demod(chunks, roles["sample_demodulator"])
    all_reference = native_demod(chunks, roles["reference_demodulator"]) if get(settings, "mode") == "dual" else None
    scans = []
    quality = readbacks.get("quality_observations", [])
    direction_levels = readbacks.get("direction_levels", {})
    detector_corrections = readbacks.get("detector_clock_corrections", ())
    stream_clock_ids = {role: readbacks.get(role+"_clock_id", "hf2li") for role in ("sample", "reference")}
    if isinstance(detector_corrections, Mapping):
        corrected = []
        for role, values in detector_corrections.items():
            if role not in stream_clock_ids:
                raise ValueError(f"Unknown detector clock correction role {role!r}")
            stream_clock_ids[role] = "hf2li_"+role
            corrected.append({"clock_id": stream_clock_ids[role], **values})
        detector_corrections = corrected

    def stream(data, begin, end, role):
        if not data or "timestamp" not in data:
            raise ValueError("A required native detector stream is missing")
        selected = (data["timestamp"] >= begin) & (data["timestamp"] <= end)
        values = data.get("r")
        if values is None:
            values = np.hypot(data["x"], data["y"])
        # Unknown quality is recorded as unknown; known bad quality excludes the
        # observation without removing a single sample from its native record.
        flags = {}
        if "flags" in data:
            flags["device_flag"] = data["flags"][selected] != 0
        if any(item.get("locked") is False for item in quality):
            flags["unlocked"] = np.ones(int(np.count_nonzero(selected)), dtype=bool)
        if any(item.get("overload", False) for item in quality):
            flags["clipped"] = np.ones(int(np.count_nonzero(selected)), dtype=bool)
        if any(item.get("clock_locked") is False for item in quality):
            flags["clock_unlocked"] = np.ones(int(np.count_nonzero(selected)), dtype=bool)
        return NativeStream(data["timestamp"][selected], values[selected], flags=flags,
                            clock_id=stream_clock_ids[role], timestamp_unit_s=1 / clockbase,
                            timestamp_origin=origin,
                            metadata={"raw_fields": {k: v[selected] for k, v in data.items()
                                                     if len(v) == len(selected)},
                                      "quality_observation_basis": "poll-boundary readbacks"})

    for begin_index in starts:
        candidate_ends = ends[ends > begin_index]
        if not len(candidate_ends):
            continue  # Incomplete sweep remains intact in raw movie chunks.
        start, stop = ticks[begin_index], ticks[candidate_ends[0]]
        scan_markers = markers[(markers >= start) & (markers < stop)]
        if len(scan_markers) < 2:
            continue  # Ancillary Tuned / pump pickup highs are not scans.
        if len(scan_markers) != len(expected_axis):
            raise ValueError(f"Observed wavelength marker count {len(scan_markers)} != calibrated count {len(expected_axis)}; raw movie retained")
        trajectory_time = (scan_markers - np.asarray(origin, dtype=scan_markers.dtype)).astype(float) / clockbase
        declared_direction = get(movie_plan, "direction", "forward")
        level = int(bool(int(dio[begin_index]) & (1 << bits["scan_direction"])))
        observed_direction = next((name for name, value in direction_levels.items() if int(value) == level), declared_direction)
        direction_flags = ("direction_mismatch",) if observed_direction != declared_direction else ()
        trajectory = ScanTrajectory(trajectory_time, expected_axis.copy(),
                                    calibration_id=readbacks["trajectory_calibration_id"],
                                    direction=observed_direction, clock_id="hf2li")
        scans.append(NativeScan(len(scans), stream(all_sample, start, stop, "sample"), trajectory,
                                reference=None if all_reference is None else stream(all_reference, start, stop, "reference"),
                                flags=direction_flags,
                                metadata={"sweep_active_ticks": np.asarray([start, stop]),
                                          "marker_ticks": scan_markers.copy(),
                                          "direction_dio": int(dio[begin_index]) & (1 << bits["scan_direction"])}))
    observed = rising_edges(ticks, dio, bits["pump_sync"])
    optical_zero = readbacks.get("optical_time_zero", {})
    optical_offset = 0.
    if optical_zero:
        if not optical_zero.get("calibration_id") or not math.isfinite(float(optical_zero.get("electrical_sync_to_optical_s", float("nan")))):
            raise ValueError("Optical time-zero correction lacks an applicable calibration identity or finite offset")
        optical_offset = float(optical_zero["electrical_sync_to_optical_s"])
    pump_observations = tuple(PumpObservation((int(tick)-origin) / clockbase + optical_offset,
                              clock_id="hf2li", basis="calibrated_optical_time_zero" if optical_zero else "electrical_sync", independently_observed=True,
                              uncertainty_s=optical_zero.get("uncertainty_s"),
                              metadata={"native_tick": int(tick), "dio_bit": bits["pump_sync"],
                                        "source": "Nd:YAG Variable Sync", "per_event_optical_observation": False,
                                        "optical_time_zero": optical_zero})
                              for tick in observed)
    correction = readbacks.get("clock_correction", {})
    clock_corrections = (ClockCorrection(clock_id="hf2li", **correction),) if correction or detector_corrections else ()
    clock_corrections += tuple(ClockCorrection(**item) for item in detector_corrections)
    condition = get(settings, "condition", {})
    scan_start_ticks = np.asarray([scan.metadata["sweep_active_ticks"][0] for scan in scans])
    observed_periods = np.asarray([int(b)-int(a) for a, b in zip(scan_start_ticks, scan_start_ticks[1:])], dtype=float)/clockbase
    return NativeMovie(get(movie_plan, "movie_id"), get(movie_plan, "selected_phase_s", 0.), tuple(scans),
                       pump_observations, get(settings, "mode", "single"), get(condition, "condition_id", "unknown"),
                       status=status, clock_corrections=clock_corrections,
                       metadata={"native_chunks": chunks, "timing_stream": timing, "readbacks": deepcopy(readbacks),
                                 "requested_phase_s": get(movie_plan, "requested_phase_s", 0.),
                                 "authorized_pump_count": get(movie_plan, "pump_count", 0),
                                 "expected_pump_count": get(movie_plan, "pump_count", 0),
                                 "control": get(movie_plan, "control", "sample"),
                                 "clockbase_hz": clockbase, "timestamp_origin": origin,
                                 "axis_basis": readbacks.get("axis_basis", "calibrated" if readbacks.get("trajectory_calibration_id") else "observed_markers_nominal_axis"),
                                 "observed_scan_start_ticks": scan_start_ticks,
                                 "observed_scan_periods_s": observed_periods,
                                 "observed_scan_period_median_s": float(np.median(observed_periods)) if len(observed_periods) else None,
                                 "observed_period_basis": "Differences of native observed sweep-start ticks; jitter and gaps retained"})


def _validate_mircat_internal_pulse(pulse, limits, current_limits, *, external_rate_hz=None):
    """Validate optical pulse duty independently of the external TTL timing."""
    from .settings import validate_mircat_pulse_pair, validate_probe_optical_pulse_pair
    rate, width, current = (float(pulse[key]) for key in ("pulse_rate_hz", "pulse_width_ns", "current_ma"))
    max_rate, max_width, vendor_duty = (float(limits[key]) for key in
        ("max_pulse_rate_hz", "max_pulse_width_ns", "max_duty_cycle"))
    if not all(math.isfinite(value) and value > 0 for value in (max_rate, max_width, vendor_duty)):
        raise ValueError("MIRcat connected pulse limits must be finite positive values")
    maximum = min(.30, vendor_duty/100.)
    if not all(math.isfinite(value) and value > 0 for value in (rate, width, current, maximum)):
        raise ValueError("MIRcat internal pulse settings/limits must be finite positive values")
    external_duty = validate_probe_optical_pulse_pair(external_rate_hz, width) if external_rate_hz is not None else None
    if external_duty is not None and external_duty > maximum:
        raise ValueError(f"MIRcat emitted optical duty cycle {external_duty:.9g} exceeds the connected device limit {maximum:.9g}")
    duty = validate_mircat_pulse_pair(rate, width)
    if duty > maximum:
        raise ValueError(f"MIRcat internal optical duty cycle {duty:.9g} exceeds {maximum:.9g}; repetition rate times pulse width must be at most 30% and any lower device limit")
    if rate > max_rate or width > max_width or not current_limits[0] <= current <= current_limits[1]:
        raise ValueError("Selected MIRcat internal pulse settings exceed its connected readback limits")
    if external_rate_hz is not None and rate <= external_rate_hz:
        raise ValueError("MIRcat internal repetition rate must exceed the separate external T660 probe trigger rate")
    return {"internal_duty_fraction": duty, "maximum_internal_duty_fraction": maximum,
            "emitted_optical_duty_fraction": external_duty, "maximum_emitted_optical_duty_fraction": maximum,
            "emitted_repetition_rate_hz": external_rate_hz,
            "basis": "Emitted cadence is the external T660 repetition rate times SDK optical pulse width; internal repetition duty is checked separately; electrical TTL width is not optical pulse width"}


class InstalledDevicesAcquirer:
    """Per-operation real services created only through the frozen host context."""

    def __init__(self, context, operation, plan):
        self.context, self.operation, self.plan = context, operation, plan
        self.settings = get(plan, "settings")
        self.devices, self.original, self.raw_movies = {}, {}, []
        self.readbacks, self.restoration = {}, {}
        self._streaming = False
        self._hf_snapshot_preset = None
        self._mutated = False
        self.config = plain(operation.configuration.get("repeated_rapid_scan", {}))
        for calibration in operation.calibration_records:
            candidate = get(calibration, "device_configuration")
            if candidate:
                self.config.update(plain(candidate))
        self.readbacks["historical_qcl_selectors"] = {
            "settings": get(self.settings, "qcl"), "device_configuration": self.config.get("qcl"),
            "pulse_configuration": self.config.get("mircat_pulse", {}).get("qcl"),
            "installed_device_configuration": operation.configuration.get("devices", {}).get("mircat", {}).get("qcl")}
        self.config["qcl"] = 1
        self.readbacks["installed_qcl"] = 1

    def _device(self, name):
        device = self.context.devices.create(name, self.operation)
        self.devices[name] = device  # Retain even when connection fails.
        return device

    def discover(self, worker):
        """Connect and retain live readbacks without configuring acquisition."""
        worker.check_cancelled()
        from control_app.devices.hf2li_service import HF2LIPreset
        self._hf_snapshot_preset = HF2LIPreset("repeated_rapid_scan_readbacks", {
            "demodulators": [{"index": index} for index in range(6)]})
        hf = self._device("hf2li"); hf.connect()
        self.original["hf2li"] = hf.export_settings_snapshot(preset=self._hf_snapshot_preset)
        nodes = self.original["hf2li"].get("nodes", {})
        sample = int(get(self.settings, "sample_demodulator", 0))
        reference = int(get(self.settings, "reference_demodulator", 3))
        timing = next(index for index in (2, 1, 4, 5, 0, 3) if index not in (sample, reference))
        roles = {"sample_demodulator": sample, "reference_demodulator": reference,
                 "timing_demodulator": timing}
        installed = plain(self.operation.configuration)
        observed = installed.get("timing_routes", {}).get("observed_timing_inputs", {})
        timing_inputs = installed.get("devices", {}).get("hf2li", {}).get("timing_inputs", {})
        bits = {"pump_sync": observed.get("ndyag_variable_sync", {}).get("hf2li_dio_bit", 17),
                "scan_direction": timing_inputs.get("scan_direction", {}).get("hf2li_dio_bit", 20),
                "sweep_active": timing_inputs.get("sweep_active", {}).get("hf2li_dio_bit", 21),
                "wavelength_trigger": timing_inputs.get("wavelength_trigger", {}).get("hf2li_dio_bit", 22)}
        self.config.setdefault("marker_bits", bits)
        self.config.setdefault("direction_levels", {})  # No unmeasured DIO polarity assumption.
        self.config.setdefault("trajectory_calibration_id", "")
        self.config.setdefault("aggregate_rate_limit_sps", 700000.)
        self.readbacks.update(hf2li=self.original["hf2li"], clockbase_hz=hf.get_clockbase(), roles=roles,
            marker_bits=self.config["marker_bits"], direction_levels=self.config["direction_levels"],
            trajectory_calibration_id=self.config["trajectory_calibration_id"],
            clock_correction=self.config.get("clock_correction", {}),
            detector_clock_corrections=self.config.get("detector_clock_corrections", {}),
            optical_time_zero=self.config.get("optical_time_zero", {}),
            axis_basis="calibrated" if self.config["trajectory_calibration_id"] else "observed_markers_nominal_axis",
            wavelength_basis="controller marker readback; additional axis calibration is optional",
            timing_basis="native electrical sync; detector/optical latency is unresolved unless supplied",
            installed_configuration=installed.get("system", {}), warnings=[])
        for name in ("t660_1", "t660_2"):
            worker.check_cancelled()
            unit = self._device(name); unit.connect()
            self.original[name] = self._snapshot_timing(unit)
        qcl = self._device("mircat"); qcl.initialize()
        # This installation has exactly one QCL. Historical selectors remain
        # provenance and never route a current SDK call to another channel.
        qcl_id = 1
        self.readbacks["reported_qcl_count"] = qcl.get_num_installed_qcls()
        self.readbacks["qcl_ranges"] = [qcl.get_qcl_tuning_range(1)]
        self.original["mircat"] = {"trigger": qcl.get_wavelength_trigger_params(),
            "marker_width_us": qcl.get_wavelength_trigger_pulse_width_us(),
            "pulse": {"qcl": qcl_id, "pulse_rate_hz": qcl.get_qcl_pulse_rate(qcl_id),
                      "pulse_width_ns": qcl.get_qcl_pulse_width(qcl_id), "current_ma": qcl.get_qcl_current(qcl_id)}}
        live = {}
        for role, index, input_index in (("sample", sample, 0), ("reference", reference, 1)):
            if role == "reference" and self.settings.mode != "dual":
                continue
            for field, suffix in (("rate", "_rate_hz"), ("order", "_filter_order"), ("timeconstant", "_filter_timeconstant_s")):
                value = nodes.get(f"/{hf.device_id}/demods/{index}/{field}", {}).get("value")
                if value is not None:
                    live[role+suffix] = value
            value = nodes.get(f"/{hf.device_id}/sigins/{input_index}/range", {}).get("value")
            if value is not None:
                live[role+"_input_range_v"] = value
        for field, key in (("pulse_rate_hz", "mircat_pulse_rate_hz"), ("pulse_width_ns", "mircat_pulse_width_ns"), ("current_ma", "mircat_current_ma")):
            live[key] = self.original["mircat"]["pulse"][field]
        try:
            sweep = qcl.get_sweep_parameters()
            self.readbacks["mircat_sweep_before"] = sweep
            if float(sweep["scan_rate_cm1_s"]) > 0:
                live["scan_speed_cm1_s"] = float(sweep["scan_rate_cm1_s"])
        except Exception as exc:
            self.readbacks["warnings"].append(f"Current MIRcat sweep readback unavailable: {exc}")
        frequency = self.original["t660_1"]["readback"]["queries"]["synth_frequency"]
        if frequency.get("ok"):
            live["probe_frequency_hz"] = float(str(frequency["response"]).strip().upper().removesuffix("HZ"))
        probe_width = self.original["t660_1"]["recipe"]["channels"]["B"]["width"]
        live["probe_pulse_width_s"] = seconds(probe_width)
        self.readbacks["capabilities"] = {"frame_capacity": self.devices["t660_2"].verified_frame_capacity(),
            "max_aggregate_rate_hz": self.config["aggregate_rate_limit_sps"],
            "available_demodulators": tuple(range(6)), "connected_readback_id": self.operation.run_id,
            "actual_sample_rate_hz": live.get("sample_rate_hz"), "actual_reference_rate_hz": live.get("reference_rate_hz"),
            "acquisition_timing_rate_hz": nodes.get(f"/{hf.device_id}/demods/{timing}/rate", {}).get("value", 0.),
            "actual_scan_period_s": None, "live_settings": live,
            "available_memory_bytes": available_memory_bytes(),
            "selected_baseline_bytes": get(get(self.plan, "capabilities", {}), "selected_baseline_bytes", 0)}
        self.readbacks["health_before"] = self._quality()
        return self.readbacks

    def prepare(self, worker):
        notify(worker, "Configuration: connecting installed HF2LI, MIRcat and T660 services")
        if not self.devices:
            self.discover(worker)
        hf, qcl = self.devices["hf2li"], self.devices["mircat"]
        roles = self.readbacks["roles"]
        required = (roles["sample_demodulator"], roles["timing_demodulator"])
        if self.settings.mode == "dual":
            required += (roles["reference_demodulator"],)
        nodes = self.original["hf2li"].get("nodes", {})
        if self.original["hf2li"].get("read_errors"):
            raise RuntimeError("Cannot retain HF2LI settings before changing acquisition configuration")
        coverage = next((value for value in self.readbacks["qcl_ranges"] if value["min_cm1"] <= self.settings.scan_start_cm1 < self.settings.scan_stop_cm1 <= value["max_cm1"]), None)
        if coverage is None:
            raise ValueError("Selected uninterrupted spectral window is outside the connected QCL coverage")
        qcl_id = 1
        self._mutated = True
        for name in ("t660_2", "t660_1"):
            unit = self.devices[name]
            unit.set_trigger_source("OFF"); unit.force_eod()
            for channel in "ABCD":
                unit.disable_channel(channel)
        qcl.turn_emission_off(); qcl.stop_scan_if_needed()
        # Preserve the installed receiver impedance/coupling; only the selected
        # input range and explicit per-detector acquisition settings are applied.
        inputs, demods = {}, [{"index": index, "enable": False} for index in range(6)]
        for role, index, input_index in (("sample", roles["sample_demodulator"], 0), ("reference", roles["reference_demodulator"], 1)):
            if role == "reference" and self.settings.mode != "dual":
                continue
            inputs[role] = {"index": input_index, "range_v": get(self.settings, role+"_input_range_v")}
            demods[index] = {"index": index, "enable": True, "adcselect": input_index, "oscselect": 0,
                "harmonic": 1, "order": get(self.settings, role+"_filter_order"),
                "timeconstant_s": get(self.settings, role+"_filter_timeconstant_s"),
                "rate_sps": get(self.settings, role+"_rate_hz"), "trigger": 0}
        timing = roles["timing_demodulator"]
        demods[timing] = {"index": timing, "enable": True, "trigger": 0,
                         "rate_sps": float(self.config.get("timing_rate_hz", 230000.))}
        pll_order = nodes.get(f"/{hf.device_id}/plls/0/order", {}).get("value", 4)
        pll = {"index": 0, "enable": True, "adcselect": 4, "freqcenter_hz": self.settings.probe_frequency_hz,
               "harmonic": 1, "order": int(pll_order), "adcthreshold": 0}
        self.config["hf2li"] = {"signal_inputs": inputs, "demodulators": demods, "pll": pll, "roles": roles}
        hf.configure_demodulators([{"index": index, "enable": False} for index in range(6)])
        hf.configure_signal_inputs(inputs); hf.configure_pll(pll); hf.configure_demodulators(demods); hf.sync()
        actual = hf.export_settings_snapshot(preset=self._hf_snapshot_preset)
        if actual.get("read_errors"):
            raise RuntimeError("Configured HF2LI settings could not be read back")
        self.readbacks.update(hf2li=actual, requested_hf2li=self.config["hf2li"], required_demodulators=required)
        actual_nodes = actual["nodes"]
        total = 0.
        for index in required:
            rate = float(actual_nodes[f"/{hf.device_id}/demods/{index}/rate"]["value"])
            if not math.isfinite(rate) or rate <= 0 or not actual_nodes[f"/{hf.device_id}/demods/{index}/enable"]["value"]:
                raise RuntimeError(f"HF2LI demodulator {index} did not enable a finite positive native sample rate")
            total += rate
        if total > self.config["aggregate_rate_limit_sps"]:
            raise RuntimeError("Combined native detector/timing throughput exceeds the HF2LI readout capacity")
        self.readbacks["aggregate_rate_sps"] = total
        for role, index, input_index in (("sample", roles["sample_demodulator"], 0), ("reference", roles["reference_demodulator"], 1)):
            if role == "reference" and self.settings.mode != "dual":
                continue
            for field, suffix in (("rate", "_rate_hz"), ("order", "_filter_order"), ("timeconstant", "_filter_timeconstant_s")):
                self.readbacks["capabilities"]["live_settings"][role+suffix] = actual_nodes[f"/{hf.device_id}/demods/{index}/{field}"]["value"]
            self.readbacks["capabilities"]["live_settings"][role+"_input_range_v"] = actual_nodes[f"/{hf.device_id}/sigins/{input_index}/range"]["value"]
            self.readbacks["capabilities"]["actual_"+role+"_rate_hz"] = actual_nodes[f"/{hf.device_id}/demods/{index}/rate"]["value"]
        self.readbacks["capabilities"]["acquisition_timing_rate_hz"] = actual_nodes[f"/{hf.device_id}/demods/{timing}/rate"]["value"]
        clock_recipe = plain(get(get(get(self.plan, "movies")[0], "compiled"), "continuous_clock_recipe"))
        clock_recipe.update(trigger_source="OFF", start=False)
        for channel in "BCD":
            clock_recipe["channels"][channel]["enabled"] = False
        clock = self.devices["t660_1"]
        for edge in (1, 3, 5, 7):
            clock.command(f"TIME:RELTo{edge} 0", expect_response=False)
        clock.apply_recipe(clock_recipe)
        clock_actual = clock.read_active_settings()
        self.readbacks["clock_settings"] = clock_actual
        actual_frequency = clock_actual["queries"]["synth_frequency"]
        if not actual_frequency.get("ok"):
            raise RuntimeError("T660 clock readback unavailable after applying the acquisition recipe")
        actual_external_rate = float(str(actual_frequency["response"]).strip().upper().removesuffix("HZ"))
        self.readbacks["actual_probe_frequency_hz"] = actual_external_rate
        if not math.isclose(actual_external_rate, self.settings.probe_frequency_hz, rel_tol=1e-10):
            raise RuntimeError("T660 clock readback differs from the compiled scan clock")
        clock.start_continuous_clock()
        pulse = deepcopy(self.original["mircat"]["pulse"])
        pulse.update(self.config.get("mircat_pulse", {}))
        pulse["qcl"] = 1
        for field, setting in (("pulse_rate_hz", "mircat_pulse_rate_hz"), ("pulse_width_ns", "mircat_pulse_width_ns"), ("current_ma", "mircat_current_ma")):
            override = get(self.settings, setting)
            if override is not None:
                pulse[field] = override
        limits, current_limits = qcl.get_qcl_pulse_limits(qcl_id), qcl.get_qcl_current_limits(qcl_id)
        self.readbacks.update(mircat_pulse_limits=limits, mircat_current_limits=current_limits)
        if pulse["pulse_rate_hz"] <= actual_external_rate:
            raise ValueError("MIRcat internal repetition rate must exceed the separate external T660 probe trigger rate")
        self.readbacks["requested_mircat_internal_pulse_validation"] = _validate_mircat_internal_pulse(pulse, limits, current_limits, external_rate_hz=actual_external_rate)
        qcl.set_qcl_pulse_params(**pulse)
        self.readbacks["requested_mircat_pulse"] = pulse
        pulse = {"qcl": qcl_id, "pulse_rate_hz": qcl.get_qcl_pulse_rate(qcl_id),
                 "pulse_width_ns": qcl.get_qcl_pulse_width(qcl_id), "current_ma": qcl.get_qcl_current(qcl_id)}
        self.config["mircat_pulse"] = pulse
        self.readbacks["mircat_pulse"] = pulse
        self.readbacks["actual_mircat_internal_pulse_validation"] = _validate_mircat_internal_pulse(pulse, limits, current_limits, external_rate_hz=actual_external_rate)
        if pulse["pulse_rate_hz"] <= actual_external_rate:
            raise ValueError("Readback MIRcat internal repetition rate does not exceed the separate external T660 probe trigger rate")
        for field, setting in (("pulse_rate_hz", "mircat_pulse_rate_hz"), ("pulse_width_ns", "mircat_pulse_width_ns"), ("current_ma", "mircat_current_ma")):
            self.readbacks["capabilities"]["live_settings"][setting] = pulse[field]
        span = self.settings.scan_stop_cm1-self.settings.scan_start_cm1
        self.config.setdefault("marker_interval_cm1", span/max(1, math.ceil(span/5.)))
        timing_rate = self.readbacks["capabilities"]["acquisition_timing_rate_hz"]
        marker_spacing = self.config["marker_interval_cm1"]/self.settings.scan_speed_cm1_s
        width_us = max(1, int(math.ceil(2e6/timing_rate)))
        width_us = min(65535, max(width_us, int(min(.25*marker_spacing*1e6, 500))))
        if width_us*1e-6 >= marker_spacing:
            raise ValueError("Connected timing stream cannot resolve the selected scan's wavelength-marker spacing")
        self.config.setdefault("marker_width_us", width_us)
        if not qcl.is_interlock_set() or not qcl.is_key_switch_set():
            raise RuntimeError("MIRcat interlock/key switch is not ready")
        if not qcl.is_laser_armed():
            qcl.arm()
        self._wait(qcl.are_tecs_ready, worker, self.config.get("tec_timeout_s", 90.), "MIRcat TEC settling")
        self._wait(lambda: self._quality()["locked"] is not False, worker, self.config.get("lock_timeout_s", 30.), "HF2LI reference-lock settling")
        health = self._quality()
        self.readbacks["health_configured"] = health
        if health.get("clock_locked") is False or health.get("overload") is True:
            raise RuntimeError("HF2LI reports an actual clock/overload fault")
        worker.check_cancelled()

    def _wait(self, predicate, worker, timeout, label):
        deadline = monotonic() + timeout
        while not predicate():
            worker.check_cancelled()
            if monotonic() > deadline:
                raise TimeoutError(label)
            worker.cancel_event.wait(.025)

    @staticmethod
    def _snapshot_timing(unit):
        saved = unit.read_active_settings()
        def response(mapping, key):
            value = mapping[key]
            if not value.get("ok"):
                raise ValueError(f"Cannot retain T660 {key} before mutation")
            return str(value["response"]).strip()
        recipe = {"stop_first": True, "trigger_source": "OFF", "gate_mode": 0, "burst_enabled": False,
                  "predivider": int(response(saved["queries"], "predivider")),
                  "clock": {"frequency": response(saved["queries"], "synth_frequency")}, "channels": {}}
        for channel, item in saved["channels"].items():
            recipe["channels"][channel] = {"enabled": False, "delay": response(item, "delay_edge"),
                "width": response(item, "width_edge"), "polarity": response(item, "polarity"),
                "termination": response(item, "termination"), "timing_mode": response(item, "timing_mode")}
        references = {edge: int(unit.command(f"TIME:RELTo{edge}?")) for edge in range(1, 9)}
        relative = {2*i+j+1: seconds(recipe["channels"][ch][key])
                    for i, ch in enumerate("ABCD") for j, key in enumerate(("delay", "width"))}
        absolute = {0: 0.}
        def resolve(edge, seen=()):
            if edge in absolute:
                return absolute[edge]
            if edge in seen or references[edge] not in range(9):
                raise ValueError("T660 timing references are cyclic or invalid")
            absolute[edge] = relative[edge] + resolve(references[edge], (*seen, edge))
            return absolute[edge]
        for edge in references:
            resolve(edge)
        return {"readback": saved, "recipe": recipe, "references": references, "absolute": absolute}

    def capture(self, movie_plan, worker):
        worker.check_cancelled()
        compiled = get(movie_plan, "compiled")
        frames = plain(get(compiled, "frames"))
        count = int(get(compiled, "expected_scan_count"))
        physical_count = len(frames)
        if physical_count != count+1 or any(values["enabled"] for values in frames[-1]["channels"].values()):
            raise ValueError("Finite movie requires all scan frames followed by one explicit all-OFF terminal frame")
        if sum(bool(frame["channels"]["C"]["enabled"]) for frame in frames) != count:
            raise ValueError("Scan trigger count differs from the declared spectral scans; terminal is not a scan")
        expected_pumps = get(movie_plan, "pump_count", 0)
        if any(frame["channels"]["D"]["enabled"] for frame in frames):
            raise ValueError("Unwired T660 channel D must stay disabled")
        for channel in "AB":
            if sum(bool(frame["channels"][channel]["enabled"]) for frame in frames) != expected_pumps:
                raise ValueError("Each pumped movie requires exactly one FIRE and one Q-switch")
        raw = {"movie_id": get(movie_plan, "movie_id"),
               "chunks": [], "readbacks": {"expected_scan_count": count, "physical_frame_count": physical_count},
               "uploaded_frames": frames, "status": "partial"}
        self.raw_movies.append(raw)
        clock, frame_unit, qcl, hf = (self.devices[n] for n in ("t660_1", "t660_2", "mircat", "hf2li"))
        clock.disable_channel("C")
        notify(worker, "Timing-table upload: acknowledged pending-field updates, including terminal inhibit", 0, physical_count)
        raw["upload"] = frame_unit.preload_frame_table(frames,
            predivider=get(compiled, "predivider"), input_frequency_hz=get(compiled, "input_frequency_hz"),
            progress=lambda done, total: notify(worker, f"Timing-table upload: {done}/{total} acknowledged frames", done, total),
            cancel_check=worker.check_cancelled)
        worker.check_cancelled()
        lower = get(self.settings, "scan_start_cm1")
        upper = get(self.settings, "scan_stop_cm1")
        start, stop = (lower, upper) if get(movie_plan, "direction") == "forward" else (upper, lower)
        qcl_id = 1
        qcl.stop_scan_if_needed()
        qcl.turn_emission_off()
        qcl.tune_to_wavenumber(start, qcl=qcl_id)
        self._wait(qcl.is_tuned, worker, self.config.get("tune_timeout_s", 45.), "MIRcat tuning")
        qcl.set_external_sweep_trigger_params(start_cm1=start, stop_cm1=stop,
            wavelength_trigger_interval_cm1=self.config["marker_interval_cm1"], external_process_trigger=True)
        qcl.set_wavelength_trigger_pulse_width_us(self.config["marker_width_us"])
        # Check the actual emitted-cadence/SDK-width pair immediately before
        # opening emission, never substituting the electrical TTL high time.
        clock_readback = clock.read_active_settings()
        frequency = clock_readback["queries"]["synth_frequency"]
        if not frequency.get("ok"):
            raise RuntimeError("Actual T660 emitted repetition rate could not be read before emission")
        external_rate = float(str(frequency["response"]).strip().upper().removesuffix("HZ"))
        actual_pulse = {"qcl": 1, "pulse_rate_hz": qcl.get_qcl_pulse_rate(1),
                        "pulse_width_ns": qcl.get_qcl_pulse_width(1), "current_ma": qcl.get_qcl_current(1)}
        limits, current_limits = qcl.get_qcl_pulse_limits(1), qcl.get_qcl_current_limits(1)
        raw["readbacks"].update(pre_emission_mircat_pulse=actual_pulse, pre_emission_clock=clock_readback,
                               pre_emission_mircat_limits=limits, pre_emission_mircat_current_limits=current_limits)
        raw["readbacks"]["pre_emission_optical_pulse_validation"] = _validate_mircat_internal_pulse(
            actual_pulse, limits, current_limits, external_rate_hz=external_rate)
        configured_pulse = self.readbacks.get("mircat_pulse")
        if configured_pulse is None or any(actual_pulse[key] != configured_pulse[key]
                                          for key in ("pulse_rate_hz", "pulse_width_ns", "current_ma")):
            raise RuntimeError("MIRcat pulse readback changed from the configured acquisition before emission")
        if not math.isclose(external_rate, get(compiled, "input_frequency_hz"), rel_tol=1e-10):
            raise RuntimeError("Actual T660 repetition rate changed from the compiled finite scan timing")
        qcl.start_emission()
        qcl.cancel_manual_tune()
        expected = {"start_cm1": start, "stop_cm1": stop,
                    "scan_rate_cm1_s": get(self.settings, "scan_speed_cm1_s"), "repetitions": count}
        qcl.start_sweep_scan(**expected, qcl=qcl_id)
        actual = qcl.get_sweep_parameters()
        raw["readbacks"]["mircat_sweep"] = {"requested": expected, "actual": actual}
        for key, value in expected.items():
            if not math.isclose(float(actual[key]), float(value), rel_tol=1e-6, abs_tol=1e-5):
                raise ValueError(f"MIRcat changed requested {key}; no frame table started")
        marker = qcl.get_wavelength_trigger_channel_params(qcl_id)
        if int(marker["units"]) != 2:
            raise ValueError("MIRcat wavelength marker readback is not in cm^-1")
        axis = float(marker["start"]) + np.arange(int(marker["num_triggers"])) * abs(float(marker["interval"])) * (1 if stop > start else -1)
        if not math.isclose(float(marker["start"]), start, abs_tol=1e-4) or not math.isclose(float(marker["stop"]), stop, abs_tol=1e-4):
            raise ValueError("Controller wavelength-marker endpoints differ from the selected scan window")
        if len(axis) < 2 or not math.isclose(axis[-1], marker["stop"], abs_tol=1e-4):
            raise ValueError("MIRcat marker count/endpoints are inconsistent")
        self.readbacks["marker_wavenumbers_cm1"] = axis
        self.readbacks["quality_observations"] = []
        self._wait(qcl.get_scan_waiting_process_trigger, worker, 30., "MIRcat process-trigger readiness")
        duration = physical_count * get(compiled, "scan_period_s")
        notify(worker, f"Acquisition: finite movie, {count} scans, {expected_pumps} pump")
        hf.start_acquisition(demodulators=self.readbacks["required_demodulators"], fields=("x", "y", "dio", "frequency"))
        self._streaming = True
        started = monotonic()
        deadline = started + duration + float(self.config.get("completion_guard_s", 5.))
        try:
            # Start establishes an arbitrary clock epoch; sub-frame timing stays
            # entirely in the accepted hardware table, independently observed.
            frame_unit.start_frame_table()
            clock.enable_channel("B")
            clock.enable_channel("C")
            while True:
                worker.check_cancelled()
                chunk = hf.read_acquisition(.025)
                raw["chunks"].append(chunk)
                native_bytes = sum(np.asarray(value).nbytes for payload in chunk.get("data", {}).values()
                                   if isinstance(payload, Mapping) for value in payload.values() if isinstance(value, np.ndarray))
                raw["native_bytes"] = raw.get("native_bytes", 0) + native_bytes
                if raw["native_bytes"] > get(self.settings, "memory_limit_bytes"):
                    raise MemoryError("Full movie exceeds its native memory allocation; no circular reuse or splitting is permitted")
                quality = self._quality()
                self.readbacks["quality_observations"].append(quality)
                state = frame_unit.get_frames_status()
                if state == "ERROR":
                    raise RuntimeError("T660 finite table reported ERROR")
                if quality.get("locked") is False or quality.get("clock_locked") is False or quality.get("overload") is True:
                    raise RuntimeError("HF2LI lock loss or detector overload; native samples retained")
                if not qcl.is_interlock_set() or qcl.get_system_error_word():
                    raise RuntimeError("MIRcat interlock/system error during movie")
                if state == "DONE" and not qcl.get_scan_status()["scan_in_progress"]:
                    break
                if monotonic() > deadline:
                    raise TimeoutError("Finite movie did not complete within its planned duration and guard")
                notify(worker, f"Acquisition: {monotonic()-started:.3f} s elapsed; estimate {max(0., duration-(monotonic()-started)):.3f} s remaining (compiled movie)")
            raw["chunks"].append(hf.read_acquisition(.025))
            raw["readbacks"]["shots"] = frame_unit.get_shot_count()
            if raw["readbacks"]["shots"] != physical_count:
                raise ValueError("T660 frame count differs from the scan frames plus terminal inhibit")
            raw["status"] = "complete"
        finally:
            # Inhibit pump first, then retrieve any surviving native buffered data.
            final_errors = []
            for label, action in (("inhibit frame triggers", lambda: frame_unit.set_trigger_source("OFF")),
                                  ("inhibit scan clock", lambda: clock.disable_channel("C")),
                                  ("stop emission", qcl.turn_emission_off), ("stop sweep", qcl.stop_scan_if_needed)):
                try:
                    action()
                except Exception as exc:
                    final_errors.append(f"{label}: {exc}")
            try:
                raw["chunks"].append(hf.read_acquisition(.001))
            except Exception as exc:
                raw["retrieval_error"] = str(exc)
                final_errors.append(f"final native retrieval: {exc}")
            try:
                hf.stop_acquisition()
                self._streaming = False
            except Exception as exc:
                final_errors.append(f"unsubscribe: {exc}")
            raw["readbacks"].update(deepcopy(self.readbacks))
            if final_errors:
                raw["finalization_errors"] = final_errors
                raise RuntimeError("Movie finalization failed: " + "; ".join(final_errors))
        effective = dict(plain(movie_plan), pump_count=expected_pumps)
        movie = decode_native_movie(raw["chunks"], effective, self.settings, raw["readbacks"], status=raw["status"])
        if len(movie.pump_observations) != expected_pumps:
            raise ValueError(f"Independent pump count {len(movie.pump_observations)} != authorized {expected_pumps}; no automatic retry")
        if len(movie.scans) != count:
            raise ValueError(f"Observed complete scans {len(movie.scans)} != declared {count}; native movie retained")
        return movie

    def _quality(self):
        hf = self.devices["hf2li"]
        pll = int(self.config.get("hf2li", {}).get("pll", {}).get("index", 0))
        health = hf.read_acquisition_health(reference_pll=pll,
            input_indices=(0, 1) if self.settings.mode == "dual" else (0,))
        return {**health, "locked": health.get("reference_locked"), "observed_monotonic_s": monotonic()}

    def restore(self, worker):
        """Restore parameters with sources/outputs inhibited; never resume emission."""
        notify(worker, "Restoration: inhibiting outputs and restoring retained instrument settings")
        errors = []
        def attempt(label, call):
            try:
                return call()
            except Exception as exc:
                errors.append(f"{label}: {exc}")
                return None
        if not self._mutated:
            for name, device in reversed(tuple(self.devices.items())):
                closer = getattr(device, "deinitialize", None) if name == "mircat" else getattr(device, "close", None)
                if closer:
                    attempt(name+" close readback session", closer)
            self.restoration.update(errors=errors, safe_verified=not errors,
                disposition="Readback sessions closed; no acquisition configuration or emission command was issued",
                original=self.original)
            return self.restoration
        for name in ("t660_2", "t660_1"):
            if name not in self.devices:
                continue
            unit = self.devices[name]
            attempt(name + " inhibit", lambda u=unit: u.set_trigger_source("OFF"))
            attempt(name + " stop", lambda u=unit: u.command("STOP", expect_response=False))
            if name == "t660_2":
                attempt(name + " stop finite engine", lambda u=unit: u.command("TFRame:STOp", expect_response=False))
            attempt(name + " EOD", unit.force_eod)
            for channel in "ABCD":
                attempt(name + channel + " disable", lambda u=unit, c=channel: u.disable_channel(c))
        qcl = self.devices.get("mircat")
        if qcl:
            attempt("MIRcat emission off", qcl.turn_emission_off)
            attempt("MIRcat stop scan", qcl.stop_scan_if_needed)
            if "mircat" in self.original:
                saved = self.original["mircat"]
                def restore_pulse():
                    pulse = {**saved["pulse"], "qcl": 1}
                    _validate_mircat_internal_pulse(pulse, qcl.get_qcl_pulse_limits(1), qcl.get_qcl_current_limits(1))
                    qcl.set_qcl_pulse_params(**pulse)
                attempt("MIRcat pulse restore", restore_pulse)
                allowed = ("pulse_mode", "process_trigger_mode", "start", "stop", "interval", "units", "dwell_us", "after_off_us")
                attempt("MIRcat trigger restore", lambda: qcl.set_wavelength_trigger_params(**{k: v for k, v in saved["trigger"].items() if k in allowed}))
                attempt("MIRcat marker restore", lambda: qcl.set_wavelength_trigger_pulse_width_us(saved["marker_width_us"]))
                def verify_mircat():
                    pulse = {**saved["pulse"], "qcl": 1}
                    actual_pulse = {"qcl": 1, "pulse_rate_hz": qcl.get_qcl_pulse_rate(1),
                                    "pulse_width_ns": qcl.get_qcl_pulse_width(1), "current_ma": qcl.get_qcl_current(1)}
                    actual_trigger = qcl.get_wavelength_trigger_params()
                    actual_width = qcl.get_wavelength_trigger_pulse_width_us()
                    after = {"pulse": actual_pulse, "trigger": actual_trigger, "marker_width_us": actual_width}
                    self.restoration["mircat"] = {"before": saved, "after": after}
                    _validate_mircat_internal_pulse(actual_pulse, qcl.get_qcl_pulse_limits(1), qcl.get_qcl_current_limits(1))
                    expected_trigger = {k: v for k, v in saved["trigger"].items() if k in allowed}
                    if any(not math.isclose(float(actual_pulse[k]), float(v), rel_tol=1e-6, abs_tol=1e-6) for k, v in pulse.items()):
                        raise RuntimeError("MIRcat restored pulse settings readback mismatch")
                    if any(k not in actual_trigger or not math.isclose(float(actual_trigger[k]), float(v), rel_tol=1e-6, abs_tol=1e-6) for k, v in expected_trigger.items()):
                        raise RuntimeError("MIRcat restored trigger settings readback mismatch")
                    if actual_width != saved["marker_width_us"]:
                        raise RuntimeError("MIRcat restored marker-width readback mismatch")
                    return after
                attempt("MIRcat restoration readback verification", verify_mircat)
            attempt("MIRcat disarm", qcl.disarm)
            emission = attempt("MIRcat emission verification", qcl.is_emission_on)
            armed = attempt("MIRcat disarmed verification", qcl.is_laser_armed)
            scan = attempt("MIRcat scan inactive verification", qcl.get_scan_status)
            self.restoration["mircat_safe_readbacks"] = {"emission_on": emission, "armed": armed, "scan": scan}
            if emission is not False:
                errors.append("MIRcat safe emission-off readback was not verified")
            if armed is not False:
                errors.append("MIRcat disarmed readback was not verified")
            if scan is None or scan.get("scan_in_progress") is not False or scan.get("scan_active") is not False:
                errors.append("MIRcat scan-inactive readback was not verified")
        hf = self.devices.get("hf2li")
        if hf:
            attempt("HF2LI stop subscription", hf.stop_acquisition)
            if "hf2li" in self.original:
                before = self.original["hf2li"]
                attempt("HF2LI settings restore", lambda: hf.reload_settings_snapshot(before))
                after = attempt("HF2LI settings readback", lambda: hf.export_settings_snapshot(preset=self._hf_snapshot_preset))
                if after is not None:
                    compare = hf.compare_settings_snapshots(before, after)
                    self.restoration["hf2li"] = compare
                    if not compare["match"] or compare.get("after_read_errors"):
                        errors.append("HF2LI restored settings verification failed")
        for name in ("t660_1", "t660_2"):
            if name not in self.original:
                continue
            unit, saved = self.devices[name], self.original[name]
            def restore_timing(u=unit, s=saved):
                for channel in "ABCD":
                    u.set_channel_timing_mode(channel, "rise_fall")
                for edge in range(1, 9):
                    u.command(f"TIME:RELTo{edge} 0", expect_response=False)
                for rising in (1, 3, 5, 7):
                    u.command(f"TIME:QUEue{rising} 0s", expect_response=False)
                    u.command(f"TIME:QUEue{rising+1} {s['absolute'][rising+1]:.12f}s", expect_response=False)
                    u.command(f"TIME:QUEue{rising} {s['absolute'][rising]:.12f}s", expect_response=False)
                u.command("TIME:COMmit", expect_response=False)
                for edge, reference in s["references"].items():
                    u.command(f"TIME:RELTo{edge} {reference}", expect_response=False)
                recipe = deepcopy(s["recipe"])
                for values in recipe["channels"].values():
                    values.pop("delay"); values.pop("width")
                u.apply_recipe(recipe)
                after = u.read_active_settings()
                for edge, reference in s["references"].items():
                    if int(u.command(f"TIME:RELTo{edge}?")) != reference:
                        raise RuntimeError(f"Timing-edge {edge} reference restoration not verified")
                for ch in "ABCD":
                    item = after["channels"][ch]
                    if not item["enabled"].get("ok") or str(item["enabled"]["response"]).strip().upper() not in ("0", "OFF"):
                        raise RuntimeError(f"{ch} safe disabled state not verified")
                    for field, requested in (("delay_edge", "delay"), ("width_edge", "width")):
                        if not item[field].get("ok") or not math.isclose(seconds(item[field]["response"]), seconds(s["recipe"]["channels"][ch][requested]), abs_tol=1e-11, rel_tol=0.):
                            raise RuntimeError(f"{ch} {field} restoration not verified")
                if str(after["queries"]["trigger_source"].get("response", "")).strip().upper() != "OFF":
                    raise RuntimeError("Timing trigger source is not OFF")
                return after
            self.restoration[name] = attempt(name + " restore and verify", restore_timing)
        for name, device in reversed(tuple(self.devices.items())):
            closer = getattr(device, "deinitialize", None) if name == "mircat" else getattr(device, "close", None)
            if closer:
                attempt(name + " close", closer)
        self.restoration.update(errors=errors, safe_verified=not errors,
            disposition="Sources, outputs, emission and engines remain inhibited; previous active emission is not resumed",
            original=self.original)
        return self.restoration
