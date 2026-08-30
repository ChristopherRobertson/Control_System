# PF-00 — pre-standard full-system noise and SNR readiness

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `planned`  
Required dependencies: `AR-01, DET-04, SC-01, OG-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### PF-00 — pre-standard full-system noise and SNR readiness

Before QCL polystyrene calibration, use a blank, stable nonbiological signal, or
qualified transfer condition—never Mylar—to measure normalized baseline noise,
common-mode rejection, drift, saturation margin, and sufficient SNR. Import detector
response, sample/reference balance and normalization covariance, MIRcat source and
beam transfer, cell/blank/temperature readiness, and AR-01 selection. PF-00 must pass
before SV-02A. PF-01 remains later for pump artifacts, experiment-length stability,
and biological-anchor operating envelopes.

Measure every materially distinct slow-scan and reconstruction configuration needed to
show that its target precision is supportable, including room-temperature and 77 K
blank/cryostat envelopes. Retain native Sample/Reference streams, settings, controls,
loss/rejection records, covariance, Allan/noise and SNR analysis, uncertainty, and the
configuration-specific acceptance rule. Changes in source/detector/topology/settings,
cell/cryostat/temperature, normalization, duration, environment, or analysis trigger
revalidation. This phase implements the readiness portions of `EXP-CAL-12`,
`EXP-CHAR-06`, `EXP-CHAR-09`, `EXP-OPT-01`, and `EXP-OPT-06`; it does not establish
sample absorbance, pump artifacts, biological variance, or kinetics.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
