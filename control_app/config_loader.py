"""Read-only loader and inventory writer for hardware_configuration.yaml."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
PREFERRED_CONFIG = REPO_ROOT / "config" / "hardware_configuration.yaml"
ROOT_CONFIG = REPO_ROOT / "hardware_configuration.yaml"


class HardwareConfigError(RuntimeError):
    """Raised when the hardware configuration is absent or unusable."""


@dataclass(frozen=True)
class ConfigInventory:
    """Structured summary of the exact hardware configuration file used."""

    config_path: str
    schema_version: str | None
    devices: dict[str, dict[str, Any]]
    t660_devices: dict[str, dict[str, Any]]
    signal_map: dict[str, dict[str, str]]
    timing_routes: dict[str, Any]
    mux_settings: dict[str, Any]
    mux_routes: dict[str, Any]
    picoscope_settings: dict[str, Any]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable inventory dictionary."""

        return asdict(self)


def find_hardware_config(path: str | Path | None = None) -> Path:
    """Locate the hardware configuration without creating or modifying it."""

    if path is not None:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        if candidate.exists():
            return candidate.resolve()
        raise HardwareConfigError(f"hardware configuration not found: {candidate}")

    if PREFERRED_CONFIG.exists():
        return PREFERRED_CONFIG.resolve()
    if ROOT_CONFIG.exists():
        return ROOT_CONFIG.resolve()
    raise HardwareConfigError(
        "hardware_configuration.yaml not found in config/ or repository root"
    )


def load_hardware_config(path: str | Path | None = None) -> tuple[dict[str, Any], Path, None]:
    """Load hardware_configuration.yaml and return its data and path."""

    config_path = find_hardware_config(path)
    with config_path.open("rb") as handle:
        raw = handle.read()
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise HardwareConfigError(f"{config_path} did not parse as a YAML mapping")
    return data, config_path, None


def build_config_inventory(
    config: dict[str, Any], config_path: str | Path, _legacy_identifier: Any = None
) -> ConfigInventory:
    """Build a flexible inventory from the available configuration sections."""

    warnings: list[str] = []
    devices = config.get("devices")
    if not isinstance(devices, dict) or not devices:
        raise HardwareConfigError("hardware_configuration.yaml is missing devices")

    t660_devices = {
        name: value
        for name, value in devices.items()
        if isinstance(value, dict) and name.lower().startswith("t660")
    }
    if not t660_devices:
        raise HardwareConfigError("hardware_configuration.yaml has no T660 devices")

    signal_map: dict[str, dict[str, str]] = {}
    for unit_name, unit_config in t660_devices.items():
        channel_map = unit_config.get("channel_map") or {}
        if not isinstance(channel_map, dict) or not channel_map:
            warnings.append(f"{unit_name} has no channel_map")
            continue
        for channel, signal_name in channel_map.items():
            if signal_name:
                signal_map[str(signal_name)] = {
                    "device": unit_name,
                    "channel": str(channel).upper(),
                }

    timing_routes = config.get("timing_routes") or {}
    if not isinstance(timing_routes, dict):
        timing_routes = {}
        warnings.append("timing_routes must be a mapping when present")

    mux_settings = config.get("arduino_mux_topology") or {}
    if not isinstance(mux_settings, dict):
        mux_settings = {}
        warnings.append("arduino_mux_topology must be a mapping when present")
    mux_device = devices.get("arduino_mux")
    mux_disabled = (
        isinstance(mux_device, dict)
        and mux_device.get("enabled") is False
    ) or mux_settings.get("enabled") is False

    mux_routes = (
        config.get("mux_routes")
        or mux_settings.get("routes")
        or config.get("routes", {}).get("mux")
        or devices.get("arduino_mux", {}).get("routes", {})
    )
    if not isinstance(mux_routes, dict):
        mux_routes = {}
    if not mux_routes:
        if mux_disabled:
            warnings.append(
                "Arduino MUX is disabled and no MUX routes are active; "
                "scope/HF2LI observations must use direct wiring."
            )
        else:
            warnings.append(
                "No MUX routes are defined in hardware_configuration.yaml; "
                "Arduino MUX diagnostics must remain BLOCKED."
            )

    picoscope_settings = dict(devices.get("picoscope") or {})
    capture_settings = (
        picoscope_settings.get("capture_settings")
        or config.get("picoscope_settings")
        or config.get("acquisition", {}).get("picoscope")
    )
    if capture_settings:
        picoscope_settings["capture_settings"] = capture_settings
    recipe_driven_settings = (
        picoscope_settings.get("settings_source") == "workflow_recipe"
        and isinstance(picoscope_settings.get("capture_capabilities"), dict)
        and isinstance(
            picoscope_settings.get("capture_capabilities", {}).get(
                "recipe_required_fields"
            ),
            list,
        )
    )
    required_pico = {"resolution", "channels", "external_trigger"}
    if (
        not recipe_driven_settings
        and (
            not isinstance(capture_settings, dict)
            or not required_pico.issubset(capture_settings.keys())
        )
    ):
        warnings.append(
            "PicoScope model/serial may be present, but capture settings "
            "(resolution, channels, external_trigger) are incomplete and no "
            "workflow_recipe capability contract is defined."
        )

    if "arduino_mux" not in devices:
        warnings.append("arduino_mux device is missing")
    if "picoscope" not in devices:
        warnings.append("picoscope device is missing")

    iris = devices.get("opo_iris")
    if not isinstance(iris, dict):
        warnings.append("opo_iris device is missing")
    elif iris.get("qualification_status") != "qualified":
        warnings.append(
            "OPO iris is configured but remains unqualified until ATT-01 passes."
        )

    wavemaster = devices.get("wavemaster")
    if not isinstance(wavemaster, dict):
        warnings.append("wavemaster device is missing")
    else:
        required = wavemaster.get("phase_entry_required_fields") or []
        if not isinstance(required, list):
            warnings.append(
                "WaveMaster phase_entry_required_fields must be a list."
            )
        else:
            unresolved = [
                str(field)
                for field in required
                if wavemaster.get(str(field)) in (None, "", "[VALUE_REQUIRED]")
            ]
            if unresolved:
                warnings.append(
                    "WM-01 entry BLOCKED by [VALUE_REQUIRED] WaveMaster fields: "
                    + ", ".join(unresolved)
                )
    if not signal_map:
        raise HardwareConfigError("no configured T660 signal names were discovered")

    return ConfigInventory(
        config_path=str(Path(config_path).resolve()),
        schema_version=config.get("schema_version"),
        devices={name: dict(value or {}) for name, value in devices.items()},
        t660_devices={name: dict(value or {}) for name, value in t660_devices.items()},
        signal_map=signal_map,
        timing_routes=timing_routes,
        mux_settings=mux_settings,
        mux_routes=mux_routes,
        picoscope_settings=picoscope_settings,
        warnings=warnings,
    )


