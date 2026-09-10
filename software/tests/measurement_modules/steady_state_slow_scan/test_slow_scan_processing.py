"""Known-truth spectroscopy on native uneven/reverse/missing support, no hardware."""
from dataclasses import replace

import numpy as np
import pytest

from control_app.measurement_modules.steady_state_slow_scan.processing import (
    AxisCorrection, FitSettings, NativeSweep, ProcessedSpectrum, SpectralControl,
    align_detector_streams, assess_sweeps, compare_states, fit_model_alternatives,
    fit_spectrum, match_support, process_sweep,
)


def native(mode="dual", **kwargs):
    values = dict(sweep_id="sweep-1", mode=mode, condition_id="rt_hrp_co", segment_id="qcl-1",
        direction="forward", replicate=0, axis_cm1=np.array([1900., 1901., 1902., 1903.]),
        sample=np.array([8., 6., 4., 2.]), timestamps_s=np.array([0., 1., 2., 3.]),
        reference=np.full(4, 10.) if mode == "dual" else None, sample_variance=np.full(4, .04),
        reference_variance=np.full(4, .09), detector_covariance=np.full(4, .015),
        metadata={"configuration_id": "config-1", "compatibility": {"configuration_id": "config-1"}})
    values.update(kwargs)
    return NativeSweep(**values)


def control(kind, values, *, mode="dual", **kwargs):
    args = dict(control_id=kind + "-1", kind=kind, mode=mode, condition_id="rt_hrp_co",
        axis_cm1=np.array([1900., 1901., 1902., 1903.]), values=np.asarray(values),
        variance=np.full(4, .0001), metadata={"complete": True, "applicable": True,
        "calibration_id": "path-1", "compatibility": {"configuration_id": "config-1"}})
    args.update(kwargs)
    return SpectralControl(**args)


def test_dual_ratio_delta_and_calibrated_absorbance_preserve_covariance_and_native():
    sweep = native()
    original = sweep.sample.copy()
    q = process_sweep(sweep)
    expected = sweep.sample / sweep.reference
    expected_var = .04 / 10**2 + sweep.sample**2 * .09 / 10**4 - 2 * sweep.sample * .015 / 10**3
    np.testing.assert_allclose(q.signal, expected)
    np.testing.assert_allclose(q.variance, expected_var)
    assert q.quantity == "reference_normalized_ratio" and q.absorbance is None
    delta = process_sweep(sweep, q0=control("unpumped_q0", np.full(4, .8)))
    np.testing.assert_allclose(delta.delta_absorbance, -np.log10(expected / .8))
    np.testing.assert_allclose(delta.provenance["delta_absorbance_variance"], (expected_var / expected**2 + .0001/.8**2) / np.log(10)**2)
    assert delta.quantity == "reference_normalized_ratio" and delta.absorbance is None
    np.testing.assert_allclose(delta.signal, expected)
    absolute = process_sweep(sweep, path_balance=control("path_balance", np.full(4, .9)))
    np.testing.assert_allclose(absolute.absorbance, -np.log10(expected / .9))
    assert absolute.quantity == "calibrated_absorbance"
    np.testing.assert_array_equal(sweep.sample, original)
    with pytest.raises(ValueError):
        sweep.sample[0] = 42


def test_single_requires_complete_compatible_blank_and_preserves_condition():
    sweep = native("single")
    blank = control("blank", np.full(4, 10.), mode="single")
    result = process_sweep(sweep, blank=blank)
    assert result.quantity == "sequential_blank_absorbance"
    np.testing.assert_allclose(result.signal, -np.log10(sweep.sample/10))
    for incompatible, message in ((replace(blank, mode="dual"), "mode"),
                                  (replace(blank, condition_id="77k_hrp_co"), "condition"),
                                  (replace(blank, metadata={"complete": False}), "compatibility")):
        with pytest.raises(ValueError, match=message):
            process_sweep(sweep, blank=incompatible)
    with pytest.raises(ValueError, match="complete"):
        process_sweep(sweep, blank=replace(blank, metadata={**blank.metadata, "complete": False}))


def test_bad_reference_clipping_unlock_and_missing_uncertainty_are_not_hidden():
    sweep = native(reference=np.array([10., 0., -1., np.nan]), valid=np.array([True, True, False, True]),
                   flags=("detector_clipping", "reference_unlocked"), sample_variance=None)
    result = process_sweep(sweep)
    assert result.valid.tolist() == [True, False, False, False]
    assert np.isnan(result.signal[1:]).all() and np.isnan(result.variance).all()
    assert "detector_clipping" in result.flags and "reference_unlocked" in result.flags
    assert "uncertainty_inputs_incomplete" in result.flags
    with pytest.raises(ValueError, match="reference stream"):
        process_sweep(replace(sweep, reference=None))
    bad_covariance = process_sweep(native(detector_covariance=np.full(4, 100.)))
    assert not bad_covariance.valid.any()
    assert "invalid_detector_covariance" in bad_covariance.flags


