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
    QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from control_app.measurement_host import TabHandle
from control_app.measurement_host.presentation import (
    CompactMeasurementPanel, LinkedSliceControl, PlotPanel,
)
from .scientific_adapter import NanosecondScientificAdapter
from .settings import Settings, ADVANCED_FIELDS, INTEGER_ADVANCED_FIELDS


class NanosecondSettingsWidget(QWidget):
    """Essential acquisition inputs; independent explicit overrides default to Auto."""

    changed = Signal()
    OVERRIDES = (
        ("filter_order", "Filter order", ""),
        ("filter_time_constant_s", "Time constant", "s"),
        ("hf2li_rate_hz", "Sample rate", "Sa/s"),
        ("reference_filter_order", "Filter order", ""),
        ("reference_filter_time_constant_s", "Time constant", "s"),
        ("reference_hf2li_rate_hz", "Sample rate", "Sa/s"),
    )
    INTEGER_OVERRIDES = INTEGER_ADVANCED_FIELDS

    def __init__(self, mode, preferences, parent=None, *, execution_mode="connected"):
        super().__init__(parent)
        self.mode, self.preferences, self.execution_mode = mode, preferences, execution_mode
        self.controls, self.override_inputs = {}, {}
        self._values = Settings(mode=mode, execution_mode=execution_mode).to_dict()
        saved = preferences.value("settings_json", "")
        if saved:
            try:
                restored = Settings.from_dict(json.loads(saved)).to_dict()
                if restored["mode"] == mode:
                    self._values = restored
            except (ValueError, TypeError, KeyError):
                pass
        self._values["execution_mode"] = execution_mode
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.measurement_group = QGroupBox("Measurement")
        layout = QFormLayout(self.measurement_group)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setVerticalSpacing(3)
        root.addWidget(self.measurement_group)
        for key, label in (("wavenumbers_cm1", "Wavenumbers (cm⁻¹)"), ("delays_ns", "Delays (ns)")):
            control = QLineEdit()
            control.setObjectName(key)
            control.setToolTip("Comma-separated values")
            control.editingFinished.connect(self._changed)
            self.controls[key] = control
            layout.addRow(label, control)
        repetitions = QSpinBox()
        repetitions.setRange(1, 100000)
        repetitions.valueChanged.connect(self._changed)
        self.controls["repetitions"] = repetitions
        layout.addRow("Averages", repetitions)
        for key, label in (("cycle_interval_s", "Cycle interval"),):
            control = QDoubleSpinBox()
            control.setDecimals(6)
            control.setRange(.000001, 86400.)
            control.setSuffix(" s")
            control.setKeyboardTracking(False)
            control.valueChanged.connect(self._changed)
            self.controls[key] = control
            layout.addRow(label, control)
        self.advanced_widget = QWidget()
        advanced = QVBoxLayout(self.advanced_widget)
        advanced.setContentsMargins(0, 0, 0, 0)
        advanced.setSpacing(3)
        self.detector_groups = {}
        forms = {}
        for role in (("sample", "reference") if mode == "dual" else ("sample",)):
            if mode == "dual":
                group = QGroupBox(role.title())
                self.detector_groups[role] = group
                form = QFormLayout(group)
                form.setContentsMargins(8, 4, 8, 4)
                advanced.addWidget(group)
            else:
                form = QFormLayout()
                form.setContentsMargins(0, 0, 0, 0)
                advanced.addLayout(form)
            form.setVerticalSpacing(3)
            forms[role] = form
        for key, label, unit in self.OVERRIDES:
            role = "reference" if key.startswith("reference_") else "sample"
            if key not in ADVANCED_FIELDS or role not in forms:
                continue
            control = QComboBox()
            control.setObjectName("override_" + key)
            control.setEditable(True)
            control.addItem("Auto", None)
            control.setToolTip(f"Automatic selection; enter an explicit {unit or 'value'} override if needed.")
            control.currentTextChanged.connect(self._changed)
            self.override_inputs[key] = control
            forms[role].addRow(label + (f" ({unit})" if unit else ""), control)
        self.restore_auto_button = QPushButton("Restore Auto")
        self.restore_auto_button.clicked.connect(self.restore_auto)
        advanced.addWidget(self.restore_auto_button)
        self.apply_settings(self._values)

    def _changed(self, *_):
        try:
            self.preferences.setValue("settings_json", json.dumps(self.read_settings()))
        except (ValueError, TypeError):
            pass
        self.changed.emit()

    def read_settings(self):
        values = deepcopy(self._values)
        for key, control in self.controls.items():
            if isinstance(control, QLineEdit):
                values[key] = tuple(float(item.strip()) for item in control.text().split(",") if item.strip())
            else:
                values[key] = control.value()
        overrides = {}
        for key, control in self.override_inputs.items():
            text = control.currentText().strip()
            if text.lower() == "auto" or not text:
                continue
            value = float(text)
            if key in self.INTEGER_OVERRIDES:
                if value != int(value):
                    raise ValueError(key.replace("_", " ") + " must be an integer")
                value = int(value)
            overrides[key] = value
        values.update(mode=self.mode, execution_mode=self.execution_mode, overrides=overrides)
        return Settings.from_dict(values).to_dict()

    def apply_settings(self, values):
        values = Settings.from_dict(values).to_dict()
        if values["mode"] != self.mode:
            raise ValueError("Plan belongs to the other detector mode")
        values["execution_mode"] = self.execution_mode
        self._values = deepcopy(values)
        for key, control in self.controls.items():
            control.blockSignals(True)
            value = values.get(key, values.get("probe_period_s", 1.))
            if isinstance(control, QLineEdit):
                control.setText(", ".join(f"{item:g}" for item in value))
                control.setCursorPosition(0)
                control.setToolTip(control.text() + (" ns" if key == "delays_ns" else " cm⁻¹"))
            else:
                control.setValue(value)
            control.blockSignals(False)
        overrides = values.get("overrides", {})
        for key, control in self.override_inputs.items():
            control.blockSignals(True)
            value = overrides.get(key)
            control.setCurrentText("Auto" if value is None else f"{value:g}")
            control.blockSignals(False)
        self.preferences.setValue("settings_json", json.dumps(values))

    def set_resolved(self, plan):
        settings = getattr(plan, "resolved_settings", None)
        if settings is None:
            return
        values = settings.to_dict()
        sources = getattr(plan, "resolution_sources", {}) or {}
        for key, control in self.override_inputs.items():
            value = values.get(key)
            control.setToolTip(f"Selected: {value if value is not None else 'pending device check'}; {sources.get(key, 'automatic')}")

    def restore_auto(self):
        for control in self.override_inputs.values():
            control.blockSignals(True)
            control.setCurrentText("Auto")
            control.blockSignals(False)
        self._changed()


