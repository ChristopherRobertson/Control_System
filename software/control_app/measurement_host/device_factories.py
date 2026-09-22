"""Lazy installed-device constructors for the application context.

Factories do not connect, discover or subscribe. Desktop operations lease the
application's retained transports; standalone callers receive fresh services.
Real SDK access still requires an operation's ownership scope at the backend edge.
Simulator factories are injected separately by each test/application session;
they never fall back to these real factories.
"""
from __future__ import annotations

from collections.abc import Mapping
from importlib import import_module
from copy import deepcopy

from .context import freeze_data, thaw_data


def installed_device_factories(*, shared=True):
    """Return scoped constructors; PicoScope accepts explicit capture_settings.

    Pass a module's frozen operation settings for a per-operation PicoScope
    recipe. The explicit mapping is detached, including nested frozen values;
    omission retains the installed configuration's capture-setting fallbacks.
    """
    def factory(device_id, module, class_name):
        def create(*, configuration, **kwargs):
            service = getattr(import_module(f"control_app.devices.{module}"), class_name)
            device = deepcopy(configuration.get("devices", {}).get(device_id))
            if not isinstance(device, dict):
                raise ValueError(f"{device_id} is missing from the operation's frozen configuration")
            if device_id.startswith("t660_"):
                return service(device_id, device, **kwargs)
            if device_id == "picoscope":
                if "capture_settings" in kwargs:
                    capture = kwargs.pop("capture_settings")
                    if not isinstance(capture, Mapping):
                        raise ValueError("PicoScope capture_settings override must be a mapping")
                    capture = thaw_data(freeze_data(capture))
                else:
                    capture = (device.get("capture_settings") or configuration.get("picoscope_settings")
                               or configuration.get("acquisition", {}).get("picoscope"))
                    if not isinstance(capture, dict):
                        raise ValueError("PicoScope capture settings are missing from the frozen configuration")
                    capture = deepcopy(capture)
                return service(device, capture, **kwargs)
            return service(device, **kwargs)
        return create

    factories = {
        "mircat": factory("mircat", "mircat_service", "MircatService"),
        "hf2li": factory("hf2li", "hf2li_service", "HF2LIService"),
        "picoscope": factory("picoscope", "picoscope_service", "PicoScopeService"),
        "t660_1": factory("t660_1", "t660_service", "T660Service"),
        "t660_2": factory("t660_2", "t660_service", "T660Service"),
        "opo_iris": factory("opo_iris", "ell15_iris_service", "ELL15IrisService"),
    }
    if not shared:
        return factories
    from .application_session import shared_device
    def persistent(name, constructor):
        def create(*, configuration, **kwargs):
            if not isinstance(configuration.get("devices", {}).get(name), Mapping):
                raise ValueError(f"{name} is missing from the operation's frozen configuration")
            attributes = {key: value for key, value in kwargs.items()
                          if key in {"command_log", "capture_settings", "allow_motion"}}
            if name == "opo_iris":
                attributes["allow_motion"] = bool(kwargs.get("allow_motion", False))
            if "capture_settings" in attributes:
                capture = attributes["capture_settings"]
                if not isinstance(capture, Mapping):
                    raise ValueError("PicoScope capture_settings override must be a mapping")
                attributes["capture_settings"] = thaw_data(freeze_data(capture))
            return shared_device(name, lambda: constructor(configuration=configuration, **kwargs), **attributes)
        return create
    return {name: persistent(name, constructor) for name, constructor in factories.items()}
