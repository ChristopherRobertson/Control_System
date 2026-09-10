"""Installed factories and real service code, with all physical transports replaced.

These fakes implement wire/SDK responses, not experiment service methods. Thus
command signatures, ownership checks, SDK bindings, readbacks, and restoration
run through the same installed service classes as an ordinary Blank or Sample.
"""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import re
import sys
import time

import numpy as np
import pytest
import yaml

from control_app.devices.hf2li_service import HF2LIService
from control_app.devices.mircat_service import MircatService
from control_app.devices import t660_service
from control_app.measurement_host.context import ContextFactory
from control_app.measurement_host.device_factories import installed_device_factories
from control_app.measurement_host.ownership import HardwareCoordinator
from control_app.measurement_modules.single_pump_scan_burst.persistence import RunStore, load_run
from control_app.measurement_modules.single_pump_scan_burst.planner import compile_plan
from control_app.measurement_modules.single_pump_scan_burst.runner import BurstRunner
from control_app.measurement_modules.single_pump_scan_burst.settings import Settings


class MircatSDKTransport:
    def __init__(self):
        self.functions, self.calls = {}, []
        self.qcls = {1: [2e6, 150., 420.], 2: [2e6, 150., 810.]}
        self.trigger = [1, 0, 1900., 1950., 5., 2, 0, 0]
        self.sweep = [1900., 1950., 5000., 2, 1, False, 1]
        self.armed = self.emission = self.closed = False
        self.interlocked = True
        self.marker_width = 20
        self.scan_waiting = False
        self.stuck_scan_field = None

    def __getattr__(self, name):
        if not name.startswith("MIRcatSDK_"):
            raise AttributeError(name)
        if name not in self.functions:
            # Plain functions support ctypes argtypes/restype assignment.
            def call(*args):
                return self.dispatch(name.removeprefix("MIRcatSDK_"), args)
            self.functions[name] = call
        return self.functions[name]

    def dispatch(self, name, args):
        values = [getattr(a, "value", None) for a in args]
        self.calls.append((name, values))
        def out(values, pointers=args):
            for pointer, value in zip(pointers, values):
                pointer._obj.value = value
        booleans = {"IsConnectedToLaser": True, "IsInterlockedStatusSet": self.interlocked,
            "IsKeySwitchStatusSet": True, "IsLaserArmed": self.armed, "IsEmissionOn": self.emission,
            "AreTECsAtSetTemperature": True, "IsTuned": True,
            "GetScanWaitingProcessTrigger": self.scan_waiting or self.stuck_scan_field == "scan_waiting_process_trigger"}
        if name in booleans:
            out([booleans[name]])
        elif name == "GetNumInstalledQcls": out([2])
        elif name == "GetActiveQcl": out([2])  # Deliberately differs from the covering QCL.
        elif name == "GetQclTuningRange": out([1800., 2000., 2] if values[0] == 1 else [2050., 2250., 2], args[1:])
        elif name in ("GetQCLPulseRate", "GetQCLPulseWidth", "GetQCLCurrent"):
            index = ("GetQCLPulseRate", "GetQCLPulseWidth", "GetQCLCurrent").index(name)
            out([self.qcls[values[0]][index]], args[1:])
        elif name == "SetQCLParams": self.qcls[values[0]] = values[1:]
        elif name == "GetWlTrigParams": out(self.trigger)
        elif name == "SetWlTrigParams": self.trigger = values
        elif name == "GetWlTrigPulseWidth": out([self.marker_width])
        elif name == "SetWlTrigPulseWidth": self.marker_width = values[0]
        elif name == "GetWlTrigChanParams":
            _, _, start, stop, interval, units, _, _ = self.trigger
            out([units, start, stop, interval, round(abs(stop-start)/interval)+1], args[1:])
        elif name == "StartSweepScan":
            self.sweep = values
            self.scan_waiting = True
        elif name in ("GetSweepStartWW", "GetSweepStopWW", "GetSweepScanSpeed"):
            out([self.sweep[("GetSweepStartWW", "GetSweepStopWW", "GetSweepScanSpeed").index(name)], 2])
        elif name == "GetSweepNumScans": out([self.sweep[4]])
        elif name == "GetScanStatus":
            out([self.stuck_scan_field == key for key in ("scan_in_progress", "scan_active", "scan_paused")]
                + [0, 0, 1900., 2, False, False])
        elif name == "GetAPIVersion": out([1, 0, 0])
        elif name == "GetTuneWW": out([1900., 2, 1])
        elif name == "GetActualWW": out([1900., 2, False])
        elif name == "GetQCLPulseLimits": out([2e6, 500., 30.], args[1:])
        elif name == "GetQCLMinPulsedCurrent": out([0], args[1:])
        elif name == "GetQCLMaxPulsedCurrent": out([1500], args[1:])
        elif name in ("GetSystemErrorWord", "GetStatusMask"): out([0])
        elif name == "ArmLaser": self.armed = True
        elif name == "DisarmLaser": self.armed = False
        elif name == "TurnEmissionOn": self.emission = True
        elif name == "TurnEmissionOff": self.emission = False
        elif name == "DeInitialize": self.closed = True
        elif name == "GetRedLaserPointerStatus": out([False, False])
        elif name == "StopScanInProgress": self.scan_waiting = False
        elif name in ("Initialize", "TuneToWW", "CancelManualTuneMode", "EnableRedLaserPointer"):
            pass
        else:
            raise AssertionError(f"Unimplemented SDK transport call {name}")
        return 0


