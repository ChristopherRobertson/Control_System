"""Bounded non-emitting matrix diagnostic for HF2 external-reference routing."""

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


def stamp():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main():
    path = RAW / "hf01_pll_reference_diagnostic_011.json"
    if path.exists():
        raise FileExistsError(path)
    inventory = load_config_inventory(write_files=False)
    log = (HERE / "command_log.txt").open("a", encoding="utf-8")
    hf = HF2LIService(inventory.devices["hf2li"], command_log=log)
    t660 = T660Service("t660_2", inventory.t660_devices["t660_2"], command_log=log)
    record = {"started_utc": stamp(), "cases": [], "status": "STARTED"}
    original = {}
    try:
        hf.connect()
        server = hf._require_server()
        dev = hf.device_id
        record["device"] = dev
        for pll in (0, 1):
            original[f"osc{pll}"] = float(server.getDouble(f"/{dev}/oscs/{pll}/freq"))
            for node, kind in (
                ("enable", "int"), ("adcselect", "int"),
                ("freqcenter", "double"), ("harmonic", "int"),
                ("order", "int"), ("adcthreshold", "int"),
                ("demodselect", "int"), ("oscselect", "int"),
            ):
                getter = server.getInt if kind == "int" else server.getDouble
                original[f"pll{pll}/{node}"] = getter(f"/{dev}/plls/{pll}/{node}")
        record["master_clock_before"] = {
            "system_extclk": int(server.getInt(f"/{dev}/system/extclk")),
            "status_plllock_flag": int(server.getInt(f"/{dev}/status/flags/plllock")),
            "status_dcmlock_flag": int(server.getInt(f"/{dev}/status/flags/dcmlock")),
            "flag_semantics": "zero_is_locked_per_HF2_node_documentation",
        }
        expected_master = {
            "system_extclk": 1,
            "status_plllock_flag": 0,
            "status_dcmlock_flag": 0,
            "flag_semantics": "zero_is_locked_per_HF2_node_documentation",
        }
        if record["master_clock_before"] != expected_master:
            raise RuntimeError(f"HF2LI master clock is not locked: {record['master_clock_before']}")

        t660.connect()
        t660.command("STOP", expect_response=False)
        t660.set_trigger_source("OFF")
        for channel in "ABCD":
            t660.disable_channel(channel)
        for channel in "AB":
            t660.set_channel_delay_width(channel, "0ns", "400ns")
            t660.command(f"CHAN:POS {channel}", expect_response=False)
            t660.command(f"CHAN:50OHM {channel}", expect_response=False)
            t660.enable_channel(channel)
        server.setInt(f"/{dev}/dios/0/drive", 0)

        # PLL0 and PLL1 are tested independently. Their retained center
        # frequencies remove capture-range ambiguity. Threshold 0 reproduces
        # the saved session; 2500 mV tests the midpoint of the measured TTL
        # envelope without changing the physical path.
        for pll, threshold in ((0, 0), (0, 2500), (1, 0), (1, 2500)):
            center = float(server.getDouble(f"/{dev}/plls/{pll}/freqcenter"))
            case = {
                "pll_index": pll,
                "threshold_requested": threshold,
                "target_frequency_hz": center,
                "samples": [],
            }
            t660.command("STOP", expect_response=False)
            t660.set_trigger_source("OFF")
            t660.set_clock_mode(frequency=f"{center:.9f}Hz", shots=0)
            t660.set_trigger_source("SYN")
            t660.command("START", expect_response=False)
            server.setInt(f"/{dev}/plls/{pll}/enable", 0)
            server.setInt(f"/{dev}/plls/{pll}/adcselect", 4)
            server.setInt(f"/{dev}/plls/{pll}/harmonic", 1)
            server.setInt(f"/{dev}/plls/{pll}/order", 4)
            server.setInt(f"/{dev}/plls/{pll}/adcthreshold", threshold)
            server.setDouble(f"/{dev}/oscs/{pll}/freq", center)
            server.setInt(f"/{dev}/plls/{pll}/enable", 1)
            # Do not call sync() here: HF2 LabOne waits for an external-
            # reference lock and times out when the case under test rejects.
            time.sleep(0.15)
            case["configured_readback"] = {
                node: int(server.getInt(f"/{dev}/plls/{pll}/{node}"))
                for node in (
                    "enable", "adcselect", "demodselect", "oscselect",
                    "harmonic", "order", "adcthreshold",
                )
            }
            for _ in range(25):
                case["samples"].append({
                    "utc": stamp(),
                    "locked": int(server.getInt(f"/{dev}/plls/{pll}/locked")),
                    "error_deg": float(server.getDouble(f"/{dev}/plls/{pll}/error")),
                    "osc_frequency_hz": float(server.getDouble(f"/{dev}/oscs/{pll}/freq")),
                    "center_frequency_hz": float(server.getDouble(f"/{dev}/plls/{pll}/freqcenter")),
                })
                time.sleep(0.08)
            case["ever_locked"] = any(sample["locked"] == 1 for sample in case["samples"])
            case["t660_shot_count"] = t660.get_shot_count()
            record["cases"].append(case)
            server.setInt(f"/{dev}/plls/{pll}/enable", 0)
            time.sleep(0.05)
        record["status"] = "CAPTURED"
    except Exception as exc:
        record["status"] = "FAIL"
        record["error"] = str(exc)
    finally:
        try:
            t660.command("STOP", expect_response=False)
            t660.set_trigger_source("OFF")
            for channel in "ABCD":
                t660.disable_channel(channel)
        except Exception as exc:
            record["t660_cleanup_error"] = str(exc)
        t660.close()
        try:
            if original:
                server = hf._require_server()
                dev = hf.device_id
                for pll in (0, 1):
                    server.setInt(f"/{dev}/plls/{pll}/enable", 0)
                    for node in (
                        "adcselect", "harmonic", "order", "adcthreshold",
                    ):
                        server.setInt(
                            f"/{dev}/plls/{pll}/{node}", int(original[f"pll{pll}/{node}"])
                        )
                    server.setDouble(f"/{dev}/oscs/{pll}/freq", float(original[f"osc{pll}"]))
                    server.setDouble(
                        f"/{dev}/plls/{pll}/freqcenter",
                        float(original[f"pll{pll}/freqcenter"]),
                    )
                    server.setInt(
                        f"/{dev}/plls/{pll}/enable", int(original[f"pll{pll}/enable"])
                    )
                server.sync()
        except Exception as exc:
            record["hf_cleanup_error"] = str(exc)
        hf.close()
        try:
            manager = TimingRecipeManager(inventory=inventory, command_log=log)
            safe = manager.apply_recipe(
                SAFE_IDLE,
                output_path=RAW / "hf01_pll_reference_diagnostic_011_safe_idle.json",
            )
            record["safe_idle"] = {
                "matches_recipe": safe.get("matches_recipe"),
                "mismatches": safe.get("mismatches"),
            }
        except Exception as exc:
            record["safe_idle_error"] = str(exc)
        log.close()
        record["finished_utc"] = stamp()
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record.get("status") == "CAPTURED" and record.get("safe_idle", {}).get("matches_recipe") else 1


if __name__ == "__main__":
    raise SystemExit(main())
