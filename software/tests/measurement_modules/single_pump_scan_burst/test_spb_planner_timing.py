"""Offline scientific-plan and installed frame protocol verification."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from control_app.devices.t660_service import T660Service
from control_app.measurement_modules.single_pump_scan_burst.settings import (
    Capabilities, Settings, example_settings, resolve_settings, resolve_live_settings,
)
from control_app.measurement_modules.single_pump_scan_burst.planner import (
    Plan, compile_blank_blocks, compile_plan, compile_preliminary, logarithmic_times,
)


class RecordingT660(T660Service):
    """An injected protocol peer; no connection, discovery or real commands."""
    def __init__(self):
        super().__init__("t660_2", {})
        self.commands, self.values, self.pending, self.stored = [], {}, {}, []

    def command(self, command, *, expect_response=True, delay_s=0.04):
        if ";" in command:
            return ";".join(self.command(part) for part in command.split(";"))
        command = command.lstrip(":")
        self.commands.append(command)
        if command == "FEATure:FRAMe?":
            return "1"
        if command.endswith("?"):
            return self.values.get(command[:-1], "0")
        key, _, value = command.partition(" ")
        self.values[key] = value
        if key.startswith(("TIME:QUEue", "CHANnel:QUEue")):
            self.pending[key + value.split(",")[0] if "," in value else key] = value
        if key == "TFRame:STORe":
            self.stored.append(deepcopy(self.pending))
        return "OK"


def test_compact_defaults_resolve_without_hardware_or_metadata():
    settings = Settings()
    plan = compile_plan(settings)
    assert settings.scan_speed_cm1_s == 5000.0 and settings.probe_rate_hz is None
    assert plan.valid and plan.ready and plan.blocks and not plan.readiness
    assert plan.requested_settings is settings
    assert plan.blocks[0].planned_end_s >= settings.early_observation_s
    assert settings.pump_polarity == settings.process_polarity == "negative"
    assert plan.selected_values["probe_rate_hz"]["requested"] is None
    assert plan.selected_values["probe_rate_hz"]["selected"] == 2000000


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_deterministic_finite_schedule_contains_exactly_one_pump_and_final_state(mode):
    settings = example_settings(mode)
    plan = compile_plan(settings)
    assert plan.valid, plan.errors
    assert plan.ready and not plan.readiness
    assert plan.to_dict() == compile_plan(settings).to_dict()
    assert Plan.from_dict(json.loads(json.dumps(plan.to_dict()))).to_dict() == plan.to_dict()
    assert plan.blocks[0].kind == "early" and plan.blocks[-1].kind == "final"
    assert plan.blocks[-1].planned_end_s == pytest.approx(settings.observation_limit_s)
    assert plan.pump_count == 1
    assert all(not frame["channels"]["A"]["enabled"] and not frame["channels"]["B"]["enabled"]
               for block in plan.blocks[1:] for frame in block.frames)
    assert all(not channel["enabled"] for block in plan.blocks for channel in block.frames[-1]["channels"].values())
    assert all(set(frame["channels"]) == set("ABCD") and frame["train_count"] == 0
               for block in plan.blocks for frame in block.frames)


def test_reusable_brief_blank_and_preliminary_never_pump():
    plan = compile_plan(example_settings())
    blank = compile_blank_blocks(plan)
    assert len(blank) == 1 and blank[0].scan_count == plan.settings.preliminary_scan_count
    assert blank[0].planned_elapsed_s == 0 and blank[0].duration_s < 1
    for block in (*blank, compile_preliminary(plan)):
        assert not block.pump_enabled
        assert all(not frame["channels"][ch]["enabled"] for frame in block.frames for ch in "AB")


def test_logarithmic_schedule_does_not_put_pre_pump_time_on_log_axis():
    assert logarithmic_times(1, 1000, 4) == (1, 10, 100, 1000)
    with pytest.raises(ValueError, match="positive"):
        logarithmic_times(-1, 10, 4)
    plan = compile_plan(example_settings())
    times = [b.planned_elapsed_s for b in plan.blocks if b.kind == "burst"]
    ratios = [b / a for a, b in zip(times, times[1:])]
    assert max(ratios) == pytest.approx(min(ratios))


def test_timing_quantization_records_requested_selected_and_unknown_actual():
    settings = replace(example_settings(), first_scan_delay_s=.001000000004,
                       scan_interval_s=.020000011)
    plan = compile_plan(settings)
    assert plan.valid, plan.errors
    delay = plan.selected_values["first_scan_delay_s"]
    assert delay["requested"] != delay["selected"]
    assert delay["selected"] == .001 and delay["unit"] == "s"
    assert delay["actual"] is None
    assert plan.blocks[0].frame_period_s >= settings.scan_interval_s


@pytest.mark.parametrize("changes,match", [
    ({"early_scan_count": 8192}, "continuous blocks cannot be silently split"),
    ({"scan_interval_s": .001}, "scan duration"),
    ({"probe_pulse_width_s": 400e-9}, "duty"),
    ({"sample_rate_hz": 699999}, "aggregate"),
    ({"process_polarity": "positive"}, "negative pulse"),
    ({"later_burst_times_s": (3.0, 2.0)}, "increasing"),
    ({"later_burst_times_s": (.1,)}, "overlap"),
    ({"observation_limit_s": .1}, "logarithmic"),
    ({"max_probe_exposure_s": 1e-7}, "exposure budget"),
    ({"max_memory_bytes": 1}, "RAM budget"),
    ({"storage_budget_bytes": 1}, "storage budget"),
    ({"probe_during_wait": True}, "dark inter-burst waits only"),
])
def test_impossible_or_inconsistent_scientific_plans_are_rejected(changes, match):
    plan = compile_plan(replace(example_settings(), **changes))
    assert not plan.valid
    assert any(match.lower() in error.lower() for error in plan.errors), plan.errors


@pytest.mark.parametrize("changes", [
    {"edge_quantum_s": 0}, {"frame_capacity": 0}, {"synthesizer_quantum_hz": float("nan")},
    {"hf2_aggregate_rate_max_hz": -1}, {"predivider_max": 0},
])
def test_malformed_capability_data_is_reported_before_arithmetic(changes):
    plan = compile_plan(example_settings(), replace(Capabilities(), **changes))
    assert not plan.valid and plan.errors


def test_longest_observation_brief_blank_and_chunk_memory_are_budgeted():
    plan = compile_plan(replace(example_settings(), observation_limit_s=86400))
    loaded = compile_plan(replace(plan.settings, blank_source="loaded"))
    dual = compile_plan(replace(plan.settings, mode="dual"))
    assert plan.valid
    assert plan.estimates["blank_observation_s"] == (plan.settings.preliminary_scan_count + 1) * plan.blocks[0].frame_period_s
    assert loaded.estimates["blank_observation_s"] == dual.estimates["blank_observation_s"] == 0
    assert plan.estimates["native_bytes"] > loaded.estimates["native_bytes"]
    assert 86400 <= plan.estimates["wall_time_min_s"] < 172800
    assert plan.estimates["peak_memory_bytes"] < plan.settings.max_memory_bytes
    assert plan.blocks[-1].planned_end_s == pytest.approx(86400)


def test_old_condition_metadata_cannot_change_numeric_planning():
    hrp = Settings()
    mb = replace(hrp, condition_id="77K-Mb-G-S")
    assert hrp.architecture_id == mb.architecture_id == "single_pump_scan_burst"
    assert compile_plan(hrp).blocks == compile_plan(mb).blocks
    resolved = resolve_settings(hrp, promoted_values={"record_id": "promoted-test-record", "values": {"probe_rate_hz": 123456}})
    assert resolved.probe_rate_hz == 2000000.
    assert "configuration" in resolved.settings_sources["probe_rate_hz"]
    assert hrp.probe_rate_hz is None
    assert resolve_settings(replace(hrp, probe_rate_hz=123456), installed_readbacks={"values": {"probe_rate_hz": 42}}).probe_rate_hz == 123456
    assert resolve_settings(hrp, installed_readbacks={"values": {"probe_rate_hz": 123}}).probe_rate_hz == 123


def test_host_pending_upload_preserves_every_compiled_frame_and_acknowledges_progress():
    plan = compile_plan(example_settings())
    device = RecordingT660()
    progress = []
    first = plan.blocks[0]
    result = device.preload_frame_table(list(first.frames), predivider=first.predivider,
        input_frequency_hz=plan.selected_values["probe_rate_hz"]["selected"],
        progress=lambda done, total: progress.append((done, total)))
    assert result["physical_frame_count"] == len(first.frames)
    assert progress[-1] == (len(first.frames), len(first.frames))
    assert len(device.stored) == len(first.frames)
    for frame, stored in zip(first.frames, device.stored):
        assert len(stored) == 20
        for ch, rising in zip("ABCD", (1, 3, 5, 7)):
            assert stored[f"TIME:QUEue{rising}"] == frame["channels"][ch]["delay"]
            assert stored[f"CHANnel:QUEue:MODe{ch}"] == f"{ch}, {'ON' if frame['channels'][ch]['enabled'] else 'OFF'}"
    assert "START" not in device.commands and "TRIG:SOUR EXT" not in device.commands
    assert device.stored[0]["CHANnel:QUEue:MODeA"] == "A, ON"
    assert all(stored["CHANnel:QUEue:MODeA"] == "A, OFF" for stored in device.stored[1:])


def test_plan_mode_schema_and_experiment_mismatches_are_explicit():
    data = compile_plan(example_settings()).to_dict()
    for key, value in (("experiment_id", "other"), ("schema_version", 88), ("instance_id", "single_pump_scan_burst:dual")):
        with pytest.raises(ValueError, match="[Ii]ncompatible|mismatch"):
            Plan.from_dict({**data, key: value})


def test_t660_upload_cancel_retains_acknowledged_frames_with_outputs_inhibited():
    block = compile_plan(example_settings()).blocks[0]
    device = RecordingT660()
    def cancel_check():
        if len(device.stored) == 2:
            raise InterruptedError("operator aborted upload")
    with pytest.raises(InterruptedError, match="aborted"):
        device.preload_frame_table(list(block.frames), predivider=block.predivider,
            input_frequency_hz=1000000, cancel_check=cancel_check)
    assert len(device.stored) == 2
    assert device.values["TRIG:SOUR"] == "OFF"
    assert "START" not in device.commands


@pytest.mark.parametrize("changes", [
    {"probe_reference_delay_s": None}, {"plateau_enabled": True, "plateau_required_bursts": None},
    {"plateau_enabled": True, "plateau_band_windows_cm1": ((1,),)}, {"later_burst_times_s": ("bad",)},
    {"early_scan_count": True}, {"probe_pulse_width_s": 1e-15},
])
def test_invalid_loaded_parameter_values_remain_reviewable_errors(changes):
    plan = compile_plan(replace(example_settings(), **changes))
    assert not plan.valid and plan.errors


def test_information_based_schedule_records_selected_count_without_new_pump():
    plan = compile_plan(replace(example_settings(), schedule_kind="information_based",
                                later_burst_times_s=(1.0, 9.0, 123.0)))
    assert plan.valid
    assert plan.selected_values["later_burst_count"]["requested"] is None
    assert plan.selected_values["later_burst_count"]["selected"] == 3
    assert plan.pump_count == 1


def test_old_evidence_fields_are_optional_and_cannot_select_operating_values():
    source = {"record_id": "PROMOTED-SPB-INSTRUMENT-1", "values": {
        "hardware_evidence": {"operating_configuration": {"configuration_record_id": "OPERATING-1"}},
        "calibration_ids": ["SPECTRAL-1", "TIMING-1"], "controls_record_ids": ["DARK-1"],
        "probe_rate_hz": 123., "scan_interval_s": 1000.,
    }}
    resolved = resolve_settings(Settings(), promoted_values=source)
    assert resolved.hardware_evidence == {} and resolved.calibration_ids == ()
    assert resolved.controls_record_ids == () and compile_plan(resolved).ready
    assert resolved.probe_rate_hz == resolve_settings(Settings()).probe_rate_hz
    assert resolved.scan_interval_s == resolve_settings(Settings()).scan_interval_s


def test_enormous_finite_burst_count_is_budgeted_before_any_schedule_allocation(monkeypatch):
    from control_app.measurement_modules.single_pump_scan_burst import planner
    def must_not_allocate(*args, **kwargs):
        pytest.fail("Schedule allocation ran before checking the finite metadata budget")
    monkeypatch.setattr(planner, "logarithmic_times", must_not_allocate)
    monkeypatch.setattr(planner, "compile_block", must_not_allocate)
    settings = replace(example_settings(), later_burst_count=10**9)
    plan = planner.compile_plan(settings)
    assert not plan.valid and not plan.blocks
    assert any("before schedule allocation" in error for error in plan.errors)
    assert plan.estimates["plan_metadata_bytes"] > settings.max_memory_bytes


def test_declared_storage_also_bounds_plan_metadata_before_schedule_allocation(monkeypatch):
    from control_app.measurement_modules.single_pump_scan_burst import planner
    monkeypatch.setattr(planner, "logarithmic_times", lambda *args: pytest.fail("Allocated an oversized stored schedule"))
    plan = planner.compile_plan(replace(example_settings(), storage_budget_bytes=1000))
    assert not plan.valid
    assert any("storage budget before schedule allocation" in error for error in plan.errors)


def test_peak_memory_and_storage_include_complete_frame_table_metadata():
    plan = compile_plan(example_settings())
    e = plan.estimates
    assert plan.valid, plan.errors
    assert e["plan_frame_count_including_preliminary"] == e["physical_frame_count"] + plan.settings.preliminary_scan_count + 1
    assert e["peak_memory_bytes"] > e["plan_metadata_bytes"] > 0
    assert e["total_storage_bytes"] == e["native_bytes"] + e["plan_metadata_bytes"]
    assert "4096 bytes" in e["plan_metadata_basis"]


def test_explicit_schedule_budgets_selected_count_instead_of_unused_logarithmic_count():
    plan = compile_plan(replace(example_settings(), later_burst_count=10**9, later_burst_times_s=(1., 10.)))
    assert plan.valid, plan.errors
    assert len(plan.blocks) == 4
    assert plan.selected_values["later_burst_count"]["selected"] == 2


def test_automatic_values_recompute_independently_when_coverage_or_speed_changes():
    requested = Settings(sample_rate_hz=10000.0)
    initial = compile_plan(requested)
    changed = compile_plan(replace(requested, scan_speed_cm1_s=1000.0, early_observation_s=2.0))
    assert initial.valid and changed.valid
    assert changed.settings.sample_rate_hz == initial.settings.sample_rate_hz == 10000.0
    assert changed.settings.scan_interval_s > initial.settings.scan_interval_s
    assert changed.settings.early_scan_count != initial.settings.early_scan_count
    assert changed.requested_settings.scan_interval_s is None
    assert changed.selected_values["scan_interval_s"]["requested"] is None


@pytest.mark.parametrize("coverage", [.010001, .012, .1, 1.0, 1.00001])
def test_automatic_early_count_covers_horizon_through_final_observed_scan(coverage):
    plan = compile_plan(Settings(early_observation_s=coverage))
    assert plan.valid, plan.errors
    early = plan.blocks[0]
    assert early.planned_end_s >= coverage
    assert early.scan_count == 1 or early.planned_end_s - early.frame_period_s < coverage
    assert plan.estimates["early_observed_until_s"] == early.planned_end_s


def test_offline_fallback_provenance_does_not_claim_an_installed_readback():
    plan = compile_plan(Settings())
    assert "provisional" in plan.selected_values["qcl"]["source"]
    assert "provisional" in plan.selected_values["hf2_filter_tc_s"]["source"]
    assert "uncalibrated" in plan.selected_values["pump_fire_to_q_s"]["source"]


def test_live_detector_capabilities_and_one_override_leave_other_values_automatic():
    cap = Capabilities(sample_rates_hz=(10000., 20000.), reference_rates_hz=(5000., 40000.),
        timing_rates_hz=(100000.,), hf2_aggregate_rate_max_hz=150000.,
        sample_filter_orders=(1, 2), sample_timeconstants_by_order={1: (.8e-6, 2e-6), 2: (1e-6, 3e-6)},
        reference_filter_orders=(1, 4), reference_timeconstants_by_order={1: (1e-6, 2e-6), 4: (4e-6,)})
    requested = Settings(mode="dual", sample_rate_hz=10000., hf2_filter_order=2)
    plan = compile_plan(requested, cap)
    assert plan.valid, plan.errors
    assert plan.settings.sample_rate_hz == 10000 and plan.settings.reference_rate_hz == 40000
    assert plan.settings.hf2_filter_order == 2 and plan.settings.hf2_filter_tc_s == 1e-6
    assert plan.settings.reference_filter_order == 1 and plan.settings.reference_filter_tc_s == 1e-6
    assert plan.settings.detector_matching_time_tolerance_s == .5 / 10000
    assert plan.settings.wavenumber_matching_tolerance_cm1 == 5000 / 10000
    changed = compile_plan(requested, replace(cap, reference_rates_hz=(5000., 50000.), hf2_aggregate_rate_max_hz=160000.))
    assert changed.settings.sample_rate_hz == 10000 and changed.settings.reference_rate_hz == 50000


def test_automatic_qcl_selection_uses_the_installed_range_and_current():
    cap = Capabilities(qcl_ranges=({"qcl": 1, "minimum_cm1": 1800., "maximum_cm1": 1890.},
                                  {"qcl": 2, "minimum_cm1": 1890., "maximum_cm1": 1980.}),
                       operating_values={"qcl": 2, "probe_current_ma": 783.0, "probe_rate_hz": 1000000.,
                                         "probe_pulse_width_s": 100e-9})
    plan = compile_plan(Settings(), cap)
    assert plan.valid and plan.settings.qcl == 2 and plan.settings.probe_current_ma == 783.
    assert plan.settings.probe_rate_hz == 1000000.
    rejected = compile_plan(Settings(qcl=1), cap)
    assert not rejected.valid and any("cover both" in error for error in rejected.errors)


def test_cached_qcl_readbacks_follow_changed_range_and_preserve_independent_override():
    cap = Capabilities(qcl_ranges=({"qcl": 1, "minimum_cm1": 1800., "maximum_cm1": 1890.},
                                  {"qcl": 2, "minimum_cm1": 1890., "maximum_cm1": 1980.}),
        operating_values={"qcl": 1, "probe_current_ma": 900., "probe_rate_hz": 2000000., "probe_pulse_width_s": 150e-9,
            "qcl_parameters": [{"qcl": 1, "current_ma": 900., "pulse_rate_hz": 2000000., "pulse_width_ns": 150.},
                               {"qcl": 2, "current_ma": 456., "pulse_rate_hz": 1000000., "pulse_width_ns": 100.}]})
    request = Settings(probe_pulse_width_s=80e-9)
    second = compile_plan(request, cap)
    first = compile_plan(replace(request, scan_start_cm1=1820., scan_stop_cm1=1870.), cap)
    assert second.valid and first.valid
    assert (second.settings.qcl, second.settings.probe_current_ma, second.settings.probe_rate_hz) == (2, 456., 1000000.)
    assert (first.settings.qcl, first.settings.probe_current_ma, first.settings.probe_rate_hz) == (1, 900., 2000000.)
    assert second.settings.probe_pulse_width_s == first.settings.probe_pulse_width_s == 80e-9
    assert second.requested_settings.probe_current_ma is None


def test_missing_other_qcl_cache_does_not_borrow_previous_qcl_current():
    cap = Capabilities(qcl_ranges=({"qcl": 2, "minimum_cm1": 1890., "maximum_cm1": 1980.},),
                       operating_values={"qcl": 1, "probe_current_ma": 999., "probe_rate_hz": 1230000.})
    selected = resolve_settings(Settings(), capabilities=cap)
    assert selected.qcl == 2 and selected.probe_current_ma is None
    assert selected.probe_rate_hz != 1230000.


def test_live_resolution_accepts_connected_payload_without_approval_records():
    request = Settings(probe_rate_hz=500000.)
    resolved = resolve_live_settings(request, {"capabilities": Capabilities().to_dict(),
        "values": {"probe_current_ma": 456., "probe_rate_hz": 1000000., "probe_pulse_width_s": 80e-9}})
    assert resolved.probe_current_ma == 456. and resolved.probe_rate_hz == 500000.
    assert resolved.probe_pulse_width_s == 80e-9
    assert resolved.early_scan_count > 0 and resolved.later_burst_count > 0


def test_plan_roundtrip_preserves_each_automatic_override_flag():
    requested = Settings(early_scan_count=7, sample_rate_hz=10000.)
    plan = Plan.from_dict(json.loads(json.dumps(compile_plan(requested).to_dict())))
    assert plan.requested_settings == requested
    assert plan.requested_settings.early_scan_count == 7
    assert plan.requested_settings.later_burst_count is None
    assert plan.requested_settings.scan_interval_s is None
    assert plan.settings.early_scan_count == 7


def test_optional_old_temperature_material_and_evidence_values_cannot_gate_or_change_frames():
    ordinary = compile_plan(Settings())
    metadata = compile_plan(replace(Settings(), condition_id="arbitrary-old-label", measured_temperature_k=-400.,
        min_temperature_k=1000., max_temperature_k=-1., temperature_uncertainty_k=10000.,
        sample_id="previously-used", accepted_state_id="", matrix_id="old", example_only=True,
        calibration_ids=(), promoted_bundle_ids=(), controls_record_ids=(),
        hardware_evidence={"operating_configuration": {"probe_rate_hz": 123, "accepted": False}}))
    assert metadata.valid and metadata.ready and not metadata.readiness
    assert metadata.blocks == ordinary.blocks
    assert metadata.probe_clock_recipe == ordinary.probe_clock_recipe
    assert metadata.estimates == ordinary.estimates
