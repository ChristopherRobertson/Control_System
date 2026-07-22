"""Processing helpers for Zurich Instruments LabOne Plotter text exports."""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence


DEFAULT_START_WAVENUMBER_CM = 2050.0
DEFAULT_END_WAVENUMBER_CM = 1650.0
DEFAULT_DETECTOR1_COLUMN = "GaAs Detector (V)"
DEFAULT_DETECTOR2_COLUMN = "MCT Detector (V)"

AlignmentMode = Literal["auto", "index", "time"]


class LabOnePlotterProcessingError(ValueError):
    """Raised when a LabOne Plotter export cannot be converted safely."""


@dataclass(frozen=True)
class NumericRow:
    """One numeric LabOne Plotter row."""

    time_s: float
    amplitude_v: float
    line_number: int


@dataclass(frozen=True)
class ProcessedPlotterSummary:
    """Summary of one processed LabOne Plotter export."""

    input_path: Path
    output_paths: tuple[Path, ...]
    data_rows: int
    trace1_rows: int
    trace2_rows: int
    first_wavenumber_cm: float
    last_wavenumber_cm: float
    alignment_mode_used: Literal["index", "time"]
    detector2_interpolated: bool


def process_labone_plotter_file(
    input_path: str | Path,
    *,
    output_paths: Sequence[str | Path] | None = None,
    write_txt_copy: bool = True,
    start_wavenumber_cm: float = DEFAULT_START_WAVENUMBER_CM,
    end_wavenumber_cm: float = DEFAULT_END_WAVENUMBER_CM,
    detector1_column: str = DEFAULT_DETECTOR1_COLUMN,
    detector2_column: str = DEFAULT_DETECTOR2_COLUMN,
    alignment: AlignmentMode = "auto",
) -> ProcessedPlotterSummary:
    """Convert a two-trace LabOne Plotter text export into a three-column table."""

    source = Path(input_path)
    if alignment not in ("auto", "index", "time"):
        raise LabOnePlotterProcessingError(f"Unknown alignment mode: {alignment!r}")

    trace1, trace2 = read_detector_traces(source)
    mode = _resolve_alignment_mode(alignment, trace1, trace2)
    wavenumbers, detector1_values, detector2_values, detector2_interpolated = _align_traces(
        trace1,
        trace2,
        start_wavenumber_cm=start_wavenumber_cm,
        end_wavenumber_cm=end_wavenumber_cm,
        alignment=mode,
    )
    text = _format_output_table(
        wavenumbers,
        detector1_values,
        detector2_values,
        detector1_column=detector1_column,
        detector2_column=detector2_column,
    )
    targets = tuple(
        Path(path)
        for path in (
            output_paths
            if output_paths is not None
            else default_output_paths(
                source,
                start_wavenumber_cm=start_wavenumber_cm,
                end_wavenumber_cm=end_wavenumber_cm,
                write_txt_copy=write_txt_copy,
            )
        )
    )
    if not targets:
        raise LabOnePlotterProcessingError("At least one output path is required")
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    return ProcessedPlotterSummary(
        input_path=source,
        output_paths=targets,
        data_rows=len(wavenumbers),
        trace1_rows=len(trace1),
        trace2_rows=len(trace2),
        first_wavenumber_cm=wavenumbers[0],
        last_wavenumber_cm=wavenumbers[-1],
        alignment_mode_used=mode,
        detector2_interpolated=detector2_interpolated,
    )


def default_output_paths(
    input_path: str | Path,
    *,
    start_wavenumber_cm: float = DEFAULT_START_WAVENUMBER_CM,
    end_wavenumber_cm: float = DEFAULT_END_WAVENUMBER_CM,
    write_txt_copy: bool = True,
) -> tuple[Path, ...]:
    """Return the default KaleidaGraph-friendly output paths for an input export."""

    source = Path(input_path)
    suffix = (
        f"_kaleidagraph_{_number_token(start_wavenumber_cm)}"
        f"_to_{_number_token(end_wavenumber_cm)}"
    )
    paths = [source.with_name(f"{source.stem}{suffix}.tsv")]
    if write_txt_copy:
        paths.append(source.with_name(f"{source.stem}{suffix}.txt"))
    return tuple(paths)


def read_detector_traces(input_path: str | Path) -> tuple[list[NumericRow], list[NumericRow]]:
    """Read the first two detector trace blocks from a LabOne Plotter export."""

    source = Path(input_path)
    try:
        text = source.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise LabOnePlotterProcessingError(f"Could not read {source}: {exc}") from exc

    rows: list[NumericRow] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("%"):
            continue
        parts = [part.strip() for part in stripped.split(";")]
        if len(parts) != 2:
            raise LabOnePlotterProcessingError(
                f"{source} line {line_number}: expected 'time; amplitude', got {line!r}"
            )
        try:
            rows.append(
                NumericRow(
                    time_s=float(parts[0]),
                    amplitude_v=float(parts[1]),
                    line_number=line_number,
                )
            )
        except ValueError as exc:
            raise LabOnePlotterProcessingError(
                f"{source} line {line_number}: could not parse numeric values"
            ) from exc

    if not rows:
        raise LabOnePlotterProcessingError(f"{source} contains no numeric Plotter rows")

    blocks = _split_trace_blocks(rows)
    if len(blocks) != 2:
        raise LabOnePlotterProcessingError(
            f"{source} must contain exactly two detector traces; found {len(blocks)}"
        )
    _validate_trace(blocks[0], "trace 1")
    _validate_trace(blocks[1], "trace 2")
    return blocks[0], blocks[1]


