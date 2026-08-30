# OP-01 — operational pump-command-to-sample timing

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `ATT-01, PB-02, DET-03, MS-02.1`
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 22. OP-01 — operational pump-command-to-sample timing

At a nonbiological sample-equivalent plane, independently observe both the
permanent-iris 540 nm pump arrival and MIRcat probe arrival for every retained probe
mode/region. Capture and report them under separate room-temperature/77 K HRP-C-CO
and MbCO acquisition configuration IDs. The pump path may be shared; probe module,
mode, region, optical path, acquisition-filter delay, sampling, and estimator
corrections may not be assumed shared.
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
budget; blocked control; one attenuated preview; a prospective precision- and
exposure-based repeat count frozen before results; raw traces;
shot/rejection/counter ledger; SNR/saturation checks;
adapter/splitter/detector/placement IDs; signed correction equation; placement
and restoration repeatability; uncertainty budget; photographs; and final safe
state. No automatic replacement shots are permitted.

## `EXPERIMENTS.md` allocation and decision contract

OP-01 implements the optical-arrival portions of `EXP-CAL-08`, `EXP-CAL-09`,
`EXP-CAL-18`, `EXP-OPT-04`, and `EXP-VAL-07`. Electrical command or equal cable
length is not chemical time zero. Native synchronized optical/electrical records,
blocked controls, reference planes, configuration IDs, signed corrections, rejected
events, jitter and uncertainty are required. Pump/probe route, module/mode/region,
optic/cell plane, detector/branch/adapter/cable, timing receiver, acquisition settings,
or analysis changes trigger revalidation. This phase does not establish a sample's
chemical response, recovery, dose tolerance, or kinetics.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
