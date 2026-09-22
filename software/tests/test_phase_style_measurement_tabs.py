"""Phase-style ownership, persistence and compact rendering without device I/O."""
from pathlib import Path
import pytest


@pytest.mark.parametrize("mode", ["single", "dual"])
@pytest.mark.parametrize("name, class_name", [
    ("fixed_wavenumber_kinetics", "FixedPointPanel"),
    ("microsecond_stroboscopy", "MicrosecondPanel"),
    ("nanosecond_stroboscopy", "NanosecondPanel"),
    ("repeated_rapid_scan", "RepeatedRapidScanPanel"),
    ("steady_state_slow_scan", "SlowScanPanel"),
])
def test_missing_start_updates_derived_settings_while_typing(app, tmp_path, mode, name, class_name):
    from importlib import import_module
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from control_app.measurement_host import ContextFactory
    cls = getattr(import_module(f"control_app.measurement_modules.{name}.widgets"), class_name)
    context = ContextFactory(preference_backend={}, save_root_provider=lambda: tmp_path).for_experiment(name).for_mode(mode)
    panel = cls(context)
    try:
        editor = panel.settings_widget
        control = editor.start if name == "steady_state_slow_scan" else editor.lasers.inputs["start_wavenumber_cm1"]
        control.setValue(1946)
        control.lineEdit().selectAll()
        QTest.keyClick(control.lineEdit(), Qt.Key.Key_Backspace)
        assert "Set Start Wavenumber to proceed" in "\n".join(v.text() for v in panel.summary_values.values())
        assert panel.plan is None
        QTest.keyClicks(control.lineEdit(), "1946")
        assert "Set Start Wavenumber to proceed" not in "\n".join(v.text() for v in panel.summary_values.values())
    finally:
        panel.deleteLater()


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont, QFontDatabase
    app = QApplication.instance() or QApplication([])
    previous = app.font()
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    app.setFont(QFont("Segoe UI", 9))
    yield app
    app.processEvents()
    app.setFont(previous)


def group_title(widget):
    from PySide6.QtWidgets import QGroupBox
    while widget is not None:
        widget = widget.parentWidget()
        if isinstance(widget, QGroupBox):
            return widget.title()


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_device_ownership_and_independent_cached_choices(app, tmp_path, mode):
    from control_app.measurement_host import ContextFactory
    from control_app.measurement_modules.fixed_wavenumber_kinetics.widgets import FixedPointPanel
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondPanel
    from control_app.measurement_modules.nanosecond_stroboscopy.widgets import NanosecondPanel
    calls = []
    def forbidden(**kwargs):
        calls.append(kwargs)
        raise AssertionError("Presentation must not construct devices")
    factory = ContextFactory(preference_backend={}, save_root_provider=lambda: tmp_path,
        real_device_factories={key: forbidden for key in ("hf2li", "mircat", "t660_1", "t660_2")})
    panels = [FixedPointPanel(factory.for_experiment("fixed_wavenumber_kinetics").for_mode(mode)),
              MicrosecondPanel(factory.for_experiment("microsecond_stroboscopy").for_mode(mode)),
              NanosecondPanel(factory.for_experiment("nanosecond_stroboscopy").for_mode(mode))]
    fixed, micro, nano = panels
    try:
        assert group_title(fixed.editor.fields["probe_rate_hz"]) == "MIRcat Settings"
        assert group_title(fixed.editor.fields["probe_width_ns"]) == "MIRcat Settings"
        assert group_title(fixed.editor.fields["shot_delay_s"]) == "Kinetics Settings"
        assert group_title(micro.settings_widget._controls["timing.probe_rate_hz"][0]) == "MIRcat Settings"
        assert group_title(micro.settings_widget._controls["timing.probe_width_ns"][0]) == "MIRcat Settings"
        assert group_title(micro.settings_widget._controls["response.integration_aperture_s"][0]) == "Microsecond Stroboscopy Settings"
        fixed.adapter.live_readbacks = {"supported": {"sample": {"rate_sps": [1000., 2000.]}}}
        fixed.refresh_plan()
        fixed.editor.fields["sample_rate_sps"].setCurrentText("2000")
        assert fixed.editor.values()["settings"]["sample_rate_sps"] == 2000
        assert fixed.editor.values()["settings"]["sample_timeconstant_s"] is None
        micro.adapter.capabilities = {"orders": [1, 2], "rates_sps": [1000., 2000.]}
        micro.refresh_plan()
        choice = micro.settings_widget.override_modes["response.hf2_order"]
        choice.setCurrentIndex(choice.findData(2))
        assert set(micro.settings_widget.read_settings()["manual_overrides"]) == {"response.hf2_order", *micro.settings_widget.MIRCAT_FIELDS}
        assert micro.settings_widget.read_settings()["response"]["hf2_order"] == 2
        for panel in panels:
            panel.show(); app.processEvents()
            panel.hide(); panel.show(); app.processEvents()
            assert not panel.command_running()
        assert calls == []
    finally:
        for panel in panels:
            panel.hide(); panel.deleteLater()


