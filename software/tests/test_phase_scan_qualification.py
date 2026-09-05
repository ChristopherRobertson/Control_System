"""Runtime qualification is read only from explicitly promoted bundles."""
import pytest
import yaml

from control_app.promoted_bundles import load_promoted_bundle, PromotedBundleError
from control_app.workflows.phase_scan import PhaseScanSettings, build_phase_scan_plan
from control_app.workflows.phase_scan_qualification import phase_scan_qualification_from_bundle


def make_bundle(tmp_path, *, status="PROMOTED", duration=.00232):
    path = tmp_path / "synthetic"
    path.mkdir()
    (tmp_path / "registry.yaml").write_text(yaml.safe_dump({"bundles": [
        {"bundle_id": "SYNTHETIC-TEST", "path": "synthetic", "status": status}]}))
    (path / "manifest.yaml").write_text(yaml.safe_dump({
        "bundle_id": "SYNTHETIC-TEST", "status": status,
        "runtime": {"phase_scan": {"qualified_sweep_active_s": duration,
            "calibrated_trajectory": {"source_id": "SYNTHETIC-TEST-TRAJECTORY",
                "time_reference": "process_trigger", "time_s": [.0002, .00135, .0025],
                "wavenumber_cm1": [1950., 1945., 1940.]}}}}))
    return load_promoted_bundle("SYNTHETIC-TEST", tmp_path)


def test_runtime_bundle_supplies_trajectory_without_modification(tmp_path):
    bundle = make_bundle(tmp_path)
    before = (bundle.path / "manifest.yaml").read_bytes()
    qualification = phase_scan_qualification_from_bundle(bundle)
    plan = build_phase_scan_plan(PhaseScanSettings(), calibrated_trajectory=qualification["calibrated_trajectory"])
    assert plan.calibrated
    assert plan.first_phase_delay_us == -3500
    assert qualification["qualified_sweep_active_s"] == .00232
    assert (bundle.path / "manifest.yaml").read_bytes() == before
    qualification["calibrated_trajectory"]["source_id"] = "changed copy"
    assert bundle.manifest["runtime"]["phase_scan"]["calibrated_trajectory"]["source_id"] == "SYNTHETIC-TEST-TRAJECTORY"


def test_unpromoted_bundle_cannot_supply_runtime_values(tmp_path):
    with pytest.raises(PromotedBundleError, match="not promoted"):
        make_bundle(tmp_path, status="DRAFT")


@pytest.mark.parametrize("duration", [None, 0, -1, True, float("nan")])
def test_qualification_duration_must_be_usable_before_hardware(tmp_path, duration):
    with pytest.raises(PromotedBundleError, match="qualified Sweep Active"):
        phase_scan_qualification_from_bundle(make_bundle(tmp_path, duration=duration))
