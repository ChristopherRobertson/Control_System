"""Offline single-detector products from synthetic native HF2LI polling records."""
from copy import deepcopy
import json

import numpy as np
import pytest

from control_app.workflows.phase_scan_data import (
    DETECTOR_INPUT, SINGLE_DETECTOR_MODE, Spectrum, absorbance, load_native, save_native,
)
from control_app.workflows.single_detector_scan_analysis import analyze_single_detector_scan


def native_record():
    base = 2**60
    ticks = np.arange(5000, dtype=np.uint64)+np.uint64(base)
    dio = np.zeros(len(ticks), dtype=np.uint32)
    dio[1000:3500] |= np.uint32(1 << 21)
    for index in range(1000, 3501, 125):
        dio[index:index+2] |= np.uint32(1 << 22)
    def stream(ts, bits):
        return {"timestamp": ts, "x": np.linspace(.8, 1., len(ts)), "y": np.zeros(len(ts)),
                "dio": bits, "auxin0": np.zeros(len(ts)), "auxin1": np.zeros(len(ts))}
    return {"optical_valid": True, "detector_mode": SINGLE_DETECTOR_MODE,
            "detector_input": DETECTOR_INPUT, "record_role": "buffer_blank", "clockbase_hz": 1000.,
            "pump_events": 0, "pump_outputs_disabled_readback_verified": True,
            "hf2li_input_checks": [{"status": {"status/flags/adcclip/0": 0}}],
            "scan_profile": {"start_cm1": 2000., "stop_cm1": 1900., "scan_rate_cm1_s": 40.,
                             "expected_markers": 21, "timing_rate_sps": 1000., "detector_rate_sps": 100.},
            "native_chunks": [{"data": {"/dev/demods/0/sample": stream(ticks[::10], dio[::10]),
                                           "/dev/demods/2/sample": stream(ticks, dio)}}]}


def analyze(tmp_path, record):
    save_native(tmp_path / "hf2li_native.npz", record)
    return analyze_single_detector_scan(tmp_path, record)


def test_blank_saves_ch1_only_products_and_does_not_identify_markers_from_count(tmp_path):
    record = native_record()
    summary = analyze(tmp_path, record)
    assert summary["usable_as_background"]
    assert summary["status"] == "USABLE_PROVISIONAL"
    assert summary["markers_observed"] == summary["markers_expected"] == 21
    assert summary["provisional"]
    assert summary["positive_sample_count"] == 251
    assert summary["sweep_duration_s"] == 2.5
    assert summary["clipped_check_count"] == summary["detector_gap_count"] == 0
    spectrum = Spectrum.from_dict(load_native(tmp_path / "ch1_spectrum.npz")["spectrum"])
    assert spectrum.reference_r is None
    assert spectrum.metadata["timestamp_origin_ticks"] == 2**60+1000
    np.testing.assert_allclose(spectrum.wavenumber_cm1[[0, -1]], [2000., 1900.])
    assert (tmp_path / "single_detector_scan.png").stat().st_size > 1000
    assert "CH1_R_V" in (tmp_path / "ch1_spectrum.csv").read_text()
    assert "reference_R_V" not in (tmp_path / "ch1_spectrum.csv").read_text()
    actual = load_native(tmp_path / "hf2li_native.npz")
    assert actual["native_chunks"][0]["data"]["/dev/demods/2/sample"]["timestamp"].dtype == np.uint64
    with pytest.raises(FileExistsError):
        analyze_single_detector_scan(tmp_path, record)


@pytest.mark.parametrize("defect", ["clipped", "unknown_clipping", "pump", "incomplete", "two_sweeps", "no_positive"])
def test_unusable_records_are_reported_and_preserved(tmp_path, defect):
    record = native_record()
    data = record["native_chunks"][0]["data"]
    if defect == "clipped":
        record["hf2li_input_checks"][0]["status"]["status/flags/adcclip/0"] = 1
    elif defect == "unknown_clipping":
        record["hf2li_input_checks"] = []
    elif defect == "pump":
        data["/dev/demods/2/sample"]["dio"][2000:2010] |= np.uint32(1 << 17)
    elif defect == "incomplete":
        record["optical_valid"] = False
    elif defect == "two_sweeps":
        data["/dev/demods/2/sample"]["dio"][4000:4500] |= np.uint32(1 << 21)
        for start in (4150, 4250):
            data["/dev/demods/2/sample"]["dio"][start:start+2] |= np.uint32(1 << 22)
    elif defect == "no_positive":
        data["/dev/demods/0/sample"]["x"][:] = 0
    result = analyze(tmp_path, record)
    assert not result["usable_for_ratio"]
    assert not result["usable_as_background"]
    assert result["unusable_reasons"]
    assert result["status"] == "UNUSABLE"
    assert json.loads((tmp_path / "analysis.json").read_text())["status"] == "UNUSABLE"
    assert (tmp_path / "hf2li_native.npz").exists()
    if (tmp_path / "ch1_spectrum.npz").exists():
        with pytest.raises(ValueError, match="diagnostic"):
            Spectrum.from_dict(load_native(tmp_path / "ch1_spectrum.npz")["spectrum"])


