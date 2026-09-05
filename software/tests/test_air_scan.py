"""Exercise the real air-scan workflow with independent, hardware-free transports."""
from copy import deepcopy
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest

from control_app.workflows import air_scan as air
from control_app.workflows.phase_scan_data import load_native
from test_phase_scan_acquisition import Timer


class FastCancel(Event):
    def wait(self, timeout=None):
        return self.is_set()


class Rig:
    def __init__(self):
        self.units = {}
        self.fires = []
        self.fail_stop = False
        self.clipped = False
        self.missing_clip = False
        self.bad_hf = False
        self.bad_qcl = False
        self.fail_capture = False
        self.cancel_capture = False
        self.start_cancel = False
        self.gate_needs_enable = False
        self.gate_fails = False
        self.gate_fails_after_start = False
        self.gate_reported_on_before_start = False
        self.gate_call_stages = []
        self.cancel_during_tune = False
        self.cancel_mode_failure = False
        self.trigger_mode_changes_at = None
        self.start_called = False
        self.cancel = FastCancel()
        self.events = []
        self.now = 0.
        self.laser = None
        self.hf = None
        self.pico = None

    def run(self, root):
        return air.run_air_scan(root, cancel=self.cancel, progress=self.events.append,
                                laser_authorized=True, pump_blocked=True,
                                laser_factory=lambda **kw: FakeLaser(self),
                                hf_factory=lambda **kw: FakeHF(self),
                                t660_factory=lambda name, **kw: AirTimer(self, name),
                                picoscope_factory=lambda device, settings, **kw: FakePico(self, settings),
                                tec_ready_stability_s=0.)


class AirTimer(Timer):
    def fire_remote_trigger(self):
        assert self.world.pico.armed, 'process trigger preceded Pico EXT arm'
        assert self.name == 't660_1' and self.source == 'REM'
        assert self.channels['C']['enabled']
        assert all(not self.channels[c]['enabled'] for c in 'ABD')
        self.shots += 1
        self.world.fires.append(deepcopy(self.channels))
        self.world.laser.triggered = True


