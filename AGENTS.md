# Repository instructions

These instructions apply to the entire repository. More specific instructions
in subdirectories add to these rules and may not weaken them.

## Hash matching must not be an operational gate

Git may use commit and object hashes normally, and repository tools may record
or display hashes, checksums, or digest values for informational or diagnostic
purposes. Do not add a repository-specific requirement that any such value
must match a previously recorded value for the application, a campaign phase,
data loading, analysis, aggregation, reproduction, acceptance, closeout, or
promotion to work. A missing or changed value may be reported as information,
but it must not be the sole reason that repository-authored behavior fails or
blocks progress.

Normal integrity behavior internal to Git, package managers, file formats, and
external tools is not restricted. The prohibition applies to additional
hash-matching gates authored in this repository.

Prefer stable human-readable IDs, relative paths, byte sizes, UTC timestamps,
explicit software/schema/analysis versions, branch or commit references,
dirty-file lists, device identities, configuration registries, and
source/producer records for campaign provenance and aggregation.

## Unified repository hierarchy

`campaigns/master_sequence.md` is the authoritative human instruction set and
`campaigns/phase_registry.yaml` is its machine-readable phase/dependency
companion. Calibration and characterization are domains in one readiness sequence.
Completed and in-progress evidence stays in its canonical phase package registered
in `campaigns/registries/evidence_locations.yaml`. Preserve every native, rejected,
preview, diagnostic, excluded, superseded, closeout, and restoration record when
maintaining those packages.

The control application consumes explicitly promoted machine-readable bundles from
`instrument/promoted_bundles/`, not raw campaign evidence or prose reports. Creating
a plan, registry row, bundle directory, or manifest never authorizes hardware,
changes phase status, or promotes a bundle.

## Thesis-quality phase procedural writeups

Every campaign phase requires a canonical `procedural_writeup.md` that complies
with `docs/phase_record_contract.md`. The writeup must explain
WHY the phase was necessary, HOW it was actually performed step by step, WHAT the
results were, and which implications, caveats, limitations, and bounded claims
follow. It must be indexed, manifest-linked, evidence-traceable, and accepted by a
named reviewer before a new phase is considered documentation-complete.

Do not substitute a plan, command log, generated result dump, or terse
`final_report.md`. Do not invent details or reacquire completed measurements to fill
a narrative gap. Completed phases retain their scientific disposition while a
retrospective evidence reconstruction is tracked separately; unknowns remain
explicit and limit claims.
