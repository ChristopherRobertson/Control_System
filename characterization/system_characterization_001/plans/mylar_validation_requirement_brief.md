# Mylar independent spectral-validation requirement brief

> **2026-08-26 material firewall:** SV-02A uses polystyrene calibration and holdout,
> then freezes correction/covariance, scan/HF2LI settings, normalization, analysis,
> windows, tolerances, and versions before issuing a Mylar unlock. SV-02B applies
> those frozen choices blindly. Mylar never tunes them; failure opens a cause-coded
> investigation or narrows the claim, never automatic refitting. See
> `campaigns/registry/phase_registry.yaml` and the preserved scientific design in
> `docs/campaign_reconstruction_20260826.md`.

Status: **REQUIREMENTS-LEVEL DESIGN ONLY — NOT AN EXECUTABLE RECIPE**  
Campaign phase: `SV-02` in `system_characterization_001`  
Material class: nonbiological characterization material  
Prepared for: thesis spectral-validation decision path  

This brief defines what must be true before, during, and after independent
Mylar validation. It does not authorize hardware operation, calibration,
characterization, recipe generation, or promotion. Final executable values
must come from the accepted bundles named below and from a closed `CH-00`
claim grid. Generic utility defaults and the numerical placeholders in the
theoretical notebook are not accepted settings.

## 1. Governing decision

The experiment shall answer one bounded question:

> After the MIRcat instrument axis has been calibrated independently and the
> final polystyrene alignment correction has been fitted and frozen, does the
> corrected QCL measurement reproduce the **position and line shape** of a
> specimen-matched, independently acquired FTIR spectrum of SPEX SamplePrep
> `3517 MYLAR`, within the predeclared uncertainty and thesis-use tolerances,
> in both QCL scan directions?

The result may support only these claims:

- local external validation of corrected wavenumber position over the Mylar
  feature window actually covered by the accepted QCL scan;
- agreement of normalized feature shape, center, and FWHM after applying the
  declared FTIR-to-QCL forward model;
- measured repeatability, scan-direction hysteresis, and observed residual
  baseline/fringe amplitude under the tested configuration; and
- a statement of whether the result is suitable for the downstream thesis
  claims frozen in `CH-00`.

The result shall not support these claims:

- Mylar-defined calibration, tuning, refitting, or revision of any wavenumber
  correction;
- traceability based on a missing Mylar certificate, lot, peak list, or
  thickness tolerance;
- absolute absorbance, concentration, extinction coefficient, thickness, or
  refractive-index claims;
- a quantitative etalon/thickness model or a film-thickness-derived fringe
  prediction;
- full-range spectral-axis accuracy if only the local carbonyl window is
  validated;
- repeat-day reproducibility unless the separate `RP-01` design is completed;
  or
- biological performance, sensitivity, temporal response, or pump–probe
  kinetics.

Mylar is never an input to the correction model. A failed Mylar result opens a
documented investigation or narrows the claim. It never triggers an automatic
refit.

## 2. Authority order and non-negotiable controls

Where requirements conflict, apply this order:

1. laboratory laser-safety rules, the installed-device interlock, and the
   manufacturer limits applicable to the exact installed unit;
2. promoted campaign bundles and accepted phase reports;
3. the frozen `CH-00` claim/test grid and the `SV-02` recipe contract;
4. the canonical theoretical notebook's equations, input layouts, and
   comparison conventions;
5. current manufacturer manuals and installed-unit correspondence;
6. peer-reviewed literature and standards; then
7. explicitly labeled pilot-selected settings.

No repository-authored hash or checksum match may be an operational gate.
Git object IDs and checksums may be recorded as information, but data use,
acceptance, aggregation, and promotion depend on human-readable identities,
relative paths, byte sizes, UTC timestamps, versions, source/producer records,
and the scientific gates in this brief.

The retired RSI-era procedures and sample recipes, and
`RSI_Manuscript.docx`, are outside the authority set.

## 3. Success decision and predeclared tolerances

`CH-00` shall define three thesis-use tolerances before `SV-02` recipe
generation:

- `T_position_cm-1`: maximum permitted absolute center bias;
- `T_FWHM_cm-1` or `T_FWHM_relative`: maximum permitted FWHM bias; and
- `T_shape`: maximum permitted normalized-shape residual metric.

Those tolerances shall be derived from the smallest error that would change a
downstream thesis interpretation, not from the observed Mylar result. If the
thesis has no quantitative tolerance, `CH-00` shall state that the result is a
descriptive consistency check and shall not label it an accuracy validation.

For each predeclared feature `j`, define

```text
delta_position_j = center_QCL_corrected_j - center_FTIR_forward_j
delta_FWHM_j     = FWHM_QCL_j - FWHM_FTIR_forward_j
z_position_j     = delta_position_j / u_combined_position_j
```

where the combined standard uncertainty includes the full covariance terms in
Section 14. Report a 95 % coverage interval or an equivalent Monte Carlo 95 %
coverage interval in accordance with JCGM 100 and JCGM 101 [U1, U2].

The primary result is **PASS for its stated claim** only when all of the
following are true:

1. all entry gates and control gates pass and no primary record has an
   unresolved loss, clipping, marker, sample-identity, or configuration error;
2. the polystyrene correction was frozen before any Mylar spectral data were
   opened by the analysis team;
3. for every primary feature, the upper 95 % bound on absolute position error
   does not exceed `T_position_cm-1`;
4. the upper 95 % bound on the declared FWHM error does not exceed the
   predeclared FWHM tolerance;
5. the upper 95 % bound on the primary normalized-shape metric does not exceed
   `T_shape`;
6. forward/reverse differences remain inside their allocated direction term;
7. the same decisions hold in the predeclared sensitivity analyses for FTIR
   instrument line shape, baseline window, QCL linewidth, and background
   interpolation; and
8. the independent polystyrene holdout remains acceptable before and after the
   Mylar block without refitting.

Also report statistical consistency (`|delta|` relative to its coverage
interval) separately from thesis-use tolerance. Statistical consistency alone
does not prove that a result is sufficiently accurate for the thesis, and a
small engineering error does not justify ignoring underestimated uncertainty.

## 4. Entry gates and required frozen inputs

No Mylar recipe may be authored or executed until the following are accepted
or promoted and linked by stable bundle/quantity IDs.

| Required input | Quantity required by this procedure | Why it is a gate |
|---|---|---|
| `CH-00` | claim grid, spectral window, operating envelope, tolerances, exposure policy | Prevents outcome-driven windows or thresholds. |
| `SP-01` | polystyrene and Mylar authority table; accepted scope and uncertainty classification | Establishes what each material can and cannot prove. |
| `SP-02` | frozen instrument-axis mapping, covariance, validity range, direction/channel rules | The starting axis must exist before final alignment. |
| `HF-01` | HF2LI device/configuration ID, external-reference qualification, demodulator/input assignments, rates, time constants, orders, phases, ranges | Generic presets are provisional. |
| `MD-01` | installed MIRcat DB9-to-HF2LI DIO bit mapping, polarity, transition and count rules | Required to segment and orient scans. |
| `MSW-01` | accepted scan speed, marker interval and width, marker count/jitter, active/gap rules, direction behavior | Required to construct the trigger-derived axis. |
| `HF-02` | simultaneous Sample/Reference/full-DIO timestamp alignment, loss limits, endurance envelope | Required for defensible dual-channel streaming. |
| `ATT-01` | identities and transfer functions of any installed attenuator or pickoff | No uncharacterized attenuation may enter silently. |
| `DET-01` | dark/noise and saturation behavior | Sets dark and clipping gates. |
| `DET-02` | separate installed detector/amplifier response functions and relative timing | The channels may not be treated as identical. |
| `DET-04` | installed wavelength-dependent optical-balance/normalization model, covariance, validity and drift rule | Equal splitter power may not be assumed. |
| `QB-01` | accepted MIRcat module, pulse rate/width/duty/cooling, QCL linewidth, power/stability, tuning delay, polarization, scan envelope | Resolves conflicts between generic limits and the exact laser. |
| `OG-01` | final reference plane, beam diameter convention, incidence, polarization, aperture/optic/mount IDs, fiducials, placement uncertainty | Makes FTIR and QCL geometry comparable. |
| `AR-01` | accepted scan-speed/time-constant/order/rate combination, measured settling and direction-dependent shift/broadening | Prevents lock-in dynamics from masquerading as spectral shape. |
| `SV-01` | sealed native FTIR records, normalized CSVs, matched geometry metadata, reference-axis uncertainty and feature rules | Provides the independent reference without fitting the QCL axis. |

The current repository does not contain accepted production values for most of
these quantities. That is a readiness finding, not permission to use the
candidate recipe.

## 5. Mylar identity, specimens, and handling

### 5.1 Material identity and claim status

The available item is recorded as:

| Field | Required record |
|---|---|
| Manufacturer | `SPEX SamplePrep` (now sold by Cole-Parmer SamplePrep) |
| Product/use | thin window film for XRF |
| Marking | `3517 MYLAR` |
| Nominal description | `0.25 mil (6 µm)` Mylar roll |
| Lot/batch/serial | none present |
| Supplied certificate | none |
| Supplied peak list or spectral uncertainty | none |

The nominal thickness identifies the product but is not an acceptance input.
The manufacturer listing corroborates the product form and nominal gauge [M1].
It does not create a thickness-tolerance, absolute-absorbance, or traceability
claim.

### 5.2 Specimen labels

Each coupon shall have a human-readable `sample_id` of the form

```text
MYLAR-3517-<cut_session_utc>-C<coupon_index>
```

and each illuminated site shall have a `position_id` linked to a measured
mount coordinate and a site photograph or diagram. Record:

- roll identity and packaging photographs;
- cut UTC time, operator, clean tool ID, and source location along the
  accessible roll when known;
- an arrow for roll/machine direction (`MD`) outside the clear aperture;
- front/back designation, even if the two faces appear identical;
- coupon outline and clear-aperture dimensions as measured results;
- `coupon_id`, `position_id`, orientation angle, face, mount ID, aperture ID,
  and every remove/remount event;
- visible defects, creases, scratches, haze, contamination, edge damage, or
  tension marks before and after each block; and
- storage container ID and storage interval.

Unknown roll position or manufacturing direction shall be recorded as
`unknown`; it shall not be guessed.

### 5.3 Coupon and position count

The mandatory minimum already fixed by the characterization matrix is at least
three accepted Mylar scans in each QCL direction [R7, R9]. That minimum
supports short-term scan repeatability only.

The number of coupons and positions is **pending a measured SV-01
heterogeneity pilot and `CH-00` uncertainty allocation**. It shall be frozen
before primary QCL Mylar data are acquired using this exact rule:

