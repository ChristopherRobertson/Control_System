"""Two isolated top-level tabs using only the frozen host presentation API."""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import time

import numpy as np
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QScrollArea, QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from control_app.measurement_host import TabHandle
from control_app.measurement_host.presentation import (
    GuidedMeasurementPanel, LinkedSliceControl, PlotPanel, StartSnapshot,
)
from .scientific_adapter import NanosecondScientificAdapter
from .settings import Settings


class NanosecondSettingsWidget(QWidget):
    """Concise primary controls plus editable supported scientific overrides."""

    changed = Signal()
    PROFILE_IDS = ("RT-HRP-G", "RT-Mb-G", "77K-HRP-G-F", "77K-Mb-G-F")
    FIELD_LABELS = {
        "sample_id": "Sample identity", "preparation_id": "Preparation identity",
        "cell_id": "Cell / path identity", "position_ids": "Position identities (comma separated)",
        "wavenumbers_cm1": "Measured wavenumbers (cm⁻¹)", "delays_ns": "Requested delays (ns)",
        "selected_populations": "Quantified sample populations", "conditions": "Control conditions",
        "temperature_k": "Measured sample temperature (K)",
        "temperature_uncertainty_k": "Temperature uncertainty (K)",
        "repetitions": "Technical repetitions", "reset_interval_s": "Equivalent-state reset interval (s)",
        "irf_sigma_ns": "IRF σ (ns)", "timing_jitter_ns": "Timing jitter σ (ns)",
        "integration_aperture_ns": "Optical integration aperture (ns)",
        "noise_sd": "Predicted detector noise SD",
    }

    def __init__(self, mode, preferences, parent=None):
        super().__init__(parent)
        self.mode, self.preferences = mode, preferences
        self.controls = {}
        self._values = Settings(mode=mode).to_dict()
        saved = preferences.value("settings_json", "")
        if saved:
            try:
                restored = Settings.from_dict(json.loads(saved)).to_dict()
                if restored["mode"] == mode:
                    self._values = restored
            except (ValueError, TypeError, KeyError):
                pass  # A malformed preference never blocks fresh planning.
        layout = QVBoxLayout(self)
        note = QLabel("EXAMPLE ONLY: simulator values are editable planning examples. "
                      "Connected operation requires promoted, configuration-specific evidence. "
                      "A numerical delay step is not the measured temporal resolution.")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.execution = QComboBox()
        self.execution.addItems(["simulation", "connected"])
        self.profile = QComboBox()
        self.profile.addItems(self.PROFILE_IDS)
        form.addRow("Execution", self.execution)
        form.addRow("Condition profile", self.profile)
        self.controls.update(execution_mode=self.execution, profile_id=self.profile)
        for key, label in self.FIELD_LABELS.items():
            if key not in self._values:
                continue
            value = self._values[key]
            if key == "repetitions":
                control = QSpinBox()
                control.setRange(1, 1000000)
                control.valueChanged.connect(self._changed)
            elif isinstance(value, (float, int)) and not isinstance(value, bool):
                control = QDoubleSpinBox()
                control.setRange(0, 1e12)
                control.setDecimals(9 if key == "noise_sd" else 6)
                control.setKeyboardTracking(False)
                control.valueChanged.connect(self._changed)
            else:
                control = QLineEdit()
                control.editingFinished.connect(self._changed)
            self.controls[key] = control
            form.addRow(label, control)
        layout.addLayout(form)
        advanced = QGroupBox("Advanced scientific settings (versioned JSON)")
        advanced_layout = QVBoxLayout(advanced)
        self.advanced = QPlainTextEdit()
        self.advanced.setMinimumHeight(150)
        self.advanced.setToolTip("Edit supported Settings fields, then Apply. Unknown or incompatible values produce explicit planning errors.")
        self.apply_advanced_button = QPushButton("Apply advanced settings")
        self.advanced_status = QLabel()
        self.advanced_status.setWordWrap(True)
        advanced_layout.addWidget(self.advanced)
        advanced_layout.addWidget(self.apply_advanced_button)
        advanced_layout.addWidget(self.advanced_status)
        layout.addWidget(advanced)
        layout.addStretch()
        self.apply_settings(self._values)
        self.execution.currentTextChanged.connect(self._changed)
        self.profile.currentTextChanged.connect(self._changed)
        self.apply_advanced_button.clicked.connect(self._apply_advanced)

    def _changed(self, *_):
        try:
            values = self.read_settings()
            self.preferences.setValue("settings_json", json.dumps(values))
            self.advanced.setPlainText(json.dumps(values, indent=2))
        except (ValueError, TypeError):
            pass
        self.changed.emit()

    def read_settings(self):
        values = deepcopy(self._values)
        for key, control in self.controls.items():
            if isinstance(control, QComboBox):
                value = control.currentText()
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                value = control.value()
            else:
                value = control.text().strip()
                if key in ("temperature_k", "temperature_uncertainty_k"):
                    value = float(value) if value else None
                elif isinstance(self._values[key], (list, tuple)):
                    value = [item.strip() for item in value.split(",") if item.strip()]
                    if key in ("wavenumbers_cm1", "delays_ns"):
                        value = [float(item) for item in value]
            values[key] = value
        values["mode"] = self.mode
        return Settings.from_dict(values).to_dict()

    def apply_settings(self, values):
        values = Settings.from_dict(values).to_dict()
        if values["mode"] != self.mode:
            raise ValueError("Settings detector mode differs from this tab")
        self._values = deepcopy(values)
        for key, control in self.controls.items():
            control.blockSignals(True)
            value = values[key]
            if isinstance(control, QComboBox):
                control.setCurrentText(str(value))
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                control.setValue(value)
            else:
                control.setText(", ".join(map(str, value)) if isinstance(value, (list, tuple)) else ("" if value is None else str(value)))
            control.blockSignals(False)
        self.advanced.setPlainText(json.dumps(values, indent=2))
        self.preferences.setValue("settings_json", json.dumps(values))

    def _apply_advanced(self):
        try:
            self.apply_settings(json.loads(self.advanced.toPlainText()))
            self.advanced_status.clear()
            self.changed.emit()
        except Exception as exc:
            self.advanced_status.setText(str(exc))


