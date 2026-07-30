"""Schema-driven Qt experiment builder.

The widget deliberately depends on the generic experiment layer only.  It does
not import device services or workflow command handlers, so rendering, editing,
validation, and plan compilation cannot operate hardware.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import yaml

from control_app.config_loader import REPO_ROOT
from control_app.experiments.builder import ExperimentBuilder
from control_app.experiments.engine import ExperimentEngine
from control_app.experiments.models import ExperimentDefinition, FieldDefinition

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSpinBox,
        QSplitter,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - import-safe for backend/test environments
    PYSIDE6_AVAILABLE = False
    QWidget = object


class ExperimentBuilderWidget(QWidget):
    """Visible create-to-export UI for typed experiment definitions."""

    def __init__(
        self,
        *,
        builder: ExperimentBuilder | None = None,
        engine: ExperimentEngine | None = None,
        parent=None,
    ) -> None:
        if not PYSIDE6_AVAILABLE:
            raise RuntimeError("PySide6 is required to instantiate ExperimentBuilderWidget")
        super().__init__(parent)
        self.builder = builder or ExperimentBuilder()
        self.engine = engine
        self.definition_path: Path | None = None
        self.plan_path: Path | None = None
        self.inputs: dict[str, QWidget] = {}
        self._running = False

        self.catalog = QComboBox()
        self.new_button = QPushButton("New from Template")
        self.load_button = QPushButton("Load…")
        self.reload_button = QPushButton("Reload")
        self.save_button = QPushButton("Save…")
        self.validate_button = QPushButton("Validate")
        self.configure_button = QPushButton("Configure && Save Plan…")
        self.run_button = QPushButton("Run Configured Plan")
        self.stop_button = QPushButton("Stop / Abort to Safe")
        self.stop_button.setProperty("danger", True)
        self.process_button = QPushButton("Process Raw JSON…")
        self.export_button = QPushButton("Export Result…")
        self.safety_checks = QTextEdit()
        self.safety_checks.setPlaceholderText("One satisfied safety prerequisite per line")
        self.safety_checks.setMaximumHeight(85)
        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMaximumHeight(130)
        self.document = QTextEdit()
        self.document.setPlaceholderText("Load or create an experiment definition to inspect/edit its YAML.")
        self.form_group = QGroupBox("Typed Experiment Fields")
        self.form = QFormLayout(self.form_group)
        self.status = QTextEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(125)
        self._build_ui()
        self._populate_catalog()
        if self.catalog.count():
            self.load_definition(self.catalog.itemData(0))
        self._set_action_state()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        intro = QLabel(
            "Build experiments from typed definitions and allow-listed device capabilities. "
            "Loading, editing, validation, and configuration do not access hardware."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)
        top = QHBoxLayout()
        top.addWidget(QLabel("Definition"))
        top.addWidget(self.catalog, 1)
        for button in (self.new_button, self.load_button, self.reload_button, self.save_button):
            top.addWidget(button)
        root.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setWidget(self.form_group)
        splitter.addWidget(form_scroll)
        document_group = QGroupBox("Definition YAML (advanced settings)")
        document_layout = QVBoxLayout(document_group)
        document_layout.addWidget(self.document)
        splitter.addWidget(document_group)
        splitter.setSizes([520, 520])
        root.addWidget(splitter, 1)

        root.addWidget(QLabel("Definition summary"))
        root.addWidget(self.summary)
        root.addWidget(QLabel("Satisfied safety prerequisites"))
        root.addWidget(self.safety_checks)
        actions = QHBoxLayout()
        for button in (
            self.validate_button, self.configure_button, self.run_button,
            self.stop_button, self.process_button, self.export_button,
        ):
            actions.addWidget(button)
        root.addLayout(actions)
        root.addWidget(self.status)

        self.new_button.clicked.connect(self._new_from_template)
        self.load_button.clicked.connect(self._load_dialog)
        self.reload_button.clicked.connect(self._reload)
        self.save_button.clicked.connect(self._save_dialog)
        self.validate_button.clicked.connect(self._validate)
        self.configure_button.clicked.connect(self._configure)
        self.run_button.clicked.connect(self._run)
        self.stop_button.clicked.connect(self._stop)
        self.process_button.clicked.connect(self._process)
        self.export_button.clicked.connect(self._export)
        self.document.textChanged.connect(self._document_changed)

    def _populate_catalog(self) -> None:
        root = REPO_ROOT / "recipes" / "experiments"
        self.catalog.clear()
        if root.exists():
            for path in sorted((*root.glob("*.yaml"), *root.glob("*.yml"), *root.glob("*.json"))):
                self.catalog.addItem(path.stem.replace("_", " ").title(), str(path))

    def _new_from_template(self) -> None:
        path = self.catalog.currentData()
        if not path:
            self._show_error("No experiment templates are available.")
            return
        try:
            source = ExperimentDefinition.load(path)
            document = source.to_dict()
            document["experiment_id"] = f"{source.experiment_id}_copy"
            document["name"] = f"{source.name} (copy)"
            self.definition_path = None
            self._display_definition(self.builder.create(document))
            self._append("CREATED: Unsaved definition copied from the selected template.")
        except Exception as exc:  # noqa: BLE001 - user-authored document feedback
            self._show_error(str(exc))

    def _load_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Experiment Definition", str(REPO_ROOT / "recipes" / "experiments"),
            "Experiment definitions (*.yaml *.yml *.json)",
        )
        if path:
            self.load_definition(path)

    def load_definition(self, path: str | Path) -> None:
        """Load a definition; public to support app automation and UI tests."""
        try:
            self.definition_path = Path(path)
            self._display_definition(self.builder.reload(path))
            self._append(f"LOADED: {self.definition_path}")
        except Exception as exc:  # noqa: BLE001
            self._show_error(str(exc))

    def _reload(self) -> None:
        if self.definition_path is None:
            self._show_error("This definition has not been saved yet.")
            return
        self.load_definition(self.definition_path)

    def _save_dialog(self) -> None:
        if not self._sync_definition():
            return
        suggested = str(self.definition_path or (REPO_ROOT / "recipes" / "experiments" / "experiment.yaml"))
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Experiment Definition", suggested,
            "YAML (*.yaml *.yml);;JSON (*.json)",
        )
        if not path:
            return
        try:
            self.definition_path = self.builder.save(path)
            self._populate_catalog()
            self._append(f"SAVED: {self.definition_path}")
        except Exception as exc:  # noqa: BLE001
            self._show_error(str(exc))

    def _display_definition(self, definition: ExperimentDefinition) -> None:
        self.document.blockSignals(True)
        self.document.setPlainText(yaml.safe_dump(definition.to_dict(), sort_keys=False))
        self.document.blockSignals(False)
        self._render_fields(definition)
        self._update_summary(definition)
        self.safety_checks.setPlainText("\n".join(definition.safety_prerequisites))
        self.plan_path = None
        self.builder.plan = None
        self._set_action_state()

    def _render_fields(self, definition: ExperimentDefinition) -> None:
        while self.form.rowCount():
            self.form.removeRow(0)
        self.inputs.clear()
        for field in definition.fields:
            value = definition.values.get(field.key, field.default)
            widget = self._field_widget(field, value)
            widget.setToolTip(field.help_text)
            self.inputs[field.key] = widget
            label = field.label + (f" ({field.units})" if field.units else "")
            self.form.addRow(label, widget)
            self._connect_field(widget)
        self._apply_conditions()

    def _field_widget(self, field: FieldDefinition, value: Any) -> QWidget:
        if field.kind == "boolean":
            widget = QCheckBox()
            widget.setChecked(bool(value))
        elif field.kind == "integer":
            widget = QSpinBox()
            widget.setRange(int(field.minimum if field.minimum is not None else -2147483648), int(field.maximum if field.maximum is not None else 2147483647))
            widget.setValue(int(value or 0))
        elif field.kind == "float":
            widget = QDoubleSpinBox()
            widget.setDecimals(8)
            widget.setRange(float(field.minimum if field.minimum is not None else -1e15), float(field.maximum if field.maximum is not None else 1e15))
            widget.setValue(float(value or 0.0))
        elif field.kind == "choice":
            widget = QComboBox()
            for choice in field.choices:
                widget.addItem(str(choice), choice)
            index = widget.findData(value)
            widget.setCurrentIndex(max(0, index))
        elif field.kind == "list":
            widget = QLineEdit(json.dumps(value if value is not None else []))
            widget.setPlaceholderText("JSON list, for example [1, 2, 3]")
        else:
            widget = QLineEdit(str(value or ""))
        widget.setEnabled(field.user_adjustable)
        return widget

    def _connect_field(self, widget: QWidget) -> None:
        signal = (
            widget.toggled if isinstance(widget, QCheckBox) else
            widget.currentIndexChanged if isinstance(widget, QComboBox) else
            widget.valueChanged if isinstance(widget, (QSpinBox, QDoubleSpinBox)) else
            widget.textChanged
        )
        signal.connect(self._field_changed)

    def _field_changed(self, *_args) -> None:
        self.plan_path = None
        self.builder.plan = None
        self._apply_conditions()
        self._set_action_state()

    def _apply_conditions(self) -> None:
        definition = self.builder.definition
        if definition is None:
            return
        values = self._field_values(show_errors=False)
        for field in definition.fields:
            widget = self.inputs[field.key]
            visible = field.visible_when is None or values.get(field.visible_when.field) == field.visible_when.equals
            enabled = field.user_adjustable and (field.enabled_when is None or values.get(field.enabled_when.field) == field.enabled_when.equals)
            label = self.form.labelForField(widget)
            widget.setVisible(visible)
            if label is not None:
                label.setVisible(visible)
            widget.setEnabled(enabled)

    def _document_changed(self) -> None:
        self.plan_path = None
        self.builder.plan = None
        self._set_action_state()

    def _sync_definition(self) -> bool:
        try:
            document = yaml.safe_load(self.document.toPlainText())
            if not isinstance(document, dict):
                raise ValueError("Definition YAML must contain a mapping.")
            document = deepcopy(document)
            document["values"] = self._field_values(show_errors=True)
            definition = self.builder.create(document)
            self._update_summary(definition)
            return True
        except Exception as exc:  # noqa: BLE001
            self._show_error(str(exc))
            return False

    def _field_values(self, *, show_errors: bool) -> dict[str, Any]:
        values: dict[str, Any] = {}
        definition = self.builder.definition
        if definition is None:
            return values
        for field in definition.fields:
            widget = self.inputs.get(field.key)
            if widget is None:
                continue
            try:
                if isinstance(widget, QCheckBox):
                    value = widget.isChecked()
                elif isinstance(widget, QComboBox):
                    value = widget.currentData()
                elif isinstance(widget, QSpinBox):
                    value = int(widget.value())
                elif isinstance(widget, QDoubleSpinBox):
                    value = float(widget.value())
                elif field.kind == "list":
                    value = json.loads(widget.text())
                    if not isinstance(value, list):
                        raise ValueError("must be a JSON list")
                else:
                    value = widget.text()
                values[field.key] = value
            except Exception as exc:
                if show_errors:
                    raise ValueError(f"{field.label}: {exc}") from exc
        return values

    def _validate(self) -> None:
        if not self._sync_definition():
            return
        errors = self.builder.validate()
        if errors:
            self._append("INVALID:\n" + "\n".join(f"- {item.path}: {item.message}" for item in errors))
        else:
            self._append("VALID: Definition satisfies schema, capability, wiring, and safety constraints.")

    def _configure(self) -> None:
        if not self._sync_definition():
            return
        suggested = REPO_ROOT / "runs" / "configured_experiments" / f"{self.builder.definition.experiment_id}_plan.json"
        path, _ = QFileDialog.getSaveFileName(self, "Save Immutable Execution Plan", str(suggested), "JSON (*.json)")
        if not path:
            return
        try:
            plan = self.builder.configure(path)
            self.plan_path = Path(path)
            self._append(f"CONFIGURED: {self.plan_path}")
            self._set_action_state()
        except Exception as exc:  # noqa: BLE001
            self._show_error(str(exc))

    def _run(self) -> None:
        if self.engine is None:
            self._show_error(
                "No capability engine is attached. The plan is valid and saved, but hardware execution "
                "is intentionally unavailable until device service adapters are registered."
            )
            return
        try:
            self._running = True
            self._set_action_state()
            prerequisites = {line.strip() for line in self.safety_checks.toPlainText().splitlines() if line.strip()}
            result = self.builder.run(self.engine, satisfied_prerequisites=prerequisites)
            self._append(f"{result.status.upper()}: {result.error or 'Execution finished.'}")
        except Exception as exc:  # noqa: BLE001
            self._show_error(str(exc))
        finally:
            self._running = False
            self._set_action_state()

    def _stop(self) -> None:
        if self.engine is None or self.builder.plan is None:
            return
        result = self.builder.abort_to_safe(self.engine)
        self._running = False
        self._append(f"{result.status.upper()}: Abort-to-Safe actions sent.")
        self._set_action_state()

    def _process(self) -> None:
        if self.builder.definition is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select Raw JSON", str(REPO_ROOT / "runs"), "JSON (*.json)")
        if not path:
            return
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Raw JSON must contain an object.")
            self.builder.process(raw)
            self._append(f"PROCESSED: {path}")
            self._set_action_state()
        except Exception as exc:  # noqa: BLE001
            self._show_error(str(exc))

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Standard Result", str(REPO_ROOT / "runs" / "result.json"), "JSON (*.json);;CSV (*.csv)")
        if not path:
            return
        try:
            target = self.builder.export(path)
            self._append(f"EXPORTED: {target}")
        except Exception as exc:  # noqa: BLE001
            self._show_error(str(exc))

    def _update_summary(self, definition: ExperimentDefinition) -> None:
        devices = ", ".join(definition.required_devices)
        processing = definition.processing.get("method", "not set")
        self.summary.setPlainText(
            f"{definition.name}\nType: {definition.experiment_type}\nDevices: {devices}\n"
            f"Processing: {processing}\nStop: {', '.join(definition.stop.actions)}\n"
            f"Abort-to-Safe: {', '.join(definition.abort_to_safe.actions)}"
        )

    def _set_action_state(self) -> None:
        loaded = self.builder.definition is not None
        configured = self.builder.plan is not None
        self.reload_button.setEnabled(self.definition_path is not None)
        for button in (self.save_button, self.validate_button, self.configure_button, self.process_button):
            button.setEnabled(loaded and not self._running)
        self.run_button.setEnabled(configured and not self._running)
        self.stop_button.setEnabled(configured and self.engine is not None)
        self.export_button.setEnabled(self.builder.result is not None)

    def command_running(self) -> bool:
        return self._running

    def _append(self, message: str) -> None:
        self.status.append(message)

    def _show_error(self, message: str) -> None:
        self._append(f"ERROR: {message}")
        QMessageBox.warning(self, "Experiment Builder", message)
