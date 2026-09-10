"""Regular phase-scan acquisition and reconstruction. Construction is hardware-free."""

from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import replace
import json
import math
from pathlib import Path
from control_app.paths import get_save_location
from control_app.workflows.phase_scan_runner import OPTICAL_ADAPTER_BLOCKER
from control_app.workflows.regular_phase_scan import (
    HF2Capabilities, RegularPhaseScanSettings, build_regular_phase_scan_plan, select_hf2_settings,
)
from control_app.workflows.regular_phase_scan_runner import RegularPhaseScanRunner

from control_app.workflows.phase_scan import (
    PHASE_SCAN_EXECUTION_BLOCKER,
    PhaseScanPlan,
    PhaseScanPlanError,
    PhaseScanSettings,
    build_phase_scan_plan,
)

try:
    from PySide6.QtCore import QPointF, QRectF, Qt, Signal, QThread, QTimer
    from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
    from PySide6.QtWidgets import (
        QAbstractItemView, QCheckBox, QTabWidget, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
        QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QScrollArea,
        QSpinBox, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    )
    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - backend remains importable without Qt
    PYSIDE6_AVAILABLE = False
    QWidget = object


if PYSIDE6_AVAILABLE:
    class _PhaseWorker(QThread):
        message = Signal(str)
        scan = Signal(object, object, str)
        configured = Signal(object)
        result = Signal(object)
        stopped = Signal(str)
        failed = Signal(str)

        def __init__(self, operation, parent=None):
            super().__init__(parent)
            self.operation = operation

        def run(self):
            try:
                self.result.emit(self.operation(self))
            except InterruptedError as exc:
                message = str(exc)
                self.stopped.emit(message if message.startswith("Acquisition stopped.")
                                  else f"Acquisition stopped. {message}")
            except Exception as exc:
                self.failed.emit(f"{type(exc).__name__}: {exc}")

    class _PreliminarySpectrumCanvas(QWidget):
        """Display the unpumped preliminary spectrum in native order, with gaps."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.points: tuple[tuple[float, float], ...] = ()
            self.requested_range = (2000.0, 1900.0)
            self.y_label = "Absorbance"
            self.setMinimumHeight(300)

        def axis_limits(self):
            xs = [x for x, _ in self.points if math.isfinite(x)]
            ys = [y for x, y in self.points if math.isfinite(x) and math.isfinite(y)]
            xmin, xmax = (min(xs), max(xs)) if xs else tuple(sorted(self.requested_range))
            if xmin == xmax:
                xmin, xmax = xmin - 0.5, xmax + 0.5
            if ys:
                ymin, ymax = min(ys), max(ys)
                padding = (ymax - ymin) * 0.08 if ymax != ymin else max(abs(ymin) * 0.08, 1e-6)
                ymin, ymax = ymin - padding, ymax + padding
            else:
                ymin, ymax = 0.0, 1.0
            return xmin, xmax, ymin, ymax

        def paintEvent(self, _event):  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.fillRect(self.rect(), self.palette().base())
            painter.setPen(self.palette().text().color())
            left, top = 84, 20
            width, height = self.width() - left - 30, self.height() - top - 65
            if width <= 0 or height <= 0:
                return
            plot_rect = QRectF(left, top, width, height)
            xmin, xmax, ymin, ymax = self.axis_limits()
            finite_points = [(x, y) for x, y in self.points if math.isfinite(x) and math.isfinite(y)]
            text_color = self.palette().text().color()
            grid_color = QColor(text_color)
            grid_color.setAlpha(35)
            for tick in range(5):
                fraction = tick / 4
                px, py = left + fraction * width, top + fraction * height
                painter.setPen(QPen(grid_color, 1))
                painter.drawLine(QPointF(px, top), QPointF(px, top + height))
                painter.drawLine(QPointF(left, py), QPointF(left + width, py))
                painter.setPen(text_color)
                # Conventional IR display: high wavenumbers on the left.
                painter.drawText(
                    QRectF(px - 43, top + height + 7, 86, 20), Qt.AlignmentFlag.AlignCenter,
                    f"{xmax - fraction * (xmax - xmin):.6g}",
                )
                if finite_points:
                    painter.drawText(
                        QRectF(25, py - 10, left - 33, 20),
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                        f"{ymax - fraction * (ymax - ymin):.4g}",
                    )
            painter.drawRect(plot_rect)
            painter.drawText(
                QRectF(left, self.height() - 27, width, 23), Qt.AlignmentFlag.AlignCenter,
                "Wavenumber (cm⁻¹)",
            )
            painter.save()
            painter.translate(16, top + height / 2)
            painter.rotate(-90)
            painter.drawText(QRectF(-height / 2, -12, height, 24), Qt.AlignmentFlag.AlignCenter, self.y_label)
            painter.restore()
            if not finite_points:
                message = "Acquire an unpumped sample spectrum for review" if not self.points else f"Spectrum has no valid {self.y_label.lower()} points"
                painter.drawText(plot_rect, Qt.AlignmentFlag.AlignCenter, message)
                return

            painter.save()
            painter.setClipRect(plot_rect)
            painter.setPen(QPen(QColor(48, 122, 190), 1.8))
            path = QPainterPath()
            segment_length = 0
            previous_point = None
            isolated_points = []
            for x, y in self.points:
                if not math.isfinite(x) or not math.isfinite(y):
                    if segment_length == 1:
                        isolated_points.append(previous_point)
                    segment_length = 0  # Do not draw an interpolated bridge over a gap.
                    continue
                point = QPointF(
                    left + (xmax - x) / (xmax - xmin) * width,
                    top + (ymax - y) / (ymax - ymin) * height,
                )
                if segment_length:
                    path.lineTo(point)
                else:
                    path.moveTo(point)
                segment_length += 1
                previous_point = point
            if segment_length == 1:
                isolated_points.append(previous_point)
            painter.drawPath(path)
            for point in isolated_points:
                painter.drawEllipse(point, 3, 3)
            painter.restore()



def _brief_setting_error(message):
    rules = (
        ("unsupported for the selected filter order", "Time constant conflicts with Filter order; choose a listed time constant for that order."),
        ("Sa/s is unsupported", "CH1 sample rate is incompatible; choose a supported rate or set it to Automatic."),
        ("two-stream transfer capacity", "CH1 sample rate exceeds transfer capacity; choose a lower supported rate."),
        ("timing-table", "Reconstruction before/after times exceed timing-table capacity; shorten either time or increase Phase-delay spacing."),
        ("retention budget", "Reconstruction before/after times and CH1 sample rate exceed record capacity; shorten either time or reduce CH1 sample rate."),
        ("cadence", "Reconstruction before/after times exceed the pump cadence with this sweep; shorten either time or lower Pump repetition rate."),
        ("single installed", "Start/Stop wavenumber exceed one QCL’s tuning range; choose endpoints within the same QCL."),
        ("Filter order", "Filter order is unsupported; choose a listed order or Automatic."),
        ("shorter than two", "Sweep duration is too short; lower Scan speed or widen the wavenumber span."),
        ("markers are too short", "Scan speed makes wavelength markers too short; lower Scan speed."),
        ("16-million-cell", "Timing window and Phase-delay spacing exceed reconstruction capacity; shorten the window or increase Phase-delay spacing."),
        ("pre_pump_ms", "Reconstruct before pump must be finite and nonnegative; enter a duration of zero or greater."),
        ("post_pump_ms", "Reconstruct after pump must be finite and positive; enter a duration greater than zero."),
    )
    for match, brief in rules:
        if match in message:
            return brief
    return message.split(";", 1)[0].split(". ", 1)[0].rstrip(".") + "; revise the indicated setting."


class PhaseScanWidget(QWidget):
    """App-only regular CH1 blank, preliminary review, and pumped phase scan."""
    if PYSIDE6_AVAILABLE:
        latest_scan_received = Signal(object, object, str)  # compatibility with spectrum providers
        busy_changed = Signal(bool)

    def __init__(self, parent=None, *, runner=None, diagnostic=None, before_start=None, preferences=None, dual_detector=False,
                 save_root_provider=None):
        if not PYSIDE6_AVAILABLE:
            raise RuntimeError("PySide6 is required to instantiate PhaseScanWidget")
        super().__init__(parent)
        self.dual_detector = dual_detector
        if dual_detector:
            from control_app.workflows.dual_detector_phase_scan_runner import DualDetectorPhaseScanRunner
            from control_app.workflows.dual_detector_phase_scan import DualDetectorPhaseScanSettings, DualHF2Capabilities, select_dual_hf2_settings
            self.settings_type, self.capabilities_type = DualDetectorPhaseScanSettings, DualHF2Capabilities
            self._select_hf2 = select_dual_hf2_settings
            self.runner = runner or DualDetectorPhaseScanRunner()
        else:
            self.settings_type, self.capabilities_type = RegularPhaseScanSettings, HF2Capabilities
            self._select_hf2 = select_hf2_settings
            self.runner = runner or RegularPhaseScanRunner()
        self.preference_key = "dual_detector_phase_scan" if dual_detector else "regular_phase_scan"
        self.plan_method = "dual_detector_phase_scan" if dual_detector else "regular_single_detector_phase_scan"
        self.before_start = before_start or (lambda: None)
        self.preferences = preferences
        self.save_root_provider = save_root_provider or get_save_location
        self._pending_instrument_changes = []
        self.worker, self.plan, self._pending_result, self._current_kind = None, None, None, None
        self.inputs, self.summary_values, self.override_inputs, self._overrides = {}, {}, {}, {}
        self._restoring = False
        self._capability_check_attempted = False
        self._build()
        self._restore_capability_preferences()
        self._restore_preferences()
        self._populate_override_choices()
        self._refresh_plan()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        # Construction remains hardware-free. Opening the tab checks the
        # connected device automatically; stored choices are already usable.
        QTimer.singleShot(0, self._ensure_connected_capabilities)

    def _ensure_connected_capabilities(self):
        if (not self.isVisible() or self._capability_check_attempted or
                not self.runner.available or self.command_running() or self._capabilities().get("verified")):
            return
        self._begin("capabilities")

    def _build(self):
        from control_app.ui.widgets.phase_scan_surface import PhaseScanReconstructionWidget
        root = QVBoxLayout(self)
        heading = ("<b>Dual-Detector Phase Scan</b> · Sample: Signal 1 (+) · Reference: Signal 2 (+)"
                   if self.dual_detector else "<b>Regular single-detector phase scan</b> · HF2LI CH1 SIG IN +")
        root.addWidget(QLabel(heading))
        splitter = QSplitter(Qt.Orientation.Horizontal)
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        controls = QWidget()
        control_layout = QVBoxLayout(controls)
        form = QFormLayout()
        defaults = self.settings_type()
        fields = (
            ("pump_repetition_rate_hz", "Pump repetition rate", " Hz", .000001, 10., 6, 1.),
            ("start_wavenumber_cm1", "Start wavenumber", " cm⁻¹", 1650., 2050., 3, 1.),
            ("stop_wavenumber_cm1", "Stop wavenumber", " cm⁻¹", 1650., 2050., 3, 1.),
            ("scan_speed_cm1_s", "Scan speed", " cm⁻¹/s", 1., 10000., 3, 100.),
            ("pre_pump_ms", "Reconstruct before pump", " ms", 0., 1e6, 3, .1),
            ("post_pump_ms", "Reconstruct after pump", " ms", .001, 1e6, 3, .1),
            ("phase_delay_us", "Phase-delay spacing", " µs", 1., 1000., 3, 1.),
        )
        for key, label, suffix, low, high, decimals, step in fields:
            spin = QDoubleSpinBox()
            spin.setObjectName(key)
            spin.setDecimals(decimals)
            spin.setRange(low, high)
            spin.setSingleStep(step)
            spin.setSuffix(suffix)
            spin.setValue(getattr(defaults, key))
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(self._refresh_plan)
            self.inputs[key] = spin
            form.addRow(label, spin)
        control_layout.addLayout(form)
        self.validation = QLabel()
        self.validation.setWordWrap(True)
        self.validation.setTextFormat(Qt.TextFormat.PlainText)
        control_layout.addWidget(self.validation)
        self.refresh_capabilities_button = QPushButton("Check connected device")
        self.refresh_capabilities_button.setToolTip("The device is checked automatically when this tab opens. Use this to retry or check a newly connected device. Existing choices remain available; no laser emission or acquisition.")
        self.refresh_capabilities_button.clicked.connect(lambda: self._begin("capabilities"))
        control_layout.addWidget(self.refresh_capabilities_button)
        self.hf2_status = QLabel()
        self.hf2_status.setWordWrap(True)
        self.hf2_status.setTextFormat(Qt.TextFormat.PlainText)
        control_layout.addWidget(self.hf2_status)
        advanced = QGroupBox("Advanced HF2LI overrides")
        advanced.setCheckable(True)
        advanced.setChecked(False)
        self.advanced_group = advanced
        advanced_layout = QVBoxLayout(advanced)
        advanced_form = QFormLayout()
        override_fields = (("order", "Filter order"), ("timeconstant_s", "Time constant"), ("rate_sps", "CH1 sample rate"))
        if self.dual_detector:
            override_fields = tuple((f"{role}_{key}", f"{role.title()} {label}")
                                    for role in ("sample", "reference")
                                    for key, label in (("order", "filter order"), ("timeconstant_s", "time constant"), ("rate_sps", "rate")))
        for key, label in override_fields:
            combo = QComboBox()
            combo.setObjectName("hf2_" + key)
            combo.addItem("Automatic", None)
            combo.currentIndexChanged.connect(lambda _index, field=key: self._override_changed(field))
            self.override_inputs[key] = combo
            advanced_form.addRow(label, combo)
        advanced_layout.addLayout(advanced_form)
        self.restore_auto_button = QPushButton("Restore automatic settings")
        self.restore_auto_button.clicked.connect(self._restore_automatic)
        advanced_layout.addWidget(self.restore_auto_button)
        advanced.toggled.connect(self._advanced_toggled)
        control_layout.addWidget(advanced)
        self.actual_settings = QLabel("")
        self.actual_settings.setWordWrap(True)
        self.actual_settings.setTextFormat(Qt.TextFormat.PlainText)
        control_layout.addWidget(self.actual_settings)
        self.save_button = QPushButton("Save plan…")
        self.save_button.clicked.connect(self._save_plan)
        control_layout.addWidget(self.save_button)
        self.load_plan_button = QPushButton("Load plan…")
        self.load_plan_button.clicked.connect(self._load_plan)
        control_layout.addWidget(self.load_plan_button)
        control_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)
        panel_layout.addWidget(scroll, 1)
        self.background_button = QPushButton("1 · Acquire buffer blank sequence")
        self.load_background_button = QPushButton("Select saved buffer blank…")
        self.test_button = QPushButton("2 · Acquire preliminary sample (pump OFF)")
        self.review_checkbox = QCheckBox("I reviewed the preliminary unpumped spectrum")
        self.start_button = QPushButton("3 · Start pumped phase scan")
        if self.dual_detector:
            self.background_button.hide()
            self.load_background_button.hide()
            self.test_button.setText("2 · Acquire preliminary sample/reference (pump OFF)")
            self.review_checkbox.setText("I reviewed the preliminary sample/reference spectrum")
        self.abort_button = QPushButton("Abort acquisition")
        self.abort_button.setProperty("danger", True)
        self.new_run_button = QPushButton("New run")
        self.new_run_button.clicked.connect(self._new_run)
        self.background_button.clicked.connect(lambda: self._begin("background"))
        self.load_background_button.clicked.connect(self._load_background)
        self.test_button.clicked.connect(lambda: self._begin("test"))
        self.review_checkbox.toggled.connect(self._reviewed)
        self.start_button.clicked.connect(lambda: self._begin("run"))
        self.abort_button.clicked.connect(self._abort)
        if self.dual_detector:
            instruction = QLabel("1 · Load the sample; keep the matched buffer blank in the reference path.")
            instruction.setWordWrap(True)
            panel_layout.addWidget(instruction)
        workflow_controls = (self.test_button, self.review_checkbox, self.start_button, self.abort_button)
        if not self.dual_detector:
            workflow_controls = (self.background_button, self.load_background_button) + workflow_controls
        for control in workflow_controls:
            panel_layout.addWidget(control)
        panel_layout.addWidget(self.new_run_button)
        self.execution, self.save_status = QLabel(), QLabel()
        for label in (self.execution, self.save_status):
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            panel_layout.addWidget(label)
        splitter.addWidget(panel)
        preview = QWidget()
        preview_layout = QVBoxLayout(preview)
        summary = QGroupBox("Derived experiment and effective settings")
        summary_form = QFormLayout(summary)
        for key, label in (("duration", "Sweep duration"), ("window", "Reconstruction window"), ("delays", "Required sweep-start range"), ("total", "Sequence scan count"), ("pump", "Pump cadence"), ("elapsed", "Sequence duration"), ("probe", "Fixed probe configuration"), ("capacity", "Preflight capacity"), ("hf2", "Selected HF2LI"), ("resolution", "Effective resolution")):
            value = QLabel()
            value.setWordWrap(True)
            self.summary_values[key] = value
            summary_form.addRow(label, value)
        preview_layout.addWidget(summary)
        self.views = QTabWidget()
        self.reconstruction = (PhaseScanReconstructionWidget(detector_mode="dual_detector") if self.dual_detector
                               else PhaseScanReconstructionWidget())
        self._surface = self.reconstruction
        self.reconstruction.run_loaded.connect(lambda _r, p: self.scan_status.setText(f"Loaded reconstruction: {p}"))
        self.views.addTab(self.reconstruction, "Reconstructed phase-scan data")
        review = QWidget()
        review_layout = QVBoxLayout(review)
        self.canvas = _PreliminarySpectrumCanvas()
        self.canvas.y_label = "Sample/reference ratio" if self.dual_detector else "Absorbance"
        review_layout.addWidget(self.canvas, 1)
        self.preliminary_status = QLabel("Preliminary review is separate from pumped reconstructed data.")
        self.preliminary_status.setWordWrap(True)
        review_layout.addWidget(self.preliminary_status)
        self.views.addTab(review, "Preliminary spectral review")
        preview_layout.addWidget(self.views, 1)
        self.scan_status = QLabel("No acquisition running.")
        self.scan_status.setWordWrap(True)
        self.scan_status.setTextFormat(Qt.TextFormat.PlainText)
        preview_layout.addWidget(self.scan_status)
        self.phase_table = QTableWidget(0, 4)
        self.phase_table.setHorizontalHeaderLabels(["Position", "Sample condition", "Start relative to sync", "End relative to sync"])
        self.phase_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.phase_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.phase_table.hide()
        sequence = QPushButton("Show phase sequence")
        sequence.setCheckable(True)
        sequence.toggled.connect(self.phase_table.setVisible)
        preview_layout.addWidget(sequence)
        preview_layout.addWidget(self.phase_table)
        splitter.addWidget(preview)
        splitter.setSizes([420, 900])
        root.addWidget(splitter, 1)
        self.latest_scan_received.connect(self.set_latest_scan)

    def settings(self):
        return self.settings_type(**{key: widget.value() for key, widget in self.inputs.items()})

    def _capabilities(self):
        caps = getattr(self.runner, "capabilities", None)
        return caps.to_dict() if hasattr(caps, "to_dict") else caps or self.capabilities_type().to_dict()

    def _populate_override_choices(self):
        caps = self._capabilities()
        for key, combo in self.override_inputs.items():
            role, field = key.split("_", 1) if self.dual_detector else (None, key)
            profile = caps.get(role, {}) if role else caps
            order_key = f"{role}_order" if role else "order"
            order = self._overrides.get(order_key)
            constants = profile.get("timeconstants_by_order", {})
            # Menus remain usable even when the current combination is invalid.
            timeconstants = (sorted({value for group in constants.values() for value in group}) if order is None
                             else constants.get(order, constants.get(str(order), ())))
            values = {"order": profile.get("orders", ()), "timeconstant_s": timeconstants, "rate_sps": profile.get("rates_sps", ())}[field]
            combo.blockSignals(True)
            combo.clear()
            wanted = self._overrides.get(key)
            combo.addItem("Automatic", None)
            for value in values:
                text = str(value) if field == "order" else f"{value*1e6:.9g} µs" if field == "timeconstant_s" else f"{value:.12g} Sa/s"
                combo.addItem(text, value)
            if wanted is not None and wanted not in values:
                label = (f"{wanted*1e6:.9g} µs" if field == "timeconstant_s" and isinstance(wanted, (int, float)) else
                         f"{wanted:.12g} Sa/s" if field == "rate_sps" and isinstance(wanted, (int, float)) else str(wanted))
                combo.addItem(f"{label} — unsupported; choose another value", wanted)
                combo.model().item(combo.count()-1).setEnabled(False)
            combo.setCurrentIndex(max(0, combo.findData(wanted)))
            combo.blockSignals(False)
            combo.setEnabled(self.advanced_group.isChecked() and
                             (not self.command_running() or self._current_kind == "capabilities"))

    def _override_changed(self, key):
        value = self.override_inputs[key].currentData()
        if value is None:
            self._overrides.pop(key, None)
        else:
            self._overrides[key] = value
        # Keep an incompatible explicit override for validation; never silently
        # rewrite the requested pair when the selected order changes.
        self._refresh_plan()
        self._populate_override_choices()

    def _restore_automatic(self):
        self._overrides.clear()
        self._refresh_plan()
        self._populate_override_choices()

    def _advanced_toggled(self, checked):
        if not checked and self._overrides:
            self._restore_automatic()
        elif not self._restoring:
            self._update_buttons()

    def _refresh_plan(self, *_):
        if self._restoring:
            return
        self.save_status.clear()
        self.actual_settings.clear()
        try:
            self.plan = self.runner.configuration_preview(self.settings(), overrides=self._overrides)
        except (ValueError, RuntimeError) as exc:
            self.plan = None
            self.validation.setText(_brief_setting_error(str(exc)))
            for label in self.summary_values.values():
                label.setText("—")
            self.hf2_status.clear()
            self.phase_table.setRowCount(0)
        else:
            p, s = self.plan, self.plan.hf2_selection
            self.validation.setText(p.capacity.get("warning", ""))
            self.summary_values["duration"].setText(f"{p.scan_duration_s*1000:.6g} ms; capture {p.capture_window.get('duration_s', p.scan_duration_s)*1000:.6g} ms")
            self.summary_values["window"].setText(f"−{p.settings.pre_pump_ms:g} to +{p.settings.post_pump_ms:g} ms · electrical pump sync")
            self.summary_values["delays"].setText(f"{p.first_phase_delay_us/1000:g} to +{p.last_phase_delay_us/1000:g} ms")
            self.summary_values["total"].setText(f"{p.total_scans:,} per blank / sample sequence; sample includes one unpumped baseline + {p.total_pump_events:,} pumped phases")
            self.summary_values["pump"].setText(f"{p.settings.pump_repetition_rate_hz:g} Hz · {p.frame_period_s*1000:.9g} ms cadence · FIRE→Q-switch 250 µs")
            self.summary_values["elapsed"].setText(f"{p.nominal_duration_s:.3f} s per sequence, plus setup, settling and retrieval")
            self.summary_values["probe"].setText("2 MHz external probe triggering, 150 ns TTL; MIRcat internal 2.1 MHz / 142 ns; CH1 SIG IN +")
            capacity = p.capacity
            self.summary_values["capacity"].setText(f"{capacity.get('estimated_retained_bytes', 0)/1e6:.1f} MB estimated · {capacity.get('max_retained_bytes', 0)/1e6:.1f} MB advisory · {p.total_scans:,} timing entries")
            self.summary_values["hf2"].setText(f"Order {s['order']} · τ {s['timeconstant_s']*1e6:.4g} µs · {s['rate_sps']/1000:.4g} kSa/s")
            self.summary_values["resolution"].setText(f"{s['temporal_resolution_s']*1e6:.4g} µs · broadening {s['spectral_broadening_cm1']:.4g} cm⁻¹ (estimated)")
            self.actual_settings.setText(f"Selected: order {s['order']} · τ {s['timeconstant_s']*1e6:.6g} µs · {s['rate_sps']/1000:.6g} kSa/s; estimated resolution {s['temporal_resolution_s']*1e6:.6g} µs.")
            self.hf2_status.setText("Aliasing advisory: increase CH1 sample rate or Time constant to improve filtering margin." if not s.get("anti_alias_guideline_met", True) else "")
            if self.dual_detector:
                self.summary_values["total"].setText(f"{p.total_scans:,} simultaneous detector scans; one unpumped + {p.total_pump_events:,} pumped phases")
                self.summary_values["probe"].setText("2 MHz external probe triggering, 150 ns TTL; MIRcat internal 2.1 MHz / 142 ns; sample + reference")
                channel_text = "\n".join(self._channel_settings_text(role, s[role]) for role in ("sample", "reference"))
                self.summary_values["hf2"].setText(channel_text + f"\nTiming: {s['timing_rate_sps']/1000:.6g} kSa/s")
                self.summary_values["resolution"].setText(f"Both channels: {s['temporal_resolution_s']*1e6:.6g} µs · {s.get('effective_spectral_resolution_cm1', 0):.6g} cm⁻¹ (estimated)")
                self.actual_settings.setText("Selected: " + channel_text)
                self.hf2_status.setText("Aliasing advisory: increase the affected detector’s sample rate or time constant." if not s.get("anti_alias_guideline_met", True) else "")
            self._populate_sequence(p)
            self.canvas.requested_range = (p.settings.start_wavenumber_cm1, p.settings.stop_wavenumber_cm1)
        self._save_preferences()
        self._update_buttons()

    @staticmethod
    def _channel_settings_text(role, values):
        text = (f"{role.title()}: order {values['order']} · τ {values['timeconstant_s']*1e6:.6g} µs · "
                f"{values['rate_sps']/1000:.6g} kSa/s")
        if "filter_group_delay_s" in values:
            text += f" · delay {values['filter_group_delay_s']*1e6:.6g} µs"
        return text

    def _populate_sequence(self, plan):
        count = plan.total_scans
        indices = list(range(min(4, count))) + ([None] if count > 6 else []) + list(range(max(4, count-2), count))
        self.phase_table.setRowCount(len(indices))
        for row, index in enumerate(indices):
            if index is None:
                cells = ("…", f"{count-6:,} more scans", "…", "…")
            else:
                event = plan.event_at(index)
                cells = (str(index+1), "Unpumped baseline", "No pump", "No pump") if not event.pump_enabled else (str(index+1), "Pumped phase", f"{event.phase_delay_us:g} µs", f"{event.phase_delay_us+plan.scan_duration_s*1e6:g} µs")
            for col, value in enumerate(cells):
                self.phase_table.setItem(row, col, QTableWidgetItem(value))

    def _update_buttons(self):
        busy, valid = self.command_running(), self.plan is not None
        acquiring = busy and self._current_kind != "capabilities"
        conflicts = self.runner.background_conflicts(self.plan or self.settings())
        blank = valid and not conflicts and self.runner.background is not None
        preliminary = valid and (self.dual_detector or blank) and self.runner.preliminary_matches(self.plan)
        verified = valid and self.plan.hf2_selection.get("capability_verified", False)
        ready = valid and verified and self.runner.available and not busy
        self.background_button.setEnabled(ready and not self.dual_detector)
        self.load_background_button.setEnabled(valid and not busy and not self.dual_detector)
        self.test_button.setEnabled(ready and (self.dual_detector or blank))
        self.review_checkbox.setEnabled(bool(preliminary) and not busy)
        if not preliminary:
            self.review_checkbox.blockSignals(True)
            self.review_checkbox.setChecked(False)
            self.review_checkbox.blockSignals(False)
            if self.dual_detector:
                self.runner.preliminary_reviewed = False
        self.start_button.setEnabled(ready and preliminary and self.review_checkbox.isChecked() and self.runner.preliminary_reviewed)
        self.abort_button.setEnabled(busy and self._current_kind != "capabilities")
        self.refresh_capabilities_button.setEnabled(self.runner.available and not busy)
        self.save_button.setEnabled(valid and not busy)
        self.load_plan_button.setEnabled(not busy)
        self.new_run_button.setEnabled(not busy)
        self.reconstruction.load_button.setEnabled(not busy)
        self.advanced_group.setEnabled(not acquiring)
        self._populate_override_choices()
        for control in self.inputs.values():
            control.setEnabled(not acquiring)
        if acquiring:
            text = "Acquisition running; requested settings are frozen."
        elif busy:
            text = "Checking the connected device. You can continue editing the experiment and overrides."
        elif not valid:
            text = "Correct the conflict shown above. The acquisition parameters and override dropdowns remain editable."
        elif not self.runner.available:
            text = OPTICAL_ADAPTER_BLOCKER
        elif not verified:
            text = "Device verification is pending or unsuccessful. You can edit saved choices; use Check connected device to retry before acquisition."
        elif self.dual_detector and not preliminary:
            text = ("Load the sample and keep the matched buffer blank in the reference path. Acquire the preliminary sample/reference spectrum."
                    + (" Baseline incompatible: " + "; ".join(conflicts) if self.runner.preliminary is not None and conflicts else ""))
        elif not blank and not self.dual_detector:
            text = "Load a buffer blank and acquire the matching full sequence. " + ("Blank compatibility: " + "; ".join(conflicts) if self.runner.background else "")
        elif not preliminary:
            text = "Compatible blank ready. Load the sample and acquire its preliminary unpumped spectrum."
        elif not self.review_checkbox.isChecked():
            text = "Review the preliminary spectrum and check the review box before starting the pumped scan."
        else:
            text = "Preliminary spectrum reviewed. Start pumped phase scan explicitly when ready."
        self.execution.setText(text)

    def _reviewed(self, checked):
        if checked:
            try:
                self.runner.mark_preliminary_reviewed()
            except (ValueError, RuntimeError) as exc:
                self.scan_status.setText(str(exc))
                self.review_checkbox.setChecked(False)
        elif self.dual_detector:
            self.runner.preliminary_reviewed = False
        self._update_buttons()

    def _begin(self, kind):
        if self.command_running() or (kind != "capabilities" and self.plan is None):
            return
        blocker = self.before_start()
        if blocker:
            self.scan_status.setText(str(blocker))
            return
        if kind == "capabilities":
            self._capability_check_attempted = True
        if kind != "capabilities":
            descriptions = {
                "background": f"Load the buffer blank. Acquire {self.plan.total_scans:,} CH1 scans with the pump inhibited, matching the full sample sequence and its cadence. Probe emission will be enabled.",
                "test": "Load the sample. Acquire an unpumped preliminary CH1 absorption spectrum using the matching buffer blank. Probe emission will be enabled; the pump stays inhibited.",
                "run": f"Start {self.plan.total_scans:,} sample scans including {self.plan.total_pump_events:,} pumped phases at {self.plan.settings.pump_repetition_rate_hz:g} Hz. This enables the pump FIRE and Q-switch outputs with 250 µs separation. Confirm the sample is loaded and the instrument is ready.",
            }
            if self.dual_detector:
                descriptions["test"] = "Load the sample and keep the matched buffer blank in the reference path. Acquire both detectors simultaneously for preliminary review. Probe emission will be enabled; the pump stays inhibited."
                descriptions["run"] = (f"Start {self.plan.total_scans:,} simultaneous sample/reference scans, including {self.plan.total_pump_events:,} pumped phases at {self.plan.settings.pump_repetition_rate_hz:g} Hz. FIRE→Q-switch separation is 250 µs. Confirm the sample and reference blank are loaded and the instrument is ready.")
            if QMessageBox.question(self, "Start acquisition", descriptions[kind], QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
        self.runner.cancel.clear()
        self._pending_result, self._current_kind = None, kind
        # Capture before scheduling the worker. A later editor/destination
        # change cannot retarget an operation waiting to enter its thread.
        from copy import deepcopy
        plan = deepcopy(self.plan)
        save_root = Path(self.save_root_provider()).expanduser().resolve()
        selected = {}
        if kind != "capabilities":
            freeze_selection = getattr(self.runner, "freeze_operation_selection", None)
            if callable(freeze_selection):
                try:
                    selected["selection_snapshot"] = freeze_selection(plan)
                except Exception as exc:
                    self.scan_status.setText(f"Cannot freeze acquisition selections: {exc}")
                    return
        if kind == "capabilities":
            def operation(worker):
                worker.message.emit("Discovering connected supported settings and restoring instruments; no laser acquisition…")
                return {"kind": "capabilities", "capabilities": self.runner.refresh_capabilities()}
        else:
            def operation(worker):
                def progress(message):
                    worker.message.emit(message)
                    if self.runner.last_readback:
                        worker.configured.emit(self.runner.last_readback)
                return self.runner.execute(kind, save_root, plan, on_scan=worker.scan.emit, progress=progress,
                                           laser_authorized=True, **selected)
        self.worker = _PhaseWorker(operation, self)
        self.worker.message.connect(self.scan_status.setText)
        self.worker.scan.connect(self._receive_spectrum)
        self.worker.configured.connect(self._show_actual_readback)
        self.worker.result.connect(lambda result: setattr(self, "_pending_result", result))
        self.worker.stopped.connect(self.scan_status.setText)
        self.worker.failed.connect(self.scan_status.setText)
        self.worker.finished.connect(self._worker_finished)
        self.busy_changed.emit(True)
        self._update_buttons()
        self.worker.start()

    def _receive_spectrum(self, wn, values, label):
        if self._current_kind == "test":
            self.set_latest_scan(wn, values, label if self.dual_detector else "Preliminary unpumped sample")

    def set_latest_scan(self, wavenumbers_cm1, absorption, scan_label="Preliminary unpumped sample"):
        xs, ys = tuple(map(float, wavenumbers_cm1)), tuple(map(float, absorption))
        if len(xs) != len(ys) or not xs:
            raise ValueError("Spectrum needs equally sized, nonempty wavelength and signal arrays")
        self.canvas.points = tuple(zip(xs, ys))
        if self.dual_detector:
            mode = getattr(self, "_preliminary_display_mode", "sample_reference_ratio")
            self.canvas.y_label = "Absorbance" if mode == "absorbance" else "Sample/reference ratio"
            self.preliminary_status.setText("Preliminary unpumped sample/reference spectrum · " +
                ("Absorbance = −log10[(S/R)/B], using the retained channel-balance calibration." if mode == "absorbance" else
                 "Q₀ = S/R; reference path contains the matched buffer blank. Invalid points remain gaps."))
        else:
            self.canvas.y_label = "Absorbance"
            self.preliminary_status.setText(scan_label + " · Transmission = CH1 sample / matched CH1 buffer blank; absorbance = −log10(transmission). Invalid points remain gaps.")
        self.canvas.update()
        self.views.setCurrentIndex(1)

    def _worker_finished(self):
        self.worker.deleteLater()
        self.worker = None
        self.busy_changed.emit(False)
        result = self._pending_result
        if result is not None:
            if result["kind"] == "capabilities":
                self._save_capability_preferences()
                self.scan_status.setText("Connected device checked; supported choices updated and instrument settings restored.")
            else:
                self.save_status.setText(f"Saved: {result['path']}")
                if result["kind"] == "test":
                    if self.dual_detector:
                        self._preliminary_display_mode = result.get("display_mode", "sample_reference_ratio")
                    self.set_latest_scan(result["spectrum"].wavenumber_cm1, result["values"] if self.dual_detector else result["absorbance"])
                    self.review_checkbox.setChecked(False)
                    self.scan_status.setText("Preliminary acquisition complete, pump OFF. Review the spectrum before starting the pumped phase scan.")
                elif result["kind"] == "background":
                    self.scan_status.setText("Full buffer blank sequence retained. Load the sample for preliminary spectral review.")
                elif result["kind"] == "run":
                    try:
                        self.show_reconstruction(result["reconstruction"], result["path"])
                    except Exception as exc:
                        self.scan_status.setText(f"Data saved; display failed: {exc}")
        readback = getattr(self.runner, "last_readback", None)
        if readback:
            self._show_actual_readback(readback)
        self._refresh_plan()
        if result is not None and "path" in result:
            self.save_status.setText(f"Saved: {result['path']}")
            if readback:
                self._show_actual_readback(readback)
        if self._pending_instrument_changes:
            changes, self._pending_instrument_changes = self._pending_instrument_changes, []
            for change in changes:
                self.instrument_state_changed(change)

    def show_reconstruction(self, result, run_path=None):
        self.reconstruction.set_result(result, run_path)
        self.views.setCurrentIndex(0)
        self.scan_status.setText("Reconstruction ready. Rotate or zoom the 3D view; select exact-coordinate spectral/time slices. Unsupported regions remain missing.")

    def _show_actual_readback(self, readback):
        actual = readback.get("hf2li_resolution", {}).get("actual", {})
        if self.dual_detector:
            if all(isinstance(actual.get(role), dict) and {"order", "timeconstant_s", "rate_sps"} <= actual[role].keys()
                   for role in ("sample", "reference")):
                resolution = readback.get("hf2li_resolution", {})
                channels = {role: {**actual[role], **resolution.get(role, {}).get("actual_estimates", {})}
                            for role in ("sample", "reference")}
                self.actual_settings.setText("Actual HF2LI readbacks:\n" + "\n".join(
                    self._channel_settings_text(role, channels[role]) for role in ("sample", "reference")) +
                    f"\nTiming: {actual.get('timing_rate_sps', 0):.12g} Sa/s. Requested, selected and actual settings are retained.")
                if all("temporal_resolution_s" in channel for channel in channels.values()):
                    combined = math.hypot(*(channel["temporal_resolution_s"] for channel in channels.values()))
                    self.actual_settings.setText(self.actual_settings.text() + f" Combined estimated resolution: {combined*1e6:.6g} µs.")
            else:
                self.actual_settings.setText("Both detector and timing readbacks are retained with the acquisition.")
            return
        required = ("order", "timeconstant_s", "rate_sps", "timing_rate_sps")
        if all(key in actual for key in required):
            from control_app.workflows.regular_phase_scan import filter_response
            speed = readback.get("requested_settings", {}).get("scan_speed_cm1_s", self.settings().scan_speed_cm1_s)
            response = filter_response(actual["order"], actual["timeconstant_s"], actual["rate_sps"], actual["timing_rate_sps"], speed)
            self.actual_settings.setText(
                f"Actual HF2LI readbacks: order {actual['order']}; τ {actual['timeconstant_s']*1e6:.9g} µs; "
                f"CH1 {actual['rate_sps']:.12g} Sa/s; timing {actual['timing_rate_sps']:.12g} Sa/s.\n"
                f"Estimated actual resolution {response['temporal_resolution_s']*1e6:.6g} µs; "
                f"filter spectral broadening {response['spectral_broadening_cm1']:.6g} cm⁻¹. "
                "Requested, selected and actual values are retained with the acquisition.")
        else:
            self.actual_settings.setText("Acquisition readbacks retained; this record does not provide all four resolved HF2LI values.")

    def _abort(self):
        self.runner.abort()
        self.abort_button.setEnabled(False)
        self.scan_status.setText("Abort requested. Retaining partial records and restoring safe idle state…")

    def _load_background(self):
        path = QFileDialog.getExistingDirectory(self, "Select a saved buffer blank sequence", str(get_save_location()))
        if path:
            self._pending_background_path = Path(path)
            try:
                self.runner.load_background(Path(path), self.plan)
                self._pending_background_path = None
                self.scan_status.setText(f"Compatible buffer blank selected: {path}")
                self._show_actual_readback(self.runner.last_readback)
            except Exception as exc:
                self.scan_status.setText(f"Blank cannot be used: {exc}")
            self._update_buttons()

    def command_running(self):
        return self.worker is not None

    def output_location_changed(self, path=None):
        # Moving the destination does not alter the saved blank's experiment.
        self._update_buttons()

    def close_blockers(self):
        return (["Operation is running; wait for restoration and native saving."]
                if self.command_running() else [])

    def request_abort(self, reason):
        if self.command_running():
            self._abort()

    def instrument_state_changed(self, change):
        if self.command_running():
            self._pending_instrument_changes.append(change)
            return
        # Invalidation is visible and affects readiness only. The entered
        # scientific settings and all saved measurements remain intact.
        self.runner.invalidate_background()
        self._update_buttons()
        self.scan_status.setText(f"Instrument state changed: {change.reason}. "
                                 "Baseline and preliminary review need revalidation.")

    def _new_run(self):
        if self.command_running():
            return
        self.runner.invalidate_background()
        self._pending_background_path = None
        self.runner.last_readback = {}
        self.runner.cancel.clear()
        self._pending_result = None
        self.review_checkbox.setChecked(False)
        self.canvas.points = ()
        self.canvas.update()
        self.reconstruction.clear_result()
        self.preliminary_status.setText("No preliminary spectrum for this run.")
        self._refresh_plan()
        self.scan_status.setText("Ready for a new run; acquire a preliminary sample/reference spectrum." if self.dual_detector else "Ready for a new run; acquire or select a buffer blank.")

    def load_plan(self, path):
        if self.command_running():
            raise RuntimeError("Wait for acquisition to finish before loading a plan")
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("method") != self.plan_method:
            raise ValueError("Select a Dual-Detector Phase Scan plan; single-detector plans are incompatible." if self.dual_detector else "Select a regular single-detector phase-scan plan; dual-detector plans are incompatible.")
        settings = self.settings_type(**payload["settings"])
        for key, control in self.inputs.items():
            value = getattr(settings, key)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not control.minimum() <= value <= control.maximum():
                raise ValueError(f"Saved {key} is outside the editable range")
        overrides = payload.get("hf2_selection", {}).get("requested", {})
        if not isinstance(overrides, dict) or set(overrides)-set(self.override_inputs):
            raise ValueError("Saved HF2LI overrides are invalid")
        calibration = payload.get("channel_balance_calibration", {})
        if self.dual_detector and (not isinstance(calibration, dict) or
                                  (calibration and not isinstance(calibration.get("bundle_id"), str))):
            raise ValueError("Saved channel-balance selection must identify a promoted bundle")
        # Recalculate from current device capabilities; saved derived values
        # and verification flags never grant acquisition authority.
        self._restoring = True
        try:
            for key, control in self.inputs.items():
                control.setValue(getattr(settings, key))
            self._overrides = dict(overrides)
            if self.dual_detector:
                self.runner.requested_channel_balance = dict(calibration)
            self.advanced_group.setChecked(bool(overrides))
        finally:
            self._restoring = False
        self._refresh_plan()
        self.save_status.setText(f"Plan loaded: {path}")
        pending_blank = getattr(self, "_pending_background_path", None)
        if self.plan is None:
            self.scan_status.setText(self.validation.text())
        elif self.dual_detector:
            conflicts = self.runner.background_conflicts(self.plan)
            self.scan_status.setText(("Baseline incompatible: " + "; ".join(conflicts) if conflicts else "Plan and preliminary baseline match; review the spectrum before starting.")
                                     if self.runner.preliminary is not None else "Plan loaded; acquire a preliminary sample/reference spectrum.")
        elif pending_blank is not None:
            # A previously rejected folder is still the user's requested
            # blank. Revalidate it against the newly loaded plan.
            try:
                self.runner.load_background(pending_blank, self.plan)
                self._pending_background_path = None
                self.scan_status.setText("Plan and selected buffer blank match.")
            except Exception as exc:
                self.scan_status.setText(f"Blank cannot be used: {exc}")
        elif self.runner.background is not None:
            conflicts = self.runner.background_conflicts(self.plan)
            self.scan_status.setText(
                "Blank incompatible: " + "; ".join(conflicts) if conflicts
                else "Plan and selected buffer blank match.")
        else:
            self.scan_status.setText("Plan loaded; acquire or select a buffer blank.")
        self._update_buttons()

    def _load_plan(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load phase-scan plan", str(get_save_location()), "JSON (*.json)")
        if path:
            try:
                self.load_plan(path)
            except (OSError, ValueError, TypeError, KeyError) as exc:
                QMessageBox.warning(self, "Load phase-scan plan", str(exc))

    def _save_plan(self):
        if self.plan is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save phase-scan plan", str(get_save_location() / ("dual_detector_phase_scan_plan.json" if self.dual_detector else "phase_scan_plan.json")), "JSON (*.json)")
        if path:
            try:
                payload = self.plan.to_dict()
                payload["saved_at_utc"] = datetime.now(UTC).isoformat()
                with Path(path).open("x", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=2, allow_nan=False)
                self.save_status.setText(f"Plan saved: {path}")
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Save phase-scan plan", str(exc))

    def _restore_preferences(self):
        if self.preferences is None:
            return
        self._restoring = True
        try:
            payload = json.loads(str(self.preferences.value(self.preference_key, "{}")))
            for key, value in payload.get("inputs", {}).items():
                if key in self.inputs and isinstance(value, (int, float)) and self.inputs[key].minimum() <= value <= self.inputs[key].maximum():
                    self.inputs[key].setValue(value)
            self._overrides = {key: value for key, value in payload.get("overrides", {}).items() if key in self.override_inputs}
            if self.dual_detector:
                calibration = payload.get("channel_balance_calibration", {})
                if isinstance(calibration, dict) and (not calibration or isinstance(calibration.get("bundle_id"), str)):
                    self.runner.requested_channel_balance = dict(calibration)
            self.advanced_group.setChecked(bool(self._overrides))
        except (ValueError, TypeError):
            pass
        finally:
            self._restoring = False

    def _restore_capability_preferences(self):
        if self.preferences is None or self.runner.capabilities is not None:
            return
        try:
            payload = json.loads(str(self.preferences.value(self.preference_key + "_hf2_choices", "null")))
            if not payload:
                return
            caps = replace(self.capabilities_type.from_dict(payload), verified=False)
            # Reject malformed caches. A cache is only a menu of recorded
            # choices, never authority to acquire from an unchecked device.
            self._select_hf2(self.settings_type(), caps)
            self.runner.set_capabilities(caps)
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            return

    def _save_capability_preferences(self):
        caps = self._capabilities()
        if self.preferences is not None and caps.get("verified"):
            payload = dict(caps)
            payload["verified"] = False
            payload["readback_records"] = []  # cache menu choices; each acquisition records its actual settings
            if self.dual_detector:
                for role in ("sample", "reference"):
                    payload[role] = {**payload[role], "verified": False, "readback_records": []}
            self.preferences.setValue(self.preference_key + "_hf2_choices", json.dumps(payload, allow_nan=False))

    def _save_preferences(self):
        if self.preferences is not None:
            payload = {"inputs": {key: control.value() for key, control in self.inputs.items()}, "overrides": self._overrides}
            if self.dual_detector:
                payload["channel_balance_calibration"] = getattr(self.runner, "requested_channel_balance", {})
            self.preferences.setValue(self.preference_key, json.dumps(payload))
