"""Exploratory standalone air scan. Construction and import never access hardware.

The fixed profile is independent of Phase Scan. Numeric settings persist;
IR emission and timing outputs are stopped on completion, failure and Stop.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread
import math
import time
import traceback

import numpy as np

from control_app.config_loader import load_hardware_config
from control_app.devices.hf2li_service import HF2LIService, HF2LIPreset
from control_app.devices.mircat_service import MircatService
from control_app.devices.picoscope_service import PicoScopeService
from control_app.devices.t660_service import T660Service
from control_app.workflows.phase_scan_data import write_json, save_native
from control_app.workflows.timing_recipe_manager import TimingRecipeManager

# Operator-confirmed LabOne setting, verified on dev18500 by live SDK readback.
HF2LI_SCAN_INPUT_RANGE_V = 2.0

AIR_SCAN_PROFILE = {
    'start_cm1': 2050., 'stop_cm1': 1650., 'scan_rate_cm1_s': 40.,
    'nominal_sweep_duration_s': 10., 'qcl_current_ma': 750., 'qcl': 1,
    'external_rate_hz': 2_000_000., 'external_width_ns': 150.,
    'mircat_internal_rate_hz': 2_100_000., 'mircat_internal_width_ns': 142.,
    'tec_ready_stability_s': 5.,
    'optical_triggering': 'EXTERNAL', 'process_triggering': 'EXTERNAL',
    'detector_rate_sps': 1798.9309210526317, 'timing_rate_sps': 28782.894736842107,
    'timeconstant_s': .0010018887078828383, 'filter_order': 4,
    'hf2li_input_range_v': HF2LI_SCAN_INPUT_RANGE_V, 'clipping_policy': 'warn_and_continue',
    'marker_interval_cm1': 5., 'marker_width_us': 500, 'expected_markers': 81,
    'independent_of_phase_scan': True, 'pump_events': 0,
    'channel_labels': ['Input 1 / Pico A', 'Input 2 / Pico B'],
    'picoscope_trigger_basis': 'MIRcat DB9 pin 2 Sweep Active; pin 7 ground',
    'picoscope_timebase': 8, 'picoscope_sample_interval_ns': 48.,
    'picoscope_capture_role': 'full-duration detector record with optical-pulse sampling',
}
IDLE = {'trigger_source': 'OFF', 'channels': {c: {'enabled': False} for c in 'ABCD'}}
PICO_SETTINGS = {
    'resolution': '8BIT', 'channels': {
        'A': {'enabled': True, 'coupling': 'DC', 'range': '5V', 'analog_offset_v': 0.},
        'B': {'enabled': True, 'coupling': 'DC', 'range': '10V', 'analog_offset_v': 0.}},
    'external_trigger': {'source': 'EXT', 'threshold_adc': 5000, 'direction': 2,
                         'delay_samples': 0, 'auto_trigger_ms': 0},
    'timebase': 8, 'total_samples': 218755418, 'pre_trigger_samples': 209, 'timeout_s': 30.,
}


def picoscope_settings_for_profile(profile, *, custom_profile=False):
    """Build a full-duration Pico recipe and retain an explicit timing contract."""
    settings = deepcopy(PICO_SETTINGS)
    timebase = int(profile.get('picoscope_timebase', settings['timebase']))
    interval_ns = float(profile.get('picoscope_sample_interval_ns', 48.))
    if timebase < 0 or not math.isfinite(interval_ns) or interval_ns <= 0:
        raise ValueError('PicoScope timebase and sample interval must be positive and finite')
    settings['timebase'] = timebase
    if custom_profile:
        duration_s = float(profile['nominal_sweep_duration_s'])*1.05+.00025
        settings['total_samples'] = math.ceil(duration_s/(interval_ns*1e-9))+209
        settings['timeout_s'] = max(30., float(profile['nominal_sweep_duration_s'])+20.)
    return settings, interval_ns


def settings_from_mircat_controls(parameters):
    """Validate the existing MIRcat Sweep Scan fields before opening any device."""
    profile = dict(AIR_SCAN_PROFILE)
    fields = {'scan_start_cm1': 'start_cm1', 'scan_stop_cm1': 'stop_cm1',
              'scan_rate_cm1_s': 'scan_rate_cm1_s', 'current_ma': 'qcl_current_ma',
              'scan_trigger_rate_hz': 'external_rate_hz', 'scan_trigger_width_ns': 'external_width_ns',
              'scan_internal_rate_hz': 'mircat_internal_rate_hz',
              'scan_internal_width_ns': 'mircat_internal_width_ns'}
    for field, target in fields.items():
        value = float(parameters.get(field, profile[target]))
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f'{field} must be positive and finite')
        profile[target] = value
    if int(parameters.get('scan_repetitions', 1)) != 1:
        raise ValueError('This exploratory sweep supports one scan per Start; use Start again to repeat')
    profile['qcl'] = int(parameters.get('qcl', 1))
    if not 1 <= profile['qcl'] <= 4:
        raise ValueError('Select an installed QCL from 1 through 4')
    duration = abs(profile['stop_cm1']-profile['start_cm1'])/profile['scan_rate_cm1_s']
    if duration <= 0 or math.ceil((duration*1.05+.00025)/48e-9)+209 > 268435456:
        raise ValueError('Choose distinct endpoints and a rate giving a sweep of at most 12.27 s for full Pico capture')
    if profile['mircat_internal_rate_hz'] <= profile['external_rate_hz']:
        raise ValueError('MIRcat internal rate must exceed the external T660 trigger rate')
    for rate, width in (('external_rate_hz', 'external_width_ns'),
                        ('mircat_internal_rate_hz', 'mircat_internal_width_ns')):
        if profile[rate]*profile[width]*1e-9 > .30+1e-9:
            raise ValueError('Pulse duty must not exceed 30%')
    profile['nominal_sweep_duration_s'] = duration
    profile['expected_markers'] = int(abs(profile['stop_cm1']-profile['start_cm1'])/5)+1
    return profile


def air_scan_preset(external_rate_hz=2_000_000.):
    """Separate fixed scan profile; never rewrite the saved Phase Scan preset."""
    return HF2LIPreset('exploratory_standalone_air_10s', {
        'signal_inputs': {f'ch{i+1}': {'index': i, 'ac': False, 'impedance_50ohm': True,
                                     'differential': False, 'range_v': HF2LI_SCAN_INPUT_RANGE_V} for i in (0, 1)},
        'pll': {'index': 0, 'enable': True, 'adcselect': 4, 'freqcenter_hz': external_rate_hz,
                'harmonic': 1, 'order': 4, 'adcthreshold': 0},
        'demodulators': [
            {'index': i, 'enable': True, 'adcselect': 1 if i == 3 else 0,
             'oscselect': 0, 'harmonic': 1, 'order': 4, 'timeconstant_s': .001,
             'rate_sps': AIR_SCAN_PROFILE['timing_rate_sps' if i == 2 else 'detector_rate_sps'],
             'trigger': 0} for i in (0, 2, 3)
        ] + [{'index': i, 'enable': False} for i in (1, 4, 5)],
    })


def verify_hf_settings(snapshot, device, external_rate_hz=2_000_000.):
    if snapshot.get('read_errors'):
        raise RuntimeError('HF2LI settings could not be read back')
    expected = {}
    for i in (0, 2, 3):
        expected.update({f'demods/{i}/{k}': v for k, v in {
            'enable': 1, 'order': 4, 'trigger': 0, 'harmonic': 1, 'oscselect': 0,
            'adcselect': 1 if i == 3 else 0, 'timeconstant': AIR_SCAN_PROFILE['timeconstant_s'],
            'rate': AIR_SCAN_PROFILE['timing_rate_sps' if i == 2 else 'detector_rate_sps']}.items()})
    for i in (1, 4, 5):
        expected[f'demods/{i}/enable'] = 0
    for i in (0, 1):
        expected.update({f'sigins/{i}/{k}': v for k, v in {'ac': 0, 'imp50': 1, 'diff': 0}.items()})
        value = snapshot['nodes'][f'/{device}/sigins/{i}/range']['value']
        # The device returns its calibrated range, which differs slightly from the request.
        if not math.isclose(value, HF2LI_SCAN_INPUT_RANGE_V, rel_tol=.03):
            raise RuntimeError(f'HF2LI input {i+1} range readback {value} does not match the requested 2 V setting')
    expected.update({f'plls/0/{k}': v for k, v in {
        'enable': 1, 'adcselect': 4, 'freqcenter': external_rate_hz, 'harmonic': 1, 'order': 4,
        'adcthreshold': 0}.items()})
    for node, wanted in expected.items():
        actual = snapshot['nodes'][f'/{device}/{node}']['value']
        tolerance = max(20., external_rate_hz*1e-5) if node == 'plls/0/freqcenter' else 1e-9
        if not math.isclose(actual, wanted, rel_tol=1e-6, abs_tol=tolerance):
            raise RuntimeError(f'HF2LI {node}: read {actual}, expected {wanted}')


def hf_input_status(hf):
    status = {}
    for node in ('status/adc0max', 'status/adc0min', 'status/adc1max', 'status/adc1min',
                 'status/flags/adcclip/0', 'status/flags/adcclip/1', 'status/flags/binary'):
        try:
            status[node] = hf._get_node('int', f'/{hf.device_id}/{node}')
        except Exception as exc:
            status[node] = {'read_error': str(exc)}
    return status


def clipping_warnings(status):
    """Clipping is diagnostic information and never inhibits this exploratory sweep."""
    clipped = []
    unavailable = []
    for index in (0, 1):
        value = status.get(f'status/flags/adcclip/{index}')
        if not isinstance(value, (int, np.integer)):
            unavailable.append(str(index+1))
        elif value:
            clipped.append(str(index+1))
    messages = []
    if clipped:
        subject = 'Input ' + clipped[0] + ' is' if len(clipped) == 1 else 'Inputs ' + ' and '.join(clipped) + ' are'
        messages.append(f'HF2LI {subject} clipped; continuing diagnostic acquisition.')
    if unavailable:
        messages.append('HF2LI Input ' + ' and '.join(unavailable) + ' clipping status unavailable; continuing diagnostic acquisition.')
    return messages


class AirScanRunner:
    def __init__(self, *, available=False, config_path=None, acquire=None, before_acquire=None):
        self.available = available
        self.config_path = config_path
        self.acquire = acquire or run_air_scan
        self.before_acquire = before_acquire
        self.cancel = Event()
        self._lock = Lock()
        self.cleanup_failed = False

    def abort(self):
        self.cancel.set()

    def execute(self, root, *, laser_authorized=False, pump_blocked=False, progress=lambda text: None):
        if laser_authorized is not True or pump_blocked is not True:
            raise PermissionError('Air Scan requires authorization for one IR sweep and a blocked pump')
        if self.cancel.is_set():
            raise InterruptedError('Air Scan stopped before setup')
        if not self.available:
            raise RuntimeError('Use the hardware-enabled app launcher for Air Scan')
        if self.cleanup_failed:
            raise RuntimeError('Previous shutdown was not verified. Resolve the reported hardware error before restarting the app.')
        if not self._lock.acquire(blocking=False):
            raise RuntimeError('Air Scan already owns the instruments')
        try:
            if self.before_acquire:
                self.before_acquire()
            result = self.acquire(root, cancel=self.cancel, progress=progress,
                                  laser_authorized=laser_authorized, pump_blocked=pump_blocked,
                                  config_path=self.config_path)
            self.cleanup_failed = not result['cleanup']['safe_state_and_retained_settings_verified']
            return result
        finally:
            self._lock.release()


def run_air_scan(root, *, cancel, progress, laser_authorized=False, pump_blocked=False,
                 config_path=None, laser_factory=MircatService.from_config,
                 hf_factory=HF2LIService.from_config, t660_factory=T660Service.from_config,
                 picoscope_factory=PicoScopeService, settings=None, on_state=lambda state: None,
                 tec_ready_stability_s=None):
    """One operator-started air sweep; settings remain, outputs always stop."""
    if laser_authorized is not True or pump_blocked is not True:
        raise PermissionError("Start Air Scan requires emission authorization and a blocked pump")
    if cancel.is_set():
        raise InterruptedError("Air Scan stopped before setup")
    profile = dict(AIR_SCAN_PROFILE if settings is None else settings)
    start_cm1, stop_cm1, rate = (profile[k] for k in ('start_cm1', 'stop_cm1', 'scan_rate_cm1_s'))
    current, qcl = profile['qcl_current_ma'], profile['qcl']
    external_rate, external_width = profile['external_rate_hz'], profile['external_width_ns']
    internal_rate, internal_width = profile['mircat_internal_rate_hz'], profile['mircat_internal_width_ns']
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    out = root / ('mircat_sweep_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir()
    write_json(out / 'operation.json', {
        **profile, 'authorization': 'Operator clicked MIRcat Sweep Scan Start Scan with Safety Approval',
        'pump_physically_blocked': True, 'retain_scan_settings': True,
        'automatic_retries': 0, 'publication_eligible': False,
        'run_classification': 'EXPLORATORY_PROOF_OF_CONCEPT',
    })
    record = {'schema': 'standalone-air-scan/2', 'native_chunks': [], 'optical_valid': False, 'pump_events': 0, 'independent_of_phase_scan': True, 'scan_profile': profile, 'warnings': []}
    units, laser, hf, pico, starter = {}, None, None, None, None
    cleanup_errors, error = [], None
    configured = None
    raw = None
    qcl_configured = False
    log = (out / 'commands.txt').open('x', encoding='utf-8', buffering=1)

    def stage(msg):
        # Progress/logging failures must never bypass instrument cleanup.
        try:
            progress(msg)
        except Exception:
            pass
        try:
            log.write(datetime.now(timezone.utc).isoformat() + ' ' + msg + '\n')
        except OSError:
            pass

    def publish_state():
        state = laser.read_state().to_dict()
        try:
            on_state(state)
        except Exception:
            pass
        return state

    def attempt(label, fn):
        try:
            return fn()
        except Exception as exc:
            cleanup_errors.append(label + ': ' + repr(exc))

    def stop_unit(unit):
        failures = []
        for fn in [lambda: unit.set_trigger_source('OFF'), lambda: unit.command('STOP', expect_response=False), *[lambda c=c: unit.disable_channel(c) for c in 'ABCD']]:
            try: fn()
            except Exception as exc: failures.append(str(exc))
        if unit.name == 't660_2':
            for command in ('TFRame:STOp', *(f'TRAin:{stage}:CouNT 0' for stage in ('ACTive', 'NEXT', 'QUEue'))):
                try: unit.command(command, expect_response=False)
                except Exception as exc: failures.append(str(exc))
        if failures: raise RuntimeError('; '.join(failures))

    def verify_unit(unit, recipe, name):
        rb = unit.read_active_settings()
        write_json(out / name, rb)
        mismatch = TimingRecipeManager._compare_readback({unit.name: recipe}, {unit.name: rb})
        if mismatch: raise RuntimeError(f'{unit.name} readback mismatch: {mismatch}')
        return rb

    def check_cancel():
        if cancel.is_set():
            raise InterruptedError("Air Scan stopped by operator")

    def check():
        check_cancel()
        if not laser.is_interlock_set() or not laser.is_key_switch_set():
            raise RuntimeError('MIRcat interlock/key is not closed')
        if laser.get_system_error_word(): raise RuntimeError('MIRcat system error reported')

    def verify_qcl():
        rb = {'rate_hz': laser.get_qcl_pulse_rate(qcl), 'width_ns': laser.get_qcl_pulse_width(qcl), 'current_ma': laser.get_qcl_current(qcl)}
        for key, expected in {'rate_hz': internal_rate, 'width_ns': internal_width, 'current_ma': current}.items():
            if not math.isclose(rb[key], expected, rel_tol=1e-6, abs_tol=1e-3): raise RuntimeError(f'QCL mismatch: {rb}')
        rb['external_rate_hz'] = external_rate
        rb['internal_duty_fraction'] = rb['rate_hz'] * rb['width_ns'] * 1e-9
        if rb['internal_duty_fraction'] > limits['max_duty_cycle'] / 100 + 1e-9: raise RuntimeError('QCL duty exceeds limit')
        return rb

    def verify_external_trigger(context):
        # Emission/status bits do not establish the pulse mode or optical output.
        # Check the real mode again after each SDK scan-mode transition.
        rb = laser.get_wavelength_trigger_params()
        expected = {'pulse_mode': 2, 'process_trigger_mode': 2, 'units': 2,
                    'start': start_cm1, 'stop': stop_cm1, 'interval': 5,
                    'dwell_us': 0, 'after_off_us': 0}
        mismatch = {key: {'actual': rb.get(key), 'expected': value}
                    for key, value in expected.items()
                    if not isinstance(rb.get(key), (int, float)) or
                    not math.isclose(rb[key], value, rel_tol=0., abs_tol=.001)}
        observation = {'context': context, 'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                       'readback': rb, 'mismatch': mismatch,
                       'optical_output_verified': False}
        record.setdefault('mircat_trigger_checks', []).append(observation)
        write_json(out / f'mircat_trigger_{context}.json', observation)
        if mismatch:
            raise RuntimeError(f'MIRcat external trigger settings changed at {context}: {mismatch}')
        return rb

    def poll(seconds=.05, interlock=True):
        check_cancel()
        if interlock: check()
        record['native_chunks'].append(hf.read_acquisition(seconds))

    def wait_for_stable_tecs(context):
        stability_s = float(profile.get('tec_ready_stability_s', 5.) if tec_ready_stability_s is None
                            else tec_ready_stability_s)
        if not math.isfinite(stability_s) or stability_s < 0:
            raise ValueError('tec_ready_stability_s must be finite and nonnegative')
        stage(f'Waiting for MIRcat TEC ready continuously for {stability_s:g} s ({context})')
        deadline = time.monotonic() + 120.
        ready_since = None
        while True:
            check()
            now = time.monotonic()
            ready = bool(laser.are_tecs_ready()) and bool(laser.is_laser_armed())
            record.setdefault('tec_readiness_checks', []).append({
                'context': context,
                'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                'ready_and_armed': ready,
            })
            if ready:
                ready_since = now if ready_since is None else ready_since
                if now - ready_since >= stability_s:
                    stage(f'MIRcat TEC ready remained stable for {stability_s:g} s ({context})')
                    return
            else:
                ready_since = None
            if now >= deadline:
                raise TimeoutError(f'MIRcat TEC readiness did not remain stable ({context})')
            cancel.wait(.25)

    try:
        stage('Preparing PicoScope EXT capture and disabled pump timing')
        cfg, _, _ = load_hardware_config(config_path)
        pico_settings, expected_pico_interval_ns = picoscope_settings_for_profile(
            profile, custom_profile=settings is not None)
        pico = picoscope_factory(cfg['devices']['picoscope'], pico_settings, command_log=log)
        pico.open_unit()
        pico.apply_capture_settings()
        timing = pico.validate_sample_timing()
        if (not math.isclose(timing['sample_interval_ns'], expected_pico_interval_ns,
                             rel_tol=0., abs_tol=1e-6) or
                timing['max_samples'] < pico_settings['total_samples']):
            raise RuntimeError(f'PicoScope memory/timing mismatch: {timing}')
        write_json(out / 'picoscope_prepared.json', {'settings': pico_settings, 'timing': timing})
        for name in ('t660_2', 't660_1'):
            check_cancel()
            unit = t660_factory(name, config_path=config_path, command_log=log)
            units[name] = unit
            unit.connect()
            if str(unit.device_config['serial_number']) not in [x.strip() for x in unit.identify().split(',')]:
                raise RuntimeError('T660 identity mismatch')
            stop_unit(unit)
            verify_unit(unit, IDLE, name + '_initial_idle.json')
        check_cancel()
        laser = laser_factory(config_path=config_path, command_log=log)
        laser.initialize()
        laser.stop_scan_if_needed()
        laser.turn_emission_off()
        laser.cancel_manual_tune()
        laser.disarm()
        laser.set_red_laser_pointer_enabled(False)
        check()
        write_json(out / 'mircat_before.json', publish_state())
        coverage = laser.get_qcl_tuning_range(qcl)
        if not coverage['min_cm1'] <= min(start_cm1, stop_cm1) < max(start_cm1, stop_cm1) <= coverage['max_cm1']:
            raise RuntimeError(f'Outside QCL {qcl} coverage')
        limits = laser.get_qcl_pulse_limits(qcl)
        lo, hi = laser.get_qcl_current_limits(qcl)
        if not all(math.isfinite(v) for v in (lo, hi, limits['max_pulse_rate_hz'],
                                             limits['max_pulse_width_ns'], limits['max_duty_cycle'])):
            raise RuntimeError('MIRcat SDK returned invalid current/pulse limits')
        if not lo <= current <= hi or internal_rate > limits['max_pulse_rate_hz'] or internal_width > limits['max_pulse_width_ns'] or internal_rate*internal_width*1e-7 > limits['max_duty_cycle'] + 1e-6:
            raise RuntimeError('Requested pulse parameters outside SDK limits')
        record['qcl_current_before_setting_ma'] = laser.get_qcl_current(qcl)
        stage(f"MIRcat initial current readback: {record['qcl_current_before_setting_ma']:g} mA; setting {current:g} mA")
        laser.set_qcl_pulse_params(qcl=qcl, pulse_rate_hz=internal_rate, pulse_width_ns=internal_width, current_ma=current)
        qcl_configured = True
        trigger = laser.set_external_sweep_trigger_params(start_cm1=start_cm1, stop_cm1=stop_cm1, wavelength_trigger_interval_cm1=5, external_process_trigger=True)
        for key, expected in {'pulse_mode': 2, 'process_trigger_mode': 2, 'units': 2, 'start': start_cm1, 'stop': stop_cm1, 'interval': 5}.items():
            if not math.isclose(trigger[key], expected, abs_tol=.001): raise RuntimeError(f'MIRcat trigger mismatch: {trigger}')
        if laser.set_wavelength_trigger_pulse_width_us(500) != 500: raise RuntimeError('Marker width mismatch')
        write_json(out / 'mircat_configured.json', {'trigger': trigger, 'qcl': verify_qcl(), 'limits': limits, 'range': coverage})
        pulse = {'enabled': True, 'delay': '0ns', 'width': f'{external_width:g}ns', 'polarity': 'positive', 'termination': '50OHM'}
        probe_recipe = {'stop_first': True, 'trigger_source': 'SYN', 'predivider': 1, 'gate_mode': 0, 'burst_enabled': False, 'clock': {'frequency': f'{external_rate:g}Hz'}, 'force_eod': True, 'channels': {'A': pulse, 'B': {**pulse, 'enabled': False}, 'C': {'enabled': False}, 'D': {'enabled': False}}}
        units['t660_1'].apply_recipe(probe_recipe)
        verify_unit(units['t660_1'], probe_recipe, 't660_1_reference_prepared.json')
        units['t660_1'].command('START', expect_response=False)
        timer_recipe = {'stop_first': True, 'trigger_source': 'REM', 'frames_engine': 'OFF', 'predivider': 1, 'gate_mode': 0, 'burst_enabled': False, 'force_eod': True, 'channels': {'A': {'enabled': False}, 'B': {'enabled': False}, 'C': {'enabled': True, 'delay': '1ms', 'width': '10ms', 'polarity': 'negative', 'termination': '50OHM'}, 'D': {'enabled': False}}}
        units['t660_2'].apply_recipe(timer_recipe)
        verify_unit(units['t660_2'], timer_recipe, 't660_2_process_only.json')
        units['t660_2'].command('START', expect_response=False)
        record['shot_counter_before'] = units['t660_2'].get_shot_count()
        hf = hf_factory(config_path=config_path, command_log=log)
        hf.connect()
        preset = air_scan_preset(external_rate)
        hf.apply_preset(preset)
        configured = hf.export_settings_snapshot(preset=preset)
        def read_input_status(context):
            status = hf_input_status(hf)
            record.setdefault('hf2li_input_checks', []).append({
                'context': context, 'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'status': status})
            for warning in clipping_warnings(status):
                if warning not in record['warnings']:
                    record['warnings'].append(warning)
                    stage('Warning: ' + warning)
            return status
        record['hf2li_input_status_before'] = read_input_status('configured')
        write_json(out / 'hf2li_configured.json', configured)
        verify_hf_settings(configured, hf.device_id, external_rate)
        # Preserve dark-input status without making clipping an acquisition gate.
        for index in range(3):
            check()
            status = read_input_status('baseline')
            record.setdefault('baseline_checks', []).append(status)
            write_json(out / f'hf2li_baseline_{index}.json', status)
            cancel.wait(.1)
        end=time.monotonic()+10
        while not math.isclose(hf.get_oscillator_frequency(0), external_rate, abs_tol=external_rate*.001):
            if time.monotonic()>end: raise RuntimeError(f'HF2LI reference did not follow {external_rate:g} Hz')
            check()
            cancel.wait(.1)
        record['reference_frequency_before_hz'] = hf.get_oscillator_frequency(0)
        if not math.isclose(record['reference_frequency_before_hz'], external_rate, abs_tol=external_rate*.001):
            raise RuntimeError('HF2LI external reference lock was lost')
        record['clockbase_hz'] = hf.get_clockbase()
        check()
        stage(f'HF2LI 2 V input ranges, rates and {external_rate:g} Hz reference verified; arming MIRcat')
        laser.arm()
        publish_state()
        wait_for_stable_tecs('after_arm')
        publish_state()
        # TurnEmissionOn requires a prior TuneToWW (vendor SDK header).
        # Keep the optical trigger train disabled throughout this preparation.
        laser.cancel_manual_tune()
        check()
        stage(f'Tuning MIRcat to {start_cm1:g} cm^-1 before explicit emission enable')
        laser.tune_to_wavenumber(start_cm1, qcl=qcl)
        end = time.monotonic()+120
        while not laser.is_tuned():
            check()
            if time.monotonic() > end:
                raise TimeoutError('MIRcat did not tune before emission enable')
            cancel.wait(.25)
        check()
        write_json(out / 'mircat_tuned_before_emission.json', publish_state())
        # Reapply/read back external optical/process triggering after tuning.
        trigger_after_tune = laser.set_external_sweep_trigger_params(
            start_cm1=start_cm1, stop_cm1=stop_cm1,
            wavelength_trigger_interval_cm1=5, external_process_trigger=True)
        for key in ('pulse_mode', 'process_trigger_mode', 'units', 'start', 'stop', 'interval'):
            if not math.isclose(trigger_after_tune[key], trigger[key], abs_tol=.001):
                raise RuntimeError(f'MIRcat trigger mismatch after tuning: {trigger_after_tune}')
        write_json(out / 'mircat_trigger_after_tune.json', trigger_after_tune)
        record['qcl_before_start'] = verify_qcl()
        read_input_status('before_sweep_setup')
        hf.start_acquisition(demodulators=(0,2,3))
        poll(.2)
        # Always issue the SDK command: StartSweepScan can report emission on
        # without this explicit enable. CHB optical triggers are still disabled here.
        check()
        stage('Calling MIRcatSDK_TurnEmissionOn before MIRcatSDK_StartSweepScan')
        laser.turn_emission_on(approved_laser_safety_condition=True)
        record['emission_gate_on_before_scan'] = bool(laser.is_emission_on())
        write_json(out / 'mircat_emission_before_scan.json', {
            'sdk_command': 'MIRcatSDK_TurnEmissionOn',
            'emission_on_readback': record['emission_gate_on_before_scan'],
            'state': publish_state(),
        })
        if not record['emission_gate_on_before_scan']:
            raise RuntimeError('MIRcat emission gate did not enable before scan start')
        # Vendor-required transition from single tune to sweep, still with CHB off.
        laser.cancel_manual_tune()
        record['manual_tune_cancelled_before_scan'] = True
        check()
        record['qcl_after_manual_tune_cancel'] = verify_qcl()
        verify_external_trigger('after_manual_tune_cancel')
        # The updated controller can transiently report ready during manual tune,
        # then reject StartSweepScan while the sweep state re-establishes its TEC
        # setpoint. Require a fresh stable interval after leaving manual tune.
        wait_for_stable_tecs('after_manual_tune_cancel')
        units['t660_1'].enable_channel('B')
        probe_recipe['channels']['B']['enabled'] = True
        verify_unit(units['t660_1'], probe_recipe, 't660_1_optical_trigger_prepared.json')
        start_errors=[]
        def start():
            try: laser.start_sweep_scan(start_cm1=start_cm1, stop_cm1=stop_cm1, scan_rate_cm1_s=rate, qcl=qcl, repetitions=1)
            except Exception as exc: start_errors.append(exc)
        stage('Starting authorized MIRcat sweep setup; waiting for external process trigger')
        starter=Thread(target=start, daemon=True)
        starter.start()
        end=time.monotonic()+45
        while starter.is_alive():
            poll(.05, interlock=False)
            if time.monotonic()>end: raise TimeoutError('StartSweepScan did not return')
        starter.join()
        check()
        if start_errors: raise start_errors[0]
        verify_external_trigger('after_sweep_setup')
        end=time.monotonic()+30
        while not laser.get_scan_waiting_process_trigger():
            poll()
            if time.monotonic()>end: raise TimeoutError('No external process wait state')
        verify_hf_settings(hf.export_settings_snapshot(preset=preset), hf.device_id, external_rate)
        read_input_status('before_process_trigger')
        record['qcl_before_process'] = verify_qcl()
        write_json(out / 'mircat_waiting_process.json', publish_state())
        if not laser.is_emission_on():
            check()
            stage('Opening MIRcat emission gate while waiting for the T660 process trigger')
            laser.turn_emission_on(approved_laser_safety_condition=True)
            record['explicit_emission_enable_needed'] = True
        record['emission_gate_on_before_process'] = bool(laser.is_emission_on())
        publish_state()
        if not record['emission_gate_on_before_process']:
            raise RuntimeError('MIRcat did not enable emission for the external sweep')
        fired=[]
        def fire():
            check()
            if not laser.get_scan_waiting_process_trigger(): raise RuntimeError('MIRcat process wait lost')
            verify_external_trigger('before_process_trigger')
            verify_unit(units['t660_2'], timer_recipe, 't660_2_before_process.json')
            units['t660_2'].fire_remote_trigger()
            fired.append(time.monotonic())
            record['process_trigger_utc'] = datetime.now(timezone.utc).isoformat()
            stage('PicoScope EXT armed; one process trigger sent, pump outputs disabled')
        last_status=[0.]
        def service_capture():
            poll(.05)
            if time.monotonic()-last_status[0] > .5:
                status=laser.get_scan_status()
                record.setdefault('scan_status_observations', []).append({'elapsed_s':time.monotonic()-fired[0], **status, 'qcl_settings':verify_qcl(), 'hf2li_input_status':read_input_status('during_capture')})
                elapsed = time.monotonic()-fired[0]
                stage(f"Scanning: {min(elapsed, profile['nominal_sweep_duration_s']):.1f} / {profile['nominal_sweep_duration_s']:.1f} s")
                last_status[0]=time.monotonic()
        def before_transfer():
            check_cancel()
            stage('Sweep captured; stopping IR before PicoScope transfer…')
            for unit in units.values():
                stop_unit(unit)
            laser.stop_scan_if_needed()
            laser.turn_emission_off()
            laser.disarm()
            stage('Transferring both PicoScope detector records…')
        raw=pico.capture_block_data(after_arm=fire, while_waiting=service_capture,
                                    before_transfer=before_transfer)
        stage('PicoScope block transferred; collecting post-sweep HF2LI markers')
        record['picoscope_metadata'] = {k:v for k,v in raw.items() if k not in ('ch_a_adc','ch_b_adc')}
        # Drain tail data even if Stop was pressed during the blocking USB transfer.
        record['native_chunks'].append(hf.read_acquisition(.3))
        record['scan_status_after_transfer'] = laser.get_scan_status()
        record['qcl_after_transfer'] = verify_qcl()
        record['hf2li_input_status_after'] = read_input_status('after_transfer')
        record['reference_frequency_after_hz'] = hf.get_oscillator_frequency(0)
        record['shot_counter_after'] = units['t660_2'].get_shot_count()
        if (record['shot_counter_after']-record['shot_counter_before'])%2**32 != 1: raise RuntimeError('Expected exactly one process event')
        if raw['overflow']: record['picoscope_overflow_warning']=raw['overflow']
        if raw['total_samples'] != pico_settings['total_samples']: raise RuntimeError('PicoScope partial transfer')
        record['capture_completed'] = True
        verify_hf_settings(hf.export_settings_snapshot(preset=preset), hf.device_id, external_rate)
        check_cancel()
    except Exception as exc:
        error=repr(exc)
        record['error']=error
        record['error_message']=str(exc)
        stage('Acquisition stopped: '+str(exc))
        try:
            log.write(traceback.format_exc())
        except OSError:
            pass
    finally:
        stage('Stopping emission and timing outputs; retaining acquisition settings')
        for unit in units.values(): attempt(unit.name+' stop', lambda u=unit:stop_unit(u))
        if starter is not None and starter.is_alive():
            stage('External triggers stopped; waiting for MIRcat SDK setup to return before shutdown…')
            # Keep instrument ownership and the UI Stop state until SDK ownership is released.
            # Never deinitialize concurrently with an unfinished vendor SDK call.
            while starter.is_alive():
                starter.join(timeout=.1)
        if laser is not None:
            for label,fn in [('scan stop',laser.stop_scan_if_needed),('emission off',laser.turn_emission_off),('disarm',laser.disarm)]: attempt(label,fn)
            def verify_laser():
                state=publish_state()
                write_json(out/'mircat_final.json',state)
                if laser.is_emission_on() or laser.is_laser_armed() or laser.get_scan_status()['scan_in_progress']: raise RuntimeError('MIRcat not safe idle')
            attempt('MIRcat final readback',verify_laser)
            def retain_laser_settings():
                actual={'rate_hz':laser.get_qcl_pulse_rate(qcl),'width_ns':laser.get_qcl_pulse_width(qcl),'current_ma':laser.get_qcl_current(qcl)}
                expected={'rate_hz':internal_rate,'width_ns':internal_width,'current_ma':current}
                corrected=False
                if any(not math.isclose(actual[k],v,rel_tol=1e-6,abs_tol=1e-3) for k,v in expected.items()):
                    laser.set_qcl_pulse_params(qcl=qcl,pulse_rate_hz=internal_rate,pulse_width_ns=internal_width,current_ma=current)
                    corrected=True
                retained={'rate_hz':laser.get_qcl_pulse_rate(qcl),'width_ns':laser.get_qcl_pulse_width(qcl),'current_ma':laser.get_qcl_current(qcl)}
                matched=all(math.isclose(retained[k],v,rel_tol=1e-6,abs_tol=1e-3) for k,v in expected.items())
                write_json(out/'mircat_retained_settings.json',{'before_retention_check':actual,'corrective_write_needed':corrected,'retained':retained,'match':matched,'trigger':laser.get_wavelength_trigger_params(),'emission_on':laser.is_emission_on(),'armed':laser.is_laser_armed()})
                if not matched: raise RuntimeError('MIRcat retained settings mismatch')
            if qcl_configured:
                attempt('MIRcat settings retained',retain_laser_settings)
            attempt('MIRcat deinitialize',laser.deinitialize)
        if pico is not None:
            attempt('PicoScope stop',pico.stop)
            attempt('PicoScope close',pico.close_unit)
        for unit in units.values():
            attempt(unit.name+' idle verify',lambda u=unit:verify_unit(u,IDLE,u.name+'_final_idle.json'))
            attempt(unit.name+' close',unit.close)
        if hf is not None:
            attempt('HF2LI stop',hf.stop_acquisition)
            def verify_retained_hf():
                if configured is None:
                    write_json(out/'hf2li_retention_unverified.json',{'reason':'Preparation failed before configured snapshot; no restoration performed'})
                    return
                before={'nodes':{p:v for p,v in configured['nodes'].items() if '/sigins/' in p or '/demods/' in p}}
                actual={'nodes':{p:{'type':v['type'],'value':hf._get_node(v['type'],p)} for p,v in before['nodes'].items()}}
                write_json(out/'hf2li_retained_settings.json',actual)
                comparison=hf.compare_settings_snapshots(before,actual,double_tolerance=1e-8)
                comparison['restoration_performed']=False
                write_json(out/'hf2li_retention_verification.json',comparison)
                if not comparison['match']: raise RuntimeError('HF2LI settings changed during acquisition')
            attempt('HF2LI retained settings verification',verify_retained_hf)
            attempt('HF2LI close',hf.close)
        cleanup={'safe_state_and_retained_settings_verified':not cleanup_errors,'fast_hf2li_restoration_performed':False,'errors':cleanup_errors}
        write_json(out/'cleanup.json',cleanup)
        stage('Saving native data after shutdown')
        save_errors = []
        def save_artifact(label, action):
            try:
                action()
            except Exception as exc:
                save_errors.append(f'{label}: {exc}')
        # Attempt every artifact independently if a disk or serialization error occurs.
        try:
            save_artifact('HF2LI native', lambda: save_native(out/'hf2li_native.npz', record))
            if raw is not None:
                def save_channel(channel):
                    with (out/f'picoscope_ch_{channel}_adc.npy').open('xb') as handle:
                        np.save(handle, raw[f'ch_{channel}_adc'], allow_pickle=False)
                for channel in ('a','b'):
                    save_artifact(f'Pico {channel}', lambda c=channel: save_channel(c))
                save_artifact('Pico metadata', lambda: write_json(out/'picoscope_metadata.json', record['picoscope_metadata']))
        finally:
            log.close()
        result = {'path': str(out), 'acquisition_error': error,
                  'acquisition_error_message': record.get('error_message'),
                  'capture_completed': record.get('capture_completed', False), 'cleanup': cleanup,
                  'native_chunk_count': len(record['native_chunks']), 'pump_events': 0,
                  'warnings': record['warnings'],
                  'cancelled': cancel.is_set(), 'publication_eligible': False, 'save_errors': save_errors}
        write_json(out/'result.json', result)
    # Native artifacts are safe on disk before analysis; analysis cannot operate hardware.
    if record.get('capture_completed') and not save_errors:
        progress('Building detector plots and scan summary…')
        try:
            from control_app.workflows.air_scan_analysis import analyze_air_scan
            result['analysis'] = analyze_air_scan(out, record)
        except Exception as exc:
            result['analysis_error'] = str(exc)
            write_json(out/'analysis_error.json', {'error': repr(exc)})
    progress('Finished: ' + str(out))
    return result
