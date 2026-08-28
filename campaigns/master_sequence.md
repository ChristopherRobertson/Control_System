# Master campaign sequence

Status: **AUTHORITATIVE CAMPAIGN INSTRUCTIONS; NO HARDWARE EXECUTION AUTHORIZED**

This document is the human-readable authority for completing the full
instrument-readiness, HRP, and optional cryogenic MbCO program. It defines the
campaign-wide execution rules, dependency order, purpose, required products, and
phase-specific plan location for every phase. Calibration and characterization
are integrated scientific domains in a single readiness sequence.

Use [`phase_registry.yaml`](phase_registry.yaml) as the machine-readable companion
for phase identity, current status, dependencies, plan paths, evidence keys, and
documentation state. Use
[`instrument_readiness_001/requirements.md`](instrument_readiness_001/requirements.md)
for cross-phase methods and measurement coverage. The linked phase `plan.md` is
the detailed procedure and acceptance authority for that phase.

## How to use this sequence

For each authorized phase:

1. Confirm its current registry status and every required dependency. A satisfied
   dependency permits scheduling; it does not authorize execution.
2. Read this phase entry, the complete phase `plan.md`, the campaign requirements,
   the applicable hardware/wiring records, and each imported result's validity
   envelope.
3. Create or resume the phase record in its canonical phase directory. Record the
   initial state and evidence destination before changing hardware.
4. Follow the plan in order. During operator-guided work, present one physical
   action at a time, wait for the operator's observation, and record the result.
   Multiple physical actions may be presented together as explicit steps when no
   measurement is made between them.
5. Apply the declared stop rules, exclusions, uncertainty model, and acceptance
   criteria. Never infer missing operator input or silently extend the test grid.
6. Restore and document the required state, evaluate every closeout criterion,
   and assign an explicit scientific disposition.
7. Complete the indexed evidence package, `final_report.md`, and
   `procedural_writeup.md` required by
   [`phase_record_contract.md`](../docs/phase_record_contract.md). The writeup must
   explain WHY the phase was needed, HOW it was actually performed step by step,
   WHAT the results were, and which implications, caveats, and claims the evidence
   supports.
8. Update the registry only after review. Begin no successor and promote no result
   without its own authorization.

Completed evidence remains authoritative for its recorded scientific disposition.
When a completed phase lacks a required writeup, reconstruct it from retained
evidence, identify unknowns, and bound the claims; do not repeat the measurement
solely to fill a documentation gap. A summary, final report, commit, checksum, or
matching hash cannot substitute for the procedural writeup or act as an
operational gate.

Catalog order expresses the intended integration flow. Required dependencies take
precedence, and phases whose dependencies are independently satisfied may run in
parallel only under separate authorization.

## Dependency roadmap

1. Retain the completed electrical and control baseline:
   `P0 -> S0 -> MS-01 -> MS-02 -> T2-01 -> T1-01 -> PT-01 -> MC-01`.
2. Retain the completed resource and claim foundations:
   `P0 -> TR-01 -> OM-01`, `P0 + TR-01 -> CH-00`, and
   `T2-01 + TR-01 -> HF-01`.
3. Preserve the in-progress `WM-01` package and resume its remaining measurements
   only after a qualified replacement spectrometer is available. In parallel,
   schedule dependency-ready work such as `HF-01.1`, `MD-01`, `DET-01`, `SP-01`,
   `SC-01`, and HRP R0 planning only after each entry's own resources and
   authorization are satisfied. SV-01 waits for SP-01.
4. Complete timing/data-stream qualification through `MD-01 -> MSW-01 -> HF-02`
   and optical/detector readiness through `WM-01 -> ATT-01`,
   `DET-01 -> DET-02 -> DET-03/DET-04`, plus `QB-01`, `PB-02`, and `SC-01`.
5. Establish installed geometry and operating choices through
   `QB-01 + PB-02 + SC-01 + OM-01 + ATT-01 -> OG-01 -> OV-01`, then converge
   at `AR-01` and `PF-00`.
6. Freeze and independently validate the spectral chain through
   `SP-01 -> SP-02`, `SP-01 -> SV-01`, and
   `PF-00 + SP-02 + SV-01 + AR-01 + DET-04 -> SV-02A -> SV-02B`.
7. Close operational timing through `OP-01 -> FE-01 -> CL-01`, then complete
   `IR-01`, `PF-01`, and `RP-01`.
8. Demonstrate, report, and promote the platform through `E2E-01 -> RPT-01 ->
   PROM-01` and `E2E-01 + SV-02B + IR-01 + PF-01 + RP-01 -> E2E-CH -> RPT-CH
   -> PROM-CH`.
9. Execute HRP through its gated R0-R9 sequence. Only after R9 restoration and
   handoff may the optional `QB-01M` and MB-00-MB-09 cryogenic MbCO branch begin.

## Ordered phase catalog

### Instrument readiness, calibration, characterization, and validation

### P0 — provenance and inventory baseline

- **Status:** complete. **Prerequisites:** none.
- **Purpose:** Establish the campaign boundary, installed hardware and accessory
  identities, software provenance, available references, unresolved resources,
  and the decision basis for all later work.
