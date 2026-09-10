import json

import numpy as np
import pytest

from control_app.workflows.phase_scan import PhaseScanSettings, build_phase_scan_plan
from control_app.workflows.phase_scan_data import (
    ANALYSIS_VERSION, DETECTOR_INPUT, SINGLE_DETECTOR_MODE, ScanStore, Spectrum, absorbance,
    acquisition_settings, interpolate_supported, save_native, load_native, reconstruct, transmission,
)


def spectrum(delay=0, *, background=False, offset=0):
    wn = np.array([2000., 1999., 1998.])
    age = delay + np.array([0., .001, .002])
    a = np.zeros(3) if background else (2000-wn)*.01 + age*20 + offset
    return Spectrum(wn, 2*10**(-a), np.ones(3), 10+age, None if background else 10,
                    {"optical_valid": True, "wavenumber_basis": "measured", "pump_time_basis": "measured"})


def plan(repetitions=1):
    return build_phase_scan_plan(PhaseScanSettings(start_wavenumber_cm1=2000, stop_wavenumber_cm1=1998, scan_speed_cm1_s=1000,
                                  phase_delay_us=500, rest_period_s=.3, repetitions=repetitions))


def single_spectrum(delay=0, *, background=False, offset=0):
    result = spectrum(delay, background=background, offset=offset)
    result.reference_r = None
    result.metadata.update(detector_mode=SINGLE_DETECTOR_MODE, detector_input=DETECTOR_INPUT,
                           record_role="buffer_blank" if background else "pumped_sample")
    return result


def test_controller_marker_basis_is_explicit_provisional_and_reconstructable():
    p = plan()
    background = single_spectrum(background=True)
    records = [(p.event_at(i), single_spectrum((p.event_at(i).phase_delay_us or 0)*1e-6))
               for i in range(p.total_scans)]
    for item in [background, *(record for _, record in records)]:
        item.metadata.update(wavenumber_basis="controller_markers", provisional=True,
                             marker_identity_basis={"source": "MIRcatSDK_GetWlTrigChanParams", "channel": 1})
    result = reconstruct(records, background, p)
    assert result["provisional"]
    assert result["wavenumber_bases"] == ["controller_markers"]
    assert np.isfinite(result["absorbance"]).all()
    assert any("independent absolute wavelength calibration" in line for line in result["limitations"])
    background.metadata["provisional"] = False
    with pytest.raises(ValueError, match="provisional"):
        background.validate()
    background.metadata["provisional"] = True
    background.metadata.pop("marker_identity_basis")
    with pytest.raises(ValueError, match="readback provenance"):
        background.validate()


@pytest.mark.parametrize("sample_basis", ["measured", "nominal_sweep_bounds"])
def test_blank_ratio_rejects_mixed_controller_and_other_coordinate_bases(sample_basis):
    background = single_spectrum(background=True)
    background.metadata.update(wavenumber_basis="controller_markers", provisional=True,
                               marker_identity_basis={"source": "MIRcatSDK_GetWlTrigChanParams"})
    sample = single_spectrum()
    sample.metadata.update(wavenumber_basis=sample_basis, provisional=sample_basis != "measured")
    with pytest.raises(ValueError, match="wavenumber bases must match"):
        transmission(sample, background)


def test_native_roundtrip_keeps_uint64_ticks_and_unknown_nested_fields(tmp_path):
    native = {"sample": {"timestamp": np.array([2**60, 2**60+1], dtype=np.uint64),
                         "dio": np.array([2**31+5, 0], dtype=np.uint32),
                         "auxin0": np.array([.1, np.nan]), "auxin1": np.array([1., 2.]),
                         "time": {"future_field": np.int64(23)}}}
    target = tmp_path / "scan.npz"
    save_native(target, native)
    actual = load_native(target)
    np.testing.assert_array_equal(actual["sample"]["timestamp"], native["sample"]["timestamp"])
    assert actual["sample"]["dio"].dtype == np.uint32
    assert np.isnan(actual["sample"]["auxin0"][1])
    assert actual["sample"]["time"]["future_field"] == 23
    with pytest.raises(FileExistsError):
        save_native(target, {"replacement": True})


