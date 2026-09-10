"""Stock-style incremental DAQ reads with bounded host retention; no hardware."""
from copy import deepcopy

import numpy as np
import pytest

from control_app.workflows.phase_scan import PhaseScanEvent
from control_app.workflows.phase_scan_data import load_native, save_native
from control_app.workflows.phase_scan_labone import (
    AcquisitionCapacityError, AcquisitionIntegrityError, FinitePhaseDAQ, MAX_EVENTS_PER_BLOCK,
)


class Module:
    def __init__(self, hf):
        self.hf, self.settings, self.paths, self.queue = hf, {}, [], []
        self.executed = self.cleared = self.stopped = False
        self.finish_error = False
        self.reads = 0

    def set(self, path, value): self.settings[path] = value
    def subscribe(self, path): self.paths.append(path)
    def getString(self, path): return self.settings[path]
    def getInt(self, path): return 4 if path == "buffercount" else self.settings[path]
    def getDouble(self, path):
        if path == "buffersize": return .1
        if path == "duration":
            override = getattr(self.hf, "duration_after_execute" if self.executed else "duration_before_execute", None)
            return override if override is not None else self.settings["grid/cols"] / self.rate
        return self.settings[path]
    @property
    def rate(self):
        return max(self.hf.rates[int(path.split("/demods/")[1].split("/")[0])] for path in self.paths)
    def execute(self):
        assert self.settings["triggernode"] == f"/{self.hf.device_id}/demods/2/sample.dio"
        assert all(path.endswith((".x", ".y", ".dio")) for path in self.paths)
        self.executed = True
    def finished(self): return False
    def progress(self): return [0.]  # Readiness must come from host records instead.
    def read(self, flat):
        assert flat and self.executed
        self.reads += 1
        result = self.queue.pop(0) if self.queue else {}
        if isinstance(result, Exception): raise result
        return result
    def finish(self):
        self.stopped = True
        if self.finish_error: raise RuntimeError("finish transport failure")
    def clear(self): self.cleared = True


class HF:
    device_id = "devtest"
    rates = {0: 2000., 2: 8000.}
    origin = 2**60
    def __init__(self): self.modules = []
    def get_clockbase(self): return 8_000_000.
    def _get_node(self, kind, path): return self.rates[int(path.split("/demods/")[1].split("/")[0])]
    def create_daq_module(self):
        module = Module(self)
        self.modules.append(module)
        return module


def setup(count=2, **kwargs):
    hf = HF()
    events = [PhaseScanEvent(i, 1, None, False, None) for i in range(count)]
    daq = FinitePhaseDAQ(hf, events=events, duration_s=.0026, pretrigger_s=.0005, **kwargs)
    return hf, daq


def burst(module, frame):
    """One immutable SDK-owned response, including fields unknown to the decoder."""
    count = module.settings["grid/cols"]
    relative = module.settings["delay"] + np.arange(count)/module.rate
    base = module.hf.origin + round((1.+.3*frame)*module.hf.get_clockbase())
    ticks = np.array([base+round(t*module.hf.get_clockbase()) for t in relative], dtype=np.uint64)
    result = {}
    for path in module.paths:
        values = np.ones(count, dtype=np.float64)
        if path.endswith(".dio"):
            values = np.zeros(count, dtype=np.uint32)
            values[(relative >= 0) & (relative < .002)] |= np.uint32(1 << 21)
        result[path] = [{"timestamp": ticks[None, :].copy(), "value": values[None, :],
                         "header": {"future_field": np.array([2**40+frame], dtype=np.uint64),
                                    "nested": {"name": "original", "unknown": [1, "value"]}}}]
    return result


def queue_frame(hf, frame):
    for module in hf.modules[:2]:
        module.queue.append(burst(module, frame))


