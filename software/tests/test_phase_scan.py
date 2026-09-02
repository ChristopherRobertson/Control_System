from dataclasses import FrozenInstanceError, replace
import json
import os

import pytest

from control_app.workflows.phase_scan import (
    PhaseScanPlanError, PhaseScanSettings, build_phase_scan_plan,
)


def test_requested_example_distinguishes_baseline_and_zero_delay_pump():
    plan = build_phase_scan_plan(PhaseScanSettings())
    assert plan.scan_duration_s == pytest.approx(0.010)
    assert plan.phases_per_repetition == 2801
    assert plan.total_scans == 2802
    assert plan.total_pump_events == 2801
    assert plan.first_phase_delay_us == -12000
    assert plan.last_phase_delay_us == 2000
    assert plan.probe_duty_cycle == pytest.approx(0.30)
    assert plan.nominal_probe_pulses_per_scan == pytest.approx(20_000)
    workaround = plan.to_dict()["sequence"]["missing_pulse_workaround"]
    assert workaround["consecutive_missing_limit"] == 2
    assert workaround["minimum_interval_coverage"] == pytest.approx(.90)
    assert workaround["maximum_scan_missing_fraction"] == pytest.approx(.05)
    assert workaround["additional_attempt_limit"] == 3
    assert plan.pump_rate_hz == 1
    baseline, first, last = (plan.event_at(i) for i in (0, 1, 2801))
    assert not baseline.pump_enabled
    assert baseline.phase_delay_us is None
    assert first.pump_enabled and first.phase_delay_us == -12000
    assert last.pump_enabled and last.phase_delay_us == 2000
    assert plan.event_at(2401).pump_enabled and plan.event_at(2401).phase_delay_us == 0


def test_repetitions_repeat_entire_set_instead_of_repeating_each_phase():
    plan = build_phase_scan_plan(PhaseScanSettings(repetitions=3))
    assert plan.total_scans == 8406
    assert plan.total_pump_events == 8403
    for rep in range(3):
        start = rep * 2802
        assert plan.event_at(start).repetition == rep + 1
        assert not plan.event_at(start).pump_enabled
        assert plan.event_at(start + 1).phase_delay_us == -12000
        assert plan.event_at(start + 2801).phase_delay_us == 2000
    with pytest.raises(IndexError):
        plan.event_at(8406)
    with pytest.raises(IndexError):
        plan.event_at(-1)
    with pytest.raises(FrozenInstanceError):
        plan.settings.repetitions = 4


@pytest.mark.parametrize("increment,expected_count,last_delay", [
    (0.1, 140_001, 2000),
    (3, 4668, 2001),
    (10_000, 4, 10000),
    (20_000, 3, 20000),
])
def test_signed_grid_rounds_outward_without_float_rounding(increment, expected_count, last_delay):
    plan = build_phase_scan_plan(PhaseScanSettings(phase_delay_us=increment))
    assert plan.phases_per_repetition == expected_count
    assert plan.last_phase_delay_us == last_delay
    assert plan.first_phase_delay_us <= -12_000
    assert plan.last_phase_delay_us >= 2_000


def test_increasing_and_decreasing_scans_have_same_count_but_keep_direction():
    descending = build_phase_scan_plan(PhaseScanSettings())
    ascending = build_phase_scan_plan(PhaseScanSettings(start_wavenumber_cm1=1900, stop_wavenumber_cm1=2000))
    assert descending.phases_per_repetition == ascending.phases_per_repetition
    assert ascending.to_dict()["derived"]["scan_direction"] == "increasing_wavenumber"
    assert descending.to_dict()["derived"]["scan_direction"] == "decreasing_wavenumber"


@pytest.mark.parametrize("changes,match", [
    ({"phase_delay_us": 0}, "finite positive"),
    ({"scan_speed_cm1_s": float("nan")}, "finite positive"),
    ({"rest_period_s": float("inf")}, "finite positive"),
    ({"probe_repetition_rate_hz": True}, "finite positive"),
    ({"stop_wavenumber_cm1": 2000}, "must differ"),
    ({"probe_pulse_width_ns": 151}, "30% ceiling"),
    ({"rest_period_s": 0.09}, "10 Hz pump"),
    ({"scan_speed_cm1_s": 100}, "latest delayed scan"),
    ({"repetitions": 1.5}, "whole number"),
    ({"repetitions": True}, "whole number"),
    ({"missing_pulse_consecutive_limit": 0}, "positive whole number"),
    ({"missing_pulse_retry_limit": 0}, "positive whole number"),
    ({"minimum_reconstruction_interval_coverage": 0}, "greater than zero"),
    ({"maximum_scan_missing_fraction": 1.1}, "at most one"),
    ({"pulse_detection_threshold_fraction": 0}, "greater than zero"),
])
def test_invalid_or_overlapping_plans_are_rejected(changes, match):
    with pytest.raises(PhaseScanPlanError, match=match):
        build_phase_scan_plan(replace(PhaseScanSettings(), **changes))


def test_cadence_duration_does_not_add_rest_after_every_scan_or_a_trailing_rest():
    plan = build_phase_scan_plan(PhaseScanSettings())
    # 2,801 pumped phases plus baseline; final sweep ends 12 ms after its pump.
    assert plan.nominal_duration_s == pytest.approx(2801.012)


def test_large_grid_export_remains_compact_and_never_claims_measurements():
    plan = build_phase_scan_plan(PhaseScanSettings(phase_delay_us=0.001, repetitions=100))
    payload = plan.to_dict()
    assert len(json.dumps(payload, allow_nan=False)) < 5000
    assert payload["status"] == "PLANNING_ONLY"
    assert payload["sequence"]["scans_per_phase_per_repetition"] == 1
    assert plan.event_at(plan.total_scans - 1).repetition == 100