def test_consolidated_store_preserves_native_arrays_and_record_index(tmp_path):
    p = plan()
    store = ScanStore(tmp_path, "run", p, compress_raw=False)
    records = [(p.event_at(index), {"spectrum": spectrum().to_dict()}) for index in range(3)]
    ticks = np.arange(1000, dtype=np.uint64) + np.uint64(2**60)
    path = store.save_block(records, native={"blocks": [{"timestamp": ticks}]})
    store.finish("COMPLETE")
    assert list((store.path / "raw").rglob("*.npz")) == [path]
    saved = load_native(path)
    np.testing.assert_array_equal(saved["native"]["blocks"][0]["timestamp"], ticks)
    assert saved["native"]["blocks"][0]["timestamp"].dtype == np.uint64
    assert len(saved["records"]) == 3
    assert json.loads((store.path / "result.json").read_text())["record_count"] == 3
    index = [json.loads(line) for line in (store.path / "scan_index.jsonl").read_text().splitlines()]
    assert [item["record_index"] for item in index] == [0, 1, 2]
    assert all(item["path"] == "raw/acquisition.npz" for item in index)
    run = json.loads((store.path / "run.json").read_text())
    assert run["raw_storage"]["save_after_acquisition"]
    with pytest.raises(FileExistsError):
        store.save_block(records)


def test_incomplete_store_retains_raw_data_without_reconstruction(tmp_path):
    p = plan()
    store = ScanStore(tmp_path, "run", p)
    path = store.save_block([], native={"partial": np.arange(7, dtype=np.uint32)})
    store.finish("INCOMPLETE", error="Expected record count was not reached")
    np.testing.assert_array_equal(load_native(path)["native"]["partial"], np.arange(7))
    assert json.loads((store.path / "result.json").read_text())["status"] == "INCOMPLETE"
    assert not (store.path / "processed").exists()


def test_absorbance_sign_reference_normalization_and_invalid_values():
    bg = spectrum(background=True)
    sample = spectrum()
    np.testing.assert_allclose(absorbance(sample, bg), [0, .03, .06], atol=1e-12)
    sample.sample_r[0] = 4
    sample.reference_r[1] = 0
    a = absorbance(sample, bg)
    assert a[0] == pytest.approx(-np.log10(2))  # Negative values are not clipped.
    assert np.isnan(a[1])
    bg.metadata["optical_valid"] = False
    with pytest.raises(ValueError, match="diagnostic"):
        absorbance(sample, bg)


def test_normalization_preserves_structured_detector_signal_and_raw_arrays():
    wn = np.linspace(1900., 2000., 301)
    times = np.linspace(0., .0023, len(wn))
    expected = .02 + .006 * np.sin(wn * 1.73) + .003 * np.cos(wn * .19)
    reference = 1.1 + .1 * np.cos(wn * .07)
    raw_sample = reference * 10**(-expected)
    metadata = {"optical_valid": True, "wavenumber_basis": "measured"}
    scan = Spectrum(wn, raw_sample.copy(), reference.copy(), times, 0., metadata)
    background = Spectrum(wn, reference.copy(), reference.copy(), times, None, metadata)
    np.testing.assert_allclose(absorbance(scan, background), expected, atol=1e-14)
    np.testing.assert_array_equal(scan.sample_r, raw_sample)
    np.testing.assert_array_equal(scan.reference_r, reference)


def test_interpolation_never_extrapolates_or_bridges_invalid_samples():
    result = interpolate_supported([0, 1, 2, 3], [1, np.nan, 3, 4], [-1, .5, 1.5, 2.5, 4])
    np.testing.assert_allclose(result, [np.nan, np.nan, np.nan, 3.5, np.nan], equal_nan=True)


def test_reconstruction_uses_time_within_scan_and_averages_complete_repetitions():
    p = plan(2)
    records = []
    for i in range(p.total_scans):
        event = p.event_at(i)
        records.append((event, spectrum((event.phase_delay_us or 0)*1e-6,
                                       offset=.02*(event.repetition-1))))
    result = reconstruct(records, spectrum(background=True), p)
    wn, times, a = result["wavenumber_cm1"], result["time_s"], result["absorbance"]
    expected = (2000-wn)[None, :]*.01 + times[:, None]*20 + .01
    valid = np.isfinite(a)
    assert valid.all()
    assert result["display_pump_time_ms"] == 0.
    np.testing.assert_allclose(a[valid], expected[valid], atol=1e-12)
    assert np.all(result["repetition_count"][valid] == 2)
    np.testing.assert_allclose(result["standard_error"][valid], .01, atol=1e-10)
    assert np.isfinite(a[0, 0])  # Negative scan starts now supply early ages at the low-wavenumber end.
    np.testing.assert_allclose(times[[0, -1]], [-.001, .005])
    records[1][1].metadata["pump_time_basis"] = "commanded"
    with pytest.raises(ValueError, match="Commanded"):
        reconstruct(records, spectrum(background=True), p)


