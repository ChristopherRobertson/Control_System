"""Finite phase-delay blocks; construction and planning never open hardware.

Complete timing tables are planned before emission. Each small DAQ block is
prepared before its event sequence and drained into bounded host array storage.
Native blocks remain in memory until the runner consolidates the run on disk.
"""
from __future__ import annotations

from control_app.paths import research_output_path
from copy import deepcopy
from dataclasses import asdict
from io import StringIO
from threading import Thread
from time import monotonic
import math
import numpy as np
from control_app.devices.hf2li_service import HF2LIService, HF2LIPreset
from control_app.devices.mircat_service import MircatService, PULSE_MODE_EXTERNAL_TRIGGER, PROC_TRIG_MODE_EXTERNAL, UNITS_CM1
from control_app.devices.t660_service import T660Service
from control_app.workflows.phase_scan_data import (
    DETECTOR_INPUT, HF2_PRESET, QCL_CURRENT_MA, SINGLE_DETECTOR_MODE, acquisition_settings, utc_now, write_json,
)
from control_app.workflows.phase_scan import build_phase_scan_plan, derive_capture_window, partition_frame_blocks
from control_app.workflows.phase_scan_native import spectrum_from_sweep
from control_app.workflows.phase_scan_labone import (
    FinitePhaseDAQ, AcquisitionIntegrityError, AcquisitionCapacityError,
    MAX_EVENTS_PER_BLOCK, estimate_capture_bytes,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager


def channel_segments(start, stop, ranges):
    """Cover the range using installed QCL readbacks, with one SDK sweep per segment."""
    direction = 1 if stop > start else -1
    current, segments = float(start), []
    while (stop-current)*direction > 1e-7:
        candidates = [r for r in ranges if r["min_cm1"]-1e-7 <= current <= r["max_cm1"]+1e-7
                      and ((r["max_cm1"]-current) if direction > 0 else (current-r["min_cm1"])) > 1e-7]
        if not candidates:
            raise ValueError(f"No installed QCL covers {current:g} cm⁻¹ toward {stop:g} cm⁻¹")
        chosen = max(candidates, key=lambda r: r["max_cm1"] if direction > 0 else -r["min_cm1"])
        end = min(stop, chosen["max_cm1"]) if direction > 0 else max(stop, chosen["min_cm1"])
        segments.append({"qcl": int(chosen["qcl"]), "start_cm1": current, "stop_cm1": float(end)})
        current = float(end)
        if len(segments) > len(ranges):
            raise ValueError("QCL range coverage did not converge")
    return segments

def frequency_hz(value):
    text = str(value).strip().lower().replace(" ", "")
    for suffix, multiplier in (("mhz", 1e6), ("khz", 1e3), ("hz", 1.0)):
        if text.endswith(suffix):
            return float(text[:-len(suffix)]) * multiplier
    return float(text)

def event_timing(event):
    """Schedule signed phase; blank and sample-baseline frames inhibit the pump.

    Removing the reference detector changes no pulse delays or digital wiring.
    Every blank/sample sweep uses the same Process Trigger width and probe clock.
    """
    phase_s = float(event.phase_delay_us or 0) * 1e-6
    pump_s = .001 + max(.000180, -phase_s)
    scan_s = pump_s + phase_s if event.pump_enabled else .001
    def pulse(delay_s, width_s, enabled=True):
        return {"enabled": enabled, "delay": f"{delay_s:.12f}s", "width": f"{width_s:.12f}s",
                "polarity": "negative", "termination": "50OHM"}
    channels = {"A": pulse(pump_s-.000180, .000010, event.pump_enabled),
                "B": pulse(pump_s-.000000170, .000010, event.pump_enabled),
                "C": pulse(scan_s, .010), "D": pulse(0, .000010, False)}
    return {"channels": channels}, max(pump_s, scan_s+.010)


def acquisition_setting_nodes(device_id, settings):
    """The exact applied configuration used for blank/sample compatibility.

    Keep the PLL, timing demodulator, CH1 and disabled-stream enables. Unused
    CH2 settings and the instantaneous PLL oscillator frequency do not affect
    this acquisition and are retained only in the complete diagnostic snapshot.
    """
    nodes = {}
    def add(group, index, values, mapping):
        for name, node in mapping.items():
            if name in values:
                value = values[name]
                nodes[f"/{device_id}/{group}/{index}/{node}"] = int(value) if isinstance(value, bool) else value
    for values in settings["signal_inputs"].values():
        add("sigins", values["index"], values,
            {"ac": "ac", "impedance_50ohm": "imp50", "differential": "diff", "range_v": "range"})
    for values in settings["demodulators"]:
        add("demods", values["index"], values,
            {"enable": "enable", "adcselect": "adcselect", "oscselect": "oscselect", "harmonic": "harmonic",
             "order": "order", "timeconstant_s": "timeconstant", "rate_sps": "rate", "trigger": "trigger"})
    values = settings["pll"]
    add("plls", values.get("index", 0), values,
        {"enable": "enable", "adcselect": "adcselect", "freqcenter_hz": "freqcenter",
         "harmonic": "harmonic", "order": "order", "adcthreshold": "adcthreshold"})
    return nodes


def verified_acquisition_settings(snapshot, device_id, settings):
    """Verify applied nodes while retaining actual calibrated/quantized values."""
    stable = {}
    for path, requested in acquisition_setting_nodes(device_id, settings).items():
        if path in snapshot['read_errors'] or path not in snapshot['nodes']:
            raise RuntimeError(f'HF2LI acquisition setting could not be read back: {path}')
        stable[path] = snapshot['nodes'][path]
        actual = stable[path]['value']
        if path.endswith('/demods/2/rate'):
            matches = math.isfinite(float(actual)) and float(actual) > 0
        elif isinstance(requested, float):
            # HF2LI exposes calibrated voltage ranges and quantized filter
            # constants (e.g. 1 ms requests read back as 1.0018887079 ms).
            tolerance = .03 if '/sigins/' in path and path.endswith('/range') else .01 if path.endswith('/timeconstant') else .001
            matches = math.isclose(float(actual), requested, rel_tol=tolerance, abs_tol=1e-12)
        else:
            matches = actual == requested
        if not matches:
            raise RuntimeError(f'HF2LI acquisition setting readback differs from the preset: {path}')
    return stable


class LivePhaseScanAcquirer:
    detector_input_indices = (0,)
    inactive_demodulators = (1, 3, 4, 5)

    def _detector_metadata(self):
        return {"detector_mode": SINGLE_DETECTOR_MODE, "detector_input": DETECTOR_INPUT}

    def _spectrum_from_native(self, native):
        return spectrum_from_sweep(native, start_cm1=self.segments[0]["start_cm1"],
            stop_cm1=self.segments[0]["stop_cm1"], targets_cm1=self.targets,
            origin_tick=int(native["sweep_event_tick"]),
            pump_tick=native["pump_event_tick"], pump_reference="electrical_sync")

    def __init__(self, *, config_path=None, laser_factory=None, hf_factory=None, t660_factory=None,
                 tec_ready_stability_s=5.0, qualified_trajectory=None, qualified_sweep_active_s=None,
                 capacity_verifier=None, promoted_bundle=None, max_retained_bytes=512*1024*1024):
        self.config_path = config_path
        self.laser_factory = laser_factory or MircatService.from_config
        self.hf_factory = hf_factory or HF2LIService.from_config
        self.t660_factory = t660_factory or T660Service.from_config
        self.qualified_trajectory = qualified_trajectory
        self.qualified_sweep_active_s = qualified_sweep_active_s
        self.capacity_verifier = capacity_verifier
        self.promoted_bundle = promoted_bundle
        self.max_retained_bytes = int(max_retained_bytes)
        if self.max_retained_bytes <= 0:
            raise ValueError("max_retained_bytes must be positive")
        self._active_daq = None
        self.tec_ready_stability_s = float(tec_ready_stability_s)
        if not math.isfinite(self.tec_ready_stability_s) or self.tec_ready_stability_s < 0:
            raise ValueError("tec_ready_stability_s must be finite and nonnegative")
        self.authorized = False
        self.qcl = self.hf = self.log = self.store = self.cancel = None
        self.units = {}
        self.progress = lambda message: None
        self._closed = self._safed = self._clock_started = False
        self._start_thread = None
        self.blocks = []
        self.partial_blocks = []
        self.warnings = []
        self.preparation_tec_readiness_checks = []

    def authorize(self, approved):
        self.authorized = approved is True

    def resolve_plan(self, plan):
        if self.qualified_trajectory is None and self.promoted_bundle is not None:
            from control_app.workflows.phase_scan_qualification import phase_scan_qualification_from_bundle
            qualification = phase_scan_qualification_from_bundle(self.promoted_bundle)
            self.qualified_trajectory = qualification["calibrated_trajectory"]
            self.qualified_sweep_active_s = qualification["qualified_sweep_active_s"]
        if self.qualified_trajectory is None:
            raise RuntimeError("Phase acquisition requires a qualified calibrated sweep trajectory; no promoted trajectory is installed")
        if self.qualified_sweep_active_s is None:
            raise RuntimeError("Phase acquisition requires a qualified Sweep Active duration")
        self.plan = build_phase_scan_plan(plan.settings, calibrated_trajectory=self.qualified_trajectory)
        self.capture_window = derive_capture_window(self.qualified_sweep_active_s)
        if self.plan.scan_duration_s > self.qualified_sweep_active_s + 1e-12:
            raise RuntimeError("Calibrated trajectory exceeds the qualified Sweep Active duration")
        active_delay = self.qualified_trajectory.get("sweep_active_delay_s")
        if active_delay is not None:
            active_delay = float(active_delay)
            first, last = self.plan.trajectory_time_bounds_s
            if (not math.isfinite(active_delay) or active_delay < 0 or first < active_delay - 1e-12 or
                    last > active_delay + self.qualified_sweep_active_s + 1e-12):
                raise RuntimeError("Calibrated trajectory lies outside the qualified Sweep Active interval")
        return self.plan

    def _check(self, *, interlock=True):
        if self.cancel is not None and self.cancel.is_set():
            raise InterruptedError("Phase Scan aborted")
        if interlock and self.qcl is not None:
            if not self.qcl.is_interlock_set() or not self.qcl.is_key_switch_set():
                raise RuntimeError("MIRcat interlock/key switch is open. Outputs will be stopped.")
            error = self.qcl.get_system_error_word()
            if error:
                raise RuntimeError(f"MIRcat reports system error {error}; resolve it before scanning")

    def _wait(self, predicate, timeout, description):
        deadline = monotonic() + timeout
        while True:
            self._check()
            self._service_daq()
            if predicate():
                return
            if monotonic() >= deadline:
                raise TimeoutError(description)
            self.cancel.wait(.05)

    def _service_daq(self):
        """Drain data without scheduling a hardware timing edge."""
        if (self._active_daq is not None and self._active_daq.incremental
                and self._active_daq.armed and not self._active_daq.closed):
            self._active_daq.drain()

    def _wait_for_stable_tecs(self, context, *, record=None):
        """Require armed/TEC-ready continuously across SDK mode transitions."""
        observations = []
        deadline = monotonic() + 120.0
        ready_since = None
        self.progress(
            f"Waiting for MIRcat TEC ready continuously for {self.tec_ready_stability_s:g} s ({context})"
        )
        while True:
            self._check()
            now = monotonic()
            self._service_daq()
            ready = bool(self.qcl.are_tecs_ready()) and bool(self.qcl.is_laser_armed())
            observations.append({"elapsed_s": now, "ready_and_armed": ready})
            if ready:
                ready_since = now if ready_since is None else ready_since
                if now - ready_since >= self.tec_ready_stability_s:
                    if record is not None:
                        record.setdefault("tec_readiness_checks", []).append(
                            {"context": context, "required_stability_s": self.tec_ready_stability_s,
                             "observations": observations}
                        )
                    else:
                        self.preparation_tec_readiness_checks.append(
                            {"context": context, "required_stability_s": self.tec_ready_stability_s,
                             "observations": observations}
                        )
                    return
            else:
                ready_since = None
            if now >= deadline:
                raise TimeoutError(f"MIRcat TEC readiness did not remain stable ({context})")
            self.cancel.wait(.05)

    def _verify_external_trigger(self, segment, interval, context, record):
        """Re-read the real MIRcat mode after each sweep-state transition."""
        readback = self.qcl.get_wavelength_trigger_params()
        expected = {
            "pulse_mode": PULSE_MODE_EXTERNAL_TRIGGER,
            "process_trigger_mode": PROC_TRIG_MODE_EXTERNAL,
            "units": UNITS_CM1,
            "start": segment["start_cm1"],
            "stop": segment["stop_cm1"],
            "interval": interval,
        }
        mismatch = {}
        for name, value in expected.items():
            actual = readback.get(name)
            if (isinstance(value, (int, float)) and isinstance(actual, (int, float)) and
                    math.isclose(float(actual), float(value), abs_tol=.001, rel_tol=1e-6)):
                continue
            if actual != value:
                mismatch[name] = {"actual": actual, "expected": value}
        record.setdefault("mircat_trigger_checks", []).append(
            {"context": context, "readback": readback, "mismatch": mismatch}
        )
        if mismatch:
            raise RuntimeError(f"MIRcat external trigger settings changed at {context}: {mismatch}")
        return readback

    def _verify_unit(self, unit, recipe):
        readback = unit.read_active_settings()
        mismatches = TimingRecipeManager._compare_readback({unit.name: recipe}, {unit.name: readback})
        if mismatches:
            raise RuntimeError(f"{unit.name} timing readback mismatch: {mismatches}")
        return readback

    def _observe_marker_channel(self, segment, record):
        observation = {"context": "after_block_setup", "timestamp_utc": utc_now(),
                       "source": "MIRcatSDK_GetWlTrigChanParams", "channel": segment["qcl"],
                       "available": False}
        try:
            getter = getattr(self.qcl, "get_wavelength_trigger_channel_params", None)
            if not callable(getter):
                raise RuntimeError("Per-QCL wavelength-trigger readback is unavailable")
            observation["readback"] = getter(segment["qcl"])
            observation["available"] = True
        except Exception as exc:
            observation["error"] = f"{type(exc).__name__}: {exc}"
            record.setdefault("warnings", []).append(f"Controller marker identity unavailable: {exc}")
        record.setdefault("mircat_marker_channel_checks", []).append(observation)

    def _verify_qcl_pulse_settings(self, qcl, *, external_rate_hz):
        """Verify internal laser settings without treating them as the pulse clock."""
        actual = {"qcl": int(qcl), "settings_role": "mircat_internal",
                  "current_ma": self.qcl.get_qcl_current(qcl),
                  "pulse_rate_hz": self.qcl.get_qcl_pulse_rate(qcl),
                  "pulse_width_ns": self.qcl.get_qcl_pulse_width(qcl)}
        for key, target in (
            ("current_ma", self.settings.qcl_current_ma),
            ("pulse_rate_hz", self.settings.mircat_internal_repetition_rate_hz),
            ("pulse_width_ns", self.settings.mircat_internal_pulse_width_ns),
        ):
            if not math.isclose(actual[key], target, rel_tol=1e-5, abs_tol=1e-3):
                raise RuntimeError(f"QCL {qcl} internal {key} readback does not match the requested value")
        if not math.isfinite(external_rate_hz) or external_rate_hz <= 0 or actual["pulse_rate_hz"] <= external_rate_hz:
            raise RuntimeError("MIRcat internal rate readback must be higher than the T660-1 trigger rate")
        limits = self.qcl.get_qcl_pulse_limits(qcl)
        actual["internal_duty_cycle"] = actual["pulse_rate_hz"] * actual["pulse_width_ns"] * 1e-9
        if (actual["pulse_rate_hz"] > limits["max_pulse_rate_hz"] or
                actual["pulse_width_ns"] > limits["max_pulse_width_ns"] or
                actual["internal_duty_cycle"] * 100 > min(30.0, limits["max_duty_cycle"]) + 1e-6):
            raise RuntimeError(f"MIRcat internal QCL {qcl} settings exceed readback limits")
        actual["internal_rate_margin_hz"] = actual["pulse_rate_hz"] - external_rate_hz
        return actual

    @staticmethod
    def _stop_unit(unit):
        errors = []
        for operation in (lambda: unit.set_trigger_source("OFF"), lambda: unit.command("STOP", expect_response=False)):
            try:
                operation()
            except Exception as exc:
                errors.append(str(exc))
        if unit.name == "t660_2":
            for command in ("TFRame:STOp", *(f"TRAin:{stage}:CouNT 0" for stage in ("ACTive", "NEXT", "QUEue"))):
                try:
                    unit.command(command, expect_response=False)
                except Exception as exc:
                    errors.append(str(exc))
        # Frame STOP can reinstall the channel configuration saved before the
        # frame engine started. Disable outputs after that restoration.
        for channel in "ABCD":
            try:
                unit.disable_channel(channel)
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError("; ".join(errors))


    def _input_integrity(self, context):
        status = {}
        for index in self.detector_input_indices:
            path = f"/{self.hf.device_id}/status/flags/adcclip/{index}"
            value = self.hf._get_node("int", path)
            status[path] = value
            if value:
                raise AcquisitionIntegrityError(f"HF2LI input {index+1} clipping at {context}")
        return status

    def _plan_for_settings(self, settings):
        return build_phase_scan_plan(settings)

    def _event_timing(self, event):
        return event_timing(event)

    def _configure_hf_preset(self, saved, copied):
        """Allow maintained acquisition modes to resolve their device settings."""
        return copied

    def _before_mircat_configuration(self):
        """Hook for modes that restore the pre-existing instrument settings."""

    def _before_timing_configuration(self, unit):
        """Hook for preserving non-emitting timing configuration."""

    def _restore_instrument_settings(self):
        """Called after safe idle and before transports are closed."""

    def _on_sequence_complete(self):
        """Hook for safe-idle before a deferred transfer of complete histories."""

    def _sequence_idle(self):
        """End one sequence; persistent experiments may retain their reference."""
        self._safe_idle()

    def _acquisition_metadata(self):
        return acquisition_settings(self.settings)

    def prepare(self, settings, store, cancel):
        if not self.authorized:
            raise PermissionError("Confirm this acquisition before laser operation")
        self.settings, self.store, self.cancel = settings, store, cancel
        self.resolve_plan(self._plan_for_settings(settings))
        # Transport command logs are buffered too: no implicit disk writes in
        # status polling or the hardware frame timing interval.
        self.log = StringIO()
        self._check(interlock=False)
        for name in ("t660_1", "t660_2"):
            unit = self.t660_factory(name, config_path=self.config_path, command_log=self.log)
            self.units[name] = unit
            unit.connect()
            identity = unit.identify()
            if str(unit.device_config["serial_number"]) not in [p.strip() for p in identity.split(",")]:
                raise RuntimeError(f"Unexpected {name} identity: {identity}")
            self._before_timing_configuration(unit)
            # Preparation inhibits sources; final safe-idle is a single, separate action.
            unit.set_trigger_source("OFF")
        self.probe_recipe = self.units["t660_1"].configure_continuous_clock(
            frequency_hz=settings.probe_repetition_rate_hz, pulse_width_ns=settings.probe_pulse_width_ns)
        probe = self._verify_unit(self.units["t660_1"], self.probe_recipe)
        self.probe_rate_readback_native = probe["queries"]["synth_frequency"]
        self.probe_rate_hz_readback = frequency_hz(self.probe_rate_readback_native["response"])
        # PLL configuration needs a real external reference during preflight.
        # Keep optical/probe and frame-input channels inhibited until DAQ and
        # the downstream frame engine are armed; only A runs during setup.
        reference = self.units["t660_1"]
        self.reference_recipe = deepcopy(self.probe_recipe)
        for channel in "BCD":
            reference.disable_channel(channel)
            self.reference_recipe["channels"][channel]["enabled"] = False
        for channel in "ABCD":
            self.units["t660_2"].disable_channel(channel)
        self._verify_unit(self.units["t660_2"], {
            "trigger_source": "OFF", "channels": {c: {"enabled": False} for c in "ABCD"}})
        self._verify_unit(reference, self.reference_recipe)
        reference.start_continuous_clock()
        self._clock_started = True
        self.reference_recipe["trigger_source"] = "SYN"
        self.reference_preflight_readback = self._verify_unit(reference, self.reference_recipe)
        self.qcl = self.laser_factory(config_path=self.config_path, command_log=self.log)
        self.qcl.initialize()
        self.qcl.stop_scan_if_needed()
        self.qcl.turn_emission_off()
        self.qcl.cancel_manual_tune()
        self._before_mircat_configuration()
        self.qcl.set_red_laser_pointer_enabled(False)
        self._check()
        ranges = [self.qcl.get_qcl_tuning_range(i) for i in range(1, self.qcl.get_num_installed_qcls()+1)]
        self.segments = channel_segments(settings.start_wavenumber_cm1, settings.stop_wavenumber_cm1, ranges)
        if len(self.segments) != 1:
            raise RuntimeError("Finite phase acquisition requires one qualified QCL trajectory spanning the requested range")
        segment = self.segments[0]
        number = segment["qcl"]
        limits = self.qcl.get_qcl_pulse_limits(number)
        minimum, maximum = self.qcl.get_qcl_current_limits(number)
        duty = settings.mircat_internal_repetition_rate_hz * settings.mircat_internal_pulse_width_ns * 1e-9
        if (settings.mircat_internal_repetition_rate_hz > limits["max_pulse_rate_hz"] or
                settings.mircat_internal_pulse_width_ns > limits["max_pulse_width_ns"] or
                duty * 100 > limits["max_duty_cycle"] + 1e-6 or not minimum <= settings.qcl_current_ma <= maximum):
            raise RuntimeError("MIRcat internal parameters exceed QCL readback limits")
        self.qcl.set_qcl_pulse_params(qcl=number, pulse_rate_hz=settings.mircat_internal_repetition_rate_hz,
                                     pulse_width_ns=settings.mircat_internal_pulse_width_ns,
                                     current_ma=settings.qcl_current_ma)
        self.configured_qcls = [self._verify_qcl_pulse_settings(number, external_rate_hz=self.probe_rate_hz_readback)]
        span = abs(segment["stop_cm1"]-segment["start_cm1"])
        self.marker_interval = span / max(1, math.ceil(span / 5))
        self.targets = np.linspace(segment["start_cm1"], segment["stop_cm1"], max(1, math.ceil(span / 5))+1)
        self.qcl.set_external_sweep_trigger_params(start_cm1=segment["start_cm1"], stop_cm1=segment["stop_cm1"],
                                                  wavelength_trigger_interval_cm1=self.marker_interval,
                                                  external_process_trigger=True)
        self.qcl.arm()
        self._wait_for_stable_tecs("after_arm")
        self.qcl.tune_to_wavenumber(segment["start_cm1"], qcl=number)
        self._wait(self.qcl.is_tuned, 45, "MIRcat did not tune to the requested start")
        self.hf = self.hf_factory(config_path=self.config_path, command_log=self.log)
        self.hf.connect()
        saved = self.hf.load_preset(getattr(self, "hf2_preset_name", HF2_PRESET))
        copied = deepcopy(saved.settings)
        # The same saved optical AND timing configuration is used for buffer
        # blank, sample baseline and pumped phase scans, regardless of phase step.
        for index in self.inactive_demodulators:
            copied["demodulators"] = [d for d in copied["demodulators"] if d["index"] != index]
            copied["demodulators"].append({"index": index, "enable": False})
        copied["pll"]["freqcenter_hz"] = self.probe_rate_hz_readback
        copied = self._configure_hf_preset(saved, copied)
        self.preset = HF2LIPreset(saved.name, copied)
        self.hf.apply_preset(self.preset)
        self._wait(lambda: math.isclose(self.hf.get_oscillator_frequency(0), self.probe_rate_hz_readback,
                                       rel_tol=.001), 10., "HF2LI did not lock to the reference-only T660-1 A clock")
        snapshot = self.hf.export_settings_snapshot(preset=self.preset)
        self.hf_settings_snapshot = snapshot
        stable = verified_acquisition_settings(snapshot, self.hf.device_id, copied)
        self.hf_detector_settings = stable
        self.clockbase = float(self.hf.get_clockbase())
        self.timing_rate = float(self.hf._get_node("double", f"/{self.hf.device_id}/demods/2/rate"))
        width_us = max(1, min(500, int(self.marker_interval/settings.scan_speed_cm1_s*1e6/4)))
        if width_us * 1e-6 < 2/self.timing_rate:
            raise RuntimeError("Timing readback cannot resolve the configured wavelength marker width")
        if self.qcl.set_wavelength_trigger_pulse_width_us(width_us) != width_us:
            raise RuntimeError("MIRcat wavelength marker width readback mismatch")
        status = self._input_integrity("preflight")
        return {"hf2li_device": snapshot["device_id"], "hf2li_detector_settings": stable,
                **self._detector_metadata(),
                "qcls": self.configured_qcls, "segments": self.segments,
                "t660_1_probe_rate_hz_readback": self.probe_rate_hz_readback,
                "capture_window": self.capture_window, "input_status": status}

    def _validate_execution_plan(self, plan):
        if not plan.calibrated:
            raise RuntimeError("Finite acquisition cannot use an uncalibrated preview plan")

    def _qualification_metadata(self):
        return {"calibrated_trajectory": self.qualified_trajectory,
                "qualified_sweep_active_s": self.qualified_sweep_active_s,
                "promoted_bundle_id": getattr(self.promoted_bundle, "bundle_id", None)}

    def _validate_spectrum(self, event, spectrum):
        return spectrum

    def prepare_blocks(self, plan, events, cancel):
        self._check()
        self._validate_execution_plan(plan)
        capacity = min(self.units["t660_2"].verified_frame_capacity(), MAX_EVENTS_PER_BLOCK)
        duration = self.capture_window["duration_s"]
        rates = {i: float(self.hf._get_node("double", f"/{self.hf.device_id}/demods/{i}/rate")) for i in (0, 2)}
        total_estimated = 0
        for index, block_events in enumerate(partition_frame_blocks(events, capacity=capacity)):
            frames = [self._event_timing(event)[0] for event in block_events]
            estimates = [estimate_capture_bytes(signal_paths=paths, grid_cols=cols, count=count+1,
                                                 duration_s=span, rate_sps=rate)
                         for paths, cols, count, span, rate in (
                             (("CH1.x", "CH1.y"), math.ceil(duration*rates[0])+1, len(block_events), duration, rates[0]),
                             (("DIO.timing",), math.ceil(duration*rates[2])+1, len(block_events), duration, rates[2]),
                             (("DIO.pump",), 4, sum(e.pump_enabled for e in block_events), 3/rates[2], rates[2]))]
            estimate = sum(item["estimated_bytes"] for item in estimates)
            total_estimated += estimate
            self.blocks.append({"block_index": index, "events": block_events, "frames": frames,
                                "daq": None, "estimated_bytes": estimate})
        if total_estimated > self.max_retained_bytes:
            raise AcquisitionCapacityError(f"Run retention estimate {total_estimated} exceeds configured {self.max_retained_bytes}-byte limit")
        if self.blocks:
            self._prepare_daq(self.blocks[0])
        write_json(self.store.path / "acquisition_preflight.json", {
            "settings": asdict(self.settings), "plan": plan.to_dict(), "capture_window": self.capture_window,
            "detector_mode": SINGLE_DETECTOR_MODE, "detector_input": DETECTOR_INPUT,
            "timing_recipe": {"id": "single_detector_phase_scan_v1",
                "probe_clock": self.probe_recipe, "reference_preflight": self.reference_recipe,
                "reference_preflight_readback": self.reference_preflight_readback,
                "frame_predivider": round(plan.frame_period_s * self.probe_rate_hz_readback),
                "frame_tables": [block["frames"] for block in self.blocks],
                "buffer_blank_and_sample_baseline": "Fire and Q-switch inhibited; Process Trigger retained",
                "normalization": "prior buffer blank, same sweep speed and HF2LI settings",
                "detector": "HF2LI CH1 SIG IN +; demodulator API index 0",
                "timing_stream": "demodulator API index 2; DIO17 pump sync, DIO21 Sweep Active, DIO22 markers"},
            **self._qualification_metadata(),
            "hf2li_settings_snapshot": self.hf_settings_snapshot,
            "capacity": [{"block_index": block["block_index"], "estimated_bytes": block["estimated_bytes"],
                          "allocation": block["daq"].capacity if block["daq"] is not None else None}
                         for block in self.blocks],
            "retention": {"maximum_events_per_block": MAX_EVENTS_PER_BLOCK,
                          "estimated_total_bytes": total_estimated, "configured_limit_bytes": self.max_retained_bytes,
                          "module_lifecycle": "one block at a time; configured and allocated before arming"},
            "tec_readiness_checks": self.preparation_tec_readiness_checks,
            "qcls": self.configured_qcls, "trigger": {"sweep_active": "DIO21 rising", "pump_sync": "DIO17 rising"}})
        return self.blocks

    def _prepare_daq(self, block):
        if block["daq"] is None:
            block["daq"] = FinitePhaseDAQ(self.hf, events=block["events"],
                duration_s=self.capture_window["duration_s"], pretrigger_s=self.capture_window["pretrigger_s"],
                capacity_verifier=self.capacity_verifier)
        return block["daq"]

    def _start_sweep_block(self, count, record):
        segment = self.segments[0]
        probe = self.units["t660_1"]
        probe.disable_channel("B")
        if not self.qcl.is_tuned():
            self.qcl.tune_to_wavenumber(segment["start_cm1"], qcl=segment["qcl"])
            self._wait(self.qcl.is_tuned, 45, "MIRcat did not tune for the next bounded block")
        self.qcl.turn_emission_on(approved_laser_safety_condition=self.authorized)
        if not self.qcl.is_emission_on():
            raise RuntimeError("MIRcat emission-enable readback did not verify")
        self.qcl.cancel_manual_tune()
        self._verify_external_trigger(segment, self.marker_interval, "after_manual_tune_cancel", record)
        record["mircat_internal_settings_before_block_setup"] = self._verify_qcl_pulse_settings(
            segment["qcl"], external_rate_hz=self.probe_rate_hz_readback)
        self._wait_for_stable_tecs("after_manual_tune_cancel", record=record)
        errors = []
        def start():
            try:
                self.qcl.start_sweep_scan(**segment, scan_rate_cm1_s=self.settings.scan_speed_cm1_s,
                                         repetitions=int(count))
            except Exception as exc:
                errors.append(exc)
        self._start_thread = Thread(target=start, daemon=True, name="phase-block-sdk-start")
        self._start_thread.start()
        deadline = monotonic() + 45
        while self._start_thread.is_alive():
            self._check(interlock=False)
            self._service_daq()
            if monotonic() > deadline:
                raise TimeoutError("MIRcat block setup did not return")
            self.cancel.wait(.02)
        self._start_thread.join()
        if errors:
            raise errors[0]
        self._verify_external_trigger(segment, self.marker_interval, "after_block_setup", record)
        self._observe_marker_channel(segment, record)
        record["mircat_internal_settings_after_block_setup"] = self._verify_qcl_pulse_settings(
            segment["qcl"], external_rate_hz=self.probe_rate_hz_readback)
        self._wait(self.qcl.get_scan_waiting_process_trigger, 30, "MIRcat did not wait for the external frame trigger")

    def capture_block(self, block, cancel):
        daq = None
        raw = {"block_index": block["block_index"], "events": [asdict(e) for e in block["events"]],
               "clockbase_hz": self.clockbase, "optical_valid": False,
               **self._detector_metadata(),
                "acquisition_settings": self._acquisition_metadata(),
                "hf2li_detector_settings": self.hf_detector_settings, "hf2li_device": self.hf.device_id,
                "scan_profile": {**self.segments[0], "marker_interval_cm1": self.marker_interval},
                "mircat_marker_channel_checks": []}
        try:
            self._check()
            timer = self.units["t660_2"]
            probe = self.units["t660_1"]
            # Preserve the PLL reference across blocks while inhibiting new
            # probe/frame edges during downstream preload and MIRcat setup.
            probe.disable_channel("B")
            probe.disable_channel("C")
            daq = self._prepare_daq(block)
            self._active_daq = daq
            table_started = monotonic()
            last_table_update = table_started-1.

            def table_progress(loaded, total):
                nonlocal last_table_update
                now = monotonic()
                raw["timing_table_load"] = {"acknowledged_frames": loaded, "physical_frames": total,
                                             "elapsed_s": now-table_started}
                if loaded in (0, total) or now-last_table_update >= 1.:
                    self.progress(f"Loading timing table: {loaded:,}/{total:,} frames; "
                                  f"{now-table_started:.1f} s elapsed")
                    last_table_update = now

            self.progress(f"Preparing timing-table upload for {len(block['frames']):,} scans…")
            raw["timing_table"] = timer.preload_frame_table(
                block["frames"], predivider=round(self.plan.frame_period_s * self.probe_rate_hz_readback),
                progress=table_progress, cancel_check=lambda: self._check(interlock=False))
            self._check(interlock=False)
            self.progress(f"Timing table loaded: {raw['timing_table']['physical_frame_count']:,} frames "
                          f"in {monotonic()-table_started:.1f} s. Preparing MIRcat sweep…")
            self._start_sweep_block(len(block["events"]), raw)
            # Arm after SDK tuning/setup has ended, while probe/frame outputs
            # remain inhibited, so setup transitions cannot fill sweep history.
            self.progress("Arming detector and timing capture; scan triggers remain inhibited…")
            daq.arm()
            self._input_integrity("before_frame_sequence")
            self._check()
            before = timer.get_shot_count()
            timer.start_frame_table()
            # The reference is already running. Enabling C only after the
            # engine is armed defines the first downstream frame opportunity.
            probe.enable_channel("B")
            probe.enable_channel("C")
            count = raw["timing_table"]["physical_frame_count"]
            sequence_started = monotonic()
            nominal_duration = count * self.plan.frame_period_s
            deadline = sequence_started + nominal_duration + 30
            last_scan_update = sequence_started
            last_scan_stage = "Scanning"
            self.progress(f"Scanning {len(block['events']):,} planned scans continuously: "
                          f"0.0 s elapsed; nominal sequence {nominal_duration:.1f} s")
            # Hardware owns every timing edge. Drain native records into bounded
            # host storage; serialize only after shutdown.
            while True:
                self._check()
                self._service_daq()
                state = timer.get_frames_status()
                if state == "ERROR":
                    raise AcquisitionIntegrityError("T660 frame engine reported an error")
                self._input_integrity("during_frame_sequence")
                if not math.isclose(self.hf.get_oscillator_frequency(0), self.probe_rate_hz_readback, rel_tol=.02):
                    raise AcquisitionIntegrityError("HF2LI reference does not follow the T660-1 DIO0 clock")
                scan_active = self.qcl.get_scan_status()["scan_in_progress"]
                if state == "DONE" and daq.expected_records_received() and not scan_active:
                    break
                now = monotonic()
                elapsed = now-sequence_started
                stage = ("Waiting for final sequence completion" if state == "DONE" or elapsed >= nominal_duration
                         else "Scanning")
                if now-last_scan_update >= 1. or stage != last_scan_stage:
                    self.progress(f"{stage}: {elapsed:.1f} s elapsed; nominal sequence {nominal_duration:.1f} s "
                                  f"(controller {state.lower()})")
                    last_scan_update, last_scan_stage = now, stage
                if now > deadline:
                    raise AcquisitionIntegrityError("Finite block did not complete its exact trigger/record count")
                cancel.wait(.02)
            # DONE may precede the final frame output edges. Allow the final
            # programmed widths to finish before readback and block completion.
            final_duration = self._event_timing(block["events"][-1])[1]
            deadline = monotonic() + final_duration
            while monotonic() < deadline:
                self._check()
                self._service_daq()
                cancel.wait(min(.02, max(0., deadline-monotonic())))
            after = timer.get_shot_count()
            raw["shot_counter_before"], raw["shot_counter_after"] = before, after
            if (after-before) % 2**32 != count:
                raise AcquisitionIntegrityError("T660 exact frame trigger count failed")
            daq.mark_sequence_complete()
            self._on_sequence_complete()
            self.progress("Sequence complete; retrieving retained detector and timing data…")
            raw["labone"] = daq.read()
            if block is self.blocks[-1]:
                # Normal timing completion is the safe-idle boundary. Conversion
                # of thousands of records must not extend laser emission.
                self._sequence_idle()
            else:
                probe.disable_channel("B")
                probe.disable_channel("C")
                timer.set_trigger_source("OFF")
                timer.command("STOP", expect_response=False)
                self.qcl.turn_emission_off()
            result = []
            self.progress("Validating retrieved native scan records…")
            last_processing_update = monotonic()
            for event, native in daq.records():
                self._check(interlock=False)
                native.update({key: raw[key] for key in
                               ("acquisition_settings", "hf2li_detector_settings", "hf2li_device",
                                "scan_profile", "mircat_marker_channel_checks")})
                spectrum = self._spectrum_from_native(native)
                self._validate_spectrum(event, spectrum)
                result.append((event, spectrum))
                now = monotonic()
                if now-last_processing_update >= 1.:
                    self.progress(f"Processing retrieved scans: {len(result):,}/{len(block['events']):,}")
                    last_processing_update = now
            self.progress(f"Processed {len(result):,} retrieved scans; preparing saved results…")
            daq.close()
            self._active_daq = None
            raw["optical_valid"] = True
            return raw, result
        except BaseException as exc:
            raw["optical_valid"] = False
            # Stop emission first, then salvage records without attempting another frame.
            try:
                self._safe_idle()
            except Exception as stop_exc:
                raw["safe_idle_error"] = str(stop_exc)
            try:
                raw["labone"] = (daq.read(partial=True) if daq is not None and daq.armed else
                                 {**(daq.raw if daq is not None else {}), "capture_not_started": True})
            except Exception as read_exc:
                raw["labone"] = daq.raw if daq is not None else {}
                raw["salvage_error"] = str(read_exc)
            raw["error"] = f"{type(exc).__name__}: {exc}"
            self.partial_blocks.append(raw)
            if daq is not None:
                daq.close()
            self._active_daq = None
            raise

    def _safe_idle(self):
        if self._safed:
            return
        self._safed = True
        errors = []
        for unit in self.units.values():
            try:
                self._stop_unit(unit)
            except Exception as exc:
                errors.append(f"{unit.name}: {exc}")
        if self.qcl is not None:
            for operation in (self.qcl.stop_scan_if_needed, self.qcl.turn_emission_off, self.qcl.disarm):
                try:
                    operation()
                except Exception as exc:
                    errors.append(str(exc))
        self._safe_errors = errors
        if errors:
            raise RuntimeError("; ".join(errors))

    def close(self):
        if self._closed:
            return
        self._closed = True
        errors = []
        try:
            self._safe_idle()
        except Exception as exc:
            errors.append(str(exc))
        errors.extend(getattr(self, "_safe_errors", []))
        for block in self.blocks:
            if block["daq"] is not None:
                try:
                    block["daq"].close()
                    errors.extend(block["daq"].raw.get("cleanup_errors", []))
                except Exception as exc:
                    errors.append(f"DAQ cleanup failed: {exc}")
        if self._start_thread is not None and self._start_thread.is_alive():
            self._start_thread.join(timeout=2)
            if self._start_thread.is_alive():
                errors.append("MIRcat SDK start call has not returned; safe state cannot be verified")
        if not (self._start_thread and self._start_thread.is_alive()):
            try:
                self._restore_instrument_settings()
            except Exception as exc:
                errors.append(f"Instrument settings restoration: {exc}")
        if self.qcl is not None and not (self._start_thread and self._start_thread.is_alive()):
            try:
                state = self.qcl.read_state().to_dict()
                if state.get("emission_on") or state.get("armed") or state.get("scan_in_progress"):
                    errors.append("MIRcat final readback is not safe idle")
                self.qcl.deinitialize()
            except Exception as exc:
                errors.append(str(exc))
        for unit in self.units.values():
            try:
                self._verify_unit(unit, {"trigger_source": "OFF", "channels": {c: {"enabled": False} for c in "ABCD"}})
                unit.close()
            except Exception as exc:
                errors.append(str(exc))
        if self.hf is not None:
            try:
                self.hf.close()
            except Exception as exc:
                errors.append(str(exc))
        if self.store is not None:
            if self.log is not None:
                (research_output_path(self.store.path / "commands.txt")).write_text(self.log.getvalue(), encoding="utf-8")
            write_json(self.store.path / "cleanup.json", {"safe_state_verified": not errors, "errors": errors})
        if errors:
            raise RuntimeError("; ".join(errors))
