"""Verify HF-01 final electronic safe idle and restored HF2LI settings."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import math
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.hf2li_service import HF2LIService  # noqa: E402
from control_app.devices.picoscope_service import PicoScopeService  # noqa: E402
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402


HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
SAFE_IDLE = REPO_ROOT / "recipes" / "safe_idle.yaml"
RELOAD = RAW / "hf01_selected_configuration_reload_001.json"
STATUS = RAW / "hf01_final_restoration_state_r1_001.json"
T660_READBACK = RAW / "hf01_final_restoration_t660_safe_idle_r1_001.json"
ACQUISITION_ID = "HF01-FINAL-RESTORATION-STATE-R1-001"


def stamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def compare_value(expected: object, actual: object) -> tuple[bool, float | None]:
    if isinstance(expected, int):
        return actual == expected, None
    expected_float = float(expected)
    actual_float = float(actual)
    relative = abs(actual_float - expected_float) / max(abs(expected_float), 1e-15)
    return math.isclose(actual_float, expected_float, rel_tol=1e-12, abs_tol=1e-15), relative


def main() -> int:
    if STATUS.exists() or T660_READBACK.exists():
        raise FileExistsError(f"{ACQUISITION_ID} already executed")

    reload_record = json.loads(RELOAD.read_text(encoding="utf-8"))
    expected_hf2 = reload_record["original_readback"]
    inventory = load_config_inventory(write_files=False)
    log = (HERE / "command_log.txt").open("a", encoding="utf-8")
    pico_settings = {
        "resolution": "8BIT",
        "channels": {
            "A": {"enabled": True, "coupling": "DC", "range": "100MV", "analog_offset_v": 0.0},
            "B": {"enabled": False, "coupling": "DC", "range": "100MV", "analog_offset_v": 0.0},
        },
        "external_trigger": {
            "source": "A",
            "threshold_adc": 5000,
            "direction": 2,
            "delay_samples": 0,
            "auto_trigger_ms": 0,
        },
        "total_samples": 5000,
        "pre_trigger_samples": 1000,
        "timebase": 1,
        "timeout_s": 5.0,
    }
    pico = PicoScopeService(inventory.devices["picoscope"], pico_settings, command_log=log)
    hf = HF2LIService(inventory.devices["hf2li"], command_log=log)
    record: dict[str, object] = {
        "campaign_id": "system_recalibration_001",
        "phase_id": "HF-01",
        "acquisition_id": ACQUISITION_ID,
        "authorization_id": "HF01-AUTH-001",
        "supersedes_acquisition_id": "HF01-FINAL-RESTORATION-STATE-001",
        "started_utc": stamp(),
        "status": "STARTED",
        "physical_restoration_confirmation_id": "HF01-OPCONF-014",
        "source_configuration_acquisition_id": "HF01-CONFIG-RELOAD-001",
        "scope": "final electronic readback after operator-confirmed default wiring restoration",
    }

    try:
        manager = TimingRecipeManager(inventory=inventory, command_log=log)
        safe = manager.apply_recipe(SAFE_IDLE, output_path=T660_READBACK)
        record["t660_safe_idle"] = {
            "matches_recipe": safe.get("matches_recipe"),
            "mismatches": safe.get("mismatches"),
        }

        pico.open_unit()
        record["picoscope_awg"] = pico.disable_signal_generator()
        pico.close_unit()

        hf.connect()
        server = hf._require_server()
        device = hf.device_id
        current_hf2: dict[str, object] = {}
        comparisons: list[dict[str, object]] = []
        for node, expected in expected_hf2.items():
            path = f"/{device}/{node}"
            actual: object
            if isinstance(expected, int):
                actual = int(server.getInt(path))
            else:
                actual = float(server.getDouble(path))
            current_hf2[node] = actual
            matches, relative_difference = compare_value(expected, actual)
            comparisons.append(
                {
                    "node": node,
                    "expected": expected,
                    "readback": actual,
                    "matches": matches,
                    "relative_difference": relative_difference,
                }
            )

        flags = {
            "pll_lock_flag": int(server.getInt(f"/{device}/status/flags/plllock")),
            "dcm_lock_flag": int(server.getInt(f"/{device}/status/flags/dcmlock")),
            "adcclip_input1": int(server.getInt(f"/{device}/status/flags/adcclip/0")),
            "adcclip_input2": int(server.getInt(f"/{device}/status/flags/adcclip/1")),
            "demodsampleloss": int(server.getInt(f"/{device}/status/flags/demodsampleloss")),
            "signal_output_1_on": int(server.getInt(f"/{device}/sigouts/0/on")),
            "signal_output_2_on": int(server.getInt(f"/{device}/sigouts/1/on")),
        }
        hf.close()

        hf_matches = all(item["matches"] is True for item in comparisons)
        clean_flags = all(value == 0 for value in flags.values())
        record["hf2li"] = {
            "device_id": device,
            "expected_configuration": expected_hf2,
            "current_readback": current_hf2,
            "comparisons": comparisons,
            "matches_prechange_configuration": hf_matches,
            "status_flags": flags,
            "status_flags_clean": clean_flags,
            "lock_flag_semantics": "zero_is_locked_per_HF2_node_documentation",
        }
        clean = (
            record["t660_safe_idle"]["matches_recipe"] is True  # type: ignore[index]
            and record["picoscope_awg"]["pk_to_pk_v"] == 0.0  # type: ignore[index]
            and hf_matches
            and clean_flags
        )
        record["status"] = "PASS_FINAL_RESTORATION" if clean else "FAIL_FINAL_RESTORATION"
    except Exception as exc:
        record["status"] = "FAIL"
        record["error"] = str(exc)
        try:
            pico.close_unit()
        except Exception:
            pass
        hf.close()
    finally:
        record["finished_utc"] = stamp()
        STATUS.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        log.close()

    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record["status"] == "PASS_FINAL_RESTORATION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
