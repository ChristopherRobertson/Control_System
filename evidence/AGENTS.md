# Evidence-store instructions

Evidence becomes immutable when indexed. Preserve accepted, rejected, preview,
diagnostic, partial, excluded, and superseded records. Corrections create derived
children with source relationships; they never replace native files.

Do not create observations or completion status from plans. Canonical phase paths
are registered in `../campaigns/registries/evidence_locations.yaml`; relocation or
catalog maintenance may change repository paths but must not change scientific
values, disposition, or completion state. Hashes may be diagnostic only and may not
gate loading, analysis, acceptance, closeout, or promotion.
