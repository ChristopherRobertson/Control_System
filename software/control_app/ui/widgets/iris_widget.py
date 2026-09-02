"""Qt controls for the permanent motorized iris at the OPO exit."""

from __future__ import annotations

from collections.abc import Callable
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


IRIS_STEP_MM = 0.10
IRIS_WIDGET_SPEC = DeviceWidgetSpec(
    device_key="opo_iris",
    title="OPO Exit Iris",
    status_fields=(
        StatusField("current_diameter_mm", "Current Diameter", units="mm", critical=True),
        StatusField("identity", "Device"),
        StatusField("configured_range", "Configured Range"),
    ),
    parameter_fields=(
        ParameterField(
            "diameter_mm",
            "Target Diameter",
            "float",
            11.5,
            units="mm",
            minimum=1.0,
            maximum=11.5,
            step=0.01,
        ),
    ),
    controls=(
        WidgetControl("refresh_status", "Refresh", "opo_iris.refresh_status"),
        WidgetControl("step_down", "Decrease", "opo_iris.step_down", kind="guarded"),
        WidgetControl("step_up", "Increase", "opo_iris.step_up", kind="guarded"),
        WidgetControl("set_diameter", "Set Diameter", "opo_iris.set_diameter", kind="guarded"),
    ),
)


try:
    from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
    from PySide6.QtGui import QDoubleValidator
    from PySide6.QtWidgets import (
        QFrame,
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
except ImportError:  # pragma: no cover - import-safe without desktop dependencies
    PYSIDE6_AVAILABLE = False
    QObject = object
    QThread = object
    QTimer = object
    Signal = None
    Slot = None
    QDoubleValidator = object
    QFrame = object
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
        """Run a serial iris command away from the GUI thread."""

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
            except Exception as exc:  # noqa: BLE001 - widget boundary reports failures
                result = WorkflowResult(status="failed", message=str(exc))
            self.finished.emit(result)


class IrisWidget(QWidget):
    """Direct diameter controls and readback for the OPO exit iris."""

    if PYSIDE6_AVAILABLE:
        busy_changed = Signal(bool)

    def __init__(
        self,
        command_handler: WorkflowCommandHandler | None = None,
        *,
        before_start: Callable[[], str | None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        if not PYSIDE6_AVAILABLE:
            raise RuntimeError("PySide6 is required to instantiate IrisWidget")
        super().__init__(parent)
        self.command_handler = command_handler or blocked_handler(
            "No workflow command handler is attached."
        )
        self.before_start = before_start or (lambda: None)
        self._active_thread: Any = None
        self._active_worker: Any = None
        self._initial_refresh_requested = False
        self.control_buttons: list[Any] = []
        self.status_labels: dict[str, Any] = {}
        self.current_diameter_label = QLabel("-- mm")
        self.current_diameter_label.setObjectName("iris_current_diameter")
        self.target_diameter = QLineEdit()
        self.target_diameter.setObjectName("iris_target_diameter")
        self.target_diameter.setPlaceholderText("Enter diameter in mm")
        self.target_diameter.setValidator(QDoubleValidator(0.0, 99.0, 2, self))
        self.result_log = QTextEdit()
        self.result_log.setReadOnly(True)
        self._build()

    def command_running(self) -> bool:
        """Return whether an iris query or motion command is active."""

        return self._active_thread is not None

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override name
        """Query the current diameter the first time the operator opens the tab."""

        super().showEvent(event)
        if not self._initial_refresh_requested:
            self._initial_refresh_requested = True
            QTimer.singleShot(0, self.refresh_current_diameter)

    def refresh_current_diameter(self) -> None:
        """Dispatch a non-moving readback request."""

        self._dispatch("opo_iris.refresh_status")

    def update_state(self, state: dict[str, Any]) -> None:
        """Display the latest device identity, limits, and diameter readback."""

        current = state.get("current_diameter_mm")
        if isinstance(current, (int, float)):
            self.current_diameter_label.setText(f"{current:.2f} mm")
            self.target_diameter.setText(f"{current:.2f}")
        for key, label in self.status_labels.items():
            label.setText(str(state.get(key, "--")))

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel(IRIS_WIDGET_SPEC.title)
        title.setObjectName("deviceTitle")
        layout.addWidget(title)
        layout.addWidget(self._build_readback_group())
        layout.addWidget(self._build_controls_group())
        note = QLabel(
            "The iris is a beam conditioner, not a safety shutter. Other tabs are locked "
            "while an iris command is active."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addWidget(self.result_log)

    def _build_readback_group(self) -> QGroupBox:
        group = QGroupBox("Readback")
        grid = QGridLayout(group)
        diameter_name = QLabel("Current Diameter")
        self.current_diameter_label.setFrameShape(QFrame.Panel)
        self.current_diameter_label.setFrameShadow(QFrame.Sunken)
        self.current_diameter_label.setMinimumWidth(180)
        grid.addWidget(diameter_name, 0, 0)
        grid.addWidget(self.current_diameter_label, 0, 1)
        for row, field in enumerate(IRIS_WIDGET_SPEC.status_fields[1:], start=1):
            value = QLabel("--")
            value.setFrameShape(QFrame.Panel)
            value.setFrameShadow(QFrame.Sunken)
            grid.addWidget(QLabel(field.label), row, 0)
            grid.addWidget(value, row, 1)
            self.status_labels[field.key] = value
        return group

    def _build_controls_group(self) -> QGroupBox:
        group = QGroupBox("Diameter Controls")
        rows = QVBoxLayout(group)
        step_row = QHBoxLayout()
        down = QPushButton(f"Decrease −{IRIS_STEP_MM:.2f} mm")
        down.setObjectName("iris_step_down")
        down.clicked.connect(
            lambda: self._dispatch("opo_iris.step_down", {"step_mm": IRIS_STEP_MM})
        )
        up = QPushButton(f"Increase +{IRIS_STEP_MM:.2f} mm")
        up.setObjectName("iris_step_up")
        up.clicked.connect(
            lambda: self._dispatch("opo_iris.step_up", {"step_mm": IRIS_STEP_MM})
        )
        step_row.addWidget(down)
        step_row.addWidget(up)
        rows.addLayout(step_row)

        direct_row = QHBoxLayout()
        direct_row.addWidget(QLabel("Target diameter (mm):"))
        direct_row.addWidget(self.target_diameter, 1)
        set_button = QPushButton("Set Diameter")
        set_button.setObjectName("iris_set_diameter")
        set_button.clicked.connect(self._dispatch_direct)
        self.target_diameter.returnPressed.connect(self._dispatch_direct)
        direct_row.addWidget(set_button)
        rows.addLayout(direct_row)

        refresh = QPushButton("Refresh Current Diameter")
        refresh.setObjectName("iris_refresh")
        refresh.clicked.connect(self.refresh_current_diameter)
        rows.addWidget(refresh)
        self.control_buttons.extend((down, up, set_button, refresh))
        return group

    def _dispatch_direct(self) -> None:
        text = self.target_diameter.text().strip()
        if not text:
            self._show_result(
                WorkflowResult(
                    status="blocked",
                    message="Enter a target diameter in millimetres.",
                )
            )
            return
        self._dispatch("opo_iris.set_diameter", {"diameter_mm": text})

    def _dispatch(
        self, command_name: str, parameters: dict[str, Any] | None = None
    ) -> None:
        if self.command_running():
            return
        blocker = self.before_start()
        if blocker:
            self._show_result(WorkflowResult(status="blocked", message=blocker))
            return
        command = WorkflowCommand(
            device_key=IRIS_WIDGET_SPEC.device_key,
            command=command_name,
            parameters=parameters or {},
        )
        self._show_result(WorkflowResult(status="accepted", message="Running iris command..."))
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
        self.busy_changed.emit(True)
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
        self.busy_changed.emit(False)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for button in self.control_buttons:
            button.setEnabled(enabled)
        self.target_diameter.setEnabled(enabled)

    def _show_result(self, result: WorkflowResult) -> None:
        self.result_log.append(f"{result.status.upper()}: {result.message}")
