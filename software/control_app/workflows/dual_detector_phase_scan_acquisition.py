"""Simultaneous detector capture on the tested continuous regular scan engine.

Only detector configuration, retained streams, and wavelength/time alignment
vary here. Timing, 250 us FIRE delay, startup, deferred read, partial salvage,
safe idle, and restoration are inherited from the maintained regular executor.
"""
from __future__ import annotations

from copy import deepcopy
import math

import numpy as np

from control_app.workflows.phase_scan_data import SINGLE_DETECTOR_MODE, interpolate_supported
from control_app.workflows.phase_scan_native import demodulator_samples, spectrum_from_sweep
from control_app.workflows.regular_phase_scan_acquisition import RegularPhaseScanAcquirer


class DualDetectorPhaseScanAcquirer(RegularPhaseScanAcquirer):
    detector_input_indices = (0, 1)
    inactive_demodulators = (1, 4, 5)
    execution_mode = "dual_detector_phase_scan_v1"
    baseline_matching = "reviewed unpumped sample/reference ratio on measured wavelength; delay-corrected timestamps"

    def resolve_plan(self, plan):
        from control_app.workflows.dual_detector_phase_scan import DualDetectorPhaseScanPlan
        if not isinstance(plan, DualDetectorPhaseScanPlan):
            raise ValueError("Dual-detector acquisition requires a dual-detector plan")
        selection = plan.hf2_selection
        if self.hf2_selection is not None and self.hf2_selection != selection:
            raise ValueError("The resolved dual-detector HF2LI configuration is frozen for this acquisition")
        for role, index, adc in (("sample", 0, 0), ("reference", 3, 1)):
            channel = selection.get(role, {})
            if any(key not in channel for key in ("order", "timeconstant_s", "rate_sps")):
                raise ValueError(f"Resolve the {role} HF2LI settings before acquiring")
            # Wiring is fixed by the maintained assignment registry. Both
            # indices are checked explicitly; labels never infer the routing.
            if channel.get("demodulator", index) != index or channel.get("adcselect", adc) != adc:
                raise ValueError(f"The {role} assignment differs from maintained instrument wiring")
        return super().resolve_plan(deepcopy(plan))

    def _detector_metadata(self):
        from control_app.workflows.dual_detector_phase_scan_data import DETECTOR_MODE
        return {"detector_mode": DETECTOR_MODE,
                "detector_roles": deepcopy(self.hf2_selection.get("detector_roles", {})),
                "detector_assignments": deepcopy(self.plan.detector_assignments),
                "sample_demodulator": 0, "reference_demodulator": 3,
                "timing_demodulator": 2}

    def _acquisition_metadata(self):
        from control_app.workflows.dual_detector_phase_scan_data import experiment_contract
        return {**experiment_contract(self.plan), **self._detector_metadata(),
                "hf2_preset": "dual_detector_resolved",
                "preset_sources": ["regular_phase_scan_single_detector", "exploratory_phase_scan_poc"],
                "normalization": "Q=S/R; delta_absorbance=-log10(Q/Q0); absolute absorbance requires calibrated B",
                "hf2li_resolution": deepcopy(self.preparation_readback["hf2li_resolution"])}

    def _configure_hf_preset(self, saved, copied):
        # Reuse the regular probe/timing recipe and the maintained dual input
        # configuration. The latter is a repository preset, never run evidence.
        dual = self.hf.load_preset("exploratory_phase_scan_poc").settings
        reference_input = next(value for value in dual["signal_inputs"].values() if value["index"] == 1)
        copied["signal_inputs"]["ch2"] = deepcopy(reference_input)
        reference = deepcopy(next(value for value in dual["demodulators"] if value["index"] == 3))
        copied["demodulators"] = [value for value in copied["demodulators"] if value["index"] != 3]
        copied["demodulators"].append(reference)
        copied = super()._configure_hf_preset(saved, copied)
        for role, index in (("sample", 0), ("reference", 3)):
            channel = self.hf2_selection[role]
            values = next(value for value in copied["demodulators"] if value["index"] == index)
            values.update(enable=True, order=int(channel["order"]),
                          timeconstant_s=float(channel["timeconstant_s"]), rate_sps=float(channel["rate_sps"]))
        copied["acquisition"].update(demodulators=[0, 3], timing_demodulator_api_index=2,
                                     detector_mode=self._detector_metadata()["detector_mode"],
                                     reference_source="simultaneous_matched_buffer_path")
        return copied

    def prepare(self, settings, store, cancel):
        reference = self.hf2_selection["reference"]
        if self.plan.scan_duration_s < 2 / float(reference["rate_sps"]):
            raise ValueError("The scan is shorter than two reference-detector sample intervals; reduce scan speed or increase the supported rate")
        result = super().prepare(settings, store, cancel)
        from control_app.workflows.regular_phase_scan import filter_response
        channels = {}
        for role, index in (("sample", 0), ("reference", 3)):
            actual = {}
            for key, node in (("order", "order"), ("timeconstant_s", "timeconstant"), ("rate_sps", "rate")):
                value = self.hf_settings_snapshot["nodes"][f"/{self.hf.device_id}/demods/{index}/{node}"]["value"]
                if not math.isclose(float(value), float(self.hf2_selection[role][key]), rel_tol=1e-6, abs_tol=1e-12):
                    raise RuntimeError(f"HF2LI {role} {key} read back {value}; resolve supported settings again")
                actual[key] = value
            response = filter_response(actual["order"], actual["timeconstant_s"], actual["rate_sps"],
                                       self.hf2_selection["timing_rate_sps"], settings.scan_speed_cm1_s)
            channels[role] = {"actual": actual, "actual_estimates": response}
        result["hf2li_resolution"].update(channels)
        result["hf2li_resolution"]["actual"].update({role: value["actual"] for role, value in channels.items()})
        result.update(self._detector_metadata())
        self.preparation_readback = result
        return result

    def _daq_detector_options(self):
        return {"detector_indices": (0, 3), "timing_demodulator": 2,
                "detector_metadata": self._detector_metadata()}

    def _baseline_matching_metadata(self):
        return {"baseline_matching": self.baseline_matching}

    def prepare_blocks(self, plan, events, cancel):
        events = list(events)
        expected = [plan.event_at(index) for index in range(plan.total_scans)]
        if events not in (expected, expected[:1]):
            raise ValueError("Dual-detector mode supports an unpumped preliminary spectrum or the full pumped sequence")
        return super().prepare_blocks(plan, events, cancel)

    def _spectrum_from_native(self, native):
        from control_app.workflows.dual_detector_phase_scan_data import align_detector_spectrum
        origin = int(native["sweep_event_tick"])
        # Use the shared marker identity decoder without its historical
        # reference interpolation. Each detector then gets its own filter delay.
        identified = spectrum_from_sweep({**native, "detector_mode": SINGLE_DETECTOR_MODE},
            start_cm1=self.segments[0]["start_cm1"], stop_cm1=self.segments[0]["stop_cm1"],
            targets_cm1=self.targets, origin_tick=origin, pump_tick=native["pump_event_tick"],
            pump_reference="electrical_sync")
        metadata = {**identified.metadata, **self._detector_metadata()}
        metadata.pop("detector_input", None)
        if metadata.get("wavenumber_basis") != "controller_markers":
            raise ValueError("Dual-detector spectra require observed controller-identified wavelength markers")
        clockbase = float(native["clockbase_hz"])
        def seconds(ticks):
            return np.asarray([(int(tick)-origin)/clockbase for tick in ticks], dtype=float)
        marker_t = seconds(metadata["marker_ticks"])
        marker_wn = np.asarray(metadata["marker_wavenumbers_cm1"], dtype=float)
        signals = {}
        for role, index in (("sample", 0), ("reference", 3)):
            data = demodulator_samples(native, index)
            actual = self.preparation_readback["hf2li_resolution"][role]["actual"]
            delay = float(actual["order"])*float(actual["timeconstant_s"])
            raw_time = seconds(data["timestamp"])
            effective_time = raw_time-delay
            selected = (effective_time >= marker_t[0]) & (effective_time <= marker_t[-1])
            signals[role] = (raw_time[selected], np.hypot(data["x"], data["y"])[selected],
                             interpolate_supported(marker_t, marker_wn, effective_time[selected]), delay)
            metadata[f"{role}_timestamps_ticks"] = data["timestamp"][selected]
            metadata[f"{role}_selected_native_indices"] = np.flatnonzero(selected)
            metadata[f"{role}_outside_marker_support_indices"] = np.flatnonzero(~selected)
        metadata["outside_marker_support_reason"] = "Effective detector time falls outside identified measured wavelength-marker coverage; native values retained"
        sample, reference = signals["sample"], signals["reference"]
        metadata.update(hf2li_resolution=deepcopy(self.preparation_readback["hf2li_resolution"]),
                        filter_delay_basis="HF2LI n-pole low-frequency group delay n*tau; no deconvolution",
                        filter_alignment_limitation="Group delay correction is a filter model, not a measured optical impulse-response calibration")
        return align_detector_spectrum(*sample[:3], *reference[:3],
            sample_filter_delay_s=sample[3], reference_filter_delay_s=reference[3], metadata=metadata,
            pump_time_s=identified.pump_time_s)

    def _validate_spectrum(self, event, spectrum):
        result = super()._validate_spectrum(event, spectrum)
        result.metadata.update(self._detector_metadata())
        result.metadata["record_role"] = ("pumped_sample_reference" if event.pump_enabled else
                                          "unpumped_sample_reference_baseline")
        return result
