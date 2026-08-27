# Phase-record template implementation

These templates instantiate the shared campaign data contract. They do not
authorize a phase or create observations.

## New or resumed phase

1. Resolve the approved `phase_id`, `campaign_id`, dependencies, plan, and
   canonical evidence location from `campaigns/phase_registry.yaml` and
   `campaigns/registries/evidence_locations.yaml`.
2. Resume an existing record when one exists. Otherwise, after authorization,
   create the registered phase/run directory and copy each required table and
   manifest template without changing its header/schema.
3. Copy `procedural_writeup.template.md` to the phase root as
   `procedural_writeup.md`. Set preparation mode to
   `PROSPECTIVE_CONTEMPORANEOUS` and begin the document-control, purpose, entry
   state, configuration, and acceptance sections before acquisition.
4. During execution, maintain the chronological HOW table from actual operator,
   command, readback, acquisition, deviation, and restoration evidence. Cite
   stable IDs; do not write expected actions as though they occurred.
5. After analysis is frozen, complete WHAT and the implications/caveats/claims
   sections from machine-readable results, exclusions, uncertainty, and
   acceptance records. Build the result/claim-to-evidence source map.
6. Prepare the proposed artifact and manifest metadata without treating the
   draft as an accepted immutable artifact.
7. Reconcile the writeup against the plan, indexes, result tables, figures,
   final report, and restoration record. Resolve all template placeholders or
   convert genuinely unavailable facts to explicit claim-limiting unknowns.
8. Complete evidence-traceability, technical/scientific, and thesis-readiness
   reviews and resolve required changes.
9. Freeze the accepted writeup, index it with role `procedural_writeup` and
   `immutable: true`, then fill the manifest with its artifact ID, version,
   authors, named reviewers, `ACCEPTED` state, and UTC review time. Never
   overwrite it; later corrections use a new versioned revision artifact.
10. Run the retention audit. Phase-specific deliverables remain additional to,
   not replacements for, the common writeup.

## Historical backfill

Do not create a replacement phase or repeat measurements. Copy the procedural
template into the existing phase root, set preparation mode to
`RETROSPECTIVE_EVIDENCE_RECONSTRUCTION`, and reconstruct the narrative from the
preserved plan, manifests, indexes, logs, operator records, analysis, results,
final report, and restoration evidence.

Mark later interpretation explicitly, preserve the original scientific
disposition, and leave unsupported details unknown. Add the backfill as a new
derived documentation artifact and update the applicable documentation register.
The governing standard is
`docs/data_contract/procedural_writeup_standard.md`.
