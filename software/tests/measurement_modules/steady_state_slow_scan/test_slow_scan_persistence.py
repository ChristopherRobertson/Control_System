"""Schema isolation, exact native retention and independent sample acceptance."""
from dataclasses import replace
from pathlib import Path
import json
import shutil

import numpy as np
import pytest

from control_app.measurement_host.interchange import load_sample_selection
from control_app.measurement_modules.steady_state_slow_scan.persistence import (
    export_run, export_selection, load_plan, load_run, save_plan, save_run,
)
from control_app.measurement_modules.steady_state_slow_scan.processing import (
    FitSettings, NativeSweep, ProcessedSpectrum, fit_spectrum, process_sweep,
)


def settings(mode="single"):
    return {"mode": mode, "condition": {"condition_id": "rt_mbco", "sample_id": "sample-A",
        "preparation_id": "prep-A", "cell_id": "cell-A", "position_id": "pos-1",
        "temperature_id": "temperature-A", "configuration_id": "config-A", "temperature_k": 294.1},
        "fit_peak_count": 1, "requested_resolution_cm1": .1}


def retained_run(mode="single"):
    x = np.linspace(1939, 1949, 121)
    y = .01 + .001 * (x - 1944) + .2 * np.exp(-.5 * ((x-1944.2)/.65)**2)
    raw = NativeSweep("sweep-1", mode, "rt_mbco", "qcl-1", "forward", 0,
        axis_cm1=x.astype(">f8"), sample=y.astype(np.float32),
        timestamps_s=np.arange(len(x), dtype=np.uint64) + np.uint64(2**60),
        reference=np.ones(len(x)) if mode == "dual" else None,
        metadata={"original_signed_zero": np.array([-0., 0., np.nan], dtype=np.float64),
                  "integer_tick_epoch": np.uint64(2**61)})
    quantity = "sequential_blank_absorbance" if mode == "single" else "reference_normalized_ratio"
    signal = y if mode == "single" else 1-y
    spectrum = ProcessedSpectrum(raw, x, signal, np.full(len(x), 1e-8), np.ones(len(x), bool), quantity,
        provenance={"axis_calibration_id": "axis-A", "axis_uncertainty_cm1": .02})
    fitted = fit_spectrum(spectrum, FitSettings(1))
    return {"run_id": "run-A", "mode": mode, "condition_id": "rt_mbco", "status": "completed",
        "kind": "measurement", "settings": settings(mode), "started_utc": "2026-09-10T00:00:00Z",
        "sweeps": [raw], "spectra": [spectrum], "fits": [fitted],
        "readbacks": {"clipped": False, "native_clock": np.array([2**63+11], dtype=np.uint64)},
        "restoration": {"safe_verified": True, "errors": []},
        "partial_native_records": [{"sample": raw.sample}], "rejected": [{"reason": "test", "values": np.array([np.nan])}]}


def accepted_arguments(run):
    peak = run["fits"][0].peaks[0]
    return {"windows": [{"lower_cm1": peak.center_cm1-1, "upper_cm1": peak.center_cm1+1,
                         "center_cm1": peak.center_cm1, "uncertainty_cm1": peak.center_uncertainty_cm1,
                         "label": "selected band"}],
            "accepted_by": "Named spectroscopy reviewer", "acceptance": {"review_complete": True,
                "sample_state_accepted": True, "configuration_id": "config-A",
                "rationale": "Independent band fit, matched condition and reviewed native repeatability"}}


def test_plan_roundtrip_includes_derived_schedule_and_rejects_other_instances(tmp_path):
    original = settings()
    path = save_plan(tmp_path / "plan.json", original, plan={"frames": [{"pump_fire": False}], "actual_resolution_cm1": .11})
    assert load_plan(path, expected_mode="single", expected_condition_id="rt_mbco") == original
    assert json.loads(path.read_text())["derived_plan"]["frames"][0]["pump_fire"] is False
    with pytest.raises(ValueError, match="mode mismatch"):
        load_plan(path, expected_mode="dual")
    assert load_plan(path, expected_condition_id="different optional annotation") == original
    with pytest.raises(FileExistsError):
        save_plan(path, original)
    for key, value in (("experiment_id", "other_experiment"), ("schema_version", 19), ("instance_id", "steady_state_slow_scan:dual")):
        data = json.loads(path.read_text())
        data[key] = value
        other = tmp_path / (key+".json")
        other.write_text(json.dumps(data))
        with pytest.raises(ValueError):
            load_plan(other)


