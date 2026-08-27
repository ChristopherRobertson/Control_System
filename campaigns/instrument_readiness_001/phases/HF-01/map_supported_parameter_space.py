"""Read back the installed HF2LI parameter domains needed by HF-01.

This is a configuration-only operation.  The selected demodulator is disabled
while settings are probed, the PicoScope AWG is not opened or enabled, T660
outputs remain in the safe-idle recipe, and every changed HF2LI node is restored.
"""

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
SAFE_IDLE = REPO_ROOT / "instrument" / "recipes" / "safe_idle.yaml"
ACQUISITION_ID = "HF01-HF2-SUPPORTED-SPACE-001"
OUTPUT = RAW / "hf01_hf2_supported_parameter_space_001.json"

NOMINAL_RANGES_V = (0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 1.5)
TIME_CONSTANT_PROBES_S = (
    0.8e-6,
    1.0e-6,
    2.0e-6,
    4.0e-6,
    5.6e-6,
    8.0e-6,
    10.0e-6,
    20.0e-6,
    50.0e-6,
    100.0e-6,
    200.0e-6,
    500.0e-6,
    1.0e-3,
    2.0e-3,
    5.0e-3,
    10.0e-3,
    20.0e-3,
    50.0e-3,
    0.1,
    0.2,
    0.5,
    1.0,
    2.0,
    5.0,
    10.0,
    100.0,
    580.0,
)


def stamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def get_demod(server, base: str) -> dict[str, float | int]:
    return {
        "enable": int(server.getInt(f"{base}/enable")),
        "order": int(server.getInt(f"{base}/order")),
        "timeconstant_s": float(server.getDouble(f"{base}/timeconstant")),
        "rate_sps": float(server.getDouble(f"{base}/rate")),
        "trigger": int(server.getInt(f"{base}/trigger")),
    }


