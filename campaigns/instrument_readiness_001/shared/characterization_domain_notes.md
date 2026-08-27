# Characterization domain notes

The unified phase authority is `campaigns/phase_registry.yaml`. This file
preserves cross-phase characterization rules and background only. Detailed
procedures live in the corresponding `../phases/<phase-id>/plan.md`; completed
evidence stays under its registered `evidence/characterization/` root. There is
no independent characterization directory hierarchy or execution order.

Each characterization campaign has a definition under `campaigns/` and a complete
archival evidence unit under `evidence/characterization/<campaign-id>/`.
Characterization measures instrument and system performance using qualified
calibration inputs; it does not replace or repeat calibration.

New records follow `docs/data_contract/measurement_campaign_data_contract.md`. Operational
runs that are not controlled characterization evidence continue to belong in
`evidence/experiments/runs/`.

Requirements-level experiment design precedes the final characterization test
grid. Executable experiment recipes remain downstream of promoted results.

Every phase also requires the distinct thesis-quality
`procedural_writeup.md` specified by
`docs/data_contract/procedural_writeup_standard.md`. It must reconstruct the
actual purpose, method, result, limitations, implications, and defensible claims
from indexed evidence and must be accepted before documentation closeout.
Historical backfill never requires reacquisition and must expose, not guess,
missing facts.
