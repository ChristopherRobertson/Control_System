#!/usr/bin/env python3
"""Verify Arduino MUX and PicoScope diagnostics remain independent.

Usage:
    python software/tests/hardware_checks/check_independent_arduino_mux_and_scope_paths.py

This check does not open hardware. It fails if legacy combined diagnostic files
are present, if the Arduino MUX check imports PicoScope services, if the
PicoScope check imports Arduino MUX services, or if the wiring map assigns MUX
board ownership to PicoScope channels.
"""

from __future__ import annotations

from _common import REPO_ROOT

import ast
from pathlib import Path

import yaml


LEGACY_FILENAMES = (
    "arduino_" + "mux_" + "diagnostic_" + "test.py",
    "check_" + "mux_" + "picoscope" + "_capture.py",
    "mux_" + "pico" + "_diagnostic.py",
)
COMBINED_TEXT_TOKENS = (
    "mux_" + "pico",
    "MUX" + "/" + "Pico",
    "Pico" + "/" + "MUX",
    "picoscope_" + "mux",
    "mux_" + "picoscope",
    "check_" + "mux_" + "picoscope",
    "picoscope_" + "input",
    "set_ch_" + "a_route",
    "set_ch_" + "b_route",
    "set_ext_" + "route",
)
ACTIVE_TEXT_PATHS = (
    REPO_ROOT / "control_app",
    REPO_ROOT / "tests",
    REPO_ROOT / "instrument" / "recipes",
    REPO_ROOT / "hardware_configuration.yaml",
    REPO_ROOT / "wiring_map.yaml",
    REPO_ROOT / "docs" / "ui_hardware_control_reference.md",
)
ARDUINO_MUX_SOURCE_FILES = (
    REPO_ROOT / "tests" / "hardware_checks" / "check_arduino_mux_diagnostic.py",
    REPO_ROOT / "control_app" / "workflows" / "arduino_mux_diagnostic.py",
    REPO_ROOT / "control_app" / "devices" / "arduino_mux_service.py",
)
PICOSCOPE_SOURCE_FILES = (
    REPO_ROOT / "tests" / "hardware_checks" / "check_picoscope_settings_apply.py",
    REPO_ROOT / "control_app" / "workflows" / "picoscope_settings_test.py",
    REPO_ROOT / "control_app" / "devices" / "picoscope_service.py",
)


def main() -> int:
    failures: list[str] = []
    failures.extend(_legacy_file_failures())
    failures.extend(_active_text_failures())
    failures.extend(_forbidden_import_failures())
    failures.extend(_wiring_map_failures())

    if failures:
        print("BLOCKED Arduino MUX and PicoScope separation failures:")
        for failure in failures:
            print(f"- {failure}")
        return 2
    print("PASS Arduino MUX and PicoScope diagnostics are separated")
    return 0


def _legacy_file_failures() -> list[str]:
    failures: list[str] = []
    for filename in LEGACY_FILENAMES:
        matches = [path for path in REPO_ROOT.rglob(filename) if ".git" not in path.parts]
        failures.extend(f"legacy combined or ambiguous file still exists: {path}" for path in matches)
    return failures


def _active_text_failures() -> list[str]:
    failures: list[str] = []
    for root in ACTIVE_TEXT_PATHS:
        paths = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in paths:
            if not path.is_file() or ".git" in path.parts or path.suffix not in {".py", ".yaml", ".yml", ".md"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for token in COMBINED_TEXT_TOKENS:
                if token in text:
                    failures.append(f"{path}: legacy combined token {token!r}")
    return failures


def _forbidden_import_failures() -> list[str]:
    failures: list[str] = []
    for path in ARDUINO_MUX_SOURCE_FILES:
        failures.extend(_module_import_failures(path, forbidden_terms=("picoscope", "PicoScope")))
    for path in PICOSCOPE_SOURCE_FILES:
        failures.extend(_module_import_failures(path, forbidden_terms=("arduino_mux", "ArduinoMux")))
    return failures


def _module_import_failures(path: Path, *, forbidden_terms: tuple[str, ...]) -> list[str]:
    failures: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(term in alias.name for term in forbidden_terms):
                    failures.append(f"{path}:{node.lineno}: forbidden import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            if any(term in node.module for term in forbidden_terms):
                failures.append(f"{path}:{node.lineno}: forbidden import from {node.module}")
    return failures


def _wiring_map_failures() -> list[str]:
    path = REPO_ROOT / "wiring_map.yaml"
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    mux_boards = data.get("mux_boards")
    if not isinstance(mux_boards, dict):
        return ["wiring_map.yaml does not define mux_boards"]
    mux_subsystem = data.get("mux_subsystem") if isinstance(data.get("mux_subsystem"), dict) else {}
    mux_disabled = mux_subsystem.get("active") is False

    expected_outputs = {
        "dmb1": "output_a",
        "amb1": "output_a",
        "dmb2": "output_b",
        "amb2": "output_b",
        "dmb3": "output_ext",
    }
    failures: list[str] = []
    for board, expected_output in expected_outputs.items():
        board_config = mux_boards.get(board)
        if not isinstance(board_config, dict):
            failures.append(f"wiring_map.yaml mux_boards.{board} is missing")
            continue
        if mux_disabled and board_config.get("active") is not False:
            failures.append(f"wiring_map.yaml mux_boards.{board}.active must be false while MUX is bypassed")
        role = str(board_config.get("role") or "")
        if "picoscope" in role.lower():
            failures.append(f"wiring_map.yaml mux_boards.{board}.role still assigns MUX ownership to PicoScope")
        if board_config.get("mux_output") != expected_output:
            failures.append(
                f"wiring_map.yaml mux_boards.{board}.mux_output must be {expected_output!r}"
            )
        if "output" in board_config:
            failures.append(
                f"wiring_map.yaml mux_boards.{board} must use mux_output, not legacy output"
            )
    if mux_disabled:
        mux_control = data.get("arduino_mux_control")
        if not isinstance(mux_control, dict) or mux_control.get("active") is not False:
            failures.append("wiring_map.yaml arduino_mux_control.active must be false while MUX is bypassed")
        breakouts = data.get("breakouts") if isinstance(data.get("breakouts"), dict) else {}
        hf2li_breakout = breakouts.get("hf2li_dio_breakout") if isinstance(breakouts.get("hf2li_dio_breakout"), dict) else {}
        if "outputs_to_muxes" in hf2li_breakout:
            failures.append(
                "wiring_map.yaml hf2li_dio_breakout must not expose active outputs_to_muxes while MUX is bypassed"
            )
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
