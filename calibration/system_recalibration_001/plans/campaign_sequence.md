# Complete calibration sequence (expanded)

Campaign: `system_recalibration_001`

Status: **T1-01 COMPLETE; PT-01 IN PROGRESS; PT-01 SETUP 1 OPERATOR ACTION REQUIRED**

This plan expands the original calibration scope to close the metrology gaps
needed by the instrument-characterization campaign, thesis, and downstream
experiments.
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

PT-01 is already in progress in `readbacks/PT-01/`. Resume that stable record;
do not create a replacement PT-01 directory or rerun its completed preflight.

## Global execution and advancement gates

1. Approval is phase-specific. Approval of this plan does not approve any
   hardware phase or physical action.
2. Read existing phase evidence before acting. Give the operator one physical
   action at a time and wait for the actual observation.
3. Before every physical transition, apply and verify the applicable safe-idle
   state. A failed safe-idle readback blocks the transition.
4. Laser emission requires a separate written phase approval and a frozen shot
   budget. No rejected acquisition silently authorizes another emitted shot.
5. T660-1 CHD and MIRcat DB9 pin 5 remain disconnected and unused; MIRcat DB9
   pins 6 and 8 remain unused and unwired.
6. Unavailable metadata are recorded as `USER_INPUT_REQUIRED`. Independent
   valid work may continue, but affected claims remain limited.
7. A phase closes only when every mandatory deliverable below exists, is
   internally consistent, and the final equipment state is recorded. If a
   deliverable cannot be completed, the phase remains open or closes as a
   documented bypass with its downstream claim limitation.
8. Canonical calibration outputs remain unchanged until PROM-01 passes and the
   user supplies the exact phrase `APPROVE CALIBRATION PROMOTION`.

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

### 6. PT-01 — MIRcat Process Trigger electrical timing — IN PROGRESS

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

### 7. MC-01 — MIRcat GUI process-trigger qualification

Under manufacturer-GUI ownership, verify external laser/process-trigger modes,
first and subsequent channel behavior, pulse counts, Sweep Active transitions,
and the permitted delay after Sweep Active falls. No SDK connection or
automation occurs until this phase passes.

Mandatory closeout deliverables:

- GUI/version/firmware provenance, selected operating modes, screenshots or
  exported logs, T660 readbacks, DIO evidence, and a timestamped action ledger.
- Expected-versus-observed state/pulse table covering first and subsequent
  channels, bounded repeats, exceptions, and failure behavior.
- Ownership release, safe shutdown, restoration record, uncertainty/ambiguity
  statement, and explicit SDK-automation eligibility decision.

### 8. TR-01 — retained identity and measurement-resource closure

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

### 9. OM-01 — optical metrology readiness and transfer standards

Qualify only the available instruments selected after downstream experiment
requirements define the needed pump/probe power, wavelength, beam-size,
polarization, attenuation, and observational ambient records. No energy meter
is currently available, so this phase does not require direct pulse-energy
measurement. It does not characterize the pump or probe beams themselves.

At each intended wavelength/range, record zeroing, background, sensor head,
range, wavelength correction, sampling mode, warm-up, linearity/check points,
repeatability, saturation limits, spatial-scale calibration, and the applicable
manufacturer specification or available comparison. Do not add a new meter or
certificate task unless an approved experimental claim requires it.

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

### 10. ATT-01 — optical attenuation and sample-plane transfer calibration

Characterize every neutral-density filter, attenuator, installed or temporary
beamsplitter, meter pickoff, window, or preview element used to transfer
source-plane measurements to the sample or detector planes. Unused elements
are not measured. A nominal 50/50 label is never used as a correction value.
For the installed sample/reference splitter, measure both output-port powers
from the same incident condition and quantify total insertion loss and the
port-resolved split versus wavenumber, polarization, alignment, and operating
power wherever those dependencies are material.

Mandatory closeout deliverables:

- Stable component IDs, orientation, wavelength, polarization, mounting, and
  reference-plane photographs/diagrams.
- Raw incident/transmitted readings, dark subtraction, transmission or optical
  density with repeatability and uncertainty, linearity/saturation checks, and
  wavelength interpolation limits.
- For every used splitter: incident power, both output powers, total recovered
  power, insertion loss, `f_sample = P_sample/(P_sample + P_reference)`,
  `f_reference`, `P_sample/P_reference`, wavelength/polarization/alignment
  dependence, revisit drift, and covariance/uncertainty. Record the exact port,
  orientation, and downstream reference plane for every reading.
- Machine-readable transfer matrix identifying which corrections may be used
  in each later phase. No uncharacterized attenuator may enter an emitting
  phase silently, and no downstream calculation may assume a 0.5 split.