def test_reconstruction_keeps_exact_endpoints_for_nondivisible_phase_step():
    settings = PhaseScanSettings(start_wavenumber_cm1=2000, stop_wavenumber_cm1=1998,
                                 scan_speed_cm1_s=1000, phase_delay_us=3)
    p = build_phase_scan_plan(settings)
    records = [(p.event_at(i), spectrum((p.event_at(i).phase_delay_us or 0)*1e-6))
               for i in range(p.total_scans)]
    result = reconstruct(records, spectrum(background=True), p)
    times = result["time_s"]
    np.testing.assert_array_equal(times[[0, -1]], [-.001, .005])
    np.testing.assert_allclose(np.diff(times)[1:-1], 3e-6, atol=1e-18)
    assert np.isfinite(result["absorbance"]).all()


@pytest.mark.parametrize("defect", ["missing", "duplicate"])
def test_reconstruction_rejects_incomplete_or_duplicated_nominal_records(defect):
    p = plan()
    records = [(p.event_at(i), spectrum((p.event_at(i).phase_delay_us or 0)*1e-6))
               for i in range(p.total_scans)]
    if defect == "missing":
        records.pop()
    else:
        records[-1] = records[-2]
    with pytest.raises(ValueError, match="complete phase set|duplicated phase records"):
        reconstruct(records, spectrum(background=True), p)


def test_reconstruction_averages_duplicate_native_time_coordinates():
    p = plan()
    records = []
    for i in range(p.total_scans):
        event = p.event_at(i)
        # Model native-tick quantization coarser than the requested phase step.
        measured_delay = round((event.phase_delay_us or 0) * 1e-6 / .001) * .001
        records.append((event, spectrum(measured_delay)))
    result = reconstruct(records, spectrum(background=True), p)
    assert np.isfinite(result["absorbance"]).any()
    assert result["repetition_count"].max() == 1


def test_native_marker_alignment_preserves_large_tick_precision_and_rejects_dark():
    from control_app.workflows.phase_scan_native import marker_spectrum
    base = 2**60
    def stream(offset, r):
        ticks = np.array([base+offset+i*10 for i in range(5)], dtype=np.uint64)
        return {"timestamp": ticks, "x": np.full(5, r), "y": np.zeros(5),
                "dio": np.zeros(5, dtype=np.uint32), "auxin0": np.zeros(5), "auxin1": np.zeros(5)}
    record = {"optical_valid": True, "clockbase_hz": 10000,
              "native_chunks": [{"data": {"/dev/demods/0/sample": stream(5, 1),
                                          "/dev/demods/3/sample": stream(0, 2)}}]}
    args = {"marker_ticks": np.array([base, base+40], dtype=np.uint64),
            "marker_wavenumbers_cm1": [2000, 1900], "pump_tick": base+10}
    actual = marker_spectrum(record, **args)
    np.testing.assert_allclose(actual.wavenumber_cm1, [1987.5, 1962.5, 1937.5, 1912.5])
    np.testing.assert_allclose(actual.sample_time_s-actual.pump_time_s, [-.0005,.0005,.0015,.0025])
    np.testing.assert_allclose(actual.reference_r, 2)
    record["optical_valid"] = False
    with pytest.raises(ValueError, match="inhibited/dark"):
        marker_spectrum(record, **args)


def test_marker_bearing_sweep_selection_preserves_ancillary_process_interval():
    from control_app.workflows.phase_scan_native import select_sweep_active_interval

    ticks = np.arange(100, dtype=np.uint64) + np.uint64(2**60)
    dio = np.zeros(100, dtype=np.uint32)
    dio[10:30] |= np.uint32(1 << 21)  # Ancillary process-event echo.
    dio[50:80] |= np.uint32(1 << 21)  # Actual Sweep Active.
    for start in (55, 65, 75):
        dio[start:start + 2] |= np.uint32(1 << 22)
    selected, markers, intervals, ancillary = select_sweep_active_interval(ticks, dio)
    assert selected == (int(ticks[50]), int(ticks[80]))
    assert markers.tolist() == ticks[[55, 65, 75]].tolist()
    assert intervals == [(int(ticks[10]), int(ticks[30])), selected]
    assert ancillary == [(int(ticks[10]), int(ticks[30]))]


