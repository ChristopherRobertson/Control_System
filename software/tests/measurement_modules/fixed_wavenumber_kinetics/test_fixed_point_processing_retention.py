"""Known-truth science and exact-retention tests without hardware or Qt."""
import json
from threading import Event

import numpy as np
import pytest

from control_app.measurement_modules.fixed_wavenumber_kinetics.persistence import (
    NativeChunkWriter, RecordCompatibilityError, export_stroboscopic_handoff, export_analysis_csv,
    load_run, load_analysis_inputs, read_native_chunk, recover_native_references, save_run,
)
from control_app.measurement_modules.fixed_wavenumber_kinetics.processing import (
    AnalysisCancelled, aggregate_events, align_detectors, analyze_run,
    baseline_statistics, compatible_record, fit_recovery, normalize_trace,
    recovery_evidence, response_convolved_exponential, time_from_ticks,
)


def stream(ticks, values, **flags):
    return {"timestamp": np.asarray(ticks, np.uint64), "x": np.asarray(values, float),
            "y": np.zeros(len(values)), **flags}


def record(mode="dual", **kwargs):
    return {"experiment_id": "fixed_wavenumber_kinetics", "schema_version": "1.0", "mode": mode,
            "condition_id": "room-a", "settings": {"condition_id": "room-a", "sample_id": "sample-a", "sample_rate_sps": 100.},
            **kwargs}


def test_fixed_native_dtype_precision_nan_and_interrupted_journal_recovery(tmp_path):
    ticks = np.asarray([2**63 + 19, 2**63 + 29, 2**63 + 39], np.uint64)
    x = np.asarray([np.nextafter(1., 2.), np.nan, -0.], np.float64)
    chunk = {"sample": {"timestamp": ticks, "x": x, "y": np.asarray([1, 2, 3], np.float32)},
             "clockbase_hz": 210000000, "optical_marker": np.uint64(2**63 + 21)}
    with NativeChunkWriter(tmp_path) as writer:
        first = writer.append(chunk, event_index=0, kind="baseline")
        second = writer.append(chunk, event_index=1, kind="observation")
    reread = read_native_chunk(tmp_path, first)
    for name in chunk["sample"]:
        assert reread["sample"][name].dtype == chunk["sample"][name].dtype
        assert reread["sample"][name].tobytes() == chunk["sample"][name].tobytes()
    assert int(reread["optical_marker"]) == 2**63 + 21
    assert first["path"] != second["path"]
    assert len(recover_native_references(tmp_path)) == 2
    relative = time_from_ticks(ticks, 2**63 + 29, 10)
    np.testing.assert_array_equal(relative, [-1, 0, 1])


def test_fixed_storage_failure_retains_previous_and_partial_chunk(tmp_path, monkeypatch):
    writer = NativeChunkWriter(tmp_path)
    previous = writer.append({"sample": stream([1, 2], [1, 2])})
    def fail(*args, **kwargs):
        raise OSError("Disk full")
    monkeypatch.setattr(np, "savez", fail)
    with pytest.raises(OSError, match="Disk full"):
        writer.append({"sample": stream([3, 4], [3, 4])})
    writer.close()
    assert (tmp_path / previous["path"]).exists()
    assert len(list((tmp_path / "native").glob("*.pending"))) == 1


def test_fixed_run_schema_mode_and_inert_metadata_diagnostics(tmp_path):
    data = record()
    path = save_run(data, tmp_path)
    assert load_run(path, mode="dual", condition_id="room-a")["mode"] == "dual"
    with pytest.raises(RecordCompatibilityError, match="detector mode"):
        load_run(path, mode="single")
    assert load_run(path, condition_id="different annotation")["condition_id"] == "room-a"
    with pytest.raises(FileExistsError):
        save_run(data, tmp_path)
    changed = {**data, "settings": {**data["settings"], "diagnostic_hash": "changed"}}
    assert compatible_record(data, changed)[0]
    changed["settings"]["sample_id"] = "other"
    assert compatible_record(data, changed)[0]
    changed["settings"]["sample_rate_sps"] = 200
    assert "sample_rate_sps" in "; ".join(compatible_record(data, changed)[1])


