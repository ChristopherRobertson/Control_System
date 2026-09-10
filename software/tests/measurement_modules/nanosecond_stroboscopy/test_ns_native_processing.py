from pathlib import Path

import numpy as np
import pytest

from control_app.measurement_modules.nanosecond_stroboscopy.persistence import (
    NativeStore, load_run, save_plan, load_plan, compatibility_conflicts,
)
from control_app.measurement_modules.nanosecond_stroboscopy.processing import (
    align_detectors, reconstruct, spectral_observable, band_kinetics,
)


def event(value=1., reference=2., *, delay=10., wave=1950., **kwargs):
    return dict(event_id=f"event-{delay}-{wave}", wavenumber_cm1=wave,
                quantized_delay_ns=delay, requested_delay_ns=delay,
                observed_electrical_delay_ns=delay, calibrated_optical_delay_ns=delay,
                condition="pump_on", repetition=0,
                pump_evidence={"optical_pulse_count": 1, "source": "synthetic_known_truth"},
                sample={"timestamp_s": [1.], "value": [value], "variance": [0.0001]},
                reference={"timestamp_s": [1.], "value": [reference], "variance": [0.0004]},
                sample_reference_covariance=0.0001, **kwargs)


def test_ns_dual_delta_covariance_and_no_false_absolute_absorbance():
    baseline = [event(1., 2.)]
    measured = [event(0.8, 2.)]
    result = reconstruct(measured, baseline, mode="dual")
    assert result["delta_a"][0, 0] == pytest.approx(-np.log10(.8))
    assert result["ratio"][0, 0] == .4
    assert not result["absolute_available"]
    assert np.isnan(result["absolute_absorbance"]).all()
    obs = spectral_observable(measured[0], "dual")
    expected = .4**2 * (.0001/.8**2 + .0004/2**2 - 2*.0001/(.8*2))
    assert obs["variance"] == pytest.approx(expected)
    assert obs["covariance"] == .0001


def test_ns_single_requires_complete_blank_and_missing_support_stays_missing():
    measurements = [event(.8), event(.9, wave=1960., delay=20.)]
    baseline = [event(), event(wave=1960.)]
    missing = reconstruct(measurements, baseline, mode="single", blank=[event(2.)])
    assert missing["coverage"].tolist() == [[1, 0], [0, 0]]
    assert missing["absolute_absorbance"][0, 0] == pytest.approx(-np.log10(.4))
    assert np.isnan(band_kinetics(missing, 1950., 1960.)["area_delta_a_cm1"]).all()


@pytest.mark.parametrize("flag", ["clipped", "unlock", "missing_trigger", "count_mismatch", "reset_failed"])
def test_ns_invalid_events_retained_excluded(flag):
    record = event(.8, quality_flags=[flag])
    result = reconstruct([record], [event()], mode="dual")
    assert result["coverage"][0, 0] == 0
    assert flag in result["event_results"][0]["flags"]
    assert result["event_results"][0]["observable"]["sample"] == .8


def test_ns_bad_reference_and_unknown_optical_coordinate_cannot_be_kinetics():
    record = event(.8, reference=0.)
    unknown = event(.8, delay=20.)
    unknown["calibrated_optical_delay_ns"] = None
    result = reconstruct([record, unknown], [event()], mode="dual")
    assert result["coverage"].sum() == 0
    assert result["event_results"][0]["observable"]["flags"] == ["unsupported_reference"]
    assert "optical_delay_unresolved" in result["event_results"][1]["flags"]


def test_ns_alignment_never_matches_indices_or_interpolates():
    sample = {"timestamp_s": [1., 2., 3.], "value": [5., 6., 7.]}
    reference = {"timestamp_s": [1.1, 3.1], "value": [2., 4.], "group_delay_s": .1}
    aligned = align_detectors(sample, reference, tolerance_s=1e-12)
    assert aligned["sample_indices"] == [0, 2]
    assert aligned["reference_indices"] == [0, 1]
    assert aligned["missing_sample_indices"] == [1]
    ambiguous = align_detectors(sample, {"timestamp_s": [1., 1.], "value": [2., 3.]})
    assert ambiguous["sample_indices"] == []
    duplicate_sample = align_detectors({"timestamp_s": [1., 1.], "value": [2., 3.]},
                                      {"timestamp_s": [1.], "value": [4.]})
    assert duplicate_sample["sample_indices"] == []


def test_ns_pumped_native_event_cannot_be_relabeled_as_unpumped_q0():
    from control_app.measurement_modules.nanosecond_stroboscopy.settings import Settings, KERNEL_ID
    from control_app.measurement_modules.nanosecond_stroboscopy.processing import validate_native_baseline
    settings = Settings(mode="dual")
    wrong = event(kernel_id=KERNEL_ID)
    record = dict(experiment_id="nanosecond_stroboscopy", mode="dual", kind="preliminary", status="completed", settings=settings.to_dict(), events=[wrong])
    assert any("pumped event" in error for error in validate_native_baseline(record, settings))


def test_ns_baseline_uncertainty_does_not_average_down_with_technical_repetitions():
    baseline = event()
    baseline["sample"]["variance"] = [1e-2]
    one = reconstruct([event(.8)], [baseline], mode="dual")
    many = reconstruct([event(.8)]*100, [baseline], mode="dual")
    assert many["uncertainty"][0, 0] >= many["baseline_uncertainty"][0, 0]
    assert one["baseline_uncertainty"][0, 0] == many["baseline_uncertainty"][0, 0]


def test_ns_cancellation_during_processing():
    def stop():
        raise InterruptedError("Acquisition stopped")
    with pytest.raises(InterruptedError):
        reconstruct([event()], [event()], mode="dual", cancel=stop)


