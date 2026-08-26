# Retained OPO-540 optical configuration

Configuration family: `OPO540-PERMANENT-IRIS`

Qualification state: **DEFERRED — INSTALLED WAVEMASTER FAILED WM-01 OPTICAL
QUALIFICATION; REPLACEMENT SPECTROMETER PENDING; ATT-01 AND OPO-540 CLAIMS NOT
AUTHORIZED; CANONICAL PROMOTION BLOCKED**

This is the sole retained biological pump path for HRP-C–CO followed by MbCO.
The OPO output passes through the permanently mounted Thorlabs ELL15 iris at
the ATT-01-qualified far-field plane. The aperture remains stationary during
every accepted acquisition and experiment block.

The configuration does not make the iris a safety shutter, interlock, pulse
picker, or finite-event limiter. Those functions remain with the independent
laser-safety and FE-01-qualified event-admission systems.

## Registered components

| Role | Stable identity | Configuration authority |
|---|---|---|
| OPO | SLOPO/Horizon, serial `24366-2` | `hardware_configuration.yaml` and OPO manufacturer records |
| Iris | Thorlabs ELL15, serial `11500020` | `hardware_configuration.yaml`; native `0in` identity |
| Iris USB converter | FTDI FT230X, VID/PID `0403:6015`, serial `DP06U124`, interface serial `DP06U124A` | Windows inventory and native service discovery |
| Iris service | `control_app/devices/ell15_iris_service.py` | ATT-01-qualified software/version record |
| Power working reference | Newport 1918-R `15879` with 919P-010-16 `161791` | OM-01 bundle and ATT-01 transfer records |
| Wavelength working reference | Replacement spectrometer `USER_INPUT_REQUIRED`; failed installed candidate was Coherent WaveMaster 33-2650, electronic serial `W0339`, on `COM8` through FTDI adapter `BG03ADXP` | WM-01 started 2026-08-21; electronic checks passed but optical qualification failed; no wavelength authority issued |

## Phase-qualified fields

The following values are not selected by convenience or visual appearance.
They are frozen only by the named phase and then copied by stable identifier
into downstream manifests.

| Field | Present state | Authority |
|---|---|---|
| WaveMaster configuration/bundle ID | `NOT_YET_QUALIFIED` | WM-01 |
| Preliminary pre-iris FIRE-to-Q-SWITCH delay and search envelope | `NOT_YET_QUALIFIED` | ATT-01 |
| Final locked-iris FIRE-to-Q-SWITCH delay and tolerance | `NOT_YET_QUALIFIED` | PB-02 |
| Iris axial plane and Z coordinate/fiducials | `NOT_YET_QUALIFIED` | ATT-01 |
| Iris X/Y mount coordinates/fiducials | `NOT_YET_QUALIFIED` | ATT-01 |
| Iris diameter command/readback/tolerance | `NOT_YET_QUALIFIED` | ATT-01 |
| 540 nm return-to-wavelength centroid/profile envelope | `NOT_YET_QUALIFIED` | ATT-01 and PB-02 |
| Core-clipping/aperture-margin limit | `NOT_YET_QUALIFIED` | ATT-01 and PB-02 |
| Residual off-wavelength power fraction or upper bound | `NOT_YET_QUALIFIED` | ATT-01 and PB-02 spectral/power method |
| 950 nm home-sensor leakage bound | `NOT_YET_QUALIFIED` | ATT-01 lasers-blocked iris-powered control |
| Post-iris/sample-plane power transfer | `NOT_YET_QUALIFIED` | ATT-01, PB-02, and OG-01 |
| Sample-plane beam geometry and overlap | `NOT_YET_QUALIFIED` | OG-01 and OV-01 |
| Validity/revalidation triggers | `NOT_YET_QUALIFIED` | ATT-01/PB-02/OG-01/OV-01/RP-01 chain |

## Mandatory acquisition record

Every phase or experiment using this path retains:

- OPO, iris, and WaveMaster stable IDs plus applicable calibration and
  characterization bundle IDs;
- final PB-02 FIRE-to-Q-SWITCH delay, command/readback, tolerance, and current
  validity against the accepted locked-iris delay-search envelope;
- iris controller ownership, driver/service version, commanded diameter,
  diameter readback, tolerance result, fault/status state, and locked-mount
  check;
- WaveMaster probe/reference-plane configuration, air/vacuum units, pulsed/CW
  mode, autocalibration state, native time tag/value/status, and uncertainty;
- center wavelength, residual spectral-content result from the accepted
  spectral/power method, post-iris/sample-plane power, centroid/profile,
  aperture margin, and applicable transfer correction;
- lasers-blocked and pump-blocked controls assigned by the active phase; and
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
the revalidation scope assigned by the promoted bundle.

This configuration is valid only at 540 nm. Another OPO wavelength requires a
separately approved wavelength-specific iris position/diameter, centroid,
profile, transfer, and wavelength qualification; no interpolation from the
540 nm configuration is permitted.
