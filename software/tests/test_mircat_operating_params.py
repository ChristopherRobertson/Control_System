from ctypes import c_bool, c_float, c_uint8, c_uint16, c_uint32, POINTER
from types import SimpleNamespace
import pytest
from control_app.devices.mircat_service import MircatService, MircatCommandError, MircatConfigurationError


class SDK:
    def __init__(self, status=0):
        self.status = status
        self.calls = []
        self.values = {
            'MIRcatSDK_GetQCLOperatingMode': (c_uint8, 2),
            'MIRcatSDK_GetQclSetTemperature': (c_float, 21.5),
            'MIRcatSDK_isCwAllowed': (c_bool, True),
            'MIRcatSDK_GetQCLMinCwCurrent': (c_uint16, 100),
            'MIRcatSDK_GetQCLMaxCwCurrent': (c_uint16, 750),
            'MIRcatSDK_GetQCLPulseRate': (c_float, 1999999),
            'MIRcatSDK_GetQCLPulseWidth': (c_float, 149),
            'MIRcatSDK_GetQCLCurrent': (c_float, 749),
        }
    def MIRcatSDK_SetAllQclParams(self, *args):
        assert [type(x) for x in args] == [c_uint8, c_float, c_float, c_float, c_float, c_uint8, c_bool]
        self.calls.append(('set', [x.value for x in args]))
        return self.status
    def __getattr__(self, name):
        if name not in self.values:
            raise AttributeError(name)
        def read(qcl, out):
            kind, value = self.values[name]
            assert type(qcl) is c_uint8 and qcl.value == 1
            assert type(out._obj) is kind
            out._obj.value = value
            self.calls.append(name)
            return self.status
        return read


def service(status=0):
    unit = MircatService({})
    unit._sdk = SDK(status)
    return unit


def test_modes_limits_and_fresh_set_readbacks():
    unit = service()
    assert unit.is_cw_allowed(1) is True
    assert unit.get_qcl_cw_current_limits(1) == (100, 750)
    result = unit.set_qcl_operating_params(1, pulse_rate_hz=2e6, pulse_width_ns=150,
        current_ma=750, temperature_c=22, laser_mode=2)
    assert result == dict(qcl=1, pulse_rate_hz=1999999, pulse_width_ns=149,
        current_ma=749, temperature_c=21.5, laser_mode=2)
    assert unit._sdk.calls[3] == ('set', [1, 2e6, 150, 750, 22, 2, True])


@pytest.mark.parametrize('qcl', [0, 5, -1, True, 1.5, '1'])
def test_invalid_qcl_does_not_reach_sdk(qcl):
    unit = service()
    with pytest.raises(ValueError):
        unit.get_qcl_operating_mode(qcl)
    assert unit._sdk.calls == []


@pytest.mark.parametrize('field,value', [('laser_mode', 0), ('laser_mode', True), ('pulse_rate_hz', float('nan')), ('temperature_c', float('inf')), ('current_ma', 1e100)])
def test_invalid_parameters_do_not_reach_sdk(field, value):
    unit = service()
    params = dict(pulse_rate_hz=2e6, pulse_width_ns=150, current_ma=750, temperature_c=22, laser_mode=2)
    params[field] = value
    with pytest.raises(ValueError):
        unit.set_qcl_operating_params(1, **params)
    assert unit._sdk.calls == []


def test_failed_set_has_no_readback_or_fallback_write():
    unit = service(96)
    with pytest.raises(MircatCommandError, match='CW_NOT_ALLOWED'):
        unit.set_qcl_operating_params(1, pulse_rate_hz=2e6, pulse_width_ns=150,
            current_ma=750, temperature_c=22, laser_mode=2)
    assert len(unit._sdk.calls) == 1


def test_missing_optional_api_is_explicit():
    unit = service()
    unit._sdk = SimpleNamespace()
    with pytest.raises(MircatConfigurationError, match='GetQCLOperatingMode'):
        unit.get_qcl_operating_mode(1)


def test_binding_matches_bundled_sdk():
    class BindSDK:
        def __init__(self): self.functions = {}
        def __getattr__(self, name): return self.functions.setdefault(name, SimpleNamespace())
    unit = service()
    unit._sdk = BindSDK()
    unit._bind_functions()
    for name, kind in [('MIRcatSDK_GetQCLOperatingMode', c_uint8), ('MIRcatSDK_GetQclSetTemperature', c_float),
                       ('MIRcatSDK_isCwAllowed', c_bool), ('MIRcatSDK_GetQCLMinCwCurrent', c_uint16),
                       ('MIRcatSDK_GetQCLMaxCwCurrent', c_uint16)]:
        assert unit._sdk.functions[name].argtypes == [c_uint8, POINTER(kind)]
        assert unit._sdk.functions[name].restype is c_uint32
    assert unit._sdk.functions['MIRcatSDK_SetAllQclParams'].argtypes == [c_uint8, c_float, c_float, c_float, c_float, c_uint8, c_bool]
