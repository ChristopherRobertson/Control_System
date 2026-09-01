"""No hardware: drive the production adapter through synthetic device transports."""
from copy import deepcopy
from dataclasses import replace
import json
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest

from control_app.workflows import phase_scan_acquisition as live
from control_app.workflows.phase_scan import PhaseScanEvent, PhaseScanSettings, build_phase_scan_plan
from control_app.workflows.phase_scan_data import ScanStore, load_native
from control_app.workflows.phase_scan_runner import PhaseScanRunner
from control_app.workflows.phase_scan_native import pump_reference_tick, spectrum_from_sweep


def small_plan(**kwargs):
    return build_phase_scan_plan(replace(PhaseScanSettings(), stop_wavenumber_cm1=1998,
        scan_speed_cm1_s=1000, phase_delay_us=500, pre_pump_ms=1, post_pump_ms=1, rest_period_s=.1, **kwargs))


class World:
    """Device clock and independently synthesized TTL/detector responses."""
    def __init__(self):
        self.now = 0.
        self.units = {}
        self.qcl = None
        self.fires = []
        self.sample_present = False
        self.open_interlock = False
        self.drop_markers = False
        self.drop_pump = False
        self.poll_failure = False
        self.bad_current = False
        self.fail_stop = False
        self.on_poll = lambda: None
        self.ranges = [{"qcl": 1, "min_cm1": 1800., "max_cm1": 2050.}]
        self.pump_s = None
        self.scan_start = self.scan_end = None
        self.base = 2**60

    def acquirer(self):
        return live.LivePhaseScanAcquirer(laser_factory=lambda **kw: Laser(self),
            hf_factory=lambda **kw: HF(self), t660_factory=lambda name, **kw: Timer(self, name))


class Timer:
    def __init__(self, world, name):
        self.world, self.name = world, name
        self.device_config = {"serial_number": name}
        self.source, self.shots = "OFF", 0
        self.channels = {ch: {"enabled": False} for ch in "ABCD"}
        self.recipe = {}
        world.units[name] = self

    def connect(self): pass
    def close(self): pass
    def identify(self): return f"Highland,T660,{self.name},fake"
    def set_trigger_source(self, source): self.source = source
    def disable_channel(self, ch):
        if self.world.fail_stop and ch == "A":
            raise RuntimeError("injected stop failure")
        self.channels[ch]["enabled"] = False
    def enable_channel(self, ch): self.channels[ch]["enabled"] = True
    def command(self, command, **kwargs): pass
    def get_shot_count(self): return self.shots
    def apply_recipe(self, recipe):
        self.recipe = deepcopy(recipe)
        self.source = recipe.get("trigger_source", self.source)
        for ch, values in recipe.get("channels", {}).items():
            self.channels[ch].update(values)

    def read_active_settings(self):
        def query(value): return {"ok": True, "response": str(value)}
        return {"queries": {"trigger_source": query(self.source), "gate_mode": query(0),
                "burst": query("OFF"), "frames_engine": query("OFF"),
                "synth_frequency": query(self.recipe.get("clock", {}).get("frequency", "2000000Hz"))},
            "channels": {ch: {"enabled": query("ON" if val["enabled"] else "OFF"),
                "delay_edge": query(val.get("delay", "0ns")), "width_edge": query(val.get("width", "10us")),
                "polarity": query(val.get("polarity", "negative")), "termination": query("50OHM"),
                "timing_mode": query("DW")} for ch, val in self.channels.items()}}

    def fire_remote_trigger(self):
        assert self.name == "t660_1" and self.source == "REM"
        assert not self.world.units["t660_2"].channels["D"]["enabled"]
        assert not self.channels["D"]["enabled"]
        self.shots += 1
        self.world.fires.append(deepcopy(self.channels))
        if self.channels["A"]["enabled"]:
            assert self.channels["B"]["enabled"]
            self.world.pump_s = self.world.now + float(self.channels["A"]["delay"][:-1]) + .000180
        else:
            self.world.pump_s = None
        # A deliberately nonzero scan-start latency, independent of the plan.
        self.world.scan_start = self.world.now + float(self.channels["C"]["delay"][:-1]) + .000100
        request = self.world.qcl.request
        self.world.scan_end = self.world.scan_start + abs(request["stop_cm1"]-request["start_cm1"])/request["scan_rate_cm1_s"]
        self.world.qcl.triggered = True


