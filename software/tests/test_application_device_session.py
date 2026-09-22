"""Application connection/cache contracts with fake transports only."""
from copy import deepcopy
from types import SimpleNamespace
import time

import pytest

from control_app.measurement_host.application_session import ApplicationDeviceSession, CachedDevice, shared_device
from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError, require_hardware_owner


def test_missing_cached_settings_reports_underlying_connection_failure():
    session = ApplicationDeviceSession(HardwareCoordinator(), {}, factories={})
    session.errors["t660_2"] = "Windows denied access to COM7"
    with pytest.raises(RuntimeError, match="Windows denied access to COM7"):
        CachedDevice(session, "t660_2").read_active_settings()


class Device:
    def __init__(self, name):
        self.name, self.calls, self.value = name, [], 4
        self.device_id = "dev18500"

    def touch(self, method):
        require_hardware_owner(self)
        self.calls.append(method)

    def connect(self): self.touch("connect")
    def initialize(self): self.touch("initialize")
    def open_unit(self): self.touch("open_unit")
    def close(self): self.touch("close")
    def deinitialize(self): self.touch("deinitialize")
    def close_unit(self): self.touch("close_unit")
    def stop(self): self.touch("stop")
    def stop_acquisition(self): self.touch("stop_acquisition")
    def get_clockbase(self): self.touch("get_clockbase"); return 210000000
    def get_value(self): self.touch("get_value"); return self.value
    def set_value(self, value): self.touch("set_value"); self.value = value

    def discover_dual_phase_scan_capabilities(self):
        self.touch("discover")
        from control_app.measurement_modules.phase_scan.regular_phase_scan import HF2Capabilities
        from control_app.measurement_modules.phase_scan.dual_detector_phase_scan import DualHF2Capabilities
        profile = HF2Capabilities(orders=(4,), timeconstants_by_order={4: (8e-6, 50e-6)},
            rates_sps=(230263.15789473685,), enabled_streams=(0, 2, 3), verified=True)
        return DualHF2Capabilities(sample=profile, reference=profile, verified=True, source="fake readbacks").to_dict()

    def export_settings_snapshot(self, **kwargs):
        self.touch("snapshot")
        nodes = {}
        for i in range(6):
            for key, value in dict(order=self.value, timeconstant=8e-6, rate=230263.15789473685).items():
                nodes[f"/dev18500/demods/{i}/{key}"] = {"type": "double", "value": value}
        for i in (0, 1):
            for key, value in dict(ac=1, imp50=0, diff=0, range=1).items():
                nodes[f"/dev18500/sigins/{i}/{key}"] = {"type": "double", "value": value}
        for key, value in dict(order=4, adcthreshold=0).items():
            nodes[f"/dev18500/plls/0/{key}"] = {"type": "int", "value": value}
        return {"nodes": nodes, "read_errors": {}}

    def get_num_installed_qcls(self): self.touch("qcl_count"); return 1
    def get_qcl_tuning_range(self, qcl):
        self.touch("range"); return {"qcl": qcl, "min_cm1": 1638., "max_cm1": 2078.}
    def get_qcl_pulse_limits(self, qcl):
        self.touch("limits"); return {"min_pulse_rate_hz": 1., "max_pulse_rate_hz": 500000.,
            "min_pulse_width_ns": 10., "max_pulse_width_ns": 500., "max_duty_cycle": .1}
    def get_qcl_pulse_rate(self, qcl): self.touch("pulse_rate"); return 100000.
    def get_qcl_pulse_width(self, qcl): self.touch("pulse_width"); return 150.
    def get_qcl_current(self, qcl): self.touch("current"); return 500.
    def get_wavelength_trigger_params(self): self.touch("trigger"); return {}
    def get_sweep_parameters(self): self.touch("sweep"); return {}
    def get_wavelength_trigger_pulse_width_us(self): self.touch("marker"); return 1
    def get_qcl_operating_mode(self, qcl): self.touch("mode"); return 0
    def get_qcl_set_temperature(self, qcl): self.touch("temperature"); return 20.
    def is_cw_allowed(self, qcl): self.touch("cw"); return True
    def get_qcl_cw_current_limits(self, qcl): self.touch("cw_limits"); return (0., 1000.)
    def get_qcl_current_limits(self, qcl): self.touch("current_limits"); return (0., 1000.)
    def is_emission_on(self): self.touch("emission"); return False
    def is_laser_armed(self): self.touch("armed"); return False
    def is_interlock_set(self): self.touch("interlock"); return True
    def is_key_switch_set(self): self.touch("key"); return True
    def are_tecs_ready(self): self.touch("tecs"); return True
    def verified_frame_capacity(self): self.touch("capacity"); return 8192
    def command(self, value):
        self.touch(value)
        edge = int(value.removeprefix("TIME:RELTo").removesuffix("?"))
        return str(edge-1 if edge % 2 == 0 else 0)
    def read_active_settings(self):
        self.touch("settings")
        def row(value): return {"ok": True, "response": str(value)}
        return {"queries": {key: row(value) for key, value in dict(synth_frequency=100000., predivider=1,
            clock_connector_mode="OUT" if self.name == "t660_2" else "IN", clock_lock_status="LOCKED").items()},
            "channels": {c: {key: row(value) for key, value in dict(delay_edge="0s", width_edge="150ns",
                timing_mode="DW", polarity="POS", termination="ON").items()} for c in "ABCD"}}
    def identity_snapshot(self): self.touch("identity"); return {"aperture_readback_mm": 12.}
    def read_state(self): self.touch("state"); return {"connected": True, "emission_on": False}
    def get_red_laser_pointer_status(self): self.touch("pointer"); return {"installed": True, "enabled": False}


