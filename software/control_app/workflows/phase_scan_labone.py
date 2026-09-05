"""Finite LabOne DAQ blocks; no polling stream or per-frame disk writer.

Node semantics follow Zurich's LabOne API DAQ module reference. In particular,
``buffersize``/``buffercount`` describe input buffers, not a reservation of
resident result history. They cannot certify available result memory.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np


class AcquisitionCapacityError(RuntimeError):
    """The installed acquisition API cannot guarantee retention before emission."""


class AcquisitionIntegrityError(RuntimeError):
    """The nominal acquisition cannot be accepted; retain its original data."""


@dataclass(frozen=True)
class ResidentCapacityReservation:
    """Evidence returned by an independently verified installed-API adapter.

    This is an application integration interface, not a LabOne SDK method.
    A provider must reserve/guarantee the stated bytes for these live modules
    until they are read. No configuration flag, RAM estimate, or historical
    Plotter size is a valid provider. Stock LabOne has no such documented API,
    so production deliberately has no default provider.
    """
    available_bytes: int
    reservation_id: str
    api_source: str


def estimate_capture_bytes(*, signal_paths, grid_cols, count, duration_s, rate_sps):
    """Conservative returned-array estimate, using configured/read-back grids.

    Each concrete scalar signal has its own float64/uint64 values and uint64
    timestamps (16 bytes per sample), plus 4096 bytes per signal record and
    25% allocation overhead. Shared timestamps are deliberately counted again.
    """
    paths = tuple(signal_paths)
    if not paths or grid_cols < 2 or count < 1 or not math.isfinite(duration_s) or duration_s <= 0:
        raise AcquisitionCapacityError("Invalid finite DAQ size inputs")
    payload = len(paths) * int(grid_cols) * int(count) * 16
    metadata = len(paths) * int(count) * 4096
    return {"signal_paths": list(paths), "grid_cols": int(grid_cols), "count": int(count),
            "duration_s": float(duration_s), "returned_grid_rate_sps": float(rate_sps),
            "sample_representation": "float64 or uint64 value + uint64 device timestamp",
            "bytes_per_sample_per_signal": 16, "payload_bytes": payload,
            "metadata_bytes": metadata, "allocation_margin_fraction": .25,
            "estimated_bytes": math.ceil((payload + metadata) * 1.25)}


class FinitePhaseDAQ:
    """Separate detector/timing grids preserve native rates and a tiny DIO17 record."""
    def __init__(self, hf, *, events, duration_s, pretrigger_s, capacity_verifier=None):
        self.hf, self.events = hf, tuple(events)
        self.modules = []
        self.raw = {"mode": "finite_sweep_active", "modules": {}}
        self.armed = False
        self._read = False
        self.sequence_complete = False
        self.closed = False
        self.capacity = None
        self.clockbase = float(hf.get_clockbase())
        if not math.isfinite(self.clockbase) or self.clockbase <= 0:
            raise AcquisitionIntegrityError("Invalid device clockbase")
        try:
            rates = {i: float(hf._get_node("double", f"/{hf.device_id}/demods/{i}/rate")) for i in (0, 2, 3)}
            if any(not math.isfinite(v) or v <= 0 for v in rates.values()):
                raise AcquisitionCapacityError("Cannot size capture from invalid demodulator rate readbacks")
            if not math.isclose(rates[0], rates[3], rel_tol=1e-9):
                raise AcquisitionCapacityError("Detector rates must agree to retain both detector grids without resampling")
            base = f"/{hf.device_id}/demods"
            self._configure("detectors", [f"{base}/{i}/sample.{f}" for i in (0, 3) for f in ("x", "y")],
                            len(events), 21, duration_s, pretrigger_s, rates[0])
            self._configure("timing", [f"{base}/2/sample.bits"], len(events), 21,
                            duration_s, pretrigger_s, rates[2])
            pump_count = sum(bool(e.pump_enabled) for e in events)
            # Also arm for an unpumped baseline: its guard record catches an
            # unexpected pump. Four samples per event, never a continuous log.
            self._configure("pump_events", [f"{base}/2/sample.bits"], pump_count,
                            17, 3/rates[2], 1/rates[2], rates[2])
            required = sum(item["estimate"]["estimated_bytes"] for item in self.modules)
            readbacks = [item["readback"] for item in self.modules]
            self.raw["capacity_estimate_bytes"] = required
            self.raw["module_readbacks"] = readbacks
            if capacity_verifier is None:
                raise AcquisitionCapacityError(
                    f"LabOne resident-history capacity is unverified: estimated {required} bytes required. "
                    "count/historylength and buffercount/buffersize readbacks do not reserve result memory; "
                    "the installed API needs a verified resident-capacity provider before trigger emission.")
            reservation = capacity_verifier(hf, tuple(item["module"] for item in self.modules),
                                            tuple(readbacks), required)
            if (not isinstance(reservation, ResidentCapacityReservation) or
                    not reservation.reservation_id.strip() or not reservation.api_source.strip()):
                raise AcquisitionCapacityError("Capacity provider did not return an installed-API reservation")
            if int(reservation.available_bytes) < required:
                raise AcquisitionCapacityError(
                    f"Insufficient LabOne resident capacity: {required} bytes required, "
                    f"{reservation.available_bytes} bytes guaranteed")
            self.capacity = {"required_bytes": required, "reservation": asdict(reservation),
                             "modules": [{"role": item["role"], **item["estimate"]} for item in self.modules]}
            self.raw["capacity"] = self.capacity
        except BaseException:
            self.close()
            raise

    def _configure(self, role, paths, count, bit, duration, pretrigger, rate):
        module = self.hf.create_daq_module()
        item = {"role": role, "module": module, "paths": paths, "expected_count": count}
        self.modules.append(item)
        # Include both endpoints so the last sample, not only the nominal
        # burst length, covers the entire qualified interval.
        cols = max(2, math.ceil(duration * rate) + 1)
        settings = {"device": self.hf.device_id, "type": 2,
                    "triggernode": f"/{self.hf.device_id}/demods/2/sample.bits",
                    "edge": 1, "bits": 1 << bit, "bitmask": 1 << bit,
                    # One finite guard catches unexpected triggers even after
                    # all nominal records arrived; it must never be accepted.
                    "count": count + 1, "historylength": count + 1, "endless": 0,
                    "grid/mode": 4, "grid/cols": cols, "grid/rows": 1,
                    "grid/repetitions": 1, "grid/overwrite": 0, "grid/waterfall": 0,
                    "holdoff/count": 0, "holdoff/time": 0.0, "delay": -pretrigger,
                    "flags": 0xC, "preview": 0, "save/saveonread": 0}
        for node, value in settings.items():
            module.set(node, value)
        for path in paths:
            module.subscribe(path)
        readback = {"role": role}
        for node, value in settings.items():
            getter = module.getString if isinstance(value, str) else module.getDouble if isinstance(value, float) else module.getInt
            actual = getter(node)
            readback[node] = actual
            if actual != value and not (isinstance(value, float) and math.isclose(actual, value, abs_tol=1e-12)):
                raise AcquisitionCapacityError(f"Finite DAQ {role} readback {node}={actual!r}, requested {value!r}")
        actual_duration = float(module.getDouble("duration"))
        if not math.isfinite(actual_duration) or actual_duration + 1e-12 < duration:
            raise AcquisitionCapacityError(f"DAQ {role} duration readback does not retain the qualified interval")
        if actual_duration > duration + 2/rate + 1e-12:
            raise AcquisitionCapacityError(f"DAQ {role} duration readback exceeds one endpoint and rounding sample")
        for node, getter in (("buffercount", module.getInt), ("buffersize", module.getDouble)):
            try:
                readback[node] = getter(node)
            except Exception as exc:
                readback[node] = {"unavailable": str(exc)}
        readback["duration"] = actual_duration
        readback["source_sample_rate_sps"] = rate
        readback["grid_cols_per_duration_s"] = cols / actual_duration
        item["readback"] = readback
        readback["expected_count"] = count
        readback["guard_records"] = 1
        item["estimate"] = estimate_capture_bytes(signal_paths=paths, grid_cols=cols, count=count + 1,
                                                  duration_s=actual_duration, rate_sps=rate)

    def arm(self):
        if not self.capacity or self.armed or self.closed:
            raise RuntimeError("Finite DAQ must have a fresh capacity reservation before arming")
        for item in self.modules:
            item["module"].execute()
        self.armed = True

    def finished(self):
        return self.armed and all(bool(item["module"].finished()) for item in self.modules)

    def expected_records_received(self):
        """Read only progress while the finite guard remains armed."""
        return self.armed and all(
            float(item["module"].progress()[0]) * item["readback"]["count"] >= item["expected_count"] - 1e-9
            for item in self.modules)

    def mark_sequence_complete(self):
        self.sequence_complete = True

    def read(self, *, partial=False):
        if self._read:
            return self.raw
        if not partial and not (self.sequence_complete or self.finished()):
            raise AcquisitionIntegrityError("Finite DAQ read requested before all expected triggers completed")
        errors = []
        for item in self.modules:
            try:
                # Read every module even if another read raises; keep salvageable data.
                self.raw["modules"][item["role"]] = item["module"].read(True)
            except Exception as exc:
                errors.append(f"{item['role']}: {exc}")
        self._read = True
        if errors:
            self.raw["read_errors"] = errors
            if not partial:
                raise AcquisitionIntegrityError("LabOne block read failed: " + "; ".join(errors))
        return self.raw

    def records(self):
        """Validate original grids, then adapt in memory for one-pass reconstruction."""
        self.read()
        by_role = {}
        for item in self.modules:
            paths = {str(k).lower(): v for k, v in self.raw["modules"][item["role"]].items()}
            parsed = {}
            for path in item["paths"]:
                records = paths.get(path.lower(), [])
                if len(records) != item["expected_count"]:
                    raise AcquisitionIntegrityError(f"Exact record count failed for {path}: {len(records)}")
                previous = None
                parsed[path] = []
                for record in records:
                    ticks = np.asarray(record.get("timestamp", [])).reshape(-1)
                    values = np.asarray(record.get("value", [])).reshape(-1)
                    cols = item["readback"]["grid/cols"]
                    if (len(ticks) != cols or len(values) != cols or values.dtype.itemsize > 8 or
                            ticks.dtype.itemsize > 8 or
                            not np.issubdtype(ticks.dtype, np.integer) or
                            np.any(ticks[1:] <= ticks[:-1]) or not np.isfinite(values).all()):
                        raise AcquisitionIntegrityError(f"Invalid, dropped, or nonmonotonic samples in {path}")
                    if previous is not None and int(ticks[0]) <= previous:
                        raise AcquisitionIntegrityError(f"Duplicated or unordered record in {path}")
                    previous = int(ticks[-1])
                    expected_step = self.clockbase / item["estimate"]["returned_grid_rate_sps"]
                    if np.any(np.abs(np.diff(ticks).astype(float) - expected_step) > max(1., expected_step*.01)):
                        raise AcquisitionIntegrityError(f"Dropped samples or grid discontinuity in {path}")
                    # THROW/DETECT are enabled at acquisition. Also honor explicit
                    # loss/overflow metadata supplied by the installed API adapter.
                    header = record.get("header", {})
                    for field in ("dataloss", "sampleloss", "overflow", "dropped_samples", "clipped"):
                        if np.any(header.get(field, 0)) or np.any(record.get(field, 0)):
                            raise AcquisitionIntegrityError(f"{field} reported in {path}")
                    parsed[path].append((ticks, values))
            by_role[item["role"]] = parsed
        timing_path = f"/{self.hf.device_id}/demods/2/sample.bits"
        pump_ticks = []
        for ticks, values in by_role.get("pump_events", {}).get(timing_path, []):
            pump_ticks.append(_one_rising_tick(ticks, values, 17))
        output, pumped_index = [], 0
        for index, event in enumerate(self.events):
            ticks, bits = by_role["timing"][timing_path][index]
            sweep_tick = _one_rising_tick(ticks, bits, 21)
            pump_tick = pump_ticks[pumped_index] if event.pump_enabled else None
            if event.pump_enabled:
                pumped_index += 1
                measured_phase = (sweep_tick - pump_tick) / self.clockbase
                # A bounded timing tolerance identifies the event's frame while
                # allowing calibrated controller start latency. No edge is invented.
                if abs(measured_phase - float(event.phase_delay_us)*1e-6) > .01:
                    raise AcquisitionIntegrityError("Expected one synchronized pump/scan event per frame")
            streams = {}
            for demod in (0, 3):
                xp = f"/{self.hf.device_id}/demods/{demod}/sample.x"
                yp = f"/{self.hf.device_id}/demods/{demod}/sample.y"
                xt, x = by_role["detectors"][xp][index]
                yt, y = by_role["detectors"][yp][index]
                if not np.array_equal(xt, yt) or abs(int(xt[0])-int(ticks[0])) > self.clockbase*.001:
                    raise AcquisitionIntegrityError("Detector/timing grids do not describe the same scan event")
                streams[xp.rsplit(".", 1)[0]] = {"timestamp": xt, "x": x, "y": y,
                                                       "dio": np.zeros(len(x), np.uint32),
                                                       "auxin0": np.zeros(len(x)), "auxin1": np.zeros(len(x))}
            streams[timing_path.rsplit(".", 1)[0]] = {
                "timestamp": ticks, "dio": bits.astype(np.uint32), "x": np.zeros(len(ticks)),
                "y": np.zeros(len(ticks)), "auxin0": np.zeros(len(ticks)), "auxin1": np.zeros(len(ticks))}
            output.append((event, {"optical_valid": True, "clockbase_hz": self.clockbase,
                                  "native_chunks": [{"data": streams}],
                                  "pump_event_tick": pump_tick, "sweep_event_tick": sweep_tick}))
        return output

    def close(self):
        if self.closed:
            return
        self.closed = True
        errors = []
        for item in self.modules:
            try:
                item["module"].finish()
                item["module"].clear()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            self.raw["cleanup_errors"] = errors


def _one_rising_tick(ticks, values, bit):
    high = np.asarray(values, dtype=np.uint32) & (1 << bit) != 0
    edges = np.flatnonzero(~high[:-1] & high[1:]) + 1
    if len(edges) != 1:
        raise AcquisitionIntegrityError(f"Expected exactly one DIO{bit} rising event; observed {len(edges)}")
    return int(ticks[edges[0]])
