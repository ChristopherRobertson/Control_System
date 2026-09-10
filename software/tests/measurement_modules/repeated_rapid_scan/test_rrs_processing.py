from dataclasses import replace

import numpy as np
import pytest

from control_app.measurement_modules.repeated_rapid_scan.data import (
    ClockCorrection, NativeKernel, NativeMovie, NativeScan, NativeStream,
    PumpObservation, ScanTrajectory, SpectralBaseline, SpectrumSupport,
)
from control_app.measurement_modules.repeated_rapid_scan.processing import (
    ProcessingCancelled, assess_recovery, assess_stationarity, build_baseline,
    combine_baselines, fit_apparent_recovery, fit_recovery_model,
    native_kernel_for_movie, reconstruct_movie,
)


def scan(index=0, *, times=None, values=None, reference=None, flags=None, direction="forward", variance=None):
    times = np.linspace(index*.2, index*.2+.18, 10) if times is None else np.asarray(times)
    axis = np.linspace(0, 1, len(times))
    if direction == "reverse":
        axis = axis[::-1]
    values = np.ones(len(times)) if values is None else np.asarray(values)
    sample = NativeStream(times, values, variance=variance, flags=flags or {})
    ref = None if reference is None else NativeStream(times, reference, variance=np.full(len(times), .04))
    return NativeScan(index, sample, ScanTrajectory(times, axis, "axis-1", direction), ref)


def movie(scans, *, mode="single", pumps=None, metadata=None):
    return NativeMovie("m-1", .037, tuple(scans),
                       (PumpObservation(0, clock_id="hf2li", basis="optical_arrival"),) if pumps is None else tuple(pumps),
                       mode,"condition-1",metadata=metadata or {})


def baseline(mode="single", value=1, kind=None, direction="forward"):
    axis = np.linspace(0,1,10)
    return SpectralBaseline("b-1", mode, "condition-1",
                            (SpectrumSupport(direction,axis,np.full(10,value),np.zeros(10)),),
                            kind or ("q0" if mode=="dual" else "single_baseline"), accepted=True)


def test_rrs_large_native_ticks_jitter_and_gaps_survive_reconstruction():
    origin = 2**60
    native = np.array([origin, origin+10, origin+21, origin+50], dtype=np.uint64)
    stream = NativeStream(native, np.ones(4), timestamp_unit_s=1e-9,
                          timestamp_origin=origin, metadata={"expected_sample_interval_s":1e-8})
    trajectory = ScanTrajectory(native, np.arange(4.), "cal", timestamp_unit_s=1e-9,timestamp_origin=origin)
    pump = PumpObservation(origin+5, clock_id="timing", timestamp_unit_s=1e-9,timestamp_origin=origin)
    item = NativeMovie("ticks",99,(NativeScan(4,stream,trajectory),),(pump,),"single","c",
                       clock_corrections=(ClockCorrection("hf2li",offset_s=1_700_000_000),
                                          ClockCorrection("timing",offset_s=1_700_000_000)))
    result = reconstruct_movie(item)
    np.testing.assert_allclose(result.points[0].time_s, np.array([-5,5,16,45])*1e-9,atol=1e-21)
    np.testing.assert_array_equal(stream.timestamps_s,native)
    assert len(result.points[0].gaps_s)==1
    assert result.points[0].scan_index == 4
    assert result.provenance["requested_phase_offset_s"] == 99
    assert result.time_zero_basis == "electrical_sync"


def test_rrs_dual_q_q0_and_b_are_distinct_with_covariance():
    item = scan(values=np.full(10,4.),reference=np.full(10,2.),variance=np.full(10,.09))
    item = replace(item,sample_reference_covariance=np.full(10,.03))
    result = reconstruct_movie(movie([item],mode="dual"), baseline("dual",4))
    p=result.points[0]
    np.testing.assert_allclose(p.normalized_signal,2)
    np.testing.assert_allclose(p.delta_absorbance,-np.log10(.5))
    np.testing.assert_allclose(p.variance_normalized,.09/4+16*.04/16-2*4*.03/8)
    assert np.all(np.isnan(p.absolute_absorbance))
    absolute=reconstruct_movie(movie([item],mode="dual"),baseline("dual",4),baseline("dual",8,kind="background"))
    np.testing.assert_allclose(absolute.points[0].absolute_absorbance,-np.log10(.25))


