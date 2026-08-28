# SV-02A — polystyrene spectral calibration and correction freeze

Campaign: `instrument-readiness-001`  
Domain: `validation`  
Registry status: `planned`  
Required dependencies: `PF-00, SP-02, SV-01, AR-01, DET-04`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### SV-02A — polystyrene spectral calibration and correction freeze

This phase contains no Mylar. It freezes scan/HF2LI settings, normalization,
baseline/fitting methods, feature windows, tolerances, and software/analysis versions
with the correction and covariance, tests the declared polystyrene holdout without
refitting, and issues the formal Mylar unlock only after every freeze gate passes.

Start from the frozen SP-02 instrument-axis result, then use only the declared
polystyrene alignment partition to fit the final wavenumber correction against
authoritative polystyrene feature values. Use a first-order correction unless
a higher order is justified by predeclared residual criteria and uncertainty.
Freeze the fitted function, coefficients, covariance, validity range, and
software version before opening the Mylar data or any later biological data.

Apply that frozen correction to an independent polystyrene holdout partition without
refitting. Mylar is not opened in SV-02A. Biological samples are outside this phase
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
  validity range, software version, and proof that neither Mylar nor biological data
  influenced the correction.
- DET-04 correction ID, raw-ratio versus normalized-result audit, forward-model
  inputs/outputs, figures/tables, and thesis-claim acceptance decision.

The minimum acquisition is the predeclared polystyrene alignment and holdout sets.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
