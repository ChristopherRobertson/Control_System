# E2E-01 — normal-wiring calibration validation

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `CL-01, SP-02, DET-04, SV-02B`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 25. E2E-01 — normal-wiring validation

Perform bounded nonbiological runs that separately validate the normal simultaneous
dual-detector topology and the temporary sample-detector/pump-detector timing/IRF
topology. Collectively cover slow scan and every materially distinct retained
architecture family rather than assuming three envelopes represent them. Together they cover startup, ownership, T660s,
MIRcat/reference lock, Sample/Reference/full-DIO capture, finite exposure,
axes, processing, safe stop, repeatability, and artifact completeness. Reuse
FE-01 fault-path evidence; add one no-emission simulated software fault only if
the E2E orchestration differs materially.

The rare-pump run uses the qualified OPO-540 iris configuration when that is
the retained more-complex path. Its startup, command/readback, configuration
foreign key, mismatch stop, and restoration are part of the end-to-end audit.

Mandatory closeout deliverables: complete configuration-specific manifests and native
data sets, configuration/calibration bundle IDs, processed-axis outputs,
cross-run comparison, artifact audit, safe-stop records, no-fire fault-injection
record, recovery record, and normal-wiring restoration.

## `EXPERIMENTS.md` allocation and decision contract

E2E-01 implements the orchestration and topology-separation portions of `EXP-OPT-04`
and `EXP-VAL-07`. Acceptance requires native dual-channel data under normal wiring,
separate native timing data under temporary wiring, a calibrated bridge limited to
supported quantities, configuration restoration, fault-safe stop/recovery, and a
complete artifact audit. Topology, orchestration, component, calibration/configuration,
or analysis changes trigger revalidation. This phase does not validate reconstruction
algorithms or establish biological readiness by itself.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
