"""Per-tab destinations without startup writes or cross-operation retargeting."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from control_app import paths
from control_app.measurement_host.context import ContextFactory
from control_app.measurement_host.contracts import ContractError


@pytest.fixture
def private_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RUN_ROOT", tmp_path / "runs")
    monkeypatch.setattr(paths, "_selected_save_location", None)
    day = [date(2026, 9, 14)]
    monkeypatch.setattr(paths, "date", SimpleNamespace(today=lambda: day[0]))
    return day


def test_default_tab_path_preserves_display_name_and_follows_local_date(private_paths):
    title = "Phase Scan - Dual Detector"
    first = paths.default_tab_save_location(title)
    assert first == paths.RUN_ROOT / "2026-09-14" / title
    private_paths[0] = date(2026, 9, 15)
    assert paths.default_tab_save_location(title) == paths.RUN_ROOT / "2026-09-15" / title
    assert not paths.RUN_ROOT.exists()


@pytest.mark.parametrize("title", ["", " ", ".", "..", "../Phase Scan", "Phase/Scan", "Phase\\Scan",
    "C:Phase Scan", "Phase: Scan", "Phase Scan.", "Phase Scan ", " Phase Scan", "Phase\nScan",
    "Phase*Scan", "Phase?Scan", "Phase|Scan", 'Phase"Scan', "Phase<Scan>", "CON", "aux.json",
    "LPT1", "COM¹", "a" * 256, None])
def test_default_tab_path_rejects_unsafe_segments(private_paths, title):
    with pytest.raises(ValueError, match="single path segment"):
        paths.default_tab_save_location(title)
    assert not paths.RUN_ROOT.exists()


def test_default_and_idle_selection_make_no_directory_or_write_probes(private_paths, monkeypatch):
    import tempfile

    def forbidden(*args, **kwargs):
        raise AssertionError("Idle tab selection must not access the filesystem")

    with monkeypatch.context() as guard:
        for method in ("resolve", "mkdir", "is_dir", "exists", "stat"):
            guard.setattr(Path, method, forbidden)
        guard.setattr(tempfile, "TemporaryFile", forbidden)
        destination = paths.default_tab_save_location("Slow Scan - Single Detector")
        selected = paths.set_save_location(destination, create=False)
        assert selected == destination
        assert paths.get_save_location() == destination
    assert not paths.RUN_ROOT.exists()


def test_explicit_selection_still_creates_and_checks_write_access(private_paths, monkeypatch):
    import tempfile

    original = tempfile.TemporaryFile
    probes = []

    def probe(*args, **kwargs):
        probes.append(kwargs["dir"])
        return original(*args, **kwargs)

    monkeypatch.setattr(tempfile, "TemporaryFile", probe)
    destination = paths.default_tab_save_location("Phase Scan - Single Detector")
    assert paths.set_save_location(destination) == destination
    assert destination.is_dir()
    assert probes == [destination]
    assert list(destination.iterdir()) == []


def test_failed_write_probe_does_not_replace_selected_root(private_paths, monkeypatch):
    import tempfile

    previous = paths.set_save_location(paths.RUN_ROOT / "previous", create=False)

    def denied(*args, **kwargs):
        raise PermissionError("Injected destination is not writable")

    monkeypatch.setattr(tempfile, "TemporaryFile", denied)
    with pytest.raises(PermissionError, match="not writable"):
        paths.set_save_location(paths.RUN_ROOT / "denied")
    assert paths.get_save_location() == previous


def test_instance_roots_and_run_folders_freeze_before_tab_or_date_changes(private_paths):
    names = {"phase_scan:single": "Phase Scan - Single Detector",
             "phase_scan:dual": "Phase Scan - Dual Detector",
             "steady_state_slow_scan:single": "Slow Scan - Single Detector"}
    overrides, calls = {}, []

    def root(instance_id):
        calls.append(instance_id)
        return overrides.get(instance_id, paths.default_tab_save_location(names[instance_id]))

    def forbidden_global_root():
        raise AssertionError("Scoped root must not use the selected global tab")

    factory = ContextFactory(ownership=object(), preference_backend={},
        save_root_provider=forbidden_global_root, instance_save_root_provider=root)
    single = factory.for_experiment("phase_scan").for_mode("single")
    dual = factory.for_experiment("phase_scan").for_mode("dual")
    slow = factory.for_experiment("steady_state_slow_scan").for_mode("single")
    first = single.begin_operation({"kind": "sample"})
    assert calls == [single.instance_id]
    assert first.output_path == first.save_root / first.run_id
    assert first.save_root == paths.RUN_ROOT / "2026-09-14" / names[single.instance_id]
    UUID(first.output_path.name)
    paths.set_save_location(paths.default_tab_save_location(names[dual.instance_id]), create=False)
    private_paths[0] = date(2026, 9, 15)
    overrides[single.instance_id] = paths.RUN_ROOT / "custom single"
    later = single.begin_operation({})
    other = dual.begin_operation({})
    third = slow.begin_operation({})
    assert later.save_root == overrides[single.instance_id]
    assert other.save_root == paths.RUN_ROOT / "2026-09-15" / names[dual.instance_id]
    assert third.save_root == paths.RUN_ROOT / "2026-09-15" / names[slow.instance_id]
    assert first.save_root == paths.RUN_ROOT / "2026-09-14" / names[single.instance_id]
    assert first.output_path == first.save_root / first.run_id
    assert len({operation.output_path for operation in (first, later, other, third)}) == 4
    assert not paths.RUN_ROOT.exists()


def test_standalone_factory_keeps_legacy_output_hierarchy(tmp_path):
    factory = ContextFactory(ownership=object(), preference_backend={}, save_root_provider=lambda: tmp_path)
    context = factory.for_experiment("phase_scan").for_mode("dual")
    operation = context.begin_operation({})
    assert operation.output_path == tmp_path / "measurements" / "phase_scan" / "dual" / operation.run_id
    assert factory.for_experiment("phase_scan").save_root() == tmp_path
    assert not operation.output_path.exists()


def test_instance_provider_requires_a_detector_scoped_context(tmp_path):
    calls = []
    factory = ContextFactory(ownership=object(), preference_backend={},
        instance_save_root_provider=lambda instance: calls.append(instance) or tmp_path)
    with pytest.raises(ContractError, match="for_mode"):
        factory.for_experiment("phase_scan").save_root()
    assert calls == []


@pytest.mark.parametrize("dual", [False, True])
def test_phase_file_dialogs_use_their_own_provider_without_touching_settings(private_paths, monkeypatch, dual):
    pytest.importorskip("PySide6")
    from control_app.ui.widgets import phase_scan_widget as phase_ui

    selected_elsewhere = paths.default_tab_save_location("Slow Scan - Single Detector")
    paths.set_save_location(selected_elsewhere, create=False)
    destination = paths.default_tab_save_location("Phase Scan - Dual Detector" if dual else "Phase Scan - Single Detector")
    widget = SimpleNamespace(save_root_provider=lambda: str(destination), dual_detector=dual, plan=object())
    dialogs = []

    def capture(kind, result):
        def show(parent, title, directory, *args):
            dialogs.append((kind, Path(directory)))
            return result
        return show

    monkeypatch.setattr(phase_ui.QFileDialog, "getExistingDirectory", capture("blank", ""))
    monkeypatch.setattr(phase_ui.QFileDialog, "getOpenFileName", capture("load", ("", "")))
    monkeypatch.setattr(phase_ui.QFileDialog, "getSaveFileName", capture("save", ("", "")))
    phase_ui.PhaseScanWidget._load_background(widget)
    phase_ui.PhaseScanWidget._load_plan(widget)
    assert not paths.RUN_ROOT.exists()
    phase_ui.PhaseScanWidget._save_plan(widget)
    filename = "dual_detector_phase_scan_plan.json" if dual else "phase_scan_plan.json"
    assert dialogs == [("blank", destination), ("load", destination), ("save", destination / filename)]
    assert paths.get_save_location() == selected_elsewhere
    assert destination.is_dir() and list(destination.iterdir()) == []
    assert not selected_elsewhere.exists()


@pytest.mark.parametrize("dual", [False, True])
def test_phase_save_prepares_selected_parent_and_preserves_plan_payload(private_paths, monkeypatch, dual):
    import json
    pytest.importorskip("PySide6")
    from control_app.ui.widgets import phase_scan_widget as phase_ui

    root = paths.default_tab_save_location("DD Phase Scan" if dual else "Phase Scan")
    selected = root / "plans" / "new" / "saved.json"
    status = []
    payload = {"mode": "dual" if dual else "single", "inputs": {"pre_pump_ms": 7}}
    widget = SimpleNamespace(save_root_provider=lambda: root, dual_detector=dual,
        plan=SimpleNamespace(to_dict=lambda: dict(payload)), save_status=SimpleNamespace(setText=status.append))
    def choose(*args):
        assert root.is_dir() and not selected.parent.exists()
        return str(selected), ""
    monkeypatch.setattr(phase_ui.QFileDialog, "getSaveFileName", choose)
    assert not root.exists()
    phase_ui.PhaseScanWidget._save_plan(widget)
    saved = json.loads(selected.read_text())
    assert saved["mode"] == payload["mode"] and saved["inputs"] == payload["inputs"]
    assert saved["saved_at_utc"] and status


def test_phase_save_folder_failure_is_shown_without_opening_dialog(private_paths, monkeypatch):
    pytest.importorskip("PySide6")
    from control_app.ui.widgets import phase_scan_widget as phase_ui

    root = paths.default_tab_save_location("Phase Scan")
    widget = SimpleNamespace(save_root_provider=lambda: root, dual_detector=False, plan=object())
    warnings = []
    def denied(*args, **kwargs):
        raise PermissionError("Injected Phase Save Plan permission failure")
    monkeypatch.setattr(Path, "mkdir", denied)
    monkeypatch.setattr(phase_ui.QMessageBox, "warning", lambda parent, title, message: warnings.append(message))
    monkeypatch.setattr(phase_ui.QFileDialog, "getSaveFileName", lambda *args: pytest.fail("Failed root must not open dialog"))
    phase_ui.PhaseScanWidget._save_plan(widget)
    assert len(warnings) == 1 and "permission failure" in warnings[0]
    assert not root.exists()
