# CL-01 — complete timing-chain closure

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `OP-01, FE-01, DET-03, HF-02`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 24. CL-01 — complete timing-chain closure

Calculate direct and derived chains only between compatible reference planes.
Keep programmed, cable-end, device-pin, detector, optical, and chemical origins
distinct and establish the operational nonzero-delay correction and pump-probe
equation.

Close the retained OPO-540 pump path, each MIRcat probe-arrival path, and every
CH-00.1 architecture configuration across both normal dual-detector and temporary
timing/IRF topologies. Distinguish slow scan, wavelength-by-wavelength, repeated rapid
scan, nanosecond and microsecond fixed-wavelength, single-scan phase-delay, and
single-pump scan-burst histories wherever their correction terms differ.
Use existing completed electrical sweeps; do not reacquire them. Include the
FE-01 observed-event clock bridge over both the longest planned HRP recovery
record and the retained MbCO record.
The OPO-540 chain is valid only for the ATT-01 iris configuration imported by
OP-01 and FE-01; iris USB/API latency is recorded as configuration provenance
but is not part of the per-shot timing equation because the aperture remains
static throughout an emitted block.

Mandatory closeout deliverables: machine-readable correction-term register,
reference-plane graph, covariance-aware uncertainty propagation, closure table
and residuals, incompatible-chain rejection list, validity/configuration IDs,
and pass/fail decisions against frozen engineering limits.

## `EXPERIMENTS.md` allocation and decision contract

CL-01 implements `EXP-CAL-04`, `EXP-CAL-08`, `EXP-CAL-09`, `EXP-CAL-18`,
`EXP-OPT-04`, and `EXP-VAL-07`. Acceptance requires a covariance-aware reference-plane
graph and closure residual for each compatible configuration; incompatible terms are
explicitly rejected rather than combined. Native source terms and their stable IDs,
signs, uncertainty, validity, and topology bridges are retained. Any constituent
component, route, topology, timing/source/acquisition setting, optical plane, or analysis
change triggers revalidation. Chemical time zero remains an optically observed
sample-plane convention, not an electrical command or cable-length assumption. This
phase does not establish biological response or kinetics.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