@pytest.fixture
def session(tmp_path):
    owner = HardwareCoordinator(tmp_path/"owner.lock")
    devices = {name: Device(name) for name in ("mircat", "hf2li", "picoscope", "t660_1", "t660_2", "opo_iris")}
    factories = {name: lambda configuration, d=device: d for name, device in devices.items()}
    session = ApplicationDeviceSession(owner, {}, factories=factories)
    yield session
    owner._unlock_os()


def finish(session):
    owner = session.coordinator
    token = owner.acquire("manual:recovery", recovery=owner.snapshot()["state"] != "free")
    with owner.scope(token): session.close()
    owner.release(token, safe_verified=True)


def test_startup_once_and_transport_reuse_until_application_close(session):
    assert session.start()["errors"] == {}
    owner = session.coordinator
    for stage in ("blank", "preliminary", "pumped", "other_tab"):
        token = owner.acquire(stage)
        with owner.scope(token):
            for name in session.devices:
                device = session.device(name)
                getattr(device, "initialize" if name == "mircat" else "open_unit" if name == "picoscope" else "connect")()
                getattr(device, "deinitialize" if name == "mircat" else "close_unit" if name == "picoscope" else "close")()
        owner.release(token, safe_verified=True)
    for raw in session.devices.values():
        assert sum(raw.calls.count(m) for m in ("connect", "initialize", "open_unit")) == 1
        assert not any(m in raw.calls for m in ("close", "deinitialize", "close_unit"))
    assert session.devices["hf2li"].calls.count("discover") == 1
    finish(session)
    assert session.closed and not session.connected
    for raw in session.devices.values():
        assert sum(raw.calls.count(m) for m in ("close", "deinitialize", "close_unit")) == 1


def test_cached_tab_views_never_touch_transport_or_expose_mutable_cache(session):
    session.start()
    before = {name: list(raw.calls) for name, raw in session.devices.items()}
    for _ in range(5):
        for dual in (False, True):
            assert session.phase_capabilities(dual).verified
        session.slow_scan_readbacks("single")
        session.slow_scan_readbacks("dual")
        session.fixed_profile("single", {"positions": []})
        session.nanosecond_capabilities()
        session.rapid_scan_capabilities("single")
    view = CachedDevice(session, "hf2li")
    snapshot = view.export_settings_snapshot()
    snapshot["nodes"].clear()
    assert view.export_settings_snapshot()["nodes"]
    with pytest.raises(RuntimeError, match="unavailable"):
        view.set_value(99)
    assert before == {name: raw.calls for name, raw in session.devices.items()}


