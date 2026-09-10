"""Two independent guided app tabs and native-coordinate recovery inspection."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Event
from time import monotonic

import numpy as np
from PySide6.QtCore import Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QToolBox,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
    QSplitter, QSizePolicy,
)

from control_app.measurement_host import TabHandle
from control_app.measurement_host.presentation import (
    GuidedMeasurementPanel, LinkedSliceControl, PlotPanel, StartSnapshot,
    choose_time_display,
)
from .settings import RepeatedRapidScanSettings, example_settings


def _label(key):
    labels = {"phase_offsets_s": "Requested phase offsets (s; JSON array)",
              "band_windows_cm1": "Population bands (cm⁻¹; JSON pairs)",
              "offband_windows_cm1": "Off-band windows (cm⁻¹; JSON pairs)",
              "measured_scan_period_s": "Measured scan period (s)",
              "scan_speed_cm1_s": "Scan speed (cm⁻¹/s)",
              "pre_scans": "Scans before pump", "post_scans": "Scans from pump crossing",
              "temperature_K": "Temperature (K)", "execution": "Execution"}
    return labels.get(key, key.replace("_cm1", " (cm⁻¹)").replace("_hz", " (Hz)")
                      .replace("_s", " (s)") if key.endswith(("_cm1", "_hz", "_s"))
                      else key.replace("_", " ").capitalize())


class SettingsWidget(QWidget):
    changed = Signal()

    def __init__(self, mode, settings=None):
        super().__init__()
        self.mode = mode
        self.inputs = {}
        self._values = (settings or example_settings(mode)).to_dict()
        layout = QVBoxLayout(self)
        note = QLabel("Choose the condition and finite movie schedule. Built-in values are EXAMPLE ONLY. "
                      "Connected operation requires applicable calibration and installed readbacks.")
        note.setWordWrap(True)
        layout.addWidget(note)
        toolbox = QToolBox()
        layout.addWidget(toolbox)
        groups = [
            ("Condition and sample", ["execution", "condition"]),
            ("Movie schedule and spectral window", ["phase_offsets_s", "pre_scans", "post_scans", "repeats",
                "directions", "controls", "scan_start_cm1", "scan_stop_cm1", "band_windows_cm1",
                "offband_windows_cm1", "measured_scan_period_s", "scan_speed_cm1_s", "recovery"]),
            ("HF2LI detector settings", [key for key in self._values if key.startswith(("sample_", "reference_"))]),
        ]
        used = {key for _, keys in groups for key in keys} | {"mode", "schema_version", "experiment_id"}
        groups.append(("Timing, provenance and capacity", [key for key in self._values if key not in used]))
        for title, keys in groups:
            page = QWidget()
            form = QFormLayout(page)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            for key in keys:
                value = self._values[key]
                if isinstance(value, dict) and key in ("condition", "recovery"):
                    for child, item in value.items():
                        self._add_field(form, (key, child), item)
                else:
                    self._add_field(form, (key,), value)
            toolbox.addItem(page, title)
        layout.addStretch()

    def _add_field(self, form, path, value):
        key = path[-1]
        if key == "execution":
            control = QComboBox()
            control.addItem("Simulation — synthetic records", "simulation")
            control.addItem("Installed instruments", "hardware")
            control.setCurrentIndex(0 if value == "simulation" else 1)
            control.currentIndexChanged.connect(self.changed.emit)
        elif isinstance(value, bool):
            control = QCheckBox()
            control.setChecked(value)
            control.toggled.connect(self.changed.emit)
        elif isinstance(value, int) and abs(value) < 2**31:
            control = QSpinBox()
            control.setRange(0, 2**31-1)
            control.setValue(value)
            control.valueChanged.connect(self.changed.emit)
        elif isinstance(value, float):
            control = QDoubleSpinBox()
            control.setDecimals(12)
            control.setRange(-1e15, 1e15)
            control.setValue(value)
            control.setKeyboardTracking(False)
            control.valueChanged.connect(self.changed.emit)
        else:
            control = QLineEdit(value if isinstance(value, str) else json.dumps(value))
            control.editingFinished.connect(self.changed.emit)
        control.setObjectName("rrs_" + "_".join(path))
        self.inputs[path] = (control, type(value))
        form.addRow(_label(key), control)

    def read(self):
        values = deepcopy(self._values)
        for path, (control, kind) in self.inputs.items():
            if isinstance(control, QComboBox):
                value = control.currentData()
            elif isinstance(control, QCheckBox):
                value = control.isChecked()
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                value = control.value()
            else:
                value = control.text() if kind is str else json.loads(control.text())
            target = values
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
        values["mode"] = self.mode
        return RepeatedRapidScanSettings.from_dict(values).to_dict()

    def apply(self, value):
        settings = RepeatedRapidScanSettings.from_dict(value)
        if settings.mode != self.mode:
            raise ValueError("Plan detector mode does not match this tab")
        self._values = settings.to_dict()
        for path, (control, kind) in self.inputs.items():
            item = self._values
            for key in path:
                item = item[key]
            control.blockSignals(True)
            if isinstance(control, QComboBox):
                control.setCurrentIndex(control.findData(item))
            elif isinstance(control, QCheckBox):
                control.setChecked(item)
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                control.setValue(item)
            else:
                control.setText(item if kind is str else json.dumps(item))
            control.blockSignals(False)


class MoviePlots(QWidget):
    """Point maps do not interpolate a scan into an instantaneous spectrum."""
    def __init__(self):
        super().__init__()
        self.result = None
        self.points = []
        self._updating = False
        self.movie = QComboBox()
        self.quantity = QComboBox()
        self.quantity.addItem("ΔAbsorbance", "delta_absorbance")
        self.quantity.addItem("Reference-normalized signal / single detector", "normalized_signal")
        self.quantity.addItem("Absolute absorbance (measured B required)", "absolute_absorbance")
        self.view = QComboBox()
        self.view.addItems(["Wavelength kinetics", "Band-area kinetics", "Phase/direction consistency", "Fit residuals"])
        self.scan = LinkedSliceControl(label="Measured scan midpoint", unit="s", decimals=9)
        self.wavenumber = LinkedSliceControl(label="Measured wavenumber", unit="cm⁻¹", decimals=6)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.plot = PlotPanel(self)
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        for control in (self.movie, self.quantity, self.view):
            row.addWidget(control)
        layout.addLayout(row)
        layout.addWidget(self.scan)
        layout.addWidget(self.wavenumber)
        layout.addWidget(self.description)
        layout.addWidget(self.plot, 1)
        self.movie.currentIndexChanged.connect(self._select_movie)
        self.scan.index_changed.connect(self._select_scan)
        self.wavenumber.index_changed.connect(self._redraw)
        self.quantity.currentIndexChanged.connect(self._redraw)
        self.view.currentIndexChanged.connect(self._redraw)

    def clear(self):
        self.result = None
        self.points = []
        self.movie.clear()
        self.scan.set_coordinates(())
        self.wavenumber.set_coordinates(())
        self.plot.clear_result()
        self.description.clear()

    def set_result(self, result):
        self.result = result
        self.quantity.blockSignals(True)
        self.quantity.setItemText(1, "Sample/reference ratio Q" if result.get("mode") == "dual" else "Sample detector signal")
        absolute_available = any(np.isfinite(p.absolute_absorbance).any()
            for movie in result.get("processed", ()) for p in movie.points)
        self.quantity.model().item(2).setEnabled(absolute_available)
        kind = result.get("kind")
        self.quantity.setCurrentIndex((2 if absolute_available else 1) if kind in ("blank", "preliminary") else 0)
        self.quantity.blockSignals(False)
        self.movie.blockSignals(True)
        self.movie.clear()
        for item in result.get("processed", ()):
            self.movie.addItem(f"{item.movie_id} · {item.status}", item)
        self.movie.blockSignals(False)
        self._select_movie()

    def _select_movie(self, *_):
        movie = self.movie.currentData()
        self.points = list(movie.points) if movie else []
        self._updating = True
        coordinates = [float(np.nanmean(p.time_s)) for p in self.points]
        coordinates = [value if np.isfinite(value) else float(i) for i, value in enumerate(coordinates)]
        self.scan.set_coordinates(coordinates)
        if movie and movie.time_zero_basis != "unpumped_control" and coordinates:
            crossing = next((i for i,p in enumerate(self.points)
                             if np.nanmin(p.time_s) <= 0 <= np.nanmax(p.time_s)), None)
            self.scan.set_index(crossing if crossing is not None else int(np.argmin(np.abs(coordinates))))
        self._updating = False
        self._select_scan()

    def _select_scan(self, *_):
        if self._updating:
            return
        self._updating = True
        p = self.points[self.scan.index] if self.points else None
        values = np.asarray(p.wavenumbers_cm1) if p else np.array([])
        previous = (self.wavenumber.coordinates[self.wavenumber.index]
                    if self.wavenumber.coordinates else None)
        if previous is None and self.result:
            windows = self.result.get("plan", {}).get("settings", {}).get("band_windows_cm1", ())
            if windows:
                previous = (windows[0][0]+windows[0][1])/2
        self.wavenumber.set_coordinates(np.unique(values[np.isfinite(values)]))
        if previous is not None and self.wavenumber.coordinates:
            self.wavenumber.set_index(int(np.argmin(np.abs(np.asarray(self.wavenumber.coordinates)-previous))))
        self._updating = False
        self._redraw()

    def _redraw(self, *_):
        if self._updating:
            return
        self.plot.set_result(self.result)

    def draw(self, figure, result):
        movie = self.movie.currentData()
        if movie is None or not self.points:
            figure.add_subplot(111).text(.1, .5, "No reconstructed support. Native/partial records remain available.")
            return
        field = self.quantity.currentData()
        label = self.quantity.currentText()
        selected = self.points[self.scan.index]
        wavenumber = self.wavenumber.coordinates[self.wavenumber.index] if self.wavenumber.coordinates else np.nan
        times = np.concatenate([np.asarray(p.time_s) for p in self.points])
        finite_times = times[np.isfinite(times)]
        display = choose_time_display(finite_times.tolist()) if len(finite_times) else choose_time_display([0.])
        scale = display.seconds_per_unit
        axes = figure.subplots(2, 2)
        map_ax, spectrum_ax, native_ax, kinetic_ax = axes.ravel()
        color = None
        supported = [np.asarray(getattr(p, field))[np.asarray(p.valid) & np.isfinite(getattr(p, field))]
                     for p in self.points]
        supported = np.concatenate(supported)
        limits = {"vmin": float(np.min(supported)), "vmax": float(np.max(supported))} if len(supported) else {}
        basis_label = {"electrical_sync": "Electrical sync", "optical_arrival": "Observed optical arrival",
                       "calibrated_optical_time_zero": "Calibrated optical time zero", "unpumped_control": "Unpumped native"}.get(movie.time_zero_basis, movie.time_zero_basis)
        for p in self.points:
            values = np.asarray(getattr(p, field))
            valid = np.asarray(p.valid) & np.isfinite(values) & np.isfinite(p.time_s) & np.isfinite(p.wavenumbers_cm1)
            if valid.any():
                color = map_ax.scatter(np.asarray(p.wavenumbers_cm1)[valid], np.asarray(p.time_s)[valid]/scale,
                                       c=values[valid], s=4, cmap="viridis", rasterized=True, **limits)
        if color is not None:
            figure.colorbar(color, ax=map_ax, label=label)
        map_ax.set(xlabel="Wavenumber (cm⁻¹)", ylabel=f"{basis_label} time ({display.unit})",
                   title="Native time-resolved support; gaps retained")
        map_ax.invert_xaxis()
        map_ax.axhline(0, color="gray", linewidth=.6)
        map_ax.axvline(wavenumber, color="gray", linewidth=.6)
        values = np.asarray(getattr(selected, field), float).copy()
        values[~np.asarray(selected.valid)] = np.nan
        wn = np.asarray(selected.wavenumbers_cm1, float)
        # Insert a gap before each retained sample interval known to be missing.
        breaks = set()
        for lower, upper in selected.gaps_s:
            indices = np.flatnonzero((np.asarray(selected.time_s)[:-1] <= lower) & (np.asarray(selected.time_s)[1:] >= upper))
            breaks.update((indices+1).tolist())
        if breaks:
            indices = sorted(breaks)
            wn, values = np.insert(wn, indices, np.nan), np.insert(values, indices, np.nan)
        spectrum_ax.plot(wn, values, ".-", markersize=2)
        spectrum_ax.set(xlabel="Wavenumber (cm⁻¹)", ylabel=label,
                        title=f"Scan {selected.scan_index} · {selected.direction}; non-instantaneous")
        spectrum_ax.invert_xaxis()
        native = next((m for m in result.get("native_movies", ()) if m.movie_id == movie.movie_id), None)
        if native:
            scan = next((s for s in native.scans if s.scan_index == selected.scan_index), None)
            if scan:
                for role, stream in (("Sample", scan.sample), ("Reference", scan.reference)):
                    if stream is not None:
                        raw = np.asarray(stream.timestamps_s)
                        t = (raw-raw[0]).astype(float)*stream.timestamp_unit_s if len(raw) else raw
                        native_ax.plot(t, stream.values, ".-", label=role, markersize=2)
                native_ax.legend(fontsize="small")
        native_ax.set(xlabel="Native time from scan start (s)", ylabel="HF2LI native signal",
                      title="Native detectors, including excluded values")
        if self.view.currentIndex() == 3:
            fits = result.get("fit_analysis", {}).get("fits_by_direction", {})
            if fits:
                for direction, fit in fits.items():
                    all_times = np.concatenate([p.time_s for p in movie.points if p.direction == direction])
                    fit_times = all_times[np.asarray(fit.valid_native_indices)]
                    kinetic_ax.scatter(fit_times/scale, fit.residuals, s=3, label=direction)
                kinetic_ax.axhline(0., color="gray", linewidth=.5)
                kinetic_ax.set_ylabel("Native fit residual ΔA")
            else:
                kinetic_ax.text(.05, .5, "Load an identified fit model and fit this movie.", transform=kinetic_ax.transAxes)
        elif self.view.currentIndex() == 1:
            groups = sorted({(b.window_cm1, b.direction, b.kind) for b in movie.band_kinetics})
            for window, direction, kind in groups:
                entries = [b for b in movie.band_kinetics if (b.window_cm1, b.direction, b.kind) == (window, direction, kind)]
                t = np.asarray([(b.earliest_time_s+b.latest_time_s)/2 for b in entries])/scale
                widths = np.asarray([(b.latest_time_s-b.earliest_time_s)/2 for b in entries])/scale
                y = [b.area if b.valid else np.nan for b in entries]
                kinetic_ax.errorbar(t, y, xerr=widths, fmt=".", label=f"{kind} {window} {direction}")
            kinetic_ax.set_ylabel("Integrated ΔA (cm⁻¹); bars = scan time span")
        elif self.view.currentIndex() == 2:
            for item in result.get("processed", ()):
                x, y = [], []
                for p in item.points:
                    valid = np.isfinite(p.wavenumbers_cm1)
                    if valid.any():
                        index = np.flatnonzero(valid)[np.argmin(abs(np.asarray(p.wavenumbers_cm1)[valid]-wavenumber))]
                        x.append(p.time_s[index]/scale)
                        y.append(getattr(p, field)[index] if p.valid[index] else np.nan)
                kinetic_ax.plot(x, y, ".", label=item.movie_id, markersize=2)
            kinetic_ax.set_ylabel(label)
        else:
            for direction in sorted({p.direction for p in self.points}):
                x, y = [], []
                for p in self.points:
                    if p.direction != direction:
                        continue
                    wn = np.asarray(p.wavenumbers_cm1)
                    valid = np.isfinite(wn)
                    if valid.any():
                        index = np.flatnonzero(valid)[np.argmin(abs(wn[valid]-wavenumber))]
                        x.append(p.time_s[index]/scale)
                        y.append(getattr(p, field)[index] if p.valid[index] else np.nan)
                kinetic_ax.plot(x, y, ".-", label=direction, markersize=3)
            kinetic_ax.set_ylabel(label)
        kinetic_ax.set_xlabel(f"{basis_label} time ({display.unit})")
        kinetic_ax.set_title(f"Measured support near {wavenumber:.4f} cm⁻¹")
        if kinetic_ax.lines:
            kinetic_ax.legend(fontsize=6)
        for ax in axes.ravel():
            ax.tick_params(labelsize=7)
        figure.tight_layout(pad=1.4)
        valid_count = sum((np.asarray(p.valid) & np.isfinite(getattr(p, field))).sum() for p in self.points)
        total_count = sum(len(p.time_s) for p in self.points)
        self.description.setText(f"{movie.movie_id}: {valid_count}/{total_count} supported {label} points. "
            f"Time basis: {movie.time_zero_basis}. Directions remain separate. " + " ".join(movie.warnings))


class RepeatedRapidScanPanel(GuidedMeasurementPanel):
    manual_action_requested = Signal(str, object)
    manual_action_closed = Signal(object)

    def __init__(self, context):
        from .adapter import RepeatedRapidScanAdapter
        settings = SettingsWidget(context.mode)
        adapter = RepeatedRapidScanAdapter(context, settings)
        self._review_candidate = None
        self._initial_state_values = {}
        super().__init__(settings, adapter, context)
        # Long commissioning details stay scrollable and cannot force the whole
        # application beyond the screen height.
        splitter = self.findChild(QSplitter)
        summary_scroll = QScrollArea()
        summary_scroll.setWidgetResizable(True)
        summary_body = splitter.replaceWidget(1, summary_scroll)
        summary_scroll.setWidget(summary_body)
        summary_body.show()
        self._summary_scroll = summary_scroll
        self._summary_body = summary_body
        splitter.setMaximumHeight(230)
        splitter.setMinimumHeight(160)
        splitter.setSizes([550, 750])
        self.setObjectName(context.instance_id)
        self.preliminary_button.setText("2 · Acquire sample preliminary (pump OFF)")
        if context.mode == "dual":
            self.preliminary_button.setText("1 · Acquire simultaneous sample/reference (pump OFF)")
        self.start_button.setText("Start recovery movies")
        self.abort_button.setText("Abort acquisition")
        self.settings_widget.changed.connect(self.refresh_plan)
        self.records_row = QHBoxLayout()
        self.blank_button = QPushButton("1 · Acquire blank")
        self.blank_button.setToolTip("Acquire the complete sequential blank with pump outputs disabled")
        self.load_blank_button = QPushButton("Load blank…")
        self.load_preliminary_button = QPushButton("Load preliminary…")
        self.sample_selection_button = QPushButton("Sample selection…")
        self.bundle_button = QPushButton("Promoted bundle…")
        self.capability_button = QPushButton("Check instruments")
        self.preserve_button = QPushButton("Save retained records")
        self.preserve_button.setVisible(False)
        if context.mode == "single":
            for button in (self.blank_button, self.load_blank_button):
                self.records_row.addWidget(button)
        for button in (self.load_preliminary_button, self.sample_selection_button, self.bundle_button, self.capability_button):
            self.records_row.addWidget(button)
        self.records_row.addWidget(self.preserve_button)
        self.layout().insertLayout(1, self.records_row)
        self.physical_ready = QCheckBox("The indicated blank/sample and matched reference are loaded; manual preparation is complete")
        self.physical_ready.setToolTip("No automatic cell exchange, shutter, positioner or temperature controller is installed by this experiment.")
        self.layout().insertWidget(2, self.physical_ready)
        self.elapsed = QLabel()
        self.layout().insertWidget(3, self.elapsed)
        self.schedule = QTableWidget(0, 8)
        self.schedule.setHorizontalHeaderLabels(["Movie", "Phase (s)", "Direction", "Control", "Pumps", "Scans", "Physical frames", "Duration (s)"])
        self.schedule.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.schedule.setMaximumHeight(112)
        self.result_layout.addWidget(self.schedule)
        self.plots = MoviePlots()
        fit_row = QHBoxLayout()
        self.fit_model_button = QPushButton("Load measured fit model…")
        self.fit_button = QPushButton("Fit selected movie")
        self.fit_summary = QLabel("Apparent recovery fitting requires an identified native kernel and justified spectral model.")
        self.fit_summary.setWordWrap(True)
        self.fit_summary.setMaximumHeight(45)
        self.fit_summary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        fit_row.addWidget(self.fit_model_button)
        fit_row.addWidget(self.fit_button)
        fit_row.addWidget(self.fit_summary, 1)
        self.result_layout.addLayout(fit_row)
        self.result_layout.addWidget(self.plots, 1)
        self.result_ready.connect(self._show_result)
        self.run_loaded.connect(lambda result, _path: self._show_result(result))
        self.new_run_requested.connect(self.plots.clear)
        self.outcome_ready.connect(self._outcome)
        self.blank_button.clicked.connect(lambda: self._user_action(lambda: self.begin_auxiliary("blank")))
        self.capability_button.clicked.connect(lambda: self._user_action(lambda: self.begin_auxiliary("capabilities")))
        self.load_blank_button.clicked.connect(lambda: self._load_record("blank"))
        self.load_preliminary_button.clicked.connect(lambda: self._load_record("preliminary"))
        self.sample_selection_button.clicked.connect(self._load_selection)
        self.bundle_button.clicked.connect(self._load_bundle)
        self.fit_model_button.clicked.connect(self._load_fit_model)
        self.fit_button.clicked.connect(lambda: self._user_action(self._fit_movie))
        self.preserve_button.clicked.connect(lambda: self._user_action(self._preserve_retained))
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._time_update)
        self.busy_changed.connect(self._busy_update)
        self._started_at = None
        self._manual_dialogs = {}
        self.manual_action_requested.connect(self._show_manual_action)
        self.manual_action_closed.connect(self._close_manual_action)
        adapter.manual_action_handler = self._wait_manual_action
        self._populate_schedule()

    def refresh_plan(self, *_):
        if getattr(self, "_busy", False):
            return
        candidate = getattr(self, "_review_candidate", None) or getattr(self, "preliminary", None)
        super().refresh_plan()
        if candidate is not None and self.plan is not None:
            errors = self.adapter.validate_review(candidate, self.plan)
            if errors:
                self.validation.setText("Review invalidated: " + "\n".join(errors))
            else:
                self.preliminary = candidate
                self.validation.clear()
                self.review_summary.setText(self.adapter.summarize_preliminary(candidate))
        self.review.setChecked(False)
        self._review_candidate = candidate
        self._update_controls()
        if hasattr(self, "schedule"):
            self._populate_schedule()

    def _populate_schedule(self):
        movies = self.plan.movies if self.plan else ()
        self.schedule.setRowCount(len(movies))
        for i, movie in enumerate(movies):
            values = (movie.movie_id, f"{movie.requested_phase_s:.9g}", movie.direction, movie.control,
                      movie.pump_count, movie.scans_per_movie, len(movie.frames), f"{movie.duration_s:.6g}")
            for j, value in enumerate(values):
                self.schedule.setItem(i, j, QTableWidgetItem(str(value)))

    def begin(self, kind):
        self._require_preserved()
        if self.adapter.hardware_required(kind, self.adapter.read_settings()) and not self.physical_ready.isChecked():
            raise ValueError("Complete the indicated physical preparation and confirm it before connected acquisition")
        if kind == "preliminary" and self.context.mode == "single":
            errors = self.adapter.validate_blank(self.plan)
            if errors:
                raise ValueError("Acquire or load a complete compatible blank first: " + "; ".join(errors))
        if kind == "measurement" and self.preliminary is not None and self.review.isChecked():
            self.preliminary["review_approval"] = {"accepted": True, "instance_id": self.context.instance_id,
                "accepted_utc": datetime.now(timezone.utc).isoformat(),
                "basis": "Operator explicitly checked preliminary review and pressed Start"}
        super().begin(kind)

    def begin_auxiliary(self, kind):
        self._require_preserved()
        if self._busy or self.plan is None:
            raise ValueError("A valid plan and idle tab are required")
        hardware = kind == "capabilities" or self.adapter.hardware_required(kind, self.adapter.read_settings())
        if hardware and kind != "capabilities" and not self.physical_ready.isChecked():
            raise ValueError("Load the blank and confirm physical preparation before acquisition")
        selected = self.adapter.selected_records()
        operation = self.context.begin_operation(plan=self._host_plan,
            calibration_records=selected.calibration_records, sample_records=selected.sample_records,
            hardware=hardware, purpose=kind, cancel=self.request_abort)
        snapshot = StartSnapshot(operation, kind, deepcopy(self.plan), None)
        self.snapshot = snapshot
        def execute(worker):
            if hardware:
                with self.context.hardware_scope(operation):
                    return self.adapter.run_auxiliary(snapshot, worker, kind)
            return self.adapter.run_auxiliary(snapshot, worker, kind)
        try:
            self._launch(execute, kind)
        except Exception:
            if hardware and not (self.worker and self.worker.isRunning()):
                self.context.ownership.release(operation.ownership, safe_verified=True, preservation_verified=True,
                                               detail="Worker dispatch failed before device access")
            raise

    def _finished(self, worker, kind, path):
        if self.worker is not worker:
            return
        outcome = worker.outcome
        presentation_error = None
        try:
            self._apply_outcome(kind, outcome)
        except Exception as exc:
            presentation_error = f"Presentation failed after {kind}: {type(exc).__name__}: {exc}"
        finally:
            # Even a failed plot or malformed loaded model must finish the host
            # worker lifecycle after its verified backend cleanup/preservation.
            super()._finished(worker, kind, path)
        if outcome and outcome.state == "completed" and kind in ("load_selection", "load_bundle", "capabilities"):
            self.refresh_plan()
        if presentation_error:
            self.status.setText(presentation_error)

    def _apply_outcome(self, kind, outcome):
        if outcome and outcome.state == "completed":
            result = outcome.result
            if kind in ("blank", "load_blank"):
                self.adapter.session.blank = result
                self._review_candidate = None
                self.preliminary = None
                self.review.setChecked(False)
                self.plots.set_result(result)
                self.review_summary.setText("Compatible blank retained. Load the sample, then acquire and review the preliminary.")
            elif kind in ("preliminary", "load_preliminary"):
                self.adapter.session.preliminary = result
                self._review_candidate = result
                self.preliminary = result
                self.review.setChecked(False)
                self.review_summary.setText(self.adapter.summarize_preliminary(result))
                self.plots.set_result(result)
            elif kind == "load_fit_model":
                self.adapter.fit_model = result
                self.fit_summary.setText("Fit model loaded. It is analysis input and does not establish acquisition readiness.")
            elif kind == "preserve_retained":
                self.preserve_button.setVisible(False)
                self.result = result
                self.plots.set_result(result)
            elif kind == "fit_movie":
                self._show_result(result)
                self.result = result
                summaries = []
                for direction, fit in result["fit_analysis"]["fits_by_direction"].items():
                    summaries.append(f"{direction}: apparent τ = {fit.apparent_tau_s:.6g} s; conditional interval "
                        f"{fit.tau_interval_s[0]:.6g}–{fit.tau_interval_s[1]:.6g} s. "
                        f"Identifiable: {fit.identifiable}. {fit.claim} " + " ".join(fit.warnings))
                self.fit_summary.setText("\n".join(summaries))
                self.plots.view.setCurrentIndex(3)
            elif kind in ("load_selection", "load_bundle", "capabilities"):
                if kind == "load_selection":
                    self.adapter.apply_selection(result)
                elif kind == "load_bundle":
                    self.adapter.apply_bundle(result)
                else:
                    self.adapter.apply_capabilities(result)

    def _outcome(self, outcome):
        if outcome.state == "cancelled":
            self.status.setText("Acquisition stopped. Native/partial records and cleanup outcome were retained.")
        elif outcome.state == "failed":
            self.status.setText(outcome.error)
            retained = getattr(self.adapter.runner, "last_result", None)
            if retained and retained.get("status") == "preservation_failed":
                self.preserve_button.setVisible(True)
                self.status.setText(outcome.error + " Native data remain in memory. Select an available Save Location, then Save retained records.")

    def _show_result(self, result):
        self.adapter.session.result = result
        self.plots.set_result(result)
        self.status.setText(f"{result.get('status', 'loaded')}. Saved at {result.get('output_path', '')}")

    def _busy_update(self, busy):
        for button in (self.blank_button, self.load_blank_button, self.load_preliminary_button,
                       self.sample_selection_button, self.bundle_button, self.capability_button):
            button.setEnabled(not busy)
        self.fit_button.setEnabled(not busy)
        self.fit_model_button.setEnabled(not busy)
        self.preserve_button.setEnabled(not busy)
        self.physical_ready.setEnabled(not busy)
        if busy:
            self._started_at = monotonic()
            self.timer.start()
        else:
            self.timer.stop()
            self._time_update()
        self.context.lifecycle.notify_state(busy, self.status.text())

    def _wait_manual_action(self, description, worker, *, cleanup=False):
        request = {"event": Event(), "approved": False}
        self.manual_action_requested.emit(description, request)
        try:
            while not request["event"].wait(.1):
                if not cleanup:
                    worker.check_cancelled()
            if not cleanup:
                worker.check_cancelled()
            if not request["approved"]:
                raise InterruptedError("Manual physical preparation cancelled")
            return True
        finally:
            self.manual_action_closed.emit(request)

    def _show_manual_action(self, description, request):
        from PySide6.QtWidgets import QMessageBox
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Physical preparation required")
        dialog.setText(description)
        dialog.setInformativeText("The application has no installed actuator for this action. Continue only after completing it.")
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
        self._manual_dialogs[id(request)] = dialog
        def answered(value):
            request["approved"] = value == QMessageBox.StandardButton.Ok
            request["event"].set()
        dialog.finished.connect(answered)
        dialog.open()

    def _close_manual_action(self, request):
        dialog = self._manual_dialogs.pop(id(request), None)
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()

    def _time_update(self):
        if self._started_at is None:
            return
        elapsed = monotonic()-self._started_at
        estimate = self.adapter.wall_estimate(self.plan)
        if not self.command_running():
            self.elapsed.setText(f"Operation finished after {elapsed:.1f} s. Planned complete-workflow estimate: {estimate:.1f} s.")
            return
        remaining = max(0., estimate-elapsed)
        self.elapsed.setText(f"Elapsed {elapsed:.1f} s · estimated remaining {remaining:.1f} s. "
            "Basis: planned preparation, acknowledged upload, scans, controls, bounded reset, retrieval, restoration and analysis; "
            "manual actions may extend the estimate.")

    def _load_record(self, kind):
        path = QFileDialog.getExistingDirectory(self, f"Load {kind}", str(self.context.save_root()))
        if path:
            self._user_action(lambda: self._launch(lambda _worker: self.adapter.load_record(Path(path), kind), "load_"+kind))

    def _load_selection(self):
        path, _ = QFileDialog.getOpenFileName(self, "Accepted sample spectral selection", str(self.context.save_root()), "JSON (*.json)")
        if path:
            self._user_action(lambda: self._launch(lambda _worker: self.adapter.read_selection(Path(path)), "load_selection"))

    def _load_bundle(self):
        from PySide6.QtWidgets import QInputDialog
        bundle_id, accepted = QInputDialog.getText(self, "Promoted bundle", "Registered promoted bundle ID")
        if accepted and bundle_id.strip():
            self._user_action(lambda: self._launch(lambda _worker: self.adapter.read_bundle(bundle_id.strip()), "load_bundle"))

    def _load_fit_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "Native response kernel and spectral fit model", str(self.context.save_root()), "JSON (*.json)")
        if path:
            self._user_action(lambda: self._launch(lambda _worker: json.loads(Path(path).read_text(encoding="utf-8")), "load_fit_model"))

    def _fit_movie(self):
        if self.result is None or self.adapter.fit_model is None or self.plots.movie.currentIndex() < 0:
            raise ValueError("Load/acquire a movie and load an identified native fit model first")
        result, model = deepcopy(self.result), deepcopy(self.adapter.fit_model)
        movie_index = self.plots.movie.currentIndex()
        snapshot = self.context.begin_operation(settings=self.adapter.read_settings(), hardware=False, purpose="apparent recovery analysis")
        self._launch(lambda worker: self.adapter.fit_record(snapshot, worker, result, movie_index, model), "fit_movie")

    def _preserve_retained(self):
        retained = getattr(self.adapter.runner, "last_result", None)
        if retained is None:
            raise ValueError("No retained native data require saving")
        snapshot = self.context.begin_operation(settings={"source_run_id": retained["run_id"]},
                                                hardware=False, purpose="preserve retained native records")
        self._launch(lambda worker: self.adapter.preserve_retained(snapshot, worker), "preserve_retained")

    def _require_preserved(self):
        retained = getattr(self.adapter.runner, "last_result", None)
        if retained and retained.get("status") == "preservation_failed" and not retained.get("recovered_to"):
            raise ValueError("Save retained records before another acquisition; native data remain only in memory.")

    def request_abort(self, reason):
        super().request_abort(reason)
        if self._active_kind in ("blank", "capabilities"):
            self.adapter.request_abort(reason)

    def output_location_changed(self, path):
        self.save_root_provider = lambda: Path(path)

    def instrument_state_changed(self, change):
        for item in change.changes:
            key = f"{item.device_id}.{item.configuration_key}"
            self._initial_state_values.setdefault(key, deepcopy(item.previous_value))
            if item.new_value == self._initial_state_values[key]:
                self.adapter.session.instrument_changes.pop(key, None)
            else:
                self.adapter.session.instrument_changes[key] = deepcopy(item.new_value)
        self.review.setChecked(False)
        if not self.command_running():
            self.refresh_plan()
        else:
            self.request_abort("Relevant instrument state changed during acquisition: " + change.reason)

    def close_blockers(self):
        blockers = list(super().close_blockers())
        retained = getattr(self.adapter.runner, "last_result", None)
        if retained and retained.get("status") == "preservation_failed" and not retained.get("recovered_to"):
            blockers.append("Save the retained native data before closing; the previous storage operation failed.")
        snapshot = self.context.ownership.snapshot()
        if isinstance(snapshot, dict) and snapshot.get("state") == "fault":
            owner = snapshot.get("owner", snapshot)
            if isinstance(owner, dict) and owner.get("instance_id") == self.context.instance_id:
                blockers.append("Instrument cleanup or preservation failed; use host instrument recovery.")
        return tuple(blockers)

    def new_run(self):
        # Check before clearing visible selections; never discard the only native
        # copy after an unsuccessful disk write.
        retained = getattr(self.adapter.runner, "last_result", None)
        if retained and retained.get("status") == "preservation_failed" and not retained.get("recovered_to"):
            self.status.setText("Save retained records before New run; native data remain only in memory.")
            return
        self._review_candidate = None
        self.physical_ready.setChecked(False)
        super().new_run()


def make_handle(context, title):
    widget = RepeatedRapidScanPanel(context)
    return TabHandle(context.instance_id, title, widget, widget.command_running, widget.close_blockers,
                     widget.request_abort, widget.output_location_changed, widget.instrument_state_changed,
                     widget.busy_changed)
