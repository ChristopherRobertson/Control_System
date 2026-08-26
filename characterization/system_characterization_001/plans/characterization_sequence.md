# Pump-probe instrument characterization sequence

Campaign: `system_characterization_001`

Status: **PLAN ONLY; WM-01 / ATT-01 / OPO-540 CHAIN DEFERRED; SV-01 MAY PROCEED AFTER SP-01 WITH SEPARATE AUTHORIZATION; PROMOTION BLOCKED**

## Objective and boundary

This run establishes the measured operating envelope and performance of the
installed pump-probe platform for the thesis and downstream experiments. Calibration
determines axes, corrections, provenance, bounded uncertainty, and safe qualified configurations;
characterization applies them to the actual pump, probe, optical geometry, and
integrated instrument.

Biological method development and biological kinetics are separate downstream
campaigns. No biological sample is used as a calibration or characterization
standard in this run.

Requirements-level designs for the Mylar method check, horseradish-peroxidase,
and myoglobin-CO experiments must define intended claims and actual operating
conditions before CH-00 freezes this campaign's test grid. This is not
permission to create executable biological recipes before calibration and
characterization results exist. It is a scope-control step so the campaign
measures only what the experiments need.

The available optical metrology includes a power meter but no energy meter.
Accordingly, no phase assumes direct pulse-energy distributions,
pulse-to-pulse energy jitter, or calibrated peak power. Mean pulse energy may
be derived as average power divided by verified repetition rate when the meter
and acquisition are suitable, with the derivation and limitation stated.

The retained OPO-540 path includes the permanent ATT-01-qualified electronic
iris. Characterization measures the beam only after this fixed far-field mount
and accepted 540 nm aperture setpoint. Every emitted OPO block retains the iris
device/configuration ID, command, readback, and validity state; the iris is not
used as a safety shutter or pulse-admission device.
Independent center-wavelength/status evidence uses the WM-01-qualified
WaveMaster configuration. Every applicable record retains its working-
reference bundle, device/adapter/probe configuration, units, pulsed mode,
autocalibration state, native time tag/value/status, and uncertainty. The
WaveMaster does not measure spectral-power fractions or the 355 nm drive.

## Non-duplication and dependency gate

- Import `system_recalibration_001` results through `calibration_links.csv`.
- OPO-540 phases must import ATT-01's electronic-iris control, permanent-mount,
  aperture-optimization, spectral-rejection, transfer, and revalidation bundle.
- OPO-540 wavelength claims must import WM-01's wavelength working-reference
  bundle and ATT-01/PB-02 residual-spectral-content evidence. A center
  wavelength is not evidence that all measured optical power is at 540 nm.
- Never copy or modify calibration raw files. Never reacquire a calibration
  quantity only to populate a characterization table.
- A phase may use a provisional calibration input only when the manifest names
  it, preserves its uncertainty/limitation, and the phase plan explicitly
  accepts the risk. Otherwise the required calibration bundle must be promoted.
- If characterization exposes a calibration defect, stop the affected phase
  and open a separately approved suffixed calibration investigation. Do not
  repair calibration inside the characterization record.

## Common execution gates

1. Approval is phase-specific and does not confirm a rewire or emission.
2. Read existing evidence before acting; resume the same phase record across
   days.
3. Freeze configuration, acceptance criteria, wavelengths, repetition counts,
   uncertainty inputs, and any emitted-shot or exposure budget before hardware
   action.
4. Apply/read back safe idle before physical transitions. Laser emission
   requires separate approval, operator readiness, and restoration planning.
5. Preserve native raw data, all attempted acquisitions, controls, previews,
   rejected/excluded records, readbacks, and analysis provenance.
6. A phase closes only after all mandatory deliverables exist and pass the
   retention audit in `docs/measurement_campaign_data_contract.md`.
7. Do not advance on a scientific FAIL. `USER_INPUT_REQUIRED` may permit only
   independent work and must propagate into claim limitations.
8. No canonical summary is promoted without
   `APPROVE CHARACTERIZATION PROMOTION`.

## Required phase closeout package

Every phase produces the common manifest and tables, immutable indexed raw
data, settings/readbacks, conditions and environment, calibration links,
analysis source, machine-readable results with units/uncertainties, acceptance
decisions, final report, restoration confirmation, and unresolved-input list.
Only repository-approved provenance fields may be used. Phase-specific
deliverables below are additional requirements.

## Phase sequence

### 2026-08-25 deferred calibration-dependency amendment

