"""Finite, laser-inhibited T660/HF2LI format diagnostic, never optical data."""
from __future__ import annotations

from pathlib import Path
from threading import Event

from control_app.devices.hf2li_service import HF2LIService
from control_app.devices.mircat_service import MircatService
from control_app.devices.t660_service import T660Service
from control_app.workflows.phase_scan import PhaseScanSettings, build_phase_scan_plan, PhaseScanEvent
from control_app.workflows.phase_scan_data import HF2_PRESET, ScanStore, write_json, utc_now


def capture_inhibited_diagnostic(root: Path, *, cancel: Event | None = None,
                                progress=lambda message: None, count: int = 3) -> Path:
    """Issue one REM event per unit per record, with all optical-drive outputs off.

    T660-2 C -> HF2LI DIO1 (10 ms high); T660-1 C -> inhibited MIRcat
    process input (10 ms low). A/B/D are disabled on both units. These are
    sequential host commands, NOT a measured common pump/scan time reference.
    """
    if not 1 <= count <= 10:
        raise ValueError("Diagnostic is limited to 1–10 records")
    cancel = cancel or Event()
    store = ScanStore(root, "diagnostic", build_phase_scan_plan(PhaseScanSettings()))
    status, failure = "FAILED", None
    cleanup_errors = []
    restore_differences = []
    hf, qcl = None, None
    units = []
    snapshot = None

    def check_cancel():
        if cancel.is_set():
            raise InterruptedError("Diagnostic aborted")

    def inhibited():
        state = {"interlock_set": qcl.is_interlock_set(), "armed": qcl.is_laser_armed(),
                 "emission": qcl.is_emission_on()}
        if any(state.values()):
            raise RuntimeError("Diagnostic requires MIRcat interlock OPEN, unarmed and emission OFF")
        return state

    def verify_t660(snapshot, *, stopped=False):
        source = snapshot["queries"]["trigger_source"]
        if not source.get("ok") or source.get("response") != ("OFF" if stopped else "REM"):
            raise RuntimeError("T660 trigger source readback did not verify")
        for name, channel in snapshot["channels"].items():
            enabled = channel["enabled"]
            expected = "OFF" if stopped or name != "C" else "ON"
            if not enabled.get("ok") or enabled.get("response") != expected:
                raise RuntimeError(f"T660 channel {name} state did not verify as {expected}")

    with (store.path / "commands.txt").open("x", encoding="utf-8") as log:
        try:
            progress("Checking MIRcat interlock; no arm or emission commands will be sent.")
            qcl = MircatService.from_config(command_log=log)
            qcl.initialize()
            write_json(store.path / "mircat_before.json", inhibited())
            check_cancel()
            for name in ("t660_1", "t660_2"):
                progress(f"Connecting {name}; disabling A, B and D.")
                unit = T660Service.from_config(name, command_log=log)
                units.append(unit)
                unit.connect()
                identity = unit.identify()
                expected = str(unit.device_config["serial_number"])
                if expected not in [part.strip() for part in identity.split(",")]:
                    raise RuntimeError(f"Unexpected identity for {name}: {identity}")
                write_json(store.path / f"{name}_before.json", unit.read_active_settings())
                unit.set_trigger_source("OFF")
                unit.command("STOP", expect_response=False)
                for channel in "ABCD":
                    unit.disable_channel(channel)
                channels = {c: {"enabled": False} for c in "ABD"}
                channels["C"] = {"enabled": True, "delay": "0ns", "width": "10ms",
                                 "polarity": "negative" if name == "t660_1" else "positive",
                                 "termination": "50OHM"}
                recipe = {"stop_first": True, "trigger_source": "OFF", "gate_mode": 0,
                          "burst_enabled": False, "channels": channels}
                if name == "t660_2":
                    recipe["frames_engine"] = "OFF"
                unit.apply_recipe(recipe)
                unit.force_eod()
                unit.set_trigger_source("REM")
                # REM selects the source; START separately enables the delay engine.
                # In REM this does not generate a periodic train.
                unit.command("START", expect_response=False)
                configured = unit.read_active_settings()
                write_json(store.path / f"{name}_configured.json", configured)
                verify_t660(configured)
                check_cancel()
            progress("Applying the saved HF2LI sweep preset; original settings will be restored.")
            hf = HF2LIService.from_config(command_log=log)
            hf.connect()
            preset = hf.load_preset(HF2_PRESET)
            snapshot = hf.export_settings_snapshot(preset=preset)
            write_json(store.path / "hf2li_before.json", snapshot)
            if snapshot["read_errors"]:
                raise RuntimeError("Cannot preserve the original HF2LI configuration: snapshot incomplete")
            hf.apply_preset(preset)
            write_json(store.path / "hf2li_configured.json", hf.export_settings_snapshot(preset=preset))
            clockbase = hf.get_clockbase()
            for index in range(count):
                check_cancel()
                progress(f"Recording inhibited diagnostic {index+1}/{count}.")
                state = inhibited()
                before = {unit.name: unit.get_shot_count() for unit in units}
                chunks, capture_errors = [], []
                after = {}
                try:
                    hf.start_acquisition(demodulators=(0, 2, 3))
                    chunks.append(hf.read_acquisition(0.05))
                    for unit in units:
                        check_cancel()
                        unit.fire_remote_trigger()
                    chunks.append(hf.read_acquisition(0.20))
                except Exception as exc:
                    capture_errors.append(f"{type(exc).__name__}: {exc}")
                finally:
                    try:
                        hf.stop_acquisition()
                    except Exception as exc:
                        capture_errors.append(f"Stop acquisition: {exc}")
                    for unit in units:
                        try:
                            after[unit.name] = unit.get_shot_count()
                        except Exception as exc:
                            capture_errors.append(f"{unit.name} counter: {exc}")
                event = PhaseScanEvent(index, 1, None, False, None)
                store.save_scan(event, {"kind": "INHIBITED_DIAGNOSTIC", "optical_valid": False,
                    "captured_utc": utc_now(), "clockbase_hz": clockbase, "native_chunks": chunks,
                    "mircat_state": state, "shot_counters_before": before, "shot_counters_after": after,
                    "capture_errors": capture_errors,
                    "timing_basis": "host_sequential_commands_only",
                    "limitations": ["No optical sweep, optical background or pump arrival was measured.",
                                    "Do not assign nominal wavenumbers or compute absorbance from this record."]})
                check_cancel()
                if capture_errors:
                    raise RuntimeError("; ".join(capture_errors))
                if any((after[key]-before[key]) % (2**32) != 1 for key in before):
                    raise RuntimeError("Expected exactly one remote event from each T660")
            status = "DIAGNOSTIC_COMPLETE"
        except InterruptedError as exc:
            status, failure = "ABORTED", str(exc)
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"
        finally:
            for unit in reversed(units):
                # Attempt each safe-state action even if another command fails.
                for label, operation in [("trigger_off", lambda u=unit: u.set_trigger_source("OFF")),
                        ("stop", lambda u=unit: u.command("STOP", expect_response=False)),
                        *[(f"disable_{ch}", lambda u=unit, c=ch: u.disable_channel(c)) for ch in "ABCD"]]:
                    try:
                        operation()
                    except Exception as exc:
                        cleanup_errors.append(f"{unit.name} {label}: {exc}")
                try:
                    after = unit.read_active_settings()
                    write_json(store.path / f"{unit.name}_after.json", after)
                    verify_t660(after, stopped=True)
                except Exception as exc:
                    cleanup_errors.append(f"{unit.name} final readback: {exc}")
                try:
                    unit.close()
                except Exception as exc:
                    cleanup_errors.append(f"{unit.name} close: {exc}")
            if hf is not None:
                try:
                    hf.stop_acquisition()
                    if snapshot is not None and not snapshot["read_errors"]:
                        hf.reload_settings_snapshot(snapshot)
                        restored = hf.export_settings_snapshot(preset=preset)
                        write_json(store.path / "hf2li_restored.json", restored)
                        comparison = hf.compare_settings_snapshots(snapshot, restored)
                        restore_differences.extend(comparison["mismatches"])
                        write_json(store.path / "hf2li_restoration_comparison.json", comparison)
                        if restored["read_errors"]:
                            cleanup_errors.append("HF2LI restoration readback is incomplete")
                        if comparison["mismatches"] or restored["read_errors"]:
                            progress("HF2LI restore has readback differences; see hf2li_restoration_comparison.json.")
                except Exception as exc:
                    cleanup_errors.append(f"HF2LI restore: {exc}")
                finally:
                    try:
                        hf.close()
                    except Exception as exc:
                        cleanup_errors.append(f"HF2LI close: {exc}")
            if qcl is not None:
                try:
                    write_json(store.path / "mircat_after.json", inhibited())
                except Exception as exc:
                    cleanup_errors.append(f"MIRcat final readback: {exc}")
                finally:
                    try:
                        qcl.deinitialize()
                    except Exception as exc:
                        cleanup_errors.append(f"MIRcat deinitialize: {exc}")
            if cleanup_errors:
                status = "FAILED_SAFE_STATE_UNVERIFIED"
            store.finish(status, error=failure, cleanup_errors=cleanup_errors,
                         restoration_differences=restore_differences, optical_valid=False)
    if status != "DIAGNOSTIC_COMPLETE":
        raise RuntimeError(f"{failure or status}; cleanup errors: {cleanup_errors}. Records: {store.path}")
    from control_app.workflows.phase_scan_diagnostic_analysis import inspect_diagnostic
    progress("Exporting diagnostic samples and native-format summary…")
    inspect_diagnostic(store.path)
    return store.path
