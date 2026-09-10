"""Synthetic simultaneous-detector alignment and reference-normalized spectra."""
from copy import deepcopy
from dataclasses import replace
import csv
import json

import numpy as np
import pytest
import yaml

from control_app.workflows.dual_detector_phase_scan import (
    DualDetectorPhaseScanSettings, build_dual_detector_phase_scan_plan,
)
from control_app.workflows.dual_detector_phase_scan_data import (
    ANALYSIS_VERSION, SCHEMA_VERSION, ChannelBalanceCalibration, DualScanStore,
    align_detector_spectrum, baseline_values, compatibility_conflicts,
    experiment_contract, load_channel_balance, load_dual_run, reconstruct_sequence,
    sample_reference_ratio, save_dual_reconstruction_csv, validate_baseline, validate_reconstruction,
)
from control_app.workflows.phase_scan_data import load_native, save_native


def plan():
    return build_dual_detector_phase_scan_plan(DualDetectorPhaseScanSettings(
        start_wavenumber_cm1=2000, stop_wavenumber_cm1=1998,
        scan_speed_cm1_s=1000, phase_delay_us=500))


def synthetic_spectrum(event=None, *, intensity=1., absorption=0., sample_delay=.0001,
                       reference_delay=.0002, reference_values=None):
    wn = np.array([2000., 1999., 1998.])
    relative = (event.phase_delay_us or 0.)*1e-6 if event else 0.
    age = relative+np.array([0., .001, .002])
    effective = 10.+age
    reference = intensity*np.array([2., 3., 4.])
    q0 = 10**(-(.1+(2000-wn)*.01))
    signal = reference*q0*10**(-absorption)
    return align_detector_spectrum(effective+sample_delay, signal, wn,
        effective+reference_delay, reference if reference_values is None else reference_values, wn,
        sample_filter_delay_s=sample_delay, reference_filter_delay_s=reference_delay,
        pump_time_s=10. if event and event.pump_enabled else None,
        metadata={"optical_valid": True, "wavenumber_basis": "measured",
                  "pump_time_basis": "electrical_sync", "record_id": "simulated/preliminary",
                  "acquisition_settings": experiment_contract(plan())})


def synthetic_result():
    requested = plan()
    baseline = synthetic_spectrum()
    records = []
    for index in range(requested.total_scans):
        event = requested.event_at(index)
        age = (event.phase_delay_us or 0.)*1e-6+np.array([0., .001, .002])
        records.append((event, synthetic_spectrum(event, intensity=1+.05*index,
                         absorption=20*age if event.pump_enabled else 0.)))
    return reconstruct_sequence(records, baseline, requested)


def calibration(requested=None):
    requested = requested or plan()
    contract = experiment_contract(requested)
    manifest = {"bundle_id": "SIMULATED-BALANCE", "schema_version": "1.0", "status": "PROMOTED",
        "kind": "dual_detector_channel_balance", "equivalent_optical_contents": True,
        "validation": {"status": "VALIDATED", "reviewer": "Simulation test reviewer"},
        "validity": {key: contract[key] for key in ("detector_assignments", "hf2li_selected")},
        "response_ratio_file": "response.npz"}
    return ChannelBalanceCalibration("SIMULATED-BALANCE", "simulated", manifest,
                                      np.array([1998., 1999., 2000.]), np.array([2., 2., 2.]))


def test_different_filter_delays_align_native_timestamps_before_ratio():
    spectrum = synthetic_spectrum(sample_delay=.0001, reference_delay=.0008)
    np.testing.assert_allclose(spectrum.sample_time_s, [10., 10.001, 10.002])
    np.testing.assert_allclose(sample_reference_ratio(spectrum), 10**(-np.array([.1, .11, .12])))
    assert not spectrum.metadata["alignment"]["invalid_reasons"].any()
    assert spectrum.metadata["alignment"]["reference_filter_delay_s"] == .0008


