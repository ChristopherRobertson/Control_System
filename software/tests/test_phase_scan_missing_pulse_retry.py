from dataclasses import replace
import json

import numpy as np

from control_app.workflows.phase_scan import PhaseScanSettings, build_phase_scan_plan
from control_app.workflows.phase_scan_data import Spectrum
from control_app.workflows.phase_scan_runner import PhaseScanRunner


def retry_plan(**changes):
    settings = replace(
        PhaseScanSettings(), start_wavenumber_cm1=2000, stop_wavenumber_cm1=1999,
        scan_speed_cm1_s=10_000, phase_delay_us=50, pre_pump_ms=.05, post_pump_ms=.05,
        rest_period_s=.1, **changes,
    )
    return build_phase_scan_plan(settings)


def pico_trace(*, duration_s=100e-6, missing=()):
    dt = 16e-9
    period = 500e-9
    pre = round(5e-6/dt)
    count = pre + int(np.ceil((duration_s+5e-6)/dt))
    times = (np.arange(count)-pre)*dt
    phase = 100e-9
    opportunity = np.rint((times-phase)/period).astype(int)
    pulse = (np.abs(times-(phase+opportunity*period)) <= 48e-9) & ~np.isin(opportunity, missing)
    return {"sample_interval_ns": 16.0, "pre_trigger_samples": pre, "maximum_adc_value": 32767,
            "overflow": 0, "ch_a_adc": np.where(pulse, 6000, 50).astype(np.int16),
            "ch_b_adc": np.where(pulse, 15000, 100).astype(np.int16),
            "external_trigger_basis": "mircat_sweep_active"}


class State:
    def __init__(self, *, never_fill=False):
        self.never_fill = never_fill
        self.calls = []


class CoverageAcquirer:
    pulse_coverage_required = True

    def __init__(self, state):
        self.state = state
        self.attempt_index = 0
        self.progress = lambda message: None

    def authorize(self, approved): pass
    def close(self): pass
    def set_attempt_context(self, attempt_index): self.attempt_index = attempt_index

    def prepare(self, settings, store, cancel):
        self.settings = settings
        return {"current_ma": 750, "picoscope": {"pulse_coverage_required": True,
                "sample_interval_ns": 16.0, "external_trigger_basis": "mircat_sweep_active"}}

    def capture(self, event, cancel):
        self.state.calls.append((event.scan_index, event.phase_index, self.attempt_index))
        duration = 100e-6
        targeted = event.pump_enabled and event.phase_index == 0
        missing = (1, 2) if targeted and (self.attempt_index == 0 or self.state.never_fill) else ()
        clockbase = 100_000_000
        sweep_start = 1.0
        start_tick = round(sweep_start*clockbase)
        stop_tick = start_tick + round(duration*clockbase)
        segment_metadata = {"optical_valid": True, "wavenumber_basis": "measured",
                            "pump_time_basis": "unpumped" if not event.pump_enabled else "measured",
                            "timestamp_origin_ticks": 0, "clockbase_hz": clockbase,
                            "sweep_active_ticks": [start_tick, stop_tick], "warnings": []}
        sample_time = sweep_start + np.linspace(0, duration, 41)
        pump_time = None if not event.pump_enabled else sweep_start-event.phase_delay_us*1e-6
        wn = np.linspace(2000, 1999, 41)
        absorbance = (np.zeros(41) if not event.pump_enabled else
                      .02 + .001*(2000-wn) + .10*self.attempt_index)
        spectrum = Spectrum(wn, 2*10**(-absorbance), np.ones(41), sample_time, pump_time,
                            {**segment_metadata, "segment_metadata": [segment_metadata],
                             "provisional": False}, np.zeros(41, dtype=np.int32))
        native = {"probe_repetition_rate_hz_readback": 2_000_000.0, "pulse_coverage_required": True,
                  "segments": [{"picoscope": pico_trace(duration_s=duration, missing=missing)}]}
        return native, spectrum