- **Primary products:** Physical inventory, provenance records, blocker and
  decision registers, requirement disposition, and the baseline configuration.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`P0/plan.md`](instrument_readiness_001/phases/P0/plan.md).

### S0 — safe-idle and interlock verification

- **Status:** complete. **Prerequisites:** P0.
- **Purpose:** Demonstrate exclusive ownership, known device identities,
  interlock state, inhibited sources, disabled T660 outputs, and a recoverable
  safe starting condition before measurement work.
- **Primary products:** Safe-state readbacks, operator confirmations, identity
  records, command log, and final cleanup/restoration evidence.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`S0/plan.md`](instrument_readiness_001/phases/S0/plan.md).

### MS-01 — PicoScope differential channel and path skew

- **Status:** complete. **Prerequisites:** S0.
- **Purpose:** Measure the relative delay of the PicoScope channels and their
  measurement paths so later two-channel timing observations can be corrected.
- **Primary products:** Normal/swapped captures, settings, path-skew estimate,
  uncertainty and sensitivity analysis, and restoration record.
- **Final Report:** [`MS-01/final_report.md`](instrument_readiness_001/phases/MS-01/final_report.md).
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`MS-01/plan.md`](instrument_readiness_001/phases/MS-01/plan.md).

### MS-02 — splitter branch skew and measurement-system sensitivities

- **Status:** complete. **Prerequisites:** MS-01.
- **Purpose:** Separate splitter-branch delay from channel/path delay and quantify
  threshold, interpolation, timebase, pulse-fidelity, and reconnection effects.
- **Primary products:** Swapped-branch acquisitions, corrected splitter result,
  sensitivity studies, uncertainty budget, and validity limitations.
- **Final Report:** [`MS-02/final_report.md`](instrument_readiness_001/phases/MS-02/final_report.md).
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`MS-02/plan.md`](instrument_readiness_001/phases/MS-02/plan.md).

### T2-01 — direct T660-2 routes

- **Status:** complete. **Prerequisites:** MS-02.
- **Purpose:** Calibrate the installed T660-2 timing routes to the DAQ, MIRcat,
  and T660-1 reference planes without repeating measurement-system calibration.
- **Primary products:** Route sweeps, fitted delays and jitter, rejected/accepted
  trace indexes, pulse-fidelity evidence, and route validity envelopes.
- **Final Report:** [`T2-01/final_report.md`](instrument_readiness_001/phases/T2-01/final_report.md).
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`T2-01/plan.md`](instrument_readiness_001/phases/T2-01/plan.md).

### T1-01 — T660-1 trigger and output routes

- **Status:** complete. **Prerequisites:** T2-01.
- **Purpose:** Calibrate T660-1 trigger/output routes and close adapter, trigger
  count, polarity, and direct-versus-derived timing questions.
- **Primary products:** Six-point route results, adapter swap characterization,
  trigger diagnostics, electrical closure analysis, and restoration evidence.
- **Final Report:** [`T1-01/final_report.md`](instrument_readiness_001/phases/T1-01/final_report.md).
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`T1-01/plan.md`](instrument_readiness_001/phases/T1-01/plan.md).

### PT-01 — MIRcat Process Trigger electrical timing

- **Status:** complete. **Prerequisites:** T1-01.
- **Purpose:** Determine the electrical behavior and timing of the retained
  MIRcat Process Trigger route at its approved reference plane.
- **Primary products:** Raw timing captures, polarity and width results, path
  corrections, reference-plane definition, uncertainty, and safe restoration.
- **Final Report:** [`PT-01/final_report.md`](instrument_readiness_001/phases/PT-01/final_report.md).
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`PT-01/plan.md`](instrument_readiness_001/phases/PT-01/plan.md).

### MC-01 — MIRcat GUI process-trigger qualification

- **Status:** complete. **Prerequisites:** PT-01.
- **Purpose:** Qualify the retained MIRcat GUI point/process sequence, bounded
  repeat behavior, state transitions, trigger correlation, ownership release,
  and subsequent SDK eligibility without optical emission.
- **Primary products:** GUI/firmware provenance, action ledger, DIO evidence,
  bounded-repeat results, automation prerequisites, and shutdown/restoration.
- **Final Report:** [`MC-01/final_report.md`](instrument_readiness_001/phases/MC-01/final_report.md).
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`MC-01/plan.md`](instrument_readiness_001/phases/MC-01/plan.md).

### TR-01 — retained identity and measurement-resource closure

- **Status:** complete. **Prerequisites:** P0.
- **Purpose:** Resolve retained P0 identity and metrology requirements, classify
  devices versus working references, and record applicable uncertainty bases
  without reacquiring completed measurements or reviving discarded work.
- **Primary products:** Measurement-resource register, source-provenance index,
  P0 decision export, validity limits, and explicit claim limitations.
- **Final Report:** [`TR-01/final_report.md`](instrument_readiness_001/phases/TR-01/final_report.md).
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`TR-01/plan.md`](instrument_readiness_001/phases/TR-01/plan.md).

### OM-01 — optical metrology readiness and transfer standards

- **Status:** complete. **Prerequisites:** TR-01.
- **Purpose:** Qualify the available optical metrology resources and transfer
  methods needed for power, wavelength correction, beam size, and observational
  conditions over the retained operating grid.
