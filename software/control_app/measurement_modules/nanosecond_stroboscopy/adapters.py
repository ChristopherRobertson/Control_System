"""Owned installed-device acquisition of sparse-probe DC detector impulses.

HF2LI records both quadratures with a zero-frequency internal oscillator. Raw
complex area is retained in V s. Missing optical calibration limits scientific
interpretation and never prevents ordinary detector recording.
"""
from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
from dataclasses import asdict, is_dataclass
import math
import time
from collections.abc import Mapping

import numpy as np

from .settings import KERNEL_ID, optical_pulse_errors


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


def installed_readiness(configuration, settings=None, qualification=None):
    """Only concrete installed-route conflicts affect device configuration.

    Missing calibration, sample metadata and scientific qualification are result
    limitations. They do not prevent recording the installed detector signals.
    """
    reasons = []
    devices = configuration.get("devices", {})
    expected = {"t660_1": {"A": "hf2li_extref", "B": "mircat_trig_in", "C": "t660_2_trig_in", "D": None},
                "t660_2": {"A": "ndyag_fire", "B": "ndyag_q_switch", "C": "mircat_db9_pin_4_process_trigger", "D": None}}
    for unit, routes in expected.items():
        actual = devices.get(unit, {}).get("channel_map", {})
        for channel, route in actual.items():
            if channel in routes and route != routes[channel]:
                reasons.append(f"Installed {unit} {channel} is routed to {route!r}; this kernel uses {routes[channel]!r}")
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


def _validate_optical_pulses(internal_rate_hz, optical_width_ns, external_rate_hz, limits):
    """Validate actual optical parameters; electrical TTL width is unrelated."""
    values = (internal_rate_hz, optical_width_ns, external_rate_hz,
              limits["max_pulse_rate_hz"], limits["max_pulse_width_ns"], limits["max_duty_cycle"])
    if not all(math.isfinite(float(value)) and float(value) > 0 for value in values):
        raise ReadinessError("MIRcat QCL 1 optical pulse parameters and vendor limits must be finite and positive")
    width_s = float(optical_width_ns)*1e-9
    configured_duty = float(internal_rate_hz)*width_s
    external_duty = float(external_rate_hz)*width_s
    vendor_duty = float(limits["max_duty_cycle"])/100.0
    errors = optical_pulse_errors(internal_rate_hz, optical_width_ns,
        max_rate_hz=float(limits["max_pulse_rate_hz"]), max_width_ns=float(limits["max_pulse_width_ns"]),
        max_duty_fraction=vendor_duty, external_probe_rate_hz=external_rate_hz)
    if errors:
        raise ReadinessError("MIRcat QCL 1: " + "; ".join(errors))
    return {"configured_duty_cycle_fraction": configured_duty, "external_probe_duty_cycle_fraction": external_duty,
            "maximum_duty_cycle_fraction": .30, "vendor_maximum_duty_cycle_fraction": vendor_duty}


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