class SerialTransport:
    def __init__(self, bank, port):
        self.bank, self.port = bank, port
        self.closed = False
        self.commands, self.frames, self.pending = [], {}, {}
        self.state = {"TRIG:SOUR": "OFF", "TRIG:FREQ:SYN": "2000000", "TRIG:EXT:PRED": "1",
            "TFR:LOOP:FIRST": "0", "TFR:LOOP:LAST": "1", "TFR:LOOP:COUNT": "0", "TFR:STAT": "OFF"}
        self.channels = {ch: {"enabled": "0", "mode": "DW", "polarity": "POS", "term": "50OHM"} for ch in "ABCD"}
        self.times = {str(i): ("0s" if i % 2 else "0.000000100000s") for i in range(1, 9)}
        self.references = {str(i): "0" for i in range(1, 9)}
        if getattr(bank, "ignore_reference_restore", False):
            self.references["2"] = "1"
        self.response = b""

    def reset_input_buffer(self): self.response = b""
    def flush(self): pass
    def close(self): self.closed = True
    def readline(self):
        result, self.response = self.response, b""
        return result
    def write(self, payload):
        text = payload.decode().strip()
        self.commands.append(text)
        self.response = (";".join(self.command(item) for item in text.split(";")) + "\r").encode()
    def command(self, text):
        text = text.upper().lstrip(":")
        for long, short in (("TRIGGER", "TRIG"), ("EXTERNAL", "EXT"), ("PREDIV", "PRED"),
            ("TFRAME", "TFR"), ("STATUS", "STAT"), ("CHANNEL", "CHAN"), ("ACTIVE", "ACT"),
            ("POLARITY", "POL"), ("TERMINATION", "TERM")):
            text = text.replace(long, short)
        key, _, arg = text.partition(" ")
        if key == "*IDN?": return "HTI,T660-2,00431,28E660-1-1.7"
        if key == "FEATURE:FRAME?": return "1"
        if key.startswith("TIME:RELTO"):
            edge = re.search(r"\d+", key)[0]
            if "?" in key: return self.references[edge]
            if getattr(self.bank, "ignore_reference_restore", False) and edge == "2" and arg == "1":
                return "OK"
            self.references[edge] = arg
        elif key.startswith(("TIME:DEL", "TIME:QUEUE")):
            edge = re.search(r"\d+", key)[0]
            if "?" in key: return self.times[edge]
            self.times[edge] = arg
        elif key.startswith("CHAN:QUEUE:MODE"):
            channel, enabled = arg.replace(" ", "").split(",")
            self.pending[channel] = enabled == "ON"
        elif key == "TFR:STORE":
            assert not self.bank.labone.subscriptions, "No unbounded native backlog during frame upload"
            self.frames[int(arg)] = deepcopy(self.pending)
        elif key == "TFR:START":
            self.state["TFR:STAT"] = "RUNNING"
            self.bank.armed_frames = deepcopy(self.frames)
        elif key == "TFR:STOP": self.state["TFR:STAT"] = "OFF"
        elif key == "TFR:STAT?": return "DONE" if self.bank.armed_frames is None else self.state["TFR:STAT"]
        elif key.startswith("CHAN:") and arg in self.channels:
            target = self.channels[arg]
            getters = {"CHAN:ON?": "enabled", "CHAN:TIMINGMODE?": "mode", "CHAN:50OHM?": "term", "CHAN:ACT:POL?": "polarity"}
            if key in getters: return target[getters[key]]
            if key in ("CHAN:ON", "CHAN:OFF"): target["enabled"] = "1" if key.endswith(":ON") else "0"
            if key in ("CHAN:POS", "CHAN:NEG"): target["polarity"] = key.split(":")[-1]
            if key in ("CHAN:DELAYWIDTH", "CHAN:RISEFALL"): target["mode"] = "DW" if key.endswith("WIDTH") else "RF"
        elif "?" in key:
            return self.state.get(key.replace("?", ""), "0")
        else:
            self.state[key] = arg
        return "OK"