- **Primary products:** Optical-metrology bundle, configuration manifest,
  correction tables, saturation and spatial methods, uncertainty, and limits.
- **Final Report:** [`OM-01/final_report.md`](instrument_readiness_001/phases/OM-01/final_report.md).
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`OM-01/plan.md`](instrument_readiness_001/phases/OM-01/plan.md).

### CH-00 — claim scope and calibration-import freeze

- **Status:** complete. **Prerequisites:** P0 and TR-01.
- **Purpose:** Freeze the supported thesis/characterization claims, minimum test
  grid, configuration identities, acceptance logic, exposure policy, calibration
  imports, and explicit exclusions before characterization expands.
- **Primary products:** Claim-to-measurement map, frozen test grid, dependency
  graph, configuration conventions, uncertainty rules, and exclusion register.
- **Final Report:** [`CH-00/final_report.md`](instrument_readiness_001/phases/CH-00/final_report.md).
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`CH-00/plan.md`](instrument_readiness_001/phases/CH-00/plan.md).

### HF-01 — HF2LI configuration and external-reference qualification

- **Status:** complete. **Prerequisites:** T2-01 and TR-01.
- **Purpose:** Qualify the supported HF2LI configuration space, complex transfer
  behavior, external reference, timing, dual-input equivalence, range, clipping,
  loss handling, and reproducible reload behavior.
- **Primary products:** Accepted anchors, validated transfer model, supported
  configurations, residual/uncertainty analysis, and restoration evidence.
- **Final Report:** [`HF-01/final_report.md`](instrument_readiness_001/phases/HF-01/final_report.md).
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`HF-01/plan.md`](instrument_readiness_001/phases/HF-01/plan.md).

### HF-01.1 — experiment-specific HF2LI candidate optimization and confirmation

- **Status:** planned. **Prerequisites:** HF-01 and CH-00.
- **Purpose:** Use the completed HF-01 model to optimize separate sweep, HRP,
  and MbCO acquisition candidates, then electrically confirm only the winning
  and nearest meaningful challenger configurations.
- **Primary products:** Frozen requirements, complete candidate tables, Pareto
  frontiers, shortlisted configurations, targeted confirmations, and selections.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`HF-01.1/plan.md`](instrument_readiness_001/phases/HF-01.1/plan.md).

### WM-01 — visible and near-IR wavelength-metrology readiness

- **Status:** in progress; deferred pending a suitable replacement instrument.
  **Prerequisites:** OM-01.
- **Purpose:** Qualify a campaign-local wavelength working reference for the
  installed visible/near-IR source conditions, including communications,
  response states, settings, repeatability, geometry, and uncertainty authority.
- **Primary products:** Working-reference identity/configuration bundle, native
  response records, repeatability and validity envelope, or documented deferral.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`WM-01/plan.md`](instrument_readiness_001/phases/WM-01/plan.md).

### MD-01 — MIRcat and HF2LI DIO mapping qualification

- **Status:** planned. **Prerequisites:** HF-01.
- **Purpose:** Establish the semantic and electrical mapping between MIRcat
  states/events and HF2LI DIO observations used for synchronization and loss
  accounting.
- **Primary products:** DIO bit/event map, timing/state evidence, ambiguity and
  failure handling, configuration record, and accepted mapping rules.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`MD-01/plan.md`](instrument_readiness_001/phases/MD-01/plan.md).

### MSW-01 — MIRcat sweep timing

- **Status:** planned. **Prerequisites:** MC-01 and MD-01.
- **Purpose:** Measure MIRcat sweep timing, direction behavior, event alignment,
  start/stop semantics, and wavenumber-versus-time behavior needed for sampled
  spectral reconstruction.
- **Primary products:** Native sweep/readback/DIO records, timing model, direction
  comparison, repeatability, loss accounting, and uncertainty.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`MSW-01/plan.md`](instrument_readiness_001/phases/MSW-01/plan.md).

### HF-02 — cross-stream alignment loss and endurance

- **Status:** planned. **Prerequisites:** HF-01, MD-01, and MSW-01.
- **Purpose:** Verify sustained alignment among MIRcat, DIO, HF2LI, and recorded
  streams; quantify missing, duplicated, misordered, or delayed records over
  experiment-relevant durations.
- **Primary products:** Endurance streams, alignment/loss metrics, fault evidence,
  throughput envelope, recovery behavior, and acceptance limits.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`HF-02/plan.md`](instrument_readiness_001/phases/HF-02/plan.md).

### DET-01 — dark detector and electronics performance

- **Status:** planned. **Prerequisites:** HF-01 and TR-01.
- **Purpose:** Characterize detector/electronics behavior without illumination,
  separating dark offset, noise, drift, range, saturation, and HF2LI effects.
- **Primary products:** Dark records, noise and drift spectra, range/saturation
  limits, channel comparison, uncertainty, and accepted electronic envelope.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`DET-01/plan.md`](instrument_readiness_001/phases/DET-01/plan.md).

### SP-01 — spectral-reference provenance

- **Status:** planned. **Prerequisites:** TR-01.
- **Purpose:** Establish authoritative polystyrene and Mylar feature/reference
  values, specimen identity, applicability, uncertainties, and separation of
  calibration, validation, and illustrative sources.
