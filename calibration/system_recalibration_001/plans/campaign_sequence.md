# Complete calibration sequence (expanded)

Campaign: `system_recalibration_001`

Status: **WM-01 OPEN / DEFERRED PENDING REPLACEMENT SPECTROMETER; 540 NM / ATT-01 DEPENDENCY CHAIN DEFERRED; INDEPENDENT PHASES MAY PROCEED WITH SEPARATE AUTHORIZATION; PROMOTION BLOCKED**

This plan expands the original calibration scope to close the metrology gaps
needed by the instrument-characterization campaign, thesis, and downstream
experiments.
The permanent OPO output path includes one electronically commanded iris whose
far-field axial placement, fixed transverse mounting, and 540 nm aperture
setpoint are qualified in ATT-01. The iris remains installed for every later
OPO-540 calibration, characterization, and experiment configuration. Its USB/
API control is an operating-configuration dependency, not a safety shutter or
finite-exposure device.
The Coherent WaveMaster is the visible/near-IR wavelength working reference.
WM-01 qualifies its installed identity and serial communications,
measurement settings, response states, repeatability, and uncertainty authority
before ATT-01 or any downstream phase may use its wavelength observations.
The unexecuted downstream biological-pump phases use this single post-iris
540 nm configuration for HRP-C–CO first and MbCO second. This prospective
scope reduction does not rewrite completed CH-00 or OM-01 evidence; prior
direct-532 observations remain historical/source-health records rather than a
retained biological pump qualification.
It is a planning and phase-gate document only. It does not authorize hardware
execution, laser emission, a cable move, or promotion of canonical calibration
files.

## Preservation and non-duplication rule

The following evidence is complete and is an immutable input to later phases:

| Completed scope | Authoritative record | Disposition |
|---|---|---|
| P0 prehardware provenance and inventory | `manifests/` and `analysis/gap_analysis.md` | Retain; close only deferred metadata in TR-01. |
| S0 safe idle, ownership, identities, and interlocks | `readbacks/S0/` | PASS; do not repeat as a measurement phase. Later phases still perform their normal pre/post safe-idle checks. |
| MS-01 PicoScope differential path skew | `readbacks/MS-01/` | PASS; import result and uncertainty by identifier. |
| MS-02 splitter skew, sensitivities, pulse fidelity, and reconnection evidence | `readbacks/MS-02/` | PASS; import result and uncertainty by identifier. |
| T2-01 three direct T660-2 routes | `readbacks/T2-01/` | PASS; retain all 1,800 accepted traces and final route fits. |
| T1-01 T660-1 routes, adapter characterization, trigger counts, and closure | `readbacks/T1-01/` | PASS; retain all accepted and rejected evidence and import the final results. |

No later phase may reacquire one of these quantities merely to use a new file
format, produce a cleaner plot, or simplify aggregation. Later aggregation
must index the existing artifacts and may generate versioned derived tables
without altering raw evidence. Reacquisition is allowed only if a documented
configuration change invalidates the result, an acceptance audit finds the
evidence unusable for its stated purpose, or the user separately approves a
bounded verification. Such work is a new suffixed phase; it never overwrites
the completed record.

PT-01 is complete in its stable `readbacks/PT-01/` record. Do not create a
replacement PT-01 directory or rerun its completed preflight.

## Global execution and advancement gates

1. Approval is phase-specific. Approval of this plan does not approve any
   hardware phase or physical action.
2. Read existing phase evidence before acting. Give the operator one physical
   action at a time and wait for the actual observation.
3. Before every physical transition, apply and verify the applicable safe-idle
   state. A failed safe-idle readback blocks the transition.
4. Laser emission requires a separate written phase approval and a frozen shot
   budget. No rejected acquisition silently authorizes another emitted shot.
5. Under `docs/default_wiring_state.md`, `default wiring restored` means
   T660-1 CHD and MIRcat DB9 pin 5 are disconnected, while MIRcat DB9 pins 6
   and 8 are unused and unwired. These are standing operator-confirmed
   conditions and are not re-asked unless the operator reports a change.
6. Unavailable metadata are recorded as `USER_INPUT_REQUIRED`. Independent
   valid work may continue, but affected claims remain limited.
7. A phase closes only when every mandatory deliverable below exists, is
   internally consistent, and the final equipment state is recorded. If a
   deliverable cannot be completed, the phase remains open or closes as a
   documented bypass with its downstream claim limitation.
8. Canonical calibration outputs remain unchanged until PROM-01 passes and the
   user supplies the exact phrase `APPROVE CALIBRATION PROMOTION`.
9. Any phase using the OPO output after ATT-01 must acquire and retain the
   electronic-iris identity, connection/driver/API versions, commanded and
   read-back aperture, qualified configuration ID, and mismatch/fault state.
   Loss of ownership, communication, or accepted readback blocks OPO emission;
   the iris is never credited as a personnel-safety shutter or pulse limiter.
10. Any phase using a WaveMaster result must retain the qualified working-
    reference bundle ID, device and adapter identities, units, pulse/CW mode,
    autocalibration state, probe geometry, native time tag and response text,
    quality state, thermal-stability classification, and applicable uncertainty.
    `Multi-Line`, `Saturated`, and `No Signal` are measurement outcomes, not
    numeric wavelengths. A WaveMaster reading neither assigns spectral-power
    fractions nor proves that no additional wavelength is present.

## Common phase record and retention gate

Each active phase uses the stable directory `readbacks/<phase-id>/` and the
shared contract in `docs/measurement_campaign_data_contract.md`. Before a
phase can close it must contain, directly or by an explicit manifest link:

