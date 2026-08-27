"""Verify electronic safe idle at the HF-01 prospective-amendment stop."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.hf2li_service import HF2LIService  # noqa: E402
from control_app.devices.picoscope_service import PicoScopeService  # noqa: E402
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402


HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
SAFE_IDLE = REPO_ROOT / "instrument" / "recipes" / "safe_idle.yaml"
STATUS = RAW / "hf01_amendment_stop_safe_state.json"


def stamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main() -> int:
    if STATUS.exists():
        raise FileExistsError("HF01-AMENDMENT-STOP-SAFE-STATE-001 already executed")
    inventory = load_config_inventory(write_files=False)
    log = (HERE / "command_log.txt").open("a", encoding="utf-8")
    pico_settings = {
        "resolution": "8BIT",
        "channels": {
            "A": {
                "enabled": True,
                "coupling": "DC",
                "range": "100MV",
                "analog_offset_v": 0.0,
            },
            "B": {
                "enabled": False,
                "coupling": "DC",
                "range": "100MV",
                "analog_offset_v": 0.0,
            },
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
    pico = PicoScopeService(
        inventory.devices["picoscope"], pico_settings, command_log=log
    )
    hf = HF2LIService(inventory.devices["hf2li"], command_log=log)
    record: dict[str, object] = {
        "campaign_id": "system_recalibration_001",
        "phase_id": "HF-01",
        "acquisition_id": "HF01-AMENDMENT-STOP-SAFE-STATE-001",
        "authorization_id": "HF01-AUTH-001",
        "started_utc": stamp(),
        "status": "STARTED",
        "physical_scope": (
            "electronic readback only; temporary HF-01 wiring remains in place and "
            "physical restoration is not inferred"
        ),
    }
    try:
        manager = TimingRecipeManager(inventory=inventory, command_log=log)
        safe = manager.apply_recipe(
            SAFE_IDLE,
            output_path=RAW / "hf01_amendment_stop_t660_safe_idle.json",
        )
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
        record["hf2li"] = {
            "device_id": device,
            "system_extclk": int(server.getInt(f"/{device}/system/extclk")),
            "pll_lock_flag": int(server.getInt(f"/{device}/status/flags/plllock")),
            "dcm_lock_flag": int(server.getInt(f"/{device}/status/flags/dcmlock")),
            "adcclip_input1": int(server.getInt(f"/{device}/status/flags/adcclip/0")),
            "adcclip_input2": int(server.getInt(f"/{device}/status/flags/adcclip/1")),
            "demodsampleloss": int(
                server.getInt(f"/{device}/status/flags/demodsampleloss")
            ),
            "signal_output_1_on": int(server.getInt(f"/{device}/sigouts/0/on")),
            "signal_output_2_on": int(server.getInt(f"/{device}/sigouts/1/on")),
            "lock_flag_semantics": "zero_is_locked_per_HF2_node_documentation",
        }
        hf.close()

        hf_state = record["hf2li"]
        clean = (
            record["t660_safe_idle"]["matches_recipe"] is True  # type: ignore[index]
            and record["picoscope_awg"]["pk_to_pk_v"] == 0.0  # type: ignore[index]
            and hf_state["system_extclk"] == 1  # type: ignore[index]
            and hf_state["pll_lock_flag"] == 0  # type: ignore[index]
            and hf_state["dcm_lock_flag"] == 0  # type: ignore[index]
            and hf_state["adcclip_input1"] == 0  # type: ignore[index]
            and hf_state["adcclip_input2"] == 0  # type: ignore[index]
            and hf_state["demodsampleloss"] == 0  # type: ignore[index]
            and hf_state["signal_output_1_on"] == 0  # type: ignore[index]
            and hf_state["signal_output_2_on"] == 0  # type: ignore[index]
        )
        record["status"] = "PASS_ELECTRONIC_SAFE_IDLE" if clean else "FAIL_SAFE_IDLE"
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
        STATUS.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        log.close()
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record["status"] == "PASS_ELECTRONIC_SAFE_IDLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
