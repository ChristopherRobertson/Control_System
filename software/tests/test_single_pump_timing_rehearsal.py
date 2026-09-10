"""Exercise one finite pump frame using hardware-free transports only."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from control_app.workflows import air_scan as air
from control_app.workflows.phase_scan_data import load_native
from test_air_scan import Rig
from test_phase_scan_acquisition import Timer
from test_single_detector_unpumped_scan import SingleHF, SingleLaser, fast_rehearsal_profile


class PumpTimer(Timer):
    def preload_frame_table(self, frames, *, predivider):
        assert self.name == 't660_2' and self.source == 'OFF'
        assert len(frames) == 1 and predivider == 600000
        assert all(frames[0]['channels'][c]['enabled'] for c in 'ABC')
        assert not frames[0]['channels']['D']['enabled']
        self.frames = [deepcopy(frames[0]), {'channels': {
            c: {**v, 'enabled': False} for c, v in frames[0]['channels'].items()}}]
        self.recipe['predivider'] = predivider
        self.shots = 0
        self.world.trace.append('preload_one_plus_inert')
        return {'acquisition_frame_count': 1, 'physical_frame_count': 2, 'inert_terminator_count': 1,
                'frame_period_s': .3, 'readback': {'first': 0, 'last': 1, 'loop_count': 0, 'predivider': predivider}}

    def start_frame_table(self):
        assert self.source == 'OFF' and self.world.hf.active
        probe = self.world.units['t660_1']
        assert probe.source == 'SYN' and probe.channels['A']['enabled']
        assert not probe.channels['B']['enabled'] and not probe.channels['C']['enabled']
        self.source = 'EXT'
        self.channels = deepcopy(self.frames[0]['channels'])
        if self.world.fault == 'first_frame_readback':
            self.channels['A']['width'] = '20us'
        self.world.frame_armed = True
        self.world.trace.append('frame_armed')

    def enable_channel(self, channel):
        if self.name == 't660_1' and channel in 'BC':
            assert self.world.frame_armed and self.world.hf.active
            self.world.trace.append('enable_' + channel)
            if channel == 'C':
                assert self.channels['B']['enabled'] and not self.channels['C']['enabled']
                assert self.world.hf.cursor >= .02
                assert not self.world.fires
                self.world.units['t660_2'].shots += 3 if self.world.fault == 'counter' else 2
                self.world.fires.append(deepcopy(self.world.units['t660_2'].frames[0]))
                self.world.laser.triggered = True
                if self.world.fault == 'cleanup': self.world.fail_stop = True
        super().enable_channel(channel)

    def get_frames_status(self):
        assert self.world.laser.triggered
        self.channels = deepcopy(self.frames[1]['channels'])
        return 'ERROR' if self.world.fault == 'engine' else 'DONE'

    def fire_remote_trigger(self):
        raise AssertionError('A pumped frame diagnostic must never fire a software remote trigger')

    def command(self, command, **kwargs):
        if command == 'TFRame:STOp':
            assert self.source == 'OFF'
            # Explicitly model frame STOP restoring old active channel enables.
            for channel in self.channels.values(): channel['enabled'] = True
            self.world.trace.append(self.name + '_frame_stop_restore')
        return super().command(command, **kwargs)


class PumpLaser(SingleLaser):
    def start_sweep_scan(self, **kwargs):
        probe = self.rig.units['t660_1']
        assert probe.channels['A']['enabled']
        assert not probe.channels['B']['enabled'] and not probe.channels['C']['enabled']
        assert not self.rig.frame_armed
        self.rig.trace.append('sdk_setup_with_reference_only')
        super().start_sweep_scan(**kwargs)

    def get_wavelength_trigger_channel_params(self, channel):
        return {'channel': channel, 'units': 2, 'start': 1950., 'stop': 1940., 'interval': 5., 'num_triggers': 3}


class PumpHF(SingleHF):
    def read_acquisition(self, duration):
        payload = super().read_acquisition(duration)
        for values in payload['data'].values():
            seconds = (values['timestamp'] - np.uint64(2**60)).astype(float) / self.get_clockbase()
            high = np.ones(len(seconds), dtype=bool)
            if self.rig.laser.triggered:
                if self.rig.fault != 'missing_sync':
                    high[(seconds >= .02005) & (seconds < .02010)] = False
                if self.rig.fault == 'extra_sync':
                    high[(seconds >= .023) & (seconds < .02305)] = False
                if self.rig.fault == 'incomplete_sync': high[seconds >= .02005] = False
            elif self.rig.fault == 'unstable_baseline':
                high[len(high)//2:] = False
            values['dio'] &= np.uint32(~(1 << 17) & 0xffffffff)
            values['dio'][high] |= np.uint32(1 << 17)
        if self.rig.fault == 'cancel_before_clock' and self.rig.frame_armed and not self.rig.laser.triggered:
            self.rig.cancel.set()
        return payload


def run_pump(tmp_path, monkeypatch, *, fault=None):
    import sys
    from types import SimpleNamespace
    analyzed = []
    def analyze(directory, record):
        analyzed.append(record)
        assert Path(directory, 'hf2li_native.npz').exists()
        return {'usable_for_timing': bool(record['optical_valid']), 'usable_for_ratio': False}
    monkeypatch.setitem(sys.modules, 'control_app.workflows.single_pump_timing_analysis',
                        SimpleNamespace(analyze_single_pump_timing_rehearsal=analyze))
    rig = Rig()
    rig.trace, rig.frame_armed, rig.fault = [], False, fault
    rig.fail_stop_after_trigger = rig.unexpected_pump = rig.fail_capture = False
    rig.pump_baseline_high, rig.unstable_pump_baseline = True, False
    rig.scan_profile, rig.fast_scan = fast_rehearsal_profile(), True
    def no_pico(*args, **kwargs): raise AssertionError('No PicoScope in single-pump timing rehearsal')
    result = air.run_single_pump_timing_rehearsal(tmp_path, cancel=rig.cancel, progress=rig.events.append,
        laser_authorized=True, pump_authorized=True, settings=rig.scan_profile,
        laser_factory=lambda **kw: PumpLaser(rig), hf_factory=lambda **kw: PumpHF(rig),
        t660_factory=lambda name, **kw: PumpTimer(rig, name), picoscope_factory=no_pico,
        tec_ready_stability_s=0.)
    record = load_native(Path(result['path']) / 'hf2li_native.npz')
    return rig, result, record, analyzed


def test_single_pump_frame_and_inert_padding_preserve_native_timing_and_shutdown(tmp_path, monkeypatch):
    rig, result, record, analyzed = run_pump(tmp_path, monkeypatch)
    assert result['acquisition_error'] is None, result
    assert result['cleanup']['safe_state_and_retained_settings_verified']
    assert len(rig.fires) == 1 and result['requested_pump_events'] == result['pump_events'] == 1
    assert record['shot_counter_after'] - record['shot_counter_before'] == 2
    assert record['first_active_frame_readback_verified']
    assert record['frame_status_observations'][-1]['state'] == 'DONE'
    assert rig.trace.index('sdk_setup_with_reference_only') < rig.trace.index('frame_armed') < rig.trace.index('enable_B') < rig.trace.index('enable_C')
    assert rig.trace.count('enable_C') == 1
    assert record['pump_sync_baseline']['stable'] and record['pump_sync_baseline']['high']
    assert record['pump_sync_event']['leading_edge'] == 'falling'
    assert record['pump_sync_event']['leading_tick'] > record['pre_process_last_timing_tick']
    assert record['observed_pump_sync_rising_edges'] == record['observed_pump_sync_falling_edges'] == 1
    assert record['record_role'] == 'single_pump_timing_rehearsal'
    assert record['event']['pump_enabled'] and record['event']['phase_delay_us'] == 0
    assert not record['usable_as_background'] and not record['usable_for_ratio'] and not record['spectral_analysis_allowed']
    assert 'process_trigger_utc' not in record and 'frame_trigger_source_enabled_utc' in record
    assert 'pump_outputs_disabled_readback_verified' not in record
    assert len(analyzed) == 1 and record['optical_valid']
    assert all(not unit.channels[c]['enabled'] for unit in rig.units.values() for c in 'ABCD')
    assert not rig.laser.emission and not rig.laser.armed and rig.hf.closed and rig.laser.closed
    operation = json.loads((Path(result['path']) / 'operation.json').read_text())
    assert operation['automatic_retries'] == 0 and operation['requested_pump_events'] == 1
    assert 'pump_physically_blocked' not in operation and 'unpumped' not in operation['authorization']


@pytest.mark.parametrize('fault', ['first_frame_readback', 'unstable_baseline', 'cancel_before_clock',
                                   'extra_sync', 'missing_sync', 'incomplete_sync', 'counter', 'engine', 'cleanup'])
def test_single_pump_fault_never_retries_and_preserves_invalid_native(tmp_path, monkeypatch, fault):
    rig, result, record, _ = run_pump(tmp_path, monkeypatch, fault=fault)
    assert result['acquisition_error'] or result['cleanup']['errors']
    assert not record['optical_valid'] and record['native_chunks']
    assert len(rig.fires) == (0 if fault in {'first_frame_readback', 'unstable_baseline', 'cancel_before_clock'} else 1)
    assert not rig.laser.emission and not rig.laser.armed and rig.laser.closed and rig.hf.closed
    assert result['requested_pump_events'] == 1
    if fault in {'extra_sync', 'missing_sync', 'incomplete_sync'}: assert record['pump_events'] is None
    if fault != 'cleanup':
        assert result['cleanup']['safe_state_and_retained_settings_verified']
        assert all(not unit.channels[c]['enabled'] for unit in rig.units.values() for c in 'ABCD')


@pytest.mark.parametrize('laser,pump', [(False, False), (True, False), (False, True), (True, 1)])
def test_single_pump_requires_both_explicit_authorizations_before_io(tmp_path, laser, pump):
    with pytest.raises(PermissionError):
        air.run_single_pump_timing_rehearsal(tmp_path, cancel=Rig().cancel, progress=lambda _: None,
                                          laser_authorized=laser, pump_authorized=pump)
    assert not list(tmp_path.iterdir())


def test_direct_core_cannot_select_pump_mode_without_authorization(tmp_path):
    with pytest.raises(PermissionError):
        air.run_air_scan(tmp_path, cancel=Rig().cancel, progress=lambda _: None,
                         laser_authorized=True, single_detector=True, record_kind='pump_timing_rehearsal')
    assert not list(tmp_path.iterdir())