- `phase_manifest.json` with schema version, phase status, configuration ID,
  operator, UTC interval, software versions, repository branch and dirty-file
  list, device and accessory IDs, calibration dependencies, and all deviations.
- `acquisition_index.csv`, including accepted and rejected acquisitions; a
  physical condition with no acquisition still receives an indexed record.
- Immutable native raw files plus `artifacts.csv` containing stable artifact
  IDs, relative paths, byte sizes, UTC timestamps, media types, producers, and
  artifact roles permitted by the repository-level provenance rules.
- Exact settings/readbacks, connection or optical-layout record, environmental
  observations, command log, and operator confirmations appropriate to the
  phase.
- Versioned analysis source, machine-readable results with units and sign or
  reference-plane conventions, an uncertainty budget, and acceptance checks.
- `final_report.md`, `restoration_confirmation.json`, unresolved-input list,
  and a statement that no canonical promotion occurred.

Derived data never replace raw data. Corrections are retained both as named
terms and as corrected results. Original, excluded, rejected, and superseded
records remain distinguishable and aggregatable.

## Phase sequence and mandatory deliverables

### 2026-08-25 dependency-aware execution amendment

The numbered order remains the intended integration order, but it is not an
operational gate for phases that do not consume the deferred dependency. The
installed WaveMaster failed WM-01 optical qualification and cannot supply the
required independent 540 nm evidence. WM-01 remains one open phase record and
will resume when a replacement spectrometer is available.

This amendment does not waive, bypass, or mark WM-01 or ATT-01 complete. It
creates two explicit lanes:

- **May proceed now with separate phase authorization:** `HF-01`, `MD-01`,
  `MSW-01`, `HF-02`, `DET-01`, and `SP-01`.
- **Deferred until WM-01 and the applicable upstream chain pass:** `ATT-01`,
  `DET-02`, `DET-03`, `DET-04`, `SP-02`, `OP-01`, `FE-01`, `CL-01`, the
  OPO-540 portion and closure of `E2E-01`, closure of `RPT-01`, and `PROM-01`.

Prehardware planning and retention indexing for a deferred phase may continue,
but measurement execution, acceptance, or closeout may not represent a missing
WM-01/ATT-01 result as available. Canonical calibration promotion remains
blocked until all deferred required phases return, pass, close, and the exact
promotion authorization is separately supplied.

Legacy downstream text and table headers that say `WaveMaster` are interpreted
during this deferral as `the WM-01-qualified wavelength instrument`; they do
not authorize the failed device or constrain procurement to the same model.
Instrument-specific field names and collectors are updated prospectively after
the replacement identity and native data contract are known.

### 0. P0 — provenance and inventory baseline — COMPLETE; DECISIONS RESOLVED

P0 established the clean-slate campaign, installed topology, initial device and
accessory identities, historical-data boundary, software provenance, spectral
reference inventory, and the original unresolved-resource list.

Mandatory closeout evidence already retained: P0 manifests, blocker table,
physical inventory, pre/post-merge provenance, and gap analysis. Deferred
requirements were resolved on 2026-08-15 in
`manifests/p0_requirement_decisions.md`. Only requirements recorded there as
`KEEP` or `NARROW` move to TR-01 or another named phase; discarded requirements
do not silently reappear. P0 is not repeated.

### 1. S0 — safe-idle and interlock verification — PASS

Mandatory closeout evidence already retained in `readbacks/S0/`: operator
physical confirmations, exclusive ownership, device identities, T660 disabled
readbacks, MIRcat safe state, interlock state, command log, and final cleanup.
S0 is not repeated as a measurement phase.

### 2. MS-01 — PicoScope differential channel/path skew — PASS

Mandatory closeout evidence already retained in `readbacks/MS-01/`: normal and
swapped raw captures, settings, analysis, result, uncertainty, restoration,
final safe idle, and the applicable PicoScope manufacturer-specification
uncertainty basis. Do not reacquire.

### 3. MS-02 — splitter branch skew and measurement-system sensitivities — PASS

Mandatory closeout evidence already retained in `readbacks/MS-02/`: imported
MS-01 data, second connection realization, threshold/interpolation/timebase
sensitivities, pulse fidelity, results, uncertainty, and restoration. Do not
reacquire.

### 4. T2-01 — direct T660-2 routes — PASS

Mandatory closeout evidence already retained in `readbacks/T2-01/`: six-point
sweeps for EXT REF to DAQ, MIRcat TRIG IN, and T660-1 TRIG IN; all raw and
rejected records; route fits; pulse fidelity; sensitivities; connection logs;
and final restoration. Do not reacquire.

### 5. T1-01 — T660-1 trigger/output routes and electrical closure — PASS

Mandatory closeout evidence already retained in `readbacks/T1-01/`: six-point
route results, adapter normal/swapped evidence, trigger-count diagnostics,
direct-versus-derived closure, all accepted and rejected traces, and final
restoration. Do not reacquire.

### 6. PT-01 — MIRcat Process Trigger electrical timing — COMPLETE; PASS

Resume the existing PT-01 record after its passed preflight. Measure the
approved reference to T660-1 CHC/MIRcat DB9 pin 4, including idle-high,
active-low behavior. CHD/pin 5 and pins 6/8 remain excluded.

Mandatory closeout deliverables:

- Completed operator connection records for every setup and final restoration.
- Raw captures, settings/readbacks, accepted/rejected counts, polarity, pulse
  width, route fit where applicable, jitter, threshold sensitivity, and the
  imported MS-02 measurement-path correction.
