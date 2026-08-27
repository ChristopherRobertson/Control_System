# Instrument readiness 001

This campaign unifies the calibration, characterization, independent validation,
reporting, and promotion work required before HRP. `../master_sequence.md` is the
human-readable execution view; `../phase_registry.yaml` is the sole
machine-readable phase/dependency authority.

Detailed procedures remain linked by registry `plan` fields. Completed evidence is
linked by `evidence_key` to `evidence/calibration/` or
`evidence/characterization/`; it is never represented as a new acquisition merely
because its path changed. Optional cryogenic MbCO work is a separate campaign and
cannot block this core path.
