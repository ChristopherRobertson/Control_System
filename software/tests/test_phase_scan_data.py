from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from control_app.workflows.phase_scan import PhaseScanSettings, build_phase_scan_plan
from control_app.workflows.phase_scan_data import (
    Spectrum, absorbance, interpolate_supported, save_native, load_native, reconstruct,
)
from control_app.workflows.phase_scan_runner import PhaseScanRunner


def spectrum(delay=0, *, background=False, offset=0):
    wn = np.array([2000., 1999., 1998.])
    age = delay + np.array([0., .001, .002])
    a = np.zeros(3) if background else (2000-wn)*.01 + age*20 + offset
    return Spectrum(wn, 2*10**(-a), np.ones(3), 10+age, None if background else 10,
                    {"optical_valid": True, "wavenumber_basis": "measured", "pump_time_basis": "measured"})


def plan(repetitions=1):
    return build_phase_scan_plan(PhaseScanSettings(start_wavenumber_cm1=2000, stop_wavenumber_cm1=1998, scan_speed_cm1_s=1000,
                                  phase_delay_us=500, rest_period_s=.1, repetitions=repetitions))


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
    np.testing.assert_allclose(a[valid], expected[valid], atol=1e-12)
    assert np.all(result["repetition_count"][valid] == 2)
    np.testing.assert_allclose(result["standard_error"][valid], .01, atol=1e-10)
    assert np.isfinite(a[0, 0])  # Negative scan starts now supply early ages at the low-wavenumber end.
    np.testing.assert_allclose(times[[0, -1]], [-.002, .005])
    records[1][1].metadata["pump_time_basis"] = "commanded"
    with pytest.raises(ValueError, match="Commanded"):
        reconstruct(records, spectrum(background=True), p)


class FakeAcquirer:
    def __init__(self, calls, *, background=False, fail_close=False, on_capture=None, readback=None):
        self.calls, self.background, self.fail_close = calls, background, fail_close
        self.on_capture = on_capture
        self.readback = readback or {"current_ma": 750, "rate": 20_000, "timeconstant": 50e-6}

    def prepare(self, settings, store, cancel):
        return self.readback

    def capture(self, event, cancel):
        self.calls.append(event)
        if self.on_capture:
            self.on_capture(cancel)
        return {"fixture": "SYNTHETIC TEST ONLY"}, spectrum((event.phase_delay_us or 0)*1e-6,
                                                           background=self.background)

    def close(self):
        if self.fail_close:
            raise RuntimeError("stop failed")


def test_background_gate_complete_run_one_scan_per_phase_and_files(tmp_path):
    calls = []
    runner = PhaseScanRunner(lambda: FakeAcquirer(calls, background=True))
    p = plan()
    with pytest.raises(RuntimeError, match="background"):
        runner.execute("run", tmp_path, p)
    runner.execute("background", tmp_path, p)
    assert runner.background_matches(p.settings)
    assert runner.background_matches(replace(p.settings, repetitions=2, rest_period_s=2))
    assert not runner.background_matches(replace(p.settings, probe_repetition_rate_hz=1e6))
    runner.acquirer_factory = lambda: FakeAcquirer(calls)
    result = runner.execute("run", tmp_path, p)
    assert len(calls) == p.total_scans + 1
    assert len(list(result["path"].glob("raw/rep_*/*.npz"))) == p.total_scans
    assert len((result["path"] / "scan_index.jsonl").read_text().splitlines()) == p.total_scans
    assert (result["path"] / "processed/reconstruction.npz").is_file()
    assert json.loads((result["path"] / "result.json").read_text())["status"] == "COMPLETE"


def test_failed_background_shutdown_does_not_enable_start(tmp_path):
    runner = PhaseScanRunner(lambda: FakeAcquirer([], background=True, fail_close=True))
    with pytest.raises(RuntimeError, match="Safe shutdown failed"):
        runner.execute("background", tmp_path, plan())
    assert runner.background is None
    record = next(tmp_path.rglob("result.json"))
    assert json.loads(record.read_text())["status"] == "FAILED_SAFE_STATE_UNVERIFIED"


def test_abort_retains_native_record_and_does_not_promote_background(tmp_path):
    runner = PhaseScanRunner(lambda: FakeAcquirer([], background=True, on_capture=lambda c: c.set()))
    with pytest.raises(RuntimeError, match="aborted"):
        runner.execute("background", tmp_path, plan())
    assert runner.background is None
    assert len(list(tmp_path.rglob("scan_*.npz"))) == 1
    assert json.loads(next(tmp_path.rglob("result.json")).read_text())["status"] == "ABORTED"


def test_device_change_invalidates_background(tmp_path):
    runner = PhaseScanRunner(lambda: FakeAcquirer([], background=True))
    runner.execute("background", tmp_path, plan())
    runner.acquirer_factory = lambda: FakeAcquirer([], readback={"current_ma": 999})
    with pytest.raises(RuntimeError, match="Instrument settings changed"):
        runner.execute("run", tmp_path, plan())
    assert runner.background is None


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