def test_default_stock_api_retains_incremental_chunks_native_dtypes_and_unknown_headers(tmp_path):
    hf, daq = setup()
    assert daq.incremental
    assert not daq.capacity["labone_resident_capacity_guaranteed"]
    assert daq.capacity["host_allocated_bytes"] == daq.capacity["required_bytes"]
    assert all(module.settings["historylength"] == module.settings["count"] for module in hf.modules)
    assert all(module.settings["grid/mode"] == 4 and module.settings["flags"] == 0xC for module in hf.modules)
    assert daq.raw["digital_trigger_source"] == "/devtest/demods/2/sample.dio"
    assert hf.modules[1].paths == hf.modules[2].paths == ["/devtest/demods/2/sample.dio"]
    daq.arm()
    assert not daq.expected_records_received()
    original = burst(hf.modules[0], 0)
    hf.modules[0].queue.append(original)
    hf.modules[1].queue.append(burst(hf.modules[1], 0))
    daq.drain()
    assert not daq.expected_records_received()
    original[hf.modules[0].paths[0]][0]["value"][:] = 999.
    original[hf.modules[0].paths[0]][0]["header"]["future_field"][:] = 0
    queue_frame(hf, 1)
    daq.drain()
    assert daq.expected_records_received()
    daq.mark_sequence_complete()
    result = daq.records()
    assert len(result) == 2
    assert all(native["pump_event_tick"] is None for _, native in result)
    raw = daq.read()
    assert len(raw["read_chunks"]) == 4
    assert raw["host_native_bytes_used"] <= daq.capacity["host_allocated_bytes"]
    saved = raw["modules"]["detectors"][hf.modules[0].paths[0]][0]
    np.testing.assert_array_equal(saved["value"], 1.)
    assert saved["timestamp"].dtype == np.uint64 and saved["timestamp"].shape == (1, 7)
    assert int(saved["header"]["future_field"][0]) == 2**40
    assert saved["header"]["nested"] == {"name": "original", "unknown": [1, "value"]}
    path = tmp_path / "native.npz"
    save_native(path, raw)
    restored = load_native(path)
    assert restored["read_chunks"][0]["payload"][hf.modules[0].paths[0]][0]["timestamp"].dtype == np.uint64


def test_final_drain_collects_tail_without_progress_state_or_explicit_prior_drain():
    hf, daq = setup(1)
    queue_frame(hf, 0)
    daq.arm()
    daq.mark_sequence_complete()
    assert len(daq.records()) == 1
    assert daq.expected_records_received()


def test_duplicate_incremental_response_is_preserved_and_rejected():
    hf, daq = setup(2)
    response = burst(hf.modules[0], 0)
    hf.modules[0].queue.extend([response, deepcopy(response)])
    daq.arm()
    daq.drain()
    with pytest.raises(AcquisitionIntegrityError, match="Duplicated"):
        daq.drain()
    assert len(daq.raw["read_chunks"]) == 2
    assert len(daq.raw["modules"]["detectors"][hf.modules[0].paths[0]]) == 2
    daq.mark_sequence_complete()
    daq.read(partial=True)
    with pytest.raises(AcquisitionIntegrityError, match="retained read/integrity"):
        daq.records()


def test_guard_extra_record_is_preserved_and_cannot_complete():
    hf, daq = setup(1)
    queue_frame(hf, 0)
    queue_frame(hf, 1)
    daq.arm(); daq.drain()
    with pytest.raises(AcquisitionIntegrityError, match="guard or duplicate"):
        daq.drain()
    assert len(daq.raw["modules"]["timing"][hf.modules[1].paths[0]]) == 2


def test_missing_records_are_not_invented_from_module_progress():
    hf, daq = setup(2)
    queue_frame(hf, 0)
    daq.arm(); daq.drain(); daq.mark_sequence_complete()
    assert not daq.expected_records_received()
    with pytest.raises(AcquisitionIntegrityError, match="Exact record count"):
        daq.records()
    assert len(daq.raw["read_chunks"]) == 2


@pytest.mark.parametrize("fault", ["dataloss", "sampleloss", "overflow", "dropped_samples", "clipped", "nonmonotonic", "gap", "nan"])
def test_bad_native_record_rejects_completion_but_retains_other_module(fault):
    hf, daq = setup(1)
    response = burst(hf.modules[0], 0)
    record = response[hf.modules[0].paths[0]][0]
    if fault == "nonmonotonic": record["timestamp"][0, 2] = record["timestamp"][0, 1]
    elif fault == "gap": record["timestamp"][0, 3:] += 10000
    elif fault == "nan": record["value"][0, 2] = np.nan
    else: record["header"][fault] = 1
    hf.modules[0].queue.append(response)
    hf.modules[1].queue.append(burst(hf.modules[1], 0))
    daq.arm()
    with pytest.raises(AcquisitionIntegrityError): daq.drain()
    assert set(daq.raw["modules"]) == {"detectors", "timing"}
    assert len(daq.raw["read_chunks"]) == 2
    assert daq.raw["integrity_errors"]


