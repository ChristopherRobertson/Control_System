"""Apply recipe-driven PicoScope settings through the real ps5000a driver."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO
import json

import yaml

from control_app.config_loader import ConfigInventory, REPO_ROOT, load_config_inventory
from control_app.devices.picoscope_service import (
    COUPLING,
    RANGES,
    RESOLUTIONS,
    TRIGGER_SOURCES,
    PicoScopeService,
)
from control_app.manifest import new_manifest, write_manifest
from control_app.paths import resolve_compat_path


class PicoScopeSettingsTestError(RuntimeError):
    """Raised when the PicoScope settings test cannot run or fails."""


def load_recipe(path: str | Path) -> tuple[dict[str, Any], Path]:
    """Load a PicoScope settings recipe from YAML."""

    recipe_path = Path(path)
    if not recipe_path.is_absolute():
        recipe_path = resolve_compat_path(recipe_path)
    if not recipe_path.exists():
        raise PicoScopeSettingsTestError(f"recipe not found: {recipe_path}")
    with recipe_path.open("r", encoding="utf-8") as handle:
        recipe = yaml.safe_load(handle) or {}
    if not isinstance(recipe, dict):
        raise PicoScopeSettingsTestError(f"recipe must be a YAML mapping: {recipe_path}")
    return recipe, recipe_path


def capture_settings_from_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    """Return the capture settings block from the supported recipe shapes."""

    candidates = [
        recipe.get("capture_settings"),
        recipe.get("picoscope_capture"),
        (recipe.get("picoscope") or {}).get("capture_settings")
        if isinstance(recipe.get("picoscope"), dict)
        else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
    raise PicoScopeSettingsTestError(
        "recipe does not define PicoScope capture settings"
    )


def validate_capture_settings(
    settings: dict[str, Any], device_config: dict[str, Any]
) -> None:
    """Validate recipe settings against hardware-configured PicoScope capabilities."""

    capabilities = device_config.get("capture_capabilities") or {}
    if not isinstance(capabilities, dict):
        capabilities = {}

    required_fields = capabilities.get("recipe_required_fields") or []
    if not isinstance(required_fields, list):
        raise PicoScopeSettingsTestError("PicoScope recipe_required_fields must be a list")
    missing = [field for field in required_fields if _setting_at(settings, str(field)) is None]
    if missing:
        raise PicoScopeSettingsTestError(
            "recipe is missing required PicoScope fields: " + ", ".join(missing)
        )

    supported_resolutions = _upper_set(capabilities.get("resolutions"), RESOLUTIONS.keys())
    resolution = str(settings.get("resolution", "")).upper()
    if resolution not in supported_resolutions:
        raise PicoScopeSettingsTestError(f"unsupported PicoScope resolution {resolution!r}")

    supported_coupling = _upper_set(capabilities.get("coupling_modes"), COUPLING.keys())
    supported_ranges = _upper_set(capabilities.get("channel_ranges"), RANGES.keys())
    channels = settings.get("channels")
    if not isinstance(channels, dict):
        raise PicoScopeSettingsTestError("PicoScope recipe channels must be a mapping")
    for channel_name in ("A", "B"):
        channel = channels.get(channel_name) or channels.get(channel_name.lower())
        if not isinstance(channel, dict):
            raise PicoScopeSettingsTestError(f"PicoScope channel {channel_name} is missing")
        coupling = str(channel.get("coupling", "")).upper()
        voltage_range = str(channel.get("range", "")).upper()
        if coupling not in supported_coupling:
            raise PicoScopeSettingsTestError(
                f"PicoScope channel {channel_name} coupling {coupling!r} is unsupported"
            )
        if voltage_range not in supported_ranges:
            raise PicoScopeSettingsTestError(
                f"PicoScope channel {channel_name} range {voltage_range!r} is unsupported"
            )

    trigger = settings.get("external_trigger")
    if not isinstance(trigger, dict):
        raise PicoScopeSettingsTestError("PicoScope recipe external_trigger must be a mapping")
    supported_trigger_sources = _trigger_sources(capabilities)
    source = str(trigger.get("source", "EXT")).upper()
    if source not in supported_trigger_sources:
        raise PicoScopeSettingsTestError(f"PicoScope trigger source {source!r} is unsupported")

    threshold_bounds = capabilities.get("threshold") or {}
    if not isinstance(threshold_bounds, dict):
        threshold_bounds = {}
    minimum_threshold = int(threshold_bounds.get("minimum", -32767))
    maximum_threshold = int(threshold_bounds.get("maximum", 32767))
    threshold_adc = _int_field(trigger, "threshold_adc")
    pulse_count_threshold = _int_field(settings, "pulse_count_threshold_adc")
    for label, value in (
        ("external_trigger.threshold_adc", threshold_adc),
        ("pulse_count_threshold_adc", pulse_count_threshold),
    ):
        if value < minimum_threshold or value > maximum_threshold:
            raise PicoScopeSettingsTestError(
                f"{label}={value} is outside {minimum_threshold}..{maximum_threshold}"
            )

    total_samples = _int_field(settings, "total_samples")
    pre_trigger = _int_field(settings, "pre_trigger_samples")
    timebase = _int_field(settings, "timebase")
    if total_samples <= 0:
        raise PicoScopeSettingsTestError("total_samples must be positive")
    if pre_trigger < 0 or pre_trigger >= total_samples:
        raise PicoScopeSettingsTestError("pre_trigger_samples must be >= 0 and < total_samples")
    if timebase < 0:
        raise PicoScopeSettingsTestError("timebase must be non-negative")
    _int_field(trigger, "direction")


class PicoScopeSettingsTest:
    """Apply recipe-defined PicoScope settings and write run evidence."""

    def __init__(
        self,
        *,
        operator: str,
        inventory: ConfigInventory | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        self.operator = operator
        self.inventory = inventory or load_config_inventory(config_path, write_files=False)

    def run(
        self,
        *,
        recipe_path: str | Path,
        run_dir: str | Path,
        command_log: TextIO | None = None,
        command_log_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        """Apply settings to the real PicoScope and write summary/manifest files."""

        recipe, resolved_recipe_path = load_recipe(recipe_path)
        settings = capture_settings_from_recipe(recipe)
        device_config = self.inventory.devices.get("picoscope")
        if not isinstance(device_config, dict):
            raise PicoScopeSettingsTestError("picoscope missing from hardware configuration")
        validate_capture_settings(settings, device_config)

        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        settings_path = run_path / "picoscope_settings_request.json"
        summary_path = run_path / "picoscope_settings_apply_summary.json"

        timing_validation: dict[str, Any] | None = None
        pico = PicoScopeService(device_config, settings, command_log=command_log)
        try:
            pico.open_unit()
            pico.apply_capture_settings()
            timing_validation = pico.validate_sample_timing()
            pico.stop()
        finally:
            pico.close_unit()

        summary = {
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "operator": self.operator,
            "recipe_path": str(resolved_recipe_path),
            "picoscope_model": device_config.get("model"),
            "picoscope_serial": device_config.get("serial_number"),
            "settings_applied": settings,
            "sample_timing_validation": timing_validation,
            "status": "PASS",
        }
        settings_path.write_text(
            json.dumps(settings, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest = new_manifest(
            operator=self.operator,
            inventory=self.inventory,
            picoscope_settings=settings,
            command_log_paths=command_log_paths or [],
            device_readback_paths=[str(settings_path), str(summary_path)],
            blocker_status={"blocked": False, "blockers": [], "next_actions": []},
        )
        write_manifest(run_path / "run_manifest.json", manifest)
        return summary


def _setting_at(settings: dict[str, Any], dotted_path: str) -> Any:
    current: Any = settings
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _upper_set(configured: Any, fallback: Any) -> set[str]:
    values = configured if isinstance(configured, list) and configured else fallback
    return {str(value).upper() for value in values}


def _trigger_sources(capabilities: dict[str, Any]) -> set[str]:
    configured = capabilities.get("trigger_sources")
    sources: set[str] = set()
    if isinstance(configured, dict):
        for value in configured.values():
            if isinstance(value, dict) and value.get("api_source"):
                sources.add(str(value["api_source"]).upper())
    analog_channels = capabilities.get("analog_channels")
    if isinstance(analog_channels, list):
        sources.update(str(channel).upper() for channel in analog_channels)
    return sources or set(TRIGGER_SOURCES.keys())


def _int_field(settings: dict[str, Any], key: str) -> int:
    if key not in settings:
        raise PicoScopeSettingsTestError(f"missing integer field {key}")
    try:
        return int(settings[key])
    except (TypeError, ValueError) as exc:
        raise PicoScopeSettingsTestError(f"{key} must be an integer") from exc