def test_independently_identified_markers_limit_support_without_extrapolation(tmp_path):
    record = native_record()
    timing = record["native_chunks"][0]["data"]["/dev/demods/2/sample"]
    timing["dio"] &= np.uint32(~np.uint32(1 << 22))
    for index in (1500, 2000, 2500, 3000):
        timing["dio"][index:index+2] |= np.uint32(1 << 22)
    record["marker_wavenumbers_cm1"] = [1980., 1960., 1940., 1920.]
    record["marker_identity_basis"] = "Synthetic independently identified anchors"
    result = analyze(tmp_path, record)
    assert result["status"] == "USABLE"
    assert not result["provisional"]
    spectrum = Spectrum.from_dict(load_native(tmp_path / "ch1_spectrum.npz")["spectrum"])
    np.testing.assert_allclose(spectrum.wavenumber_cm1[[0, -1]], [1980., 1920.])
    assert spectrum.wavenumber_cm1.min() >= 1920
    assert spectrum.wavenumber_cm1.max() <= 1980


def controller_record():
    record = native_record()
    record["scan_profile"].update(qcl=1, marker_interval_cm1=5.)
    readback = {"channel": 1, "units": 2, "start": 2000., "stop": 1900.,
                "interval": 5., "num_triggers": 21}
    record["mircat_marker_channel_checks"] = [
        {"context": context, "available": True, "channel": 1,
         "source": "MIRcatSDK_GetWlTrigChanParams", "readback": deepcopy(readback),
         "timestamp_utc": "2026-09-06T21:41:19+00:00"}
        for context in ("configured", "after_sweep_setup")]
    return record


def test_controller_readbacks_map_observed_markers_and_crop_without_calibration_claim(tmp_path):
    record = controller_record()
    timing = record["native_chunks"][0]["data"]["/dev/demods/2/sample"]
    timing["dio"] &= np.uint32(~np.uint32(1 << 22))
    positions = np.arange(1100, 3401, 115)
    positions[1] += 20  # Controller mapping follows observed nonuniform marker timing.
    for position in positions:
        timing["dio"][position:position+2] |= np.uint32(1 << 22)
    result = analyze(tmp_path, record)
    assert result["usable_as_background"] and result["provisional"]
    assert result["wavenumber_basis"] == "controller_markers"
    assert result["axis_sample_count"] < result["sample_count"]
    assert result["marker_identity_basis"]["source"] == "MIRcatSDK_GetWlTrigChanParams"
    spectrum = Spectrum.from_dict(load_native(tmp_path / "ch1_spectrum.npz")["spectrum"])
    np.testing.assert_allclose(spectrum.wavenumber_cm1[[0, -1]], [2000., 1900.])
    expected = np.interp(spectrum.sample_time_s, (positions-1000)/1000., np.arange(2000., 1899., -5.))
    np.testing.assert_allclose(spectrum.wavenumber_cm1, expected)
    assert any("independent absolute wavelength calibration is not established" in message for message in result["warnings"])


def test_conflicting_controller_marker_readbacks_do_not_silently_assign_nominal_axis(tmp_path):
    record = controller_record()
    record["mircat_marker_channel_checks"][-1]["readback"]["num_triggers"] = 20
    result = analyze(tmp_path, record)
    assert result["status"] == "UNUSABLE"
    assert not (tmp_path / "ch1_spectrum.npz").exists()


def test_reanalysis_links_original_native_without_copy_or_overwrite(tmp_path):
    record = controller_record()
    native_path = tmp_path / "original" / "hf2li_native.npz"
    save_native(native_path, record)
    original = native_path.read_bytes()
    derived = tmp_path / "derived"
    result = analyze_single_detector_scan(derived, record, native_source=native_path)
    assert result["native_source"] == "../original/hf2li_native.npz"
    assert result["artifact_kind"] == "derived_spectrum_from_preserved_native"
    assert not (derived / "hf2li_native.npz").exists()
    assert native_path.read_bytes() == original
    with pytest.raises(FileExistsError):
        analyze_single_detector_scan(derived, record, native_source=native_path)


