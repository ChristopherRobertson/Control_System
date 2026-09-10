"""Hardware-free scientific/timing regression tests with synthetic truths."""
from dataclasses import replace
import json

import numpy as np
import pytest

from control_app.measurement_modules.nanosecond_stroboscopy.settings import Settings, PROFILES
from control_app.measurement_modules.nanosecond_stroboscopy.planner import build_plan
from control_app.measurement_modules.nanosecond_stroboscopy.timing import compile_timing, quantize_ns
from control_app.measurement_modules.nanosecond_stroboscopy.simulation import (
    convolved_response, evaluate_schedule, fit_shared_lifetimes, identify_lifetime, simulate_trace,
)


def test_ns_settings_roundtrip_and_four_traceable_profiles():
    s = Settings(mode="dual")
    assert Settings.from_dict(json.loads(json.dumps(s.to_dict()))) == s
    assert s.instance_id == "nanosecond_stroboscopy:dual"
    assert len(PROFILES) == 4
    assert s.illustrative_only and "EXAMPLE ONLY" in s.value_source
    assert s.demodulator_reference == 3
    assert Settings().qualification is not Settings().qualification


def test_ns_delay_compilation_is_deterministic_signed_and_all_channels_explicit():
    s = replace(Settings(), delays_ns=(-100.005, 0.004, 200.003), optical_delay_offset_ns=11.0)
    compiled = compile_timing(s)
    assert compiled == compile_timing(s)
    assert quantize_ns(-0.005) == -0.01
    assert compiled.quantized_delays_ns == pytest.approx((-100.01, 0, 200))
    assert compiled.electrical_delays_ns == pytest.approx((-111.01, -11, 189))
    for frame in compiled.frames:
        assert set(frame["channels"]) == set("ABCD")
        assert not frame["channels"]["C"]["enabled"]
        assert not frame["channels"]["D"]["enabled"]
        assert frame["train_count"] == 0
    assert compiled.t660_1_recipe["channels"]["A"]["enabled"]
    assert not compiled.t660_1_recipe["channels"]["D"]["enabled"]


def test_ns_dds_quantization_and_invalid_electrical_settings():
    comp = compile_timing(replace(Settings(), probe_period_s=3))
    assert comp.input_frequency_hz == .34
    assert comp.frame_period_s == pytest.approx(1 / .34)
    with pytest.raises(ValueError, match="0.01 ns"):
        quantize_ns(5, .001)
    assert build_plan(replace(Settings(), probe_anchor_ns=100)).errors
    assert build_plan(replace(Settings(), delays_ns=(0, .001))).errors


def test_ns_wavelength_major_counterbalance_budget_and_independent_records():
    s = replace(Settings(), repetitions=2)
    p = build_plan(s)
    assert not p.errors
    assert len(p.events) == len(s.wavenumbers_cm1) * len(s.delays_ns) * 2 * 2
    nus = [e.wavenumber_cm1 for e in p.events]
    assert nus == sorted(nus)
    assert p.budget["physical_frame_count"] == len(p.events) * 6
    assert p.budget["reset_count"] == len(p.events) // 2
    assert p.budget["control_event_count"] == len(p.events) // 2
    assert p.budget["total_s"] > p.budget["acquisition_s"]
    for e in p.events:
        assert e.observed_electrical_delay_ns is None
        assert e.calibrated_optical_delay_ns is None
        assert e.frames[e.frame_index]["channels"]["A"]["enabled"] == (e.condition == "pump_on")
        assert all(not c["enabled"] for c in e.frames[-1]["channels"].values())
    assert not build_plan(replace(s, mode="dual")).budget["blank_event_count"]


def test_ns_exact_missing_kernel_and_cryo_reset_readiness():
    p = build_plan(replace(Settings(), execution_mode="connected", profile_id="77K-HRP-G-F", reset_method="fresh_position"))
    assert not p.connected_ready
    assert any("impulse" in r for r in p.readiness)
    assert any("no automatic fresh-position" in r for r in p.readiness)
    assert any("temperature" in r for r in p.readiness)
    assert any("both sample-fitted" in r for r in p.readiness)


def test_ns_recovery_is_unbiased_with_resolvable_truth():
    s = Settings()
    result = evaluate_schedule(s.delays_ns, 250, -.01, s.kernel(), noise_sd=.00006, repetitions=3, trials=12, seed=8)
    assert result["resolved_fraction"] == 1
    assert abs(result["relative_bias"]) < .025
    assert result["interval_coverage"] >= .75


@pytest.mark.parametrize("change", [
    {"irf_sigma_ns": 5000}, {"timing_jitter_ns": 5000},
    {"integration_aperture_ns": 20000}, {"filter_blur_ns": 10000},
])
def test_ns_broad_kernels_do_not_claim_fast_lifetime(change):
    s = Settings()
    k = {**s.kernel(), **change}
    trace = simulate_trace(s.delays_ns, 15, -.003, k, noise_sd=.0001, seed=42)
    fit = identify_lifetime(trace["delay_ns"], trace["delta_a"], trace["uncertainty"], k)
    assert fit["outcome"] == "prompt_unresolved_bound"
    assert fit["lifetime_ns"] is None


