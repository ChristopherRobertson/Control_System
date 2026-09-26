"""Per-tab requests win over a previous experiment's 10 Hz clock."""
from dataclasses import replace

import pytest


@pytest.mark.parametrize("requested,expected", [(None, 2_000_000.), (1_000_000., 1_000_000.)])
@pytest.mark.parametrize("mode", ["single", "dual"])
def test_experiment_rate_policy(requested, expected, mode):
    from control_app.measurement_modules.steady_state_slow_scan.settings import SlowScanSettings
    from control_app.measurement_modules.steady_state_slow_scan.planner import build_plan, simulation_inputs
    slow = SlowScanSettings(mode=mode, repetition_rate_hz=requested)
    inputs = simulation_inputs(slow)
    inputs.scientific_profile["probe_rate_hz"] = 10.
    assert build_plan(slow, inputs).selected["probe_rate_hz"] == expected

    from control_app.measurement_modules.fixed_wavenumber_kinetics.settings import Settings as Fixed
    from control_app.measurement_modules.fixed_wavenumber_kinetics.planner import build_plan as fixed_plan
    fixed = fixed_plan(Fixed(mode=mode, probe_rate_hz=requested), evidence={"operating_profile": {
        "probe_recipe": {"clock": {"frequency": "10Hz"}}, "timing": {"input_frequency_hz": 10.}}})
    assert fixed.resolved["timing"]["input_frequency_hz"] == expected
    assert fixed.resolved["mircat"]["pulse_rate_hz"] == expected * 1.05

    from control_app.measurement_modules.repeated_rapid_scan.settings import AcquisitionIntent
    from control_app.measurement_modules.repeated_rapid_scan.planner import resolve_intent_settings
    rapid = resolve_intent_settings(AcquisitionIntent(), mode=mode,
        capabilities={"live_settings": {"probe_frequency_hz": 10.}},
        overrides={} if requested is None else {"probe_frequency_hz": requested})
    assert rapid.probe_frequency_hz == expected
    assert rapid.mircat_pulse_rate_hz == expected * 1.05

    from control_app.measurement_modules.microsecond_stroboscopy.settings import default_settings
    from control_app.measurement_modules.microsecond_stroboscopy.planner import resolve_settings
    micro = default_settings(mode)
    micro = replace(micro, timing=replace(micro.timing, probe_rate_hz=requested or 10.),
        manual_overrides=() if requested is None else ("timing.probe_rate_hz",))
    assert resolve_settings(micro, {"actual_values": {"timing.probe_rate_hz": 10.}}).timing.probe_rate_hz == expected

    from control_app.measurement_modules.single_pump_scan_burst.settings import Settings as Burst, resolve_settings as burst_resolve
    burst = burst_resolve(Burst(mode=mode, probe_rate_hz=requested), installed_readbacks={"probe_rate_hz": 10.})
    assert burst.probe_rate_hz == expected
    assert burst.mircat_internal_pulse_rate_hz == expected * 1.05

    from control_app.measurement_modules.nanosecond_stroboscopy.settings import Settings as Nano, resolve_settings as nano_resolve
    nano = nano_resolve(Nano(mode=mode, execution_mode="simulation",
        laser_settings={} if requested is None else {"probe_repetition_rate_hz": requested})).settings
    assert nano.mircat_pulse_rate_hz == expected
    # Sparse event timing must not turn into a continuous MHz pulse train.
    assert nano.probe_period_s >= nano.cycle_interval_s


@pytest.mark.parametrize("rate", [1_000_000., 2_000_000.])
def test_phase_scan_divider_follows_requested_rate(rate):
    from control_app.measurement_modules.phase_scan.regular_phase_scan import RegularPhaseScanSettings, build_regular_phase_scan_plan
    settings = RegularPhaseScanSettings(probe_repetition_rate_hz=rate)
    plan = build_regular_phase_scan_plan(settings)
    record = plan.to_dict()
    assert plan.settings.probe_repetition_rate_hz == rate
    assert plan.settings.mircat_internal_repetition_rate_hz == rate * 1.05
    assert record["derived"]["frame_predivider"] == round(rate * plan.frame_period_s)


@pytest.mark.parametrize("rate,width", [(2_000_000.,142.), (2_100_000.,142.),
                                      (3_000_000.,100.), (3_150_000.,95.)])
def test_automatic_internal_width_stays_below_thirty_percent_after_sdk_encoding(rate, width):
    import struct
    from decimal import Decimal
    from control_app.measurement_host.laser_settings import mircat_automatic_width_ns
    selected = mircat_automatic_width_ns(rate)
    assert selected == width
    sdk_rate, sdk_width = struct.unpack("ff", struct.pack("ff", rate, selected))
    assert Decimal(str(sdk_rate)) * Decimal(str(sdk_width)) / Decimal("1e9") <= Decimal(".30")


def test_high_rate_planners_shorten_automatic_internal_width():
    from control_app.measurement_modules.fixed_wavenumber_kinetics.settings import Settings as Fixed
    from control_app.measurement_modules.fixed_wavenumber_kinetics.planner import build_plan
    fixed = build_plan(Fixed(probe_rate_hz=3_000_000.))
    assert fixed.resolved["mircat"]["pulse_rate_hz"] == 3_150_000.
    assert fixed.resolved["mircat"]["pulse_width_ns"] == 95.
    from control_app.measurement_modules.repeated_rapid_scan.settings import AcquisitionIntent
    from control_app.measurement_modules.repeated_rapid_scan.planner import resolve_intent_settings
    rapid = resolve_intent_settings(AcquisitionIntent(), overrides={"probe_frequency_hz": 3_000_000.})
    assert rapid.mircat_pulse_width_ns == 95.
    from control_app.measurement_modules.microsecond_stroboscopy.settings import default_settings
    from control_app.measurement_modules.microsecond_stroboscopy.planner import resolve_settings
    micro = default_settings()
    micro = replace(micro, timing=replace(micro.timing, probe_rate_hz=3_000_000.),
                    manual_overrides=("timing.probe_rate_hz",))
    assert resolve_settings(micro).timing.mircat_pulse_width_ns == 95.
    from control_app.measurement_modules.single_pump_scan_burst.settings import Settings as Burst, resolve_settings as burst_resolve
    assert burst_resolve(Burst(probe_rate_hz=3_000_000.)).probe_pulse_width_s == pytest.approx(95e-9)
    # Width selection does not override other timing or vendor limits.
