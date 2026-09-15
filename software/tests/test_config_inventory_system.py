"""Configuration passed to the application retains detector topology."""
import json
import pytest
from control_app.config_loader import ConfigInventory, build_config_inventory, load_hardware_config


def test_real_inventory_roundtrip_retains_detached_system():
    config, path, _ = load_hardware_config()
    inventory = build_config_inventory(config, path)
    exported = inventory.to_dict()
    assert exported['system']['default_detector_connections'] == config['system']['default_detector_connections']
    restored = ConfigInventory(**json.loads(json.dumps(exported)))
    assert restored.system == inventory.system
    config['system']['default_detector_connections'] = ['changed source']
    exported['system']['default_detector_connections'] = ['changed export']
    assert inventory.system == restored.system
    assert inventory.system['default_detector_connections'] != ['changed source']
    assert inventory.system['default_detector_connections'] != ['changed export']


def test_old_inventory_constructor_still_accepts_missing_system():
    config, path, _ = load_hardware_config()
    data = build_config_inventory(config, path).to_dict()
    data.pop('system')
    first, second = ConfigInventory(**data), ConfigInventory(**data)
    first.system['test'] = True
    assert second.system == {}


@pytest.mark.parametrize('value', [None, [], 'invalid'])
def test_malformed_system_is_reported_without_breaking_legacy_inventory(value):
    config, path, _ = load_hardware_config()
    config['system'] = value
    inventory = build_config_inventory(config, path)
    assert inventory.system == {}
    assert 'system must be a mapping when present' in inventory.warnings


def test_missing_system_is_backward_compatible():
    config, path, _ = load_hardware_config()
    config.pop('system', None)
    inventory = build_config_inventory(config, path)
    assert inventory.system == {}
    assert 'system must be a mapping when present' not in inventory.warnings
