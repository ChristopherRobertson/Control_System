#!/usr/bin/env python3
"""Scan UI code for forbidden direct hardware imports.

Usage:
    python software/tests/hardware_checks/check_forbidden_ui_imports.py

UI files may dispatch workflow commands, but must not import serial, sockets,
SDKs, Pico, LabOne, MIRcat, T660, Arduino, or project device services directly.
"""

from __future__ import annotations

from _common import REPO_ROOT

import ast


FORBIDDEN_MODULES = {
    "serial",
    "socket",
    "ctypes",
    "picosdk",
    "zhinst",
    "control_app.devices",
}
FORBIDDEN_TEXT = {
    "MIRcatSDK",
    "mircat_service",
    "t660_service",
    "arduino_mux_service",
    "picoscope_service",
    "LabOne",
}


def _root_name(name: str) -> str:
    parts = name.split(".")
    if len(parts) >= 2 and parts[0] == "control_app" and parts[1] == "devices":
        return "control_app.devices"
    return parts[0]


def main() -> int:
    ui_dir = REPO_ROOT / "control_app" / "ui"
    failures: list[str] = []
    for path in sorted(ui_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_TEXT:
            if token in text:
                failures.append(f"{path}: forbidden token {token!r}")
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = _root_name(alias.name)
                    if root in FORBIDDEN_MODULES:
                        failures.append(f"{path}:{node.lineno}: forbidden import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = _root_name(node.module)
                if root in FORBIDDEN_MODULES:
                    failures.append(f"{path}:{node.lineno}: forbidden import from {node.module}")

    if failures:
        print("BLOCKED forbidden UI imports found:")
        for failure in failures:
            print(f"- {failure}")
        return 2
    print("PASS no forbidden UI hardware imports found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

