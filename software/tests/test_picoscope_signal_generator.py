from ctypes import c_int16, cast, POINTER
import unittest

from control_app.devices.picoscope_service import (
    PicoScopeConfigurationError,
    PicoScopeService,
)


class FakeDriver:
    def __init__(self) -> None:
        self.calls = []

    def ps5000aSetSigGenBuiltInV2(self, *args):
        self.calls.append(args)
        return 0

    def ps5000aMaximumValue(self, _handle, maximum):
        cast(maximum, POINTER(c_int16))[0] = 32512
        return 0


def service_with_fake_driver() -> tuple[PicoScopeService, FakeDriver]:
    service = PicoScopeService({}, {})
    driver = FakeDriver()
    service._driver = driver
    service._handle = c_int16(7)
    service._is_open = True
    return service, driver


class PicoScopeSignalGeneratorTests(unittest.TestCase):
    def test_disable_signal_generator_programs_zero_output(self) -> None:
        service, driver = service_with_fake_driver()

        result = service.disable_signal_generator()

        self.assertEqual(result["electrical_state"], "PROGRAMMED_ZERO_OUTPUT")
        self.assertEqual(result["pk_to_pk_v"], 0.0)
        self.assertEqual(result["offset_v"], 0.0)
        self.assertEqual(len(driver.calls), 1)
        call = driver.calls[0]
        self.assertEqual(call[1].value, 0)
        self.assertEqual(call[2].value, 0)

    def test_configure_builtin_signal_generator_preserves_requested_values(self) -> None:
        service, driver = service_with_fake_driver()

        result = service.configure_builtin_signal_generator(
            waveform="sine", frequency_hz=2_000_000.25, pk_to_pk_v=0.05, offset_v=0.001
        )

        self.assertEqual(result["frequency_hz"], 2_000_000.25)
        self.assertEqual(result["pk_to_pk_v"], 0.05)
        self.assertEqual(result["offset_v"], 0.001)
        call = driver.calls[0]
        self.assertEqual(call[1].value, 1000)
        self.assertEqual(call[2].value, 50000)
        self.assertEqual(call[4].value, 2_000_000.25)

    def test_configure_builtin_signal_generator_rejects_voltage_outside_capability(self) -> None:
        service, _ = service_with_fake_driver()

        with self.assertRaisesRegex(PicoScopeConfigurationError, "exceeds"):
            service.configure_builtin_signal_generator(
                waveform="sine", frequency_hz=1.0, pk_to_pk_v=4.0, offset_v=0.1
            )

    def test_reads_active_resolution_adc_full_scale(self) -> None:
        service, _ = service_with_fake_driver()

        self.assertEqual(service.get_maximum_adc_value(), 32512)


if __name__ == "__main__":
    unittest.main()