def test_idle_app_keeps_process_lock_and_old_worker_cannot_use_new_owner(session):
    session.start()
    owner = session.coordinator
    competing = HardwareCoordinator(owner.lock_path)
    with pytest.raises(OwnershipError): competing.acquire("other-process")
    token = owner.acquire("first")
    with owner.scope(token): device = session.device("hf2li")
    owner.release(token, safe_verified=True)
    token = owner.acquire("second")
    with pytest.raises(OwnershipError): device.get_value()
    with owner.scope(token): assert session.device("hf2li").get_value() == 4
    owner.release(token, safe_verified=True)
    finish(session)
    token = competing.acquire("after-close")
    competing.release(token, safe_verified=True)


def test_changes_refresh_live_settings_without_reconnecting(session):
    session.start()
    token = session.coordinator.acquire("manual:settings")
    with session.coordinator.scope(token):
        device = shared_device("hf2li", lambda: pytest.fail("duplicate connection"))
        device.set_value(8)
        assert device.get_value() == 8  # Acquisition/control reads always live.
    session.coordinator.release(token, safe_verified=True)
    snapshot = CachedDevice(session, "hf2li").export_settings_snapshot()
    assert snapshot["nodes"]["/dev18500/demods/0/order"]["value"] == 8
    assert session.devices["hf2li"].calls.count("connect") == 1


def test_blocking_sdk_call_does_not_hold_up_status_or_stop(session):
    from threading import Event, Thread
    session.start()
    entered, release, observed = Event(), Event(), Event()
    def scan():
        entered.set()
        assert release.wait(3)
    session.devices["mircat"].start_sweep_scan = scan
    owner = session.coordinator
    token = owner.acquire("scan")
    with owner.scope(token):
        lease = session.device("mircat")
    scan_worker = Thread(target=lease.start_sweep_scan)
    status_worker = Thread(target=lambda: (lease.get_value(), observed.set()))
    try:
        scan_worker.start()
        assert entered.wait(1)
        status_worker.start()
        assert observed.wait(1), "A blocked SDK call prevented status/stop access"
    finally:
        release.set()
        scan_worker.join(3)
        status_worker.join(3)
        owner.release(token, safe_verified=True)


def test_capability_record_speeds_later_launch_but_operating_settings_are_live(session, tmp_path):
    session.capability_cache_path = tmp_path/"capabilities.json"
    session.start()
    finish(session)
    owner = HardwareCoordinator(tmp_path/"second.lock")
    raw = Device("hf2li")
    raw.value = 8
    second = ApplicationDeviceSession(owner, {}, factories={"hf2li": lambda configuration: raw},
        capability_cache_path=session.capability_cache_path)
    try:
        second.start()
        assert "discover" not in raw.calls
        assert "snapshot" in raw.calls
        assert CachedDevice(second, "hf2li").export_settings_snapshot()["nodes"]["/dev18500/demods/0/order"]["value"] == 8
        finish(second)
    finally:
        owner._unlock_os()


def test_partial_startup_reports_failure_without_repeating_it_on_tab_use(session):
    def fail(): raise RuntimeError("unplugged")
    # Factories are not evaluated until startup.
    session.factories["mircat"] = lambda configuration: SimpleNamespace(initialize=fail, deinitialize=lambda: None)
    result = session.start()
    assert "unplugged" in result["errors"]["mircat"]
    with pytest.raises(RuntimeError, match="MIRcat"):
        session.phase_capabilities()
    assert session.devices["hf2li"].calls.count("discover") == 1


@pytest.mark.parametrize("persistent", [False, True])
def test_timer_access_denied_retries_once_after_other_discovery(session, persistent):
    timer = Device("t660_2")
    attempts = []
    def connect():
        timer.touch("connect")
        attempts.append(True)
        if len(attempts) == 1 or persistent:
            raise PermissionError("Windows denied access to COM7")
        assert "discover" in session.devices["hf2li"].calls
        assert "settings" in session.devices["t660_1"].calls
    timer.connect = connect
    session.factories["t660_2"] = lambda configuration: timer
    result = session.start()
    assert len(attempts) == 2
    assert ("t660_2" in result["errors"]) is persistent
    assert ("t660_2" in result["connected"]) is not persistent
    finish(session)


