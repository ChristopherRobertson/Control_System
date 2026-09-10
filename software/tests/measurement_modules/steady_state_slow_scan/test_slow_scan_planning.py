"""Slow-scan planning tests: scientific coupling and finite pump-OFF schedules."""

from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from control_app.measurement_modules.steady_state_slow_scan.settings import (
    CONDITION_PROFILES, ConditionIdentity, PlannerInputs, QCLWindow, SlowScanSettings, SpectralSegment,
)
from control_app.measurement_modules.steady_state_slow_scan.planner import build_plan, inputs_from_context, simulation_inputs
from control_app.measurement_modules.steady_state_slow_scan.timing import compile_timing, quantize_seconds, assert_pump_inhibited


def request(mode="single", **changes):
    identity = ConditionIdentity(sample_id="sample-1", preparation_id="preparation-1", cell_id="cell-1", position_id="position-1",
                                 temperature_id="temperature-1", temperature_k=295., temperature_uncertainty_k=1.,
                                 temperature_record_id="record-T-1", matrix_id="matrix-1", configuration_id="config-1")
    return replace(SlowScanSettings(mode=mode, condition=identity,
                                   segments=(SpectralSegment("local", 1, 1900., 1910.),),
                                   condition_equilibrated=True, physical_controls_confirmed=True), **changes)


def plan_for(settings=None):
    settings = settings or request()
    return build_plan(settings, simulation_inputs(settings))


def test_empty_draft_is_hardware_free_and_reports_missing_evidence():
    plan = build_plan(SlowScanSettings())
    assert not plan.ready
    assert "Declare at least one supported QCL segment" in plan.errors
    assert any("promoted" in issue for issue in plan.readiness)
    assert plan.actual == {}
    assert plan.selected["optical_pump_events"] is None
    assert plan.estimates["pump_event_count"] == 0


@pytest.mark.parametrize("condition_id", tuple(CONDITION_PROFILES))
def test_four_condition_identities_round_trip_without_arc_ids(condition_id):
    settings = request(condition=replace(request().condition, condition_id=condition_id))
    restored = SlowScanSettings.from_dict(json.loads(json.dumps(settings.to_dict())))
    assert restored == settings
    assert restored.condition.condition_id == condition_id
    assert "ARC" not in json.dumps(restored.to_dict())
    assert restored.instance_id == "steady_state_slow_scan:single"


@pytest.mark.parametrize("field,value", [("schema_version", "900"), ("experiment_id", "phase_scan"), ("instance_id", "steady_state_slow_scan:dual")])
def test_incompatible_plan_schema_mode_or_experiment_is_rejected(field, value):
    data = request().to_dict()
    data[field] = value
    with pytest.raises(ValueError):
        SlowScanSettings.from_dict(data)


def test_unknown_scientific_setting_is_not_silently_dropped():
    with pytest.raises(ValueError, match="Unsupported"):
        SlowScanSettings.from_dict({"arbitrary_peak_center": 1905.})


def test_resolution_linewidth_native_sampling_and_measured_response_limit_speed():
    settings = request(requested_scan_speed_cm1_s=100., measured_linewidth_cm1=.6, sample_rate_hz=100.)
    inputs = simulation_inputs(settings)
    plan = build_plan(settings, inputs)
    assert not plan.errors
    block = plan.blocks[0]
    assert block.scan_speed_cm1_s <= 100 * (.6 / 6)
    assert block.scan_speed_cm1_s < settings.requested_scan_speed_cm1_s
    assert plan.selected["target_native_spacing_cm1"] == pytest.approx(.1)
    assert plan.selected["nominal_filter_3db_hz"] > 0
    assert plan.requested["requested_scan_speed_cm1_s"] == 100.
    assert plan.actual == {}


def test_below_measured_intrinsic_resolution_cannot_be_claimed():
    plan = plan_for(request(requested_resolution_cm1=.01))
    assert any("intrinsic" in error for error in plan.errors)


