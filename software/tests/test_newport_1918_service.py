from pathlib import Path
import tempfile
import unittest

from control_app.devices.newport_1918_service import Newport1918


class Newport1918Tests(unittest.TestCase):
    def test_missing_dll_is_reported_before_usb_access(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "Newport USB DLL not found"):
                Newport1918(Path(directory) / "missing.dll")

    def test_query_rejects_state_changing_commands_without_contact(self) -> None:
        meter = object.__new__(Newport1918)
        with self.assertRaisesRegex(ValueError, "must end with"):
            meter.query("PM:Lambda 532")


if __name__ == "__main__":
    unittest.main()
