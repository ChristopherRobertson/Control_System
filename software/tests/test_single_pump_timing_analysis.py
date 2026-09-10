"""One-shot electrical timing analysis from synthetic native data; no hardware."""
import csv
from copy import deepcopy

import numpy as np
import pytest

from control_app.workflows.phase_scan_data import DETECTOR_INPUT, SINGLE_DETECTOR_MODE, load_native, save_native
from control_app.workflows.single_pump_timing_analysis import analyze_single_pump_timing_rehearsal


def native_record():
    base = 2**60
    ticks = np.arange(0, 15001, 5, dtype=np.uint64)+np.uint64(base)
    dio = np.full(len(ticks), 1 << 17, dtype=np.uint32)
    dio[180:182] &= np.uint32(~(1 << 17) & 0xffffffff)  # LOW900..910us, then HIGH.
    dio[200:2200] |= np.uint32(1 << 21)  # Sweep1000..11000us.
    for position in range(240, 2161, 96):  # 21 markers1200..10800us.
        dio[position:position+4] |= np.uint32(1 << 22)
    def stream(ts, words):
        return {"timestamp": ts, "x": np.linspace(.01, .03, len(ts)), "y": np.zeros(len(ts)),
                "dio": words, "auxin0": np.zeros(len(ts)), "auxin1": np.zeros(len(ts))}
    readback = {"channel": 1, "units": 2, "start": 2000., "stop": 1900., "interval": 5., "num_triggers": 21}
    return {
        "record_kind": "pump_timing_rehearsal", "record_role": "single_pump_timing_rehearsal",
        "pump_timing_rehearsal": True, "optical_valid": True, "capture_completed": True,
        "detector_mode": SINGLE_DETECTOR_MODE, "detector_input": DETECTOR_INPUT,
        "pump_events": 1, "event": {"pump_enabled": True, "phase_delay_us": 0.},
        "clockbase_hz": 1_000_000., "pre_process_last_timing_tick": base+500,
        "hf2li_input_checks": [{"status": {"status/flags/adcclip/0": 0}}],
        "hf2li_detector_settings": {"/dev/demods/0/rate": {"value": 20_000.},
                                   "/dev/demods/2/rate": {"value": 200_000.}},
        "scan_profile": {"qcl": 1, "start_cm1": 2000., "stop_cm1": 1900., "scan_rate_cm1_s": 10000.,
                         "nominal_sweep_duration_s": .01, "expected_markers": 21, "marker_interval_cm1": 5.},
        "mircat_marker_channel_checks": [
            {"context": context, "available": True, "channel": 1,
             "source": "MIRcatSDK_GetWlTrigChanParams", "readback": deepcopy(readback)}
            for context in ("configured", "after_sweep_setup")],
        "native_chunks": [{"data": {"/dev/demods/0/sample": stream(ticks[::10], dio[::10]),
                                     "/dev/demods/2/sample": stream(ticks, dio)}}],
    }


def analyze(tmp_path, record):
    save_native(tmp_path / "hf2li_native.npz", record)
    return analyze_single_pump_timing_rehearsal(tmp_path, record)