def test_single_detector_uses_prior_blank_intensity_and_keeps_native_arrays(tmp_path):
    wn = np.array([2000., 1999., 1998.])
    sample = single_spectrum()
    expected = np.array([-.02, .12, .08])
    blank = single_spectrum(background=True)
    blank.sample_r = np.array([4., 2., 3.])
    sample.sample_r = blank.sample_r * 10**(-expected)
    source = sample.sample_r.copy()
    np.testing.assert_allclose(transmission(sample, blank), 10**(-expected))
    np.testing.assert_allclose(absorbance(sample, blank), expected, atol=1e-14)
    np.testing.assert_array_equal(sample.sample_r, source)
    np.testing.assert_array_equal(sample.wavenumber_cm1, wn)
    np.testing.assert_array_equal(blank.normalization_signal(), blank.sample_r)
    with pytest.raises(ValueError, match="separate buffer blank"):
        sample.ratio()
    path = tmp_path / "single.npz"
    save_native(path, sample.to_dict())
    restored = Spectrum.from_dict(load_native(path))
    assert restored.reference_r is None
    assert restored.detector_mode == SINGLE_DETECTOR_MODE
    np.testing.assert_array_equal(restored.sample_r, source)


def test_single_detector_blank_interpolation_keeps_invalid_points_and_no_extrapolation():
    blank = single_spectrum(background=True)
    blank.wavenumber_cm1 = np.array([2000., 1998., 1996.])
    blank.sample_r = np.array([4., 2., 6.])
    sample = single_spectrum()
    sample.wavenumber_cm1 = np.array([2001., 1999., 1997.])
    sample.sample_r = np.array([1., 1.5, 1.])
    np.testing.assert_allclose(transmission(sample, blank), [np.nan, .5, .25], equal_nan=True)
    blank.sample_r[1] = 0
    assert np.isnan(absorbance(sample, blank)).all()
    blank.sample_r[1] = np.nan
    assert np.isnan(absorbance(sample, blank)).all()


@pytest.mark.parametrize("defect", ["dual", "baseline", "pumped", "acquisition_settings", "hf2li_detector_settings", "hf2li_device"])
def test_single_detector_requires_matching_unpumped_buffer_blank(defect):
    sample, blank = single_spectrum(), single_spectrum(background=True)
    if defect == "dual":
        blank = spectrum(background=True)
    elif defect == "baseline":
        blank.metadata["record_role"] = "unpumped_sample_baseline"
    elif defect == "pumped":
        blank.pump_time_s = 10.
    else:
        sample.metadata[defect] = {"value": 1}
        blank.metadata[defect] = {"value": 2}
    with pytest.raises(ValueError, match="match|unpumped buffer blank"):
        absorbance(sample, blank)


def test_single_detector_processing_uses_runner_tolerance_for_hf2li_readbacks():
    sample, blank = single_spectrum(), single_spectrum(background=True)
    sample.metadata["hf2li_detector_settings"] = {"/dev/demods/0/rate": {"value": 1000.0002}}
    blank.metadata["hf2li_detector_settings"] = {"/dev/demods/0/rate": {"value": 1000.}}
    np.testing.assert_allclose(absorbance(sample, blank), [0, .03, .06], atol=1e-12)
    blank.metadata["hf2li_detector_settings"]["/dev/demods/0/rate"]["value"] = 900.
    with pytest.raises(ValueError, match="hf2li_detector_settings must match"):
        absorbance(sample, blank)


def test_single_detector_rejects_fabricated_reference_and_undeclared_mode():
    sample = single_spectrum()
    sample.reference_r = np.ones(3)
    with pytest.raises(ValueError, match="CH2 reference"):
        sample.validate()
    sample.reference_r = None
    sample.metadata.pop("detector_mode")
    with pytest.raises(ValueError, match="actual reference"):
        sample.validate()


def test_single_detector_settings_include_input_mode_and_preserve_blank_compatibility():
    settings = PhaseScanSettings()
    metadata = acquisition_settings(settings)
    assert metadata["detector_mode"] == SINGLE_DETECTOR_MODE
    assert metadata["detector_input"] == DETECTOR_INPUT
    assert metadata["hf2_preset"] == "exploratory_phase_scan_single_detector"
    from dataclasses import replace
    assert acquisition_settings(replace(settings, phase_delay_us=20, repetitions=3)) == metadata
    assert acquisition_settings(replace(settings, scan_speed_cm1_s=settings.scan_speed_cm1_s / 2)) != metadata


