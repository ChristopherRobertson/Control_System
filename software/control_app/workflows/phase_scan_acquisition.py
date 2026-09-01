"""Live first-light Phase Scan adapter. Importing/constructing it never opens hardware.

The user's per-operation GUI confirmation authorizes emission. Hardware limits,
interlocks and readbacks remain mandatory. This workflow does not promote a
calibration bundle or modify the campaign sequence. Native data is retained even
if timing/optical interpretation fails.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from threading import Thread
from time import monotonic
import math

import numpy as np

from control_app.devices.hf2li_service import HF2LIService, HF2LIPreset
from control_app.devices.mircat_service import MircatService, PULSE_MODE_EXTERNAL_TRIGGER, PROC_TRIG_MODE_EXTERNAL, UNITS_CM1
from control_app.devices.t660_service import T660Service
from control_app.workflows.phase_scan_data import Spectrum, HF2_PRESET, QCL_CURRENT_MA, write_json, save_native
from control_app.workflows.phase_scan_native import demodulator_samples, high_intervals, pump_reference_tick, spectrum_from_sweep
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


def event_timing(event):
    """One REM event on T660-1 schedules Fire, Q-switch and Process in hardware.

    Surelite nominal fire-to-light 180 us, Q-switch-to-light 170 ns, as in the
    installed alignment settings. These are scheduling values, not corrections
    applied to measured time. T660-2 only provides the continuous probe train.
    """
    phase_s = float(event.phase_delay_us or 0) * 1e-6
    pump_s = .001 + max(.000180, -phase_s)
    scan_s = pump_s + phase_s if event.pump_enabled else .001
    def pulse(delay_s, width_s):
        return {"enabled": True, "delay": f"{delay_s:.12f}s", "width": f"{width_s:.12f}s",
                "polarity": "negative", "termination": "50OHM"}
    return {"stop_first": True, "trigger_source": "REM", "gate_mode": 0, "burst_enabled": False,
            "force_eod": True,
            "channels": {"A": pulse(pump_s-.000180, .000010) if event.pump_enabled else {"enabled": False},
                         "B": pulse(pump_s-.000000170, .000010) if event.pump_enabled else {"enabled": False},
                         "C": pulse(scan_s, .010), "D": {"enabled": False}}}, max(pump_s, scan_s+.010)


class LivePhaseScanAcquirer:
    def __init__(self, *, config_path=None, laser_factory=None, hf_factory=None, t660_factory=None):
        self.config_path = config_path
        self.laser_factory = laser_factory or MircatService.from_config
        self.hf_factory = hf_factory or HF2LIService.from_config
        self.t660_factory = t660_factory or T660Service.from_config
        self.authorized = False
        self.qcl = self.hf = self.log = self.store = None
        self.units = {}
        self.cancel = None
        self.progress = lambda message: None
        self._closed = False
        self._start_thread = None
        self.warnings = []
        self._last_pump_latest = None

    def authorize(self, approved):
        self.authorized = approved is True

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

    def _verify_unit(self, unit, recipe):
        readback = unit.read_active_settings()
        mismatches = TimingRecipeManager._compare_readback({unit.name: recipe}, {unit.name: readback})
        if mismatches:
            raise RuntimeError(f"{unit.name} timing readback mismatch: {mismatches}")
        return readback

    def prepare(self, settings, store, cancel):
        if not self.authorized:
            raise PermissionError("Confirm this acquisition in the GUI before laser operation")
        self.settings, self.store, self.cancel = settings, store, cancel
        self.log = (store.path / "commands.txt").open("x", encoding="utf-8")
        self._check(interlock=False)
        for name in ("t660_1", "t660_2"):
            unit = self.t660_factory(name, config_path=self.config_path, command_log=self.log)
            self.units[name] = unit
            unit.connect()
            identity = unit.identify()
            expected = str(unit.device_config["serial_number"])
            if expected not in [part.strip() for part in identity.split(",")]:
                raise RuntimeError(f"Unexpected {name} identity: {identity}")
            self._stop_unit(unit)
        self.qcl = self.laser_factory(config_path=self.config_path, command_log=self.log)
        self.qcl.initialize()
        self.qcl.stop_scan_if_needed()
        self.qcl.turn_emission_off()
        self.qcl.cancel_manual_tune()
        if self.qcl.is_interlock_set() and self.qcl.is_key_switch_set():
            before_error = self.qcl.get_system_error_word()
            if before_error:
                cleared = self.qcl.clear_system_error()
                write_json(store.path / "mircat_error_clear.json", {"before": before_error, "clear_return": cleared,
                           "after": self.qcl.get_system_error_word()})
        self._check()
        ranges = [self.qcl.get_qcl_tuning_range(i) for i in range(1, self.qcl.get_num_installed_qcls()+1)]
        self.segments = channel_segments(settings.start_wavenumber_cm1, settings.stop_wavenumber_cm1, ranges)
        configured_qcls = []
        for number in sorted({s["qcl"] for s in self.segments}):
            limits = self.qcl.get_qcl_pulse_limits(number)
            minimum, maximum = self.qcl.get_qcl_current_limits(number)
            duty = settings.probe_repetition_rate_hz * settings.probe_pulse_width_ns * 1e-9
            if (settings.probe_repetition_rate_hz > limits["max_pulse_rate_hz"] or
                settings.probe_pulse_width_ns > limits["max_pulse_width_ns"] or
                duty*100 > limits["max_duty_cycle"] + 1e-6 or not minimum <= QCL_CURRENT_MA <= maximum):
                raise ValueError(f"Requested probe parameters exceed QCL {number} readback limits")
            self.qcl.set_qcl_pulse_params(qcl=number, pulse_rate_hz=settings.probe_repetition_rate_hz,
                                         pulse_width_ns=settings.probe_pulse_width_ns, current_ma=QCL_CURRENT_MA)
            actual = {"qcl": number, "current_ma": self.qcl.get_qcl_current(number),
                      "pulse_rate_hz": self.qcl.get_qcl_pulse_rate(number), "pulse_width_ns": self.qcl.get_qcl_pulse_width(number)}
            for key, target in (("current_ma", QCL_CURRENT_MA), ("pulse_rate_hz", settings.probe_repetition_rate_hz),
                                ("pulse_width_ns", settings.probe_pulse_width_ns)):
                if not math.isclose(actual[key], target, rel_tol=1e-5, abs_tol=1e-3):
                    raise RuntimeError(f"QCL {number} {key} readback does not match the requested value")
            configured_qcls.append(actual)
        first = self.segments[0]
        self.qcl.set_external_sweep_trigger_params(start_cm1=first["start_cm1"], stop_cm1=first["stop_cm1"],
                                                  wavelength_trigger_interval_cm1=5, external_process_trigger=False)
        self._check()
        self.qcl.arm()
        self.progress("Waiting for MIRcat temperature readiness…")
        self._wait(self.qcl.are_tecs_ready, 120, "MIRcat temperatures did not become ready")
        self.qcl.tune_to_wavenumber(first["start_cm1"], qcl=first["qcl"])
        self._wait(self.qcl.is_tuned, 45, "MIRcat did not tune to the requested start")
        pulse = {"enabled": True, "delay": "0ns", "width": f"{settings.probe_pulse_width_ns:.9g}ns",
                 "polarity": "positive", "termination": "50OHM"}
        self.probe_recipe = {"stop_first": True, "trigger_source": "SYN", "frames_engine": "OFF",
                             "gate_mode": 0, "burst_enabled": False, "clock": {"frequency": f"{settings.probe_repetition_rate_hz:.9g}Hz"},
                             "force_eod": True, "channels": {"A": pulse, "B": {**pulse, "enabled": False},
                                                              "C": {"enabled": False}, "D": {"enabled": False}}}
        probe = self.units["t660_2"]
        probe.apply_recipe(self.probe_recipe)
        write_json(store.path / "t660_probe_prepared.json", self._verify_unit(probe, self.probe_recipe))
        probe.command("START", expect_response=False)
        self.hf = self.hf_factory(config_path=self.config_path, command_log=self.log)
        self.hf.connect()
        saved = self.hf.load_preset(HF2_PRESET)
        # Detector filters/rates are retained. Only timing-stream rate is raised
        # to observe short markers; nonparticipating streams are disabled.
        settings_copy = deepcopy(saved.settings)
        self.timing_rate_requested = min(200_000., max(5000., 2e6/settings.phase_delay_us))
        for demod in settings_copy["demodulators"]:
            if demod["index"] == 2:
                demod["rate_sps"] = self.timing_rate_requested
        settings_copy["demodulators"].extend({"index": i, "enable": False} for i in (1, 4, 5))
        settings_copy["pll"]["freqcenter_hz"] = settings.probe_repetition_rate_hz
        self.preset = HF2LIPreset(saved.name, settings_copy)
        write_json(store.path / "hf2li_before.json", self.hf.export_settings_snapshot(preset=self.preset))
        self.hf.apply_preset(self.preset)
        self._wait(lambda: math.isclose(self.hf.get_oscillator_frequency(0), settings.probe_repetition_rate_hz, rel_tol=.02),
                   10, "HF2LI is not following the probe reference; check T660-2 CHA → DIO0")
        snapshot = self.hf.export_settings_snapshot(preset=self.preset)
        write_json(store.path / "hf2li_configured.json", snapshot)
        if snapshot["read_errors"]:
            raise RuntimeError("HF2LI acquisition settings could not all be read back")
        self.clockbase = self.hf.get_clockbase()
        if not self.clockbase > 0:
            raise ValueError("Invalid HF2LI device clockbase")
        self.warnings = ["First-light workflow: no optical timing or wavelength qualification has been applied.",
                         "Saved detector filters/rates retained; timing demodulator rate is derived from the phase step."]
        if len(self.segments) > 1:
            self.warnings.append("Multiple QCL sweeps contain real return/settling gaps; unsupported time regions remain blank.")
        write_json(store.path / "acquisition_preflight.json", {"qcls": configured_qcls, "segments": self.segments,
                   "timing_stream_requested_sps": self.timing_rate_requested, "clockbase_hz": self.clockbase,
                   "warnings": self.warnings, "settings": asdict(settings), "calibration_status": "NOT_QUALIFIED"})
        # Exclude live PLL tracker values from background equality; frequency is
        # separately checked against the requested reference above.
        stable = {path: value for path, value in snapshot["nodes"].items()
                  if "/sigins/" in path or ("/demods/" in path and "/demods/2/" not in path)}
        return {"hf2li_device": snapshot["device_id"], "hf2li_detector_settings": stable,
                "qcls": configured_qcls, "segments": self.segments}

    def _poll(self, record, seconds=.02, *, interlock=True):
        self._check(interlock=interlock)
        record["native_chunks"].append(self.hf.read_acquisition(seconds))
        self._check(interlock=interlock)

    def _capture_segment(self, event, segment, record):
        settings = self.settings
        # Divide the span into exact target intervals; keep pulses separated at
        # high speed. Do not stretch wavelength pulses across adjacent targets.
        span = abs(segment["stop_cm1"]-segment["start_cm1"])
        count = max(1, math.ceil(span / 5))
        interval = span / count
        targets = np.linspace(segment["start_cm1"], segment["stop_cm1"], count+1)
        record["expected_marker_wavenumbers_cm1"] = targets
        trigger = self.qcl.set_external_sweep_trigger_params(start_cm1=segment["start_cm1"], stop_cm1=segment["stop_cm1"],
                    wavelength_trigger_interval_cm1=interval, external_process_trigger=True)
        record["trigger_readback"] = trigger
        for name, expected in (("pulse_mode", PULSE_MODE_EXTERNAL_TRIGGER), ("process_trigger_mode", PROC_TRIG_MODE_EXTERNAL), ("units", UNITS_CM1)):
            if trigger[name] != expected:
                raise RuntimeError(f"MIRcat {name} readback is not the requested external trigger mode")
        for name, expected in (("start", segment["start_cm1"]), ("stop", segment["stop_cm1"]), ("interval", interval)):
            if not math.isclose(trigger[name], expected, abs_tol=.001, rel_tol=1e-6):
                raise RuntimeError(f"MIRcat {name} readback mismatch")
        width_us = max(1, min(500, int(interval/settings.scan_speed_cm1_s*1e6/4)))
        if self.qcl.set_wavelength_trigger_pulse_width_us(width_us) != width_us:
            raise RuntimeError("MIRcat wavelength-marker pulse width readback mismatch")
        record["marker_pulse_width_us"] = width_us
        timing, event_duration = event_timing(event)
        timer = self.units["t660_1"]
        timer.apply_recipe(timing)
        record["timing_recipe"] = timing
        record["timing_readback"] = self._verify_unit(timer, timing)
        timer.command("START", expect_response=False)  # REM never starts a periodic train.
        shot_before = timer.get_shot_count()
        self._check()
        self.hf.start_acquisition(demodulators=(0, 2, 3))
        try:
            self._poll(record, .05)
            self.qcl.turn_emission_on(approved_laser_safety_condition=self.authorized)
            self._check()
            if not self.qcl.is_emission_on():
                raise RuntimeError("MIRcat emission-enable readback did not verify")
            record["optical_valid"] = True
            self.units["t660_2"].enable_channel("B")
            errors = []
            def start():
                try:
                    self.qcl.start_sweep_scan(**segment, scan_rate_cm1_s=settings.scan_speed_cm1_s, repetitions=1)
                except Exception as exc:
                    errors.append(exc)
            self._start_thread = Thread(target=start, daemon=True, name="phase-scan-sdk-start")
            self._start_thread.start()
            deadline = monotonic()+45
            while self._start_thread.is_alive():
                # Keep polling HF2 while the SDK prepares the sweep. Do not make
                # concurrent status queries to the SDK during StartSweepScan.
                self._poll(record, interlock=False)
                if monotonic() > deadline:
                    raise TimeoutError("MIRcat StartSweepScan did not return")
            self._start_thread.join()
            if errors:
                raise errors[0]
            deadline = monotonic()+30
            while not self.qcl.get_scan_waiting_process_trigger():
                self._poll(record)
                if monotonic() > deadline:
                    raise TimeoutError("MIRcat never reported waiting for its external process trigger")
            self._check()
            if event.pump_enabled and self._last_pump_latest is not None:
                while monotonic() < self._last_pump_latest + settings.rest_period_s:
                    self._poll(record)
            timer.fire_remote_trigger()  # The only pump-producing call in this event.
            fired_at = monotonic()
            if event.pump_enabled:
                # Conservative host upper bound; the actual reference timestamp
                # remains in native device ticks and is used for reconstruction.
                self._last_pump_latest = fired_at + event_duration
            deadline = fired_at + max(10, span/settings.scan_speed_cm1_s + event_duration + 5)
            while True:
                self._poll(record)
                state = self.qcl.get_scan_status()
                record["scan_status_final"] = state
                timing_samples = demodulator_samples(record, 2)
                completed = high_intervals(timing_samples["timestamp"],
                                           (timing_samples["dio"].astype(np.uint32) & (1 << 21)) != 0)
                if len(completed) > 1:
                    raise RuntimeError("More than one QCL sweep was observed after a single process trigger")
                if completed and monotonic()-fired_at >= event_duration+.03:
                    break
                if monotonic() > deadline:
                    raise TimeoutError("MIRcat sweep did not finish after one process trigger; native data retained")
            self._poll(record, .05)
            shot_after = timer.get_shot_count()
            record["shot_counter_before"], record["shot_counter_after"] = shot_before, shot_after
            if (shot_after-shot_before) % 2**32 != 1:
                raise RuntimeError("T660-1 did not report exactly one event")
        finally:
            # Prevent any additional Fire/Q-switch event, then close the probe gate.
            timer.set_trigger_source("OFF")
            timer.command("STOP", expect_response=False)
            self.units["t660_2"].disable_channel("B")
            self.qcl.stop_scan_if_needed()
            self.qcl.turn_emission_off()
            self.hf.stop_acquisition()
        return targets

    def capture(self, event, cancel):
        from control_app.workflows.phase_scan import PhaseScanEvent
        self._check()
        raw = {"optical_valid": False, "clockbase_hz": self.clockbase, "segments": [], "event": asdict(event)}
        spectra = []
        pump_tick = origin = None
        try:
            for index, segment in enumerate(self.segments):
                self.progress(f"Acquiring QCL {segment['qcl']}: {segment['start_cm1']:g} → {segment['stop_cm1']:g} cm⁻¹")
                part = {"clockbase_hz": self.clockbase, "native_chunks": [], **segment}
                raw["segments"].append(part)
                # Subsequent QCL segments advance the probe only, never fire an extra pump.
                segment_event = event if index == 0 else PhaseScanEvent(event.scan_index, event.repetition, None, False, None)
                targets = self._capture_segment(segment_event, segment, part)
                if origin is None:
                    origin = int(demodulator_samples(part, 2)["timestamp"][0])
                if index == 0 and event.pump_enabled:
                    pump_tick = pump_reference_tick(part, self.settings.pump_reference, self.settings.pump_threshold_v)
                spectrum = spectrum_from_sweep(part, start_cm1=segment["start_cm1"], stop_cm1=segment["stop_cm1"],
                            targets_cm1=targets, origin_tick=origin, pump_tick=pump_tick, pump_reference=self.settings.pump_reference)
                spectra.append(spectrum)
            # Remove only overlapping endpoint samples, preserving acquisition order.
            direction = 1 if self.settings.stop_wavenumber_cm1 > self.settings.start_wavenumber_cm1 else -1
            combined = {name: [] for name in ("wavenumber_cm1", "sample_r", "reference_r", "sample_time_s")}
            ids, last = [], None
            for index, spectrum in enumerate(spectra):
                selected = np.ones(len(spectrum.wavenumber_cm1), dtype=bool) if last is None else (spectrum.wavenumber_cm1-last)*direction > 1e-7
                if not selected.any():
                    continue
                for name in combined:
                    combined[name].append(np.asarray(getattr(spectrum, name))[selected])
                ids.append(np.full(selected.sum(), index, dtype=np.int32))
                last = spectrum.wavenumber_cm1[selected][-1]
            provisional = any(s.metadata["provisional"] for s in spectra)
            metadata = {**spectra[0].metadata, "wavenumber_basis": "nominal_sweep_bounds" if provisional else "measured",
                        "provisional": provisional, "segment_metadata": [s.metadata for s in spectra],
                        "warnings": sorted(set(self.warnings + [w for s in spectra for w in s.metadata["warnings"]]))}
            result = Spectrum(**{name: np.concatenate(parts) for name, parts in combined.items()},
                       pump_time_s=spectra[0].pump_time_s, metadata=metadata, segment_id=np.concatenate(ids)).validate()
            raw["optical_valid"] = True
            return raw, result
        except Exception as exc:
            raw["error"] = f"{type(exc).__name__}: {exc}"
            save_native(self.store.path / "partial" / f"scan_{event.scan_index:07d}.npz", raw)
            raise

    @staticmethod
    def _stop_unit(unit):
        errors = []
        for operation in (lambda: unit.set_trigger_source("OFF"), lambda: unit.command("STOP", expect_response=False),
                          *[lambda c=c: unit.disable_channel(c) for c in "ABCD"]):
            try:
                operation()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError("; ".join(errors))

    def close(self):
        if self._closed:
            return
        self._closed = True
        errors = []
        def attempt(label, operation):
            try:
                return operation()
            except Exception as exc:
                errors.append(f"{label}: {exc}")
        for unit in self.units.values():
            attempt(unit.name+" stop", lambda u=unit: self._stop_unit(u))
        if self.qcl is not None:
            for label, operation in (("scan stop", self.qcl.stop_scan_if_needed), ("emission off", self.qcl.turn_emission_off),
                                     ("disarm", self.qcl.disarm)):
                attempt(label, operation)
            if self._start_thread is not None and self._start_thread.is_alive():
                self._start_thread.join(timeout=2)
                if self._start_thread.is_alive():
                    errors.append("MIRcat SDK start call has not returned; safe state cannot be verified")
            def verify_laser():
                state = self.qcl.read_state().to_dict()
                write_json(self.store.path / "mircat_final.json", state)
                if self.qcl.is_emission_on() or self.qcl.is_laser_armed() or self.qcl.get_scan_status()["scan_in_progress"]:
                    raise RuntimeError("MIRcat is not stopped, disarmed and emission OFF")
            attempt("laser final readback", verify_laser)
        for unit in self.units.values():
            def verify(u=unit):
                readback = self._verify_unit(u, {"trigger_source": "OFF", "channels": {c: {"enabled": False} for c in "ABCD"}})
                write_json(self.store.path / f"{u.name}_final.json", readback)
            attempt(unit.name+" final readback", verify)
            attempt(unit.name+" close", unit.close)
        if self.hf is not None:
            attempt("HF2LI stop", self.hf.stop_acquisition)
            # Deliberately leave the selected debugging preset configured. No
            # claim is made that the previous PLL tracker state was restored.
            if hasattr(self, "preset"):
                attempt("HF2LI final readback", lambda: write_json(self.store.path / "hf2li_final.json", self.hf.export_settings_snapshot(preset=self.preset)))
            attempt("HF2LI close", self.hf.close)
        if self.qcl is not None and not (self._start_thread is not None and self._start_thread.is_alive()):
            attempt("MIRcat deinitialize", self.qcl.deinitialize)
        if self.store is not None:
            attempt("save cleanup", lambda: write_json(self.store.path / "cleanup.json", {"safe_state_verified": not errors, "errors": list(errors)}))
        if self.log is not None:
            self.log.close()
        if errors:
            raise RuntimeError("; ".join(errors))
