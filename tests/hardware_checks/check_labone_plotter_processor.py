"""Checks for the LabOne Plotter export processor."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import _common  # noqa: F401 - adds the repository root to sys.path for script execution

from control_app.workflows.labone_plotter_processor import process_labone_plotter_file


def main() -> int:
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        _check_auto_uses_index_for_equal_lengths(temp_path)
        _check_time_alignment_handles_unequal_lengths(temp_path)
    print("LabOne Plotter processor checks passed")
    return 0


def _check_auto_uses_index_for_equal_lengths(temp_path: Path) -> None:
    raw = temp_path / "equal_lengths.txt"
    raw.write_text(
        "\n".join(
            [
                "% Module: Plotter",
                "-2; 1",
                "-1; 2",
                "0; 3",
                "-2; 10",
                "-0.5; 20",
                "0; 30",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary = process_labone_plotter_file(raw, write_txt_copy=False, alignment="auto")
    lines = summary.output_paths[0].read_text(encoding="utf-8").splitlines()
    assert summary.alignment_mode_used == "index"
    assert summary.data_rows == 3
    assert lines[0] == "Wavenumber (cm^-1)\tGaAs Detector (V)\tMCT Detector (V)"
    assert lines[1] == "2050.000000\t1\t10"
    assert lines[2] == "1850.000000\t2\t20"
    assert lines[3] == "1650.000000\t3\t30"


def _check_time_alignment_handles_unequal_lengths(temp_path: Path) -> None:
    raw = temp_path / "unequal_lengths.txt"
    raw.write_text(
        "\n".join(
            [
                "% Module: Plotter",
                "-2; 1",
                "-1; 2",
                "0; 3",
                "-2; 10",
                "-0.5; 20",
                "0; 30",
                "0.1; 31",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary = process_labone_plotter_file(raw, write_txt_copy=False, alignment="auto")
    lines = summary.output_paths[0].read_text(encoding="utf-8").splitlines()
    assert summary.alignment_mode_used == "time"
    assert summary.detector2_interpolated is True
    assert summary.data_rows == 3
    assert lines[1] == "2050.000000\t1\t10"
    assert lines[2].startswith("1850.000000\t2\t16.666666666666")
    assert lines[3] == "1650.000000\t3\t30"


if __name__ == "__main__":
    raise SystemExit(main())
