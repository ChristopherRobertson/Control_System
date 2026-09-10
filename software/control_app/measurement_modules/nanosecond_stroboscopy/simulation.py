"""IRF/noise-aware forward model and free-lifetime profile fits (NumPy only).

The molecular recovery is convolved with a Gaussian optical IRF plus Gaussian
jitter and a rectangular probe aperture. A separately qualified residual filter
blur can be represented by an exponential. Filter history is applied in event
order, independently of ns optical delay, avoiding the claim that a slow HF2LI
timestamp measures ns dynamics. The estimator fits the convolved observable.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np

_AP_X, _AP_W = np.polynomial.legendre.leggauss(24)
_FILTER_X, _FILTER_W = np.polynomial.laguerre.laggauss(24)


def _kernel_dict(kernel: Mapping[str, Any] | Any) -> dict[str, Any]:
    if hasattr(kernel, "kernel"):
        return kernel.kernel()
    return dict(kernel or {})


def _log_erfc(x: float) -> float:
    if x < 25:
        return math.log(math.erfc(x))
    # Stable positive-tail expansion, avoiding overflow * underflow at tau -> 0.
    inv = 1 / (x * x)
    return -x * x - math.log(x) - 0.5 * math.log(math.pi) + math.log(1 - 0.5 * inv + 0.75 * inv * inv - 1.875 * inv ** 3)


def _gaussian_recovery(t: np.ndarray, tau: float, sigma: float) -> np.ndarray:
    if sigma <= 0:
        return np.where(t >= 0, np.exp(-np.maximum(t, 0) / tau), 0.0)
    z = (sigma * sigma / tau - t) / (math.sqrt(2) * sigma)
    erfc_log = np.fromiter((_log_erfc(float(x)) for x in z.flat), dtype=float, count=z.size).reshape(t.shape)
    return 0.5 * np.exp(np.clip(sigma * sigma / (2 * tau * tau) - t / tau + erfc_log, -745, 700))


def _gaussian_step(t: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0:
        return (t >= 0).astype(float)
    z = -t / (math.sqrt(2) * sigma)
    return 0.5 * np.fromiter((math.erfc(float(x)) for x in z.flat), dtype=float, count=z.size).reshape(t.shape)


def convolved_response(delay_ns: Sequence[float], lifetime_ns: float | None, kernel: Mapping[str, Any] | Any) -> np.ndarray:
    """Unit recovery; lifetime=None gives the convolved persistent step."""
    k = _kernel_dict(kernel)
    t = np.asarray(delay_ns, dtype=float)
    if lifetime_ns is not None and (not math.isfinite(lifetime_ns) or lifetime_ns <= 0):
        raise ValueError("Lifetime must be finite and positive")
    sigma = math.hypot(float(k.get("irf_sigma_ns", 0)), float(k.get("timing_jitter_ns", 0)))
    aperture = float(k.get("integration_aperture_ns", k.get("aperture_ns", 0)))
    blur = float(k.get("filter_blur_ns", 0))
    if sigma < 0 or aperture < 0 or blur < 0 or not all(math.isfinite(x) for x in (sigma, aperture, blur)):
        raise ValueError("IRF, jitter, aperture and residual filter blur must be finite and nonnegative")
    t = t - float(k.get("time_zero_ns", 0))
    func = lambda x: _gaussian_step(x, sigma) if lifetime_ns is None else _gaussian_recovery(x, lifetime_ns, sigma)
    # Delay is probe-centre minus pump arrival; aperture integrates around centre.
    if aperture:
        shifted = t[..., None] + aperture * _AP_X / 2
        if blur:
            values = func(shifted[..., None] - blur * _FILTER_X)
            response = np.sum(np.sum(values * _FILTER_W, axis=-1) * _AP_W / 2, axis=-1)
        else:
            response = np.sum(func(shifted) * _AP_W / 2, axis=-1)
    elif blur:
        response = np.sum(func(t[..., None] - blur * _FILTER_X) * _FILTER_W, axis=-1)
    else:
        response = func(t)
    return response


def apply_filter_history(values: Sequence[float], memory_fraction: float, *, initial: float = 0.0) -> np.ndarray:
    """First-order event-history mixing after impulse extraction, when qualified.

    memory_fraction is an empirical residual mixing coefficient, or conservative
    gamma-tail fraction for an n-pole lowpass. Full native filter stream persists.
    """
    memory = float(memory_fraction)
    if not 0 <= memory <= 1:
        raise ValueError("Residual filter memory fraction must be in [0, 1]")
    result = np.empty(len(values), dtype=float)
    last = float(initial)
    for i, value in enumerate(values):
        last = (1 - memory) * float(value) + memory * last
        result[i] = last
    return result


def forward_signal(delay_ns: Sequence[float], lifetime_ns: float, amplitude: float, kernel: Mapping[str, Any] | Any,
                   *, baseline: float = 0.0, long_lived_offset: float = 0.0,
                   reset_residual_fraction: float = 0.0, drift_per_event: float = 0.0,
                   apply_history: bool = True) -> np.ndarray:
    k = _kernel_dict(kernel)
    result = baseline + amplitude * convolved_response(delay_ns, lifetime_ns, k) + long_lived_offset * convolved_response(delay_ns, None, k)
    if reset_residual_fraction:
        # Cumulative-state contribution is retained and invalidates equivalent-event claims.
        result += amplitude * reset_residual_fraction * np.arange(len(result))
    result += drift_per_event * np.arange(len(result))
    if apply_history and k.get("filter_memory_fraction", 0):
        result = baseline + apply_filter_history(result - baseline, k["filter_memory_fraction"])
    return result


def simulate_trace(delay_ns: Sequence[float], lifetime_ns: float, amplitude: float,
                   kernel: Mapping[str, Any] | Any, *, noise_sd: float = 0.0001,
                   seed: int = 0, **kwargs: Any) -> dict[str, Any]:
    if not math.isfinite(noise_sd) or noise_sd <= 0:
        raise ValueError("Noise standard deviation must be finite and positive")
    k = _kernel_dict(kernel)
    truth = forward_signal(delay_ns, lifetime_ns, amplitude, k, **kwargs)
    rng = np.random.default_rng(seed)
    observed = truth + rng.normal(0, noise_sd, len(truth))
    if kwargs.get("reset_residual_fraction", 0):
        k["reset_equivalent"] = False
    return {"delay_ns": list(delay_ns), "delta_a": observed.tolist(), "uncertainty": [noise_sd] * len(truth),
            "truth": truth.tolist(), "kernel": k, "lifetime_ns": lifetime_ns, "amplitude": amplitude,
            "provenance": {"generator": "nanosecond-forward-v1", "seed": seed, "value_source": "EXAMPLE ONLY known synthetic truth"}}


def _design(t: np.ndarray, tau: float, kernel: dict[str, Any]) -> np.ndarray:
    fast = convolved_response(t, tau, kernel)
    slow = convolved_response(t, None, kernel)
    memory = float(kernel.get("filter_memory_fraction", 0))
    if memory:
        fast, slow = apply_filter_history(fast, memory), apply_filter_history(slow, memory)
    return np.column_stack((fast, slow, np.ones(len(t))))


def _profile(t: np.ndarray, y: np.ndarray, sd: np.ndarray, k: dict[str, Any], taus: np.ndarray) -> tuple[np.ndarray, list[np.ndarray]]:
    chi, coefficients = [], []
    for tau in taus:
        x = _design(t, float(tau), k)
        beta = np.linalg.lstsq(x / sd[:, None], y / sd, rcond=None)[0]
        chi.append(float(np.sum(((y - x @ beta) / sd) ** 2)))
        coefficients.append(beta)
    return np.asarray(chi), coefficients


def identify_lifetime(delay_ns: Sequence[float], delta_a: Sequence[float], uncertainty: Sequence[float] | float,
                      kernel: Mapping[str, Any] | Any, *, tau_bounds_ns: tuple[float, float] | None = None) -> dict[str, Any]:
    """Profile a free lifetime with nuisance bleach, persistent offset and baseline.

    No literature lifetime/fraction is fixed. A nominal best fit is never exposed
    as a resolved lifetime when profile support includes prompt or upper limits.
    """
    k = _kernel_dict(kernel)
    t, y = np.asarray(delay_ns, dtype=float), np.asarray(delta_a, dtype=float)
    sd = np.broadcast_to(np.asarray(uncertainty, dtype=float), y.shape).copy()
    if t.shape != y.shape or t.ndim != 1:
        raise ValueError("Delay, signal and uncertainty require matching one-dimensional support")
    valid = np.isfinite(t) & np.isfinite(y) & np.isfinite(sd) & (sd > 0)
    excluded = np.flatnonzero(~valid).tolist()
    t, y, sd = t[valid], y[valid], sd[valid]
    base = {"model": "Gaussian-IRF+jitter/aperture/filter-convolved exponential plus persistent step and baseline",
            "analysis_version": "nanosecond-profile-v1", "valid_count": int(len(t)), "excluded_indices": excluded,
            "lifetime_ns": None, "lifetime_interval_ns": None, "upper_bound_ns": None, "kernel": k}
    if len(t) < 7 or len(np.unique(t)) < 6 or not np.any(t < k.get("time_zero_ns", 0)):
        return {**base, "outcome": "insufficient_support", "reasons": ["Need finite negative controls and at least six distinct supported delays"], "predicted": []}
    span = float(np.ptp(t))
    effective_sigma = math.sqrt(float(k.get("irf_sigma_ns", 0)) ** 2 + float(k.get("timing_jitter_ns", 0)) ** 2 + float(k.get("integration_aperture_ns", 0)) ** 2 / 12 + float(k.get("filter_blur_ns", 0)) ** 2)
    lower, upper = tau_bounds_ns or (max(0.01, effective_sigma * 0.002), max(span * 10, 1.0))
    if not 0 < lower < upper:
        raise ValueError("Positive ordered lifetime profile bounds are required")
    taus = np.geomspace(lower, upper, 221)
    chi, betas = _profile(t, y, sd, k, taus)
    best = int(np.argmin(chi))
    # Refine only the local minimum, preserving complete broad identifiability profile.
    if 0 < best < len(taus) - 1:
        dense = np.geomspace(taus[best - 1], taus[best + 1], 41)
        taus = np.unique(np.concatenate((taus, dense)))
        chi, betas = _profile(t, y, sd, k, taus)
        best = int(np.argmin(chi))
    beta = betas[best]
    supported = np.flatnonzero(chi <= chi[best] + 3.841458820694124)
    lo, hi = float(taus[supported[0]]), float(taus[supported[-1]])
    reasons = []
    if supported[0] == 0:
        reasons.append("Profile includes prompt/unresolved response; amplitude and lifetime are confounded")
    if supported[-1] == len(taus) - 1:
        reasons.append("Profile includes the upper observation/model bound; later-time coverage is inadequate")
    if hi / lo > 4:
        reasons.append("Lifetime interval spans more than a factor of four under the measured noise/kernel")
    if chi[0] - chi[best] < 9:
        reasons.append("Data do not distinguish the fitted recovery from a prompt component at the prespecified delta-chi-squared 9 threshold")
    if not k.get("reset_equivalent", False):
        reasons.append("Equivalent sample reset is unverified or failed; cumulative photoproduct invalidates lifetime identification")
    if not k.get("irf_qualified", False):
        reasons.append("Optical time zero/IRF is unqualified; only model-conditional exploratory fits are available")
    dof = max(1, len(t) - 4)
    if chi[best] / dof > 3:
        reasons.append("Convolved model fails residual/noise consistency; drift, filter/reset history or model alternatives are unresolved")
    if excluded and k.get("filter_memory_fraction", 0) > 0.001:
        reasons.append("Missing event history prevents a valid filter-memory correction")
    pred = _design(t, float(taus[best]), k) @ beta
    resolved = not reasons
    return {**base, "outcome": "resolved" if resolved else "prompt_unresolved_bound",
            "lifetime_ns": float(taus[best]) if resolved else None,
            "candidate_lifetime_ns": float(taus[best]),
            "lifetime_interval_ns": [lo, hi] if resolved else None,
            "model_conditional_interval_ns": [lo, hi],
            "upper_bound_ns": hi if not resolved and supported[-1] < len(taus) - 1 and k.get("reset_equivalent", False) and k.get("irf_qualified", False) and chi[best] / dof <= 3 else None,
            "amplitude": float(beta[0]), "long_lived_offset": float(beta[1]), "baseline": float(beta[2]),
            "prompt_observed_amplitude": float(np.ptp(pred)),
            "predicted": pred.tolist(), "supported_delay_ns": t.tolist(), "residuals": (y - pred).tolist(),
            "chi_squared": float(chi[best]), "degrees_of_freedom": dof,
            "profile_tau_ns": taus.tolist(), "profile_chi_squared": chi.tolist(),
            "reasons": reasons, "identifiability_basis": "95% one-parameter profile interval; prompt comparison delta chi-squared >=9; reset/IRF evidence and residual consistency required"}


def fit_shared_lifetimes(traces: Sequence[Mapping[str, Any]], kernel: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Compare shared versus separate band kinetics on native supported traces."""
    if len(traces) < 2:
        return {"outcome": "insufficient_support", "reason": "Two sample-fitted populations are required"}
    k = _kernel_dict(kernel)
    independent = [identify_lifetime(tr["delay_ns"], tr["delta_a"], tr["uncertainty"], k) for tr in traces]
    if any("profile_tau_ns" not in fit for fit in independent):
        return {"outcome": "insufficient_support", "independent": independent}
    lower = min(fit["profile_tau_ns"][0] for fit in independent)
    upper = max(fit["profile_tau_ns"][-1] for fit in independent)
    taus = np.geomspace(lower, upper, 321)
    total = np.zeros_like(taus)
    for tr in traces:
        t, y = np.asarray(tr["delay_ns"], dtype=float), np.asarray(tr["delta_a"], dtype=float)
        sd = np.broadcast_to(np.asarray(tr["uncertainty"], dtype=float), y.shape)
        valid = np.isfinite(t) & np.isfinite(y) & np.isfinite(sd) & (sd > 0)
        chi, _ = _profile(t[valid], y[valid], sd[valid], k, taus)
        total += chi
    best = int(np.argmin(total))
    if 0 < best < len(taus) - 1:
        dense = np.geomspace(taus[best - 1], taus[best + 1], 81)
        taus = np.unique(np.concatenate((taus, dense)))
        total = np.zeros_like(taus)
        for tr in traces:
            t, y = np.asarray(tr["delay_ns"], dtype=float), np.asarray(tr["delta_a"], dtype=float)
            sd = np.broadcast_to(np.asarray(tr["uncertainty"], dtype=float), y.shape)
            valid = np.isfinite(t) & np.isfinite(y) & np.isfinite(sd) & (sd > 0)
            chi, _ = _profile(t[valid], y[valid], sd[valid], k, taus)
            total += chi
        best = int(np.argmin(total))
    separate_chi = sum(fit["chi_squared"] for fit in independent)
    difference = max(0, float(total[best]) - separate_chi)
    all_resolved = all(fit["outcome"] == "resolved" for fit in independent)
    threshold = 9 * (len(traces) - 1)
    return {"outcome": "distinct_supported" if all_resolved and difference > threshold else "shared_compatible" if all_resolved else "prompt_unresolved_bound",
            "shared_lifetime_ns": float(taus[best]) if all_resolved else None,
            "shared_chi_squared": float(total[best]), "separate_chi_squared": separate_chi,
            "delta_chi_squared": difference, "distinct_threshold": threshold,
            "independent": independent, "profile_tau_ns": taus.tolist(), "shared_profile_chi_squared": total.tolist(),
            "claim_limit": "Shared compatibility does not prove common mechanism; separate state identities and uncertainty remain retained"}


