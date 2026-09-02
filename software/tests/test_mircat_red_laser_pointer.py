from __future__ import annotations

from ctypes import POINTER, c_uint32, cast

from control_app.devices.mircat_service import (
    STATUS_MASK_RED_LASER_POINTER_ENABLED,
    STATUS_MASK_RED_LASER_POINTER_INSTALLED,
    MircatSafetyError,
    MircatService,
)
from control_app.ui.contracts import WorkflowCommand
from control_app.ui.widgets.mircat_widget import GLOBAL_CONTROL_KEYS, MIRCAT_WIDGET_SPEC
from control_app.workflows.mircat_widget_commands import MircatWidgetCommandHandler


class _FakeSdk:
    def __init__(self) -> None:
        self.status_mask = STATUS_MASK_RED_LASER_POINTER_INSTALLED
        self.requests: list[bool] = []
        self.deinitialize_calls = 0

    def MIRcatSDK_GetStatusMask(self, status_mask) -> int:  # noqa: N802 - vendor API
        cast(status_mask, POINTER(c_uint32)).contents.value = self.status_mask
        return 0

    def MIRcatSDK_EnableRedLaserPointer(self, enabled) -> int:  # noqa: N802 - vendor API
        requested = bool(enabled.value)
        self.requests.append(requested)
        if requested:
            self.status_mask |= STATUS_MASK_RED_LASER_POINTER_ENABLED
        else:
            self.status_mask &= ~STATUS_MASK_RED_LASER_POINTER_ENABLED
        return 0

    def MIRcatSDK_DeInitialize(self) -> int:  # noqa: N802 - vendor API
        self.deinitialize_calls += 1
        return 0


class _FakeState:
    def __init__(self, pointer_enabled: bool) -> None:
        self.pointer_enabled = pointer_enabled

    def to_dict(self) -> dict[str, bool]:
        return {
            "red_laser_pointer_installed": True,
            "red_laser_pointer_enabled": self.pointer_enabled,
        }


class _FakeService:
    def __init__(self) -> None:
        self.command_log = None
        self.pointer_enabled = False
        self.requests: list[tuple[bool, bool]] = []

    def set_red_laser_pointer_enabled(
        self,
        enabled: bool,
        *,
        approved_laser_safety_condition: bool = False,
    ) -> dict[str, bool]:
        self.requests.append((enabled, approved_laser_safety_condition))
        self.pointer_enabled = enabled
        return {"installed": True, "enabled": enabled}

    def read_state(self) -> _FakeState:
        return _FakeState(self.pointer_enabled)


def test_service_controls_pointer_and_requires_approval_for_on() -> None:
    service = MircatService({})
    sdk = _FakeSdk()
    service._sdk = sdk

    try:
        service.set_red_laser_pointer_enabled(True)
    except MircatSafetyError:
        pass
    else:
        raise AssertionError("Pointer-on should require explicit laser-safety approval")

    on_status = service.set_red_laser_pointer_enabled(
        True, approved_laser_safety_condition=True
    )
    off_status = service.set_red_laser_pointer_enabled(False)

    assert sdk.requests == [True, False]
    assert on_status == {"installed": True, "enabled": True}
    assert off_status == {"installed": True, "enabled": False}


def test_deinitialize_turns_off_an_enabled_pointer() -> None:
    service = MircatService({})
    sdk = _FakeSdk()
    service._sdk = sdk
    service._initialized = True
    sdk.status_mask |= STATUS_MASK_RED_LASER_POINTER_ENABLED

    service.deinitialize()

    assert sdk.requests == [False]
    assert sdk.deinitialize_calls == 1
    assert service._sdk is None


def test_mircat_tab_registers_explicit_pointer_on_and_off_controls() -> None:
    controls = {control.key: control for control in MIRCAT_WIDGET_SPEC.controls}

    assert "red_laser_pointer_on" in GLOBAL_CONTROL_KEYS
    assert "red_laser_pointer_off" in GLOBAL_CONTROL_KEYS
    assert controls["red_laser_pointer_on"].command == "mircat.red_laser_pointer_on"
    assert controls["red_laser_pointer_on"].safety_approval_required is True
    assert controls["red_laser_pointer_off"].command == "mircat.red_laser_pointer_off"


def test_widget_handler_routes_pointer_on_and_off(tmp_path, monkeypatch) -> None:
    from control_app.workflows import mircat_widget_commands

    monkeypatch.setattr(
        mircat_widget_commands, "output_log_root", lambda: tmp_path / "logs"
    )
    handler = MircatWidgetCommandHandler(operator="test")
    service = _FakeService()
    handler.service = service
    handler.initialized = True

    on_result = handler(
        WorkflowCommand(
            device_key="mircat",
            command="mircat.red_laser_pointer_on",
            safety_approval=True,
        )
    )
    off_result = handler(
        WorkflowCommand(
            device_key="mircat",
            command="mircat.red_laser_pointer_off",
        )
    )

    assert on_result.status == "complete"
    assert on_result.data["state"]["red_laser_pointer_enabled"] is True
    assert off_result.status == "complete"
    assert off_result.data["state"]["red_laser_pointer_enabled"] is False
    assert service.requests == [(True, True), (False, False)]
