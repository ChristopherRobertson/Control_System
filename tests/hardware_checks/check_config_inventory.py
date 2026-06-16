#!/usr/bin/env python3
"""Load and hash hardware_configuration.yaml.

Usage:
    python tests/hardware_checks/check_config_inventory.py

This check does not open hardware connections. It fails only when the required
read-only configuration cannot be loaded or lacks configured devices/T660 maps.
"""

from __future__ import annotations

from _common import REPO_ROOT

from control_app.config_loader import HardwareConfigError, load_config_inventory, write_inventory_files


def main() -> int:
    try:
        inventory = load_config_inventory(write_files=True)
        write_inventory_files(inventory, REPO_ROOT / "config")
    except HardwareConfigError as exc:
        print(f"BLOCKED: {exc}")
        return 2
    print(f"PASS config_path={inventory.config_path}")
    print(f"PASS config_hash={inventory.config_hash}")
    for warning in inventory.warnings:
        print(f"WARNING {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

