from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_campaign_operator_contract_is_explicit() -> None:
    instructions = (
        REPO_ROOT
        / "campaigns"
        / "instrument_readiness_001"
        / "AGENTS.md"
    ).read_text(encoding="utf-8")
    requirements = (
        REPO_ROOT
        / "campaigns"
        / "instrument_readiness_001"
        / "requirements.md"
    ).read_text(encoding="utf-8")

    assert "one physical action at a time" in instructions
    assert "USER_INPUT_REQUIRED" in instructions
    assert "phase-primary organization" in instructions.lower()
    assert "one physical action at a time" in requirements
    assert "software development do not authorize a" in requirements
    assert "hardware action or scientific acquisition" in requirements


def test_ms01_continues_from_stable_phase_record() -> None:
    record = (
        REPO_ROOT
        / "campaigns"
        / "instrument_readiness_001"
        / "phases"
        / "MS-01"
        / "run_record.md"
    ).read_text(encoding="utf-8")

    assert "PREFLIGHT COMPLETE" in record
    assert "S1 directly to PicoScope CHA" in record
    assert "S2 directly to PicoScope CHB" in record
    assert "MS-02 analysis is not started automatically" in record