def test_rrs_missing_reference_and_clipped_unlock_are_retained():
    item=scan(values=np.arange(1,11.),reference=np.ones(10),flags={"clipped":np.arange(10)==3})
    reference=replace(item.reference,timestamps_s=np.delete(item.reference.timestamps_s,4),
                      values=np.delete(item.reference.values,4),variance=np.full(9,.04),
                      flags={"unlocked":np.arange(9)==6})
    item=replace(item,reference=reference)
    result=reconstruct_movie(movie([item],mode="dual"),baseline("dual"))
    p=result.points[0]
    assert len(p.time_s)==10
    assert not p.valid[3] and not p.valid[4] and not p.valid[7]
    assert p.reference_indices[4] == -1
    assert item.sample.values[3]==4
    assert p.flags["clipped"][3] and p.flags["missing_reference"][4]


@pytest.mark.parametrize("reference",[0.,-1.,float("nan")])
def test_rrs_bad_reference_never_produces_absorbance(reference):
    result=reconstruct_movie(movie([scan(reference=np.full(10,reference))],mode="dual"),baseline("dual"))
    assert not result.points[0].valid.any()
    assert np.isnan(result.points[0].delta_absorbance).all()


def test_rrs_cross_clock_alignment_and_observed_pump_count_are_required():
    item=movie([scan()],pumps=[PumpObservation(0,clock_id="other")])
    assert reconstruct_movie(item).status=="rejected"
    for pumps in ([],[PumpObservation(0),PumpObservation(1)],[PumpObservation(0,independently_observed=False)]):
        result=reconstruct_movie(movie([scan()],pumps=pumps))
        assert result.status=="rejected" and not result.points[0].valid.any()


def test_rrs_baseline_kind_mode_condition_and_review_compatibility():
    for invalid in (replace(baseline(),accepted=False),replace(baseline(),condition_id="wrong"),
                    replace(baseline(),mode="dual"),replace(baseline(),kind="background"),
                    replace(baseline(),complete=False)):
        with pytest.raises(ValueError): reconstruct_movie(movie([scan()]),invalid)
    result=reconstruct_movie(movie([scan(direction="reverse")]),baseline())
    assert not result.points[0].valid.any()
    assert result.points[0].direction=="reverse"


def test_rrs_pre_pump_baseline_excludes_pumped_data():
    unpumped=scan(times=np.linspace(-1,-.82,10),values=np.full(10,2))
    pumped=scan(times=np.linspace(0,.18,10),values=np.ones(10))
    result=build_baseline(movie([unpumped,pumped]),accepted=True)
    np.testing.assert_allclose(result.spectra[0].values,2)
    assert result.accepted and result.complete
    partial=replace(movie([unpumped,pumped]),status="interrupted")
    assert not build_baseline(partial).complete


def test_rrs_known_transient_changes_during_scans_and_native_kernel_fit():
    tau=.37
    kernel=NativeKernel(np.array([0,.011,.03]),np.array([.3,.4,.3]),"measured-filter-1")
    scans=[]
    expected=[]
    for index in range(14):
        times=np.linspace(index*.2,index*.2+.18,10)
        elapsed=times[:,None]-kernel.delays_s[None,:]
        transient=.08*np.sum(np.where(elapsed>=0,np.exp(-np.maximum(elapsed,0)/tau),0)*kernel.weights,axis=1)+.002
        expected.append(transient)
        scans.append(scan(index,times=times,values=10**(-transient),variance=np.full(10,1e-10)))
    result=reconstruct_movie(movie(scans),baseline())
    for p,truth in zip(result.points,expected):
        np.testing.assert_allclose(p.delta_absorbance,truth,atol=1e-14)
    fit=fit_apparent_recovery(result.points,kernel,tau_bounds_s=(.1,1),grid_size=800)
    assert abs(fit.apparent_tau_s-tau)<.002
    assert abs(fit.amplitude-.08)<.0003
    assert "no molecular mechanism" in fit.claim
    assert fit.predicted.shape==(140,)


def state_scan(index, amplitude=.1, background=1.):
    nu=np.linspace(0,1,101)
    values=background*10**(-amplitude*np.exp(-((nu-.5)/.1)**2))
    times=nu*.1+index*.2
    return NativeScan(index,NativeStream(times,values),ScanTrajectory(times,nu,"cal"))


def test_rrs_stationarity_and_reset_require_band_and_offband_recovery():
    bands=((.3,.7),)
    offbands=((0,.2),(.8,1.))
    before=[state_scan(i) for i in range(3)]
    assert assess_stationarity(before,bands,offbands).accepted
    assert not assess_stationarity(before[:2],bands,offbands).accepted
    assert not assess_stationarity([state_scan(i,.1+i*.01) for i in range(3)],bands,offbands).accepted
    recovered=[state_scan(i+10) for i in range(3)]
    assert assess_recovery(before,recovered,bands,offbands).accepted
    for after in ([state_scan(i+10,.07) for i in range(3)],
                  [state_scan(i+10,.1,background=.95) for i in range(3)]):
        assessment=assess_recovery(before,after,bands,offbands)
        assert not assessment.accepted
        assert not assessment.metrics["next_equivalent_pump_permitted"]
        assert assessment.metrics["outcome"]=="duration_limited_incomplete_recovery"


