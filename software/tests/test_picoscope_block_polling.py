"""Keep another detector stream serviced during a long hardware block wait."""
from types import SimpleNamespace

import pytest

from control_app.devices import picoscope_service as pico_module


@pytest.mark.parametrize("poll_fails", [False, True])
def test_block_wait_services_stream_and_propagates_poll_failures(monkeypatch, poll_fails):
    events = []
    checks = 0

    def ready(handle, pointer):
        nonlocal checks
        checks += 1
        pointer._obj.value = int(checks == 2)
        events.append("ready" if checks == 2 else "waiting")
        return 0

    def get_values(*args):
        events.append("transfer")
        return 0

    def timebase(handle, number, count, interval, maximum, segment):
        interval._obj.value = 48.0
        maximum._obj.value = 100
        return 0

    pico = pico_module.PicoScopeService({}, {
        "total_samples": 4, "pre_trigger_samples": 1, "timebase": 8, "timeout_s": 1,
    })
    pico._is_open = True
    pico._driver = SimpleNamespace(
        ps5000aSetDataBuffer=lambda *args: 0,
        ps5000aRunBlock=lambda *args: 0,
        ps5000aIsReady=ready,
        ps5000aGetValues=get_values,
        ps5000aGetTimebase2=timebase,
    )
    monkeypatch.setattr(pico, "configure_channels", lambda: None)
    monkeypatch.setattr(pico, "set_external_trigger", lambda: None)
    monkeypatch.setattr(pico, "get_maximum_adc_value", lambda: 32767)
    monkeypatch.setattr(pico_module.time, "sleep", lambda duration: None)

    def poll():
        events.append("poll")
        if poll_fails:
            raise RuntimeError("other detector stream failed")

    if poll_fails:
        with pytest.raises(RuntimeError, match="other detector stream failed"):
            pico.capture_block_data(after_arm=lambda: events.append("armed"), while_waiting=poll)
        assert events == ["armed", "waiting", "poll"]
    else:
        result = pico.capture_block_data(after_arm=lambda: events.append("armed"), while_waiting=poll,
                                         before_transfer=lambda: events.append("outputs off"))
        assert events == ["armed", "waiting", "poll", "ready", "outputs off", "transfer"]
        assert len(result["ch_a_adc"]) == len(result["ch_b_adc"]) == 4
        assert result["sample_interval_ns"] == 48
