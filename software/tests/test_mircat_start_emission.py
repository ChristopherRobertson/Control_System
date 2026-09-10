"""Canonical emission API checks real readbacks; only an in-memory SDK is used."""
from contextlib import contextmanager
from ctypes import POINTER, c_bool, c_uint16, cast
from inspect import signature
from io import StringIO

import pytest

from control_app.devices.mircat_service import (
    MircatCommandError, MircatSafetyError, MircatService, RET_COMM_ERROR,
    RET_EMISSION_ALREADY_ON, RET_EMISSION_ON_FAILURE, RET_LASER_NOT_TUNED,
    RET_SUCCESS,
)
from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError


class FakeSDK:
    def __init__(self):
        self.calls = []
        self.values = {
            "MIRcatSDK_IsConnectedToLaser": True,
            "MIRcatSDK_IsInterlockedStatusSet": True,
            "MIRcatSDK_IsKeySwitchStatusSet": True,
            "MIRcatSDK_IsLaserArmed": True,
            "MIRcatSDK_AreTECsAtSetTemperature": True,
            "MIRcatSDK_GetSystemErrorWord": 0,
        }
        self.statuses = {}

    def __getattr__(self, name):
        if name not in self.values and name != "MIRcatSDK_TurnEmissionOn":
            raise AttributeError(name)
        def call(*arguments):
            self.calls.append(name)
            if arguments:
                kind = c_uint16 if name == "MIRcatSDK_GetSystemErrorWord" else c_bool
                cast(arguments[0], POINTER(kind)).contents.value = self.values[name]
            return self.statuses.get(name, RET_SUCCESS)
        return call


@contextmanager
def owned_service(tmp_path):
    coordinator = HardwareCoordinator(tmp_path / "instrument.lock")
    service = MircatService({}, command_log=StringIO())
    service._sdk = FakeSDK()
    token = coordinator.acquire("steady_state_slow_scan:single")
    try:
        with coordinator.scope(token):
            yield service, service._sdk, coordinator, token
    finally:
        coordinator.release(token, safe_verified=True, preservation_verified=True)


@pytest.mark.parametrize("status", (RET_SUCCESS, RET_EMISSION_ALREADY_ON))
def test_start_emission_has_no_approval_argument_and_checks_physical_state(tmp_path, status):
    assert tuple(signature(MircatService.start_emission).parameters) == ("self",)
    with owned_service(tmp_path) as (service, sdk, coordinator, token):
        sdk.statuses["MIRcatSDK_TurnEmissionOn"] = status
        assert service.start_emission() is None
        assert sdk.calls == [*sdk.values, "MIRcatSDK_TurnEmissionOn"]
        assert service.last_return_code == status
        assert "MIRcatSDK_TurnEmissionOn" in service.command_log.getvalue()
        coordinator.assert_owner(token)  # Emission start never releases ownership.


@pytest.mark.parametrize(("readback", "value", "message"), (
    ("MIRcatSDK_IsConnectedToLaser", False, "not connected"),
    ("MIRcatSDK_IsInterlockedStatusSet", False, "interlock is open"),
    ("MIRcatSDK_IsKeySwitchStatusSet", False, "key switch"),
    ("MIRcatSDK_IsLaserArmed", False, "not armed"),
    ("MIRcatSDK_AreTECsAtSetTemperature", False, "TECs are not ready"),
    ("MIRcatSDK_GetSystemErrorWord", 16, "system error word 16"),
))
def test_physical_fault_never_reaches_emission_command(tmp_path, readback, value, message):
    with owned_service(tmp_path) as (service, sdk, coordinator, token):
        sdk.values[readback] = value
        with pytest.raises(MircatSafetyError, match=message):
            service.start_emission()
        assert "MIRcatSDK_TurnEmissionOn" not in sdk.calls
        coordinator.assert_owner(token)


@pytest.mark.parametrize("command", ("MIRcatSDK_IsKeySwitchStatusSet", "MIRcatSDK_GetSystemErrorWord"))
def test_failed_readback_preserves_sdk_error_and_never_starts_emission(tmp_path, command):
    with owned_service(tmp_path) as (service, sdk, _, _token):
        sdk.statuses[command] = RET_COMM_ERROR
        with pytest.raises(MircatCommandError, match=command + " returned 100.*COMM_ERROR"):
            service.start_emission()
        assert "MIRcatSDK_TurnEmissionOn" not in sdk.calls


@pytest.mark.parametrize("status", (RET_EMISSION_ON_FAILURE, RET_LASER_NOT_TUNED, RET_COMM_ERROR))
def test_sdk_emission_error_is_visible_after_successful_readbacks(tmp_path, status):
    with owned_service(tmp_path) as (service, sdk, _, _token):
        sdk.statuses["MIRcatSDK_TurnEmissionOn"] = status
        with pytest.raises(MircatCommandError, match=f"MIRcatSDK_TurnEmissionOn returned {status}"):
            service.start_emission()
        assert sdk.calls[-1] == "MIRcatSDK_TurnEmissionOn"
        assert service.last_return_code == status


def test_start_rejects_unowned_or_stale_service_before_any_sdk_readback(tmp_path):
    service = MircatService({})
    service._sdk = sdk = FakeSDK()
    with pytest.raises(OwnershipError):
        service.start_emission()
    assert sdk.calls == []
    coordinator = HardwareCoordinator(tmp_path / "instrument.lock")
    first = coordinator.acquire("steady_state_slow_scan:single")
    with coordinator.scope(first):
        service.start_emission()
    coordinator.release(first, safe_verified=True, preservation_verified=True)
    sdk.calls.clear()
    second = coordinator.acquire("steady_state_slow_scan:dual")
    try:
        with coordinator.scope(second), pytest.raises(OwnershipError, match="stale"):
            service.start_emission()
        assert sdk.calls == []
        coordinator.assert_owner(second)
    finally:
        coordinator.release(second, safe_verified=True, preservation_verified=True)


def test_legacy_approval_signature_and_command_sequence_are_unchanged():
    service = MircatService({})
    service._sdk = sdk = FakeSDK()
    with pytest.raises(TypeError):
        service.turn_emission_on()
    with pytest.raises(MircatSafetyError, match="approved_laser_safety_condition=True"):
        service.turn_emission_on(approved_laser_safety_condition=False)
    assert sdk.calls == []
    # Legacy callers retain their previous preflight and exact SDK sequence.
    # In particular, the compatibility method adds no new readback operations.
    sdk.values = {}
    service.turn_emission_on(approved_laser_safety_condition=True)
    sdk.statuses["MIRcatSDK_TurnEmissionOn"] = RET_EMISSION_ALREADY_ON
    service.turn_emission_on(approved_laser_safety_condition=True)
    assert sdk.calls == ["MIRcatSDK_TurnEmissionOn"] * 2
    sdk.statuses["MIRcatSDK_TurnEmissionOn"] = RET_EMISSION_ON_FAILURE
    with pytest.raises(MircatCommandError, match="EMISSION_ON_FAILURE"):
        service.turn_emission_on(approved_laser_safety_condition=True)
