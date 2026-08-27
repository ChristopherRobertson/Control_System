"""Verify repeatable reload of the three HF-01 selected configuration IDs."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import math
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT / "software") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "software"))

from control_app.config_loader import load_config_inventory  # noqa: E402
from control_app.devices.hf2li_service import HF2LIService  # noqa: E402
from control_app.workflows.timing_recipe_manager import TimingRecipeManager  # noqa: E402


HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
OUTPUT = RAW / "hf01_selected_configuration_reload_001.json"
SAFE_IDLE = REPO_ROOT / "instrument" / "recipes" / "safe_idle.yaml"
ACQUISITION_ID = "HF01-CONFIG-RELOAD-001"

CONFIGS = {
    "HF01-SWEEP-SELECTED-001": {"order": 4, "timeconstant_s": 0.001, "rate_sps": 899.4654605263158},
    "HF01-HRP-SELECTED-001": {"order": 4, "timeconstant_s": 0.001, "rate_sps": 899.4654605263158},
    "HF01-MBCO-SELECTED-001": {"order": 1, "timeconstant_s": 5.6e-6, "rate_sps": 230263.15789473685},
}


def stamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def node_spec() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = [("system/extclk", "int")]
    for input_index in (0, 1):
        rows.extend(
            [
                (f"sigins/{input_index}/ac", "int"),
                (f"sigins/{input_index}/imp50", "int"),
                (f"sigins/{input_index}/diff", "int"),
                (f"sigins/{input_index}/range", "double"),
            ]
        )
    for demod, adc in ((0, 0), (3, 1)):
        rows.extend(
            [
                (f"demods/{demod}/enable", "int"),
                (f"demods/{demod}/adcselect", "int"),
                (f"demods/{demod}/oscselect", "int"),
                (f"demods/{demod}/harmonic", "int"),
                (f"demods/{demod}/order", "int"),
                (f"demods/{demod}/timeconstant", "double"),
                (f"demods/{demod}/rate", "double"),
                (f"demods/{demod}/trigger", "int"),
            ]
        )
    return rows


def snapshot(server, device: str, spec: list[tuple[str, str]]) -> dict[str, float | int]:
    return {
        suffix: (
            int(server.getInt(f"/{device}/{suffix}"))
            if kind == "int"
            else float(server.getDouble(f"/{device}/{suffix}"))
        )
        for suffix, kind in spec
    }


def restore(server, device: str, values: dict[str, float | int], spec: list[tuple[str, str]]) -> None:
    for demod in (0, 3):
        server.setInt(f"/{device}/demods/{demod}/enable", 0)
    for suffix, kind in spec:
        if suffix.endswith("/enable"):
            continue
        if kind == "int":
            server.setInt(f"/{device}/{suffix}", int(values[suffix]))
        else:
            server.setDouble(f"/{device}/{suffix}", float(values[suffix]))
    for demod in (0, 3):
        suffix = f"demods/{demod}/enable"
        server.setInt(f"/{device}/{suffix}", int(values[suffix]))
    server.sync()


def apply_config(server, device: str, config: dict[str, float | int]) -> None:
    for demod, adc in ((0, 0), (3, 1)):
        base = f"/{device}/demods/{demod}"
        server.setInt(f"{base}/enable", 0)
        server.setInt(f"{base}/adcselect", adc)
        server.setInt(f"{base}/oscselect", 0)
        server.setInt(f"{base}/harmonic", 1)
        server.setInt(f"{base}/order", int(config["order"]))
        server.setDouble(f"{base}/timeconstant", float(config["timeconstant_s"]))
        server.setDouble(f"{base}/rate", float(config["rate_sps"]))
        server.setInt(f"{base}/trigger", 0)
    for input_index in (0, 1):
        base = f"/{device}/sigins/{input_index}"
        server.setInt(f"{base}/ac", 0)
        server.setInt(f"{base}/imp50", 0)
        server.setInt(f"{base}/diff", 0)
        server.setDouble(f"{base}/range", 1.0)
    server.setInt(f"/{device}/system/extclk", 1)
    for demod in (0, 3):
        server.setInt(f"/{device}/demods/{demod}/enable", 1)
    server.sync()


def compare(first: dict[str, float | int], second: dict[str, float | int], spec: list[tuple[str, str]]) -> dict[str, object]:
    rows = []
    passed = True
    for suffix, kind in spec:
        left = first[suffix]
        right = second[suffix]
        if kind == "int":
            match = int(left) == int(right)
            relative = None
        else:
            scale = max(abs(float(left)), abs(float(right)), 1e-300)
            relative = abs(float(left) - float(right)) / scale
            match = relative <= 1e-9
        passed = passed and match
        rows.append(
            {
                "node": suffix,
                "kind": kind,
                "first_readback": left,
                "second_readback": right,
                "relative_difference": relative,
                "pass": match,
            }
        )
    return {"pass": passed, "nodes": rows}


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise FileExistsError(f"{ACQUISITION_ID} already exists; do not overwrite it")
    inventory = load_config_inventory(write_files=False)
    log = (HERE / "command_log.txt").open("a", encoding="utf-8")
    hf = HF2LIService(inventory.devices["hf2li"], command_log=log)
    record: dict[str, object] = {
        "campaign_id": "system_recalibration_001",
        "phase_id": "HF-01",
        "acquisition_id": ACQUISITION_ID,
        "authorization_id": "HF01-AUTH-001",
        "amendment_id": "HF01-AUTH-AMEND-005",
        "scope": "HF2LI configuration reload only; no PicoScope AWG or T660 output",
        "started_utc": stamp(),
        "status": "STARTED",
        "configuration_results": {},
    }
    server = None
    device = ""
    original: dict[str, float | int] | None = None
    spec = node_spec()
    try:
        manager = TimingRecipeManager(inventory=inventory, command_log=log)
        before = manager.apply_recipe(
            SAFE_IDLE, output_path=RAW / "hf01_selected_configuration_reload_001_pre_safe_idle.json"
        )
        if before.get("matches_recipe") is not True:
            raise RuntimeError("T660 safe idle did not match before reload verification")
        record["t660_safe_idle_before"] = {"matches_recipe": True, "mismatches": []}
        hf.connect()
        server = hf._require_server()
        device = hf.device_id
        original = snapshot(server, device, spec)
        record["device_id"] = device
        record["original_readback"] = original
        for config_id, config in CONFIGS.items():
            apply_config(server, device, config)
            first = snapshot(server, device, spec)
            restore(server, device, original, spec)
            apply_config(server, device, config)
            second = snapshot(server, device, spec)
            comparison = compare(first, second, spec)
            record["configuration_results"][config_id] = {  # type: ignore[index]
                "requested": config,
                "first_readback": first,
                "second_readback": second,
                "comparison": comparison,
                "alias_note": (
                    "numeric alias of HF01-SWEEP-SELECTED-001"
                    if config_id == "HF01-HRP-SELECTED-001"
                    else None
                ),
            }
            if not comparison["pass"]:
                raise RuntimeError(f"reload equivalence failed for {config_id}")
            restore(server, device, original, spec)
        record["status"] = "PASS"
    except Exception as exc:
        record["status"] = "FAIL"
        record["error"] = str(exc)
    finally:
        try:
            if server is not None and original is not None:
                restore(server, device, original, spec)
                record["restored_readback"] = snapshot(server, device, spec)
                record["restore_matches_original"] = compare(
                    original, record["restored_readback"], spec  # type: ignore[arg-type]
                )["pass"]
        except Exception as exc:
            record["hf2li_restore_error"] = str(exc)
        hf.close()
        try:
            manager = TimingRecipeManager(inventory=inventory, command_log=log)
            after = manager.apply_recipe(
                SAFE_IDLE, output_path=RAW / "hf01_selected_configuration_reload_001_final_safe_idle.json"
            )
            record["t660_safe_idle_after"] = {
                "matches_recipe": after.get("matches_recipe"),
                "mismatches": after.get("mismatches"),
            }
        except Exception as exc:
            record["final_safe_idle_error"] = str(exc)
        record["finished_utc"] = stamp()
        OUTPUT.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        log.close()
    print(json.dumps(record, indent=2, sort_keys=True))
    clean = (
        record.get("status") == "PASS"
        and record.get("restore_matches_original") is True
        and (record.get("t660_safe_idle_after") or {}).get("matches_recipe") is True
        and not any(key.endswith("_error") for key in record)
    )
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
