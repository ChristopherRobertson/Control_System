# Non-phase evidence-store instructions

Registered campaign phase evidence does not live here. It belongs directly in the
self-contained `campaigns/<campaign>/phases/<phase-id>/` package. This directory is
limited to generic operational runs and catalogs that have not been incorporated
into a registered phase.

Evidence becomes immutable when indexed. Preserve accepted, rejected, preview,
diagnostic, partial, excluded, and superseded records. Corrections create derived
children with source relationships; they never replace native files.

Do not create observations or completion status from plans. Canonical phase paths
are registered in `../campaigns/registries/evidence_locations.yaml`; relocation or
catalog maintenance may change repository paths but must not change scientific
values, disposition, or completion state. Hashes may be diagnostic only and may not
gate loading, analysis, acceptance, closeout, or promotion.

Each registered phase package must contain `procedural_writeup.md` before
documentation closeout. It must follow
`../docs/data_contract/procedural_writeup_standard.md`, be
indexed in `artifacts.csv` with role `procedural_writeup`, and be linked from the
manifest. Preserve source tables and logs as the numerical authority; the writeup
must cite their stable IDs rather than replacing them.

Historical backfill is a new derived documentation artifact, not a modification of
native evidence. Label it `RETROSPECTIVE_EVIDENCE_RECONSTRUCTION`, distinguish later
interpretation from contemporaneous records, and leave irrecoverable facts unknown
with an explicit claim limitation. Backfill never authorizes reacquisition.
