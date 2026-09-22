"""Continuous multi-shot trials, native pre-pump support and display contracts."""
from dataclasses import replace
import numpy as np
import pytest
from test_fixed_point_runner_native import scenario
from test_fixed_kinetics_planner import recipe, profile_case
from control_app.measurement_modules.fixed_wavenumber_kinetics.planner import build_plan
from control_app.measurement_modules.fixed_wavenumber_kinetics.processing import aggregate_events
from control_app.measurement_modules.fixed_wavenumber_kinetics.timing import TimingError


def test_finite_shot_train_has_exact_pre_and_post_intervals():
    timing = recipe(pre_observation_s=.025, post_observation_s=.05, pump_shots=3, shot_delay_s=.1)
    assert timing.pump_command_offsets_s == pytest.approx([.025, .125, .225])
    assert timing.duration_s == pytest.approx(.275)
    for channel, expected in (("A", [.024, .124, .224]), ("B", [.025, .125, .225])):
        edges = [f["offset_s"]+float(f["channels"][channel]["delay"][:-1]) for f in timing.frames if f["channels"][channel]["enabled"]]
        assert edges == pytest.approx(expected)
    assert not any(v["enabled"] for v in timing.frames[-1]["channels"].values())
    with pytest.raises(TimingError, match="10 Hz"):
        recipe(pump_shots=2, shot_delay_s=.099)
    assert recipe(pre_observation_s=.7, pump_shots=7).expected_pump_count == 7


def test_continuous_recording_trials_average_and_retain_originals(tmp_path):
    runner, op, plan, devices = scenario(tmp_path, settings={"pump_shots": 3, "shot_delay_s": .1,
        "events_per_position": 2, "event_budget": 6, "pre_observation_s": .1, "post_observation_s": .1})
    record = runner.run(op, plan)
    assert record["status"] == "complete", record.get("error")
    assert devices[0].dispatched == 2 and len(devices[0].pumps) == 6
    assert np.all(np.diff(devices[0].pumps) >= .1-1e-9)
    assert len(record["events"]) == 2
    for event in record["events"]:
        assert len(event["pump_timestamps"]) == 3
        assert (event["original_pump_timestamp"]-event["first_native_timestamp"])/event["clockbase_hz"] >= .1
        assert (event["last_native_timestamp"]-event["pump_timestamps"][-1])/event["clockbase_hz"] == pytest.approx(.1, abs=.006)
    assert {r["kind"] for r in record["native_chunks"]} == {"baseline", "continuous_trial"}
    assert len(record["analysis"]["aggregates"]) == 1
    from control_app.measurement_modules.fixed_wavenumber_kinetics.persistence import export_trial_mean_csv
    import csv
    target = export_trial_mean_csv(record, tmp_path/"mean.csv")
    with target.open() as stream:
        rows = list(csv.DictReader(stream))
    assert rows and max(int(row["trial_count"]) for row in rows) == 2
    assert max(record["analysis"]["aggregates"][0]["valid_event_count"]) == 2
    assert record["analysis"]["events"][0]["recovery_fit"]["status"] == "multi_shot_model_required"


def test_nonstationary_pre_pump_data_retained_without_delaying_shots(tmp_path):
    runner, op, plan, devices = scenario(tmp_path, mode="single", faults={"baseline_drift_per_s": 1.})
    result = runner.run(op, plan)
    assert result["status"] == "complete"
    assert "nonstationary_pre_pump_baseline" in result["events"][0]["quality_flags"]
    assert plan.settings.pre_observation_s <= devices[0].pumps[0] <= plan.settings.pre_observation_s + .02
    assert result["events"][0]["stream_ready_before_dispatch"]


def test_trial_average_equal_weight_with_clock_jitter_and_gap():
    events = [{"event_index": i, "position_cm1": 1940., "time_s": np.arange(6)*.1+i*.001,
        "delta_absorbance": np.full(6, float(i+1)), "gap_mask": np.array([False, False, True, False, False, False]),
        "quality_flags": ["gap"], "equivalent_state": False} for i in range(2)]
    result = aggregate_events(events)["aggregates"][0]
    assert np.isnan(result["mean_delta_absorbance"]).any()
    np.testing.assert_allclose(result["mean_delta_absorbance"][np.isfinite(result["mean_delta_absorbance"])], 1.5)
    assert not result["equivalent_state_verified"]


