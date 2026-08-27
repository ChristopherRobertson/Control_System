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