class NanosecondPlotAdapter:
    """Native support, reconstruction and actual nearest slices; no gap filling."""

    def __init__(self):
        self.time_index = 0
        self.wavenumber_index = 0
        self.quantity = "delta_a"
        self.condition = "pump_on"

    def draw(self, figure, run):
        reconstructed = run.get("result") or {}
        if self.condition != "pump_on":
            control = reconstructed.get("controls", {}).get(self.condition, {})
            reconstructed = {**reconstructed, **control, "fits": [], "uncertainty": [], "optical_delay_ns": []}
        waves = np.asarray(reconstructed.get("wavenumbers_cm1", []), dtype=float)
        delays = np.asarray(reconstructed.get("delays_ns", []), dtype=float)
        data = np.asarray(reconstructed.get(self.quantity, []), dtype=float)
        native = figure.add_subplot(224)
        events = run.get("events", [])
        samples, references = [], []
        for event in events:
            samples.append(_native_mean(event, "sample"))
            references.append(_native_mean(event, "reference"))
        native.plot(samples, ".", markersize=2, label="HF2LI sample")
        if any(np.isfinite(references)):
            native.plot(references, ".", markersize=2, label="HF2LI reference")
        native.set(xlabel="Retained native event index", ylabel="Native detector signal", title="Native records (including rejected)")
        if events:
            native.legend(fontsize=7)
        if not waves.size or not delays.size or data.shape != (waves.size, delays.size):
            from .processing import spectral_observable
            quantity = "Q0 = unpumped S/R" if run.get("mode") == "dual" else "Unpumped HF2LI sample signal"
            observables = [spectral_observable(event, run.get("mode", "single"))["value"] for event in events]
            axes = figure.add_subplot(211)
            axes.plot([event.get("wavenumber_cm1", np.nan) for event in events], observables, ".")
            axes.set(xlabel="Measured wavenumber (cm⁻¹)", ylabel=quantity,
                     title="Preliminary / native data; reconstructed optical support unavailable")
            figure.subplots_adjust(hspace=.65, wspace=.4, bottom=.13)
            return
        ti = min(self.time_index, delays.size - 1)
        wi = min(self.wavenumber_index, waves.size - 1)
        dual = run.get("mode") == "dual"
        label = {"delta_a": "ΔA = −log₁₀(Q/Q₀)" if dual else "ΔA = −log₁₀(S/S₀)",
                 "ratio": "Reference-normalized Q = S/R" if dual else "HF2LI sample signal",
                 "absolute_absorbance": "Absolute absorbance (measured B required)",
                 "coverage": "Accepted matched observations"}[self.quantity]
        surface = figure.add_subplot(221)
        image = surface.pcolormesh(delays, waves, np.ma.masked_invalid(data), shading="nearest", cmap="viridis")
        figure.colorbar(image, ax=surface, pad=.02)
        surface.axvline(delays[ti], color="white", linewidth=.6)
        surface.axhline(waves[wi], color="white", linewidth=.6)
        surface.set(xlabel="Quantized command delay bin (ns)", ylabel="Wavenumber (cm⁻¹)", title=label)
        spectrum = figure.add_subplot(222)
        spectrum.plot(waves, data[:, ti], ".-")
        spectrum.set(xlabel="Wavenumber (cm⁻¹)", ylabel=label,
                     title=f"Local spectrum at {delays[ti]:g} ns")
        spectrum.invert_xaxis()
        kinetic = figure.add_subplot(223)
        optical = np.asarray(reconstructed.get("optical_delay_ns", []), dtype=float)
        kinetic_delays = optical[wi] if optical.shape == data.shape else delays
        kinetic.plot(kinetic_delays, data[wi], ".-", label="Measured")
        kinetic.set(xlabel="Calibrated optical delay (ns)" if optical.shape == data.shape else "Quantized command delay bin (ns)", ylabel=label,
                    title=f"Point kinetics at {waves[wi]:g} cm⁻¹")
        uncertainty = np.asarray(reconstructed.get("uncertainty", []), dtype=float)
        if self.quantity == "delta_a" and uncertainty.shape == data.shape:
            kinetic.fill_between(kinetic_delays, data[wi] - uncertainty[wi], data[wi] + uncertainty[wi], alpha=.2)
            fit = next((item for item in reconstructed.get("fits", []) if item.get("wavenumber_cm1") == waves[wi]), {})
            if fit.get("predicted"):
                kinetic.plot(fit.get("supported_delay_ns", []), fit["predicted"], "--", label="IRF-convolved fit")
                kinetic.legend(fontsize=7)
        figure.subplots_adjust(hspace=.75, wspace=.6, bottom=.13, top=.9)