1. after the polystyrene correction is frozen and the Mylar embargo is lifted,
   measure a balanced pilot over separately identified coupon and position
   levels with matched FTIR geometry;
2. estimate coupon, position-within-coupon, remount, and scan variance using a
   nested model, following the NIST measurement-process framework [S1, S2];
3. calculate prospectively the coupon and position counts needed for the 95 %
   uncertainty bound on center and FWHM to remain inside the `CH-00` allocation;
4. freeze those counts and a balanced schedule before the primary QCL block;
   and
5. if the prospective count is infeasible with the available material or
   qualified instrument capacity, restrict the conclusion to the tested
   coupon/site rather than claiming roll-wide reproducibility.

The pilot specimens shall not be silently pooled with the primary validation
set. Counts and stopping rules shall not be adjusted after inspecting whether
the primary result passes.

### 5.4 Handling and mounting

- Store flat, covered, dry, and dark in an identified clean container. Record
  temperature and relative humidity observationally; do not claim traceable
  environmental accuracy from the current logger.
- Wear clean powder-free gloves and use clean nonmarring tools. Touch only
  sacrificial edges outside the clear aperture. Do not wipe the illuminated
  area, stretch the film, apply solvent, or remove dust by contact. If dust
  removal is necessary, use the laboratory-approved clean dry-gas method and
  record it.
- Use the same coupon, face, marked orientation, aperture, and nominal
  illuminated site for the paired FTIR and QCL primary comparison.
- Clamp only outside the clear aperture. The mount shall constrain position
  without visibly tensioning, bowing, wrinkling, or creasing the film. The
  installed tension method and clamp force, if measurable, are pending `OG-01`;
  “hand taut” is not an acceptable setting.
- Record the angle between marked MD and the QCL electric-field direction.
  The MIRcat data sheet specifies linear vertical polarization greater than
  100:1 for the generic product family [M2], but the exact installed value and
  laboratory vertical shall come from `QB-01`/`OG-01`.
- Keep the beam footprint and its placement-uncertainty envelope inside the
  clear aperture and away from prior damaged sites; the clearance is a
  measured `OG-01` result, not a guessed distance.
- A repeat mount shall fully remove and reinstall the coupon using the frozen
  fiducial method; a “repeat position” without removal is only a revisit.

Replace or exclude a coupon/site for a predeclared physical reason only:
tear, puncture, crease within the footprint, visible contamination, loss of
orientation mark, clamp slip, unrecorded face/orientation, beam footprint
crossing the aperture edge, or measured irreversible spectral change in the
fixed-wavenumber drift control. Retain all data and record the reason in
`exclusions.csv`.

## 6. Authoritative Mylar features and window selection

### 6.1 What is authoritative

“Mylar” is biaxially oriented polyethylene terephthalate (BoPET). Literature
does not provide a certificate value for this particular unlotted roll. The
authoritative value for comparison is therefore the **specimen-matched SV-01
FTIR center and shape with its own axis and fit uncertainty**. Literature
provides band identity and a blind search region, not an exact certified center
for this specimen.

PET literature reports a strong ester carbonyl feature near 1715–1719 cm⁻¹,
with center and FWHM changing with crystalline/amorphous content and film
direction [P1]. Polarized PET studies also resolve carbonyl contributions near
1685, 1710/1717, and 1735 cm⁻¹ and show orientation-dependent profiles [P2].
FTIR work on PET crystallization independently reinforces that PET band shape
depends on material state [P3]. Thus the carbonyl envelope is useful for
position/shape validation but cannot be treated as a universal single line.

### 6.2 Feature authority table

| Feature | Literature evidence | Use in this validation |
|---|---|---|
| Ester `C=O` stretching envelope | main maxima 1715–1719 cm⁻¹ in crystalline/amorphous and MD/TD PET; reported FWHM changes with structure and direction [P1] | **Primary** if inside the accepted MIRcat range. Center and FWHM come from the matched FTIR coupon/orientation, not the literature value. |
| Carbonyl substructure | reported components from 1685 to 1735 cm⁻¹ under polarization-sensitive analysis [P2] | Diagnostic search interval. Multiple components may be reported only if SV-01 resolution and an identifiability simulation show they are resolvable after QCL convolution. |
| Ring/ester/glycol bands below the carbonyl region | examples include 1578, 1505, 1471, 1410, 1341, 1260/1246, 1120/1100, 1021/1017, 972, 872/874, and 849/898 cm⁻¹ [P1] | Eligible only if `CH-00`, the installed QCL module, `SP-02`, and `QB-01` accept the range before unlock. They shall not be added after seeing Mylar results. |

The current design candidate scans 1650–2050 cm⁻¹ [R11], which contains the
carbonyl envelope but not the lower-wavenumber PET fundamentals above. If the
final accepted range is similar, `SV-02` is a local one-envelope external
validation and its report shall say so.

### 6.3 Blind selection rules

Before Mylar data are opened, freeze:

- the literature-defined carbonyl search interval spanning the reported
  1685–1735 cm⁻¹ substructure [P2];
- the rule for finding local baseline shoulders in the specimen FTIR trace;
- the maximum number of components permitted by the identifiability test;
- the primary Gaussian-plus-sloping-baseline model required by the canonical
  notebook [N1];
- the normalization and residual metrics; and
- the fallback rule if the feature is clipped, saturated, outside the accepted
  QCL range, or not identifiable.

The final fit window endpoints are pending measured `SV-01` local-baseline
locations. Select them without consulting QCL residuals. The same endpoints,
after applying the frozen axis transformation, shall be used for FTIR forward
prediction and QCL fitting. A secondary window sensitivity analysis may move
each endpoint only according to a predeclared FTIR-baseline rule.

## 7. Mylar data embargo and correction freeze

`SV-01` may acquire and register Mylar FTIR files before `SV-02`, but the
spectral contents shall remain unavailable to the correction-fitting analyst
until the final polystyrene correction is frozen.

Required sequence:

1. Register native Mylar FTIR artifact paths, byte sizes, UTC creation times,
   producer/instrument IDs, coupon/orientation metadata, and custodian without
   opening spectral values in the correction workspace.
2. Freeze the polystyrene alignment/holdout assignment before fitting.
3. Fit only the alignment partition, beginning from promoted `SP-02`.
4. Evaluate the polystyrene holdout without refitting.
5. Write `correction_freeze.json` containing function form, coefficients,
   covariance, validity range, software/analysis version, input acquisition
   IDs, fit and holdout metrics, freeze UTC time, operator, and approval state.
6. Record `mylar_unlock_log.json` with the later unlock UTC time, custodian,
   analyst, and authorized artifact IDs.
7. Only then open Mylar FTIR or QCL spectral values and run the frozen analysis.

Access control, timestamps, manifests, and review provide the proof. Hash
matching is neither required nor an acceptance gate.

## 8. `SV-01` independent FTIR requirement

### 8.1 Geometry and comparability

Acquire transmission FTIR on the exact primary coupon(s), face(s), marked
orientation(s), and sites later used in the QCL comparison. Record:

- FTIR make, model, serial, software version, source, beamsplitter, detector,
  aperture, accessory/mount, purge/vacuum state, and warm-up/performance-check
  status;
- incidence angle and its uncertainty, beam footprint/diameter convention,
  clear aperture, polarization state, polarizer identity/orientation and
  extinction information when available;
- coupon face, MD angle, site coordinate, mount/tension method, and all
  remounts;
- nominal resolution, actual point spacing, instrument line-shape assumption,
  apodization, phase correction, zero filling, scan count, acquisition time,
  background handling, and atmospheric compensation; and
- observational temperature and RH plus the instrument's wavelength-axis
  check and uncertainty source.

PET spectra are orientation-sensitive [P1, P2]. The primary FTIR comparison
shall therefore use a mid-IR polarizer and match the QCL electric-field basis,
or acquire both orthogonal polarization bases and select the matched one by the
predeclared geometry record. An unpolarized FTIR spectrum may be retained as a
diagnostic, but it cannot be the primary line-shape reference for a vertically
polarized QCL unless a measured sensitivity study shows polarization mismatch
is negligible relative to `T_shape` and the FWHM allocation.

### 8.2 Background and acquisition blocks

Use an empty, clean, identical aperture/mount as the FTIR background. Each
sample block shall be bracketed by backgrounds without changing purge,
aperture, resolution, apodization, gain, or polarizer. A bracket fails if the
background drift exceeds the `SV-01` allocation or if atmospheric features,
detector saturation, or source instability invalidate the carbonyl window.

Acquire separate native interferograms/spectra for each background and sample
block; do not retain only a coadded final trace. The scan count is pending a
pilot-selected precision result. Starting from the instrument's normal
high-resolution acquisition, acquire successively larger independent coadd
blocks and freeze the smallest supported count for which the 95 % uncertainty
of the carbonyl center, FWHM, and normalized-shape reference is inside its
`CH-00` allocation and no drift trend is detected. Do not select the count on
QCL agreement.

The recommended starting nominal FTIR resolution is 0.5 cm⁻¹ if supported by
the instrument. NIST's polystyrene work used 0.5 cm⁻¹ instrument-calibration
measurements and about 1.3 cm⁻¹ polystyrene measurements [W1]; the MIRcat
family data sheet specifies pulsed linewidth no greater than 1 cm⁻¹ [M2]. The
final resolution remains a measured `SV-01` choice: its line-shape sensitivity
shall contribute less than the allocated reference-resolution uncertainty.

### 8.3 Wavenumber-axis check

Use the FTIR laboratory's current, independent wavenumber performance check.
Polystyrene is an established IR wavelength/wavenumber standard; NIST SRM 1921
provides selected bands and uncertainties [W1, W2], and ASTM E1421 describes
FT-MIR performance tests [W3]. The available campaign polystyrene insert is not
itself a NIST-certified SRM, so it cannot inherit the SRM certificate values.
Record the exact standard identity and uncertainty actually used by the FTIR
facility.

### 8.4 Preprocessing and exports

- Preserve the immutable native export and an unaltered absorbance-versus-
  wavenumber export.
- Produce the canonical notebook CSV with exactly
  `Wavenumber_cm-1,Absorbance` [N1]. Wavenumber shall be monotonically ordered,
  with units and direction recorded.
- Do not smooth, peak-pick, baseline-flatten, normalize, interpolate, splice,
  or atmospheric-correct silently. Preserve raw and each derived stage with a
  method/version record.
- The primary feature fit uses a Gaussian plus sloping baseline. Any component
  decomposition or alternate baseline is a predeclared sensitivity analysis,
  not a replacement chosen on fit quality.
- Thickness may be recorded observationally but shall not enter the primary
  position/shape comparison.

