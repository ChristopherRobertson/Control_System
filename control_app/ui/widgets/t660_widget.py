"""Reusable Qt T660-2 timing widget."""

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


T660_WIDGET_SPEC = DeviceWidgetSpec(
    device_key="t660_2",
    title="T660-2 Timing",
    status_fields=(
        StatusField("identity", "Identity"),
        StatusField("trigger_source", "Trigger Source", critical=True),
        StatusField("synth_frequency", "Synth Frequency", units="Hz"),
        StatusField("shots", "Shots"),
        StatusField("channel_a_enabled", "CHA Enabled", critical=True),
        StatusField("channel_a_delay", "CHA Delay"),
        StatusField("channel_a_width", "CHA Width"),
        StatusField("channel_b_enabled", "CHB Enabled", critical=True),
        StatusField("channel_b_delay", "CHB Delay"),
        StatusField("channel_b_width", "CHB Width"),
        StatusField("channel_c_enabled", "CHC Enabled"),
        StatusField("channel_d_enabled", "CHD Enabled"),
        StatusField("matches_recipe", "Matches Recipe"),
        StatusField("last_error", "Last Error", critical=True),
    ),
    parameter_fields=(
        ParameterField(
            "approved_laser_safety_condition",
            "Safety Approval",
            "bool",
            False,
            required=False,
        ),
    ),
    controls=(
        WidgetControl("refresh_status", "Refresh", "t660_2.refresh_status"),
        WidgetControl("start_cha", "Start CHA", "t660_2.start_cha", kind="guarded"),
        WidgetControl(
            "start_chb",
            "Start CHB",
            "t660_2.start_chb",
            kind="guarded",
            safety_approval_required=True,
        ),
        WidgetControl(
            "start_cha_chb",
            "Start CHA + CHB",
            "t660_2.start_cha_chb",
            kind="guarded",
            safety_approval_required=True,
        ),
        WidgetControl("safe_idle", "Safe Idle", "t660_2.safe_idle", kind="danger"),
    ),
)


try:
    from PySide6.QtCore import QObject, QThread, Signal, Slot
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QFrame,
        QFormLayout,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
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
    QComboBox = object
    QFrame = object
    QFormLayout = object
    QGridLayout = object
    QGroupBox = object
    QHBoxLayout = object
    QLabel = object
    QLineEdit = object
    QPushButton = object
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


