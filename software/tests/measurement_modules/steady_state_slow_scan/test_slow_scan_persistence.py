"""Schema isolation, exact native retention and independent sample acceptance."""
from dataclasses import replace
import json
import shutil

import numpy as np
import pytest

from control_app.measurement_host.interchange import load_sample_selection
from control_app.measurement_modules.steady_state_slow_scan.persistence import (
    export_run, export_selection, load_plan, load_run, save_plan, save_run,
)
from control_app.measurement_modules.steady_state_slow_scan.processing import (
    FitSettings, NativeSweep, ProcessedSpectrum, fit_spectrum,
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
    for kwargs, message in (({"expected_mode": "dual"}, "mode mismatch"),
                            ({"expected_condition_id": "77k_mbco"}, "Condition mismatch")):
        with pytest.raises(ValueError, match=message):
            load_plan(path, **kwargs)
    with pytest.raises(FileExistsError):
        save_plan(path, original)
    for key, value in (("experiment_id", "other_experiment"), ("schema_version", 19), ("instance_id", "steady_state_slow_scan:dual")):
        data = json.loads(path.read_text())
        data[key] = value
        other = tmp_path / (key+".json")
        other.write_text(json.dumps(data))
        with pytest.raises(ValueError):
            load_plan(other)


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
    assert selection.condition["campaign_phase_accepted"] is False
    assert selection.accepted_by == "Named spectroscopy reviewer"
    assert selection.windows[0].center_cm1 == run["fits"][0].peaks[0].center_cm1


@pytest.mark.parametrize("change,message", [
    ("status", "complete retained"), ("review", "explicit completed review"),
    ("axis", "spectral-axis calibration"), ("uncertainty", "understates"),
    ("configuration", "configuration identity"), ("clipping", "quality faults"),
    ("unfitted", "not present"),
    ("simulation", "Simulation spectra"),
])
def test_exploratory_or_faulted_records_cannot_silently_become_accepted(tmp_path, change, message):
    run = retained_run()
    kwargs = accepted_arguments(run)
    if change == "status":
        run["status"] = "cancelled"
    elif change == "review":
        kwargs["acceptance"]["review_complete"] = False
    elif change == "axis":
        run["spectra"][0] = replace(run["spectra"][0], provenance={})
    elif change == "uncertainty":
        kwargs["windows"][0]["uncertainty_cm1"] = 0
    elif change == "configuration":
        kwargs["acceptance"]["configuration_id"] = "other"
    elif change == "clipping":
        run["spectra"][0] = replace(run["spectra"][0], flags=("clipping",))
    elif change == "unfitted":
        kwargs["windows"][0]["center_cm1"] += .001
    elif change == "simulation":
        run["simulation"] = True
    with pytest.raises(ValueError, match=message):
        export_selection(run, tmp_path / "selection.json", **kwargs)
    assert not (tmp_path / "selection.json").exists()


@pytest.mark.parametrize("change,message", [
    ("settings_mode", "settings detector mode/condition"),
    ("settings_condition", "settings detector mode/condition"),
    ("spectrum_mode", "spectrum native identity"),
    ("spectrum_condition", "spectrum native identity"),
    ("spectrum_unknown_sweep", "spectrum native identity"),
    ("fit_condition", "Fit condition/sweep/quantity"),
    ("fit_unknown_sweep", "Fit condition/sweep/quantity"),
    ("fit_quantity", "Fit condition/sweep/quantity"),
    ("fit_shape", "Fit support shape"),
    ("alternative_condition", "Fit condition/sweep/quantity"),
])
def test_loaded_scientific_objects_must_match_run_and_sweep_identities(tmp_path, change, message):
    run = retained_run()
    if change == "settings_mode":
        run["settings"]["mode"] = "dual"
    elif change == "settings_condition":
        run["settings"]["condition"]["condition_id"] = "77k_mbco"
    elif change.startswith("spectrum_"):
        replacements = {"spectrum_mode": {"mode": "dual"},
                        "spectrum_condition": {"condition_id": "77k_mbco"},
                        "spectrum_unknown_sweep": {"sweep_id": "unrelated-sweep"}}
        spectrum = run["spectra"][0]
        run["spectra"][0] = replace(spectrum, native=replace(spectrum.native, **replacements[change]))
    elif change == "fit_shape":
        run["fits"][0] = replace(run["fits"][0], fitted=np.zeros(2))
    else:
        provenance = dict(run["fits"][0].provenance)
        provenance.update({"condition_id": "77k_mbco"} if change.endswith("condition") else
                          {"sweep_id": "unrelated-sweep"} if change.endswith("sweep") else
                          {"quantity": "calibrated_absorbance"})
        changed_fit = replace(run["fits"][0], provenance=provenance)
        if change == "alternative_condition":
            run["fit_alternatives"] = [(changed_fit,)]
        else:
            run["fits"][0] = changed_fit
    path = save_run(tmp_path / "mixed", run)
    with pytest.raises(ValueError, match=message):
        load_run(path)


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


@pytest.mark.parametrize("change,message", [
    ("restoration_failed", "verified safe restoration"),
    ("restoration_missing", "verified safe restoration"),
    ("source_missing", "only after.*retained"),
    ("gap", "incomplete valid support"),
    ("replicate_without_fit", "lacks a fitted result"),
    ("replicate_without_spectrum", "without a processed spectrum"),
])
def test_acceptance_requires_preserved_restored_fitted_support_for_relevant_replicates(tmp_path, change, message):
    run = retained_run()
    kwargs = accepted_arguments(run)
    if change == "restoration_failed":
        run["restoration"]["safe_verified"] = False
    elif change == "restoration_missing":
        run["restoration"] = {}
    elif change == "gap":
        spectrum = run["spectra"][0]
        valid = spectrum.valid.copy()
        valid[60] = False
        run["spectra"][0] = replace(spectrum, valid=valid)
    elif change in ("replicate_without_fit", "replicate_without_spectrum"):
        spectrum = run["spectra"][0]
        extra = replace(spectrum.native, sweep_id="repeat-without-fit", replicate=1)
        run["sweeps"].append(extra)
        if change == "replicate_without_fit":
            run["spectra"].append(replace(spectrum, native=extra))
    with pytest.raises(ValueError, match=message):
        export_selection(run, tmp_path / "not-accepted.json", **kwargs)
