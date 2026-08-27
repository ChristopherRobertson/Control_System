# Instrument-readiness procedural-writeup backfill register

Policy effective: `2026-08-27`

Authority: `docs/data_contract/procedural_writeup_standard.md`

This register tracks documentation conformance separately from the preserved
scientific disposition of historical phases. A `BACKFILL_REQUIRED` entry does
not invalidate, alter, or require reacquisition of the phase evidence. It means
the phase needs a retrospective, evidence-grounded `procedural_writeup.md`
before it is treated as thesis-documentation complete or used in a new
promotion/reuse review.

| Phase | Preserved scientific state | Procedural-writeup state | Required action |
| --- | --- | --- | --- |
| P0 | historical complete | `BACKFILL_REQUIRED` | Reconstruct from manifests, inventory, blocker table, and decision records. |
| S0 | historical complete | `BACKFILL_REQUIRED` | Reconstruct safe-idle/interlock actions, observations, and claim limits from indexed evidence. |
| MS-01 | historical complete | `BACKFILL_REQUIRED` | Reconstruct method, swaps, skew results, uncertainty, and limitations. |
| MS-02 | historical complete | `BACKFILL_REQUIRED` | Reconstruct splitter/path method, sensitivities, results, and uncertainty. |
| T2-01 | historical complete | `BACKFILL_REQUIRED` | Reconstruct route tests, acceptance, rejected evidence, and restoration. |
| T1-01 | historical complete | `BACKFILL_REQUIRED` | Reconstruct route/adapter tests, closure, diagnostics, and restoration. |
| PT-01 | PASS | `BACKFILL_REQUIRED` | Reconstruct process-trigger timing method, results, uncertainty, and applicability. |
| MC-01 | COMPLETE | `BACKFILL_REQUIRED` | Reconstruct GUI qualification, bounded continuation, results, and claim limits. |
| TR-01 | PASS | `BACKFILL_REQUIRED` | Reconstruct identity/resource closure, traceability basis, and implications. |
| OM-01 | qualified bounded PASS | `BACKFILL_REQUIRED` | Reconstruct metrology readiness, transfer standards, qualifications, and exclusions. |
| HF-01 | PASS | `BACKFILL_REQUIRED` | Reconstruct the complete configuration/model-validation workflow and bounded claims. |
| CH-00 | PASS | `BACKFILL_REQUIRED` | Reconstruct claim freeze, imported evidence, exclusions, and downstream scope. |
| WM-01 | IN_PROGRESS | `REQUIRED_BEFORE_CLOSEOUT` | Write contemporaneously as the existing phase resumes; do not create a replacement phase. |

Backfills use `preparation_mode: RETROSPECTIVE_EVIDENCE_RECONSTRUCTION`. Unknown
facts remain explicit and claim-limiting. New measurements require separate
authorization and are never performed merely to make a writeup easier.