The installed WaveMaster failed WM-01 optical qualification and a replacement
spectrometer is pending. Every characterization phase consuming WM-01,
ATT-01, or OPO-540 evidence remains deferred and cannot execute or close on a
setpoint-only or bypass basis. `SV-01` is dependency-independent of that chain
and may proceed after calibration `SP-01` closes, with separate phase
authorization, even though it appears later in the numbered integration order.
`RPT-CH` cannot close and `PROM-CH` cannot begin until the deferred calibration
and characterization chain returns and passes.

Legacy downstream references to `WaveMaster` mean the future WM-01-qualified
wavelength instrument. They do not grant authority to the failed installed
device or require the replacement to use the same interface or native format.

The intended integration order is `PB-02 -> QB-01 -> SC-01 -> OG-01 -> OV-01 ->
AR-01 -> SV-01 -> SV-02 -> IR-01 -> PF-01 -> RP-01 -> E2E-CH -> RPT-CH ->
PROM-CH`, subject to each phase's calibration dependencies and separate
authorization and the dependency-independent SV-01 exception above. PB-01 is a supplemental thesis characterization performed after
PROM-CH under its own authorization. It is outside the required completion,
promotion, and biological-entry dependency chain.

### CH-00 — claim, scope, and calibration-import freeze

Status: **COMPLETE — PASS; ANALYSIS-ONLY CLOSEOUT; PB-02 NOT AUTHORIZED**

Define the claims the thesis and downstream experiments will make, the tested operating
envelope needed to support them, and the calibration dependencies for every
reported quantity. This phase is analysis-only.

The mandatory grid is the smallest union of the three verified briefs:

- one probe-only continuous-sweep window around the specimen-matched Mylar PET
  carbonyl feature and the polystyrene features needed to freeze its correction;
- the combined 1885-1980 cm^-1 biological probe region, reduced to the two
  HRP-C-CO bands, the MbCO A1/upper diagnostic band, and only the off-band
  anchors required by the controls;
- direct 532 nm pumping for HRP-C-CO;
- 355 nm only as the drive required to produce the 540 nm OPO pump for MbCO;
- 540 nm OPO pumping for MbCO; and
- exactly two acquisition topologies: probe-only continuous sweep and finite
  rare-pump fixed-wavenumber/recovery acquisition.

Shared anchors and settings are characterized once. The broad 1650-2050 cm^-1
probe survey, direct 1064 nm sample-path claims, broad OPO tuning, pulse-energy
distributions, peak power, and optional mechanistic/quantum-yield extensions
are excluded unless CH-00 is formally reopened before hardware begins.

Mandatory deliverables before CH-00 closes:

- Claim-to-measurement matrix distinguishing manufacturer specification,
  measured result, derived result, and unvalidated capability.
- Frozen wavelength/power/scan/delay test grid with rationale covering every
  retained condition in the three-brief union. Broader-range claims and their
  representative points remain excluded unless CH-00 is formally reopened.
- Calibration dependency graph and `calibration_links.csv` populated with the
  required bundle/quantity IDs and validity states.
- Imported final P0 requirement decisions that affect reference bases,
  spectral standards, observational environmental records, or installed
  detector identity.
- Equipment/sample/component registries, configuration-ID method, acceptance
  criteria, uncertainty plan, and exposure/shot-budget policy.

#### Retained permanent OPO-iris configuration boundary

CH-00 remains complete and is not reacquired or rewritten. The iris does not
change its wavelength, claim, biological-sample, or acquisition-topology
evidence. All unexecuted phases treat the ATT-01-qualified iris and the
WM-01-qualified wavelength working reference as required parts of the final
OPO-540 configuration. The characterized wavelength remains 540 nm only.
Observed X/Y beam-center motion elsewhere in the OPO tuning range is a reason
not to extrapolate this configuration: any future OPO wavelength requires a
separately approved wavelength-specific iris/centroid qualification.

Every unexecuted downstream phase uses one biological pump path:
permanent-iris OPO 540 nm, used by HRP-C-CO first and MbCO second. Completed
CH-00 evidence remains unchanged and is not repeated. The shared instrument
configuration is characterized once; HRP and MbCO retain separate sample-
specific dose, absorbance, overlap, photolysis, damage, and kinetics pilots.

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

### QB-01 — minimal MIRcat probe-source characterization

