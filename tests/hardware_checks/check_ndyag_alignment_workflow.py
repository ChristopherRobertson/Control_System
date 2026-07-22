#!/usr/bin/env python3
"""Validate the Nd:YAG 10 Hz alignment UI contract and timing recipe."""

from __future__ import annotations

from _common import REPO_ROOT

import math

import yaml

from control_app.ui.contracts import WorkflowCommand
from control_app.ui.widgets.ndyag_widget import NDYAG_WIDGET_SPEC
from control_app.workflows.ndyag_alignment import (
    NDYAG_ALIGNMENT_TIMING_RECIPE,
    NDYAG_CONTINUOUS_DEFAULT,
    NDYAG_SHOT_COUNT_DEFAULT,
    NDYAG_SHOT_COUNT_MAX,
    NDYAG_SHOT_COUNT_MIN,
    SURELITE_DAT_MODE2_Q_SWITCH_DELAY_DEFAULT_US,
    SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MAX_US,
    SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MIN_US,
    SURELITE_DAT_MODE2_FIRE_TO_Q_SWITCH_TARGET_NS,
    load_timing_offsets,
    programmed_q_switch_delay_ns,
    recipe_with_q_switch_delay_us,
    recipe_with_ui_parameters,
)
from control_app.workflows.ndyag_widget_commands import NDYAG_SAFE_IDLE_RECIPE
from control_app.workflows.state_machine import WorkflowStateMachine
from control_app.workflows.timing_recipe_manager import TimingRecipeManager


def main() -> int:
    recipe_path = REPO_ROOT / NDYAG_ALIGNMENT_TIMING_RECIPE
    with recipe_path.open("r", encoding="utf-8") as handle:
        recipe = yaml.safe_load(handle)

    assert recipe["name"] == "ndyag_alignment_10hz"
    assert recipe["approved_laser_safety_condition"] is True
    assert recipe["duration"]["mode"] == "continuous"
    assert recipe["duration"]["t660_shots"] == 0
    assert recipe["timing"]["repetition_rate_hz"] == 10
    assert recipe["timing"]["target_fire_to_q_switch_delay_ns"] == int(
        SURELITE_DAT_MODE2_FIRE_TO_Q_SWITCH_TARGET_NS
    )
    expected_q_switch_delay = programmed_q_switch_delay_ns(load_timing_offsets())
    assert math.isclose(
        float(recipe["timing"]["programmed_q_switch_delay_ns"]),
        expected_q_switch_delay,
        abs_tol=0.001,
    )

    t660 = recipe["t660"]
    assert set(t660["t660_2"].get("channels", {})) == {"D"}
    assert "signals" not in t660["t660_2"]
    assert t660["t660_2"]["clock"]["frequency"] == "10Hz"
    assert t660["t660_2"]["clock"]["shots"] == 0
    assert t660["t660_2"]["channels"]["D"]["enabled"] is True

    assert set(t660["t660_1"]["signals"]) == {"ndyag_fire", "ndyag_q_switch"}
    fire = t660["t660_1"]["signals"]["ndyag_fire"]
    q_switch = t660["t660_1"]["signals"]["ndyag_q_switch"]
    assert fire["width"] == "10us"
    assert q_switch["width"] == "10us"
    assert fire["polarity"] == "negative"
    assert q_switch["polarity"] == "negative"
    assert str(q_switch["delay"]).endswith("ns")
    safe_idle_text = yaml.safe_dump(NDYAG_SAFE_IDLE_RECIPE)
    assert "hf2li" not in safe_idle_text.lower()
    assert "mircat" not in safe_idle_text.lower()

    forbidden_signal_names = {"hf2li_extref", "hf2li_daq_trigger", "mircat_trig_in"}
    resolved = TimingRecipeManager().validate_recipe(recipe_path)["resolved_settings"]
    resolved_signals = {
        settings.get("signal")
        for unit in resolved.values()
        for settings in (unit.get("channels") or {}).values()
    }
    assert forbidden_signal_names.isdisjoint(resolved_signals)
    assert {"ndyag_fire", "ndyag_q_switch", "t660_1_trig_in"}.issubset(resolved_signals)

    controls = {control.key: control for control in NDYAG_WIDGET_SPEC.controls}
    fields = {field.key: field for field in NDYAG_WIDGET_SPEC.parameter_fields}
    assert fields["q_switch_delay_us"].default == SURELITE_DAT_MODE2_Q_SWITCH_DELAY_DEFAULT_US
    assert fields["q_switch_delay_us"].minimum == SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MIN_US
    assert fields["q_switch_delay_us"].maximum == SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MAX_US
    assert fields["continuous_mode"].default == NDYAG_CONTINUOUS_DEFAULT
    assert fields["shot_count"].default == NDYAG_SHOT_COUNT_DEFAULT
    assert fields["shot_count"].minimum == NDYAG_SHOT_COUNT_MIN
    assert fields["shot_count"].maximum == NDYAG_SHOT_COUNT_MAX
    assert controls["load_alignment_10hz"].command == "ndyag.load_alignment_10hz"
    assert controls["load_alignment_10hz"].safety_approval_required is True
    assert controls["safe_idle"].command == "ndyag.safe_idle"
    assert NDYAG_WIDGET_SPEC.device_key == "ndyag"

    delay_override = recipe_with_q_switch_delay_us(recipe, 250.0)
    override_q_switch = delay_override["t660"]["t660_1"]["signals"]["ndyag_q_switch"]
    assert override_q_switch["delay"] == "250us"
    assert delay_override["timing"]["programmed_q_switch_delay_ns"] == 250000.0
    try:
        recipe_with_q_switch_delay_us(recipe, 99.9)
    except ValueError as exc:
        assert "between 100 us and 300 us" in str(exc)
    else:  # pragma: no cover - assertion clarity for direct script execution
        raise AssertionError("Q-switch delay below the DAT Mode 2 range was accepted")
    finite_shots = recipe_with_ui_parameters(
        recipe,
        q_switch_delay_us=250.0,
        shot_count=25,
        continuous=False,
    )
    assert finite_shots["duration"]["mode"] == "finite"
    assert finite_shots["duration"]["t660_shots"] == 25
    assert finite_shots["t660"]["t660_2"]["clock"]["shots"] == 25
    continuous = recipe_with_ui_parameters(
        recipe,
        q_switch_delay_us=250.0,
        shot_count=25,
        continuous=True,
    )
    assert continuous["duration"]["mode"] == "continuous"
    assert continuous["duration"]["t660_shots"] == 0
    assert continuous["t660"]["t660_2"]["clock"]["shots"] == 0
    try:
        recipe_with_ui_parameters(recipe, shot_count=0, continuous=False)
    except ValueError as exc:
        assert "Finite shot count must be between 1 and 100" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Finite zero-shot Nd:YAG run was accepted")

    state_machine = WorkflowStateMachine(operator="test", hardware_access=False)
    result = state_machine(
        WorkflowCommand(device_key="ndyag", command="ndyag.load_alignment_10hz")
    )
    assert result.status == "blocked"
    assert "was not sent" in result.message

    print("PASS Nd:YAG alignment workflow recipe and UI contract are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
