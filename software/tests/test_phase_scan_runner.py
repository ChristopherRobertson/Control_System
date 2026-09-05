"""Hardware-free finite-block lifecycle, retention, and scientific reconstruction."""
from dataclasses import replace
import json

import numpy as np
import pytest

from control_app.workflows.phase_scan import PhaseScanSettings, build_phase_scan_plan
from control_app.workflows.phase_scan_data import ScanStore, Spectrum, load_native
from control_app.workflows.phase_scan_runner import PhaseScanRunner


def plan():
    return build_phase_scan_plan(PhaseScanSettings(
        start_wavenumber_cm1=2000, stop_wavenumber_cm1=1998,
        scan_speed_cm1_s=1000, phase_delay_us=500))


def spectrum(event, background=False):
    wn = np.array([2000., 1999., 1998.])
    age = (event.phase_delay_us or 0) * 1e-6 + np.array([0., .001, .002])
    absorption = np.zeros(3) if background else (2000 - wn) * .01 + age * 20
    return Spectrum(wn, 2 * 10 ** -absorption, np.ones(3), 10 + age,
                    10 if event.pump_enabled else None,
                    {"optical_valid": True, "wavenumber_basis": "measured",
                     "pump_time_basis": "measured"})


class Acquirer:
    def __init__(self, *, background=False, capacity=10000, fault=None, stage="capture",
                 close_fault=False, mutate=None, readback=None):
        self.background, self.capacity, self.fault = background, capacity, fault
        self.stage, self.close_fault, self.mutate = stage, close_fault, mutate
        self.readback = readback or {"current_ma": 750, "rate": 20000}
        self.calls, self.partial_blocks = [], []
        self.closed = False

    def prepare(self, settings, store, cancel):
        self.calls.append("prepare")
        if self.stage == "prepare" and self.fault:
            raise self.fault
        return self.readback

    def prepare_blocks(self, plan, events, cancel):
        self.calls.append("preflight")
        if self.stage == "preflight" and self.fault:
            raise self.fault
        return [events[i:i + self.capacity] for i in range(0, len(events), self.capacity)]

    def capture_block(self, block, cancel):
        self.calls.append("capture")
        native = {"ticks": np.array([2**60, 2**60 + 1], dtype=np.uint64)}
        if self.fault:
            self.partial_blocks.append(native)
            raise self.fault
        records = [(event, spectrum(event, self.background)) for event in block]
        if self.mutate:
            records = self.mutate(records, cancel)
        return native, records

    def close(self):
        self.calls.append("close")
        self.closed = True
        if self.close_fault:
            raise RuntimeError("stop failed")


def background_runner(tmp_path):
    runner = PhaseScanRunner(lambda: Acquirer(background=True))
    runner.execute("background", tmp_path, plan())
    return runner


def test_preflight_all_blocks_then_acquire_then_close_then_single_save(tmp_path, monkeypatch):
    runner = background_runner(tmp_path)
    acquirer = Acquirer(capacity=4)
    runner.acquirer_factory = lambda: acquirer
    original = ScanStore.save_block
    saves = []

    def save(store, records, **kwargs):
        assert acquirer.closed
        assert acquirer.calls.count("capture") == (plan().total_scans + 3) // 4
        saves.append(len(records))
        return original(store, records, **kwargs)

    monkeypatch.setattr(ScanStore, "save_block", save)
    result = runner.execute("run", tmp_path, plan(), on_scan=lambda *args: assert_closed(acquirer))
    assert acquirer.calls[:2] == ["prepare", "preflight"]
    assert acquirer.calls[-1] == "close"
    assert acquirer.calls.count("close") == 1
    assert saves == [plan().total_scans]
    paths = list((result["path"] / "raw").glob("*.npz"))
    assert len(paths) == 1
    payload = load_native(paths[0])
    assert len(payload["records"]) == plan().total_scans
    assert payload["native"]["blocks"][0]["ticks"].dtype == np.uint64
    actual = result["reconstruction"]
    np.testing.assert_allclose(actual["time_s"][[0, -1]], [-.001, .005])
    # Ordinary sample/reference/background normalization retains its sign and scale.
    expected = (2000 - actual["wavenumber_cm1"])[None, :] * .01 + actual["time_s"][:, None] * 20
    valid = np.isfinite(actual["absorbance"])
    np.testing.assert_allclose(actual["absorbance"][valid], expected[valid], atol=1e-12)
    assert json.loads((result["path"] / "result.json").read_text())["status"] == "COMPLETE"


def assert_closed(acquirer):
    assert acquirer.closed


@pytest.mark.parametrize("stage", ["prepare", "preflight", "capture"])
@pytest.mark.parametrize("fault,status", [(RuntimeError("fault"), "INCOMPLETE"),
                                         (InterruptedError("aborted"), "ABORTED"),
                                         (KeyboardInterrupt(), "ABORTED")])