@pytest.mark.parametrize("mode", ["single", "dual"])
@pytest.mark.parametrize("experiment", ["microsecond_stroboscopy", "nanosecond_stroboscopy"])
def test_run_label_roundtrip_preserves_metadata_and_compatibility(app, tmp_path, experiment, mode):
    from control_app.measurement_host import ContextFactory
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondPanel
    from control_app.measurement_modules.nanosecond_stroboscopy.widgets import NanosecondPanel
    context = ContextFactory(preference_backend={}, save_root_provider=lambda: tmp_path).for_experiment(experiment).for_mode(mode)
    panel = (MicrosecondPanel(context, hardware=False) if experiment.startswith("micro") else
             NanosecondPanel(context, execution_mode="simulation"))
    try:
        initial = panel.adapter.read_settings()
        panel.settings_widget.run_label.setText("cell 7 repeat B")
        requested = panel.adapter.read_settings()
        plan = panel.adapter.make_plan(requested)
        path = tmp_path / "plan.json"
        panel.adapter.save_plan(path, requested, plan)
        loaded = panel.adapter.load_plan(path)
        panel.adapter.apply_settings(loaded)
        assert panel.settings_widget.run_label.text() == "cell 7 repeat B"
        if experiment.startswith("micro"):
            from control_app.measurement_modules.microsecond_stroboscopy.planner import acquisition_signature
            assert acquisition_signature(initial) == acquisition_signature(panel.adapter.read_settings())
            # Older plans lacking the optional label still load.
            initial.pop("run_label", None)
            panel.adapter.apply_settings(initial)
        else:
            from control_app.measurement_modules.nanosecond_stroboscopy.persistence import acquisition_conflicts
            assert acquisition_conflicts(initial, requested) == []
            assert requested["metadata"]["run_label"] == "cell 7 repeat B"
            assert requested["overrides"] == initial["overrides"]
            panel.adapter.apply_settings(initial)
        assert panel.settings_widget.run_label.text() == ""
    finally:
        panel.deleteLater()


def test_all_target_pages_fit_shell_and_keep_actions_outside_scroll(app, tmp_path, monkeypatch):
    from PySide6.QtCore import QPoint, QRect
    from control_app.ui.contracts import blocked_handler
    from control_app.ui.main_window import ControlSystemMainWindow
    from control_app.measurement_host.ownership import HardwareCoordinator
    def forbidden(*args, **kwargs):
        raise AssertionError("Tab activation/edit attempted hardware ownership")
    monkeypatch.setattr(HardwareCoordinator, "acquire", forbidden)
    handler = blocked_handler("UI layout test")
    handler.coordinator = HardwareCoordinator(tmp_path / "lock")
    window = ControlSystemMainWindow(handler, persist_settings=False)
    try:
        window.resize(1100, 780); window.show(); app.processEvents()
        for handle in window.measurement_lifecycle.handles:
            experiment, mode = handle.instance_id.split(":")
            if experiment not in ("fixed_wavenumber_kinetics", "microsecond_stroboscopy", "nanosecond_stroboscopy", "repeated_rapid_scan"):
                continue
            window.set_detector_mode(mode)
            window.tabs.setCurrentWidget(handle.widget)
            app.processEvents()
            panel = handle.widget
            assert (window.width(), window.height()) == (1100, 780)
            assert window.workspace_scroll.verticalScrollBar().maximum() == 0, handle.instance_id
            assert window.workspace_scroll.horizontalScrollBar().maximum() == 0
            assert panel.settings_scroll.horizontalScrollBar().maximum() == 0
            for control in (panel.preliminary_button, panel.start_button, panel.abort_button, panel.new_run_button):
                assert not panel.settings_scroll.isAncestorOf(control)
                assert panel.rect().contains(QRect(control.mapTo(panel, QPoint()), control.size()))
            panel.settings_scroll.ensureWidgetVisible(panel.load_plan_button)
            app.processEvents()
            viewport = panel.settings_scroll.viewport()
            assert viewport.rect().contains(QRect(panel.load_plan_button.mapTo(viewport, QPoint()), panel.load_plan_button.size()))
            panel.settings_scroll.verticalScrollBar().setValue(0)
            app.processEvents()
            assert window.grab().save(str(tmp_path / f"{experiment}-{mode}-1100x780.png"))
    finally:
        window.hide(); window.deleteLater()


