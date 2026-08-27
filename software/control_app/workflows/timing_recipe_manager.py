"""Timing recipe parsing, signal resolution, application, and readback."""

from __future__ import annotations

from datetime import UTC, datetime
from copy import deepcopy
from pathlib import Path
from typing import Any, TextIO
import json

import yaml

from control_app.config_loader import ConfigInventory, load_config_inventory
from control_app.devices.t660_service import T660ConfigurationError, T660Service


LASER_SIGNAL_KEYWORDS = ("ndyag", "q_switch", "fire", "mircat", "laser", "opo")


class TimingRecipeError(RuntimeError):
    """Raised when a timing recipe cannot be safely applied."""


class TimingRecipeManager:
    """Apply timing recipes to configured real T660 services only."""

    def __init__(
        self,
        inventory: ConfigInventory | None = None,
        *,
        config_path: str | Path | None = None,
        command_log: TextIO | None = None,
    ) -> None:
        self.inventory = inventory or load_config_inventory(config_path, write_files=False)
        self.config_path = Path(self.inventory.config_path)
        self.command_log = command_log

    def load_recipe(self, recipe_path: str | Path) -> dict[str, Any]:
        """Parse one timing recipe YAML file."""

        path = Path(recipe_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        with path.open("r", encoding="utf-8") as handle:
            recipe = yaml.safe_load(handle) or {}
        if not isinstance(recipe, dict):
            raise TimingRecipeError(f"{path} did not parse as a YAML mapping")
        recipe.setdefault("name", path.stem)
        recipe["_path"] = str(path.resolve())
        return recipe

    def resolve_signal(self, signal_or_channel: str, unit: str | None = None) -> dict[str, str]:
        """Resolve a configured signal name to a T660 device/channel pair."""

        token = str(signal_or_channel)
        if unit and token.upper() in {"A", "B", "C", "D"}:
            return {"device": unit, "channel": token.upper(), "signal": self._signal_for(unit, token)}
        mapping = self.inventory.signal_map.get(token)
        if mapping:
            return {"device": mapping["device"], "channel": mapping["channel"], "signal": token}
        raise TimingRecipeError(f"signal/channel {signal_or_channel!r} cannot be resolved")

    def apply_recipe(
        self,
        recipe: str | Path | dict[str, Any],
        *,
        output_path: str | Path,
    ) -> dict[str, Any]:
        """Apply a recipe, force requested EOD, read back, compare, and write JSON."""

        recipe_data = self.load_recipe(recipe) if not isinstance(recipe, dict) else dict(recipe)
        resolved = self._resolve_recipe(recipe_data)
        readback: dict[str, Any] = {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "recipe_name": recipe_data.get("name"),
            "recipe_path": recipe_data.get("_path"),
            "resolved_settings": resolved,
            "devices": {},
            "matches_recipe": None,
            "mismatches": [],
        }

        services: dict[str, T660Service] = {}
        try:
            for unit in sorted(resolved):
                # Use the already loaded inventory for this operation.
                service = T660Service(
                    unit,
                    deepcopy(self.inventory.t660_devices[unit]),
                    command_log=self.command_log,
                )
                service.connect()
                service.identify()
                services[unit] = service

            for unit, unit_recipe in resolved.items():
                services[unit].apply_recipe(unit_recipe)
                readback["devices"][unit] = services[unit].read_active_settings()

            readback["mismatches"] = self._compare_readback(resolved, readback["devices"])
            readback["matches_recipe"] = not readback["mismatches"]
        finally:
            for service in services.values():
                service.close()

        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(readback, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if readback["mismatches"]:
            raise TimingRecipeError(f"readback mismatch: {readback['mismatches']}")
        return readback

    def validate_recipe(self, recipe: str | Path | dict[str, Any]) -> dict[str, Any]:
        """Resolve and safety-check a timing recipe without opening hardware."""

        recipe_data = self.load_recipe(recipe) if not isinstance(recipe, dict) else dict(recipe)
        resolved = self._resolve_recipe(recipe_data)
        return {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "recipe_name": recipe_data.get("name"),
            "recipe_path": recipe_data.get("_path"),
            "resolved_settings": resolved,
            "status": "VALIDATED_PREHARDWARE",
        }

    def _resolve_recipe(self, recipe: dict[str, Any]) -> dict[str, dict[str, Any]]:
        approved_value = recipe.get("approved_laser_safety_condition", False)
        if not isinstance(approved_value, bool):
            raise TimingRecipeError(
                "approved_laser_safety_condition must be a YAML boolean"
            )
        approved = approved_value
        resolved: dict[str, dict[str, Any]] = {}
        t660_section = recipe.get("t660")
        if t660_section is None:
            t660_section = {}
        if not isinstance(t660_section, dict):
            raise TimingRecipeError("recipe t660 section must be a mapping")

        for unit, unit_recipe in t660_section.items():
            if unit not in self.inventory.t660_devices:
                raise TimingRecipeError(f"recipe references unknown T660 unit {unit!r}")
            if not isinstance(unit_recipe, dict):
                raise TimingRecipeError(f"{unit} recipe must be a mapping")
            resolved_unit = {
                key: value
                for key, value in unit_recipe.items()
                if key not in {"channels", "signals"}
            }
            channels: dict[str, Any] = {}
            for section_name in ("channels", "signals"):
                section = unit_recipe.get(section_name)
                if section is None:
                    section = {}
                if not isinstance(section, dict):
                    raise TimingRecipeError(f"{unit} {section_name} must be a mapping")
                for key, settings in section.items():
                    if not isinstance(settings, dict):
                        raise TimingRecipeError(
                            f"{unit} {section_name} entry {key!r} must be a mapping"
                        )
                    mapping = self.resolve_signal(str(key), unit=unit if section_name == "channels" else None)
                    if mapping["device"] != unit:
                        raise TimingRecipeError(
                            f"{key!r} resolves to {mapping['device']}, not recipe unit {unit}"
                        )
                    if mapping["channel"] in channels:
                        raise TimingRecipeError(
                            f"{unit} channel {mapping['channel']} is configured more than once"
                        )
                    if settings.get("enabled") is True and self._is_laser_signal(mapping["signal"]) and not approved:
                        raise TimingRecipeError(
                            f"laser-driving signal {mapping['signal']} cannot be enabled "
                            "without approved_laser_safety_condition"
                        )
                    channels[mapping["channel"]] = dict(settings)
                    channels[mapping["channel"]]["signal"] = mapping["signal"]
            resolved_unit["channels"] = channels
            if "frames_engine" in resolved_unit:
                role = str(self.inventory.t660_devices[unit].get("role", "")).lower()
                if "frame" not in role:
                    raise TimingRecipeError(
                        f"{unit} is not configured with the Trains and Frames feature"
                    )
            try:
                T660Service.validate_recipe_section(unit, resolved_unit)
            except T660ConfigurationError as exc:
                raise TimingRecipeError(str(exc)) from exc
            resolved[unit] = resolved_unit
        if not resolved:
            raise TimingRecipeError("recipe has no T660 settings")
        return resolved

    def _signal_for(self, unit: str, channel: str) -> str:
        unit_config = self.inventory.t660_devices.get(unit, {})
        return str((unit_config.get("channel_map") or {}).get(channel.upper(), channel.upper()))

    @staticmethod
    def _is_laser_signal(signal_name: str) -> bool:
        lowered = signal_name.lower()
        return any(keyword in lowered for keyword in LASER_SIGNAL_KEYWORDS)

    @staticmethod
    def _compare_readback(
        resolved: dict[str, dict[str, Any]], readbacks: dict[str, Any]
    ) -> list[dict[str, Any]]:
        mismatches: list[dict[str, Any]] = []
        for unit, unit_recipe in resolved.items():
            device_readback = readbacks.get(unit, {})
            if not device_readback:
                mismatches.append({"device": unit, "issue": "missing readback"})
                continue
            queries = device_readback.get("queries") or {}
            clock = unit_recipe.get("clock") or {}
            expected_trigger_source = unit_recipe.get("trigger_source")
            if expected_trigger_source is None:
                expected_trigger_source = clock.get("mode")
            if expected_trigger_source is not None:
                _append_text_query_mismatch(
                    mismatches,
                    device=unit,
                    field="trigger_source",
                    query=queries.get("trigger_source", {}),
                    expected=str(expected_trigger_source).strip().upper(),
                )
            if "predivider" in unit_recipe:
                _append_numeric_query_mismatch(
                    mismatches,
                    device=unit,
                    field="predivider",
                    query=queries.get("predivider", {}),
                    expected=float(unit_recipe["predivider"]),
                    absolute_tolerance=0.0,
                )
            if "gate_mode" in unit_recipe:
                query = queries.get("gate_mode", {})
                if not query.get("ok"):
                    mismatches.append(
                        {
                            "device": unit,
                            "field": "gate_mode",
                            "issue": query.get("error", "query failed"),
                        }
                    )
                else:
                    actual = str(query.get("response", "")).strip().upper()
                    expected_mode = int(unit_recipe["gate_mode"])
                    if not (
                        (expected_mode == 0 and actual in {"0", "OFF"})
                        or actual == str(expected_mode)
                    ):
                        mismatches.append(
                            {
                                "device": unit,
                                "field": "gate_mode",
                                "expected": expected_mode,
                                "actual": actual,
                            }
                        )
            if "burst_enabled" in unit_recipe:
                query = queries.get("burst", {})
                expected_burst = "ON" if unit_recipe["burst_enabled"] else "OFF"
                if not query.get("ok"):
                    mismatches.append(
                        {
                            "device": unit,
                            "field": "burst_enabled",
                            "issue": query.get("error", "query failed"),
                        }
                    )
                else:
                    actual = str(query.get("response", "")).strip().upper().split()
                    if expected_burst not in actual:
                        mismatches.append(
                            {
                                "device": unit,
                                "field": "burst_enabled",
                                "expected": expected_burst,
                                "actual": " ".join(actual),
                            }
                        )
            if str(unit_recipe.get("frames_engine", "")).strip().upper() == "OFF":
                _append_text_query_mismatch(
                    mismatches,
                    device=unit,
                    field="frames_engine",
                    query=queries.get("frames_engine", {}),
                    expected="OFF",
                )
            external_trigger = unit_recipe.get("external_trigger") or {}
            if external_trigger:
                expected_polarity = _canonical_polarity(
                    external_trigger.get("polarity", "positive")
                )
                _append_canonical_text_query_mismatch(
                    mismatches,
                    device=unit,
                    field="trigger_input_polarity",
                    query=queries.get("trigger_input_polarity", {}),
                    expected=expected_polarity,
                    canonicalizer=_canonical_polarity,
                )
                expected_termination = _canonical_trigger_termination(
                    external_trigger.get("termination", "50OHM")
                )
                actual_termination_query = queries.get(
                    "trigger_input_termination", {}
                )
                if not actual_termination_query.get("ok"):
                    mismatches.append(
                        {
                            "device": unit,
                            "field": "trigger_input_termination",
                            "issue": actual_termination_query.get(
                                "error", "query failed"
                            ),
                        }
                    )
                else:
                    raw_termination = actual_termination_query.get("response", "")
                    try:
                        actual_termination = _canonical_trigger_termination(
                            raw_termination
                        )
                    except ValueError:
                        actual_termination = str(raw_termination).strip().upper()
                    if actual_termination != expected_termination:
                        mismatches.append(
                            {
                                "device": unit,
                                "field": "trigger_input_termination",
                                "expected": expected_termination,
                                "actual": actual_termination,
                            }
                        )
                _append_numeric_query_mismatch(
                    mismatches,
                    device=unit,
                    field="trigger_input_threshold_v",
                    query=queries.get("trigger_input_threshold_v", {}),
                    expected=float(external_trigger.get("threshold_v", 2.0)),
                    absolute_tolerance=0.001,
                )
            if "frequency" in clock:
                frequency_query = (device_readback.get("queries") or {}).get(
                    "synth_frequency", {}
                )
                if not frequency_query.get("ok"):
                    mismatches.append(
                        {
                            "device": unit,
                            "field": "synth_frequency",
                            "issue": frequency_query.get("error", "query failed"),
                        }
                    )
                else:
                    try:
                        expected_hz = _parse_frequency_hz(clock["frequency"])
                        actual_hz = _parse_frequency_hz(
                            frequency_query.get("response")
                        )
                    except (TypeError, ValueError):
                        mismatches.append(
                            {
                                "device": unit,
                                "field": "synth_frequency",
                                "expected": clock["frequency"],
                                "actual": frequency_query.get("response"),
                                "issue": "frequency could not be parsed",
                            }
                        )
                    else:
                        if not _nearly_equal(
                            expected_hz, actual_hz, absolute_tolerance=1e-6
                        ):
                            mismatches.append(
                                {
                                    "device": unit,
                                    "field": "synth_frequency",
                                    "expected_hz": expected_hz,
                                    "actual_hz": actual_hz,
                                }
                            )
            for channel, settings in (unit_recipe.get("channels") or {}).items():
                channel_readback = (device_readback.get("channels") or {}).get(channel, {})
                if "enabled" in settings:
                    response = channel_readback.get("enabled", {})
                    if not response.get("ok"):
                        mismatches.append(
                            {
                                "device": unit,
                                "channel": channel,
                                "field": "enabled",
                                "issue": response.get("error", "query failed"),
                            }
                        )
                    else:
                        expected_state = "ON" if settings["enabled"] else "OFF"
                        actual_state = str(response.get("response", "")).strip().upper()
                        if actual_state != expected_state:
                            mismatches.append(
                                {
                                    "device": unit,
                                    "channel": channel,
                                    "field": "enabled",
                                    "expected": expected_state,
                                    "actual": actual_state,
                                }
                            )
                for recipe_field, readback_field in (
                    ("delay", "delay_edge"),
                    ("width", "width_edge"),
                ):
                    if recipe_field not in settings:
                        continue
                    response = channel_readback.get(readback_field, {})
                    if not response.get("ok"):
                        mismatches.append(
                            {
                                "device": unit,
                                "channel": channel,
                                "field": recipe_field,
                                "issue": response.get("error", "query failed"),
                            }
                        )
                        continue
                    try:
                        expected_seconds = _parse_duration_seconds(
                            settings[recipe_field]
                        )
                        actual_seconds = _parse_duration_seconds(
                            response.get("response")
                        )
                    except (TypeError, ValueError):
                        mismatches.append(
                            {
                                "device": unit,
                                "channel": channel,
                                "field": recipe_field,
                                "expected": settings[recipe_field],
                                "actual": response.get("response"),
                                "issue": "duration could not be parsed",
                            }
                        )
                        continue
                    if not _nearly_equal(
                        expected_seconds,
                        actual_seconds,
                        absolute_tolerance=1e-12,
                    ):
                        mismatches.append(
                            {
                                "device": unit,
                                "channel": channel,
                                "field": recipe_field,
                                "expected_seconds": expected_seconds,
                                "actual_seconds": actual_seconds,
                            }
                        )
                if "termination" in settings:
                    response = channel_readback.get("termination", {})
                    if not response.get("ok"):
                        mismatches.append(
                            {
                                "device": unit,
                                "channel": channel,
                                "field": "termination",
                                "issue": response.get("error", "query failed"),
                            }
                        )
                    else:
                        expected = _canonical_channel_termination(
                            settings["termination"]
                        )
                        raw_actual = response.get("response", "")
                        try:
                            actual = _canonical_channel_termination(raw_actual)
                        except ValueError:
                            actual = str(raw_actual).strip().upper()
                        if actual != expected:
                            mismatches.append(
                                {
                                    "device": unit,
                                    "channel": channel,
                                    "field": "termination",
                                    "expected": expected,
                                    "actual": actual,
                                }
                            )
                if "polarity" in settings:
                    response = channel_readback.get("polarity", {})
                    expected = _canonical_polarity(settings["polarity"])
                    if not response.get("ok"):
                        mismatches.append(
                            {
                                "device": unit,
                                "channel": channel,
                                "field": "polarity",
                                "issue": response.get("error", "query failed"),
                            }
                        )
                    else:
                        raw_actual = response.get("response", "")
                        try:
                            actual = _canonical_polarity(raw_actual)
                        except ValueError:
                            actual = str(raw_actual).strip().upper()
                        if actual != expected:
                            mismatches.append(
                                {
                                    "device": unit,
                                    "channel": channel,
                                    "field": "polarity",
                                    "expected": expected,
                                    "actual": actual,
                                }
                            )
                if (
                    "delay" in settings
                    or "width" in settings
                    or "timing_mode" in settings
                ):
                    response = channel_readback.get("timing_mode", {})
                    expected_mode = (
                        "DW"
                        if "delay" in settings or "width" in settings
                        else _canonical_timing_mode(settings["timing_mode"])
                    )
                    if not response.get("ok"):
                        mismatches.append(
                            {
                                "device": unit,
                                "channel": channel,
                                "field": "timing_mode",
                                "issue": response.get("error", "query failed"),
                            }
                        )
                    else:
                        raw_actual = response.get("response", "")
                        try:
                            actual = _canonical_timing_mode(raw_actual)
                        except ValueError:
                            actual = str(raw_actual).strip().upper()
                        if actual != expected_mode:
                            mismatches.append(
                                {
                                    "device": unit,
                                    "channel": channel,
                                    "field": "timing_mode",
                                    "expected": expected_mode,
                                    "actual": actual,
                                }
                            )
        return mismatches


def _append_text_query_mismatch(
    mismatches: list[dict[str, Any]],
    *,
    device: str,
    field: str,
    query: dict[str, Any],
    expected: str,
) -> None:
    if not query.get("ok"):
        mismatches.append(
            {
                "device": device,
                "field": field,
                "issue": query.get("error", "query failed"),
            }
        )
        return
    actual = str(query.get("response", "")).strip().upper()
    if actual != expected:
        mismatches.append(
            {
                "device": device,
                "field": field,
                "expected": expected,
                "actual": actual,
            }
        )


def _append_canonical_text_query_mismatch(
    mismatches: list[dict[str, Any]],
    *,
    device: str,
    field: str,
    query: dict[str, Any],
    expected: str,
    canonicalizer: Any,
) -> None:
    if not query.get("ok"):
        mismatches.append(
            {
                "device": device,
                "field": field,
                "issue": query.get("error", "query failed"),
            }
        )
        return
    raw_actual = query.get("response", "")
    try:
        actual = canonicalizer(raw_actual)
    except ValueError:
        actual = str(raw_actual).strip().upper()
    if actual != expected:
        mismatches.append(
            {
                "device": device,
                "field": field,
                "expected": expected,
                "actual": actual,
            }
        )


def _append_numeric_query_mismatch(
    mismatches: list[dict[str, Any]],
    *,
    device: str,
    field: str,
    query: dict[str, Any],
    expected: float,
    absolute_tolerance: float,
) -> None:
    if not query.get("ok"):
        mismatches.append(
            {
                "device": device,
                "field": field,
                "issue": query.get("error", "query failed"),
            }
        )
        return
    try:
        actual = float(str(query.get("response", "")).strip())
    except (TypeError, ValueError):
        mismatches.append(
            {
                "device": device,
                "field": field,
                "expected": expected,
                "actual": query.get("response"),
            }
        )
        return
    if not _nearly_equal(
        expected,
        actual,
        absolute_tolerance=absolute_tolerance,
    ):
        mismatches.append(
            {
                "device": device,
                "field": field,
                "expected": expected,
                "actual": actual,
            }
        )


def _parse_frequency_hz(value: Any) -> float:
    text = str(value).strip().lower().replace(" ", "")
    multipliers = {"mhz": 1_000_000.0, "khz": 1_000.0, "hz": 1.0}
    for suffix, multiplier in multipliers.items():
        if text.endswith(suffix):
            return float(text[: -len(suffix)]) * multiplier
    return float(text)


def _parse_duration_seconds(value: Any) -> float:
    text = str(value).strip().lower().replace(" ", "")
    multipliers = {"ns": 1e-9, "us": 1e-6, "ms": 1e-3, "s": 1.0}
    for suffix, multiplier in multipliers.items():
        if text.endswith(suffix):
            return float(text[: -len(suffix)]) * multiplier
    return float(text)


def _canonical_polarity(value: Any) -> str:
    normalized = str(value).strip().upper()
    if normalized in {"POS", "POSITIVE", "+"}:
        return "POS"
    if normalized in {"NEG", "NEGATIVE", "-"}:
        return "NEG"
    raise ValueError(f"unsupported polarity {value!r}")


def _canonical_trigger_termination(value: Any) -> str:
    normalized = str(value).strip().upper()
    if normalized in {"50OHM", "50R", "50", "ON"}:
        return "50OHM"
    if normalized in {"HIZ", "HI_Z", "NONE", "OFF"}:
        return "HIZ"
    raise ValueError(f"unsupported trigger termination {value!r}")


def _canonical_channel_termination(value: Any) -> str:
    normalized = str(value).strip().upper()
    if normalized in {"50OHM", "50R", "50", "ON"}:
        return "50OHM"
    if normalized in {"LOWZ", "LOW_Z", "NONE", "OFF"}:
        return "LOWZ"
    raise ValueError(f"unsupported channel termination {value!r}")


def _canonical_timing_mode(value: Any) -> str:
    normalized = str(value).strip().upper().replace("_", "").replace("-", "")
    if normalized in {"DW", "DELAYWIDTH"}:
        return "DW"
    if normalized in {"RF", "RISEFALL"}:
        return "RF"
    raise ValueError(f"unsupported timing mode {value!r}")


def _nearly_equal(
    expected: float,
    actual: float,
    *,
    absolute_tolerance: float,
) -> bool:
    return abs(expected - actual) <= max(
        absolute_tolerance,
        abs(expected) * 1e-9,
    )
