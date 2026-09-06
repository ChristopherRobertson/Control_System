# MD-01 — MIRcat and HF2LI DIO mapping qualification

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `HF-01, CH-00.1, MS-02.1`
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 13. MD-01 — MIRcat/HF2LI DIO mapping qualification

Use the accepted side-experiment pin-to-bit mapping without repeating the
mapping-only discovery. Qualify the installed process-trigger pulse and state
semantics for each CH-00.1-retained acquisition method. Verify that one commanded
wavelength or scan transition produces one accounted transition, including Tuned,
process/fault/invalid states, polarity, direction, pulse interval and width, receiver
level and termination, signatures, counts, timestamp alignment, and repeatability.
For finite scan acquisition, reconcile each scheduled T660-2 C process command
and frame identity with exactly one observed Sweep Active interval on HF2LI
DIO21, using the same pin-2 signal on PicoScope EXT when acquiring diagnostics.
Verify edge polarity, event order, first/last-frame behavior, count equality,
invalid/fault behavior, and missing or duplicate scan transitions. Retain the
complete T660 frame/train table, readbacks, and channel OFF baseline/padding
semantics and zero-additional-pulse train setting. No T660 D marker or DIO1 acquisition gate is present.

Acquire campaign-local records in both scan directions and repeated point/process or
scan-burst sequences under each materially distinct retained configuration. Do not map
unused DB9 modes or reserved pins.

Mandatory closeout deliverables: complete DIO words rather than selected bits,
MIRcat logs, HF2LI configuration ID, pin/bit/state truth table, direction and
transition signatures, T660-2 C/frame/Sweep-Active event-reconciliation table, count
reconciliation, timestamp alignment, raw artifact
index entries, configuration IDs, receiver electrical conditions, uncertainty, and an
explicit qualification decision.

## `EXPERIMENTS.md` allocation and decision contract

This phase supplies the installed digital-event mapping and transition integrity needed
by `EXP-CAL-04`, `EXP-CAL-06`, `EXP-CAL-07`, and `EXP-CHAR-03`.
Acceptance is configuration-specific and requires complete event accounting with no
unexplained duplicates, omissions, invalid states, or unsupported receiver conditions.
For Phase Scan, a missing, extra, or ambiguously paired frame, process command, or Sweep Active
interval rejects the affected event/configuration before optical-pulse coverage is
interpreted.
Native complete DIO words and MIRcat records are the evidence; selected-bit extracts
alone are insufficient. Revalidation is triggered by cable/pinout, receiver,
termination, MIRcat firmware/mode, HF2LI DIO settings, event semantics, or analysis
version changes. MSW-01, AR-01, IR-01, E2E-01, and both biological campaigns consume
the result. This phase does not establish wavenumber accuracy, optical timing zero,
sample kinetics, or scan-speed accuracy.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