class Laser:
    def __init__(self, world):
        self.world = world
        world.qcl = self
        self.emission = self.armed = self.triggered = self.started = False
        self.params = {}
    def initialize(self): pass
    def deinitialize(self): pass
    def is_interlock_set(self): return not self.world.open_interlock
    def is_key_switch_set(self): return True
    def get_system_error_word(self): return 0
    def is_emission_on(self): return self.emission
    def is_laser_armed(self): return self.armed
    def get_num_installed_qcls(self): return len(self.world.ranges)
    def get_qcl_tuning_range(self, i): return self.world.ranges[i-1]
    def get_qcl_pulse_limits(self, i): return {"max_pulse_rate_hz": 2e6, "max_pulse_width_ns": 500, "max_duty_cycle": 30.}
    def get_qcl_current_limits(self, i): return (100, 1500)
    def set_qcl_pulse_params(self, **kw): self.params[kw["qcl"]] = kw
    def get_qcl_current(self, i): return 999 if self.world.bad_current else self.params[i]["current_ma"]
    def get_qcl_pulse_rate(self, i): return self.params[i]["pulse_rate_hz"]
    def get_qcl_pulse_width(self, i): return self.params[i]["pulse_width_ns"]
    def set_external_sweep_trigger_params(self, **kw):
        self.trigger = kw
        return {"pulse_mode": live.PULSE_MODE_EXTERNAL_TRIGGER, "process_trigger_mode": live.PROC_TRIG_MODE_EXTERNAL,
                "units": live.UNITS_CM1, "start": kw["start_cm1"], "stop": kw["stop_cm1"], "interval": kw["wavelength_trigger_interval_cm1"]}
    def set_wavelength_trigger_pulse_width_us(self, value): self.marker_width = value*1e-6; return value
    def arm(self): self.armed = True
    def disarm(self): self.armed = False
    def are_tecs_ready(self): return True
    def tune_to_wavenumber(self, wn, **kw): pass
    def is_tuned(self): return True
    def turn_emission_on(self, **kw): assert kw["approved_laser_safety_condition"]; self.emission = True
    def turn_emission_off(self): self.emission = False
    def start_sweep_scan(self, **kw): self.request = kw; self.started = True; self.triggered = False
    def stop_scan_if_needed(self): self.started = False
    def cancel_manual_tune(self): pass
    def get_scan_waiting_process_trigger(self): return self.started and not self.triggered
    def get_scan_status(self):
        active = self.started and (not self.triggered or self.world.now < self.world.scan_end)
        return {"scan_in_progress": active}
    def read_state(self): return SimpleNamespace(to_dict=lambda: {"emission_on": self.emission, "armed": self.armed})


