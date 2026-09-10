"""Installed PicoScope factory compatibility using a fake constructor only."""
from copy import deepcopy
from types import MappingProxyType, SimpleNamespace

import pytest

from control_app.measurement_host.context import ContextFactory
from control_app.measurement_host.contracts import ContractError
from control_app.measurement_host import device_factories
from control_app.measurement_host.ownership import HardwareCoordinator, OwnershipError, require_hardware_owner


@pytest.fixture
def fake_picoscope(monkeypatch):
    observations = SimpleNamespace(constructors=[], imports=[], owner_required=False)

    class FakePicoScope:
        # An explicit signature catches accidentally forwarding capture_settings
        # twice as both the second positional argument and a keyword argument.
        def __init__(self, device_config, capture_settings, *, command_log=None):
            self.owner = require_hardware_owner() if observations.owner_required else None
            self.device_config = device_config
            self.capture_settings = capture_settings
            self.command_log = command_log
            observations.constructors.append(self)

    def fake_import(module_name):
        assert module_name == "control_app.devices.picoscope_service"
        observations.imports.append(module_name)
        return SimpleNamespace(PicoScopeService=FakePicoScope)

    monkeypatch.setattr(device_factories, "import_module", fake_import)
    observations.factory = device_factories.installed_device_factories()["picoscope"]
    return observations


def _configuration():
    return {
        "devices": {"picoscope": {
            "serial_number": "configured-serial", "identity": {"model": "simulated"},
            "capture_settings": {"samples": 100, "channels": {"A": {"range": "1V"}}},
        }},
        "picoscope_settings": {"samples": 200},
        "acquisition": {"picoscope": {"samples": 300}},
    }


def test_explicit_capture_override_is_fresh_deeply_detached_and_forwards_other_kwargs(fake_picoscope):
    configuration = _configuration()
    original_configuration = deepcopy(configuration)
    override = {"samples": 42, "channels": {"A": {"range": "2V", "offsets": [0, 1]}}}
    original_override = deepcopy(override)
    command_log = object()
    first = fake_picoscope.factory(configuration=configuration, capture_settings=override, command_log=command_log)
    second = fake_picoscope.factory(configuration=configuration, capture_settings=override, command_log=command_log)

    assert first is not second
    assert first.capture_settings == second.capture_settings == original_override
    assert first.capture_settings is not second.capture_settings
    assert first.command_log is second.command_log is command_log
    assert configuration == original_configuration and override == original_override

    # Caller edits and mutable service state are independent in both directions.
    override["channels"]["A"]["offsets"].append(2)
    configuration["devices"]["picoscope"]["identity"]["model"] = "caller edit"
    assert first.capture_settings["channels"]["A"]["offsets"] == [0, 1]
    assert first.device_config["identity"]["model"] == "simulated"
    first.capture_settings["channels"]["A"]["range"] = "10V"
    first.device_config["identity"]["model"] = "service edit"
    assert second.capture_settings == original_override
    assert second.device_config == original_configuration["devices"]["picoscope"]
    assert override["channels"]["A"]["range"] == "2V"
    assert configuration["devices"]["picoscope"]["identity"]["model"] == "caller edit"


@pytest.mark.parametrize("source", ["device", "global", "acquisition", "empty_device_uses_global"])
def test_omitted_override_retains_configuration_precedence_and_detaches(fake_picoscope, source):
    configuration = _configuration()
    if source == "global":
        del configuration["devices"]["picoscope"]["capture_settings"]
        expected = configuration["picoscope_settings"]
    elif source == "acquisition":
        del configuration["devices"]["picoscope"]["capture_settings"]
        del configuration["picoscope_settings"]
        expected = configuration["acquisition"]["picoscope"]
    elif source == "empty_device_uses_global":
        configuration["devices"]["picoscope"]["capture_settings"] = {}
        expected = configuration["picoscope_settings"]
    else:
        expected = configuration["devices"]["picoscope"]["capture_settings"]
    expected_value = deepcopy(expected)
    service = fake_picoscope.factory(configuration=configuration)
    assert service.capture_settings == expected_value
    expected["samples"] = 999
    assert service.capture_settings == expected_value
    service.capture_settings["samples"] = 777
    assert expected["samples"] == 999


def test_explicit_empty_mapping_is_an_override_and_missing_fallback_is_reported(fake_picoscope):
    service = fake_picoscope.factory(configuration=_configuration(), capture_settings={})
    assert service.capture_settings == {}  # Required scientific fields are validated by the real service later.
    assert len(fake_picoscope.constructors) == 1
    with pytest.raises(ValueError, match="capture settings"):
        fake_picoscope.factory(configuration={"devices": {"picoscope": {"serial_number": "simulated"}}})
    assert len(fake_picoscope.constructors) == 1