Characterize only the module(s) intersecting the retained Mylar/polystyrene
carbonyl window and combined 1885-1980 cm^-1 biological region. In the Mylar
window use the lower edge, selected feature, and upper edge of the accepted
continuous sweep. In the biological region use the merged HRP/MbCO band and
off-band anchors; coincident anchors are one condition. Test the single sweep
operating point and the single fixed-wavenumber/rare-pump operating point.
Measure a module transition only if a retained window crosses one. Reuse SP-02
axis calibration and MSW-01 timing; do not redetermine them or survey unused
modules/ranges.

Mandatory deliverables:

- Synchronized MIRcat readbacks, trigger/DIO records, optical-meter data, module
  identities, operating mode, pulse settings, and all calibration links.
- Power/pulse/stability versus wavenumber, module/crossover behavior, warm-up
  and repeatability tables, saturation limits, uncertainty, and recommended
  operating envelope.
- Measured-versus-manufacturer capability table and safe shutdown record.

### SC-01 — gas-tight sample-cell and temperature-stage qualification

Qualify the minimum nonbiological sample hardware shared by the HRP-C-CO and
MbCO procedures before biological preparation. Use water or the approved
buffer surrogate only; no CO or protein is used. CH-00 selects the smallest
cell set, preferring one common gas-tight CaF2 assembly/path when the two briefs'
transmission and sensitivity constraints allow it.

Mandatory deliverables:

- Stable IDs for cell body, windows, spacer, seals, mount, temperature sensor/
  stage, and fill/vent hardware; measured assembled path length and uncertainty;
  fill/dead volume; aperture; orientation; cleaning and assembly method.
- Empty-cell and filled-blank transmission at the retained probe anchors,
  background/fringe/scatter results, bubble and leak criteria, one disassembly/
  reassembly check, and compatibility with the retained pump/probe geometry.
- Temperature-sensor basis, spatial placement, equilibration rule, stability/
  drift and uncertainty at 293 K and 298 K when active control is available.
  If a setpoint cannot be controlled, record the observational limit and narrow
  the later kinetic claim rather than adding an unsupported calibration.
- Safe handling/restoration record and a biological-handoff table identifying
  the qualified cell/path/temperature configurations. CO loading, protein
  state verification, and chemical stability remain experiment-phase work.

### OG-01 — sample-plane optical transfer and beam geometry

Using the final optical path and SC-01 cell/mount, characterize exactly three
optical conditions: probe-only Mylar validation, permanent-iris OPO-540/HRP
probing, and the same OPO-540 pump with MbCO probing. For the QCL, profile one Mylar anchor and the lower/upper
biological anchors; add an intermediate point only if the endpoint comparison
fails the wavelength-dependence criterion. Measure pump and probe spot size
using a stated diameter convention, spatial profile, incidence angle,
polarization, path length, transfer efficiency, average power, derived mean
pulse energy where allowed, fluence/irradiance inputs, and positioning
uncertainty.

For OPO-540, the final path begins at the qualified post-iris plane. OG-01
independently verifies that the accepted aperture does not clip the useful core
at the sample plane and measures the delivered post-iris power used to derive
mean pulse energy and theoretical pump dose. Pre-iris OM-01 mixed-output power
is not substituted for this quantity.

Mandatory deliverables:

- Reference-plane and optical-layout diagrams/photos with stable optic,
  attenuator, meter-pickoff, electronic-iris device/configuration/readback,
  aperture, window, and mount IDs.
- Native profiles/images/readings; background and scale calibration; beam-
  diameter calculations; transfer/fluence/irradiance tables with full
  uncertainty propagation.
- Alignment coordinates or reproducible fiducials, acceptance bounds, damage/
  saturation margins, and restoration/reinstallation record.

### OV-01 — pump-probe overlap and placement repeatability

Establish spatial overlap at the sample or sample-equivalent plane without
using the desired biological response as the only indicator. Quantify overlap
fraction, relative centroids, crossing angle, overlap area/volume as applicable,
placement repeatability, and sensitivity to routine realignment.

Retain only two pump/probe pairs: permanent-iris OPO 540 nm with the HRP probe
geometry and that same pump with the MbCO A1 probe geometry. For each pair perform three
independent placements and one controlled realignment. Mylar is pump-off and
adds no overlap condition. Add a second probe wavenumber only if OG-01 shows a
material geometry change across the corresponding biological window.

All OPO-540 placements retain the same ATT-01/PB-02 iris mount and diameter.
The controlled realignment tests routine downstream placement and does not
authorize an iris adjustment. If overlap cannot pass without changing the
iris, stop and investigate the upstream configuration rather than fitting the
aperture to a biological or desired-response result.

