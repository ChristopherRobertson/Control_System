"""Build PT-01 contract indexes from retained evidence without hash gates."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CAMPAIGN_ROOT = HERE.parents[1]
SETUP = HERE / "setup_1_fire_to_process_trigger"
DELAYS = (0, 100, 1_000, 10_000, 100_000, 1_000_000)


def utc(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, UTC).isoformat()


excluded_outputs = {
    HERE / "artifacts.csv",
    HERE / "acquisition_index.csv",
    HERE / "conditions.csv",
    HERE / "measurements.csv",
}
paths = sorted(p for p in HERE.rglob("*") if p.is_file() and p not in excluded_outputs)
artifact_by_path: dict[Path, str] = {}
artifact_fields = [
    "artifact_id", "campaign_id", "phase_id", "acquisition_id",
    "relative_path", "artifact_role", "media_type", "byte_size", "created_utc",
    "modified_utc", "producer", "source_artifact_ids", "immutable", "notes",
]
with (HERE / "artifacts.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=artifact_fields)
    writer.writeheader()
    for index, path in enumerate(paths, 1):
        artifact_id = f"PT01-ART-{index:04d}"
        artifact_by_path[path.resolve()] = artifact_id
        stat = path.stat()
        raw = "raw" in path.parts
        acquisition_id = ""
        if raw:
            delay = path.parent.name.removesuffix("ns")
            attempt = int(path.stem.split("_")[-1])
            acquisition_id = f"PT01-TC08-{int(delay):07d}NS-A{attempt:03d}"
        writer.writerow({
            "artifact_id": artifact_id,
            "campaign_id": "system_recalibration_001",
            "phase_id": "PT-01",
            "acquisition_id": acquisition_id,
            "relative_path": path.relative_to(CAMPAIGN_ROOT).as_posix(),
            "artifact_role": "native_raw" if raw else "analysis_source" if path.suffix == ".py" else "derived_table" if path.suffix == ".csv" else "readback" if path.suffix == ".json" else "report" if path.name == "final_report.md" else "log" if path.suffix == ".txt" else "analysis_document",
            "media_type": "text/csv" if path.suffix == ".csv" else "application/json" if path.suffix == ".json" else "text/plain",
            "byte_size": stat.st_size,
            "created_utc": utc(stat.st_ctime),
            "modified_utc": utc(stat.st_mtime),
            "producer": "PicoScopeService" if raw else "PT-01 phase workflow",
            "source_artifact_ids": "",
            "immutable": "true",
            "notes": "No content hash is used as an operational gate",
        })

acq_fields = "campaign_id,phase_id,phase_run_id,acquisition_id,parent_acquisition_id,start_utc,end_utc,operator_id,configuration_id,calibration_bundle_id,sample_id,measurement_kind,condition_set_id,replicate_index,planned,accepted,rejection_code,raw_primary_artifact_id,notes".split(",")
condition_fields = "campaign_id,phase_id,acquisition_id,condition_set_id,condition_name,value_text,value_number,unit,source,uncertainty_value,uncertainty_unit,uncertainty_type,notes".split(",")
with (HERE / "acquisition_index.csv").open("w", newline="", encoding="utf-8") as ah, (HERE / "conditions.csv").open("w", newline="", encoding="utf-8") as ch:
    aw = csv.DictWriter(ah, fieldnames=acq_fields); aw.writeheader()
    cw = csv.DictWriter(ch, fieldnames=condition_fields); cw.writeheader()
    for delay in DELAYS:
        attempts = SETUP / f"capture_attempts_{delay}ns.csv"
        with attempts.open(newline="", encoding="utf-8") as source:
            for row in csv.DictReader(source):
                attempt = int(row["attempt"])
                acq = f"PT01-TC08-{delay:07d}NS-A{attempt:03d}"
                raw_path = Path(row["raw_path"]).resolve()
                condition = f"PT01-COND-{delay:07d}NS"
                aw.writerow({
                    "campaign_id": "system_recalibration_001", "phase_id": "PT-01",
                    "phase_run_id": "system_recalibration_001_PT-01_001",
                    "acquisition_id": acq, "parent_acquisition_id": "",
                    "start_utc": row["captured_utc"], "end_utc": row["captured_utc"],
                    "operator_id": "Christopher_Robertson",
                    "configuration_id": "PT01-STEP8-FIRE-TO-MIRCAT-PIN4-v1",
                    "calibration_bundle_id": "MS02+T1-01-COMPLETED-WORKING-EVIDENCE",
                    "sample_id": "", "measurement_kind": "electrical_falling_edge_timing",
                    "condition_set_id": condition, "replicate_index": row["accepted_index"] or attempt,
                    "planned": "true", "accepted": str(row["status"] == "ACCEPTED").lower(),
                    "rejection_code": row["reason"],
                    "raw_primary_artifact_id": artifact_by_path[raw_path],
                    "notes": "Both laser destination DB9 connectors physically disconnected",
                })
                cw.writerow({
                    "campaign_id": "system_recalibration_001", "phase_id": "PT-01",
                    "acquisition_id": acq, "condition_set_id": condition,
                    "condition_name": "programmed_process_trigger_delay",
                    "value_text": "", "value_number": delay, "unit": "ns",
                    "source": f"active_recipe_{delay}ns.json", "uncertainty_value": "",
                    "uncertainty_unit": "", "uncertainty_type": "", "notes": "setpoint",
                })

analysis = json.loads((SETUP / "analysis.json").read_text(encoding="utf-8"))
measurement_fields = "campaign_id,phase_id,acquisition_id,result_set_id,quantity_name,value,unit,statistic,reference_plane,sign_convention,correction_state,standard_uncertainty,coverage_factor,expanded_uncertainty,quality_flag,analysis_artifact_id,notes".split(",")
with (HERE / "measurements.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=measurement_fields); writer.writeheader()
    fit = analysis["fit_adapter_and_scope_corrected"]
    writer.writerow({
        "campaign_id": "system_recalibration_001", "phase_id": "PT-01", "acquisition_id": "",
        "result_set_id": "PT01-RESULT-FIT-v1", "quantity_name": "fire_to_process_trigger_intercept",
        "value": fit["fixed_offset_intercept_ns"], "unit": "ns", "statistic": "weighted_fit_intercept",
        "reference_plane": analysis["reference_plane"] + " to " + analysis["target_plane"],
        "sign_convention": analysis["sign_convention"], "correction_state": "corrected",
        "standard_uncertainty": fit["intercept_combined_standard_uncertainty_ns"],
        "coverage_factor": "1", "expanded_uncertainty": "", "quality_flag": "PASS",
        "analysis_artifact_id": artifact_by_path[(SETUP / "analysis.json").resolve()],
        "notes": "MS-02 scope and T1-01 adapter differential corrections applied",
    })
    for point in analysis["per_delay"]:
        writer.writerow({
            "campaign_id": "system_recalibration_001", "phase_id": "PT-01", "acquisition_id": "",
            "result_set_id": "PT01-RESULT-PER-DELAY-v1", "quantity_name": "mean_corrected_arrival_separation",
            "value": point["mean_corrected_measured_ns"], "unit": "ns", "statistic": "mean",
            "reference_plane": analysis["reference_plane"] + " to " + analysis["target_plane"],
            "sign_convention": analysis["sign_convention"], "correction_state": "corrected",
            "standard_uncertainty": point["standard_error_ns"], "coverage_factor": "1",
            "expanded_uncertainty": "", "quality_flag": "PASS",
            "analysis_artifact_id": artifact_by_path[(SETUP / "analysis.json").resolve()],
            "notes": f"programmed delay {point['programmed_delay_ns']} ns; jitter {point['jitter_std_ns']} ns",
        })
