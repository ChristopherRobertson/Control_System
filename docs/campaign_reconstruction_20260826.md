# Prospective instrument-readiness and experiment campaign reconstruction

Status: **AUTHORITATIVE PROSPECTIVE DEPENDENCY CROSSWALK; NO HARDWARE EXECUTION AUTHORIZED**  
Effective: 2026-08-26  
Scope: future calibration, characterization, HRP, and optional cryogenic MbCO work

This amendment changes future dependencies and methods, not history. Completed phase
records, decisions, identifiers, raw evidence, rejected attempts, exclusions, and
restoration records remain authoritative in place. A completed result can remain
historically valid while having a bounded current applicability or being superseded
for future use. Only a documented physical change that affects a measured quantity
opens a targeted revalidation phase; plan edits never do so.

## Material firewall and staged promotion

The immutable material order is:

`polystyrene calibration/alignment partition -> polystyrene holdout -> blind Mylar validation -> HRP -> optional cryogenic MbCO`

Polystyrene alone fits the spectral correction. Before any Mylar data are opened,
SV-02A freezes the correction and covariance, validity range, scan mode/direction,
scan speed, HF2LI configuration, detector normalization, baseline and fitting
methods, feature windows, tolerances, and software/analysis versions. The declared
polystyrene holdout tests the frozen result without refitting. SV-02B then applies it
blindly to specimen-matched Mylar FTIR comparisons in both directions. Mylar may not
tune any method or threshold. Failure opens a cause-coded investigation or narrows
the claim; it never automatically refits the correction.

The core promotion bundle ends with HRP closeout and verified restoration. Optional
MbCO gates are a separate staged bundle and cannot block polystyrene, Mylar, or HRP.
Biological observations never calibrate the instrument.

## Dependency-ordered phase list

Existing IDs retain their historical identity and status. This list expresses the
effective future dependency order, not a renumbering.

1. **Preserved baseline:** P0, S0, MS-01, MS-02, T2-01, T1-01, PT-01, MC-01,
   TR-01, OM-01, HF-01, and CH-00 are imported at their recorded status. WM-01
   resumes its existing run; it is not recreated.
2. **HF-01.1:** experiment-specific HF2LI candidate optimization and targeted
   electrical confirmation.
3. **Remaining electrical/source prerequisites:** WM-01 as applicable, MD-01,
   MSW-01, HF-02, DET-01, DET-02, DET-03, DET-04, SP-01, plus ATT-01/QB-01 inputs
   whose dependencies are available.
4. **Installed optical readiness:** SC-01, OG-01, OV-01, PB-02, and applicable
   source/temperature/blank-transfer work. PB-01 remains supplemental.
5. **AR-01:** joint scan-speed/HF2LI acquisition optimization and optical
   validation on a stable nonbiological target.
6. **PF-00:** pre-standard normalized noise/SNR readiness gate using a blank,
   stable nonbiological signal, or qualified transfer condition; never Mylar.
7. **SP-02 and SV-01 prerequisites, then SV-02A:** polystyrene calibration,
   holdout test, correction freeze, and formal Mylar unlock.
8. **SV-02B:** blind independent Mylar validation.
9. **Core completion:** OP-01, FE-01, CL-01, IR-01, PF-01, RP-01, E2E-01,
   E2E-CH, RPT-01, RPT-CH, PROM-01, and PROM-CH as required by the HRP validity
   envelope. Dependencies permit already completed inputs to be imported once.
10. **HRP:** HRP R0-R9, including accepted closeout, verified restoration, and an
    explicit `HANDOFF-HRP-MBCO` record.
11. **Optional MbCO gate:** QB-01M and cryostat-specific targeted qualification.
12. **Optional MbCO extension:** MbCO-specific AR, IRF, sensitivity, end-to-end,
    reporting, and promotion extensions.
13. **Optional MbCO biology:** MB-01-MB-09 only if readiness and time permit.

## Completed-evidence reuse and supersession

| Completed evidence | Historical validity | Prospective reuse |
|---|---|---|
| P0/S0 | unchanged | provenance, identity, safe-state baseline |
| MS-01/MS-02 | unchanged | channel/path and splitter timing corrections; no wholesale repeat |
| T2-01/T1-01 | unchanged | T660 route timing and uncertainty inputs |
| PT-01/MC-01 | unchanged | MIRcat process-trigger electrical and GUI behavior |
| TR-01 | unchanged | resource identity, provenance, and uncertainty basis |
| OM-01 | unchanged and bounded | retained optical-metrology and transfer anchors within recorded envelope |
| HF-01 | PASS unchanged | three electrical anchors; validated filter/transfer model; supported-space readback; external-reference/timing; Input 1/Input 2 equivalence; range, clipping, loss, reload, restoration, and uncertainty evidence |
| CH-00 | PASS unchanged | claims, exclusions, registries, and scope baseline |

