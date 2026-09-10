"""Interactive measured phase-scan views; no smoothing or extrapolation."""
from __future__ import annotations

from pathlib import Path
import numpy as np


def quantity_label(mode):
    return {"absorbance": "Absorbance", "delta_absorbance": "ΔAbsorbance",
            "sample_reference_ratio": "Sample/reference ratio"}.get(mode, mode)


def surface_arrays(result, mode="absorbance"):
    x, t = np.asarray(result["wavenumber_cm1"], float), np.asarray(result["time_s"], float)
    if x.ndim != 1 or t.ndim != 1 or not len(x) or not len(t) or not np.isfinite(x).all() or not np.isfinite(t).all():
        raise ValueError("Reconstruction axes must be nonempty, one-dimensional and finite")
    if mode not in result:
        raise ValueError("This run does not retain the requested reconstructed quantity")
    values = np.asarray(result[mode], float)
    if values.shape != (len(t), len(x)):
        raise ValueError("Reconstruction shape does not match its wavelength/time axes")
    return x, t, values


def time_axis_label(result):
    return "Time relative to calibrated optical arrival (ms)" if result.get("optical_arrival_calibrated", False) else "Time relative to electrical pump sync (ms)"


def draw_surface(axes, result, mode="absorbance"):
    from matplotlib import colormaps
    from matplotlib.colors import Normalize
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    wn, time, values = surface_arrays(result, mode)
    x, z = np.meshgrid(wn, time * 1000)
    finite = np.isfinite(values)
    if finite.any():
        normalizer = Normalize(vmin=np.min(values[finite]), vmax=np.max(values[finite]))
        rows = np.unique(np.linspace(0, len(time)-1, min(len(time), 96), dtype=int))
        cols = np.unique(np.linspace(0, len(wn)-1, min(len(wn), 128), dtype=int))
        # Omit a display cell if ANY interior point is unsupported, including
        # points skipped by rendering strides. Stored values remain untouched.
        holes = np.pad((~finite).astype(np.int64), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
        vertices, heights = [], []
        for top, bottom in zip(rows[:-1], rows[1:]):
            for left, right in zip(cols[:-1], cols[1:]):
                if holes[bottom+1, right+1]-holes[top, right+1]-holes[bottom+1, left]+holes[top, left]:
                    continue
                positions = ((top, left), (bottom, left), (bottom, right), (top, right))
                vertices.append([(x[r, c], values[r, c], z[r, c]) for r, c in positions])
                heights.append(np.mean([values[r, c] for r, c in positions]))
        if vertices:
            axes.add_collection3d(Poly3DCollection(vertices, facecolors=colormaps["viridis"](normalizer(heights)), edgecolors="none"))
        else:
            axes.scatter(x[finite], values[finite], z[finite], s=5)
        axes.auto_scale_xyz(x.ravel(), values[finite], z.ravel())
    else:
        axes.text2D(.2, .5, "No supported data", transform=axes.transAxes)
    axes.set_xlabel("Wavenumber (cm⁻¹)", labelpad=9)
    from matplotlib.ticker import MaxNLocator
    axes.xaxis.set_major_locator(MaxNLocator(nbins=3))
    axes.set_ylabel(quantity_label(mode), labelpad=10)
    axes.set_zlabel("Optical-arrival time (ms)" if result.get("optical_arrival_calibrated", False)
                    else "Electrical sync time (ms)", labelpad=3)
    axes.invert_xaxis()
    axes.view_init(elev=20, azim=25, vertical_axis="y")
    axes.set_title({"delta_absorbance": "Change from unpumped sample",
                    "sample_reference_ratio": "Simultaneous sample/reference spectrum"}.get(mode, "Reconstructed absorbance"))
    return axes


def make_surface_figure(result, mode="absorbance"):
    from matplotlib.figure import Figure
    figure = Figure(figsize=(9, 6), layout="constrained")
    draw_surface(figure.add_subplot(111, projection="3d"), result, mode)
    return figure


def export_quantitative_csv(path, result):
    if result.get("schema_version", "").startswith("dual-detector-phase-scan/"):
        from control_app.workflows.dual_detector_phase_scan_data import save_dual_reconstruction_csv
        return save_dual_reconstruction_csv(path, result)
    from control_app.workflows.regular_phase_scan_data import save_regular_reconstruction_csv
    save_regular_reconstruction_csv(path, result)


try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget)
except ImportError:  # pragma: no cover
    QWidget = None


