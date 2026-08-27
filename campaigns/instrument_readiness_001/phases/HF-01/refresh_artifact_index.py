"""Refresh the HF-01 stable artifact index without content-hash gates."""

from __future__ import annotations

from datetime import UTC, datetime
import csv
import mimetypes
from pathlib import Path


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
INDEX = HERE / "artifacts.csv"
HEADERS = [
    "artifact_id",
    "campaign_id",
    "phase_id",
    "acquisition_id",
    "relative_path",
    "artifact_role",
    "media_type",
    "byte_size",
    "created_utc",
    "modified_utc",
    "producer",
    "source_artifact_ids",
    "immutable",
    "notes",
]


def timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z")


def role(path: Path) -> str:
    relative = path.relative_to(HERE).as_posix()
    if relative.startswith("raw/"):
        return "raw_primary"
    if relative.startswith("analysis/"):
        return "analysis_output"
    if relative.startswith("figures/"):
        return "figure"
    if relative.startswith("tables/"):
        return "derived_table"
    if path.suffix == ".py":
        return "analysis_source"
    if path.suffix == ".csv":
        return "index_or_ledger"
    if path.suffix == ".json":
        return "readback_or_manifest"
    return "phase_document"


def media_type(path: Path) -> str:
    if path.suffix == ".csv":
        return "text/csv"
    if path.suffix in {".md", ".py", ".txt"}:
        return "text/plain"
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def load_ids() -> dict[str, str]:
    if not INDEX.exists():
        return {}
    with INDEX.open("r", newline="", encoding="utf-8-sig") as handle:
        return {
            row["relative_path"]: row["artifact_id"]
            for row in csv.DictReader(handle)
            if row.get("relative_path") and row.get("artifact_id")
        }


def write_index() -> None:
    ids = load_ids()
    files = sorted(
        (
            path
            for path in HERE.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix.lower() != ".pyc"
        ),
        key=lambda value: value.relative_to(HERE).as_posix().lower(),
    )
    used = {
        int(value.rsplit("-", 1)[-1])
        for value in ids.values()
        if value.startswith("HF01-ART-") and value.rsplit("-", 1)[-1].isdigit()
    }
    next_id = max(used, default=0) + 1
    rows: list[dict[str, str]] = []
    for path in files:
        relative = path.relative_to(CAMPAIGN).as_posix()
        artifact_id = ids.get(relative)
        if artifact_id is None:
            artifact_id = f"HF01-ART-{next_id:04d}"
            next_id += 1
        stat = path.stat()
        mutable = path.name in {
            "artifacts.csv",
            "acquisition_index.csv",
            "action_ledger.csv",
            "conditions.csv",
            "measurements.csv",
            "exclusions.csv",
            "calibration_links.csv",
            "command_log.txt",
            "phase_manifest.json",
            "preflight_status.json",
        }
        rows.append(
            {
                "artifact_id": artifact_id,
                "campaign_id": "system_recalibration_001",
                "phase_id": "HF-01",
                "acquisition_id": "",
                "relative_path": relative,
                "artifact_role": role(path),
                "media_type": media_type(path),
                "byte_size": str(stat.st_size),
                "created_utc": timestamp(stat.st_ctime),
                "modified_utc": timestamp(stat.st_mtime),
                "producer": "HF-01 controlled execution",
                "source_artifact_ids": "",
                "immutable": "false" if mutable else "true",
                "notes": "Stable-ID provenance; no content hash or checksum is an operational gate",
            }
        )
    with INDEX.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    # Converge the self-row byte size without assigning a new identity.
    for _ in range(3):
        current_size = INDEX.stat().st_size
        changed = False
        for row in rows:
            if row["relative_path"].endswith("phases/HF-01/artifacts.csv"):
                if row["byte_size"] != str(current_size):
                    row["byte_size"] = str(current_size)
                    changed = True
        if not changed:
            break
        with INDEX.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    write_index()
