# Instrument-readiness campaign instructions

These instructions apply throughout this campaign.

## Phase-primary organization

`phases/<phase-id>/` is the sole active home for a phase definition. Every
registered phase must contain `phase.yaml`, `plan.md`, and `README.md`. Put
phase-specific planning notes beside those files. Do not recreate separate
calibration or characterization plan trees, combined sequence catalogs, or a
second copy of a phase plan.

`shared/` is only for material that genuinely governs or compares multiple
phases. Calibration, characterization, validation, and promotion are registry
metadata domains, not directory hierarchies.

## Evidence and completed work

Keep acquired records in the evidence root registered by `evidence_key` in
`campaigns/registries/evidence_locations.yaml`. Never move, rewrite, or repeat a
completed measurement merely to make its historical evidence resemble a new
template. Link the canonical phase directory to retained evidence instead.

Historical evidence may cite repository paths that existed when it was created.
Treat those citations as provenance records. Do not silently rewrite an accepted
manifest or artifact to point at the post-migration layout.

## Execution and closeout

Follow `shared/phase_execution_requirements.md` and the phase's `plan.md`. Work on
one explicitly authorized phase at a time, present one physical action at a time,
record the operator's actual observation, and stop at the authorized boundary.
Planning or documentation work does not authorize hardware control, acquisition,
phase-state changes, closure, or promotion.

Record information that only the operator can supply as `USER_INPUT_REQUIRED`;
never replace a missing observation, confirmation, or setting with an assumption.

Every phase requires a distinct thesis-quality `procedural_writeup.md` meeting
`../../docs/data_contract/procedural_writeup_standard.md`. For historically
completed phases, prepare the writeup from retained evidence and state unknowns
and limitations; do not reacquire data solely to backfill documentation.

Repository-authored checks must not use hash matching as an operational gate.
Use stable IDs, relative paths, versions, timestamps, configuration identities,
and explicit source records for provenance and acceptance.
