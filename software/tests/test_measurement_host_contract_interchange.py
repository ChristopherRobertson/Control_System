"""Standalone interchange validates without Slow Scan or other engines installed."""
from dataclasses import replace

import pytest

from control_app.measurement_host import ContextFactory
from control_app.measurement_host.contracts import ContractError
from control_app.measurement_host.interchange import (
    DeviceConfigurationChange, InstrumentStateChange, PromotedCalibrationReference,
    SampleSpectralSelection, SourceRecord, SpectralWindow, instrument_state_change_from_dict,
    load_sample_selection, sample_selection_from_dict, save_sample_selection, validate_sample_selection,
)
from control_app.measurement_host.ownership import HardwareCoordinator


def accepted_selection():
    return SampleSpectralSelection(
        selection_id="sample_a_window_1", sample_id="sample_a",
        producer_instance_id="steady_state_slow_scan:single",
        source=SourceRecord("run-123", "sample_a/native.json", "2026-09-10T00:00:00Z", "slow-scan-v1"),
        condition_id="room_temperature_v1", condition={"temperature_K": 293.15, "mixture": ["sample_a"]},
        windows=(SpectralWindow(1500, 1510, 1505, .5, "selected band"),),
        accepted_by="Example reviewer", accepted_utc="2026-09-10T00:01:00Z",
        uncertainty_description="One-standard-deviation center uncertainty in cm^-1",
    )


def test_standalone_sample_roundtrip_and_frozen_run(tmp_path):
    selection = accepted_selection()
    path = save_sample_selection(selection, tmp_path / "selection.json")
    assert load_sample_selection(path) == selection
    assert sample_selection_from_dict(selection.to_dict()) == selection
    with pytest.raises(FileExistsError):
        save_sample_selection(selection, path)
    with pytest.raises(TypeError):
        selection.condition["temperature_K"] = 300
    context = ContextFactory(ownership=HardwareCoordinator(tmp_path / "lock"), save_root_provider=lambda: tmp_path
                             ).for_experiment("fixed_wavenumber_kinetics").for_mode("dual")
    run = context.begin_operation({}, sample_records=(selection,),
                                  calibration_records=(PromotedCalibrationReference("timing_bundle", "timing_v1"),))
    assert run.sample_records[0]["record_kind"] == "sample_spectral_selection"
    assert run.calibration_records[0]["record_kind"] == "promoted_instrument_calibration"
    assert run.to_dict()["sample_records"][0]["condition"]["mixture"] == ["sample_a"]


def test_sample_schema_rejects_calibration_unknown_versions_and_invalid_uncertainty():
    selection = accepted_selection()
    with pytest.raises(ContractError, match="separate record type"):
        validate_sample_selection(PromotedCalibrationReference("a", "b"))
    with pytest.raises(ContractError, match="instrument calibration"):
        sample_selection_from_dict({"schema_version": 1, "record_kind": "promoted_instrument_calibration"})
    with pytest.raises(ContractError, match="schema_version"):
        sample_selection_from_dict({**selection.to_dict(), "schema_version": 2})
    with pytest.raises(ContractError, match="accepted"):
        replace(selection, disposition="preview")
    for uncertainty in (-1, float("nan"), float("inf")):
        with pytest.raises(ContractError):
            SpectralWindow(1, 2, 1.5, uncertainty)
    with pytest.raises(ContractError, match="inside"):
        SpectralWindow(1, 2, 3)


def test_instrument_event_explicit_recipients_device_changes_and_roundtrip():
    previous = {"routes": ["pump"]}
    event = InstrumentStateChange(
        producer_instance_id="manual:t660_1", recipients=("phase_scan:single", "nanosecond_stroboscopy:dual"),
        changes=(DeviceConfigurationChange("t660_1", "timing_table", previous, {"routes": ["probe"]}),),
        reason="Timing route configured manually; review dependent timing settings",
    )
    previous["routes"].append("changed")
    assert event.changes[0].previous_value["routes"] == ("pump",)
    assert instrument_state_change_from_dict(event.to_dict()) == event
    with pytest.raises(ContractError, match="explicit recipients"):
        replace(event, recipients=())
    with pytest.raises(ContractError, match="device/configuration"):
        replace(event, changes=())
    with pytest.raises(ContractError, match="instance_id"):
        replace(event, recipients=("*",))