class LabOneTransport:
    def __init__(self, bank):
        self.bank, self.nodes, self.subscriptions = bank, {}, set()
        self.tick, self.closed, self.poll_count = 2**54, False, 0
        self.fail_health_after_capture = False
    def listNodes(self, *args): return ["/dev18500/demods/0/sample"]
    def connectDevice(self, *args): pass
    def sync(self): pass
    def disconnect(self): self.closed = True
    def setInt(self, path, value): self.nodes[path] = int(value)
    def setDouble(self, path, value): self.nodes[path] = float(value)
    def setString(self, path, value): self.nodes[path] = str(value)
    def getString(self, path): return str(self.nodes.get(path, "HF2LI"))
    def getInt(self, path):
        if path.endswith("clockbase"): return 210000000
        if "/adcclip/" in path: return int(self.fail_health_after_capture and self.bank.pumps > 0)
        if path.endswith(("/plls/0/locked", "/system/extclk")): return 1
        return int(self.nodes.get(path, 1 if path.endswith(("/order", "/harmonic")) else 0))
    def getDouble(self, path):
        defaults = {"rate": 230000., "timeconstant": 1e-6, "range": 1., "freq": 2e6}
        return float(self.nodes.get(path, defaults.get(path.split("/")[-1], 0.)))
    def subscribe(self, path): self.subscriptions.add(path)
    def unsubscribe(self, path):
        if path == "*": self.subscriptions.clear()
        else: self.subscriptions.discard(path)
    def poll(self, *args):
        self.poll_count += 1
        frames, self.bank.armed_frames = self.bank.armed_frames, None
        count = int(self.bank.sdk.sweep[4]) if frames else 0
        words = np.full(max(4, count*32+4), 1 << 17, dtype=np.uint32)
        if frames:
            pumped = any(frame.get("A") or frame.get("B") for frame in frames.values())
            self.bank.pumps += int(pumped)
            if pumped: words[1] &= np.uint32(~np.uint32(1 << 17))
            for index in range(count):
                offset = 32*index
                words[offset+2:offset+27] |= np.uint32((1 << 21) | (1 << 20))
                words[offset+3:offset+25:2] |= np.uint32(1 << 22)
        ticks = np.uint64(self.tick) + np.arange(len(words), dtype=np.uint64)*1000
        self.tick = int(ticks[-1]) + 2100000
        result = {}
        for path in self.subscriptions:
            result[path] = {"timestamp": ticks.copy(), "dio": words.copy(),
                "x": np.full(len(words), .1), "y": np.zeros(len(words))}
        if hasattr(self, "on_poll"):
            self.on_poll()
        return result


