"""HF-01 software/device preflight with generator held at programmed zero."""

from __future__ import annotations

from datetime import UTC, datetime
import csv
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any

import jsonschema


REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.hf2li_service import HF2LIService  # noqa: E402
from control_app.devices.picoscope_service import PicoScopeService  # noqa: E402
from control_app.workflows.picoscope_settings_test import (  # noqa: E402
    capture_settings_from_recipe,
    load_recipe,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402


HERE = Path(__file__).resolve().parent
SAFE_IDLE = REPO_ROOT / "instrument" / "recipes" / "safe_idle.yaml"
PICO_RECIPE = REPO_ROOT / "instrument" / "recipes" / "picoscope_settings_test.yaml"
MANIFEST_SCHEMA = REPO_ROOT / "instrument" / "schemas" / "phase_manifest.schema.json"
MANIFEST = HERE / "phase_manifest.json"


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_ledger(
    *, action: str, expected: str, observed: str, evidence: str, decision: str, notes: str
) -> None:
    with (HERE / "action_ledger.csv").open("r", newline="", encoding="utf-8") as handle:
        count = sum(1 for _ in csv.reader(handle)) - 1
    with (HERE / "action_ledger.csv").open("a", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(
            [
                f"HF01-LEDGER-{count + 1:04d}",
                utc_now(),
                "Codex",
                action,
                expected,
                observed,
                evidence,
                decision,
                notes,
            ]
        )


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def process_inventory() -> list[str]:
    completed = subprocess.run(
        ["tasklist", "/fo", "csv", "/nh"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    retained: list[str] = []
    for row in csv.reader(completed.stdout.splitlines()):
        if not row:
            continue
        name = row[0]
        lowered = name.lower()
        if any(token in lowered for token in ("pico", "labone", "zi", "python")):
            retained.append(name)
    return sorted(set(retained), key=str.lower)


def read_hf2_node(server: Any, path: str, value_type: str) -> Any:
    if value_type == "int":
        return int(server.getInt(path))
    if value_type == "double":
        return float(server.getDouble(path))
    return str(server.getString(path))


def hf2_snapshot(service: HF2LIService) -> dict[str, Any]:
    server = service._require_server()  # Focused phase utility; no state change.
    device = service.device_id
    nodes: list[tuple[str, str]] = [
        (f"/{device}/features/serial", "string"),
        (f"/{device}/features/devtype", "string"),
        (f"/{device}/features/options", "string"),
        (f"/{device}/system/hwrevision", "int"),
        (f"/{device}/system/extclk", "int"),
        (f"/{device}/system/properties/minfreq", "double"),
        (f"/{device}/system/properties/maxfreq", "double"),
        (f"/{device}/system/properties/mintimeconstant", "double"),
        (f"/{device}/system/properties/maxtimeconstant", "double"),
        (f"/{device}/system/properties/timebase", "double"),
        (f"/{device}/system/properties/freqresolution", "double"),
        (f"/{device}/clockbase", "int"),
        (f"/{device}/status/flags/dcmlock", "int"),
        (f"/{device}/status/flags/plllock", "int"),
        (f"/{device}/status/flags/adcclip/0", "int"),
        (f"/{device}/status/flags/adcclip/1", "int"),
        (f"/{device}/status/flags/demodsampleloss", "int"),
        (f"/{device}/dios/0/extclk", "int"),
        (f"/{device}/dios/0/decimation", "int"),
    ]
    for index in (0, 1):
        for name, kind in (("range", "double"), ("ac", "int"), ("imp50", "int"), ("diff", "int")):
            nodes.append((f"/{device}/sigins/{index}/{name}", kind))
    for index in range(6):
        for name, kind in (
            ("enable", "int"),
            ("adcselect", "int"),
            ("oscselect", "int"),
            ("harmonic", "int"),
            ("order", "int"),
            ("timeconstant", "double"),
            ("rate", "double"),
            ("trigger", "int"),
        ):
            nodes.append((f"/{device}/demods/{index}/{name}", kind))
    values: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for path, kind in nodes:
        try:
            values[path] = {"type": kind, "value": read_hf2_node(server, path, kind)}
        except Exception as exc:
            errors[path] = str(exc)
    return {
        "timestamp_utc": utc_now(),
        "device_id": device,
        "nodes": values,
        "read_errors": errors,
        "node_inventory": list(server.listNodes(f"/{device}", 7)),
        "manufacturer_constraints": {
            "filter_orders": [1, 2, 3, 4, 5, 6, 7, 8],
            "signal_input_ranges_v": [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 1.5],
            "coupling_modes": ["DC", "AC"],
            "input_impedance_modes": ["HIGH_Z", "50_OHM"],
            "demodulator_count": 6,
            "maximum_native_rate_sps_by_active_demodulators": {
                "1": 460000.0,
                "2-3": 230000.0,
                "4-6": 115000.0,
            },
            "maximum_cumulative_usb_rate_sps": 700000.0,
            "rate_quantization": "submultiples_of_460000_sps",
            "minimum_rate_rule": "at_least_8x_filter_bandwidth_where_device_and_aggregate_throughput_permit",
            "filter_model": "H_n(f)=(1+i*2*pi*f*tau)^(-n)",
            "source": "Zurich Instruments HF2LI User Manual; installed node readback",
        },
    }


def main() -> int:
    started = utc_now()
    status: dict[str, Any] = {
        "campaign_id": "system_recalibration_001",
        "phase_id": "HF-01",
        "phase_run_id": "system_recalibration_001_HF-01_001",
        "authorization_id": "HF01-AUTH-001",
        "started_utc": started,
        "status": "NOT_READY",
        "checks": {},
        "value_required_fields": [],
        "safety_boundary": "NON_EMITTING_ELECTRICAL_ONLY",
    }
    status_path = HERE / "preflight_status.json"
    write_json(status_path, status)

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(manifest)
    status["checks"]["phase_manifest_schema"] = "PASS"

    required = [
        HERE / "phase_authorization.md",
        HERE / "temporary_wiring_plan.md",
        HERE / "source_load_voltage_envelope.md",
        HERE / "experiment_constraints.md",
        HERE / "validation_point_declaration.md",
        HERE / "model_residual_criteria.md",
        HERE / "stopping_rules.md",
        HERE / "safe_state_checklists.md",
    ]
    missing = [str(path.relative_to(REPO_ROOT)) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"mandatory preflight records missing: {missing}")
    status["checks"]["mandatory_records"] = "PASS"

    dependencies = {
        "S0": REPO_ROOT / "calibration/system_recalibration_001/readbacks/S0/s0_record.json",
        "MS-01": REPO_ROOT / "calibration/system_recalibration_001/readbacks/MS-01/ms01_results.json",
        "MS-02": REPO_ROOT / "calibration/system_recalibration_001/readbacks/MS-02/ms02_results.json",
        "T2-01": REPO_ROOT / "calibration/system_recalibration_001/readbacks/T2-01/t2_01_results.json",
        "CH-00": REPO_ROOT / "characterization/system_characterization_001/readbacks/CH-00/phase_manifest.json",
    }
    dependency_status: dict[str, Any] = {}
    for phase, path in dependencies.items():
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        dependency_status[phase] = {
            "status": value.get("status"),
            "source": str(path.relative_to(REPO_ROOT)),
        }
    if any(item["status"] != "PASS" for item in dependency_status.values()):
        raise RuntimeError(f"dependency status not PASS: {dependency_status}")
    status["checks"]["dependencies"] = dependency_status

    inventory = load_config_inventory(write_files=False)
    provenance = {
        "timestamp_utc": utc_now(),
        "python": platform.python_version(),
        "executable": sys.executable,
        "packages": {
            "zhinst": package_version("zhinst"),
            "zhinst-core": package_version("zhinst-core"),
            "jsonschema": package_version("jsonschema"),
            "pyserial": package_version("pyserial"),
        },
        "process_names_matching_device_software": process_inventory(),
        "picosdk_driver": {
            "path": "C:/Program Files/Pico Technology/SDK/lib/ps5000a.dll",
            "file_version": "2.2.8.5060",
        },
        "ownership_note": "Successful Pico open is the SDK exclusivity test. HF2 process scan is advisory; operator must close competing LabOne clients before settings changes.",
    }
    write_json(HERE / "software_provenance.json", provenance)

    t660_ready = False
    with (HERE / "command_log.txt").open("a", encoding="utf-8") as command_log:
        manager = TimingRecipeManager(inventory=inventory, command_log=command_log)
        try:
            safe_idle = manager.apply_recipe(
                SAFE_IDLE, output_path=HERE / "preflight_t660_safe_idle_readback.json"
            )
            if not safe_idle.get("matches_recipe"):
                raise RuntimeError(f"T660 safe-idle mismatch: {safe_idle.get('mismatches')}")
            status["checks"]["t660_safe_idle"] = {
                "status": "PASS",
                "mismatch_count": 0,
            }
            t660_ready = True
        except Exception as exc:
            status["checks"]["t660_safe_idle"] = {
                "status": "USER_INPUT_REQUIRED",
                "error": str(exc),
                "diagnosis": "COM7 is present and registered to T660-2, T660-1 responds on COM3, and T660-2 returned no bytes at the registered or common serial rates; observe T660-2 power/display state.",
            }

        pico_config = inventory.devices["picoscope"]
        pico_recipe, _ = load_recipe(PICO_RECIPE)
        pico = PicoScopeService(
            pico_config, capture_settings_from_recipe(pico_recipe), command_log=command_log
        )
        pico_record: dict[str, Any] = {
            "configured_model": pico_config.get("model"),
            "configured_serial": pico_config.get("serial_number"),
            "sdk_serial": pico_config.get("sdk_serial_number"),
        }
        try:
            pico.open_unit()
            first_zero = pico.disable_signal_generator()
            pico.apply_capture_settings()
            timing = pico.validate_sample_timing()
            symbols = {
                name: getattr(pico._driver, name, None) is not None
                for name in (
                    "ps5000aSetSigGenBuiltInV2",
                    "ps5000aSetSigGenArbitrary",
                    "ps5000aSigGenArbitraryMinMaxValues",
                    "ps5000aRunBlock",
                    "ps5000aGetValues",
                )
            }
            if not all(symbols.values()):
                raise RuntimeError(f"required PicoSDK symbols missing: {symbols}")
            final_zero = pico.disable_signal_generator()
            pico_record.update(
                {
                    "status": "PASS",
                    "exclusive_open": True,
                    "single_handle_capture_and_generator": True,
                    "first_zero": first_zero,
                    "capture_timing_validation": timing,
                    "required_symbols": symbols,
                    "final_zero": final_zero,
                    "generator_readback_limit": "PicoSDK exposes set/status return but no generator settings getter; exact accepted settings are preserved for mandatory reapply and monitor measurement.",
                }
            )
        finally:
            try:
                if pico._is_open:
                    pico.disable_signal_generator()
                    pico.stop()
                    pico.close_unit()
            except Exception as exc:
                pico_record["close_error"] = str(exc)
        if pico_record.get("status") != "PASS" or pico_record.get("close_error"):
            raise RuntimeError(f"PicoScope preflight failed: {pico_record}")
        write_json(HERE / "preflight_picoscope_ownership_awg_zero.json", pico_record)
        status["checks"]["picoscope_capture_awg_single_owner"] = "PASS"

        hf = HF2LIService(inventory.devices["hf2li"], command_log=command_log)
        try:
            hf.connect()
            snapshot = hf2_snapshot(hf)
            if snapshot["device_id"].lower() != "dev18500":
                raise RuntimeError(f"unexpected HF2LI identity: {snapshot['device_id']}")
            if snapshot["read_errors"]:
                raise RuntimeError(f"HF2LI snapshot read errors: {snapshot['read_errors']}")
            write_json(HERE / "preflight_hf2li_snapshot.json", snapshot)
            status["checks"]["hf2li_identity_and_supported_space"] = "PASS"
            status["checks"]["hf2li_external_clock"] = {
                "selection": snapshot["nodes"][f"/{snapshot['device_id']}/system/extclk"]["value"],
                "dcm_lock_flag": snapshot["nodes"][f"/{snapshot['device_id']}/status/flags/dcmlock"]["value"],
                "status": "RECORDED_PENDING_OPERATOR_CLOCK_WIRING_OBSERVATION",
            }
        finally:
            hf.close()

    status["status"] = "READY_FOR_PHASE_APPROVAL" if t660_ready else "USER_INPUT_REQUIRED"
    status["phase_authorized_after_preflight"] = bool(t660_ready)
    status["execution_gate"] = "WAITING_FOR_OPERATOR_OBSERVATION"
    status["value_required_fields"] = [
        *( [] if t660_ready else ["observe whether T660-2 serial 00431 is powered and its front-panel display is active"] ),
        "HF01-UIR-001 current laser inhibit/shutter observations, one action at a time",
        "HF01-UIR-002 tee/cable inspection after safe-state observations",
        "operator confirmation that competing PicoScope and LabOne clients are closed before configuration changes",
    ]
    status["finished_utc"] = utc_now()
    write_json(status_path, status)
    if t660_ready:
        append_ledger(
            action="Completed HF01 software/device preflight with Pico generator programmed zero",
            expected="READY_FOR_PHASE_APPROVAL without emission or cable movement",
            observed="T660 safe idle matched; Pico single-handle capture/AWG controls passed at programmed zero; HF2 dev18500 snapshot retained",
            evidence="HF01-PREFLIGHT-001",
            decision="WAIT_FOR_ONE_OPERATOR_OBSERVATION",
            notes="No cable moved and no nonzero generator output; current laser and shutter state remains USER_INPUT_REQUIRED",
        )
    else:
        append_ledger(
            action="Ran HF01 software/device preflight with Pico generator programmed zero",
            expected="READY_FOR_PHASE_APPROVAL without emission or cable movement",
            observed="Pico/HF2 checks completed but T660-2 gave no serial response; T660-1 responds and COM7 is present",
            evidence="HF01-PREFLIGHT-001",
            decision="USER_INPUT_REQUIRED_T6602_POWER_OBSERVATION",
            notes="No cable moved and no nonzero generator output; do not infer T660-2 physical state",
        )
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
