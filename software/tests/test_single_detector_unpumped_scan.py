"""Exercise the CH1-only optical sequence with independent fake transports."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from control_app.workflows import air_scan as air
from control_app.workflows.phase_scan_acquisition import acquisition_setting_nodes
from control_app.workflows.phase_scan_data import load_native
from test_air_scan import Rig, FakeLaser, FakeHF, AirTimer


class SingleTimer(AirTimer):
    def fire_remote_trigger(self):
        assert self.name == 't660_2' and self.source == 'REM'
        assert self.channels['C']['enabled']
        assert all(not self.channels[channel]['enabled'] for channel in 'ABD')
        assert self.world.hf.active
        self.shots += 1
        self.world.fires.append(deepcopy(self.channels))
        self.world.laser.triggered = True
        if self.world.fail_stop_after_trigger:
            self.world.fail_stop = True


class SingleLaser(FakeLaser):
    def tune_to_wavenumber(self, wavenumber, *, qcl):
        assert wavenumber == self.rig.scan_profile['start_cm1'] and qcl == 1 and self.armed
        assert not self.rig.units['t660_1'].channels['B']['enabled']
        self.tuned = self.manual_tune = True

    def start_sweep_scan(self, **kwargs):
        assert kwargs == {**{key: self.rig.scan_profile[key] for key in ('start_cm1', 'stop_cm1', 'scan_rate_cm1_s')},
                          'qcl': 1, 'repetitions': 1}
        assert not self.manual_tune
        self.started = self.emission = True

    def set_wavelength_trigger_pulse_width_us(self, width):
        self.rig.marker_width_set = width
        return width

    def get_scan_status(self):
        return {'scan_in_progress': self.started and not self.rig.hf.completed}


class SingleHF(FakeHF):
    def __init__(self, rig):
        super().__init__(rig)
        self.completed = False
        self.subscriptions = None
        self.status_paths = []

    def load_preset(self, name):
        return air.HF2LIService.load_preset(self, name)

    def apply_preset(self, preset):
        self.preset = preset
        nodes = acquisition_setting_nodes('fake', preset.settings)
        # Genuine device behavior already observed by the standalone workflow.
        nodes['/fake/demods/2/timeconstant'] = .0010018887078828383
        nodes['/fake/sigins/0/range'] = 1.00739
        self.snapshot = {'nodes': {path: {'type': 'double' if isinstance(value, float) else 'int', 'value': value}
                                   for path, value in nodes.items()}, 'read_errors': {}}

    def _get_node(self, kind, path):
        if '/status/' in path:
            self.status_paths.append(path)
            assert 'adc1' not in path and not path.endswith('/adcclip/1')
        return super()._get_node(kind, path)

    def start_acquisition(self, *, demodulators):
        self.subscriptions = demodulators
        assert demodulators == (0, 2)
        self.active = True

    def read_acquisition(self, duration):
        if self.rig.laser.triggered and self.rig.fail_capture:
            raise RuntimeError('injected CH1 stream failure')
        data = {}
        begin = self.cursor
        end = begin + (2.7 if self.rig.laser.triggered and not self.completed and not self.rig.fast_scan else .01)
        for demod, rate in ((0, 28782.894736842107), (2, 200000.)):
            times = np.arange(np.ceil(begin * rate), np.ceil(end * rate)) / rate
            dio = np.zeros(len(times), dtype=np.uint32)
            if self.rig.pump_baseline_high:
                dio |= 1 << 17
            if self.rig.unstable_pump_baseline and not self.rig.laser.triggered:
                dio[len(dio)//2:] ^= 1 << 17
            if self.rig.laser.triggered:
                start = .02025 if self.rig.fast_scan else .02
                duration = .0023 if self.rig.fast_scan else 2.5
                inside = (times >= start) & (times < start + duration)
                dio[inside] |= 1 << 21
                if self.rig.fast_scan:
                    for offset in (.00025, .000825, .0014):
                        dio[(times >= start + offset) & (times < start + offset + .000125)] |= 1 << 22
                else:
                    dio[inside & (np.mod(times - start, .125) < .0005)] |= 1 << 22
                if self.rig.unexpected_pump:
                    dio[inside] ^= 1 << 17
            data[f'/fake/demods/{demod}/sample'] = {
                'timestamp': np.rint(times * self.get_clockbase()).astype(np.uint64) + np.uint64(2**60),
                'x': np.full(len(times), .1), 'y': np.zeros(len(times)), 'dio': dio,
                'auxin0': np.zeros(len(times)), 'auxin1': np.zeros(len(times)),
            }
        self.cursor = end
        if self.rig.laser.triggered:
            self.completed = True
        return {'data': data}


def run_single(tmp_path, *, fault=None, kind='buffer_blank', baseline_high=False, settings=None):
    rig = Rig()
    rig.fail_stop_after_trigger = fault == 'cleanup'
    rig.unexpected_pump = fault == 'pump'
    rig.fail_capture = fault == 'stream'
    rig.pump_baseline_high = baseline_high
    rig.unstable_pump_baseline = fault == 'pretrigger_pump'
    rig.scan_profile = settings or air.single_detector_scan_profile()
    rig.fast_scan = rig.scan_profile['scan_rate_cm1_s'] == 10000.
    def no_pico(*args, **kwargs):
        raise AssertionError('Single CH1 scan must never access PicoScope')
    result = air.run_air_scan(
        tmp_path, cancel=rig.cancel, progress=rig.events.append, laser_authorized=True,
        single_detector=True, record_kind=kind, pump_blocked=False, settings=settings,
        laser_factory=lambda **kwargs: SingleLaser(rig), hf_factory=lambda **kwargs: SingleHF(rig),
        t660_factory=lambda name, **kwargs: SingleTimer(rig, name), picoscope_factory=no_pico,
        tec_ready_stability_s=0.,
    )
    return rig, result, load_native(Path(result['path']) / 'hf2li_native.npz')


@pytest.mark.parametrize('kind,role', [('buffer_blank', 'buffer_blank'), ('sample', 'unpumped_sample_test')])
def test_one_ch1_sweep_without_pico_preserves_truthful_provenance_and_stops_outputs(tmp_path, kind, role):
    rig, result, native = run_single(tmp_path, kind=kind)
    assert result['acquisition_error'] is None, result
    assert result['cleanup']['safe_state_and_retained_settings_verified'], result
    assert result['save_errors'] == []
    assert native['optical_valid'] and native['record_role'] == role
    assert native['pump_outputs_disabled_readback_verified']
    assert rig.hf.subscriptions == (0, 2) and rig.pico is None
    assert rig.hf.closed and rig.laser.closed and not rig.laser.emission and not rig.laser.armed
    assert len(rig.fires) == 1
    assert all(not unit.channels[channel]['enabled'] for unit in rig.units.values() for channel in 'ABCD')
    operation = json.loads((Path(result['path']) / 'operation.json').read_text())
    assert 'pump_physically_blocked' not in operation and 'clicked' not in operation['authorization']
    assert 'pump_inhibition_plan' in operation
    assert not list(Path(result['path']).glob('picoscope*'))
    assert all(not check['available'] and 'error' in check
               for check in native['mircat_marker_channel_checks'])


@pytest.mark.parametrize('readback_error', [False, True])
def test_per_qcl_marker_readback_is_preserved_before_and_after_setup(tmp_path, monkeypatch, readback_error):
    from control_app.devices.mircat_service import MircatCommandError
    def marker_readback(laser, channel):
        assert channel == 1 and not laser.triggered
        if readback_error:
            raise MircatCommandError('injected marker readback communication error')
        # Distinct SDK observations must survive without being replaced by the
        # global requested scan range or an inferred endpoint/count calculation.
        return {'channel': channel, 'units': 2, 'units_name': 'cm^-1',
                'start': 1999.75 if laser.started else 1999.5,
                'stop': 1900.25, 'interval': 5., 'num_triggers': 20}
    monkeypatch.setattr(SingleLaser, 'get_wavelength_trigger_channel_params', marker_readback, raising=False)
    _, result, native = run_single(tmp_path)
    assert result['acquisition_error'] is None and native['optical_valid']
    checks = native['mircat_marker_channel_checks']
    assert [item['context'] for item in checks] == ['configured', 'after_sweep_setup']
    directory = Path(result['path'])
    for item in checks:
        assert item['timestamp_utc'] and item['source'] == 'MIRcatSDK_GetWlTrigChanParams'
        assert json.loads((directory / f"mircat_marker_channel_{item['context']}.json").read_text()) == item
        if readback_error:
            assert not item['available'] and 'MircatCommandError' in item['error']
            assert 'readback' not in item
        else:
            assert item['available'] and item['readback']['num_triggers'] == 20
    assert json.loads((directory / 'mircat_configured.json').read_text())['marker_channel'] == checks[0]
    if not readback_error:
        assert [item['readback']['start'] for item in checks] == [1999.5, 1999.75]
    assert 'marker_wavenumbers_cm1' not in native
    assert 'marker_identity_basis' not in native


@pytest.mark.parametrize('fault', ['stream', 'pump', 'cleanup'])
def test_faults_preserve_native_and_do_not_claim_an_accepted_optical_record(tmp_path, fault):
    rig, result, native = run_single(tmp_path, fault=fault)
    assert not native['optical_valid']
    assert len(rig.fires) == 1
    assert not rig.laser.emission and not rig.laser.armed and rig.laser.closed
    assert result['acquisition_error'] or result['cleanup']['errors']
    if fault != 'cleanup':
        assert result['cleanup']['safe_state_and_retained_settings_verified']


def test_unpumped_scan_still_requires_explicit_emission_authorization(tmp_path):
    with pytest.raises(PermissionError):
        air.run_air_scan(tmp_path, cancel=Rig().cancel, progress=lambda _: None, single_detector=True)


def test_stable_high_dio17_is_observed_before_trigger_and_is_not_an_optical_pump_claim(tmp_path):
    rig, result, native = run_single(tmp_path, baseline_high=True)
    assert result['acquisition_error'] is None, result
    assert result['capture_completed'] and native['optical_valid']
    assert len(rig.fires) == 1
    baseline = native['pump_sync_baseline']
    assert baseline['stable'] and baseline['high'] and baseline['observed_before_process_trigger']
    assert baseline['sample_count'] >= 2
    assert baseline['last_tick'] == native['pre_process_last_timing_tick']
    assert native['observed_pump_sync_transitions'] == 0
    assert not native['optical_pump_absence_verified']
    assert any('does not verify optical pump absence' in warning for warning in native['warnings'])


@pytest.mark.parametrize('baseline_high', [False, True])
def test_either_transition_polarity_is_rejected_after_trigger(tmp_path, baseline_high):
    rig, result, native = run_single(tmp_path, fault='pump', baseline_high=baseline_high)
    assert 'pump sync transition/change during unpumped capture' in result['acquisition_error']
    assert len(rig.fires) == 1 and not native['optical_valid']
    assert native['pump_events'] is None and result['pump_events'] is None
    assert native['observed_pump_sync_transitions'] >= 1
    polarity = 'falling' if baseline_high else 'rising'
    assert native[f'observed_pump_sync_{polarity}_edges'] >= 1


def test_unstable_pretrigger_dio17_is_rejected_without_firing(tmp_path):
    rig, result, native = run_single(tmp_path, fault='pretrigger_pump')
    assert 'before Process Trigger' in result['acquisition_error']
    assert not rig.fires and not native['optical_valid']
    assert not native['pump_sync_baseline']['stable']
    assert native['pump_sync_baseline']['high'] is None
    assert native['pump_events'] is None
    assert result['cleanup']['safe_state_and_retained_settings_verified']


def fast_rehearsal_profile():
    return air.single_detector_scan_profile({
        'scan_start_cm1': 1950., 'scan_stop_cm1': 1940., 'scan_rate_cm1_s': 10000.,
        'marker_width_us': 125, 'sweep_duration_bounds_s': [.0005, .005],
    })


def test_fast_rehearsal_accepts_observed_duration_and_routes_only_to_timing_analysis(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace
    analyzed = []
    def timing_analysis(directory, record):
        assert (directory / 'hf2li_native.npz').is_file()
        assert record['record_role'] == 'pump_off_timing_rehearsal'
        assert record['capture_completed'] and record['optical_valid']
        assert not record['usable_as_background'] and not record['usable_for_ratio']
        assert not record['spectral_analysis_allowed']
        analyzed.append(record)
        return {'analysis_kind': 'timing_only', 'usable_as_background': False, 'usable_for_ratio': False}
    monkeypatch.setitem(sys.modules, 'control_app.workflows.single_detector_timing_analysis',
                        SimpleNamespace(analyze_single_detector_timing_rehearsal=timing_analysis))
    rig, result, native = run_single(tmp_path, kind='timing_rehearsal', settings=fast_rehearsal_profile(), baseline_high=True)
    assert result['acquisition_error'] is None and result['save_errors'] == []
    assert result['cleanup']['safe_state_and_retained_settings_verified']
    assert len(rig.fires) == len(analyzed) == 1
    assert rig.marker_width_set == native['marker_width_us_readback'] == 125
    ticks = native['observed_sweep_active_ticks'][0]
    assert (ticks[1] - ticks[0]) / native['clockbase_hz'] == pytest.approx(.0023, abs=5e-6)
    assert native['scan_profile']['nominal_sweep_duration_s'] == .001
    assert native['applied_sweep_duration_bounds_s'] == [.0005, .005]
    assert result['analysis']['analysis_kind'] == 'timing_only'
    assert not (Path(result['path']) / 'spectrum.json').exists()


def test_regular_blank_still_rejects_fast_duration_outside_default_strict_bounds(tmp_path):
    profile = fast_rehearsal_profile()
    del profile['sweep_duration_bounds_s']
    _, result, native = run_single(tmp_path, settings=profile)
    assert 'duration is inconsistent' in result['acquisition_error']
    assert not native['optical_valid'] and 'analysis' not in result


@pytest.mark.parametrize('key,value', [
    ('sweep_duration_bounds_s', [0, .005]), ('sweep_duration_bounds_s', [.005, .0005]),
    ('sweep_duration_bounds_s', [.002, .005]), ('sweep_duration_bounds_s', [.0005, float('inf')]),
    ('sweep_duration_bounds_s', [.0005]), ('marker_width_us', 0), ('marker_width_us', 125.5),
    ('marker_width_us', 500), ('marker_width_us', 65536),
])
def test_invalid_rehearsal_timing_rejects_before_any_device_is_opened(tmp_path, key, value):
    profile = fast_rehearsal_profile()
    profile[key] = value
    def no_hardware(*args, **kwargs):
        raise AssertionError('Invalid timing opened hardware')
    with pytest.raises(ValueError):
        air.run_air_scan(tmp_path, cancel=Rig().cancel, progress=lambda _: None, laser_authorized=True,
                        single_detector=True, record_kind='timing_rehearsal', settings=profile,
                        laser_factory=no_hardware, hf_factory=no_hardware, t660_factory=no_hardware,
                        picoscope_factory=no_hardware)
    assert not list(tmp_path.iterdir())


def test_relaxed_timing_bounds_cannot_be_applied_to_a_buffer_blank(tmp_path):
    with pytest.raises(ValueError, match='only for timing_rehearsal'):
        run_single(tmp_path, settings=fast_rehearsal_profile())
