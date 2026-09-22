"""Compatibility import; implementation lives in measurement_modules.phase_scan."""
from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("control_app.measurement_modules.phase_scan.dual_detector_phase_scan_runner")
