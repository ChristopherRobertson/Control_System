"""Bounded finite LabOne DAQ blocks drained into preallocated host storage.

Node semantics follow Zurich's LabOne API DAQ module reference. In particular,
``buffersize``/``buffercount`` describe input buffers, not a reservation of
resident result history. Host allocation does not guarantee LabOne memory.
Stock DataAcquisitionModule.read() supports reads while acquisition is running;
the adapter must drain regularly and stop on any loss or count failure.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from time import monotonic, sleep

import numpy as np

from control_app.workflows.phase_scan_data import DETECTOR_INPUT, SINGLE_DETECTOR_MODE

MAX_EVENTS_PER_BLOCK = 16
MAX_HOST_CAPTURE_BYTES = 64 * 1024 * 1024
# HF2's DAQ scalar field is ``dio``. The generic LabOne module documentation
# uses ``bits`` for other devices; HF2 rejects that source at execute().
HF2_DIO_SIGNAL = "dio"


class AcquisitionCapacityError(RuntimeError):
    """A finite capture exceeds its explicit host retention bounds."""


class AcquisitionIntegrityError(RuntimeError):
    """The nominal acquisition cannot be accepted; retain its original data."""


@dataclass(frozen=True)
class ResidentCapacityReservation:
    """Legacy optional evidence from an independently verified API adapter.

    This is an application integration interface, not a LabOne SDK method.
    Retained for callers that already supply such an adapter. The stock path
    uses bounded incremental reads and host storage, not this reservation.
    """
    available_bytes: int
    reservation_id: str
    api_source: str


def estimate_capture_bytes(*, signal_paths, grid_cols, count, duration_s, rate_sps, allocation_margin_fraction=.25):
    """Conservative returned-array estimate, using configured/read-back grids.

    Each concrete scalar signal has its own float64/uint64 values and uint64
    timestamps (16 bytes per sample), plus 4096 bytes per signal record and
    optional allocation overhead (legacy default 25%; regular phase scans use zero). Shared timestamps are deliberately counted again.
    """
    if not math.isfinite(allocation_margin_fraction) or allocation_margin_fraction < 0:
        raise AcquisitionCapacityError("Allocation margin must be finite and nonnegative")
    paths = tuple(signal_paths)
    if not paths or grid_cols < 2 or count < 1 or not math.isfinite(duration_s) or duration_s <= 0:
        raise AcquisitionCapacityError("Invalid finite DAQ size inputs")
    payload = len(paths) * int(grid_cols) * int(count) * 16
    metadata = len(paths) * int(count) * 4096
    return {"signal_paths": list(paths), "grid_cols": int(grid_cols), "count": int(count),
            "duration_s": float(duration_s), "returned_grid_rate_sps": float(rate_sps),
            "sample_representation": "float64 or uint64 value + uint64 device timestamp",
            "bytes_per_sample_per_signal": 16, "payload_bytes": payload,
            "metadata_bytes": metadata, "allocation_margin_fraction": allocation_margin_fraction,
            "estimated_bytes": math.ceil((payload + metadata) * (1 + allocation_margin_fraction))}


class FinitePhaseDAQ:
    """Separate detector/timing grids preserve native rates and a tiny DIO17 record."""
    def __init__(self, hf, *, events, duration_s, pretrigger_s, capacity_verifier=None,
                 host_capacity_bytes=MAX_HOST_CAPTURE_BYTES, live_readback_timeout_s=1.0,
                 read_policy="incremental", max_events=MAX_EVENTS_PER_BLOCK, allocation_margin_fraction=.25,
                 detector_indices=(0,), timing_demodulator=2, detector_metadata=None):
        self.allocation_margin_fraction = allocation_margin_fraction
        self.hf, self.events = hf, tuple(events)
        self.detector_indices = tuple(detector_indices)
        self.timing_demodulator = int(timing_demodulator)
        if (not self.detector_indices or len(set(self.detector_indices)) != len(self.detector_indices)
                or any(index not in range(6) for index in self.detector_indices)
                or self.timing_demodulator not in range(6)
                or self.timing_demodulator in self.detector_indices):
            raise AcquisitionCapacityError("Distinct supported detector and timing demodulators are required")
        self.detector_metadata = dict(detector_metadata or {
            "detector_mode": SINGLE_DETECTOR_MODE, "detector_input": DETECTOR_INPUT})
        self.detector_module_roles = {index: "detectors" if position == 0 else f"detectors_{index}"
                                      for position, index in enumerate(self.detector_indices)}
        if read_policy not in {"incremental", "deferred"}:
            raise ValueError("DAQ read policy must be incremental or deferred")
        self.read_policy = read_policy
        self.incremental = read_policy == "incremental" and capacity_verifier is None
        if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events < 1:
            raise AcquisitionCapacityError("A positive verified event capacity is required")
        if not 1 <= len(self.events) <= max_events:
            raise AcquisitionCapacityError(f"The complete DAQ sequence requires 1 to {max_events} events")
        self.modules = []
        self.raw = {"mode": "finite_sweep_active", **self.detector_metadata,
                    "modules": {}, "read_chunks": [],
                    "read_call_count": 0, "read_policy": read_policy,
                    "read_phase_observations": []}
        self.armed = False
        self._read = False
        self.sequence_complete = False
        self.closed = False
        self.capacity = None
        self._host_buffer = None
        self._host_used_bytes = 0
        self.live_readback_timeout_s = float(live_readback_timeout_s)
        if not math.isfinite(self.live_readback_timeout_s) or self.live_readback_timeout_s <= 0:
            raise AcquisitionCapacityError("A positive finite live readback timeout is required")
        self.clockbase = float(hf.get_clockbase())
        if not math.isfinite(self.clockbase) or self.clockbase <= 0:
            raise AcquisitionIntegrityError("Invalid device clockbase")
        try:
            rates = {i: float(hf._get_node("double", f"/{hf.device_id}/demods/{i}/rate"))
                     for i in (*self.detector_indices, self.timing_demodulator)}
            if any(not math.isfinite(v) or v <= 0 for v in rates.values()):
                raise AcquisitionCapacityError("Cannot size capture from invalid demodulator rate readbacks")
            base = f"/{hf.device_id}/demods"
            self.timing_path = f"{base}/{self.timing_demodulator}/sample.{HF2_DIO_SIGNAL}"
            self.raw["digital_trigger_source"] = self.timing_path
            for index in self.detector_indices:
                self._configure(self.detector_module_roles[index],
                                [f"{base}/{index}/sample.{field}" for field in ("x", "y")],
                                len(events), 21, duration_s, pretrigger_s, rates[index])
            self._configure("timing", [self.timing_path], len(events), 21,
                            duration_s, pretrigger_s, rates[self.timing_demodulator])
            pump_count = sum(bool(e.pump_enabled) for e in events)
            # Also arm for an unpumped baseline: its guard record catches an
            # unexpected pump. Four samples per event, never a continuous log.
            self._configure("pump_events", [self.timing_path], pump_count,
                            17, 3/rates[self.timing_demodulator], 1/rates[self.timing_demodulator],
                            rates[self.timing_demodulator])
            required = sum(item["estimate"]["estimated_bytes"] for item in self.modules)
            readbacks = [item["readback"] for item in self.modules]
            self.raw["capacity_estimate_bytes"] = required
            self.raw["module_readbacks"] = readbacks
            if required > int(host_capacity_bytes) or int(host_capacity_bytes) <= 0:
                raise AcquisitionCapacityError(
                    f"Bounded DAQ needs {required} host bytes; configured limit is {host_capacity_bytes}")
            try:
                self._host_buffer = np.empty(required, dtype=np.uint8)
                self._host_buffer.fill(0)  # Commit/touch the actual host allocation before arming.
            except (MemoryError, ValueError) as exc:
                raise AcquisitionCapacityError(f"Cannot allocate {required} host capture bytes") from exc
            self.capacity = {"required_bytes": required,
                             "method": "host_preallocation_and_incremental_native_read",
                             "host_allocated_bytes": int(self._host_buffer.nbytes),
                             "host_allocation_scope": "Returned NumPy arrays; Python mappings/scalars and SDK transfers use additional estimated memory",
                             "host_limit_bytes": int(host_capacity_bytes),
                             "maximum_events_per_block": max_events,
                             "labone_resident_capacity_guaranteed": False,
                             "limitations": "Host arrays are preallocated; SDK transfer allocations and internal LabOne buffers remain external. Loss/count errors invalidate completion.",
                             "modules": [{"role": item["role"], **item["estimate"]} for item in self.modules]}
            if read_policy == "deferred":
                self.capacity.update(
                    method="end_of_sequence_read_with_bounded_host_copy",
                    limitations=("Complete native histories remain in LabOne until sequence completion. "
                                 "Exact history/count/grid readbacks and host allocation are verified before arming. "
                                 "LabOne exposes no resident-memory reservation; runtime loss or missing records "
                                 "invalidate completion and all returned data are retained."))
            if capacity_verifier is not None:
                reservation = capacity_verifier(hf, tuple(item["module"] for item in self.modules),
                                                tuple(readbacks), required)
                if (not isinstance(reservation, ResidentCapacityReservation) or
                        not reservation.reservation_id.strip() or not reservation.api_source.strip()):
                    raise AcquisitionCapacityError("Capacity provider did not return an installed-API reservation")
                if int(reservation.available_bytes) < required:
                    raise AcquisitionCapacityError(
                        f"Insufficient LabOne resident capacity: {required} bytes required, "
                        f"{reservation.available_bytes} bytes guaranteed")
                self.capacity["reservation"] = asdict(reservation)
            self.raw["capacity"] = self.capacity
        except BaseException:
            self.close()
            raise

    def _configure(self, role, paths, count, bit, duration, pretrigger, rate):
        module = self.hf.create_daq_module()
        item = {"role": role, "module": module, "paths": paths, "expected_count": count,
                "last_timestamp": {}}
        self.modules.append(item)
        # Include both endpoints so the last sample, not only the nominal
        # burst length, covers the entire qualified interval.
        cols = max(2, math.ceil(duration * rate) + 1)
        settings = {"device": self.hf.device_id, "type": 2,
                    "triggernode": self.timing_path,
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
        # In exact mode duration is a derived OUTPUT (N / source rate), not a
        # settable acquisition input. HF2/LabOne may expose its default value
        # until execution receives native samples. Preserve that observation,
        # size the host arena from read-back columns/rates, and verify the live
        # derived output before arm() returns permission for external triggers.
        before_execute_duration = float(module.getDouble("duration"))
        calculated_duration = cols / rate
        for node, getter in (("buffercount", module.getInt), ("buffersize", module.getDouble)):
            try:
                readback[node] = getter(node)
            except Exception as exc:
                readback[node] = {"unavailable": str(exc)}
        readback["duration"] = before_execute_duration
        readback["duration_before_execute_s"] = before_execute_duration
        readback["duration_calculated_from_grid_s"] = calculated_duration
        readback["duration_verified_after_execute"] = False
        readback["requested_capture_duration_s"] = duration
        readback["source_sample_rate_sps"] = rate
        readback["grid_cols_per_calculated_duration_s"] = cols / calculated_duration
        item["readback"] = readback
        readback["expected_count"] = count
        readback["guard_records"] = 1
        item["estimate"] = estimate_capture_bytes(signal_paths=paths, grid_cols=cols, count=count + 1,
                                                  duration_s=calculated_duration, rate_sps=rate,
                                                  allocation_margin_fraction=self.allocation_margin_fraction)
        item["estimate"]["duration_basis"] = "read-back grid columns / source rate; verified after execute"

    def _verify_live_grid_readbacks(self):
        deadline = monotonic() + self.live_readback_timeout_s
        pending = list(self.modules)
        observations = self.raw.setdefault("live_grid_readback_observations", [])
        while pending:
            for item in pending[:]:
                module, readback = item["module"], item["readback"]
                # Grid size controls the allocated host memory; do not accept
                # a module that silently changes it during execution.
                for node in ("grid/mode", "grid/cols", "grid/rows", "count", "historylength"):
                    actual = module.getInt(node)
                    if actual != readback[node]:
                        raise AcquisitionCapacityError(f"DAQ {item['role']} live {node}={actual}, configured {readback[node]}")
                actual = float(module.getDouble("duration"))
                readback["duration"] = actual
                expected = readback["duration_calculated_from_grid_s"]
                observations.append({"role": item["role"], "duration_s": actual,
                                     "expected_grid_duration_s": expected})
                if (math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-6,
                                                         abs_tol=max(1e-12, 1/self.clockbase))):
                    requested = readback["requested_capture_duration_s"]
                    rate = readback["source_sample_rate_sps"]
                    if actual + 1e-12 < requested or actual > requested + 2/rate + 1e-12:
                        raise AcquisitionCapacityError(f"DAQ {item['role']} live duration does not cover the qualified interval with endpoint rounding")
                    readback["duration_verified_after_execute"] = True
                    pending.remove(item)
            if pending:
                if monotonic() >= deadline:
                    details = "; ".join(f"{item['role']}: {item['readback']['duration']} s observed, "
                                        f"{item['readback']['duration_calculated_from_grid_s']} s expected"
                                        for item in pending)
                    raise AcquisitionCapacityError("DAQ live exact-grid duration did not become valid before external triggers: " + details)
                sleep(min(.01, max(0., deadline-monotonic())))

    def arm(self):
        if not self.capacity or self.armed or self.closed:
            raise RuntimeError("Finite DAQ must have fresh bounded host storage before arming")
        self.armed = True  # Permit partial salvage if a later module fails to execute.
        try:
            for item in self.modules:
                item["module"].execute()
            self._verify_live_grid_readbacks()
        except BaseException as exc:
            self.raw.setdefault("arm_errors", []).append(str(exc))
            try:
                self.drain(partial=True)
            except Exception as salvage_error:
                self.raw.setdefault("read_errors", []).append(f"Arm-failure salvage: {salvage_error}")
            finally:
                self.close()
            raise

    def finished(self):
        return self.armed and all(bool(item["module"].finished()) for item in self.modules)

    def expected_records_received(self):
        """Use records already drained to the host; module progress is not retention."""
        if self.raw.get("arm_errors"):
            return False
        if not self.incremental:
            # Compatibility only for an explicitly supplied legacy reservation.
            return self.armed and all(
                float(item["module"].progress()[0]) * item["readback"]["count"] >= item["expected_count"] - 1e-9
                for item in self.modules)
        return self.armed and all(
            len(self.raw["modules"].get(item["role"], {}).get(path.lower(), [])) == item["expected_count"]
            for item in self.modules for path in item["paths"]) and not self.raw.get("read_errors") and not self.raw.get("integrity_errors")

    def _retain_native(self, value):
        """Copy all returned native arrays, including unknown header arrays, unchanged."""
        if isinstance(value, (np.ndarray, np.generic)):
            array = np.asarray(value)
            if array.dtype.hasobject:
                raise AcquisitionIntegrityError("Native object arrays cannot be retained without pickle")
            offset = (self._host_used_bytes + 7) // 8 * 8
            if offset + array.nbytes > self._host_buffer.nbytes:
                raise AcquisitionCapacityError("Returned native arrays exceeded bounded host storage")
            retained = np.ndarray(array.shape, dtype=array.dtype, buffer=self._host_buffer, offset=offset)
            np.copyto(retained, array)
            self._host_used_bytes = offset + array.nbytes
            return retained
        if isinstance(value, dict):
            return {key: self._retain_native(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._retain_native(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._retain_native(item) for item in value)
        return value

    def _validate_record(self, item, path, record, previous):
        ticks = np.asarray(record.get("timestamp", [])).reshape(-1)
        values = np.asarray(record.get("value", [])).reshape(-1)
        cols = item["readback"]["grid/cols"]
        if (len(ticks) != cols or len(values) != cols or values.dtype.itemsize > 8 or
                ticks.dtype.itemsize > 8 or not np.issubdtype(ticks.dtype, np.integer) or
                np.any(ticks[1:] <= ticks[:-1]) or not np.isfinite(values).all()):
            raise AcquisitionIntegrityError(f"Invalid, dropped, or nonmonotonic samples in {path}")
        if previous is not None and int(ticks[0]) <= previous:
            raise AcquisitionIntegrityError(f"Duplicated or unordered record in {path}")
        expected_step = self.clockbase / item["estimate"]["returned_grid_rate_sps"]
        if np.any(np.abs(np.diff(ticks).astype(float) - expected_step) > max(1., expected_step*.01)):
            raise AcquisitionIntegrityError(f"Dropped samples or grid discontinuity in {path}")
        # HF2 returns DIO words as float64. All uint32 integers are exactly
        # representable there; reject fractional/out-of-range data before any
        # uint32 conversion can truncate or wrap the observed digital lines.
        if path.endswith(".dio") and (values.dtype.kind not in "uif" or
                np.any(values < 0) or np.any(values > np.iinfo(np.uint32).max) or
                np.any(values != np.floor(values))):
            raise AcquisitionIntegrityError(f"DIO values are not exact uint32 words in {path}")
        header = record.get("header", {})
        # ZI_CHUNK_HEADER_FLAG_DATALOSS, distinct from the module flags setting.
        # https://docs.zhinst.com/labone_api_user_manual/reference/c/enums.html#zichunkheaderflags_enum
        if np.any(np.asarray(header.get("flags", 0), dtype=np.uint64) & np.uint64(0x4)):
            raise AcquisitionIntegrityError(f"dataloss reported in native header.flags for {path}")
        for field in ("dataloss", "sampleloss", "overflow", "dropped_samples", "clipped"):
            if np.any(header.get(field, 0)) or np.any(record.get(field, 0)):
                raise AcquisitionIntegrityError(f"{field} reported in {path}")
        return ticks, values

    def drain(self, *, partial=False):
        """Retain complete incremental SDK reads while finite guards remain armed.

        No disk I/O occurs here. Even failed/duplicate responses remain in
        read_chunks; all other modules are drained before an error is raised.
        """
        if not self.armed or self.closed:
            raise RuntimeError("Drain requires an armed, open finite DAQ block")
        self.raw["read_phase_observations"].append(
            {"sequence_complete": self.sequence_complete, "partial_salvage": partial})
        if self.read_policy == "deferred" and not partial and not self.sequence_complete:
            raise AcquisitionIntegrityError("Native data retrieval is deferred until the complete sequence ends")
        if self._read:
            return self.raw
        read_errors, integrity_errors = [], []
        for item in self.modules:
            role = item["role"]
            try:
                payload = item["module"].read(True)
                self.raw["read_call_count"] += 1
            except Exception as exc:
                read_errors.append(f"{role}: {exc}")
                continue
            if not payload:
                continue
            try:
                retained = self._retain_native(payload)
            except Exception as exc:
                # The SDK has already delivered this response. Preserve it even
                # when the planned arena is exceeded, then reject completion.
                retained = payload
                integrity_errors.append(f"{role}: native retention failed: {exc}")
            self.raw["read_chunks"].append({"role": role, "payload": retained})
            if not isinstance(retained, dict):
                integrity_errors.append(f"{role}: native response is not a mapping")
                continue
            aggregate = self.raw["modules"].setdefault(role, {})
            for path in item["paths"]:
                records = next((v for k, v in retained.items() if str(k).lower() == path.lower()), [])
                if not isinstance(records, (list, tuple)):
                    integrity_errors.append(f"{role}: expected a native burst list for {path}")
                    continue
                collected = aggregate.setdefault(path.lower(), [])
                collected.extend(records)
                if len(collected) > item["expected_count"]:
                    integrity_errors.append(f"Exact record count failed for {path}: {len(collected)} (guard or duplicate)")
                for record in records:
                    try:
                        ticks, _ = self._validate_record(item, path, record, item["last_timestamp"].get(path))
                        item["last_timestamp"][path] = int(ticks[-1])
                    except Exception as exc:
                        integrity_errors.append(f"{role}: {exc}")
        self.raw["host_native_bytes_used"] = self._host_used_bytes
        if read_errors:
            self.raw.setdefault("read_errors", []).extend(read_errors)
        if integrity_errors:
            self.raw.setdefault("integrity_errors", []).extend(integrity_errors)
        if (read_errors or integrity_errors) and not partial:
            raise AcquisitionIntegrityError("LabOne incremental read failed: " + "; ".join(read_errors + integrity_errors))
        return self.raw

    def mark_sequence_complete(self):
        self.sequence_complete = True

    def read(self, *, partial=False):
        if self.closed and partial:
            return self.raw
        if self.raw.get("arm_errors") and not partial:
            raise AcquisitionIntegrityError("DAQ live grid validation failed before external triggers")
        if self._read:
            if not partial and (self.raw.get("read_errors") or self.raw.get("integrity_errors")):
                raise AcquisitionIntegrityError("LabOne block has retained read/integrity errors")
            return self.raw
        if not partial and not (self.sequence_complete or self.finished()):
            raise AcquisitionIntegrityError("Finite DAQ read requested before all expected triggers completed")
        try:
            self.drain(partial=partial)
        finally:
            if not self.incremental:
                self._read = True
        self._read = True
        if not partial and (self.raw.get("read_errors") or self.raw.get("integrity_errors")):
            raise AcquisitionIntegrityError("LabOne block has retained read/integrity errors")
        return self.raw

    def records(self):
        """Validate original grids, then adapt in memory for one-pass reconstruction."""
        self.read()
        by_role = {}
        for item in self.modules:
            paths = {str(k).lower(): v for k, v in self.raw["modules"].get(item["role"], {}).items()}
            parsed = {}
            for path in item["paths"]:
                records = paths.get(path.lower(), [])
                if len(records) != item["expected_count"]:
                    raise AcquisitionIntegrityError(f"Exact record count failed for {path}: {len(records)}")
                previous = None
                parsed[path] = []
                for record in records:
                    ticks, values = self._validate_record(item, path, record, previous)
                    previous = int(ticks[-1])
                    parsed[path].append((ticks, values))
            by_role[item["role"]] = parsed
        timing_path = self.timing_path
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
            for demod in self.detector_indices:
                xp = f"/{self.hf.device_id}/demods/{demod}/sample.x"
                yp = f"/{self.hf.device_id}/demods/{demod}/sample.y"
                xt, x = by_role[self.detector_module_roles[demod]][xp][index]
                yt, y = by_role[self.detector_module_roles[demod]][yp][index]
                if not np.array_equal(xt, yt) or abs(int(xt[0])-int(ticks[0])) > self.clockbase*.001:
                    raise AcquisitionIntegrityError("Detector/timing grids do not describe the same scan event")
                streams[xp.rsplit(".", 1)[0]] = {"timestamp": xt, "x": x, "y": y,
                                                       "dio": np.zeros(len(x), np.uint32),
                                                       "auxin0": np.zeros(len(x)), "auxin1": np.zeros(len(x))}
            streams[timing_path.rsplit(".", 1)[0]] = {
                "timestamp": ticks, "dio": bits.astype(np.uint32), "x": np.zeros(len(ticks)),
                "y": np.zeros(len(ticks)), "auxin0": np.zeros(len(ticks)), "auxin1": np.zeros(len(ticks))}
            output.append((event, {"optical_valid": True, "clockbase_hz": self.clockbase,
                                  **self.detector_metadata,
                                  "native_chunks": [{"data": streams}],
                                  "pump_event_tick": pump_tick, "sweep_event_tick": sweep_tick}))
        return output

    def close(self):
        if self.closed:
            return
        self.closed = True
        errors = []
        for item in self.modules:
            for action in ("finish", "clear"):
                try:
                    getattr(item["module"], action)()
                except Exception as exc:
                    errors.append(f"{item['role']} {action}: {exc}")
        if errors:
            self.raw["cleanup_errors"] = errors


def _one_rising_tick(ticks, values, bit):
    high = np.asarray(values, dtype=np.uint32) & (1 << bit) != 0
    edges = np.flatnonzero(~high[:-1] & high[1:]) + 1
    if len(edges) != 1:
        raise AcquisitionIntegrityError(f"Expected exactly one DIO{bit} rising event; observed {len(edges)}")
    return int(ticks[edges[0]])
