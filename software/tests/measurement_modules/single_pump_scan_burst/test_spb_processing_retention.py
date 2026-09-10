from pathlib import Path
import json
import numpy as np
import pytest

from control_app.measurement_modules.single_pump_scan_burst.persistence import RunStore, load_run, iter_chunks, compatibility_conflicts, assert_unused_sample_state
from control_app.measurement_modules.single_pump_scan_burst.processing import process_block, detector_ratio, band_summary, Quality, PlateauTracker


def native(times, signal, *, scans=None, wn=None):
    times = np.asarray(times, float)
    return {"sample_time_s": times, "sample": np.asarray(signal, float),
            "wavenumber_cm1": np.full(len(times), 1945.) if wn is None else np.asarray(wn),
            "reference": np.ones(len(times)),
            "scan_index": np.arange(len(times)) if scans is None else np.asarray(scans),
            "direction": np.ones(len(times), int)}


def test_spb_multiscale_pointwise_recovery_censoring_and_sparse_support():
    times = np.array([.00001, .00003, .0001, .03, .1, 1., 30., 100., 1200., 3000.])
    truth = -.08*(.35*np.exp(-times/.00008)+.4*np.exp(-times/20.)+.25)
    record = native(99.+times, 10**(-truth))
    baseline = native([98.], [1.])
    result = process_block(record, baseline, mode="dual", pump_time_s=99.)
    np.testing.assert_allclose(result["delta_absorbance"], truth, atol=1e-15)
    np.testing.assert_allclose(result["time_s"], times, atol=1e-13)
    assert len(result["time_s"]) == len(times)  # No invented points in long gaps.
    assert result["absorbance"] is None
    summary = band_summary(result, 1944., 1946., plateau_tolerance=1e-7, plateau_points=2, plateau_min_span_s=100.)
    assert summary["plateau"] and summary["right_censored"]
    assert summary["unrecovered_fraction"] == pytest.approx(truth[-1]/truth[0])


def test_spb_dual_observed_alignment_covariance_and_invalid_support():
    record = native([1., 2., 3., 4.], [2., 2., 2., 2.])
    record.update(reference_time_s=np.array([1., 2.01, 3., 4.]),
                  reference=np.array([1., 1., 0., 1.]),
                  sample_variance=np.full(4, .04), reference_variance=np.full(4, .01),
                  sample_reference_covariance=np.full(4, .01), clipped=np.array([False, False, False, True]))
    ratio = detector_ratio(record, mode="dual")
    assert ratio["ratio"][0] == 2.
    assert ratio["variance"][0] == pytest.approx(.04)
    assert np.isnan(ratio["ratio"][1:]).all()
    assert ratio["quality_flags"][1] & Quality.UNMATCHED_REFERENCE
    assert ratio["quality_flags"][2] & Quality.INVALID_REFERENCE
    assert ratio["quality_flags"][3] & Quality.CLIPPED
    record["reference"] = np.array([])
    record.pop("reference_time_s")
    assert np.isnan(detector_ratio(record, mode="dual")["ratio"]).all()


def test_spb_single_uses_complete_sequence_blank_and_separate_baseline():
    blank = native([1., 2., 3.], [2., 4., 8.])
    record = native([10., 20., 30.], [1., 2., 4.])
    baseline = native([0.], [1.])
    result = process_block(record, baseline, mode="single", pump_time_s=9., blank=blank)
    np.testing.assert_allclose(result["delta_absorbance"], 0.)
    np.testing.assert_allclose(result["absorbance"], -np.log10(.5))
    blank["scan_index"] = np.array([0, 1, 9])
    missing = process_block(record, baseline, mode="single", pump_time_s=9., blank=blank)
    assert np.isnan(missing["delta_absorbance"][-1])
    with pytest.raises(ValueError, match="complete compatible"):
        process_block(record, baseline, mode="single", pump_time_s=9.)


def test_spb_baseline_does_not_become_absolute_balance_and_no_direction_crossing():
    record = native([1.], [4.])
    baseline = native([-1.], [2.])
    result = process_block(record, baseline, mode="dual", pump_time_s=0.)
    assert result["ratio"][0] == 4.
    assert result["delta_absorbance"][0] == pytest.approx(-np.log10(2.))
    assert result["absorbance"] is None
    balance = {"wavenumber_cm1": [1945.], "balance": [8.]}
    absolute = process_block(record, baseline, mode="dual", pump_time_s=0., balance=balance)
    assert absolute["absorbance"][0] == pytest.approx(-np.log10(.5))
    baseline["direction"] = [-1]
    assert np.isnan(process_block(record, baseline, mode="dual", pump_time_s=0.)["delta_absorbance"]).all()


def test_spb_processing_cancel_and_bad_covariance():
    record = native([1.], [2.])
    record.update(sample_variance=[1.], reference_variance=[1.], sample_reference_covariance=[2.])
    assert detector_ratio(record, mode="dual")["quality_flags"][0] & Quality.INVALID_UNCERTAINTY
    def cancel():
        raise InterruptedError("Acquisition stopped")
    with pytest.raises(InterruptedError):
        process_block(record, native([-1.], [1.]), mode="dual", pump_time_s=0., cancel=cancel)


