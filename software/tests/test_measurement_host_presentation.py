"""Executable scientific adapter examples; no hardware or feature packages."""
from pathlib import Path
from contextlib import contextmanager
from threading import Event
from types import SimpleNamespace
import time

import pytest


@pytest.fixture
def qt_app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def wait_for(app, condition):
    deadline = time.monotonic() + 5
    while not condition():
        app.processEvents()
        if time.monotonic() > deadline:
            pytest.fail("Background presentation operation did not finish")
        time.sleep(.005)
    app.processEvents()


def test_time_units_cover_nanoseconds_microseconds_and_long_recovery():
    from control_app.measurement_host.presentation import choose_time_display
    assert choose_time_display([0, 8e-9]).unit == "ns"
    assert choose_time_display([0, 4e-6]).unit == "µs"
    assert choose_time_display([0, .004]).unit == "ms"
    assert choose_time_display([0, 7200]).unit == "h"
    assert choose_time_display([0, .0000001], unit="us").format(.0000001) == "0.100 µs"
    assert choose_time_display([0, 1e-12], unit="ms").decimals >= 9
    with pytest.raises(ValueError, match="finite"):
        choose_time_display([float("nan")])


def test_linked_numeric_controls_step_measured_samples_and_typed_nearest(qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from control_app.measurement_host.presentation import LinkedSliceControl
    control = LinkedSliceControl([10, 4, 4.00001, 1], decimals=3, label="Delay", unit="ns")
    events = []
    control.index_changed.connect(events.append)
    control.set_index(1)
    control.input.stepBy(1)
    assert control.index == 2  # Distinct sample despite identical numeric display.
    control.input.editingFinished.emit()
    assert control.index == 2
    control.input.stepBy(1)
    assert control.index == 0
    control.input.stepBy(-3)
    assert control.index == 3
    control.input.lineEdit().setFocus()
    control.input.lineEdit().selectAll()
    QTest.keyClicks(control.input.lineEdit(), "8")
    QTest.keyClick(control.input.lineEdit(), Qt.Key.Key_Return)
    assert control.index == 0 and control.input.value() == 10
    assert len(events) >= 5
    control.deleteLater()


def test_held_numeric_arrow_updates_before_release(qt_app):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from control_app.measurement_host.presentation import LinkedSliceControl
    control = LinkedSliceControl(range(100), label="Measured slice")
    control.resize(700, 60)
    control.show()
    control.set_index(0)
    qt_app.processEvents()
    changed = []
    control.index_changed.connect(changed.append)
    point = QPoint(control.input.width()-7, control.input.height()//4)
    QTest.mousePress(control.input, Qt.MouseButton.LeftButton, pos=point)
    QTest.qWait(750)
    assert control.index > 1 and len(changed) > 1
    QTest.mouseRelease(control.input, Qt.MouseButton.LeftButton, pos=point)
    control.close()
    control.deleteLater()


def test_worker_cancellation_cleanup_save_failure_and_callback_failure(qt_app):
    from control_app.measurement_host.presentation import OperationWorker
    records = []

    def operation(worker):
        try:
            worker.notify(lambda: (_ for _ in ()).throw(RuntimeError("status callback")))
            worker.request_abort("operator abort")
            worker.check_cancelled()
        finally:
            records.extend(["restoration", "native save"])

    worker = OperationWorker(operation)
    worker.start()
    wait_for(qt_app, lambda: worker.isFinished())
    assert worker.outcome.state == "cancelled"
    assert records == ["restoration", "native save"]
    assert worker.notification_errors == ["RuntimeError: status callback"]

    def failed_save(worker):
        try:
            raise InterruptedError("cancelled")
        finally:
            raise OSError("native data save failed")

    second = OperationWorker(failed_save)
    second.start()
    wait_for(qt_app, lambda: second.isFinished())
    assert second.outcome.state == "failed"
    assert "native data save failed" in second.outcome.error


class DummyScientificAdapter:
    """Minimal independent adapter; scientific objects are deliberately simple."""

    def __init__(self):
        self.settings = {"delay_s": 5e-9}
        self.records = {"sample_selection": "sample-window-1"}
        self.calls = []
        self.gate = Event()
        self.gate.set()

    def read_settings(self): return self.settings
    def apply_settings(self, settings): self.settings = settings
    def make_plan(self, settings): return {"delay_s": settings["delay_s"], "samples": 3}
    def validate_plan(self, plan): return [] if plan["delay_s"] > 0 else ["Delay must be positive."]
    def summarize_plan(self, plan): return f"{plan['samples']} measured points"
    def selected_records(self):
        from control_app.measurement_host.presentation import ScientificSelections
        return ScientificSelections(sample_records=(self.records,))
    def hardware_required(self, kind, settings): return False
    def run_preliminary(self, snapshot, worker):
        self.calls.append(snapshot)
        return {"accepted": True, "spectrum": [1, 2, 3]}
    def summarize_preliminary(self, result): return "Review the three measured points."
    def validate_review(self, preliminary, plan): return [] if preliminary["accepted"] else ["Review rejected."]
    def run_measurement(self, snapshot, worker):
        self.calls.append(snapshot)
        while not self.gate.wait(.01):
            worker.check_cancelled()
        worker.progress.emit(3, 3)
        return {"native_run": snapshot.operation_id, "spectrum": [3, 4, 5]}
    def request_abort(self, reason): self.calls.append(reason)
    def save_plan(self, path, settings, plan): path.write_text(str(settings["delay_s"]))
    def load_plan(self, path): return {"delay_s": float(path.read_text())}
    def load_run(self, path): return {"native_path": str(path), "spectrum": [5, 6, 7]}
    def export_run(self, path, result): path.write_text(",".join(map(str, result["spectrum"])))
    def new_run(self): self.calls.append("new run")


@pytest.mark.parametrize("panel_name", ["GuidedMeasurementPanel", "CompactMeasurementPanel"])
def test_save_click_prepares_only_its_scoped_root_and_nested_plan_parent(qt_app, tmp_path, monkeypatch, panel_name):
    from PySide6.QtWidgets import QWidget
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_host import presentation

    roots = {mode: tmp_path / "2026-09-14" / ("Nano" if mode == "single" else "DD Nano")
             for mode in ("single", "dual")}
    factory = ContextFactory(ownership=object(), preference_backend={},
        instance_save_root_provider=lambda instance: roots[instance.rsplit(":", 1)[1]])
    panel_type = getattr(presentation, panel_name)
    panels = [panel_type(QWidget(), DummyScientificAdapter(),
        factory.for_experiment("nanosecond_stroboscopy").for_mode(mode)) for mode in roots]
    try:
        assert all(not root.exists() for root in roots.values())
        monkeypatch.setattr(presentation.QFileDialog, "getOpenFileName", lambda *args: ("", ""))
        panels[0].load_plan_button.click()
        assert all(not root.exists() for root in roots.values())
        observed = []
        def choose(parent, title, directory, *args):
            directory = Path(directory)
            assert directory.is_dir()  # The native dialog receives an existing folder.
            observed.append(directory)
            return "", ""
        monkeypatch.setattr(presentation.QFileDialog, "getSaveFileName", choose)
        panels[0].save_plan_button.click()
        assert observed == [roots["single"]]
        assert list(roots["single"].iterdir()) == []
        assert not roots["dual"].exists()

        selected = roots["dual"] / "plans" / "nested" / "native.plan"
        def choose_nested(parent, title, directory, *args):
            assert Path(directory) == roots["dual"] and Path(directory).is_dir()
            assert not selected.parent.exists()
            return str(selected), ""
        monkeypatch.setattr(presentation.QFileDialog, "getSaveFileName", choose_nested)
        panels[1].save_plan_button.click()
        wait_for(qt_app, lambda: not panels[1].command_running())
        assert selected.read_text() == str(panels[1].adapter.settings["delay_s"])
        assert list(roots["single"].iterdir()) == []
    finally:
        for panel in panels:
            panel.deleteLater()


@pytest.mark.parametrize("panel_name", ["GuidedMeasurementPanel", "CompactMeasurementPanel"])
@pytest.mark.parametrize("action", ["save_plan", "export"])
def test_save_folder_failure_is_visible_before_dialog_without_starting_worker(qt_app, tmp_path, monkeypatch, panel_name, action):
    from PySide6.QtWidgets import QWidget
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_host import presentation

    destination = tmp_path / "denied"
    context = ContextFactory(ownership=object(), preference_backend={},
        instance_save_root_provider=lambda instance: destination).for_experiment("nanosecond_stroboscopy").for_mode("single")
    panel = getattr(presentation, panel_name)(QWidget(), DummyScientificAdapter(), context)
    mkdir = Path.mkdir
    def denied(path, *args, **kwargs):
        if path == destination:
            raise PermissionError("Injected Save Plan destination permission failure")
        return mkdir(path, *args, **kwargs)
    monkeypatch.setattr(Path, "mkdir", denied)
    monkeypatch.setattr(presentation.QFileDialog, "getSaveFileName", lambda *args: pytest.fail("Failed root must not open dialog"))
    try:
        if action == "export":
            panel.result = {"spectrum": [1, 2, 3]}
            panel._update_controls()
            panel.export_button.click()
        else:
            panel.save_plan_button.click()
        assert "Cannot prepare" in panel.status.text()
        assert "permission failure" in panel.status.toolTip()
        assert not panel.command_running() and not destination.exists()
    finally:
        panel.deleteLater()


@pytest.mark.parametrize("panel_name", ["GuidedMeasurementPanel", "CompactMeasurementPanel"])
def test_loaded_run_export_prepares_current_tab_root_and_chosen_parent(qt_app, tmp_path, monkeypatch, panel_name):
    from PySide6.QtWidgets import QWidget
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_host import presentation

    root = tmp_path / "2026-09-15" / "DD Nano"
    other_root = tmp_path / "2026-09-15" / "Nano"
    context = ContextFactory(ownership=object(), preference_backend={}, save_root_provider=lambda: other_root,
        instance_save_root_provider=lambda instance: root).for_experiment("nanosecond_stroboscopy").for_mode("dual")
    panel = getattr(presentation, panel_name)(QWidget(), DummyScientificAdapter(), context)
    try:
        old_source = tmp_path / "2026-09-14" / "source" / "native"
        panel.load_run(old_source)
        wait_for(qt_app, lambda: not panel.command_running())
        assert panel.result["native_path"] == str(old_source)
        assert not root.exists() and not other_root.exists()
        selected = root / "exports" / "new" / "data.csv"
        def choose(parent, title, directory, *args):
            assert Path(directory) == root and root.is_dir()
            assert not selected.parent.exists()
            return str(selected), ""
        monkeypatch.setattr(presentation.QFileDialog, "getSaveFileName", choose)
        panel.export_button.click()
        wait_for(qt_app, lambda: not panel.command_running())
        assert selected.read_text() == "5,6,7"
        assert panel.result["native_path"] == str(old_source)
        assert not other_root.exists() and not old_source.exists()
    finally:
        panel.deleteLater()


def test_guided_adapter_isolation_frozen_output_review_plan_native_export_new_run(qt_app, tmp_path):
    from PySide6.QtWidgets import QWidget
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_host.presentation import GuidedMeasurementPanel
    adapter = DummyScientificAdapter()
    other = DummyScientificAdapter()
    destination = [tmp_path / "first"]
    factory = ContextFactory(save_root_provider=lambda: destination[0], ownership=object())
    context = factory.for_experiment("nanosecond_stroboscopy")
    panel = GuidedMeasurementPanel(QWidget(), adapter, context.for_mode("single"))
    second = GuidedMeasurementPanel(QWidget(), other, context.for_mode("dual"))
    assert adapter.calls == [] and other.calls == []  # Construction has no device action.
    assert not panel.start_button.isEnabled()
    panel.begin("preliminary")
    wait_for(qt_app, lambda: not panel.command_running())
    assert panel.preliminary["accepted"] and second.preliminary is None
    assert not panel.start_button.isEnabled()
    panel.review.setChecked(True)
    adapter.gate.clear()
    panel.begin("measurement")
    snapshot = panel.snapshot
    assert panel.command_running() and not panel.settings_widget.isEnabled()
    destination[0] = tmp_path / "changed"
    adapter.settings["delay_s"] = 80e-9
    adapter.records["sample_selection"] = "changed"
    assert snapshot.settings["delay_s"] == 5e-9
    assert snapshot.operation.sample_records[0]["sample_selection"] == "sample-window-1"
    with pytest.raises(TypeError):
        snapshot.settings["delay_s"] = 99
    assert snapshot.save_root == tmp_path / "first"
    assert snapshot.operation.output_path.parent == tmp_path / "first" / "measurements" / "nanosecond_stroboscopy" / "single"
    assert adapter.calls[0].operation_id != snapshot.operation_id
    adapter.gate.set()
    wait_for(qt_app, lambda: not panel.command_running())
    assert panel.result and second.result is None
    plan_path = tmp_path / "saved.plan"
    panel.save_plan(plan_path)
    wait_for(qt_app, lambda: not panel.command_running())
    panel.load_plan(plan_path)
    wait_for(qt_app, lambda: not panel.command_running())
    assert panel.preliminary is None and not panel.review.isChecked()
    panel.load_run(tmp_path / "native")
    wait_for(qt_app, lambda: not panel.command_running())
    export_path = tmp_path / "quantitative.csv"
    panel.export_run(export_path)
    wait_for(qt_app, lambda: not panel.command_running())
    assert export_path.read_text() == "5,6,7"
    panel.new_run()
    assert panel.result is panel.preliminary is panel.snapshot is None
    assert "new run" in adapter.calls and other.calls == []
    panel.deleteLater()
    second.deleteLater()


def test_plot_adapter_supports_plain_2d_toolbar_home_and_image_preservation(qt_app, tmp_path):
    from control_app.measurement_host.presentation import PlotPanel

    class SpectrumAdapter:
        def draw(self, figure, result):
            axes = figure.add_subplot(111)
            axes.plot(result["wavenumber"], result["absorbance"])
            axes.set(xlabel="Wavenumber (cm⁻¹)", ylabel="Absorbance")
            axes.invert_xaxis()

    panel = PlotPanel(SpectrumAdapter())
    panel.set_result({"wavenumber": [2000, 1999, 1998], "absorbance": [.1, float("nan"), .2]})
    assert len(panel.figure.axes) == 1 and panel.figure.axes[0].name == "rectilinear"
    panel.toolbar.pan()
    panel.select_action.trigger()
    assert not panel.toolbar.mode
    panel.figure.axes[0].set_xlim(1, 2)
    panel.toolbar._actions["home"].trigger()
    assert panel.figure.axes[0].get_xlim()[0] > 1999
    path = tmp_path / "spectrum.png"
    panel.save_image(path)
    assert path.stat().st_size > 1000
    with pytest.raises(FileExistsError):
        panel.save_image(path)
    panel.clear_result()
    assert not panel.figure.axes
    panel.deleteLater()


def _nested_plot(owner, presentation):
    from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget
    container = QWidget()
    layout = QVBoxLayout(container)
    tabs = QTabWidget()
    plot = presentation.PlotPanel(SimpleNamespace(draw=lambda figure, result:
        figure.add_subplot(111).plot([1, 2, 3], result)))
    tabs.addTab(plot, "Native points")
    layout.addWidget(tabs)
    owner.result_layout.addWidget(container)
    plot.set_result([3, 2, 1])
    return plot


@pytest.mark.parametrize("panel_name", ["GuidedMeasurementPanel", "CompactMeasurementPanel"])
def test_plot_toolbar_save_uses_owning_panel_root_and_preserves_existing_image(qt_app, tmp_path, monkeypatch, panel_name):
    from PySide6.QtWidgets import QWidget
    from control_app import paths
    from control_app.measurement_host import presentation
    from control_app.measurement_host.context import ContextFactory

    roots = {mode: tmp_path / "2026-09-15" / ("Nano" if mode == "single" else "DD Nano")
             for mode in ("single", "dual")}
    unrelated = tmp_path / "another selected tab"
    monkeypatch.setattr(paths, "get_save_location", lambda: unrelated)
    factory = ContextFactory(ownership=object(), preference_backend={},
        instance_save_root_provider=lambda instance: roots[instance.rsplit(":", 1)[1]])
    owners = [getattr(presentation, panel_name)(QWidget(), DummyScientificAdapter(),
        factory.for_experiment("nanosecond_stroboscopy").for_mode(mode)) for mode in roots]
    plots = [_nested_plot(owner, presentation) for owner in owners]
    warnings = []
    monkeypatch.setattr(presentation.QMessageBox, "warning", lambda parent, title, message: warnings.append(message))
    try:
        assert all(not root.exists() for root in roots.values()) and not unrelated.exists()
        for mode, plot in zip(roots, plots):
            root = roots[mode]
            selected = root / "images" / "nested" / "spectrum.png"
            def choose(parent, title, filename, *args):
                assert parent is plot and Path(filename) == root / "measurement.png"
                assert root.is_dir()
                return str(selected), ""
            monkeypatch.setattr(presentation.QFileDialog, "getSaveFileName", choose)
            plot.toolbar._actions["save_figure"].trigger()
            original = selected.read_bytes()
            assert len(original) > 1000
            errors = []
            plot.error.connect(errors.append)
            plot.toolbar._actions["save_figure"].trigger()
            assert selected.read_bytes() == original
            assert len(errors) == 1 and "FileExistsError" in errors[0]
            assert warnings[-1] == errors[0]
        assert not unrelated.exists()
    finally:
        for owner in owners:
            owner.deleteLater()


@pytest.mark.parametrize("panel_name", ["GuidedMeasurementPanel", "CompactMeasurementPanel"])
@pytest.mark.parametrize("failure_stage", ["root", "chosen_parent"])
def test_plot_toolbar_save_reports_folder_failure(qt_app, tmp_path, monkeypatch, panel_name, failure_stage):
    from PySide6.QtWidgets import QWidget
    from control_app.measurement_host import presentation
    from control_app.measurement_host.context import ContextFactory

    root = tmp_path / "2026-09-15" / "Nano"
    selected = root / "images" / "new" / "spectrum.png"
    context = ContextFactory(ownership=object(), preference_backend={},
        instance_save_root_provider=lambda instance: root).for_experiment("nanosecond_stroboscopy").for_mode("single")
    owner = getattr(presentation, panel_name)(QWidget(), DummyScientificAdapter(), context)
    plot = _nested_plot(owner, presentation)
    mkdir = Path.mkdir
    def denied(path, *args, **kwargs):
        if path == (root if failure_stage == "root" else selected.parent):
            raise PermissionError("Injected image folder permission failure")
        return mkdir(path, *args, **kwargs)
    monkeypatch.setattr(Path, "mkdir", denied)
    def choose(*args):
        assert failure_stage == "chosen_parent", "A failed root must not open the dialog"
        return str(selected), ""
    monkeypatch.setattr(presentation.QFileDialog, "getSaveFileName", choose)
    warnings, errors = [], []
    monkeypatch.setattr(presentation.QMessageBox, "warning", lambda parent, title, message: warnings.append(message))
    plot.error.connect(errors.append)
    try:
        plot.toolbar._actions["save_figure"].trigger()
        assert warnings == errors and len(errors) == 1
        assert "permission failure" in errors[0]
        assert not selected.exists()
        assert not owner.command_running()
    finally:
        owner.deleteLater()


@pytest.mark.parametrize("explicit", [False, True])
def test_standalone_plot_toolbar_prepares_fallback_or_explicit_root_only_on_save(qt_app, tmp_path, monkeypatch, explicit):
    from control_app import paths
    from control_app.measurement_host import presentation

    fallback, injected = tmp_path / "standalone", tmp_path / "explicit"
    monkeypatch.setattr(paths, "get_save_location", lambda: fallback)
    plot = presentation.PlotPanel(SimpleNamespace(draw=lambda *args: None),
        save_root_provider=(lambda: injected) if explicit else None)
    root = injected if explicit else fallback
    observed = []
    def cancel(parent, title, filename, *args):
        assert root.is_dir()
        observed.append(Path(filename))
        return "", ""
    monkeypatch.setattr(presentation.QFileDialog, "getSaveFileName", cancel)
    try:
        assert not fallback.exists() and not injected.exists()
        plot.toolbar._actions["save_figure"].trigger()
        assert observed == [root / "measurement.png"]
        assert list(root.iterdir()) == []
        assert not (fallback if explicit else injected).exists()
    finally:
        plot.deleteLater()


def test_hardware_declaration_acquires_before_dispatch_and_cleanup_owns_release(qt_app, tmp_path):
    from PySide6.QtWidgets import QWidget
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_host.presentation import GuidedMeasurementPanel

    class Coordinator:
        def __init__(self):
            self.owner = None
            self.calls = []
        def acquire(self, instance_id, **kwargs):
            assert self.owner is None
            self.calls.append("acquire")
            self.owner = SimpleNamespace(instance_id=instance_id, operation_id=kwargs["operation_id"])
            return self.owner
        def assert_owner(self, token): assert token is self.owner
        @contextmanager
        def scope(self, token):
            self.assert_owner(token)
            self.calls.append("enter worker scope")
            yield
        def release(self, token, **kwargs):
            self.assert_owner(token)
            assert kwargs["safe_verified"] and kwargs["preservation_verified"]
            self.calls.append("release after native save")
            self.owner = None

    coordinator = Coordinator()
    context = ContextFactory(save_root_provider=lambda: tmp_path, ownership=coordinator).for_experiment("fixed_wavenumber_kinetics").for_mode("single")

    class HardwareAdapter(DummyScientificAdapter):
        def hardware_required(self, kind, settings): return True
        def run_preliminary(self, snapshot, worker):
            assert coordinator.calls == ["acquire", "enter worker scope"]
            try:
                worker.check_cancelled()
                return super().run_preliminary(snapshot, worker)
            finally:
                coordinator.calls.extend(["restoration", "native save"])
                context.ownership.release(snapshot.operation.ownership, safe_verified=True, preservation_verified=True)

    panel = GuidedMeasurementPanel(QWidget(), HardwareAdapter(), context)
    assert coordinator.calls == []
    panel.begin("preliminary")
    assert coordinator.calls[0] == "acquire"
    wait_for(qt_app, lambda: not panel.command_running())
    assert coordinator.calls == ["acquire", "enter worker scope", "restoration", "native save", "release after native save"]
    assert coordinator.owner is None
    panel.deleteLater()


def test_early_worker_abort_enters_cleanup_and_offline_abort_never_targets_runner(qt_app, tmp_path):
    from PySide6.QtWidgets import QWidget
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_host.presentation import GuidedMeasurementPanel, OperationWorker
    cleanup = []

    def operation(worker):
        try:
            worker.check_cancelled()
        finally:
            cleanup.append("release pre-acquired ownership")

    worker = OperationWorker(operation)
    worker.request_abort("preparation cancelled")
    worker.start()
    wait_for(qt_app, lambda: worker.isFinished())
    assert worker.outcome.state == "cancelled" and cleanup

    class OfflineAdapter(DummyScientificAdapter):
        def load_run(self, path):
            self.gate.wait(2)
            return super().load_run(path)

    adapter = OfflineAdapter()
    context = ContextFactory(save_root_provider=lambda: tmp_path, ownership=object()).for_experiment("steady_state_slow_scan").for_mode("single")
    panel = GuidedMeasurementPanel(QWidget(), adapter, context)
    panel.begin("preliminary")
    wait_for(qt_app, lambda: not panel.command_running())
    stale_worker = SimpleNamespace(outcome=None)
    panel._finished(stale_worker, "measurement", None)  # A delayed unrelated completion is ignored.
    adapter.gate.clear()
    panel.load_run(tmp_path)
    panel.request_abort("offline load stop")
    assert "offline load stop" not in adapter.calls
    adapter.gate.set()
    wait_for(qt_app, lambda: not panel.command_running())
    panel.deleteLater()
