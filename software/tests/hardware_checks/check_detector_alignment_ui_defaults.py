#!/usr/bin/env python3
"""Validate detector-alignment UI defaults, recipes, and HF2LI preset metadata."""

from __future__ import annotations

from _common import REPO_ROOT

import yaml

from control_app.ui.widgets.mircat_widget import (
    ALIGNMENT_CONTROL_KEYS,
    DIRECT_CONTROL_KEYS,
    GLOBAL_CONTROL_KEYS,
    MIRCAT_WIDGET_SPEC,
    SCAN_CONTROL_KEYS,
)
from control_app.workflows.mircat_detector_alignment import (
    ALIGNMENT_TIMING_RECIPE,
    DEFAULT_CURRENT_MA,
    DEFAULT_HF2LI_PRESET,
    DEFAULT_PULSE_RATE_HZ,
    DEFAULT_PULSE_WIDTH_NS,
    DEFAULT_USE_T660_TIMING,
    DEFAULT_WAVENUMBER_CM1,
    MircatDetectorAlignmentRequest,
    MircatDetectorAlignmentWorkflow,
)
from control_app.workflows.mircat_widget_commands import MircatWidgetCommandHandler
from control_app.workflows.state_machine import WorkflowStateMachine
from control_app.ui.contracts import WorkflowCommand