## 9. QCL geometry, detectors, and reference plane

### 9.1 Optical geometry

Use the final `OG-01` sample-plane geometry. The record shall identify:

- MIRcat-QT-Z-2100 serial `10524`, installed module and accepted spectral
  range, laser/SDK versions, and accepted polarization basis;
- source reference plane, sample plane, incidence angle, beam centroid,
  footprint convention, aperture, mount, all optics/pickoffs/attenuators, beam
  dump, shutter/block state, and reproducible fiducials;
- the optical element that creates sample/reference branches, each branch
  path, and the exact sample and reference detector identities;
- Sample detector to HF2LI Sample input and Reference detector to HF2LI
  Reference input, preserving the installed assignments; and
- the coupon face/orientation/site mapping to the paired FTIR record.

Do not realign on the height, width, center, or residual of the Mylar band.
Alignment shall use `OG-01` fiducials and sample-independent power/geometry
checks. Beam-placement adjustments after the first Mylar spectrum require a
new configuration ID and investigation; they cannot be optimized against the
reference spectrum.

### 9.2 Detector requirements

The recorded Sample chain is VIGO `SIP-DC-250M` serial `445160800` with
`PVM-10.6-1x1` detector serial `16023` [R6]. The installed replacement
Reference chain is VIGO `SIP-DC-250M` serial `445161066` with
`PVM-10.6-1x1` detector serial `21834`, recorded on 2026-08-17. Its identity
gate is resolved; DET-01 through DET-04 performance qualification remains.

The PVM-10.6 family covers 2–13 µm and the SIP amplifier family provides a
50 Ω output; the exact detector/amplifier response, bandwidth, gain, polarity,
and relative timing must come from `DET-02`, not a family-data-sheet
assumption [M3, M4]. The manufacturer family ratings and the current package
PDF are safety/envelope sources only.

Both channels shall be acquired simultaneously. Record detector power-supply
IDs/status, coupling, termination, HF2LI ranges, clipping flags, phase, dark
offsets, and temperature/RH observations. Any change of detector, amplifier,
gain, range, cable, optic, or branch alignment invalidates the relevant
`DET-02`/`DET-04` link until reviewed.

The primary detector record is continuous HF2LI Sample/Reference/full-DIO
streaming, not a triggered PicoScope block. Its pretrigger equivalent is the
measured prepad acquired before enabling the accepted T660-2 pulse outputs; its
record length is the measured prepad plus the complete scan and transition plus
the measured postpad. There is no scope-style detector pretrigger, fixed record
length, or waveform averaging in the primary spectrum. Preserve the individual
HF2 samples and individual scan records; select Sample/Reference and DIO sample
rates only from `HF-01`, `MD-01`, and `HF-02` as specified in Section 11.

### 9.3 Dual-channel normalization

For time-matched Sample `S(t)` and Reference `R(t)`, use the canonical and
campaign-approved ratio-of-ratios:

```text
A(nu) = -log10[(S/R)_sample(nu) / (S/R)_background(nu)]
```

where background is the bracketing empty-mount measurement evaluated with the
frozen interpolation rule. Propagate Sample/Reference covariance and the
`DET-04` wavelength-dependent balance covariance. Do not assume a 50/50 split
and do not scale a channel to make Mylar agree with FTIR.

Before forming the ratio, align both channels on the common HF2 device time and
apply only the promoted `DET-02` relative-delay correction. Use the intersection
of the Sample and Reference usable windows after transition and filter settling;
never normalize one channel with samples from a different effective time
window. Propagate the residual delay as both a spectral-axis term
(`scan_speed * residual_delay`) and a ratio error on sloping signals. `DET-02`
and `AR-01` shall show that both effects remain inside their `CH-00` allocations.

The raw `S`, `R`, `X`, `Y`, DIO bits, device timestamps, host timestamps, and
readbacks shall remain retained. A raw-ratio versus corrected-ratio audit is a
mandatory deliverable.

## 10. Controls and experimental design

### 10.1 Mandatory controls

| Control | Timing | Decision use |
|---|---|---|
| Safe-idle readback | start, every abort, and final restoration | Proves outputs/emission returned to the reviewed safe state. |
| Detector dark / emission-off | before optical acquisition and after any range change | Apply `DET-01` dark and saturation gates; do not subtract an unqualified dark ad hoc. |
| Empty mount / no sample | bracket every sample/remount block | Supplies `(S0/R0)` and detects background drift. |
| Blocked sample and blocked reference branch | at configuration entry and after optical-path change | Detects cross-talk, wrong channel, and stray illumination. |
| Fixed-wavenumber stability point | before and after each scan block using a predeclared nonfeature point | Detects source/detector drift without tuning on Mylar. Point comes from the frozen window, not observed residuals. |
| Independent polystyrene holdout | immediately before unlock and after the final Mylar block | Detects correction drift; never refits. |
| Repeat scan, both directions | at least the campaign minimum of three accepted scans per direction [R9] | Estimates short-term repeatability and hysteresis. |
| Repeat position | revisit a fiducial site without remount | Separates short-term revisit variation. Count is frozen from the heterogeneity pilot. |
| Repeat mount | remove and reinstall with frozen fiducials | Estimates placement/mount variation. Count is frozen from the heterogeneity pilot. |
| Orthogonal specimen orientation | paired matched FTIR/QCL basis when allowed by the claim grid | Tests known PET anisotropy; it is a separate stratum, not pooled blindly. |
| Face reversal with MD basis preserved | diagnostic on a designated coupon | Detects mounting/face sensitivity without changing the primary reference. |

### 10.2 Randomization and blocking

Treat coupon/remount block and time block as nuisance factors. Within each
block, counterbalance scan direction and specimen orientation; randomize the
order of coupon/site combinations using a recorded software RNG algorithm,
version, and seed. Generate and freeze `schedule.csv` before the first primary
Mylar scan. This follows the NIST principle of blocking controlled nuisance
factors and randomizing remaining order [S3].

The schedule shall keep every sample spectrum paired with an adjacent empty-
mount bracket and shall not randomize safety ordering. Deviations, repeats,
and recovery acquisitions append new rows; they never overwrite the planned
or attempted row.

### 10.3 Repeat-day evidence

`SV-02` establishes within-configuration validation. A repeat-day claim
requires `RP-01`, whose campaign design calls for at least three independent
day/configuration realizations [R7]. For the minimal thesis path, report
repeat-day work as out of scope unless it is completed under `RP-01`; do not
rename same-day remounts as day reproducibility.

## 11. Scan, integration, and timing requirements

### 11.1 Final-parameter selection rules

The production values are imported values, not choices made in `SV-02`:

| Parameter | Exact selection rule before recipe generation |
|---|---|
| QCL module/range | `CH-00` window intersected with the promoted `SP-02` validity range and `QB-01` usable module range; it must include the predeclared feature and measured baseline shoulders. |
| Acquisition mode and spectral step | Use the promoted `MSW-01` continuous-sweep mode; there is no programmed wavelength step. Native sample spacing within an accepted constant-speed active segment is `scan_speed / HF2_output_rate`, while the reporting grid comes from the frozen forward-model plan. `SP-02`/`AR-01` simulations shall show that sampling, filter correlation, and interpolation fit inside their allocations. A later change to step tuning requires a revised reviewed procedure. |
| Scan direction/order | Both directions under the `MSW-01` direction definition; order counterbalanced in `schedule.csv`. |
| Scan speed | Fastest `MSW-01`/`AR-01` accepted speed whose measured lock-in shift, broadening, and direction hysteresis remain within their `CH-00` allocations. |
| Marker interval/width | Promoted `MSW-01` values whose marker count, jitter, DIO pulse sampling, and interpolation uncertainty meet the axis allocation throughout each active segment. |
| QCL pulse rate/width/duty | Promoted `QB-01` operating point for the installed module, cooling state, power envelope, and detector linearity. It must not be inferred from generic maximum ratings. |
| MIRcat trigger latency | Import the `QB-01` measured distribution from T660-2 CHB electrical edge to optical pulse and the `MSW-01` distribution from start command/process trigger to pin-2 active. Compensate a fixed latency only if the promoted model requires it; propagate residual jitter and segment spectra from DIO markers rather than host-command time. |
| T660 synchronization | T660-2 CHA and CHB use the same promoted repetition source. Import each enabled channel's period/rate, delay, width, polarity, and termination plus the measured CHB-minus-CHA relationship from `HF-01`/`QB-01`; require HF2 external-reference lock and the accepted phase relationship before emission. T660-2 CHC/CHD and every T660-1 channel remain disabled unless a separately promoted design explicitly changes that state. |
| HF2LI time constant/order | Promoted `AR-01` pair meeting noise and dynamic-distortion allocations at the selected scan speed. |
| Dwell/integration | A continuous sweep has no per-wavenumber dwell. Effective integration and memory are set by the promoted HF2 filter response; exclude transitions for the promoted order-specific 99 % settling interval [M5] and validate shift/broadening in `AR-01`. Do not convert correlated HF2 samples into independent dwell replicates. |
| HF2LI output rate | Promoted `HF-01`/`HF-02` rate that samples the accepted filter bandwidth and preserves simultaneous streams without sample loss. The HF2 manual notes a common rate near eight times filter bandwidth [M5]. |
| DIO rate | Promoted `MD-01`/`MSW-01` rate resolving every accepted marker and active/direction transition with count reconciliation. |
| Stream duration | Measured prepad for external-reference lock and filter settling + complete scan/transition duration + measured postpad; all terms come from `HF-01`, `HF-02`, `MSW-01`, `QB-01`, and `AR-01`. |
| Tuning-transition exclusion | Exclude every pin-2-low transition gap and the measured `QB-01`/`AR-01` settling interval after active status returns; never bridge an unmodeled gap or mix pre- and post-transition response. |
| Background/sample recovery | Long enough that the bracket stability statistic and fixed-point drift return within their predeclared control limits; selected in `AR-01`/the pilot, not by visual waiting. |
| Scan count | At least three accepted scans per direction [R9], increased prospectively if the measured uncertainty pilot requires it. |
| Spectral averaging | No averaging across directions, coupons, positions, remounts, or failed controls. Average only equivalent accepted scans within a declared cell after preserving individual results and covariance. |

### 11.2 Candidate values are not production values

The current design-only recipe contains 2050→1650 cm⁻¹, 40 cm⁻¹/s,
5 cm⁻¹ markers of 500 µs, 2 MHz external laser/reference pulses of 150 ns,
HF2 detector demodulators at 2 kSa/s with 1 ms fourth-order filters, DIO at
5 kSa/s, and a 30 s stream [R4, R11, R12]. These values are evidence for what
must be qualified, not authorization to run.

