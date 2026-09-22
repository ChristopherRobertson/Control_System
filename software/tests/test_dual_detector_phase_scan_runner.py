"""Session review, frozen baseline settings and native persistence without hardware."""
from copy import deepcopy
from dataclasses import replace
import json

import numpy as np
import pytest

from control_app.workflows.dual_detector_phase_scan import (
    DualHF2Capabilities, DualDetectorPhaseScanSettings, build_dual_detector_phase_scan_plan,
)
from control_app.workflows.dual_detector_phase_scan_data import align_detector_spectrum, load_dual_run
from control_app.workflows.dual_detector_phase_scan_runner import DualDetectorPhaseScanRunner
from control_app.workflows.phase_scan_data import load_native
from control_app.workflows.regular_phase_scan import build_regular_phase_scan_plan


def plan():
    return build_dual_detector_phase_scan_plan(DualDetectorPhaseScanSettings(
        start_wavenumber_cm1=2000, stop_wavenumber_cm1=1998,
        scan_speed_cm1_s=1000, phase_delay_us=500))


def synthetic_spectrum(event):
    wn = np.array([2000., 1999., 1998.])
    physical = 10+(event.phase_delay_us or 0)*1e-6+np.array([0., .001, .002])
    common = np.array([2., 3., 4.])*(1+.07*event.scan_index)
    ratio = .5*10**(-.1 if event.pump_enabled else 0.)
    return align_detector_spectrum(physical, common*ratio, wn, physical, common, wn,
        sample_filter_delay_s=0., reference_filter_delay_s=0.,
        metadata={"optical_valid": True, "wavenumber_basis": "measured", "pump_time_basis": "electrical_sync"},
        pump_time_s=10. if event.pump_enabled else None)


class SimulatedAcquirer:
    def __init__(self, *, fault=None, cleanup_fault=False, split=False, readback=None):
        self.fault, self.cleanup_fault, self.split = fault, cleanup_fault, split
        self.readback = readback or {"hf2li_device": "simulated",
            "hf2li_resolution": {"actual": {"sample": {"order": 4}, "reference": {"order": 4}}}}
        self.partial_blocks, self.calls = [], []

    def resolve_plan(self, requested): return requested
    def authorize(self, allowed): self.authorized = allowed
    def prepare(self, settings, store, cancel):
        self.calls.append("prepare")
        return deepcopy(self.readback)
    def prepare_blocks(self, requested, events, cancel):
        self.calls.append("preflight")
        return [events[:1], events[1:]] if self.split else [events]
    def capture_block(self, events, cancel):
        self.calls.append("capture")
        raw = {"sample_ticks": np.array([2**60, 2**60+1], np.uint64),
               "reference_ticks": np.array([2**60+2, 2**60+3], np.uint64), "read_after_sequence": True}
        if self.fault is not None:
            self.partial_blocks.append(raw)
            raise self.fault
        return raw, [(event, synthetic_spectrum(event)) for event in events]
    def close(self):
        self.calls.append("close")
        if self.cleanup_fault:
            raise RuntimeError("simulated restoration failure")


def reviewed_runner(tmp_path):
    runner = DualDetectorPhaseScanRunner(SimulatedAcquirer)
    result = runner.execute("test", tmp_path, plan())
    runner.mark_preliminary_reviewed()
    return runner, result


def test_preliminary_without_blank_then_reviewed_pumped_run_and_saved_loading(tmp_path):
    runner, preliminary = reviewed_runner(tmp_path)
    assert runner.background is None and runner.preliminary_reviewed
    assert preliminary["display_mode"] == "sample_reference_ratio"
    assert np.allclose(preliminary["values"], .5)
    assert (preliminary["path"]/"processed"/"preliminary.csv").exists()
    result = runner.execute("run", tmp_path, plan())
    surface = load_dual_run(result["path"])
    assert "absorbance" not in surface
    values = surface["delta_absorbance"]
    assert np.allclose(values[np.isfinite(values)], .1)
    native = load_native(result["path"]/"raw"/"acquisition.npz")
    assert native["native"]["unpumped_baseline"]["reviewed"]
    assert native["native"]["unpumped_baseline"]["source"] == str(preliminary["path"])
    assert native["native"]["blocks"][0]["reference_ticks"].dtype == np.uint64


def test_pump_accepts_compatible_sample_without_review_and_retains_optional_reviews(tmp_path):
    runner = DualDetectorPhaseScanRunner(SimulatedAcquirer)
    runner.execute("test", tmp_path, plan())
    result = runner.execute("run", tmp_path, plan())
    native = load_native(result["path"]/"raw"/"acquisition.npz")
    assert not native["native"]["unpumped_baseline"]["reviewed"]
    runner.mark_preliminary_reviewed()
    changed = build_dual_detector_phase_scan_plan(replace(plan().settings, pump_repetition_rate_hz=5))
    assert runner.baseline_conflicts(changed)
    assert not runner.preliminary_reviewed
    assert runner.baseline_conflicts(plan()) == []
    runner.mark_preliminary_reviewed()
    assert len(list(runner.preliminary["path"].glob("review*.json"))) == 2


