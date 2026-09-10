"""Read-only health semantics using injected transports and isolated lock files."""
from datetime import UTC, datetime
import json

import numpy as np
import pytest

from control_app.devices.hf2li_service import HF2LIConnectionError, HF2LIService
from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError, require_hardware_owner


class HealthServer:
    """Expose only reads: accidental mutation/acquisition calls fail the test."""
    def __init__(self):
        self.values = {
            "/dev123/plls/0/enable": 1,
            "/dev123/plls/0/locked": 1,
            "/dev123/status/flags/plllock": 0,
            "/dev123/status/flags/dcmlock": 0,
            "/dev123/system/extclk": 1,
            "/dev123/status/flags/adcclip/0": 0,
            "/dev123/status/flags/adcclip/1": 0,
        }
        self.reads = []
        self.after_read = None

    def getInt(self, path):
        self.reads.append(path)
        value = self.values[path]
        if self.after_read is not None:
            self.after_read()
        if isinstance(value, Exception):
            raise value
        return value


@pytest.fixture
def connected():
    service = HF2LIService({})
    server = HealthServer()
    service._server, service._device_id = server, "dev123"
    return service, server


def test_health_is_serializable_read_only_and_fresh(connected):
    service, server = connected
    before = datetime.now(UTC)
    result = service.read_acquisition_health()
    assert before <= datetime.fromisoformat(result["timestamp_utc"]) <= datetime.now(UTC)
    assert result["schema_version"] == "hf2li-acquisition-health/1"
    assert result["device_id"] == "dev123"
    assert result["reference_locked"] is True
    assert result["clock_locked"] is True
    assert result["external_clock_selected"] is True
    assert result["external_reference_locked"] is None
    assert result["clock_lock_basis"] == "internal_clock_generation_pll_and_digital_clock_manager"
    assert result["overload"] is False
    assert result["overload_scope"] == "selected_signal_input_adc_clipping"
    assert result["inputs"]["1"] == {"input_index": 1, "adc_clipped": False, "overload": False}
    assert result["read_errors"] == {}
    assert set(server.reads) == set(server.values) == set(result["nodes"])
    assert len(server.reads) == len(server.values)
    assert json.loads(json.dumps(result)) == result
    assert service._subscribed_paths == []

    server.values["/dev123/plls/0/locked"] = 0
    server.values["/dev123/status/flags/adcclip/1"] = 1
    later = service.read_acquisition_health()
    assert later["reference_locked"] is False
    assert later["overload"] is True
    assert result["overload"] is False
    assert len(server.reads) == 2 * len(server.values)


@pytest.mark.parametrize("pll,dcm,expected", [
    (0, 0, True), (0, 1, False), (1, 0, False), (1, 1, False),
    (0, OSError("unreadable"), None), (OSError("unreadable"), 1, False),
])
def test_clock_flags_use_documented_inverse_polarity(connected, pll, dcm, expected):
    service, server = connected
    server.values["/dev123/status/flags/plllock"] = pll
    server.values["/dev123/status/flags/dcmlock"] = dcm
    result = service.read_acquisition_health()
    assert result["clock_locked"] is expected
    assert result["external_reference_locked"] is None


@pytest.mark.parametrize("enabled,locked,expected", [
    (1, 0, False), (1, 1, True), (0, 1, None), (0, 0, None),
    (OSError("enable unreadable"), 1, None), (1, OSError("lock unreadable"), None),
])
def test_reference_lock_requires_enabled_selected_pll(connected, enabled, locked, expected):
    service, server = connected
    server.values["/dev123/plls/1/enable"] = enabled
    server.values["/dev123/plls/1/locked"] = locked
    result = service.read_acquisition_health(reference_pll=1, input_indices=(1,))
    assert result["reference_locked"] is expected
    assert result["reference"]["pll_index"] == 1
    assert set(result["inputs"]) == {"1"}
    assert "/dev123/plls/0/locked" not in server.reads
    assert "/dev123/status/flags/adcclip/0" not in server.reads