They imply a nominal 10 s active traversal, approximately 125 ms between
markers, 30 % electrical pulse duty, a fourth-order 99 % lock-in settling time
of 10 time constants (10 ms for the candidate), and 0.4 cm⁻¹ of scan travel
during that settling interval. The calculations follow directly from the
candidate settings and the HF2 settling table [M5].

Those implications expose unresolved gates:

- the MIRcat-QT family data sheet lists standard duty up to 20 %, custom up to
  30 %, while the older generic user manual lists a 10 % maximum [M2, M6];
- exact limits are factory/module dependent, so `QB-01` and installed readbacks
  must resolve pulse rate, width, duty, cooling, and power;
- the candidate lock-in dynamics could shift or broaden the carbonyl feature,
  so `AR-01` must accept or replace them; and
- `MD-01`, `MSW-01`, and `HF-02` must accept the DIO and streaming behavior.

### 11.3 Lock-in settling model

For an `n`-stage low-pass filter with stage time constant `tau`, use the
canonical notebook/HF2 step response:

```text
g(t) = 1 - exp(-t/tau) * sum[k=0..n-1] (t/tau)^k / k!
```

The HF2 manual gives 99 % settling multipliers of 4.6, 6.6, 8.4, 10.0,
11.6, 13.1, 14.6, and 16.0 time constants for orders one through eight,
respectively, and NEPBW factors from 0.2500/tau to 0.0524/tau [M5]. Use the
multiplier for the promoted order. The usable normalization window at every
wavenumber shall exclude measured transition/settling intervals defined by
`AR-01`; it may not mix different effective time windows for Sample and
Reference.

### 11.4 Detailed routing and relationships

The installed timing topology to preserve is:

- `T660-2 CHA → HF2LI DIO0 external reference`;
- `T660-2 CHB → MIRcat TRIG IN`;
- `T660-2 CHC → HF2LI DIO1 DAQ trigger` physically, but leave it disabled
  unless the promoted HF configuration explicitly requires it;
- `T660-2 CHD → T660-1 TRIG IN` physically, but leave it disabled for this
  pump-off validation;
- `T660-1 CHC → MIRcat DB9 pin 4 process trigger` physically, but leave it
  disabled when the promoted sweep uses internal process triggering; and
- MIRcat DB9 pin 1 direction, pin 2 sweep-active/tuned, and pin 3 wavelength
  marker mapped by `MD-01` to the full DIO word.

Installed-unit correspondence states pin 1 maps scan direction, pin 2 is high
during a channel's active sweep and low in transitions, pin 3 is the wavelength
marker, and pin 4 process trigger is active low; it reports roughly 1–100 ms as
sufficient for the installed process-trigger input [R14]. The older generic
manual says 250–500 ms for step/multispectral process triggering [M6]. For a
continuous sweep, use internal process triggering unless the accepted
`PT-01`/`MSW-01` bundle explicitly selects external process triggering. If
external is selected, the accepted installed-unit measurement supersedes both
generic ranges.

The generated recipe shall tabulate both T660 units and every channel A–D,
including disabled channels, with trigger source, enable state, destination,
rate/period, delay relative to that source, width, polarity, source termination,
expected load termination, and promoted evidence ID. Readback agreement is
required before the stream starts. For the pump-off Mylar topology, only the
reviewed T660-2 HF2-reference and MIRcat-trigger channels may be enabled.

All T660 outputs use the accepted polarity and termination readbacks. The
candidate configuration uses positive 150 ns, 50 Ω-source pulses on the
active T660-2 channels [R11]. The T660 manual specifies selectable 50 Ω source
termination, +2.5 V into a 50 Ω load, 10 ps programming resolution, and a
16 MHz maximum output repetition envelope [M7]; these are capability limits,
not proof that the downstream load or chosen recipe is correct.

`TRIGger:SHOTs` only clears/queries the elapsed-shot counter and does not limit
shots [M8, R15]. The workflow must explicitly set trigger source `OFF`/stop at
closeout; shot-counter reconciliation is diagnostic evidence, not the stop
mechanism.

### 11.5 PicoScope role and settings

The PicoScope is not a primary spectral detector and shall not be averaged into
the Mylar spectrum. Existing accepted timing-path measurements used PicoScope
5244D serial `10261` (`10261/0071`) in 8-bit DC ±10 V mode, 2 ns sample
interval, 100000 total samples, 1000 pretrigger samples, rising Channel A
trigger, zero trigger delay, and 100 accepted individual captures [R16, R17]. The
5244D data sheet supports up to 1 GS/s in 8-bit mode, simultaneous enabled-
channel sampling, external/analog triggering, and up to 100 % pretrigger
capture [M9].

For `SV-02`:

- import promoted `MSW-01`/timing results; do not repeat calibration merely
  because the Mylar run begins;
- use the PicoScope only for a reviewed electrical diagnostic if a timing
  cable, termination, trigger mode, pulse rate/width, or route has changed;
- when such a diagnostic is required, its source, channels, ranges, trigger
  level/edge, pretrigger, record length, sample interval, and number of
  individual captures shall be selected from the changed signal's accepted
  pulse width, period, and uncertainty target, then reviewed as a new
  calibration/diagnostic action outside `SV-02`;
- retain individual waveforms; do not hide jitter or missing pulses with scope
  waveform averaging; and
- if manufacturer amplitude/timebase accuracy is invoked, observe the
  PicoScope data sheet's one-hour warm-up condition [M9].

### 11.6 Warm-up and stability gates

- MIRcat: allow at least the generic manual's 15 min thermal-equilibrium
  period and, more importantly, require armed status, interlock/key true, all
  TECs at set temperature, and `QB-01` stability inside its control limits
  [M6, M10]. The family data sheet's specifications are stated after a 10 min
  warm-up [M2]; the longer generic interval is the conservative starting gate,
  while `QB-01` decides the installed value. The SDK guide's approximately
  4 Hz status-query guidance is implemented as at least 300 ms between repeated
  queries [M10]; host polling is never used as a spectral timestamp.
- HF2LI: if manufacturer analog specifications are invoked, use its 30 min
  warm-up condition and verify external-reference/PLL lock and no status flags
  [M5].
- detectors/amplifiers: remain within the exact installed-component operating
  envelope. The current VIGO family package lists amplifier operation from
  10–30 °C [M4]; `DET-02`/`QB-01` decide the usable laboratory envelope.
- PicoScope: the one-hour accuracy warm-up applies only if the diagnostic is
  used [M9].
- environmental logger values remain observational. A value outside an
  accepted instrument envelope is an abort condition; it does not become a
  traceable correction.

### 11.7 Safe startup, acquisition, stop, and restoration order

The generated workflow shall implement and log this order:

1. Establish the laboratory laser-controlled area, PPE, enclosure/beam dumps,
   approved shutter/block state, and operator authorization. Keep pump,
   Nd:YAG, OPO, and every T660-1 output disabled and optically blocked for the
   entire Mylar experiment.
2. Apply `safe_idle.yaml`; verify both T660 trigger sources off, every channel
   disabled, MIRcat emission off, no scan active, and MIRcat disarmed. Stop if
   any readback disagrees.
3. Verify physical wiring, detector identities/power, optical branch and mount
   IDs, shutter/block, interlock, key, beam dump, and restoration baseline.
4. Power and warm instruments with emission off. Connect to MIRcat, verify
   model/serial/SDK, cancel manual tune mode, arm, and wait for every TEC to
   report at set temperature. Arming does not authorize emission.
5. Configure HF2LI from the accepted `HF-01`/`AR-01` configuration. Verify
   Sample/Reference assignments, external reference, demodulators, rates,
   time constants/orders, phases, ranges, full-DIO subscription, and loss
   flags.
6. With T660 triggering still off, program and read back the accepted T660-2
   pulse channels, polarity, termination, delays and widths. T660-1 remains
   entirely off. Configure the MIRcat sweep, pulse mode, marker settings, and
   process-trigger mode with emission off.
7. Start native HF2LI Sample/Reference/full-DIO streaming and record the
   measured prepad. Enable only the accepted T660-2 reference/laser-trigger
   channels. Before scan start the MIRcat is not emitting, so the external
   laser triggers shall produce no optical output.
8. Verify stable HF2LI external-reference lock, legal input ranges, no clipping
   or loss, and expected DIO idle state. Abort to safe idle on failure.
9. With the reviewed sample/background state installed and the beam path safe,
   open only the required shutter/block, start the single MIRcat sweep, and
   verify emission/scan-active/direction/marker readbacks. Never use an
   infinite scan count.
10. Acquire through the complete active segment and transition. Reconcile
    marker count/order and retain low active-gate intervals raw while excluding
    them from spectral estimation as defined by `MSW-01`.
11. At normal scan end or any anomaly, first stop T660-2 triggering so no new
    laser pulses can be requested, then command MIRcat stop-scan and emission
    off, verify both, and retain the required HF2 postpad before stopping the
    stream.
12. Close the shutter/replace the block before changing background/sample,
    coupon, face, orientation, or site. Reapply safe idle if wiring, range,
    trigger mode, or optical path changes.
13. At block/end-of-day closeout: T660 sources off and all channels disabled;
    MIRcat scan stopped, emission off, manual mode canceled, and disarmed;
    pump/OPO disabled; shutter/block safe; detector power handled per its SOP;
    final readbacks recorded; and the complete original wiring/optics/mount
    state restored and photographed/confirmed.

On software exception, operator stop, interlock event, unexpected emission,
lost communication, clipping, missing DIO, sample motion, or cooling fault,
execute the same stop path immediately and preserve partial evidence.

## 12. Execution phases

### Phase A — requirements and embargo closure

**Entry:** `CH-00`, `SP-01`, sample identity, authority table, correction
partition, analysis model, tolerances, and data locations reviewed.  
**Actions:** freeze claims, windows, features, counts-selection rule,
randomization method, controls, exclusions, and embargo roles.  
**Deliverables:** signed/reviewed requirement record, feature table,
`schedule_draft.csv`, analysis/version record, access plan.  
**Accept:** every numeric starting value is sourced or explicitly pending a
named measured input; no Mylar spectral value has been opened.  
**Abort:** missing claim tolerance, ambiguous sample identity, or access to
Mylar before correction freeze.  
**Restore:** no hardware action is permitted in this phase.

### Phase B — prerequisite bundle audit

**Entry:** Phase A accepted.  
**Actions:** verify every bundle in Section 4, validity envelope, installed
configuration, and quantity ID; verify reference-detector identity.  
**Deliverables:** `calibration_links.csv`, dependency audit, accepted settings
table, unresolved-item decision.  
**Accept:** all mandatory quantities are accepted for the exact range,
direction, power, detector, geometry, environment, and date/configuration.  
**Abort:** any missing/expired/out-of-envelope dependency.  
**Restore:** no hardware action unless separately authorized prerequisite work.

