"""Independent contract checks against actual installed-service signatures."""
from dataclasses import replace
from datetime import datetime, timezone
from threading import Event
from types import SimpleNamespace
from unittest.mock import create_autospec

import numpy as np
import pytest

from control_app.devices.hf2li_service import HF2LIService
from control_app.devices.mircat_service import MircatService
from control_app.devices.t660_service import T660Service
from control_app.measurement_modules.single_pump_scan_burst.acquisition import (
    ConnectedBurstAdapter, ReadinessError, reconstruct_native,
)
from control_app.measurement_host.context import ContextFactory
from control_app.measurement_modules.single_pump_scan_burst.planner import compile_plan, compile_preliminary
from control_app.measurement_modules.single_pump_scan_burst.settings import example_settings


def _native_streams(*, descending=False, missing_end=False, marker_count=3):
    # Keep integers beyond exact binary64 integer resolution to exercise native
    # preservation independently from floating point display coordinates.
    origin = np.uint64(2**54)
    count = 2 * marker_count + 6
    ticks = origin + np.arange(count, dtype=np.uint64) * 10
    words = np.zeros(count, np.uint32)
    words[2:(count if missing_end else 2 * marker_count + 3)] |= np.uint32(1 << 21)
    words[np.arange(3, 2 * marker_count + 3, 2)] |= np.uint32(1 << 22)
    if not descending:
        words |= np.uint32(1 << 20)
    detector_ticks = origin + np.arange(3, 2 * marker_count + 2, dtype=np.uint64) * 10
    return {2: {"timestamp": ticks, "dio": words},
            0: {"timestamp": detector_ticks, "x": np.arange(1, len(detector_ticks) + 1, dtype=float), "y": np.zeros(len(detector_ticks))}}


@pytest.mark.parametrize("descending", [False, True])
def test_native_marker_direction_preserves_reverse_and_forward_coordinates(descending):
    streams = _native_streams(descending=descending)
    markers = [1950., 1925., 1900.] if descending else [1900., 1925., 1950.]
    result = reconstruct_native(streams, clockbase_hz=210_000_000,
                                markers_cm1=markers, expected_scans=1)
    expected = np.linspace(markers[0], markers[-1], 5)
    np.testing.assert_array_equal(result["wavenumber_cm1"], expected)
    np.testing.assert_array_equal(result["native_sample_ticks"], streams[0]["timestamp"])
    assert result["native_sample_ticks"].dtype == np.uint64


def test_incomplete_sweep_activity_cannot_be_accepted_as_a_complete_scan():
    with pytest.raises(ReadinessError, match="[Ss]weep|[Ii]ncomplete|[Ee]nd"):
        reconstruct_native(_native_streams(missing_end=True), clockbase_hz=210_000_000,
                           markers_cm1=[1900., 1925., 1950.], expected_scans=1)


def _adapter(*, marker_interval=25., requested_rate=1000000.):
    settings = replace(example_settings(), tuning_settling_time_s=0., probe_rate_hz=requested_rate)
    plan = compile_plan(settings)
    assert plan.valid, plan.errors
    operation = SimpleNamespace(configuration={}, instance_id=settings.instance_id, hardware=False)
    store = SimpleNamespace(append_event=lambda *a, **kw: None, save_record=lambda *a, **kw: None)
    adapter = ConnectedBurstAdapter(SimpleNamespace(), operation, plan,
                                    cancel=Event(), progress=lambda **kw: None, store=store)
    adapter.recipe["trajectory"].update(marker_interval_cm1=marker_interval, marker_width_us=20)
    adapter.clock = create_autospec(T660Service, instance=True)
    adapter.timing = create_autospec(T660Service, instance=True)
    adapter.hf = create_autospec(HF2LIService, instance=True)
    adapter.qcl = create_autospec(MircatService, instance=True)
    adapter.timing.preload_frame_table.return_value = {"physical_frame_count": len(plan.blocks[0].frames)}
    adapter.qcl.is_tuned.return_value = True
    adapter.qcl.get_scan_waiting_process_trigger.return_value = True
    adapter.hf.get_oscillator_frequency.return_value = plan.selected_values["probe_rate_hz"]["selected"]
    adapter.hf.read_acquisition_health.return_value = {"reference_locked": True, "clock_locked": True, "overload": False}
    adapter.qcl.get_sweep_parameters.return_value = {
        "start_cm1": settings.scan_start_cm1, "stop_cm1": settings.scan_stop_cm1,
        "scan_rate_cm1_s": settings.scan_speed_cm1_s, "repetitions": plan.blocks[0].scan_count,
    }
    adapter.qcl.get_wavelength_trigger_channel_params.return_value = {
        "channel": settings.qcl, "units": 2, "units_name": "cm-1", "start": settings.scan_start_cm1,
        "stop": settings.scan_stop_cm1, "interval": marker_interval, "num_triggers": 3,
    }
    return adapter, plan


