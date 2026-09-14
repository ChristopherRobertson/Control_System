"""Visible names/order remain separate from stable module and detector IDs."""
from importlib import import_module
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from control_app.measurement_host.naming import EXPERIMENT_ORDER, EXPERIMENT_TITLES, tab_title


EXPECTED = (
    ("steady_state_slow_scan", "Slow Scan"),
    ("fixed_wavenumber_kinetics", "Fixed Wavenumber"),
    ("nanosecond_stroboscopy", "Nanosecond Stroboscopy"),
    ("microsecond_stroboscopy", "Microsecond Stroboscopy"),
    ("single_pump_scan_burst", "Single Scan Phase Delay"),
    ("repeated_rapid_scan", "Rapid Scan Phase Delay"),
)


def _context(experiment_id):
    # Only the registration boundary is exercised: no configuration, preferences,
    # coordinator, Qt widget, SDK or native record is instantiated.
    return SimpleNamespace(for_mode=lambda mode: SimpleNamespace(
        instance_id=f"{experiment_id}:{mode}", preferences=object(),
        save_root=lambda: Path("unused-test-destination")))


def test_exact_visible_order_titles_and_legacy_fallback():
    assert EXPERIMENT_ORDER == tuple(experiment_id for experiment_id, _ in EXPECTED)
    for experiment_id, title in EXPECTED:
        assert EXPERIMENT_TITLES[experiment_id] == title
        assert tab_title(experiment_id, "single") == title
        assert tab_title(experiment_id, "dual") == f"DD {title}"
    assert tab_title("phase_scan", "single") == "Phase Scan"
    assert tab_title("phase_scan", "dual") == "DD Phase Scan"
    assert tab_title("optional_example", "single") == "Optional Example"
    assert tab_title("optional_example", "dual") == "DD Optional Example"
    with pytest.raises(ValueError, match="detector mode"):
        tab_title("steady_state_slow_scan", "other")


def test_six_registrations_use_requested_titles_and_order_without_changing_ids(monkeypatch):
    descriptors = []
    for experiment_id, title in EXPECTED:
        package = f"control_app.measurement_modules.{experiment_id}"
        registration = import_module(package + ".registration")
        descriptor = registration.DESCRIPTOR
        assert descriptor.api_version == 1
        assert descriptor.experiment_id == experiment_id
        monkeypatch.setitem(sys.modules, package + ".widgets", SimpleNamespace(
            make_handle=lambda context, title: SimpleNamespace(instance_id=context.instance_id, title=title)))
        single, dual = descriptor.create_tabs(_context(experiment_id))
        assert (single.instance_id, single.title) == (f"{experiment_id}:single", title)
        assert (dual.instance_id, dual.title) == (f"{experiment_id}:dual", f"DD {title}")
        descriptors.append(descriptor)
    assert tuple(item.experiment_id for item in sorted(descriptors, key=lambda item: item.display_order)) == EXPERIMENT_ORDER
    assert len({item.display_order for item in descriptors}) == 6


def test_legacy_adapter_changes_only_visible_titles(monkeypatch):
    from control_app.measurement_host.legacy_phase_scan import create_phase_scan_tabs

    class FakePhaseWidget:
        def __init__(self, **kwargs):
            self.options = kwargs
            self.busy_changed = object()
        def command_running(self): return False
        def close_blockers(self): return ()
        def request_abort(self, reason): pass
        def output_location_changed(self, path): pass
        def instrument_state_changed(self, change): pass

    monkeypatch.setitem(sys.modules, "control_app.ui.widgets.phase_scan_widget",
                        SimpleNamespace(PhaseScanWidget=FakePhaseWidget))
    single_runner, dual_runner = object(), object()
    single, dual = create_phase_scan_tabs(_context("phase_scan"), single_runner=single_runner,
                                          dual_runner=dual_runner)
    assert (single.instance_id, single.title) == ("phase_scan:single", "Phase Scan")
    assert (dual.instance_id, dual.title) == ("phase_scan:dual", "DD Phase Scan")
    assert single.widget.options["runner"] is single_runner
    assert dual.widget.options["runner"] is dual_runner
    assert single.widget.options["dual_detector"] is False
    assert dual.widget.options["dual_detector"] is True
