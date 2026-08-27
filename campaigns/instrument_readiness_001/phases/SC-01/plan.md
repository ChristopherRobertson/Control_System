# SC-01 — sample-cell and temperature-stage qualification

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `planned`  
Required dependencies: `TR-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

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
  drift and uncertainty at 293 K and 298 K when active control is available.
  If a setpoint cannot be controlled, record the observational limit and narrow
  the later kinetic claim rather than adding an unsupported calibration.
- Safe handling/restoration record and a biological-handoff table identifying
  the qualified cell/path/temperature configurations. CO loading, protein
  state verification, and chemical stability remain experiment-phase work.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
