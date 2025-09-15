"""
PicoScope 5244D Controller — Phase 1 (UI scaffolding only)

Implements in-memory state, validation against hardware_configuration.toml,
and idempotent connect/disconnect plus configuration setters. No SDK calls
are made in this phase; those are introduced in Part D.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
from pathlib import Path
import toml
import logging
import math
import os
from ctypes import byref, c_int16, c_int32, c_float, create_string_buffer

logger = logging.getLogger(__name__)


def _load_cfg() -> Dict[str, Any]:
    try:
        cfg_path = Path(__file__).parents[4] / 'hardware_configuration.toml'
        data = toml.load(cfg_path)
        return data.get('picoscope_5244d', {})
    except Exception as e:
        logger.warning(f"Failed to read hardware_configuration.toml: {e}")
        return {}


@dataclass
class PicoScopeState:
    connected: bool = False
    acquiring: bool = False
    resolution_bits: int = 8
    waveform_count: int = 1
    model: Optional[str] = None
    serial: Optional[str] = None
    driver_version: Optional[str] = None
    transport: str = 'USB'
    last_error: Optional[str] = None
    last_error_code: Optional[int] = None
    # Channel configuration
    channels: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        'A': {
            'enabled': True,
            'range': '±2V',
            'coupling': 'DC',
            'offset': 0.0,
            'bandwidth_limiter': False,
            'invert': False,
        },
        'B': {
            'enabled': False,
            'range': '±2V',
            'coupling': 'DC',
            'offset': 0.0,
            'bandwidth_limiter': False,
            'invert': False,
        },
    })
    # Timebase & trigger
    timebase: Dict[str, Any] = field(default_factory=lambda: {
        'time_per_div': '1ms/div',
        'n_samples': 100_000,
        'sample_rate_hz': 1_000_000,
    })
    trigger: Dict[str, Any] = field(default_factory=lambda: {
        'mode': 'None',        # None | Auto | Single
        'source': 'A',         # A | B | Ext
        'level_v': 0.0,
        'edge': 'Rising',
        'enabled': True,
    })
    # AWG/Signal Generator (minimal)
    awg: Dict[str, Any] = field(default_factory=lambda: {
        'enabled': False,
        'shape': 'Sine',
        'frequency_hz': 1000.0,
        'amplitude_vpp': 2.0,
        'offset_v': 0.0,
    })
    # Last preview waveform
    last_waveform: Dict[str, List[float]] = field(default_factory=dict)
    # ADC full-scale counts for current resolution (queried from SDK)
    adc_max_counts: Optional[int] = None


class PicoScope5244DController:
    def __init__(self) -> None:
        self._cfg = _load_cfg()
        self._params = self._cfg.get('parameters', {})
        self.state = PicoScopeState()
        self._ps = None
        self._handle: Optional[c_int16] = None
        # Fill transport/model hints if provided
        if (ct := self._cfg.get('connection_type')):
            self.state.transport = ct
        self.state.model = self._cfg.get('device_type', 'PicoScope 5244D')

    # ------------------------ helpers ------------------------
    def _validate_channel(self, ch: str) -> None:
        if ch not in ('A', 'B'):
            raise ValueError('Only channels A and B are supported in Phase 1')

    def _clamp(self, val: float, vmin: float, vmax: float) -> float:
        return max(vmin, min(vmax, val))

    def _prepare_dll_search_paths(self) -> None:
        if os.name != 'nt':
            return
        candidates = []
        envp = os.environ.get('PICO_SDK_PATH')
        if envp:
            candidates.append(envp)
        if self._cfg.get('sdk_path'):
            candidates.append(self._cfg['sdk_path'])
        prog_files = os.environ.get('ProgramFiles', r"C:\\Program Files")
        candidates.append(os.path.join(prog_files, 'Pico Technology', 'SDK'))
        for base in candidates:
            for p in (base, os.path.join(base, 'lib')):
                if os.path.isdir(p):
                    try:
                        os.add_dll_directory(p)  # type: ignore[attr-defined]
                    except Exception:
                        pass

    def _require_sdk(self) -> None:
        if self._ps is not None:
            return
        self._prepare_dll_search_paths()
        from picosdk.ps5000a import ps5000a as ps  # type: ignore
        self._ps = ps

    def _ch_enum(self, ch: str) -> int:
        ps = self._ps
        return ps.PS5000A_CHANNEL[f'PS5000A_CHANNEL_{ch}']

    def _range_to_enum(self, label: str) -> int:
        ps = self._ps
        mapping = {
            '±20V': ps.PS5000A_RANGE['PS5000A_20V'],
            '±10V': ps.PS5000A_RANGE['PS5000A_10V'],
            '±5V': ps.PS5000A_RANGE['PS5000A_5V'],
            '±2V': ps.PS5000A_RANGE['PS5000A_2V'],
            '±1V': ps.PS5000A_RANGE['PS5000A_1V'],
            '±500mV': ps.PS5000A_RANGE['PS5000A_500MV'],
            '±200mV': ps.PS5000A_RANGE['PS5000A_200MV'],
            '±100mV': ps.PS5000A_RANGE['PS5000A_100MV'],
            '±50mV': ps.PS5000A_RANGE['PS5000A_50MV'],
            '±20mV': ps.PS5000A_RANGE['PS5000A_20MV'],
            '±10mV': ps.PS5000A_RANGE['PS5000A_10MV'],
        }
        return mapping.get(label, ps.PS5000A_RANGE['PS5000A_2V'])

    def _coupling_to_enum(self, label: str) -> int:
        ps = self._ps
        return ps.PS5000A_COUPLING['PS5000A_DC'] if label == 'DC' else ps.PS5000A_COUPLING['PS5000A_AC']

    def _resolve_timebase(self, time_per_div: str) -> Dict[str, Any]:
        ps = self._ps
        handle = self._handle
        if handle is None:
            raise RuntimeError('Device not connected')
        tbmap = (self._params.get('timebase_index_map') or {})
        index = int(tbmap.get(time_per_div, 17))
        ti = c_float()
        mx = c_int32()
        st = ps.ps5000aGetTimebase2(handle, index, 1, byref(ti), byref(mx), 0)
        if st != 0:
            for delta in (-2, -1, 1, 2, -5, 5):
                st = ps.ps5000aGetTimebase2(handle, index + delta, 1, byref(ti), byref(mx), 0)
                if st == 0:
                    index += delta
                    break
        if st != 0:
            raise RuntimeError(f'GetTimebase2 failed: {st}')
        label_list = self._params.get('time_per_div_options', [])
        ladder = self._params.get('time_per_div_options_s', [])
        total_s = 10.0 * (ladder[label_list.index(time_per_div)] if time_per_div in label_list else 0.001)
        samples = int(min(mx.value, max(1000, total_s / (ti.value * 1e-9))))
        ti2 = c_float()
        mx2 = c_int32()
        st2 = ps.ps5000aGetTimebase2(handle, index, samples, byref(ti2), byref(mx2), 0)
        if st2 != 0:
            samples = int(mx.value)
        return {
            'index': int(index),
            'time_interval_ns': float(ti.value),
            'max_samples': int(mx.value),
            'samples': samples,
        }

    # ------------------------ public API ---------------------
    async def connect(self) -> bool:
        if self.state.connected:
            return True
        try:
            self._require_sdk()
            self._handle = c_int16()
            res_enum = self._ps.PS5000A_DEVICE_RESOLUTION[f'PS5000A_DR_{self.state.resolution_bits}BIT']
            status = self._ps.ps5000aOpenUnit(byref(self._handle), None, res_enum)
            if status != 0:
                self.state.connected = False
                self.state.last_error_code = int(status)
                self.state.last_error = f"ps5000aOpenUnit failed: {status}"
                raise RuntimeError(self.state.last_error)

            def unit_info(info: int) -> str:
                buf = create_string_buffer(128)
                req = c_int16()
                self._ps.ps5000aGetUnitInfo(self._handle, buf, c_int16(128), byref(req), info)
                return buf.value.decode(errors='ignore')

            self.state.model = unit_info(3)
            self.state.serial = unit_info(4) or None
            self.state.driver_version = unit_info(0)

            # Query ADC max counts for current resolution
            try:
                max_adc = c_int16()
                self._ps.ps5000aMaximumValue(self._handle, byref(max_adc))
                self.state.adc_max_counts = int(max_adc.value)
            except Exception:
                self.state.adc_max_counts = 32767

            self.state.connected = True
            self.state.acquiring = False
            self.state.last_error = None
            self.state.last_error_code = None
            return True
        except Exception as e:
            logger.error(f"Connect failed: {e}")
            return False

    async def disconnect(self) -> bool:
        try:
            if self._ps and self._handle is not None:
                try:
                    self._ps.ps5000aCloseUnit(self._handle)
                except Exception as e:
                    logger.warning(f"CloseUnit error: {e}")
            self._handle = None
            self.state.connected = False
            self.state.acquiring = False
            return True
        except Exception as e:
            logger.error(f"Disconnect failed: {e}")
            return False

    async def get_status(self) -> Dict[str, Any]:
        s = self.state
        return {
            'connected': s.connected,
            'acquiring': s.acquiring,
            'channels': s.channels,
            'timebase': s.timebase,
            'trigger': s.trigger,
            'awg': s.awg,
            'resolution_bits': s.resolution_bits,
            'waveform_count': s.waveform_count,
            'adc_max_counts': s.adc_max_counts,
            'model': s.model,
            'serial': s.serial,
            'driver_version': s.driver_version,
            'transport': s.transport,
            'last_error': s.last_error,
            'last_error_code': s.last_error_code,
        }

    async def set_resolution(self, bits: int) -> None:
        # PS5244D valid FlexRes set does not include 16-bit
        if bits not in (8, 12, 14, 15):
            raise ValueError('resolution_bits must be one of 8,12,14,15')
        if self.state.resolution_bits == bits:
            return
        self.state.resolution_bits = bits
        if self._handle is not None:
            await self.disconnect()
            await self.connect()

    async def set_waveform_count(self, count: int) -> None:
        if count < 1:
            raise ValueError('waveform_count must be >= 1')
        self.state.waveform_count = int(count)

    async def set_channel_config(self, channel: str, config: Dict[str, Any]) -> None:
        self._validate_channel(channel)
        ch = self.state.channels[channel]
        ch.update(config)
        # enforce ranges if provided in config file
        valid_ranges = self._params.get('input_ranges', ['±50mV','±100mV','±200mV','±500mV','±1V','±2V','±5V','±10V'])
        if ch.get('range') not in valid_ranges:
            ch['range'] = '±2V'
        if ch.get('coupling') not in ('AC','DC'):
            ch['coupling'] = 'DC'
        try:
            ch['offset'] = float(ch.get('offset', 0.0))
        except Exception:
            ch['offset'] = 0.0
        ch['bandwidth_limiter'] = bool(ch.get('bandwidth_limiter', ch.get('bw_limit', False)))
        ch['invert'] = bool(ch.get('invert', False))

    async def set_timebase_config(self, config: Dict[str, Any]) -> None:
        tb = self.state.timebase
        tb.update(config)
        valid_tpdiv = self._params.get('time_per_div_options', [])
        if tb.get('time_per_div') not in valid_tpdiv:
            tb['time_per_div'] = '1ms/div'
        if self._handle is not None and self._ps is not None:
            info = self._resolve_timebase(tb['time_per_div'])
            tb['n_samples'] = info['samples']
            tb['sample_rate_hz'] = 1e9 / info['time_interval_ns']

    async def set_trigger_config(self, config: Dict[str, Any]) -> None:
        trg = self.state.trigger
        trg.update(config)
        if trg.get('source') not in ('A','B','Ext'):
            trg['source'] = 'A'
        if trg.get('edge') not in ('Rising','Falling'):
            trg['edge'] = 'Rising'
        if trg.get('mode') not in ('None','Auto','Single'):
            trg['mode'] = 'None'
        try:
            trg['level_v'] = float(trg.get('level_v', 0.0))
        except Exception:
            trg['level_v'] = 0.0
        trg['enabled'] = bool(trg.get('enabled', True))
        if self._handle is not None and self._ps is not None:
            ps = self._ps
            src = trg.get('source', 'A')
            src_enum = self._ch_enum(src) if src in ('A','B') else ps.PS5000A_CHANNEL['PS5000A_EXTERNAL']
            lvl_mv = int(float(trg.get('level_v', 0.0)) * 1000)
            direction = ps.PS5000A_THRESHOLD_DIRECTION['PS5000A_RISING'] if trg.get('edge') == 'Rising' else ps.PS5000A_THRESHOLD_DIRECTION['PS5000A_FALLING']
            enable = 1 if trg.get('enabled', True) else 0
            auto_ms = 100 if trg.get('mode') == 'Auto' else 0
            if trg.get('mode') == 'None':
                ps.ps5000aSetSimpleTrigger(self._handle, 0, src_enum, 0, direction, 0, 0)
            else:
                ps.ps5000aSetSimpleTrigger(self._handle, enable, src_enum, lvl_mv, direction, auto_ms, 0)

    async def zero_offset(self, channel: str) -> None:
        self._validate_channel(channel)
        self.state.channels[channel]['offset'] = 0.0
        if self._handle is not None and self._ps is not None:
            ch = self.state.channels[channel]
            self._ps.ps5000aSetChannel(self._handle, self._ch_enum(channel), 1 if ch.get('enabled') else 0, self._coupling_to_enum(ch.get('coupling','DC')), self._range_to_enum(ch.get('range','±2V')), c_float(0.0))

    async def auto_setup(self) -> Dict[str, Any]:
        """Auto setup approximating PicoScope UI behaviour.

        Strategy:
        - Enable channel A DC-coupled, start from moderate range (±2V or ±5V).
        - Capture a short frame to estimate peak-to-peak and dominant period.
        - Choose vertical range so signal spans ~7/10 divisions (headroom against clipping).
        - Choose timebase so ~2–4 cycles are visible across the 10-division width.
        - Set trigger to Auto, source A, threshold ~50% of amplitude, rising edge.
        """
        if not self.state.connected or self._handle is None:
            raise RuntimeError('Device not connected')

        ranges = self._params.get('input_ranges', [
            '±10mV','±20mV','±50mV','±100mV','±200mV','±500mV','±1V','±2V','±5V','±10V','±20V'
        ])

        def range_label_to_volts(label: str) -> float:
            try:
                if 'mV' in label:
                    return float(label.replace('±','').replace('mV',''))/1000.0
                return float(label.replace('±','').replace('V',''))
            except Exception:
                return 2.0

        def nearest_range_for_vpp(vpp: float) -> str:
            # Aim for ~70% of full scale (7 divisions of 10) for Vpp
            target_half = max(1e-6, vpp/2/0.7)
            best = ranges[0]
            for r in ranges:
                if range_label_to_volts(r) >= target_half:
                    best = r
                    break
            return best

        # 1) Baseline config
        await self.set_channel_config('A', { 'enabled': True, 'range': '±2V', 'coupling': 'DC', 'offset': 0.0 })
        await self.set_trigger_config({'mode': 'Auto', 'source': 'A', 'edge': 'Rising', 'level_v': 0.0, 'enabled': True})
        await self.set_timebase_config({'time_per_div': '1ms/div'})

        # 2) First capture
        res = await self.acquire_preview()
        a = res['waveforms'].get('A', [])
        if not a:
            return await self.get_status()

        # Counts -> volts estimate using current range
        fs_counts = 32767.0
        cur_range_v = range_label_to_volts(self.state.channels['A'].get('range','±2V'))
        max_c = max(a)
        min_c = min(a)
        vpp_est = (max_c - min_c)/fs_counts * (2*cur_range_v)

        # 3) Choose better vertical range if needed
        best_r = nearest_range_for_vpp(vpp_est)
        if best_r != self.state.channels['A']['range']:
            await self.set_channel_config('A', { 'range': best_r })
            res = await self.acquire_preview()
            a = res['waveforms'].get('A', a)
            cur_range_v = range_label_to_volts(best_r)
            max_c = max(a)
            min_c = min(a)
            vpp_est = (max_c - min_c)/fs_counts * (2*cur_range_v)

        # 4) Estimate period by rising-edge spacing (fallback to zero-crossing)
        dt = float(res.get('time_interval_ns', 0.0)) * 1e-9 or 1e-6
        thr_counts = (max_c + min_c)/2
        rising_idx: List[int] = []
        last = a[0]
        for i in range(1, len(a)):
            v = a[i]
            if last < thr_counts and v >= thr_counts:
                rising_idx.append(i)
            last = v
        period_s = 0.0
        if len(rising_idx) >= 2:
            gaps = [ (rising_idx[i+1]-rising_idx[i])*dt for i in range(len(rising_idx)-1) ]
            period_s = sum(gaps)/len(gaps)
        else:
            # Zero-crossings as crude fallback
            z = []
            last = a[0]
            for i in range(1, len(a)):
                v = a[i]
                if (last <= 0 and v > 0) or (last >= 0 and v < 0):
                    z.append(i)
                last = v
            if len(z) >= 3:
                gaps = [ (z[i+1]-z[i])*dt for i in range(len(z)-1) ]
                period_s = 2 * (sum(gaps)/len(gaps))  # two zero crossings per period

        # 5) Choose time/div to show ~3 cycles across 10 divisions
        if period_s > 0:
            desired_t_per_div = (3*period_s)/10.0
            # pick nearest allowed label
            tpdiv_labels: List[str] = self._params.get('time_per_div_options', []) or [
                '1ns/div','2ns/div','5ns/div','10ns/div','20ns/div','50ns/div','100ns/div','200ns/div','500ns/div',
                '1µs/div','2µs/div','5µs/div','10µs/div','20µs/div','50µs/div','100µs/div','200µs/div','500µs/div',
                '1ms/div','2ms/div','5ms/div','10ms/div','20ms/div','50ms/div','100ms/div','200ms/div','500ms/div',
                '1s/div','2s/div','5s/div'
            ]
            def label_to_seconds(lbl: str) -> float:
                s = lbl.lower().replace('/div','')
                mult = 1.0
                if 'ns' in s: mult = 1e-9
                elif 'µs' in s or 'us' in s: mult = 1e-6
                elif 'ms' in s: mult = 1e-3
                val = float(s.replace('ns','').replace('µs','').replace('us','').replace('ms','').replace('s',''))
                return val*mult
            best_lbl = min(tpdiv_labels, key=lambda L: abs(label_to_seconds(L) - desired_t_per_div))
            await self.set_timebase_config({'time_per_div': best_lbl})

        # 6) Trigger at mid-level
        lvl_v = (vpp_est/2.0) * 0.5  # 50% of half range to avoid chatter
        await self.set_trigger_config({'mode': 'Auto', 'source': 'A', 'edge': 'Rising', 'level_v': lvl_v, 'enabled': True})

        return await self.get_status()

    async def set_awg_config(self, config: Dict[str, Any]) -> None:
        awg = self.state.awg
        awg.update(config)
        if awg.get('shape') not in ('Sine','Square','Triangle','DC'):
            awg['shape'] = 'Sine'
        try:
            awg['frequency_hz'] = self._clamp(float(awg.get('frequency_hz', 1000.0)), 0.1, 20_000_000.0)
            awg['amplitude_vpp'] = self._clamp(float(awg.get('amplitude_vpp', 2.0)), 0.02, 20.0)
            awg['offset_v'] = self._clamp(float(awg.get('offset_v', 0.0)), -5.0, 5.0)
        except Exception:
            awg['frequency_hz'] = 1000.0
            awg['amplitude_vpp'] = 2.0
            awg['offset_v'] = 0.0
        awg['enabled'] = bool(awg.get('enabled', False))

    async def run(self) -> None:
        if not self.state.connected:
            raise RuntimeError('Device not connected')
        self.state.acquiring = True

    async def stop(self) -> None:
        self.state.acquiring = False

    async def acquire_preview(self) -> Dict[str, Any]:
        """Perform a single block acquisition on A and B using SDK."""
        if not self.state.connected or self._handle is None:
            raise RuntimeError('Device not connected')
        ps = self._ps
        handle = self._handle

        # Apply channel settings
        for ch_name in ('A','B'):
            ch = self.state.channels[ch_name]
            enabled = 1 if ch.get('enabled') else 0
            coup = self._coupling_to_enum(ch.get('coupling','DC'))
            rng = self._range_to_enum(ch.get('range','±2V'))
            offset = c_float(float(ch.get('offset', 0.0)))
            ps.ps5000aSetChannel(handle, self._ch_enum(ch_name), enabled, coup, rng, offset)
            # Optional bandwidth limiter
            bw_fun = getattr(ps, 'ps5000aSetBandwidthFilter', None)
            if bw_fun is not None:
                try:
                    bw = 1 if ch.get('bandwidth_limiter') else 0
                    bw_fun(handle, self._ch_enum(ch_name), bw)
                except Exception:
                    pass

        # Trigger already configured
        await self.set_trigger_config({})

        # Timebase
        tb_info = self._resolve_timebase(self.state.timebase.get('time_per_div','1ms/div'))
        n_samples = c_int32(tb_info['samples'])
        timebase_index = tb_info['index']

        # Buffers
        buffer_a = (c_int16 * n_samples.value)()
        buffer_b = (c_int16 * n_samples.value)()
        ps.ps5000aSetDataBuffer(handle, self._ch_enum('A'), byref(buffer_a), n_samples.value, 0, 0)
        ps.ps5000aSetDataBuffer(handle, self._ch_enum('B'), byref(buffer_b), n_samples.value, 0, 0)

        # Run block
        st = ps.ps5000aRunBlock(handle, 0, n_samples, timebase_index, None, 0, None, None)
        if st != 0:
            raise RuntimeError(f"RunBlock failed: {st}")
        self.state.acquiring = True

        ready = c_int16(0)
        while ready.value == 0:
            ps.ps5000aIsReady(handle, byref(ready))

        samples_out = c_int32(n_samples.value)
        overflow = c_int16()
        ps.ps5000aGetValues(handle, 0, byref(samples_out), 1, 0, 0, byref(overflow))
        self.state.acquiring = False

        count = samples_out.value
        invA = -1 if self.state.channels['A'].get('invert') else 1
        invB = -1 if self.state.channels['B'].get('invert') else 1
        data_a = [int(buffer_a[i]) * invA for i in range(count)]
        data_b = [int(buffer_b[i]) * invB for i in range(count)]
        self.state.last_waveform = {'A': data_a, 'B': data_b}
        return {
            'samples': count,
            'time_interval_ns': float(tb_info['time_interval_ns']),
            'overflow': int(overflow.value),
            'waveforms': self.state.last_waveform,
            'adc_max_counts': self.state.adc_max_counts,
        }
