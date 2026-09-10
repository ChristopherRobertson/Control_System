"""Automatic reference reuse, live defaults and conservative native loading."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from control_app.measurement_modules.microsecond_stroboscopy.settings import default_settings, SpectralPoint
from control_app.measurement_modules.microsecond_stroboscopy.planner import build_plan
from control_app.measurement_modules.microsecond_stroboscopy.scientific_adapter import MicrosecondScientificAdapter


def accepted_selection(settings):
    return {"schema_version": 1, "record_kind": "sample_spectral_selection", "disposition": "accepted",
            "selection_id": "selection-1", "sample_id": settings.identity.sample_id,
            "producer_instance_id": "microsecond_stroboscopy:single",
            "source": {"producer_run_id": "source-1", "native_path": "measurements/source-1/native.json",
                       "created_utc": "2026-09-10T00:00:00Z", "software_version": "1"},
            "condition_id": settings.identity.condition_id, "condition": {},
            "windows": [{"lower_cm1": 1944., "upper_cm1": 1946., "label": "Measured A1"}],
            "accepted_by": "Test reviewer", "accepted_utc": "2026-09-10T01:00:00Z"}


def adapter_plan(hardware=False):
    settings = default_settings("dual")
    settings = replace(settings, execution_mode="hardware" if hardware else "simulation",
                       identity=replace(settings.identity, sample_selection_id="selection-1"))
    adapter = MicrosecondScientificAdapter(SimpleNamespace(mode="dual"), SimpleNamespace(_base=settings.to_dict()))
    return adapter, build_plan(settings)


def test_us_optional_selection_metadata_does_not_alter_or_gate_manual_grid():
    adapter, plan = adapter_plan(True)
    adapter.sample_records = (accepted_selection(plan.settings),)
    before = plan.settings.to_dict()
    assert not adapter.validate_plan(plan)
    assert plan.settings.to_dict() == before


@pytest.mark.parametrize("field,value", [
    ("sample_id", "different-sample"),
    ("condition_id", "different-condition"),
    ("selection_id", "different-selection"),
    ("disposition", "rejected"),
])
def test_us_optional_selection_never_becomes_an_acquisition_gate(field, value):
    adapter, plan = adapter_plan()
    record = accepted_selection(plan.settings)
    record[field] = value
    adapter.sample_records = (record,)
    assert not adapter.validate_plan(plan)


def test_us_raw_grid_requires_no_accepted_selection():
    adapter, plan = adapter_plan()
    record = accepted_selection(plan.settings)
    adapter.sample_records = (record, deepcopy(record))
    assert not adapter.validate_plan(plan)
    adapter.sample_records = (record,)
    changed = replace(plan.settings, spectral_points=plan.settings.spectral_points + (SpectralPoint(1947., "A1", "band"),))
    assert not adapter.validate_plan(build_plan(changed))


def test_us_live_default_does_not_follow_historical_simulation_plan():
    adapter, plan = adapter_plan(True)
    assert not adapter.validate_plan(plan)
    assert adapter.hardware_required("measurement", {"execution_mode": "simulation"})
    assert adapter.validate_preliminary(None, plan) == ()
    assert not adapter.validate_plan(build_plan(replace(plan.settings, execution_mode="simulation")))


def compatible_record(adapter, plan, kind="preliminary"):
    return {"experiment_id": "microsecond_stroboscopy", "mode": "dual", "kind": kind,
            "status": "completed", "settings": plan.settings.to_dict(),
            "compatibility": adapter.compatibility(plan),
            "processing": {"points": [{"wavenumber_cm1": point.wavenumber_cm1, "valid": True}
                                      for point in plan.settings.spectral_points]}}


def test_us_reference_reuse_ignores_metadata_but_respects_response_and_coverage():
    adapter, plan = adapter_plan()
    record = compatible_record(adapter, plan)
    changed = replace(plan.settings, condition_profile_id="historical-note",
                      identity=replace(plan.settings.identity, sample_id="relabeled", measured_temperature_k=77.))
    assert adapter.reusable(record, build_plan(changed), kind="preliminary") is record
    changed = replace(plan.settings, response=replace(plan.settings.response, sample_rate_sps=1000.),
                      manual_overrides=("response.sample_rate_sps",))
    assert adapter.reusable(record, build_plan(changed), kind="preliminary") is None
    record["processing"]["points"].pop()
    assert adapter.reusable(record, plan, kind="preliminary") is None


def test_us_loaded_reference_retained_across_new_run_and_isolated_by_adapter():
    adapter, plan = adapter_plan()
    other, _ = adapter_plan()
    record = compatible_record(adapter, plan)
    adapter.reuse_records(record)
    adapter.new_run()
    assert adapter.retained_preliminary is record
    assert other.retained_preliminary is None
    assert adapter.validate_preliminary({"status": "failed"}, plan) == ()
    malformed = compatible_record(adapter, plan)
    malformed["compatibility"]["settings"] = {"bad_old_record": object()}
    assert adapter.reusable(malformed, plan, kind="preliminary") is None


def test_us_missing_installed_factory_is_concrete_action_prerequisite():
    adapter, plan = adapter_plan()
    adapter.context.devices = SimpleNamespace(available=lambda **_: ("hf2li", "t660_1", "t660_2"))
    assert adapter.validate_operation("check_capabilities", plan, None) == ()
    assert adapter.validate_operation("measurement", plan, None) == ("Device service unavailable: mircat",)


def test_us_adapter_setup_failure_releases_before_device_access(monkeypatch):
    adapter, plan = adapter_plan()
    released = []
    adapter.context.ownership = SimpleNamespace(release=lambda token, **outcomes: released.append((token, outcomes)))
    snapshot = SimpleNamespace(plan=plan, preliminary=None,
                               operation=SimpleNamespace(hardware=True, ownership="owned-token"))
    def broken(*_, **__):
        raise ValueError("Malformed optional compatibility")
    monkeypatch.setattr(adapter, "compatibility", broken)
    with pytest.raises(ValueError, match="Malformed"):
        adapter._execute(snapshot, object(), "run")
    assert adapter._active_worker is None
    assert released[0][0] == "owned-token"
    assert released[0][1]["safe_verified"] and released[0][1]["preservation_verified"]


def test_us_capacity_is_action_specific_so_large_sample_does_not_gate_preliminary():
    adapter, plan = adapter_plan()
    limited = build_plan(replace(plan.settings, budget=replace(plan.settings.budget, maximum_memory_bytes=200 * 1024**2)))
    adapter.context.devices = SimpleNamespace(available=lambda **_: ("hf2li", "mircat", "t660_1", "t660_2"))
    assert not adapter.validate_plan(limited)
    assert not adapter.validate_operation("preliminary", limited, None)
    assert any("memory" in error for error in adapter.validate_operation("measurement", limited, None))


@pytest.mark.parametrize("analysis_fails", [False, True])
def test_us_native_load_reconstructs_without_fits_and_retains_analysis_failure(tmp_path, monkeypatch, analysis_fails):
    from control_app.measurement_modules.microsecond_stroboscopy import persistence, processing
    adapter, plan = adapter_plan()
    native = np.array([1., np.nan, 3.], dtype=np.float32)
    record = {"schema_version": 1, "experiment_id": "microsecond_stroboscopy", "mode": "dual",
              "settings": plan.settings.to_dict(), "disposition": "interrupted", "native_blocks": [{"native": native}]}
    path = persistence.save_run(tmp_path / "partial", record)
    calls = []
    def reconstruct(retained, *, fit_models):
        calls.append(fit_models)
        if analysis_fails:
            raise ValueError("No complete timing support")
        return {"points": [], "coverage": {"missing_points": 3}}
    monkeypatch.setattr(processing, "process_run", reconstruct)
    loaded = adapter.load_run(path)
    assert calls == [False]
    assert np.array_equal(loaded["native_blocks"][0]["native"], native, equal_nan=True)
    if analysis_fails:
        assert "No complete timing support" in loaded["analysis_error"]
    else:
        assert loaded["processing"]["coverage"]["missing_points"] == 3
