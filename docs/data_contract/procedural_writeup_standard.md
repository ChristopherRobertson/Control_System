# Phase procedural-writeup standard

Version: `1.0.0`

Status: **REQUIRED PHASE-CLOSEOUT STANDARD**

## 1. Purpose and authority

Every campaign phase requires a thesis-quality `procedural_writeup.md`. The
writeup is the human-readable scientific account of why the phase was needed,
how it was actually performed, what it found, and what may and may not be
concluded from the result. It is a mandatory closeout deliverable under the
measurement-campaign data contract and is not interchangeable with a plan,
command log, notebook, artifact index, or terse final report.

This standard applies to calibration, characterization, validation, promotion,
biological experiment, analysis-only, failed, bypassed, and prematurely stopped
phases. A phase may have a scientific disposition such as `PASS`, `FAIL`, or
`BYPASSED`, but it is not documentation-complete until its procedural writeup is
accepted.

The writeup does not replace machine-readable evidence. Numerical aggregation
continues to use manifests, indexes, measurements, conditions, calibration
links, and versioned analysis outputs. The writeup explains and interprets
those records for a technically literate thesis reader.

## 2. Required file, registration, and review state

The canonical phase-level file is:

```text
campaigns/<campaign-directory>/phases/<phase-id>/procedural_writeup.md
```

For phase records stored below `runs/<phase-run-id>/`, the campaign may retain
run-specific supplements, but the phase root still requires one consolidated
`procedural_writeup.md` covering every run used in the phase decision.

Before closure, the writeup must:

1. be indexed in `artifacts.csv` with a stable artifact ID and the role
   `procedural_writeup`;
2. be linked from `phase_manifest.json` through the `procedural_writeup` object;
3. identify its version, authors, reviewers, preparation mode, and review state;
4. have `review_status: ACCEPTED` for a terminal phase disposition;
5. contain no unresolved template instruction or unexplained
   `USER_INPUT_REQUIRED` marker; and
6. pass both the evidence-traceability review and the thesis-readiness review in
   Section 10.

Automated checks may confirm the file, headings, index entry, links, and
placeholders. They cannot determine whether the scientific explanation is
sufficient. Acceptance therefore requires a named human reviewer.

The working draft may be edited before it is accepted and indexed. Acceptance
freezes `procedural_writeup.md` as an immutable artifact. Never overwrite an
accepted version. A later correction is written as
`procedural_writeup_revision_<version>.md`, receives a new artifact ID and review
record, cites and supersedes the prior narrative where applicable, and becomes the
manifest's current accepted writeup. The original accepted file remains retained.

## 3. Relationship to other phase documents

- The **plan or procedure** states what was intended before execution.
- The **command log and operator records** preserve the contemporaneous action
  history.
- The **machine-readable tables and analysis artifacts** preserve observations,
  calculations, exclusions, uncertainty, and lineage.
- The **final report** records the formal acceptance decision, status, blockers,
  and downstream authorization.
- The **procedural writeup** reconstructs the complete scientific narrative from
  those sources at thesis depth.

Do not satisfy this requirement by renaming `final_report.md`. An existing final
report may be used as a source, or expanded into a separately reviewed
procedural writeup, but both roles must remain explicit and independently
indexed.

## 4. Writing and evidence rules

Write for a graduate-level reader who understands spectroscopy and experimental
science but was not present for the work. The account must be sufficiently
detailed that the reader can understand and critically evaluate the decisions,
execution, results, uncertainty, and claim boundaries without searching through
raw logs merely to discover the method.

The following rules are mandatory:

1. Describe what actually happened, not only what the plan prescribed. Use past
   tense for completed actions and clearly label planned, inferred, simulated,
   or recommended work.
2. Define abbreviations, device roles, signal names, reference planes, time
   origins, sign conventions, and configuration IDs at first use.
3. Give every reported quantitative result a unit, statistic or estimator,
   uncertainty or explicit limitation, replicate or sample count, and evidence
   reference.
4. Cite stable acquisition, artifact, configuration, calibration-bundle, sample,
   criterion, analysis, figure, and table IDs. A repository path alone is not a
   scientific citation.
5. Distinguish direct observations from derived quantities, model-dependent
   inferences, engineering decisions, and broader interpretations.
6. Report rejected, excluded, aborted, preview, control, superseded, and failed
   attempts when they affect interpretation. Never narrate only the accepted
   subset.
7. Describe deviations and troubleshooting chronologically, including their
   effect on validity and whether data acquired before or after the deviation
   were retained, rejected, or bounded.
8. State uncertainty sources and limitations even when a formal combined
   uncertainty is not available. Never convert missing information to zero.
9. Use informational hashes only as optional provenance. A hash match is not a
   substitute for evidence traceability or a closeout gate.
10. Do not invent observations, settings, rationale, or operator actions. An
    irrecoverable fact is written as unknown, with the resulting claim
    limitation.

## 5. Required document structure

