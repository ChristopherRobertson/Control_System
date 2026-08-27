# MD-01 — MIRcat and HF2LI DIO mapping qualification

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `HF-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

### 13. MD-01 — MIRcat/HF2LI DIO mapping qualification

Use the accepted side-experiment mapping (pin 1 to bit 20, pin 2 to bit 21,
pin 3 to bit 22) without repeating the mapping-only discovery. Acquire three
campaign-local scans per direction at the retained continuous-sweep
configuration and three repeats of the retained point/process sequence under
each of the HRP-C-CO and MbCO acquisition configurations. Verify
polarity/state semantics, direction behavior, signatures, counts, timing, and
repeatability. Do not map unused DB9 modes or reserved pins.

Mandatory closeout deliverables: complete DIO words rather than selected bits,
MIRcat logs, HF2LI configuration ID, pin/bit/state truth table, direction and
transition signatures, count reconciliation, timestamp alignment, raw artifact
index entries, and an explicit qualification decision.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
