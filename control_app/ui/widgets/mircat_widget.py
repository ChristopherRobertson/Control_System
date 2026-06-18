"""Reusable Qt MIRcat device widget."""

from __future__ import annotations

from typing import Any

from control_app.ui.contracts import (
    DeviceWidgetSpec,
    ParameterField,
    StatusField,
    WidgetControl,
    WorkflowCommand,
    WorkflowCommandHandler,
    WorkflowResult,
    blocked_handler,
)


MIRCAT_WIDGET_SPEC = DeviceWidgetSpec(
    device_key="mircat",
    title="MIRcat Probe Laser",
    status_fields=(
        StatusField("connected", "Connected", critical=True),
        StatusField("armed", "Armed", critical=True),
        StatusField("tec_ready", "TEC Ready", critical=True),
        StatusField("emission_on", "Emission Gate", critical=True),
        StatusField("tuned", "Tuned"),
        StatusField("scan_active", "Scan Active"),
        StatusField("scan_paused", "Scan Paused"),
        StatusField("scan_current_wavelength", "Scan Wavenumber", units="cm^-1"),
        StatusField("qcl_pulse_rate_hz", "Pulse Rate", units="Hz"),
        StatusField("qcl_pulse_width_ns", "Pulse Width", units="ns"),
    ),
    parameter_fields=(
        ParameterField(
            "wavenumber_cm1",
            "Wavenumber",
            "float",
            1858.0,
            units="cm^-1",
            minimum=1638.8,
            maximum=2077.3,
            step=0.1,
        ),
        ParameterField("qcl", "QCL", "int", 1, minimum=1, maximum=4, step=1),
        ParameterField(
            "scan_start_cm1",
            "Start Wavenumber",
            "float",
            1848.0,
            units="cm^-1",
            minimum=1638.8,
            maximum=2077.3,
            step=0.1,
        ),
        ParameterField(
            "scan_stop_cm1",
            "Stop Wavenumber",
            "float",
            1868.0,
            units="cm^-1",
            minimum=1638.8,
            maximum=2077.3,
            step=0.1,
        ),
        ParameterField(
            "scan_rate_cm1_s",
            "Scan Rate",
            "float",
            1.0,
            units="cm^-1/s",
            minimum=0.001,
            step=0.1,
        ),
        ParameterField("scan_repetitions", "Repetitions", "int", 1, minimum=1, maximum=65535, step=1),
        ParameterField(
            "pulse_rate_hz",
            "Pulse Repetition Rate",
            "float",
            100000.0,
            units="Hz",
            minimum=0.001,
            step=1000.0,
        ),
        ParameterField(
            "pulse_width_ns",
            "Pulse Width",
            "float",
            500.0,
            units="ns",
            minimum=0.001,
            step=10.0,
        ),
        ParameterField("tec_timeout_s", "TEC Timeout", "float", 120.0, units="s", minimum=1),
        ParameterField("tune_timeout_s", "Tune Timeout", "float", 120.0, units="s", minimum=1),
        ParameterField("poll_interval_s", "Poll Interval", "float", 0.5, units="s", minimum=0.1),
        ParameterField(
            "approved_laser_safety_condition",
            "Safety Approval",
            "bool",
            False,
            required=False,
        ),
    ),
    controls=(
        WidgetControl("initialize", "Initialize", "mircat.initialize"),
        WidgetControl("refresh_status", "Refresh", "mircat.refresh_status"),
        WidgetControl("arm", "Arm", "mircat.arm", kind="guarded"),
        WidgetControl("safe_tune", "Direct Tune", "mircat.safe_tune", kind="guarded"),
        WidgetControl("configure_pulse", "Apply Pulse Params", "mircat.configure_pulse", kind="guarded"),
        WidgetControl(
            "start_sweep_scan",
            "Start Scan",
            "mircat.start_sweep_scan",
            kind="guarded",
            safety_approval_required=True,
        ),
        WidgetControl("stop_scan", "Stop Scan", "mircat.stop_scan", kind="danger"),
        WidgetControl("cancel_manual_tune", "Cancel Manual Tune", "mircat.cancel_manual_tune"),
        WidgetControl("emission_off", "Emission Off", "mircat.emission_off", kind="danger"),
        WidgetControl("disarm", "Disarm", "mircat.disarm", kind="danger"),
        WidgetControl("deinitialize", "Deinitialize", "mircat.deinitialize"),
        WidgetControl(
            "emission_on",
            "Emission On",
            "mircat.emission_on",
            kind="guarded",
            safety_approval_required=True,
        ),
    ),
)

