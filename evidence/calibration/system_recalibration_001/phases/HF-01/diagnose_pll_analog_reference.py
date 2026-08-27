"""Bounded HF2LI PLL diagnostic using the confirmed PicoScope carrier path."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import time


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
ACQUISITION_ID = "HF01-PLL-ANALOG-REFERENCE-DIAG-001"


def stamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / "hf01_pll_analog_reference_diagnostic_001.json"
    if path.exists():
        raise FileExistsError(
            f"{ACQUISITION_ID} already executed; use a new stable acquisition ID"
        )
    inventory = load_config_inventory(write_files=False)
    log = (HERE / "command_log.txt").open("a", encoding="utf-8")
    hf = HF2LIService(inventory.devices["hf2li"], command_log=log)
    pico_settings = {
        "resolution": "12BIT",
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
                "range": "10V",
                "analog_offset_v": 0.0,
            },
        },
        "external_trigger": {
            "source": "A",
            "threshold_adc": 0,
            "direction": 2,
            "delay_samples": 0,
            "auto_trigger_ms": 10,
        },
        "total_samples": 5000,
        "pre_trigger_samples": 1000,
        "timebase": 1,
        "timeout_s": 5.0,
    }
    pico = PicoScopeService(
        inventory.devices["picoscope"], pico_settings, command_log=log
    )
    record: dict[str, object] = {
        "campaign_id": "system_recalibration_001",
        "phase_id": "HF-01",
        "acquisition_id": ACQUISITION_ID,
        "bounded_repeat_authorization_id": "HF01-AUTH-AMEND-004",
        "stimulus_authority_acquisition_id": "HF01-AWG-FIRST-ENABLE-R1-001",
        "started_utc": stamp(),
        "status": "STARTED",
        "output": {
            "waveform": "SINE",
            "frequency_hz": 2_000_000.0,
            "pk_to_pk_v": 0.050,
            "offset_v": 0.0,
            "connected_measured_vpp_authority": 0.051247817269791676,
        },
    }
    original: dict[str, float | int] = {}
    try:
        manager = TimingRecipeManager(inventory=inventory, command_log=log)
        safe_before = manager.apply_recipe(
            SAFE_IDLE,
            output_path=RAW / "hf01_pll_analog_reference_diagnostic_001_pre_safe_idle.json",
        )
        record["t660_safe_idle_before"] = {
            "matches_recipe": safe_before.get("matches_recipe"),
            "mismatches": safe_before.get("mismatches"),
        }
        if safe_before.get("matches_recipe") is not True:
            raise RuntimeError("T660 safe idle did not match before analog PLL diagnostic")

        hf.connect()
        server = hf._require_server()
        device = hf.device_id
        nodes = {
            "sigins/0/ac": "int",
            "sigins/0/imp50": "int",
            "sigins/0/diff": "int",
            "sigins/0/range": "double",
            "oscs/0/freq": "double",
            "plls/0/enable": "int",
            "plls/0/adcselect": "int",
            "plls/0/harmonic": "int",
            "plls/0/order": "int",
            "plls/0/adcthreshold": "int",
        }
        for suffix, kind in nodes.items():
            getter = server.getInt if kind == "int" else server.getDouble
            original[suffix] = getter(f"/{device}/{suffix}")
        record["hf2li_original"] = original
        master = {
            "system_extclk": int(server.getInt(f"/{device}/system/extclk")),
            "status_plllock_flag": int(
                server.getInt(f"/{device}/status/flags/plllock")
            ),
            "status_dcmlock_flag": int(
                server.getInt(f"/{device}/status/flags/dcmlock")
            ),
        }
        record["master_clock_before"] = master
        if master != {
            "system_extclk": 1,
            "status_plllock_flag": 0,
            "status_dcmlock_flag": 0,
        }:
            raise RuntimeError(f"HF2LI master clock is not locked: {master}")

        server.setInt(f"/{device}/plls/0/enable", 0)
        server.setInt(f"/{device}/sigins/0/ac", 0)
        server.setInt(f"/{device}/sigins/0/imp50", 0)
        server.setInt(f"/{device}/sigins/0/diff", 0)
        server.setDouble(f"/{device}/sigins/0/range", 0.1)
        server.setDouble(f"/{device}/oscs/0/freq", 2_000_000.0)
        server.sync()
        server.setInt(f"/{device}/plls/0/adcselect", 0)
        server.setInt(f"/{device}/plls/0/harmonic", 1)
        server.setInt(f"/{device}/plls/0/order", 4)
        server.setInt(f"/{device}/plls/0/adcthreshold", 100)

        pico.open_unit()
        record["pico_zero_before"] = pico.disable_signal_generator()
        record["pico_nonzero"] = pico.configure_builtin_signal_generator(
            waveform="SINE",
            frequency_hz=2_000_000.0,
            pk_to_pk_v=0.050,
            offset_v=0.0,
        )
        server.setInt(f"/{device}/plls/0/enable", 1)
        server.sync()
        samples = []
        for _ in range(30):
            samples.append(
                {
                    "utc": stamp(),
                    "enable": int(server.getInt(f"/{device}/plls/0/enable")),
                    "locked": int(server.getInt(f"/{device}/plls/0/locked")),
                    "error_deg": float(server.getDouble(f"/{device}/plls/0/error")),
                    "osc0_frequency_hz": float(
                        server.getDouble(f"/{device}/oscs/0/freq")
                    ),
                    "freqcenter_hz": float(
                        server.getDouble(f"/{device}/plls/0/freqcenter")
                    ),
                    "adcclip0": int(
                        server.getInt(f"/{device}/status/flags/adcclip/0")
                    ),
                }
            )
            if samples[-1]["locked"] == 1:
                break
            time.sleep(0.1)
        record["samples"] = samples
        record["status"] = (
            "PASS_PLL_LOCKED_TO_ANALOG_REFERENCE"
            if samples[-1]["locked"] == 1
            else "FAIL_PLL_DID_NOT_LOCK_TO_ANALOG_REFERENCE"
        )
    except Exception as exc:
        record["status"] = "FAIL"
        record["error"] = str(exc)
    finally:
        try:
            if pico._is_open:
                record["pico_zero_final"] = pico.disable_signal_generator()
                pico.stop()
                pico.close_unit()
        except Exception as exc:
            record["pico_cleanup_error"] = str(exc)
        try:
            if original:
                server = hf._require_server()
                device = hf.device_id
                server.setInt(f"/{device}/plls/0/enable", 0)
                for suffix in (
                    "sigins/0/ac",
                    "sigins/0/imp50",
                    "sigins/0/diff",
                    "plls/0/adcselect",
                    "plls/0/harmonic",
                    "plls/0/order",
                    "plls/0/adcthreshold",
                ):
                    server.setInt(f"/{device}/{suffix}", int(original[suffix]))
                for suffix in ("sigins/0/range", "oscs/0/freq"):
                    server.setDouble(f"/{device}/{suffix}", float(original[suffix]))
                server.setInt(
                    f"/{device}/plls/0/enable", int(original["plls/0/enable"])
                )
                server.sync()
        except Exception as exc:
            record["hf2li_cleanup_error"] = str(exc)
        hf.close()
        try:
            manager = TimingRecipeManager(inventory=inventory, command_log=log)
            safe_after = manager.apply_recipe(
                SAFE_IDLE,
                output_path=RAW / "hf01_pll_analog_reference_diagnostic_001_final_safe_idle.json",
            )
            record["t660_safe_idle_after"] = {
                "matches_recipe": safe_after.get("matches_recipe"),
                "mismatches": safe_after.get("mismatches"),
            }
        except Exception as exc:
            record["final_safe_idle_error"] = str(exc)
        record["finished_utc"] = stamp()
        path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        log.close()
    print(json.dumps(record, indent=2, sort_keys=True))
    clean = (
        record.get("status") == "PASS_PLL_LOCKED_TO_ANALOG_REFERENCE"
        and not any(key.endswith("_error") for key in record)
        and (record.get("t660_safe_idle_after") or {}).get("matches_recipe") is True
    )
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