def test_legacy_plan_requests_remain_metadata_after_normalization_and_resave(tmp_path):
    from control_app.measurement_modules.steady_state_slow_scan.settings import SlowScanSettings
    current = {"mode": "single", "lower_cm1": 1939, "upper_cm1": 1949,
               "requested_scan_speed_cm1_s": 4., "repetition_rate_hz": 100000., "pulse_width_s": 1e-6,
               "requested_sample_rate_hz": 1000., "requested_reference_sample_rate_hz": None}
    retired = {"requested_resolution_cm1": -1., "measured_linewidth_cm1": "unknown",
        "segments": [{"segment_id": "historical-QCL4", "qcl": 4, "lower_cm1": 1600, "upper_cm1": 1700}],
        "fit_peak_count": 0, "fit_line_shape": "historical-model", "fit_baseline_degree": 99,
        "fit_fringe_periods_cm1": [-1], "probe_width_s": 150e-9,
        "sample_rate_hz": 17., "reference_sample_rate_hz": 23.}
    original = {**current, **retired, "imported_requested_metadata": {"previous_note": "retained"}}
    first = save_plan(tmp_path / "legacy.json", original)
    assert load_plan(first) == original
    normalized = SlowScanSettings.from_dict(load_plan(first)).to_dict()
    expected = SlowScanSettings.from_dict(current).to_dict()
    imported = normalized.pop("imported_requested_metadata")
    expected.pop("imported_requested_metadata")
    assert normalized == expected
    assert imported == {"previous_note": "retained", **retired}
    normalized["imported_requested_metadata"] = imported
    resaved = save_plan(tmp_path / "resaved.json", normalized)
    reloaded = SlowScanSettings.from_dict(load_plan(resaved)).to_dict()
    assert reloaded == normalized
    assert load_plan(first) == original
    # A legacy T660 TTL width must never become the optical QCL pulse width.
    assert reloaded["pulse_width_s"] == current["pulse_width_s"]
    assert reloaded["requested_sample_rate_hz"] == 1000.
    assert reloaded["requested_reference_sample_rate_hz"] is None


def test_native_roundtrip_is_exact_dtype_values_directions_flags_and_rich_results(tmp_path):
    run = retained_run()
    first = run["sweeps"][0]
    reverse = replace(first, sweep_id="sweep-2-rejected", direction="reverse", replicate=1,
        axis_cm1=first.axis_cm1[::-1], sample=first.sample[::-1], flags=("rejected", "clipping"))
    run["sweeps"].append(reverse)
    path = save_run(tmp_path / "retained", run)
    restored = load_run(path, expected_mode="single", expected_condition_id="rt_mbco")
    assert isinstance(restored["spectra"][0], ProcessedSpectrum)
    assert restored["fits"][0].peaks[0] == run["fits"][0].peaks[0]
    for before, after in zip(run["sweeps"], restored["sweeps"]):
        for name in ("axis_cm1", "sample", "timestamps_s"):
            assert getattr(after, name).dtype == getattr(before, name).dtype
            assert getattr(after, name).tobytes() == getattr(before, name).tobytes()
        assert after.direction == before.direction and after.flags == before.flags
        assert after.metadata["original_signed_zero"].tobytes() == before.metadata["original_signed_zero"].tobytes()
    assert restored["readbacks"]["native_clock"][0] == 2**63+11
    assert np.isnan(restored["rejected"][0]["values"][0])
    assert restored["restoration"] == run["restoration"]
    with pytest.raises(FileExistsError):
        save_run(path.parent, run)
    with pytest.raises(ValueError, match="mode mismatch"):
        load_run(path, expected_mode="dual")