Mandatory deliverables:

- Independent overlap method, blocked/single-beam controls, native images or
  scans, coordinate transforms, profile fits, and overlap calculation source.
- Overlap fraction/area/volume with uncertainty, alignment tolerances,
  reinstallation/realignment repeatability, and explicit validity for each
  pump/probe condition.
- Final fiducial/alignment procedure and sample-position record suitable for
  later biological campaigns.

### AR-01 — acquisition settling and scan-dwell response

Using an optically stable nonbiological signal and the qualified HF2LI setup,
validate exactly three experiment-specific acquisition configurations across
two topologies. Import the HF-01 PicoScope-AWG complex transfer, step, range,
rate, noise, channel-equivalence, and uncertainty results; do not repeat its
electrical parameter grid. For the Mylar continuous sweep, compare the selected
speed/filter setting with one slower quasi-static reference in both directions,
because that optical comparison is required to measure scan peak shift and
broadening. For each HRP-C-CO and MbCO fixed-wavenumber configuration, acquire
the selected setting only using one controlled nonbiological point transition
and that workflow's retained record envelope. Compare observed settling,
filter memory, and Sample/Reference response with the HF-01/DET-03 prediction.
Add one bracketing biological setting only when the prediction residual fails,
the observed result lies inside its acceptance guard band, or an installed
source/detector effect cannot otherwise be separated. A common numeric setting
remains acceptable only with the explicit HF-01 equivalence record and separate
configuration IDs.

Mandatory deliverables:

- Native Sample/Reference/full-DIO streams, complete settings/readbacks,
  controlled step/dwell series, and environmental records.
- Imported-versus-observed response residuals, scan-direction shift/broadening,
  minimum justified dwell, filtering/averaging rules, covariance behavior,
  uncertainty, and any predeclared bracket-escalation decision.
- Three frozen experiment-specific acquisition configuration IDs linked to
  their permitted scan/record envelopes, including filter transfer, effective
  noise bandwidth, settling, temporal attenuation/bias, and any explicit
  biological equivalence alias.

### SV-01 — independent FTIR reference-data acquisition

Acquire or register one specimen-matched high-resolution FTIR reference set for
polystyrene and one for Mylar. No other standard and no biological spectrum is
part of this phase. Match the retained polarization/orientation basis and
acquire only the resolution/coadds required by the frozen position/shape
uncertainty allocation. Do not refit the QCL axis here.

Mandatory deliverables:

- FTIR instrument/configuration identity, sampling geometry, resolution,
  apodization, scans, background, sample presentation, observational
  temperature, available path/thickness information, preprocessing, and
  source-data provenance. Missing film thickness does not block peak-position
  alignment or independent validation.
- Immutable native FTIR exports plus normalized CSV in the notebook-required
  layout, artifact IDs/paths/sizes/timestamps, feature/uncertainty authority,
  and preprocessing source/version.
- Separation of calibration, independent validation, and illustrative-only
  records.

### SV-02 — polystyrene alignment, Mylar validation, and forward-model comparison

Start from the frozen SP-02 instrument-axis result, then use only the declared
polystyrene alignment partition to fit the final wavenumber correction against
authoritative polystyrene feature values. Use a first-order correction unless
a higher order is justified by predeclared residual criteria and uncertainty.
Freeze the fitted function, coefficients, covariance, validity range, and
software version before opening the Mylar data or any later biological data.

Apply that frozen correction to an independent polystyrene holdout partition
and to Mylar. Mylar is the independent external validation standard and may
not refit or tune the correction. Biological samples are outside this phase
and may never define or revise the alignment. Compare corrected QCL spectra
with high-resolution FTIR forward predictions. Apply the DET-04 background-
ratio correction with its uncertainty; never force or assume equal
sample/reference powers.

Mandatory deliverables:

- At least the CH-00-defined repeated scans in both directions with complete
  Sample/Reference/DIO/readback records and acquisition settings.
- Peak centers, Gaussian/sloping-baseline fits, FWHM/effective resolution,
  residuals, RMS wavenumber deviation, SNR, baseline/etalon amplitude,
  direction hysteresis, repeatability, and uncertainty.
- Predeclared polystyrene alignment/holdout assignment; authoritative feature
  table; frozen correction function, coefficients, covariance, residuals,
  validity range, and software version; independent Mylar result; and proof
  that neither Mylar nor biological data influenced the correction.
- DET-04 correction ID, raw-ratio versus normalized-result audit, forward-model
  inputs/outputs, figures/tables, and thesis-claim acceptance decision.

