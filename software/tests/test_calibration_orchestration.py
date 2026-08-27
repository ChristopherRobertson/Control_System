from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_codex_is_the_campaign_operator_interface() -> None:
    instructions = (
        REPO_ROOT
        / "campaigns"
        / "instrument_readiness_001"
        / "procedures"
        / "calibration"
        / "AGENTS.md"
    ).read_text(encoding="utf-8")
    campaign = (
        REPO_ROOT
        / "campaigns"
        / "instrument_readiness_001"
        / "procedures"
        / "calibration"
        / "legacy_campaign_readme.md"
    ).read_text(encoding="utf-8")

    assert "one physical action at a time" in instructions
    assert "USER_INPUT_REQUIRED" in instructions
    assert "monolithic complete-calibration runner" in instructions.lower()
    assert "The retired monolithic timing runner is not a campaign entry point" in campaign


def test_ms01_continues_from_stable_phase_record() -> None:
    record = (
        REPO_ROOT
        / "evidence"
        / "calibration"
        / "system_recalibration_001"
        / "phases"
        / "MS-01"
        / "README.md"
    ).read_text(encoding="utf-8")

    assert "PREFLIGHT COMPLETE" in record
    assert "S1 directly to PicoScope CHA" in record
    assert "S2 directly to PicoScope CHB" in record
    assert "MS-02 analysis is not started automatically" in record
