from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path

import pytest

from control_app.workflows.phase_scan import (
    PhaseScanPlanError, PhaseScanSettings, build_phase_scan_plan, derive_capture_window, partition_frame_blocks,
)


def test_requested_example_distinguishes_baseline_and_zero_delay_pump():
    plan = build_phase_scan_plan(PhaseScanSettings())
    assert plan.scan_duration_s == pytest.approx(0.001)
    assert plan.phases_per_repetition == 1401
    assert plan.total_scans == 1402
    assert plan.total_pump_events == 1401
    assert plan.first_phase_delay_us == -2000
    assert plan.last_phase_delay_us == 5000
    assert plan.probe_duty_cycle == pytest.approx(0.30)
    assert plan.settings.mircat_internal_repetition_rate_hz == 2_100_000
    assert plan.settings.mircat_internal_pulse_width_ns == 142
    assert plan.mircat_internal_duty_cycle == pytest.approx(.2982)
    assert plan.mircat_internal_rate_margin_hz == 100_000
    assert plan.nominal_probe_pulses_per_scan == pytest.approx(2_000)
    timing = plan.to_dict()["sequence"]["probe_timing"]
    assert timing["t660_1_repetition_rate_hz"] == 2_000_000
    assert timing["mircat_internal_repetition_rate_hz"] == 2_100_000
    assert timing["optical_pulse_trigger_mode"] == "external_trigger"
    assert plan.pump_rate_hz == pytest.approx(10/3)
    baseline, first, last = (plan.event_at(i) for i in (0, 1, 1401))
    assert not baseline.pump_enabled
    assert baseline.phase_delay_us is None
    assert first.pump_enabled and first.phase_delay_us == -2000
    assert last.pump_enabled and last.phase_delay_us == 5000
    assert plan.event_at(401).pump_enabled and plan.event_at(401).phase_delay_us == 0


def test_exploratory_current_and_fast_hf2li_preset_leave_campaign_candidate_unchanged():
    import yaml
    from control_app.workflows.phase_scan_data import HF2_PRESET, QCL_CURRENT_MA

    assert QCL_CURRENT_MA == pytest.approx(750)
    assert HF2_PRESET == "exploratory_phase_scan_poc"
    path = Path(__file__).resolve().parents[2] / "instrument" / "recipes" / "hf2li_presets.yaml"
    presets = yaml.safe_load(path.read_text(encoding="utf-8"))["presets"]
    exploratory = presets[HF2_PRESET]
    detectors = {item["index"]: item for item in exploratory["demodulators"] if item["index"] in {0, 3}}
    assert set(detectors) == {0, 3}
    assert all(item["rate_sps"] == pytest.approx(28_782.894736842107) for item in detectors.values())
    assert all(item["timeconstant_s"] == pytest.approx(50e-6) for item in detectors.values())
    campaign = presets["campaign_sweep_qualification_candidate"]
    campaign_detectors = {item["index"]: item for item in campaign["demodulators"] if item["index"] in {0, 3}}
    assert all(item["rate_sps"] == pytest.approx(2_000) for item in campaign_detectors.values())
    assert all(item["timeconstant_s"] == pytest.approx(1e-3) for item in campaign_detectors.values())


def test_repetitions_repeat_nominal_set_after_one_run_baseline():
    plan = build_phase_scan_plan(PhaseScanSettings(repetitions=3))
    assert plan.total_scans == 4204
    assert plan.total_pump_events == 4203
    assert not plan.event_at(0).pump_enabled
    for rep in range(3):
        start = 1 + rep * 1401
        assert plan.event_at(start).repetition == rep + 1
        assert plan.event_at(start).pump_enabled
        assert plan.event_at(start).phase_delay_us == -2000
        assert plan.event_at(start + 1400).phase_delay_us == 5000
    with pytest.raises(IndexError):
        plan.event_at(4204)
    with pytest.raises(IndexError):
        plan.event_at(-1)
    with pytest.raises(FrozenInstanceError):
        plan.settings.repetitions = 4


def test_internal_timing_is_independently_configurable_without_changing_opportunities():
    plan = build_phase_scan_plan(PhaseScanSettings(
        mircat_internal_repetition_rate_hz=2_001_000, mircat_internal_pulse_width_ns=149))
    assert plan.mircat_internal_rate_margin_hz == 1000
    assert plan.mircat_internal_duty_cycle == pytest.approx(.298149)
    assert plan.settings.probe_repetition_rate_hz == 2_000_000
    assert plan.settings.probe_pulse_width_ns == 150
    assert plan.nominal_probe_pulses_per_scan == 2000
    assert plan.phases_per_repetition == 1401


