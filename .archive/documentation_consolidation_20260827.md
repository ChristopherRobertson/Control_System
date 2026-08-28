# Documentation consolidation record — 2026-08-27

## Purpose

This record shows where the active information from each relocated source is now
maintained. The source files themselves remain intact at their path-mirrored
locations below `.archive/`. No phase acquisition, readback, analysis result,
artifact index, report, or other scientific evidence was removed or replaced by
this consolidation.

## Repository documentation coverage

| Retained source path below `.archive/` | Active authority |
| --- | --- |
| `docs/architecture/repository_cleanup_20260814.md` | `README.md`, `docs/README.md`, and `docs/AGENTS.md` define the active hierarchy, authority flow, preservation rule, and documentation-maintenance policy. |
| `docs/architecture/repository_scope.md` | `README.md` and `docs/README.md` define repository scope, directory responsibilities, scientific boundaries, and the control-application interface. |
| `docs/architecture/experiment_builder_architecture.md` | `docs/README.md` defines the GUI/workflow architecture and runtime boundary; detailed operator procedures remain under `docs/operating_procedures/`. |
| `docs/architecture/recipe_driven_workflow_ui.md` | `docs/README.md` defines the recipe-driven application boundary; recipes remain under `instrument/recipes/`. |
| `docs/data_contract/measurement_campaign_data_contract.md` | `docs/phase_record_contract.md` defines stable IDs, phase-package layout, tables, manifests, provenance, versioning, aggregation, and retention. |
| `docs/data_contract/procedural_writeup_standard.md` | `docs/phase_record_contract.md` defines the required thesis-level WHY/HOW/WHAT/claims narrative, retrospective reconstruction, review, indexing, and phase-type adaptations. |

## Instrument-readiness documentation coverage

| Retained source path below `.archive/` | Active authority |
| --- | --- |
| `campaigns/instrument_readiness_001/shared/calibration_campaign_history.md` | `campaigns/instrument_readiness_001/README.md`, `campaigns/phase_registry.yaml`, and the completed phase packages define current state and retained evidence. |
| `campaigns/instrument_readiness_001/shared/characterization_campaign_history.md` | `campaigns/instrument_readiness_001/README.md`, `campaigns/master_sequence.md`, and the phase packages define current state and remaining work. |
| `campaigns/instrument_readiness_001/shared/calibration_deferred_dependency_register_20260825.csv` | Required phase dependencies are in `campaigns/phase_registry.yaml`; the remaining WM-01 external equipment constraint is recorded there explicitly. |
| `campaigns/instrument_readiness_001/shared/characterization_deferred_dependency_register_20260825.csv` | Required characterization dependencies are in `campaigns/phase_registry.yaml`; phase plans own resource and operator-input gates. |
| `campaigns/instrument_readiness_001/shared/calibration_domain_notes.md` | `campaigns/instrument_readiness_001/requirements.md` and `AGENTS.md` define domain boundaries, evidence reuse, and promotion behavior. |
| `campaigns/instrument_readiness_001/shared/characterization_domain_notes.md` | `campaigns/instrument_readiness_001/requirements.md` and `AGENTS.md` define characterization boundaries, provisional inputs, and calibration-defect handling. |
| `campaigns/instrument_readiness_001/shared/calibration_gap_analysis.md` | `campaigns/master_sequence.md`, `campaigns/phase_registry.yaml`, `campaigns/instrument_readiness_001/requirements.md`, and phase plans encode all required phases and gaps. |
| `campaigns/instrument_readiness_001/shared/calibration_measurement_matrix.csv` | `campaigns/instrument_readiness_001/requirements.md` defines minimum cross-phase coverage; every phase plan contains the complete grid, method, products, and acceptance logic. |
| `campaigns/instrument_readiness_001/shared/characterization_measurement_matrix.csv` | `campaigns/instrument_readiness_001/requirements.md` defines minimum cross-phase coverage; every phase plan contains the complete grid, method, products, and acceptance logic. |
| `campaigns/instrument_readiness_001/shared/electrical_timing_method.md` | Section 6 of `campaigns/instrument_readiness_001/requirements.md` defines cross-phase timing rules; MS-01 through CL-01 plans define the exact phase procedures. |
| `campaigns/instrument_readiness_001/shared/expansion_gap_map.md` | `campaigns/master_sequence.md`, `campaigns/phase_registry.yaml`, and Section 7 of the campaign requirements define the complete dependency graph and measurement coverage. |
| `campaigns/instrument_readiness_001/shared/experiment_requirement_campaign_crosswalk.md` | Section 7 of the campaign requirements maps the bounded instrument measurements; HRP and MbCO requirements retain biological-only work. |
| `campaigns/instrument_readiness_001/shared/phase_execution_requirements.md` | `campaigns/instrument_readiness_001/requirements.md` defines authorization, entry review, evidence, common constraints, timing, closeout, and handoff. |
| `campaigns/instrument_readiness_001/shared/procedural_writeup_backfill_register.md` | `campaigns/phase_registry.yaml` records scientific and documentation state separately; `docs/phase_record_contract.md` defines retrospective reconstruction. |

## Preservation and use

The relocation is organizational. It does not authorize execution, modify a
scientific disposition, promote a result, or require reacquisition. During a
retrospective writeup, begin with the canonical phase package and use an archived
source only to recover context that can be traced to retained evidence. If the
records do not support a detail, identify it as unknown and constrain the claim.

Archive resolution is path based. Repository checks may report size, timestamp,
version, branch/commit context, and source identity; they do not require a stored
hash to match as an operational condition.