def test_alignment_matches_measured_wavelength_and_time_not_array_position():
    ref_t = np.arange(5)*.0005+10
    ref_wn = 2000-(ref_t-10)*1000
    sample_t = np.array([10.00025, 10.00075, 10.00125, 10.00175])
    sample_wn = 2000-(sample_t-10)*1000
    ref_r = 2+(ref_t-10)*1000
    sample_r = (2+(sample_t-10)*1000)*.4
    aligned = align_detector_spectrum(sample_t+.0001, sample_r, sample_wn,
        ref_t+.0002, ref_r, ref_wn, sample_filter_delay_s=.0001,
        reference_filter_delay_s=.0002,
        metadata={"optical_valid": True, "wavenumber_basis": "measured"})
    np.testing.assert_allclose(sample_reference_ratio(aligned), .4, atol=1e-12)
    assert len(aligned.sample_r) != len(ref_r)


def test_same_index_and_wavelength_but_different_measurement_time_is_missing():
    spectrum = synthetic_spectrum()
    timing = np.array([10., 10.001, 10.002])
    shifted = align_detector_spectrum(timing, spectrum.sample_r, spectrum.wavenumber_cm1,
        timing+.0001, np.array([2., 3., 4.]), spectrum.wavenumber_cm1,
        sample_filter_delay_s=0., reference_filter_delay_s=0.,
        metadata={"optical_valid": True, "wavenumber_basis": "measured"})
    assert np.isnan(sample_reference_ratio(shifted)).all()
    assert (shifted.metadata["alignment"]["invalid_reasons"] & 64).all()


@pytest.mark.parametrize("invalid,flag", [(np.nan, 4), (0., 8), (-1., 8), (np.inf, 4)])
def test_invalid_reference_remains_missing_with_reason(invalid, flag):
    spectrum = synthetic_spectrum(reference_values=np.array([2., invalid, 4.]))
    ratio = sample_reference_ratio(spectrum)
    assert np.isfinite(ratio[[0, 2]]).all() and np.isnan(ratio[1])
    assert spectrum.metadata["alignment"]["invalid_reasons"][1] & flag


def test_missing_reference_tick_gap_is_not_bridged():
    st = 10+np.arange(9)*.001
    rt = st[[0, 1, 2, 6, 7, 8]]
    spectrum = align_detector_spectrum(st, np.ones(9), 2000-(st-10)*1000,
        rt, np.ones(len(rt)), 2000-(rt-10)*1000,
        sample_filter_delay_s=0., reference_filter_delay_s=0.,
        metadata={"optical_valid": True, "wavenumber_basis": "measured"})
    assert np.isnan(sample_reference_ratio(spectrum)[3:6]).all()
    assert (spectrum.metadata["alignment"]["invalid_reasons"][3:6] & 32).all()


def test_unknown_measured_coordinate_cannot_be_removed_to_bridge_gap():
    st = np.array([10., 10.001, 10.002])
    spectrum = align_detector_spectrum(st, np.ones(3), np.array([2000., 1999., 1998.]),
        st, np.ones(3), np.array([2000., np.nan, 1998.]),
        sample_filter_delay_s=0., reference_filter_delay_s=0.,
        metadata={"optical_valid": True, "wavenumber_basis": "measured"})
    assert np.isnan(sample_reference_ratio(spectrum)[1])
    assert spectrum.metadata["alignment"]["invalid_reasons"][1] & 16


@pytest.mark.parametrize("sample,reference", [(1e308, 1e-308), (1e-308, 1e308)])
def test_numeric_ratio_out_of_range_is_missing_with_explicit_reason(sample, reference):
    spectrum = synthetic_spectrum()
    spectrum.sample_r[1] = sample
    spectrum.reference_r[1] = reference
    with np.errstate(all="raise"):
        result = baseline_values(spectrum)
    assert np.isnan(result["sample_reference_ratio"][1])
    assert result["invalid_reasons"][1] & 2048


