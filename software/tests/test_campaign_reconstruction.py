from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_canonical_campaign_authorities_define_hierarchy_and_new_phases():
    master = (ROOT / "campaigns/master_sequence.md").read_text(encoding="utf-8")
    registry = (ROOT / "campaigns/phase_registry.yaml").read_text(encoding="utf-8")
    requirements = (
        ROOT / "campaigns/instrument_readiness_001/requirements.md"
    ).read_text(encoding="utf-8")
    mbco_requirements = (
        ROOT / "campaigns/mbco_cryo_001/requirements.md"
    ).read_text(encoding="utf-8")

    assert "independent polystyrene holdout" in master
    assert "blind Mylar independent validation" in master
    assert "Only after R9 restoration and handoff" in master
    assert "predeclared polystyrene partition and holdout" in requirements
    assert "blind Mylar validation" in requirements
    for phase in ("HF-01.1", "PF-00", "SV-02A", "SV-02B", "QB-01M"):
        assert phase in master
        assert f"phase_id: {phase}" in registry
    assert "At 2 MHz" in mbco_requirements
    assert "30% duty ceiling is 150 ns" in mbco_requirements
    assert "1005 ns at 2 MHz is prohibited" in mbco_requirements


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
