"""Runner integration tests using virtual clocks and actual native retention."""
from copy import deepcopy
from pathlib import Path
import threading

import numpy as np
import pytest

from control_app.measurement_host import ContextFactory
from control_app.measurement_modules.fixed_wavenumber_kinetics.planner import build_plan
from control_app.measurement_modules.fixed_wavenumber_kinetics.runner import Runner
from control_app.measurement_modules.fixed_wavenumber_kinetics.simulation import SimulatedDevices, simulation_profile
from control_app.measurement_modules.fixed_wavenumber_kinetics.persistence import load_run, read_native_chunk


def scenario(tmp_path, mode="dual", faults=None, settings=None):
    profile = simulation_profile(mode)
    profile["settings"].update(settings or {})
    profile["configuration"]["fixed_point_simulation"] = faults or {}
    context = ContextFactory(configuration_provider=lambda: profile["configuration"],
        save_root_provider=lambda: tmp_path).for_experiment("fixed_wavenumber_kinetics").for_mode(mode)
    plan = build_plan(profile["settings"], profile["configuration"], profile["evidence"])
    assert plan.ready, (plan.validation_errors, plan.readiness_items)
    operation = context.begin_operation(settings=profile["settings"], hardware=False)
    devices = []
    def factory(context, op):
        device = SimulatedDevices(context, op)
        devices.append(device)
        return device
    return Runner(context, device_factory=factory), operation, plan, devices


def test_fixed_point_native_finite_count_original_large_epoch_and_analysis(tmp_path):
    runner, op, plan, devices = scenario(tmp_path)
    record = runner.run(op, plan)
    assert record["status"] == "complete", record.get("error", record.get("analysis_error"))
    assert devices[0].dispatched == 1
    event = record["events"][0]
    assert event["original_pump_timestamp"] > 2**53
    assert event["pump_timestamps"] == [event["original_pump_timestamp"]]
    assert event["baseline"]["stationary"] and event["reset"]["accepted"]
    loaded = load_run(op.output_path)
    first = read_native_chunk(op.output_path, loaded["native_chunks"][0])
    assert first["sample"]["timestamp"].dtype == np.uint64
    assert int(first["sample"]["timestamp"][0]) == devices[0].epoch
    assert np.array_equal(first["sample"]["y"], np.zeros(200))
    assert "analysis" in record


@pytest.mark.parametrize("fault, phrase", [
    ({"baseline_drift_per_s": 1.}, "baseline"),
    ({"missing_reference": True}, "baseline"),
    ({"clipped": True}, "baseline"),
    ({"unlocked": True}, "baseline"),
    ({"missing_marker": True}, "pump count"),
    ({"extra_marker": True}, "finite count"),
    ({"timing_error": True}, "timing table"),
])
def test_fixed_point_faults_preserve_without_biological_retry(tmp_path, fault, phrase):
    runner, op, plan, devices = scenario(tmp_path, faults=fault)
    result = runner.run(op, plan)
    assert result["status"] == "failed"
    assert phrase in result["error"].lower()
    assert result["preservation_verified"] and result["restoration"]["safe_verified"]
    assert devices[0].dispatched <= 1
    assert Path(op.output_path, "run.json").exists()


@pytest.mark.parametrize("kind", ["blank", "preliminary"])
def test_fixed_point_no_pump_controls(tmp_path, kind):
    runner, op, plan, devices = scenario(tmp_path, mode="single")
    result = runner.run(op, plan, kind=kind)
    assert result["status"] == "complete", result.get("error", result.get("analysis_error"))
    assert devices[0].dispatched == 0
    assert result["events"][0]["pump_timestamps"] == []


def test_fixed_point_reset_failure_inhibits_later_event(tmp_path):
    runner, op, plan, devices = scenario(tmp_path, faults={"recovery_tau_s": 1000., "amplitude": .05},
        settings={"technical_repetitions": 2, "event_budget": 2})
    result = runner.run(op, plan)
    assert devices[0].dispatched == 1
    assert result["status"] == "failed"
    assert "reset criterion" in result["error"]


def test_fixed_point_known_recovery_allows_second_finite_event(tmp_path):
    runner, op, plan, devices = scenario(tmp_path, settings={"technical_repetitions": 2, "event_budget": 2})
    result = runner.run(op, plan)
    assert result["status"] == "complete", result.get("error")
    assert devices[0].dispatched == 2
    assert result["events"][1]["equivalent_state"]
    assert result["events"][1]["original_pump_timestamp"] > result["events"][0]["original_pump_timestamp"]
    first, second = result["events"]
    assert first["first_native_timestamp"] < first["last_native_timestamp"] < second["first_native_timestamp"]
    expected_gap = max(0., (second["first_native_timestamp"]-first["last_native_timestamp"])/210000000.-1./1000.)
    assert second["inter_block_dead_time_s"] == pytest.approx(expected_gap)


@pytest.mark.parametrize("stage", ["configuration", "acknowledged timing-table upload", "acquisition", "analysis"])
def test_fixed_point_cancel_at_stages_retains_cleanup(tmp_path, stage):
    runner, op, plan, devices = scenario(tmp_path)
    cancel = threading.Event()
    def progress(event):
        if event["stage"] == stage:
            cancel.set()
    result = runner.run(op, plan, cancel=cancel, progress=progress)
    assert result["status"] == "stopped", result
    assert result["preservation_verified"] and result["restoration"]["safe_verified"]
    assert Path(op.output_path, "run.json").exists()


def test_fixed_point_cleanup_failure_takes_precedence_over_cancel(tmp_path):
    runner, op, plan, devices = scenario(tmp_path, faults={"cleanup_failure": True})
    cancel = threading.Event()
    result = runner.run(op, plan, cancel=cancel,
        progress=lambda event: cancel.set() if event["stage"] == "acquisition" else None)
    assert result["status"] == "cleanup_failed"
    assert result["acquisition_status"] == "stopped"
    assert result["preservation_verified"]