class FakeLaser:
    def __init__(self, rig):
        rig.laser = self
        self.rig = rig
        self.params = {'pulse_rate_hz': 2100000., 'pulse_width_ns': 142., 'current_ma': 750.}
        self.emission = self.armed = self.started = self.triggered = False
        self.closed = False
        self.ever_armed = False
        self.tuned = self.manual_tune = False

    def initialize(self): pass
    def deinitialize(self): self.closed = True
    def is_interlock_set(self): return True
    def is_key_switch_set(self): return True
    def get_system_error_word(self): return 0
    def cancel_manual_tune(self):
        if self.manual_tune:
            assert not self.rig.units['t660_2'].channels['B']['enabled']
            self.rig.events.append('cancel manual tune')
            if self.rig.cancel_mode_failure:
                raise RuntimeError('manual tune cancellation failed')
            if self.rig.trigger_mode_changes_at == 'after_manual_tune_cancel':
                self.trigger['pulse_mode'] = 1
        self.manual_tune = False
    def tune_to_wavenumber(self, wavenumber, *, qcl):
        assert wavenumber == 2050 and qcl == 1 and self.armed
        assert not self.rig.units['t660_2'].channels['B']['enabled']
        self.rig.events.append('tune to start')
        self.tuned = self.manual_tune = True
        if self.rig.cancel_during_tune:
            self.rig.cancel.set()
    def is_tuned(self): return self.tuned
    def set_red_laser_pointer_enabled(self, enabled): assert not enabled
    def stop_scan_if_needed(self): self.started = False
    def turn_emission_off(self): self.emission = False
    def turn_emission_on(self, *, approved_laser_safety_condition):
        assert approved_laser_safety_condition and self.armed and self.tuned
        if not self.started:
            assert not self.rig.units['t660_2'].channels['B']['enabled']
        self.rig.gate_call_stages.append('after_start' if self.started else 'before_start')
        self.rig.events.append('explicit gate enable')
        self.emission = not (self.rig.gate_fails or (self.started and self.rig.gate_fails_after_start))
    def disarm(self): self.armed = False
    def is_emission_on(self): return self.emission
    def is_laser_armed(self): return self.armed
    def get_qcl_tuning_range(self, qcl): return {'min_cm1': 1600., 'max_cm1': 2100.}
    def get_qcl_pulse_limits(self, qcl):
        return {'max_pulse_rate_hz': 3e6, 'max_pulse_width_ns': 500., 'max_duty_cycle': 30.}
    def get_qcl_current_limits(self, qcl): return 100., 1500.
    def get_qcl_current(self, qcl): return self.params['current_ma']
    def get_qcl_pulse_rate(self, qcl): return self.params['pulse_rate_hz']
    def get_qcl_pulse_width(self, qcl): return self.params['pulse_width_ns']
    def set_qcl_pulse_params(self, **kwargs): self.params = kwargs
    def set_external_sweep_trigger_params(self, **kwargs):
        self.trigger = {'pulse_mode': 2, 'process_trigger_mode': 2, 'units': 2,
                        'pulse_mode_name': 'external_trigger', 'process_trigger_mode_name': 'external',
                        'units_name': 'cm^-1', 'dwell_us': 0, 'after_off_us': 0,
                        'start': kwargs['start_cm1'], 'stop': kwargs['stop_cm1'],
                        'interval': kwargs['wavelength_trigger_interval_cm1']}
        return self.trigger
    def get_wavelength_trigger_params(self): return self.trigger
    def set_wavelength_trigger_pulse_width_us(self, width): return width
    def arm(self):
        self.armed = self.ever_armed = True
        self.emission = self.rig.gate_reported_on_before_start
    def are_tecs_ready(self): return True
    def start_sweep_scan(self, **kwargs):
        self.rig.start_called = True
        assert not self.manual_tune, 'StartSweepScan requires leaving manual tune mode'
        self.rig.events.append('start sweep SDK')
        assert kwargs == {'start_cm1': 2050, 'stop_cm1': 1650, 'scan_rate_cm1_s': 40,
                          'qcl': 1, 'repetitions': 1}
        self.started = self.emission = True
        if self.rig.trigger_mode_changes_at == 'after_sweep_setup':
            self.trigger['pulse_mode'] = 1
        if self.rig.gate_needs_enable:
            self.emission = False
        if self.rig.bad_qcl:
            self.params['pulse_rate_hz'] = 2e6
        if self.rig.start_cancel:
            self.rig.cancel.set()
    def get_scan_waiting_process_trigger(self): return self.started and not self.triggered
    def get_scan_status(self): return {'scan_in_progress': self.started}
    def read_state(self):
        return SimpleNamespace(to_dict=lambda: {'emission_on': self.emission, 'armed': self.armed})


def hf_snapshot():
    nodes = {}
    for i in range(6):
        values = {'enable': int(i in (0, 2, 3)), 'order': 4, 'trigger': 0, 'harmonic': 1,
                  'oscselect': 0, 'adcselect': int(i == 3), 'timeconstant': .0010018887078828383,
                  'rate': 28782.894736842107 if i == 2 else 1798.9309210526317}
        nodes.update({f'/fake/demods/{i}/{k}': {'type': 'double' if isinstance(v, float) else 'int', 'value': v}
                      for k, v in values.items()})
    for i in (0, 1):
        nodes.update({f'/fake/sigins/{i}/{k}': {'type': 'double' if k == 'range' else 'int', 'value': v}
                      for k, v in {'range': 2.015, 'ac': 0, 'imp50': 1, 'diff': 0}.items()})
    nodes.update({f'/fake/plls/0/{k}': {'type': 'int', 'value': v} for k, v in
                  {'enable': 1, 'adcselect': 4, 'freqcenter': 2e6, 'harmonic': 1, 'order': 4, 'adcthreshold': 0}.items()})
    return {'nodes': nodes, 'read_errors': {}}


