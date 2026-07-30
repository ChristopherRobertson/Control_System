"""Analyze the two preserved manual MS-01 orientations."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import statistics
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_app.workflows.timing_calibration_procedure import (  # noqa: E402
    derive_measurement_system_corrections,
)


EVIDENCE_DIR = Path(__file__).resolve().parent


def load_orientation(name: str, measurement_id: str) -> tuple[list[dict], int]:
    rows: list[dict] = []
    rejected = 0
    path = EVIDENCE_DIR / name / "capture_attempts.csv"
    with path.open("r", newline="", encoding="utf-8") as handle:
        for item in csv.DictReader(handle):
            if item["status"] == "ACCEPTED":
                rows.append(
                    {
                        "measurement_id": measurement_id,
                        "measured_separation_ns": float(
                            item["measured_separation_ns"]
                        ),
                        "sample_interval_ns": float(item["sample_interval_ns"]),
                    }
                )
            else:
                rejected += 1
    return rows, rejected


def main() -> int:
    normal, normal_rejected = load_orientation("normal", "MS-00A")
    swapped, swapped_rejected = load_orientation("swapped", "MS-00B")
    if len(normal) != 100 or len(swapped) != 100:
        raise RuntimeError(
            f"expected 100 accepted per orientation, got {len(normal)} and {len(swapped)}"
        )
    corrections = derive_measurement_system_corrections(normal + swapped)
    n_values = [row["measured_separation_ns"] for row in normal]
    s_values = [row["measured_separation_ns"] for row in swapped]
    pooled_repeatability = math.sqrt(
        (
            (len(n_values) - 1) * statistics.stdev(n_values) ** 2
            + (len(s_values) - 1) * statistics.stdev(s_values) ** 2
        )
        / (len(n_values) + len(s_values) - 2)
    )
    result = {
        "status": "PASS",
        "accepted_counts": {"normal": 100, "swapped": 100},
        "rejected_counts": {
            "normal": normal_rejected,
            "swapped": swapped_rejected,
        },
        "repeatability": {
            "normal_sample_standard_deviation_ns": corrections[
                "normal_jitter_std_ns"
            ],
            "swapped_sample_standard_deviation_ns": corrections[
                "swapped_jitter_std_ns"
            ],
            "pooled_within_orientation_standard_deviation_ns": pooled_repeatability,
        },
        "measurement_system_corrections": corrections,
        "uncertainty_note": (
            "Repository swap analysis combines each orientation's standard "
            "error with a sample-resolution standard-uncertainty term. "
            "Cable reconnection repeatability was not separately evaluated."
        ),
        "user_input_required": [
            "PicoScope calibration-certificate uncertainty and association",
            "CLOCK-SPLITTER-01 manufacturer specifications",
            "separate cable-reconnection repeatability",
        ],
    }
    json_path = EVIDENCE_DIR / "ms01_results.json"
    json_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    c = corrections
    markdown = "\n".join(
        [
            "# MS-01 manual result",
            "",
            "Sign convention: B minus A; positive means PicoScope CHB arrived later. "
            "Splitter sign is branch 2 minus branch 1.",
            "",
            f"- Normal mean B-A: {c['normal_mean_b_minus_a_ns']:.9g} ns",
            f"- Swapped mean B-A: {c['swapped_mean_b_minus_a_ns']:.9g} ns",
            f"- PicoScope channel/path skew B-A: {c['scope_channel_and_fixed_lead_b_minus_a_ns']:.9g} "
            f"+/- {c['scope_correction_standard_uncertainty_ns']:.3g} ns (standard uncertainty)",
            f"- Splitter branch skew S2-S1: {c['splitter_branch_2_minus_1_ns']:.9g} "
            f"+/- {c['splitter_correction_standard_uncertainty_ns']:.3g} ns (standard uncertainty)",
            f"- Normal repeatability (sample SD): {c['normal_jitter_std_ns']:.3g} ns",
            f"- Swapped repeatability (sample SD): {c['swapped_jitter_std_ns']:.3g} ns",
            f"- Pooled within-orientation repeatability: {pooled_repeatability:.3g} ns",
            f"- Accepted/rejected: normal 100/{normal_rejected}; swapped 100/{swapped_rejected}",
            "",
            "Cable reconnection repeatability was not separately evaluated.",
        ]
    )
    (EVIDENCE_DIR / "ms01_results.md").write_text(
        markdown + "\n", encoding="utf-8"
    )
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
