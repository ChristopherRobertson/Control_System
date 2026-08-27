# DET-01 — dark detector and electronics performance

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `HF-01, TR-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

### 16. DET-01 — dark detector/electronics performance

With non-emitting sources, determine dark noise, drift, Allan-style stability,
electrical cross-talk, range dependence, and short/long-duration repeatability.
Use only the gains/ranges retained for the three HF-01 configurations. For each
installed channel/configuration acquire one short record, one record as long as
the longest planned acquisition, and one revisit; do not scan unused gains,
ranges, or durations.

Mandatory closeout deliverables: exact installed detector/amplifier/power-
supply identities and settings, blocked-state definition, environmental log,
raw Sample/Reference records, PSD/Allan/noise tables, cross-talk controls,
uncertainty budget, and accepted dark-operating configuration.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
