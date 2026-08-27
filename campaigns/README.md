# Unified thesis campaign workspace

This directory is the authority for prospective campaign order and dependency
management. Calibration, characterization, validation, promotion, and biological
experiment are phase domains in one dependency graph; they are not independent
linear schedules.

The machine-readable authority is `registry/phase_registry.yaml`. The human-readable
execution view is `instrument_readiness_001/master_sequence.md`. Detailed legacy
procedures remain at their existing paths until individually migrated. Completed
evidence is never moved merely to match this hierarchy; `registry/evidence_locations.yaml`
maps stable phase IDs to the immutable records.

Directory responsibilities:

- `registry/`: phase, evidence, configuration, and bundle relationships;
- `instrument_readiness_001/`: the shared calibration/characterization/validation
  critical path through HRP readiness;
- `hrp_001/`: first biological campaign requirements and future phase records;
- `mbco_cryo_001/`: optional post-HRP cryogenic branch; and
- `generated/`: derived views that must never replace the registry as authority.

Adding a phase requires one registry entry, one plan path, stable dependencies, and
a declared evidence location. A plan file alone does not authorize execution.
