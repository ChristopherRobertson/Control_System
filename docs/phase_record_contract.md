# Campaign phase-record and procedural-writeup contract

Version: `2.0.0`

Status: **REQUIRED FOR NEW PHASE EXECUTION, CLOSEOUT, AGGREGATION, AND PROMOTION**

## 1. Purpose and scope

This contract makes calibration, characterization, validation, promotion, and
experiment records collectable, reviewable, aggregatable, and thesis-ready without
reacquisition. Existing native evidence remains valid and is linked through stable
indexes. A documentation requirement never authorizes new measurement work or a
change to a completed scientific disposition.

Machine-readable evidence remains the numerical authority. The procedural writeup
is the human-readable scientific account of why the phase was necessary, how it
was actually performed, what it found, and what may and may not be claimed.

## 2. Stable identifiers

Identifiers are ASCII, human-readable, stable, and never reused:

- `campaign_id`: stable campaign identity;
- `phase_id`: registered phase identity;
- `phase_run_id`: one authorized continuation-safe run record;
- `acquisition_id`: every attempted acquisition, including rejected attempts;
- `artifact_id`: every indexed native or derived artifact;
- `configuration_id`: complete effective setup and settings identity;
- `calibration_bundle_id`: promoted or explicitly bounded provisional bundle;
- `sample_id`, `device_id`, `component_id`, and `operator_id`: registry identities.

Tables join on these keys, never on filenames, hashes, or row order.

## 3. Canonical phase package

```text
campaigns/<campaign-directory>/phases/<phase-id>/
├── README.md
├── phase.yaml
├── plan.md
├── run_record.md                 # when a contemporaneous overview exists
├── phase_manifest.json           # once execution produces a manifest
├── acquisition_index.csv
├── conditions.csv
├── measurements.csv
├── artifacts.csv
├── exclusions.csv
├── calibration_links.csv
├── command_log.txt
├── final_report.md
├── procedural_writeup.md
├── restoration_confirmation.json
├── raw/
├── analysis/
├── figures/
└── tables/
```

The phase directory is the complete package. Empty required tables retain their
header. Native/device files remain in their lossless format under `raw/`; tabular
exports supplement rather than replace them.

## 4. Canonical tables

### Acquisition index

One row records every attempted acquisition:

```text
campaign_id,phase_id,phase_run_id,acquisition_id,parent_acquisition_id,start_utc,end_utc,operator_id,configuration_id,calibration_bundle_id,sample_id,measurement_kind,condition_set_id,replicate_index,planned,accepted,rejection_code,raw_primary_artifact_id,notes
```

Rejected, preview, control, diagnostic, aborted, and unplanned attempts remain
indexed. `planned=false` identifies work outside the original acquisition grid.

### Conditions

```text
campaign_id,phase_id,acquisition_id,condition_set_id,condition_name,value_text,value_number,unit,source,uncertainty_value,uncertainty_unit,uncertainty_type,notes
```

Setpoints and readbacks are separate conditions. Use either `value_text` or
`value_number`; zero is never a missing-value substitute.

### Measurements

```text
campaign_id,phase_id,acquisition_id,result_set_id,quantity_name,value,unit,statistic,reference_plane,sign_convention,correction_state,standard_uncertainty,coverage_factor,expanded_uncertainty,quality_flag,analysis_artifact_id,notes
```

`correction_state` is `raw`, `corrected`, `derived`, or `bounded`. Named
corrections and uncertainties remain explicit. Non-numeric device outcomes remain
textual quality states and are not coerced to zero.

### Artifacts

```text
artifact_id,campaign_id,phase_id,acquisition_id,relative_path,artifact_role,media_type,byte_size,created_utc,modified_utc,producer,source_artifact_ids,immutable,notes
```

Paths are relative to the campaign or phase root as declared by the manifest.
Roles distinguish native data, readback, observation, log, analysis source,
derived table, figure, report, procedural writeup, photograph, and reference link.

