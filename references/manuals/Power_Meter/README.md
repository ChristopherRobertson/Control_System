# Newport average optical-power working reference

The installed average-power chain is Newport 1918-R meter serial `15879` with
919P-010-16 thermopile sensor serial `161791`. Its bounded average-power
qualification is not a promoted runtime calibration. The configuration identifies
this source as `power_reference_15879_161791`.

## Installed configuration

| Field | Retained value |
|---|---|
| Meter | Newport 1918-R, serial `15879` |
| Meter firmware | `v1.0.2 04/06/12` |
| USB product ID | `0xCEC7` |
| Observed USB address observation | `2` |
| USB driver/DLL | Newport USB driver / `usbdll.dll` version `5.0.8` |
| Service | `software/control_app/devices/newport_1918_service.py` |
| Sensor | Newport 919P-010-16, serial `161791` |
| Sensor active diameter | 16 mm |
| Sensor spectral range | 190-11000 nm |
| Sensor certificate | `3161791-001`; calibrated 2025-01-12; recommended recalibration 2026-07 |
| Qualified mode | DC Continuous, range code 0, 0.5 Hz analog filter, digital filter off |

The certificate date and recommended recalibration date are not extended by use.

## Measurement authority

The chain measures average optical power. It does not directly measure a pulse-
energy distribution, pulse-to-pulse energy jitter, or calibrated peak power.
Mean pulse energy may be derived only from qualified average power and an
independently verified accepted repetition rate, with uncertainty and the
derivation stated.

Pre-iris power can include the complete visible footprint and off-wavelength
content. Treat it as a mixed-spectrum meter indication, not pure 540 nm power or
sample-plane dose. Post-iris spectral purity, transfer and sample-plane geometry
require applicable independent calibration before those quantities are reported.

## Software and source register

The query-only service rejects state-changing commands, releases DLL ownership
on close, and is tested by `software/tests/test_newport_1918_service.py`.

| Source | Role |
|---|---|
| `1918-R_Power_Meter_Users_Manual_RevA.pdf` | Meter operation, command, and safety authority |
| `1918-R_Power_Meter_Datasheet.pdf` | Meter specifications |
| `919-P_Sensor_Datasheet.pdf` | Sensor range, geometry, and specification source |
| `919-P_Sensor_Certificate_of_Calibration.pdf` | Sensor calibration provenance and stated uncertainty |
| `Installation_Readme.pdf` and `Newport_USB_Driver_5.0.8/` | Retained USB-driver installation material |
| `Firmware-PM1918R-1.0.3.1/` | Retained supplier firmware package; not an instruction to change installed firmware |

Supplier binaries and documents are provenance sources. Their presence does
not authorize installation, firmware change, instrument operation, or scientific qualification.

## Supplemental direct-355 sensor

A Newport 919P-050-18HP high-power thermopile sensor has been reported as
installed for direct-355 characterization. It is a separate
measurement configuration from the 919P-010-16 working reference and does not extend its validity.
The retained datasheet identifies a 17.5 mm active diameter (2.40 cm²),
0.24–2.2 µm spectral range, 50 W continuous maximum, greater-than-10 kW/cm²
maximum average power density, and 4 J/cm² sub-100 ns energy-density limit at
1064 nm with a stated 355 nm derating. It also requires Gaussian-beam and hot-
spot factors when comparing incident loading with the threshold. The installed
serial number, device-specific calibration basis, and accepted numerical 355
nm derated limit remain `USER_INPUT_REQUIRED` in `hardware_configuration.yaml`.
Emission is prohibited until those fields and the worst-case load margin are accepted.
This sensor does not extend the average-power reference or OPO-540 validity envelope.
