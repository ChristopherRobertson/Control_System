"""Two independent, hardware-free app tabs using host presentation components."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time
from uuid import UUID, uuid4

import numpy as np
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSizePolicy, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from control_app.measurement_host.settings_sections import HF2LIValueInput, hf2li_choices
from control_app.measurement_host import TabHandle
from control_app.measurement_host.presentation import (
    CompactMeasurementPanel, LinkedSliceControl, PlotPanel,
    choose_time_display,
)
from .scientific_adapter import MicrosecondScientificAdapter, plain
from control_app.measurement_host.settings_sections import compact_settings_page, settings_section, run_label_section, PhaseLaserSections
from .settings import default_settings


class _CompactDoubleSpinBox(QDoubleSpinBox):
    def textFromValue(self, value):
        return self.locale().toString(value, "g", 7)


class MicrosecondSettingsWidget(QWidget):
    """Essential inputs and continuously visible independent parameter overrides."""
    changed = Signal()
    MIRCAT_FIELDS = {"timing.probe_rate_hz": "probe_repetition_rate_hz",
                     "timing.probe_width_ns": "probe_pulse_width_ns"}

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self._controls, self.override_modes, self._display_scales = {}, {}, {}
        self._loading = False
        self._base = default_settings(context.mode).to_dict()
        stored = context.preferences.value("settings_json", "")
        if stored:
            try:
                from .settings import StroboscopySettings
                saved = StroboscopySettings.from_dict(json.loads(stored))
                if saved.mode == context.mode:
                    self._base = saved.to_dict()
            except (TypeError, ValueError):
                pass
        self._base["execution_mode"] = "hardware"
        self.manual_override_fields = set(self._base.get("manual_overrides", ()))
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.run_label = run_label_section(root)
        self.run_label.textChanged.connect(self._emit_changed)
        source = QFormLayout()
        self._add_numeric(source, "timing.probe_rate_hz", "Repetition Rate", override=False, suffix=" Hz")
        self._add_numeric(source, "timing.probe_width_ns", "Pulse Width", override=False, suffix=" ns")
        rate = source.takeRow(0).fieldItem.widget()
        width = source.takeRow(0).fieldItem.widget()
        self.lasers = PhaseLaserSections(root, self._emit_changed, supplied={
            "probe_repetition_rate_hz": rate, "probe_pulse_width_ns": width,
        })
        _, layout = settings_section(root, "Microsecond Stroboscopy Settings")
        self.spectral = QLineEdit(self)
        self.spectral.hide()
        self.spectral.setObjectName("spectral_points")
        self.spectral.setToolTip("Measured wavenumbers in cm⁻¹, separated by commas.")
        self.spectral.textChanged.connect(self._emit_changed)
        self.delays = QLineEdit()
        self.delays.setObjectName("delays_us")
        self.delays.setToolTip("Pump–probe delays in µs, separated by commas.")
        self.delays.textChanged.connect(self._emit_changed)
        layout.addRow("Delays (µs)", self.delays)
        self._add_numeric(layout, "averages", "Averages", override=False)
        self._add_numeric(layout, "event_spacing_s", "Event spacing", override=False, suffix=" s")
        self.advanced_widget = QWidget()
        advanced = QFormLayout(self.advanced_widget)
        advanced.setContentsMargins(0, 0, 0, 0)
        advanced.setVerticalSpacing(3)
        advanced.setHorizontalSpacing(5)
        advanced.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        advanced.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        fields = [
            ("response.hf2_order", "Sample filter order" if context.mode == "dual" else "Filter order", ""),
            ("response.hf2_time_constant_s", "Sample time constant" if context.mode == "dual" else "Time constant", " µs"),
            ("response.sample_rate_sps", "Sample rate" if context.mode == "dual" else "CH1 sample rate", " kSa/s"),
        ]
        if context.mode == "dual":
            fields += [("response.reference_order", "Reference filter order", ""),
                       ("response.reference_time_constant_s", "Reference time constant", " µs"),
                       ("response.reference_rate_sps", "Reference rate", " kSa/s")]
        self._add_numeric(layout, "response.integration_aperture_s", "Integration aperture", suffix=" µs")
        for path, label, suffix in fields:
            self._add_numeric(advanced, path, label, suffix=suffix)
        self.restore_auto_button = QPushButton("Restore automatic settings")
        self.restore_auto_button.clicked.connect(self.restore_automatic)
        advanced.addRow(self.restore_auto_button)
        self.apply_settings(self._base)

    @staticmethod
    def _get(data, path):
        value = data
        for part in path.split("."):
            value = value[part]
        return value

    @staticmethod
    def _set(data, path, value):
        parts = path.split(".")
        target = data
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value

    def _add_numeric(self, layout, path, label, *, override=True, suffix=""):
        value = self._get(self._base, path)
        scale = 1e6 if path.startswith("response.") and path.endswith("_s") else 1.
        if path.endswith("_sps"):
            scale = .001
        self._display_scales[path] = scale
        editor = QSpinBox() if isinstance(value, int) else _CompactDoubleSpinBox()
        if isinstance(editor, QDoubleSpinBox):
            editor.setDecimals(3 if path == "event_spacing_s" else 9 if scale == 1 else 6)
            editor.setRange(-1e12, 1e12)
        else:
            editor.setRange(-1000000, 1000000)
        editor.setKeyboardTracking(False)
        editor.setMinimumWidth(80)
        editor.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        editor.setSuffix(suffix)
        editor.setObjectName(path)
        editor.valueChanged.connect(lambda *_: self._field_changed(path))
        self._controls[path] = (editor, value)
        if not override:
            layout.addRow(label, editor)
            return
        hf2 = path.startswith("response.") and not path.endswith("integration_aperture_s")
        mode = HF2LIValueInput() if hf2 else QComboBox()
        if not hf2:
            mode.addItems(("Auto", "Override"))
        mode.setObjectName("override:" + path)
        if not hf2:
            mode.setFixedWidth(75)
        mode.currentIndexChanged.connect(lambda *_: self._override_changed(path))
        self.override_modes[path] = mode
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)
        row_layout.addWidget(mode)
        if hf2:
            editor.setParent(row)
            editor.hide()
        else:
            row_layout.addWidget(editor, 1)
        layout.addRow(label, row)

    def _emit_changed(self, *_):
        if not self._loading:
            self.changed.emit()

    def _field_changed(self, path):
        if not self._loading:
            self.changed.emit()

    def _override_changed(self, path):
        manual = self.override_modes[path].currentIndex() > 0
        selected = self.override_modes[path].currentData()
        if manual and isinstance(self.override_modes[path], HF2LIValueInput):
            selected = float(self.override_modes[path].text())
        if selected is not None:
            editor = self._controls[path][0]
            blocked = editor.blockSignals(True)
            editor.setValue(selected * self._display_scales[path])
            editor.blockSignals(blocked)
        self._controls[path][0].setEnabled(manual)
        if manual:
            self.manual_override_fields.add(path)
        else:
            self.manual_override_fields.discard(path)
        self._emit_changed()

    def set_capability_choices(self, capabilities):
        """Use the detached application snapshot; never query a transport."""
        caps = capabilities or {}
        for path, combo in self.override_modes.items():
            if not path.startswith("response.") or path.endswith("integration_aperture_s"):
                continue
            role = "reference" if "reference_" in path else "sample"
            profile = caps.get(role, caps if role == "sample" else {})
            key = "orders" if path.endswith("order") else "rates_sps" if path.endswith("sps") else "timeconstants_by_order"
            values = profile.get(key, ())
            if isinstance(values, dict):
                order_path = "response.reference_order" if role == "reference" else "response.hf2_order"
                order = self._controls[order_path][0].value() if order_path in self.manual_override_fields else None
                values = hf2li_choices(caps, role, "timeconstant", order)
            combo.set_choices(values)

    def restore_automatic(self):
        self._loading = True
        self.lasers.restore_automatic()
        for path, mode in self.override_modes.items():
            mode.setCurrentIndex(0)
            self._controls[path][0].setEnabled(False)
        self.manual_override_fields.difference_update(self.override_modes)
        for path, key in self.MIRCAT_FIELDS.items():
            self._controls[path][0].setValue(PhaseLaserSections.MIRCAT_DEFAULTS[key] * self._display_scales[path])
        self.manual_override_fields.update(self.MIRCAT_FIELDS)
        self._loading = False
        self.changed.emit()

    def read_settings(self):
        data = deepcopy(self._base)
        data["run_label"] = self.run_label.text().strip()
        data["laser_settings"] = self.lasers.values()
        for path, (editor, original) in self._controls.items():
            if path in self.override_modes and path not in self.manual_override_fields:
                continue
            value = editor.value() / self._display_scales[path]
            combo = self.override_modes.get(path)
            if isinstance(combo, HF2LIValueInput) and path in self.manual_override_fields:
                value = float(combo.text())
            self._set(data, path, int(value) if isinstance(original, int) else value)
        waves = [float(text.strip()) for text in self.spectral.text().split(",") if text.strip()]
        if self.lasers.range_edited:
            waves = self.lasers.points()
        previous = {point["wavenumber_cm1"]: point for point in self._base["spectral_points"]}
        data["spectral_points"] = [{"wavenumber_cm1": wave,
            "label": previous.get(wave, {}).get("label", "Local band"),
            "role": previous.get(wave, {}).get("role", "band")} for wave in waves]
        data["delays_us"] = [float(text.strip()) for text in self.delays.text().split(",") if text.strip()]
        data["manual_overrides"] = sorted(self.manual_override_fields | self.MIRCAT_FIELDS.keys())
        data["mode"] = self.context.mode
        return data

    def apply_settings(self, settings):
        from .settings import normalize_ui_settings
        settings = normalize_ui_settings(plain(settings)).to_dict()
        if settings.get("mode", self.context.mode) != self.context.mode:
            raise ValueError("Settings belong to another detector mode")
        self._loading = True
        try:
            self._base = deepcopy(settings)
            self.run_label.setText(settings.get("run_label", ""))
            self.lasers.apply(settings.get("laser_settings", {}))
            self.manual_override_fields = set(settings.get("manual_overrides", ()))
            for path, key in self.MIRCAT_FIELDS.items():
                if path not in self.manual_override_fields:
                    self._set(settings, path, PhaseLaserSections.MIRCAT_DEFAULTS[key])
            self.manual_override_fields.update(self.MIRCAT_FIELDS)
            for path, (editor, _) in self._controls.items():
                editor.setValue(self._get(settings, path) * self._display_scales[path])
                if path in self.override_modes:
                    manual = path in self.manual_override_fields
                    combo = self.override_modes[path]
                    if isinstance(combo, HF2LIValueInput):
                        combo.setText(f"{self._get(settings, path):.12g}" if manual else "")
                    else:
                        combo.setCurrentIndex(1 if manual else 0)
                    editor.setEnabled(manual)
            self.lasers.set_points([point["wavenumber_cm1"] for point in settings["spectral_points"]])
            self.spectral.setText(", ".join(f"{point['wavenumber_cm1']:g}" for point in settings["spectral_points"]))
            self.delays.setText(", ".join(f"{delay:g}" for delay in settings["delays_us"]))
            self.delays.setCursorPosition(0)
            self.spectral.setCursorPosition(0)
        finally:
            self._loading = False
        self.changed.emit()

    def show_selected_settings(self, settings):
        selected = plain(settings)
        self._loading = True
        try:
            for path, (editor, _) in self._controls.items():
                if path in self.override_modes and path not in self.manual_override_fields:
                    editor.setValue(self._get(selected, path) * self._display_scales[path])
        finally:
            self._loading = False

    def save_preferences(self):
        self.context.preferences.setValue("settings_json", json.dumps(self.read_settings(), allow_nan=False))
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
        time_label = f"Delay ({unit.unit}, " + ("optical estimate)" if data.get("optical_arrival_calibrated") else "electrical sync)")
        if self.kind == "native":
            if record.get("kind") in ("blank", "preliminary"):
                x = [point.get("wavenumber_cm1", math.nan) for point in points]
                normalized = [point.get("value", math.nan) if point.get("valid", True) else math.nan for point in points]
                raw = not np.any(np.isfinite(normalized))
                y = [point.get("raw_sample_x", math.nan) for point in points] if raw else normalized
                axis.plot(x, y, "o-", markersize=3)
                axis.set(xlabel="Wavenumber (cm⁻¹)", ylabel="Sample X" if raw else "Sample/reference Q₀" if record.get("mode") == "dual" else "Sample X",
                         title="Unpumped spectrum")
                axis.invert_xaxis()
            else:
                matching = [point for point in points if not len(wn) or math.isclose(float(point.get("wavenumber_cm1", math.nan)), wn[owner.spectral_index])]
                x = [float(point.get("actual_delay_s", point.get("delay_s", 0))) * scale for point in matching]
                y = [point.get(owner.quantity, point.get("value", math.nan) if owner.quantity == "sample_reference_ratio" and record.get("mode") == "dual" else math.nan)
                     for point in matching]
                if not np.any(np.isfinite(y)):
                    y = [point.get("raw_sample_x", math.nan) for point in matching]
                    label = "Sample X"
                axis.scatter(x, y, s=16, label="Retained native points")
                axis.set(xlabel=time_label, ylabel=label, title="Native points")
        elif self.kind == "map" and valid_map:
            if len(wn) > 1 and len(delays) > 1:
                artist = axis.pcolormesh(wn, delays * scale, np.ma.masked_invalid(values), shading="nearest")
                figure.colorbar(artist, ax=axis, label=label)
            else:
                xx, yy = np.meshgrid(wn, delays * scale)
                axis.scatter(xx.ravel(), yy.ravel(), c=values.ravel())
            axis.axhline(delays[owner.time_index] * scale, color="white", linewidth=.7)
            axis.axvline(wn[owner.spectral_index], color="white", linewidth=.7)
            axis.set(ylabel=f"Delay ({unit.unit})", title="Local spectral map")
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
                axis.plot(fit_x, prediction, "--", label="Response-convolved fit")
            axis.set(ylabel=label, title="Kinetics")
            axis.legend(loc="upper left", fontsize=8)
            residual_axis = figure.add_subplot(212)
            if fit_x.size and residuals.shape == fit_x.shape:
                residual_axis.plot(fit_x, residuals, "o-", markersize=3)
                residual_axis.axhline(0, color="black", linewidth=.7)
            else:
                residual_axis.text(.5, .5, "No fit available", ha="center", transform=residual_axis.transAxes)
            residual_axis.set(xlabel=time_label, ylabel="Residual", title="Fit residuals")
        elif self.kind == "coverage" and valid_map:
            supported = np.isfinite(values).astype(float)
            xx, yy = np.meshgrid(wn, delays * scale)
            axis.scatter(xx.ravel(), yy.ravel(), c=supported.ravel(), vmin=0, vmax=1,
                         marker="s", cmap="RdYlGn", s=25)
            axis.set(xlabel="Wavenumber (cm⁻¹)", ylabel=f"Delay ({unit.unit})", title="Native support: green valid, red absent/rejected")
            axis.invert_xaxis()
            coverage = data.get("coverage", {})
            text = "; ".join(f"{key}: {value}" for key, value in coverage.items() if isinstance(value, (str, int, float)))
            if text:
                figure.text(.02, .015, text[:220], fontsize=8, wrap=True)
        else:
            axis.text(.5, .5, "No reconstructed data",
                      transform=axis.transAxes, ha="center")
            axis.set_title(self.kind.capitalize())
        for axes in figure.axes:
            axes.tick_params(labelsize=8)
            axes.xaxis.label.set_size(9)
            axes.yaxis.label.set_size(9)
            axes.title.set_size(10)
        figure.subplots_adjust(left=.14, bottom=.23, right=.96, top=.9, hspace=.95)


class MicrosecondViews(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.record = None
        self.time_index = self.spectral_index = 0
        self.quantity = "delta_absorbance"
        self.time_display = choose_time_display([0.0, .005])
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)
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
        self.time_control.setEnabled(False)
        self.spectral_control.setEnabled(False)
        controls.addStretch(1)
        layout.addLayout(controls)
        self.analysis_summary = QLabel()
        self.analysis_summary.setWordWrap(True)
        self.analysis_summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.analysis_summary.hide()
        self.tabs = QTabWidget()
        self.plots = []
        for kind, title in (("native", "Native points"), ("map", "Local spectral map"),
                            ("kinetics", "Kinetics"), ("coverage", "Coverage")):
            panel = PlotPanel(_ScientificPlot(self, kind))
            panel.canvas.setMinimumHeight(200)
            self.plots.append(panel)
            self.tabs.addTab(panel, title)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.time_control)
        layout.addWidget(self.spectral_control)
        layout.addWidget(self.analysis_summary)

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
        self.time_control.setEnabled(bool(delays))
        self.spectral_control.setEnabled(bool(wn))
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
        self.analysis_summary.setVisible(bool(fit))
        if not fit:
            self.analysis_summary.clear()
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
            parts.append(f"AICc {fit['aicc']:.3g}")
        self.analysis_summary.setText("; ".join(parts))

    def _redraw(self, *_):
        if self.record is not None:
            self._update_fit_summary()
            for plot in self.plots:
                plot.reset_view()

    def clear(self):
        self.record = None
        self.analysis_summary.clear()
        self.analysis_summary.hide()
        self.time_control.setEnabled(False)
        self.spectral_control.setEnabled(False)
        for plot in self.plots:
            plot.clear_result()


class MicrosecondPanel(CompactMeasurementPanel):
    """Scientific actions hosted by the shared compact measurement workspace."""
    def __init__(self, context, *, runner=None, hardware=True, parent=None):
        settings = MicrosecondSettingsWidget(context)
        adapter = MicrosecondScientificAdapter(context, settings, runner=runner, hardware=hardware)
        self._capability_check_attempted = False
        self._clock_started = None
        super().__init__(settings, adapter, context, parent, advanced_widget=settings.advanced_widget)
        compact_settings_page(self)
        self.advanced_group.setTitle("HF2LI Settings")
        self.preliminary_button.setText("Preliminary sample/reference" if context.mode == "dual" else "Preliminary sample")
        self.start_button.setText("Start acquisition")
        self.abort_button.setText("Abort")
        self.blank_button = QPushButton("Acquire blank")
        self.load_blank_button = QPushButton("Load blank…")
        if context.mode == "single":
            self.blank_actions_layout.addWidget(self.blank_button)
            self.blank_actions_layout.addWidget(self.load_blank_button)
        else:
            self.blank_button.hide()
            self.load_blank_button.hide()
        self.blank_button.clicked.connect(lambda: self._user_action(lambda: self.begin("blank")))
        self.load_blank_button.clicked.connect(self._choose_blank)
        self.retry_save_button = QPushButton("Retry native save…")
        self.retry_save_button.setVisible(False)
        self.retry_save_button.clicked.connect(self._choose_retry_native_save)
        self.settings_extras_layout.addWidget(self.retry_save_button)
        self.views = MicrosecondViews()
        self.add_result_widget(self.views)
        self.elapsed_label = QLabel()
        self.elapsed_label.setVisible(False)
        self.result_layout.addWidget(self.elapsed_label)
        settings.changed.connect(self.refresh_plan)
        self.result_ready.connect(self.views.set_record)
        self.run_loaded.connect(self._loaded_run)
        self.new_run_requested.connect(self.views.clear)
        self.operation_finished.connect(self._operation_finished)
        self.busy_changed.connect(self._busy_clock)
        self.busy_changed.connect(self.refresh_readiness)
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._update_clock)
        self.refresh_plan()
        self.splitter.setSizes([380, 700])

    def refresh_plan(self, *_):
        self.settings_widget.set_capability_choices(self.adapter.capabilities)
        super().refresh_plan()
        if self.plan is not None:
            self.settings_widget.show_selected_settings(self.plan.settings)
            try:
                self.settings_widget.save_preferences()
            except (TypeError, ValueError):
                pass
        self.refresh_readiness()

    def refresh_readiness(self, *_):
        super().refresh_readiness()
        if not hasattr(self, "blank_button"):
            return
        idle = not self.command_running()
        for kind, button in (("blank", self.blank_button), ("preliminary", self.preliminary_button), ("measurement", self.start_button)):
            issues = self.adapter.validate_operation(kind, self.plan, self.preliminary) if self.plan is not None else ("Invalid plan",)
            button.setEnabled(idle and self.plan is not None and not issues)
        if idle and self.plan is not None and not self.validation.text():
            issues = self.adapter.validate_operation("measurement", self.plan, self.preliminary)
            if issues:
                self.validation.setText(self._brief(issues[0]))
        self.load_blank_button.setEnabled(idle)
        unsaved = self._needs_native_preservation()
        self.retry_save_button.setVisible(unsaved)
        self.retry_save_button.setEnabled(idle and unsaved)
        self.new_run_button.setEnabled(idle and not unsaved)

    def begin(self, kind):
        if kind == "blank":
            if self.context.mode != "single":
                raise ValueError("The reference detector records the simultaneous blank.")
            return self.begin_operation("blank", self.adapter.run_blank, invalidates_preliminary=False)
        return super().begin(kind)

    def _operation_finished(self, kind, outcome):
        if outcome.state == "completed":
            if kind in ("blank", "preliminary"):
                self.adapter.reuse_records(outcome.result, self.plan)
                self.result = outcome.result
                self.views.set_record(outcome.result)
            elif kind == "check_capabilities":
                self.adapter.capabilities = outcome.result.get("capabilities")
                self.adapter.acknowledge_instrument_check()
                self.refresh_plan()
            elif kind == "retry_native_save":
                self.adapter.last_record = outcome.result
                self.result = outcome.result
                self.views.set_record(outcome.result)
                self.status.setText("Native data saved.")
        elif kind in ("blank", "preliminary", "measurement") and self.adapter.last_record is not None:
            self.result = self.adapter.last_record
            self.views.set_record(self.result)
        if outcome.state == "cancelled":
            self.status.setText("Acquisition stopped.")
        self.refresh_readiness()

    def _loaded_run(self, record, path):
        self.adapter.reuse_records(record, self.plan)
        self.views.set_record(record)
        self.refresh_readiness()

    def _choose_blank(self):
        path = QFileDialog.getExistingDirectory(self, "Load blank", str(self.save_root_provider()))
        if path:
            self.load_blank(path)

    def load_blank(self, path):
        return self.load_run(path)

    def check_capabilities(self):
        from .runner import discover_capabilities
        from .persistence import save_run
        def check(snapshot, worker):
            return discover_capabilities(self.context, snapshot.operation,
                cancel=worker.cancel_event.is_set, progress=worker.message.emit,
                preserve=lambda record: save_run(snapshot.operation.output_path, record))
        return self.begin_operation("check_capabilities", check, invalidates_preliminary=False, requires_valid_plan=False)

    def _needs_native_preservation(self):
        record = self.adapter.last_record
        return bool(record and record.get("preservation_error") and not record.get("preservation_recovery", {}).get("saved"))

    def close_blockers(self):
        reasons = tuple(super().close_blockers())
        if self._needs_native_preservation():
            reasons += ("Native data are unsaved. Retry native save before closing.",)
        return reasons

    def new_run(self):
        if self._needs_native_preservation():
            raise RuntimeError("Native data remain unsaved. Retry native save before New run.")
        result = super().new_run()
        self._clock_started = None
        self.elapsed_label.clear()
        self.elapsed_label.hide()
        return result

    def _choose_retry_native_save(self):
        path = QFileDialog.getExistingDirectory(self, "Retry native save", str(self.save_root_provider()))
        if path:
            self._user_action(lambda: self.retry_native_save(path))

    def retry_native_save(self, root):
        from .persistence import save_run
        if not self._needs_native_preservation():
            raise ValueError("No unsaved native data are retained.")
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
        def retry(snapshot, worker):
            worker.check_cancelled()
            worker.message.emit("Saving retained native data…")
            record["native_path"] = str(save_run(destination, record))
            return record
        return self.begin_operation("retry_native_save", retry, invalidates_preliminary=False, requires_valid_plan=False)

    def output_location_changed(self, path):
        super().output_location_changed(path)

    def instrument_state_changed(self, change):
        self.adapter.instrument_state_changed(change)
        self.refresh_plan()

    def _busy_clock(self, busy):
        if busy:
            self._clock_started = time.monotonic()
            self.elapsed_label.setVisible(True)
            self._timer.start()
        else:
            self._timer.stop()
            self._update_clock()

    def _update_clock(self):
        if self._clock_started is None:
            return
        elapsed = time.monotonic() - self._clock_started
        budget = plain(self.plan.budget) if self.plan is not None else {}
        estimate = budget.get("wall_clock_s")
        from control_app.measurement_host.experiment_summary import remaining_text
        remaining = " · " + remaining_text(estimate, elapsed)
        self.elapsed_label.setText(f"Elapsed {elapsed:,.1f} s{remaining}")


def make_handle(context, *, title):
    widget = MicrosecondPanel(context)
    return TabHandle(context.instance_id, title, widget, widget.command_running,
                     widget.close_blockers, widget.request_abort, widget.output_location_changed,
                     widget.instrument_state_changed, widget.busy_changed)
