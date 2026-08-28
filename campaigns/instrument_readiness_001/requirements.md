# Instrument-readiness campaign requirements

Version: `2.0.0`
Status: **AUTHORITATIVE CROSS-PHASE REQUIREMENTS**

## 1. Purpose and authority

This document defines the requirements shared by the calibration,
characterization, independent-validation, reporting, and promotion phases of
`instrument-readiness-001`. It is used together with:

1. [`../master_sequence.md`](../master_sequence.md), the authoritative human
   instructions and dependency-ordered phase catalog;
2. [`../phase_registry.yaml`](../phase_registry.yaml), the machine-readable
   phase, status, dependency, and evidence-key registry;
3. `phases/<phase-id>/plan.md`, the authoritative phase-specific procedure,
   acceptance logic, and deliverables; and
4. [`../../docs/phase_record_contract.md`](../../docs/phase_record_contract.md),
   the evidence and thesis-quality procedural-writeup contract.

If two active records disagree, stop before execution and reconcile them in that
order of authority. A phase directory is the sole active home for its plan and
all evidence produced by the phase. Calibration and characterization are
scientific domains in the registry, not separate execution trees.

## 2. Authorization and session boundaries

Planning, review, documentation, and software development do not authorize a
hardware action or scientific acquisition. Before execution, identify the exact
phase, verify its required dependencies, read its complete plan, confirm the
evidence destination, and obtain the authorization required by that plan.

During an operator-guided session:

1. Establish and record the initial instrument, wiring, optical, software, and
   environmental state.
2. Present one physical action at a time and wait for the operator's actual
   observation or readback. Never infer that an action occurred.
3. Record commands, settings, observations, decisions, deviations, and files as
   they are produced.
4. Use `USER_INPUT_REQUIRED` for an identity, observation, confirmation, or
   judgment that only the operator can provide.
5. Stop on an interlock, unexpected emission or motion, unsafe state, ownership
   conflict, missing required input, or plan-defined stop condition.
6. Restore and document the required safe or baseline state.
7. Stop at the authorized phase boundary. Completion never authorizes the next
   phase or a promotion decision.

## 3. Entry review

Before a phase begins, its run record must resolve or explicitly defer:

- required and optional dependencies and the imported result or bundle IDs;
- the validity envelope and revalidation triggers of every imported result;
- device identities, firmware, drivers, SDKs, software, recipes, schemas,
  analysis versions, and configuration IDs;
- wiring, optical topology, reference planes, grounding, channel roles, ranges,
  rates, time origins, signs, and units;
- warm-up, stabilization, purge, sample, exposure, and metrology conditions;
- predeclared acceptance criteria, exclusions, stop rules, replication,
  uncertainty treatment, and decision logic;
- required raw, processed, figure, table, report, restoration, and writeup
  products; and
- the initial state and the required restored state.

Do not repeat an accepted measurement grid when its retained result covers the
needed configuration and validity envelope. Import it by stable ID. When coverage
is insufficient, document the gap and obtain separate authorization for a bounded
new measurement.

## 4. Common evidence and completion requirements

Every phase follows the phase-record contract. Retain or index, as applicable:

- phase/run manifests, artifact and acquisition indexes, source and producer
  records, configuration snapshots, readbacks, command/operator logs, and
  environment records;
- raw/native acquisitions without undocumented conversion or overwriting;
- processed tables, analysis inputs and outputs, code and parameter versions,
  exclusions, diagnostics, uncertainty records, figures, and tables;
- controls and any rejected, failed, aborted, stopped, or bypassed attempts that
  affect interpretation;
- deviations, troubleshooting, approvals, photographs, topology records,
  restoration evidence, and unresolved-input records;
- `final_report.md`, with criterion-by-criterion disposition and downstream
  authorization; and
- `procedural_writeup.md`, with thesis-level WHY, HOW, WHAT, and supported claims,
  implications, caveats, and limitations.

Completed evidence is not reacquired merely to satisfy a newer document format.
Prepare a missing writeup from the retained evidence, identify unknown details,
and narrow claims accordingly. Documentation state and scientific disposition are
separate fields in the phase registry.

Use stable IDs, relative paths, byte sizes, UTC timestamps, explicit versions,
device/configuration identities, source records, and branch or commit context for
provenance. Checksums may be diagnostic information, but repository-authored hash
matching must not be the sole gate for loading, analysis, aggregation,
reproduction, acceptance, closeout, or promotion.

## 5. Standing installed-system constraints

- The default wiring state is defined by
  [`../../instrument/default_wiring_state.md`](../../instrument/default_wiring_state.md).
  “Default wiring restored” means T660-1 CHD and MIRcat DB9 pin 5 are
  disconnected; MIRcat DB9 pins 6 and 8 are unused and unwired unless the
  operator records a changed installed state.
- Hardwired room and door interlocks remain external safety infrastructure. The
  repository does not substitute software for those interlocks.
