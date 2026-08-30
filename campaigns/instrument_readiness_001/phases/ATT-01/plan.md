# ATT-01 — electronic iris optical attenuation and sample-plane transfer calibration

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `WM-01, OM-01, CH-00.1`
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 11. ATT-01 — electronic-iris, optical attenuation, and sample-plane transfer calibration

Execution status: **DEFERRED PENDING WM-01 REPLACEMENT-SPECTROMETER
QUALIFICATION; NO ATT-01 MEASUREMENT EXECUTION AUTHORIZED**.

ATT-01 imports the accepted WM-01 wavelength working-reference bundle and
establishes the permanent beam-conditioning configuration before any
downstream OPO-output characterization. Characterize every used neutral-density
filter, attenuator, electronic iris or fixed aperture, installed or temporary
beamsplitter, meter pickoff, window, or preview element that transfers a
source-plane measurement to a sample or detector plane. Unused elements are
not measured. A nominal 50/50 label is never used as a correction value.

The electronic iris is a controlled subsystem. Its registered ELL15 identity,
USB-converter identity, power requirements, driver/service versions, units,
command range, readback semantics, homing behavior, power-on state,
timeout/error behavior, and clear-aperture limits are phase inputs. Use
exclusive ownership and the focused service with offline tests for unit
conversion, bounds, malformed or stale replies, and safe connection cleanup.
Qualify connect/query, bounded
command/readback agreement, monotonicity, repeatability, backlash or
hysteresis, reconnect, power-cycle recovery, invalid-command rejection, and
restoration. The iris is not an interlock, safety shutter, pulse picker, or
finite-event gate; communication or readback failure prevents OPO emission and
requires the independent laser shutter to remain closed.

Before comparing iris planes, perform a preliminary FIRE-to-Q-SWITCH delay
search using the unoccluded pre-iris 540 nm output. Freeze the permitted delay
range, coarse step sequence, dwell, repetition count, approach directions, and
meter safety limit before emission. A previously observed maximum at another
wavelength is only a safe search-center hypothesis; it
is not authority for the 355 nm drive or 540 nm output. Use the qualified power
meter within its accepted range and the WM-01 wavelength/status record at every
retained point. Reject saturated, unstable, unresolved `Multi-Line`, or
otherwise wavelength-invalid points. Select a reproducible preliminary delay
from repeated ascending and descending searches by maximum accepted pre-iris
540 nm average power subject to wavelength-state and stability criteria. This
setting establishes the source condition for the candidate-plane and aperture
work; it is not the final operating delay.

Scientifically determine the permanent axial position rather than selecting it
for mechanical convenience. At accessible far-field candidate planes, compare
the desired 540 nm core with the angularly separated halo using attenuated or
indirect diagnostics suitable for pulsed light. Select the plane that provides
the largest reproducible spatial separation and halo rejection while retaining
the un-clipped 540 nm core, adequate damage margin, beam-dump containment,
mechanical stability, downstream clearance, and a reproducible fixed X/Y mount.
Record rejected candidate planes and the selection analysis. Once accepted,
lock the Z/X/Y mount; routine electronic control changes aperture diameter only
unless later manufacturer documentation establishes another controlled axis.

At the accepted plane, scan the available aperture diameter in a prospectively
frozen sequence at 540 nm. For every diameter retain commanded and read-back
values, transmitted desired-wavelength power, residual off-wavelength content,
beam profile/encircled energy, centroid, radii or stated diameter convention,
ellipticity, diffraction/profile change, and repeatability. The accepted
diameter is the largest stable halo-rejecting setting that meets predeclared
spectral-contamination and core-transmission limits without clipping the 540 nm
beam over its measured centroid/radius uncertainty and return-to-wavelength
drift envelope. Do not choose it solely by appearance or maximum throughput.
Before seeing the diameter-scan results, derive the permitted residual-
contamination bound from the maximum tolerable bias in the notebook's absorbed-
photon/initial-photolysis prediction and the intended RSI/thesis uncertainty
budget. Evaluate the absorption-weighted bias for both planned HRP-C–CO and
MbCO samples and use the stricter bound; if a required sample absorption input
is not yet measured, use a documented conservative envelope and retain the
sample-specific pilot as a later confirmation gate. Report both the post-iris off-wavelength power fraction and a
conservative absorption-weighted dose-bias bound; visible suppression alone is
not an acceptance measurement.

