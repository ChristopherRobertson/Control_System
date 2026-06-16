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
        StatusField("api_version", "API Version"),
        StatusField("interlock_set", "Interlock", critical=True),
        StatusField("key_switch_set", "Key Switch", critical=True),
        StatusField("armed", "Armed", critical=True),
        StatusField("tec_ready", "TEC Ready", critical=True),
        StatusField("set_wavelength", "Setpoint", units="cm^-1"),
        StatusField("actual_wavelength", "Actual", units="cm^-1"),
        StatusField("light_valid", "Light Valid"),
        StatusField("emission_on", "Emission Gate", critical=True),
        StatusField("tuned", "Tuned"),
        StatusField("last_return_code", "Last Return"),
        StatusField("last_error", "Last Error", critical=True),
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
        WidgetControl("safe_tune", "Safe Tune", "mircat.safe_tune", kind="guarded"),
        WidgetControl("cancel_manual_tune", "Cancel Tune", "mircat.cancel_manual_tune"),
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


try:
    from PySide6.QtCore import QObject, QThread, Signal, Slot
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
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - import-safe in non-UI hardware environments
    PYSIDE6_AVAILABLE = False
    QObject = object
    QThread = object
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
        self.parameter_inputs: dict[str, Any] = {}
        self.status_labels: dict[str, Any] = {}
        self.control_buttons: list[Any] = []
        self._active_thread: Any = None
        self._active_worker: Any = None
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
        form = QFormLayout(group)
        for field in MIRCAT_WIDGET_SPEC.parameter_fields:
            widget = self._parameter_widget(field)
            self.parameter_inputs[field.key] = widget
            label = field.label if field.units is None else f"{field.label} ({field.units})"
            form.addRow(label, widget)
        return group

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
        thread.start()

    def _handle_worker_result(self, result: WorkflowResult) -> None:
        self._show_result(result)
        state = result.data.get("state") if isinstance(result.data, dict) else None
        if isinstance(state, dict):
            self.update_state(state)
        self._set_controls_enabled(True)

    def _clear_active_worker(self) -> None:
        self._active_thread = None
        self._active_worker = None

    def _set_controls_enabled(self, enabled: bool) -> None:
        for button in self.control_buttons:
            button.setEnabled(enabled)

    def current_parameters(self) -> dict[str, Any]:
        """Return current parameter values."""

        values: dict[str, Any] = {}
        for key, widget in self.parameter_inputs.items():
            if isinstance(widget, QCheckBox):
                values[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                values[key] = int(widget.value())
            elif isinstance(widget, QDoubleSpinBox):
                values[key] = float(widget.value())
        return values

    def _show_result(self, result: WorkflowResult) -> None:
        self.result_log.append(f"{result.status.upper()}: {result.message}")


def _display_value(value: Any) -> str:
    if value is None:
        return "--"
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    return str(value)
