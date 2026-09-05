"""KaleidaGraph-compatible sweep data viewer."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from control_app.workflows.sweep_export import export_kaleidagraph_scan
from control_app.paths import output_run_root

DIAGNOSTIC_COLUMNS = (
    "Provisional Wavenumber (cm^-1)", "Input 1 / Pico A (V)", "Input 2 / Pico B (V)",
    "Run classification", "Publication eligible", "Diagnostic metadata (JSON)",
)

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter, QPen
    from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover
    PYSIDE6_AVAILABLE = False
    QWidget = object


if PYSIDE6_AVAILABLE:

    class _SweepCanvas(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.rows: list[tuple[float, float, float]] = []
            self.labels = ('Sample', 'Reference')
            self.warning = ''
            self.setMinimumHeight(360)

        def paintEvent(self, _event) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.fillRect(self.rect(), self.palette().base())
            if not self.rows:
                painter.drawText(self.rect(), Qt.AlignCenter, "Load a scan CSV to plot Sample and Reference.")
                return
            x0, y0, w, h = 56, 22, self.width() - 78, self.height() - 64
            xs = [r[0] for r in self.rows if math.isfinite(r[0])]
            ys = [v for r in self.rows for v in r[1:] if math.isfinite(v)]
            if not xs or not ys:
                return
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)
            if xmax == xmin: xmax += 1.0
            if ymax == ymin: ymax += 1.0
            painter.setPen(QPen(self.palette().text().color()))
            painter.drawRect(x0, y0, w, h)
            # IR spectra conventionally display decreasing wavenumber from
            # left to right. This is display-only; exported rows retain their
            # acquisition order and physical wavelength values.
            painter.drawText(x0, self.height() - 12, f"{xmax:.3f} cm⁻¹")
            painter.drawText(x0 + w - 100, self.height() - 12, f"{xmin:.3f} cm⁻¹")
            for index, color in ((1, QColor(45, 120, 220)), (2, QColor(200, 80, 70))):
                painter.setPen(QPen(color, 1.5))
                previous = None
                for row in self.rows:
                    if not math.isfinite(row[0]) or not math.isfinite(row[index]):
                        previous = None
                        continue
                    px = x0 + (xmax - row[0]) / (xmax - xmin) * w
                    py = y0 + h - (row[index] - ymin) / (ymax - ymin) * h
                    if previous is not None:
                        painter.drawLine(previous[0], previous[1], px, py)
                    previous = (px, py)
            painter.setPen(QPen(QColor(45, 120, 220)))
            painter.drawText(x0 + 6, y0 + 16, self.labels[0])
            painter.setPen(QPen(QColor(200, 80, 70)))
            painter.drawText(x0 + 155, y0 + 16, self.labels[1])
            painter.drawText(x0 + 6, y0 + 35, self.warning)


    class ScanPlotterWidget(QWidget):
        """Load and display the three-column CSV written for KaleidaGraph."""

        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self.canvas = _SweepCanvas()
            self.diagnostic_metadata = {}
            self.status = QLabel("No sweep data loaded.")
            load = QPushButton("Load Scan CSV")
            load.clicked.connect(self._load)
            browse = QPushButton("Destination…")
            browse.clicked.connect(self._choose_destination)
            export = QPushButton("Export")
            export.clicked.connect(self._export)
            self.destination = QLineEdit(str(output_run_root()))
            self.filename = QLineEdit("scan_kaleidagraph.csv")
            layout = QVBoxLayout(self)
            controls = QHBoxLayout()
            controls.addWidget(load)
            controls.addWidget(QLabel("Folder:"))
            controls.addWidget(self.destination)
            controls.addWidget(browse)
            controls.addWidget(QLabel("Filename:"))
            controls.addWidget(self.filename)
            controls.addWidget(export)
            layout.addLayout(controls)
            layout.addWidget(self.status)
            layout.addWidget(self.canvas)

        def set_rows(self, rows) -> None:
            """Replace the in-memory scan; nothing is written until Export."""
            self.canvas.rows = [tuple(map(float, row)) for row in rows]
            self.diagnostic_metadata = {}
            self.canvas.labels = ('Sample', 'Reference')
            self.canvas.warning = ''
            self.status.setText(f"Scan complete: {len(self.canvas.rows)} points held in memory. Export when ready.")
            self.canvas.update()

        def set_diagnostic_metadata(self, metadata):
            if not metadata:
                return
            # Rows already live in the numeric CSV columns. Keeping another copy
            # in metadata would duplicate the full acquisition during export.
            self.diagnostic_metadata = {key: value for key, value in metadata.items()
                                        if key != 'scan_rows'}
            self.diagnostic_metadata.update(
                run_classification='EXPLORATORY_PROOF_OF_CONCEPT', publication_eligible=False,
                channel_labels=['Input 1 / Pico A', 'Input 2 / Pico B'],
            )
            self.diagnostic_metadata.setdefault('wavenumber_basis', 'PROVISIONAL linear axis')
            self.canvas.labels = ('Input 1 / Pico A', 'Input 2 / Pico B')
            self.canvas.warning = 'PROVISIONAL AXIS · NOT FOR PUBLICATION'
            self.status.setText(f"{metadata.get('detector_status', 'Diagnostic sweep')} · "
                                f"{metadata.get('markers_observed', '?')}/{metadata.get('markers_expected', '?')} markers. "
                                'PROVISIONAL AXIS · NOT FOR PUBLICATION.')
            self.canvas.update()

        def load_csv(self, path: str | Path) -> None:
            with Path(path).open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                columns = reader.fieldnames or []
                rows = list(reader)
            diagnostic = DIAGNOSTIC_COLUMNS[0] in columns
            data_columns = (DIAGNOSTIC_COLUMNS[:3] if diagnostic else
                            ("Wavenumber (cm^-1)", "Sample (V)", "Reference (V)"))
            loaded_rows = [tuple(float(row[column]) for column in data_columns) for row in rows]
            metadata = {}
            if diagnostic:
                metadata_text = next((row.get(DIAGNOSTIC_COLUMNS[-1]) for row in rows
                                      if row.get(DIAGNOSTIC_COLUMNS[-1])), '{}')
                metadata = json.loads(metadata_text)
                if not isinstance(metadata, dict):
                    raise ValueError('Diagnostic CSV metadata must be a JSON object')
                metadata.setdefault('run_classification', 'EXPLORATORY_PROOF_OF_CONCEPT')
            self.set_rows(loaded_rows)
            if diagnostic:
                self.set_diagnostic_metadata(metadata)
            detail = f" · {self.status.text()}" if diagnostic else ''
            self.status.setText(f"Loaded {len(self.canvas.rows)} points from {Path(path).name}{detail}")

        def _choose_destination(self) -> None:
            folder = QFileDialog.getExistingDirectory(self, "Export destination", self.destination.text())
            if folder:
                self.destination.setText(folder)

        def _export(self) -> None:
            if not self.canvas.rows:
                self.status.setText("No scan data are available to export.")
                return
            filename = self.filename.text().strip() or "scan_kaleidagraph.csv"
            if not filename.lower().endswith(".csv"):
                filename += ".csv"
            path = Path(self.destination.text()) / filename
            if self.diagnostic_metadata:
                self._export_diagnostic_csv(path)
            else:
                export_kaleidagraph_scan(self.canvas.rows, output_path=path)
            detail = ' · PROVISIONAL AXIS · NOT FOR PUBLICATION' if self.diagnostic_metadata else ''
            self.status.setText(f"Exported {len(self.canvas.rows)} points to {path}{detail}")

        def _export_diagnostic_csv(self, path: Path) -> None:
            metadata = json.dumps(self.diagnostic_metadata, allow_nan=False)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', newline='', encoding='utf-8') as handle:
                writer = csv.writer(handle)
                writer.writerow(DIAGNOSTIC_COLUMNS)
                for index, row in enumerate(self.canvas.rows):
                    writer.writerow([*(f'{value:.9g}' for value in row),
                                     self.diagnostic_metadata['run_classification'], False,
                                     metadata if index == 0 else ''])

        def _load(self) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Load scan data", "", "CSV files (*.csv)")
            if path:
                self.load_csv(path)