@pytest.fixture
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def test_widget_updates_plan_and_clears_stale_preview_on_invalid_input(qt_app):
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    widget = PhaseScanWidget()
    assert set(widget.inputs) == set(PhaseScanSettings.__dataclass_fields__)
    assert widget.plan.total_scans == 2802
    assert "2,802" in widget.summary_values["total"].text()
    assert widget.phase_table.item(0, 1).text() == "Baseline · pump OFF"
    assert widget.phase_table.item(1, 2).text() == "-12,000 µs"
    widget.inputs["repetitions"].setValue(2)
    assert widget.plan.total_scans == 5604
    assert "5,604" in widget.summary_values["total"].text()
    widget.inputs["probe_pulse_width_ns"].setValue(151)
    assert widget.plan is None
    assert widget.canvas.points == ()
    assert widget.phase_table.rowCount() == 0
    assert not widget.save_button.isEnabled()
    widget.inputs["probe_pulse_width_ns"].setValue(150)
    assert widget.plan.total_scans == 5604
    assert widget.save_button.isEnabled()
    assert not widget.start_button.isEnabled()
    assert not widget.abort_button.isEnabled()
    assert not widget.command_running()
    widget.deleteLater()


def test_save_plan_records_corrected_probe_fields_and_no_hardware_authorization(qt_app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    target = tmp_path / "phase_plan.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(target), "JSON (*.json)"))
    widget = PhaseScanWidget()
    widget.save_button.click()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["settings"]["probe_repetition_rate_hz"] == 2_000_000
    assert "pump_repetition_rate_hz" not in payload["settings"]
    assert payload["derived"]["total_scans"] == 2802
    assert payload["status"] == "PLANNING_ONLY"
    assert payload["saved_at_utc"].endswith("+00:00")
    widget.inputs["repetitions"].setValue(2)
    assert widget.save_status.text() == ""
    assert payload["settings"]["repetitions"] == 1
    widget.deleteLater()


def test_background_worker_enables_start_only_after_success(qt_app, monkeypatch, tmp_path):
    import time
    import numpy as np
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QMessageBox
    from control_app import paths
    from control_app.workflows.phase_scan_data import Spectrum
    from control_app.workflows.phase_scan_runner import PhaseScanRunner
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    monkeypatch.setattr(paths, "_selected_save_location", tmp_path)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)

    class Acquirer:
        def prepare(self, *args):
            return {"current_ma": 1000}

        def capture(self, event, cancel):
            assert not event.pump_enabled
            return {"test_only": True}, Spectrum(np.array([2000., 1900.]), np.array([2., 2.]),
                np.ones(2), np.array([1., 1.01]), None,
                {"optical_valid": True, "wavenumber_basis": "measured"})

        def close(self):
            pass

    widget = PhaseScanWidget(runner=PhaseScanRunner(Acquirer))
    assert widget.background_button.isEnabled()
    assert not widget.start_button.isEnabled()
    widget.background_button.click()
    assert widget.command_running() and widget.abort_button.isEnabled()
    deadline = time.monotonic()+3
    while widget.command_running() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert not widget.command_running()
    assert widget.start_button.isEnabled()
    assert widget.canvas.y_label == "Background S₀/R₀"
    assert "sample/reference ratio" in widget.scan_status.text()
    widget.inputs["phase_delay_us"].setValue(10)
    assert widget.start_button.isEnabled()
    widget.inputs["probe_pulse_width_ns"].setValue(140)
    assert not widget.start_button.isEnabled()
    widget.deleteLater()


def test_global_save_location_creates_folder_and_blocks_changes_during_activity(qt_app, monkeypatch, tmp_path):
    from control_app import paths
    from control_app.ui.main_window import ControlSystemMainWindow
    monkeypatch.setattr(paths, "_selected_save_location", None)
    window = ControlSystemMainWindow(persist_settings=False)
    target = tmp_path / "experiment data" / "new folder"
    window.save_location.setText(str(target))
    window._apply_save_location()
    assert target.is_dir()
    assert paths.output_run_root() == target
    assert paths.output_log_root() == target / "logs"
    assert window.scan_plotter_widget.destination.text() == str(target)
    monkeypatch.setattr(window, "_close_blockers", lambda: ["active test operation"])
    window._update_save_enabled()
    assert not window.save_location.isEnabled()
    assert not window.browse_save_location.isEnabled()
    window.save_location.setText(str(tmp_path / "wrong folder"))
    window._apply_save_location()
    assert paths.output_run_root() == target
    assert not (tmp_path / "wrong folder").exists()
    assert "cannot change" in window.save_location_status.text()
    window.deleteLater()


def test_completed_surface_uses_absorbance_vertical_and_time_depth(qt_app):
    import numpy as np
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    widget = PhaseScanWidget()
    widget.show_reconstruction({"wavenumber_cm1": np.array([1900, 1950, 2000]),
        "time_s": np.array([0, .01, .02]),
        "absorbance": np.array([[np.nan, .3, .0], [.0, .2, .0], [.0, .1, .0]])})
    axes = widget._surface.figure.axes[0]
    assert axes.get_xlabel().startswith("Wavenumber")
    assert axes.get_ylabel() == "Absorbance"
    assert axes.get_zlabel() == "Time after pump (ms)"
    assert axes._vertical_axis == 1  # Matplotlib Y axis.
    assert widget.plot_stack.currentWidget() is widget._surface
    widget.deleteLater()