class FakeHF:
    device_id = 'fake'
    compare_settings_snapshots = air.HF2LIService.compare_settings_snapshots

    def __init__(self, rig):
        rig.hf = self
        self.rig = rig
        self.snapshot = hf_snapshot()
        self.cursor = 0.
        self.closed = False
        if rig.bad_hf:
            self.snapshot['nodes']['/fake/demods/3/rate']['value'] = 224.866
    def connect(self): pass
    def close(self): self.closed = True
    def apply_preset(self, preset): self.preset = preset
    def export_settings_snapshot(self, **kwargs): return deepcopy(self.snapshot)
    def _get_node(self, kind, path):
        if '/adcclip/' in path:
            if self.rig.missing_clip: raise RuntimeError('status unavailable')
            return int(self.rig.clipped)
        if '/status/' in path: return -128 if self.rig.clipped else 0
        return self.snapshot['nodes'][path]['value']
    def get_oscillator_frequency(self, index): return 2e6
    def get_clockbase(self): return 210e6
    def start_acquisition(self, **kwargs): self.active = True
    def stop_acquisition(self): self.active = False
    def read_acquisition(self, duration):
        # Low/high/low Sweep Active and 80 resolved rising markers at 0.125 s spacing.
        count = 3000 if self.rig.laser.triggered else 50
        times = self.cursor+np.arange(count)*.004
        self.cursor = float(times[-1]+.004)
        dio = np.zeros(count, dtype=np.uint32)
        inside = (times >= 1.) & (times < 11.)
        dio[inside] |= 1 << 21
        dio[inside & (np.mod(times-1., .125) < .004)] |= 1 << 22
        data = {}
        for demod in (0, 2, 3):
            data[f'/fake/demods/{demod}/sample'] = {
                'timestamp': np.rint(times*210e6).astype(np.uint64)+np.uint64(2**60),
                'x': np.ones(count)*(.1 if demod == 0 else .2), 'y': np.zeros(count),
                'dio': dio, 'auxin0': np.zeros(count), 'auxin1': np.zeros(count)}
        return {'data': data}


class FakePico:
    def __init__(self, rig, settings):
        rig.pico = self
        self.rig, self.settings = rig, settings
        self.armed = self.closed = False
    def open_unit(self): pass
    def close_unit(self): self.closed = True
    def stop(self): pass
    def apply_capture_settings(self):
        assert self.settings['external_trigger'] == {'source': 'EXT', 'threshold_adc': 5000,
                                                     'direction': 2, 'delay_samples': 0, 'auto_trigger_ms': 0}
    def validate_sample_timing(self): return {'sample_interval_ns': 48., 'max_samples': 268435456}
    def capture_block_data(self, *, after_arm, while_waiting, before_transfer):
        self.armed = True
        if self.rig.trigger_mode_changes_at == 'before_process_trigger':
            self.rig.laser.trigger['pulse_mode'] = 1
        after_arm()
        if self.rig.cancel_capture: self.rig.cancel.set()
        if self.rig.fail_capture: raise RuntimeError('EXT trigger timeout')
        while_waiting()
        before_transfer()
        assert not self.rig.laser.emission and not self.rig.laser.armed
        assert all(not u.channels[c]['enabled'] for u in self.rig.units.values() for c in 'ABCD')
        count = self.settings['total_samples']
        return {'sample_interval_ns': 48., 'total_samples': count, 'pre_trigger_samples': 209,
                'overflow': 0, 'maximum_adc_value': 32512,
                'ch_a_adc': np.ones(count, dtype=np.int16)*100,
                'ch_b_adc': np.ones(count, dtype=np.int16)*200}


@pytest.fixture
def rig(monkeypatch):
    # Keep transport tests small; the real fixed profile's memory contract is checked separately.
    monkeypatch.setattr(air, 'PICO_SETTINGS', {**air.PICO_SETTINGS, 'total_samples': 200000})
    return Rig()


def assert_idle(rig):
    assert rig.laser.closed and not rig.laser.emission and not rig.laser.armed
    assert rig.pico.closed and rig.hf.closed
    assert all(not u.channels[c]['enabled'] for u in rig.units.values() for c in 'ABCD')


