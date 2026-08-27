from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_preserved_reconstruction_defines_hierarchy_and_new_phases():
    text = (
        ROOT / "campaigns/migration/campaign_reconstruction_20260826.md"
    ).read_text(encoding="utf-8")
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
    text = (ROOT / "campaigns/methods/time_resolved_acquisition_modes.md").read_text(
        encoding="utf-8"
    )
    assert "## Fixed-wavelength kinetics" in text
    assert "## Phase-shifted rapid-scan stroboscopy" in text
    assert "## Wavelength-by-wavelength stroboscopic reconstruction" in text
    assert "single rapid scan is never an instantaneous spectrum" in text


def test_completed_phase_packages_are_preserved_in_self_contained_phase_homes():
    assert (
        ROOT
        / "campaigns/instrument_readiness_001/phases/HF-01/phase_manifest.json"
    ).exists()
    assert (
        ROOT
        / "campaigns/instrument_readiness_001/phases/CH-00/phase_manifest.json"
    ).exists()
    assert not (ROOT / "evidence/calibration").exists()
    assert not (ROOT / "evidence/characterization").exists()
