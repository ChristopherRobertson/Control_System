"""Acquire one manually confirmed MS-01 orientation using direct repo services."""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import yaml


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.picoscope_service import PicoScopeService  # noqa: E402
from control_app.workflows.picoscope_settings_test import (  # noqa: E402
    capture_settings_from_recipe,
    load_recipe,
    validate_capture_settings,
)
from control_app.workflows.timing_calibration_procedure import (  # noqa: E402
    MEASUREMENT_STEPS,
    TimingCalibrationProcedure,
    _settings_with_channel_a_trigger,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402
from control_app.workflows.timing_trace_analysis import analyze_pico_trace  # noqa: E402


EVIDENCE_DIR = Path(__file__).resolve().parent
SAFE_IDLE_RECIPE = REPO_ROOT / "instrument" / "recipes" / "safe_idle.yaml"
PICO_RECIPE = REPO_ROOT / "instrument" / "recipes" / "picoscope_settings_test.yaml"
ACCEPTED_REQUIRED = 100
MAX_ATTEMPTS = 300


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def append_row(path: Path, fieldnames: list[str], row: dict) -> None:
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("orientation", choices=("normal", "swapped"))
    parser.add_argument(
        "--output-root",
        type=Path,
        default=EVIDENCE_DIR,
        help="Stable phase evidence directory; defaults to the MS-01 directory.",
    )
    parser.add_argument(
        "--run-label",
        default="",
        help="Optional prefix for the orientation directory, such as reconnection.",
    )
    args = parser.parse_args()
    orientation = args.orientation
    step_id = "0a" if orientation == "normal" else "0b"
    step = next(item for item in MEASUREMENT_STEPS if item.step == step_id)

    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    directory_name = (
        f"{args.run_label}_{orientation}" if args.run_label else orientation
    )
    orientation_dir = output_root / directory_name
    raw_dir = orientation_dir / "raw"
    if orientation_dir.exists():
        raise RuntimeError(
            f"{orientation_dir} already exists; refusing to overwrite evidence"
        )
    raw_dir.mkdir(parents=True)

    status = {
        "orientation": orientation,
        "step": step_id,
        "measurement_id": step.measurement_id,
        "started_utc": datetime.now(UTC).isoformat(),
        "accepted_required": ACCEPTED_REQUIRED,
        "accepted": 0,
        "rejected": 0,
        "status": "STARTING",
        "sign_convention": "B minus A; positive means CHB arrived later than CHA",
    }
    write_json(orientation_dir / "status.json", status)

    inventory = load_config_inventory(write_files=False)
    command_log = (orientation_dir / "command_log.txt").open(
        "a", encoding="utf-8"
    )
    manager = TimingRecipeManager(inventory=inventory, command_log=command_log)
    pico_recipe, _ = load_recipe(PICO_RECIPE)
    settings = _settings_with_channel_a_trigger(
        capture_settings_from_recipe(pico_recipe), edge="rising"
    )
    pico_config = inventory.devices["picoscope"]
    validate_capture_settings(settings, pico_config)
    pico = PicoScopeService(pico_config, settings)

    try:
        initial_safe = manager.apply_recipe(
            SAFE_IDLE_RECIPE,
            output_path=orientation_dir / "safe_idle_before.json",
        )
        if not initial_safe["matches_recipe"]:
            raise RuntimeError("safe-idle readback did not match before acquisition")

        pico.open_unit()
        pico.apply_capture_settings()
        timing_validation = pico.validate_sample_timing()
        write_json(
            orientation_dir / "picoscope_configuration.json",
            {
                "configured_model": pico_config.get("model"),
                "configured_serial_number": pico_config.get("serial_number"),
                "sdk_serial_number": pico_config.get("sdk_serial_number"),
                "capture_settings": settings,
                "sample_timing_validation": timing_validation,
            },
        )

        recipe = TimingCalibrationProcedure(
            operator="Christopher Robertson", inventory=inventory
        ).build_step_recipe(step, programmed_delay_ns=0)
        with SAFE_IDLE_RECIPE.open("r", encoding="utf-8") as handle:
            safe_idle_recipe_data = yaml.safe_load(handle)
        recipe["t660"]["t660_1"] = safe_idle_recipe_data["t660"]["t660_1"]
        active = manager.apply_recipe(
            recipe,
            output_path=orientation_dir / "active_recipe_readback.json",
        )
        if not active["matches_recipe"]:
            raise RuntimeError("active MS-01 recipe readback did not match")

        interval_ns = float(timing_validation["sample_interval_ns"])
        threshold_adc = int(settings["pulse_count_threshold_adc"])
        attempts_path = orientation_dir / "capture_attempts.csv"
        fields = [
            "attempt",
            "accepted_index",
            "status",
            "reason",
            "raw_path",
            "measured_separation_ns",
            "sample_interval_ns",
            "threshold_adc",
            "captured_utc",
        ]
        attempt = 0
        while status["accepted"] < ACCEPTED_REQUIRED and attempt < MAX_ATTEMPTS:
            attempt += 1
            raw_path = raw_dir / f"attempt_{attempt:03d}.csv"
            row = {
                "attempt": attempt,
                "accepted_index": "",
                "status": "REJECTED",
                "reason": "",
                "raw_path": str(raw_path),
                "measured_separation_ns": "",
                "sample_interval_ns": interval_ns,
                "threshold_adc": threshold_adc,
                "captured_utc": datetime.now(UTC).isoformat(),
            }
            try:
                pico.capture_block(raw_path)
                measurement = analyze_pico_trace(
                    raw_path,
                    sample_interval_ns=interval_ns,
                    threshold_adc=threshold_adc,
                    programmed_separation_ns=0.0,
                    reference_edge="rising",
                    target_edge="rising",
                )
                status["accepted"] += 1
                row.update(
                    {
                        "accepted_index": status["accepted"],
                        "status": "ACCEPTED",
                        "measured_separation_ns": measurement[
                            "measured_separation_ns"
                        ],
                    }
                )
            except BaseException as exc:
                status["rejected"] += 1
                row["reason"] = str(exc)
            append_row(attempts_path, fields, row)
            write_json(orientation_dir / "status.json", status)

        if status["accepted"] != ACCEPTED_REQUIRED:
            raise RuntimeError(
                f"only {status['accepted']} accepted captures after {attempt} attempts"
            )
        status["status"] = "PASS"
    except BaseException as exc:
        status["status"] = "FAIL"
        status["error"] = str(exc)
        raise
    finally:
        final_errors = []
        try:
            final_safe = manager.apply_recipe(
                SAFE_IDLE_RECIPE,
                output_path=orientation_dir / "safe_idle_after.json",
            )
            status["final_safe_idle_matches"] = final_safe["matches_recipe"]
        except BaseException as exc:
            final_errors.append(f"safe idle: {exc}")
            status["final_safe_idle_matches"] = False
        try:
            pico.stop()
        except BaseException as exc:
            final_errors.append(f"PicoScope stop: {exc}")
        try:
            pico.close_unit()
        except BaseException as exc:
            final_errors.append(f"PicoScope close: {exc}")
        command_log.close()
        status["finished_utc"] = datetime.now(UTC).isoformat()
        status["finalization_errors"] = final_errors
        write_json(orientation_dir / "status.json", status)

    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
