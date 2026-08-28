# PB-02 — 540 nm OPO output characterization

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `planned`  
Required dependencies: `WM-01, ATT-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### PB-02 — 540 nm OPO output characterization

At 540 nm only, characterize the final output after the permanent ATT-01 iris
using its locked mount and accepted aperture setpoint. Before every emitted
block acquire the iris USB/API identity, service/firmware version, command,
readback, tolerance result, and configuration ID. Measure post-iris average
power, WM-01-linked independent wavelength/readback agreement, residual off-wavelength
content, the linewidth bound required by the MbCO experiment, throughput
relative to the pre-iris 540 nm reference, stability, spatial profile, and
pointing. PB-02 has no PB-01 or direct-355 measurement dependency.

Begin with the ATT-01 preliminary delay and a prospectively frozen narrow
FIRE-to-Q-SWITCH delay range. With the iris mount and aperture locked, acquire
repeated ascending and descending searches plus a revisit. For every point
retain the programmed and read-back delay, synchronized post-iris power,
WaveMaster native value/status, residual-content result, iris readback,
centroid/profile, and stability diagnostics. Select the final delay by maximum
accepted post-iris 540 nm average power, not unfiltered total power, subject to
the wavelength, residual-content, stability, core-clipping, and meter-safety
criteria. Confirm the selected point on a separate return visit and freeze it
as part of the OPO-540 configuration before the remaining PB-02 measurements.

Perform three return-to-540 visits, approaching from the directions required
to expose repeatability/hysteresis, and retain X/Y centroid displacement,
radius/profile change, aperture-margin calculation, and transmitted-power
change. The accepted configuration must remain free of 540 nm clipping over
the measured centroid/radius uncertainty while meeting the ATT-01 halo-
rejection bound. A failed margin, iris readback, or residual-content criterion
stops PB-02 and returns to a separately approved ATT-01 investigation; PB-02
does not silently retune the aperture.

Do not map the broader OPO tuning range. The observed wavelength-dependent X/Y
beam walk makes the qualified iris setting explicitly 540 nm-specific. Direct
532 nm is outside the retained biological scope and is not added here; any other future OPO output
wavelength requires its own approved iris/centroid qualification before use.

Mandatory deliverables:

- Native OPO meter, wavelength-reference, spatial-profile, and iris USB/
  API command/readback records with synchronized shot or acquisition IDs.
- WaveMaster bundle/configuration ID, device/adapter/probe identity, reference
  plane, air-nanometre units, pulsed mode, autocalibration state, native
  `VAL$` time tag/value/status, thermal-stability class, and uncertainty for
  every accepted wavelength record. `Multi-Line`, `Saturated`, and `No Signal`
  remain non-numeric outcomes; an unresolved `Multi-Line` result blocks the
  single-wavelength claim unless the accepted spectral method resolves and
  bounds every contributing component.
- Post-iris average power, residual spectral-content bound, pre/post-iris
  throughput, required linewidth bound, warm-up, X/Y centroid,
  beam radius/profile, aperture margin, direction/revisit repeatability, and
  uncertainty tables.
- Explicit distinction between measured range, interpolated range,
  manufacturer-only range, and unavailable range; recommended wavelength-
  specific settings, accepted iris configuration/tolerance, mismatch stop,
  revalidation triggers, and restoration record.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