- **Primary products:** Reference registry, feature tables, source provenance,
  uncertainty authority, specimen restrictions, and validity decisions.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`SP-01/plan.md`](instrument_readiness_001/phases/SP-01/plan.md).

### ATT-01 — electronic iris attenuation and sample-plane transfer calibration

- **Status:** planned. **Prerequisites:** WM-01 and OM-01.
- **Purpose:** Qualify the permanent electronic iris as an operating component,
  determine its 540 nm command/readback aperture and attenuation/transfer
  behavior, and freeze its installed placement and configuration limits.
- **Primary products:** Iris identity/API record, attenuation and transfer curves,
  aperture setpoint/tolerance, beam/aperture margin, faults, and configuration ID.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`ATT-01/plan.md`](instrument_readiness_001/phases/ATT-01/plan.md).

### DET-02 — illuminated detector and electronics transfer performance

- **Status:** planned. **Prerequisites:** DET-01, ATT-01, and HF-01.1.
- **Purpose:** Characterize detector/electronics response under controlled
  illumination across the retained ranges and selected HF2LI configurations.
- **Primary products:** Transfer/linearity data, range and saturation envelope,
  noise versus signal, gain/phase behavior, uncertainty, and accepted settings.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`DET-02/plan.md`](instrument_readiness_001/phases/DET-02/plan.md).

### DET-03 — detector temporal response and latency correction

- **Status:** planned. **Prerequisites:** DET-02 and HF-01.
- **Purpose:** Measure detector/electronics temporal response, latency, bandwidth,
  and configuration-dependent correction needed for timing-chain and IRF work.
- **Primary products:** Step/impulse response, delay and bandwidth model, correction
  terms, uncertainty, and configuration-specific validity envelope.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`DET-03/plan.md`](instrument_readiness_001/phases/DET-03/plan.md).

### DET-04 — installed sample-reference balance and normalization calibration

- **Status:** planned. **Prerequisites:** DET-02 and ATT-01.
- **Purpose:** Quantify installed sample/reference imbalance and covariance so
  normalized signals use measured corrections rather than assumed equal powers.
- **Primary products:** Channel-balance and background-ratio corrections,
  covariance model, normalization method, uncertainty, and validity conditions.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`DET-04/plan.md`](instrument_readiness_001/phases/DET-04/plan.md).

### QB-01 — MIRcat probe-source characterization

- **Status:** planned. **Prerequisites:** MD-01, MSW-01, HF-02, and DET-02.
- **Purpose:** Characterize the installed MIRcat probe across the required bands,
  pulse widths, currents, rates, scan behavior, stability, timing, and detector
  operating constraints.
- **Primary products:** Source operating envelope, spectral/power/timing records,
  stability and repeatability metrics, saturation limits, and accepted modes.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`QB-01/plan.md`](instrument_readiness_001/phases/QB-01/plan.md).

### PB-02 — 540 nm OPO output characterization

- **Status:** planned. **Prerequisites:** WM-01 and ATT-01.
- **Purpose:** Characterize the biologically relevant 540 nm OPO output after the
  permanent iris over the retained command, delay, rate, power, spatial, and
  wavelength conditions.
- **Primary products:** Post-iris power/wavelength/beam envelope, stability and
  uncertainty, iris configuration linkage, limits, and safe restoration.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`PB-02/plan.md`](instrument_readiness_001/phases/PB-02/plan.md).

### SC-01 — sample-cell and temperature-stage qualification

- **Status:** planned. **Prerequisites:** TR-01.
- **Purpose:** Qualify cell materials, path, windows, seals, filling, leak and
  bubble behavior, transmission, temperature control, gradients, and recovery.
- **Primary products:** Cell/stage configuration, path and thermal results,
  blank/transmission evidence, compatibility limits, uncertainty, and procedures.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`SC-01/plan.md`](instrument_readiness_001/phases/SC-01/plan.md).

### OG-01 — sample-plane optical transfer and beam geometry

- **Status:** planned. **Prerequisites:** QB-01, PB-02, SC-01, OM-01, and ATT-01.
- **Purpose:** Transfer qualified source measurements to the sample plane and
  determine beam size, centroid, profile, polarization applicability, clipping,
  and geometry through the installed cell path.
- **Primary products:** Sample-plane power/fluence transfer, beam maps, geometry
  and aperture margins, polarization record, uncertainty, and alignment limits.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`OG-01/plan.md`](instrument_readiness_001/phases/OG-01/plan.md).

### OV-01 — pump-probe overlap and placement repeatability

- **Status:** planned. **Prerequisites:** OG-01.
- **Purpose:** Measure pump-probe spatial overlap, placement repeatability, drift,
  and restoration/fiducial performance at the sample-equivalent plane.
- **Primary products:** Overlap maps and metric, alignment/fiducial procedure,
  repeatability and drift results, uncertainty, and revalidation triggers.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`OV-01/plan.md`](instrument_readiness_001/phases/OV-01/plan.md).

### AR-01 — joint scan-speed and HF2LI acquisition optimization

- **Status:** planned. **Prerequisites:** HF-01.1, MSW-01, HF-02, DET-02,
  DET-03, DET-04, QB-01, OG-01, and OV-01.
