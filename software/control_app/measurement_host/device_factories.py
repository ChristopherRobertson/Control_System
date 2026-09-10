"""Lazy, fresh installed-device constructors for the application context.

Factories do not connect, discover, subscribe or share service instances. Real
SDK access still requires an operation's ownership scope at the backend edge.
Simulator factories are injected separately by each test/application session;
they never fall back to these real factories.
"""
from __future__ import annotations

from importlib import import_module
from copy import deepcopy


def installed_device_factories():
    def factory(device_id, module, class_name):
        def create(*, configuration, **kwargs):
            service = getattr(import_module(f"control_app.devices.{module}"), class_name)
            device = deepcopy(configuration.get("devices", {}).get(device_id))
            if not isinstance(device, dict):
                raise ValueError(f"{device_id} is missing from the operation's frozen configuration")
            if device_id.startswith("t660_"):
                return service(device_id, device, **kwargs)
            if device_id == "picoscope":
                capture = (device.get("capture_settings") or configuration.get("picoscope_settings")
                           or configuration.get("acquisition", {}).get("picoscope"))
                if not isinstance(capture, dict):
                    raise ValueError("PicoScope capture settings are missing from the frozen configuration")
                return service(device, deepcopy(capture), **kwargs)
            return service(device, **kwargs)
        return create

    return {
        "mircat": factory("mircat", "mircat_service", "MircatService"),
        "hf2li": factory("hf2li", "hf2li_service", "HF2LIService"),
        "picoscope": factory("picoscope", "picoscope_service", "PicoScopeService"),
        "t660_1": factory("t660_1", "t660_service", "T660Service"),
        "t660_2": factory("t660_2", "t660_service", "T660Service"),
        "opo_iris": factory("opo_iris", "ell15_iris_service", "ELL15IrisService"),
    }
