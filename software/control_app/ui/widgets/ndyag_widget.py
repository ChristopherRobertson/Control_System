"""Reusable Qt Nd:YAG alignment widget."""

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
from control_app.workflows.ndyag_alignment import (
    NDYAG_CONTINUOUS_DEFAULT,
    NDYAG_SHOT_COUNT_DEFAULT,
    NDYAG_SHOT_COUNT_MAX,
    NDYAG_SHOT_COUNT_MIN,
    SURELITE_DAT_MODE2_Q_SWITCH_DELAY_DEFAULT_US,
    SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MAX_US,
    SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MIN_US,
)


NDYAG_WIDGET_SPEC = DeviceWidgetSpec(
    device_key="ndyag",
    title="Nd:YAG Alignment",
    status_fields=(
        StatusField("recipe_name", "Recipe"),
        StatusField("repetition_rate_hz", "Rate", units="Hz", critical=True),
        StatusField("shot_count", "Shot Count"),
        StatusField("t6602_trigger_source", "T660-2 Trigger", critical=True),
        StatusField("t6602_synth_frequency", "T660-2 Frequency", units="Hz", critical=True),
        StatusField("t6602_drive_enabled", "T660-2 Drive", critical=True),
        StatusField("t6602_drive_delay", "Drive Delay"),
        StatusField("t6602_drive_width", "Drive Width"),
        StatusField("t6601_trigger_source", "T660-1 Trigger", critical=True),
        StatusField("fire_enabled", "Fire Enabled", critical=True),
        StatusField("fire_delay", "Fire Delay"),
        StatusField("fire_width", "Fire Width"),
        StatusField("q_switch_enabled", "Q-switch Enabled", critical=True),
        StatusField("q_switch_delay", "Q-switch Delay"),
        StatusField("q_switch_width", "Q-switch Width"),
        StatusField("matches_recipe", "Matches Recipe"),
        StatusField("last_error", "Last Error", critical=True),
    ),
    parameter_fields=(
        ParameterField(
            "q_switch_delay_us",
            "Q-switch Delay",
            "float",
            SURELITE_DAT_MODE2_Q_SWITCH_DELAY_DEFAULT_US,
            units="us",
            minimum=SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MIN_US,
            maximum=SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MAX_US,
            step=1.0,
        ),
        ParameterField(
            "continuous_mode",
            "Continuous",
            "bool",
            NDYAG_CONTINUOUS_DEFAULT,
            required=False,
        ),
        ParameterField(
            "shot_count",
            "Shot Count",
            "int",
            NDYAG_SHOT_COUNT_DEFAULT,
            minimum=NDYAG_SHOT_COUNT_MIN,
            maximum=NDYAG_SHOT_COUNT_MAX,
            step=1,
        ),
        ParameterField(
            "approved_laser_safety_condition",
            "Safety Approval",
            "bool",
            False,
            required=False,
        ),
    ),
    controls=(
        WidgetControl("refresh_status", "Refresh", "ndyag.refresh_status"),
        WidgetControl(
            "load_alignment_10hz",
            "Load 10 Hz Workflow",
            "ndyag.load_alignment_10hz",
            kind="guarded",
            safety_approval_required=True,
        ),
        WidgetControl("safe_idle", "Safe Idle", "ndyag.safe_idle", kind="danger"),
    ),
)


