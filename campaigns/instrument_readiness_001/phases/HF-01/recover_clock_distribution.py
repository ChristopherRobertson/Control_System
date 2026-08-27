"""Restore and verify the installed T660-2-led 10 MHz clock distribution."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import time


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.hf2li_service import HF2LIService  # noqa: E402
from control_app.devices.t660_service import T660Service  # noqa: E402
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402


HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
SAFE_IDLE = REPO_ROOT / "instrument" / "recipes" / "safe_idle.yaml"
ACQUISITION_ID = "HF01-CLOCK-DISTRIBUTION-RECOVERY-001"


def stamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def read_t660_clock(unit: T660Service) -> dict[str, str]:
    return {
        "mode": unit.command("CLOCK:MODE?"),
        "external_enabled": unit.command("CLOCK:EXTERNAL?"),
        "frequency_hz": unit.command("CLOCK:FREQUENCY?"),
        "status": unit.command("CLOCK:STATUS?"),
    }


def read_hf_clock(hf: HF2LIService) -> dict[str, int | str]:
    server = hf._require_server()
    device = hf.device_id
    return {
        "system_extclk": int(server.getInt(f"/{device}/system/extclk")),
        "status_plllock_flag": int(
            server.getInt(f"/{device}/status/flags/plllock")
        ),
        "status_dcmlock_flag": int(
            server.getInt(f"/{device}/status/flags/dcmlock")
        ),
        "status_flags_binary": int(
            server.getInt(f"/{device}/status/flags/binary")
        ),
        "flag_semantics": "zero_is_locked_per_HF2_node_documentation",
    }


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    status_path = RAW / "hf01_clock_distribution_recovery_001.json"
    if status_path.exists():
        raise FileExistsError(
            f"{ACQUISITION_ID} already executed; use a new stable acquisition ID"
        )

    inventory = load_config_inventory(write_files=False)
    log = (HERE / "command_log.txt").open("a", encoding="utf-8")
    t660_2 = T660Service(
        "t660_2", inventory.t660_devices["t660_2"], command_log=log
    )
    t660_1 = T660Service(
        "t660_1", inventory.t660_devices["t660_1"], command_log=log
    )
    hf = HF2LIService(inventory.devices["hf2li"], command_log=log)
    record: dict[str, object] = {
        "campaign_id": "system_recalibration_001",
        "phase_id": "HF-01",
        "acquisition_id": ACQUISITION_ID,
        "bounded_repeat_authorization_id": "HF01-AUTH-AMEND-004",
        "started_utc": stamp(),
        "status": "STARTED",
        "installed_topology": (
            "T660-2 CLOCK OUT -> CLOCK-SPLITTER-01 -> T660-1 CLOCK IN and "
            "HF2LI CLOCK IN"
        ),
        "physical_change": "NONE",
    }
    try:
        manager = TimingRecipeManager(inventory=inventory, command_log=log)
        safe_before = manager.apply_recipe(
            SAFE_IDLE,
            output_path=RAW / "hf01_clock_distribution_recovery_001_pre_safe_idle.json",
        )
        record["t660_safe_idle_before"] = {
            "matches_recipe": safe_before.get("matches_recipe"),
            "mismatches": safe_before.get("mismatches"),
        }
        if safe_before.get("matches_recipe") is not True:
            raise RuntimeError("T660 channel safe idle did not match before recovery")

        t660_2.connect()
        t660_1.connect()
        hf.connect()
        record["before"] = {
            "t660_2": read_t660_clock(t660_2),
            "t660_1": read_t660_clock(t660_1),
            "hf2li": read_hf_clock(hf),
        }

        t660_2.command("CLOCK:MODE OUTPUT")
        t660_1.command("CLOCK:MODE INPUT")
        server = hf._require_server()
        server.setInt(f"/{hf.device_id}/system/extclk", 1)
        server.sync()

        samples = []
        for _ in range(30):
            samples.append(
                {
                    "utc": stamp(),
                    "t660_1": read_t660_clock(t660_1),
                    "hf2li": read_hf_clock(hf),
                }
            )
            follower_locked = samples[-1]["t660_1"]["status"] == "LOCKED"
            hf_state = samples[-1]["hf2li"]
            hf_locked = (
                hf_state["system_extclk"] == 1
                and hf_state["status_plllock_flag"] == 0
                and hf_state["status_dcmlock_flag"] == 0
            )
            if follower_locked and hf_locked:
                break
            time.sleep(0.2)
        record["lock_samples"] = samples
        record["after"] = {
            "t660_2": read_t660_clock(t660_2),
            "t660_1": read_t660_clock(t660_1),
            "hf2li": read_hf_clock(hf),
        }

        after = record["after"]
        passed = (
            after["t660_2"]["mode"] == "OUT"
            and after["t660_1"]["mode"] == "INP"
            and after["t660_1"]["status"] == "LOCKED"
            and after["t660_1"]["frequency_hz"] == "10000000"
            and after["hf2li"]["system_extclk"] == 1
            and after["hf2li"]["status_plllock_flag"] == 0
            and after["hf2li"]["status_dcmlock_flag"] == 0
        )
        record["status"] = (
            "PASS_CLOCK_DISTRIBUTION_RESTORED_AND_LOCKED"
            if passed
            else "FAIL_CLOCK_DISTRIBUTION_NOT_LOCKED"
        )
    except Exception as exc:
        record["status"] = "FAIL"
        record["error"] = str(exc)
    finally:
        hf.close()
        t660_1.close()
        t660_2.close()
        try:
            manager = TimingRecipeManager(inventory=inventory, command_log=log)
            safe_after = manager.apply_recipe(
                SAFE_IDLE,
                output_path=RAW / "hf01_clock_distribution_recovery_001_final_safe_idle.json",
            )
            record["t660_safe_idle_after"] = {
                "matches_recipe": safe_after.get("matches_recipe"),
                "mismatches": safe_after.get("mismatches"),
            }
        except Exception as exc:
            record["final_safe_idle_error"] = str(exc)
        record["finished_utc"] = stamp()
        status_path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        log.close()

    print(json.dumps(record, indent=2, sort_keys=True))
    clean = (
        record.get("status") == "PASS_CLOCK_DISTRIBUTION_RESTORED_AND_LOCKED"
        and not any(key.endswith("_error") for key in record)
        and (record.get("t660_safe_idle_after") or {}).get("matches_recipe") is True
    )
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
