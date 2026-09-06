# Instrument-readiness campaign requirements

Version: `2.1.0`
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

Root-level [`../../EXPERIMENTS.md`](../../EXPERIMENTS.md) is the source for the
experimental architectures and claims that this readiness campaign must support.
It does not silently override the authority order above, authorize hardware, or
freeze a setting. `CH-00.1` maintains the reviewed requirement allocation in
[`phases/CH-00.1/experiment_requirements_traceability.md`](phases/CH-00.1/experiment_requirements_traceability.md).

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

Every `status: complete` phase and its canonical package are immutable for this
alignment. A requirement that would have added work to such a phase is owned by a
registered supplemental phase immediately after it or by an already-planned phase
whose scope coherently covers the missing work. Completed status, dependencies,
plans, writeups, manifests, evidence, and scientific dispositions are not edited.
`WM-01` is incomplete and may be updated while preserving every retained entry,
preflight, failure, diagnostic, and deferral record.

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
  Sample feeds HF2LI Signal 1 In (+)/PicoScope CHA and reference feeds HF2LI
  Signal 2 In (+)/PicoScope CHB through separate adapter/tee networks. Both
  receivers remain connected; the MUX remains bypassed. Both T660 channel-D
  outputs and HF2LI DIO1 are unwired. MIRcat DB9 pins 5, 6, and 8 are unused
  and unwired. MS-02.1 qualifies the installed transfer and receiver conditions.
- T660-1 A supplies HF2LI DIO0, B supplies MIRcat TRIG IN, and C supplies
  T660-2 TRIG IN. T660-2 A/B/C supply FIRE/Q-switch/MIRcat Process Trigger.
  T660-2 CLOCK OUT distributes 10 MHz to T660-1 and HF2LI; it is separate
  from the T660-1 probe pulse train.

- Hardwired room and door interlocks remain external safety infrastructure. The
  repository does not substitute software for those interlocks.
- The retained OPO-540 path uses the ATT-01-qualified electronic iris. Applicable
  phases record its device/configuration ID, service or driver/API version,
  command, readback, qualified aperture and tolerance, and fault state. Loss of
  ownership, communication, or accepted readback blocks OPO emission. The iris is
  not a personnel-safety shutter or finite-exposure counter.
- Quantitative OPO-540 work imports the WM-01 replacement working-reference bundle
  and records device/interface/sampling-optic identity, wavelength medium/units,
  acquisition and calibration state, geometry, native time/value/status, quality
  state, stability classification, and uncertainty. Instrument-specific multi-line,
  saturation, low/no-signal, or invalid states are outcomes, not wavelengths. Center
  wavelength does not establish spectral-power fractions or absence of other
  wavelengths.
- A power meter is available; an energy meter is not. Do not claim measured
  pulse-energy distributions, pulse-to-pulse energy jitter, or calibrated peak
  power. Mean pulse energy may be derived from qualified average-power and
  repetition-rate evidence only when the derivation and limitation are explicit.
- Biological samples are not calibration standards. Sample preparation, CO
  handling, biological state, dose-response controls, and biological acquisition
  remain in their experiment campaigns.
- The HF2LI is the primary sample/reference spectral recorder. The PicoScope is an
  independently calibrated timing, pulse-shape, detector-response, branch-skew,
  saturation, overflow, and trigger diagnostic; it does not replace the HF2LI.
- Normal sweep acquisition retains both detector split paths and observes
  MIRcat DB9 pin 2 Sweep Active concurrently on HF2LI DIO21 and PicoScope EXT.
  Qualify the high-impedance branch and ground return; neither D output is a
  process marker. DIO1 is not an acquisition gate in the default configuration.

- In that Phase-Scan configuration PicoScope CHA is the sample-detector witness and
  CHB is the reference-detector primary optical-pulse witness. A pulse opportunity is
  classified as a MIRcat optical omission only when it is absent from both channels;
  a one-channel-only observation is retained separately as a detector/path
  discrepancy. Neither optical channel is the timing authority.
- Normal dual-detector acquisition and the sample-detector/pump-detector timing/IRF
  topology are separate configuration families. A correction may cross between
  them only through an accepted bridge with reference planes and uncertainty.
  Temporary timing/IRF work uses PicoScope CHA for the sample IR detector and
  CHB for the pump detector, records any disconnected detector branch and changed
  loading, and restores both default detector split paths afterward.
- The MIRcat probe carrier rate is independent of the 10 Hz pump limit. Low-rate
  and high-rate probe candidates require separate measured source, reference-lock,
  detector, heating, synchronization, and stream-validity envelopes.

## 6. Measurement-system and timing requirements

### 6.1 Time origins and rates