if QWidget is not None:
    class _SliceCoordinateSpinBox(QDoubleSpinBox):
        stepped = Signal(int)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._coordinate_edited = False
            self.lineEdit().textEdited.connect(self._text_edited)

        def _text_edited(self, _text):
            self._coordinate_edited = True
            self.update()

        def stepBy(self, steps):
            self.interpretText()
            self.stepped.emit(steps)

        def stepEnabled(self):
            if getattr(self, "_coordinate_edited", False):
                return self.StepEnabledFlag.StepDownEnabled | self.StepEnabledFlag.StepUpEnabled
            return getattr(self, "_enabled_steps", self.StepEnabledFlag.StepNone)

        def set_step_limits(self, position, count):
            self._enabled_steps = self.StepEnabledFlag.StepNone
            if position > 0:
                self._enabled_steps |= self.StepEnabledFlag.StepDownEnabled
            if position < count-1:
                self._enabled_steps |= self.StepEnabledFlag.StepUpEnabled
            self.update()


    class PhaseScanReconstructionWidget(QWidget):
        run_loaded = Signal(object, str)

        def __init__(self, parent=None, *, detector_mode="single_ch1_buffer_blank"):
            super().__init__(parent)
            self.detector_mode = detector_mode
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
            from matplotlib.figure import Figure
            self.result, self.run_path = None, None
            # The toolbar's subplot editor uses subplots_adjust. A competing
            # constrained-layout engine both rejects those edits and collapses
            # axes during small/hidden Qt layouts.
            self.figure = Figure(figsize=(10, 8), layout="none")
            self.canvas = FigureCanvasQTAgg(self.figure)
            self.canvas.setMinimumHeight(350)
            self.toolbar = NavigationToolbar2QT(self.canvas, self)
            from PySide6.QtGui import QIcon, QPixmap, QPainter, QPolygon, QColor
            from PySide6.QtCore import QPoint
            pixmap = QPixmap(24, 24)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setBrush(QColor("black"))
            painter.drawPolygon(QPolygon([QPoint(5, 2), QPoint(5, 20), QPoint(10, 15), QPoint(14, 22), QPoint(17, 20), QPoint(13, 13), QPoint(21, 13)]))
            painter.end()
            self.select_action = self.toolbar.addAction(QIcon(pixmap), "Mouse selection")
            self.toolbar.insertAction(self.toolbar._actions["pan"], self.select_action)
            self.select_action.triggered.connect(self._mouse_selection)
            self.toolbar._actions["home"].triggered.disconnect()
            self.toolbar._actions["home"].triggered.connect(self._reset_view)
            self.toolbar._actions["save_figure"].triggered.disconnect()
            self.toolbar._actions["save_figure"].triggered.connect(self._choose_image)
            self.mode = QComboBox()
            if self.detector_mode == "dual_detector":
                self.mode.addItem("ΔAbsorbance", "delta_absorbance")
                self.mode.addItem("Sample/reference ratio", "sample_reference_ratio")
            else:
                self.mode.addItem("Absolute absorbance", "absorbance")
                self.mode.addItem("Change from unpumped sample", "delta_absorbance")
            self.load_button = QPushButton("Load phase-scan run…")
            self.export_button = QPushButton("Export quantitative data…")
            self.cursor = QLabel("Load or acquire a phase scan. Drag to rotate; use the toolbar to zoom.")
            self.status = QLabel("Unsupported regions remain missing. Phase spacing is not temporal resolution.")
            self.cursor.setWordWrap(True)
            self.status.setWordWrap(True)
            self.time_slider, self.spectral_slider = QSlider(Qt.Orientation.Horizontal), QSlider(Qt.Orientation.Horizontal)
            self.time_input, self.wavenumber_input = _SliceCoordinateSpinBox(), _SliceCoordinateSpinBox()
            for control, suffix, name in ((self.time_input, " ms", "slice_time"),
                                          (self.wavenumber_input, " cm⁻¹", "slice_wavenumber")):
                control.setObjectName(name)
                control.setDecimals(3 if control is self.time_input else 2)
                control.setKeyboardTracking(False)
                control.setSuffix(suffix)
                control.setToolTip("Hold an arrow to update the plot continuously, or enter a coordinate and press Enter to select the nearest reconstructed slice; no interpolation.")
            self.time_label, self.spectral_label = QLabel(), QLabel()
            layout, buttons = QVBoxLayout(self), QHBoxLayout()
            for control in (self.mode, self.load_button, self.export_button):
                buttons.addWidget(control)
            layout.addLayout(buttons)
            layout.addWidget(self.toolbar)
            layout.addWidget(self.canvas, 1)
            for label, slider, control in ((self.time_label, self.time_slider, self.time_input),
                                           (self.spectral_label, self.spectral_slider, self.wavenumber_input)):
                row = QHBoxLayout()
                row.addWidget(label)
                row.addWidget(control)
                row.addWidget(slider, 1)
                layout.addLayout(row)
            layout.addWidget(self.cursor)
            layout.addWidget(self.status)
            self.mode.currentIndexChanged.connect(self._redraw)
            self.time_slider.valueChanged.connect(self._update_slices)
            self.spectral_slider.valueChanged.connect(self._update_slices)
            self.time_input.stepped.connect(lambda steps: self._step_coordinate("time", steps))
            self.wavenumber_input.stepped.connect(lambda steps: self._step_coordinate("wavenumber", steps))
            # Keyboard tracking stays off so typed coordinates commit on Enter.
            self.time_input.valueChanged.connect(lambda: self._enter_coordinate("time"))
            self.wavenumber_input.valueChanged.connect(lambda: self._enter_coordinate("wavenumber"))
            self.time_input.editingFinished.connect(lambda: self._enter_coordinate("time", require_edit=True))
            self.wavenumber_input.editingFinished.connect(lambda: self._enter_coordinate("wavenumber", require_edit=True))
            self.load_button.clicked.connect(self._choose_load)
            self.export_button.clicked.connect(self._choose_export)
            self.canvas.mpl_connect("motion_notify_event", self._cursor_move)
            self.canvas.mpl_connect("button_press_event", self._select_slice)
            self._set_available(False)

        def _set_available(self, value):
            for control in (self.mode, self.export_button, self.time_slider, self.spectral_slider, self.time_input, self.wavenumber_input):
                control.setEnabled(value)
            for key in ("home", "save_figure"):
                self.toolbar._actions[key].setEnabled(value)

        def _mouse_selection(self):
            if self.toolbar.mode == "pan/zoom":
                self.toolbar.pan()
            elif self.toolbar.mode == "zoom rect":
                self.toolbar.zoom()

        def _reset_view(self):
            self._mouse_selection()
            self._redraw()

        def clear_result(self):
            self._mouse_selection()
            self.result = self.run_path = None
            self.figure.clear()
            self.toolbar.update()
            self.time_label.clear()
            self.spectral_label.clear()
            self.cursor.setText("Load or acquire a phase scan.")
            self._set_available(False)
            self.canvas.draw_idle()

        def set_result(self, result, run_path=None):
            dual = result.get("schema_version", "").startswith("dual-detector-phase-scan/")
            if self.detector_mode == "dual_detector":
                from control_app.workflows.dual_detector_phase_scan_data import validate_reconstruction
                validate_reconstruction(result)
            elif dual:
                raise ValueError("Open this dataset in the Dual-Detector Phase Scan tab")
            preferred = "absorbance" if "absorbance" in result else "delta_absorbance"
            x, time, _ = surface_arrays(result, preferred)
            self.result, self.run_path = result, Path(run_path) if run_path else None
            self.mode.blockSignals(True)
            self.mode.clear()
            if dual:
                if "absorbance" in result:
                    self.mode.addItem("Absolute absorbance", "absorbance")
                self.mode.addItem("ΔAbsorbance", "delta_absorbance")
                if "absorbance" not in result:
                    self.mode.addItem("Sample/reference ratio", "sample_reference_ratio")
            else:
                self.mode.addItem("Absolute absorbance", "absorbance")
                self.mode.addItem("Change from unpumped sample", "delta_absorbance")
                self.mode.model().item(1).setEnabled("delta_absorbance" in result)
            self.mode.setCurrentIndex(0)
            self.mode.blockSignals(False)
            for control, coordinates in ((self.time_input, time*1000), (self.wavenumber_input, x)):
                control.blockSignals(True)
                control.setRange(float(np.min(coordinates)), float(np.max(coordinates)))
                steps = np.diff(np.unique(coordinates))
                control.setSingleStep(float(np.min(steps)) if len(steps) else 1.)
                control.blockSignals(False)
            for slider, count in ((self.time_slider, len(time)), (self.spectral_slider, len(x))):
                slider.blockSignals(True)
                slider.setRange(0, count-1)
                slider.setValue(count//2)
                slider.blockSignals(False)
            self._set_available(True)
            notices = ["Unsupported regions remain missing. Phase spacing is not temporal resolution."]
            if not result.get("optical_arrival_calibrated", False):
                notices.append("Time uses electrical pump sync; optical arrival is not calibrated.")
            if result.get("provisional"):
                notices.append("Wavenumber calibration is provisional.")
            if not result.get("publication_eligible", False):
                notices.append("Exploratory data; publication eligibility is not established.")
            self.status.setText(" ".join(notices))
            self._redraw()

        def load_run(self, path):
            if self.detector_mode == "dual_detector":
                from control_app.workflows.dual_detector_phase_scan_data import load_dual_run as loader
            else:
                from control_app.workflows.regular_phase_scan_data import load_regular_run as loader
            path = Path(path)
            result = loader(path)
            self.set_result(result, path if path.is_dir() else path.parent.parent)
            self.run_loaded.emit(result, str(path))

        def _redraw(self, *_):
            if self.result is None:
                return
            self.figure.clear()
            grid = self.figure.add_gridspec(2, 2, width_ratios=[1.8, 1])
            bottom = max(.12, 60/max(350, self.canvas.height()))
            self.figure.subplots_adjust(left=.06, right=.97, bottom=bottom, top=.9, wspace=.30, hspace=.48)
            self.axes = draw_surface(self.figure.add_subplot(grid[:, 0], projection="3d"), self.result, self.mode.currentData())
            self.spectral_axes = self.figure.add_subplot(grid[0, 1])
            self.time_axes = self.figure.add_subplot(grid[1, 1])
            self._slice_lines = []
            self._update_slices()
            self.toolbar.update()

        def _step_coordinate(self, coordinate, steps):
            if self.result is None:
                return
            self._enter_coordinate(coordinate, require_edit=True)
            x, time, _ = surface_arrays(self.result, self.mode.currentData())
            values, slider = ((time, self.time_slider) if coordinate == "time"
                              else (x, self.spectral_slider))
            order = np.argsort(values, kind="stable")
            position = int(np.flatnonzero(order == slider.value())[0])
            # Step through measured slices, even with unequal gaps or values
            # closer together than the numeric display's decimal precision.
            position = max(0, min(len(order)-1, position+steps))
            slider.setValue(int(order[position]))

        def _enter_coordinate(self, coordinate, *, require_edit=False):
            if self.result is None:
                return
            x, time, _ = surface_arrays(self.result, self.mode.currentData())
            values, control, slider = ((time*1000, self.time_input, self.time_slider) if coordinate == "time"
                                       else (x, self.wavenumber_input, self.spectral_slider))
            # Several slices can share a rounded display value. Moving focus
            # without editing must preserve the selected slice.
            if require_edit and not control._coordinate_edited:
                return
            index = int(np.argmin(abs(values-control.value())))
            slider.blockSignals(True)
            slider.setValue(index)
            slider.blockSignals(False)
            # Update even if the nearest index did not change, so the numeric
            # control shows the actual coordinate, including missing-data slices.
            self._update_slices()

        def _update_slices(self, *_):
            if self.result is None or not hasattr(self, "spectral_axes"):
                return
            x, time, values = surface_arrays(self.result, self.mode.currentData())
            row, col = self.time_slider.value(), self.spectral_slider.value()
            label = quantity_label(self.mode.currentData())
            self.time_label.setText(f"Time: {time[row]*1000:.3f} ms")
            self.spectral_label.setText(f"Wavenumber: {x[col]:.2f} cm⁻¹")
            for control, coordinates, index in ((self.time_input, time*1000, row),
                                                (self.wavenumber_input, x, col)):
                order = np.argsort(coordinates, kind="stable")
                control.set_step_limits(int(np.flatnonzero(order == index)[0]), len(order))
                control.blockSignals(True)
                control.setValue(float(coordinates[index]))
                control._coordinate_edited = False
                control.blockSignals(False)
            for line in self._slice_lines:
                line.remove()
            self._slice_lines = self.axes.plot(x, values[row, :], np.full(len(x), time[row]*1000), color="#d35e25", lw=1.5)
            self._slice_lines += self.axes.plot(np.full(len(time), x[col]), values[:, col], time*1000, color="#a32b9b", lw=1.5)
            self.spectral_axes.clear()
            self.spectral_axes.plot(x, values[row], color="#d35e25")
            self.spectral_axes.axvline(x[col], color="#a32b9b", ls=":")
            self.spectral_axes.invert_xaxis()
            self.spectral_axes.set(xlabel="Wavenumber (cm⁻¹)", ylabel=label)
            self.time_axes.clear()
            self.time_axes.plot(time*1000, values[:, col], color="#a32b9b")
            self.time_axes.axvline(time[row]*1000, color="#d35e25", ls=":")
            self.time_axes.set(xlabel=time_axis_label(self.result), ylabel=label)
            self._show_cursor(row, col)
            self.canvas.draw_idle()

        def _show_cursor(self, row, col):
            x, time, values = surface_arrays(self.result, self.mode.currentData())
            value = f"{values[row, col]:.9g}" if np.isfinite(values[row, col]) else "missing / unsupported"
            self.cursor.setText(f"{x[col]:.9g} cm⁻¹ · {time[row]*1000:.9g} ms · {self.mode.currentText()}: {value}")

        def _nearest(self, event):
            if self.result is None or event.xdata is None:
                return None
            x, time, values = surface_arrays(self.result, self.mode.currentData())
            row, col = self.time_slider.value(), self.spectral_slider.value()
            if event.inaxes is self.spectral_axes:
                col = int(np.argmin(abs(x-event.xdata)))
            elif event.inaxes is self.time_axes:
                row = int(np.argmin(abs(time*1000-event.xdata)))
            elif event.inaxes is self.axes:
                from mpl_toolkits.mplot3d import proj3d
                rows = np.unique(np.linspace(0, len(time)-1, min(len(time), 96), dtype=int))
                cols = np.unique(np.linspace(0, len(x)-1, min(len(x), 128), dtype=int))
                rr, cc = np.meshgrid(rows, cols, indexing="ij")
                valid = np.isfinite(values[rr, cc])
                if not valid.any():
                    return None
                rr, cc = rr[valid], cc[valid]
                px, py, _ = proj3d.proj_transform(x[cc], values[rr, cc], time[rr]*1000, self.axes.get_proj())
                pixels = self.axes.transData.transform(np.column_stack([px, py]))
                index = int(np.argmin(np.sum((pixels-[event.x, event.y])**2, axis=1)))
                row, col = int(rr[index]), int(cc[index])
            else:
                return None
            return row, col

        def _cursor_move(self, event):
            nearest = self._nearest(event)
            if nearest is not None:
                self._show_cursor(*nearest)

        def _select_slice(self, event):
            if event.button != 1 or self.toolbar.mode:
                return
            nearest = self._nearest(event)
            if nearest is not None:
                self.time_slider.setValue(nearest[0])
                self.spectral_slider.setValue(nearest[1])

        def _choose_load(self):
            path = QFileDialog.getExistingDirectory(self, "Load saved phase-scan run")
            if path:
                try:
                    self.load_run(path)
                except Exception as exc:
                    QMessageBox.warning(self, "Load phase scan", str(exc))

        def _choose_export(self):
            path, _ = QFileDialog.getSaveFileName(self, "Export quantitative phase-scan data", "phase_scan.csv", "CSV (*.csv)")
            if path:
                try:
                    export_quantitative_csv(path, self.result)
                except Exception as exc:
                    QMessageBox.warning(self, "Export phase scan", str(exc))

        def _choose_image(self):
            path, _ = QFileDialog.getSaveFileName(self, "Save phase-scan plot image", "phase_scan.png", "PNG (*.png);;SVG (*.svg);;PDF (*.pdf)")
            if path:
                try:
                    if Path(path).exists():
                        raise FileExistsError("Choose a new filename to preserve existing images")
                    self.figure.savefig(path, dpi=180)
                except Exception as exc:
                    QMessageBox.warning(self, "Save phase-scan image", str(exc))