def test_spb_long_uptime_preserves_nanosecond_pointwise_offsets():
    record = native([float(2**63)/1e9]*3, [1., 1., 1.])
    record.update(native_sample_ticks=np.array([2**63-1, 2**63, 2**63+1], dtype=np.uint64),
                  pump_timestamp_ticks=np.asarray(2**63, np.uint64), clockbase_hz=1e9)
    result = process_block(record, native([0.], [1.]), mode="dual", pump_time_s=float(2**63)/1e9)
    np.testing.assert_array_equal(result["time_s"], [-1e-9, 0., 1e-9])
    record.update(sample_response_correction_applied=True, sample_latency_s=2e-9)
    corrected = process_block(record, native([0.], [1.]), mode="dual", pump_time_s=float(2**63)/1e9)
    np.testing.assert_allclose(corrected["time_s"], [-3e-9, -2e-9, -1e-9], atol=1e-24)


def test_spb_band_plateau_requires_every_supported_band_and_preserves_residual():
    tracker = PlateauTracker([(1900., 1902.), (1940., 1942.)], relative_tolerance=.01, required_bursts=3)
    def point(a, b, t):
        return {"wavenumber_cm1": [1901., 1941.], "delta_absorbance": [a, b], "time_s": [t, t+.01]}
    tracker.update(point(-.1, -.2, .1), "early")
    tracker.update(point(-.05, -.2, 10.), "late1")
    result = tracker.update(point(-.05, np.nan, 100.), "late2")
    assert not result["reached"]
    for i in range(3):
        result = tracker.update(point(-.05, -.1, 1000.+i*100), f"stable{i}")
    assert result["reached"]
    assert all(b["unrecovered_fraction"] == .5 and b["right_censored"] for b in result["bands"])


def test_spb_native_dtype_values_exact_and_checkpoint_durable(tmp_path):
    store = RunStore(tmp_path / "observation", {"mode": "dual", "condition_id": "77K-Mb-G-S"})
    original = {"timestamps": np.array([2**63+1, 2**63+2], np.uint64),
                "voltage": np.array([np.nan, np.inf, -0.], np.float64),
                "dio": np.array([0, 2**31], np.uint32)}
    store.save_chunk("early", original)
    store.append_event("pump_intent", {"authorized_count": 1})
    store.checkpoint({"pump_epoch": {"event_id": "optical-1", "clock_id": "clock-1"}})
    loaded = load_run(store.path, "dual", "77K-Mb-G-S")
    assert loaded["status"] == "incomplete"
    for key, value in next(iter_chunks(store.path)).items():
        assert value.dtype == original[key].dtype
        assert value.tobytes() == original[key].tobytes()
    with pytest.raises(FileExistsError):
        store.save_chunk("early", original)
    with pytest.raises(ValueError, match="Incompatible mode"):
        load_run(store.path, "single")
    store.finalize("interrupted", reason="Operator stopped")
    assert load_run(store.path)["status"] == "interrupted"
    assert list((store.path / "checkpoints").iterdir())


def test_spb_torn_journal_never_invents_completion(tmp_path):
    store = RunStore(tmp_path / "run", {"mode": "single"})
    store.append_event("pump_intent", {"authorized_count": 1})
    with (store.path / "events.jsonl").open("ab") as stream:
        stream.write(b'{"sequence":2')
    loaded = load_run(store.path)
    assert loaded["status"] == "incomplete" and loaded["journal_errors"]
    with pytest.raises(ValueError, match="Interrupted journal"):
        RunStore(store.path, {}, create=False)


def test_spb_storage_failure_and_paths_are_not_silent(tmp_path, monkeypatch):
    store = RunStore(tmp_path / "run", {"mode": "single"})
    with pytest.raises(ValueError, match="stable identifier"):
        store.save_chunk("../escape", {"x": [1.]})
    def fail(*args, **kwargs):
        raise OSError("Disk full")
    monkeypatch.setattr("control_app.measurement_modules.single_pump_scan_burst.persistence.os.fsync", fail)
    with pytest.raises(OSError, match="Disk full"):
        store.save_chunk("failed", {"x": [1.]})
    assert load_run(store.path)["chunks"] == []
    assert (store.path / "chunks" / "failed.npz").exists()
    assert compatibility_conflicts({"condition": "old"}, {"condition": "new"}) == ["condition: saved 'old'; requested 'new'"]


def test_spb_new_pump_reuses_neither_sibling_state_nor_ambiguous_intent(tmp_path):
    identity = {key: key+"-1" for key in ("condition_id", "sample_id", "preparation_id", "accepted_state_id", "cell_id", "position_id")}
    prior = RunStore(tmp_path/"experiment"/"single"/"first", {"mode": "single", "settings": identity})
    next_path = tmp_path/"experiment"/"dual"/"next"
    assert_unused_sample_state(next_path, identity)
    prior.append_event("pump_intent", {"automatic_retry_allowed": False})
    with pytest.raises(ValueError, match="already has a retained pump intent"):
        assert_unused_sample_state(next_path, identity)
    assert_unused_sample_state(next_path, {**identity, "accepted_state_id": "newly-qualified-state-2"})
