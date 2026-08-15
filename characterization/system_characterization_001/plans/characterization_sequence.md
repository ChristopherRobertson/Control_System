# Pump-probe instrument characterization sequence

Campaign: `system_characterization_001`

Status: **PLAN ONLY — NO HARDWARE, EMISSION, OR ACQUISITION APPROVED**

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

## Non-duplication and dependency gate

- Import `system_recalibration_001` results through `calibration_links.csv`.
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

### CH-00 — claim, scope, and calibration-import freeze

Define the claims the thesis and downstream experiments will make, the tested operating
envelope needed to support them, and the calibration dependencies for every
reported quantity. This phase is analysis-only.

Mandatory deliverables before CH-00 closes:

- Claim-to-measurement matrix distinguishing manufacturer specification,
  measured result, derived result, and unvalidated capability.
- Frozen wavelength/power/scan/delay test grid with rationale, including
  every condition intended for biological work and representative points for
  any broader range claim.
- Calibration dependency graph and `calibration_links.csv` populated with the
  required bundle/quantity IDs and validity states.
- Imported final P0 requirement decisions that affect reference bases,
  spectral standards, observational environmental records, or installed
  detector identity.
- Equipment/sample/component registries, configuration-ID method, acceptance
  criteria, uncertainty plan, and exposure/shot-budget policy.

### PB-01 — Nd:YAG direct-output characterization

Characterize the installed Nd:YAG at 1064 nm and the direct 355 nm path under
the operating Q-switch conditions intended for downstream work. Measure only
conditions required by the frozen claim grid.

Mandatory deliverables:

- Source-plane average-power readings at experiment-required conditions,
  repetition-rate verification, warm-up behavior, short-term stability,
  longer drift record, and rejected-reading accounting. If useful, report only
  derived mean pulse energy from average power and verified repetition rate.
- Exact harmonic configuration, meter/sensor IDs, wavelength corrections,
  trigger/timing configuration, polarization and beam-location observations,
  environmental conditions, and all calibration/attenuation links.
- Average-power stability and uncertainty tables, any explicitly derived mean
  pulse-energy table, recommended operating window, saturation/damage-margin
  statement, and safe restoration. Do not claim direct pulse-energy
  distributions, pulse-to-pulse energy jitter, or calibrated peak power.

### PB-02 — OPO output and wavelength-dependent characterization

At every biologically intended OPO wavelength plus the representative points
defined in CH-00, measure average power, wavelength/readback agreement, only a
linewidth bound required by the experiment, throughput relative to the 355 nm pump,
stability, tuning repeatability, and unusable/gap regions. Direct 532 nm is
included only if it will be claimed or used.

Mandatory deliverables:

- Native pump/OPO meter and wavelength-reference records with synchronized shot
  or acquisition IDs.
- Average-power-versus-wavelength, pump-to-OPO throughput, required linewidth bound, warm-up,
  direction/revisit repeatability, and uncertainty tables.
- Explicit distinction between measured range, interpolated range,
  manufacturer-only range, and unavailable range; recommended wavelength-
  specific settings and restoration record.

### QB-01 — MIRcat probe-source characterization

Across each installed module and the CH-00 test grid, characterize sample-plane-
independent source output: average optical power, operating pulse settings,
repetition rate, duty cycle, wavelength/readback behavior, module transitions,
stability, tuning delay, and polarization. Reuse SP-02 axis calibration and
MSW-01 timing; do not redetermine them.

Mandatory deliverables:

- Synchronized MIRcat readbacks, trigger/DIO records, optical-meter data, module
  identities, operating mode, pulse settings, and all calibration links.
- Power/pulse/stability versus wavenumber, module/crossover behavior, warm-up
  and repeatability tables, saturation limits, uncertainty, and recommended
  operating envelope.
- Measured-versus-manufacturer capability table and safe shutdown record.

### OG-01 — sample-plane optical transfer and beam geometry

Using the final optical path, characterize how source output reaches the
sample plane. For every operating condition needed downstream, measure pump and
probe spot size using a stated diameter convention, spatial profile, incidence
angle, polarization, path length, transfer efficiency, sample-plane pulse
energy/power, fluence or irradiance, and positioning uncertainty.

Mandatory deliverables:

- Reference-plane and optical-layout diagrams/photos with stable optic,
  attenuator, meter-pickoff, aperture, window, and mount IDs.
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
characterize lock-in settling, dwell-time distortion, phase dependence,
forward/reverse peak shift, effective bandwidth, and sample/reference ratio
response under normal acquisition conditions. Import HF-01/HF-02/DET-01/02
and the DET-04 wavelength-dependent optical-balance/normalization bundle; do
not repeat their component or splitter-balance qualification.

Mandatory deliverables:

- Native Sample/Reference/full-DIO streams, complete settings/readbacks,
  controlled step/dwell series, and environmental records.
- Measured step response, model parameters, residuals, scan-direction shift/
  broadening, minimum justified dwell, filtering/averaging rules, covariance
  behavior, and uncertainty.
- Frozen acquisition configurations linked to their permitted scan envelopes.

### SV-01 — independent FTIR reference-data acquisition

Acquire or register the high-resolution FTIR references needed for polystyrene,
Mylar, and any other nonbiological validation standard. Do not refit the QCL
axis here and do not use biological spectra as calibration standards.

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

### IR-01 — system temporal instrument response

Measure the complete instrument temporal response at a sample-equivalent plane
using the OP-01/CL-01 time origin and qualified detector/acquisition settings.
Characterize the combined effects of pump duration, probe gate, residual
jitter, detector response, and lock-in filtering without repeating electrical
path calibration.

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

Mandatory deliverables:

- At least three independent day/configuration realizations for the selected
  checkpoints, with stable configuration IDs, complete settings snapshots,
  environment, operator actions, and calibration validity.
- Within-run, between-run, and restoration components; control charts or
  equivalent drift assessment; agreement with earlier phase results; and
  recharacterization triggers.
- Final operating-envelope table identifying validated, conditionally
  validated, manufacturer-only, and unsupported regions.

### E2E-CH — bounded nonbiological full-system demonstration

Run the final promoted characterization configuration end to end using a
nonbiological standard/control. Reuse calibration E2E-01 fault-recovery
evidence; do not repeat its simulated failure unless the software/configuration
has materially changed.

Mandatory deliverables:

- Complete manifest, native Sample/Reference/DIO/source/readback data,
  calibration and characterization configuration IDs, axes, processing,
  startup/safe-stop/restoration records, and artifact audit.
- Predeclared expected result, observed agreement, uncertainty, and a readiness
  decision for biological method development.

### RPT-CH — characterization reporting and thesis reuse package

Analysis-only aggregation phase. It must not create replacement measurements.

Mandatory deliverables:

- Campaign-wide concatenated indexes/tables after identifier, relationship,
  metadata, path-existence, and file-size validation.
- Source/beam/geometry/spectral/temporal/noise/reproducibility summary tables,
  uncertainty budgets, machine-readable claim-to-evidence matrix, and
  thesis figure and downstream-experiment source packages.
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

## Biological handoff

Later biological campaigns must reference promoted calibration and
characterization bundle IDs, use the validated operating envelope, retain their
own sample/preparation/control metadata, and never mutate these campaign
archives. At minimum they inherit the sample-plane fluence/overlap method,
spectral-axis calibration, temporal-origin convention, acquisition settings,
normalization model, sensitivity limits, and revalidation triggers.
