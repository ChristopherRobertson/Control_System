# CH-00 — claim scope and calibration-import freeze: procedural writeup

## Document control

| Field | Value |
| --- | --- |
| Canonical campaign ID | `instrument-readiness-001` |
| Retained execution campaign | `system_characterization_001` |
| Phase ID | `CH-00` |
| Phase run ID | `system_characterization_001_CH-00_001` |
| Domain | Characterization governance |
| Scientific disposition | `PASS — COMPLETE AT ANALYSIS-ONLY BOUNDARY` |
| Documentation status | `DRAFT_RECONSTRUCTION_REVIEW_PENDING` |
| Preparation mode | `RETROSPECTIVE_EVIDENCE_RECONSTRUCTION` |
| Draft author | Codex, from retained repository evidence |
| Reviewer | Not assigned; review remains pending. |
| Document version | `0.1.0` |
| Execution interval | Analysis-only closeout; exact UTC drafting interval was not inferred. |
| Draft date | 2026-08-27 |
| Governing records | `plan.md`; `phase_manifest.json`; `final_report.md`; `acceptance_and_uncertainty.md` |
| Required inputs | P0 decisions; TR-01 resource closure; verified scientific briefs/crosswalk |

## Executive synopsis

CH-00 froze the smallest characterization program capable of supporting the
retained thesis claims. It mapped each claim to a measurement class and phase,
defined the two permitted acquisition topologies, limited the pump/probe regions,
allocated calibration and uncertainty dependencies, and explicitly excluded
broader surveys and optional interpretations.

The analysis-only closeout passed. No hardware was operated, no sample or CO was
handled, and no acquisition occurred. The output is a governance boundary rather
than an experimental result: it determines what downstream evidence would be
needed, but does not itself demonstrate optical, detector, spectral, temporal, or
biological performance.

## 1. Purpose — WHY

Calibration and characterization could otherwise expand indefinitely, with each
new capability adding test points that were not necessary for the thesis. CH-00
was needed to prevent scope drift and circular validation by fixing the intended
claims, minimum test grid, dependencies, acceptance logic, configuration
identity, uncertainty ownership, exposure policy, and exclusions before more
hardware phases proceeded.

Acceptance required every retained claim to have a measurement class and owner,
the minimum region/source/topology union to be frozen, P0 decisions imported,
calibration dependencies assigned explicit validity states, and optional work
excluded. The phase did not create an executable biological recipe or authorize
hardware/emission.

## 2. Procedure performed — HOW

### 2.1 Input eligibility and boundary

The eligible inputs were the verified scientific briefs and crosswalk, P0's final
requirement decisions, TR-01's resource classifications, and completed calibration
links. Manufacturer specifications, completed measurements, derived results, and
unvalidated capabilities were required to remain separate classes.

### 2.2 Chronological reconstruction

| Step | Action actually performed | Purpose and decision rule | Evidence | Outcome |
| ---: | --- | --- | --- | --- |
| 1 | The minimum claims from the verified Mylar, HRP-C-CO, and MbCO briefs were extracted. | Include only work needed for the retained thesis scope. | `claim_to_measurement_mapping.csv`; verified crosswalk/briefs | Ten retained/shared claim rows were classified. |
| 2 | Overlapping source, spectral-region, and acquisition needs were reduced to a shared minimum grid. | Measure shared anchors once and avoid duplicated characterization. | `frozen_test_grid.csv` | Seven frozen grid families cover two topologies, retained probe regions, and 532/355/540 nm source roles. |
| 3 | Every claim was assigned a responsible phase and acceptance authority. | Make downstream ownership explicit and prevent an unmeasured capability from being reported as a result. | `claim_to_measurement_mapping.csv`; `acceptance_and_uncertainty.md` | Each retained claim has a phase path and excluded extension. |
| 4 | Completed calibration inputs and validity states were linked. | Ensure downstream quantitative work imports qualified values rather than remeasures or copies them. | `calibration_links.csv`; `calibration_dependency_graph.md` | Dependency graph and link table were completed. |
| 5 | P0 decisions affecting references, environment, and detector identity were imported. | Preserve the accepted planning boundary and avoid reviving discarded work. | `imported_p0_decisions.md` | Final P0 dispositions were represented. |
| 6 | Configuration identity, uncertainty allocation, exposure budget, and acceptance rules were fixed. | Make later evidence comparable and prevent invented numerical tolerances. | `configuration_identity_conventions.md`; `acceptance_and_uncertainty.md`; `exposure_budget_policy.md` | Cross-phase conventions and owners were established. |
| 7 | Broad or optional work was entered in explicit exclusions. | Prevent implied authorization or unsupported thesis scope. | `explicit_exclusions.md`; `exclusions.csv` | Broad probe survey, direct 1064 nm sample claims, broad OPO tuning, pulse-energy distributions, peak power, and optional mechanistic extensions were excluded. |
| 8 | The package and no-transition state were audited. | Close only when the governance record was complete and no hardware state had changed. | `final_report.md`; `restoration_confirmation.json`; phase tables | Audit passed; header-only acquisition tables correctly record no acquisition. |