- **Purpose:** Jointly select experiment-specific scan speed, direction, HF2LI
  filtering/rate/range, record length, settling, throughput, and loss margins
  using measured source, detector, geometry, and timing behavior.
- **Primary products:** Validated sweep, HRP, and MbCO acquisition configurations,
  response residuals, speed/dwell envelope, robustness, and uncertainty.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`AR-01/plan.md`](instrument_readiness_001/phases/AR-01/plan.md).

### PF-00 — pre-standard full-system noise and SNR readiness

- **Status:** planned. **Prerequisites:** AR-01, DET-04, SC-01, and OG-01.
- **Purpose:** Demonstrate sufficient normalized baseline noise, common-mode
  rejection, drift, saturation margin, and SNR using nonbiological conditions
  before consuming spectral standards.
- **Primary products:** Baseline/noise/SNR records, normalization audit, artifact
  assessment, readiness decision, and conditions for SV-02A entry.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`PF-00/plan.md`](instrument_readiness_001/phases/PF-00/plan.md).

### SP-02 — spectral-axis calibration

- **Status:** planned. **Prerequisites:** SP-01, AR-01, and DET-04.
- **Purpose:** Establish the instrument spectral-axis mapping, direction effects,
  repeatability, correction model, and uncertainty under the selected acquisition
  and normalization conditions before standard-based freeze.
- **Primary products:** Native/readback streams, axis mapping and residuals,
  direction/repeatability analysis, correction candidate, and uncertainty.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`SP-02/plan.md`](instrument_readiness_001/phases/SP-02/plan.md).

### SV-01 — independent FTIR reference acquisition

- **Status:** planned. **Prerequisites:** SP-01.
- **Purpose:** Acquire or register specimen-matched high-resolution FTIR reference
  data for polystyrene calibration and independent Mylar validation.
- **Primary products:** FTIR configuration/provenance, immutable native exports,
  normalized data, preprocessing record, feature authority, and uncertainty.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`SV-01/plan.md`](instrument_readiness_001/phases/SV-01/plan.md).

### SV-02A — polystyrene spectral calibration and correction freeze

- **Status:** planned. **Prerequisites:** PF-00, SP-02, SV-01, AR-01, and DET-04.
- **Purpose:** Fit and freeze the final spectral correction using only predeclared
  polystyrene alignment data, then test its independent polystyrene holdout before
  any Mylar data are opened.
- **Primary products:** Frozen correction and covariance, fit/holdout residuals,
  feature and line-shape metrics, software/version freeze, and Mylar unlock.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`SV-02A/plan.md`](instrument_readiness_001/phases/SV-02A/plan.md).

### SV-02B — blind Mylar independent validation

- **Status:** planned. **Prerequisites:** SV-02A.
- **Purpose:** Apply every frozen acquisition, correction, fitting, and acceptance
  choice to Mylar without allowing Mylar to tune or revise the calibration.
- **Primary products:** Blind forward/reverse validation spectra, position/FWHM/
  shape/hysteresis metrics, uncertainty, deviations, and claim disposition.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`SV-02B/plan.md`](instrument_readiness_001/phases/SV-02B/plan.md).

### OP-01 — operational pump-command-to-sample timing

- **Status:** planned. **Prerequisites:** ATT-01, PB-02, and DET-03.
- **Purpose:** Measure the operational delay and jitter from pump command through
  actual emitted OPO event arrival at the sample-equivalent plane.
- **Primary products:** Synchronized electrical/optical records, time-origin
  definition, delay and jitter model, correction, uncertainty, and envelope.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`OP-01/plan.md`](instrument_readiness_001/phases/OP-01/plan.md).

### FE-01 — finite emitted-pump-event control and reconciliation

- **Status:** planned. **Prerequisites:** OP-01 and PT-01.
- **Purpose:** Prove bounded one-command/one-emitted-event control, event counting,
  reconciliation, stop behavior, and recovery without crediting the static iris
  as a shutter or event limiter.
- **Primary products:** Command/event ledger, reconciliation metrics, bounded
  failure/recovery evidence, exposure accounting, and accepted control rules.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`FE-01/plan.md`](instrument_readiness_001/phases/FE-01/plan.md).

### CL-01 — complete timing-chain closure

- **Status:** planned. **Prerequisites:** OP-01, FE-01, DET-03, and HF-02.
- **Purpose:** Combine measurement-path, trigger, optical-event, detector, DIO,
  and acquisition delays into one end-to-end timing convention and uncertainty.
- **Primary products:** Timing-chain model, correction/uncertainty table, closure
  residuals, reference-plane/time-zero convention, and validity envelope.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`CL-01/plan.md`](instrument_readiness_001/phases/CL-01/plan.md).

### IR-01 — system temporal instrument response

- **Status:** planned. **Prerequisites:** SV-02B, CL-01, DET-03, AR-01, and OV-01.
- **Purpose:** Measure the complete sample-plane instrument response for the
  retained experiment-specific configurations, including pump duration, probe
  gate, jitter, detector response, and lock-in filtering.
- **Primary products:** Synchronized IRF data, response model and resolution,
  delay bias, condition dependence, uncertainty, and biological time-zero handoff.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`IR-01/plan.md`](instrument_readiness_001/phases/IR-01/plan.md).

