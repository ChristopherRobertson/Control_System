"""Shared Phase Scan-style vocabulary for experiment previews (no device I/O)."""
from dataclasses import asdict, is_dataclass
import math


def plain(value):
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return asdict(value) if is_dataclass(value) else (value or {})


def duration_text(seconds, *, lower_bound=False):
    if not isinstance(seconds, (int, float)) or not math.isfinite(seconds):
        return "Pending startup settings"
    if seconds >= 3600:
        text = f"{seconds/3600:.2f} h"
    elif seconds >= 60:
        text = f"{seconds/60:.2f} min"
    else:
        text = f"{seconds:.3g} s"
    return ("At least " if lower_bound else "About ") + text


def summary_rows(plan, procedure_rows, *, slow_scan=False):
    """Retain procedure-specific facts, consolidate common instrument rows."""
    s = plain(getattr(plan, "resolved_settings", None) or plan.settings)
    resolved = plain(getattr(plan, "resolved", {}))
    selected = plain(getattr(plan, "selected", {}))
    budget = plain(getattr(plan, "estimates", None) or getattr(plan, "budget", {}))
    aliases = {"Schedule": "Sequence", "Acquisition": "Sequence", "Speed / scans": "Sequence",
        "Observation": "Acquisition window", "Movie": "Acquisition window",
        "Delay": "Delay range", "HF2LI impulse area": "Selected HF2LI", "HF2 response": "Selected HF2LI",
        "HF2LI filters": "Selected HF2LI", "HF2LI": "Selected HF2LI", "Filter": "Selected HF2LI",
        "Detector rate": "Selected HF2LI", "Sample rate": "Selected HF2LI",
        "Storage": "Preflight capacity", "Native storage": "Preflight capacity",
        "Estimated memory": "Preflight capacity", "Memory / storage": "Preflight capacity"}
    rows = {}
    for label, value in procedure_rows:
        if label in ("Duration", "Estimated duration", "Estimated time", "Laser current", "Pulse duty"):
            continue
        key = aliases.get(label, label)
        rows[key] = rows[key]+"; "+str(value) if key in rows else str(value)
    lasers = s.get("laser_settings", {})
    def fmt(value, unit):
        return f"{value:g} {unit}" if isinstance(value, (int, float)) else "pending"
    if slow_scan:
        current = selected.get("current_ma", s.get("current_ma"))
        rate = selected.get("repetition_rate_hz", s.get("repetition_rate_hz"))
        width = selected.get("pulse_width_s", s.get("pulse_width_s"))
        pulse = "CW" if s.get("laser_mode") == "cw" else fmt(rate, "Hz")+" / "+fmt(width*1e9 if width else None, "ns")
        rows["MIRcat settings"] = pulse+"; "+fmt(current, "mA")
        tau, order = selected.get("time_constant_s"), selected.get("filter_order")
        rate = selected.get("hf2li", {}).get("sample", {}).get("rate_sps")
    else:
        timing = s.get("timing", {})
        rate = s.get("probe_rate_hz", timing.get("probe_rate_hz", lasers.get("probe_repetition_rate_hz", s.get("probe_frequency_hz"))))
        width = s.get("probe_width_ns", timing.get("probe_width_ns", lasers.get("probe_pulse_width_ns", s.get("probe_command_width_ns"))))
        if rate is None and s.get("probe_period_s"):
            rate = 1/s["probe_period_s"]
        if width is None and s.get("probe_pulse_width_s"):
            width = s["probe_pulse_width_s"]*1e9
        rows["MIRcat settings"] = ("External "+fmt(rate, "Hz")+" / "+fmt(width, "ns")+
            "; internal 2.1 MHz / 142 ns; "+fmt(lasers.get("qcl_current_ma", s.get("mircat_current_ma", 1000.)), "mA"))
        rows["Nd:YAG settings"] = (fmt(lasers.get("pump_repetition_rate_hz", 10.), "Hz maximum")+
            "; FIRE–Q-switch "+fmt(lasers.get("fire_to_qswitch_us", 250.), "µs")+"; 540 nm")
        sample = resolved.get("sample", {})
        response = s.get("response", {})
        tau = sample.get("timeconstant_s", response.get("hf2_time_constant_s", s.get("filter_time_constant_s", s.get("sample_filter_timeconstant_s"))))
        order = sample.get("order", response.get("hf2_order", s.get("filter_order", s.get("sample_filter_order"))))
        rate = sample.get("rate_sps", response.get("sample_rate_sps", s.get("hf2li_rate_hz", s.get("sample_rate_hz"))))
    profiles = []
    for role in (("sample", "reference") if s.get("mode") == "dual" else ("sample",)):
        if slow_scan:
            profile = selected.get("hf2li", {}).get(role, {})
        elif resolved.get(role):
            profile = resolved[role]
        elif s.get("response"):
            r = s["response"]
            profile = {"rate_sps": r.get("sample_rate_sps" if role == "sample" else "reference_rate_sps"),
                "order": r.get("hf2_order" if role == "sample" else "reference_order"),
                "timeconstant_s": r.get("hf2_time_constant_s" if role == "sample" else "reference_time_constant_s")}
        else:
            prefix = "" if role == "sample" else "reference_"
            profile = {"rate_sps": s.get(prefix+"hf2li_rate_hz", s.get(role+"_rate_hz")),
                "order": s.get(prefix+"filter_order", s.get(role+"_filter_order")),
                "timeconstant_s": s.get(prefix+"filter_time_constant_s", s.get(role+"_filter_timeconstant_s"))}
        if profile.get("rate_sps") and profile.get("timeconstant_s") and profile.get("order"):
            profiles.append(role.title()+": "+fmt(profile["rate_sps"], "Sa/s")+"; τ "+fmt(profile["timeconstant_s"], "s")+f"; order {profile['order']}")
    if profiles:
        rows["Selected HF2LI"] = " / ".join(profiles)
    if "Preflight capacity" not in rows:
        storage = budget.get("native_storage_bytes", budget.get("storage_bytes"))
        rows["Preflight capacity"] = fmt(storage/1024**2, "MiB storage") if storage is not None else "Pending startup settings"
    if "Effective resolution" not in rows:
        rows["Effective resolution"] = (("Sample interval "+fmt(1/rate, "s") if rate else "Sample interval pending")+
            ("; nominal filter response "+fmt(tau*math.sqrt(order), "s RMS") if tau and order else "; filter response pending")+
            "; optical resolution requires measured response")
    seconds = next((budget[k] for k in ("wall_clock_s", "wall_time_s", "measurement_s", "total_s") if budget.get(k) is not None), None)
    lower = bool(budget.get("wall_clock_is_lower_bound") or budget.get("unresolved_estimate_terms") or budget.get("capture_estimate_complete") is False)
    rows["Estimated completion"] = duration_text(seconds, lower_bound=lower)
    if seconds is not None and lower:
        rows["Estimated completion"] += "; unresolved setup/transfer overhead adds time"
    elif seconds is not None:
        rows["Estimated completion"] += "; includes configured overhead allowances"
    order_keys = ("Range", "Acquisition window", "Sequence", "Delay range", "Cadence", "Recovery",
        "Nd:YAG settings", "MIRcat settings", "Selected HF2LI", "Effective resolution", "Preflight capacity", "Estimated completion", "Interpretation")
    return [(k, rows.pop(k)) for k in order_keys if k in rows]+list(rows.items())


def remaining_text(estimate_s, elapsed_s):
    if not isinstance(estimate_s, (int, float)) or not math.isfinite(estimate_s):
        return "Remaining time pending"
    remaining = estimate_s-elapsed_s
    if remaining <= 0:
        return "Initial estimate exceeded; operation still running"
    return duration_text(remaining)+" remaining"