HF-01's shared sweep/HRP numerical selection remains a valid historical,
provisional electrical selection under its original configuration IDs. HF-01.1 may
issue new configuration IDs and a `supersedes_for_future_use`, `equivalent_setting`,
or `not_equivalent_requirement` relationship. Such records never modify HF-01's
decision. The retained finding that HF2LI cannot resolve the original approximately
1 us uncooled MbCO requirement remains in force.

Each future phase shall provide a completed-evidence reuse matrix with source
campaign ID, phase ID/run ID, acquisition/artifact/configuration ID, relative path,
role, validity envelope, and disposition. Evidence is linked, never copied and
represented as a new acquisition. Rejected, diagnostic, preview, partial,
superseded, and excluded rows remain indexed and retain their states.

## HF-01.1 requirements

The detailed procedure is `calibration/system_recalibration_001/plans/hf01_1_experiment_specific_optimization.md`.
It imports the HF-01 model and complete supported space and freezes separate
requirements for continuous scanning, HRP fixed wavelength, HRP phase-shifted
stroboscopy, cryogenic MbCO fixed wavelength, and cryogenic MbCO phase-shifted
stroboscopy. Wavelength-by-wavelength reconstruction uses the applicable
fixed-wavelength numerical envelope but retains a distinct experiment-mode identity.

All supported settings are evaluated deterministically. Detector noise, signal
range, duration, distortion tolerance, and temporal resolution are explicit inputs.
Missing detector/optical/cryostat inputs make a candidate provisional. Separate
Pareto frontiers and shortlists are produced for each mode. Only the eventual winner
and nearest meaningful Pareto challenger for each distinct numerical configuration
receive targeted physical confirmation, unless existing HF-01 evidence already
supports that exact confirmation and no physical trigger applies.

## AR-01 joint optimization

AR-01 is acquisition optimization plus optical validation, not validation-only. A
prospectively selected candidate set and deterministic selection rule are frozen
before optical results are viewed. The stable nonbiological target is not Mylar.
For each candidate tuple it jointly evaluates scan speed (1-10000 cm-1/s), spectral
window/direction, HF2LI time constant/order/output rate/input range/phase, record
length/padding, exclusions, SNR, throughput, and data volume.

Required outputs include native spacing `v_scan / f_out`, validated-model spectral
lag and broadening, order-specific settling, effective noise bandwidth, duration
`window_width / v_scan`, direction hysteresis, clipping/range margin, sample-loss
and throughput margin, total uncertainty, and selection robustness. Expressions
such as `v_scan*n*tau` and `v_scan*sqrt(n)*tau` are labeled approximations and must
be checked against the retained HF-01 transfer model. Output-rate/filter-bandwidth
and installed-rate constraints are mandatory. Noise minimization cannot sacrifice
required spectral or temporal features.

AR-01 selects either one configuration with a bounded speed envelope or explicitly
named slow/high-resolution, normal analytical, and rapid/stroboscopic modes. Final
installed choices also require the relevant PF/IRF evidence.

## Pre-polystyrene readiness

QCL polystyrene work is locked until promoted evidence covers HF2LI/stream quality,
MIRcat DIO/sweep timing, detector dark noise/drift/gain/linearity/saturation/
wavelength and temporal response, relative latency, sample/reference balance,
normalization covariance, MIRcat power/pulses/wavelength/scan envelope, probe beam
profile/transfer, required pump beam profile, overlap/repeatability, cell/windows/
path/blank/temperature, AR-01 settling/optimization, and PF-00.

PF-00 measures normalized baseline noise, common-mode rejection, drift, saturation
margin, and adequate SNR before standards. PF-01 remains later and covers full
platform sensitivity, pump artifacts, experiment-length stability, and biological
anchor operating envelopes.

## Three qualified time-resolved acquisition modes

The canonical prospective procedure for both proteins is
`experiments/time_resolved_acquisition_modes.md`.

- **Fixed-wavelength kinetics:** settled pre-pump baseline at primary, secondary,
  and off-band wavelengths; Sample, Reference, full DIO, MIRcat readbacks, observed
  pump, temperature, and configuration IDs; negative-delay/pump-blocked controls;
  complete recovery; exposure/recovery enforcement; balanced order; pulse- and
  stream-level retention.