def test_sdk_read_exception_salvages_other_modules_and_cannot_later_be_accepted():
    hf, daq = setup(1)
    hf.modules[0].queue.append(EOFError("sample loss"))
    hf.modules[1].queue.append(burst(hf.modules[1], 0))
    daq.arm()
    with pytest.raises(AcquisitionIntegrityError, match="sample loss"):
        daq.drain()
    assert "timing" in daq.raw["modules"]
    hf.modules[0].queue.append(burst(hf.modules[0], 0))
    daq.mark_sequence_complete()
    daq.read(partial=True)
    assert len(daq.raw["read_chunks"]) == 2
    with pytest.raises(AcquisitionIntegrityError, match="retained read/integrity"):
        daq.records()


def test_native_header_loss_bit_rejects_record_and_retains_all_responses():
    hf, daq = setup(1)
    response = burst(hf.modules[0], 0)
    for record in response.values():
        record[0]["header"]["flags"] = np.array([0x739 | 0x4], dtype=np.uint32)
    hf.modules[0].queue.append(response)
    hf.modules[1].queue.append(burst(hf.modules[1], 0))
    daq.arm()
    with pytest.raises(AcquisitionIntegrityError, match="native header.flags"):
        daq.drain()
    assert len(daq.raw["read_chunks"]) == 2
    retained = daq.raw["modules"]["detectors"][hf.modules[0].paths[0]][0]
    np.testing.assert_array_equal(retained["header"]["flags"], [0x73D])
    assert not daq.expected_records_received()
    daq.mark_sequence_complete()
    with pytest.raises(AcquisitionIntegrityError, match="retained read/integrity"):
        daq.records()


@pytest.mark.parametrize("invalid_word", [-1., .5, 2.**32, np.nan, np.inf])
def test_invalid_float_dio_words_are_retained_without_cast_or_acceptance(invalid_word):
    hf, daq = setup(1)
    hf.modules[0].queue.append(burst(hf.modules[0], 0))
    response = burst(hf.modules[1], 0)
    record = response[hf.modules[1].paths[0]][0]
    record["value"] = record["value"].astype(np.float64)
    record["value"][0, 2] = invalid_word
    hf.modules[1].queue.append(response)
    daq.arm()
    with pytest.raises(AcquisitionIntegrityError):
        daq.drain()
    assert len(daq.raw["read_chunks"]) == 2
    retained = daq.raw["modules"]["timing"][hf.modules[1].paths[0]][0]
    assert retained["value"].dtype == np.float64
    np.testing.assert_array_equal(retained["value"], record["value"])
    assert not daq.expected_records_received()


def test_real_native_flags_and_float_uint32_endpoints_are_accepted_unchanged():
    hf, daq = setup(1)
    queue_frame(hf, 0)
    for module in hf.modules[:2]:
        for records in module.queue[0].values():
            records[0]["header"].update(flags=np.array([0x739], dtype=np.uint32),
                                        moduleflags=np.array([0], dtype=np.uint32),
                                        status=np.array([1], dtype=np.uint32))
    record = hf.modules[1].queue[0][hf.modules[1].paths[0]][0]
    record["value"] = record["value"].astype(np.float64)
    record["value"][0, :2] = [0., float(np.iinfo(np.uint32).max)]
    daq.arm(); daq.drain()
    assert daq.expected_records_received()
    retained = daq.raw["modules"]["timing"][hf.modules[1].paths[0]][0]
    np.testing.assert_array_equal(retained["value"], record["value"])