The minimum acquisition is the predeclared polystyrene alignment and holdout
sets plus three accepted Mylar scans per direction. The post-freeze Mylar
heterogeneity pilot may increase coupon/site/remount counts prospectively, but
no extra scan, material, orientation, or spectral window is added merely to
improve the appearance of the result.

### IR-01 — system temporal instrument response

Measure the complete instrument temporal response at a sample-equivalent plane
using the OP-01/CL-01 time origin and the applicable experiment-specific
detector/acquisition settings. Apply the HRP configuration to both HRP bands
and the MbCO configuration to MbCO A1; do not transfer lock-in filter delay or
attenuation between them without the HF-01/AR-01 equivalence record.
Characterize the combined effects of pump duration, probe gate, residual
jitter, detector response, and lock-in filtering without repeating electrical
path calibration.

Use three retained configurations only: permanent-iris OPO 540 nm at the lower
HRP-C-CO band, the same pump at the upper HRP-C-CO band, and the same pump at
the MbCO A1 band. Merge HRP upper/MbCO probe settings only where the combined
probe/detector response is demonstrably equivalent. The repeat count is selected
prospectively from the IRF-width/bias precision target and capped by the frozen
exposure budget. Mylar adds no temporal-response condition.

The OPO-540 configuration uses the static qualified iris. Its command/readback
and configuration ID are retained with each block, but iris communication
latency is not convolved into the per-shot IRF because the aperture is not
commanded during an emitted sequence.

Mandatory deliverables:

- Raw synchronized optical/electrical/DIO traces, configuration and calibration
  links, reference-plane definition, blocked controls, exposure ledger, and
  detector placement.
- True-versus-observed response model, impulse/step response as appropriate,
  FWHM or other resolution metric, delay bias, operating-condition dependence,
  uncertainty, residuals, and supported temporal window.
- Exact chemical-time-zero handoff convention for later biological campaigns.

### PF-01 — platform sensitivity, noise, artifacts, and stability

Under normal optical operation with nonbiological controls, determine noise-
equivalent absorbance, minimum detectable absorbance for stated integration,
SNR scaling with averaging, drift, Allan behavior, common-mode rejection,
baseline/etalon artifacts, back-reflection sensitivity, and saturation margin.
Reuse component-level detector results and the DET-04 optical/detector balance
model; do not reacquire the splitter calibration.

The minimum grid is one complete Mylar continuous-sweep control under the sweep
configuration, fixed-wavenumber records at the two HRP bands under the HRP
configuration and MbCO A1 under the MbCO configuration, and one shared
off-band control. At each condition acquire one short record and one record as
long as the corresponding planned experiment block. Run pump-blocked plus
finite OPO-540 artifact controls only at their matching
biological anchors. Add power, dwell, or averaging points only if the retained
claim's detection/precision rule fails.

The OPO-540 controls use the qualified iris without adjustment and explicitly
test for residual pump-color/scatter artifacts after the aperture. Record the
post-iris power, iris configuration readback, and native WaveMaster wavelength/
status record for every associated block. Use the accepted spectral method,
not a center-wavelength reading alone, to assign or bound residual-color power.

Mandatory deliverables:

- Fixed-wavenumber short/long traces, repeated spectra, Sample/Reference and
  normalized records, controls, settings, conditions, and all rejection logs.
- Noise/Allan/SNR/averaging/common-mode/artifact metrics with definitions,
  confidence intervals, uncertainty, and recommended integration/averaging
  envelope.
- Explicit distinction between detector/electronics limits and complete-
  platform optical limits.

### RP-01 — between-run reproducibility and operational envelope

Repeat only representative characterization conditions selected in CH-00 on
separate days and after one documented normal restoration/reinstallation. This
tests reproducibility; it is not a repeat of the complete characterization
grid.

On each of three independent days, run one compact checkpoint suite containing
the Mylar sweep anchor under the sweep configuration, one OPO-540/HRP surrogate
point under the HRP configuration, and one OPO-540/MbCO surrogate point under
the MbCO configuration with the unchanged iris configuration. Shared startup,
dark, geometry, and restoration evidence
is recorded once per day. Do not repeat full PB/QB/OG/OV/AR/SV/IR/PF grids.

Each OPO-540 checkpoint verifies the permanent mount/fiducials, commands and
reads back the promoted diameter, and evaluates centroid/profile/aperture
margin against the revalidation limits. It also acquires a WM-01-linked native
wavelength/status checkpoint in the retained probe geometry. Failure triggers
recharacterization; the daily checkpoint does not optimize a new diameter.