def test_connected_session_edits_use_cached_readbacks_without_io(app, tmp_path, monkeypatch):
    from test_application_device_session import Device, finish
    from control_app.measurement_host.application_session import ApplicationDeviceSession
    from control_app.measurement_host.ownership import HardwareCoordinator
    from control_app.measurement_host import application_session as module
    from control_app.ui.main_window import ControlSystemMainWindow
    from control_app.workflows.state_machine import WorkflowStateMachine
    owner = HardwareCoordinator(tmp_path / "connected.lock")
    devices = {name: Device(name) for name in ("mircat", "hf2li", "picoscope", "t660_1", "t660_2", "opo_iris")}
    session = ApplicationDeviceSession(owner, {}, factories={name: lambda configuration, device=device: device for name, device in devices.items()},
        capability_cache_path=tmp_path / "capabilities.json")
    monkeypatch.setattr(module, "ApplicationDeviceSession", lambda *args, **kwargs: session)
    handler = WorkflowStateMachine(operator="test", coordinator=owner, run_dir=tmp_path / "run")
    window = ControlSystemMainWindow(handler, persist_settings=False)
    try:
        window.device_session = session
        session.start()
        window._publish_device_settings()
        before = {name: list(device.calls) for name, device in devices.items()}
        for handle in window.measurement_lifecycle.handles:
            experiment, mode = handle.instance_id.split(":")
            panel = handle.widget
            if experiment == "fixed_wavenumber_kinetics":
                assert panel.adapter.live_readbacks["source_kind"] == "connected_readbacks"
                panel.editor.fields["sample_rate_sps"].setText("230263.15789473685")
            elif experiment == "microsecond_stroboscopy":
                assert panel.adapter.capabilities["verified"]
                panel.settings_widget.override_modes["response.hf2_order"].setCurrentIndex(1)
                panel.settings_widget._controls["response.hf2_order"][0].setValue(4)
            elif experiment == "nanosecond_stroboscopy":
                assert panel.adapter.capabilities["filter_order"] == 4
                panel.settings_widget.override_inputs["filter_order"].setCurrentText("4")
            else:
                continue
            window.set_detector_mode(mode)
            window.tabs.setCurrentWidget(panel)
            app.processEvents()
            assert not panel.command_running()
        assert before == {name: device.calls for name, device in devices.items()}
    finally:
        window.safe_shutdown_completed = True
        window.hide(); window.deleteLater()
        finish(session)