def get_sigin(server, base: str) -> dict[str, float | int]:
    return {
        "ac": int(server.getInt(f"{base}/ac")),
        "differential": int(server.getInt(f"{base}/diff")),
        "impedance_50ohm": int(server.getInt(f"{base}/imp50")),
        "range_v": float(server.getDouble(f"{base}/range")),
    }


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
        "purpose": "Installed parameter-domain readback for complete analytical candidate evaluation",
        "operation_scope": "HF2LI configuration only; no PicoScope AWG or T660 output",
        "started_utc": stamp(),
        "status": "STARTED",
    }
    server = None
    device = ""
    original_demod: dict[str, float | int] | None = None
    original_sigin: dict[str, float | int] | None = None
    try:
        manager = TimingRecipeManager(inventory=inventory, command_log=log)
        before = manager.apply_recipe(
            SAFE_IDLE, output_path=RAW / "hf01_hf2_supported_space_001_pre_safe_idle.json"
        )
        record["t660_safe_idle_before"] = {
            "matches_recipe": before.get("matches_recipe"),
            "mismatches": before.get("mismatches"),
        }
        if before.get("matches_recipe") is not True:
            raise RuntimeError("T660 safe idle did not match before the parameter readback")

        hf.connect()
        server = hf._require_server()
        device = hf.device_id
        demod = f"/{device}/demods/0"
        sigin = f"/{device}/sigins/0"
        original_demod = get_demod(server, demod)
        original_sigin = get_sigin(server, sigin)
        record["device_id"] = device
        record["original_demodulator_readback"] = original_demod
        record["original_signal_input_readback"] = original_sigin

        min_tc = float(server.getDouble(f"/{device}/system/properties/mintimeconstant"))
        max_tc = float(server.getDouble(f"/{device}/system/properties/maxtimeconstant"))
        record["timeconstant_domain"] = {
            "node_type": "writable_double",
            "minimum_readback_s": min_tc,
            "maximum_readback_s": max_tc,
            "coverage_method": (
                "continuous interval evaluated analytically; exact device-quantized readback "
                "is retained for each physically selected value"
            ),
        }

        server.setInt(f"{demod}/enable", 0)
        server.setInt(f"{demod}/trigger", 0)
        server.setInt(f"{demod}/order", 1)
        server.sync()

        tc_rows = []
        for requested in (min_tc, *TIME_CONSTANT_PROBES_S, max_tc):
            server.setDouble(f"{demod}/timeconstant", requested)
            server.sync()
            tc_rows.append(
                {
                    "requested_s": requested,
                    "readback_s": float(server.getDouble(f"{demod}/timeconstant")),
                }
            )
        record["timeconstant_readback_probes"] = tc_rows

        base_rate = 460526.3157894737
        rate_rows = []
        for exponent in range(0, 22):
            requested = base_rate / (2**exponent)
            server.setDouble(f"{demod}/rate", requested)
            server.sync()
            rate_rows.append(
                {
                    "decimation_exponent": exponent,
                    "requested_sps": requested,
                    "readback_sps": float(server.getDouble(f"{demod}/rate")),
                    "dual_channel_eligible": exponent >= 1,
                }
            )
        record["installed_rate_ladder"] = rate_rows
        record["dual_channel_rate_ladder_sps"] = [
            row["readback_sps"] for row in rate_rows if row["dual_channel_eligible"]
        ]

        order_rows = []
        for requested in range(1, 9):
            server.setInt(f"{demod}/order", requested)
            server.sync()
            order_rows.append(
                {"requested": requested, "readback": int(server.getInt(f"{demod}/order"))}
            )
        record["filter_orders"] = order_rows

        range_rows = []
        for requested in NOMINAL_RANGES_V:
            server.setDouble(f"{sigin}/range", requested)
            server.sync()
            range_rows.append(
                {
                    "requested_v": requested,
                    "readback_v": float(server.getDouble(f"{sigin}/range")),
                }
            )
        record["input_ranges"] = range_rows

        mode_rows = []
        for ac in (0, 1):
            for imp50 in (0, 1):
                for diff in (0, 1):
                    server.setInt(f"{sigin}/ac", ac)
                    server.setInt(f"{sigin}/imp50", imp50)
                    server.setInt(f"{sigin}/diff", diff)
                    server.sync()
                    mode_rows.append(get_sigin(server, sigin))
        record["input_modes"] = mode_rows
        record["readout_modes"] = [
            {
                "name": "continuous_timestamped_xy",
                "trigger_node_value": 0,
                "applicable": True,
            },
            {
                "name": "edge_triggered_transfer",
                "trigger_node_values": [1, 2, 4, 8],
                "applicable": False,
                "reason": "would omit continuous pre-event and recovery history required by all three retained cases",
            },
            {
                "name": "level_gated_transfer",
                "trigger_node_values": [16, 32, 64, 128],
                "applicable": False,
                "reason": "would make the retained waveform dependent on marker level duration",
            },
        ]
        record["model_validation_source"] = "HF01-ANALYSIS-DUAL-DEMOD-MODEL-V3-001"
        record["status"] = "PASS"
    except Exception as exc:
        record["status"] = "FAIL"
        record["error"] = str(exc)
    finally:
        try:
            if server is not None and original_sigin is not None and original_demod is not None:
                demod = f"/{device}/demods/0"
                sigin = f"/{device}/sigins/0"
                server.setInt(f"{demod}/enable", 0)
                server.setInt(f"{sigin}/ac", int(original_sigin["ac"]))
                server.setInt(f"{sigin}/diff", int(original_sigin["differential"]))
                server.setInt(f"{sigin}/imp50", int(original_sigin["impedance_50ohm"]))
                server.setDouble(f"{sigin}/range", float(original_sigin["range_v"]))
                server.setInt(f"{demod}/order", int(original_demod["order"]))
                server.setDouble(f"{demod}/rate", float(original_demod["rate_sps"]))
                server.setDouble(
                    f"{demod}/timeconstant", float(original_demod["timeconstant_s"])
                )
                server.setInt(f"{demod}/trigger", int(original_demod["trigger"]))
                server.setInt(f"{demod}/enable", int(original_demod["enable"]))
                server.sync()
                record["restored_signal_input_readback"] = get_sigin(server, sigin)
                record["restored_demodulator_readback"] = get_demod(server, demod)
        except Exception as exc:
            record["hf2li_restore_error"] = str(exc)
        hf.close()
        try:
            manager = TimingRecipeManager(inventory=inventory, command_log=log)
            after = manager.apply_recipe(
                SAFE_IDLE, output_path=RAW / "hf01_hf2_supported_space_001_final_safe_idle.json"
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
        and not any(key.endswith("_error") for key in record)
        and (record.get("t660_safe_idle_after") or {}).get("matches_recipe") is True
    )
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
