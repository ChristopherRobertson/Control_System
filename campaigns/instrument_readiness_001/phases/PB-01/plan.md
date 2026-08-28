# PB-01 — supplemental direct 355 nm OPO-drive characterization

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `optional`  
Required dependencies: `PROM-CH`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### PB-01 — supplemental direct 355 nm OPO-drive characterization

PB-01 is performed after PROM-CH as a non-gating thesis/source-characterization
phase. It is not a prerequisite for campaign completion, RPT-CH, PROM-CH,
biological entry, or any OPO-540 phase. Measure the upstream 355 nm beam at the
final PB-02 FIRE-to-Q-SWITCH delay and the retained low/high OPO-drive envelope.
Observe direct 532 nm and residual 1064 nm only for source health, separation,
and safety; do not create quantitative biological sample-path grids for them.

The newly installed high-energy detector remains `USER_INPUT_REQUIRED` until
its manufacturer, model, serial number, active-area/aperture geometry,
wavelength range and correction, measurement mode, calibration basis,
single-pulse energy-density limit, average-power limit, and installed readout
identity are recorded from the device and its documentation. PB-01 entry must
prove that the worst-case 355 nm pulse and average loading, including spatial
nonuniformity and alignment uncertainty, remain inside those limits.

PB-01 characterizes the 355 nm OPO drive upstream of the OPO. The permanent
downstream iris does not define 355 nm power and receives no 355 nm transfer
correction. Retain its device/configuration ID and non-emitting state in the
layout record.

Mandatory deliverables:

- Installed high-energy detector/readout identity, documentation, calibration
  basis, wavelength correction, active-area geometry, load/damage-margin
  calculation, range/linearity checks, zero/background, and reference plane.
- Source-plane readings at the final PB-02 delay and retained low/high drive
  conditions, repetition-rate verification, warm-up, short-term stability,
  longer drift record, revisit, and rejected-reading accounting. Report mean
  pulse energy only when explicitly derived from measured average power and
  verified repetition rate.
- Exact harmonic configuration, trigger/timing configuration, polarization and
  beam-location observations, environmental conditions, and any used transfer
  or attenuation links.
- Average-power stability and uncertainty tables, any explicitly derived mean
  pulse-energy table, measured 355 nm operating envelope, saturation/damage-
  margin statement, and safe restoration. Do not claim direct pulse-energy
  distributions, pulse-to-pulse energy jitter, or calibrated peak power.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
