"""Bounded HF2LI master-clock lock diagnostic for HF-01."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import time


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.hf2li_service import HF2LIService  # noqa: E402
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402


HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
SAFE_IDLE = REPO_ROOT / "recipes" / "safe_idle.yaml"
ACQUISITION_ID = "HF01-HF2-MASTER-CLOCK-DIAG-001"


def stamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sample_clock(server, device: str) -> dict[str, float | int | str]:
    return {
        "utc": stamp(),
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
        "oscillator0_frequency_hz": float(
            server.getDouble(f"/{device}/oscs/0/freq")
        ),
        "clockbase_hz": int(server.getInt(f"/{device}/clockbase")),
        "flag_semantics": "zero_is_locked_per_HF2_node_documentation",
    }


def collect(server, device: str, count: int, interval_s: float) -> list[dict]:
    values = []
    for _ in range(count):
        values.append(sample_clock(server, device))
        time.sleep(interval_s)
    return values


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    status_path = RAW / "hf01_hf2_master_clock_diagnostic_001.json"
    if status_path.exists():
        raise FileExistsError(
            f"{ACQUISITION_ID} already executed; use a new stable acquisition ID"
        )

    inventory = load_config_inventory(write_files=False)
    log = (HERE / "command_log.txt").open("a", encoding="utf-8")
    hf = HF2LIService(inventory.devices["hf2li"], command_log=log)
    record: dict[str, object] = {
        "campaign_id": "system_recalibration_001",
        "phase_id": "HF-01",
        "acquisition_id": ACQUISITION_ID,
        "bounded_repeat_authorization_id": "HF01-AUTH-AMEND-004",
        "started_utc": stamp(),
        "status": "STARTED",
        "purpose": (
            "Distinguish an unlocked installed external master-clock path from an "
            "HF2LI internal-clock or DIO-reference-PLL fault without analog output."
        ),
        "manufacturer_flag_semantics": {
            "status_flags_plllock": {"0": "locked", "1": "not locked"},
            "status_flags_dcmlock": {"0": "locked", "1": "not locked"},
        },
    }
    original_extclk: int | None = None
    server = None
    device = ""
    try:
        manager = TimingRecipeManager(inventory=inventory, command_log=log)
        safe_before = manager.apply_recipe(
            SAFE_IDLE,
            output_path=RAW / "hf01_hf2_master_clock_diagnostic_001_pre_safe_idle.json",
        )
        record["t660_safe_idle_before"] = {
            "matches_recipe": safe_before.get("matches_recipe"),
            "mismatches": safe_before.get("mismatches"),
        }
        if safe_before.get("matches_recipe") is not True:
            raise RuntimeError("T660 safe idle did not match before clock diagnostic")

        hf.connect()
        server = hf._require_server()
        device = hf.device_id
        original_extclk = int(server.getInt(f"/{device}/system/extclk"))
        record["original_external_clock_selection"] = original_extclk
        record["external_selected_before"] = collect(server, device, 8, 0.1)

        server.setInt(f"/{device}/system/extclk", 0)
        server.sync()
        time.sleep(0.5)
        record["internal_clock_control"] = collect(server, device, 12, 0.1)

        server.setInt(f"/{device}/system/extclk", 1)
        server.sync()
        time.sleep(0.5)
        record["external_clock_recheck"] = collect(server, device, 20, 0.1)

        internal = record["internal_clock_control"]
        external = record["external_clock_recheck"]
        internal_locked = all(
            row["status_plllock_flag"] == 0 and row["status_dcmlock_flag"] == 0
            for row in internal
        )
        external_locked = all(
            row["status_plllock_flag"] == 0 and row["status_dcmlock_flag"] == 0
            for row in external[-5:]
        )
        record["assessment"] = {
            "internal_clock_control_locked": internal_locked,
            "installed_external_clock_locked": external_locked,
        }
        if internal_locked and not external_locked:
            record["status"] = "DIAGNOSED_EXTERNAL_MASTER_CLOCK_UNLOCKED"
        elif internal_locked and external_locked:
            record["status"] = "PASS_EXTERNAL_MASTER_CLOCK_LOCKED"
        else:
            record["status"] = "INCONCLUSIVE_CLOCK_LOCK_DIAGNOSTIC"
    except Exception as exc:
        record["status"] = "FAIL"
        record["error"] = str(exc)
    finally:
        try:
            if server is not None and original_extclk is not None:
                server.setInt(f"/{device}/system/extclk", original_extclk)
                server.sync()
                time.sleep(0.5)
                record["restored_clock_state"] = sample_clock(server, device)
        except Exception as exc:
            record["hf2li_cleanup_error"] = str(exc)
        hf.close()
        try:
            manager = TimingRecipeManager(inventory=inventory, command_log=log)
            safe_after = manager.apply_recipe(
                SAFE_IDLE,
                output_path=RAW / "hf01_hf2_master_clock_diagnostic_001_final_safe_idle.json",
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
        record.get("status")
        in {
            "DIAGNOSED_EXTERNAL_MASTER_CLOCK_UNLOCKED",
            "PASS_EXTERNAL_MASTER_CLOCK_LOCKED",
        }
        and not any(key.endswith("_error") for key in record)
        and (record.get("t660_safe_idle_after") or {}).get("matches_recipe") is True
    )
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