### 2.3 Analysis and uncertainty workflow

CH-00 performed set union, classification, dependency mapping, and ownership
allocation. It did not fit experimental data. Quantitative acceptance values that
depend on instrument performance were assigned to later phases rather than
invented. Correlated inputs were required to remain correlated, and shared
measurements were linked once.

### 2.4 Deviations and restoration

No hardware or acquisition deviation occurred. The retained permanent OPO-iris
boundary was later clarified for unexecuted work without reacquiring or rewriting
the completed CH-00 evidence. Because no physical state changed, restoration was
not required; `restoration_confirmation.json` records that negative result.

## 3. Results — WHAT

- Ten claim rows distinguish measured, derived, manufacturer-specification, and
  unvalidated-capability classes.
- Seven frozen grid rows define the minimum probe, pump/drive, and acquisition-
  topology families.
- The probe scope is limited to the local Mylar/polystyrene carbonyl window and
  combined 1885–1980 cm^-1 biological region.
- Pump roles are limited to direct 532 nm for HRP-C-CO, 355 nm as OPO drive, and
  540 nm OPO output for MbCO.
- The permitted topologies are probe-only continuous sweep and finite rare-pump
  fixed-wavenumber/recovery acquisition.
- Every retained claim has a responsible phase, acceptance authority, calibration
  dependencies, and an explicit excluded extension.
- No acquisition, hardware readback, laser emission, sample handling, or
  promotion occurred.

## 4. Implications, caveats, and claims

CH-00 supports the claim that downstream characterization has a defined minimum
scope and evidence ownership. It permits mean pulse energy to be derived only
from measured average power and verified repetition rate, with that limitation
retained. Manufacturer-only information remains a specification.

The phase does not support any measured system-performance, optical, spectral,
detector, geometry, timing, sensitivity, reproducibility, or biological claim.
Its grid is a requirements boundary, not evidence that the required conditions
have passed. Optional or broader work requires a formal scope change and its own
authorization before hardware execution.

## 5. Reproducibility and source map

| Narrative item | Primary retained source | Reproduction note |
| --- | --- | --- |
| Retained claims and owners | `claim_to_measurement_mapping.csv` | Verify every claim class, phase, authority, and exclusion. |
| Minimum grid | `frozen_test_grid.csv` | Recompute the set union from the verified briefs without adding points. |
| Dependencies | `calibration_dependency_graph.md`; `calibration_links.csv` | Keep validity states and correlation rules explicit. |
| Acceptance/uncertainty ownership | `acceptance_and_uncertainty.md` | Do not invent unresolved numeric tolerances. |
| P0 and exclusions | `imported_p0_decisions.md`; `explicit_exclusions.md` | Confirm discarded work is not revived. |
| No-transition closeout | `restoration_confirmation.json`; `final_report.md` | Confirm that required acquisition tables contain headers only. |

Minimal reproduction is a read-only comparison of the verified briefs/crosswalk
with the claim map and frozen grid, followed by dependency, exclusion, and
no-acquisition audits. Hardware execution is not part of reproduction.

## 6. Review record

| Review | Reviewer | UTC date | Outcome | Comment |
| --- | --- | --- | --- | --- |
| Evidence traceability | Not assigned | Pending | `PENDING` | Verify claim/grid completeness against the retained authorities. |
| Technical/scientific | Not assigned | Pending | `PENDING` | Review scope and uncertainty ownership. |
| Thesis readiness | Not assigned | Pending | `PENDING` | Editorial integration remains outstanding. |
