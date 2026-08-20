"""One-shot OM-01 Newport shutter-transition capture."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from control_app.devices.newport_1918_service import Newport1918


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=90.0)
    args = parser.parse_args()

    result: dict[str, object] = {
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "purpose": "540nm_OPO_shutter_transition_and_return_to_setting",
        "configuration": {},
        "samples": [],
    }
    with Newport1918(response_delay_s=0.25) as meter:
        result["configuration"] = {
            query: meter.query(query)
            for query in (
                "*IDN?",
                "PM:DETMODEL?",
                "PM:DETSN?",
                "PM:Lambda?",
                "PM:RANGE?",
                "PM:FILT?",
                "PM:ANALOGFILTER?",
                "PM:DIGITALFILTER?",
                "PM:ZERO?",
                "PM:ZEROVAL?",
            )
        }
        args.ready.write_text(
            dt.datetime.now(dt.timezone.utc).isoformat() + "\n", encoding="utf-8"
        )
        deadline = time.monotonic() + args.duration
        index = 0
        while time.monotonic() < deadline:
            index += 1
            response = meter.query("PM:PWS?")
            value, status = response.split(",")
            result["samples"].append(
                {
                    "i": index,
                    "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "power_w": float(value),
                    "status": status.strip(),
                }
            )
    result["ended_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
