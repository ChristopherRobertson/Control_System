# [PHASE-ID] — [descriptive phase title]: procedural writeup

## Document control

| Field | Value |
| --- | --- |
| Campaign ID | `USER_INPUT_REQUIRED` |
| Phase ID | `USER_INPUT_REQUIRED` |
| Phase run ID(s) | `USER_INPUT_REQUIRED` |
| Domain | `USER_INPUT_REQUIRED` |
| Scientific disposition | `PLANNED` |
| Documentation status | `DRAFT` |
| Preparation mode | `PROSPECTIVE_CONTEMPORANEOUS` or `RETROSPECTIVE_EVIDENCE_RECONSTRUCTION` |
| Author ID(s) | `USER_INPUT_REQUIRED` |
| Reviewer ID(s) | `USER_INPUT_REQUIRED` |
| Document version | `0.1.0` |
| Execution interval (UTC) | `USER_INPUT_REQUIRED` |
| Writeup/review dates (UTC) | `USER_INPUT_REQUIRED` |
| Governing plan/procedure and version | `USER_INPUT_REQUIRED` |
| Configuration/calibration IDs | `USER_INPUT_REQUIRED` |

## Executive synopsis

[In one to three paragraphs, state the question, actual method, central result,
phase disposition, and most important limitation. Draft this after completing
the detailed sections.]

## 1. Purpose — WHY

### 1.1 Scientific or engineering problem

[Explain the problem and why resolving it was necessary for the instrument,
campaign, or thesis.]

### 1.2 Objective, questions, and acceptance criteria

[State the objective, predeclared questions/hypotheses, acceptance criteria,
and decision the phase was intended to support. Cite criterion IDs/versions.]

### 1.3 Dependencies, downstream use, scope, and exclusions

[Identify required upstream evidence, intended downstream consumers, tested
validity envelope, and claims deliberately outside scope.]

## 2. Procedure performed — HOW

### 2.1 Entry state and prerequisites

[Record approvals, safety state, imported bundle IDs, sample/material readiness,
environmental limits, and unresolved inputs at entry.]

### 2.2 Equipment, materials, topology, and configuration

[Define stable device/component/sample IDs, wiring/optical topology, settings,
reference planes, time origins, software/firmware/driver/recipe versions, and
calibration links needed to understand or reproduce the work.]

### 2.3 Step-by-step execution

| Step | Action actually performed | Purpose and decision rule | Settings/readbacks or observation | Evidence IDs | Outcome/next decision |
| ---: | --- | --- | --- | --- | --- |
| 1 | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` |

[Add rows in chronological order. Describe repeated blocks unambiguously and
cite the complete command/operator log instead of pasting it.]

### 2.4 Acquisition and control design as executed

[Describe controls, previews, randomization/counterbalancing, replicate and
independent-realization structure, exposure/shot budget, actual attempt counts,
and prospective acceptance/rejection rules.]

### 2.5 Analysis and uncertainty workflow

[Describe input eligibility, preprocessing/corrections, equations or model,
analysis/parameter versions, uncertainty propagation, sensitivity checks, and
acceptance evaluation. Separate direct observations from derived results.]

### 2.6 Deviations, troubleshooting, exclusions, and supersessions

[For each deviation, state when it occurred, why, who/what authorized it, which
evidence was affected, the disposition, and the validity consequence. State
explicitly if there were none.]

### 2.7 Stop, safe state, and restoration

[Describe how work ended, final instrument/sample state, restoration evidence
ID, and any intentional remaining change.]

## 3. Results — WHAT

### 3.1 Evidence population and quality accounting

| Category | Count | Stable IDs or index query | Notes |
| --- | ---: | --- | --- |
| Attempted acquisitions | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | |
| Accepted acquisitions | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | |
| Rejected/excluded acquisitions | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | |
| Controls/previews/diagnostics | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | |

### 3.2 Primary and supporting results

[Report results with units, statistic/estimator, uncertainty or explicit
limitation, replicate/sample count, reference plane, configuration ID, and
source measurement/artifact IDs. Include numbered tables and figures with
captions and sources where useful.]

### 3.3 Acceptance evaluation

| Criterion ID/version | Predeclared requirement | Observed result and evidence | Outcome | Qualification |
| --- | --- | --- | --- | --- |
| `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | `PASS/FAIL/BOUNDED` | `USER_INPUT_REQUIRED` |

### 3.4 Phase disposition

[State the final scientific disposition and identify the evidence and review
record supporting it. Reconcile it explicitly with `phase_manifest.json` and
`final_report.md`.]

## 4. Implications, caveats, and claims

### 4.1 Supported claims

| Claim ID | Precisely bounded claim | Conditions/validity envelope | Supporting evidence IDs | Uncertainty/qualification |
| --- | --- | --- | --- | --- |
| `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` |

### 4.2 Unsupported or prohibited claims

[State conclusions that the phase does not support, including untested
extrapolations, populations, configurations, wavelengths, powers, timings, or
causal/mechanistic interpretations.]

### 4.3 Caveats, limitations, and assumptions

[Discuss systematic and statistical limits, unresolved inputs, detection or
resolution bounds, model dependence, sample/replicate limits, deviations,
failed controls, and assumptions.]

### 4.4 Downstream implications and open work

[State effects on software/configuration, uncertainty, later phase entry gates,
promotion, thesis scope, revalidation, and explicitly owned follow-up work.]

## 5. Reproducibility and source map

### 5.1 Claim/result-to-evidence map

| Narrative item | Evidence or artifact IDs | Analysis/criterion version | Reproduction note |
| --- | --- | --- | --- |
| `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` |

### 5.2 Minimal reproduction procedure

1. [Identify retained inputs and eligibility rules.]
2. [Identify the versioned analysis entry point and parameters.]
3. [Identify expected machine-readable outputs and comparison criteria.]

## 6. Review record

| Review | Reviewer ID | UTC date | Outcome | Comments/action reference |
| --- | --- | --- | --- | --- |
| Evidence traceability | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | `PENDING` | |
| Technical/scientific | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | `PENDING` | |
| Thesis readiness | `USER_INPUT_REQUIRED` | `USER_INPUT_REQUIRED` | `PENDING` | |

The writeup may be marked `ACCEPTED` only after every checklist item in
`docs/data_contract/procedural_writeup_standard.md` passes and all placeholders
are resolved or converted into explicit, claim-limiting unknowns.
