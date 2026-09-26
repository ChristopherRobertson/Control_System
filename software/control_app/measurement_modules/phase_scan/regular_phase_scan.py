"""Regular CH1 phase-scan planning and readback-based HF2LI selection.

No constructor connects to hardware. The built-in profile is a preview,
never a substitute for connected capabilities. Device discovery is an explicit
configuration-only operation; no laser or timing output is started.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from fractions import Fraction
import math

from control_app.workflows.phase_scan import PhaseScanSettings, PhaseScanPlan, PhaseScanPlanError

HF2_SPECIFICATION = "https://docs.zhinst.com/hf2_user_manual/specifications.html"
HF2_FILTER_DOCUMENTATION = "https://docs.zhinst.com/hf2_user_manual/signal_processing_basics.html"
PREVIEW_PROFILE_SOURCE = "instrument/phase_scan_preview.md#single-detector-profile"
SCHEMA_VERSION = "regular_single_detector_phase_scan_v1"


def _positive_finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value > 0


@dataclass(frozen=True)
class RegularPhaseScanSettings(PhaseScanSettings):
    pump_repetition_rate_hz: float = 10.0
    rest_period_s: float = .1

    def __post_init__(self):
        rate = self.pump_repetition_rate_hz
        if isinstance(rate, (int, float)) and math.isfinite(rate) and rate > 0:
            object.__setattr__(self, "rest_period_s", 1 / rate)


@dataclass(frozen=True)
class HF2Capabilities:
    device_id: str = "dev18500"
    orders: tuple[int, ...] = (4,)
    timeconstants_by_order: dict = field(default_factory=lambda: {4: (4.999538607626059e-5,)})
    rates_sps: tuple[float, ...] = (28782.894736842107,)
    timing_rate_sps: float = 230263.15789473685
    enabled_streams: tuple[int, ...] = (0, 2)
    source: str = PREVIEW_PROFILE_SOURCE
    verified: bool = False
    tuning_ranges: tuple = ((1, 1638.8068850219217, 2077.2745597378685),)
    timing_table_capacity: int = 8192
    max_retained_bytes: int = 512 * 1024 * 1024
    readback_records: tuple = ()

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if isinstance(value, cls):
            return value
        fields = cls.__dataclass_fields__
        data = {k: v for k, v in value.items() if k in fields}
        for name in ("orders", "rates_sps", "enabled_streams", "tuning_ranges", "readback_records"):
            if name in data:
                data[name] = tuple(data[name])
        if "timeconstants_by_order" in data:
            data["timeconstants_by_order"] = {int(k): tuple(v) for k, v in data["timeconstants_by_order"].items()}
        if "tuning_ranges" in data:
            data["tuning_ranges"] = tuple(tuple(row) for row in data["tuning_ranges"])
        return cls(**data)


def filter_response(order, timeconstant_s, rate_sps, timing_rate_sps, scan_speed_cm1_s):
    """Cascaded RC estimate: 10–90% step rise, group delay and 3 dB BW.

    Effective resolution combines step response and two source-sample intervals
    in quadrature. It is an engineering estimate, not a calibrated impulse
    response or an assertion of optical timing accuracy. No data deconvolution.
    """
    if (isinstance(order, bool) or not isinstance(order, int) or not 1 <= order <= 8 or
            not all(_positive_finite(v) for v in (timeconstant_s, rate_sps, timing_rate_sps, scan_speed_cm1_s))):
        raise PhaseScanPlanError("Filter response requires a supported HF2 order and finite positive time constant, rates and scan speed")
    def crossing(level):
        lo, hi = 0., 100.
        for _ in range(64):
            x = (lo + hi) / 2
            cdf = 1 - math.exp(-x) * sum(x**k / math.factorial(k) for k in range(order))
            if cdf < level:
                lo = x
            else:
                hi = x
        return (lo + hi) / 2
    rise = (crossing(.9) - crossing(.1)) * timeconstant_s
    bandwidth = math.sqrt(2**(1/order) - 1) / (2 * math.pi * timeconstant_s)
    effective = math.sqrt(rise**2 + (2/rate_sps)**2 + (2/timing_rate_sps)**2)
    return {"filter_rise_time_s": rise, "filter_group_delay_s": order*timeconstant_s,
            "bandwidth_hz": bandwidth, "temporal_resolution_s": effective,
            "spectral_broadening_cm1": scan_speed_cm1_s*rise,
            "effective_spectral_resolution_cm1": scan_speed_cm1_s*effective}


def _hf2_value(field, value):
    if field == "order":
        return str(value)
    if not _positive_finite(value):
        return repr(value)
    return f"{value*1e6:.9g} µs" if field == "timeconstant_s" else f"{value:.12g} Sa/s"


def _hf2_requested_text(overrides):
    labels = {"order": "filter order", "timeconstant_s": "time constant", "rate_sps": "CH1 sample rate"}
    return ", ".join(f"{label} {_hf2_value(field, overrides[field]) if field in overrides else 'Automatic'}"
                     for field, label in labels.items())


def _hf2_supported_text(field, values, *, near=None):
    ordered = sorted(set(values))
    if len(ordered) > 5 and field != "order":
        if _positive_finite(near):
            ordered = sorted(sorted(ordered, key=lambda value: abs(value-near))[:5])
        else:
            ordered = ordered[:5]
    return ", ".join(_hf2_value(field, value) for value in ordered)


def _hf2_recovery_text(caps, overrides):
    """Offer only changes that can coexist with the other selected overrides.

    The suggestions are explanatory, not applied settings. A one-field remedy
    must leave a valid combination with every other manual setting unchanged.
    If multiple fields must change, provide a complete accepted combination.
    """
    feasible = []
    for order in caps.orders:
        for tc in caps.timeconstants_by_order[order]:
            for rate in caps.rates_sps:
                if (16000 <= caps.timing_rate_sps <= 231000 and 0 < rate <= 231000
                        and rate + caps.timing_rate_sps <= 700000):
                    feasible.append({"order": order, "timeconstant_s": tc, "rate_sps": rate})
    if not feasible:
        return ("No accepted filter/rate combination in this capability profile meets that requirement. "
                "Use Instruments → Recheck supported device choices to verify choices with CH1 and DIO streams enabled; no requested setting was changed.")
    labels = {"order": "Filter order", "timeconstant_s": "Time constant", "rate_sps": "CH1 sample rate"}
    suggestions = []
    for field in ("rate_sps", "timeconstant_s", "order"):
        if field not in overrides:
            continue
        compatible = [candidate for candidate in feasible if all(
            candidate[key] == value for key, value in overrides.items() if key != field)]
        if not compatible:
            continue
        values = {candidate[field] for candidate in compatible}
        current = overrides[field]
        chosen = min(values, key=lambda value: (abs(value-current), value)) if _positive_finite(current) else min(values)
        suggestions.append(f"Set {labels[field]} to {_hf2_value(field, chosen)} (or set that override to Automatic)")
    if suggestions:
        return "; or ".join(suggestions) + ". Each option keeps the other manual overrides."
    # No individual dropdown change can recover. Favor the fewest changed
    # overrides, then stay near their values; every suggested value is accepted.
    def preference(candidate):
        return (sum(candidate[key] != value for key, value in overrides.items()),
                sum(abs(candidate[key]-value)/value for key, value in overrides.items() if _positive_finite(value)),
                abs(candidate["order"]-4), candidate["rate_sps"])
    chosen = min(feasible, key=preference)
    return ("More than one override must change. Choose the supported combination "
            + _hf2_requested_text(chosen) + ", or select Restore automatic settings.")


def select_hf2_settings(settings, capabilities=None, overrides=None, *, _expected_streams=(0, 2)):
    caps = HF2Capabilities.from_dict(capabilities) if capabilities is not None else HF2Capabilities()
    overrides = dict(overrides or {})
    unknown = set(overrides) - {"order", "timeconstant_s", "rate_sps"}
    if unknown:
        raise PhaseScanPlanError(f"Unknown HF2LI override: {', '.join(sorted(unknown))}")
    if tuple(caps.enabled_streams) != tuple(_expected_streams):
        raise PhaseScanPlanError("HF2LI capabilities must be measured with CH1 and DIO streams (API 0 and 2) enabled; use Instruments → Recheck supported device choices")
    if not caps.orders or not caps.rates_sps or not _positive_finite(caps.timing_rate_sps):
        raise PhaseScanPlanError("HF2LI has no supported acquisition settings; use Instruments → Recheck supported device choices")
    if (any(isinstance(order, bool) or not isinstance(order, int) or not 1 <= order <= 8 for order in caps.orders)
            or any(not _positive_finite(rate) for rate in caps.rates_sps)
            or any(not caps.timeconstants_by_order.get(order) or
                   any(not _positive_finite(tc) for tc in caps.timeconstants_by_order[order]) for order in caps.orders)):
        raise PhaseScanPlanError("HF2LI capability profile has invalid orders, time constants or rates; use Instruments → Recheck supported device choices")
    if "order" in overrides and (isinstance(overrides["order"], bool) or
                                  not isinstance(overrides["order"], int)):
        raise PhaseScanPlanError(f"Filter order {overrides['order']!r} is not a supported integer order. "
                                f"Accepted orders: {_hf2_supported_text('order', caps.orders)}. "
                                "Select an accepted order from the dropdown or set Filter order to Automatic.")
    orders = [overrides["order"]] if "order" in overrides else list(caps.orders)
    if any(order not in caps.orders for order in orders):
        raise PhaseScanPlanError(f"Filter order {overrides['order']} is unsupported by this HF2LI profile. "
                                f"Accepted orders: {_hf2_supported_text('order', caps.orders)}. "
                                + _hf2_recovery_text(caps, overrides))
    for key in ("timeconstant_s", "rate_sps"):
        if key in overrides and not _positive_finite(overrides[key]):
            label = "Time constant" if key == "timeconstant_s" else "CH1 sample rate"
            raise PhaseScanPlanError(f"{label} {overrides[key]!r} is not a finite positive supported value. "
                                    f"Select an accepted value from its dropdown or set {label} to Automatic.")
    rates = [overrides["rate_sps"]] if "rate_sps" in overrides else sorted(caps.rates_sps)
    if any(rate not in caps.rates_sps for rate in rates):
        raise PhaseScanPlanError(f"CH1 sample rate {_hf2_value('rate_sps', overrides['rate_sps'])} is unsupported "
            "with the enabled CH1 and DIO streams. Accepted dropdown rates include "
            + _hf2_supported_text("rate_sps", caps.rates_sps, near=overrides["rate_sps"]) + ". "
            + _hf2_recovery_text(caps, overrides))
    # The nominal 230 kSa/s two-stream ceiling includes the documented HF2
    # hardware quantization (observed 230263.1579), not a nominal dropdown.
    if max(rates + [caps.timing_rate_sps]) > 231000 or max(rates) + caps.timing_rate_sps > 700000:
        raise PhaseScanPlanError(f"HF2LI CH1 rate up to {_hf2_value('rate_sps', max(rates))} and DIO rate "
            f"{_hf2_value('rate_sps', caps.timing_rate_sps)} exceed the two-stream transfer capacity "
            "(at most 231000 Sa/s per stream and 700000 Sa/s combined). "
            "Use Instruments → Recheck supported device choices to verify choices with only CH1 and DIO enabled.")
    if 2/caps.timing_rate_sps > .000125:
        raise PhaseScanPlanError(f"HF2LI DIO rate {_hf2_value('rate_sps', caps.timing_rate_sps)} cannot resolve "
            "the 125 µs marker pulse: at least 16000 Sa/s is required for two timing samples. "
            "Use Instruments → Recheck supported device choices; changing the CH1 sample rate alone cannot resolve this timing conflict.")
    if "timeconstant_s" in overrides and not any(overrides["timeconstant_s"] in caps.timeconstants_by_order[order]
                                                for order in orders):
        accepted = "; ".join(f"order {order}: {_hf2_supported_text('timeconstant_s', caps.timeconstants_by_order[order], near=overrides['timeconstant_s'])}"
                             for order in orders)
        tc_orders = [order for order in caps.orders if overrides["timeconstant_s"] in caps.timeconstants_by_order[order]]
        elsewhere = (f" That time constant is accepted at order {_hf2_supported_text('order', tc_orders)}."
                     if tc_orders else " That time constant is not an accepted readback for any supported order.")
        raise PhaseScanPlanError(f"HF2LI {_hf2_requested_text(overrides)} conflict: the selected time constant "
            f"is unsupported for the selected filter order. Accepted dropdown values include {accepted}."
            + elsewhere + " " + _hf2_recovery_text(caps, overrides))
    target_s = min(settings.phase_delay_us*1e-6, 1/settings.scan_speed_cm1_s)
    candidates = []
    for order in orders:
        constants = caps.timeconstants_by_order.get(order, ())
        if "timeconstant_s" in overrides:
            constants = [overrides["timeconstant_s"]] if overrides["timeconstant_s"] in constants else []
        for tc in constants:
            for rate in rates:
                response = filter_response(order, tc, rate, caps.timing_rate_sps, settings.scan_speed_cm1_s)
                candidates.append({"order": order, "timeconstant_s": tc, "rate_sps": rate,
                    "timing_rate_sps": caps.timing_rate_sps, **response})
    # Anti-aliasing guidance ranks automatic choices; it is not hardware validity.
    # Keep every explicit override, even when no remaining candidate meets 7x.
    recommended = [c for c in candidates if c["rate_sps"] >= 7*c["bandwidth_hz"]]
    if recommended:
        candidates = recommended
    sufficient = [c for c in candidates if c["temporal_resolution_s"] <= target_s]
    if sufficient:
        # Prefer the tested fourth-order family, then largest useful filtering,
        # then lowest adequate transfer rate. All values came from readbacks.
        selected = min(sufficient, key=lambda c: (abs(c["order"]-4), -c["timeconstant_s"], c["rate_sps"]))
    else:
        selected = min(candidates, key=lambda c: c["temporal_resolution_s"])
    selected.update(mode="manual" if overrides else "automatic", requested=overrides,
        enabled_streams=list(caps.enabled_streams), device_id=caps.device_id,
        capability_source=caps.source, capability_verified=caps.verified,
        target_temporal_resolution_s=target_s, target_spectral_resolution_cm1=1.,
        resolution_target_met=bool(sufficient),
        estimate_basis="Cascaded RC 10–90% step rise and two detector/DIO sample intervals, quadrature; not optical calibration",
        warning=("" if sufficient else "The supported configuration does not meet the temporal/spectral resolution target; phase spacing is not achievable temporal resolution. See the estimated response and broadening."))
    ratio = selected["rate_sps"] / selected["bandwidth_hz"]
    # Attenuation at Nyquist characterizes the selected RC filter, not total
    # aliased noise, which also depends on the input spectrum and other filters.
    nyquist_attenuation_db = 10*selected["order"]*math.log10(
        1 + (math.pi*selected["rate_sps"]*selected["timeconstant_s"])**2)
    selected.update(sample_rate_to_bandwidth_ratio=ratio,
        anti_alias_guideline_ratio=7., anti_alias_guideline_met=ratio >= 7,
        filter_attenuation_at_nyquist_db=nyquist_attenuation_db)
    if ratio < 7:
        advisory = (f"Aliasing advisory: CH1 sample rate is {ratio:.3g} × the filter 3 dB bandwidth "
            f"({selected['bandwidth_hz']:.6g} Hz), below the recommended 7–10× margin. "
            f"Estimated filter attenuation at Nyquist is {nyquist_attenuation_db:.1f} dB. "
            "This is not a hardware incompatibility; acquisition is allowed. Aliasing depends on "
            "signal/noise content and filter response and has not been quantified. "
            "A higher supported sample rate or longer time constant can reduce aliasing risk.")
        selected["warning"] = " ".join(filter(None, (selected["warning"], advisory)))
    return selected


@dataclass(frozen=True)
class RegularPhaseScanPlan(PhaseScanPlan):
    hf2_selection: dict = field(default_factory=dict)
    capture_window: dict = field(default_factory=dict)
    capacity: dict = field(default_factory=dict)

    @property
    def frame_period_s(self):
        return 1/self.settings.pump_repetition_rate_hz

    @property
    def nominal_duration_s(self):
        return (self.total_scans-1)*self.frame_period_s + self.capacity.get("occupied_frame_s", self.scan_duration_s)

    def to_dict(self):
        return {"schema_version": SCHEMA_VERSION, "method": "regular_single_detector_phase_scan",
            "settings": asdict(self.settings), "detector_input": "HF2LI CH1 SIG IN +",
            "derived": {"scan_duration_s": self.scan_duration_s, "total_scans": self.total_scans,
                "total_pump_events": self.total_pump_events, "nominal_duration_s": self.nominal_duration_s,
                "frame_period_s": self.frame_period_s, "frame_predivider": round(self.settings.probe_repetition_rate_hz*self.frame_period_s),
                "phase_first_us": self.first_phase_delay_us, "phase_last_us": self.last_phase_delay_us,
                "phase_count_per_repetition": self.phases_per_repetition},
            "sequence": {"order": "one_unpumped_baseline_then_signed_phase_steps",
                "blank": "identical_full_sequence_with_pump_inhibited",
                "phase_first_us": self.first_phase_delay_us, "phase_last_us": self.last_phase_delay_us,
                "phase_increment_us": self.settings.phase_delay_us,
                "observation_window_s": [-self.settings.pre_pump_ms/1000, self.settings.post_pump_ms/1000],
                "fire_to_qswitch_us": self.settings.fire_to_qswitch_us,
                "pump_time_basis": "electrical_sync", "optical_arrival_calibrated": False},
            "hf2_selection": self.hf2_selection, "capture_window": self.capture_window,
            "capacity": self.capacity, "trajectory_calibrated": False,
            "limitations": ["Timing bounds are an engineering envelope; measured controller markers define wavelength.",
                "Time is relative to electrical pump sync; optical arrival is not calibrated.",
                "Filter response estimates do not remove filter delay or broadened spectral features.",
                "Unobserved coverage remains missing; sequential blank normalization does not remove inter-run drift."]}


def build_regular_phase_scan_plan(settings=None, capabilities=None, overrides=None, *, _selection=None):
    settings = settings or RegularPhaseScanSettings()
    if not isinstance(settings, RegularPhaseScanSettings):
        raise PhaseScanPlanError("Regular Phase Scan requires RegularPhaseScanSettings")
    from control_app.measurement_host.laser_settings import mircat_acceptance_rate_hz
    bounds = {"pump_repetition_rate_hz": (0, 10), "pump_wavelength_nm": (1, 10000),
              "fire_to_qswitch_us": (1, 1_000_000), "qcl_current_ma": (1, 10_000), "start_wavenumber_cm1": (1650, 2050),
              "stop_wavenumber_cm1": (1650, 2050), "scan_speed_cm1_s": (1, 10000), "phase_delay_us": (1, 1000)}
    for name, (low, high) in bounds.items():
        value = getattr(settings, name)
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                or not low <= value <= high or (low == 0 and value == 0)):
            raise PhaseScanPlanError(f"{name.replace('_', ' ')} must be {'positive and ' if low == 0 else ''}within {low:g}–{high:g}")
    for name in ("pre_pump_ms", "post_pump_ms"):
        value = getattr(settings, name)
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                or value < 0 or (name.endswith("post_pump_ms") and value == 0)):
            raise PhaseScanPlanError(f"{name} must be finite and {'nonnegative' if name.endswith('pre_pump_ms') else 'positive'}")
    fixed = RegularPhaseScanSettings()
    for name in ("probe_pulse_width_ns",
                 "mircat_internal_pulse_width_ns", "repetitions", "pump_reference"):
        if getattr(settings, name) != getattr(fixed, name):
            raise PhaseScanPlanError(f"{name} is fixed by the regular phase-scan instrument recipe")
    start, stop, speed = settings.start_wavenumber_cm1, settings.stop_wavenumber_cm1, settings.scan_speed_cm1_s
    from control_app.measurement_host.laser_settings import validate_mircat_limits
    validate_mircat_limits(current=settings.qcl_current_ma, width=settings.probe_pulse_width_ns, wavenumbers=(start, stop))
    if start <= stop:
        raise PhaseScanPlanError("Start wavenumber must be greater than Stop wavenumber")
    caps = HF2Capabilities.from_dict(capabilities) if capabilities is not None else HF2Capabilities()
    if not any(min(start, stop) >= float(r[1]) and max(start, stop) <= float(r[2]) for r in caps.tuning_ranges):
        raise PhaseScanPlanError("Requested trajectory is not covered by a single installed MIRcat QCL; continuous phase scanning cannot switch QCLs")
    rate = settings.probe_repetition_rate_hz
    if not _positive_finite(rate) or rate > 2_000_000.:
        raise PhaseScanPlanError("MIRcat repetition rate must be positive and at most 2 MHz for the HF2LI DIO reference")
    if Fraction(str(rate)) / Fraction("0.02") % 1:
        raise PhaseScanPlanError("MIRcat repetition rate must lie on the T660 0.02 Hz DDS grid")
    settings = replace(settings, mircat_internal_repetition_rate_hz=mircat_acceptance_rate_hz(rate))
    if rate >= settings.mircat_internal_repetition_rate_hz:
        raise PhaseScanPlanError("MIRcat internal rate must exceed the requested trigger rate")
    if rate * settings.probe_pulse_width_ns * 1e-9 > .30 + 1e-12:
        raise PhaseScanPlanError("Requested probe duty exceeds 30%")
    divider = Fraction(str(rate)) / Fraction(str(settings.pump_repetition_rate_hz))
    if divider.denominator != 1 or not 1 <= divider <= 2**32-1:
        raise PhaseScanPlanError("Pump cadence is not exactly supported by the requested MIRcat repetition rate and 32-bit integer predivider")
    scan_s = abs(Fraction(str(start))-Fraction(str(stop))) / Fraction(str(speed))
    spacing_s = Fraction(str(settings.phase_delay_us))/1000000
    before, after = settings.pre_pump_ms, settings.post_pump_ms
    # Every wavelength is reached at a different time during a sweep: include
    # the complete trajectory duration before the requested negative-time edge.
    # Phase starts are derived, not confused with the reconstructed time window.
    first = math.floor((-scan_s-Fraction(str(before))/1000)/spacing_s)
    last = math.ceil((Fraction(str(after))/1000)/spacing_s)
    count = last-first+1
    if count+1 > min(8192, caps.timing_table_capacity):
        raise PhaseScanPlanError(f"Sequence needs {count+1} timing-table entries, exceeding capacity {min(8192, caps.timing_table_capacity)}; increase Phase-delay spacing or bring Start wavenumber and Stop wavenumber closer together. Runs are not split.")
    sweep_bound = 2*float(scan_s)
    occupied = .001 + max(settings.fire_to_qswitch_us*1e-6, -first*float(spacing_s)) + max(.01, last*float(spacing_s)+sweep_bound) + .010
    period = 1/settings.pump_repetition_rate_hz
    if occupied >= period:
        raise PhaseScanPlanError(f"Scan trajectory, signed delays and return margin need {occupied:.6g} s per frame, exceeding the {period:.6g} s pump cadence; reduce pump rate, narrow the range or increase scan speed")
    selection = (select_hf2_settings(settings, caps, overrides) if _selection is None
                 else _selection() if callable(_selection) else _selection)
    if float(scan_s) < 2/selection["rate_sps"]:
        raise PhaseScanPlanError("The requested scan is shorter than two HF2LI detector sample intervals; increase the span, reduce speed or select a supported higher rate")
    marker_interval = float(abs(Fraction(str(start))-Fraction(str(stop)))) / max(1, math.ceil(abs(start-stop)/5))
    marker_width_us = max(1, min(500, int(marker_interval/speed*1e6/4)))
    if marker_width_us*1e-6 < 2/selection["timing_rate_sps"]:
        raise PhaseScanPlanError("The requested scan's wavelength markers are too short for the supported HF2LI timing rate; increase the span or reduce speed")
    capture = {"duration_s": sweep_bound+.00028, "engineering_sweep_bound_s": sweep_bound,
               "pretrigger_s": .0001, "posttrigger_margin_s": .00018,
               "basis": "twice_requested_sweep_duration_engineering_envelope_not_calibration"}
    # Returned arrays plus per-record metadata; no multiplicative allowances.
    # Exact module capacity is checked pre-arm. This is not peak process RAM.
    samples = math.ceil(capture["duration_s"]*selection["rate_sps"])
    timing_samples = math.ceil(capture["duration_s"]*selection["timing_rate_sps"])
    payload_bytes = (count+1)*(samples*2*16 + timing_samples*16 + 4*16)
    metadata_bytes = (count+1)*4*4096
    estimated = payload_bytes + metadata_bytes
    warning = (f"Warning: estimated record storage is {estimated/1e6:.1f} MB; increase Phase-delay spacing to reduce memory use."
               if estimated > caps.max_retained_bytes else "")
    cells = (math.ceil((settings.pre_pump_ms+settings.post_pump_ms)/1000/float(spacing_s))+1)*min(samples, 1024)
    if cells > 16_000_000:
        raise PhaseScanPlanError("Reconstruction exceeds the 16-million-cell capacity; increase Phase-delay spacing or bring Start wavenumber and Stop wavenumber closer together")
    return RegularPhaseScanPlan(settings, count, float(scan_s), first, (0., float(scan_s)), None,
        selection, capture, {"estimated_retained_bytes": estimated, "max_retained_bytes": caps.max_retained_bytes,
            "warning": warning, "retention_budget_is_advisory": True,
            "estimated_uncompressed_payload_bytes": payload_bytes,
            "metadata_allowance_bytes": metadata_bytes,
            "allocation_margin_factor": 1., "buffer_processing_factor": 1.,
            "timing_table_entries": count+1, "timing_table_capacity": caps.timing_table_capacity,
            "occupied_frame_s": occupied, "reconstruction_cells": cells,
            "marker_interval_cm1": marker_interval, "marker_width_us": marker_width_us,
            "labone_resident_capacity_guaranteed": False})


def discover_regular_capabilities(config_path=None, *, hf_factory=None, laser_factory=None):
    """Refresh HF2 accepted settings and installed MIRcat ranges without firing."""
    from control_app.devices.hf2li_service import HF2LIService
    from control_app.devices.mircat_service import MircatService
    hf = hf_factory() if hf_factory else HF2LIService.from_config(config_path=config_path)
    laser = laser_factory() if laser_factory else MircatService.from_config(config_path=config_path)
    try:
        hf.connect()
        capabilities = hf.discover_phase_scan_capabilities()
        laser.initialize()
        ranges = [laser.get_qcl_tuning_range(i) for i in range(1, laser.get_num_installed_qcls()+1)]
        capabilities["tuning_ranges"] = tuple((r["qcl"], r["min_cm1"], r["max_cm1"]) for r in ranges)
        return HF2Capabilities.from_dict(capabilities)
    finally:
        try:
            hf.close()
        finally:
            laser.deinitialize()
