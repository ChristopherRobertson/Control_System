"""Planning and configuration tests never connect to laboratory devices."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from control_app.devices.hf2li_service import HF2LIService, HF2LIConfigurationError
from control_app.workflows.regular_phase_scan import (
    HF2Capabilities, RegularPhaseScanSettings, build_regular_phase_scan_plan,
    filter_response, select_hf2_settings,
)


def capabilities():
    # Explicit fake-device supported profile: intentionally irregular values.
    return HF2Capabilities(orders=(1, 4),
        timeconstants_by_order={1: (2e-6, 10e-6, 50e-6, .001), 4: (8.02e-6, 20.1e-6, 49.99e-6, .001)},
        rates_sps=tuple(230263.15789473685/2**i for i in range(12)), verified=True,
        source="simulated-device-profile")


def test_defaults_and_regular_cadence():
    plan = build_regular_phase_scan_plan()
    assert plan.total_scans == 322
    assert plan.total_pump_events == 321
    assert (plan.first_phase_delay_us, plan.last_phase_delay_us) == (-11000, 5000)
    assert plan.frame_period_s == .1
    assert not plan.event_at(0).pump_enabled
    assert plan.to_dict()["sequence"]["fire_to_qswitch_us"] == 250
    assert not plan.hf2_selection["capability_verified"]
    assert plan.hf2_selection["temporal_resolution_s"] > 5*50e-6
    assert plan.hf2_selection["spectral_broadening_cm1"] > 2
    assert plan.nominal_duration_s < 33


def test_editable_pump_window_changes_schedule_and_capacity_without_changing_sweep():
    original = build_regular_phase_scan_plan()
    changed = build_regular_phase_scan_plan(replace(original.settings, pre_pump_ms=2, post_pump_ms=8))
    assert (changed.first_phase_delay_us, changed.last_phase_delay_us, changed.total_scans) == (-12000, 8000, 402)
    assert changed.scan_duration_s == original.scan_duration_s
    assert changed.capture_window == original.capture_window
    assert changed.to_dict()['sequence']['observation_window_s'] == [-.002, .008]
    assert changed.capacity['estimated_retained_bytes'] > original.capacity['estimated_retained_bytes']
    for field, value in [('pre_pump_ms', -1), ('post_pump_ms', 0), ('pre_pump_ms', float('nan'))]:
        with pytest.raises(ValueError, match=field):
            build_regular_phase_scan_plan(replace(original.settings, **{field: value}))
    with pytest.raises(ValueError, match='cadence'):
        build_regular_phase_scan_plan(replace(original.settings, post_pump_ms=80))


@pytest.mark.parametrize('speed,spacing,before,after', [(10000, 50, 6, 6), (5000, 73, 2, 9), (10000, 100, 0, 2)])
def test_complete_sweep_coverage_is_derived_for_every_wavelength(speed, spacing, before, after):
    settings = RegularPhaseScanSettings(scan_speed_cm1_s=speed, phase_delay_us=spacing,
        pre_pump_ms=before, post_pump_ms=after)
    plan = build_regular_phase_scan_plan(settings)
    # Check early, middle and late wavelength positions along the full sweep.
    for age in (0, plan.scan_duration_s/2, plan.scan_duration_s):
        assert plan.first_phase_delay_us*1e-6 + age <= -before/1000 + 1e-12
        assert plan.last_phase_delay_us*1e-6 + age >= after/1000 - 1e-12
    assert plan.to_dict()['sequence']['observation_window_s'] == [-before/1000, after/1000]


def test_memory_breakdown_and_phase_spacing_scaling_at_fixed_rates():
    coarse = build_regular_phase_scan_plan()
    fine = build_regular_phase_scan_plan(replace(RegularPhaseScanSettings(), phase_delay_us=25))
    assert (coarse.total_scans, fine.total_scans) == (322, 642)
    assert coarse.hf2_selection['rate_sps'] == fine.hf2_selection['rate_sps']
    for plan in (coarse, fine):
        capacity = plan.capacity
        assert capacity['allocation_margin_factor'] == capacity['buffer_processing_factor'] == 1
        assert capacity['estimated_retained_bytes'] == (
            capacity['estimated_uncompressed_payload_bytes'] + capacity['metadata_allowance_bytes']
        ) * capacity['allocation_margin_factor'] * capacity['buffer_processing_factor']
    assert fine.capacity['estimated_retained_bytes'] / coarse.capacity['estimated_retained_bytes'] == pytest.approx(642/322)
    large = build_regular_phase_scan_plan(capabilities=replace(HF2Capabilities(), max_retained_bytes=1000))
    assert large.capacity['warning'].startswith('Warning:')
    assert large.capacity['retention_budget_is_advisory']



def test_25us_high_rate_plan_has_no_percentage_or_copy_multiplier():
    rate = 230263.15789473685
    tc = .799995886e-6
    caps = HF2Capabilities(orders=(8,), timeconstants_by_order={8: (tc,)}, rates_sps=(rate,), verified=True)
    plan = build_regular_phase_scan_plan(replace(RegularPhaseScanSettings(), phase_delay_us=25), caps,
                                        {"order": 8, "timeconstant_s": tc, "rate_sps": rate})
    assert plan.total_scans == 642
    assert plan.capacity['estimated_retained_bytes'] == 154470336
    assert plan.capacity['estimated_retained_bytes'] < caps.max_retained_bytes


@pytest.mark.parametrize("field,value", [
    ("pump_repetition_rate_hz", 0), ("pump_repetition_rate_hz", 10.1),
    ("pump_repetition_rate_hz", float("nan")), ("pump_repetition_rate_hz", 3),
    ("pump_repetition_rate_hz", 1e-6), ("scan_speed_cm1_s", .9),
    ("scan_speed_cm1_s", 10001), ("start_wavenumber_cm1", 1649),
    ("stop_wavenumber_cm1", 2051), ("phase_delay_us", .9),
    ("phase_delay_us", 1001), ("repetitions", 2),
])
def test_parameter_limits_and_clock_representability(field, value):
    with pytest.raises(ValueError):
        build_regular_phase_scan_plan(replace(RegularPhaseScanSettings(), **{field: value}))


def test_conflicts_are_specific_and_do_not_mutate_request():
    settings = replace(RegularPhaseScanSettings(), scan_speed_cm1_s=1000)
    with pytest.raises(ValueError, match="cadence"):
        build_regular_phase_scan_plan(settings)
    assert settings.scan_speed_cm1_s == 1000
    with pytest.raises(ValueError, match="timing-table"):
        build_regular_phase_scan_plan(replace(RegularPhaseScanSettings(), phase_delay_us=1))
    assert build_regular_phase_scan_plan(capabilities=replace(capabilities(), max_retained_bytes=1000)).capacity["warning"]
    with pytest.raises(ValueError, match="single installed"):
        build_regular_phase_scan_plan(capabilities=replace(capabilities(), tuning_ranges=((1, 1950, 2050),)))
    with pytest.raises(ValueError, match="fixed-wavenumber"):
        build_regular_phase_scan_plan(replace(RegularPhaseScanSettings(), stop_wavenumber_cm1=2000))


def test_slow_supported_combo_and_cadence_duration():
    settings = replace(RegularPhaseScanSettings(), scan_speed_cm1_s=1000,
                       phase_delay_us=1000, pump_repetition_rate_hz=1)
    plan = build_regular_phase_scan_plan(settings, capabilities())
    assert plan.frame_period_s == 1
    assert plan.settings.rest_period_s == 1
    assert plan.capacity["occupied_frame_s"] < 1


def test_automatic_selection_uses_filter_and_spectral_response():
    caps = capabilities()
    chosen = select_hf2_settings(RegularPhaseScanSettings(), caps)
    assert chosen["order"] == 4
    assert chosen["timeconstant_s"] in caps.timeconstants_by_order[4]
    assert chosen["rate_sps"] in caps.rates_sps
    assert chosen["rate_sps"] >= 7*chosen["bandwidth_hz"]
    assert chosen["temporal_resolution_s"] <= 50e-6
    assert chosen["rate_sps"] < max(caps.rates_sps)
    wider = select_hf2_settings(replace(RegularPhaseScanSettings(), phase_delay_us=1000), caps)
    assert wider["target_temporal_resolution_s"] == .0001  # 1 cm-1 / 10000 cm-1/s
    assert wider["spectral_broadening_cm1"] <= 1


def test_overrides_supported_combinations_and_restore_auto():
    caps = capabilities()
    auto = select_hf2_settings(RegularPhaseScanSettings(), caps)
    manual = select_hf2_settings(RegularPhaseScanSettings(), caps,
        {"order": 4, "timeconstant_s": 49.99e-6, "rate_sps": caps.rates_sps[2]})
    assert manual["mode"] == "manual"
    assert manual["temporal_resolution_s"] > 50e-6
    assert manual["warning"]
    assert select_hf2_settings(RegularPhaseScanSettings(), caps, {}) == auto
    for override in ({"order": 3}, {"order": True}, {"order": 1.8}, {"rate_sps": 20000},
                     {"timeconstant_s": 10e-6, "order": 4}):
        with pytest.raises(ValueError):
            select_hf2_settings(RegularPhaseScanSettings(), caps, override)
    with pytest.raises(ValueError, match="streams"):
        select_hf2_settings(RegularPhaseScanSettings(), replace(caps, enabled_streams=(0,)))


def test_filter_response_is_physical_not_phase_spacing():
    response = filter_response(1, 50e-6, 230263.15789473685, 230263.15789473685, 10000)
    assert response["filter_rise_time_s"] == pytest.approx(2.197224577*50e-6)
    assert response["filter_group_delay_s"] == 50e-6
    assert response["spectral_broadening_cm1"] == pytest.approx(1.0986122885)


def test_preview_profile_matches_retained_successful_readbacks():
    root = Path(__file__).resolve().parents[2]
    path = root / "evidence/experiments/runs/single_detector_ftir_20260906T203723_580408Z/full_phase_sample_deferred_read_01/Phase Scan/2026-09-06/20260906T232516_385204Z_run/acquisition_preflight.json"
    if not path.exists():
        pytest.skip("retained local acquisition record unavailable")
    nodes = json.loads(path.read_text())["hf2li_settings_snapshot"]["nodes"]
    chosen = build_regular_phase_scan_plan().hf2_selection
    for setting, node in (("order", "order"), ("timeconstant_s", "timeconstant"), ("rate_sps", "rate")):
        assert chosen[setting] == nodes[f"/dev18500/demods/0/{node}"]["value"]
    assert chosen["timing_rate_sps"] == nodes["/dev18500/demods/2/rate"]["value"]


class ConfigurationOnlyHF2(HF2LIService):
    def __init__(self):
        super().__init__({})
        self._device_id = "fake"
        self.nodes = {f"/fake/demods/{i}/{node}": value for i in range(6)
                      for node, value in (("enable", int(i == 3)), ("order", 4),
                                          ("timeconstant", .001), ("rate", 1000.))}
        self.writes = []
    def _get_node(self, kind, path):
        return self.nodes[path]
    def _set_node(self, method, path, value):
        self.writes.append((path, value))
        if path.endswith("/rate") and value != 1000:
            ladder = [230263.15789473685/2**i for i in range(16)]
            value = min(ladder, key=lambda x: abs(x-value))
        self.nodes[path] = value
    def sync(self):
        pass


def test_connected_discovery_uses_actual_values_and_restores():
    service = ConfigurationOnlyHF2()
    before = service.nodes.copy()
    caps = service.discover_phase_scan_capabilities()
    assert caps["verified"]
    assert caps["enabled_streams"] == (0, 2)
    assert 20000 not in caps["rates_sps"]
    assert caps["timing_rate_sps"] == pytest.approx(230263.15789473685)
    assert service.nodes == before
    assert all("/demods/" in node for node, _ in service.writes)


@pytest.mark.parametrize("changes", [
    {"orders": (0,)}, {"timeconstants_by_order": {4: (-1e-6,)}},
    {"rates_sps": (float("nan"),)}, {"timing_rate_sps": float("inf")},
])
def test_invalid_capability_profiles_are_rejected(changes):
    with pytest.raises(ValueError, match="capabilit|supported"):
        build_regular_phase_scan_plan(capabilities=replace(HF2Capabilities(), **changes))


def test_unobservable_short_scan_is_rejected_in_preview():
    with pytest.raises(ValueError, match="shorter than two"):
        build_regular_phase_scan_plan(RegularPhaseScanSettings(stop_wavenumber_cm1=1999.9999))


def test_spectral_target_warning_does_not_misstate_phase_spacing():
    chosen = select_hf2_settings(RegularPhaseScanSettings(phase_delay_us=1000))
    assert chosen["temporal_resolution_s"] < .001
    assert not chosen["resolution_target_met"]
    assert "temporal/spectral resolution target" in chosen["warning"]


def test_discovery_restores_even_on_bad_rate_readback():
    service = ConfigurationOnlyHF2()
    before = service.nodes.copy()
    original = service._get_node
    calls = [0]
    def fail_once(kind, path):
        calls[0] += 1
        if calls[0] == 31:
            return float("nan")
        return original(kind, path)
    service._get_node = fail_once
    with pytest.raises(HF2LIConfigurationError):
        service.discover_phase_scan_capabilities()
    assert service.nodes == before


def test_discovery_retains_supported_options_after_individual_candidate_rejection():
    service = ConfigurationOnlyHF2()
    before = service.nodes.copy()
    original = service._set_node
    def reject_subset(method, path, value):
        if path.endswith("/timeconstant") and value < 2e-6:
            raise HF2LIConfigurationError("This device rejects this short constant")
        if path.endswith("/rate") and value < 100:
            raise HF2LIConfigurationError("This device rejects this slow rate")
        original(method, path, value)
    service._set_node = reject_subset
    caps = service.discover_phase_scan_capabilities()
    assert caps["orders"] == tuple(range(1, 9))
    assert all(min(values) >= 2e-6 for values in caps["timeconstants_by_order"].values())
    assert caps["rates_sps"] and min(caps["rates_sps"]) >= 100
    assert service.nodes == before


@pytest.mark.parametrize("order,tc,rate", [(4, 8.02e-6, 112.43318256578948), (1, 2e-6, 230263.15789473685)])
def test_supported_filter_rate_is_advisory_and_keeps_all_overrides(order, tc, rate):
    caps = capabilities()
    requested = {"order": order, "timeconstant_s": tc, "rate_sps": rate}
    selected = select_hf2_settings(RegularPhaseScanSettings(), caps, requested)
    assert selected["requested"] == requested
    assert all(selected[k] == v for k, v in requested.items())
    assert not selected["anti_alias_guideline_met"]
    assert "Aliasing advisory" in selected["warning"]
    assert "not a hardware incompatibility" in selected["warning"]
    assert "has not been quantified" in selected["warning"]


def test_screenshot_order_eight_configuration_has_advisory_not_error():
    rate = 230263.15789473685
    tc = .799995886e-6
    caps = HF2Capabilities(orders=(8,), timeconstants_by_order={8: (tc,)}, rates_sps=(rate,), verified=True)
    requested = {"order": 8, "timeconstant_s": tc, "rate_sps": rate}
    selected = select_hf2_settings(replace(RegularPhaseScanSettings(), phase_delay_us=25), caps, requested)
    assert selected["sample_rate_to_bandwidth_ratio"] == pytest.approx(3.847, rel=.001)
    assert selected["filter_attenuation_at_nyquist_db"] > 0
    assert selected["requested"] == requested
    assert "Aliasing advisory" in selected["warning"]


def test_unsupported_time_constant_for_order_lists_accepted_values_and_orders():
    caps = capabilities()
    requested = {"order": 4, "timeconstant_s": 10e-6, "rate_sps": max(caps.rates_sps)}
    with pytest.raises(ValueError) as caught:
        select_hf2_settings(RegularPhaseScanSettings(), caps, requested)
    message = str(caught.value)
    assert "time constant 10 µs" in message
    assert "unsupported for the selected filter order" in message
    assert "order 4: 8.02 µs, 20.1 µs, 49.99 µs, 1000 µs" in message
    assert "accepted at order 1" in message
    assert "Set Filter order to 1" in message
    recovered = select_hf2_settings(RegularPhaseScanSettings(), caps, {**requested, "order": 1})
    assert recovered["timeconstant_s"] == requested["timeconstant_s"]


def test_unsupported_nominal_rate_offers_an_accepted_rate_instead_of_inventing_one():
    caps = capabilities()
    requested = {"order": 4, "timeconstant_s": 49.99e-6, "rate_sps": 20000.}
    with pytest.raises(ValueError) as caught:
        select_hf2_settings(RegularPhaseScanSettings(), caps, requested)
    message = str(caught.value)
    assert "20000 Sa/s is unsupported with the enabled CH1 and DIO streams" in message
    assert "Accepted dropdown rates include" in message
    accepted_rate = caps.rates_sps[4]
    assert f"Set CH1 sample rate to {accepted_rate:.12g} Sa/s" in message
    recovered = select_hf2_settings(RegularPhaseScanSettings(), caps, {**requested, "rate_sps": accepted_rate})
    assert recovered["rate_sps"] in caps.rates_sps


def test_automatic_falls_back_with_advisory_when_guideline_cannot_be_met():
    caps = HF2Capabilities(orders=(4,), timeconstants_by_order={4: (8e-6,)}, rates_sps=(1000.,), verified=True)
    selected = select_hf2_settings(RegularPhaseScanSettings(), caps)
    assert selected["mode"] == "automatic"
    assert selected["rate_sps"] == 1000.
    assert not selected["anti_alias_guideline_met"]
    assert "Aliasing advisory" in selected["warning"]
    assert "resolution target" in selected["warning"]


def test_unsupported_order_message_lists_all_supported_orders():
    caps = HF2Capabilities(orders=tuple(range(1, 9)), timeconstants_by_order={order: (.001,) for order in range(1, 9)})
    with pytest.raises(ValueError) as caught:
        select_hf2_settings(RegularPhaseScanSettings(), caps, {"order": 9})
    assert "Accepted orders: 1, 2, 3, 4, 5, 6, 7, 8" in str(caught.value)
