from dataclasses import replace
import json

import numpy as np
import pytest

from control_app.measurement_modules.microsecond_stroboscopy.processing import (
    ResponseKernel, align_native, fit_recovery, normalized_observable, process_run,
)
from control_app.measurement_modules.microsecond_stroboscopy.persistence import save_run, load_run


def stream(t, x):
    return {"timestamp_s": np.asarray(t), "x": np.asarray(x), "y": np.zeros(len(x))}


def test_us_native_roundtrip_exact_unsigned_clocks_nan_and_revisions(tmp_path):
    values = np.array([0, 2**53+1, 2**64-1], dtype=np.uint64)
    record = {"mode": "dual", "settings": {"condition_profile_id": "77K-Mb-G-F"},
              "native_blocks": [{"timestamp_ticks": values, "x": np.array([1., np.nan, -0.]), "tuple": (1,2)}],
              "disposition": "interrupted", "restoration": {"verified": False, "error": "retained"}}
    first = save_run(tmp_path, record)
    record["disposition"] = "failed"
    second = save_run(tmp_path, record)
    loaded = load_run(tmp_path, "dual", "77K-Mb-G-F")
    assert first != second and first.exists()
    assert loaded["native_blocks"][0]["timestamp_ticks"].tobytes() == values.tobytes()
    assert np.isnan(loaded["native_blocks"][0]["x"][1])
    assert np.signbit(loaded["native_blocks"][0]["x"][2])
    assert loaded["native_blocks"][0]["tuple"] == (1,2)
    assert load_run(first)["disposition"] == "interrupted"
    with pytest.raises(ValueError, match="detector mode"): load_run(first,"single")
    assert load_run(first,"dual","RT-Mb-R-K")["settings"]["condition_profile_id"] == "77K-Mb-G-F"


def test_us_native_rejects_path_escape_and_object_arrays(tmp_path):
    with pytest.raises(ValueError, match="Object arrays"):
        save_run(tmp_path, {"mode":"single", "bad":np.array([{}],dtype=object)})
    (tmp_path/"bad.json").write_text(json.dumps({"record_file":"../elsewhere.json"}))
    with pytest.raises(ValueError, match="local filename"):
        load_run(tmp_path/"bad.json")


def test_us_dual_alignment_covariance_and_absolute_label_boundary():
    t = np.arange(6)*1e-6
    s = stream(t, [1,2,3,4,5,6])
    r = stream(t+0.4e-6, [.5,1,1.5,2,2.5,3])
    q = normalized_observable(s,r,q0=2.,reference_latency_s=.4e-6,tolerance_s=1e-12)
    assert q["matched_count"] == 6 and q["sample_reference_ratio"] == 2
    assert abs(q["delta_absorbance"]) < 1e-15
    assert q["standard_error"] < 1e-7  # common-mode covariance cancels
    assert "absolute_absorbance" not in q and "absolute_transmission" not in q
    q = normalized_observable(s,r,q0=2.,background_factor=4.,reference_latency_s=.4e-6,tolerance_s=1e-12)
    assert q["absolute_absorbance"] == pytest.approx(np.log10(2))
    missing = normalized_observable(s,r,q0=2.,tolerance_s=.1e-6)
    assert missing["matched_count"] == 0 and np.isnan(missing["delta_absorbance"])


def test_us_no_interpolation_bad_reference_and_clock_errors():
    s = stream([0,1,2,3], [1,1,1,1])
    r = stream([0,2,3], [1,0,-1])
    q = normalized_observable(s,r,q0=1.)
    assert q["matched_count"] == 1 and "missing_or_invalid_reference_support" in q["flags"]
    with pytest.raises(ValueError,match="increasing"):
        align_native(stream([0,0],[1,1]),r)


