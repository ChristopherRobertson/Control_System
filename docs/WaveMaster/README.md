# Coherent WaveMaster wavelength working reference

The visible/near-IR wavelength working reference is a Coherent WaveMaster,
catalog number 33-2650. WM-01 qualifies its installed identity, power,
communications, self-test/autocalibration behavior, measurement modes,
repeatability, and uncertainty authority before ATT-01 uses its results.

The WaveMaster identifies a wavelength within its accepted installed envelope.
It does not measure total optical power, apportion power among simultaneous
spectral components, establish the absence of undetected components, or cover
the 355 nm OPO drive. `Multi-Line`, `Saturated`, and `No Signal` are retained as
measurement outcomes and are never coerced into numeric wavelengths.

## Installed configuration gate

The instrument is disconnected while its installed RS-232/USB adapter and
power supply are being established. Every connection-derived field below must
be resolved in `hardware_configuration.yaml` before WM-01 may start:

| Field | Current value |
|---|---|
| Electronically reported serial | `[VALUE_REQUIRED]` |
| Complete `*IDN?` response | `[VALUE_REQUIRED]` |
| Firmware revision | `[VALUE_REQUIRED]` |
| Assigned COM port | `[VALUE_REQUIRED]` |
| USB adapter VID/PID | `[VALUE_REQUIRED]` |
| USB adapter and port-interface serials | `[VALUE_REQUIRED]` |
| USB adapter model | `[VALUE_REQUIRED]` |
| Installed driver provider/version | `[VALUE_REQUIRED]` |
| Installed power-supply identity | `[VALUE_REQUIRED]` |
| Power-supply manufacturer approval basis | `[VALUE_REQUIRED]` |

The visible rear label was reported as `WO 339`. The manual specifies a serial
format of `W` followed by four digits. The label photograph and `*IDN?` response
must be retained independently; no character is normalized by assumption.

Run `python tools/wm01_preflight.py` to evaluate this gate. A successful result
means only that the entry fields are resolved; it does not authorize WM-01,
power application, laser emission, or phase advancement.

After physical inspection of the connected supply and straight-through cable,
`python tools/wavemaster_connection_intake.py --port COMx
--confirm-supply-and-cable-inspected` can collect the native `*IDN?` and serial-
adapter observations without editing configuration. Its output is an intake
record for review, not WM-01 evidence or authorization. Driver, USB-parent, and
power-supply fields still require independent installed-system observation.

## Electrical and software interface

- WaveMaster rear connector: female DB9 RS-232.
- Cable: straight-through, not null modem.
- Required conductors: RXD pin 2, TXD pin 3, GND pin 5, RTS pin 7, CTS pin 8.
- Serial settings: 9600 baud, 8 data bits, no parity, 1 stop bit, hardware
  RTS/CTS flow control.
- Service: `control_app/devices/coherent_wavemaster_service.py`.
- Tests: `tests/test_coherent_wavemaster_service.py` and
  `tests/test_serial_support.py`.

The adapter's stable USB identity is the connection key; its COM assignment is
an observation. The files under `DRIVER_64/` contain FTDI driver 2.08.14 dated
2011 and are retained as supplier material. The driver associated with the
actual installed adapter must be current, signed, compatible, and recorded;
the archived driver is not an operational matching gate.

## Power and physical inspection

The manufacturer documentation specifies 12 VDC, 2.5 A and directs use of the
supplied supply. WM-01 requires a manufacturer-supplied or explicitly
Coherent-approved unit, exact connector/polarity confirmation, strain-free
rear-panel connection, and an inspection record before power is applied. A
loose power connection is a failed entry condition.

The sampling probe, captive fibre, ST connector, wide/narrow acceptance switch,
nosepiece/pickoff, mount, and beam-dump arrangement receive stable component
IDs and photographs. The uncoated sampling plate can alter the transmitted
wavefront, so a retained in-beam or pickoff configuration must be characterized
before it can become part of the measurement path.

## Measurement authority

Manufacturer specifications include 380-1095 nm coverage, 0.005 nm accuracy,
0.001 nm resolution, 3 Hz display update, single-shot-to-CW operation, and
maximum signal bandwidths of 2 nm at 400 nm, 3 nm at 600 nm, and 5 nm at
1000 nm. These are manufacturer-only values until WM-01 establishes their
installed applicability and uncertainty classification.

WM-01 records:

- label and electronic identity agreement;
- power-on self-test and `*TST?` result, including autocalibration-failure bits;
- air/vacuum wavelength units, pulse/CW mode, autocalibration state, intensity
  status, and the native `VAL$` time tag for every retained measurement;
- no-signal, saturation, and naturally observed multi-line behavior;
- communication loss, reconnect, stale/malformed reply handling, exclusive
  ownership, settings restoration, and local control restoration;
- thermal-stability interval, probe position/acceptance setting, wavelength
  repeatability, nominal-source agreement, and any external-reference result;
- a working-reference uncertainty and validity statement that does not claim
  accredited traceability without supporting calibration evidence.

The instrument is ready for an initial functional check after its startup
autocalibration clears. Quantitative stability measurements use the manual's
approximately four-hour best-thermal-stability guidance. Autocalibration stays
enabled except for a prospectively approved critical single-shot interval; any
temporary disable is logged and followed immediately by restoration and
recalibration.

## Manufacturer source register

| File | Role | Document identity |
|---|---|---|
| `WaveMaster_Manual.pdf` | Safety, operation, serial protocol, installed-use guidance and specifications | Coherent WaveMaster User Manual, part 1095245 Rev. AA |
| `Coherent_WaveMaster_33-2650_Datasheet.pdf` | Catalog specifications and probe geometry | Coherent catalog record for 33-2650-000 |
| `WaveMaster_USB_driver_install.pdf` | Supplier USB-serial installation note | Coherent instruction dated 2013 |
| `DRIVER_64/` | Archived FTDI driver package | Driver 2.08.14 dated 2011 |

All supplier files are provenance sources, not executable evidence that the
installed device, adapter, power supply, or measurement authority has passed.
