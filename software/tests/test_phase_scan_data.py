import json

import numpy as np
import pytest

from control_app.workflows.phase_scan import PhaseScanSettings, build_phase_scan_plan
from control_app.workflows.phase_scan_data import (
    ScanStore, Spectrum, absorbance, interpolate_supported, save_native, load_native, reconstruct,
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
