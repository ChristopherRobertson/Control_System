"""Native timing precision, missing intervals, directions and retained values."""
import json
import numpy as np
import pytest

from control_app.measurement_modules.steady_state_slow_scan.native import (
    observed_sweeps, seconds_from_ticks, retain_chunk, combine_poll_streams)


def native_record(*, reverse=False, omit_marker=False, omit_samples=False, bad_reference=False, pump=False):
    ticks = np.arange(110, dtype=np.uint64) + np.uint64(2**62)
    dio = np.zeros(110, np.uint32)
    dio[5:101] |= 1 << 21
    if reverse:
        dio[5:101] |= 1 << 20
    for position in (10, 30, 50, 70, 90):
        if omit_marker and position == 50:
            continue
        dio[position:position+3] |= 1 << 22
    if pump:
        dio[42:44] |= 1 << 17
    indices = np.arange(0, 110, 2)
    if omit_samples:
        indices = indices[(indices < 44) | (indices > 52)]
    sample = {"timestamp": ticks[indices], "x": np.linspace(1., 2., len(indices)), "y": np.zeros(len(indices))}
    reference = {"timestamp": ticks[indices]+1, "x": np.ones(len(indices)), "y": np.zeros(len(indices))}
    if bad_reference:
        reference["x"][20:25] = 0.
    return {"data": {"/test/demods/0/sample": sample, "/test/demods/3/sample": reference,
                     "/test/demods/2/sample": {"timestamp": ticks, "dio": dio}}}


def decode(record, reverse=False):
    return observed_sweeps([record], sample_demodulator=0, reference_demodulator=3,
        timing_demodulator=2, clockbase_hz=100., marker_targets_cm1=[1904.,1903.,1902.,1901.,1900.] if reverse else [1900.,1901.,1902.,1903.,1904.],
        expected_sweeps=1, sample_rate_sps=50., reference_rate_sps=50., marker_gap_limit_s=.3)


def test_large_native_tick_epoch_is_subtracted_before_float_conversion():
    ticks = np.array([2**62+3, 2**62+4, 2**62+13], dtype=np.uint64)
    np.testing.assert_allclose(seconds_from_ticks(ticks, 2**62+3, 1e9), [0.,1e-9,10e-9])


@pytest.mark.parametrize("reverse", [False, True])
def test_observed_controller_axis_and_nearest_reference_keep_original_direction(reverse):
    record = native_record(reverse=reverse)
    sweeps, streams, flags = decode(record, reverse)
    assert not flags
    assert len(sweeps) == 1
    valid_axis = sweeps[0]["axis_cm1"][sweeps[0]["valid"]]
    assert np.all(np.diff(valid_axis) < 0 if reverse else np.diff(valid_axis) > 0)
    np.testing.assert_array_equal(streams["sample"]["timestamp"], record["data"]["/test/demods/0/sample"]["timestamp"])
    np.testing.assert_array_equal(sweeps[0]["sample"], streams["sample"]["x"][sweeps[0]["native_indices"]])


def test_missing_marker_never_invents_axis_positions():
    sweeps, _, _ = decode(native_record(omit_marker=True))
    assert "wavelength_marker_count_mismatch" in sweeps[0]["flags"]
    assert not np.any(sweeps[0]["valid"])
    assert np.all(np.isnan(sweeps[0]["axis_cm1"]))


def test_native_sample_gaps_remain_explicit_missing_support():
    sweeps, _, _ = decode(native_record(omit_samples=True))
    assert "native_sample_gap" in sweeps[0]["flags"]
    gaps = np.flatnonzero(np.diff(sweeps[0]["timestamps_s"]) > .04)
    assert len(gaps) == 1
    assert not sweeps[0]["valid"][gaps[0]+1]


def test_zero_reference_and_unexpected_pump_sync_are_detected():
    sweeps, _, flags = decode(native_record(bad_reference=True, pump=True))
    assert "unexpected_electrical_pump_sync" in flags
    assert not np.all(sweeps[0]["valid"])


def test_partial_native_journal_exact_dtype_and_exclusive_preservation(tmp_path):
    record = native_record()
    path = retain_chunk(tmp_path, 0, record)
    payload = json.loads(open(path, encoding="utf-8").read())
    with np.load(tmp_path / "chunk_000000.npz", allow_pickle=False) as arrays:
        reference = payload["data"]["/test/demods/0/sample"]["timestamp"]
        saved = arrays[reference["native_array"]]
        assert saved.dtype == np.dtype("uint64")
        np.testing.assert_array_equal(saved, record["data"]["/test/demods/0/sample"]["timestamp"])
    with pytest.raises(FileExistsError):
        retain_chunk(tmp_path, 0, record)


def test_missing_stream_duplicate_timing_and_count_errors_are_explicit():
    record = native_record()
    del record["data"]["/test/demods/3/sample"]
    with pytest.raises(ValueError, match="Missing"):
        decode(record)
    record = native_record()
    record["data"]["/test/demods/2/sample"]["timestamp"][15] -= np.uint64(1)
    with pytest.raises(ValueError, match="timestamps"):
        decode(record)


def test_no_native_stream_reordering_or_silent_duplicate_deduplication():
    record = native_record()
    result = combine_poll_streams([record, record], 0)
    expected = record["data"]["/test/demods/0/sample"]["timestamp"]
    np.testing.assert_array_equal(result["timestamp"], np.r_[expected, expected])
