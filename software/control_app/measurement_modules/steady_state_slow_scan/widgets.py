"""Spectrum-first scientific presentation using the frozen measurement host."""
from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path
import time

import numpy as np
from PySide6.QtCore import QTimer, Signal, Qt
from PySide6.QtWidgets import (
    QBoxLayout, QComboBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget, QFileDialog, QDoubleSpinBox, QSpinBox, QHeaderView, QToolButton,
)

from control_app.measurement_host.settings_sections import HF2LIValueInput, hf2li_choices
from control_app.measurement_host import TabHandle
from control_app.measurement_host.presentation import (
    CompactMeasurementPanel, LinkedSliceControl, PlotPanel,
)


def _value(record, key, default=None):
    return record.get(key, default) if isinstance(record, dict) else getattr(record, key, default)


def _fit_for_spectrum(result, spectrum):
    """Some rejected/short spectra have no fit; index position is not identity."""
    sweep_id = _value(_value(spectrum, "native"), "sweep_id")
    return next((fit for fit in result.get("fits", ())
                 if _value(fit, "provenance", {}).get("sweep_id") == sweep_id), None)


def _quantity_label(quantity):
    return {"reference_normalized_ratio": "Ratio Q = S/R",
            "sequential_blank_absorbance": "Absorbance\n(sequential blank)",
            "calibrated_absorbance": "Calibrated absorbance A",
            "raw_sample_signal": "Sample signal"}.get(quantity, str(quantity).replace("_", " "))


