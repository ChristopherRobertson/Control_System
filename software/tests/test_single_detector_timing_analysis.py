"""Offline timing-only checks use synthetic native data and never hardware."""
import csv
import json

import numpy as np
import pytest

from control_app.workflows.phase_scan_data import DETECTOR_INPUT, SINGLE_DETECTOR_MODE, load_native, save_native
from control_app.workflows.single_detector_timing_analysis import analyze_single_detector_timing_rehearsal


def native_record(*, idle_high=False):
    base = 2**60
    ticks = np.arange(0, 5001, 5, dtype=np.uint64) + np.uint64(base)
    dio = np.zeros(len(ticks), dtype=np.uint32)
    dio[100:560] |= np.uint32(1 << 21)  # 500 -> 2800 us: 2.3 ms observed.
    for index in (150, 300, 380):  # 250, 1000, 1400 us after Sweep Active.
        dio[index:index + 25] |= np.uint32(1 << 22)
    if idle_high:
        dio |= np.uint32(1 << 17)

    def stream(ts, bits):
        return {"timestamp": ts, "x": np.linspace(.8, 1., len(ts)), "y": np.zeros(len(ts)),
                "dio": bits, "auxin0": np.zeros(len(ts)), "auxin1": np.zeros(len(ts))}

    return {
        "record_kind": "timing_rehearsal", "record_role": "pump_off_timing_rehearsal",
        "optical_valid": True, "capture_completed": True, "detector_mode": SINGLE_DETECTOR_MODE,
        "detector_input": DETECTOR_INPUT, "clockbase_hz": 1_000_000.,
        "pre_process_last_timing_tick": base + 250, "pump_events": 0,
        "pump_outputs_disabled_readback_verified": True,
        "hf2li_input_checks": [{"status": {"status/flags/adcclip/0": 0}}],
        "hf2li_detector_settings": {"/dev/demods/0/rate": {"value": 20_000.},
                                    "/dev/demods/2/rate": {"value": 200_000.}},
        # Requested rates deliberately differ: actual readbacks must govern gaps.
        "scan_profile": {"start_cm1": 1950., "stop_cm1": 1940., "scan_rate_cm1_s": 10_000.,
                         "nominal_sweep_duration_s": .001, "sweep_duration_bounds_s": [.0005, .005],
                         "expected_markers": 3, "detector_rate_sps": 200_000., "timing_rate_sps": 1_000_000.},
        "process_trigger_utc": "2026-09-06T22:00:00+00:00",
        "native_chunks": [{"data": {"/dev/demods/0/sample": stream(ticks[::10], dio[::10]),
                                       "/dev/demods/2/sample": stream(ticks, dio)}}],
    }


def analyze(tmp_path, record):
    save_native(tmp_path / "hf2li_native.npz", record)
    return analyze_single_detector_timing_rehearsal(tmp_path, record)