def _native_mean(event, role):
    stream = event.get(role, event.get("native", {}).get(role, {}))
    if isinstance(stream, dict):
        value = stream.get("value", stream.get("values", stream.get("r", stream.get("x", np.nan))))
    elif stream is None:
        return np.nan
    else:
        value = stream
    try:
        array = np.asarray(value, dtype=float)
        return float(np.mean(array)) if array.size else np.nan
    except (ValueError, TypeError):
        return np.nan


class NanosecondPanel(GuidedMeasurementPanel):
    """Single blank or dual Q0 workflow, with independently invalidated review."""

    def __init__(self, context, parent=None):
        self._candidate_preliminary = None
        self._next_root = None
        self._started = None
        settings = NanosecondSettingsWidget(context.mode, context.preferences)
        adapter = NanosecondScientificAdapter(context, settings)
        super().__init__(settings, adapter, context, parent)
        splitter = self.findChild(QSplitter)
        summary_box = splitter.widget(1)
        summary_layout = summary_box.layout()
        summary_layout.removeWidget(self.summary)
        summary_layout.removeWidget(self.validation)
        self._summary_scroll = QScrollArea(summary_box)
        self._summary_scroll.setWidgetResizable(True)
        self._summary_contents = QWidget()
        details_layout = QVBoxLayout(self._summary_contents)
        details_layout.addWidget(self.summary)
        details_layout.addWidget(self.validation)
        details_layout.addStretch()
        self._summary_scroll.setWidget(self._summary_contents)
        summary_layout.insertWidget(0, self._summary_scroll, 1)
        self.save_root_provider = lambda: self._next_root or self.context.save_root()
        settings.changed.connect(self.refresh_plan)
        self.blank_status = QLabel()
        self.blank_status.setWordWrap(True)
        self.acquire_blank_button = QPushButton("1 · Acquire complete blank/control")
        self.load_blank_button = QPushButton("Load blank/control…")
        self.load_preliminary_button = QPushButton("Load preliminary / Q0…")
        self.load_selection_button = QPushButton("Load accepted spectral selection…")
        self.load_calibration_button = QPushButton("Load promoted bundle")
        self.bundle_id = QLineEdit()
        self.bundle_id.setPlaceholderText("Promoted instrument bundle ID")
        self.simulation_button = QPushButton("Evaluate schedule (simulation)")
        self.plan_details_button = QPushButton("View complete frame/channel plan")
        preview_row = QHBoxLayout()
        preview_row.addWidget(self.simulation_button)
        preview_row.addWidget(self.plan_details_button)
        self.layout().insertLayout(2, preview_row)
        actions = QHBoxLayout()
        if context.mode == "single":
            actions.addWidget(self.acquire_blank_button)
            actions.addWidget(self.load_blank_button)
            self.preliminary_button.setText("2 · Acquire sample preliminary (pump OFF)")
        else:
            self.acquire_blank_button.hide()
            self.load_blank_button.hide()
            self.preliminary_button.setText("1 · Acquire sample + reference Q0 (pump OFF)")
        actions.addWidget(self.load_preliminary_button)
        actions.addWidget(self.load_selection_button)
        self.layout().insertLayout(2, actions)
        self.layout().insertWidget(3, self.blank_status)
        bundle_row = QHBoxLayout()
        bundle_row.addWidget(self.bundle_id)
        bundle_row.addWidget(self.load_calibration_button)
        self.layout().insertLayout(4, bundle_row)
        self.start_button.setText("Start pumped reconstruction")
        self.abort_button.setText("Abort acquisition")
        self.elapsed = QLabel("Elapsed 0 s · remaining estimate includes preparation, reset, restoration and analysis.")
        self.layout().insertWidget(self.layout().count() - 1, self.elapsed)
        self.plot_adapter = NanosecondPlotAdapter()
        self.plot = PlotPanel(self.plot_adapter)
        self.quantity = QComboBox()
        self.quantity.addItem("ΔAbsorbance", "delta_a")
        self.quantity.addItem("Reference-normalized signal Q" if context.mode == "dual" else "HF2LI sample signal", "ratio")
        self.quantity.addItem("Coverage", "coverage")
        self.plot.toolbar.addWidget(self.quantity)
        self.condition = QComboBox()
        self.condition.addItem("Pump on", "pump_on")
        self.plot.toolbar.addWidget(self.condition)
        self.time_slice = LinkedSliceControl(label="Command delay bin selects spectrum", unit="ns", decimals=2)
        self.wavenumber_slice = LinkedSliceControl(label="Wavenumber selects kinetics", unit="cm⁻¹", decimals=4)
        self.result_note = QLabel()
        self.result_note.setWordWrap(True)
        self.result_layout.addWidget(self.result_note)
        self.result_layout.addWidget(self.plot)
        self.result_layout.addWidget(self.time_slice)
        self.result_layout.addWidget(self.wavenumber_slice)
        self.time_slice.index_changed.connect(self._slice_changed)
        self.wavenumber_slice.index_changed.connect(self._slice_changed)
        self.quantity.currentIndexChanged.connect(self._quantity_changed)
        self.condition.currentIndexChanged.connect(self._condition_changed)
        self.result_ready.connect(self.show_result)
        self.run_loaded.connect(lambda result, _path: self.show_result(result))
        self.plot.error.connect(self.status.setText)
        self.acquire_blank_button.clicked.connect(lambda: self._user_action(self.begin_blank))
        self.load_blank_button.clicked.connect(lambda: self._choose_reference("blank"))
        self.load_preliminary_button.clicked.connect(lambda: self._choose_reference("preliminary"))
        self.load_selection_button.clicked.connect(self._choose_selection)
        self.load_calibration_button.clicked.connect(lambda: self._user_action(self.load_bundle))
        self.simulation_button.clicked.connect(lambda: self._user_action(self.evaluate_schedule))
        self.plan_details_button.clicked.connect(lambda: self._user_action(self.show_plan_details))
        self.new_run_requested.connect(self._clear_results)
        self.busy_changed.connect(self._busy_transition)
        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(250)
        self.clock_timer.timeout.connect(self._elapsed)
        self._update_controls()

    def refresh_plan(self, *_):
        if self._busy:
            return
        self._candidate_preliminary = self.preliminary or self._candidate_preliminary
        super().refresh_plan()
        if self.plan is not None:
            errors = self.adapter.selection_conflicts(self.adapter.read_settings())
            if self.adapter.blank:
                errors += self.adapter.compatibility(self.adapter.blank, self.plan, kind="blank")
            if self._candidate_preliminary:
                conflicts = self.adapter.validate_review(self._candidate_preliminary, self.plan)
                errors += conflicts
                if not conflicts:
                    self.preliminary = self._candidate_preliminary
                    self.review_summary.setText(self.adapter.summarize_preliminary(self.preliminary))
            self.validation.setText("\n".join(dict.fromkeys(errors)))
        self._update_controls()

    def _update_controls(self, *_):
        super()._update_controls()
        if not hasattr(self, "blank_status"):
            return
        idle, valid = not self._busy, self.plan is not None
        if self.context.mode == "single":
            conflicts = self.adapter.compatibility(self.adapter.blank, self.plan, kind="blank") if valid else ["A valid plan is required."]
            self.preliminary_button.setEnabled(idle and valid and not conflicts)
            self.blank_status.setText("Sequential blank/control: " + ("complete and compatible. Load the sample before preliminary acquisition." if not conflicts else "; ".join(conflicts[:3])))
        else:
            self.blank_status.setText("Keep matched buffer/matrix in the reference path. The preliminary records simultaneous S, R and unpumped Q0.")
        if self.preliminary is not None and valid:
            self.start_button.setEnabled(idle and self.review.isChecked() and not self.adapter.validate_review(self.preliminary, self.plan))
        for button in (self.acquire_blank_button, self.load_blank_button, self.load_preliminary_button,
                       self.load_selection_button, self.load_calibration_button,
                       self.simulation_button, self.plan_details_button):
            button.setEnabled(idle and valid)
        self.bundle_id.setEnabled(idle)

    def begin(self, kind):
        if kind == "preliminary" and self.context.mode == "single":
            conflicts = self.adapter.compatibility(self.adapter.blank, self.plan, kind="blank")
            if conflicts:
                raise ValueError("Acquire/load a compatible complete sequential blank first: " + "; ".join(conflicts))
        if kind == "measurement" and self.preliminary is not None:
            conflicts = self.adapter.validate_review(self.preliminary, self.plan)
            if conflicts:
                self.review.setChecked(False)
                self.validation.setText("\n".join(conflicts))
                return
        self.adapter.freeze_inputs()
        super().begin(kind)

    def begin_blank(self):
        if self.context.mode != "single" or self._busy or self.plan is None:
            raise ValueError("A valid idle single-detector plan is required")
        self.review.setChecked(False)
        self.preliminary = self._candidate_preliminary = None
        self.adapter.freeze_inputs()
        selected = self.adapter.selected_records()
        operation = self.context.begin_operation(
            plan=self._host_plan, calibration_records=selected.calibration_records,
            sample_records=selected.sample_records,
            hardware=self.adapter.hardware_required("blank", self._host_plan.settings),
            purpose="blank", cancel=self.request_abort,
        )
        snapshot = StartSnapshot(operation, "blank", deepcopy(self.plan), None)
        self.snapshot = snapshot
        def run(worker):
            if operation.hardware:
                with self.context.hardware_scope(operation):
                    return self.adapter.run_blank(snapshot, worker)
            return self.adapter.run_blank(snapshot, worker)
        try:
            self._launch(run, "blank")
        except Exception:
            if operation.hardware and not (self.worker and self.worker.isRunning()):
                self.context.ownership.release(operation.ownership, safe_verified=True, preservation_verified=True,
                                               detail="Blank dispatch failed before hardware access")
            raise

    def _finished(self, worker, kind, path):
        presentation_error = None
        try:
            self._finish_scientific_presentation(worker, kind)
        except Exception as exc:
            presentation_error = f"Scientific display failed: {type(exc).__name__}: {exc}"
        finally:
            super()._finished(worker, kind, path)
        if self.preliminary is not None and self.plan is not None:
            conflicts = self.adapter.validate_review(self.preliminary, self.plan)
            self.validation.setText("\n".join(conflicts))
        if presentation_error:
            self.status.setText(presentation_error)

    def _finish_scientific_presentation(self, worker, kind):
        if self.worker is worker and worker.outcome.state == "completed":
            if kind in ("blank", "load_blank"):
                self.adapter.blank = worker.outcome.result
                self.preliminary = self._candidate_preliminary = None
                self.review.setChecked(False)
                self.show_result(worker.outcome.result)
            elif kind in ("preliminary", "load_preliminary"):
                self.preliminary = self._candidate_preliminary = worker.outcome.result
                self.review.setChecked(False)
                self.review_summary.setText(self.adapter.summarize_preliminary(worker.outcome.result))
                self.validation.clear()
                self.show_result(worker.outcome.result)
            elif kind == "simulation_preview":
                simulation = worker.outcome.result
                bias = simulation.get("relative_bias")
                self.result_note.setText(
                    f"Prospective known-truth simulation: {simulation['resolved_fraction']:.0%} resolved across "
                    f"{simulation['trials']} trials; interval coverage {simulation['interval_coverage']:.0%}; "
                    + (f"relative bias {bias:.1%}. " if bias is not None else "No resolved lifetime estimates. ")
                    + "This is conditional on entered IRF/noise/reset assumptions and does not grant commissioning or review approval.\n"
                    + simulation["output_path"]
                )
        elif self.worker is worker and kind in ("blank", "preliminary", "measurement"):
            if self.adapter.last_result:
                self.result = self.adapter.last_result
                self.show_result(self.result)
    def evaluate_schedule(self):
        if self._busy or self.plan is None:
            raise ValueError("A valid idle plan is required for prospective simulation")
        operation = self.context.begin_operation(plan=self._host_plan, hardware=False,
                                                  purpose="prospective simulation", cancel=self.request_abort)
        plan = deepcopy(self.plan)
        self._launch(lambda worker: self.adapter.evaluate_schedule(operation, plan, worker), "simulation_preview")

    def show_plan_details(self):
        if self.plan is None:
            raise ValueError("A valid plan is required")
        dialog = QDialog(self)
        dialog.setWindowTitle("Nanosecond plan — every event, frame and channel")
        dialog.resize(900, 650)
        layout = QVBoxLayout(dialog)
        label = QLabel("Deterministic requested/quantized electrical plan only. Native observations and optical delay calibration are recorded during acquisition. Save Plan preserves this complete schedule.")
        label.setWordWrap(True)
        layout.addWidget(label)
        content = QPlainTextEdit()
        content.setReadOnly(True)
        content.setPlainText(json.dumps(self.plan.to_dict(), indent=2))
        layout.addWidget(content)
        dialog.show()
        self._plan_dialog = dialog

    def load_reference(self, path, kind):
        if kind not in ("blank", "preliminary") or (kind == "blank" and self.context.mode != "single"):
            raise ValueError("Unsupported baseline kind for this detector mode")
        plan = deepcopy(self.plan)
        def load(_worker):
            result = self.adapter.load_run(Path(path))
            conflicts = self.adapter.compatibility(result, plan, kind=kind)
            if conflicts:
                raise ValueError("Incompatible baseline: " + "; ".join(conflicts))
            return result
        self._launch(load, "load_" + kind, path)

    def _choose_reference(self, kind):
        path = QFileDialog.getExistingDirectory(self, "Load compatible " + kind, str(self.save_root_provider()))
        if path:
            self._user_action(lambda: self.load_reference(path, kind))

    def _choose_selection(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load accepted sample spectral selection", str(self.save_root_provider()), "JSON (*.json)")
        if path:
            self._user_action(lambda: self.load_selection(Path(path)))

    def load_selection(self, path):
        from control_app.measurement_host.interchange import load_sample_selection
        record = load_sample_selection(path)
        settings = self.adapter.read_settings()
        if settings["sample_id"] and record.sample_id != settings["sample_id"]:
            raise ValueError("Spectral selection sample identity differs from entered sample")
        if settings["condition_id"] and record.condition_id != settings["condition_id"]:
            raise ValueError("Spectral selection condition identity differs from entered condition")
        settings["sample_id"] = record.sample_id
        settings["condition_id"] = record.condition_id
        settings["sample_selection_id"] = record.selection_id
        selected = record.to_dict()
        for name, value in selected["condition"].items():
            if name in settings:
                if settings[name] not in (None, "", (), []) and settings[name] != value:
                    raise ValueError(f"Spectral selection condition.{name} differs from entered condition")
                settings[name] = value
        if not all(any(window.lower_cm1 <= wave <= window.upper_cm1 for window in record.windows)
                   for wave in settings["wavenumbers_cm1"]):
            centers = [window.center_cm1 for window in record.windows]
            if any(center is None for center in centers):
                raise ValueError("Select measured wavelengths inside the accepted windows; no measured centers were supplied")
            settings["wavenumbers_cm1"] = tuple(dict.fromkeys(centers))
        settings["qualification"] = {**settings["qualification"], "spectral_selection_accepted": True}
        self.adapter.sample_records = [selected]
        self.adapter.apply_settings(settings)
        self.refresh_plan()
        self.status.setText("Accepted sample selection loaded. Review selected measured wavelengths and condition applicability.")

    def load_bundle(self):
        bundle_id = self.bundle_id.text().strip()
        if not bundle_id:
            raise ValueError("Enter an applicable promoted instrument bundle ID")
        bundle = self.context.promoted_bundle(bundle_id)
        manifest = bundle.manifest if hasattr(bundle, "manifest") else bundle.get("manifest", bundle)
        payload = manifest.get("nanosecond_stroboscopy")
        if not isinstance(payload, dict) or not isinstance(payload.get("settings_domain"), dict):
            raise ValueError("Promoted bundle lacks a nanosecond_stroboscopy settings_domain")
        domain = payload["settings_domain"]
        settings = self.adapter.read_settings()
        if domain.get("experiment_id", "nanosecond_stroboscopy") != "nanosecond_stroboscopy":
            raise ValueError("Promoted bundle experiment identity differs")
        if domain.get("mode", self.context.mode) != self.context.mode:
            raise ValueError("Promoted bundle detector mode differs")
        identities = {"sample_id", "condition_id", "preparation_id", "cell_id", "matrix_id", "day_id",
                      "position_ids", "sample_selection_id", "temperature_record_id"}
        for name in identities:
            if settings.get(name) and domain.get(name) not in (None, settings[name], list(settings[name]) if isinstance(settings[name], tuple) else settings[name]):
                raise ValueError(f"Promoted bundle domain {name} differs from entered sample/condition identity")
        for name, value in domain.items():
            if name in settings and name not in identities | {"mode", "execution_mode", "qualification", "calibration_ids"}:
                settings[name] = value
        qualifications = dict(settings["qualification"])
        qualifications.update(payload.get("qualification", {}))
        qualifications.update({name: value for name, value in payload.items() if name.endswith("_qualified")})
        aliases = {"selected_probe_qualified": "pulse_selection_qualified",
                   "sparse_reference_lock_qualified": "reference_lock_qualified",
                   "impulse_area_qualified": "hf2li_impulse_qualified",
                   "optical_timing_qualified": "irf_qualified"}
        for source, target in aliases.items():
            if source in payload:
                qualifications[target] = payload[source]
        settings["qualification"] = qualifications
        settings["calibration_ids"] = tuple(dict.fromkeys((*settings["calibration_ids"], bundle_id)))
        conflicts = self.adapter.selection_conflicts(settings)
        if conflicts:
            raise ValueError("Promoted domain conflicts with selected sample: " + "; ".join(conflicts))
        self.adapter.calibration_records.append(bundle)
        self.adapter.apply_settings(settings)
        self.preliminary = self._candidate_preliminary = None
        self.adapter.blank = None
        self.refresh_plan()
        self.status.setText("Promoted bundle loaded; reacquire compatible baseline and preliminary records before review.")

    def show_result(self, result):
        reconstructed = result.get("result") or {}
        command_step = float(result.get("settings", {}).get("timing_step_ns", .01))
        if command_step > 0:
            self.time_slice.input.setDecimals(max(0, min(9, math.ceil(-math.log10(command_step)))))
        previous_condition = self.condition.currentData()
        self.condition.blockSignals(True)
        self.condition.clear()
        self.condition.addItem("Pump on", "pump_on")
        for condition in reconstructed.get("controls", {}):
            self.condition.addItem(condition.replace("_", " ").title(), condition)
        self.condition.setCurrentIndex(max(0, self.condition.findData(previous_condition)))
        self.condition.blockSignals(False)
        self.plot_adapter.condition = self.condition.currentData()
        self.time_slice.set_coordinates(reconstructed.get("delays_ns", []))
        self.wavenumber_slice.set_coordinates(reconstructed.get("wavenumbers_cm1", []))
        absolute_index = self.quantity.findData("absolute_absorbance")
        if reconstructed.get("absolute_available", False) and absolute_index < 0:
            self.quantity.addItem("Absolute absorbance (measured balance B)", "absolute_absorbance")
        elif not reconstructed.get("absolute_available", False) and absolute_index >= 0:
            self.quantity.removeItem(absolute_index)
        self.plot_adapter.time_index = self.time_slice.index
        self.plot_adapter.wavenumber_index = self.wavenumber_slice.index
        self.plot.set_result(result)
        self._condition_changed()
        fit_notes = [f"{item['wavenumber_cm1']:g} cm⁻¹: {item.get('outcome', 'unresolved')}" +
                     (f", τ = {item['lifetime_ns']:.3g} ns" if item.get("lifetime_ns") is not None else "")
                     + (f", 95% interval {item['lifetime_interval_ns'][0]:.3g}–{item['lifetime_interval_ns'][1]:.3g} ns" if item.get("lifetime_interval_ns") else "")
                     + (" (" + "; ".join(item.get("reasons", [])) + ")" if item.get("reasons") else "")
                     for item in reconstructed.get("fits", [])]
        populations = reconstructed.get("population_analysis")
        if populations:
            fit_notes.append("Sample-population analysis: " + str(populations.get("point_comparison", {}).get("outcome", "retained")))
        self.result_note.setText(
            f"{result.get('status', 'loaded')} · {result.get('output_path', '')}\n"
            "Native gaps and exclusions are preserved. Delay bins are displayed in ns; "
            "calibrated optical coordinates and measured IRF determine time resolution. "
            "Q is reference-normalized signal; absolute absorbance requires a sequential blank or applicable measured B.\n" +
            "; ".join(fit_notes)
        )

    def _slice_changed(self, *_):
        self.plot_adapter.time_index = self.time_slice.index
        self.plot_adapter.wavenumber_index = self.wavenumber_slice.index
        if self.plot.result is not None:
            self.plot.reset_view()

    def _quantity_changed(self, *_):
        self.plot_adapter.quantity = self.quantity.currentData()
        if self.plot.result is not None:
            self.plot.reset_view()

    def _condition_changed(self, *_):
        self.plot_adapter.condition = self.condition.currentData()
        control_selected = self.plot_adapter.condition != "pump_on"
        for index in range(self.quantity.count()):
            self.quantity.model().item(index).setEnabled(not control_selected or self.quantity.itemData(index) in ("delta_a", "coverage"))
        if control_selected and self.quantity.currentData() not in ("delta_a", "coverage"):
            self.quantity.setCurrentIndex(self.quantity.findData("delta_a"))
        if self.plot.result is not None:
            self.plot.reset_view()

    def _clear_results(self):
        self._candidate_preliminary = None
        self.plot.clear_result()
        self.time_slice.set_coordinates([])
        self.wavenumber_slice.set_coordinates([])
        self.result_note.clear()

    def new_run(self):
        self._candidate_preliminary = None
        super().new_run()

    def instrument_state_changed(self, change):
        details = self.adapter.note_instrument_change(change)
        self.review.setChecked(False)
        if not self._busy:
            self.refresh_plan()
        self.status.setText("Preliminary review invalidated by instrument change: " + details)

    def output_location_changed(self, path):
        self._next_root = Path(path)
        # The host owns the root provider; an active operation keeps its frozen
        # output_path. This value is only for the next file selection dialog.

    def _busy_transition(self, busy):
        if busy:
            self._started = time.monotonic()
            self.clock_timer.start()
        else:
            self._elapsed()
            self.clock_timer.stop()

    def _elapsed(self):
        elapsed = 0 if self._started is None else time.monotonic() - self._started
        budget = self.plan.budget if self.plan else {}
        estimate = next((budget[key] for key in ("total_s", "wall_time_s", "wall_clock_s", "estimated_wall_time_s", "wall_seconds") if key in budget), None)
        remaining = "0 s (operation finished)" if not self._busy else (f"{max(0, float(estimate) - elapsed):.1f} s" if estimate is not None else "stage-dependent")
        self.elapsed.setText(f"Elapsed {elapsed:.1f} s · estimated remaining {remaining}. Basis: planned preparation, tuning, controls, reset, acquisition and final processing; simulation may execute faster.")


def make_handle(context, *, title):
    panel = NanosecondPanel(context)
    return TabHandle(
        instance_id=context.instance_id, title=title, widget=panel,
        command_running=panel.command_running, close_blockers=panel.close_blockers,
        request_abort=panel.request_abort, output_location_changed=panel.output_location_changed,
        instrument_state_changed=panel.instrument_state_changed, state_changed=panel.busy_changed,
    )