class SlowScanSettingsWidget(QWidget):
    """One visible acquisition form; connected values supply independent Auto fields."""

    changed = Signal()
    HF_OVERRIDE_ROWS = (("Time constant (s)", "time_constant_s", "reference_time_constant_s"),
                        ("Filter order", "filter_order", "reference_filter_order"),
                        ("Sampling rate (Sa/s)", "requested_sample_rate_hz", "requested_reference_sample_rate_hz"))
    AUTO_FIELDS = (("repetition_rate_hz", "Repetition rate (Hz)", 1.),
                   ("pulse_width_s", "Pulse width (ns)", 1e-9),
                   ("current_ma", "Current (mA)", 1.))

    def __init__(self, mode, parent=None):
        super().__init__(parent)
        from .settings import SlowScanSettings
        self.mode, self._applying = mode, False
        self._base = SlowScanSettings(mode=mode).to_dict()
        self.fields = self.override_inputs = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        run_group = QGroupBox("Run Label")
        run_form = QFormLayout(run_group)
        run_form.setContentsMargins(4, 0, 4, 0)
        run_form.setVerticalSpacing(0)
        run_group.setMaximumHeight(46)
        self.plan_label = QLineEdit()
        self.plan_label.setPlaceholderText("Optional")
        self.plan_label.textChanged.connect(self._changed)
        run_form.addRow("Run Label", self.plan_label)
        layout.addWidget(run_group)
        group = QGroupBox("MIRcat Settings")
        form = QFormLayout(group)
        form.setContentsMargins(4, 4, 4, 4)
        form.setVerticalSpacing(0)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.laser_mode = QComboBox()
        self.laser_mode.setObjectName("laser_mode")
        self.laser_mode.addItem("Pulsed", "pulsed")
        self.laser_mode.addItem("Continuous Wave", "cw")
        self.laser_mode.currentIndexChanged.connect(self._laser_mode_changed)
        form.addRow("Mode", self.laser_mode)
        self.lower, self.upper = QDoubleSpinBox(), QDoubleSpinBox()
        self.start, self.end = self.upper, self.lower
        for editor, name in ((self.lower, "lower_cm1"), (self.upper, "upper_cm1")):
            editor.setObjectName(name)
            editor.setDecimals(3)
            editor.setRange(1639., 2077.)
            editor.setSuffix(" cm⁻¹")
            editor.setKeyboardTracking(False)
            editor.valueChanged.connect(self._changed)
        form.addRow("Start", self.start)
        form.addRow("Stop", self.end)
        self.scan_speed = QDoubleSpinBox()
        self.scan_speed.setObjectName("requested_scan_speed_cm1_s")
        self.scan_speed.setDecimals(3)
        self.scan_speed.setRange(.1, 10000.)
        self.scan_speed.setSuffix(" cm⁻¹/s")
        self.scan_speed.setKeyboardTracking(False)
        self.scan_speed.valueChanged.connect(self._changed)
        form.addRow("Scan speed", self.scan_speed)
        for key, label, _scale in self.AUTO_FIELDS:
            editor = QLineEdit()
            editor.setObjectName(key)
            editor.setPlaceholderText("Auto")
            editor.textChanged.connect(self._changed)
            self.fields[key] = editor
            if key in ("current_ma", "pulse_width_s"):
                from control_app.measurement_host.laser_settings import constrain_mircat_control
                constrain_mircat_control(editor, "current" if key == "current_ma" else "width")
            form.addRow(label, editor)
        self.repeats = QSpinBox()
        self.repeats.setObjectName("replicates")
        self.repeats.setRange(1, 8192)
        self.repeats.valueChanged.connect(self._changed)
        self.repeats.setToolTip("Total number of descending scans from Start to Stop.")
        form.addRow("Number of Scans", self.repeats)
        self.advanced_widget = QWidget()
        filter_form = QGridLayout(self.advanced_widget)
        filter_form.setContentsMargins(0, 0, 0, 0)
        filter_form.setHorizontalSpacing(4)
        filter_form.setVerticalSpacing(1)
        first_row = 1 if mode == "dual" else 0
        if mode == "dual":
            for column, label in ((1, "Sample"), (2, "Reference")):
                heading = QLabel(label)
                heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
                filter_form.addWidget(heading, 0, column)
                filter_form.setColumnStretch(column, 1)
        for offset, (label, sample_key, reference_key) in enumerate(self.HF_OVERRIDE_ROWS):
            row = first_row + offset
            filter_form.addWidget(QLabel(label), row, 0)
            keys = (sample_key, reference_key) if mode == "dual" else (sample_key,)
            for column, key in enumerate(keys, start=1):
                editor = HF2LIValueInput()
                editor.setObjectName(key)
                editor.currentTextChanged.connect(self._changed)
                self.fields[key] = editor
                filter_form.addWidget(editor, row, column)
        layout.addWidget(group)
        self.apply_settings(self._base)

    def _changed(self, *_):
        if not self._applying:
            self.changed.emit()

    def _laser_mode_changed(self, *_):
        pulsed = self.laser_mode.currentData() == "pulsed"
        self.fields["current_ma"].setPlaceholderText("1000" if pulsed else "750")
        for name in ("pulse_width_s",):
            self.fields[name].setEnabled(pulsed)
        if not self._applying:
            self.fields["current_ma"].setText("1000" if pulsed else "750")
            self.changed.emit()

    def read_settings(self):
        from .settings import SlowScanSettings
        values = deepcopy(self._base)
        values.update(mode=self.mode, hardware=True, lower_cm1=self.lower.value(), upper_cm1=self.upper.value(),
                      plan_label=self.plan_label.text().strip(), requested_scan_speed_cm1_s=self.scan_speed.value(),
                      replicates=self.repeats.value(), laser_mode=self.laser_mode.currentData())
        scales = {key: scale for key, _label, scale in self.AUTO_FIELDS}
        for key, editor in self.fields.items():
            text = editor.text().strip()
            if values["laser_mode"] == "cw" and key == "pulse_width_s":
                try:
                    values[key] = None if not text or text.casefold() == "auto" else float(text) * scales[key]
                except ValueError:
                    values[key] = self._base[key]
                continue
            values[key] = (None if not text or text.casefold() == "auto" else int(text) if key.endswith("filter_order")
                           else float(text) * scales.get(key, 1.))
        if values["laser_mode"] == "pulsed" and values["repetition_rate_hz"] is not None and values["pulse_width_s"] is not None:
            if values["repetition_rate_hz"] * values["pulse_width_s"] > .30 + 1e-12:
                raise ValueError("Pulse duty must be 30% or less")
        return SlowScanSettings.from_dict(values).to_dict()

    def apply_settings(self, settings):
        from .settings import SlowScanSettings
        data = settings.to_dict() if hasattr(settings, "to_dict") else deepcopy(settings)
        if data.get("mode", self.mode) != self.mode:
            raise ValueError(f"Plan detector mode differs from this {self.mode} tab")
        data = SlowScanSettings.from_dict(data).to_dict()
        self._applying = True
        try:
            self._base = data
            self.laser_mode.setCurrentIndex(self.laser_mode.findData(data["laser_mode"]))
            self._laser_mode_changed()
            self.plan_label.setText(data.get("plan_label", ""))
            self.lower.setValue(data["lower_cm1"])
            self.upper.setValue(data["upper_cm1"])
            self.scan_speed.setValue(data.get("requested_scan_speed_cm1_s") or 40.)
            self.repeats.setValue(data["replicates"])
            scales = {key: scale for key, _label, scale in self.AUTO_FIELDS}
            for key, editor in self.fields.items():
                value = data.get(key)
                precision = ".17g" if key in ("requested_sample_rate_hz", "requested_reference_sample_rate_hz") else "g"
                editor.setText("" if value is None else format(value / scales.get(key, 1.), precision))
        finally:
            self._applying = False
        self.changed.emit()