DIRECT_PARAMETER_KEYS = ("wavenumber_cm1", "pulse_rate_hz", "pulse_width_ns")
SCAN_PARAMETER_KEYS = (
    "scan_start_cm1",
    "scan_stop_cm1",
    "scan_rate_cm1_s",
    "scan_repetitions",
    "pulse_rate_hz",
    "pulse_width_ns",
)
COMMON_PARAMETER_KEYS = (
    "qcl",
    "tec_timeout_s",
    "tune_timeout_s",
    "poll_interval_s",
    "approved_laser_safety_condition",
)


try:
    from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
    from PySide6.QtWidgets import (
        QCheckBox,
        QDoubleSpinBox,
        QFormLayout,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSpinBox,
        QTabWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - import-safe in non-UI hardware environments
    PYSIDE6_AVAILABLE = False
    QObject = object
    QThread = object
    QTimer = object
    Signal = None
    Slot = None
    QCheckBox = object
    QDoubleSpinBox = object
    QFormLayout = object
    QFrame = object
    QGridLayout = object
    QGroupBox = object
    QHBoxLayout = object
    QLabel = object
    QPushButton = object
    QSpinBox = object
    QTabWidget = object
    QTextEdit = object
    QVBoxLayout = object
    QWidget = object


if PYSIDE6_AVAILABLE:

    class _CommandWorker(QObject):
        """Run one workflow command away from the GUI thread."""

        finished = Signal(object)

        def __init__(
            self,
            handler: WorkflowCommandHandler,
            command: WorkflowCommand,
        ) -> None:
            super().__init__()
            self.handler = handler
            self.command = command

        @Slot()
        def run(self) -> None:
            try:
                result = self.handler(self.command)
            except Exception as exc:  # noqa: BLE001 - widget boundary reports workflow errors
                result = WorkflowResult(status="failed", message=str(exc))
            self.finished.emit(result)


class MircatWidget(QWidget):
    """Independent MIRcat panel designed for the unified desktop interface."""

    def __init__(
        self,
        command_handler: WorkflowCommandHandler | None = None,
        *,
        parent: QWidget | None = None,
    ) -> None:
        if not PYSIDE6_AVAILABLE:
            raise RuntimeError("PySide6 is required to instantiate MircatWidget")
        super().__init__(parent)
        self.command_handler = command_handler or blocked_handler(
            "No workflow command handler is attached."
        )
        self.parameter_inputs: dict[str, list[Any]] = {}
        self.status_labels: dict[str, Any] = {}
        self.control_buttons: list[Any] = []
        self._active_thread: Any = None
        self._active_worker: Any = None
        self._active_command: str | None = None
        self.result_log = QTextEdit()
        self.result_log.setReadOnly(True)
        self._build()

    def update_state(self, state: dict[str, Any]) -> None:
        """Update status labels from a workflow state dictionary."""

        for key, label in self.status_labels.items():
            value = state.get(key)
            label.setText(_display_value(value))

    def command_running(self) -> bool:
        """Return whether a workflow command is still active."""

        return self._active_thread is not None

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override name
        """Prevent closing this widget while a hardware command is active."""

        if self.command_running():
            self._show_result(
                WorkflowResult(
                    status="blocked",
                    message="A MIRcat command is still running; wait for it to finish before closing.",
                )
            )
            event.ignore()
            return
        super().closeEvent(event)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel(MIRCAT_WIDGET_SPEC.title)
        title.setObjectName("deviceTitle")
        layout.addWidget(title)
        layout.addWidget(self._build_status_group())
        layout.addWidget(self._build_parameter_group())
        layout.addWidget(self._build_controls_group())
        layout.addWidget(self.result_log)

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("Status")
        grid = QGridLayout(group)
        for row, field in enumerate(MIRCAT_WIDGET_SPEC.status_fields):
            name = QLabel(field.label)
            value = QLabel("--")
            value.setFrameShape(QFrame.Panel)
            value.setFrameShadow(QFrame.Sunken)
            value.setMinimumWidth(160)
            grid.addWidget(name, row, 0)
            grid.addWidget(value, row, 1)
            self.status_labels[field.key] = value
        return group

    def _build_parameter_group(self) -> QGroupBox:
        group = QGroupBox("Parameters")
        layout = QVBoxLayout(group)
        tabs = QTabWidget()
        tabs.addTab(self._build_parameter_page(DIRECT_PARAMETER_KEYS), "Direct Tune")
        tabs.addTab(self._build_parameter_page(SCAN_PARAMETER_KEYS), "Sweep Scan")
        layout.addWidget(tabs)

        common = QGroupBox("Common")
        common_form = QFormLayout(common)
        self._add_parameter_fields(common_form, COMMON_PARAMETER_KEYS)
        layout.addWidget(common)
        return group

    def _build_parameter_page(self, keys: tuple[str, ...]) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self._add_parameter_fields(form, keys)
        return page

    def _add_parameter_fields(self, form: QFormLayout, keys: tuple[str, ...]) -> None:
        fields = {field.key: field for field in MIRCAT_WIDGET_SPEC.parameter_fields}
        for key in keys:
            field = fields[key]
            widget = self._parameter_widget(field)
            self.parameter_inputs.setdefault(field.key, []).append(widget)
            self._connect_linked_parameter(field.key, widget)
            form.addRow(_field_label(field), widget)

    def _connect_linked_parameter(self, key: str, widget: Any) -> None:
        if isinstance(widget, QCheckBox):
            widget.toggled.connect(lambda value, name=key, source=widget: self._sync_parameter(name, source, value))
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            widget.valueChanged.connect(
                lambda value, name=key, source=widget: self._sync_parameter(name, source, value)
            )

    def _parameter_widget(self, field: ParameterField) -> Any:
        if field.kind == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(field.default))
            return widget
        if field.kind == "int":
            widget = QSpinBox()
            widget.setMinimum(int(field.minimum if field.minimum is not None else -2147483648))
            widget.setMaximum(int(field.maximum if field.maximum is not None else 2147483647))
            widget.setSingleStep(int(field.step or 1))
            widget.setValue(int(field.default))
            return widget
        widget = QDoubleSpinBox()
        widget.setDecimals(3)
        widget.setMinimum(float(field.minimum if field.minimum is not None else -1.0e12))
        widget.setMaximum(float(field.maximum if field.maximum is not None else 1.0e12))
        widget.setSingleStep(float(field.step or 1.0))
        widget.setValue(float(field.default))
        return widget

    def _build_controls_group(self) -> QGroupBox:
        group = QGroupBox("Controls")
        rows = QVBoxLayout(group)
        row = QHBoxLayout()
        for index, control in enumerate(MIRCAT_WIDGET_SPEC.controls):
            button = QPushButton(control.label)
            button.clicked.connect(lambda _checked=False, item=control: self._dispatch(item))
            if control.kind == "danger":
                button.setProperty("danger", True)
            row.addWidget(button)
            self.control_buttons.append(button)
            if (index + 1) % 4 == 0:
                rows.addLayout(row)
                row = QHBoxLayout()
        if row.count():
            rows.addLayout(row)
        return group

    def _dispatch(self, control: WidgetControl) -> None:
        parameters = self.current_parameters()
        safety_approval = bool(parameters.get("approved_laser_safety_condition"))
        if control.safety_approval_required and not safety_approval:
            self._show_result(
                WorkflowResult(
                    status="blocked",
                    message="Safety approval must be checked before this command can run.",
                )
            )
            return
        command = WorkflowCommand(
            device_key=MIRCAT_WIDGET_SPEC.device_key,
            command=control.command,
            parameters=parameters,
            safety_approval=safety_approval,
        )
        self._show_result(
            WorkflowResult(status="accepted", message=f"Running {control.label}...")
        )
        self._set_controls_enabled(False)
        thread = QThread(self)
        worker = _CommandWorker(self.command_handler, command)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._handle_worker_result)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_active_worker)
        self._active_thread = thread
        self._active_worker = worker
        self._active_command = control.command
        thread.start()

    def _handle_worker_result(self, result: WorkflowResult) -> None:
        self._show_result(result)
        state = result.data.get("state") if isinstance(result.data, dict) else None
        if isinstance(state, dict):
            self.update_state(state)
        if self._active_command == "mircat.arm":
            self._show_result(
                WorkflowResult(
                    status="accepted",
                    message="Waiting 5 seconds for the armed state to settle...",
                )
            )
            QTimer.singleShot(5000, lambda: self._set_controls_enabled(True))
        else:
            self._set_controls_enabled(True)

    def _clear_active_worker(self) -> None:
        self._active_thread = None
        self._active_worker = None
        self._active_command = None

    def _set_controls_enabled(self, enabled: bool) -> None:
        for button in self.control_buttons:
            button.setEnabled(enabled)

    def current_parameters(self) -> dict[str, Any]:
        """Return current parameter values."""

        values: dict[str, Any] = {}
        for key, widgets in self.parameter_inputs.items():
            widget = widgets[0]
            if isinstance(widget, QCheckBox):
                values[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                values[key] = int(widget.value())
            elif isinstance(widget, QDoubleSpinBox):
                values[key] = float(widget.value())
        return values

    def _sync_parameter(self, key: str, source: Any, value: Any) -> None:
        for widget in self.parameter_inputs.get(key, []):
            if widget is source:
                continue
            widget.blockSignals(True)
            try:
                if isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    widget.setValue(value)
            finally:
                widget.blockSignals(False)

    def _show_result(self, result: WorkflowResult) -> None:
        self.result_log.append(f"{result.status.upper()}: {result.message}")


def _display_value(value: Any) -> str:
    if value is None:
        return "--"
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    return str(value)


def _field_label(field: ParameterField) -> str:
    if field.units is None:
        return field.label
    return f"{field.label} ({field.units})"
