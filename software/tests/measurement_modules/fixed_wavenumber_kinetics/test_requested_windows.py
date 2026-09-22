"""Regression coverage for short windows and buffered, delayed marker delivery."""
from copy import deepcopy
import numpy as np
import pytest
from matplotlib.figure import Figure
from control_app.measurement_host import ContextFactory
from control_app.measurement_modules.fixed_wavenumber_kinetics.simulation import simulation_profile, SimulatedDevices
from control_app.measurement_modules.fixed_wavenumber_kinetics.planner import build_plan
from control_app.measurement_modules.fixed_wavenumber_kinetics.runner import Runner
from control_app.measurement_modules.fixed_wavenumber_kinetics.widgets import TraceRenderer
from control_app.measurement_modules.fixed_wavenumber_kinetics.processing import analyze_run
from test_fixed_kinetics_planner import recipe


def test_short_pre_window_does_not_shorten_fire_lead_in():
    timing = recipe(pre_observation_s=100e-6, post_observation_s=500e-6,
        input_frequency_hz=2e6, fire_delay_s=0., q_switch_delay_s=250e-6,
        fire_width_s=150e-9, q_switch_width_s=150e-9)
    assert timing.requested_pre_observation_s == 100e-6
    assert timing.selected_pre_observation_s == 250e-6
    assert timing.duration_s == pytest.approx(750e-6)
    edges = {ch: [frame["offset_s"]+float(frame["channels"][ch]["delay"][:-1])
        for frame in timing.frames if frame["channels"][ch]["enabled"]] for ch in "AB"}
    assert edges["B"][0]-edges["A"][0] == pytest.approx(250e-6)


def buffered_run(tmp_path, *, shots=1, mode="single"):
    profile = simulation_profile(mode)
    settings = profile["settings"]
    settings.update(positions=[{"wavenumber_cm1": w} for w in (1946,1945,1944,1943)],
        pre_observation_s=100e-6, post_observation_s=500e-6, events_per_position=2,
        pump_shots=shots, shot_delay_s=100000*1e-6, event_budget=8*shots, time_unit="µs")
    for data in (profile["configuration"]["fixed_wavenumber_kinetics"], profile["evidence"]["operating_profile"]):
        for role in ("sample", "reference"):
            data[role].update(rate_sps=100000., timeconstant_s=1e-6)
            data[role+"_supported_rates_sps"] = [100000.]
        data["timing_rate_sps"] = 100000.
        data["timing_supported_rates_sps"] = [100000.]
        data["timing"]["q_switch_delay_s"] = 250e-6
    context = ContextFactory(configuration_provider=lambda: profile["configuration"], save_root_provider=lambda: tmp_path).for_experiment("fixed_wavenumber_kinetics").for_mode(mode)
    plan = build_plan(settings, profile["configuration"], profile["evidence"])
    assert plan.ready, (plan.validation_errors, plan.readiness_items)
    operation = context.begin_operation(settings=settings, hardware=False)
    class BufferedDevices(SimulatedDevices):
        def start_event(self, program):
            super().start_event(program)
            n = len(program["pump_command_offsets_s"])
            # First reads exceed the whole requested short window but precede
            # the marker. This models queued data/dispatch and transfer latency.
            self.pumps[-n:] = [p+.03 for p in self.pumps[-n:]]
        def read(self, duration_s):
            return super().read(min(.01, duration_s) if duration_s > .01 else .01)
    devices = []
    def factory(ctx, op):
        device = BufferedDevices(ctx, op)
        devices.append(device)
        return device
    record = Runner(context, device_factory=factory).run(operation, plan)
    assert record["status"] == "complete", record.get("error", record.get("analysis_error"))
    return record, devices[0]


