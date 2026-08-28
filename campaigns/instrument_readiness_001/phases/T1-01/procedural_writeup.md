# T1-01 — T660-1 trigger and output routes: procedural writeup

## Document control

| Field | Value |
| --- | --- |
| Canonical campaign ID | `instrument-readiness-001` |
| Phase ID | `T1-01` |
| Phase run ID(s) | No stable phase-run ID is present in the retained T1-01 overview. |
| Domain | Calibration |
| Scientific disposition | `PASS — COMPLETE` |
| Documentation status | `DRAFT_RECONSTRUCTION_REVIEW_PENDING` |
| Preparation mode | `RETROSPECTIVE_EVIDENCE_RECONSTRUCTION` |
| Operator | Christopher Robertson |
| Draft author | Codex, from retained repository evidence |
| Reviewer | Not assigned; review remains pending. |
| Document version | `0.1.0` |
| Execution closeout | Default wiring and final safe idle were confirmed 2026-08-13; exact start UTC was not reconstructed. |
| Draft date | 2026-08-27 |
| Governing records | `plan.md`; `run_record.md`; `final_report.md`; `t1_01_results.json` |
| Imported correction | T2-01 EXT REF-to-T660-1-TRIG-IN route |

## Executive synopsis

T1-01 completed the electrical timing chain through T660-1 by measuring the
trigger-input-to-FIRE and trigger-input-to-Q-SWITCH routes and the FIRE-to-
Q-SWITCH separation. Because the direct DB9 measurements required two adapters,
the phase also characterized both adapter delays instead of assuming either was
zero.

The retained accepted population contains 2,600 traces. The fitted results were
`50.7471 ± 3.1419 ns` from T660-1 trigger input to FIRE,
`0.149286 ± 0.951338 ns` from FIRE to Q-SWITCH, and
`50.9372 ± 3.0676 ns` from trigger input to Q-SWITCH. Direct and derived
EXT REF-to-Q-SWITCH estimates closed within `0.0407522 ns`. Three hundred
initial-wiring traces remain preserved as rejected evidence and are not included
in the accepted results.

## 1. Purpose — WHY

The T2-01 result ended at T660-1 TRIG IN. Operational timing also depends on the
internal T660-1 response and the physical FIRE and Q-SWITCH output paths. T1-01
was required to calibrate those remaining electrical segments, characterize the
measurement adapters, verify trigger-count behavior, and test chain closure
before MIRcat Process Trigger timing.

The phase remained nonemitting and did not promote a canonical bundle or
authorize PT-01. Its conclusions apply only to the recorded configurations,
reference planes, adapters, and programmed delay interval.

## 2. Procedure performed — HOW

### 2.1 Entry state and topology

Both lasers remained nonemitting. The phase used the PicoScope to compare T660-1
FIRE and Q-SWITCH electrical outputs with the EXT REF timing reference across six
programmed delays from 0 ns through 1 ms. Adapter A and Adapter B provided the
documented DB9/breakout measurement interfaces; their delays were measured in
normal and swapped orientations.

### 2.2 Chronological reconstruction

| Step | Action actually performed | Purpose and decision rule | Evidence | Outcome |
| ---: | --- | --- | --- | --- |
| 1 | Ownership and safe-idle conditions were established before rewiring or output activity. | Protect the nonemitting boundary and obtain attributable control. | Preflight and safe-idle records | Entry checks passed. |
| 2 | Direct EXT REF-to-FIRE and EXT REF-to-Q-SWITCH configurations were acquired over six programmed delays. | Measure the complete electrical routes before subtracting the known T2-01 segment. | Primary setup directories; acquisition index | 1,800 accepted primary traces were retained. |
| 3 | FIRE and Q-SWITCH were measured with the adapter assignment reversed over the same delay grid. | Isolate the FIRE-to-Q-SWITCH difference from adapter asymmetry. | Setup 2 records; `setup_2_adapter_swap_result.json` | 600 accepted adapter-swap traces were retained. |
| 4 | Adapter A and B were characterized in normal and swapped splitter orientations. | Estimate absolute adapter corrections without assigning either adapter zero delay. | `adapter_absolute_delay_result.json`; adapter raw/configuration records | 100 traces per orientation were accepted; Adapter A and B delays were estimated. |
| 5 | The T2-01 EXT REF-to-T660-1-TRIG-IN intercept was subtracted from adapter-corrected direct fits. | Express results at the T660-1 trigger-input reference plane. | `t1_01_results.json`; route analysis files | Trigger-to-FIRE and trigger-to-Q-SWITCH delays were derived. |
| 6 | Direct and derived EXT REF-to-Q-SWITCH paths and trigger counters were compared. | Detect a sign, routing, adapter, or counting inconsistency. | `direct_derived_closure.json`; diagnostics | Closure and trigger-count checks passed. |
| 7 | Default wiring was restored and final safe idle was checked. | End the phase with no active timing output. | `restoration_confirmation.json`; final readback records | Restoration and safe idle passed. |