### Phase C — `SV-01` FTIR acquisition/registration

**Entry:** approved FTIR method, matched polarizer/geometry, labeled coupons,
and embargo custodian.  
**Actions:** acquire bracketed backgrounds and specimen spectra; preserve
native exports; perform the independent axis/performance check; register but
seal Mylar spectra.  
**Deliverables:** native FTIR artifacts, normalized canonical CSV, full
metadata, reference-axis and fit uncertainty plan, custody record.  
**Accept:** matched geometry is demonstrated, no invalid saturation/drift,
and the FTIR resolution/precision allocation is met.  
**Abort:** polarization mismatch without an approved sensitivity path,
unrecorded orientation/site, failed FTIR performance check, or damaged sample.  
**Restore:** coupon stored in its identified container without changing marks.

### Phase D — polystyrene alignment and freeze

**Entry:** accepted `SP-02`, alignment/holdout assignment, approved correction
form, and no Mylar access.  
**Actions:** fit first-order correction by default on alignment data only;
allow a higher order only under the residual/uncertainty criterion frozen in
`CH-00`; write covariance and validity; evaluate holdout without refit.  
**Deliverables:** `correction_freeze.json`, coefficients/covariance/residuals,
holdout result, access log, proof of Mylar exclusion.  
**Accept:** holdout and model diagnostics meet their predeclared criteria.  
**Abort:** holdout failure, invalid extrapolation, unstable coefficients, or
evidence that Mylar/biological data influenced the fit.  
**Restore:** normal safe-idle and complete polystyrene closeout.

### Phase E — Mylar pilot, counts freeze, and schedule freeze

**Entry:** Phase D frozen; Mylar unlock logged; valid FTIR references.  
**Actions:** run only the predeclared heterogeneity pilot, estimate nested
variance, freeze coupon/site/remount counts, and generate balanced randomized
`schedule.csv`.  
**Deliverables:** pilot records, variance components, prospective count
calculation, final schedule and RNG provenance.  
**Accept:** required precision is feasible inside the approved exposure and
resource limits.  
**Abort:** heterogeneity, damage, or required count makes the claim infeasible;
narrow the claim or revise the schedule through review, not by discarding the
pilot.  
**Restore:** safe idle and stored coupons between blocks.

### Phase F — primary QCL Mylar acquisition

**Entry:** all prior phases accepted; final recipe generated from promoted
settings; operator/safety review; configuration and sample state verified.  
**Actions:** acquire all controls and the frozen schedule using the startup,
scan, stop, background switching, and restoration order in Section 11.  
**Deliverables:** native Sample/Reference/full-DIO streams, device readbacks,
commands, backgrounds, controls, sample/mount records, exclusions, and final
restoration.  
**Accept:** all scheduled cells complete or formally excluded; every accepted
active segment has valid direction and marker anchors, simultaneous channels,
no prohibited clipping/loss, and valid brackets.  
**Abort:** any safety fault; unexpected emission; interlock/cooling/communication
fault; sample slip/damage; invalid detector range; missing marker anchors;
unreconciled marker count; sample/packet loss; invalid background denominator;
or operation outside a promoted validity envelope.  
**Restore:** mandatory safe idle after every abort and at phase close.

### Phase G — locked analysis and decision

**Entry:** Phase F closed; analysis code/version frozen; correction remains
read-only.  
**Actions:** construct axes, normalize, forward-model FTIR, fit features,
propagate uncertainty, inspect residuals, run sensitivity analyses, and apply
Section 3 criteria.  
**Deliverables:** all tables/figures, uncertainty budget, pass/limitation
decision, raw-versus-normalized audit, and proof of no refit.  
**Accept:** reproducible outputs from retained inputs and complete retention
audit.  
**Abort analysis:** mismatched sample/orientation/geometry, untraceable
preprocessing, correction outside validity, nonidentifiable feature, or an
unresolved data-contract violation. Preserve the result as incomplete.  
**Restore:** analysis-only; no hardware action.

### Phase H — closeout/promotion decision

**Entry:** Phase G complete and independently reviewed.  
**Actions:** state exact validated scope, limitations, unresolved anomalies,
and downstream permissions.  
**Deliverables:** `final_report.md`, retention audit, restoration confirmation,
and campaign approval record.  
**Accept:** promotion occurs only through the campaign's explicit approval
process. A report is not self-promoting.  
**Failure path:** open a cause-coded investigation; do not refit on Mylar.

## 13. Spectral construction and comparison

### 13.1 Trigger-derived axis

For each active segment:

1. decode full DIO using the accepted `MD-01` mapping;
2. define direction from pin 1 and active interval from pin 2;
3. pair pin 3 marker pulses with their programmed target wavenumbers in order;
4. require the `MSW-01` minimum anchor count and exact count reconciliation;
5. interpolate only by the accepted `SP-02`/`MSW-01` method inside the active
   segment; never bridge an unmodeled transition gap; and
6. apply the frozen polystyrene correction and covariance. Do not extrapolate
   beyond its stated validity range.

Retain MIRcat actual/tuned readbacks as diagnostics. Marker-derived and
readback axes shall remain separately identifiable.

### 13.2 FTIR-to-QCL forward model

Follow the canonical notebook [N1]:

1. convert high-resolution FTIR absorbance to transmission,
   `T_FTIR = 10^(-A_FTIR)`;
2. convolve transmission with the measured QCL spectral kernel from `QB-01`
   and the declared treatment of the FTIR instrument line shape/apodization;
3. resample at the corrected QCL axis using the accepted sampling/interpolation
   rule;
4. apply any measured `AR-01` dynamic response required for the chosen scan
   direction/speed, without fitting its parameters to Mylar;
5. convert the predicted transmission back to absorbance; and
6. fit predicted and measured spectra with the identical frozen feature and
   baseline model.

Convolution in transmission space is mandatory; a weak-absorbance linear
approximation is not the primary model. No deconvolution of the measured QCL
spectrum is allowed in the primary result.

### 13.3 Position and line shape

Use a Gaussian feature with a linear/sloping baseline as the primary model.
For each coupon/site/orientation/direction/scan report:

- corrected center and covariance;
- FWHM and covariance;
- integrated area and height as diagnostic fit parameters only, not absolute-
  absorbance validation;
- observed QCL FWHM, FTIR FWHM, forward-predicted FWHM, and the notebook's
  effective-resolution calculation;
- center/FWHM residuals and standardized residuals;
- normalized-shape RMSE, mean residual, maximum absolute residual, and Pearson
  correlation over the frozen window;
- repeatability, remount/position/coupon variance, forward/reverse difference,
  and elapsed-time drift; and
- SNR and baseline/fringe diagnostics with the exact baseline region and
  estimator recorded.

For shape comparison, subtract only the fitted sloping baseline and normalize
both measured and predicted feature profiles to unit area over the frozen
window. This removes absolute absorbance from the claim while preserving
center, width, asymmetry, and residual structure. Peak-height normalization is
a sensitivity analysis, not a replacement selected after seeing the result.

If a multi-component carbonyl fit was predeclared, require that the forward-
convolved components remain identifiable under simulation and report their
full covariance. Otherwise report the single envelope; do not create apparent
accuracy by overfitting unresolved subbands.

### 13.4 Resolution treatment

Use the notebook convention for a Gaussian effective QCL contribution:

```text
FWHM_QCL_instrument = sqrt(max(0,
    FWHM_QCL_observed^2 - FWHM_FTIR_observed^2 + FWHM_FTIR_instrument^2))
```

and include sampling standard uncertainty from the accepted axis spacing,
calibration/correction uncertainty, FTIR resolution/ILS, QCL kernel
uncertainty, fit covariance, and `AR-01` dynamic broadening. The equation is a
model-based derived result, not a manufacturer linewidth measurement.

### 13.5 Residual and fringe inspection

Plot residual versus corrected wavenumber, direction, elapsed time, coupon,
site, and fitted signal. Inspect coherent shoulders, derivative-shaped
residuals, direction reversal, baseline curvature, periodic structure, and
heteroscedasticity. Report residual RMS and peak-to-peak periodic amplitude
using the frozen estimator. A Fourier/autocorrelation diagnostic may report an
observed periodic spacing, but it shall not infer film thickness or fit a
quantitative etalon model.

## 14. Uncertainty and reproducibility

### 14.1 Required uncertainty components

The position/FWHM/shape budget shall include, as applicable:

- specimen-matched FTIR axis check, instrument resolution/line shape,
  apodization sensitivity, background drift, feature fit, and repeat block;
- promoted `SP-02` axis and frozen polystyrene correction coefficients with
  full covariance and validity-range behavior;
- marker timing/interpolation, direction, module/crossover, and QCL kernel;
- HF2 Sample/Reference relative timestamps, loss/gap audit, time constant,
  filter order, sample rate, and `AR-01` dynamic shift/broadening;
- detector dark, nonlinearity/range, separate response, `DET-04` balance,
  background interpolation, and Sample/Reference covariance;
- sample coupon, position, remount, orientation, face, beam placement,
  incidence, and polarization mismatch;
- repeat scan, direction hysteresis, elapsed-time drift, and observational
  environment sensitivity; and
- software numerical precision, interpolation, baseline/window, and fit-model
  sensitivity.

Do not double count a component already represented in a promoted covariance
matrix. Preserve correlations between correction coefficients, between Sample
and Reference, and among repeated points sharing a background or coupon.

### 14.2 Propagation

- Use analytical covariance propagation where the model is locally linear and
  diagnostics support it [U1].
- Use JCGM 101 Monte Carlo propagation for nonlinear transformations,
  constrained widths, ratio/log transforms, correlated correction
  coefficients, and forward-model uncertainty [U2].
- Use a nested mixed model or cluster bootstrap at the highest independent
  experimental unit; do not resample spectral points as though they were
  independent replicates. NIST describes nested variance components and
  bootstrap uncertainty use [S2, S4].
- Report estimate, standard uncertainty, degrees-of-freedom/coverage method,
  and 95 % interval. Preserve the Monte Carlo seed, distribution choices,
  correlation matrix, draws count selection rule, and convergence diagnostic.

The Monte Carlo draw count is selected by convergence: increase it until the
reported interval endpoints change by less than the `CH-00` numerical
reporting allocation in independent seeded runs. It is not selected by whether
the interval crosses an acceptance threshold.

### 14.3 Exclusions and outliers