### 11. HF-01 — HF2LI configuration and external-reference qualification

Verify reference lock/readback, demodulator assignments, rates, time constants,
filter orders, phase, ranges, clipping margin, and reload equivalence.

Mandatory closeout deliverables: complete node snapshot, configuration diff
after reload, reference-frequency comparison, phase/filter response results,
range/clipping tests, raw records, uncertainty/acceptance table, and restorable
approved configuration ID.

### 12. MD-01 — MIRcat/HF2LI DIO mapping qualification

Use the accepted side-experiment mapping (pin 1 to bit 20, pin 2 to bit 21,
pin 3 to bit 22) without repeating the mapping-only discovery. Acquire
campaign-local repeated scans in both directions to verify polarity/state
semantics, direction behavior, signatures, counts, timing, and repeatability.

Mandatory closeout deliverables: complete DIO words rather than selected bits,
MIRcat logs, HF2LI configuration ID, pin/bit/state truth table, direction and
transition signatures, count reconciliation, timestamp alignment, raw artifact
index entries, and an explicit qualification decision.

### 13. MSW-01 — MIRcat sweep timing

At 5 cm^-1 trigger spacing, 500 us pulse width, and 40 cm^-1/s, measure trigger
spacing, counts/jitter, Sweep Active segments/gaps, direction, channel
transitions, scan repeatability, and host-independent correlation.

Mandatory closeout deliverables: at least three complete scans per direction,
raw MIRcat and HF2LI/DIO streams, trigger/segment event table, expected-versus-
observed counts, approximately 125 ms spacing check, transition/gap analysis,
clock/reference conventions, uncertainty, and acceptance decision.

### 14. HF-02 — cross-stream alignment, loss, and endurance

Verify simultaneous Sample, Reference, and complete-DIO timestamps, API/server
buffering, dropped samples, scan-boundary behavior, and endurance over at least
two full-duration scans using the approved HF-01 configuration.

Mandatory closeout deliverables: native streams, common-event alignment table,
sample-count and gap audit, loss/reorder/duplicate statistics, host/server
clock record, resource/endurance log, configuration reload check, and a maximum
supported scan envelope with uncertainty or limitation.

### 15. DET-01 — dark detector/electronics performance

With non-emitting sources, determine dark noise, drift, Allan-style stability,
electrical cross-talk, range dependence, and short/long-duration repeatability.

Mandatory closeout deliverables: exact installed detector/amplifier/power-
supply identities and settings, blocked-state definition, environmental log,
raw Sample/Reference records, PSD/Allan/noise tables, cross-talk controls,
uncertainty budget, and accepted dark-operating configuration.

### 16. DET-02 — illuminated detector/electronics transfer performance

Using OM-01/ATT-01-qualified metrology and separately authorized illumination,
measure each detector/amplifier/HF2LI channel's response against independently
measured incident power: gain or responsivity, linearity, saturation, SNR,
noise, and wavelength dependence over the unequal power ranges expected after
the installed splitter. Use a common calibrated transfer detector/source or an
approved branch/detector interchange where practical to separate detector-
electronics response from optical-path transmission. Do not repeat DET-01 dark
acquisitions; import their result bundle.

Mandatory closeout deliverables: frozen illumination budget and conditions,
raw detector and optical-meter data, incident-power reference planes,
attenuation/transfer IDs, per-channel response curves, fit residuals,
saturation and recommended operating margins, detector-gain ratio with
uncertainty, accepted/rejected ledger, and safe restoration. Identify which
part of the channel mismatch belongs to detector/electronics response rather
than optical splitting. Report installed-chain response to the qualified
available power meter; accredited absolute detector responsivity is outside
scope.

### 17. DET-03 — detector temporal-response and latency correction

Measure or authoritatively bound the response delay and temporal bandwidth of
the exact detector/amplifier/cable/acquisition path used by OP-01. This is a
new missing correction term; it does not repeat MS-01/MS-02 or T1-01.

Mandatory closeout deliverables: stimulus/reference planes, detector placement
and cable IDs, raw response data or authoritative model record, amplitude-
dependence and threshold checks, latency/bandwidth estimate, sign convention,
standard uncertainty, validity envelope, and a stable correction ID accepted
for OP-01.

### 18. DET-04 — installed sample/reference optical-balance and normalization calibration

Combine ATT-01's component/port measurements with DET-02's separate channel
response functions in the final installed sample/reference optical paths.
Measure power at the sample and reference detector planes separately under the
same source condition. Establish the end-to-end optical balance, detector-
electronics balance, and measured system baseline ratio without assuming the
splitter is 50/50.