class NanosecondPlotAdapter:
    """Native support and linked slices, with optical and programmed time distinct."""

    def __init__(self):
        self.time_index = self.wavenumber_index = 0
        self.quantity, self.condition, self.view = "delta_a", "pump_on", "reconstruction"

    def draw(self, figure, run):
        from .processing import spectral_observable
        events = run.get("events", [])
        dual = run.get("mode") == "dual"
        reconstructed = run.get("result") or {}
        if self.view == "native":
            axes = figure.add_subplot(111)
            axes.plot([_native_mean(event, "sample") for event in events], ".", label="Sample")
            if dual:
                axes.plot([_native_mean(event, "reference") for event in events], ".", label="Reference")
            axes.set(xlabel="Event", ylabel="Integrated response (V·s)")
            if events:
                axes.legend(fontsize=8)
            figure.subplots_adjust(left=.12, right=.96, bottom=.15, top=.94)
            return
        if self.view == "sample" or not reconstructed.get("wavenumbers_cm1"):
            axes = figure.add_subplot(111)
            observable = [spectral_observable(event, "dual" if dual else "single")["value"] for event in events]
            axes.plot([event.get("wavenumber_cm1", np.nan) for event in events], observable, ".")
            axes.set(xlabel="Wavenumber (cm⁻¹)", ylabel="Q = S/R" if dual else "Integrated response (V·s)")
            figure.subplots_adjust(left=.12, right=.96, bottom=.15, top=.94)
            return
        if self.condition != "pump_on":
            control = reconstructed.get("controls", {}).get(self.condition, {})
            reconstructed = {**reconstructed, **control, "fits": [], "uncertainty": [], "optical_delay_ns": []}
        waves = np.asarray(reconstructed.get("wavenumbers_cm1", []), dtype=float)
        delays = np.asarray(reconstructed.get("delays_ns", []), dtype=float)
        values = np.asarray(reconstructed.get(self.quantity, []), dtype=float)
        if not waves.size or not delays.size or values.shape != (waves.size, delays.size):
            axes = figure.add_subplot(111)
            axes.set(xlabel="Delay (ns)", ylabel="Wavenumber (cm⁻¹)")
            return
        ti = min(self.time_index, len(delays) - 1)
        wi = min(self.wavenumber_index, len(waves) - 1)
        label = {"delta_a": "ΔA", "ratio": "Q = S/R" if dual else "Response (V·s)",
                 "absolute_absorbance": "Absorbance", "coverage": "Count"}[self.quantity]
        grid = figure.add_gridspec(2, 2, height_ratios=(1.2, 1))
        surface = figure.add_subplot(grid[0, :])
        image = surface.pcolormesh(delays, waves, np.ma.masked_invalid(values), shading="nearest", cmap="viridis")
        figure.colorbar(image, ax=surface, label=label, pad=.015)
        surface.axvline(delays[ti], color="white", linewidth=.6)
        surface.axhline(waves[wi], color="white", linewidth=.6)
        surface.set(xlabel="Programmed delay (ns)", ylabel="Wavenumber (cm⁻¹)")
        if len(delays) > 1:
            surface.set_xlim(float(np.min(delays)), float(np.max(delays)))
        if len(waves) > 1:
            surface.set_ylim(float(np.min(waves)), float(np.max(waves)))
        spectrum = figure.add_subplot(grid[1, 0])
        spectrum.plot(waves, values[:, ti], ".-")
        spectrum.set(xlabel="Wavenumber (cm⁻¹)", ylabel=label, title=f"{delays[ti]:g} ns")
        spectrum.invert_xaxis()
        kinetic = figure.add_subplot(grid[1, 1])
        optical = np.asarray(reconstructed.get("optical_delay_ns", []), dtype=float)
        optical_present = optical.shape == values.shape and np.any(np.isfinite(optical[wi]))
        times = optical[wi] if optical_present else delays
        kinetic.plot(times, values[wi], ".-")
        kinetic.set(xlabel="Optical delay (ns)" if optical_present else "Programmed delay (ns)",
                    ylabel=label, title=f"{waves[wi]:g} cm⁻¹")
        uncertainty = np.asarray(reconstructed.get("uncertainty", []), dtype=float)
        if self.quantity == "delta_a" and uncertainty.shape == values.shape:
            kinetic.fill_between(times, values[wi] - uncertainty[wi], values[wi] + uncertainty[wi], alpha=.2)
            fit = next((item for item in reconstructed.get("fits", []) if item.get("wavenumber_cm1") == waves[wi]), {})
            if fit.get("predicted"):
                kinetic.plot(fit.get("supported_delay_ns", []), fit["predicted"], "--")
        for axes in (surface, spectrum, kinetic):
            axes.tick_params(labelsize=8)
            axes.xaxis.label.set_size(8)
            axes.yaxis.label.set_size(8)
            axes.title.set_size(9)
        figure.subplots_adjust(left=.12, right=.95, bottom=.13, top=.97, hspace=.65, wspace=.45)


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


