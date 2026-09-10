"""Optional HF2 settings preserve legacy calls and round-trip via fake LabOne."""
from copy import deepcopy

import pytest

from control_app.devices.hf2li_service import HF2LIPreset, HF2LIService
from control_app.measurement_host.ownership import (
    HardwareCoordinator, OwnershipError, require_hardware_owner,
)


BASE = "/dev123"
LEGACY_NODES = {
    **{f"{BASE}/sigins/{index}/{node}": kind for index in (0, 1)
       for node, kind in (("ac", "int"), ("imp50", "int"), ("diff", "int"), ("range", "double"))},
    **{f"{BASE}/plls/0/{node}": kind for node, kind in (
        ("enable", "int"), ("adcselect", "int"), ("freqcenter", "double"),
        ("harmonic", "int"), ("order", "int"), ("adcthreshold", "int"))},
    f"{BASE}/oscs/0/freq": "double",
    **{f"{BASE}/demods/{index}/{node}": kind for index in (0, 3)
       for node, kind in (("enable", "int"), ("adcselect", "int"), ("oscselect", "int"),
                          ("harmonic", "int"), ("order", "int"), ("timeconstant", "double"),
                          ("rate", "double"), ("trigger", "int"))},
}


class SettingsServer:
    def __init__(self):
        self.types = dict(LEGACY_NODES)
        self.types.update({f"{BASE}/demods/{index}/{node}": kind for index in (0, 3)
                           for node, kind in (("sinc", "int"), ("phaseshift", "double"))})
        self.values = {path: 1 if kind == "int" else 12.5 for path, kind in self.types.items()}
        self.reads, self.writes = [], []
        self.sync_count = 0

    def _read(self, kind, path):
        assert self.types[path] == kind
        self.reads.append((kind, path))
        return self.values[path]

    def getInt(self, path):
        return self._read("int", path)

    def getDouble(self, path):
        return self._read("double", path)

    def _write(self, kind, path, value):
        assert self.types[path] == kind
        assert type(value) is (int if kind == "int" else float)
        self.writes.append((kind, path, value))
        self.values[path] = value

    def setInt(self, path, value):
        self._write("int", path, value)

    def setDouble(self, path, value):
        self._write("double", path, value)

    def sync(self):
        self.sync_count += 1


@pytest.fixture
def connected():
    service, server = HF2LIService({}), SettingsServer()
    service._server, service._device_id = server, "dev123"
    return service, server


@pytest.mark.parametrize("sinc,phase", [(False, 0), (True, -42.5)])
def test_optional_false_zero_and_nonzero_values_are_written(connected, sinc, phase):
    service, server = connected
    service.configure_demodulators([{"index": 0, "sinc": sinc, "phaseshift": phase}])
    assert server.writes == [
        ("int", f"{BASE}/demods/0/enable", 0),
        ("int", f"{BASE}/demods/0/sinc", int(sinc)),
        ("double", f"{BASE}/demods/0/phaseshift", float(phase)),
    ]


@pytest.mark.parametrize("preset", [None, HF2LIPreset("legacy", {"demodulators": [{"index": 0}]})])
def test_omitted_settings_leave_writes_and_snapshot_footprint_unchanged(connected, preset):
    service, server = connected
    service.configure_demodulators([{"index": 0, "order": 4, "rate_sps": 2000}])
    assert server.writes == [
        ("int", f"{BASE}/demods/0/enable", 0),
        ("int", f"{BASE}/demods/0/order", 4),
        ("double", f"{BASE}/demods/0/rate", 2000.0),
    ]
    snapshot = service.export_settings_snapshot(preset=preset)
    assert snapshot["read_errors"] == {}
    assert {path: item["type"] for path, item in snapshot["nodes"].items()} == LEGACY_NODES
    assert {path for _, path in server.reads} == set(LEGACY_NODES)


def test_optional_snapshot_fields_are_requested_per_demodulator(connected):
    service, server = connected
    preset = HF2LIPreset("selected_fields", {"demodulators": [
        {"index": 0, "sinc": False}, {"index": 3, "phaseshift": 0},
    ]})
    snapshot = service.export_settings_snapshot(preset=preset)
    assert snapshot["read_errors"] == {}
    assert set(snapshot["nodes"]) == set(LEGACY_NODES) | {
        f"{BASE}/demods/0/sinc", f"{BASE}/demods/3/phaseshift",
    }
    assert {path for _, path in server.reads} == set(snapshot["nodes"])
    service.reload_settings_snapshot(snapshot)
    assert not {f"{BASE}/demods/0/phaseshift", f"{BASE}/demods/3/sinc"} & {
        path for _, path, _ in server.writes
    }


@pytest.mark.parametrize("sinc,phase", [(False, 0), (True, 37.25)])
def test_optional_snapshot_roundtrip_restores_original_values(connected, tmp_path, sinc, phase):
    service, server = connected
    preset = HF2LIPreset("dc_response", {"demodulators": [
        {"index": 0, "sinc": sinc, "phaseshift": phase},
    ]})
    service.configure_demodulators(preset.settings["demodulators"])
    before = deepcopy(server.values)
    path = tmp_path / "settings.json"
    snapshot = service.export_settings_snapshot(path, preset=preset)
    assert snapshot["nodes"][f"{BASE}/demods/0/sinc"] == {"type": "int", "value": int(sinc)}
    assert snapshot["nodes"][f"{BASE}/demods/0/phaseshift"] == {"type": "double", "value": float(phase)}
    service.configure_demodulators([{"index": 0, "sinc": not sinc, "phaseshift": 90}])
    result = service.reload_settings_snapshot(path)
    assert server.values == before
    assert set(result["applied_nodes"]) == set(snapshot["nodes"])
    assert server.sync_count == 1


def test_optional_writes_and_restoration_reject_expired_owner(connected, tmp_path):
    service, server = connected
    coordinator = HardwareCoordinator(tmp_path / "optional-settings.lock")
    token = coordinator.acquire("optional-settings-test")
    try:
        with coordinator.scope(token):
            require_hardware_owner(service)
            service.configure_demodulators([{"index": 0, "sinc": False, "phaseshift": 0}])
    finally:
        coordinator.release(token, safe_verified=True)
    server.writes.clear()
    with pytest.raises(OwnershipError):
        service.configure_demodulators([{"index": 0, "sinc": True, "phaseshift": 90}])
    with pytest.raises(OwnershipError):
        service.reload_settings_snapshot({"nodes": {
            f"{BASE}/demods/0/sinc": {"type": "int", "value": 1},
        }})
    assert server.writes == []