### Exclusions

```text
campaign_id,phase_id,acquisition_id,decision_utc,decision_maker,exclusion_code,criterion_version,reason,downstream_effect,superseded_by_acquisition_id,notes
```

Exclusion never removes or mutates the source acquisition.

### Calibration links

```text
campaign_id,phase_id,phase_run_id,calibration_bundle_id,calibration_quantity_id,source_campaign_id,source_phase_id,source_artifact_id,value_used,unit,standard_uncertainty,validity_status,notes
```

This is the foreign-key bridge through which downstream phases consume completed
calibration without copying or repeating it.

## 5. Manifest, provenance, and versioning

New manifests validate against `instrument/schemas/phase_manifest.schema.json` and
use the current schema version. Retained manifests remain readable under their
recorded version. A manifest records the actual branch and dirty-file list,
device/configuration identities, settings/readbacks, software/driver/recipe/
analysis versions, imported bundles, artifacts, deviations, phase status,
restoration, and procedural-writeup review state.

UTC timestamps use ISO 8601 with a `Z` suffix. Units are explicit and stable.
Missing values are empty with a reason or `USER_INPUT_REQUIRED`. Corrections and
reanalysis create new derived artifacts with new IDs. Superseded records remain
indexed and point to replacements.

Native artifacts become immutable after indexing. An accepted procedural writeup
also becomes immutable; a correction is a separately indexed revision with a new
version, artifact ID, review record, and supersession relationship.

Use relative paths, byte sizes, timestamps, versions, IDs, and producer/source
records for reproducibility. Hashes may be informational only and cannot be the
sole loading, analysis, reproduction, acceptance, closeout, or promotion gate.

## 6. Procedural writeup

Every phase requires:

```text
campaigns/<campaign-directory>/phases/<phase-id>/procedural_writeup.md
```

The writeup is distinct from the prospective plan, command log, raw evidence,
analysis outputs, and `final_report.md`. It is indexed in `artifacts.csv` with
role `procedural_writeup`, linked from the manifest, versioned, attributed to its
authors and named reviewers, and marked `ACCEPTED` before documentation closeout.

Write for a graduate-level reader who understands spectroscopy and experimental
science but was not present. Define abbreviations, device roles, signals,
reference planes, time origins, sign conventions, and configurations at first use.
Every quantitative result states units, estimator/statistic, uncertainty or
explicit limitation, population/replicate context, and stable evidence IDs.

Distinguish direct observations, derived quantities, model-dependent inferences,
engineering decisions, and broader interpretation. Report rejected, excluded,
aborted, preview, control, failed, and superseded work when it affects the result.
Never invent an observation, setting, rationale, or operator action.

### Required structure

#### Document control and executive synopsis

Identify campaign, phase, phase runs, title, domain, scientific disposition,
documentation status, authors, reviewers, version, preparation mode, dates,
governing plan/procedure versions, and principal configurations/bundles. Summarize
the question, method, central result, disposition, and principal limitation.

#### Purpose — WHY

Explain the scientific or engineering problem, thesis relevance, dependency or
risk addressed, objectives, questions, acceptance criteria, downstream consumers,
tested validity envelope, and deliberately excluded scope. Do not merely repeat
the plan objective.

#### Procedure performed — HOW

Provide a chronological account of the actual work:

1. Entry state, approvals, safety, imported results, and unresolved inputs.
2. Equipment, wiring/optical topology, configurations, versions, ranges, rates,
   timing, reference planes, and calibration links.
3. Numbered actions with their purpose, settings, observation/readback, evidence
   IDs, and stop/continue decision.
4. Controls, previews, replication, randomization/counterbalancing, attempted and
   accepted counts, exclusion rules, and exposure budget.
5. Preprocessing, corrections, equations/models, fit/selection methods, analysis
   versions, uncertainty propagation, sensitivity checks, and criteria.
6. Deviations and troubleshooting in sequence, including affected evidence and
   downstream consequences.