def _relative_seconds(ticks, epoch_ticks, clockbase):
    """Subtract integer device epochs before any floating-point conversion."""
    values = np.asarray(ticks)
    if values.dtype.kind in "ui":
        delta = (values.astype(np.uint64) - np.uint64(epoch_ticks)).view(np.int64)
        return delta.astype(np.float64)/float(clockbase)
    return (values.astype(np.float64)-float(epoch_ticks))/float(clockbase)


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
    t = _relative_seconds(ticks, round(float(probe_epoch_s)*float(clockbase)), clockbase)
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
        """Resolve Auto choices from real devices while this operation owns them."""
        from control_app.devices.hf2li_service import HF2LIPreset
        from .planner import build_plan
        self.check()
        reasons = installed_readiness(data(self.operation.configuration), self.settings)
        if reasons:
            raise ReadinessError("; ".join(reasons))
        optional = self.settings.get("qualification", {})
        self.qualification = dict(optional) if isinstance(optional, Mapping) else {}
        # Optional calibration enriches results; unavailable records stay visible
        # as provenance warnings rather than vetoing ordinary raw acquisition.
        self.readbacks["calibration_warnings"] = []
        for bundle_id in self.settings.get("calibration_ids", []):
            try:
                bundle = self.context.promoted_bundle(bundle_id)
                manifest = bundle.manifest if hasattr(bundle, "manifest") else bundle.get("manifest", bundle)
                self.qualification.update(deepcopy(manifest.get("nanosecond_stroboscopy", {})))
            except Exception as exc:
                self.readbacks["calibration_warnings"].append(f"{bundle_id}: {exc}")
        with self._scope():
            for name in ("t660_1", "t660_2", "hf2li", "mircat"):
                self.check()
                device = self.context.devices.create(name, self.operation)
                self.devices[name] = device
                self.touched = True
                (device.initialize if name == "mircat" else device.connect)()
            for name in ("t660_1", "t660_2"):
                unit = self.devices[name]
                self.before[name] = {"readback": unit.read_active_settings(),
                    "references": {i: int(unit.command(f"TIME:RELTo{i}?")) for i in range(1, 9)}}
            self.before["t660_1"]["burst"] = {"pulses": int(self.devices["t660_1"].command("BURst:PULse?")),
                "triggers": int(self.devices["t660_1"].command("BURst:TRIGger?"))}
            hf = self.devices["hf2li"]
            self.hf_snapshot_preset = HF2LIPreset("nanosecond_stroboscopy_dc_restoration", {
                "demodulators": [{"index": i, "sinc": False, "phaseshift": 0.0} for i in range(6)], "oscillators": [{"index": 0}],
                "pll": {"index": 0}})
            self.before["hf2li"] = hf.export_settings_snapshot(preset=self.hf_snapshot_preset)
            if self.before["hf2li"].get("read_errors"):
                raise ReadinessError("HF2LI settings could not be preserved before configuration: " + str(self.before["hf2li"]["read_errors"]))
            qcl = self.devices["mircat"]
            # This installation contains exactly QCL 1. Historical selectors
            # remain provenance and never choose a device or tuning range.
            qcls = [{"qcl": 1, "pulse_rate_hz": qcl.get_qcl_pulse_rate(1),
                "pulse_width_ns": qcl.get_qcl_pulse_width(1), "current_ma": qcl.get_qcl_current(1),
                "range": qcl.get_qcl_tuning_range(1), "limits": qcl.get_qcl_pulse_limits(1)}]
            self.before["mircat"] = {"trigger": qcl.get_wavelength_trigger_params(),
                "qcls": qcls, "state": {"emission_on": qcl.is_emission_on(), "armed": qcl.is_laser_armed(), "qcl": 1}}
            self._inhibit()
            qcl.turn_emission_off()
            self.capabilities = self._capabilities()
            self.plan = build_plan(getattr(self.plan, "settings", self.settings), capabilities=self.capabilities)
            if self.plan.errors:
                raise ValueError("; ".join(self.plan.errors))
            resolved = getattr(self.plan, "resolved_settings", None) or self.plan.settings
            self.settings = data(resolved)
            if not self.plan.timing or not self.plan.events:
                raise ValueError("Installed numeric readbacks did not resolve a finite timing sequence: " + "; ".join(self.plan.readiness))
            inputs = {f"ch{i+1}": {"index": i, "ac": False, "differential": False,
                "impedance_50ohm": bool(self._hf_before(f"sigins/{i}/imp50")),
                "range_v": float(self._hf_before(f"sigins/{i}/range"))} for i in (0, 1)}
            active = [0, 3] if self.settings["mode"] == "dual" else [0]
            tc, order, rate = (self.settings[k] for k in ("filter_time_constant_s", "filter_order", "hf2li_rate_hz"))
            demods = [{"index": i, "enable": i in active,
                **({"adcselect": 0 if i == 0 else 1, "oscselect": 0, "harmonic": 1,
                    "order": order if i == 0 else self.settings.get("reference_filter_order") or self.capabilities["reference_filter_order"],
                    "timeconstant_s": tc if i == 0 else self.settings.get("reference_filter_time_constant_s") or self.capabilities["reference_filter_time_constant_s"],
                    "rate_sps": rate if i == 0 else self.settings.get("reference_hf2li_rate_hz") or self.capabilities["reference_hf2li_rate_hz"],
                    "trigger": 0, "sinc": False} if i in active else {})} for i in range(6)]
            hf.configure_demodulators([{"index": i, "enable": False} for i in range(6)])
            hf.configure_pll({"index": 0, "enable": False})
            hf.configure_oscillators([{"index": 0, "frequency_hz": 0.0}])
            hf.configure_signal_inputs(inputs)
            hf.configure_demodulators(demods)
            hf.sync()
            after = hf.export_settings_snapshot(preset=self.hf_snapshot_preset)
            if after.get("read_errors"):
                raise ReadinessError("HF2LI configured readback failed: " + str(after["read_errors"]))
            for index in (0, 1):
                if after["nodes"][f"/{hf.device_id}/sigins/{index}/ac"]["value"] != 0:
                    raise ReadinessError(f"HF2LI signal input {index} did not accept DC coupling")
            if after["nodes"][f"/{hf.device_id}/plls/0/enable"]["value"] != 0:
                raise ReadinessError("HF2LI external PLL did not disable for DC demodulation")
            actual_frequency = float(hf.get_oscillator_frequency(0))
            if actual_frequency != 0.0:
                raise ReadinessError(f"HF2LI rejected internal DC demodulation: requested 0 Hz, read back {actual_frequency:g} Hz")
            self.readbacks.update(hf2li=after, clockbase=hf.get_clockbase(), capabilities=self.capabilities,
                resolved_settings=self.settings, resolved_plan=data(self.plan), demodulation="internal_zero_frequency",
                actual_oscillator_hz=actual_frequency)
            self.detector_settings = {}
            for demod in active:
                base = f"/{hf.device_id}/demods/{demod}/"
                get = lambda key: after["nodes"][base+key]["value"]
                self.detector_settings[demod] = {"timeconstant_s": float(get("timeconstant")), "order": int(get("order")), "rate_sps": float(get("rate"))}
                if "sinc" not in {path.rsplit("/", 1)[-1] for path in after["nodes"] if path.startswith(base)}:
                    raise ReadinessError("HF2LI service lacks public sinc-filter configuration/readback required for DC demodulation")
                if int(get("sinc")) != 0:
                    raise ReadinessError(f"HF2LI demodulator {demod} sinc filter did not disable at DC")
                if any(int(get(key)) != expected for key, expected in (("oscselect", 0), ("harmonic", 1), ("trigger", 0))):
                    raise ReadinessError(f"HF2LI demodulator {demod} rejected its internal DC oscillator/harmonic/free-running trigger settings")
                measured = self.detector_settings[demod]
                if measured["order"] not in range(1,9) or measured["timeconstant_s"]*measured["rate_sps"] < 4-1e-9:
                    raise ReadinessError(f"HF2LI demodulator {demod} actual filter/rate has insufficient impulse-area sample support")
                if .75*self.plan.timing["frame_period_s"] < 10*measured["order"]*measured["timeconstant_s"]:
                    raise ReadinessError(f"HF2LI demodulator {demod} actual filter tail exceeds the selected acquisition aperture")
                if int(get("enable")) != 1 or int(get("adcselect")) != (0 if demod == 0 else 1):
                    raise ReadinessError(f"HF2LI demodulator {demod} did not accept its sample/reference input")
            aggregate = sum(item["rate_sps"] for item in self.detector_settings.values())
            if aggregate > 700000 or any(x["rate_sps"] <= 0 for x in self.detector_settings.values()):
                raise ReadinessError("HF2LI actual aggregate readout exceeds the documented 700 kSa/s capacity")
            self.readbacks["actual_detectors"] = deepcopy(self.detector_settings)
            self.readbacks["raw_kernel"] = {"kernel_id": KERNEL_ID, "version": 2,
                "demodulation": "internal_zero_frequency", "observable": "magnitude_of_baseline_subtracted_complex_impulse_area",
                "units": "V s (uncalibrated demodulator scale)", "detectors": deepcopy(self.detector_settings),
                "signal_inputs": {path: value for path, value in after["nodes"].items() if "/sigins/" in path},
                "mircat_qcls": [{key: deepcopy(value) for key, value in item.items() if key != "limits"} for item in qcls],
                "probe_trigger_width_ns": _seconds(self.plan.timing["t660_1_recipe"]["channels"]["B"]["width"])*1e9,
                "probe_period_s": self.plan.timing["frame_period_s"], "optical_timing_qualified": False}
            self._health("configured")
            self.retain("configuration", self.readbacks)
        return deepcopy(self.readbacks)

    def _hf_before(self, suffix):
        path = f"/{self.devices['hf2li'].device_id}/{suffix}"
        return self.before["hf2li"]["nodes"][path]["value"]

    def _capabilities(self):
        """Only documented values actually read from the installed services."""
        from control_app.measurement_host.application_session import cached_hf2_choices
        def absolute(name):
            saved = self.before[name]
            relative = {edge: _seconds(_query(saved["readback"]["channels"][c], key))
                for c, edges in zip("ABCD", ((1, 2), (3, 4), (5, 6), (7, 8)))
                for edge, key in zip(edges, ("delay_edge", "width_edge"))}
            values = {0: 0.}
            def resolve(edge, path=()):
                if edge in values: return values[edge]
                target = saved["references"][edge]
                if edge in path or target not in range(9):
                    raise ValueError(f"{name} has cyclic or invalid active timing references")
                values[edge] = relative[edge] + resolve(target, (*path, edge))
                return values[edge]
            for edge in relative: resolve(edge)
            return values
        t1, t2 = absolute("t660_1"), absolute("t660_2")
        optical = self.before["mircat"]["qcls"][0]
        limits = optical["limits"]
        return {"hf2_choices": cached_hf2_choices(self.devices["hf2li"], "dual"),
            "mircat_pulse_rate_hz": optical["pulse_rate_hz"], "mircat_pulse_width_ns": optical["pulse_width_ns"],
            "mircat_max_pulse_rate_hz": limits["max_pulse_rate_hz"], "mircat_max_pulse_width_ns": limits["max_pulse_width_ns"],
            "mircat_max_duty_fraction": float(limits["max_duty_cycle"])/100.0, "qcl": 1,
            "fire_to_q_ns": (t2[3]-t2[1])*1e9,
            "pump_command_width_ns": (t2[2]-t2[1])*1e9,
            "fire_command_width_ns": (t2[2]-t2[1])*1e9,
            "q_command_width_ns": (t2[4]-t2[3])*1e9,
            "probe_command_width_ns": (t1[4]-t1[3])*1e9,
            "reference_command_width_ns": (t1[2]-t1[1])*1e9,
            "event_trigger_width_ns": (t1[6]-t1[5])*1e9,
            "filter_time_constant_s": float(self._hf_before("demods/0/timeconstant")),
            "filter_order": int(self._hf_before("demods/0/order")),
            "hf2li_rate_hz": float(self._hf_before("demods/0/rate")),
            "reference_filter_time_constant_s": float(self._hf_before("demods/3/timeconstant")),
            "reference_filter_order": int(self._hf_before("demods/3/order")),
            "reference_hf2li_rate_hz": float(self._hf_before("demods/3/rate")),
            "timing_step_ns": .01, "max_frame_capacity": self.devices["t660_2"].verified_frame_capacity(),
            "source": "owned installed device readbacks"}

    def _health(self, stage):
        hf = self.devices["hf2li"]
        health = hf.read_acquisition_health(input_indices=(0, 1) if self.settings["mode"] == "dual" else (0,))
        self.readbacks.setdefault("health", []).append({"stage": stage, **health})
        if health.get("overload") is True:
            raise ReadinessError("HF2LI reports ADC overload; reduce detector signal or increase its input range")
        if health.get("clock_locked") is False:
            raise ReadinessError("HF2LI reports an internal clock-generation failure")
        # PLL deliberately disabled at DC: reference_locked=None is expected.
        # Unreadable status nodes remain unknown in retained health, not all-clear.
        return health

    def tune(self, wavenumber):
        with self._scope():
            self.check()
            qcl = self.devices["mircat"]
            self._inhibit()
            qcl.turn_emission_off()
            if qcl.get_system_error_word():
                raise ReadinessError("MIRcat reports a system fault")
            if not qcl.is_interlock_set() or not qcl.is_key_switch_set():
                raise ReadinessError("MIRcat interlock/key switch is not ready")
            index = 1
            installed = self.before["mircat"]["qcls"][0]
            if not installed["range"]["min_cm1"] <= wavenumber <= installed["range"]["max_cm1"]:
                raise ValueError(f"{wavenumber:g} cm^-1 is outside the installed MIRcat QCL 1 tuning range")
            if not qcl.is_laser_armed(): qcl.arm()
            deadline = time.monotonic() + 120.0
            while not qcl.are_tecs_ready():
                self.check()
                if time.monotonic() >= deadline: raise ReadinessError("MIRcat TEC readiness timed out")
                time.sleep(.05)
            qcl.set_external_trigger_params(wavenumber_cm1=wavenumber)
            qcl.tune_to_wavenumber(wavenumber, qcl=index)
            while not qcl.is_tuned():
                self.check()
                if time.monotonic() >= deadline: raise ReadinessError("MIRcat Tuned readiness timed out")
                time.sleep(.025)
            actual = qcl.get_actual_wavelength()
            value = float(actual["value"])
            if actual.get("units") == "microns": value = 10000.0/value
            elif actual.get("units") != "cm^-1": raise ReadinessError("MIRcat returned an unsupported wavelength unit")
            if not math.isfinite(value): raise ReadinessError("MIRcat returned a nonfinite wavelength")
            self.readbacks["wavelength"] = {**actual, "wavenumber_cm1": value, "qcl": index}
            limits = qcl.get_qcl_pulse_limits(index)
            requests = self.settings.get("laser_settings", {})
            pulse = {"pulse_rate_hz": self.plan.resolved_settings.mircat_pulse_rate_hz,
                     "pulse_width_ns": self.plan.resolved_settings.mircat_pulse_width_ns,
                     "current_ma": requests.get("qcl_current_ma", float(qcl.get_qcl_current(1)))}
            low, high = qcl.get_qcl_current_limits(1)
            if not low <= pulse["current_ma"] <= high:
                raise ReadinessError("Requested MIRcat current exceeds installed QCL limits")
            _validate_optical_pulses(pulse["pulse_rate_hz"], pulse["pulse_width_ns"], self.plan.timing["input_frequency_hz"], limits)
            self.readbacks["requested_mircat_pulse"] = dict(pulse)
            qcl.set_qcl_pulse_params(qcl=1, **pulse)
            for key, method in (("pulse_rate_hz", qcl.get_qcl_pulse_rate), ("pulse_width_ns", qcl.get_qcl_pulse_width), ("current_ma", qcl.get_qcl_current)):
                if not math.isclose(float(method(1)), pulse[key], rel_tol=1e-7, abs_tol=1e-9):
                    raise ReadinessError(f"MIRcat {key} readback differs from request")
            width = float(qcl.get_qcl_pulse_width(index))
            rate = self.plan.timing["input_frequency_hz"]
            internal_rate = float(qcl.get_qcl_pulse_rate(1))
            self.readbacks["mircat_pulse"] = {"qcl": 1, "optical_pulse_width_ns": width,
                "current_ma": qcl.get_qcl_current(1), "external_probe_rate_hz": rate,
                "internal_rate_hz": internal_rate, "source": "installed QCL 1 readback; verified provisional internal optical settings"}
            self.readbacks["mircat_pulse"].update(_validate_optical_pulses(internal_rate, width, rate, limits))
            qcl.start_emission()
            settling = max(x["timeconstant_s"]*x["order"]*8 for x in self.detector_settings.values())
            self._wait(settling, "detector settling")

    def _wait(self, duration, stage):
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            self.check()
            self.progress(stage, 0, 1, f"{max(0, deadline-time.monotonic()):.2f} s remaining; selected interval")
            time.sleep(min(.05, max(0, deadline-time.monotonic())))

    def acquire(self, event, *, kind="measurement"):
        ev = data(event)
        self.pending_native = []
        with self._scope():
            self.check()
            if kind == "measurement" and ev["condition"] in ("pump_on", "pump_only"):
                self._wait(float(self.settings["reset_interval_s"]), "cycle recovery interval")
            recipe = deepcopy(self.plan.timing["t660_1_recipe"])
            frames = deepcopy(ev["frames"])
            if kind != "measurement":
                for frame in frames:
                    frame["channels"]["A"]["enabled"] = False
                    frame["channels"]["B"]["enabled"] = False
            t1, t2, hf = (self.devices[k] for k in ("t660_1", "t660_2", "hf2li"))
            self._inhibit()
            # Installed rising-edge references persist across workflows. The
            # compiled electrical recipe is absolute to each synthesizer shot.
            for edge in (1, 3, 5, 7):
                t1.command(f"TIME:RELTo{edge} 0", expect_response=False)
            t1.apply_recipe(recipe)
            configured = t1.read_active_settings()
            for channel, edge in zip("ABCD", (1, 3, 5, 7)):
                if int(t1.command(f"TIME:RELTo{edge}?")) != 0 or int(t1.command(f"TIME:RELTo{edge+1}?")) != edge:
                    raise ReadinessError(f"T660-1 {channel} did not accept shot-relative delay/width references")
                for key, setting in (("delay_edge", "delay"), ("width_edge", "width")):
                    if not math.isclose(_seconds(_query(configured["channels"][channel], key)), _seconds(recipe["channels"][channel][setting]), abs_tol=1e-11, rel_tol=0):
                        raise ReadinessError(f"T660-1 {channel} {setting} did not match the compiled electrical timing")
            if not math.isclose(float(_query(configured["queries"], "synth_frequency")), self.plan.timing["input_frequency_hz"], rel_tol=1e-9):
                raise ReadinessError("T660-1 actual synthesizer frequency differs from the compiled frame cadence")
            # T660 remote gate mode 9 emits one finite N-of-M burst per
            # GATE:EXECute. M=N+1 avoids the documented N=M repeat caveat.
            # This bounds probe pulses in hardware while the host retrieves data.
            for command in ("BURst:MODe OFF", f"BURst:PULse {len(frames)}", f"BURst:TRIGger {len(frames)+1}", "BURst:MODe ON", "GATE:MODe 9"):
                t1.command(command, expect_response=False)
            burst = {"pulses": int(t1.command("BURst:PULse?")), "triggers": int(t1.command("BURst:TRIGger?")),
                "enabled": str(t1.command("BURst:MODe?")).strip().upper(), "gate_mode": int(t1.command("GATE:MODe?"))}
            if burst["pulses"] != len(frames) or burst["triggers"] != len(frames)+1 or burst["enabled"] not in ("ON", "1") or burst["gate_mode"] != 9:
                raise ReadinessError("T660-1 rejected the finite remote-gated probe burst")
            configured["finite_remote_burst"] = burst
            self.retain(f"probe-clock-{ev['event_id']}", configured)
            previous_counter = t2.get_shot_count()
            upload = t2.preload_frame_table(frames, predivider=self.plan.timing["predivider"],
                input_frequency_hz=self.plan.timing["input_frequency_hz"], cancel_check=self.check,
                progress=lambda done, total: self.progress("acknowledged timing-table upload", done, total, ev["event_id"]))
            upload.update(counter_before_explicit_burst=previous_counter, biological_event_identity=ev["event_id"])
            self.retain(f"upload-{ev['event_id']}", upload)
            hf.start_acquisition(demodulators=[0, 3] if self.settings["mode"] == "dual" else [0])
            def poll(duration):
                native = hf.read_acquisition(duration)
                self.pending_native.append(native)
                self.retain(f"native-{ev['event_id']}-{len(self.pending_native):06d}", native)
                return native
            try:
                # A real pre-start baseline and whole native burst are retained.
                # Host times only bracket commands; both pump/probe edges come
                # from the preloaded T660 frame engine and synthesizer.
                poll(min(.2, self.plan.timing["frame_period_s"]/4))
                self._health("before_burst")
                t2.start_frame_table()
                start_before = time.monotonic()
                t1.set_trigger_source("SYN")
                t1.command("START", expect_response=False)
                t1.command("GATE:EXECute", expect_response=False)
                start_after = time.monotonic()
                deadline = start_after + len(frames)*self.plan.timing["frame_period_s"] + 10.
                counter_observations = []
                while True:
                    self.check()
                    poll(min(.1, self.plan.timing["frame_period_s"]))
                    state, shots = t2.get_frames_status(), t2.get_shot_count()
                    counter_observations.append({"host_monotonic_s": time.monotonic(), "state": state, "shot_count": shots})
                    self._health("acquisition")
                    if state == "DONE": break
                    if state == "ERROR" or time.monotonic() >= deadline:
                        raise ReadinessError(f"Finite event table {state}; native data retained, no automatic pump retry")
                tail = max(x["timeconstant_s"]*x["order"]*8 for x in self.detector_settings.values())
                remaining = self.plan.timing["frame_period_s"] + tail
                while remaining > 1e-9:
                    self.check()
                    duration = min(.1, remaining)
                    poll(duration)
                    remaining -= duration
                self._inhibit()
                self._health("retrieval")
                shots = t2.get_shot_count()
                probe_shots = t1.get_shot_count()
                counts = {"t660_1_shot_counter": probe_shots, "t660_1_counter_basis": "diagnostic; counter may include burst-suppressed synthesizer shots", "t660_2_frame_shots": shots, "finite_probe_burst": burst, "expected": len(frames)}
                self.readbacks["last_burst_counts"] = counts
                self.retain(f"burst-counts-{ev['event_id']}", counts)
                if shots != len(frames):
                    raise ValueError(f"T660 observed shot count {shots} differs from planned {len(frames)}")
                result = self._extract_raw(ev, kind)
                result["readbacks"] = {"t660_shot_count": shots, "t660_1_diagnostic_shot_count": probe_shots, "upload": upload,
                    "counter_observations": counter_observations, "command_start_host_monotonic_s": [start_before, start_after],
                    "wavelength": deepcopy(self.readbacks["wavelength"]), "health": deepcopy(self.readbacks.get("health", []))}
                return result
            finally:
                failures = []
                for callback in (self._inhibit, hf.stop_acquisition):
                    try: callback()
                    except Exception as exc: failures.append(str(exc))
                if failures: raise RuntimeError("; ".join(failures))

    def _extract_raw(self, ev, kind):
        """Native DC impulse area; no calibration approval or narrow marker gate."""
        cb = float(self.readbacks["clockbase"])
        raw = {"sample": _flatten_native(self.pending_native, 0)}
        if self.settings["mode"] == "dual": raw["reference"] = _flatten_native(self.pending_native, 3)
        period = float(self.plan.timing["frame_period_s"])
        flags, observed_peaks, epoch, assignment = [], [], None, "unassigned_native_burst"
        starts = [int(np.asarray(stream.get("timestamp", []))[0]) for stream in raw.values() if len(np.asarray(stream.get("timestamp", [])))]
        origin_tick = min(starts) if starts else 0
        epoch_tick = None
        # Detector-envelope peaks identify recorded probes at the slow recorder's
        # resolution only; this is not electrical or chemical time zero.
        for role, stream in reversed(tuple(raw.items())):
            ticks = np.asarray(stream.get("timestamp", []))
            x, y = np.asarray(stream.get("x", [])), np.asarray(stream.get("y", []))
            if len(ticks) < 5 or len(x) != len(ticks) or len(y) != len(ticks): continue
            times = _relative_seconds(ticks, origin_tick, cb)
            if np.any(np.diff(times) <= 0): continue
            signal = x+1j*y
            baseline = np.median(signal[:max(3, min(len(signal)//10, 50))])
            envelope = np.abs(signal-baseline)
            noise = float(np.sqrt(np.mean(np.abs(signal[:max(3, min(len(signal)//10, 50))]-baseline)**2)))
            threshold = max(np.finfo(float).eps, (np.max(envelope)-np.median(envelope))*.08, 8*noise)
            separation = max(1, int(period/np.median(np.diff(times))*.6))
            candidates = np.flatnonzero((envelope[1:-1] > envelope[:-2]) &
                (envelope[1:-1] >= envelope[2:]) & (envelope[1:-1] > threshold))+1
            retained = []
            for candidate in candidates[np.argsort(envelope[candidates])[::-1]]:
                if all(abs(int(candidate)-prior) >= separation for prior in retained):
                    retained.append(int(candidate))
            peaks = np.asarray(sorted(retained), dtype=int)
            if len(peaks) == len(ev["frames"]):
                cadence_tolerance = max(3*float(np.median(np.diff(times))), period*.002)
                if np.any(np.abs(np.diff(times[peaks])-period) > cadence_tolerance):
                    flags.append("probe_envelope_cadence_mismatch")
                    continue
                detector = self.detector_settings[3 if role == "reference" else 0]
                observed_peaks = [int(ticks[index]) for index in peaks]
                selected = peaks[int(ev["frame_index"])]
                relative_epoch = float(times[selected]-(detector["order"]-1)*detector["timeconstant_s"])
                epoch_tick = origin_tick + round(relative_epoch*cb)
                epoch = epoch_tick/cb
                assignment = "measured_detector_impulse_order_with_programmed_frame_index"
                break
            flags.append("probe_envelope_count_mismatch")
        if epoch is None: flags.append("pulse_assignment_unresolved")
        result = {k: v for k, v in ev.items() if k != "frames"}
        commanded = kind == "measurement" and ev["condition"] in ("pump_on", "pump_only")
        offset = self.settings.get("optical_delay_offset_ns")
        try:
            optical = ev.get("electrical_delay_ns", ev["quantized_delay_ns"])+float(offset) if offset is not None else None
            if optical is not None and not math.isfinite(optical): raise ValueError("Nonfinite optional offset")
        except (TypeError, ValueError):
            optical = None
            flags.append("invalid_optional_optical_offset")
        result.update(condition=ev["condition"] if kind == "measurement" else "unpumped", requested_condition=ev["condition"],
            native_device_data=deepcopy(self.pending_native), quality_flags=flags,
            acquisition_kernel=deepcopy(self.readbacks["raw_kernel"]),
            observed_electrical_delay_ns=None, calibrated_optical_delay_ns=None,
            estimated_optical_delay_ns=optical,
            estimated_optical_delay_source="operator_supplied_route_offset" if offset is not None else "unavailable",
            optical_delay_source="unavailable",
            probe_assignment={"method": assignment, "detector_envelope_peak_ticks": observed_peaks, "clockbase": cb,
                "filter_model_epoch_s": epoch, "optical_time_zero": False},
            pump_evidence={"commanded": commanded, "optical_pulse_count": None if commanded else 0,
                "observation": "electrical sequence commands retained; optical pump arrival is not independently observed"},
            reset_evidence={"method": "operator_selected_cycle_interval", "wait_s": period, "description": "Cycle interval; sample equivalence unobserved",
                "equivalent": None},
            measured_wavenumber_cm1=float(self.readbacks["wavelength"]["wavenumber_cm1"]))
        for role, stream in raw.items():
            result[role] = self._raw_area(stream, epoch, period, cb, epoch_ticks=epoch_tick)
        if commanded: result["quality_flags"].append("optical_delay_unresolved")
        for role in raw:
            result["quality_flags"].extend(result[role].get("quality_flags", []))
        return result

    @staticmethod
    def _raw_area(stream, epoch, period, clockbase, *, epoch_ticks=None):
        """Integrate signed X/Y before taking magnitude; retain raw gain units."""
        ticks = np.asarray(stream.get("timestamp", []))
        x, y = np.asarray(stream.get("x", [])), np.asarray(stream.get("y", []))
        output = {"timestamp_s": np.array([epoch if epoch is not None else 0.]), "value": np.array([np.nan]),
            "valid": np.array([False]), "group_delay_s": 0., "estimator": "uncalibrated_complex_impulse_area",
            "units": "V s (HF2 demodulator scale)", "variance": np.array([np.nan]),
            "uncertainty_basis": "Filter-correlated integrated noise not yet estimated; no independent-sample assumption",
            "quality_flags": []}
        def unsupported(reason):
            output["quality_flags"].append(reason)
            return output
        if epoch is None: return unsupported("pulse_assignment_unresolved")
        if len(ticks) != len(x) or len(ticks) != len(y) or len(ticks) < 5: return unsupported("malformed_native_stream")
        epoch_ticks = int(round(epoch*clockbase)) if epoch_ticks is None else int(epoch_ticks)
        times = _relative_seconds(ticks, epoch_ticks, clockbase)
        output["timestamp_ticks"] = np.array([epoch_ticks], dtype=np.uint64)
        if np.any(np.diff(times) <= 0): return unsupported("nonmonotonic_native_timestamps")
        base = (times >= -.2*period) & (times <= -.05*period)
        signal = (times >= -.01*period) & (times <= .75*period)
        if base.sum() < 3 or signal.sum() < 3: return unsupported("truncated_native_aperture")
        support = times[signal]
        step = float(np.median(np.diff(times)))
        if np.max(np.diff(support)) > step*2.5 or np.max(np.diff(times[base])) > step*2.5:
            return unsupported("native_sample_gap")
        if (support[0]+.01*period > step*2.5 or .75*period-support[-1] > step*2.5
                or times[base][0]+.2*period > step*2.5 or -.05*period-times[base][-1] > step*2.5):
            return unsupported("truncated_native_aperture")
        native = x+1j*y
        if not np.isfinite(native[base | signal]).all(): return unsupported("nonfinite_native_signal")
        background = np.mean(native[base])
        integrated = np.trapezoid(native[signal]-background, support)
        output.update(value=np.array([abs(integrated)]), valid=np.array([True]),
            signed_area_x=float(integrated.real), signed_area_y=float(integrated.imag),
            baseline_x=float(background.real), baseline_y=float(background.imag),
            baseline_noise_rms_v=float(np.sqrt(np.mean(np.abs(native[base]-background)**2))),
            integration_window_hf2_s=[float(epoch+support[0]), float(epoch+support[-1])])
        tail = native[signal][-max(3, int(signal.sum()*.1)):] - background
        tail_mean = abs(np.mean(tail))
        tail_tolerance = max(5*output["baseline_noise_rms_v"], float(np.max(np.abs(native[signal]-background)))*.005, np.finfo(float).eps)
        output["tail_support"] = {"mean_offset_v": float(tail_mean), "tolerance_v": float(tail_tolerance),
            "returned_to_baseline": bool(tail_mean <= tail_tolerance)}
        if tail_mean > tail_tolerance:
            output["valid"][:] = False
            output["quality_flags"].append("nonreturning_detector_tail")
        # A conservative correlated-noise scale is retained rather than an
        # independent-sample standard error. Norm integration is biased near zero.
        noise_area = 2*output["baseline_noise_rms_v"]*(support[-1]-support[0])
        output["conservative_noise_area_v_s"] = float(noise_area)
        if abs(integrated) <= max(5*noise_area, np.finfo(float).tiny):
            output["valid"][:] = False
            output["quality_flags"].append("low_snr_integrated_signal")
        return output

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
                        retained_qcls = [item for item in (before.get("qcls") or [before]) if int(item.get("qcl", 1)) == 1]
                        if len(retained_qcls) != 1:
                            raise RuntimeError("Original QCL 1 settings are unavailable for restoration")
                        original = retained_qcls[0]
                        restored_fields = (("pulse_rate_hz", qcl.get_qcl_pulse_rate), ("pulse_width_ns", qcl.get_qcl_pulse_width), ("current_ma", qcl.get_qcl_current))
                        if any(not math.isclose(method(1), original[key], rel_tol=1e-6) for key, method in restored_fields):
                            qcl.set_qcl_pulse_params(qcl=1, **{k: original[k] for k in ("pulse_rate_hz", "pulse_width_ns", "current_ma")})
                        allowed = ("pulse_mode", "process_trigger_mode", "start", "stop", "interval", "units", "dwell_us", "after_off_us")
                        qcl.set_wavelength_trigger_params(**{k: v for k, v in before["trigger"].items() if k in allowed})
                        after = {"trigger": qcl.get_wavelength_trigger_params(), "state": {"emission_on": qcl.is_emission_on(), "armed": qcl.is_laser_armed(), "qcl": 1}}
                        for key in allowed:
                            if key not in before["trigger"]:
                                continue
                            expected, actual = before["trigger"][key], after["trigger"].get(key)
                            equal = (isinstance(actual, (int, float)) and math.isclose(float(actual), float(expected), rel_tol=1e-6, abs_tol=1e-9))
                            if not equal:
                                raise RuntimeError(f"MIRcat trigger {key} did not restore: {actual!r} != {expected!r}")
                        if qcl.is_emission_on() or qcl.is_laser_armed():
                            raise RuntimeError("MIRcat safe idle readback failed")
                        for original in retained_qcls:
                            for key, method in (("pulse_rate_hz", qcl.get_qcl_pulse_rate), ("pulse_width_ns", qcl.get_qcl_pulse_width), ("current_ma", qcl.get_qcl_current)):
                                if not math.isclose(method(1), original[key], rel_tol=1e-6):
                                    raise RuntimeError(f"MIRcat QCL {original['qcl']} {key} did not restore")
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
                        center_path = f"/{hf.device_id}/plls/0/freqcenter"
                        snapshot["nodes"] = {p: v for p, v in snapshot["nodes"].items() if p not in enables and p != center_path}
                        hf.reload_settings_snapshot(snapshot)
                        hf.reload_settings_snapshot({"nodes": enables})
                        after = hf.export_settings_snapshot(preset=self.hf_snapshot_preset)
                        check = deepcopy(self.before["hf2li"])
                        # Installed HF2 PLL center follows its external reference;
                        # it is retained in before/after, not replayed as a setpoint.
                        check["nodes"].pop(center_path, None)
                        if int(self.before["hf2li"]["nodes"][f"/{hf.device_id}/plls/0/enable"]["value"]) == 1:
                            # An enabled restored PLL owns the instantaneous
                            # oscillator frequency; the saved scalar is dynamic.
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
        if "burst" in before:
            for command in (f"BURst:PULse {before['burst']['pulses']}", f"BURst:TRIGger {before['burst']['triggers']}"):
                unit.command(command, expect_response=False)
            if int(unit.command("BURst:PULse?")) != before["burst"]["pulses"] or int(unit.command("BURst:TRIGger?")) != before["burst"]["triggers"]:
                raise RuntimeError("T660 original burst pulse/trigger counts did not restore")
        unit.command(f"GATE:MODe {_query(saved['queries'], 'gate_mode')}", expect_response=False)
        unit.command(f"BURst:MODe {_query(saved['queries'], 'burst')}", expect_response=False)
        after = unit.read_active_settings()
        for key in ("gate_mode", "burst"):
            if _query(after["queries"], key).upper() != _query(saved["queries"], key).upper():
                raise RuntimeError(f"T660 original {key} did not restore")
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
