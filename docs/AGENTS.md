# Documentation instructions

These instructions apply to `docs/` and its subdirectories.

## Canonical documents

Keep repository architecture and navigation in `README.md`. Keep the complete
phase evidence and procedural-writeup contract in `phase_record_contract.md`.
Keep focused, operator-facing application procedures in `operating_procedures/`.
Do not create a second repository-scope document, data contract, writeup standard,
campaign sequence, phase-status list, or migration narrative in the active tree.

When information belongs to one campaign or phase, put it in that campaign's
`README.md`, `requirements.md`, master entry, registry metadata, or phase package
instead of expanding repository-wide documentation.

## Change discipline

- Update every live reference when a canonical document path changes.
- Preserve superseded source documents by moving them intact into `.archive/`
  under their original repository-relative hierarchy.
- Treat `.archive/` as read-only reference material, never as an execution,
  dependency, data-loading, or promotion authority.
- Do not rewrite completed phase observations, manifests, indexed artifacts, or
  contemporaneous provenance merely to modernize documentation wording.
- Keep stable campaign, phase, acquisition, artifact, configuration, and bundle
  identifiers unchanged.
- Record unknown information as `USER_INPUT_REQUIRED`; do not infer an operator
  action, setting, observation, or scientific rationale.

## Contract maintenance

Schema, template, collector, validator, test, and documentation changes that affect
the phase-record contract must be updated together. A change to a required table or
manifest field increments the applicable schema/contract version. Existing native
evidence remains readable and is never reacquired or converted solely because the
contract changed.

Repository-authored checks may validate stable IDs, paths, byte sizes, timestamps,
relationships, versions, statuses, and required fields. They must not require a
previously recorded hash or digest to match as an operational gate.
