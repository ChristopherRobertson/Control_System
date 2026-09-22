"""The established Phase Scan is discoverable without duplicating its implementation."""
from importlib import import_module

import pytest


@pytest.mark.parametrize("old,new", [
    *((f"control_app.workflows.{name}", f"control_app.measurement_modules.phase_scan.{name}")
      for name in ("regular_phase_scan", "regular_phase_scan_acquisition", "regular_phase_scan_data",
                   "regular_phase_scan_runner", "dual_detector_phase_scan", "dual_detector_phase_scan_acquisition",
                   "dual_detector_phase_scan_data", "dual_detector_phase_scan_runner")),
    ("control_app.ui.widgets.phase_scan_widget", "control_app.measurement_modules.phase_scan.widgets"),
    ("control_app.ui.widgets.phase_scan_surface", "control_app.measurement_modules.phase_scan.surface"),
])
def test_old_imports_resolve_to_same_module_and_runtime_state(old, new):
    assert import_module(old) is import_module(new)


def test_phase_scan_registered_once_and_redundant_tab_retired():
    from control_app.measurement_host.registry import discover_modules
    from control_app.measurement_modules.phase_scan.registration import DESCRIPTOR
    discovered = discover_modules()
    assert not discovered.issues
    assert [d for d in discovered.descriptors if d.experiment_id == "phase_scan"] == [DESCRIPTOR]
    assert not any(d.experiment_id == "single_pump_scan_burst" for d in discovered.descriptors)
    # Retirement of the tab must not make historic saved records unreadable.
    assert import_module("control_app.measurement_modules.single_pump_scan_burst.persistence")
