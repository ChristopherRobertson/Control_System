"""Retained sample selection validation and conservative offline native loading."""
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


def test_us_selected_accepted_window_allows_off_band_outside_without_altering_grid():
    adapter, plan = adapter_plan(True)
    adapter.sample_records = (accepted_selection(plan.settings),)
    before = plan.settings.to_dict()
    assert not adapter.validate_plan(plan)
    assert plan.settings.to_dict() == before


@pytest.mark.parametrize("field,value,expected", [
    ("sample_id", "different-sample", "sample_id"),
    ("condition_id", "different-condition", "condition_id"),
    ("selection_id", "different-selection", "exactly one"),
    ("disposition", "rejected", "invalid"),
])
def test_us_selection_rejects_named_record_incompatibility(field, value, expected):
    adapter, plan = adapter_plan()
    record = accepted_selection(plan.settings)
    record[field] = value
    adapter.sample_records = (record,)
    assert any(expected in error for error in adapter.validate_plan(plan))


def test_us_selection_rejects_duplicate_ids_and_unaccepted_band_coordinates():
    adapter, plan = adapter_plan()
    record = accepted_selection(plan.settings)
    adapter.sample_records = (record, deepcopy(record))
    assert any("exactly one" in error for error in adapter.validate_plan(plan))
    adapter.sample_records = (record,)
    changed = replace(plan.settings, spectral_points=plan.settings.spectral_points + (SpectralPoint(1947., "A1", "band"),))
    assert any("1947" in error for error in adapter.validate_plan(build_plan(changed)))


def test_us_hardware_requires_retained_selection_but_examples_remain_plannable():
    adapter, plan = adapter_plan(True)
    assert any("alone is not a record" in error for error in adapter.validate_plan(plan))
    assert not adapter.validate_plan(build_plan(replace(plan.settings, execution_mode="simulation")))


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
