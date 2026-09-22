"""Compact single-pump tabs using the shared host measurement presentation."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
import json
from pathlib import Path

import numpy as np
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (QBoxLayout, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGridLayout, QLabel, QLineEdit, QWidget)

from control_app.measurement_host import TabHandle
from control_app.measurement_host.presentation import CompactMeasurementPanel, LinkedSliceControl, PlotPanel
from .adapter import BurstScientificAdapter
from .persistence import iter_chunks, json_value
from .settings import AUTOMATIC_FIELDS, Settings


ESSENTIALS = (
    ("scan_start_cm1", "Range start", " cm⁻¹", 1900., 1., 100000., 3),
    ("scan_stop_cm1", "Range stop", " cm⁻¹", 1950., 1., 100000., 3),
    ("scan_speed_cm1_s", "Scan speed", " cm⁻¹/s", 5000., .001, 10000000., 3),
    ("early_observation_s", "Early coverage", " s", 1., .000000001, 100000000., 9),
    ("observation_limit_s", "Total observation", " s", 1200., .001, 100000000., 3),
)
ADVANCED = (
    ("sample_rate_hz", "Sample rate (Hz)"), ("hf2_filter_order", "Filter order"),
    ("hf2_filter_tc_s", "Time constant (s)"), ("reference_rate_hz", "Reference rate (Hz)"),
    ("reference_filter_order", "Reference filter order"), ("reference_filter_tc_s", "Reference time constant (s)"),
    ("probe_rate_hz", "Repetition rate (kHz)"), ("probe_pulse_width_s", "Pulse width (ns)"),
    ("scans_per_burst", "Scans per burst"),
)
DISPLAY_SCALES = {"probe_rate_hz": 1e-3, "probe_pulse_width_s": 1e9}


def _override_text(name, value):
    if name in DISPLAY_SCALES:
        return f"{value * DISPLAY_SCALES[name]:.12g}"
    return str(value)


class _NumberInput(QDoubleSpinBox):
    def textFromValue(self, value):
        text = f"{value:.{self.decimals()}f}".rstrip("0").rstrip(".")
        return "0" if text in ("", "-0") else text


class BurstSettingsWidget(QWidget):
    changed = Signal()

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.controls = {}
        self._values = Settings(mode=context.mode).to_dict()
        self._values["qcl"] = 1
        self._types = {field.name: str(field.type) for field in fields(Settings)}
        self._labels = {name: label for name, label in ADVANCED}
        self._capabilities = None
        self.automatic_settings_restored = False
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)
        for name, label, unit, fallback, minimum, maximum, decimals in ESSENTIALS:
            control = _NumberInput()
            control.setObjectName(name)
            control.setRange(minimum, maximum)
            control.setDecimals(decimals)
            control.setSuffix(unit)
            control.setKeyboardTracking(False)
            control.setValue(self._values.get(name) or fallback)
            control.setSingleStep(100. if name == "scan_speed_cm1_s" else 1.)
            control.valueChanged.connect(self.changed)
            self.controls[name] = control
            form.addRow(label, control)
        self.advanced_widget = QWidget()
        advanced = QGridLayout(self.advanced_widget)
        advanced.setContentsMargins(0, 0, 0, 0)
        advanced.setHorizontalSpacing(5)
        advanced.setVerticalSpacing(4)
        self.override_controls = {}
        for name, label in ADVANCED:
            if context.mode == "single" and name.startswith("reference_"):
                continue
            control = QComboBox()
            control.setObjectName(name)
            control.setEditable(True)
            control.addItem("Automatic", None)
            value = self._values.get(name)
            if value is not None:
                control.addItem(_override_text(name, value), value)
                control.setCurrentIndex(1)
            control.setToolTip("Automatic uses the current scan and device settings. Enter an independent supported override.")
            control.currentTextChanged.connect(self.changed)
            self.controls[name] = self.override_controls[name] = control
        row = 0
        dual = context.mode == "dual"
        if dual:
            advanced.addWidget(QLabel("Sample"), row, 1)
            advanced.addWidget(QLabel("Reference"), row, 2)
            row += 1
        for label, sample_name, reference_name in (("Sample rate (Hz)", "sample_rate_hz", "reference_rate_hz"),
                ("Filter order", "hf2_filter_order", "reference_filter_order"),
                ("Time constant (s)", "hf2_filter_tc_s", "reference_filter_tc_s")):
            advanced.addWidget(QLabel(label), row, 0)
            advanced.addWidget(self.override_controls[sample_name], row, 1)
            if dual:
                advanced.addWidget(self.override_controls[reference_name], row, 2)
            row += 1
        for name, label in ADVANCED[-3:]:
            advanced.addWidget(QLabel(label), row, 0)
            advanced.addWidget(self.override_controls[name], row, 1, 1, 2 if dual else 1)
            row += 1
        advanced.setColumnStretch(1, 1)
        if dual:
            advanced.setColumnStretch(2, 1)
        for name in ("hf2_filter_order", "reference_filter_order"):
            if name in self.override_controls:
                self.override_controls[name].currentTextChanged.connect(self._refresh_timeconstant_choices)
        stored = context.preferences.value("settings", None)
        if stored:
            try:
                self.apply_settings(json.loads(stored) if isinstance(stored, str) else stored)
            except (ValueError, TypeError, KeyError):
                pass

    def read_settings(self):
        result = deepcopy(self._values)
        for name, control in self.controls.items():
            if isinstance(control, QDoubleSpinBox):
                value = control.value()
            else:
                raw = control.currentText().strip()
                if raw.lower() in ("", "automatic"):
                    value = None
                else:
                    try:
                        value = int(raw) if "int" in self._types.get(name, "") else float(raw) / DISPLAY_SCALES.get(name, 1.)
                    except ValueError as exc:
                        raise ValueError(f"Enter a number for {self._labels.get(name, name)} or choose Automatic.") from exc
            result[name] = value
        result["mode"] = self.context.mode
        return self.normalize_settings(result)

    def normalize_settings(self, settings):
        values = deepcopy(settings)
        for name in AUTOMATIC_FIELDS:
            if name not in self.controls:
                values[name] = None
        values["qcl"] = 1
        values["schedule_kind"] = "logarithmic"
        values["later_burst_times_s"] = ()
        return values

    def apply_settings(self, settings):
        if settings.get("mode", self.context.mode) != self.context.mode:
            raise ValueError("Choose a plan saved from this detector mode.")
        names = {field.name for field in fields(Settings)}
        self.automatic_settings_restored = bool(settings.get("example_only") or settings.get("_execution") == "simulated")
        if self.automatic_settings_restored:
            # Old example files remain untouched. Carry requested coverage into
            # the live UI, then select current automatic device settings.
            settings = {key: settings[key] for key in ({item[0] for item in ESSENTIALS} | {"mode"}) if key in settings}
        settings = self.normalize_settings(settings)
        values = Settings.from_dict({key: value for key, value in settings.items() if key in names}).to_dict()
        self._values = values
        for name, control in self.controls.items():
            value = values.get(name)
            control.blockSignals(True)
            if isinstance(control, QDoubleSpinBox):
                if value is not None:
                    control.setValue(value)
            else:
                control.setCurrentIndex(0)
                if value is not None:
                    control.setEditText(_override_text(name, value))
            control.blockSignals(False)
        self.changed.emit()

    def set_capabilities(self, capabilities):
        self._capabilities = capabilities
        for name, attribute in (("sample_rate_hz", "sample_rates_hz"),
                                ("reference_rate_hz", "reference_rates_hz"),
                                ("hf2_filter_order", "sample_filter_orders"),
                                ("reference_filter_order", "reference_filter_orders")):
            self._set_choices(name, getattr(capabilities, attribute, ()))
        self._refresh_timeconstant_choices()

    def _set_choices(self, name, values):
        control = self.override_controls.get(name)
        if control is None:
            return
        text = control.currentText()
        control.blockSignals(True)
        control.clear()
        control.addItem("Automatic", None)
        for value in values:
            control.addItem(_override_text(name, value), value)
        control.setEditText(text)
        control.blockSignals(False)

    def _refresh_timeconstant_choices(self, *_):
        if self._capabilities is None:
            return
        for order_name, tc_name, attribute in (("hf2_filter_order", "hf2_filter_tc_s", "sample_timeconstants_by_order"),
                ("reference_filter_order", "reference_filter_tc_s", "reference_timeconstants_by_order")):
            control = self.override_controls.get(order_name)
            if control is None:
                continue
            by_order = getattr(self._capabilities, attribute, {})
            try:
                order = int(control.currentText())
            except ValueError:
                order = min((int(key) for key in by_order), default=1)
            self._set_choices(tc_name, by_order.get(order, by_order.get(str(order), ())))


def _display_points(result, limit=100000, *, native_only=False):
    """A bounded display copy; no averaging, timing substitution or gap filling."""
    if not isinstance(result, dict):
        result = json_value(result)
    data = result.get("data", result)
    if not isinstance(data, dict):
        data = result
    sources = data.get("processed")
    block_count = 1
    if sources is None:
        native = data.get("native")
        if native is not None:
            sources = native
        elif result.get("output_path") or result.get("path"):
            path = Path(result.get("output_path", result.get("path")))
            names = result.get("chunks", ())
            processed = [name for name in names if Path(name).name.startswith("processed-")]
            spectral = [name for name in names if Path(name).name.startswith(("spectral-", "unpumped-"))]
            names = (spectral or names) if native_only else (processed or spectral or names)
            block_count = max(1, len(names))
            def read_paths():
                for name in names:
                    target = (path / name).resolve()
                    if not target.is_relative_to(path.resolve()):
                        raise ValueError("Native display path escapes retained run")
                    with np.load(target, allow_pickle=False) as chunk:
                        yield {key: chunk[key] for key in chunk.files}
            sources = read_paths() if names else iter_chunks(path)
        else:
            sources = data
    if isinstance(sources, dict):
        sources = (sources,)
    output = {key: [] for key in ("time", "wavenumber", "signal", "sample", "reference", "ratio", "scan", "burst", "direction")}
    labels = []
    truncated = False
    per_block_limit = max(1, limit//block_count)
    epoch = result.get("epoch") or result.get("manifest", {}).get("epoch") or {}
    epoch_s = epoch.get("pump_time_s")
    transmission_available = False
    for block_number, source in enumerate(sources):
        if not isinstance(source, dict):
            continue
        times = np.asarray(source.get("time_s", source.get("sample_time_s", ())), dtype=float).reshape(-1)
        if "time_s" not in source and epoch_s is not None:
            ticks = source.get("native_sample_ticks")
            pump_tick = source.get("pump_timestamp_ticks", epoch.get("pump_timestamp_ticks"))
            clockbase = source.get("clockbase_hz", epoch.get("clockbase_hz"))
            if ticks is not None and pump_tick is not None and clockbase is not None:
                origin = int(np.asarray(pump_tick).item())
                times = np.fromiter((int(tick)-origin for tick in np.asarray(ticks).reshape(-1)), dtype=float) / float(np.asarray(clockbase).item())
                times -= float(np.asarray(source.get("pump_optical_offset_s", epoch.get("optical_offset_s", 0.))).item())
            else:
                times = times - float(epoch_s)
        wn = np.asarray(source.get("wavenumber_cm1", ()), dtype=float).reshape(-1)
        if not len(times) or not len(wn):
            continue
        # Quantitative labels are conditional on actual retained quantities.
        if source.get("delta_absorbance") is not None:
            values, label = source["delta_absorbance"], "ΔAbsorbance"
        elif source.get("ratio") is not None:
            values, label = source["ratio"], "Reference-normalized signal Q = S/R"
        else:
            values, label = source.get("sample", ()), "Sample signal S"
        transmission_available |= source.get("transmission") is not None
        values = np.asarray(values, dtype=float)
        if values.ndim == 2 and values.shape == (len(times), len(wn)):
            wn = np.tile(wn, len(times))
            times = np.repeat(times, values.shape[1])
        values = values.reshape(-1)
        n = min(len(times), len(wn), len(values))
        if not n:
            continue
        mapping = {"time": times[:n], "wavenumber": wn[:n], "signal": values[:n]}
        for name, fallback in (("sample", np.nan), ("reference", np.nan), ("ratio", np.nan), ("scan", block_number),
                               ("burst", block_number), ("direction", 0)):
            original = source.get({"scan": "scan_index", "burst": "burst_index"}.get(name, name), fallback)
            array = np.asarray(original)
            if array.ndim == 0:
                array = np.full(n, original)
            mapping[name] = array.reshape(-1)[:n] if array.size >= n else np.full(n, fallback)
        valid = np.asarray(source.get("valid", np.ones(n, bool))).reshape(-1)
        if len(valid) >= n:
            mapping["signal"] = np.where(valid[:n], mapping["signal"], np.nan)
        if n > per_block_limit:
            indices = np.unique(np.linspace(0, n-1, per_block_limit, dtype=int))
            mapping = {key: value[indices] for key, value in mapping.items()}
            truncated = True
        for key in output:
            output[key].append(mapping[key])
        labels.append(label)
    output = {key: np.concatenate(values) if values else np.asarray([]) for key, values in output.items()}
    output["label"] = labels[0] if labels and len(set(labels)) == 1 else "Recorded signal"
    output["truncated"] = truncated
    output["events"] = result.get("events", [])
    output["metadata"] = result.get("metadata", {})
    output["summary"] = result.get("summary") or result.get("manifest", {}).get("summary", {})
    reference = output["summary"].get("time_reference")
    if not reference and epoch_s is not None:
        reference = "optical_arrival" if epoch.get("independently_observed") else "electrical_trigger" if epoch.get("electrical_observed") else "retained_epoch"
    output["time_label"] = {"optical_arrival": "Time from optical arrival (s)", "electrical_trigger": "Time from trigger (s)",
                            "retained_epoch": "Time from retained epoch (s)"}.get(reference, "Native time (s)")
    output["ratio_label"] = ("Q = S/R" if output["metadata"].get("mode") == "dual" else
                             "Transmission" if transmission_available else "Sample signal S")
    selected = output["metadata"].get("actual_settings", output["metadata"].get("settings", {}))
    output["wavenumber_tolerance_cm1"] = selected.get("wavenumber_matching_tolerance_cm1") or 0.
    return output


class BurstPlotAdapter:
    def __init__(self):
        self.view = "Early linear kinetics"
        self.time_index = 0
        self.wavenumber_index = 0
        self.times = np.asarray([])
        self.wavenumbers = np.asarray([])

    def draw(self, figure, result):
        points = result if "signal" in result and "wavenumber" in result else _display_points(result)
        axes = figure.add_subplot(111)
        t, w, y = (np.asarray(points[key]) for key in ("time", "wavenumber", "signal"))
        if not len(t):
            axes.text(.5, .5, "No data", ha="center", transform=axes.transAxes)
            return
        quantity = points["label"]
        if self.view in ("Early linear kinetics", "Positive-time logarithmic kinetics", "Reference-normalized Q", "Sample signal / transmission"):
            chosen = self.wavenumbers[min(self.wavenumber_index, len(self.wavenumbers)-1)] if len(self.wavenumbers) else w[0]
            mask = np.zeros(len(w), dtype=bool)
            tolerance = max(1e-8, float(points.get("wavenumber_tolerance_cm1", 0.)))
            for scan in np.unique(points["scan"]):
                indices = np.flatnonzero((points["scan"] == scan) & np.isfinite(w) & np.isfinite(t))
                if len(indices):
                    index = indices[np.argmin(np.abs(w[indices]-chosen))]
                    if abs(w[index]-chosen) <= tolerance:
                        mask[index] = True
            if self.view == "Early linear kinetics":
                # Show the informative continuous first train at useful scale;
                # long waits belong to the separately selected logarithmic view.
                burst_ids = np.asarray(points["burst"])
                finite_bursts = burst_ids[np.isfinite(burst_ids)]
                if len(finite_bursts):
                    mask &= (burst_ids == np.min(finite_bursts)) | (t <= 0)
            if self.view.startswith("Positive"):
                mask &= t > 0
                axes.set_xscale("log")
            if self.view in ("Reference-normalized Q", "Sample signal / transmission"):
                y = np.asarray(points["ratio"])
                quantity = points["ratio_label"]
            # Markers avoid inventing support over sparse inter-burst gaps.
            axes.plot(t[mask], y[mask], ".", label=f"{chosen:.6g} cm⁻¹")
            axes.set(xlabel=points.get("time_label", "Observed elapsed time (s)"), ylabel=quantity)
            axes.legend(loc="best")
        elif self.view == "Supported spectral map":
            good = np.isfinite(t) & np.isfinite(w) & np.isfinite(y)
            image = axes.scatter(w[good], t[good], c=y[good], s=7, cmap="viridis")
            figure.colorbar(image, ax=axes, label=quantity)
            axes.set(xlabel="Observed wavenumber (cm⁻¹)", ylabel="Observed elapsed time (s)")
            axes.invert_xaxis()
        elif self.view == "Measured spectral slice":
            # Time selector picks a measured scan by its actual first point;
            # every point retains its own wavelength/time trajectory.
            ids = np.unique(points["scan"])
            chosen = ids[min(self.time_index, len(ids)-1)]
            mask = points["scan"] == chosen
            axes.plot(w[mask], y[mask], ".")
            axes.set(xlabel="Observed wavenumber (cm⁻¹)", ylabel=quantity,
                     title=f"Native scan {chosen}; elapsed {np.min(t[mask]):.9g} to {np.max(t[mask]):.9g} s")
            axes.invert_xaxis()
        elif self.view == "Native trajectory and direction":
            for direction in np.unique(points["direction"]):
                mask = points["direction"] == direction
                axes.plot(t[mask], w[mask], ".", label=f"Direction {direction}")
            axes.set(xlabel="Native point time (s)", ylabel="Observed wavenumber (cm⁻¹)")
            axes.legend()
        elif self.view == "Native detector streams":
            axes.plot(t, points["sample"], ".", markersize=2, label="Native sample")
            if np.isfinite(points["reference"]).any():
                axes.plot(t, points["reference"], ".", markersize=2, label="Native matched reference")
            axes.set(xlabel=points.get("time_label", "Native time (s)"), ylabel="HF2LI magnitude (instrument units)")
            axes.legend()
        elif self.view == "Scan-burst timeline":
            for burst in np.unique(points["burst"]):
                mask = points["burst"] == burst
                axes.plot(t[mask], points["scan"][mask], "|", label=f"Burst {burst}")
            axes.set(xlabel="Observed elapsed time (s); gaps are unobserved", ylabel="Native scan index")
        elif self.view == "Band plateaus and unrecovered fractions":
            summary = points.get("summary", {})
            bands = summary.get("bands", summary.get("analysis", {}).get("bands", []))
            if bands:
                labels, fractions = [], []
                for band in bands:
                    lo, hi = band["band_cm1"]
                    labels.append(f"{lo:g}–{hi:g} cm⁻¹\n" + ("plateau" if band.get("plateau") else "right-censored / unresolved"))
                    fractions.append(band.get("unrecovered_fraction"))
                for index, value in enumerate(fractions):
                    if value is not None:
                        axes.bar(index, value)
                    else:
                        axes.text(index, 0, "Unresolved", ha="center")
                axes.set_xticks(range(len(labels)), labels)
                axes.set_ylabel("Unrecovered fraction of first observed band signal")
            else:
                axes.text(.5, .5, "No band summary", ha="center", transform=axes.transAxes)
            figure.text(.02, .01, "Recovery on observed support; incomplete recovery is retained.", fontsize=8)
        else:
            events = points.get("events", [])
            entries = [e.get("payload", {}) for e in events]
            key = "temperature_k" if self.view == "Temperature history" else "probe_exposure_s"
            times, values = [], []
            basis = "Observed elapsed time (s)"
            from datetime import datetime
            started = points.get("metadata", {}).get("operation", {}).get("started_utc")
            for event in entries:
                if event.get(key) is None:
                    continue
                elapsed = event.get("elapsed_s")
                if elapsed is None and started and event.get("observed_utc"):
                    elapsed = (datetime.fromisoformat(event["observed_utc"].replace("Z", "+00:00")) - datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds()
                    basis = "Wall time from operation start (s); recorded temperature timestamps"
                if elapsed is not None:
                    times.append(elapsed)
                    values.append(event[key])
            if values:
                axes.plot(times, values, ".")
            else:
                axes.text(.5, .5, "No recorded history", ha="center", transform=axes.transAxes)
            axes.set(xlabel=basis, ylabel="Temperature (K)" if key == "temperature_k" else "Probe exposure (s)")
        if self.view != "Measured spectral slice":
            axes.set_title(self.view)
        axes.grid(alpha=.2)
        if points.get("truncated"):
            figure.text(.02, .01, "Bounded display sampling includes every burst; native files preserve every observed point.", fontsize=8)
        figure.tight_layout()


class SinglePumpScanBurstWidget(CompactMeasurementPanel):
    def __init__(self, context, parent=None, *, runner_factory=None, hardware=True):
        settings = BurstSettingsWidget(context)
        adapter = BurstScientificAdapter(context, settings, runner_factory=runner_factory, hardware=hardware)
        self._initializing = True
        super().__init__(settings, adapter, context, parent, advanced_widget=settings.advanced_widget)
        self._initializing = False
        self.splitter.setSizes((390, 686))
        self.settings_layout.setContentsMargins(6, 6, 6, 6)
        self.settings_layout.setSpacing(4)
        self.left_layout.setSpacing(4)
        self.action_layout.setSpacing(4)
        self.file_layout.setDirection(QBoxLayout.Direction.LeftToRight)
        self.blank_actions_layout.setDirection(QBoxLayout.Direction.LeftToRight)
        self._points = self._native_points = None
        self._next_root = context.save_root()
        self._capability_check_attempted = False
        settings.changed.connect(self._settings_changed)
        self.preliminary_button.setText("Acquire unpumped sample")
        self.start_button.setText("Start pump sequence")
        self.abort_button.setText("Abort")
        self.blank_button = self.load_blank_button = None
        if context.mode == "single":
            self.blank_button = self.add_blank_action("Acquire blank", self.begin_blank)
            self.load_blank_button = self.add_blank_action("Load blank…", self._choose_blank)
        self.plot_adapter = BurstPlotAdapter()
        self.plot = PlotPanel(self.plot_adapter)
        self.plot.canvas.setMinimumHeight(220)
        self.plot.error.connect(self.status.setText)
        self.views = QComboBox()
        self.views.addItems(("Early linear kinetics", "Positive-time logarithmic kinetics", "Scan-burst timeline",
            "Supported spectral map", "Measured spectral slice", "Native trajectory and direction",
            "Native detector streams", "Reference-normalized Q" if context.mode == "dual" else "Sample signal / transmission",
            "Probe-duty history", "Band plateaus and unrecovered fractions"))
        self.views.currentTextChanged.connect(self._view_changed)
        self.time_slice = LinkedSliceControl(label="Time", unit="s", decimals=9)
        self.wavenumber_slice = LinkedSliceControl(label="Wavenumber", unit="cm⁻¹", decimals=6)
        self.time_slice.hide()
        self.wavenumber_slice.hide()
        self.time_slice.index_changed.connect(self._time_changed)
        self.wavenumber_slice.index_changed.connect(self._wavenumber_changed)
        self.result_layout.addWidget(self.views)
        self.result_layout.addWidget(self.time_slice)
        self.result_layout.addWidget(self.wavenumber_slice)
        self.result_layout.addWidget(self.plot, 1)
        self.result_ready.connect(self._show_result)
        self.run_loaded.connect(lambda result, _path: self._show_result(result))
        self.new_run_requested.connect(self._clear_results)
        self.busy_changed.connect(self._operation_state)
        self.operation_finished.connect(self._operation_finished)
        self.refresh_readiness()
        if settings.automatic_settings_restored:
            self.status.setText("Automatic device settings restored.")

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._ensure_capabilities)

    def _ensure_capabilities(self):
        if self._capability_check_attempted or self.command_running() or not self.adapter.hardware:
            return
        if "hf2li" in self.context.devices.available(hardware=True):
            self._user_action(self.begin_capabilities)

    def _settings_changed(self):
        self.refresh_plan()
        try:
            self.context.preferences.setValue("settings", json.dumps(self.adapter.read_settings()))
            self.context.preferences.sync()
        except (ValueError, TypeError):
            pass

    def refresh_plan(self, *_):
        super().refresh_plan()
        if not self._initializing and self.plan is not None:
            self._reuse_preliminary()

    def _reuse_preliminary(self):
        if self.plan is not None:
            current = self.preliminary
            if current is None or self.adapter.validate_preliminary(current, self.plan):
                self.preliminary = self.adapter.compatible_preliminary(self.plan)
        self.refresh_readiness()

    def begin_blank(self):
        self.begin_operation("baseline", self.adapter.run_blank)

    def begin_capabilities(self):
        from control_app.measurement_host.ownership import OwnershipError
        try:
            self.begin_operation("capabilities", self.adapter.run_capabilities, requires_valid_plan=False)
        except OwnershipError as exc:
            self.set_status("Instrument busy. Check device after the current operation finishes.")
            self.status.setToolTip(str(exc))
            return
        self._capability_check_attempted = True

    def begin(self, kind):
        if kind == "measurement" and self.preliminary is not None:
            self.preliminary["_dispatch_blank"] = (self.adapter._record_reference(self.adapter.blank)
                if not self.adapter.blank_conflicts(self.plan) else None)
        super().begin(kind)

    def _operation_finished(self, kind, outcome):
        if outcome.state != "completed":
            if outcome.state == "cancelled":
                self.status.setText("Acquisition stopped. Partial data retained.")
            return
        result = outcome.result
        if isinstance(result, dict) and result.get("capabilities"):
            from .settings import Capabilities
            self.adapter.capabilities = Capabilities.from_dict(result["capabilities"])
            self.settings_widget.set_capabilities(self.adapter.capabilities)
            self.refresh_plan()
        if kind in ("baseline", "load_blank"):
            self.adapter.blank = result
            self._reuse_preliminary()
            self.status.setText("Blank ready. Load the sample.")
            self._show_result(result)
        elif kind == "preliminary":
            self.adapter.retain_preliminary(result)
            self._reuse_preliminary()
            self._show_result(result)
            self.status.setText("Sample ready.")
        elif kind == "load_run" and result.get("status") in ("complete", "completed"):
            source_kind = result.get("metadata", {}).get("kind")
            if source_kind in ("preliminary", "baseline"):
                result["complete"] = True
                if source_kind == "preliminary":
                    self.adapter.retain_preliminary(result)
                elif self.context.mode == "single":
                    self.adapter.blank = result
                self._reuse_preliminary()
                if source_kind == "preliminary" and self.preliminary is result:
                    self.status.setText("Sample loaded and ready.")
        elif kind == "capabilities":
            self.status.setText("Device settings updated.")
        elif kind == "load_plan" and self.settings_widget.automatic_settings_restored:
            self.status.setText("Automatic device settings restored.")
        self.refresh_readiness()

    def _choose_blank(self):
        path = QFileDialog.getExistingDirectory(self, "Load blank", str(self._next_root))
        if path:
            self.load_blank(Path(path))

    def load_blank(self, path):
        self.begin_operation("load_blank", lambda snapshot, worker: self.adapter.load_blank(path, snapshot.plan))

    def _show_result(self, result):
        self._points = result.get("display_points")
        self._native_points = result.get("native_display_points")
        if self._points is None:
            self._points = _display_points(result)
        points = self._points
        if len(points["time"]):
            self.time_slice.show()
            self.wavenumber_slice.show()
            scans = np.unique(points["scan"])
            times = np.asarray([points["time"][points["scan"] == scan][0] for scan in scans])
            wavenumbers = np.unique(points["wavenumber"][np.isfinite(points["wavenumber"])])
            self.plot_adapter.times, self.plot_adapter.wavenumbers = times, wavenumbers
            self.time_slice.set_coordinates(times)
            self.wavenumber_slice.set_coordinates(wavenumbers)
        self._view_changed(self.views.currentText())

    def _view_changed(self, view):
        self.plot_adapter.view = view
        selected = self._native_points if view in ("Native detector streams", "Native trajectory and direction") else self._points
        self.plot.set_result(selected)

    def _time_changed(self, index):
        self.plot_adapter.time_index = index
        self.plot.reset_view()

    def _wavenumber_changed(self, index):
        self.plot_adapter.wavenumber_index = index
        self.plot.reset_view()

    def _clear_results(self):
        self._points = self._native_points = None
        self.plot.clear_result()
        self.time_slice.set_coordinates(())
        self.wavenumber_slice.set_coordinates(())
        self.time_slice.hide()
        self.wavenumber_slice.hide()

    def _operation_state(self, busy):
        self.context.lifecycle.notify_state(busy, "single-pump observation" if busy else "idle")

    def output_location_changed(self, path):
        self._next_root = Path(path)
        super().output_location_changed(path)

    def instrument_state_changed(self, change):
        self._capability_check_attempted = False
        self.status.setText("Device settings changed. They will be checked before acquisition.")
        if not self.command_running():
            self._ensure_capabilities()


def make_handle(context, *, title):
    widget = SinglePumpScanBurstWidget(context)
    return TabHandle(instance_id=context.instance_id, title=title, widget=widget,
        command_running=widget.command_running, close_blockers=widget.close_blockers,
        request_abort=widget.request_abort, output_location_changed=widget.output_location_changed,
        instrument_state_changed=widget.instrument_state_changed, state_changed=widget.busy_changed)