def test_fixed_matched_ticks_missing_reference_and_clipping_unlock():
    sample = stream([100, 110, 120, 130, 140], [4, 4, 4, 4, 4], clipped=[False, False, True, False, False])
    reference = stream([100, 120, 130, 140], [2, 2, 0, 2], unlocked=[False, False, False, True])
    result = normalize_trace(sample, reference, q0=2)
    np.testing.assert_array_equal(np.isfinite(result["ratio"]), [True, False, False, False, False])
    assert result["ratio"][0] == 2
    assert result["delta_absorbance"][0] == 0
    assert "unmatched_reference_support" in result["quality_flags"]
    assert "missing_reference" in normalize_trace(sample, None, q0=2)["quality_flags"]
    assert not align_detectors(sample, None)["valid"].any()


def test_fixed_dual_q_q0_absolute_only_with_measured_b_and_covariance():
    sample, ref = stream([1, 2], [4, 2]), stream([1, 2], [2, 2])
    result = normalize_trace(sample, ref, q0=2, sample_variance=.04, reference_variance=.01, covariance=.01)
    np.testing.assert_allclose(result["delta_absorbance"], [0, np.log10(2)])
    assert result["absolute_absorbance"] is None
    assert result["ratio_label"] == "Reference-normalized signal Q = S/R"
    assert result["ratio_variance"][0] == pytest.approx(.01)
    absolute = normalize_trace(sample, ref, q0=2, background_factor=4, background_record_id="measured-path-balance-1")
    np.testing.assert_allclose(absolute["absolute_absorbance"], -np.log10(np.asarray([2, 1]) / 4))
    assert normalize_trace(sample, ref, q0=2, background_factor=4)["absolute_absorbance"] is None


def test_fixed_single_blank_and_stationarity_controls():
    t = np.linspace(-2, -0.01, 400)
    rng = np.random.default_rng(22)
    stationary = 2 + rng.normal(0, .001, len(t))
    assert baseline_statistics(t, stationary)["stationary"]
    assert not baseline_statistics(t, 2 + .05 * t)["stationary"]
    data = stream(np.arange(len(t)), stationary)
    missing = normalize_trace(data, mode="single", time_s=t)
    assert not missing["quality_flags"]
    assert missing["normalization_kind"] == "observed_sample_baseline"
    assert np.isnan(missing["reference"]).all()
    assert missing["q0"] is None
    assert missing["s0"] == pytest.approx(np.mean(stationary))
    np.testing.assert_allclose(missing["ratio"], stationary / np.mean(stationary))
    valid = normalize_trace(data, mode="single", blank_mean=4, time_s=t)
    assert valid["baseline"]["stationary"]
    assert abs(np.nanmean(valid["delta_absorbance"])) < 1e-5


def test_fixed_known_recovery_drift_measured_convolution_and_uncertainty():
    t = np.linspace(-1, 10, 1200)
    response = {"record_id": "qualified-response", "measured": True, "time_constant_s": .08, "resolution_s": .15}
    rng = np.random.default_rng(773)
    truth = -.025 * response_convolved_exponential(t, 1.7, response) + .001 + .0002 * t
    y = truth + rng.normal(0, .00008, len(t))
    fit = fit_recovery(t, y, response, standard_error=np.full(len(t), .00008))
    assert fit["status"] == "apparent_recovery_fit"
    assert fit["tau_s"] == pytest.approx(1.7, rel=.03)
    assert fit["amplitude"] == pytest.approx(-.025, rel=.01)
    assert fit["drift_per_s"] == pytest.approx(.0002, abs=.000005)
    assert fit["parameter_covariance"].shape == (4, 4)
    assert fit["residual_rms"] < .0001
    assert np.all(fit["standard_errors"] > 0)
    assert fit_recovery(t, y, None)["status"] == "unresolved_response"


def test_fixed_no_pump_off_band_control_is_not_recovery_claim():
    t = np.linspace(-1, 10, 600)
    response = {"record_id": "qualified-response", "measured": True, "time_constant_s": .08}
    y = np.random.default_rng(42).normal(0, .0001, len(t))
    fit = fit_recovery(t, y, response)
    assert fit["status"] == "unresolved_apparent_component"
    summary = aggregate_events([{"event_index": 0, "kind": "off_band", "equivalent_state": True}])
    assert not summary["aggregates"]
    assert len(summary["excluded"]) == 1


