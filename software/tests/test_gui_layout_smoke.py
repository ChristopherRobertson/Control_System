import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.mark.parametrize("discovery_case", ("installed", "empty", "optional_pair"))
def test_seven_tab_gui_shell_instantiates_without_hardware(monkeypatch, tmp_path, discovery_case):
    pytest.importorskip("PySide6")
    from importlib import import_module
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import QApplication, QWidget

    from control_app.measurement_host import ModuleDescriptor, TabHandle
    from control_app.measurement_host.ownership import HardwareCoordinator
    from control_app.measurement_host.registry import DiscoveryResult
    from control_app.ui.contracts import blocked_handler
    from control_app.ui import main_window

    hardware_attempts = []

    def reject_hardware(*args, **kwargs):
        # Registration isolates optional errors, so also retain attempts and
        # assert outside construction that none was silently caught there.
        hardware_attempts.append((args, kwargs))
        raise AssertionError("Shell construction must not construct or acquire hardware")

    for module_name, class_name in (
        ("mircat_service", "MircatService"), ("hf2li_service", "HF2LIService"),
        ("picoscope_service", "PicoScopeService"), ("t660_service", "T660Service"),
        ("ell15_iris_service", "ELL15IrisService"),
    ):
        service = getattr(import_module(f"control_app.devices.{module_name}"), class_name)
        monkeypatch.setattr(service, "__init__", reject_hardware)
    monkeypatch.setattr(main_window, "installed_device_factories", reject_hardware)
    coordinator = HardwareCoordinator(tmp_path / "smoke_instrument.lock")
    monkeypatch.setattr(coordinator, "acquire", reject_hardware)
    handler = blocked_handler("automated smoke test; no hardware")
    handler.coordinator = coordinator

    if discovery_case != "installed":
        class OptionalWidget(QWidget):
            state_changed = Signal(bool)

        def create_pair(context):
            pair = []
            for mode in ("single", "dual"):
                scoped = context.for_mode(mode)
                widget = OptionalWidget()
                pair.append(TabHandle(
                    scoped.instance_id, f"Smoke Optional {mode}", widget,
                    lambda: False, lambda: (), lambda reason: None,
                    lambda path: None, lambda change: None, widget.state_changed,
                ))
            return pair

        descriptors = (() if discovery_case == "empty" else (
            ModuleDescriptor(1, "smoke_optional_measurement", 10, create_pair),
        ))
        monkeypatch.setattr(main_window, "discover_modules", lambda: DiscoveryResult(descriptors, ()))

    app = QApplication.instance() or QApplication([])
    window = main_window.ControlSystemMainWindow(handler, persist_settings=False)
    try:
        app.processEvents()
        assert window.windowTitle() == "IR Spectroscope Control System"
        assert window.save_location.objectName() == "save_location"
        handles = window.measurement_lifecycle.handles
        assert [handle.instance_id for handle in handles[:2]] == ["phase_scan:single", "phase_scan:dual"]
        assert handles[0].widget is window.phase_scan_widget
        assert handles[1].widget is window.dual_detector_phase_scan_widget
        legacy_tabs = [
            ("Phase Scan", window.phase_scan_widget),
            ("DD Phase Scan", window.dual_detector_phase_scan_widget),
            ("MIRcat", window.mircat_widget),
            ("T660-1", window.t660_widget),
            ("Nd:YAG", window.ndyag_widget),
            ("OPO Iris", window.iris_widget),
            ("Plotter", window.scan_plotter_widget),
        ]
        # Accepted optional pairs are inserted before the two phase tabs. Use
        # their actual handles, since invalid optional pairs may be excluded.
        expected_tabs = [(handle.title, handle.widget) for handle in handles[2:] + handles[:2]] + legacy_tabs[2:]
        assert window.tabs.count() == len(expected_tabs)
        for index, (title, widget) in enumerate(expected_tabs):
            assert window.tabs.tabText(index) == title
            assert window.tabs.widget(index) is widget
            window.tabs.tabBar().setCurrentIndex(index)
            assert window.tabs.currentWidget() is widget
        assert not hasattr(window, "tab_selector")
        assert window.findChild(QWidget, "workspace_tab_selector") is None
        assert window.tabs.usesScrollButtons()
        legacy_indices = [window.tabs.indexOf(widget) for _, widget in legacy_tabs]
        assert legacy_indices == sorted(set(legacy_indices))
        assert [window.tabs.tabText(index) for index in legacy_indices] == [title for title, _ in legacy_tabs]
        window.tabs.tabBar().setCurrentIndex(window.tabs.count() - 1)
        assert window.tabs.currentWidget() is window.scan_plotter_widget
        window.tabs.tabBar().setCurrentIndex(0)
        assert window.tabs.currentWidget() is expected_tabs[0][1]
        if discovery_case != "installed":
            assert window.registration_issues == ()
            assert window.tabs.count() == (7 if discovery_case == "empty" else 9)
            assert [handle.instance_id for handle in handles[2:]] == (
                [] if discovery_case == "empty" else [
                    "smoke_optional_measurement:single", "smoke_optional_measurement:dual",
                ])
        assert not hasattr(window, "experiment_builder_widget")
        assert not hasattr(window, "workflow_selector_widget")
        assert window.iris_widget.current_diameter_label.text() == "-- mm"
        assert window.iris_widget.target_diameter.objectName() == "iris_target_diameter"
        app.processEvents()
        assert hardware_attempts == []
        assert not coordinator.lock_path.exists()
    finally:
        window.deleteLater()
        app.processEvents()


def test_iris_tab_refreshes_and_applies_direct_entry_asynchronously():
    import time

    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QPushButton

    from control_app.ui.contracts import WorkflowResult
    from control_app.ui.widgets.iris_widget import IrisWidget

    app = QApplication.instance() or QApplication([])
    commands = []

    def handler(command):
        commands.append(command)
        diameter = float(command.parameters.get("diameter_mm", 7.4))
        return WorkflowResult(
            status="complete",
            message="test readback",
            data={
                "state": {
                    "current_diameter_mm": diameter,
                    "identity": "ELL15 S/N 11500020",
                    "configured_range": "1.00-11.50 mm",
                }
            },
        )

    def wait_for_idle(widget):
        deadline = time.monotonic() + 2
        while widget.command_running() and time.monotonic() < deadline:
            app.processEvents()
        app.processEvents()
        assert not widget.command_running()

    widget = IrisWidget(handler)
    widget.show()
    app.processEvents()
    wait_for_idle(widget)
    assert commands[0].command == "opo_iris.refresh_status"
    assert widget.current_diameter_label.text() == "7.40 mm"

    widget.target_diameter.setText("6.25")
    widget.findChild(QPushButton, "iris_set_diameter").click()
    wait_for_idle(widget)
    assert commands[-1].parameters["diameter_mm"] == "6.25"
    assert widget.current_diameter_label.text() == "6.25 mm"
    widget.close()
    widget.deleteLater()
    app.processEvents()
