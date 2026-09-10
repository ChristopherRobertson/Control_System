"""Experimental scope never silently weakens the ordinary phase-scan gate."""
from dataclasses import replace
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest

from control_app.workflows.phase_scan import PhaseScanSettings, build_phase_scan_plan, partition_frame_blocks
from control_app.workflows.phase_scan_acquisition import LivePhaseScanAcquirer
from control_app.workflows.temporary_phase_scan import TemporaryPhaseScanAcquirer, ExperimentalPhaseScanPlan


def adapter(**changes):
    return TemporaryPhaseScanAcquirer(**dict(experimental_authorized=True, pump_authorized=True,
        authorization_record='Operator explicitly approved temporary mode', **changes))


@pytest.mark.parametrize('experiment,pump,record', [(False, True, 'yes'), (True, False, 'yes'),
                                                   (1, True, 'yes'), (True, 1, 'yes'), (True, True, '')])
def test_missing_explicit_scope_never_connects(experiment, pump, record, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail('Hardware factory reached before authorization')
    acq = TemporaryPhaseScanAcquirer(experimental_authorized=experiment, pump_authorized=pump,
        authorization_record=record, laser_factory=forbidden, t660_factory=forbidden, hf_factory=forbidden)
    acq.authorize(True)
    with pytest.raises(PermissionError):
        acq.prepare(PhaseScanSettings(), SimpleNamespace(path=tmp_path), Event())


def test_standard_mode_still_requires_qualification():
    plan = build_phase_scan_plan(PhaseScanSettings())
    with pytest.raises(RuntimeError, match='qualified calibrated'):
        LivePhaseScanAcquirer().resolve_plan(plan)
    with pytest.raises(RuntimeError, match='uncalibrated'):
        LivePhaseScanAcquirer()._validate_execution_plan(plan)


def test_exact_agreed_grid_and_engineering_metadata():
    acq = adapter()
    plan = acq.resolve_plan(build_phase_scan_plan(PhaseScanSettings()))
    assert isinstance(plan, ExperimentalPhaseScanPlan) and not plan.calibrated
    assert plan.total_scans == 322 and plan.total_pump_events == 321
    assert (plan.first_phase_delay_us, plan.last_phase_delay_us) == (-11000., 5000.)
    blocks = partition_frame_blocks([plan.event_at(i) for i in range(322)], capacity=16)
    assert [len(b) for b in blocks] == [16]*20 + [2]
    assert acq.capture_window['duration_s'] == .02028
    assert 'qualified_sweep_active_s' not in acq.capture_window
    assert 'calibrated_trajectory' not in acq._qualification_metadata()
    assert plan.to_dict()['derived']['trajectory_calibrated'] is False
    assert plan.to_dict()['status'] == 'EXPERIMENTAL_PROGRAMMED_GRID'
    acq._validate_execution_plan(plan)
    with pytest.raises(PermissionError):
        acq._validate_execution_plan(build_phase_scan_plan(PhaseScanSettings()))


@pytest.mark.parametrize('changes', [{'repetitions': 2}, {'phase_delay_us': 5}, {'scan_speed_cm1_s': 9000}])
def test_changed_experiment_scope_rejected(changes):
    with pytest.raises(ValueError, match='restricted'):
        adapter().resolve_plan(build_phase_scan_plan(replace(PhaseScanSettings(), **changes)))


@pytest.mark.parametrize('kwargs', [{'engineering_sweep_bound_s': float('nan')},
    {'engineering_sweep_bound_s': .3}, {'qualified_trajectory': {'source_id': 'fake'}},
    {'qualified_sweep_active_s': .02}])
def test_no_fake_qualification_or_unbounded_capture(kwargs):
    with pytest.raises(ValueError):
        adapter(**kwargs)


@pytest.mark.parametrize('fault', ['basis', 'marker_count', 'long_sweep', 'missing_pump', 'invalid_ch1'])
def test_experimental_spectral_integrity(fault):
    acq = adapter()
    plan = acq.resolve_plan(build_phase_scan_plan(PhaseScanSettings()))
    spectrum = SimpleNamespace(metadata={'wavenumber_basis': 'controller_markers',
        'marker_ticks': list(range(21)), 'sweep_active_ticks': [0, 10], 'clockbase_hz': 1000.},
        sample_r=np.array([1., 2.]), pump_time_s=.1)
    if fault == 'basis': spectrum.metadata['wavenumber_basis'] = 'nominal_sweep_bounds'
    if fault == 'marker_count': spectrum.metadata['marker_ticks'].pop()
    if fault == 'long_sweep': spectrum.metadata['sweep_active_ticks'] = [0, 30]
    if fault == 'missing_pump': spectrum.pump_time_s = None
    if fault == 'invalid_ch1': spectrum.sample_r[0] = np.nan
    with pytest.raises(ValueError):
        acq._validate_spectrum(plan.event_at(1), spectrum)
