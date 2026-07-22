"""KaleidaGraph-compatible sweep data viewer."""

from __future__ import annotations

import csv
from pathlib import Path

from control_app.workflows.sweep_export import export_kaleidagraph_scan

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
            self.setMinimumHeight(360)

        def paintEvent(self, _event) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.fillRect(self.rect(), self.palette().base())
            if not self.rows:
                painter.drawText(self.rect(), Qt.AlignCenter, "Load a scan CSV to plot Sample and Reference.")
                return
            x0, y0, w, h = 56, 22, self.width() - 78, self.height() - 64
            xs = [r[0] for r in self.rows]
            ys = [v for r in self.rows for v in r[1:]]
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
                    px = x0 + (xmax - row[0]) / (xmax - xmin) * w
                    py = y0 + h - (row[index] - ymin) / (ymax - ymin) * h
                    if previous is not None:
                        painter.drawLine(previous[0], previous[1], px, py)
                    previous = (px, py)
            painter.setPen(QPen(QColor(45, 120, 220)))
            painter.drawText(x0 + 6, y0 + 16, "Sample")
            painter.setPen(QPen(QColor(200, 80, 70)))
            painter.drawText(x0 + 70, y0 + 16, "Reference")


    class ScanPlotterWidget(QWidget):
        """Load and display the three-column CSV written for KaleidaGraph."""

        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self.canvas = _SweepCanvas()
            self.status = QLabel("No sweep data loaded.")
            load = QPushButton("Load Scan CSV")
            load.clicked.connect(self._load)
            browse = QPushButton("Destination…")
            browse.clicked.connect(self._choose_destination)
            export = QPushButton("Export")
            export.clicked.connect(self._export)
            self.destination = QLineEdit(str(Path.cwd() / "runs"))
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
            self.status.setText(f"Scan complete: {len(self.canvas.rows)} points held in memory. Export when ready.")
            self.canvas.update()

        def load_csv(self, path: str | Path) -> None:
            with Path(path).open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.canvas.rows = [
                (float(row["Wavenumber (cm^-1)"]), float(row["Sample (V)"]), float(row["Reference (V)"]))
                for row in rows
            ]
            self.status.setText(f"Loaded {len(self.canvas.rows)} points from {Path(path).name}")
            self.canvas.update()

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
            path = export_kaleidagraph_scan(self.canvas.rows, output_path=Path(self.destination.text()) / filename)
            self.status.setText(f"Exported {len(self.canvas.rows)} points to {path}")

        def _load(self) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Load scan data", "", "CSV files (*.csv)")
            if path:
                self.load_csv(path)
