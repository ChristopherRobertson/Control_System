from collections import deque
from types import SimpleNamespace
import unittest

from control_app.devices.ell15_iris_service import (
    ELL15CommunicationError,
    ELL15IrisService,
    ELL15MotionAuthorizationError,
    parse_identity_reply,
    parse_position_reply,
)


IRIS_CONFIG = {
    "preferred_port": "COM5",
    "usb_vid_hex": "0403",
    "usb_pid_hex": "6015",
    "usb_serial_number": "DP06U124",
    "port_serial_number": "DP06U124A",
    "baudrate": 9600,
    "device_address": "0",
    "serial_number": "11500020",
    "protocol_model_code_hex": "0F",
    "minimum_aperture_mm": 1.0,
    "maximum_aperture_mm": 11.5,
    "encoder_counts_per_mm": 1000,
    "minimum_incremental_motion_mm": 0.01,
}


class FakeSerial:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.lines: deque[bytes] = deque()
        self.closed = False

    def reset_input_buffer(self):
        self.lines.clear()

    def write(self, payload: bytes):
        command = payload.decode("ascii")
        replies = {
            "0in": b"0IN0F11500020202410212CEC000003E8\r\n",
            "0gp": b"0PO00002CEC\r\n",
            "0ma00002710": b"0PO00002710\r\n",
        }
        if command in replies:
            self.lines.append(replies[command])
        return len(payload)

    def flush(self):
        return None

    def readline(self):
        return self.lines.popleft() if self.lines else b""

    def close(self):
        self.closed = True


class ELL15IrisServiceTests(unittest.TestCase):
    def test_parses_live_identity_format(self) -> None:
        result = parse_identity_reply("0IN0F11500020202410212CEC000003E8")
        self.assertEqual(result.serial_number, "11500020")
        self.assertEqual(result.maximum_aperture_mm, 11.5)
        self.assertEqual(result.firmware_field_hex, "10")

    def test_parses_signed_position(self) -> None:
        self.assertEqual(parse_position_reply("0POFFFFFFFF"), -1)

    def test_malformed_identity_is_rejected(self) -> None:
        with self.assertRaises(ELL15CommunicationError):
            parse_identity_reply("0INBAD")

    def test_identity_bound_connect_and_readback(self) -> None:
        holder = {}

        def factory(**kwargs):
            holder["serial"] = FakeSerial(**kwargs)
            return holder["serial"]

        service = ELL15IrisService(
            dict(IRIS_CONFIG),
            serial_factory=factory,
            ports_provider=lambda: [
                SimpleNamespace(
                    device="COM15",
                    serial_number="DP06U124A",
                    vid=0x0403,
                    pid=0x6015,
                )
            ],
        )
        service.connect()
        self.assertEqual(service.identify().serial_number, "11500020")
        self.assertEqual(service.get_aperture_mm(), 11.5)
        self.assertEqual(holder["serial"].kwargs["port"], "COM15")
        service.close()
        self.assertTrue(holder["serial"].closed)

    def test_query_only_session_refuses_motion(self) -> None:
        service = ELL15IrisService(dict(IRIS_CONFIG), allow_motion=False)
        with self.assertRaises(ELL15MotionAuthorizationError):
            service.set_aperture_mm(10.0)

    def test_motion_uses_counts_and_open_side_approach(self) -> None:
        fake = FakeSerial()
        service = ELL15IrisService(
            dict(IRIS_CONFIG), allow_motion=True, serial_factory=lambda **_: fake
        )
        service._serial = fake
        self.assertEqual(service.set_aperture_mm(10.0), 10.0)


if __name__ == "__main__":
    unittest.main()
