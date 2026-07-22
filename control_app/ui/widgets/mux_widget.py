"""Dormant Qt Arduino MUX routing widget.

The active desktop UI does not instantiate this widget while the Arduino MUX is
disabled/bypassed in hardware_configuration.yaml.
"""

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


MUX_WIDGET_SPEC = DeviceWidgetSpec(
    device_key="arduino_mux",
    title="Arduino MUX Router",
    status_fields=(
        StatusField("connected", "Connected", critical=True),
        StatusField("identity", "Identity"),
        StatusField("firmware_version", "Firmware"),
        StatusField("status_response", "Status"),
        StatusField("output_a_route", "MUX Output A"),
        StatusField("output_b_route", "MUX Output B"),
        StatusField("output_ext_route", "MUX Output EXT"),
        StatusField("last_error", "Last Error", critical=True),
    ),
    parameter_fields=(
        ParameterField("output_a_route", "MUX Output A Signal", "choice", ""),
        ParameterField("output_b_route", "MUX Output B Signal", "choice", ""),
        ParameterField("output_ext_route", "MUX Output EXT Signal", "choice", ""),
    ),
    controls=(
        WidgetControl("connect", "Connect", "arduino_mux.connect"),
        WidgetControl("refresh_status", "Refresh", "arduino_mux.refresh_status"),
        WidgetControl("apply_routes", "Apply Routes", "arduino_mux.apply_routes", kind="guarded"),
        WidgetControl("safe_idle", "Safe Idle", "arduino_mux.safe_idle", kind="danger"),
        WidgetControl("disconnect", "Disconnect", "arduino_mux.disconnect"),
    ),
)

ROUTE_PARAMETER_TARGETS = {
    "output_a_route": "output_a",
    "output_b_route": "output_b",
    "output_ext_route": "output_ext",
}


try:
    from PySide6.QtCore import QObject, QThread, Signal, Slot
    from PySide6.QtWidgets import (
        QComboBox,
        QFormLayout,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QMessageBox,
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
    QComboBox = object
    QFormLayout = object
    QFrame = object
    QGridLayout = object
    QGroupBox = object
    QHBoxLayout = object
    QLabel = object
    QMessageBox = object
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


class MuxWidget(QWidget):
    """Independent Arduino MUX panel for selecting MUX output routes."""

    def __init__(
        self,
        command_handler: WorkflowCommandHandler | None = None,
        *,
        route_options: dict[str, tuple[str, ...]] | None = None,
        route_labels: dict[str, str] | None = None,
        default_routes: dict[str, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        if not PYSIDE6_AVAILABLE:
            raise RuntimeError("PySide6 is required to instantiate MuxWidget")
        super().__init__(parent)
        self.command_handler = command_handler or blocked_handler(
            "No workflow command handler is attached."
        )
        self.route_options = route_options or {}
        self.route_labels = route_labels or {}
        self.default_routes = default_routes or {}
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
                    message="An Arduino MUX command is still running; wait for it to finish before closing.",
                )
            )
            event.ignore()
            return
        super().closeEvent(event)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel(MUX_WIDGET_SPEC.title)
        title.setObjectName("deviceTitle")
        layout.addWidget(title)
        layout.addWidget(self._build_status_group())
        layout.addWidget(self._build_route_group())
        layout.addWidget(self._build_controls_group())
        layout.addWidget(self.result_log)

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("Status")
        grid = QGridLayout(group)
        for row, field in enumerate(MUX_WIDGET_SPEC.status_fields):
            name = QLabel(field.label)
            value = QLabel("--")
            value.setFrameShape(QFrame.Panel)
            value.setFrameShadow(QFrame.Sunken)
            value.setMinimumWidth(260)
            grid.addWidget(name, row, 0)
            grid.addWidget(value, row, 1)
            self.status_labels[field.key] = value
        return group

    def _build_route_group(self) -> QGroupBox:
        group = QGroupBox("Routes")
        form = QFormLayout(group)
        for field in MUX_WIDGET_SPEC.parameter_fields:
            widget = self._route_combo(field)
            self.parameter_inputs[field.key] = widget
            form.addRow(field.label, widget)
        return group

    def _route_combo(self, field: ParameterField) -> QComboBox:
        widget = QComboBox()
        target = ROUTE_PARAMETER_TARGETS[field.key]
        routes = self.route_options.get(target, ())
        default_route = self.default_routes.get(field.key, "")
        if not routes:
            widget.addItem("No configured routes", "")
            return widget
        for route in routes:
            widget.addItem(self.route_labels.get(route, route), route)
        if default_route in routes:
            widget.setCurrentIndex(routes.index(default_route))
        widget.currentIndexChanged.connect(lambda _index, combo=widget: self._notify_aux_route(combo))
        return widget

    def _build_controls_group(self) -> QGroupBox:
        group = QGroupBox("Controls")
        row = QHBoxLayout(group)
        for control in MUX_WIDGET_SPEC.controls:
            button = QPushButton(control.label)
            button.clicked.connect(lambda _checked=False, item=control: self._dispatch(item))
            if control.kind == "danger":
                button.setProperty("danger", True)
            row.addWidget(button)
            self.control_buttons.append(button)
        return group

    def _dispatch(self, control: WidgetControl) -> None:
        parameters = self.current_parameters()
        command = WorkflowCommand(
            device_key=MUX_WIDGET_SPEC.device_key,
            command=control.command,
            parameters=parameters,
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
            if isinstance(widget, QComboBox):
                values[key] = widget.currentData()
        return values

    def _show_result(self, result: WorkflowResult) -> None:
        self.result_log.append(f"{result.status.upper()}: {result.message}")

    def _notify_aux_route(self, widget: QComboBox) -> None:
        route_name = str(widget.currentData() or "")
        if "_hf2li_aux" not in route_name:
            return
        QMessageBox.information(
            self,
            "HF2LI AUX Output",
            "Use the HF2LI " + "Lab" + "One interface to select what parameter and demodulator "
            "is used as the AUX output.",
        )


def _display_value(value: Any) -> str:
    if value is None:
        return "--"
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    return str(value)