def test_com7_opens_first_attempt_when_sdk_discovery_temporarily_owns_converter(session, monkeypatch):
    from threading import Event
    discovering = Event()
    timer = Device("t660_2")
    original_start = session._start_device
    original_connect = timer.connect
    attempts = []
    def discover(name, token, recheck):
        if name != "mircat":
            return original_start(name, token, recheck)
        discovering.set()
        try:
            time.sleep(.05)
            return original_start(name, token, recheck)
        finally:
            discovering.clear()
    def connect():
        attempts.append(True)
        if discovering.is_set():
            raise PermissionError("Windows denied access to COM7")
        original_connect()
    timer.connect = connect
    session.factories["t660_2"] = lambda configuration: timer
    monkeypatch.setattr(session, "_start_device", discover)
    messages = []
    result = session.start(messages.append)
    assert result["errors"] == {}
    assert len(attempts) == 1
    assert not any("Retrying" in message or "unavailable" in message for message in messages)
    finish(session)


def test_shutdown_disconnects_even_after_verified_idle_operation(session, monkeypatch, tmp_path):
    from control_app.workflows.state_machine import WorkflowStateMachine
    from control_app.ui.contracts import WorkflowResult
    session.start()
    machine = WorkflowStateMachine(operator="test", coordinator=session.coordinator, run_dir=tmp_path/"run")
    machine.application_session = session
    monkeypatch.setattr(machine, "_handle_workflow_command", lambda *args: WorkflowResult("complete", "fake safe idle", {}))
    token = session.coordinator.acquire("phase_scan:single")
    session.coordinator.release(token, safe_verified=True)
    assert machine.ui_safe_shutdown().status == "complete"
    assert session.closed and session.coordinator._file is None


def test_instrument_reset_keeps_application_session_available(session, monkeypatch, tmp_path):
    from control_app.workflows.state_machine import WorkflowStateMachine
    from control_app.ui.contracts import WorkflowResult
    session.start()
    machine = WorkflowStateMachine(operator="test", coordinator=session.coordinator, run_dir=tmp_path/"run")
    machine.application_session = session
    monkeypatch.setattr(machine, "_handle_workflow_command", lambda *args: WorkflowResult("complete", "fake reset", {}))
    token = session.coordinator.acquire("manual:recovery", recovery=True)
    with session.coordinator.scope(token):
        assert machine._ui_shutdown_actions(reason="instrument_reset", emergency=True).status == "complete"
    session.coordinator.release(token, safe_verified=True)
    assert not session.closed and session.connected


def test_interrupted_app_record_requires_recovery_even_between_experiments(session):
    session.start()
    session.coordinator._unlock_os()  # Simulate OS releasing the process lock on death.
    restarted = HardwareCoordinator(session.coordinator.lock_path)
    assert restarted.snapshot()["state"] == "owned"
    with pytest.raises(OwnershipError, match="recovery"):
        restarted.acquire("new-app")


def test_invalid_capability_record_falls_back_to_device_discovery(session, tmp_path):
    session.capability_cache_path = tmp_path/"caps.json"
    session.capability_cache_path.write_text('{"schema_version": 99}')
    assert session.start()["errors"] == {}
    assert session.devices["hf2li"].calls.count("discover") == 1


def test_explicit_recheck_refreshes_choices_without_reconnecting_healthy_devices(session):
    session.start()
    session.start(recheck_capabilities=True)
    assert session.devices["hf2li"].calls.count("discover") == 2
    assert session.devices["hf2li"].calls.count("connect") == 1


def test_explicit_refresh_retries_only_unavailable_connection(session):
    raw = session.factories["mircat"](configuration={})
    initialize = raw.initialize
    def unavailable(): raise RuntimeError("offline")
    raw.initialize = unavailable
    session.start()
    assert "mircat" in session.errors
    raw.initialize = initialize
    session.start()
    assert not session.errors
    assert raw.calls.count("initialize") == 1
    assert session.devices["hf2li"].calls.count("connect") == 1