- Reference-plane definition, uncertainty budget, final report, and safe-idle
  readback. PT-01 closes before MC-01 begins.

### 7. MC-01 — MIRcat GUI process-trigger qualification — COMPLETE / PASS

Under manufacturer-GUI ownership, qualify only the discrete point/process
sequence selected in CH-00 for the biological fixed-wavenumber workflow. Verify
external laser/process-trigger state transitions, one-command/one-process
behavior, the first and subsequent bounded repeats, and the permitted delay
after Sweep Active falls. Do not exercise unused multispectral/channel modes.
SDK use before GUI qualification was prohibited; bounded SDK control
qualification was performed only after the GUI repeats passed.

Mandatory closeout deliverables:

- GUI/version/firmware provenance, selected operating modes, screenshots or
  exported logs, T660 readbacks, DIO evidence, and a timestamped action ledger.
- Expected-versus-observed state/pulse table for one inhibited control and
  three bounded repeats of the retained point/process sequence, including
  exceptions and failure behavior.
- Ownership release, safe shutdown, restoration record, uncertainty/ambiguity
  statement, and explicit SDK-automation eligibility decision.

The inhibited control and three bounded repeats passed. Each accepted repeat
used one started-engine 10 ms active-low T660-1 CHC command and produced one
1905-to-1934 cm^-1 transition followed by explicit Stop Scan. Raw DIO evidence
supports event correlation but not a persistent ready level; automation must
use MIRcat waiting/tuned state readback rather than a fixed delay. SDK control
qualification set/read External process mode and restored/read Internal mode.
Initial configuration import, power-down, GUI/SDK ownership release, interlock
inhibition, default-wiring restoration, and final T660 safe idle all passed.

The shutter remained closed and T660-2 sent no external laser-trigger pulse,
so no optical pulses occurred. Authorization `MC01-AUTH-002` permitted the
bounded continuation but did not authorize any later phase. See
`../readbacks/MC-01/final_report.md` and `continuation_authorization.md`.

### 8. TR-01 — retained identity and measurement-resource closure — COMPLETE / PASS

Close only requirements retained or narrowed in
`manifests/p0_requirement_decisions.md` plus metrology resources actually
selected for later phases. Do not repeat completed measurements and do not
retrieve certificate or accessory metadata that the decision register
discarded. Devices whose installed performance is measured directly require
identity, configuration, evidence, uncertainty, and validity limits—not a
formal certificate. Only instruments serving as measurement references need
an applicable uncertainty basis, which may be a manufacturer specification,
available calibration record, or qualified comparison.

Mandatory closeout deliverables:

- A concise measurement-resource register listing stable equipment ID, role
  (`DEVICE_UNDER_TEST` or `WORKING_REFERENCE`), configuration/range used,
  uncertainty basis where applicable, validity conditions, and source record.
- Final P0 decision-register export showing every item as retained, narrowed,
  or discarded with its downstream claim consequence.
- PicoScope serial `10261`, actual timebases/ranges used, and applicable
  manufacturer accuracy; voltage accuracy is required only for a reported
  quantitative voltage, not a threshold diagnostic.
- MIRcat and LabOne/HF2LI software versions for accepted configurations, the
  existing schema/analysis-version convention, the retained detector identity
  requirement, applicable wiring authority, and the metrology resources
  actually selected after experimental requirements are defined.

All P0 decision rows are resolved. TR-01 may proceed in parallel with
nondependent analysis and cannot add discarded work back into the campaign.
PROM-01 must describe the actual uncertainty basis without claiming accredited
traceability that the campaign does not establish. The replacement
reference-detector SIP model/serial and detector model/serial must be recorded
after arrival and before reference-detector-dependent DET phases begin.

TR-01 closed by records audit in `../readbacks/TR-01/`. It imported completed
campaign evidence by stable identifier, retained the applicable PicoScope
manufacturer-specification basis, classified spectral authority as deferred to
SP-01 and optical resource qualification as deferred to OM-01, and made no
hardware or canonical-calibration change. It designated OM-01 as its successor;
OM-01 is now complete and retained without reacquisition.

### 9. OM-01 — optical metrology readiness and transfer standards

Execution status: **PASS - COMPLETE, QUALIFIED BOUNDED** in the stable
`readbacks/OM-01/` record. Newport 1918-R serial `15879` with 919P-010-16
sensor serial `161791` has passed query-only USB identity/configuration
communication and the completed installed checks are retained in
`optical_metrology_bundle.json`. This status does not authorize WM-01, ATT-01,
or any later phase and performs no canonical promotion.

Qualify only the available instruments selected after downstream experiment
requirements define the needed pump/probe power, wavelength, beam-size,
polarization, attenuation, and observational ambient records. No energy meter
is currently available, so this phase does not require direct pulse-energy
measurement. It does not characterize the pump or probe beams themselves.

The minimum wavelength grid is the union frozen in CH-00: direct 532 nm pump,
355 nm only as the OPO drive, 540 nm OPO output, one Mylar-carbonyl probe
anchor, and the merged HRP/MbCO probe anchors and off-band control points.
Shared points are measured once. No other wavelength or range is qualified
unless the frozen claim grid requires it.

At each retained wavelength family and meter range required by the
experiment-derived expected reading envelope, record zeroing, background,
sensor head, wavelength correction, sampling mode, warm-up, bounded
low/high meter-behavior evidence, three repeat readings, one revisit,
saturation limits, spatial-scale calibration, and the applicable manufacturer
specification or available comparison. Exact laser delay, current, pulse/duty,
and delivered-power operating points are selected and characterized later in
ATT-01/PB-02/PB-01/QB-01; they are not OM-01 inputs. Add a midpoint only when the
meter-behavior residual rule fails. Do not add a new meter or certificate task
unless an approved experimental claim requires it.