7. Stop, final state, and restoration evidence.

Summarize repetitive command traffic and cite the indexed log rather than copying
it into prose.

#### Results — WHAT

Report the attempt population, accepted records, exclusions, controls, primary
and supporting results, units, uncertainties, reference planes, configurations,
numbered tables/figures, expected-versus-observed comparison, criterion-by-
criterion outcome, and exact scientific disposition. Machine-readable values
remain authoritative when prose rounds a result.

#### Implications, caveats, and claims

State supported claims with their configuration, conditions, population,
uncertainty, and validity envelope. State unsupported/prohibited extrapolations,
unresolved inputs, systematic limitations, detection/resolution limits, model
dependence, deviations, assumptions, downstream consequences, revalidation
triggers, and owned open work.

#### Reproducibility and source map

Map every major method statement, result, figure/table, acceptance decision,
caveat, and claim to stable evidence IDs and analysis versions. Give the minimal
ordered reproduction procedure using retained inputs without modifying native
data or criteria.

## 7. Writeup preparation and review

1. Freeze the evidence package for documentation review.
2. Inventory plans, manifests, indexes, conditions, measurements, exclusions,
   calibration links, logs, operator records, analysis, figures, final report,
   and restoration.
3. Build a chronological event outline and claim-to-evidence map.
4. Draft WHY from the prospective rationale and criteria.
5. Draft HOW from contemporaneous evidence and reconcile deviations.
6. Draft WHAT from machine-readable results and acceptance outputs.
7. Draft implications and claim boundaries only after results are fixed.
8. Add the source map and check every quantitative statement.
9. Resolve or explicitly limit every unknown and remove template instructions.
10. Complete evidence-traceability, technical, and thesis-readiness review.
11. Index and manifest-link the accepted immutable document.
12. Run the phase retention audit.

For a completed phase whose writeup was not prepared during execution, use
`preparation_mode: RETROSPECTIVE_EVIDENCE_RECONSTRUCTION`. Preserve the recorded
scientific disposition, use only attributable records, distinguish contemporaneous
rationale from later interpretation, expose gaps, and narrow claims when evidence
is insufficient. Documentation reconstruction never requires reacquisition.

## 8. Phase-type adaptations

- Hardware phases include topology, ownership, safety transitions, command/
  readback agreement, fault handling, and restoration.
- Analysis-only phases document input eligibility, transformations, model and
  parameter versions, environment, and reproduction commands.
- Biological phases include material identity, preparation, controls,
  randomization, independent preparations/replicates, exposure, integrity,
  exclusions, and sample disposition.
- Promotion phases document source phases, proposed machine-readable changes,
  validity, uncertainty, approval, rollback, and declared consumers.
- Failed, blocked, bypassed, or aborted phases document the attempted method,
  stop condition, retained evidence, root cause if known, safe restoration,
  invalidated claims, bounded usable information, and recovery requirement.

## 9. Aggregation and retention audit

Aggregation concatenates tables only under compatible declared schema versions,
verifies primary-key uniqueness, required artifact metadata, path existence,
byte-size consistency, and relationships, then joins on stable IDs. It never
parses prose to recover numerical results.

Before closure verify that:

1. Every attempted acquisition is indexed.
2. Every native and derived artifact has an ID, relative path, byte size,
   timestamp, producer, and role.
3. Accepted, rejected, preview, control, excluded, aborted, and superseded states
   remain distinguishable.
4. Settings, readbacks, conditions, units, identities, and calibration links exist.
5. Results identify analysis version, reference plane, correction state, and
   uncertainty or explicit limitation.
6. The procedural writeup is substantive, indexed, manifest-linked, reconciled,
   placeholder-free, and accepted by named reviewers.
7. Every major writeup result and claim maps to evidence and analysis versions.
8. Restoration and safe final state are recorded when hardware was involved.
9. No bundle was promoted without the registered approval gate and accepted
   source-phase documentation.
