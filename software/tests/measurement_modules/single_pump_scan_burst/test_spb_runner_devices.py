"""Injected lifecycle and native timing tests; never connects physical devices."""
from dataclasses import replace
from threading import Event
from datetime import datetime, timezone
from unittest.mock import create_autospec

import numpy as np
import pytest

from control_app.measurement_host.context import ContextFactory
from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError
from control_app.measurement_modules.single_pump_scan_burst.acquisition import (
    ConnectedBurstAdapter, ReadinessError, reconstruct_native, rising_edges,
)
from control_app.measurement_modules.single_pump_scan_burst.persistence import RunStore, load_run
from control_app.measurement_modules.single_pump_scan_burst.planner import compile_plan
from control_app.measurement_modules.single_pump_scan_burst.runner import BurstRunner
from control_app.measurement_modules.single_pump_scan_burst.settings import example_settings
from control_app.measurement_modules.single_pump_scan_burst.simulation import SimulatedBurstAdapter


def plan(mode="dual"):
    return compile_plan(replace(example_settings(mode), early_scan_count=2, later_burst_count=2,
        scans_per_burst=2, final_scan_count=1, first_later_burst_s=.5, observation_limit_s=3.,
        temperature_check_interval_s=.1, preliminary_scan_count=2))


def context(tmp_path, mode="dual", coordinator=None):
    return ContextFactory(save_root_provider=lambda: tmp_path, ownership=coordinator or object()).for_experiment(
        "single_pump_scan_burst").for_mode(mode)


def build(ctx, p, *, progress=None, adapter_kwargs=None):
    operation = ctx.begin_operation(p.settings.to_dict(), hardware=False)
    store = RunStore(operation.output_path, {"mode": p.settings.mode, "condition_id": p.settings.condition_id,
        "settings": p.settings.to_dict()})
    runner = BurstRunner(ctx, p, operation, store=store, progress=progress)
    adapter = SimulatedBurstAdapter(ctx, operation, p, cancel=runner.cancel_event, progress=runner._progress,
                                    store=store, **(adapter_kwargs or {}))
    runner.adapter = adapter
    return runner, adapter


def baselines(ctx, p):
    preliminary = build(ctx, p)[0].prepare("preliminary")
    assert preliminary["complete"], preliminary["error"]
    result = {"preliminary": preliminary}
    if p.settings.mode == "single":
        result["blank"] = build(ctx, p)[0].prepare("baseline")
        assert result["blank"]["complete"], result["blank"]["error"]
        assert "native" not in result["blank"]
    return result


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_injected_full_workflow_has_exactly_one_optical_pump_across_all_blocks(tmp_path, mode):
    p, ctx = plan(mode), context(tmp_path, mode)
    baseline = baselines(ctx, p)
    runner, adapter = build(ctx, p)
    result = runner.run({"accepted": True, "settings": p.settings.to_dict()}, baseline)
    assert result.status == "complete", result.to_dict()
    assert adapter.pump_count == 1
    assert result.epoch["independently_observed"]
    assert len(result.summary["completed_blocks"]) == len(p.blocks)
    retained = load_run(result.output_path)
    assert sum(e["kind"] == "pump_intent" for e in retained["events"]) == 1
    assert sum(e["kind"] == "pump_epoch_observed" for e in retained["events"]) == 1
    assert retained["manifest"]["status"] == "complete"
    assert any("processed" in path for path in retained["chunks"])


def test_ambiguous_epoch_after_emission_is_retained_and_never_repeated(tmp_path):
    p, ctx = plan(), context(tmp_path)
    baseline = baselines(ctx, p)
    runner, adapter = build(ctx, p, adapter_kwargs={"ambiguous_epoch": True})
    result = runner.run({"accepted": True, "settings": p.settings.to_dict()}, baseline)
    assert result.status == "incomplete"
    assert adapter.pump_count == 1 and result.epoch is None
    assert result.native_paths
    with pytest.raises(RuntimeError, match="cannot be repeated"):
        runner.run({"accepted": True}, baseline)
    resumed, hardware = build(ctx, p)
    refusal = resumed.run({"accepted": True, "settings": p.settings.to_dict()}, baseline,
        continuation={"pump_intent": True, "epoch": None})
    assert "Ambiguous" in refusal.error and hardware.pump_count == 0


def test_long_wait_abort_restores_preserves_epoch_and_does_not_repeat_pump(tmp_path):
    p, ctx = plan(), context(tmp_path)
    baseline = baselines(ctx, p)
    runner, adapter = build(ctx, p)
    runner.callback = lambda item: runner.cancel() if item["stage"] == "recovery_wait" else None
    result = runner.run({"accepted": True, "settings": p.settings.to_dict()}, baseline)
    assert result.status == "stopped", result.to_dict()
    assert adapter.pump_count == 1
    assert adapter.events[-1][0] == "restore"
    assert load_run(result.output_path)["checkpoint"]["state"]["epoch"]["independently_observed"]