@pytest.mark.parametrize("tau", [185e-6, 1e-3])
def test_us_known_truth_nonuniform_convolved_recovery(tau):
    kernel = ResponseKernel(hf2_order=3,hf2_time_constant_s=4e-6,
                            integration_aperture_s=3e-6,jitter_s=.4e-6,qualified=True)
    t = np.r_[-50e-6,-20e-6,0.,np.geomspace(5e-6,10e-3,40)]
    y = kernel.absorbance(t,[-.02],[tau])
    fit = fit_recovery(t,y,np.full(len(t),2e-5),kernel=kernel)
    assert fit["taus_s"][0] == pytest.approx(tau,rel=.015)
    assert fit["disposition"] == "apparent_recovery"
    assert fit["tau_interval95_s"][0,0] < tau < fit["tau_interval95_s"][0,1]
    assert len(fit["candidates"]) == 2


def test_us_insufficient_snr_pump_blocked_unresolved_irf_and_unrecovered():
    kernel = ResponseKernel(qualified=True)
    t = np.r_[-20e-6,0,np.geomspace(2e-6,5e-3,30)]
    blocked = fit_recovery(t,np.zeros(len(t)),np.full(len(t),.001),kernel=kernel)
    assert blocked["disposition"] == "unresolvable"
    low_snr = fit_recovery(t,1e-5*kernel.recovery(t,1e-3),np.full(len(t),.001),kernel=kernel)
    assert low_snr["disposition"] == "unresolvable"
    y = kernel.absorbance(t,[-.02],[1e-3],offset=-.01)
    fit = fit_recovery(t,y,np.full(len(t),1e-5),kernel=kernel)
    assert fit["disposition"] == "unrecovered" and fit["unrecovered_at_limit"]
    unknown = fit_recovery(t,y,np.full(len(t),1e-5),kernel=replace(kernel,qualified=False))
    assert unknown["disposition"] == "unresolvable"


def test_us_processing_missing_and_flagged_blocks_remain_gaps():
    blocks = []
    for nu in [1943.,1944.,1945.]:
        blocks.append({"block_id":f"off{nu}","wavenumber_cm1":nu,"kind":"baseline", "sample":stream([0,1],[1,1.01])})
        blocks.append({"block_id":f"on{nu}","wavenumber_cm1":nu,"delay_s":1e-4,"kind":"pumped", "sample":stream([0,1],[.9,.91]),"flags":["clipping"] if nu==1944 else []})
    result = process_run({"mode":"single","native_blocks":blocks})
    assert result["maps"]["delta_absorbance"].shape == (1,3)
    assert np.isnan(result["maps"]["delta_absorbance"][0,1])
    assert result["coverage"]["missing_points"] == 1
    assert len(result["points"]) == 6


def test_us_processing_and_fitting_cancellation():
    def cancelled(): raise InterruptedError("Acquisition stopped")
    with pytest.raises(InterruptedError):
        process_run({"native_blocks":[{}]},check_cancelled=cancelled)
    with pytest.raises(InterruptedError):
        fit_recovery(np.arange(10.),np.ones(10),check_cancelled=cancelled)


def test_us_filter_convolution_matches_independent_analytic_first_order():
    kernel = ResponseKernel(hf2_order=1,hf2_time_constant_s=10e-6,
                            sample_rate_sps=1e12,integration_aperture_s=1e-12,jitter_s=0)
    t = np.geomspace(.1e-6,1e-3,100)
    tau = 185e-6
    expected = tau/(tau-10e-6)*(np.exp(-t/tau)-np.exp(-t/10e-6))
    np.testing.assert_allclose(kernel.recovery(t,tau),expected,rtol=1e-7,atol=1e-9)
    expected_equal = t/10e-6*np.exp(-t/10e-6)
    np.testing.assert_allclose(kernel.recovery(t,10e-6),expected_equal,atol=1e-9)


def test_us_log_is_applied_after_intensity_filtering():
    kernel = ResponseKernel(hf2_order=3,hf2_time_constant_s=10e-6,
                            sample_rate_sps=1e12,integration_aperture_s=1e-12,jitter_s=0)
    t = np.array([50e-6,100e-6,250e-6,1e-3])
    lag = np.linspace(0,600e-6,60001)
    impulse = lag**2*np.exp(-lag/10e-6)/(2*(10e-6)**3)
    expected=[]
    for time in t:
        age=time-lag
        delta=np.where(age>=0,-.2*np.exp(-np.maximum(age,0)/185e-6),0)
        expected.append(-np.log10(np.trapezoid(10**(-delta)*impulse,lag)))
    np.testing.assert_allclose(kernel.absorbance(t,[-.2],[185e-6]),expected,atol=3e-5)


