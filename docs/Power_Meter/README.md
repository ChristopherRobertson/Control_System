# Newport average optical-power working reference

The installed average-power chain is Newport 1918-R meter serial `15879` with
919P-010-16 thermopile sensor serial `161791`. Completed OM-01 qualifies this
chain as a bounded campaign-local working reference under bundle
`CAL-system_recalibration_001-OM01-v1`; no canonical promotion has occurred.

## Installed configuration

| Field | Retained value |
|---|---|
| Meter | Newport 1918-R, serial `15879` |
| Meter firmware | `v1.0.2 04/06/12` |
| USB product ID | `0xCEC7` |
| OM-01 USB address observation | `2` |
| USB driver/DLL | Newport USB driver / `usbdll.dll` version `5.0.8` |
| Service | `control_app/devices/newport_1918_service.py` |
| Sensor | Newport 919P-010-16, serial `161791` |
| Sensor active diameter | 16 mm |
| Sensor spectral range | 190-11000 nm |
| Sensor certificate | `3161791-001`; calibrated 2025-01-12; recommended recalibration 2026-07 |
| Qualified OM-01 mode | DC Continuous, range code 0, 0.5 Hz analog filter, digital filter off |

The certificate date is retained as provenance and is not extended. The OM-01
acceptance, uncertainty, validity, raw records, and limitations are authoritative
in `calibration/system_recalibration_001/readbacks/OM-01/`.

## Measurement authority

The chain measures average optical power. It does not directly measure a pulse-
energy distribution, pulse-to-pulse energy jitter, or calibrated peak power.
Mean pulse energy may be derived only from qualified average power and an
independently verified accepted repetition rate, with uncertainty and the
derivation stated.

The OM-01 OPO observation captured the complete visible footprint before the
permanent iris, including the halos. It is a bounded mixed-spectrum meter
indication, not pure 540 nm power and not a sample-plane dose input. ATT-01,
PB-02, and OG-01 establish the post-iris spectral/transfer/sample-plane chain.

## Software and source register

The query-only service rejects state-changing commands, releases DLL ownership
on close, and is tested by `tests/test_newport_1918_service.py`. The bounded
OM-01 capture helper is `tools/om01_newport_transition_capture.py`.

| Source | Role |
|---|---|
| `1918-R_Power_Meter_Users_Manual_RevA.pdf` | Meter operation, command, and safety authority |
| `1918-R_Power_Meter_Datasheet.pdf` | Meter specifications |
| `919-P_Sensor_Datasheet.pdf` | Sensor range, geometry, and specification source |
| `919-P_Sensor_Certificate_of_Calibration.pdf` | Sensor calibration provenance and stated uncertainty |
| `Installation_Readme.pdf` and `Newport_USB_Driver_5.0.8/` | Retained USB-driver installation material |
| `Firmware-PM1918R-1.0.3.1/` | Retained supplier firmware package; not an instruction to change installed firmware |

Supplier binaries and documents are provenance sources. Their presence does
not authorize installation, firmware change, instrument operation, or phase
advancement.
