"""Complete MC-01 artifact and repository-state indexes without hash gates."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import mimetypes
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
CAMPAIGN_ROOT = HERE.parents[1]
REPO_ROOT = HERE.parents[3]
INDEX = HERE / "artifacts.csv"
HEADER = [
    "artifact_id", "campaign_id", "phase_id", "acquisition_id",
    "relative_path", "artifact_role", "media_type", "byte_size",
    "created_utc", "modified_utc", "producer", "source_artifact_ids",
    "immutable", "notes",
]


def iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).isoformat().replace("+00:00", "Z")


def role(path: Path) -> str:
    if "raw" in path.parts:
        return "native_raw"
    if path.suffix == ".py":
        return "analysis_source"
    if path.suffix == ".csv":
        return "derived_table"
    if path.suffix == ".json":
        return "readback"
    if "log" in path.name or path.name == "repository_state.txt":
        return "log"
    if path.name == "final_report.md":
        return "report"
    return "analysis_document"


def main() -> None:
    status = subprocess.run(
        ["git", "status", "--short", "--branch"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    (HERE / "repository_state.txt").write_text(
        "Captured UTC: " + datetime.now(UTC).isoformat() + "\n" + status,
        encoding="utf-8",
    )

    existing: dict[str, dict[str, str]] = {}
    if INDEX.exists():
        with INDEX.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("relative_path"):
                    existing[row["relative_path"]] = row

    used_ids = {row["artifact_id"] for row in existing.values()}
    next_id = 1
    rows: list[dict[str, str]] = []
    for path in sorted(p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        relative = path.relative_to(CAMPAIGN_ROOT).as_posix()
        row = existing.get(relative, {})
        artifact_id = row.get("artifact_id", "")
        while not artifact_id:
            candidate = f"MC01-ART-{next_id:04d}"
            next_id += 1
            if candidate not in used_ids:
                artifact_id = candidate
                used_ids.add(candidate)
        stat = path.stat()
        rows.append({
            "artifact_id": artifact_id,
            "campaign_id": "system_recalibration_001",
            "phase_id": "MC-01",
            "acquisition_id": row.get("acquisition_id", ""),
            "relative_path": relative,
            "artifact_role": row.get("artifact_role") or role(path),
            "media_type": row.get("media_type") or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "byte_size": str(stat.st_size),
            "created_utc": iso(stat.st_ctime),
            "modified_utc": iso(stat.st_mtime),
            "producer": row.get("producer") or "MC-01 controlled execution",
            "source_artifact_ids": row.get("source_artifact_ids", ""),
            "immutable": "true",
            "notes": row.get("notes") or "Indexed by stable ID; no hash or checksum operational gate",
        })

    with INDEX.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
