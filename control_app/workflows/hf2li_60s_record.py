"""Workflow for recording real HF2LI detector data."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TextIO
import json

from control_app.config_loader import ConfigInventory, load_config_inventory
from control_app.devices.hf2li_service import HF2LIService
from control_app.manifest import new_manifest, write_manifest


class HF2LIRecordWorkflow:
    """Run one real HF2LI acquisition and write Day 6 artifacts."""

    def __init__(
        self,
        *,
        operator: str,
        inventory: ConfigInventory | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        self.operator = operator
        self.inventory = inventory or load_config_inventory(config_path, write_files=False)
        self.config_path = Path(self.inventory.config_path)

    def run(
        self,
        *,
        run_dir: str | Path,
        preset_name: str,
        duration_s: float,
        command_log: TextIO | None = None,
        command_log_paths: list[str] | None = None,
        presets_path: str | Path = "recipes/hf2li_presets.yaml",
    ) -> dict[str, Any]:
        """Apply preset, reload settings, acquire real data, and write a manifest."""

        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        service = HF2LIService.from_config(config_path=self.config_path, command_log=command_log)
        raw_csv = run_path / "hf2li_raw_samples.csv"
        summary_csv = run_path / "hf2li_summary.csv"
        snapshot_path = run_path / "settings_snapshot.json"
        reload_snapshot_path = run_path / "settings_reload_snapshot.json"
        reload_result_path = run_path / "settings_reload_result.json"
        comparison_path = run_path / "settings_reload_comparison.json"
        try:
            service.connect()
            preset = service.load_preset(preset_name, presets_path=presets_path)
            applied = service.apply_preset(preset)
            snapshot = service.export_settings_snapshot(snapshot_path, preset=preset)
            reload_result = service.reload_settings_snapshot(snapshot)
            reload_result_path.write_text(
                json.dumps(reload_result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            reload_snapshot = service.export_settings_snapshot(reload_snapshot_path, preset=preset)
            comparison = service.compare_settings_snapshots(snapshot, reload_snapshot)
            comparison_path.write_text(
                json.dumps(comparison, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            acquisition = preset.settings.get("acquisition") or {}
            demodulators = acquisition.get("demodulators") or [0, 3]
            fields = acquisition.get("fields") or ["x", "y", "r"]
            record = service.acquire_record(
                duration_s=duration_s,
                demodulators=demodulators,
                fields=fields,
            )
            save_summary = service.save_record(
                record,
                raw_csv_path=raw_csv,
                summary_csv_path=summary_csv,
            )
        finally:
            service.close()

        manifest = new_manifest(
            operator=self.operator,
            inventory=self.inventory,
            hf2li_settings_snapshot={
                "preset": preset_name,
                "settings_snapshot_path": str(snapshot_path),
                "settings_reload_snapshot_path": str(reload_snapshot_path),
                "settings_reload_comparison_path": str(comparison_path),
                "settings_reload_match": bool(comparison.get("match")),
                "applied": applied,
                "save_summary": save_summary,
            },
            raw_data_paths=[str(raw_csv)],
            command_log_paths=command_log_paths or [],
            device_readback_paths=[
                str(summary_csv),
                str(snapshot_path),
                str(reload_snapshot_path),
                str(reload_result_path),
                str(comparison_path),
            ],
            blocker_status={"blocked": False, "blockers": [], "next_actions": []},
        )
        write_manifest(run_path / "run_manifest.json", manifest)
        return {
            "run_dir": str(run_path),
            "raw_csv": str(raw_csv),
            "summary_csv": str(summary_csv),
            "settings_snapshot": str(snapshot_path),
            "settings_reload_comparison": str(comparison_path),
            "manifest": str(run_path / "run_manifest.json"),
            "settings_reload_match": bool(comparison.get("match")),
            "sample_count": save_summary.get("sample_count"),
        }
