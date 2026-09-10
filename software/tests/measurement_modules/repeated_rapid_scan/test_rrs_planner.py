"""Scientific schedule and finite resource guarantees, without hardware imports."""
from dataclasses import asdict, replace
import json

import pytest

from control_app.measurement_modules.repeated_rapid_scan.settings import RepeatedRapidScanSettings, example_settings
from control_app.measurement_modules.repeated_rapid_scan.timing import compile_movie
from control_app.measurement_modules.repeated_rapid_scan.planner import (
    build_plan, HardwareCapabilities, CalibrationEvidence, load_plan, save_plan,
    resolve_calibration_from_bundle,
)


def compact(mode="single", **kwargs):
    return replace(example_settings(mode), phase_offsets_s=(0.0, 0.025), post_scans=8,
                   directions=("forward", "reverse"), **kwargs)


def test_rrs_many_scans_exactly_one_pump_and_crossing_retained():
    compiled = compile_movie(compact(), 0)
    assert compiled.expected_scan_count == 14
    assert sum(frame["channels"]["A"]["enabled"] for frame in compiled.frames) == 1
    assert sum(frame["channels"]["B"]["enabled"] for frame in compiled.frames) == 1
    assert all(frame["channels"]["C"]["enabled"] for frame in compiled.frames[:-1])
    assert not any(frame["channels"]["D"]["enabled"] for frame in compiled.frames)
    assert compiled.frames[5]["role"] == "pump_crossing"
    assert compiled.frames[4]["channels"]["A"]["enabled"]
    assert compiled.frames[5]["channels"]["B"]["enabled"]
    assert compiled.physical_frame_count == len(compiled.frames) == 15
    assert compiled.frames[-1]["scan_index"] is None
    assert compiled.frames[-1]["role"] == "terminal_inhibit"
    assert not any(values["enabled"] for values in compiled.frames[-1]["channels"].values())
    assert compiled.duration_s == 1.5


def test_rrs_compilation_is_deterministic_and_native_epoch_not_fabricated():
    one = compile_movie(compact(), 0.025)
    two = compile_movie(compact(), 0.025)
    assert one.to_dict() == two.to_dict()
    assert one.requested_phase_s == 0.025
    assert one.frames[6]["programmed_scan_start_s"] != one.requested_phase_s
    assert "observed" in one.timing_basis


def test_rrs_no_automatic_movie_split_for_frame_capacity():
    settings = replace(compact(), post_scans=8192)
    with pytest.raises(ValueError, match="no splitting"):
        build_plan(settings)


def test_rrs_memory_is_whole_movie_and_no_circular_reuse():
    with pytest.raises(ValueError, match="full uninterrupted movie exceeds memory"):
        build_plan(compact(memory_limit_bytes=100))


def test_rrs_dual_duration_is_not_doubled_but_throughput_is():
    single = build_plan(compact())
    dual = build_plan(compact("dual"))
    assert single.movies[0].duration_s == dual.movies[0].duration_s
    assert dual.estimates["aggregate_rate_hz"] == 2 * single.estimates["aggregate_rate_hz"]
    assert dual.estimates["movie_native_bytes"] == 2 * single.estimates["movie_native_bytes"]
    assert dual.estimates["preliminary_s"] == single.estimates["preliminary_s"]
    assert dual.estimates["blank_s"] == 0 < single.estimates["blank_s"]


def test_rrs_timing_stream_counts_towards_aggregate_limit():
    caps = HardwareCapabilities(max_aggregate_rate_hz=4300, acquisition_timing_rate_hz=500)
    with pytest.raises(ValueError, match="aggregate rate exceeds"):
        build_plan(compact("dual"), caps)


def test_rrs_invalid_period_never_silently_slows_scan():
    settings = replace(compact(), measured_scan_period_s=0.1000004)
    with pytest.raises(ValueError, match="integer number of carrier"):
        compile_movie(settings)
    accepted = compile_movie(replace(settings, allow_period_quantization=True))
    assert accepted.requested_scan_period_s == 0.1000004
    assert accepted.scan_period_s == 0.1


def test_rrs_phase_quantization_is_explicit_and_reports_both_values():
    with pytest.raises(ValueError, match="phase is not on"):
        compile_movie(compact(), 0.025000000004)
    result = compile_movie(compact(allow_phase_quantization=True), 0.025000000004)
    assert result.requested_phase_s == 0.025000000004
    assert result.selected_phase_s == 0.025


def test_rrs_long_process_pulse_does_not_trigger_scan_timing_rewrite():
    with pytest.raises(ValueError, match="does not finish"):
        compile_movie(compact(process_pulse_width_s=.1))


def test_rrs_control_events_are_explicit_and_phase_matched():
    plan = build_plan(compact())
    assert {movie.control for movie in plan.movies} == {"sample", "probe_only", "pump_blocked"}
    for movie in plan.movies:
        assert movie.pump_count == (0 if movie.control == "probe_only" else 1)
        assert movie.compiled.electrical_pump_count == movie.pump_count
        if movie.control == "pump_blocked":
            assert "Manually block" in movie.required_action