def test_burst_programming_uses_actual_host_service_signatures_and_selected_clock():
    adapter, plan = _adapter(requested_rate=1000000.004)
    adapter.program_block(plan.blocks[0], pump_allowed=True)
    adapter.qcl.start_sweep_scan.assert_called_once_with(start_cm1=1900., stop_cm1=1950.,
        scan_rate_cm1_s=5000., qcl=1, repetitions=10)
    adapter.qcl.start_emission.assert_called_once_with()
    arguments = adapter.timing.preload_frame_table.call_args.kwargs
    assert arguments["input_frequency_hz"] == plan.selected_values["probe_rate_hz"]["selected"]
    assert arguments["predivider"] == plan.blocks[0].predivider
    assert adapter.recipe["qcl_pulse_parameters"]["pulse_rate_hz"] == plan.selected_values["probe_rate_hz"]["selected"]
    np.testing.assert_array_equal(adapter.marker_targets, [1900., 1925., 1950.])


def test_contradictory_controller_marker_interval_is_rejected_before_acquisition():
    adapter, plan = _adapter(marker_interval=20.)
    with pytest.raises(ReadinessError, match="[Mm]arker|[Ii]nterval|[Ee]ndpoint"):
        adapter.program_block(plan.blocks[0], pump_allowed=True)
    adapter.timing.start_frame_table.assert_not_called()


def test_shutdown_keeps_unsettled_sdk_programming_an_unverified_host_fault():
    adapter, _ = _adapter()
    adapter.pending = [SimpleNamespace(is_alive=lambda: True)]
    result = adapter.restore()
    assert result["safe_verified"] is False
    assert "in progress" in result["errors"][0]
    adapter.clock.set_trigger_source.assert_not_called()


