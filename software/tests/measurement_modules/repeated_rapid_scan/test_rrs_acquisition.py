"""Native acquisition and preservation tests: all devices are explicitly injected."""
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest

from control_app.measurement_host.context import ContextFactory
from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError
from control_app.measurement_host.presentation import StartSnapshot
from control_app.measurement_modules.repeated_rapid_scan.acquisition import InstalledDevicesAcquirer, decode_native_movie
from control_app.measurement_modules.repeated_rapid_scan.planner import build_plan
from control_app.measurement_modules.repeated_rapid_scan.runner import RepeatedRapidScanRunner
from control_app.measurement_modules.repeated_rapid_scan.settings import RepeatedRapidScanSettings
from control_app.measurement_modules.repeated_rapid_scan.simulation import SimulationAcquirer
from control_app.measurement_modules.repeated_rapid_scan.persistence import load_run


class Signal:
    def __init__(self): self.values = []
    def emit(self, *args): self.values.append(args)


class Worker:
    def __init__(self):
        self.cancel_event = Event()
        self.message, self.progress = Signal(), Signal()
        self.actions = []
    def check_cancelled(self):
        if self.cancel_event.is_set(): raise InterruptedError("operator stop")


def context(tmp_path, mode="single"):
    factory = ContextFactory(save_root_provider=lambda: tmp_path)
    return factory.for_experiment("repeated_rapid_scan").for_mode(mode)


def settings(mode="single", **changes):
    return replace(RepeatedRapidScanSettings(mode=mode), controls=(), phase_offsets_s=(0., .025),
                   directions=("forward",), post_scans=20, **changes)


def snapshot(ctx, plan, kind, preliminary=None):
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=False)
    return StartSnapshot(operation, kind, plan, preliminary)


def preliminary(ctx, plan):
    runner = RepeatedRapidScanRunner(ctx)
    blank = runner.run(snapshot(ctx, plan, "blank"), Worker()) if plan.mode == "single" else None
    sample = runner.run(snapshot(ctx, plan, "preliminary", {"blank": blank}), Worker())
    return sample


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_rrs_simulated_end_to_end_one_pump_per_movie_and_native_roundtrip(tmp_path, mode):
    ctx, plan = context(tmp_path, mode), build_plan(settings(mode))
    sample = preliminary(ctx, plan)
    runner = RepeatedRapidScanRunner(ctx)
    result = runner.run(snapshot(ctx, plan, "measurement", sample), Worker())
    assert result["status"] == "complete"
    assert len(result["native_movies"]) == len(plan.movies)
    assert all(len(movie.pump_observations) == 1 for movie in result["native_movies"])
    assert all(len(movie.scans) == plan.movies[0].scans_per_movie for movie in result["native_movies"])
    assert not result["qualification_movies"]
    reloaded = load_run(result["output_path"], expected_mode=mode).record
    for original, retained in zip(result["native_movies"], reloaded["native_movies"]):
        np.testing.assert_array_equal(original.scans[0].sample.timestamps_s, retained.scans[0].sample.timestamps_s)
        np.testing.assert_array_equal(original.scans[0].sample.values, retained.scans[0].sample.values)
        assert retained.scans[0].sample.timestamps_s.dtype == np.int64
    assert result["restoration"]["safe_verified"]


def test_rrs_dual_same_movie_duration_and_reference_simultaneous(tmp_path):
    durations = []
    for mode in ("single", "dual"):
        ctx, plan = context(tmp_path / mode, mode), build_plan(settings(mode))
        sim = SimulationAcquirer(ctx, snapshot(ctx, plan, "measurement").operation, plan)
        sim.prepare(Worker())
        movie = sim.capture(plan.movies[0], Worker())
        durations.append(movie.metadata["planned_duration_s"])
        if mode == "dual":
            np.testing.assert_array_equal(movie.scans[0].sample.timestamps_s, movie.scans[0].reference.timestamps_s)
    assert durations[0] == durations[1]


@pytest.mark.parametrize("fault", ["reset", "offband_reset"])
def test_rrs_failed_reset_retains_finite_outcome_and_prevents_next_pump(tmp_path, fault):
    ctx, plan = context(tmp_path), build_plan(settings())
    sample = preliminary(ctx, plan)
    created = []
    def factory(*args):
        value = SimulationAcquirer(*args, faults={fault: True}); created.append(value); return value
    result = RepeatedRapidScanRunner(ctx, factory).run(snapshot(ctx, plan, "measurement", sample), Worker())
    assert result["status"] == "incomplete_recovery"
    assert result["next_pump_inhibited"]
    assert created[0].pump_count == 1
    assert len(result["native_movies"]) == 1


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_rrs_first_start_records_baseline_without_blank_qualification_or_prompt(tmp_path, mode):
    ctx, plan = context(tmp_path, mode), build_plan(settings(mode))
    worker = Worker()
    result = RepeatedRapidScanRunner(ctx).run(snapshot(ctx, plan, "measurement"), worker)
    assert result["status"] == "complete"
    assert result["auto_preliminary"]["kind"] == "preliminary"
    assert result["auto_preliminary"]["baseline"].complete
    assert not result["qualification_movies"]
    assert all(not movie.pump_observations for movie in result["auto_preliminary"]["native_movies"])
    assert len(result["native_movies"]) == len(plan.movies)
    if mode == "single":
        assert result["blank"] is None
        assert any("No compatible blank" in warning for warning in result["warnings"])


@pytest.mark.parametrize("fault", ["missing_pump", "extra_pump"])
def test_rrs_missing_or_extra_independent_pump_is_not_repaired(tmp_path, fault):
    ctx, plan = context(tmp_path), build_plan(settings())
    sample = preliminary(ctx, plan)
    runner = RepeatedRapidScanRunner(ctx, lambda *args: SimulationAcquirer(*args, faults={fault: True}))
    with pytest.raises(ValueError, match="pump count"):
        runner.run(snapshot(ctx, plan, "measurement", sample), Worker())
    assert len(runner.last_result["native_movies"]) == 1
    assert runner.last_result["restoration"]["safe_verified"]


def test_rrs_cancel_acquisition_preserves_native_and_cleanup_failure_wins(tmp_path):
    ctx, plan = context(tmp_path), build_plan(settings())
    sample = preliminary(ctx, plan)
    for cleanup in (False, True):
        runner = RepeatedRapidScanRunner(ctx, lambda *args: SimulationAcquirer(*args, faults={"cancel_scan": 2, "cleanup": cleanup}))
        with pytest.raises(RuntimeError if cleanup else InterruptedError, match="Restoration failed" if cleanup else "Acquisition stopped"):
            runner.run(snapshot(ctx, plan, "measurement", sample), Worker())
        assert len(runner.last_result["raw_movies"][0]["scans"]) == 3
        loaded = load_run(runner.last_result["output_path"]).record
        assert loaded["status"] == ("cleanup_failed" if cleanup else "cancelled")


def test_rrs_early_cancel_still_saves_without_constructing_devices(tmp_path):
    ctx, plan = context(tmp_path), build_plan(settings())
    worker = Worker(); worker.cancel_event.set()
    def never(*args): raise AssertionError("must not construct device")
    runner = RepeatedRapidScanRunner(ctx, never)
    with pytest.raises(InterruptedError):
        runner.run(snapshot(ctx, plan, "preliminary"), worker)
    assert load_run(runner.last_result["output_path"]).record["status"] == "cancelled"


def test_rrs_storage_failure_reports_failure_after_cleanup(tmp_path):
    ctx, plan = context(tmp_path, "dual"), build_plan(settings("dual"))
    def broken(*args, **kwargs): raise OSError("disk full")
    runner = RepeatedRapidScanRunner(ctx, saver=broken)
    with pytest.raises(RuntimeError, match="disk full"):
        runner.run(snapshot(ctx, plan, "preliminary"), Worker())
    assert runner.last_result["restoration"]["safe_verified"]
    assert runner.last_result["status"] == "preservation_failed"


