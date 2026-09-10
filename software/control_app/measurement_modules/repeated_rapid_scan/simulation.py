"""Explicit deterministic offline devices and known native transient truth.

This module cannot construct a real device or fall back to physical acquisition.
The changing transient is evaluated at each native wavelength/time observation.
"""
from __future__ import annotations

from dataclasses import replace
import numpy as np

from .acquisition import get, notify
from .data import NativeMovie, NativeScan, NativeStream, PumpObservation, ScanTrajectory


class SimulationAcquirer:
    def __init__(self, context, operation, plan, *, faults=None):
        self.context, self.operation, self.plan = context, operation, plan
        self.settings = get(plan, "settings")
        self.faults = dict(faults or {})
        self.raw_movies, self.readbacks, self.restoration = [], {}, {}
        self.role = "measurement"
        self.pump_count = 0
        self.capture_count = 0

    def prepare(self, worker):
        notify(worker, "Configuration: explicit simulated devices; no physical hardware")
        worker.check_cancelled()
        if self.faults.get("prepare"):
            raise RuntimeError("Injected preparation failure")
        self.readbacks = {"simulation": True, "device_identity": "rrs-native-simulator-v1",
                          "time_zero_basis": "simulated_electrical_sync", "optical_arrival_verified": False}

    def capture(self, movie_plan, worker, *, qualification=False):
        worker.check_cancelled()
        self.capture_count += 1
        settings, compiled = self.settings, get(movie_plan, "compiled")
        count = settings.pre_scans if qualification else get(compiled, "expected_scan_count")
        pump_enabled = not qualification and get(movie_plan, "pump_count", 0) == 1
        pump_time = get(compiled, "pump_command_s") if pump_enabled else None
        if pump_time is not None:
            pump_time += self.faults.get("pump_jitter_s", 17e-6)
        self.pump_count += int(pump_enabled)
        movie_id = get(movie_plan, "movie_id") + (":qualification" if qualification else "")
        physical_count = count+1 if qualification else len(get(compiled, "frames"))
        raw = {"movie_id": movie_id, "scans": [], "status": "partial", "qualification": qualification,
               "expected_scan_count": count, "physical_frame_count": physical_count,
               "terminal_inhibit_count": 1}
        self.raw_movies.append(raw)
        notify(worker, f"Acquisition: simulated {'qualification' if qualification else 'recovery'} movie ({count} scans)", 0, count)
        period = get(compiled, "scan_period_s")
        points_per_scan = min(300, max(64, int(settings.sample_rate_hz * period)))
        nu = np.linspace(settings.scan_start_cm1, settings.scan_stop_cm1, points_per_scan)
        direction = get(movie_plan, "direction", "forward")
        if direction == "reverse":
            nu = nu[::-1].copy()
        shape = sum(np.exp(-.5 * ((nu - .5*(window[0]+window[1])) / max((window[1]-window[0])/3., .1))**2)
                    for window in settings.band_windows_cm1)
        tau = float(self.faults.get("tau_s", .15))
        clockbase = 210_000_000
        tick_origin = 2**53 + 973  # Deliberately cannot be represented by float64.
        for index in range(count):
            worker.check_cancelled()
            jitter = 0. if index == 0 else np.sin(index * 1.3) * 2e-6
            t = index * period + jitter + np.linspace(.00001*period, .97*period, points_per_scan)
            ticks = tick_origin + np.rint(t * clockbase).astype(np.int64)
            actual_t = (ticks-tick_origin).astype(float) / clockbase
            transient = np.zeros(points_per_scan)
            if pump_enabled and get(movie_plan, "control") == "sample":
                delay = actual_t-pump_time
                transient = np.where(delay >= 0., np.exp(-np.maximum(delay, 0.) / tau), 0.)
                if self.faults.get("reset"):
                    transient = np.where(delay >= 0., .8 + .2*transient, 0.)
            absorbance = .2*shape - .08*shape*transient
            if self.faults.get("offband_reset"):
                absorbance += .03 * (transient > 0)
            reference = 1. + .003*np.sin(actual_t * .7)
            sample = np.power(10., -absorbance)
            if self.role == "blank":
                sample = np.ones(points_per_scan)
            if settings.mode == "dual":
                sample *= reference
            if get(movie_plan, "control") == "dark":
                sample = np.zeros(points_per_scan)
                reference = np.zeros(points_per_scan)
            if self.faults.get("stationarity") and qualification:
                sample *= 1 + .2*index
            flags = {}
            if self.faults.get("clipped") and index == settings.pre_scans:
                flags["clipped"] = np.ones(points_per_scan, dtype=bool)
            if self.faults.get("unlocked") and index == settings.pre_scans:
                flags["unlocked"] = np.ones(points_per_scan, dtype=bool)
            keep = np.ones(points_per_scan, dtype=bool)
            if self.faults.get("missing_data") and index == settings.pre_scans:
                keep[points_per_scan//3:points_per_scan//2] = False
            native = NativeStream(ticks[keep], sample[keep], variance=np.full(np.count_nonzero(keep), 1e-10),
                flags={k: v[keep] for k, v in flags.items()}, timestamp_origin=tick_origin,
                timestamp_unit_s=1/clockbase, metadata={"expected_sample_interval_s": .97*period/(points_per_scan-1)})
            ref_stream = None
            if settings.mode == "dual":
                if self.faults.get("bad_reference") and index == settings.pre_scans:
                    reference[points_per_scan//2] = 0.
                ref_stream = NativeStream(ticks.copy(), reference.copy(), variance=np.full(points_per_scan, 1e-10),
                    timestamp_origin=tick_origin, timestamp_unit_s=1/clockbase)
            trajectory = ScanTrajectory(ticks.copy(), nu.copy(), "simulated-calibrated-trajectory-v1", direction,
                                       timestamp_origin=tick_origin, timestamp_unit_s=1/clockbase)
            scan = NativeScan(index, native, trajectory, ref_stream,
                             sample_reference_covariance=np.zeros(np.count_nonzero(keep)) if ref_stream is not None else None,
                             metadata={"known_truth_absorbance": absorbance[keep], "known_truth_time_s": actual_t[keep],
                                       "known_truth_wavenumber_cm1": nu[keep]})
            raw["scans"].append(scan)
            notify(worker, f"Acquisition: simulated scan {index+1}/{count}", index+1, count)
            if self.faults.get("cancel_scan") == index:
                worker.cancel_event.set()
                worker.check_cancelled()
            if self.faults.get("capture_scan") == index:
                raise RuntimeError("Injected retrieval failure; accumulated native scans retained")
        observed = () if not pump_enabled or self.faults.get("missing_pump") else (
            PumpObservation(pump_time, clock_id="hf2li", basis="electrical_sync", observation_id=movie_id+":sync",
                            metadata={"source": "simulated independent electrical observation", "optical_arrival_verified": False}),)
        if self.faults.get("extra_pump") and pump_enabled:
            observed += (replace(observed[0], timestamp_s=pump_time+.001),)
        raw["status"] = "complete"
        raw["pump_observations"] = observed
        return NativeMovie(movie_id, get(movie_plan, "selected_phase_s", 0.), tuple(raw["scans"]), observed,
            settings.mode, settings.condition_id, metadata={"expected_pump_count": int(pump_enabled),
                "control": get(movie_plan, "control", "sample"), "qualification": qualification,
                "simulation": True, "known_truth_tau_s": tau, "condition": settings.condition.to_dict() if hasattr(settings.condition, "to_dict") else {},
                "planned_duration_s": physical_count*period, "spectral_scan_count": count,
                "physical_frame_count": physical_count, "terminal_inhibit_count": 1})

    def restore(self, worker):
        notify(worker, "Restoration: simulated source outputs inhibited")
        errors = ["Injected cleanup failure"] if self.faults.get("cleanup") else []
        self.restoration = {"safe_verified": not errors, "errors": errors, "simulation": True}
        return self.restoration

    def safe_pause(self):
        self.readbacks["simulated_outputs_inhibited"] = True