def test_full_run_retains_settings_saves_both_detectors_and_plots_without_pump(rig, tmp_path):
    result = rig.run(tmp_path)
    assert result['acquisition_error'] is None, result
    assert result['cleanup']['errors'] == []
    assert result['save_errors'] == []
    assert 'analysis_error' not in result, result
    assert len(rig.fires) == 1
    assert_idle(rig)
    assert rig.hf.preset.settings['demodulators'][0]['rate_sps'] == pytest.approx(1798.9309210526317)
    assert all(channel['range_v'] == 2.0 for channel in rig.hf.preset.settings['signal_inputs'].values())
    assert rig.laser.params['current_ma'] == 750
    assert rig.laser.params['pulse_rate_hz'] == 2.1e6
    root = Path(result['path'])
    assert (root/'air_scan.png').is_file() and (root/'detectors.csv').is_file()
    assert np.load(root/'picoscope_ch_b_adc.npy').size == 200000
    native = load_native(root/'hf2li_native.npz')
    assert native['clockbase_hz'] == 210e6 and native['pump_events'] == 0
    assert not result['analysis']['publication_eligible']
    assert not result['analysis']['accepted_as_background']
    assert 'PROVISIONAL' in result['analysis']['wavenumber_basis']
    second = rig.run(tmp_path)
    assert second['path'] != result['path']
    assert (root/'hf2li_native.npz').is_file()


@pytest.mark.parametrize('fault, message', [
    ('bad_hf', 'expected'), ('bad_qcl', 'QCL mismatch'),
    ('fail_capture', 'EXT trigger timeout'), ('cancel_capture', 'stopped by operator'),
    ('start_cancel', 'stopped by operator'),
])
def test_faults_stop_outputs_and_preserve_native_records(rig, tmp_path, fault, message):
    setattr(rig, fault, True)
    result = rig.run(tmp_path)
    assert message in result['acquisition_error'], result
    assert_idle(rig)
    assert (Path(result['path'])/'hf2li_native.npz').exists()
    assert not result['cleanup']['errors']
    if fault == 'bad_hf':
        assert not rig.start_called and not rig.laser.ever_armed and not rig.fires
    if fault in ('bad_qcl', 'start_cancel'):
        assert not rig.fires


@pytest.mark.parametrize('condition, warning', [('clipped', 'clipped'), ('missing_clip', 'status unavailable')])
def test_clipping_is_nonfatal_and_preserved_in_native_data_and_plots(rig, tmp_path, condition, warning):
    setattr(rig, condition, True)
    result = rig.run(tmp_path)
    assert result['capture_completed'] and result['acquisition_error'] is None
    assert 'analysis_error' not in result
    assert rig.start_called and len(rig.fires) == 1
    assert_idle(rig)
    assert any(warning in message for message in result['warnings'])
    native = load_native(Path(result['path'])/'hf2li_native.npz')
    assert native['warnings'] == result['warnings']
    assert native['scan_profile']['clipping_policy'] == 'warn_and_continue'
    assert {item['context'] for item in native['hf2li_input_checks']} >= {
        'baseline', 'before_sweep_setup', 'before_process_trigger', 'during_capture', 'after_transfer'}
    assert 'CLIPPED' in result['analysis']['detector_status']
    assert not result['analysis']['accepted_as_background']
    assert (Path(result['path'])/'air_scan.png').exists()


def test_stop_requested_before_execute_never_connects(tmp_path):
    calls = []
    runner = air.AirScanRunner(available=True, before_acquire=lambda: calls.append('handoff'))
    with pytest.raises(PermissionError):
        runner.execute(tmp_path)
    runner.abort()
    with pytest.raises(InterruptedError):
        runner.execute(tmp_path, laser_authorized=True, pump_blocked=True)
    assert not calls