def test_ns_controls_reconstructed_separately_from_pumped_signal():
    control = event(1., delay=10.)
    control.update(condition="pump_blocked", pump_evidence={"optical_pulse_count": 0})
    result = reconstruct([event(.8), control], [event()], mode="dual")
    assert result["controls"]["pump_blocked"]["delta_a"][0, 0] == pytest.approx(0.)
    assert result["coverage"][0, 0] == 1
    assert result["controls"]["pump_blocked"]["coverage"][0, 0] == 1


def test_ns_population_comparison_consumes_only_standalone_selected_windows():
    from control_app.measurement_modules.nanosecond_stroboscopy.settings import Settings
    from control_app.measurement_modules.nanosecond_stroboscopy.simulation import convolved_response
    from control_app.measurement_modules.nanosecond_stroboscopy.processing import population_kinetics
    settings = Settings()
    delay = np.array(settings.delays_ns)
    kernel = settings.kernel()
    result = dict(wavenumbers_cm1=[1930., 1945.], delays_ns=delay,
                  optical_delay_ns=np.array([delay, delay]),
                  delta_a=np.array([-.01*convolved_response(delay, 200., kernel), -.008*convolved_response(delay, 650., kernel)]),
                  uncertainty=np.full((2, len(delay)), .00003))
    record = dict(schema_version=1, record_kind="sample_spectral_selection", disposition="accepted",
                  selection_id="sample-selection-1", sample_id="sample-1", producer_instance_id="nanosecond_stroboscopy:single",
                  source=dict(producer_run_id="source-run", native_path="sample-record.json", created_utc="2026-09-09T00:00:00+00:00", software_version="1"),
                  condition_id="condition-1", condition={"profile_id": "RT-HRP-G"},
                  accepted_by="synthetic test reviewer", accepted_utc="2026-09-09T00:00:00+00:00",
                  windows=[dict(lower_cm1=1929., upper_cm1=1931., center_cm1=1930., label="CO-1"),
                           dict(lower_cm1=1944., upper_cm1=1946., center_cm1=1945., label="CO-2")])
    analysis = population_kinetics(result, record, kernel)
    assert analysis["point_comparison"]["outcome"] == "distinct_supported"
    assert [p["label"] for p in analysis["populations"]] == ["CO-1", "CO-2"]
    assert np.isnan(analysis["populations"][0]["band"]["area_delta_a_cm1"]).all()


def test_ns_fully_retained_filter_history_is_unresolved_not_a_fit_crash():
    from control_app.measurement_modules.nanosecond_stroboscopy.settings import Settings
    from control_app.measurement_modules.nanosecond_stroboscopy.simulation import simulate_trace, identify_lifetime
    settings = Settings()
    kernel = {**settings.kernel(), "filter_memory_fraction": 1.0}
    trace = simulate_trace(settings.delays_ns, 250., -.01, kernel, noise_sd=.0001, seed=17)
    fit = identify_lifetime(trace["delay_ns"], trace["delta_a"], trace["uncertainty"], kernel)
    assert fit["outcome"] == "prompt_unresolved_bound"
    assert fit["lifetime_ns"] is None


def test_ns_native_roundtrip_exact_dtype_bytes_nonfinite_and_uint64(tmp_path):
    values = np.array([0., -0., np.inf, -np.inf, np.nan], dtype="<f8")
    ticks = np.array([2**63+1, 2**64-1], dtype="<u8")
    record = event()
    record["native_device_data"] = dict(values=values, ticks=ticks, scalar=np.uint64(2**63+1), missing=float("nan"))
    store = NativeStore(tmp_path / "run", mode="dual", settings={"mode": "dual"})
    store.append_event(record)
    store.finish("cancelled", restoration={"safe_verified": True})
    loaded = load_run(store.path, expected_mode="dual")
    native = loaded["events"][0]["native_device_data"]
    assert native["values"].dtype == values.dtype
    assert native["values"].tobytes() == values.tobytes()
    assert native["ticks"].tobytes() == ticks.tobytes()
    assert type(native["scalar"]) is np.uint64
    assert np.isnan(native["missing"])
    assert loaded["status"] == "cancelled"
    with pytest.raises(ValueError, match="mode"):
        load_run(store.path, expected_mode="single")
    with pytest.raises(FileExistsError):
        store.finish("completed")


def test_ns_plan_identity_compatibility_and_torn_journal(tmp_path):
    settings = {"mode": "single", "sample_id": "sample-a", "delay_ns": [0, 20]}
    save_plan(tmp_path / "plan.json", settings, mode="single")
    assert load_plan(tmp_path / "plan.json", expected_mode="single") == settings
    assert "sample_id" in compatibility_conflicts(settings, dict(settings, sample_id="sample-b"))[0]
    store = NativeStore(tmp_path / "run", mode="single", settings=settings)
    store.append_event(event())
    with store.events.open("a") as stream:
        stream.write('{"event_id":')
    loaded = load_run(store.path)
    assert len(loaded["events"]) == 1 and loaded["journal_errors"]
    assert loaded["status"] == "interrupted"


def test_ns_storage_failure_is_reported_without_overwriting_existing_record(tmp_path, monkeypatch):
    store = NativeStore(tmp_path / "run", mode="single", settings={})
    store.save_record("restoration", {"safe": False})
    with pytest.raises(FileExistsError):
        store.save_record("restoration", {"safe": True})
    import control_app.measurement_modules.nanosecond_stroboscopy.persistence as module
    def failed(_):
        raise OSError("disk failure")
    monkeypatch.setattr(module.os, "fsync", failed)
    with pytest.raises(OSError, match="disk failure"):
        store.append_event(event())
