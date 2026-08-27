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

All phases inherit the procedural-writeup closeout standard at
`../../docs/data_contract/procedural_writeup_standard.md`. The narrative is required
in addition to phase-specific technical deliverables and must be indexed,
manifest-linked, evidence-traceable, and reviewer-accepted. Historical scientific
dispositions remain preserved while missing narratives are tracked in
`reports/procedural_writeup_backfill_register.md`; documentation backfill never
requires repeating a completed measurement.