class T660Widget(QWidget):
    """Fixed-purpose T660-2 panel for alignment timing."""

    def __init__(
        self,
        command_handler: WorkflowCommandHandler | None = None,
        *,
        parent: QWidget | None = None,
    ) -> None:
        if not PYSIDE6_AVAILABLE:
            raise RuntimeError("PySide6 is required to instantiate T660Widget")
        super().__init__(parent)
        self.command_handler = command_handler or blocked_handler(
            "No workflow command handler is attached."
        )
        self.status_labels: dict[str, Any] = {}
        self.control_buttons: list[Any] = []
        self.safety_approval = QCheckBox("Safety Approval")
        self.manual_source = QComboBox()
        self.manual_source.addItems(["SYN", "OFF"])
        self.manual_frequency = QLineEdit("2MHz")
        self.manual_cha_delay = QLineEdit("0ns")
        self.manual_cha_width = QLineEdit("150ns")
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
                    message="A T660 command is still running; wait for it to finish before closing.",
                )
            )
            event.ignore()
            return
        super().closeEvent(event)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel(T660_WIDGET_SPEC.title)
        title.setObjectName("deviceTitle")
        layout.addWidget(title)
        layout.addWidget(self._build_manual_cha_group())
        layout.addWidget(self._build_fixed_settings_group())
        layout.addWidget(self._build_status_group())
        layout.addWidget(self._build_controls_group())
        layout.addWidget(self.result_log)

    def _build_fixed_settings_group(self) -> QGroupBox:
        group = QGroupBox("Fixed Settings")
        grid = QGridLayout(group)
        values = (
            ("CHA", "2 MHz", "150 ns", "0"),
            ("CHB", "2 MHz", "150 ns", "5 ms"),
        )
        for row, (channel, rate, width, delay) in enumerate(values):
            grid.addWidget(QLabel(channel), row, 0)
            grid.addWidget(QLabel(rate), row, 1)
            grid.addWidget(QLabel(width), row, 2)
            grid.addWidget(QLabel(delay), row, 3)
        return group

    def _build_manual_cha_group(self) -> QGroupBox:
        """Provide a laser-safe CHA-only synthesizer diagnostic control."""

        group = QGroupBox("Manual CHA Reference Test")
        form = QFormLayout(group)
        form.addRow("Trigger source", self.manual_source)
        form.addRow("Synth frequency", self.manual_frequency)
        form.addRow("CHA delay", self.manual_cha_delay)
        form.addRow("CHA width", self.manual_cha_width)
        button = QPushButton("Apply + Start CHA Only")
        button.clicked.connect(self._dispatch_manual_cha)
        form.addRow(button)
        self.control_buttons.append(button)
        return group

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("Readback")
        grid = QGridLayout(group)
        for row, field in enumerate(T660_WIDGET_SPEC.status_fields):
            name = QLabel(field.label)
            value = QLabel("--")
            value.setFrameShape(QFrame.Panel)
            value.setFrameShadow(QFrame.Sunken)
            value.setMinimumWidth(180)
            grid.addWidget(name, row, 0)
            grid.addWidget(value, row, 1)
            self.status_labels[field.key] = value
        return group

    def _build_controls_group(self) -> QGroupBox:
        group = QGroupBox("Controls")
        rows = QVBoxLayout(group)
        rows.addWidget(self.safety_approval)
        row = QHBoxLayout()
        for control in T660_WIDGET_SPEC.controls:
            button = QPushButton(control.label)
            button.clicked.connect(lambda _checked=False, item=control: self._dispatch(item))
            if control.kind == "danger":
                button.setProperty("danger", True)
            row.addWidget(button)
            self.control_buttons.append(button)
        rows.addLayout(row)
        return group

    def _dispatch(self, control: WidgetControl) -> None:
        safety_approval = self.safety_approval.isChecked()
        if control.safety_approval_required and not safety_approval:
            self._show_result(
                WorkflowResult(
                    status="blocked",
                    message="Safety approval must be checked before enabling CHB.",
                )
            )
            return
        command = WorkflowCommand(
            device_key=T660_WIDGET_SPEC.device_key,
            command=control.command,
            parameters={"approved_laser_safety_condition": safety_approval},
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

    def _dispatch_manual_cha(self) -> None:
        """Start only CHA; CHB/CHC/CHD and all T660-1 channels remain off."""

        parameters = {
            "approved_laser_safety_condition": False,
            "trigger_source": self.manual_source.currentText(),
            "frequency": self.manual_frequency.text().strip(),
            "cha_delay": self.manual_cha_delay.text().strip(),
            "cha_width": self.manual_cha_width.text().strip(),
        }
        command = WorkflowCommand(
            device_key=T660_WIDGET_SPEC.device_key,
            command="t660_2.apply_manual_cha",
            parameters=parameters,
            safety_approval=False,
        )
        self._show_result(WorkflowResult(status="accepted", message="Applying manual CHA-only reference test..."))
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
        self.safety_approval.setEnabled(enabled)
        self.manual_source.setEnabled(enabled)
        self.manual_frequency.setEnabled(enabled)
        self.manual_cha_delay.setEnabled(enabled)
        self.manual_cha_width.setEnabled(enabled)

    def _show_result(self, result: WorkflowResult) -> None:
        self.result_log.append(f"{result.status.upper()}: {result.message}")


def _display_value(value: Any) -> str:
    if value is None:
        return "--"
    if isinstance(value, bool):
        return "YES" if value else "NO"
    return str(value)
