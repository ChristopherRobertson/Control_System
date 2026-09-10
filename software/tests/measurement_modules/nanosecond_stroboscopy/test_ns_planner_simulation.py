"""Hardware-free scientific/timing regression tests with synthetic truths."""
from dataclasses import replace
import json

import numpy as np
import pytest

from control_app.measurement_modules.nanosecond_stroboscopy.settings import ADVANCED_FIELDS, Settings, PROFILES, optical_pulse_errors, resolve_settings
from control_app.measurement_modules.nanosecond_stroboscopy.planner import build_plan
from control_app.measurement_modules.nanosecond_stroboscopy.timing import compile_timing, quantize_ns
from control_app.measurement_modules.nanosecond_stroboscopy.simulation import (
    convolved_response, evaluate_schedule, fit_shared_lifetimes, identify_lifetime, simulate_trace,
)


CAPS = {"fire_to_q_ns": 200000.0, "pump_command_width_ns": 1000.0,
        "probe_command_width_ns": 100.0, "filter_time_constant_s": .05,
        "filter_order": 1, "hf2li_rate_hz": 200.0}


def sim(**values):
    return resolve_settings(replace(Settings(execution_mode="simulation"), **values)).settings


def test_ns_settings_roundtrip_and_four_traceable_profiles():
    s = Settings(mode="dual")
    assert Settings.from_dict(json.loads(json.dumps(s.to_dict()))) == s
    assert s.instance_id == "nanosecond_stroboscopy:dual"
    assert len(PROFILES) == 4
    assert s.execution_mode == "connected" and not s.illustrative_only
    assert s.demodulator_reference == 3
    assert Settings().qualification is not Settings().qualification


def test_ns_delay_compilation_is_deterministic_signed_and_all_channels_explicit():
    s = sim(delays_ns=(-100.005, 0.004, 200.003), optical_delay_offset_ns=11.0)
    compiled = compile_timing(s)
    assert compiled == compile_timing(s)
    assert quantize_ns(-0.005) == -0.01
    assert compiled.quantized_delays_ns == pytest.approx((-100.01, 0, 200))
    assert compiled.electrical_delays_ns == pytest.approx((-100.01, 0, 200))
    for frame in compiled.frames:
        assert set(frame["channels"]) == set("ABCD")
        assert not frame["channels"]["C"]["enabled"]
        assert not frame["channels"]["D"]["enabled"]
        assert frame["train_count"] == 0
    assert not compiled.t660_1_recipe["channels"]["A"]["enabled"]
    assert not compiled.t660_1_recipe["channels"]["D"]["enabled"]


def test_ns_dds_quantization_and_invalid_electrical_settings():
    comp = compile_timing(sim(cycle_interval_s=3))
    assert comp.input_frequency_hz == .32
    assert comp.frame_period_s == pytest.approx(1 / .32)
    with pytest.raises(ValueError, match="0.01 ns"):
        quantize_ns(5, .001)
    with pytest.raises(ValueError, match="anchor"):
        compile_timing(replace(sim(), probe_anchor_ns=100))
    assert build_plan(Settings(delays_ns=(0, .001)), CAPS).errors


def test_ns_wavelength_major_counterbalance_budget_and_independent_records():
    s = Settings(execution_mode="simulation", repetitions=2)
    p = build_plan(s)
    assert not p.errors
    assert len(p.events) == len(s.wavenumbers_cm1) * len(s.delays_ns) * 2 * 2
    nus = [e.wavenumber_cm1 for e in p.events]
    assert nus == sorted(nus)
    assert p.budget["physical_frame_count"] == len(p.events) * 4
    assert p.budget["reset_count"] == len(p.events) // 2
    assert p.budget["control_event_count"] == len(p.events) // 2
    assert p.budget["total_s"] > p.budget["acquisition_s"]
    for e in p.events:
        assert e.observed_electrical_delay_ns is None
        assert e.calibrated_optical_delay_ns is None
        assert e.frames[e.frame_index]["channels"]["A"]["enabled"] == (e.condition == "pump_on")
        assert all(not c["enabled"] for c in e.frames[-1]["channels"].values())
    assert not build_plan(replace(s, mode="dual")).budget["blank_event_count"]


def test_ns_default_connected_plan_defers_live_reads_without_procedural_gates():
    p = build_plan(Settings())
    assert p.connected_ready and not p.errors
    assert p.unresolved and p.events and not p.events[0].frames
    assert p.budget["storage_bytes"] is None
    for profile in ("", *PROFILES, "unlisted material"):
        requested = Settings(profile_id=profile, temperature_k=None, matrix_id="", reset_equivalent=False,
                             reset_method="fresh_position", confirmatory=True, calibration_ids=())
        connected = build_plan(requested, CAPS)
        assert connected.connected_ready and not connected.errors and not connected.unresolved
        assert not connected.readiness
        assert connected.events[0].frames == build_plan(Settings(), CAPS).events[0].frames


