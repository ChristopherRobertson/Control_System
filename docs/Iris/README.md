# Thorlabs ELL15 permanent OPO iris

The installed OPO output path contains a Thorlabs ELL15 motorized iris supplied
as an ELL15K kit. It is a permanently retained beam-conditioning component for
the shared 540 nm HRP-C-CO and MbCO configuration. ATT-01 qualifies its control,
far-field placement, aperture, halo rejection, useful-core margin, and optical
transfer before any downstream OPO-540 phase may use it.

The iris is not a safety shutter, interlock, pulse picker, exposure limiter, or
finite-event gate. The independent laser shutter and interlock chain retain
those functions. No scientific acquisition is permitted during iris movement,
homing, cleaning, motor-frequency search, or control recovery.

## Installed identity and connection

| Field | Installed value | Authority |
|---|---|---|
| Procurement model | ELL15K | Kit/manual association |
| Device model | ELL15; protocol model code `0x0F` | Native `0in` reply |
| Device serial | `11500020` | Native `0in` reply |
| Manufacturing year | `2024` | Native `0in` reply |
| Firmware field | `0x10` | Native `0in` reply; raw field retained |
| Hardware field | `0x21` | Native `0in` reply; raw field retained |
| Device address | `0` | Installed serial-bus configuration |
| USB converter | FTDI FT230X Basic UART, VID/PID `0403:6015` | Windows PnP inventory |
| Converter serial | `DP06U124` | Windows USB parent identity |
| Port-interface serial | `DP06U124A` | Windows/pyserial port identity |
| Current preferred port | `COM5` | Observed assignment; not identity |
| Driver | FTDI `2.12.36.20` | Installed Windows driver inventory |
| Serial protocol | 9600 baud, 8 data bits, no parity, 1 stop bit, no flow control | Manufacturer protocol |
| Power | 5 VDC +/-10%; 800 mA typical during movement | Manufacturer manual |

The service discovers the converter identity and then verifies device serial
`11500020`; it does not trust COM5 alone. A read-only implementation audit
observed the native identity reply
`0IN0F11500020202410212CEC000003E8` and position reply `0PO00002CEC`,
corresponding to 11.500 mm. These observations establish implementation input,
not ATT-01 campaign evidence. ATT-01 captures its own approved records.

## Controlled aperture semantics

- Command and readback units are aperture diameter in millimetres.
- Qualified command range: 1.0 to 11.5 mm.
- Encoder scale: 1000 counts/mm; minimum incremental motion: 0.01 mm.
- Manufacturer unidirectional and homing repeatability: +/-0.10 mm.
- Manufacturer backlash: 0.20 mm.
- A target diameter is approached from a larger aperture for repeatability.
- ATT-01 defines the accepted diameter, readback tolerance, centroid/profile
  margin, and locked Z/X/Y mount. Encoder resolution is not treated as optical
  aperture accuracy.
- A command/readback mismatch, USB loss, mount movement, upstream realignment,
  or centroid/profile departure invalidates the OPO-540 configuration and
  prevents emission until the applicable revalidation passes.

The home sensor uses a 950 nm LED that can leak light. ATT-01 therefore includes
a lasers-blocked, iris-powered background control at the retained optical and
detector planes. The iris remains stationary during all accepted acquisitions.

## Software

- Service: `control_app/devices/ell15_iris_service.py`
- Discovery support: `control_app/devices/serial_support.py`
- Tests: `tests/test_ell15_iris_service.py` and
  `tests/test_serial_support.py`
- Vendor installer: `setup.exe`, Thorlabs version `1.6.7.0`, valid Authenticode
  signature observed during repository intake. The vendor GUI is optional for
  diagnostics and must not share the COM port with the service.

The service is query-only unless constructed with explicit motion authority.
Motion authority is still subordinate to the active phase approval, physical
readiness, laser shutter, shot budget, and operator instructions.

## Manufacturer source register

| File | Role | Document identity |
|---|---|---|
| `ELL15K_Iris_Manual.pdf` | Safety, installation, operation, aperture and mechanical specifications | Rev. A, August 31, 2023; DTN000949-D02 |
| `Ellx_Iris_Communication_Protocol.pdf` | Native serial messages, identity/position formats and status codes | Issue 12 |
| `setup.exe` | Optional Thorlabs ELLO software/driver installer | Product/file version 1.6.7.0 |

Manufacturer values remain specifications until the installed tests assigned to
ATT-01 accept them for the stated campaign use.