def native_fixture(mode="single", count=3):
    # All clocks are native int64 ticks. Distinct measured scan periods survive.
    rate = 10000
    times = np.arange(int((count+.5)*.1*rate)) / rate
    ticks = 2**53 + 71 + np.arange(len(times), dtype=np.int64)
    dio = np.zeros(len(times), dtype=np.uint32)
    axis = np.linspace(1898., 1951., 7)
    for scan in range(count):
        begin = int((.01+scan*.1+(scan%2)*.001)*rate)
        end = begin+800
        dio[begin:end] |= 1 << 21
        for marker in np.linspace(begin+10, end-10, len(axis)).astype(int):
            dio[marker:marker+2] |= 1 << 22
    dio[1250:1252] |= 1 << 17
    data = {f"/dev/demods/{index}/sample": {"timestamp": ticks.copy(), "x": np.ones(len(ticks)), "y": np.zeros(len(ticks)), "dio": dio.copy()}
            for index in ((0, 2, 3) if mode == "dual" else (0, 2))}
    return [{"data": data}], {"roles": {"sample_demodulator": 0, "reference_demodulator": 3, "timing_demodulator": 2},
        "clockbase_hz": rate, "marker_bits": {"sweep_active": 21, "wavelength_trigger": 22, "pump_sync": 17, "scan_direction": 20},
        "marker_wavenumbers_cm1": axis, "trajectory_calibration_id": "native-marker-calibration"}


def test_rrs_native_decoder_uses_observed_jitter_and_ticks_without_fabricating_pump():
    chunks, readbacks = native_fixture()
    movie = decode_native_movie(chunks, {"movie_id": "native", "direction": "forward", "pump_count": 1}, settings(), readbacks)
    assert len(movie.scans) == 3
    assert len(movie.pump_observations) == 1
    assert movie.pump_observations[0].timestamp_s == pytest.approx(.125)
    assert movie.scans[1].trajectory.timestamps_s[0]-movie.scans[0].trajectory.timestamps_s[0] == pytest.approx(.101)
    assert movie.scans[0].sample.timestamps_s.dtype == np.int64
    chunks[0]["data"]["/dev/demods/2/sample"]["dio"] &= np.uint32(~(1 << 17) & 0xffffffff)
    missing = decode_native_movie(chunks, {"movie_id": "missing", "pump_count": 1}, settings(), readbacks)
    assert not missing.pump_observations


def test_rrs_installed_capture_upload_acknowledgements_and_native_continuity(tmp_path):
    ctx, plan = context(tmp_path), build_plan(settings())
    count = plan.movies[0].scans_per_movie
    chunks, readbacks = native_fixture(count=count)
    class HF:
        device_id = "dev"
        def __init__(self): self.starts = 0; self.reads = 0; self.stops = 0
        def start_acquisition(self, **kwargs): self.starts += 1; self.args = kwargs
        def read_acquisition(self, duration):
            self.reads += 1
            return chunks[0] if self.reads == 1 else {"data": {}}
        def stop_acquisition(self): self.stops += 1
    class Timing:
        def __init__(self): self.frames = None; self.started = 0
        def disable_channel(self, ch): pass
        def enable_channel(self, ch): pass
        def set_trigger_source(self, source): pass
        def command(self, *args, **kwargs): pass
        def preload_frame_table(self, frames, **kwargs):
            self.frames = frames; self.args = kwargs
            for index in range(len(frames)):
                kwargs["cancel_check"](); kwargs["progress"](index+1, len(frames))
            return {"physical_frame_count": len(frames), "acknowledged": True}
        def start_frame_table(self): self.started += 1
        def get_frames_status(self): return "DONE"
        def get_shot_count(self): return len(self.frames)
        def read_active_settings(self): return {"queries": {"synth_frequency": {"ok": True, "response": "1000000"}}}
    class QCL:
        def get_qcl_pulse_rate(self, qcl): assert qcl == 1; return 2500000.
        def get_qcl_pulse_width(self, qcl): assert qcl == 1; return 100.
        def get_qcl_current(self, qcl): assert qcl == 1; return 600.
        def get_qcl_pulse_limits(self, qcl):
            assert qcl == 1
            return {"max_pulse_rate_hz": 3e6, "max_pulse_width_ns": 500., "max_duty_cycle": 50.}
        def get_qcl_current_limits(self, qcl): assert qcl == 1; return (1., 1000.)
        def stop_scan_if_needed(self): pass
        def turn_emission_off(self): pass
        def tune_to_wavenumber(self, *args, **kwargs): assert kwargs["qcl"] == 1
        def is_tuned(self): return True
        def set_external_sweep_trigger_params(self, **kwargs): pass
        def set_wavelength_trigger_pulse_width_us(self, value): pass
        def start_emission(self): pass
        def cancel_manual_tune(self): pass
        def start_sweep_scan(self, **kwargs):
            assert kwargs["qcl"] == 1
            self.sweep = kwargs
        def get_sweep_parameters(self): return self.sweep
        def get_wavelength_trigger_channel_params(self, qcl):
            assert qcl == 1
            return {"units": 2, "start": 1898., "stop": 1951., "interval": 53/6, "num_triggers": 7}
        def get_scan_waiting_process_trigger(self): return True
        def is_interlock_set(self): return True
        def get_system_error_word(self): return 0
        def get_scan_status(self): return {"scan_in_progress": False}
    acquirer = InstalledDevicesAcquirer(ctx, snapshot(ctx, plan, "measurement").operation, plan)
    hf, clock, timing = HF(), Timing(), Timing()
    acquirer.devices = {"hf2li": hf, "t660_1": clock, "t660_2": timing, "mircat": QCL()}
    acquirer.config = {"marker_interval_cm1": 53/6, "marker_width_us": 1, "qcl": 2}
    acquirer.settings = SimpleNamespace(**vars(plan.settings), qcl=2)
    acquirer.readbacks = {**readbacks, "required_demodulators": (0, 2),
                          "mircat_pulse": {"qcl": 1, "pulse_rate_hz": 2500000., "pulse_width_ns": 100., "current_ma": 600.}}
    acquirer._quality = lambda: {"locked": True, "overload": False}
    movie = acquirer.capture(plan.movies[0], Worker())
    assert hf.starts == hf.stops == timing.started == 1
    assert len(movie.scans) == count
    assert len(timing.frames) == count+1
    assert acquirer.devices["mircat"].sweep["repetitions"] == count
    assert not any(values["enabled"] for values in timing.frames[-1]["channels"].values())
    assert acquirer.raw_movies[0]["readbacks"]["shots"] == count+1
    assert sum(frame["channels"]["A"]["enabled"] for frame in timing.frames) == 1
    assert sum(frame["channels"]["B"]["enabled"] for frame in timing.frames) == 1
    assert acquirer.raw_movies[0]["upload"]["acknowledged"]
    assert len(movie.pump_observations) == 1  # It is read at .125 s, not copied from planned .5 s.
    chunks, _ = native_fixture(count=count)
    for values in chunks[0]["data"].values():
        values["dio"] &= np.uint32(~(1 << 17) & 0xffffffff)
    hf.reads = 0
    from control_app.measurement_modules.repeated_rapid_scan.runner import _unpumped
    baseline = acquirer.capture(_unpumped(plan.movies[0], ":baseline"), Worker())
    assert len(baseline.scans) == count
    assert len(timing.frames) == count+1
    assert not any(values["enabled"] for values in timing.frames[-1]["channels"].values())
    assert acquirer.devices["mircat"].sweep["repetitions"] == count
    assert not baseline.pump_observations