Mandatory closeout deliverables:

- Optical-metrology configuration manifest and permitted range/wavelength
  table for every meter/sensor.
- Raw zero/background/check data, applicable specification or comparison
  links, correction tables, interpolation rules, saturation rules, and
  uncertainty budgets.
- Beam-profiler spatial calibration or documented alternative beam-diameter
  method; environmental observation method and uncertainty classification.
- `optical_metrology_bundle.json` assigning a stable bundle ID consumable by
  DET-02, DET-03, DET-04, OP-01, and `system_characterization_001`.

### 10. WM-01 — visible/near-IR wavelength-metrology readiness

Execution status: **STARTED 2026-08-21; INSTALLED WAVEMASTER OPTICAL
QUALIFICATION FAILED; OPEN / DEFERRED PENDING REPLACEMENT SPECTROMETER**.

WM-01 qualifies the installed Coherent WaveMaster, catalog number 33-2650, as
a campaign-local wavelength working reference over only the source conditions
used by the retained campaign. It does not qualify optical power, spectral-
power fractions, absence of additional wavelengths, or the 355 nm OPO drive,
which is outside the instrument's 380-1095 nm specified range.

Before WM-01 may start, every `devices.wavemaster.phase_entry_required_fields`
entry in `hardware_configuration.yaml` must contain an observed value. The
2026-08-20 query-only connection intake resolved and recorded the electronic
serial, complete `*IDN?` response, firmware revision, COM port, adapter
VID/PID, adapter/interface serials, adapter model, installed driver, and native
query responses. The operator confirms that the connected instrument works
safely. All phase-entry fields are resolved.

`python tools/wm01_preflight.py` enforces this entry gate and now reports
`READY_FOR_PHASE_APPROVAL`. Separate user approval is still required before
phase work, optical placement, or laser emission. A null-modem cable or missing
RTS/CTS conductors blocks the phase.

The phase first identifies and photographs the label, front panel, sampling
probe/fibre and acceptance switch, mount, pickoff, and dump. Cable, USB adapter,
and rear-panel photographs are optional when the installed RS-232 and power
connections are otherwise identified in the cable/adapter, driver, device
configuration, and live communication evidence. It then verifies
straight-through RS-232 operation at
9600 baud, 8-N-1 with hardware RTS/CTS, exclusive port ownership, `*IDN?`,
`*TST?`, local/remote restoration, documented query/set/readback behavior,
communication loss/reconnect, malformed/stale-response rejection, and safe
cleanup. Electronic identity is compared with the reported `WO 339` label
without normalizing an ambiguous character by assumption.

Optical qualification freezes air-nanometre units, pulsed mode for OPO work,
autocalibration enabled, sampling-probe geometry/acceptance setting, input-
status interpretation, and the retained reference plane. Quantitative records
use the manufacturer guidance for best thermal stability after approximately
four hours. At 540 nm, and at 532 nm only where useful as a visible source-
health/reference point, acquire blocked/no-signal controls, native `VAL$`
records with time tags, repeated windows and a later revisit. Capture naturally
observed `Multi-Line` or saturation states without coercion or deliberate
overload. An applicable independent wavelength reference may support an
agreement check; when none is available, the result remains a manufacturer-
specification-based installed working reference and does not claim accredited
traceability.

Mandatory closeout deliverables:

- Installed-device, cable, adapter/driver, probe, mount, reference-plane,
  and software configuration manifests with native identities and applicable
  photographs; rear-panel, cable, and adapter photographs are not mandatory
  when the installed connections are otherwise identified.
- Raw serial transcript; self-test/autocalibration results; settings/readbacks;
  disconnect/reconnect, exclusive-ownership, invalid-response, local-control,
  and restoration evidence; offline-test results; and accepted/rejected index.
- Native wavelength/status/time-tag records, blocked control, thermal-stability
  classification, repeatability/revisit analysis, any reference comparison,
  response-state handling, uncertainty budget, and explicit 355 nm and
  spectral-power-fraction exclusions.
- `wavelength_metrology_bundle.json` with a stable bundle ID, validity envelope,
  permitted units/modes/probe geometry, revalidation triggers, and machine-
  readable quantity IDs consumable by ATT-01, PB-02, OG-01, PF-01, RP-01,
  RPT-01, and the characterization campaign.

WM-01 must pass and close before ATT-01 can be authorized. The 2026-08-25
dependency amendment allows only independent non-WaveMaster phases to proceed;
it is not a bypass. A bypass cannot
support independent 540 nm wavelength identity, residual-color interpretation,
or quantitative notebook-prediction claims.

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
meter safety limit before emission. The previously observed approximately
245 microsecond maximum at 632 nm is only a safe search-center hypothesis; it
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

The WaveMaster records independent center-wavelength/status evidence for every
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
power wherever those dependencies are material. Use only the CH-00-retained
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
  read-back delays, synchronized pre-iris power and WaveMaster status records,
  rejected-point accounting, direction/revisit comparison, selected
  preliminary delay, uncertainty, and safe restoration.
- Complete 540 nm diameter-scan records and the frozen selection rule, including
  pre/post-iris and sample-plane power, residual spectral content, beam profile,
  centroid/radii, core encircled-energy or transmission loss, diffraction,
  drift margin, uncertainty, accepted aperture/readback tolerance, and the
  lasers-blocked iris-powered 950 nm leakage control.
