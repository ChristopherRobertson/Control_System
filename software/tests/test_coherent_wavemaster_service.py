import unittest
from types import SimpleNamespace

from control_app.devices.coherent_wavemaster_service import (
    CoherentWaveMasterService,
    WaveMasterCommunicationError,
    WaveMasterConfigurationError,
    parse_identity_reply,
    parse_measurement_reply,
)


class FakeWaveMasterSerial:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.replies: list[bytes] = []
        self.commands: list[str] = []
        self.closed = False

    def reset_input_buffer(self) -> None:
        self.replies.clear()

    def write(self, payload: bytes) -> int:
        command = payload.decode("ascii").rstrip("\r")
        self.commands.append(command)
        if command == "*IDN?":
            self.replies.append(
                b"Coherent Inc.,WaveMaster,W0339,A1.V2.3\r\n"
            )
        elif command == "MDE?":
            self.replies.append(b"MDE$P\r\n")
        return len(payload)

    def flush(self) -> None:
        return None

    def readline(self) -> bytes:
        return self.replies.pop(0) if self.replies else b""

    def close(self) -> None:
        self.closed = True


class CoherentWaveMasterServiceTests(unittest.TestCase):
    def test_disconnected_configuration_blocks_phase_entry(self) -> None:
        config = {
            "serial_number": "[VALUE_REQUIRED]",
            "preferred_port": "[VALUE_REQUIRED]",
            "phase_entry_required_fields": ["serial_number", "preferred_port"],
        }
        service = CoherentWaveMasterService(config)
        self.assertEqual(
            service.phase_entry_gaps(), ["serial_number", "preferred_port"]
        )
        with self.assertRaisesRegex(WaveMasterConfigurationError, "WM-01 entry"):
            service.assert_phase_entry_ready()

    def test_identity_reply(self) -> None:
        identity = parse_identity_reply("Coherent Inc.,WaveMaster,W0339,A1.V2.3")
        self.assertEqual(identity.serial_number, "W0339")
        self.assertEqual(identity.firmware_revision, "A1.V2.3")

    def test_connect_resolves_adapter_and_verifies_instrument_identity(self) -> None:
        fake = FakeWaveMasterSerial()
        config = {
            "phase_entry_required_fields": [],
            "preferred_port": "COM5",
            "usb_vid_hex": "0403",
            "usb_pid_hex": "6001",
            "usb_serial_number": "WMUSB01",
            "port_serial_number": "WMUSB01A",
            "serial_number": "W0339",
            "firmware_revision": "A1.V2.3",
            "model_number": "WaveMaster",
        }
        service = CoherentWaveMasterService(
            config,
            serial_factory=lambda **kwargs: (
                setattr(fake, "kwargs", kwargs) or fake
            ),
            ports_provider=lambda: [
                SimpleNamespace(
                    device="COM11",
                    serial_number="WMUSB01A",
                    vid=0x0403,
                    pid=0x6001,
                )
            ],
        )
        service.connect()
        self.assertEqual(fake.kwargs["port"], "COM11")
        self.assertTrue(fake.kwargs["rtscts"])
        service.close()
        self.assertTrue(fake.closed)

    def test_valid_measurement_reply(self) -> None:
        measurement = parse_measurement_reply("VAL$12345,540.012")
        self.assertEqual(measurement.time_tag_10ms, 12345)
        self.assertEqual(measurement.value, 540.012)
        self.assertEqual(measurement.quality, "valid")

    def test_multiline_is_not_converted_to_a_number(self) -> None:
        measurement = parse_measurement_reply("VAL$12346,Multi-Line")
        self.assertIsNone(measurement.value)
        self.assertEqual(measurement.quality, "multi_line")

    def test_unknown_measurement_text_is_rejected(self) -> None:
        with self.assertRaises(WaveMasterCommunicationError):
            parse_measurement_reply("VAL$12347,Maybe")

    def test_setting_changes_require_explicit_session_authority(self) -> None:
        service = CoherentWaveMasterService({})
        with self.assertRaisesRegex(WaveMasterConfigurationError, "allow_settings"):
            service.set_mode("P")

    def test_period_below_documented_minimum_is_rejected(self) -> None:
        service = CoherentWaveMasterService({}, allow_settings=True)
        with self.assertRaisesRegex(WaveMasterConfigurationError, "at least 5"):
            service.set_period_s(4)

    def test_setting_command_is_verified_by_separate_query(self) -> None:
        fake = FakeWaveMasterSerial()
        service = CoherentWaveMasterService({}, allow_settings=True)
        service._serial = fake
        service.set_mode("P")
        self.assertEqual(fake.commands, ["MDE P", "MDE?"])


if __name__ == "__main__":
    unittest.main()
