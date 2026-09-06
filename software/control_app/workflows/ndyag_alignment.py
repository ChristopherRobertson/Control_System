"""Nd:YAG alignment timing constants and calibration helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

NDYAG_ALIGNMENT_TIMING_RECIPE = "instrument/recipes/ndyag_alignment_10hz.yaml"
SURELITE_DAT_MODE2_FIRE_TO_Q_SWITCH_TARGET_NS = 179_830.0
SURELITE_DAT_MODE2_Q_SWITCH_DELAY_DEFAULT_US = 250.0
SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MIN_US = 100.0
SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MAX_US = 300.0
NDYAG_SHOT_COUNT_MIN = 0
NDYAG_FINITE_SHOT_COUNT_MIN = 1
NDYAG_SHOT_COUNT_MAX = 100
NDYAG_SHOT_COUNT_DEFAULT = 0
NDYAG_CONTINUOUS_DEFAULT = True

def validate_q_switch_delay_us(value: Any) -> float:
    """Return a validated Surelite DAT Mode 2 Q-switch delay in microseconds."""

    try:
        delay_us = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Q-switch delay must be a numeric microsecond value") from exc
    if not (
        SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MIN_US
        <= delay_us
        <= SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MAX_US
    ):
        raise ValueError(
            "Q-switch delay must be between "
            f"{SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MIN_US:g} us and "
            f"{SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MAX_US:g} us"
        )
    return delay_us


def format_q_switch_delay_us(delay_us: float) -> str:
    """Format a microsecond Q-switch delay for the T660 command parser."""

    text = f"{delay_us:.6f}".rstrip("0").rstrip(".")
    return f"{text}us"


def validate_shot_count(value: Any, *, continuous: bool) -> int:
    """Return the requested number of finite Nd:YAG pump frames."""

    if continuous:
        return 0
    try:
        shot_count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Shot count must be an integer") from exc
    if shot_count < NDYAG_FINITE_SHOT_COUNT_MIN or shot_count > NDYAG_SHOT_COUNT_MAX:
        raise ValueError(
            "Finite shot count must be between "
            f"{NDYAG_FINITE_SHOT_COUNT_MIN} and {NDYAG_SHOT_COUNT_MAX}; "
            "select Continuous for continuous 10 Hz operation"
        )
    return shot_count


def recipe_with_q_switch_delay_us(recipe: dict[str, Any], delay_us: Any) -> dict[str, Any]:
    """Return a copy of the Nd:YAG recipe with the Q-switch delay overridden."""

    validated_delay_us = validate_q_switch_delay_us(delay_us)
    updated = deepcopy(recipe)
    timing = updated.setdefault("timing", {})
    timing["target_fire_to_q_switch_delay_ns"] = validated_delay_us * 1000.0
    timing["programmed_q_switch_delay_ns"] = validated_delay_us * 1000.0
    timing["q_switch_delay_source"] = "ui_parameter"
    pump = updated["t660"]["t660_2"]
    q_switch = (pump.get("signals") or {}).get("ndyag_q_switch")
    if q_switch is None:
        q_switch = pump["channels"]["B"]
    q_switch["delay"] = format_q_switch_delay_us(validated_delay_us)
    return updated


def recipe_with_shot_count(
    recipe: dict[str, Any],
    shot_count: Any,
    *,
    continuous: bool,
) -> dict[str, Any]:
    """Return an Nd:YAG recipe with continuous timing or bounded T660-2 frames."""

    validated_shot_count = validate_shot_count(shot_count, continuous=continuous)
    updated = deepcopy(recipe)
    duration = updated.setdefault("duration", {})
    duration["mode"] = "continuous" if continuous else "finite"
    duration["t660_shots"] = validated_shot_count
    t6601_clock = updated["t660"]["t660_1"].setdefault("clock", {})
    t6601_clock["shots"] = 0
    if continuous:
        updated["t660"]["t660_2"].pop("finite_frame_count", None)
        updated["t660"]["t660_2"].pop("frame_input_frequency_hz", None)
    else:
        updated["t660"]["t660_2"]["finite_frame_count"] = validated_shot_count
        updated["t660"]["t660_2"]["frame_input_frequency_hz"] = 10.0
    return updated


def recipe_with_ui_parameters(
    recipe: dict[str, Any],
    *,
    q_switch_delay_us: Any | None = None,
    shot_count: Any = NDYAG_SHOT_COUNT_DEFAULT,
    continuous: bool = NDYAG_CONTINUOUS_DEFAULT,
) -> dict[str, Any]:
    """Return a copy of the Nd:YAG recipe with UI timing parameters applied."""

    updated = deepcopy(recipe)
    if q_switch_delay_us is not None:
        updated = recipe_with_q_switch_delay_us(updated, q_switch_delay_us)
    return recipe_with_shot_count(updated, shot_count, continuous=continuous)