def test_every_fault_closes_once_and_preserves_available_data(tmp_path, stage, fault, status):
    acquirer = Acquirer(background=True, stage=stage, fault=fault)
    runner = PhaseScanRunner(lambda: acquirer)
    with pytest.raises(RuntimeError):
        runner.execute("background", tmp_path, plan())
    assert acquirer.calls.count("close") == 1
    assert acquirer.calls.count("capture") == (1 if stage == "capture" else 0)
    assert runner.background is None
    result = json.loads(next(tmp_path.rglob("result.json")).read_text())
    assert result["status"] == status
    if isinstance(fault, KeyboardInterrupt):
        assert "interrupted by operator" in result["error"]
    payload = load_native(next(tmp_path.rglob("acquisition.npz")))
    assert len(payload["native"]["blocks"]) == (1 if stage == "capture" else 0)
    assert runner._lock.acquire(blocking=False)
    runner._lock.release()


def test_cancel_after_completed_capture_retains_record(tmp_path):
    def cancel_after(records, cancel):
        cancel.set()
        return records
    acquirer = Acquirer(background=True, mutate=cancel_after)
    runner = PhaseScanRunner(lambda: acquirer)
    with pytest.raises(RuntimeError, match="aborted"):
        runner.execute("background", tmp_path, plan())
    assert acquirer.calls.count("close") == 1
    assert len(load_native(next(tmp_path.rglob("acquisition.npz")))["records"]) == 1
    assert runner.background is None


def test_safe_state_failure_never_enables_background(tmp_path):
    acquirer = Acquirer(background=True, close_fault=True)
    runner = PhaseScanRunner(lambda: acquirer)
    with pytest.raises(RuntimeError, match="Safe shutdown failed"):
        runner.execute("background", tmp_path, plan())
    assert acquirer.calls.count("close") == 1
    assert runner.background is None
    assert json.loads(next(tmp_path.rglob("result.json")).read_text())["status"] == "FAILED_SAFE_STATE_UNVERIFIED"


@pytest.mark.parametrize("mutation", [lambda records: records[:-1],
                                       lambda records: records + records[-1:],
                                       lambda records: list(reversed(records))])
def test_wrong_record_count_or_order_preserves_native_without_reacquisition(tmp_path, mutation):
    runner = background_runner(tmp_path)
    acquirer = Acquirer(mutate=lambda records, cancel: mutation(records))
    runner.acquirer_factory = lambda: acquirer
    with pytest.raises(RuntimeError, match="Acquisition integrity"):
        runner.execute("run", tmp_path, plan())
    assert acquirer.calls.count("capture") == 1
    assert acquirer.calls.count("close") == 1
    results = [json.loads(p.read_text()) for p in tmp_path.rglob("result.json")]
    assert {result["status"] for result in results} == {"COMPLETE", "INCOMPLETE"}


def test_background_compatibility_and_readback_gate(tmp_path):
    runner = background_runner(tmp_path)
    assert runner.background_matches(replace(plan().settings, phase_delay_us=250, repetitions=2))
    assert not runner.background_matches(replace(plan().settings, mircat_internal_repetition_rate_hz=2_001_000))
    assert not runner.background_matches(replace(plan().settings, mircat_internal_pulse_width_ns=140))
    acquirer = Acquirer(readback={"current_ma": 999, "rate": 20000})
    runner.acquirer_factory = lambda: acquirer
    with pytest.raises(RuntimeError, match="Instrument settings changed"):
        runner.execute("run", tmp_path, plan())
    assert runner.background is None
    assert "capture" not in acquirer.calls


def test_later_block_fault_retains_completed_and_partial_blocks(tmp_path):
    runner = background_runner(tmp_path)
    acquirer = Acquirer(capacity=4)
    capture = acquirer.capture_block

    def second_fails(block, cancel):
        if "capture" in acquirer.calls:
            acquirer.fault = RuntimeError("later block failed")
        return capture(block, cancel)

    acquirer.capture_block = second_fails
    runner.acquirer_factory = lambda: acquirer
    with pytest.raises(RuntimeError, match="later block failed"):
        runner.execute("run", tmp_path, plan())
    assert acquirer.calls.count("capture") == 2
    assert acquirer.calls.count("close") == 1
    raw = next(p for p in tmp_path.rglob("acquisition.npz") if p.parents[1].name.endswith("_run"))
    payload = load_native(raw)
    assert len(payload["records"]) == 4
    assert len(payload["native"]["blocks"]) == 2


def test_processing_failure_retains_consolidated_raw_without_reopening(tmp_path):
    runner = background_runner(tmp_path)
    acquirer = Acquirer()
    runner.acquirer_factory = lambda: acquirer

    def fails(*args):
        raise RuntimeError("display failed")

    with pytest.raises(RuntimeError, match="display failed"):
        runner.execute("run", tmp_path, plan(), on_scan=fails)
    assert acquirer.calls.count("capture") == 1
    assert acquirer.calls.count("close") == 1
    raw = next(p for p in tmp_path.rglob("acquisition.npz") if p.parents[1].name.endswith("_run"))
    assert len(load_native(raw)["records"]) == plan().total_scans
