"""Nd:YAG alignment timing constants and calibration helpers."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from control_app.config_loader import REPO_ROOT


NDYAG_ALIGNMENT_TIMING_RECIPE = "recipes/ndyag_alignment_10hz.yaml"
TIMING_OFFSETS_PATH = REPO_ROOT / "calibration" / "timing_offsets.yaml"
SURELITE_DAT_MODE2_FIRE_TO_Q_SWITCH_TARGET_NS = 179_830.0
SURELITE_DAT_MODE2_Q_SWITCH_DELAY_DEFAULT_US = 250.0
SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MIN_US = 100.0
SURELITE_DAT_MODE2_Q_SWITCH_DELAY_MAX_US = 300.0
NDYAG_SHOT_COUNT_MIN = 0
NDYAG_FINITE_SHOT_COUNT_MIN = 1
NDYAG_SHOT_COUNT_MAX = 100
NDYAG_SHOT_COUNT_DEFAULT = 0
NDYAG_CONTINUOUS_DEFAULT = True


def load_timing_offsets(path: str | Path = TIMING_OFFSETS_PATH) -> dict[str, Any]:
    """Load the Day 8 timing offsets used by the Nd:YAG recipe."""

    target = Path(path)
    if not target.is_absolute():
        target = REPO_ROOT / target
    with target.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{target} did not parse as a YAML mapping")
    return data


def interpolate_pair_residual_ns(
    offsets: dict[str, Any],
    pair_id: str,
    separation_ns: float,
) -> float:
    """Return the measured residual at a requested separation using linear interpolation."""

    pair = (offsets.get("pairs") or {}).get(pair_id) or {}
    separations = pair.get("separations") or {}
    points = sorted(
        (float(programmed), float(values["mean_residual_ns"]))
        for programmed, values in separations.items()
        if isinstance(values, dict) and "mean_residual_ns" in values
    )
    if not points:
        raise ValueError(f"timing offsets do not contain residuals for {pair_id!r}")
    if separation_ns <= points[0][0]:
        return points[0][1]
    if separation_ns >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= separation_ns <= x1:
            fraction = (separation_ns - x0) / (x1 - x0)
            return y0 + (y1 - y0) * fraction
    return points[-1][1]


def programmed_q_switch_delay_ns(offsets: dict[str, Any] | None = None) -> float:
    """Return the Fire-to-Q-switch T660 delay corrected by Day 8 residual timing."""

    offset_data = offsets or load_timing_offsets()
    residual = interpolate_pair_residual_ns(
        offset_data,
        "pump_fire_to_q_switch",
        SURELITE_DAT_MODE2_FIRE_TO_Q_SWITCH_TARGET_NS,
    )
    return SURELITE_DAT_MODE2_FIRE_TO_Q_SWITCH_TARGET_NS - residual


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
    """Return a validated T660-2 shot count for the Nd:YAG 10 Hz drive."""

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
    q_switch = updated["t660"]["t660_1"]["signals"]["ndyag_q_switch"]
    q_switch["delay"] = format_q_switch_delay_us(validated_delay_us)
    return updated


def recipe_with_shot_count(
    recipe: dict[str, Any],
    shot_count: Any,
    *,
    continuous: bool,
) -> dict[str, Any]:
    """Return a copy of the Nd:YAG recipe with the T660-2 shot count overridden."""

    validated_shot_count = validate_shot_count(shot_count, continuous=continuous)
    updated = deepcopy(recipe)
    duration = updated.setdefault("duration", {})
    duration["mode"] = "continuous" if continuous else "finite"
    duration["t660_shots"] = validated_shot_count
    t6602_clock = updated["t660"]["t660_2"].setdefault("clock", {})
    t6602_clock["shots"] = validated_shot_count
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
