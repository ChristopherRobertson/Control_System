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
    def confirm_physical_action(self, description, cleanup=False):
        self.actions.append((description, cleanup))


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
    assert len(result["qualification_movies"]) == len(plan.movies)
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


def test_rrs_stationarity_failure_never_arms_pump(tmp_path):
    ctx, plan = context(tmp_path), build_plan(settings())
    sample = preliminary(ctx, plan)
    created = []
    def factory(*args):
        value = SimulationAcquirer(*args, faults={"stationarity": True}); created.append(value); return value
    runner = RepeatedRapidScanRunner(ctx, factory)
    with pytest.raises(ValueError, match="stationarity rejected"):
        runner.run(snapshot(ctx, plan, "measurement", sample), Worker())
    assert created[0].pump_count == 0
    assert len(runner.last_result["qualification_movies"]) == 1
    assert load_run(runner.last_result["output_path"]).record["status"] == "failed"


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
    class QCL:
        def stop_scan_if_needed(self): pass
        def turn_emission_off(self): pass
        def tune_to_wavenumber(self, *args, **kwargs): pass
        def is_tuned(self): return True
        def set_external_sweep_trigger_params(self, **kwargs): pass
        def set_wavelength_trigger_pulse_width_us(self, value): pass
        def turn_emission_on(self, **kwargs): pass
        def cancel_manual_tune(self): pass
        def start_sweep_scan(self, **kwargs): self.sweep = kwargs
        def get_sweep_parameters(self): return self.sweep
        def get_wavelength_trigger_channel_params(self, qcl): return {"units": 2, "start": 1898., "stop": 1951., "interval": 53/6, "num_triggers": 7}
        def get_scan_waiting_process_trigger(self): return True
        def is_interlock_set(self): return True
        def get_system_error_word(self): return 0
        def get_scan_status(self): return {"scan_in_progress": False}
    acquirer = InstalledDevicesAcquirer(ctx, snapshot(ctx, plan, "measurement").operation, plan)
    hf, clock, timing = HF(), Timing(), Timing()
    acquirer.devices = {"hf2li": hf, "t660_1": clock, "t660_2": timing, "mircat": QCL()}
    acquirer.config = {"marker_interval_cm1": 53/6, "marker_width_us": 1, "approved_laser_safety_condition": True}
    acquirer.readbacks = {**readbacks, "required_demodulators": (0, 2)}
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
    chunks, _ = native_fixture(count=plan.settings.pre_scans)
    for values in chunks[0]["data"].values():
        values["dio"] &= np.uint32(~(1 << 17) & 0xffffffff)
    hf.reads = 0
    qualification = acquirer.capture(plan.movies[0], Worker(), qualification=True)
    assert len(qualification.scans) == plan.settings.pre_scans
    assert len(timing.frames) == plan.settings.pre_scans+1
    assert not any(values["enabled"] for values in timing.frames[-1]["channels"].values())
    assert acquirer.devices["mircat"].sweep["repetitions"] == plan.settings.pre_scans
    assert not qualification.pump_observations


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
