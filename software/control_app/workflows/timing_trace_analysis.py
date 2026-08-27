"""Shared primitives for the comprehensive timing-calibration campaign."""

from __future__ import annotations

import bisect
import csv
from pathlib import Path
from typing import Any


DEFAULT_SEPARATIONS_NS = (0, 100, 1_000, 10_000, 100_000, 1_000_000)
DEFAULT_SHOT_COUNT = 100


class TimingCalibrationError(RuntimeError):
    """Raised when timing-calibration planning, acquisition, or analysis fails."""


def analyze_pico_trace(
    raw_csv_path: str | Path,
    *,
    sample_interval_ns: float,
    threshold_adc: int,
    programmed_separation_ns: float = 0.0,
    reference_edge: str = "rising",
    target_edge: str = "rising",
    target_selection_tolerance_ns: float | None = None,
) -> dict[str, Any]:
    """Measure interpolated edge separation from one PicoScope trace CSV."""

    samples_a: list[int] = []
    samples_b: list[int] = []
    with Path(raw_csv_path).open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            samples_a.append(int(row["ch_a_adc"]))
            samples_b.append(int(row["ch_b_adc"]))
    if not samples_a or not samples_b:
        raise TimingCalibrationError(f"No samples found in {raw_csv_path}")
    reference_indices = _edge_indices(samples_a, threshold_adc, reference_edge)
    target_indices = _edge_indices(samples_b, threshold_adc, target_edge)
    reference_index, target_index, target_error_ns = _select_edge_pair(
        reference_indices,
        target_indices,
        sample_interval_ns=sample_interval_ns,
        programmed_separation_ns=programmed_separation_ns,
        tolerance_ns=target_selection_tolerance_ns,
        raw_csv_path=raw_csv_path,
    )
    reference_time_ns = reference_index * sample_interval_ns
    target_time_ns = target_index * sample_interval_ns
    measured = target_time_ns - reference_time_ns
    return {
        "raw_csv_path": str(raw_csv_path),
        "threshold_adc": threshold_adc,
        "sample_interval_ns": sample_interval_ns,
        "programmed_separation_ns": programmed_separation_ns,
        "reference_edge_sample": reference_index,
        "target_edge_sample": target_index,
        "reference_edge_time_ns": reference_time_ns,
        "target_edge_time_ns": target_time_ns,
        "expected_target_edge_time_ns": reference_time_ns + programmed_separation_ns,
        "target_edge_selection_error_ns": target_error_ns,
        "reference_edge_count": len(reference_indices),
        "target_edge_count": len(target_indices),
        "measured_separation_ns": measured,
        "residual_ns": measured - programmed_separation_ns,
    }


def _edge_indices(samples: list[int], threshold_adc: int, edge: str) -> list[float]:
    normalized = edge.lower()
    if normalized not in {"rising", "falling"}:
        raise TimingCalibrationError(f"Unsupported edge definition {edge!r}")
    edges: list[float] = []
    for index in range(1, len(samples)):
        previous = samples[index - 1]
        current = samples[index]
        crossed = (
            previous < threshold_adc <= current
            if normalized == "rising"
            else previous > threshold_adc >= current
        )
        if crossed:
            span = current - previous
            edges.append(
                float(index)
                if span == 0
                else (index - 1) + ((threshold_adc - previous) / span)
            )
    if not edges:
        raise TimingCalibrationError(
            f"No {normalized} edge crossed threshold {threshold_adc} ADC counts"
        )
    return edges


def _select_edge_pair(
    reference_indices: list[float],
    target_indices: list[float],
    *,
    sample_interval_ns: float,
    programmed_separation_ns: float,
    tolerance_ns: float | None,
    raw_csv_path: str | Path,
) -> tuple[float, float, float]:
    if not reference_indices or not target_indices:
        raise TimingCalibrationError(
            f"Missing reference or target edge in {raw_csv_path}"
        )
    tolerance = float(
        tolerance_ns
        if tolerance_ns is not None
        else max(100.0, 10.0 * sample_interval_ns)
    )
    programmed_samples = programmed_separation_ns / sample_interval_ns
    best: tuple[float, float, float] | None = None
    for reference_index in reference_indices:
        expected_target_index = reference_index + programmed_samples
        insert_at = bisect.bisect_left(target_indices, expected_target_index)
        for position in (insert_at - 1, insert_at):
            if 0 <= position < len(target_indices):
                target_index = target_indices[position]
                error_ns = abs(
                    (target_index - expected_target_index) * sample_interval_ns
                )
                if best is None or error_ns < best[0]:
                    best = (error_ns, reference_index, target_index)
    if best is None:
        raise TimingCalibrationError(
            f"No comparable edge pair found in {raw_csv_path}"
        )
    error_ns, reference_index, target_index = best
    if error_ns > tolerance:
        raise TimingCalibrationError(
            "No target edge matched the programmed separation in "
            f"{raw_csv_path}; best error was {error_ns:.3f} ns for "
            f"{programmed_separation_ns:.3f} ns programmed separation. "
            "Increase the PicoScope capture span or inspect the timing output."
        )
    return reference_index, target_index, error_ns
