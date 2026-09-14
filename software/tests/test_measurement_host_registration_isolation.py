"""Optional title and callback failures cannot prevent the shell from opening."""
from dataclasses import replace
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QWidget

from control_app import paths
from control_app.measurement_host import ContextFactory, ModuleDescriptor, TabHandle
from control_app.measurement_host.ownership import HardwareCoordinator
from control_app.measurement_host.registry import create_registered_tabs
from control_app.ui.contracts import blocked_handler
from control_app.ui.main_window import ControlSystemMainWindow


class FixturePage(QWidget):
    changed = Signal(bool)

    def __init__(self, context):
        super().__init__()
        self.context = context
        self.destinations = []

    def handle(self, title):
        return TabHandle(self.context.instance_id, title, self, lambda: False,
            lambda: (), lambda reason: None, self.destinations.append,
            lambda change: None, self.changed)


def pair(context):
    return tuple(FixturePage(context.for_mode(mode)).handle(f"Fixture {mode}")
                 for mode in ("single", "dual"))


@pytest.fixture
def private_shell_environment(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(paths, "RUN_ROOT", tmp_path / "runs")
    monkeypatch.setattr(paths, "_selected_save_location", None)
    handler = blocked_handler("No hardware in optional registration tests")
    handler.coordinator = HardwareCoordinator(tmp_path / "private-owner.lock")
    yield app, handler
    app.processEvents()
    assert not paths.RUN_ROOT.exists()
    assert not handler.coordinator.lock_path.exists()


@pytest.mark.parametrize("unsafe_title", ["Fixture: dual", "CON", "../Fixture", "Fixture "])
def test_unsafe_optional_title_rejects_whole_pair_before_publication(private_shell_environment,
                                                                  monkeypatch, unsafe_title):
    _, handler = private_shell_environment

    def unsafe_pair(context):
        single, dual = pair(context)
        return single, replace(dual, title=unsafe_title)

    unsafe = ModuleDescriptor(1, "unsafe_fixture", 0, unsafe_pair)
    healthy = ModuleDescriptor(1, "healthy_fixture", 1, pair)
    factory = ContextFactory(ownership=handler.coordinator, preference_backend={})

    def forbidden(*args, **kwargs):
        raise AssertionError("Registration must not inspect or create filesystem paths")

    with monkeypatch.context() as guard:
        for method in ("mkdir", "exists", "stat", "resolve"):
            guard.setattr(Path, method, forbidden)
        result = create_registered_tabs((unsafe, healthy), factory)
    try:
        assert [item.instance_id for item in result.handles] == [
            "healthy_fixture:single", "healthy_fixture:dual"]
        assert [item.title for item in result.handles] == ["Fixture single", "Fixture dual"]
        assert len(result.issues) == 1
        assert result.issues[0].module == "unsafe_fixture"
        assert "exact Windows folder name" in result.issues[0].message
    finally:
        for item in result.handles:
            item.widget.deleteLater()


def test_unsafe_optional_pair_does_not_block_legacy_shell(private_shell_environment):
    _, handler = private_shell_environment

    def unsafe_pair(context):
        return tuple(replace(item, title="Fixture: " + item.instance_id.rsplit(":", 1)[1])
                     for item in pair(context))

    window = ControlSystemMainWindow(handler, module_discovery=(
        ModuleDescriptor(1, "unsafe_fixture", 0, unsafe_pair),))
    window._save_timer.stop()
    try:
        assert window.tabs.count() == 7
        assert len(window.measurement_lifecycle.handles) == 2
        assert len(window.registration_issues) == 1
        assert "exact Windows folder name" in window.host_status.text()
        window.set_detector_mode("dual")
        assert window.tabs.currentWidget() is window.dual_detector_phase_scan_widget
    finally:
        window.deleteLater()


@pytest.mark.parametrize("failing_callback", ["command_running", "output_location_changed"])
def test_optional_runtime_callback_failure_does_not_block_other_destinations(
        private_shell_environment, failing_callback):
    app, handler = private_shell_environment

    def throwing_pair(context):
        single, dual = pair(context)

        def fail(*args):
            raise RuntimeError("Injected optional callback failure")

        return replace(single, **{failing_callback: fail}), dual

    window = ControlSystemMainWindow(handler, module_discovery=(
        ModuleDescriptor(1, "throwing_fixture", 0, throwing_pair),))
    window._save_timer.stop()
    try:
        assert window.tabs.count() == 9
        assert window.registration_issues == ()
        window._update_save_enabled()
        assert "Injected optional callback failure" in window.host_status.text()
        healthy = next(item for item in window.measurement_lifecycle.handles
                       if item.instance_id == "throwing_fixture:dual")
        assert healthy.widget.destinations == [paths.default_tab_save_location(healthy.title)]
        window.set_detector_mode("dual")
        app.processEvents()
        assert window.tabs.currentWidget() is healthy.widget
    finally:
        window.deleteLater()


def test_manual_notification_failure_does_not_block_measurement_destinations(private_shell_environment):
    _, handler = private_shell_environment

    def fail(path):
        raise RuntimeError("Injected manual destination failure")

    handler.output_location_changed = fail
    window = ControlSystemMainWindow(handler, module_discovery=(
        ModuleDescriptor(1, "healthy_fixture", 0, pair),))
    window._save_timer.stop()
    try:
        window._update_save_enabled()
        assert "Injected manual destination failure" in window.host_status.text()
        healthy = [item for item in window.measurement_lifecycle.handles
                   if item.instance_id.startswith("healthy_fixture:")]
        assert len(healthy) == 2
        for item in healthy:
            assert item.widget.destinations == [paths.default_tab_save_location(item.title)]
        recovered = []
        handler.output_location_changed = recovered.append
        window._update_save_enabled()
        assert recovered == [Path(window.save_location.text())]
        assert paths.get_save_location() == recovered[0]
        window._update_save_enabled()
        assert len(recovered) == 1
        for item in healthy:
            assert item.widget.destinations == [paths.default_tab_save_location(item.title)]
    finally:
        window.deleteLater()