def test_common_mode_change_cancels_and_delta_matches_preliminary_baseline():
    result = synthetic_result()
    assert "absorbance" not in result and "transmission" not in result
    assert result["absolute_absorbance_available"] is False
    expected = np.broadcast_to(result["time_s"][:, None]*20, result["delta_absorbance"].shape)
    np.testing.assert_allclose(result["delta_absorbance"], expected, atol=1e-11)
    assert result["baseline_record_id"] == "simulated/preliminary"
    assert result["baseline_matching"].startswith("separate_reviewed")
    np.testing.assert_allclose(result["baseline_sample_reference_ratio"], 10**(-np.array([.12, .11, .1])))
    assert result["sequence_unpumped_spectrum"] is not result["baseline_spectrum"]


def test_baseline_gaps_propagate_to_delta_without_invented_data():
    requested = plan()
    baseline = synthetic_spectrum(reference_values=np.array([2., np.nan, 4.]))
    records = [(requested.event_at(i), synthetic_spectrum(requested.event_at(i)))
               for i in range(requested.total_scans)]
    result = reconstruct_sequence(records, baseline, requested)
    assert np.isnan(result["delta_absorbance"][:, 1]).all()
    assert np.isfinite(result["sample_reference_ratio"][:, 1]).all()
    assert all(row["invalid_reasons"][1] & 128 for row in result["native_invalid_reasons"])


def test_alternating_missing_wavelength_support_does_not_widen_phase_gap():
    requested = plan()
    baseline = synthetic_spectrum()
    records = []
    for i in range(requested.total_scans):
        event = requested.event_at(i)
        spectrum = synthetic_spectrum(event)
        if event.pump_enabled and event.phase_index % 2:
            # Missing measured marker coverage at the end of alternate scans.
            spectrum.wavenumber_cm1 = spectrum.wavenumber_cm1[:2]
            spectrum.sample_time_s = spectrum.sample_time_s[:2]
            spectrum.sample_r = spectrum.sample_r[:2]
            spectrum.reference_r = spectrum.reference_r[:2]
            spectrum.metadata["alignment"]["invalid_reasons"] = spectrum.metadata["alignment"]["invalid_reasons"][:2]
        records.append((event, spectrum))
    result = reconstruct_sequence(records, baseline, requested)
    assert np.isnan(result["sample_reference_ratio"][:, 0]).any()
    assert np.isfinite(result["sample_reference_ratio"][:, 1:]).all()


def test_absolute_absorbance_requires_validated_promoted_equivalent_contents():
    spectrum = synthetic_spectrum()
    basic = baseline_values(spectrum)
    assert basic["display_mode"] == "sample_reference_ratio" and "absorbance" not in basic
    valid = calibration()
    values = baseline_values(spectrum, valid)
    np.testing.assert_allclose(values["absorbance"], np.array([.1, .11, .12])+np.log10(2.))
    assert values["display_mode"] == "absorbance"
    for key, value in (("status", "CANDIDATE"), ("equivalent_optical_contents", False)):
        manifest = deepcopy(valid.manifest)
        manifest[key] = value
        with pytest.raises(ValueError, match="validated promoted"):
            baseline_values(spectrum, replace(valid, manifest=manifest))
    incompatible = deepcopy(spectrum)
    incompatible.metadata["acquisition_settings"]["detector_assignments"]["reference"]["input"] = 0
    with pytest.raises(ValueError, match="detector_assignments"):
        baseline_values(incompatible, valid)
    incompatible.metadata.pop("acquisition_settings")
    with pytest.raises(ValueError, match="applicability"):
        baseline_values(incompatible, valid)


def test_promoted_calibration_loader_no_bundle_does_not_block_delta(tmp_path):
    (tmp_path/"registry.yaml").write_text("bundles: []\n")
    assert load_channel_balance(plan(), tmp_path) is None


