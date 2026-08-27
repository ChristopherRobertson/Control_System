# Coherent WaveMaster wavelength working reference

The visible/near-IR wavelength working reference is a Coherent WaveMaster,
catalog number 33-2650. WM-01 qualifies its installed identity,
communications, self-test/autocalibration behavior, measurement modes,
repeatability, and uncertainty authority before ATT-01 uses its results.

Current disposition (2026-08-25): the installed WaveMaster passed WM-01
electronic checks but failed optical qualification. Its front-panel fibre
receptacle moved relative to the panel, red-source outcomes depended on
connector position, and the instrument did not respond to the 540 nm OPO
output despite gross fibre continuity. It has no measurement authority. WM-01
remains open and deferred pending a replacement spectrometer; the intake and
failed qualification evidence remain retained and are not a bypass.

The WaveMaster identifies a wavelength within its accepted installed envelope.
It does not measure total optical power, apportion power among simultaneous
spectral components, establish the absence of undetected components, or cover
the 355 nm OPO drive. `Multi-Line`, `Saturated`, and `No Signal` are retained as
measurement outcomes and are never coerced into numeric wavelengths.

## Installed configuration gate

Read-only connection intake on 2026-08-20 established native communication and
the instrument/adapter fields below. The operator confirms that the connected
instrument works safely. Coherent support declared the WaveMaster obsolete with
no service, replacement parts, or additional documentation available. All
connection-derived WM-01 entry fields are resolved:

| Field | Current value |
|---|---|
| Electronically reported serial | `W0339` |
| Complete `*IDN?` response | `*IDN$ Coherent Inc,WaveMaster,W0339,A1.1V1.6` |
| Firmware revision | `A1.1V1.6` |
| Assigned COM port | `COM8` |
| USB adapter VID/PID | `0403:6001` |
| USB adapter and port-interface serials | `BG03ADXP`; `BG03ADXPA` |
| USB adapter model | FTDI FT232R USB UART |
| Installed driver provider/version | FTDI `2.12.36.20` |
| Operational status | Operator-confirmed working safely |

The visible rear label was reported as `WO 339`; the electronic response is
`W0339`. The label photograph and `*IDN?` response remain independent evidence,
and the discrepancy is not normalized by assumption.

Run `python software/tools/wm01_preflight.py` to evaluate this gate. A successful result
means only that the entry fields are resolved; it does not authorize WM-01,
laser emission, or phase advancement.

After inspection of the straight-through cable,
`python software/tools/wavemaster_connection_intake.py --port COMx
--confirm-cable-inspected` can collect the native `*IDN?` and serial-
adapter observations without editing configuration. Its output is an intake
record for review, not WM-01 evidence or authorization. Driver and USB-parent
fields require independent installed-system observation.

The retained intake record is `connection_intake_20260820.json`. It includes
raw `*TST?`, autocalibration, mode, units, period, and `VAL?` responses. The
`NO SIGNAL` result is retained as a non-numeric status and does not qualify an
optical measurement or interpret the raw self-test byte.

## Electrical and software interface

- WaveMaster rear connector: female DB9 RS-232.
- Cable: straight-through, not null modem.
- Required conductors: RXD pin 2, TXD pin 3, GND pin 5, RTS pin 7, CTS pin 8.
- Serial settings: 9600 baud, 8 data bits, no parity, 1 stop bit, hardware
  RTS/CTS flow control.
- Service: `software/control_app/devices/coherent_wavemaster_service.py`.
- Tests: `software/tests/test_coherent_wavemaster_service.py` and
  `software/tests/test_serial_support.py`.

The adapter's stable USB identity is the connection key; its COM assignment is
an observation. The files under `DRIVER_64/` contain FTDI driver 2.08.14 dated
2011 and are retained as supplier material. The driver associated with the
actual installed adapter must be current, signed, compatible, and recorded;
the archived driver is not an operational matching gate.

## Physical inspection

The operator previously confirmed that the connected instrument worked safely
for intake. That statement does not override the later optical failure or grant
wavelength-measurement authority.

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
installed device, adapter, or measurement authority has passed.
The repository documentation remains the retained manufacturer basis because
the operator-reported Coherent response states that no additional manufacturer
documentation or service is available.