@pytest.mark.parametrize("idle_high", [False, True])
def test_fast_three_marker_rehearsal_preserves_ticks_and_time_only_products(tmp_path, idle_high):
    record = native_record(idle_high=idle_high)
    summary = analyze(tmp_path, record)
    assert summary["status"] == "USABLE_TIMING_REHEARSAL"
    assert summary["usable_for_timing_rehearsal"]
    assert summary["sweep_active_ticks"] == [2**60 + 500, 2**60 + 2800]
    assert summary["sweep_duration_ticks"] == 2300
    assert summary["sweep_duration_s"] == .0023
    assert summary["marker_offset_ticks"] == [250, 1000, 1400]
    assert summary["marker_spacing_ticks"] == [750, 400]
    assert summary["marker_offsets_s"] == [.00025, .001, .0014]
    assert summary["pump_sync_baseline_high"] is idle_high
    assert summary["pump_sync_transition_count"] == 0
    assert summary["detector_actual_rate_sps"] == 20_000
    assert summary["timing_actual_rate_sps"] == 200_000
    assert summary["detector_native_gap_count"] == summary["timing_native_gap_count"] == 0
    assert summary["sample_count"] == 47
    assert not summary["usable_for_ratio"] and not summary["usable_as_background"]
    assert not summary["spectral_analysis_allowed"] and not summary["trajectory_promoted"]
    assert summary["wavenumber_assignment"] is None
    assert not summary["process_trigger_timestamp_recorded_in_HF2LI"]
    assert summary["process_trigger_latency_s"] is None
    assert summary["host_process_trigger_utc"] == record["process_trigger_utc"]
    with (tmp_path / "timing_analysis.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["stream"] for row in rows} == {"sample_demod0", "timing_demod2"}
    assert rows[0]["timestamp_ticks"] == str(2**60)
    assert "wavenumber" not in rows[0]
    assert (tmp_path / "timing_analysis.png").stat().st_size > 1000
    assert not (tmp_path / "ch1_spectrum.npz").exists()
    saved = load_native(tmp_path / "hf2li_native.npz")
    assert saved["native_chunks"][0]["data"]["/dev/demods/2/sample"]["timestamp"].dtype == np.uint64


@pytest.mark.parametrize("defect, expected", [
    ("clipped", "clipping was observed"), ("unknown_clip", "clipping status is unavailable"),
    ("timing_gap", "Native sample gaps"), ("sample_gap", "Native sample gaps"),
    ("rising_pump", "DIO17 changed level"), ("falling_pump", "DIO17 changed level"),
    ("unstable_baseline", "stable pre-trigger DIO17 baseline"),
    ("missing_marker", "marker count differs"), ("no_markers", "marker-bearing"),
    ("incomplete", "marker-bearing"), ("two_sweeps", "marker-bearing"),
    ("wrong_kind", "explicit pump_off_timing_rehearsal"), ("missing_cutoff", "cutoff is missing"),
    ("missing_rate", "sample-rate readback"), ("bounds", "outside the predeclared"),
    ("missing_bounds", "engineering sweep-duration bounds"),
    ("capture_failed", "completion and safe shutdown"), ("shutdown_failed", "completion and safe shutdown"),
    ("pump_outputs", "Disabled pump timing outputs"), ("nonfinite", "nonfinite samples"),
])
def test_invalid_rehearsals_preserve_native_and_report_unusable(tmp_path, defect, expected):
    record = native_record(idle_high=defect == "falling_pump")
    data = record["native_chunks"][0]["data"]
    timing = data["/dev/demods/2/sample"]
    if defect == "clipped":
        record["hf2li_input_checks"][0]["status"]["status/flags/adcclip/0"] = 1
    elif defect == "unknown_clip":
        record["hf2li_input_checks"] = []
    elif defect in {"timing_gap", "sample_gap"}:
        stream = data[f"/dev/demods/{2 if defect == 'timing_gap' else 0}/sample"]
        index = 250 if defect == "timing_gap" else 25
        for key, values in stream.items():
            stream[key] = np.delete(values, index)
    elif defect == "rising_pump":
        timing["dio"][200:] |= np.uint32(1 << 17)
    elif defect == "falling_pump":
        timing["dio"][200:] &= np.uint32(~(1 << 17) & 0xffffffff)
    elif defect == "unstable_baseline":
        timing["dio"][10:20] |= np.uint32(1 << 17)
    elif defect == "missing_marker":
        timing["dio"][380:405] &= np.uint32(~(1 << 22) & 0xffffffff)
    elif defect == "no_markers":
        timing["dio"] &= np.uint32(~(1 << 22) & 0xffffffff)
    elif defect == "incomplete":
        timing["dio"][560:] |= np.uint32(1 << 21)
    elif defect == "two_sweeps":
        timing["dio"][650:900] |= np.uint32(1 << 21)
        for index in (680, 740, 820):
            timing["dio"][index:index + 10] |= np.uint32(1 << 22)
    elif defect == "wrong_kind":
        record["record_kind"] = "buffer_blank"
    elif defect == "missing_cutoff":
        del record["pre_process_last_timing_tick"]
    elif defect == "missing_rate":
        record["hf2li_detector_settings"] = {}
    elif defect == "bounds":
        record["scan_profile"]["sweep_duration_bounds_s"] = [.0005, .002]
    elif defect == "missing_bounds":
        del record["scan_profile"]["sweep_duration_bounds_s"]
    elif defect == "capture_failed":
        record["capture_completed"] = False
    elif defect == "shutdown_failed":
        record["optical_valid"] = False
    elif defect == "pump_outputs":
        record["pump_outputs_disabled_readback_verified"] = False
    elif defect == "nonfinite":
        data["/dev/demods/0/sample"]["x"][25] = np.nan
    summary = analyze(tmp_path, record)
    assert summary["status"] == "UNUSABLE"
    assert not summary["usable_for_timing_rehearsal"]
    assert not summary["usable_for_ratio"] and not summary["usable_as_background"]
    assert any(expected in reason for reason in summary["unusable_reasons"])
    assert (tmp_path / "hf2li_native.npz").is_file()
    assert json.loads((tmp_path / "timing_analysis.json").read_text())["status"] == "UNUSABLE"


def test_ignores_preserved_pre_cutoff_sweep_and_reports_ancillary_interval(tmp_path):
    record = native_record()
    timing = record["native_chunks"][0]["data"]["/dev/demods/2/sample"]
    timing["dio"][5:45] |= np.uint32(1 << 21)
    timing["dio"][10:12] |= np.uint32(1 << 22)
    timing["dio"][30:32] |= np.uint32(1 << 22)
    summary = analyze(tmp_path, record)
    assert summary["usable_for_timing_rehearsal"]
    assert summary["post_cutoff_marker_bearing_interval_count"] == 1
    assert summary["ancillary_dio21_intervals"] == [[2**60 + 25, 2**60 + 225]]


@pytest.mark.parametrize("extension", ["json", "csv", "png"])
def test_refuses_overwrite_even_when_other_artifacts_do_not_exist(tmp_path, extension):
    record = native_record()
    save_native(tmp_path / "hf2li_native.npz", record)
    occupied = tmp_path / f"timing_analysis.{extension}"
    occupied.write_bytes(b"preserved")
    with pytest.raises(FileExistsError):
        analyze_single_detector_timing_rehearsal(tmp_path, record)
    assert occupied.read_bytes() == b"preserved"
    assert len(list(tmp_path.iterdir())) == 2


def test_requires_preserved_native_record(tmp_path):
    with pytest.raises(FileNotFoundError):
        analyze_single_detector_timing_rehearsal(tmp_path, native_record())
