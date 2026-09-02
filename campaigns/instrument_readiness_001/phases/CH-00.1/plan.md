# CH-00.1 — experimental architecture and claim traceability freeze

Campaign: `instrument-readiness-001`
Domain: `validation`
Registry status: `planned`
Required dependencies: `CH-00`
Optional dependencies: `none`

This is the canonical phase plan. It does not authorize hardware, acquisition,
status changes, acceptance, recipe freeze, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Why this supplemental phase is required

The immutable completed `CH-00` disposition predates the complete architecture and
claim set in root-level `EXPERIMENTS.md`. This analysis-only supplement allocates
those requirements to the unified readiness sequence while preserving `CH-00` and
all completed evidence exactly as recorded.

## Procedure and required outputs

1. Freeze stable requirement and architecture IDs for every calibration,
   characterization, optimization, validation, initial-slow-scan, and claim
   prerequisite in `EXPERIMENTS.md`.
2. Reconcile each item against the master sequence, registry, readiness
   requirements, acquisition-method requirements, and HRP/MbCO requirements.
3. Link each item to an existing incomplete phase, `MS-02.1`, or an explicit
   unresolved gap. A completed phase may be cited only as an immutable imported
   source; no row may assign it new work.
4. Allocate the Phase-Scan synchronization and optical-pulse-coverage chain without
   collapsing its distinct questions: MS-02.1 owns the T660-1 CHD-to-PicoScope-EXT
   electrical route, MD-01 owns CHC-command/CHD-marker/Sweep-Active semantics,
   MSW-01 owns their measured timing relation, HF-02 owns sustained cross-stream
   alignment, QB-01 owns optical-omission characterization, AR-01 owns acquisition-
   policy selection, and E2E-CH owns retry/merge/reconstruction validation.
5. For every mapping record the required output, reference plane/configuration,
   native evidence class, uncertainty, acceptance boundary, downstream
   architecture or thesis claim, validity envelope, and revalidation trigger.
6. Verify that no numerical value requiring measurement or optimization is frozen
   and that literature or manufacturer values remain planning bounds only.
7. Review the dependency changes and publish the architecture prerequisites and
   unresolved recipe/thesis blockers.

The canonical allocation is
`experiment_requirements_traceability.md`. Its rows are planning requirements, not
measurement evidence. Native sources include the repository authorities and their
stable paths/versions; rejected alternatives and unresolved mappings remain visible.

## Acceptance, validity, consumers, and exclusions

Accept this phase only when every in-scope `EXPERIMENTS.md` requirement has one
unambiguous owner or explicit gap, every architecture has a dependency-complete
readiness path, master/registry/phase metadata agree, and named technical and
thesis-readiness reviewers accept the source map. Any orphan, circular dependency,
hidden numerical setting, or attempted reassignment of completed work rejects
closeout.

The allocation remains valid for the cited `EXPERIMENTS.md` and campaign-document
versions. Revalidate after a requirement, architecture, claim, topology, phase
status, dependency, device/configuration family, or promotion boundary changes.
Consumers include every incomplete readiness phase, `R0` through `R9`, the MbCO
campaign, reporting/promotion reviews, and future condition-specific recipe
freezes. This phase does not establish hardware performance, sample behavior,
scientific acceptance, phase completion, or promotion.

## Closeout

Closure requires the reviewed traceability matrix, unresolved-gap register,
dependency audit, `final_report.md`, and an indexed, manifest-linked,
reviewer-accepted `procedural_writeup.md` under
`docs/phase_record_contract.md` documenting WHY, the actual reconciliation HOW,
WHAT mappings resulted, limitations, and the reproducibility/source map.