def test_fixed_incomplete_recovery_is_censored_and_no_assumed_reset():
    t = np.linspace(0, 100, 2000)
    y = -.1 * np.exp(-t / 1000)
    evidence = recovery_evidence(t, y)
    assert not evidence["recovered"]
    assert evidence["status"] == "incomplete_recovery_right_censored"
    assert evidence["remaining_fixed_point_fraction"] > .9
    assert evidence["observation_limit_s"] == 100
    event = {"event_index": 0, "time_s": t, "delta_absorbance": y, "recovery": evidence,
             "kind": "measurement", "equivalent_state": False}
    assert not aggregate_events([event])["aggregates"]


def test_fixed_bounded_chunk_analysis_preserves_pump_epoch_and_gap(tmp_path):
    base = 2**63 + 700
    refs = []
    with NativeChunkWriter(tmp_path) as writer:
        for index in range(10):
            ticks = np.arange(base + index * 1000, base + (index + 1) * 1000, dtype=np.uint64)
            if index == 5:
                ticks = ticks[20:]
            chunk = {"sample": stream(ticks, np.ones(len(ticks)) * 2), "reference": stream(ticks, np.ones(len(ticks))),
                     "clockbase_hz": 100, "event_index": 0}
            refs.append(writer.append(chunk, event_index=0, position_index=0))
    data = record(run_directory=str(tmp_path), native_chunks=refs, kind="measurement", events=[{
        "event_index": 0, "expected_pump_count": 1, "original_pump_timestamp": base + 1000,
        "pump_timestamps": [base + 1000], "clockbase_hz": 100,
        "baseline": {"stationary": True, "mean": 2., "std": 0., "count": 1000}, "position_cm1": 1934}])
    analysis = analyze_run(data, max_points=200, max_points_per_event=100)
    event = analysis["events"][0]
    assert event["analysis_count"] <= 100
    assert event["native_count"] == 9980
    assert event["original_pump_timestamp"] == base + 1000
    assert event["time_s"][0] == -10
    assert event["time_s"][-1] == pytest.approx(89.99)
    assert "native_timestamp_gap" in event["quality_flags"]
    assert np.isnan(event["delta_absorbance"]).any()
    assert event["baseline"]["native_streaming_statistics"]
    assert event["baseline"]["count"] == 1000


def test_fixed_analysis_cancellation_and_standalone_file_handoff(tmp_path):
    cancel = Event()
    cancel.set()
    with pytest.raises(AnalysisCancelled):
        analyze_run(record(), cancel=cancel)
    with pytest.raises(AnalysisCancelled):
        fit_recovery([0], [0], None, cancel=cancel)
    path = export_stroboscopic_handoff(record(run_id="discovery-1"), tmp_path / "handoff.json", selected_times_s=[-1, 10])
    exported = json.loads(path.read_text())
    assert exported["record_kind"] == "fixed_point_discovery_handoff"
    assert exported["source_run_id"] == "discovery-1"
    assert "nanosecond" in exported["claim_limit"]
    assert "requires" not in exported
    assert exported["interpretation_considerations"]
    assert "accepted" not in " ".join(exported["interpretation_considerations"])


def test_fixed_aggregation_uses_explicit_equivalence_and_preserves_dose_order():
    times = np.asarray([0., 1., 2.])
    events = [{"event_index": i, "position_cm1": 1934., "time_s": times,
               "delta_absorbance": np.asarray([-.04 + i * .002, -.01, 0.]),
               "equivalent_state": True, "quality_flags": [], "dose": {"value": i + 1, "units": "a.u."},
               "recovery_fit": {"amplitude": -.04 + i * .002}} for i in range(2)]
    summary = aggregate_events(events)
    assert len(summary["aggregates"]) == 1
    np.testing.assert_allclose(summary["aggregates"][0]["mean_delta_absorbance"], [-.039, -.01, 0])
    assert summary["aggregates"][0]["valid_event_count"].tolist() == [2, 2, 2]
    assert summary["order_dose_trends"][1]["dose"]["value"] == 2
    events[1]["equivalent_state"] = False
    assert len(aggregate_events(events)["excluded"]) == 1


