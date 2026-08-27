# Unified thesis campaign workspace

This directory is the authority for prospective campaign order and dependency
management. Calibration, characterization, validation, promotion, and biological
experiment are phase domains in one dependency graph; they are not independent
linear schedules.

The machine-readable authority is `phase_registry.yaml`. The human-readable
execution view is `master_sequence.md`. Detailed procedures are organized under the
campaign that owns them. `registries/evidence_locations.yaml` maps stable phase IDs
to their canonical evidence packages.

Directory responsibilities:

- `phase_registry.yaml`: phase identity, status, ordering, and hard dependencies;
- `registries/`: evidence and configuration relationships;
- `instrument_readiness_001/`: the shared calibration/characterization/validation
  critical path through HRP readiness;
- `hrp_001/`: first biological campaign requirements and future phase records;
- `mbco_cryo_001/`: optional post-HRP cryogenic branch; and
- `methods/` and `templates/`: shared controlled campaign resources.

Adding a phase requires one registry entry, one plan path, stable dependencies, and
a declared evidence location. A plan file alone does not authorize execution.

Every phase plan must budget time and evidence for a thesis-quality
`procedural_writeup.md` conforming to
`../docs/data_contract/procedural_writeup_standard.md`. The writeup is a required
closeout product in addition to the manifest, tables, raw/derived evidence,
restoration record, and final report. Its accepted review state is required before
a new completion, downstream advance, or promotion review.

Previously completed phases are not rerun. Their documentation status is assessed
and backfilled from retained evidence, with missing facts stated explicitly. The
instrument-readiness backfill register is
`instrument_readiness_001/reports/procedural_writeup_backfill_register.md`.
