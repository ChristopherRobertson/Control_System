"""Read-only loader for explicitly promoted instrument configuration bundles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from control_app.paths import PROMOTED_BUNDLE_ROOT


class PromotedBundleError(RuntimeError):
    """Raised when a requested runtime bundle is absent or not promoted."""


@dataclass(frozen=True)
class PromotedBundle:
    bundle_id: str
    path: Path
    manifest: dict[str, Any]


def load_bundle_registry(root: str | Path | None = None) -> dict[str, Any]:
    bundle_root = Path(root) if root is not None else PROMOTED_BUNDLE_ROOT
    path = bundle_root / "registry.yaml"
    if not path.exists():
        raise PromotedBundleError(f"promoted-bundle registry not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not isinstance(data.get("bundles"), list):
        raise PromotedBundleError(f"invalid promoted-bundle registry: {path}")
    return data


def load_promoted_bundle(
    bundle_id: str, root: str | Path | None = None
) -> PromotedBundle:
    """Load a runtime bundle only when its registry and manifest say PROMOTED."""

    bundle_root = Path(root) if root is not None else PROMOTED_BUNDLE_ROOT
    registry = load_bundle_registry(bundle_root)
    entry = next(
        (
            item
            for item in registry["bundles"]
            if isinstance(item, dict) and item.get("bundle_id") == bundle_id
        ),
        None,
    )
    if entry is None:
        raise PromotedBundleError(f"bundle is not registered: {bundle_id}")
    if entry.get("status") != "PROMOTED":
        raise PromotedBundleError(
            f"bundle {bundle_id} is not promoted (status={entry.get('status')!r})"
        )
    relative = entry.get("path") or bundle_id
    path = (bundle_root / str(relative)).resolve()
    manifest_path = path / "manifest.yaml"
    if not manifest_path.exists():
        raise PromotedBundleError(f"bundle manifest not found: {manifest_path}")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(manifest, dict):
        raise PromotedBundleError(f"invalid bundle manifest: {manifest_path}")
    if manifest.get("bundle_id") != bundle_id:
        raise PromotedBundleError(
            f"bundle ID mismatch: registry={bundle_id}, manifest={manifest.get('bundle_id')!r}"
        )
    if manifest.get("status") != "PROMOTED":
        raise PromotedBundleError(f"bundle manifest is not PROMOTED: {manifest_path}")
    return PromotedBundle(bundle_id=bundle_id, path=path, manifest=manifest)
