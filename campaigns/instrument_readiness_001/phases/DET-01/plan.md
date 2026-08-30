# DET-01 — dark detector and electronics performance

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `HF-01, TR-01, MS-02.1, CH-00.1`
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 16. DET-01 — dark detector/electronics performance

With non-emitting sources, determine dark noise, drift, Allan-style stability,
electrical cross-talk, range dependence, and short/long-duration repeatability.
Use only the gains/ranges retained for the CH-00.1 architecture configurations. For each
installed channel/configuration acquire one short record, one record as long as
the longest planned acquisition, and one revisit; do not scan unused gains,
ranges, or durations.

Mandatory closeout deliverables: exact installed detector/amplifier/power-
supply identities and settings, blocked-state definition, environmental log,
raw Sample/Reference records, PSD/Allan/noise tables, cross-talk controls,
uncertainty budget, and accepted dark-operating configuration.

## `EXPERIMENTS.md` allocation and decision contract

DET-01 implements the dark/noise/drift foundations of `EXP-CAL-11`,
`EXP-CHAR-06`, and `EXP-OPT-02` across slow-scan,
fixed-wavelength, repeated rapid-scan, and single-pump scan-burst configurations at
room temperature and 77 K where retained. Native dual-channel records, settings,
controls, environment, rejected intervals, spectra/Allan analysis, and uncertainty are
required. Acceptance is channel/configuration/duration-specific. Detector, amplifier,
power supply, cable/branch, HF2LI path, range/gain/filter/rate, grounding, environment,
or analysis changes trigger revalidation. It does not establish illuminated linearity,
optical throughput, chemical time zero, or sample behavior.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