def test_retry_occurs_after_nominal_pass_and_merges_valid_regions(tmp_path):
    state = State()
    runner = PhaseScanRunner(lambda: CoverageAcquirer(state))
    plan = retry_plan()
    runner.execute("background", tmp_path, plan, laser_authorized=True)
    state.calls.clear()
    result = runner.execute("run", tmp_path, plan, laser_authorized=True)

    assert [attempt for _, _, attempt in state.calls[:plan.total_scans]] == [0]*plan.total_scans
    assert state.calls[plan.total_scans:] == [(plan.event_at(1).scan_index, 0, 1)]
    reconstruction = result["reconstruction"]
    assert reconstruction["completion_status"] == "COMPLETE"
    assert not reconstruction["publication_eligible"]
    assert reconstruction["run_classification"] == "EXPLORATORY_PROOF_OF_CONCEPT"
    weights = reconstruction["merge_contribution_weights"][0]
    assert np.any((weights[:, 0] == 0) & (weights[:, 1] == 1))
    assert np.any((weights[:, 0] > 0) & (weights[:, 1] > 0))
    both = np.flatnonzero((weights[:, 0] > 0) & (weights[:, 1] > 0))[0]
    wn = reconstruction["merge_target_wavenumber_cm1"][both]
    a0 = .02 + .001*(2000-wn)
    a1 = a0 + .10
    expected_ratio = weights[both, 0]*(2*10**(-a0)) + weights[both, 1]*(2*10**(-a1))
    expected_absorbance = -np.log10(expected_ratio/reconstruction["merge_background_ratio"][both])
    assert reconstruction["merge_transmission_ratio"][0, both] == expected_ratio
    assert reconstruction["merge_absorbance"][0, both] == expected_absorbance
    assert reconstruction["merge_absorbance"][0, both] != np.mean([a0, a1])
    summary = json.loads((result["path"] / "coverage" / "coverage_summary.json").read_text())
    assert len(summary["initial_affected_phase_delays"]) == 1
    assert summary["remaining_incomplete_phase_delays"] == []
    assert json.loads((result["path"] / "result.json").read_text())["status"] == "COMPLETE"


def test_three_failed_retries_create_flagged_best_effort_outputs(tmp_path):
    state = State(never_fill=True)
    runner = PhaseScanRunner(lambda: CoverageAcquirer(state))
    plan = retry_plan()
    runner.execute("background", tmp_path, plan, laser_authorized=True)
    state.calls.clear()
    result = runner.execute("run", tmp_path, plan, laser_authorized=True)

    target_calls = [call for call in state.calls if call[1] == 0]
    assert [attempt for _, _, attempt in target_calls] == [0, 1, 2, 3]
    reconstruction = result["reconstruction"]
    assert reconstruction["completion_status"] == "INCOMPLETE_MISSING_PULSE_COVERAGE"
    assert not reconstruction["publication_eligible"]
    assert reconstruction["deficient_missing_pulse_coverage"]
    assert np.isnan(reconstruction["absorbance"]).any()
    run_result = json.loads((result["path"] / "result.json").read_text())
    assert run_result["status"] == "INCOMPLETE_MISSING_PULSE_COVERAGE"
    assert not run_result["publication_eligible"]
    assert run_result["missing_pulse_coverage_status"] == "INCOMPLETE_MISSING_PULSE_COVERAGE"
    table = (result["path"] / "processed" / "reconstruction.csv").read_text()
    assert "INCOMPLETE_MISSING_PULSE_COVERAGE,False" in table
    processed_attempt = next((result["path"] / "processed" / "scans").glob("*.csv"))
    assert "INCOMPLETE_MISSING_PULSE_COVERAGE" in processed_attempt.read_text()


def test_incomplete_surface_is_visibly_marked_not_for_publication():
    import pytest
    pytest.importorskip("matplotlib")
    from control_app.ui.widgets.phase_scan_surface import make_surface_figure

    result = {"wavenumber_cm1": np.array([1999., 2000.]), "time_s": np.array([0., 1e-6]),
              "absorbance": np.array([[.1, np.nan], [.2, .3]]),
              "completion_status": "INCOMPLETE_MISSING_PULSE_COVERAGE"}
    figure = make_surface_figure(result)
    assert "NOT FOR PUBLICATION" in figure.axes[0].get_title()
    assert any("NOT FOR PUBLICATION" in text.get_text() for text in figure.texts)
