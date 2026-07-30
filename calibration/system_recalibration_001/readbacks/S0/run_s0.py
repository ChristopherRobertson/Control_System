"""Execute campaign S0 only: ownership, safe idle, identity, and interlocks.

This script is intentionally campaign-local evidence. It never enables a T660
channel, starts a trigger source, arms a laser, tunes a laser, or starts a scan.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import traceback
from typing import Any

import serial
import yaml


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.mircat_service import MircatService  # noqa: E402
from control_app.devices.t660_service import T660Service  # noqa: E402
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402


RECORD_DIR = Path(__file__).resolve().parent
OPERATOR = "Christopher Robertson"
CAMPAIGN = "system_recalibration_001"
SAFE_RECIPE_PATH = REPO_ROOT / "recipes" / "safe_idle.yaml"
EXPECTED_IDENTITIES = {
    "t660_1": {"serial_number": "00369", "model_family": "T660"},
    "t660_2": {"serial_number": "00431", "model_family": "T660"},
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def write_json(name: str, value: Any) -> None:
    (RECORD_DIR / name).write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def response_text(query: dict[str, Any]) -> str | None:
    if not query.get("ok"):
        return None
    return str(query.get("response", "")).strip()


def channel_off_evidence(service: T660Service) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for channel in "ABCD":
        query = service._safe_query(f"CHAN:ON? {channel}")
        result[channel] = query
    result["all_disabled"] = all(
        item.get("ok") and str(item.get("response", "")).strip().upper() == "OFF"
        for channel, item in result.items()
        if channel in "ABCD"
    )
    return result


def identity_matches(unit: str, identity: str) -> tuple[bool, list[str]]:
    expected = EXPECTED_IDENTITIES[unit]
    upper = identity.upper()
    missing = [
        value
        for value in (expected["serial_number"], expected["model_family"])
        if str(value).upper() not in upper
    ]
    return not missing, missing


def best_effort_t660_safe(service: T660Service, events: list[dict[str, Any]]) -> None:
    for command in ("STOP", "TRIG:SOUR OFF", "CHAN:OFF A", "CHAN:OFF B", "CHAN:OFF C", "CHAN:OFF D"):
        try:
            service.command(command, expect_response=False)
            events.append({"timestamp_utc": utc_now(), "command": command, "ok": True})
        except BaseException as exc:  # preserve every cleanup failure
            events.append(
                {
                    "timestamp_utc": utc_now(),
                    "command": command,
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )


def main() -> int:
    RECORD_DIR.mkdir(parents=True, exist_ok=False) if not RECORD_DIR.exists() else None
    command_log_path = RECORD_DIR / "command_log.txt"
    inventory = load_config_inventory(write_files=False)
    recipe = yaml.safe_load(SAFE_RECIPE_PATH.read_text(encoding="utf-8"))
    manager = TimingRecipeManager(inventory)
    resolved = manager.validate_recipe(recipe)["resolved_settings"]

    record: dict[str, Any] = {
        "campaign": CAMPAIGN,
        "phase": "S0",
        "operator": OPERATOR,
        "started_utc": utc_now(),
        "baseline_worktree_was_clean_before_s0_record_creation": True,
        "canonical_outputs_before_s0": {
            "calibration/timing_calibration.csv": (
                REPO_ROOT / "calibration" / "timing_calibration.csv"
            ).exists(),
            "calibration/timing_offsets.yaml": (
                REPO_ROOT / "calibration" / "timing_offsets.yaml"
            ).exists(),
        },
        "configured_device_identities": {
            "t660_1": EXPECTED_IDENTITIES["t660_1"],
            "t660_2": EXPECTED_IDENTITIES["t660_2"],
            "mircat": {
                "model_number": inventory.devices["mircat"].get("model_number"),
                "serial_number": inventory.devices["mircat"].get("serial_number"),
            },
            "ndyag": {
                "model_number": inventory.devices["ndyag"].get("model_number"),
                "serial_number": inventory.devices["ndyag"].get("serial_number"),
                "identity_source": "P0 physical inventory; no S0 command interface",
            },
        },
        "operator_physical_confirmations": {
            "confirmation_source": "Christopher Robertson confirmation in the active Codex task",
            "recorded_utc": utc_now(),
            "both_lasers_positively_inhibited": True,
            "room_interlock_and_installed_controls_authoritative_safe": True,
            "normal_wiring_untouched": True,
            "t660_1_channel_d_disabled_disconnected_unmapped": True,
            "mircat_db9_pin_5_disconnected": True,
            "mircat_db9_pins_6_and_8_unwired": True,
            "arduino_mux_disabled_and_excluded": True,
            "fixed_12_inch_ddg_bulkhead_assemblies_untouched": True,
            "clock_splitter_01_normal_distribution": True,
            "other_t660_and_mircat_clients_closed": True,
        },
        "prohibited_actions": {
            "laser_emission_commands_sent": False,
            "laser_arm_commands_sent": False,
            "process_trigger_pulses_generated": False,
            "t660_channels_enabled": False,
            "trigger_sources_started": False,
            "cables_moved": False,
            "arduino_mux_used": False,
            "canonical_outputs_created_or_modified": False,
        },
        "ownership": {},
        "t660_initial_disabled_readback_before_identity": {},
        "t660_identity_and_firmware": {},
        "safe_idle": {},
        "mircat": {},
        "independent_safety_evidence": {
            "physical_operator_confirmation": "PASS",
            "software_readbacks": "PENDING",
        },
        "blockers": [],
        "status": "IN_PROGRESS",
    }
    write_json("s0_record.json", record)

    serial_handles: dict[str, serial.Serial] = {}
    t660_services: dict[str, T660Service] = {}
    mircat: MircatService | None = None
    mircat_initialized = False
    cleanup_events: list[dict[str, Any]] = []

    with command_log_path.open("x", encoding="utf-8", newline="\n") as command_log:
        command_log.write(f"{utc_now()} S0 START operator={OPERATOR}\n")
        try:
            # Acquire both Windows serial endpoints without sending any command.
            for unit in ("t660_1", "t660_2"):
                cfg = deepcopy(inventory.t660_devices[unit])
                port = str(cfg["preferred_port"])
                handle = serial.Serial(
                    port=port,
                    baudrate=int(cfg["baudrate"]),
                    timeout=0.5,
                    write_timeout=0.5,
                )
                serial_handles[unit] = handle
                record["ownership"][unit] = {
                    "method": "exclusive Windows serial handle",
                    "port": port,
                    "acquired": True,
                    "timestamp_utc": utc_now(),
                }
                service = T660Service(unit, cfg, command_log=command_log)
                service._serial = handle
                t660_services[unit] = service

            # MIRcat Initialize is the SDK's single-client ownership acquisition.
            mircat_cfg = inventory.devices["mircat"]
            mircat = MircatService(mircat_cfg, command_log=command_log)
            mircat.initialize()
            mircat_initialized = True
            record["ownership"]["mircat"] = {
                "method": "MIRcatSDK_Initialize single-client session",
                "acquired": True,
                "timestamp_utc": utc_now(),
            }
            write_json("s0_record.json", record)

            # Enter documented command mode, then immediately STOP/OFF before
            # any identity or firmware query.
            for unit in ("t660_1", "t660_2"):
                service = t660_services[unit]
                service._set_p500_session()
                service.command("STOP", expect_response=False)
                if unit == "t660_2":
                    service.command("TFRame:STOp", expect_response=False)
                service.command("TRIG:SOUR OFF", expect_response=False)
                for channel in "ABCD":
                    service.command(f"CHAN:OFF {channel}", expect_response=False)

            for unit in ("t660_1", "t660_2"):
                evidence = channel_off_evidence(t660_services[unit])
                trigger_query = t660_services[unit]._safe_query("TRIG:SOUR?")
                evidence["trigger_source"] = trigger_query
                evidence["trigger_source_off"] = (
                    trigger_query.get("ok")
                    and str(trigger_query.get("response", "")).strip().upper() == "OFF"
                )
                record["t660_initial_disabled_readback_before_identity"][unit] = evidence
            write_json("t660_preidentity_disabled_readback.json", record["t660_initial_disabled_readback_before_identity"])
            if not all(
                item["all_disabled"] and item["trigger_source_off"]
                for item in record["t660_initial_disabled_readback_before_identity"].values()
            ):
                raise RuntimeError(
                    "initial T660 STOP/OFF readback failed before identity; identity/firmware queries were not permitted"
                )

            # Identity and firmware are permitted only now.
            for unit in ("t660_1", "t660_2"):
                identity = t660_services[unit].identify()
                matches, missing = identity_matches(unit, identity)
                parts = [part.strip() for part in identity.split(",")]
                record["t660_identity_and_firmware"][unit] = {
                    "identity_response": identity,
                    "firmware_readback": parts[3] if len(parts) >= 4 and parts[3] else None,
                    "expected": EXPECTED_IDENTITIES[unit],
                    "identity_matches_expected": matches,
                    "missing_expected_tokens": missing,
                    "timestamp_utc": utc_now(),
                }
                if not matches or not record["t660_identity_and_firmware"][unit]["firmware_readback"]:
                    raise RuntimeError(f"{unit} identity or firmware readback did not match the P0 inventory")
            write_json("t660_identity_firmware.json", record["t660_identity_and_firmware"])

            # Apply the complete approved recipe using the already-owned sessions.
            devices_readback: dict[str, Any] = {}
            for unit in ("t660_1", "t660_2"):
                t660_services[unit].apply_recipe(resolved[unit])
                devices_readback[unit] = t660_services[unit].read_active_settings()
            mismatches = TimingRecipeManager._compare_readback(resolved, devices_readback)
            record["safe_idle"] = {
                "recipe_path": str(SAFE_RECIPE_PATH),
                "resolved_settings": resolved,
                "devices": devices_readback,
                "mismatches": mismatches,
                "matches_recipe": not mismatches,
            }
            write_json("t660_safe_idle_command_readback.json", record["safe_idle"])
            if mismatches:
                raise RuntimeError(f"approved safe-idle recipe readback mismatch: {mismatches}")
            if not all(
                response_text(devices_readback[unit]["channels"][channel]["enabled"]) == "OFF"
                for unit in ("t660_1", "t660_2")
                for channel in "ABCD"
            ):
                raise RuntimeError("not every T660 channel read back OFF after full safe idle")

            # With SDK ownership established, positively close MIRcat emission,
            # stop any scan, and disarm. Never arm, tune, emit, or trigger.
            mircat.turn_emission_off()
            stop_scan_return_code = mircat.stop_scan_if_needed()
            mircat.disarm()
            mircat_state = mircat.read_state().to_dict()
            record["mircat"] = {
                "configured_identity": {
                    "model_number": mircat_cfg.get("model_number"),
                    "serial_number": mircat_cfg.get("serial_number"),
                },
                "sdk_api_version_readback": mircat_state.get("api_version"),
                "stop_scan_return_code": stop_scan_return_code,
                "state_readback": mircat_state,
                "required_state_checks": {
                    "connected": mircat_state.get("connected") is True,
                    "emission_off": mircat_state.get("emission_on") is False,
                    "disarmed": mircat_state.get("armed") is False,
                    "interlock_set": mircat_state.get("interlock_set") is True,
                    "scan_not_in_progress": mircat_state.get("scan_in_progress") is False,
                    "scan_not_active": mircat_state.get("scan_active") is False,
                    "status_mask_not_scanning": mircat_state.get("status_mask_scanning") is False,
                },
            }
            write_json("mircat_safe_state_readback.json", record["mircat"])
            if mircat_state.get("last_error"):
                raise RuntimeError(f"MIRcat state readback incomplete: {mircat_state['last_error']}")
            if not all(record["mircat"]["required_state_checks"].values()):
                raise RuntimeError(
                    f"MIRcat safe/interlock state check failed: {record['mircat']['required_state_checks']}"
                )

            record["independent_safety_evidence"]["software_readbacks"] = "PASS"
            record["status"] = "PASS"
        except BaseException as exc:
            blocker = f"{type(exc).__name__}: {exc}"
            record["blockers"].append(blocker)
            record["status"] = "BLOCKED"
            record["exception_traceback"] = traceback.format_exc()
            command_log.write(f"{utc_now()} S0 BLOCKED {blocker}\n")
        finally:
            # Leave every acquired device in the safest achievable state.
            for unit, service in t660_services.items():
                best_effort_t660_safe(service, cleanup_events)
                try:
                    final_disabled = channel_off_evidence(service)
                    final_trigger = service._safe_query("TRIG:SOUR?")
                    record.setdefault("final_safe_idle", {})[unit] = {
                        "channels": final_disabled,
                        "trigger_source": final_trigger,
                        "verified": bool(
                            final_disabled.get("all_disabled")
                            and final_trigger.get("ok")
                            and str(final_trigger.get("response", "")).strip().upper() == "OFF"
                        ),
                    }
                except BaseException as exc:
                    record.setdefault("final_safe_idle", {})[unit] = {
                        "verified": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    }

            if mircat is not None and mircat._sdk is not None:
                for label, action in (
                    ("emission_off", mircat.turn_emission_off),
                    ("stop_scan", mircat.stop_scan_if_needed),
                    ("disarm", mircat.disarm),
                ):
                    try:
                        action()
                        cleanup_events.append({"timestamp_utc": utc_now(), "command": f"mircat.{label}", "ok": True})
                    except BaseException as exc:
                        cleanup_events.append(
                            {
                                "timestamp_utc": utc_now(),
                                "command": f"mircat.{label}",
                                "ok": False,
                                "error": f"{type(exc).__name__}: {exc}",
                            }
                        )
                if mircat_initialized:
                    try:
                        final_mircat = mircat.read_state().to_dict()
                        record.setdefault("final_safe_idle", {})["mircat"] = {
                            "state": final_mircat,
                            "verified": bool(
                                final_mircat.get("connected") is True
                                and final_mircat.get("emission_on") is False
                                and final_mircat.get("armed") is False
                                and final_mircat.get("scan_in_progress") is False
                                and final_mircat.get("scan_active") is False
                            ),
                        }
                    except BaseException as exc:
                        record.setdefault("final_safe_idle", {})["mircat"] = {
                            "verified": False,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                else:
                    record.setdefault("final_safe_idle", {})["mircat"] = {
                        "verified": False,
                        "error": "MIRcat SDK ownership was not established",
                    }
                try:
                    mircat.deinitialize()
                except BaseException as exc:
                    cleanup_events.append(
                        {
                            "timestamp_utc": utc_now(),
                            "command": "mircat.deinitialize",
                            "ok": False,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )

            for unit, service in t660_services.items():
                try:
                    service.close()
                except BaseException as exc:
                    cleanup_events.append(
                        {
                            "timestamp_utc": utc_now(),
                            "command": f"{unit}.close",
                            "ok": False,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
            for unit, handle in serial_handles.items():
                if handle.is_open:
                    try:
                        handle.close()
                    except BaseException as exc:
                        cleanup_events.append(
                            {
                                "timestamp_utc": utc_now(),
                                "command": f"{unit}.serial_close",
                                "ok": False,
                                "error": f"{type(exc).__name__}: {exc}",
                            }
                        )

            record["cleanup_events"] = cleanup_events
            record["ownership_released"] = {
                "t660_1": not serial_handles.get("t660_1") or not serial_handles["t660_1"].is_open,
                "t660_2": not serial_handles.get("t660_2") or not serial_handles["t660_2"].is_open,
                "mircat": not mircat_initialized or (mircat is not None and not mircat._initialized),
            }
            final_items = record.get("final_safe_idle", {})
            required_final_devices = {"t660_1", "t660_2", "mircat"}
            final_verified = required_final_devices == set(final_items) and all(
                final_items[device].get("verified") is True
                for device in required_final_devices
            )
            if not final_verified:
                record["blockers"].append("final safe-idle readback was not fully verified")
                record["status"] = "BLOCKED_UNSAFE_STATE_UNVERIFIED"
            if any(not item.get("ok") for item in cleanup_events):
                record["blockers"].append("one or more best-effort cleanup actions failed")
                if record["status"] == "PASS":
                    record["status"] = "BLOCKED"
            record["final_verified_safe_idle_state"] = final_verified
            record["completed_utc"] = utc_now()
            record["canonical_outputs_after_s0"] = {
                "calibration/timing_calibration.csv": (
                    REPO_ROOT / "calibration" / "timing_calibration.csv"
                ).exists(),
                "calibration/timing_offsets.yaml": (
                    REPO_ROOT / "calibration" / "timing_offsets.yaml"
                ).exists(),
            }
            if any(record["canonical_outputs_after_s0"].values()):
                record["status"] = "BLOCKED"
                record["blockers"].append("a prohibited canonical calibration output exists after S0")
            write_json("s0_record.json", record)
            command_log.write(
                f"{utc_now()} S0 END status={record['status']} final_verified={final_verified}\n"
            )

    return 0 if record["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
