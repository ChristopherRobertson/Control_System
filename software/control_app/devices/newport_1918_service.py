"""Python 3 interface for Newport 1918-R meters using Newport ``usbdll.dll``.

The DLL call sequence is based on Newport's ``NewpDll.h`` and the historical
``plasmon360/python_newport_1918_powermeter`` example.  This implementation is
64-bit/Python-3 safe and intentionally exposes read-only queries by default.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_DLL = Path(r"C:\Program Files\Newport\Newport USB Driver\Bin\usbdll.dll")
DEFAULT_PRODUCT_ID = 0xCEC7


class NewportCommunicationError(RuntimeError):
    """Raised when the Newport USB API reports a communication failure."""


@dataclass(frozen=True)
class NewportInstrument:
    device_id: int
    model: int
    serial: int


class Newport1918:
    """Context-managed connection to a Newport 1918-R.

    Construction opens matching USB devices.  ``close``/context exit always
    releases the Newport DLL's ownership.  ``query`` sends commands ending in
    ``?`` only; state-changing commands are deliberately not exposed here.
    """

    def __init__(
        self,
        dll_path: Path | str = DEFAULT_DLL,
        product_id: int = DEFAULT_PRODUCT_ID,
        response_delay_s: float = 0.25,
    ) -> None:
        self.dll_path = Path(dll_path)
        self.product_id = product_id
        self.response_delay_s = response_delay_s
        if not self.dll_path.is_file():
            raise FileNotFoundError(f"Newport USB DLL not found: {self.dll_path}")
        self._lib = ctypes.WinDLL(str(self.dll_path))
        self._configure_signatures()
        self._closed = False
        count = ctypes.c_int()
        status = self._lib.newp_usb_open_devices(
            self.product_id, True, ctypes.byref(count)
        )
        if status != 0:
            self._closed = True
            raise NewportCommunicationError(
                f"newp_usb_open_devices failed with status {status}"
            )
        if count.value < 1:
            self.close()
            raise NewportCommunicationError("No matching Newport USB meter found")
        self.instruments = tuple(self._get_instruments(count.value))
        self.instrument = self.instruments[0]

    def _configure_signatures(self) -> None:
        lib = self._lib
        lib.newp_usb_open_devices.argtypes = [
            ctypes.c_int,
            ctypes.c_bool,
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.newp_usb_open_devices.restype = ctypes.c_long
        lib.GetInstrumentList.argtypes = [
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.GetInstrumentList.restype = ctypes.c_long
        lib.newp_usb_send_ascii.argtypes = [
            ctypes.c_long,
            ctypes.POINTER(ctypes.c_char),
            ctypes.c_ulong,
        ]
        lib.newp_usb_send_ascii.restype = ctypes.c_long
        lib.newp_usb_get_ascii.argtypes = [
            ctypes.c_long,
            ctypes.POINTER(ctypes.c_char),
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        lib.newp_usb_get_ascii.restype = ctypes.c_long
        lib.newp_usb_uninit_system.argtypes = []
        lib.newp_usb_uninit_system.restype = None

    def _get_instruments(self, count: int) -> Iterable[NewportInstrument]:
        ids = (ctypes.c_int * count)()
        models = (ctypes.c_int * count)()
        serials = (ctypes.c_int * count)()
        array_size = ctypes.c_int(count)
        status = self._lib.GetInstrumentList(
            ids, models, serials, ctypes.byref(array_size)
        )
        if status != 0:
            self.close()
            raise NewportCommunicationError(
                f"GetInstrumentList failed with status {status}"
            )
        for index in range(min(array_size.value, count)):
            yield NewportInstrument(ids[index], models[index], serials[index])

    def query(self, command: str) -> str:
        """Run one non-mutating query and return its stripped response."""
        command = command.strip()
        if not command.endswith("?"):
            raise ValueError("Read-only query must end with '?'")
        payload = ctypes.create_string_buffer(command.encode("ascii"))
        status = self._lib.newp_usb_send_ascii(
            self.instrument.device_id, payload, len(command)
        )
        if status != 0:
            raise NewportCommunicationError(
                f"send failed for {command!r} with status {status}"
            )
        time.sleep(self.response_delay_s)
        response = ctypes.create_string_buffer(4096)
        bytes_read = ctypes.c_ulong()
        status = self._lib.newp_usb_get_ascii(
            self.instrument.device_id,
            response,
            len(response),
            ctypes.byref(bytes_read),
        )
        if status != 0:
            raise NewportCommunicationError(
                f"read failed for {command!r} with status {status}"
            )
        return response.raw[: bytes_read.value].decode("ascii", errors="replace").strip()

    def identity_snapshot(self) -> dict[str, object]:
        """Return the bounded read-only identity/configuration snapshot for OM-01."""
        commands = {
            "idn": "*IDN?",
            "usb_address": "ADDR?",
            "detector_model": "PM:DETMODEL?",
            "detector_serial": "PM:DETSN?",
            "attenuator_serial": "PM:ATTSN?",
            "minimum_wavelength_nm": "PM:MIN:Lambda?",
            "maximum_wavelength_nm": "PM:MAX:Lambda?",
            "selected_wavelength_nm": "PM:Lambda?",
            "measurement_mode": "PM:MODE?",
            "autorange": "PM:AUTO?",
            "range": "PM:RANGE?",
            "filter": "PM:FILT?",
            "zero_value_w": "PM:ZEROVAL?",
        }
        return {
            "dll_path": str(self.dll_path),
            "dll_version": self._dll_version(),
            "product_id_hex": f"0x{self.product_id:04X}",
            "device_id": self.instrument.device_id,
            "model_number": self.instrument.model,
            "meter_serial": self.instrument.serial,
            "queries": {name: self.query(command) for name, command in commands.items()},
        }

    def _dll_version(self) -> str:
        class FixedFileInfo(ctypes.Structure):
            _fields_ = [
                ("signature", ctypes.c_uint32),
                ("struct_version", ctypes.c_uint32),
                ("file_version_ms", ctypes.c_uint32),
                ("file_version_ls", ctypes.c_uint32),
                ("product_version_ms", ctypes.c_uint32),
                ("product_version_ls", ctypes.c_uint32),
                ("file_flags_mask", ctypes.c_uint32),
                ("file_flags", ctypes.c_uint32),
                ("file_os", ctypes.c_uint32),
                ("file_type", ctypes.c_uint32),
                ("file_subtype", ctypes.c_uint32),
                ("file_date_ms", ctypes.c_uint32),
                ("file_date_ls", ctypes.c_uint32),
            ]

        version = ctypes.windll.version
        size = version.GetFileVersionInfoSizeW(str(self.dll_path), None)
        if not size:
            return "UNKNOWN"
        buffer = ctypes.create_string_buffer(size)
        version.GetFileVersionInfoW(str(self.dll_path), 0, size, buffer)
        value = ctypes.c_void_p()
        length = ctypes.c_uint()
        version.VerQueryValueW(buffer, "\\", ctypes.byref(value), ctypes.byref(length))
        info = ctypes.cast(value, ctypes.POINTER(FixedFileInfo)).contents
        major = info.file_version_ms >> 16
        minor = info.file_version_ms & 0xFFFF
        build = info.file_version_ls >> 16
        revision = info.file_version_ls & 0xFFFF
        parts = [major, minor, build, revision]
        while len(parts) > 3 and parts[-1] == 0:
            parts.pop()
        return ".".join(str(part) for part in parts)

    def close(self) -> None:
        if not self._closed:
            self._lib.newp_usb_uninit_system()
            self._closed = True

    def __enter__(self) -> "Newport1918":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Newport 1918-R USB query")
    parser.add_argument("--dll", type=Path, default=DEFAULT_DLL)
    parser.add_argument(
        "--query",
        action="append",
        help="Read-only command ending in '?'; repeat for multiple queries",
    )
    args = parser.parse_args()
    with Newport1918(args.dll) as meter:
        if args.query:
            result = {query: meter.query(query) for query in args.query}
        else:
            result = meter.identity_snapshot()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
