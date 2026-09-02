from dataclasses import replace

import numpy as np
import pytest

from control_app.workflows.phase_scan import PhaseScanSettings
from control_app.workflows.phase_scan_data import Spectrum
from control_app.workflows.phase_scan_pulse_coverage import analyze_scan_pulse_coverage


def synthetic_attempt(*, duration_s=50e-6, missing_a=(), missing_b=(), sample_interval_ns=16.0,
                      sweep_start_offset_s=0.0):
    rate_hz = 2_000_000.0
    period = 1 / rate_hz
    dt = sample_interval_ns * 1e-9
    pre = int(round(5e-6 / dt))
    count = pre + int(np.ceil((sweep_start_offset_s + duration_s + 5e-6) / dt))
    times = (np.arange(count)-pre)*dt
    phase = 100e-9
    opportunity = np.rint((times-phase)/period).astype(int)
    centers = phase + opportunity*period
    pulse = np.abs(times-centers) <= 48e-9
    a = np.where(pulse & ~np.isin(opportunity, missing_a), 6000, 50).astype(np.int16)
    b = np.where(pulse & ~np.isin(opportunity, missing_b), 15000, 100).astype(np.int16)
    pico = {"sample_interval_ns": sample_interval_ns, "pre_trigger_samples": pre,
            "maximum_adc_value": 32767, "overflow": 0, "ch_a_adc": a, "ch_b_adc": b,
            "external_trigger_basis": ("mircat_sweep_active" if sweep_start_offset_s == 0 else
                                       "t660_1_chd_process_marker")}
    if sweep_start_offset_s:
        pico.update({"sweep_start_offset_s": sweep_start_offset_s,
                     "sweep_start_uncertainty_s": 10e-9,
                     "trigger_alignment_qualification_id": "synthetic-chd-alignment"})
    clockbase = 100_000_000
    start_tick = clockbase
    stop_tick = start_tick + round(duration_s*clockbase)
    metadata = {"optical_valid": True, "wavenumber_basis": "measured", "pump_time_basis": "measured",
                "timestamp_origin_ticks": 0, "clockbase_hz": clockbase,
                "sweep_active_ticks": [start_tick, stop_tick]}
    times_hf = np.linspace(1.0, 1.0+duration_s, 101)
    spectrum = Spectrum(np.linspace(2000, 1999, 101), np.ones(101), np.ones(101), times_hf, 1.0,
                        {**metadata, "segment_metadata": [metadata]}, np.zeros(101, dtype=np.int32))
    native = {"probe_repetition_rate_hz_readback": rate_hz, "segments": [{"picoscope": pico}]}
    settings = replace(PhaseScanSettings(), phase_delay_us=5.0)
    return native, spectrum, settings


def analyze(**kwargs):
    native, spectrum, settings = synthetic_attempt(**kwargs)
    return analyze_scan_pulse_coverage(native, spectrum, settings)


def test_one_missing_of_ten_is_accepted_and_one_channel_loss_is_discrepancy():
    report = analyze(missing_b=(1,))
    first = report["segments"][0]["intervals"][0]
    assert first["expected_opportunities"] == 10
    assert first["coverage_fraction"] == pytest.approx(1.0)
    assert first["cha_only"] == 1
    assert report["missing_opportunities"] == 0
    assert report["detector_path_discrepancies"] == 1
    assert report["status"] == "ACCEPTABLE"

    report = analyze(missing_a=(1,), missing_b=(1,))
    first = report["segments"][0]["intervals"][0]
    assert first["coverage_fraction"] == pytest.approx(.9)
    assert first["acceptable"]
    assert report["status"] == "ACCEPTABLE"


def test_clustered_nonconsecutive_losses_fail_interval_without_consecutive_gate():
    report = analyze(missing_a=(1, 3), missing_b=(1, 3))
    first = report["segments"][0]["intervals"][0]
    assert first["coverage_fraction"] == pytest.approx(.8)
    assert first["maximum_consecutive_missing"] == 1
    assert not first["acceptable"]
    assert "RECONSTRUCTION_INTERVAL_COVERAGE" in report["repeat_reasons"]
    assert "CONSECUTIVE_MISSING_PULSES" not in report["repeat_reasons"]


def test_two_consecutive_losses_force_reacquisition():
    report = analyze(missing_a=(1, 2), missing_b=(1, 2))
    assert report["maximum_consecutive_missing"] == 2
    assert "CONSECUTIVE_MISSING_PULSES" in report["repeat_reasons"]
    assert report["reacquire_required"]


def test_whole_scan_fraction_triggers_even_when_every_interval_is_exactly_ninety_percent():
    missing = tuple(range(1, 100, 10))
    report = analyze(missing_a=missing, missing_b=missing)
    assert all(interval["acceptable"] for interval in report["segments"][0]["intervals"])
    assert report["missing_fraction"] == pytest.approx(.10)
    assert report["repeat_reasons"] == ["WHOLE_SCAN_MISSING_FRACTION"]


def test_sampling_slower_than_48_ns_is_unavailable_not_silently_accepted():
    report = analyze(sample_interval_ns=64.0)
    assert report["analysis_status"] == "PARTIAL_OR_UNAVAILABLE"
    assert report["status"] == "REACQUIRE"
    assert "48 ns/sample" in report["segments"][0]["reason"]


def test_qualified_chd_offset_crops_and_bins_the_observed_sweep_interval():
    report = analyze(sweep_start_offset_s=20e-6)
    segment = report["segments"][0]
    assert report["status"] == "ACCEPTABLE"
    assert segment["external_trigger_basis"] == "t660_1_chd_process_marker"
    assert segment["sweep_start_offset_s"] == pytest.approx(20e-6)
    assert segment["trigger_alignment_qualification_id"] == "synthetic-chd-alignment"
    assert segment["intervals"][0]["expected_opportunities"] == 10
