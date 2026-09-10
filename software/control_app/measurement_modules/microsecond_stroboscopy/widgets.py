"""Two independent, hardware-free app tabs using host presentation components."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import csv
import io
import json
import math
from pathlib import Path
import time
from uuid import UUID, uuid4

import numpy as np
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QTabWidget,
    QToolBox, QVBoxLayout, QWidget, QScrollArea,
)

from control_app.measurement_host import TabHandle
from control_app.measurement_host.presentation import (
    GuidedMeasurementPanel, LinkedSliceControl, PlotPanel, StartSnapshot,
    choose_time_display,
)
from .scientific_adapter import MicrosecondScientificAdapter, plain
from .settings import default_settings, information_delay_grid


def _label(key):
    return (key.replace("_sps", " (samples/s)").replace("_cm1", " (cm⁻¹)")
            .replace("_us", " (µs)").replace("_ns", " (ns)")
            .replace("_hz", " (Hz)").replace("_k", " (K)")
            .replace("_s", " (s)") if key.endswith(("_sps", "_cm1", "_us", "_ns", "_hz", "_k", "_s"))
            else key).replace("_", " ").capitalize()


class MicrosecondSettingsWidget(QWidget):
    changed = Signal()

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self._controls = {}
        self._display_scales = {}
        try:
            self.manual_override_fields = set(json.loads(context.preferences.value("manual_override_fields_json", "[]")))
        except (TypeError, ValueError):
            self.manual_override_fields = set()
        self._loading = False
        self._base = default_settings(context.mode).to_dict()
        stored = context.preferences.value("settings_json", "")
        if stored:
            try:
                from .settings import StroboscopySettings
                candidate = StroboscopySettings.from_dict(json.loads(stored))
                if candidate.mode == context.mode:
                    self._base = candidate.to_dict()
            except (ValueError, TypeError):
                pass
        layout = QVBoxLayout(self)
        note = QLabel("Wavelength-by-wavelength equivalent-time recovery.\n"
                      "EXAMPLE ONLY settings support planning and simulation; connected operation requires applicable qualification.")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        layout.addLayout(form)
        for key in ("execution_mode", "condition_profile_id", "averages", "delay_order"):
            self._add_control(form, key, self._base[key])
        self.spectral = QPlainTextEdit()
        self.spectral.setPlaceholderText("Wavenumber cm⁻¹, band label, band/off_band")
        self.spectral.setMaximumHeight(105)
        self.spectral.textChanged.connect(self._emit_changed)
        form.addRow("Measured spectral points\ncm⁻¹, label, role", self.spectral)
        self.delays = QLineEdit()
        self.delays.setToolTip("Explicit nonuniform delays in µs, separated by commas. Negative delays remain negative.")
        self.delays.textChanged.connect(self._emit_changed)
        form.addRow("Delays (µs)", self.delays)
        grid = QPushButton("Use IRF-sized early + logarithmic later grid")
        grid.setToolTip("Derives coverage from the entered response width and latest delay, not literature lifetimes.")
        grid.clicked.connect(self._make_grid)
        form.addRow(grid)
        toolbox = QToolBox()
        layout.addWidget(toolbox)
        for group in ("identity", "response", "timing", "reset", "controls", "budget"):
            page = QWidget()
            nested = QFormLayout(page)
            nested.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            for key, value in self._base[group].items():
                self._add_control(nested, f"{group}.{key}", value)
            toolbox.addItem(page, {
                "identity": "Sample, preparation, cell and temperature",
                "response": "HF2LI, detector response and alignment overrides",
                "timing": "Hardware timing recipe overrides",
                "reset": "Recovery and equivalent-state evidence",
                "controls": "Dark, artifact and blank controls",
                "budget": "Duration, upload, memory and storage estimates",
            }[group])
        provenance = QWidget()
        provenance_form = QFormLayout(provenance)
        for key in ("operating_basis", "promoted_bundle_ids", "calibration_ids"):
            self._add_control(provenance_form, key, self._base[key])
        toolbox.addItem(provenance, "Qualification and provenance")
        layout.addStretch()
        self.apply_settings(self._base)

    def _add_control(self, form, path, value):
        key = path.split(".")[-1]
        self._display_scales[path] = 1e6 if path.startswith("response.") and key.endswith("_s") else 1.
        options = {"execution_mode": ("simulation", "hardware"),
                   "condition_profile_id": ("RT-Mb-R-K", "77K-Mb-G-F"),
                   "delay_order": ("ascending", "descending", "alternating")}
        if path in options:
            control = QComboBox()
            control.addItems(options[path])
            control.currentIndexChanged.connect(lambda *_: self._mark_changed(path))
        elif isinstance(value, bool):
            control = QCheckBox("Evidence-backed claim" if "verified" in key or key == "qualified" else "Required")
            control.toggled.connect(lambda *_: self._mark_changed(path))
        elif isinstance(value, int) and abs(value) <= 2_000_000_000:
            control = QSpinBox()
            control.setRange(-2_000_000_000, 2_000_000_000)
            control.valueChanged.connect(lambda *_: self._mark_changed(path))
        elif isinstance(value, (int, float)):
            control = QDoubleSpinBox()
            control.setDecimals(12)
            control.setRange(-1e15, 1e15)
            control.setKeyboardTracking(False)
            control.valueChanged.connect(lambda *_: self._mark_changed(path))
        else:
            control = QLineEdit()
            if value is None:
                control.setPlaceholderText("Unmeasured / unknown")
            elif isinstance(value, (list, tuple)):
                control.setPlaceholderText("Comma-separated stable record IDs")
            control.textChanged.connect(lambda *_: self._mark_changed(path))
        control.setObjectName(path)
        self._controls[path] = (control, value)
        label = _label(key).replace("(s)", "(µs)") if self._display_scales[path] == 1e6 else _label(key)
        if path == "timing.event_interval_s":
            label = "T660 frame interval (s)"
            control.setToolTip("Interval between hardware frames inside one pump event; sample-event cadence includes independently verified recovery/reset.")
        form.addRow(label, control)

    def _emit_changed(self, *_):
        if not self._loading:
            self.changed.emit()

    def _mark_changed(self, path):
        if not self._loading:
            self.manual_override_fields.add(path)
            self.changed.emit()

    def _make_grid(self):
        try:
            from .settings import StroboscopySettings
            settings = StroboscopySettings.from_dict(self.read_settings())
            grid = information_delay_grid(response_width_us=settings.response.effective_sigma_s * 1e6,
                                          recovery_limit_us=max(settings.delays_us))
            self.delays.setText(", ".join(f"{value:.8g}" for value in grid))
        except ValueError as exc:
            self.delays.setToolTip(str(exc))

    def read_settings(self):
        data = deepcopy(self._base)
        for path, (control, original) in self._controls.items():
            if isinstance(control, QComboBox):
                value = control.currentText()
            elif isinstance(control, QCheckBox):
                value = control.isChecked()
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                value = control.value() / self._display_scales[path]
                if isinstance(original, int):
                    value = int(value)
            elif original is None:
                value = float(control.text()) if control.text().strip() else None
            elif isinstance(original, (list, tuple)):
                value = [item.strip() for item in control.text().split(",") if item.strip()]
            else:
                value = control.text().strip()
            parts = path.split(".")
            if len(parts) == 2:
                data[parts[0]][parts[1]] = value
            else:
                data[path] = value
        data["delays_us"] = [float(item.strip()) for item in self.delays.text().split(",") if item.strip()]
        points = []
        for row in csv.reader(io.StringIO(self.spectral.toPlainText())):
            if not row or not row[0].strip():
                continue
            if len(row) != 3:
                raise ValueError("Each spectral row requires: wavenumber cm⁻¹, band label, band/off_band")
            points.append({"wavenumber_cm1": float(row[0]), "label": row[1].strip(), "role": row[2].strip()})
        data["spectral_points"] = points
        data["mode"] = self.context.mode
        return data

    def apply_settings(self, settings):
        if settings.get("mode", self.context.mode) != self.context.mode:
            raise ValueError("Settings belong to another detector mode")
        self._loading = True
        try:
            self._base = deepcopy(settings)
            for path, (control, _) in self._controls.items():
                value = settings
                for part in path.split("."):
                    value = value[part]
                if isinstance(control, QComboBox):
                    control.setCurrentText(str(value))
                elif isinstance(control, QCheckBox):
                    control.setChecked(bool(value))
                elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                    control.setValue(value * self._display_scales[path])
                else:
                    control.setText(", ".join(value) if isinstance(value, (list, tuple)) else "" if value is None else str(value))
            self.delays.setText(", ".join(str(v) for v in settings["delays_us"]))
            stream = io.StringIO()
            writer = csv.writer(stream)
            for point in settings["spectral_points"]:
                writer.writerow((point["wavenumber_cm1"], point["label"], point["role"]))
            self.spectral.setPlainText(stream.getvalue().strip())
        finally:
            self._loading = False
        self.changed.emit()

    def save_preferences(self):
        self.context.preferences.setValue("settings_json", json.dumps(self.read_settings(), allow_nan=False))
        self.context.preferences.setValue("manual_override_fields_json", json.dumps(sorted(self.manual_override_fields)))
        self.context.preferences.sync()


class _ScientificPlot:
    def __init__(self, owner, kind):
        self.owner, self.kind = owner, kind

    def draw(self, figure, record):
        owner = self.owner
        data = record.get("processing", {})
        axis = figure.add_subplot(211 if self.kind in ("map", "kinetics") else 111)
        points = data.get("points", [])
        maps = data.get("maps", {})
        wn = np.asarray(maps.get("wavenumber_cm1", []), float)
        delays = np.asarray(maps.get("delay_s", maps.get("time_s", [])), float)
        values = np.asarray(maps.get(owner.quantity, []), float)
        valid_map = values.shape == (len(delays), len(wn)) and values.size > 0
        label = {"delta_absorbance": "ΔAbsorbance", "sample_reference_ratio": "Sample/reference ratio Q",
                 "absolute_absorbance": "Absolute absorbance (measured background)"}.get(owner.quantity, owner.quantity)
        unit = owner.time_display
        scale = 1 / unit.seconds_per_unit
        time_label = f"Delay ({unit.unit}); " + ("calibrated optical estimate" if data.get("optical_arrival_calibrated") else "electrical sync; optical time zero unverified")
        if self.kind == "native":
            if record.get("kind") in ("blank", "preliminary"):
                x = [point.get("wavenumber_cm1", math.nan) for point in points]
                y = [point.get("value", math.nan) if point.get("valid", True) else math.nan for point in points]
                axis.plot(x, y, "o-", markersize=3)
                axis.set(xlabel="Wavenumber (cm⁻¹)", ylabel="Sample/reference Q₀" if record.get("mode") == "dual" else "Native detector signal",
                         title="Unpumped preliminary / blank spectral review")
                axis.invert_xaxis()
            else:
                matching = [point for point in points if not len(wn) or math.isclose(float(point.get("wavenumber_cm1", math.nan)), wn[owner.spectral_index])]
                x = [float(point.get("actual_delay_s", point.get("delay_s", 0))) * scale for point in matching]
                y = [point.get(owner.quantity, point.get("value", math.nan) if owner.quantity == "sample_reference_ratio" and record.get("mode") == "dual" else math.nan)
                     for point in matching]
                axis.scatter(x, y, s=16, label="Retained native points")
                axis.set(xlabel=time_label, ylabel=label, title="Native points at selected wavenumber")
        elif self.kind == "map" and valid_map:
            if len(wn) > 1 and len(delays) > 1:
                artist = axis.pcolormesh(wn, delays * scale, np.ma.masked_invalid(values), shading="nearest")
                figure.colorbar(artist, ax=axis, label=label)
            else:
                xx, yy = np.meshgrid(wn, delays * scale)
                axis.scatter(xx.ravel(), yy.ravel(), c=values.ravel())
            axis.axhline(delays[owner.time_index] * scale, color="white", linewidth=.7)
            axis.axvline(wn[owner.spectral_index], color="white", linewidth=.7)
            axis.set(xlabel="Wavenumber (cm⁻¹)", ylabel=time_label, title="Local spectral map; missing support remains gaps")
            axis.invert_xaxis()
            spectrum = figure.add_subplot(212)
            spectrum.plot(wn, values[owner.time_index, :], "o-", markersize=3)
            spectrum.set(xlabel="Wavenumber (cm⁻¹)", ylabel=label,
                         title=f"Measured spectrum at {delays[owner.time_index] * scale:g} {unit.unit}")
            spectrum.invert_xaxis()
        elif self.kind == "kinetics" and valid_map:
            kinetic = owner.selected_kinetic()
            area = kinetic.get("area")
            if area is not None:
                x = np.asarray(kinetic["delay_s"], float) * scale
                y = np.asarray(area, float)
                error = np.asarray(kinetic.get("standard_error", np.full_like(y, np.nan)), float)
                trace_label = kinetic.get("label", "Measured band area")
                label = "Band area (ΔA cm⁻¹)"
            else:
                x, y = delays * scale, values[:, owner.spectral_index]
                error = np.asarray(maps.get("standard_error", np.full_like(values, np.nan)))[:, owner.spectral_index]
                trace_label = f"{wn[owner.spectral_index]:g} cm⁻¹"
            axis.errorbar(x, y, yerr=error if owner.quantity == "delta_absorbance" or area is not None else None,
                          fmt="o-", markersize=3, linewidth=.8, label=trace_label)
            fit = kinetic.get("fit", {}) if owner.quantity == "delta_absorbance" or area is not None else {}
            fit_x = np.asarray(fit.get("delays_s", []), float) * scale
            prediction = np.asarray(fit.get("prediction", []), float)
            residuals = np.asarray(fit.get("residuals", []), float)
            if fit_x.size and prediction.shape == fit_x.shape:
                axis.plot(fit_x, prediction, "--", label="Response-convolved fitted model")
            axis.set(ylabel=label, title="Wavelength / local-band kinetics with native uncertainty")
            axis.legend(loc="upper left")
            residual_axis = figure.add_subplot(212)
            if fit_x.size and residuals.shape == fit_x.shape:
                residual_axis.plot(fit_x, residuals, "o-", markersize=3)
                residual_axis.axhline(0, color="black", linewidth=.7)
            else:
                residual_axis.text(.5, .5, fit.get("reason", "No compatible identified fit"), ha="center", transform=residual_axis.transAxes)
            residual_axis.set(xlabel=time_label, ylabel="Data − fitted model", title="Residuals on measured fit support")
        elif self.kind == "coverage" and valid_map:
            supported = np.isfinite(values).astype(float)
            xx, yy = np.meshgrid(wn, delays * scale)
            axis.scatter(xx.ravel(), yy.ravel(), c=supported.ravel(), vmin=0, vmax=1,
                         marker="s", cmap="RdYlGn", s=25)
            axis.set(xlabel="Wavenumber (cm⁻¹)", ylabel=time_label, title="Native support: green valid, red absent/rejected")
            axis.invert_xaxis()
            coverage = data.get("coverage", {})
            text = "; ".join(f"{key}: {value}" for key, value in coverage.items() if isinstance(value, (str, int, float)))
            if text:
                figure.text(.02, .015, text[:220], fontsize=8, wrap=True)
        else:
            axis.text(.5, .5, "No supported reconstruction in this record.\nNative and rejection records remain retained.",
                      transform=axis.transAxes, ha="center")
            axis.set_title(self.kind.capitalize())
        figure.subplots_adjust(left=.13, bottom=.2, right=.85 if self.kind == "kinetics" else .92, top=.88, hspace=.9)


class MicrosecondViews(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.record = None
        self.time_index = self.spectral_index = 0
        self.quantity = "delta_absorbance"
        self.time_display = choose_time_display([0.0, .005])
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.quantity_control = QComboBox()
        self.quantity_control.addItem("ΔAbsorbance", "delta_absorbance")
        self.quantity_control.addItem("Sample/reference ratio Q", "sample_reference_ratio")
        self.quantity_control.currentIndexChanged.connect(self._quantity_changed)
        controls.addWidget(self.quantity_control)
        self.band_control = QComboBox()
        self.band_control.addItem("Selected wavenumber", "")
        self.band_control.currentIndexChanged.connect(self._redraw)
        controls.addWidget(self.band_control)
        self.time_control = LinkedSliceControl([0], label="Time", unit="ms", decimals=6)
        self.spectral_control = LinkedSliceControl([0], label="Wavenumber", unit="cm⁻¹", decimals=4)
        self.time_control.index_changed.connect(self._time_changed)
        self.spectral_control.index_changed.connect(self._spectral_changed)
        controls.addWidget(self.time_control, 1)
        controls.addWidget(self.spectral_control, 1)
        layout.addLayout(controls)
        self.analysis_summary = QLabel("Load or acquire native data to inspect response-convolved fits, uncertainty and support.")
        self.analysis_summary.setWordWrap(True)
        self.analysis_summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.analysis_summary)
        self.tabs = QTabWidget()
        self.plots = []
        for kind, title in (("native", "Native points"), ("map", "Local spectral map"),
                            ("kinetics", "Wavelength / band-area kinetics"), ("coverage", "Coverage")):
            panel = PlotPanel(_ScientificPlot(self, kind))
            self.plots.append(panel)
            self.tabs.addTab(panel, title)
        layout.addWidget(self.tabs)

    def set_record(self, record):
        self.record = None
        ratio_index = self.quantity_control.findData("sample_reference_ratio")
        if record.get("mode") == "single" and ratio_index >= 0:
            self.quantity_control.removeItem(ratio_index)
        elif record.get("mode") == "dual" and ratio_index < 0:
            self.quantity_control.addItem("Sample/reference ratio Q", "sample_reference_ratio")
        maps = record.get("processing", {}).get("maps", {})
        wn = list(maps.get("wavenumber_cm1", []))
        delays = list(maps.get("delay_s", maps.get("time_s", [])))
        self.time_index = self.spectral_index = 0
        if delays:
            self.time_display = choose_time_display(delays, unit="us" if max(map(abs, delays)) < .001 else "ms")
            self.time_control.input.setSuffix(f" {self.time_display.unit}")
            self.time_control.input.setDecimals(self.time_display.decimals)
            self.time_control.set_coordinates([self.time_display.value(t) for t in delays])
            self.time_index = self.time_control.index
        if wn:
            self.spectral_control.set_coordinates(wn)
            self.spectral_index = self.spectral_control.index
        self.band_control.blockSignals(True)
        self.band_control.clear()
        self.band_control.addItem("Selected wavenumber", "")
        for kinetic in record.get("processing", {}).get("kinetics", []):
            if "area" in kinetic:
                self.band_control.addItem("Band area: " + kinetic.get("label", "Local band"), kinetic.get("label", "Local band"))
        self.band_control.blockSignals(False)
        if "absolute_absorbance" in maps and self.quantity_control.findData("absolute_absorbance") < 0:
            self.quantity_control.addItem("Absolute absorbance (measured background)", "absolute_absorbance")
        if "absolute_absorbance" not in maps and self.quantity_control.findData("absolute_absorbance") >= 0:
            self.quantity_control.removeItem(self.quantity_control.findData("absolute_absorbance"))
        self.record = record
        self._update_fit_summary()
        for plot in self.plots:
            plot.set_result(record)

    def _quantity_changed(self, *_):
        self.quantity = self.quantity_control.currentData()
        self._redraw()

    def _time_changed(self, index):
        self.time_index = index
        self._redraw()

    def _spectral_changed(self, index):
        self.spectral_index = index
        self._redraw()

    def selected_kinetic(self):
        if self.record is None:
            return {}
        processing = self.record.get("processing", {})
        band = self.band_control.currentData()
        wn = processing.get("maps", {}).get("wavenumber_cm1", [])
        for kinetic in processing.get("kinetics", []):
            if band and "area" in kinetic and kinetic.get("label") == band:
                return kinetic
            if not band and len(wn) and kinetic.get("wavenumber_cm1") == wn[self.spectral_index]:
                return kinetic
        return {}

    def _update_fit_summary(self):
        fit = self.selected_kinetic().get("fit", {})
        if not fit:
            self.analysis_summary.setText("No fit available on the selected native support. Missing data remain gaps.")
            return
        parts = [str(fit.get("disposition", "Unresolved fit")).replace("_", " ")]
        if fit.get("reason"):
            parts.append(fit["reason"])
        for i, tau in enumerate(fit.get("taus_s", [])):
            text = f"τ{i+1} {self.time_display.format(tau)}"
            intervals = fit.get("tau_interval95_s", [])
            if i < len(intervals):
                text += f" (local 95% CI {self.time_display.value(intervals[i][0]):.3g}–{self.time_display.value(intervals[i][1]):.3g} {self.time_display.unit})"
            parts.append(text)
        if "aicc" in fit:
            parts.append(f"AICc {fit['aicc']:.3g}; {fit.get('criterion', '')}")
        if "identifiability_condition" in fit:
            parts.append(f"Identifiability condition {fit['identifiability_condition']:.3g}")
        parts.append("Apparent recovery; molecular pathway is not assigned.")
        self.analysis_summary.setText("; ".join(parts))

    def _redraw(self, *_):
        if self.record is not None:
            self._update_fit_summary()
            for plot in self.plots:
                plot.reset_view()

    def clear(self):
        self.record = None
        self.analysis_summary.setText("Load or acquire native data to inspect response-convolved fits, uncertainty and support.")
        for plot in self.plots:
            plot.clear_result()


class MicrosecondPanel(GuidedMeasurementPanel):
    def __init__(self, context, *, runner=None, parent=None):
        settings = MicrosecondSettingsWidget(context)
        adapter = MicrosecondScientificAdapter(context, settings, runner=runner)
        super().__init__(settings, adapter, context, parent)
        splitter = self.layout().itemAt(0).widget()
        summary_box = splitter.widget(1)
        self._summary_scroll = QScrollArea()
        self._summary_scroll.setWidgetResizable(True)
        self._summary_container = splitter.replaceWidget(1, self._summary_scroll)
        self._summary_scroll.setWidget(self._summary_container)
        splitter.setMinimumHeight(220)
        splitter.setMaximumHeight(350)
        self.preliminary_button.setText("2 · Preliminary (pump OFF)")
        self.start_button.setText("3 · Start pumped acquisition")
        self.abort_button.setText("Abort acquisition")
        self.review.setText("I reviewed the preliminary sample/reference spectrum" if context.mode == "dual"
                            else "I reviewed the preliminary unpumped sample spectrum")
        extra = QHBoxLayout()
        self.blank_button = QPushButton("1 · Acquire blank sequence")
        self.load_blank_button = QPushButton("Load blank…")
        self.blank_button.setVisible(context.mode == "single")
        self.load_blank_button.setVisible(context.mode == "single")
        self.check_button = QPushButton("Check devices")
        self.supported_button = QPushButton("Apply supported choices")
        self.bundle_button = QPushButton("Load qualification")
        self.bundle_button.setToolTip("Load selected promoted qualification; preserve entered manual overrides.")
        self.sample_button = QPushButton("Load spectral selection…")
        self.retry_save_button = QPushButton("Retry native save…")
        for button in (self.blank_button, self.load_blank_button, self.check_button, self.supported_button, self.bundle_button, self.sample_button):
            extra.addWidget(button)
        self.layout().insertLayout(1, extra)
        self.blank_status = QLabel("Single: load buffer for the complete sequential blank, then load sample." if context.mode == "single"
                                   else "Dual: load sample and matched-buffer reference simultaneously. No separate routine blank sequence.")
        self.blank_status.setWordWrap(True)
        self.layout().insertWidget(2, self.blank_status)
        recovery = QHBoxLayout()
        recovery.addWidget(self.retry_save_button)
        self.preservation_status = QLabel()
        self.preservation_status.setWordWrap(True)
        recovery.addWidget(self.preservation_status, 1)
        self.layout().insertLayout(3, recovery)
        self.elapsed_label = QLabel("Elapsed 0 s; estimate includes preparation, controls, reset, upload, restoration and analysis.")
        self.result_layout.addWidget(self.elapsed_label)
        self.views = MicrosecondViews()
        self.result_layout.addWidget(self.views, 1)
        self.blank_button.clicked.connect(lambda: self._user_action(lambda: self.begin("blank")))
        self.load_blank_button.clicked.connect(self._choose_blank)
        self.check_button.clicked.connect(lambda: self._user_action(self.check_capabilities))
        self.supported_button.clicked.connect(lambda: self._user_action(self.apply_supported_choices))
        self.bundle_button.clicked.connect(lambda: self._user_action(self.load_qualification))
        self.sample_button.clicked.connect(self._choose_sample_selection)
        self.retry_save_button.clicked.connect(self._choose_retry_native_save)
        settings.changed.connect(self.refresh_plan)
        self.result_ready.connect(self.views.set_record)
        self.run_loaded.connect(lambda record, _: self.views.set_record(record))
        self.new_run_requested.connect(self.views.clear)
        self.busy_changed.connect(lambda busy: context.lifecycle.notify_state(busy, self._active_kind or "idle"))
        self._clock_started = None
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._update_clock)
        self.busy_changed.connect(self._busy_clock)
        self.refresh_plan()

    def refresh_plan(self, *_):
        if self._busy:
            return
        retained = self.preliminary
        super().refresh_plan()
        self.preliminary = retained
        if self.plan is not None:
            errors = self.adapter.validate_review(retained, self.plan) if retained else []
            self.review_summary.setText("\n".join(errors) if errors else self.adapter.summarize_preliminary(retained) if retained else "")
            if retained and errors:
                self.review.setChecked(False)
            try:
                self.settings_widget.save_preferences()
            except (ValueError, TypeError):
                pass
        self._update_controls()

    def _update_controls(self, *_):
        super()._update_controls()
        if not hasattr(self, "blank_button"):
            return
        idle, valid = not self._busy, self.plan is not None
        for button in (self.load_blank_button, self.check_button, self.bundle_button, self.sample_button):
            button.setEnabled(idle)
        self.supported_button.setEnabled(idle and self.adapter.capabilities is not None)
        unsaved = self._needs_native_preservation()
        self.retry_save_button.setVisible(unsaved)
        self.preservation_status.setVisible(unsaved)
        self.retry_save_button.setEnabled(idle and unsaved)
        self.preservation_status.setText("Native saving failed. Retained data must be saved to a writable directory before New run or closing. Instrument recovery remains a separate host action." if unsaved else "")
        self.new_run_button.setEnabled(idle and not unsaved)
        self.blank_button.setEnabled(idle and valid)
        blank_errors = self.adapter.validate_record(self.adapter.blank, self.plan, kind="blank") if valid and self.adapter.blank else []
        if self.context.mode == "single":
            self.preliminary_button.setEnabled(idle and valid and self.adapter.blank is not None and not blank_errors)
            if self.adapter.blank is not None:
                self.blank_status.setText("\n".join("Blank: " + error for error in blank_errors) if blank_errors
                                          else f"Compatible sequential blank: {self.adapter.blank.get('run_id', 'loaded')}")
            else:
                self.blank_status.setText("Load buffer and acquire a complete sequential blank, or load a compatible saved blank.")
        errors = self.adapter.validate_review(self.preliminary, self.plan) if valid and self.preliminary else []
        readiness_errors = self.plan.readiness.blockers if valid and self.plan.settings.execution_mode == "hardware" else ()
        self.review.setEnabled(idle and self.preliminary is not None and not errors)
        self.start_button.setEnabled(idle and valid and self.preliminary is not None and self.review.isChecked() and not errors and not readiness_errors)

    def begin(self, kind):
        if kind == "measurement" and self.plan is not None and self.plan.settings.execution_mode == "hardware" and not self.plan.readiness.hardware_ready:
            self.review.setChecked(False)
            raise ValueError("Connected acquisition readiness: " + "; ".join(self.plan.readiness.errors + self.plan.readiness.blockers))
        if kind != "blank":
            if kind == "preliminary" and self.context.mode == "single":
                errors = self.adapter.validate_record(self.adapter.blank, self.plan, kind="blank")
                if errors:
                    raise ValueError("\n".join(errors))
            return super().begin(kind)
        if self._busy or self.plan is None or self.context.mode != "single":
            raise ValueError("A valid idle single-detector plan is required for a blank")
        self.review.setChecked(False)
        self.preliminary = None
        selected = self.adapter.selected_records()
        operation = self.context.begin_operation(plan=self._host_plan, calibration_records=selected.calibration_records,
                                                 sample_records=selected.sample_records,
                                                 hardware=self.adapter.hardware_required(kind, self._host_plan.settings),
                                                 purpose="complete sequential pump-off blank", cancel=self.request_abort)
        self.snapshot = StartSnapshot(operation, "blank", deepcopy(self.plan), None)
        snapshot = self.snapshot
        self._launch_owned(operation, lambda worker: self.adapter.run_blank(snapshot, worker), "blank")

    def _launch_owned(self, operation, callback, kind):
        try:
            self._launch(callback, kind)
        except Exception:
            if operation.hardware and not (self.worker and self.worker.isRunning()):
                self.context.ownership.release(operation.ownership, safe_verified=True,
                    preservation_verified=True, detail="Worker dispatch failed before device access")
            self._busy = False
            self._active_kind = None
            self._update_controls()
            self.busy_changed.emit(False)
            raise

    def _finished(self, worker, kind, path):
        outcome = worker.outcome
        if outcome and outcome.state == "completed":
            if kind == "blank":
                self.adapter.blank = outcome.result
            elif kind == "load_blank":
                errors = self.adapter.validate_record(outcome.result, self.plan, kind="blank")
                if errors:
                    worker.outcome = type(outcome)("failed", error="\n".join(errors))
                else:
                    self.adapter.blank = outcome.result
                    self.review.setChecked(False)
            elif kind == "check_capabilities":
                self.adapter.capabilities = outcome.result.get("capabilities")
                self.adapter.acknowledge_instrument_check()
            elif kind == "retry_native_save":
                self.adapter.last_record = outcome.result
                self.result = outcome.result
        super()._finished(worker, kind, path)
        if outcome and outcome.state == "completed" and kind in ("preliminary", "blank"):
            self.views.set_record(outcome.result)
        if kind == "check_capabilities":
            if outcome and outcome.state == "completed":
                try:
                    self.apply_supported_choices()
                except (ValueError, TypeError) as exc:
                    self.refresh_plan()
                    self.status.setText(f"Device check completed; supported choices need attention: {exc}. Manual settings remain editable.")
            else:
                self.refresh_plan()
        if outcome and outcome.state != "completed" and kind in ("blank", "preliminary", "measurement") and self.adapter.last_record is not None:
            self.result = self.adapter.last_record
            self.views.set_record(self.result)
            self._update_controls()
        if outcome and outcome.state == "cancelled":
            self.status.setText("Acquisition stopped. Native partial data and restoration records retained.")
        if outcome and outcome.state == "completed" and kind == "retry_native_save":
            self.views.set_record(outcome.result)
            self.status.setText("Retained native data saved. Restoration and original preservation failures remain recorded; use the host's instrument recovery action before hardware work.")

    def _needs_native_preservation(self):
        record = self.adapter.last_record
        return bool(record and record.get("preservation_error") and not record.get("preservation_recovery", {}).get("saved"))

    def close_blockers(self):
        reasons = super().close_blockers()
        if self._needs_native_preservation():
            reasons += ("Native data preservation failed. Use Retry native save to retain this run before closing.",)
        return reasons

    def new_run(self):
        if self._needs_native_preservation():
            raise RuntimeError("Native data remain unsaved. Use Retry native save before New run.")
        return super().new_run()

    def _choose_retry_native_save(self):
        path = QFileDialog.getExistingDirectory(self, "Retry native save in writable directory", str(self.save_root_provider()))
        if path:
            self._user_action(lambda: self.retry_native_save(path))

    def retry_native_save(self, root):
        from .persistence import save_run
        if not self._needs_native_preservation():
            raise ValueError("No unresolved native preservation failure is retained")
        record = deepcopy(self.adapter.last_record)
        recovery_id = str(uuid4())
        run_id = str(UUID(record["run_id"]))
        destination = Path(root).expanduser().resolve() / "measurements" / "microsecond_stroboscopy" / self.context.mode / run_id / ("preservation-recovery-" + recovery_id)
        record["preservation_recovery"] = {
            "recovery_id": recovery_id, "created_utc": datetime.now(timezone.utc).isoformat(),
            "original_native_path": record.get("native_path"), "destination": str(destination),
            "original_preservation_error": record["preservation_error"], "saved": True,
            "instrument_fault_cleared": False,
        }
        def retry(worker):
            worker.check_cancelled()
            worker.message.emit("Saving exact retained native arrays and original restoration/preservation errors; instruments are not accessed.")
            record["native_path"] = str(save_run(destination, record))
            return record
        self._launch(retry, "retry_native_save", destination)

    def _choose_blank(self):
        path = QFileDialog.getExistingDirectory(self, "Load complete compatible blank", str(self.save_root_provider()))
        if path:
            self.load_blank(path)

    def load_blank(self, path):
        self._launch(lambda _: self.adapter.load_run(path), "load_blank", path)

    def check_capabilities(self):
        from .runner import discover_capabilities
        from .persistence import save_run
        settings = self.adapter.read_settings()
        operation = self.context.begin_operation(settings, hardware=self.adapter.hardware_required("check", settings),
                                                 purpose="explicit microsecond capability check", cancel=self.request_abort)
        self._launch_owned(operation, lambda worker: discover_capabilities(
            self.context, operation, cancel=worker.cancel_event.is_set, progress=worker.message.emit,
            preserve=lambda record: save_run(operation.output_path, record)), "check_capabilities")

    def load_qualification(self):
        from .settings import StroboscopySettings
        from .planner import apply_qualified_recommendations
        ids = self.adapter.read_settings().get("promoted_bundle_ids", [])
        if not ids:
            raise ValueError("Enter an applicable promoted bundle ID in Qualification and provenance.")
        qualification = self.adapter.load_qualified_bundle(ids[0])
        settings = StroboscopySettings.from_dict(self.adapter.read_settings())
        recommended = apply_qualified_recommendations(settings, qualification,
                          override_fields=tuple(self.settings_widget.manual_override_fields))
        self.adapter.apply_settings(recommended)
        self.refresh_plan()

    def apply_supported_choices(self):
        from .settings import StroboscopySettings
        from .planner import select_supported_response
        previous = StroboscopySettings.from_dict(self.adapter.read_settings())
        settings = select_supported_response(previous, self.adapter.capabilities,
                    preserve_fields=tuple(self.settings_widget.manual_override_fields))
        self.adapter.apply_settings(settings)
        self.refresh_plan()
        before, after = plain(previous.response), plain(settings.response)
        changes = []
        for name, value in after.items():
            if value == before[name]:
                continue
            scale = 1e6 if name.endswith("_s") else 1
            label = _label(name).replace("(s)", "(µs)") if scale == 1e6 else _label(name)
            changes.append(f"{label}: {before[name] * scale:g} → {value * scale:g}")
        message = "Supported choices applied: " + "; ".join(changes) if changes else "Entered automatic settings already match supported choices."
        overrides = sorted(name.removeprefix("response.") for name in self.settings_widget.manual_override_fields if name.startswith("response."))
        if overrides:
            message += " Manual overrides retained and editable: " + ", ".join(overrides) + "."
        self.status.setText(message)

    def _choose_sample_selection(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load accepted sample spectral selection", str(self.save_root_provider()), "JSON (*.json)")
        if path:
            self._user_action(lambda: self.load_sample_selection(path))

    def load_sample_selection(self, path):
        from control_app.measurement_host.interchange import load_sample_selection
        selection = load_sample_selection(path)
        settings = self.adapter.read_settings()
        if selection.sample_id != settings["identity"]["sample_id"]:
            raise ValueError("Spectral selection sample ID differs from the entered sample")
        if selection.condition_id != settings["identity"]["condition_id"]:
            raise ValueError("Spectral selection condition ID differs from the entered condition")
        self.adapter.sample_records = (plain(selection),)
        settings["identity"]["sample_selection_id"] = selection.selection_id
        self.adapter.apply_settings(settings)
        self.refresh_plan()

    def output_location_changed(self, path):
        self.save_root_provider = lambda: Path(path)

    def instrument_state_changed(self, change):
        self.adapter.instrument_state_changed(change)
        self.review.setChecked(False)
        self.refresh_plan()

    def _busy_clock(self, busy):
        if busy:
            self._clock_started = time.monotonic()
            self._timer.start()
        else:
            self._timer.stop()
            self._update_clock()

    def _update_clock(self):
        if self._clock_started is None:
            return
        elapsed = time.monotonic() - self._clock_started
        budget = plain(self.plan.budget) if self.plan is not None else {}
        estimate = next((float(budget[key]) for key in ("total_wall_s", "total_duration_s", "total_s", "wall_clock_s") if key in budget), None)
        remaining = f"; estimated remaining {max(0, estimate-elapsed):,.1f} s" if estimate is not None else "; remaining estimate unavailable"
        self.elapsed_label.setText(f"Elapsed {elapsed:,.1f} s{remaining}. Basis: plan preparation, controls, tuning, recovery, upload, retrieval, restoration, saving and analysis.")


def make_handle(context, *, title):
    widget = MicrosecondPanel(context)
    return TabHandle(context.instance_id, title, widget, widget.command_running,
                     widget.close_blockers, widget.request_abort, widget.output_location_changed,
                     widget.instrument_state_changed, widget.busy_changed)