@pytest.mark.parametrize("increment,expected_count,last_delay", [
    (0.1, 70_001, 5000),
    (3, 2335, 5001),
    (10_000, 3, 10000),
    (20_000, 3, 20000),
])
def test_signed_grid_rounds_outward_without_float_rounding(increment, expected_count, last_delay):
    plan = build_phase_scan_plan(PhaseScanSettings(phase_delay_us=increment))
    assert plan.phases_per_repetition == expected_count
    assert plan.last_phase_delay_us == last_delay
    assert plan.first_phase_delay_us <= -2_000
    assert plan.last_phase_delay_us >= 5_000


def test_increasing_and_decreasing_scans_have_same_count_but_keep_direction():
    descending = build_phase_scan_plan(PhaseScanSettings())
    ascending = build_phase_scan_plan(PhaseScanSettings(start_wavenumber_cm1=1940, stop_wavenumber_cm1=1950))
    assert descending.phases_per_repetition == ascending.phases_per_repetition
    assert ascending.to_dict()["derived"]["scan_direction"] == "increasing_wavenumber"
    assert descending.to_dict()["derived"]["scan_direction"] == "decreasing_wavenumber"


@pytest.mark.parametrize("changes,match", [
    ({"phase_delay_us": 0}, "finite positive"),
    ({"scan_speed_cm1_s": float("nan")}, "finite positive"),
    ({"rest_period_s": float("inf")}, "finite positive"),
    ({"probe_repetition_rate_hz": True}, "finite positive"),
    ({"stop_wavenumber_cm1": 1950}, "must differ"),
    ({"probe_pulse_width_ns": 151}, "30% ceiling"),
    ({"mircat_internal_repetition_rate_hz": 2_000_000}, "higher than the T660-1"),
    ({"mircat_internal_repetition_rate_hz": 1_999_000}, "higher than the T660-1"),
    ({"mircat_internal_repetition_rate_hz": float("nan")}, "finite positive"),
    ({"mircat_internal_pulse_width_ns": 0}, "finite positive"),
    ({"mircat_internal_pulse_width_ns": 143}, "MIRcat internal duty cycle.*30% ceiling"),
    ({"rest_period_s": 0.09}, "10 Hz pump"),
    ({"scan_speed_cm1_s": 10}, "latest delayed scan"),
    ({"repetitions": 1.5}, "whole number"),
    ({"repetitions": True}, "whole number"),
])
def test_invalid_or_overlapping_plans_are_rejected(changes, match):
    with pytest.raises(PhaseScanPlanError, match=match):
        build_phase_scan_plan(replace(PhaseScanSettings(), **changes))


def test_cadence_duration_does_not_add_rest_after_every_scan_or_a_trailing_rest():
    plan = build_phase_scan_plan(PhaseScanSettings())
    # One baseline, 1401 pumped phases at 300 ms hardware cadence.
    assert plan.nominal_duration_s == pytest.approx(420.30718)


def test_large_grid_export_remains_compact_and_never_claims_measurements():
    plan = build_phase_scan_plan(PhaseScanSettings(phase_delay_us=0.001, repetitions=100))
    payload = plan.to_dict()
    assert len(json.dumps(payload, allow_nan=False)) < 5000
    assert payload["status"] == "PLANNING_ONLY"
    assert payload["sequence"]["scans_per_phase_per_repetition"] == 1
    assert plan.event_at(plan.total_scans - 1).repetition == 100


def test_calibrated_hardware_bounds_use_requested_trajectory_not_output_window():
    trajectory = {"source_id": "synthetic-nonlinear-calibration-v1",
        "wavenumber_cm1": [1952., 1950., 1945., 1940., 1938.],
        "time_s": [.0001, .0003, .00085, .00145, .0019],
        "time_reference": "process_trigger", "scan_speed_cm1_s": 10000.}
    plan = build_phase_scan_plan(PhaseScanSettings(), calibrated_trajectory=trajectory)
    assert plan.calibrated
    assert plan.trajectory_time_bounds_s == pytest.approx((.0003, .00145))
    assert plan.first_phase_delay_us == -2450
    assert plan.last_phase_delay_us == 4700
    assert plan.total_scans == 1432
    assert plan.to_dict()["sequence"]["observation_window_s"] == [-.001, .005]
    # Every calibrated requested wavenumber spans both requested output endpoints.
    for sweep_time in (.0003, .00085, .00145):
        assert plan.first_phase_delay_us*1e-6+sweep_time <= -.001+1e-12
        assert plan.last_phase_delay_us*1e-6+sweep_time >= .005-1e-12
    assert not build_phase_scan_plan(PhaseScanSettings()).calibrated


def test_sweep_active_trajectory_requires_measured_trigger_offset():
    trajectory = {"source_id": "synthetic-active-v1", "time_s": [0., .0012],
                  "wavenumber_cm1": [1950., 1940.], "time_reference": "sweep_active"}
    with pytest.raises(PhaseScanPlanError, match="measured sweep_active_delay_s"):
        build_phase_scan_plan(PhaseScanSettings(), calibrated_trajectory=trajectory)
    trajectory["sweep_active_delay_s"] = .0004
    plan = build_phase_scan_plan(PhaseScanSettings(), calibrated_trajectory=trajectory)
    assert plan.first_phase_delay_us == -2600
    assert plan.last_phase_delay_us == 4600