def test_exports_are_new_revisions_and_preserve_original_native(tmp_path):
    run = retained_run()
    original_path = save_run(tmp_path / "native", run)
    original_bytes = original_path.read_bytes()
    export = export_run(tmp_path / "analysis-1.json", {**run, "analysis_note": "Prospective alternate baseline"})
    assert export.with_suffix(".npz").exists()
    restored = load_run(export)
    assert restored["analysis_note"] == "Prospective alternate baseline"
    assert original_path.read_bytes() == original_bytes
    with pytest.raises(FileExistsError):
        export_run(export, run)


def test_historical_fit_settings_and_results_survive_load_and_export_without_refitting(tmp_path, monkeypatch):
    run = retained_run()
    legacy = {"requested_resolution_cm1": .004, "measured_linewidth_cm1": .03,
        "segments": [{"segment_id": "old-QCL4", "qcl": 4, "lower_cm1": 1939, "upper_cm1": 1949}],
        "fit_peak_count": 6, "fit_line_shape": "lorentzian", "fit_baseline_degree": 2,
        "fit_fringe_periods_cm1": [2.3, 8.1]}
    run["settings"].update(legacy)
    fitted = run["fits"][0]
    alternative = replace(fitted, settings=replace(fitted.settings, selection_reason="Historical alternative"))
    run["fit_alternatives"] = [(fitted, alternative)]
    def no_refitting(*args, **kwargs):
        raise AssertionError("Loading or exporting must not refit historical observations")
    monkeypatch.setattr("control_app.measurement_modules.steady_state_slow_scan.processing.fit_spectrum", no_refitting)
    original = save_run(tmp_path / "original", run)
    loaded = load_run(original)
    exported = load_run(export_run(tmp_path / "export.json", loaded))
    for record in (loaded, exported):
        assert record["settings"] == run["settings"]
        assert record["fits"][0].settings == fitted.settings
        assert record["fits"][0].peaks == fitted.peaks
        assert record["fit_alternatives"][0][1].settings == alternative.settings
        for name in ("fitted", "baseline", "residuals", "covariance", "parameters", "valid"):
            before, after = getattr(fitted, name), getattr(record["fits"][0], name)
            assert before.dtype == after.dtype and before.tobytes() == after.tobytes()


def test_storage_failure_retains_acquisition_chunks_and_does_not_invent_completed_manifest(tmp_path, monkeypatch):
    output = tmp_path / "run"
    output.mkdir()
    partial = output / "partial-0001.json"
    partial.write_text('{"observed": 2}')
    def fail(*args, **kwargs):
        raise OSError("Disk full")
    monkeypatch.setattr(np, "savez", fail)
    with pytest.raises(OSError, match="Disk full"):
        save_run(output, retained_run())
    assert partial.read_text() == '{"observed": 2}'
    assert not (output / "run.json").exists()


def test_sample_selection_is_standalone_and_keeps_ratio_distinct_from_absorbance(tmp_path):
    run = retained_run("dual")
    path = save_run(tmp_path / "native", run)
    run["path"] = path.parent
    selection_path = export_selection(run, tmp_path / "sample-state.json", **accepted_arguments(run))
    selection = load_sample_selection(selection_path)
    assert selection.sample_id == "sample-A"
    assert selection.producer_instance_id == "steady_state_slow_scan:dual"
    assert selection.condition["spectral_quantities"] == ("reference_normalized_ratio",)
    assert selection.condition["instrument_bundle_promoted"] is False
    assert selection.condition["instrument_configuration_accepted"] is False
    assert selection.accepted_by == "Named spectroscopy reviewer"
    assert selection.windows[0].center_cm1 == run["fits"][0].peaks[0].center_cm1