Each timing result names its source and destination event, electrical or optical
reference plane, threshold/crossing definition, sign convention, sampling rate,
and configuration ID. Completed timing evidence retains its actually used rates and
programmed delays as immutable provenance. A future phase selects its rate and delay
grid only from accepted device limits, the measured response/uncertainty, and the
frozen precision/resolution requirement; completed values are not automatic defaults.

Chemical time zero is the optically observed pump arrival at the sample plane.
Command edges, programmed delays, and cable lengths are diagnostic/provenance
quantities and are never relabeled as chemical time zero. Physical cable-length
equality is not a timing calibration.

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
qualifies installed detector latency. OP-01 measures independently observed pump and
probe arrival at the sample-equivalent plane, FE-01 qualifies finite emitted-event
admission and reconciliation, and CL-01 performs covariance-aware closure across every
retained slow-scan and reconstruction configuration. Closure must retain every component identity and configuration
foreign key and may not hide an incompatible time origin or failed loop.

### 6.3 Train/frame scheduling, sweep alignment, and pulse opportunities

T660-1 supplies the probe/reference pulse train: channel A feeds HF2LI DIO0,
channel B feeds MIRcat TRIG IN, and channel C feeds T660-2 TRIG IN. T660-2
uses its train/frame engine for the event schedule: channel A drives Surelite
FIRE, B drives Q-switch, and C drives MIRcat DB9 pin 4 Process Trigger. Both
channel-D outputs are disabled and unwired; HF2LI DIO1 is unwired. MIRcat DB9
pin 2 Sweep Active feeds HF2LI DIO21 and PicoScope EXT through the qualified
high-impedance branch; pin 1 direction feeds DIO20 and pin 3 wavelength markers
feed DIO22. Connector pin numbers and captured DIO bit indices are distinct.
T660-2 CLOCK OUT supplies the 10 MHz clock distribution to T660-1 CLOCK IN and
HF2LI CLOCK IN. This frequency-reference distribution is separate from the
T660-1 probe pulse train.

A finite run preloads the complete bounded T660-2 frame table while outputs
are disabled. Per-frame channel OFF states suppress unrequested outputs,
including pump outputs in unpumped baselines; terminal padding has all outputs
OFF. Train count zero disables additional pulses, not the first pulse of an
enabled channel. Train count and spacing are shared by enabled channels within
each frame. The frame predivider, frame repetition, train count/spacing,
channel enables/delays/widths/polarities, terminal padding, and physical frame
count are recorded and checked against readback before arming. Acquisition
is ready before the event sequence starts; software polling does not schedule
pump/probe/scan edges. Frames and train counts schedule electrical commands;
independent optical observation establishes emitted pump counts and sample time
zero. Each experiment freezes its own cadence, recovery interval, and data budget;
the Phase Scan 0.3 s frame period is not a default for other experiment types.

MS-02.1 qualifies the direct Sweep Active-to-PicoScope EXT branch, loading,
threshold, edge, and latency. MD-01 reconciles each T660-2 C process command
with MIRcat state transitions and complete HF2LI DIO records. MSW-01 measures
process-command-to-observed-scan timing and actual wavenumber/time trajectory;
HF-02 establishes the synchronized Sample/Reference/Sweep Active/pump-event
recording envelope. Scope and HF2LI observe the same source signal, but their
receiver and clock delays still require calibration.

Finite Phase Scan uses bounded Sweep-Active-triggered LabOne histories and a
separate synchronized pump-event record, retaining consolidated native records.
PicoScope pulse diagnostics qualify the acquisition envelope; a dedicated scope
record and automatic replacement scan are not required for every physical scan.
Expected probe opportunities use the configured and read-back T660-1 rate.
Where pulse diagnostics are acquired, local detector thresholds distinguish
absence in both channels from a one-channel detector/path discrepancy. Retain
partial, missing, clipped, or unclassifiable records and reject unsupported
scientific regions. Ordinary reconstruction does not fill gaps by retry/merge
or remove detector etalons algorithmically.

## 7. Required measurement coverage by phase

The following table defines the minimum cross-phase intent and retained products.
Each phase plan supplies the complete step sequence, grid, stop rules, and
acceptance thresholds.

