"""Compact fixed-wavenumber tabs with independent, owned operations."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QLineEdit, QDoubleSpinBox, QSpinBox, QPushButton,
    QFileDialog)
from control_app.measurement_host.settings_sections import HF2LIValueInput, hf2li_choices
from control_app.measurement_host import TabHandle
from control_app.measurement_host.presentation import (
    CompactMeasurementPanel, LinkedSliceControl, PlotPanel, choose_time_display)
from control_app.measurement_host.settings_sections import compact_settings_page, settings_section, AutomaticValueInput, PhaseLaserSections
from .settings import Settings
from .app_adapter import FixedPointAdapter


class _ObservationTimeInput(QDoubleSpinBox):
    def textFromValue(self, value):
        return f"{value:.9f}".rstrip("0").rstrip(".") or "0"


class SettingsEditor(QWidget):
    changed = Signal()
    MIRCAT_DEFAULTS = {"probe_rate_hz": PhaseLaserSections.MIRCAT_DEFAULTS["probe_repetition_rate_hz"],
                       "probe_width_ns": PhaseLaserSections.MIRCAT_DEFAULTS["probe_pulse_width_ns"]}

    def __init__(self, mode):
        super().__init__()
        self.mode, self.sample_selection = mode, None
        self._base_data = Settings(mode=mode).to_dict()
        self._execution, self._applying = "connected", False
        self._historical_ui_settings = {}
        self.fields = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        run_group, run_form = settings_section(layout, "Run Label")
        sample = QLineEdit()
        sample.setMaximumHeight(20)
        sample.setPlaceholderText("Optional label")
        self.fields["sample_label"] = sample
        run_form.addRow("Run Label", sample)
        self.lasers = PhaseLaserSections(layout, self._changed, allow_single_point=True, supplied={
            "probe_repetition_rate_hz": self._text(None, "probe_rate_hz", "Repetition Rate"),
            "probe_pulse_width_ns": self._text(None, "probe_width_ns", "Pulse Width"),
        })
        settings_group, form = settings_section(layout, "Kinetics Settings")
        self.wavenumber = QDoubleSpinBox(self)
        self.wavenumber.hide()
        self.wavenumber.setMaximumHeight(20)
        self.wavenumber.setRange(0, 10000)
        self.wavenumber.setDecimals(3)
        self.wavenumber.setSuffix(" cm^-1")
        self.wavenumber.setSpecialValueText("Enter wavenumber")
        self.wavenumber.setKeyboardTracking(False)
        self._number(form, "pre_observation_s", "Pre-Pump Acquisition", 1, 1e7, " s")
        self._number(form, "post_observation_s", "Post-Pump Acquisition", 10, 1e7, " s")
        self.fields["pre_observation_s"].setDecimals(9)
        self.fields["post_observation_s"].setDecimals(9)
        self._integer(form, "pump_shots", "Pump Shots", 1, 8191)
        self._number(form, "shot_delay_s", "Shot Delay", .1, 1e7, " s")
        self._integer(form, "events_per_position", "Trials", 1, 1000000)
        self._time_scale = 1.
        self.time_units = QComboBox()
        for label, scale in (("s", 1.), ("ms", 1e-3), ("µs", 1e-6), ("ns", 1e-9)):
            self.time_units.addItem(label, scale)
        form.addRow("Time units", self.time_units)
        self.time_units.currentIndexChanged.connect(self._update_time_units)
        self.fields["pump_shots"].valueChanged.connect(self._shot_count_changed)
        self._update_time_units()
        self.pump = QComboBox()
        self.pump.setMaximumHeight(20)
        self.pump.addItem("Pump shots", True)
        self.pump.addItem("No pump", False)
        self.pump.hide()
        self.positions = QLineEdit(self)
        self.positions.hide()
        self.positions.setMaximumHeight(20)
        self.positions.setPlaceholderText("Optional, comma separated")
        self.positions.setToolTip("Additional wavenumbers in acquisition order")
        self.selection_button = QPushButton("Load…")
        self.selection_button.setToolTip("Load measured positions")
        self.selection_button.setText("Load positions…")
        self.selection_button.setMinimumWidth(120)
        self.selection_button.hide()

        self.advanced = QWidget()
        advanced_layout = QVBoxLayout(self.advanced)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(3)
        advanced = QFormLayout()
        advanced.setVerticalSpacing(3)
        advanced_layout.addLayout(advanced)

        roles = ("sample", "reference") if mode == "dual" else ("sample",)
        for role in roles:
            for suffix, label in (("filter_order", "Filter order"),
                                  ("timeconstant_s", "Time constant (s)"),
                                  ("rate_sps", "CH1 sample rate (Sa/s)")):
                name = f"{role.title()} {label.lower().replace('ch1 ', '')}" if mode == "dual" else label
                self._text(advanced, f"{role}_{suffix}", name)
        reset = QPushButton("Restore automatic settings")
        reset.clicked.connect(self.restore_automatic)
        advanced_layout.addWidget(reset)
        for control in self.fields.values():
            (control.currentTextChanged if isinstance(control, AutomaticValueInput) else control.textChanged if isinstance(control, QLineEdit) else control.valueChanged).connect(self._changed)
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
        control.setMaximumHeight(20)
        self.fields[key] = control
        form.addRow(label, control)

    def _integer(self, form, key, label, default, maximum):
        control = QSpinBox()
        control.setRange(1, maximum)
        control.setValue(default)
        control.setKeyboardTracking(False)
        control.setMaximumHeight(20)
        self.fields[key] = control
        form.addRow(label, control)

    def _text(self, form, key, label):
        control = HF2LIValueInput() if key.startswith(("sample_", "reference_")) else AutomaticValueInput()
        self.fields[key] = control
        if form is not None:
            form.addRow(label, control)
        return control

    def _changed(self, *_):
        if not self._applying:
            if self.sender() is self.wavenumber and self.wavenumber.value():
                self.lasers.set_points([self.wavenumber.value()])
            self.changed.emit()

    def restore_automatic(self):
        self._applying = True
        self.lasers.restore_automatic()
        for key in ("pump_fire_delay_s", "pump_q_switch_delay_s", "pump_fire_width_s",
                    "pump_q_switch_width_s", "wavenumber_tolerance_cm1"):
            self._base_data[key] = None
        for key, control in self.fields.items():
            if isinstance(control, (QLineEdit, AutomaticValueInput)) and key != "sample_label":
                control.setText(str(self.MIRCAT_DEFAULTS[key])) if key in self.MIRCAT_DEFAULTS else control.clear()
        self._applying = False
        self.changed.emit()

    def _shot_count_changed(self, *_):
        self.fields["shot_delay_s"].setEnabled(self.fields["pump_shots"].value() > 1)

    def _update_time_units(self, *_):
        scale = self.time_units.currentData()
        unit = self.time_units.currentText()
        for key in ("pre_observation_s", "post_observation_s", "shot_delay_s"):
            control = self.fields[key]
            seconds = control.value() * self._time_scale
            blocked = control.blockSignals(True)
            control.setDecimals(9)
            control.setRange((.1 if key == "shot_delay_s" else 1e-9) / scale, 1e7 / scale)
            control.setSuffix(" " + unit)
            control.setValue(seconds / scale)
            control.blockSignals(blocked)
        self._time_scale = scale
        self._shot_count_changed()
        self._changed()

    def values(self):
        data = deepcopy(self._base_data)
        data["laser_settings"] = self.lasers.values()
        for key, control in self.fields.items():
            if isinstance(control, (QLineEdit, AutomaticValueInput)):
                text = control.text().strip()
                if key == "sample_label":
                    data[key] = text
                elif key in ("baseline_window_s", "integration_window_s"):
                    data[key] = list(map(float, text.strip("[]").split(","))) if text else None
                else:
                    data[key] = (int(text) if key.endswith("_order") else float(text)) if text else None
            else:
                data[key] = control.value() * self._time_scale if key in ("pre_observation_s", "post_observation_s", "shot_delay_s") else control.value()
        data["time_unit"] = self.time_units.currentText()
        previous = {}
        for point in self._base_data.get("positions", []):
            previous.setdefault(point["wavenumber_cm1"], []).append(point)
        requested = [self.wavenumber.value()] if self.wavenumber.value() else []
        for text in self.positions.text().split(","):
            if not text.strip():
                continue
            requested.append(float(text.strip()))
        if self.lasers.range_edited:
            requested = self.lasers.points()
        positions = []
        for value in requested:
            matching = previous.get(value, [])
            saved = matching.pop(0) if matching else {}
            positions.append({**saved, "wavenumber_cm1": value})
        data["positions"] = positions
        data["pump_enabled"] = self.pump.currentData()
        data["event_budget"] = len(positions)*data["events_per_position"]*data["technical_repetitions"]*data["pump_shots"] if data["pump_enabled"] else 0
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
            self.lasers.apply(data.get("laser_settings", {}))
            self._execution = "connected"
            self.sample_selection = deepcopy(envelope.get("sample_selection"))
            self.time_units.setCurrentText(data.get("time_unit", "s"))
            for key, control in self.fields.items():
                value = data.get(key)
                if key in ("pre_observation_s", "post_observation_s", "shot_delay_s") and value is not None:
                    value /= self._time_scale
                if value is None:
                    value = self.MIRCAT_DEFAULTS.get(key)
                if isinstance(control, (QLineEdit, AutomaticValueInput)):
                    control.setText("" if value is None else ", ".join(map(str, value)) if isinstance(value, (tuple, list)) else str(value))
                elif value is not None:
                    control.setValue(value)
            positions = data.get("positions", [])
            self.lasers.set_points([p["wavenumber_cm1"] for p in positions])
            self.wavenumber.setValue(positions[0]["wavenumber_cm1"] if positions else 0)
            self.positions.setText(", ".join(str(point["wavenumber_cm1"]) for point in positions[1:]))
            self.pump.setCurrentIndex(0 if data["pump_enabled"] else 1)
            self._shot_count_changed()
        finally:
            self._applying = False
        self.changed.emit()


class TraceRenderer:
    def __init__(self):
        self.event_index = 0
        self.view = "aggregate"
        self.quantity = "sample"
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
        if "observed_pump_count_mismatch" in event.get("quality_flags", ()):
            axes = figure.add_subplot(111)
            count = len(event.get("pump_timestamps", event.get("measured_pump_time_s", [])))
            axes.text(.5, .5, f"Incomplete trial: {event.get('expected_pump_count', '?')} pump shots requested; {count} sync pulses observed.\n"
                      "No valid pump-relative trace is available.\nNative data retained for diagnosis.",
                      ha="center", va="center", transform=axes.transAxes)
            axes.set_title(f"{event.get('position_cm1', '?')} cm⁻¹ · pump-count mismatch")
            return
        if event.get("expected_pump_count", 0) and event.get("original_pump_timestamp") is None:
            axes = figure.add_subplot(111)
            axes.text(.5, .5, "Pump sync was not observed.\nNo pump-relative trace is available.\nNative data retained for diagnosis.",
                      ha="center", va="center", transform=axes.transAxes)
            axes.set_title(f"{event.get('position_cm1', '?')} cm⁻¹ · incomplete trial")
            return
        aggregate = None
        if self.view == "aggregate":
            aggregate = next((a for a in analysis.get("aggregates", []) if a["position_cm1"] == event.get("position_cm1", event.get("wavenumber_cm1"))), None)
            if aggregate is not None:
                event = {**event, **aggregate.get("means", {"delta_absorbance": aggregate["mean_delta_absorbance"]}),
                         "time_s": aggregate["time_s"], "measured_pump_time_s": aggregate.get("measured_pump_time_s", event.get("measured_pump_time_s", [0.])),
                         "recovery_fit": {}}
        time = np.asarray(event.get("time_s", []), float)
        if not len(time):
            return
        display = choose_time_display(time[np.isfinite(time)], unit=record.get("settings", {}).get("time_unit"))
        t = time / display.seconds_per_unit
        native = figure.add_subplot(111)
        axes_rows = [native]
        for key, label in (("sample", "Sample magnitude"), ("reference", "Reference magnitude")):
            if key == "reference" and record.get("mode") == "single":
                continue
            values = event.get(key)
            if values is not None and len(values) == len(t) and np.isfinite(np.asarray(values, float)).any():
                native.plot(t, values, label=label, linewidth=.9)
        native.set_ylabel("Magnitude (V)")
        if native.lines:
            native.legend(loc="best", fontsize=8)
        title = f"Mean of {len(aggregate['event_indices'])} trials" if aggregate is not None else f"Trial {event.get('trial_index', event.get('repetition_index', index))+1}"
        native.set_title(f"{title} · {event.get('wavenumber_cm1', '?')} cm⁻¹", fontsize=10)
        basis = "electrical pump" if event.get("original_pump_timestamp") is not None else "first observation"
        axes_rows[-1].set_xlabel(f"Time from {basis} ({display.unit})")
        window = event.get("analysis_window_s")
        if window is None and event.get("original_pump_timestamp") is not None:
            settings = record.get("settings", {})
            if "pre_observation_s" in settings and "post_observation_s" in settings:
                window = [-settings["pre_observation_s"], max(event.get("measured_pump_time_s", [0.]))+settings["post_observation_s"]]
        for axes in axes_rows:
            if window is not None:
                axes.set_xlim(np.asarray(window)/display.seconds_per_unit)
            if event.get("original_pump_timestamp") is not None:
                for shot, marker in enumerate(event.get("measured_pump_time_s", [0.]), 1):
                    x = marker/display.seconds_per_unit
                    axes.axvline(x, color="tab:red", linestyle="--", label="Measured electrical pump marker")
                    if axes is native:
                        axes.text(x, .98, f" Pump {shot}", color="tab:red", va="top", fontsize=8, transform=axes.get_xaxis_transform())
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
        compact_settings_page(self)
        self.advanced_group.setTitle("HF2LI Settings")
        self.setObjectName(context.instance_id)
        self.preliminary_button.setText("Acquire sample · pump off")
        self.start_button.setText("Start acquisition")
        self.abort_button.setText("Stop")
        self.load_run_button.setText("Load run…")
        self.export_button.setText("Export…")
        if context.mode == "single":
            self.blank_button = self.add_blank_action("Acquire blank", self.begin_blank)
            self.load_blank_button = self.add_blank_action("Load blank…", self._load_blank)
        self.blank_status = QLabel("Blank: none" if context.mode == "single" else "Sample / reference recorded together")
        self.blank_status.setWordWrap(True)
        self.settings_extras_layout.addWidget(self.blank_status)
        self.renderer = TraceRenderer()
        self.view = QComboBox()
        for text, value in (("Mean across trials", "aggregate"), ("Individual trial", "individual")):
            self.view.addItem(text, value)
        row = QHBoxLayout()
        self.wavenumber = QComboBox()
        self.wavenumber.setObjectName("fixed_wavenumber_plot_selection")
        row.addWidget(QLabel("Wavenumber"))
        row.addWidget(self.wavenumber)
        row.addWidget(self.view)
        self.result_layout.addLayout(row)
        self.event_control = LinkedSliceControl([], label="Trial", decimals=0)
        self.time_control = LinkedSliceControl([], label="Time", unit="s", decimals=6)
        self._time_scale = 1.
        self.result_layout.addWidget(self.event_control)
        self.result_layout.addWidget(self.time_control)
        self.plot = PlotPanel(self.renderer)
        self.plot.canvas.setMinimumHeight(215)
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
        self._position_event_indices = []
        self.wavenumber.currentIndexChanged.connect(self._position_changed)
        self.event_control.index_changed.connect(self._event_changed)
        self.time_control.index_changed.connect(self._time_changed)
        self.view.currentIndexChanged.connect(self._view_changed)
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
        supported = (self.adapter.live_readbacks or {}).get("supported", {})
        for role, fields in supported.items():
            for key, values in fields.items():
                control = self.editor.fields.get(f"{role}_{'filter_order' if key == 'order' else key}")
                if isinstance(control, AutomaticValueInput) and isinstance(values, (list, tuple)):
                    control.set_choices(values)
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
        if idle and not self._connected_devices_available() and not self.status.text():
            self.set_status("Connected instruments unavailable")
        reason = ("Acquisition is running" if not idle else
                  "\n".join(map(str, self._plan_issues or self._preliminary_issues)))
        for button in (self.preliminary_button, self.start_button, getattr(self, "blank_button", None)):
            if button is not None:
                button.setToolTip(reason if not button.isEnabled() else "")
        # The detailed validation lives inside the settings scroll. Repeat the
        # reason beside the actions so startup cannot leave unexplained gray buttons.
        if idle and self.plan is None and reason:
            self.set_status(reason if self._connected_devices_available() else "Connected instruments unavailable · " + reason)
            self._displaying_plan_error = True
        elif idle and getattr(self, "_displaying_plan_error", False):
            self.set_status(("Ready to acquire" if self._connected_devices_available() else "Connected instruments unavailable") if self.plan is not None else reason)
            self._displaying_plan_error = False
        self.handoff_button.setEnabled(idle and self.result is not None)
        self.blank_status.clear()
        self.blank_status.hide()
        self._disable_reference_controls()

    def _disable_reference_controls(self):
        for name in ("blank_button", "load_blank_button", "preliminary_button", "load_preliminary_button"):
            button = getattr(self, name, None)
            if button is not None:
                button.setEnabled(False)
                button.setToolTip("Not used for Fixed Wavenumber detector traces; start acquisition directly.")

    def _update_controls(self, *_):
        super()._update_controls()
        self._disable_reference_controls()

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
        # The developer fixture uses a 100 kHz external clock and 110 kHz
        # internal laser; select its intended rate explicitly in the editor.
        profile["settings"]["probe_rate_hz"] = 100000.
        self.editor.apply({"settings": profile["settings"]})
        self.editor._execution = "simulation"
        self.refresh_plan()

    def show_record(self, record):
        events = record.get("analysis", record).get("events", [])
        self.plot.set_result(record)
        selected = self.wavenumber.currentData()
        positions = list(dict.fromkeys(e.get("position_cm1", e.get("wavenumber_cm1")) for e in events))
        self.wavenumber.blockSignals(True)
        self.wavenumber.clear()
        for position in positions:
            self.wavenumber.addItem(f"{position:g} cm⁻¹" if position is not None else "Current position", position)
        self.wavenumber.setCurrentIndex(positions.index(selected) if selected in positions else 0)
        self.wavenumber.blockSignals(False)
        self._position_changed()

    def _position_changed(self, *_):
        record = self.plot.result or {}
        events = record.get("analysis", record).get("events", [])
        position = self.wavenumber.currentData()
        self._position_event_indices = [i for i, event in enumerate(events)
            if event.get("position_cm1", event.get("wavenumber_cm1")) == position]
        self.event_control.set_coordinates(range(1, len(self._position_event_indices)+1))
        if self._position_event_indices:
            self.event_control.set_index(0)
        self._event_changed(0)

    def _event_changed(self, index):
        index = self._position_event_indices[min(index, len(self._position_event_indices)-1)] if self._position_event_indices else 0
        self.renderer.event_index = index
        record = self.plot.result or {}
        events = record.get("analysis", record).get("events", [])
        if events:
            event = events[min(index, len(events)-1)]
            coordinates = event.get("time_s", [])
            display = choose_time_display(coordinates, unit=record.get("settings", {}).get("time_unit"))
            self._time_scale = display.seconds_per_unit
            self.time_control.input.setSuffix(f" {display.unit}")
            self.time_control.set_coordinates([value/self._time_scale for value in coordinates])
            text = "Detector magnitude"
            flags = event.get("quality_flags", [])
            if self.renderer.view == "aggregate":
                aggregate = next((a for a in record.get("analysis", {}).get("aggregates", ())
                    if a["position_cm1"] == event.get("position_cm1", event.get("wavenumber_cm1"))), None)
                if aggregate is not None:
                    flags = aggregate.get("quality_notes", [])
                    text = f"Mean across {len(aggregate['event_indices'])} trials; individual recordings retained"
                    if not aggregate.get("equivalent_state_verified", False):
                        text += " · sample reset not verified"
            if flags:
                text += " · " + str(flags[0]).replace("_", " ")
            self.fit_summary.setText(text)
            self.fit_summary.setToolTip("; ".join(map(str, flags)))
        self.plot.reset_view()

    def _time_changed(self, index):
        if self.time_control.coordinates:
            self.renderer.coordinate = self.time_control.coordinates[index]*self._time_scale
            self.plot.reset_view()

    def _view_changed(self, *_):
        self.renderer.view = self.view.currentData()
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
        self.wavenumber.clear()
        self._position_event_indices = []
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
