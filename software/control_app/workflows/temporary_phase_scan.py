"""Explicitly authorized temporary experiment; never a promoted calibration.

The standard Phase Scan adapter remains qualification-gated. This separate
entrypoint accepts the operator's fixed electrical phase grid and records
controller-marker/electrical-sync coordinates. Ratios/reconstruction are saved
by PhaseScanRunner only after verified shutdown and native-data retention.
"""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import json

import numpy as np

from control_app.workflows.phase_scan import PhaseScanPlan, PhaseScanSettings, build_phase_scan_plan
from control_app.workflows.phase_scan_acquisition import LivePhaseScanAcquirer
from control_app.workflows.phase_scan_data import (
    Spectrum, acquisition_settings, compatible_readbacks, load_native, write_json,
)
from control_app.workflows.phase_scan_runner import Background
from control_app.workflows.single_detector_marker_identity import controller_marker_identity

MODE = 'temporary_single_detector_electrical_phase_scan_v1'
READBACK_KEYS = ('hf2li_device', 'hf2li_detector_settings')


@dataclass(frozen=True)
class ExperimentalPhaseScanPlan(PhaseScanPlan):
    def to_dict(self):
        result = super().to_dict()
        result.update(status='EXPERIMENTAL_PROGRAMMED_GRID', execution_mode=MODE)
        result['sequence']['phase_interval'] = 'Operator-programmed -11000 to +5000 us inclusive, in 50 us steps'
        result['limitations'][0] = ('Programmed phase bounds are an experimental acquisition request; '
                                    'observed electrical sync and controller markers define offline coordinates. '
                                    'Complete time-window coverage is evaluated from the records.')
        return result


class TemporaryPhaseScanAcquirer(LivePhaseScanAcquirer):
    def __init__(self, *, experimental_authorized=False, pump_authorized=False,
                 authorization_record='', engineering_sweep_bound_s=.020, **kwargs):
        super().__init__(**kwargs)
        self.experimental_authorized = experimental_authorized is True
        self.pump_authorized = pump_authorized is True
        self.authorization_record = str(authorization_record).strip()
        if engineering_sweep_bound_s != .020 or isinstance(engineering_sweep_bound_s, bool):
            raise ValueError('This temporary experiment uses the explicit 20 ms engineering sweep bound')
        self.engineering_sweep_bound_s = .020
        if self.qualified_trajectory is not None or self.qualified_sweep_active_s is not None or self.promoted_bundle is not None:
            raise ValueError('Experimental timing must not be supplied as a qualified trajectory or bundle')

    def resolve_plan(self, plan):
        if not self.experimental_authorized or not self.pump_authorized or not self.authorization_record:
            raise PermissionError('Explicit temporary-mode and pump authorization with an operator record is required')
        if plan.calibrated or plan.settings != PhaseScanSettings():
            raise ValueError('Temporary mode is restricted to the agreed 2000-1900 cm-1, 50 us, single-repetition experiment')
        preview = build_phase_scan_plan(plan.settings)
        self.plan = ExperimentalPhaseScanPlan(preview.settings, preview.phases_per_repetition,
            preview.scan_duration_s, preview.first_phase_tick, preview.trajectory_time_bounds_s, None)
        self.capture_window = {'duration_s': .02028, 'pretrigger_s': .0001,
            'engineering_sweep_bound_s': .020, 'posttrigger_margin_s': .00018,
            'basis': 'operator_authorized_engineering_envelope_not_calibration'}
        return self.plan

    def _validate_execution_plan(self, plan):
        if (not isinstance(plan, ExperimentalPhaseScanPlan) or plan.calibrated or
                plan != self.plan or not self.experimental_authorized or not self.pump_authorized):
            raise PermissionError('Only this explicitly authorized experimental plan can execute')

    def _qualification_metadata(self):
        return {'execution_mode': MODE, 'experimental_authorization_record': self.authorization_record,
                'trajectory_calibrated': False, 'engineering_sweep_bound_s': self.engineering_sweep_bound_s,
                'pump_time_basis': 'electrical_sync', 'wavenumber_basis': 'controller_markers',
                'optical_pump_arrival_verified': False, 'promoted_bundle_created': False}

    def prepare_blocks(self, plan, events, cancel):
        expected = [plan.event_at(i) for i in range(plan.total_scans)]
        if list(events) != expected:
            raise ValueError('Temporary mode requires exactly one baseline followed by the complete agreed phase set')
        return super().prepare_blocks(plan, events, cancel)

    def prepare(self, settings, store, cancel):
        readback = super().prepare(settings, store, cancel)
        write_json(store.path / 'experimental_mode.json', self._qualification_metadata())
        # Device-specific limits, QCL settings, trigger modes, and source clock
        # have been checked by the shared executor. Match the actual detector
        # settings/device to the separately imported blank at this boundary.
        return {key: readback[key] for key in READBACK_KEYS}

    def _observe_marker_channel(self, segment, record):
        super()._observe_marker_channel(segment, record)
        if controller_marker_identity(record, 21) is None:
            raise ValueError('Temporary scan requires verified per-QCL controller marker identity before triggering')

    def _validate_spectrum(self, event, spectrum):
        metadata = spectrum.metadata
        if metadata.get('wavenumber_basis') != 'controller_markers' or len(metadata.get('marker_ticks', [])) != 21:
            raise ValueError('Every temporary scan must retain exactly 21 identified controller markers')
        start, stop = metadata['sweep_active_ticks']
        duration = (stop-start)/metadata['clockbase_hz']
        if not .005 <= duration <= self.engineering_sweep_bound_s:
            raise ValueError('Observed Sweep Active is outside the experimental engineering envelope')
        if (spectrum.pump_time_s is not None) != event.pump_enabled:
            raise ValueError('Observed electrical pump event does not match the requested frame')
        if not np.all(np.isfinite(spectrum.sample_r) & (spectrum.sample_r > 0)):
            raise ValueError('Temporary scan contains nonpositive or invalid CH1 samples')
        metadata.update(execution_mode=MODE, independently_calibrated=False,
                        optical_pump_arrival_verified=False)
        return spectrum