### PF-01 — platform sensitivity, noise, artifacts, and stability

- **Status:** planned. **Prerequisites:** SV-02B, IR-01, PF-00, PB-02, and OV-01.
- **Purpose:** Establish full-platform noise-equivalent absorbance, detection
  limits, averaging behavior, drift/Allan behavior, artifacts, common-mode
  rejection, stability, and saturation margin under normal optical operation.
- **Primary products:** Short/long controls, noise and sensitivity metrics,
  artifact tests, confidence/uncertainty, and recommended operating envelope.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`PF-01/plan.md`](instrument_readiness_001/phases/PF-01/plan.md).

### RP-01 — between-run reproducibility and operational envelope

- **Status:** planned. **Prerequisites:** PF-01.
- **Purpose:** Test representative checkpoints on independent days and after
  normal restoration/reinstallation to separate within-run, between-run, and
  restoration variability without repeating full characterization grids.
- **Primary products:** Three-day checkpoint records, variance/drift assessment,
  agreement audit, final operating-envelope table, and revalidation triggers.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`RP-01/plan.md`](instrument_readiness_001/phases/RP-01/plan.md).

### E2E-01 — normal-wiring calibration validation

- **Status:** planned. **Prerequisites:** CL-01, SP-02, DET-04, and SV-02B.
- **Purpose:** Verify that the complete promoted-candidate calibration chain works
  together under normal wiring, startup, acquisition, failure, and restoration
  conditions without replacing component-phase evidence.
- **Primary products:** End-to-end calibration records, configuration/calibration
  links, expected-versus-observed checks, fault handling, and readiness decision.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`E2E-01/plan.md`](instrument_readiness_001/phases/E2E-01/plan.md).

### RPT-01 — calibration reporting, uncertainty, and reuse package

- **Status:** planned. **Prerequisites:** E2E-01.
- **Purpose:** Aggregate the completed calibration evidence into reproducible,
  versioned, machine-readable and thesis-ready products without generating
  replacement measurements.
- **Primary products:** Validated indexes, calibration tables and uncertainties,
  claim/evidence map, figures, data dictionary, environment, and retention audit.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`RPT-01/plan.md`](instrument_readiness_001/phases/RPT-01/plan.md).

### PROM-01 — calibration promotion gate

- **Status:** planned. **Prerequisites:** RPT-01.
- **Purpose:** Review the proposed calibration bundle, its evidence, uncertainty,
  validity envelope, limitations, retention, and exact canonical changes before
  explicit promotion authorization.
- **Primary products:** Proposed diff, reviewed bundle, promotion decision,
  validity/revalidation rules, retention/rollback plan, and dependency record.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`PROM-01/plan.md`](instrument_readiness_001/phases/PROM-01/plan.md).

### E2E-CH — bounded nonbiological full-system demonstration

- **Status:** planned. **Prerequisites:** E2E-01, SV-02B, IR-01, PF-01, and RP-01.
- **Purpose:** Demonstrate the complete platform with bounded nonbiological sweep,
  HRP-style, and MbCO-style blocks using the frozen configurations and evidence
  chain before biological method development.
- **Primary products:** Native full-system data, configuration/calibration links,
  startup/safe-stop/restoration records, agreement/uncertainty, and readiness.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`E2E-CH/plan.md`](instrument_readiness_001/phases/E2E-CH/plan.md).

### RPT-CH — characterization reporting and thesis reuse package

- **Status:** planned. **Prerequisites:** E2E-CH.
- **Purpose:** Aggregate characterization results and limitations into a complete
  reproducibility, claim-to-evidence, thesis, and biological-handoff package
  without reacquiring or replacing source measurements.
- **Primary products:** Validated indexes, source/geometry/spectral/temporal/noise/
  reproducibility summaries, uncertainties, figures, data dictionary, and audit.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`RPT-CH/plan.md`](instrument_readiness_001/phases/RPT-CH/plan.md).

### PROM-CH — characterization promotion gate

- **Status:** planned. **Prerequisites:** PROM-01 and RPT-CH.
- **Purpose:** Review and explicitly authorize the characterization bundle,
  supported claims, limitations, validity envelope, recharacterization triggers,
  and biological-entry criteria.
- **Primary products:** Proposed diff, approved or rejected bundle decision,
  validity envelope, triggers, retention/rollback plan, and downstream handoff.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`PROM-CH/plan.md`](instrument_readiness_001/phases/PROM-CH/plan.md).

### PB-01 — supplemental direct 355 nm OPO-drive characterization

- **Status:** optional. **Prerequisites:** PROM-CH.
- **Purpose:** Characterize the upstream 355 nm OPO drive as a non-gating thesis
  source study after core promotion; it does not define the biological 540 nm
  sample-path configuration.
- **Primary products:** High-energy detector qualification, 355 nm source-plane
  envelope and stability, derived quantities with limits, uncertainty, and safety.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`PB-01/plan.md`](instrument_readiness_001/phases/PB-01/plan.md).

## HRP biological campaign

### R0 — HRP requirements freeze

- **Status:** planned. **Prerequisites:** CH-00.
- **Purpose:** Freeze the HRP question, claims, observables, controls, parameter
  registry, owners, exclusions, and analysis logic before biological work.
