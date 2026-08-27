from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_preserved_reconstruction_defines_hierarchy_and_new_phases():
    text = (ROOT / "docs/campaign_reconstruction_20260826.md").read_text(encoding="utf-8")
    assert "UNIFIED REGISTRY SUPERSEDES ITS PHASE ORDER" in text
    assert (
        "`polystyrene calibration/alignment partition -> polystyrene holdout -> "
        "blind Mylar validation -> HRP -> optional cryogenic MbCO`"
    ) in text
    for phase in ("HF-01.1", "PF-00", "SV-02A", "SV-02B", "QB-01M"):
        assert phase in text
    assert "| HF-01 | PASS unchanged |" in text
    assert "2 MHz the ceiling is 150 ns" in text


def test_three_time_resolved_modes_are_explicit():
    text = (ROOT / "experiments/time_resolved_acquisition_modes.md").read_text(
        encoding="utf-8"
    )
    assert "## Fixed-wavelength kinetics" in text
    assert "## Phase-shifted rapid-scan stroboscopy" in text
    assert "## Wavelength-by-wavelength stroboscopic reconstruction" in text
    assert "single rapid scan is never an instantaneous spectrum" in text


def test_completed_readbacks_are_not_part_of_this_change():
    # This repository-level guard documents the preservation boundary. Git-based
    # verification is also run in the reconstruction audit/report.
    assert (ROOT / "calibration/system_recalibration_001/readbacks/HF-01/phase_manifest.json").exists()
    assert (ROOT / "characterization/system_characterization_001/readbacks/CH-00/phase_manifest.json").exists()