def test_saved_calibrated_result_uses_acquisition_date_and_validates_scope():
    requested = plan()
    valid = calibration(requested)
    records = [(requested.event_at(i), synthetic_spectrum(requested.event_at(i)))
               for i in range(requested.total_scans)]
    result = reconstruct_sequence(records, synthetic_spectrum(), requested, calibration=valid)
    assert np.isfinite(result["absorbance"]).all()
    # A formerly valid calibration remains applicable to retained measurements.
    result["acquisition_utc"] = "2020-01-01T00:00:00+00:00"
    result["channel_balance_calibration"]["manifest"]["validity"]["valid_until_utc"] = "2020-02-01T00:00:00+00:00"
    validate_reconstruction(result)
    wrong = deepcopy(result)
    wrong["experiment_contract"]["detector_assignments"]["sample"]["input"] = 9
    with pytest.raises(ValueError, match="detector_assignments"):
        validate_reconstruction(wrong)
    wrong = deepcopy(result)
    wrong["absorbance"][0, 0] = np.inf
    with pytest.raises(ValueError, match="infinity"):
        validate_reconstruction(wrong)


def test_calibration_extra_applicability_is_checked_not_ignored():
    valid = calibration()
    manifest = deepcopy(valid.manifest)
    manifest["validity"]["settings"] = {"probe_repetition_rate_hz": 99.}
    with pytest.raises(ValueError, match="probe_repetition_rate_hz"):
        baseline_values(synthetic_spectrum(), replace(valid, manifest=manifest))
    manifest = deepcopy(valid.manifest)
    manifest["validity"]["unknown_required_optical_path"] = "different"
    with pytest.raises(ValueError, match="unsupported requirements"):
        baseline_values(synthetic_spectrum(), replace(valid, manifest=manifest))


def test_promoted_calibration_loader_checks_manifest_and_detector_scope(tmp_path):
    valid = calibration()
    directory = tmp_path/valid.bundle_id
    directory.mkdir()
    (directory/"manifest.yaml").write_text(yaml.safe_dump(valid.manifest))
    save_native(directory/"response.npz", {"wavenumber_cm1": valid.wavenumber_cm1,
                                         "response_ratio": valid.response_ratio})
    (tmp_path/"registry.yaml").write_text(yaml.safe_dump({"bundles": [
        {"bundle_id": valid.bundle_id, "status": "PROMOTED", "path": valid.bundle_id}]}))
    loaded = load_channel_balance(plan(), tmp_path)
    assert loaded.bundle_id == valid.bundle_id
    changed = replace(plan(), hf2_selection={**plan().hf2_selection, "rate_sps": 123.})
    assert load_channel_balance(changed, tmp_path) is None
    manifest = deepcopy(valid.manifest)
    manifest["validation"]["status"] = "PENDING"
    (directory/"manifest.yaml").write_text(yaml.safe_dump(manifest))
    assert load_channel_balance(plan(), tmp_path) is None


def test_compatibility_includes_roles_both_detectors_cadence_and_balance():
    original = plan()
    left = experiment_contract(original)
    for key in ("sample", "reference"):
        selection = deepcopy(original.hf2_selection)
        selection[key]["order"] = 2
        assert any(key in value for value in compatibility_conflicts(left, experiment_contract(replace(original, hf2_selection=selection))))
    assignments = deepcopy(original.detector_assignments)
    assignments["sample"]["input"] = 1
    assert compatibility_conflicts(left, experiment_contract(replace(original, detector_assignments=assignments)))
    assert compatibility_conflicts(left, experiment_contract(replace(original, channel_balance_calibration={"bundle_id": "another"})))
    same = replace(original, hf2_selection={**original.hf2_selection, "capability_source": "new read-only check"})
    assert not compatibility_conflicts(left, experiment_contract(same))