- WM-01 bundle link and native center-wavelength/status/time-tag records for
  each retained condition, with probe geometry, units, pulsed mode,
  autocalibration state, quality outcome, and the explicit limitation that the
  WaveMaster does not determine spectral-power fractions.
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

### 12. HF-01 — HF2LI configuration and external-reference qualification

Execute the bounded PicoScope-AWG electrical parameter-characterization design
in `plans/hf01_awg_parameter_characterization.md`. Keep all lasers inhibited
and shuttered. Use the monitored AWG carrier step and offset-carrier response to
measure, rather than merely assume, the relationship among input range,
time constant, filter order, acquisition rate, noise, settling, attenuation,
phase/delay, clipping, and throughput. Use exactly three separated electrical
points solely to validate the manufacturer response model; they are not
preselected experiment settings and receive no sweep, HRP-C-CO, or MbCO label.
After model validation, evaluate every supported order, time constant, range,
and output rate computationally against each experiment's requirements, then
physically confirm only the configurations selected by that analysis plus one
challenger per case when uncertainty leaves the selection ambiguous. Do not
run an HF2LI parameter grid on Mylar. Preserve `CLOCK-SPLITTER-01` in its
normal T660-2-to-T660-1/HF2LI 10 MHz clock distribution. Use a separately
identified passive 50 ohm, DC-coupled BNC tee for monitored AWG stimulus and
use measured, read-back-verified T660 reference/marker copy channels for
PicoScope timing.

All HF-01 signal-input stimuli remain centered at the retained 2 MHz carrier.
The 10 Hz Nd:YAG/OPO cadence is not an analog HF2LI test frequency and does not
create a fourth response point or anchor. Check it once, without emission, only
as the retained T660 digital event/recording-marker cadence across the
PicoScope and HF2LI DIO timestamps; leave stream endurance and optical-event
reconciliation to HF-02 and FE-01 respectively.

Qualify exactly three experiment-specific retained configurations across two
topologies: the probe-only continuous-sweep configuration used by
polystyrene/Mylar, an HRP-C-CO fixed-wavenumber/rare-pump configuration sized
for the longest retained HRP recovery, and an MbCO fixed-wavenumber/rare-pump
configuration sized for the fastest retained MbCO dynamics. Select acquisition
rate, time constant, filter order, phase, ranges, and record length separately
for each configuration against frozen temporal-bandwidth, settling/bias,
noise/SNR, clipping, loss, and data-volume criteria. The CH-00 settings and
repository presets are qualification seeds, not accepted values. A common
numeric setting may be retained for HRP-C-CO and MbCO only after measured
equivalence demonstrates that it satisfies both sets of criteria; even then,
retain separate configuration IDs with an explicit alias/equivalence record.
For each selected configuration, verify reference lock/readback, demodulator
assignments, model-predicted filter transfer and effective noise bandwidth,
used ranges, clipping margin, and one reload equivalence. Add a challenger only
under the ambiguity rule in the HF-01 AWG design; add a fourth model anchor only
after a predeclared model-residual failure.

Mandatory closeout deliverables: the complete evidence package required by the
HF-01 AWG design, complete node snapshots and reload diffs, reference-frequency
comparison, native monitored-stimulus and HF2LI records, analytical candidate-
disposition table, three-anchor model validation, complex filter/step/noise/
range/rate/selected-setting channel-equivalence results, uncertainty/acceptance
table, and three restorable experiment-specific
approved configuration IDs (or separate biological IDs supported by an
explicit equivalence alias).

### 13. MD-01 — MIRcat/HF2LI DIO mapping qualification

Use the accepted side-experiment mapping (pin 1 to bit 20, pin 2 to bit 21,
pin 3 to bit 22) without repeating the mapping-only discovery. Acquire three
campaign-local scans per direction at the retained continuous-sweep
configuration and three repeats of the retained point/process sequence under
each of the HRP-C-CO and MbCO acquisition configurations. Verify
polarity/state semantics, direction behavior, signatures, counts, timing, and
repeatability. Do not map unused DB9 modes or reserved pins.

Mandatory closeout deliverables: complete DIO words rather than selected bits,
MIRcat logs, HF2LI configuration ID, pin/bit/state truth table, direction and
transition signatures, count reconciliation, timestamp alignment, raw artifact
index entries, and an explicit qualification decision.

### 14. MSW-01 — MIRcat sweep timing

Measure the single CH-00-selected continuous-sweep speed and marker interval/
width in both directions over the longest retained Mylar/polystyrene window.
Also measure the discrete point-tune/process transition sequence under each
retained HRP-C-CO and MbCO acquisition configuration. The former 5 cm^-1,
500 us, and 40 cm^-1/s values are
planning candidates only; test them only if CH-00 retains them. An alternative
setting is added only after the selected setting fails a predeclared marker,
transition, or uncertainty criterion.

Mandatory closeout deliverables: three complete scans per direction plus three
point/process sequences per biological acquisition configuration, raw MIRcat
and HF2LI/DIO streams, trigger/segment event
table, expected-versus-observed counts, measured spacing check, transition/gap
analysis, clock/reference conventions, uncertainty, and acceptance decision.

### 15. HF-02 — cross-stream alignment, loss, and endurance

