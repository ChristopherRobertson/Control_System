"""Central repository layout and compatibility paths.

Importing this module is read-only. New logical roots coexist with established
runtime locations so the GUI remains compatible throughout migration.
"""

from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOFTWARE_ROOT = REPO_ROOT / "software"
INSTRUMENT_ROOT = REPO_ROOT / "instrument"
CAMPAIGNS_ROOT = REPO_ROOT / "campaigns"
EVIDENCE_ROOT = REPO_ROOT / "evidence"
REFERENCES_ROOT = REPO_ROOT / "references"
THEORY_ROOT = REPO_ROOT / "theory"


def _configured_root(variable: str, fallback: Path) -> Path:
    value = os.environ.get(variable)
    if not value:
        return fallback
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


RECIPE_ROOT = _configured_root("CONTROL_SYSTEM_RECIPE_ROOT", REPO_ROOT / "recipes")
RUN_ROOT = _configured_root("CONTROL_SYSTEM_RUN_ROOT", REPO_ROOT / "runs")
LOG_ROOT = _configured_root("CONTROL_SYSTEM_LOG_ROOT", REPO_ROOT / "logs")
PROMOTED_BUNDLE_ROOT = _configured_root(
    "CONTROL_SYSTEM_BUNDLE_ROOT", INSTRUMENT_ROOT / "promoted_bundles"
)

HARDWARE_CONFIGURATION_CANDIDATES = (
    INSTRUMENT_ROOT / "current" / "hardware_configuration.yaml",
    REPO_ROOT / "config" / "hardware_configuration.yaml",
    REPO_ROOT / "hardware_configuration.yaml",
)
WIRING_MAP_CANDIDATES = (
    INSTRUMENT_ROOT / "current" / "wiring_map.yaml",
    REPO_ROOT / "config" / "wiring_map.yaml",
    REPO_ROOT / "wiring_map.yaml",
)


def first_existing(candidates: tuple[Path, ...], *, label: str) -> Path:
    """Return the first existing compatibility path without modifying the tree."""

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"{label} was not found; searched: {searched}")


def hardware_configuration_path() -> Path:
    return first_existing(
        HARDWARE_CONFIGURATION_CANDIDATES, label="hardware configuration"
    )


def wiring_map_path() -> Path:
    return first_existing(WIRING_MAP_CANDIDATES, label="wiring map")


def recipe_path(relative: str | Path) -> Path:
    return (RECIPE_ROOT / relative).resolve()


def run_path(relative: str | Path) -> Path:
    return (RUN_ROOT / relative).resolve()


def log_path(relative: str | Path) -> Path:
    return (LOG_ROOT / relative).resolve()


def resolve_compat_path(value: str | Path) -> Path:
    """Resolve established repo-relative paths through the new logical roots."""

    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    parts = path.parts
    if parts and parts[0] == "recipes":
        return (RECIPE_ROOT.joinpath(*parts[1:])).resolve()
    if parts and parts[0] == "runs":
        return (RUN_ROOT.joinpath(*parts[1:])).resolve()
    if parts and parts[0] == "logs":
        return (LOG_ROOT.joinpath(*parts[1:])).resolve()
    return (REPO_ROOT / path).resolve()
