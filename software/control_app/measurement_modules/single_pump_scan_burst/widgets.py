"""The two independent top-level tabs and native scan-burst views.

The host supplies the worker, review/start interaction, file controls, toolbar
and measured-coordinate navigation. Scientific settings and rendering stay here.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
import json
from pathlib import Path

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QToolBox, QVBoxLayout, QWidget)

from control_app.measurement_host import TabHandle
from control_app.measurement_host.presentation import (
    GuidedMeasurementPanel, LinkedSliceControl, PlotPanel, StartSnapshot,
)
from .adapter import BurstScientificAdapter
from .persistence import iter_chunks, json_value
from .settings import CONDITION_PROFILES, Settings, example_settings


_LABELS = {
    "condition_id": "Condition profile", "measured_temperature_k": "Illuminated sample temperature (K)",
    "temperature_uncertainty_k": "Temperature uncertainty (K)", "scan_start_cm1": "Scan start (cm⁻¹)",
    "scan_stop_cm1": "Scan stop (cm⁻¹)", "scan_speed_cm1_s": "Useful scan speed (cm⁻¹/s)",
    "scan_interval_s": "Individual scan spacing (s)", "first_scan_delay_s": "First scan after pump (s)",
    "first_later_burst_s": "First later burst (s)", "observation_limit_s": "Observation limit (s)",
    "later_burst_times_s": "Information-based burst times (s, JSON array)",
    "plateau_band_windows_cm1": "Band windows (cm⁻¹, JSON pairs)",
    "max_probe_exposure_s": "Total probe exposure budget (s)",
    "hardware_evidence": "Installed capability / qualification evidence (JSON)",
    "settings_sources": "Operating-value source record IDs (JSON)",
}


def _label(name):
    if name in _LABELS:
        return _LABELS[name]
    for suffix, unit in (("_cm1_s", "cm⁻¹/s"), ("_cm1", "cm⁻¹"), ("_hz", "Hz"),
                         ("_bytes", "bytes"), ("_s", "s"), ("_k", "K"), ("_v", "V"), ("_ma", "mA")):
        if name.endswith(suffix):
            return name[:-len(suffix)].replace("_", " ").capitalize() + " (" + unit + ")"
    return name.replace("_", " ").capitalize()


class BurstSettingsWidget(QWidget):
    changed = Signal()
    sample_selection_requested = Signal()
    bundles_requested = Signal()

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.controls = {}
        self._values = Settings(mode=context.mode).to_dict()
        layout = QVBoxLayout(self)
        self.execution = QComboBox()
        self.execution.addItem("Connected instruments", "connected")
        self.execution.addItem("Simulation — no physical devices", "simulated")
        self.execution.currentIndexChanged.connect(self.changed)
        layout.addWidget(self.execution)
        note = QLabel("One pump per accepted sample state. Load the sample and matched matrix/cell, record the measured sample temperature, then acquire stationary preliminary spectra. Physical sample exchange is guided; no position stage or thermal reset is assumed.")
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        self.selection_button = QPushButton("Load accepted sample selection…")
        self.selection_button.clicked.connect(self.sample_selection_requested)
        self.bundles_button = QPushButton("Resolve promoted settings")
        self.bundles_button.clicked.connect(self.bundles_requested)
        row.addWidget(self.selection_button)
        row.addWidget(self.bundles_button)
        layout.addLayout(row)
        groups = {name: QFormLayout() for name in (
            "Sample and cryogenic state", "Rapid scans and later bursts", "Temperature and probe duty",
            "HF2LI sample and reference", "Pump and probe timing", "Plateau stopping rule",
            "Controls, calibration and evidence", "Wall time and storage estimates")}
        book = QToolBox()
        self.sections = book
        layout.addWidget(book)
        fixed = {"mode", "schema_version", "experiment_id"}
        for field in fields(Settings):
            name, value = field.name, self._values[field.name]
            if name in fixed:
                continue
            if name == "condition_id":
                control = QComboBox()
                for condition, profile in CONDITION_PROFILES.items():
                    control.addItem(condition + " / " + profile["architecture_id"], condition)
                control.currentIndexChanged.connect(self.changed)
            elif name in ("schedule_kind", "pump_polarity", "process_polarity"):
                control = QComboBox()
                for choice in (("logarithmic", "information_based") if name == "schedule_kind" else ("positive", "negative")):
                    control.addItem(choice, choice)
                control.currentIndexChanged.connect(self.changed)
            elif isinstance(value, bool):
                control = QCheckBox()
                control.setChecked(value)
                control.toggled.connect(self.changed)
            else:
                control = QLineEdit()
                control.setText(self._text(value))
                if value is None:
                    control.setPlaceholderText("Required source/readback or justified override")
                if "dict" in str(field.type) or "tuple" in str(field.type):
                    control.setToolTip("Enter valid JSON. Empty arrays/objects explicitly mean no selected evidence.")
                elif "float" in str(field.type):
                    control.setToolTip("Explicit SI units shown in label. Scientific notation is supported (e.g. 1e-9 s). Blank is unresolved.")
                control.textChanged.connect(self.changed)
            control.setObjectName(name)
            self.controls[name] = control
            groups[self._group(name)].addRow(_label(name), control)
        for title, form in groups.items():
            page = QWidget()
            page.setLayout(form)
            book.addItem(page, title)
        example = QPushButton("Load EXAMPLE ONLY simulation plan")
        example.setToolTip("Nonbiological synthetic verification settings; not an established operating recipe.")
        example.clicked.connect(self.load_example)
        layout.addWidget(example)
        layout.addStretch()
        stored = context.preferences.value("settings", None)
        if stored:
            try:
                self.apply_settings(json.loads(stored) if isinstance(stored, str) else stored)
            except (ValueError, TypeError, KeyError):
                note.setText(note.text() + " Saved preferences were incompatible; settings require review.")

    @staticmethod
    def _group(name):
        if name.startswith("plateau"):
            return "Plateau stopping rule"
        if name in {"configuration_time_s", "tuning_settling_time_s", "controls_time_s", "restoration_time_s", "processing_time_s", "upload_seconds_per_frame", "native_chunk_duration_s", "max_memory_bytes", "storage_budget_bytes"}:
            return "Wall time and storage estimates"
        if name.startswith(("sample_rate", "reference_", "timing_rate", "sample_demod", "timing_demod", "hf2_", "sample_input")):
            return "HF2LI sample and reference"
        if name.startswith(("calibration", "promoted", "controls_", "settings_sources", "hardware_evidence", "sample_selection", "example")):
            return "Controls, calibration and evidence"
        if name.startswith(("scan", "first_", "early_", "later_", "final_", "schedule", "observation", "preliminary")):
            return "Rapid scans and later bursts"
        if name.startswith(("min_temperature", "max_temperature", "temperature_check", "max_probe", "probe_during")):
            return "Temperature and probe duty"
        if name.startswith(("pump", "probe", "process")) or name == "qcl":
            return "Pump and probe timing"
        return "Sample and cryogenic state"

    @staticmethod
    def _text(value):
        if value is None:
            return ""
        return json.dumps(value) if isinstance(value, (tuple, list, dict)) else str(value)

    def read_settings(self):
        result = deepcopy(self._values)
        for field in fields(Settings):
            name = field.name
            if name not in self.controls:
                continue
            control = self.controls[name]
            if isinstance(control, QComboBox):
                value = control.currentData()
            elif isinstance(control, QCheckBox):
                value = control.isChecked()
            else:
                raw = control.text().strip()
                type_name = str(field.type)
                try:
                    if "tuple" in type_name or "dict" in type_name:
                        value = json.loads(raw)
                    elif "float" in type_name:
                        value = float(raw) if raw else None
                    elif "int" in type_name:
                        value = int(raw) if raw else None
                    else:
                        value = raw
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"{_label(name)}: enter a valid value") from exc
            result[name] = value
        result["mode"] = self.context.mode
        result["_execution"] = self.execution.currentData()
        return result

    def apply_settings(self, settings):
        if settings.get("mode", self.context.mode) != self.context.mode:
            raise ValueError("Incompatible detector mode")
        names = {field.name for field in fields(Settings)}
        values = Settings.from_dict({key: value for key, value in settings.items() if key in names}).to_dict()
        self._values = values
        for name, control in self.controls.items():
            control.blockSignals(True)
            if isinstance(control, QComboBox):
                index = control.findData(values[name])
                if index < 0:
                    control.addItem(str(values[name]), values[name])
                    index = control.count()-1
                control.setCurrentIndex(index)
            elif isinstance(control, QCheckBox):
                control.setChecked(values[name])
            else:
                control.setText(self._text(values[name]))
            control.blockSignals(False)
        self.execution.blockSignals(True)
        self.execution.setCurrentIndex(max(0, self.execution.findData(settings.get("_execution", "connected"))))
        self.execution.blockSignals(False)
        self.changed.emit()

    def load_example(self):
        self.apply_settings({**example_settings(self.context.mode).to_dict(), "_execution": "simulated"})


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
    for block_number, source in enumerate(sources):
        if not isinstance(source, dict):
            continue
        times = np.asarray(source.get("time_s", source.get("sample_time_s", ())), dtype=float).reshape(-1)
        if "time_s" not in source and epoch_s is not None:
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
            values, label = source.get("sample", ()), "Native HF2LI sample signal"
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
    output["label"] = labels[0] if labels and len(set(labels)) == 1 else "Retained signal (see native metadata)"
    output["truncated"] = truncated
    output["events"] = result.get("events", [])
    output["metadata"] = result.get("metadata", {})
    output["summary"] = result.get("summary") or result.get("manifest", {}).get("summary", {})
    output["time_label"] = "Observed elapsed time from retained pump epoch (s)" if epoch_s is not None or "processed" in data else "Native HF2LI timestamp (s); unpumped/epoch unavailable"
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
            axes.text(.5, .5, "No supported native points retained", ha="center", transform=axes.transAxes)
            return
        quantity = points["label"]
        if self.view in ("Early linear kinetics", "Positive-time logarithmic kinetics", "Reference-normalized Q"):
            chosen = self.wavenumbers[min(self.wavenumber_index, len(self.wavenumbers)-1)] if len(self.wavenumbers) else w[0]
            mask = np.isclose(w, chosen, rtol=0, atol=1e-8) & np.isfinite(t)
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
            if self.view == "Reference-normalized Q":
                y = np.asarray(points["ratio"])
                quantity = "Reference-normalized Q = S/R" if points.get("metadata", {}).get("mode") == "dual" else "Sample / sequential blank"
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
                axes.text(.5, .5, "No supported accepted band-population summary retained", ha="center", transform=axes.transAxes)
            figure.text(.02, .01, "Apparent cryogenic recovery; independent escape evidence is not established.", fontsize=8)
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
                axes.text(.5, .5, "No observed history available in this record", ha="center", transform=axes.transAxes)
            axes.set(xlabel=basis, ylabel="Temperature (K)" if key == "temperature_k" else "Probe exposure (s)")
        if self.view != "Measured spectral slice":
            axes.set_title(self.view)
        axes.grid(alpha=.2)
        if points.get("truncated"):
            figure.text(.02, .01, "Bounded display sampling includes every burst; native files preserve every observed point.", fontsize=8)
        figure.tight_layout()


class SinglePumpScanBurstWidget(GuidedMeasurementPanel):
    def __init__(self, context, parent=None, *, runner_factory=None):
        settings = BurstSettingsWidget(context)
        adapter = BurstScientificAdapter(context, settings, runner_factory=runner_factory)
        self._initializing = True
        super().__init__(settings, adapter, context, parent)
        self._initializing = False
        self._points = None
        self._native_points = None
        self._next_root = context.save_root()
        settings.changed.connect(self._settings_changed)
        settings.sample_selection_requested.connect(self._choose_sample_selection)
        settings.bundles_requested.connect(lambda: self._user_action(self._resolve_bundles))
        self.preliminary_button.setText("2 · Acquire sample/reference preliminary (pump OFF)" if context.mode == "dual" else "2 · Acquire sample preliminary (pump OFF)")
        self.start_button.setText("3 · Start one-pump observation")
        self.abort_button.setText("Abort acquisition")
        self.blank_status = QLabel("Concurrent matched-buffer reference supplies Q; review unpumped Q₀." if context.mode == "dual" else "Load the matched matrix/cell blank, then acquire or load its complete control record.")
        self.blank_status.setWordWrap(True)
        self.blank_button = QPushButton("1 · Acquire sequential blank/control")
        self.load_blank_button = QPushButton("Select saved blank…")
        self.capabilities_button = QPushButton("Check connected devices")
        self.capabilities_button.setToolTip("Owned device readbacks and restoration; no optical acquisition or pump.")
        self.capabilities_button.clicked.connect(lambda: self._user_action(self.begin_capabilities))
        self.layout().insertWidget(1, self.capabilities_button)
        self.details_button = QPushButton("Plan details and readiness…")
        self.details_button.clicked.connect(lambda: self._user_action(self.show_plan_details))
        self.layout().insertWidget(2, self.details_button)
        self.continue_button = QPushButton("Continue retained observation…")
        self.continue_button.setToolTip("Load retained pump epoch plus separate named continuity evidence; never repeat a pump automatically.")
        self.continue_button.clicked.connect(self._choose_continuation)
        self.layout().insertWidget(3, self.continue_button)
        self.blank_button.clicked.connect(lambda: self._user_action(self.begin_blank))
        self.load_blank_button.clicked.connect(self._choose_blank)
        if context.mode == "single":
            row = QHBoxLayout()
            row.addWidget(self.blank_button)
            row.addWidget(self.load_blank_button)
            self.layout().insertLayout(1, row)
        self.layout().insertWidget(2, self.blank_status)
        self.plot_adapter = BurstPlotAdapter()
        self.plot = PlotPanel(self.plot_adapter)
        self.plot.error.connect(self.status.setText)
        self.views = QComboBox()
        self.views.addItems(("Early linear kinetics", "Positive-time logarithmic kinetics", "Scan-burst timeline",
                            "Supported spectral map", "Measured spectral slice", "Native trajectory and direction",
                            "Native detector streams", "Reference-normalized Q", "Temperature history", "Probe-duty history",
                            "Band plateaus and unrecovered fractions"))
        self.views.currentTextChanged.connect(self._view_changed)
        self.time_slice = LinkedSliceControl(label="Measured scan time", unit="s", decimals=9)
        self.wavenumber_slice = LinkedSliceControl(label="Wavenumber", unit="cm⁻¹", decimals=6)
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
        self._update_controls()

    def refresh_plan(self, *_):
        previous = getattr(self, "preliminary", None)
        super().refresh_plan()
        text = self.validation.text()
        if len(text.splitlines()) > 5:
            self.validation.setToolTip(text)
            self.validation.setText("\n".join(text.splitlines()[:4]) + f"\n… {len(text.splitlines())} items; see Plan details and readiness.")
        if self.plan is None and self.summary.text().startswith("Plan incomplete:"):
            self.summary.setText("Enter source-backed operating values and complete the accepted cryogenic state identity. No operating recipe is assumed.")
        if previous is not None and not getattr(self, "_initializing", True):
            self.review_summary.setText("Preliminary approval cleared: settings or selected evidence changed. Acquire a compatible preliminary and review again.")

    def _settings_changed(self):
        self.adapter.continuation = None
        self.start_button.setText("3 · Start one-pump observation")
        self.refresh_plan()
        try:
            self.context.preferences.setValue("settings", json.dumps(self.adapter.read_settings()))
            self.context.preferences.sync()
        except (ValueError, TypeError):
            pass
        if self.plan is not None:
            errors = self.adapter.blank_conflicts(self.plan)
            self.blank_status.setText("Concurrent matched-buffer reference supplies Q; acquire and review unpumped Q₀." if self.context.mode == "dual" else
                                     "\n".join(errors) if errors else "Compatible blank/control retained; load the sample and acquire its preliminary.")

    def _update_controls(self, *_):
        super()._update_controls()
        if not hasattr(self, "blank_button"):
            return
        idle = not self.command_running()
        self.blank_button.setEnabled(idle and self.plan is not None)
        self.load_blank_button.setEnabled(idle and self.plan is not None)
        self.capabilities_button.setEnabled(idle)
        self.continue_button.setEnabled(idle)
        if self.context.mode == "single":
            conflicts = self.adapter.blank_conflicts(self.plan) if self.plan is not None else ["Incomplete plan"]
            self.preliminary_button.setEnabled(idle and self.plan is not None and not conflicts)
            if conflicts:
                self.start_button.setEnabled(False)
        if self.adapter.continuation is not None:
            self.blank_button.setEnabled(False)
            self.load_blank_button.setEnabled(False)
            self.preliminary_button.setEnabled(False)
        elif self.plan is not None and self.plan.settings.accepted_state_id in self.adapter.used_accepted_states:
            self.start_button.setEnabled(False)

    def begin_blank(self):
        if self.context.mode != "single":
            raise ValueError("Dual mode uses simultaneous matched reference")
        self.adapter.preparation_kind = "baseline"
        self.begin("preliminary")

    def begin_capabilities(self):
        if self.command_running():
            raise RuntimeError("Wait for this tab's current operation and cleanup")
        settings = self.adapter.read_settings()
        plan = self.adapter.make_plan(settings)
        records = self.adapter.selected_records()
        operation = self.context.begin_operation(settings, hardware=self.adapter.hardware_required("capabilities", settings),
            purpose="explicit device capability readbacks", cancel=self.request_abort,
            calibration_records=records.calibration_records, sample_records=records.sample_records)
        self.snapshot = snapshot = StartSnapshot(operation, "capabilities", plan, None)
        self.adapter.preparation_kind = "capabilities"
        def run(worker):
            if operation.hardware:
                with self.context.hardware_scope(operation):
                    return self.adapter.run_preliminary(snapshot, worker)
            return self.adapter.run_preliminary(snapshot, worker)
        try:
            self._launch(run, "preliminary")
        except Exception:
            if operation.hardware:
                self.context.ownership.release(operation.ownership, safe_verified=True, preservation_verified=True,
                    detail="Capability worker dispatch failed before any device access")
            raise

    def show_plan_details(self):
        plan = self.adapter.make_plan(self.adapter.read_settings())
        dialog = QDialog(self)
        dialog.setWindowTitle("Finite single-pump plan: requested, selected and actual values")
        dialog.resize(900, 620)
        layout = QVBoxLayout(dialog)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        rows = list(plan.selected_values.items())
        table = QTableWidget(len(rows), 6)
        table.setHorizontalHeaderLabels(("Setting", "Requested", "Selected", "Actual readback", "Unit", "Source"))
        for row, (name, values) in enumerate(rows):
            for column, value in enumerate((name, values.get("requested"), values.get("selected"), values.get("actual"), values.get("unit"), values.get("source"))):
                item = QTableWidgetItem("Unresolved" if value is None else str(value))
                from PySide6.QtCore import Qt
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row, column, item)
        table.resizeColumnsToContents()
        tabs.addTab(table, "Operating values")
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText("\n".join(("PLAN ERRORS", *plan.errors, "", "READINESS", *plan.readiness, "", "WARNINGS", *plan.warnings)))
        tabs.addTab(text, "Readiness and limitations")
        schedule = QPlainTextEdit()
        schedule.setReadOnly(True)
        schedule.setPlainText(json.dumps({"estimates": plan.estimates, "blocks": [json_value(block) for block in plan.blocks]}, indent=2))
        tabs.addTab(schedule, "Finite frame/channel schedule")
        dialog.show()
        self._details_dialog = dialog

    def begin(self, kind):
        if kind == "preliminary" and self.adapter.preparation_kind != "baseline" and self.plan is not None:
            errors = self.adapter.blank_conflicts(self.plan)
            if errors:
                raise ValueError("\n".join(errors))
        if kind == "measurement" and self.preliminary is not None:
            errors = self.adapter.validate_review(self.preliminary, self.plan)
            if errors:
                self.validation.setText("\n".join(errors))
                self.review.setChecked(False)
                return
            self.validation.clear()
            # The host deep-copies this envelope before dispatch. Later UI
            # invalidation cannot change a selected continuation into a new pump.
            self.preliminary["_dispatch_blank"] = self.adapter._record_reference(self.adapter.blank)
            self.preliminary["_dispatch_continuation"] = deepcopy(self.adapter.continuation)
        super().begin(kind)

    def _finished(self, worker, kind, path):
        if self.worker is not worker:
            return
        outcome = worker.outcome
        result = outcome.result if outcome and outcome.state == "completed" else None
        capabilities = isinstance(result, dict) and result.get("preparation_kind") == "capabilities"
        blank = kind == "load_blank" or (kind == "preliminary" and isinstance(result, dict) and result.get("preparation_kind") == "baseline")
        super()._finished(worker, "capabilities" if capabilities else "blank" if blank else kind, path)
        if kind == "load_continuation" and result is not None:
            records = result["operation_records"]
            selected = records.get("sample_records", ())
            self.adapter.sample_selection = deepcopy(selected[0]) if selected else None
            self.adapter.calibration_records = tuple(deepcopy(records.get("calibration_records", ())))
            self.adapter.apply_settings(result["settings"])
            self.adapter.continuation = result
            self.adapter.blank = deepcopy(result["baseline"].get("blank"))
            if self.adapter.blank is not None:
                self.adapter.blank["compatibility"] = self.adapter._identity(self.plan)
            self.preliminary = deepcopy(result["baseline"]["preliminary"])
            self.preliminary["compatibility"] = self.adapter._identity(self.plan)
            self.review.setChecked(False)
            self.review_summary.setText("Review the retained preliminary approval, single observed pump epoch and separately named continuity evidence. Start continues remaining blocks without a pump; connected state is verified again under ownership.")
            self.start_button.setText("Start explicit continuation (no pump)")
            self.status.setText("Retained observation loaded. Explicit review and Start continuation are required; no device was accessed.")
            self.blank_status.setText("Original retained baseline/control references selected for this explicit continuation.")
        elif capabilities:
            from .settings import Capabilities
            self.adapter.capabilities = Capabilities.from_dict(result["capabilities"])
            self._settings_changed()
            self.status.setText("Device readbacks retained and prior state restored. Review readiness items; no optical acquisition was requested.")
        elif blank and result is not None:
            self.adapter.blank = result
            self.preliminary = None
            self.review.setChecked(False)
            self.blank_status.setText("Blank/control retained. Load the sample in the recorded cell/position and acquire its preliminary.")
            self.status.setText("Completed sequential blank/control; pump inhibited.")
            self._show_result(result)
        elif kind == "preliminary" and result is not None:
            self._show_result(result)
        if kind == "measurement":
            retained = self.adapter.last_measurement_outcome or {}
            if retained.get("summary", {}).get("pump_intent") and self.snapshot is not None:
                state_id = self.snapshot.settings.get("accepted_state_id")
                if state_id:
                    self.adapter.used_accepted_states.add(state_id)
                    self.context.preferences.setValue("used_accepted_state_ids", sorted(self.adapter.used_accepted_states))
                    self.context.preferences.sync()
            # A review authorizes one dispatch only. A completed or uncertain
            # pump never leaves a reusable Start button for the same state.
            self.review.setChecked(False)
            self.preliminary = None
            self.adapter.continuation = None
            self.review_summary.setText("This Start authorization has been consumed. Continue an interrupted retained epoch explicitly, or select a newly accepted/equivalent sample state before a new pump observation.")
        if outcome and outcome.state == "cancelled":
            self.status.setText("Acquisition stopped. " + outcome.error)
        self._update_controls()

    def _choose_blank(self):
        path = QFileDialog.getExistingDirectory(self, "Load compatible blank/control", str(self._next_root))
        if path:
            plan = deepcopy(self.plan)
            self._user_action(lambda: self._launch(lambda _worker: self.adapter.load_blank(Path(path), plan), "load_blank", path))

    def _choose_continuation(self):
        path = QFileDialog.getExistingDirectory(self, "Retained incomplete observation", str(self._next_root))
        if not path:
            return
        evidence, _ = QFileDialog.getOpenFileName(self, "Named clock and sample-state continuity evidence", str(self._next_root), "JSON (*.json)")
        if evidence:
            self._user_action(lambda: self.load_continuation(Path(path), Path(evidence)))

    def load_continuation(self, path, evidence_path):
        self.adapter.read_settings()  # Freeze pure UI choices before background file I/O.
        self._launch(lambda _worker: self.adapter.prepare_continuation(path, evidence_path), "load_continuation", path)

    def _choose_sample_selection(self):
        path, _ = QFileDialog.getOpenFileName(self, "Accepted sample spectral selection", str(self._next_root), "JSON (*.json)")
        if path:
            self._user_action(lambda: self.load_sample_selection(Path(path)))

    def load_sample_selection(self, path):
        from control_app.measurement_host.interchange import load_sample_selection
        selection = load_sample_selection(path)
        values = self.adapter.read_settings()
        if selection.condition_id != values["condition_id"]:
            raise ValueError("Sample-selection condition does not match this cryogenic profile")
        if values["sample_id"] and selection.sample_id != values["sample_id"]:
            raise ValueError("Sample-selection sample identity does not match entered sample")
        values["sample_id"] = selection.sample_id
        values["sample_selection_id"] = selection.selection_id
        # Accepted sample records may establish measured windows/condition data;
        # they never provide an instrument operating recipe or promotion.
        condition_fields = ("preparation_id", "accepted_state_id", "matrix_id", "cell_id", "position_id",
                            "temperature_identity", "thermal_history_id", "measured_temperature_k", "temperature_uncertainty_k")
        for key in condition_fields:
            if values.get(key) in (None, "") and selection.condition.get(key) is not None:
                values[key] = selection.condition[key]
                values["settings_sources"][key] = selection.selection_id
        windows = [(window.lower_cm1, window.upper_cm1) for window in selection.windows]
        for key, value in (("scan_start_cm1", min(lo for lo, _ in windows)),
                           ("scan_stop_cm1", max(hi for _, hi in windows))):
            if values[key] is None:
                values[key] = value
                values["settings_sources"][key] = selection.selection_id
        if not values["plateau_band_windows_cm1"]:
            values["plateau_band_windows_cm1"] = windows
            values["settings_sources"]["plateau_band_windows_cm1"] = selection.selection_id
        self.adapter.sample_selection = json_value(selection)
        self.adapter.apply_settings(values)
        self.status.setText("Accepted sample selection loaded as versioned data; instrument calibration is separate.")

    def _resolve_bundles(self):
        from .settings import resolve_settings
        data = self.adapter.read_settings()
        execution = data.pop("_execution")
        settings = Settings.from_dict(data)
        records = []
        for bundle_id in settings.promoted_bundle_ids:
            bundle = self.context.promoted_bundle(bundle_id)
            native = json_value(bundle)
            manifest = native.get("manifest", {})
            payload = manifest.get("measurement_modules", {}).get(self.context.experiment_id)
            if payload is None and manifest.get("experiment_id") == self.context.experiment_id:
                payload = manifest
            payload = payload or {}
            values = payload.get("settings", payload.get("values", {}))
            settings = resolve_settings(settings, promoted_values={"record_id": bundle_id, "values": values})
            records.append(native)
        self.adapter.calibration_records = tuple(records)
        self.adapter.apply_settings({**settings.to_dict(), "_execution": execution})
        self.status.setText(f"Resolved {len(records)} promoted bundle(s); explicit overrides retained. Review must be renewed.")

    def _show_result(self, result):
        self._points = result.get("display_points")
        self._native_points = result.get("native_display_points")
        if self._points is None:
            self._points = _display_points(result)
        points = self._points
        if len(points["time"]):
            scans = np.unique(points["scan"])
            times = np.asarray([points["time"][points["scan"] == scan][0] for scan in scans])
            wavenumbers = np.unique(points["wavenumber"][np.isfinite(points["wavenumber"])])
            self.plot_adapter.times, self.plot_adapter.wavenumbers = times, wavenumbers
            self.time_slice.set_coordinates(times)
            self.wavenumber_slice.set_coordinates(wavenumbers)
        self.plot.set_result(points)

    def _view_changed(self, view):
        self.plot_adapter.view = view
        if view in ("Native detector streams", "Native trajectory and direction") and self._native_points is not None:
            self.plot.set_result(self._native_points)
        else:
            self.plot.set_result(self._points)

    def _time_changed(self, index):
        self.plot_adapter.time_index = index
        self.plot.reset_view()

    def _wavenumber_changed(self, index):
        self.plot_adapter.wavenumber_index = index
        self.plot.reset_view()

    def _clear_results(self):
        self._points = None
        self._native_points = None
        self.plot.clear_result()
        self.time_slice.set_coordinates(())
        self.wavenumber_slice.set_coordinates(())
        self.blank_status.setText("Load or acquire this tab's blank/control." if self.context.mode == "single" else "Acquire a new simultaneous unpumped Q₀.")
        self.start_button.setText("3 · Start one-pump observation")
        if self.plan is not None and self.plan.settings.accepted_state_id in self.adapter.used_accepted_states:
            self.status.setText("New run cleared this tab's records. The entered accepted sample state already has a pump; select a new accepted/equivalent state ID or explicitly continue its retained epoch.")

    def _operation_state(self, busy):
        self.context.lifecycle.notify_state(busy, "single-pump observation" if busy else "idle")

    def output_location_changed(self, path):
        self._next_root = Path(path)
        # The host operation already owns its frozen output_path. This changes
        # path suggestions only; the next operation obtains the host's new root.

    def instrument_state_changed(self, change):
        self.adapter.continuation = None
        self.adapter.instrument_revision += 1
        detail = "; ".join(f"{item.device_id}.{item.configuration_key}: {item.previous_value} → {item.new_value}" for item in change.changes)
        self.adapter.instrument_changes.append(detail)
        self.review.setChecked(False)
        if not self.command_running():
            self.preliminary = None
        self.validation.setText("Instrument state changed; preliminary review invalidated: " + detail)
        self._update_controls()


def make_handle(context, *, title):
    widget = SinglePumpScanBurstWidget(context)
    return TabHandle(instance_id=context.instance_id, title=title, widget=widget,
        command_running=widget.command_running, close_blockers=widget.close_blockers,
        request_abort=widget.request_abort, output_location_changed=widget.output_location_changed,
        instrument_state_changed=widget.instrument_state_changed, state_changed=widget.busy_changed)
