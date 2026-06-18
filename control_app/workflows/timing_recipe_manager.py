"""Timing recipe parsing, signal resolution, application, and readback."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO
import json

import yaml

from control_app.config_loader import ConfigInventory, load_config_inventory
from control_app.devices.t660_service import T660Service


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

        if not self.inventory.config_hash:
            raise TimingRecipeError("config hash is missing; refusing to apply recipe")
        recipe_data = self.load_recipe(recipe) if not isinstance(recipe, dict) else dict(recipe)
        resolved = self._resolve_recipe(recipe_data)
        readback: dict[str, Any] = {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "recipe_name": recipe_data.get("name"),
            "recipe_path": recipe_data.get("_path"),
            "config_hash": self.inventory.config_hash,
            "resolved_settings": resolved,
            "devices": {},
            "matches_recipe": None,
            "mismatches": [],
        }

        services: dict[str, T660Service] = {}
        try:
            for unit in sorted(resolved):
                service = T660Service.from_config(
                    unit, config_path=self.config_path, command_log=self.command_log
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

        if not self.inventory.config_hash:
            raise TimingRecipeError("config hash is missing; refusing to validate recipe")
        recipe_data = self.load_recipe(recipe) if not isinstance(recipe, dict) else dict(recipe)
        resolved = self._resolve_recipe(recipe_data)
        return {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "recipe_name": recipe_data.get("name"),
            "recipe_path": recipe_data.get("_path"),
            "config_hash": self.inventory.config_hash,
            "resolved_settings": resolved,
            "status": "VALIDATED_PREHARDWARE",
        }

    def _resolve_recipe(self, recipe: dict[str, Any]) -> dict[str, dict[str, Any]]:
        approved = bool(recipe.get("approved_laser_safety_condition", False))
        resolved: dict[str, dict[str, Any]] = {}
        t660_section = recipe.get("t660") or {}
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
                section = unit_recipe.get(section_name) or {}
                if not isinstance(section, dict):
                    raise TimingRecipeError(f"{unit} {section_name} must be a mapping")
                for key, settings in section.items():
                    mapping = self.resolve_signal(str(key), unit=unit if section_name == "channels" else None)
                    if mapping["device"] != unit:
                        raise TimingRecipeError(
                            f"{key!r} resolves to {mapping['device']}, not recipe unit {unit}"
                        )
                    if settings.get("enabled") is True and self._is_laser_signal(mapping["signal"]) and not approved:
                        raise TimingRecipeError(
                            f"laser-driving signal {mapping['signal']} cannot be enabled "
                            "without approved_laser_safety_condition"
                        )
                    channels[mapping["channel"]] = dict(settings)
                    channels[mapping["channel"]]["signal"] = mapping["signal"]
            resolved_unit["channels"] = channels
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
        return mismatches