def test_fixed_interrupted_reference_recovery_uses_native_clock_order(tmp_path):
    with NativeChunkWriter(tmp_path) as writer:
        late = writer.append({"sample": stream([200, 201], [1, 1])})
        early = writer.append({"sample": stream([100, 101], [1, 1])})
    recovered = recover_native_references(tmp_path)
    assert [reference["path"] for reference in recovered] == [early["path"], late["path"]]


def test_fixed_complete_runner_normalization_recovers_surrogate_truth(tmp_path):
    from control_app.measurement_host import ContextFactory
    from control_app.measurement_modules.fixed_wavenumber_kinetics.planner import build_plan
    from control_app.measurement_modules.fixed_wavenumber_kinetics.runner import Runner
    from control_app.measurement_modules.fixed_wavenumber_kinetics.simulation import simulation_profile
    profile = simulation_profile("dual")
    context = ContextFactory(configuration_provider=lambda: profile["configuration"], save_root_provider=lambda: tmp_path).for_experiment("fixed_wavenumber_kinetics").for_mode("dual")
    plan = build_plan(profile["settings"], profile["configuration"], profile["evidence"])
    operation = context.begin_operation(profile["settings"], hardware=False)
    retained = Runner(context).run(operation, plan)
    assert retained["status"] == "complete"
    event = retained["analysis"]["events"][0]
    assert event["q0"] == pytest.approx(.625)
    assert event["absolute_absorbance"] is None
    assert event["recovery_fit"]["tau_s"] == pytest.approx(.4, rel=.002)
    assert event["recovery_fit"]["amplitude"] == pytest.approx(.015, rel=.002)
    assert not retained["analysis"]["quality_flags"]
    assert len(retained["analysis"]["aggregates"]) == 1


def test_fixed_parent_sources_roundtrip_exact_native_and_no_fallback(tmp_path):
    blank_dir, target_dir = tmp_path / "saved-blank", tmp_path / "saved-observation"
    native = stream([2**63 + 3, 2**63 + 7], [np.nextafter(2., 3.), -0.])
    with NativeChunkWriter(blank_dir) as writer:
        reference = writer.append({"sample": native, "clockbase_hz": 100})
    blank = record("single", run_id="blank-source-1", status="complete", kind="blank", native_chunks=[reference])
    save_run(blank, blank_dir)
    current = record("single", run_id="sample-1", kind="measurement", run_directory=str(target_dir),
                     analysis_inputs={"blank": {"run_id": "blank-source-1", "native_path": "../saved-blank/run.json"}})
    inputs = load_analysis_inputs(current)
    assert inputs["preliminary"] is None
    assert inputs["blank"]["run_id"] == "blank-source-1"
    parent_trace = read_native_chunk(inputs["blank"]["run_directory"], inputs["blank"]["native_chunks"][0])
    for name in native:
        assert parent_trace["sample"][name].tobytes() == native[name].tobytes()
    current["analysis_inputs"]["blank"]["run_id"] = "unrecorded-other-blank"
    with pytest.raises(RecordCompatibilityError, match="run_id"):
        load_analysis_inputs(current)
    current["analysis_inputs"]["blank"]["run_id"] = "blank-source-1"
    current["analysis_inputs"]["blank"]["native_path"] = "../missing-blank/run.json"
    with pytest.raises(RecordCompatibilityError, match="Cannot load explicit blank parent"):
        load_analysis_inputs(current)
    assert load_analysis_inputs(record("single")) == {"blank": None, "preliminary": None}


def test_fixed_parent_mode_and_missing_native_are_explicit_but_metadata_is_inert(tmp_path):
    parent_dir = tmp_path / "parent"
    with NativeChunkWriter(parent_dir) as writer:
        ref = writer.append({"sample": stream([1, 2], [1, 1])})
    parent = record("dual", run_id="prelim-1", kind="preliminary", status="complete", native_chunks=[ref])
    save_run(parent, parent_dir)
    current = record("single", analysis_inputs={"preliminary": {"run_id": "prelim-1", "native_path": str(parent_dir)}})
    with pytest.raises(RecordCompatibilityError, match="detector mode"):
        load_analysis_inputs(current)
    current["mode"] = "dual"
    current["condition_id"] = "different-condition"
    assert load_analysis_inputs(current)["preliminary"]["condition_id"] == "room-a"
    current["condition_id"] = "room-a"
    # Preserve the intentionally incomplete source as its own failed fixture;
    # no native data are deleted to produce this test.
    incomplete_dir = tmp_path / "missing-native-parent"
    save_run({**parent, "native_chunks": [{"path": "native/absent.npz"}]}, incomplete_dir)
    current["analysis_inputs"]["preliminary"]["native_path"] = str(incomplete_dir)
    with pytest.raises(RecordCompatibilityError, match="native observation is unavailable"):
        load_analysis_inputs(current)


