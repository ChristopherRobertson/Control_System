# Unified-layout completion audit

Date: 2026-08-27  
Branch: `codex/unified-campaign-layout`  
Checkpoint: `codex/pre-unified-layout-20260827` at `654f896`

## Completed restructuring

- Added logical `campaigns/`, `instrument/`, `evidence/`, `software/`, `references/`,
  and `theory/` boundaries without moving completed evidence.
- Established `campaigns/registry/phase_registry.yaml` as the sole prospective
  order/dependency authority for 68 phases.
- Added a unified master sequence, stable legacy-evidence mappings, configuration
  supersession registry, and new-evidence path contract.
- Moved the canonical HF-01.1 plan prospectively into the unified campaign tree and
  retained a compatibility pointer at its old mutable planning path.
- Listed HF-01.1 explicitly as phase 12a in the calibration procedure catalog.
- Reclassified calibration and characterization sequences as detailed procedure
  catalogs rather than competing schedules.
- Added a promoted-bundle runtime interface and schema. The bundle registry is empty;
  no configuration was promoted by restructuring.
- Centralized application paths with legacy compatibility and updated GUI-facing
  config, recipe, run, and log consumers.

## GUI and software verification

- Existing launch entry remains `python -m control_app.ui.app`.
- Hardware configuration resolves to the existing root file.
- Wiring and recipe paths resolve to their existing locations.
- The Qt GUI instantiated offscreen with `hardware_access=False`, retained its title,
  and exposed all six expected tabs.
- Full automated result: 72 passed, 3 skipped, and 24 subtests passed.
- Registry validation: PASS; 68 unique titled phases; all hard dependencies resolve;
  no hard-dependency cycle; required material and optional-branch edges pass.

No live instrument behavior is claimed by these software-only checks. A later
operator-controlled, no-emission hardware smoke test is still required before using a
restructured software release on instruments.

## Evidence preservation comparison

| Record | Before | After | Result |
|---|---:|---:|---|
| acquisition rows | 675 | 675 | unchanged |
| artifact rows | 1380 | 1380 | unchanged |
| calibration-link rows | 43 | 43 | unchanged |
| condition rows | 882 | 882 | unchanged |
| exclusion rows | 53 | 53 | unchanged |
| measurement rows | 138 | 138 | unchanged |
| phase-manifest files | 7 | 7 | unchanged |
| final-report files | 10 | 10 | unchanged |
| restoration-confirmation files | 11 | 11 | unchanged |

No file under a completed or in-progress `readbacks/` directory changed. Stable
acquisition and artifact IDs remain unique. The revised path audit resolves both
campaign-relative and phase-relative legacy artifact conventions.

Five pre-existing OM-01 external-manual links remain unresolved because their indexed
filenames use spaces while the retained repository filenames use underscores:

- `OM01-ART-EXT-0001` through `OM01-ART-EXT-0005`.

They were reported and not silently repaired or removed. The earlier preliminary
count of thirteen also included eight WM-01 false positives; those WM-01 paths resolve
correctly relative to the phase directory.

## Safety and truthfulness

No hardware was operated, no measurement phase was executed, no observation was
created, no completed status was changed, no raw evidence was altered or moved, and
no bundle was promoted. Hash matching is not an operational gate.
