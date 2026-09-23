# Optical pump constraints

Configuration family: `OPO540-PERMANENT-IRIS`

Qualification state: **DEFERRED — INSTALLED WAVEMASTER FAILED OPTICAL
QUALIFICATION; REPLACEMENT SPECTROMETER PENDING; IRIS AND OPO-540 CLAIMS NOT
AUTHORIZED; RUNTIME CALIBRATION UNAVAILABLE**

The configured OPO pump path passes through the permanently mounted Thorlabs
ELL15 iris. The axial plane and mount coordinates remain unqualified. The aperture remains stationary during
every accepted acquisition and experiment block.

The configuration does not make the iris a safety shutter, interlock, pulse
picker, or finite-event limiter. Those functions remain with the independent
laser-safety and qualified event-admission systems.

## Registered components

| Role | Stable identity | Configuration authority |
|---|---|---|
| OPO | SLOPO/Horizon, serial `24366-2` | `hardware_configuration.yaml` and OPO manufacturer records |
| Iris | Thorlabs ELL15, serial `11500020` | `hardware_configuration.yaml`; native `0in` identity |
| Iris USB converter | FTDI FT230X, VID/PID `0403:6015`, serial `DP06U124`, interface serial `DP06U124A` | Native identity readback and configured USB identity |
| Iris service | `software/control_app/devices/ell15_iris_service.py` | Selected driver and software version |
| Power working reference | Newport 1918-R `15879` with 919P-010-16 `161791` | Explicitly selected power and optical-transfer records |
| Wavelength working reference | Replacement spectrometer `USER_INPUT_REQUIRED`; failed installed candidate was Coherent WaveMaster 33-2650, electronic serial `W0339`, on `COM8` through FTDI adapter `BG03ADXP` | Electronic communication does not establish wavelength accuracy; installed WaveMaster optical qualification failed |

## Unqualified operating fields

The following fields have no selected qualified value. Software defaults and
visual appearance cannot supply them. An explicitly selected runtime parameter
set must state values, units, uncertainties, applicability and validity conditions
before an operation may claim that calibration.

| Field | Present state | Required operational information |
|---|---|---|
| WaveMaster configuration/bundle ID | `NOT_YET_QUALIFIED` | Applicable wavelength-instrument identity and configuration |
| Preliminary pre-iris FIRE-to-Q-SWITCH delay and search envelope | `NOT_YET_QUALIFIED` | Allowed electrical command interval and operating bounds |
| Final locked-iris FIRE-to-Q-SWITCH delay and tolerance | `NOT_YET_QUALIFIED` | Selected command interval and tolerance with stationary iris |
| Iris axial plane and Z coordinate/fiducials | `NOT_YET_QUALIFIED` | Verified plane, axial position and fiducials |
| Iris X/Y mount coordinates/fiducials | `NOT_YET_QUALIFIED` | Verified transverse mount position and fiducials |
| Iris diameter command/readback/tolerance | `NOT_YET_QUALIFIED` | Selected aperture and allowable readback difference |
| 540 nm return-to-wavelength centroid/profile envelope | `NOT_YET_QUALIFIED` | Permitted centroid and profile at 540 nm |
| Core-clipping/aperture-margin limit | `NOT_YET_QUALIFIED` | Required aperture margin and allowable clipping |
| Residual off-wavelength power fraction or upper bound | `NOT_YET_QUALIFIED` | Wavelength-resolved power fraction and uncertainty |
| 950 nm home-sensor leakage bound | `NOT_YET_QUALIFIED` | Allowed iris-powered leakage with lasers blocked |
| Post-iris/sample-plane power transfer | `NOT_YET_QUALIFIED` | Applicable power-transfer relationship and uncertainty |
| Sample-plane beam geometry and overlap | `NOT_YET_QUALIFIED` | Spatial beam extent and pump/probe overlap bounds |
| Validity/revalidation triggers | `NOT_YET_QUALIFIED` | Conditions that invalidate the selected operating set |

## Mandatory acquisition record

Every experiment using this path retains:

- OPO, iris, and WaveMaster stable IDs plus applicable calibration and
  characterization bundle IDs;
- final FIRE-to-Q-SWITCH delay, command/readback, tolerance, and current
  validity against the selected operating interval;
- iris controller ownership, driver/service version, commanded diameter,
  diameter readback, tolerance result, fault/status state, and locked-mount
  check;
- WaveMaster probe/reference-plane configuration, air/vacuum units, pulsed/CW
  mode, autocalibration state, native time tag/value/status, and uncertainty;
- center wavelength, residual spectral-content result from the accepted
  spectral/power method, post-iris/sample-plane power, centroid/profile,
  aperture margin, and applicable transfer correction;
- lasers-blocked and pump-blocked controls assigned by the operating procedure; and
- configuration-validity decision before emission and restoration/validity
  decision after the block.

`Multi-Line`, `Saturated`, and `No Signal` are retained WaveMaster outcomes.
They are not converted to a numeric wavelength. A numeric center wavelength
does not establish a residual spectral-power fraction, and a total power-meter
reading is not treated as pure 540 nm power without the accepted residual-
content bound.

## Stop and revalidation conditions

OPO emission is blocked by missing exclusive ownership, iris identity or
readback mismatch, controller/USB loss, iris motion or homing, moved mount,
unapproved aperture, WaveMaster configuration/status failure when required,
source realignment, or centroid/profile/aperture-margin departure. A service,
driver, firmware, optical-layout, pickoff/probe, or wavelength change invokes
a validity review of the affected settings before reuse.

This configuration is valid only at 540 nm. Another OPO wavelength requires a
separately approved wavelength-specific iris position/diameter, centroid,
profile, transfer, and wavelength qualification; no interpolation from the
540 nm configuration is permitted.