Use the repository template at
`campaigns/templates/phase_record/procedural_writeup.template.md`. Additional
subsections are encouraged, but the required top-level headings and their
meaning may not be removed.

### 5.1 Document control and executive synopsis

The document-control block identifies the campaign, phase, phase runs, title,
domain, scientific disposition, documentation status, authors, reviewers,
document version, preparation mode, execution dates, writeup date, governing
plan/procedure versions, and principal configuration/calibration IDs.

The executive synopsis gives a compact account of the question, method, central
result, phase disposition, and most important limitation. It is written last and
must agree with the detailed sections.

### 5.2 Purpose — WHY

This section answers why the phase existed. It must explain:

- the scientific or engineering problem and its thesis relevance;
- the dependency, uncertainty, risk, or decision that made the work necessary;
- the phase objective, hypotheses or engineering questions, and predeclared
  acceptance criteria;
- the intended downstream consumers of the result;
- the scope and tested validity envelope; and
- questions and claims deliberately outside the phase scope.

Do not merely copy the plan objective. Explain the reasoning that connects the
phase to the larger instrument or thesis argument.

### 5.3 Procedure performed — HOW

This section is a step-by-step account of the actual work. It must include, as
applicable:

1. **Entry state and prerequisites:** approvals, safety state, imported bundles,
   prior phase outputs, sample readiness, environmental limits, and unresolved
   inputs at entry.
2. **Equipment and configuration:** stable device/component/sample IDs, wiring or
   optical topology, firmware/driver/software/recipe/analysis versions, ranges,
   rates, gains, timing, reference planes, and calibration links necessary to
   reproduce or evaluate the work.
3. **Chronological procedure:** numbered steps in execution order. Each step
   identifies the action, purpose, settings or decision rule, readback or
   observation, evidence IDs, and any stop/continue decision. Repeated blocks may
   use a table or loop definition only when the ordering and variations remain
   unambiguous.
4. **Acquisition design:** controls, previews, randomization/counterbalancing,
   replicates, independent preparations/days, acceptance/rejection rules,
   exposure or shot budget, and the actual numbers attempted and retained.
5. **Analysis and uncertainty:** preprocessing, correction sequence, equations or
   model family, fit/selection method, software and parameter-set versions,
   uncertainty propagation, sensitivity checks, and acceptance evaluation.
6. **Deviations and troubleshooting:** differences from the prospective plan,
   cause, authorization, evidence affected, corrective action, and downstream
   consequence.
7. **Stop and restoration:** how acquisition ended, final instrument/sample
   state, restoration evidence, and any state that remained intentionally
   changed.

The procedure must be detailed enough to audit the result but must not duplicate
entire raw logs. Summarize repetitive command traffic and cite the indexed log or
native readback artifact.

### 5.4 Results — WHAT

This section reports what was observed and decided. It must include:

- a result summary tied directly to the phase objective;
- the population of attempts, accepted records, exclusions, controls, and
  replicates;
- primary and supporting results with units, uncertainty/intervals, reference
  planes, and configuration IDs;
- tables and figures with numbered captions, defined symbols, sample sizes, and
  stable source IDs;
- acceptance-criterion-by-criterion outcomes, including failures and bounded or
  conditional passes;
- comparison with the expected behavior or model without hiding disagreement;
  and
- the final scientific disposition and exact evidence supporting it.

Machine-readable values remain authoritative. If prose rounds a value for
readability, identify the source table and preserve enough significant figures
to avoid changing the conclusion.

### 5.5 Implications, caveats, and claims

This section separates interpretation from observation and must state:

1. **Supported claims:** precise statements justified by the retained evidence,
   including the configuration, conditions, population, uncertainty, and
   validity envelope to which each claim applies.
2. **Unsupported or prohibited claims:** plausible-sounding conclusions the
   phase did not test, such as extrapolation to an unmeasured wavelength, device,
   sample, power, timing mode, or population.
3. **Caveats and limitations:** unresolved inputs, systematic uncertainty,
   detection or resolution limits, model dependence, sample/replicate limits,
   deviations, failed controls, and assumptions.
4. **Implications:** consequences for control-software behavior, configuration
   selection, uncertainty budgets, later phase entry gates, thesis scope, and
   promotion or revalidation.
5. **Open work:** follow-up measurements or analyses, who/what owns them, and
   whether they block use, narrow a claim, or are optional.

Use calibrated claim language. “The phase demonstrates X under conditions Y
within uncertainty Z” is acceptable when traceable. “The system works” is not.
A null or failed result receives the same level of explanation as a pass.

### 5.6 Reproducibility and source map

The final section provides a compact mapping from each major method statement,
reported result, figure/table, acceptance decision, caveat, and supported claim
to its stable evidence IDs and analysis version. It also gives the minimal
ordered reproduction procedure using retained inputs. Reproduction may verify a
result but may not silently modify native data or acceptance criteria.

## 6. Phase-type adaptations

- **Hardware phases:** include physical topology, ownership, safety transitions,
  command/readback agreement, fault handling, and restoration.
