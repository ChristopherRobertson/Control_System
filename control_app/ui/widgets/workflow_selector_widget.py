"""Recipe-driven workflow selector with a configure-and-save run gate."""

from __future__ import annotations

import json
from typing import Any

from control_app.ui.contracts import WorkflowCommand, WorkflowCommandHandler, WorkflowResult, blocked_handler
from control_app.workflows.selectable_workflows import public_workflow_catalog

try:
    from PySide6.QtCore import QObject, QThread, Signal, Slot
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QFormLayout,
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
except ImportError:  # pragma: no cover
    PYSIDE6_AVAILABLE = False
    QObject = object
    QThread = object
    Signal = None
    Slot = None
    QWidget = object


if PYSIDE6_AVAILABLE:

    class _WorkflowWorker(QObject):
        finished = Signal(object)

        def __init__(self, handler: WorkflowCommandHandler, command: WorkflowCommand) -> None:
            super().__init__()
            self.handler = handler
            self.command = command

        @Slot()
        def run(self) -> None:
            try:
                result = self.handler(self.command)
            except Exception as exc:  # noqa: BLE001
                result = WorkflowResult(status="failed", message=str(exc))
            self.finished.emit(result)


class WorkflowSelectorWidget(QWidget):
    """Select, edit, save, and run an approved backend workflow."""

    def __init__(self, command_handler: WorkflowCommandHandler | None = None, parent=None) -> None:
        if not PYSIDE6_AVAILABLE:
            raise RuntimeError("PySide6 is required to instantiate WorkflowSelectorWidget")
        super().__init__(parent)
        self.command_handler = command_handler or blocked_handler("No workflow handler is attached.")
        self.catalog = public_workflow_catalog()
        self.parameter_inputs: dict[str, Any] = {}
        self.current_definition: dict[str, Any] | None = None
        self.configured_fingerprint: str | None = None
        self._active_thread = None
        self._active_worker = None
        self._active_action: str | None = None
        self._workflow_active = False
        self.scan_data_ready_callback = None

        self.selector = QComboBox()
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.fixed_settings = QTextEdit()
        self.fixed_settings.setReadOnly(True)
        self.fixed_settings.setMaximumHeight(125)
        self.parameter_group = QGroupBox("Adjustable Settings")
        self.parameter_form = QFormLayout(self.parameter_group)
        self.safety_approval = QCheckBox("Approved laser-safety condition confirmed")
        self.configure_button = QPushButton("Configure && Save")
        self.run_button = QPushButton("Run Configured Workflow")
        self.run_button.setEnabled(False)
        self.stop_button = QPushButton("Stop / Safe Idle")
        self.stop_button.setEnabled(False)
        self.stop_button.setProperty("danger", True)
        self.status = QTextEdit()
        self.status.setReadOnly(True)
        self._build()
        self._populate_selector()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Workflow"))
        layout.addWidget(self.selector)
        layout.addWidget(self.description)
        fixed_group = QGroupBox("Preset Device and Timing Settings")
        fixed_layout = QVBoxLayout(fixed_group)
        fixed_layout.addWidget(self.fixed_settings)
        layout.addWidget(fixed_group)
        layout.addWidget(self.parameter_group)
        layout.addWidget(self.safety_approval)
        buttons = QHBoxLayout()
        buttons.addWidget(self.configure_button)
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.stop_button)
        layout.addLayout(buttons)
        layout.addWidget(self.status)
        self.selector.currentIndexChanged.connect(self._workflow_changed)
        self.configure_button.clicked.connect(self._configure)
        self.run_button.clicked.connect(self._run)
        self.stop_button.clicked.connect(self._stop)
        self.safety_approval.toggled.connect(self._update_run_enabled)

    def _populate_selector(self) -> None:
        for definition in self.catalog:
            self.selector.addItem(str(definition["label"]), definition["id"])
        if self.catalog:
            self._workflow_changed(0)

    def _workflow_changed(self, index: int) -> None:
        if index < 0 or index >= len(self.catalog):
            return
        self.current_definition = self.catalog[index]
        self.description.setText(str(self.current_definition.get("description", "")))
        self.fixed_settings.setPlainText(
            json.dumps(self.current_definition.get("fixed_settings", {}), indent=2, sort_keys=True)
        )
        self._clear_form()
        for key, schema in (self.current_definition.get("parameters") or {}).items():
            widget = self._parameter_widget(schema)
            self.parameter_inputs[str(key)] = widget
            label = str(schema.get("label", key))
            if schema.get("units"):
                label += f" ({schema['units']})"
            self.parameter_form.addRow(label, widget)
            self._connect_dirty(widget)
        self._invalidate_configuration("Workflow selection changed; configure and save before running.")

    def _clear_form(self) -> None:
        while self.parameter_form.rowCount():
            self.parameter_form.removeRow(0)
        self.parameter_inputs.clear()

    def _parameter_widget(self, schema: dict[str, Any]):
        kind = str(schema.get("type", "float"))
        if kind == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(schema.get("default", False)))
            return widget
        if kind == "int":
            widget = QSpinBox()
            widget.setRange(
                int(schema.get("minimum", -2147483648)),
                int(schema.get("maximum", 2147483647)),
            )
            widget.setSingleStep(int(schema.get("step", 1)))
            widget.setValue(int(schema.get("default", 0)))
            return widget
        widget = QDoubleSpinBox()
        widget.setDecimals(6)
        widget.setRange(
            float(schema.get("minimum", -1.0e12)),
            float(schema.get("maximum", 1.0e12)),
        )
        widget.setSingleStep(float(schema.get("step", 1.0)))
        widget.setValue(float(schema.get("default", 0.0)))
        return widget

    def _connect_dirty(self, widget) -> None:
        if isinstance(widget, QCheckBox):
            widget.toggled.connect(lambda _value: self._invalidate_configuration())
        else:
            widget.valueChanged.connect(lambda _value: self._invalidate_configuration())

    def _invalidate_configuration(self, message: str | None = None) -> None:
        self.configured_fingerprint = None
        self.run_button.setEnabled(False)
        if message:
            self.status.append(f"PENDING: {message}")

    def _values(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for key, widget in self.parameter_inputs.items():
            if isinstance(widget, QCheckBox):
                values[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                values[key] = int(widget.value())
            else:
                values[key] = float(widget.value())
        return values

    def _configure(self) -> None:
        if self.current_definition is None:
            return
        command = WorkflowCommand(
            device_key="workflow",
            command="workflow.configure_selected",
            parameters={
                "workflow_id": self.current_definition["id"],
                "workflow_parameters": self._values(),
            },
        )
        self._dispatch(command, "configure")

    def _run(self) -> None:
        if self.configured_fingerprint is None:
            return
        command = WorkflowCommand(
            device_key="workflow",
            command="workflow.run_selected",
            parameters={
                "fingerprint": self.configured_fingerprint,
                "workflow_id": self.current_definition["id"],
                "workflow_parameters": self._values(),
            },
            safety_approval=self.safety_approval.isChecked(),
        )
        self._dispatch(command, "run")

    def _stop(self) -> None:
        self._dispatch(
            WorkflowCommand(device_key="workflow", command="workflow.stop_selected"),
            "stop",
        )

    def _dispatch(self, command: WorkflowCommand, action: str) -> None:
        self.configure_button.setEnabled(False)
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.selector.setEnabled(False)
        worker = _WorkflowWorker(self.command_handler, command)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_worker)
        self._active_worker = worker
        self._active_thread = thread
        self._active_action = action
        self.status.append(f"RUNNING: {action}")
        thread.start()

    def _finished(self, result: WorkflowResult) -> None:
        self.status.append(f"{result.status.upper()}: {result.message}")
        if self._active_action == "configure" and result.status == "complete":
            self.configured_fingerprint = str(result.data["fingerprint"])
        if self._active_action == "run" and result.status == "complete":
            self._workflow_active = True
        if self._active_action == "stop" and result.status == "complete":
            self._workflow_active = False
        if isinstance(result.data, dict) and result.data.get("scan_rows") and callable(self.scan_data_ready_callback):
            self.scan_data_ready_callback(result.data["scan_rows"])
        self.configure_button.setEnabled(not self._workflow_active)
        self.selector.setEnabled(not self._workflow_active)
        self.stop_button.setEnabled(self._workflow_active)
        self._update_run_enabled()

    def _update_run_enabled(self, *_args) -> None:
        required = bool((self.current_definition or {}).get("safety_approval_required", False))
        approved = self.safety_approval.isChecked() or not required
        self.run_button.setEnabled(
            self._active_thread is None
            and not self._workflow_active
            and self.configured_fingerprint is not None
            and approved
        )

    def _clear_worker(self) -> None:
        self._active_worker = None
        self._active_thread = None
        self._active_action = None
        self.configure_button.setEnabled(not self._workflow_active)
        self.selector.setEnabled(not self._workflow_active)
        self.stop_button.setEnabled(self._workflow_active)
        self._update_run_enabled()

    def command_running(self) -> bool:
        return self._active_thread is not None