@pytest.mark.parametrize("source", ["device", "global", "acquisition"])
def test_omitted_override_still_rejects_invalid_selected_fallback(fake_picoscope, source):
    configuration = _configuration()
    if source == "device":
        configuration["devices"]["picoscope"]["capture_settings"] = "invalid device capture"
    elif source == "global":
        del configuration["devices"]["picoscope"]["capture_settings"]
        configuration["picoscope_settings"] = ["invalid global capture"]
    else:
        del configuration["devices"]["picoscope"]["capture_settings"]
        del configuration["picoscope_settings"]
        configuration["acquisition"]["picoscope"] = 12
    unchanged = deepcopy(configuration)
    with pytest.raises(ValueError, match="capture settings"):
        fake_picoscope.factory(configuration=configuration)
    assert fake_picoscope.constructors == []
    assert configuration == unchanged


@pytest.mark.parametrize("override", [None, [], "", 0, False])
def test_explicit_nonmapping_never_silently_uses_configured_fallback(fake_picoscope, override):
    configuration = _configuration()
    with pytest.raises((TypeError, ValueError), match="capture_settings|capture settings"):
        fake_picoscope.factory(configuration=configuration, capture_settings=override)
    assert fake_picoscope.constructors == []
    assert configuration == _configuration()


def test_context_preserves_frozen_operation_recipe_configuration_and_ownership(fake_picoscope, tmp_path):
    fake_picoscope.owner_required = True
    coordinator = HardwareCoordinator(tmp_path / "picoscope_factory.lock")
    configuration = _configuration()
    # The maintained hardware config has device identity but no capture recipe.
    del configuration["devices"]["picoscope"]["capture_settings"]
    del configuration["picoscope_settings"]
    del configuration["acquisition"]
    settings = {"capture_settings": {"samples": 64, "channels": {"A": {"range": "5V", "offsets": [0, 2]}}}}
    contexts = ContextFactory(
        configuration_provider=lambda: configuration,
        real_device_factories=device_factories.installed_device_factories(),
        ownership=coordinator, save_root_provider=lambda: tmp_path,
    ).for_experiment("nanosecond_stroboscopy")
    single, dual = contexts.for_mode("single"), contexts.for_mode("dual")
    operation = single.begin_operation(settings, hardware=True, purpose="simulated constructor compatibility")
    frozen_recipe = operation.settings["capture_settings"]
    assert isinstance(frozen_recipe, MappingProxyType)
    assert isinstance(frozen_recipe["channels"]["A"], MappingProxyType)
    configuration["devices"]["picoscope"]["serial_number"] = "later configuration edit"
    configuration["devices"]["picoscope"]["capture_settings"] = {"samples": 12345}
    settings["capture_settings"]["channels"]["A"]["range"] = "later recipe edit"
    try:
        first = single.devices.create("picoscope", operation, capture_settings=frozen_recipe)
        second = single.devices.create("picoscope", operation, capture_settings=frozen_recipe)
        assert first is not second and first.owner == operation.ownership
        assert first.device_config["serial_number"] == second.device_config["serial_number"] == "configured-serial"
        assert first.capture_settings == second.capture_settings == {
            "samples": 64, "channels": {"A": {"range": "5V", "offsets": [0, 2]}}}
        first.capture_settings["channels"]["A"]["range"] = "constructor state edit"
        first.capture_settings["channels"]["A"]["offsets"].append(4)
        assert second.capture_settings["channels"]["A"]["range"] == "5V"
        assert second.capture_settings["channels"]["A"]["offsets"] == [0, 2]
        assert frozen_recipe["channels"]["A"]["range"] == "5V"
        assert frozen_recipe["channels"]["A"]["offsets"] == (0, 2)
        assert "capture_settings" not in operation.configuration["devices"]["picoscope"]

        # Wrong detector scope fails before importing or constructing any service.
        imports = len(fake_picoscope.imports)
        with pytest.raises(ContractError, match="cannot cross"):
            dual.devices.create("picoscope", operation, capture_settings=frozen_recipe)
        assert len(fake_picoscope.imports) == imports
        assert len(fake_picoscope.constructors) == 2
    finally:
        single.ownership.release(operation.ownership, safe_verified=True, preservation_verified=True)
    with pytest.raises(OwnershipError, match="stale"):
        single.devices.create("picoscope", operation, capture_settings=frozen_recipe)
    assert len(fake_picoscope.constructors) == 2
    assert len(fake_picoscope.imports) == imports