- **Primary products:** Approved requirements/claim matrix, control plan,
  parameter registry, responsibility map, and unresolved-blocker disposition.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`R0/plan.md`](hrp_001/phases/R0/plan.md).

### R3 — HRP chemistry dry run

- **Status:** planned. **Prerequisites:** R0.
- **Purpose:** Practice approved buffer, reductant, CO, sealed-cell, state-record,
  and waste-handling procedures without consuming valuable protein.
- **Primary products:** EHS/training confirmation, preparation and handling logs,
  leak/state records, data-path check, waste-route verification, and deviations.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`R3/plan.md`](hrp_001/phases/R3/plan.md).

### R1 — HRP calibration completion

- **Status:** planned. **Prerequisites:** PROM-01.
- **Purpose:** Verify that the promoted calibration bundle and every required
  reference resolve and remain valid for the proposed HRP configurations.
- **Primary products:** Calibration-link and validity audit, imported configuration
  registry, unresolved-dependency disposition, and HRP calibration readiness.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`R1/plan.md`](hrp_001/phases/R1/plan.md).

### R2 — HRP characterization completion

- **Status:** planned. **Prerequisites:** PROM-CH.
- **Purpose:** Verify that the promoted characterization bundle, frozen CH-00
  settings, end-to-end demonstration, and repeatability envelope support HRP.
- **Primary products:** Characterization-link and validity audit, operating-envelope
  import, biological-entry assessment, and readiness disposition.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`R2/plan.md`](hrp_001/phases/R2/plan.md).

### R4 — HRP reference preparation

- **Status:** planned. **Prerequisites:** R1, R2, and R3.
- **Purpose:** Prepare sacrificial HRP-C(FeII)-CO reference material and verify its
  chemical state and stability before any pump exposure.
- **Primary products:** Preparation/batch record, UV-visible and FTIR verification,
  concentration/state/stability assessment, acceptance, and storage/disposition.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`R4/plan.md`](hrp_001/phases/R4/plan.md).

### R5 — HRP steady-state pilot

- **Status:** planned. **Prerequisites:** R4.
- **Purpose:** Establish dark and control spectra, both scan directions, target
  region support, signal quality, and beginning/end chemical-state stability.
- **Primary products:** Steady-state native data, controls, direction comparison,
  SNR/drift/saturation assessment, state checks, and pilot disposition.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`R5/plan.md`](hrp_001/phases/R5/plan.md).

### R6 — HRP exposure and recovery pilot

- **Status:** planned. **Prerequisites:** R5.
- **Purpose:** Identify a reversible 540 nm exposure regime and recovery cadence
  using the unchanged promoted iris configuration and the lowest justified dose.
- **Primary products:** Iris/power validity records, dose ladder, rare-pump recovery,
  reversibility/damage assessment, cadence, exposure ledger, and limits.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`R6/plan.md`](hrp_001/phases/R6/plan.md).

### R7 — HRP minimum viable acquisition

- **Status:** planned. **Prerequisites:** R6.
- **Purpose:** Execute the preregistered minimum HRP experiment across independent
  preparations with randomized/interleaved blocks and complete controls.
- **Primary products:** Native and derived datasets for at least three independent
  preparations, per-block QC, controls, uncertainty, and planned comparisons.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`R7/plan.md`](hrp_001/phases/R7/plan.md).

### R8 — optional HRP fast branch

- **Status:** optional. **Prerequisites:** R7, IR-01, and PF-01.
- **Purpose:** Attempt a faster HRP acquisition only if instrument response,
  sensitivity, exposure control, and the accepted MVP justify the extension.
- **Primary products:** Extension preregistration, fast data, IRF/SNR and exposure
  validation, comparison with core results, and bounded disposition.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`R8/plan.md`](hrp_001/phases/R8/plan.md).

### R9 — HRP analysis, closeout, restoration, and MbCO handoff

- **Status:** planned. **Prerequisites:** R7; R8 is optional.
- **Purpose:** Complete reproducible analysis and thesis products, reconcile
  exclusions/uncertainty, restore the instrument, audit retention/writeups, and
  decide whether an MbCO handoff is permitted.
- **Primary products:** Versioned analysis, final tables/figures and report,
  accepted writeups, restoration and retention audits, and signed handoff record.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`R9/plan.md`](hrp_001/phases/R9/plan.md).

## Optional cryogenic MbCO campaign

### QB-01M — cryogenic MbCO MIRcat probe and acquisition optimization

- **Status:** optional. **Prerequisites:** R9.
- **Purpose:** Qualify cryostat geometry, transmission, temperature/condensation,
  MIRcat pulse/rate/current behavior, detector response, and supported acquisition
  modes specifically for the optional cryogenic MbCO branch.
- **Primary products:** Cryogenic probe/acquisition envelope, pulse and thermal
  limits, detector/HF2LI applicability, timing/power stability, and mode choices.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`QB-01M/plan.md`](mbco_cryo_001/phases/QB-01M/plan.md).

### MB-00 — MbCO claims and dependency freeze

- **Status:** optional. **Prerequisites:** R9 and QB-01M.
- **Purpose:** Freeze the minimum and optional MbCO claims, species, observables,
  models, numeric evidence map, promoted imports, exclusions, and analysis tests.
