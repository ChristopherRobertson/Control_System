"""Read-only HF-01 retention and closeout audit."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
REQUIRED = [
    "phase_manifest.json", "acquisition_index.csv", "conditions.csv",
    "measurements.csv", "artifacts.csv", "exclusions.csv",
    "calibration_links.csv", "command_log.txt", "final_report.md",
    "restoration_confirmation.json", "retention_audit.md",
]
HEADERS = {
    "acquisition_index.csv": "campaign_id,phase_id,phase_run_id,acquisition_id,parent_acquisition_id,start_utc,end_utc,operator_id,configuration_id,calibration_bundle_id,sample_id,measurement_kind,condition_set_id,replicate_index,planned,accepted,rejection_code,raw_primary_artifact_id,notes".split(","),
    "conditions.csv": "campaign_id,phase_id,acquisition_id,condition_set_id,condition_name,value_text,value_number,unit,source,uncertainty_value,uncertainty_unit,uncertainty_type,notes".split(","),
    "measurements.csv": "campaign_id,phase_id,acquisition_id,result_set_id,quantity_name,value,unit,statistic,reference_plane,sign_convention,correction_state,standard_uncertainty,coverage_factor,expanded_uncertainty,quality_flag,analysis_artifact_id,notes".split(","),
    "artifacts.csv": "artifact_id,campaign_id,phase_id,acquisition_id,relative_path,artifact_role,media_type,byte_size,created_utc,modified_utc,producer,source_artifact_ids,immutable,notes".split(","),
    "exclusions.csv": "campaign_id,phase_id,acquisition_id,decision_utc,decision_maker,exclusion_code,criterion_version,reason,downstream_effect,superseded_by_acquisition_id,notes".split(","),
    "calibration_links.csv": "campaign_id,phase_id,phase_run_id,calibration_bundle_id,calibration_quantity_id,source_campaign_id,source_phase_id,source_artifact_id,value_used,unit,standard_uncertainty,validity_status,notes".split(","),
}


def table(name: str) -> tuple[list[str], list[dict[str, str]]]:
    with (HERE / name).open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def main() -> int:
    failures: list[str] = []
    for name in REQUIRED:
        if not (HERE / name).is_file():
            failures.append(f"missing required product: {name}")
    for directory in ("raw", "analysis", "figures", "tables"):
        if not (HERE / directory).is_dir():
            failures.append(f"missing required directory: {directory}")

    tables: dict[str, list[dict[str, str]]] = {}
    for name, expected in HEADERS.items():
        actual, rows = table(name)
        tables[name] = rows
        if actual != expected:
            failures.append(f"header mismatch: {name}")

    acquisitions = tables["acquisition_index.csv"]
    acquisition_ids = [row["acquisition_id"] for row in acquisitions]
    if len(acquisition_ids) != len(set(acquisition_ids)):
        failures.append("duplicate acquisition ID")
    raw_ids: set[str] = set()
    for path in (HERE / "raw").glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data.get("acquisition_id"):
            raw_ids.add(str(data["acquisition_id"]))
    missing_acquisitions = sorted(raw_ids - set(acquisition_ids))
    if missing_acquisitions:
        failures.append(f"raw acquisition IDs absent from index: {missing_acquisitions}")

    artifacts = tables["artifacts.csv"]
    artifact_ids = [row["artifact_id"] for row in artifacts]
    artifact_paths = [row["relative_path"] for row in artifacts]
    if len(artifact_ids) != len(set(artifact_ids)):
        failures.append("duplicate artifact ID")
    if len(artifact_paths) != len(set(artifact_paths)):
        failures.append("duplicate artifact path")
    artifact_by_path = {row["relative_path"]: row for row in artifacts}
    current_files = [
        path for path in HERE.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix.lower() != ".pyc"
    ]
    for path in current_files:
        relative = path.relative_to(CAMPAIGN).as_posix()
        row = artifact_by_path.get(relative)
        if row is None:
            failures.append(f"unindexed artifact: {relative}")
        elif int(row["byte_size"]) != path.stat().st_size:
            failures.append(f"artifact byte-size mismatch: {relative}")

    artifact_id_set = set(artifact_ids)
    for row in acquisitions:
        primary = row["raw_primary_artifact_id"]
        if not primary:
            failures.append(f"acquisition lacks raw primary artifact: {row['acquisition_id']}")
        elif primary not in artifact_id_set:
            failures.append(f"unknown raw primary artifact ID: {primary}")
        if row["accepted"] not in {"true", "false"}:
            failures.append(f"invalid accepted value: {row['acquisition_id']}")
        if row["accepted"] == "false" and not row["rejection_code"]:
            failures.append(f"rejected acquisition lacks code: {row['acquisition_id']}")

    for row in tables["measurements.csv"]:
        if row["value"]:
            try:
                float(row["value"])
            except ValueError:
                failures.append(f"nonnumeric measurement value: {row['acquisition_id']} {row['quantity_name']}")
        if row["correction_state"] not in {"raw", "corrected", "derived", "bounded"}:
            failures.append(f"invalid correction state: {row['acquisition_id']} {row['quantity_name']}")

    restoration = json.loads((HERE / "restoration_confirmation.json").read_text(encoding="utf-8"))
    manifest = json.loads((HERE / "phase_manifest.json").read_text(encoding="utf-8"))
    if not str(restoration.get("status", "")).startswith("PASS"):
        failures.append("restoration confirmation does not pass")
    if manifest.get("promotion_performed") is not False:
        failures.append("promotion state is not false")
    if manifest.get("status") != "PASS":
        failures.append("phase manifest is not PASS")

    summary = {
        "status": "PASS" if not failures else "FAIL",
        "failure_count": len(failures),
        "failures": failures,
        "acquisition_count": len(acquisitions),
        "accepted_acquisition_count": sum(row["accepted"] == "true" for row in acquisitions),
        "rejected_acquisition_count": sum(row["accepted"] == "false" for row in acquisitions),
        "raw_acquisition_id_count": len(raw_ids),
        "artifact_count": len(artifacts),
        "condition_count": len(tables["conditions.csv"]),
        "measurement_count": len(tables["measurements.csv"]),
        "exclusion_count": len(tables["exclusions.csv"]),
        "promotion_performed": manifest.get("promotion_performed"),
        "final_restoration_status": restoration.get("status"),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
