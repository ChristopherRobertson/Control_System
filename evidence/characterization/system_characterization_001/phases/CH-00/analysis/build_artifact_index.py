"""Build CH-00 artifact metadata without using hashes as a gate."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
CAMPAIGN_ROOT = HERE.parents[1]
OUTPUT = HERE / "artifacts.csv"


def role(path: Path) -> str:
    if path.name == "final_report.md":
        return "report"
    if path.suffix == ".py":
        return "analysis_source"
    if path.suffix == ".csv":
        return "derived_table"
    if path.suffix == ".json":
        return "readback" if "manifest" in path.name else "operator_observation"
    if path.suffix == ".txt":
        return "log"
    return "analysis_document"


paths = sorted(p for p in HERE.rglob("*") if p.is_file() and p != OUTPUT)
fields = [
    "artifact_id", "campaign_id", "phase_id", "acquisition_id",
    "relative_path", "artifact_role", "media_type", "byte_size",
    "created_utc", "modified_utc", "producer", "source_artifact_ids",
    "immutable", "notes",
]
with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    for index, path in enumerate(paths, 1):
        stat = path.stat()
        writer.writerow({
            "artifact_id": f"CH00-ART-{index:03d}",
            "campaign_id": "system_characterization_001",
            "phase_id": "CH-00",
            "acquisition_id": "",
            "relative_path": path.relative_to(CAMPAIGN_ROOT).as_posix(),
            "artifact_role": role(path),
            "media_type": "text/csv" if path.suffix == ".csv" else "application/json" if path.suffix == ".json" else "text/plain",
            "byte_size": stat.st_size,
            "created_utc": datetime.fromtimestamp(stat.st_ctime, UTC).isoformat(),
            "modified_utc": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
            "producer": "CH-00 analysis closeout",
            "source_artifact_ids": "",
            "immutable": "true",
            "notes": "No content hash is used as an operational gate",
        })