def test_uneven_reverse_controls_never_silently_fill_missing_intervals():
    axis = np.array([9., 8.5, 8., 3., 2., 1.])
    points = np.array([1., 1.5, 2., 4., 7., 8.25, 9.])
    exact, _, support = match_support(points, axis, axis * 2)
    assert support.tolist() == [True, False, True, False, False, False, True]
    interpolated, _, support = match_support(points, axis, axis * 2, max_gap_cm1=1.)
    assert support.tolist() == [True, True, True, False, False, True, True]
    np.testing.assert_allclose(interpolated[support], points[support] * 2)
    blocked, _, support = match_support([1.5, 2., 2.5], [1., 2., 3.], [1., 2., 3.],
                                        source_valid=[True, False, True], max_gap_cm1=3.)
    assert not support.any() and np.isnan(blocked).all()
    assert not match_support([1], [], [])[2].any()
    assert not match_support([1], [1, 1], [2, 3])[2].any()


def test_alignment_has_no_reference_reuse_or_interpolated_observation():
    values, indices, support = align_detector_streams([0., .001, .1, .2], [0., .2], [1., 3.], tolerance_s=.002)
    assert indices.tolist() == [0, -1, -1, 1]
    assert support.tolist() == [True, False, False, True]
    assert np.isnan(values[1:3]).all()


def test_only_applicable_axis_correction_retains_original_values():
    sweep = native()
    correction = AxisCorrection("axis-v3", "config-1", 1899, 1905, offset_cm1=.13, uncertainty_cm1=.025)
    result = process_sweep(sweep, axis_correction=correction)
    np.testing.assert_allclose(result.axis_cm1, sweep.axis_cm1 + .13)
    np.testing.assert_array_equal(result.native.axis_cm1, [1900, 1901, 1902, 1903])
    assert result.provenance["axis_uncertainty_cm1"] == .025
    with pytest.raises(ValueError, match="not applicable"):
        process_sweep(sweep, axis_correction=replace(correction, configuration_id="other"))
    with pytest.raises(ValueError, match="outside"):
        process_sweep(sweep, axis_correction=replace(correction, upper_cm1=1902))


def test_measured_path_balance_uses_declared_calibration_scope_not_mutable_sample_fit_settings():
    sweep = native(metadata={"configuration_id": "config-1", "condition": {"matrix_id": "buffer-1"},
        "compatibility": {"configuration_id": "config-1", "settings": {"fit_peak_count": 2, "sample_id": "A"}}})
    balance = control("path_balance", np.ones(4), metadata={"configuration_id": "config-1",
        "calibration_id": "path-1", "applicable": True, "applicability": {"matrix_id": "buffer-1"}})
    result = process_sweep(sweep, path_balance=balance)
    assert result.quantity == "calibrated_absorbance"
    with pytest.raises(ValueError, match="matrix_id"):
        process_sweep(sweep, path_balance=replace(balance, metadata={**balance.metadata,
            "applicability": {"matrix_id": "different"}}))
    with pytest.raises(ValueError, match="configuration_id"):
        process_sweep(sweep, path_balance=replace(balance, metadata={**balance.metadata,
            "configuration_id": "different"}))


def synthetic(*, shift=0., reverse=False, gap=True, seed=11, fringed=True):
    rng = np.random.default_rng(seed)
    x = np.linspace(1898, 1914, 500) + rng.uniform(-.006, .006, 500)
    truth = ((.31, 1904.2 + shift, .72), (.23, 1905.65 + shift, .9))
    baseline = .012 + .0018 * (x - 1906)
    if fringed:
        baseline += .008 * np.sin(2 * np.pi * (x - 1906) / 3.7) + .004 * np.cos(2 * np.pi * (x - 1906) / 3.7)
    y = baseline.copy()
    for height, center, width in truth:
        y += height * np.exp(-.5*((x-center)/width)**2)
    y += rng.normal(0, .00065, len(x))
    valid = ~((x > 1909.2) & (x < 1910.)) if gap else np.ones(len(x), bool)
    if reverse:
        x, y, valid = x[::-1], y[::-1], valid[::-1]
    raw = native("single", axis_cm1=x, sample=y, timestamps_s=np.arange(len(x), dtype=np.uint64),
        condition_id="77k_hrp_co" if shift else "rt_hrp_co", direction="reverse" if reverse else "forward",
        reference=None, sample_variance=None, reference_variance=None, detector_covariance=None, valid=valid)
    spectrum = ProcessedSpectrum(raw, x, np.where(valid, y, np.nan), np.full(len(x), .00065**2), valid,
                                 "sequential_blank_absorbance", provenance={"axis_uncertainty_cm1": .015,
                                 "axis_calibration_id": "axis-v3"})
    return spectrum, truth


