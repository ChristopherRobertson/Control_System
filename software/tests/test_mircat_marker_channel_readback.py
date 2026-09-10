"""Check the optional per-QCL marker readback against the bundled SDK ABI."""
from ctypes import POINTER, c_float, c_uint8, c_uint16, c_uint32, cast
from types import SimpleNamespace

import pytest

from control_app.devices.mircat_service import MircatCommandError, MircatConfigurationError, MircatService


class MarkerSDK:
    def __init__(self, *, status=0, units=2, start=1949., stop=1941., interval=4., count=3):
        self.status = status
        self.values = units, start, stop, interval, count
        self.channels = []

    def MIRcatSDK_GetWlTrigChanParams(self, channel, units, start, stop, interval, count):
        assert type(channel) is c_uint8
        self.channels.append(channel.value)
        for pointer, value, kind in zip((units, start, stop, interval, count), self.values,
                                        (c_uint8, c_float, c_float, c_float, c_uint16)):
            assert type(pointer._obj) is kind
            cast(pointer, POINTER(kind)).contents.value = value
        return self.status


@pytest.mark.parametrize('units,start,stop,interval,count,units_name', [
    (2, 1949., 1941., 4., 3, 'cm^-1'),
    (1, 5., 5.5, .125, 65535, 'microns'),
])
def test_channel_marker_targets_and_native_uint16_count_are_read_without_setting(
        units, start, stop, interval, count, units_name):
    service = MircatService({})
    service._sdk = MarkerSDK(units=units, start=start, stop=stop, interval=interval, count=count)
    result = service.get_wavelength_trigger_channel_params(1)
    assert result == {'channel': 1, 'units': units, 'units_name': units_name,
                      'start': start, 'stop': stop, 'interval': interval, 'num_triggers': count}
    assert service._sdk.channels == [1]


@pytest.mark.parametrize('channel', [-1, 0, 256, True, False, 1.5, '1', None])
def test_invalid_channel_is_rejected_before_any_sdk_call(channel):
    service = MircatService({})
    service._sdk = MarkerSDK()
    with pytest.raises(ValueError, match='integer from 1 through 255'):
        service.get_wavelength_trigger_channel_params(channel)
    assert not service._sdk.channels


def test_sdk_error_never_returns_partially_populated_target_identity():
    service = MircatService({})
    service._sdk = MarkerSDK(status=100)
    with pytest.raises(MircatCommandError, match='COMM_ERROR'):
        service.get_wavelength_trigger_channel_params(1)
    assert service._sdk.channels == [1]


def test_absent_optional_channel_entrypoint_reports_unavailable():
    service = MircatService({})
    service._sdk = SimpleNamespace()
    with pytest.raises(MircatConfigurationError, match='does not provide MIRcatSDK_GetWlTrigChanParams'):
        service.get_wavelength_trigger_channel_params(1)


@pytest.mark.parametrize('optional_present', [False, True])
def test_sdk_binding_is_optional_and_matches_uint16_output_signature(optional_present):
    class BindingSDK:
        def __init__(self):
            self.functions = {}
        def __getattr__(self, name):
            if name == 'MIRcatSDK_GetWlTrigChanParams' and not optional_present:
                raise AttributeError(name)
            return self.functions.setdefault(name, SimpleNamespace())
    service = MircatService({})
    service._sdk = BindingSDK()
    service._bind_functions()
    function = service._sdk.functions.get('MIRcatSDK_GetWlTrigChanParams')
    if optional_present:
        assert function.argtypes == [c_uint8, POINTER(c_uint8), POINTER(c_float), POINTER(c_float),
                                      POINTER(c_float), POINTER(c_uint16)]
        assert function.restype is c_uint32
    else:
        assert function is None
