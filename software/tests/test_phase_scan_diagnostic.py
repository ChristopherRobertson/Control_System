"""Exercise finite triggers and failure cleanup using fake instruments only."""
import json
import numpy as np
import pytest

from control_app.workflows import phase_scan_diagnostic as diagnostic
from control_app.workflows.phase_scan_data import load_native


@pytest.mark.parametrize("poll_fails", [False, True])
def test_inhibited_capture_never_enables_laser_outputs_and_preserves_partial_data(tmp_path, monkeypatch, poll_fails):
    units = []

    class Laser:
        @classmethod
        def from_config(cls, **kwargs): return cls()
        def initialize(self): pass
        def deinitialize(self): pass
        def is_interlock_set(self): return False
        def is_laser_armed(self): return False
        def is_emission_on(self): return False
        # No arm/emission methods exist on this fake: attempting either fails.

    class T660:
        @classmethod
        def from_config(cls, name, **kwargs):
            obj = cls()
            obj.name = name
            obj.device_config = {"serial_number": name}
            obj.source = "OFF"
            obj.started = False
            obj.channels = {ch: False for ch in "ABCD"}
            obj.shots = 10
            units.append(obj)
            return obj
        def connect(self): pass
        def close(self): pass
        def identify(self): return f"HTI,T660,{self.name},1.7"
        def get_shot_count(self): return self.shots
        def set_trigger_source(self, source): self.source = source
        def disable_channel(self, channel): self.channels[channel] = False
        def force_eod(self): pass
        def command(self, command, **kwargs):
            if command in {"START", "STOP"}:
                self.started = command == "START"
        def apply_recipe(self, recipe):
            for ch, settings in recipe["channels"].items():
                self.channels[ch] = settings["enabled"]
        def read_active_settings(self):
            return {"queries": {"trigger_source": {"ok": True, "response": self.source}},
                    "channels": {ch: {"enabled": {"ok": True, "response": "ON" if on else "OFF"}}
                                 for ch, on in self.channels.items()}}
        def fire_remote_trigger(self):
            assert self.source == "REM" and self.started
            assert self.channels == {"A": False, "B": False, "C": True, "D": False}
            self.shots += 1

    class HF:
        restored = False
        polls = 0
        @classmethod
        def from_config(cls, **kwargs): return cls()
        def connect(self): pass
        def close(self): pass
        def load_preset(self, name): return name
        def export_settings_snapshot(self, **kwargs): return {"nodes": {}, "read_errors": {}}
        def apply_preset(self, preset): pass
        def reload_settings_snapshot(self, snapshot): HF.restored = True
        def compare_settings_snapshots(self, *args): return {"mismatches": []}
        def get_clockbase(self): return 210000000
        def start_acquisition(self, **kwargs): pass
        def stop_acquisition(self): pass
        def read_acquisition(self, duration):
            HF.polls += 1
            if poll_fails and HF.polls == 2:
                raise RuntimeError("poll interrupted")
            return {"data": {"/dev/demods/0/sample": {"timestamp": np.arange(3, dtype=np.uint64)}}}

    monkeypatch.setattr(diagnostic, "T660Service", T660)
    monkeypatch.setattr(diagnostic, "HF2LIService", HF)
    monkeypatch.setattr(diagnostic, "MircatService", Laser)
    from control_app.workflows import phase_scan_diagnostic_analysis
    monkeypatch.setattr(phase_scan_diagnostic_analysis, "inspect_diagnostic", lambda path: path)
    if poll_fails:
        with pytest.raises(RuntimeError, match="poll interrupted"):
            diagnostic.capture_inhibited_diagnostic(tmp_path, count=1)
    else:
        diagnostic.capture_inhibited_diagnostic(tmp_path, count=1)
    assert HF.restored
    assert all(u.source == "OFF" and not u.started and not any(u.channels.values()) for u in units)
    assert all(u.shots == 11 for u in units)
    raw = load_native(next(tmp_path.rglob("scan_*.npz")))
    assert len(raw["native_chunks"]) == (1 if poll_fails else 2)
    assert raw["optical_valid"] is False
    result = json.loads(next(tmp_path.rglob("result.json")).read_text())
    assert result["status"] == ("FAILED" if poll_fails else "DIAGNOSTIC_COMPLETE")
