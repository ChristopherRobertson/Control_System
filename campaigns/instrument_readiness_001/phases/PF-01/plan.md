# PF-01 — platform sensitivity noise artifacts and stability

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `planned`  
Required dependencies: `SV-02B, IR-01, PF-00, PB-02, OV-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### PF-01 — platform sensitivity, noise, artifacts, and stability

Under normal optical operation with nonbiological controls, determine noise-
equivalent absorbance, minimum detectable absorbance for stated integration,
SNR scaling with averaging, drift, Allan behavior, common-mode rejection,
baseline/etalon artifacts, back-reflection sensitivity, and saturation margin.
Reuse component-level detector results and the DET-04 optical/detector balance
model; do not reacquire the splitter calibration.

The minimum grid is one complete Mylar continuous-sweep control plus a nonbiological
control for every materially distinct slow-scan and five-method architecture
configuration in the CH-00.1 matrix. Include room-temperature and 77 K
cell/cryostat/background conditions and one shared off-band control only when
equivalence is demonstrated. At each condition acquire one short record and one record as
long as the corresponding planned experiment block. Run pump-blocked plus
finite OPO-540 artifact controls only at their matching
biological anchors. Add power, dwell, or averaging points only if the retained
claim's detection/precision rule fails.

The OPO-540 controls use the qualified iris without adjustment and explicitly
test for residual pump-color/scatter artifacts after the aperture. Record the
post-iris power, iris configuration readback, and native WM-01 replacement
wavelength/status record for every associated block. Use the accepted spectral method,
not a center-wavelength reading alone, to assign or bound residual-color power.

Mandatory deliverables:

- Fixed-wavenumber short/long traces, repeated spectra, Sample/Reference and
  normalized records, controls, settings, conditions, and all rejection logs.
- Noise/Allan/SNR/averaging/common-mode/artifact metrics with definitions,
  confidence intervals, uncertainty, and recommended integration/averaging
  envelope.
- Explicit distinction between detector/electronics limits and complete-
  platform optical limits.

## `EXPERIMENTS.md` allocation and decision contract

PF-01 implements `EXP-CAL-12`, `EXP-CHAR-02`, `EXP-CHAR-05`, `EXP-CHAR-06`,
`EXP-CHAR-07`, `EXP-CHAR-09`, `EXP-CHAR-11`, `EXP-OPT-02`, `EXP-OPT-03`,
`EXP-OPT-05`, and `EXP-OPT-09`. Native streams, settings, controls, exposure and loss
ledgers, rejected intervals, covariance/noise/Allan/SNR/artifact analysis, uncertainty,
and supported envelopes are retained. Acceptance is configuration, temperature,
duration, wavelength/power, and topology specific. Hardware/path/topology/settings,
cell/cryostat/thermal state, source/dose/geometry, duration/environment, or analysis
changes trigger revalidation. This phase does not establish biological recovery,
damage, spectra, variance, or kinetics.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