def test_single_detector_reconstruction_uses_buffer_blank_keeps_unpumped_baseline_separate():
    p = plan(2)
    records = []
    for i in range(p.total_scans):
        event = p.event_at(i)
        value = single_spectrum((event.phase_delay_us or 0)*1e-6, offset=.02*(event.repetition-1))
        if not event.pump_enabled:
            value.metadata["record_role"] = "unpumped_sample_baseline"
            value.pump_time_s = None
            value.sample_r[:] = 1e-9  # Baseline cannot alter the ratio denominator.
        records.append((event, value))
    blank = single_spectrum(background=True)
    result = reconstruct(records, blank, p)
    expected = (2000-result["wavenumber_cm1"])[None, :]*.01 + result["time_s"][:, None]*20 + .01
    np.testing.assert_allclose(result["absorbance"], expected, atol=1e-12)
    assert result["analysis_version"] == ANALYSIS_VERSION
    assert result["detector_mode"] == SINGLE_DETECTOR_MODE
    assert result["normalization"] == "-log10(CH1_sample / prior_CH1_buffer_blank)"
    assert any("drift" in limitation for limitation in result["limitations"])
    assert np.all(result["repetition_count"] == 2)


def test_single_detector_native_marker_mapping_needs_no_ch2_and_retains_large_ticks():
    from control_app.workflows.phase_scan_native import marker_spectrum
    base = 2**60
    ticks = np.array([base+5+i*10 for i in range(5)], dtype=np.uint64)
    stream = {"timestamp": ticks, "x": np.ones(5), "y": np.zeros(5),
              "dio": np.zeros(5, dtype=np.uint32), "auxin0": np.zeros(5), "auxin1": np.zeros(5)}
    record = {"optical_valid": True, "clockbase_hz": 10000, "detector_mode": SINGLE_DETECTOR_MODE,
              "detector_input": DETECTOR_INPUT, "native_chunks": [{"data": {"/dev/demods/0/sample": stream}}]}
    args = {"marker_ticks": np.array([base, base+40], dtype=np.uint64),
            "marker_wavenumbers_cm1": [2000, 1900], "pump_tick": base+10}
    actual = marker_spectrum(record, **args)
    assert actual.reference_r is None
    assert actual.metadata["reference_demodulator"] is None
    assert actual.metadata["detector_input"] == DETECTOR_INPUT
    np.testing.assert_allclose(actual.wavenumber_cm1, [1987.5, 1962.5, 1937.5, 1912.5])
    np.testing.assert_allclose(actual.sample_time_s-actual.pump_time_s, [-.0005,.0005,.0015,.0025])
    with pytest.raises(ValueError, match="CH1 demodulator 0"):
        marker_spectrum(record, sample_demod=3, **args)


def test_single_detector_sweep_decode_preserves_timing_without_reference_stream():
    from control_app.workflows.phase_scan_native import spectrum_from_sweep
    base = 2**60
    ticks = np.arange(100, dtype=np.uint64) + np.uint64(base)
    dio = np.zeros(100, dtype=np.uint32)
    dio[20:80] |= np.uint32(1 << 21)
    for start in (30, 50, 70):
        dio[start:start+2] |= np.uint32(1 << 22)
    def stream(native_ticks, signal, bits):
        return {"timestamp": native_ticks, "x": signal, "y": np.zeros(len(native_ticks)),
                "dio": bits, "auxin0": np.zeros(len(native_ticks)), "auxin1": np.zeros(len(native_ticks))}
    record = {"optical_valid": True, "clockbase_hz": 10000, "detector_mode": SINGLE_DETECTOR_MODE,
              "record_role": "buffer_blank", "native_chunks": [{"data": {
                  "/dev/demods/0/sample": stream(ticks[[35, 45, 55, 65]], np.array([2., 3., 4., 5.]), np.zeros(4, dtype=np.uint32)),
                  "/dev/demods/2/sample": stream(ticks, np.zeros(100), dio)}}]}
    actual = spectrum_from_sweep(record, start_cm1=2000, stop_cm1=1998,
                                 targets_cm1=[2000, 1999, 1998], origin_tick=base)
    assert actual.reference_r is None
    assert actual.metadata["record_role"] == "buffer_blank"
    assert actual.metadata["wavenumber_basis"] == "measured"
    assert actual.metadata["timestamp_origin_ticks"] == base
    np.testing.assert_allclose(actual.wavenumber_cm1, [1999.75, 1999.25, 1998.75, 1998.25])
    np.testing.assert_array_equal(actual.normalization_signal(), [2., 3., 4., 5.])
