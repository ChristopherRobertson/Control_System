"""Serial lifecycle checks without opening hardware."""
import pytest
from control_app.devices.t660_service import T660Service, T660Error


def setup_transport(monkeypatch):
    import serial
    from control_app.measurement_host import ownership
    monkeypatch.setattr(ownership, "require_hardware_owner", lambda service: None)
    opened = []
    class Port:
        is_open = True
        def close(self):
            self.is_open = False
    def open_port(**kwargs):
        assert not any(port.is_open for port in opened), "exclusive port already held"
        port = Port()
        opened.append(port)
        return port
    monkeypatch.setattr(serial, "Serial", open_port)
    service = T660Service("t660_2", {"preferred_port":"COM7", "baudrate":38400})
    return service, opened


def test_repeated_connect_reuses_open_serial_port(monkeypatch):
    service, opened = setup_transport(monkeypatch)
    initialized = []
    monkeypatch.setattr(service, "_set_p500_session", lambda: initialized.append(True))
    service.connect()
    service.connect()
    assert len(opened) == len(initialized) == 1
    service.close()
    service.connect()
    assert len(opened) == 2
    service.close()


def test_protocol_failure_closes_port_before_retry(monkeypatch):
    service, opened = setup_transport(monkeypatch)
    def fail():
        raise RuntimeError("initialization failed")
    monkeypatch.setattr(service, "_set_p500_session", fail)
    with pytest.raises(RuntimeError, match="initialization failed"):
        service.connect()
    assert not opened[0].is_open and service._serial is None
    monkeypatch.setattr(service, "_set_p500_session", lambda: None)
    service.connect()
    assert len(opened) == 2 and opened[1].is_open
    service.close()


def test_access_denied_reports_port_and_preserves_original_error(monkeypatch):
    import serial
    service, opened = setup_transport(monkeypatch)
    original = serial.SerialException("could not open port 'COM7': PermissionError(13, 'Access is denied.')")
    def fail(**kwargs):
        raise original
    monkeypatch.setattr(serial, "Serial", fail)
    with pytest.raises(T660Error, match="Windows denied access to COM7") as error:
        service.connect()
    assert error.value.__cause__ is original
    assert service._serial is None and not opened