@pytest.mark.parametrize("stage", ["configuration", "upload", "analysis"])
def test_abort_during_preparation_programming_and_processing(tmp_path, stage):
    p, ctx = plan(), context(tmp_path)
    baseline = baselines(ctx, p)
    runner, adapter = build(ctx, p)
    runner.callback = lambda item: runner.cancel() if item["stage"] == stage else None
    result = runner.run({"accepted": True, "settings": p.settings.to_dict()}, baseline)
    assert result.status == "stopped", result.to_dict()
    assert adapter.pump_count <= 1
    assert adapter.events[-1][0] == "restore"


def test_thermal_excursion_stops_before_any_pump(tmp_path):
    p, ctx = plan(), context(tmp_path)
    baseline = baselines(ctx, p)
    runner, adapter = build(ctx, p, adapter_kwargs={"thermal_excursion": True})
    result = runner.run({"accepted": True, "settings": p.settings.to_dict()}, baseline)
    assert result.status == "failed" and "Thermal excursion" in result.error
    assert adapter.pump_count == 0


def test_missing_reference_after_pump_retains_native_but_stops_without_retry(tmp_path):
    p, ctx = plan(), context(tmp_path)
    baseline = baselines(ctx, p)
    runner, adapter = build(ctx, p)
    capture = adapter.capture_block
    def missing_reference(*args, **kwargs):
        result = capture(*args, **kwargs)
        result["native"]["reference"][:] = 0.
        return result
    adapter.capture_block = missing_reference
    outcome = runner.run({"accepted": True, "settings": p.settings.to_dict()}, baseline)
    assert outcome.status == "incomplete"
    assert adapter.pump_count == 1
    assert "support" in outcome.error
    retained = load_run(outcome.output_path)
    assert any("spectral-early" in path for path in retained["chunks"])


def test_empty_preliminary_detector_is_not_reviewable(tmp_path):
    p, ctx = plan(), context(tmp_path)
    runner, adapter = build(ctx, p)
    capture = adapter.capture_block
    def empty_detector(*args, **kwargs):
        result = capture(*args, **kwargs)
        result["native"]["sample"][:] = np.nan
        return result
    adapter.capture_block = empty_detector
    outcome = runner.prepare("preliminary")
    assert not outcome["complete"]
    assert adapter.pump_count == 0


def test_cleanup_failure_takes_precedence_over_normal_abort(tmp_path):
    p, ctx = plan(), context(tmp_path)
    baseline = baselines(ctx, p)
    runner, adapter = build(ctx, p, adapter_kwargs={"cleanup_failure": True})
    runner.callback = lambda item: runner.cancel() if item["stage"] == "recovery_wait" else None
    result = runner.run({"accepted": True, "settings": p.settings.to_dict()}, baseline)
    assert result.status == "cleanup_failed"
    assert result.error == "Acquisition stopped"
    assert result.cleanup_errors


def test_native_reconstruction_keeps_uint64_markers_pointwise_times_and_missing_edges():
    origin = 2**60
    ticks = np.arange(32, dtype=np.uint64) * np.uint64(10) + np.uint64(origin)
    words = np.zeros(32, np.uint32)
    words[3:26] |= 1 << 21
    words[3:26] |= 1 << 20
    words[[5, 12, 19, 25]] |= 1 << 22
    words[1] |= 1 << 17
    streams = {2: {"timestamp": ticks, "dio": words},
               0: {"timestamp": ticks, "x": np.ones(32), "y": np.zeros(32)}}
    native = reconstruct_native(streams, clockbase_hz=210_000_000, markers_cm1=[1900, 1910, 1920, 1930], expected_scans=1)
    np.testing.assert_array_equal(native["native_sample_ticks"], ticks)
    assert native["native_sample_ticks"].dtype == np.uint64
    assert native["wavenumber_cm1"][12] == 1910
    assert np.isnan(native["wavenumber_cm1"][2])
    assert len(native["native_pump_sync_ticks"]) == 1
    # A capture starting high does not manufacture an observed rising edge.
    assert len(rising_edges(ticks[:2], np.array([1 << 17] * 2), 17)) == 0


def test_connected_optical_qualification_rejects_extra_pulse_even_outside_expected_window():
    adapter = object.__new__(ConnectedBurstAdapter)
    adapter.recipe = {"optical_pump_diagnostic": {"channel": "A", "threshold_adc": 5,
        "arrival_window_samples": [3, 5]}}
    record = {"overflow": 0, "ch_a_adc": np.array([0, 9, 0, 0, 9, 0])}
    with pytest.raises(ReadinessError, match="Observed 2"):
        adapter._optical_epoch(record, {})


