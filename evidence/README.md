# Measurement evidence

This is the default root for new immutable acquisition records. Existing completed
and in-progress records remain at the legacy paths mapped by
`campaigns/registry/evidence_locations.yaml`; they are not moved to make the directory
tree look uniform.

New records use:

`evidence/<campaign-id>/phases/<phase-id>/runs/<phase-run-id>/`

Each run follows `docs/measurement_campaign_data_contract.md`. Native, rejected,
preview, diagnostic, partial, excluded, and superseded evidence remains indexed.
Planning documents do not belong here. Indexing makes a native object immutable;
correction creates a derived child rather than replacing its source.