@pytest.mark.parametrize("change", ["partial", "uncalibrated", "clipping", "simulation", "unfitted", "uncertainty"])
def test_export_action_retains_raw_windows_and_limits_unsupported_claims(tmp_path, change):
    run = retained_run()
    kwargs = accepted_arguments(run)
    if change == "partial":
        run["status"] = "cancelled"
    elif change == "uncalibrated":
        run["spectra"][0] = replace(run["spectra"][0], provenance={})
    elif change == "clipping":
        run["spectra"][0] = replace(run["spectra"][0], flags=("clipping",))
    elif change == "simulation":
        run["simulation"] = True
    elif change == "unfitted":
        kwargs["windows"][0]["center_cm1"] += .001
    elif change == "uncertainty":
        kwargs["windows"][0]["uncertainty_cm1"] = 0
    kwargs["accepted_by"] = ""
    kwargs["acceptance"] = {"review_complete": False, "sample_state_accepted": False}
    path = export_selection(run, tmp_path / "selection.json", **kwargs)
    record = load_sample_selection(path)
    assert record.accepted_by == "operator export"
    assert record.condition["acceptance_provenance"]["action"] == "operator_export"
    assert not record.condition["physical_sample_state_accepted"]
    assert record.source.native_path and Path(record.source.native_path).is_file()
    if change == "unfitted":
        assert record.windows[0].center_cm1 is None
    elif change == "uncertainty":
        assert record.windows[0].uncertainty_cm1 == run["fits"][0].peaks[0].center_uncertainty_cm1
    elif change == "clipping":
        assert "clipping" in record.condition["quality_flags"]
    else:
        assert record.condition["limitations"]


@pytest.mark.parametrize("change,message", [
    ("settings_mode", "settings detector mode"),
    ("spectrum_mode", "spectrum native identity"),
    ("spectrum_unknown_sweep", "spectrum native identity"),
    ("fit_unknown_sweep", "Fit sweep/quantity"),
    ("fit_quantity", "Fit sweep/quantity"),
    ("fit_shape", "Fit support shape"),
])
def test_loaded_records_validate_detector_and_array_associations(tmp_path, change, message):
    run = retained_run()
    if change == "settings_mode":
        run["settings"]["mode"] = "dual"
    elif change.startswith("spectrum_"):
        replacements = {"spectrum_mode": {"mode": "dual"}, "spectrum_unknown_sweep": {"sweep_id": "unrelated-sweep"}}
        spectrum = run["spectra"][0]
        run["spectra"][0] = replace(spectrum, native=replace(spectrum.native, **replacements[change]))
    elif change == "fit_shape":
        run["fits"][0] = replace(run["fits"][0], fitted=np.zeros(2))
    else:
        provenance = dict(run["fits"][0].provenance)
        provenance.update({"sweep_id": "unrelated-sweep"} if change.endswith("sweep") else {"quantity": "calibrated_absorbance"})
        run["fits"][0] = replace(run["fits"][0], provenance=provenance)
    path = save_run(tmp_path / "mixed", run)
    with pytest.raises(ValueError, match=message):
        load_run(path)


def test_legacy_condition_annotations_and_absent_metadata_do_not_gate_loading_or_export(tmp_path):
    run = retained_run()
    run["condition_id"] = ""
    run["settings"]["condition"] = {}
    spectrum = run["spectra"][0]
    run["spectra"][0] = replace(spectrum, native=replace(spectrum.native, condition_id="old optional condition"))
    run["fits"][0] = replace(run["fits"][0], provenance={**run["fits"][0].provenance, "condition_id": "another annotation"})
    path = save_run(tmp_path / "retained", run)
    loaded = load_run(path, expected_condition_id="different annotation")
    assert loaded["spectra"][0].native.condition_id == "old optional condition"
    exported = export_selection(loaded, tmp_path / "selection.json", windows=[{"lower_cm1": 1943, "upper_cm1": 1945}])
    record = load_sample_selection(exported)
    assert not record.condition["sample_identity_provided"]
    assert not record.condition["condition_identity_provided"]
    assert record.sample_id == "unidentified-sample:run-A"
    assert record.condition_id == "unidentified-condition:run-A"
    assert not record.condition["physical_sample_state_accepted"]


def test_moved_analysis_export_rebinds_loaded_source_and_preserves_original_location(tmp_path):
    run = retained_run()
    original = export_run(tmp_path / "original" / "analysis.json", run)
    moved = tmp_path / "copied" / "analysis.json"
    moved.parent.mkdir()
    shutil.copy2(original, moved)
    shutil.copy2(original.with_suffix(".npz"), moved.with_suffix(".npz"))
    restored = load_run(moved)
    assert restored["analysis_path"] == str(moved.resolve())
    assert restored["source_locations"][-1] == {"original_analysis_path": str(original)}
    path = export_selection(restored, tmp_path / "accepted-moved.json", **accepted_arguments(restored))
    assert load_sample_selection(path).source.native_path == str(moved.resolve())


