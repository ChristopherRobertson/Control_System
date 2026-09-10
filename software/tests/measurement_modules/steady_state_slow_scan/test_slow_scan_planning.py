"""Raw/relative planning from connected capabilities, independent Auto settings."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import json
import pytest
from control_app.measurement_modules.steady_state_slow_scan.settings import ConditionIdentity, PlannerInputs, QCLWindow, SlowScanSettings, SpectralSegment
from control_app.measurement_modules.steady_state_slow_scan.planner import build_plan, resolve_runtime_inputs, inputs_from_context
from control_app.measurement_modules.steady_state_slow_scan.timing import compile_timing, quantize_seconds, assert_pump_inhibited


def live_readbacks(mode="single"):
    device = "devTEST"
    caps = {"device_id": device, "verified": True, "source": "injected installed transport", "orders": (1,2,3,4),
            "timeconstants_by_order": {i: (.0001,.001,.002,.01) for i in range(1,5)}, "rates_sps": (100.,1000.,10000.),
            "timing_rate_sps": 10000., "enabled_streams": (0,2)}
    if mode == "dual": caps = {**caps, "sample": deepcopy(caps), "reference": deepcopy(caps), "enabled_streams": (0,2,3)}
    nodes = {}
    for index in range(6):
        for node,value in (("order",2),("timeconstant",.001),("rate",1000.)):
            nodes[f"/{device}/demods/{index}/{node}"] = {"value":value,"type":"double"}
    for index in (0,1):
        nodes[f"/{device}/sigins/{index}/range"] = {"value":1.,"type":"double"}
        nodes[f"/{device}/sigins/{index}/imp50"] = {"value":0,"type":"int"}
    return {"hf2li":caps,"hf2li_settings":{"nodes":nodes,"read_errors":[]},
            "qcl_windows":[{"qcl":1,"min_cm1":1800.,"max_cm1":2050.}],"qcl_pulse_params":{"1":{"pulse_rate_hz":120000.,"pulse_width_ns":1000.,"current_ma":1.}},
            "t660_1":{"queries":{"synth_frequency":{"ok":True,"response":"100000Hz"}},"channels":{"B":{"width_edge":{"ok":True,"response":"1000ns"}}}},
            "probe_width_s":1e-6,"t660_frame_capacity":8192,"marker_width_us":1000,"sweep":{"scan_rate_cm1_s":2.}}


def plan_for(settings=None, readbacks=None):
    settings = settings or SlowScanSettings(lower_cm1=1900.,upper_cm1=1901.,requested_resolution_cm1=.05)
    return build_plan(settings,resolve_runtime_inputs({},readbacks or live_readbacks(settings.mode),settings))


def test_default_connected_metadata_optional_no_acknowledgement_flags():
    settings=SlowScanSettings()
    assert settings.hardware is True and settings.condition.condition_id == ""
    assert "physical_controls_confirmed" not in settings.to_dict()
    assert "condition_equilibrated" not in settings.to_dict()
    assert not build_plan(settings).errors
    assert build_plan(settings).readiness


def test_raw_connected_plan_needs_no_promoted_or_qualification_records():
    plan=plan_for()
    assert plan.ready, (plan.errors,plan.readiness)
    assert not plan.inputs.promoted_bundle_ids
    assert plan.inputs.tee_receiver_topology_verified is False
    assert plan.selected["measured_response_s"] is None
    assert plan.selected["intrinsic_resolution_cm1"] is None
    assert plan.selected["planning_response_s"] > 0
    assert plan.warnings
    plan.require_ready(hardware=True)


@pytest.mark.parametrize("label,temperature",[("",None),("arbitrary material",295.),("77k_hrp_co",77.),("different",-1.)])
def test_optional_material_and_temperature_never_change_or_gate_plan(label,temperature):
    plain=plan_for()
    settings=replace(plain.settings,condition=ConditionIdentity(condition_id=label,temperature_k=temperature))
    result=plan_for(settings)
    assert result.ready
    assert result.blocks == plain.blocks
    assert result.selected == plain.selected


def test_legacy_acknowledgements_are_dropped_on_import():
    data=SlowScanSettings().to_dict()
    data.update(physical_controls_confirmed=False,condition_equilibrated=False)
    result=SlowScanSettings.from_dict(data)
    assert "physical_controls_confirmed" not in result.to_dict()


@pytest.mark.parametrize("field,value",[("schema_version","900"),("experiment_id","phase_scan"),("instance_id","steady_state_slow_scan:dual")])
def test_incompatible_native_plan_rejected(field,value):
    data=SlowScanSettings().to_dict(); data[field]=value
    with pytest.raises(ValueError): SlowScanSettings.from_dict(data)


def test_live_ranges_automatically_create_explicit_qcl_blocks_and_gaps():
    settings=SlowScanSettings(lower_cm1=1900.,upper_cm1=1904.,requested_resolution_cm1=.05)
    raw=live_readbacks(); raw["qcl_windows"]=[{"qcl":1,"min_cm1":1890.,"max_cm1":1901.},{"qcl":2,"min_cm1":1902.,"max_cm1":1910.}]
    plan=plan_for(settings,raw)
    assert plan.ready
    assert [(b.qcl,b.start_cm1,b.stop_cm1) for b in plan.blocks] == [(1,1900.,1901.),(1,1901.,1900.),(2,1902.,1904.),(2,1904.,1902.)]
    assert any("unsupported QCL intervals" in warning for warning in plan.warnings)


def test_explicit_segment_syntax_can_be_saved_before_discovery():
    settings=SlowScanSettings(segments=(SpectralSegment("custom",0,1900.,1901.),))
    assert not build_plan(settings).errors
    assert build_plan(SlowScanSettings.from_dict(json.loads(json.dumps(settings.to_dict())))).readiness


def test_known_out_of_range_explicit_segment_blocks():
    settings=SlowScanSettings(segments=(SpectralSegment("bad",1,1800.,2100.),))
    assert any("QCL bounds" in error for error in plan_for(settings).errors)


def test_each_detector_override_is_independent_and_auto_recomputes():
    settings=SlowScanSettings(mode="dual",lower_cm1=1900.,upper_cm1=1901.,requested_resolution_cm1=.05)
    base=plan_for(settings)
    manual=plan_for(replace(settings,reference_filter_order=3,reference_sample_rate_hz=1000.))
    assert manual.ready
    assert manual.selected["reference_filter_order"] == 3
    assert manual.selected["filter_order"] == base.selected["filter_order"]
    assert manual.selected["time_constant_s"] == base.selected["time_constant_s"]
    changed=plan_for(replace(settings,reference_sample_rate_hz=1000.,requested_resolution_cm1=.005))
    assert changed.ready
    assert changed.selected["reference_sample_rate_hz"] == 1000.
    assert changed.selected["time_constant_s"] != base.selected["time_constant_s"]
    assert changed.selected["sample_rate_hz"] != base.selected["sample_rate_hz"]


def test_unsupported_hardware_override_is_specific_error():
    assert any("sample rate unsupported" in error for error in plan_for(replace(plan_for().settings,sample_rate_hz=600.)).errors)
    assert any("filter order unsupported" in error for error in plan_for(replace(plan_for().settings,filter_order=8)).errors)


def test_narrow_resolution_remains_claim_warning_with_explicit_fast_scan():
    plan=plan_for(replace(plan_for().settings,requested_resolution_cm1=.00001,requested_scan_speed_cm1_s=10.))
    assert plan.ready
    assert any("broadening" in warning for warning in plan.warnings)
    assert plan.blocks[0].scan_speed_cm1_s == 10.


def test_native_support_matching_policy_is_bounded_and_recorded():
    plan=plan_for()
    expected=2*max(b.scan_speed_cm1_s/plan.selected["sample_rate_hz"] for b in plan.blocks)
    assert plan.selected["control_match_max_gap_cm1"] == pytest.approx(expected)
    assert "no calibration claim" in plan.selected["control_matching_basis"]


def test_aggregate_throughput_and_frame_memory_are_actual_blockers():
    plan=plan_for(SlowScanSettings(mode="dual",lower_cm1=1900.,upper_cm1=1901.))
    limited=build_plan(plan.settings,replace(plan.inputs,aggregate_max_rate_hz=1.))
    assert any("throughput" in error for error in limited.errors)
    limited=build_plan(plan.settings,replace(plan.inputs,t660_frame_capacity=2))
    assert any("physical frame memory" in error for error in limited.errors)


def test_deterministic_finite_schedule_has_terminal_off_and_no_pump_outputs():
    plan=plan_for(); compiled=compile_timing(plan)
    assert compiled.to_dict() == compile_timing(plan).to_dict()
    for block in compiled.blocks:
        assert len(block.frames) == plan.settings.replicates+1
        assert block.frames[-1]["inert_terminator"]
        for frame in block.frames:
            assert set(frame["channels"]) == set("ABCD")
            assert all(not frame["channels"][channel]["enabled"] for channel in "ABD")
        assert all(not item["enabled"] for item in block.frames[-1]["channels"].values())
    assert compiled.event_counts["pump_fire"] == compiled.event_counts["pump_q_switch"] == 0
    assert_pump_inhibited(compiled)


def test_mutated_pump_schedule_is_rejected():
    compiled=compile_timing(plan_for()); compiled.blocks[0].frames[0]["channels"]["A"]["enabled"]=True
    with pytest.raises(ValueError,match="must remain OFF"): assert_pump_inhibited(compiled)


def test_upload_uses_service_pending_fields_callbacks_and_detached_tables():
    block=compile_timing(plan_for()).blocks[0]; cb=lambda *args:None
    kwargs=block.upload_kwargs(progress=cb,cancel_check=cb)
    assert set(kwargs)=={"frames","predivider","input_frequency_hz","progress","cancel_check"}
    kwargs["frames"][0]["channels"]["A"]["enabled"]=True
    assert block.frames[0]["channels"]["A"]["enabled"] is False


def test_manufacturer_command_grid_is_not_claimed_optical_precision():
    plan=plan_for()
    assert plan.inputs.t660_tick_s == 10e-12
    assert plan.inputs.t660_maximum_delay_s == 3600.
    assert quantize_seconds(.001000000004,10e-12,3600.) == .001
    assert plan.selected["time_zero_irf_status"] == "not established by static spectroscopy"


def test_unavailable_optional_calibration_cannot_block_raw_plan():
    raw=live_readbacks()
    context=SimpleNamespace(configuration=lambda:{},promoted_bundle=lambda name:(_ for _ in ()).throw(ValueError("not promoted")))
    settings=SlowScanSettings(lower_cm1=1900.,upper_cm1=1901.,calibration_bundle_ids=("missing",))
    plan=build_plan(settings,inputs_from_context(context,settings,raw))
    assert plan.ready
    assert any("Optional calibration" in warning for warning in plan.warnings)


def test_plan_keeps_native_actual_values_and_detaches_input():
    raw=live_readbacks(); inputs=resolve_runtime_inputs({},raw)
    plan=build_plan(SlowScanSettings(),inputs)
    raw["t660_frame_capacity"]=1
    inputs.scientific_profile["probe_rate_hz"]=1.
    assert plan.actual["t660_frame_capacity"]==8192
    assert plan.inputs.scientific_profile["probe_rate_hz"]==100000.
    assert plan.estimates["wall_clock_is_lower_bound"]
    assert plan.estimates["wall_clock_s"] == pytest.approx(plan.estimates["sample_acquisition_s"]+plan.estimates["dark_s"])


@pytest.mark.parametrize("period", [0., -1., float("nan"), float("inf")])
def test_invalid_fringe_model_is_rejected_before_device_discovery(period):
    assert "Fringe periods" in " ".join(build_plan(SlowScanSettings(fit_fringe_periods_cm1=(period,))).errors)


def test_optional_report_labels_and_legacy_review_fields_do_not_gate_operation():
    data = SlowScanSettings(purpose="unstructured observation label").to_dict()
    data.update(acceptance_reviewer="old", acceptance_rationale="legacy")
    restored = SlowScanSettings.from_dict(data)
    assert restored.purpose == "unstructured observation label"
    assert "acceptance_reviewer" not in restored.to_dict()
    assert not build_plan(restored).errors


def test_optional_calibration_preserves_guarded_models_without_unchecked_timing_changes():
    profile = {"measured_response_s": float("nan"), "intrinsic_resolution_cm1": -1.,
               "sample_group_delay_s": 1000., "direction_bit_by_direction": {"forward": 0},
               "axis_correction": {"calibration_id": "axis-1"}, "path_balance": {"control_id": "B-1"}}
    bundle = SimpleNamespace(path="instrument/promoted_bundles/optional", manifest={"steady_state_slow_scan": {
        "planner_inputs": {"scientific_profile": profile}}})
    context = SimpleNamespace(configuration=lambda: (_ for _ in ()).throw(AssertionError("Must use immutable operation configuration")),
                              promoted_bundle=lambda _: bundle)
    settings = SlowScanSettings(lower_cm1=1900., upper_cm1=1901., calibration_bundle_ids=("optional",))
    inputs = inputs_from_context(context, settings, live_readbacks(), configuration={"system": {"name": "observed-config"}})
    plan = build_plan(settings, inputs)
    assert plan.ready and plan.inputs.configuration_id == "observed-config"
    assert plan.selected["measured_response_s"] is None and plan.selected["intrinsic_resolution_cm1"] is None
    assert "sample_group_delay_s" not in plan.inputs.scientific_profile
    assert "direction_bit_by_direction" not in plan.inputs.scientific_profile
    assert plan.inputs.scientific_profile["axis_correction"]["calibration_id"] == "axis-1"
    assert plan.inputs.scientific_profile["path_balance"]["control_id"] == "B-1"
    assert any("not applied" in warning for warning in plan.warnings)