def import_buffer_blank(directory, settings):
    """Validate the retained blank, then adapt field names in memory only."""
    directory = Path(directory).resolve()
    quality = json.loads((directory / 'analysis.json').read_text(encoding='utf-8-sig'))
    if not quality.get('usable_as_background') or quality.get('unusable_reasons'):
        raise ValueError('Selected buffer blank is not usable')
    native_path = (directory / quality['native_source']).resolve()
    result = json.loads((native_path.parent / 'result.json').read_text(encoding='utf-8-sig'))
    if (not result.get('capture_completed') or result.get('acquisition_error') or result.get('save_errors') or
            not result.get('cleanup', {}).get('safe_state_and_retained_settings_verified')):
        raise ValueError('Buffer blank acquisition or shutdown was not complete')
    spectrum_path = directory / 'ch1_spectrum.npz'
    spectrum = Spectrum.from_dict(load_native(spectrum_path)['spectrum'])
    metadata = spectrum.metadata
    if (metadata.get('record_role') != 'buffer_blank' or spectrum.pump_time_s is not None or
            metadata.get('wavenumber_basis') != 'controller_markers'):
        raise ValueError('An unpumped controller-marker buffer blank is required')
    profile = metadata['acquisition_settings']
    expected = {'start_cm1': settings.start_wavenumber_cm1, 'stop_cm1': settings.stop_wavenumber_cm1,
        'scan_rate_cm1_s': settings.scan_speed_cm1_s, 'external_rate_hz': settings.probe_repetition_rate_hz,
        'external_width_ns': settings.probe_pulse_width_ns,
        'mircat_internal_rate_hz': settings.mircat_internal_repetition_rate_hz,
        'mircat_internal_width_ns': settings.mircat_internal_pulse_width_ns,
        'qcl_current_ma': 750., 'qcl': 1, 'optical_triggering': 'EXTERNAL', 'process_triggering': 'EXTERNAL',
        'hf2li_preset': 'exploratory_phase_scan_single_detector', 'expected_markers': 21,
        'marker_interval_cm1': 5., 'marker_width_us': 125}
    for key, value in expected.items():
        if not compatible_readbacks(profile.get(key), value):
            raise ValueError(f'Buffer blank differs in {key}')
    readback = {key: deepcopy(metadata[key]) for key in READBACK_KEYS}
    converted = acquisition_settings(settings)
    metadata.update(source_acquisition_settings=deepcopy(profile), acquisition_settings=converted,
                    imported_spectrum_source=str(spectrum_path), acquisition_id=str(directory))
    # Preserve the original native record and spectrum unchanged in provenance.
    native = {'source_native_path': str(native_path), 'source_spectrum_path': str(spectrum_path),
              'source_native': load_native(native_path), 'source_quality': quality}
    return Background(spectrum, native, converted, readback, native_path)