- The retained OPO-540 path uses the ATT-01-qualified electronic iris. Applicable
  phases record its device/configuration ID, service or driver/API version,
  command, readback, qualified aperture and tolerance, and fault state. Loss of
  ownership, communication, or accepted readback blocks OPO emission. The iris is
  not a personnel-safety shutter or finite-exposure counter.
- Quantitative OPO-540 work imports the WM-01 working-reference bundle and records
  meter, adapter, probe, unit, pulse/CW mode, autocalibration state, geometry,
  native time/value/status, quality state, stability classification, and
  uncertainty. `Multi-Line`, `Saturated`, and `No Signal` are outcomes, not
  wavelengths. Center wavelength does not establish spectral-power fractions or
  absence of other wavelengths.
- A power meter is available; an energy meter is not. Do not claim measured
  pulse-energy distributions, pulse-to-pulse energy jitter, or calibrated peak
  power. Mean pulse energy may be derived from qualified average-power and
  repetition-rate evidence only when the derivation and limitation are explicit.
- Biological samples are not calibration standards. Sample preparation, CO
  handling, biological state, dose-response controls, and biological acquisition
  remain in their experiment campaigns.

## 6. Measurement-system and timing requirements

### 6.1 Time origins and rates

Each timing result names its source and destination event, electrical or optical
reference plane, threshold/crossing definition, sign convention, sampling rate,
and configuration ID. Use 100 Hz for direct T660-2 electrical routes. Use 10 Hz
for T660-1 routes and optical work unless the phase plan explicitly qualifies a
different rate. The standard programmed delay grid is
`[0, 100, 1000, 10000, 100000, 1000000] ns`; a phase may use a smaller declared
subset only when its plan explains why.

Make wiring and range changes only from a safe, non-emitting state. Record the
pre-change topology, the exact change, a post-change verification, and the
restored state. Never connect a signal until its expected range and common-ground
relationship are established.

### 6.2 Corrections and uncertainty

MS-01 supplies PicoScope channel/path-skew corrections and MS-02 supplies splitter
branch skew plus measurement-system sensitivity. Downstream timing phases import
those products by stable ID and propagate their covariance; they do not measure
the same correction again. Retain native traces and per-shot results, apply
predeclared threshold or fit methods, report accepted and excluded populations,
fit delay/offset/slope or residual models as specified by the phase plan, and
include repeatability, timebase, threshold, cable, splitter, adapter, detector,
and configuration terms in the uncertainty budget.

T2-01 and T1-01 qualify direct trigger/output routes. PT-01 and MC-01 qualify
MIRcat Process Trigger electrical behavior and GUI state semantics. DET-03
qualifies installed detector latency. OP-01 measures command-to-sample optical
timing, FE-01 qualifies finite emitted-event admission and reconciliation, and
CL-01 performs covariance-aware closure across the retained sweep, HRP, and MbCO
configurations. Closure must retain every component identity and configuration
foreign key and may not hide an incompatible time origin or failed loop.

## 7. Required measurement coverage by phase

The following table defines the minimum cross-phase intent and retained products.
Each phase plan supplies the complete step sequence, grid, stop rules, and
acceptance thresholds.

