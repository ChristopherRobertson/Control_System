"""Acquire one focused T1-01 six-point electrical sweep."""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
    _electrical_target_pulse_width_ns,
    _plan_capture_settings,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402
from control_app.workflows.timing_trace_analysis import analyze_pico_trace  # noqa: E402


HERE = Path(__file__).resolve().parent
SAFE_IDLE = REPO_ROOT / "recipes" / "safe_idle.yaml"
PICO_RECIPE = REPO_ROOT / "recipes" / "picoscope_settings_test.yaml"
DELAYS_NS = (0, 100, 1_000, 10_000, 100_000, 1_000_000)
ACCEPTED_REQUIRED = 100
MAX_ATTEMPTS = 300
STEPS = {
    "4": "setup_1_extref_to_fire",
    "5": "setup_2_fire_to_qswitch",
    "6": "setup_3_extref_to_qswitch",
}
POLARITIES = {
    "4": ("positive", "negative"),
    "5": ("negative", "negative"),
    "6": ("positive", "negative"),
}


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_csv(path: Path, fields: list[str], row: dict) -> None:
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if new:
            writer.writeheader()
        writer.writerow(row)


def require_complete_pulse(
    values: list[int],
    *,
    threshold_adc: int,
    polarity: str,
    minimum_post_edge_samples: int = 100,
) -> None:
    active = None
    returned = None
    for index in range(1, len(values)):
        previous, current = values[index - 1], values[index]
        active_crossing = (
            previous < threshold_adc <= current
            if polarity == "positive"
            else previous > threshold_adc >= current
        )
        return_crossing = (
            previous > threshold_adc >= current
            if polarity == "positive"
            else previous < threshold_adc <= current
        )
        if active is None and active_crossing:
            active = index
        elif active is not None and return_crossing:
            returned = index
            break
    if active is None or returned is None:
        raise RuntimeError(f"{polarity} pulse lacks active or return threshold crossing")
    if len(values) - returned - 1 < minimum_post_edge_samples:
        raise RuntimeError("pulse return edge lacks required post-edge samples")


def validate_raw_pulses(
    path: Path,
    *,
    threshold_adc: int,
    polarities: tuple[str, str],
) -> None:
    a, b = [], []
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            a.append(int(row["ch_a_adc"]))
            b.append(int(row["ch_b_adc"]))
    require_complete_pulse(a, threshold_adc=threshold_adc, polarity=polarities[0])
    require_complete_pulse(b, threshold_adc=threshold_adc, polarity=polarities[1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=STEPS)
    parser.add_argument("--output-name", default="")
    args = parser.parse_args()
    step = next(item for item in MEASUREMENT_STEPS if item.step == args.step)
    output = HERE / (args.output_name or STEPS[args.step])
    output.mkdir(parents=True, exist_ok=True)
    raw_root = output / "raw"
    if raw_root.exists():
        raise RuntimeError(f"{raw_root} already exists; refusing to overwrite evidence")
    raw_root.mkdir()

    status = {
        "operator": "Christopher Robertson",
        "phase": "T1-01",
        "step": args.step,
        "measurement_id": step.measurement_id,
        "started_utc": datetime.now(UTC).isoformat(),
        "accepted_required_per_delay": ACCEPTED_REQUIRED,
        "programmed_delays_ns": list(DELAYS_NS),
        "per_delay": {},
        "status": "STARTING",
        "sign_convention": "PicoScope CHB minus CHA; positive means target arrived later",
        "reference_edge": step.reference_edge,
        "target_edge": step.target_edge,
    }
    write_json(output / "status.json", status)
    inventory = load_config_inventory(write_files=False)
    log = (output / "command_log.txt").open("a", encoding="utf-8")
    manager = TimingRecipeManager(inventory=inventory, command_log=log)
    pico_recipe, _ = load_recipe(PICO_RECIPE)
    base = capture_settings_from_recipe(pico_recipe)
    pico_config = inventory.devices["picoscope"]
    pico = PicoScopeService(pico_config, base)
    procedure = TimingCalibrationProcedure(operator="Christopher Robertson", inventory=inventory)
    fields = [
        "attempt", "accepted_index", "status", "reason", "raw_path",
        "programmed_delay_ns", "measured_separation_ns", "residual_ns",
        "reference_edge_time_ns", "target_edge_time_ns", "sample_interval_ns",
        "timebase", "total_samples", "pre_trigger_samples", "threshold_adc",
        "captured_utc",
    ]

    try:
        safe = manager.apply_recipe(
            SAFE_IDLE, output_path=output / "safe_idle_before_acquisition.json"
        )
        if not safe["matches_recipe"]:
            raise RuntimeError("safe-idle mismatch before acquisition")
        pico.open_unit()
        pico.capture_settings = base
        base_timing = pico.validate_sample_timing()
        for delay_ns in DELAYS_NS:
            delay_dir = raw_root / f"{delay_ns}ns"
            delay_dir.mkdir()
            settings, timing = _plan_capture_settings(
                pico,
                base,
                programmed_delay_ns=delay_ns,
                base_sample_interval_ns=float(base_timing["sample_interval_ns"]),
                trigger_edge=step.reference_edge,
                target_pulse_width_ns=_electrical_target_pulse_width_ns(step),
            )
            validate_capture_settings(settings, pico_config)
            pico.capture_settings = settings
            pico.apply_capture_settings()
            timing = pico.validate_sample_timing()
            write_json(
                output / f"picoscope_{delay_ns}ns.json",
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
                recipe, output_path=output / f"active_recipe_{delay_ns}ns.json"
            )
            if not active["matches_recipe"]:
                raise RuntimeError(f"active recipe mismatch at {delay_ns} ns")

            accepted = rejected = 0
            attempts_path = output / f"capture_attempts_{delay_ns}ns.csv"
            for attempt in range(1, MAX_ATTEMPTS + 1):
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
                    capture = pico.capture_block(raw_path)
                    if int(capture.get("overflow", 0)) != 0:
                        raise RuntimeError(f"PicoScope overflow mask {capture['overflow']}")
                    validate_raw_pulses(
                        raw_path,
                        threshold_adc=int(settings["pulse_count_threshold_adc"]),
                        polarities=POLARITIES[args.step],
                    )
                    measured = analyze_pico_trace(
                        raw_path,
                        sample_interval_ns=float(timing["sample_interval_ns"]),
                        threshold_adc=int(settings["pulse_count_threshold_adc"]),
                        programmed_separation_ns=float(delay_ns),
                        reference_edge=step.reference_edge,
                        target_edge=step.target_edge,
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
                    "accepted": accepted,
                    "rejected": rejected,
                }
                write_json(output / "status.json", status)
            if accepted != ACCEPTED_REQUIRED:
                raise RuntimeError(
                    f"{delay_ns} ns: only {accepted} accepted after {accepted + rejected} attempts"
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
                SAFE_IDLE, output_path=output / "safe_idle_after_acquisition.json"
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
        write_json(output / "status.json", status)
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
