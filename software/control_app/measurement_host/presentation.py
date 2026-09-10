"""Reusable, hardware-free presentation for independently registered measurements.

``GuidedMeasurementPanel`` combines a module's settings QWidget and scientific
adapter with a small preliminary / review / start interaction. The adapter owns
all scientific validation, serialization, readiness, normalization and runners.
No experiment ID or detector-mode dispatch belongs here. Construction invokes
only pure planning methods; device work belongs in explicit worker callbacks.

Adapters must acquire the host coordinator before device access, retain it through
restoration and native saving, and report cleanup/save failures by raising them.
Worker completion means that its Python call returned; it never establishes safe
hardware state. Cancellation is cooperative and must pass through runner cleanup.
The immutable StartSnapshot envelope contains detached copies of scientific state
and a resolved save destination. Callbacks must use these copies, not read mutable
widgets or re-query the application's current save location.

``PlotPanel`` uses an injected PlotAdapter; a steady-state adapter can draw one
ordinary 2-D axes. A kinetic adapter can create its own axes and connect separate
``LinkedSliceControl`` instances. All navigation/image actions stay in the toolbar.
Qt and Matplotlib are optional: pure helpers remain importable without either.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
from pathlib import Path
from threading import Event
from typing import Any, Callable, Protocol, Sequence

from .context import MeasurementContext, OperationSnapshot


@dataclass(frozen=True)
class TimeDisplay:
    """Convert seconds for display only; retain native seconds in saved data."""

    unit: str
    seconds_per_unit: float
    decimals: int = 3

    def value(self, seconds: float) -> float:
        return seconds / self.seconds_per_unit

    def format(self, seconds: float) -> str:
        return f"{self.value(seconds):.{self.decimals}f} {self.unit}"


def choose_time_display(seconds: Sequence[float], *, unit: str | None = None) -> TimeDisplay:
    """Choose ns/us/ms/s/min/h/d and precision from range and measured spacing.

    Modules can explicitly select a unit (``us`` and ``µs`` both work). Choosing
    units never changes sample coordinates, performs interpolation, or claims a
    time resolution. Numeric arrows still step through samples below precision.
    """
    factors = {"ns": 1e-9, "µs": 1e-6, "ms": 1e-3, "s": 1., "min": 60., "h": 3600., "d": 86400.}
    values = sorted(set(float(value) for value in seconds))
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("Time coordinates must be nonempty and finite")
    if unit == "us":
        unit = "µs"
    if unit is None:
        extent = max(abs(value) for value in values)
        unit = "s" if extent == 0 else "ns"
        for name, factor in factors.items():
            if extent >= factor:
                unit = name
    if unit not in factors:
        raise ValueError(f"Unknown time unit: {unit}")
    factor = factors[unit]
    gaps = [(b-a)/factor for a, b in zip(values, values[1:]) if b > a]
    decimals = max(3, min(12, int(math.ceil(-math.log10(min(gaps)))) + 1)) if gaps else 3
    return TimeDisplay(unit, factor, decimals)


@dataclass(frozen=True)
class ScientificSelections:
    """Keep promoted instrument selections separate from sample-derived records."""

    calibration_records: tuple[Any, ...] = ()
    sample_records: tuple[Any, ...] = ()


@dataclass(frozen=True)
class StartSnapshot:
    """Canonical host operation plus detached, module-owned scientific payloads.

    Use operation.output_path for native saving. Its settings/records are deeply
    immutable; plan/preliminary are private copies for scientific code that uses
    native objects such as NumPy arrays. They are never shared with another tab.
    """

    operation: OperationSnapshot
    kind: str
    plan: Any
    preliminary: Any

    @property
    def operation_id(self) -> str:
        return self.operation.run_id

    @property
    def settings(self):
        return self.operation.settings

    @property
    def save_root(self) -> Path:
        return self.operation.save_root


@dataclass(frozen=True)
class WorkerOutcome:
    """Call outcome only. ``state`` is completed, cancelled, or failed."""

    state: str
    result: Any = None
    error: str = ""


class ScientificAdapter(Protocol):
    """Exact callback contract for GuidedMeasurementPanel; all methods required.

    Planning and presentation callbacks run on the UI thread and must be pure.
    The two run methods and file I/O callbacks run in a background worker. Run
    callbacks may use worker.message.emit(str), worker.progress.emit(done,total),
    and worker.check_cancelled(). ``request_abort`` must only request cancellation
    of this adapter's active operation and must not block on hardware cleanup.
    ``selected_records`` keeps instrument calibration/sample records distinct.
    ``hardware_required`` is pure and declares real versus simulated execution;
    ownership is acquired by the panel on the UI thread before worker dispatch.
    Hardware run callbacks receive an already scoped ownership token and MUST
    release it through their context only after restoration/preservation outcomes
    are known. This panel deliberately never infers safety from worker completion.
    A module must use distinct adapter/runner instances for its single/dual tabs.
    """

    def read_settings(self) -> Any: ...
    def apply_settings(self, settings: Any) -> None: ...
    def make_plan(self, settings: Any) -> Any: ...
    def validate_plan(self, plan: Any) -> Sequence[str]: ...
    def summarize_plan(self, plan: Any) -> str: ...
    def selected_records(self) -> ScientificSelections: ...
    def hardware_required(self, kind: str, settings: Any) -> bool: ...
    def run_preliminary(self, snapshot: StartSnapshot, worker: OperationWorker) -> Any: ...
    def summarize_preliminary(self, result: Any) -> str: ...
    def validate_review(self, preliminary: Any, plan: Any) -> Sequence[str]: ...
    def run_measurement(self, snapshot: StartSnapshot, worker: OperationWorker) -> Any: ...
    def request_abort(self, reason: str) -> None: ...
    def save_plan(self, path: Path, settings: Any, plan: Any) -> None: ...
    def load_plan(self, path: Path) -> Any: ...
    def load_run(self, path: Path) -> Any: ...
    def export_run(self, path: Path, result: Any) -> None: ...
    def new_run(self) -> None: ...


class PlotAdapter(Protocol):
    """A renderer owns axes, scientific labels, units, gaps and plot geometry."""

    def draw(self, figure: Any, result: Any) -> None: ...


try:
    from PySide6.QtCore import Qt, QThread, Signal
    from PySide6.QtWidgets import (
        QCheckBox, QDoubleSpinBox, QFileDialog, QHBoxLayout, QLabel,
        QProgressBar, QPushButton, QScrollArea, QSlider, QSplitter,
        QVBoxLayout, QWidget,
    )
except ImportError:  # Optional UI dependencies must not block module discovery.
    QWidget = None


if QWidget is not None:
    class OperationWorker(QThread):
        """One nonblocking call with a cancellation event and truthful outcome.

        Never terminate() a measurement worker. ``InterruptedError`` denotes
        intentional cancellation; cleanup/save exceptions are ordinary failures.
        Signals are notifications, not prerequisites for the operation's cleanup.
        """

        message = Signal(str)
        progress = Signal(int, int)
        result = Signal(object)
        stopped = Signal(str)
        failed = Signal(str)

        def __init__(self, operation: Callable[[OperationWorker], Any], parent=None):
            super().__init__(parent)
            self.operation = operation
            self.cancel_event = Event()
            self.cancel_reason = "Cancellation requested"
            self.outcome: WorkerOutcome | None = None
            self.notification_errors: list[str] = []

        def request_abort(self, reason: str = "Cancellation requested") -> None:
            self.cancel_reason = reason
            self.cancel_event.set()

        def check_cancelled(self) -> None:
            if self.cancel_event.is_set():
                raise InterruptedError(self.cancel_reason)

        def notify(self, callback: Callable[..., None], *args: Any) -> None:
            """Optional callback delivery must not skip cleanup or native saving."""
            try:
                callback(*args)
            except Exception as exc:
                self.notification_errors.append(f"{type(exc).__name__}: {exc}")

        def run(self) -> None:
            try:
                # Always enter the operation even after an early abort: it may
                # already own a host token and must execute its cleanup/finally.
                result = self.operation(self)
                self.outcome = WorkerOutcome("completed", result)
                self.result.emit(result)
            except InterruptedError as exc:
                self.outcome = WorkerOutcome("cancelled", error=str(exc))
                self.stopped.emit(str(exc))
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                self.outcome = WorkerOutcome("failed", error=error)
                self.failed.emit(error)


    class _CoordinateSpinBox(QDoubleSpinBox):
        stepped = Signal(int)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.coordinate_edited = False
            self._enabled_steps = self.StepEnabledFlag.StepNone
            self.setKeyboardTracking(False)
            self.lineEdit().textEdited.connect(self._edited)

        def _edited(self, _text):
            self.coordinate_edited = True
            self.update()

        def stepBy(self, steps):
            self.interpretText()
            self.stepped.emit(steps)

        def stepEnabled(self):
            if self.coordinate_edited:
                return self.StepEnabledFlag.StepUpEnabled | self.StepEnabledFlag.StepDownEnabled
            return self._enabled_steps


    class LinkedSliceControl(QWidget):
        """Measured index + numeric coordinate; unsorted/nonuniform axes work.

        ``index_changed`` always reports the index in the original input sequence.
        Held arrows traverse coordinates in ascending order, not rounded values.
        Typed coordinates select the nearest measured sample without interpolation.
        """

        index_changed = Signal(int)

        def __init__(self, coordinates=(), *, label="Slice", unit="", decimals=3, parent=None):
            super().__init__(parent)
            self.coordinates: tuple[float, ...] = ()
            self.order: list[int] = []
            self.label = QLabel(label)
            self.input = _CoordinateSpinBox()
            self.input.setDecimals(decimals)
            self.input.setSuffix(f" {unit}" if unit else "")
            self.input.setToolTip("Hold an arrow to step through measured slices, or type a coordinate and press Enter to select the nearest slice.")
            self.slider = QSlider(Qt.Orientation.Horizontal)
            row = QHBoxLayout(self)
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(self.label)
            row.addWidget(self.input)
            row.addWidget(self.slider, 1)
            self.slider.valueChanged.connect(self._sync)
            self.input.stepped.connect(self._step)
            self.input.valueChanged.connect(self._enter)
            self.input.editingFinished.connect(self._enter_if_edited)
            self.set_coordinates(coordinates)

        @property
        def index(self):
            return self.slider.value()

        def set_coordinates(self, coordinates):
            values = tuple(float(value) for value in coordinates)
            if not all(math.isfinite(value) for value in values):
                raise ValueError("Slice coordinates must be finite")
            self.coordinates = values
            self.order = sorted(range(len(values)), key=values.__getitem__)
            self.setEnabled(bool(values))
            self.slider.blockSignals(True)
            self.slider.setRange(0, max(0, len(values)-1))
            self.slider.setValue(len(values)//2)
            self.slider.blockSignals(False)
            self.input.blockSignals(True)
            self.input.setRange(min(values) if values else 0., max(values) if values else 0.)
            self.input.blockSignals(False)
            if values:
                self._sync(self.index)

        def set_index(self, index: int):
            if not 0 <= index < len(self.coordinates):
                raise IndexError("Slice index is outside the measured coordinates")
            self.slider.setValue(index)

        def _sync(self, index):
            if not self.coordinates:
                return
            self.input.blockSignals(True)
            self.input.setValue(self.coordinates[index])
            self.input.coordinate_edited = False
            position = self.order.index(index)
            flags = self.input.StepEnabledFlag.StepNone
            if position:
                flags |= self.input.StepEnabledFlag.StepDownEnabled
            if position < len(self.order)-1:
                flags |= self.input.StepEnabledFlag.StepUpEnabled
            self.input._enabled_steps = flags
            self.input.blockSignals(False)
            self.input.update()
            self.index_changed.emit(index)

        def _enter(self, *_):
            if self.coordinates:
                index = min(range(len(self.coordinates)), key=lambda i: abs(self.coordinates[i]-self.input.value()))
                self.slider.blockSignals(True)
                self.slider.setValue(index)
                self.slider.blockSignals(False)
                self._sync(index)

        def _enter_if_edited(self):
            if self.input.coordinate_edited:
                self._enter()

        def _step(self, steps):
            if not self.coordinates:
                return
            self._enter_if_edited()
            position = max(0, min(len(self.order)-1, self.order.index(self.index)+steps))
            self.set_index(self.order[position])


    class PlotPanel(QWidget):
        """Toolbar-only navigation and image export with injected scientific drawing."""

        error = Signal(str)

        def __init__(self, adapter: PlotAdapter, parent=None):
            super().__init__(parent)
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
            from matplotlib.figure import Figure
            self.adapter, self.result = adapter, None
            # The toolbar subplot editor requires an unconstrained layout engine.
            self.figure = Figure(figsize=(8, 5), layout="none")
            self.canvas = FigureCanvasQTAgg(self.figure)
            self.canvas.setMinimumHeight(300)
            self.toolbar = NavigationToolbar2QT(self.canvas, self)
            self.select_action = self.toolbar.addAction("Mouse selection")
            self.toolbar.insertAction(self.toolbar._actions["pan"], self.select_action)
            self.select_action.triggered.connect(self.mouse_selection)
            self.toolbar._actions["home"].triggered.disconnect()
            self.toolbar._actions["home"].triggered.connect(self.reset_view)
            self.toolbar._actions["save_figure"].triggered.disconnect()
            self.toolbar._actions["save_figure"].triggered.connect(self._choose_image)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.toolbar)
            layout.addWidget(self.canvas, 1)

        def mouse_selection(self):
            if self.toolbar.mode == "pan/zoom":
                self.toolbar.pan()
            elif self.toolbar.mode == "zoom rect":
                self.toolbar.zoom()

        def set_result(self, result):
            self.result = result
            self.reset_view()

        def reset_view(self):
            self.mouse_selection()
            self.figure.clear()
            if self.result is not None:
                self.adapter.draw(self.figure, self.result)
            self.toolbar.update()
            self.canvas.draw_idle()

        def clear_result(self):
            self.result = None
            self.reset_view()

        def save_image(self, path: Path):
            path = Path(path)
            if path.exists():
                raise FileExistsError("Choose a new filename to preserve existing images")
            self.figure.savefig(path, dpi=180)

        def _choose_image(self):
            path, _ = QFileDialog.getSaveFileName(self, "Save plot image", "measurement.png", "PNG (*.png);;SVG (*.svg);;PDF (*.pdf)")
            if path:
                try:
                    self.save_image(Path(path))
                except Exception as exc:
                    self.error.emit(f"{type(exc).__name__}: {exc}")


    class GuidedMeasurementPanel(QWidget):
        """Reusable settings/summary and preliminary/review/start presentation.

        Connect each settings control's changed signal to ``refresh_plan``. Add
        plots to ``result_layout`` and connect ``run_loaded`` / ``result_ready``.
        Every adapter gets a distinct panel. Native I/O is background work; file
        dialogs are only path selection. Module lifecycle handles can delegate
        command_running/request_abort and expose the panel's busy_changed signal.
        """

        busy_changed = Signal(bool)
        result_ready = Signal(object)
        run_loaded = Signal(object, str)
        outcome_ready = Signal(object)
        new_run_requested = Signal()

        def __init__(self, settings_widget: QWidget, adapter: ScientificAdapter,
                     context: MeasurementContext, parent=None):
            super().__init__(parent)
            self.adapter, self.context = adapter, context
            self.save_root_provider = context.save_root
            self.settings_widget = settings_widget
            self.plan = self.preliminary = self.result = self.worker = None
            self.snapshot: StartSnapshot | None = None
            self._busy = False
            self._active_kind = None
            self._host_plan = None
            self.summary = QLabel()
            self.validation = QLabel()
            self.status = QLabel("Review settings, then acquire a preliminary measurement.")
            self.review_summary = QLabel()
            for label in (self.summary, self.validation, self.status, self.review_summary):
                label.setWordWrap(True)
                label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.save_plan_button = QPushButton("Save plan…")
            self.load_plan_button = QPushButton("Load plan…")
            self.load_run_button = QPushButton("Load native run…")
            self.export_button = QPushButton("Export data…")
            self.preliminary_button = QPushButton("Acquire preliminary")
            self.review = QCheckBox("I have reviewed the preliminary measurement")
            self.start_button = QPushButton("Start measurement")
            self.abort_button = QPushButton("Stop")
            self.new_run_button = QPushButton("New run")
            self.progress = QProgressBar()
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            layout = QVBoxLayout(self)
            splitter = QSplitter(Qt.Orientation.Horizontal)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(settings_widget)
            splitter.addWidget(scroll)
            summary_box = QWidget()
            summaries = QVBoxLayout(summary_box)
            summaries.addWidget(self.summary)
            summaries.addWidget(self.validation)
            summaries.addStretch()
            splitter.addWidget(summary_box)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 1)
            layout.addWidget(splitter)
            files = QHBoxLayout()
            for button in (self.save_plan_button, self.load_plan_button, self.load_run_button, self.export_button):
                files.addWidget(button)
            layout.addLayout(files)
            layout.addWidget(self.review_summary)
            layout.addWidget(self.review)
            actions = QHBoxLayout()
            for button in (self.preliminary_button, self.start_button, self.abort_button, self.new_run_button):
                actions.addWidget(button)
            layout.addLayout(actions)
            layout.addWidget(self.status)
            layout.addWidget(self.progress)
            self.result_layout = QVBoxLayout()
            layout.addLayout(self.result_layout, 1)
            self.preliminary_button.clicked.connect(lambda: self._user_action(lambda: self.begin("preliminary")))
            self.start_button.clicked.connect(lambda: self._user_action(lambda: self.begin("measurement")))
            self.abort_button.clicked.connect(lambda: self.request_abort("Stopped by user"))
            self.new_run_button.clicked.connect(self.new_run)
            self.review.toggled.connect(self._update_controls)
            self.save_plan_button.clicked.connect(self._choose_save_plan)
            self.load_plan_button.clicked.connect(self._choose_load_plan)
            self.load_run_button.clicked.connect(self._choose_load_run)
            self.export_button.clicked.connect(self._choose_export)
            self.refresh_plan()

        def command_running(self):
            return self._busy

        def close_blockers(self) -> tuple[str, ...]:
            """Active work blocks close through native saving and restoration."""
            return ("Wait for the active operation, cleanup, and data preservation.",) if self._busy else ()

        def _user_action(self, callback):
            try:
                callback()
            except Exception as exc:
                self.status.setText(f"{type(exc).__name__}: {exc}")

        def refresh_plan(self, *_):
            if self._busy:
                return
            self.review.setChecked(False)
            self.preliminary = None
            self.review_summary.clear()
            try:
                plan = self.adapter.make_plan(deepcopy(self.adapter.read_settings()))
                errors = tuple(self.adapter.validate_plan(plan))
                self.summary.setText(self.adapter.summarize_plan(plan))
                self.plan = None if errors else plan
                self._host_plan = self.context.new_plan(self.adapter.read_settings()) if self.plan is not None else None
                self.validation.setText("\n".join(errors))
            except Exception as exc:
                self.plan = None
                self._host_plan = None
                self.summary.clear()
                self.validation.setText(str(exc))
            self._update_controls()

        def _update_controls(self, *_):
            idle, valid = not self._busy, self.plan is not None
            self.settings_widget.setEnabled(idle)
            self.preliminary_button.setEnabled(idle and valid)
            self.review.setEnabled(idle and self.preliminary is not None)
            self.start_button.setEnabled(idle and valid and self.preliminary is not None and self.review.isChecked())
            self.abort_button.setEnabled(self._busy)
            self.new_run_button.setEnabled(idle)
            self.save_plan_button.setEnabled(idle and valid)
            self.load_plan_button.setEnabled(idle)
            self.load_run_button.setEnabled(idle)
            self.export_button.setEnabled(idle and self.result is not None)

        def begin(self, kind: str):
            if self._busy:
                raise RuntimeError("This measurement already has an operation running")
            if kind not in ("preliminary", "measurement") or self.plan is None:
                raise ValueError("A valid plan and operation kind are required")
            if kind == "measurement":
                if self.preliminary is None or not self.review.isChecked():
                    raise ValueError("Review a preliminary measurement before starting")
                errors = tuple(self.adapter.validate_review(self.preliminary, self.plan))
                if errors:
                    self.validation.setText("\n".join(errors))
                    self.review.setChecked(False)
                    return
            # Finish copying fallible scientific objects before acquiring a token.
            plan, preliminary = deepcopy(self.plan), deepcopy(self.preliminary)
            selected = self.adapter.selected_records()
            host_operation = self.context.begin_operation(
                plan=self._host_plan, calibration_records=selected.calibration_records,
                sample_records=selected.sample_records,
                hardware=self.adapter.hardware_required(kind, self._host_plan.settings),
                purpose=kind, cancel=self.request_abort,
            )
            self.snapshot = StartSnapshot(host_operation, kind, plan, preliminary)
            snapshot = self.snapshot
            operation = self.adapter.run_preliminary if kind == "preliminary" else self.adapter.run_measurement
            if kind == "preliminary":
                self.preliminary = None
                self.review.setChecked(False)
            def run(worker):
                if snapshot.operation.hardware:
                    with self.context.hardware_scope(snapshot.operation):
                        return operation(snapshot, worker)
                return operation(snapshot, worker)
            try:
                self._launch(run, kind)
            except Exception:
                # Dispatch failed before any hardware callback was entered.
                if snapshot.operation.hardware and not (self.worker and self.worker.isRunning()):
                    self.context.ownership.release(snapshot.operation.ownership, safe_verified=True,
                                                   preservation_verified=True, detail="Worker dispatch failed before hardware access")
                self._busy = False
                self._active_kind = None
                self._update_controls()
                self.busy_changed.emit(False)
                raise

        def _launch(self, operation, kind, path=None):
            if self._busy:
                raise RuntimeError("An operation is already running")
            self._busy = True
            self._active_kind = kind
            self.worker = OperationWorker(operation, self)
            worker = self.worker
            worker.message.connect(lambda message: self.status.setText(message) if self.worker is worker else None)
            worker.progress.connect(lambda done, total: self._progress(done, total) if self.worker is worker else None)
            worker.finished.connect(lambda: self._finished(worker, kind, path))
            self.progress.setRange(0, 0)
            self.status.setText(f"Running {kind.replace('_', ' ')}…")
            self._update_controls()
            self.busy_changed.emit(True)
            self.worker.start()

        def _progress(self, completed, total):
            self.progress.setRange(0, max(0, total))
            self.progress.setValue(max(0, min(completed, total)))

        def _finished(self, worker, kind, path):
            if self.worker is not worker:
                return
            outcome = worker.outcome
            self.progress.setRange(0, 100)
            self.progress.setValue(100 if outcome.state == "completed" else 0)
            self.status.setText(outcome.error or f"Completed {kind.replace('_', ' ')}.")
            try:
                if outcome.state == "completed":
                    if kind == "preliminary":
                        self.preliminary = outcome.result
                        self.review_summary.setText(self.adapter.summarize_preliminary(outcome.result))
                    elif kind == "measurement":
                        self.result = outcome.result
                        self.result_ready.emit(outcome.result)
                    elif kind == "load_plan":
                        self.adapter.apply_settings(outcome.result)
                        self._busy = False
                        self.refresh_plan()
                        self._busy = True
                    elif kind == "load_run":
                        self.result = outcome.result
                        self.run_loaded.emit(outcome.result, str(path))
                if worker.notification_errors:
                    self.status.setText(self.status.text() + " Notification errors: " + "; ".join(worker.notification_errors))
            except Exception as exc:
                self.status.setText(f"Presentation failed after {kind}: {type(exc).__name__}: {exc}")
            finally:
                self.worker = None
                self._busy = False
                self._active_kind = None
                worker.deleteLater()
                self._update_controls()
                self.busy_changed.emit(False)
                self.outcome_ready.emit(outcome)

        def request_abort(self, reason: str):
            if self.worker is not None and self._busy:
                self.worker.request_abort(reason)
                try:
                    if self._active_kind in ("preliminary", "measurement"):
                        self.adapter.request_abort(reason)
                    self.status.setText(f"{reason}; waiting for cleanup and data preservation.")
                except Exception as exc:
                    self.status.setText(f"Cancellation request failed: {type(exc).__name__}: {exc}")

        def new_run(self):
            if self._busy:
                raise RuntimeError("Wait for the current operation and cleanup before New run")
            self.adapter.new_run()
            self.preliminary = self.result = self.snapshot = None
            self.progress.setValue(0)
            self.refresh_plan()
            self.status.setText("Review settings, then acquire a preliminary measurement.")
            self.new_run_requested.emit()

        def save_plan(self, path):
            if self.plan is None:
                raise ValueError("A valid plan is required")
            settings, plan = deepcopy(self.adapter.read_settings()), deepcopy(self.plan)
            self._launch(lambda _worker: self.adapter.save_plan(Path(path), settings, plan), "save_plan", path)

        def load_plan(self, path):
            self._launch(lambda _worker: self.adapter.load_plan(Path(path)), "load_plan", path)

        def load_run(self, path):
            self._launch(lambda _worker: self.adapter.load_run(Path(path)), "load_run", path)

        def export_run(self, path):
            if self.result is None:
                raise ValueError("Load or acquire a native result before export")
            result = deepcopy(self.result)
            self._launch(lambda _worker: self.adapter.export_run(Path(path), result), "export_run", path)

        def _choose_save_plan(self):
            path, _ = QFileDialog.getSaveFileName(self, "Save plan", str(self.save_root_provider()), "Plan files (*)")
            if path:
                self.save_plan(path)

        def _choose_load_plan(self):
            path, _ = QFileDialog.getOpenFileName(self, "Load plan", str(self.save_root_provider()), "Plan files (*)")
            if path:
                self.load_plan(path)

        def _choose_load_run(self):
            path = QFileDialog.getExistingDirectory(self, "Load native run", str(self.save_root_provider()))
            if path:
                self.load_run(path)

        def _choose_export(self):
            path, _ = QFileDialog.getSaveFileName(self, "Export data", str(self.save_root_provider()), "Data files (*)")
            if path:
                self.export_run(path)