def test_uncharacterized_filter_override_invalidates_readiness():
    settings = request(time_constant_s=.1)
    plan = plan_for(settings)
    assert any("time_constant_s override" in item for item in plan.readiness)


def test_native_sample_rate_quantization_is_selected_and_requested_retained():
    plan = plan_for(request(sample_rate_hz=600.))
    assert plan.requested["sample_rate_hz"] == 600.
    assert plan.selected["sample_rate_hz"] == 1000.


def test_dual_reference_sampling_and_response_constrain_both_detectors():
    settings = request("dual", requested_scan_speed_cm1_s=100.)
    inputs = simulation_inputs(settings)
    profile = deepcopy(inputs.scientific_profile)
    profile["hf2li"]["reference"]["rate_sps"] = 100.
    profile["hf2li"]["reference"]["measured_response_s"] = .1
    plan = build_plan(settings, replace(inputs, scientific_profile=profile))
    assert plan.selected["aggregate_rate_hz"] == 11100.
    assert plan.blocks[0].scan_speed_cm1_s < 3.
    assert plan.estimates["control_acquisition_s"] == 0.
    assert plan_for().estimates["control_acquisition_s"] > 0.


def test_aggregate_detector_and_timing_throughput_is_checked():
    settings = request("dual")
    plan = build_plan(settings, replace(simulation_inputs(settings), aggregate_max_rate_hz=11000.))
    assert any("Aggregate" in error for error in plan.errors)


def test_qcl_transition_is_explicit_and_out_of_window_segment_rejected():
    settings = request(segments=(SpectralSegment("low", 1, 1900., 1910.), SpectralSegment("high", 2, 1920., 1930.)))
    plan = plan_for(settings)
    assert [(block.segment_id, block.direction) for block in plan.blocks] == [
        ("low", "forward"), ("low", "reverse"), ("high", "forward"), ("high", "reverse")]
    inputs = simulation_inputs(settings)
    inputs = replace(inputs, qcl_windows=(replace(inputs.qcl_windows[0], upper_cm1=1905.), inputs.qcl_windows[1]))
    assert any("crosses QCL" in error for error in build_plan(settings, inputs).errors)


def test_unqualified_nominal_qcl_window_never_silently_becomes_calibration():
    settings = request()
    inputs = replace(simulation_inputs(settings), qcl_windows=(QCLWindow(1, 1800., 2000.),))
    plan = build_plan(settings, inputs)
    assert any("QCL usable-range" in issue for issue in plan.readiness)
    assert not plan.blocks


def test_finite_frames_are_deterministic_complete_and_all_pump_off():
    plan = plan_for()
    compiled = compile_timing(plan)
    assert compiled.to_dict() == compile_timing(plan).to_dict()
    for block in compiled.blocks:
        assert len(block.frames) == plan.settings.replicates + 1
        assert block.physical_frame_count == len(block.frames)
        for frame in block.frames:
            assert set(frame["channels"]) == set("ABCD")
            assert frame["channels"]["A"]["enabled"] is False
            assert frame["channels"]["B"]["enabled"] is False
            assert frame["channels"]["D"]["enabled"] is False
        assert block.frames[-1]["inert_terminator"] is True
        assert all(not channel["enabled"] for channel in block.frames[-1]["channels"].values())
        assert block.frames[0]["channels"]["C"]["polarity"] == "negative"
        assert block.record_duration_s == pytest.approx(block.block.frame_period_s * len(block.frames))
    assert compiled.event_counts["process"] == len(plan.blocks) * plan.settings.replicates
    assert compiled.event_counts["pump_fire"] == compiled.event_counts["pump_q_switch"] == 0
    assert compiled.probe_recipe["trigger_source"] == "OFF"
    assert_pump_inhibited(compiled)


def test_safety_validator_rejects_mutated_pump_enabled_schedule():
    compiled = compile_timing(plan_for())
    compiled.blocks[0].frames[0]["channels"]["A"]["enabled"] = True
    with pytest.raises(ValueError, match="must remain OFF"):
        assert_pump_inhibited(compiled)


