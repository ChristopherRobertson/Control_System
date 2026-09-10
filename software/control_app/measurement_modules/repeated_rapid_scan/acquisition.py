"""Owned installed-device acquisition of finite, uninterrupted recovery movies.

No Phase Scan scientific engine is imported.  HF2LI's native poll subscriptions
remain active for the whole declared movie, including flyback and pump crossing.
Polls only drain native buffers: the acknowledged T660 table defines every edge.
The unpumped qualification train is explicitly additional to the declared movie.
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
        if any(not item.get("locked", False) for item in quality):
            flags["unlocked"] = np.ones(int(np.count_nonzero(selected)), dtype=bool)
        if any(item.get("overload", False) for item in quality):
            flags["clipped"] = np.ones(int(np.count_nonzero(selected)), dtype=bool)
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
                                 "observed_scan_start_ticks": scan_start_ticks,
                                 "observed_scan_periods_s": observed_periods,
                                 "observed_scan_period_median_s": float(np.median(observed_periods)) if len(observed_periods) else None,
                                 "observed_period_basis": "Differences of native observed sweep-start ticks; jitter and gaps retained"})


class InstalledDevicesAcquirer:
    """Per-operation real services created only through the frozen host context."""

    def __init__(self, context, operation, plan):
        self.context, self.operation, self.plan = context, operation, plan
        self.settings = get(plan, "settings")
        self.devices, self.original, self.raw_movies = {}, {}, []
        self.readbacks, self.restoration = {}, {}
        self._streaming = False
        self._hf_snapshot_preset = None
        self.config = plain(operation.configuration.get("repeated_rapid_scan", {}))
        for calibration in operation.calibration_records:
            candidate = get(calibration, "device_configuration")
            if candidate:
                self.config.update(plain(candidate))

    def _device(self, name):
        device = self.context.devices.create(name, self.operation)
        self.devices[name] = device  # Retain even when connection fails.
        return device

    def prepare(self, worker):
        worker.check_cancelled()
        if not self.config:
            raise ValueError("An applicable promoted repeated rapid-scan device_configuration is required")
        if not self.config.get("tee_receiver_topology_verified"):
            raise ValueError("Installed tee/receiver topology must be verified for the selected calibration")
        for key in ("hf2li", "marker_bits", "trajectory_calibration_id", "direction_levels", "clock_topology"):
            if key not in self.config:
                raise ValueError(f"Promoted device configuration is missing {key}")
        if set(self.config["direction_levels"]) != {"forward", "reverse"} or set(self.config["direction_levels"].values()) != {0, 1}:
            raise ValueError("Qualified direction polarity must identify forward and reverse as distinct DIO levels")
        topology_fields = {"clock_connector_mode", "clock_external_lock_enabled", "clock_external_frequency_hz", "clock_lock_status"}
        if any(not topology_fields <= set(self.config["clock_topology"].get(name, {})) for name in ("t660_1", "t660_2")):
            raise ValueError("Physical clock topology requires connector, external-lock enable, frequency and lock-status readbacks for both T660 units")
        unequal_filters = (get(self.settings, "sample_filter_order") != get(self.settings, "reference_filter_order") or
                           get(self.settings, "sample_filter_timeconstant_s") != get(self.settings, "reference_filter_timeconstant_s"))
        detector_corrections = self.config.get("detector_clock_corrections", {})
        if get(self.settings, "mode") == "dual" and unequal_filters and (not isinstance(detector_corrections, Mapping) or not {"sample", "reference"} <= set(detector_corrections)):
            raise ValueError("Unequal detector filters require independently calibrated sample and reference latency corrections; order times tau is not an observation")
        if isinstance(detector_corrections, Mapping):
            if any(not values.get("calibration_id") for values in detector_corrections.values()):
                raise ValueError("Detector clock/latency correction requires an applicable calibration identity")
        notify(worker, "Configuration: connecting owned HF2LI, MIRcat and T660 services")
        from control_app.devices.hf2li_service import HF2LIPreset
        # Include every configured timing/detector demodulator in preservation;
        # the generic service's default snapshot covers detector indices only.
        self._hf_snapshot_preset = HF2LIPreset("repeated_rapid_scan_selected", self.config["hf2li"])
        hf = self._device("hf2li"); hf.connect()
        self.original["hf2li"] = hf.export_settings_snapshot(preset=self._hf_snapshot_preset)
        if self.original["hf2li"].get("read_errors"):
            raise ValueError("Cannot preserve all HF2LI settings before configuration")
        qcl = self._device("mircat"); qcl.initialize()
        qcl_id = int(get(self.settings, "qcl", self.config.get("qcl", 1)))
        coverage = qcl.get_qcl_tuning_range(qcl_id)
        self.readbacks["qcl_coverage"] = coverage
        if not coverage["min_cm1"] <= get(self.settings, "scan_start_cm1") < get(self.settings, "scan_stop_cm1") <= coverage["max_cm1"]:
            raise ValueError("Selected uninterrupted spectral window is outside the connected QCL coverage")
        self.original["mircat"] = {
            "trigger": qcl.get_wavelength_trigger_params(),
            "marker_width_us": qcl.get_wavelength_trigger_pulse_width_us(),
            "pulse": {"qcl": qcl_id, "pulse_rate_hz": qcl.get_qcl_pulse_rate(qcl_id),
                      "pulse_width_ns": qcl.get_qcl_pulse_width(qcl_id), "current_ma": qcl.get_qcl_current(qcl_id)}}
        for name in ("t660_1", "t660_2"):
            worker.check_cancelled()
            unit = self._device(name); unit.connect()
            self.original[name] = self._snapshot_timing(unit)
            topology = self.config["clock_topology"][name]
            for field, expected in topology.items():
                actual_clock = self.original[name]["readback"]["queries"][field]
                actual_value = str(actual_clock.get("response", "")).strip().upper()
                if not actual_clock.get("ok") or actual_value != str(expected).strip().upper():
                    raise ValueError(f"{name} physical clock topology {field} readback {actual_value!r} != qualified {expected!r}")
            unit.set_trigger_source("OFF"); unit.force_eod()
            for channel in "ABCD":
                unit.disable_channel(channel)
        hf_config = self.config["hf2li"]
        for role in ("sample", "reference"):
            if role == "reference" and get(self.settings, "mode") != "dual":
                continue
            index = get(self.settings, role + "_demodulator")
            if index != hf_config["roles"][role + "_demodulator"]:
                raise ValueError(f"{role} detector role differs from the selected qualified topology")
            demod = next((d for d in hf_config["demodulators"] if d["index"] == index), None)
            if demod is None:
                raise ValueError(f"No qualified configuration for {role} demodulator")
            input_values = next((value for value in hf_config.get("signal_inputs", {}).values() if value.get("index") == demod.get("adcselect")), None)
            if input_values is None or not math.isclose(float(input_values["range_v"]), get(self.settings, role+"_input_range_v"), rel_tol=1e-9):
                raise ValueError(f"{role} detector input/range differs from the selected qualified wiring")
            for field, setting in (("rate_sps", "_rate_hz"), ("order", "_filter_order"), ("timeconstant_s", "_filter_timeconstant_s")):
                if not math.isclose(float(demod[field]), float(get(self.settings, role+setting)), rel_tol=1e-9):
                    raise ValueError(f"{role} {field} differs from the applicable qualified settings")
        hf.configure_signal_inputs(hf_config.get("signal_inputs", {}))
        hf.configure_pll(hf_config.get("pll", {}))
        hf.configure_oscillators(hf_config.get("oscillators", []))
        hf.configure_demodulators(hf_config["demodulators"])
        hf.sync()
        roles = hf_config["roles"]
        required = (roles["sample_demodulator"], roles["timing_demodulator"])
        if get(self.settings, "mode") == "dual":
            required += (roles["reference_demodulator"],)
        if len(set(required)) != len(required):
            raise ValueError("Sample, reference and timing require independent demodulator roles")
        actual = hf.export_settings_snapshot(preset=self._hf_snapshot_preset)
        self.readbacks.update(hf2li=actual, clockbase_hz=hf.get_clockbase(), roles=roles,
                              marker_bits=self.config["marker_bits"],
                              direction_levels=self.config["direction_levels"],
                              trajectory_calibration_id=self.config["trajectory_calibration_id"],
                              clock_correction=self.config.get("clock_correction", {}),
                              detector_clock_corrections=self.config.get("detector_clock_corrections", ()),
                              sample_clock_id=self.config.get("sample_clock_id", "hf2li"),
                              reference_clock_id=self.config.get("reference_clock_id", "hf2li"),
                              optical_time_zero=self.config.get("optical_time_zero", {}))
        nodes = actual.get("nodes", {})
        if actual.get("read_errors"):
            raise ValueError("Connected HF2LI configured settings could not all be read back")
        for demod in hf_config["demodulators"]:
            prefix = f"/{hf.device_id}/demods/{demod['index']}/"
            for field, key in (("enable", "enable"), ("adcselect", "adcselect"), ("oscselect", "oscselect"),
                               ("harmonic", "harmonic"), ("order", "order"), ("timeconstant", "timeconstant_s"), ("trigger", "trigger")):
                if key in demod and not math.isclose(float(nodes[prefix+field]["value"]), float(demod[key]), rel_tol=1e-6):
                    raise ValueError(f"HF2LI demodulator {demod['index']} {field} readback differs from qualified setting")
        for input_values in hf_config.get("signal_inputs", {}).values():
            prefix = f"/{hf.device_id}/sigins/{input_values['index']}/"
            for field, key in (("ac", "ac"), ("imp50", "impedance_50ohm"), ("diff", "differential"), ("range", "range_v")):
                if key in input_values and not math.isclose(float(nodes[prefix+field]["value"]), float(input_values[key]), rel_tol=1e-6):
                    raise ValueError(f"HF2LI input {input_values['index']} {field} readback differs from qualified setting")
        total = 0.
        for demod in required:
            path = f"/{hf.device_id}/demods/{demod}/rate"
            rate = float(nodes[path]["value"])
            requested = next(d["rate_sps"] for d in hf_config["demodulators"] if d["index"] == demod)
            if not math.isclose(rate, requested, rel_tol=1e-6):
                raise ValueError(f"HF2LI demodulator {demod} requested {requested} Sa/s but selected {rate}")
            total += rate
        maximum = float(self.config["aggregate_rate_limit_sps"])
        if total > maximum:
            raise ValueError("Combined sample/reference/timing rate exceeds connected aggregate capacity")
        self.readbacks["aggregate_rate_sps"] = total
        self.readbacks["required_demodulators"] = required
        sample_rate = float(nodes[f"/{hf.device_id}/demods/{roles['sample_demodulator']}/rate"]["value"])
        timing_rate = float(nodes[f"/{hf.device_id}/demods/{roles['timing_demodulator']}/rate"]["value"])
        self.readbacks["capabilities"] = {"frame_capacity": self.devices["t660_2"].verified_frame_capacity(),
            "max_aggregate_rate_hz": maximum, "max_movie_bytes": self.config.get("max_movie_bytes"),
            "available_demodulators": tuple(sorted({d["index"] for d in hf_config["demodulators"]})),
            "connected_readback_id": self.operation.run_id,
            "detector_roles_verified": True, "receiver_topology_verified": True,
            "continuous_recording_verified": bool(self.config.get("continuous_recording_verified", False)),
            "actual_sample_rate_hz": sample_rate,
            "actual_reference_rate_hz": float(nodes[f"/{hf.device_id}/demods/{roles['reference_demodulator']}/rate"]["value"]) if get(self.settings, "mode") == "dual" else None,
            "acquisition_timing_rate_hz": timing_rate,
            "actual_scan_period_s": None}
        self.readbacks["selected_prior_scan_period"] = {"period_s": self.config.get("measured_scan_period_s"),
            "source": self.config.get("trajectory_calibration_id"),
            "basis": "Selected calibration evidence; configuration check does not measure a new scan period"}
        # The clock recipe can run the reference/probe but never a sample pump.
        clock_recipe = plain(get(get(get(self.plan, "movies")[0], "compiled"), "continuous_clock_recipe"))
        clock_recipe.update(trigger_source="OFF", start=False)
        clock_recipe["channels"]["C"]["enabled"] = False
        clock_recipe["channels"]["D"]["enabled"] = False
        for edge in (1, 3, 5, 7):
            self.devices["t660_1"].command(f"TIME:RELTo{edge} 0", expect_response=False)
        self.devices["t660_1"].apply_recipe(clock_recipe)
        clock_actual = self.devices["t660_1"].read_active_settings()
        clock_frequency = clock_actual["queries"]["synth_frequency"]
        expected_frequency = get(get(get(self.plan, "movies")[0], "compiled"), "input_frequency_hz")
        if not clock_frequency.get("ok") or not math.isclose(float(str(clock_frequency["response"]).strip().removesuffix("Hz")), expected_frequency, rel_tol=1e-10):
            raise ValueError("T660 clock readback differs from the compiled scan-opportunity clock")
        self.readbacks["clock_settings"] = clock_actual
        self.devices["t660_1"].set_trigger_source("SYN")
        self.devices["t660_1"].command("START", expect_response=False)
        worker.check_cancelled()
        notify(worker, "Tuning and settling: checking interlock, TECs and calibrated probe settings")
        if not qcl.is_interlock_set() or not qcl.is_key_switch_set():
            raise RuntimeError("MIRcat interlock/key switch is not ready")
        if not qcl.is_laser_armed():
            qcl.arm()
        self._wait(qcl.are_tecs_ready, worker, self.config.get("tec_timeout_s", 90.), "MIRcat TEC settling")
        qcl.set_qcl_pulse_params(**self.config["mircat_pulse"])
        pulse = self.config["mircat_pulse"]
        for getter, key in ((qcl.get_qcl_pulse_rate, "pulse_rate_hz"), (qcl.get_qcl_pulse_width, "pulse_width_ns"), (qcl.get_qcl_current, "current_ma")):
            if not math.isclose(float(getter(qcl_id)), float(pulse[key]), rel_tol=1e-6):
                raise ValueError(f"MIRcat {key} readback differs from selected calibration settings")
        self.readbacks["mircat_before"] = plain(qcl.read_state())
        self._wait(lambda: self._quality()["locked"], worker, self.config.get("lock_timeout_s", 30.), "HF2LI reference-lock settling")

    def safe_pause(self):
        """Inhibit pump/scan commands and optical output before a physical action."""
        self.devices["t660_2"].set_trigger_source("OFF")
        self.devices["t660_1"].disable_channel("C")
        self.devices["mircat"].turn_emission_off()
        self.devices["mircat"].stop_scan_if_needed()
        if self.devices["mircat"].is_emission_on():
            raise RuntimeError("Cannot request a physical change while MIRcat emission remains on")

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

    def capture(self, movie_plan, worker, *, qualification=False):
        worker.check_cancelled()
        compiled = get(movie_plan, "compiled")
        frames = plain(get(compiled, "frames"))
        count = int(get(compiled, "expected_scan_count"))
        if qualification:
            count = int(get(self.settings, "pre_scans", get(self.settings, "pre_pump_scans", 3)))
            terminal = deepcopy(frames[-1])
            frames = frames[:count]
            for frame in frames:
                for channel in "AB":
                    frame["channels"][channel]["enabled"] = False
            terminal.update(scan_index=None, role="terminal_inhibit", terminal_inhibit=True,
                            programmed_scan_start_s=None, programmed_frame_start_s=count*get(compiled, "scan_period_s"))
            for values in terminal["channels"].values():
                values["enabled"] = False
            frames.append(terminal)
        physical_count = len(frames)
        if physical_count != count+1 or any(values["enabled"] for values in frames[-1]["channels"].values()):
            raise ValueError("Finite movie requires all scan frames followed by one explicit all-OFF terminal frame")
        if sum(bool(frame["channels"]["C"]["enabled"]) for frame in frames) != count:
            raise ValueError("Scan trigger count differs from the declared spectral scans; terminal is not a scan")
        expected_pumps = 0 if qualification else get(movie_plan, "pump_count", 0)
        if any(frame["channels"]["D"]["enabled"] for frame in frames):
            raise ValueError("Unwired T660 channel D must stay disabled")
        for channel in "AB":
            if sum(bool(frame["channels"][channel]["enabled"]) for frame in frames) != expected_pumps:
                raise ValueError("Each pumped movie requires exactly one FIRE and one Q-switch")
        raw = {"movie_id": get(movie_plan, "movie_id"), "qualification": qualification,
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
        qcl_id = int(get(self.settings, "qcl", self.config.get("qcl", 1)))
        qcl.stop_scan_if_needed()
        qcl.turn_emission_off()
        qcl.tune_to_wavenumber(start, qcl=qcl_id)
        self._wait(qcl.is_tuned, worker, self.config.get("tune_timeout_s", 45.), "MIRcat tuning")
        qcl.set_external_sweep_trigger_params(start_cm1=start, stop_cm1=stop,
            wavelength_trigger_interval_cm1=self.config["marker_interval_cm1"], external_process_trigger=True)
        qcl.set_wavelength_trigger_pulse_width_us(self.config["marker_width_us"])
        # No optical transition is authorized by a saved plan alone.
        if not self.config.get("approved_laser_safety_condition"):
            raise ValueError("Explicit applicable laser-safety condition is missing")
        qcl.turn_emission_on(approved_laser_safety_condition=True)
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
        notify(worker, f"Acquisition: {'qualification' if qualification else 'recovery'} movie, {count} scans, {expected_pumps} pump")
        hf.start_acquisition(demodulators=self.readbacks["required_demodulators"], fields=("x", "y", "dio", "frequency"))
        self._streaming = True
        started = monotonic()
        deadline = started + duration + float(self.config.get("completion_guard_s", 5.))
        try:
            # Start establishes an arbitrary clock epoch; sub-frame timing stays
            # entirely in the accepted hardware table, independently observed.
            frame_unit.start_frame_table()
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
                if not quality["locked"] or quality["overload"]:
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
        if qualification:
            effective["movie_id"] += ":qualification"
        movie = decode_native_movie(raw["chunks"], effective, self.settings, raw["readbacks"], status=raw["status"])
        if len(movie.pump_observations) != expected_pumps:
            raise ValueError(f"Independent pump count {len(movie.pump_observations)} != authorized {expected_pumps}; no automatic retry")
        if len(movie.scans) != count:
            raise ValueError(f"Observed complete scans {len(movie.scans)} != declared {count}; native movie retained")
        return movie

    def _quality(self):
        hf = self.devices["hf2li"]
        pll = int(self.config["hf2li"].get("pll", {}).get("index", 0))
        locked = bool(hf._get_node("int", f"/{hf.device_id}/plls/{pll}/locked"))
        overload_nodes = self.config.get("overload_nodes")
        if not overload_nodes:
            raise ValueError("Qualified HF2LI overload-status nodes are required")
        overload = any(bool(hf._get_node("int", path.format(device=hf.device_id))) for path in overload_nodes)
        return {"locked": locked, "overload": overload, "observed_monotonic_s": monotonic()}

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
                attempt("MIRcat pulse restore", lambda: qcl.set_qcl_pulse_params(**saved["pulse"]))
                allowed = ("pulse_mode", "process_trigger_mode", "start", "stop", "interval", "units", "dwell_us", "after_off_us")
                attempt("MIRcat trigger restore", lambda: qcl.set_wavelength_trigger_params(**{k: v for k, v in saved["trigger"].items() if k in allowed}))
                attempt("MIRcat marker restore", lambda: qcl.set_wavelength_trigger_pulse_width_us(saved["marker_width_us"]))
                def verify_mircat():
                    pulse = saved["pulse"]
                    actual_pulse = {"qcl": pulse["qcl"], "pulse_rate_hz": qcl.get_qcl_pulse_rate(pulse["qcl"]),
                                    "pulse_width_ns": qcl.get_qcl_pulse_width(pulse["qcl"]), "current_ma": qcl.get_qcl_current(pulse["qcl"])}
                    actual_trigger = qcl.get_wavelength_trigger_params()
                    actual_width = qcl.get_wavelength_trigger_pulse_width_us()
                    after = {"pulse": actual_pulse, "trigger": actual_trigger, "marker_width_us": actual_width}
                    self.restoration["mircat"] = {"before": saved, "after": after}
                    expected_trigger = {k: v for k, v in saved["trigger"].items() if k in allowed}
                    if any(not math.isclose(float(actual_pulse[k]), float(v), rel_tol=1e-6, abs_tol=1e-6) for k, v in pulse.items()):
                        raise RuntimeError("MIRcat restored pulse settings readback mismatch")
                    if any(k not in actual_trigger or not math.isclose(float(actual_trigger[k]), float(v), rel_tol=1e-6, abs_tol=1e-6) for k, v in expected_trigger.items()):
                        raise RuntimeError("MIRcat restored trigger settings readback mismatch")
                    if actual_width != saved["marker_width_us"]:
                        raise RuntimeError("MIRcat restored marker-width readback mismatch")
                    return after
                attempt("MIRcat restoration readback verification", verify_mircat)
            emission = attempt("MIRcat emission verification", qcl.is_emission_on)
            if emission is not False:
                errors.append("MIRcat safe emission-off readback was not verified")
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
