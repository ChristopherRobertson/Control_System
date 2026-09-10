"""Offline scientific-plan and installed frame protocol verification."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from control_app.devices.t660_service import T660Service
from control_app.measurement_modules.single_pump_scan_burst.settings import (
    Capabilities, Settings, example_settings, resolve_settings,
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


def test_missing_operating_settings_remain_unconfigured_and_hardware_free():
    settings = Settings()
    plan = compile_plan(settings)
    assert settings.scan_speed_cm1_s is None and settings.probe_rate_hz is None
    assert not plan.valid and not plan.ready and not plan.blocks
    assert any("probe_rate_hz" in error for error in plan.errors)


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_deterministic_finite_schedule_contains_exactly_one_pump_and_final_state(mode):
    settings = example_settings(mode)
    plan = compile_plan(settings)
    assert plan.valid, plan.errors
    assert not plan.ready
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


def test_complete_sequential_blank_and_preliminary_never_pump():
    plan = compile_plan(example_settings())
    blank = compile_blank_blocks(plan)
    assert sum(b.scan_count for b in blank) == plan.total_scans
    assert [b.planned_elapsed_s for b in blank] == [b.planned_elapsed_s for b in plan.blocks]
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
    ({"temperature_uncertainty_k": 10}, "uncertainty envelope"),
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


def test_longest_observation_full_blank_and_chunk_memory_are_budgeted():
    plan = compile_plan(replace(example_settings(), observation_limit_s=86400))
    loaded = compile_plan(replace(plan.settings, blank_source="loaded"))
    dual = compile_plan(replace(plan.settings, mode="dual"))
    assert plan.valid
    assert plan.estimates["blank_observation_s"] == 86400
    assert loaded.estimates["blank_observation_s"] == dual.estimates["blank_observation_s"] == 0
    assert plan.estimates["native_bytes"] > loaded.estimates["native_bytes"]
    assert plan.estimates["wall_time_min_s"] >= 172800
    assert plan.estimates["peak_memory_bytes"] < plan.settings.max_memory_bytes
    assert plan.blocks[-1].planned_end_s == pytest.approx(86400)


def test_each_condition_requires_its_own_identity_and_only_explicit_sources_fill_operating_values():
    hrp = Settings()
    mb = replace(hrp, condition_id="77K-Mb-G-S")
    assert hrp.architecture_id == "ARC-77-HRP-SPB" and mb.architecture_id == "ARC-77-MB-SPB"
    resolved = resolve_settings(hrp, promoted_values={"record_id": "promoted-test-record", "values": {"probe_rate_hz": 123456}})
    assert resolved.probe_rate_hz == 123456
    assert resolved.settings_sources["probe_rate_hz"] == "promoted-test-record"
    assert hrp.probe_rate_hz is None
    assert resolve_settings(resolved, installed_readbacks={"record_id": "readback", "values": {"probe_rate_hz": 42}}).probe_rate_hz == 123456
    with pytest.raises(ValueError, match="record_id"):
        resolve_settings(hrp, promoted_values={"values": {"probe_rate_hz": 123}})


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
    {"plateau_band_windows_cm1": ((1,),)}, {"later_burst_times_s": ("bad",)},
    {"early_scan_count": True}, {"probe_pulse_width_s": 1e-15},
])
def test_invalid_loaded_parameter_values_remain_reviewable_errors(changes):
    plan = compile_plan(replace(example_settings(), **changes))
    assert not plan.valid and plan.errors


def test_information_based_schedule_records_selected_count_without_new_pump():
    plan = compile_plan(replace(example_settings(), schedule_kind="information_based",
                                later_burst_times_s=(1.0, 9.0, 123.0)))
    assert plan.valid
    assert plan.selected_values["later_burst_count"]["requested"] == 8
    assert plan.selected_values["later_burst_count"]["selected"] == 3
    assert plan.pump_count == 1


def test_promoted_empty_evidence_fields_are_resolved_with_detached_provenance():
    source = {"record_id": "PROMOTED-SPB-INSTRUMENT-1", "values": {
        "hardware_evidence": {"operating_configuration": {"configuration_record_id": "OPERATING-1"}},
        "calibration_ids": ["SPECTRAL-1", "TIMING-1"], "controls_record_ids": ["DARK-1"],
    }}
    resolved = resolve_settings(Settings(), promoted_values=source)
    assert resolved.hardware_evidence["operating_configuration"]["configuration_record_id"] == "OPERATING-1"
    assert resolved.calibration_ids == ("SPECTRAL-1", "TIMING-1")
    assert resolved.controls_record_ids == ("DARK-1",)
    assert resolved.settings_sources["hardware_evidence"] == source["record_id"]
    assert resolved.settings_sources["hardware_evidence:source_kind"] == "promoted"
    source["values"]["hardware_evidence"]["operating_configuration"]["configuration_record_id"] = "CHANGED"
    assert resolved.hardware_evidence["operating_configuration"]["configuration_record_id"] == "OPERATING-1"
    assert resolve_settings(resolved, promoted_values=source).hardware_evidence == resolved.hardware_evidence


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
