# Instrument-readiness campaign instructions

These instructions apply throughout this campaign.

## Phase-primary organization

`phases/<phase-id>/` is the sole active home for a phase package. Every registered
phase contains `phase.yaml`, `plan.md`, and `README.md`. Put phase-specific
planning records, run records, readbacks, raw acquisitions, analysis, reports,
restoration evidence, and retained artifacts in that directory. Do not create a
second plan or evidence tree organized by calibration or characterization.

Use `requirements.md` only for rules or methods that govern multiple phases.
The domain field in the registry classifies the work; it does not define a
directory hierarchy or an independent sequence.

## Authority and execution

Follow, in order:

1. `../master_sequence.md` for campaign-level instructions and dependency order;
2. `../phase_registry.yaml` for machine-readable status and dependencies;
3. `requirements.md` for cross-phase execution, evidence, and method rules; and
4. the phase's `plan.md` for its exact procedure and acceptance logic.

Planning or documentation work does not authorize hardware control, acquisition,
phase-state changes, closeout, or promotion. During authorized execution, present
one physical action at a time, wait for the operator's actual observation, and
stop at the authorized boundary. Record operator-only information as
`USER_INPUT_REQUIRED`; never substitute an assumption.

## Evidence and completed work

The phase directory is the evidence root registered by `evidence_key` in
`../registries/evidence_locations.yaml`. Preserve accepted native files and their
stable IDs. Do not copy, rewrite, or repeat a completed measurement merely to
satisfy an organizational or documentation change.

Accepted evidence may contain path strings that record where a source existed at
acquisition time. Preserve those strings as provenance. Use current canonical
paths in new plans and records.

Every phase requires a distinct thesis-quality `procedural_writeup.md` meeting
`../../docs/phase_record_contract.md`. For a completed phase without that
document, reconstruct it from retained evidence, identify unknowns and limitations,
and preserve the scientific disposition. Do not reacquire data solely to fill a
documentation gap.

Repository-authored behavior must not use hash matching as an operational gate.
Use stable IDs, relative paths, versions, timestamps, device/configuration
identities, source records, and branch or commit context for provenance and
acceptance.