def test_us_native_aperture_matches_exact_discrete_sample_average():
    t=np.array([30e-6,70e-6,150e-6,500e-6])
    rows=((-3e-6,2e-6),(-1e-6,4e-6),(-5e-6,0.,3e-6),(-2e-6,1e-6))
    instantaneous=ResponseKernel(hf2_order=2,hf2_time_constant_s=8e-6,
                                sample_rate_sps=1e12,integration_aperture_s=1e-12)
    sampled=replace(instantaneous,native_aperture_offsets_s=rows)
    expected=[]
    for time,offsets in zip(t,rows):
        point_absorbance=instantaneous.absorbance(time+np.array(offsets),[-.1],[200e-6])
        expected.append(-np.log10(np.mean(10**(-point_absorbance))))
    np.testing.assert_allclose(sampled.absorbance(t,[-.1],[200e-6]),expected,atol=1e-8)


def test_us_incremental_retention_reuses_unchanged_arrays_but_preserves_edits(tmp_path):
    record={"mode":"single","native_blocks":[{"x":np.array([1.,2.]),"gain":np.float64(.5)}]}
    first=save_run(tmp_path,record)
    before=len(list(tmp_path.glob("native-*.npy")))
    save_run(tmp_path,record)
    assert len(list(tmp_path.glob("native-*.npy")))==before
    record["native_blocks"][0]["x"][0]=3.
    save_run(tmp_path,record)
    assert len(list(tmp_path.glob("native-*.npy")))==before+1
    assert load_run(first)["native_blocks"][0]["x"][0]==1.
    assert load_run(tmp_path)["native_blocks"][0]["x"][0]==3.


def test_us_wholly_missing_planned_coordinates_remain_coverage_gaps():
    from control_app.measurement_modules.microsecond_stroboscopy.settings import default_settings
    settings=default_settings().to_dict()
    result=process_run({"mode":"single","kind":"run","settings":settings,"native_blocks":[]})
    assert result["maps"]["delta_absorbance"].shape==(10,5)
    assert result["coverage"]["missing_points"]==50
    assert np.isnan(result["maps"]["delta_absorbance"]).all()
    assert all("taus_s" not in k["fit"] for k in result["kinetics"] if "area" in k)


def test_us_matched_aperture_weights_and_dark_correction_preserve_native():
    s=stream([0.,1e-6,2e-6,3e-6],[1.,1.,1.,1.])
    r=stream([0.,2e-6,3e-6],[1.,1.,1.])
    record={"mode":"dual","settings":{"response":{"sample_rate_sps":1e6,"reference_rate_sps":1e6}},
            "qualification":{"normalization":{"dark_offsets":{"sample":{"offset":.1,"standard_error":.001,"record_id":"dark"}}}},
            "native_blocks":[{"block_id":"one","kind":"pumped","wavenumber_cm1":1944.,
                "sample":s,"reference":r,"delay_s":1.5e-6,"optical_origin_s":0.}]}
    point=process_run(record)["points"][0]
    np.testing.assert_array_equal(point["valid_sample_indices"],[0,2,3])
    assert point["delay_s"]==pytest.approx(5e-6/3)
    assert len(point["native_aperture_offsets_s"])==3
    assert point["sample_reference_ratio"]==pytest.approx(.9)
    assert point["raw_sample_x"] == 1.
    np.testing.assert_array_equal(s["x"],np.ones(4))


def test_us_unequal_reference_filter_requires_measured_transfer_record():
    record={"mode":"dual","settings":{"spectral_points":[{"wavenumber_cm1":1944.}],
             "response":{"reference_order":3,"qualified":True}},"native_blocks":[]}
    result=process_run(record)
    assert result["kinetics"][0]["fit"]["disposition"]=="unresolvable"
    assert "Unequal" in result["kinetics"][0]["fit"]["reason"]


