#!/usr/bin/env python3
"""Load and validate hardware_configuration.yaml.

Usage:
    python software/tests/hardware_checks/check_config_inventory.py

This check does not open hardware connections. It fails when the required
read-only configuration cannot be loaded, lacks configured devices/T660 maps, or
mixes PicoScope identity with Arduino MUX/timing route ownership.
"""

from __future__ import annotations

from _common import REPO_ROOT

from control_app.config_loader import (
    HardwareConfigError,
    load_config_inventory,
    load_hardware_config,
    write_inventory_files,
)


LEGACY_COMBINED_MUX_KEY = "diagnostic" + "_mux"
LEGACY_ROUTE_TARGET_KEY = "picoscope" + "_input"
LEGACY_SOURCE_BOARD_KEY = "source" + "_mux_boards"
LEGACY_PICO_CONNECTOR_SECTION = "picoscope" + "_inputs"


def main() -> int:
    try:
        inventory = load_config_inventory(write_files=True)
        write_inventory_files(inventory, REPO_ROOT / "instrument" / "schemas")
        config, _, _ = load_hardware_config()
        _validate_independent_mux_and_picoscope(config)
    except HardwareConfigError as exc:
        print(f"BLOCKED: {exc}")
        return 2
    print(f"PASS config_path={inventory.config_path}")
    print("PASS configuration inventory loaded")
    for warning in inventory.warnings:
        print(f"WARNING {warning}")
    return 0


def _validate_independent_mux_and_picoscope(config) -> None:
    devices = config.get("devices") or {}
    picoscope = devices.get("picoscope") or {}
    if isinstance(picoscope, dict) and "routing_alignment" in picoscope:
        raise HardwareConfigError(
            "devices.picoscope must not contain routing_alignment; use timing_routes "
            "and arduino_mux_topology instead"
        )

    timing_routes = config.get("timing_routes")
    if not isinstance(timing_routes, dict):
        raise HardwareConfigError("timing_routes section is required")
    direct_destinations = timing_routes.get("direct_ttl_destinations")
    if not isinstance(direct_destinations, dict) or not direct_destinations:
        raise HardwareConfigError("timing_routes.direct_ttl_destinations is required")
    if timing_routes.get("mux_routes_t660_ttl") is not False:
        raise HardwareConfigError("timing_routes.mux_routes_t660_ttl must be false")

    if LEGACY_COMBINED_MUX_KEY in config:
        raise HardwareConfigError(
            "legacy combined MUX topology key is not allowed; use arduino_mux_topology "
            "so the MUX is not owned by PicoScope diagnostics"
        )

    mux_topology = config.get("arduino_mux_topology")
    if not isinstance(mux_topology, dict):
        raise HardwareConfigError("arduino_mux_topology section is required")
    mux_disabled = _arduino_mux_disabled(config)
    if mux_disabled and mux_topology.get("enabled") is not False:
        raise HardwareConfigError(
            "arduino_mux_topology.enabled must be false while devices.arduino_mux is disabled"
        )
    if mux_topology.get("controller_device") != "arduino_mux":
        raise HardwareConfigError("arduino_mux_topology.controller_device must be arduino_mux")
    if "observed_by_device" in mux_topology or "inputs_section" in mux_topology:
        raise HardwareConfigError(
            "arduino_mux_topology must not define observed_by_device or inputs_section"
        )

    if LEGACY_PICO_CONNECTOR_SECTION in config:
        raise HardwareConfigError(
            "legacy PicoScope connector section name is not allowed; use "
            "picoscope_connectors"
        )

    pico_connectors = config.get("picoscope_connectors") or {}
    if isinstance(pico_connectors, dict):
        for name, value in pico_connectors.items():
            if isinstance(value, dict) and LEGACY_SOURCE_BOARD_KEY in value:
                raise HardwareConfigError(
                    f"picoscope_connectors.{name} legacy source-board mapping is not allowed; "
                    "MUX board ownership belongs under arduino_mux_topology.outputs"
                )

    mux_routes = config.get("mux_routes")
    if mux_disabled:
        if mux_routes not in ({}, None):
            raise HardwareConfigError(
                "mux_routes must be empty while Arduino MUX is disabled/bypassed"
            )
        return
    if not isinstance(mux_routes, dict):
        raise HardwareConfigError("mux_routes section is required")
    allowed_outputs = set((mux_topology.get("outputs") or {}).keys())
    if not allowed_outputs:
        raise HardwareConfigError("arduino_mux_topology.outputs is required")
    diagnostic = mux_routes.get("diagnostic") or {}
    required_defaults = {"output_a_route", "output_b_route", "output_ext_route"}
    if not isinstance(diagnostic, dict) or not required_defaults.issubset(diagnostic.keys()):
        raise HardwareConfigError(
            "mux_routes.diagnostic must define output_a_route, output_b_route, and output_ext_route"
        )
    for route_name, route_config in mux_routes.items():
        if route_name == "diagnostic":
            continue
        if not isinstance(route_config, dict):
            raise HardwareConfigError(f"mux_routes.{route_name} must be a mapping")
        if LEGACY_ROUTE_TARGET_KEY in route_config:
            raise HardwareConfigError(
                f"mux_routes.{route_name} legacy PicoScope route-target key is not allowed; use mux_output"
            )
        mux_output = route_config.get("mux_output")
        if mux_output not in allowed_outputs:
            raise HardwareConfigError(
                f"mux_routes.{route_name}.mux_output {mux_output!r} is not one of "
                f"{sorted(allowed_outputs)!r}"
            )


def _arduino_mux_disabled(config) -> bool:
    devices = config.get("devices") or {}
    mux_device = devices.get("arduino_mux")
    mux_topology = config.get("arduino_mux_topology")
    return (
        isinstance(mux_device, dict)
        and mux_device.get("enabled") is False
    ) or (
        isinstance(mux_topology, dict)
        and mux_topology.get("enabled") is False
    )


if __name__ == "__main__":
    raise SystemExit(main())