Verify simultaneous Sample, Reference, and complete-DIO timestamps, API/server
buffering, dropped samples, and boundary behavior over exactly three maximum-
duration records: one complete retained continuous sweep, one longest planned
HRP-C-CO recovery stream, and one longest planned MbCO acquisition stream.
Additional endurance records are acquired only if a retained configuration
fails. A biological record may serve both configurations only when HF-01 has
documented numeric equivalence and the maximum-duration envelopes are also
identical; preserve the cross-reference rather than silently omitting a test.
Import the HF-01 filter/rate response bundle; HF-02 tests streaming integrity
and duration only and must not repeat AWG transfer, settling, range, or noise
mapping.

Mandatory closeout deliverables: native streams, common-event alignment table,
sample-count and gap audit, loss/reorder/duplicate statistics, host/server
clock record, resource/endurance log, configuration reload check, and a maximum
supported scan envelope with uncertainty or limitation.

### 16. DET-01 — dark detector/electronics performance

With non-emitting sources, determine dark noise, drift, Allan-style stability,
electrical cross-talk, range dependence, and short/long-duration repeatability.
Use only the gains/ranges retained for the three HF-01 configurations. For each
installed channel/configuration acquire one short record, one record as long as
the longest planned acquisition, and one revisit; do not scan unused gains,
ranges, or durations.

Mandatory closeout deliverables: exact installed detector/amplifier/power-
supply identities and settings, blocked-state definition, environmental log,
raw Sample/Reference records, PSD/Allan/noise tables, cross-talk controls,
uncertainty budget, and accepted dark-operating configuration.

### 17. DET-02 — illuminated detector/electronics transfer performance

Using OM-01/ATT-01-qualified metrology and separately authorized illumination,
measure each detector/amplifier/HF2LI channel's response against independently
measured incident power: gain or responsivity, linearity, saturation, SNR,
noise, and wavelength dependence over the unequal power ranges expected after
the installed splitter. Use a common calibrated transfer detector/source or an
approved branch/detector interchange where practical to separate detector-
electronics response from optical-path transmission. Do not repeat DET-01 dark
acquisitions; import their result bundle.

The minimum grid is the merged CH-00 probe-anchor set: one Mylar-carbonyl
anchor, the two HRP-C-CO band anchors, the MbCO A1/upper diagnostic anchor, and
only the off-band point needed by the biological controls. Merge coincident
anchors. At each retained wavelength use the lowest and highest expected
incident powers with three readings per channel and one revisit; add a midpoint
only if the predeclared fit-residual rule fails.

Mandatory closeout deliverables: frozen illumination budget and conditions,
raw detector and optical-meter data, incident-power reference planes,
attenuation/transfer IDs, per-channel response curves, fit residuals,
saturation and recommended operating margins, detector-gain ratio with
uncertainty, accepted/rejected ledger, and safe restoration. Identify which
part of the channel mismatch belongs to detector/electronics response rather
than optical splitting. Report installed-chain response to the qualified
available power meter; accredited absolute detector responsivity is outside
scope.

### 18. DET-03 — detector temporal-response and latency correction

Measure or authoritatively bound the response delay and temporal bandwidth of
the exact detector/amplifier/cable/acquisition path used by OP-01. This is a
new missing correction term; it does not repeat MS-01/MS-02 or T1-01.
Test each installed detector/amplifier/cable path at the fastest required
acquisition configuration and at the low/high accepted signal levels. Import
the HF-01 measured complex filter transfers and compose them with this detector
response to produce HRP-C-CO and MbCO latency/attenuation corrections. Confirm
that composition once under the other biological configuration only if the
paths cannot be shown linear and time invariant, the propagated result lies in
an acceptance guard band, or the confirmation residual fails. Use one anchor
in each disjoint Mylar and biological probe window; add another wavelength only
if the manufacturer model or measured residuals show material wavelength
dependence. Do not repeat the HF-01 AWG filter grid.

Mandatory closeout deliverables: stimulus/reference planes, detector placement
and cable IDs, raw response data or authoritative model record, amplitude-
dependence and threshold checks, detector-only response plus HF-01-composed
HRP/MbCO latency and attenuation estimates, composition residual or stated
escalation result, sign convention, standard uncertainty, validity envelope,
and a stable correction ID accepted for OP-01.

### 19. DET-04 — installed sample/reference optical-balance and normalization calibration

Combine ATT-01's component/port measurements with DET-02's separate channel
response functions in the final installed sample/reference optical paths.
Measure power at the sample and reference detector planes separately under the
same source condition. Establish the end-to-end optical balance, detector-
electronics balance, and measured system baseline ratio without assuming the
splitter is 50/50.

Use the same merged probe anchors and low/high expected powers retained in
DET-02, with shared points measured once. Use only the polarization and
alignment states that survive CH-00, and include one controlled realignment/
revisit. If detector or branch exchange is safe and practical, use it once as
a separation/closure test; otherwise use the same qualified transfer detector
sequentially at both detector planes and retain the placement/repeatability
uncertainty.

Mandatory closeout deliverables:

- Stable identities for splitter input/output ports, all downstream optics,
  detector planes, detectors, amplifiers, HF2LI inputs, meter heads, mounts,
  polarization state, and alignment configuration.
- Synchronized incident, sample-plane detector-path, and reference-plane
  detector-path optical readings plus simultaneous electrical outputs where
  possible; native raw data, backgrounds, settings, and accepted/rejected
  ledger.
- Wavelength-dependent `P_sample`, `P_reference`, optical balance
  `B_opt = P_sample/P_reference`, detector/electronics balance
  `B_det = G_sample/G_reference`, and system baseline ratio
  `B_sys = V_sample/V_reference`, with the closure check
  `B_sys ~= B_opt * B_det` and defined acceptance limits.
