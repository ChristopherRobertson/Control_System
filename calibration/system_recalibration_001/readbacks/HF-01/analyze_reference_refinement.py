"""Refine the HF-01 carrier-reference trim from the corrected intermediate repeat."""

import json
from pathlib import Path

import numpy as np

from analyze_reference_detuning import CLOCKBASE_HZ, load_complex, segment_frequency


HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
ANALYSIS = HERE / "analysis"


def main() -> None:
    status_path = RAW / "hf01_anchor_intermediate_r1_001_status.json"
    raw_path = RAW / "hf01_anchor_intermediate_r1_001_hf2_raw.csv"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    timestamps, complex_values = load_complex(raw_path)
    estimates = []
    segments = status["segments"]
    for index, segment in enumerate(segments):
        if not segment["label"].startswith("step_rise_"):
            continue
        end_tick = segments[index + 1]["device_tick_before"]
        estimate = segment_frequency(
            timestamps,
            complex_values,
            int(segment["device_tick_after"]),
            int(end_tick),
        )
        estimates.append(float(estimate["measured_rotation_hz"]))
    residual = float(np.mean(estimates))
    prior = float(status["reference_frequency_hz"])
    output = {
        "analysis_id": "HF01-ANALYSIS-REFERENCE-REFINEMENT-001",
        "source_acquisition_id": status["acquisition_id"],
        "source_status_path": str(status_path),
        "source_raw_path": str(raw_path),
        "clockbase_hz": CLOCKBASE_HZ,
        "step_rotation_estimates_hz": estimates,
        "mean_residual_rotation_hz": residual,
        "standard_uncertainty_hz": float(
            np.std(estimates, ddof=1) / np.sqrt(len(estimates))
        ),
        "prior_reference_frequency_hz": prior,
        "refined_reference_frequency_hz": prior + residual,
        "scope": "reference synchronization only; no new filter setting or validation point",
    }
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    path = ANALYSIS / "hf01_reference_refinement.json"
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