@pytest.mark.parametrize("shots,mode", [(1,"single"), (3,"dual")])
def test_buffered_capture_all_positions_trials_and_post_last_shot(tmp_path, shots, mode):
    record, device = buffered_run(tmp_path, shots=shots, mode=mode)
    assert device.dispatched == 8
    assert [e["position_cm1"] for e in record["events"]] == [1946,1946,1945,1945,1944,1944,1943,1943]
    assert len(record["analysis"]["aggregates"]) == 4
    for event in record["analysis"]["events"]:
        assert len(event["pump_timestamps"]) == shots
        markers = event["measured_pump_time_s"]
        if shots > 1:
            assert min(np.diff(markers)) >= .1-1e-5
        assert min(event["time_s"]) >= -100e-6-1e-12
        assert max(event["time_s"]) <= markers[-1]+500e-6+1e-12
        assert max(event["time_s"]) >= markers[-1]+490e-6-1e-12
        assert event["native_poll_padding_excluded"]
    for aggregate in record["analysis"]["aggregates"]:
        assert len(aggregate["event_indices"]) == 2
        assert max(aggregate["valid_counts"]["sample"]) == 2
        assert max(aggregate["valid_counts"]["ratio"]) == 2
    renderer = TraceRenderer()
    renderer.quantity = "ratio"
    figure = Figure()
    renderer.draw(figure, record)
    assert figure.axes[-1].get_xlim() == pytest.approx([-100, (shots-1)*100000+500], abs=11)
    assert "Mean of 2 trials" in figure.axes[0].get_title()
    assert len([text for text in figure.axes[0].texts if "Pump" in text.get_text()]) == shots
    expected = record["analysis"]["aggregates"][0]["means"]["sample"]
    np.testing.assert_allclose(figure.axes[0].lines[0].get_ydata(), expected, equal_nan=True)
    # Large buffered lead-in must not consume a short window's display budget.
    limited = analyze_run(record, max_points=800, max_points_per_event=100)
    if shots == 1:
        assert all(e["analysis_stride"] == 1 and e["analysis_count"] >= 59 for e in limited["events"])


def test_missing_marker_has_diagnostic_instead_of_misleading_time_axis():
    renderer = TraceRenderer()
    figure = Figure()
    renderer.draw(figure, {"analysis": {"events": [{"position_cm1": 1946,
        "expected_pump_count": 1, "original_pump_timestamp": None, "time_s": [0,.01]}]}})
    assert not figure.axes[0].lines
    assert "Pump sync was not observed" in figure.axes[0].texts[0].get_text()


def test_wavenumber_selector_limits_trial_selection(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from control_app.measurement_modules.fixed_wavenumber_kinetics.widgets import FixedPointPanel
    app = QApplication.instance() or QApplication([])
    context = ContextFactory(save_root_provider=lambda: tmp_path).for_experiment("fixed_wavenumber_kinetics").for_mode("single")
    panel = FixedPointPanel(context)
    events = [{"position_cm1": wave, "wavenumber_cm1": wave, "time_s": [0.,.001],
        "sample": [1.,1.], "ratio": [1.,1.], "delta_absorbance": [0.,0.]} for wave in (1946,1946,1945,1945,1944,1944,1943,1943)]
    panel.show_record({"mode": "single", "analysis": {"events": events}})
    assert panel.wavenumber.count() == 4
    panel.wavenumber.setCurrentIndex(3)
    assert panel.renderer.event_index == 6
    assert panel.event_control.coordinates == (1.,2.)
    panel.event_control.set_index(1)
    assert panel.renderer.event_index == 7
    panel.deleteLater()


def test_detector_export_uses_raw_trial_mean(tmp_path):
    import csv
    from control_app.measurement_modules.fixed_wavenumber_kinetics.persistence import export_detector_csv
    data = {"mode": "single", "status": "complete", "analysis": {"aggregates": [{
        "position_cm1": 1945., "time_s": [-.0005,0.,.0005],
        "means": {"sample": [.08,.07,.075], "delta_absorbance": [0.,.1,.05]},
        "valid_counts": {"sample": [2,2,2]}}]}}
    path = export_detector_csv(data, tmp_path/"trace.csv")
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    assert [float(r["sample_magnitude_v"]) for r in rows] == [.08,.07,.075]
    assert all(r["trial_count"] == "2" for r in rows)
    assert "mean_delta_absorbance" not in rows[0]
