"""Estimate the common Pico carrier detuning from the intermediate HF2 record."""

import csv
import json
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
ANALYSIS = HERE / "analysis"
CLOCKBASE_HZ = 210_000_000.0
CARRIER_HZ = 2_000_000.0


def load_complex(path: Path) -> tuple[np.ndarray, np.ndarray]:
    timestamps: dict[str, list[int]] = {"x": [], "y": []}
    values: dict[str, list[float]] = {"x": [], "y": []}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            field = "x" if row["path"].endswith(".x") else "y"
            timestamps[field].append(int(row["timestamp"]))
            values[field].append(float(row["value"]))
    tx = np.asarray(timestamps["x"], dtype=np.int64)
    ty = np.asarray(timestamps["y"], dtype=np.int64)
    if not np.array_equal(tx, ty):
        raise RuntimeError("HF2 X/Y timestamps do not match")
    return tx, np.asarray(values["x"]) + 1j * np.asarray(values["y"])


def segment_frequency(
    timestamps: np.ndarray,
    complex_values: np.ndarray,
    start_tick: int,
    end_tick: int,
) -> dict[str, float | int]:
    indices = np.flatnonzero((timestamps >= start_tick) & (timestamps < end_tick))
    if len(indices) < 8:
        raise RuntimeError(f"Segment has only {len(indices)} samples")
    indices = indices[len(indices) // 2 :]
    seconds = (timestamps[indices] - timestamps[indices][0]) / CLOCKBASE_HZ
    phase = np.unwrap(np.angle(complex_values[indices]))
    slope, intercept = np.polyfit(seconds, phase, 1)
    residual = phase - (slope * seconds + intercept)
    return {
        "retained_samples": int(len(indices)),
        "measured_rotation_hz": float(slope / (2.0 * np.pi)),
        "phase_fit_rms_rad": float(np.sqrt(np.mean(residual * residual))),
    }


def main() -> None:
    status_path = RAW / "hf01_anchor_intermediate_001_status.json"
    raw_path = RAW / "hf01_anchor_intermediate_001_hf2_raw.csv"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    timestamps, complex_values = load_complex(raw_path)
    rows = []
    segments = status["segments"]
    for index, segment in enumerate(segments):
        if segment["kind"] not in {"carrier", "offset_carrier"}:
            continue
        end_tick = (
            segments[index + 1]["device_tick_before"]
            if index + 1 < len(segments)
            else int(timestamps[-1])
        )
        estimate = segment_frequency(
            timestamps,
            complex_values,
            int(segment["device_tick_after"]),
            int(end_tick),
        )
        commanded_offset = float(segment.get("offset_hz", 0.0))
        estimate.update(
            {
                "label": segment["label"],
                "commanded_offset_hz": commanded_offset,
                "carrier_detuning_hz": float(estimate["measured_rotation_hz"])
                - commanded_offset,
            }
        )
        rows.append(estimate)
    zero_offset = [
        float(row["carrier_detuning_hz"])
        for row in rows
        if row["label"].startswith("step_rise_")
    ]
    correction = float(np.mean(zero_offset))
    output = {
        "analysis_id": "HF01-ANALYSIS-REFERENCE-DETUNING-001",
        "source_acquisition_id": status["acquisition_id"],
        "source_status_path": str(status_path),
        "source_raw_path": str(raw_path),
        "method": "linear fit to unwrapped HF2 complex phase over the final half of each energized segment",
        "step_carrier_detuning_hz": zero_offset,
        "mean_carrier_detuning_hz": correction,
        "standard_uncertainty_hz": float(np.std(zero_offset, ddof=1) / np.sqrt(len(zero_offset))),
        "corrected_reference_frequency_hz": CARRIER_HZ + correction,
        "segment_estimates": rows,
        "disposition": {
            "HF01-ANCHOR-FAST-R1-001": "REJECT_REFERENCE_DETUNING",
            "HF01-ANCHOR-INTERMEDIATE-001": "REJECT_REFERENCE_DETUNING",
            "HF01-ANCHOR-SLOW-001": "REJECT_REFERENCE_DETUNING",
        },
        "repeat_scope": "repeat the same three frozen anchors with corrected reference; no additional model point",
    }
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    output_path = ANALYSIS / "hf01_reference_detuning_diagnostic.json"
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