- Linearity and saturation checks at both detector planes across the actual
  unequal-power range; split-ratio and balance dependence on power,
  polarization, alignment, and time; revisit/realignment drift; covariance and
  full uncertainty budgets.
- A machine-readable normalization table versus wavenumber with interpolation
  and extrapolation limits. It must support the background-normalized equation
  `A = -log10[(S/R)/(S0/R0)]` (and the separately defined transient estimator)
  without forcing the two raw powers or voltages to be equal.
- A stable `detector_balance_bundle.json` correction ID, recommended operating
  margins, revalidation triggers after splitter/optic movement, detector or
  amplifier replacement, gain/range changes, material realignment, or drift
  beyond the accepted limit, plus safe restoration.

DET-04 is a prerequisite for quantitative dual-detector spectral calibration,
normalization, platform sensitivity, and later biological absorbance claims.

### 20. SP-01 — spectral-reference provenance

Close the identity, source, lot, accepted features, feature authority, and
uncertainty for polystyrene and Mylar. Record temperature and any available
path/thickness information as observations only; neither is a calibration
prerequisite for the approved peak-position alignment/validation claims.
Reuse P0 inventory observations; do not reinspect documented facts unless a new
reference is introduced.

Mandatory closeout deliverables: reference manifest, photographs/labels,
authority citations or available certificate locations, accepted-feature
table with uncertainty, observational conditions, and an explicit statement
that absolute film absorbance and quantitative Mylar etalon prediction are
outside scope. Missing film thickness does not block SP-01 or SV-02.

### 21. SP-02 — spectral-axis calibration

Measure internal-readback accuracy, trigger-derived axis, per-channel behavior,
direction hysteresis, crossovers, effective sampling/interpolation, reference
agreement, and scan-to-scan repeatability using qualified prior phases. Import
the DET-04 balance/normalization bundle; do not estimate or assume a 50/50
split from the spectral data.

The grid contains only two disjoint validated regions: the CH-00 Mylar/
polystyrene carbonyl window and the combined 1885-1980 cm^-1 HRP/MbCO window.
Use one accepted continuous-sweep configuration and three scans per direction
per retained region. Add a module-crossover condition only when a retained
region crosses one. Do not run the former broad 1650-2050 cm^-1 candidate.

Mandatory closeout deliverables: native spectra/readbacks/DIO streams, exactly
three planned scans per direction and relevant channel, frozen calibration fit,
residual and hysteresis tables, interpolation method, uncertainty budget,
independent validation partition, DET-04 correction ID, raw and normalized
Sample/Reference products, and validity range. Calibration data and validation
data must remain separately identifiable. Another scan is allowed only after a
predeclared acceptance criterion fails.

### 22. OP-01 — operational pump-command-to-sample timing

Execute one bounded biological-pump optical path at permanent-iris 540 nm, but
capture and report it under the separate retained HRP-C-CO and MbCO HF2LI
acquisition configuration IDs. The pump path may be shared; acquisition-filter
delay, sampling, and estimator corrections may not be assumed shared.
Use the identified straight barrel adapter correction (0.125 ns with
0.0722 ns rectangular standard uncertainty), MS-01/MS-02 results, and DET-03
detector correction. The Q-switch cable, loaded Nd:YAG response, the applicable
internal laser/OPO response, and optical propagation remain intentionally
included. Mylar is pump-off and adds no OP-01 condition.

The OPO-540 timing configuration must use the ATT-01-qualified permanent iris
at its accepted locked mount and aperture setpoint. Record a fresh command/
readback and configuration ID before every emitted block. Do not use the iris
as the timing origin, optical event gate, or safety shutter.

Mandatory closeout deliverables for the retained pump path: frozen shot
budget; blocked control; one attenuated preview; a prospective precision-based
repeat count capped at 100 unless separately approved; raw traces;
shot/rejection/counter ledger; SNR/saturation checks;
adapter/splitter/detector/placement IDs; signed correction equation; placement
and restoration repeatability; uncertainty budget; photographs; and final safe
state. No automatic replacement shots are permitted.

### 23. FE-01 — finite emitted-pump-event control and reconciliation

Qualify the finite-exposure mechanism shared by the biological experiments
without a biological sample. Preserve the manufacturer-qualified Nd:YAG/OPO
cadence while admitting only CH-00-approved rare post-iris OPO-540 pump events
to the sample-equivalent plane. The accepted implementation may be a
validated laser pulse-division mode, an interlocked optical pulse picker/
shutter, or another separately approved topology. A T660 shot-counter reset is
never an exposure limiter.

For the OPO-540 path, retain the ATT-01 iris configuration and verify its
command/readback before the independent event-count tests. Changing iris
diameter or mount state creates a different optical configuration and cannot be
used to admit or suppress individual pump events.

Mandatory closeout deliverables:

- Stable configuration and topology IDs for the retained 540 nm path,
  with command source, flashlamp cadence, optical gate/divider state, and an
  independent optical pump-event observation.
- A blocked zero-event control, a one-event test, and one finite multi-event
  block for the retained path; command-versus-observed event reconciliation;
  verification that the programmed limit stops further admitted events; and
  proof that unused pulses remain blocked from the sample-equivalent plane.
- No-emission fault tests for observation loss, command/observation mismatch,
  software exception, and operator stop, plus the normal-completion path. Each
  path must close the pump first, stop both T660s/MIRcat as applicable, apply
  safe idle, preserve partial evidence, and verify restoration.
- Latency/uncertainty, event-observation behavior, and maximum supported rare-
  event interval/record length under each retained HRP and MbCO acquisition
  configuration. Dose, photolysis,
  and biological recovery are outside this calibration phase.

