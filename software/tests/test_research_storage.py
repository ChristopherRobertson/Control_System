"""Scientific storage boundaries, independent of instrument access."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from control_app import paths
from control_app.workflows.phase_scan_data import write_json


def test_relative_output_creates_research_file_and_returns_resolvable_path(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RESEARCH_ROOT", tmp_path)
    write_json("nested/record.json", {"signal_v": 1.25})
    assert json.loads((tmp_path / "nested/record.json").read_text()) == {"signal_v": 1.25}
    assert not (paths.REPO_ROOT / "nested/record.json").exists()


@pytest.mark.parametrize("destination", ["../escape.json", paths.REPO_ROOT / "output.json"])
def test_native_writer_rejects_escape_before_creating_file(tmp_path, monkeypatch, destination):
    monkeypatch.setattr(paths, "RESEARCH_ROOT", tmp_path)
    with pytest.raises(ValueError, match="Research output"):
        write_json(destination, {"measurement": 1})


def test_write_failure_is_not_redirected(tmp_path, monkeypatch):
    target = tmp_path / "record.json"
    original = Path.open

    def deny(path, *args, **kwargs):
        if path == target:
            raise PermissionError(f"Cannot write {path}")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny)
    with pytest.raises(PermissionError, match="Cannot write"):
        write_json(target, {"measurement": 1})
    assert not target.exists()


def test_environment_research_root_and_invalid_run_override(tmp_path):
    env = dict(os.environ, CONTROL_SYSTEM_RESEARCH_ROOT=str(tmp_path))
    env["PYTHONPATH"] = str(paths.SOFTWARE_ROOT)
    result = subprocess.run([sys.executable, "-c",
        "from control_app.paths import RUN_ROOT; print(RUN_ROOT)"],
        env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == tmp_path / "experiments/runs"
    env["CONTROL_SYSTEM_RUN_ROOT"] = str(paths.REPO_ROOT / "runs")
    result = subprocess.run([sys.executable, "-c", "import control_app.paths"],
        env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "Research output must be under" in result.stderr


def test_plotter_defaults_do_not_write_beside_external_input(tmp_path):
    from control_app.workflows.labone_plotter_processor import default_output_paths
    outputs = default_output_paths(paths.REPO_ROOT / "input.tsv")
    assert all(p.is_relative_to(paths.RESEARCH_ROOT) for p in outputs)
    assert all(p.parent != paths.REPO_ROOT for p in outputs)


def test_saved_instrument_destination_keeps_relative_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RESEARCH_ROOT", tmp_path)
    saved = paths.REPO_ROOT / "evidence/experiments/runs/2026-09-16/Slow Scan"
    assert paths.resolve_save_preference(saved) == tmp_path / "experiments/runs/2026-09-16/Slow Scan"
    assert not (tmp_path / "experiments").exists()


def test_symlink_escape_is_rejected(tmp_path, monkeypatch):
    root = tmp_path / "research"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "redirect"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires Windows developer mode or privilege")
    monkeypatch.setattr(paths, "RESEARCH_ROOT", root)
    with pytest.raises(ValueError, match="Research output"):
        write_json(link / "record.json", {"measurement": 1})
    assert not (outside / "record.json").exists()