@pytest.fixture
def transports(monkeypatch, tmp_path):
    bank = SimpleNamespace(sdk=MircatSDKTransport(), serials=[], armed_frames=None, pumps=0)
    bank.labone = LabOneTransport(bank)
    def serial(**kwargs):
        transport = SerialTransport(bank, kwargs["port"])
        bank.serials.append(transport)
        return transport
    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=serial))
    monkeypatch.setattr(t660_service, "time", SimpleNamespace(time=time.time, sleep=lambda _: None))
    monkeypatch.setattr(HF2LIService, "_load_labone_module", lambda self: SimpleNamespace(ziDAQServer=lambda *a: bank.labone))
    monkeypatch.setattr(MircatService, "_load_sdk", lambda self: bank.sdk)
    # Actual installed configuration, including the Pico entry with no capture
    # recipe. It must not be constructed for normal electrical acquisition.
    repository = Path(__file__).resolve().parents[4]
    bank.configuration = yaml.safe_load((repository / "instrument/hardware_configuration.yaml").read_text(encoding="utf-8"))
    bank.coordinator = HardwareCoordinator(tmp_path / "instrument.lock")
    bank.factory = ContextFactory(configuration_provider=lambda: bank.configuration,
        real_device_factories=installed_device_factories(), save_root_provider=lambda: tmp_path,
        ownership=bank.coordinator)
    return bank


def make_runner(bank, mode, *, progress=None, **overrides):
    request = Settings(mode=mode, early_scan_count=1, later_burst_count=1, scans_per_burst=1,
        final_scan_count=1, preliminary_scan_count=1, first_later_burst_s=.2,
        observation_limit_s=.5, tuning_settling_time_s=0.)
    request = replace(request, **overrides)
    plan = compile_plan(request)
    assert plan.valid, plan.errors
    context = bank.factory.for_experiment("single_pump_scan_burst").for_mode(mode)
    operation = context.begin_operation(request.to_dict(), hardware=True)
    store = RunStore(operation.output_path, {"mode": mode, "settings": request.to_dict()})
    return BurstRunner(context, plan, operation, store=store, progress=progress)


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_installed_factories_resolve_defaults_and_capture_electrical_raw(transports, mode):
    runner = make_runner(transports, mode)
    result = runner.run()
    assert result.status == "complete", result.to_dict()
    assert result.epoch["electrically_observed"] and not result.epoch["optical_arrival_observed"]
    assert result.epoch["time_reference"] == "electrical_trigger"
    assert result.epoch["electrical_trigger_edge"] == "falling"
    assert transports.pumps == 1
    assert runner.settings.qcl == 1 and runner.settings.probe_current_ma == 420.
    assert runner.plan.requested_settings.qcl is None
    assert "picoscope" not in runner.adapter.devices
    assert transports.labone.closed and transports.sdk.closed
    assert all(serial.closed for serial in transports.serials)
    assert not transports.sdk.emission and not transports.sdk.armed
    assert transports.coordinator.snapshot()["state"] == "free"
    retained = load_run(result.output_path)
    assert sum(e["kind"] == "pump_intent" for e in retained["events"]) == 1
    assert any("hf2-native" in path for path in retained["chunks"])


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_installed_services_stop_upload_before_pump_and_restore(transports, mode):
    runner = make_runner(transports, mode)
    runner.callback = lambda item: runner.cancel() if item["stage"] == "upload" else None
    result = runner.run()
    assert result.status == "stopped", result.to_dict()
    assert transports.pumps == 0
    assert transports.coordinator.snapshot()["state"] == "free"
    assert all(serial.closed for serial in transports.serials)


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_actual_sdk_interlock_failure_restores_without_pump(transports, mode):
    transports.sdk.interlocked = False
    result = make_runner(transports, mode).run()
    assert result.status == "failed", result.to_dict()
    assert "interlock" in result.error.lower()
    assert transports.pumps == 0
    assert not transports.sdk.emission and not transports.sdk.armed
    assert transports.coordinator.snapshot()["state"] == "free"


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_installed_blank_sample_and_single_pump_workflow(transports, mode):
    blank = make_runner(transports, mode).prepare("baseline")
    assert blank["complete"], blank
    assert transports.pumps == 0
    sample = make_runner(transports, mode).prepare("preliminary")
    assert sample["complete"], sample
    assert transports.pumps == 0
    runner = make_runner(transports, mode)
    result = runner.run(baseline={"preliminary": sample, "blank": blank})
    assert result.status == "complete", result.to_dict()
    assert transports.pumps == 1
    assert result.data["latest_processed"]["valid"].any()
    assert result.summary["actual_settings"]["probe_current_ma"] == 420.
    assert transports.coordinator.snapshot()["state"] == "free"
    # The real pending upload must emit active-low Fire/Q-switch commands.
    commands = [command for serial in transports.serials for command in serial.commands]
    assert any(":CHANnel:QUEue:POLarity A, NEG" in command for command in commands)


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_health_fault_after_short_block_keeps_raw_and_never_repeats_pump(transports, mode):
    transports.labone.fail_health_after_capture = True
    result = make_runner(transports, mode).run()
    assert result.status == "incomplete", result.to_dict()
    assert "overload" in result.error.lower()
    assert transports.pumps == 1
    assert any("hf2-native" in path for path in load_run(result.output_path)["chunks"])
    assert transports.coordinator.snapshot()["state"] == "free"


