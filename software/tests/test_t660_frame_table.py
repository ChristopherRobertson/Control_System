"""Hardware-free protocol tests for the finite phase-delay timing architecture."""
from copy import deepcopy
from dataclasses import replace

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
        self.command_lines = []

    def command_sequence(self, commands):
        self.command_lines.append(list(commands))
        return super().command_sequence(commands)

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


def assert_complete_stored_frame(stored, requested):
    """Check every independently observable pending field, including defaults."""
    assert len(stored) == 20
    for channel, rising in zip("ABCD", (1, 3, 5, 7)):
        expected = requested["channels"][channel]
        assert stored[f"TIME:QUEue{rising}"] == expected["delay"]
        assert stored[f"TIME:QUEue{rising+1}"] == expected["width"]
        assert stored[f"CHANnel:QUEue:MODe{channel}"] == f"{channel}, {'ON' if expected['enabled'] else 'OFF'}"
        polarity = {"negative": "NEG", "positive": "POS"}[expected["polarity"]]
        assert stored[f"CHANnel:QUEue:POLarity{channel}"] == f"{channel}, {polarity}"
        assert stored[f"CHANnel:QUEue:TERMination{channel}"] == f"{channel}, {expected['termination']}"


@pytest.mark.parametrize("blank", [False, True], ids=["pumped_sample", "matched_blank"])
def test_delta_upload_retains_all_fields_of_1402_signed_regular_frames(blank):
    from control_app.workflows.regular_phase_scan import RegularPhaseScanSettings, build_regular_phase_scan_plan
    from control_app.workflows.regular_phase_scan_acquisition import regular_event_timing
    plan = build_regular_phase_scan_plan(RegularPhaseScanSettings(
        start_wavenumber_cm1=2000, stop_wavenumber_cm1=1900, scan_speed_cm1_s=10000,
        phase_delay_us=10, pre_pump_ms=1, post_pump_ms=3))
    assert plan.total_scans == 1402 and plan.first_phase_delay_us < 0 < plan.last_phase_delay_us
    events = [plan.event_at(i) for i in range(plan.total_scans)]
    if blank:
        events = [replace(event, pump_enabled=False) for event in events]
    requested = [regular_event_timing(event)[0] for event in events]
    device = FrameDevice()
    original = deepcopy(requested)
    device.preload_frame_table(requested, predivider=200000)
    assert requested == original
    assert len(device.frames) == len(device.command_lines) == len(requested)
    assert len(device.command_lines[0]) == 21
    for index, (stored, expected, line) in enumerate(zip(device.frames, requested, device.command_lines)):
        assert_complete_stored_frame(stored, expected)
        assert line[-1] == f":TFRame:STORe {index}"
        assert sum(command.startswith(":TFRame:STORe") for command in line) == 1
        assert all(":QUEue" in command for command in line[:-1])
    assert sum(map(len, device.command_lines)) < len(requested)*4
    assert all(command not in device.commands for command in ("START", "TFRame:STArt", "TRIG:SOUR EXT"))


def test_delta_upload_handles_every_changed_field_and_restores_prior_values():
    initial = frame(pump_enabled=False)
    changed = deepcopy(initial)
    for position, channel in enumerate("ABCD"):
        changed["channels"][channel].update(
            delay=f"{position+2}ms", width=f"{position+1}us",
            enabled=not initial["channels"][channel]["enabled"], polarity="positive", termination="LOWZ")
    requested = [initial, changed, changed, initial]
    device = FrameDevice()
    device.preload_frame_table(requested)
    for stored, expected in zip(device.frames, requested):
        assert_complete_stored_frame(stored, expected)
    assert [len(line) for line in device.command_lines] == [21, 21, 1, 21]
    assert device.command_lines[2] == [":TFRame:STORe 2"]


def test_repeated_preloads_fully_reinitialize_pending_configuration():
    device = FrameDevice()
    requested = [frame(pump_enabled=False)]*2
    device.preload_frame_table(requested)
    # Other actions/restoration can change pending state between acquisitions.
    device.pending = {key: "unrelated prior instrument setting" for key in device.pending}
    device.preload_frame_table(requested)
    assert [len(line) for line in device.command_lines] == [21, 1, 21, 1]
    for stored in device.frames[-2:]:
        assert_complete_stored_frame(stored, requested[0])


def test_invalid_later_frame_prevents_every_pending_write_and_store():
    device = FrameDevice()
    requested = [frame(pump_enabled=False)]*2+[deepcopy(frame(pump_enabled=True))]
    requested[-1]["channels"]["D"]["width"] = "0s"
    with pytest.raises(T660ConfigurationError, match="width"):
        device.preload_frame_table(requested)
    assert device.commands == ["FEATure:FRAMe?"]
    assert not device.frames and not device.command_lines


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
    inert = deepcopy(frame(pump_enabled=False))
    for settings in inert["channels"].values():
        settings["enabled"] = False
    assert_complete_stored_frame(device.frames[0], frame(pump_enabled=False))
    assert_complete_stored_frame(device.frames[1], inert)
    assert device.command_lines[1] == [":CHANnel:QUEue:MODe C, OFF", ":TFRame:STORe 1"]


