"""Sequence-position normalization and app lifecycle, using synthetic CH1 data."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json

import numpy as np
import pytest

from control_app.workflows.phase_scan_data import Spectrum, load_native, save_native
from control_app.workflows.phase_scan import PhaseScanEvent
from control_app.workflows.regular_phase_scan import RegularPhaseScanSettings, build_regular_phase_scan_plan
from control_app.workflows.regular_phase_scan_data import (
    BackgroundSequence, RegularScanStore, compatibility_conflicts, experiment_contract,
    load_background_sequence, load_regular_run, reconstruct_sequence,
    save_regular_reconstruction_csv, stable_device_configuration, validate_blank_sequence,
)
from control_app.workflows.regular_phase_scan_runner import RegularPhaseScanRunner


def plan():
    return build_regular_phase_scan_plan(RegularPhaseScanSettings(
        start_wavenumber_cm1=2000, stop_wavenumber_cm1=1998,
        scan_speed_cm1_s=1000, phase_delay_us=500))


def synthetic_spectrum(event, blank=False):
    wn = np.array([2000., 1999., 1998.])
    age = (event.phase_delay_us or 0)*1e-6 + np.array([0., .001, .002])
    intensity = np.array([2., 3., 4.])*(1 + .07*event.scan_index)
    baseline = .1 + (2000-wn)*.01
    absorption = baseline + (20*age if event.pump_enabled else 0)
    return Spectrum(wn, intensity if blank else intensity*10**(-absorption), None,
                    10 + age, 10. if event.pump_enabled else None,
                    {"optical_valid": True, "wavenumber_basis": "measured",
                     "pump_time_basis": "electrical_sync", "detector_mode": "single_ch1_buffer_blank",
                     "detector_input": "HF2LI CH1 SIG IN +", "record_role": "buffer_blank" if blank else "sample"})


READBACK = {"hf2li_device": "test-device", "hf2li_detector_settings": {"order": 4, "rate": 28782.894736842107},
            "hf2li_resolution": {"requested": {}, "selected": {"order": 4}, "actual": {"order": 4}}}


class SimulatedAcquirer:
    def __init__(self, *, blank=False, fault=None, cleanup_fault=False, split=False, mutate=None, readback=None):
        self.blank, self.fault, self.cleanup_fault = blank, fault, cleanup_fault
        self.split, self.mutate = split, mutate
        self.readback = deepcopy(READBACK if readback is None else readback)
        self.calls, self.partial_blocks = [], []
        self.closed = False

    def resolve_plan(self, requested):
        return requested

    def authorize(self, allowed):
        self.authorized = allowed

    def prepare(self, settings, store, cancel):
        self.calls.append("prepare")
        return self.readback

    def prepare_blocks(self, requested, events, cancel):
        self.calls.append("preflight")
        self.events = events
        return [events[:4], events[4:]] if self.split else [events]

    def capture_block(self, block, cancel):
        self.calls.append("capture")
        native = {"ticks": np.array([2**60, 2**60+1], dtype=np.uint64), "read_after_sequence": True}
        if self.fault is not None:
            self.partial_blocks.append(native)
            raise self.fault
        records = [(event, synthetic_spectrum(event, self.blank)) for event in block]
        if self.mutate:
            records = self.mutate(records)
        return native, records

    def close(self):
        self.calls.append("close")
        self.closed = True
        if self.cleanup_fault:
            raise RuntimeError("restoration did not verify")


def blank_runner(tmp_path):
    acquirer = SimulatedAcquirer(blank=True)
    runner = RegularPhaseScanRunner(lambda: acquirer)
    runner.execute("background", tmp_path, plan())
    return runner


def reviewed_runner(tmp_path):
    runner = blank_runner(tmp_path)
    runner.acquirer_factory = SimulatedAcquirer
    runner.execute("test", tmp_path, plan())
    runner.mark_preliminary_reviewed()
    return runner


def test_full_blank_preserves_signed_phase_schedule_but_inhibits_every_pump(tmp_path):
    requested = plan()
    acquirer = SimulatedAcquirer(blank=True)
    runner = RegularPhaseScanRunner(lambda: acquirer)
    result = runner.execute("background", tmp_path, requested)
    assert len(acquirer.events) == requested.total_scans > 16
    assert all(not event.pump_enabled for event in acquirer.events)
    assert [event.phase_delay_us for event in acquirer.events] == [requested.event_at(i).phase_delay_us for i in range(requested.total_scans)]
    assert acquirer.calls == ["prepare", "preflight", "capture", "close"]
    assert runner.background_matches(requested)
    manifest = json.loads((result["path"] / "run.json").read_text())
    assert manifest["experiment_contract"]["fire_to_qswitch_us"] == 250.


def test_custom_window_survives_acquisition_reconstruction_and_loading(tmp_path):
    requested = build_regular_phase_scan_plan(replace(plan().settings, pre_pump_ms=2, post_pump_ms=8))
    runner = RegularPhaseScanRunner(lambda: SimulatedAcquirer(blank=True))
    runner.execute('background', tmp_path, requested)
    assert not runner.background_matches(plan())
    runner.acquirer_factory = SimulatedAcquirer
    runner.execute('test', tmp_path, requested)
    runner.mark_preliminary_reviewed()
    result = runner.execute('run', tmp_path, requested)
    loaded = load_regular_run(result['path'])
    assert loaded['time_s'][0] == pytest.approx(-.002)
    assert loaded['time_s'][-1] == pytest.approx(.008)


def test_derived_acquisition_covers_full_spectrum_before_and_after_pump(tmp_path):
    requested = build_regular_phase_scan_plan(replace(plan().settings,
        pre_pump_ms=1, post_pump_ms=5))
    runner = RegularPhaseScanRunner(lambda: SimulatedAcquirer(blank=True))
    runner.execute('background', tmp_path, requested)
    cropped = build_regular_phase_scan_plan(replace(requested.settings, pre_pump_ms=.5, post_pump_ms=3))
    assert not runner.background_matches(cropped)
    assert not runner.background_matches(cropped.settings)
    assert cropped.total_scans < requested.total_scans
    runner.acquirer_factory = SimulatedAcquirer
    runner.execute('test', tmp_path, requested)
    runner.mark_preliminary_reviewed()
    result = runner.execute('run', tmp_path, requested)
    surface = load_regular_run(result['path'])
    assert np.isfinite(surface['absorbance']).all()
    assert surface['time_s'][0] == pytest.approx(-.001)
    assert surface['time_s'][-1] == pytest.approx(.005)
    assert len(surface['scan_index']) == requested.total_scans


def test_sequence_position_blank_removes_repeatable_drift_and_keeps_separate_delta(tmp_path, monkeypatch):
    runner = reviewed_runner(tmp_path)
    acquirer = SimulatedAcquirer()
    runner.acquirer_factory = lambda: acquirer
    original = RegularScanStore.save_block

    def save_after_close(store, records, **kwargs):
        assert acquirer.closed
        return original(store, records, **kwargs)

    monkeypatch.setattr(RegularScanStore, "save_block", save_after_close)
    result = runner.execute("run", tmp_path, plan())
    r = result["reconstruction"]
    baseline = .1 + (2000-r["wavenumber_cm1"])*.01
    expected = baseline[None, :] + r["time_s"][:, None]*20
    valid = np.isfinite(r["absorbance"])
    np.testing.assert_allclose(r["absorbance"][valid], expected[valid], atol=1e-12)
    np.testing.assert_allclose(r["baseline_absorbance"], baseline, atol=1e-12)
    np.testing.assert_allclose(r["delta_absorbance"][valid], (expected-baseline)[valid], atol=1e-12)
    assert r["background_matching"] == "sequence_position_and_measured_wavelength"
    assert r["baseline_record_id"].endswith("/scan_0000000")
    raw = load_native(result["path"] / "raw" / "acquisition.npz")
    assert len(raw["native"]["background"]["records"]) == plan().total_scans
    assert raw["native"]["blocks"][0]["ticks"].dtype == np.uint64
    assert raw["native"]["hf2li_requested_selected"] == plan().hf2_selection
    assert len(raw["records"]) == plan().total_scans
    assert acquirer.calls.count("capture") == 1
    loaded = load_regular_run(result["path"])
    np.testing.assert_equal(loaded["delta_absorbance"], r["delta_absorbance"])


def test_preliminary_is_unpumped_separate_and_requires_explicit_review(tmp_path):
    runner = blank_runner(tmp_path)
    with pytest.raises(RuntimeError, match="explicitly review"):
        runner.execute("run", tmp_path, plan())
    acquirer = SimulatedAcquirer()
    runner.acquirer_factory = lambda: acquirer
    preliminary = runner.execute("test", tmp_path, plan())
    assert len(acquirer.events) == 1 and not acquirer.events[0].pump_enabled
    assert preliminary["spectrum"].pump_time_s is None
    assert runner.preliminary_matches(plan()) and not runner.preliminary_reviewed
    with pytest.raises(RuntimeError, match="explicitly review"):
        runner.execute("run", tmp_path, plan())
    runner.mark_preliminary_reviewed()
    assert json.loads((preliminary["path"] / "review.json").read_text())["pump_acquisition_authorized"] is False


@pytest.mark.parametrize("changed,field", [
    ({"pump_repetition_rate_hz": 5}, "pump_repetition_rate_hz"),
    ({"phase_delay_us": 1000}, "phase_delay_us"),
    ({"start_wavenumber_cm1": 2001}, "start_wavenumber_cm1"),
    ({"scan_speed_cm1_s": 2000}, "scan_speed_cm1_s"),
])
def test_changed_requested_combination_reports_blank_conflict(tmp_path, changed, field):
    runner = blank_runner(tmp_path)
    altered = build_regular_phase_scan_plan(replace(plan().settings, **changed))
    assert any(field in message for message in runner.background_conflicts(altered))
    with pytest.raises(RuntimeError, match="incompatible"):
        runner.execute("test", tmp_path, altered)


def test_hf2_change_rejected_after_actual_readback_and_preserved(tmp_path):
    runner = blank_runner(tmp_path)
    changed = deepcopy(READBACK)
    changed["hf2li_detector_settings"]["order"] = 2
    acquirer = SimulatedAcquirer(readback=changed)
    runner.acquirer_factory = lambda: acquirer
    with pytest.raises(RuntimeError, match="hf2li_detector_settings.order"):
        runner.execute("test", tmp_path, plan())
    assert "capture" not in acquirer.calls
    result_path = next(tmp_path.rglob("*_test/result.json"))
    assert json.loads(result_path.read_text())["status"] == "INCOMPLETE"
    assert load_native(result_path.parent / "raw/acquisition.npz")["native"]["device_settings"] == changed


def test_saved_blank_roundtrip_preserves_pair_and_reports_incompatibility(tmp_path):
    runner = blank_runner(tmp_path)
    path = runner.background.path
    loaded = load_background_sequence(path, plan())
    assert len(loaded.records) == plan().total_scans
    assert loaded.settings == runner.background.settings
    runner.load_background(path, plan())
    assert not runner.preliminary_reviewed
    with pytest.raises(ValueError, match="scan|phase"):
        load_background_sequence(path, build_regular_phase_scan_plan(replace(plan().settings, phase_delay_us=1000)))


def test_no_artificial_block_splitting(tmp_path):
    runner = blank_runner(tmp_path)
    acquirer = SimulatedAcquirer(split=True)
    runner.acquirer_factory = lambda: acquirer
    with pytest.raises(RuntimeError, match="one continuous acquisition"):
        runner.execute("test", tmp_path, plan())
    assert "capture" not in acquirer.calls and acquirer.closed


@pytest.mark.parametrize("fault,status", [(InterruptedError("aborted"), "ABORTED"), (RuntimeError("lost frame"), "INCOMPLETE")])
def test_partial_native_survives_abort_and_failure(tmp_path, fault, status):
    acquirer = SimulatedAcquirer(blank=True, fault=fault)
    runner = RegularPhaseScanRunner(lambda: acquirer)
    progress = []
    with pytest.raises(InterruptedError if status == "ABORTED" else RuntimeError) as caught:
        runner.execute("background", tmp_path, plan(), progress=progress.append)
    raw = load_native(next(tmp_path.rglob("acquisition.npz")))
    assert raw["records"] == [] and len(raw["native"]["partial_blocks"]) == 1
    assert raw["native"]["partial_blocks"][0]["ticks"].dtype == np.uint64
    assert json.loads(next(tmp_path.rglob("result.json")).read_text())["status"] == status
    assert acquirer.closed and runner.background is None
    if status == "ABORTED":
        assert str(caught.value).startswith("Acquisition stopped. Data: ")
        assert str(next(tmp_path.rglob("result.json")).parent) in str(caught.value)
    assert any(message.startswith("Preparing one continuous sequence") for message in progress)
    assert not any(message.startswith("Acquiring ") for message in progress)
    assert progress[-2:] == ["Restoring safe idle and instrument settings…", "Saving available native records…"]


def test_cancellation_with_restoration_failure_remains_an_error(tmp_path):
    acquirer = SimulatedAcquirer(blank=True, fault=InterruptedError("operator stopped"), cleanup_fault=True)
    runner = RegularPhaseScanRunner(lambda: acquirer)
    with pytest.raises(RuntimeError, match="Safe shutdown or restoration failed") as caught:
        runner.execute("background", tmp_path, plan())
    assert not str(caught.value).startswith("Acquisition stopped.")
    result = json.loads(next(tmp_path.rglob("result.json")).read_text())
    assert result["status"] == "FAILED_SAFE_STATE_UNVERIFIED"
    assert not result["safe_shutdown_and_restoration_verified"]
    assert load_native(next(tmp_path.rglob("acquisition.npz")))["native"]["partial_blocks"]


def test_native_save_failure_after_cancellation_is_not_reported_as_normal_stop(tmp_path, monkeypatch):
    acquirer = SimulatedAcquirer(blank=True, fault=InterruptedError("operator stopped"))
    runner = RegularPhaseScanRunner(lambda: acquirer)
    def fail_save(*args, **kwargs):
        raise OSError("simulated disk failure")
    monkeypatch.setattr(RegularScanStore, "save_block", fail_save)
    with pytest.raises(RuntimeError, match="simulated disk failure"):
        runner.execute("background", tmp_path, plan())
    assert json.loads(next(tmp_path.rglob("result.json")).read_text())["status"] == "INCOMPLETE"
    assert acquirer.closed


def test_restoration_failure_prevents_blank_acceptance_but_keeps_scans(tmp_path):
    acquirer = SimulatedAcquirer(blank=True, cleanup_fault=True)
    runner = RegularPhaseScanRunner(lambda: acquirer)
    with pytest.raises(RuntimeError, match="restoration"):
        runner.execute("background", tmp_path, plan())
    assert len(load_native(next(tmp_path.rglob("acquisition.npz")))["records"]) == plan().total_scans
    assert json.loads(next(tmp_path.rglob("result.json")).read_text())["status"] == "FAILED_SAFE_STATE_UNVERIFIED"
    assert runner.background is None


def test_missing_blank_data_stays_missing_after_reconstruction_and_export(tmp_path):
    runner = reviewed_runner(tmp_path)
    for _, spectrum in runner.background.records:
        spectrum.sample_r[1] = np.nan
    result = runner.execute("run", tmp_path, plan())["reconstruction"]
    assert np.isnan(result["absorbance"][:, 1]).all()
    assert np.isnan(result["delta_absorbance"][:, 1]).all()
    exported = tmp_path / "quantitative.csv"
    save_regular_reconstruction_csv(exported, result)
    assert "nan" in exported.read_text() and "time_from_electrical_pump_sync_s" in exported.read_text()


def test_blank_reordering_is_not_accepted_by_position(tmp_path):
    runner = blank_runner(tmp_path)
    reordered = list(runner.background.records)
    reordered[1], reordered[2] = reordered[2], reordered[1]
    with pytest.raises(ValueError, match="sequence position"):
        validate_blank_sequence(reordered, plan())


def test_hf2_discovery_source_is_not_an_operational_compatibility_gate():
    original = plan()
    same_settings_new_source = replace(original, hf2_selection={**original.hf2_selection, "capability_source": "new discovery UTC"})
    assert compatibility_conflicts(experiment_contract(original), experiment_contract(same_settings_new_source)) == []


def test_loading_retained_phase_analysis_preserves_measured_arrays():
    repo = Path(__file__).resolve().parents[2]
    roots = list((repo / "evidence/experiments/runs/single_detector_ftir_20260906T203723_580408Z/full_phase_sample_10hz_realigned_03").rglob("paired_reconstruction.npz"))
    if not roots:
        pytest.skip("Retained local phase-scan evidence is not distributed with this checkout")
    result = load_regular_run(roots[0])
    assert np.asarray(result["absorbance"]).shape == np.asarray(result["delta_absorbance"]).shape
    assert result["pump_reference_bases"] == ["electrical_sync"]
    original = load_native(roots[0].parent / "absorbance_and_change.npz")
    np.testing.assert_equal(result["delta_absorbance"], original["delta_absorbance"])


def test_import_retained_10hz_blank_uses_actual_cadence_and_full_signed_schedule():
    repo = Path(__file__).resolve().parents[2]
    roots = list((repo / "evidence/experiments/runs/single_detector_ftir_20260906T203723_580408Z/full_phase_blank_10hz_01").rglob("acquisition.npz"))
    if not roots:
        pytest.skip("Retained local phase-scan evidence is not distributed with this checkout")
    requested = build_regular_phase_scan_plan()
    background = load_background_sequence(roots[0], requested)
    assert len(background.records) == 322
    assert background.settings["settings"]["pump_repetition_rate_hz"] == 10.
    assert background.settings["frame_period_s"] == .1
    assert background.device_settings["fire_to_qswitch_us"] == 250.
    assert background.device_settings["hf2li_resolution"]["actual"]["rate_sps"] == 28782.894736842107
    assert background.records[1][0].phase_delay_us == -11000.
    # Legacy nominal 0.3 s request remains intact on disk; the imported
    # in-memory contract uses the recorded effective predivider/cadence.
    saved = json.loads((roots[0].parent.parent / "run.json").read_text())
    assert saved["plan"]["settings"]["rest_period_s"] == .3
    assert background.settings["settings"]["rest_period_s"] == .1
    with pytest.raises(ValueError, match="pump_repetition_rate_hz|frame_period_s"):
        load_background_sequence(roots[0], build_regular_phase_scan_plan(RegularPhaseScanSettings(pump_repetition_rate_hz=5)))
    current = deepcopy(background.device_settings)
    current["capture_window"]["basis"] = requested.capture_window["basis"]
    current["segments"] = [{k: v for k, v in segment.items() if k != "marker_interval_cm1"}
                           for segment in current["segments"]]
    assert compatibility_conflicts(stable_device_configuration(background.device_settings), stable_device_configuration(current)) == []
    current["capture_window"]["duration_s"] *= 2
    assert any("duration_s" in message for message in compatibility_conflicts(
        stable_device_configuration(background.device_settings), stable_device_configuration(current)))


def test_replay_retained_322_scan_sequence_matches_saved_absolute_and_delta():
    repo = Path(__file__).resolve().parents[2]
    evidence = repo / "evidence/experiments/runs/single_detector_ftir_20260906T203723_580408Z"
    sample_paths = list((evidence / "full_phase_sample_10hz_realigned_03").rglob("acquisition.npz"))
    blank_paths = list((evidence / "full_phase_blank_10hz_01").rglob("acquisition.npz"))
    if not sample_paths or not blank_paths:
        pytest.skip("Retained local phase-scan evidence is not distributed with this checkout")
    requested = build_regular_phase_scan_plan()
    background = load_background_sequence(blank_paths[0], requested)
    native = load_native(sample_paths[0])
    records = [(PhaseScanEvent(**row["event"]), Spectrum.from_dict(row["spectrum"])) for row in native["records"]]
    assert len(records) == 322
    for _, spectrum in records:
        # A read-only field-name adaptation mirrors current acquisition metadata;
        # the measured CH1, marker coordinates and pump timestamps are untouched.
        spectrum.metadata["acquisition_settings"] = background.settings
    replay = reconstruct_sequence(records, background, requested)
    saved = load_regular_run(sample_paths[0].parent.parent)
    np.testing.assert_equal(replay["wavenumber_cm1"], saved["wavenumber_cm1"])
    np.testing.assert_equal(replay["time_s"], saved["time_s"])
    np.testing.assert_allclose(replay["absorbance"], saved["absorbance"], atol=1e-14, rtol=0, equal_nan=True)
    np.testing.assert_allclose(replay["delta_absorbance"], saved["delta_absorbance"], atol=1e-14, rtol=0, equal_nan=True)
    assert np.isfinite(replay["absorbance"]).sum() == 32738
    assert np.isnan(replay["absorbance"]).sum() == 174