Use the wavelengths, polarization states, alignments, and power levels required
by the downstream spectral and biological operating envelope. Include at least
one controlled realignment/revisit. If detector or branch exchange is safe and
practical, use it as a separation/closure test; otherwise use the same
qualified transfer detector sequentially at both detector planes and retain
the placement/repeatability uncertainty.

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

### 19. SP-01 — spectral-reference provenance

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

### 20. SP-02 — spectral-axis calibration

Measure internal-readback accuracy, trigger-derived axis, per-channel behavior,
direction hysteresis, crossovers, effective sampling/interpolation, reference
agreement, and scan-to-scan repeatability using qualified prior phases. Import
the DET-04 balance/normalization bundle; do not estimate or assume a 50/50
split from the spectral data.

Mandatory closeout deliverables: native spectra/readbacks/DIO streams, at least
three scans per direction and relevant channel, frozen calibration fit, residual
and hysteresis tables, interpolation method, uncertainty budget, independent
validation partition, DET-04 correction ID, raw and normalized Sample/Reference
products, and validity range. Calibration data and validation data must remain
separately identifiable.

### 21. OP-01 — operational pump-command-to-sample timing

Execute the previously defined bounded optical timing measurement using the
identified straight barrel adapter correction (0.125 ns with 0.0722 ns
rectangular standard uncertainty), MS-01/MS-02 results, and DET-03 detector
correction. The Q-switch cable, loaded Nd:YAG response, internal laser/OPO
response, and optical propagation remain intentionally included.

Mandatory closeout deliverables: frozen shot budget; blocked control; one
attenuated preview; at most 100 planned measurement shots unless separately
approved; raw traces; shot/rejection/counter ledger; SNR/saturation checks;
adapter/splitter/detector/placement IDs; signed correction equation; placement
and restoration repeatability; uncertainty budget; photographs; and final safe
state. No automatic replacement shots are permitted.

### 22. CL-01 — complete timing-chain closure

Calculate direct and derived chains only between compatible reference planes.
Keep programmed, cable-end, device-pin, detector, optical, and chemical origins
distinct and establish the operational nonzero-delay correction and pump-probe
equation.

Mandatory closeout deliverables: machine-readable correction-term register,
reference-plane graph, covariance-aware uncertainty propagation, closure table
and residuals, incompatible-chain rejection list, validity/configuration IDs,
and pass/fail decisions against frozen engineering limits.

### 23. E2E-01 — normal-wiring validation

Perform two bounded normal experimental runs covering startup, ownership,
T660s, MIRcat/reference lock, Sample/Reference/full-DIO capture, pump only if
authorized, axes, processing, safe stop, repeatability, artifact completeness,
and recovery from a simulated software failure without unintended firing.

Mandatory closeout deliverables: two complete independent manifests and native
data sets, configuration/calibration bundle IDs, processed-axis outputs,
cross-run comparison, artifact audit, safe-stop records, no-fire fault-injection
record, recovery record, and normal-wiring restoration.

### 24. RPT-01 — calibration reporting, uncertainty, and reuse package

Create the reusable package that downstream characterization, thesis analysis,
and experimental campaigns will consume. This is analysis-only and does not
repeat acquisition.

Mandatory closeout deliverables:

- Versioned calibration-bundle manifest linking every promoted candidate value
  to raw evidence, analysis code, correction terms, units, reference planes,
  covariance, validity envelope, and unresolved limitations.
- Aggregation-ready acquisition/artifact indexes for all phases, including the
  previously completed phases without relocating or rewriting their raw data.
- GUM-style budgets, thesis claim-to-evidence matrix, bypass register,
  data dictionary, machine-readable summary tables, and reproducible figure
  scripts.
- Retention audit confirming raw, rejected, excluded, and superseded evidence
  remain recoverable and distinguishable.

### 25. PROM-01 — promotion gate

Present results, uncertainties, bypasses, unresolved terms, closure/E2E results,
retention audit, proposed canonical diff, and characterization prerequisites.
Make no canonical change without the exact approval phrase
`APPROVE CALIBRATION PROMOTION`.

Mandatory closeout deliverables: reviewed promotion candidate, exact diff,
approved calibration bundle ID and validity date if promoted, rollback/archive
plan, and updated downstream dependency record. After promotion and retention
review, the campaign directory can be archived as one independent unit.

## Characterization handoff gate

`characterization/system_characterization_001` may be planned in parallel but
may not begin emitting or quantitative acquisition until its required
calibration dependencies are promoted or explicitly accepted as bounded
provisional inputs. It imports calibration bundle IDs and existing evidence;
it does not copy raw calibration files or reacquire completed calibration work.

The hardwired room and door interlocks remain external to software execution.