Mandatory deliverables:

- Exactly three planned independent day/configuration realizations for the
  selected checkpoints, with stable configuration IDs, complete settings
  snapshots, environment, operator actions, and calibration validity. An
  additional realization is allowed only under the campaign minimal-grid rule.
- Within-run, between-run, and restoration components; control charts or
  equivalent drift assessment; agreement with earlier phase results; and
  recharacterization triggers.
- Final operating-envelope table identifying validated, conditionally
  validated, manufacturer-only, and unsupported regions.

### E2E-CH — bounded nonbiological full-system demonstration

Run one composite nonbiological demonstration with three bounded blocks under
one reviewed phase plan: probe-only Mylar-style continuous sweep under the
sweep configuration, finite OPO-540/HRP-style fixed-wavenumber recovery under
the HRP configuration, and finite OPO-540/MbCO-style fixed-wavenumber recovery
under the MbCO configuration using one unchanged iris configuration. Reuse
calibration FE-01/E2E-01 fault-recovery
evidence; do not repeat simulated failures unless the orchestration or
configuration has materially changed.

The OPO-540 block includes electronic-iris startup/ownership, accepted command/
readback, configuration foreign key, post-iris power, mismatch stop, unchanged-
setpoint audit, WaveMaster working-reference identity/settings/native status,
and restoration. The iris remains outside finite-event control.

Mandatory deliverables:

- Complete manifest, native Sample/Reference/DIO/source/readback data,
  calibration and characterization configuration IDs, axes, processing,
  startup/safe-stop/restoration records, and artifact audit.
- Predeclared expected result, observed agreement, uncertainty, and a readiness
  decision for biological method development.

### RPT-CH — characterization reporting and thesis reuse package

Analysis-only aggregation phase. It must not create replacement measurements.
PB-01 is outside its required-phase completion gate.

Mandatory deliverables:

- Campaign-wide concatenated indexes/tables after identifier, relationship,
  metadata, path-existence, and file-size validation.
- Source/beam/geometry/spectral/temporal/noise/reproducibility summary tables,
  uncertainty budgets, machine-readable claim-to-evidence matrix, and
  thesis figure and downstream-experiment source packages.
- Electronic-iris characterization summary linking ATT-01 control/placement
  evidence to PB-02/OG/OV/RP results, the accepted 540 nm setting and tolerance,
  post-iris dose inputs, spectral-rejection/core-margin bounds, and all
  revalidation triggers.
- Wavelength-metrology summary linking the WM-01 device/adapter/power/probe
  configuration and uncertainty to PB-02/PF/RP/E2E records, with native status
  handling and an audit that center-wavelength evidence was not used as a
  spectral-power fraction.
- Data dictionary, analysis environment, reproducibility instructions,
  retention audit, unresolved/bypass register, and biological-handoff bundle.

### PROM-CH — characterization promotion gate

Present the reviewed characterization bundle, acceptance results, limitations,
retention audit, proposed canonical summaries, and biological-entry criteria.
No canonical promotion occurs without the exact phrase
`APPROVE CHARACTERIZATION PROMOTION`.

Mandatory deliverables: exact proposed diff, approved bundle ID and validity
envelope if promoted, recharacterization triggers, archive/rollback plan, and
downstream dependency record.
Promotion of the OPO-540 envelope requires the WM-01 wavelength working-
reference bundle, ATT-01 electronic-iris bundle, and accepted
PB-02/OG/OV/RP configuration chain; a bypass cannot support quantitative
540 nm dose or notebook-prediction claims. PB-01 is outside this gate.

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

## Biological handoff

Later biological campaigns must reference promoted calibration and
characterization bundle IDs, use the validated operating envelope, retain their
own sample/preparation/control metadata, and never mutate these campaign
archives. At minimum they inherit the sample-plane fluence/overlap method,
spectral-axis calibration, temporal-origin convention, acquisition settings,
normalization model, sensitivity limits, and revalidation triggers.
HRP-C–CO first and MbCO second additionally inherit the same permanent iris
device/service version, locked mount/fiducials, 540 nm command/readback/
tolerance, post-iris power and beam geometry, contamination bound, and
configuration-validity checks. The iris is not adjusted during either
experiment. HRP closeout/restoration is the operational handoff to MbCO, while
each protein retains separate biological dose and response evidence. Another
OPO wavelength cannot inherit the 540 nm setting and requires its own approved
qualification.