def test_host_ownership_blocks_sibling_and_manual_until_restoration_and_persistence(tmp_path):
    coordinator = HardwareCoordinator(tmp_path / "owned-instrument.lock")
    ctx = context(tmp_path, coordinator=coordinator)
    sibling = context(tmp_path, mode="single", coordinator=coordinator)
    p0 = plan()
    p = replace(p0, settings=replace(p0.settings, example_only=False), readiness=())
    baseline = baselines(ctx, p)
    operation = ctx.begin_operation(p.settings.to_dict(), hardware=True)
    store = RunStore(operation.output_path, {"mode": "dual", "condition_id": p.settings.condition_id})
    runner = BurstRunner(ctx, p, operation, store=store)
    adapter = SimulatedBurstAdapter(ctx, operation, p, cancel=runner.cancel_event, progress=runner._progress, store=store)
    runner.adapter = adapter
    with pytest.raises(OwnershipError):
        sibling.begin_operation({}, hardware=True)
    with pytest.raises(OwnershipError):
        coordinator.acquire("manual-controls")
    original_restore = adapter.restore
    def restore():
        assert coordinator.snapshot()["state"] == "owned"
        with pytest.raises(OwnershipError):
            coordinator.acquire("manual-controls")
        return original_restore()
    adapter.restore = restore
    original_finalize = store.finalize
    def finalize(*args, **kwargs):
        assert coordinator.snapshot()["state"] == "owned"
        return original_finalize(*args, **kwargs)
    store.finalize = finalize
    result = runner.run({"accepted": True, "settings": p.settings.to_dict()}, baseline)
    assert result.status == "complete", result.to_dict()
    assert coordinator.snapshot()["state"] == "free"
    token = coordinator.acquire("manual-controls")
    coordinator.release(token, safe_verified=True)


def test_storage_failure_after_pump_faults_owned_instrument_without_replacement(tmp_path):
    coordinator = HardwareCoordinator(tmp_path / "owned-instrument.lock")
    ctx = context(tmp_path, coordinator=coordinator)
    p0 = plan()
    p = replace(p0, settings=replace(p0.settings, example_only=False), readiness=())
    baseline = baselines(ctx, p)
    operation = ctx.begin_operation(p.settings.to_dict(), hardware=True)
    store = RunStore(operation.output_path, {"mode": "dual", "condition_id": p.settings.condition_id})
    runner = BurstRunner(ctx, p, operation, store=store)
    adapter = SimulatedBurstAdapter(ctx, operation, p, cancel=runner.cancel_event, progress=runner._progress, store=store)
    runner.adapter = adapter
    original_save = store.save_chunk
    def fail_spectral(name, values):
        if name.startswith("spectral-"):
            raise OSError("Injected disk full after observed pump")
        return original_save(name, values)
    store.save_chunk = fail_spectral
    result = runner.run({"accepted": True, "settings": p.settings.to_dict()}, baseline)
    assert result.status == "incomplete"
    assert adapter.pump_count == 1
    assert "disk full" in result.error
    # The failure itself remains retained. The caller must not pretend missing
    # spectral native values were preserved merely because final JSON succeeded.
    assert coordinator.snapshot()["state"] == "fault"
    recovery = coordinator.acquire("explicit-recovery", recovery=True)
    coordinator.release(recovery, safe_verified=True, preservation_verified=True)


def test_prospective_plateau_still_takes_final_spectrum_at_planned_blank_scan_identity(tmp_path):
    p = compile_plan(replace(plan("single").settings, later_burst_count=5, observation_limit_s=10.,
        plateau_enabled=True, plateau_relative_tolerance=.99, plateau_band_windows_cm1=((1910., 1920.),)))
    ctx = context(tmp_path, "single")
    baseline = baselines(ctx, p)
    runner, adapter = build(ctx, p)
    result = runner.run({"accepted": True, "settings": p.settings.to_dict()}, baseline)
    assert result.status == "complete", result.to_dict()
    assert result.summary["termination"] == "prospective_plateau_with_final_spectrum"
    assert p.blocks[-1].block_id in result.summary["completed_blocks"]
    assert len(result.summary["completed_blocks"]) < len(p.blocks)
    final = result.data["latest_processed"]
    assert final["valid"].any()
    assert np.min(final["scan_index"]) == sum(b.scan_count for b in p.blocks[:-1])
    assert adapter.pump_count == 1


