"""Read-only preservation audit for the 2026-08-27 physical restructure."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN = ROOT / "campaigns/instrument_readiness_001"

# Counts exclude interpreter caches.  They are minimum preservation counts from the
# pre-move inventory, not closeout or data-loading gates.
PRE_MOVE = {
    "P0": (8, 53_961, None),
    "S0": (8, 154_227, None),
    "MS-01": (231, 289_313_702, None),
    "MS-02": (226, 286_810_552, None),
    "T2-01": (1_898, 940_518_053, None),
    "T1-01": (3_054, 1_975_934_526, None),
    "PT-01": (656, 1_372_651_012, "PASS"),
    "MC-01": (97, 4_072_108, "COMPLETE"),
    "TR-01": (17, 37_381, "PASS"),
    "OM-01": (46, 174_874, "PASS_COMPLETE_QUALIFIED_BOUNDED"),
    "HF-01": (533, 2_682_508_197, "PASS"),
    "WM-01": (35, 65_967, "IN_PROGRESS"),
    "CH-00": (22, 36_468, "PASS"),
}

REQUIRED_CLOSED_FILES = {
    "acquisition_index.csv",
    "artifacts.csv",
    "calibration_links.csv",
    "conditions.csv",
    "exclusions.csv",
    "measurements.csv",
    "phase_manifest.json",
    "final_report.md",
    "restoration_confirmation.json",
}


def stable_files(directory: Path) -> list[Path]:
    return [
        path
        for path in directory.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix.lower() != ".pyc"
    ]


def artifact_path_errors(campaign: Path) -> list[str]:
    errors: list[str] = []
    for index in (campaign / "phases").rglob("artifacts.csv"):
        with index.open(encoding="utf-8-sig", newline="") as handle:
            rows = csv.DictReader(handle)
            for row in rows:
                relative = (row.get("relative_path") or row.get("path") or "").strip()
                if not relative:
                    continue
                candidates = (campaign / relative, index.parent / relative)
                if not any(candidate.exists() for candidate in candidates):
                    errors.append(
                        f"{row.get('artifact_id', '<no-id>')} -> {relative}"
                    )
    return errors


def main() -> int:
    errors: list[str] = []
    phases: list[dict[str, object]] = []

    for phase_id, (minimum_count, pre_bytes, expected_status) in PRE_MOVE.items():
        phase = CAMPAIGN / "phases" / phase_id
        if not phase.is_dir():
            errors.append(f"missing phase directory: {phase.relative_to(ROOT)}")
            continue
        files = stable_files(phase)
        current_bytes = sum(path.stat().st_size for path in files)
        if len(files) < minimum_count:
            errors.append(
                f"{phase_id} has {len(files)} stable files; pre-move minimum is {minimum_count}"
            )

        status = None
        manifest = phase / "phase_manifest.json"
        if manifest.exists():
            status = json.loads(manifest.read_text(encoding="utf-8")).get("status")
        if expected_status is not None and status != expected_status:
            errors.append(
                f"{phase_id} status changed: expected {expected_status}, found {status}"
            )
        if expected_status not in (None, "IN_PROGRESS"):
            missing = sorted(name for name in REQUIRED_CLOSED_FILES if not (phase / name).exists())
            if missing:
                errors.append(f"{phase_id} missing closeout files: {', '.join(missing)}")

        phases.append(
            {
                "phase_id": phase_id,
                "stable_file_count": len(files),
                "pre_move_stable_file_count": minimum_count,
                "current_bytes": current_bytes,
                "pre_move_bytes": pre_bytes,
                "byte_delta_from_path_metadata_updates": current_bytes - pre_bytes,
                "status": status,
            }
        )

    for legacy in (
        "calibration",
        "characterization",
        "experiments",
        "vendor",
        "control_app",
        "tests",
        "tools",
        "recipes",
        "config",
        "runs",
        "logs",
        "hardware_configuration.yaml",
        "wiring_map.yaml",
    ):
        if (ROOT / legacy).exists():
            errors.append(f"legacy root still exists: {legacy}")

    for required in (
        "software/control_app",
        "instrument/hardware_configuration.yaml",
        "instrument/wiring_map.yaml",
        "campaigns/phase_registry.yaml",
        "campaigns/master_sequence.md",
        "campaigns/registries/evidence_locations.yaml",
        "references/reference_registry.yaml",
    ):
        if not (ROOT / required).exists():
            errors.append(f"missing canonical path: {required}")

    for retired in (ROOT / "evidence/calibration", ROOT / "evidence/characterization"):
        if retired.exists():
            errors.append(f"retired external phase-evidence root still exists: {retired}")

    artifact_errors = artifact_path_errors(CAMPAIGN)
    errors.extend(f"unresolved artifact path: {item}" for item in artifact_errors)

    print(
        json.dumps(
            {
                "phases": phases,
                "unresolved_artifact_paths": artifact_errors,
                "errors": errors,
                "note": (
                    "Byte deltas are informational path/metadata effects; no hash or "
                    "digest match is an operational gate."
                ),
            },
            indent=2,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