def test_complete_high_low_high_pulse_preserves_large_ticks_and_proposes_margin_bounds(tmp_path):
    record = native_record()
    result = analyze(tmp_path, record)
    assert result["usable_for_timing"] and result["status"] == "USABLE_TIMING_REHEARSAL"
    assert result["pump_sync_falling_ticks"] == [2**60+900]
    assert result["pump_sync_rising_ticks"] == [2**60+910]
    assert result["pump_sync_low_widths_s"] == [10e-6]
    np.testing.assert_allclose(result["pump_sync_low_width_sampling_bounds_s"], [5e-6, 15e-6])
    assert result["pump_sync_baseline_high"] and result["pump_sync_final_high"]
    assert result["markers_observed"] == 21
    assert result["marker_wavenumbers_cm1"] == list(np.arange(2000., 1899., -5.))
    assert result["wavenumber_basis"] == "controller_markers" and result["provisional"]
    np.testing.assert_allclose(np.array(result["marker_minus_sync_minus_programmed_phase_s"])[[0, -1]], [.00029, .00989])
    proposal = result["phase_coverage_proposal"]
    assert proposal["first_phase_us"] == -10900.
    assert proposal["last_phase_us"] == 4750.
    assert proposal["phase_increment_us"] == 50.
    assert proposal["quantization_margin_s_each_direction"] == 5e-6
    assert proposal["common_age_bounds_s_after_margin"][0] <= -.001
    assert proposal["common_age_bounds_s_after_margin"][1] >= .005
    for field in ("usable_for_ratio", "usable_as_background", "trajectory_promoted", "optical_pump_arrival_verified", "independently_calibrated"):
        assert result[field] is False
    assert not proposal["application_settings_modified"] and not proposal["calibration_established"]
    assert result["timing_gap_count"] == result["detector_gap_count"] == result["clipped_check_count"] == 0
    assert (tmp_path / "pump_timing_analysis.png").stat().st_size > 1000
    with (tmp_path / "pump_timing_analysis.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["timestamp_ticks"] == str(2**60)
    assert {row["stream"] for row in rows} == {"sample_demod0", "timing_demod2"}
    assert not (tmp_path / "ch1_spectrum.npz").exists()
    restored = load_native(tmp_path / "hf2li_native.npz")
    np.testing.assert_array_equal(restored["native_chunks"][0]["data"]["/dev/demods/2/sample"]["timestamp"],
                                  record["native_chunks"][0]["data"]["/dev/demods/2/sample"]["timestamp"])
    with pytest.raises(FileExistsError):
        analyze_single_pump_timing_rehearsal(tmp_path, record)


@pytest.mark.parametrize("defect, message", [
    ("inverted_pulse", "HIGH pre-trigger"), ("no_pulse", "exactly one complete"),
    ("missing_return", "returned HIGH"), ("extra_pulse", "exactly one complete"),
    ("precutoff_pulse", "exactly one complete"), ("unstable_baseline", "HIGH pre-trigger"),
    ("timing_gap_before_pump", "Native sample gaps"), ("timing_gap_during_sweep", "Native sample gaps"),
    ("sample_gap_before_pump", "Native sample gaps"), ("sample_gap_during_sweep", "Native sample gaps"),
    ("missing_marker", "21 configured"), ("extra_marker", "Unexpected post-cutoff"),
    ("no_controller", "controller marker readbacks"), ("changed_controller", "count/interval"),
    ("clipped", "clipping was observed"), ("unknown_clipping", "clipping status is unavailable"),
    ("nonfinite", "finite and positive"), ("nonpositive", "finite and positive"),
    ("wrong_event_count", "exactly one completed"), ("incomplete_capture", "completion and safe shutdown"),
    ("incomplete_sweep", "marker-bearing"), ("two_sweeps", "marker-bearing"),
])
def test_invalid_pulse_timing_is_not_accepted_and_native_is_preserved(tmp_path, defect, message):
    record = native_record()
    data = record["native_chunks"][0]["data"]
    timing, sample = data["/dev/demods/2/sample"], data["/dev/demods/0/sample"]
    if defect == "inverted_pulse":
        timing["dio"] ^= np.uint32(1 << 17)
    elif defect == "no_pulse":
        timing["dio"] |= np.uint32(1 << 17)
    elif defect == "missing_return":
        timing["dio"][180:] &= np.uint32(~(1 << 17) & 0xffffffff)
    elif defect == "extra_pulse":
        timing["dio"][2600:2602] &= np.uint32(~(1 << 17) & 0xffffffff)
    elif defect == "precutoff_pulse":
        record["pre_process_last_timing_tick"] = 2**60+950
    elif defect == "unstable_baseline":
        timing["dio"][20:22] &= np.uint32(~(1 << 17) & 0xffffffff)
    elif "gap" in defect:
        target = timing if defect.startswith("timing") else sample
        index = (150 if "before" in defect else 500) if target is timing else (15 if "before" in defect else 50)
        for key in target:
            target[key] = np.delete(target[key], index)
    elif defect == "missing_marker":
        timing["dio"][240:244] &= np.uint32(~(1 << 22) & 0xffffffff)
    elif defect == "extra_marker":
        timing["dio"][2600:2604] |= np.uint32(1 << 22)
    elif defect == "no_controller":
        record.pop("mircat_marker_channel_checks")
    elif defect == "changed_controller":
        record["mircat_marker_channel_checks"][-1]["readback"]["interval"] = 4.
    elif defect == "clipped":
        record["hf2li_input_checks"][0]["status"]["status/flags/adcclip/0"] = 1
    elif defect == "unknown_clipping":
        record["hf2li_input_checks"] = []
    elif defect == "nonfinite":
        sample["x"][30] = np.nan
    elif defect == "nonpositive":
        sample["x"][30] = 0.
    elif defect == "wrong_event_count":
        record["pump_events"] = 0
    elif defect == "incomplete_capture":
        record["optical_valid"] = False
    elif defect == "incomplete_sweep":
        timing["dio"][2200:] |= np.uint32(1 << 21)
    elif defect == "two_sweeps":
        timing["dio"][2400:2900] |= np.uint32(1 << 21)
        for index in (2500, 2600):
            timing["dio"][index:index+4] |= np.uint32(1 << 22)
    summary = analyze(tmp_path, record)
    assert not summary["usable_for_timing"]
    assert summary["status"] == "UNUSABLE"
    assert summary["phase_coverage_proposal"] is None
    assert any(message in reason for reason in summary["unusable_reasons"])
    assert (tmp_path / "hf2li_native.npz").is_file()
    assert (tmp_path / "pump_timing_analysis.json").is_file()


def test_programmed_phase_is_subtracted_from_observed_marker_ages(tmp_path):
    record = native_record()
    record["event"]["phase_delay_us"] = 50.
    result = analyze(tmp_path, record)
    np.testing.assert_allclose(result["marker_minus_sync_minus_programmed_phase_s"],
                               np.array(result["marker_age_from_sync_rise_s"])-50e-6)
    assert result["phase_coverage_proposal"]["first_phase_us"] == -10850.
    assert result["phase_coverage_proposal"]["last_phase_us"] == 4800.


def test_native_source_is_required_before_products(tmp_path):
    with pytest.raises(FileNotFoundError, match="Preserve"):
        analyze_single_pump_timing_rehearsal(tmp_path, native_record())
