"""Compare MS-01 and MS-02 splitter connection realizations."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.workflows.timing_calibration_procedure import (  # noqa: E402
    derive_measurement_system_corrections,
)


HERE = Path(__file__).resolve().parent
MS01 = HERE.parent / "MS-01"


def rows(directory: Path, normal_name: str, swapped_name: str) -> list[dict]:
    output: list[dict] = []
    for name, measurement_id in (
        (normal_name, "MS-00A"),
        (swapped_name, "MS-00B"),
    ):
        with (directory / name / "capture_attempts.csv").open(
            "r", newline="", encoding="utf-8"
        ) as handle:
            for row in csv.DictReader(handle):
                if row["status"] == "ACCEPTED":
                    output.append(
                        {
                            "measurement_id": measurement_id,
                            "measured_separation_ns": float(
                                row["measured_separation_ns"]
                            ),
                            "sample_interval_ns": float(row["sample_interval_ns"]),
                        }
                    )
    return output


def main() -> int:
    first = derive_measurement_system_corrections(
        rows(MS01, "normal", "swapped")
    )
    second = derive_measurement_system_corrections(
        rows(HERE, "reconnection_normal", "reconnection_swapped")
    )
    offline = json.loads(
        (HERE / "offline_analysis.json").read_text(encoding="utf-8")
    )
    scope_delta = (
        second["scope_channel_and_fixed_lead_b_minus_a_ns"]
        - first["scope_channel_and_fixed_lead_b_minus_a_ns"]
    )
    splitter_delta = (
        second["splitter_branch_2_minus_1_ns"]
        - first["splitter_branch_2_minus_1_ns"]
    )
    scope_estimate = (
        second["scope_channel_and_fixed_lead_b_minus_a_ns"]
        + first["scope_channel_and_fixed_lead_b_minus_a_ns"]
    ) / 2.0
    splitter_estimate = (
        second["splitter_branch_2_minus_1_ns"]
        + first["splitter_branch_2_minus_1_ns"]
    ) / 2.0
    scope_reconnection = abs(scope_delta) / 2.0
    splitter_reconnection = abs(splitter_delta) / 2.0
    scope_threshold = offline["threshold_sensitivity"]["scope_half_range_ns"]
    splitter_threshold = offline["threshold_sensitivity"][
        "splitter_half_range_ns"
    ]
    scope_interpolation = offline["interpolation_sensitivity"][
        "scope_absolute_difference_ns"
    ]
    splitter_interpolation = offline["interpolation_sensitivity"][
        "splitter_absolute_difference_ns"
    ]
    scope_timebase = abs(scope_estimate) * 2.0e-6
    splitter_timebase = abs(splitter_estimate) * 2.0e-6
    scope_combined = math.sqrt(
        second["scope_correction_standard_uncertainty_ns"] ** 2
        + scope_threshold**2
        + scope_interpolation**2
        + scope_reconnection**2
        + scope_timebase**2
    )
    splitter_combined = math.sqrt(
        second["splitter_correction_standard_uncertainty_ns"] ** 2
        + splitter_threshold**2
        + splitter_interpolation**2
        + splitter_reconnection**2
        + splitter_timebase**2
    )
    result = {
        "status": "PASS",
        "sign_convention": "B minus A; splitter S2 minus S1",
        "realization_1_ms01": first,
        "realization_2_ms02": second,
        "reconnection_difference_ns": {
            "scope_b_minus_a": scope_delta,
            "splitter_s2_minus_s1": splitter_delta,
        },
        "reconnection_half_range_standard_uncertainty_ns": {
            "scope_b_minus_a": scope_reconnection,
            "splitter_s2_minus_s1": splitter_reconnection,
        },
        "ms02_result": {
            "estimate_basis": "midpoint of two complete connection realizations",
            "scope_b_minus_a_ns": scope_estimate,
            "scope_combined_standard_uncertainty_ns": scope_combined,
            "splitter_s2_minus_s1_ns": splitter_estimate,
            "splitter_combined_standard_uncertainty_ns": splitter_combined,
        },
        "uncertainty_components_ns": {
            "scope": {
                "repeat_statistics_and_sample_resolution": second[
                    "scope_correction_standard_uncertainty_ns"
                ],
                "threshold_half_range": scope_threshold,
                "interpolation_method_difference": scope_interpolation,
                "reconnection_half_range": scope_reconnection,
                "timebase_2ppm": scope_timebase,
            },
            "splitter": {
                "repeat_statistics_and_sample_resolution": second[
                    "splitter_correction_standard_uncertainty_ns"
                ],
                "threshold_half_range": splitter_threshold,
                "interpolation_method_difference": splitter_interpolation,
                "reconnection_half_range": splitter_reconnection,
                "timebase_2ppm": splitter_timebase,
            },
        },
        "user_input_required": offline["user_input_required"],
        "limitation": (
            "Reconnection evidence contains two complete connection realizations; "
            "the half-range is used because a multi-cycle reconnection distribution "
            "was not measured."
        ),
    }
    (HERE / "ms02_results.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
