# RPT-CH — characterization reporting and thesis reuse package

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `planned`  
Required dependencies: `E2E-CH`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

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

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