def test_new_run_clears_baseline_without_touching_saved_records(tmp_path):
    runner, result = reviewed_runner(tmp_path)
    runner.invalidate_background()
    assert runner.preliminary is None and not runner.preliminary_reviewed
    assert (result["path"]/"raw"/"acquisition.npz").exists()


def test_single_detector_plan_and_blank_workflow_are_rejected(tmp_path):
    runner = DualDetectorPhaseScanRunner(SimulatedAcquirer)
    with pytest.raises(ValueError, match="single-detector"):
        runner.execute("test", tmp_path, build_regular_phase_scan_plan())
    with pytest.raises(ValueError, match="only"):
        runner.execute("background", tmp_path, plan())
    with pytest.raises(ValueError, match="incompatible"):
        runner.load_background(tmp_path)


@pytest.mark.parametrize("fault,cleanup,expected", [
    (InterruptedError("simulated abort"), False, "ABORTED"),
    (InterruptedError("simulated abort"), True, "FAILED_SAFE_STATE_UNVERIFIED"),
    (RuntimeError("simulated loss"), False, "INCOMPLETE"),
    (None, True, "FAILED_SAFE_STATE_UNVERIFIED"),
])
def test_partial_and_restoration_failure_records_persist(tmp_path, fault, cleanup, expected):
    acquirer = SimulatedAcquirer(fault=fault, cleanup_fault=cleanup)
    runner = DualDetectorPhaseScanRunner(lambda: acquirer)
    progress = []
    with pytest.raises(InterruptedError if expected == "ABORTED" else RuntimeError) as caught:
        runner.execute("test", tmp_path, plan(), progress=progress.append)
    run_path = next(tmp_path.glob("Dual-Detector Phase Scan/*/*"))
    assert json.loads((run_path/"result.json").read_text())["status"] == expected
    native = load_native(run_path/"raw"/"acquisition.npz")
    assert native["native"]["partial_blocks"] if fault else native["records"]
    assert acquirer.calls.count("close") == 1
    assert runner.preliminary is None and not runner._lock.locked()
    if expected == "ABORTED":
        assert str(caught.value).startswith("Acquisition stopped. Data: ")
        assert str(run_path) in str(caught.value)
    elif cleanup:
        assert str(caught.value).startswith("Safe shutdown or restoration failed:")
    assert any(message.startswith("Preparing one continuous sequence") for message in progress)
    assert not any(message.startswith("Acquiring ") for message in progress)
    assert progress[-2:] == ["Restoring safe idle and instrument settings…", "Saving available native records…"]


def test_cancelled_dual_save_failure_remains_a_failure(tmp_path, monkeypatch):
    from control_app.workflows.dual_detector_phase_scan_data import DualScanStore
    acquirer = SimulatedAcquirer(fault=InterruptedError("operator stopped"))
    runner = DualDetectorPhaseScanRunner(lambda: acquirer)
    def fail_save(*args, **kwargs):
        raise OSError("simulated disk failure")
    monkeypatch.setattr(DualScanStore, "save_block", fail_save)
    with pytest.raises(RuntimeError, match="simulated disk failure"):
        runner.execute("test", tmp_path, plan())
    assert json.loads(next(tmp_path.rglob("result.json")).read_text())["status"] == "INCOMPLETE"
    assert acquirer.calls[-1] == "close"


