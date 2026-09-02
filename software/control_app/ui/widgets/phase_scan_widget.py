"""Dedicated single-scan phase-delay planner. Construction never accesses hardware."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import math
from pathlib import Path
from control_app.paths import get_save_location
from control_app.workflows.phase_scan_runner import PhaseScanRunner, OPTICAL_ADAPTER_BLOCKER

from control_app.workflows.phase_scan import (
    PHASE_SCAN_EXECUTION_BLOCKER,
    PhaseScanPlan,
    PhaseScanPlanError,
    PhaseScanSettings,
    build_phase_scan_plan,
)

try:
    from PySide6.QtCore import QPointF, QRectF, Qt, Signal, QThread
    from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
    from PySide6.QtWidgets import (
        QAbstractItemView, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
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
        result = Signal(object)
        failed = Signal(str)

        def __init__(self, operation, parent=None):
            super().__init__(parent)
            self.operation = operation

        def run(self):
            try:
                self.result.emit(self.operation(self))
            except Exception as exc:
                self.failed.emit(f"{type(exc).__name__}: {exc}")

    class _LatestScanCanvas(QWidget):
        """Display only the latest supplied absorption spectrum, in native order."""

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
                message = "Waiting for latest scan" if not self.points else "Latest scan has no valid absorption points"
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


class PhaseScanWidget(QWidget):
    """Editable controls, derived plan and export; execution is visibly unavailable.

    No synthetic acquisition is attached to Start Scan. Hardware integration must
    supply a cancellable workflow with shared instrument ownership and safe abort
    before those two controls can be enabled.
    """

    if PYSIDE6_AVAILABLE:
        latest_scan_received = Signal(object, object, str)
        busy_changed = Signal(bool)

    def __init__(self, parent=None, *, runner=None, diagnostic=None, before_start=None):
        if not PYSIDE6_AVAILABLE:
            raise RuntimeError("PySide6 is required to instantiate PhaseScanWidget")
        super().__init__(parent)
        self.runner = runner or PhaseScanRunner()
        self.diagnostic = diagnostic
        self.before_start = before_start or (lambda: None)
        self.worker = None
        self._latest = None
        self._surface = None
        self._surface_quality_status = None
        self._pending_result = None
        self.inputs = {}
        self.plan: PhaseScanPlan | None = None
        self.summary_values = {}
        self.start_button = QPushButton("Start Scan")
        self.abort_button = QPushButton("Abort Scan")
        self.abort_button.setProperty("danger", True)
        self.save_button = QPushButton("Save Plan…")
        self.background_button = QPushButton("Capture Background")
        self.test_button = QPushButton("Capture Test Scan (pump OFF)")
        self.show_background_button = QPushButton("Show Background")
        self.show_latest_button = QPushButton("Latest Scan")
        self.show_map_button = QPushButton("Completed 3D Map")
        self.diagnostic_button = QPushButton("Capture Inhibited Diagnostic")
        self.start_button.setEnabled(False)
        self.abort_button.setEnabled(False)
        self.start_button.setToolTip(PHASE_SCAN_EXECUTION_BLOCKER)
        self.abort_button.setToolTip("No Phase Scan acquisition is running. This is not a global emergency stop.")
        self.validation = QLabel()
        self.validation.setWordWrap(True)
        self.save_status = QLabel()
        self.save_status.setWordWrap(True)
        self.phase_table = QTableWidget(0, 4)
        self.phase_table.setHorizontalHeaderLabels(["Scan in set", "Condition", "Start after pump", "End after pump"])
        self.phase_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.phase_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.phase_table.verticalHeader().setVisible(False)
        self.phase_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.phase_table.setMinimumHeight(255)
        self.canvas = _LatestScanCanvas()
        self.scan_status = QLabel("No scan data received.")
        self.scan_status.setWordWrap(True)
        self.scan_status.setTextFormat(Qt.TextFormat.PlainText)
        self.latest_scan_received.connect(self.set_latest_scan)
        self._build()
        self.background_button.clicked.connect(lambda: self._begin("background"))
        self.test_button.clicked.connect(lambda: self._begin("test"))
        self.start_button.clicked.connect(lambda: self._begin("run"))
        self.abort_button.clicked.connect(self._abort)
        self.diagnostic_button.clicked.connect(lambda: self._begin("diagnostic"))
        self.show_background_button.clicked.connect(self._show_background)
        self.show_latest_button.clicked.connect(self._show_latest)
        self.show_map_button.clicked.connect(self._show_map)
        self._refresh_plan()

    def _build(self):
        root = QVBoxLayout(self)
        heading = QLabel("<b>Phase-delayed single scan</b> · Room-temperature MbCO")
        root.addWidget(heading)
        intro = QLabel("One unpumped baseline, then one scan at each phase. After the nominal pass, PicoScope detector traces identify missing optical pulses and affected delays are retried before reconstruction.")
        intro.setWordWrap(True)
        root.addWidget(intro)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        controls = QGroupBox("Controls")
        controls_layout = QVBoxLayout(controls)
        form = QFormLayout()
        defaults = PhaseScanSettings()
        fields = (
            ("probe_repetition_rate_hz", "Probe Repetition Rate", " Hz", 1.0, 10_000_000.0, 0, 1000.0,
             "MIRcat probe pulse rate, independent of the pump cadence. Device-specific limits require readback."),
            ("probe_pulse_width_ns", "Probe Pulse Width", " ns", 0.001, 1_000_000.0, 3, 1.0,
             "MIRcat probe pulse width. Rate × width determines the duty cycle."),
            ("start_wavenumber_cm1", "Start Wavenumber", " cm⁻¹", 1.0, 10_000.0, 3, 1.0,
             "Requested sweep start. The instrument preset must confirm QCL coverage."),
            ("stop_wavenumber_cm1", "Stop Wavenumber", " cm⁻¹", 1.0, 10_000.0, 3, 1.0,
             "Requested sweep stop. Direction follows Start → Stop; no separate direction control is needed."),
            ("scan_speed_cm1_s", "Scan Speed", " cm⁻¹/s", 0.001, 1_000_000.0, 3, 100.0,
             "Requested speed, not a measured trajectory. Actual supported speeds require instrument readback."),
            ("phase_delay_us", "Phase Delay", " µs", 0.001, 1_000_000_000.0, 3, 1.0,
             "Increment between signed scan-start offsets. Negative offsets start the scan before its pump."),
            ("pre_pump_ms", "Before Pump", " ms", 0.0, 1_000_000.0, 3, .5,
             "Requested pre-pump observation window at every wavenumber. Also the displayed position of the pump."),
            ("post_pump_ms", "After Pump", " ms", .001, 1_000_000.0, 3, .5,
             "Requested post-pump observation window at every wavenumber."),
            ("pump_threshold_v", "Pump Input Threshold", " V", -9.999, 9.999, 3, .01,
             "Rising threshold for an optional rear Aux In photodetector. Unused for electrical DIO17 sync. Aux inputs accept ±10 V; verify detector output before connection."),
            ("rest_period_s", "Rest Period", " s", 0.1, 1_000_000.0, 6, 0.1,
             "Minimum spacing between pump events, not a sleep after each scan. Includes the phase delay and scan; reset/readiness may take longer."),
            ("minimum_reconstruction_interval_coverage", "Minimum Interval Coverage", "", .01, 1.0, 3, .01,
             "Repeat a phase when any Phase Delay-sized reconstruction interval falls below this optical-pulse coverage fraction. Exactly 0.90 is accepted."),
            ("maximum_scan_missing_fraction", "Maximum Scan Missing Fraction", "", .001, 1.0, 3, .005,
             "A larger whole-scan fraction of opportunities absent from both detectors forces a repeat."),
            ("pulse_detection_threshold_fraction", "Local Pulse Threshold Fraction", "", .01, 1.0, 3, .05,
             "Local detector threshold as a fraction of baseline-to-pulse amplitude. Thresholds are derived independently across each trace."),
        )
        for key, label, suffix, minimum, maximum, decimals, step, tooltip in fields:
            spin = QDoubleSpinBox()
            spin.setObjectName(key)
            spin.setDecimals(decimals)
            spin.setRange(minimum, maximum)
            spin.setSingleStep(step)
            spin.setSuffix(suffix)
            spin.setValue(getattr(defaults, key))
            spin.setKeyboardTracking(False)
            spin.setToolTip(tooltip)
            spin.valueChanged.connect(self._refresh_plan)
            self.inputs[key] = spin
            form.addRow(label, spin)
        repetitions = QSpinBox()
        repetitions.setObjectName("repetitions")
        repetitions.setRange(1, 1_000_000)
        repetitions.setValue(defaults.repetitions)
        repetitions.setToolTip("Repeat the entire baseline + phase series, then average matching phases across sets. One scan per phase in each set.")
        repetitions.setKeyboardTracking(False)
        repetitions.valueChanged.connect(self._refresh_plan)
        self.inputs["repetitions"] = repetitions
        form.addRow("Repetitions", repetitions)
        for key, label, maximum, tooltip in (
            ("missing_pulse_consecutive_limit", "Consecutive Missing Limit", 100,
             "Repeat when this many consecutive expected pulses are absent from both detector channels."),
            ("missing_pulse_retry_limit", "Additional Attempts", 20,
             "Maximum additional acquisitions at an affected phase delay."),
        ):
            spin = QSpinBox()
            spin.setObjectName(key)
            spin.setRange(1, maximum)
            spin.setValue(getattr(defaults, key))
            spin.setToolTip(tooltip)
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(self._refresh_plan)
            self.inputs[key] = spin
            form.addRow(label, spin)
        reference = QComboBox()
        reference.addItem("Electrical sync · DIO17", "electrical_sync")
        reference.addItem("Photodetector · rear Aux In 1", "auxin0")
        reference.addItem("Photodetector · rear Aux In 2", "auxin1")
        reference.setToolTip("Electrical sync uses the existing Nd:YAG Variable Sync connection; it is not optical pump arrival. Aux inputs need an attached detector and suitable pulse amplitude/duration.")
        reference.currentIndexChanged.connect(self._refresh_plan)
        self.inputs["pump_reference"] = reference
        form.addRow("Pump Timing Reference", reference)
        controls_layout.addLayout(form)
        note = QLabel("<b>Phase Delay is the phase increment and pulse-coverage bin width.</b><br>Scan starts span −(Before Pump + scan duration) through After Pump.<br>PicoScope CHA = sample detector, CHB = reference detector, EXT = T660-1 CHD process marker. MIRcat Sweep Active remains on HF2LI DIO21. Test scans keep the pump off.")
        note.setWordWrap(True)
        controls_layout.addWidget(note)
        controls_layout.addWidget(self.validation)
        controls_layout.addWidget(self.save_button)
        controls_layout.addWidget(self.diagnostic_button)
        controls_layout.addStretch(1)
        control_panel = QWidget()
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setMinimumWidth(365)
        controls_scroll.setWidget(controls)
        panel_layout.addWidget(controls_scroll, 1)
        # Acquisition/Abort controls stay visible while parameters scroll.
        panel_layout.addWidget(self.background_button)
        panel_layout.addWidget(self.test_button)
        buttons = QHBoxLayout()
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.abort_button)
        panel_layout.addLayout(buttons)
        self.save_button.clicked.connect(self._save_plan)
        panel_layout.addWidget(self.save_status)
        self.execution = QLabel()
        self.execution.setWordWrap(True)
        self.execution.setTextFormat(Qt.TextFormat.PlainText)
        panel_layout.addWidget(self.execution)
        splitter.addWidget(control_panel)

        preview = QWidget()
        preview_layout = QVBoxLayout(preview)
        summary = QGroupBox("Derived plan")
        summary_form = QFormLayout(summary)
        for key, label in (
            ("duration", "One scan"), ("phases", "Pumped phases / set"),
            ("total", "Total records"), ("pump", "Pump events / cadence"),
            ("probe", "Probe train"), ("coverage", "Missing-pulse policy"),
            ("elapsed", "Nominal elapsed time"),
        ):
            value = QLabel()
            value.setWordWrap(True)
            self.summary_values[key] = value
            summary_form.addRow(label, value)
        preview_layout.addWidget(summary)
        scan_group = QGroupBox("Latest scan")
        scan_layout = QVBoxLayout(scan_group)
        self.plot_stack = QStackedWidget()
        self.plot_stack.addWidget(self.canvas)
        scan_layout.addWidget(self.plot_stack, 1)
        views = QHBoxLayout()
        for button in (self.show_latest_button, self.show_background_button, self.show_map_button):
            views.addWidget(button)
        scan_layout.addLayout(views)
        scan_layout.addWidget(self.scan_status)
        preview_layout.addWidget(scan_group, 1)
        sequence_button = QPushButton("Show phase sequence")
        sequence_button.setCheckable(True)
        sequence_button.toggled.connect(self.phase_table.setVisible)
        sequence_button.toggled.connect(
            lambda visible: sequence_button.setText("Hide phase sequence" if visible else "Show phase sequence")
        )
        preview_layout.addWidget(sequence_button)
        self.phase_table.hide()
        preview_layout.addWidget(self.phase_table)
        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setWidget(preview)
        splitter.addWidget(preview_scroll)
        splitter.setSizes([385, 655])
        root.addWidget(splitter, 1)

    def settings(self) -> PhaseScanSettings:
        return PhaseScanSettings(**{key: widget.currentData() if key == "pump_reference" else widget.value()
                                    for key, widget in self.inputs.items()})

    def _refresh_plan(self, *_args):
        self.save_status.clear()
        try:
            self.plan = build_phase_scan_plan(self.settings())
        except PhaseScanPlanError as exc:
            self.plan = None
            self.validation.setText(f"<b>Check settings:</b> {exc}")
            for value in self.summary_values.values():
                value.setText("—")
            self.phase_table.setRowCount(0)
            self.save_button.setEnabled(False)
        else:
            plan = self.plan
            self.validation.setText("Plan updated. Instrument limits and sample reset still require validation.")
            self.summary_values["duration"].setText(f"{plan.scan_duration_s * 1000:,.6g} ms")
            self.summary_values["phases"].setText(
                f"{plan.phases_per_repetition:,} · {plan.first_phase_delay_us:,.9g} → {plan.last_phase_delay_us:,.9g} µs"
            )
            self.summary_values["total"].setText(
                f"{plan.total_scans:,} = {plan.scans_per_repetition:,} / set × {plan.settings.repetitions:,} sets "
                f"({plan.settings.repetitions:,} unpumped baseline(s))"
            )
            self.summary_values["pump"].setText(
                f"{plan.total_pump_events:,} · at most {plan.pump_rate_hz:,.6g} Hz"
            )
            self.summary_values["probe"].setText(
                f"{plan.probe_duty_cycle:.3%} duty · ≈ {plan.nominal_probe_pulses_per_scan:,.9g} pulses / scan"
            )
            pulses_per_interval = plan.settings.probe_repetition_rate_hz * plan.settings.phase_delay_us * 1e-6
            self.summary_values["coverage"].setText(
                f"{plan.settings.minimum_reconstruction_interval_coverage:.1%} / interval "
                f"(≈ {pulses_per_interval:,.6g} opportunities) · "
                f"{plan.settings.missing_pulse_consecutive_limit} consecutive · "
                f"{plan.settings.maximum_scan_missing_fraction:.1%} whole scan · "
                f"+{plan.settings.missing_pulse_retry_limit} attempts"
            )
            self.summary_values["elapsed"].setText(
                f"{_duration_text(plan.nominal_duration_s)} + setup / settling"
            )
            self.summary_values["elapsed"].setToolTip(
                "One Rest Period slot per record, including baselines; no trailing rest. "
                "This cadence budget is not a measured runtime or a guaranteed reset time."
            )
            self._populate_sequence(plan)
            self.save_button.setEnabled(True)
        if self.plan is not None:
            self.canvas.requested_range = (
                self.plan.settings.start_wavenumber_cm1, self.plan.settings.stop_wavenumber_cm1,
            )
        self.canvas.update()
        self._update_buttons()

    def set_latest_scan(self, wavenumbers_cm1, absorption, scan_label: str = "Latest scan"):
        """Replace, never average, the displayed spectrum with supplied data.

        Supply processed absorption, not raw Sample/Reference voltages. No
        normalization, baseline subtraction, or absorption conversion is guessed
        here. Call on the GUI thread; workers can emit latest_scan_received.
        Non-finite pairs remain explicit gaps in the displayed trace.
        """
        xs = tuple(float(value) for value in wavenumbers_cm1)
        ys = tuple(float(value) for value in absorption)
        if len(xs) != len(ys) or not xs:
            raise ValueError("Latest scan requires equally sized, non-empty wavenumber and absorption arrays")
        self.canvas.points = tuple(zip(xs, ys))
        self.canvas.y_label = "Absorbance"
        self._latest = (xs, ys, scan_label)
        self.show_latest_button.setEnabled(not self.command_running())
        self.plot_stack.setCurrentWidget(self.canvas)
        valid_count = sum(math.isfinite(x) and math.isfinite(y) for x, y in self.canvas.points)
        gaps = len(xs) - valid_count
        self.scan_status.setText(
            f"{scan_label} · {valid_count:,} valid points"
            + (f" · {gaps:,} invalid points shown as gaps" if gaps else "")
        )
        self.canvas.update()

    def _populate_sequence(self, plan: PhaseScanPlan):
        # Keep UI work bounded even when a fine phase grid represents millions
        # of scans. All actual indices remain available in the compact plan.
        count = plan.scans_per_repetition
        indices = list(range(min(4, count)))
        if count > 6:
            indices.append(None)
        indices.extend(index for index in range(max(4, count - 2), count))
        self.phase_table.setRowCount(len(indices))
        for row, index in enumerate(indices):
            if index is None:
                cells = ("…", f"{count - 6:,} more phases", "…", "…")
            else:
                event = plan.event_at(index)
                if not event.pump_enabled:
                    cells = (str(index + 1), "Baseline · pump OFF", "No pump", "No pump")
                else:
                    delay = event.phase_delay_us
                    cells = (
                        f"{index + 1:,}", f"Phase {event.phase_index + 1:,}",
                        f"{delay:,.9g} µs", f"{delay + plan.scan_duration_s * 1_000_000:,.9g} µs",
                    )
            for column, text in enumerate(cells):
                self.phase_table.setItem(row, column, QTableWidgetItem(text))

    def _save_plan(self):
        if self.plan is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Phase Scan Plan", str(get_save_location() / "phase_scan_plan.json"), "JSON (*.json)")
        if not path:
            return
        try:
            payload = self.plan.to_dict()
            payload["saved_at_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
            Path(path).write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Save Phase Scan Plan", str(exc))
            return
        self.save_status.setText(f"Plan saved: {path}")

    def command_running(self) -> bool:
        return self.worker is not None

    def output_location_changed(self):
        self.runner.invalidate_background()
        self._update_buttons()

    def _update_buttons(self):
        busy = self.command_running()
        valid = self.plan is not None
        background = valid and self.runner.background_matches(self.settings())
        self.background_button.setEnabled(valid and self.runner.available and not busy)
        self.test_button.setEnabled(valid and background and self.runner.available and not busy)
        self.start_button.setEnabled(valid and background and self.runner.available and not busy)
        self.start_button.setToolTip("Capture a compatible optical background before Start Scan.")
        self.background_button.setToolTip(OPTICAL_ADAPTER_BLOCKER if not self.runner.available else
                                         "One unpumped sweep; QCL current 1000 mA; saved HF2LI preset.")
        self.abort_button.setEnabled(busy)
        self.diagnostic_button.setEnabled(self.diagnostic is not None and not busy)
        self.show_background_button.setEnabled(bool(background) and not busy)
        self.show_latest_button.setEnabled(self._latest is not None and not busy)
        self.show_map_button.setEnabled(self._surface is not None and not busy)
        self.save_button.setEnabled(valid and not busy)
        for widget in self.inputs.values():
            widget.setEnabled(not busy)
        self.inputs["pump_threshold_v"].setEnabled(not busy and self.inputs["pump_reference"].currentData() != "electrical_sync")
        self.execution.setText(
            "QCL: 1000 mA. HF2LI observes Sweep Active and wavelength markers; PicoScope CHA/CHB record both optical detectors at ≤48 ns/sample and EXT receives T660-1 CHD. A qualified CHD-to-Sweep-Active offset is required before acquisition.\n"
            + ("An acquisition is running. Abort requests safe shutdown." if busy else
               OPTICAL_ADAPTER_BLOCKER if not self.runner.available else
               "Background ready. One scan per phase per set." if background else
               "Capture Background before starting a run; changing scan/probe settings requires a new background.")
        )

    def _begin(self, kind):
        if self.command_running() or (kind != "diagnostic" and self.plan is None):
            return
        blocker = self.before_start()
        if blocker:
            self.scan_status.setText(str(blocker))
            return
        description = (
            "Capture three dark timing records. MIRcat must remain interlocked, unarmed and OFF. "
            "A/B/D outputs remain disabled; only C timing outputs are exercised. HF2LI settings "
            "are restored afterward. This does not capture an optical background."
            if kind == "diagnostic" else
            "Acquire one unpumped background sweep at 1000 mA using the displayed probe/scan settings."
            if kind == "background" else
            "Acquire one probe-only test sweep at 1000 mA and calculate absorbance against the captured background. The pump remains OFF."
            if kind == "test" else
            f"Acquire {self.plan.total_scans:,} scans and {self.plan.total_pump_events:,} pump events "
            "at the displayed settings, using the captured optical background. This enables the Nd:YAG Fire and Q-switch outputs. "
            "After the nominal pass, affected phase delays may be acquired up to the displayed retry limit before reconstruction. "
            "Confirm PicoScope CHA=sample, CHB=reference, EXT=T660-1 CHD, and MIRcat Sweep Active=HF2LI DIO21. The pump must already be configured "
            "for external operation and the beam path made safe."
        )
        if QMessageBox.question(self, "Confirm acquisition", description,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self.runner.cancel.clear()
        self._pending_result = None
        root, plan = get_save_location(), self.plan
        if kind == "diagnostic":
            def operation(worker):
                path = self.diagnostic(root, cancel=self.runner.cancel, progress=worker.message.emit)
                return {"kind": "diagnostic", "path": path}
        else:
            def operation(worker):
                return self.runner.execute(kind, root, plan, on_scan=worker.scan.emit, progress=worker.message.emit,
                                           laser_authorized=True)
        self.worker = _PhaseWorker(operation, self)
        self.worker.message.connect(self.scan_status.setText)
        self.worker.scan.connect(self.set_latest_scan)
        self.worker.result.connect(self._receive_result)
        self.worker.failed.connect(self.scan_status.setText)
        self.worker.finished.connect(self._worker_finished)
        self.busy_changed.emit(True)
        self._update_buttons()
        self.worker.start()

    def _abort(self):
        self.runner.abort()
        self.abort_button.setEnabled(False)
        self.scan_status.setText("Abort requested. Waiting for safe shutdown and partial data to finish saving…")

    def _receive_result(self, result):
        self._pending_result = result

    def _worker_finished(self):
        self.worker.deleteLater()
        self.worker = None
        self.busy_changed.emit(False)
        self._update_buttons()
        result = self._pending_result
        if result is None:
            return
        self.save_status.setText(f"Saved: {result['path']}")
        if result["kind"] == "background":
            self._show_background()
        elif result["kind"] == "test":
            self.scan_status.setText("Test scan complete · pump OFF. " + " ".join(result.get("warnings", [])))
        elif result["kind"] == "diagnostic":
            try:
                summary = json.loads((Path(result["path"]) / "result.json").read_text(encoding="utf-8"))
                warning = (" HF2LI restoration has readback differences; inspect the restoration comparison."
                           if summary.get("restoration_differences") else "")
            except (OSError, ValueError):
                warning = " Result summary could not be read; inspect the saved folder."
            self.scan_status.setText("Inhibited diagnostic saved. No optical background, wavelength sweep or absorbance was measured." + warning)
        else:
            try:
                self.show_reconstruction(result["reconstruction"], result["path"])
            except Exception as exc:
                self.scan_status.setText(f"Data saved; 3D display failed: {exc}")

    def _show_background(self):
        background = self.runner.background
        if background is None:
            return
        spectrum = background.spectrum
        self.canvas.points = tuple(zip(spectrum.wavenumber_cm1, spectrum.ratio()))
        self.canvas.y_label = "Background S₀/R₀"
        self.plot_stack.setCurrentWidget(self.canvas)
        self.scan_status.setText("Captured background · sample/reference ratio (I₀). Used for absolute absorbance; self-normalization would be A = 0.")
        if spectrum.metadata.get("provisional"):
            self.scan_status.setText(self.scan_status.text() + " PROVISIONAL wavenumber axis; inspect the saved marker data.")
        self.canvas.update()

    def _show_latest(self):
        if self._latest is not None:
            self.set_latest_scan(*self._latest)

    def _show_map(self):
        if self._surface is not None:
            self.plot_stack.setCurrentWidget(self._surface)
            if self._surface_quality_status == "INCOMPLETE_MISSING_PULSE_COVERAGE":
                self.scan_status.setText("INCOMPLETE_MISSING_PULSE_COVERAGE · diagnostic reconstruction only; not for publication.")
            else:
                self.scan_status.setText("Completed run · reconstructed absorbance map. This view is not a live acquisition.")

    def show_reconstruction(self, result, run_path=None):
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from control_app.ui.widgets.phase_scan_surface import make_surface_figure
        figure = make_surface_figure(result)
        if run_path is not None:
            target = Path(run_path) / "processed" / "absorbance_map.png"
            if not target.exists():
                figure.savefig(target, dpi=180)
        if self._surface is not None:
            self.plot_stack.removeWidget(self._surface)
            self._surface.deleteLater()
        self._surface = FigureCanvasQTAgg(figure)
        self._surface_quality_status = result.get("completion_status", "COMPLETE")
        self.plot_stack.addWidget(self._surface)
        self.show_map_button.setEnabled(not self.command_running())
        timing = "electrical pump-sync reference" if "electrical_sync" in result.get("pump_reference_bases", []) else "observed pump reference"
        if result.get("completion_status") == "INCOMPLETE_MISSING_PULSE_COVERAGE":
            self.scan_status.setText(
                "INCOMPLETE_MISSING_PULSE_COVERAGE · best-effort diagnostic reconstruction with deficient regions left empty. "
                "All outputs are not for publication."
            )
        else:
            self.scan_status.setText(f"Run complete · absorbance vs wavenumber and {timing}. "
                "Unsupported regions are left empty; phase increment is not time resolution. "
                + ("PROVISIONAL wavenumber axis. " if result.get("provisional") else ""))
        self.plot_stack.setCurrentWidget(self._surface)
        self._surface.draw_idle()


def _duration_text(seconds: float) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, remaining = divmod(remainder, 60)
    return f"{int(hours):,} h {int(minutes):02d} min {remaining:06.3f} s"
