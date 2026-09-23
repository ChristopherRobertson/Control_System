import pytest
import yaml
from control_app.promoted_bundles import PromotedBundleError, load_bundle_registry, load_promoted_bundle

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
