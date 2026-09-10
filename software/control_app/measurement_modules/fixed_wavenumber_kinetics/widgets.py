"""Compact fixed-wavenumber tabs with independent, owned operations."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import Signal, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QLineEdit, QDoubleSpinBox, QSpinBox, QPushButton,
    QFileDialog)
from control_app.measurement_host import TabHandle
from control_app.measurement_host.presentation import (
    CompactMeasurementPanel, LinkedSliceControl, PlotPanel, choose_time_display)
from .settings import Settings
from .app_adapter import FixedPointAdapter


class _ObservationTimeInput(QDoubleSpinBox):
    def textFromValue(self, value):
        return f"{value:.9f}".rstrip("0").rstrip(".") or "0"


class SettingsEditor(QWidget):
    changed = Signal()

    def __init__(self, mode):
        super().__init__()
        self.mode, self.sample_selection = mode, None
        self._base_data = Settings(mode=mode).to_dict()
        self._execution, self._applying = "connected", False
        self._historical_ui_settings = {}
        self.fields = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        form.setVerticalSpacing(3)
        layout.addLayout(form)
        sample = QLineEdit()
        sample.setPlaceholderText("Optional label")
        self.fields["sample_label"] = sample
        form.addRow("Sample", sample)
        self.wavenumber = QDoubleSpinBox()
        self.wavenumber.setRange(0, 10000)
        self.wavenumber.setDecimals(3)
        self.wavenumber.setSuffix(" cm^-1")
        self.wavenumber.setSpecialValueText("Enter wavenumber")
        self.wavenumber.setKeyboardTracking(False)
        form.addRow("Wavenumber", self.wavenumber)
        self._number(form, "pre_observation_s", "Before pump", 1, 1e7, " s")
        self._number(form, "post_observation_s", "Recovery", 10, 1e7, " s")
        self.fields["pre_observation_s"].setDecimals(9)
        self.fields["post_observation_s"].setDecimals(9)
        self._integer(form, "events_per_position", "Events", 1, 1000000)
        self.pump = QComboBox()
        self.pump.addItem("Pump event", True)
        self.pump.addItem("No pump", False)
        form.addRow("Acquisition", self.pump)
        self.positions = QLineEdit()
        self.positions.setPlaceholderText("Optional, comma separated")
        self.positions.setToolTip("Additional wavenumbers in acquisition order")
        self.selection_button = QPushButton("Load…")
        self.selection_button.setFixedWidth(56)
        self.selection_button.setToolTip("Load measured positions")
        positions_row = QHBoxLayout()
        positions_row.addWidget(self.positions, 1)
        positions_row.addWidget(self.selection_button)
        form.addRow("Other positions (cm⁻¹)", positions_row)

        self.advanced = QWidget()
        advanced_layout = QVBoxLayout(self.advanced)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(3)
        advanced = QFormLayout()
        advanced.setVerticalSpacing(3)
        advanced_layout.addLayout(advanced)
        self._text(advanced, "probe_rate_hz", "Repetition rate (Hz)")
        self._text(advanced, "probe_width_ns", "Pulse width (ns)")
        self._text(advanced, "minimum_event_interval_s", "Event interval (s)")
        roles = ("sample", "reference") if mode == "dual" else ("sample",)
        if mode == "dual":
            heading = QHBoxLayout()
            for role in roles:
                heading.addWidget(QLabel(role.title()), 1)
            advanced.addRow("Detector", heading)
        for suffix, label in (("rate_sps", "Rate (Sa/s)"),
                              ("timeconstant_s", "Time constant (s)"),
                              ("filter_order", "Filter order")):
            row = QHBoxLayout()
            for role in roles:
                control = self._text(None, f"{role}_{suffix}", label)
                control.setToolTip(f"{role.title()} {label.lower()}")
                row.addWidget(control, 1)
            advanced.addRow(label, row)
        reset = QPushButton("Restore automatic settings")
        reset.clicked.connect(self.restore_automatic)
        advanced_layout.addWidget(reset)
        for control in self.fields.values():
            (control.textChanged if isinstance(control, QLineEdit) else control.valueChanged).connect(self._changed)
        self.wavenumber.valueChanged.connect(self._changed)
        self.pump.currentIndexChanged.connect(self._changed)
        self.positions.textChanged.connect(self._changed)
        self.apply({"settings": self._base_data})

    def _number(self, form, key, label, default, maximum, suffix=""):
        control = _ObservationTimeInput() if key in ("pre_observation_s", "post_observation_s") else QDoubleSpinBox()
        control.setRange(0, maximum)
        control.setDecimals(6)
        control.setSuffix(suffix)
        control.setValue(default)
        control.setKeyboardTracking(False)
        self.fields[key] = control
        form.addRow(label, control)

    def _integer(self, form, key, label, default, maximum):
        control = QSpinBox()
        control.setRange(1, maximum)
        control.setValue(default)
        control.setKeyboardTracking(False)
        self.fields[key] = control
        form.addRow(label, control)

    def _text(self, form, key, label):
        control = QLineEdit()
        control.setPlaceholderText("Automatic")
        self.fields[key] = control
        if form is not None:
            form.addRow(label, control)
        return control

    def _changed(self, *_):
        if not self._applying:
            self.changed.emit()

    def restore_automatic(self):
        self._applying = True
        for key in ("pump_fire_delay_s", "pump_q_switch_delay_s", "pump_fire_width_s",
                    "pump_q_switch_width_s", "wavenumber_tolerance_cm1"):
            self._base_data[key] = None
        for key, control in self.fields.items():
            if isinstance(control, QLineEdit) and key != "sample_label":
                control.clear()
        self._applying = False
        self.changed.emit()

    def values(self):
        data = deepcopy(self._base_data)
        for key, control in self.fields.items():
            if isinstance(control, QLineEdit):
                text = control.text().strip()
                if key == "sample_label":
                    data[key] = text
                elif key in ("baseline_window_s", "integration_window_s"):
                    data[key] = list(map(float, text.strip("[]").split(","))) if text else None
                else:
                    data[key] = (int(text) if key.endswith("_order") else float(text)) if text else None
            else:
                data[key] = control.value()
        previous = {}
        for point in self._base_data.get("positions", []):
            previous.setdefault(point["wavenumber_cm1"], []).append(point)
        requested = [self.wavenumber.value()] if self.wavenumber.value() else []
        for text in self.positions.text().split(","):
            if not text.strip():
                continue
            requested.append(float(text.strip()))
        positions = []
        for value in requested:
            matching = previous.get(value, [])
            saved = matching.pop(0) if matching else {}
            positions.append({**saved, "wavenumber_cm1": value})
        data["positions"] = positions
        data["pump_enabled"] = self.pump.currentData()
        data["event_budget"] = len(positions)*data["events_per_position"]*data["technical_repetitions"] if data["pump_enabled"] else 0
        data["retention_strategy"] = "continuous_to_disk"
        return {"schema_version": 1, "record_kind": "fixed_point_plan", "experiment_id": "fixed_wavenumber_kinetics",
                "settings": data, "execution": self._execution, "sample_selection": deepcopy(self.sample_selection),
                "historical_ui_settings": deepcopy(self._historical_ui_settings)}

    def apply(self, envelope):
        self._applying = True
        try:
            defaults = Settings(mode=self.mode).to_dict()
            data = {**defaults, **envelope.get("settings", {})}
            if data["mode"] != self.mode:
                raise ValueError("Detector mode differs from this tab")
            historical = deepcopy(envelope.get("historical_ui_settings", {}))
            for key in ("technical_repetitions", "baseline_window_s", "integration_window_s",
                        "baseline_drift_fraction", "baseline_cv_limit", "reset_tolerance_fraction",
                        "pump_fire_delay_s", "pump_q_switch_delay_s", "pump_fire_width_s",
                        "pump_q_switch_width_s", "wavenumber_tolerance_cm1", "chunk_duration_s",
                        "memory_limit_mb", "storage_limit_mb", "tune_timeout_s"):
                if data[key] != defaults[key]:
                    historical[key] = deepcopy(data[key])
                data[key] = defaults[key]
            self._historical_ui_settings = historical
            self._base_data = deepcopy(data)
            self._execution = "connected"
            self.sample_selection = deepcopy(envelope.get("sample_selection"))
            for key, control in self.fields.items():
                value = data.get(key)
                if isinstance(control, QLineEdit):
                    control.setText("" if value is None else ", ".join(map(str, value)) if isinstance(value, (tuple, list)) else str(value))
                elif value is not None:
                    control.setValue(value)
            positions = data.get("positions", [])
            self.wavenumber.setValue(positions[0]["wavenumber_cm1"] if positions else 0)
            self.positions.setText(", ".join(str(point["wavenumber_cm1"]) for point in positions[1:]))
            self.pump.setCurrentIndex(0 if data["pump_enabled"] else 1)
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
        figure.set_layout_engine("constrained")
        analysis = record.get("analysis", record)
        events = analysis.get("events", [])
        if not events:
            axes = figure.add_subplot(111)
            axes.text(.05, .5, "No measurement loaded", transform=axes.transAxes)
            return
        if self.view == "trends":
            axes = figure.add_subplot(111)
            for key, label in (("amplitude", "Apparent amplitude"), ("remaining_fixed_point_fraction", "Unrecovered fraction")):
                values = [event.get("recovery_fit" if key == "amplitude" else "recovery", {}).get(key, float("nan")) for event in events]
                axes.plot(range(1, len(events)+1), values, "o-", label=label)
            axes.set(xlabel="Retained acquisition order / dose event", ylabel="Reported fit value", title="Dose / order trends; separate positions retain separate meaning")
            axes.legend()
            return
        index = min(self.event_index, len(events)-1)
        event = events[index]
        time = np.asarray(event.get("time_s", []), float)
        if not len(time):
            return
        display = choose_time_display(time[np.isfinite(time)])
        t = time / display.seconds_per_unit
        fit = event.get("recovery_fit", {}) or {}
        has_fit = fit.get("residuals") is not None
        axes_rows = figure.subplots(3 if has_fit else 2, 1, sharex=True)
        native, normalized = axes_rows[:2]
        for key, label in (("sample", "Sample magnitude"), ("reference", "Reference magnitude")):
            if key == "reference" and record.get("mode") == "single":
                continue
            values = event.get(key)
            if values is not None and len(values) == len(t) and np.isfinite(np.asarray(values, float)).any():
                native.plot(t, values, label=label, linewidth=.9)
        native.set_ylabel("Magnitude (V)")
        if native.lines:
            native.legend(loc="best", fontsize=8)
        native.set_title(f"Event {index+1} · {event.get('wavenumber_cm1', '?')} cm⁻¹ · fixed point", fontsize=10)
        values = event.get(self.quantity)
        label = {"delta_absorbance": "ΔA = −log₁₀(Q/Q₀)", "ratio": "Reference-normalized S/R" if record.get("mode") == "dual" else "Sample / sequential blank", "absolute_absorbance": "Absolute A (measured background/path balance required)"}[self.quantity]
        label = event.get(self.quantity + "_label", label)
        if values is None or not np.isfinite(np.asarray(values, float)).any():
            ratio = event.get("ratio")
            if ratio is not None and np.isfinite(np.asarray(ratio, float)).any():
                values = ratio
                label = event.get("ratio_label", "Reference-normalized S/R" if record.get("mode") == "dual" else "Sample / sequential blank")
            else:
                values = None
        if values is not None:
            normalized.plot(t, values, label=label, linewidth=1)
        else:
            normalized.text(.5, .5, "No normalized signal", ha="center", va="center", transform=normalized.transAxes)
        model = fit.get("prediction", fit.get("predicted", fit.get("fitted")))
        if model is not None and len(model) == len(t) and self.quantity == "delta_absorbance":
            normalized.plot(t, model, label="Apparent recovery fit")
        if self.view == "aggregate" and self.quantity == "delta_absorbance":
            aggregation = analysis.get("aggregation", analysis)
            for aggregate in aggregation.get("aggregates", []):
                if aggregate.get("position_cm1") == event.get("wavenumber_cm1"):
                    normalized.plot(np.asarray(aggregate["time_s"])/display.seconds_per_unit,
                                    aggregate["mean_delta_absorbance"], linewidth=2,
                                    label=f"Equivalent events ({len(aggregate['event_indices'])})")
        normalized.set_ylabel("Normalized")
        if normalized.lines:
            normalized.legend(loc="best", fontsize=8)
        residual = fit.get("residuals")
        if has_fit:
            residuals = axes_rows[-1]
            if len(residual) == len(t):
                residuals.plot(t, residual, linewidth=.8)
            residuals.set_ylabel("Fit residual")
        basis = "electrical pump" if event.get("original_pump_timestamp") is not None else "first observation"
        axes_rows[-1].set_xlabel(f"Time from {basis} ({display.unit})")
        for axes in axes_rows:
            if event.get("original_pump_timestamp") is not None:
                for marker in event.get("measured_pump_time_s", [0.]):
                    axes.axvline(marker/display.seconds_per_unit, color="tab:red", linestyle="--", label="Retained measured electrical pump marker")
            if self.coordinate is not None:
                axes.axvline(self.coordinate/display.seconds_per_unit, color="gray", linewidth=.7)
            axes.grid(alpha=.2)
            axes.tick_params(labelsize=8)
            axes.xaxis.label.set_size(9)
            axes.yaxis.label.set_size(9)


class FixedPointPanel(CompactMeasurementPanel):
    live_record = Signal(object)

    def __init__(self, context):
        self.editor = SettingsEditor(context.mode)
        self._next_output = context.save_root()
        self._capability_check_attempted = False
        adapter = FixedPointAdapter(context, self.editor)
        super().__init__(self.editor, adapter, context, advanced_widget=self.editor.advanced)
        self.file_layout.setDirection(QHBoxLayout.Direction.LeftToRight)
        self.settings_layout.setContentsMargins(6, 3, 6, 3)
        self.settings_layout.setSpacing(3)
        self.settings_extras_layout.setSpacing(3)
        self.advanced_layout.setContentsMargins(6, 6, 6, 6)
        self.setObjectName(context.instance_id)
        self.preliminary_button.setText("Acquire sample · pump off")
        self.start_button.setText("Start acquisition")
        self.abort_button.setText("Stop")
        self.load_run_button.setText("Load run…")
        self.export_button.setText("Export…")
        self.check_device_button = self.add_settings_action("Check connected device", self.check_device)
        if context.mode == "single":
            self.blank_button = self.add_blank_action("Acquire blank", self.begin_blank)
            self.load_blank_button = self.add_blank_action("Load blank…", self._load_blank)
        self.blank_status = QLabel("Blank: none" if context.mode == "single" else "Sample / reference recorded together")
        self.blank_status.setWordWrap(True)
        self.settings_extras_layout.addWidget(self.blank_status)
        self.renderer = TraceRenderer()
        self.view = QComboBox()
        for text, value in (("Individual event", "individual"), ("Aggregate", "aggregate"), ("Dose / order", "trends")):
            self.view.addItem(text, value)
        self.quantity = QComboBox()
        self.quantity.addItem("Relative log signal", "delta_absorbance")
        self.quantity.addItem("Normalized signal", "ratio")
        self.quantity.addItem("Absolute absorbance", "absolute_absorbance")
        self.quantity.model().item(2).setEnabled(False)
        row = QHBoxLayout()
        row.addWidget(self.view)
        row.addWidget(self.quantity)
        self.result_layout.addLayout(row)
        self.event_control = LinkedSliceControl([], label="Event", decimals=0)
        self.time_control = LinkedSliceControl([], label="Time", unit="s", decimals=6)
        self.result_layout.addWidget(self.event_control)
        self.result_layout.addWidget(self.time_control)
        self.plot = PlotPanel(self.renderer)
        self.plot.canvas.setMinimumHeight(240)
        self.result_layout.addWidget(self.plot, 1)
        self.fit_summary = QLabel()
        self.fit_summary.setWordWrap(True)
        self.result_layout.addWidget(self.fit_summary)
        self.handoff_button = QPushButton("Export comparison…")
        self.handoff_button.setToolTip("Export retained data for a stroboscopic comparison")
        self.run_file_layout.addWidget(self.handoff_button)
        self.editor.changed.connect(self.refresh_plan)
        self.editor.selection_button.clicked.connect(self._load_selection)
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
        self.operation_finished.connect(self._operation_finished)
        self.busy_changed.connect(self._busy_changed)
        self.plot.error.connect(self.set_status)
        saved = context.preferences.value("settings")
        if isinstance(saved, dict):
            try:
                self.adapter.apply_settings(saved)
            except Exception as exc:
                self.set_status(f"Load settings: {exc}")
        self.refresh_plan()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._capability_check_attempted:
            QTimer.singleShot(0, self._automatic_device_check)

    def _automatic_device_check(self):
        if not self.isVisible() or self.command_running() or self._capability_check_attempted:
            return
        self._capability_check_attempted = True
        if self.editor.values().get("execution") == "connected":
            self._user_action(self.check_device)

    def check_device(self):
        self._capability_check_attempted = True
        if not self._connected_devices_available():
            self.set_status("Connected instruments unavailable")
            self._update_extra_controls()
            return
        self.begin_operation("capabilities", self.adapter.run_capabilities, requires_valid_plan=False)

    def _connected_devices_available(self):
        return {"t660_1", "t660_2", "mircat", "hf2li"}.issubset(
            self.context.devices.available(hardware=True))

    def refresh_plan(self, *_):
        super().refresh_plan()
        if not self.command_running():
            try:
                self.context.preferences.setValue("settings", self.editor.values())
            except (TypeError, ValueError):
                pass
        self._update_extra_controls()

    def refresh_readiness(self, *_):
        super().refresh_readiness()
        self.validation.setVisible(bool(self.validation.text()))

    def _update_extra_controls(self):
        if not hasattr(self, "blank_status"):
            return
        idle = not self.command_running()
        self.check_device_button.setEnabled(idle and self._connected_devices_available())
        self.handoff_button.setEnabled(idle and self.result is not None)
        if hasattr(self, "blank_button"):
            self.blank_button.setEnabled(idle and self.plan is not None)
            self.load_blank_button.setEnabled(idle)
            if self.adapter.blank:
                from .processing import compatible_record
                compatible = self.plan is not None and compatible_record(self.adapter.blank, self.plan)[0]
                self.blank_status.setText("Blank: ready" if compatible else "Blank: different settings · using local baseline")
            else:
                self.blank_status.setText("Blank: none · using local baseline")

    def _busy_changed(self, busy):
        self.context.lifecycle.notify_state(busy, "active" if busy else "idle")
        self._update_extra_controls()

    def begin_blank(self):
        self.begin_operation("blank", self.adapter.run_blank, invalidates_preliminary=True)

    def _operation_finished(self, kind, outcome):
        if outcome.state == "completed":
            record = outcome.result
            if kind == "capabilities":
                self.adapter.live_readbacks = deepcopy(record)
                self.set_status("Connected device settings loaded")
                self.refresh_plan()
            elif kind in ("blank", "load_blank"):
                self.adapter.blank = record
                self.result = record
                self.show_record(record)
                self.set_status("Blank ready")
            elif kind in ("preliminary", "measurement", "load_run"):
                if record.get("live_readbacks"):
                    self.adapter.live_readbacks = deepcopy(record["live_readbacks"])
                    self.refresh_plan()
                if kind == "load_run" and record.get("kind") == "blank":
                    self.adapter.blank = record
                if record.get("kind") == "preliminary":
                    self.preliminary = record
                self.show_record(record)
        elif kind in ("blank", "preliminary", "measurement"):
            record = self.adapter.last_record
            if record and self.snapshot and record.get("run_id") == self.snapshot.operation.run_id:
                self.result = record
                self.show_record(record)
            if outcome.state == "cancelled":
                self.set_status("Acquisition stopped")
        self.refresh_readiness()
        self._update_extra_controls()

    def _load_blank(self):
        path = QFileDialog.getExistingDirectory(self, "Load blank", str(self._next_output))
        if path:
            def load(snapshot, worker):
                record = self.adapter.load_run(path, cancel=worker.cancel_event)
                if record.get("kind") != "blank" or record.get("status") not in ("complete", "completed"):
                    raise ValueError("Select a completed blank run")
                return record
            self.begin_operation("load_blank", load, invalidates_preliminary=True, requires_valid_plan=False)

    def _load_selection(self):
        import json
        path, _ = QFileDialog.getOpenFileName(self, "Load positions", str(self._next_output), "JSON (*.json)")
        if path:
            try:
                record = json.loads(Path(path).read_text(encoding="utf-8"))
                if record.get("record_kind") != "sample_spectral_selection" or record.get("schema_version") != 1:
                    raise ValueError("Select a version 1 spectral-selection file")
                positions = []
                for window in record["windows"]:
                    if window.get("center_cm1") is None:
                        raise ValueError("Choose a file with selected wavenumbers")
                    label = str(window.get("label", "band"))
                    positions.append({"wavenumber_cm1": window["center_cm1"], "band_assignment": label,
                        "label": "off_band" if "off" in label.lower() else "band"})
                envelope = self.editor.values()
                envelope["settings"]["positions"] = positions
                envelope["sample_selection"] = record
                self.editor.apply(envelope)
            except Exception as exc:
                self.set_status(str(exc))

    def _example(self):
        """Developer-only injection; no simulator choice is exposed in the tab."""
        from .simulation import simulation_profile
        profile = simulation_profile(self.context.mode)
        self.editor.apply({"settings": profile["settings"]})
        self.editor._execution = "simulation"
        self.refresh_plan()

    def show_record(self, record):
        events = record.get("analysis", record).get("events", [])
        absolute = any(event.get("absolute_absorbance") is not None for event in events)
        self.quantity.model().item(2).setEnabled(absolute)
        if not absolute and self.quantity.currentData() == "absolute_absorbance":
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
            baseline_relative = event.get("normalization_kind") == "observed_sample_baseline"
            self.quantity.setItemText(0, "Relative log signal" if baseline_relative else "Delta absorbance")
            self.quantity.setItemText(1, "Baseline-relative S/S0" if baseline_relative else
                "Sample / blank" if record.get("mode") == "single" else "Sample / reference")
            coordinates = event.get("time_s", [])
            self.time_control.set_coordinates(coordinates)
            fit = event.get("recovery_fit") or {}
            baseline = event.get("baseline", {})
            mean = baseline.get("mean")
            text = f"Baseline {mean:.5g}" if isinstance(mean, (float, int)) else "Baseline unavailable"
            if fit.get("tau_s") is not None:
                text += f" · apparent recovery {fit['tau_s']:.3g} s"
                interval = fit.get("tau_profile_95_s")
                if interval and len(interval) == 2:
                    text += f" · 95% interval {interval[0]:.3g}–{interval[1]:.3g} s"
            else:
                text += " · response unqualified" if fit.get("status") == "unresolved_response" else " · no recovery fit"
            flags = event.get("quality_flags", [])
            if flags:
                text += " · " + str(flags[0]).replace("_", " ")
            self.fit_summary.setText(text)
        self.plot.reset_view()

    def _time_changed(self, index):
        if self.time_control.coordinates:
            self.renderer.coordinate = self.time_control.coordinates[index]
            self.plot.reset_view()

    def _view_changed(self, *_):
        self.renderer.view, self.renderer.quantity = self.view.currentData(), self.quantity.currentData()
        self.plot.reset_view()

    def _export_handoff(self):
        if self.command_running() or self.result is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export comparison", str(self._next_output), "JSON (*.json)")
        if path:
            from .persistence import export_stroboscopic_handoff
            record = deepcopy(self.result)
            self.begin_operation("export_handoff", lambda snapshot, worker: export_stroboscopic_handoff(record, path), requires_valid_plan=False)

    def _clear_results(self):
        self.plot.clear_result()
        self.event_control.set_coordinates([])
        self.time_control.set_coordinates([])
        self.fit_summary.clear()
        self._update_extra_controls()

    def output_location_changed(self, path):
        self._next_output = Path(path)
        super().output_location_changed(path)

    def close_blockers(self):
        blockers = list(super().close_blockers())
        state = self.context.ownership.snapshot()
        if state.get("state") == "fault" and (state.get("owner") or {}).get("instance_id") == self.context.instance_id:
            blockers.append("Host recovery required after cleanup or preservation failure")
        return tuple(blockers)

    def instrument_state_changed(self, change):
        self.adapter.live_readbacks = {}
        self.refresh_plan()
        self.set_status("Device settings changed · automatic values will refresh on connection")


def make_handle(context, *, title):
    panel = FixedPointPanel(context)
    return TabHandle(instance_id=context.instance_id, title=title, widget=panel,
        command_running=panel.command_running, close_blockers=panel.close_blockers,
        request_abort=panel.request_abort, output_location_changed=panel.output_location_changed,
        instrument_state_changed=panel.instrument_state_changed, state_changed=panel.busy_changed)