def test_fixed_fresh_state_acceptance_preserves_blank_recipe_compatibility():
    blank_plan = {**record("single"), "resolved": {"configuration_id": "geometry-a", "acquisition_purpose": "blank"}}
    sample_plan = {**record("single"), "resolved": {"configuration_id": "geometry-a", "acquisition_purpose": "measurement",
                    "fresh_state_record": {"record_id": "accepted-fresh-state-1", "accepted_by": "Named reviewer"}}}
    assert compatible_record(blank_plan, sample_plan)[0]
    sample_plan["resolved"]["configuration_id"] = "geometry-b"
    assert compatible_record(blank_plan, sample_plan)[0]
    sample_plan["resolved"]["sample"] = {"input_index": 1}
    assert not compatible_record(blank_plan, sample_plan)[0]


def test_fixed_saved_single_run_reanalysis_uses_original_saved_parents(tmp_path):
    from control_app.measurement_host import ContextFactory
    from control_app.measurement_modules.fixed_wavenumber_kinetics.planner import build_plan
    from control_app.measurement_modules.fixed_wavenumber_kinetics.runner import Runner
    from control_app.measurement_modules.fixed_wavenumber_kinetics.simulation import simulation_profile
    profile = simulation_profile("single")
    context = ContextFactory(configuration_provider=lambda: profile["configuration"], save_root_provider=lambda: tmp_path).for_experiment("fixed_wavenumber_kinetics").for_mode("single")
    def acquire(kind, **parents):
        plan = build_plan(profile["settings"], profile["configuration"], profile["evidence"], purpose=kind)
        operation = context.begin_operation(profile["settings"], hardware=False)
        return Runner(context).run(operation, plan, kind=kind, **parents)
    blank = acquire("blank")
    preliminary = acquire("preliminary", blank=blank)
    pumped = acquire("measurement", blank=blank, preliminary=preliminary)
    assert pumped["status"] == "complete"
    loaded = load_run(pumped["run_directory"])
    inputs = load_analysis_inputs(loaded)
    assert inputs["blank"]["run_id"] == blank["run_id"]
    assert inputs["preliminary"]["run_id"] == preliminary["run_id"]
    recomputed = analyze_run(loaded, **inputs)
    original = pumped["analysis"]["events"][0]
    for quantity in ("sample", "ratio", "delta_absorbance"):
        np.testing.assert_array_equal(recomputed["events"][0][quantity], original[quantity])


def _ordinary_raw_record(mode="single"):
    ticks = np.arange(500, dtype=np.uint64) + np.uint64(2**63 + 700)
    time = (np.arange(500) - 100) / 100
    sample_values = 2 + .1 * np.exp(-np.maximum(time, 0) / .5) * (time > 0)
    chunk = {"clockbase_hz": 100, "sample": stream(ticks, sample_values), "event_index": 0}
    if mode == "dual":
        chunk["reference"] = stream(ticks, np.ones(500))
    return {"experiment_id": "fixed_wavenumber_kinetics", "mode": mode, "schema_version": "1.0",
            "kind": "measurement", "settings": {"sample_rate_sps": 100, "pre_observation_s": 1},
            "native_chunks": [chunk], "events": [{"event_index": 0, "position_index": 0, "position_cm1": 1930,
                "expected_pump_count": 1, "pump_timestamps": [int(ticks[100])], "original_pump_timestamp": int(ticks[100]),
                "clockbase_hz": 100, "baseline": {"mean": 2., "std": 0., "count": 100, "stationary": True}}]}


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_fixed_raw_relative_processing_requires_no_profile_or_response_and_annotations_are_inert(mode):
    from copy import deepcopy
    raw = _ordinary_raw_record(mode)
    initial = analyze_run(raw)
    event = initial["events"][0]
    assert not initial["quality_flags"]
    assert np.isfinite(event["ratio"]).all()
    assert np.isfinite(event["delta_absorbance"]).all()
    assert event["recovery_fit"]["status"] == "unresolved_response"
    assert "tau_s" not in event["recovery_fit"]
    annotated = deepcopy(raw)
    annotated["settings"].update(condition_profile="arbitrary-temperature-note", condition_id="optional",
        temperature_k=77, temperature_id="annotation", sample_label="any material", sample_id="optional sample",
        preparation_id="optional preparation", notes="A free text note")
    annotated["condition_id"] = "different annotation"
    annotated["acquisition_response"] = {"timeconstant_s": 1e-9, "measured": False, "record_id": "example-only"}
    assert compatible_record(raw, annotated)[0]
    result = analyze_run(annotated)
    for quantity in ("sample", "ratio", "delta_absorbance"):
        np.testing.assert_array_equal(result["events"][0][quantity], event[quantity])
    assert result["events"][0]["recovery_fit"]["status"] == "unresolved_response"
    assert not result["quality_flags"]


