"""Capture one uniquely named native WaveMaster measurement window."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import time

PHASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PHASE_DIR.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_app.devices.coherent_wavemaster_service import CoherentWaveMasterService


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acquisition-id", required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--interval-s", type=float, default=0.35)
    args = parser.parse_args()
    if args.count < 1 or args.interval_s < 0:
        raise SystemExit("count must be >=1 and interval-s must be >=0")
    stem = args.acquisition_id.lower().replace("-", "_")
    json_path = PHASE_DIR / "raw" / f"{stem}.json"
    csv_path = PHASE_DIR / "raw" / f"{stem}.csv"
    if json_path.exists() or csv_path.exists():
        raise SystemExit(f"refusing to overwrite existing acquisition {args.acquisition_id}")
    rows = []
    start = now()
    with (PHASE_DIR / "command_log.txt").open("a", encoding="utf-8", newline="\n") as log:
        meter = CoherentWaveMasterService.from_config(command_log=log)
        meter.connect()
        try:
            settings = {
                "identity": asdict(meter.identify()),
                "self_test_hex": f"0x{meter.self_test():02X}",
                "autocalibration": meter.get_autocalibration(),
                "mode": meter.get_mode(),
                "units": meter.get_units(),
                "period_s": meter.get_period_s(),
            }
            for index in range(1, args.count + 1):
                observed = now()
                measurement = meter.get_measurement()
                rows.append({"replicate_index": index, "observed_utc": observed, **asdict(measurement)})
                if index < args.count:
                    time.sleep(args.interval_s)
        finally:
            meter.close()
    end = now()
    record = {
        "schema_version": "1.0.0",
        "campaign_id": "system_recalibration_001",
        "phase_id": "WM-01",
        "phase_run_id": "WM01-RUN-20260821",
        "acquisition_id": args.acquisition_id,
        "start_utc": start,
        "end_utc": end,
        "settings": settings,
        "samples": rows,
    }
    json_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
