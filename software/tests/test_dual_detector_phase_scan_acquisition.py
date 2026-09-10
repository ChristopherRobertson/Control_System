"""Both detector streams exercise the existing simulated continuous instruments."""
from dataclasses import replace
import json
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest

from control_app.workflows.dual_detector_phase_scan import (
    DualHF2Capabilities, DualDetectorPhaseScanSettings, build_dual_detector_phase_scan_plan,
)
from control_app.workflows.dual_detector_phase_scan_acquisition import DualDetectorPhaseScanAcquirer
from control_app.workflows.regular_phase_scan_acquisition import regular_event_timing
from control_app.workflows.phase_scan_labone import AcquisitionCapacityError
from test_regular_phase_scan_acquisition import RegularHF, RegularLaser, RegularTimer


def dual_fixture(tmp_path, *, preliminary=False, fault=None, host_capacity_bytes=None):
    base = DualHF2Capabilities()
    caps = replace(base, device_id="dev1234", verified=True,
                   sample=replace(base.sample, device_id="dev1234", verified=True),
                   reference=replace(base.reference, device_id="dev1234", verified=True))
    plan = build_dual_detector_phase_scan_plan(capabilities=caps)
    rig = SimpleNamespace(units={}, running=False, trace=[], fail_stop=False, interlock=True,
                          fault=fault, cancel=Event())
    rig.hf = RegularHF(rig, plan)
    rig.hf.clipping[1] = 0
    rig.hf.apply_preset(rig.hf.load_preset("exploratory_phase_scan_poc"))
    rig.hf.calls = rig.trace
    rig.laser = RegularLaser(rig)
    adapter = DualDetectorPhaseScanAcquirer(plan, laser_factory=lambda **kw: rig.laser,
        hf_factory=lambda **kw: rig.hf, t660_factory=lambda name, **kw: RegularTimer(rig, name),
        tec_ready_stability_s=0., host_capacity_bytes=host_capacity_bytes)
    adapter.authorize(True)
    adapter.prepare(plan.settings, SimpleNamespace(path=tmp_path), rig.cancel)
    events = [plan.event_at(index) for index in range(1 if preliminary else plan.total_scans)]
    rig.hf.events = events
    return rig, adapter, events


@pytest.mark.parametrize("preliminary", [True, False])
def test_dual_continuous_channels_deferred_read_and_restoration(tmp_path, preliminary):
    rig, adapter, events = dual_fixture(tmp_path, preliminary=preliminary)
    blocks = adapter.prepare_blocks(adapter.plan, events, rig.cancel)
    assert len(blocks) == 1 and len(events) == (1 if preliminary else 322)
    assert blocks[0]["daq"].read_policy == "deferred"
    modules = blocks[0]["daq"].modules
    assert {item["role"] for item in modules} == {"detectors", "detectors_3", "timing", "pump_events"}
    assert all(item["estimate"]["allocation_margin_fraction"] == 0 for item in modules)
    raw, records = adapter.capture_block(blocks[0], rig.cancel)
    assert len(records) == len(events)
    assert rig.trace.count("emission_enable") == rig.trace.count("frames_start") == 1
    assert rig.trace.index("t660_2_safe_stop") < rig.trace.index("daq_read")
    assert raw["labone"]["read_call_count"] == 4
    assert all(item["sequence_complete"] and not item["partial_salvage"]
               for item in raw["labone"]["read_phase_observations"])
    assert all(np.isfinite(s.reference_r).any() for _, s in records)
    for event, spectrum in records:
        assert spectrum.metadata["reference_demodulator"] == 3
        assert spectrum.metadata["sample_demodulator"] == 0
        assert spectrum.metadata["alignment"]["sample_filter_delay_s"] > 0
        assert np.allclose(spectrum.normalization_signal()[np.isfinite(spectrum.normalization_signal())], 1)
        a, b = [float(regular_event_timing(event)[0]["channels"][ch]["delay"][:-1]) for ch in "AB"]
        assert b-a == pytest.approx(250e-6, abs=1e-12)
    assert {0, 1} == {int(path.rsplit("/", 1)[1]) for path in rig.trace if "/adcclip/" in path}
    adapter.close()
    assert json.loads((tmp_path/"restoration.json").read_text())["settings_restored_and_outputs_inhibited"]
    assert not rig.laser.emission and not rig.laser.armed
    assert all(unit.source == "OFF" for unit in rig.units.values())


@pytest.mark.parametrize("fault", ["cancel", "engine", "unsupported_speed", "count"])
def test_dual_abort_retains_both_native_streams_and_restores(tmp_path, fault):
    rig, adapter, events = dual_fixture(tmp_path, preliminary=True, fault=fault)
    block = adapter.prepare_blocks(adapter.plan, events, rig.cancel)[0]
    with pytest.raises((RuntimeError, InterruptedError)):
        adapter.capture_block(block, rig.cancel)
    partial = adapter.partial_blocks[0]
    if fault != "unsupported_speed":
        assert {"detectors", "detectors_3", "timing", "pump_events"} <= partial["labone"]["modules"].keys()
        assert all(item["partial_salvage"] for item in partial["labone"]["read_phase_observations"])
    else:
        assert "emission_enable" not in rig.trace
    adapter.close()
    assert json.loads((tmp_path/"restoration.json").read_text())["settings_restored_and_outputs_inhibited"]


def test_dual_full_sequence_cannot_split_to_fit_memory(tmp_path):
    rig, adapter, events = dual_fixture(tmp_path, host_capacity_bytes=1024)
    with pytest.raises(AcquisitionCapacityError, match="host bytes"):
        adapter.prepare_blocks(adapter.plan, events, rig.cancel)
    assert not any(module.executed for module in rig.hf.modules)
    assert not rig.laser.emission
    adapter.close()


def test_dual_plan_is_frozen_without_aliasing_caller_configuration(tmp_path):
    plan = build_dual_detector_phase_scan_plan()
    adapter = DualDetectorPhaseScanAcquirer(plan)
    plan.hf2_selection["reference"]["order"] = 99
    assert adapter.plan.hf2_selection["reference"]["order"] != 99
    with pytest.raises(ValueError, match="frozen"):
        adapter.resolve_plan(plan)


def test_dual_unverified_capabilities_cannot_open_instruments(tmp_path):
    requested = build_dual_detector_phase_scan_plan()
    adapter = DualDetectorPhaseScanAcquirer(requested)
    adapter.authorize(True)
    with pytest.raises(ValueError, match="capabilities"):
        adapter.prepare(requested.settings, SimpleNamespace(path=tmp_path), Event())
    assert adapter.qcl is adapter.hf is None and not adapter.units
