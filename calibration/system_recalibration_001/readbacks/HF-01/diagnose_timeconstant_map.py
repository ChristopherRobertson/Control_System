"""Map a bounded set of zero-output HF2LI writes around the 100 ms target."""

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
ACQUISITION_ID = "HF01-HF2-TC-MAP-DIAG-001"
REQUESTS_S = (0.1, 0.11, 0.12, 0.13, 0.14, 0.15, 0.2)


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
    status_path = RAW / "hf01_hf2_timeconstant_map_diagnostic_001.json"
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
        "purpose": "Identify the nearest installed-node readback to the frozen 100 ms slow-anchor target.",
        "electrical_scope": "HF2LI configuration only; demodulator disabled; no AWG or T660 output",
        "requested_values_s": list(REQUESTS_S),
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
            output_path=RAW / "hf01_hf2_timeconstant_map_diagnostic_001_pre_safe_idle.json",
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
        server.setDouble(f"{demod}/rate", 100.0)
        server.sync()

        mapped = []
        for requested in REQUESTS_S:
            server.setDouble(f"{demod}/timeconstant", requested)
            server.sync()
            mapped.append(
                {
                    "requested_timeconstant_s": requested,
                    **readback(server, demod),
                }
            )
        record["mapped_readbacks"] = mapped
        nearest = min(
            mapped,
            key=lambda row: abs(float(row["timeconstant_s"]) - 0.1),
        )
        record["nearest_to_100ms"] = nearest
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
                output_path=RAW / "hf01_hf2_timeconstant_map_diagnostic_001_final_safe_idle.json",
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
