"""Diagnostic CSV exports retain their limitations outside the acquisition UI."""
import csv
import json
import math
import os

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication

from control_app.ui.widgets.scan_plotter_widget import ScanPlotterWidget
from control_app.workflows.sweep_export import export_kaleidagraph_scan


@pytest.fixture
def plotters():
    app = QApplication.instance() or QApplication([])
    widgets = [ScanPlotterWidget(), ScanPlotterWidget()]
    yield widgets
    for widget in widgets:
        widget.close()
        widget.deleteLater()
    app.processEvents()


def test_diagnostic_csv_round_trip_preserves_channels_clipping_and_provisional_axis(tmp_path, plotters):
    original, loaded = plotters
    rows = [[2050., .1, .2], [2049., .3, float('nan')]]
    metadata = {
        'run_classification': 'EXPLORATORY_PROOF_OF_CONCEPT',
        'publication_eligible': False,
        'wavenumber_basis': 'PROVISIONAL linear axis; endpoint marker identity unresolved',
        'detector_status': 'CLIPPED OR CLIPPING STATUS UNKNOWN',
        'clipping_status_scope': 'before, during and after scan',
        'channels': {'1': {'clipped_checks': 2}, '2': {'clip_read_errors': 1}},
        'warnings': ['HF2LI Input 1 is clipped'],
        'markers_observed': 80, 'markers_expected': 81,
        'scan_rows': rows,
    }
    original.set_rows(rows)
    original.set_diagnostic_metadata(metadata)
    original.destination.setText(str(tmp_path))
    original._export()
    path = tmp_path / 'scan_kaleidagraph.csv'
    with path.open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        exported = list(reader)
    assert reader.fieldnames[:3] == [
        'Provisional Wavenumber (cm^-1)', 'Input 1 / Pico A (V)', 'Input 2 / Pico B (V)']
    assert all(row['Run classification'] == 'EXPLORATORY_PROOF_OF_CONCEPT' and
               row['Publication eligible'] == 'False' for row in exported)
    saved_metadata = json.loads(exported[0]['Diagnostic metadata (JSON)'])
    assert 'scan_rows' not in saved_metadata
    assert exported[1]['Diagnostic metadata (JSON)'] == ''
    assert saved_metadata['channel_labels'] == ['Input 1 / Pico A', 'Input 2 / Pico B']
    for key in ('wavenumber_basis', 'detector_status', 'channels', 'warnings',
                'clipping_status_scope', 'markers_observed', 'markers_expected'):
        assert saved_metadata[key] == metadata[key]

    loaded.load_csv(path)
    assert loaded.diagnostic_metadata == saved_metadata
    assert loaded.canvas.labels == ('Input 1 / Pico A', 'Input 2 / Pico B')
    assert 'PROVISIONAL' in loaded.canvas.warning and 'NOT FOR PUBLICATION' in loaded.canvas.warning
    assert 'CLIPPED' in loaded.status.text() and '80/81' in loaded.status.text()
    assert loaded.canvas.rows[0] == (2050., .1, .2)
    assert loaded.canvas.rows[1][:2] == (2049., .3)
    assert math.isnan(loaded.canvas.rows[1][2])
    # A loaded diagnostic keeps its context through another export.
    loaded.destination.setText(str(tmp_path))
    loaded.filename.setText('reexport.csv')
    loaded._export()
    assert (tmp_path / 'reexport.csv').read_bytes() == path.read_bytes()


@pytest.mark.parametrize('replace_via', ['load_csv', 'set_rows'])
def test_ordinary_data_clears_diagnostic_context_and_preserves_legacy_csv(tmp_path, plotters, replace_via):
    widget, _ = plotters
    widget.set_rows([[2050., .1, .2]])
    widget.set_diagnostic_metadata({'detector_status': 'CLIPPED'})
    rows = [(2000., .25, .5), (1999., .4, .6)]
    ordinary = export_kaleidagraph_scan(rows, output_path=tmp_path / 'ordinary.csv')
    if replace_via == 'load_csv':
        widget.load_csv(ordinary)
    else:
        widget.set_rows(rows)
    assert widget.canvas.rows == rows
    assert widget.canvas.labels == ('Sample', 'Reference')
    assert widget.canvas.warning == '' and widget.diagnostic_metadata == {}
    assert 'CLIPPED' not in widget.status.text()
    widget.destination.setText(str(tmp_path))
    widget._export()
    assert (tmp_path / 'scan_kaleidagraph.csv').read_bytes() == ordinary.read_bytes()