| Phase or phase family | Required question and minimum retained products |
| --- | --- |
| P0, S0 | Establish inventory/provenance and safe-idle/interlock behavior; retain identities, topology, observations, and restoration evidence. |
| MS-01, MS-02 | Quantify oscilloscope channel/path and splitter-branch timing corrections, sensitivity, covariance, and validity. |
| T2-01, T1-01, PT-01, MC-01 | Qualify the direct timer routes, MIRcat Process Trigger electrical route, and GUI/process-trigger state semantics with native traces and command/readback records. |
| TR-01, OM-01 | Close identity/resource gaps and qualify only the metrology resources, adapters, references, limits, and transfer standards required by the campaign. |
| CH-00 | Freeze the minimum claim grid and imported calibration dependencies for Mylar, HRP-C–CO, and MbCO work; exclude optional scope from core gates. |
| HF-01, HF-01.1, HF-02 | Qualify HF2LI external-reference, acquisition, candidate experiment settings, cross-stream alignment, loss/recovery, filter memory, and endurance. Retain distinct sweep, HRP, and MbCO configuration IDs. |
| WM-01 | Qualify installed visible/near-IR wavelength metrology, including identity, communications, state semantics, 540 nm repeatability, stability, uncertainty, and validity. Completion requires a qualified replacement spectrometer. |
| MD-01, MSW-01 | Qualify MIRcat/HF2LI DIO mapping and sweep timing with direction, rate, trigger, state, and error records. |
| DET-01 | Measure dark detector/electronics offsets, noise, drift, range, saturation, and stability over the retained configurations. |
| SP-01 | Freeze reference-material identities, feature authorities, uncertainties, and partition rules before spectral fitting. |
| ATT-01 | Qualify the electronic iris control/readback and faults; lock the far-field mount; perform the preliminary bidirectional OPO-540 delay search; measure attenuation, splitter-port, and sample-plane transfer; preserve wavelength and clipping controls. |
| DET-02 | Measure illuminated detector/electronics response at the retained anchors and endpoints, with raw meter/detector/HF2LI/interchange records and fit residuals. |
| DET-03 | Measure installed detector temporal response and configuration-specific composition with HF-01 transfer functions. |
| DET-04 | Separate optical split balance from detector/electronics balance and produce wavelength-dependent normalization with covariance. |
| QB-01 | Qualify only the Mylar window and merged 1885–1980 cm⁻¹ probe anchors, including one retained sweep and one fixed-point envelope. |
| PB-02 | Qualify the final post-iris OPO-540 output and final narrow FIRE-to-Q-SWITCH delay using bidirectional searches, a confirmation revisit, three return-to-540 visits, and low/high planned power conditions. |
| SC-01 | Qualify the minimum gas-tight CaF2 cell set and 293 K/298 K states using blank, leak, transmission, reassembly, and temperature evidence without biological material or CO. |
| OG-01, OV-01 | Measure sample-plane transfer, beam profiles, fluence inputs, placement, and overlap for Mylar and the fixed-iris OPO-540 path at HRP and MbCO geometries. Do not tune the iris to obtain a desired response. |
| AR-01 | Jointly validate the selected sweep, HRP fixed-point, and MbCO fixed-point configurations optically; retain settling, filter-memory, peak-shift/broadening, covariance, and bounded-escalation results without repeating HF-01 mapping. |
| PF-00 | Before reference-standard acquisition, establish normalized noise, common-mode rejection, drift, saturation margin, and SNR on blank or stable nonbiological inputs. |
| SP-02, SV-01 | Calibrate the spectral axis over the Mylar/polystyrene carbonyl window and 1885–1980 cm⁻¹ region; acquire specimen-matched FTIR reference sets for polystyrene and Mylar. |
| SV-02A, SV-02B | Fit/freeze corrections with a predeclared polystyrene partition and holdout, then perform blind Mylar validation with three accepted scans per direction and no post-unblinding refit. |
| OP-01, FE-01, CL-01 | Qualify post-iris OPO-540 command-to-sample timing, finite-event count and stop/fault behavior, and complete timing closure for sweep, HRP, and MbCO configurations. |
| IR-01 | Measure temporal instrument response for fixed-iris OPO-540 at both HRP bands and MbCO A1 with synchronized native streams, controls, configuration-specific bias/width/residual, and uncertainty. |
| PF-01 | Measure sensitivity, artifacts, drift, common-mode residual, SNR, NEA/MDA where supportable, and averaging validity for Mylar, both HRP bands, MbCO A1, and one shared off-band condition. |
| RP-01 | Repeat compact Mylar, OPO-540-HRP, and OPO-540-MbCO checkpoints on three independent days, retaining configuration, wavelength, iris, mount, environment, restoration, variance, and recharacterization evidence. |
| E2E-01, E2E-CH | Demonstrate bounded normal-wiring nonbiological workflows with all native streams, axes, controls, event ledgers, mismatch stops, iris/wavelength state, processing, uncertainty, and restoration. |
| RPT-01, RPT-CH | Aggregate indexed evidence, thesis tables/figures, uncertainty budgets, claim-to-evidence links, configuration/validity envelopes, and experiment handoff records without altering source evidence. |
| PROM-01, PROM-CH | Review an exact candidate bundle, unresolved limitations, validity/revalidation rules, and retention plan; promotion requires the plan's explicit authorization phrase. |
| PB-01 | After core promotion, optionally characterize direct 355 nm drive for supplemental thesis evidence. It does not satisfy or block any core gate and cannot inherit the 540 nm meter/iris qualification. |

## 8. Acceptance, restoration, promotion, and handoff

Close a phase only after evaluating every plan-specific and common criterion
against retained evidence. Record pass, fail, conditional, bypassed, stopped, or
incomplete outcomes explicitly. A failed control, exclusion, unmet criterion, or
unresolved dependency remains visible.

Phase closure does not alter control-software defaults. Promotion is a separate
registered phase. PROM-01 requires `APPROVE CALIBRATION PROMOTION`; PROM-CH
requires `APPROVE CHARACTERIZATION PROMOTION`. The application consumes only
promoted bundles under `instrument/promoted_bundles/`, while campaign evidence
and narratives retain how each input was established.

Characterization may be planned in parallel, but emitting or quantitative work
waits for its calibration dependencies or a plan-declared, bounded provisional
input. A discovered calibration defect opens a separately authorized suffixed
investigation; it is not repaired inside characterization evidence.

Biological campaigns import promoted bundle IDs and remain within their validity
envelopes. They retain separate sample, preparation, control, exposure, and
response evidence. HRP-C–CO precedes MbCO. A different OPO wavelength cannot
inherit the OPO-540 iris or wavelength qualification.