def test_fixed_observed_blank_normalizes_without_qualification_or_metadata_match():
    raw = _ordinary_raw_record("single")
    blank = {**_ordinary_raw_record("single"), "kind": "blank", "status": "complete", "condition_id": "any note"}
    blank["settings"] = {**blank["settings"], "temperature_k": 290, "material": "buffer note", "sample_id": "optional"}
    blank["events"][0]["baseline"] = {"mean": 4., "std": 0., "count": 100, "stationary": True}
    result = analyze_run(raw, blank=blank)
    assert not result["quality_flags"]
    event = result["events"][0]
    assert event["normalization_kind"] == "measured_sequential_blank"
    np.testing.assert_array_equal(event["ratio"], event["sample"] / 4)
    assert event["q0"] == .5
    assert event["recovery_fit"]["status"] == "unresolved_response"


def test_fixed_parent_without_condition_annotation_still_loads_exact_native(tmp_path):
    native = stream([1, 2], [1.23456789, 2.34567891])
    with NativeChunkWriter(tmp_path / "parent") as writer:
        ref = writer.append({"sample": native})
    parent = {"experiment_id": "fixed_wavenumber_kinetics", "schema_version": 1, "mode": "single",
              "run_id": "plain-parent", "kind": "blank", "status": "complete", "native_chunks": [ref]}
    save_run(parent, tmp_path / "parent")
    current = {"experiment_id": "fixed_wavenumber_kinetics", "schema_version": 1, "mode": "single",
               "analysis_inputs": {"blank": {"run_id": "plain-parent", "native_path": str(tmp_path / "parent")}}}
    loaded = load_analysis_inputs(current)["blank"]
    actual = read_native_chunk(loaded["run_directory"], loaded["native_chunks"][0])
    assert actual["sample"]["x"].tobytes() == native["x"].tobytes()


def test_fixed_optional_annotation_changes_do_not_hide_actual_data_incompatibility(tmp_path):
    raw = _ordinary_raw_record("single")
    changed = {**raw, "settings": {**raw["settings"], "temperature_k": 77, "sample_rate_sps": 200}}
    assert not compatible_record(raw, changed)[0]
    with pytest.raises(RecordCompatibilityError, match="mode mismatch"):
        save_run({**raw, "plan": {"mode": "dual"}}, tmp_path)


def test_fixed_saved_and_csv_labels_distinguish_raw_blank_and_sample_relative_signal(tmp_path):
    import csv
    raw = _ordinary_raw_record("single")
    raw["analysis"] = analyze_run(raw)
    path = export_analysis_csv(raw, tmp_path / "relative.csv")
    with path.open(newline="", encoding="utf-8") as stream:
        first = next(csv.DictReader(stream))
    assert first["normalization_kind"] == "observed_sample_baseline"
    assert "S/S0" in first["ratio_label"]
    assert first["delta_absorbance_label"] == "Relative log signal -log10(S/S0)"
    blank = {**raw, "kind": "blank"}
    event = analyze_run(blank)["events"][0]
    assert event["normalization_kind"] == "raw_blank"
    assert np.isnan(event["ratio"]).all()
    assert "no sample ratio" in event["ratio_label"]
    flags = aggregate_events([{**raw["analysis"]["events"][0], "equivalent_state": True, "quality_flags": ["gap"]}])
    assert flags["excluded"][0]["reason"] == "Quality flags; shown individually"
