"""The completed application must actually install all six delivered modules.

Optional/dummy package behavior belongs to the host compatibility tests. This
integration check deliberately fails if one of the six bundled packages is
missing or silently rejected by discovery/widget construction.
"""
from importlib import import_module
import os

import pytest


TITLES = {
    "steady_state_slow_scan": ("Slow Scan", "DD Slow Scan"),
    "fixed_wavenumber_kinetics": ("Fixed Wavenumber", "DD Fixed Wavenumber"),
    "nanosecond_stroboscopy": ("Nanosecond Stroboscopy", "DD Nanosecond Stroboscopy"),
    "microsecond_stroboscopy": ("Microsecond Stroboscopy", "DD Microsecond Stroboscopy"),
    "single_pump_scan_burst": ("Single Scan Phase Delay", "DD Single Scan Phase Delay"),
    "repeated_rapid_scan": ("Rapid Scan Phase Delay", "DD Rapid Scan Phase Delay"),
}


def test_all_six_delivered_modules_install_together_without_hardware(monkeypatch, tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from control_app.measurement_host.ownership import HardwareCoordinator
    from control_app.measurement_host.presentation import CompactMeasurementPanel
    from control_app.measurement_host.registry import discover_modules
    from control_app.ui import main_window
    from control_app.ui.contracts import blocked_handler

    attempts = []

    def reject_hardware(*args, **kwargs):
        attempts.append((args, kwargs))
        raise AssertionError("Installed-module discovery and construction must not access hardware")

    # Imports of these service definitions are SDK-free. Catch both direct
    # construction and injected factory usage, even if registry isolation catches
    # the raised exception and would otherwise silently omit the broken pair.
    for module_name, class_name in (
        ("mircat_service", "MircatService"), ("hf2li_service", "HF2LIService"),
        ("picoscope_service", "PicoScopeService"), ("t660_service", "T660Service"),
        ("ell15_iris_service", "ELL15IrisService"),
    ):
        monkeypatch.setattr(getattr(import_module(f"control_app.devices.{module_name}"), class_name),
                            "__init__", reject_hardware)
    monkeypatch.setattr(main_window, "installed_device_factories", reject_hardware)
    coordinator = HardwareCoordinator(tmp_path / "installed_modules.lock")
    monkeypatch.setattr(coordinator, "acquire", reject_hardware)
    handler = blocked_handler("Installed-module integration test; no hardware")
    handler.coordinator = coordinator

    discovery = discover_modules()
    assert discovery.issues == (), discovery.issues
    assert {descriptor.experiment_id for descriptor in discovery.descriptors} == set(TITLES)
    assert len(discovery.descriptors) == 6
    app = QApplication.instance() or QApplication([])
    # Use the actual app's default discovery path, not synthetic registration.
    window = main_window.ControlSystemMainWindow(handler, persist_settings=False)
    try:
        app.processEvents()
        assert window.registration_issues == (), window.registration_issues
        handles = window.measurement_lifecycle.handles
        features = {handle.instance_id: handle for handle in handles if not handle.instance_id.startswith("phase_scan:")}
        expected = {f"{experiment}:{mode}": titles[index]
                    for experiment, titles in TITLES.items() for index, mode in enumerate(("single", "dual"))}
        assert set(features) == set(expected)
        assert len(handles) == 14 and len(features) == 12
        assert window.tabs.count() == 19
        assert not hasattr(window, "tab_selector")
        assert window.detector_mode.currentData() == "single"
        assert [window.tabs.tabText(index) for index in range(12, 14)] == ["Phase Scan", "DD Phase Scan"]
        assert [window.tabs.tabText(index) for index in range(12) if window.tabs.isTabVisible(index)] == [titles[0] for titles in TITLES.values()]
        assert [window.tabs.tabText(index) for index in range(14, 19)] == ["MIRcat", "T660-1", "Nd:YAG", "OPO Iris", "Plotter"]
        for identity, title in expected.items():
            handle = features[identity]
            assert handle.title == title
            index = window.tabs.indexOf(handle.widget)
            assert 0 <= index < 12 and window.tabs.tabText(index) == title
            window.tabs.setCurrentIndex(index)
            assert window.tabs.currentWidget() is handle.widget
            assert window.detector_mode.currentData() == identity.rsplit(":", 1)[1]
            assert window.tabs.isTabVisible(index)
            assert not handle.command_running()

        widgets = [handle.widget for handle in features.values()]
        adapters = [widget.adapter for widget in widgets]
        contexts = [widget.context for widget in widgets]
        assert len({id(widget) for widget in widgets}) == 12
        assert len({id(adapter) for adapter in adapters}) == 12
        assert len({id(context) for context in contexts}) == 12
        assert len({id(context.preferences) for context in contexts}) == 12
        for widget, adapter in zip(widgets, adapters):
            assert isinstance(widget, CompactMeasurementPanel)
            assert not hasattr(widget, "review")
            assert not hasattr(widget, "review_checkbox")
            assert not hasattr(widget, "advanced_button")
            assert not widget.advanced_content.isHidden()
            assert not widget.advanced_content.isCheckable()
            # Operator pages default to installed instruments. Test simulators
            # remain explicit backend fixtures, never an accidental UI default.
            settings = adapter.read_settings()
            assert adapter.hardware_required("measurement", settings), widget.context.instance_id
            assert adapter.hardware_required("preliminary", settings), widget.context.instance_id
        for context in contexts:
            assert context.preferences.namespace == f"measurements/{context.experiment_id}/{context.mode}/v1/"
            context.preferences.setValue("installed_module_probe", {"instance_id": context.instance_id})
        for context in contexts:
            assert context.preferences.value("installed_module_probe") == {"instance_id": context.instance_id}

        # Runners are deliberately lazy. No feature may own an active worker or
        # share a mutable runner before an explicit operation is requested.
        for adapter, context in zip(adapters, contexts):
            assert adapter.context is context
            for runner_attribute in ("runner", "active_runner", "_runner"):
                assert getattr(adapter, runner_attribute, None) is None
        assert window.phase_scan_widget.runner is not window.dual_detector_phase_scan_widget.runner
        app.processEvents()
        assert window.live_worker_blockers() == []
        assert attempts == []
        assert not coordinator.lock_path.exists()
    finally:
        window.deleteLater()
        app.processEvents()