### 24. CL-01 — complete timing-chain closure

Calculate direct and derived chains only between compatible reference planes.
Keep programmed, cable-end, device-pin, detector, optical, and chemical origins
distinct and establish the operational nonzero-delay correction and pump-probe
equation.

Close the retained OPO-540 pump path and all three acquisition configurations
across both topologies: the probe-only continuous sweep, the HRP-C-CO finite
rare-pump recovery stream, and the MbCO finite rare-pump delay/recovery stream.
Use existing completed electrical sweeps; do not reacquire them. Include the
FE-01 observed-event clock bridge over both the longest planned HRP recovery
record and the retained MbCO record.
The OPO-540 chain is valid only for the ATT-01 iris configuration imported by
OP-01 and FE-01; iris USB/API latency is recorded as configuration provenance
but is not part of the per-shot timing equation because the aperture remains
static throughout an emitted block.

Mandatory closeout deliverables: machine-readable correction-term register,
reference-plane graph, covariance-aware uncertainty propagation, closure table
and residuals, incompatible-chain rejection list, validity/configuration IDs,
and pass/fail decisions against frozen engineering limits.

### 25. E2E-01 — normal-wiring validation

Perform exactly three bounded nonbiological runs: one probe-only continuous
sweep, one HRP-style finite rare-pump recovery run, and one MbCO-style finite
rare-pump delay/recovery run. Together they cover startup, ownership, T660s,
MIRcat/reference lock, Sample/Reference/full-DIO capture, finite exposure,
axes, processing, safe stop, repeatability, and artifact completeness. Reuse
FE-01 fault-path evidence; add one no-emission simulated software fault only if
the E2E orchestration differs materially.

The rare-pump run uses the qualified OPO-540 iris configuration when that is
the retained more-complex path. Its startup, command/readback, configuration
foreign key, mismatch stop, and restoration are part of the end-to-end audit.

Mandatory closeout deliverables: three complete independent manifests and native
data sets, configuration/calibration bundle IDs, processed-axis outputs,
cross-run comparison, artifact audit, safe-stop records, no-fire fault-injection
record, recovery record, and normal-wiring restoration.

### 26. RPT-01 — calibration reporting, uncertainty, and reuse package

Create the reusable package that downstream characterization, thesis analysis,
and experimental campaigns will consume. This is analysis-only and does not
repeat acquisition.

Mandatory closeout deliverables:

- Versioned calibration-bundle manifest linking every promoted candidate value
  to raw evidence, analysis code, correction terms, units, reference planes,
  covariance, validity envelope, and unresolved limitations.
- Three experiment-specific HF2LI configuration IDs, their acquisition-rate,
  time-constant, filter-order, settling, bandwidth, and record-length validity
  envelopes, plus any measured biological equivalence/alias record. Reporting
  must not silently substitute one biological configuration for the other.
- The reusable HF-01 electrical response bundle containing the monitored-AWG
  topology, three-anchor validation, computational setting-evaluation table,
  complex transfer/step/noise/range/rate/selected-channel-equivalence models,
  covariance, validity limits, and explicit downstream non-duplication links.
- Aggregation-ready acquisition/artifact indexes for all phases, including the
  previously completed phases without relocating or rewriting their raw data.
- GUM-style budgets, thesis claim-to-evidence matrix, bypass register,
  data dictionary, machine-readable summary tables, and reproducible figure
  scripts.
- Retention audit confirming raw, rejected, excluded, and superseded evidence
  remain recoverable and distinguishable.
- Electronic-iris reuse package containing the control/service version,
  permanent mount/fiducials, accepted 540 nm setpoint and tolerance, optical
  transfer and contamination bounds, validity envelope, command/readback
  requirements, and revalidation triggers. Preserve the pre-iris OM-01 result
  as historical mixed-spectrum evidence rather than relabeling it.
- WaveMaster working-reference package containing its WM-01 identity,
  adapter/power/probe configuration, native response-state contract,
  measurement settings, repeatability and uncertainty, validity envelope,
  bundle/quantity IDs, and the distinction between center-wavelength evidence
  and spectral-power-fraction evidence.

### 27. PROM-01 — promotion gate

Present results, uncertainties, bypasses, unresolved terms, closure/E2E results,
retention audit, proposed canonical diff, and characterization prerequisites.
Make no canonical change without the exact approval phrase
`APPROVE CALIBRATION PROMOTION`.

Mandatory closeout deliverables: reviewed promotion candidate, exact diff,
approved calibration bundle ID and validity date if promoted, rollback/archive
plan, and updated downstream dependency record. After promotion and retention
review, the campaign directory can be archived as one independent unit.

The promotion candidate must include the electronic-iris control/optical-
transfer bundle and the qualified WaveMaster working-reference bundle. It must
not promote the original OM-01 mixed-spectrum indication as post-iris 540 nm
sample-plane power or a WaveMaster center wavelength as a spectral-power
fraction.

## Characterization handoff gate

`characterization/system_characterization_001` may be planned in parallel but
may not begin emitting or quantitative acquisition until its required
calibration dependencies are promoted or explicitly accepted as bounded
provisional inputs. It imports calibration bundle IDs and existing evidence;
it does not copy raw calibration files or reacquire completed calibration work.

Every OPO-540 handoff names the permanent ATT-01 iris configuration and WM-01
wavelength working-reference bundle; another OPO wavelength remains outside
the handoff until its own iris/beam-center qualification is approved and
completed.

The hardwired room and door interlocks remain external to software execution.
