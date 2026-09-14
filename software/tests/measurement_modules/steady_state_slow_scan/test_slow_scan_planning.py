"""Raw/relative planning from connected capabilities, independent Auto settings."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import json
import pytest
from control_app.measurement_modules.steady_state_slow_scan.settings import ConditionIdentity, PlannerInputs, QCLWindow, SlowScanSettings, SpectralSegment
from control_app.measurement_modules.steady_state_slow_scan.planner import build_plan, resolve_runtime_inputs, inputs_from_context, current_to_requested_range_v
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
            "qcl_windows":[{"qcl":1,"min_cm1":1600.,"max_cm1":2100.}],"qcl_pulse_params":{"1":{"pulse_rate_hz":120000.,"pulse_width_ns":1000.,"current_ma":1.}},
            "t660_1":{"queries":{"synth_frequency":{"ok":True,"response":"100000Hz"}},"channels":{"B":{"width_edge":{"ok":True,"response":"1000ns"}}}},
            "qcl_current_limits":{"1":(0.,1000.)},"qcl_pulse_limits":{"1":{"max_pulse_rate_hz":3000000.,"max_pulse_width_ns":5000.,"max_duty_cycle":30.}},"probe_width_s":1e-6,"t660_frame_capacity":8192,"marker_width_us":1000,"sweep":{"scan_rate_cm1_s":2.}}


def plan_for(settings=None, readbacks=None):
    settings = settings or SlowScanSettings(lower_cm1=1900.,upper_cm1=1901.,requested_scan_speed_cm1_s=2.)
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














def test_native_support_matching_policy_is_bounded_and_recorded():
    plan=plan_for()
    expected=2*max(b.scan_speed_cm1_s/plan.selected["sample_rate_hz"] for b in plan.blocks)
    assert plan.selected["control_match_max_gap_cm1"] == pytest.approx(expected)
    assert "no calibration claim" in plan.selected["control_matching_basis"]


def test_aggregate_throughput_and_frame_memory_are_actual_blockers():
    plan=plan_for(SlowScanSettings(mode="dual",lower_cm1=1900.,upper_cm1=1901.))
    limited=build_plan(plan.settings,replace(plan.inputs,aggregate_max_rate_hz=1.))
    assert any("throughput" in error for error in limited.errors)
    limited=build_plan(plan.settings,replace(plan.inputs,t660_frame_capacity=1))
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


@pytest.mark.parametrize("speed", [.1, 2., 400., 10000.])
def test_entered_speed_is_authoritative_without_resolution_throttling(speed):
    plan = plan_for(SlowScanSettings(lower_cm1=1800.,upper_cm1=2000.,requested_scan_speed_cm1_s=speed))
    assert plan.ready, (plan.errors,plan.readiness)
    assert all(block.scan_speed_cm1_s == pytest.approx(speed,rel=1e-7) for block in plan.blocks)
    assert {block.qcl for block in plan.blocks} == {1}


@pytest.mark.parametrize("speed", [0., .099, 10001., float("nan"), float("inf")])
def test_invalid_speed_rejected_before_connected_discovery(speed):
    assert "Scan speed" in " ".join(build_plan(SlowScanSettings(requested_scan_speed_cm1_s=speed)).errors)


def test_saved_removed_controls_cannot_change_selected_settings_or_select_qcl2():
    plain = plan_for()
    data = plain.settings.to_dict()
    retired = {"segments":[{"segment_id":"old","qcl":2,"lower_cm1":1.,"upper_cm1":2.}],
        "requested_resolution_cm1":1e-12,"measured_linewidth_cm1":0.,"sample_rate_hz":1.,"reference_sample_rate_hz":1.,
        "sample_range_v":9.,"reference_range_v":9.,"settle_s":999.,"marker_interval_cm1":20.,"marker_width_s":2.,
        "dark_duration_s":999.,"process_pulse_width_s":1.,"fit_peak_count":7,"fit_line_shape":"invalid",
        "fit_baseline_degree":3,"fit_fringe_periods_cm1":[-1.],"probe_width_s":.9}
    data.update(retired)
    restored = SlowScanSettings.from_dict(data)
    changed = plan_for(restored)
    assert changed.selected == plain.selected and changed.blocks == plain.blocks
    assert restored.imported_requested_metadata == retired and restored.pulse_width_s == 150e-9
    assert SlowScanSettings.from_dict(restored.to_dict()).imported_requested_metadata == retired


def test_legacy_cadence_migrates_but_electrical_width_is_not_optical_width():
    settings = SlowScanSettings.from_dict({"probe_rate_hz":80000.,"probe_width_s":5e-6})
    assert settings.repetition_rate_hz == 80000. and settings.pulse_width_s == 150e-9
    plan = plan_for(replace(settings,lower_cm1=1900.,upper_cm1=1901.))
    assert plan.selected["pulse_width_s"] == pytest.approx(150e-9)
    assert plan.selected["probe_width_s"] == pytest.approx(1e-6)


def test_qcl2_coverage_cannot_route_an_out_of_range_request():
    readbacks = live_readbacks()
    readbacks["qcl_windows"].append({"qcl":2,"min_cm1":2100.,"max_cm1":2300.})
    plan = plan_for(SlowScanSettings(lower_cm1=2100.,upper_cm1=2200.),readbacks)
    assert "QCL 1 bounds" in " ".join(plan.errors) and not plan.blocks


@pytest.mark.parametrize("current,expected", [(0.,.001),(250.,.5),(500.,1.),(625.,1.375),(750.,1.75),(1000.,2.),(1200.,2.)])
def test_confirmed_current_range_policy(current,expected):
    assert current_to_requested_range_v(current) == pytest.approx(expected)


def test_current_and_independent_filter_controls_are_real_settings():
    settings = SlowScanSettings(mode="dual",lower_cm1=1900.,upper_cm1=1901.,current_ma=750.,reference_filter_order=3,reference_time_constant_s=.002)
    plan = plan_for(settings)
    assert plan.ready
    assert plan.selected["hf2li"]["sample"]["order"] == 2 and plan.selected["hf2li"]["reference"]["order"] == 3
    assert plan.selected["hf2li"]["reference"]["timeconstant_s"] == .002
    assert plan.inputs.scientific_profile["qcl_pulse_params"]["1"]["current_ma"] == 750.
    assert plan.selected["sample_range_v"] == plan.selected["reference_range_v"] == 1.75
    assert "Current exceeds" in " ".join(plan_for(replace(settings,current_ma=1001.)).errors)


def test_visible_optical_duty_limit_is_inclusive_and_independent_of_ttl_width():
    at_limit = build_plan(SlowScanSettings(repetition_rate_hz=100000.,pulse_width_s=3e-6))
    assert not any("30% duty" in error for error in at_limit.errors)
    above = build_plan(SlowScanSettings(repetition_rate_hz=100000.,pulse_width_s=3.0001e-6))
    assert "30% duty" in " ".join(above.errors)
    plan = plan_for(SlowScanSettings(lower_cm1=1900.,upper_cm1=1901.,repetition_rate_hz=100000.,pulse_width_s=2e-6))
    assert plan.ready and plan.selected["pulse_duty_fraction"] == pytest.approx(.2)
    assert plan.selected["probe_width_s"] == 1e-6
    assert plan.inputs.scientific_profile["qcl_pulse_params"]["1"]["pulse_width_ns"] == pytest.approx(2000.)


def test_internal_vendor_duty_is_separate_and_cannot_exceed_thirty_percent():
    raw = live_readbacks()
    raw["qcl_pulse_params"]["1"]["pulse_rate_hz"] = 190000.
    raw["qcl_pulse_limits"]["1"]["max_duty_cycle"] = 40.
    plan = plan_for(SlowScanSettings(lower_cm1=1900.,upper_cm1=1901.,repetition_rate_hz=100000.,pulse_width_s=2e-6),raw)
    assert plan.ready
    params = plan.inputs.scientific_profile["qcl_pulse_params"]["1"]
    assert params["pulse_rate_hz"] * params["pulse_width_ns"] * 1e-9 <= .30 + 1e-12
    assert params["pulse_rate_hz"] == plan.selected["repetition_rate_hz"]
    raw["qcl_pulse_limits"]["1"]["max_duty_cycle"] = 10.
    assert plan_for(SlowScanSettings(lower_cm1=1900.,upper_cm1=1901.,repetition_rate_hz=100000.,pulse_width_s=2e-6),raw).errors


def test_internal_rate_ceiling_uses_sdk_float32_optical_width_not_unrounded_request():
    import struct
    requested_ns = 1500.0069134
    raw = live_readbacks()
    raw["qcl_pulse_params"]["1"]["pulse_rate_hz"] = 100000.
    settings = SlowScanSettings(lower_cm1=1900.,upper_cm1=1901.,repetition_rate_hz=150000.,pulse_width_s=requested_ns*1e-9)
    plan = plan_for(settings,raw)
    assert plan.ready, (plan.errors,plan.readiness)
    params = plan.inputs.scientific_profile["qcl_pulse_params"]["1"]
    encoded_width = struct.unpack("f",struct.pack("f",requested_ns))[0]
    encoded_rate = struct.unpack("f",struct.pack("f",params["pulse_rate_hz"]))[0]
    assert encoded_width == 1500.0069580078125
    assert plan.settings.pulse_width_s == settings.pulse_width_s
    assert params["pulse_width_ns"] == encoded_width
    assert plan.selected["pulse_width_s"] == encoded_width*1e-9
    assert encoded_rate == params["pulse_rate_hz"]
    assert encoded_rate == 150000.
    assert encoded_rate * encoded_width * 1e-9 <= .30


@pytest.mark.parametrize("field", ["requested_sample_rate_hz", "requested_reference_sample_rate_hz"])
@pytest.mark.parametrize("value", [0.,-1.,float("nan"),float("inf"),True])
def test_sampling_override_requires_finite_positive_rate_before_discovery(field,value):
    plan = build_plan(replace(SlowScanSettings(mode="dual"),**{field:value}))
    assert field in " ".join(plan.errors)


def test_sampling_overrides_are_independent_and_preserve_auto_filters_and_speed():
    settings = SlowScanSettings(mode="dual",lower_cm1=1900.,upper_cm1=1901.,requested_scan_speed_cm1_s=2.)
    automatic = plan_for(settings)
    for field,role,other in (("requested_sample_rate_hz","sample","reference"),
                            ("requested_reference_sample_rate_hz","reference","sample")):
        selected = plan_for(replace(settings,**{field:10000.}))
        assert selected.ready
        assert selected.selected["hf2li"][role]["rate_sps"] == 10000.
        assert selected.selected["hf2li"][other] == automatic.selected["hf2li"][other]
        for key in ("order","timeconstant_s"):
            assert selected.selected["hf2li"][role][key] == automatic.selected["hf2li"][role][key]
        assert [block.scan_speed_cm1_s for block in selected.blocks] == [block.scan_speed_cm1_s for block in automatic.blocks]
        assert selected.requested[field] == 10000.


def test_sampling_override_uses_each_detectors_capabilities_and_aggregate_limits():
    settings = SlowScanSettings(mode="dual",lower_cm1=1900.,upper_cm1=1901.,requested_reference_sample_rate_hz=10000.)
    raw = live_readbacks("dual")
    raw["hf2li"]["reference"]["rates_sps"] = (100.,1000.)
    limited = plan_for(settings,raw)
    assert "reference sampling rate unsupported" in " ".join(limited.errors)
    manual = plan_for(replace(settings,requested_sample_rate_hz=10000.))
    assert manual.ready and manual.selected["aggregate_rate_hz"] == 30000.
    unknown_reference = build_plan(manual.settings,replace(manual.inputs,supported_reference_sample_rates_hz=()))
    assert "reference sample rates unavailable" in " ".join(unknown_reference.readiness)
    assert "reference_sample_rate_hz" not in unknown_reference.selected
    assert "throughput" in " ".join(build_plan(manual.settings,replace(manual.inputs,aggregate_max_rate_hz=29000.)).errors)
    short = plan_for(SlowScanSettings(lower_cm1=1900.,upper_cm1=1900.4,requested_scan_speed_cm1_s=100.,requested_sample_rate_hz=100.))
    assert "sample stream cannot sample" in " ".join(short.errors)


def test_sampling_override_roundtrip_keeps_retired_rate_preferences_inert():
    current = SlowScanSettings(mode="dual",lower_cm1=1900.,upper_cm1=1901.,requested_sample_rate_hz=10000.)
    imported = SlowScanSettings.from_dict({**current.to_dict(),"sample_rate_hz":333.,"reference_sample_rate_hz":444.})
    assert imported.requested_sample_rate_hz == 10000. and imported.requested_reference_sample_rate_hz is None
    assert imported.imported_requested_metadata["sample_rate_hz"] == 333.
    assert imported.imported_requested_metadata["reference_sample_rate_hz"] == 444.
    assert SlowScanSettings.from_dict(imported.to_dict()) == imported
    assert plan_for(imported).selected == plan_for(current).selected
    assert not build_plan(current).errors
    unsupported = plan_for(replace(current,requested_sample_rate_hz=333.))
    assert "sample sampling rate unsupported" in " ".join(unsupported.errors)


@pytest.mark.parametrize("count", [1,3])
def test_default_start_to_end_plan_has_total_scan_count_and_one_terminal_frame(count):
    settings = SlowScanSettings(replicates=count)
    assert (settings.upper_cm1,settings.lower_cm1,settings.requested_scan_speed_cm1_s) == (2050.,1650.,40.)
    assert SlowScanSettings.from_dict({"requested_scan_speed_cm1_s":None}).requested_scan_speed_cm1_s == 40.
    plan = plan_for(settings)
    assert plan.ready and len(plan.blocks) == 1
    block = plan.blocks[0]
    assert (block.direction,block.start_cm1,block.stop_cm1,block.scan_speed_cm1_s,block.replicates) == ("reverse",2050.,1650.,40.,count)
    assert block.scan_duration_s == 10.
    compiled = compile_timing(plan)
    assert len(compiled.blocks) == 1 and len(compiled.blocks[0].frames) == count+1
    assert compiled.event_counts["process"] == count and compiled.event_counts["physical_frames"] == count+1
    assert compiled.blocks[0].frames[-1]["inert_terminator"]
    assert plan.estimates["sample_sweep_count"] == count
    assert plan.estimates["sample_physical_frame_count"] == count+1
    assert plan.estimates["sample_acquisition_s"] == pytest.approx((count+1)*block.frame_period_s)
    assert plan.estimates["wall_clock_s"] == pytest.approx((count+1)*block.frame_period_s+plan.estimates["dark_s"])


@pytest.mark.parametrize("start,end", [(1650.,2050.),(2050.,2050.)])
def test_start_must_exceed_end(start,end):
    plan = build_plan(SlowScanSettings(upper_cm1=start,lower_cm1=end))
    assert "Start must be greater than End" in " ".join(plan.errors)


def test_compiler_refuses_an_ascending_trajectory_even_if_imported_block_is_mutated():
    plan = plan_for()
    ascending = replace(plan.blocks[0],direction="forward",start_cm1=plan.settings.lower_cm1,stop_cm1=plan.settings.upper_cm1)
    with pytest.raises(ValueError,match="descending Start-to-End"):
        compile_timing(replace(plan,blocks=(ascending,)))