def test_native_reconstruction_roundtrip_exports_ratio_without_false_absolute(tmp_path):
    result = synthetic_result()
    store = DualScanStore(tmp_path, "run", plan())
    ticks = np.array([2**60, 2**60+1], np.uint64)
    store.save_block([], native={"partial_blocks": [{"timestamp": ticks}]})
    store.finish("ABORTED")
    raw = load_native(store.path/"raw"/"acquisition.npz")
    assert raw["schema_version"] == SCHEMA_VERSION
    np.testing.assert_array_equal(raw["native"]["partial_blocks"][0]["timestamp"], ticks)
    save_native(store.path/"processed"/"reconstruction.npz", result)
    restored = load_dual_run(store.path)
    np.testing.assert_equal(restored["delta_absorbance"], result["delta_absorbance"])
    export = tmp_path/"dual.csv"
    save_dual_reconstruction_csv(export, result)
    with export.open() as handle:
        header = next(csv.reader(handle))
    assert "sample_reference_ratio" in header and "delta_absorbance" in header
    assert "absorbance" not in header and "transmission" not in header
    manifest = json.loads((store.path/"run.json").read_text())
    assert manifest["detector_mode"] == "dual_detector"


def test_single_or_legacy_dataset_is_rejected(tmp_path):
    path = tmp_path/"single.npz"
    save_native(path, {"absorbance": np.ones((2, 2)), "wavenumber_cm1": [1., 2.], "time_s": [0., 1.]})
    with pytest.raises(ValueError, match="single-detector or legacy"):
        load_dual_run(path)


def test_dual_surface_modes_labels_load_rejects_single_and_numeric_controls(tmp_path):
    from PySide6.QtWidgets import QApplication
    from control_app.ui.widgets.phase_scan_surface import PhaseScanReconstructionWidget
    app = QApplication.instance() or QApplication([])
    result = synthetic_result()
    widget = PhaseScanReconstructionWidget(detector_mode="dual_detector")
    widget.set_result(result)
    assert [widget.mode.itemData(i) for i in range(widget.mode.count())] == ["delta_absorbance", "sample_reference_ratio"]
    assert widget.axes.get_ylabel() == "ΔAbsorbance"
    widget.mode.setCurrentIndex(1)
    assert widget.axes.get_ylabel() == "Sample/reference ratio"
    assert widget.spectral_axes.get_ylabel() == "Sample/reference ratio"
    assert widget.time_axes.get_ylabel() == "Sample/reference ratio"
    assert widget.time_input.decimals() == 3 and widget.wavenumber_input.decimals() == 2
    widget.time_input.setValue(2.)
    widget._enter_coordinate("time")
    assert result["time_s"][widget.time_slider.value()] == pytest.approx(.002)
    single = {"absorbance": np.ones((2, 2)), "wavenumber_cm1": [1., 2.], "time_s": [0., 1.]}
    with pytest.raises(ValueError, match="single-detector or legacy"):
        widget.set_result(single)
    path = tmp_path/"single.npz"
    save_native(path, single)
    with pytest.raises(ValueError, match="single-detector or legacy"):
        widget.load_run(path)
    regular_widget = PhaseScanReconstructionWidget()
    with pytest.raises(ValueError, match="Dual-Detector"):
        regular_widget.set_result(result)
    requested = plan()
    records = [(requested.event_at(i), synthetic_spectrum(requested.event_at(i)))
               for i in range(requested.total_scans)]
    calibrated = reconstruct_sequence(records, synthetic_spectrum(), requested, calibration=calibration())
    widget.set_result(calibrated)
    assert [widget.mode.itemData(i) for i in range(widget.mode.count())] == ["absorbance", "delta_absorbance"]
    assert widget.axes.get_ylabel() == "Absorbance"
    widget.mode.setCurrentIndex(1)
    assert widget.axes.get_ylabel() == "ΔAbsorbance"
    widget.clear_result()
    assert widget.result is None and not widget.time_input.isEnabled()
    widget.close()
    regular_widget.close()
    app.processEvents()