def test_units_preserve_seconds_and_shot_delay_enablement(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from control_app.measurement_modules.fixed_wavenumber_kinetics.widgets import SettingsEditor
    app = QApplication.instance() or QApplication([])
    editor = SettingsEditor("single")
    assert not editor.fields["shot_delay_s"].isEnabled()
    editor.fields["pump_shots"].setValue(2)
    assert editor.fields["shot_delay_s"].isEnabled()
    editor.time_units.setCurrentText("µs")
    assert editor.fields["shot_delay_s"].minimum() == 100000
    editor.fields["pre_observation_s"].setValue(500)
    values = editor.values()
    assert values["settings"]["pre_observation_s"] == pytest.approx(.0005)
    editor.apply(values)
    assert editor.fields["pre_observation_s"].value() == 500
    editor.time_units.setCurrentText("s")
    assert editor.fields["pre_observation_s"].value() == pytest.approx(.0005)
    editor.deleteLater()


@pytest.mark.parametrize("key,good,bad", [("current",[250,1000],[249,1001]), ("width",[21,1005],[20,1006]), ("wavenumbers",[[1639,2077]],[[1638],[2078]])])
def test_shared_limits_exact_endpoints(key, good, bad):
    from control_app.measurement_host.laser_settings import validate_mircat_limits
    for value in good:
        validate_mircat_limits(**{key:value})
    for value in bad:
        with pytest.raises(ValueError):
            validate_mircat_limits(**{key:value})


def test_estimate_counts_trial_capture_once():
    settings, evidence = profile_case()
    plan = build_plan(replace(settings, pump_shots=3, shot_delay_s=.1, events_per_position=2, event_budget=6), evidence=evidence)
    assert plan.ready, plan.validation_errors
    assert plan.estimates["capture_s"] == pytest.approx(2*(1+.2+10))
    assert plan.resolved["integration_window_s"] == [0.,10.2]


def test_auto_hf2_responds_to_timescale_and_preserves_each_override():
    settings, evidence = profile_case()
    choices = {"orders":[1,2,4,8], "rates_sps":[1000.,10000.,100000.],
        "timeconstants_by_order":{4:[1e-6,1e-5,1e-4,1e-3]}}
    evidence["operating_profile"]["hf2_choices"] = {"sample":choices}
    evidence["operating_profile"]["maximum_aggregate_rate_sps"] = 700000.
    slow = build_plan(settings, evidence=evidence)
    fast = build_plan(replace(settings, pre_observation_s=.001, post_observation_s=.001), evidence=evidence)
    assert fast.resolved["sample"]["timeconstant_s"] < slow.resolved["sample"]["timeconstant_s"]
    override = build_plan(replace(settings, sample_rate_sps=10000.), evidence=evidence)
    assert override.resolved["sample"]["rate_sps"] == 10000.
    assert override.resolved["sample"]["timeconstant_s"] == slow.resolved["sample"]["timeconstant_s"]


def test_summary_has_shared_instrument_rows_and_explicit_estimate():
    from control_app.measurement_host.experiment_summary import summary_rows, remaining_text
    settings, evidence = profile_case()
    plan = build_plan(settings, evidence=evidence)
    rows = dict(summary_rows(plan, [("Sequence", "one trial")]))
    assert {"MIRcat settings","Nd:YAG settings","Selected HF2LI","Effective resolution","Preflight capacity","Estimated completion"} <= rows.keys()
    assert "2.1 MHz / 142 ns" in rows["MIRcat settings"]
    assert "still running" in remaining_text(1., 2.)
    from control_app.measurement_modules.steady_state_slow_scan.settings import SlowScanSettings
    from control_app.measurement_modules.steady_state_slow_scan.planner import build_plan as slow_plan
    rows = dict(summary_rows(slow_plan(SlowScanSettings()), [], slow_scan=True))
    assert "Nd:YAG settings" not in rows
    assert "Estimated completion" in rows
