"""Maintained single-detector experiment with one deferred-read sequence.

The execution follows the retained continuous phase experiments. Controller
marker readbacks establish wavelength coordinates and DIO17 establishes the
electrical pump reference; neither is an optical-arrival calibration.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
import math
from threading import Thread
from time import monotonic

from control_app.devices.hf2li_service import HF2LIPreset
from control_app.devices.t660_service import CHANNEL_EDGES, _seconds_value
from control_app.workflows.phase_scan_acquisition import LivePhaseScanAcquirer
from control_app.workflows.phase_scan_data import DETECTOR_INPUT, SINGLE_DETECTOR_MODE, write_json
from control_app.workflows.phase_scan_labone import (
    AcquisitionCapacityError, FinitePhaseDAQ,
)
from control_app.workflows.single_detector_marker_identity import controller_marker_identity


FIRE_TO_QSWITCH_S = 250e-6


def available_host_memory_bytes():
    """Current physical memory available to the host, without budget multipliers."""
    import os
    if os.name == "nt":
        import ctypes
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in
                ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise AcquisitionCapacityError("Available memory could not be checked; retry acquisition")
        return status.available
    return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")


def regular_event_timing(event, fire_to_qswitch_s=FIRE_TO_QSWITCH_S):
    """Preserve signed Process Trigger delays when a matched blank inhibits FIRE.

    The baseline has no phase index and starts at 1 ms. Every later blank and
    sample record has the same Process Trigger delay at the same sequence index.
    """
    phase_s = float(event.phase_delay_us or 0.) * 1e-6
    qswitch_s = .001 + max(fire_to_qswitch_s, -phase_s)
    scan_s = qswitch_s + phase_s if event.phase_index is not None else .001
    def pulse(delay, width, enabled=True):
        return {"enabled": enabled, "delay": f"{delay:.12f}s", "width": f"{width:.12f}s",
                "polarity": "negative", "termination": "50OHM"}
    channels = {"A": pulse(qswitch_s-fire_to_qswitch_s, .000010, event.pump_enabled),
                "B": pulse(qswitch_s, .000010, event.pump_enabled),
                "C": pulse(scan_s, .010), "D": pulse(0., .000010, False)}
    return {"channels": channels}, max(qswitch_s+.000010, scan_s+.010)


class RegularPhaseScanAcquirer(LivePhaseScanAcquirer):
    """One full timing table, one emission interval, one final native retrieval."""
    hf2_preset_name = "regular_phase_scan_single_detector"
    execution_mode = "regular_single_detector_phase_scan_v1"
    baseline_matching = "sequence position, signed Process Trigger, cadence and measured wavelength"
    def __init__(self, plan=None, hf2_selection=None, *, host_capacity_bytes=None, **kwargs):
        super().__init__(**kwargs)
        self.host_capacity_bytes = int(host_capacity_bytes) if host_capacity_bytes is not None else None
        self.frozen_plan = None
        self.hf2_selection = deepcopy(hf2_selection)
        self._original_hf = self._original_mircat = None
        self._original_timing = {}
        self._restoration = {}
        self.role = None
        self.experiment_session_id = None
        self._session_stores = []
        self._between_stages = False
        if plan is not None:
            self.resolve_plan(plan)

    def resolve_plan(self, plan):
        if not hasattr(plan, "capture_window") or not hasattr(plan, "hf2_selection"):
            raise ValueError("Regular phase acquisition requires a resolved regular phase-scan plan")
        if self.frozen_plan is not None and plan != self.frozen_plan:
            raise ValueError("The resolved phase-scan configuration is frozen for this acquisition")
        selection = self.hf2_selection or plan.hf2_selection
        if not selection or any(key not in selection for key in ("order", "timeconstant_s", "rate_sps", "timing_rate_sps")):
            raise ValueError("Resolve the connected HF2LI settings before acquisition")
        self.hf2_selection = deepcopy(selection)
        self.frozen_plan = self.plan = plan
        self.capture_window = deepcopy(plan.capture_window)
        return plan

    def _plan_for_settings(self, settings):
        if self.frozen_plan is None or settings != self.frozen_plan.settings:
            raise ValueError("Acquisition settings differ from the frozen blank/sample plan")
        return self.frozen_plan

    def _event_timing(self, event):
        return regular_event_timing(event, self.settings.fire_to_qswitch_us * 1e-6)

    def _validate_execution_plan(self, plan):
        if plan != self.frozen_plan:
            raise ValueError("Execution plan differs from the frozen phase-scan configuration")

    def _before_timing_configuration(self, unit):
        saved = unit.read_active_settings()
        def response(mapping, key):
            item = mapping[key]
            if not item.get("ok"):
                raise RuntimeError(f"Cannot retain {unit.name} {key}: {item.get('error', 'read failed')}")
            return str(item["response"]).strip()
        queries = saved["queries"]
        recipe = {"stop_first": True, "trigger_source": "OFF", "gate_mode": 0,
                  "burst_enabled": False, "predivider": int(response(queries, "predivider")),
                  "clock": {"frequency": f"{float(response(queries, 'synth_frequency').removesuffix('Hz')):.15g}Hz"}, "channels": {}}
        # Active engines, source enables and trains are deliberately not
        # restarted. Preserve their original readbacks in the restoration file.
        for channel, values in saved["channels"].items():
            recipe["channels"][channel] = {"enabled": False,
                "delay": response(values, "delay_edge"), "width": response(values, "width_edge"),
                "polarity": response(values, "polarity"), "termination": response(values, "termination"),
                "timing_mode": response(values, "timing_mode")}
        keys = ("trigger_input_polarity", "trigger_input_termination", "trigger_input_threshold_v")
        if all(key in queries for key in keys):
            recipe["external_trigger"] = {"polarity": response(queries, keys[0]),
                "termination": response(queries, keys[1]), "threshold_v": float(response(queries, keys[2]))}
        # P500 queries express edge times relative to configurable other edges.
        # Preserve all references before configure_continuous_clock/preload
        # changes them (T660 Programming Guide, pp. 53, 57, 77).
        references = {edge: int(unit.command(f"TIME:RELTo{edge}?")) for edge in range(1, 9)}
        relative = {edge: _seconds_value(recipe["channels"][channel][key])
                    for channel, edges in CHANNEL_EDGES.items() for edge, key in zip(edges, ("delay", "width"))}
        absolute = {0: 0.}
        def resolve(edge, ancestors=()):
            if edge in absolute:
                return absolute[edge]
            if edge in ancestors or references.get(edge) not in range(9):
                raise ValueError(f"Cannot preserve {unit.name} cyclic/invalid timing-edge references")
            absolute[edge] = relative[edge]+resolve(references[edge], (*ancestors, edge))
            return absolute[edge]
        for edge in references:
            resolve(edge)
        self._original_timing[unit.name] = {"readback": saved, "safe_restore_recipe": recipe,
            "edge_references": references, "absolute_edge_seconds": absolute}

    def _before_mircat_configuration(self):
        self._original_mircat = {"trigger": self.qcl.get_wavelength_trigger_params(),
            "marker_width_us": self.qcl.get_wavelength_trigger_pulse_width_us(), "qcls": []}
        for index in range(1, self.qcl.get_num_installed_qcls()+1):
            self._original_mircat["qcls"].append({"qcl": index,
                "pulse_rate_hz": self.qcl.get_qcl_pulse_rate(index),
                "pulse_width_ns": self.qcl.get_qcl_pulse_width(index),
                "current_ma": self.qcl.get_qcl_current(index)})

    def _configure_hf_preset(self, saved, copied):
        if self.hf2_selection.get("device_id") != self.hf.device_id:
            raise ValueError("Connected HF2LI identity differs from the device whose capabilities were selected")
        self._hf_snapshot_preset = HF2LIPreset(saved.name, copied)
        self._original_hf = self.hf.export_settings_snapshot(preset=self._hf_snapshot_preset)
        if self._original_hf.get("read_errors"):
            raise RuntimeError("HF2LI settings could not all be preserved before configuration: "
                               + str(self._original_hf["read_errors"]))
        for demod in copied["demodulators"]:
            if demod["index"] == 0:
                demod.update(order=int(self.hf2_selection["order"]),
                             timeconstant_s=float(self.hf2_selection["timeconstant_s"]),
                             rate_sps=float(self.hf2_selection["rate_sps"]))
            elif demod["index"] == 2:
                demod["rate_sps"] = float(self.hf2_selection["timing_rate_sps"])
        # Disable the non-acquiring streams before applying rates: HF2 rates
        # depend on every enabled stream, not merely DAQ subscriptions.
        for index in range(6):
            self.hf._set_node("setInt", f"/{self.hf.device_id}/demods/{index}/enable", 0)
        self.hf.sync()
        return copied

    def prepare(self, settings, store, cancel):
        if not self.hf2_selection or not self.hf2_selection.get("capability_verified"):
            raise ValueError("Refresh connected HF2LI capabilities and resolve supported settings before live acquisition")
        if self.plan.scan_duration_s < 2/float(self.hf2_selection["rate_sps"]):
            raise ValueError("The requested scan is shorter than two HF2LI detector sample intervals; "
                             "increase the wavelength span, reduce scan speed or select a supported higher sample rate")
        span = abs(settings.start_wavenumber_cm1-settings.stop_wavenumber_cm1)
        marker_interval = span/max(1, math.ceil(span/5))
        marker_width_us = max(1, min(500, int(marker_interval/settings.scan_speed_cm1_s*1e6/4)))
        if marker_width_us*1e-6 < 2/float(self.hf2_selection["timing_rate_sps"]):
            raise ValueError("The requested scan's wavelength markers are too short for the supported HF2LI "
                             "timing rate; increase the wavelength span or reduce scan speed")
        result = super().prepare(settings, store, cancel)
        actual = {}
        for key, index, node in (("order", 0, "order"), ("timeconstant_s", 0, "timeconstant"),
                                 ("rate_sps", 0, "rate"), ("timing_rate_sps", 2, "rate")):
            value = self.hf_settings_snapshot["nodes"][f"/{self.hf.device_id}/demods/{index}/{node}"]["value"]
            if not math.isclose(float(value), float(self.hf2_selection[key]), rel_tol=1e-6, abs_tol=1e-12):
                raise RuntimeError(f"HF2LI {key} read back {value}, selected {self.hf2_selection[key]}; "
                                   "resolve supported settings again before acquiring a blank")
            actual[key] = value
        from control_app.workflows.regular_phase_scan import filter_response
        resolution = {"requested": deepcopy(self.hf2_selection.get("requested", {})),
                      "selected": deepcopy(self.hf2_selection), "actual": actual,
                      "actual_estimates": filter_response(actual["order"], actual["timeconstant_s"],
                          actual["rate_sps"], actual["timing_rate_sps"], settings.scan_speed_cm1_s)}
        result.update(hf2li_resolution=resolution,
                      experiment_session_id=self.experiment_session_id,
                      requested_settings=asdict(settings),
                      effective_pump_repetition_rate_hz=1/self.plan.frame_period_s,
                      fire_to_qswitch_us=settings.fire_to_qswitch_us, probe_recipe=deepcopy(self.probe_recipe))
        self.preparation_readback = result
        return result

    def _on_sequence_complete(self):
        self._sequence_idle()

    def begin_experiment_session(self, session_id):
        self.experiment_session_id = session_id

    def _verify_interstage(self):
        """Read back the retained configuration without reapplying it."""
        self._check()
        reference = self._verify_unit(self.units["t660_1"], self.reference_recipe)
        timing = self._verify_unit(self.units["t660_2"], {
            "trigger_source": "OFF", "channels": {c: {"enabled": False} for c in "ABCD"}})
        if self.qcl.is_emission_on() or self.qcl.get_scan_status()["scan_in_progress"]:
            raise RuntimeError("Phase experiment is not ready between stages: emission or sweep is active")
        if not self.qcl.is_laser_armed():
            raise RuntimeError("Phase experiment lost its armed MIRcat session")
        snapshot = self.hf.export_settings_snapshot(preset=self.preset)
        expected = deepcopy(self.hf_settings_snapshot)
        expected["nodes"] = {p: v for p, v in expected["nodes"].items()
                             if "/oscs/" not in p and not p.endswith("/plls/0/freqcenter")}
        comparison = self.hf.compare_settings_snapshots(expected, snapshot, double_tolerance=1e-8)
        if snapshot.get("read_errors") or not comparison["match"]:
            raise RuntimeError(f"Retained HF2LI settings changed: {comparison}")
        frequency = self.hf.get_oscillator_frequency(0)
        if not math.isclose(frequency, self.probe_rate_hz_readback, rel_tol=.001):
            raise RuntimeError("HF2LI lost the retained external reference; end the experiment and acquire a new blank")
        qcls = [self._verify_qcl_pulse_settings(s["qcl"], external_rate_hz=self.probe_rate_hz_readback)
                for s in self.segments]
        from control_app.workflows.phase_scan_data import compatible_readbacks
        if not compatible_readbacks(self.configured_qcls, qcls):
            raise RuntimeError("Retained MIRcat pulse settings changed")
        marker = {}
        self._verify_external_trigger(self.segments[0], self.marker_interval, "between_stages", marker)
        return {"reference": reference, "timing": timing, "hf2li": snapshot,
                "hf2li_comparison": comparison, "oscillator_frequency_hz": frequency,
                "qcls": qcls, "marker": marker, "emission_off": True, "reference_running": True}

    def _sequence_idle(self):
        if self.experiment_session_id is None:
            return super()._sequence_idle()
        if self._between_stages:
            return
        # A alone supplies the HF2 reference. B drives the optical probe and C
        # feeds the downstream frame engine; inhibit both without stopping A.
        for channel in "BCD":
            self.units["t660_1"].disable_channel(channel)
        self._stop_unit(self.units["t660_2"])
        self.qcl.stop_scan_if_needed()
        self.qcl.turn_emission_off()
        self._interstage_readback = self._verify_interstage()
        self._between_stages = True

    def retain_experiment(self):
        if not self._between_stages or self._closed or self._safed:
            raise RuntimeError("Cannot retain an experiment that has not reached its interstage boundary")
        if self.store.path not in self._session_stores:
            self._session_stores.append(self.store.path)
        record = {"session_id": self.experiment_session_id, "state": "awaiting_next_stage",
                  "restoration_deferred": True, "interstage_verified": True,
                  "readback": self._interstage_readback}
        write_json(self.store.path / "experiment_session.json", record)
        (self.store.path / "commands.txt").write_text(self.log.getvalue(), encoding="utf-8")
        return {k: v for k, v in record.items() if k != "readback"}

    def resume_experiment(self, settings, store, cancel):
        if not self.authorized:
            raise PermissionError("Confirm this acquisition before laser operation")
        if settings != self.settings or not self._between_stages or self._closed or self._safed:
            raise RuntimeError("The retained experiment cannot resume with these settings; end it first")
        # Switch the evidence destination before verification, so a failed
        # resume cannot overwrite the completed blank's records.
        self.store, self.cancel = store, cancel
        self.log.seek(0)
        self.log.truncate(0)
        self.blocks, self.partial_blocks = [], []
        readback = self._verify_interstage()
        write_json(store.path / "experiment_session_resume.json", {
            "session_id": self.experiment_session_id, "state": "resumed", "readback": readback})
        self._between_stages = False
        return deepcopy(self.preparation_readback)

    def close(self):
        already_closed = self._closed
        try:
            super().close()
        except BaseException as exc:
            if not already_closed:
                self._record_session_close(False, str(exc))
            raise
        else:
            if not already_closed:
                self._record_session_close(True, None)

    def _record_session_close(self, verified, error):
        if self.experiment_session_id is None:
            return
        paths = list(self._session_stores)
        if self.store is not None and self.store.path not in paths:
            paths.append(self.store.path)
        for path in paths:
            write_json(path / "experiment_session_close.json", {
                "session_id": self.experiment_session_id, "safe_verified": verified, "error": error,
                "restoration_path": str(self.store.path / "restoration.json")})

    def _acquisition_metadata(self):
        return {**super()._acquisition_metadata(), "hf2_preset": self.hf2_preset_name,
                "experiment_session_id": self.experiment_session_id,
                "pump_repetition_rate_hz": self.settings.pump_repetition_rate_hz,
                "phase_delay_us": self.settings.phase_delay_us, "fire_to_qswitch_us": self.settings.fire_to_qswitch_us,
                "hf2li_resolution": deepcopy(self.preparation_readback["hf2li_resolution"])}

    def _qualification_metadata(self):
        return {"execution_mode": self.execution_mode,
                "trajectory_calibrated": False, "pump_time_basis": "electrical_sync",
                "wavenumber_basis": "controller_markers", "optical_pump_arrival_verified": False,
                "fire_to_qswitch_us": self.settings.fire_to_qswitch_us, "hf2li_resolution": self.preparation_readback["hf2li_resolution"]}

    def prepare_blocks(self, plan, events, cancel):
        self._check()
        self._validate_execution_plan(plan)
        if self.blocks:
            raise ValueError("This acquisition already has a prepared sequence")
        events = list(events)
        expected = [plan.event_at(i) for i in range(plan.total_scans)]
        if events == expected:
            self.role = "sample"
        elif events == [replace(event, pump_enabled=False) for event in expected]:
            self.role = "blank"
        elif events == [expected[0]]:
            self.role = "preliminary"
        else:
            raise ValueError("Acquire the complete planned blank/sample sequence or its unpumped preliminary scan")
        frame_capacity = self.units["t660_2"].verified_frame_capacity()
        physical_count = max(2, len(events))
        if physical_count > frame_capacity or len(events) > 65535:
            raise AcquisitionCapacityError(f"The uninterrupted sequence needs {physical_count} timing frames; "
                                           f"the connected controller supports {frame_capacity}. No splitting is performed.")
        predivider = self.plan.frame_period_s * self.probe_rate_hz_readback
        if not math.isclose(predivider, round(predivider), rel_tol=0., abs_tol=1e-6) or not 1 <= round(predivider) <= 2**32-1:
            raise AcquisitionCapacityError("The requested pump cadence is not representable by the connected timing predivider")
        frames = []
        for event in events:
            frame, duration = self._event_timing(event)
            scan_delay = float(frame["channels"]["C"]["delay"][:-1])
            if max(duration, scan_delay+self.capture_window["duration_s"]) >= self.plan.frame_period_s-1e-6:
                raise AcquisitionCapacityError(f"Scan {event.scan_index+1} does not fit the requested cadence: "
                                               "signed timing and the full capture window exceed the frame period")
            frames.append(frame)
        block = {"block_index": 0, "events": events, "frames": frames, "daq": None,
                 "frame_capacity": frame_capacity}
        self.blocks = [block]
        daq = self._prepare_daq(block)
        block["estimated_bytes"] = daq.capacity["required_bytes"]
        write_json(self.store.path / "acquisition_preflight.json", {
            "settings": asdict(self.settings), "plan": plan.to_dict(), "capture_window": self.capture_window,
            **self._detector_metadata(), "role": self.role,
            "timing_recipe": {"id": self.execution_mode, "probe_clock": self.probe_recipe,
                "reference_preflight": self.reference_recipe, "frame_predivider": round(predivider),
                "frame_tables": [frames], "fire_to_qswitch_us": self.settings.fire_to_qswitch_us,
                **self._baseline_matching_metadata(),
                "pump_inhibited": not any(e.pump_enabled for e in events)},
            "capacity": daq.capacity, "retention": {"read_policy": "deferred",
                "sequence_count": 1, "scan_count": len(events), "no_automatic_partitioning": True},
            "hf2li_settings_snapshot": self.hf_settings_snapshot, **self._qualification_metadata()})
        return self.blocks

    def _prepare_daq(self, block):
        if block["daq"] is None:
            block["daq"] = FinitePhaseDAQ(self.hf, events=block["events"],
                duration_s=self.capture_window["duration_s"], pretrigger_s=self.capture_window["pretrigger_s"],
                host_capacity_bytes=(self.host_capacity_bytes if self.host_capacity_bytes is not None else available_host_memory_bytes()),
                read_policy="deferred", max_events=block["frame_capacity"], allocation_margin_fraction=0.,
                **self._daq_detector_options())
        return block["daq"]

    def _daq_detector_options(self):
        return {}

    def _baseline_matching_metadata(self):
        return {"blank_matching": self.baseline_matching}

    def _start_sweep_block(self, count, record):
        """Validate the controller's accepted sweep while probe/pump are inhibited."""
        segment = self.segments[0]
        for channel in "BC":
            self.units["t660_1"].disable_channel(channel)
        if self.qcl.is_emission_on():
            raise RuntimeError("MIRcat emission must be off during sweep capability preflight")
        self.qcl.cancel_manual_tune()
        self._verify_external_trigger(segment, self.marker_interval, "after_manual_tune_cancel", record)
        self._wait_for_stable_tecs("before_continuous_sweep_setup", record=record)
        errors = []
        def start():
            try:
                self.qcl.start_sweep_scan(**segment, scan_rate_cm1_s=self.settings.scan_speed_cm1_s,
                                         repetitions=count)
            except Exception as exc:
                errors.append(exc)
        self._start_thread = Thread(target=start, daemon=True, name="regular-phase-sweep-setup")
        self._start_thread.start()
        deadline = monotonic()+45
        while self._start_thread.is_alive():
            self._check(interlock=False)
            if monotonic() > deadline:
                raise TimeoutError("MIRcat sweep setup did not return before emission")
            self.cancel.wait(.02)
        self._start_thread.join()
        if errors:
            raise RuntimeError(f"MIRcat rejected the requested sweep settings: {errors[0]}") from errors[0]
        actual = self.qcl.get_sweep_parameters()
        expected = {"start_cm1": segment["start_cm1"], "stop_cm1": segment["stop_cm1"],
                    "scan_rate_cm1_s": self.settings.scan_speed_cm1_s, "repetitions": count}
        record["mircat_sweep_settings"] = {"requested": expected, "actual": actual}
        for key, value in expected.items():
            if key not in actual or not math.isclose(float(actual[key]), float(value), rel_tol=1e-6, abs_tol=1e-5):
                raise RuntimeError(f"MIRcat does not accept requested {key}={value}; readback is {actual.get(key)}")
        self._verify_external_trigger(segment, self.marker_interval, "after_block_setup", record)
        self._observe_marker_channel(segment, record)
        record["mircat_internal_settings_after_block_setup"] = self._verify_qcl_pulse_settings(
            segment["qcl"], external_rate_hz=self.probe_rate_hz_readback)
        self._wait(self.qcl.get_scan_waiting_process_trigger, 30, "MIRcat did not wait for the external frame trigger")
        # StartSweepScan/CancelManualTuneMode can clear the manually tuned
        # state: enabling emission in that state returns LASER_NOT_TUNED.
        # End the non-emitting capability check, then use the tested order:
        # tune, enable emission, cancel manual tune, arm the full sweep.
        # No frames have fired; the actual sequence has one emission interval.
        self.qcl.stop_scan_if_needed()
        self.qcl.tune_to_wavenumber(segment["start_cm1"], qcl=segment["qcl"])
        self._wait(self.qcl.is_tuned, 45, "MIRcat did not tune before emission")
        super()._start_sweep_block(count, record)
        actual = self.qcl.get_sweep_parameters()
        record["mircat_sweep_settings_after_emission"] = {"requested": expected, "actual": actual}
        for key, value in expected.items():
            if key not in actual or not math.isclose(float(actual[key]), float(value), rel_tol=1e-6, abs_tol=1e-5):
                raise RuntimeError(f"MIRcat does not accept requested {key}={value}; readback is {actual.get(key)}")

    def _observe_marker_channel(self, segment, record):
        super()._observe_marker_channel(segment, record)
        if controller_marker_identity({**record, "scan_profile": {**segment, "marker_interval_cm1": self.marker_interval}},
                                      len(self.targets)) is None:
            raise ValueError("The connected MIRcat must identify each wavelength marker before triggering")

    def _validate_spectrum(self, event, spectrum):
        metadata = spectrum.metadata
        if metadata.get("wavenumber_basis") != "controller_markers":
            raise ValueError("Regular phase spectra require observed controller-identified wavelength markers")
        if len(metadata.get("marker_ticks", [])) != len(self.targets):
            raise ValueError("Observed wavelength-marker count does not match the accepted scan trajectory")
        start, stop = metadata["sweep_active_ticks"]
        duration = (stop-start)/metadata["clockbase_hz"]
        if not 0 < duration <= self.capture_window["engineering_sweep_bound_s"]:
            raise ValueError("Measured sweep exceeds the preflight capture envelope; native data retained")
        if (spectrum.pump_time_s is not None) != event.pump_enabled:
            raise ValueError("Observed electrical pump sync does not match the requested sequence position")
        metadata.update(execution_mode=self.execution_mode, sequence_position=event.scan_index,
                        record_role="buffer_blank" if self.role == "blank" else
                                    "pumped_sample" if event.pump_enabled else "unpumped_sample_baseline",
                        fire_to_qswitch_us=self.settings.fire_to_qswitch_us, optical_pump_arrival_verified=False,
                        hf2li_resolution=deepcopy(self.preparation_readback["hf2li_resolution"]))
        return spectrum

    def _restore_instrument_settings(self):
        errors = []
        if self._original_hf is not None:
            try:
                snapshot = deepcopy(self._original_hf)
                # The installed external-reference PLL center is an acquired
                # frequency, even when disabled. Retain it as evidence, but
                # do not replay it or require it to match after safe-idle.
                center_path = f"/{self.hf.device_id}/plls/0/freqcenter"
                snapshot["nodes"].pop(center_path, None)
                enables = {p: v for p, v in snapshot["nodes"].items() if "/demods/" in p and p.endswith("/enable")}
                for path in enables:
                    self.hf._set_node("setInt", path, 0)
                    snapshot["nodes"].pop(path)
                self.hf.reload_settings_snapshot(snapshot)
                for path, value in enables.items():
                    self.hf._set_node("setInt", path, value["value"])
                self.hf.sync()
                after = self.hf.export_settings_snapshot(preset=self._hf_snapshot_preset)
                # PLL oscillator frequency is an observed external signal, not
                # a restorable setting while the safe-idle reference is stopped.
                check = deepcopy(self._original_hf)
                check["nodes"] = {p: v for p, v in check["nodes"].items()
                                  if "/oscs/" not in p and p != center_path}
                differences = self.hf.compare_settings_snapshots(check, after, double_tolerance=1e-8)
                differences["external_reference_observations"] = {
                    p: {"before": v, "after": after["nodes"].get(p)}
                    for p, v in self._original_hf["nodes"].items() if p not in check["nodes"]}
                self._restoration["hf2li"] = {"before": self._original_hf, "after": after, "comparison": differences}
                if not differences["match"]:
                    raise RuntimeError(f"HF2LI original settings did not restore: {differences['mismatches']}")
            except Exception as exc:
                errors.append(f"HF2LI: {exc}")
        if self._original_mircat is not None:
            try:
                original = self._original_mircat
                for settings in original["qcls"]:
                    self.qcl.set_qcl_pulse_params(**settings)
                allowed = ("pulse_mode", "process_trigger_mode", "start", "stop", "interval", "units", "dwell_us", "after_off_us")
                self.qcl.set_wavelength_trigger_params(**{k: original["trigger"][k] for k in allowed if k in original["trigger"]})
                self.qcl.set_wavelength_trigger_pulse_width_us(original["marker_width_us"])
                after = {"trigger": self.qcl.get_wavelength_trigger_params(),
                         "marker_width_us": self.qcl.get_wavelength_trigger_pulse_width_us(), "qcls": []}
                for settings in original["qcls"]:
                    index = settings["qcl"]
                    after["qcls"].append({"qcl": index, "pulse_rate_hz": self.qcl.get_qcl_pulse_rate(index),
                        "pulse_width_ns": self.qcl.get_qcl_pulse_width(index), "current_ma": self.qcl.get_qcl_current(index)})
                from control_app.workflows.phase_scan_data import compatible_readbacks
                matched = compatible_readbacks(original, after)
                self._restoration["mircat"] = {"before": original, "after": after, "match": matched}
                if not matched:
                    raise RuntimeError("MIRcat original settings did not restore")
            except Exception as exc:
                errors.append(f"MIRcat: {exc}")
        for name, saved in self._original_timing.items():
            try:
                unit = self.units[name]
                # Restore absolute timing in a neutral, inhibited RF state,
                # then restore original references and channel timing modes.
                for channel in "ABCD":
                    unit.set_channel_timing_mode(channel, "rise_fall")
                for edge in range(1, 9):
                    unit.command(f"TIME:RELTo{edge} 0", expect_response=False)
                absolute = saved["absolute_edge_seconds"]
                for rising, falling in CHANNEL_EDGES.values():
                    unit.command(f"TIME:QUEue{rising} 0s", expect_response=False)
                    unit.command(f"TIME:QUEue{falling} {absolute[falling]:.12f}s", expect_response=False)
                    unit.command(f"TIME:QUEue{rising} {absolute[rising]:.12f}s", expect_response=False)
                unit.command("TIME:COMmit", expect_response=False)
                for edge, reference in saved["edge_references"].items():
                    unit.command(f"TIME:RELTo{edge} {reference}", expect_response=False)
                recipe = deepcopy(saved["safe_restore_recipe"])
                for values in recipe["channels"].values():
                    values.pop("delay")
                    values.pop("width")
                unit.apply_recipe(recipe)
                after = self._verify_unit(unit, recipe)
                for channel, values in saved["safe_restore_recipe"]["channels"].items():
                    for key, query in (("delay", "delay_edge"), ("width", "width_edge")):
                        actual = after["channels"][channel][query]
                        if not actual.get("ok") or not math.isclose(
                                _seconds_value(actual["response"]), _seconds_value(values[key]), abs_tol=1e-11, rel_tol=0.):
                            raise RuntimeError(f"{name} channel {channel} {key} did not restore")
                for edge, reference in saved["edge_references"].items():
                    if int(unit.command(f"TIME:RELTo{edge}?")) != reference:
                        raise RuntimeError(f"{name} timing-edge {edge} reference did not restore")
                self._restoration[name] = {**saved, "after": after,
                    "safe_idle_exclusions": "Sources, outputs, frame engine, trains, gate and bursts remain inhibited; elapsed shot counters and overwritten inactive frame tables are diagnostic history"}
            except Exception as exc:
                errors.append(f"{name}: {exc}")
        if self.store is not None:
            write_json(self.store.path / "restoration.json", {"instruments": self._restoration,
                "settings_restored_and_outputs_inhibited": not errors, "errors": errors})
        if errors:
            raise RuntimeError("; ".join(errors))