def test_rrs_hardware_owner_held_through_restore_save_and_sibling_manual_contention(tmp_path):
    coordinator = HardwareCoordinator(tmp_path / "instrument.lock")
    lifecycle = []
    def fake_factory(**kwargs):
        assert coordinator.snapshot()["state"] == "owned"
        lifecycle.append("construct injected service")
        return SimpleNamespace(configuration=kwargs["configuration"])
    factory = ContextFactory(save_root_provider=lambda: tmp_path, ownership=coordinator,
                             real_device_factories={"injected_native": fake_factory})
    ctx = factory.for_experiment("repeated_rapid_scan").for_mode("dual")
    sibling = factory.for_experiment("repeated_rapid_scan").for_mode("single")
    plan = replace(build_plan(settings("dual")), readiness_items=())
    class OwnedSimulation(SimulationAcquirer):
        def prepare(self, worker):
            self.service = ctx.devices.create("injected_native", self.operation)
            assert coordinator.snapshot()["state"] == "owned"
            with pytest.raises(OwnershipError):
                sibling.begin_operation(settings().to_dict(), hardware=True)
            with pytest.raises(OwnershipError):
                coordinator.acquire("manual-controls", purpose="manual controls contention")
            super().prepare(worker)
        def restore(self, worker):
            assert coordinator.snapshot()["state"] == "owned"
            lifecycle.append("restore")
            return super().restore(worker)
    from control_app.measurement_modules.repeated_rapid_scan.persistence import save_run
    def save(*args, **kwargs):
        assert coordinator.snapshot()["state"] == "owned"
        lifecycle.append("preserve")
        return save_run(*args, **kwargs)
    worker = Worker()
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True, cancel=lambda reason: worker.cancel_event.set())
    runner = RepeatedRapidScanRunner(ctx, OwnedSimulation, saver=save)
    with ctx.hardware_scope(operation):
        result = runner.run(StartSnapshot(operation, "preliminary", plan, None), worker)
    assert lifecycle == ["construct injected service", "restore", "preserve"]
    assert coordinator.snapshot()["state"] == "free"
    assert result["status"] == "complete"


@pytest.mark.parametrize("failure", ["prepare", "cleanup", "storage", "early_cancel"])
def test_rrs_hardware_failure_token_outcomes_are_explicit(tmp_path, failure):
    coordinator = HardwareCoordinator(tmp_path / "instrument.lock")
    factory = ContextFactory(save_root_provider=lambda: tmp_path, ownership=coordinator)
    ctx = factory.for_experiment("repeated_rapid_scan").for_mode("dual")
    plan = replace(build_plan(settings("dual")), readiness_items=())
    worker = Worker()
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True, cancel=lambda reason: worker.cancel_event.set())
    if failure == "early_cancel": worker.cancel_event.set()
    def save(*args, **kwargs):
        if failure == "storage": raise OSError("retained native path unavailable")
        from control_app.measurement_modules.repeated_rapid_scan.persistence import save_run
        return save_run(*args, **kwargs)
    runner = RepeatedRapidScanRunner(ctx, lambda *args: SimulationAcquirer(*args, faults={failure: True}), saver=save)
    with ctx.hardware_scope(operation), pytest.raises((RuntimeError, InterruptedError)):
        runner.run(StartSnapshot(operation, "preliminary", plan, None), worker)
    assert coordinator.snapshot()["state"] == ("fault" if failure in ("cleanup", "storage") else "free")
    if failure in ("cleanup", "storage"):
        with pytest.raises(OwnershipError):
            ctx.begin_operation(plan.settings.to_dict(), hardware=True)
        recovery = coordinator.acquire("test-explicit-recovery", recovery=True)
        coordinator.release(recovery, safe_verified=True, preservation_verified=True)


def test_rrs_processing_cancellation_preserves_movie_and_reports_normal_stop(tmp_path, monkeypatch):
    from control_app.measurement_modules.repeated_rapid_scan import runner as module
    ctx, plan = context(tmp_path, "dual"), build_plan(settings("dual"))
    sample = preliminary(ctx, plan)
    def cancelled(*args, **kwargs):
        raise InterruptedError("Acquisition stopped during native analysis")
    monkeypatch.setattr(module, "reconstruct_movie", cancelled)
    runner = RepeatedRapidScanRunner(ctx)
    with pytest.raises(InterruptedError, match="Acquisition stopped"):
        runner.run(snapshot(ctx, plan, "measurement", sample), Worker())
    assert len(runner.last_result["native_movies"]) == 1
    assert load_run(runner.last_result["output_path"]).record["status"] == "cancelled"


def test_rrs_normal_abort_targets_only_its_own_worker(tmp_path):
    ctx = context(tmp_path)
    first, second = RepeatedRapidScanRunner(ctx), RepeatedRapidScanRunner(ctx)
    first._cancel_event, second._cancel_event = Event(), Event()
    first.request_abort("one tab only")
    assert first._cancel_event.is_set()
    assert not second._cancel_event.is_set()


def test_rrs_installed_t660_pending_upload_acknowledgement_and_cancel():
    from control_app.devices.t660_service import T660Service
    plan = build_plan(settings())
    compiled = plan.movies[0].compiled
    unit = T660Service("t660_2", {"role": "trains_frames"})
    commands, acknowledged = [], []
    def command(value, **kwargs):
        commands.append(value)
        if value == "FEATure:FRAMe?": return "1"
        if ";" in value: return ";".join("OK" for _ in value.split(";"))
        lookup = {"TFRame:LOOP:FIRST?": "0", "TFRame:LOOP:LAST?": str(len(compiled.frames)-1),
                  "TFRame:LOOP:CouNT?": "0", "TRIGger:EXTernal:PREDiv?": str(compiled.predivider)}
        return lookup.get(value, "OK")
    unit.command = command
    result = unit.preload_frame_table(list(compiled.frames), predivider=compiled.predivider,
        input_frequency_hz=compiled.input_frequency_hz, progress=lambda done, total: acknowledged.append(done))
    uploads = [value for value in commands if ":TFRame:STORe" in value]
    assert len(uploads) == len(compiled.frames)
    assert len(uploads[0].split(";")) == 21
    assert uploads[1] == ":TFRame:STORe 1"  # Stable pending fields are not redundantly sent.
    assert acknowledged[-1] == result["physical_frame_count"]
    assert not any(value in ("START", "TFRame:STArt") for value in commands)
    commands.clear(); acknowledged.clear()
    def cancel_check():
        if acknowledged and acknowledged[-1] == 2:
            raise InterruptedError("cancel after two acknowledged frames")
    with pytest.raises(InterruptedError, match="two acknowledged"):
        unit.preload_frame_table(list(compiled.frames), predivider=compiled.predivider,
            input_frequency_hz=compiled.input_frequency_hz, progress=lambda done, total: acknowledged.append(done),
            cancel_check=cancel_check)
    assert len([value for value in commands if ":TFRame:STORe" in value]) == 2
    assert not any(value in ("START", "TFRame:STArt") for value in commands)


def test_rrs_native_direction_mismatch_and_calibrated_optical_zero_are_explicit():
    chunks, readbacks = native_fixture()
    readbacks["direction_levels"] = {"forward": 1, "reverse": 0}
    readbacks["optical_time_zero"] = {"calibration_id": "optical-zero-v1", "electrical_sync_to_optical_s": 2e-6,
                                       "uncertainty_s": 5e-7}
    movie = decode_native_movie(chunks, {"movie_id": "native", "direction": "forward", "pump_count": 1}, settings(), readbacks)
    assert "direction_mismatch" in movie.scans[0].flags
    assert movie.scans[0].trajectory.direction == "reverse"
    assert movie.pump_observations[0].timestamp_s == pytest.approx(.125002)
    assert movie.pump_observations[0].basis == "calibrated_optical_time_zero"
    assert not movie.pump_observations[0].metadata["per_event_optical_observation"]


def test_rrs_native_independent_detector_latency_uses_corrected_reference_support():
    from control_app.measurement_modules.repeated_rapid_scan.processing import reconstruct_movie
    chunks, readbacks = native_fixture(mode="dual")
    readbacks["detector_clock_corrections"] = {
        "sample": {"latency_s": .0001, "calibration_id": "sample-response-measured"},
        "reference": {"latency_s": .0003, "calibration_id": "reference-response-measured"}}
    movie = decode_native_movie(chunks, {"movie_id": "latency", "direction": "forward", "pump_count": 1}, settings("dual"), readbacks)
    assert movie.scans[0].sample.clock_id == "hf2li_sample"
    assert movie.scans[0].reference.clock_id == "hf2li_reference"
    assert movie.scans[0].trajectory.clock_id == movie.pump_observations[0].clock_id == "hf2li"
    reconstruction = reconstruct_movie(movie, alignment_tolerance_s=1e-10)
    point = reconstruction.points[0]
    assert point.reference_indices[20] == 22
    assert point.time_s[20] == pytest.approx((int(movie.scans[0].sample.timestamps_s[20])-movie.scans[0].sample.timestamp_origin)/10000-.0001-.125)


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_rrs_dark_controls_retain_zero_native_diagnostics_without_false_absorbance(tmp_path, mode):
    ctx = context(tmp_path, mode)
    plan = build_plan(replace(settings(mode), controls=("dark",)))
    sample = preliminary(ctx, plan)
    result = RepeatedRapidScanRunner(ctx).run(snapshot(ctx, plan, "measurement", sample), Worker())
    assert result["status"] == "complete"
    darks = [movie for movie in result["native_movies"] if movie.metadata["control"] == "dark"]
    assert len(darks) == 2
    for movie in darks:
        assert not movie.pump_observations
        assert np.count_nonzero(movie.scans[0].sample.values) == 0
        if mode == "dual": assert np.count_nonzero(movie.scans[0].reference.values) == 0
        processed = next(value for value in result["processed"] if value.movie_id == movie.movie_id)
        assert not np.any(processed.points[0].valid)
        assert np.all(np.isnan(processed.points[0].delta_absorbance))

