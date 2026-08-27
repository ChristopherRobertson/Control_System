import copy
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, ValidationError

from control_app.paths import (
    CAMPAIGNS_ROOT,
    EVIDENCE_ROOT,
    LOG_ROOT,
    PROMOTED_BUNDLE_ROOT,
    RECIPE_ROOT,
    REPO_ROOT,
    RUN_ROOT,
    hardware_configuration_path,
    wiring_map_path,
)
from control_app.promoted_bundles import (
    PromotedBundleError,
    load_bundle_registry,
    load_promoted_bundle,
)
from tools.validate_phase_registry import validate


def test_compatibility_paths_keep_current_gui_assets_reachable():
    assert REPO_ROOT == Path(__file__).resolve().parents[2]
    assert hardware_configuration_path() == (
        REPO_ROOT / "instrument" / "hardware_configuration.yaml"
    ).resolve()
    assert wiring_map_path() == (
        REPO_ROOT / "instrument" / "wiring_map.yaml"
    ).resolve()
    assert RECIPE_ROOT == REPO_ROOT / "instrument" / "recipes"
    assert RUN_ROOT == REPO_ROOT / "evidence" / "experiments" / "runs"
    assert LOG_ROOT == REPO_ROOT / "evidence" / "experiments" / "logs"
    assert CAMPAIGNS_ROOT.is_dir()
    assert EVIDENCE_ROOT.is_dir()
    assert PROMOTED_BUNDLE_ROOT.is_dir()


def test_unified_phase_registry_is_complete_and_acyclic():
    order = validate()
    assert len(order) == 68
    for phase_id in ("HF-01", "HF-01.1", "AR-01", "PF-00", "SV-02A", "SV-02B", "R9", "QB-01M", "MB-01"):
        assert phase_id in order
    positions = {phase_id: order.index(phase_id) for phase_id in order}
    assert positions["HF-01"] < positions["HF-01.1"] < positions["AR-01"]
    assert positions["AR-01"] < positions["PF-00"] < positions["SV-02A"] < positions["SV-02B"]
    assert positions["R9"] < positions["QB-01M"] < positions["MB-01"]


def test_every_registered_phase_has_one_canonical_phase_home():
    registry = yaml.safe_load(
        (CAMPAIGNS_ROOT / "phase_registry.yaml").read_text(encoding="utf-8")
    )
    campaign_dirs = {
        "instrument-readiness-001": "instrument_readiness_001",
        "hrp-001": "hrp_001",
        "mbco-cryo-001": "mbco_cryo_001",
    }
    expected_counts = {
        "instrument-readiness-001": 47,
        "hrp-001": 10,
        "mbco-cryo-001": 11,
    }

    actual_counts = {campaign_id: 0 for campaign_id in expected_counts}
    for phase in registry["phases"]:
        campaign_id = phase["campaign_id"]
        actual_counts[campaign_id] += 1
        home = (
            CAMPAIGNS_ROOT
            / campaign_dirs[campaign_id]
            / "phases"
            / phase["phase_id"]
        )
        expected_plan = (
            Path("campaigns")
            / campaign_dirs[campaign_id]
            / "phases"
            / phase["phase_id"]
            / "plan.md"
        ).as_posix()
        assert phase["plan"] == expected_plan
        assert (home / "README.md").is_file()
        assert (home / "phase.yaml").is_file()
        assert (home / "plan.md").is_file()

    assert actual_counts == expected_counts


def test_retired_split_campaign_trees_are_absent():
    campaign_root = CAMPAIGNS_ROOT / "instrument_readiness_001"
    for retired_name in ("planning", "procedures", "reports", "promotion"):
        assert not (campaign_root / retired_name).exists()
    assert (campaign_root / "shared" / "phase_execution_requirements.md").is_file()


def test_registry_has_no_promoted_bundle_until_promotion_is_authorized():
    registry = load_bundle_registry()
    assert registry["bundles"] == []
    with pytest.raises(PromotedBundleError, match="not registered"):
        load_promoted_bundle("NOT-PROMOTED")


def test_promoted_bundle_loader_requires_both_registry_and_manifest_promotion(tmp_path):
    (tmp_path / "registry.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "bundles": [
                    {"bundle_id": "BUNDLE-TEST-001", "status": "DRAFT", "path": "test"}
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PromotedBundleError, match="not promoted"):
        load_promoted_bundle("BUNDLE-TEST-001", tmp_path)

    bundle_dir = tmp_path / "test"
    bundle_dir.mkdir()
    (tmp_path / "registry.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "bundles": [
                    {"bundle_id": "BUNDLE-TEST-001", "status": "PROMOTED", "path": "test"}
                ],
            }
        ),
        encoding="utf-8",
    )
    (bundle_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "bundle_id": "BUNDLE-TEST-001",
                "status": "PROMOTED",
                "sources": [],
                "validity": {"purpose": "unit test"},
            }
        ),
        encoding="utf-8",
    )
    bundle = load_promoted_bundle("BUNDLE-TEST-001", tmp_path)
    assert bundle.bundle_id == "BUNDLE-TEST-001"
    assert bundle.manifest["status"] == "PROMOTED"


def test_procedural_writeup_standard_and_template_cover_required_thesis_narrative():
    standard_path = REPO_ROOT / "docs" / "data_contract" / "procedural_writeup_standard.md"
    template_path = (
        REPO_ROOT
        / "campaigns"
        / "templates"
        / "phase_record"
        / "procedural_writeup.template.md"
    )
    standard = standard_path.read_text(encoding="utf-8")
    template = template_path.read_text(encoding="utf-8")

    for required_heading in (
        "Purpose — WHY",
        "Procedure performed — HOW",
        "Results — WHAT",
        "Implications, caveats, and claims",
        "Reproducibility and source map",
    ):
        assert required_heading in standard
        assert required_heading in template

    assert "RETROSPECTIVE_EVIDENCE_RECONSTRUCTION" in standard
    assert "Backfilling documentation does not require rerunning a phase" in standard
    assert "review_status: ACCEPTED" in standard


def test_manifest_schema_requires_accepted_writeup_for_new_terminal_phase():
    schema = json.loads(
        (REPO_ROOT / "instrument" / "schemas" / "phase_manifest.schema.json").read_text(
            encoding="utf-8"
        )
    )
    template = json.loads(
        (
            REPO_ROOT
            / "campaigns"
            / "templates"
            / "phase_record"
            / "phase_manifest.template.json"
        ).read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    validator.validate(template)

    terminal = copy.deepcopy(template)
    terminal["status"] = "PASS"
    with pytest.raises(ValidationError):
        validator.validate(terminal)

    terminal["procedural_writeup"].update(
        {
            "review_status": "ACCEPTED",
            "reviewer_ids": ["REVIEWER-001"],
            "review_utc": "2026-08-27T12:00:00Z",
        }
    )
    validator.validate(terminal)

    historical = copy.deepcopy(template)
    historical["schema_version"] = "1.0.0"
    historical.pop("procedural_writeup")
    validator.validate(historical)


def test_phase_registry_declares_writeup_completion_and_backfill_policy():
    registry = yaml.safe_load((CAMPAIGNS_ROOT / "phase_registry.yaml").read_text(encoding="utf-8"))
    policy = registry["completion_policy"]
    assert policy["required_artifact"] == "procedural_writeup.md"
    assert policy["required_before_new_completion_or_advance"] is True
    assert policy["required_before_promotion_or_thesis_reuse"] is True
    assert policy["historical_scientific_disposition_preserved"] is True
    assert policy["backfill_requires_reacquisition"] is False