- **Primary products:** Approved claim matrix, dependency register, observable/
  calibration map, analysis preregistration, and stop/narrowing rules.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`MB-00/plan.md`](mbco_cryo_001/phases/MB-00/plan.md).

### MB-01 — MbCO safety and procurement readiness

- **Status:** optional. **Prerequisites:** MB-00 and R9.
- **Purpose:** Verify HRP restoration and shared-platform validity, then establish
  CO safety, training, materials, sample/cell compatibility, procurement, waste,
  monitoring, emergency, and authorization readiness.
- **Primary products:** Safety/training records, SDS/manuals, procurement and
  identity table, compatibility assessment, emergency/waste plans, and decision.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`MB-01/plan.md`](mbco_cryo_001/phases/MB-01/plan.md).

### MB-02 — MbCO promoted platform imports

- **Status:** optional. **Prerequisites:** MB-01, PROM-01, PROM-CH, and QB-01M.
- **Purpose:** Import and verify every promoted wavelength, spectral, timing,
  detector, normalization, power, geometry, IRF, sensitivity, reproducibility,
  and acquisition dependency for the selected cryogenic configuration.
- **Primary products:** Calibration/characterization links, validity assessment,
  MbCO configuration registry, range verification, and readiness report.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`MB-02/plan.md`](mbco_cryo_001/phases/MB-02/plan.md).

### MB-03 — MbCO blank and cell qualification

- **Status:** optional. **Prerequisites:** MB-02.
- **Purpose:** Qualify the cryogenic cell and blank without protein, including
  assembly, path, leak/bubble behavior, temperature hold, transmission, fringes,
  forward/reverse scans, and pump/probe-only artifacts.
- **Primary products:** Cell/path and compatibility report, blank/background data,
  thermal/leak evidence, baseline/noise results, and acceptance limits.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`MB-03/plan.md`](mbco_cryo_001/phases/MB-03/plan.md).

### MB-04 — MbCO sample chemistry pilot

- **Status:** optional. **Prerequisites:** MB-03.
- **Purpose:** Prepare small independent MbCO batches and verify concentration,
  oxidation/ligation state, pH, stability, cell loading, and the steady A1 signal.
- **Primary products:** Preparation records, pre/post UV-visible and IR data,
  concentration/path uncertainty, stability window, and sample acceptance.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`MB-04/plan.md`](mbco_cryo_001/phases/MB-04/plan.md).

### MB-05 — MbCO pump dose and overlap pilot

- **Status:** optional. **Prerequisites:** MB-04.
- **Purpose:** Verify the unchanged promoted 540 nm configuration at the sample,
  then find the lowest useful, stable, nondamaging dose and overlap condition with
  complete blank, deoxy, no-pump, and integrity controls.
- **Primary products:** Iris/wavelength/configuration ledger, post-iris dose and
  overlap maps, artifact and integrity checks, damage ceiling, and selected dose.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`MB-05/plan.md`](mbco_cryo_001/phases/MB-05/plan.md).

### MB-06 — MbCO timing, IRF, and discovery kinetics

- **Status:** optional. **Prerequisites:** MB-05.
- **Purpose:** Verify time zero/IRF on a surrogate, acquire discovery kinetics over
  negative through recovery delays, and determine whether proposed kinetic
  components are identifiable at the measured SNR and response.
- **Primary products:** Time-zero/IRF links, discovery traces, identifiability
  simulation, selected delay/rate/filter design, recovery, and stop decision.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`MB-06/plan.md`](mbco_cryo_001/phases/MB-06/plan.md).

### MB-07 — MbCO confirmatory minimum viable experiment

- **Status:** optional. **Prerequisites:** MB-06.
- **Purpose:** Execute the independently frozen, randomized/counterbalanced MbCO
  MVP across preparations/days with full controls and post-integrity checks.
- **Primary products:** Native and derived datasets, fit diagnostics, uncertainty,
  predicted-versus-measured comparison, reproducibility, and minimum-claim decision.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`MB-07/plan.md`](mbco_cryo_001/phases/MB-07/plan.md).

### MB-08 — optional MbCO mechanistic extension

- **Status:** optional. **Prerequisites:** MB-07.
- **Purpose:** Extend an accepted MVP with denser geminate timing, additional bands,
  concentration dependence, or a separately qualified comparison only when IRF,
  SNR, sample, and model-identifiability gates support it.
- **Primary products:** Extension preregistration and data, model comparison,
  sensitivity analysis, validity assessment, and bounded conclusions.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`MB-08/plan.md`](mbco_cryo_001/phases/MB-08/plan.md).

### MB-09 — MbCO closeout, restoration, and retention

- **Status:** optional. **Prerequisites:** MB-07; MB-08 is optional.
- **Purpose:** Close the MbCO branch with safe restoration, reproducible analysis,
  complete exclusions and uncertainty, accepted procedural writeups, retention
  audit, thesis-ready provenance, and explicit result limitations.
- **Primary products:** Restoration report, final report/tables/figures, accepted
  writeups, exclusions and retention audits, provenance, and closeout decision.
- **Final Report:** Incomplete.
- **Procedural Writeup:** Incomplete.
- **Detailed plan:** [`MB-09/plan.md`](mbco_cryo_001/phases/MB-09/plan.md).