try:
    from PySide6.QtCore import QObject, QThread, Signal, Slot
    from PySide6.QtWidgets import (
        QCheckBox,
        QDoubleSpinBox,
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


class NdYagWidget(QWidget):
    """Nd:YAG alignment panel for the 10 Hz Surelite DAT Mode 2 workflow."""

    def __init__(
        self,
        command_handler: WorkflowCommandHandler | None = None,
        *,
        parent: QWidget | None = None,
    ) -> None:
        if not PYSIDE6_AVAILABLE:
            raise RuntimeError("PySide6 is required to instantiate NdYagWidget")
        super().__init__(parent)
        self.command_handler = command_handler or blocked_handler(
            "No workflow command handler is attached."
        )
        self.status_labels: dict[str, Any] = {}
        self.control_buttons: list[Any] = []
        self.safety_approval = QCheckBox("Safety Approval")
        self.q_switch_delay_input = QDoubleSpinBox()
        self.continuous_mode = QCheckBox("Continuous")
        self.shot_count_input = QSpinBox()
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
                    message="An Nd:YAG command is still running; wait for it to finish before closing.",
                )
            )
            event.ignore()
            return
        super().closeEvent(event)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel(NDYAG_WIDGET_SPEC.title)
        title.setObjectName("deviceTitle")
        layout.addWidget(title)
        layout.addWidget(self._build_fixed_settings_group())
        layout.addWidget(self._build_status_group())
        layout.addWidget(self._build_controls_group())
        layout.addWidget(self.result_log)

    def _build_fixed_settings_group(self) -> QGroupBox:
        group = QGroupBox("Timing Settings")
        grid = QGridLayout(group)
        self.q_switch_delay_input.setDecimals(3)
        self.q_switch_delay_input.setMinimum(SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MIN_US)
        self.q_switch_delay_input.setMaximum(SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MAX_US)
        self.q_switch_delay_input.setSingleStep(1.0)
        self.q_switch_delay_input.setValue(SURELITE_DAT_MODE2_Q_SWITCH_DELAY_DEFAULT_US)
        self.q_switch_delay_input.setSuffix(" us")
        self.continuous_mode.setChecked(NDYAG_CONTINUOUS_DEFAULT)
        self.continuous_mode.toggled.connect(self._sync_shot_count_enabled)
        self.shot_count_input.setMinimum(NDYAG_SHOT_COUNT_MIN)
        self.shot_count_input.setMaximum(NDYAG_SHOT_COUNT_MAX)
        self.shot_count_input.setSingleStep(1)
        self.shot_count_input.setValue(NDYAG_SHOT_COUNT_DEFAULT)
        values: tuple[tuple[str, str, str | Any, str, str], ...] = (
            ("Drive", "T660-2 CHD", "10 Hz", "10 us", "positive"),
            ("Fire", "T660-1 CHA", "0 us", "10 us", "negative"),
            ("Q-switch", "T660-1 CHB", self.q_switch_delay_input, "10 us", "negative"),
        )
        for col, header in enumerate(("Signal", "Route", "Delay / Rate", "Width", "Polarity")):
            grid.addWidget(QLabel(header), 0, col)
        for row, (signal, route, delay_or_rate, width, polarity) in enumerate(values):
            grid.addWidget(QLabel(signal), row + 1, 0)
            grid.addWidget(QLabel(route), row + 1, 1)
            if isinstance(delay_or_rate, str):
                grid.addWidget(QLabel(delay_or_rate), row + 1, 2)
            else:
                grid.addWidget(delay_or_rate, row + 1, 2)
            grid.addWidget(QLabel(width), row + 1, 3)
            grid.addWidget(QLabel(polarity), row + 1, 4)
        grid.addWidget(QLabel("Shots"), 4, 0)
        grid.addWidget(self.shot_count_input, 4, 1)
        grid.addWidget(self.continuous_mode, 4, 2)
        self._sync_shot_count_enabled(self.continuous_mode.isChecked())
        return group

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("Readback")
        grid = QGridLayout(group)
        for row, field in enumerate(NDYAG_WIDGET_SPEC.status_fields):
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
        for control in NDYAG_WIDGET_SPEC.controls:
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
                    message="Safety approval must be checked before loading Nd:YAG timing.",
                )
            )
            return
        command = WorkflowCommand(
            device_key=NDYAG_WIDGET_SPEC.device_key,
            command=control.command,
            parameters=self.current_parameters(),
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
        self.safety_approval.setEnabled(enabled)
        self.q_switch_delay_input.setEnabled(enabled)
        self.continuous_mode.setEnabled(enabled)
        self._sync_shot_count_enabled(self.continuous_mode.isChecked() and enabled)

    def current_parameters(self) -> dict[str, Any]:
        """Return current Nd:YAG command parameters."""

        return {
            "approved_laser_safety_condition": self.safety_approval.isChecked(),
            "q_switch_delay_us": float(self.q_switch_delay_input.value()),
            "continuous_mode": self.continuous_mode.isChecked(),
            "shot_count": int(self.shot_count_input.value()),
        }

    def _sync_shot_count_enabled(self, continuous: bool) -> None:
        if continuous:
            self.shot_count_input.setMinimum(NDYAG_SHOT_COUNT_MIN)
            self.shot_count_input.setValue(0)
        else:
            self.shot_count_input.setMinimum(1)
            if self.shot_count_input.value() < 1:
                self.shot_count_input.setValue(1)
        self.shot_count_input.setEnabled(not continuous and self.continuous_mode.isEnabled())

    def _show_result(self, result: WorkflowResult) -> None:
        self.result_log.append(f"{result.status.upper()}: {result.message}")


def _display_value(value: Any) -> str:
    if value is None:
        return "--"
    if isinstance(value, bool):
        return "YES" if value else "NO"
    return str(value)