The WM-01-qualified replacement spectrometer records independent
center-wavelength/status evidence for every
retained optical condition within its accepted envelope. Its native
`Multi-Line` result is a qualitative spectral-complexity flag, not a power
fraction; the residual off-wavelength power fraction still requires the
phase-approved dispersive/spectral method and the power-meter transfer chain.
Keep the iris powered but stationary during accepted optical records and run a
lasers-blocked iris-powered control to bound the ELL15 home sensor's 950 nm
leakage at each detector or meter plane used by the selection analysis.

The retained campaign uses only OPO 540 nm at the sample. Do not create a broad
410-710 nm iris map. Approach 540 nm from the directions required by PB-02 and
record X/Y centroid return behavior. Any later use of another OPO wavelength
requires a separately approved wavelength-specific iris position/diameter and
beam-center qualification; the 540 nm setting is not interpolated or assumed
valid. Direct 532 nm and the 355 nm OPO drive remain distinct upstream paths
and do not inherit the OPO-output iris correction.

For the installed sample/reference splitter, measure both output-port powers
from the same incident condition and quantify total insertion loss and the
port-resolved split versus wavenumber, polarization, alignment, and operating
power wherever those dependencies are material. Use only the CH-00.1-retained
355 nm OPO-drive, post-iris 540 nm, Mylar-carbonyl, and merged biological
probe anchors. At each used configuration measure the lowest and highest
planned power; add a midpoint only if the predeclared linearity test fails.

Mandatory closeout deliverables:

- Manufacturer-document register; electronic-iris device/service manifest;
  USB/API native readbacks and command log; offline test results; command-
  readback, monotonicity, hysteresis, repeatability, reconnect, power-cycle,
  invalid-command, loss-of-communication, and restoration results.
- Stable component and configuration IDs; accepted and rejected far-field
  candidate positions; locked Z/X/Y mount coordinates or fiducials; orientation,
  wavelength, polarization, beam-dump, and reference-plane photographs/diagrams.
- Preliminary FIRE-to-Q-SWITCH delay-search definition, native programmed and
  read-back delays, synchronized pre-iris power and WM-01 spectrometer status records,
  rejected-point accounting, direction/revisit comparison, selected
  preliminary delay, uncertainty, and safe restoration.
- Complete 540 nm diameter-scan records and the frozen selection rule, including
  pre/post-iris and sample-plane power, residual spectral content, beam profile,
  centroid/radii, core encircled-energy or transmission loss, diffraction,
  drift margin, uncertainty, accepted aperture/readback tolerance, and the
  lasers-blocked iris-powered 950 nm leakage control.
- WM-01 replacement bundle link and native center-wavelength/status/time-tag records for
  each retained condition, with probe geometry, units, pulsed mode,
  autocalibration state, quality outcome, and the explicit limitation that the
  the wavelength spectrometer does not determine spectral-power fractions.
- Raw incident/transmitted readings, dark subtraction, transmission or optical
  density with repeatability and uncertainty, linearity/saturation checks, and
  wavelength interpolation limits for every other used transfer element.
- For every used splitter: incident power, both output powers, total recovered
  power, insertion loss, `f_sample = P_sample/(P_sample + P_reference)`,
  `f_reference`, `P_sample/P_reference`, wavelength/polarization/alignment
  dependence, revisit drift, and covariance/uncertainty. Record the exact port,
  orientation, and downstream reference plane for every reading.
- A machine-readable transfer/configuration matrix identifying which
  corrections and iris setpoint may be used in each later phase, plus
  revalidation triggers after iris command/readback mismatch, diameter change,
  mount or upstream-optic movement, OPO realignment, service/firmware change,
  or centroid/profile drift outside the qualified envelope. No uncharacterized
  aperture or attenuator may enter an emitting phase silently, and no
  downstream calculation may assume a 0.5 split.

## `EXPERIMENTS.md` allocation and decision contract

ATT-01 implements the installed iris, attenuation, splitter, and sample-plane-transfer
portions of `EXP-CAL-14`, `EXP-CAL-15`, `EXP-CHAR-05`, and `EXP-OPT-03`.
Each optical element, port, reference plane, wavelength, polarization, power, geometry,
and source condition is explicit. Native commands/readbacks, power and spectral records,
controls, rejected candidates, uncertainty, acceptance limits, and restoration are
retained. Optic/iris/mount/metrology/source changes or a failed wavelength, residual-
content, clipping, transfer, repeatability, or contamination check trigger revalidation.
PB-02, DET-02/04, OG-01, OV-01, OP-01, and the biological campaigns consume the
result. This phase does not establish sample photochemistry, temporal IRF, chemical time
zero, or kinetics.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
