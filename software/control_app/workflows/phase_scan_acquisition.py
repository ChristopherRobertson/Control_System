"""Finite phase-delay blocks; construction and planning never open hardware.

Complete timing tables and finite DAQ histories are prepared before emission.
Native blocks remain in memory until the runner consolidates the run on disk.
"""
from __future__ import annotations
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
from control_app.workflows.phase_scan_data import HF2_PRESET, QCL_CURRENT_MA, write_json
from control_app.workflows.phase_scan import build_phase_scan_plan, derive_capture_window, partition_frame_blocks
from control_app.workflows.phase_scan_native import spectrum_from_sweep
from control_app.workflows.phase_scan_labone import FinitePhaseDAQ, AcquisitionIntegrityError
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
    """A frame schedules Fire, Q-switch and Process Trigger with signed delay."""
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


class LivePhaseScanAcquirer:
    def __init__(self, *, config_path=None, laser_factory=None, hf_factory=None, t660_factory=None,
                 tec_ready_stability_s=5.0, qualified_trajectory=None, qualified_sweep_active_s=None,
                 capacity_verifier=None, promoted_bundle=None):
        self.config_path = config_path
        self.laser_factory = laser_factory or MircatService.from_config
        self.hf_factory = hf_factory or HF2LIService.from_config
        self.t660_factory = t660_factory or T660Service.from_config
        self.qualified_trajectory = qualified_trajectory
        self.qualified_sweep_active_s = qualified_sweep_active_s
        self.capacity_verifier = capacity_verifier
        self.promoted_bundle = promoted_bundle
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
            if predicate():
                return
            if monotonic() >= deadline:
                raise TimeoutError(description)
            self.cancel.wait(.05)

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

    def _verify_qcl_pulse_settings(self, qcl, *, external_rate_hz):
        """Verify internal laser settings without treating them as the pulse clock."""
        actual = {"qcl": int(qcl), "settings_role": "mircat_internal",
                  "current_ma": self.qcl.get_qcl_current(qcl),
                  "pulse_rate_hz": self.qcl.get_qcl_pulse_rate(qcl),
                  "pulse_width_ns": self.qcl.get_qcl_pulse_width(qcl)}
        for key, target in (
            ("current_ma", QCL_CURRENT_MA),
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
        for operation in (lambda: unit.set_trigger_source("OFF"), lambda: unit.command("STOP", expect_response=False),
                          *[lambda c=c: unit.disable_channel(c) for c in "ABCD"]):
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
        if errors:
            raise RuntimeError("; ".join(errors))


    def _input_integrity(self, context):
        status = {}
        for index in (0, 1):
            path = f"/{self.hf.device_id}/status/flags/adcclip/{index}"
            value = self.hf._get_node("int", path)
            status[path] = value
            if value:
                raise AcquisitionIntegrityError(f"HF2LI input {index+1} clipping at {context}")
        return status

    def prepare(self, settings, store, cancel):
        if not self.authorized:
            raise PermissionError("Confirm this acquisition before laser operation")
        self.settings, self.store, self.cancel = settings, store, cancel
        self.resolve_plan(build_phase_scan_plan(settings))
        self.capture_window = derive_capture_window(self.qualified_sweep_active_s)
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
            # Preparation inhibits sources; final safe-idle is a single, separate action.
            unit.set_trigger_source("OFF")
        self.probe_recipe = self.units["t660_1"].configure_continuous_clock(
            frequency_hz=settings.probe_repetition_rate_hz, pulse_width_ns=settings.probe_pulse_width_ns)
        probe = self._verify_unit(self.units["t660_1"], self.probe_recipe)
        self.probe_rate_readback_native = probe["queries"]["synth_frequency"]
        self.probe_rate_hz_readback = frequency_hz(self.probe_rate_readback_native["response"])
        self.qcl = self.laser_factory(config_path=self.config_path, command_log=self.log)
        self.qcl.initialize()
        self.qcl.stop_scan_if_needed()
        self.qcl.turn_emission_off()
        self.qcl.cancel_manual_tune()
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
                duty * 100 > limits["max_duty_cycle"] + 1e-6 or not minimum <= QCL_CURRENT_MA <= maximum):
            raise RuntimeError("MIRcat internal parameters exceed QCL readback limits")
        self.qcl.set_qcl_pulse_params(qcl=number, pulse_rate_hz=settings.mircat_internal_repetition_rate_hz,
                                     pulse_width_ns=settings.mircat_internal_pulse_width_ns, current_ma=QCL_CURRENT_MA)
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
        saved = self.hf.load_preset(HF2_PRESET)
        copied = deepcopy(saved.settings)
        timing_requested = min(200_000., max(5000., 2e6/settings.phase_delay_us))
        for demod in copied["demodulators"]:
            if demod["index"] == 2:
                demod["rate_sps"] = timing_requested
        copied["demodulators"].extend({"index": i, "enable": False} for i in (1, 4, 5))
        copied["pll"]["freqcenter_hz"] = self.probe_rate_hz_readback
        self.preset = HF2LIPreset(saved.name, copied)
        self.hf.apply_preset(self.preset)
        snapshot = self.hf.export_settings_snapshot(preset=self.preset)
        self.hf_settings_snapshot = snapshot
        if snapshot["read_errors"]:
            raise RuntimeError("HF2LI acquisition settings could not all be read back")
        for index, role in ((0, "sample"), (3, "reference")):
            requested = next(float(item["rate_sps"]) for item in copied["demodulators"] if item["index"] == index)
            actual = float(snapshot["nodes"][f"/{self.hf.device_id}/demods/{index}/rate"]["value"])
            if not math.isclose(actual, requested, rel_tol=1e-3, abs_tol=1e-3):
                raise RuntimeError(f"HF2LI {role} detector rate readback differs from the preset")
        self.clockbase = float(self.hf.get_clockbase())
        self.timing_rate = float(self.hf._get_node("double", f"/{self.hf.device_id}/demods/2/rate"))
        width_us = max(1, min(500, int(self.marker_interval/settings.scan_speed_cm1_s*1e6/4)))
        if width_us * 1e-6 < 2/self.timing_rate:
            raise RuntimeError("Timing readback cannot resolve the configured wavelength marker width")
        if self.qcl.set_wavelength_trigger_pulse_width_us(width_us) != width_us:
            raise RuntimeError("MIRcat wavelength marker width readback mismatch")
        status = self._input_integrity("preflight")
        stable = {path: value for path, value in snapshot["nodes"].items()
                  if "/sigins/" in path or ("/demods/" in path and "/demods/2/" not in path)}
        return {"hf2li_device": snapshot["device_id"], "hf2li_detector_settings": stable,
                "qcls": self.configured_qcls, "segments": self.segments,
                "t660_1_probe_rate_hz_readback": self.probe_rate_hz_readback,
                "capture_window": self.capture_window, "input_status": status}

    def prepare_blocks(self, plan, events, cancel):
        self._check()
        if not plan.calibrated:
            raise RuntimeError("Finite acquisition cannot use an uncalibrated preview plan")
        capacity = self.units["t660_2"].verified_frame_capacity()
        for index, block_events in enumerate(partition_frame_blocks(events, capacity=capacity)):
            frames = [event_timing(event)[0] for event in block_events]
            daq = FinitePhaseDAQ(self.hf, events=block_events, duration_s=self.capture_window["duration_s"],
                                pretrigger_s=self.capture_window["pretrigger_s"], capacity_verifier=self.capacity_verifier)
            self.blocks.append({"block_index": index, "events": block_events, "frames": frames, "daq": daq})
        write_json(self.store.path / "acquisition_preflight.json", {
            "settings": asdict(self.settings), "plan": plan.to_dict(), "capture_window": self.capture_window,
            "calibrated_trajectory": self.qualified_trajectory,
            "qualified_sweep_active_s": self.qualified_sweep_active_s,
            "promoted_bundle_id": getattr(self.promoted_bundle, "bundle_id", None),
            "hf2li_settings_snapshot": self.hf_settings_snapshot,
            "capacity": [block["daq"].capacity for block in self.blocks],
            "tec_readiness_checks": self.preparation_tec_readiness_checks,
            "qcls": self.configured_qcls, "trigger": {"sweep_active": "DIO21 rising", "pump_sync": "DIO17 rising"}})
        return self.blocks

    def _start_sweep_block(self, count, record):
        segment = self.segments[0]
        probe = self.units["t660_1"]
        if self._clock_started:
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
            if monotonic() > deadline:
                raise TimeoutError("MIRcat block setup did not return")
            self.cancel.wait(.02)
        self._start_thread.join()
        if errors:
            raise errors[0]
        self._verify_external_trigger(segment, self.marker_interval, "after_block_setup", record)
        record["mircat_internal_settings_after_block_setup"] = self._verify_qcl_pulse_settings(
            segment["qcl"], external_rate_hz=self.probe_rate_hz_readback)
        self._wait(self.qcl.get_scan_waiting_process_trigger, 30, "MIRcat did not wait for the external frame trigger")
        if self._clock_started:
            probe.enable_channel("B")

    def capture_block(self, block, cancel):
        daq = block["daq"]
        raw = {"block_index": block["block_index"], "events": [asdict(e) for e in block["events"]],
               "clockbase_hz": self.clockbase, "optical_valid": False}
        try:
            self._check()
            timer = self.units["t660_2"]
            raw["timing_table"] = timer.preload_frame_table(block["frames"], predivider=600_000)
            daq.arm()
            self._start_sweep_block(len(block["events"]), raw)
            self._input_integrity("before_frame_sequence")
            self._check()
            before = timer.get_shot_count()
            timer.start_frame_table()
            if not self._clock_started:
                self.units["t660_1"].start_continuous_clock()
                self._clock_started = True
            count = raw["timing_table"]["physical_frame_count"]
            deadline = monotonic() + count * self.plan.frame_period_s + 30
            # Timing is exclusively in the preloaded hardware. Only status and
            # clipping/interlocks are checked here; no capture reads or writes.
            while True:
                self._check()
                state = timer.get_frames_status()
                if state == "ERROR":
                    raise AcquisitionIntegrityError("T660 frame engine reported an error")
                self._input_integrity("during_frame_sequence")
                if not math.isclose(self.hf.get_oscillator_frequency(0), self.probe_rate_hz_readback, rel_tol=.02):
                    raise AcquisitionIntegrityError("HF2LI reference does not follow the T660-1 DIO0 clock")
                scan_active = self.qcl.get_scan_status()["scan_in_progress"]
                if state == "DONE" and daq.expected_records_received() and not scan_active:
                    break
                if monotonic() > deadline:
                    raise AcquisitionIntegrityError("Finite block did not complete its exact trigger/record count")
                cancel.wait(.02)
            # DONE may precede the final frame output edges. Allow the final
            # programmed widths to finish before readback and block completion.
            final_duration = event_timing(block["events"][-1])[1]
            deadline = monotonic() + final_duration
            while monotonic() < deadline:
                self._check()
                cancel.wait(min(.02, max(0., deadline-monotonic())))
            after = timer.get_shot_count()
            raw["shot_counter_before"], raw["shot_counter_after"] = before, after
            if (after-before) % 2**32 != count:
                raise AcquisitionIntegrityError("T660 exact frame trigger count failed")
            daq.mark_sequence_complete()
            raw["labone"] = daq.read()
            if block is self.blocks[-1]:
                # Normal timing completion is the safe-idle boundary. Conversion
                # of thousands of records must not extend laser emission.
                self._safe_idle()
            raw["optical_valid"] = True
            result = []
            for event, native in daq.records():
                origin = int(native["sweep_event_tick"])
                spectrum = spectrum_from_sweep(native, start_cm1=self.segments[0]["start_cm1"],
                    stop_cm1=self.segments[0]["stop_cm1"], targets_cm1=self.targets, origin_tick=origin,
                    pump_tick=native["pump_event_tick"], pump_reference="electrical_sync")
                result.append((event, spectrum))
            daq.close()
            return raw, result
        except BaseException as exc:
            # Stop emission first, then salvage records without attempting another frame.
            try:
                self._safe_idle()
            except Exception as stop_exc:
                raw["safe_idle_error"] = str(stop_exc)
            raw["labone"] = daq.read(partial=True)
            raw["error"] = f"{type(exc).__name__}: {exc}"
            self.partial_blocks.append(raw)
            daq.close()
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
            block["daq"].close()
            errors.extend(block["daq"].raw.get("cleanup_errors", []))
        if self._start_thread is not None and self._start_thread.is_alive():
            self._start_thread.join(timeout=2)
            if self._start_thread.is_alive():
                errors.append("MIRcat SDK start call has not returned; safe state cannot be verified")
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
                (self.store.path / "commands.txt").write_text(self.log.getvalue(), encoding="utf-8")
            write_json(self.store.path / "cleanup.json", {"safe_state_verified": not errors, "errors": errors})
        if errors:
            raise RuntimeError("; ".join(errors))