class InstalledTransport:
    """Injected serial, LabOne and ctypes transports; production services execute."""
    def __init__(self, mode, coordinator, worker, fault=None):
        from copy import deepcopy
        self.copy = deepcopy
        self.mode, self.coordinator, self.worker, self.fault = mode, coordinator, worker, fault
        self.calls, self.subscribed, self.nodes = [], set(), {}
        self.train_starts = 0
        self.qcl_calls, self.pulse_writes = [], []
        self.vendor_duty_percent = 50.
        self.vendor_first_limits = None
        self.vendor_limit_reads = 0
        self.frequency_readback_offset_hz = 0.
        self.emission, self.armed = False, False
        self.sweep = [1898., 1951., 530., 2, 1]
        self.trigger = [0, 0, 1898., 1951., 53./11, 2, 0, 0]
        self.pulse, self.marker_width = [2500000., 100., 600.], 100
        self.frame_generation = self.polled_generation = 0
        self.units = {}
        for port in ('COM3', 'COM7'):
            self.units[port] = {'TRIG:SOUR': 'OFF', 'TRIG:FREQ:SYN': '1000000',
                'TRIGGER:EXTERNAL:PREDIV': '1', 'GATE:MODE': '0', 'BURST:MODE': 'OFF',
                'frames': [], 'pending': {}, 'refs': {i: (0 if i % 2 else i-1) for i in range(1,9)},
                'times': {i: (0. if i % 2 else 1e-7) for i in range(1,9)},
                'channels': {ch: {'on': 'OFF', 'mode': 'DW', 'pol': 'POS', 'term': 'ON'} for ch in 'ABCD'},
                'status': 'OFF', 'shots': '0'}
        for i in range(6):
            for name, value in {'enable': int(i in (0,3)), 'adcselect': int(i == 3), 'oscselect': 0,
                    'harmonic': 1, 'order': 4, 'timeconstant': .0001, 'rate': 2000. if i != 3 else 4000., 'trigger': 0}.items():
                self.nodes[f'/dev2468/demods/{i}/{name}'] = value
        for i in (0,1):
            for name, value in {'ac': 1, 'imp50': 0, 'diff': 0, 'range': 1.}.items():
                self.nodes[f'/dev2468/sigins/{i}/{name}'] = value
        for name, value in {'enable': 1, 'adcselect': 4, 'freqcenter': 1e6, 'harmonic': 1, 'order': 4, 'adcthreshold': 0, 'locked': 1}.items():
            self.nodes[f'/dev2468/plls/0/{name}'] = value
        if self.fault == 'unlocked': self.nodes['/dev2468/plls/0/locked'] = 0
        self.nodes.update({'/dev2468/oscs/0/freq': 1e6, '/dev2468/clockbase': 20000,
                          '/dev2468/system/extclk': 1})
        for path in ('plllock', 'dcmlock', 'adcclip/0', 'adcclip/1'):
            self.nodes['/dev2468/status/flags/'+path] = 0

    def own(self, action):
        assert self.coordinator.snapshot()['state'] == 'owned', action
        self.calls.append(action)

    # LabOne API transport. No production HF2LI methods are replaced.
    def getList(self, path): self.own('hf read '+path); return ['dev2468']
    def getString(self, path): self.own('hf read '+path); return 'dev2468'
    def listNodes(self, path, *args): self.own('hf list'); return ['/dev2468']
    def connectDevice(self, *args): self.own('hf connect')
    def disconnect(self): self.own('hf disconnect')
    def getInt(self, path):
        self.own('hf read '+path)
        if self.fault == 'unknown_health' and '/status/flags/' in path:
            raise OSError('node unavailable')
        return int(self.nodes[path])
    def getDouble(self, path): self.own('hf read '+path); return float(self.nodes[path])
    def setInt(self, path, value): self.own('hf set '+path); self.nodes[path] = int(value)
    def setDouble(self, path, value):
        self.own('hf set '+path)
        # Demonstrate real native quantization; it is retained and accepted.
        self.nodes[path] = 20000. if path.endswith('/demods/2/rate') and value > 20000. else float(value)
    def sync(self): self.own('hf sync')
    def subscribe(self, path): self.own('hf subscribe'); self.subscribed.add(path)
    def unsubscribe(self, path): self.own('hf unsubscribe'); self.subscribed.discard(path)
    def poll(self, *args):
        self.own('hf poll')
        if self.polled_generation == self.frame_generation:
            return {}
        self.polled_generation = self.frame_generation
        unit = self.units['COM7']
        frames = unit['frames']
        period = int(unit['TRIGGER:EXTERNAL:PREDIV']) / float(self.units['COM3']['TRIG:FREQ:SYN'].removesuffix('HZ'))
        count = int(self.sweep[4])
        marker_count = round(abs(self.trigger[3]-self.trigger[2])/self.trigger[4])+1
        output = {}
        for path in self.subscribed:
            rate = self.nodes[path.replace('/sample', '/rate')]
            step = int(20000/rate)
            local_ticks = np.arange(0, round((count+1)*period*20000), step, dtype=np.int64)
            times = local_ticks/20000
            dio = np.zeros(len(times), dtype=np.uint32)
            for index in range(count):
                start = round(index*period*20000)+40
                stop = start + round(min(.09, period-.004)*20000)
                dio[(local_ticks >= start) & (local_ticks < stop)] |= 1 << 21
                for marker in np.linspace(start+20, stop-20, marker_count).round().astype(int):
                    dio[(local_ticks >= marker) & (local_ticks < marker+max(round(self.marker_width*.02), 4))] |= 1 << 22
                frame = frames[index]
                if frame.get(('B','mode')) == 'ON':
                    pump = index*period+frame['time3']
                    dio[(times >= pump) & (times < pump+.001)] |= 1 << 17
            output[path] = {'timestamp': 2**53+71+local_ticks, 'x': np.ones(len(times)),
                            'y': np.zeros(len(times)), 'dio': dio, 'frequency': np.full(len(times), 1e6)}
        if self.train_starts >= 2 and self.fault == 'overload':
            self.nodes['/dev2468/status/flags/adcclip/0'] = 1
        if self.train_starts >= 2 and self.fault == 'abort':
            self.worker.cancel_event.set()
            unit['status'] = 'RUNNING'
        return output

    # MIRcat SDK functions are produced dynamically at the ctypes boundary.
    def __getattr__(self, name):
        if not name.startswith('MIRcatSDK_'): raise AttributeError(name)
        def call(*args):
            self.own(name)
            key = name.removeprefix('MIRcatSDK_')
            qcl_argument = {'GetQclTuningRange': 0, 'GetQCLPulseRate': 0, 'GetQCLPulseWidth': 0,
                'GetQCLCurrent': 0, 'GetQCLPulseLimits': 0, 'GetQCLMinPulsedCurrent': 0,
                'GetQCLMaxPulsedCurrent': 0, 'SetQCLParams': 0, 'TuneToWW': 2,
                'StartSweepScan': 6, 'GetWlTrigChanParams': 0}.get(key)
            if qcl_argument is not None:
                self.qcl_calls.append((key, args[qcl_argument].value))
            def val(arg): return arg.value
            def put(values, pointers=args):
                for pointer, value in zip(pointers, values): pointer._obj.value = value
            if key == 'TuneToWW' and self.fault in ('changed_width', 'changed_rate', 'changed_current'):
                self.pulse[{'changed_rate': 0, 'changed_width': 1, 'changed_current': 2}[self.fault]] *= .9
            elif key == 'TuneToWW' and self.fault == 'changed_external_rate':
                self.units['COM3']['TRIG:FREQ:SYN'] = '4000000'
            elif key in ('Initialize', 'DeInitialize', 'TuneToWW', 'CancelManualTuneMode'): pass
            elif key == 'ArmLaser': self.armed = True
            elif key == 'DisarmLaser': self.armed = self.fault == 'disarm'
            elif key == 'IsLaserArmed': put([self.armed])
            elif key == 'TurnEmissionOn': self.emission = True
            elif key == 'TurnEmissionOff': self.emission = False
            elif key == 'StopScanInProgress': pass
            elif key in ('IsConnectedToLaser','IsInterlockedStatusSet','IsKeySwitchStatusSet','IsLaserArmed','AreTECsAtSetTemperature','IsTuned','GetScanWaitingProcessTrigger'): put([True])
            elif key == 'IsEmissionOn': put([self.emission])
            elif key in ('GetSystemErrorWord','GetStatusMask'): put([0])
            elif key in ('GetNumInstalledQcls','GetActiveQcl'): put([1])
            elif key == 'GetQclTuningRange': put([1800., 2100., 2], args[1:])
            elif key in ('GetQCLPulseRate','GetQCLPulseWidth','GetQCLCurrent'):
                put([self.pulse[('GetQCLPulseRate','GetQCLPulseWidth','GetQCLCurrent').index(key)]], args[1:])
            elif key == 'GetQCLPulseLimits':
                self.vendor_limit_reads += 1
                limits = self.vendor_first_limits if self.vendor_first_limits is not None and self.vendor_limit_reads == 1 else [3e6, 500., self.vendor_duty_percent]
                if isinstance(limits, Exception): raise limits
                put(limits, args[1:])
            elif key == 'GetQCLMinPulsedCurrent': put([1], args[1:])
            elif key == 'GetQCLMaxPulsedCurrent': put([1000], args[1:])
            elif key == 'SetQCLParams':
                self.pulse = [val(arg) for arg in args[1:]]
                self.pulse_writes.append(tuple(self.pulse))
                if self.fault == 'rounded_pulse_above_limit' and len(self.pulse_writes) == 1:
                    self.pulse[1] = 121.
            elif key == 'GetWlTrigParams': put(self.trigger)
            elif key == 'SetWlTrigParams': self.trigger = [val(arg) for arg in args]
            elif key == 'GetWlTrigPulseWidth': put([self.marker_width])
            elif key == 'SetWlTrigPulseWidth': self.marker_width = val(args[0])
            elif key == 'StartSweepScan': self.sweep = [val(arg) for arg in args[:5]]
            elif key in ('GetSweepStartWW','GetSweepStopWW','GetSweepScanSpeed'):
                put([self.sweep[('GetSweepStartWW','GetSweepStopWW','GetSweepScanSpeed').index(key)], 2])
            elif key == 'GetSweepNumScans': put([self.sweep[4]])
            elif key == 'GetWlTrigChanParams': put([2, self.trigger[2], self.trigger[3], self.trigger[4], round(abs(self.trigger[3]-self.trigger[2])/self.trigger[4])+1], args[1:])
            elif key == 'GetScanStatus': put([False, False, False, 0, 100, self.sweep[1], 2, False, False])
            else: raise AssertionError('Unhandled SDK call '+key)
            return 0
        return call

    def serial(self, port, **kwargs):
        harness = self
        class Serial:
            response = b''
            def reset_input_buffer(self): pass
            def flush(self): pass
            def close(self): harness.own('serial close '+port)
            def write(self, payload):
                command = payload.decode('ascii').strip()
                self.response = (';'.join(harness.command(port, entry) for entry in command.split(';'))+'\n').encode('ascii')
            def readline(self):
                value, self.response = self.response, b''
                return value
        return Serial()

    def command(self, port, command):
        import re
        from control_app.measurement_modules.repeated_rapid_scan.acquisition import seconds
        self.own(port+' '+command)
        text = command.upper().lstrip(':')
        unit = self.units[port]
        if text == '*IDN?': return 'Berkeley,T660,123,F5'
        if text == 'TRIG:FREQ:SYN?' and self.frequency_readback_offset_hz:
            return str(float(unit['TRIG:FREQ:SYN'].removesuffix('HZ')) + self.frequency_readback_offset_hz)
        if text == 'FEATURE:FRAME?': return '1'
        if text.startswith('TIME:RELTO'):
            edge = int(re.search(r'\d+', text)[0])
            if '?' in text: return str(unit['refs'][edge])
            unit['refs'][edge] = int(text.split()[-1]); return 'OK'
        if text.startswith(('TIME:DEL','TIME:QUEUE')):
            edge = int(re.search(r'\d+', text)[0])
            if '?' in text: return str(unit['times'][edge])+'s'
            value = seconds(command.split()[-1])
            if 'QUEUE' in text: unit['pending']['time'+str(edge)] = value
            else: unit['times'][edge] = value
            return 'OK'
        if text == 'TIME:COMMIT':
            for key, value in unit['pending'].items():
                if isinstance(key, str) and key.startswith('time'): unit['times'][int(key[4:])] = value
            return 'OK'
        if text.startswith('CHANNEL:QUEUE:'):
            field = text.split(':')[2].split()[0]
            channel, value = text.split(' ', 1)[1].replace(',', '').split()
            unit['pending'][channel, field.lower()] = value
            return 'OK'
        if text.startswith('TFRAME:STORE '):
            index = int(text.split()[-1])
            if index == 0: unit['frames'] = []
            unit['frames'].append(self.copy(unit['pending'])); return 'OK'
        if text.startswith('CHAN'):
            channel = text.split()[-1]
            state = unit['channels'][channel]
            if '?' in text:
                if text.startswith('CHAN:ON?'): return state['on']
                if text.startswith('CHAN:TIMINGMODE?'): return state['mode']
                if text.startswith('CHAN:50OHM?'): return state['term']
                if text.startswith('CHANNEL:ACTIVE:POLARITY?'): return state['pol']
            else:
                verb = text.split(':')[1].split()[0]
                if verb in ('ON','OFF'): state['on'] = verb
                elif verb in ('POS','NEG'): state['pol'] = verb
                elif verb in ('50OHM','LOWZ'): state['term'] = 'ON' if verb == '50OHM' else 'OFF'
                elif verb in ('DELAYWIDTH','RISEFALL'): state['mode'] = 'DW' if verb == 'DELAYWIDTH' else 'RF'
                else: raise AssertionError(text)
                return 'OK'
        if text == 'TFRAME:START':
            self.train_starts += 1; self.frame_generation += 1
            unit['status'], unit['shots'] = 'DONE', str(len(unit['frames']))
            return 'OK'
        if text == 'TFRAME:STOP': unit['status'] = 'OFF'; return 'OK'
        if text == 'TFRAME:STATUS?': return unit['status']
        if text == 'TRIG:SHOTS?': return unit['shots']
        if text.endswith('?'):
            key = text[:-1]
            defaults = {'CLOCK:MODE': 'IN' if port == 'COM3' else 'OUT', 'CLOCK:EXTERNAL': '1', 'CLOCK:FREQUENCY': '10000000', 'CLOCK:STATUS': '1',
                'TRIGGER:INPUT:POLARITY': 'POS', 'TRIGGER:INPUT:TERMINATION': '50OHM', 'TRIGGER:INPUT:VOLTAGE': '2', 'TRAIN:ACTIVE:COUNT': '0'}
            if key not in unit and key not in defaults: raise AssertionError(text)
            return unit.get(key, defaults.get(key))
        if ' ' in text:
            key, value = text.split(' ', 1)
            unit[key] = value
        return 'OK'