def test_host_capacity_and_event_limit_fail_before_any_module_arms():
    hf = HF()
    events = [PhaseScanEvent(0, 1, None, False, None)]
    with pytest.raises(AcquisitionCapacityError, match="configured limit"):
        FinitePhaseDAQ(hf, events=events, duration_s=.0026, pretrigger_s=.0005, host_capacity_bytes=1)
    assert all(not module.executed and module.cleared for module in hf.modules)
    with pytest.raises(AcquisitionCapacityError, match="1 to 16"):
        FinitePhaseDAQ(hf, events=events*(MAX_EVENTS_PER_BLOCK+1), duration_s=.0026, pretrigger_s=.0005)


def test_real_host_allocation_failure_cleans_modules_before_arm(monkeypatch):
    from control_app.workflows import phase_scan_labone
    hf = HF()
    def unavailable(*args, **kwargs):
        raise MemoryError("host allocation unavailable")
    monkeypatch.setattr(phase_scan_labone.np, "empty", unavailable)
    with pytest.raises(AcquisitionCapacityError, match="Cannot allocate"):
        FinitePhaseDAQ(hf, events=[PhaseScanEvent(0, 1, None, False, None)],
                       duration_s=.0026, pretrigger_s=.0005)
    assert all(not module.executed and module.cleared for module in hf.modules)


def test_exact_grid_duration_can_be_stale_before_execute_but_must_verify_before_arm_returns():
    hf = HF()
    hf.duration_before_execute = .01
    daq = FinitePhaseDAQ(hf, events=[PhaseScanEvent(0, 1, None, False, None)],
                         duration_s=.003, pretrigger_s=.0002)
    assert all(item["readback"]["duration_before_execute_s"] == .01 for item in daq.modules)
    assert not any(item["readback"]["duration_verified_after_execute"] for item in daq.modules)
    assert all(item["estimate"]["duration_s"] == item["readback"]["grid/cols"] / item["module"].rate for item in daq.modules)
    daq.arm()
    assert all(item["readback"]["duration_verified_after_execute"] for item in daq.modules)
    assert all(item["readback"]["duration"] == item["readback"]["grid/cols"] / item["module"].rate for item in daq.modules)
    daq.close()


def test_wrong_live_duration_fails_arm_closes_all_modules_and_preserves_observations():
    hf = HF()
    hf.duration_before_execute = hf.duration_after_execute = .01
    daq = FinitePhaseDAQ(hf, events=[PhaseScanEvent(0, 1, None, False, None)],
                         duration_s=.003, pretrigger_s=.0002, live_readback_timeout_s=.001)
    with pytest.raises(AcquisitionCapacityError, match="before external triggers"):
        daq.arm()
    assert all(module.executed and module.stopped and module.cleared for module in hf.modules)
    partial = daq.read(partial=True)
    assert partial["arm_errors"] and partial["live_grid_readback_observations"]
    assert not any(item["readback"]["duration_verified_after_execute"] for item in daq.modules)


def test_grid_resizing_during_execute_is_rejected_before_external_triggers():
    hf, daq = setup(1)
    execute = hf.modules[0].execute
    def changed_size():
        execute()
        hf.modules[0].settings["grid/cols"] += 1
    hf.modules[0].execute = changed_size
    with pytest.raises(AcquisitionCapacityError, match="live grid/cols"):
        daq.arm()
    assert daq.closed
    assert all(module.cleared for module in hf.modules)


def test_oversized_unknown_header_is_retained_but_rejects_planned_capacity():
    hf, daq = setup(1)
    response = burst(hf.modules[0], 0)
    response[hf.modules[0].paths[0]][0]["header"]["unexpected_large_field"] = np.ones(daq.capacity["required_bytes"]+1, dtype=np.uint8)
    hf.modules[0].queue.append(response)
    daq.arm()
    with pytest.raises(AcquisitionIntegrityError, match="exceeded bounded host"):
        daq.drain()
    retained = daq.raw["read_chunks"][0]["payload"][hf.modules[0].paths[0]][0]
    np.testing.assert_array_equal(retained["header"]["unexpected_large_field"], 1)


def test_cleanup_attempts_every_finish_and_clear_even_after_failure():
    hf, daq = setup(1)
    hf.modules[0].finish_error = True
    daq.close()
    assert all(module.stopped and module.cleared for module in hf.modules)
    assert daq.raw["cleanup_errors"] == ["detectors finish: finish transport failure"]
    daq.close()
    assert len(daq.raw["cleanup_errors"]) == 1
