"""Bounded zero-output HF2LI time-constant write-order diagnostic for HF-01."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.hf2li_service import HF2LIService  # noqa: E402
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402


HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
SAFE_IDLE = REPO_ROOT / "recipes" / "safe_idle.yaml"
ACQUISITION_ID = "HF01-HF2-TC-WRITE-DIAG-001"


def stamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def readback(server, demod: str) -> dict[str, float | int]:
    return {
        "enable": int(server.getInt(f"{demod}/enable")),
        "order": int(server.getInt(f"{demod}/order")),
        "timeconstant_s": float(server.getDouble(f"{demod}/timeconstant")),
        "rate_sps": float(server.getDouble(f"{demod}/rate")),
        "trigger": int(server.getInt(f"{demod}/trigger")),
    }


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    status_path = RAW / "hf01_hf2_timeconstant_write_diagnostic_001.json"
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
        "authorization_id": "HF01-AUTH-001",
        "bounded_repeat_authorization_id": "HF01-AUTH-AMEND-004",
        "purpose": (
            "Determine whether setting the output rate after the time constant "
            "caused the slow anchor's 100 ms request to read back as 71.153 ms."
        ),
        "electrical_scope": "HF2LI configuration only; demodulator disabled; no AWG or T660 output",
        "started_utc": stamp(),
        "status": "STARTED",
    }
    server = None
    device = ""
    original: dict[str, float | int] | None = None
    try:
        manager = TimingRecipeManager(inventory=inventory, command_log=log)
        safe_before = manager.apply_recipe(
            SAFE_IDLE,
            output_path=RAW / "hf01_hf2_timeconstant_write_diagnostic_001_pre_safe_idle.json",
        )
        record["t660_safe_idle_before"] = {
            "matches_recipe": safe_before.get("matches_recipe"),
            "mismatches": safe_before.get("mismatches"),
        }
        if safe_before.get("matches_recipe") is not True:
            raise RuntimeError("T660 safe idle did not match before diagnostic")

        hf.connect()
        server = hf._require_server()
        device = hf.device_id
        demod = f"/{device}/demods/0"
        original = readback(server, demod)
        record["original_readback"] = original

        server.setInt(f"{demod}/enable", 0)
        server.setInt(f"{demod}/order", 8)
        server.setDouble(f"{demod}/timeconstant", 0.1)
        server.setDouble(f"{demod}/rate", 100.0)
        server.sync()
        record["timeconstant_then_rate"] = readback(server, demod)

        server.setInt(f"{demod}/order", 8)
        server.setDouble(f"{demod}/rate", 100.0)
        server.setDouble(f"{demod}/timeconstant", 0.1)
        server.sync()
        record["rate_then_timeconstant"] = readback(server, demod)

        first = float(record["timeconstant_then_rate"]["timeconstant_s"])  # type: ignore[index]
        second = float(record["rate_then_timeconstant"]["timeconstant_s"])  # type: ignore[index]
        record["assessment"] = {
            "write_order_changes_timeconstant": abs(first - second) > 1e-12,
            "slow_anchor_repeat_required": abs(second - 0.1) / 0.1 > 0.02,
            "preferred_write_order": "rate_then_timeconstant",
        }
        record["status"] = "PASS_DIAGNOSTIC"
    except Exception as exc:
        record["status"] = "FAIL"
        record["error"] = str(exc)
    finally:
        try:
            if server is not None and original is not None:
                demod = f"/{device}/demods/0"
                server.setInt(f"{demod}/enable", 0)
                server.setInt(f"{demod}/order", int(original["order"]))
                server.setDouble(f"{demod}/rate", float(original["rate_sps"]))
                server.setDouble(
                    f"{demod}/timeconstant", float(original["timeconstant_s"])
                )
                server.setInt(f"{demod}/trigger", int(original["trigger"]))
                server.setInt(f"{demod}/enable", int(original["enable"]))
                server.sync()
                record["restored_readback"] = readback(server, demod)
        except Exception as exc:
            record["hf2li_cleanup_error"] = str(exc)
        hf.close()
        try:
            manager = TimingRecipeManager(inventory=inventory, command_log=log)
            safe_after = manager.apply_recipe(
                SAFE_IDLE,
                output_path=RAW / "hf01_hf2_timeconstant_write_diagnostic_001_final_safe_idle.json",
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
        record.get("status") == "PASS_DIAGNOSTIC"
        and not any(key.endswith("_error") for key in record)
        and (record.get("t660_safe_idle_after") or {}).get("matches_recipe") is True
    )
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
