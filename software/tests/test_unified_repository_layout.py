from pathlib import Path

import pytest
import yaml

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
    for phase_id in ("HF-01", "HF-01.1", "AR-01", "PF-00", "SV-02A", "SV-02B", "R9", "QB-01M", "MB-01"):
        assert phase_id in order
    positions = {phase_id: order.index(phase_id) for phase_id in order}
    assert positions["HF-01"] < positions["HF-01.1"] < positions["AR-01"]
    assert positions["AR-01"] < positions["PF-00"] < positions["SV-02A"] < positions["SV-02B"]
    assert positions["R9"] < positions["QB-01M"] < positions["MB-01"]


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