def main() -> int:
    request = MircatDetectorAlignmentRequest(approved_laser_safety_condition=True)
    assert request.wavenumber_cm1 == DEFAULT_WAVENUMBER_CM1 == 1850.0
    assert request.pulse_rate_hz == DEFAULT_PULSE_RATE_HZ == 2_000_000.0
    assert request.pulse_width_ns == DEFAULT_PULSE_WIDTH_NS == 150.0
    assert request.current_ma == DEFAULT_CURRENT_MA == 1000.0
    assert request.use_t660_timing is DEFAULT_USE_T660_TIMING is False
    assert request.hf2li_preset == DEFAULT_HF2LI_PRESET == "detector_alignment_internal"

    controls = {control.key: control for control in MIRCAT_WIDGET_SPEC.controls}
    grouped_controls = (
        GLOBAL_CONTROL_KEYS
        + DIRECT_CONTROL_KEYS
        + SCAN_CONTROL_KEYS
        + ALIGNMENT_CONTROL_KEYS
    )
    assert set(grouped_controls) == set(controls)
    assert len(grouped_controls) == len(set(grouped_controls))
    assert "start_sweep_scan" in SCAN_CONTROL_KEYS
    assert "stop_scan" in SCAN_CONTROL_KEYS
    assert "start_sweep_scan" not in GLOBAL_CONTROL_KEYS + DIRECT_CONTROL_KEYS + ALIGNMENT_CONTROL_KEYS
    assert "stop_scan" not in GLOBAL_CONTROL_KEYS + DIRECT_CONTROL_KEYS + ALIGNMENT_CONTROL_KEYS
    assert "start_detector_alignment" in ALIGNMENT_CONTROL_KEYS
    assert "stop_detector_alignment" in ALIGNMENT_CONTROL_KEYS
    assert "start_detector_alignment" not in GLOBAL_CONTROL_KEYS + DIRECT_CONTROL_KEYS + SCAN_CONTROL_KEYS
    assert "stop_detector_alignment" not in GLOBAL_CONTROL_KEYS + DIRECT_CONTROL_KEYS + SCAN_CONTROL_KEYS
    assert controls["start_detector_alignment"].command == "mircat.start_detector_alignment"
    assert controls["start_detector_alignment"].safety_approval_required is True
    assert controls["stop_detector_alignment"].command == "mircat.stop_detector_alignment"
    assert controls["emission_off"].command == "mircat.emission_off"

    fields = {field.key: field for field in MIRCAT_WIDGET_SPEC.parameter_fields}
    assert fields["wavenumber_cm1"].default == 1850.0
    assert fields["pulse_rate_hz"].default == 2_000_000.0
    assert fields["pulse_width_ns"].default == 150.0
    assert fields["current_ma"].default == 750.0
    assert fields["use_t660_timing"].default is False

    handler = MircatWidgetCommandHandler(operator="test")
    handler.scan_running = True
    assert "Stop Scan" in " ".join(handler.close_blockers())
    handler.scan_running = False
    handler.alignment_running = True
    assert "Emission Off" in " ".join(handler.close_blockers())
    state_machine = WorkflowStateMachine(operator="test", hardware_access=False)
    state_machine._mircat_handler = handler
    assert state_machine.ui_close_blockers()
    handler.alignment_running = False

    pulse_settings = handler._pulse_settings(
        WorkflowCommand(
            device_key="mircat",
            command="mircat.configure_pulse",
            parameters={
                "pulse_rate_hz": 2_000_000.0,
                "pulse_width_ns": 150.0,
                "current_ma": 1000.0,
            },
        )
    )
    assert pulse_settings["pulse_rate_hz"] == 2_000_000.0
    assert pulse_settings["pulse_width_ns"] == 150.0

    fake_service = _FakeArmService(armed_after_poll=2)
    arm_attempts = MircatDetectorAlignmentWorkflow._arm_and_confirm(
        fake_service,
        request=MircatDetectorAlignmentRequest(
            approved_laser_safety_condition=True,
            poll_interval_s=0.0,
        ),
        label="test",
    )
    assert fake_service.arm_calls == 1
    assert len(arm_attempts) == 2
    assert arm_attempts[-1]["confirmed_armed"] is True

    with (REPO_ROOT / "instrument" / "recipes" / "hf2li_presets.yaml").open("r", encoding="utf-8") as handle:
        presets = yaml.safe_load(handle)["presets"]
    internal_preset = presets["detector_alignment_internal"]
    assert internal_preset["pll"]["enable"] is False
    assert internal_preset["oscillators"][0]["frequency_hz"] == 2_000_000.0
    assert {item["index"] for item in internal_preset["demodulators"]} == {0, 3}
    for demod in internal_preset["demodulators"]:
        assert demod["trigger"] == 0
        assert demod["oscselect"] == 0

    preset = presets["detector_alignment"]
    assert preset["pll"]["adcselect"] == 4
    assert preset["pll"]["freqcenter_hz"] == 2_000_000.0
    assert "daq_trigger" not in preset
    assert preset["labone_plotter"]["trigger"]["source"] is None
    assert preset["labone_plotter"]["trigger"]["demodulator_trigger_value"] == 0
    assert "continuous demodulator stream" in preset["labone_plotter"]["trigger"]["trigger_name"]
    assert {item["index"] for item in preset["demodulators"]} == {0, 3}
    for demod in preset["demodulators"]:
        assert demod["timeconstant_s"] == 0.001
        assert demod["rate_sps"] == 2000.0
        assert demod["trigger"] == 0
        assert demod["trigger_name"] == "continuous"

    with (REPO_ROOT / ALIGNMENT_TIMING_RECIPE).open("r", encoding="utf-8") as handle:
        timing_recipe = yaml.safe_load(handle)
    pulse_setup = timing_recipe["mircat_pulse_setup"]
    assert pulse_setup["wavenumber_cm1"] == 1850.0
    assert pulse_setup["current_ma"] == 1000.0
    assert pulse_setup["pulse_rate_hz"] == 2_000_000
    assert timing_recipe["hf2li_setup"]["plotter_trigger"]["demodulator_trigger_value"] == 0
    assert timing_recipe["hf2li_setup"]["plotter_trigger"]["input"] is None
    for unit, settings in timing_recipe["t660"].items():
        for channel, output in settings["channels"].items():
            assert output["enabled"] is (unit == "t660_1" and channel in "AB")

    print("PASS detector-alignment UI defaults and preset metadata are valid")
    return 0


class _FakeState:
    def __init__(self, state: dict[str, object]) -> None:
        self._state = state

    def to_dict(self) -> dict[str, object]:
        return dict(self._state)


class _FakeArmService:
    def __init__(self, *, armed_after_poll: int) -> None:
        self.armed_after_poll = armed_after_poll
        self.arm_calls = 0
        self.polls = 0

    def arm(self) -> None:
        self.arm_calls += 1

    def is_laser_armed(self) -> bool:
        self.polls += 1
        return self.polls >= self.armed_after_poll

    def read_state(self) -> _FakeState:
        return _FakeState({"armed": self.polls >= self.armed_after_poll, "connected": True})


if __name__ == "__main__":
    raise SystemExit(main())
