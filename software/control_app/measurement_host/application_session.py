"""Application lifetime transports, with operation-scoped access and cached previews.

Acquisition reads remain live. ``CachedDevice`` exposes the startup snapshot to
previews; it never silently performs I/O on a cache miss.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter
from datetime import UTC, datetime
from threading import RLock
import json
import os
from pathlib import Path
import math

from .ownership import OwnershipError, _bound_owner


_SETTINGS_READS = frozenset({
    "export_settings_snapshot", "get_clockbase", "read_active_settings", "verified_frame_capacity", "identity_snapshot",
    "get_num_installed_qcls", "is_emission_on", "is_laser_armed", "is_interlock_set", "is_key_switch_set",
    "are_tecs_ready", "get_wavelength_trigger_params", "get_wavelength_trigger_pulse_width_us", "get_qcl_tuning_range",
    "get_qcl_pulse_rate", "get_qcl_pulse_width", "get_qcl_current", "get_qcl_pulse_limits", "get_qcl_operating_mode",
    "get_qcl_set_temperature", "is_cw_allowed", "get_qcl_cw_current_limits", "get_qcl_current_limits", "get_sweep_parameters", "read_state",
})


def current_session():
    owner = _bound_owner.get()
    return getattr(owner[0], "application_session", None) if owner else None


def shared_device(name, constructor, **attributes):
    """CLI/tests retain fresh services; the desktop opts into connection reuse."""
    session = current_session()
    if session is None:
        return constructor()
    return session.borrow(name, constructor, **attributes)


def _key(method, args, kwargs):
    # Snapshots contain a superset of all experiment nodes, independent of the
    # caller's preset name. File-writing snapshot calls always stay live.
    if method == "export_settings_snapshot":
        return (method,)
    return (method, repr(args), repr(sorted(kwargs.items())))


class DeviceLease:
    """A stale worker cannot inherit a newer operation's ownership token."""
    def __init__(self, session, name, owner):
        object.__setattr__(self, "_session", session)
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_owner", owner)

    def __getattr__(self, name):
        raw = self._session.devices[self._name]
        value = getattr(raw, name)
        if not callable(value):
            return value
        def call(*args, **kwargs):
            return self._session.invoke(self, name, args, kwargs)
        return call

    def __setattr__(self, name, value):
        if name == "_measurement_owner":
            object.__setattr__(self, "_owner", value)
        else:
            setattr(self._session.devices[self._name], name, value)


class CachedDevice:
    """Read-only UI view. No owner token and no route to a hardware call."""
    def __init__(self, session, name):
        self.session, self.name = session, name

    def __getattr__(self, method):
        if method == "device_id":
            return self.session.capabilities["dual"]["device_id"]
        if method in {"connect", "initialize", "close", "deinitialize"}:
            return lambda: None
        def read(*args, **kwargs):
            key = (self.name, _key(method, args, kwargs))
            with self.session._mutex:
                if key not in self.session.cache:
                    failure = self.session.errors.get(self.name)
                    if failure:
                        raise RuntimeError(
                            f"Settings unavailable for {self.name}: {failure}; "
                            "resolve the connection problem, then use Instruments → Refresh connected settings"
                        )
                    raise RuntimeError(f"Settings unavailable for {self.name}.{method}; use Instruments → Refresh connected settings")
                return deepcopy(self.session.cache[key])
        return read


def cached_hf2_choices(device, mode):
    """No discovery or transport calls from previews or acquisition setup."""
    session = device.session if isinstance(device, CachedDevice) else device._session if isinstance(device, DeviceLease) else None
    return deepcopy(session.capabilities.get(mode, {})) if session is not None else {}