class NanosecondPanel(CompactMeasurementPanel):
    """Compact live acquisition tab with automatic baseline compatibility."""

    def __init__(self, context, parent=None, *, execution_mode="connected", runner_factory=None):
        self._next_root = None
        self._started = None
        settings = NanosecondSettingsWidget(context.mode, context.preferences, execution_mode=execution_mode)
        adapter = NanosecondScientificAdapter(context, settings, runner_factory=runner_factory)
        super().__init__(settings, adapter, context, parent, advanced_widget=settings.advanced_widget)
        self.advanced_group.setTitle("HF2LI overrides")
        self.advanced_layout.setContentsMargins(8, 4, 8, 4)
        self.settings_layout.setSpacing(4)
        settings.changed.connect(self.refresh_plan)
        self.save_root_provider = lambda: self._next_root or self.context.save_root()
        self.preliminary_button.setText("Acquire unpumped sample")
        self.start_button.setText("Start pump–probe scan")
        self.abort_button.setText("Abort")
        self.new_run_button.setText("New run")
        if context.mode == "single":
            self.acquire_blank_button = self.add_blank_action("Acquire blank", self.begin_blank)
            self.load_blank_button = self.add_blank_action("Load blank…", lambda: self._choose_reference("blank"))
        else:
            self.acquire_blank_button = QPushButton("Acquire blank", self)
            self.load_blank_button = QPushButton("Load blank…", self)
            self.acquire_blank_button.hide()
            self.load_blank_button.hide()
        self.load_preliminary_button = self.add_action("Load unpumped sample…", lambda: self._choose_reference("preliminary"))
        self.action_layout.insertWidget(1, self.load_preliminary_button)
        self.record_status = QLabel()
        self.record_status.setWordWrap(True)
        self.settings_extras_layout.addWidget(self.record_status)
        self.plot_adapter = NanosecondPlotAdapter()
        self.plot = PlotPanel(self.plot_adapter)
        self.plot.canvas.setMinimumHeight(260)
        self.quantity = QComboBox()
        self.quantity.addItem("ΔA", "delta_a")
        self.quantity.addItem("Q = S/R" if context.mode == "dual" else "Sample signal", "ratio")
        self.quantity.addItem("Coverage", "coverage")
        self.condition = QComboBox()
        self.condition.addItem("Pump on", "pump_on")
        self.view = QComboBox()
        self.view.addItem("Reconstruction", "reconstruction")
        self.view.addItem("Sample", "sample")
        self.view.addItem("Native", "native")
        for control in (self.view, self.quantity, self.condition):
            self.plot.toolbar.addWidget(control)
        self.time_slice = LinkedSliceControl(label="Delay", unit="ns", decimals=2)
        self.wavenumber_slice = LinkedSliceControl(label="Wavenumber", unit="cm⁻¹", decimals=3)
        self.result_note = QLabel()
        self.result_note.setWordWrap(True)
        self.result_layout.addWidget(self.plot, 1)
        self.result_layout.addWidget(self.time_slice)
        self.result_layout.addWidget(self.wavenumber_slice)
        self.result_layout.addWidget(self.result_note)
        self.result_ready.connect(self.show_result)
        self.run_loaded.connect(lambda result, _path: self.show_result(result))
        self.plot.error.connect(self.set_status)
        self.time_slice.index_changed.connect(self._slice_changed)
        self.wavenumber_slice.index_changed.connect(self._slice_changed)
        self.quantity.currentIndexChanged.connect(self._quantity_changed)
        self.condition.currentIndexChanged.connect(self._condition_changed)
        self.view.currentIndexChanged.connect(self._view_changed)
        self.operation_finished.connect(self._operation_finished)
        self.new_run_requested.connect(self._clear_results)
        self.busy_changed.connect(self._busy_transition)
        self.elapsed = QLabel("Idle")
        self.result_layout.addWidget(self.elapsed)
        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(500)
        self.clock_timer.timeout.connect(self._elapsed)
        self.refresh_readiness()

    def refresh_plan(self, *_):
        super().refresh_plan()
        if self.plan is not None:
            self.settings_widget.set_resolved(self.plan)

    def refresh_readiness(self, *_):
        super().refresh_readiness()
        if not hasattr(self, "record_status"):
            return
        idle = not self.command_running()
        valid = self.plan is not None
        for button in (self.acquire_blank_button, self.load_blank_button, self.load_preliminary_button):
            button.setEnabled(idle and valid)
        blank_ready = bool(valid and self.adapter.blank and not self.adapter.compatibility(self.adapter.blank, self.plan, kind="blank"))
        sample_ready = bool(valid and self.preliminary and not self.adapter.validate_preliminary(self.preliminary, self.plan))
        states = ["Blank ready"] if self.context.mode == "single" and blank_ready else []
        if sample_ready:
            states.append("Unpumped sample ready")
        self.record_status.setText(" · ".join(states))
        self.record_status.setVisible(bool(states))
        if self.context.mode == "single":
            self.preliminary_button.setEnabled(idle and valid and blank_ready)

    def begin(self, kind):
        self.adapter.freeze_inputs()
        return super().begin(kind)

    def begin_blank(self):
        if self.context.mode != "single":
            raise ValueError("Dual mode uses simultaneous reference acquisition")
        self.adapter.freeze_inputs()
        self.begin_operation("blank", self.adapter.run_blank)

    def load_reference(self, path, kind):
        if kind not in ("blank", "preliminary") or kind == "blank" and self.context.mode != "single":
            raise ValueError("Unsupported baseline kind")
        def load(snapshot, worker):
            worker.check_cancelled()
            record = self.adapter.load_run(Path(path))
            conflicts = self.adapter.compatibility(record, snapshot.plan, kind=kind)
            if conflicts:
                raise ValueError("; ".join(conflicts))
            return record
        self.begin_operation("load_" + kind, load)

    def _choose_reference(self, kind):
        path = QFileDialog.getExistingDirectory(self, "Load blank" if kind == "blank" else "Load unpumped sample", str(self.save_root_provider()))
        if path:
            self._user_action(lambda: self.load_reference(path, kind))

    def _operation_finished(self, kind, outcome):
        if outcome.state == "completed":
            result = outcome.result
            capabilities = result.get("readbacks", {}).get("capabilities") if isinstance(result, dict) else None
            if capabilities:
                self.adapter.capabilities = deepcopy(capabilities)
                QTimer.singleShot(0, self.refresh_plan)
            if kind in ("blank", "load_blank"):
                self.adapter.blank = result
                self.show_result(result)
            elif kind in ("preliminary", "load_preliminary"):
                self.preliminary = result
                self.show_result(result)
        elif kind in ("blank", "preliminary", "measurement") and self.adapter.last_result:
            self.result = self.adapter.last_result
            self.show_result(self.result)

    def show_result(self, result):
        reconstructed = result.get("result") or {}
        command_step = float(result.get("settings", {}).get("timing_step_ns", .01) or .01)
        self.time_slice.input.setDecimals(max(0, min(9, math.ceil(-math.log10(command_step)))))
        self.time_slice.set_coordinates(reconstructed.get("delays_ns", []))
        self.wavenumber_slice.set_coordinates(reconstructed.get("wavenumbers_cm1", []))
        self.condition.blockSignals(True)
        self.condition.clear()
        self.condition.addItem("Pump on", "pump_on")
        for condition in reconstructed.get("controls", {}):
            self.condition.addItem(condition.replace("_", " ").title(), condition)
        self.condition.blockSignals(False)
        self.plot_adapter.condition = self.condition.currentData()
        absolute_index = self.quantity.findData("absolute_absorbance")
        if reconstructed.get("absolute_available", False) and absolute_index < 0:
            self.quantity.addItem("Absorbance", "absolute_absorbance")
        elif not reconstructed.get("absolute_available", False) and absolute_index >= 0:
            self.quantity.removeItem(absolute_index)
        self.plot_adapter.time_index = self.time_slice.index
        self.plot_adapter.wavenumber_index = self.wavenumber_slice.index
        is_sample = result.get("kind") in ("blank", "preliminary")
        self.view.setCurrentIndex(self.view.findData("sample" if is_sample else "reconstruction"))
        self.plot.set_result(result)
        self._condition_changed()
        outcomes = reconstructed.get("fits", [])
        resolved = [item for item in outcomes if item.get("lifetime_ns") is not None]
        if resolved:
            self.result_note.setText(" · ".join(f"{item['wavenumber_cm1']:g} cm⁻¹: τ {item['lifetime_ns']:.3g} ns" for item in resolved))
        elif outcomes:
            self.result_note.setText("Lifetime unresolved")
        else:
            self.result_note.clear()
        if (result.get("settings", {}).get("execution_mode") == "simulation"
                or result.get("readbacks", {}).get("execution") == "simulation"):
            detail = self.result_note.text()
            self.result_note.setText("Example data" + (f" · {detail}" if detail else ""))
        self.result_note.setToolTip(str(result.get("output_path", result.get("native_path", ""))))

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

    def _view_changed(self, *_):
        self.plot_adapter.view = self.view.currentData()
        reconstruction = self.plot_adapter.view == "reconstruction"
        self.time_slice.setVisible(reconstruction)
        self.wavenumber_slice.setVisible(reconstruction)
        self.quantity.setVisible(reconstruction)
        self.condition.setVisible(reconstruction)
        if self.plot.result is not None:
            self.plot.reset_view()

    def _clear_results(self):
        self.plot.clear_result()
        self.time_slice.set_coordinates([])
        self.wavenumber_slice.set_coordinates([])
        self.result_note.clear()

    def instrument_state_changed(self, change):
        details = self.adapter.note_instrument_change(change)
        self.refresh_readiness()
        if self.preliminary is not None and self.plan is not None:
            conflicts = self.adapter.validate_preliminary(self.preliminary, self.plan)
            if conflicts:
                self.set_status("Baseline changed: " + details)
            elif not self.command_running():
                self.status.setText("Ready")

    def output_location_changed(self, path):
        self._next_root = Path(path)
        super().output_location_changed(path)

    def _busy_transition(self, busy):
        if busy:
            self._started = time.monotonic()
            self.clock_timer.start()
        else:
            self._elapsed()
            self.clock_timer.stop()

    def _elapsed(self):
        elapsed = 0 if self._started is None else time.monotonic() - self._started
        if not self.command_running():
            self.elapsed.setText(f"Elapsed {elapsed:.1f} s")
            return
        estimate = (self.plan.budget if self.plan else {}).get("total_s")
        remaining = f" · remaining ≈ {max(0, estimate - elapsed):.1f} s" if isinstance(estimate, (int, float)) else ""
        self.elapsed.setText(f"Elapsed {elapsed:.1f} s{remaining}")


def make_handle(context, *, title):
    panel = NanosecondPanel(context)
    return TabHandle(
        instance_id=context.instance_id, title=title, widget=panel,
        command_running=panel.command_running, close_blockers=panel.close_blockers,
        request_abort=panel.request_abort, output_location_changed=panel.output_location_changed,
        instrument_state_changed=panel.instrument_state_changed, state_changed=panel.busy_changed,
    )