def installed_context(tmp_path, monkeypatch, mode, worker, fault=None, configuration_changes=None):
    import serial
    import yaml
    from control_app.devices.hf2li_service import HF2LIService
    from control_app.devices.mircat_service import MircatService
    from control_app.devices.t660_service import T660Service
    from control_app.measurement_host.device_factories import installed_device_factories
    configuration = yaml.safe_load(Path('instrument/hardware_configuration.yaml').read_text())
    configuration['devices']['hf2li']['device_id'] = 'dev2468'
    if configuration_changes: configuration.update(configuration_changes)
    if fault == 'unlocked': configuration['repeated_rapid_scan'] = {'lock_timeout_s': .001}
    coordinator = HardwareCoordinator(tmp_path/'installed.lock')
    transport = InstalledTransport(mode, coordinator, worker, fault)
    monkeypatch.setattr(serial, 'Serial', transport.serial)
    command = T660Service.command
    monkeypatch.setattr(T660Service, 'command', lambda self, text, **kwargs: command(self, text, **{**kwargs, 'delay_s': 0}))
    monkeypatch.setattr(HF2LIService, '_load_labone_module', lambda self: SimpleNamespace(ziDAQServer=lambda *args: transport))
    monkeypatch.setattr(MircatService, '_load_sdk', lambda self: transport)
    monkeypatch.setattr(MircatService, '_bind_functions', lambda self: None)
    ctx = ContextFactory(configuration_provider=lambda: configuration,
        real_device_factories=installed_device_factories(), ownership=coordinator,
        save_root_provider=lambda: tmp_path).for_experiment('repeated_rapid_scan').for_mode(mode)
    return ctx, transport, coordinator


