"""Bounded, hardware-free scientific planner and deterministic timing checks."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from control_app.measurement_modules.fixed_wavenumber_kinetics.settings import Position, Settings
from control_app.measurement_modules.fixed_wavenumber_kinetics.planner import Plan, build_plan
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
        "mircat": {"qcl": 1, "pulse_width_ns": 20, "pulse_rate_hz": 1000},
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


def test_default_plan_is_editable_unready_and_hardware_free():
    p = build_plan(Settings())
    assert not p.ready and not p.validation_errors
    assert any("measured operating profile" in item for item in p.readiness_items)
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
    assert p.estimates["sequential_blank_s"] > 0
    dual.resolved["sample"]["rate_sps"] = 1
    assert p.resolved["sample"]["rate_sps"] == 200
    assert evidence["operating_profile"]["sample"]["rate_sps"] == 200


def test_budget_cadence_reset_and_cryo_no_repeat():
    s, evidence = profile_case()
    repeat = replace(s, technical_repetitions=2)
    assert "exceed" in " ".join(build_plan(repeat, evidence=evidence).validation_errors)
    repeat = replace(repeat, event_budget=2)
    p = build_plan(repeat, evidence=evidence)
    assert p.ready and p.total_pump_events == 2
    assert not p.blocks[0].reset_required and p.blocks[1].reset_required
    evidence["operating_profile"].pop("reset_record_id")
    assert any("reset record" in issue for issue in build_plan(repeat, evidence=evidence).readiness_items)
    assert "10 Hz" in " ".join(build_plan(replace(repeat, minimum_event_interval_s=.05), evidence=evidence).validation_errors)
    cryo = replace(repeat, condition_profile="cryo_hrp_co")
    assert "Cryogenic no-repeat" in " ".join(build_plan(cryo, evidence=evidence).validation_errors)


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
    assert not build_plan(s, evidence=evidence).ready
    preliminary = build_plan(s, evidence=evidence, purpose="preliminary")
    blank = build_plan(s, evidence=evidence, purpose="blank")
    assert preliminary.ready, preliminary.readiness_items
    assert len(preliminary.blocks) == 1 and preliminary.total_pump_events == 0
    assert blank.ready and len(blank.blocks) == 4 and blank.total_pump_events == 0
    assert blank.settings == s and preliminary.settings == s
    assert all(not f["channels"]["A"]["enabled"] for b in blank.blocks for f in b.timing.frames)


def test_host_native_sample_exchange_and_missing_condition_identifiers():
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
    assert any("cell_id" in v for v in build_plan(s, evidence=evidence).readiness_items)


def test_mb_a1_first_and_extensions_require_quantification():
    s, evidence = profile_case()
    s = replace(s, condition_profile="rt_mbco", positions=(replace(s.positions[0], band_assignment="A0"),))
    evidence["operating_profile"]["condition_profile"] = s.condition_profile
    p = build_plan(s, evidence=evidence)
    assert any("starts at" in v for v in p.readiness_items)
    assert any("extension" in v for v in p.readiness_items)


def test_cryo_fresh_state_ids_do_not_invent_automatic_repositioning():
    s, evidence = profile_case()
    s = replace(s, condition_profile="cryo_hrp_co", technical_repetitions=2, event_budget=2,
                fresh_state_record_ids=("declared-fresh-state",))
    p = build_plan(s, evidence=evidence)
    assert any("separate operation" in v for v in p.validation_errors)


def test_probe_frequency_must_equal_actual_frame_input_carrier():
    s, evidence = profile_case()
    evidence["operating_profile"]["probe_recipe"]["clock"]["frequency"] = "2kHz"
    p = build_plan(s, evidence=evidence)
    assert any("frame-input frequency" in v for v in p.validation_errors)


def test_selected_threshold_needs_condition_evidence_and_estimate_includes_prearm_capture():
    s, evidence = profile_case()
    p = build_plan(s, evidence=evidence)
    assert p.blocks[0].duration_s == s.pre_observation_s + p.timing.duration_s
    assert p.blocks[0].pre_observation_s == s.pre_observation_s + p.timing.selected_pre_observation_s
    assert any("proposal" in v for v in build_plan(replace(s, baseline_drift_fraction=.2), evidence=evidence).readiness_items)


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
def test_operating_profile_must_explicitly_qualify_pump_polarity_and_loading(field):
    s, evidence = profile_case()
    # A capability/configuration value does not silently become measured recipe evidence.
    configuration = {"fixed_wavenumber_kinetics": deepcopy(evidence["operating_profile"])}
    evidence["operating_profile"]["timing"].pop(field)
    p = build_plan(s, configuration, evidence)
    assert not p.ready and p.timing is None
    assert any(field in issue for issue in p.readiness_items)


def test_missing_temperature_limits_claims_and_cryo_requires_retained_qualification():
    s, evidence = profile_case()
    assert any("temperature is unentered" in issue for issue in build_plan(s, evidence=evidence).warnings)
    s = replace(s, condition_profile="cryo_hrp_co")
    evidence["operating_profile"]["condition_profile"] = s.condition_profile
    p = build_plan(s, evidence=evidence)
    assert not p.ready
    assert any("entered measured temperature" in issue for issue in p.readiness_items)
    s = replace(s, temperature_k=77.0)
    p = build_plan(s, evidence=evidence)
    assert any("explicit profile uncertainty" in issue for issue in p.readiness_items)
    evidence["operating_profile"]["temperature_uncertainty_k"] = .1  # Synthetic fixture only.
    assert build_plan(s, evidence=evidence).ready
    evidence["operating_profile"].pop("temperature_uncertainty_k")
    evidence["operating_profile"]["temperature_status"] = "condition_source_measured"
    assert build_plan(s, evidence=evidence).ready


@pytest.mark.parametrize("updates", [{"pre_observation_s": float("nan")}, {"event_budget": True},
    {"technical_repetitions": 1.5}, {"baseline_window_s": (0, 1)}, {"retention_strategy": "ring_buffer"}])
def test_invalid_values_are_reviewable_errors(updates):
    s, evidence = profile_case()
    p = build_plan(replace(s, **updates), evidence=evidence)
    assert p.validation_errors and not p.ready