def _split_trace_blocks(rows: Sequence[NumericRow]) -> list[list[NumericRow]]:
    starts = [0]
    for index in range(1, len(rows)):
        # Each LabOne trace block sweeps from negative time toward zero; the next
        # block starts by jumping back near the beginning of the same time window.
        if rows[index].time_s < rows[index - 1].time_s - 1e-9:
            starts.append(index)
    starts.append(len(rows))
    return [list(rows[starts[i] : starts[i + 1]]) for i in range(len(starts) - 1)]


def _validate_trace(trace: Sequence[NumericRow], label: str) -> None:
    if len(trace) < 2:
        raise LabOnePlotterProcessingError(f"{label} must contain at least two rows")
    for previous, current in zip(trace, trace[1:]):
        if current.time_s < previous.time_s - 1e-9:
            raise LabOnePlotterProcessingError(
                f"{label} time axis is not monotonic near input line {current.line_number}"
            )


def _resolve_alignment_mode(
    requested: AlignmentMode,
    trace1: Sequence[NumericRow],
    trace2: Sequence[NumericRow],
) -> Literal["index", "time"]:
    if requested == "auto":
        return "index" if len(trace1) == len(trace2) else "time"
    if requested == "index" and len(trace1) != len(trace2):
        raise LabOnePlotterProcessingError(
            "Index alignment requires equal trace lengths "
            f"({len(trace1)} rows vs {len(trace2)} rows)"
        )
    return requested


def _align_traces(
    trace1: Sequence[NumericRow],
    trace2: Sequence[NumericRow],
    *,
    start_wavenumber_cm: float,
    end_wavenumber_cm: float,
    alignment: Literal["index", "time"],
) -> tuple[list[float], list[float], list[float], bool]:
    time1 = [row.time_s for row in trace1]
    detector1 = [row.amplitude_v for row in trace1]
    time2 = [row.time_s for row in trace2]
    detector2_source = [row.amplitude_v for row in trace2]

    if time1[-1] == time1[0]:
        raise LabOnePlotterProcessingError("Trace 1 time axis has zero span")
    wavenumbers = [
        start_wavenumber_cm
        + (time_s - time1[0]) * (end_wavenumber_cm - start_wavenumber_cm) / (time1[-1] - time1[0])
        for time_s in time1
    ]

    if alignment == "index":
        return wavenumbers, detector1, detector2_source, False

    detector2 = _interpolate_series(time2, detector2_source, time1)
    interpolated = len(time1) != len(time2) or any(
        abs(left - right) > 1e-12 for left, right in zip(time1, time2)
    )
    return wavenumbers, detector1, detector2, interpolated


def _interpolate_series(xs: Sequence[float], ys: Sequence[float], targets: Sequence[float]) -> list[float]:
    if len(xs) != len(ys):
        raise LabOnePlotterProcessingError("Interpolation source axes have mismatched lengths")
    output: list[float] = []
    for target in targets:
        if target < xs[0] - 1e-9 or target > xs[-1] + 1e-9:
            raise LabOnePlotterProcessingError(
                f"Trace 2 does not cover trace 1 timestamp {target:.12g} s"
            )
        if target <= xs[0]:
            output.append(ys[0])
            continue
        if target >= xs[-1]:
            output.append(ys[-1])
            continue
        index = bisect_left(xs, target)
        if index < len(xs) and abs(xs[index] - target) <= 1e-12:
            output.append(ys[index])
            continue
        x0 = xs[index - 1]
        x1 = xs[index]
        y0 = ys[index - 1]
        y1 = ys[index]
        if abs(x1 - x0) <= 1e-15:
            output.append(y0)
        else:
            fraction = (target - x0) / (x1 - x0)
            output.append(y0 + fraction * (y1 - y0))
    return output


def _format_output_table(
    wavenumbers: Sequence[float],
    detector1_values: Sequence[float],
    detector2_values: Sequence[float],
    *,
    detector1_column: str,
    detector2_column: str,
) -> str:
    if not (len(wavenumbers) == len(detector1_values) == len(detector2_values)):
        raise LabOnePlotterProcessingError("Output columns have mismatched lengths")
    lines = [f"Wavenumber (cm^-1)\t{detector1_column}\t{detector2_column}"]
    for wavenumber, detector1, detector2 in zip(wavenumbers, detector1_values, detector2_values):
        lines.append(f"{wavenumber:.6f}\t{detector1:.15g}\t{detector2:.15g}")
    return "\n".join(lines) + "\n"


def _number_token(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}".replace("-", "m").replace(".", "p")