def test_ns_auto_resolution_changes_only_explicit_override():
    requested = Settings(cycle_interval_s=.2, overrides={"filter_time_constant_s": .1}, fire_to_q_ns=999)
    first = build_plan(requested, CAPS)
    assert first.resolved_settings.filter_time_constant_s == .1
    assert first.resolved_settings.probe_period_s == pytest.approx(1.6)
    second = build_plan(replace(requested, cycle_interval_s=3), {**CAPS, "fire_to_q_ns": 250000.0})
    assert second.resolved_settings.probe_period_s == 3
    assert second.resolved_settings.fire_to_q_ns == 250000
    assert second.resolved_settings.probe_anchor_ns > first.resolved_settings.probe_anchor_ns
    assert requested.overrides == {"filter_time_constant_s": .1}
    assert second.settings == replace(requested, cycle_interval_s=3)
    reset = build_plan(replace(requested, overrides={"filter_time_constant_s": None}), CAPS)
    assert reset.resolved_settings.filter_time_constant_s == CAPS["filter_time_constant_s"]
    assert reset.resolved_settings.probe_period_s == pytest.approx(.8)


def test_ns_legacy_engineering_overrides_and_qcl_selection_become_metadata():
    obsolete = {"probe_period_s": 40, "fire_to_q_ns": "bad", "warmup_frames": 1000000,
                "probe_command_width_ns": -9, "demodulator_sample": 5}
    requested = Settings(qcl=2, overrides={**obsolete, "filter_order": 2}, metadata={"sample": "buffer"})
    normalized = Settings.from_dict(requested)
    assert normalized.qcl == 1
    assert normalized.overrides == {"filter_order": 2}
    assert normalized.metadata == {"sample": "buffer", "legacy_qcl_selection": 2, "legacy_timing_overrides": obsolete}
    assert Settings.from_dict(normalized) == normalized
    assert Settings.from_dict(requested.to_dict()) == normalized
    assert requested.qcl == 2 and requested.overrides["fire_to_q_ns"] == "bad"  # Caller is unchanged.
    p = build_plan(requested, {**CAPS, "qcl": 7})
    assert not p.errors and p.settings == normalized
    assert p.resolved_settings.qcl == 1
    assert p.resolved_settings.probe_period_s == pytest.approx(1.6)
    assert p.resolved_settings.fire_to_q_ns == CAPS["fire_to_q_ns"]
    assert p.resolved_settings.warmup_frames == 1
    assert set(ADVANCED_FIELDS) == {"filter_order", "filter_time_constant_s", "hf2li_rate_hz",
                                   "reference_filter_order", "reference_filter_time_constant_s", "reference_hf2li_rate_hz"}


@pytest.mark.parametrize("rate,width,accepted", [
    (600000, 500, True), (600000.01, 500, False), (599999.99, 500, True),
    (3000000, 100, True), (3000000.000001, 100, False),
])
def test_ns_optical_duty_boundary_is_inclusive_without_above_limit_tolerance(rate, width, accepted):
    errors = optical_pulse_errors(rate, width)
    assert not errors if accepted else any("30%" in e for e in errors)


def test_ns_optical_live_values_preserve_vendor_limits_and_distinguish_external_cadence():
    optical = {"mircat_pulse_rate_hz": 600000., "mircat_pulse_width_ns": 500.,
               "mircat_max_pulse_rate_hz": 1000000., "mircat_max_pulse_width_ns": 2000.,
               "mircat_max_duty_fraction": .5}
    s = Settings(mircat_pulse_rate_hz=123, mircat_pulse_width_ns=999)
    p = build_plan(s, {**CAPS, **optical})
    assert not p.errors
    assert p.resolved_settings.mircat_pulse_rate_hz == 600000
    assert p.resolved_settings.mircat_pulse_width_ns == 500
    assert p.resolved_settings.probe_command_width_ns == 100  # Independent electrical TTL width.
    assert p.timing["input_frequency_hz"] == 1
    changed = build_plan(s, {**CAPS, **optical, "mircat_pulse_rate_hz": 600001})
    assert not changed.events and any("configured optical pulse rate" in e for e in changed.errors)
    lower_vendor = build_plan(s, {**CAPS, **optical, "mircat_max_duty_fraction": .25})
    assert any("vendor duty" in e for e in lower_vendor.errors)
    assert not optical_pulse_errors(500000, 500, max_duty_fraction=.25)
    assert any("vendor duty" in e for e in optical_pulse_errors(500000.001, 500, max_duty_fraction=.25))
    assert any("vendor pulse-rate" in e for e in optical_pulse_errors(600000, 500, max_rate_hz=500000))
    assert any("vendor limit" in e for e in optical_pulse_errors(600000, 500, max_width_ns=400))
    external = optical_pulse_errors(1, 500, external_probe_rate_hz=600000.01)
    assert any("External probe cadence" in e for e in external)
    assert not optical_pulse_errors(None, None)
    pending = build_plan(s)
    assert not pending.errors
    assert pending.resolved_settings.mircat_pulse_rate_hz is None
    assert pending.resolved_settings.mircat_pulse_width_ns is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 0, True, "500"])