def test_preload_progress_reports_acknowledged_frames_without_protocol_changes():
    requested = [frame(pump_enabled=False), frame(pump_enabled=True, phase_us=-2000)]
    original = FrameDevice()
    original.preload_frame_table(requested)
    observed, progress = FrameDevice(), []

    def report(loaded, total):
        assert loaded == len(observed.frames)
        progress.append((loaded, total))

    result = observed.preload_frame_table(requested, progress=report, cancel_check=lambda: None)
    assert progress == [(0, 2), (1, 2), (2, 2)]
    assert result["physical_frame_count"] == 2
    assert observed.commands == original.commands
    assert observed.frames == original.frames


def test_preload_cancel_after_acknowledged_frame_leaves_triggers_inhibited():
    device = FrameDevice()
    cancelled = False

    def report(loaded, total):
        nonlocal cancelled
        if loaded == 1:
            cancelled = True

    def check():
        if cancelled:
            raise InterruptedError("operator aborted timing-table upload")

    with pytest.raises(InterruptedError, match="aborted"):
        device.preload_frame_table([frame(pump_enabled=False)]*20, progress=report, cancel_check=check)
    assert len(device.frames) == 1
    assert device.values["TRIG:SOUR"] == "OFF"
    assert not any(command in device.commands for command in ("START", "TRIG:SOUR EXT", "TFRame:STArt"))
    assert "TFRame:LOOP:FIRST 0" not in device.commands


def test_preload_failed_frame_is_not_reported_as_loaded():
    class FailedFrame(FrameDevice):
        def command_sequence(self, commands):
            if commands[-1] == ":TFRame:STORe 1":
                raise T660CommandError("injected frame acknowledgement failure")
            return super().command_sequence(commands)

    device, progress = FailedFrame(), []
    with pytest.raises(T660CommandError, match="acknowledgement"):
        device.preload_frame_table([frame(pump_enabled=False)]*3,
                                   progress=lambda loaded, total: progress.append((loaded, total)))
    assert progress == [(0, 3), (1, 3)]
    assert "START" not in device.commands


def test_ack_failure_after_store_does_not_advance_progress_or_reuse_cache():
    class LostAcknowledgement(FrameDevice):
        fail = True

        def command_sequence(self, commands):
            responses = super().command_sequence(commands)
            if self.fail and commands[-1] == ":TFRame:STORe 1":
                self.fail = False
                raise T660CommandError("injected lost acknowledgement after storage")
            return responses

    device, progress = LostAcknowledgement(), []
    requested = [frame(pump_enabled=False)]*3
    with pytest.raises(T660CommandError, match="acknowledgement"):
        device.preload_frame_table(requested, progress=lambda done, total: progress.append((done, total)))
    assert len(device.frames) == 2
    assert progress == [(0, 3), (1, 3)]
    assert "TFRame:LOOP:FIRST 0" not in device.commands
    device.pending.clear()
    device.preload_frame_table(requested)
    assert len(device.command_lines[2]) == 21
    assert all(len(line) == 1 for line in device.command_lines[3:])
    assert_complete_stored_frame(device.frames[2], requested[0])


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


@pytest.mark.parametrize("count", [1, 3, 100])
def test_finite_alignment_uses_bounded_frames_at_ten_hz(count):
    device = FrameDevice()
    channels = frame(pump_enabled=True)["channels"]
    channels["C"]["enabled"] = False
    result = device.apply_recipe({
        "trigger_source": "EXT", "predivider": 1, "frames_engine": "OFF",
        "finite_frame_count": count, "frame_input_frequency_hz": 10.0,
        "start": True, "channels": channels,
    })
    timing = result["timing_table"]
    assert timing["frame_period_s"] == .1
    assert timing["acquisition_frame_count"] == count
    assert len(device.frames) == max(2, count)
    assert sum(stored["CHANnel:QUEue:MODeA"] == "A, ON" for stored in device.frames) == count
    assert sum(stored["CHANnel:QUEue:MODeB"] == "B, ON" for stored in device.frames) == count
    assert all(stored["CHANnel:QUEue:MODeD"] == "D, OFF" for stored in device.frames)
    assert "TRIG:SHOTS 0" in device.commands
    assert not any(command == f"TRIG:SHOTS {count}" for command in device.commands)
    assert device.commands[-3:] == ["TRIG:SOUR EXT", "TFRame:STArt", "START"]


@pytest.mark.parametrize("change", [
    {"finite_frame_count": 0}, {"finite_frame_count": True},
    {"frame_input_frequency_hz": float("nan")}, {"trigger_source": "SYN"},
    {"frame_input_frequency_hz": 100_000.0},
])
def test_invalid_finite_alignment_fails_before_commands(change):
    device = FrameDevice()
    recipe = {"finite_frame_count": 1, "frame_input_frequency_hz": 10.0,
              "trigger_source": "EXT", "predivider": 1,
              "channels": frame(pump_enabled=True)["channels"], **change}
    with pytest.raises(T660ConfigurationError):
        device.apply_recipe(recipe)
    assert not device.commands
