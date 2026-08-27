# E2E-01 — normal-wiring calibration validation

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `CL-01, SP-02, DET-04, SV-02B`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

### 25. E2E-01 — normal-wiring validation

Perform exactly three bounded nonbiological runs: one probe-only continuous
sweep, one HRP-style finite rare-pump recovery run, and one MbCO-style finite
rare-pump delay/recovery run. Together they cover startup, ownership, T660s,
MIRcat/reference lock, Sample/Reference/full-DIO capture, finite exposure,
axes, processing, safe stop, repeatability, and artifact completeness. Reuse
FE-01 fault-path evidence; add one no-emission simulated software fault only if
the E2E orchestration differs materially.

The rare-pump run uses the qualified OPO-540 iris configuration when that is
the retained more-complex path. Its startup, command/readback, configuration
foreign key, mismatch stop, and restoration are part of the end-to-end audit.

Mandatory closeout deliverables: three complete independent manifests and native
data sets, configuration/calibration bundle IDs, processed-axis outputs,
cross-run comparison, artifact audit, safe-stop records, no-fire fault-injection
record, recovery record, and normal-wiring restoration.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
