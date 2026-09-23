"""Executable v1 compatibility fixtures: independent packages, no science engines."""
from dataclasses import FrozenInstanceError, replace
import importlib
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import UUID

import pytest

from control_app.measurement_host import ContextFactory, ModuleDescriptor, create_registered_tabs, discover_modules
from control_app.measurement_host.contracts import ContractError, validate_descriptor
from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError, require_hardware_owner


FEATURES = (
    ("steady_state_slow_scan", "Slow Scan", "Dual-Detector Slow Scan"),
    ("fixed_wavenumber_kinetics", "Fixed-Wavenumber Kinetics", "Dual-Detector Fixed-Wavenumber Kinetics"),
    ("nanosecond_stroboscopy", "Nanosecond Stroboscopy", "Dual-Detector Nanosecond Stroboscopy"),
    ("microsecond_stroboscopy", "Microsecond Stroboscopy", "Dual-Detector Microsecond Stroboscopy"),
    ("repeated_rapid_scan", "Repeated Rapid-Scan Phase Delay", "Dual-Detector Repeated Rapid-Scan Phase Delay"),
    ("single_pump_scan_burst", "Single-Pump Scan Bursts", "Dual-Detector Single-Pump Scan Bursts"),
)


def test_operation_serialization_designates_tests_without_changing_settings(tmp_path):
    from uuid import uuid4
    from control_app.measurement_host.context import OperationSnapshot
    operation = OperationSnapshot(1, 'steady_state_slow_scan:single', str(uuid4()),
        str(uuid4()), '2026-09-23T00:00:00+00:00', False, {'delay_s': .00025},
        {}, (), (), tmp_path, tmp_path / 'run', None)
    record = operation.to_dict()
    assert record['result_classification'] == 'FUNCTIONALITY_TEST'
    assert record['publication_eligible'] is False
    assert record['runtime_calibration_eligible'] is False
    assert record['settings'] == {'delay_s': .00025}


@pytest.fixture
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


@pytest.fixture
def coordinator(tmp_path):
    return HardwareCoordinator(tmp_path / "instrument.lock")