def evaluate_schedule(delay_ns: Sequence[float], lifetime_ns: float, amplitude: float,
                      kernel: Mapping[str, Any] | Any, *, noise_sd: float, repetitions: int = 1,
                      trials: int = 12, seed: int = 0, cancel_check: Any = None) -> dict[str, Any]:
    """Known-truth prospective recovery test; never converts priors into operating values."""
    if repetitions < 1 or trials < 1:
        raise ValueError("Positive technical repetition/trial counts are required")
    fits = []
    for trial in range(trials):
        if cancel_check is not None:
            cancel_check()
        sim = simulate_trace(delay_ns, lifetime_ns, amplitude, kernel, noise_sd=noise_sd / math.sqrt(repetitions), seed=seed + trial)
        fits.append(identify_lifetime(sim["delay_ns"], sim["delta_a"], sim["uncertainty"], sim["kernel"]))
    estimates = [f["lifetime_ns"] for f in fits if f["outcome"] == "resolved"]
    coverage = sum(f["lifetime_interval_ns"] is not None and f["lifetime_interval_ns"][0] <= lifetime_ns <= f["lifetime_interval_ns"][1] for f in fits) / trials
    return {"trials": trials, "resolved_fraction": len(estimates) / trials,
            "relative_bias": float(np.mean(estimates) / lifetime_ns - 1) if estimates else None,
            "interval_coverage": coverage, "known_truth_lifetime_ns": lifetime_ns,
            "noise_per_average": noise_sd / math.sqrt(repetitions), "fits": fits,
            "value_source": "EXAMPLE ONLY prospective known-truth simulation; requires actual noise/IRF/reset evidence for confirmatory acceptance"}
