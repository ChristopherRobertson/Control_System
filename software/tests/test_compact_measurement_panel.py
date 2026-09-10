"""Shared compact UI contract; scientific fixtures have no manual review state."""
from pathlib import Path
from threading import Event
import time

import pytest


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    instance = QApplication.instance() or QApplication([])
    yield instance
    instance.processEvents()


def wait_for(app, predicate):
    deadline = time.monotonic() + 4
    while not predicate():
        app.processEvents()
        if time.monotonic() > deadline:
            pytest.fail("Compact panel operation did not complete")
        time.sleep(.002)
    app.processEvents()


class Adapter:
    def __init__(self):
        self.settings = {"wavenumber_cm1": 1900., "real": False}
        self.sample_records = [{"selection_id": "window-1"}]
        self.calls = []
        self.gate = Event()
        self.gate.set()

    def read_settings(self): return self.settings
    def apply_settings(self, settings): self.settings = settings
    def make_plan(self, settings):
        if settings["wavenumber_cm1"] is None:
            raise ValueError("Enter a wavenumber")
        return {"wavenumber_cm1": settings["wavenumber_cm1"], "points": 3}
    def validate_plan(self, plan): return ()
    def summarize_plan(self, plan):
        return (("Wavenumber", f"{plan['wavenumber_cm1']:g} cm⁻¹"), ("Points", "3"))
    def selected_records(self):
        from control_app.measurement_host.presentation import ScientificSelections
        return ScientificSelections(sample_records=tuple(self.sample_records))
    def hardware_required(self, kind, settings): return settings["real"]
    def validate_preliminary(self, preliminary, plan):
        if preliminary is None:
            return ("Acquire preliminary",)
        return () if preliminary["wavenumber_cm1"] == plan["wavenumber_cm1"] else ("Preliminary wavenumber differs",)
    def run_preliminary(self, snapshot, worker):
        self.calls.append(snapshot)
        return {"wavenumber_cm1": snapshot.plan["wavenumber_cm1"]}
    def run_measurement(self, snapshot, worker):
        self.calls.append(snapshot)
        while not self.gate.wait(.01):
            worker.check_cancelled()
        worker.progress.emit(3, 3)
        return {"native_path": str(snapshot.operation.output_path), "spectrum": [1, 2, 3]}
    def request_abort(self, reason): self.calls.append(reason)
    def save_plan(self, path, settings, plan): path.write_text(str(settings["wavenumber_cm1"]))
    def load_plan(self, path): return {"wavenumber_cm1": float(path.read_text()), "real": False}
    def load_run(self, path): return {"native_path": str(path), "spectrum": [4, 5, 6]}
    def export_run(self, path, result): path.write_text(",".join(map(str, result["spectrum"])))
    def new_run(self): self.calls.append("new run")


def make_panel(tmp_path, adapter=None, mode="single", root_provider=None):
    from PySide6.QtWidgets import QWidget
    from control_app.measurement_host.context import ContextFactory
    from control_app.measurement_host.ownership import HardwareCoordinator
    from control_app.measurement_host.presentation import CompactMeasurementPanel
    coordinator = HardwareCoordinator(tmp_path / "instrument.lock")
    context = ContextFactory(ownership=coordinator, save_root_provider=root_provider or (lambda: tmp_path)).for_experiment(
        "fixed_wavenumber_kinetics").for_mode(mode)
    return CompactMeasurementPanel(QWidget(), adapter or Adapter(), context), coordinator