- **Phase-shifted rapid-scan stroboscopy:** repeated recoverable events with a
  predeclared pump-to-scan phase schedule, both scan directions, blocked/no-sample
  controls, measured scan repeatability, and retention of corrected instantaneous
  wavenumber plus delay from the observed pump. The predeclared 2-D reconstruction
  reports its actual coverage matrix and rejects unsupported interpolation. A
  nonbiological surrogate demonstration precedes biology. One rapid scan is never
  an instantaneous spectrum.
- **Wavelength-by-wavelength reconstruction:** a predeclared delay grid and repeated
  accepted events at each wavelength; recovery/state checks before wavelength
  changes; matched controls; qualified normalization; explicit wavelength-dependent
  power, linewidth, timing, detector response, and uncertainty; no unbridged pooling
  of configurations.

All three remain documented even if evidence later rejects one as insufficient.

## HRP and optional cryogenic MbCO

HRP is optimized for approximately second-scale recovery and only faster early
features supported by IRF and SNR. It covers all three modes and uses the minimum
probe duty/repetition rate meeting resolution and precision. Preferred low-rate and
high-rate fallback architectures have distinct configuration IDs and require a
bridge study if both contribute to one claim.

QB-01M is the mandatory entry gate only for optional MbCO. It does not assert the
slowed kinetic timescale. It qualifies cryostat geometry/windows/transmission,
temperature stability/gradients/condensation/recovery, MIRcat 20-25 ns through
1005 ns pulse widths, T660-2 rate, current, wavelength/linewidth, trigger latency/
jitter, power stability, detector/Pico saturation/response, and HF2LI applicability
to the supported tens-to-hundreds-of-microseconds target envelope.

`duty_cycle = repetition_rate_Hz * pulse_width_seconds <= 0.30` is a hard ceiling;
a documented lower operating margin is selected. At 2 MHz the ceiling is 150 ns,
so 1005 ns at 2 MHz is prohibited. Device, detector, cooling, stability, cryostat,
and sample limits may be stricter. Direct detector/PicoScope is used for pulse-level
resolution. HF2LI is used only within its measured envelope. If cryogenic MbCO is
still faster, retain the direct path, narrow the claim, or stop the branch.

## Numerical freeze register

The following remain `USER_INPUT_REQUIRED` until measured/promoted; absence must not
be encoded as zero. Each is frozen under a stable requirement/configuration ID before
the consuming phase opens:

1. Per-mode temporal resolution, distortion, SNR/precision, signal range, detector
   noise spectrum, duration, recovery, exposure, and data-volume/throughput limits.
2. Per-mode HF2LI time constant, order, rate, range, phase, input, settling rule,
   record length/padding, loss margin, and candidate-selection robustness threshold.
3. Sweep window, speed/mode envelope, direction rule, native spacing, lag,
   broadening, hysteresis tolerance, baseline exclusions, and scan count.
4. Detector gains, linearity/saturation margins, wavelength response, temporal
   response/latency, dark drift, sample/reference balance, normalization covariance,
   and common-mode rejection/SNR thresholds.
5. MIRcat current, point/scan power, pulse width, rate, linewidth, wavelength
   stability, scan envelope, trigger latency/jitter, and operating margins.
6. Probe/pump beam diameters and profiles, sample-plane transfer, overlap tolerance,
   alignment repeatability, cell/window/path/blank transmission, temperature
   setpoints/stability/gradients, and condensation limits.
7. Polystyrene partition IDs, reference feature values/windows, correction model,
   coefficient/covariance acceptance, holdout tolerances, validity range, baseline/
   fit method, and software/schema/analysis versions; specimen-matched Mylar
   tolerances and blind decision rules.
8. HRP primary/secondary/off-band wavelengths, delay/phase grids, baselines,
   repetitions, recovery/exposure limits, pump dose/power, duty/rate, IRF threshold,
   and bridge criteria.
9. MbCO cryostat design and qualified temperature envelope; primary/secondary/
   off-band wavelengths; delay/phase grids; pulse width/rate/current/duty margin;
   recovery/heating/perturbation limits; direct-path/HF2LI boundary; and bridge/
   stop criteria.

## Promotion, reporting, and preservation audit rule

Promotion reports must distinguish historical validity, current applicability,
future supersession, and physical revalidation. They include configuration and
software/schema/analysis versions, uncertainty/covariance, validity envelopes,
reuse/supersession tables, all accepted and nonaccepted acquisition states,
restoration, unresolved inputs, and staged core versus optional-MbCO decisions.

Before and after future edits/execution, retention audits compare stable IDs,
relative paths, byte sizes, roles, row counts, timestamps, and source relationships.
Every indexed path must be checked. Missing paths are reported, not fabricated or
removed. Hashes may be informational only and never gate acceptance or progress.

This amendment performed no hardware operation, created no observation, changed no
completed readback, and authorized no phase execution.