def test_rrs_band_area_retains_time_span_and_missing_support():
    item=scan(values=np.full(10,.8),flags={"unlocked":np.arange(10)==5})
    result=reconstruct_movie(movie([item]),baseline(),band_windows_cm1=((0,1),))
    area=result.band_kinetics[0]
    assert area.earliest_time_s==0
    assert area.latest_time_s==.18
    assert area.coverage_fraction<1
    assert not area.valid


def test_rrs_analysis_cancellation_is_normal_and_keeps_native():
    item=movie([scan()])
    original=item.scans[0].sample.values.copy()
    with pytest.raises(ProcessingCancelled,match="Acquisition stopped"):
        reconstruct_movie(item,cancelled=lambda:True)
    np.testing.assert_array_equal(item.scans[0].sample.values,original)


def test_rrs_baseline_repeat_average_does_not_overwrite_direction_or_hide_rejection():
    first=baseline(value=2)
    second=replace(baseline(value=4),record_id="b-2")
    reverse=replace(baseline(value=8,direction="reverse"),record_id="b-r")
    combined=combine_baselines([first,second,reverse],record_id="combined")
    by_direction={s.direction:s for s in combined.spectra}
    np.testing.assert_allclose(by_direction["forward"].values,3)
    np.testing.assert_allclose(by_direction["reverse"].values,8)
    unsupported=movie([scan(flags={"clipped":np.arange(10)==4})],pumps=[],metadata={"expected_pump_count":0})
    assert not build_baseline(unsupported,accepted=True).complete


def test_rrs_missing_detector_covariance_is_unknown_uncertainty():
    item=scan(values=np.full(10,4.),reference=np.full(10,2.),variance=np.full(10,.09))
    result=reconstruct_movie(movie([item],mode="dual"),baseline("dual",4))
    assert result.points[0].valid.all()
    assert np.isnan(result.points[0].variance_normalized).all()


def test_rrs_fit_model_uses_actual_scan_history_and_template_without_gap_extrapolation():
    initial=movie([scan(i) for i in range(12)])
    calibration={"measured":True,"calibration_id":"measured-response-1",
                 "response_basis":"optical_arrival","delays_s":[0.,.015,.035],"weights":[.2,.5,.3]}
    kernel=native_kernel_for_movie(initial,calibration)
    assert np.isnan(kernel.wavelength_offsets_cm1[0,1:]).all()
    axis=np.linspace(0,1,201)
    shape=np.exp(-((axis-.5)/.18)**2)
    tau=.34
    t=np.concatenate([s.sample.timestamps_s for s in initial.scans])
    nu=np.concatenate([s.trajectory.wavenumbers_cm1 for s in initial.scans])
    sampled_shape=np.interp(nu[:,None]+kernel.wavelength_offsets_cm1,axis,shape,left=np.nan,right=np.nan)
    elapsed=t[:,None]-kernel.delays_s
    response=.06*np.sum(sampled_shape*np.exp(-np.maximum(elapsed,0)/tau)*(elapsed>=0)*kernel.weights,axis=1)+.001
    response=np.nan_to_num(response,nan=0.)
    generated=[]
    for index,item in enumerate(initial.scans):
        values=10**(-response[index*10:(index+1)*10])
        generated.append(replace(item,sample=replace(item.sample,values=values,variance=np.full(10,1e-9))))
    native=replace(initial,scans=tuple(generated))
    reconstructed=reconstruct_movie(native,baseline())
    spec={"kernel":calibration,"spectral_template":{"record_id":"accepted-template-1",
          "description":"Known synthetic band template","wavenumbers_cm1":axis.tolist(),"values":shape.tolist()},
          "tau_bounds_s":[.1,1.],"grid_size":600}
    result=fit_recovery_model(native,reconstructed,spec)
    fit=result["fits_by_direction"]["forward"]
    assert abs(fit.apparent_tau_s-tau)<.003
    assert len(fit.valid_native_indices)<len(t)
    assert result["provenance"]["direction_pooling"]=="not_performed"
    assert any("filter history" in text for text in fit.warnings)
    with pytest.raises(ValueError,match="measured=true"):
        native_kernel_for_movie(native,{**calibration,"measured":False})
    with pytest.raises(ValueError,match="time basis"):
        native_kernel_for_movie(native,{**calibration,"response_basis":"electrical_sync"})
    with pytest.raises(ProcessingCancelled):
        fit_recovery_model(native,reconstructed,spec,cancelled=lambda:True)