No record may be excluded because its center, width, or residual is
inconvenient. Primary technical exclusions are limited to frozen cause codes:

- safety/interlock/cooling or unexpected-emission event;
- wrong/unverified sample, face, orientation, site, mount, detector, or
  configuration;
- clipping/nonlinearity or invalid dark/background denominator;
- missing, duplicate, reordered, or unreconciled markers;
- HF2 sample/packet loss, reorder, duplicate, timestamp discontinuity, or
  missing channel/DIO stream beyond the promoted rule;
- scan outside the correction, detector, power, geometry, or filter validity
  envelope;
- sample slip/damage/contamination or aperture-edge illumination;
- predeclared fit nonconvergence/identifiability failure; or
- corrupted/unreadable artifact with documented producer/storage evidence.

Retain excluded and aborted attempts, raw data, reason, operator, UTC time, and
the rule invoked. Robust summaries may be secondary analyses, but they do not
erase the primary result.

## 15. Failure investigation without refitting

If Mylar fails, freeze all current correction and analysis artifacts and
classify the evidence before any new acquisition:

1. **Reference comparability:** FTIR axis, polarization, orientation, site,
   aperture, background, resolution, preprocessing, or sample change.
2. **Axis acquisition:** marker count/order, active segmentation, interpolation,
   module/crossover, direction, correction validity, or polystyrene holdout.
3. **Dynamic response:** time constant/order, scan speed, tuning delay,
   direction-dependent shift/broadening, or stream alignment.
4. **Optical/detector:** branch identity, clipping, dark, `DET-04` drift,
   sample/reference timing, placement, or polarization.
5. **Material:** within/between-coupon heterogeneity, remount sensitivity,
   damage, contamination, or PET anisotropy.
6. **Model:** QCL kernel, FTIR ILS, baseline, component identifiability, or
   understated covariance.

Permitted outcomes are: correct a documented processing defect and rerun the
unchanged locked analysis; repeat under a newly reviewed configuration while
preserving the failed configuration; perform an independently authorized
calibration investigation; or narrow/withdraw the thesis claim. Mylar remains
excluded from any correction fit in every outcome.

## 16. Data products and retention contract

Create the `SV-02` phase directory only when execution is separately
authorized. It shall contain the repository-required top-level products
[R3, R18]:

```text
phase_manifest.json
acquisition_index.csv
conditions.csv
measurements.csv
artifacts.csv
exclusions.csv
calibration_links.csv
command_log.txt
final_report.md
restoration_confirmation.json
raw/
analysis/
figures/
tables/
```

Required identifiers on every applicable row are `campaign_id`, `phase_id`,
`phase_run_id`, `acquisition_id`, `configuration_id`,
`calibration_bundle_id`, `sample_id`, `device_id`, `component_id`, and
`operator_id` [R3]. Add `coupon_id`, `position_id`, `mount_id`,
`background_id`, `schedule_row_id`, `correction_id`, `ftir_reference_id`,
`direction_code`, and `replicate_id` for this phase.

Retain at minimum:

- native MIRcat readbacks and scan status; T660 commands/readbacks/shot counts;
  HF2 settings/snapshots, Sample/Reference/full-DIO native streams, status and
  loss flags; any Pico diagnostic waveforms; detector and environment records;
- all FTIR native exports, backgrounds, canonical CSVs, preprocessing records,
  coupon/site/orientation metadata, and custody/unlock logs;
- `sample_registry.csv`, `feature_authority.csv`, `schedule.csv`,
  `correction_freeze.json`, `mylar_unlock_log.json`,
  `background_pairs.csv`, `marker_axis.csv`, `stream_gap_audit.csv`,
  `normalization_audit.csv`, `peak_fits.csv`, `shape_metrics.csv`,
  `variance_components.csv`, `uncertainty_budget.csv`,
  `control_results.csv`, and `selection_decisions.csv`;
- software/module/analysis/schema versions, function form and coefficients,
  covariance matrices, RNG seeds, relative input/output paths, and UTC
  execution times; and
- every attempted, preview, control, aborted, rejected, excluded, superseded,
  and accepted record.

`artifacts.csv` shall use repository-relative paths and include byte size,
creation/record UTC times, producer, source acquisition IDs, type, state, and
retention decision. Informational hashes may be present but cannot gate data.
No file is overwritten; revisions get new artifact/acquisition IDs and an
explicit supersession link.

The retention audit shall reconcile schedule rows, acquisition attempts,
native files, table rows, exclusion reasons, calibration links, figures,
reported values, correction freeze/unlock order, and restoration evidence.

## 17. Dependency map and unnecessary work

```text
requirements brief + P0 decisions/inventory
        |
        +--> HF-01 --> MD-01 --> MSW-01 --> HF-02 ---+
        |                                            |
        +--> ATT-01 --> DET-02 --> DET-04 -----------+
        |                  ^                         |
        +--> DET-01 -------+                         |
        |                                            |
        +--> SP-01 --> SP-02 ------------------------+
        |                                            |
        +--------------------------------------------+--> CH-00 claim/test-grid freeze
                                                            |
                         +----------------------------------+------------------+
                         |                                  |                  |
                         v                                  v                  v
                      QB-01 -----------------------------> OG-01            SV-01
                         |                                  |            sealed FTIR
                         +--> AR-01 <--- HF/DET chains -----+                  |
                         |                                  |                  |
                         +----------------+-----------------+------------------+
                                          |
                          SP-02 + DET-04 --+
                                          v
                             polystyrene fit/holdout/freeze
                                          |
                                          v
                                  Mylar unlock + pilot
                                          |
                                          v
                                  SV-02 primary validation
                                          |
                             +------------+------------+
                             v                         v
                     local thesis claim        RP-01 repeat-day claim
```

Pending measurements that can change the recipe are exactly: installed
reference-detector identity; detector ranges/relative timing; wavelength-
dependent balance and covariance; usable QCL module/range/power/pulse/cooling;
beam geometry/polarization/placement; marker timing/interpolation; HF stream
rates/loss limits; time constant/order/settling; scan speed/direction
broadening; FTIR resolution/polarization/heterogeneity; background recovery;
and the prospective replicate count.

The following campaign work is unnecessary for the mandatory Mylar position/
shape validation:

- supplemental post-promotion direct-355 phase `PB-01` and OPO-540 phase `PB-02`;
- pump–probe overlap `OV-01`;
- system temporal instrument response `IR-01`;
- biological sample preparation or biological spectra;
- platform sensitivity/noise claim phase `PF-01` (although `SV-02` reports its
  own local SNR and residual baseline diagnostics);
- direct pulse-energy distributions, energy meter work, or biological fluence;
- Mylar certificate procurement, film-thickness tolerance, absolute absorbance,
  and quantitative etalon modeling; and
- repeat-day `RP-01` unless a repeat-day claim is required by the thesis.

`QB-01` and the probe-only portion of `OG-01` remain necessary; disabling the
pump does not remove probe power, polarization, geometry, or detector-linearity
requirements.

## 18. Minimal thesis path and optional enhancements

### Mandatory minimal path

1. Close the `CH-00` local carbonyl-window claim and tolerances.
2. Complete/promote only the prerequisite probe-axis, DIO/stream, detector,
   balance, probe-source, geometry, and acquisition-response quantities in
   Sections 4 and 17.
3. Acquire/register matched-polarization specimen FTIR under `SV-01` and seal
   Mylar spectral values.
4. Fit and freeze the final polystyrene correction and pass the independent
   polystyrene holdout.
5. Unlock Mylar, run the small heterogeneity/count pilot, and freeze a balanced
   schedule that includes at least the campaign-required three scans per
   direction.
6. Acquire bracketed empty-mount controls and both QCL directions with pump,
   OPO, and T660-1 disabled.
7. Run the locked transmission-space forward model, uncertainty propagation,
   and decision; report the result as local to the tested carbonyl envelope and
   configuration.

This is the shortest scientifically defensible route because it preserves
independence and all quantitative dual-detector/axis dependencies while
excluding unrelated pump, temporal, biological, absolute-absorbance, and
repeat-day claims.

### Optional enhancements

- Additional independently cut coupons/sites to support roll-level material
  generalization after the prospective count rule.
- Both orthogonal polarization/orientation strata if not already mandatory for
  FTIR comparability.
- Additional PET bands only if a promoted QCL range covers them and they were
  frozen before unlock.
- `RP-01` independent day/configuration realizations for repeat-day claims.
- Extra baseline/fringe diagnostics, provided they do not infer thickness or
  alter the primary model.
- Independent analyst reproduction from retained inputs after closeout.

## 19. Readiness checklist

All boxes must be true before recipe generation:

- [ ] `CH-00` freezes the local claim, window, tolerances, and exposure policy.
- [ ] Mylar and polystyrene roles and the no-refit rule are in the approved
  protocol.
- [ ] Alignment/holdout assignments and the first-order/higher-order decision
  rule are frozen.
- [ ] `SP-02`, `HF-01`, `MD-01`, `MSW-01`, `HF-02`, `ATT-01`, `DET-01`,
  `DET-02`, `DET-04`, `QB-01`, `OG-01`, and `AR-01` supply accepted IDs and
  in-envelope quantities.
- [x] The installed reference detector/amplifier identities are recorded:
  VIGO SIP `445161066`, detector `21834`.
- [ ] `SV-01` provides matched coupon/site/orientation/polarization FTIR,
  native exports, canonical CSV, and reference uncertainty.
- [ ] FTIR Mylar data are sealed from the correction-fitting analyst.
- [ ] `correction_freeze.json` and the polystyrene holdout pass before
  `mylar_unlock_log.json`.
- [ ] Coupon/site/remount counts are frozen from the prospective measured
  heterogeneity rule.
- [ ] `schedule.csv`, RNG provenance, controls, exclusion codes, and analysis
  version are frozen.
- [ ] Exact QCL pulse/cooling limits resolve the generic-manual conflict and
  the candidate 30 % duty implication.
- [ ] Generated recipe contains a finite scan count and explicit safe startup,
  stop, exception, and restoration paths.
- [ ] Data-contract directories/tables/identifiers are prepared without an
  operational hash gate.
- [ ] Operator, laser-safety, configuration, and campaign approvals are
  documented.

### Current unresolved dependencies