def test_manual_mircat_controls_use_the_already_initialized_session(session, tmp_path, monkeypatch):
    from control_app.workflows.mircat_widget_commands import MircatWidgetCommandHandler
    from control_app.ui.contracts import WorkflowCommand, WorkflowResult
    session.start()
    handler = MircatWidgetCommandHandler(operator="test")
    monkeypatch.setattr(handler, "_command_log_path", lambda: tmp_path/"manual.log")
    def check(command, log):
        assert handler.initialized
        assert handler.service.get_num_installed_qcls() == 1
        return WorkflowResult("complete", "connected")
    monkeypatch.setattr(handler, "_handle", check)
    owner = session.coordinator
    token = owner.acquire("manual:mircat")
    with owner.scope(token):
        assert handler(WorkflowCommand(device_key="mircat", command="mircat.refresh_status")).status == "complete"
    owner.release(token, safe_verified=True)
    assert session.devices["mircat"].calls.count("initialize") == 1


def test_failed_write_invalidates_cached_settings_and_retains_fault_ownership(session):
    session.start()
    def partial_write(value):
        session.devices["hf2li"].value = value
        raise RuntimeError("lost readback after write")
    session.devices["hf2li"].set_value = partial_write
    owner = session.coordinator
    token = owner.acquire("manual:settings")
    with owner.scope(token), pytest.raises(RuntimeError, match="lost readback"):
        session.device("hf2li").set_value(8)
    owner.release(token, safe_verified=False)
    with pytest.raises(RuntimeError, match="unavailable"):
        CachedDevice(session, "hf2li").export_settings_snapshot()
    assert owner.snapshot()["state"] == "fault"


def test_desktop_tab_switches_use_startup_snapshot_only(session, monkeypatch, tmp_path):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from control_app.ui.main_window import ControlSystemMainWindow
    from control_app.workflows.state_machine import WorkflowStateMachine
    from control_app.measurement_host import application_session as module
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(module, "ApplicationDeviceSession", lambda *args, **kwargs: session)
    handler = WorkflowStateMachine(operator="test", coordinator=session.coordinator, run_dir=tmp_path/"run")
    window = ControlSystemMainWindow(handler, connect_devices_on_startup=True)
    try:
        window.show()
        deadline = time.monotonic()+10
        while not session.ready or window._device_startup_worker is not None:
            app.processEvents()
            assert time.monotonic() < deadline
            time.sleep(.005)
        app.processEvents()
        assert session.errors == {}
        assert window.phase_scan_widget.runner.capabilities.verified
        for handle in window.measurement_lifecycle.handles:
            experiment = handle.instance_id.split(":")[0]
            adapter = getattr(handle.widget, "adapter", None)
            if experiment == "steady_state_slow_scan":
                assert adapter.readbacks["hf2li_settings"]["nodes"]
            elif experiment == "fixed_wavenumber_kinetics":
                assert adapter.live_readbacks["source_kind"] == "connected_readbacks"
            elif experiment == "microsecond_stroboscopy":
                assert adapter.capabilities["verified"]
            elif experiment == "nanosecond_stroboscopy":
                assert adapter.capabilities["filter_order"] == 4
            elif experiment == "repeated_rapid_scan":
                assert adapter.capabilities.connected_readback_id.startswith("application-settings-")
        before = {name: list(raw.calls) for name, raw in session.devices.items()}
        for _ in range(2):
            for mode in ("single", "dual"):
                window.set_detector_mode(mode)
                for i in range(window.tabs.count()):
                    window.tabs.setCurrentIndex(i)
                    app.processEvents()
        assert before == {name: raw.calls for name, raw in session.devices.items()}
    finally:
        window.safe_shutdown_completed = True
        window.close()
        window.deleteLater()
        finish(session)


