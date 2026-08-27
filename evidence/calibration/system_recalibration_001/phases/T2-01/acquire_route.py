"""Acquire one T2-01 six-point installed-route sweep with focused services."""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[5]
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
    _plan_capture_settings,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402
from control_app.workflows.timing_trace_analysis import analyze_pico_trace  # noqa: E402


PHASE_DIR = Path(__file__).resolve().parent
SAFE_IDLE_RECIPE = REPO_ROOT / "instrument" / "recipes" / "safe_idle.yaml"
PICO_RECIPE = REPO_ROOT / "instrument" / "recipes" / "picoscope_settings_test.yaml"
DELAYS_NS = (0, 100, 1_000, 10_000, 100_000, 1_000_000)
ACCEPTED_REQUIRED = 100
MAX_ATTEMPTS_PER_DELAY = 300
SETUPS = {
    "1": ("1", "setup_1_extref_to_daq"),
    "2": ("2", "setup_2_extref_to_mircat"),
    "3": ("3", "setup_3_extref_to_t6601"),
}
TARGET_PULSE_WIDTH_NS = {"1": 150.0, "2": 150.0, "3": 10_000.0}


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_csv(path: Path, fieldnames: list[str], row: dict) -> None:
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if new:
            writer.writeheader()
        writer.writerow(row)


def slug(delay_ns: int) -> str:
    return f"{delay_ns}ns"