def test_ns_invalid_live_optical_values_are_rejected(value):
    assert build_plan(Settings(), {**CAPS, "mircat_pulse_width_ns": value}).errors


def test_ns_independent_reference_readbacks_drive_dual_cycle_and_aggregate_rate():
    caps = {**CAPS, "reference_filter_time_constant_s": .2, "reference_filter_order": 2,
            "reference_hf2li_rate_hz": 500.0}
    requested = Settings(mode="dual", cycle_interval_s=.1, max_storage_bytes=2000000000)
    p = build_plan(requested, caps)
    assert not p.errors and not p.unresolved
    assert p.resolved_settings.probe_period_s == pytest.approx(6.4)
    assert p.resolved_settings.reference_filter_time_constant_s == .2
    assert p.budget["aggregate_rate_hz"] == 700
    override = build_plan(replace(requested, overrides={"reference_filter_time_constant_s": .01}), caps)
    assert override.resolved_settings.filter_time_constant_s == .05
    assert override.resolved_settings.probe_period_s == pytest.approx(.8)
    assert override.settings.overrides == {"reference_filter_time_constant_s": .01}


def test_ns_optional_optical_metadata_does_not_silently_retime_commands():
    first = build_plan(Settings(), CAPS)
    second = build_plan(Settings(optical_delay_offset_ns=1200, temperature_k=77,
                                 sample_id="buffer", profile_id="any matrix", reset_equivalent=True), CAPS)
    assert first.timing == second.timing
    assert all(a.frames == b.frames for a, b in zip(first.events, second.events))
    assert first.resolved_settings.kernel()["irf_qualified"] is False
    legacy = build_plan(Settings(reset_interval_s=600, reset_method="thermal"), CAPS)
    assert legacy.settings.reset_interval_s == 600
    assert legacy.resolved_settings.reset_interval_s == 0
    assert legacy.budget["reset_s"] == 0
    assert first.timing == legacy.timing


def test_ns_auto_filter_adapts_to_export_sampling_without_overriding_user_choice():
    caps = {**CAPS, "filter_time_constant_s": .00001, "hf2li_rate_hz": 1000.0}
    requested = Settings(cycle_interval_s=.2)
    auto = build_plan(requested, caps)
    assert not auto.errors
    assert auto.resolved_settings.filter_time_constant_s == .004
    assert "4 / selected export rate" in auto.resolution_sources["filter_time_constant_s"]
    rate = build_plan(replace(requested, overrides={"hf2li_rate_hz": 2000}), caps)
    assert rate.resolved_settings.filter_time_constant_s == .002
    invalid = build_plan(replace(requested, overrides={"filter_time_constant_s": .00001}), caps)
    assert invalid.resolved_settings.filter_time_constant_s == .00001
    assert any("undersamples" in error for error in invalid.errors)


def test_ns_recovery_is_unbiased_with_resolvable_truth():
    s = sim()
    result = evaluate_schedule(s.delays_ns, 250, -.01, s.kernel(), noise_sd=.00006, repetitions=3, trials=12, seed=8)
    assert result["resolved_fraction"] == 1
    assert abs(result["relative_bias"]) < .025
    assert result["interval_coverage"] >= .75


@pytest.mark.parametrize("change", [
    {"irf_sigma_ns": 5000}, {"timing_jitter_ns": 5000},
    {"integration_aperture_ns": 20000}, {"filter_blur_ns": 10000},
])
def test_ns_broad_kernels_do_not_claim_fast_lifetime(change):
    s = sim()
    k = {**s.kernel(), **change}
    trace = simulate_trace(s.delays_ns, 15, -.003, k, noise_sd=.0001, seed=42)
    fit = identify_lifetime(trace["delay_ns"], trace["delta_a"], trace["uncertainty"], k)
    assert fit["outcome"] == "prompt_unresolved_bound"
    assert fit["lifetime_ns"] is None


