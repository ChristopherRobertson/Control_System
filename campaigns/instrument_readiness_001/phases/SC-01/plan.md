# SC-01 — sample-cell and temperature-stage qualification

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `planned`  
Required dependencies: `TR-01, CH-00.1`
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### SC-01 — gas-tight sample-cell and temperature-stage qualification

Qualify the minimum nonbiological sample hardware shared by the HRP-C-CO and
MbCO procedures before biological preparation. Use water or the approved
buffer surrogate only; no CO or protein is used. CH-00 selects the smallest
cell set, preferring one common gas-tight CaF2 assembly/path when the two briefs'
transmission and sensitivity constraints allow it.

Mandatory deliverables:

- Stable IDs for cell body, windows, spacer, seals, mount, temperature sensor/
  stage, and fill/vent hardware; measured assembled path length and uncertainty;
  fill/dead volume; aperture; orientation; cleaning and assembly method.
- Empty-cell and filled-blank transmission at the retained probe anchors,
  background/fringe/scatter results, bubble and leak criteria, one disassembly/
  reassembly check, and compatibility with the retained pump/probe geometry.
- Temperature-sensor basis, spatial placement, equilibration rule, stability/
  drift and uncertainty at every retained room-temperature condition and at 77 K.
  Qualify cryostat/window/background, thermal cycling, condensation/frost control,
  sample-plane temperature gradients, and pump/probe access as separate configuration
  terms rather than extrapolating room-temperature evidence.
  If a setpoint cannot be controlled, record the observational limit and narrow
  the later kinetic claim rather than adding an unsupported calibration.
- Safe handling/restoration record and a biological-handoff table identifying
  the qualified cell/path/temperature configurations. CO loading, protein
  state verification, and chemical stability remain experiment-phase work.

## `EXPERIMENTS.md` allocation and decision contract

SC-01 implements `EXP-CAL-16`, `EXP-CAL-17`, `EXP-CHAR-10`, `EXP-CHAR-11`, and
`EXP-OPT-01` and
is the hardware prerequisite for all four mandatory slow-scan conditions. Native
temperature/time records, sensor calibration basis, empty/filled controls, thermal
cycles, geometry, background, leak/bubble/frost checks, uncertainty, rejected records,
and restoration are required. Acceptance is cell/path/temperature/configuration-
specific. Cell/window/spacer/seal, cryostat/stage/sensor, alignment, thermal cycle,
temperature range, or analysis changes trigger revalidation. This phase does not
establish CO loading, protein state, photochemistry, sample stability, or spectra.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
