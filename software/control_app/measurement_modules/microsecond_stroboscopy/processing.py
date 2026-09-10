"""Native-point reconstruction and response-convolved apparent recovery.

The observable is the in-phase HF2LI envelope of a continuous probe train.
The gamma kernel describes the n cascaded first-order lock-in sections, not
the T660 delay increment. Numerical integration evaluates the forward model
on the measured, potentially nonuniform delay grid; data are never interpolated.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
import math
from typing import Mapping

import numpy as np

ANALYSIS_VERSION = "microsecond-stroboscopy/1"


@dataclass(frozen=True)
class ResponseKernel:
    hf2_order: int = 1
    hf2_time_constant_s: float = 1e-6
    sample_rate_sps: float = 1e6
    reference_rate_sps: float = 1e6
    detector_latency_s: float = 0.
    reference_latency_s: float = 0.
    integration_aperture_s: float = 1e-6
    jitter_s: float = 0.
    time_zero_s: float = 0.
    qualified: bool = False
    qualification_id: str = "EXAMPLE ONLY"
    reference_order: int = 1
    reference_time_constant_s: float = 1e-6
    reference_alignment_uncertainty_s: float = 0.
    native_aperture_offsets_s: tuple[tuple[float, ...], ...] | None = None

    def __post_init__(self):
        if type(self.hf2_order) is not int or not 1 <= self.hf2_order <= 8:
            raise ValueError("HF2LI filter order must be 1..8")
        for name in ("hf2_time_constant_s", "sample_rate_sps", "reference_rate_sps",
                     "integration_aperture_s", "reference_time_constant_s"):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("jitter_s", "reference_alignment_uncertainty_s"):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) < 0:
                raise ValueError(f"{name} must be nonnegative")

    @classmethod
    def from_mapping(cls, value):
        if hasattr(value, "to_dict"):
            value = value.to_dict()
        elif hasattr(value, "__dataclass_fields__"):
            from dataclasses import asdict
            value = asdict(value)
        return cls(**{f.name: value[f.name] for f in fields(cls) if f.name in value})

    @property
    def rms_width_s(self):
        return math.sqrt(self.hf2_order * self.hf2_time_constant_s ** 2 + self.jitter_s ** 2
                         + self.integration_aperture_s ** 2 / 12 + 1 / (12 * self.sample_rate_sps ** 2))

    def aperture_quadrature(self):
        """Integrate the software aperture and jitter, never invent a rate boxcar.

        HF2 output decimation determines timestamp support; it does not establish
        an additional integration exposure of 1/rate. Native samples use their
        exact measured weights instead of a continuous software-aperture estimate.
        """
        aperture, aw = np.polynomial.legendre.leggauss(7)
        jitter, jw = np.polynomial.hermite.hermgauss(9)
        if self.native_aperture_offsets_s is not None:
            count = max(len(row) for row in self.native_aperture_offsets_s)
            offsets = np.zeros((len(self.native_aperture_offsets_s),count,9))
            weights = np.zeros_like(offsets)
            for i,row in enumerate(self.native_aperture_offsets_s):
                if not row: continue
                offsets[i,:len(row)] = (self.detector_latency_s+self.time_zero_s-np.asarray(row)[:,None]
                    +jitter[None,:]*self.jitter_s*math.sqrt(2))
                weights[i,:len(row)] = jw[None,:]/(math.sqrt(math.pi)*len(row))
            return offsets.reshape(len(offsets),-1),weights.reshape(len(weights),-1)
        offsets = (self.detector_latency_s + self.time_zero_s
                   + aperture[:,None]*self.integration_aperture_s/2
                   + jitter[None,:]*self.jitter_s*math.sqrt(2))
        weights = aw[:,None]/2*jw[None,:]/math.sqrt(math.pi)
        return offsets.ravel(), weights.ravel()

    def _filtered_exponential(self, time, tau):
        """Causal Erlang/exponential convolution, including near-equal constants."""
        time = np.maximum(np.asarray(time, float), 0)
        n, tc = self.hf2_order, self.hf2_time_constant_s
        rate = 1/tc - 1/tau
        if rate > 1e-5/tc:
            x = rate*time
            polynomial = sum(x**k/math.factorial(k) for k in range(n))
            cdf = 1-np.exp(-x)*polynomial
            small = x < 1
            z = x[small]
            term = z**n/math.factorial(n)
            series = term.copy()
            for k in range(1,35):
                term = term*z/(n+k)
                series += term
            cdf[small] = np.exp(-z)*series
            return np.exp(-time/tau)*cdf/(tc*rate)**n
        # Integrate over chemical age. This remains stable when tau is shorter
        # than tc and when the two constants coincide, without subtracting poles.
        nodes, weights = np.polynomial.legendre.leggauss(48)
        bound = np.minimum(time,40*tau)
        u = bound[...,None]*(nodes+1)/2
        lag = np.maximum(time[...,None]-u,0)
        impulse = (lag/tc)**(n-1)*np.exp(-lag/tc)/(tc*math.factorial(n-1))
        return np.sum(impulse*np.exp(-u/tau)*weights,axis=-1)*bound/2

    def recovery(self, delays_s, tau_s):
        if not math.isfinite(tau_s) or tau_s <= 0:
            raise ValueError("Recovery time must be positive")
        offsets, weights = self.aperture_quadrature()
        times = np.asarray(delays_s, dtype=float)[:, None] - offsets
        return np.sum(self._filtered_exponential(times,tau_s)*weights,axis=-1)

    def step(self, delays_s):
        offsets, weights = self.aperture_quadrature()
        x = np.maximum(np.asarray(delays_s)[:,None]-offsets,0)/self.hf2_time_constant_s
        return np.sum((1-np.exp(-x)*sum(x**k/math.factorial(k) for k in range(self.hf2_order)))*weights,axis=-1)

    def absorbance(self, delays_s, amplitudes, taus_s, *, offset=0., baseline=0.):
        """Filter intensity first, then take the logarithm, as the HF2LI does.

        The convergent exponential series avoids discretizing a chemical trace.
        The pump-induced absorbance is c + Σ a_i exp(-t/tau_i) for t >= 0.
        """
        terms = [(0., 1.)]
        for amplitude, tau in zip(amplitudes, taus_s):
            component = [(0.,1.)]
            coefficient = 1.
            for k in range(1,40):
                coefficient *= -math.log(10)*amplitude/k
                component.append((k/tau,coefficient))
                if abs(coefficient) < 1e-13: break
            terms = [(r1+r2,c1*c2) for r1,c1 in terms for r2,c2 in component if abs(c1*c2)>1e-14]
        filtered = np.ones(len(delays_s))+(10.**(-offset)-1)*self.step(delays_s)
        offsets, weights = self.aperture_quadrature()
        times = np.asarray(delays_s)[:,None]-offsets
        for rate, coefficient in terms:
            if rate:
                filtered += 10.**(-offset)*coefficient*np.sum(self._filtered_exponential(times,1/rate)*weights,axis=-1)
        return baseline-np.log10(np.maximum(filtered,np.finfo(float).tiny))


def align_native(sample, reference, *, sample_latency_s=0., reference_latency_s=0., tolerance_s=0.):
    """One-to-one timestamp matching. Missing samples stay unmatched, never filled."""
    st = np.asarray(sample.get("timestamp_s", []), float) - sample_latency_s
    rt = np.asarray(reference.get("timestamp_s", []), float) - reference_latency_s
    if tolerance_s < 0 or np.any(np.diff(st) <= 0) or np.any(np.diff(rt) <= 0):
        raise ValueError("Alignment needs strictly increasing native clocks and nonnegative tolerance")
    si, ri, residual = [], [], []
    j = 0
    for i, value in enumerate(st):
        while j < len(rt) and rt[j] < value - tolerance_s:
            j += 1
        if j >= len(rt):
            break
        candidate = j
        if j + 1 < len(rt) and abs(rt[j+1] - value) < abs(rt[j] - value):
            candidate = j + 1
        if np.isfinite(value) and abs(rt[candidate] - value) <= tolerance_s:
            si.append(i); ri.append(candidate); residual.append(rt[candidate] - value)
            j = candidate + 1
    return np.asarray(si, int), np.asarray(ri, int), np.asarray(residual, float)


def normalized_observable(sample, reference=None, *, q0=None, background_factor=None,
                          sample_latency_s=0., reference_latency_s=0., tolerance_s=0.,
                          sample_offset_variance=0., reference_offset_variance=0.):
    """Propagate paired sample/reference covariance into Q and delta absorbance.

    Inputs are phase-aligned signed X, with baseline/dark corrections already
    explicit in the native record. Negative or zero references are invalid.
    An absent B never yields a field named absolute absorbance/transmission.
    """
    sx = np.asarray(sample.get("x", []), float)
    flags = []
    if reference is None:
        valid = np.isfinite(sx) & (sx > 0)
        values = sx[valid]
        sample_indices, reference_indices = np.flatnonzero(valid), np.array([],int)
        covariance = np.full((2, 2), np.nan)
        ratio = float(np.mean(values)) if len(values) else math.nan
        variance = float(np.var(values, ddof=1) / len(values))+sample_offset_variance if len(values) > 1 else math.nan
        matched = len(values)
        residual = np.array([])
        label = "Sample in-phase signal"
    else:
        si, ri, residual = align_native(sample, reference, sample_latency_s=sample_latency_s,
                                       reference_latency_s=reference_latency_s, tolerance_s=tolerance_s)
        rx = np.asarray(reference.get("x", []), float)
        good = np.isfinite(sx[si]) & np.isfinite(rx[ri]) & (sx[si] > 0) & (rx[ri] > 0)
        sv, rv = sx[si[good]], rx[ri[good]]
        sample_indices, reference_indices = si[good],ri[good]
        matched = len(sv)
        covariance = np.cov(np.vstack([sv, rv]), ddof=1) / matched if matched > 1 else np.full((2, 2), np.nan)
        covariance += np.diag([sample_offset_variance,reference_offset_variance])
        sm, rm = (float(np.mean(sv)), float(np.mean(rv))) if matched else (math.nan, math.nan)
        ratio = sm / rm if rm > 0 else math.nan
        gradient = np.asarray([1 / rm, -sm / rm ** 2]) if rm > 0 else np.full(2, np.nan)
        variance = float(gradient @ covariance @ gradient)
        label = "Reference-normalized signal Q = S/R"
        if matched < len(sx) or matched < len(rx):
            flags.append("missing_or_invalid_reference_support")
    if matched == 0:
        flags.append("no_valid_support")
    result = {"value": ratio, "sample_reference_ratio": ratio if reference is not None else None,
              "standard_error": math.sqrt(max(0., variance)) if np.isfinite(variance) else math.nan,
              "covariance_of_means": covariance, "matched_count": matched,
              "alignment_residual_s": residual, "label": label, "flags": flags,
              "valid_sample_indices":sample_indices,"valid_reference_indices":reference_indices,
              "delta_absorbance": math.nan, "delta_absorbance_se": math.nan}
    if q0 is not None:
        baseline, baseline_variance = (q0.get("value"), q0.get("standard_error", math.nan) ** 2) if isinstance(q0, Mapping) else (q0, 0.)
        if baseline is not None and baseline > 0 and ratio > 0:
            result["delta_absorbance"] = -math.log10(ratio / baseline)
            result["delta_absorbance_se"] = math.sqrt(max(0., variance / ratio ** 2 + baseline_variance / baseline ** 2)) / math.log(10)
        else:
            result["flags"].append("invalid_unpumped_baseline")
    if background_factor is not None:
        b = float(background_factor)
        if b > 0 and ratio > 0:
            result["absolute_absorbance"] = -math.log10(ratio / b)
            result["absolute_transmission"] = ratio / b
        else:
            result["flags"].append("invalid_measured_background_factor")
    return result


def fit_recovery(delays_s, values, standard_error=None, *, kernel=None, allow_two=False,
                 order=None, check_cancelled=lambda: None):
    """Compare constant/no-response, one recovery, and optionally two using AICc.

    Rates are estimated freely on the observed interval. Covariance is a local
    uncertainty estimate; broad or ill-conditioned solutions are unresolvable.
    """
    kernel = kernel or ResponseKernel()
    t, y = np.asarray(delays_s, float), np.asarray(values, float)
    sigma = np.ones_like(y) if standard_error is None else np.asarray(standard_error, float)
    valid = np.isfinite(t) & np.isfinite(y) & np.isfinite(sigma) & (sigma > 0)
    if kernel.native_aperture_offsets_s is not None:
        if len(kernel.native_aperture_offsets_s) != len(t):
            raise ValueError("Native integration apertures must match fitted observations")
        kernel = replace(kernel,native_aperture_offsets_s=tuple(row for row,keep in zip(kernel.native_aperture_offsets_s,valid) if keep))
    t, y, sigma = t[valid], y[valid], sigma[valid]
    if len(t) < 7 or len(np.unique(t)) < 7:
        return {"disposition": "unresolvable", "reason": "Insufficient distinct valid delay support", "valid_count": len(t)}
    check_cancelled()
    gaps = np.diff(np.unique(t))
    lower = max(min(gaps) / 10, kernel.rms_width_s / 30, 1e-12)
    upper = max(np.ptp(t) * 100, lower * 100)
    step = kernel.step(t)
    offsets, weights = kernel.aperture_quadrature()
    effective_times = t[:, None] - offsets
    def response(tau):
        return np.sum(kernel._filtered_exponential(effective_times,tau)*weights,axis=-1)
    def solve(taus):
        design = np.column_stack([np.ones(len(t)), step] + [response(tau) for tau in taus]) if taus else np.ones((len(t), 1))
        coefficients = np.linalg.lstsq(design / sigma[:, None], y / sigma, rcond=None)[0]
        residual = y - design @ coefficients
        chi2 = float(np.sum((residual / sigma) ** 2))
        k = design.shape[1] + len(taus)
        aicc = chi2 + 2*k + (2*k*(k+1)/(len(t)-k-1) if len(t)>k+1 else math.inf)
        return {"taus_s": list(taus), "coefficients": coefficients, "chi2": chi2, "aicc": aicc,
                "parameter_count": k, "residuals": residual, "prediction": design @ coefficients}
    null = solve(())
    logs = np.linspace(math.log(lower), math.log(upper), 121)
    choices = []
    for index, log_tau in enumerate(logs):
        if index % 12 == 0: check_cancelled()
        choices.append(solve((math.exp(log_tau),)))
    best_index = min(range(len(choices)), key=lambda i: choices[i]["chi2"])
    left, right = logs[max(0, best_index-1)], logs[min(len(logs)-1, best_index+1)]
    # Bounded ternary refinement in log time avoids an additional scipy dependency.
    for _ in range(32):
        a, b = (2*left+right)/3, (left+2*right)/3
        if solve((math.exp(a),))["chi2"] < solve((math.exp(b),))["chi2"]: right = b
        else: left = a
    single = solve((math.exp((left+right)/2),))
    candidates = [null, single]
    if allow_two and len(t) > 10:
        best = None
        grid = np.geomspace(lower, upper, 30)
        for i, first in enumerate(grid[:-1]):
            check_cancelled()
            for second in grid[i+1:]:
                fit = solve((first, second))
                if best is None or fit["chi2"] < best["chi2"]: best = fit
        candidates.append(best)
    # The linear convolved-absorbance solve supplies initial values only.
    # Refine against the real recorder equation: log AFTER intensity filtering.
    for candidate in candidates[1:]:
        check_cancelled()
        n_tau = len(candidate["taus_s"])
        parameters = np.r_[candidate["coefficients"], np.log(candidate["taus_s"])]
        def prediction(parameters):
            return kernel.absorbance(t, parameters[2:2+n_tau], np.exp(parameters[-n_tau:]),
                                     offset=parameters[1], baseline=parameters[0])
        damping = 1e-3
        for iteration in range(18):
            check_cancelled()
            current = prediction(parameters)
            residual = (y-current)/sigma
            columns = []
            for index in range(len(parameters)):
                perturbed = parameters.copy()
                step_size = 1e-5 if index>=len(parameters)-n_tau else 1e-6
                perturbed[index] += step_size
                columns.append((prediction(perturbed)-current)/(sigma*step_size))
            jacobian = np.column_stack(columns)
            norm = np.maximum(np.linalg.norm(jacobian,axis=0),1e-20)
            scaled_jac = jacobian/norm
            delta = np.linalg.lstsq(scaled_jac.T@scaled_jac+damping*np.eye(len(parameters)),
                                   scaled_jac.T@residual,rcond=None)[0]/norm
            proposed = parameters+delta
            proposed[:2+n_tau] = np.clip(proposed[:2+n_tau],-2,2)
            proposed[-n_tau:] = np.clip(proposed[-n_tau:],math.log(lower),math.log(upper))
            if np.sum(((y-prediction(proposed))/sigma)**2) < residual@residual:
                parameters = proposed
                damping = max(1e-9,damping/3)
                if np.linalg.norm(delta)<1e-7: break
            else:
                damping *= 10
        candidate["coefficients"] = parameters[:2+n_tau]
        candidate["taus_s"] = list(np.exp(parameters[-n_tau:]))
        candidate["prediction"] = prediction(parameters)
        candidate["residuals"] = y-candidate["prediction"]
        candidate["chi2"] = float(np.sum((candidate["residuals"]/sigma)**2))
        k = candidate["parameter_count"]
        candidate["aicc"] = candidate["chi2"]+2*k+2*k*(k+1)/(len(t)-k-1)
    # Require a meaningful comparison gain to justify additional complexity.
    selected = null
    for candidate in candidates[1:]:
        if candidate["aicc"] < selected["aicc"] - 6: selected = candidate
    result = dict(selected)
    result.update({"analysis_version": ANALYSIS_VERSION, "criterion": "AICc, improvement > 6",
                   "candidates": [{"taus_s": c["taus_s"], "aicc": c["aicc"]} for c in candidates],
                   "delays_s": t, "valid_count": len(t), "kernel_qualified": kernel.qualified,
                   "resolution_rms_s": kernel.rms_width_s, "claim": "Apparent recovery; no molecular pathway assignment"})
    result["forward_equation"] = "-log10(h * 10^(-[offset + sum a exp(-t/tau)] H(t))) + baseline"
    if not selected["taus_s"]:
        result.update(disposition="unresolvable", reason="No supported recovery above noise/offset")
        return result
    taus = selected["taus_s"]
    coeff = selected["coefficients"]
    base_parameters = np.r_[coeff, taus]
    def actual_model(parameters):
        return kernel.absorbance(t,parameters[2:2+len(taus)],parameters[-len(taus):],offset=parameters[1],baseline=parameters[0])
    jac = []
    for i,value in enumerate(base_parameters):
        dx = max(abs(value)*1e-5,1e-10)
        changed = base_parameters.copy(); changed[i]+=dx
        jac.append((actual_model(changed)-selected["prediction"])/dx)
    jac = np.column_stack(jac)
    scaled = jac / sigma[:, None]
    covariance = np.linalg.pinv(scaled.T @ scaled)
    # Known sigma sets the noise scale; never shrink uncertainties for lucky residuals.
    covariance *= max(1., selected["chi2"] / max(1, len(t)-selected["parameter_count"]))
    tau_se = np.sqrt(np.maximum(0, np.diag(covariance)[-len(taus):]))
    tau_ci = np.asarray([[max(0., tau-1.96*se), tau+1.96*se] for tau,se in zip(taus,tau_se)])
    norms = np.linalg.norm(scaled, axis=0)
    condition = np.linalg.cond(scaled / np.maximum(norms, 1e-300))
    reduced_chi2 = selected["chi2"] / max(1,len(t)-selected["parameter_count"])
    unresolved = (not kernel.qualified or condition > 1e7 or reduced_chi2 > 3 or any(se > tau/2 for tau,se in zip(taus,tau_se))
                  or min(taus) < kernel.rms_width_s/2 or min(taus)<lower*1.05 or max(taus)>upper/1.05)
    latest = np.flatnonzero(t == max(t))
    unrecovered = abs(float(np.mean(y[latest]))) > 3 * math.sqrt(float(np.mean(sigma[latest]**2)))
    residual = selected["residuals"]
    correlation = float(np.corrcoef(residual[:-1], residual[1:])[0,1]) if np.std(residual)>0 else math.nan
    result.update(covariance=covariance, tau_standard_error_s=tau_se, tau_interval95_s=tau_ci,
                  reduced_chi2=reduced_chi2,
                  identifiability_condition=condition, residual_lag1_correlation=correlation,
                  disposition="unresolvable" if unresolved else ("unrecovered" if unrecovered else "apparent_recovery"),
                  observed_recovery_limit_s=float(max(t)), unrecovered_at_limit=unrecovered)
    if order is not None:
        acquisition_order = np.asarray(order, float)[valid]
        residual_order = np.argsort(acquisition_order)
        result["residuals_in_acquisition_order"] = residual[residual_order]
        result["order_drift_slope"] = float(np.polyfit(acquisition_order, residual, 1)[0])
    return result


def _aperture_stream(stream, start, stop):
    if stream is None: return None
    timestamps = np.asarray(stream.get("timestamp_s", []), float)
    mask = (timestamps >= start) & (timestamps <= stop)
    return {key: np.asarray(value)[mask] for key,value in stream.items()
            if isinstance(value, (np.ndarray, list, tuple)) and len(value) == len(timestamps)}


def process_run(record, *, check_cancelled=lambda: None, fit_models=True):
    """Reconstruct only observed support; preserve holes and excluded records."""
    settings = record.get("settings", {})
    response = ResponseKernel.from_mapping(settings.get("response", {}))
    blocks = record.get("native_blocks", record.get("blocks", []))
    normalization = record.get("qualification",{}).get("normalization",{})
    dark_offsets = normalization.get("dark_offsets",{})
    points, baselines = [], {}
    tolerance = min(0.49 / response.sample_rate_sps, 0.49 / response.reference_rate_sps)
    tolerance += response.reference_alignment_uncertainty_s
    for i, block in enumerate(blocks):
        check_cancelled()
        sample = block.get("sample", block.get("streams", {}).get("sample", {}))
        reference = block.get("reference", block.get("streams", {}).get("reference"))
        start, stop = block.get("aperture_start_s", -math.inf), block.get("aperture_stop_s", math.inf)
        sample = _aperture_stream(sample, start, stop)
        reference = _aperture_stream(reference, start+response.reference_latency_s-response.detector_latency_s,
                                     stop+response.reference_latency_s-response.detector_latency_s)
        if record.get("mode") == "dual" and reference is None:
            reference = {"timestamp_s": [], "x": []}
        raw_means = {}
        for role, native in (("sample", sample), ("reference", reference)):
            if native is not None:
                for quadrature in ("x", "y"):
                    values = np.asarray(native.get(quadrature, ()), float)
                    finite = values[np.isfinite(values)]
                    raw_means[f"raw_{role}_{quadrature}"] = float(np.mean(finite)) if len(finite) else math.nan
        variances={}
        for role,stream in (("sample",sample),("reference",reference)):
            dark=dark_offsets.get(role)
            variances[role]=0.
            if dark and stream is not None:
                if not dark.get("record_id") or not math.isfinite(float(dark["offset"])) or float(dark.get("standard_error",0))<0:
                    raise ValueError("Dark correction needs a measured record identity, finite offset and nonnegative uncertainty")
                stream["x"]=np.asarray(stream["x"])-float(dark["offset"])
                variances[role]=float(dark.get("standard_error",0))**2
        background = block.get("background_factor")
        background_id = block.get("background_record_id")
        for entry in normalization.get("background_factors",[]):
            if entry.get("wavenumber_cm1")==block["wavenumber_cm1"] and entry.get("record_id"):
                background,background_id=entry["value"],entry["record_id"]
        result = normalized_observable(sample, reference, sample_latency_s=response.detector_latency_s,
             reference_latency_s=response.reference_latency_s, tolerance_s=tolerance,
             background_factor=background if background_id else None,
             sample_offset_variance=variances["sample"],reference_offset_variance=variances["reference"])
        result.update(raw_means)
        selected_delay = float(block.get("delay_s", 0))
        actual_delay = float(block.get("actual_delay_s",selected_delay))
        program_events=block.get("program",{}).get("events",[])
        map_delay=float(program_events[0]["requested_delay_us"])*1e-6 if program_events else selected_delay
        result.update(block_id=block.get("block_id", str(i)), wavenumber_cm1=float(block["wavenumber_cm1"]),
                      delay_s=actual_delay, selected_delay_s=selected_delay,
                      map_delay_s=map_delay,background_record_id=background_id,
                      dark_record_ids={role:entry.get("record_id") for role,entry in dark_offsets.items()},
                      kind=block.get("kind", record.get("kind", "run")), order=i)
        optical_origin = block.get("optical_origin_s")
        origin = optical_origin if optical_origin is not None else block.get("electrical_origin_s")
        result["time_origin"] = "optical" if optical_origin is not None else "electrical"
        sample_times = np.asarray(sample.get("timestamp_s",[]))[result["valid_sample_indices"]]
        if origin is not None and len(sample_times):
            actual_delay=float(np.mean(sample_times)-float(origin))
            result["delay_s"]=actual_delay
        result["native_aperture_offsets_s"] = tuple((sample_times-float(origin)-actual_delay).tolist()) if origin is not None else None
        result["flags"] += list(block.get("flags", block.get("quality_flags", [])))
        invalid = {"clipping", "overload", "unlock", "lost_lock", "trigger_count_mismatch", "incomplete",
                   "electrical_event_count_mismatch", "timestamp_gap", "timestamp_order", "missing_aperture_support",
                   "insufficient_aperture_support"}
        result["valid"] = not invalid.intersection(result["flags"]) and np.isfinite(result["value"])
        points.append(result)
        if result["kind"] in ("baseline", "pump_off", "preliminary", "reset", "unpumped") and result["valid"]:
            baselines.setdefault(result["wavenumber_cm1"], []).append(result)
    # Complete preliminary records can supply Q0, but callers validate compatibility.
    preliminary = record.get("preliminary")
    if isinstance(preliminary, dict):
        for point in preliminary.get("processing", {}).get("points", []):
            if point.get("valid"):
                baselines.setdefault(point["wavenumber_cm1"], []).append(point)
    blank_by_wave = {}
    blank_record = record.get("blank", record.get("blank_record"))
    if record.get("mode") == "single" and isinstance(blank_record, dict):
        for point in blank_record.get("processing", {}).get("points", []):
            if point.get("valid") and point.get("value", 0) > 0:
                blank_by_wave.setdefault(point["wavenumber_cm1"], []).append(point)
    for point in points:
        options = baselines.get(point["wavenumber_cm1"], [])
        options = [b for b in options if not {"reset_nonrecovery", "initial_state_mismatch"}.intersection(b.get("flags", ()))]
        initial = [b for b in options if b.get("kind") in ("baseline", "unpumped")]
        preliminary_options = [b for b in options if b.get("kind") == "preliminary"]
        # Each run's initial unpumped state defines its own change. Later
        # recovery checks and older preliminary data remain diagnostics rather
        # than shifting that reference when the state drifts or fails to recover.
        options = initial or preliminary_options or options
        if options and point["valid"]:
            q0 = float(np.mean([b["value"] for b in options]))
            se0 = math.sqrt(sum(b["standard_error"]**2 for b in options))/len(options)
            if q0 > 0 and point["value"] > 0:
                point["q0"] = q0
                point["delta_absorbance"] = -math.log10(point["value"] / q0)
                point["delta_absorbance_se"] = math.sqrt((point["standard_error"]/point["value"])**2+(se0/q0)**2)/math.log(10)
        if not point["valid"]: point["delta_absorbance"] = math.nan
        blank_points = blank_by_wave.get(point["wavenumber_cm1"], [])
        if blank_points and point["valid"] and point["value"] > 0:
            background = float(np.mean([b["value"] for b in blank_points]))
            point["absolute_transmission"] = point["value"]/background
            point["absolute_absorbance"] = -math.log10(point["absolute_transmission"])
            point["background_source_block_ids"] = [b["block_id"] for b in blank_points]
    scientific = [p for p in points if p["kind"] in ("run", "pumped", "pump_on", "measurement")]
    spectral = sorted(set(p["wavenumber_cm1"] for p in points)|{float(p["wavenumber_cm1"]) for p in settings.get("spectral_points",[])})
    delays = sorted(set(p["map_delay_s"] for p in scientific)|{float(d)*1e-6 for d in settings.get("delays_us",[])}) if record.get("kind","run")=="run" else sorted(set(p["map_delay_s"] for p in scientific))
    grid, error, coverage = (np.full((len(delays),len(spectral)),np.nan),
                             np.full((len(delays),len(spectral)),np.nan),
                             np.zeros((len(delays),len(spectral)),int))
    ratio_grid = np.full_like(grid, np.nan)
    absolute_grid = np.full_like(grid, np.nan)
    actual_grid = np.full_like(grid, np.nan)
    for j, nu in enumerate(spectral):
        for i, delay in enumerate(delays):
            available = [p for p in scientific if p["wavenumber_cm1"]==nu and p["map_delay_s"]==delay and np.isfinite(p["delta_absorbance"])]
            if available:
                grid[i,j] = np.mean([p["delta_absorbance"] for p in available])
                error[i,j] = math.sqrt(sum(p["delta_absorbance_se"]**2 for p in available))/len(available)
                coverage[i,j] = len(available)
                actual_grid[i,j] = np.mean([p["delay_s"] for p in available])
            observed = [p for p in scientific if p["wavenumber_cm1"]==nu and p["map_delay_s"]==delay and p["valid"]]
            ratio_values = [p["sample_reference_ratio"] for p in observed if p.get("sample_reference_ratio") is not None]
            absolute_values = [p["absolute_absorbance"] for p in observed if "absolute_absorbance" in p]
            if ratio_values: ratio_grid[i,j] = np.mean(ratio_values)
            if absolute_values: absolute_grid[i,j] = np.mean(absolute_values)
    kinetics = []
    for j, nu in enumerate(spectral):
        check_cancelled()
        fitted_points = [p for p in scientific if p["wavenumber_cm1"]==nu and p["valid"]]
        fit_kernel = response
        optical_origin_unresolved = any(p["time_origin"] != "optical" for p in fitted_points)
        reset_nonrecovery = any("reset_nonrecovery" in p["flags"] for p in fitted_points)
        if optical_origin_unresolved or reset_nonrecovery:
            fit_kernel = replace(fit_kernel, qualified=False)
        reference_response_unresolved = False
        if record.get("mode")=="dual" and (response.hf2_order!=response.reference_order or
                response.hf2_time_constant_s!=response.reference_time_constant_s):
            transfer=normalization.get("reference_transfer",{})
            reference_response_unresolved = not (transfer.get("record_id") and transfer.get("static_reference_verified") is True)
            if reference_response_unresolved:
                fit_kernel=replace(response,qualified=False)
        if fitted_points and all(p["native_aperture_offsets_s"] for p in fitted_points):
            fit_kernel = replace(fit_kernel,native_aperture_offsets_s=tuple(p["native_aperture_offsets_s"] for p in fitted_points))
        fit = fit_recovery([p["delay_s"] for p in fitted_points],[p["delta_absorbance"] for p in fitted_points],
             [p["delta_absorbance_se"] for p in fitted_points],kernel=fit_kernel,
             order=[p["order"] for p in fitted_points],check_cancelled=check_cancelled) if fit_models else {
                 "disposition":"not_fitted","reason":"Native/coverage reconstruction only; no fit requested"}
        if reference_response_unresolved:
            fit["disposition"]="unresolvable"
            fit["reason"]="Unequal sample/reference filters require applicable measured static-reference/transfer qualification; reference dynamics cannot be assigned to the sample."
        if optical_origin_unresolved or reset_nonrecovery:
            fit["disposition"] = "unresolvable"
            fit["reason"] = "; ".join(reason for condition, reason in (
                (optical_origin_unresolved, "Optical time origin is uncalibrated; relative electrical-delay measurements retained"),
                (reset_nonrecovery, "Measured pre-pump levels did not recover within the requested event spacing"),
            ) if condition)
        kinetics.append({"label": f"{nu:g} cm⁻¹", "wavenumber_cm1": nu, "delay_s": np.asarray(delays),
                         "actual_delay_s":actual_grid[:,j],"value": grid[:,j], "standard_error": error[:,j], "fit":fit})
    # Integrate distinct local windows only; off-band points never bridge windows.
    windows = {}
    for point in settings.get("spectral_points", []):
        if point.get("role", "band") != "off_band" and point.get("role") != "offband":
            windows.setdefault(point.get("window_id", point.get("label", "local band")), []).append(float(point["wavenumber_cm1"]))
    for label, wave in windows.items():
        indexes = [spectral.index(nu) for nu in sorted(set(wave)) if nu in spectral]
        if len(indexes) < 3: continue
        axis = np.asarray([spectral[j] for j in indexes])
        weights = np.zeros(len(axis)); weights[:-1] += np.diff(axis)/2; weights[1:] += np.diff(axis)/2
        area = grid[:,indexes] @ weights
        se = np.sqrt(error[:,indexes]**2 @ weights**2)
        kinetics.append({"label": label, "delay_s": np.asarray(delays), "area": area,
                         "area_unit": "absorbance cm⁻¹", "standard_error": se,
                         "fit": {"disposition":"measured_area_curve",
                                 "reason":"Integrated ΔA is an area, not a detector intensity. Assess rates from constituent convolved wavelength fits; no scalar intensity logarithm is applied to an area."}})
    maps = {"wavenumber_cm1": spectral, "delay_s": delays, "actual_delay_s":actual_grid,
            "coordinate_basis":"Declared integration-aperture bins; native times retained and used in point fits",
            "delta_absorbance": grid, "standard_error": error}
    if record.get("mode") == "dual": maps["sample_reference_ratio"] = ratio_grid
    if np.any(np.isfinite(absolute_grid)): maps["absolute_absorbance"] = absolute_grid
    diagnostics = []
    for nu, baseline_points in baselines.items():
        valid_baseline = [p for p in baseline_points if "order" in p]
        if len(valid_baseline) >= 3:
            orders = np.asarray([p["order"] for p in valid_baseline])
            values = np.asarray([p["value"] for p in valid_baseline])
            if np.ptp(orders) > 0:
                slope = float(np.polyfit(orders,values,1)[0])
                noise = float(np.nanmean([p["standard_error"] for p in valid_baseline]))
                diagnostics.append({"kind":"baseline_order_drift", "wavenumber_cm1":nu,
                    "slope_per_block":slope,"excursion":slope*np.ptp(orders),
                    "flagged":bool(abs(slope*np.ptp(orders))>3*noise), "block_ids":[p["block_id"] for p in valid_baseline]})
    for p in points:
        if p["kind"] in ("pump_blocked", "pump_off", "artifact_control"):
            diagnostics.append({"kind":"pump_blocked_control", "block_id":p["block_id"],
                "delta_absorbance":p["delta_absorbance"],
                "flagged":bool(abs(p["delta_absorbance"])>3*p["delta_absorbance_se"])})
    optical_calibrated = bool(scientific) and all(b.get("optical_origin_s") is not None for b in blocks if b.get("kind") in ("pumped","run","measurement","pump_on"))
    return {"analysis_version": ANALYSIS_VERSION, "points": points, "maps": maps,
            "optical_arrival_calibrated":optical_calibrated,
            "kinetics": kinetics, "coverage": {"counts": coverage, "missing_points": int(np.sum(coverage==0))},
            "diagnostics": diagnostics,
            "provenance": {"native_block_ids": [p["block_id"] for p in points],
                           "normalization": "Q=S/R; delta A=-log10(Q/Q0); A only with measured B",
                           "kernel_qualification_id": response.qualification_id,
                           "uncertainty": "Paired covariance and Q0 uncertainty; fit local covariance, not preparation replication",
                           "reference_transfer": "Independent filters retained in settings; qualified matching required"}}