- **Analysis-only phases:** replace physical steps with input selection, data
  eligibility, transformations, model/parameter versions, computational
  environment, and reproduction commands.
- **Biological phases:** include material identity, preparation history, controls,
  randomization, independent preparation/replicate structure, exposure,
  integrity checks, exclusions, and disposition of samples.
- **Promotion phases:** explain the source phases reviewed, proposed changes,
  validity envelope, uncertainty, approval record, rollback, and why the promoted
  artifact is fit for each declared consumer.
- **Failed, blocked, bypassed, or aborted phases:** explain the attempted method,
  stopping condition, evidence retained, root cause if known, safe restoration,
  invalidated claims, bounded information that remains usable, and required
  recovery. Do not force a positive conclusion.

## 7. Drafting workflow

1. Freeze the phase evidence package for documentation review without changing
   native observations.
2. Inventory the plan, manifests, acquisition and artifact indexes, conditions,
   measurements, exclusions, calibration links, command logs, operator records,
   analysis code/results, figures, final report, and restoration record.
3. Build a chronological event outline and a claim-to-evidence table before
   writing prose.
4. Draft WHY from the prospective rationale and acceptance criteria.
5. Draft HOW from contemporaneous evidence, explicitly reconciling deviations
   against the plan.
6. Draft WHAT from machine-readable results and acceptance outputs.
7. Draft implications and claim boundaries only after WHAT is fixed.
8. Add the source map and verify every quantitative statement and claim.
9. Run structural and link checks; resolve or explicitly limit every unknown.
10. Prepare proposed artifact/manifest metadata, complete evidence-traceability,
    technical/scientific, and thesis-readiness reviews, and resolve required
    changes without treating the draft as an accepted immutable artifact.
11. Freeze the accepted file, add it to `artifacts.csv` with role
    `procedural_writeup` and `immutable: true`, and record its path, artifact ID,
    version, preparation mode, authors, named reviewers, acceptance state, and UTC
    review time in the manifest.
12. Run the retention audit. Phase-specific deliverables remain additional to,
    not replacements for, the common writeup.

## 8. Retrospective writeups for existing phases

Previously completed evidence is not reacquired merely to satisfy this standard.
Create a retrospective `procedural_writeup.md` from the preserved phase record and
set `preparation_mode: RETROSPECTIVE_EVIDENCE_RECONSTRUCTION`.

Retrospective authors must:

- preserve the original scientific disposition and all native records;
- use only documented observations and attributable context;
- distinguish contemporaneous rationale from later interpretation;
- identify gaps caused by unavailable records rather than filling them from
  memory or assumption;
- retain the original plan/report wording when a later conclusion would otherwise
  appear prospective; and
- state how every evidence gap limits reproducibility or claim strength.

Backfilling documentation does not require rerunning a phase. If the evidence is
insufficient to support part of a thesis narrative, narrow the narrative or mark
the point unresolved. A new acquisition requires a separately approved new or
suffixed phase; it is never disguised as documentation backfill.

The original phase disposition remains scientifically valid while documentation
conformance is tracked separately as `BACKFILL_REQUIRED`, `IN_REVIEW`, or
`ACCEPTED`. New promotion or thesis reuse of a historical phase requires an
accepted writeup for every source phase material to the proposed claim.

## 9. Prohibited shortcuts

The following do not satisfy the requirement:

- a copied plan written in future tense;
- a list of filenames or commands without explanation;
- an automatically generated result dump without interpretation;
- a final report containing only pass/fail statements;
- a narrative that omits rejected attempts, deviations, uncertainty, or
  limitations;
- a claim supported only by a plot with no source IDs or analysis version;
- undocumented recollection presented as an observation; or
- text whose quantitative statements cannot be reconciled to retained evidence.

## 10. Acceptance checklist

### Evidence and reproducibility review

- [ ] The file is at the canonical path and is indexed and manifest-linked.
- [ ] All required headings are present and substantive.
- [ ] Actual execution is distinguished from the prospective plan.
- [ ] Steps, configurations, analysis, deviations, and restoration are traceable.
- [ ] Every quantitative result includes units, uncertainty/limitation, sample or
      replicate context, and a stable source ID.
- [ ] Attempt, exclusion, control, and acceptance counts reconcile to indexes.
- [ ] Figures and tables identify their retained source and analysis version.
- [ ] The source map supports reproduction from retained inputs.
- [ ] No observation was invented and no missing value was encoded as zero.

### Thesis-readiness review

- [ ] WHY explains the scientific rationale and thesis relevance.
- [ ] HOW is detailed enough for critical evaluation and reasonable reproduction.
- [ ] WHAT reports results neutrally, including failures and discordant evidence.
- [ ] Supported claims are precise and bounded by configuration and validity.
- [ ] Unsupported claims, caveats, assumptions, and open work are explicit.
- [ ] The synopsis, detailed results, final report, and machine-readable status
      agree.
- [ ] Terminology, symbols, units, captions, and cross-references are consistent.
- [ ] A named technical reviewer has marked the writeup `ACCEPTED`.