| Dependency | Current evidence | Required closure | Can it change the procedure? |
|---|---|---|---|
| Reference detector identity | VIGO `SIP-DC-250M` serial `445161066`; `PVM-10.6-1x1` serial `21834` [R6] | identity complete; import into DET-01–04 records | Response, timing, range, and balance remain phase-measured. |
| Promoted spectral/DIO/stream bundles | relevant phases largely not executed/promoted | close `SP-02`, `HF-01`, `MD-01`, `MSW-01`, `HF-02` | Yes—axis, marker, rate, duration, segmentation. |
| Detector balance | `DET-04` pending | installed-path balance/covariance and drift rule | Yes—normalization and uncertainty. |
| QCL pulse/power/cooling | candidate settings conflict with generic duty limits | `QB-01` installed-module envelope and readbacks | Yes—rate, width, duty, power, warm-up. |
| Geometry/polarization | no accepted final sample-plane record | `OG-01`; matched FTIR/QCL polarizer basis | Yes—comparability and sample placement. |
| Acquisition dynamics | provisional 1 ms/order-four candidate only | `AR-01` accepted shift/broadening and dwell/scan envelope | Yes—speed, filters, usable windows. |
| FTIR reference | not yet registered in current evidence | `SV-01` native/CSV, axis/ILS, matched coupon and polarization | Yes—features, windows, uncertainty. |
| Coupon/site/remount counts | material heterogeneity unknown | post-freeze measured pilot and prospective calculation | Yes—schedule and claim breadth. |
| Thesis tolerances | not frozen | `CH-00` scientific-use thresholds | Yes—acceptance and precision targets. |
| Repeat-day claim | `RP-01` not executed | complete `RP-01` only if claimed | No for local validation; yes for repeat-day language. |

With the current evidence, the experiment is **not ready for execution**.

## 20. Parameter-to-source evidence table

| Parameter or rule | Recommended starting value/range or selection rule | Rationale | Source | Evidence class | Confidence / status |
|---|---|---|---|---|---|
| Material | SPEX/Cole-Parmer 3517 Mylar, nominal 0.25 mil (6 µm) | Matches physical inventory and current seller listing; thickness is identity only | [R6], [M1] | inventory + manufacturer | High identity; no lot/certificate/tolerance |
| Primary PET feature | specimen FTIR carbonyl envelope; literature main maximum 1715–1719 cm⁻¹ | Strong in accessible region but structure/orientation sensitive | [P1] | primary peer-reviewed | High band identity; specimen center pending `SV-01` |
| Blind substructure interval | 1685–1735 cm⁻¹ reported components | Prevents outcome-driven search and acknowledges polarization structure | [P2] | primary peer-reviewed | Moderate across PET types; primary endpoints pending FTIR baseline |
| Candidate QCL range | 1650–2050 cm⁻¹, design only | Contains carbonyl and baselines; current recipe is not approved | [R11] | repository candidate | Not executable; final pending `CH-00`/`SP-02`/`QB-01` |
| FTIR resolution start | 0.5 cm⁻¹ if supported; final by sensitivity allocation | High-resolution relative to generic ≤1 cm⁻¹ QCL linewidth; consistent with NIST calibration practice | [W1], [M2] | standards + manufacturer | Medium start; final pending `SV-01` |
| FTIR coadds | pilot-selected from successively larger independent blocks until center/FWHM/shape uncertainty meets allocation without drift | Avoids arbitrary scan count | [S1], [U1] | measurement/statistics | Final pending measured `SV-01` result |
| FTIR polarization | matched QCL electric-field basis or both orthogonal bases | PET band profiles show native/induced anisotropy | [P1], [P2], [M2] | peer-reviewed + manufacturer | High requirement; hardware availability unresolved |
| Mylar QCL scans | at least three accepted scans per direction; more if prospective uncertainty requires | Campaign minimum and repeatability estimate | [R9] | campaign requirement | High minimum; final count pending pilot |
| Coupons/sites/remounts | prospective nested-variance count after post-freeze pilot | Claim breadth and uncertainty depend on material/placement heterogeneity | [S1], [S2], [S3] | authoritative statistics | Pending measured result |
| Scan speed candidate | 40 cm⁻¹/s, design only; final fastest accepted under AR distortion limits | Current timing qualification point; dynamics must be measured | [R4], [R11], [R7] | campaign candidate + selection rule | Not executable; pending `MSW-01`/`AR-01` |
| Native continuous-sweep spacing | no commanded wavelength step; candidate `40 cm⁻¹/s / 2 kSa/s = 0.02 cm⁻¹` per native HF2 sample before filtering/correlation | Distinguishes sampled stream spacing from optical resolution and independent information | [R11], [N1] | repository candidate + derived | Not executable; final speed/rate pending `AR-01`/`HF-01` |
| Marker candidate | 5 cm⁻¹ interval, 500 µs width; about 125 ms at candidate speed | Current timing qualification point | [R4] | campaign candidate/derived | Not executable; pending `MD-01`/`MSW-01` |
| QCL pulse candidate | 2 MHz, 150 ns external trigger; 30 % duty | Current design candidate; exposes conflict with generic duty limits | [R11], [M2], [M6] | candidate + manufacturer | Low until `QB-01`; do not run |
| MIRcat family pulse envelope | 0.1 kHz–3 MHz, 40 ns–1 µs; standard duty to 20 %, custom to 30 % | Family capability only; installed chip limits vary | [M2] | manufacturer | Medium family-level; installed value pending |
| MIRcat accuracy/linewidth | family ≤1 cm⁻¹ accuracy and ≤1 cm⁻¹ pulsed FWHM | Planning/uncertainty prior, not acceptance truth | [M2] | manufacturer | Medium; replace with `SP-02`/`QB-01` measured values |
| MIRcat warm-up start | 15 min plus TEC-at-setpoint and measured stability | Generic manual says 15 min; family sheet says specs after 10 min | [M6], [M2], [M10] | manufacturer | Conservative start; installed gate pending `QB-01` |
| MIRcat SDK status polling | at least 300 ms between repeated status queries (approximately 4 Hz guidance) | Avoids over-querying the controller; polling is not a timing reference | [M10] | manufacturer SDK guide | High implementation rule |
| MIRcat trigger latency | promoted electrical-edge-to-optical-pulse and start/process-to-active distributions; no guessed correction | Required for phase, segment, and uncertainty relationships | [R4], [R7], [R14] | instrument-measured campaign requirement | Pending `QB-01`/`MSW-01` |
| Process trigger | internal for sweep unless accepted external mode; installed correspondence reports roughly 1–100 ms active-low if external | Avoids applying older 250–500 ms step-mode text to the installed sweep without qualification | [R14], [M6] | installed correspondence + manual | High topology; width pending accepted `PT-01`/`MSW-01` if used |
| T660 output envelope | candidate positive, 150 ns, 50 Ω source; manual max 16 MHz and 10 ps programming resolution | Candidate wiring/settings within manufacturer capability, but downstream acceptance still required | [R11], [M7] | candidate + manufacturer | Candidate only |
| HF2 time constant/order candidate | 1 ms, order four; 99 % settling = 10 ms and 0.4 cm⁻¹ candidate scan travel | Quantifies possible dynamic distortion | [R11], [M5] | candidate + manufacturer/derived | Not executable; pending `AR-01` |
| HF2 rates candidate | Sample/Reference 2 kSa/s; DIO 5 kSa/s | Current provisional design | [R11] | repository candidate | Pending `HF-01`/`MD-01`/`HF-02` |
| HF2 output-rate rule | accepted rate; manufacturer notes commonly about 8× filter bandwidth | Preserves dynamics while avoiding USB loss | [M5] | manufacturer + measured campaign | Final pending `HF-01`/`HF-02` |
| HF2 filter settling | use manufacturer order-specific 99 % multiplier (4.6–16.0 tau across orders one–eight) | Direct filter response requirement | [M5], [N1] | manufacturer + canonical model | High equation; chosen order/tau pending `AR-01` |
| HF2 warm-up | 30 min when manufacturer specs are invoked | Manual specification condition | [M5] | manufacturer | High |
| Stream candidate | 30 s, design only; final measured prepad + full scan/transitions + postpad | Current candidate may cover a nominal 10 s traversal, but accepted timings are pending | [R11] | candidate + exact selection rule | Pending multiple promoted phases |
| Pico prior timing config | 8-bit DC ±10 V, 2 ns, 100000 samples, 1000 pretrigger, rising A, 100 individual captures | Completed timing evidence; not spectral acquisition | [R16] | instrument-measured campaign | High for those timing phases; repeat only if route changes |
| Pico warm-up | one hour if data-sheet accuracy is invoked | Manufacturer accuracy condition | [M9] | manufacturer | High |
| Detector spectral family | PVM-10.6 family 2–13 µm | Confirms family coverage; exact installed response comes from `DET-02` | [M3] | manufacturer | High family coverage; exact response pending |
| Dual normalization | `-log10[(S/R)_sample/(S/R)_background]` with covariance and `DET-04` balance | Canonical/campaign model; no equal-split assumption | [R4], [R7], [N1] | campaign + canonical model | High equation; correction bundle pending |
| Coverage reporting | 95 % coverage interval | Standard uncertainty reporting/Monte Carlo convention | [U1], [U2] | international metrology | High |
| Repeat day | at least three independent day/config realizations only under `RP-01` | Existing characterization-campaign requirement | [R7] | campaign | High if repeat-day claim is pursued |

## 21. Sources utilized

### Repository and campaign authorities

- **[R1]** [`AGENTS.md`](../../../AGENTS.md), repository rule prohibiting
  operational hash-matching gates.
- **[R2]** [`README.md`](../../../README.md),
  [`docs/repository_scope.md`](../../../docs/repository_scope.md), and
  [`docs/repository_cleanup_20260814.md`](../../../docs/repository_cleanup_20260814.md),
  campaign/material scope and retired-recipe boundary.
- **[R3]** [`docs/measurement_campaign_data_contract.md`](../../../docs/measurement_campaign_data_contract.md),
  identifiers, phase layout, artifacts, exclusions, restoration, and retention
  audit.
- **[R4]** Calibration campaign
  [`README.md`](../../../calibration/system_recalibration_001/README.md),
  [`campaign_sequence.md`](../../../calibration/system_recalibration_001/plans/campaign_sequence.md),
  [`calibration_matrix.csv`](../../../calibration/system_recalibration_001/analysis/calibration_matrix.csv),
  [`gap_analysis.md`](../../../calibration/system_recalibration_001/analysis/gap_analysis.md), and
  [`expansion_gap_map.md`](../../../calibration/system_recalibration_001/analysis/expansion_gap_map.md):
  campaign phase evidence plus `HF-01`, `MD-01`, `MSW-01`, `HF-02`, detector,
  `SP-01`, and `SP-02` requirements.
- **[R5]** P0
  [`p0_execution_baseline.md`](../../../calibration/system_recalibration_001/manifests/p0_execution_baseline.md),
  [`p0_blocker_table.md`](../../../calibration/system_recalibration_001/manifests/p0_blocker_table.md), and
  [`p0_requirement_decisions.md`](../../../calibration/system_recalibration_001/manifests/p0_requirement_decisions.md):
  accepted/discarded provenance, blocker, and claim decisions.