def test_us_order_drift_control_and_local_area_gaps():
    blocks = []
    for i, val in enumerate([1.,1.1,1.2]):
        blocks.append({"block_id":str(i),"wavenumber_cm1":1944.,"kind":"baseline",
                       "sample":stream([0,1],[val-.0001,val+.0001])})
    blocks.append({"block_id":"blocked","wavenumber_cm1":1944.,"kind":"pump_blocked",
                   "sample":stream([0,1],[.7999,.8001])})
    out = process_run({"mode":"single","native_blocks":blocks})
    assert out["diagnostics"][0]["kind"] == "baseline_order_drift"
    assert out["diagnostics"][0]["flagged"]
    assert out["diagnostics"][1]["kind"] == "pump_blocked_control"
    assert out["diagnostics"][1]["flagged"]


def test_us_uncalibrated_electrical_delay_preserves_relative_measurement_and_limits_fit():
    baseline = {"block_id": "baseline", "wavenumber_cm1": 1944., "kind": "baseline",
                "sample": stream([0., 1e-6], [1., 1.001])}
    pumped = {"block_id": "pumped", "wavenumber_cm1": 1944., "kind": "pumped",
              "sample": stream([100e-6, 101e-6], [.9, .901]), "delay_s": 100e-6,
              "electrical_origin_s": 0., "flags": ["unresolved_time_zero"]}
    result = process_run({"mode": "single", "native_blocks": [baseline, pumped],
                          "settings": {"response": {"qualified": True}}})
    point = result["points"][1]
    assert point["valid"] and np.isfinite(point["delta_absorbance"])
    assert point["time_origin"] == "electrical"
    assert point["delay_s"] == pytest.approx(100.5e-6)
    assert len(point["native_aperture_offsets_s"]) == 2
    assert result["kinetics"][0]["fit"]["disposition"] == "unresolvable"
    assert "uncalibrated" in result["kinetics"][0]["fit"]["reason"]
    assert not result["optical_arrival_calibrated"]


def test_us_negative_quadratures_remain_available_without_absorbance_repair():
    result = process_run({"mode": "single", "native_blocks": [{"block_id": "signed",
        "wavenumber_cm1": 1944., "kind": "pumped", "sample": stream([0., 1e-6], [-1., -2.])}]})
    point = result["points"][0]
    assert point["raw_sample_x"] == -1.5
    assert not point["valid"] and np.isnan(point["delta_absorbance"])


def test_us_own_initial_baseline_excludes_old_preliminary_and_nonrecovery_from_q0():
    blocks = [{"block_id": kind, "wavenumber_cm1": 1944., "kind": kind,
               "sample": stream([0., 1e-6], [value, value]), "flags": flags}
              for kind, value, flags in (("baseline", 1., []), ("reset", .8, ["reset_nonrecovery"]),
                                         ("pumped", .9, ["reset_nonrecovery"]))]
    result = process_run({"mode": "single", "native_blocks": blocks,
        "preliminary": {"processing": {"points": [{"wavenumber_cm1": 1944., "kind": "preliminary",
            "valid": True, "value": 2., "standard_error": .01, "flags": []}]}}})
    pumped = result["points"][-1]
    assert pumped["q0"] == 1.
    assert pumped["delta_absorbance"] == pytest.approx(-np.log10(.9))
    assert result["kinetics"][0]["fit"]["disposition"] == "unresolvable"


def test_us_sparse_aperture_remains_raw_and_is_masked_in_reconstruction():
    result = process_run({"mode": "single", "native_blocks": [{"block_id": "sparse",
        "wavenumber_cm1": 1944., "kind": "pumped", "sample": stream([0.], [1.]),
        "flags": ["insufficient_aperture_support"]}]})
    point = result["points"][0]
    assert point["raw_sample_x"] == 1.
    assert not point["valid"] and np.isnan(point["delta_absorbance"])
    assert result["coverage"]["missing_points"] == 1