@pytest.mark.parametrize("shift,reverse", [(0., False), (1.1, True)])
def test_known_truth_overlapping_tilted_fringed_shifted_peaks_and_covariance(shift, reverse):
    spectrum, truth = synthetic(shift=shift, reverse=reverse)
    result = fit_spectrum(spectrum, FitSettings(peak_count=2, fringe_periods_cm1=(3.7,)))
    for peak, (height, center, width) in zip(result.peaks, truth):
        assert abs(peak.center_cm1-center) < .04
        assert abs(peak.width_fwhm_cm1-width*2*np.sqrt(2*np.log(2))) < .06
        assert abs(peak.height-height) < .008
        assert abs(peak.integrated_area-height*width*np.sqrt(2*np.pi)) < .03
        assert peak.center_uncertainty_cm1 >= .015
        assert peak.area_uncertainty > 0
    assert np.isnan(result.fitted[~spectrum.valid]).all()
    assert np.isnan(result.residuals[~spectrum.valid]).all()
    assert result.residual_rms < .0008
    assert abs(result.covariance[5, 8]) > 0  # overlapping center correlation retained
    assert result.provenance["condition_id"] == spectrum.native.condition_id
    assert "fit_parameters_not_identifiable" not in result.flags
    assert "fit_not_converged" not in result.flags


def test_prospective_baseline_and_lineshape_alternatives_retain_residuals():
    spectrum, _ = synthetic()
    models = fit_model_alternatives(spectrum, (
        FitSettings(2, fringe_periods_cm1=(3.7,)),
        FitSettings(2, baseline_degree=1),
        FitSettings(2, line_shape="lorentzian", fringe_periods_cm1=(3.7,)),
    ))
    assert len(models) == 3
    assert models[0].settings.line_shape == "gaussian" and models[0].settings.fringe_periods_cm1 == (3.7,)
    assert models[0].aicc < models[1].aicc
    assert all(model.residuals.shape == spectrum.signal.shape for model in models)


def test_reference_normalized_dips_are_not_mislabeled_as_absorbance_peaks():
    spectrum, _ = synthetic(fringed=False, gap=False)
    ratio = replace(spectrum, signal=1 - spectrum.signal, quantity="reference_normalized_ratio")
    result = fit_spectrum(ratio, FitSettings(2))
    np.testing.assert_allclose([peak.center_cm1 for peak in result.peaks], [1904.2, 1905.65], atol=.04)
    assert all(peak.height < 0 and peak.integrated_area < 0 for peak in result.peaks)
    assert result.provenance["quantity"] == "reference_normalized_ratio"


def test_repeatability_direction_drift_assessed_without_pooling_and_cancellation():
    first = process_sweep(native())
    reverse = native(sweep_id="sweep-2", direction="reverse", replicate=1,
        axis_cm1=first.native.axis_cm1[::-1], sample=first.native.sample[::-1] + .1,
        timestamps_s=np.arange(4.) + 10)
    second = process_sweep(reverse)
    assessment = assess_sweeps([first, second], maximum_rms_difference=.02)
    assert not assessment["pooled"]
    row = assessment["comparisons"][0]
    assert row["direction_comparison"] and row["within_prespecified_tolerance"]
    assert row["apparent_drift_per_s"] is not None
    def stop():
        raise InterruptedError("Acquisition stopped")
    with pytest.raises(InterruptedError):
        process_sweep(native(), cancel_check=stop)
    spectrum, _ = synthetic()
    with pytest.raises(InterruptedError):
        fit_spectrum(spectrum, FitSettings(2), cancel_check=stop)
    fit = fit_spectrum(spectrum, FitSettings(2, fringe_periods_cm1=(3.7,)))
    comparison = compare_states(fit, fit, center_tolerance_cm1=.1, area_fraction_tolerance=.05)
    assert comparison["accepted"]
    assert compare_states(fit, fit)["accepted"] is None