class ApplicationDeviceSession:
    def __init__(self, coordinator, configuration, *, factories=None, capability_cache_path=None):
        from .device_factories import installed_device_factories
        self.coordinator = coordinator
        self.configuration = deepcopy(configuration)
        self.factories = installed_device_factories(shared=False) if factories is None else factories
        self.capability_cache_path = (Path(capability_cache_path) if capability_cache_path else
            Path(os.environ.get("LOCALAPPDATA", Path.home()/".cache"))/"ControlSystem"/"device_capabilities_v1.json"
            if factories is None else None)
        self.devices, self.connected, self.cache, self.capabilities = {}, set(), {}, {}
        self.errors = {}
        self.ready = False
        self.closed = False
        self._locks = {}
        self._mutex = RLock()
        self.dirty = set()
        self.changed = None
        coordinator.application_session = self

    def borrow(self, name, constructor, **attributes):
        owner = _bound_owner.get()
        if owner is None or owner[0] is not self.coordinator:
            raise OwnershipError("Application devices require this application's hardware scope")
        self.coordinator.assert_owner(owner[1])
        with self._mutex:
            if self.closed:
                raise RuntimeError("Application device session is closed")
            self.coordinator.retain_application_connections = True
            if name not in self.devices:
                self.devices[name] = constructor()
                self._locks[name] = RLock()
            raw = self.devices[name]
            for key, value in attributes.items():
                setattr(raw, key, value)
            return DeviceLease(self, name, owner)

    def device(self, name):
        return self.borrow(name, lambda: self.factories[name](configuration=self.configuration), command_log=None)

    def invoke(self, lease, method, args, kwargs):
        owner = _bound_owner.get() or lease._owner
        if owner[0] is not self.coordinator:
            raise OwnershipError("Device belongs to another application")
        self.coordinator.assert_owner(owner[1])
        name = lease._name
        # Preserve the services' established concurrent stop/status paths. A
        # blocking SDK scan or wait must never hold a pool lock against Stop.
        lifecycle_call = method in {"connect", "initialize", "open_unit", "close", "deinitialize", "close_unit"}
        with self._locks[name] if lifecycle_call else nullcontext():
            raw = self.devices[name]
            raw._measurement_owner = owner
            if method in {"connect", "initialize", "open_unit"}:
                if name in self.connected:
                    return None
                result = getattr(raw, method)(*args, **kwargs)
                self.connected.add(name)
                return result
            if method in {"close", "deinitialize", "close_unit"}:
                # Native acquisition cleanup still stops scans, inhibits outputs,
                # restores its settings and unsubscribes. Keep the SDK alive.
                if name == "hf2li":
                    raw.stop_acquisition()
                elif name == "mircat" and name in self.connected:
                    pointer = raw.get_red_laser_pointer_status()
                    if pointer["installed"] and pointer["enabled"]:
                        raw.set_red_laser_pointer_enabled(False)
                        self._invalidate(name)
                        self.dirty.add(name)
                return None
            if method in {"discover_phase_scan_capabilities", "discover_dual_phase_scan_capabilities"}:
                mode = "dual" if "dual" in method else "single"
                if mode in self.capabilities:
                    return deepcopy(self.capabilities[mode])
            key = (name, _key(method, args, kwargs))
            reading = (method.startswith(("get_", "is_", "are_", "read_", "export_settings"))
                       or method in {"identify", "identity_snapshot", "verified_frame_capacity"}
                       or method == "command" and args and "?" in args[0])
            if not reading:
                # Invalidate before the call: even a failed write may have
                # partially changed the device and must not leave stale data.
                with self._mutex:
                    self._invalidate(name)
                    self.dirty.add(name)
            result = getattr(raw, method)(*args, **kwargs)
            if (method in _SETTINGS_READS or method == "command" and reading) and not kwargs.get("path"):
                with self._mutex:
                    if method == "export_settings_snapshot" and key in self.cache:
                        result_for_cache = {**result, "nodes": {**self.cache[key].get("nodes", {}), **result.get("nodes", {})}}
                    else:
                        result_for_cache = result
                    self.cache[key] = deepcopy(result_for_cache)
            return result

    def _invalidate(self, name):
        with self._mutex:
            self.cache = {key: value for key, value in self.cache.items() if key[0] != name}

    def _start_device(self, name, token, recheck_capabilities):
        # ContextVars do not automatically propagate into executor threads.
        # Each independent connection shares the same exclusive startup token.
        started = perf_counter()
        try:
            with self.coordinator.scope(token):
                if name in self.errors and name in self.devices:
                    raw = self.devices[name]
                    raw._measurement_owner = (self.coordinator, token)
                    raw.command_log = None
                    close = "deinitialize" if name == "mircat" else "close_unit" if name == "picoscope" else "close"
                    getattr(raw, close)()
                    with self._mutex:
                        self.connected.discard(name)
                device = self.device(name)
                method = "initialize" if name == "mircat" else "open_unit" if name == "picoscope" else "connect"
                getattr(device, method)()
                if name == "hf2li":
                    if recheck_capabilities:
                        self.capabilities.clear()
                    dual = None if recheck_capabilities else self._load_capabilities(device.device_id)
                    if dual is None:
                        dual = device.discover_dual_phase_scan_capabilities()
                        self._save_capabilities(dual)
                    self.capabilities["dual"] = dual
                    self.capabilities["single"] = {**deepcopy(dual["sample"]), "enabled_streams": (0, 2),
                        "source": dual["source"] + "; CH1 subset of verified three-stream profile"}
                self.refresh(name)
                with self._mutex:
                    self.errors.pop(name, None)
        except Exception as exc:
            with self._mutex:
                self.errors[name] = f"{type(exc).__name__}: {exc}"
                self._invalidate(name)
        return perf_counter() - started

    def start(self, progress=lambda message: None, *, recheck_capabilities=False):
        token = self.coordinator.acquire("application:startup", purpose="Connect application devices and read settings")
        self.coordinator.retain_application_connections = True
        self.ready = False
        started = perf_counter()
        self.startup_device_seconds = {}
        try:
            progress("Discovering SDK devices; checking HF2LI supported choices…")
            # One task per physical connection. Never issue concurrent commands
            # on the same device or release ownership while tasks remain active.
            with ThreadPoolExecutor(max_workers=max(1, min(6, len(self.factories))),
                                    thread_name_prefix="instrument-startup") as executor:
                # SDK discovery and Windows virtual COM opens can contend for
                # USB converters. In particular, COM7 has repeatedly failed
                # during discovery but opened successfully once it finished.
                # Keep parallel work within each stage, never across that edge.
                serial_names = {"t660_1", "t660_2", "opo_iris"}
                stages = ([name for name in self.factories if name not in serial_names],
                          [name for name in self.factories if name in serial_names])
                for stage, names in enumerate(stages):
                    if stage == 1 and names:
                        progress("SDK discovery finished; connecting serial instruments…")
                    tasks = {executor.submit(self._start_device, name, token, recheck_capabilities): name
                             for name in names}
                    for task in as_completed(tasks):
                        name = tasks[task]
                        elapsed = task.result()
                        self.startup_device_seconds[name] = elapsed
                        status = "unavailable" if name in self.errors else "ready"
                        progress(f"{name}: {status} ({elapsed:.1f} s); {len(self.startup_device_seconds)}/{len(self.factories)} checked")
            # USB SDK discovery may briefly hold a serial converter while the
            # independent startup jobs run. Retry denied timer connections once
            # after all discovery has finished, never in an unbounded loop.
            for name, error in tuple(self.errors.items()):
                if name.startswith("t660_") and any(text in error for text in (
                    "Windows denied access", "Access is denied", "PermissionError(13"
                )):
                    progress(f"Retrying {name} after device discovery…")
                    self.startup_device_seconds[name] += self._start_device(name, token, recheck_capabilities)
            self.ready = True
        finally:
            self.startup_seconds = perf_counter() - started
            # Executor shutdown joins every task, including when progress or a
            # worker fails. Discovery restoration failures retain fault status.
            safe = not any("restoration failed" in error.lower() for error in self.errors.values())
            self.coordinator.release(token, safe_verified=safe,
                detail="Application connections retained; startup settings read" if safe else str(self.errors))
        return {"errors": deepcopy(self.errors), "connected": sorted(self.connected),
                "elapsed_seconds": self.startup_seconds, "device_seconds": dict(self.startup_device_seconds)}

    def _load_capabilities(self, device_id):
        """An optional device capability record, never cached operating settings.

        Missing/incompatible records fall back to discovery. Acquisition still
        verifies the selected settings on the connected hardware every time.
        """
        if self.capability_cache_path is None:
            return None
        try:
            record = json.loads(self.capability_cache_path.read_text(encoding="utf-8"))
            caps = record["capabilities"]
            if record["schema_version"] != 1 or caps["device_id"] != device_id or not caps["verified"]:
                return None
            from control_app.measurement_modules.phase_scan.dual_detector_phase_scan import DualHF2Capabilities
            parsed = DualHF2Capabilities.from_dict(caps)
            for profile in (parsed.sample, parsed.reference):
                if not profile.orders or not profile.rates_sps or not all(profile.timeconstants_by_order.get(order) for order in profile.orders):
                    return None
                if (any(type(order) is not int or not 1 <= order <= 8 for order in profile.orders)
                        or any(not math.isfinite(rate) or not 0 < rate <= 231000 for rate in profile.rates_sps)
                        or any(not math.isfinite(tau) or tau <= 0 for values in profile.timeconstants_by_order.values() for tau in values)
                        or not 16000 <= profile.timing_rate_sps <= 231000):
                    return None
            caps["source"] += "; retained device capability enumeration, live settings read separately"
            return caps
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _save_capabilities(self, caps):
        if self.capability_cache_path is None:
            return
        try:
            path = self.capability_cache_path
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps({"schema_version": 1, "capabilities": caps}), encoding="utf-8")
            temporary.replace(path)
        except OSError:
            pass  # An optional speed optimization must not block the instrument.

    def refresh(self, name):
        """Refresh bounded operating settings; never arm, emit or start timing."""
        device = self.device(name)
        if name == "hf2li":
            from control_app.devices.hf2li_service import HF2LIPreset
            snapshot = device.export_settings_snapshot(preset=HF2LIPreset("application_settings", {
                "demodulators": [{"index": i, "sinc": False, "phaseshift": 0.} for i in range(6)],
                "oscillators": [{"index": 1}], "pll": {"index": 1}}))
            if snapshot.get("read_errors"):
                raise RuntimeError(f"HF2LI settings readback incomplete: {snapshot['read_errors']}")
            device.get_clockbase()
        elif name.startswith("t660_"):
            device.read_active_settings()
            for edge in range(1, 9):
                device.command(f"TIME:RELTo{edge}?")
            if name == "t660_2":
                device.verified_frame_capacity()
        elif name == "mircat":
            for method in ("get_num_installed_qcls", "is_emission_on", "is_laser_armed", "is_interlock_set",
                           "is_key_switch_set", "are_tecs_ready", "get_wavelength_trigger_params",
                           "get_wavelength_trigger_pulse_width_us"):
                getattr(device, method)()
            for i in range(1, device.get_num_installed_qcls()+1):
                for method in ("get_qcl_tuning_range", "get_qcl_pulse_rate", "get_qcl_pulse_width",
                               "get_qcl_current", "get_qcl_pulse_limits", "get_qcl_operating_mode",
                               "get_qcl_set_temperature", "is_cw_allowed", "get_qcl_cw_current_limits",
                               "get_qcl_current_limits"):
                    getattr(device, method)(i)
            device.read_state()
            try:
                device.get_sweep_parameters()
            except Exception:
                pass  # An unset sweep is valid at startup.
        elif name == "opo_iris":
            device.identity_snapshot()
        self.updated_utc = datetime.now(UTC).isoformat()
        self.dirty.discard(name)

    def update_readbacks(self, token):
        if not self.ready or self.closed:
            return
        with self.coordinator.scope(token):
            for name in tuple(self.dirty):
                try:
                    self.refresh(name)
                    self.errors.pop(name, None)
                except Exception as exc:
                    self.errors[name] = str(exc)
                    self._invalidate(name)
        if self.changed is not None:
            try:
                self.changed()
            except Exception:
                pass  # Presentation notification cannot prevent owner release.

    def fixed_profile(self, mode, settings):
        from types import SimpleNamespace
        from uuid import uuid4
        from control_app.measurement_modules.fixed_wavenumber_kinetics.adapters import InstalledDevices
        context = SimpleNamespace(mode=mode, devices=SimpleNamespace(
            create=lambda name, operation: CachedDevice(self, name)))
        backend = InstalledDevices(context, SimpleNamespace(run_id=str(uuid4())))
        backend.connect(lambda: None, prepare=False)
        return backend.discover_operating_profile(settings, lambda: None, lambda message: None)

    def slow_scan_readbacks(self, mode):
        from control_app.measurement_modules.steady_state_slow_scan.acquisition import _absolute_edges
        hf, laser = CachedDevice(self, "hf2li"), CachedDevice(self, "mircat")
        timers = {name: CachedDevice(self, name) for name in ("t660_1", "t660_2")}
        states = {name: device.read_active_settings() for name, device in timers.items()}
        references = {str(i): int(timers["t660_1"].command(f"TIME:RELTo{i}?")) for i in range(1, 9)}
        edges = _absolute_edges(states["t660_1"], references)
        pulse = {"pulse_rate_hz": laser.get_qcl_pulse_rate(1), "pulse_width_ns": laser.get_qcl_pulse_width(1),
                 "current_ma": laser.get_qcl_current(1)}
        result = {"hf2li": deepcopy(self.capabilities[mode]), "hf2li_settings": hf.export_settings_snapshot(),
            "qcl_windows": [laser.get_qcl_tuning_range(1)], "qcl_pulse_params": {"1": pulse},
            "qcl_pulse_limits": {"1": laser.get_qcl_pulse_limits(1)}, "qcl_cw_allowed": {"1": laser.is_cw_allowed(1)},
            "qcl_cw_current_limits": {"1": laser.get_qcl_cw_current_limits(1)},
            "qcl_current_limits": {"1": laser.get_qcl_current_limits(1)},
            "marker_width_us": laser.get_wavelength_trigger_pulse_width_us(),
            "probe_width_s": edges["4"]-edges["3"], "probe_width_basis": "Application session T660-1 B edge readbacks",
            **states, "t660_frame_capacity": timers["t660_2"].verified_frame_capacity(),
            "mircat_state": {"qcl": 1, **pulse}}
        try:
            result["sweep"] = laser.get_sweep_parameters()
        except RuntimeError:
            pass
        return result

    def phase_capabilities(self, dual=False):
        from control_app.measurement_modules.phase_scan.regular_phase_scan import HF2Capabilities
        from control_app.measurement_modules.phase_scan.dual_detector_phase_scan import DualHF2Capabilities
        mode = "dual" if dual else "single"
        if not self.ready or mode not in self.capabilities or "hf2li" in self.errors:
            raise RuntimeError("Application device check is not ready: " + str(self.errors))
        caps = deepcopy(self.capabilities[mode])
        count = self.cache.get(("mircat", _key("get_num_installed_qcls", (), {})))
        if count is None:
            raise RuntimeError("MIRcat startup settings unavailable: " + str(self.errors.get("mircat", "")))
        ranges = [self.cache[("mircat", _key("get_qcl_tuning_range", (i,), {}))] for i in range(1, count+1)]
        caps["tuning_ranges"] = tuple((r["qcl"], r["min_cm1"], r["max_cm1"]) for r in ranges)
        return (DualHF2Capabilities if dual else HF2Capabilities).from_dict(caps)

    def nanosecond_capabilities(self):
        from control_app.measurement_modules.nanosecond_stroboscopy.adapters import InstalledAdapter
        # Reuse the experiment's pure settings conversion; CachedDevice cannot
        # connect, prepare, configure or acquire hardware.
        adapter = InstalledAdapter(None, None, {})
        adapter.devices = {name: CachedDevice(self, name) for name in ("hf2li", "mircat", "t660_1", "t660_2")}
        adapter.before["hf2li"] = adapter.devices["hf2li"].export_settings_snapshot()
        for name in ("t660_1", "t660_2"):
            device = adapter.devices[name]
            adapter.before[name] = {"readback": device.read_active_settings(),
                "references": {i: int(device.command(f"TIME:RELTo{i}?")) for i in range(1, 9)}}
        laser = adapter.devices["mircat"]
        adapter.before["mircat"] = {"qcls": [{"pulse_rate_hz": laser.get_qcl_pulse_rate(1),
            "pulse_width_ns": laser.get_qcl_pulse_width(1), "limits": laser.get_qcl_pulse_limits(1)}]}
        return adapter._capabilities()

    def rapid_scan_capabilities(self, mode):
        from control_app.measurement_modules.repeated_rapid_scan.planner import HardwareCapabilities
        from control_app.measurement_modules.repeated_rapid_scan.acquisition import available_memory_bytes
        from control_app.measurement_modules.steady_state_slow_scan.acquisition import _quantity, _response
        readbacks = self.slow_scan_readbacks(mode)
        nodes = readbacks["hf2li_settings"]["nodes"]
        device_id = self.capabilities[mode]["device_id"]
        live = {}
        for role, index, input_index in (("sample", 0, 0), ("reference", 3, 1)):
            if role == "reference" and mode != "dual":
                continue
            for field, suffix in (("rate", "_rate_hz"), ("order", "_filter_order"), ("timeconstant", "_filter_timeconstant_s")):
                live[role+suffix] = nodes[f"/{device_id}/demods/{index}/{field}"]["value"]
            live[role+"_input_range_v"] = nodes[f"/{device_id}/sigins/{input_index}/range"]["value"]
        pulse = readbacks["qcl_pulse_params"]["1"]
        live.update(mircat_pulse_rate_hz=pulse["pulse_rate_hz"], mircat_pulse_width_ns=pulse["pulse_width_ns"],
                    mircat_current_ma=pulse["current_ma"], probe_pulse_width_s=readbacks["probe_width_s"],
                    probe_frequency_hz=_quantity(_response(readbacks["t660_1"]["queries"]["synth_frequency"])))
        sweep = readbacks.get("sweep", {})
        if sweep.get("scan_rate_cm1_s", 0) > 0:
            live["scan_speed_cm1_s"] = sweep["scan_rate_cm1_s"]
        return HardwareCapabilities(frame_capacity=readbacks["t660_frame_capacity"], max_aggregate_rate_hz=700000.,
            hf2_choices=deepcopy(self.capabilities[mode]),
            connected_readback_id=f"application-settings-{self.updated_utc}", live_settings=live,
            actual_sample_rate_hz=live["sample_rate_hz"], actual_reference_rate_hz=live.get("reference_rate_hz"),
            acquisition_timing_rate_hz=nodes[f"/{device_id}/demods/2/rate"]["value"],
            available_memory_bytes=available_memory_bytes())

    def close(self):
        """Call only after the application's existing safe-state shutdown."""
        owner = _bound_owner.get()
        if owner is None:
            raise OwnershipError("Shutdown requires scoped hardware ownership")
        errors = []
        for name, raw in reversed(tuple(self.devices.items())):
            try:
                raw._measurement_owner = owner
                raw.command_log = None
                if name == "picoscope" and name in self.connected:
                    raw.stop()
                method = "deinitialize" if name == "mircat" else "close_unit" if name == "picoscope" else "close"
                getattr(raw, method)()
                self.connected.discard(name)
            except Exception as exc:
                errors.append(f"{name}: {exc}")
        if errors:
            raise RuntimeError("Application disconnect failed: " + "; ".join(errors))
        self.closed = True
        self.coordinator.retain_application_connections = False