| Phase or phase family | Required question and minimum retained products |
| --- | --- |
| P0, S0 | Establish inventory/provenance and safe-idle/interlock behavior; retain identities, topology, observations, and restoration evidence. |
| MS-01, MS-02 | Quantify oscilloscope channel/path and splitter-branch timing corrections, sensitivity, covariance, and validity. |
| MS-02.1 | Without changing or reacquiring MS-01/MS-02, calibrate the installed detector-output tee/adapter/cable networks to the HF2LI and PicoScope, including loading, attenuation, reflection/ringing, bandwidth, skew, PicoScope timebase/amplitude/bandwidth/trigger behavior, overflow, uncertainty, and topology-specific validity; separately qualify the MIRcat Sweep Active-to-PicoScope-EXT electrical trigger route used by Phase Scan. |
| T2-01, T1-01, PT-01, MC-01 | Qualify the direct timer routes, MIRcat Process Trigger electrical route, and GUI/process-trigger state semantics with native traces and command/readback records. |
| TR-01, OM-01 | Close identity/resource gaps and qualify only the metrology resources, adapters, references, limits, and transfer standards required by the campaign. |
| CH-00 | Freeze the minimum claim grid and imported calibration dependencies for Mylar, HRP-C–CO, and MbCO work; exclude optional scope from core gates. |
| CH-00.1 | Reconcile every `EXPERIMENTS.md` calibration, characterization, optimization, validation, initial-slow-scan, architecture, and claim prerequisite with the sequence; maintain the canonical traceability and unresolved-gap register without assigning new work to completed phases. |
| HF-01, HF-01.1, HF-02 | Import immutable HF-01 evidence and qualify experiment-specific low/high-rate HF2LI reference topologies, demodulator/filter/order/time-constant/phase/range/output-rate tradeoffs, timestamps, settling/filter memory, cross-stream alignment, loss/relock, and endurance. Retain distinct IDs for every acquisition architecture even when numerical settings coincide. |
| WM-01 | Resume the incomplete phase with a suitable replacement spectrometer and qualify its installed identity, communications, native status semantics, pulsed/CW applicability, 540 nm repeatability/stability, uncertainty, validity, and exclusions. Preserve the failed WaveMaster evidence; no center-wavelength instrument assigns residual spectral-power fractions. |
| MD-01, MSW-01 | Qualify MIRcat/HF2LI DIO mapping, the installed process-trigger receiver interval, one-command/one-transition behavior, T660-2 C/frame/Sweep-Active semantics, `Tuned` reliability, the configuration-specific cross-recorder Sweep Active offset and uncertainty, discrete optical settling and history, failure response, and actual scan trajectory versus speed, direction, window, start, acceleration/turnaround, and module transition. |
| DET-01 | Measure dark detector/electronics offsets, noise, 1/f/drift/Allan behavior, cross-talk, range, saturation/recovery baselines, temperature sensitivity, and stability over the retained normal dual-recorder configurations. |
| SP-01 | Freeze reference-material identities, feature authorities, uncertainties, and partition rules before spectral fitting. |
| ATT-01 | Qualify the electronic iris control/readback and faults; lock the far-field mount; perform the preliminary bidirectional OPO-540 delay search; measure attenuation, splitter-port, and sample-plane transfer; preserve wavelength and clipping controls. |
| DET-02 | Measure illuminated sample/reference detector/electronics gain, linearity, noise, saturation and recovery versus signal/wavelength, including the installed simultaneous HF2LI/PicoScope loading configuration, with raw meter/detector/HF2LI/PicoScope/interchange records and fit residuals. |
| DET-03 | Measure separate sample- and reference-path impulse/step response, bandwidth, latency, wavelength/signal dependence, pump-scatter recovery, and configuration-specific composition with MS-02.1 and HF-01 transfer functions. |
| DET-04 | Separate optical split balance from detector/electronics balance and produce wavelength-dependent normalization, covariance, common-mode rejection, residual baseline, and uncertainty. |
| QB-01 | Characterize MIRcat output versus wavenumber, current, pulse width, repetition rate, and duty cycle across all retained regions and low/high-rate candidates; measure pulse/timing/linewidth/stability/thermal behavior, dual-detector optical omissions and detector/path discrepancies, tune/process behavior, scan dynamics, and sample-heating bounds. |
| PB-02 | Qualify the final post-iris OPO-540 output and final narrow FIRE-to-Q-SWITCH delay using bidirectional searches, a confirmation revisit, three return-to-540 visits, and low/high planned power conditions. |
| SC-01 | Qualify room-temperature and nominal-77 K cell/stage/cryostat configurations: path, blank/matrix/window/fringe/placement, sensor calibration, sample gradient, equilibration, transmission, focus/beam shift, condensation/icing/purge, heating, thermal cycling, and mechanical stability without protein or CO. |
| OG-01, OV-01 | Measure pump/probe sample-plane transfer, beam profiles, centroids, pointing, illuminated geometry, placement, and overlap at room-temperature and cryogenic sample-equivalent planes. Do not tune the iris to obtain a desired response. |
| AR-01 | Jointly optimize and validate slow-scan, fixed-wavelength nanosecond/microsecond, repeated rapid-scan, single-scan phase-delay, and single-pump scan-burst acquisition candidates; retain settling, filter memory, scan distortion, native pulse coverage, one-pass coverage and frame-capacity rules, covariance, and bounded-escalation results. |
| PF-00 | Before reference-standard acquisition, establish normalized noise, common-mode rejection, drift, saturation margin, and SNR on blank or stable nonbiological inputs. |
| SP-02, SV-01 | Calibrate the spectral axis over the Mylar/polystyrene carbonyl window and 1885–1980 cm⁻¹ region; acquire specimen-matched FTIR reference sets for polystyrene and Mylar. |
| SV-02A, SV-02B | Fit/freeze corrections with a predeclared polystyrene partition and holdout, then perform blind Mylar validation with three accepted scans per direction and no post-unblinding refit. |
| OP-01, FE-01, CL-01 | Qualify independently observed post-iris OPO-540 pump and MIRcat probe arrival at the sample-equivalent plane, finite-event count and stop/fault behavior, and complete timing closure for every retained architecture/configuration. |
| IR-01 | Measure complete sample-plane IRFs for every retained architecture/configuration, combining pump/probe optical envelopes, jitter, sample/reference detector responses, branch latency, PicoScope aperture/trigger uncertainty, HF2LI acquisition kernels, and scan history with synchronized native streams and uncertainty. |
| PF-01 | Measure sensitivity, detector/pump/cell artifacts, pump-scatter recovery, drift, common-mode residual, SNR, NEA/MDA where supportable, averaging validity, probe/pump heating, and saturation margin for all retained room-temperature and cryogenic surrogate configurations. |
| RP-01 | Repeat compact checkpoints across startups, placements/reinstallations, and independent days for each materially distinct retained configuration, retaining configuration, wavelength, iris, cryostat/cell, environment, restoration, variance, and recharacterization evidence. |
| E2E-01, E2E-CH | Demonstrate bounded normal-wiring nonbiological workflows and validate nanosecond and microsecond stroboscopy, repeated rapid-scan phase-delay, single-scan phase-delay, and single-pump rapid-scan/logarithmic scan-burst reconstruction. Publish native `(wavenumber,time)` and optical-pulse coverage, attempt/bin provenance, one-pass reconstruction behavior, finite-block interruption, interpolation support, bias, filter memory, direction, deficient-output labeling, identifiable regions, uncertainty, mismatch stops, and restoration. |
| RPT-01, RPT-CH | Aggregate indexed evidence, thesis tables/figures, uncertainty budgets, claim-to-evidence links, configuration/validity envelopes, and experiment handoff records without altering source evidence. |
| PROM-01, PROM-CH | Review an exact candidate bundle, unresolved limitations, validity/revalidation rules, and retention plan; promotion requires the plan's explicit authorization phrase. |
| PB-01 | After core promotion, optionally characterize direct 355 nm drive for supplemental thesis evidence. It does not satisfy or block any core gate and cannot inherit the 540 nm meter/iris qualification. |

