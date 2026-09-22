"""Shared startup discovery, automatic defaults and accepted HF2LI overrides."""
import time

import pytest


def test_all_measurement_pages_receive_startup_choices_without_check_buttons(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QPushButton
    from control_app.measurement_host import application_session as module
    from control_app.measurement_host.application_session import ApplicationDeviceSession
    from control_app.measurement_host.settings_sections import HF2LIValueInput
    from control_app.measurement_host.ownership import HardwareCoordinator
    from control_app.ui.main_window import ControlSystemMainWindow
    from control_app.workflows.state_machine import WorkflowStateMachine
    from test_application_device_session import Device, finish
    app = QApplication.instance() or QApplication([])
    owner = HardwareCoordinator(tmp_path / "owner.lock")
    devices = {key: Device(key) for key in ("mircat", "hf2li", "picoscope", "t660_1", "t660_2", "opo_iris")}
    session = ApplicationDeviceSession(owner, {}, factories={key: lambda configuration, d=d: d for key, d in devices.items()},
        capability_cache_path=tmp_path / "choices.json")
    monkeypatch.setattr(module, "ApplicationDeviceSession", lambda *args, **kwargs: session)
    window = ControlSystemMainWindow(WorkflowStateMachine(operator="test", coordinator=owner, run_dir=tmp_path / "runs"), persist_settings=False, connect_devices_on_startup=True)
    try:
        deadline = time.monotonic() + 20
        while not session.ready or window._device_startup_worker is not None:
            app.processEvents()
            assert time.monotonic() < deadline
            time.sleep(.005)
        app.processEvents()
        assert devices["hf2li"].calls.count("discover") == 1
        before = {key: list(device.calls) for key, device in devices.items()}
        checked = 0
        for handle in window.measurement_lifecycle.handles:
            panel = handle.widget
            assert not any("check device" in b.text().lower() or "check connected device" in b.text().lower()
                           or "read connected settings" in b.text().lower() for b in panel.findChildren(QPushButton))
            if handle.instance_id.startswith("phase_scan:"):
                controls = list(panel.override_inputs.values())
            else:
                controls = panel.findChildren(HF2LIValueInput)
            assert len(controls) == (6 if handle.instance_id.endswith(":dual") else 3), handle.instance_id
            assert all(not control.isEditable() and control.currentIndex() == 0 and control.count() > 1 for control in controls), handle.instance_id
            control = controls[0]
            control.setCurrentIndex(1)
            assert control.currentIndex() == 1
            assert all(other.currentIndex() == 0 for other in controls[1:])
            control.setCurrentIndex(0)
            checked += 1
        assert checked == 12
        assert before == {key: device.calls for key, device in devices.items()}
    finally:
        window.safe_shutdown_completed = True
        window.deleteLater()
        finish(session)


def test_supported_automatic_selection_tracks_interval_and_keeps_independent_overrides():
    from control_app.measurement_host.hf2_selection import select_supported
    profile = {"orders": [1, 4], "timeconstants_by_order": {1: [.00001, .001, .1], 4: [.00001, .001, .1]},
               "rates_sps": [100., 10000., 200000.]}
    fast = select_supported(profile, time_scale_s=.1)
    slow = select_supported(profile, time_scale_s=100.)
    assert fast["timeconstant_s"] < slow["timeconstant_s"]
    assert fast["rate_sps"] > slow["rate_sps"]
    explicit = select_supported(profile, time_scale_s=.1, overrides={"order": 1})
    assert explicit["order"] == 1 and explicit["rate_sps"] in profile["rates_sps"]
    with pytest.raises(ValueError, match="not accepted"):
        select_supported(profile, time_scale_s=.1, overrides={"rate_sps": 12345.})
