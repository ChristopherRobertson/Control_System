"""Read phase acquisition qualification from an already promoted runtime bundle."""
from __future__ import annotations

from copy import deepcopy
import math

from control_app.promoted_bundles import PromotedBundle, PromotedBundleError


def phase_scan_qualification_from_bundle(bundle: PromotedBundle) -> dict:
    """Consume the runtime.phase_scan mapping returned by load_promoted_bundle.

    The registry/manifest loader remains the promotion authority. This function
    only reads its runtime values; it never loads campaign records or promotes
    a bundle. The full calibration trajectory remains in the returned mapping
    for range, direction, and timing-reference validation by the planner.
    """
    if (not isinstance(bundle, PromotedBundle) or bundle.manifest.get("status") != "PROMOTED"
            or bundle.manifest.get("bundle_id") != bundle.bundle_id):
        raise PromotedBundleError("Phase acquisition requires an explicitly promoted runtime bundle")
    runtime = bundle.manifest.get("runtime", {})
    values = runtime.get("phase_scan") if isinstance(runtime, dict) else None
    if not isinstance(values, dict):
        raise PromotedBundleError(f"Bundle {bundle.bundle_id} has no runtime.phase_scan qualification")
    trajectory = values.get("calibrated_trajectory")
    duration = values.get("qualified_sweep_active_s")
    if not isinstance(trajectory, dict) or not str(trajectory.get("source_id") or "").strip():
        raise PromotedBundleError("Phase qualification requires an identified calibrated trajectory")
    if (isinstance(duration, bool) or not isinstance(duration, (int, float))
            or not math.isfinite(duration) or duration <= 0):
        raise PromotedBundleError("Phase qualification requires a positive qualified Sweep Active duration")
    return {"calibrated_trajectory": deepcopy(trajectory), "qualified_sweep_active_s": float(duration),
            "bundle_id": bundle.bundle_id}
