from types import SimpleNamespace
import unittest

from control_app.devices.serial_support import (
    SerialIdentityError,
    resolve_serial_port,
    unresolved_fields,
)


class SerialSupportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "preferred_port": "COM5",
            "usb_vid_hex": "0403",
            "usb_pid_hex": "6015",
            "usb_serial_number": "DP06U124",
            "port_serial_number": "DP06U124A",
        }

    def test_resolves_by_adapter_identity_not_com_assignment(self) -> None:
        ports = [
            SimpleNamespace(
                device="COM12", serial_number="DP06U124A", vid=0x0403, pid=0x6015
            )
        ]
        self.assertEqual(resolve_serial_port(self.config, ports=ports), "COM12")

    def test_present_preferred_port_with_wrong_identity_is_rejected(self) -> None:
        ports = [
            SimpleNamespace(
                device="COM5", serial_number="OTHER", vid=0x0403, pid=0x6015
            )
        ]
        with self.assertRaisesRegex(SerialIdentityError, "does not match"):
            resolve_serial_port(self.config, ports=ports)

    def test_value_required_fields_are_reported(self) -> None:
        config = {"serial_number": "[VALUE_REQUIRED]", "preferred_port": ""}
        self.assertEqual(
            unresolved_fields(config, ["serial_number", "preferred_port"]),
            ["serial_number", "preferred_port"],
        )


if __name__ == "__main__":
    unittest.main()