def test_ns_noise_reset_failure_missing_history_and_missing_time_zero_are_honest():
    s = sim()
    for k, noise, reset in [(s.kernel(), .1, 0), (s.kernel(), .00001, .02), ({**s.kernel(), "irf_qualified": False}, .00001, 0)]:
        trace = simulate_trace(s.delays_ns, 250, -.01, k, noise_sd=noise, reset_residual_fraction=reset, seed=7)
        fit = identify_lifetime(trace["delay_ns"], trace["delta_a"], trace["uncertainty"], trace["kernel"])
        assert fit["lifetime_ns"] is None
        assert fit["reasons"]
    k = {**s.kernel(), "filter_memory_fraction": .5}
    trace = simulate_trace(s.delays_ns, 250, -.01, k, noise_sd=.00001)
    trace["delta_a"][4] = float("nan")
    fit = identify_lifetime(trace["delay_ns"], trace["delta_a"], trace["uncertainty"], k)
    assert fit["lifetime_ns"] is None
    assert fit["excluded_indices"] == [4]
    assert any("Missing event history" in r for r in fit["reasons"])


def test_ns_convolution_has_causal_irf_support_and_free_shared_vs_distinct_states():
    s = sim()
    k = s.kernel()
    sharp = {**k, "irf_sigma_ns": 0, "timing_jitter_ns": 0, "integration_aperture_ns": 0}
    assert convolved_response([-1, 0, 100], 100, sharp) == pytest.approx([0, 1, np.exp(-1)])
    traces = [simulate_trace(s.delays_ns, tau, -.01, k, noise_sd=.00003, seed=i) for i, tau in enumerate((200, 650))]
    distinct = fit_shared_lifetimes(traces, k)
    assert distinct["outcome"] == "distinct_supported"
    shared = fit_shared_lifetimes([simulate_trace(s.delays_ns, 250, a, k, noise_sd=.00003, seed=i) for i, a in enumerate((-.01, -.008))], k)
    assert shared["outcome"] == "shared_compatible"


def test_ns_filter_order_tail_and_event_storage_limits():
    assert replace(sim(), filter_order=4).kernel()["filter_memory_fraction"] > sim().kernel()["filter_memory_fraction"]
    assert any("storage" in e for e in build_plan(Settings(max_storage_bytes=1), CAPS).errors)
    assert any("event budget" in e for e in build_plan(Settings(max_pump_events=1), CAPS).errors)


@pytest.mark.parametrize("values", [{"cycle_interval_s": float("nan")}, {"cycle_interval_s": "1"},
                                   {"repetitions": True}, {"delays_ns": ("zero",)},
                                   {"max_frame_capacity": "bad"}, {"delays_ns": None}, {"overrides": None},
                                   {"overrides": {"filter_order": 0}}, {"overrides": {"filter_order": 1.5}},
                                   {"overrides": {"hf2li_rate_hz": "bad"}}, {"overrides": {"not_supported": 1}}])
def test_ns_malformed_operating_inputs_are_reviewable_errors(values):
    assert build_plan(Settings(**values), CAPS).errors


