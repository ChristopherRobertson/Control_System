"""Spectrum-first scientific presentation using the frozen measurement host."""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import time

import numpy as np
from PySide6.QtCore import QTimer, Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget, QFileDialog, QPlainTextEdit, QDialog, QSplitter, QScrollArea,
)

from control_app.measurement_host import TabHandle
from control_app.measurement_host.presentation import (
    GuidedMeasurementPanel, LinkedSliceControl, PlotPanel, StartSnapshot,
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
    """Editable scientific values; blank overrides resolve from qualified profiles."""

    changed = Signal()
    PROFILES = (("Room temperature HRP–CO", "rt_hrp_co"),
                ("Room temperature MbCO", "rt_mbco"),
                ("77 K HRP–CO", "77k_hrp_co"), ("77 K MbCO", "77k_mbco"))
    IDENTITY_FIELDS = (
        ("sample_id", "Sample ID"), ("preparation_id", "Preparation ID"),
        ("cell_id", "Cell / reload ID"), ("position_id", "Illuminated position ID"),
        ("temperature_id", "Temperature condition ID"), ("matrix_id", "Matrix / buffer ID"),
        ("configuration_id", "Configuration ID"), ("temperature_k", "Observed temperature (K)"),
        ("temperature_uncertainty_k", "Temperature uncertainty (K)"),
        ("temperature_record_id", "Temperature observation record"),
        ("pH", "Measured pH"), ("state_id", "Sample state ID"),
        ("exposure_history_id", "Exposure history record"),
        ("cell_reload_id", "Cell reload ID"), ("lot_id", "Material lot ID"),
        ("state_verification_id", "Independent state verification record"),
        ("thermal_history_id", "Thermal history / cooling record"),
    )
    NUMERIC_FIELDS = (
        ("requested_resolution_cm1", "Requested resolution (cm⁻¹)"),
        ("measured_linewidth_cm1", "Measured line width (cm⁻¹)"),
        ("requested_scan_speed_cm1_s", "Scan speed override (cm⁻¹/s)"),
        ("sample_rate_hz", "HF2LI native rate override (Hz/channel)"),
        ("time_constant_s", "HF2LI time constant override (s)"),
        ("filter_order", "HF2LI filter order override"),
        ("replicates", "Technical replicates, each direction"),
        ("settle_s", "Tune / filter settling override (s)"),
        ("marker_interval_cm1", "Native marker interval override (cm⁻¹)"),
        ("marker_width_s", "Marker width override (s)"),
        ("probe_rate_hz", "Probe rate override (Hz)"),
        ("probe_width_s", "Probe width override (s)"),
        ("process_pulse_width_s", "Process trigger width override (s)"),
        ("dark_duration_s", "Dark observation duration override (s)"),
        ("fit_peak_count", "Prospective component count"),
        ("fit_baseline_degree", "Baseline polynomial degree"),
    )
    INTEGERS = {"filter_order", "replicates", "fit_peak_count", "fit_baseline_degree"}

    def __init__(self, mode, parent=None):
        super().__init__(parent)
        from .settings import SlowScanSettings
        self.mode = mode
        self._applying = False
        self._profiles = {}
        self._previous_profile = "rt_hrp_co"
        self._base = SlowScanSettings(mode=mode).to_dict()
        self.fields = {}
        layout = QVBoxLayout(self)
        notice = QLabel("Unpumped steady-state spectra. FIRE and Q-switch remain OFF. "
                        "Blank numeric overrides use the applicable characterized operating profile.")
        notice.setWordWrap(True)
        layout.addWidget(notice)

        identity = QGroupBox("Sample and condition")
        form = QFormLayout(identity)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.condition = QComboBox()
        for title, key in self.PROFILES:
            self.condition.addItem(title, key)
        form.addRow("Condition profile", self.condition)
        for key, title in self.IDENTITY_FIELDS:
            editor = QLineEdit()
            editor.setObjectName(key)
            editor.textChanged.connect(self._changed)
            self.fields[key] = editor
            form.addRow(title, editor)
        self.equilibrated = QCheckBox("Condition equilibrated; temperature evidence entered above")
        self.equilibrated.toggled.connect(self._changed)
        form.addRow(self.equilibrated)
        layout.addWidget(identity)

        geometry = QGroupBox("Measurement and declared QCL segments")
        form = QFormLayout(geometry)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.purpose = QComboBox()
        for label, key in (("Survey", "survey"), ("Local high-quality spectrum", "local_spectrum"),
                           ("Short state verification", "state_verification"),
                           ("Pre/post-exposure comparison", "pre_post_comparison")):
            self.purpose.addItem(label, key)
        self.purpose.currentIndexChanged.connect(self._changed)
        form.addRow("Purpose", self.purpose)
        self.plan_label = QLineEdit()
        self.plan_label.textChanged.connect(self._changed)
        form.addRow("Plan label", self.plan_label)
        self.segments = QTableWidget(0, 4)
        self.segments.setHorizontalHeaderLabels(["Segment ID", "QCL", "Lower cm⁻¹", "Upper cm⁻¹"])
        self.segments.setMinimumHeight(125)
        self.segments.cellChanged.connect(self._changed)
        form.addRow(self.segments)
        row = QHBoxLayout()
        add = QPushButton("Add segment")
        remove = QPushButton("Remove selected segment")
        add.clicked.connect(lambda: self.add_segment())
        remove.clicked.connect(self.remove_segment)
        row.addWidget(add)
        row.addWidget(remove)
        form.addRow(row)
        layout.addWidget(geometry)

        acquisition = QGroupBox("Resolution, acquisition and fit settings")
        form = QFormLayout(acquisition)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        for key, title in self.NUMERIC_FIELDS:
            editor = QLineEdit()
            editor.setObjectName(key)
            editor.setPlaceholderText("Automatic from applicable evidence")
            editor.textChanged.connect(self._changed)
            self.fields[key] = editor
            form.addRow(title, editor)
        self.line_shape = QComboBox()
        self.line_shape.addItems(["gaussian", "lorentzian"])
        self.line_shape.currentTextChanged.connect(self._changed)
        form.addRow("Prospective line shape", self.line_shape)
        self.fringes = QLineEdit()
        self.fringes.setPlaceholderText("Optional measured periods, comma separated (cm⁻¹)")
        self.fringes.textChanged.connect(self._changed)
        form.addRow("Fringe periods (cm⁻¹)", self.fringes)
        self.hardware = QCheckBox("Use connected instruments (exclusive instrument ownership)")
        self.hardware.toggled.connect(self._changed)
        form.addRow(self.hardware)
        layout.addWidget(acquisition)

        profile = QGroupBox("Qualified operating profile")
        form = QFormLayout(profile)
        self.bundle_ids = QLineEdit()
        self.bundle_ids.setPlaceholderText("Promoted bundle IDs, comma separated")
        self.bundle_ids.textChanged.connect(self._changed)
        form.addRow("Promoted bundle IDs", self.bundle_ids)
        self.load_profile_button = QPushButton("Load promoted operating profile")
        self.capability_button = QPushButton("Read connected capabilities")
        form.addRow(self.load_profile_button)
        form.addRow(self.capability_button)
        layout.addWidget(profile)
        layout.addStretch()
        self.apply_settings(self._base)
        self.condition.currentIndexChanged.connect(self._switch_profile)

    def _changed(self, *_):
        if not self._applying:
            self.changed.emit()

    def _identity(self):
        values = {key: editor.text().strip() for key, editor in self.fields.items()
                  if key in dict(self.IDENTITY_FIELDS)}
        for key in ("temperature_k", "temperature_uncertainty_k", "pH"):
            values[key] = float(values[key]) if values[key] else None
        values["condition_id"] = self.condition.currentData()
        return values

    def _switch_profile(self, *_):
        if self._applying:
            return
        # Retain independent identities when switching protein/temperature profiles.
        self._profiles[self._previous_profile] = {
            key: self.fields[key].text() for key, _ in self.IDENTITY_FIELDS}
        selected = self.condition.currentData()
        values = self._profiles.get(selected, {"state_id": "initial"})
        self._applying = True
        for key, _ in self.IDENTITY_FIELDS:
            self.fields[key].setText(str(values.get(key, "")))
        self.equilibrated.setChecked(False)
        self._previous_profile = selected
        self._applying = False
        self.changed.emit()

    def add_segment(self, values=None):
        row = self.segments.rowCount()
        self.segments.insertRow(row)
        values = values or {"segment_id": f"segment-{row + 1}", "qcl": "", "lower_cm1": "", "upper_cm1": ""}
        for column, key in enumerate(("segment_id", "qcl", "lower_cm1", "upper_cm1")):
            self.segments.setItem(row, column, QTableWidgetItem(str(values.get(key, ""))))
        self._changed()

    def remove_segment(self):
        row = self.segments.currentRow()
        if row >= 0:
            self.segments.removeRow(row)
            self._changed()

    def read_settings(self):
        from .settings import SlowScanSettings
        values = deepcopy(self._base)
        values.update(mode=self.mode, condition=self._identity(), purpose=self.purpose.currentData(),
                      hardware=self.hardware.isChecked(), condition_equilibrated=self.equilibrated.isChecked(),
                      plan_label=self.plan_label.text().strip(),
                      calibration_bundle_ids=[v.strip() for v in self.bundle_ids.text().split(",") if v.strip()],
                      fit_line_shape=self.line_shape.currentText(),
                      fit_fringe_periods_cm1=[float(v.strip()) for v in self.fringes.text().split(",") if v.strip()])
        values["segments"] = []
        for row in range(self.segments.rowCount()):
            cells = [self.segments.item(row, column).text().strip() if self.segments.item(row, column) else ""
                     for column in range(4)]
            values["segments"].append({"segment_id": cells[0], "qcl": int(cells[1]),
                                       "lower_cm1": float(cells[2]), "upper_cm1": float(cells[3])})
        for key, _ in self.NUMERIC_FIELDS:
            text = self.fields[key].text().strip()
            values[key] = (int(text) if key in self.INTEGERS else float(text)) if text else None
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
            condition = data["condition"]
            self.condition.setCurrentIndex(self.condition.findData(condition["condition_id"]))
            self._previous_profile = condition["condition_id"]
            for key, _ in self.IDENTITY_FIELDS:
                value = condition.get(key)
                self.fields[key].setText("" if value is None else str(value))
            for key, _ in self.NUMERIC_FIELDS:
                value = data.get(key)
                self.fields[key].setText("" if value is None else str(value))
            self.purpose.setCurrentIndex(max(0, self.purpose.findData(data["purpose"])))
            self.plan_label.setText(data.get("plan_label", ""))
            self.hardware.setChecked(data.get("hardware", False))
            self.equilibrated.setChecked(data.get("condition_equilibrated", False))
            self.bundle_ids.setText(", ".join(data.get("calibration_bundle_ids", ())))
            self.line_shape.setCurrentText(data.get("fit_line_shape", "gaussian"))
            self.fringes.setText(", ".join(str(v) for v in data.get("fit_fringe_periods_cm1", ())))
            self.segments.setRowCount(0)
            for segment in data["segments"]:
                self.add_segment(segment)
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
            axes.text(.5, .5, "This quantity has no applicable calibration / reference support",
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


class SlowScanPanel(GuidedMeasurementPanel):
    """Guided physical staging and independent scientific session for one mode."""

    def __init__(self, context, parent=None):
        from .adapter import SlowScanScientificAdapter
        settings = SlowScanSettingsWidget(context.mode)
        adapter = SlowScanScientificAdapter(context, settings)
        self._displayed = None
        self._comparison = None
        self._instrument_mismatch = ""
        self._clock_start = None
        super().__init__(settings, adapter, context, parent)
        self.settings_editor = settings
        self.preliminary_button.setText("Acquire sample preliminary")
        self.start_button.setText("Start unpumped slow scan")
        self.abort_button.setText("Abort")

        controls = QGroupBox("Physical staging and controls")
        row = QVBoxLayout(controls)
        self.physical_stage = QComboBox()
        stages = [("Select the physically installed optical state", ""),
                  ("Both optical paths blocked for detector dark", "dark")]
        if context.mode == "single":
            stages += [("Matched blank / matrix / cryostat cell in place", "blank")]
        stages += [("Sample in place" + ("; matched-buffer reference in reference arm" if context.mode == "dual" else ""), "sample")]
        for label, key in stages:
            self.physical_stage.addItem(label, key)
        self.physical_confirm = QCheckBox("I confirm this physical state; pump remains inhibited")
        self.control_status = QLabel("Acquire or load a compatible dark" +
                                     (" and sequential blank." if context.mode == "single" else ". Sample/reference will be simultaneous."))
        self.control_status.setWordWrap(True)
        row.addWidget(self.physical_stage)
        row.addWidget(self.physical_confirm)
        buttons = QHBoxLayout()
        self.dark_button = QPushButton("Acquire dark")
        self.load_dark_button = QPushButton("Load dark…")
        self.blank_button = QPushButton("Acquire matched blank")
        self.load_blank_button = QPushButton("Load matched blank…")
        for button in (self.dark_button, self.load_dark_button):
            buttons.addWidget(button)
        if context.mode == "single":
            buttons.addWidget(self.blank_button)
            buttons.addWidget(self.load_blank_button)
        row.addLayout(buttons)
        row.addWidget(self.control_status)
        self.layout().insertWidget(1, controls)
        self.control_widget = controls
        self.dark_button.clicked.connect(lambda: self._user_action(lambda: self.begin_control("dark")))
        self.blank_button.clicked.connect(lambda: self._user_action(lambda: self.begin_control("blank")))
        self.load_dark_button.clicked.connect(lambda: self._choose_control("dark"))
        self.load_blank_button.clicked.connect(lambda: self._choose_control("blank"))
        self.physical_stage.currentIndexChanged.connect(lambda *_: self.physical_confirm.setChecked(False))
        self.physical_confirm.toggled.connect(self._physical_changed)
        settings.load_profile_button.clicked.connect(lambda: self._user_action(self.load_operating_profile))
        settings.capability_button.clicked.connect(lambda: self._user_action(lambda: self.begin_control("capability")))

        selectors = QHBoxLayout()
        self.sweep_choice = QComboBox()
        self.sweep_choice.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.sweep_choice.setMinimumContentsLength(16)
        self.view_choice = QComboBox()
        for label, key in (("Normalized spectrum", "normalized"), ("Native sample detector", "sample"),
                           ("Native reference detector", "reference"), ("Ratio Q = S/R", "ratio"),
                           ("Calibrated absorbance", "absorbance"), ("ΔA from compatible Q₀", "delta")):
            self.view_choice.addItem(label, key)
        if context.mode == "single":
            self.view_choice.setItemText(self.view_choice.findData("ratio"), "Sequential blank-normalized S/blank")
            self.view_choice.setItemText(self.view_choice.findData("absorbance"), "Matched-blank absorbance")
        self.comparison_button = QPushButton("Load pre-exposure state…")
        self.refit_button = QPushButton("Refit with entered models")
        for control in (self.sweep_choice, self.view_choice, self.comparison_button, self.refit_button):
            selectors.addWidget(control)
        self.result_layout.addLayout(selectors)
        self.plan_details_button = QPushButton("Inspect plan and frame/channel schedule")
        self.layout().insertWidget(2, self.plan_details_button)
        self.plan_details_button.clicked.connect(lambda: self._user_action(self.show_plan_details))
        self.spectral_slice = LinkedSliceControl([0.], label="Observed coordinate", unit="cm⁻¹", decimals=5)
        self.result_layout.addWidget(self.spectral_slice)
        selections = QHBoxLayout()
        self.band_lower, self.band_upper, self.offband_lower, self.offband_upper = (QLineEdit() for _ in range(4))
        for label, widget in (("Band lower", self.band_lower), ("Band upper", self.band_upper),
                              ("Off-band lower", self.offband_lower), ("Off-band upper", self.offband_upper)):
            selections.addWidget(QLabel(label + " (cm⁻¹)"))
            widget.setMaximumWidth(100)
            widget.editingFinished.connect(self.redraw)
            selections.addWidget(widget)
        self.result_layout.addLayout(selections)
        self.plot = PlotPanel(SpectrumPlotAdapter())
        self.result_layout.addWidget(self.plot, 1)
        self.peak_table = QTableWidget(0, 6)
        self.peak_table.setHorizontalHeaderLabels(["Center cm⁻¹", "σ center cm⁻¹", "FWHM cm⁻¹", "Height", "Area", "Model"])
        self.peak_table.setMaximumHeight(160)
        self.result_layout.addWidget(self.peak_table)
        self.quality = QLabel()
        self.quality.setWordWrap(True)
        self.result_layout.addWidget(self.quality)

        acceptance = QHBoxLayout()
        self.reviewer = QLineEdit()
        self.reviewer.setPlaceholderText("Named sample-state reviewer")
        self.rationale = QLineEdit()
        self.rationale.setPlaceholderText("Acceptance rationale and bounded claim")
        self.state_acceptance = QCheckBox("Accept sample state and selected windows")
        self.selection_export = QPushButton("Export accepted state record…")
        for control in (self.reviewer, self.rationale, self.state_acceptance, self.selection_export):
            acceptance.addWidget(control)
        self.result_layout.addLayout(acceptance)
        self.elapsed = QLabel("Elapsed 0.0 s; remaining estimate includes preparation, controls, restoration and processing.")
        self.elapsed.setWordWrap(True)
        self.layout().insertWidget(self.layout().count() - 1, self.elapsed)
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.busy_changed.connect(self._busy_update)
        self.result_ready.connect(self.display_result)
        self.run_loaded.connect(lambda result, _: self.display_result(result))
        self.outcome_ready.connect(self._outcome)
        self.new_run_requested.connect(self._clear_display)
        self.sweep_choice.currentIndexChanged.connect(self._sweep_changed)
        self.view_choice.currentIndexChanged.connect(self.redraw)
        self.spectral_slice.index_changed.connect(self.redraw)
        self.comparison_button.clicked.connect(self._choose_comparison)
        self.refit_button.clicked.connect(lambda: self._user_action(self.refit))
        self.selection_export.clicked.connect(self._choose_selection_export)
        settings.changed.connect(self._settings_changed)
        self._arrange_spectrum_first()
        self._update_controls()

    def _arrange_spectrum_first(self):
        """Keep the host actions, with a scrolling sidebar beside the spectrum."""
        old_splitter = self.findChild(QSplitter)
        # QScrollArea retains its managed-widget pointer across setParent().
        # Explicitly detach it so two scroll areas cannot resize the same form.
        if old_splitter is not None and isinstance(old_splitter.widget(0), QScrollArea):
            old_splitter.widget(0).takeWidget()
        self.settings_editor.setParent(None)
        for label in (self.summary, self.validation):
            label.setParent(None)
        outer = self.layout()
        while outer.count():
            outer.takeAt(0)
        if old_splitter is not None:
            old_splitter.setParent(None)
            old_splitter.deleteLater()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 4, 0)
        sidebar_layout.addWidget(self.summary)
        sidebar_layout.addWidget(self.validation)
        sidebar_layout.addWidget(self.plan_details_button)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.settings_editor)
        sidebar_layout.addWidget(scroll, 1)
        plan_files = QHBoxLayout()
        plan_files.addWidget(self.save_plan_button)
        plan_files.addWidget(self.load_plan_button)
        sidebar_layout.addLayout(plan_files)
        splitter.addWidget(sidebar)
        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(4, 0, 0, 0)
        main_layout.addWidget(self.control_widget)
        main_layout.addWidget(self.review_summary)
        main_layout.addWidget(self.review)
        actions = QHBoxLayout()
        for widget in (self.preliminary_button, self.start_button, self.abort_button, self.new_run_button):
            actions.addWidget(widget)
        main_layout.addLayout(actions)
        main_layout.addWidget(self.status)
        main_layout.addWidget(self.progress)
        main_layout.addWidget(self.elapsed)
        native_files = QHBoxLayout()
        native_files.addWidget(self.load_run_button)
        native_files.addWidget(self.export_button)
        main_layout.addLayout(native_files)
        main_layout.addLayout(self.result_layout, 1)
        splitter.addWidget(main)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([440, 1060])
        outer.addWidget(splitter)

    def _settings_changed(self):
        self._instrument_mismatch = ""
        self.adapter.persist_preferences()
        self.refresh_plan()
        self._refresh_controls_summary()
        if hasattr(self, "state_acceptance"):
            self.state_acceptance.setChecked(False)

    def _physical_changed(self):
        self.adapter.physical_controls_confirmed = self.physical_confirm.isChecked()
        self.refresh_plan()

    def refresh_plan(self, *_):
        previous_review = getattr(self, "review", None)
        had_review = previous_review is not None and previous_review.isChecked()
        super().refresh_plan()
        if had_review:
            self.review_summary.setText("Preliminary review invalidated: scientific settings, selected evidence or physical staging changed.")

    def _update_controls(self, *_):
        super()._update_controls()
        if hasattr(self, "control_widget"):
            self.control_widget.setEnabled(not self._busy)
            valid = self.plan is not None and not self._busy
            self.dark_button.setEnabled(valid)
            self.blank_button.setEnabled(valid and self.adapter.controls.get("dark") is not None)
        if hasattr(self, "selection_export"):
            for control in (self.comparison_button, self.refit_button, self.selection_export):
                control.setEnabled(not self._busy and self._displayed is not None)

    def load_operating_profile(self):
        self.adapter.load_operating_profile()
        self.refresh_plan()

    def _check_physical_stage(self, stage):
        if not self.physical_confirm.isChecked() or self.physical_stage.currentData() != stage:
            raise ValueError(f"Place the optics in the {stage} state and confirm the physical staging first")

    def begin(self, kind):
        self._check_physical_stage("sample")
        if self.plan is None:
            raise ValueError("Resolve the scientific plan before acquiring the sample")
        self.plan.require_ready(hardware=self.plan.settings.hardware)
        errors = self.adapter.control_errors(self.plan)
        if errors:
            raise ValueError("; ".join(errors))
        self._instrument_mismatch = ""
        super().begin(kind)

    def begin_control(self, kind):
        if self._busy:
            raise RuntimeError("Wait for this tab's active operation and cleanup")
        if kind != "capability":
            self._check_physical_stage(kind)
            if self.plan is None:
                raise ValueError("Resolve the scientific plan before acquiring controls")
            self.plan.require_ready(hardware=self.plan.settings.hardware)
        if kind == "blank" and self.context.mode != "single":
            raise ValueError("Dual mode records a simultaneous matched-buffer reference")
        settings = self.adapter.read_settings()
        plan = deepcopy(self.plan or self.adapter.make_plan(settings))
        selected = self.adapter.selected_records()
        host_plan = self.context.new_plan(settings)
        operation = self.context.begin_operation(
            plan=host_plan, calibration_records=selected.calibration_records,
            sample_records=selected.sample_records,
            hardware=self.adapter.hardware_required(kind, settings),
            purpose=kind, cancel=self.request_abort,
        )
        snapshot = StartSnapshot(operation, kind, plan, None)
        self.snapshot = snapshot
        def run(worker):
            if operation.hardware:
                with self.context.hardware_scope(operation):
                    return self.adapter.run_control(snapshot, worker)
            return self.adapter.run_control(snapshot, worker)
        try:
            self._launch(run, kind)
        except Exception:
            if operation.hardware and not (self.worker and self.worker.isRunning()):
                self.context.ownership.release(operation.ownership, safe_verified=True,
                                               preservation_verified=True, detail="Dispatch failed before device access")
            raise

    def _finished(self, worker, kind, path):
        if self.worker is worker and worker.outcome.state == "completed":
            if kind in ("dark", "blank", "capability"):
                try:
                    self.adapter.accept_control(kind, worker.outcome.result)
                    self.preliminary = None
                    self.review.setChecked(False)
                    self._refresh_controls_summary()
                except Exception as exc:
                    from control_app.measurement_host.presentation import WorkerOutcome
                    worker.outcome = WorkerOutcome("failed", error=str(exc))
            elif kind in ("refit", "load_comparison"):
                if kind == "refit":
                    self.result = worker.outcome.result
                    self.display_result(self.result)
                else:
                    self._comparison = worker.outcome.result
                    self.redraw()
        super()._finished(worker, kind, path)
        if kind == "preliminary" and worker.outcome.state == "completed" and self.preliminary is not None:
            self.display_result(self.preliminary)
        if kind == "capability":
            self.refresh_plan()

    def _outcome(self, outcome):
        if outcome.state == "cancelled":
            self.status.setText("Acquisition stopped. Partial data and restoration outcome retained.")

    def _refresh_controls_summary(self):
        if not hasattr(self, "control_status"):
            return
        descriptions = []
        for role in ("dark", "blank") if self.context.mode == "single" else ("dark",):
            result = self.adapter.controls.get(role)
            errors = self.adapter.compatibility_errors(result, self.plan) if result else []
            descriptions.append(f"{role}: " + ("missing" if result is None else "; ".join(errors) if errors else "compatible"))
        self.control_status.setText(" | ".join(descriptions))

    def _choose_control(self, role):
        path = QFileDialog.getExistingDirectory(self, f"Load compatible {role}", str(self.save_root_provider()))
        if path:
            self._launch(lambda worker: self.adapter.load_control(Path(path), role, worker), role)

    def request_abort(self, reason):
        if self._busy and self._active_kind in ("dark", "blank", "capability"):
            self.adapter.request_abort(reason)
        super().request_abort(reason)

    def output_location_changed(self, path):
        # Start uses context.save_root(); existing snapshots retain their root.
        self.adapter.next_output_root = Path(path)
        if not self._busy:
            self.status.setText(f"Next run save root: {path}")

    def instrument_state_changed(self, change):
        names = ", ".join(f"{item.device_id}.{item.configuration_key}" for item in change.changes)
        self._instrument_mismatch = f"Instrument state changed: {names}. {change.reason}"
        self.adapter.invalidate_instrument_state(self._instrument_mismatch)
        self.review.setChecked(False)
        self.preliminary = None
        self.review_summary.setText(self._instrument_mismatch)
        self.validation.setText(self._instrument_mismatch)
        self._refresh_controls_summary()

    def _busy_update(self, busy):
        if busy:
            self._clock_start = time.monotonic()
        self._tick()

    def _tick(self):
        if self._clock_start is None:
            return
        elapsed = time.monotonic() - self._clock_start
        estimate = self.adapter.estimated_seconds(self.plan)
        if not self._busy:
            planned = f" Planned wall-time estimate: {estimate:.1f} s." if estimate is not None else ""
            self.elapsed.setText(f"Operation finished in {elapsed:.1f} s, including cleanup and preservation.{planned}")
            self._clock_start = None
            return
        remaining = f"{max(0., estimate - elapsed):.1f} s estimated remaining" if estimate else "remaining estimate unavailable"
        self.elapsed.setText(f"Elapsed {elapsed:.1f} s; {remaining}. Basis: planned preparation, tuning/settling, controls, acquisition, retrieval, restoration and analysis.")

    def display_result(self, result):
        self._displayed = result
        self.state_acceptance.setChecked(False)
        self.sweep_choice.blockSignals(True)
        self.sweep_choice.clear()
        for index, spectrum in enumerate(result.get("spectra", ())):
            native = _value(spectrum, "native")
            label = f"{_value(native, 'segment_id', '')} / {_value(native, 'direction', '')} / replicate {_value(native, 'replicate', '')} / {_value(native, 'sweep_id', index)}"
            self.sweep_choice.addItem(label, index)
        self.sweep_choice.blockSignals(False)
        self._sweep_changed()
        self._update_controls()

    def show_plan_details(self):
        if self.plan is None:
            raise ValueError("Resolve the scientific settings to inspect the plan")
        details = self.adapter.plan_details(self.plan)
        dialog = QDialog(self)
        dialog.setWindowTitle("Requested, selected and actual values; declared frame/channel schedule")
        dialog.resize(850, 700)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(json.dumps(details, indent=2))
        layout.addWidget(text)
        self._plan_dialog = dialog
        dialog.show()

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
                                     ". Component correspondence and acceptance tolerances require review.")
            except ValueError as exc:
                self.quality.setText(self.quality.text() + f" Pre/post comparison unavailable: {exc}")

    def _choose_comparison(self):
        path = QFileDialog.getExistingDirectory(self, "Load compatible pre-exposure state", str(self.save_root_provider()))
        if path:
            self._launch(lambda worker: self.adapter.load_comparison(Path(path), self._displayed, worker), "load_comparison")

    def refit(self):
        if self._displayed is None:
            raise ValueError("Load or acquire a spectrum before refitting")
        settings, result = deepcopy(self.adapter.read_settings()), deepcopy(self._displayed)
        self._launch(lambda worker: self.adapter.refit(result, settings, worker), "refit")

    def _choose_selection_export(self):
        self._user_action(self._export_selection_dialog)

    def _export_selection_dialog(self):
        if not self.state_acceptance.isChecked():
            raise ValueError("Explicitly accept the sample state and selected windows first")
        if not self.reviewer.text().strip() or not self.rationale.text().strip():
            raise ValueError("Provide a named reviewer and the acceptance rationale")
        windows = []
        for label, lower, upper in (("band", self.band_lower, self.band_upper), ("off-band", self.offband_lower, self.offband_upper)):
            bounds = self._bounds(lower, upper)
            if bounds is None or bounds[0] >= bounds[1]:
                raise ValueError(f"Enter a valid numeric {label} window")
            fitted_peaks = ()
            if label == "band":
                index = self.sweep_choice.currentIndex()
                spectra = self._displayed.get("spectra", ())
                fit = _fit_for_spectrum(self._displayed, spectra[index]) if 0 <= index < len(spectra) else None
                if fit is not None:
                    fitted_peaks = tuple(peak for peak in _value(fit, "peaks", ())
                                         if bounds[0] <= _value(peak, "center_cm1") <= bounds[1])
            if fitted_peaks:
                for peak in fitted_peaks:
                    windows.append({"lower_cm1": bounds[0], "upper_cm1": bounds[1],
                                    "center_cm1": _value(peak, "center_cm1"),
                                    "uncertainty_cm1": _value(peak, "center_uncertainty_cm1"),
                                    "label": f"Fitted band component {_value(peak, 'component')}"})
            else:
                windows.append({"lower_cm1": bounds[0], "upper_cm1": bounds[1], "label": label})
        path, _ = QFileDialog.getSaveFileName(self, "Export accepted state record", str(self.save_root_provider()), "JSON (*.json)")
        if path:
            result = deepcopy(self._displayed)
            reviewer, rationale = self.reviewer.text().strip(), self.rationale.text().strip()
            self._launch(lambda worker: self.adapter.export_selection(Path(path), result, windows, reviewer, rationale, worker), "export_selection")

    def _clear_display(self):
        self._displayed = self._comparison = None
        self.sweep_choice.clear()
        self.plot.clear_result()
        self.peak_table.setRowCount(0)
        self.quality.clear()
        self.state_acceptance.setChecked(False)
        for field in (self.band_lower, self.band_upper, self.offband_lower, self.offband_upper):
            field.clear()
        self.physical_confirm.setChecked(False)
        self._refresh_controls_summary()


def make_handle(context, *, title):
    panel = SlowScanPanel(context)
    return TabHandle(instance_id=context.instance_id, title=title, widget=panel,
                     command_running=panel.command_running, close_blockers=panel.close_blockers,
                     request_abort=panel.request_abort, output_location_changed=panel.output_location_changed,
                     instrument_state_changed=panel.instrument_state_changed, state_changed=panel.busy_changed)