def write_inventory_files(
    inventory: ConfigInventory, output_dir: str | Path | None = None
) -> Path:
    """Write the human-readable configuration inventory."""

    target = Path(output_dir) if output_dir is not None else REPO_ROOT / "config"
    if not target.is_absolute():
        target = REPO_ROOT / target
    target.mkdir(parents=True, exist_ok=True)

    inventory_path = target / "config_inventory.txt"

    lines = [
        "Hardware Configuration Inventory",
        f"config_path: {inventory.config_path}",
        f"schema_version: {inventory.schema_version}",
        "",
        "Devices:",
    ]
    for name, info in sorted(inventory.devices.items()):
        label = info.get("display_name") or info.get("model") or name
        role = info.get("role", "unspecified")
        lines.append(f"- {name}: {label} ({role})")
    lines.extend(["", "T660 signal map:"])
    for signal, mapping in sorted(inventory.signal_map.items()):
        lines.append(f"- {signal}: {mapping['device']} channel {mapping['channel']}")
    lines.extend(["", "Timing routes:"])
    lines.append(json.dumps(inventory.timing_routes, indent=2, sort_keys=True))
    lines.extend(["", "Arduino MUX topology:"])
    lines.append(json.dumps(inventory.mux_settings, indent=2, sort_keys=True))
    lines.extend(["", "MUX routes:"])
    if inventory.mux_routes:
        for name in sorted(inventory.mux_routes):
            lines.append(f"- {name}: {json.dumps(inventory.mux_routes[name], sort_keys=True)}")
    else:
        lines.append("- NONE CONFIGURED")
    lines.extend(["", "PicoScope settings:"])
    lines.append(json.dumps(inventory.picoscope_settings, indent=2, sort_keys=True))
    lines.extend(["", "Warnings:"])
    if inventory.warnings:
        lines.extend(f"- {warning}" for warning in inventory.warnings)
    else:
        lines.append("- none")
    inventory_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return inventory_path


def load_config_inventory(
    path: str | Path | None = None, *, write_files: bool = False
) -> ConfigInventory:
    """Load, validate, and optionally persist the configuration inventory."""

    config, config_path, _ = load_hardware_config(path)
    inventory = build_config_inventory(config, config_path)
    if write_files:
        write_inventory_files(inventory)
    return inventory