def installed_plan(mode):
    return build_plan(replace(settings(mode), manual_overrides={'measured_scan_period_s': .1,
        'scan_speed_cm1_s': 530., 'controls': ()}), capabilities={'selected_baseline_bytes': 65536})


@pytest.mark.parametrize('mode', ['single', 'dual'])
def test_rrs_real_installed_factories_first_start_with_injected_native_transports(tmp_path, monkeypatch, mode):
    worker = Worker()
    ctx, transport, coordinator = installed_context(tmp_path, monkeypatch, mode, worker)
    plan = installed_plan(mode)
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True)
    runner = RepeatedRapidScanRunner(ctx)
    with ctx.hardware_scope(operation):
        result = runner.run(StartSnapshot(operation, 'measurement', plan, None), worker)
    assert result['status'] == 'complete', result['assessments']
    assert coordinator.snapshot()['state'] == 'free'
    assert result['auto_preliminary']['baseline'].complete
    assert not result['qualification_movies']
    assert len(result['native_movies']) == 2
    assert all(len(movie.pump_observations) == 1 for movie in result['native_movies'])
    assert result['capabilities']['live_settings']['sample_rate_hz'] == 2000.
    assert result['capabilities']['acquisition_timing_rate_hz'] == 20000.
    assert result['plan']['settings']['sample_rate_hz'] == 2000.
    assert result['readbacks']['health_configured']['schema_version'] == 'hf2li-acquisition-health/1'
    assert result['capabilities']['actual_scan_period_s'] is None
    assert result['capabilities']['available_memory_bytes'] > 0
    assert result['capabilities']['selected_baseline_bytes'] == 65536
    assert result['plan']['estimates']['selected_baseline_bytes'] == 65536
    assert not transport.subscribed and not transport.emission and not transport.armed
    assert all(state['on'] == 'OFF' for unit in transport.units.values() for state in unit['channels'].values())
    assert transport.pulse == [2500000., 100., 600.]
    assert result['restoration']['safe_verified']
    assert result['native_movies'][0].metadata['axis_basis'] == 'observed_markers_nominal_axis'
    assert not result['native_movies'][0].scans[0].trajectory.calibration_id
    if mode == 'dual':
        assert result['plan']['settings']['reference_rate_hz'] == 4000.
        assert result['native_movies'][0].scans[0].reference is not None
    # The all-OFF terminator is a physical frame, never a MIRcat repetition.
    for raw in result['raw_movies']:
        assert raw['readbacks']['physical_frame_count'] == raw['readbacks']['expected_scan_count']+1
        assert not any(ch['enabled'] for ch in raw['uploaded_frames'][-1]['channels'].values())


@pytest.mark.parametrize('fault', ['overload', 'abort'])
def test_rrs_installed_transport_failure_or_stop_preserves_raw_and_releases_after_cleanup(tmp_path, monkeypatch, fault):
    worker = Worker()
    ctx, transport, coordinator = installed_context(tmp_path, monkeypatch, 'dual', worker, fault)
    plan = installed_plan('dual')
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True, cancel=lambda reason: worker.cancel_event.set())
    runner = RepeatedRapidScanRunner(ctx)
    with ctx.hardware_scope(operation), pytest.raises(InterruptedError if fault == 'abort' else RuntimeError):
        runner.run(StartSnapshot(operation, 'measurement', plan, None), worker)
    assert runner.last_result['status'] == ('cancelled' if fault == 'abort' else 'failed')
    assert runner.last_result['restoration']['safe_verified']
    assert runner.last_result['raw_movies'][-1]['chunks'][0]['data']
    assert not transport.subscribed and not transport.emission and not transport.armed
    assert coordinator.snapshot()['state'] == 'free'
    retained = load_run(runner.last_result['output_path']).record
    assert retained['raw_movies'][-1]['chunks'][0]['data']
    assert transport.train_starts == 2  # automatic baseline then one pump; no retry


def test_rrs_installed_capability_check_is_read_only_and_unknown_health_is_retained(tmp_path, monkeypatch):
    worker = Worker()
    ctx, transport, coordinator = installed_context(tmp_path, monkeypatch, 'dual', worker, 'unknown_health')
    plan = installed_plan('dual')
    before = dict(transport.nodes)
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True)
    with ctx.hardware_scope(operation):
        result = RepeatedRapidScanRunner(ctx).run(StartSnapshot(operation, 'capabilities', plan, None), worker)
    assert result['status'] == 'complete'
    assert result['readbacks']['health_before']['clock_locked'] is None
    assert result['readbacks']['health_before']['read_errors']
    assert transport.nodes == before
    assert not any(call.startswith('hf set ') for call in transport.calls)
    assert not any(call.startswith('MIRcatSDK_Set') or call in ('MIRcatSDK_TurnEmissionOn','MIRcatSDK_ArmLaser','MIRcatSDK_StartSweepScan') for call in transport.calls)
    assert transport.train_starts == 0 and not transport.emission
    assert coordinator.snapshot()['state'] == 'free'

@pytest.mark.parametrize('fault', ['unlocked', 'unknown_health'])
def test_rrs_actual_lock_failure_stops_before_emission_unknown_health_stays_informational(tmp_path, monkeypatch, fault):
    worker = Worker()
    ctx, transport, coordinator = installed_context(tmp_path, monkeypatch, 'single', worker, fault)
    plan = installed_plan('single')
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True)
    runner = RepeatedRapidScanRunner(ctx)
    with ctx.hardware_scope(operation):
        if fault == 'unlocked':
            with pytest.raises(TimeoutError, match='reference-lock'):
                runner.run(StartSnapshot(operation, 'measurement', plan, None), worker)
            assert transport.train_starts == 0
            assert 'MIRcatSDK_TurnEmissionOn' not in transport.calls
        else:
            result = runner.run(StartSnapshot(operation, 'measurement', plan, None), worker)
            assert result['status'] == 'complete'
            assert result['readbacks']['health_configured']['clock_locked'] is None
            assert result['readbacks']['health_configured']['read_errors']
    assert coordinator.snapshot()['state'] == 'free'
    assert not transport.emission and not transport.subscribed


def test_rrs_actual_native_rates_revalidate_memory_before_any_capture(tmp_path, monkeypatch):
    worker = Worker()
    ctx, transport, coordinator = installed_context(tmp_path, monkeypatch, 'dual', worker)
    # The initial two detector + idle carrier profile fits. The configured
    # native carrier adds full-movie retention and exceeds this explicit bound.
    value = settings('dual')
    value = replace(value, manual_overrides={'measured_scan_period_s': .1, 'controls': (), 'memory_limit_bytes': 30_000_000})
    plan = build_plan(value)
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True)
    runner = RepeatedRapidScanRunner(ctx)
    with ctx.hardware_scope(operation), pytest.raises(ValueError, match='memory budget'):
        runner.run(StartSnapshot(operation, 'measurement', plan, None), worker)
    assert transport.train_starts == 0
    assert 'MIRcatSDK_TurnEmissionOn' not in transport.calls
    assert coordinator.snapshot()['state'] == 'free'
    assert runner.last_result['restoration']['safe_verified']