def test_fixed_profile_covers_ten_seconds_and_keeps_distinct_timing_roles():
    assert air.PICO_SETTINGS['total_samples']*48e-9 > 10.5
    assert air.PICO_SETTINGS['total_samples'] < 268435456
    profile = air.AIR_SCAN_PROFILE
    assert profile['external_rate_hz'] == 2e6
    assert profile['mircat_internal_rate_hz'] == 2.1e6
    assert profile['mircat_internal_rate_hz']*profile['mircat_internal_width_ns']*1e-9 < .30
    assert profile['tec_ready_stability_s'] == 5.


def test_custom_profile_can_request_slower_full_duration_pico_capture():
    profile = {**air.AIR_SCAN_PROFILE, 'nominal_sweep_duration_s': 50.,
               'picoscope_timebase': 27, 'picoscope_sample_interval_ns': 200.,
               'picoscope_capture_role': 'full-duration detector-envelope witness'}
    settings, interval_ns = air.picoscope_settings_for_profile(profile, custom_profile=True)
    assert interval_ns == 200.
    assert settings['timebase'] == 27
    assert settings['total_samples'] == 262501459
    assert settings['total_samples'] < 268435456
    assert settings['timeout_s'] == 70.


def test_cleanup_failure_prevents_another_start(tmp_path):
    calls = []
    def acquire(*args, **kwargs):
        calls.append(True)
        return {'cleanup': {'safe_state_and_retained_settings_verified': False}}
    runner = air.AirScanRunner(available=True, acquire=acquire)
    runner.execute(tmp_path, laser_authorized=True, pump_blocked=True)
    with pytest.raises(RuntimeError, match='Previous shutdown'):
        runner.execute(tmp_path, laser_authorized=True, pump_blocked=True)
    assert len(calls) == 1


def test_clipped_captured_record_keeps_diagnostic_plot_without_ratio(rig, tmp_path):
    result = rig.run(tmp_path)
    directory = Path(result['path'])
    native = load_native(directory/'hf2li_native.npz')
    # Clipping seen only before the scan must remain visible in its diagnostic plot.
    native['hf2li_input_checks'] = [{'context': 'baseline', 'status': {'status/flags/adcclip/0': 0,
                                                                    'status/flags/adcclip/1': 1}}]
    # A new derived directory, preserving the first analysis and native sources.
    import shutil
    from control_app.workflows.air_scan_analysis import analyze_air_scan
    child = directory/'clipping_diagnostic'
    child.mkdir()
    for name in ('picoscope_ch_a_adc.npy', 'picoscope_ch_b_adc.npy'):
        shutil.copyfile(directory/name, child/name)
    analysis = analyze_air_scan(child, native)
    assert analysis['channels']['2']['clipped_checks'] == 1
    assert 'CLIPPED' in analysis['detector_status']
    assert not (child/'ratio.csv').exists()


@pytest.mark.parametrize('fails', [False, True])
def test_emission_gate_is_reopened_if_scan_setup_closes_it(rig, tmp_path, fails):
    rig.gate_needs_enable = True
    rig.gate_fails_after_start = fails
    result = rig.run(tmp_path)
    assert rig.gate_call_stages == ['before_start', 'after_start']
    assert len(rig.fires) == (0 if fails else 1)
    assert bool(result['acquisition_error']) == fails
    assert_idle(rig)


@pytest.mark.parametrize('reported_on', [False, True])
def test_emission_on_command_precedes_scan_start_even_if_sdk_already_reports_on(rig, tmp_path, reported_on):
    rig.gate_reported_on_before_start = reported_on
    result = rig.run(tmp_path)
    assert result['acquisition_error'] is None
    assert rig.gate_call_stages == ['before_start']
    assert (rig.events.index('tune to start') < rig.events.index('explicit gate enable') <
            rig.events.index('cancel manual tune') < rig.events.index('start sweep SDK'))
    saved = json.loads((Path(result['path'])/'mircat_emission_before_scan.json').read_text())
    assert saved['sdk_command'] == 'MIRcatSDK_TurnEmissionOn'
    assert saved['emission_on_readback'] is True
    native = load_native(Path(result['path'])/'hf2li_native.npz')
    assert native['emission_gate_on_before_scan'] is True
    assert native['manual_tune_cancelled_before_scan'] is True
    assert native['optical_valid'] is False  # SDK status alone is not optical evidence.
    assert_idle(rig)