def test_ns_noise_reset_failure_missing_history_and_missing_time_zero_are_honest():
    s = Settings()
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
    s = Settings()
    k = s.kernel()
    sharp = {**k, "irf_sigma_ns": 0, "timing_jitter_ns": 0, "integration_aperture_ns": 0}
    assert convolved_response([-1, 0, 100], 100, sharp) == pytest.approx([0, 1, np.exp(-1)])
    traces = [simulate_trace(s.delays_ns, tau, -.01, k, noise_sd=.00003, seed=i) for i, tau in enumerate((200, 650))]
    distinct = fit_shared_lifetimes(traces, k)
    assert distinct["outcome"] == "distinct_supported"
    shared = fit_shared_lifetimes([simulate_trace(s.delays_ns, 250, a, k, noise_sd=.00003, seed=i) for i, a in enumerate((-.01, -.008))], k)
    assert shared["outcome"] == "shared_compatible"


def test_ns_filter_order_tail_and_dose_storage_limits():
    assert replace(Settings(), filter_order=4).kernel()["filter_memory_fraction"] > Settings().kernel()["filter_memory_fraction"]
    assert any("storage" in e for e in build_plan(replace(Settings(), max_storage_bytes=1)).errors)
    assert any("dose" in e for e in build_plan(replace(Settings(), max_pump_events=1)).errors)


@pytest.mark.parametrize("field,value", [("noise_sd", float("nan")), ("probe_period_s", "1"), ("repetitions", True), ("filter_order", 0), ("temperature_k", -1), ("delays_ns", ("zero",))])
def test_ns_malformed_settings_are_reviewable_errors(field, value):
    plan = build_plan(replace(Settings(), **{field: value}))
    assert plan.errors


def test_ns_offband_preparation_budget_and_unique_pump_positions():
    s = replace(Settings(), repetitions=1, delays_ns=(-100, 0, 100), off_band_wavenumbers_cm1=(1930.0,), reset_method="fresh_position", position_ids=tuple(f"pos-{i}" for i in range(12)))
    p = build_plan(s)
    assert not p.errors
    assert 1930.0 in [e.wavenumber_cm1 for e in p.events]
    assert p.budget["blank_event_count"] == len(p.events)
    assert p.budget["preliminary_event_count"] == 4
    positions = [e.position_id for e in p.events if e.condition == "pump_on"]
    assert len(set(positions)) == len(positions)
    assert p.budget["preparation_frame_count"] == (len(p.events) + 4) * 6
    assert p.budget["detector_count"] == 1
    assert p.budget["stream_count"] == 2
    assert p.budget["aggregate_rate_hz"] == 2 * s.hf2li_rate_hz
    assert p.budget["restoration_s"] == 3 * s.restoration_estimate_s
    dual = build_plan(replace(s, mode="dual"))
    assert dual.budget["stream_count"] == 3
    assert dual.budget["restoration_s"] == 2 * s.restoration_estimate_s


def test_ns_forward_evaluation_cancellation_and_confirmatory_does_real_simulation():
    class Stopped(Exception):
        pass
    def stop():
        raise Stopped()
    with pytest.raises(Stopped):
        evaluate_schedule(Settings().delays_ns, 200, -.01, Settings().kernel(), noise_sd=.001, cancel_check=stop)
    p = build_plan(replace(Settings(), confirmatory=True, noise_sd=.1, qualification={"forward_simulation_accepted": True, "forward_simulation_record_id": "declared-but-fails-current-design"}))
    assert p.budget["forward_simulation"]["resolved_fraction"] < .8
    assert any("Current IRF/noise/reset" in r for r in p.readiness)


@pytest.mark.parametrize("overrides,reason", [
    ({"repetitions": 10000, "max_storage_bytes": 1}, "storage"),
    ({"repetitions": 1000, "max_storage_bytes": 10**15, "max_pump_events": 10**9}, "memory"),
    ({"max_storage_bytes": 1}, "storage"),
    ({"max_pump_events": 1}, "dose"),
    ({"warmup_frames": 1000000}, "frame capacity"),
])
def test_ns_oversized_plans_fail_before_event_materialization(monkeypatch, overrides, reason):
    import control_app.measurement_modules.nanosecond_stroboscopy.planner as planner_module
    def allocation_forbidden(*args, **kwargs):
        raise AssertionError("Oversized schedule tried to allocate an Event frame table")
    monkeypatch.setattr(planner_module, "event_frames", allocation_forbidden)
    plan = planner_module.build_plan(replace(Settings(), **overrides))
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
    recipe = compile_timing(Settings()).t660_1_recipe
    service.apply_recipe(recipe)
    assert not any(command.startswith(("TFRame:", "TRAin:")) for command in service.commands)
    assert "CHAN:OFF D" in service.commands
    assert "TRIG:SOUR OFF" in service.commands or any("SOUR" in command and "OFF" in command for command in service.commands)
