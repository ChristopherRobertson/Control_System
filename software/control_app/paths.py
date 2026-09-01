"""Canonical repository paths and compatibility resolution.

Importing this module is read-only.  The application uses the physical unified
layout while still accepting older repo-relative path strings found in historic
run manifests and operator scripts.
"""

from __future__ import annotations

import os
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
SOFTWARE_ROOT = PACKAGE_ROOT.parent
REPO_ROOT = SOFTWARE_ROOT.parent
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


RECIPE_ROOT = _configured_root(
    "CONTROL_SYSTEM_RECIPE_ROOT", INSTRUMENT_ROOT / "recipes"
)
RUN_ROOT = _configured_root(
    "CONTROL_SYSTEM_RUN_ROOT", EVIDENCE_ROOT / "experiments" / "runs"
)
LOG_ROOT = _configured_root(
    "CONTROL_SYSTEM_LOG_ROOT", EVIDENCE_ROOT / "experiments" / "logs"
)
PROMOTED_BUNDLE_ROOT = _configured_root(
    "CONTROL_SYSTEM_BUNDLE_ROOT", INSTRUMENT_ROOT / "promoted_bundles"
)

# GUI selection affects new output only, never historic input resolution.
_selected_save_location: Path | None = None


def get_save_location() -> Path:
    return _selected_save_location or RUN_ROOT


def set_save_location(value: str | Path) -> Path:
    global _selected_save_location
    if not str(value).strip():
        raise ValueError("Choose a non-empty save location")
    path = Path(value).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise ValueError("Save Location must be a folder")
    # Check actual write access, including network shares and Windows ACLs.
    from tempfile import TemporaryFile
    with TemporaryFile(dir=path):
        pass
    _selected_save_location = path
    return path


def output_run_root() -> Path:
    return get_save_location()


def output_log_root() -> Path:
    return _selected_save_location / "logs" if _selected_save_location else LOG_ROOT

HARDWARE_CONFIGURATION_CANDIDATES = (
    INSTRUMENT_ROOT / "hardware_configuration.yaml",
)
WIRING_MAP_CANDIDATES = (
    INSTRUMENT_ROOT / "wiring_map.yaml",
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
    return (output_run_root() / relative).resolve()


def log_path(relative: str | Path) -> Path:
    return (output_log_root() / relative).resolve()


def resolve_compat_path(value: str | Path) -> Path:
    """Resolve canonical and historic repo-relative paths.

    Historic spellings are accepted as inputs only.  They do not require legacy
    directories or duplicate data to exist in the repository.
    """

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
    if parts and parts[0] == "config":
        return (INSTRUMENT_ROOT / "schemas").joinpath(*parts[1:]).resolve()
    if len(parts) >= 3 and parts[:3] == (
        "calibration",
        "system_recalibration_001",
        "readbacks",
    ):
        return (
            EVIDENCE_ROOT
            / "calibration"
            / "system_recalibration_001"
            / "phases"
        ).joinpath(*parts[3:]).resolve()
    if len(parts) >= 3 and parts[:3] == (
        "characterization",
        "system_characterization_001",
        "readbacks",
    ):
        return (
            EVIDENCE_ROOT
            / "characterization"
            / "system_characterization_001"
            / "phases"
        ).joinpath(*parts[3:]).resolve()
    if len(parts) >= 2 and parts[:2] == ("vendor", "picosdk"):
        return (REFERENCES_ROOT / "sdk" / "picosdk").joinpath(*parts[2:]).resolve()
    return (REPO_ROOT / path).resolve()