### 7.1 Experimental architecture and configuration families

The campaign supplies separate configuration IDs and validity envelopes for:

1. slow steady-state scanning at room temperature and 77 K;
2. nanosecond wavelength-by-wavelength stroboscopy;
3. microsecond wavelength-by-wavelength stroboscopy;
4. repeated rapid-scan phase-delay reconstruction;
5. single-scan phase-delay reconstruction;
6. single-pump rapid-scan and logarithmic scan-burst reconstruction;
7. normal dual-detector HF2LI-primary acquisition with PicoScope diagnostics; and
8. sample-detector/pump-detector sample-plane timing and IRF acquisition; and
9. normal dual-detector finite Phase-Scan acquisition with Sweep Active on PicoScope
   EXT and HF2LI DIO21, plus a separately synchronized pump-event record.

Room-temperature HRP–CO, room-temperature MbCO, 77 K HRP–CO, and 77 K MbCO each
require an accepted condition-specific initial slow scan before time-resolved work.
Readiness phases provide the axis, scan/tune, detector, normalization, path,
temperature, and sensitivity prerequisites. The experimental scan determines the
actual centers, widths, areas, baselines, interference, and local windows; literature
positions never become final setpoints.

### 7.2 Phase-plan completeness for `EXPERIMENTS.md` allocations

Every affected incomplete phase plan must state or inherit without ambiguity:

- why the phase is required and which traceability IDs it owns;
- measured quantities, reference planes, and configuration identities;
- native evidence, retained failures/exclusions, and analysis/uncertainty outputs;
- prospective acceptance, rejection, stop, and fallback logic;
- validity envelope and revalidation triggers;
- downstream architecture/claim consumers; and
- what the phase explicitly does not establish.

Plans must not assign final pulse width, repetition rate, scan speed, spectral or
phase increment, window, delay grid, filter, output rate, detector range, averaging,
pump cadence/dose, recovery interval, or cryogenic equilibration time. A numeric
illustration remains non-operational only when labeled `EXAMPLE ONLY`.

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