@pytest.mark.parametrize("change", ["restoration_failed", "restoration_missing", "source_missing", "gap", "no_fits"])
def test_partial_and_raw_exports_preserve_limits_without_approval_gates(tmp_path, change):
    run = retained_run()
    if change == "restoration_failed":
        run["restoration"]["safe_verified"] = False
    elif change == "restoration_missing":
        run["restoration"] = {}
    elif change == "gap":
        spectrum = run["spectra"][0]
        valid = spectrum.valid.copy()
        valid[60] = False
        run["spectra"][0] = replace(spectrum, valid=valid)
    elif change == "no_fits":
        run["fits"] = []
    path = export_selection(run, tmp_path / "selection.json", windows=[{"lower_cm1": 1943, "upper_cm1": 1945}])
    record = load_sample_selection(path)
    source = load_run(record.source.native_path)
    assert source["restoration"] == run["restoration"]
    assert not record.condition["physical_sample_state_accepted"]
    if change in ("restoration_failed", "restoration_missing", "gap"):
        assert record.condition["limitations"]
    assert record.windows[0].center_cm1 is None


def test_window_without_any_observed_support_still_rejects_invalid_data(tmp_path):
    with pytest.raises(ValueError, match="native spectral support"):
        export_selection(retained_run(), tmp_path / "selection.json", windows=[{"lower_cm1": 2000, "upper_cm1": 2010}])


@pytest.mark.parametrize("mode,quantity", [("single", "raw_sample_signal"), ("dual", "reference_normalized_ratio")])
def test_raw_relative_exports_need_no_material_metadata_calibration_or_fit(tmp_path, mode, quantity):
    run = retained_run(mode)
    raw = replace(run["sweeps"][0], condition_id="", metadata={})
    run.update(settings={"mode": mode}, condition_id="", sweeps=[raw], spectra=[process_sweep(raw)],
               fits=[], status="cancelled", restoration={})
    original_raw = raw.sample.tobytes()
    path = export_selection(run, tmp_path / "selection.json", windows=[{"lower_cm1": 1943, "upper_cm1": 1945}])
    record = load_sample_selection(path)
    assert record.condition["spectral_quantities"] == (quantity,)
    assert not record.condition["axis_calibrated"]
    assert not record.condition["physical_sample_state_accepted"]
    assert not record.condition["sample_identity_provided"]
    assert "analysis_path" not in run and "path" not in run
    assert raw.sample.tobytes() == original_raw


def test_moved_run_rebases_only_embedded_automatic_dark_parent_references(tmp_path):
    run = retained_run()
    original = tmp_path / "original"
    external = tmp_path / "external-blank"
    run["path"] = str(original)
    run["automatic_dark"] = {"run_id": "run-A:dark", "source_run_id": "run-A", "kind": "dark",
        "path": str(original), "native_record_field": "dark_native_records", "dark": {"sample": .001}}
    run["dark_native_records"] = [{"observations": np.array([.001, .002])}]
    run["controls"] = {"dark": {"run_id": "run-A:dark", "path": str(original)},
        "blank": {"run_id": "external-blank", "path": str(external)},
        "q0": {"run_id": "other-same-folder", "path": str(original)}}
    manifest = save_run(original, run)
    moved = tmp_path / "moved"
    moved.mkdir()
    shutil.copy2(manifest, moved / "run.json")
    shutil.copy2(original / "native.npz", moved / "native.npz")
    loaded = load_run(moved)
    assert loaded["automatic_dark"]["path"] == str(moved.resolve())
    assert loaded["controls"]["dark"]["path"] == str(moved.resolve())
    assert loaded["automatic_dark"]["source_locations"] == [{"original_parent_path": str(original)}]
    assert loaded["controls"]["blank"]["path"] == str(external)
    assert loaded["controls"]["q0"]["path"] == str(original)
    assert run["automatic_dark"]["path"] == str(original)
    np.testing.assert_array_equal(loaded["dark_native_records"][0]["observations"], [.001, .002])
