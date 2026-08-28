# Unified thesis campaign workspace

This directory is the authority for campaign instructions, order, and dependency
management. Calibration, characterization, validation, promotion, and biological
experiment are phase domains in one dependency graph; they are not independent
linear schedules.

The human-readable authority is `master_sequence.md`; `phase_registry.yaml` is its
machine-readable companion. Every registered phase has one
self-contained package under the owning campaign's `phases/<phase-id>/` directory,
including its detailed plan and all generated run evidence.
`registries/evidence_locations.yaml` maps stable phase IDs to their canonical
evidence packages.

Directory responsibilities:

- `master_sequence.md`: authoritative execution instructions and phase catalog;
- `phase_registry.yaml`: phase identity, status, ordering, and hard dependencies;
- `registries/`: evidence and configuration relationships;
- `instrument_readiness_001/phases/`: all 47 instrument-readiness phase homes;
- `instrument_readiness_001/requirements.md`: consolidated cross-phase
  execution, measurement, method, and closeout requirements;
- `hrp_001/phases/`: all 10 first-biological-campaign phase homes;
- `mbco_cryo_001/phases/`: all 11 optional cryogenic-branch phase homes; and
- `methods/` and `templates/`: shared controlled campaign resources.

Adding a phase requires one registry entry, one self-contained phase path, stable
dependencies, and that same path as its declared evidence location. A plan file
alone does not authorize execution.

Every phase plan must budget time and evidence for a thesis-quality
`procedural_writeup.md` conforming to
`../docs/phase_record_contract.md`. The writeup is a required
closeout product in addition to the manifest, tables, raw/derived evidence,
restoration record, and final report. Its accepted review state is required before
a new completion, downstream advance, or promotion review.

Completed phases are not rerun. Their documentation state is recorded in
`phase_registry.yaml` and backfilled from retained evidence, with missing facts
stated explicitly.