def test_calibration_cannot_extrapolate_or_use_nonmonotonic_times():
    trajectory = {"source_id": "synthetic-v1", "time_s": [0., .001],
                  "wavenumber_cm1": [1949., 1940.]}
    with pytest.raises(PhaseScanPlanError, match="bracket"):
        build_phase_scan_plan(PhaseScanSettings(), calibrated_trajectory=trajectory)
    trajectory.update(time_s=[0., 0.], wavenumber_cm1=[1950., 1940.])
    with pytest.raises(PhaseScanPlanError, match="strictly increasing"):
        build_phase_scan_plan(PhaseScanSettings(), calibrated_trajectory=trajectory)


def test_capture_duration_covers_qualified_active_interval_and_readback_grid():
    capture = derive_capture_window(.00232, sample_rate_hz=28_782.894736842107)
    assert .0026 <= capture["duration_s"] < .0027
    assert .0001 <= capture["pretrigger_s"] < .00014
    assert capture["duration_s"]-capture["pretrigger_s"] >= .00232+.00018
    assert derive_capture_window(.003)["duration_s"] == pytest.approx(.00328)
    with pytest.raises(PhaseScanPlanError, match="qualification"):
        derive_capture_window(float("nan"))


def test_partition_uses_fewest_documented_capacity_blocks_without_rescheduling():
    plan = build_phase_scan_plan(PhaseScanSettings(phase_delay_us=.5))
    events = tuple(plan.event_at(index) for index in range(plan.total_scans))
    blocks = partition_frame_blocks(events)
    assert len(blocks) == 2
    assert len(blocks[0]) == 8192
    assert tuple(event for block in blocks for event in block) == events
    assert partition_frame_blocks([1, 2, 3], capacity=2) == ((1, 2), (3,))
    assert [len(block) for block in partition_frame_blocks(range(8193))] == [8191, 2]
    with pytest.raises(PhaseScanPlanError, match="Verified T660 frame capacity"):
        partition_frame_blocks(events, capacity=8193)


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
    assert widget.plan.total_scans == 1402
    assert "1,402" in widget.summary_values["total"].text()
    assert widget.phase_table.item(0, 1).text() == "Baseline · pump OFF"
    assert widget.phase_table.item(1, 2).text() == "-2,000 µs"
    widget.inputs["repetitions"].setValue(2)
    assert widget.plan.total_scans == 2803
    assert "2,803" in widget.summary_values["total"].text()
    widget.inputs["probe_pulse_width_ns"].setValue(151)
    assert widget.plan is None
    assert widget.canvas.points == ()
    assert widget.phase_table.rowCount() == 0
    assert not widget.save_button.isEnabled()
    widget.inputs["probe_pulse_width_ns"].setValue(150)
    assert widget.plan.total_scans == 2803
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
    assert payload["settings"]["probe_pulse_width_ns"] == 150
    assert payload["settings"]["mircat_internal_repetition_rate_hz"] == 2_100_000
    assert payload["settings"]["mircat_internal_pulse_width_ns"] == 142
    assert "pump_repetition_rate_hz" not in payload["settings"]
    assert payload["derived"]["total_scans"] == 1402
    assert payload["status"] == "PLANNING_ONLY"
    assert payload["saved_at_utc"].endswith("+00:00")
    widget.inputs["repetitions"].setValue(2)
    assert widget.save_status.text() == ""
    assert payload["settings"]["repetitions"] == 1
    widget.deleteLater()


def test_widget_exposes_internal_headroom_separately_from_t660_opportunities(qt_app):
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    widget = PhaseScanWidget()
    assert "2,000,000 Hz / 150 ns" in widget.summary_values["probe"].text()
    assert "2,100,000 Hz / 142 ns" in widget.summary_values["mircat"].text()
    assert "29.820%" in widget.summary_values["mircat"].text()
    widget.inputs["mircat_internal_repetition_rate_hz"].setValue(2_000_000)
    assert widget.plan is None
    assert not widget.background_button.isEnabled()
    widget.inputs["mircat_internal_repetition_rate_hz"].setValue(2_100_000)
    widget.inputs["mircat_internal_pulse_width_ns"].setValue(143)
    assert widget.plan is None
    widget.inputs["mircat_internal_pulse_width_ns"].setValue(142)
    assert widget.plan.nominal_probe_pulses_per_scan == 2000
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

        def prepare_blocks(self, plan, events, cancel):
            return [tuple(events)]

        def capture_block(self, block, cancel):
            assert len(block) == 1 and not block[0].pump_enabled
            spectrum = Spectrum(np.array([2000., 1900.]), np.array([2., 2.]),
                np.ones(2), np.array([1., 1.01]), None,
                {"optical_valid": True, "wavenumber_basis": "measured"})
            return {"test_only": True}, [(block[0], spectrum)]

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
