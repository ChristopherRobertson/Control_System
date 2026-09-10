"""Installed sparse-probe adapters. Construction never opens a device.

The HF2LI measures the signed area of its calibrated response to one selected IR
pulse. Pulse isolation, reference lock, aperture and reset are qualifications, not
consequences of programming a nanosecond delay. No optional DIO1 gate is assumed.
"""
from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
from dataclasses import asdict, is_dataclass
import math
import time
from collections.abc import Mapping

import numpy as np

KERNEL_ID = "sparse_single_probe_demod_impulse"


class ReadinessError(RuntimeError):
    pass


def data(value):
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return {str(k): data(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [data(v) for v in value]
    return value


def settings_data(plan):
    return data(getattr(plan, "settings", plan))


def installed_readiness(configuration, settings, qualification):
    """Pure checks of installed routes and a promoted kernel's stated domain."""
    reasons = []
    devices = configuration.get("devices", {})
    expected = {"t660_1": {"A": "hf2li_extref", "B": "mircat_trig_in", "C": "t660_2_trig_in", "D": None},
                "t660_2": {"A": "ndyag_fire", "B": "ndyag_q_switch", "C": "mircat_db9_pin_4_process_trigger", "D": None}}
    for unit, routes in expected.items():
        actual = devices.get(unit, {}).get("channel_map", {})
        for channel, route in routes.items():
            if channel not in actual or actual[channel] != route:
                reasons.append(f"Installed {unit} {channel} route is not {route!r}; no alternative route is assumed")
    requirements = {
        "selected_probe_qualified": "One and only one MIRcat optical probe per selected cycle is unqualified",
        "sparse_reference_lock_qualified": "HF2LI DIO0 reference lock at the selected sparse probe cadence is unqualified",
        "impulse_area_qualified": "HF2LI signed impulse-area gain, integration aperture and filter history are unqualified",
        "tee_transfer_qualified": "Installed sample/reference tee loading, receiver transfer and skew are unqualified (MS-02.1)",
        "electrical_timing_qualified": "T660 route latency, trigger closure and electrical timing are unqualified",
        "optical_timing_qualified": "Sample-plane optical time zero and IRF are unqualified",
        "reset_equivalence_qualified": "Equivalent-state recovery at the selected cadence has not been demonstrated",
        "probe_marker_qualified": "Observed MIRcat DIO19 pulse identity/count and HF2 timing-stream coverage are unqualified",
    }
    for key, reason in requirements.items():
        if qualification.get(key) is not True:
            reasons.append(reason)
    if qualification.get("kernel_id") != KERNEL_ID:
        reasons.append("A promoted sparse_single_probe_demod_impulse kernel is required; continuous slow averaging is not equivalent-time acquisition")
    if not qualification.get("hf2li"):
        reasons.append("Promoted independent HF2LI sample/reference settings and aggregate readout qualification are missing")
    domain = {k: v for k, v in settings.items() if k not in ("qualification", "calibration_ids")}
    if data(qualification.get("settings_domain")) != data(domain):
        reasons.append("Promoted kernel settings_domain must match scientific settings excluding qualification and calibration_ids")
    if str(settings.get("profile_id", settings.get("profile", ""))).startswith("77"):
        reasons.append("Installed adapters have no cryogenic temperature readback or automatic qualified fresh-position/thermal reset; provide the missing commissioned host capability")
    reasons.append("Normal installed detector wiring has no simultaneous sample-plane optical pump observation; no genuine per-event optical evidence adapter is available")
    if not qualification.get("laser_safety_approved"):
        reasons.append("Applicable laser safety authorization is absent from the promoted operating selection")
    return tuple(reasons)


def _query(record, name):
    item = record[name]
    if not item.get("ok"):
        raise ReadinessError(f"Required installed readback {name} failed: {item}")
    return str(item["response"]).strip()


def _seconds(value):
    text = str(value).strip().lower()
    for suffix, scale in (("ns", 1e-9), ("us", 1e-6), ("ms", 1e-3), ("s", 1)):
        if text.endswith(suffix):
            return float(text[:-len(suffix)]) * scale
    return float(text)


def _flatten_native(records, demod):
    """Extract a view of a demod; the source records are retained untouched."""
    chunks = []
    for record in records:
        for path, payload in record.get("data", {}).items():
            if f"/demods/{demod}/sample" not in path.lower():
                continue
            chunks.extend(payload if isinstance(payload, (list, tuple)) else [payload])
    keys = set().union(*(chunk.keys() for chunk in chunks)) if chunks else set()
    return {key: np.concatenate([np.asarray(c[key]).reshape(-1) for c in chunks if key in c]) for key in keys}


def integrate_impulse(stream, probe_epoch_s, *, clockbase, calibration):
    """Linear signed projection plus measured-aperture trapezoid integration.

    No resampling or gap filling is performed. The gain includes the measured
    aperture loss and mixer phase. Every coordinate remains an HF2 clock tick;
    the epoch is an observed electrical marker, never an optical timestamp.
    """
    ticks = np.asarray(stream.get("timestamp", []))
    x, y = np.asarray(stream.get("x", [])), np.asarray(stream.get("y", []))
    if len(ticks) < 3 or len(x) != len(ticks) or len(y) != len(ticks):
        raise ValueError("Incomplete native HF2LI impulse x/y/timestamp support")
    t = ticks.astype(np.float64) / float(clockbase) - float(probe_epoch_s)
    if np.any(np.diff(t) <= 0):
        raise ValueError("Native HF2LI timestamps are duplicated or nonmonotonic")
    phase = float(calibration["projection_phase_rad"])
    projected = x * math.cos(phase) + y * math.sin(phase)
    lo, hi = map(float, calibration["integration_window_s"])
    blo, bhi = map(float, calibration["baseline_window_s"])
    gain = float(calibration["impulse_area_gain"])
    if not (lo < hi and blo < bhi <= lo and gain > 0):
        raise ValueError("Invalid calibrated integration/baseline aperture or impulse gain")
    integration = (t >= lo) & (t <= hi)
    background = (t >= blo) & (t <= bhi)
    if integration.sum() < 3 or background.sum() < 3:
        raise ValueError("Incomplete measured impulse or pre-probe baseline aperture")
    ti = t[integration]
    max_gap = float(calibration["maximum_sample_gap_s"])
    if np.max(np.diff(ti)) > max_gap or ti[0] - lo > max_gap or hi - ti[-1] > max_gap:
        raise ValueError("Missing native support inside the calibrated impulse aperture")
    if not np.isfinite(projected[integration | background]).all():
        raise ValueError("Nonfinite native HF2LI impulse sample")
    base = float(np.mean(projected[background]))
    # Correlated detector noise requires measured covariance; sample scatter is
    # not silently converted to independent-point uncertainty.
    value = float(np.trapezoid(projected[integration] - base, ti) / gain)
    result = {"timestamp_s": np.array([probe_epoch_s]), "value": np.array([value]),
              "valid": np.array([True]), "group_delay_s": 0.0,
              "estimator": "calibrated_signed_impulse_area", "baseline_value": base,
              "calibration_id": calibration["calibration_id"]}
    if "integrated_variance" in calibration and "gain_relative_variance" in calibration:
        if float(calibration["integrated_variance"]) < 0 or float(calibration.get("gain_relative_variance", 0)) < 0:
            raise ValueError("Calibrated integrated/gain variances must be nonnegative")
        result["variance"] = np.array([float(calibration["integrated_variance"]) + value * value * float(calibration.get("gain_relative_variance", 0))])
    return result


class InstalledAdapter:
    """Calls only installed services supplied by the scoped host context."""
    def __init__(self, context, operation, plan, *, check=lambda: None, progress=lambda *a: None, retain=lambda *a: None):
        self.context, self.operation, self.plan = context, operation, plan
        self.settings = settings_data(plan)
        self.check, self.progress, self.retain = check, progress, retain
        self.devices, self.before, self.readbacks = {}, {}, {}
        self.qualification = {}
        self.pending_native = []
        self.touched = False
        self.hf_snapshot_preset = None

    def _scope(self):
        return self.context.hardware_scope(self.operation) if self.operation.hardware else nullcontext()

    def prepare(self):
        self.check()
        # Loading a promoted bundle is read-only; no raw campaign data can grant
        # connected readiness, and no hash is used as an operational gate.
        for bundle_id in self.settings.get("calibration_ids", []):
            bundle = self.context.promoted_bundle(bundle_id)
            manifest = bundle.manifest if hasattr(bundle, "manifest") else bundle.get("manifest", bundle)
            payload = manifest.get("nanosecond_stroboscopy")
            if payload:
                self.qualification.update(deepcopy(payload))
        reasons = installed_readiness(data(self.operation.configuration), self.settings, self.qualification)
        if reasons:
            raise ReadinessError("Connected Start is not ready:\n" + "\n".join(reasons))
        with self._scope():
            for name in ("t660_1", "t660_2", "hf2li", "mircat"):
                self.check()
                device = self.context.devices.create(name, self.operation)
                self.devices[name] = device
                self.touched = True
                (device.initialize if name == "mircat" else device.connect)()
            for name in ("t660_1", "t660_2"):
                unit = self.devices[name]
                saved = unit.read_active_settings()
                refs = {i: int(unit.command(f"TIME:RELTo{i}?")) for i in range(1, 9)}
                self.before[name] = {"readback": saved, "references": refs}
                self._validate_clock(name, saved)
            hf = self.devices["hf2li"]
            from control_app.devices.hf2li_service import HF2LIPreset
            cfg = self.qualification["hf2li"]
            self.hf_snapshot_preset = HF2LIPreset("nanosecond_stroboscopy_restoration", {
                **cfg, "demodulators": [{"index": i} for i in range(6)]})
            self.before["hf2li"] = hf.export_settings_snapshot(preset=self.hf_snapshot_preset)
            if self.before["hf2li"].get("read_errors"):
                raise ReadinessError("HF2LI initial settings preservation is incomplete")
            qcl = self.devices["mircat"]
            index = int(self.qualification["qcl_index"])
            self.before["mircat"] = {"trigger": qcl.get_wavelength_trigger_params(), "qcl": index,
                "pulse_rate_hz": qcl.get_qcl_pulse_rate(index), "pulse_width_ns": qcl.get_qcl_pulse_width(index),
                "current_ma": qcl.get_qcl_current(index), "state": data(qcl.read_state())}
            self._inhibit()
            cfg = self.qualification["hf2li"]
            hf.configure_demodulators([{"index": i, "enable": False} for i in range(6)])
            hf.configure_signal_inputs(cfg["signal_inputs"])
            hf.configure_pll(cfg["pll"])
            hf.configure_demodulators(cfg["demodulators"])
            hf.sync()
            after = hf.export_settings_snapshot(preset=self.hf_snapshot_preset)
            self.readbacks["hf2li"] = after
            self._validate_hf(after, cfg)
            limits = qcl.get_qcl_pulse_limits(index)
            rate, width = self.plan.timing["input_frequency_hz"], float(self.qualification["probe_width_ns"])
            if rate > limits["max_pulse_rate_hz"] or width > limits["max_pulse_width_ns"] or rate * width * 1e-9 * 100 > limits["max_duty_cycle"]:
                raise ReadinessError("Selected sparse probe exceeds installed MIRcat pulse or duty readback")
            self.readbacks["mircat_pulse"] = qcl.set_qcl_pulse_params(qcl=index, pulse_rate_hz=rate,
                pulse_width_ns=width, current_ma=float(self.qualification["probe_current_ma"]))
            self.readbacks["clockbase"] = hf.get_clockbase()
            self.readbacks["qualification"] = deepcopy(self.qualification)
            self.retain("configuration", self.readbacks)
        return deepcopy(self.readbacks)

    def _validate_clock(self, name, saved):
        expected = "IN" if name == "t660_1" else "OUT"
        if _query(saved["queries"], "clock_connector_mode").upper() != expected:
            raise ReadinessError(f"{name} shared 10 MHz clock connector readback must be {expected}")
        if name == "t660_1" and _query(saved["queries"], "clock_lock_status").upper() not in ("1", "LOCKED", "LOCK"):
            raise ReadinessError("T660-1 shared clock lock is not observed")

    def _validate_hf(self, after, cfg):
        if after.get("read_errors"):
            raise ReadinessError("HF2LI configured readback incomplete")
        hf = self.devices["hf2li"]
        expected_indices = {0, 2, 3} if self.settings["mode"] == "dual" else {0, 2}
        enabled = {d["index"] for d in cfg["demodulators"] if d.get("enable")}
        if enabled != expected_indices:
            raise ReadinessError("Maintained HF2 detector roles are sample demod 0, reference demod 3, timing demod 2")
        total = 0.0
        for d in cfg["demodulators"]:
            if not d.get("enable"):
                continue
            for key, node in (("rate_sps", "rate"), ("timeconstant_s", "timeconstant"), ("order", "order"), ("adcselect", "adcselect")):
                if key in d:
                    actual = after["nodes"][f"/{hf.device_id}/demods/{d['index']}/{node}"]["value"]
                    if not math.isclose(float(actual), float(d[key]), rel_tol=1e-9, abs_tol=1e-12):
                        raise ReadinessError(f"HF2LI demod {d['index']} {key} differs from promoted selection")
            total += float(d["rate_sps"])
        if total > float(cfg["qualified_aggregate_rate_sps"]):
            raise ReadinessError("HF2LI aggregate stream rate exceeds the jointly qualified readout")
        # These are retained connected observations selected by the qualified
        # device node map; no unsupported gate or receiver is manufactured.
        for path, expected in cfg["required_readbacks"].items():
            if path not in after["nodes"] or after["nodes"][path]["value"] != expected:
                raise ReadinessError(f"Required HF2LI lock/clock/receiver readback failed: {path}")

    def tune(self, wavenumber):
        with self._scope():
            self.check()
            qcl = self.devices["mircat"]
            self._inhibit()
            qcl.set_external_trigger_params(wavenumber_cm1=wavenumber)
            qcl.tune_to_wavenumber(wavenumber, qcl=int(self.qualification["qcl_index"]))
            deadline = time.monotonic() + float(self.qualification["tune_timeout_s"])
            while not qcl.is_tuned():
                self.check()
                if time.monotonic() >= deadline:
                    raise ReadinessError("MIRcat Tuned readiness deadline expired; no pump was retried")
                time.sleep(.025)
            self._wait(float(self.qualification["settling_s"]), "tuning/settling")
            actual = qcl.get_actual_wavelength()
            if actual.get("units") not in ("cm-1", "cm^-1", "cm1", "wavenumber_cm1") or abs(float(actual["value"]) - wavenumber) > float(self.qualification["wavenumber_tolerance_cm1"]):
                raise ReadinessError("MIRcat actual wavenumber does not satisfy the selected measured coordinate")
            self.readbacks["wavelength"] = actual
            if not qcl.is_laser_armed():
                qcl.arm()
            qcl.turn_emission_on(approved_laser_safety_condition=True)

    def _wait(self, duration, stage):
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            self.check()
            self.progress(stage, 0, 1, f"{max(0, deadline-time.monotonic()):.2f} s remaining; qualified minimum interval")
            time.sleep(min(.05, max(0, deadline-time.monotonic())))

    def acquire(self, event, *, kind="measurement"):
        from .timing import compile_timing
        ev = data(event)
        self.pending_native = []
        with self._scope():
            self.check()
            if kind == "measurement" and ev["condition"] in ("pump_on", "pump_only"):
                self._wait(float(self.settings["reset_interval_s"]), "recovery waits")
            timing = compile_timing(getattr(self.plan, "settings", self.settings))
            recipe = deepcopy(timing.t660_1_recipe)
            frames = deepcopy(ev["frames"])
            if kind != "measurement":
                for frame in frames:
                    frame["channels"]["A"]["enabled"] = False
                    frame["channels"]["B"]["enabled"] = False
            t1, t2, hf = (self.devices[k] for k in ("t660_1", "t660_2", "hf2li"))
            self._inhibit()
            t1.apply_recipe(recipe)
            previous_counter = t2.get_shot_count()
            upload = t2.preload_frame_table(frames, predivider=timing.predivider,
                input_frequency_hz=timing.input_frequency_hz, cancel_check=self.check,
                progress=lambda done, total: self.progress("acknowledged timing-table upload", done, total, ev["event_id"]))
            upload["counter_before_explicit_burst"] = previous_counter
            upload["biological_event_identity"] = ev["event_id"]
            self.retain(f"upload-{ev['event_id']}", upload)
            hf.start_acquisition(demodulators=[0, 2, 3] if self.settings["mode"] == "dual" else [0, 2])
            try:
                # Acquisition is subscribed before either precise edge source.
                t2.start_frame_table()
                t1.set_trigger_source("SYN")
                t1.command("START", expect_response=False)
                deadline = time.monotonic() + len(frames) * timing.frame_period_s + float(self.qualification["retrieval_timeout_s"])
                while True:
                    self.check()
                    native = hf.read_acquisition(min(.1, timing.frame_period_s))
                    self.pending_native.append(native)
                    self.retain(f"native-{ev['event_id']}-{len(self.pending_native):06d}", native)
                    state = t2.get_frames_status()
                    if state == "DONE":
                        break
                    if state == "ERROR" or time.monotonic() >= deadline:
                        raise ReadinessError(f"Finite event table {state}; retained partial native data; pump is never retried")
                self._inhibit()
                native = hf.read_acquisition(float(self.qualification["retrieval_tail_s"]))
                self.pending_native.append(native)
                self.retain(f"native-{ev['event_id']}-{len(self.pending_native):06d}", native)
                shots = t2.get_shot_count()
                if shots != len(frames):
                    raise ValueError(f"T660 observed shot count {shots} differs from planned {len(frames)}")
                result = self._extract(ev, kind)
                result["readbacks"] = {"t660_shot_count": shots, "upload": upload, "wavelength": deepcopy(self.readbacks["wavelength"])}
                return result
            finally:
                # Any stop failure propagates to runner cleanup, which tries
                # every device independently and retains the actual outcome.
                self._inhibit()
                hf.stop_acquisition()

    def _extract(self, ev, kind):
        cb = self.readbacks["clockbase"]
        timing = _flatten_native(self.pending_native, 2)
        ticks = np.asarray(timing.get("timestamp", []))
        dio = np.asarray(timing.get("dio", []), dtype=np.uint32)
        if len(ticks) != len(dio) or len(ticks) < 2:
            raise ValueError("Observed DIO19 probe identity stream is missing")
        high = (dio & (1 << 19)) != 0
        edges = np.flatnonzero(high[1:] & ~high[:-1]) + 1
        frame_index = int(ev["frame_index"])
        if len(edges) != len(ev["frames"]) or frame_index >= len(edges):
            raise ValueError("Observed probe pulse count differs from the complete finite burst; no event-to-pulse assignment invented")
        epochs = ticks[edges].astype(np.float64) / cb
        period = float(self.plan.timing["frame_period_s"])
        if np.any(np.abs(np.diff(epochs[:len(ev["frames"])]) - period) > float(self.qualification["probe_period_tolerance_s"])):
            raise ValueError("Observed probe pulse epochs do not match the planned frame cadence")
        epoch = float(epochs[frame_index])
        result = {k: v for k, v in ev.items() if k != "frames"}
        result.update(condition=ev["condition"] if kind == "measurement" else "unpumped",
            sample=integrate_impulse(_flatten_native(self.pending_native, 0), epoch, clockbase=cb,
                                     calibration=self.qualification["impulse_calibration"]["sample"]),
            native_device_data=deepcopy(self.pending_native), quality_flags=[],
            observed_electrical_delay_ns=None, calibrated_optical_delay_ns=None,
            acquisition_kernel={"kernel_id": KERNEL_ID, "qualification": self.qualification["qualification_id"]},
            pump_evidence={"commanded": kind == "measurement" and ev["condition"] == "pump_on",
                           "optical_pulse_count": None if kind == "measurement" and ev["condition"] == "pump_on" else 0, "optical_observation": "No sample-plane pump detector in normal dual receiver topology"},
            reset_evidence={"method": "qualified_passive_recovery_envelope", "wait_s": self.settings["reset_interval_s"],
                            "qualification_id": self.qualification["qualification_id"], "equivalent": True},
            measured_wavenumber_cm1=float(self.readbacks["wavelength"]["value"]))
        if self.settings["mode"] == "dual":
            result["reference"] = integrate_impulse(_flatten_native(self.pending_native, 3), epoch, clockbase=cb,
                calibration=self.qualification["impulse_calibration"]["reference"])
            if "sample_reference_covariance" in self.qualification:
                result["sample_reference_covariance"] = self.qualification["sample_reference_covariance"]
        # Calibration maps programmed delay only within its accepted domain; it
        # is not relabelled as an independently observed optical event timestamp.
        result["calibrated_optical_delay_ns"] = ev["electrical_delay_ns"] + float(self.qualification["optical_delay_offset_ns"])
        result["optical_delay_source"] = self.qualification["optical_timing_calibration_id"]
        if result["pump_evidence"]["commanded"]:
            result["quality_flags"].append("per_event_optical_pump_unobserved")
        return result

    def _inhibit(self):
        errors = []
        for name in ("t660_2", "t660_1"):
            unit = self.devices.get(name)
            if unit is None:
                continue
            for callback in (lambda u=unit: u.set_trigger_source("OFF"),
                             lambda u=unit: u.command("STOP", expect_response=False),
                             *[lambda u=unit, c=c: u.disable_channel(c) for c in "ABCD"]):
                try:
                    callback()
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
            if name == "t660_2":
                callbacks = [lambda u=unit: u.command("TFRame:STOp", expect_response=False),
                    *[lambda u=unit, bank=stage: u.configure_train(count=0, stage=bank)
                      for stage in ("ACTIVE", "NEXT", "QUEUE")]]
                for callback in callbacks:
                    try:
                        callback()
                    except Exception as exc:
                        errors.append(f"{name}: {exc}")
        if errors:
            raise RuntimeError("; ".join(errors))

    def restore(self):
        """Safe idle, restore original settings, verify, and close all sessions."""
        report = {"safe_verified": True, "errors": [], "devices": {},
                  "safe_idle_exclusions": "Emission/arming, triggers, channels and frames remain inhibited; counters and overwritten frame RAM remain retained history"}
        def attempt(label, callback):
            try:
                report["devices"][label] = callback()
            except Exception as exc:
                report["errors"].append(f"{label}: {type(exc).__name__}: {exc}")
        with self._scope():
            attempt("timing_inhibit", self._inhibit)
            qcl = self.devices.get("mircat")
            if qcl:
                attempt("mircat_emission_off", qcl.turn_emission_off)
                attempt("mircat_disarm", qcl.disarm)
                if "mircat" in self.before:
                    def restore_qcl():
                        before = self.before["mircat"]
                        qcl.set_qcl_pulse_params(**{k: before[k] for k in ("qcl", "pulse_rate_hz", "pulse_width_ns", "current_ma")})
                        allowed = ("pulse_mode", "process_trigger_mode", "start", "stop", "interval", "units", "dwell_us", "after_off_us")
                        qcl.set_wavelength_trigger_params(**{k: v for k, v in before["trigger"].items() if k in allowed})
                        after = {"trigger": qcl.get_wavelength_trigger_params(), "state": data(qcl.read_state())}
                        for key in allowed:
                            if key not in before["trigger"]:
                                continue
                            expected, actual = before["trigger"][key], after["trigger"].get(key)
                            equal = (isinstance(actual, (int, float)) and math.isclose(float(actual), float(expected), rel_tol=1e-6, abs_tol=1e-9))
                            if not equal:
                                raise RuntimeError(f"MIRcat trigger {key} did not restore: {actual!r} != {expected!r}")
                        if qcl.is_emission_on() or qcl.is_laser_armed():
                            raise RuntimeError("MIRcat safe idle readback failed")
                        for key, method in (("pulse_rate_hz", qcl.get_qcl_pulse_rate), ("pulse_width_ns", qcl.get_qcl_pulse_width), ("current_ma", qcl.get_qcl_current)):
                            if not math.isclose(method(before["qcl"]), before[key], rel_tol=1e-6):
                                raise RuntimeError(f"MIRcat {key} did not restore")
                        return {"before": before, "after": after}
                    attempt("mircat_settings", restore_qcl)
            hf = self.devices.get("hf2li")
            if hf:
                attempt("hf2li_unsubscribe", hf.stop_acquisition)
                if "hf2li" in self.before:
                    def restore_hf():
                        snapshot = deepcopy(self.before["hf2li"])
                        enables = {p: v for p, v in snapshot["nodes"].items() if "/demods/" in p and p.endswith("/enable")}
                        hf.configure_demodulators([{"index": i, "enable": False} for i in range(6)])
                        snapshot["nodes"] = {p: v for p, v in snapshot["nodes"].items() if p not in enables}
                        hf.reload_settings_snapshot(snapshot)
                        hf.reload_settings_snapshot({"nodes": enables})
                        after = hf.export_settings_snapshot(preset=self.hf_snapshot_preset)
                        check = deepcopy(self.before["hf2li"])
                        check["nodes"] = {k: v for k, v in check["nodes"].items() if "/oscs/" not in k}
                        comparison = hf.compare_settings_snapshots(check, after)
                        if not comparison["match"] or after.get("read_errors"):
                            raise RuntimeError(f"HF2LI restoration readback failed: {comparison}")
                        return {"before": self.before["hf2li"], "after": after, "comparison": comparison}
                    attempt("hf2li_settings", restore_hf)
            for name in ("t660_1", "t660_2"):
                if name in self.before:
                    attempt(name, lambda n=name: self._restore_timing(n))
            for name, device in reversed(tuple(self.devices.items())):
                attempt(f"{name}_close", device.deinitialize if name == "mircat" else device.close)
        report["safe_verified"] = not report["errors"]
        return report

    def _restore_timing(self, name):
        unit, before = self.devices[name], self.before[name]
        saved, refs = before["readback"], before["references"]
        relative = {edge: _seconds(_query(saved["channels"][c], key)) for c, edges in zip("ABCD", ((1, 2), (3, 4), (5, 6), (7, 8))) for edge, key in zip(edges, ("delay_edge", "width_edge"))}
        absolute = {0: 0.}
        def resolve(edge, visited=()):
            if edge in absolute:
                return absolute[edge]
            if edge in visited or refs[edge] not in range(9):
                raise RuntimeError("Invalid original T660 edge references")
            absolute[edge] = relative[edge] + resolve(refs[edge], (*visited, edge))
            return absolute[edge]
        for edge in refs:
            resolve(edge)
        for c in "ABCD":
            unit.set_channel_timing_mode(c, "rise_fall")
        for edge in range(1, 9):
            unit.command(f"TIME:RELTo{edge} 0", expect_response=False)
        for rising, falling in ((1, 2), (3, 4), (5, 6), (7, 8)):
            unit.command(f"TIME:QUEue{rising} 0s", expect_response=False)
            unit.command(f"TIME:QUEue{falling} {absolute[falling]:.15g}s", expect_response=False)
            unit.command(f"TIME:QUEue{rising} {absolute[rising]:.15g}s", expect_response=False)
        unit.command("TIME:COMmit", expect_response=False)
        for edge, ref in refs.items():
            unit.command(f"TIME:RELTo{edge} {ref}", expect_response=False)
        recipe = {"stop_first": True, "trigger_source": "OFF", "predivider": int(_query(saved["queries"], "predivider")),
                  "clock": {"frequency": _query(saved["queries"], "synth_frequency")}, "gate_mode": 0, "burst_enabled": False,
                  "external_trigger": {"polarity": _query(saved["queries"], "trigger_input_polarity"),
                                       "termination": _query(saved["queries"], "trigger_input_termination"),
                                       "threshold_v": float(_query(saved["queries"], "trigger_input_threshold_v"))},
                  "channels": {c: {"enabled": False, "polarity": _query(v, "polarity"),
                       "termination": _query(v, "termination"), "timing_mode": _query(v, "timing_mode")} for c, v in saved["channels"].items()}}
        unit.apply_recipe(recipe)
        after = unit.read_active_settings()
        if _query(after["queries"], "trigger_source").upper() != "OFF":
            raise RuntimeError("T660 trigger source is not inhibited")
        for channel in "ABCD":
            if _query(after["channels"][channel], "enabled").upper() not in ("0", "OFF"):
                raise RuntimeError(f"T660 channel {channel} remains enabled")
            for key in ("delay_edge", "width_edge"):
                if not math.isclose(_seconds(_query(after["channels"][channel], key)), _seconds(_query(saved["channels"][channel], key)), abs_tol=1e-11, rel_tol=0):
                    raise RuntimeError(f"T660 channel {channel} {key} did not restore")
        if name == "t660_2" and unit.get_frames_status() != "OFF":
            raise RuntimeError("T660-2 frames remain active")
        for edge, ref in refs.items():
            if int(unit.command(f"TIME:RELTo{edge}?")) != ref:
                raise RuntimeError(f"T660 edge {edge} reference did not restore")
        return {"before": before, "after": after}
