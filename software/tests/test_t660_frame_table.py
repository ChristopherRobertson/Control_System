"""Hardware-free protocol tests for the finite phase-delay timing architecture."""
from copy import deepcopy

import pytest

from control_app.devices.t660_service import T660Service, T660ConfigurationError, T660CommandError


class FrameDevice(T660Service):
    def __init__(self, *, feature="1"):
        super().__init__("t660_2", {"role": "master_timing_trains_frames"})
        self.commands = []
        self.feature = feature
        self.values = {}
        self.frames = []
        self.pending = {}

    def command(self, command, *, expect_response=True, delay_s=.04):
        if ";" in command:
            return ";".join(self.command(part) for part in command.split(";"))
        command = command.lstrip(":")
        self.commands.append(command)
        if command == "FEATure:FRAMe?":
            return self.feature
        if command == "TFRame:STATus?":
            return "DONE"
        if command.endswith("?"):
            return self.values.get(command[:-1], "0")
        key, _, value = command.partition(" ")
        self.values[key] = value
        if command.startswith("TIME:QUEue") or command.startswith("CHANnel:QUEue"):
            self.pending[key + value.split(",")[0] if "," in value else key] = value
        if key == "TFRame:STORe":
            self.frames.append(deepcopy(self.pending))
        return "OK"


def frame(*, pump_enabled, phase_us=0):
    pump_s = .001 + max(.000180, -phase_us*1e-6)
    process_s = pump_s + phase_us*1e-6 if pump_enabled else .001
    def pulse(delay, width, enabled=True):
        return {"enabled": enabled, "delay": f"{delay:.12f}s", "width": f"{width:.12f}s",
                "polarity": "negative", "termination": "50OHM"}
    return {"channels": {
        "A": pulse(pump_s-.000180, .000010, pump_enabled),
        "B": pulse(pump_s-.000000170, .000010, pump_enabled),
        "C": pulse(process_s, .010), "D": pulse(0, 150e-9, False)}}


def test_preload_programs_one_unpumped_then_all_nominal_frames_with_no_emission():
    device = FrameDevice()
    requested = [frame(pump_enabled=False), frame(pump_enabled=True, phase_us=-2000),
                 frame(pump_enabled=True, phase_us=5000)]
    result = device.preload_frame_table(requested)
    assert result["capacity"] == 8192
    assert result["physical_frame_count"] == result["acquisition_frame_count"] == 3
    assert result["frame_period_s"] == .3
    assert device.commands[0] == "FEATure:FRAMe?"
    assert "TRIGger:EXTernal:PREDiv 600000" in device.commands
    assert "TRAin:QUEue:CouNT 0" in device.commands
    assert "TFRame:LOOP:CouNT 0" in device.commands
    assert "TFRame:LOOP:LAST 2" in device.commands
    assert device.commands.count("STOP") == 1
    assert all(command not in device.commands for command in ("START", "TRIG:SOUR EXT", "TRIG:EXECute"))
    assert len(device.frames) == 3
    assert device.frames[0]["CHANnel:QUEue:MODeA"] == "A, OFF"
    assert device.frames[0]["CHANnel:QUEue:MODeB"] == "B, OFF"
    for stored, requested_frame in zip(device.frames, requested):
        assert stored["CHANnel:QUEue:MODeC"] == "C, ON"
        assert stored["CHANnel:QUEue:MODeD"] == "D, OFF"
        for channel, rising in zip("ABC", (1, 3, 5)):
            assert stored[f"TIME:QUEue{rising}"] == requested_frame["channels"][channel]["delay"]
    start_index = len(device.commands)
    device.start_frame_table()
    assert device.commands[start_index:] == ["TRIG:SOUR EXT", "TFRame:STArt", "START"]
    assert device.get_frames_status() == "DONE"
    assert len(device.frames) == 3  # No frame programming occurs during execution/status polling.


def test_single_background_gets_inert_terminator_not_second_acquisition():
    device = FrameDevice()
    result = device.preload_frame_table([frame(pump_enabled=False)])
    assert result["acquisition_frame_count"] == 1
    assert result["physical_frame_count"] == 2
    assert result["inert_terminator_count"] == 1
    for channel in "ABCD":
        assert device.frames[1][f"CHANnel:QUEue:MODe{channel}"] == f"{channel}, OFF"


def test_continuous_clock_roles_are_abc_on_d_off_without_starting_source():
    device = FrameDevice()
    settings = device.configure_continuous_clock()
    assert settings["clock"]["frequency"] == "2e+06Hz"
    assert settings["trigger_source"] == "OFF"
    assert settings["predivider"] == 1
    for channel in "ABC":
        assert settings["channels"][channel]["enabled"]
        assert f"CHAN:ON {channel}" in device.commands
    assert not settings["channels"]["D"]["enabled"]
    assert "START" not in device.commands
    device.start_continuous_clock()
    assert device.commands[-2:] == ["TRIG:SOUR SYN", "START"]


def test_feature_and_capacity_fail_before_any_timing_mutation():
    absent = FrameDevice(feature="0")
    with pytest.raises(T660ConfigurationError, match="Trains and Frames"):
        absent.preload_frame_table([frame(pump_enabled=False)])
    assert absent.commands == ["FEATure:FRAMe?"]
    oversized = FrameDevice()
    with pytest.raises(T660ConfigurationError, match="verified capacity is 8192"):
        oversized.preload_frame_table([frame(pump_enabled=False)]*8193)
    assert oversized.commands == ["FEATure:FRAMe?"]


def test_predivider_readback_mismatch_prevents_start():
    class WrongDivider(FrameDevice):
        def command(self, command, **kwargs):
            if command == "TRIGger:EXTernal:PREDiv?":
                return "599999"
            return super().command(command, **kwargs)
    device = WrongDivider()
    with pytest.raises(T660CommandError, match="predivider readback"):
        device.preload_frame_table([frame(pump_enabled=False)])
    assert "START" not in device.commands


@pytest.mark.parametrize("changes", [{"count": -1}, {"count": True}, {"spacing_s": 81e-9}, {"stage": "wrong"}])
def test_train_parameters_cannot_silently_round_or_overflow(changes):
    device = FrameDevice()
    with pytest.raises(T660ConfigurationError):
        device.configure_train(**changes)
    assert not device.commands
