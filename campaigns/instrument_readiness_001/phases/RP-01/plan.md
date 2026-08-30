# RP-01 — between-run reproducibility and operational envelope

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `planned`  
Required dependencies: `PF-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### RP-01 — between-run reproducibility and operational envelope

Repeat only representative characterization conditions selected in CH-00 on
separate days and after one documented normal restoration/reinstallation. This
tests reproducibility; it is not a repeat of the complete characterization
grid.

On each of three independent days, run a prospectively balanced compact checkpoint
suite that collectively covers every non-equivalent architecture configuration,
including room-temperature and 77 K optical/cryostat states, without repeating full
phase grids. Include the Mylar sweep anchor and HRP/MbCO surrogates under the unchanged
iris configuration. Shared startup,
dark, geometry, and restoration evidence
is recorded once per day. Do not repeat full PB/QB/OG/OV/AR/SV/IR/PF grids.

Each OPO-540 checkpoint verifies the permanent mount/fiducials, commands and
reads back the promoted diameter, and evaluates centroid/profile/aperture
margin against the revalidation limits. It also acquires a WM-01-linked native
wavelength/status checkpoint in the retained probe geometry. Failure triggers
recharacterization; the daily checkpoint does not optimize a new diameter.

Mandatory deliverables:

- Exactly three planned independent day/configuration realizations for the
  selected checkpoints, with stable configuration IDs, complete settings
  snapshots, environment, operator actions, and calibration validity. An
  additional realization is allowed only under the campaign minimal-grid rule.
- Within-run, between-run, and restoration components; control charts or
  equivalent drift assessment; agreement with earlier phase results; and
  recharacterization triggers.
- Final operating-envelope table identifying validated, conditionally
  validated, manufacturer-only, and unsupported regions.

## `EXPERIMENTS.md` allocation and decision contract

RP-01 implements `EXP-CHAR-09`, `EXP-CHAR-11`, `EXP-CHAR-14`, `EXP-OPT-10`, and
`EXP-VAL-06`. The three-day design must distinguish startup, placement/reinstallation,
day, temperature/thermal-cycle, and residual repeat components with configuration IDs,
native checkpoints, uncertainty, control limits, and rejected records. A material
hardware/path/configuration change or failed checkpoint triggers recharacterization;
unsupported rows remain unsupported. This phase does not establish preparation
variance, biological recovery, dose tolerance, peak positions, or kinetics.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