def test_rrs_automatic_baseline_reused_but_filter_change_reacquires_without_confirmation(tmp_path):
    ctx, plan = context(tmp_path), build_plan(settings())
    runner = RepeatedRapidScanRunner(ctx)
    first = runner.run(snapshot(ctx, plan, 'measurement'), Worker())
    baseline_record = first['auto_preliminary']
    # Reviewer/temperature/condition provenance does not invalidate native reuse.
    baseline_record['baseline'] = replace(baseline_record['baseline'], accepted=False)
    changed = replace(plan.settings, condition=replace(plan.settings.condition, temperature_K=87., condition_id='renamed'))
    second = runner.run(snapshot(ctx, build_plan(changed), 'measurement', baseline_record), Worker())
    assert 'auto_preliminary' not in second
    changed = replace(changed, sample_filter_timeconstant_s=.002)
    third = runner.run(snapshot(ctx, build_plan(changed), 'measurement', baseline_record), Worker())
    assert third['auto_preliminary']['baseline'].complete
    assert third['unused_baselines'][0]['differences']
    assert third['status'] == 'complete'

@pytest.mark.parametrize('mode', ['single', 'dual'])
def test_rrs_partial_optional_background_limits_absolute_only(tmp_path, mode):
    ctx, plan = context(tmp_path, mode), build_plan(settings(mode))
    runner = RepeatedRapidScanRunner(ctx)
    first = runner.run(snapshot(ctx, plan, 'measurement'), Worker())
    baseline_record = first['auto_preliminary']
    supports = []
    for support in baseline_record['baseline'].spectra:
        selected = np.asarray(support.wavenumbers_cm1) < 1920.
        supports.append(replace(support, wavenumbers_cm1=np.asarray(support.wavenumbers_cm1)[selected],
            values=np.asarray(support.values)[selected], variance=np.asarray(support.variance)[selected],
            valid=None if support.valid is None else np.asarray(support.valid)[selected]))
    background = replace(baseline_record['baseline'], kind='background', spectra=tuple(supports))
    result = runner.run(snapshot(ctx, plan, 'measurement', baseline_record), Worker(), background=background)
    assert result['status'] == 'complete'
    points = result['processed'][0].points[0]
    assert np.any(points.flags['missing_background_support'] & points.valid)
    assert np.any(np.isfinite(points.delta_absorbance))
    assert np.any(np.isfinite(points.absolute_absorbance))
    assert np.any(np.isnan(points.absolute_absorbance) & points.valid)
    wrong = replace(background, compatibility={**background.compatibility, 'acquisition':
                    {**background.compatibility['acquisition'], 'sample_rate_hz': 999.}})
    raw = runner.run(snapshot(ctx, plan, 'measurement', baseline_record), Worker(), background=wrong)
    assert raw['status'] == 'complete' and raw['unused_normalizations']
    assert np.any(np.isfinite(raw['processed'][0].points[0].delta_absorbance))
    assert np.all(np.isnan(raw['processed'][0].points[0].absolute_absorbance))


def test_rrs_installed_failed_disarm_retains_fault_ownership_and_native_record(tmp_path, monkeypatch):
    worker = Worker()
    ctx, transport, coordinator = installed_context(tmp_path, monkeypatch, 'single', worker, 'disarm')
    plan = installed_plan('single')
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True)
    runner = RepeatedRapidScanRunner(ctx)
    with ctx.hardware_scope(operation), pytest.raises(RuntimeError, match='disarmed readback'):
        runner.run(StartSnapshot(operation, 'measurement', plan, None), worker)
    assert runner.last_result['status'] == 'cleanup_failed'
    assert transport.armed and not transport.emission
    assert runner.last_result['restoration']['mircat_safe_readbacks']['armed'] is True
    assert not runner.last_result['restoration']['safe_verified']
    assert coordinator.snapshot()['state'] == 'fault'
    assert load_run(runner.last_result['output_path']).record['native_movies']
    recovery = coordinator.acquire('test-explicit-recovery', recovery=True)
    coordinator.release(recovery, safe_verified=True, preservation_verified=True)


@pytest.mark.parametrize('mode', ['single', 'dual'])
def test_rrs_installed_qcl1_ignores_legacy_selector_and_accepts_exact_internal_duty_boundary(tmp_path, monkeypatch, mode):
    worker = Worker()
    ctx, transport, coordinator = installed_context(tmp_path, monkeypatch, mode, worker,
        configuration_changes={'repeated_rapid_scan': {'qcl': 2, 'mircat_pulse': {'qcl': 2}}})
    initial = installed_plan(mode).settings
    value = replace(initial, manual_overrides={**initial.manual_overrides, 'mircat_pulse_rate_hz': 2500000., 'mircat_pulse_width_ns': 120., 'probe_pulse_width_s': 700e-9})
    plan = build_plan(value)
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True)
    with ctx.hardware_scope(operation):
        result = RepeatedRapidScanRunner(ctx).run(StartSnapshot(operation, 'measurement', plan, None), worker)
    assert result['status'] == 'complete'
    assert result['readbacks']['historical_qcl_selectors']['device_configuration'] == 2
    assert result['readbacks']['historical_qcl_selectors']['pulse_configuration'] == 2
    assert result['readbacks']['installed_qcl'] == 1
    assert transport.qcl_calls and all(index == 1 for _, index in transport.qcl_calls)
    assert {'TuneToWW','StartSweepScan','GetWlTrigChanParams','SetQCLParams'} <= {call for call,_ in transport.qcl_calls}
    assert transport.pulse_writes[0] == (2500000., 120., 600.)
    assert transport.pulse_writes[-1] == (2500000., 100., 600.)
    assert result['readbacks']['actual_mircat_internal_pulse_validation']['internal_duty_fraction'] == .30
    assert result['readbacks']['actual_mircat_internal_pulse_validation']['emitted_optical_duty_fraction'] == .12
    assert result['raw_movies'][0]['readbacks']['pre_emission_optical_pulse_validation']['emitted_optical_duty_fraction'] == .12
    assert result['raw_movies'][0]['readbacks']['pre_emission_clock']['channels']['B']['width_edge']['response'] == '7e-07s'
    assert result['readbacks']['capabilities']['live_settings']['mircat_pulse_width_ns'] == 120.
    assert result['restoration']['safe_verified'] and coordinator.snapshot()['state'] == 'free'


@pytest.mark.parametrize('width, vendor_limit', [(120.001, 50.), (100., 20.)])
def test_rrs_installed_effective_config_pulse_pair_respects_global_and_lower_vendor_duty(tmp_path, monkeypatch, width, vendor_limit):
    worker = Worker()
    ctx, transport, coordinator = installed_context(tmp_path, monkeypatch, 'single', worker,
        configuration_changes={'repeated_rapid_scan': {'qcl': 2, 'mircat_pulse': {'qcl': 2, 'pulse_rate_hz': 2500000., 'pulse_width_ns': width}}})
    transport.vendor_duty_percent = vendor_limit
    transport.pulse[1] = 60. if vendor_limit == 20. else 100.
    plan = installed_plan('single')
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True)
    with ctx.hardware_scope(operation):
        acquirer = InstalledDevicesAcquirer(ctx, operation, plan)
        try:
            with pytest.raises(ValueError, match='duty'):
                acquirer.prepare(worker)
            assert not transport.pulse_writes
            assert 'MIRcatSDK_TurnEmissionOn' not in transport.calls
        finally:
            restored = acquirer.restore(worker)
            ctx.ownership.release(operation.ownership, safe_verified=restored['safe_verified'], preservation_verified=True)
    assert restored['safe_verified']
    assert all(index == 1 for _, index in transport.qcl_calls)
    assert coordinator.snapshot()['state'] == 'free'