@pytest.mark.parametrize("mode", ["single", "dual"])
@pytest.mark.parametrize("notification", ["Restoring safe idle", "Saving available native"])
@pytest.mark.parametrize("cleanup_fault", [False, True])
def test_failed_preservation_progress_does_not_interrupt_cleanup_or_retention(tmp_path, mode, notification, cleanup_fault):
    from control_app.workflows.regular_phase_scan_runner import RegularPhaseScanRunner
    from test_regular_phase_scan_data import SimulatedAcquirer as SingleAcquirer, plan as single_plan
    if mode == "single":
        acquirer = SingleAcquirer(blank=True, fault=InterruptedError("operator stopped"),
                                  cleanup_fault=cleanup_fault)
        runner = RegularPhaseScanRunner(lambda: acquirer)
        kind, requested = "background", single_plan()
    else:
        acquirer = SimulatedAcquirer(fault=InterruptedError("operator stopped"), cleanup_fault=cleanup_fault)
        runner = DualDetectorPhaseScanRunner(lambda: acquirer)
        kind, requested = "test", plan()
    failed_notifications = []
    def progress(message):
        if message.startswith(notification):
            failed_notifications.append(message)
            raise RuntimeError("simulated deleted Qt worker")
    with pytest.raises(RuntimeError if cleanup_fault else InterruptedError) as caught:
        runner.execute(kind, tmp_path, requested, progress=progress)
    assert len(failed_notifications) == 1
    assert acquirer.calls.count("close") == 1
    raw_path = next(tmp_path.rglob("acquisition.npz"))
    assert load_native(raw_path)["native"]["partial_blocks"]
    outcome = json.loads(next(tmp_path.rglob("result.json")).read_text())
    assert outcome["status"] == ("FAILED_SAFE_STATE_UNVERIFIED" if cleanup_fault else "ABORTED")
    assert outcome["safe_shutdown_and_restoration_verified"] is (not cleanup_fault)
    assert "simulated deleted Qt worker" not in str(caught.value)
    assert str(caught.value).startswith("Safe shutdown or restoration failed:" if cleanup_fault else "Acquisition stopped. Data:")
    assert not runner._lock.locked()


def test_reference_actual_setting_change_prevents_pump_and_invalidates_review(tmp_path):
    runner, _ = reviewed_runner(tmp_path)
    changed = SimulatedAcquirer(readback={"hf2li_device": "simulated", "hf2li_resolution": {
        "actual": {"sample": {"order": 4}, "reference": {"order": 3}}}})
    runner.acquirer_factory = lambda: changed
    with pytest.raises(RuntimeError, match="incompatible after instrument"):
        runner.execute("run", tmp_path, plan())
    assert "capture" not in changed.calls and not runner.preliminary_reviewed


def test_capability_discovery_failure_revokes_dual_start_authority():
    def failed(): raise RuntimeError("device disconnected")
    runner = DualDetectorPhaseScanRunner(SimulatedAcquirer, capabilities=replace(DualHF2Capabilities(), verified=True),
                                         capability_provider=failed)
    with pytest.raises(RuntimeError, match="disconnected"):
        runner.refresh_capabilities()
    assert not runner.capabilities.verified


def test_validated_balance_is_frozen_retained_and_enables_absolute_display(tmp_path):
    from test_dual_detector_phase_scan_data import calibration
    balance = calibration(plan())
    runner = DualDetectorPhaseScanRunner(SimulatedAcquirer, calibration_provider=lambda requested: balance)
    preliminary = runner.execute("test", tmp_path, plan())
    assert preliminary["display_mode"] == "absorbance"
    assert preliminary["experiment_contract"]["channel_balance_calibration"] == balance.contract()
    assert runner.preliminary_matches(plan())
    runner.mark_preliminary_reviewed()
    result = runner.execute("run", tmp_path, plan())
    surface = load_dual_run(result["path"])
    assert "absorbance" in surface
    raw = load_native(result["path"]/"raw"/"acquisition.npz")
    np.testing.assert_array_equal(raw["native"]["channel_balance"]["response_ratio"], balance.response_ratio)
    runner.calibration_provider = lambda requested: replace(balance, bundle_id="SIMULATED-CHANGED")
    assert runner.baseline_conflicts(plan()) and not runner.preliminary_reviewed


def test_saved_plan_selects_explicit_balance_and_execution_rejects_changes(tmp_path):
    from test_dual_detector_phase_scan_data import calibration
    balance = calibration(plan())
    seen = []
    def provider(requested):
        seen.append(deepcopy(requested.channel_balance_calibration))
        return balance
    runner = DualDetectorPhaseScanRunner(SimulatedAcquirer, calibration_provider=provider)
    runner.requested_channel_balance = {"bundle_id": balance.bundle_id}
    requested = runner.configuration_preview(plan().settings)
    assert seen[-1] == {"bundle_id": balance.bundle_id}
    assert requested.channel_balance_calibration == balance.contract()
    original_contract = deepcopy(requested.channel_balance_calibration)
    result = runner.execute("test", tmp_path, requested)
    assert result["plan"].channel_balance_calibration == original_contract
    runner.calibration_provider = lambda requested: replace(balance, source="changed-source")
    with pytest.raises(RuntimeError, match="absent or changed"):
        runner.execute("test", tmp_path, requested)
    assert requested.channel_balance_calibration == original_contract


def test_explicit_unavailable_balance_is_not_silently_replaced():
    runner = DualDetectorPhaseScanRunner(SimulatedAcquirer, calibration_provider=lambda requested: None)
    runner.requested_channel_balance = {"bundle_id": "absent-bundle"}
    with pytest.raises(ValueError, match="absent or changed"):
        runner.configuration_preview(plan().settings)