def test_compact_extension_layout_has_no_review_control_and_collapsed_advanced(app, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QCheckBox, QLabel, QWidget
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    panel, coordinator = make_panel(tmp_path)
    reference = PhaseScanWidget()
    try:
        assert not panel.findChildren(QCheckBox)
        assert not hasattr(panel, "review")
        assert not hasattr(panel, "review_checkbox")
        assert panel.splitter.orientation() == Qt.Orientation.Horizontal
        assert panel.splitter.widget(0) is panel.left_panel
        assert panel.splitter.widget(1) is panel.right_panel
        assert panel.control_layout is panel.settings_layout
        assert panel.layout().spacing() == reference.layout().spacing()
        assert panel.layout().contentsMargins() == reference.layout().contentsMargins()
        assert panel.summary_values["Points"].text() == "3"
        assert panel.summary_group.parentWidget() is panel.right_panel
        assert panel.start_button.parentWidget() is panel.left_panel
        assert panel.settings_scroll.widget().layout() is panel.settings_layout
        advanced = QWidget()
        panel.set_advanced_widget(advanced)
        assert not panel.advanced_button.isChecked() and panel.advanced_content.isHidden()
        toggles = []
        panel.advanced_toggled.connect(toggles.append)
        panel.advanced_button.click()
        assert not panel.advanced_content.isHidden() and toggles == [True]
        panel.advanced_button.click()
        assert panel.advanced_content.isHidden() and toggles == [True, False]
        blank = panel.add_blank_action("Acquire blank", lambda: None)
        capability = panel.add_settings_action("Check device", lambda: None)
        plot = QLabel("Scientific plot")
        panel.add_result_widget(plot)
        assert panel.blank_actions_layout.indexOf(blank) == 0
        assert panel.settings_extras_layout.indexOf(capability) == 0
        assert panel.result_layout.indexOf(plot) == 0
        assert panel.adapter.calls == [] and not coordinator.lock_path.exists()
    finally:
        panel.deleteLater()
        reference.deleteLater()


def test_actual_preliminary_compatibility_controls_start_and_survives_harmless_refresh(app, tmp_path):
    panel, _ = make_panel(tmp_path)
    try:
        assert not panel.start_button.isEnabled()
        panel.begin("preliminary")
        wait_for(app, lambda: not panel.command_running())
        preliminary = panel.preliminary
        assert panel.start_button.isEnabled()
        panel.refresh_plan()
        assert panel.preliminary is preliminary and panel.start_button.isEnabled()
        panel.adapter.settings["wavenumber_cm1"] = 1950.
        panel.refresh_plan()
        assert panel.preliminary is preliminary and not panel.start_button.isEnabled()
        assert panel.begin("measurement") is None
        assert len(panel.adapter.calls) == 1
        panel.adapter.settings["wavenumber_cm1"] = 1900.
        panel.refresh_plan()
        assert panel.start_button.isEnabled()
        panel.begin("measurement")
        wait_for(app, lambda: not panel.command_running())
        assert panel.result["spectrum"] == [1, 2, 3]
    finally:
        panel.deleteLater()


def test_method_without_preliminary_requirement_starts_directly_without_approval(app, tmp_path):
    class DirectAdapter(Adapter):
        def validate_preliminary(self, preliminary, plan): return ()
    panel, _ = make_panel(tmp_path, DirectAdapter())
    try:
        assert panel.preliminary is None and panel.start_button.isEnabled()
        panel.start_button.click()
        wait_for(app, lambda: not panel.command_running())
        assert panel.result is not None and len(panel.adapter.calls) == 1
    finally:
        panel.deleteLater()


def test_invalid_plan_capability_action_is_owned_and_custom_abort_reaches_adapter(app, tmp_path):
    adapter = Adapter()
    adapter.settings.update(wavenumber_cm1=None, real=True)
    validations = []
    adapter.validate_operation = lambda kind, plan, preliminary: validations.append((kind, plan)) or ()
    panel, coordinator = make_panel(tmp_path, adapter)
    entered = Event()
    outcomes = []
    panel.operation_finished.connect(lambda kind, outcome: outcomes.append((kind, outcome)))
    def capabilities(snapshot, worker):
        try:
            assert snapshot.plan is None and snapshot.settings["wavenumber_cm1"] is None
            coordinator.assert_owner(snapshot.operation.ownership)
            entered.set()
            while True:
                worker.check_cancelled()
                time.sleep(.002)
        finally:
            panel.context.ownership.release(snapshot.operation.ownership, safe_verified=True, preservation_verified=True)
    try:
        assert panel.plan is None
        with pytest.raises(ValueError, match="valid plan"):
            panel.begin("measurement")
        snapshot = panel.begin_operation("capabilities", capabilities, requires_valid_plan=False)
        assert entered.wait(1)
        assert coordinator.snapshot()["owner"]["operation_id"] == snapshot.operation.run_id
        panel.request_abort("Stop device check")
        wait_for(app, lambda: not panel.command_running())
        assert "Stop device check" in adapter.calls
        assert validations == [("capabilities", None)]
        assert outcomes[-1][0] == "capabilities" and outcomes[-1][1].state == "cancelled"
        assert coordinator.snapshot()["state"] == "free"
        assert panel.plan is None and not panel.start_button.isEnabled()
    finally:
        if panel.command_running():
            panel.request_abort("test cleanup")
            wait_for(app, lambda: not panel.command_running())
        panel.deleteLater()


def test_post_dispatch_error_retains_ownership_and_busy_until_cleanup(app, tmp_path, monkeypatch):
    from control_app.measurement_host.presentation import OperationWorker
    adapter = Adapter()
    adapter.settings["real"] = True
    panel, coordinator = make_panel(tmp_path, adapter)
    gate = Event()
    def acquisition(snapshot, worker):
        try:
            assert gate.wait(2)
            return {"native_path": str(snapshot.operation.output_path)}
        finally:
            panel.context.ownership.release(snapshot.operation.ownership, safe_verified=True, preservation_verified=True)
    original_start = OperationWorker.start
    def start_then_fail(worker):
        original_start(worker)
        assert worker.operation_started.wait(1)
        raise RuntimeError("dispatch wrapper failed after start")
    monkeypatch.setattr(OperationWorker, "start", start_then_fail)
    try:
        with pytest.raises(RuntimeError, match="after start"):
            panel.begin_operation("blank", acquisition)
        assert panel.command_running()
        assert coordinator.snapshot()["state"] == "owned"
        gate.set()
        wait_for(app, lambda: not panel.command_running())
        assert coordinator.snapshot()["state"] == "free"
    finally:
        gate.set()
        if panel.command_running():
            wait_for(app, lambda: not panel.command_running())
        panel.deleteLater()


def test_failed_thread_dispatch_without_entry_releases_only_unstarted_operation(app, tmp_path, monkeypatch):
    from control_app.measurement_host.presentation import OperationWorker
    adapter = Adapter()
    adapter.settings["real"] = True
    panel, coordinator = make_panel(tmp_path, adapter)
    def fail_start(worker):
        raise RuntimeError("Thread could not start")
    monkeypatch.setattr(OperationWorker, "start", fail_start)
    try:
        with pytest.raises(RuntimeError, match="could not start"):
            panel.begin_operation("blank", lambda snapshot, worker: pytest.fail("Must not enter hardware callback"))
        assert not panel.command_running() and panel.worker is None
        assert coordinator.snapshot()["state"] == "free"
    finally:
        panel.deleteLater()


def test_custom_cleanup_failure_keeps_fault_visible_and_does_not_claim_completion(app, tmp_path):
    adapter = Adapter()
    adapter.settings["real"] = True
    panel, coordinator = make_panel(tmp_path, adapter)
    outcomes = []
    panel.outcome_ready.connect(outcomes.append)
    def failed_blank(snapshot, worker):
        try:
            raise InterruptedError("Stopped")
        finally:
            panel.context.ownership.release(snapshot.operation.ownership, safe_verified=False,
                                           preservation_verified=False, detail="Native save and restoration failed")
            raise OSError("Native save and restoration failed")
    try:
        panel.begin_operation("blank", failed_blank)
        wait_for(app, lambda: not panel.command_running())
        assert outcomes[-1].state == "failed"
        assert "Native save and restoration failed" in panel.status.text()
        assert coordinator.snapshot()["state"] == "fault"
        assert panel.result is None
    finally:
        # This fixture has no physical instruments or data; explicitly resolve
        # its deliberate synthetic fault so it does not retain the test lock.
        recovery = coordinator.acquire("manual:recovery", recovery=True)
        coordinator.release(recovery, safe_verified=True, preservation_verified=True)
        panel.deleteLater()


def test_snapshot_isolation_file_actions_and_new_run(app, tmp_path):
    roots = [tmp_path / "first"]
    panel, _ = make_panel(tmp_path, root_provider=lambda: roots[0])
    other, _ = make_panel(tmp_path, mode="dual")
    try:
        panel.begin("preliminary")
        wait_for(app, lambda: not panel.command_running())
        panel.adapter.gate.clear()
        snapshot = panel.begin("measurement")
        roots[0] = tmp_path / "changed"
        panel.output_location_changed(roots[0])
        panel.adapter.sample_records[0]["selection_id"] = "later-selection"
        assert snapshot.operation.sample_records[0]["selection_id"] == "window-1"
        assert snapshot.save_root == tmp_path / "first"
        assert panel.snapshot is snapshot
        assert panel.save_plan_button.toolTip() == str(roots[0])
        assert not panel.settings_widget.isEnabled() and other.settings_widget.isEnabled()
        assert other.preliminary is None and other.result is None
        panel.adapter.gate.set()
        wait_for(app, lambda: not panel.command_running())
        plan_path = tmp_path / "settings.plan"
        panel.save_plan(plan_path)
        wait_for(app, lambda: not panel.command_running())
        panel.load_plan(plan_path)
        wait_for(app, lambda: not panel.command_running())
        assert panel.start_button.isEnabled()  # Compatible data is still usable.
        panel.load_run(tmp_path / "retained_native")
        wait_for(app, lambda: not panel.command_running())
        target = tmp_path / "data.csv"
        panel.export_run(target)
        wait_for(app, lambda: not panel.command_running())
        assert target.read_text() == "4,5,6"
        panel.new_run()
        assert panel.preliminary is panel.result is panel.snapshot is None
        assert not panel.start_button.isEnabled() and other.adapter.calls == []
    finally:
        panel.adapter.gate.set()
        if panel.command_running():
            wait_for(app, lambda: not panel.command_running())
        panel.deleteLater()
        other.deleteLater()
