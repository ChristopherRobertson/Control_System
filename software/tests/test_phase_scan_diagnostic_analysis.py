"""Diagnostic digital markers follow acquisition metadata without rewriting raw data."""
import json

import numpy as np
import pytest
from matplotlib.figure import Figure

from control_app.workflows import phase_scan_diagnostic_analysis as analysis


@pytest.mark.parametrize("use_metadata", [False, True])
def test_diagnostic_selects_recorded_bit_and_names_actual_observational_signal(tmp_path, monkeypatch, use_metadata):
    # DIO1 and DIO21 have different widths so an incorrect bit selection fails.
    dio = np.array([0, 2, 2 | (1 << 21), 1 << 21, 1 << 21, 0], dtype=np.uint32)
    stream = {"timestamp": np.arange(6, dtype=np.uint64), "dio": dio,
              **{key: np.zeros(6) for key in ("x", "y", "trigger", "auxin0", "auxin1")}}
    record = {"kind": "INHIBITED_DIAGNOSTIC", "clockbase_hz": 1000,
              "native_chunks": [{"data": {"/dev/demods/2/sample": stream}}],
              "shot_counters_before": {"t660_1": 0, "t660_2": 0},
              "shot_counters_after": {"t660_1": 1, "t660_2": 1}}
    if use_metadata:
        record.update({"diagnostic_dio_bit": 21,
                       "diagnostic_dio_signal": "MIRcat DB9 pin 2 Sweep Active (observational input)",
                       "diagnostic_dio_expectation": "No sweep commanded; no transition expected"})
    index = json.dumps({"path": "scan_000001.npz"}) + "\n"
    (tmp_path / "scan_index.jsonl").write_text(index)
    marker_labels = []
    monkeypatch.setattr(analysis, "load_native", lambda path: record)
    monkeypatch.setattr(Figure, "savefig", lambda figure, *args, **kwargs: marker_labels.append(figure.axes[1].get_ylabel()))
    destination = analysis.inspect_diagnostic(tmp_path)
    summary = json.loads((destination / "summary.json").read_text())
    stream_summary = summary["records"][0]["streams"][0]
    assert stream_summary["observed_dio_bit"] == (21 if use_metadata else 1)
    assert stream_summary["observed_dio_high_widths_s"] == pytest.approx([.003 if use_metadata else .002])
    assert marker_labels == [summary["records"][0]["observed_dio_label"]]
    assert ("Sweep Active" if use_metadata else "DIO1 electrical marker") in marker_labels[0]
    if use_metadata:
        assert "observational input" in marker_labels[0]
        assert "no transition expected" in summary["records"][0]["dio_expectation"]
        assert "dio1_high_widths_s" not in stream_summary
    else:
        assert stream_summary["dio1_high_widths_s"] == pytest.approx([.002])
    assert (tmp_path / "scan_index.jsonl").read_text() == index
    np.testing.assert_array_equal(record["native_chunks"][0]["data"]["/dev/demods/2/sample"]["dio"], dio)