class HF:
    def __init__(self, world): self.world = world; self.preset = None
    def connect(self): pass
    def close(self): pass
    def load_preset(self, name):
        return live.HF2LIPreset(name, {"signal_inputs": {}, "pll": {"freqcenter_hz": 2e6},
            "demodulators": [{"index": i, "enable": True, "rate_sps": 2000, "timeconstant_s": .001, "order": 4} for i in (0, 2, 3)]})
    def apply_preset(self, preset): self.preset = preset
    def get_oscillator_frequency(self, i): return 2e6
    def get_clockbase(self): return 100_000_000
    def export_settings_snapshot(self, **kwargs):
        return {"device_id": "fake", "read_errors": {}, "nodes": {"/fake/demods/0/rate": {"type": "double", "value": 2000.}}}
    def start_acquisition(self, **kwargs): pass
    def stop_acquisition(self): pass
    def read_acquisition(self, duration):
        w = self.world
        if w.poll_failure:
            raise RuntimeError("injected USB poll failure")
        first = round(w.now*1e8)
        w.now += duration
        end = round(w.now*1e8)
        data = {}
        for demod, stride in ((0, 1000), (2, 500), (3, 1000)):
            relative = np.arange(first+stride, end+1, stride, dtype=np.uint64)
            times = relative.astype(float)/1e8
            dio = np.zeros(len(times), dtype=np.uint32)
            absorption = np.zeros(len(times))
            aux = np.zeros(len(times))
            if w.qcl.triggered:
                active = (times >= w.scan_start) & (times < w.scan_end+5e-6)
                dio[active] |= 1 << 21
                request = w.qcl.request
                span = abs(request["stop_cm1"]-request["start_cm1"])
                n = round(span/w.qcl.trigger["wavelength_trigger_interval_cm1"])
                if not w.drop_markers:
                    for at in np.linspace(w.scan_start, w.scan_end, n+1):
                        dio[(times >= at-1e-12) & (times < at+w.qcl.marker_width-1e-12)] |= 1 << 22
                if w.pump_s is not None:
                    pulse = (times >= w.pump_s) & (times < w.pump_s+.00005)
                    if not w.drop_pump:
                        dio[pulse] |= 1 << 17
                        aux[pulse] = 1.
                if w.sample_present:
                    wn = request["start_cm1"]+(request["stop_cm1"]-request["start_cm1"])*(times-w.scan_start)/(w.scan_end-w.scan_start)
                    absorption = .1*np.exp(-((wn-1999)/.3)**2)
                    if w.pump_s is not None:
                        age = times-w.pump_s
                        absorption *= np.where(age < 0, 1., -np.expm1(-np.maximum(age, 0)/.001))
            r = 2*10**(-absorption) if demod == 0 else np.ones(len(times))
            data[f"/fake/demods/{demod}/sample"] = {"timestamp": relative+np.uint64(w.base),
                "x": r, "y": np.zeros(len(times)), "dio": dio, "auxin0": aux, "auxin1": aux}
        w.on_poll()
        return {"data": data}


@pytest.fixture
def world(monkeypatch):
    w = World()
    monkeypatch.setattr(live, "monotonic", lambda: w.now)
    return w


@pytest.mark.parametrize("delay", [-12000, -180, 0, 2000])
def test_pump_and_process_share_one_hardware_event_with_signed_delays(delay):
    recipe, _ = live.event_timing(PhaseScanEvent(1, 1, 0, True, delay))
    channels = recipe["channels"]
    fire, qswitch, process = [float(channels[ch]["delay"][:-1]) for ch in "ABC"]
    assert min(fire, qswitch, process) >= 0
    assert process-(fire+.000180) == pytest.approx(delay*1e-6, abs=1e-12)
    assert qswitch-fire == pytest.approx(.000179830)
    assert not channels["D"]["enabled"]
    assert recipe["trigger_source"] == "REM"


def test_live_adapter_requires_explicit_operation_confirmation_before_connecting(world, tmp_path):
    adapter = world.acquirer()
    with pytest.raises(PermissionError):
        adapter.prepare(small_plan().settings, ScanStore(tmp_path, "background", small_plan()), Event())
    assert not world.units and world.qcl is None


def test_background_and_air_polymer_test_scan_use_production_adapter_without_pump(world, tmp_path):
    runner = PhaseScanRunner(world.acquirer)
    p = small_plan()
    runner.execute("background", tmp_path, p, laser_authorized=True)
    assert runner.background is not None
    world.sample_present = True
    result = runner.execute("test", tmp_path, p, laser_authorized=True)
    assert np.nanmax(result["absorbance"]) == pytest.approx(.1, abs=.002)
    assert len(world.fires) == 2
    assert all(not fire["A"]["enabled"] and not fire["B"]["enabled"] for fire in world.fires)
    assert not world.qcl.emission and not world.qcl.armed
    assert all(unit.source == "OFF" and all(not c["enabled"] for c in unit.channels.values()) for unit in world.units.values())
    assert len(list(result["path"].glob("raw/rep_*/*.npz"))) == 1
    assert len(list(result["path"].glob("processed/scans/*.csv"))) == 1
    assert json.loads((result["path"] / "cleanup.json").read_text())["safe_state_verified"]


