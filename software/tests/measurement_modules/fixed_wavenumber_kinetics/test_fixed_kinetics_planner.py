"""Bounded, hardware-free scientific planner and deterministic timing checks."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from control_app.measurement_modules.fixed_wavenumber_kinetics.settings import Position, Settings
from control_app.measurement_modules.fixed_wavenumber_kinetics.planner import Plan, build_plan, mircat_pulse_errors
from control_app.measurement_modules.fixed_wavenumber_kinetics.timing import TimingError, compile_timing, quantize_seconds


def profile_case(mode="single"):
    settings = Settings(mode=mode, condition_id="condition-example", sample_id="sample-example",
        preparation_id="prep-example", cell_id="cell-example", position_id="position-example",
        temperature_id="temp-example", positions=(Position(1944.2, selection_record_id="selection-example", band_assignment="A1"),),
        dark_control_record_id="dark-example", artifact_control_record_id="artifact-example")
    sample = {"demodulator_index": 0, "input_index": 0, "rate_sps": 200., "timeconstant_s": .001, "order": 2}
    reference = {**sample, "demodulator_index": 1, "input_index": 1}
    profile = {"qualification_kind": "simulation", "record_id": "SIMULATED-profile-only", "condition_id": settings.condition_id,
        "condition_profile": settings.condition_profile, "configuration_id": "SIMULATED-config", "sample": sample, "reference": reference,
        "topology_record_id": "SIMULATED-topology", "acquisition_response_record_id": "SIMULATED-response",
        "temperature_record_id": "SIMULATED-temperature", "dose_record_id": "SIMULATED-dose", "reset_record_id": "SIMULATED-reset",
        "settling_s": .05, "tune_tolerance_cm1": .05, "timing_rate_sps": 10000., "timing_demodulator_index": 2,
        "pump_marker_bit": 16, "pump_marker_min_width_s": .001, "maximum_aggregate_rate_sps": 100000.,
        "continuous_poll_lossless_qualified": True, "baseline_drift_fraction": .01, "baseline_cv_limit": .05,
        "reset_tolerance_fraction": .02, "minimum_event_interval_s": 20.,
        "probe_recipe": {"clock": {"frequency": "1000Hz"}, "predivider": 1,
            "channels": {ch: {"enabled": ch != "D", "delay": "0s", "width": "100ns", "polarity": "positive", "termination": "50OHM"} for ch in "ABCD"}},
        "hf2li": {"signal_inputs": {"0": {"range": 1.}}, "pll": {"enabled": True}},
        "mircat": {"qcl": 1, "pulse_width_ns": 20, "pulse_rate_hz": 3000},
        "timing": {"input_frequency_hz": 1000., "fire_delay_s": .001, "q_switch_delay_s": .002,
                   "fire_width_s": .0001, "q_switch_width_s": .0001,
                   "fire_polarity": "positive", "q_switch_polarity": "positive", "termination": "50OHM"},
        "overhead_estimates_s": {k: .1 for k in ("configuration", "upload_per_frame", "tune_per_position", "restoration", "saving", "analysis")}}
    selection = {"schema_version": "1.0", "record_id": "selection-example", "accepted": True, "sample_id": settings.sample_id,
        "condition_id": settings.condition_id, "preparation_id": settings.preparation_id, "cell_id": settings.cell_id,
        "positions": [{"wavenumber_cm1": settings.positions[0].wavenumber_cm1}]}
    return settings, {"operating_profile": profile, "sample_selection": selection}


def recipe(**overrides):
    values = dict(pre_observation_s=1., post_observation_s=10., input_frequency_hz=1000.,
                  fire_delay_s=.001, q_switch_delay_s=.002, fire_width_s=.0001, q_switch_width_s=.0001)
    values.update(overrides)
    return compile_timing(**values)


def test_timing_determinism_complete_channels_finite_pumps_and_original_epoch():
    one = recipe()
    assert one.to_dict() == recipe().to_dict()
    assert one.expected_pump_count == 1
    assert sum(f["channels"]["A"]["enabled"] for f in one.frames) == 1
    assert sum(f["channels"]["B"]["enabled"] for f in one.frames) == 1
    assert one.frames[0]["kind"] == "probe_only_baseline"
    assert one.frames[-1]["kind"] == "terminal_all_off"
    assert all(set(f["channels"]) == set("ABCD") for f in one.frames)
    assert all(not f["channels"][ch]["enabled"] for f in one.frames for ch in "CD")
    assert all(f["train_count"] == 0 and f["frame_repetitions"] == 1 for f in one.frames)
    assert one.pump_command_offsets_s == (one.frame_period_s + .002,)
    assert one.selected_post_observation_s >= 10.


def test_no_pump_control_is_electrically_off_even_zero_additional_train_count():
    control = recipe(pump_enabled=False)
    assert control.expected_pump_count == 0 and control.pump_command_offsets_s == ()
    assert not any(f["channels"][ch]["enabled"] for f in control.frames for ch in "ABCD")


def test_long_capture_extends_baseline_explicitly_without_continuous_split():
    long = recipe(pre_observation_s=.01, post_observation_s=1200.)
    assert long.physical_frame_count <= 8192
    assert long.selected_pre_observation_s >= .01
    assert long.selected_post_observation_s >= 1200.
    assert long.requested_pre_observation_s == .01
    assert sum(f["channels"]["B"]["enabled"] for f in long.frames) == 1
    with pytest.raises(TimingError, match="predivider"):
        recipe(pre_observation_s=5000, input_frequency_hz=16e6)


def test_timing_quantization_and_documented_limits():
    assert quantize_seconds(.000000000015) == .00000000002
    assert recipe(q_switch_delay_s=.002000000004).frames[1]["channels"]["B"]["delay"] == "0.00200000000s"
    with pytest.raises(TimingError, match="10 ps"):
        recipe(edge_quantum_s=1e-12)
    with pytest.raises(TimingError, match="3600"):
        recipe(fire_delay_s=3600, q_switch_delay_s=3600, fire_width_s=1)
    with pytest.raises(TimingError, match="Q-switch"):
        recipe(fire_delay_s=.01, q_switch_delay_s=.001)


def test_default_plan_requires_a_position_but_no_files_and_is_hardware_free():
    p = build_plan(Settings())
    assert not p.ready and any("wavenumber" in issue for issue in p.validation_errors)
    p = build_plan(Settings(positions=(Position(1944.2),)))
    assert p.ready and not p.operational_ready
    assert all("profile" not in item and "record" not in item for item in p.readiness_items)
    assert p.actual == {} and p.timing is None
    assert Settings.from_dict(json.loads(json.dumps(Settings().to_dict()))) == Settings()


def test_complete_synthetic_plan_roundtrip_modes_are_independent():
    s, evidence = profile_case()
    p = build_plan(s, evidence=evidence)
    assert p.ready, p.readiness_items
    assert p.to_dict()["ready"] and p.blocks[0].position_index == 0
    assert Plan.from_dict(json.loads(json.dumps(p.to_dict()))).to_dict() == p.to_dict()
    sd, ed = profile_case("dual")
    dual = build_plan(sd, evidence=ed)
    assert dual.ready, dual.readiness_items
    assert dual.estimates["aggregate_rate_sps"] > p.estimates["aggregate_rate_sps"]
    assert dual.estimates["sequential_blank_s"] == 0
    assert p.estimates["sequential_blank_s"] == 0
    assert dual.operational_ready and p.operational_ready
    dual.resolved["sample"]["rate_sps"] = 1
    assert p.resolved["sample"]["rate_sps"] == 200
    assert evidence["operating_profile"]["sample"]["rate_sps"] == 200


def test_finite_budget_cadence_and_material_independent_event_count():
    s, evidence = profile_case()
    repeat = replace(s, technical_repetitions=2)
    assert "exceed" in " ".join(build_plan(repeat, evidence=evidence).validation_errors)
    repeat = replace(repeat, event_budget=2)
    p = build_plan(repeat, evidence=evidence)
    assert p.ready and p.total_pump_events == 2
    assert not any(block.reset_required for block in p.blocks)
    evidence["operating_profile"].pop("reset_record_id")
    assert build_plan(repeat, evidence=evidence).operational_ready
    assert "10 Hz" in " ".join(build_plan(replace(repeat, minimum_event_interval_s=.05), evidence=evidence).validation_errors)
    cryo = replace(repeat, condition_profile="cryo_hrp_co")
    assert build_plan(cryo, evidence=evidence).operational_ready


def test_missing_reference_and_aggregate_capacity_are_distinct_errors():
    s, evidence = profile_case("dual")
    evidence["operating_profile"].pop("reference")
    p = build_plan(s, evidence=evidence)
    assert any("reference" in item for item in p.readiness_items)
    _, evidence = profile_case("dual")
    evidence["operating_profile"]["maximum_aggregate_rate_sps"] = 100
    assert any("aggregate throughput" in item for item in build_plan(s, evidence=evidence).validation_errors)


def test_retention_and_declared_budget_limits_are_enforced():
    s, evidence = profile_case()
    p = build_plan(replace(s, post_observation_s=600), evidence=evidence)
    assert p.ready
    assert p.estimates["peak_memory_bytes"] < p.estimates["storage_bytes"]
    assert p.estimates["continuous_per_block"] is True
    memory = build_plan(replace(s, retention_strategy="bounded_memory", memory_limit_mb=.01), evidence=evidence)
    assert any("memory budget" in v for v in memory.validation_errors)
    storage = build_plan(replace(s, storage_limit_mb=.01), evidence=evidence)
    assert any("storage budget" in v for v in storage.validation_errors)


def test_preparation_standalone_no_selection_no_pump_and_blank_complete_order():
    s, evidence = profile_case()
    s = replace(s, technical_repetitions=2, events_per_position=2, event_budget=4,
                positions=(replace(s.positions[0], selection_record_id=""),), dark_control_record_id="", artifact_control_record_id="")
    evidence.pop("sample_selection")
    assert build_plan(s, evidence=evidence).operational_ready
    # Pump outputs are irrelevant to raw unpumped preparation.
    evidence["operating_profile"].pop("timing")
    preliminary = build_plan(s, evidence=evidence, purpose="preliminary")
    blank = build_plan(s, evidence=evidence, purpose="blank")
    assert preliminary.operational_ready, preliminary.readiness_items
    assert len(preliminary.blocks) == 1 and preliminary.total_pump_events == 0
    assert blank.operational_ready and len(blank.blocks) == 4 and blank.total_pump_events == 0
    assert blank.settings == s and preliminary.settings == s
    assert all(b.timing is None for b in blank.blocks)


def test_optional_host_sample_exchange_is_retained_but_never_gates_raw_capture():
    s, evidence = profile_case()
    native = {"schema_version": 1, "record_kind": "sample_spectral_selection", "disposition": "accepted",
              "selection_id": "selection-example", "sample_id": s.sample_id, "condition_id": s.condition_id,
              "producer_instance_id": "fixed_wavenumber_kinetics:single", "accepted_by": "reviewer",
              "accepted_utc": "2026-01-01T00:00:00Z", "condition": {"preparation_id": s.preparation_id, "cell_id": s.cell_id},
              "source": {"producer_run_id": "prelim-example", "native_path": "native.json", "created_utc": "2026-01-01T00:00:00Z", "software_version": "1.0"},
              "windows": [{"lower_cm1": 1944.2, "upper_cm1": 1944.2, "center_cm1": 1944.2}]}
    evidence["sample_selection"] = native
    assert build_plan(s, evidence=evidence).ready
    native["condition"].pop("cell_id")
    p = build_plan(s, evidence=evidence)
    assert p.operational_ready
    assert p.evidence_records["sample_selection"] == native


def test_band_assignments_and_legacy_material_labels_do_not_control_acquisition():
    s, evidence = profile_case()
    s = replace(s, condition_profile="rt_mbco", positions=(replace(s.positions[0], band_assignment="A0"),))
    evidence["operating_profile"]["condition_profile"] = s.condition_profile
    p = build_plan(s, evidence=evidence)
    assert p.operational_ready and not p.readiness_items


def test_legacy_temperature_and_fresh_state_metadata_never_limit_event_count():
    s, evidence = profile_case()
    s = replace(s, condition_profile="cryo_hrp_co", technical_repetitions=2, event_budget=2,
                fresh_state_record_ids=("declared-fresh-state",))
    p = build_plan(s, evidence=evidence)
    assert p.operational_ready and p.total_pump_events == 2
    assert p.settings.fresh_state_record_ids == ("declared-fresh-state",)


def test_probe_frequency_must_equal_actual_frame_input_carrier():
    s, evidence = profile_case()
    evidence["operating_profile"]["probe_recipe"]["clock"]["frequency"] = "2kHz"
    p = build_plan(s, evidence=evidence)
    assert any("frame-input frequency" in v for v in p.validation_errors)


def test_diagnostic_thresholds_are_editable_and_estimates_include_prearm_capture():
    s, evidence = profile_case()
    p = build_plan(s, evidence=evidence)
    assert p.blocks[0].duration_s == s.pre_observation_s + p.timing.duration_s
    assert p.blocks[0].pre_observation_s == s.pre_observation_s + p.timing.selected_pre_observation_s
    assert build_plan(replace(s, baseline_drift_fraction=.2), evidence=evidence).operational_ready


def test_oversized_repeated_frame_tables_stay_saveable_without_duplicate_allocation():
    s, evidence = profile_case()
    s = replace(s, pre_observation_s=.1, post_observation_s=200., chunk_duration_s=.1,
                technical_repetitions=10, event_budget=10, memory_limit_mb=1.)
    p = build_plan(s, evidence=evidence)
    assert p.validation_errors and p.estimates["serialized_plan_bytes"] > 8*1024**2
    stored = p.to_dict()
    assert all(row["timing_program_ref"] == "selected.finite_timing" for row in stored["blocks"])
    loaded = Plan.from_dict(stored)
    assert loaded.to_dict() == stored


def test_unrelated_checksum_changes_never_gate_planning():
    s, evidence = profile_case()
    evidence["operating_profile"]["checksum"] = "previous"
    assert build_plan(s, evidence=evidence).ready
    evidence["operating_profile"]["checksum"] = "changed"
    assert build_plan(s, evidence=evidence).ready


@pytest.mark.parametrize("field", ["fire_polarity", "q_switch_polarity", "termination"])
def test_actual_runtime_polarity_and_loading_required_only_for_pumped_capture(field):
    s, evidence = profile_case()
    evidence["operating_profile"]["timing"].pop(field)
    live = evidence["operating_profile"]
    p = build_plan(s, live_readbacks=live)
    assert p.ready and not p.operational_ready and p.timing is None
    assert any(field in issue for issue in p.readiness_items)
    assert build_plan(replace(s, pump_enabled=False), live_readbacks=live).operational_ready


def test_temperature_is_optional_metadata_without_temperature_specific_warnings_or_gates():
    s, evidence = profile_case()
    for value in (None, 77.0, 295.0):
        p = build_plan(replace(s, condition_profile="arbitrary-label", temperature_k=value), evidence=evidence)
        assert p.operational_ready
        assert all("temperature" not in issue.lower() for issue in (*p.readiness_items, *p.warnings))


def test_live_readbacks_enable_raw_capture_without_any_promoted_or_sample_evidence():
    _, evidence = profile_case()
    runtime_keys = {"sample", "reference", "probe_recipe", "mircat", "hf2li", "timing", "timing_rate_sps",
                    "timing_demodulator_index", "tune_tolerance_cm1"}
    live = {key: value for key, value in evidence["operating_profile"].items() if key in runtime_keys}
    settings = Settings(positions=(Position(1944.2),), sample_label="ordinary sample")
    p = build_plan(settings, live_readbacks=live)
    assert p.ready and p.operational_ready, p.readiness_items
    assert p.evidence_records == {}
    assert p.actual["installed_readbacks"] == live
    assert "acquisition_response" not in p.resolved
    assert p.resolved["settling_s"] == 5*live["sample"]["order"]*live["sample"]["timeconstant_s"]
    assert "engineering_estimate" in p.resolved["value_sources"]["settling_s"]
    assert any("fits unresolved" in warning for warning in p.warnings)


@pytest.mark.parametrize("override,field,value", [
    ("sample_rate_sps", "rate_sps", 333.),
    ("sample_timeconstant_s", "timeconstant_s", .005),
    ("sample_filter_order", "order", 5),
])
def test_one_exact_override_does_not_freeze_other_automatic_fields(override, field, value):
    s, evidence = profile_case("dual")
    s = replace(s, **{override: value})
    previous = deepcopy(evidence["operating_profile"])
    live = deepcopy(previous)
    live["sample"].update(rate_sps=500., timeconstant_s=.02, order=3)
    live["reference"].update(rate_sps=400., timeconstant_s=.03, order=4)
    p = build_plan(s, {"fixed_wavenumber_kinetics": previous}, evidence, live_readbacks=live)
    assert p.operational_ready, p.readiness_items
    for key in ("rate_sps", "timeconstant_s", "order"):
        assert p.resolved["sample"][key] == (value if key == field else live["sample"][key])
        assert p.resolved["reference"][key] == live["reference"][key]
    assert p.resolved["value_sources"][f"sample.{field}"] == "user_override"
    assert p.resolved["value_sources"]["reference.rate_sps"] == "installed_readback"


def test_probe_and_pump_overrides_change_only_explicit_fields_and_required_carrier_recipients():
    s, evidence = profile_case()
    live = deepcopy(evidence["operating_profile"])
    s = replace(s, probe_width_ns=50., probe_rate_hz=2000., pump_q_switch_width_s=.0002)
    p = build_plan(s, live_readbacks=live)
    assert p.operational_ready, p.readiness_items
    assert p.resolved["mircat"]["pulse_width_ns"] == 50.
    assert p.resolved["mircat"]["pulse_rate_hz"] == live["mircat"]["pulse_rate_hz"]
    assert p.resolved["probe_recipe"]["clock"]["frequency"] == "2000Hz"
    assert p.resolved["probe_recipe"]["channels"] == live["probe_recipe"]["channels"]
    assert p.resolved["timing"]["q_switch_width_s"] == .0002
    assert p.resolved["timing"]["fire_width_s"] == live["timing"]["fire_width_s"]
    assert p.resolved["timing"]["input_frequency_hz"] == 2000.
    assert p.resolved["hf2li"]["pll"]["freqcenter_hz"] == 2000.
    assert live["timing"]["q_switch_width_s"] == .0001


def test_no_pump_ignores_unrelated_pump_input_clock_and_runtime_stream_qualification():
    s, evidence = profile_case()
    live = deepcopy(evidence["operating_profile"])
    live["timing"] = {"input_frequency_hz": 9999.}
    live.pop("continuous_poll_lossless_qualified")
    p = build_plan(replace(s, pump_enabled=False), live_readbacks=live)
    assert p.operational_ready and p.timing is None
    assert p.total_pump_events == 0


def test_external_probe_override_preserves_independent_internal_rate_and_provenance():
    s, evidence = profile_case()
    live = deepcopy(evidence["operating_profile"])
    live["mircat"]["pulse_rate_hz"] = 2_300_000.
    live["mircat_readback"] = {"pulse_limits": {"max_pulse_rate_hz": 3_000_000.,
        "max_pulse_width_ns": 100., "max_duty_cycle": 10.}}
    p = build_plan(replace(s, probe_rate_hz=2_000_000.), live_readbacks=live)
    assert p.operational_ready, p.validation_errors
    assert p.resolved["mircat"]["pulse_rate_hz"] == 2_300_000.
    assert p.resolved["timing"]["input_frequency_hz"] == 2_000_000.
    assert p.resolved["value_sources"]["mircat.pulse_rate_hz"] == "installed_readback"
    assert p.resolved["value_sources"]["probe_rate_hz"] == "user_override"


@pytest.mark.parametrize("params,external,match", [
    ({"pulse_rate_hz": 1000., "pulse_width_ns": 20.}, 1000., "strictly greater"),
    ({"pulse_rate_hz": 1000., "pulse_width_ns": 20.}, 1001., "strictly greater"),
    ({"pulse_rate_hz": 0., "pulse_width_ns": 20.}, 1000., "internal pulse rate"),
    ({"pulse_rate_hz": float("inf"), "pulse_width_ns": 20.}, 1000., "internal pulse rate"),
    ({"pulse_rate_hz": True, "pulse_width_ns": 20.}, 1000., "internal pulse rate"),
    ({"pulse_rate_hz": 2000., "pulse_width_ns": 0.}, 1000., "pulse width"),
    ({"pulse_rate_hz": 2000., "pulse_width_ns": float("nan")}, 1000., "pulse width"),
    ({"pulse_rate_hz": 2000., "pulse_width_ns": 20.}, float("nan"), "external trigger rate"),
])
def test_mircat_pulse_helper_rejects_invalid_actual_settings(params, external, match):
    assert any(match in error for error in mircat_pulse_errors(params, external))


def test_mircat_sdk_limits_use_internal_duty_percentage_and_no_invented_margin():
    params = {"pulse_rate_hz": 2_000_000., "pulse_width_ns": 50.}
    assert mircat_pulse_errors(params, 1_999_999., {"max_duty_cycle": 10.}) == ()
    assert any("10%" in issue for issue in mircat_pulse_errors(params, 1_900_000., {"max_duty_cycle": 9.9}))
    assert any("max_pulse_rate_hz" in issue for issue in mircat_pulse_errors(params, 1_900_000., {"max_pulse_rate_hz": 1_950_000.}))
    assert any("max_pulse_width_ns" in issue for issue in mircat_pulse_errors(params, 1_900_000., {"max_pulse_width_ns": 49.}))
    assert mircat_pulse_errors(params, 1_900_000.) == ()


def test_planner_reports_equal_internal_rate_and_sdk_limit_as_invalid_operating_values():
    s, evidence = profile_case()
    live = deepcopy(evidence["operating_profile"])
    live["mircat"]["pulse_rate_hz"] = 1000.
    equal = build_plan(s, live_readbacks=live)
    assert not equal.ready and any("strictly greater" in error for error in equal.validation_errors)
    live["mircat"]["pulse_rate_hz"] = 3000.
    live["mircat_readback"] = {"pulse_limits": {"max_pulse_width_ns": 19.}}
    limited = build_plan(s, live_readbacks=live)
    assert not limited.ready and any("max_pulse_width_ns" in error for error in limited.validation_errors)


@pytest.mark.parametrize("source", ["configured", "optional_profile", "installed_readback"])
def test_stale_qcl2_route_becomes_qcl1_without_relabeling_pulse_or_limit_data(source):
    s, evidence = profile_case()
    old = deepcopy(evidence["operating_profile"])
    old["mircat"] = {"qcl": 2, "pulse_rate_hz": 123456., "pulse_width_ns": 88.}
    old["mircat_readback"] = {"qcl": 2, "pulse_limits": {"max_pulse_width_ns": 10.}}
    old["qcl_ranges"] = [{"qcl": 2, "min_cm1": 1900., "max_cm1": 2000.}]
    arguments = {"configuration": {"fixed_wavenumber_kinetics": old}} if source == "configured" else (
        {"evidence": {"operating_profile": old}} if source == "optional_profile" else {"live_readbacks": old})
    p = build_plan(s, **arguments)
    assert p.ready and not p.operational_ready
    assert p.resolved["mircat"] == {"qcl": 1}
    assert not p.resolved["mircat_readback"].get("pulse_limits")
    assert p.resolved["qcl_ranges"] == []
    assert p.resolved["value_sources"]["mircat.pulse_rate_hz"] == "unresolved"
    assert p.evidence_records["historical_qcl_routing"][source]["mircat"] == old["mircat"]
    assert old["mircat"]["qcl"] == 2


def test_live_qcl1_overrides_saved_qcl2_without_inheriting_its_pulse_limits_or_ranges():
    s, evidence = profile_case()
    old = evidence["operating_profile"]
    old["mircat"] = {"qcl": 2, "pulse_rate_hz": 100., "pulse_width_ns": 500.}
    old["mircat_readback"] = {"pulse_limits": {"max_duty_cycle": .001}}
    old["qcl_ranges"] = [{"qcl": 2, "min_cm1": 1800., "max_cm1": 2000.}]
    live = {"mircat": {"qcl": 1, "pulse_rate_hz": 2_300_000., "pulse_width_ns": 100.},
        "qcl_ranges": [{"qcl": 1, "min_cm1": 1900., "max_cm1": 2000.}]}
    p = build_plan(replace(s, probe_rate_hz=2_000_000.), evidence=evidence, live_readbacks=live)
    assert p.operational_ready, (p.validation_errors, p.readiness_items)
    assert p.resolved["mircat"] == live["mircat"]
    assert p.resolved["qcl_ranges"] == live["qcl_ranges"]
    assert not p.resolved["mircat_readback"].get("pulse_limits")
    assert p.resolved["value_sources"]["mircat.pulse_rate_hz"] == "installed_readback"
    assert p.actual["installed_readbacks"] == live
    partial = deepcopy(live)
    partial["mircat"].pop("pulse_width_ns")
    unresolved = build_plan(s, evidence=evidence, live_readbacks=partial)
    assert not unresolved.operational_ready
    assert "pulse_width_ns" not in unresolved.resolved["mircat"]


def test_stale_live_qcl2_does_not_fall_back_to_lower_priority_pulse_values():
    s, evidence = profile_case()
    p = build_plan(s, evidence=evidence, live_readbacks={
        "mircat": {"qcl": 2, "pulse_rate_hz": 4000., "pulse_width_ns": 25.}})
    assert p.ready and not p.operational_ready
    assert p.resolved["mircat"] == {"qcl": 1}
    assert p.actual["installed_readbacks"]["mircat"]["qcl"] == 2


def test_saved_plan_normalizes_historical_route_and_preserves_explicit_width_and_original_record():
    s, evidence = profile_case()
    s = replace(s, probe_width_ns=50.)
    saved = build_plan(s, evidence=evidence).to_dict()
    saved["resolved"]["mircat"] = {"qcl": 2, "pulse_rate_hz": 1234., "pulse_width_ns": 88.}
    saved["resolved"]["qcl_ranges"] = [{"qcl": 2, "min_cm1": 1900., "max_cm1": 2000.}]
    original = deepcopy(saved)
    p = Plan.from_dict(saved)
    assert p.ready and not p.operational_ready
    assert p.resolved["mircat"] == {"qcl": 1, "pulse_width_ns": 50.}
    assert p.settings == s and p.resolved["qcl_ranges"] == []
    assert p.resolved["value_sources"]["mircat.pulse_width_ns"] == "user_override"
    assert p.evidence_records["historical_qcl_routing"]["saved_plan"]["mircat"] == original["resolved"]["mircat"]
    assert saved == original
    assert Plan.from_dict(p.to_dict()).to_dict() == p.to_dict()


def test_hard_internal_duty_boundary_and_tighter_sdk_limits_are_independent_of_rate_relationship():
    params = {"pulse_rate_hz": 3_000_000., "pulse_width_ns": 100.}
    assert mircat_pulse_errors(params, 2_900_000.) == ()
    assert mircat_pulse_errors(params, 2_900_000., {"max_duty_cycle": 80.}) == ()
    assert any("SDK max_duty_cycle limit 25%" in error for error in
        mircat_pulse_errors(params, 2_900_000., {"max_duty_cycle": 25.}))
    over = {**params, "pulse_width_ns": 100.000001}
    assert any("30% maximum" in error for error in mircat_pulse_errors(over, 2_900_000.))
    assert any("30% maximum" in error for error in mircat_pulse_errors(over, 2_900_000., {"max_duty_cycle": 80.}))
    equal = mircat_pulse_errors(params, 3_000_000.)
    assert any("strictly greater" in error for error in equal)
    assert not any("duty" in error for error in equal)


def test_external_duty_is_checked_before_connection_at_the_requested_thirty_percent_boundary():
    s = Settings(positions=(Position(1944.2),), probe_rate_hz=2_000_000., probe_width_ns=150.)
    boundary = build_plan(s)
    assert boundary.ready and not boundary.operational_ready
    over = build_plan(replace(s, probe_width_ns=150.000001))
    assert not over.ready
    assert any("External probe" in error and "30%" in error for error in over.validation_errors)
    loaded = Plan.from_dict(boundary.to_dict())
    assert loaded.ready
    invalid_saved = boundary.to_dict()
    invalid_saved["settings"]["probe_width_ns"] = 151.
    assert not Plan.from_dict(invalid_saved).ready


def test_actual_internal_duty_can_fail_while_external_product_is_exactly_thirty_percent():
    s, evidence = profile_case()
    live = deepcopy(evidence["operating_profile"])
    live["mircat"].update(pulse_rate_hz=2_300_000., pulse_width_ns=150.)
    live["mircat_readback"] = {"qcl": 1, "pulse_limits": {"max_duty_cycle": 80.}}
    p = build_plan(replace(s, probe_rate_hz=2_000_000.), live_readbacks=live)
    assert not p.ready
    assert any("internal duty cycle 34.5%" in error and "30%" in error for error in p.validation_errors)
    assert not any("External probe" in error for error in p.validation_errors)


@pytest.mark.parametrize("key,value", [("pulse_rate_hz", float("nan")),
    ("pulse_width_ns", float("inf")), ("pulse_width_ns", 0.)])
def test_planner_rejects_invalid_qcl1_actual_pulse_values(key, value):
    s, evidence = profile_case()
    live = deepcopy(evidence["operating_profile"])
    live["mircat"][key] = value
    p = build_plan(s, live_readbacks=live)
    assert not p.ready and any("finite and positive" in error for error in p.validation_errors)


@pytest.mark.parametrize("updates", [{"pre_observation_s": float("nan")}, {"event_budget": True},
    {"technical_repetitions": 1.5}, {"baseline_window_s": (0, 1)}, {"retention_strategy": "ring_buffer"}])
def test_invalid_values_are_reviewable_errors(updates):
    s, evidence = profile_case()
    p = build_plan(replace(s, **updates), evidence=evidence)
    assert p.validation_errors and not p.ready