class SpectrumPlotAdapter:
    """Render only observed support; sorting and gap markers never interpolate."""

    def draw(self, figure, selection):
        spectrum = selection["spectrum"]
        fit = selection.get("fit")
        native = _value(spectrum, "native")
        x = np.asarray(_value(spectrum, "axis_cm1"), dtype=float)
        view = selection.get("view", "normalized")
        if view == "sample":
            y, label = _value(native, "sample"), "Sample detector (native units)"
            x = np.asarray(_value(native, "axis_cm1"), dtype=float)
        elif view == "reference":
            y, label = _value(native, "reference"), "Reference detector (native units)"
            x = np.asarray(_value(native, "axis_cm1"), dtype=float)
        else:
            mode = _value(native, "mode")
            fields = {"normalized": ("signal", _quantity_label(_value(spectrum, "quantity", "Signal"))),
                      "ratio": ("ratio", "Reference-normalized ratio Q = S/R" if mode == "dual" else "Sequential blank-normalized ratio S/blank"),
                      "absorbance": ("absorbance", "Calibrated absorbance A = −log₁₀(Q/B)" if mode == "dual" else "Matched-blank absorbance A = −log₁₀(S/blank)"),
                      "delta": ("delta_absorbance", "ΔA = −log₁₀(Q/Q₀)")}
            field, label = fields.get(view, fields["normalized"])
            y = _value(spectrum, field)
        axes = figure.add_subplot(211 if fit is not None and view == "normalized" else 111)
        axes.set(xlabel="Wavenumber (cm⁻¹)", ylabel=str(label))
        if y is None:
            missing = ("No matched blank was used for this sample."
                       if view in ("ratio", "absorbance") and _value(native, "mode") == "single"
                       else "No matching reference data for this quantity.")
            axes.text(.5, .5, missing,
                      ha="center", va="center", transform=axes.transAxes, wrap=True)
            return
        y = np.asarray(y, dtype=float)
        valid = np.asarray(_value(spectrum, "valid", np.ones(x.size)), dtype=bool)
        if view in ("sample", "reference"):
            native_valid = _value(native, "valid")
            valid = np.ones(x.size, dtype=bool) if native_valid is None else np.asarray(native_valid, dtype=bool)
        elif view in ("ratio", "delta"):
            provenance = _value(spectrum, "provenance", {})
            valid = np.asarray(provenance.get("ratio_valid" if view == "ratio" else "delta_absorbance_valid", valid), dtype=bool)
        indices = np.argsort(x, kind="stable")
        sx, sy = x[indices], np.where(valid, y, np.nan)[indices]
        gaps = np.flatnonzero(np.diff(sx) > 3 * np.median(np.diff(np.unique(sx)))) + 1 if len(np.unique(sx)) > 2 else []
        # Every declared absent interval is shown as a break, never a bridge.
        axes.plot(np.insert(sx, gaps, np.nan), np.insert(sy, gaps, np.nan), label="Observed", linewidth=1)
        if fit is not None and view == "normalized":
            fitted = np.asarray(_value(fit, "fitted"), dtype=float)
            baseline = np.asarray(_value(fit, "baseline"), dtype=float)
            axes.plot(np.insert(sx, gaps, np.nan), np.insert(np.where(valid, fitted, np.nan)[indices], gaps, np.nan), label="Fit", linewidth=1)
            axes.plot(np.insert(sx, gaps, np.nan), np.insert(np.where(valid, baseline, np.nan)[indices], gaps, np.nan), label="Baseline", linestyle=":")
            residual_axes = figure.add_subplot(212, sharex=axes)
            residuals = np.asarray(_value(fit, "residuals"), dtype=float)
            residual_axes.plot(np.insert(sx, gaps, np.nan),
                               np.insert(np.where(valid, residuals, np.nan)[indices], gaps, np.nan), linewidth=1)
            residual_axes.axhline(0, color="grey", linewidth=.5)
            residual_axes.set(xlabel="Wavenumber (cm⁻¹)", ylabel="Residual")
            axes.set_xlabel("")
            axes.tick_params(labelbottom=False)
        comparison = selection.get("comparison")
        if comparison is not None and view == "normalized":
            cx = np.asarray(_value(comparison, "axis_cm1"))
            cy = np.asarray(_value(comparison, "signal"))
            cv = np.asarray(_value(comparison, "valid"), dtype=bool)
            order = np.argsort(cx, kind="stable")
            ordered = cx[order]
            gaps = np.flatnonzero(np.diff(ordered) > 3 * np.median(np.diff(np.unique(ordered)))) + 1 if len(np.unique(ordered)) > 2 else []
            axes.plot(np.insert(ordered, gaps, np.nan), np.insert(np.where(cv, cy, np.nan)[order], gaps, np.nan), label="Pre-exposure state", alpha=.65)
        for key, color in (("band", "tab:green"), ("offband", "tab:orange")):
            bounds = selection.get(key)
            if bounds and bounds[0] < bounds[1]:
                axes.axvspan(*bounds, color=color, alpha=.10, label=key)
        coordinate = selection.get("coordinate")
        if coordinate is not None:
            axes.axvline(coordinate, color="grey", linestyle="--", linewidth=.7)
        axes.legend(loc="best", fontsize="small")
        axes.invert_xaxis()
        figure.tight_layout()


