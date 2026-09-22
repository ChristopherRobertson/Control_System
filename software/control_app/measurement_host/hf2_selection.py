"""Pure selection from the HF2LI values enumerated at application startup."""
import math


def select_supported(profile, *, time_scale_s, overrides=None, area=False):
    """Engineering sampling/filter targets, not a calibrated resolution claim.

    Time traces and sweeps target 1000 samples across the requested interval.
    Sparse pulse-area acquisition targets a tail contained within the cycle
    and at least eight samples per filter time constant.
    """
    overrides = overrides or {}
    orders = profile.get("orders", ())
    rates = [v for v in profile.get("rates_sps", ()) if 0 < v <= 231000.]
    tables = profile.get("timeconstants_by_order", {})
    if not orders or not rates or not math.isfinite(time_scale_s) or time_scale_s <= 0:
        return {}
    order = overrides.get("order") or min(orders, key=lambda v: abs(v-4))
    if order not in orders:
        raise ValueError("HF2LI filter order is not in the startup-supported choices")
    constants = tables.get(order, tables.get(str(order), ()))
    if not constants:
        return {}
    for key, accepted in (("timeconstant_s", constants), ("rate_sps", rates)):
        if key in overrides and not any(math.isclose(overrides[key], v, rel_tol=1e-9, abs_tol=1e-15) for v in accepted):
            raise ValueError(f"HF2LI {key} is not accepted for the selected filter order and stream configuration")
    target_tau = time_scale_s/(20*order) if area else time_scale_s/(1000*order)
    tau = overrides.get("timeconstant_s") or min(constants, key=lambda v: abs(math.log(v/target_tau)))
    target_rate = max(8/tau if area else 1000/time_scale_s, 4/tau)
    rate = overrides.get("rate_sps") or min((v for v in rates if v >= target_rate), default=max(rates))
    # Pulse-area sampling requires >=4 samples/tau. Quantize upward within
    # accepted device values instead of inventing an arbitrary time constant.
    if area and "timeconstant_s" not in overrides:
        supported = [v for v in constants if v >= max(tau, 4/rate)]
        if not supported:
            raise ValueError("HF2LI accepted filter values cannot provide four samples per time constant at the selected rate")
        tau = min(supported)
    return {"order": order, "timeconstant_s": tau, "rate_sps": rate}
