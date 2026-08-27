# OP-01 — operational pump-command-to-sample timing

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `ATT-01, PB-02, DET-03`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

### 22. OP-01 — operational pump-command-to-sample timing

Execute one bounded biological-pump optical path at permanent-iris 540 nm, but
capture and report it under the separate retained HRP-C-CO and MbCO HF2LI
acquisition configuration IDs. The pump path may be shared; acquisition-filter
delay, sampling, and estimator corrections may not be assumed shared.
Use the identified straight barrel adapter correction (0.125 ns with
0.0722 ns rectangular standard uncertainty), MS-01/MS-02 results, and DET-03
detector correction. The Q-switch cable, loaded Nd:YAG response, the applicable
internal laser/OPO response, and optical propagation remain intentionally
included. Mylar is pump-off and adds no OP-01 condition.

The OPO-540 timing configuration must use the ATT-01-qualified permanent iris
at its accepted locked mount and aperture setpoint. Record a fresh command/
readback and configuration ID before every emitted block. Do not use the iris
as the timing origin, optical event gate, or safety shutter.

Mandatory closeout deliverables for the retained pump path: frozen shot
budget; blocked control; one attenuated preview; a prospective precision-based
repeat count capped at 100 unless separately approved; raw traces;
shot/rejection/counter ledger; SNR/saturation checks;
adapter/splitter/detector/placement IDs; signed correction equation; placement
and restoration repeatability; uncertainty budget; photographs; and final safe
state. No automatic replacement shots are permitted.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
