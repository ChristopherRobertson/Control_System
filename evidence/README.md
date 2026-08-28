# Non-phase operational evidence

This root is only for generic GUI/operational experiment runs and cross-campaign
catalogs that do not yet belong to a registered campaign phase. A registered phase
is self-contained under `campaigns/<campaign>/phases/<phase-id>/`, where its plan,
readbacks, raw data, analysis, reports, and artifacts remain together.

Every acquisition follows `docs/phase_record_contract.md`.
Native, rejected, preview, diagnostic, partial, excluded, and superseded evidence
remains indexed. Indexing makes a native object immutable; correction creates a
derived child rather than replacing its source.

Generic GUI output is retained under `evidence/experiments/runs/` and logs under
`evidence/experiments/logs/`; those records become campaign evidence only through an
approved, indexed import.

Every canonical campaign phase package requires a thesis-quality
`procedural_writeup.md` governed by
`docs/phase_record_contract.md`. It is a distinct indexed
artifact, not a replacement for `final_report.md` or machine-readable tables. A
new phase is not documentation-complete until the writeup is manifest-linked and
reviewer-accepted.

For completed phases, writeups are reconstructed from retained evidence without
reacquisition or invented details. The original scientific status remains intact;
documentation conformance is tracked independently until the backfill is accepted.
