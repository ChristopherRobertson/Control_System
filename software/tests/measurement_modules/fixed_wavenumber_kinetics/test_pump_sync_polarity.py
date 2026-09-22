"""Active-low pump markers: pulse onset, native epochs and poll boundaries."""
import numpy as np
import pytest
from control_app.measurement_modules.fixed_wavenumber_kinetics.pump_sync import falling_sync_ticks
from test_fixed_point_runner_native import scenario


@pytest.mark.parametrize("split", range(9))
def test_low_pulse_leading_edge_survives_every_poll_split(split):
    base = 2**63+15
    ticks = np.asarray([base+i*100 for i in range(8)], dtype=np.uint64)
    # Initial LOW and its return HIGH are not onsets. Subsequent LOW pulses are.
    words = np.asarray([0, 0, 1, 0, 0, 1, 0, 1], dtype=np.uint64) << np.uint64(16)
    first, state = falling_sync_ticks(ticks[:split], words[:split], 16)
    second, state = falling_sync_ticks(ticks[split:], words[split:], 16, state)
    assert first+second == [base+300, base+600]
    assert state == 1


@pytest.mark.parametrize("level", [0, 1])
def test_constant_level_is_not_a_pump(level):
    ticks = np.arange(10, dtype=np.uint64)
    assert falling_sync_ticks(ticks, np.full(10, level << 16, dtype=np.uint64), 16)[0] == []


def test_runner_records_onset_not_return_to_high(tmp_path):
    runner, op, plan, devices = scenario(tmp_path, settings={"pump_shots": 3,
        "shot_delay_s": .1, "event_budget": 3, "post_observation_s": .1})
    record = runner.run(op, plan)
    assert record["status"] == "complete", record.get("error")
    event = record["events"][0]
    actual = [(tick-devices[0].epoch)/devices[0].clockbase_hz for tick in event["pump_timestamps"]]
    np.testing.assert_allclose(actual, devices[0].pumps, atol=1/plan.resolved["timing_rate_sps"])
    assert event["pump_marker_edge"] == "falling"
    assert record["analysis"]["events"][0]["pump_marker_edge"] == "falling"
    assert devices[0].dispatched == 1


@pytest.mark.parametrize("shots", [1, 3])
@pytest.mark.parametrize("fire_polarity,q_polarity", [("negative", "negative"), ("positive", "negative"), ("positive", "positive")])
def test_disabled_and_terminal_frames_preserve_pump_idle_polarity(shots, fire_polarity, q_polarity):
    from control_app.measurement_modules.fixed_wavenumber_kinetics.timing import compile_timing
    program = compile_timing(pre_observation_s=.0005, post_observation_s=.0005,
        input_frequency_hz=2e6, fire_delay_s=0., q_switch_delay_s=.00025,
        fire_width_s=150e-9, q_switch_width_s=150e-9, pump_shots=shots,
        fire_polarity=fire_polarity, q_switch_polarity=q_polarity)
    # Includes loading the first frame under STOP, inter-shot OFF frames,
    # and the terminal frame. None may change either channel's idle level.
    for channel, polarity in (("A", fire_polarity), ("B", q_polarity)):
        assert {frame["channels"][channel]["polarity"] for frame in program.frames} == {polarity}
        assert sum(frame["channels"][channel]["enabled"] for frame in program.frames) == shots
    assert not any(row["enabled"] for row in program.frames[-1]["channels"].values())


def test_extra_sync_does_not_expand_requested_window_or_plot_as_two_shots(tmp_path):
    from matplotlib.figure import Figure
    from test_fixed_point_processing_retention import record, stream
    from control_app.measurement_modules.fixed_wavenumber_kinetics.persistence import NativeChunkWriter, read_native_chunk
    from control_app.measurement_modules.fixed_wavenumber_kinetics.processing import analyze_run
    from control_app.measurement_modules.fixed_wavenumber_kinetics.widgets import TraceRenderer
    ticks = np.arange(40001, dtype=np.uint64)
    with NativeChunkWriter(tmp_path) as writer:
        ref = writer.append({"sample": stream(ticks, np.ones(len(ticks))), "clockbase_hz": 1000000}, event_index=0, position_index=0)
    data = record(mode="single", run_directory=str(tmp_path), native_chunks=[ref], kind="measurement", status="failed",
        events=[{"event_index": 0, "position_index": 0, "position_cm1": 1945, "expected_pump_count": 1,
                 "original_pump_timestamp": 500, "pump_timestamps": [500, 38040], "clockbase_hz": 1000000}])
    data["settings"].update(pre_observation_s=.0005, post_observation_s=.0005, sample_rate_sps=1000000)
    analysis = analyze_run(data)
    event = analysis["events"][0]
    assert event["analysis_window_s"] == [-.0005, .0005]
    assert event["pump_timestamps"] == [500,38040]
    assert event["recovery_fit"]["status"] == "observed_pump_count_mismatch"
    assert not analysis["aggregates"]
    figure = Figure()
    TraceRenderer().draw(figure, {**data, "analysis": analysis})
    assert not figure.axes[0].lines
    assert "1 pump shots requested; 2 sync pulses observed" in figure.axes[0].texts[0].get_text()
    assert len(read_native_chunk(tmp_path, ref)["sample"]["timestamp"]) == 40001