- **[R6]** [`calibration/system_recalibration_001/manifests/p0_physical_inventory.md`](../../../calibration/system_recalibration_001/manifests/p0_physical_inventory.md),
  Mylar, detector/amplifier, cable, and unresolved identity evidence.
- **[R7]** Characterization campaign [`README.md`](../README.md) and
  [`characterization_sequence.md`](characterization_sequence.md): `CH-00`,
  `QB-01`, `OG-01`, `AR-01`, `SV-01`, `SV-02`, `IR-01`, `PF-01`, and `RP-01`
  requirements.
- **[R8]** [`sv02_recipe_contract.md`](sv02_recipe_contract.md), required
  inputs and correction-freeze order.
- **[R9]** [`../analysis/characterization_matrix.csv`](../analysis/characterization_matrix.csv),
  minimum bidirectional Mylar replication.
- **[R10]** [`../../../recipes/safe_idle.yaml`](../../../recipes/safe_idle.yaml),
  reviewed safe-idle target.
- **[R11]** [`../../../recipes/mircat_sweep_scan.yaml`](../../../recipes/mircat_sweep_scan.yaml)
  and [`../../../recipes/hf2li_presets.yaml`](../../../recipes/hf2li_presets.yaml),
  provisional design settings inspected only to identify qualification needs.
- **[R12]** [`../../../docs/mircat_sweep_scan_workflow.md`](../../../docs/mircat_sweep_scan_workflow.md),
  active-segment, marker, direction, streaming, and abort rules.
- **[R13]** [`../../../hardware_configuration.yaml`](../../../hardware_configuration.yaml),
  [`../../../wiring_map.yaml`](../../../wiring_map.yaml), and current device
  services/workflow under `control_app/`, used to verify installed topology and
  current control behavior, not as approved campaign recipes.
- **[R14]** [`../../../docs/MIRcat/daylight_db9_process_trigger_correspondence.md`](../../../docs/MIRcat/daylight_db9_process_trigger_correspondence.md),
  installed-system DB9 mapping and process-trigger clarification.
- **[R15]** [`../../../control_app/devices/t660_service.py`](../../../control_app/devices/t660_service.py),
  current T660 stop/configure/start implementation and shot-counter semantics.
- **[R16]** [`../../../calibration/system_recalibration_001/readbacks/MS-01/normal/picoscope_configuration.json`](../../../calibration/system_recalibration_001/readbacks/MS-01/normal/picoscope_configuration.json)
  and the `MS-01` final report/acquisition source, completed PicoScope timing
  evidence.
- **[R17]** Complete current calibration readback evidence under
  `calibration/system_recalibration_001/readbacks/`, including `S0`, `MS-01`,
  `MS-02`, `T1-01`, `T2-01`, and the incomplete `PT-01` preflight: identities,
  PicoScope configurations, accepted/rejected captures, timing-path results,
  safe-idle records, limitations, and restoration evidence.
- **[R18]** Characterization data-retention templates under
  `characterization/system_characterization_001/templates/`: phase manifest,
  acquisitions, conditions, measurements, artifacts, exclusions, and
  calibration links.
- **[N1]** `C:\Users\Chris\Documents\UC Davis\SETI\Thesis\articles\rsi-pump-probe\supplement\notebook\RSI_Supplemental_Theoretical_Calculations.nb`,
  complete canonical notebook: CSV layouts, transmission-space spectral
  convolution, calibration/holdout logic, Gaussian/sloping-baseline fitting,
  resolution, Mylar validation, lock-in response/NEPBW, dual normalization,
  uncertainty, and predicted-versus-measured metrics.

### Manufacturer manuals and product sources

- **[M1]** Cole-Parmer SamplePrep, “3517 Mylar Window Film, 0.25 mil
  (6 µm),” [product page](https://www.coleparmer.com/i/cole-parmer-sampleprep-3517-mylar-window-film-0-25-mil-6-m-thick-2-3-4-in-wide-300-ft/0457599).
- **[M2]** DRS Daylight Solutions, *MIRcat-QT Data Sheet*, revision 13
  (2021), [direct PDF](https://www.daylightsolutions.com/wp-content/uploads/sites/3/2024/04/DRS_DLS_MIRCAT-QT-DATA-SHEET_REV-13-Zero-Pointing-1.pdf).
- **[M3]** VIGO Photonics, *PVM-10.6 Detector Series Datasheet*, version 3.0
  (2025), [direct PDF](https://vigophotonics.com/app/uploads/2024/07/PVM-10.6-detector-series-datasheet.pdf).
- **[M4]** VIGO Photonics, *SIP series preamplifiers datasheet*,
  [direct PDF](https://vigophotonics.com/app/uploads/sites/3/2022/07/SIP-series-datasheet.pdf);
  local installed package source: `docs/Detectors/MIDIR-Detector-Package.pdf`.
- **[M5]** Zurich Instruments, *HF2 User Manual*, current
  [online manual](https://docs.zhinst.com/hf2_user_manual/index.html) and
  [direct PDF](https://docs.zhinst.com/pdf/ziHF2_UserManual.pdf); local source:
  `docs/HF2LI/Zurich Insturments HF2LI User Manual.pdf`. Also used:
  `docs/HF2LI/Zurich Instruments LabOne API User Manual.pdf` for continuous
  streaming, DIO trigger resolution, loss flags, and timestamps.
- **[M6]** Daylight Solutions, *MIRcat Ultra-Broadly Tunable Mid-IR Laser User
  Manual*, D11-00028-02 Rev. A (2017), local source
  `docs/MIRcat/Daylight Solutions MIRcat Manual.pdf`; searchable public
  [manual page](https://manualzz.com/doc/68263000/daylight-solutions-mircat-qt-1-series-user-manual).
- **[M7]** Highland Technology, *T660 Manual*, hardware revision F / firmware
  history through 2025, local source
  `docs/T660/Highland Technologies T660 Manual.pdf`; manufacturer
  [T660 product page](https://www.highlandtechnology.com/product/T660) and
  [manual library](https://www.highlandtechnology.com/downloads/manuals.shtml).
- **[M8]** Highland Technology, *T660 Programming Guide* (2025), local source
  `docs/T660/Highland Technologies T660 Programming Guide.pdf`.
- **[M9]** Pico Technology, *PicoScope 5000D Series Data Sheet*, version 4
  (2021), [direct PDF](https://www.picotech.com/download/datasheets/picoscope-5000d-series-data-sheet.pdf);
  [manual/download page](https://www.picotech.com/oscilloscope/5000/picoscope-5000-manuals).
- **[M10]** Daylight Solutions, *Getting Started with the MIRcatSDK*, local
  direct source `docs/MIRcat/SDK/MIRcatSDKGuide.pdf`, used for initialization,
  interlock/key checks, arm/TEC-at-temperature, scan status, emission-off, and
  disarm sequencing.

### PET/Mylar spectroscopy literature

- **[P1]** I. Donelli, G. Freddi, V. A. Nierstrasz, and P. Taddei, “Surface
  structure and properties of poly-(ethylene terephthalate) hydrolyzed by
  alkali and cutinase,” *Polymer Degradation and Stability* 95 (2010)
  1542–1550. [DOI](https://doi.org/10.1016/j.polymdegradstab.2010.06.011),
  [direct author-manuscript PDF](https://backoffice.biblio.ugent.be/download/1044327/1044341).
- **[P2]** M. I. Avadanei, D. G. Dimitriu, and D. O. Dorohoi, “Optical
  Anisotropy of Polyethylene Terephthalate Films Characterized by Spectral
  Means,” *Polymers* 16 (2024) 850.
  [DOI](https://doi.org/10.3390/polym16060850),
  [open full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC10975901/),
  [direct publisher PDF](https://mdpi-res.com/d_attachment/polymers/polymers-16-00850/article_deploy/polymers-16-00850.pdf).
- **[P3]** Z. Chen, J. N. Hay, and M. J. Jenkins, “FTIR spectroscopic analysis of
  poly(ethylene terephthalate) on crystallization,” *European Polymer Journal*
  48 (2012) 1586–1610.
  [DOI](https://doi.org/10.1016/j.eurpolymj.2012.06.006).

### Wavenumber, uncertainty, and statistical authorities

- **[W1]** P. J. Potts et al., “Wavenumber Standards for Mid-infrared
  Spectrometry,” [direct NIST PDF](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=841561).
- **[W2]** R. U. Datla, J. J. Hsia, L. Wang, and D. Gupta, *Standard Reference
  Materials: Polystyrene Films for Calibrating the Wavelength Scale of
  Infrared Spectrophotometers — SRM 1921*, NIST SP 260-122 (1995).
  [DOI](https://doi.org/10.6028/NIST.SP.260-122),
  [direct PDF](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication260-122.pdf).
- **[W3]** ASTM E1421-99(2021), *Standard Practice for Describing and Measuring
  Performance of Fourier Transform Mid-Infrared Spectrometers: Level Zero and
  Level One Tests*. [DOI](https://doi.org/10.1520/E1421-99R21),
  [official standard page](https://store.astm.org/e1421-99r21.html).
- **[U1]** JCGM 100:2008, *Evaluation of measurement data — Guide to the
  expression of uncertainty in measurement*.
  [DOI](https://doi.org/10.59161/JCGM100-2008E),
  [direct PDF](https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf/cb0ef43f-baa5-11cf-3f85-4dcd86f77bd6?download=true).
- **[U2]** JCGM 101:2008, *Supplement 1 — Propagation of distributions using a
  Monte Carlo method*. [DOI](https://doi.org/10.59161/JCGM101-2008),
  [direct PDF](https://www.bipm.org/documents/20126/2071204/JCGM_101_2008_E.pdf/325dcaad-c15a-407c-1105-8b7f322d651c?download=true).
- **[S1]** C. M. Croarkin, “Measurement Process Characterization,”
  *NIST/SEMATECH Engineering Statistics Handbook*, chapter 2
  ([NIST page](https://www.nist.gov/publications/nistsematech-engineering-statistics-handbook-chapter-2-measurement-process)).
- **[S2]** NIST/SEMATECH, “Analysis of variability from a nested design”
  ([online handbook](https://www.itl.nist.gov/div898/handbook/mpc/section4/mpc44.htm)).
- **[S3]** NIST/SEMATECH, “Randomized block designs”
  ([online handbook](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm)).
- **[S4]** NIST/SEMATECH, “Bootstrap Plot”
  ([online handbook](https://www.itl.nist.gov/div898/handbook/eda/section3/bootplot.htm)).
