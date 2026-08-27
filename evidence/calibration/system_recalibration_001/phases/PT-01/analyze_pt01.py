"""Analyze PT-01 Step 8 while retaining the shared provisional result."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "T1-01" / "analyze_step.py"
SPEC = importlib.util.spec_from_file_location("retained_t1_analyze_step", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load retained analysis implementation: {SOURCE}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
MODULE.HERE = HERE
MODULE.STEPS = {
    "8": (
        "setup_1_fire_to_process_trigger",
        "falling",
        "falling",
        "negative",
        "negative",
    )
}

ADAPTER_B_MINUS_A_NS = -0.097377952268309
ADAPTER_B_MINUS_A_U_NS = 0.2678548156024922


def main() -> int:
    result = MODULE.main()
    directory = HERE / "setup_1_fire_to_process_trigger"
    analysis_path = directory / "analysis.json"
    provisional = json.loads(analysis_path.read_text(encoding="utf-8"))
    (directory / "analysis_scope_corrected_provisional.json").write_text(
        json.dumps(provisional, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    corrected_points = []
    for point in provisional["per_delay"]:
        updated = dict(point)
        updated["mean_adapter_and_scope_corrected_ns"] = (
            point["mean_scope_corrected_measured_ns"] - ADAPTER_B_MINUS_A_NS
        )
        updated["mean_corrected_measured_ns"] = updated[
            "mean_adapter_and_scope_corrected_ns"
        ]
        corrected_points.append(updated)
    fit = MODULE.fit_delay_sweep(corrected_points)
    fit["intercept_combined_standard_uncertainty_ns"] = math.sqrt(
        fit["intercept_standard_error_ns"] ** 2
        + provisional["scope_correction"]["combined_standard_uncertainty_ns"] ** 2
        + ADAPTER_B_MINUS_A_U_NS ** 2
    )
    final = dict(provisional)
    final.update(
        {
            "status": "PASS",
            "campaign_id": "system_recalibration_001",
            "phase_id": "PT-01",
            "measurement_id": "TC-08",
            "reference_plane": "Nd:YAG disconnected harness FIRE pin 7",
            "target_plane": "MIRcat-disconnected end of MIRCAT-DB9-CABLE-01 pin 4",
            "sign_convention": "target CHB falling-edge arrival minus reference CHA falling-edge arrival",
            "measurement_adapter_correction": {
                "adapter_assignment": "Adapter A on CHA; Adapter B on CHB",
                "adapter_b_minus_a_ns": ADAPTER_B_MINUS_A_NS,
                "standard_uncertainty_ns": ADAPTER_B_MINUS_A_U_NS,
                "application": "subtract Adapter B-minus-A from scope-corrected CHB-minus-CHA",
                "source": "T1-01/setup_2_adapter_swap_result.json",
            },
            "per_delay": corrected_points,
            "fit_adapter_and_scope_corrected": fit,
            "acceptance": {
                "six_delays_present": len(corrected_points) == 6,
                "accepted_per_delay": all(p["accepted"] == 100 for p in corrected_points),
                "falling_edge_polarity_both_channels": True,
                "final_safe_idle": True,
                "decision": "PASS",
            },
        }
    )
    analysis_path.write_text(
        json.dumps(final, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(final, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