def test_shared_axis_controls_select_axes_restore_auto_and_preserve_inversion(app):
    from control_app.measurement_host.presentation import PlotPanel
    class Renderer:
        def draw(self, figure, result):
            first, second = figure.subplots(2)
            for axis in (first, second):
                axis.plot([1900, 1950, 2000], [1, 2, 3])
                axis.invert_xaxis()
    panel = PlotPanel(Renderer())
    try:
        panel.set_result({})
        limits = panel.axis_limits
        limits.axes_choice.setCurrentIndex(1)
        first, second = panel.figure.axes
        first_limits = first.get_xlim()
        for key, value in dict(xmin=1920, xmax=1980, ymin=1.2, ymax=2.8).items():
            limits.inputs[key].setText(str(value))
        limits.apply()
        assert second.get_xlim() == (1980, 1920)
        assert first.get_xlim() == first_limits
        limits.auto_button.click()
        assert second.xaxis_inverted()
        assert min(second.get_xlim()) < 1900 and max(second.get_xlim()) > 2000
        assert first.get_xlim() == first_limits
    finally:
        panel.deleteLater()


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_exact_phase_laser_sections_and_inclusive_step_grid(app, tmp_path, mode):
    from PySide6.QtWidgets import QGroupBox, QFormLayout
    from control_app.measurement_host import ContextFactory
    from control_app.measurement_modules.fixed_wavenumber_kinetics.widgets import FixedPointPanel
    from control_app.measurement_modules.microsecond_stroboscopy.widgets import MicrosecondPanel
    from control_app.measurement_modules.nanosecond_stroboscopy.widgets import NanosecondPanel
    from control_app.measurement_modules.repeated_rapid_scan.widgets import RepeatedRapidScanPanel
    factory = ContextFactory(preference_backend={}, save_root_provider=lambda: tmp_path)
    modules = [("fixed_wavenumber_kinetics", FixedPointPanel), ("microsecond_stroboscopy", MicrosecondPanel),
               ("nanosecond_stroboscopy", NanosecondPanel), ("repeated_rapid_scan", RepeatedRapidScanPanel)]
    for name, cls in modules:
        panel = cls(factory.for_experiment(name).for_mode(mode))
        try:
            editor = panel.settings_widget
            lasers = editor.lasers
            groups = {group.title(): group for group in panel.findChildren(QGroupBox)}
            assert "Nd:YAG Settings" in groups and "MIRcat Settings" in groups and "HF2LI Settings" in groups
            assert not any("T660" in title or "MIRcat +" in title for title in groups)
            def labels(title):
                form = groups[title].layout()
                return [form.itemAt(i, QFormLayout.ItemRole.LabelRole).widget().text() for i in range(form.rowCount())]
            assert labels("Nd:YAG Settings") == ["Repetition Rate", "FIRE - Q-SWITCH Delay", "Wavelength"]
            assert labels("MIRcat Settings") == ["Start", "Stop", "Scan Speed" if name == "repeated_rapid_scan" else "Step Size", "Repetition Rate", "Pulse Width", "Current"]
            lasers.inputs["pump_repetition_rate_hz"].setValue(2)
            lasers.inputs["fire_to_qswitch_us"].setValue(300)
            lasers.inputs["pump_wavelength_nm"].setValue(532)
            lasers.inputs["qcl_current_ma"].setValue(500)
            if name == "repeated_rapid_scan":
                assert lasers.inputs["start_wavenumber_cm1"] is editor.inputs["spectral_max_cm1"]
                assert lasers.inputs["stop_wavenumber_cm1"] is editor.inputs["spectral_min_cm1"]
                settings = editor.read()
                plan = panel.adapter.make_plan(settings)
                assert plan.settings.fire_to_qswitch_s == pytest.approx(300e-6)
                assert plan.settings.mircat_current_ma == 500
                continue
            for key, value in (("start_wavenumber_cm1", 1946), ("stop_wavenumber_cm1", 1940), ("step_size_cm1", 2)):
                lasers.inputs[key].setValue(value)
            assert lasers.points() == [1946, 1944, 1942, 1940]
            if name == "fixed_wavenumber_kinetics":
                settings = editor.values()
                points = [p["wavenumber_cm1"] for p in settings["settings"]["positions"]]
                laser_data = settings["settings"]["laser_settings"]
            else:
                settings = editor.read_settings()
                points = [p["wavenumber_cm1"] for p in settings["spectral_points"]] if name.startswith("micro") else list(settings["wavenumbers_cm1"])
                laser_data = settings["laser_settings"]
            assert points == [1946, 1944, 1942, 1940]
            assert laser_data["pump_wavelength_nm"] == 532
            saved = tmp_path / f"{name}-{mode}.json"
            panel.adapter.save_plan(saved, settings, panel.adapter.make_plan(settings))
            panel.adapter.apply_settings(panel.adapter.load_plan(saved))
            assert editor.lasers.points() == points
            assert editor.lasers.values() == laser_data
            lasers.inputs["stop_wavenumber_cm1"].setValue(1945)
            with pytest.raises(ValueError, match="grid"):
                lasers.points()
            lasers.inputs["stop_wavenumber_cm1"].setValue(1934)
            assert lasers.points() == [1946, 1944, 1942, 1940, 1938, 1936, 1934]
            for invalid_stop in (1946, 1948):
                lasers.inputs["stop_wavenumber_cm1"].setValue(invalid_stop)
                if name == "fixed_wavenumber_kinetics" and invalid_stop == 1946:
                    assert lasers.points() == [1946]
                    assert not lasers.inputs["step_size_cm1"].isEnabled()
                    continue
                with pytest.raises(ValueError, match="[Ss]top [Ww]avenumber"):
                    lasers.points()
        finally:
            panel.deleteLater()
