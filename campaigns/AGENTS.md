# Campaign planning instructions

`phase_registry.yaml` is the sole prospective phase/dependency authority.
Detailed plans define methods but must not maintain a competing execution order.
Creating or editing a plan never authorizes hardware or changes phase status.

Completed evidence remains at the path in `registries/evidence_locations.yaml` and is
linked by stable IDs. Never copy it into a new phase as a new acquisition. Unknown
numeric inputs remain `USER_INPUT_REQUIRED` until prospectively frozen.

Every phase plan must allocate and review the mandatory thesis-quality
`procedural_writeup.md` defined by
`../docs/data_contract/procedural_writeup_standard.md`. Phase-specific deliverables
supplement, but never replace, its WHY/HOW/WHAT/implications requirements. Do not
mark a new phase complete, advance its dependents, or propose promotion until the
writeup is indexed, manifest-linked, internally reconciled, and reviewer-accepted.

For historical phases, preserve the recorded scientific status and backfill the
writeup only from retained evidence. Never rerun a completed phase or invent an
operator action, setting, observation, or rationale to improve the narrative.
