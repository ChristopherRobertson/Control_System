"""Explicit synthetic virtual-clock adapter; never falls back to real devices."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import numpy as np

from .acquisition import AcquisitionStopped, ReadinessError, field


class SimulatedBurstAdapter:
    virtual_time = True

    def __init__(self, context, operation, plan, *, cancel, progress, store,
                 fail_stage=None, thermal_excursion=False, ambiguous_epoch=False, cleanup_failure=False):
        self.context, self.operation, self.plan = context, operation, plan
        self.settings, self.cancel, self.progress, self.store = plan.settings, cancel, progress, store
        self.fail_stage, self.thermal_excursion = fail_stage, thermal_excursion
        self.ambiguous_epoch, self.cleanup_failure = ambiguous_epoch, cleanup_failure
        self.now, self.clockbase, self.pump_count, self.scan_offset = 1000., 210_000_000, 0, 0
        self.pump_time = None
        self.events = []

    def check(self, stage):
        if self.cancel.is_set():
            raise AcquisitionStopped("Acquisition stopped")
        if self.fail_stage == stage:
            raise RuntimeError("Injected failure: " + stage)

    def configure(self, *, pumped=False):
        self.check("configuration")
        return {"simulation": True, "native_clock": "synthetic-HF2-clock-1", "detector_mode": self.settings.mode}

    def inspect_capabilities(self):
        self.check("capabilities")
        return {"capabilities": self.plan.capabilities.to_dict(), "simulation": True}

    def temperature(self):
        self.check("temperature")
        if self.settings.measured_temperature_k is None and not self.thermal_excursion:
            return None
        record = {"observation_id": f"synthetic-temperature-{len(self.events)}", "temperature_identity": self.settings.temperature_identity,
            "observed_utc": datetime.now(timezone.utc).isoformat(), "temperature_k": 85. if self.thermal_excursion else self.settings.measured_temperature_k,
            "uncertainty_k": self.settings.temperature_uncertainty_k, "valid_for_s": 60., "simulation": True}
        self.store.append_event("temperature", record)
        return record

    def program_block(self, block, *, pump_allowed=False):
        self.check("programming")
        frames = field(block, "frames")
        pump_frames = sum(bool(frame["channels"]["A"]["enabled"] or frame["channels"]["B"]["enabled"]) for frame in frames)
        if pump_frames != int(pump_allowed):
            raise ReadinessError("Synthetic frame pump count is inconsistent with the immutable finite plan")
        for index in range(len(frames)):
            self.check("upload")
            self.progress(stage="upload", message=f"Acknowledged timing frames {index + 1}/{len(frames)}",
                          fraction=(index + 1) / len(frames))
        self.events.append(("program", field(block, "block_id"), pump_frames))
        self.store.append_event("timing_upload", {"block_id": field(block, "block_id"), "acknowledged": len(frames), "simulation": True})

    def capture_block(self, block, *, pump_allowed=False, before_fire=None):
        self.check("acquisition")
        if pump_allowed:
            if self.pump_count:
                raise ReadinessError("Synthetic biological sample cannot receive a replacement pump")
            if before_fire:
                before_fire()
            self.pump_count += 1
            self.pump_time = self.now
        self.check("after_pump")
        count = int(field(block, "scan_count"))
        scan_duration = abs(self.settings.scan_stop_cm1 - self.settings.scan_start_cm1) / self.settings.scan_speed_cm1_s
        n = max(8, min(4096, int(scan_duration * self.settings.sample_rate_hz)))
        offset = float(field(block, "first_process_delay_s", self.settings.first_scan_delay_s))
        blocks = []
        for index in range(count):
            self.check("scan")
            times = self.now + offset + index * field(block, "frame_period_s") + np.linspace(0., scan_duration, n)
            wn = np.linspace(self.settings.scan_start_cm1, self.settings.scan_stop_cm1, n)
            elapsed = np.maximum(0., times - (self.pump_time if self.pump_time is not None else times[0]))
            baseline = np.exp(-.08 * np.exp(-((wn - (self.settings.scan_start_cm1 + 15)) / 3) ** 2))
            # Two distinct band populations and three time scales with a genuine
            # unrecovered term. The final frame is not forced to full recovery.
            loss = (.015 * np.exp(-elapsed / .08) + .025 * np.exp(-elapsed / 8.) + .04 * np.exp(-elapsed / 250.) + .012)
            shape = np.exp(-((wn - (self.settings.scan_start_cm1 + 15)) / 3) ** 2)
            shape += .7 * np.exp(-((wn - (self.settings.scan_start_cm1 + 34)) / 4) ** 2)
            delta = -loss * shape if self.pump_time is not None else np.zeros(n)
            reference = 1. + .005 * np.sin(times * .01)
            sample = reference * baseline * np.power(10., -delta)
            ticks = np.rint(times * self.clockbase).astype(np.uint64)
            native = {"sample_time_s": ticks.astype(float) / self.clockbase, "wavenumber_cm1": wn,
                "sample": sample, "scan_index": np.full(n, self.scan_offset + index, np.int64),
                "direction": np.full(n, 1 if self.settings.scan_stop_cm1 >= self.settings.scan_start_cm1 else -1, np.int8),
                "flags": np.zeros(n, np.uint32), "native_sample_ticks": ticks,
                "clockbase_hz": np.asarray(self.clockbase, np.int64), "synthetic_delta_absorbance_truth": delta}
            if self.settings.mode == "dual":
                native.update(reference=reference, reference_time_s=native["sample_time_s"].copy(),
                              reference_wavenumber_cm1=wn.copy(), native_reference_ticks=ticks.copy())
            blocks.append(native)
        native = {key: (np.concatenate([part[key] for part in blocks]) if np.asarray(blocks[0][key]).ndim else blocks[0][key]) for key in blocks[0]}
        epoch = None
        if pump_allowed and not self.ambiguous_epoch:
            epoch = {"pump_time_s": self.pump_time, "pump_timestamp_ticks": int(round(self.pump_time * self.clockbase)),
                "clock_domain": "synthetic-HF2-clock-1", "clockbase_hz": self.clockbase,
                "device_id": "synthetic-hf2", "electrically_observed": True, "independently_observed": False,
                "optical_arrival_observed": False, "time_reference": "electrical_trigger", "optical_resolution": "unresolved",
                "sample_state": self.state_evidence(), "simulation": True}
        native["time_reference"] = np.asarray("electrical_trigger")
        self.now += float(field(block, "duration_s"))
        self.scan_offset += count
        self.events.append(("capture", field(block, "block_id"), self.pump_count))
        return {"native": native, "epoch": epoch, "observed_pump_count": int(pump_allowed),
                "observed_scan_count": count, "end_native_time_s": self.now}

    def idle(self):
        self.events.append(("dark", self.now))

    def native_now(self):
        self.check("wait")
        # Advances the explicitly simulated native hardware clock, never wall time.
        step = 1.
        target = getattr(self, "wait_target", None)
        self.now += min(step, max(0., target - self.now)) if target is not None else step
        return self.now

    def state_evidence(self):
        return {key: getattr(self.settings, key) for key in ("condition_id", "sample_id", "preparation_id", "accepted_state_id",
            "matrix_id", "cell_id", "position_id", "temperature_identity", "thermal_history_id")}

    def verify_continuation(self, continuation):
        self.check("continuation")
        if self.ambiguous_epoch or continuation.get("epoch", {}).get("clockbase_hz") != self.clockbase:
            raise ReadinessError("Retained native clock is ambiguous; never replace pump")
        proof = continuation.get("state_evidence", {})
        self.pump_time = float(continuation["epoch"]["pump_time_s"])
        self.pump_count = 1
        self.now = float(proof.get("native_now_s", self.pump_time + .1))

    def restore(self):
        self.events.append(("restore", self.pump_count))
        return {"safe_verified": not self.cleanup_failure,
                "errors": ["Injected restoration failure"] if self.cleanup_failure else [],
                "records": {"synthetic_pump_count": self.pump_count, "events": deepcopy(self.events)}}