def test_shutdown_does_not_call_a_failed_disable_safe():
    adapter, _ = _adapter()
    adapter.devices = {"t660_1": adapter.clock, "t660_2": adapter.timing}
    for device in adapter.devices.values():
        device.read_active_settings.return_value = {"queries": {"trigger_source": {"response": "OFF"}},
            "channels": {ch: {"enabled": {"response": "0"}} for ch in "ABCD"}}
    adapter.clock.disable_channel.side_effect = RuntimeError("injected unacknowledged disable")
    result = adapter.restore()
    assert result["safe_verified"] is False
    assert any("unacknowledged disable" in item for item in result["errors"])
    adapter.timing.close.assert_called_once()


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_connected_adapter_preflight_capture_and_restore_through_injected_host_services(mode, tmp_path):
    """Run the real scientific adapter using spec-checked installed services.

    Factories are injected into the host's simulation lane so this test cannot
    accidentally enumerate or connect to a physical instrument.
    """
    settings = replace(example_settings(mode), preliminary_scan_count=1, tuning_settling_time_s=0.,
        hardware_evidence={}, calibration_ids=(), promoted_bundle_ids=(), controls_record_ids=(),
        sample_id="", preparation_id="", accepted_state_id="", matrix_id="", cell_id="", position_id="",
        temperature_identity="", measured_temperature_k=None, example_only=False)
    plan = compile_plan(settings)
    block = compile_preliminary(plan)
    hf = create_autospec(HF2LIService, instance=True)
    qcl = create_autospec(MircatService, instance=True)
    clock, timing = (create_autospec(T660Service, instance=True) for _ in range(2))
    devices = {"hf2li": hf, "mircat": qcl, "t660_1": clock, "t660_2": timing}
    context = ContextFactory(configuration_provider=lambda: {"devices": {}},
        simulated_device_factories={name: (lambda *, configuration, unit=unit, **kw: unit) for name, unit in devices.items()},
        save_root_provider=lambda: tmp_path).for_experiment("single_pump_scan_burst").for_mode(mode)
    operation = context.begin_operation(settings=settings.to_dict(), hardware=False)
    retained = []
    store = SimpleNamespace(append_event=lambda *args: retained.append(args), save_record=lambda *args: retained.append(args),
                            save_chunk=lambda *args: retained.append(args))
    adapter = ConnectedBurstAdapter(context, operation, plan, cancel=Event(), progress=lambda **kw: None, store=store)
    hf.device_id = "dev18500"
    hf.export_settings_snapshot.return_value = {"read_errors": [], "nodes": {}}
    hf.compare_settings_snapshots.return_value = {"match": True}
    hf.get_clockbase.return_value = 210_000_000
    hf.get_oscillator_frequency.return_value = settings.probe_rate_hz
    hf.read_acquisition_health.return_value = {"reference_locked": True, "clock_locked": True, "overload": False}
    detector_cap = {"rates_sps": (settings.sample_rate_hz,), "orders": (1,),
                    "timeconstants_by_order": {1: (settings.hf2_filter_tc_s,)}}
    hf.discover_phase_scan_capabilities.return_value = {**detector_cap, "timing_rate_sps": settings.timing_rate_hz, "verified": True}
    hf.discover_dual_phase_scan_capabilities.return_value = {"sample": detector_cap, "reference": detector_cap,
        "timing_rate_sps": settings.timing_rate_hz, "verified": True}
    def node(_kind, path):
        if "/sigins/" in path:
            return 1.0
        if path.endswith("/rate"):
            return settings.timing_rate_hz if "/demods/2/" in path else settings.sample_rate_hz
        if path.endswith("/order"):
            return 1
        return settings.hf2_filter_tc_s
    hf._get_node.side_effect = node
    qcl.get_num_installed_qcls.return_value = 1
    qcl.get_qcl_tuning_range.return_value = {"min_cm1": 1850., "max_cm1": 2000.}
    qcl.get_qcl_pulse_rate.return_value = settings.probe_rate_hz
    qcl.get_qcl_pulse_width.return_value = settings.probe_pulse_width_s * 1e9
    qcl.get_qcl_current.return_value = settings.probe_current_ma
    qcl.set_qcl_pulse_params.side_effect = lambda **values: {**values,
        "preserved_current_ma": settings.probe_current_ma, "current_ma_used": values["current_ma"]}
    qcl.get_wavelength_trigger_params.return_value = {"pulse_mode": 1, "process_trigger_mode": 1,
        "start": 1900., "stop": 1950., "interval": 25., "units": 2, "dwell_us": 0, "after_off_us": 0}
    qcl.get_wavelength_trigger_pulse_width_us.return_value = 20
    qcl.get_wavelength_trigger_channel_params.return_value = {"channel": 1, "units": 2, "units_name": "cm-1",
        "start": 1900., "stop": 1950., "interval": 5., "num_triggers": 11}
    qcl.get_sweep_parameters.return_value = {"start_cm1": 1900., "stop_cm1": 1950.,
        "scan_rate_cm1_s": 5000., "repetitions": 1}
    qcl.is_tuned.return_value = qcl.get_scan_waiting_process_trigger.return_value = True
    qcl.is_emission_on.return_value = qcl.is_laser_armed.return_value = False
    qcl.read_state.return_value = {key: False for key in ("emission_on", "armed", "scan_in_progress",
        "scan_active", "scan_paused", "scan_waiting_process_trigger")}
    def reply(value):
        return {"ok": True, "response": str(value)}
    for unit in (clock, timing):
        unit.read_active_settings.return_value = {"queries": {"trigger_source": reply("OFF"),
            "predivider": reply(1), "synth_frequency": reply(settings.probe_rate_hz)},
            "channels": {ch: {"enabled": reply(0), "timing_mode": reply("DW"), "polarity": reply("POS"),
                "termination": reply("50OHM"), "delay_edge": reply("0s"), "width_edge": reply("1us")}
                for ch in "ABCD"}}
        unit.command.side_effect = lambda command, **kwargs: "0" if "RELTo" in command else "1us" if command.endswith(("2?", "4?", "6?", "8?")) else "0s"
    timing.preload_frame_table.return_value = {"physical_frame_count": len(block.frames)}
    timing.get_frames_status.return_value = "DONE"
    timing.verified_frame_capacity.return_value = 8192
    timing.identify.return_value = "T660 installed-test-peer"
    readback = adapter.configure(pumped=False)
    assert readback["clockbase_hz"] == 210_000_000
    hf.start_acquisition.assert_not_called()
    assert adapter.pico is None
    adapter.program_block(block, pump_allowed=False)
    native = _native_streams(marker_count=11)
    if mode == "dual":
        native[3] = {key: np.array(value, copy=True) for key, value in native[0].items()}
    # A real LabOne poll wraps per-demod native records inside data; snapshots
    # before and after the burst have no fabricated samples or duplicate ticks.
    polls = [{"data": {}}, {"data": {f"/dev18500/demods/{i}/sample": record for i, record in native.items()}}, {"data": {}}]
    hf.read_acquisition.side_effect = polls
    captured = adapter.capture_block(block, pump_allowed=False)
    hf.start_acquisition.assert_called_once_with(demodulators=[0, 2] if mode == "single" else [0, 2, 3], fields=("x", "y", "dio"))
    assert captured["observed_pump_count"] == 0 and captured["observed_scan_count"] == 1
    np.testing.assert_array_equal(captured["native"]["native_sample_ticks"], native[0]["timestamp"])
    assert ("reference" in captured["native"]) == (mode == "dual")
    result = adapter.restore()
    assert result["safe_verified"], result["errors"]
    assert any(entry[0].startswith("hf2-native-") for entry in retained)
    hf.close.assert_called_once()
    qcl.deinitialize.assert_called_once()