def test_fixed_point_long_capture_poll_boundaries_are_native(tmp_path):
    runner, op, plan, devices = scenario(tmp_path, settings={"post_observation_s": 12., "chunk_duration_s": .137})
    result = runner.run(op, plan)
    assert result["status"] == "complete", result.get("error")
    sample_chunks = [read_native_chunk(op.output_path, ref)["sample"]["timestamp"] for ref in result["native_chunks"]]
    counts = [len(chunk) for chunk in sample_chunks]
    assert max(counts) <= 138
    combined = np.concatenate(sample_chunks)
    assert np.all(np.diff(combined) == 210000)
    assert not result["quality_flags"]


def test_fixed_point_storage_failure_is_preservation_failure(tmp_path, monkeypatch):
    from control_app.measurement_modules.fixed_wavenumber_kinetics import persistence
    runner, op, plan, devices = scenario(tmp_path)
    def fail(*args, **kwargs):
        raise OSError("injected disk full")
    monkeypatch.setattr(persistence, "save_run", fail)
    result = runner.run(op, plan)
    assert result["status"] == "preservation_failed"
    assert not result["preservation_verified"]
    assert result["restoration"]["safe_verified"]
    assert list(Path(op.output_path, "native").glob("*.npz"))


def test_fixed_point_chunk_failure_does_not_claim_preservation(tmp_path, monkeypatch):
    from control_app.measurement_modules.fixed_wavenumber_kinetics import persistence
    runner, op, plan, devices = scenario(tmp_path)
    monkeypatch.setattr(persistence.NativeChunkWriter, "append",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("native disk full")))
    result = runner.run(op, plan)
    assert result["status"] == "preservation_failed"
    assert not result["preservation_verified"]
    assert result["restoration"]["safe_verified"]
    assert "native disk full" in result["native_preservation_error"]
    assert devices[0].dispatched == 0


def test_fixed_point_progress_callback_failure_cannot_bypass_cleanup(tmp_path):
    runner, op, plan, devices = scenario(tmp_path)
    def fail(event):
        raise RuntimeError("broken view")
    result = runner.run(op, plan, progress=fail)
    assert result["status"] == "complete"
    assert result["restoration"]["safe_verified"] and result["preservation_verified"]
    assert result["presentation_errors"]


def test_fixed_point_off_band_simulator_has_no_default_pump_response(tmp_path):
    runner, op, plan, devices = scenario(tmp_path, settings={"positions": [{"wavenumber_cm1": 1930., "label": "off_band", "selection_record_id": "SYNTHETIC-selection", "band_assignment": ""}]})
    result = runner.run(op, plan)
    assert result["status"] == "complete", result.get("error")
    assert devices[0].dispatched == 1
    assert result["events"][0]["reset"]["observed_fraction_from_baseline"] < 1e-12


def test_fixed_point_analysis_parents_record_absolute_native_paths(tmp_path):
    runner, op, plan, _ = scenario(tmp_path, mode="single")
    blank = runner.run(op, plan, kind="blank")
    runner2, op2, plan2, _ = scenario(tmp_path, mode="single")
    sample = runner2.run(op2, plan2, kind="preliminary", blank=blank)
    assert sample["analysis_inputs"]["blank"]["run_id"] == blank["run_id"]
    assert Path(sample["analysis_inputs"]["blank"]["native_path"]).is_absolute()
    assert Path(sample["analysis_inputs"]["blank"]["native_path"]).exists()


def test_fixed_point_cleanup_high_level_does_not_invent_pump_epoch(tmp_path):
    runner, op, plan, _ = scenario(tmp_path)
    class HighTailDevices(SimulatedDevices):
        def cleanup(self, retain_tail=None):
            if self.streaming and retain_tail is not None:
                chunk = self.read(.001)
                chunk["timing"]["dio"][:] = np.uint64(1 << self.resolved["pump_marker_bit"])
                retain_tail(chunk)
            return super().cleanup(retain_tail=None)
    runner.device_factory = HighTailDevices
    cancel = threading.Event()
    result = runner.run(op, plan, cancel=cancel,
        progress=lambda event: cancel.set() if event["stage"] == "acquisition" else None)
    event = result["events"][0]
    assert result["status"] == "stopped"
    assert event["original_pump_timestamp"] is None
    assert event["pump_timestamps"] == []
    assert event["unqualified_pump_marker_candidates"][0]["timestamp"] > 2**53
    assert "missing_observed_pump_epoch" in result["quality_flags"]
    assert result["preservation_verified"]
    # Reprocessing retained native data must also decline a pump-relative fit.
    from control_app.measurement_modules.fixed_wavenumber_kinetics.processing import analyze_run
    analysis = analyze_run(result)
    assert analysis["events"][0]["recovery_fit"]["status"] == "unresolved_time_zero"


def test_fixed_point_live_marker_lists_and_device_epoch_precision(tmp_path):
    runner, op, plan, _ = scenario(tmp_path)
    previews = []
    result = runner.run(op, plan, progress=lambda event: previews.append(event["preview"]) if "preview" in event else None)
    assert result["status"] == "complete"
    assert previews
    assert all(isinstance(p["analysis"]["events"][0]["measured_pump_time_s"], list) for p in previews)
    pumped = [p["analysis"]["events"][0] for p in previews if p["analysis"]["events"][0]["measured_pump_time_s"]]
    assert pumped and pumped[0]["measured_pump_time_s"] == [0.]
    times = np.asarray(pumped[0]["time_s"])
    assert np.allclose(np.diff(times), .001, rtol=0, atol=1e-14)
