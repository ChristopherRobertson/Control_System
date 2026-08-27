from __future__ import annotations

import pytest

from control_app.config_loader import REPO_ROOT
from control_app.workflows.mircat_sweep_scan import (
    MircatSweepScanError,
    _validate_campaign_gate,
    _wavelength_targets,
)
from control_app.workflows.sweep_export import segmented_kaleidagraph_rows_from_hf2li_record


def _record(dio_values: list[int]) -> dict:
    times = [float(index) for index in range(len(dio_values))]
    return {
        "data": {
            "/dev/demods/0/sample": [{"timestamp": times, "r": times}],
            "/dev/demods/3/sample": [{"timestamp": times, "r": [100.0 + t for t in times]}],
            "/dev/demods/2/sample": [{"timestamp": times, "dio": dio_values}],
        }
    }


def test_segmented_export_excludes_gaps_and_calibrates_each_segment() -> None:
    active = 1 << 4
    marker = 1 << 7
    # Active at [1, 5) and [6, 11); marker rising edges at 2, 4, 7, and 9.
    dio = [0, active, active | marker, active, active | marker, 0,
           active, active | marker, active, active | marker, active, 0]
    rows, metadata = segmented_kaleidagraph_rows_from_hf2li_record(
        _record(dio),
        wavelength_targets_cm1=[2050, 2045, 2030, 2025],
        sweep_active_bit=4,
        wavelength_trigger_bit=7,
    )

    assert [row[1] for row in rows] == [1, 2, 3, 4, 6, 7, 8, 9, 10]
    assert [row[0] for row in rows] == pytest.approx(
        [2052.5, 2050, 2047.5, 2045, 2032.5, 2030, 2027.5, 2025, 2022.5]
    )
    assert [row[2] for row in rows] == [101, 102, 103, 104, 106, 107, 108, 109, 110]
    assert metadata["segment_count"] == 2
    assert metadata["captured_anchor_count"] == 4


def test_segmented_export_rejects_ambiguous_marker_count() -> None:
    active = 1 << 4
    marker = 1 << 7
    with pytest.raises(ValueError, match="edge count does not match"):
        segmented_kaleidagraph_rows_from_hf2li_record(
            _record([active, active | marker, active, 0]),
            wavelength_targets_cm1=[2050, 2045],
            sweep_active_bit=4,
            wavelength_trigger_bit=7,
        )


def test_segmented_export_rejects_segment_with_one_anchor() -> None:
    active = 1 << 4
    marker = 1 << 7
    with pytest.raises(ValueError, match="at least two"):
        segmented_kaleidagraph_rows_from_hf2li_record(
            _record([active, active | marker, active, 0]),
            wavelength_targets_cm1=[2050],
            sweep_active_bit=4,
            wavelength_trigger_bit=7,
        )


def test_descending_wavelength_targets_include_endpoints() -> None:
    assert _wavelength_targets(2050, 2038, 5) == [2050, 2045, 2040, 2038]


def test_sweep_candidate_cannot_run_without_phase_approval(tmp_path) -> None:
    request = {
        "campaign_gate": {
            "campaign_id": "system_recalibration_001",
            "allowed_phases": ["MD-01", "MSW-01"],
            "phase_id": "USER_INPUT_REQUIRED",
            "phase_run_id": "USER_INPUT_REQUIRED",
            "approved_phase_directory": "USER_INPUT_REQUIRED",
            "status": "CANDIDATE_NOT_APPROVED_FOR_EXECUTION",
        }
    }
    with pytest.raises(MircatSweepScanError, match="non-executable candidate"):
        _validate_campaign_gate(request, tmp_path)


def test_sweep_gate_accepts_only_stable_named_phase_directory() -> None:
    approved = REPO_ROOT / "campaigns" / "instrument_readiness_001" / "phases" / "MD-01"
    request = {
        "campaign_gate": {
            "campaign_id": "system_recalibration_001",
            "allowed_phases": ["MD-01", "MSW-01"],
            "phase_id": "MD-01",
            "phase_run_id": "system_recalibration_001_MD-01_001",
            "approved_phase_directory": str(approved),
            "status": "APPROVED_FOR_EXECUTION",
        }
    }
    _validate_campaign_gate(request, approved / "raw")
    with pytest.raises(MircatSweepScanError, match="inside the approved"):
        _validate_campaign_gate(request, REPO_ROOT / "evidence" / "experiments" / "runs" / "wrong-directory")


def test_sweep_gate_cannot_expand_its_own_phase_scope() -> None:
    approved = REPO_ROOT / "campaigns" / "instrument_readiness_001" / "phases" / "E2E-01"
    request = {
        "campaign_gate": {
            "campaign_id": "system_recalibration_001",
            "allowed_phases": ["E2E-01"],
            "phase_id": "E2E-01",
            "phase_run_id": "system_recalibration_001_E2E-01_001",
            "approved_phase_directory": str(approved),
            "status": "APPROVED_FOR_EXECUTION",
        }
    }
    with pytest.raises(MircatSweepScanError, match="exactly the MD-01 and MSW-01"):
        _validate_campaign_gate(request, approved)