def test_rrs_default_examples_never_claim_commissioning_or_optical_zero():
    plan = build_plan(compact())
    assert not plan.ready_for_hardware
    assert any(item.code == "optical_time_zero" and not item.blocks_hardware for item in plan.readiness_items)
    assert "EXAMPLE ONLY" in plan.settings.value_source
    assert plan.actual["sample_rate_hz"] is None


def test_rrs_plan_roundtrip_rejects_wrong_mode_and_foreign_schema(tmp_path):
    plan = build_plan(compact())
    path = save_plan(plan, tmp_path / "plan.json")
    restored = load_plan(path, mode="single")
    assert restored.settings == plan.settings
    assert restored.movies[0].compiled.to_dict() == plan.movies[0].compiled.to_dict()
    with pytest.raises(ValueError, match="detector mode"):
        load_plan(path, mode="dual")
    data = json.loads(path.read_text())
    data["experiment_id"] = "another_experiment"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="identity/schema"):
        load_plan(path)


def test_rrs_settings_roundtrip_keeps_condition_and_units():
    settings = compact("dual")
    assert RepeatedRapidScanSettings.from_dict(json.loads(json.dumps(asdict(settings)))) == settings
    with pytest.raises(ValueError, match="Unsupported settings"):
        RepeatedRapidScanSettings.from_dict({"wrong_method_flag": True})


def test_rrs_promoted_manifest_requires_status_and_method_specific_evidence():
    with pytest.raises(ValueError, match="PROMOTED"):
        resolve_calibration_from_bundle({"bundle_id": "example", "status": "PREVIEW"})
    with pytest.raises(ValueError, match="applicability data"):
        resolve_calibration_from_bundle({"bundle_id": "example", "status": "PROMOTED"})
    calibration = resolve_calibration_from_bundle({"bundle_id": "test", "status": "PROMOTED",
                                                   "repeated_rapid_scan": {"calibration": {"trajectory_id": "trajectory-1"}}})
    assert calibration.source == "instrument/promoted_bundles/test"
    assert calibration.promoted
    assert not build_plan(compact(), calibration=calibration).ready_for_hardware


def test_rrs_no_reference_demod_reuse_and_band_support_must_be_complete():
    with pytest.raises(ValueError, match="independently configured"):
        build_plan(compact("dual", reference_demodulator=0))
    with pytest.raises(ValueError, match="contained within"):
        build_plan(compact(scan_start_cm1=1920.0))


def test_rrs_upload_estimate_uses_pending_deltas_and_includes_full_workflow():
    plan = build_plan(compact())
    table = plan.movies[0].compiled
    assert table.command_count < len(table.frames) * 21
    assert plan.estimates["wall_time_s"] > plan.estimates["acquisition_s"] + plan.estimates["upload_s"]
    assert plan.estimates["qualification_s"] > 0


def test_rrs_complete_run_retention_memory_is_budgeted_not_only_one_movie():
    unrestricted = build_plan(compact())
    movie_memory = unrestricted.estimates["movie_memory_bytes"]
    assert unrestricted.estimates["retained_run_memory_bytes"] > movie_memory * 2
    with pytest.raises(ValueError, match="complete retained run exceeds memory"):
        build_plan(compact(memory_limit_bytes=movie_memory * 2))


def test_rrs_tiny_but_real_period_quantization_requires_permission():
    with pytest.raises(ValueError, match="integer number of carrier"):
        compile_movie(compact(measured_scan_period_s=.10000000004))


def test_rrs_documented_t660_edge_range_is_validated_before_any_upload():
    settings = compact(probe_frequency_hz=1.0, measured_scan_period_s=5000.,
                       process_delay_s=4000.)
    with pytest.raises(ValueError, match="3600 s edge range"):
        compile_movie(settings)


def test_rrs_terminal_inhibit_frame_counts_against_connected_and_total_capacity():
    settings = compact()
    with pytest.raises(ValueError, match="connected frame capacity"):
        build_plan(settings, HardwareCapabilities(frame_capacity=14))
    with pytest.raises(ValueError, match="plus one terminal frame"):
        compile_movie(replace(settings, post_scans=8186))


def test_rrs_qualification_and_memory_estimates_include_terminal_period():
    plan = build_plan(compact())
    assert plan.estimates["physical_frames_per_movie"] == plan.estimates["scans_per_movie"] + 1
    samples = sum(movie.control == "sample" for movie in plan.movies)
    assert plan.estimates["qualification_s"] == samples * (plan.settings.pre_scans + 1) * plan.selected["scan_period_s"]
    assert plan.estimates["movie_duration_s"] == plan.estimates["spectral_record_duration_s"] + plan.estimates["terminal_inhibit_duration_s"]
