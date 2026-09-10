"""Compact acquisition tabs and native-coordinate recovery inspection."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QFileDialog, QSizePolicy,
)

from control_app.measurement_host import TabHandle
from control_app.measurement_host.presentation import (
    CompactMeasurementPanel, LinkedSliceControl, PlotPanel,
    choose_time_display,
)
from .settings import RepeatedRapidScanSettings


class _EssentialDoubleSpinBox(QDoubleSpinBox):
    def textFromValue(self, value):
        # Display the shortest round-trippable number without padding precise
        # loaded settings with a screenful of trailing zeros.
        return str(value).replace(".", self.locale().decimalPoint())


def _override_text(value):
    number = float(value)
    return str(int(number)) if number.is_integer() else repr(number)


class SettingsWidget(QWidget):
    """Essential intent plus independent, optional instrument overrides."""
    changed = Signal()

    def __init__(self, mode, settings=None):
        super().__init__()
        self.mode = mode
        self.capabilities = None
        self.inputs, self.override_inputs = {}, {}
        if settings is None:
            from .planner import resolve_intent_settings
            from .settings import AcquisitionIntent
            settings = resolve_intent_settings(AcquisitionIntent(), mode=mode)
        self._base = settings
        self.advanced = QWidget()
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.setVerticalSpacing(3)
        self.sample = QLineEdit()
        self.sample.setObjectName("rrs_sample_name")
        self.sample.editingFinished.connect(lambda *_: self.changed.emit())
        form.addRow("Sample", self.sample)
        fields = (
            ("spectral_min_cm1", "Start", " cm⁻¹", 1., 10000., 3, 1.),
            ("spectral_max_cm1", "Stop", " cm⁻¹", 1., 10000., 3, 1.),
            ("observation_duration_s", "Observe after pump", " s", .001, 1e6, 3, 1.),
            ("phase_count", "Phase positions", "", 1, 10000, 0, 1),
            ("repeats", "Repeats", "", 1, 10000, 0, 1),
        )
        for key, label, suffix, lower, upper, decimals, step in fields:
            control = QSpinBox() if decimals == 0 else _EssentialDoubleSpinBox()
            if decimals:
                control.setDecimals(decimals)
            control.setRange(lower, upper)
            control.setSingleStep(step)
            control.setSuffix(suffix)
            control.setKeyboardTracking(False)
            control.setObjectName("rrs_" + key)
            control.valueChanged.connect(lambda *_: self.changed.emit())
            self.inputs[key] = control
            form.addRow(label, control)
        advanced = QFormLayout(self.advanced)
        advanced.setContentsMargins(0, 0, 0, 0)
        advanced.setVerticalSpacing(3)
        overrides = [
            ("scan_speed_cm1_s", "Scan speed (cm⁻¹/s)"),
            ("sample_rate_hz", "Sample rate (Sa/s)"),
            ("sample_filter_order", "Sample filter order"),
            ("sample_filter_timeconstant_s", "Time constant (s)"),
        ]
        if mode == "dual":
            overrides += [
                ("reference_rate_hz", "Reference rate (Sa/s)"),
                ("reference_filter_order", "Reference filter order"),
                ("reference_filter_timeconstant_s", "Time constant (s)"),
            ]
        overrides += [
            ("probe_frequency_hz", "Repetition rate (Hz)"),
            ("mircat_pulse_width_ns", "Pulse width (ns)"),
        ]
        for key, label in overrides:
            combo = QComboBox()
            combo.setEditable(True)
            combo.setMinimumContentsLength(6)
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            combo.addItem("Automatic", None)
            initial = getattr(self._base, key)
            if initial is not None:
                combo.addItem(_override_text(initial), initial)
            combo.setObjectName("rrs_override_" + key)
            combo.currentIndexChanged.connect(lambda *_: self.changed.emit())
            combo.lineEdit().editingFinished.connect(lambda *_: self.changed.emit())
            self.override_inputs[key] = combo
            if mode != "dual" or key not in {
                    "sample_rate_hz", "sample_filter_order", "sample_filter_timeconstant_s",
                    "reference_rate_hz", "reference_filter_order", "reference_filter_timeconstant_s"}:
                advanced.addRow(label, combo)
        if mode == "dual":
            detectors = QWidget()
            grid = QGridLayout(detectors)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setVerticalSpacing(3)
            for column, role in enumerate(("sample", "reference"), 1):
                grid.addWidget(QLabel(role.title()), 0, column)
                for row, (suffix, label) in enumerate((("rate_hz", "Rate (Sa/s)"),
                        ("filter_order", "Filter order"), ("filter_timeconstant_s", "Time constant (s)")), 1):
                    if column == 1:
                        grid.addWidget(QLabel(label), row, 0)
                    control = self.override_inputs[f"{role}_{suffix}"]
                    control.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
                    control.setMinimumWidth(72)
                    grid.addWidget(control, row, column)
            advanced.insertRow(1, detectors)
        self.restore_auto_button = QPushButton("Restore automatic settings")
        self.restore_auto_button.clicked.connect(self.restore_automatic)
        advanced.addRow(self.restore_auto_button)
        self.apply(self._base.to_dict())

    def raw_intent(self):
        return {"sample_name": self.sample.text().strip(),
                **{key: control.value() for key, control in self.inputs.items()}}

    def read(self):
        from .settings import AcquisitionIntent
        from .planner import resolve_intent_settings
        values = {key: control.value() for key, control in self.inputs.items()}
        values["sample_name"] = self.sample.text().strip() or "Sample"
        overrides = dict(getattr(self._base, "manual_overrides", {}) or {})
        for key, control in self.override_inputs.items():
            text = control.currentText().strip()
            if not text or text.lower() == "automatic":
                overrides.pop(key, None)
                continue
            try:
                value = float(text)
            except ValueError:
                raise ValueError(f"{key.replace('_', ' ')}: enter Automatic or a number") from None
            if key in ("sample_filter_order", "reference_filter_order"):
                if not value.is_integer():
                    raise ValueError(f"{key.replace('_', ' ')} must be an integer")
                value = int(value)
            overrides[key] = value
        settings = resolve_intent_settings(AcquisitionIntent(**values), mode=self.mode,
            base_settings=self._base, capabilities=self.capabilities, overrides=overrides)
        # Simulation is available through injected developer transports only.
        from dataclasses import replace
        return replace(settings, execution="hardware").to_dict()

    def apply(self, value):
        from .settings import AcquisitionIntent
        from .session import normalize_ui_settings
        settings = RepeatedRapidScanSettings.from_dict(normalize_ui_settings(value, mode=self.mode))
        if settings.mode != self.mode:
            raise ValueError("Plan detector mode does not match this tab")
        self._base = settings
        intent = (AcquisitionIntent(**settings.acquisition_intent) if settings.acquisition_intent
                  else AcquisitionIntent.from_settings(settings))
        self.sample.setText(intent.sample_name)
        for key, control in self.inputs.items():
            control.blockSignals(True)
            value = getattr(intent, key)
            if isinstance(control, QDoubleSpinBox):
                from decimal import Decimal
                control.setDecimals(max(3, min(15, -Decimal(str(value)).as_tuple().exponent)))
            control.setValue(value)
            control.blockSignals(False)
        for key, control in self.override_inputs.items():
            control.blockSignals(True)
            value = settings.manual_overrides.get(key)
            control.setCurrentIndex(0)
            if value is not None:
                control.setEditText(_override_text(value))
            control.blockSignals(False)

    def set_capabilities(self, capabilities):
        self.capabilities = capabilities
        live = getattr(capabilities, "live_settings", {}) or {}
        for key, control in self.override_inputs.items():
            value = live.get(key)
            if value is not None:
                text = _override_text(value)
                if control.findText(text) < 0:
                    control.addItem(text, value)

    def restore_automatic(self):
        from dataclasses import replace
        self._base = replace(self._base, manual_overrides={})
        for control in self.override_inputs.values():
            control.blockSignals(True)
            control.setCurrentIndex(0)
            control.blockSignals(False)
        self.changed.emit()


def native_detector_coordinates(scan, movie):
    """One documented scan origin preserves inter-detector delays and gaps."""
    from dataclasses import replace
    from .processing import aligned_seconds
    anchor = movie.clock_corrections[0].offset_s if movie.clock_corrections else 0.
    clocks = {clock.clock_id: replace(clock, offset_s=clock.offset_s-anchor)
              for clock in movie.clock_corrections}
    def seconds(stream):
        return aligned_seconds(stream.timestamps_s, unit_s=stream.timestamp_unit_s,
            origin=stream.timestamp_origin, correction=clocks.get(stream.clock_id))
    trajectory_times = seconds(scan.trajectory)
    finite = trajectory_times[np.isfinite(trajectory_times)]
    origin = float(finite[0]) if len(finite) else 0.
    traces = []
    for role, stream in (("Sample", scan.sample), ("Reference", scan.reference)):
        if stream is not None:
            label = role
            if stream.clock_id != scan.trajectory.clock_id and not (
                    stream.clock_id in clocks and scan.trajectory.clock_id in clocks):
                label += " (clock alignment unknown)"
            traces.append((label, seconds(stream)-origin, stream.values))
    return traces


class MoviePlots(QWidget):
    """Point maps do not interpolate a scan into an instantaneous spectrum."""
    def __init__(self):
        super().__init__()
        self.result = None
        self.points = []
        self._updating = False
        self.movie = QComboBox()
        self.movie.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.movie.setMinimumContentsLength(12)
        self.quantity = QComboBox()
        self.quantity.addItem("Relative ΔA", "delta_absorbance")
        self.quantity.addItem("Detector signal", "normalized_signal")
        self.quantity.addItem("Absolute absorbance", "absolute_absorbance")
        self.view = QComboBox()
        self.view.addItems(["Spectrum", "Wavelength kinetics", "Band-area kinetics", "Phase/direction consistency", "Fit residuals", "Native detectors"])
        self.scan = LinkedSliceControl(label="Scan time", unit="s", decimals=9)
        self.wavenumber = LinkedSliceControl(label="Wavenumber", unit="cm⁻¹", decimals=6)
        self.description = QLabel()
        self.description.setWordWrap(False)
        self.description.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.plot = PlotPanel(self)
        self.plot.canvas.setMinimumHeight(220)
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
        available = [any(np.any(np.asarray(p.valid) & np.isfinite(getattr(p, field))) for p in self.points)
                     for field in ("delta_absorbance", "normalized_signal", "absolute_absorbance")]
        self.quantity.blockSignals(True)
        for index, present in enumerate(available):
            self.quantity.model().item(index).setEnabled(present or index == 1)
        if not available[self.quantity.currentIndex()]:
            self.quantity.setCurrentIndex(0 if available[0] else 1)
        if self.points and not any(available):
            self.view.setCurrentIndex(5)
        self.quantity.blockSignals(False)
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
            figure.add_subplot(111).text(.1, .5, "Acquire or load a movie")
            return
        field = self.quantity.currentData()
        label = self.quantity.currentText()
        selected = self.points[self.scan.index]
        wavenumber = self.wavenumber.coordinates[self.wavenumber.index] if self.wavenumber.coordinates else np.nan
        times = np.concatenate([np.asarray(p.time_s) for p in self.points])
        finite_times = times[np.isfinite(times)]
        display = choose_time_display(finite_times.tolist()) if len(finite_times) else choose_time_display([0.])
        scale = display.seconds_per_unit
        axes = figure.subplots(1, 2)
        map_ax, detail_ax = axes
        spectrum_ax = native_ax = kinetic_ax = detail_ax
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
        axis_bases = movie.provenance.get("axis_basis_by_scan", {}).values()
        axis_uncalibrated = any(basis == "observed_uncalibrated_trajectory" for basis in axis_bases)
        axis_label = "Indicated wavenumber (cm⁻¹)" if axis_uncalibrated else "Wavenumber (cm⁻¹)"
        map_ax.set(xlabel=axis_label, ylabel=f"{basis_label} time ({display.unit})",
                   title="Time-resolved signal")
        map_ax.invert_xaxis()
        map_ax.axhline(0, color="gray", linewidth=.6)
        map_ax.axvline(wavenumber, color="gray", linewidth=.6)
        if self.view.currentIndex() == 0:
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
            spectrum_ax.set(xlabel=axis_label, ylabel=label,
                            title=f"Scan {selected.scan_index} · {selected.direction}")
            spectrum_ax.invert_xaxis()
        elif self.view.currentIndex() == 5:
            native = next((m for m in result.get("native_movies", ()) if m.movie_id == movie.movie_id), None)
            if native:
                scan = next((s for s in native.scans if s.scan_index == selected.scan_index), None)
                if scan:
                    for role, times, values in native_detector_coordinates(scan, native):
                        native_ax.plot(times, values, ".-", label=role, markersize=2)
                    native_ax.legend(fontsize="small")
            native_ax.set(xlabel="Native time from scan start (s)", ylabel="HF2LI native signal",
                          title="Native detectors")
        else:
            if self.view.currentIndex() == 4:
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
            elif self.view.currentIndex() == 2:
                groups = sorted({(b.window_cm1, b.direction, b.kind) for b in movie.band_kinetics})
                for window, direction, kind in groups:
                    entries = [b for b in movie.band_kinetics if (b.window_cm1, b.direction, b.kind) == (window, direction, kind)]
                    t = np.asarray([(b.earliest_time_s+b.latest_time_s)/2 for b in entries])/scale
                    widths = np.asarray([(b.latest_time_s-b.earliest_time_s)/2 for b in entries])/scale
                    y = [b.area if b.valid else np.nan for b in entries]
                    kinetic_ax.errorbar(t, y, xerr=widths, fmt=".", label=f"{kind} {window} {direction}")
                kinetic_ax.set_ylabel("Integrated ΔA (cm⁻¹); bars = scan time span")
            elif self.view.currentIndex() == 3:
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
            ax.title.set_fontsize(9)
            ax.xaxis.label.set_fontsize(8)
            ax.yaxis.label.set_fontsize(8)
        figure.tight_layout(pad=1.1)
        valid_count = sum((np.asarray(p.valid) & np.isfinite(getattr(p, field))).sum() for p in self.points)
        total_count = sum(len(p.time_s) for p in self.points)
        details = [f"{valid_count}/{total_count} valid points", basis_label]
        if axis_uncalibrated:
            details.append("axis uncalibrated")
        details.append("dark correction not applied")
        self.description.setText(" · ".join(details))
        self.description.setToolTip(" ".join(movie.warnings))


class RepeatedRapidScanPanel(CompactMeasurementPanel):
    """Compact host lifecycle; the module owns only scientific presentation."""
    def __init__(self, context):
        from .adapter import RepeatedRapidScanAdapter
        settings = SettingsWidget(context.mode)
        adapter = RepeatedRapidScanAdapter(context, settings)
        self._initial_state_values = {}
        super().__init__(settings, adapter, context, advanced_widget=settings.advanced)
        self.file_layout.setDirection(QHBoxLayout.Direction.LeftToRight)
        self.blank_actions_layout.setDirection(QHBoxLayout.Direction.LeftToRight)
        self.settings_layout.setContentsMargins(6, 6, 6, 6)
        self.settings_layout.setSpacing(3)
        self.advanced_layout.setContentsMargins(6, 6, 6, 6)
        self.setObjectName(context.instance_id)
        self.preliminary_button.setText("Acquire sample · pump off")
        self.start_button.setText("Start recovery movies")
        self.abort_button.setText("Stop")
        self.settings_widget.changed.connect(self.refresh_plan)
        self.capability_button = self.add_settings_action("Check device", lambda: self._user_action(
            lambda: self.begin_auxiliary("capabilities")))
        self.blank_button = self.add_blank_action("Acquire blank", lambda: self._user_action(
            lambda: self.begin_auxiliary("blank")))
        self.load_blank_button = self.add_blank_action("Load blank…", lambda: self._load_record("blank"))
        self.blank_button.setVisible(context.mode == "single")
        self.load_blank_button.setVisible(context.mode == "single")
        self.plots = MoviePlots()
        self.add_result_widget(self.plots)
        self.sample_selection_button = QPushButton("Bands…")
        self.fit_model_button = QPushButton("Fit model…")
        self.fit_button = QPushButton("Fit movie")
        self.fit_summary = QLabel()
        self.fit_summary.setWordWrap(True)
        self.fit_summary.setMaximumHeight(45)
        self.preserve_button = QPushButton("Save retained records")
        self.preserve_button.hide()
        for control in (self.sample_selection_button, self.fit_model_button, self.fit_button):
            self.run_file_layout.addWidget(control)
        self.fit_summary.hide()
        self.result_layout.addWidget(self.fit_summary)
        self.action_layout.addWidget(self.preserve_button)
        self.sample_selection_button.clicked.connect(self._load_selection)
        self.fit_model_button.clicked.connect(self._load_fit_model)
        self.fit_button.clicked.connect(lambda: self._user_action(self._fit_movie))
        self.preserve_button.clicked.connect(lambda: self._user_action(self._preserve_retained))
        self.result_ready.connect(self._show_result)
        self.run_loaded.connect(lambda result, _path: self._show_result(result))
        self.operation_finished.connect(self._operation_finished)
        self.new_run_requested.connect(self.plots.clear)
        self.busy_changed.connect(self._busy_update)
        self.outcome_ready.connect(self._outcome)
        self.splitter.setSizes([320, 760])
        self.refresh_readiness()

    def refresh_plan(self, *_):
        super().refresh_plan()
        self.validation.setVisible(bool(self.validation.text()))
        if self.plan is not None:
            self.preliminary = self.adapter.compatible_preliminary(self.plan)
            self.refresh_readiness()

    def begin(self, kind):
        self._require_preserved()
        if self.plan is not None:
            self.preliminary = self.adapter.compatible_preliminary(self.plan)
        return super().begin(kind)

    def begin_auxiliary(self, kind):
        self._require_preserved()
        return self.begin_operation(kind, lambda snapshot, worker:
            self.adapter.run_auxiliary(snapshot, worker, kind), requires_valid_plan=kind != "capabilities")

    def _operation_finished(self, kind, outcome):
        try:
            if outcome.state != "completed":
                return
            result = outcome.result
            if kind in ("blank", "load_blank"):
                self.adapter.session.blank = result
                self.plots.set_result(result)
            elif kind in ("preliminary", "load_preliminary"):
                self.adapter.session.preliminary = result
                self.preliminary = result
                self.plots.set_result(result)
            elif kind == "load_fit_model":
                self.adapter.fit_model = result
                self.fit_summary.setText("Fit model loaded")
                self.fit_summary.show()
            elif kind == "preserve_retained":
                self.preserve_button.hide()
                self.result = result
                self._show_result(result)
            elif kind == "fit_movie":
                self.result = result
                self._show_result(result)
                summaries = [f"{direction}: apparent τ {fit.apparent_tau_s:.4g} s"
                    for direction, fit in result["fit_analysis"]["fits_by_direction"].items()]
                self.fit_summary.setText(" · ".join(summaries))
                self.fit_summary.show()
                self.plots.view.setCurrentIndex(4)
            elif kind == "load_selection":
                self.adapter.apply_selection(result)
                self.refresh_plan()
            elif kind == "capabilities":
                self.adapter.apply_capabilities(result)
                self.settings_widget.set_capabilities(self.adapter.capabilities)
                self.refresh_plan()
            if kind in ("measurement", "preliminary", "blank"):
                capabilities = result.get("capabilities", result.get("readbacks", {}).get("capabilities"))
                if capabilities:
                    self.adapter.apply_capabilities({"capabilities": capabilities})
                    self.refresh_plan()
            self.refresh_readiness()
        except Exception as exc:
            self.set_status(f"Presentation failed after {kind}: {exc}")

    def _outcome(self, outcome):
        if outcome.state == "failed":
            retained = getattr(self.adapter.runner, "last_result", None)
            if retained and retained.get("status") == "preservation_failed":
                self.preserve_button.show()
                self.set_status("Save failed; choose an available Save Location and save retained records.")

    def _show_result(self, result):
        self.adapter.session.result = result
        if result.get("kind") == "preliminary":
            self.adapter.session.preliminary = result
        elif result.get("kind") == "blank":
            self.adapter.session.blank = result
        try:
            self.plots.set_result(result)
        except Exception as exc:
            self.set_status(f"Presentation failed: {exc}")

    def _busy_update(self, busy):
        for button in (self.sample_selection_button, self.fit_button,
                       self.fit_model_button, self.preserve_button):
            button.setEnabled(not busy)
        self.context.lifecycle.notify_state(busy, self.status.text())

    def _load_record(self, kind):
        path = QFileDialog.getExistingDirectory(self, f"Load {kind}", str(self.context.save_root()))
        if path:
            self._user_action(lambda: self.begin_operation("load_" + kind,
                lambda _snapshot, _worker: self.adapter.load_record(Path(path), kind)))

    def _load_selection(self):
        path, _ = QFileDialog.getOpenFileName(self, "Spectral bands", str(self.context.save_root()), "JSON (*.json)")
        if path:
            self._user_action(lambda: self.begin_operation("load_selection",
                lambda _snapshot, _worker: self.adapter.read_selection(Path(path))))

    def _load_fit_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "Native response and spectral fit model", str(self.context.save_root()), "JSON (*.json)")
        if path:
            self._user_action(lambda: self.begin_operation("load_fit_model",
                lambda _snapshot, _worker: json.loads(Path(path).read_text(encoding="utf-8"))))

    def _fit_movie(self):
        if self.result is None or self.adapter.fit_model is None or self.plots.movie.currentIndex() < 0:
            raise ValueError("Load a movie and a fit model first")
        result, model = deepcopy(self.result), deepcopy(self.adapter.fit_model)
        movie_index = self.plots.movie.currentIndex()
        self.begin_operation("fit_movie", lambda snapshot, worker:
            self.adapter.fit_record(snapshot.operation, worker, result, movie_index, model))

    def _preserve_retained(self):
        if getattr(self.adapter.runner, "last_result", None) is None:
            raise ValueError("No retained native data require saving")
        self.begin_operation("preserve_retained", lambda snapshot, worker:
            self.adapter.preserve_retained(snapshot.operation, worker))

    def _require_preserved(self):
        retained = getattr(self.adapter.runner, "last_result", None)
        if retained and retained.get("status") == "preservation_failed" and not retained.get("recovered_to"):
            raise ValueError("Save retained records before another acquisition; native data remain in memory.")

    def instrument_state_changed(self, change):
        for item in change.changes:
            key = f"{item.device_id}.{item.configuration_key}"
            self._initial_state_values.setdefault(key, deepcopy(item.previous_value))
            if item.new_value == self._initial_state_values[key]:
                self.adapter.session.instrument_changes.pop(key, None)
            else:
                self.adapter.session.instrument_changes[key] = deepcopy(item.new_value)
        if not self.command_running():
            self.refresh_plan()
        else:
            self.request_abort("Instrument settings changed during acquisition: " + change.reason)

    def close_blockers(self):
        blockers = list(super().close_blockers())
        retained = getattr(self.adapter.runner, "last_result", None)
        if retained and retained.get("status") == "preservation_failed" and not retained.get("recovered_to"):
            blockers.append("Save retained native data before closing.")
        snapshot = self.context.ownership.snapshot()
        if isinstance(snapshot, dict) and snapshot.get("state") == "fault":
            owner = snapshot.get("owner", snapshot)
            if isinstance(owner, dict) and owner.get("instance_id") == self.context.instance_id:
                blockers.append("Instrument cleanup or preservation failed; use host instrument recovery.")
        return tuple(blockers)

    def new_run(self):
        try:
            self._require_preserved()
        except ValueError as exc:
            self.set_status(str(exc))
            return
        super().new_run()


def make_handle(context, title):
    widget = RepeatedRapidScanPanel(context)
    return TabHandle(context.instance_id, title, widget, widget.command_running, widget.close_blockers,
                     widget.request_abort, widget.output_location_changed, widget.instrument_state_changed,
                     widget.busy_changed)
