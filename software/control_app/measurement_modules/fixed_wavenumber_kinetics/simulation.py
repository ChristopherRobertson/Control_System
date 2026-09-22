"""Explicit synthetic devices; never a fallback for a connected operation."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import numpy as np


def simulation_profile(mode="single", *, condition_id="synthetic-condition", condition_profile="rt_hrp_co"):
    """Illustrative simulated capabilities, deliberately unrelated to commissioning."""
    detector = {"demodulator_index": 0, "input_index": 0, "rate_sps": 1000.,
                "timeconstant_s": .001, "order": 1}
    profile = {"record_id": "SYNTHETIC-fixed-point-operating-profile-v1",
        "qualification_kind": "simulation", "condition_profile": condition_profile,
        "condition_id": condition_id, "configuration_id": "SYNTHETIC-no-hardware-v1",
        "sample": detector, "reference": {**detector, "demodulator_index": 3, "input_index": 1},
        "probe_recipe": {"trigger_source": "OFF", "stop_first": True, "predivider": 1,
            "gate_mode": 0, "burst_enabled": False, "clock": {"frequency": "100000Hz", "shots": 0},
            "channels": {c: {"enabled": c != "D", "delay": "0ns", "width": "150ns",
                "polarity": "positive", "termination": "50OHM"} for c in "ABCD"}},
        "mircat": {"qcl": 1, "pulse_rate_hz": 110000., "pulse_width_ns": 150.},
        "settling_s": .02, "tune_tolerance_cm1": .05, "timing_rate_sps": 10000.,
        "timing_demodulator_index": 2, "pump_marker_bit": 16, "pump_marker_min_width_s": .002,
        "hf2li": {"signal_inputs": {"sample": {"index": 0, "range_v": 1., "ac": False,
                    "impedance_50ohm": False, "differential": False},
                "reference": {"index": 1, "range_v": 1., "ac": False, "impedance_50ohm": False, "differential": False}},
            "pll": {"index": 0, "enable": True, "adcselect": 4, "freqcenter_hz": 100000., "harmonic": 1, "order": 1, "adcthreshold": 0}},
        "timing": {"input_frequency_hz": 100000., "fire_delay_s": 0., "q_switch_delay_s": .0002,
            "fire_width_s": .00001, "q_switch_width_s": .00001,
            "fire_polarity": "positive", "q_switch_polarity": "positive", "termination": "50OHM"},
        "topology_record_id": "SYNTHETIC-tee-topology", "acquisition_response_record_id": "SYNTHETIC-response",
        "temperature_record_id": "SYNTHETIC-temperature", "dose_record_id": "SYNTHETIC-dose",
        "temperature_uncertainty_k": .1, "temperature_uncertainty_source": "SYNTHETIC illustration only",
        "reset_record_id": "SYNTHETIC-reset", "minimum_event_interval_s": .5,
        "baseline_drift_fraction": .01, "baseline_cv_limit": .05, "reset_tolerance_fraction": .02,
        "continuous_poll_lossless_qualified": True, "maximum_aggregate_rate_sps": 700000.,
        "overhead_estimates_s": {"configuration": .1, "upload_per_frame": .001, "tune_per_position": .01,
            "restoration": .01, "saving": .01, "analysis": .1},
        "acquisition_response": {"model": "single_pole", "timeconstant_s": .001,
            "record_id": "SYNTHETIC-response", "measured": True},
        "sample_supported_rates_sps": [1000.], "reference_supported_rates_sps": [1000.],
        "timing_supported_rates_sps": [10000.], "configuration_source": "Explicit simulation only"}
    from .settings import Settings, Position
    from control_app.measurement_host.interchange import SampleSpectralSelection, SourceRecord, SpectralWindow
    sample_id = "SYNTHETIC-sample"
    selection = SampleSpectralSelection("SYNTHETIC-selection", sample_id,
        f"fixed_wavenumber_kinetics:{mode}",
        SourceRecord("SYNTHETIC-source-run", "synthetic://fixed-point-example", "2026-09-09T00:00:00+00:00", "synthetic-1"),
        condition_id, {"condition_profile": condition_profile, "synthetic": True,
            "preparation_id": "SYNTHETIC-preparation", "cell_id": "SYNTHETIC-cell"},
        (SpectralWindow(1900., 1950., 1930., .05, "SYNTHETIC-band"),),
        "Synthetic fixture", "2026-09-09T00:00:00+00:00", "Synthetic uncertainties; no measured sample evidence")
    settings = Settings(mode=mode, condition_id=condition_id, condition_profile=condition_profile,
        sample_id=sample_id, preparation_id="SYNTHETIC-preparation", cell_id="SYNTHETIC-cell",
        position_id="SYNTHETIC-position", temperature_id="SYNTHETIC-temperature",
        temperature_k=77. if condition_profile.startswith("cryo") else 295.,
        positions=(Position(1930., "band", "SYNTHETIC-selection", "A1" if "mbco" in condition_profile else ""),),
        pre_observation_s=.2, post_observation_s=3., chunk_duration_s=.2,
        dark_control_record_id="SYNTHETIC-dark", artifact_control_record_id="SYNTHETIC-artifact")
    configuration = {"fixed_wavenumber_kinetics": deepcopy(profile)}
    evidence = {"operating_profile": deepcopy(profile), "sample_selection": selection.to_dict()}
    return {"configuration": configuration, "evidence": evidence, "settings": settings.to_dict()}


class SimulatedDevices:
    """Virtual-clock surrogate with finite events and exact large uint64 clocks.

    Fault injection occurs via operation.configuration['fixed_point_simulation'].
    It exercises the same runner/retention path as installed services.
    """
    def __init__(self, context, operation):
        if operation.hardware:
            raise ValueError("Synthetic devices cannot satisfy a connected operation")
        self.context, self.operation = context, operation
        self.faults = dict(operation.configuration.get("fixed_point_simulation", {}))
        self.clockbase_hz = 210000000
        self.epoch = 2**54 + 123456
        self.time = 0.
        self.pumps = []
        self.rng = np.random.default_rng(41)
        self.streaming = False
        self.before = {"simulation": True}
        self.readbacks = {"simulation": True, "clockbase_hz": self.clockbase_hz}
        self.services = {}
        self.dispatched = 0
        self.read_count = 0
        self.position = 0.
        self.off_band = False

    def connect(self, check, *, prepare=True):
        check()
        if self.faults.get("connect_failure"):
            raise RuntimeError("Injected connection failure")

    def discover_operating_profile(self, settings, check, progress, *, probe_capabilities=False):
        from .adapters import mapping
        check()
        profile = simulation_profile(self.context.mode)["configuration"]["fixed_wavenumber_kinetics"]
        profile.update(mapping(self.operation.configuration).get("fixed_wavenumber_kinetics", {}))
        profile["source_kind"] = "simulation"
        profile["source"] = "Explicit synthetic devices; no connected measurements"
        return profile

    read_operating_settings = discover_operating_profile

    def configure(self, resolved, check):
        check()
        self.resolved = deepcopy(resolved)
        self.readbacks["resolved"] = deepcopy(resolved)

    def tune(self, wavenumber_cm1, settings, check, progress):
        check()
        self.position = wavenumber_cm1
        self.off_band = any(float(p["wavenumber_cm1"]) == float(wavenumber_cm1) and
            p.get("label") in {"off_band", "control"} for p in settings.get("positions", ()))
        if self.faults.get("tune_failure"):
            raise RuntimeError("Injected actual Tuned failure")
        return {"requested_cm1": wavenumber_cm1, "actual": {"value": wavenumber_cm1, "units": "cm-1", "light_valid": True},
            "tuned": True, "settling_s": self.resolved["settling_s"], "simulation": True}

    def upload(self, program, check, progress):
        for n in range(len(program["frames"])+1):
            check()
            progress({"stage": "acknowledged timing-table upload", "completed": n,
                "total": len(program["frames"]), "message": "Synthetic acknowledged frame"})
        return {"physical_frame_count": len(program["frames"]), "simulation": True}

    def start_stream(self):
        self.streaming = True

    def read(self, duration_s):
        if not self.streaming:
            raise RuntimeError("Synthetic acquisition is not subscribed")
        self.read_count += 1
        if self.faults.get("read_failure_at") == self.read_count:
            raise RuntimeError("Injected read failure")
        start, end = self.time, self.time+duration_s
        self.time = end
        result = {"clockbase_hz": self.clockbase_hz, "simulation": True}
        for role in ("sample", "reference", "timing"):
            if role == "reference" and self.context.mode != "dual":
                continue
            profile = self.resolved.get(role, {})
            rate = profile.get("rate_sps", self.resolved["timing_rate_sps"])
            # Global device grid independent of host poll boundaries.
            n0, n1 = int(np.ceil(start*rate-1e-8)), int(np.ceil(end*rate-1e-8))
            seconds = np.arange(n0, n1, dtype=float)/rate
            ticks = np.asarray(np.rint(seconds*self.clockbase_hz), dtype=np.uint64)+np.uint64(self.epoch)
            signal = np.full(len(ticks), .8 if role == "reference" else .5)
            common = .0001*np.sin(seconds*2*np.pi*.3)
            signal *= 1+common
            drift = float(self.faults.get("baseline_drift_per_s", 0))
            signal *= 1+drift*seconds
            marker_bit = np.uint64(1 << int(self.resolved["pump_marker_bit"]))
            dio = np.full(len(ticks), marker_bit, dtype=np.uint64)
            for pump in self.pumps:
                dt = seconds-pump
                active = dt >= 0
                if role == "sample":
                    amplitude = float(self.faults.get("off_band_artifact_amplitude", 0.) if self.off_band else self.faults.get("amplitude", .015))
                    tau = float(self.faults.get("recovery_tau_s", .4))
                    response = float(self.resolved["sample"]["timeconstant_s"])
                    a = np.maximum(dt, 0)
                    transient = tau/(tau-response)*(np.exp(-a/tau)-np.exp(-a/response))
                    signal *= 10**(-amplitude*transient*active)
                if not self.faults.get("missing_marker"):
                    pulse = active & (dt < .002)
                    dio[pulse] &= ~marker_bit
                if self.faults.get("extra_marker"):
                    dio[(dt >= .01) & (dt < .012)] &= ~marker_bit
            if self.faults.get("missing_reference") and role == "reference":
                signal[:] = np.nan
            if self.faults.get("gap_at") == self.read_count:
                keep = np.arange(len(ticks)) >= max(1, len(ticks)//4)
                ticks, signal, dio = ticks[keep], signal[keep], dio[keep]
            result[role] = {"timestamp": ticks, "x": signal, "y": np.zeros(len(signal)), "dio": dio,
                "clipped": np.full(len(signal), bool(self.faults.get("clipped"))),
                "unlocked": np.full(len(signal), bool(self.faults.get("unlocked")))}
        return result

    def start_event(self, program):
        self.dispatched += 1
        offsets = program["pump_command_offsets_s"]
        self.pumps.extend(self.time+float(offset) for offset in offsets)
        self.current_program = program

    def finish_event(self):
        return {"frames_status": "ERROR" if self.faults.get("timing_error") else "DONE",
            "frame_shot_count": len(self.current_program["frames"]), "simulation": True}

    def idle(self, duration_s, check):
        check()
        self.time += duration_s

    def stop_stream(self):
        self.streaming = False

    def cleanup(self, retain_tail=None):
        preservation_errors = []
        if self.streaming and retain_tail is not None:
            try:
                retain_tail(self.read(.001))
            except Exception as exc:
                preservation_errors.append(str(exc))
        self.streaming = False
        errors = ["Injected restoration readback failure"] if self.faults.get("cleanup_failure") else []
        return {"safe_verified": not errors, "errors": errors,
            "actions": [{"action": "synthetic safe closure", "ok": not errors}], "simulation": True,
            "preservation_errors": preservation_errors}
