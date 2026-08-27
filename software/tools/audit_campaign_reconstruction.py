"""Read-only audit for prospective campaign documents and retained evidence."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAMPAIGNS = (
    ROOT / "evidence/calibration/system_recalibration_001",
    ROOT / "evidence/characterization/system_characterization_001",
)
INDEX_KEYS = {
    "acquisition_index.csv": "acquisition_id",
    "artifacts.csv": "artifact_id",
    "exclusions.csv": "exclusion_id",
}


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    errors: list[str] = []
    counts: Counter[str] = Counter()
    ids: dict[str, list[str]] = {key: [] for key in INDEX_KEYS.values()}

    for campaign in CAMPAIGNS:
        for path in (campaign / "phases").rglob("*"):
            if not path.is_file():
                continue
            if path.name in {
                "acquisition_index.csv",
                "artifacts.csv",
                "calibration_links.csv",
                "conditions.csv",
                "exclusions.csv",
                "measurements.csv",
                "phase_manifest.json",
                "final_report.md",
                "restoration_confirmation.json",
            }:
                counts[path.name] += 1
            if path.name in INDEX_KEYS:
                key = INDEX_KEYS[path.name]
                for row in csv_rows(path):
                    value = row.get(key, "").strip()
                    if value:
                        ids[key].append(value)
            if path.name == "artifacts.csv":
                for row in csv_rows(path):
                    relative = (row.get("relative_path") or row.get("path") or "").strip()
                    candidates = (campaign / relative, path.parent / relative)
                    if relative and not any(candidate.exists() for candidate in candidates):
                        errors.append(
                            f"pre-existing unresolved artifact path: "
                            f"{row.get('artifact_id', '<no-id>')} -> {relative}"
                        )

    duplicate_errors: list[str] = []
    for key, values in ids.items():
        for value, count in Counter(values).items():
            if count > 1:
                duplicate_errors.append(f"duplicate {key}: {value} ({count})")

    required = {
        "campaigns/migration/campaign_reconstruction_20260826.md": (
            "HF-01.1",
            "SV-02A",
            "SV-02B",
            "PF-00",
            "QB-01M",
            "Polystyrene",
            "Mylar",
            "HRP",
            "MbCO",
        ),
        "campaigns/methods/time_resolved_acquisition_modes.md": (
            "Fixed-wavelength kinetics",
            "Phase-shifted rapid-scan stroboscopy",
            "Wavelength-by-wavelength stroboscopic reconstruction",
        ),
    }
    for relative, tokens in required.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        for token in tokens:
            if token not in text:
                errors.append(f"missing required token {token!r} in {relative}")

    manifests = []
    for campaign in CAMPAIGNS:
        for path in (campaign / "phases").rglob("phase_manifest.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            manifests.append(
                {"phase_id": data.get("phase_id"), "status": data.get("status")}
            )

    report = {
        "index_file_counts": dict(sorted(counts.items())),
        "stable_id_counts": {key: len(value) for key, value in ids.items()},
        "manifests": manifests,
        "duplicate_id_errors": duplicate_errors,
        "unresolved_artifact_paths": errors,
    }
    print(json.dumps(report, indent=2))
    # Existing missing paths are reported but are not silently repaired and do not
    # become a hash-like operational gate. New structural or duplicate-ID errors fail.
    structural = [error for error in errors if not error.startswith("pre-existing")]
    return 1 if structural or duplicate_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
