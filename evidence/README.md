# Measurement evidence

This is the canonical root for retained and new acquisition records. Existing
completed and in-progress phase packages are mapped by
`campaigns/registries/evidence_locations.yaml`.

New records use:

`evidence/<domain>/<campaign-id>/phases/<phase-id>/`

Each run follows `docs/data_contract/measurement_campaign_data_contract.md`. Native, rejected,
preview, diagnostic, partial, excluded, and superseded evidence remains indexed.
Planning documents do not belong here. Indexing makes a native object immutable;
correction creates a derived child rather than replacing its source.

Generic GUI output is retained under `evidence/experiments/runs/` and logs under
`evidence/experiments/logs/`; those records become campaign evidence only through an
approved, indexed import.

Every canonical phase evidence root requires a thesis-quality
`procedural_writeup.md` governed by
`docs/data_contract/procedural_writeup_standard.md`. It is a distinct indexed
artifact, not a replacement for `final_report.md` or machine-readable tables. A
new phase is not documentation-complete until the writeup is manifest-linked and
reviewer-accepted.

For historical phases, writeups are reconstructed from retained evidence without
reacquisition or invented details. The original scientific status remains intact;
documentation conformance is tracked independently until the backfill is accepted.