@pytest.mark.parametrize("diagnostic", ["clipped", "failed"])
def test_optional_optical_capture_failure_preserves_electrical_run(transports, diagnostic):
    runner = make_runner(transports, "single")
    runner._make_adapter()
    configure = runner.adapter.configure
    def configured(**kwargs):
        result = configure(**kwargs)
        def capture(**callbacks):
            callbacks["after_arm"]()
            if diagnostic == "failed":
                raise RuntimeError("Optional optical SDK diagnostic failed after arm")
            return {"overflow": True, "ch_a_adc": np.array([0, 100], dtype=np.int16)}
        runner.adapter.pico = SimpleNamespace(capture_block_data=capture)
        runner.adapter.recipe["optical_pump_diagnostic"] = {}
        return result
    runner.adapter.configure = configured
    result = runner.run()
    assert result.status == "complete", result.to_dict()
    assert transports.pumps == 1
    assert result.epoch["electrically_observed"] and not result.epoch["optical_arrival_observed"]
    assert transports.coordinator.snapshot()["state"] == "free"
    events = load_run(result.output_path)["events"]
    assert any(event["kind"] in ("optional_diagnostic_error", "optical_timing_unresolved") for event in events)


def test_disabled_old_metadata_never_changes_or_blocks_installed_acquisition(transports):
    runner = make_runner(transports, "dual", hardware_evidence={"operating_configuration": "old-metadata-only",
        "sample_prior_probe_pulse_on_s": "unavailable"}, plateau_enabled=False,
        plateau_band_windows_cm1=((1.,),), plateau_required_bursts=-1,
        measured_temperature_k=None, temperature_check_interval_s=None)
    result = runner.run()
    assert result.status == "complete", result.to_dict()
    assert transports.pumps == 1
    assert runner.adapter.recipe["trajectory"]["marker_interval_cm1"] == 5.


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_stop_during_real_native_poll_inhibits_probe_and_preserves_partial_record(transports, mode):
    runner = make_runner(transports, mode)
    transports.labone.on_poll = lambda: runner.cancel() if transports.pumps else None
    result = runner.run()
    assert result.status == "stopped", result.to_dict()
    assert transports.pumps == 1
    assert not transports.labone.subscriptions
    assert transports.coordinator.snapshot()["state"] == "free"
    retained = load_run(result.output_path)
    assert any("hf2-native" in path for path in retained["chunks"])
    assert any(event["kind"] == "probe_enabled_interval" for event in retained["events"])
    interval = next(event["payload"] for event in retained["events"] if event["kind"] == "probe_enabled_interval")
    assert result.summary["probe_exposure_s"] == interval["pulse_on_upper_bound_s"]


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_check_connected_devices_only_closes_sessions_without_changing_outputs(transports, mode):
    transports.sdk.armed = transports.sdk.emission = True
    result = make_runner(transports, mode).prepare("capabilities")
    assert result["complete"], result
    assert result["capabilities"]["operating_values"]["probe_current_ma"] == 420.
    commands = [command.upper() for serial in transports.serials for command in serial.commands]
    assert not any(command in ("STOP", "TFRAME:STOP") for command in commands)
    assert not any(command.startswith(("TRIG:SOUR ", "CHAN:ON ", "CHAN:OFF ")) for command in commands)
    sdk_commands = [name for name, values in transports.sdk.calls]
    assert not set(sdk_commands) & {"ArmLaser", "DisarmLaser", "TurnEmissionOn", "TurnEmissionOff", "TuneToWW", "SetQCLParams"}
    assert transports.coordinator.snapshot()["state"] == "free"
    assert all(serial.closed for serial in transports.serials)
    assert transports.sdk.armed and transports.sdk.emission