@pytest.mark.parametrize("first,second,expected", [
    (0, 0, False), (0, 1, True), (1, 0, True),
    (0, OSError("input missing"), None), (1, OSError("input missing"), True),
])
def test_aggregate_clipping_retains_each_input_and_partial_errors(connected, first, second, expected):
    service, server = connected
    server.values["/dev123/status/flags/adcclip/0"] = first
    server.values["/dev123/status/flags/adcclip/1"] = second
    result = service.read_acquisition_health()
    assert result["overload"] is expected
    if isinstance(second, Exception):
        assert result["inputs"]["1"]["adc_clipped"] is None
        assert "input missing" in result["read_errors"]["/dev123/status/flags/adcclip/1"]
        assert "/dev123/status/flags/adcclip/1" not in result["nodes"]


@pytest.mark.parametrize("invalid", [None, -1, 2, 0.5, "0", float("nan")])
def test_unavailable_or_malformed_values_never_become_healthy(connected, invalid):
    service, server = connected
    server.values = dict.fromkeys(server.values, invalid)
    result = service.read_acquisition_health()
    assert all(result[name] is None for name in (
        "reference_locked", "clock_locked", "external_clock_selected", "overload"))
    assert result["nodes"] == {}
    assert set(result["read_errors"]) == set(server.values)
    assert all("Expected binary integer" in error for error in result["read_errors"].values())


def test_missing_nodes_are_unknown_and_numpy_integers_return_python_bools(connected):
    service, server = connected
    server.values = {path: np.int64(value) for path, value in server.values.items()}
    result = service.read_acquisition_health(reference_pll=np.int64(0), input_indices=(np.int64(1),))
    assert result["reference_locked"] is True
    assert result["clock_locked"] is True
    assert result["overload"] is False
    json.dumps(result)
    server.values.clear()
    result = service.read_acquisition_health()
    assert result["reference_locked"] is result["clock_locked"] is result["overload"] is None
    assert len(result["read_errors"]) == 7


@pytest.mark.parametrize("kwargs", [
    {"reference_pll": -1}, {"reference_pll": 2}, {"reference_pll": True}, {"reference_pll": "0"},
    {"input_indices": ()}, {"input_indices": (0, 0)}, {"input_indices": (2,)},
    {"input_indices": (False,)}, {"input_indices": (0.5,)},
])
def test_invalid_selection_fails_before_transport_reads(connected, kwargs):
    service, server = connected
    with pytest.raises(ValueError):
        service.read_acquisition_health(**kwargs)
    assert server.reads == []


def test_connection_precondition_is_not_an_unknown_snapshot():
    with pytest.raises(HF2LIConnectionError):
        HF2LIService({}).read_acquisition_health()


def test_bound_session_allows_helper_use_but_rejects_expired_ownership_before_reads(connected, tmp_path):
    service, server = connected
    coordinator = HardwareCoordinator(tmp_path / "health.lock")
    token = coordinator.acquire("health-test")
    try:
        with coordinator.scope(token):
            require_hardware_owner(service)
            assert service.read_acquisition_health()["reference_locked"] is True
        # Bound sessions remain usable by acquisition helper threads which do
        # not inherit the constructor's contextvars, while their token is live.
        assert service.read_acquisition_health()["reference_locked"] is True
    finally:
        coordinator.release(token, safe_verified=True)
    server.reads.clear()
    with pytest.raises(OwnershipError):
        service.read_acquisition_health()
    assert server.reads == []
    replacement = coordinator.acquire("later-operation")
    try:
        with coordinator.scope(replacement), pytest.raises(OwnershipError):
            service.read_acquisition_health()
        assert server.reads == []
    finally:
        coordinator.release(replacement, safe_verified=True)


def test_transport_ownership_exception_is_not_downgraded_to_unknown(connected):
    service, server = connected
    server.values["/dev123/plls/0/enable"] = OwnershipError("expired session")
    with pytest.raises(OwnershipError, match="expired session"):
        service.read_acquisition_health()
    assert len(server.reads) == 1


def test_ownership_loss_between_reads_aborts_without_downgrading_to_unknown(connected, tmp_path):
    service, server = connected
    coordinator = HardwareCoordinator(tmp_path / "health.lock")
    token = coordinator.acquire("health-test")
    try:
        with coordinator.scope(token):
            require_hardware_owner(service)
            server.after_read = lambda: coordinator.release(token, safe_verified=True)
            with pytest.raises(OwnershipError):
                service.read_acquisition_health()
        assert len(server.reads) == 1
    finally:
        if coordinator.snapshot()["state"] == "owned":
            coordinator.release(token, safe_verified=True)