def test_failed_emission_readback_prevents_scan_start_and_process_trigger(rig, tmp_path):
    rig.gate_fails = True
    result = rig.run(tmp_path)
    assert 'before scan start' in result['acquisition_error']
    assert rig.gate_call_stages == ['before_start']
    assert not rig.start_called and not rig.fires
    assert_idle(rig)


@pytest.mark.parametrize('transition', [
    'after_manual_tune_cancel', 'after_sweep_setup', 'before_process_trigger'])
def test_external_mode_loss_is_recorded_and_never_fires_process_even_with_gate_on(rig, tmp_path, transition):
    rig.trigger_mode_changes_at = transition
    result = rig.run(tmp_path)
    assert f'external trigger settings changed at {transition}' in result['acquisition_error']
    assert not rig.fires
    if transition == 'after_manual_tune_cancel':
        assert not rig.start_called
    else:
        assert rig.start_called
    check = json.loads((Path(result['path'])/f'mircat_trigger_{transition}.json').read_text())
    assert check['mismatch']['pulse_mode'] == {'actual': 1, 'expected': 2}
    assert not check['optical_output_verified']
    assert_idle(rig)


def test_external_mode_is_rechecked_after_transitions_without_claiming_optical_output(rig, tmp_path):
    result = rig.run(tmp_path)
    assert result['acquisition_error'] is None
    native = load_native(Path(result['path'])/'hf2li_native.npz')
    checks = native['mircat_trigger_checks']
    assert [item['context'] for item in checks] == [
        'after_manual_tune_cancel', 'after_sweep_setup', 'before_process_trigger']
    assert all(item['readback']['pulse_mode'] == 2 and not item['mismatch'] for item in checks)
    assert all(not item['optical_output_verified'] for item in checks)
    assert not native['optical_valid']


@pytest.mark.parametrize('fault', ['cancel_during_tune', 'cancel_mode_failure'])
def test_tune_preparation_fault_never_starts_sweep(rig, tmp_path, fault):
    setattr(rig, fault, True)
    result = rig.run(tmp_path)
    assert result['acquisition_error'] is not None
    assert not rig.start_called and not rig.fires
    assert_idle(rig)


def test_observed_pll_quantization_passes_but_internal_rate_as_reference_fails():
    snapshot = hf_snapshot()
    snapshot['nodes']['/fake/plls/0/freqcenter']['value'] = 2000012.3977661133
    air.verify_hf_settings(snapshot, 'fake')
    snapshot['nodes']['/fake/plls/0/freqcenter']['value'] = 2100000.
    with pytest.raises(RuntimeError, match='freqcenter'):
        air.verify_hf_settings(snapshot, 'fake')


def test_live_two_volt_range_readbacks_pass_and_lower_range_is_rejected():
    snapshot = hf_snapshot()
    for index, value in enumerate((2.014782648377699, 2.0164402001630966)):
        snapshot['nodes'][f'/fake/sigins/{index}/range']['value'] = value
    air.verify_hf_settings(snapshot, 'fake')
    snapshot['nodes']['/fake/sigins/1/range']['value'] = 1.0144783062439409
    with pytest.raises(RuntimeError, match='requested 2 V'):
        air.verify_hf_settings(snapshot, 'fake')


def test_mircat_control_values_drive_plan_and_invalid_duty_or_duration_is_rejected():
    plan = air.settings_from_mircat_controls({'scan_start_cm1': 2000, 'scan_stop_cm1': 1800,
                                           'scan_rate_cm1_s': 40, 'current_ma': 725})
    assert plan['nominal_sweep_duration_s'] == 5 and plan['qcl_current_ma'] == 725
    with pytest.raises(ValueError, match='at most'):
        air.settings_from_mircat_controls({'scan_rate_cm1_s': 1})
    with pytest.raises(ValueError, match='duty'):
        air.settings_from_mircat_controls({'scan_internal_width_ns': 150})