### 2.3 Analysis and uncertainty workflow

Six-point fits supplied direct route intercepts and slopes. Adapter A was removed
from the direct routes using its measured delay. The completed T2-01 intercept
was then subtracted to move the origin from EXT REF to T660-1 TRIG IN. The
FIRE-to-Q-SWITCH result was the midpoint of normal and adapter-swapped fits.
Uncertainties conservatively combined fit statistics, threshold and interpolation
sensitivities, absolute adapter uncertainty, and the imported T2-01 route term,
with shared PicoScope evidence retained as correlated.

### 2.4 Deviations, rejected evidence, and restoration

Three hundred traces from an initial wiring configuration are retained as
rejected evidence. The accepted result uses only the corrected valid measurement
configurations; no accepted measurement trace was rejected. The retained records
do not justify reconstructing more specific actions for the initial wiring than
those documented by its exclusion. Final wiring and safe idle were operator-
confirmed on 2026-08-13.

## 3. Results — WHAT

| Quantity | Result | Derivation/qualification |
| --- | ---: | --- |
| T660-1 TRIG IN to FIRE | `50.7471 ± 3.1419 ns` | Combined standard uncertainty; T2-01 segment subtracted |
| FIRE to Q-SWITCH | `0.149286 ± 0.951338 ns` | Midpoint of normal and adapter-swapped fits |
| T660-1 TRIG IN to Q-SWITCH | `50.9372 ± 3.0676 ns` | Combined standard uncertainty; T2-01 segment subtracted |
| Adapter A delay | `6.43913 ± 0.322384 ns` | Standard uncertainty |
| Adapter B delay | `6.34175 ± 0.322384 ns` | Standard uncertainty |
| Direct-minus-derived closure | `0.0407522 ns` | PASS |

Accepted measurement traces totaled 2,600: 1,800 primary six-point traces, 600
adapter-swap six-point traces, and 200 absolute-adapter traces. The 300 preserved
initial-wiring traces are rejected evidence. Trigger-count agreement, chain
closure, restoration, and safe idle passed.

## 4. Implications, caveats, and claims

T1-01 supports the reported installed electrical route delays and adapter
corrections within the recorded topology and 0–1 ms programmed-delay interval.
The independent direct/derived closure supports the internal consistency of the
route decomposition at sub-nanosecond residual scale.

The phase does not establish optical pulse emission time, arbitrary adapter or
cable behavior, or certificate-level PicoScope traceability. Its uncertainties
depend on retained model and correction choices, and the T2-01/MS-02 evidence is
correlated across derived routes. PT-01 could use these corrections only after
its own setup, reference plane, and authorization were established.

## 5. Reproducibility and source map

| Narrative item | Primary retained source | Reproduction note |
| --- | --- | --- |
| Full-precision route results | `t1_01_results.json` | Numerical authority for values and counts. |
| Adapter swap | `setup_2_adapter_swap_result.json` | Preserve the recorded normal/swapped sign convention. |
| Absolute adapter correction | `adapter_absolute_delay_result.json` | Do not set either adapter delay to zero. |
| Chain closure | `direct_derived_closure.json` | Compare direct and summed/derived paths using common corrections. |
| Rejected initial wiring | Acquisition/exclusion records; `final_report.md` | Retain but exclude the 300 traces from accepted fits. |
| Restoration | `restoration_confirmation.json`; final readbacks | Verify default wiring and safe idle. |

Minimal reproduction is to run the retained analyses over only eligible
acquisitions, apply adapter and T2-01 corrections with their recorded signs,
and compare results to `t1_01_results.json` and the closure record.

## 6. Review record

| Review | Reviewer | UTC date | Outcome | Comment |
| --- | --- | --- | --- | --- |
| Evidence traceability | Not assigned | Pending | `PENDING` | Verify accepted/rejected population accounting. |
| Technical/scientific | Not assigned | Pending | `PENDING` | Review correction covariance and closure interpretation. |
| Thesis readiness | Not assigned | Pending | `PENDING` | Editorial integration remains outstanding. |