def test_upload_uses_existing_acknowledged_pending_field_service_shape():
    compiled = compile_timing(plan_for())
    callback = lambda *args: None
    kwargs = compiled.blocks[0].upload_kwargs(progress=callback, cancel_check=callback)
    assert set(kwargs) == {"frames", "predivider", "input_frequency_hz", "progress", "cancel_check"}
    assert kwargs["progress"] is callback
    kwargs["frames"][0]["channels"]["A"]["enabled"] = True
    assert compiled.blocks[0].frames[0]["channels"]["A"]["enabled"] is False


def test_terminal_frame_memory_is_included_and_no_implicit_split_occurs():
    settings = request(replicates=3)
    plan = build_plan(settings, replace(simulation_inputs(settings), t660_frame_capacity=3))
    assert any("no implicit splitting" in error for error in plan.errors)
    with pytest.raises(ValueError):
        compile_timing(plan)


def test_simulation_profile_cannot_authorize_real_hardware():
    plan = plan_for()
    plan.require_ready(hardware=False)
    with pytest.raises(ValueError, match="Simulation"):
        plan.require_ready(hardware=True)


def test_time_quantization_and_range_limits():
    assert quantize_seconds(1.0004e-3, 1e-6, 10.) == .001
    assert quantize_seconds(0., 1e-9, 10., allow_zero=True) == 0.
    with pytest.raises(ValueError):
        quantize_seconds(1e-12, 1e-9, 10.)
    with pytest.raises(ValueError):
        quantize_seconds(11., 1e-9, 10.)


def test_missing_overheads_are_lower_bound_and_saving_cleanup_included():
    settings = request()
    inputs = simulation_inputs(settings)
    profile = deepcopy(inputs.scientific_profile)
    profile["overhead_estimates_s"] = {"restoration": 10., "saving": 5., "analysis": 3.}
    plan = build_plan(settings, replace(inputs, scientific_profile=profile))
    assert plan.estimates["wall_clock_is_lower_bound"]
    assert plan.estimates["wall_clock_s"] >= plan.estimates["sample_acquisition_s"] + 18.
    assert plan.estimates["native_storage_bytes"] > 0
    assert plan.estimates["peak_memory_bytes"] >= plan.estimates["native_storage_bytes"]


def test_promoted_profile_is_loaded_by_host_and_raw_evidence_is_not_read():
    settings = request(calibration_bundle_ids=("accepted-1",))
    calls = []
    profile = simulation_inputs(settings).to_dict()
    profile.pop("promoted_bundle_ids")
    profile.pop("source_records")
    def loader(bundle_id):
        calls.append(bundle_id)
        return SimpleNamespace(path="instrument/promoted_bundles/accepted-1", manifest={"steady_state_slow_scan": {"planner_inputs": profile}})
    inputs = inputs_from_context(SimpleNamespace(promoted_bundle=loader), settings)
    assert calls == ["accepted-1"]
    assert inputs.promoted_bundle_ids == ("accepted-1",)
    assert inputs.source_records[0]["source_id"] == "accepted-1"


def test_missing_promoted_scientific_payload_reports_specific_issue():
    context = SimpleNamespace(promoted_bundle=lambda _: SimpleNamespace(path="bundle", manifest={}))
    with pytest.raises(ValueError, match="does not contain"):
        inputs_from_context(context, request(calibration_bundle_ids=("unrelated",)))


def test_planner_detaches_caller_evidence_and_retains_actual_readbacks():
    settings = request()
    inputs = simulation_inputs(settings)
    inputs.actual_readbacks["observed_rate_hz"] = 999.
    plan = build_plan(settings, inputs)
    inputs.scientific_profile["probe_rate_hz"] = 1.
    inputs.actual_readbacks["observed_rate_hz"] = 2.
    assert plan.inputs.scientific_profile["probe_rate_hz"] == 100000.
    assert plan.actual["observed_rate_hz"] == 999.
