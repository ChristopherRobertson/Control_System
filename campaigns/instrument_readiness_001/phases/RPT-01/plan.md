# RPT-01 — calibration reporting uncertainty and reuse package

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `E2E-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

### 26. RPT-01 — calibration reporting, uncertainty, and reuse package

Create the reusable package that downstream characterization, thesis analysis,
and experimental campaigns will consume. This is analysis-only and does not
repeat acquisition.

Mandatory closeout deliverables:

- Versioned calibration-bundle manifest linking every promoted candidate value
  to raw evidence, analysis code, correction terms, units, reference planes,
  covariance, validity envelope, and unresolved limitations.
- Three experiment-specific HF2LI configuration IDs, their acquisition-rate,
  time-constant, filter-order, settling, bandwidth, and record-length validity
  envelopes, plus any measured biological equivalence/alias record. Reporting
  must not silently substitute one biological configuration for the other.
- The reusable HF-01 electrical response bundle containing the monitored-AWG
  topology, three-anchor validation, computational setting-evaluation table,
  complex transfer/step/noise/range/rate/selected-channel-equivalence models,
  covariance, validity limits, and explicit downstream non-duplication links.
- Aggregation-ready acquisition/artifact indexes for all phases, including the
  previously completed phases without relocating or rewriting their raw data.
- GUM-style budgets, thesis claim-to-evidence matrix, bypass register,
  data dictionary, machine-readable summary tables, and reproducible figure
  scripts.
- Retention audit confirming raw, rejected, excluded, and superseded evidence
  remain recoverable and distinguishable.
- Electronic-iris reuse package containing the control/service version,
  permanent mount/fiducials, accepted 540 nm setpoint and tolerance, optical
  transfer and contamination bounds, validity envelope, command/readback
  requirements, and revalidation triggers. Preserve the pre-iris OM-01 result
  as historical mixed-spectrum evidence rather than relabeling it.
- WaveMaster working-reference package containing its WM-01 identity,
  adapter/power/probe configuration, native response-state contract,
  measurement settings, repeatability and uncertainty, validity envelope,
  bundle/quantity IDs, and the distinction between center-wavelength evidence
  and spectral-power-fraction evidence.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
