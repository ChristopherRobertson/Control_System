"""Reusable, hardware-free presentation for independently registered measurements.

``CompactMeasurementPanel`` provides the shared Phase Scan-style presentation
for new measurement pages, with data-based readiness and no review control.
``GuidedMeasurementPanel`` retains compatibility with the earlier presentation.
It combines a module's settings QWidget and scientific
adapter with a small preliminary / review / start interaction. The adapter owns
all scientific validation, serialization, readiness, normalization and runners.
No experiment ID or detector-mode dispatch belongs here. Construction invokes
only pure planning methods; device work belongs in explicit worker callbacks.

The panel acquires the host coordinator before dispatching declared hardware
operations. Adapters retain ownership through restoration and native saving,
release it with the verified outcomes, and report cleanup/save failures by raising.
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


class CompactScientificAdapter(Protocol):
    """Scientific boundary for CompactMeasurementPanel; no manual review state.

    All planning/validation callbacks are pure. ``validate_preliminary`` receives
    the retained preliminary result (possibly None) and current plan. It returns
    actual incompatibilities or missing data; an experiment without a preliminary
    requirement returns (). The host adds no promotion or procedural conditions.

    ``summarize_plan`` supplies concise (label, value) rows. Run and file callbacks
    keep the same signature as ScientificAdapter. Hardware run callbacks execute
    inside the frozen operation's ownership scope and remain responsible for
    restoration, saving and explicitly releasing ownership with truthful outcomes.

    An optional ``validate_operation(kind, plan, preliminary)`` can express the
    numeric/device/data prerequisites for additional blank or capability actions.
    It must not represent an acknowledgement or approval flag.

    An optional ``read_operation_settings(kind)`` supplies raw intent/mode data
    only for custom actions using requires_valid_plan=False. This permits device
    checks before scientific inputs can be resolved. Its data is frozen before
    ownership, and validate_operation still applies. Standard acquisitions and
    actions requiring a valid plan never call this optional hook.
    """

    def read_settings(self) -> Any: ...
    def apply_settings(self, settings: Any) -> None: ...
    def make_plan(self, settings: Any) -> Any: ...
    def validate_plan(self, plan: Any) -> Sequence[str]: ...
    def summarize_plan(self, plan: Any) -> Sequence[tuple[str, str]]: ...
    def selected_records(self) -> ScientificSelections: ...
    def hardware_required(self, kind: str, settings: Any) -> bool: ...
    def validate_preliminary(self, preliminary: Any, plan: Any) -> Sequence[str]: ...
    def run_preliminary(self, snapshot: StartSnapshot, worker: OperationWorker) -> Any: ...
    def run_measurement(self, snapshot: StartSnapshot, worker: OperationWorker) -> Any: ...
    def request_abort(self, reason: str) -> None: ...
    def save_plan(self, path: Path, settings: Any, plan: Any) -> None: ...
    def load_plan(self, path: Path) -> Any: ...
    def load_run(self, path: Path) -> Any: ...
    def export_run(self, path: Path, result: Any) -> None: ...
    def new_run(self) -> None: ...


try:
    from PySide6.QtCore import Qt, QThread, Signal
    from PySide6.QtWidgets import (
        QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
        QMessageBox, QProgressBar, QPushButton, QScrollArea, QSlider, QSplitter,
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
            self.operation_started = Event()
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
                self.operation_started.set()
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

        def __init__(self, adapter: PlotAdapter, parent=None, *, save_root_provider=None):
            super().__init__(parent)
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
            from matplotlib.figure import Figure
            self.adapter, self.result = adapter, None
            self._image_root_provider = save_root_provider
            # The toolbar subplot editor requires an unconstrained layout engine.
            self.figure = Figure(figsize=(8, 5), layout="none")
            self.canvas = FigureCanvasQTAgg(self.figure)
            self.canvas.setMinimumHeight(215)
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
            layout.setSpacing(3)
            layout.addWidget(self.toolbar)
            self.axis_limits = AxisLimitsWidget(self.figure, self.canvas)
            self.toolbar.addSeparator()
            self.toolbar.addWidget(QLabel("Axes:"))
            self.toolbar.addWidget(self.axis_limits.axes_choice)
            self.toolbar.addWidget(self.axis_limits.auto_button)
            layout.addWidget(self.axis_limits)

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
            self.axis_limits.refresh_axes()
            self.toolbar.update()
            self.canvas.draw_idle()

        def clear_result(self):
            self.result = None
            self.reset_view()

        def save_image(self, path: Path):
            path = Path(path).expanduser().resolve()
            if path.exists():
                raise FileExistsError("Choose a new filename to preserve existing images")
            path.parent.mkdir(parents=True, exist_ok=True)
            self.figure.savefig(path, dpi=180)

        def _image_save_root(self):
            provider = self._image_root_provider
            parent = self.parentWidget()
            while provider is None and parent is not None:
                candidate = getattr(parent, "save_root_provider", None)
                if callable(candidate):
                    provider = candidate
                parent = parent.parentWidget()
            if provider is None:
                from control_app.paths import get_save_location
                provider = get_save_location
            return Path(provider()).expanduser().resolve()

        def _choose_image(self):
            try:
                root = self._image_save_root()
                path, _ = QFileDialog.getSaveFileName(self, "Save plot image", str(root / "measurement.png"), "PNG (*.png);;SVG (*.svg);;PDF (*.pdf)")
                if path:
                    self.save_image(Path(path))
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                self.error.emit(message)
                QMessageBox.warning(self, "Save plot image", message)


    class AxisLimitsWidget(QWidget):
        """Editable display limits for every axes in a Matplotlib figure."""

        def __init__(self, figure, canvas, parent=None):
            super().__init__(parent)
            self.figure, self.canvas = figure, canvas
            self._axes = []
            self._syncing = False
            self.axes_choice = QComboBox()
            self.axes_choice.setObjectName("plot_axes_choice")
            self.axes_choice.setMaximumWidth(120)
            self.axes_choice.setFixedHeight(19)
            self.inputs = {}
            for key, label in (("xmin", "X min"), ("xmax", "X max"),
                               ("ymin", "Y min"), ("ymax", "Y max")):
                editor = QLineEdit()
                editor.setObjectName("plot_" + key)
                editor.setFixedWidth(92)
                editor.setPlaceholderText("Auto")
                editor.setToolTip(f"Editable {label.lower()} for the selected axes")
                editor.editingFinished.connect(self.apply)
                self.inputs[key] = editor
            self.auto_button = QPushButton("Auto")
            self.auto_button.setToolTip("Restore automatic limits for the selected axes")
            self.auto_button.clicked.connect(self.restore_auto)
            layout = QGridLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setHorizontalSpacing(4)
            layout.setVerticalSpacing(2)
            layout.addWidget(self.canvas, 0, 0)
            y_rail = QWidget()
            y_layout = QVBoxLayout(y_rail)
            y_layout.setContentsMargins(0, 0, 0, 0)
            y_layout.setSpacing(2)
            y_layout.addWidget(QLabel("Y max"))
            y_layout.addWidget(self.inputs["ymax"])
            y_layout.addStretch(1)
            y_layout.addWidget(QLabel("Y min"))
            y_layout.addWidget(self.inputs["ymin"])
            layout.addWidget(y_rail, 0, 1)
            x_rail = QWidget()
            x_layout = QHBoxLayout(x_rail)
            x_layout.setContentsMargins(0, 0, 0, 0)
            x_layout.setSpacing(4)
            x_layout.addWidget(QLabel("X min"))
            x_layout.addWidget(self.inputs["xmin"])
            x_layout.addStretch(1)
            x_layout.addWidget(QLabel("X max"))
            x_layout.addWidget(self.inputs["xmax"])
            layout.addWidget(x_rail, 1, 0)
            layout.setRowStretch(0, 1)
            layout.setColumnStretch(0, 1)
            self.axes_choice.currentIndexChanged.connect(self._sync_from_axes)
            self.setEnabled(False)

        @staticmethod
        def _label(axis, index):
            title = axis.get_title().strip()
            xlabel, ylabel = axis.get_xlabel().strip(), axis.get_ylabel().strip()
            detail = title or " / ".join(value for value in (xlabel, ylabel) if value)
            return detail or f"Axes {index + 1}"

        def refresh_axes(self):
            previous = self.axes_choice.currentIndex()
            self._axes = list(self.figure.axes)
            self.axes_choice.blockSignals(True)
            self.axes_choice.clear()
            for index, axis in enumerate(self._axes):
                self.axes_choice.addItem(self._label(axis, index), index)
            self.axes_choice.setCurrentIndex(min(max(previous, 0), len(self._axes)-1))
            self.axes_choice.blockSignals(False)
            self.setEnabled(bool(self._axes))
            self._sync_from_axes()

        def _selected(self):
            index = self.axes_choice.currentIndex()
            return self._axes[index] if 0 <= index < len(self._axes) else None

        def _sync_from_axes(self, *_):
            axis = self._selected()
            self._syncing = True
            try:
                limits = (*axis.get_xlim(), *axis.get_ylim()) if axis is not None else (None,)*4
                values = (min(limits[:2]), max(limits[:2]), min(limits[2:]), max(limits[2:])) if axis is not None else limits
                for key, value in zip(("xmin", "xmax", "ymin", "ymax"), values):
                    self.inputs[key].setText("" if value is None else f"{value:.12g}")
            finally:
                self._syncing = False

        def apply(self):
            if self._syncing:
                return
            axis = self._selected()
            if axis is None:
                return
            try:
                values = {key: float(editor.text()) for key, editor in self.inputs.items()}
                if not all(math.isfinite(value) for value in values.values()):
                    raise ValueError
                if values["xmin"] >= values["xmax"] or values["ymin"] >= values["ymax"]:
                    raise ValueError
            except ValueError:
                self._sync_from_axes()
                return
            x_inverted = axis.get_xlim()[0] > axis.get_xlim()[1]
            y_inverted = axis.get_ylim()[0] > axis.get_ylim()[1]
            axis.set_xlim((values["xmax"], values["xmin"]) if x_inverted else (values["xmin"], values["xmax"]))
            axis.set_ylim((values["ymax"], values["ymin"]) if y_inverted else (values["ymin"], values["ymax"]))
            self.canvas.draw_idle()

        def restore_auto(self):
            axis = self._selected()
            if axis is None:
                return
            axis.relim()
            axis.autoscale(enable=True, axis="both", tight=False)
            self.canvas.draw_idle()
            self._sync_from_axes()


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
            path = Path(path).expanduser().resolve()
            def save(_worker):
                path.parent.mkdir(parents=True, exist_ok=True)
                return self.adapter.save_plan(path, settings, plan)
            self._launch(save, "save_plan", path)

        def load_plan(self, path):
            self._launch(lambda _worker: self.adapter.load_plan(Path(path)), "load_plan", path)

        def load_run(self, path):
            self._launch(lambda _worker: self.adapter.load_run(Path(path)), "load_run", path)

        def export_run(self, path):
            if self.result is None:
                raise ValueError("Load or acquire a native result before export")
            result = deepcopy(self.result)
            path = Path(path).expanduser().resolve()
            def export(_worker):
                path.parent.mkdir(parents=True, exist_ok=True)
                return self.adapter.export_run(path, result)
            self._launch(export, "export_run", path)

        def _prepare_save_folder(self, action):
            try:
                root = Path(self.save_root_provider()).expanduser().resolve()
            except (OSError, ValueError) as exc:
                self.status.setText(f"Cannot prepare the {action} folder.")
                self.status.setToolTip(str(exc))
                return None
            return root

        def _choose_save_plan(self):
            root = self._prepare_save_folder("Save Plan")
            if root is None:
                return
            path, _ = QFileDialog.getSaveFileName(self, "Save plan", str(root), "Plan files (*)")
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
            root = self._prepare_save_folder("Export")
            if root is None:
                return
            path, _ = QFileDialog.getSaveFileName(self, "Export data", str(root), "Data files (*)")
            if path:
                self.export_run(path)


    class CompactMeasurementPanel(QWidget):
        """Compact settings/actions left; derived rows and scientific plots right.

        Constructor: (settings_widget, adapter, context, parent=None,
        *, advanced_widget=None). No hardware access occurs during construction.
        Essential settings belong in settings_widget; controls with derived
        defaults belong in set_advanced_widget(). These controls remain visible
        in the framed advanced_content/advanced_group. Each field's Auto/value
        selection independently determines its override. Connect settings signals to
        refresh_plan(). There is no review widget or acknowledgement state.

        Stable extension layouts: control_layout/settings_layout,
        settings_extras_layout, advanced_layout, file_layout, blank_actions_layout,
        action_layout, right_layout, summary_form, run_file_layout, result_layout.
        add_action/add_blank_action/add_settings_action add controls in place.
        begin_operation dispatches custom blank/capability work through the same
        snapshot/ownership path. operation_finished(kind, outcome) lets a module
        apply its own extra operation result and then call refresh_readiness().
        requires_valid_plan=False permits a capability check before planning is possible.
        """

        busy_changed = Signal(bool)
        result_ready = Signal(object)
        preliminary_ready = Signal(object)
        run_loaded = Signal(object, str)
        outcome_ready = Signal(object)
        operation_finished = Signal(str, object)
        new_run_requested = Signal()

        def __init__(self, settings_widget: QWidget, adapter: CompactScientificAdapter,
                     context: MeasurementContext, parent=None, *, advanced_widget=None):
            super().__init__(parent)
            self.adapter, self.context = adapter, context
            self.save_root_provider = context.save_root
            self.settings_widget = settings_widget
            self.plan = self.preliminary = self.result = self.worker = None
            self.snapshot: StartSnapshot | None = None
            self._busy = False
            self._active_kind = None
            self._host_plan = None
            self._plan_issues = self._preliminary_issues = ()
            self._operation_actions = []
            root = QVBoxLayout(self)
            self.splitter = QSplitter(Qt.Orientation.Horizontal)
            root.addWidget(self.splitter, 1)
            self.left_panel, self.right_panel = QWidget(), QWidget()
            self.left_layout, self.right_layout = QVBoxLayout(self.left_panel), QVBoxLayout(self.right_panel)
            self.splitter.addWidget(self.left_panel)
            self.splitter.addWidget(self.right_panel)

            controls = QWidget()
            self.settings_layout = self.control_layout = QVBoxLayout(controls)
            self.settings_layout.addWidget(settings_widget)
            self.settings_extras_layout = QVBoxLayout()
            self.settings_layout.addLayout(self.settings_extras_layout)
            self.advanced_content = self.advanced_group = QGroupBox("Advanced overrides")
            self.advanced_layout = QVBoxLayout(self.advanced_content)
            self.settings_layout.addWidget(self.advanced_content)

            self.validation = QLabel()
            self.validation.setWordWrap(True)
            self.validation.setTextFormat(Qt.TextFormat.PlainText)
            self.settings_layout.addWidget(self.validation)
            self.save_plan_button, self.load_plan_button = QPushButton("Save plan…"), QPushButton("Load plan…")
            self.file_layout = QVBoxLayout()
            self.file_layout.addWidget(self.save_plan_button)
            self.file_layout.addWidget(self.load_plan_button)
            self.settings_layout.addLayout(self.file_layout)
            self.settings_layout.addStretch(1)
            self.settings_scroll = QScrollArea()
            self.settings_scroll.setWidgetResizable(True)
            self.settings_scroll.setWidget(controls)
            self.left_layout.addWidget(self.settings_scroll, 1)

            self.blank_actions_layout = QVBoxLayout()
            self.left_layout.addLayout(self.blank_actions_layout)
            self.action_layout = QVBoxLayout()
            self.left_layout.addLayout(self.action_layout)
            self.preliminary_button = QPushButton("Acquire preliminary")
            self.start_button = QPushButton("Acquire sample")
            self.abort_button = QPushButton("Stop")
            self.abort_button.setProperty("danger", True)
            self.new_run_button = QPushButton("New run")
            for button in (self.preliminary_button, self.start_button, self.abort_button, self.new_run_button):
                self.action_layout.addWidget(button)
            self.status = QLabel()
            self.status.setWordWrap(True)
            self.status.setTextFormat(Qt.TextFormat.PlainText)
            self.left_layout.addWidget(self.status)
            self.progress = QProgressBar()
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.progress.hide()
            self.left_layout.addWidget(self.progress)

            self.summary_group = QGroupBox("Derived experiment and effective settings")
            self.summary_form = QFormLayout(self.summary_group)
            self.summary_values = {}
            self.right_layout.addWidget(self.summary_group)
            self.load_run_button = QPushButton("Load native run…")
            self.export_button = QPushButton("Export data…")
            self.run_file_layout = QHBoxLayout()
            self.run_file_layout.addWidget(self.load_run_button)
            self.run_file_layout.addWidget(self.export_button)
            self.run_file_layout.addStretch(1)
            self.right_layout.addLayout(self.run_file_layout)
            self.result_layout = QVBoxLayout()
            self.right_layout.addLayout(self.result_layout, 1)

            self.preliminary_button.clicked.connect(lambda: self._user_action(lambda: self.begin("preliminary")))
            self.start_button.clicked.connect(lambda: self._user_action(lambda: self.begin("measurement")))
            self.abort_button.clicked.connect(lambda: self.request_abort("Stopped by user"))
            self.new_run_button.clicked.connect(lambda: self._user_action(self.new_run))
            self.save_plan_button.clicked.connect(lambda: self._user_action(self._choose_save_plan))
            self.load_plan_button.clicked.connect(lambda: self._user_action(self._choose_load_plan))
            self.load_run_button.clicked.connect(lambda: self._user_action(self._choose_load_run))
            self.export_button.clicked.connect(lambda: self._user_action(self._choose_export))
            if advanced_widget is not None:
                self.set_advanced_widget(advanced_widget)
            self.refresh_plan()
            self.splitter.setSizes([420, 900])

        # These legacy helpers concern file dialogs and running state only; they
        # carry no preliminary/review logic or widget-layout assumptions.
        command_running = GuidedMeasurementPanel.command_running
        close_blockers = GuidedMeasurementPanel.close_blockers
        _progress = GuidedMeasurementPanel._progress
        save_plan = GuidedMeasurementPanel.save_plan
        load_plan = GuidedMeasurementPanel.load_plan
        load_run = GuidedMeasurementPanel.load_run
        export_run = GuidedMeasurementPanel.export_run
        _prepare_save_folder = GuidedMeasurementPanel._prepare_save_folder
        _choose_save_plan = GuidedMeasurementPanel._choose_save_plan
        _choose_load_plan = GuidedMeasurementPanel._choose_load_plan
        _choose_load_run = GuidedMeasurementPanel._choose_load_run
        _choose_export = GuidedMeasurementPanel._choose_export

        @staticmethod
        def _brief(text):
            line = str(text).splitlines()[0] if str(text) else ""
            return line if len(line) <= 160 else line[:157].rstrip() + "…"

        def set_status(self, message):
            self.status.setText(self._brief(message))
            self.status.setToolTip(str(message))

        def output_location_changed(self, path):
            """Refresh destination hints without changing any plan or run snapshot.

            The scoped provider already reflects the application selection. File
            dialogs read it when opened; active operations keep their frozen root.
            """
            destination = str(self.save_root_provider())
            for button in (self.save_plan_button, self.load_plan_button,
                           self.load_run_button, self.export_button):
                button.setToolTip(destination)

        def _user_action(self, callback):
            try:
                return callback()
            except Exception as exc:
                self.set_status(f"{type(exc).__name__}: {exc}")
                return None

        def set_advanced_widget(self, widget):
            self.advanced_layout.addWidget(widget)
            widget.show()

        def add_action(self, text, callback, *, section="actions", requires_plan=True):
            layouts = {"actions": self.action_layout, "blank": self.blank_actions_layout,
                       "settings": self.settings_extras_layout}
            if section not in layouts:
                raise ValueError("Action section must be actions, blank, or settings")
            button = QPushButton(text)
            button.clicked.connect(lambda: self._user_action(callback))
            layouts[section].addWidget(button)
            self._operation_actions.append((button, requires_plan))
            self._update_controls()
            return button

        def add_blank_action(self, text, callback, *, requires_plan=True):
            return self.add_action(text, callback, section="blank", requires_plan=requires_plan)

        def add_settings_action(self, text, callback, *, requires_plan=False):
            return self.add_action(text, callback, section="settings", requires_plan=requires_plan)

        def add_result_widget(self, widget, stretch=1):
            self.result_layout.addWidget(widget, stretch)

        def set_summary_rows(self, rows):
            if isinstance(rows, str):
                rows = (("Plan", rows),) if rows else ()
            elif hasattr(rows, "items"):
                rows = rows.items()
            rows = tuple(rows)
            while self.summary_form.rowCount():
                self.summary_form.removeRow(0)
            self.summary_values.clear()
            self.summary_form.setVerticalSpacing(2)
            for label, value in rows:
                display = QLabel(str(value))
                display.setWordWrap(True)
                display.setTextFormat(Qt.TextFormat.PlainText)
                self.summary_values[str(label)] = display
                self.summary_form.addRow(str(label), display)

        def refresh_plan(self, *_):
            if self._busy:
                return
            from .parameter_feedback import required_parameter_prompts, plan_parameter_prompts, live_parameter_updates
            if not getattr(self, "_live_parameters_connected", False):
                live_parameter_updates(self.settings_widget, self.refresh_plan)
                self._live_parameters_connected = True
            try:
                missing = required_parameter_prompts(self.settings_widget)
                if missing:
                    raise ValueError("\n".join(missing))
                settings = deepcopy(self.adapter.read_settings())
                candidate = self.adapter.make_plan(settings)
                from .uniform_layout import effective_hf2_values
                effective_hf2_values(self, candidate)
                self._plan_issues = tuple(self.adapter.validate_plan(candidate))
                self.set_summary_rows(self.adapter.summarize_plan(candidate))
                self.plan = None if self._plan_issues else candidate
                self._host_plan = self.context.new_plan(settings) if self.plan is not None else None
            except Exception as exc:
                self.plan = self._host_plan = None
                self._plan_issues = (str(exc),)
                self.set_summary_rows(())
            if self._plan_issues:
                self.set_summary_rows((("Required settings", plan_parameter_prompts(self._plan_issues)),))
            # Keep scientific data; compatibility, not a manual flag, determines
            # whether it remains usable after settings or device changes.
            self.refresh_readiness()

        def refresh_readiness(self, *_):
            if self._busy:
                self._update_controls()
                return
            try:
                self._preliminary_issues = (tuple(self.adapter.validate_preliminary(self.preliminary, self.plan))
                                            if self.plan is not None else ())
            except Exception as exc:
                self._preliminary_issues = (str(exc),)
            issues = self._plan_issues or self._preliminary_issues
            self.validation.setText("\n".join(self._brief(issue) for issue in issues[:2]))
            self.validation.setToolTip("\n".join(str(issue) for issue in issues))
            self._update_controls()

        def _update_controls(self, *_):
            idle, valid = not self._busy, self.plan is not None
            self.settings_widget.setEnabled(idle)
            self.advanced_content.setEnabled(idle)
            self.preliminary_button.setEnabled(idle and valid)
            self.start_button.setEnabled(idle and valid and not self._preliminary_issues)
            self.abort_button.setEnabled(self._busy and self._active_kind not in ("save_plan", "load_plan", "load_run", "export_run"))
            self.new_run_button.setEnabled(idle)
            self.save_plan_button.setEnabled(idle and valid)
            self.load_plan_button.setEnabled(idle)
            self.load_run_button.setEnabled(idle)
            self.export_button.setEnabled(idle and self.result is not None)
            for button, requires_plan in self._operation_actions:
                button.setEnabled(idle and (valid or not requires_plan))
            self.progress.setVisible(self._busy)

        def begin(self, kind="measurement"):
            if kind not in ("preliminary", "measurement"):
                raise ValueError("Use begin_operation for a custom operation kind")
            if self._busy:
                raise RuntimeError("An operation is already running")
            self.refresh_readiness()
            if kind == "measurement" and self._preliminary_issues:
                self.set_status(self._preliminary_issues[0])
                return
            callback = self.adapter.run_preliminary if kind == "preliminary" else self.adapter.run_measurement
            return self.begin_operation(kind, callback, invalidates_preliminary=kind == "preliminary")

        def begin_operation(self, kind, operation, *, invalidates_preliminary=False, requires_valid_plan=True):
            """Freeze, own, and dispatch one scientific callback(snapshot, worker)."""
            if self._busy:
                raise RuntimeError("An operation is already running")
            if kind in ("preliminary", "measurement") and not requires_valid_plan:
                raise ValueError("Preliminary and measurement operations require a valid plan")
            if requires_valid_plan and self.plan is None:
                raise ValueError("A valid plan is required")
            if kind == "measurement":
                preliminary_issues = tuple(self.adapter.validate_preliminary(self.preliminary, self.plan))
                if preliminary_issues:
                    self.set_status(preliminary_issues[0])
                    return
            validation = getattr(self.adapter, "validate_operation", None)
            issues = tuple(validation(kind, self.plan, self.preliminary)) if callable(validation) else ()
            if issues:
                self.set_status(issues[0])
                return
            plan, preliminary = deepcopy(self.plan), deepcopy(self.preliminary)
            selected = self.adapter.selected_records()
            if requires_valid_plan:
                host_plan = self._host_plan or self.context.new_plan(self.adapter.read_settings())
            else:
                raw_settings = getattr(self.adapter, "read_operation_settings", None)
                settings = raw_settings(kind) if callable(raw_settings) else self.adapter.read_settings()
                host_plan = self.context.new_plan(settings)
            operation_snapshot = self.context.begin_operation(
                plan=host_plan, calibration_records=selected.calibration_records,
                sample_records=selected.sample_records,
                hardware=self.adapter.hardware_required(kind, host_plan.settings),
                purpose=kind, cancel=self.request_abort,
            )
            snapshot = self.snapshot = StartSnapshot(operation_snapshot, str(kind), plan, preliminary)
            if invalidates_preliminary:
                self.preliminary = None

            def execute(worker):
                if snapshot.operation.hardware:
                    with self.context.hardware_scope(snapshot.operation):
                        return operation(snapshot, worker)
                return operation(snapshot, worker)
            try:
                self._launch(execute, str(kind))
            except Exception:
                dispatched = self.worker and (self.worker.isRunning() or self.worker.operation_started.is_set())
                if dispatched:
                    # A startup wrapper may fail after the thread entered its
                    # operation. Only that operation can verify/release ownership;
                    # retain busy state until its completion callback is delivered.
                    raise
                if snapshot.operation.hardware:
                    self.context.ownership.release(snapshot.operation.ownership, safe_verified=True,
                                                   preservation_verified=True, detail="Worker dispatch failed before hardware access")
                failed_worker, self.worker = self.worker, None
                if failed_worker is not None:
                    failed_worker.deleteLater()
                self._busy, self._active_kind = False, None
                self._update_controls()
                self.busy_changed.emit(False)
                raise
            return snapshot

        def _launch(self, operation, kind, path=None):
            if self._busy:
                raise RuntimeError("An operation is already running")
            worker = self.worker = OperationWorker(operation, self)
            self._busy, self._active_kind = True, kind
            worker.message.connect(lambda text: self.set_status(text) if self.worker is worker else None)
            worker.progress.connect(lambda done, total: self._progress(done, total) if self.worker is worker else None)
            worker.finished.connect(lambda: self._finished(worker, kind, path))
            self.progress.setRange(0, 0)
            self.set_status(f"Running {kind.replace('_', ' ')}…")
            self._update_controls()
            self.busy_changed.emit(True)
            worker.start()

        def _finished(self, worker, kind, path):
            if self.worker is not worker:
                return
            outcome = worker.outcome
            self.progress.setRange(0, 100)
            self.progress.setValue(100 if outcome.state == "completed" else 0)
            self.set_status(outcome.error or "Complete")
            loaded_plan = False
            try:
                if outcome.state == "completed":
                    if kind == "preliminary":
                        self.preliminary = outcome.result
                        self.preliminary_ready.emit(outcome.result)
                    elif kind == "measurement":
                        self.result = outcome.result
                        self.result_ready.emit(outcome.result)
                    elif kind == "load_plan":
                        self.adapter.apply_settings(outcome.result)
                        loaded_plan = True
                    elif kind == "load_run":
                        self.result = outcome.result
                        self.run_loaded.emit(outcome.result, str(path))
                if worker.notification_errors:
                    self.set_status("Notification failed: " + "; ".join(worker.notification_errors))
            except Exception as exc:
                self.set_status(f"Display failed: {type(exc).__name__}: {exc}")
            finally:
                self.worker = None
                self._busy, self._active_kind = False, None
                worker.deleteLater()
                self.operation_finished.emit(kind, outcome)
                if loaded_plan:
                    self.refresh_plan()
                else:
                    self.refresh_readiness()
                self.busy_changed.emit(False)
                self.outcome_ready.emit(outcome)

        def request_abort(self, reason):
            if self.worker is None or not self._busy:
                return
            self.worker.request_abort(reason)
            try:
                if self._active_kind not in ("save_plan", "load_plan", "load_run", "export_run"):
                    self.adapter.request_abort(reason)
                self.set_status("Stopping; preserving data…")
            except Exception as exc:
                self.set_status(f"Stop failed: {type(exc).__name__}: {exc}")

        def new_run(self):
            if self._busy:
                raise RuntimeError("Wait for the current operation to finish")
            self.adapter.new_run()
            self.preliminary = self.result = self.snapshot = None
            self.progress.setValue(0)
            self.refresh_plan()
            self.set_status("")
            self.new_run_requested.emit()
