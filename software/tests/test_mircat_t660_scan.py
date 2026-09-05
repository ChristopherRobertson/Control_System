"""Verify the existing MIRcat Sweep Scan buttons route through T660 acquisition."""
import os
import time
from threading import Event

import pytest

from control_app.ui.contracts import WorkflowCommand, WorkflowResult
from control_app.workflows import mircat_widget_commands as commands

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


def test_existing_handler_forwards_scan_fields_and_releases_previous_sdk(tmp_path, monkeypatch):
    calls = []
    class PreviousSDK:
        def stop_scan_if_needed(self): calls.append('stop')
        def turn_emission_off(self): calls.append('off')
        def disarm(self): calls.append('disarm')
        def deinitialize(self): calls.append('close')
    def capture(root, **kwargs):
        calls.append(kwargs)
        assert kwargs['settings']['start_cm1'] == 2000
        assert kwargs['settings']['stop_cm1'] == 1800
        assert kwargs['settings']['qcl_current_ma'] == 725
        assert kwargs['settings']['external_rate_hz'] == 2e6
        assert kwargs['settings']['mircat_internal_rate_hz'] == 2.1e6
        return {'path': str(root), 'cleanup': {'safe_state_and_retained_settings_verified': True, 'errors': []},
                'warnings': ['HF2LI Inputs 1 and 2 are clipped; continuing diagnostic acquisition.'],
                'analysis': {'scan_rows': [[2000, .1, .2]]}}
    monkeypatch.setattr(commands, 'run_air_scan', capture)
    monkeypatch.setattr(commands, 'output_run_root', lambda: tmp_path)
    handler = commands.MircatWidgetCommandHandler()
    handler.initialized, handler.service = True, PreviousSDK()
    command = WorkflowCommand(device_key='mircat', command='mircat.start_sweep_scan', safety_approval=True,
                              parameters={'scan_start_cm1': 2000, 'scan_stop_cm1': 1800, 'current_ma': 725})
    result = handler._handle(command, None)
    assert result.status == 'complete' and result.data['scan_rows'] == [[2000, .1, .2]]
    assert 'Warnings: HF2LI Inputs 1 and 2 are clipped' in result.message
    assert calls[:4] == ['stop', 'off', 'disarm', 'close']
    assert not handler.initialized and handler.service is None and not handler.scan_running
    result = handler._handle(WorkflowCommand(device_key='mircat', command='mircat.start_sweep_scan'), None)
    assert result.status == 'blocked' and len(calls) == 5


def test_existing_scan_buttons_show_state_keep_stop_available_and_wait_for_cleanup(tmp_path, monkeypatch):
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    from control_app.ui.main_window import ControlSystemMainWindow
    from control_app import paths
    from control_app.ui.widgets.mircat_widget import MIRCAT_WIDGET_SPEC
    monkeypatch.setattr(paths, '_selected_save_location', tmp_path)
    app = QApplication.instance() or QApplication([])
    entered, release = Event(), Event()
    requests = []

    class Handler:
        hardware_access = False
        mircat_scan_active = False
        mircat_scan_cancel = Event()
        def __call__(self, command): return WorkflowResult(status='blocked', message='no hardware')
        def request_mircat_scan_stop(self): self.mircat_scan_cancel.set()
        def run_mircat_scan(self, command, *, progress, on_state):
            requests.append(command)
            on_state({'armed': True, 'emission_on': True})
            progress('Pico armed; T660 process trigger sent')
            entered.set()
            self.mircat_scan_cancel.wait(3)
            release.wait(3)
            on_state({'armed': False, 'emission_on': False})
            return WorkflowResult(status='complete', message='Outputs stopped; settings retained',
                                  data={'scan_rows': [[2050, .1, .2]],
                                        'scan_metadata': {'detector_status': 'diagnostic', 'markers_observed': 80, 'markers_expected': 81}})
    handler = Handler()
    window = ControlSystemMainWindow(handler)
    widget = window.mircat_widget
    window.tabs.setCurrentWidget(widget)
    widget.parameter_tabs.setCurrentIndex(1)
    window.show()
    app.processEvents()
    widget.parameter_inputs['approved_laser_safety_condition'][0].setChecked(True)
    widget.buttons_by_command['mircat.start_sweep_scan'].click()
    assert entered.wait(1)
    app.processEvents()
    assert widget.status_labels['armed'].text() == 'ON'
    assert widget.status_labels['emission_on'].text() == 'ON'
    assert handler.mircat_scan_active and widget.command_running()
    assert widget.buttons_by_command['mircat.stop_scan'].isEnabled()
    assert not widget.buttons_by_command['mircat.start_sweep_scan'].isEnabled()
    assert not window.tabs.isTabEnabled(window.tabs.indexOf(window.phase_scan_widget))
    widget.buttons_by_command['mircat.stop_scan'].click()
    app.processEvents()
    assert handler.mircat_scan_cancel.is_set() and widget.command_running()
    assert window._close_blockers() and not window.save_location.isEnabled()
    release.set()
    deadline = time.monotonic()+3
    while widget.command_running() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.001)
    assert not widget.command_running() and not handler.mircat_scan_active
    assert widget.status_labels['armed'].text() == 'OFF'
    assert widget.buttons_by_command['mircat.start_sweep_scan'].isEnabled()
    assert len(requests) == 1
    assert requests[0].parameters['current_ma'] == 750
    assert requests[0].parameters['scan_internal_rate_hz'] == 2100000
    assert window.scan_plotter_widget.canvas.rows == [(2050., .1, .2)]
    assert 'PROVISIONAL' in window.scan_plotter_widget.canvas.warning
    assert not any(window.tabs.tabText(i) == 'Air Scan' for i in range(window.tabs.count()))
    window.close()
    window.deleteLater()
    app.processEvents()