@pytest.fixture
def independent_modules(tmp_path, monkeypatch):
    """Create the six future packages in a temporary import root, never production."""
    root = tmp_path / "compatibility_modules"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "_fixture.py").write_text('''
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from control_app.measurement_host import TabHandle

class DummyWidget(QWidget):
    state_changed = Signal(bool)
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.baseline = []
        self.review = []
        self.busy = False
        self.aborts = []
        self.output = None
        self.events = []
    def abort(self, reason): self.aborts.append(reason)
    def output_changed(self, path): self.output = path
    def instrument_changed(self, change): self.events.append(change)

def create_pair(context, titles):
    handles = []
    for mode, title in zip(('single', 'dual'), titles):
        scoped = context.for_mode(mode)
        widget = DummyWidget(scoped)
        handles.append(TabHandle(scoped.instance_id, title, widget,
            lambda w=widget: w.busy, lambda: (), widget.abort,
            widget.output_changed, widget.instrument_changed, widget.state_changed))
    return handles
''', encoding="utf-8")
    for order, (experiment_id, single, dual) in enumerate(FEATURES):
        path = root / experiment_id
        path.mkdir()
        (path / "__init__.py").write_text("", encoding="utf-8")
        (path / "registration.py").write_text(
            "from control_app.measurement_host import ModuleDescriptor\n"
            "def create_tabs(context):\n"
            "    from .._fixture import create_pair\n"
            f"    return create_pair(context, ({single!r}, {dual!r}))\n"
            f"DESCRIPTOR = ModuleDescriptor(1, {experiment_id!r}, {60-order}, create_tabs)\n",
            encoding="utf-8",
        )
    for name, source in {
        "broken_sdk": "raise ImportError('optional fixture SDK is absent')\n",
        "broken_system_exit": "raise SystemExit('optional fixture must not terminate the host')\n",
        "unsupported_api": "from control_app.measurement_host import ModuleDescriptor\nDESCRIPTOR=ModuleDescriptor(99, 'unsupported_api', 2, lambda c: ())\n",
        "invalid_factory": "from control_app.measurement_host import ModuleDescriptor\nDESCRIPTOR=ModuleDescriptor(1, 'invalid_factory', 2, lambda: ())\n",
    }.items():
        path = root / name
        path.mkdir()
        (path / "registration.py").write_text(source, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    yield "compatibility_modules"
    for name in tuple(sys.modules):
        if name == "compatibility_modules" or name.startswith("compatibility_modules."):
            del sys.modules[name]


def test_discovery_is_deterministic_lazy_and_fault_isolated(independent_modules):
    result = discover_modules(package_name=independent_modules)
    assert [item.experiment_id for item in result.descriptors] == [item[0] for item in reversed(FEATURES)]
    assert len(result.issues) == 4
    assert any("optional fixture SDK" in item.message for item in result.issues)
    assert any("Incompatible module API" in item.message for item in result.issues)
    assert any("incompatible signature" in item.message for item in result.issues)
    assert any("SystemExit" in item.message for item in result.issues)
    # Discovery hasn't imported the fixture widget, much less a device SDK.
    assert "compatibility_modules._fixture" not in sys.modules
    assert discover_modules(package_name=independent_modules) == result


def test_all_six_pairs_install_without_central_edits(qt_app, independent_modules, coordinator, tmp_path):
    accesses = []
    factory = ContextFactory(ownership=coordinator, save_root_provider=lambda: tmp_path,
                             real_device_factories={"device": lambda **kwargs: accesses.append("hardware")})
    result = create_registered_tabs(discover_modules(package_name=independent_modules), factory)
    assert len(result.handles) == 12
    assert len(result.issues) == 4
    assert len({handle.title for handle in result.handles}) == 12
    assert {handle.instance_id for handle in result.handles} == {
        f"{experiment_id}:{mode}" for experiment_id, _, _ in FEATURES for mode in ("single", "dual")}
    assert accesses == []
    assert not coordinator.lock_path.exists()
    first, second = result.handles[:2]
    first.widget.baseline.append("one baseline")
    first.widget.review.append("one review")
    first.request_abort("this tab only")
    assert second.widget.baseline == second.widget.review == second.widget.aborts == []
    for handle in result.handles:
        handle.widget.deleteLater()


def test_invalid_pairs_titles_and_existing_ids_fail_atomically(qt_app, independent_modules, coordinator):
    discovery = discover_modules(package_name=independent_modules)
    descriptor = discovery.descriptors[0]
    factory = ContextFactory(ownership=coordinator)
    conflict = create_registered_tabs([descriptor], factory, existing_titles=[FEATURES[-1][1]])
    assert not conflict.handles and "Duplicate top-level" in conflict.issues[0].message
    existing = create_registered_tabs([descriptor], factory,
                                     existing_instance_ids=[descriptor.experiment_id + ":single"])
    assert not existing.handles and "Duplicate experiment" in existing.issues[0].message
    original = descriptor.create_tabs
    invalid = replace(descriptor, create_tabs=lambda context: original(context)[:1])
    result = create_registered_tabs([invalid], factory)
    assert not result.handles and "exactly two" in result.issues[0].message
    def wrong_callback(context):
        pair = original(context)
        pair[0] = replace(pair[0], request_abort=lambda: None)
        return pair
    result = create_registered_tabs([replace(descriptor, create_tabs=wrong_callback)], factory)
    assert not result.handles and "request_abort has an incompatible signature" in result.issues[0].message
    def exits(context):
        raise SystemExit("broken widget")
    result = create_registered_tabs([replace(descriptor, create_tabs=exits), discovery.descriptors[1]], factory)
    assert len(result.handles) == 2 and "SystemExit: broken widget" in result.issues[0].message
    for handle in result.handles:
        handle.widget.deleteLater()


def test_construction_cannot_acquire_hardware(qt_app, coordinator):
    def illegal(context):
        context.for_mode("single").begin_operation({}, hardware=True)
    result = create_registered_tabs([ModuleDescriptor(1, "construction_check", 0, illegal)],
                                    ContextFactory(ownership=coordinator))
    assert not result.handles and "during module construction" in result.issues[0].message
    assert not coordinator.lock_path.exists()


def test_descriptor_immutable_and_strict():
    descriptor = ModuleDescriptor(1, "test_measurement", 0, lambda context: ())
    with pytest.raises(FrozenInstanceError):
        descriptor.experiment_id = "changed"
    with pytest.raises(ContractError, match="Incompatible"):
        validate_descriptor(replace(descriptor, api_version=True))
    with pytest.raises(ContractError, match="directory ID"):
        validate_descriptor(descriptor, directory_id="another_id")


def test_context_preferences_and_operation_inputs_are_isolated(coordinator, tmp_path):
    config = {"devices": {"sample": [1, 2]}}
    preferences = {}
    destination = [tmp_path / "first"]
    factory = ContextFactory(ownership=coordinator, configuration_provider=lambda: config,
                             preference_backend=preferences, save_root_provider=lambda: destination[0])
    contexts = [factory.for_experiment(experiment_id).for_mode(mode)
                for experiment_id, _, _ in FEATURES for mode in ("single", "dual")]
    for index, context in enumerate(contexts):
        context.preferences.setValue("settings", {"value": [index]})
    assert len(preferences) == 12
    for index, context in enumerate(contexts):
        value = context.preferences.value("settings")
        value["value"].append("changed")
        assert context.preferences.value("settings") == {"value": [index]}
        assert context.preferences.namespace == f"measurements/{context.experiment_id}/{context.mode}/v1/"
        with pytest.raises(AttributeError):
            context.preferences.namespace = "global/"
        with pytest.raises(ContractError):
            context.preferences.setValue("../../global", 4)
    context = contexts[0]
    with pytest.raises(AttributeError):
        context.experiment_id = "different_experiment"
    with pytest.raises(AttributeError):
        context.ownership.instance_id = contexts[1].instance_id
    settings, sample = {"gain": [1]}, {"sample": {"id": "source"}}
    plan = context.new_plan(settings)
    run = context.begin_operation(plan=plan, sample_records=[sample])
    settings["gain"].append(4)
    sample["sample"]["id"] = "changed"
    config["devices"]["sample"].append(3)
    destination[0] = tmp_path / "second"
    assert run.settings["gain"] == (1,)
    assert run.sample_records[0]["sample"]["id"] == "source"
    assert run.configuration["devices"]["sample"] == (1, 2)
    assert run.save_root == (tmp_path / "first").resolve()
    assert run.output_path.parent == run.save_root / "measurements" / context.experiment_id / "single"
    assert not run.output_path.exists()
    with pytest.raises(TypeError):
        run.settings["gain"] = [9]
    UUID(run.plan_id)
    UUID(run.run_id)
    assert run.plan_id != run.run_id
    another = context.begin_operation(plan=plan)
    assert another.run_id != run.run_id and another.output_path != run.output_path
    assert another.plan_id == run.plan_id
    with pytest.raises(ContractError, match="cannot cross"):
        contexts[1].begin_operation(plan=plan)
    assert run.to_dict()["settings"] == {"gain": [1]}


def test_real_factories_require_owner_and_simulation_stays_independent(coordinator, tmp_path):
    calls = []
    configuration_source = {"devices": {"test": {"serial": "original"}}}
    def real_factory(*, configuration):
        calls.append(require_hardware_owner().instance_id)
        assert configuration["devices"]["test"]["serial"] == "original"
        configuration["devices"]["test"]["serial"] = "factory mutation"
        return object()
    factory = ContextFactory(ownership=coordinator, save_root_provider=lambda: tmp_path,
                             configuration_provider=lambda: configuration_source,
                             real_device_factories={"test": real_factory},
                             simulated_device_factories={"test": lambda **kwargs: object()})
    single = factory.for_experiment("sample_method").for_mode("single")
    dual = factory.for_experiment("sample_method").for_mode("dual")
    run = single.begin_operation({}, hardware=True, purpose="explicit capability discovery")
    configuration_source["devices"]["test"]["serial"] = "later edit"
    try:
        assert coordinator.snapshot()["owner"]["operation_id"] == run.run_id
        single.devices.create("test", run)
        assert run.configuration["devices"]["test"]["serial"] == "original"
        assert calls == ["sample_method:single"]
        with pytest.raises(OwnershipError):
            dual.begin_operation({}, hardware=True)
        simulation = dual.begin_operation({})
        dual.devices.create("test", simulation)
        assert calls == ["sample_method:single"]
        with pytest.raises(ContractError):
            dual.devices.create("test", run)
        with pytest.raises(RuntimeError, match="another tab"):
            dual.ownership.release(run.ownership, safe_verified=True)
    finally:
        single.ownership.release(run.ownership, safe_verified=True)
    with pytest.raises(OwnershipError):
        single.devices.create("test", run)
    assert calls == ["sample_method:single"]


def test_offline_begin_ignores_hardware_start_blockers(coordinator):
    hooks = SimpleNamespace(before_start=lambda instance: "Another tab owns hardware")
    context = ContextFactory(ownership=coordinator, lifecycle=hooks).for_experiment("offline_check").for_mode("dual")
    assert not context.begin_operation({}).hardware
    with pytest.raises(RuntimeError, match="Another tab"):
        context.begin_operation({}, hardware=True)