def test_verified_continuation_preserves_epoch_and_does_not_rearm_early_pump(tmp_path):
    p, ctx = plan(), context(tmp_path)
    baseline = baselines(ctx, p)
    first, first_adapter = build(ctx, p)
    first.callback = lambda item: first.cancel() if item["stage"] == "recovery_wait" else None
    interrupted = first.run({"accepted": True, "settings": p.settings.to_dict()}, baseline)
    retained = load_run(interrupted.output_path)["checkpoint"]["state"]
    retained.update(source_output_path=interrupted.output_path,
        state_evidence={"accepted_by": "Injected reviewer", "uninterrupted_native_clock": True,
                        "unchanged_sample_state": True, "native_now_s": interrupted.epoch["pump_time_s"] + .4})
    second, second_adapter = build(ctx, p)
    result = second.run({"accepted": True, "settings": p.settings.to_dict()}, baseline, continuation=retained)
    assert result.status == "complete", result.to_dict()
    assert result.epoch == interrupted.epoch
    assert all(event[2] == 0 for event in second_adapter.events if event[0] == "program")
    assert second_adapter.pump_count == 1
    events = load_run(result.output_path)["events"]
    assert not any(event["kind"] == "pump_intent" for event in events)


def test_owned_installed_capability_discovery_can_resolve_qualified_readiness(tmp_path):
    from control_app.devices.hf2li_service import HF2LIService
    from control_app.devices.t660_service import T660Service
    from control_app.measurement_modules.single_pump_scan_burst.settings import Capabilities
    hf, timer = create_autospec(HF2LIService, instance=True), create_autospec(T660Service, instance=True)
    hf.device_id = "test-hf2-owned"
    for method in (hf.connect, hf.stop_acquisition, hf.close, timer.connect, timer.set_trigger_source,
                   timer.command, timer.disable_channel, timer.configure_train, timer.close):
        method.return_value = None
    hf.discover_dual_phase_scan_capabilities.return_value = {"verified": True, "timing_rate_sps": 100000.,
        "sample": {"rates_sps": [10000.]}, "reference": {"rates_sps": [10000.]}}
    timer.verified_frame_capacity.return_value = 8192
    timer.get_frames_status.return_value = "OFF"
    timer.identify.return_value = "qualified-test-T660-2"
    timer.read_active_settings.return_value = {"queries": {"trigger_source": {"response": "OFF"}},
        "channels": {ch: {"enabled": {"response": "0"}} for ch in "ABCD"}}
    configuration = {"qualifications": {name: {"accepted": True, "record_id": "qualified-" + name}
        for name in ("tee_receiver_topology", "clock_transfer", "trajectory", "detector_roles")},
        "picoscope_capture_settings": {"total_samples": 200},
        "optical_pump_diagnostic": {"accepted": True, "calibration_id": "qualified-optical-01", "channel": "B",
            "signal_kind": "independent_optical_pump", "preserves_spectral_detector_topology": True},
        "sample_temperature_observation": {"observation_id": "qualified-77K-01", "temperature_identity": "EXAMPLE-TEMP",
            "observed_utc": datetime.now(timezone.utc).isoformat(), "temperature_k": 77., "uncertainty_k": .5, "valid_for_s": 60}}
    settings = replace(plan().settings, example_only=False, calibration_ids=("qualified-calibration",), promoted_bundle_ids=("qualified-test-bundle",),
        controls_record_ids=("accepted-dark-matrix-artifact",), hardware_evidence={"operating_configuration": configuration})
    preliminary_plan = compile_plan(settings)
    coordinator = HardwareCoordinator(tmp_path / "capability-owner.lock")
    def factory(device):
        def create(*, configuration):
            ctx.ownership.assert_owner(operation.ownership)
            return device
        return create
    ctx = ContextFactory(real_device_factories={"hf2li": factory(hf), "t660_2": factory(timer)},
        save_root_provider=lambda: tmp_path, ownership=coordinator).for_experiment("single_pump_scan_burst").for_mode("dual")
    operation = ctx.begin_operation(settings.to_dict(), hardware=True)
    runner = BurstRunner(ctx, preliminary_plan, operation)
    result = runner.prepare("capabilities")
    assert result["complete"], result
    capabilities = Capabilities.from_dict(result["capabilities"])
    assert capabilities.frame_feature_verified and capabilities.detector_rates_verified
    assert capabilities.topology_verified and capabilities.optical_pump_observation_available
    assert capabilities.temperature_observation_available
    resolved = compile_plan(settings, capabilities)
    assert resolved.ready, (resolved.errors, resolved.readiness)
    assert coordinator.snapshot()["state"] == "free"
    hf.close.assert_called_once()
    timer.close.assert_called_once()
