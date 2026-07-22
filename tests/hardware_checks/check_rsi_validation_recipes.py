#!/usr/bin/env python3
"""Validate RSI spectral-validation recipes and scan metadata behavior without hardware."""

from __future__ import annotations

from _common import REPO_ROOT

from pathlib import Path
import tempfile

import yaml

from control_app.config_loader import load_config_inventory
from control_app.workflows.mircat_fast_sweep import load_fast_sweep_request
from control_app.workflows.state_machine import (
    WorkflowStateMachine,
    WorkflowStateMachineError,
    _scan_points,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager


RECIPES = (
    REPO_ROOT / "recipes" / "polystyrene_validation.yaml",
    REPO_ROOT / "recipes" / "mylar_validation.yaml",
    REPO_ROOT / "recipes" / "myoglobin_co_validation.yaml",
)
INSTALLED_MIN_CM1 = 1638.8
INSTALLED_MAX_CM1 = 2077.3


def main() -> int:
    recipes = [_load_recipe(path) for path in RECIPES]
    for path, recipe in zip(RECIPES, recipes, strict=True):
        _assert_recipe_shape(path, recipe)
        _assert_scan_points(path, recipe)
    _assert_unapproved_emission_blocks(recipes[0])
    _assert_per_point_metadata(recipes[2])
    _assert_fast_sweep_recipe()
    print("PASS RSI validation recipes")
    return 0


def _load_recipe(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise AssertionError(f"{path} must parse as a mapping")
    return data


def _assert_recipe_shape(path: Path, recipe: dict[str, object]) -> None:
    required = {
        "probe",
        "pump",
        "delay_list_ns",
        "controls",
        "file_naming",
        "go_no_go_criteria",
        "hf2li_preset",
        "timing_recipe",
        "picoscope_recipe",
        "approved_laser_safety_condition",
    }
    missing = sorted(required - set(recipe))
    if missing:
        raise AssertionError(f"{path} missing keys: {missing}")
    if recipe.get("approved_laser_safety_condition") is not True:
        raise AssertionError(f"{path} must explicitly safety-approve MIRcat emission")
    timing_recipe = REPO_ROOT / str(recipe["timing_recipe"])
    if not timing_recipe.exists():
        raise AssertionError(f"{path} references missing timing recipe {timing_recipe}")


def _assert_scan_points(path: Path, recipe: dict[str, object]) -> None:
    points = _scan_points(recipe)
    if not points:
        raise AssertionError(f"{path} generated no scan points")
    for point in points:
        value = float(point["wavenumber_cm1"])
        if value < INSTALLED_MIN_CM1 or value > INSTALLED_MAX_CM1:
            raise AssertionError(f"{path} generated out-of-range wavenumber {value}")
        if float(point["dwell_s"]) <= 0:
            raise AssertionError(f"{path} generated nonpositive dwell")


def _assert_unapproved_emission_blocks(recipe: dict[str, object]) -> None:
    bad_recipe = dict(recipe)
    bad_recipe["approved_laser_safety_condition"] = False
    with tempfile.TemporaryDirectory() as temp_dir:
        machine = WorkflowStateMachine(
            operator="test",
            inventory=load_config_inventory(write_files=False),
            hardware_access=False,
            run_dir=temp_dir,
        )
        try:
            machine._validate_recipe_shape(bad_recipe)
        except WorkflowStateMachineError:
            return
    raise AssertionError("unapproved MIRcat emission recipe did not block")


def _assert_per_point_metadata(recipe: dict[str, object]) -> None:
    first_point = _scan_points(recipe)[0]
    with tempfile.TemporaryDirectory() as temp_dir:
        machine = WorkflowStateMachine(
            operator="test",
            inventory=load_config_inventory(write_files=False),
            hardware_access=True,
            run_dir=temp_dir,
        )
        machine.recipe = recipe
        machine.recipe_path = RECIPES[2]
        fake = FakeMircatService()
        machine._mircat_service = fake
        readback = machine._prepare_mircat_for_point(first_point, point_index=0)
        if fake.tuned_wavenumbers != [first_point["wavenumber_cm1"]]:
            raise AssertionError("MIRcat was not tuned to the scan point")
        if not readback["emission_on"]:
            raise AssertionError("approved validation recipe did not request emission-on")
        if not Path(readback["readback_path"]).exists():
            raise AssertionError("per-point MIRcat readback JSON was not written")
        if readback["trigger_settings"]["start"] != first_point["wavenumber_cm1"]:
            raise AssertionError("external-trigger settings did not track scan point")


def _assert_fast_sweep_recipe() -> None:
    request = load_fast_sweep_request(REPO_ROOT / "recipes" / "polystyrene_fast_sweep.yaml")
    if request.sample_name != "Polystyrene":
        raise AssertionError("fast-sweep recipe did not preserve sample name")
    if request.use_t660_ext_ref:
        raise AssertionError("fast-sweep recipe must not drive the HF2LI reference from T660 by default")
    if not request.require_rewired_mircat_trig_out_to_hf2li_dio0:
        raise AssertionError("fast-sweep recipe must require MIRcat TRIG OUT -> HF2LI DIO0")
    if not request.require_rewired_mircat_trig_out_to_hf2li_dio1:
        raise AssertionError("fast-sweep recipe must require MIRcat TRIG OUT -> HF2LI DIO1")
    if request.sweep_duration_s > 10.1:
        raise AssertionError(f"fast-sweep duration is unexpectedly long: {request.sweep_duration_s}")
    inventory = load_config_inventory(write_files=False)
    validation = TimingRecipeManager(inventory).validate_recipe(
        REPO_ROOT / "recipes" / "hf2li_extref_2mhz.yaml"
    )
    resolved = validation["resolved_settings"]["t660_2"]["channels"]
    if not resolved["A"].get("enabled"):
        raise AssertionError("fast-sweep T660 recipe must enable T660-2 CHA for HF2LI EXT REF")
    if resolved["B"].get("enabled"):
        raise AssertionError("fast-sweep T660 recipe must not drive MIRcat TRIG IN on T660-2 CHB")


class FakeState:
    def __init__(self, emission_on: bool) -> None:
        self.emission_on = emission_on

    def to_dict(self) -> dict[str, object]:
        return {"emission_on": self.emission_on}


class FakeMircatService:
    def __init__(self) -> None:
        self.emission_on = False
        self.tuned_wavenumbers: list[float] = []

    def read_state(self) -> FakeState:
        return FakeState(self.emission_on)

    def turn_emission_off(self) -> None:
        self.emission_on = False

    def tune_to_wavenumber(self, wavenumber_cm1: float, *, qcl: int) -> None:
        self.tuned_wavenumbers.append(float(wavenumber_cm1))

    def wait_for_tuned(self, *, timeout_s: float, poll_interval_s: float) -> bool:
        return True

    def set_external_trigger_params(self, *, wavenumber_cm1: float) -> dict[str, object]:
        return {"pulse_mode": 2, "pulse_mode_name": "external_trigger", "start": wavenumber_cm1}

    def turn_emission_on(self, *, approved_laser_safety_condition: bool) -> None:
        if not approved_laser_safety_condition:
            raise AssertionError("emission-on was called without approval")
        self.emission_on = True

    def get_actual_wavelength(self) -> dict[str, object]:
        return {"value": self.tuned_wavenumbers[-1], "units": "cm^-1", "light_valid": True}


if __name__ == "__main__":
    raise SystemExit(main())