def test_ns_offband_and_all_preparation_stream_budgets():
    s = Settings(execution_mode="simulation", repetitions=1, delays_ns=(-100, 0, 100), off_band_wavenumbers_cm1=(1930.0,))
    p = build_plan(s)
    assert not p.errors
    assert 1930.0 in [e.wavenumber_cm1 for e in p.events]
    assert p.budget["blank_event_count"] == len(p.events)
    assert p.budget["preliminary_event_count"] == 4
    assert p.budget["preparation_frame_count"] == (len(p.events) + 4) * 4
    assert p.budget["detector_count"] == 1 and p.budget["stream_count"] == 1
    assert p.budget["aggregate_rate_hz"] == p.resolved_settings.hf2li_rate_hz
    assert p.budget["restoration_s"] == 3 * s.restoration_estimate_s
    dual = build_plan(replace(s, mode="dual"))
    assert dual.budget["stream_count"] == 2
    assert dual.budget["restoration_s"] == 2 * s.restoration_estimate_s


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_ns_native_budget_includes_pre_capture_and_finite_burst_retrieval_tail(mode):
    requested = Settings(mode=mode, wavenumbers_cm1=(1942.0,), delays_ns=(-100.0, 100.0), repetitions=1)
    caps = {**CAPS, "reference_filter_time_constant_s": .08, "reference_filter_order": 2,
            "reference_hf2li_rate_hz": 500.0}
    p = build_plan(requested, caps)
    assert not p.errors
    b, period = p.budget, p.timing["frame_period_s"]
    tail = 8 * (.08 * 2 if mode == "dual" else .05)
    pre = min(.2, period / 4)
    capture = pre + b["frames_per_event_burst"] * period + period + tail
    total_events = b["event_count"] + b["blank_event_count"] + b["preliminary_event_count"]
    assert b["filter_tail_capture_s"] == pytest.approx(tail)
    assert b["capture_per_event_s"] == pytest.approx(capture)
    assert b["native_capture_s"] == pytest.approx(total_events * capture)
    # Equivalent floating-point associations can move ceil by one sample at an
    # exactly integral boundary; this does not change the captured duration.
    assert b["native_sample_count"] == pytest.approx(np.ceil(total_events * capture * b["aggregate_rate_hz"]), abs=1, rel=0)
    assert b["acquisition_s"] == pytest.approx(b["event_count"] * capture)
    operations = 3 if mode == "single" else 2
    assert b["preparation_s"] == pytest.approx(operations * requested.preparation_estimate_s + (total_events - b["event_count"]) * capture)
    assert b["capture_estimate_complete"]
    assert p.timing["finite_probe_burst"]["pulse_count"] == b["frames_per_event_burst"]
    assert p.timing["finite_probe_burst"]["trigger_period_count"] == b["frames_per_event_burst"] + 1
    assert p.timing["t660_1_recipe"]["gate_mode"] == 0  # Remote burst is configured by the owned adapter.


def test_ns_capture_budget_does_not_invent_missing_live_filter_tail():
    p = build_plan(Settings(), {"hf2li_rate_hz": 200.0})
    assert p.connected_ready and p.unresolved
    for field in ("filter_tail_capture_s", "post_capture_per_event_s", "capture_per_event_s", "native_capture_s", "native_sample_count", "storage_bytes"):
        assert p.budget[field] is None
    assert p.budget["capture_estimate_complete"] is False
    assert p.budget["total_s"] > 0


def test_ns_forward_evaluation_cancellation_and_no_approval_gate():
    class Stopped(Exception):
        pass
    def stop():
        raise Stopped()
    with pytest.raises(Stopped):
        evaluate_schedule(sim().delays_ns, 200, -.01, sim().kernel(), noise_sd=.001, cancel_check=stop)
    p = build_plan(Settings(confirmatory=True, noise_sd=.1, qualification={}), CAPS)
    assert p.connected_ready and not p.readiness
    assert p.budget["forward_simulation"] is None


@pytest.mark.parametrize("values,reason", [
    ({"repetitions": 10000, "max_storage_bytes": 1}, "storage"),
    ({"repetitions": 1000, "max_storage_bytes": 10**15, "max_pump_events": 10**9}, "memory"),
    ({"max_storage_bytes": 1}, "storage"), ({"max_pump_events": 1}, "event budget"),
    ({"max_frame_capacity": 3}, "frame capacity"),
])
def test_ns_oversized_plans_fail_before_event_materialization(monkeypatch, values, reason):
    import control_app.measurement_modules.nanosecond_stroboscopy.planner as planner_module
    def allocation_forbidden(*args, **kwargs):
        raise AssertionError("Oversized schedule tried to allocate an Event frame table")
    monkeypatch.setattr(planner_module, "event_frames", allocation_forbidden)
    plan = planner_module.build_plan(Settings(**values), CAPS)
    assert not plan.events
    assert any(reason in error for error in plan.errors)
    assert plan.budget["materialized_event_count"] == 0
    assert plan.budget["event_count"] > 0
    assert plan.budget["memory_bytes"] >= plan.budget["native_bytes"]


def test_ns_t6601_recipe_uses_genuine_service_without_uninstalled_frames_feature():
    from control_app.devices.t660_service import T660Service
    class Transport(T660Service):
        def __init__(self):
            super().__init__("t660_1", {"role": "continuous_probe_reference_and_event_trigger"})
            self.commands = []
        def command(self, command, **kwargs):
            self.commands.append(command)
            return "OK"
    service = Transport()
    recipe = compile_timing(sim()).t660_1_recipe
    service.apply_recipe(recipe)
    assert not any(command.startswith(("TFRame:", "TRAin:")) for command in service.commands)
    assert "CHAN:OFF D" in service.commands
    assert "CHAN:OFF A" in service.commands
    assert "TRIG:SOUR OFF" in service.commands or any("SOUR" in command and "OFF" in command for command in service.commands)
