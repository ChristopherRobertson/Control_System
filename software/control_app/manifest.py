"""Run manifest helpers for hardware actions and blocker records."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import json

from .config_loader import ConfigInventory, load_config_inventory
from .paths import INSTRUMENT_ROOT


REQUIRED_FIELDS = [
    "config_path",
    "operator",
    "timestamp_utc",
    "device_ids",
    "t660_recipes",
    "mux_routes",
    "mircat_setpoint",
    "mircat_actual_wavelength",
    "hf2li_settings_snapshot",
    "picoscope_settings",
    "timing_offset_file",
    "raw_data_paths",
    "command_log_paths",
    "device_readback_paths",
    "error_state",
    "abort_state",
    "blocker_status",
]


def _device_ids(inventory: ConfigInventory) -> dict[str, Any]:
    ids: dict[str, Any] = {}
    for name, info in inventory.devices.items():
        ids[name] = {
            key: info.get(key)
            for key in (
                "display_name",
                "role",
                "serial_number",
                "device_id",
                "model",
                "model_number",
                "preferred_port",
            )
            if key in info
        }
    return ids


def new_manifest(
    *,
    operator: str,
    inventory: ConfigInventory | None = None,
    device_ids: dict[str, Any] | None = None,
    t660_recipes: list[str] | dict[str, Any] | None = None,
    mux_routes: dict[str, Any] | None = None,
    mircat_setpoint: Any = None,
    mircat_actual_wavelength: Any = None,
    hf2li_settings_snapshot: dict[str, Any] | None = None,
    picoscope_settings: dict[str, Any] | None = None,
    timing_offset_file: str | None = None,
    raw_data_paths: list[str] | None = None,
    command_log_paths: list[str] | None = None,
    device_readback_paths: list[str] | None = None,
    error_state: dict[str, Any] | None = None,
    abort_state: dict[str, Any] | None = None,
    blocker_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a complete manifest dictionary with all required fields."""

    inv = inventory or load_config_inventory(write_files=False)
    return {
        "config_path": inv.config_path,
        "operator": operator,
        "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "device_ids": device_ids if device_ids is not None else _device_ids(inv),
        "t660_recipes": t660_recipes or [],
        "mux_routes": mux_routes or {},
        "mircat_setpoint": mircat_setpoint,
        "mircat_actual_wavelength": mircat_actual_wavelength,
        "hf2li_settings_snapshot": hf2li_settings_snapshot or {},
        "picoscope_settings": picoscope_settings or {},
        "timing_offset_file": timing_offset_file,
        "raw_data_paths": raw_data_paths or [],
        "command_log_paths": command_log_paths or [],
        "device_readback_paths": device_readback_paths or [],
        "error_state": error_state or {"has_error": False, "errors": []},
        "abort_state": abort_state or {"aborted": False, "reason": None},
        "blocker_status": blocker_status
        or {"blocked": False, "blockers": [], "next_actions": []},
    }


def validate_manifest(path_or_data: str | Path | dict[str, Any]) -> dict[str, Any]:
    """Validate a manifest against instrument/schemas/run_manifest.schema.json."""

    if isinstance(path_or_data, (str, Path)):
        with Path(path_or_data).open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    else:
        data = dict(path_or_data)

    schema_path = INSTRUMENT_ROOT / "schemas" / "run_manifest.schema.json"
    if schema_path.exists():
        try:
            import jsonschema
        except ImportError as exc:
            raise ValueError("jsonschema is required to validate run manifests") from exc
        with schema_path.open("r", encoding="utf-8") as handle:
            schema = json.load(handle)
        jsonschema.validate(data, schema)
    else:
        missing = [field for field in REQUIRED_FIELDS if field not in data]
        if missing:
            raise ValueError(f"manifest missing required fields: {missing}")
    return data


def write_manifest(path: str | Path, data: dict[str, Any]) -> Path:
    """Validate and write a manifest JSON file."""

    manifest = validate_manifest(data)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
