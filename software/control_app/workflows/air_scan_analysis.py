"""Read-only diagnostic products for the independent air scan; never a background."""
from __future__ import annotations

import csv
from pathlib import Path
import numpy as np

from control_app.workflows.phase_scan_data import write_json, interpolate_supported
from control_app.workflows.phase_scan_native import demodulator_samples, high_intervals


def analyze_air_scan(directory, record):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    directory = Path(directory)
    profile = record.get('scan_profile', {'start_cm1': 2050., 'stop_cm1': 1650.,
                                          'scan_rate_cm1_s': 40., 'qcl_current_ma': 750., 'expected_markers': 81})
    timing = demodulator_samples(record, 2)
    ticks = timing['timestamp']
    dio = timing['dio'].astype(np.uint32)
    intervals = high_intervals(ticks, (dio & (1 << 21)) != 0)
    if len(intervals) != 1:
        raise ValueError(f'Expected one complete Sweep Active interval; found {len(intervals)}. Native data retained.')
    start, stop = intervals[0]
    clock = float(record['clockbase_hz'])
    duration = (stop-start)/clock
    high = (dio & (1 << 22)) != 0
    marker_ticks = ticks[np.flatnonzero(~high[:-1] & high[1:])+1]
    markers = marker_ticks[(marker_ticks >= start) & (marker_ticks <= stop)]
    checks = record.get('hf2li_input_checks')
    statuses = ([x['status'] for x in checks] if checks else
                [x['hf2li_input_status'] for x in record.get('scan_status_observations', [])])
    summary = {
        'run_classification': 'EXPLORATORY_PROOF_OF_CONCEPT', 'publication_eligible': False,
        'sweep_duration_s': duration, 'markers_observed': len(markers), 'markers_expected': profile['expected_markers'],
        'wavenumber_basis': 'PROVISIONAL linear axis between observed Sweep Active edges; endpoint marker identity unresolved',
        'source': 'hf2li_native.npz and picoscope_ch_a/b_adc.npy',
        'pump_events': 0, 'accepted_as_background': False, 'channels': {},
        'picoscope_ext_autotrigger_ms': 0, 'picoscope_overflow': record['picoscope_metadata']['overflow'],
        'clipping_status_scope': 'before, during and after scan' if checks else 'during scan',
        'warnings': record.get('warnings', []),
    }
    figure = Figure(figsize=(11, 8), constrained_layout=True)
    FigureCanvasAgg(figure)
    axes = figure.subplots(3, 1)
    colours = ('#287bbc', '#d96d12')
    traces = []
    with (directory/'detectors.csv').open('x', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['input', 'time_from_sweep_active_s', 'provisional_wavenumber_cm1', 'R_V',
                         'run_classification', 'publication_eligible'])
        for index, demod in enumerate((0, 3)):
            data = demodulator_samples(record, demod)
            selected = (data['timestamp'] >= start) & (data['timestamp'] <= stop)
            selected_ticks = data['timestamp'][selected]
            if len(selected_ticks) < 2:
                raise ValueError(f'Input {index+1} has insufficient in-sweep samples; native data retained')
            seconds = np.asarray([(int(t)-start)/clock for t in selected_ticks])
            r = np.hypot(data['x'][selected], data['y'][selected])
            wn = profile['start_cm1'] + (profile['stop_cm1']-profile['start_cm1'])*seconds/duration
            traces.append((seconds, wn, r))
            clipping = [s.get(f'status/flags/adcclip/{index}') for s in statuses]
            gaps = int(np.count_nonzero(np.diff(seconds) > 1.75/1798.9309210526317))
            summary['channels'][str(index+1)] = {
                'samples': len(r), 'in_sweep_gaps': gaps, 'clip_checks': len(clipping),
                'clipped_checks': sum(isinstance(v, (int, np.integer)) and v != 0 for v in clipping),
                'clip_read_errors': sum(not isinstance(v, (int, np.integer)) for v in clipping),
                'leading_gap_s': float(seconds[0]), 'trailing_gap_s': float(duration-seconds[-1]),
            }
            label = f'Input {index+1} / Pico {"AB"[index]}'
            # Break display paths at missing samples, preserving the original CSV values.
            plot_r = r.copy()
            plot_r[np.r_[False, np.diff(seconds) > 1.75/1798.9309210526317]] = np.nan
            axes[0].plot(wn, plot_r*1000, color=colours[index], lw=.65, label=label)
            writer.writerows((index+1, t, x, v, 'EXPLORATORY_PROOF_OF_CONCEPT', False)
                             for t, x, v in zip(seconds, wn, r))

    meta = record['picoscope_metadata']
    for index, channel in enumerate(('a', 'b')):
        adc = np.load(directory/f'picoscope_ch_{channel}_adc.npy', mmap_mode='r')
        scale = (5., 10.)[index]/meta['maximum_adc_value']
        block = 100_000
        blocks = len(adc)//block
        used = blocks*block
        means = adc[:used].reshape(blocks, block).mean(axis=1)*scale
        times = (np.arange(blocks)*block+block/2-meta['pre_trigger_samples'])*meta['sample_interval_ns']*1e-9
        axes[1].plot(times, means, color=colours[index], lw=.8)
        centre = min(len(adc)-106, meta['pre_trigger_samples'] + round(5./(meta['sample_interval_ns']*1e-9)))
        sample = adc[centre:centre+105].astype(float)*scale
        axes[2].plot(np.arange(len(sample))*meta['sample_interval_ns']*.001, sample,
                     color=colours[index], lw=.8)
        summary['channels'][str(index+1)].update(
            raw_min_v=float(adc.min())*scale, raw_max_v=float(adc.max())*scale,
            raw_samples=len(adc), raw_mean_v=float(adc.mean())*scale)
    clipped = any(c['clipped_checks'] or c['clip_read_errors'] for c in summary['channels'].values())
    summary['detector_status'] = 'CLIPPED OR CLIPPING STATUS UNKNOWN' if clipped else 'No clipping seen in sampled status checks'
    axes[0].invert_xaxis()
    axes[0].set(xlabel='Provisional wavenumber (cm⁻¹)', ylabel='HF2LI R (mV)')
    axes[0].legend(loc='upper right')
    axes[1].set(xlabel='Time from Pico EXT trigger (s)', ylabel='Pico mean (V)')
    axes[2].set(xlabel='Time within raw waveform near 5 s (µs)', ylabel='Pico voltage (V)')
    for axis in axes:
        axis.grid(alpha=.25)
    figure.suptitle(f"MIRcat sweep · {profile['start_cm1']:g} → {profile['stop_cm1']:g} cm⁻¹ · "
                   f"{profile['scan_rate_cm1_s']:g} cm⁻¹/s · {profile['qcl_current_ma']:g} mA\n"
                   f"{summary['detector_status']} · {len(markers)}/{profile['expected_markers']} markers · NOT FOR PUBLICATION", fontsize=12)
    summary['plot_path'] = str(directory/'air_scan.png')
    figure.savefig(summary['plot_path'], dpi=130)
    write_json(directory/'analysis.json', summary)
    aligned = interpolate_supported(traces[1][0], traces[1][2], traces[0][0],
                                    max_gap=1.75*float(np.median(np.diff(traces[1][0]))))
    summary['scan_rows'] = [[float(x), float(a), float(b)] for x, a, b in zip(traces[0][1], traces[0][2], aligned)]
    return summary
