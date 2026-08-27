# Phase-primary campaign-layout completion

> **Superseded layout note:** this document records the intermediate phase-plan
> materialization. The final phase packages now include their retained run data and
> artifacts directly; see `self_contained_phase_packages_20260827.md`.

Date: `2026-08-27`  
Branch: `codex/physical-unified-layout`  
Pre-restructure checkpoint: `codex/pre-unified-layout-20260827` at `654f896`

## Purpose

This correction completes the intended phase-primary restructure. The preceding
layout had moved evidence but left most calibration and characterization phase
definitions inside two combined procedure catalogs and retained parallel
`planning/` and `procedures/` hierarchies. That was incomplete and ambiguous.

The active layout now represents every registered phase exactly once under its
own campaign phase directory. Domain names remain registry metadata; they no
longer create competing directory structures or execution sequences.

## Materialized phase homes

| Campaign | Registered phases | Canonical homes created/verified |
| --- | ---: | ---: |
| `instrument-readiness-001` | 47 | 47 |
| `hrp-001` | 10 | 10 |
| `mbco-cryo-001` | 11 | 11 |
| **Total** | **68** | **68** |

Every home contains `README.md`, `phase.yaml`, and `plan.md`. Each of the 48
phase sections formerly present in the two combined instrument procedure catalogs
(47 instrument-readiness phases plus optional `QB-01M`) was matched to exactly one
canonical plan. The HRP and MbCO requirement-table rows were materialized into the
remaining biological phase plans, which inherit their complete campaign
requirements.

`HF-01.1` retained its more detailed existing plan and received the corresponding
preserved catalog detail. Existing phase-specific files such as the HF-01 planning
basis and SV-02A/SV-02B requirement material remain beside their canonical plans.
Rows from the former measurement matrices were copied into phase-local
`planning_context.md` files where applicable so phase-specific planning work was
not lost.

## Cross-phase material

Only genuinely cross-phase material remains in
`campaigns/instrument_readiness_001/shared/`:

- common execution and closeout requirements;
- electrical timing method;
- calibration and characterization measurement matrices;
- deferred-dependency registers and gap/crosswalk material;
- historical campaign context; and
- the procedural-writeup backfill register.

The prior active `planning/`, `procedures/`, `reports/`, and `promotion/`
containers were removed after their retained material was relocated. The combined
catalogs were retired after their phase-specific sections were materialized. They
remain recoverable in Git history, the checkpoint branch, and the user's external
backup; they are not duplicated in the active tree.

## Evidence preservation

No evidence package was deleted, renamed, or rewritten during this correction.
Completed and in-progress phase homes point through `evidence_key` and
`campaigns/registries/evidence_locations.yaml` to the existing canonical evidence.
Planned phases explicitly state that no evidence package exists until execution is
authorized.

Historical accepted manifests intentionally retain source-path strings from the
layout that existed when they were created. Those strings are provenance, not an
active second directory hierarchy. Current plans and software references use the
new canonical paths.

The physical-migration audit confirmed unchanged stable file counts for all 12
historical/in-progress instrument phases, no unresolved artifact paths, and no
operational hash gate. The reconstruction audit found no duplicate stable IDs and
no unresolved artifact paths.

## Enforced invariants

`software/tools/validate_phase_registry.py` and the repository tests now require:

1. every registry plan to be exactly
   `campaigns/<campaign>/phases/<phase-id>/plan.md`;
2. every phase home to contain `README.md`, `phase.yaml`, and `plan.md`;
3. phase metadata, dependencies, status, evidence key, and evidence location to
   agree with the registries;
4. every phase plan to require `procedural_writeup.md`;
5. every instrument-readiness plan to inherit the shared execution requirements;
6. exactly 47 instrument-readiness, 10 HRP, and 11 MbCO registered phase homes;
   and
7. the retired split-layout directories to remain absent.

## Verification result

- phase registry: `PASS`, 68 phases, acyclic dependency graph;
- complete test suite: `77 passed, 3 skipped, 24 subtests passed`;
- GUI and unified-layout smoke tests: `10 passed`;
- physical evidence migration audit: `PASS`, no errors;
- campaign reconstruction audit: `PASS`, no duplicate IDs or unresolved paths;
  and
- active references to retired planning/procedure/report/promotion paths: none.