def test_observed_surelite_sync_polarity_is_independent_of_t660_command_polarity(transports):
    result = make_runner(transports, "single", pump_polarity="positive").run()
    assert result.status == "complete", result.to_dict()
    assert result.epoch["electrical_trigger_edge"] == "falling"
    assert result.epoch["electrical_sync_source"] == "Surelite Variable Sync OUT on HF2LI DIO17"
    assert "Manual" in result.epoch["electrical_sync_polarity_source"]


def test_check_devices_retains_owner_fault_when_hf2_discovery_cannot_restore(transports):
    original_set_int, original_set_double = transports.labone.setInt, transports.labone.setDouble
    restoring = False
    def set_int(path, value):
        nonlocal restoring
        if path.endswith("/demods/0/enable") and value == 0:
            restoring = True
        original_set_int(path, value)
    def set_double(path, value):
        if restoring:
            raise RuntimeError("Injected HF2 restore write failure")
        original_set_double(path, value)
    transports.labone.setInt, transports.labone.setDouble = set_int, set_double
    result = make_runner(transports, "single").prepare("capabilities")
    assert result["status"] == "cleanup_failed", result
    assert "restoration failed" in result["error"]
    assert transports.coordinator.snapshot()["state"] == "fault"
    assert transports.labone.closed
    assert not any(command.upper() == "STOP" for serial in transports.serials for command in serial.commands)


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_ignored_t660_reference_restore_is_recorded_and_faults_owner(transports, mode):
    transports.ignore_reference_restore = True
    result = make_runner(transports, mode).prepare("preliminary")
    assert result["status"] == "cleanup_failed", result
    assert any("edge references did not restore" in error for error in result["cleanup_errors"])
    assert transports.coordinator.snapshot()["state"] == "fault"
    import json
    restoration = json.loads((Path(result["output_path"]) / "records/restoration.json").read_text())
    refs = restoration["records"]["t660_2-restored-references"]
    assert refs["expected"]["2"] == 1 and refs["actual"]["2"] == 0
    assert set(refs["actual"]) == {str(edge) for edge in range(1, 9)}
    assert all(serial.closed for serial in transports.serials)


@pytest.mark.parametrize("field", ["scan_in_progress", "scan_active", "scan_paused", "scan_waiting_process_trigger"])
def test_stuck_mircat_scan_state_after_stop_is_retained_and_faults_owner(transports, field):
    transports.sdk.stuck_scan_field = field
    result = make_runner(transports, "single").prepare("preliminary")
    assert result["status"] == "cleanup_failed", result
    assert any(field in error for error in result["cleanup_errors"])
    assert transports.coordinator.snapshot()["state"] == "fault"
    import json
    restoration = json.loads((Path(result["output_path"]) / "records/restoration.json").read_text())
    actual = restoration["records"]["mircat-final-state"]
    assert actual[field] is True
    assert actual["emission_on"] is False and actual["armed"] is False
    assert transports.sdk.closed