def test_phase_sequence_uses_pooled_services_without_changing_stage_treatment(tmp_path, monkeypatch):
    from test_regular_phase_scan_acquisition import regular_fixture
    from control_app.measurement_modules.phase_scan.regular_phase_scan_runner import RegularPhaseScanRunner
    rig, adapter, _ = regular_fixture(tmp_path, prepared=False)
    owner = HardwareCoordinator(tmp_path/"phase.lock")
    session = ApplicationDeviceSession(owner, {}, factories={})
    counts = {"laser_init": 0, "laser_deinit": 0, "hf_connect": 0, "hf_close": 0}
    for raw, method, key in ((rig.laser, "initialize", "laser_init"), (rig.laser, "deinitialize", "laser_deinit"),
                             (rig.hf, "connect", "hf_connect"), (rig.hf, "close", "hf_close")):
        original = getattr(raw, method)
        def counted(*args, _original=original, _key=key, **kwargs):
            counts[_key] += 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(raw, method, counted)
    rig.hf.stop_acquisition = lambda: None
    rig.laser.get_red_laser_pointer_status = lambda: {"installed": False, "enabled": False}
    laser, hf, timer = adapter.laser_factory, adapter.hf_factory, adapter.t660_factory
    adapter.laser_factory = lambda **kw: shared_device("mircat", lambda: laser(**kw))
    adapter.hf_factory = lambda **kw: shared_device("hf2li", lambda: hf(**kw))
    adapter.t660_factory = lambda name, **kw: shared_device(name, lambda: timer(name, **kw))
    blocks = adapter.prepare_blocks
    def select(plan, events, cancel):
        rig.hf.events = events
        return blocks(plan, events, cancel)
    monkeypatch.setattr(adapter, "prepare_blocks", select)
    runner = RegularPhaseScanRunner(lambda: adapter, coordinator=owner, hardware_access=True)
    try:
        runner.execute("background", tmp_path/"runs", adapter.plan, laser_authorized=True)
        configured = deepcopy(rig.hf.values)
        assert runner.experiment_session_active
        runner.execute("test", tmp_path/"runs", adapter.plan, laser_authorized=True)
        assert rig.hf.values == configured
        runner.mark_preliminary_reviewed()
        runner.execute("run", tmp_path/"runs", adapter.plan, laser_authorized=True)
        assert counts == {"laser_init": 1, "laser_deinit": 0, "hf_connect": 1, "hf_close": 0}
        assert not rig.laser.emission and not rig.laser.armed
        finish(session)
        assert counts == {"laser_init": 1, "laser_deinit": 1, "hf_connect": 1, "hf_close": 1}
    finally:
        owner._unlock_os()


@pytest.mark.parametrize("failure", [None, "offline", "restoration failed"])
def test_startup_connections_overlap_but_keep_one_owner_and_per_device_order(session, monkeypatch, failure):
    from threading import Barrier, get_ident
    sdk_names = {"mircat", "hf2li", "picoscope"}
    rendezvous = {"sdk": Barrier(3, timeout=5), "serial": Barrier(3, timeout=5)}
    caller_thread = get_ident()
    threads = {}
    original_touch = Device.touch

    def tracked_touch(device, method):
        original_touch(device, method)  # asserts valid hardware ownership in this thread
        threads.setdefault(device.name, set()).add(get_ident())
        assert session.coordinator.snapshot()["state"] == "owned"
        assert not session.ready
        if method in ("connect", "initialize", "open_unit"):
            if device.name not in sdk_names:
                # Every SDK worker has completed, including refresh or failure,
                # before any serial connection is attempted.
                assert sdk_names.issubset(session.startup_device_seconds)
            rendezvous["sdk" if device.name in sdk_names else "serial"].wait()
            if device.name == "hf2li" and failure:
                raise RuntimeError(failure)

    monkeypatch.setattr(Device, "touch", tracked_touch)
    messages = []
    result = session.start(lambda message: messages.append((get_ident(), message)), recheck_capabilities=True)
    assert session.ready
    assert len(threads) == 6
    assert all(len(ids) == 1 for ids in threads.values())
    assert len(set.union(*(threads[name] for name in sdk_names))) == 3
    assert len(set.union(*(threads[name] for name in threads if name not in sdk_names))) == 3
    assert all(thread == caller_thread for thread, _ in messages)
    assert set(result["device_seconds"]) == set(session.factories)
    assert result["elapsed_seconds"] >= max(result["device_seconds"].values())
    assert set(result["errors"]) == ({"hf2li"} if failure else set())
    assert session.coordinator.snapshot()["state"] == ("fault" if failure == "restoration failed" else "free")
    for name, device in session.devices.items():
        assert device.calls[0] == ("initialize" if name == "mircat" else "open_unit" if name == "picoscope" else "connect")
    monkeypatch.setattr(Device, "touch", original_touch)
    finish(session)
