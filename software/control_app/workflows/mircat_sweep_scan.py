"""Current-wiring MIRcat sweep with DIO-gated, per-channel calibration."""

from __future__ import annotations

from pathlib import Path
import json
import math
import time
import threading

from control_app.config_loader import REPO_ROOT
from control_app.paths import EVIDENCE_ROOT, resolve_compat_path
from control_app.devices.hf2li_service import HF2LIService
from control_app.devices.mircat_service import (
    MircatService,
    PROC_TRIG_MODE_INTERNAL,
    PULSE_MODE_EXTERNAL_TRIGGER,
    UNITS_CM1,
)
from control_app.workflows.sweep_export import (
    dio_bit_diagnostics,
    segmented_kaleidagraph_rows_from_hf2li_record,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager


class MircatSweepScanError(RuntimeError):
    pass


def _validate_campaign_gate(request: dict, run_dir: str | Path) -> None:
    gate = request.get("campaign_gate")
    if not isinstance(gate, dict):
        raise MircatSweepScanError("Sweep recipe does not define a campaign_gate")
    if gate.get("status") != "APPROVED_FOR_EXECUTION":
        raise MircatSweepScanError(
            "Sweep recipe is a non-executable candidate. Approve the named calibration "
            "phase and freeze its phase directory before hardware use."
        )
    campaign_id = str(gate.get("campaign_id", "")).strip()
    phase_id = str(gate.get("phase_id", "")).strip()
    phase_run_id = str(gate.get("phase_run_id", "")).strip()
    declared_phases = {str(value) for value in gate.get("allowed_phases", [])}
    workflow_phases = {"MD-01", "MSW-01"}
    if declared_phases != workflow_phases:
        raise MircatSweepScanError(
            "Sweep recipe must declare exactly the MD-01 and MSW-01 qualification phases"
        )
    if campaign_id != "system_recalibration_001" or phase_id not in workflow_phases:
        raise MircatSweepScanError("Sweep campaign or phase is not allowed by the recipe gate")
    if not phase_run_id or phase_run_id == "USER_INPUT_REQUIRED":
        raise MircatSweepScanError("Sweep campaign gate does not define an approved phase_run_id")

    approved_value = str(gate.get("approved_phase_directory", "")).strip()
    if not approved_value or approved_value == "USER_INPUT_REQUIRED":
        raise MircatSweepScanError("Sweep campaign gate does not define an approved phase directory")
    approved_dir = Path(approved_value)
    if not approved_dir.is_absolute():
        approved_dir = resolve_compat_path(approved_dir)
    approved_dir = approved_dir.resolve()
    expected_dir = (
        EVIDENCE_ROOT
        / "calibration"
        / campaign_id
        / "phases"
        / phase_id
    ).resolve()
    if approved_dir != expected_dir:
        raise MircatSweepScanError(
            f"Approved phase directory must be {expected_dir}; received {approved_dir}"
        )
    resolved_run_dir = Path(run_dir).resolve()
    if resolved_run_dir != approved_dir and approved_dir not in resolved_run_dir.parents:
        raise MircatSweepScanError(
            "Sweep output must remain inside the approved stable calibration phase directory"
        )


def run_gui_owned_sweep_capture(*, request: dict, run_dir: str | Path, command_log=None) -> dict:
    """Acquire a GUI-started MIRcat scan while never opening its SDK session."""

    _validate_campaign_gate(request, run_dir)
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    mircat_cfg, hf_cfg = request["mircat"], request["hf2li"]
    acquisition_cfg = hf_cfg["acquisition"]
    timing_demodulator = int(acquisition_cfg["timing_demodulator_api_index"])
    duration = float(acquisition_cfg.get("stream_record_s", 30.0))
    hf = HF2LIService.from_config(command_log=command_log)
    try:
        TimingRecipeManager(command_log=command_log).apply_recipe(
            "instrument/recipes/mircat_sweep_scan.yaml",
            output_path=run_dir / "t660_sweep_scan_readback.json",
        )
        hf.connect()
        preset = hf.load_preset(str(hf_cfg["preset"]))
        hf.apply_preset(preset)
        expected_reference_hz = float(mircat_cfg["pulse_rate_hz"])
        reference_hz = hf.get_oscillator_frequency(0)
        if abs(reference_hz - expected_reference_hz) > expected_reference_hz * 0.02:
            raise MircatSweepScanError(
                "HF2LI external reference is not locked to the required 2 MHz clock "
                f"(Oscillator 1 reads {reference_hz:.6g} Hz; expected {expected_reference_hz:.6g} Hz)."
            )
        record = hf.acquire_record(
            duration_s=duration,
            demodulators=[0, 3, timing_demodulator],
            fields=["r", "dio"],
        )
        save_summary = hf.save_record(
            record,
            raw_csv_path=run_dir / "hf2li_gui_sweep_raw.csv",
            summary_csv_path=run_dir / "hf2li_gui_sweep_summary.csv",
        )
        clockbase = hf.get_clockbase()
        diagnostics = dio_bit_diagnostics(
            record, timing_demodulator=timing_demodulator, clockbase_hz=clockbase
        )
        diagnostics_path = run_dir / "dio_bit_diagnostics.json"
        diagnostics_path.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")

        mapping = acquisition_cfg.get("confirmed_dio_mapping") or {}
        common = {
            "mircat_control_mode": "gui_manual",
            "mircat_sdk_accessed": False,
            "acquisition_duration_s": duration,
            "raw_record": save_summary,
            "dio_diagnostics_path": str(diagnostics_path),
            "dio_diagnostics": diagnostics,
        }
        if not bool(mapping.get("experimentally_confirmed", False)):
            return {
                **common,
                "mapping_required": True,
                "point_count": 0,
            }

        required = ("scan_direction_bit", "sweep_active_bit", "wavelength_trigger_bit")
        if any(mapping.get(key) is None for key in required):
            raise MircatSweepScanError("Confirmed DIO mapping is incomplete")
        start = float(mircat_cfg["start_cm1"])
        stop = float(mircat_cfg["stop_cm1"])
        interval = float(acquisition_cfg["wavelength_trigger_interval_cm1"])
        rows, timing = segmented_kaleidagraph_rows_from_hf2li_record(
            record,
            wavelength_targets_cm1=_wavelength_targets(start, stop, interval),
            sample_demodulator=0,
            reference_demodulator=3,
            timing_demodulator=timing_demodulator,
            sweep_active_bit=int(mapping["sweep_active_bit"]),
            wavelength_trigger_bit=int(mapping["wavelength_trigger_bit"]),
        )
        return {
            **common,
            "mapping_required": False,
            "scan_rows": rows,
            "point_count": len(rows),
            "timing": timing,
        }
    finally:
        hf.close()
        try:
            TimingRecipeManager(command_log=command_log).apply_recipe(
                "instrument/recipes/safe_idle.yaml", output_path=run_dir / "safe_idle_after_sweep.json"
            )
        except Exception:
            pass


def run_sweep_scan(*, request: dict, run_dir: str | Path, command_log=None) -> dict:
    """Run a DIO-gated, wavelength-trigger-calibrated normal sweep."""
    _validate_campaign_gate(request, run_dir)
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    mircat_cfg, hf_cfg = request["mircat"], request["hf2li"]
    start, stop, rate = (float(mircat_cfg[key]) for key in ("start_cm1", "stop_cm1", "scan_rate_cm1_s"))
    nominal_duration = abs(stop - start) / rate
    acquisition_cfg = hf_cfg["acquisition"]
    mapping = acquisition_cfg.get("confirmed_dio_mapping") or {}
    if not bool(mapping.get("experimentally_confirmed", False)):
        raise MircatSweepScanError(
            "HF2LI DIO mapping is not experimentally confirmed. Identify the complete-word bits for "
            "DB9 pin 1 Scan Direction, pin 2 Sweep Active, and pin 3 Wavelength Trigger, then record "
            "them in instrument/recipes/mircat_sweep_scan.yaml before laser operation."
        )
    required_mapping = ("scan_direction_bit", "sweep_active_bit", "wavelength_trigger_bit")
    if any(mapping.get(key) is None for key in required_mapping):
        raise MircatSweepScanError("Confirmed DIO mapping is incomplete: " + ", ".join(required_mapping))
    mapped_bits = [int(mapping[key]) for key in required_mapping]
    if len(set(mapped_bits)) != len(mapped_bits) or any(bit < 0 or bit > 31 for bit in mapped_bits):
        raise MircatSweepScanError("Confirmed DIO bits must be three distinct values from 0 through 31")
    interval_cm1 = float(acquisition_cfg.get("wavelength_trigger_interval_cm1", 5.0))
    wavelength_trigger_pulse_width_us = int(
        acquisition_cfg.get("wavelength_trigger_pulse_width_us", 500)
    )
    wavelength_targets = _wavelength_targets(start, stop, interval_cm1)
    external_process_trigger = bool(mircat_cfg.get("external_process_trigger_gui_confirmed", False))
    if external_process_trigger:
        raise MircatSweepScanError(
            "Automated external Process Trigger is intentionally disabled until its channel-by-channel "
            "pulse count/timing has been implemented from the completed GUI test. Use internal process "
            "trigger mode for this run."
        )
    hf = HF2LIService.from_config(command_log=command_log)
    mircat = MircatService.from_config(command_log=command_log)
    try:
        TimingRecipeManager(command_log=command_log).apply_recipe(
            "instrument/recipes/mircat_sweep_scan.yaml",
            output_path=run_dir / "t660_sweep_scan_readback.json",
        )
        hf.connect()
        preset = hf.load_preset(str(hf_cfg["preset"]))
        hf.apply_preset(preset)
        reference_hz = hf.get_oscillator_frequency(0)
        expected_reference_hz = float(mircat_cfg["pulse_rate_hz"])
        if abs(reference_hz - expected_reference_hz) > expected_reference_hz * 0.02:
            raise MircatSweepScanError(
                "HF2LI external reference is not locked to the required 2 MHz clock "
                f"(Oscillator 1 reads {reference_hz:.6g} Hz; expected {expected_reference_hz:.6g} Hz). "
                "Verify T660-2 trigger source is SYN, CHA is enabled, and the CHA cable reaches HF2LI DIO0."
            )
        mircat.initialize()
        mircat.arm()
        if not mircat.wait_for_tecs_ready(timeout_s=120, poll_interval_s=0.5):
            raise MircatSweepScanError("MIRcat TECs did not become ready")
        qcl = int(mircat_cfg["qcl"])
        mircat.set_qcl_pulse_params(qcl=qcl, pulse_rate_hz=float(mircat_cfg["pulse_rate_hz"]), pulse_width_ns=float(mircat_cfg["pulse_width_ns"]))
        trigger_readback = mircat.set_external_sweep_trigger_params(
            start_cm1=start,
            stop_cm1=stop,
            wavelength_trigger_interval_cm1=interval_cm1,
            external_process_trigger=False,
        )
        _validate_trigger_readback(
            trigger_readback, start_cm1=start, stop_cm1=stop, interval_cm1=interval_cm1
        )
        observed_pulse_width_us = mircat.set_wavelength_trigger_pulse_width_us(
            wavelength_trigger_pulse_width_us
        )
        if observed_pulse_width_us != wavelength_trigger_pulse_width_us:
            raise MircatSweepScanError(
                "MIRcat wavelength-trigger pulse-width readback "
                f"was {observed_pulse_width_us} us; expected {wavelength_trigger_pulse_width_us} us"
            )
        # A sweep establishes its own start setpoint. Do not enter TuneToWW
        # first: that leaves this firmware in manual-tune mode and blocks either
        # emission or StartSweepScan.
        mircat.cancel_manual_tune()

        timing_demodulator = int(acquisition_cfg["timing_demodulator_api_index"])
        pre_padding = float(acquisition_cfg.get("pre_padding_s", 0.10))
        stream_start_delay = float(acquisition_cfg.get("stream_start_delay_s", 0.05))
        duration = float(acquisition_cfg.get("stream_record_s", 11.0))
        # Low-level LabOne polling retains native timestamps and the complete
        # DIO word continuously through active sweeps and channel gaps.
        hf.start_acquisition(demodulators=[0, 3, timing_demodulator], fields=["r", "dio"])
        try:
            time.sleep(pre_padding)
            # Discard only the pre-scan lock-in settling samples. The retained
            # poll begins before StartSweepScan so the first DIO edges remain.
            hf.read_acquisition(0.001)
            start_errors: list[Exception] = []

            def start_sweep_during_stream() -> None:
                time.sleep(stream_start_delay)
                try:
                    mircat.start_sweep_scan(
                        start_cm1=start,
                        stop_cm1=stop,
                        scan_rate_cm1_s=rate,
                        qcl=qcl,
                        repetitions=int(mircat_cfg["repetitions"]),
                    )
                except Exception as exc:  # noqa: BLE001 - re-raised on UI thread below
                    start_errors.append(exc)

            start_thread = threading.Thread(target=start_sweep_during_stream, daemon=True)
            start_thread.start()
            record = hf.read_acquisition(duration)
            start_thread.join()
            if start_errors:
                raise start_errors[0]
            record["fields"] = ["r", "dio"]
            record["acquisition_mode"] = "labone_streaming_poll"
        finally:
            hf.stop_acquisition()
        try:
            rows, timing = segmented_kaleidagraph_rows_from_hf2li_record(
                record,
                wavelength_targets_cm1=wavelength_targets,
                sample_demodulator=0,
                reference_demodulator=3,
                timing_demodulator=timing_demodulator,
                sweep_active_bit=int(mapping["sweep_active_bit"]),
                wavelength_trigger_bit=int(mapping["wavelength_trigger_bit"]),
            )
        except ValueError:
            (run_dir / "hf2li_record_structure.json").write_text(
                json.dumps(_record_structure(record), indent=2), encoding="utf-8"
            )
            raise
        return {
            "scan_rows": rows,
            "duration_s": nominal_duration,
            "acquisition_duration_s": duration,
            "point_count": len(rows),
            "timing": timing,
            "wavelength_trigger_readback": trigger_readback,
            "wavelength_trigger_pulse_width_us": observed_pulse_width_us,
        }
    finally:
        try: mircat.stop_scan_if_needed(); mircat.turn_emission_off(); mircat.disarm(); mircat.deinitialize()
        except Exception: pass
        hf.close()
        try:
            TimingRecipeManager(command_log=command_log).apply_recipe(
                "instrument/recipes/safe_idle.yaml", output_path=run_dir / "safe_idle_after_sweep.json"
            )
        except Exception:
            pass


def _wavelength_targets(start_cm1: float, stop_cm1: float, interval_cm1: float) -> list[float]:
    """Return the exact ordered target sequence programmed into the MIRcat."""
    if interval_cm1 <= 0:
        raise MircatSweepScanError("Wavelength-trigger interval must be positive")
    direction = 1.0 if stop_cm1 >= start_cm1 else -1.0
    targets: list[float] = []
    value = float(start_cm1)
    tolerance = interval_cm1 * 1e-9
    while (value - stop_cm1) * direction <= tolerance:
        targets.append(value)
        value += direction * interval_cm1
    if abs(targets[-1] - stop_cm1) > tolerance:
        targets.append(float(stop_cm1))
    return targets


def _validate_trigger_readback(
    readback: dict, *, start_cm1: float, stop_cm1: float, interval_cm1: float
) -> None:
    expected_modes = {
        "pulse_mode": PULSE_MODE_EXTERNAL_TRIGGER,
        "process_trigger_mode": PROC_TRIG_MODE_INTERNAL,
        "units": UNITS_CM1,
    }
    for key, expected in expected_modes.items():
        if int(readback.get(key, -1)) != expected:
            raise MircatSweepScanError(
                f"MIRcat wavelength-trigger readback {key}={readback.get(key)!r}; expected {expected}"
            )
    for key, expected in (
        ("start", start_cm1),
        ("stop", stop_cm1),
        ("interval", interval_cm1),
    ):
        observed = float(readback.get(key, float("nan")))
        if not math.isclose(observed, expected, abs_tol=1e-3):
            raise MircatSweepScanError(
                f"MIRcat wavelength-trigger readback {key}={readback.get(key)!r}; expected {expected}"
            )


def _record_structure(record: dict) -> dict:
    """Persist a compact LabOne response schema when a run cannot be parsed."""
    paths: dict[str, list[dict[str, object]]] = {}
    for path, payload in (record.get("data") or {}).items():
        chunks = payload if isinstance(payload, list) else [payload]
        summaries: list[dict[str, object]] = []
        for chunk in chunks:
            if not isinstance(chunk, dict):
                summaries.append({"type": type(chunk).__name__})
                continue
            summaries.append(
                {
                    "fields": sorted(str(key) for key in chunk),
                    "lengths": {
                        str(key): len(value) if hasattr(value, "__len__") else 1
                        for key, value in chunk.items()
                    },
                }
            )
        paths[str(path)] = summaries
    return {"fields_requested": record.get("fields"), "paths": paths}