def require_complete_positive_pulse(
    raw_path: Path,
    *,
    threshold_adc: int,
    minimum_post_edge_samples: int = 100,
) -> None:
    values = []
    with raw_path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            values.append(int(row["ch_b_adc"]))
    rising = None
    falling = None
    for index in range(1, len(values)):
        if rising is None and values[index - 1] < threshold_adc <= values[index]:
            rising = index
        elif rising is not None and values[index - 1] > threshold_adc >= values[index]:
            falling = index
            break
    if rising is None or falling is None:
        raise RuntimeError("target pulse does not contain both rising and falling threshold crossings")
    if len(values) - falling - 1 < minimum_post_edge_samples:
        raise RuntimeError("target falling edge lacks the required post-edge samples")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("setup", choices=SETUPS)
    parser.add_argument("--output-name", default="")
    args = parser.parse_args()
    step_number, directory_name = SETUPS[args.setup]
    step = next(item for item in MEASUREMENT_STEPS if item.step == step_number)
    output_dir = PHASE_DIR / (args.output_name or directory_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_root = output_dir / "raw"
    if raw_root.exists():
        raise RuntimeError(f"{raw_root} already exists; refusing to overwrite evidence")
    raw_root.mkdir()

    status = {
        "operator": "Christopher Robertson",
        "phase": "T2-01",
        "setup": args.setup,
        "measurement_id": step.measurement_id,
        "started_utc": datetime.now(UTC).isoformat(),
        "programmed_delays_ns": list(DELAYS_NS),
        "accepted_required_per_delay": ACCEPTED_REQUIRED,
        "per_delay": {},
        "status": "STARTING",
        "sign_convention": "PicoScope CHB minus CHA; positive means target arrived later",
    }
    write_json(output_dir / "status.json", status)

    inventory = load_config_inventory(write_files=False)
    log = (output_dir / "command_log.txt").open("a", encoding="utf-8")
    manager = TimingRecipeManager(inventory=inventory, command_log=log)
    base_recipe, _ = load_recipe(PICO_RECIPE)
    base_settings = capture_settings_from_recipe(base_recipe)
    pico_config = inventory.devices["picoscope"]
    pico = PicoScopeService(pico_config, base_settings)
    fields = [
        "attempt", "accepted_index", "status", "reason", "raw_path",
        "programmed_delay_ns", "measured_separation_ns", "residual_ns",
        "reference_edge_time_ns", "target_edge_time_ns", "sample_interval_ns",
        "timebase", "total_samples", "pre_trigger_samples", "threshold_adc",
        "captured_utc",
    ]

    try:
        safe = manager.apply_recipe(
            SAFE_IDLE_RECIPE, output_path=output_dir / "safe_idle_before_acquisition.json"
        )
        if not safe["matches_recipe"]:
            raise RuntimeError("safe-idle readback mismatch before acquisition")

        pico.open_unit()
        pico.capture_settings = base_settings
        base_timing = pico.validate_sample_timing()
        procedure = TimingCalibrationProcedure(
            operator="Christopher Robertson", inventory=inventory
        )

        for delay_ns in DELAYS_NS:
            delay_dir = raw_root / slug(delay_ns)
            delay_dir.mkdir()
            settings, timing = _plan_capture_settings(
                pico,
                base_settings,
                programmed_delay_ns=delay_ns,
                base_sample_interval_ns=float(base_timing["sample_interval_ns"]),
                trigger_edge="rising",
                target_pulse_width_ns=TARGET_PULSE_WIDTH_NS[args.setup],
            )
            validate_capture_settings(settings, pico_config)
            pico.capture_settings = settings
            pico.apply_capture_settings()
            timing = pico.validate_sample_timing()
            write_json(
                output_dir / f"picoscope_{slug(delay_ns)}.json",
                {
                    "capture_settings": settings,
                    "sample_timing_validation": timing,
                    "configured_model": pico_config.get("model"),
                    "configured_serial_number": pico_config.get("serial_number"),
                    "sdk_serial_number": pico_config.get("sdk_serial_number"),
                },
            )

            recipe = procedure.build_step_recipe(step, programmed_delay_ns=delay_ns)
            active = manager.apply_recipe(
                recipe, output_path=output_dir / f"active_recipe_{slug(delay_ns)}.json"
            )
            if not active["matches_recipe"]:
                raise RuntimeError(f"active recipe mismatch at {delay_ns} ns")

            accepted = 0
            rejected = 0
            attempts_path = output_dir / f"capture_attempts_{slug(delay_ns)}.csv"
            for attempt in range(1, MAX_ATTEMPTS_PER_DELAY + 1):
                if accepted >= ACCEPTED_REQUIRED:
                    break
                raw_path = delay_dir / f"attempt_{attempt:03d}.csv"
                row = {
                    "attempt": attempt,
                    "accepted_index": "",
                    "status": "REJECTED",
                    "reason": "",
                    "raw_path": str(raw_path),
                    "programmed_delay_ns": delay_ns,
                    "measured_separation_ns": "",
                    "residual_ns": "",
                    "reference_edge_time_ns": "",
                    "target_edge_time_ns": "",
                    "sample_interval_ns": timing["sample_interval_ns"],
                    "timebase": settings["timebase"],
                    "total_samples": settings["total_samples"],
                    "pre_trigger_samples": settings["pre_trigger_samples"],
                    "threshold_adc": settings["pulse_count_threshold_adc"],
                    "captured_utc": datetime.now(UTC).isoformat(),
                }
                try:
                    capture_summary = pico.capture_block(raw_path)
                    if int(capture_summary.get("overflow", 0)) != 0:
                        raise RuntimeError(
                            f"PicoScope overflow mask {capture_summary['overflow']}"
                        )
                    require_complete_positive_pulse(
                        raw_path,
                        threshold_adc=int(settings["pulse_count_threshold_adc"]),
                    )
                    measured = analyze_pico_trace(
                        raw_path,
                        sample_interval_ns=float(timing["sample_interval_ns"]),
                        threshold_adc=int(settings["pulse_count_threshold_adc"]),
                        programmed_separation_ns=float(delay_ns),
                        reference_edge="rising",
                        target_edge="rising",
                    )
                    accepted += 1
                    row.update(
                        {
                            "accepted_index": accepted,
                            "status": "ACCEPTED",
                            "measured_separation_ns": measured["measured_separation_ns"],
                            "residual_ns": measured["residual_ns"],
                            "reference_edge_time_ns": measured["reference_edge_time_ns"],
                            "target_edge_time_ns": measured["target_edge_time_ns"],
                        }
                    )
                except BaseException as exc:
                    rejected += 1
                    row["reason"] = str(exc)
                append_csv(attempts_path, fields, row)
                status["per_delay"][str(delay_ns)] = {
                    "accepted": accepted, "rejected": rejected
                }
                write_json(output_dir / "status.json", status)
            if accepted != ACCEPTED_REQUIRED:
                raise RuntimeError(
                    f"{delay_ns} ns: only {accepted} accepted captures after "
                    f"{accepted + rejected} attempts"
                )

        status["status"] = "PASS"
    except BaseException as exc:
        status["status"] = "FAIL"
        status["error"] = str(exc)
        raise
    finally:
        errors = []
        try:
            safe = manager.apply_recipe(
                SAFE_IDLE_RECIPE, output_path=output_dir / "safe_idle_after_acquisition.json"
            )
            status["final_safe_idle_matches"] = safe["matches_recipe"]
        except BaseException as exc:
            errors.append(f"safe idle: {exc}")
            status["final_safe_idle_matches"] = False
        try:
            pico.stop()
        except BaseException as exc:
            errors.append(f"PicoScope stop: {exc}")
        try:
            pico.close_unit()
        except BaseException as exc:
            errors.append(f"PicoScope close: {exc}")
        log.close()
        status["finished_utc"] = datetime.now(UTC).isoformat()
        status["finalization_errors"] = errors
        write_json(output_dir / "status.json", status)

    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
