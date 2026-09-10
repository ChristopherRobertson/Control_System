"""Two complete, independent fixed-point tabs using the frozen host presentation."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel,
    QComboBox, QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QScrollArea, QSplitter,
)

from control_app.measurement_host import TabHandle
from control_app.measurement_host.presentation import (
    GuidedMeasurementPanel, LinkedSliceControl, PlotPanel, StartSnapshot, choose_time_display,
)
from .settings import Settings
from .app_adapter import FixedPointAdapter


class SettingsEditor(QWidget):
    changed = Signal()

    def __init__(self, mode):
        super().__init__()
        self.mode, self.sample_selection = mode, None
        self.fresh_state_record = None
        self._base_data = Settings(mode=mode).to_dict()
        self.local_selection_id = "fixed-point-selection-" + uuid4().hex
        self._applying = False
        self.fields = {}
        layout = QVBoxLayout(self)
        self.execution = QComboBox()
        self.execution.addItem("Connected instruments", "connected")
        self.execution.addItem("Simulation — synthetic, no hardware", "simulation")
        layout.addWidget(self.execution)
        self.bundle = QLineEdit()
        self.bundle.setPlaceholderText("Promoted fixed-point operating bundle ID")
        layout.addWidget(self.bundle)
        self.profile_button = QPushButton("Load promoted operating profile")
        self.selection_button = QPushButton("Load accepted sample band selection…")
        self.clear_selection_button = QPushButton("Clear imported band selection")
        self.example_button = QPushButton("Use synthetic example settings")
        self.fresh_state_button = QPushButton("Load accepted fresh-state equivalence record…")
        layout.addWidget(self.profile_button)
        layout.addWidget(self.selection_button)
        layout.addWidget(self.clear_selection_button)
        layout.addWidget(self.fresh_state_button)
        layout.addWidget(self.example_button)

        condition = self._group(layout, "Condition and sample")
        self.profile = QComboBox()
        for label, value in (("Room-temperature HRP–CO", "rt_hrp_co"),
                             ("Room-temperature MbCO · A1 first", "rt_mbco"),
                             ("Cryogenic HRP–CO", "cryo_hrp_co"),
                             ("Cryogenic MbCO", "cryo_mbco")):
            self.profile.addItem(label, value)
        condition.addRow("Condition profile", self.profile)
        for key, label in (("condition_id", "Condition ID"), ("sample_id", "Sample ID"),
                           ("preparation_id", "Preparation ID"), ("cell_id", "Cell ID"),
                           ("position_id", "Physical position ID"), ("temperature_id", "Temperature record ID")):
            control = QLineEdit()
            control.setPlaceholderText("Required measured / preparation identity")
            self.fields[key] = control
            condition.addRow(label, control)
        self._text(condition, "temperature_k", "Measured sample temperature (K)", "Applicable temperature record / profile")
        for key, label in (("dark_control_record_id", "Dark-control record ID"),
                           ("artifact_control_record_id", "Artifact / off-band control record ID"),
                           ("background_balance_record_id", "Optional measured path balance B record")):
            self._text(condition, key, label, "Applicable retained record identity")

        positions_box = QGroupBox("Ordered measured band / off-band positions")
        positions_layout = QVBoxLayout(positions_box)
        self.positions = QTableWidget(0, 4)
        self.positions.setHorizontalHeaderLabels(["cm⁻¹", "band / off_band", "Assignment", "Selection record ID"])
        self.positions.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.positions.setMinimumHeight(155)
        positions_layout.addWidget(self.positions)
        row = QHBoxLayout()
        add, remove = QPushButton("Add measured position"), QPushButton("Remove selected")
        row.addWidget(add)
        row.addWidget(remove)
        positions_layout.addLayout(row)
        positions_layout.addWidget(QLabel("Row order is acquisition order. Positions are never a simultaneous spectrum."))
        layout.addWidget(positions_box)
        add.clicked.connect(self.add_position)
        remove.clicked.connect(self.remove_position)

        observation = self._group(layout, "Observation, finite dose and recovery")
        for key, label, default, maximum in (
            ("pre_observation_s", "Pre-pump observation (s)", 1, 1e7),
            ("post_observation_s", "Post-pump recovery observation (s)", 10, 1e7),
            ("baseline_drift_fraction", "Allowed fractional baseline drift", .01, 1),
            ("baseline_cv_limit", "Allowed baseline coefficient of variation", .05, 1),
            ("reset_tolerance_fraction", "Measured reset tolerance (fraction)", .02, 1),
        ):
            self._number(observation, key, label, default, maximum)
        for key, label in (("event_budget", "Total authorized pump event budget"),
                           ("events_per_position", "Finite events per position / repetition"),
                           ("technical_repetitions", "Independent technical repetitions")):
            box = QSpinBox()
            box.setRange(0 if key == "event_budget" else 1, 1000000)
            box.setValue(1)
            self.fields[key] = box
            observation.addRow(label, box)
        self.pump = QCheckBox("Enable finite pump event(s); uncheck for no-pump control")
        self.pump.setChecked(True)
        observation.addRow(self.pump)
        self._text(observation, "minimum_event_interval_s", "Minimum accepted pump interval (s)", "Automatic from measured reset profile")
        self._text(observation, "baseline_window_s", "Baseline window [start, end] (s)", "Automatic within pre-pump record")
        self._text(observation, "integration_window_s", "Integration window [start, end] (s)", "Automatic within observation")
        self._text(observation, "reset_observation_s", "Reset confirmation window (s)", "Measured profile criterion")
        observation.addRow(QLabel("Entered durations and tolerances are proposals until accepted by an applicable measured condition profile."))

        advanced = self._group(layout, "Acquisition and retention overrides")
        for key, label in (("sample_rate_sps", "Sample acquisition rate (Sa/s)"),
                           ("sample_timeconstant_s", "Sample HF2LI time constant (s)"),
                           ("sample_filter_order", "Sample HF2LI filter order")):
            self._text(advanced, key, label, "Automatic from promoted profile")
        if mode == "dual":
            for key, label in (("reference_rate_sps", "Reference acquisition rate (Sa/s)"),
                               ("reference_timeconstant_s", "Reference HF2LI time constant (s)"),
                               ("reference_filter_order", "Reference HF2LI filter order")):
                self._text(advanced, key, label, "Automatic from promoted profile")
        self._number(advanced, "chunk_duration_s", "Continuous disk chunk interval (s)", 1, 60)
        self._number(advanced, "memory_limit_mb", "Memory budget (MiB)", 256, 100000)
        self._number(advanced, "storage_limit_mb", "Storage budget (MiB)", 10240, 10000000)
        self._number(advanced, "tune_timeout_s", "Tune timeout (s)", 60, 3600)
        self._text(advanced, "wavenumber_tolerance_cm1", "Actual wavenumber tolerance (cm⁻¹)", "Measured profile tolerance")
        advanced.addRow(QLabel("Native streams go continuously to disk. Chunk boundaries never restart the acquisition or reset the pump epoch."))
        layout.addStretch()
        for control in self.fields.values():
            signal = control.textChanged if isinstance(control, QLineEdit) else control.valueChanged
            signal.connect(self._changed)
        for control in (self.execution, self.profile):
            control.currentIndexChanged.connect(self._changed)
        self.bundle.textChanged.connect(self._changed)
        self.positions.itemChanged.connect(self._changed)
        self.pump.toggled.connect(self._changed)
        self.apply({"settings": Settings(mode=mode).to_dict(), "execution": "connected"})

    def _group(self, layout, title):
        box = QGroupBox(title)
        form = QFormLayout(box)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        layout.addWidget(box)
        return form

    def _number(self, form, key, label, default, maximum):
        control = QDoubleSpinBox()
        control.setRange(0, maximum)
        control.setDecimals(9)
        control.setValue(default)
        control.setKeyboardTracking(False)
        self.fields[key] = control
        form.addRow(label, control)

    def _text(self, form, key, label, placeholder):
        control = QLineEdit()
        control.setPlaceholderText(placeholder)
        self.fields[key] = control
        form.addRow(label, control)

    def _changed(self, *_):
        if not self._applying:
            self.changed.emit()

    def add_position(self, *_):
        self.positions.insertRow(self.positions.rowCount())
        self._changed()

    def remove_position(self):
        if self.positions.currentRow() >= 0:
            self.positions.removeRow(self.positions.currentRow())
            self._changed()

    def values(self):
        data = deepcopy(self._base_data)
        data["condition_profile"] = self.profile.currentData()
        data["pump_enabled"] = self.pump.isChecked()
        data["retention_strategy"] = "continuous_to_disk"
        for key, control in self.fields.items():
            if isinstance(control, QLineEdit):
                text = control.text().strip()
                if key.endswith("_id"):
                    data[key] = text
                elif key in ("baseline_window_s", "integration_window_s"):
                    data[key] = list(map(float, text.replace("[", "").replace("]", "").split(","))) if text else None
                else:
                    data[key] = (int(text) if key.endswith("_order") else float(text)) if text else None
            else:
                data[key] = control.value()
        positions = []
        for row in range(self.positions.rowCount()):
            cells = [self.positions.item(row, col).text().strip() if self.positions.item(row, col) else "" for col in range(4)]
            positions.append({"wavenumber_cm1": float(cells[0]), "label": cells[1] or "band",
                              "band_assignment": cells[2], "selection_record_id": cells[3] or self.local_selection_id})
        data["positions"] = positions
        return {"schema_version": 1, "record_kind": "fixed_point_plan", "experiment_id": "fixed_wavenumber_kinetics", "settings": data,
                "execution": self.execution.currentData(), "bundle_id": self.bundle.text().strip(),
                "sample_selection": deepcopy(self.sample_selection),
                "fresh_state_record": deepcopy(self.fresh_state_record)}

    def apply(self, envelope):
        self._applying = True
        try:
            data = {**Settings(mode=self.mode).to_dict(), **envelope.get("settings", {})}
            self._base_data = deepcopy(data)
            if data["mode"] != self.mode:
                raise ValueError("Cannot load the other detector mode into this tab")
            for key, control in self.fields.items():
                value = data.get(key)
                if isinstance(control, QLineEdit):
                    control.setText("" if value is None else ", ".join(map(str, value)) if isinstance(value, (tuple, list)) else str(value))
                elif value is not None:
                    control.setValue(value)
            self.profile.setCurrentIndex(max(0, self.profile.findData(data["condition_profile"])))
            self.execution.setCurrentIndex(max(0, self.execution.findData(envelope.get("execution", "connected"))))
            self.pump.setChecked(data["pump_enabled"])
            self.bundle.setText(envelope.get("bundle_id", ""))
            self.sample_selection = deepcopy(envelope.get("sample_selection"))
            self.fresh_state_record = deepcopy(envelope.get("fresh_state_record"))
            self.positions.setRowCount(len(data["positions"]))
            for row, point in enumerate(data["positions"]):
                for col, key in enumerate(("wavenumber_cm1", "label", "band_assignment", "selection_record_id")):
                    self.positions.setItem(row, col, QTableWidgetItem(str(point.get(key, ""))))
        finally:
            self._applying = False
        self.changed.emit()


class TraceRenderer:
    def __init__(self):
        self.event_index = 0
        self.view = "individual"
        self.quantity = "delta_absorbance"
        self.coordinate = None

    def draw(self, figure, record):
        import numpy as np
        analysis = record.get("analysis", record)
        events = analysis.get("events", [])
        if not events:
            axes = figure.add_subplot(111)
            axes.text(.05, .5, "No retained supported trace is available", transform=axes.transAxes)
            return
        if self.view == "trends":
            axes = figure.add_subplot(111)
            for key, label in (("amplitude", "Apparent amplitude"), ("remaining_fixed_point_fraction", "Unrecovered fraction")):
                values = [event.get("recovery_fit" if key == "amplitude" else "recovery", {}).get(key, float("nan")) for event in events]
                axes.plot(range(1, len(events)+1), values, "o-", label=label)
            axes.set(xlabel="Retained acquisition order / dose event", ylabel="Reported fit value", title="Dose / order trends; separate positions retain separate meaning")
            axes.legend()
            figure.tight_layout()
            return
        index = min(self.event_index, len(events)-1)
        event = events[index]
        time = np.asarray(event.get("time_s", []), float)
        if not len(time):
            return
        display = choose_time_display(time[np.isfinite(time)])
        t = time / display.seconds_per_unit
        native, normalized, residuals = figure.subplots(3, 1, sharex=True)
        for key, label in (("sample", "Sample native"), ("reference", "Reference native")):
            values = event.get(key)
            if values is not None and len(values) == len(t):
                native.plot(t, values, label=label, linewidth=.9)
        native.set_ylabel("Detector signal (V)")
        if native.lines:
            native.legend(loc="best")
        native.set_title(f"Event {index+1} · {event.get('wavenumber_cm1', '?')} cm⁻¹ · ordered fixed-point observation")
        values = event.get(self.quantity)
        label = {"delta_absorbance": "ΔA = −log₁₀(Q/Q₀)", "ratio": "Reference-normalized S/R" if record.get("mode") == "dual" else "Sample / sequential blank", "absolute_absorbance": "Absolute A (measured background/path balance required)"}[self.quantity]
        if values is None or not np.isfinite(np.asarray(values, float)).any():
            values, label = event.get("ratio", event.get("sample")), "Reference-normalized S/R" if record.get("mode") == "dual" else "Native sample signal (V)"
        if values is not None:
            normalized.plot(t, values, label=label, linewidth=1)
        fit = event.get("recovery_fit", {}) or {}
        model = fit.get("prediction", fit.get("predicted", fit.get("fitted")))
        if model is not None and len(model) == len(t) and self.quantity == "delta_absorbance":
            normalized.plot(t, model, label="Measured-response-convolved apparent recovery")
        if self.view == "aggregate" and self.quantity == "delta_absorbance":
            aggregation = analysis.get("aggregation", analysis)
            for aggregate in aggregation.get("aggregates", []):
                if aggregate.get("position_cm1") == event.get("wavenumber_cm1"):
                    normalized.plot(np.asarray(aggregate["time_s"])/display.seconds_per_unit,
                                    aggregate["mean_delta_absorbance"], linewidth=2,
                                    label=f"Accepted equivalent events ({len(aggregate['event_indices'])})")
        normalized.set_ylabel("Normalized signal")
        if normalized.lines:
            normalized.legend(loc="best")
        residual = fit.get("residuals")
        if residual is not None and len(residual) == len(t):
            residuals.plot(t, residual, linewidth=.8)
        residuals.set_ylabel("Fit residual")
        basis = "retained electrical pump epoch" if event.get("original_pump_timestamp") is not None else "first retained observation (no measured pump epoch)"
        residuals.set_xlabel(f"Elapsed device time relative to {basis} ({display.unit})")
        for axes in (native, normalized, residuals):
            if event.get("original_pump_timestamp") is not None:
                for marker in event.get("measured_pump_time_s", [0.]):
                    axes.axvline(marker/display.seconds_per_unit, color="tab:red", linestyle="--", label="Retained measured electrical pump marker")
            if self.coordinate is not None:
                axes.axvline(self.coordinate/display.seconds_per_unit, color="gray", linewidth=.7)
            axes.grid(alpha=.2)
        figure.tight_layout()


class FixedPointPanel(GuidedMeasurementPanel):
    live_record = Signal(object)

    def __init__(self, context):
        self.editor = SettingsEditor(context.mode)
        adapter = FixedPointAdapter(context, self.editor)
        self._last_envelope = None
        self._preparation_plan = None
        self._next_output = context.save_root()
        super().__init__(self.editor, adapter, context)
        self.setObjectName(context.instance_id)
        splitter = self.findChild(QSplitter)
        summary_widget = splitter.widget(1)
        summary_widget.setParent(None)
        summary_scroll = QScrollArea()
        summary_scroll.setWidgetResizable(True)
        summary_scroll.setWidget(summary_widget)
        splitter.addWidget(summary_scroll)
        splitter.setMinimumHeight(170)
        splitter.setMaximumHeight(240)
        self.preliminary_button.setText("2 · Acquire sample preliminary (pump OFF)" if context.mode == "single" else "1 · Acquire sample/reference preliminary (pump OFF)")
        self.start_button.setText("Start finite fixed-point acquisition")
        self.abort_button.setText("Abort acquisition")
        self.blank_button = QPushButton("1 · Acquire complete buffer blank (pump OFF)")
        self.load_blank_button = QPushButton("Load compatible buffer blank…")
        self.blank_status = QLabel("Load the buffer in the sample path before acquiring the blank." if context.mode == "single" else "Load the sample and matched-buffer reference together. No routine separate blank is required.")
        self.blank_status.setWordWrap(True)
        self.result_layout.addWidget(self.blank_status)
        if context.mode == "single":
            row = QHBoxLayout()
            row.addWidget(self.blank_button)
            row.addWidget(self.load_blank_button)
            self.result_layout.addLayout(row)
        self.renderer = TraceRenderer()
        self.view = QComboBox()
        for text, value in (("Individual retained event", "individual"), ("Matched events and aggregate", "aggregate"), ("Dose and acquisition-order trends", "trends")):
            self.view.addItem(text, value)
        views_row = QHBoxLayout()
        views_row.addWidget(self.view)
        self.result_layout.addLayout(views_row)
        self.quantity = QComboBox()
        self.quantity.addItem("Delta absorbance from unpumped baseline", "delta_absorbance")
        self.quantity.addItem("Reference-normalized ratio" if context.mode == "dual" else "Sample / sequential blank", "ratio")
        self.quantity.addItem("Absolute absorbance — measured B required", "absolute_absorbance")
        views_row.addWidget(self.quantity)
        self.handoff_button = QPushButton("Export discovery evidence for stroboscopic comparison…")
        views_row.addWidget(self.handoff_button)
        self.event_control = LinkedSliceControl([], label="Retained event / position", unit="index", decimals=0)
        self.time_control = LinkedSliceControl([], label="Measured time", unit="s", decimals=9)
        self.result_layout.addWidget(self.event_control)
        self.result_layout.addWidget(self.time_control)
        self.plot = PlotPanel(self.renderer)
        self.plot.canvas.setMinimumHeight(360)
        self.result_layout.addWidget(self.plot)
        self.fit_summary = QLabel()
        self.fit_summary.setWordWrap(True)
        self.fit_summary.setMaximumHeight(85)
        self.result_layout.addWidget(self.fit_summary)
        self.editor.changed.connect(self.refresh_plan)
        self.editor.profile_button.clicked.connect(self._load_profile)
        self.editor.selection_button.clicked.connect(self._load_selection)
        self.editor.clear_selection_button.clicked.connect(self._clear_selection)
        self.editor.fresh_state_button.clicked.connect(self._load_fresh_state)
        self.editor.example_button.clicked.connect(self._example)
        self.blank_button.clicked.connect(lambda: self._user_action(self.begin_blank))
        self.load_blank_button.clicked.connect(self._load_blank)
        self.result_ready.connect(self.show_record)
        self.run_loaded.connect(lambda result, _: self.show_record(result))
        self.live_record.connect(self.show_record)
        self.adapter.preview_callback = self.live_record.emit
        self.event_control.index_changed.connect(self._event_changed)
        self.time_control.index_changed.connect(self._time_changed)
        self.view.currentIndexChanged.connect(self._view_changed)
        self.quantity.currentIndexChanged.connect(self._view_changed)
        self.handoff_button.clicked.connect(self._export_handoff)
        self.new_run_requested.connect(self._clear_results)
        self.busy_changed.connect(lambda busy: context.lifecycle.notify_state(busy, "active" if busy else "idle"))
        self.plot.error.connect(self.status.setText)
        self.review.toggled.connect(self._review_selection)
        saved = context.preferences.value("settings")
        if isinstance(saved, dict):
            # Cached preferences never restore acquired baselines or review approval.
            try:
                self.adapter.apply_settings(saved)
            except Exception as exc:
                self.status.setText(f"Saved settings need correction: {exc}")
        self.refresh_plan()

    def refresh_plan(self, *_):
        if getattr(self, "_busy", False):
            return
        previous = self._last_envelope
        super().refresh_plan()
        try:
            current = self.adapter.read_settings()
            self._preparation_plan = self.adapter.make_plan(current, purpose="preliminary")
            self._last_envelope = deepcopy(current)
            self.context.preferences.setValue("settings", current)
            if previous is not None and previous != current:
                changed = [key for key in set(previous.get("settings", {})) | set(current["settings"])
                           if previous.get("settings", {}).get(key) != current["settings"].get(key)]
                self.status.setText("Preliminary review cleared: " + ", ".join(changed or ["profile, execution mode or selected records changed"]))
        except (TypeError, ValueError):
            self._preparation_plan = None
        if hasattr(self, "blank_status") and self.adapter.blank is not None and self.plan is not None:
            from .processing import compatible_record
            valid, messages = compatible_record(self.adapter.blank, self.plan)
            self.blank_status.setText("Compatible complete blank loaded." if valid else "Blank mismatch: " + "; ".join(messages))
        self._update_controls()

    def _update_controls(self, *_):
        super()._update_controls()
        ready = self.plan is not None and self.plan.ready
        preparation_ready = self._preparation_plan is not None and self._preparation_plan.ready
        blank_compatible = self.context.mode == "dual"
        if self.context.mode == "single" and self.adapter.blank is not None and self._preparation_plan is not None:
            from .processing import compatible_record
            blank_compatible = compatible_record(self.adapter.blank, self._preparation_plan)[0]
        if hasattr(self, "blank_button"):
            self.blank_button.setEnabled(not self._busy and preparation_ready)
            self.load_blank_button.setEnabled(not self._busy)
            self.preliminary_button.setEnabled(not self._busy and preparation_ready and blank_compatible)
        else:
            self.preliminary_button.setEnabled(not self._busy and preparation_ready)
        self.start_button.setEnabled(self.start_button.isEnabled() and ready)

    def begin(self, kind):
        target_plan = self._preparation_plan if kind == "preliminary" else self.plan
        if target_plan is None or not target_plan.ready:
            raise ValueError("Resolve the displayed operating-profile readiness items before acquisition")
        if self.context.mode == "single" and self.adapter.blank is None:
            raise ValueError("Acquire or load the complete compatible buffer blank first")
        if self.context.mode == "single":
            from .processing import compatible_record
            compatible, conflicts = compatible_record(self.adapter.blank, target_plan)
            if not compatible:
                raise ValueError("Blank mismatch: " + "; ".join(conflicts))
        original = self.plan
        if kind == "preliminary":
            self.plan = self._preparation_plan
        try:
            super().begin(kind)
        finally:
            self.plan = original

    def begin_blank(self):
        if self.context.mode != "single" or self._busy or self._preparation_plan is None or not self._preparation_plan.ready:
            raise ValueError("A ready single-detector plan is required for the blank")
        plan = self.adapter.make_plan(self.adapter.read_settings(), purpose="blank")
        selected = self.adapter.selected_records()
        operation = self.context.begin_operation(plan=self._host_plan,
            calibration_records=selected.calibration_records, sample_records=selected.sample_records,
            hardware=self.adapter.hardware_required("blank", self._host_plan.settings), purpose="blank", cancel=self.request_abort)
        snapshot = StartSnapshot(operation, "blank", plan, None)
        self.review.setChecked(False)
        self.preliminary = None
        self.adapter.blank = None
        self.snapshot = snapshot
        def run(worker):
            if operation.hardware:
                with self.context.hardware_scope(operation):
                    return self.adapter.run_blank(snapshot, worker)
            return self.adapter.run_blank(snapshot, worker)
        try:
            self._launch(run, "blank")
        except Exception:
            if operation.hardware:
                self.context.ownership.release(operation.ownership, safe_verified=True,
                    preservation_verified=True, detail="Blank worker dispatch failed before hardware access")
            raise

    def _finished(self, worker, kind, path):
        outcome = worker.outcome
        super()._finished(worker, kind, path)
        if outcome.state == "completed":
            if kind in ("blank", "load_blank"):
                self.adapter.blank = outcome.result
                self.review.setChecked(False)
                self.preliminary = None
                self.blank_status.setText("Complete compatible blank retained. Load sample, then acquire preliminary.")
                self.show_record(outcome.result)
            elif kind == "preliminary":
                self.adapter.instrument_changes.clear()
                self.show_record(outcome.result)
            elif kind == "load_profile":
                self.adapter.accept_profile(outcome.result)
                self.refresh_plan()
            elif kind == "load_selection":
                self._accept_selection(outcome.result)
            elif kind == "load_fresh_state":
                self.editor.fresh_state_record = outcome.result
                self.refresh_plan()
        elif outcome.state == "cancelled":
            self.status.setText("Acquisition stopped. Partial native records and restoration outcomes were retained.")
        current_record = self.adapter.last_record
        if outcome.state in ("cancelled", "failed") and kind in ("blank", "preliminary", "measurement") and current_record is not None and self.snapshot is not None and current_record.get("run_id") == self.snapshot.operation.run_id:
            self.result = self.adapter.last_record
            self.show_record(self.result)
        if kind == "measurement" and current_record is not None and any(
                event.get("commanded_event_number") for event in current_record.get("events", [])):
            self.review.setChecked(False)
            self.preliminary = None
            self.review_summary.setText("Pump event dispatched. A new compatible preliminary and explicit review are required before another run; cryogenic state reuse also requires accepted fresh-state evidence.")
        self._update_controls()

    def _load_profile(self):
        bundle_id = self.editor.bundle.text().strip()
        self._launch(lambda _: self.adapter.load_profile(bundle_id), "load_profile")

    def _review_selection(self, checked):
        """Accept only the observed points in this preliminary, not an inferred band."""
        if not checked or self.preliminary is None or self._busy:
            return
        if self.editor.sample_selection is None:
            from datetime import datetime, timezone
            import getpass
            settings = self.editor.values()["settings"]
            events = self.preliminary.get("analysis", {}).get("events", [])
            if not events or self.preliminary.get("analysis", {}).get("quality_flags"):
                self.review.setChecked(False)
                self.validation.setText("Preliminary has unresolved quality flags; retain it and correct the cause before review")
                return
            record = {"record_kind": "fixed_point_selection", "schema_version": 1,
                "record_id": settings["positions"][0]["selection_record_id"], "accepted": True,
                "sample_id": settings["sample_id"], "condition_id": settings["condition_id"],
                "preparation_id": settings["preparation_id"], "cell_id": settings["cell_id"],
                "positions": [{"wavenumber_cm1": e["wavenumber_cm1"],
                    "actual_readback": e.get("tuning", {}).get("actual"),
                    "actual_tuned": e.get("tuning", {}).get("tuned"),
                    "wavenumber_tolerance_cm1": self._preparation_plan.resolved.get("tune_tolerance_cm1")}
                    for e in events],
                "source_run_id": self.preliminary["run_id"], "source_path": self.preliminary["run_directory"],
                "accepted_by": getpass.getuser(), "accepted_utc": datetime.now(timezone.utc).isoformat(),
                "claim_limit": "Accepted local fixed-point support only; no fitted band center, band area or conformer quantification"}
            from .persistence import write_json
            try:
                write_json(Path(self.preliminary["run_directory"])/("accepted-selection-"+uuid4().hex+".json"), record)
                self.adapter.local_selection = record
                self.plan = self.adapter.make_plan(self.adapter.read_settings())
                self._host_plan = self.context.new_plan(self.adapter.read_settings())
                self.summary.setText(self.adapter.summarize_plan(self.plan))
                self.validation.setText("\n".join(self.adapter.validate_plan(self.plan)))
            except Exception as exc:
                self.review.setChecked(False)
                self.status.setText(f"Could not retain preliminary acceptance: {exc}")
        self._update_controls()

    def _load_selection(self):
        from control_app.measurement_host.interchange import load_sample_selection
        path, _ = QFileDialog.getOpenFileName(self, "Accepted sample spectral selection", str(self._next_output), "JSON (*.json)")
        if path:
            self._launch(lambda _: load_sample_selection(path).to_dict(), "load_selection")

    def _clear_selection(self):
        envelope = self.editor.values()
        envelope["sample_selection"] = None
        self.adapter.local_selection = None
        self.editor.local_selection_id = "fixed-point-selection-" + uuid4().hex
        for point in envelope["settings"]["positions"]:
            point["selection_record_id"] = self.editor.local_selection_id
        self.editor.apply(envelope)

    def _load_fresh_state(self):
        path, _ = QFileDialog.getOpenFileName(self, "Accepted measured fresh-state equivalence", str(self._next_output), "JSON (*.json)")
        if path:
            def read(_):
                record = json.loads(Path(path).read_text(encoding="utf-8"))
                required = ("record_id", "sample_id", "preparation_id", "cell_id", "condition_id", "position_id",
                            "accepted_by", "source_run_id", "equivalence_basis")
                if record.get("accepted") is not True or any(not record.get(k) for k in required):
                    raise ValueError("Fresh-state record needs accepted=true, measured source/equivalence basis, named reviewer and all sample/state identities")
                return record
            self._launch(read, "load_fresh_state")

    def _accept_selection(self, record):
        if any(window.get("center_cm1") is None for window in record["windows"]):
            raise ValueError("Select a measured fixed-point center in each imported window; a spectral range alone is not a selected wavenumber")
        envelope = self.editor.values()
        envelope["sample_selection"] = record
        envelope["settings"]["sample_id"] = record["sample_id"]
        envelope["settings"]["condition_id"] = record["condition_id"]
        envelope["settings"]["positions"] = [
            {"wavenumber_cm1": window["center_cm1"], "label": "off_band" if "off" in window["label"].lower() else "band",
             "band_assignment": window["label"], "selection_record_id": record["selection_id"]}
            for window in record["windows"]]
        self.editor.apply(envelope)

    def _load_blank(self):
        from .processing import compatible_record
        path = QFileDialog.getExistingDirectory(self, "Load complete compatible buffer blank", str(self._next_output))
        if path:
            plan = deepcopy(self.plan)
            def load(_):
                record = self.adapter.load_run(path, condition_id=plan.settings.condition_id)
                if record.get("kind") != "blank" or record.get("status") not in ("completed", "complete"):
                    raise ValueError("A completed buffer blank record is required")
                valid, conflicts = compatible_record(record, plan)
                if not valid:
                    raise ValueError("; ".join(conflicts))
                return record
            self._launch(load, "load_blank")

    def load_run(self, path):
        condition_id = self.editor.values()["settings"]["condition_id"] or None
        self._launch(lambda worker: self.adapter.load_run(Path(path), condition_id=condition_id,
                     cancel=worker.cancel_event), "load_run", path)

    def _example(self):
        from .simulation import simulation_profile
        profile = simulation_profile(self.context.mode)
        envelope = {"settings": profile["settings"], "execution": "simulation", "bundle_id": "", "sample_selection": None}
        self.editor.apply(envelope)
        self.status.setText("Synthetic example loaded. All observations and calibration values in this mode are simulation only.")

    def show_record(self, record):
        events = record.get("analysis", record).get("events", [])
        absolute_available = any(event.get("absolute_absorbance") is not None for event in events)
        self.quantity.model().item(2).setEnabled(absolute_available)
        self.quantity.setItemText(2, "Absolute absorbance (measured background)" if absolute_available
                                  else "Absolute absorbance unavailable — compatible measured B required")
        if not absolute_available and self.quantity.currentData() == "absolute_absorbance":
            self.quantity.setCurrentIndex(0)
        self.plot.set_result(record)
        self.event_control.set_coordinates(range(1, len(events)+1))
        self._event_changed(min(self.renderer.event_index, max(0, len(events)-1)))

    def _event_changed(self, index):
        self.renderer.event_index = index
        record = self.plot.result or {}
        events = record.get("analysis", record).get("events", [])
        if events:
            event = events[min(index, len(events)-1)]
            self.time_control.set_coordinates(event.get("time_s", []))
            fit = event.get("recovery_fit") or {}
            baseline = event.get("baseline", {})
            text = f"Baseline mean {baseline.get('mean', '?')} · stationary {baseline.get('stationary', '?')} · "
            text += f"{event.get('analysis_count', '?')} analysed / {event.get('native_count', '?')} native observations.\n"
            if fit.get("tau_s") is not None:
                text += f"Apparent τ={fit['tau_s']:.6g} s · 95% profile interval {fit.get('tau_profile_95_s')} · "
                text += f"amplitude={fit.get('amplitude', float('nan')):.6g} · residual RMS={fit.get('residual_rms', float('nan')):.4g}.\n"
            else:
                text += f"Recovery: {fit.get('status', 'unresolved')}.\n"
            text += "Quality: " + (", ".join(event.get("quality_flags", [])) or "no flags on retained support")
            text += ". Apparent local recovery only; electrical epoch unless optical arrival is independently qualified."
            self.fit_summary.setText(text)
            self.fit_summary.setToolTip("Full covariance, residuals, uncertainty inputs and claim limits are retained in the saved run.")
        self.plot.reset_view()

    def _time_changed(self, index):
        if self.time_control.coordinates:
            self.renderer.coordinate = self.time_control.coordinates[index]
            self.plot.reset_view()

    def _view_changed(self, *_):
        self.renderer.view = self.view.currentData()
        self.renderer.quantity = self.quantity.currentData()
        self.plot.reset_view()

    def _export_handoff(self):
        if self._busy or self.result is None:
            self.status.setText("Load or acquire a retained discovery run before exporting its comparison evidence.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Stroboscopic comparison evidence", str(self._next_output), "JSON (*.json)")
        if path:
            from .persistence import export_stroboscopic_handoff
            record = deepcopy(self.result)
            self._launch(lambda _: export_stroboscopic_handoff(record, path), "export_handoff")

    def _clear_results(self):
        self.plot.clear_result()
        self.event_control.set_coordinates([])
        self.time_control.set_coordinates([])
        self.fit_summary.clear()
        self.blank_status.setText("New run: blank and review cleared." if self.context.mode == "single" else "New run: simultaneous baseline and review cleared.")

    def output_location_changed(self, path):
        self._next_output = Path(path)
        # Active operations keep the host's already-frozen output_path.
        self.save_root_provider = lambda: self._next_output

    def close_blockers(self):
        blockers = list(super().close_blockers())
        state = self.context.ownership.snapshot()
        if state.get("state") == "fault" and (state.get("owner") or {}).get("instance_id") == self.context.instance_id:
            blockers.append("Explicit host recovery is required: this operation's cleanup or native preservation remains unverified.")
        return tuple(blockers)

    def instrument_state_changed(self, change):
        messages = [f"{item.device_id}.{item.configuration_key} changed: {item.previous_value} → {item.new_value}" for item in change.changes]
        self.adapter.instrument_changes.extend(messages)
        self.review.setChecked(False)
        self.preliminary = None
        self.adapter.blank = None
        self.validation.setText("Preliminary/blank invalidated: " + "; ".join(messages))
        self._update_controls()


def make_handle(context, *, title):
    panel = FixedPointPanel(context)
    return TabHandle(instance_id=context.instance_id, title=title, widget=panel,
        command_running=panel.command_running, close_blockers=panel.close_blockers,
        request_abort=panel.request_abort, output_location_changed=panel.output_location_changed,
        instrument_state_changed=panel.instrument_state_changed, state_changed=panel.busy_changed)