class SlowScanPanel(CompactMeasurementPanel):
    """Compact range-to-spectrum presentation on the shared host lifecycle."""

    def __init__(self, context, parent=None):
        from .adapter import SlowScanScientificAdapter
        settings = SlowScanSettingsWidget(context.mode)
        adapter = SlowScanScientificAdapter(context, settings)
        self._displayed = self._comparison = None
        self._clock_start = None
        super().__init__(settings, adapter, context, parent, advanced_widget=settings.advanced_widget)
        self.settings_editor = settings
        self.settings_layout.setContentsMargins(6, 6, 6, 6)
        self.settings_layout.setSpacing(2)
        self.settings_layout.setContentsMargins(2, 2, 2, 2)
        self.left_layout.setSpacing(4)
        self.settings_extras_layout.setSpacing(2)
        self.advanced_layout.setContentsMargins(4, 4, 4, 4)
        self.advanced_group.setTitle("HF2LI Settings")
        self.file_layout.setDirection(QBoxLayout.Direction.LeftToRight)
        self.preliminary_button.hide()
        self.start_button.setText("Sample")
        self.abort_button.setText("Stop")
        self.load_run_button.setText("Load run…")
        self.blank_button = self.add_blank_action("Blank", lambda: self._user_action(lambda: self.begin_control("blank")))
        self.load_blank_button = self.add_blank_action("Load blank…", lambda: self._choose_control("blank"), requires_plan=False)
        if context.mode == "dual":
            self.blank_button.hide()
            self.load_blank_button.hide()
        self.control_status = QLabel("Automatic dark; acquire or load a blank to proceed." if context.mode == "single"
                                    else "Automatic dark; simultaneous reference.")
        self.control_status.setWordWrap(True)
        self.control_status.setToolTip(self.control_status.text())
        self.load_dark_button = QPushButton("Load dark…")
        device_actions = QHBoxLayout()
        device_actions.setSpacing(4)
        device_actions.addWidget(self.load_dark_button)
        self.settings_extras_layout.addLayout(device_actions)
        self.load_dark_button.clicked.connect(lambda: self._choose_control("dark"))

        selectors = QHBoxLayout()
        self.sweep_choice = QComboBox()
        self.sweep_choice.setMinimumContentsLength(12)
        self.sweep_choice.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.view_choice = QComboBox()
        self.view_choice.setMinimumContentsLength(12)
        self.view_choice.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        for label, key in (("Spectrum", "normalized"), ("Native sample", "sample"),
                           ("Native reference", "reference"), ("Ratio S/R", "ratio"),
                           ("Absorbance", "absorbance"), ("ΔA from prior sample", "delta")):
            self.view_choice.addItem(label, key)
        if context.mode == "single":
            self.view_choice.setItemText(self.view_choice.findData("ratio"), "Ratio S/blank")
            self.view_choice.setItemText(self.view_choice.findData("absorbance"), "Blank absorbance")
            self.view_choice.removeItem(self.view_choice.findData("reference"))
        selectors.addWidget(self.sweep_choice, 1)
        selectors.addWidget(self.view_choice, 1)
        self.result_layout.addLayout(selectors)
        self.spectral_slice = LinkedSliceControl([0.], label="Coordinate", unit="cm⁻¹", decimals=5)
        self.result_layout.addWidget(self.spectral_slice)
        self.plot = PlotPanel(SpectrumPlotAdapter())
        self.plot.canvas.setMinimumHeight(160)
        self.plot.setMinimumHeight(220)
        self.result_layout.addWidget(self.plot, 1)
        self.quality = QLabel("Acquire a sample or load a run to display its spectrum.")
        self.quality.setWordWrap(True)
        self.quality.setMaximumHeight(48)
        self.result_layout.addWidget(self.quality)
        self.analysis_button = QToolButton()
        self.analysis_button.setText("Selected windows")
        self.analysis_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.analysis_button.setArrowType(Qt.ArrowType.RightArrow)
        self.analysis_button.setCheckable(True)
        self.result_layout.addWidget(self.analysis_button)
        self.analysis_content = QWidget()
        analysis = QVBoxLayout(self.analysis_content)
        analysis.setContentsMargins(0, 0, 0, 0)
        self.peak_table = QTableWidget(0, 6)
        self.peak_table.setHorizontalHeaderLabels(["Center cm⁻¹", "σ center", "FWHM", "Height", "Area", "Model"])
        self.peak_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.peak_table.setMinimumHeight(75)
        self.peak_table.setMaximumHeight(100)
        self.peak_table.hide()
        analysis.addWidget(self.peak_table)
        selections = QHBoxLayout()
        self.band_lower, self.band_upper, self.offband_lower, self.offband_upper = (QLineEdit() for _ in range(4))
        for label, lower, upper in (("Band", self.band_lower, self.band_upper),
                                    ("Off-band", self.offband_lower, self.offband_upper)):
            selections.addWidget(QLabel(label))
            for editor, placeholder in ((lower, "Lower"), (upper, "Upper")):
                editor.setPlaceholderText(placeholder + " cm⁻¹")
                editor.setMinimumWidth(40)
                editor.setMaximumWidth(95)
                editor.editingFinished.connect(self.redraw)
                selections.addWidget(editor)
        analysis.addLayout(selections)
        tools = QHBoxLayout()
        self.comparison_button = QPushButton("Compare run…")
        self.selection_export = QPushButton("Export selection…")
        for button in (self.comparison_button, self.selection_export):
            tools.addWidget(button)
        analysis.addLayout(tools)
        self.analysis_content.hide()
        self.result_layout.addWidget(self.analysis_content)
        self.analysis_button.toggled.connect(self._toggle_analysis)
        self.elapsed = QLabel()
        self.elapsed.setWordWrap(True)
        self.left_layout.addWidget(self.elapsed)
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.busy_changed.connect(self._busy_update)
        self.result_ready.connect(self.display_result)
        self.run_loaded.connect(lambda result, _: self.display_result(result))
        self.operation_finished.connect(self._operation_finished)
        self.outcome_ready.connect(self._outcome)
        self.new_run_requested.connect(self._clear_display)
        self.sweep_choice.currentIndexChanged.connect(self._sweep_changed)
        self.view_choice.currentIndexChanged.connect(self.redraw)
        self.spectral_slice.index_changed.connect(self.redraw)
        self.comparison_button.clicked.connect(self._choose_comparison)
        self.selection_export.clicked.connect(lambda: self._user_action(self._export_selection_dialog))
        settings.changed.connect(self._settings_changed)
        self._update_local_controls()

    def _toggle_analysis(self, shown):
        self.analysis_content.setVisible(shown)
        self.analysis_button.setArrowType(Qt.ArrowType.DownArrow if shown else Qt.ArrowType.RightArrow)
        QTimer.singleShot(0, self.redraw)

    def _settings_changed(self):
        self.adapter.persist_preferences()
        self.refresh_plan()
        self._update_local_controls()

    def _update_local_controls(self):
        idle = not self.command_running()
        self.blank_button.setEnabled(idle and self.plan is not None)
        for button in (self.load_blank_button, self.load_dark_button):
            button.setEnabled(idle)
        for button in (self.comparison_button, self.selection_export):
            button.setEnabled(idle and self._displayed is not None)
        if hasattr(self, "control_status"):
            controls = self.adapter.controls
            description = "Dark: retained" if controls["dark"] else "Dark: automatic"
            if self.context.mode == "single":
                description += " · Blank: retained" if controls["blank"] else " · Acquire or load a blank to proceed"
            else:
                description += " · Simultaneous reference"
            self.control_status.setText(description)

    def _update_controls(self):
        super()._update_controls()
        if hasattr(self, "sample_acquisition_button"):
            self.sample_acquisition_button.setEnabled(self.start_button.isEnabled())
        if not self._busy and self.context.ownership.has_parked_session():
            self.abort_button.setEnabled(True)

    def request_abort(self, reason):
        if not self._busy and self.context.ownership.has_parked_session():
            self._launch(lambda worker: self.context.ownership.close_parked_session(), "close_prepared")
            return
        super().request_abort(reason)

    def new_run(self):
        if not self._busy and self.context.ownership.has_parked_session():
            self._launch(lambda worker: self.context.ownership.close_parked_session(), "close_prepared_new_run")
            return
        super().new_run()

    def begin_control(self, kind):
        if kind == "blank" and self.context.mode != "single":
            raise ValueError("Dual mode records the reference simultaneously")
        self.begin_operation(kind, self.adapter.run_control, requires_valid_plan=kind != "capability")

    def _operation_finished(self, kind, outcome):
        self._completion_label = {"completed": "Completed", "cancelled": "Stopped"}.get(outcome.state, "Failed")
        if kind == "blank" and outcome.state == "failed":
            self.status.setText(f"Blank failed: {outcome.error}")
            if self.adapter.controls["blank"] is None:
                self.status.setText(self.status.text() + "\nNo completed blank is available; sample acquisition remains disabled.")
        if kind == "close_prepared_new_run" and outcome.state == "completed":
            super().new_run()
        if outcome.state == "completed":
            try:
                if kind in ("dark", "blank", "capability", "load_dark", "load_blank"):
                    self.adapter.accept_control(kind.removeprefix("load_"), outcome.result)
                elif kind == "load_comparison":
                    self._comparison = outcome.result
                    self.redraw()
                elif kind in ("measurement", "preliminary", "load_run"):
                    self.adapter.accept_result(outcome.result)
                self.refresh_plan()
                if kind == "blank" and outcome.result.get("prepared_session", {}).get("warning"):
                    self.status.setText("Blank saved. Sample will reconnect; prepared session unavailable.")
                    self.status.setToolTip(str(outcome.result["prepared_session"]["warning"]))
            except Exception as exc:
                self.status.setText(str(exc))
        self._update_local_controls()

    def _outcome(self, outcome):
        if outcome.state == "cancelled":
            self.status.setText("Stopped. Partial data and cleanup results were retained.")

    def _choose_control(self, role):
        path = QFileDialog.getExistingDirectory(self, f"Load {role}", str(self.save_root_provider()))
        if path:
            self.load_control(path, role)

    def load_control(self, path, role):
        self.begin_operation("load_" + role,
            lambda _snapshot, worker: self.adapter.load_control(Path(path), role, worker), requires_valid_plan=False)

    def output_location_changed(self, path):
        if not self.command_running():
            self.status.setText("Save location updated for the next run.")
            self.status.setToolTip(str(path))

    def instrument_state_changed(self, change):
        self.adapter.invalidate_instrument_state(change.reason)
        self.refresh_plan()

    def _busy_update(self, busy):
        if busy:
            self._clock_start = time.monotonic()
            self._completion_label = "Finished"
        self._tick()
        self._update_local_controls()

    def _tick(self):
        if self._clock_start is None:
            return
        elapsed = time.monotonic() - self._clock_start
        estimate = self.adapter.estimated_seconds(self.plan)
        if not self.command_running():
            self.elapsed.setText(f"{self._completion_label} in {elapsed:.1f} s, including cleanup and saving.")
            self._clock_start = None
            return
        from control_app.measurement_host.experiment_summary import remaining_text
        remaining = " · " + remaining_text(estimate, elapsed)
        self.elapsed.setText(f"Elapsed {elapsed:.1f} s{remaining}")

    def display_result(self, result):
        self._displayed = result
        self.adapter.accept_result(result)
        self.sweep_choice.blockSignals(True)
        self.sweep_choice.clear()
        for index, spectrum in enumerate(result.get("spectra", ())):
            native = _value(spectrum, "native")
            label = f"{_value(native, 'segment_id', '')} · {_value(native, 'direction', '')} · repeat {_value(native, 'replicate', '')}"
            self.sweep_choice.addItem(label, index)
        self.sweep_choice.blockSignals(False)
        self._sweep_changed()
        self._update_local_controls()

    def _sweep_changed(self, *_):
        if not self._displayed or self.sweep_choice.currentIndex() < 0:
            return
        spectrum = self._displayed["spectra"][self.sweep_choice.currentIndex()]
        values = [float(v) for v in _value(spectrum, "axis_cm1") if math.isfinite(float(v))]
        if values:
            self.spectral_slice.set_coordinates(values)
        self.redraw()

    def _bounds(self, lower, upper):
        try:
            values = float(lower.text()), float(upper.text())
            return values if all(math.isfinite(v) for v in values) else None
        except ValueError:
            return None

    def redraw(self, *_):
        if not self._displayed or self.sweep_choice.currentIndex() < 0:
            return
        index = self.sweep_choice.currentIndex()
        spectrum = self._displayed["spectra"][index]
        fit = _fit_for_spectrum(self._displayed, spectrum)
        comparison = None
        comparison_fit = None
        if self._comparison:
            native = _value(spectrum, "native")
            for candidate in self._comparison.get("spectra", ()):
                other = _value(candidate, "native")
                if all(_value(native, key) == _value(other, key) for key in ("segment_id", "direction", "replicate")):
                    comparison = candidate
                    comparison_fit = _fit_for_spectrum(self._comparison, candidate)
                    break
        self.plot.set_result({"spectrum": spectrum, "fit": fit,
                              "view": self.view_choice.currentData(), "comparison": comparison,
                              "coordinate": self.spectral_slice.input.value(),
                              "band": self._bounds(self.band_lower, self.band_upper),
                              "offband": self._bounds(self.offband_lower, self.offband_upper)})
        peaks = _value(fit, "peaks", ()) if fit is not None else ()
        self.analysis_button.setText("Peaks and selected windows" if fit is not None else "Selected windows")
        self.peak_table.setVisible(fit is not None)
        self.peak_table.setRowCount(len(peaks))
        for row, peak in enumerate(peaks):
            for column, key in enumerate(("center_cm1", "center_uncertainty_cm1", "width_fwhm_cm1", "height", "integrated_area", "line_shape")):
                value = _value(peak, key, _value(_value(fit, "settings"), key, ""))
                self.peak_table.setItem(row, column, QTableWidgetItem(f"{value:.6g}" if isinstance(value, (int, float)) else str(value)))
        flags = list(_value(spectrum, "flags", ())) + list(_value(fit, "flags", ()) if fit else ())
        self.quality.setText(f"Quantity: {_quantity_label(_value(spectrum, 'quantity', 'unknown')).replace(chr(10), ' ')}. " +
                             ("Quality flags: " + "; ".join(map(str, flags)) if flags else "No reported quality flags.") +
                             " Individual directions and replicates retained. Full uncertainty and overlap covariance are preserved in native/exported fit records.")
        comparisons = self._displayed.get("quality", {}).get("comparisons", ())
        rms = [row["rms_difference"] for row in comparisons if row.get("rms_difference") is not None]
        drift = [abs(row["apparent_drift_per_s"]) for row in comparisons if row.get("apparent_drift_per_s") is not None]
        if rms:
            self.quality.setText(self.quality.text() + f" Across recorded sweeps: maximum matched RMS difference {max(rms):.5g}" +
                                 (f", maximum absolute apparent drift {max(drift):.5g}/s." if drift else ". Drift rate unresolved."))
        if comparison_fit is not None and fit is not None:
            from .processing import compare_states
            try:
                comparison_result = compare_states(comparison_fit, fit)
                rows = comparison_result.get("peaks", ())
                summary = "; ".join(f"component {row['component']}: center shift {row['center_shift_cm1']:.5g} ± "
                                    f"{row['center_shift_uncertainty_cm1']:.3g} cm⁻¹, width change {row['width_change_cm1']:.5g} cm⁻¹, "
                                    f"fractional area change {row['area_fraction_change']}" for row in rows)
                self.quality.setText(self.quality.text() + " Pre/post comparison: " + summary +
                                     ". Component correspondence remains an analysis assumption.")
            except ValueError as exc:
                self.quality.setText(self.quality.text() + f" Pre/post comparison unavailable: {exc}")
        detail = self.quality.text()
        labels = []
        for fragment, label in (("axis_uncalibrated", "Axis uncalibrated"),
                                ("uncertainty", "Uncertainty limited"),
                                ("correlated_residuals", "Structured residuals")):
            if any(fragment in str(flag) for flag in flags):
                labels.append(label)
        quantity = _quantity_label(_value(spectrum, "quantity", "unknown")).replace("\n", " ")
        self.quality.setText(" · ".join([quantity, *labels]) + (" · Comparison loaded" if comparison is not None else ""))
        self.quality.setToolTip(detail)

    def _choose_comparison(self):
        path = QFileDialog.getExistingDirectory(self, "Compare saved run", str(self.save_root_provider()))
        if path:
            displayed = deepcopy(self._displayed)
            self.begin_operation("load_comparison",
                lambda _snapshot, worker: self.adapter.load_comparison(Path(path), displayed, worker), requires_valid_plan=False)

    def selected_windows(self):
        windows = []
        for label, lower, upper in (("band", self.band_lower, self.band_upper),
                                    ("off-band", self.offband_lower, self.offband_upper)):
            if not lower.text().strip() and not upper.text().strip():
                continue
            bounds = self._bounds(lower, upper)
            if bounds is None or bounds[0] >= bounds[1]:
                raise ValueError(f"Enter a numeric {label} range with Lower below Upper")
            peaks = ()
            if label == "band":
                index = self.sweep_choice.currentIndex()
                spectra = self._displayed.get("spectra", ()) if self._displayed else ()
                fit = _fit_for_spectrum(self._displayed, spectra[index]) if 0 <= index < len(spectra) else None
                if fit is not None:
                    peaks = tuple(peak for peak in _value(fit, "peaks", ())
                                  if bounds[0] <= _value(peak, "center_cm1") <= bounds[1])
            if peaks:
                windows.extend({"lower_cm1": bounds[0], "upper_cm1": bounds[1],
                                "center_cm1": _value(peak, "center_cm1"),
                                "uncertainty_cm1": _value(peak, "center_uncertainty_cm1"),
                                "label": f"Fitted band component {_value(peak, 'component')}"} for peak in peaks)
            else:
                windows.append({"lower_cm1": bounds[0], "upper_cm1": bounds[1], "label": label})
        if not windows:
            raise ValueError("Enter a band or off-band range to export")
        return windows

    def _export_selection_dialog(self):
        windows = self.selected_windows()
        path, _ = QFileDialog.getSaveFileName(self, "Export selection", str(self.save_root_provider()), "JSON (*.json)")
        if path:
            self.export_selection(path, windows)

    def export_selection(self, path, windows=None):
        if self._displayed is None:
            raise ValueError("Acquire or load a spectrum before exporting a selection")
        result = deepcopy(self._displayed)
        windows = deepcopy(self.selected_windows() if windows is None else windows)
        self.begin_operation("export_selection",
            lambda _snapshot, worker: self.adapter.export_selection(Path(path), result, windows, worker), requires_valid_plan=False)

    def _clear_display(self):
        self._displayed = self._comparison = None
        self.sweep_choice.clear()
        self.plot.clear_result()
        self.peak_table.setRowCount(0)
        self.peak_table.hide()
        self.analysis_button.setText("Selected windows")
        self.quality.setText("Acquire a sample or load a run to display its spectrum.")
        for field in (self.band_lower, self.band_upper, self.offband_lower, self.offband_upper):
            field.clear()
        self._update_local_controls()


def make_handle(context, *, title):
    panel = SlowScanPanel(context)
    return TabHandle(instance_id=context.instance_id, title=title, widget=panel,
                     command_running=panel.command_running, close_blockers=panel.close_blockers,
                     request_abort=panel.request_abort, output_location_changed=panel.output_location_changed,
                     instrument_state_changed=panel.instrument_state_changed, state_changed=panel.busy_changed)
