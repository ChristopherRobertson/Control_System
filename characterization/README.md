# Instrument characterization campaigns

The unified phase authority is `campaigns/registry/phase_registry.yaml`. This
directory retains detailed characterization procedures and completed evidence; it no
longer maintains an independent execution order.

Each characterization campaign is a complete archival unit under
`characterization/<campaign-id>/`. Characterization measures instrument and
system performance using qualified calibration inputs; it does not replace or
repeat calibration.

New records follow `docs/measurement_campaign_data_contract.md`. Operational
runs that are not controlled characterization evidence continue to belong in
`runs/`.

Requirements-level experiment design precedes the final characterization test
grid. Executable experiment recipes remain downstream of promoted results.