def test_full_live_sequence_records_one_pump_per_phase_and_centered_map(world, tmp_path):
    runner = PhaseScanRunner(world.acquirer)
    p = small_plan()
    runner.execute("background", tmp_path, p, laser_authorized=True)
    world.sample_present = True
    result = runner.execute("run", tmp_path, p, laser_authorized=True)
    assert sum(f["A"]["enabled"] for f in world.fires) == p.total_pump_events
    reconstruction = result["reconstruction"]
    np.testing.assert_allclose(reconstruction["time_s"], [-.001, -.0005, 0, .0005, .001])
    assert reconstruction["display_pump_time_ms"] == 1
    assert reconstruction["pump_reference_bases"] == ["electrical_sync"]
    assert np.isfinite(reconstruction["absorbance"]).any()
    assert len(list(result["path"].glob("raw/rep_*/*.npz"))) == p.total_scans


@pytest.mark.parametrize("reference", ["auxin0", "auxin1"])
def test_rear_aux_pump_reference_uses_observed_samples(world, tmp_path, reference):
    adapter = world.acquirer()
    p = small_plan(pump_reference=reference)
    cancel = Event()
    adapter.authorize(True)
    try:
        adapter.prepare(p.settings, ScanStore(tmp_path, "run", p), cancel)
        raw, spectrum = adapter.capture(p.event_at(1), cancel)
        assert spectrum.metadata["pump_time_basis"] == "aux_input"
        assert spectrum.pump_time_s is not None
        assert np.isfinite(spectrum.sample_time_s-spectrum.pump_time_s).all()
        assert raw["optical_valid"]
    finally:
        adapter.close()


@pytest.mark.parametrize("failure,message", [("open_interlock", "interlock"), ("bad_current", "current_ma"), ("poll_failure", "USB poll")])
def test_faults_never_promote_background_and_stop_all_outputs(world, tmp_path, failure, message):
    setattr(world, failure, True)
    runner = PhaseScanRunner(world.acquirer)
    with pytest.raises(RuntimeError, match=message):
        runner.execute("background", tmp_path, small_plan(), laser_authorized=True)
    assert runner.background is None and not world.fires
    assert not world.qcl.emission and not world.qcl.armed
    assert all(not c["enabled"] for unit in world.units.values() for c in unit.channels.values())


def test_missing_wavelength_markers_are_explicitly_provisional_not_renumbered(world, tmp_path):
    world.drop_markers = True
    runner = PhaseScanRunner(world.acquirer)
    runner.execute("background", tmp_path, small_plan(), laser_authorized=True)
    assert runner.background.spectrum.metadata["provisional"]
    assert runner.background.spectrum.metadata["wavenumber_basis"] == "nominal_sweep_bounds"
    assert any("0 markers" in w for w in runner.background.spectrum.metadata["warnings"])


def test_missing_pump_marker_preserves_raw_data_and_stops_sequence(world, tmp_path):
    runner = PhaseScanRunner(world.acquirer)
    p = small_plan()
    runner.execute("background", tmp_path, p, laser_authorized=True)
    world.drop_pump = True
    with pytest.raises(RuntimeError, match="pump-reference"):
        runner.execute("run", tmp_path, p, laser_authorized=True)
    assert sum(f["A"]["enabled"] for f in world.fires) == 1
    partial = list(tmp_path.rglob("partial/*.npz"))
    assert len(partial) == 1
    raw = load_native(partial[0])
    assert raw["segments"][0]["native_chunks"]
    assert not world.qcl.emission and not world.qcl.armed


def test_multi_qcl_static_scan_uses_one_probe_trigger_per_segment(world, tmp_path):
    world.ranges = [{"qcl": 1, "min_cm1": 1999, "max_cm1": 2050},
                    {"qcl": 2, "min_cm1": 1800, "max_cm1": 1999.5}]
    runner = PhaseScanRunner(world.acquirer)
    runner.execute("background", tmp_path, small_plan(), laser_authorized=True)
    spectrum = runner.background.spectrum
    assert len(world.fires) == 2
    assert set(spectrum.segment_id) == {0, 1}
    assert np.all(np.diff(spectrum.sample_time_s) > 0)
    assert np.all(np.diff(spectrum.wavenumber_cm1) < 0)


