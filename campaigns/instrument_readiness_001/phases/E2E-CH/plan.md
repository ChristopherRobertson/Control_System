# E2E-CH — bounded nonbiological full-system demonstration

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `planned`  
Required dependencies: `E2E-01, SV-02B, IR-01, PF-01, RP-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

### E2E-CH — bounded nonbiological full-system demonstration

Run one composite nonbiological demonstration with three bounded blocks under
one reviewed phase plan: probe-only Mylar-style continuous sweep under the
sweep configuration, finite OPO-540/HRP-style fixed-wavenumber recovery under
the HRP configuration, and finite OPO-540/MbCO-style fixed-wavenumber recovery
under the MbCO configuration using one unchanged iris configuration. Reuse
calibration FE-01/E2E-01 fault-recovery
evidence; do not repeat simulated failures unless the orchestration or
configuration has materially changed.

The OPO-540 block includes electronic-iris startup/ownership, accepted command/
readback, configuration foreign key, post-iris power, mismatch stop, unchanged-
setpoint audit, WaveMaster working-reference identity/settings/native status,
and restoration. The iris remains outside finite-event control.

Mandatory deliverables:

- Complete manifest, native Sample/Reference/DIO/source/readback data,
  calibration and characterization configuration IDs, axes, processing,
  startup/safe-stop/restoration records, and artifact audit.
- Predeclared expected result, observed agreement, uncertainty, and a readiness
  decision for biological method development.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