def test_rrs_installed_actual_pulse_readback_over_limit_stops_before_arm_or_emission(tmp_path, monkeypatch):
    worker = Worker()
    ctx, transport, coordinator = installed_context(tmp_path, monkeypatch, 'single', worker, 'rounded_pulse_above_limit')
    initial = installed_plan('single').settings
    value = replace(initial, manual_overrides={**initial.manual_overrides, 'mircat_pulse_rate_hz': 2500000., 'mircat_pulse_width_ns': 120.})
    plan = build_plan(value)
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True)
    runner = RepeatedRapidScanRunner(ctx)
    with ctx.hardware_scope(operation), pytest.raises(ValueError, match='duty'):
        runner.run(StartSnapshot(operation, 'measurement', plan, None), worker)
    assert runner.last_result['readbacks']['mircat_pulse']['pulse_width_ns'] == 121.
    assert transport.pulse_writes == [(2500000., 120., 600.), (2500000., 100., 600.)]
    assert not any(call in transport.calls for call in ('MIRcatSDK_ArmLaser', 'MIRcatSDK_TurnEmissionOn', 'MIRcatSDK_StartSweepScan'))
    assert runner.last_result['restoration']['safe_verified']
    assert coordinator.snapshot()['state'] == 'free'


def test_rrs_actual_emitted_cadence_and_sdk_width_rechecked_before_emission(tmp_path, monkeypatch):
    worker = Worker()
    ctx, transport, coordinator = installed_context(tmp_path, monkeypatch, 'single', worker, 'changed_external_rate')
    plan = installed_plan('single')
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True)
    runner = RepeatedRapidScanRunner(ctx)
    with ctx.hardware_scope(operation), pytest.raises(ValueError, match='30%'):
        runner.run(StartSnapshot(operation, 'measurement', plan, None), worker)
    assert runner.last_result['raw_movies'][0]['readbacks']['pre_emission_mircat_pulse']['pulse_width_ns'] == 100.
    clock = runner.last_result['raw_movies'][0]['readbacks']['pre_emission_clock']
    assert clock['queries']['synth_frequency']['response'] == '4000000'
    assert 'MIRcatSDK_TurnEmissionOn' not in transport.calls
    assert transport.train_starts == 0
    assert runner.last_result['restoration']['safe_verified']
    assert coordinator.snapshot()['state'] == 'free'


def test_rrs_valid_optical_duty_keeps_separate_internal_external_rate_constraint(tmp_path, monkeypatch):
    worker = Worker()
    ctx, transport, coordinator = installed_context(tmp_path, monkeypatch, 'single', worker,
        configuration_changes={'repeated_rapid_scan': {'mircat_pulse': {'pulse_rate_hz': 1000000., 'pulse_width_ns': 100.}}})
    plan = installed_plan('single')
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True)
    with ctx.hardware_scope(operation):
        acquirer = InstalledDevicesAcquirer(ctx, operation, plan)
        try:
            with pytest.raises(ValueError, match='internal repetition rate.*separate external'):
                acquirer.prepare(worker)
            assert not transport.pulse_writes
        finally:
            restored = acquirer.restore(worker)
            ctx.ownership.release(operation.ownership, safe_verified=restored['safe_verified'], preservation_verified=True)
    assert restored['safe_verified'] and coordinator.snapshot()['state'] == 'free'


@pytest.mark.parametrize('field', ['max_pulse_rate_hz', 'max_pulse_width_ns', 'max_duty_cycle'])
@pytest.mark.parametrize('invalid', [float('nan'), float('inf'), 0., -1.], ids=['nan', 'infinity', 'zero', 'negative'])
def test_rrs_nonfinite_or_nonpositive_sdk_limits_reject_before_pulse_write(tmp_path, monkeypatch, field, invalid):
    worker = Worker()
    ctx, transport, coordinator = installed_context(tmp_path, monkeypatch, 'single', worker)
    limits = [3e6, 500., 50.]
    limits[('max_pulse_rate_hz','max_pulse_width_ns','max_duty_cycle').index(field)] = invalid
    transport.vendor_first_limits = limits  # A subsequent fresh cleanup read is valid.
    plan = installed_plan('single')
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True)
    runner = RepeatedRapidScanRunner(ctx)
    with ctx.hardware_scope(operation), pytest.raises(ValueError, match='connected pulse limits must be finite positive'):
        runner.run(StartSnapshot(operation, 'measurement', plan, None), worker)
    observed = runner.last_result['readbacks']['mircat_pulse_limits'][field]
    assert np.isnan(observed) if np.isnan(invalid) else observed == invalid
    assert transport.pulse_writes == [(2500000., 100., 600.)]  # Valid original restore only.
    assert not any(name in transport.calls for name in ('MIRcatSDK_ArmLaser','MIRcatSDK_TurnEmissionOn','MIRcatSDK_StartSweepScan'))
    assert runner.last_result['restoration']['safe_verified'] and coordinator.snapshot()['state'] == 'free'
    retained = load_run(runner.last_result['output_path']).record['readbacks']['mircat_pulse_limits'][field]
    assert np.isnan(retained) if np.isnan(invalid) else retained == invalid


def test_rrs_missing_sdk_limits_raise_without_fallback(tmp_path, monkeypatch):
    worker = Worker()
    ctx, transport, coordinator = installed_context(tmp_path, monkeypatch, 'single', worker)
    transport.vendor_first_limits = RuntimeError('SDK pulse maximum data unavailable')
    plan = installed_plan('single')
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True)
    runner = RepeatedRapidScanRunner(ctx)
    with ctx.hardware_scope(operation), pytest.raises(RuntimeError, match='maximum data unavailable'):
        runner.run(StartSnapshot(operation, 'measurement', plan, None), worker)
    assert 'MIRcatSDK_TurnEmissionOn' not in transport.calls
    assert transport.pulse_writes == [(2500000., 100., 600.)]
    assert runner.last_result['restoration']['safe_verified'] and coordinator.snapshot()['state'] == 'free'


@pytest.mark.parametrize('fault', ['changed_rate', 'changed_width', 'changed_current'])
def test_rrs_unexpected_valid_sdk_pulse_change_after_tune_is_retained_and_rejected(tmp_path, monkeypatch, fault):
    worker = Worker()
    ctx, transport, coordinator = installed_context(tmp_path, monkeypatch, 'single', worker, fault)
    plan = installed_plan('single')
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True)
    runner = RepeatedRapidScanRunner(ctx)
    with ctx.hardware_scope(operation), pytest.raises(RuntimeError, match='pulse readback changed'):
        runner.run(StartSnapshot(operation, 'measurement', plan, None), worker)
    captured = runner.last_result['raw_movies'][0]['readbacks']
    changed_key = {'changed_rate':'pulse_rate_hz','changed_width':'pulse_width_ns','changed_current':'current_ma'}[fault]
    assert captured['pre_emission_mircat_pulse'][changed_key] != runner.last_result['readbacks']['mircat_pulse'][changed_key]
    assert captured['pre_emission_mircat_limits']['max_duty_cycle'] == 50.
    assert captured['pre_emission_mircat_current_limits'] == (1., 1000.)
    assert 'MIRcatSDK_TurnEmissionOn' not in transport.calls and transport.train_starts == 0
    assert runner.last_result['restoration']['safe_verified'] and coordinator.snapshot()['state'] == 'free'


def test_rrs_after_recipe_duty_uses_actual_dds_readback_within_timing_tolerance(tmp_path, monkeypatch):
    worker = Worker()
    ctx, transport, coordinator = installed_context(tmp_path, monkeypatch, 'single', worker)
    transport.frequency_readback_offset_hz = .00001
    plan = installed_plan('single')
    operation = ctx.begin_operation(plan.settings.to_dict(), hardware=True)
    with ctx.hardware_scope(operation):
        acquirer = InstalledDevicesAcquirer(ctx, operation, plan)
        try:
            acquirer.prepare(worker)
            actual = float(acquirer.readbacks['clock_settings']['queries']['synth_frequency']['response'])
            assert actual != plan.settings.probe_frequency_hz
            assert acquirer.readbacks['requested_mircat_internal_pulse_validation']['emitted_repetition_rate_hz'] == actual
            assert acquirer.readbacks['actual_mircat_internal_pulse_validation']['emitted_repetition_rate_hz'] == actual
            assert acquirer.readbacks['actual_mircat_internal_pulse_validation']['emitted_optical_duty_fraction'] > .1
        finally:
            restored = acquirer.restore(worker)
            ctx.ownership.release(operation.ownership, safe_verified=restored['safe_verified'], preservation_verified=True)
    assert restored['safe_verified'] and coordinator.snapshot()['state'] == 'free'
