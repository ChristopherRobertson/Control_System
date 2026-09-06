"""Derived CSV/figure inspection of preserved inhibited captures; no absorbance."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from datetime import UTC, datetime

import numpy as np

from control_app.workflows.phase_scan_data import load_native, write_json


def inspect_diagnostic(run_path: Path) -> Path:
    destination = run_path / "processed" / datetime.now(UTC).strftime("format_review_%H%M%S_%fZ")
    destination.mkdir(parents=True, exist_ok=False)
    summaries = []
    latest = {}
    with (destination / "samples.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["record", "demodulator_api_index", "timestamp_ticks", "time_in_record_s",
                         "x_v", "y_v", "r_v", "dio_word", "trigger_word", "auxin0_v", "auxin1_v"])
        for index_line in (run_path / "scan_index.jsonl").read_text().splitlines():
            entry = json.loads(index_line)
            record = load_native(run_path / entry["path"])
            if record.get("kind") != "INHIBITED_DIAGNOSTIC":
                raise ValueError("This analysis is restricted to inhibited diagnostic records")
            # Records without explicit marker metadata retain their recorded
            # DIO1 interpretation. Do not reinterpret stored acquisition data.
            dio_bit = int(record.get("diagnostic_dio_bit", 1))
            if not 0 <= dio_bit <= 31:
                raise ValueError("Diagnostic DIO bit must be in 0..31")
            dio_signal = str(record.get("diagnostic_dio_signal", "DIO1 electrical marker"))
            dio_label = f"{dio_signal}\nDIO{dio_bit} logic level"
            chunks = record["native_chunks"]
            paths = sorted({p for chunk in chunks for p in chunk["data"]})
            origin = min(int(chunk["data"][p]["timestamp"][0]) for chunk in chunks
                         for p in chunk["data"] if len(chunk["data"][p].get("timestamp", [])))
            streams = []
            for path in paths:
                parts = [chunk["data"][path] for chunk in chunks if path in chunk["data"]]
                fields = ("timestamp", "x", "y", "dio", "trigger", "auxin0", "auxin1")
                arrays = {name: np.concatenate([part[name] for part in parts]) for name in fields}
                ticks = arrays["timestamp"]
                times = np.array([(int(tick)-origin)/record["clockbase_hz"] for tick in ticks])
                r = np.hypot(arrays["x"], arrays["y"])
                demod = int(path.split("/")[-2])
                dt = np.diff(times)
                positive = dt[dt > 0]
                period = float(np.median(positive)) if len(positive) else None
                dio_level = (arrays["dio"] >> dio_bit) & 1
                rising = np.flatnonzero((dio_level[1:] == 1) & (dio_level[:-1] == 0)) + 1
                falling = np.flatnonzero((dio_level[1:] == 0) & (dio_level[:-1] == 1)) + 1
                widths = []
                for start in rising:
                    end = falling[falling > start]
                    if len(end):
                        widths.append(float(times[end[0]]-times[start]))
                streams.append({"path": path, "samples": len(times),
                    "observed_rate_sps": 1/period if period else None,
                    "nonincreasing_timestamps": int(np.sum(dt <= 0)),
                    "gaps_over_1_5_sample_periods": int(np.sum(dt > 1.5*period)) if period else None,
                    "observed_dio_bit": dio_bit, "observed_dio_signal": dio_signal,
                    "observed_dio_rising_edges": len(rising), "observed_dio_high_widths_s": widths,
                    "r_mean_v": float(np.mean(r)), "r_std_v": float(np.std(r)),
                    "native_fields": sorted(parts[0]),
                })
                if dio_bit == 1:
                    streams[-1].update({"dio1_rising_edges": len(rising), "dio1_high_widths_s": widths})
                for j in range(len(times)):
                    writer.writerow([entry["path"], demod, int(ticks[j]), times[j], arrays["x"][j],
                        arrays["y"][j], r[j], int(arrays["dio"][j]), int(arrays["trigger"][j]),
                        arrays["auxin0"][j], arrays["auxin1"][j]])
                latest[demod] = {"time": times, "r": r, "dio_level": dio_level,
                                 "dio_label": dio_label,
                                 "auxin0": arrays["auxin0"], "auxin1": arrays["auxin1"]}
            summaries.append({"record": entry["path"], "streams": streams,
                "shot_counters_before": record["shot_counters_before"],
                "shot_counters_after": record["shot_counters_after"],
                "observed_dio_label": dio_label,
                "dio_expectation": record.get("diagnostic_dio_expectation", "Electrical marker only; no pump-arrival measurement")})
    write_json(destination / "summary.json", {
        "source_run": str(run_path.resolve()), "classification": "INHIBITED_DIAGNOSTIC",
        "records": summaries,
        "limitations": ["No laser emission, optical background, pump arrival or wavelength sweep was measured.",
                        "The plotted digital input is identified by each record's marker metadata; it is not a pump-arrival measurement.",
                        "An inhibited diagnostic does not command an optical sweep or generate a Sweep Active transition.",
                        "These data cannot determine water-vapor noise or absorbance."]})
    if latest:
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        figure = Figure(figsize=(10, 7), layout="constrained")
        FigureCanvasAgg(figure)
        axes = figure.subplots(3, 1, sharex=True)
        for demod in (0, 3):
            if demod in latest:
                item = latest[demod]
                axes[0].plot(item["time"]*1000, item["r"]*1e6, label=f"Demod {demod+1} (API {demod})")
        timing = latest.get(2, next(iter(latest.values())))
        axes[1].step(timing["time"]*1000, timing["dio_level"], where="post", color="#aa5b16")
        axes[2].plot(timing["time"]*1000, timing["auxin0"], label="Aux input 1")
        axes[2].plot(timing["time"]*1000, timing["auxin1"], label="Aux input 2")
        axes[0].set_ylabel("Detector R (µV)")
        axes[0].legend(loc="upper right")
        axes[1].set_ylabel(timing["dio_label"])
        axes[2].set_ylabel("Aux input (V)")
        axes[2].set_xlabel("Time from first recorded sample (ms)")
        axes[2].legend(loc="upper right")
        for ax in axes:
            ax.grid(alpha=.2)
        figure.suptitle("Real inhibited diagnostic · latest record\nNo optical background or absorbance measurement", fontsize=13)
        figure.savefig(destination / "diagnostic_preview.png", dpi=150)
    return destination
