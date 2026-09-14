"""Scoped reconstruction dialogs and unchanged native exports, without hardware."""
from pathlib import Path

import pytest


@pytest.fixture
def qt_app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


@pytest.fixture(params=("single_ch1_buffer_blank", "dual_detector"), ids=("single", "dual"))
def surface_case(request):
    from test_regular_phase_scan_ui import reconstruction
    from test_dual_detector_phase_scan_data import synthetic_result
    return request.param, synthetic_result() if request.param == "dual_detector" else reconstruction()


def nested_surface(mode, provider, **kwargs):
    from PySide6.QtWidgets import QVBoxLayout, QWidget
    from control_app.ui.widgets.phase_scan_surface import PhaseScanReconstructionWidget
    owner = QWidget()
    owner.save_root_provider = provider
    middle = QWidget()
    # Ignore non-callable attributes while traversing real Qt layout parents.
    middle.save_root_provider = "not a provider"
    QVBoxLayout(owner).addWidget(middle)
    surface = PhaseScanReconstructionWidget(detector_mode=mode, **kwargs)
    QVBoxLayout(middle).addWidget(surface)
    return owner, surface


def capture_warnings(monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, message: warnings.append((title, message)))
    return warnings


def test_nested_provider_load_is_read_only_and_csv_keeps_native_payload(qt_app, surface_case, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from control_app.ui.widgets.phase_scan_surface import export_quantitative_csv
    mode, result = surface_case
    roots = [tmp_path / "2026-09-14" / "Original tab"]
    owner, surface = nested_surface(mode, lambda: roots[0])
    warnings = capture_warnings(monkeypatch)
    try:
        surface.set_result(result, run_path=tmp_path / "loaded-old-run")
        assert not roots[0].exists()
        load_roots = []
        monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                            lambda parent, title, directory: load_roots.append(Path(directory)) or "")
        surface.load_button.click()
        assert load_roots == [roots[0]]
        assert not roots[0].exists()

        roots[0] = tmp_path / "2026-09-15" / "Current tab"
        target = roots[0] / "chosen" / "quantitative.csv"
        baseline = tmp_path / "baseline.csv"
        export_quantitative_csv(baseline, result)
        dialogs = []
        def select_csv(parent, title, filename, filters):
            dialogs.append(Path(filename))
            assert roots[0].is_dir()
            return str(target), "CSV (*.csv)"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", select_csv)
        surface.export_button.click()
        assert dialogs == [roots[0] / "phase_scan.csv"]
        assert target.read_bytes() == baseline.read_bytes()
        assert not warnings
        original = target.read_bytes()
        surface.export_button.click()
        assert warnings and target.read_bytes() == original
    finally:
        owner.deleteLater()


def test_explicit_provider_toolbar_image_creates_parent_and_preserves_file(qt_app, surface_case, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    mode, result = surface_case
    inherited = tmp_path / "ancestor"
    root = tmp_path / "explicit"
    owner, surface = nested_surface(mode, lambda: inherited, save_root_provider=lambda: root)
    warnings = capture_warnings(monkeypatch)
    try:
        surface.set_result(result)
        assert not root.exists() and not inherited.exists()
        target = tmp_path / "chosen-image-parent" / "nested" / "surface.png"
        dialogs = []
        def select_image(parent, title, filename, filters):
            dialogs.append(Path(filename))
            assert root.is_dir()
            return str(target), "PNG (*.png)"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", select_image)
        surface.toolbar._actions["save_figure"].trigger()
        assert dialogs == [root / "phase_scan.png"]
        original = target.read_bytes()
        assert original.startswith(b"\x89PNG\r\n\x1a\n") and len(original) > 1000
        assert not warnings and not inherited.exists()
        surface.toolbar._actions["save_figure"].trigger()
        assert warnings and target.read_bytes() == original
    finally:
        owner.deleteLater()


def test_standalone_global_fallback_load_does_not_create_directory(qt_app, surface_case, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from control_app import paths
    from control_app.ui.widgets.phase_scan_surface import PhaseScanReconstructionWidget
    mode, result = surface_case
    root = tmp_path / "global-fallback"
    monkeypatch.setattr(paths, "get_save_location", lambda: root)
    surface = PhaseScanReconstructionWidget(detector_mode=mode)
    try:
        surface.set_result(result)
        seen = []
        monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                            lambda parent, title, directory: seen.append(Path(directory)) or "")
        surface.load_button.click()
        assert seen == [root] and not root.exists()
    finally:
        surface.deleteLater()


@pytest.mark.parametrize("action", ("csv", "image"))
@pytest.mark.parametrize("failure_at", ("root", "chosen_parent"))
def test_save_directory_failure_is_visible(qt_app, surface_case, tmp_path, monkeypatch, action, failure_at):
    from PySide6.QtWidgets import QFileDialog
    from control_app.ui.widgets.phase_scan_surface import PhaseScanReconstructionWidget
    mode, result = surface_case
    blocker = tmp_path / "existing-file"
    blocker.write_bytes(b"preserve this file")
    root = blocker / "folder" if failure_at == "root" else tmp_path / "dialog-root"
    target = blocker / "folder" / ("data.csv" if action == "csv" else "plot.png")
    surface = PhaseScanReconstructionWidget(detector_mode=mode, save_root_provider=lambda: root)
    warnings = capture_warnings(monkeypatch)
    dialogs = []
    try:
        surface.set_result(result)
        monkeypatch.setattr(QFileDialog, "getSaveFileName",
                            lambda *args: dialogs.append(args) or (str(target), ""))
        if action == "csv":
            surface.export_button.click()
        else:
            surface.toolbar._actions["save_figure"].trigger()
        assert len(dialogs) == (0 if failure_at == "root" else 1)
        assert len(warnings) == 1 and blocker.name in warnings[0][1]
        assert blocker.read_bytes() == b"preserve this file"
        assert not target.exists()
    finally:
        surface.deleteLater()