def test_detector_gap_is_segmented_and_cannot_be_bridged_in_blank_ratio(tmp_path):
    record = native_record()
    stream = record["native_chunks"][0]["data"]["/dev/demods/0/sample"]
    for key in stream:
        stream[key] = np.delete(stream[key], np.arange(200, 210))
    result = analyze(tmp_path, record)
    assert result["detector_gap_count"] == 1
    blank = Spectrum.from_dict(load_native(tmp_path / "ch1_spectrum.npz")["spectrum"])
    assert len(np.unique(blank.segment_id)) == 2
    sample = deepcopy(blank)
    sample.metadata["record_role"] = "unpumped_sample_test"
    sample.wavenumber_cm1 = np.array([1970., 1960., 1950.])
    sample.sample_time_s = np.array([.75, 1., 1.25])
    sample.sample_r = np.ones(3)
    sample.segment_id = None
    ratio = absorbance(sample, blank)
    assert np.isfinite(ratio[0]) and np.isnan(ratio[1]) and np.isfinite(ratio[2])


def test_analysis_requires_preserved_native_before_deriving_artifacts(tmp_path):
    with pytest.raises(FileNotFoundError, match="Preserve"):
        analyze_single_detector_scan(tmp_path, native_record())


def test_dropout_checks_use_quantized_readback_instead_of_requested_rate(tmp_path):
    record = native_record()
    record["scan_profile"].update(detector_rate_sps=28782., timing_rate_sps=200000.)
    record["hf2li_detector_settings"] = {
        "/dev/demods/0/rate": {"value": 100.}, "/dev/demods/2/rate": {"value": 1000.}}
    result = analyze(tmp_path, record)
    assert result["usable_as_background"]
    assert result["detector_gap_count"] == result["timing_gap_count"] == 0
    assert result["detector_sample_interval_s"] == .01


@pytest.mark.parametrize("defect", ["no_markers", "short_echo", "only_prefire"])
def test_nonoptical_intervals_cannot_supply_a_blank(tmp_path, defect):
    record = native_record()
    timing = record["native_chunks"][0]["data"]["/dev/demods/2/sample"]
    if defect == "no_markers":
        timing["dio"] &= np.uint32(~np.uint32(1 << 22))
    elif defect == "short_echo":
        timing["dio"][:] = 0
        timing["dio"][1000:1010] |= np.uint32(1 << 21)
        timing["dio"][[1002, 1005]] |= np.uint32(1 << 22)
    else:
        record["pre_process_last_timing_tick"] = 2**60+3600
    result = analyze(tmp_path, record)
    assert not result["usable_as_background"]
    assert result["status"] == "UNUSABLE"


def test_prefire_marker_interval_and_short_ancillary_echo_remain_retained(tmp_path):
    record = native_record()
    timing = record["native_chunks"][0]["data"]["/dev/demods/2/sample"]
    timing["dio"][100:300] |= np.uint32(1 << 21)
    timing["dio"][[150, 200]] |= np.uint32(1 << 22)
    timing["dio"][500:510] |= np.uint32(1 << 21)
    record["pre_process_last_timing_tick"] = 2**60+400
    result = analyze(tmp_path, record)
    assert result["usable_as_background"]
    assert result["observed_complete_sweeps"] == 1
    assert result["observed_complete_dio21_intervals"] == 3
    assert len(result["ancillary_dio21_intervals_ignored"]) == 2
    assert result["sweep_duration_s"] == 2.5


@pytest.mark.parametrize("baseline_high", [False, True])
def test_static_idle_level_is_not_a_pump_event(tmp_path, baseline_high):
    record = native_record()
    record["pre_process_last_timing_tick"] = 2**60+500
    if baseline_high:
        for stream in record["native_chunks"][0]["data"].values():
            stream["dio"] |= np.uint32(1 << 17)
    result = analyze(tmp_path, record)
    assert result["usable_as_background"]
    assert result["pump_sync_baseline_high"] is baseline_high
    assert result["pump_sync_transition_count"] == 0
    assert result["pump_high_sample_count"] == (5000 if baseline_high else 0)


@pytest.mark.parametrize("defect", ["falling_edge", "unstable_baseline", "unverified_inhibition", "unknown_events"])
def test_pump_uncertainty_rejects_background(tmp_path, defect):
    record = native_record()
    record["pre_process_last_timing_tick"] = 2**60+500
    timing = record["native_chunks"][0]["data"]["/dev/demods/2/sample"]
    if defect == "falling_edge":
        timing["dio"][:2000] |= np.uint32(1 << 17)
    elif defect == "unstable_baseline":
        timing["dio"][100:200] |= np.uint32(1 << 17)
    elif defect == "unverified_inhibition":
        record["pump_outputs_disabled_readback_verified"] = False
    else:
        record["pump_events"] = None
    result = analyze(tmp_path, record)
    assert not result["usable_as_background"]
    assert result["unusable_reasons"]