def test_state_machine_blocks_other_routes_during_mircat_sweep(tmp_path):
    from control_app.workflows.state_machine import WorkflowStateMachine
    handler = WorkflowStateMachine(operator='test', hardware_access=False, run_dir=tmp_path)
    handler.mircat_scan_active = True
    result = handler(WorkflowCommand(device_key='mircat', command='mircat.initialize'))
    assert result.status == 'blocked' and 'Sweep Scan' in result.message
    assert handler.ui_close_blockers() and handler.ui_iris_motion_blockers()
    handler.request_mircat_scan_stop()
    assert handler.mircat_scan_cancel.is_set()


def test_preflight_failure_is_visible_above_scrolled_controls(tmp_path, monkeypatch):
    pytest.importorskip('PySide6')
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication
    from control_app.ui.widgets.mircat_widget import MircatWidget

    def failed_capture(root, **kwargs):
        exc = RuntimeError('HF2LI reference did not follow 2000000 Hz')
        return {'path': str(root), 'acquisition_error': repr(exc),
                'acquisition_error_message': str(exc),
                'cleanup': {'safe_state_and_retained_settings_verified': True, 'errors': []}}

    monkeypatch.setattr(commands, 'run_air_scan', failed_capture)
    monkeypatch.setattr(commands, 'output_run_root', lambda: tmp_path)
    monkeypatch.setattr(commands, 'output_log_root', lambda: tmp_path)
    app = QApplication.instance() or QApplication([])
    widget = MircatWidget(commands.MircatWidgetCommandHandler())
    widget.parameter_tabs.setCurrentIndex(1)
    widget.resize(1000, 740)
    widget.show()
    widget.parameter_inputs['approved_laser_safety_condition'][0].setChecked(True)
    app.processEvents()
    start = widget.buttons_by_command['mircat.start_sweep_scan']
    viewport = widget.parameter_scroll.viewport()
    assert viewport.rect().contains(start.mapTo(viewport, start.rect().center()))
    start.click()
    deadline = time.monotonic()+3
    while widget.command_running() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.001)
    assert not widget.command_running()
    assert 'FAILED: HF2LI reference did not follow 2000000 Hz' in widget.operation_status.text()
    assert 'IR OFF; MIRcat disarmed' in widget.operation_status.text()
    assert 'RuntimeError' not in widget.operation_status.text()
    assert str(tmp_path) in widget.result_log.toPlainText()
    widget.parameter_scroll.verticalScrollBar().setValue(widget.parameter_scroll.verticalScrollBar().maximum())
    app.processEvents()
    assert widget.operation_status.visibleRegion().contains(widget.operation_status.rect().center())
    assert widget.rect().contains(widget.operation_status.mapTo(widget, QPoint(0, 0)))
    assert start.isEnabled()
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_scan_progress_and_result_are_delivered_on_gui_thread():
    pytest.importorskip('PySide6')
    from threading import get_ident
    from PySide6.QtWidgets import QApplication
    from control_app.ui.widgets.mircat_widget import MircatWidget

    app = QApplication.instance() or QApplication([])
    gui_thread = get_ident()
    deliveries, work_threads = [], []

    class Handler:
        def run_mircat_scan(self, command, *, progress, on_state):
            work_threads.append(get_ident())
            for message in ('Preparing detectors', 'Acquisition stopped: reference lock lost',
                            'Stopping outputs', 'Saving native data after shutdown'):
                progress(message)
            on_state({'armed': False, 'emission_on': False})
            return WorkflowResult(status='failed', message='Reference lock lost; outputs stopped')

    class ObservedWidget(MircatWidget):
        def _show_result(self, result):
            deliveries.append((result.message, get_ident()))
            # Record a threading violation without making an unsafe Qt call in this test.
            if get_ident() == gui_thread:
                super()._show_result(result)

    widget = ObservedWidget(Handler())
    widget.parameter_tabs.setCurrentIndex(1)
    widget.parameter_inputs['approved_laser_safety_condition'][0].setChecked(True)
    widget.buttons_by_command['mircat.start_sweep_scan'].click()
    deadline = time.monotonic()+3
    while widget.command_running() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.001)
    app.processEvents()
    assert not widget.command_running()
    assert work_threads and all(thread != gui_thread for thread in work_threads)
    assert len(deliveries) == 6  # Initial UI message, four progress events, final failure.
    violations = [message for message, thread in deliveries if thread != gui_thread]
    widget.close()
    widget.deleteLater()
    app.processEvents()
    assert not violations, f'GUI updates executed on scan worker: {violations}'