def test_opening_default_handler_attaches_adapter_without_opening_hardware(tmp_path, monkeypatch):
    from control_app.workflows.state_machine import WorkflowStateMachine
    def forbidden(*args, **kwargs): raise AssertionError("unexpected device connection")
    monkeypatch.setattr(live.MircatService, "initialize", forbidden)
    monkeypatch.setattr(live.HF2LIService, "connect", forbidden)
    monkeypatch.setattr(live.T660Service, "connect", forbidden)
    handler = WorkflowStateMachine(operator="offline test", run_dir=tmp_path, hardware_access=True)
    assert handler.phase_scan_runner.available
    assert isinstance(handler.phase_scan_runner.acquirer_factory(), live.LivePhaseScanAcquirer)


@pytest.mark.parametrize("failure", ["abort", "interlock"])
def test_abort_or_interlock_loss_during_poll_stops_before_any_trigger(world, tmp_path, failure):
    runner = PhaseScanRunner(world.acquirer)
    def fail():
        if failure == "abort":
            runner.abort()
        else:
            world.open_interlock = True
    world.on_poll = fail
    with pytest.raises(RuntimeError, match="aborted|interlock"):
        runner.execute("background", tmp_path, small_plan(), laser_authorized=True)
    assert runner.background is None and not world.fires
    assert not world.qcl.emission and not world.qcl.armed
    assert list(tmp_path.rglob("partial/*.npz"))


def test_cleanup_failure_is_visible_and_does_not_accept_background(world, tmp_path):
    runner = PhaseScanRunner(world.acquirer)
    def break_stop():
        if world.qcl.triggered:
            world.fail_stop = True
    world.on_poll = break_stop
    with pytest.raises(RuntimeError, match="Safe shutdown failed"):
        runner.execute("background", tmp_path, small_plan(), laser_authorized=True)
    assert runner.background is None
    assert json.loads(next(tmp_path.rglob("result.json")).read_text())["status"] == "FAILED_SAFE_STATE_UNVERIFIED"
    assert not world.qcl.emission and not world.qcl.armed


def test_sdk_duty_cycle_percent_limit_is_enforced(world, tmp_path, monkeypatch):
    monkeypatch.setattr(Laser, "get_qcl_pulse_limits", lambda self, i: {
        "max_pulse_rate_hz": 2e6, "max_pulse_width_ns": 500, "max_duty_cycle": 20.})
    with pytest.raises(RuntimeError, match="readback limits"):
        PhaseScanRunner(world.acquirer).execute("background", tmp_path, small_plan(), laser_authorized=True)
    assert not world.qcl.armed and not world.qcl.emission and not world.fires


def test_actual_gui_buttons_complete_background_test_and_phase_run(world, tmp_path, monkeypatch):
    import os
    import time
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtTest import QTest
    from control_app import paths
    from control_app.ui.widgets.phase_scan_widget import PhaseScanWidget
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(paths, "_selected_save_location", tmp_path)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    widget = PhaseScanWidget(runner=PhaseScanRunner(world.acquirer))
    for name, value in vars(small_plan().settings).items():
        if name == "pump_reference":
            continue
        widget.inputs[name].setValue(value)
    assert widget.background_button.isEnabled()
    assert not widget.test_button.isEnabled() and not widget.start_button.isEnabled()
    def click_and_wait(button):
        button.click()
        assert widget.command_running() and widget.abort_button.isEnabled()
        deadline = time.monotonic()+5
        while widget.command_running() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.002)  # Let both the Qt worker and SDK-start thread acquire the GIL.
        if widget.command_running():
            widget.runner.abort()
            widget.worker.wait(3000)
            app.processEvents()
        assert not widget.command_running(), widget.scan_status.text()
        assert widget._pending_result is not None, widget.scan_status.text()
    click_and_wait(widget.background_button)
    assert widget.test_button.isEnabled() and widget.start_button.isEnabled()
    world.sample_present = True
    click_and_wait(widget.test_button)
    assert "pump OFF" in widget.scan_status.text()
    assert widget.canvas.y_label == "Absorbance"
    click_and_wait(widget.start_button)
    assert widget._surface is not None
    assert widget.plot_stack.currentWidget() is widget._surface
    axes = widget._surface.figure.axes[0]
    assert axes.get_ylabel() == "Absorbance"
    assert "pump sync at 1" in axes.get_zlabel()
    assert axes.get_zlim() == pytest.approx((2, 0))
    assert list(tmp_path.rglob("absorbance_map.png"))
    assert not widget.abort_button.isEnabled()
    widget.deleteLater()
    app.processEvents()
